from configurator_vehicle_readiness import assess_vehicle_configurator_readiness


def _vehicle():
    return {
        "variant_id": "demo-variant",
        "model_id": "demo-model",
        "brand_id": "demo-brand",
        "active": True,
        "verification_status": "verified",
        "configurator_status": "AVAILABLE",
        "configurator_asset_id": "asset-1",
    }


def _pricing():
    return {
        "variant_id": "demo-variant",
        "base_ex_showroom": 1000000,
        "source": "verified-source",
        "verification_status": "verified",
    }


def _asset():
    return {
        "asset_id": "asset-1",
        "variant_id": "demo-variant",
        "version": "1.0.0",
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
        "storage_status": "PUBLISHED",
    }


def _options():
    return ([{"variant_id": "demo-variant", "available": True}],
            [{"variant_id": "demo-variant", "available": True}],
            [{"variant_id": "demo-variant", "available": True}])


def test_complete_verified_vehicle_is_ready():
    colors, wheels, interiors = _options()
    result = assess_vehicle_configurator_readiness(
        _vehicle(), _pricing(), colors, wheels, interiors, _asset()
    )
    assert result["ready"] is True
    assert result["blockers"] == []


def test_unverified_vehicle_data_blocks_production_readiness():
    vehicle = {**_vehicle(), "verification_status": "unverified"}
    colors, wheels, interiors = _options()
    result = assess_vehicle_configurator_readiness(
        vehicle, _pricing(), colors, wheels, interiors, _asset()
    )
    assert result["ready"] is False
    assert "vehicle verification is not complete" in result["blockers"]


def test_missing_pricing_blocks_production_readiness():
    colors, wheels, interiors = _options()
    result = assess_vehicle_configurator_readiness(
        _vehicle(), None, colors, wheels, interiors, _asset()
    )
    assert result["ready"] is False
    assert "authoritative variant pricing is missing" in result["blockers"]


def test_missing_required_option_category_blocks_readiness():
    colors, _, interiors = _options()
    result = assess_vehicle_configurator_readiness(
        _vehicle(), _pricing(), colors, [], interiors, _asset()
    )
    assert result["ready"] is False
    assert "no available wheel option for the vehicle" in result["blockers"]


def test_asset_identity_and_publication_are_required():
    colors, wheels, interiors = _options()
    asset = {**_asset(), "asset_id": "wrong-asset"}
    result = assess_vehicle_configurator_readiness(
        _vehicle(), _pricing(), colors, wheels, interiors, asset
    )
    assert result["ready"] is False
    assert "configured asset identity does not match the variant" in result["blockers"]


def test_asset_license_and_publisher_are_required():
    colors, wheels, interiors = _options()
    asset = {**_asset(), "license_name": None, "publisher": None}
    result = assess_vehicle_configurator_readiness(
        _vehicle(), _pricing(), colors, wheels, interiors, asset
    )
    assert result["ready"] is False
    assert "configurator asset license metadata is incomplete" in result["blockers"]


def test_asset_integrity_evidence_is_required():
    colors, wheels, interiors = _options()
    asset = {**_asset(), "checksum_sha256": None, "file_size_bytes": None}
    result = assess_vehicle_configurator_readiness(
        _vehicle(), _pricing(), colors, wheels, interiors, asset
    )
    assert result["ready"] is False
    assert "configurator asset integrity evidence is incomplete" in result["blockers"]


def test_asset_storage_publication_state_is_required():
    colors, wheels, interiors = _options()
    asset = {**_asset(), "storage_status": "VALIDATED"}
    result = assess_vehicle_configurator_readiness(
        _vehicle(), _pricing(), colors, wheels, interiors, asset
    )
    assert result["ready"] is False
    assert "configurator asset storage publication state is not complete" in result["blockers"]


def test_missing_provenance_evidence_blocks_production_readiness():
    colors, wheels, interiors = _options()
    asset = {**_asset(), "provenance_evidence": []}
    result = assess_vehicle_configurator_readiness(
        _vehicle(), _pricing(), colors, wheels, interiors, asset
    )
    assert result["ready"] is False
    assert "configurator asset provenance evidence is missing" in result["blockers"]


def test_pending_or_incomplete_provenance_evidence_blocks_production_readiness():
    colors, wheels, interiors = _options()
    asset = {**_asset(), "provenance_evidence": [{
        "evidence_id": "evidence-pending",
        "evidence_type": "LICENSE_RECORD",
        "status": "PENDING",
        "reference": "LICENSE-PENDING",
    }]}
    result = assess_vehicle_configurator_readiness(
        _vehicle(), _pricing(), colors, wheels, interiors, asset
    )
    assert result["ready"] is False
    assert "configurator asset provenance evidence is not fully verified" in result["blockers"]
