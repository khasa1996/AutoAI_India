"""Admin APIs for verified configurator asset metadata, storage and publication."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from tempfile import SpooledTemporaryFile
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field, ValidationError

from configurator_asset_ingestion import build_verified_asset_metadata
from configurator_asset_inspection import inspect_gltf_bytes
from configurator_asset_storage import (
    AssetStorageConfigError,
    build_asset_storage_key,
    create_presigned_upload,
    download_object,
    get_asset_storage_config,
    head_object,
    public_asset_url,
)
from configurator_asset_validation import validate_asset_manifest
from configurator_schemas import ConfiguratorAssetCreate, ConfiguratorAsset
from vehicle_schemas import ConfiguratorStatus

_MAX_UPLOAD_BYTES = 200 * 1024 * 1024


class AssetManifestValidationRequest(BaseModel):
    asset: ConfiguratorAssetCreate
    mesh_names: List[str] = Field(default_factory=list, max_length=10000)
    material_names: List[str] = Field(default_factory=list, max_length=10000)


class AssetPublicationRequest(BaseModel):
    asset_id: str = Field(..., max_length=100)
    publish: bool


class AssetReviewRequest(BaseModel):
    asset_id: str = Field(..., max_length=100)
    approved: bool
    review_notes: str = Field(default="", max_length=1000)


class AssetAssignmentRequest(BaseModel):
    variant_id: str = Field(..., max_length=100)
    asset_id: str = Field(..., max_length=100)


class AssetUploadUrlRequest(BaseModel):
    asset_id: str = Field(..., max_length=100)
    filename: str = Field(..., min_length=1, max_length=255)


class AssetFinalizeUploadRequest(BaseModel):
    asset_id: str = Field(..., max_length=100)
    storage_key: str = Field(..., min_length=1, max_length=500)
    expected_checksum_sha256: Optional[str] = Field(None, min_length=64, max_length=64)


async def _require_admin(authorization: Optional[str] = Header(None)) -> str:
    from server import require_admin

    return await require_admin(authorization)


def make_asset_admin_router(db: AsyncIOMotorDatabase) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin/configurator", tags=["configurator-admin"])

    @router.get("/assets")
    async def list_assets(_: str = Depends(_require_admin)):
        return await db.configurator_assets.find({}, {"_id": 0}).sort([("variant_id", 1), ("version", -1)]).to_list(500)

    @router.post("/assets/validate")
    async def validate_asset_manifest_endpoint(
        request: AssetManifestValidationRequest,
        _: str = Depends(_require_admin),
    ):
        result = validate_asset_manifest(request.asset, request.mesh_names, request.material_names)
        now = datetime.now(timezone.utc).isoformat()
        update = {
            "validation_passed": result["valid"],
            "updated_at": now,
            "validation_errors": result["errors"],
            "validation_warnings": result["warnings"],
        }
        await db.configurator_assets.update_one({"asset_id": request.asset.asset_id}, {"$set": update})
        return {"asset_id": request.asset.asset_id, **result}

    @router.post("/assets/upload-url")
    async def create_asset_upload_url(
        request: AssetUploadUrlRequest,
        _: str = Depends(_require_admin),
    ):
        asset = await db.configurator_assets.find_one({"asset_id": request.asset_id}, {"_id": 0})
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        if asset.get("format") != "glb":
            raise HTTPException(status_code=422, detail="Production direct upload currently supports GLB assets only")
        if not request.filename.lower().endswith(".glb"):
            raise HTTPException(status_code=422, detail="Uploaded asset must use a .glb filename")

        try:
            config = get_asset_storage_config()
            key = build_asset_storage_key(request.asset_id, asset["version"], request.filename)
            upload_url = await asyncio.to_thread(create_presigned_upload, config, key)
        except AssetStorageConfigError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        now = datetime.now(timezone.utc).isoformat()
        update = {
            "storage_key": key,
            "storage_provider": "s3-compatible",
            "storage_status": "PENDING_UPLOAD",
            "validation_passed": False,
            "published": False,
            "admin_reviewed": False,
            "review_notes": "",
            "updated_at": now,
        }
        public_url = public_asset_url(config, key)
        if public_url:
            update["url"] = public_url
        await db.configurator_assets.update_one({"asset_id": request.asset_id}, {"$set": update})

        return {
            "asset_id": request.asset_id,
            "storage_key": key,
            "upload_url": upload_url,
            "public_url": public_url or asset.get("url"),
            "expires_in": config.upload_ttl_seconds,
            "content_type": "model/gltf-binary",
        }

    @router.post("/assets/finalize-upload")
    async def finalize_asset_upload(
        request: AssetFinalizeUploadRequest,
        _: str = Depends(_require_admin),
    ):
        asset_doc = await db.configurator_assets.find_one({"asset_id": request.asset_id}, {"_id": 0})
        if not asset_doc:
            raise HTTPException(status_code=404, detail="Asset not found")
        if asset_doc.get("storage_key") != request.storage_key:
            raise HTTPException(status_code=422, detail="Storage key does not match the asset upload session")
        if asset_doc.get("format") != "glb":
            raise HTTPException(status_code=422, detail="Production direct upload currently supports GLB assets only")

        try:
            config = get_asset_storage_config()
            metadata = await asyncio.to_thread(head_object, config, request.storage_key)
        except AssetStorageConfigError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=404, detail="Uploaded asset was not found in object storage") from exc

        remote_size = int(metadata.get("ContentLength", 0))
        if remote_size <= 0:
            raise HTTPException(status_code=422, detail="Uploaded asset is empty")
        if remote_size > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Asset exceeds the 200 MB upload limit")

        try:
            with SpooledTemporaryFile(max_size=10 * 1024 * 1024, mode="w+b") as temp:
                downloaded_size = await asyncio.to_thread(download_object, config, request.storage_key, temp)
                if downloaded_size != remote_size:
                    raise ValueError("Stored object size changed during verification")
                temp.seek(0)
                payload = temp.read()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Unable to read uploaded asset from object storage") from exc

        checksum = hashlib.sha256(payload).hexdigest()
        expected = (request.expected_checksum_sha256 or "").lower()
        if expected and checksum != expected:
            raise HTTPException(status_code=422, detail="Uploaded asset checksum does not match expected SHA-256")

        try:
            inspected = inspect_gltf_bytes(payload, filename=request.storage_key.rsplit("/", 1)[-1])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        asset = ConfiguratorAssetCreate.model_validate(asset_doc)
        manifest_result = validate_asset_manifest(
            asset,
            [*inspected["mesh_names"], *inspected["node_names"]],
            inspected["material_names"],
        )
        structure_result = build_verified_asset_metadata(asset, inspected)
        valid = manifest_result["valid"] and structure_result["valid"]
        now = datetime.now(timezone.utc).isoformat()
        public_url = public_asset_url(config, request.storage_key)
        update = {
            "file_size_bytes": downloaded_size,
            "checksum_sha256": checksum,
            "validation_passed": valid,
            "published": False,
            "admin_reviewed": False,
            "review_notes": "",
            "storage_status": "VALIDATED" if valid else "REJECTED",
            "updated_at": now,
            "validation_errors": [*manifest_result["errors"], *structure_result["errors"]],
            "validation_warnings": manifest_result["warnings"],
            "inspected_structure": inspected,
        }
        if public_url:
            update["url"] = public_url
        await db.configurator_assets.update_one({"asset_id": request.asset_id}, {"$set": update})

        return {
            "asset_id": request.asset_id,
            "valid": valid,
            "checksum_sha256": checksum,
            "file_size_bytes": downloaded_size,
            "storage_key": request.storage_key,
            "storage_status": update["storage_status"],
            "public_url": public_url or asset_doc.get("url"),
            "inspection": inspected,
            "manifest": manifest_result,
            "structure": structure_result,
        }

    @router.post("/assets/inspect")
    async def inspect_asset_upload(
        asset_json: str = Form(...),
        asset_file: UploadFile = File(...),
        _: str = Depends(_require_admin),
    ):
        try:
            asset = ConfiguratorAssetCreate.model_validate(json.loads(asset_json))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise HTTPException(status_code=422, detail="asset_json must contain a valid ConfiguratorAssetCreate payload") from exc

        if asset.format != "glb":
            raise HTTPException(status_code=422, detail="Binary inspection currently supports GLB assets only")
        if not (asset_file.filename or "").lower().endswith(".glb"):
            raise HTTPException(status_code=422, detail="Uploaded asset must use a .glb filename")

        payload = await asset_file.read(_MAX_UPLOAD_BYTES + 1)
        if len(payload) > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Asset exceeds the 200 MB upload limit")

        try:
            inspected = inspect_gltf_bytes(payload, filename=asset_file.filename)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        manifest_result = validate_asset_manifest(
            asset,
            [*inspected["mesh_names"], *inspected["node_names"]],
            inspected["material_names"],
        )
        structure_result = build_verified_asset_metadata(asset, inspected)
        valid = manifest_result["valid"] and structure_result["valid"]
        checksum = hashlib.sha256(payload).hexdigest()
        now = datetime.now(timezone.utc).isoformat()

        await db.configurator_assets.update_one(
            {"asset_id": asset.asset_id},
            {
                "$set": {
                    "file_size_bytes": len(payload),
                    "checksum_sha256": checksum,
                    "validation_passed": valid,
                    "published": False,
                    "admin_reviewed": False,
                    "review_notes": "",
                    "updated_at": now,
                    "validation_errors": [*manifest_result["errors"], *structure_result["errors"]],
                    "validation_warnings": manifest_result["warnings"],
                    "inspected_structure": inspected,
                }
            },
            upsert=False,
        )

        return {
            "asset_id": asset.asset_id,
            "valid": valid,
            "checksum_sha256": checksum,
            "file_size_bytes": len(payload),
            "inspection": inspected,
            "manifest": manifest_result,
            "structure": structure_result,
        }

    @router.post("/assets")
    async def upsert_asset(
        asset: ConfiguratorAssetCreate,
        _: str = Depends(_require_admin),
    ):
        variant = await db.variants.find_one(
            {"variant_id": asset.variant_id},
            {"_id": 0, "model_id": 1, "brand_id": 1},
        )
        if not variant:
            raise HTTPException(status_code=404, detail="Variant not found")
        if variant.get("model_id") != asset.model_id or variant.get("brand_id") != asset.brand_id:
            raise HTTPException(status_code=422, detail="Asset model_id/brand_id does not match the variant")

        now = datetime.now(timezone.utc).isoformat()
        existing = await db.configurator_assets.find_one({"asset_id": asset.asset_id}, {"_id": 0})
        document = asset.model_dump(mode="json")
        document["created_at"] = existing.get("created_at", now) if existing else now
        document["updated_at"] = now
        document["published"] = False
        document["validation_passed"] = False
        document["admin_reviewed"] = False
        document["review_notes"] = ""
        for field in ("storage_key", "storage_provider", "storage_status"):
            if existing and existing.get(field) and not document.get(field):
                document[field] = existing[field]

        await db.configurator_assets.replace_one(
            {"asset_id": asset.asset_id},
            document,
            upsert=True,
        )
        return ConfiguratorAsset(**document)

    @router.post("/assets/review")
    async def review_asset(
        request: AssetReviewRequest,
        _: str = Depends(_require_admin),
    ):
        asset_doc = await db.configurator_assets.find_one({"asset_id": request.asset_id}, {"_id": 0})
        if not asset_doc:
            raise HTTPException(status_code=404, detail="Asset not found")
        if request.approved and not asset_doc.get("validation_passed"):
            raise HTTPException(status_code=422, detail="Technical validation must pass before admin approval")

        now = datetime.now(timezone.utc).isoformat()
        update = {
            "admin_reviewed": request.approved,
            "review_notes": request.review_notes,
            "updated_at": now,
        }
        if not request.approved:
            update["published"] = False
        await db.configurator_assets.update_one({"asset_id": request.asset_id}, {"$set": update})
        return {
            "asset_id": request.asset_id,
            "admin_reviewed": request.approved,
            "review_notes": request.review_notes,
            "published": False if not request.approved else bool(asset_doc.get("published")),
        }

    @router.post("/assets/publish")
    async def publish_asset(
        request: AssetPublicationRequest,
        _: str = Depends(_require_admin),
    ):
        asset_doc = await db.configurator_assets.find_one({"asset_id": request.asset_id}, {"_id": 0})
        if not asset_doc:
            raise HTTPException(status_code=404, detail="Asset not found")
        asset = ConfiguratorAsset(**asset_doc)
        if request.publish:
            try:
                from configurator_asset_revision import resolve_authoritative_asset_revision

                resolve_authoritative_asset_revision(
                    asset_doc,
                    asset_doc.get("revisions", []),
                )
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=422,
                    detail="Asset must have an authoritative PUBLISHED active revision before publication",
                ) from exc
            if not asset.is_publishable():
                raise HTTPException(status_code=422, detail="Asset does not satisfy publication gates")
            update = {"published": True, "updated_at": datetime.now(timezone.utc).isoformat(), "storage_status": "PUBLISHED"}
        else:
            update = {"published": False, "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.configurator_assets.update_one({"asset_id": request.asset_id}, {"$set": update})
        return {"asset_id": request.asset_id, "published": request.publish}

    @router.post("/assets/assign")
    async def assign_asset(
        request: AssetAssignmentRequest,
        _: str = Depends(_require_admin),
    ):
        variant = await db.variants.find_one({"variant_id": request.variant_id}, {"_id": 0, "configurator_asset_id": 1})
        if not variant:
            raise HTTPException(status_code=404, detail="Variant not found")
        asset = await db.configurator_assets.find_one({"asset_id": request.asset_id}, {"_id": 0, "variant_id": 1})
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        if asset.get("variant_id") != request.variant_id:
            raise HTTPException(status_code=422, detail="Asset is registered for a different variant")
        await db.variants.update_one({"variant_id": request.variant_id}, {"$set": {"configurator_asset_id": request.asset_id}})
        return {"variant_id": request.variant_id, "configurator_asset_id": request.asset_id}

    @router.delete("/assets/assign/{variant_id}")
    async def unassign_asset(variant_id: str, _: str = Depends(_require_admin)):
        result = await db.variants.update_one({"variant_id": variant_id}, {"$unset": {"configurator_asset_id": ""}})
        if not result.matched_count:
            raise HTTPException(status_code=404, detail="Variant not found")
        return {"variant_id": variant_id, "configurator_asset_id": None}

    @router.post("/assets/inspect-binary")
    async def inspect_binary_asset(
        asset_file: UploadFile = File(...),
        _: str = Depends(_require_admin),
    ):
        payload = await asset_file.read(_MAX_UPLOAD_BYTES + 1)
        if len(payload) > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Asset exceeds the 200 MB upload limit")
        try:
            return inspect_gltf_bytes(payload, filename=asset_file.filename)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router


def mount_asset_admin_routes(app, db):
    app.include_router(make_asset_admin_router(db))
