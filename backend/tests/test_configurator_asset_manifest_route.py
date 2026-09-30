"""Regression tests for the complete configurator runtime asset manifest."""

from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from configurator_routes import make_configurator_router
from vehicle_schemas import ConfiguratorStatus


class FakeCursor:
    def __init__(self, documents: list[Dict[str, Any]]) -> None:
        self.documents = documents

    async def to_list(self, _limit: int) -> list[Dict[str, Any]]:
        return list(self.documents)


class FakeCollection:
    def __init__(self, documents: list[Optional[Dict[str, Any]]]) -> None:
        self.documents = [document for document in documents if document is not None]
        self.queries: list[Dict[str, Any]] = []

    async def find_one(
        self,
        query: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None,
    ) -> Optional[Dict[str, Any]]:
        self.queries.append(query)
        for document in self.documents:
            if document is not None:
                return document
        return None

    def find(
        self,
        query: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None,
    ) -> FakeCursor:
        self.queries.append(query)
        return FakeCursor([
            document for document in self.documents
            if all(document.get(key) == value for key, value in query.items())
        ])


class FakeDatabase:
    def __init__(self) -> None:
        self.variants = FakeCollection([{
            "variant_id": "variant-1",
            "configurator_status": ConfiguratorStatus.AVAILABLE,
            "configurator_asset_id": "asset-1",
            "active": True,
            "verification_status": "verified",
        }])
        self.variant_pricing = FakeCollection([{
            "variant_id": "variant-1",
            "base_ex_showroom": 1000000,
            "verification_status": "verified",
            "source": "canonical",
        }])
        self.variant_colors = FakeCollection([{"variant_id": "variant-1", "available": True}])
        self.variant_wheels = FakeCollection([{"variant_id": "variant-1", "available": True}])
        self.variant_interiors = FakeCollection([{"variant_id": "variant-1", "available": True}])
        self.configurator_assets = FakeCollection([{
            "asset_id": "asset-1",
            "variant_id": "variant-1",
            "url": "https://cdn.example.com/model.glb",
            "cdn_url": "https://cdn.example.com/model.glb",
            "format": "glb",
            "version": "v1",
            "lod_level": "LOD0",
            "published": True,
            "validation_passed": True,
            "admin_reviewed": True,
            "provenance": "AUTO_AI_LICENSED",
            "provenance_evidence": [{
                "evidence_id": "evidence-1",
                "evidence_type": "LICENSE_RECORD",
                "status": "VERIFIED",
                "reference": "LICENSE-1",
                "verified_by": "admin@example.invalid",
                "verified_at": "2026-09-29T00:00:00Z",
            }],
            "license_name": "Test license",
            "publisher": "Auto AI India",
            "checksum_sha256": "a" * 64,
            "file_size_bytes": 1024,
            "storage_key": "assets/asset-1/v1/model.glb",
            "storage_status": "PUBLISHED",
            "supported_interactions": ["camera_exterior", "doors"],
            "paint_material_names": ["BodyPaint"],
            "interior_material_names": ["SeatLeather"],
            "interior_material_mappings": {"black": ["SeatLeather"]},
            "wheel_mesh_names": {"alloy": "Wheel"},
            "option_mesh_names": {"roof": ["Sunroof"]},
            "camera_preset_names": ["exterior", "interior"],
            "interaction_animation_names": {"doors": {"open": "door-open"}},
        }])
        self.configurator_asset_versions = FakeCollection([{
            "asset_id": "asset-1",
            "variant_id": "variant-1",
            "revision_id": "rev-1",
            "version": "v1",
            "checksum_sha256": "a" * 64,
            "file_size_bytes": 1024,
            "storage_key": "assets/asset-1/v1/model.glb",
            "published": True,
            "validation_passed": True,
            "admin_reviewed": True,
            "storage_status": "PUBLISHED",
            "cdn_url": "https://immutable.example/model.glb",
            "url": "https://immutable.example/model.glb",
            "lod_level": "LOD0",
            "provenance": "AUTO_AI_LICENSED",
            "license_name": "Test license",
            "publisher": "Auto AI India",
            "supported_interactions": ["camera_exterior", "doors"],
            "camera_preset_names": ["exterior", "interior"],
            "interaction_animation_names": {"doors": {"open": "door-open"}},
            "paint_material_names": ["BodyPaint"],
            "interior_material_names": ["SeatLeather"],
            "interior_material_mappings": {"black": ["SeatLeather"]},
            "wheel_mesh_names": {"alloy": "Wheel"},
            "option_mesh_names": {"roof": ["Sunroof"]},
        }])

