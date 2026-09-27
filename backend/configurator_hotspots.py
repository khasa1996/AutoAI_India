"""Verified 3D configurator hotspot contracts and API."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field, field_validator


class ConfiguratorHotspot(BaseModel):
    """A UI hotspot anchored to a verified configurator asset."""
    id: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    x: float = Field(..., ge=0, le=100)
    y: float = Field(..., ge=0, le=100)
    camera_preset: Optional[str] = Field(None, max_length=40)
    feature_key: Optional[str] = Field(None, max_length=100)

    @field_validator("id", "label")
    @classmethod
    def non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Hotspot text cannot be blank")
        return value


class HotspotManifestRequest(BaseModel):
    asset_id: str = Field(..., min_length=2, max_length=100)
    hotspots: List[ConfiguratorHotspot] = Field(default_factory=list, max_length=100)


def validate_hotspots(hotspots: List[ConfiguratorHotspot]) -> List[str]:
    """Return validation errors for an asset hotspot collection."""
    ids = [hotspot.id for hotspot in hotspots]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    return ["Duplicate hotspot IDs: " + ", ".join(duplicates)] if duplicates else []


def make_hotspot_router(db: AsyncIOMotorDatabase) -> APIRouter:
    """Build public and admin hotspot routes."""
    router = APIRouter(prefix="/api/v1/configurator", tags=["configurator-hotspots"])

    @router.get("/{variant_id}/hotspots")
    async def get_hotspots(variant_id: str):
        variant = await db.variants.find_one({"variant_id": variant_id}, {"_id": 0, "configurator_asset_id": 1})
        if not variant:
            raise HTTPException(status_code=404, detail="Variant not found")
        asset_id = variant.get("configurator_asset_id")
        if not asset_id:
            return {"variant_id": variant_id, "available": False, "hotspots": []}
        asset = await db.configurator_assets.find_one(
            {"asset_id": asset_id, "variant_id": variant_id, "published": True, "validation_passed": True},
            {"_id": 0, "hotspots": 1},
        )
        if not asset:
            return {"variant_id": variant_id, "available": False, "hotspots": []}
        try:
            from configurator_asset_revision import resolve_authoritative_asset_revision

            resolve_authoritative_asset_revision(asset, asset.get("revisions", []))
        except (TypeError, ValueError):
            return {"variant_id": variant_id, "available": False, "hotspots": []}
        try:
            hotspots = [ConfiguratorHotspot.model_validate(item) for item in asset.get("hotspots", [])]
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Published hotspot metadata is invalid") from exc
        errors = validate_hotspots(hotspots)
        if errors:
            raise HTTPException(status_code=500, detail={"message": "Published hotspot metadata is invalid", "errors": errors})
        return {"variant_id": variant_id, "available": True, "hotspots": [item.model_dump() for item in hotspots]}

    @router.post("/admin/hotspots")
    async def save_hotspots(request: HotspotManifestRequest, authorization: Optional[str] = Header(None)):
        from server import require_admin
        await require_admin(authorization)
        errors = validate_hotspots(request.hotspots)
        if errors:
            raise HTTPException(status_code=422, detail={"message": "Invalid hotspot manifest", "errors": errors})
        asset = await db.configurator_assets.find_one(
            {"asset_id": request.asset_id},
            {"_id": 0, "variant_id": 1, "published": 1, "validation_passed": 1},
        )
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        if asset.get("published") or asset.get("validation_passed"):
            raise HTTPException(status_code=409, detail="Hotspots must be changed before validation/publication; revalidate the asset afterward")
        await db.configurator_assets.update_one(
            {"asset_id": request.asset_id},
            {"$set": {"hotspots": [item.model_dump() for item in request.hotspots]}},
        )
        return {"asset_id": request.asset_id, "hotspots": [item.model_dump() for item in request.hotspots]}

    return router


def mount_hotspot_routes(app, db) -> None:
    """Mount verified configurator hotspot routes."""
    app.include_router(make_hotspot_router(db))
