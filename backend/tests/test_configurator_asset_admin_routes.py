import inspect

from fastapi.params import Header as HeaderParam

from configurator_asset_admin_routes import AssetManifestValidationRequest, _require_admin
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
