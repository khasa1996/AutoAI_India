import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from configurator_routes import make_configurator_router


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return self.rows


class _Collection:
    def __init__(self, rows=None):
        self.rows = rows or []

    async def find_one(self, query, *_args, **_kwargs):
        for row in self.rows:
            if all(row.get(key) == value for key, value in query.items()):
                return row
        return None

    def find(self, query=None, *_args, **_kwargs):
        if not query:
            return _Cursor(self.rows)
        return _Cursor([
            row for row in self.rows
            if all(row.get(key) == value for key, value in query.items())
        ])


class _DB:
    def __init__(self):
        self.variants = _Collection([
            {
                "variant_id": "v1",
                "brand_id": "b1",
                "model_id": "m1",
                "active": True,
                "verification_status": "verified",
                "configurator_status": "AVAILABLE",
                "configurator_asset_id": "asset-1",
            },
        ])
        self.variant_pricing = _Collection([])
        self.variant_colors = _Collection([])
        self.variant_wheels = _Collection([])
        self.variant_interiors = _Collection([])
        self.configurator_assets = _Collection([])


def _app(db):
    app = FastAPI()
    app.include_router(make_configurator_router(db))
    return app


@pytest.mark.asyncio
async def test_availability_does_not_claim_available_without_full_runtime_readiness():
    async with AsyncClient(
        transport=ASGITransport(app=_app(_DB())),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/configurator/v1/availability")

    assert response.status_code == 200
    body = response.json()
    assert body["configurator_status"] == "COMING_SOON"
    assert body["available"] is False
    assert body["asset_id"] is None


@pytest.mark.asyncio
async def test_availability_preserves_explicit_disabled_status_when_not_ready():
    db = _DB()
    db.variants.rows[0]["configurator_status"] = "DISABLED"

    async with AsyncClient(
        transport=ASGITransport(app=_app(db)),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/configurator/v1/availability")

    assert response.status_code == 200
    body = response.json()
    assert body["configurator_status"] == "DISABLED"
    assert body["available"] is False


@pytest.mark.asyncio
async def test_asset_endpoint_does_not_expose_asset_without_full_runtime_readiness():
    db = _DB()
    db.configurator_assets.rows = [{
        "asset_id": "asset-1",
        "variant_id": "v1",
        "active_revision_id": "rev-1",
        "revisions": [{
            "revision_id": "rev-1",
            "asset_id": "asset-1",
            "variant_id": "v1",
            "version": "1.0.0",
            "checksum_sha256": "a" * 64,
            "state": "PUBLISHED",
        }],
        "url": "https://cdn.example.com/car.glb",
        "format": "glb",
        "version": "1.0.0",
        "lod_level": 0,
        "published": True,
        "validation_passed": True,
    }]

    async with AsyncClient(
        transport=ASGITransport(app=_app(db)),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/configurator/v1/asset")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False


@pytest.mark.asyncio
async def test_rules_and_pricing_do_not_use_legacy_cars_for_configurator_identity():
    from pricing_engine import calculate_configuration_price
    from configurator_schemas import ConfigurationPriceRequest, PurchasableConfiguration, ConfigurationValidationRequest
    from rules_engine import validate_configuration

    class LegacyOnlyDB:
        class Legacy:
            async def find_one(self, *args, **kwargs):
                return {"id": "v1", "price_ex_showroom": 1000000}

        cars = Legacy()

        class Missing:
            async def find_one(self, *args, **kwargs):
                return None
            def find(self, *args, **kwargs):
                return _Cursor([])

        variants = Missing()
        variant_pricing = Missing()
        variant_colors = Missing()
        variant_wheels = Missing()
        variant_interiors = Missing()
        configurator_options = Missing()
        configurator_rules = Missing()

    db = LegacyOnlyDB()
    with pytest.raises(ValueError, match="authoritative variant pricing is missing"):
        await calculate_configuration_price(
            ConfigurationPriceRequest(configuration=PurchasableConfiguration(variant_id="v1")),
            db,
        )
    result = await validate_configuration(
        ConfigurationValidationRequest(configuration=PurchasableConfiguration(variant_id="v1")),
        db,
    )
    assert result.valid is False
    assert result.errors == ["Variant 'v1' not found"]
