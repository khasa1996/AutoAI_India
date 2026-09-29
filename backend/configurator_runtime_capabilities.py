"""Authoritative runtime capability contract for the production 3D configurator."""

from __future__ import annotations

from typing import Any, Dict, Optional

from configurator_vehicle_readiness import assess_vehicle_configurator_readiness
from rules_engine import get_available_options_for_variant


def _asset_runtime_contract(asset: Dict[str, Any]) -> Dict[str, Any]:
    """Expose only verified manifest data required by the runtime."""
    return {
        "asset_id": asset["asset_id"],
        "version": asset["version"],
        "active_revision_id": asset["active_revision_id"],
        "url": asset.get("cdn_url") or asset["url"],
        "format": asset["format"],
        "lod_level": asset["lod_level"],
        "provenance": asset["provenance"],
        "license_name": asset["license_name"],
        "publisher": asset["publisher"],
        "checksum_sha256": asset["checksum_sha256"],
        "file_size_bytes": asset["file_size_bytes"],
    }


def _capability_contract(asset: Dict[str, Any]) -> Dict[str, Any]:
    """Translate the validated manifest into frontend runtime capabilities."""
    return {
        "interactions": list(asset.get("supported_interactions", [])),
        "cameras": list(asset.get("camera_preset_names", [])),
        "animations": dict(asset.get("interaction_animation_names", {})),
        "paint_materials": list(asset.get("paint_material_names", [])),
        "interior_materials": list(asset.get("interior_material_names", [])),
        "interior_material_mappings": dict(asset.get("interior_material_mappings", {})),
        "wheel_mesh_mappings": dict(asset.get("wheel_mesh_names", {})),
        "option_mesh_mappings": dict(asset.get("option_mesh_names", {})),
    }


async def _resolve_active_published_revision(
    db: Any,
    asset: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Resolve the exact published revision selected by the asset runtime pointer."""
    revision_id = asset.get("active_revision_id")
    if not revision_id:
        return None

    return await db.configurator_asset_versions.find_one(
        {
            "asset_id": asset.get("asset_id"),
            "variant_id": asset.get("variant_id"),
            "revision_id": revision_id,
            "version": asset.get("version"),
            "checksum_sha256": asset.get("checksum_sha256"),
            "file_size_bytes": asset.get("file_size_bytes"),
            "storage_key": asset.get("storage_key"),
            "published": True,
            "validation_passed": True,
            "admin_reviewed": True,
            "storage_status": "PUBLISHED",
        },
        {"_id": 0},
    )


async def build_runtime_capability_contract(
    db: Any,
    variant_id: str,
) -> Dict[str, Any]:
    """Build a deterministic runtime contract from the authoritative backend records."""
    vehicle: Optional[Dict[str, Any]] = await db.variants.find_one(
        {"variant_id": variant_id}, {"_id": 0}
    )
    if not vehicle:
        raise LookupError("Vehicle variant not found")

    pricing = await db.variant_pricing.find_one({"variant_id": variant_id}, {"_id": 0})
    colors = await db.variant_colors.find(
        {"variant_id": variant_id}, {"_id": 0}
    ).to_list(100)
    wheels = await db.variant_wheels.find(
        {"variant_id": variant_id}, {"_id": 0}
    ).to_list(100)
    interiors = await db.variant_interiors.find(
        {"variant_id": variant_id}, {"_id": 0}
    ).to_list(100)

    asset = None
    active_revision = None
    asset_id = vehicle.get("configurator_asset_id")
    if asset_id:
        asset = await db.configurator_assets.find_one(
            {
                "asset_id": asset_id,
                "variant_id": variant_id,
                "published": True,
                "validation_passed": True,
            },
            {"_id": 0},
        )
        if asset is not None:
            active_revision = await _resolve_active_published_revision(db, asset)

    readiness = assess_vehicle_configurator_readiness(
        vehicle,
        pricing,
        colors,
        wheels,
        interiors,
        asset,
    )

    if asset is not None and active_revision is None:
        readiness["blockers"].append(
            "active configurator asset revision is missing or invalid"
        )
        readiness["ready"] = False

    if not readiness["ready"] or asset is None:
        return {
            "variant_id": variant_id,
            "ready": False,
            "blockers": readiness["blockers"],
            "warnings": readiness["warnings"],
            "asset": None,
            "capabilities": None,
            "options": None,
        }

    options = await get_available_options_for_variant(variant_id, db)
    return {
        "variant_id": variant_id,
        "ready": True,
        "blockers": [],
        "warnings": readiness["warnings"],
        "asset": _asset_runtime_contract(asset),
        "capabilities": _capability_contract(asset),
        "options": options,
    }
