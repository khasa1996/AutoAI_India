"""Side-effect-free diagnostics for production configurator onboarding."""

from __future__ import annotations

from typing import Optional

from configurator_database_authority import assess_database_authority


def assess_production_configurator_diagnostics(
    configured_database_name: str,
    expected_database_name: Optional[str],
    variant_count: int,
    pricing_count: int,
    asset_count: int,
) -> dict[str, object]:
    """Report database authority and catalog counts without mutating production data."""
    database = assess_database_authority(
        configured_database_name,
        expected_database_name,
    )
    catalog = {
        "variants": max(0, variant_count),
        "verified_pricing": max(0, pricing_count),
        "published_assets": max(0, asset_count),
    }
    return {
        "ready": bool(database["ready"]) and all(value > 0 for value in catalog.values()),
        "database": database,
        "catalog": catalog,
    }
