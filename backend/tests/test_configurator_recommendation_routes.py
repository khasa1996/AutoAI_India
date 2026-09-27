import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from configurator_recommendation_routes import make_configurator_recommendation_router


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
            if all(row.get(key) == value for key, value in query.items() if key not in {"published", "validation_passed"}):
                if "published" in query and row.get("published") is not query["published"]:
                    continue
                if "validation_passed" in query and row.get("validation_passed") is not query["validation_passed"]:
                    continue
                return row
        return None

    def find(self, *_args, **_kwargs):
        return _Cursor(self.rows)


class _DB:
    def __init__(self):
        self.variants = _Collection([
            {"variant_id": "v1", "brand_id": "b1", "model_id": "m1", "name": "Diesel SUV", "market_segment": "SUV", "specs": {"fuel_type": "Diesel"}, "active": True, "configurator_status": "AVAILABLE", "configurator_asset_id": "asset-1", "verification_status": "verified"},
            {"variant_id": "v2", "brand_id": "b2", "model_id": "m2", "name": "Petrol SUV", "market_segment": "SUV", "specs": {"fuel_type": "Petrol"}, "active": True, "configurator_status": "COMING_SOON"},
        ])
        self.variant_pricing = _Collection([
            {"variant_id": "v1", "base_ex_showroom": 1200000, "verification_status": "verified", "city_pricing": [
                {"city": "Delhi", "state": "Delhi", "ex_showroom": 1250000, "verification_status": "verified"},
                {"city": "Panipat", "state": "Haryana", "ex_showroom": 1300000, "verification_status": "verified"},
            ]},
            {"variant_id": "v2", "base_ex_showroom": 1000000, "verification_status": "verified", "city_pricing": [
                {"city": "Panipat", "state": "Haryana", "ex_showroom": 1100000, "verification_status": "verified"},
            ]},
        ])
        self.variant_colors = _Collection([{"variant_id": "v1", "color_id": "black", "available": True}])
        self.variant_wheels = _Collection([{"variant_id": "v1", "wheel_id": "alloy", "available": True}])
        self.variant_interiors = _Collection([{"variant_id": "v1", "interior_id": "black", "available": True}])
        self.configurator_options = _Collection([])
        self.configurator_assets = _Collection([
            {
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
                "version": "1.0.0",
                "url": "https://cdn.example/vehicle.glb",
                "format": "glb",
                "lod_level": 0,
                "published": True,
                "validation_passed": True,
                "provenance": "AUTO_AI_LICENSED",
                "license_name": "Licensed",
                "publisher": "Auto AI India",
                "checksum_sha256": "a" * 64,
                "file_size_bytes": 1024,
                "storage_status": "PUBLISHED",
            },
        ])


def _app(db):
    app = FastAPI()
    app.include_router(make_configurator_recommendation_router(db))
    return app


@pytest.mark.asyncio
async def test_recommendations_return_bounded_backend_candidates_and_readiness():
    async with AsyncClient(transport=ASGITransport(app=_app(_DB())), base_url="http://test") as client:
        response = await client.post("/api/v1/configurator/recommendations", json={"raw_request": "I need a diesel SUV under ₹15 lakh", "limit": 5})

    assert response.status_code == 200
    body = response.json()
    assert len(body["recommendations"]) == 1
    assert body["recommendations"][0]["variant_id"] == "v1"
    assert body["recommendations"][0]["configurator_available"] is True
    assert body["recommendations"][0]["pricing"]["base_ex_showroom"] == 1200000
    assert body["ai_assisted"] is False


@pytest.mark.asyncio
async def test_recommendations_use_verified_city_price_for_budget_filtering():
    async with AsyncClient(transport=ASGITransport(app=_app(_DB())), base_url="http://test") as client:
        response = await client.post("/api/v1/configurator/recommendations", json={
            "raw_request": "SUV under ₹12 lakh in Panipat",
            "city": "Panipat",
            "state": "Haryana",
            "limit": 5,
        })

    assert response.status_code == 200
    result = {item["variant_id"]: item for item in response.json()["recommendations"]}
    assert "v1" not in result
    assert result["v2"]["pricing"]["ex_showroom"] == 1100000


@pytest.mark.asyncio
async def test_recommendations_do_not_use_unverified_city_price():
    db = _DB()
    db.variant_pricing.rows[0]["city_pricing"][1]["verification_status"] = "unverified"

    async with AsyncClient(transport=ASGITransport(app=_app(db)), base_url="http://test") as client:
        response = await client.post("/api/v1/configurator/recommendations", json={
            "raw_request": "diesel SUV under ₹15 lakh in Panipat",
            "city": "Panipat",
            "state": "Haryana",
            "limit": 5,
        })

    assert response.status_code == 200
    result = {item["variant_id"]: item for item in response.json()["recommendations"]}
    assert "v1" not in result


@pytest.mark.asyncio
async def test_recommendations_never_claim_configurator_ready_for_coming_soon_variant():
    db = _DB()
    db.variants.rows[0]["configurator_status"] = "COMING_SOON"
    db.variants.rows[0].pop("configurator_asset_id", None)

    async with AsyncClient(transport=ASGITransport(app=_app(db)), base_url="http://test") as client:
        response = await client.post("/api/v1/configurator/recommendations", json={"raw_request": "SUV under ₹15 lakh", "limit": 5})

    assert response.status_code == 200
    result = {item["variant_id"]: item for item in response.json()["recommendations"]}
    assert result["v1"]["configurator_available"] is False
    assert result["v1"]["availability_status"] == "COMING_SOON"


@pytest.mark.asyncio
async def test_recommendations_explanation_reports_deterministic_fallback_when_ai_is_unavailable(monkeypatch):
    async def fallback_intent(_raw_request, _candidates):
        return {
            "preferred_segment": "suv",
            "preferred_fuel": "diesel",
            "max_budget": 1500000,
            "required_features": [],
            "ai_assisted": False,
        }

    monkeypatch.setattr("configurator_recommendation_routes.extract_recommendation_intent", fallback_intent)

    async with AsyncClient(transport=ASGITransport(app=_app(_DB())), base_url="http://test") as client:
        response = await client.post("/api/v1/configurator/recommendations", json={"raw_request": "diesel SUV under ₹15 lakh", "limit": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["ai_assisted"] is False
    assert "deterministically extracted" in body["explanation"]
    assert "AI extracted" not in body["explanation"]


@pytest.mark.asyncio
async def test_recommendations_explanation_identifies_ai_assisted_intent_extraction(monkeypatch):
    async def ai_intent(_raw_request, _candidates):
        return {
            "preferred_segment": "suv",
            "preferred_fuel": "diesel",
            "max_budget": 1500000,
            "required_features": [],
            "ai_assisted": True,
        }

    monkeypatch.setattr("configurator_recommendation_routes.extract_recommendation_intent", ai_intent)

    async with AsyncClient(transport=ASGITransport(app=_app(_DB())), base_url="http://test") as client:
        response = await client.post("/api/v1/configurator/recommendations", json={"raw_request": "diesel SUV under ₹15 lakh", "limit": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["ai_assisted"] is True
    assert "AI extracted" in body["explanation"]