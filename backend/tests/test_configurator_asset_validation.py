from configurator_asset_validation import validate_asset_manifest
from configurator_schemas import AssetEvidence, AssetEvidenceStatus, AssetEvidenceType, AssetProvenance, ConfiguratorAssetCreate


def make_asset(**overrides):
    data = {
        "asset_id": "asset-1",
        "variant_id": "v1",
        "model_id": "m1",
        "brand_id": "b1",
        "format": "glb",
        "url": "https://cdn.example.com/car.glb",
        "version": "1.0",
        "provenance": AssetProvenance.AUTO_AI_LICENSED,
        "license_name": "Licensed Asset",
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
        "supported_interactions": ["doors", "hood"],
        "wheel_mesh_names": {"w1": "wheel-a"},
        "option_mesh_names": {"roof-1": ["roof-a"]},
    }
    data.update(overrides)
    return ConfiguratorAssetCreate(**data)


def test_valid_manifest_passes_when_all_mappings_exist():
    result = validate_asset_manifest(make_asset(), ["body", "wheel-a", "roof-a"])
    assert result["valid"] is True
    assert result["errors"] == []


def test_manifest_rejects_missing_mesh_mapping():
    result = validate_asset_manifest(make_asset(), ["body"])
    assert result["valid"] is False
    assert any("missing mesh" in error.lower() for error in result["errors"])


def test_manifest_rejects_unknown_interaction():
    result = validate_asset_manifest(make_asset(supported_interactions=["teleport"]), ["wheel-a", "roof-a"])
    assert result["valid"] is False
    assert any("unsupported interaction" in error.lower() for error in result["errors"])


def test_manifest_rejects_missing_interior_material_mapping():
    asset = make_asset(interior_material_mappings={"leather-black": ["Leather"]})
    result = validate_asset_manifest(asset, ["wheel-a", "roof-a"], ["BodyPaint"])
    assert result["valid"] is False
    assert any("interior material mapping" in error.lower() for error in result["errors"])


def test_manifest_rejects_missing_paint_material_mapping():
    asset = make_asset(paint_material_names=["BodyPaint"])
    result = validate_asset_manifest(asset, ["wheel-a", "roof-a"], ["Leather"])
    assert result["valid"] is False
    assert any("paint material" in error.lower() for error in result["errors"])


def test_manifest_rejects_unknown_camera_preset():
    asset = make_asset(camera_preset_names=["studio-front", "missing-camera"])
    result = validate_asset_manifest(
        asset,
        ["wheel-a", "roof-a"],
        [],
        inspected_camera_preset_names=["studio-front"],
    )
    assert result["valid"] is False
    assert any("camera preset" in error.lower() for error in result["errors"])


def test_manifest_rejects_animation_mapping_for_unsupported_interaction():
    asset = make_asset(
        interaction_animation_names={"doors": {"front_left": "Door_FL"}, "sunroof": {"open": "Sunroof_Open"}}
    )
    result = validate_asset_manifest(asset, ["wheel-a", "roof-a"])
    assert result["valid"] is False
    assert any("animation mapping" in error.lower() for error in result["errors"])
