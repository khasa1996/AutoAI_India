import pytest

from configurator_persistence import revalidate_saved_configuration


@pytest.mark.asyncio
async def test_revalidation_fails_closed_when_authoritative_price_is_missing():
    saved = {
        "configuration": {"purchasable": {"variant_id": "v1"}},
        "city": "Delhi",
        "price_snapshot": 100,
        "asset_id": "asset-1",
        "asset_version": "1",
    }

    async def missing_price(_configuration, _city):
        raise ValueError("authoritative variant pricing is missing")

    async def current_asset(_variant_id, _asset_id):
        return {"asset_id": "asset-1", "version": "1"}

    with pytest.raises(ValueError, match="authoritative variant pricing is missing"):
        await revalidate_saved_configuration(saved, missing_price, current_asset)


@pytest.mark.asyncio
async def test_revalidation_fails_closed_when_price_snapshot_is_not_numeric():
    saved = {
        "configuration": {"purchasable": {"variant_id": "v1"}},
        "price_snapshot": "not-a-price",
        "asset_id": "asset-1",
        "asset_version": "1",
    }

    async def current_price(_configuration, _city):
        return {"estimated_on_road": 100}

    async def current_asset(_variant_id, _asset_id):
        return {"asset_id": "asset-1", "version": "1"}

    with pytest.raises((TypeError, ValueError)):
        await revalidate_saved_configuration(saved, current_price, current_asset)
