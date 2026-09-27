import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import configurator_routes


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return self.rows


class _Collection:
    def __init__(self, one=None):
        self.one = one

    def find(self, query, projection=None):
        rows = self.one if isinstance(self.one, list) else ([] if self.one is None else [self.one])
        return _Cursor([
            row for row in rows
            if all(row.get(key) == value for key, value in query.items())
        ])

    async def find_one(self, query, projection=None):
        if query.get("variant_id") is not None and self.one is not None:
            if self.one.get("variant_id") != query.get("variant_id"):
                return None
        if query.get("asset_id") is not None and self.one is not None:
            if self.one.get("asset_id") != query.get("asset_id"):
                return None
        if query.get("published") is True and self.one is not None:
            if self.one.get("published") is not True:
                return None
        if query.get("validation_passed") is True and self.one is not None:
            if self.one.get("validation_passed") is not True:
                return None
        return self.one


class _DB:
    def __init__(self, asset):
        self.variants = _Collection(
            {
                "variant_id": "demo-variant",
                "brand_id": "brand-1",
                "model_id": "model-1",
                "active": True,
                "verification_status": "verified",
                "configurator_status": "AVAILABLE",
                "configurator_asset_id": "asset-1",
            }
        )
        self.variant_pricing = _Collection({
            "variant_id": "demo-variant",
            "base_ex_showroom": 1000000,
            "verification_status": "verified",
            "source": "OEM",
        })
        self.variant_colors = _Collection({"variant_id": "demo-variant", "color_id": "black", "available": True})
        self.variant_wheels = _Collection({"variant_id": "demo-variant", "wheel_id": "alloy", "available": True})
        self.variant_interiors = _Collection({"variant_id": "demo-variant", "interior_id": "black", "available": True})
        self.configurator_options = _Collection(None)
        self.configurator_assets = _Collection(asset)


def _asset(state="PUBLISHED"):
    return {
        "asset_id": "asset-1",
        "variant_id": "demo-variant",
        "active_revision_id": "rev-1",
        "revisions": [
            {
                "revision_id": "rev-1",
                "asset_id": "asset-1",
                "variant_id": "demo-variant",
                "version": "2.0.0",
                "checksum_sha256": "b" * 64,
                "state": state,
            }
        ],
        "version": "1.0.0",
        "url": "https://cdn.example/vehicle.glb",
        "format": "glb",
        "lod_level": "LOD0",
        "published": True,
        "validation_passed": True,
        "supported_interactions": [],
        "paint_material_names": [],
        "interior_material_names": [],
        "interior_material_mappings": {},
        "wheel_mesh_names": {},
        "option_mesh_names": {},
        "camera_preset_names": [],
        "interaction_animation_names": {},
        "provenance": "AUTO_AI_LICENSED",
        "license_name": "Licensed",
        "publisher": "Auto AI India",
        "checksum_sha256": "b" * 64,
        "file_size_bytes": 1024,
        "storage_status": "PUBLISHED",
    }


def _client(db):
    app = FastAPI()
    app.include_router(configurator_routes.make_configurator_router(db))
    return TestClient(app)


def test_asset_endpoint_exposes_selected_revision_identity():
    response = _client(_DB(_asset())).get(
        "/api/v1/configurator/demo-variant/asset"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["asset"]["revision_id"] == "rev-1"
    assert payload["asset"]["version"] == "2.0.0"


def test_asset_endpoint_fails_closed_for_non_published_active_revision():
    response = _client(_DB(_asset("SUPERSEDED"))).get(
        "/api/v1/configurator/demo-variant/asset"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False
    assert any("active revision" in blocker for blocker in payload["readiness_blockers"])
    assert "https://cdn.example/vehicle.glb" not in response.text


@pytest.mark.asyncio
async def test_saved_asset_resolution_ignores_arbitrary_requested_asset_id():
    db = _DB(_asset())

    resolved = await configurator_routes.resolve_saved_configuration_asset(
        db,
        "demo-variant",
        "attacker-selected-asset",
    )

    assert resolved == {
        "asset_id": "asset-1",
        "revision_id": "rev-1",
        "version": "2.0.0",
        "checksum_sha256": "b" * 64,
    }
