"""TDD gate for safe configurator catalog onboarding preparation."""

import pytest

from configurator_onboarding_adapter import prepare_configurator_onboarding
from configurator_onboarding_contract import ConfiguratorOnboardingRecordSet
from configurator_vehicle_catalog_manifest import ConfiguratorVehicleCatalogManifest


def _manifest(**overrides: object) -> ConfiguratorVehicleCatalogManifest:
    values = {
        "brand_id": "brand-1",
        "brand_name": "Example",
        "model_id": "model-1",
        "model_name": "Example SUV",
        "variant_id": "variant-1",
        "variant_name": "Example Premium",
        "fuel_type": "petrol",
        "transmission": "automatic",
        "verification_status": "verified",
        "active": True,
        "configurator_status": "AVAILABLE",
        "source": "verified-oem-source",
        "source_url": "https://example.com/variant-1",
    }
    values.update(overrides)
    return ConfiguratorVehicleCatalogManifest(**values)


def _records() -> ConfiguratorOnboardingRecordSet:
    return ConfiguratorOnboardingRecordSet(
        vehicle={
            "variant_id": "variant-1",
            "model_id": "model-1",
            "brand_id": "brand-1",
            "active": True,
            "verification_status": "verified",
            "configurator_status": "AVAILABLE",
            "configurator_asset_id": "asset-1",
            "source": "verified-oem-source",
            "source_url": "https://example.com/variant-1",
        },
        pricing={
            "variant_id": "variant-1",
            "base_ex_showroom": 1000000,
            "source": "verified-source",
            "verification_status": "verified",
        },
        colors=[{"variant_id": "variant-1", "color_id": "paint-1", "available": True}],
        wheels=[{"variant_id": "variant-1", "wheel_id": "wheel-1", "available": True}],
        interiors=[{"variant_id": "variant-1", "interior_id": "interior-1", "available": True}],
        asset={
            "asset_id": "asset-1",
            "variant_id": "variant-1",
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
            "revisions": [
                {
                    "revision_id": "rev-1",
                    "asset_id": "asset-1",
                    "variant_id": "variant-1",
                    "version": "1.0.0",
                    "checksum_sha256": "a" * 64,
                    "state": "PUBLISHED",
                }
            ],
        },
    )


def test_preparation_requires_explicit_production_database_authority() -> None:
    result = prepare_configurator_onboarding(
        _manifest(),
        _records(),
        configured_database_name="autoai",
        expected_database_name=None,
    )

    assert result.ready is False
    assert result.errors == ["expected production database name is not configured"]
    assert result.write_allowed is False


def test_preparation_rejects_database_name_mismatch() -> None:
    result = prepare_configurator_onboarding(
        _manifest(),
        _records(),
        configured_database_name="auto_ai",
        expected_database_name="autoai",
    )

    assert result.ready is False
    assert result.errors == [
        "configured database does not match expected production database"
    ]
    assert result.write_allowed is False


def test_preparation_requires_manifest_and_runtime_variant_identity_to_match() -> None:
    records = _records()
    records.vehicle["variant_id"] = "variant-other"

    result = prepare_configurator_onboarding(
        _manifest(),
        records,
        configured_database_name="autoai",
        expected_database_name="autoai",
    )

    assert result.ready is False
    assert result.errors == ["manifest and runtime variant identities do not match"]
    assert result.write_allowed is False


def test_preparation_rejects_manifest_and_runtime_model_identity_mismatch() -> None:
    records = _records()
    records.vehicle["model_id"] = "model-other"

    result = prepare_configurator_onboarding(
        _manifest(),
        records,
        configured_database_name="autoai",
        expected_database_name="autoai",
    )

    assert result.ready is False
    assert result.errors == ["manifest and runtime model identities do not match"]
    assert result.write_allowed is False


def test_preparation_rejects_manifest_and_runtime_brand_identity_mismatch() -> None:
    records = _records()
    records.vehicle["brand_id"] = "brand-other"

    result = prepare_configurator_onboarding(
        _manifest(),
        records,
        configured_database_name="autoai",
        expected_database_name="autoai",
    )

    assert result.ready is False
    assert result.errors == ["manifest and runtime brand identities do not match"]
    assert result.write_allowed is False


def test_valid_preparation_is_still_write_disabled() -> None:
    result = prepare_configurator_onboarding(
        _manifest(),
        _records(),
        configured_database_name="autoai",
        expected_database_name="autoai",
    )

    assert result.ready is True
    assert result.errors == []
    assert result.warnings == []
    assert result.write_allowed is False
    assert result.variant_id == "variant-1"


def test_invalid_onboarding_records_are_reported_without_writes() -> None:
    records = _records()
    records.asset = None

    result = prepare_configurator_onboarding(
        _manifest(),
        records,
        configured_database_name="autoai",
        expected_database_name="autoai",
    )

    assert result.ready is False
    assert "published verified configurator asset is missing" in result.errors
    assert result.write_allowed is False


def test_manifest_validation_error_is_reported() -> None:
    with pytest.raises(ValueError, match="vehicle verification is not complete"):
        prepare_configurator_onboarding(
            _manifest(verification_status="unverified"),
            _records(),
            configured_database_name="autoai",
            expected_database_name="autoai",
        )
