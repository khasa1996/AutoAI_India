"""Side-effect-free audit for the authoritative configurator catalog."""

from __future__ import annotations

from typing import Any, Dict


CATALOG_COLLECTIONS = (
    "brands",
    "models",
    "variants",
    "variant_pricing",
    "variant_colors",
    "variant_wheels",
    "variant_interiors",
    "configurator_assets",
    "configurator_rules",
)


async def audit_configurator_catalog(db) -> Dict[str, Any]:
    """Audit catalog completeness without inserting, updating, or deleting data."""
    counts: dict[str, int] = {}
    for name in CATALOG_COLLECTIONS:
        counts[name] = await db[name].count_documents({})

    verified_variants = await db.variants.count_documents(
        {
            "active": True,
            "verification_status": "verified",
            "configurator_status": "AVAILABLE",
        }
    )

    missing_pricing = await db.variants.count_documents(
        {
            "active": True,
            "verification_status": "verified",
            "configurator_status": "AVAILABLE",
            "variant_id": {"$nin": await db.variant_pricing.distinct("variant_id")},
        }
    )

    published_assets = await db.configurator_assets.count_documents(
        {
            "published": True,
            "validation_passed": True,
        }
    )

    return {
        "database": db.name,
        "catalog_collections": counts,
        "verified_available_variants": verified_variants,
        "verified_available_variants_missing_pricing": missing_pricing,
        "published_validated_assets": published_assets,
        "production_data_write": False,
    }


def catalog_has_publishable_variants(audit: Dict[str, Any]) -> bool:
    """Return whether the audit has at least one verified, priced production variant."""
    return (
        audit["verified_available_variants"] > 0
        and audit["verified_available_variants_missing_pricing"] == 0
    )
