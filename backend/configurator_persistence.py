"""Persistence freshness checks for saved configurator snapshots."""

from __future__ import annotations

from typing import Awaitable, Callable, Dict, Optional, Tuple


async def revalidate_saved_configuration(
    saved_document: Dict[str, object],
    current_price_resolver: Callable[[Dict[str, object], Optional[str]], Awaitable[Dict[str, object]]],
    current_asset_resolver: Callable[[str, Optional[str]], Awaitable[Optional[Dict[str, object]]]],
) -> Dict[str, object]:
    """Refresh authoritative price/asset context while preserving the saved configuration."""
    configuration = saved_document.get("configuration")
    if not isinstance(configuration, dict):
        raise ValueError("Saved configuration is invalid")

    purchasable = configuration.get("purchasable")
    if not isinstance(purchasable, dict):
        raise ValueError("Saved purchasable configuration is invalid")

    city_value = saved_document.get("city")
    city = city_value if isinstance(city_value, str) else None
    current_price = await current_price_resolver(purchasable, city)

    variant_value = purchasable.get("variant_id")
    variant_id = variant_value if isinstance(variant_value, str) else ""
    asset_id_value = saved_document.get("asset_id")
    asset_id = asset_id_value if isinstance(asset_id_value, str) else None
    current_asset = await current_asset_resolver(variant_id, asset_id)

    stale, stale_reason = assess_saved_configuration_freshness(
        saved_document,
        current_price,
        current_asset,
    )

    refreshed = dict(saved_document)
    refreshed["price_snapshot"] = int(current_price.get("estimated_on_road", 0))
    refreshed["price_breakdown"] = current_price
    refreshed["stale"] = stale
    refreshed["stale_reason"] = stale_reason
    if current_asset is not None:
        refreshed["asset_id"] = current_asset.get("asset_id")
        refreshed["asset_version"] = current_asset.get("version")
        refreshed["asset_revision_id"] = current_asset.get("revision_id")

    return refreshed


def assess_saved_configuration_freshness(
    saved_document: Dict[str, object],
    current_price_snapshot: Dict[str, object],
    current_asset: Optional[Dict[str, object]],
) -> Tuple[bool, Optional[str]]:
    """Compare persisted authoritative context with the current verified context."""
    if int(saved_document.get("price_snapshot", 0)) != int(current_price_snapshot.get("estimated_on_road", 0)):
        return True, "Authoritative configurator price has changed"
    if current_asset is None:
        return True, "Published verified configurator asset is unavailable"
    if (
        saved_document.get("asset_id") != current_asset.get("asset_id")
        or saved_document.get("asset_version") != current_asset.get("version")
    ):
        return True, "Published verified configurator asset has changed"
    if saved_document.get("asset_revision_id") != current_asset.get("revision_id"):
        return True, "Published verified configurator asset revision has changed"
    return False, None
