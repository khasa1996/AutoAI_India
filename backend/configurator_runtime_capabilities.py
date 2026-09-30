"""Authoritative runtime capability contract for the production 3D configurator."""

from __future__ import annotations

from typing import Any, Dict, Optional

from configurator_vehicle_readiness import assess_vehicle_configurator_readiness
from rules_engine import get_available_options_for_variant


def _asset_runtime_contract(
    asset: Dict[str, Any],
    revision: Dict[str, Any],
) -> Dict[str, Any]:
    """Expose immutable published manifest data required by the runtime."""
    return {
        "asset_id": revision["asset_id"],
        "version": revision["version"],
        "active_revision_id": revision["revision_id"],
        "url": revision.get("cdn_url") or revision["url"],
        "format": revision["format"],
        "lod_level": revision["lod_level"],
        "provenance": revision["provenance"],
        "license_name": revision["license_name"],
        "publisher": revision["publisher"],
        "checksum_sha256": revision["checksum_sha256"],
        "file_size_bytes": revision["file_size_bytes"],
    }


def _capability_contract(revision: Dict[str, Any]) -> Dict[str, Any]:
    """Translate the immutable published manifest into frontend capabilities."""
    return {
        "interactions": list(revision.get("supported_interactions", [])),
        "cameras": list(revision.get("camera_preset_names", [])),
        "animations": dict(revision.get("interaction_animation_names", {})),
        "paint_materials": list(revision.get("paint_material_names", [])),
        "interior_materials": list(revision.get("interior_material_names", [])),
        "interior_material_mappings": dict(
            revision.get("interior_material_mappings", {})
        ),
        "wheel_mesh_mappings": dict(revision.get("wheel_mesh_names", {})),
        "option_mesh_mappings": dict(revision.get("option_mesh_names", {})),
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
    """Build a deterministic runtime contract from authoritative backend records."""
    vehicle: Optional[Dict[str, Any]] = await db.variants.find_one(
        {"variant_id": variant_id}, {"_id": 0}
    )
    if not vehicle:
        raise LookupError("Vehicle variant not found")

    pricing = await db.variant_pricing.find_one(
        {"variant_id": variant_id}, {"_id": 0}
    )
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
        "asset": _asset_runtime_contract(asset, active_revision),
        "capabilities": _capability_contract(active_revision),
        "options": options,
    }
