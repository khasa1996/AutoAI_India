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

    async def find_one(self, query=None, *_args, **_kwargs):
        if query is None:
            return self.one
        for row in self.rows:
            if all(row.get(key) == value for key, value in query.items()):
                return row
        if self.one is not None and all(self.one.get(key) == value for key, value in query.items()):
            return self.one
        return None

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
            "version": "1.0.0",
            "active_revision_id": "rev-1",
            "published": True,
            "validation_passed": True,
            "provenance": "AUTO_AI_LICENSED",
            "license_name": "Production license",
            "publisher": "Auto AI India",
            "provenance_evidence": [{
                "evidence_id": "evidence-001",
                "evidence_type": "LICENSE_RECORD",
                "status": "VERIFIED",
                "reference": "LICENSE-001",
                "verified_by": "admin@example.invalid",
                "verified_at": "2026-09-29T00:00:00Z",
            }],
            "checksum_sha256": "a" * 64,
            "file_size_bytes": 1024,
            "storage_key": "configurator/asset-1/v1.0.0/vehicle.glb",
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
        self.configurator_asset_versions = _Collection(rows=[{
            "asset_id": "asset-1",
            "revision_id": "rev-1",
            "variant_id": "demo-variant",
            "version": "1.0.0",
            "published": True,
            "validation_passed": True,
            "admin_reviewed": True,
            "storage_status": "PUBLISHED",
            "checksum_sha256": "a" * 64,
            "file_size_bytes": 1024,
            "storage_key": "configurator/asset-1/v1.0.0/vehicle.glb",
            "cdn_url": "https://immutable.example/vehicle.glb",
            "format": "glb",
            "lod_level": 1,
            "provenance": "IMMUTABLE_REVISION_LICENSE",
            "license_name": "Immutable production license",
            "publisher": "Verified Asset Publisher",
            "supported_interactions": ["doors"],
            "camera_preset_names": ["immutable-front"],
            "interaction_animation_names": {"doors": {"open": "ImmutableDoorsOpen"}},
            "paint_material_names": ["ImmutableBodyPaint"],
            "interior_material_names": ["ImmutableInteriorTrim"],
            "interior_material_mappings": {"interior-black": ["ImmutableInteriorTrim"]},
            "wheel_mesh_names": {"wheel-a": "ImmutableWheelMesh"},
            "option_mesh_names": {"roof-black": ["ImmutableRoofMesh"]},
        }])


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
    assert payload["asset"]["version"] == "1.0.0"
    assert payload["asset"]["url"] == "https://immutable.example/vehicle.glb"
    assert payload["asset"]["active_revision_id"] == "rev-1"
    assert payload["asset"]["checksum_sha256"] == "a" * 64
    assert payload["asset"]["file_size_bytes"] == 1024
    assert payload["capabilities"]["interactions"] == ["doors"]
    assert payload["capabilities"]["cameras"] == ["immutable-front"]
    assert payload["capabilities"]["animations"]["doors"]["open"] == "ImmutableDoorsOpen"
    assert payload["options"]["colors"][0]["color_id"] == "paint-red"
    assert payload["options"]["wheels"][0]["wheel_id"] == "wheel-a"
    assert payload["options"]["interiors"][0]["interior_id"] == "interior-black"
    assert payload["options"]["roofs"][0]["option_id"] == "roof-black"
    assert payload["options"]["accessories"][0]["option_id"] == "accessory-1"


@pytest.mark.asyncio
async def test_runtime_capabilities_ignores_mutable_asset_manifest_drift_after_revision_validation():
    db = _DB()
    db.configurator_assets.one["cdn_url"] = "https://mutable.example/vehicle.glb"
    db.configurator_assets.one["supported_interactions"] = ["tampered-interaction"]
    db.configurator_assets.one["camera_preset_names"] = ["tampered-camera"]

    async with AsyncClient(transport=ASGITransport(app=_app(db)), base_url="http://test") as client:
        response = await client.get("/api/v1/configurator/demo-variant/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["asset"]["url"] == "https://immutable.example/vehicle.glb"
    assert payload["capabilities"]["interactions"] == ["doors"]
    assert payload["capabilities"]["cameras"] == ["immutable-front"]


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
async def test_runtime_capabilities_requires_matching_active_revision():
    db = _DB()
    db.configurator_asset_versions.rows = []

    async with AsyncClient(transport=ASGITransport(app=_app(db)), base_url="http://test") as client:
        response = await client.get("/api/v1/configurator/demo-variant/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["asset"] is None
    assert "active configurator asset revision is missing or invalid" in payload["blockers"]


@pytest.mark.asyncio
async def test_runtime_capabilities_rejects_revision_identity_mismatch():
    db = _DB()
    db.configurator_asset_versions.rows[0]["asset_id"] = "different-asset"

    async with AsyncClient(transport=ASGITransport(app=_app(db)), base_url="http://test") as client:
        response = await client.get("/api/v1/configurator/demo-variant/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["asset"] is None
    assert "active configurator asset revision is missing or invalid" in payload["blockers"]


@pytest.mark.asyncio
async def test_runtime_capabilities_returns_404_for_unknown_variant():
    db = _DB()
    db.variants.one = None

    async with AsyncClient(transport=ASGITransport(app=_app(db)), base_url="http://test") as client:
        response = await client.get("/api/v1/configurator/missing/capabilities")

    assert response.status_code == 404
    assert response.json()["detail"] == "Vehicle variant not found"
