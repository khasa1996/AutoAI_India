"""AI configurator production-readiness gate."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from configurator_vehicle_readiness import assess_vehicle_configurator_readiness


async def require_ai_configurator_readiness(
    variant_id: str,
    db: Any,
    colors: Iterable[Dict[str, Any]],
    wheels: Iterable[Dict[str, Any]],
    interiors: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    """Require a verified, active, AVAILABLE variant with authoritative runtime inputs."""
    vehicle = await db.variants.find_one({"variant_id": variant_id}, {"_id": 0})
    if vehicle is None:
        raise ValueError(f"Variant not found: {variant_id}")

    pricing = await db.variant_pricing.find_one(
        {"variant_id": variant_id}, {"_id": 0}
    )
    asset_id = vehicle.get("configurator_asset_id")
    asset: Optional[Dict[str, Any]] = None
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

    readiness = assess_vehicle_configurator_readiness(
        vehicle,
        pricing,
        colors,
        wheels,
        interiors,
        asset,
    )
    if not readiness["ready"]:
        raise ValueError("; ".join(readiness["blockers"]))

    return {
        "vehicle": vehicle,
        "pricing": pricing,
        "asset": asset,
        "readiness": readiness,
    }
