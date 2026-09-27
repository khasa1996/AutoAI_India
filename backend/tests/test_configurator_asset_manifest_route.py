"""Regression tests for the complete configurator runtime asset manifest."""

from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from configurator_routes import make_configurator_router
from vehicle_schemas import ConfiguratorStatus


class FakeCollection:
    def __init__(self, documents: list[Optional[Dict[str, Any]]]) -> None:
        self.documents = documents
        self.queries: list[Dict[str, Any]] = []

    async def find_one(
        self,
        query: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None,
    ) -> Optional[Dict[str, Any]]:
        self.queries.append(query)
        for document in self.documents:
            if document is not None and all(document.get(key) == value for key, value in query.items()):
                return document
        return None

    def find(
        self,
        _query: Dict[str, Any],
        _projection: Optional[Dict[str, int]] = None,
    ) -> Any:
        return _AsyncCursor([
            document for document in self.documents
            if document is not None and all(document.get(key) == value for key, value in _query.items())
        ])


class _AsyncCursor:
    def __init__(self, documents: list[Dict[str, Any]]) -> None:
        self.documents = documents

    async def to_list(self, _limit: int) -> list[Dict[str, Any]]:
        return self.documents


class FakeDatabase:
    def __init__(self) -> None:
        self.variants = FakeCollection([
            {
                "variant_id": "variant-1",
                "active": True,
                "verification_status": "verified",
                "configurator_status": ConfiguratorStatus.AVAILABLE,
                "configurator_asset_id": "asset-1",
            }
        ])
        self.variant_pricing = FakeCollection([{
            "variant_id": "variant-1",
            "base_ex_showroom": 1000000,
            "verification_status": "verified",
            "source": "OEM",
        }])
        self.variant_colors = FakeCollection([{"variant_id": "variant-1", "color_id": "black", "available": True}])
        self.variant_wheels = FakeCollection([{"variant_id": "variant-1", "wheel_id": "alloy", "available": True}])
        self.variant_interiors = FakeCollection([{"variant_id": "variant-1", "interior_id": "black", "available": True}])
        self.configurator_options = FakeCollection([])
        self.configurator_assets = FakeCollection([
            {
                "asset_id": "asset-1",
                "variant_id": "variant-1",
                "active_revision_id": "rev-1",
                "revisions": [{"revision_id": "rev-1", "asset_id": "asset-1", "variant_id": "variant-1", "version": "v1", "checksum_sha256": "a" * 64, "state": "PUBLISHED"}],
                "url": "https://cdn.example.com/model.glb",
                "format": "glb",
                "version": "v1",
                "lod_level": 0,
                "published": True,
                "validation_passed": True,
                "supported_interactions": ["camera_exterior", "doors"],
                "paint_material_names": ["BodyPaint"],
                "interior_material_names": ["SeatLeather"],
                "interior_material_mappings": {"black": ["SeatLeather"]},
                "wheel_mesh_names": {"alloy": ["Wheel"]},
                "option_mesh_names": {"roof": {"sunroof": ["Sunroof"]}},
                "camera_preset_names": ["exterior", "interior"],
                "interaction_animation_names": {"doors": "door-open"},
                "provenance": "AUTO_AI_LICENSED",
                "license_name": "Licensed",
                "publisher": "Auto AI India",
                "checksum_sha256": "a" * 64,
                "file_size_bytes": 1024,
                "storage_status": "PUBLISHED",
            }
        ])


def test_asset_route_returns_complete_runtime_manifest() -> None:
    app = FastAPI()
    database = FakeDatabase()
    app.include_router(make_configurator_router(database))
    client = TestClient(app)

    response = client.get("/api/v1/configurator/variant-1/asset")

    assert response.status_code == 200
    asset = response.json()["asset"]
    assert asset["interior_material_names"] == ["SeatLeather"]
    assert asset["interior_material_mappings"] == {"black": ["SeatLeather"]}
    assert asset["camera_preset_names"] == ["exterior", "interior"]
    assert asset["interaction_animation_names"] == {"doors": "door-open"}
    assert database.configurator_assets.queries[-1]["variant_id"] == "variant-1"
