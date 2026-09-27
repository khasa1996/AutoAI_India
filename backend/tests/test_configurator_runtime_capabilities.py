import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from configurator_runtime_capabilities_routes import make_runtime_capabilities_router


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return self.rows


class _Collection:
    def __init__(self, rows=None, one=None):
        self.rows = rows or []
        self.one = one

    async def to_list(self, _limit):
        return self.rows

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
        self.variant_colors = _Collection(rows=[
            {"color_id": "paint-red", "variant_id": "demo-variant", "available": True, "name": "Red"},
        ])
        self.variant_wheels = _Collection(rows=[
            {"wheel_id": "wheel-a", "variant_id": "demo-variant", "available": True, "name": "18-inch"},
        ])
        self.variant_interiors = _Collection(rows=[
            {"interior_id": "interior-black", "variant_id": "demo-variant", "available": True, "name": "Black"},
        ])
        self.configurator_options = _Collection(rows=[
            {"option_id": "roof-black", "option_type": "roof", "variant_id": "demo-variant", "available": True, "name": "Black Roof"},
            {"option_id": "accessory-1", "option_type": "accessory", "variant_id": "demo-variant", "available": True, "name": "Accessory"},
        ])
        self.configurator_assets = _Collection(one={
            "asset_id": "asset-1",
            "variant_id": "demo-variant",
            "active_revision_id": "rev-1",
            "revisions": [
                {
                    "revision_id": "rev-1",
                    "asset_id": "asset-1",
                    "variant_id": "demo-variant",
                    "version": "1.0.0",
                    "checksum_sha256": "a" * 64,
                    "state": "PUBLISHED",
                }
            ],
            "version": "1.0.0",
            "published": True,
            "validation_passed": True,
            "provenance": "AUTO_AI_LICENSED",
            "license_name": "Production license",
            "publisher": "Auto AI India",
            "checksum_sha256": "a" * 64,
            "file_size_bytes": 1024,
            "storage_status": "PUBLISHED",
            "cdn_url": "https://cdn.example/vehicle.glb",
            "format": "glb",
            "lod_level": 0,
            "supported_interactions": ["doors", "sunroof", "camera_exterior"],
            "paint_material_names": ["BodyPaint"],
            "interior_material_names": ["InteriorTrim"],
            "interior_material_mappings": {"interior-black": ["InteriorTrim"]},
            "wheel_mesh_names": {"wheel-a": "WheelMesh"},
            "option_mesh_names": {"roof-black": ["RoofMesh"]},
            "camera_preset_names": ["front", "interior"],
            "interaction_animation_names": {
                "doors": {"open": "DoorsOpen", "close": "DoorsClose"},
                "sunroof": {"open": "SunroofOpen", "close": "SunroofClose"},
            },
        })


def _app(db):
    app = FastAPI()
    app.include_router(make_runtime_capabilities_router(db))
    return app


@pytest.mark.asyncio
async def test_runtime_capabilities_returns_only_published_verified_runtime_contract():
    async with AsyncClient(transport=ASGITransport(app=_app(_DB())), base_url="http://test") as client:
        response = await client.get("/api/v1/configurator/demo-variant/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["variant_id"] == "demo-variant"
    assert payload["ready"] is True
    assert payload["asset"]["asset_id"] == "asset-1"
    assert payload["asset"]["revision_id"] == "rev-1"
    assert payload["asset"]["version"] == "1.0.0"
    assert payload["asset"]["checksum_sha256"] == "a" * 64
    assert payload["asset"]["url"] == "https://cdn.example/vehicle.glb"
    assert payload["capabilities"]["interactions"] == ["doors", "sunroof", "camera_exterior"]
    assert payload["capabilities"]["cameras"] == ["front", "interior"]
    assert payload["capabilities"]["animations"]["doors"]["open"] == "DoorsOpen"
    assert payload["options"]["colors"][0]["color_id"] == "paint-red"
    assert payload["options"]["wheels"][0]["wheel_id"] == "wheel-a"
    assert payload["options"]["interiors"][0]["interior_id"] == "interior-black"
    assert payload["options"]["roofs"][0]["option_id"] == "roof-black"
    assert payload["options"]["accessories"][0]["option_id"] == "accessory-1"


@pytest.mark.asyncio
async def test_runtime_capabilities_blocks_unready_variant_without_exposing_runtime_asset():
    db = _DB()
    db.configurator_assets.one["storage_status"] = "STAGED"

    async with AsyncClient(transport=ASGITransport(app=_app(db)), base_url="http://test") as client:
        response = await client.get("/api/v1/configurator/demo-variant/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["asset"] is None
    assert "configurator asset storage publication state is not complete" in payload["blockers"]


@pytest.mark.asyncio
async def test_runtime_capabilities_returns_404_for_unknown_variant():
    db = _DB()
    db.variants.one = None

    async with AsyncClient(transport=ASGITransport(app=_app(db)), base_url="http://test") as client:
        response = await client.get("/api/v1/configurator/missing/capabilities")

    assert response.status_code == 404
    assert response.json()["detail"] == "Vehicle variant not found"



@pytest.mark.asyncio
async def test_runtime_capabilities_reports_active_revision_blocker() -> None:
    db = _DB()
    db.configurator_assets.one["active_revision_id"] = "missing-revision"

    async with AsyncClient(transport=ASGITransport(app=_app(db)), base_url="http://test") as client:
        response = await client.get("/api/v1/configurator/demo-variant/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert "configurator asset active revision is not published or is invalid" in payload["blockers"]
