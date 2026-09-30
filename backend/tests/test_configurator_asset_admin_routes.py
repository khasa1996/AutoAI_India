import inspect
from types import SimpleNamespace

import pytest

from fastapi.params import Header as HeaderParam

from configurator_asset_admin_routes import (\n    AssetManifestValidationRequest,\n    _require_admin,\n    build_asset_onboarding_preflight,\n    validate_inspected_asset_manifest,\n)
from configurator_schemas import AssetEvidence, AssetEvidenceStatus, AssetEvidenceType, AssetProvenance, ConfiguratorAssetCreate


def make_asset(**overrides):
    payload = {
        "asset_id": "asset-001",
        "variant_id": "variant-001",
        "model_id": "model-001",
        "brand_id": "brand-001",
        "format": "glb",
        "url": "https://cdn.example.com/vehicle.glb",
        "version": "1.0.0",
        "provenance": AssetProvenance.AUTO_AI_LICENSED,
        "license_name": "Auto AI licensed asset",
        "publisher": "Auto AI India",
        "provenance_evidence": [AssetEvidence(
            evidence_id="evidence-001",
            evidence_type=AssetEvidenceType.LICENSE_RECORD,
            status=AssetEvidenceStatus.VERIFIED,
            reference="LICENSE-001",
            verified_by="admin@example.invalid",
            verified_at="2026-09-29T00:00:00Z",
        )],
        "validation_passed": True,
        "admin_reviewed": True,
    }
    payload.update(overrides)
    return ConfiguratorAssetCreate(**payload)


def test_asset_manifest_request_accepts_exact_mesh_manifest():
    request = AssetManifestValidationRequest(
        asset=make_asset(wheel_mesh_names={"wheel-a": "Wheel_FL"}),
        mesh_names=["Body", "Wheel_FL"],
    )
    assert request.mesh_names == ["Body", "Wheel_FL"]


def test_publishable_asset_requires_review_and_validation():
    assert make_asset().is_publishable() is True
    assert make_asset(validation_passed=False).is_publishable() is False
    assert make_asset(admin_reviewed=False).is_publishable() is False
    assert make_asset(provenance=AssetProvenance.AI_GENERATED_CONCEPT).is_publishable() is False
    assert make_asset(provenance_evidence=[]).is_publishable() is False
    assert make_asset(provenance_evidence=[AssetEvidence(
        evidence_id="evidence-pending",
        evidence_type=AssetEvidenceType.LICENSE_RECORD,
        status=AssetEvidenceStatus.PENDING,
        reference="LICENSE-PENDING",
    )]).is_publishable() is False


def test_admin_dependency_is_header_bound():
    parameter = inspect.signature(_require_admin).parameters["authorization"]
    assert isinstance(parameter.default, HeaderParam)


class _FakeFindCursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return list(self.rows)


class _FakeCollection:
    def __init__(self, rows=None):
        self.rows = rows or []

    async def find_one(self, query, *_args, **_kwargs):
        for row in self.rows:
            if all(row.get(key) == value for key, value in query.items()):
                return dict(row)
        return None

    def find(self, query, *_args, **_kwargs):
        return _FakeFindCursor([
            dict(row) for row in self.rows
            if all(row.get(key) == value for key, value in query.items())
        ])


@pytest.mark.asyncio
async def test_asset_onboarding_preflight_reports_readiness_blockers():
    db = SimpleNamespace(
        configurator_assets=_FakeCollection([{
            "asset_id": "asset-001",
            "variant_id": "variant-001",
            "version": "1.0.0",
            "published": False,
            "validation_passed": False,
            "provenance": "AUTO_AI_LICENSED",
            "provenance_evidence": [],
        }]),
        variants=_FakeCollection([{
            "variant_id": "variant-001",
            "active": True,
            "verification_status": "verified",
            "configurator_asset_id": "asset-001",
            "source": "canonical",
            "source_url": "https://example.invalid/variant",
        }]),
        variant_pricing=_FakeCollection([{
            "variant_id": "variant-001",
            "base_ex_showroom": 1000000,
            "verification_status": "verified",
            "source": "canonical",
        }]),
        variant_colors=_FakeCollection([{"variant_id": "variant-001", "available": True}]),
        variant_wheels=_FakeCollection([{"variant_id": "variant-001", "available": True}]),
        variant_interiors=_FakeCollection([{"variant_id": "variant-001", "available": True}]),
    )

    result = await build_asset_onboarding_preflight(db, "asset-001")

    assert result["ready"] is False
    assert "configurator asset provenance evidence is missing" in result["blockers"]
    assert "configurator asset is not published" in result["blockers"]



def test_provenance_evidence_rejects_invalid_audit_fields():
    invalid_verifier = AssetEvidence(
        evidence_id="evidence-invalid-verifier",
        evidence_type=AssetEvidenceType.LICENSE_RECORD,
        status=AssetEvidenceStatus.VERIFIED,
        reference="LICENSE-INVALID",
        verified_by="   ",
        verified_at="2026-09-29T00:00:00Z",
    )
    invalid_timestamp = AssetEvidence(
        evidence_id="evidence-invalid-time",
        evidence_type=AssetEvidenceType.LICENSE_RECORD,
        status=AssetEvidenceStatus.VERIFIED,
        reference="LICENSE-INVALID-TIME",
        verified_by="admin@example.invalid",
        verified_at="not-a-timestamp",
    )
    assert invalid_verifier.is_verified() is False
    assert invalid_timestamp.is_verified() is False
\n\ndef test_finalize_manifest_cross_checks_inspected_cameras_and_animations():\n    asset = make_asset(\n        camera_preset_names=["studio-front"],\n        interaction_animation_names={"doors": {"front_left": "Door_FL_Open"}},\n    )\n\n    result = validate_inspected_asset_manifest(\n        asset,\n        {\n            "mesh_names": ["Body", "Wheel_FL"],\n            "node_names": [],\n            "material_names": [],\n            "camera_names": [],\n            "animation_names": [],\n        },\n    )\n\n    assert result["valid"] is False\n    assert any("camera preset" in error.lower() for error in result["errors"])\n    assert any("animation mapping" in error.lower() for error in result["errors"])\n