"""Immutable configurator asset revisions and safe rollback APIs."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field


class AssetRollbackRequest(BaseModel):
    revision_id: str = Field(..., min_length=8, max_length=100)


async def _require_admin(authorization: Optional[str] = Header(None)) -> str:
    from server import require_admin

    return await require_admin(authorization)


def snapshot_asset(asset: dict, *, revision_id: str, snapshot_type: str, created_at: str) -> dict:
    """Create an immutable revision document without Mongo's internal id."""
    snapshot = deepcopy({key: value for key, value in asset.items() if key != "_id"})
    snapshot["revision_id"] = revision_id
    snapshot["snapshot_type"] = snapshot_type
    snapshot["revision_created_at"] = created_at
    return snapshot


async def snapshot_before_upload(db: AsyncIOMotorDatabase, asset: dict) -> Optional[str]:
    """Snapshot the currently verified binary before a new upload replaces it."""
    if not asset.get("storage_key") or not asset.get("checksum_sha256") or not asset.get("validation_passed"):
        return None

    now = datetime.now(timezone.utc).isoformat()
    revision_id = f"rev-{uuid4().hex}"
    await db.configurator_asset_versions.insert_one(
        snapshot_asset(
            asset,
            revision_id=revision_id,
            snapshot_type="UPLOAD_SOURCE",
            created_at=now,
        )
    )
    return revision_id


async def create_publication_revision(db: AsyncIOMotorDatabase, asset: dict) -> str:
    """Create the immutable revision that becomes the runtime publication authority."""
    now = datetime.now(timezone.utc).isoformat()
    revision_id = f"rev-{uuid4().hex}"
    revision = snapshot_asset(
        asset,
        revision_id=revision_id,
        snapshot_type="PUBLICATION",
        created_at=now,
    )
    revision["published"] = True
    revision["storage_status"] = "PUBLISHED"
    revision["active_revision_id"] = revision_id
    await db.configurator_asset_versions.insert_one(revision)
    return revision_id


def _public_revision(revision: dict) -> dict:
    """Return revision metadata without duplicating the large inspection payload."""
    return {
        "revision_id": revision.get("revision_id"),
        "asset_id": revision.get("asset_id"),
        "variant_id": revision.get("variant_id"),
        "version": revision.get("version"),
        "storage_key": revision.get("storage_key"),
        "checksum_sha256": revision.get("checksum_sha256"),
        "file_size_bytes": revision.get("file_size_bytes"),
        "validation_passed": bool(revision.get("validation_passed")),
        "admin_reviewed": bool(revision.get("admin_reviewed")),
        "published": bool(revision.get("published")),
        "storage_status": revision.get("storage_status"),
        "review_notes": revision.get("review_notes"),
        "snapshot_type": revision.get("snapshot_type"),
        "revision_created_at": revision.get("revision_created_at"),
    }


def make_asset_version_router(db: AsyncIOMotorDatabase) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin/configurator", tags=["configurator-asset-versioning"])

    @router.post("/assets/{asset_id}/prepare-version")
    async def prepare_asset_version(asset_id: str, _: str = Depends(_require_admin)):
        current = await db.configurator_assets.find_one({"asset_id": asset_id}, {"_id": 0})
        if not current:
            raise HTTPException(status_code=404, detail="Asset not found")
        revision_id = await snapshot_before_upload(db, current)
        return {"asset_id": asset_id, "revision_id": revision_id, "snapshotted": revision_id is not None}

    @router.get("/assets/{asset_id}/versions")
    async def list_asset_versions(asset_id: str, _: str = Depends(_require_admin)):
        revisions = await db.configurator_asset_versions.find(
            {"asset_id": asset_id},
            {"_id": 0},
        ).sort([("revision_created_at", -1)]).to_list(200)
        return {
            "asset_id": asset_id,
            "versions": [_public_revision(revision) for revision in revisions],
        }

    @router.post("/assets/{asset_id}/rollback")
    async def rollback_asset(
        asset_id: str,
        request: AssetRollbackRequest,
        _: str = Depends(_require_admin),
    ):
        current = await db.configurator_assets.find_one({"asset_id": asset_id}, {"_id": 0})
        if not current:
            raise HTTPException(status_code=404, detail="Asset not found")

        revision = await db.configurator_asset_versions.find_one(
            {
                "asset_id": asset_id,
                "revision_id": request.revision_id,
                "validation_passed": True,
                "admin_reviewed": True,
                "published": True,
                "storage_status": "PUBLISHED",
            },
            {"_id": 0},
        )
        if not revision:
            raise HTTPException(
                status_code=422,
                detail="Rollback target must be a technically validated and admin-reviewed revision",
            )

        if not revision.get("storage_key") or not revision.get("checksum_sha256"):
            raise HTTPException(status_code=422, detail="Rollback target does not contain a verified stored asset")

        now = datetime.now(timezone.utc).isoformat()
        source_revision = snapshot_asset(
            current,
            revision_id=f"rev-{uuid4().hex}",
            snapshot_type="ROLLBACK_SOURCE",
            created_at=now,
        )
        await db.configurator_asset_versions.insert_one(source_revision)

        restored = deepcopy({key: value for key, value in revision.items() if key not in {"revision_id", "snapshot_type", "revision_created_at"}})
        restored["asset_id"] = asset_id
        restored["created_at"] = current.get("created_at", now)
        restored["updated_at"] = now
        restored["active_revision_id"] = request.revision_id
        restored["published"] = bool(revision.get("published"))
        restored["storage_status"] = "PUBLISHED" if restored["published"] else "VALIDATED"

        await db.configurator_assets.replace_one({"asset_id": asset_id}, restored, upsert=False)
        return {
            "asset_id": asset_id,
            "active_revision_id": request.revision_id,
            "version": restored.get("version"),
            "storage_key": restored.get("storage_key"),
            "published": restored["published"],
            "rolled_back_at": now,
        }

    return router


def mount_asset_version_routes(app, db):
    """Mount immutable asset version history and rollback endpoints."""
    app.include_router(make_asset_version_router(db))
