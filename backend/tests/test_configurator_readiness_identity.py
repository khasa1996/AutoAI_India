"""TDD gate for strict production readiness identity and integrity."""

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
        "checksum_sha256": "a" * 64,
        "file_size_bytes": 1024,
        "storage_status": "PUBLISHED",
        "active_revision_id": "rev-1",
        "revisions": [{
            "revision_id": "rev-1",
            "asset_id": "asset-1",
            "variant_id": "demo-variant",
            "version": "1.0.0",
            "checksum_sha256": "a" * 64,
            "state": "PUBLISHED",
        }],
    }


def _options():
    return (
        [{"variant_id": "demo-variant", "available": True}],
        [{"variant_id": "demo-variant", "available": True}],
        [{"variant_id": "demo-variant", "available": True}],
    )


def test_complete_verified_vehicle_is_ready():
    colors, wheels, interiors = _options()
    result = assess_vehicle_configurator_readiness(
        _vehicle(), _pricing(), colors, wheels, interiors, _asset()
    )
    assert result["ready"] is True
    assert result["blockers"] == []


def test_missing_required_option_category_blocks_readiness():
    colors, _, interiors = _options()
    result = assess_vehicle_configurator_readiness(
        _vehicle(), _pricing(), colors, [], interiors, _asset()
    )
    assert result["ready"] is False
    assert "no available wheel option for the vehicle" in result["blockers"]


def test_mismatched_option_identity_blocks_readiness():
    colors, wheels, interiors = _options()
    mismatched = [{**wheels[0], "variant_id": "other-variant"}]
    result = assess_vehicle_configurator_readiness(
        _vehicle(), _pricing(), colors, mismatched, interiors, _asset()
    )
    assert result["ready"] is False
    assert "no available wheel option for the vehicle" in result["blockers"]


def test_zero_or_negative_price_blocks_readiness():
    colors, wheels, interiors = _options()
    pricing = {**_pricing(), "base_ex_showroom": 0}
    result = assess_vehicle_configurator_readiness(
        _vehicle(), pricing, colors, wheels, interiors, _asset()
    )
    assert result["ready"] is False
    assert "positive base ex-showroom price" in " ".join(result["blockers"])


def test_unpublishable_asset_provenance_blocks_readiness():
    colors, wheels, interiors = _options()
    asset = {**_asset(), "provenance": "AI_GENERATED_CONCEPT"}
    result = assess_vehicle_configurator_readiness(
        _vehicle(), _pricing(), colors, wheels, interiors, asset
    )
    assert result["ready"] is False
    assert "provenance is not publishable" in " ".join(result["blockers"])


def test_oversized_asset_blocks_readiness():
    colors, wheels, interiors = _options()
    asset = {**_asset(), "file_size_bytes": 200 * 1024 * 1024 + 1}
    result = assess_vehicle_configurator_readiness(
        _vehicle(), _pricing(), colors, wheels, interiors, asset
    )
    assert result["ready"] is False
    assert "integrity evidence is incomplete" in " ".join(result["blockers"])
