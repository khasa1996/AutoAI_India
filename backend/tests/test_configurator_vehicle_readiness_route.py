import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from configurator_vehicle_readiness_routes import make_vehicle_readiness_router


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return self.rows


class _Collection:
    def __init__(self, rows=None, one=None):
        self.rows = rows or []
        self.one = one

    async def find_one(self, *_args, **_kwargs):
        return self.one

    def find(self, *_args, **_kwargs):
        return _Cursor(self.rows)


class _DB:
    def __init__(self):
        self.variants = _Collection(one={
            "variant_id": "demo-variant",
            "model_id": "demo-model",
            "brand_id": "demo-brand",
            "active": True,
            "verification_status": "verified",
            "configurator_status": "AVAILABLE",
            "configurator_asset_id": "asset-1",
        })
        self.variant_pricing = _Collection(one={
            "variant_id": "demo-variant",
            "base_ex_showroom": 1000000,
            "source": "verified-source",
            "verification_status": "verified",
        })
        self.variant_colors = _Collection(rows=[{"variant_id": "demo-variant", "available": True}])
        self.variant_wheels = _Collection(rows=[{"variant_id": "demo-variant", "available": True}])
        self.variant_interiors = _Collection(rows=[{"variant_id": "demo-variant", "available": True}])
        self.configurator_assets = _Collection(one={
            "asset_id": "asset-1",
            "variant_id": "demo-variant",
            "version": "1.0.0",
            "published": True,
            "validation_passed": True,
            "provenance": "AUTO_AI_LICENSED",
            "license_name": "Production license",
            "publisher": "Auto AI India",
            "checksum_sha256": "a" * 64,
            "file_size_bytes": 1024,
                "storage_status": "PUBLISHED",
            "active_revision_id": "rev-1",
            "revisions": [{
                "revision_id": "rev-1",
                "asset_id": "asset-1",
                "variant_id": "demo-variant",
                "version": "1.0.0",
                "checksum_sha256": "a" * 64,
                "state": "PUBLISHED",
            }],
            "active_revision_id": "rev-1",
            "revisions": [{
                "revision_id": "rev-1",
                "asset_id": "asset-1",
                "variant_id": "demo-variant",
                "version": "1.0.0",
                "checksum_sha256": "a" * 64,
                "state": "PUBLISHED",
            }],
        })


def _app(db):
    app = FastAPI()
    app.include_router(make_vehicle_readiness_router(db))
    return app


@pytest.mark.asyncio
async def test_vehicle_readiness_route_returns_ready_contract():
    async with AsyncClient(transport=ASGITransport(app=_app(_DB())), base_url="http://test") as client:
        response = await client.get("/api/v1/configurator/variants/demo-variant/readiness")

    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert response.json()["blockers"] == []


@pytest.mark.asyncio
async def test_vehicle_readiness_route_blocks_unverified_pricing():
    db = _DB()
    db.variant_pricing.one["verification_status"] = "unverified"

    async with AsyncClient(transport=ASGITransport(app=_app(db)), base_url="http://test") as client:
        response = await client.get("/api/v1/configurator/variants/demo-variant/readiness")

    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert "variant pricing verification is not complete" in response.json()["blockers"]


@pytest.mark.asyncio
async def test_vehicle_readiness_route_reports_unpublished_asset_reason():
    db = _DB()
    db.configurator_assets.one["published"] = False

    async with AsyncClient(transport=ASGITransport(app=_app(db)), base_url="http://test") as client:
        response = await client.get("/api/v1/configurator/variants/demo-variant/readiness")

    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert "configurator asset is not published" in response.json()["blockers"]


@pytest.mark.asyncio
async def test_vehicle_readiness_route_returns_404_for_unknown_variant():
    db = _DB()
    db.variants.one = None

    async with AsyncClient(transport=ASGITransport(app=_app(db)), base_url="http://test") as client:
        response = await client.get("/api/v1/configurator/variants/missing/readiness")

    assert response.status_code == 404
    assert response.json()["detail"] == "Vehicle variant not found"
