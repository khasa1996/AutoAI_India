"""TDD gate for production vehicle/variant catalog onboarding."""

import pytest
from pydantic import ValidationError

from configurator_vehicle_catalog_manifest import (
    ConfiguratorVehicleCatalogManifest,
    validate_catalog_manifest,
)


def _record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "brand_id": "tata",
        "brand_name": "Tata Motors",
        "model_id": "nexon",
        "model_name": "Nexon",
        "variant_id": "tata-nexon-creative-plus",
        "variant_name": "Creative+",
        "fuel_type": "petrol",
        "transmission": "automatic",
        "verification_status": "verified",
        "active": True,
        "configurator_status": "AVAILABLE",
        "source": "OEM",
        "source_url": "https://example.com/nexon",
    }
    record.update(overrides)
    return record


def test_manifest_requires_canonical_variant_identity() -> None:
    payload = _record(variant_id="")

    with pytest.raises(ValidationError):
        ConfiguratorVehicleCatalogManifest.model_validate(payload)


def test_manifest_rejects_unverified_vehicle() -> None:
    with pytest.raises(ValueError, match="vehicle verification is not complete"):
        validate_catalog_manifest(
            ConfiguratorVehicleCatalogManifest.model_validate(
                _record(verification_status="unverified")
            )
        )


def test_manifest_rejects_non_available_configurator_status() -> None:
    with pytest.raises(ValueError, match="configurator status must be AVAILABLE"):
        validate_catalog_manifest(
            ConfiguratorVehicleCatalogManifest.model_validate(
                _record(configurator_status="COMING_SOON")
            )
        )


def test_manifest_rejects_duplicate_variant_ids() -> None:
    first = ConfiguratorVehicleCatalogManifest.model_validate(_record())
    second = ConfiguratorVehicleCatalogManifest.model_validate(
        _record(variant_name="Creative+ Dark")
    )

    with pytest.raises(ValueError, match="duplicate variant_id"):
        validate_catalog_manifest([first, second])


def test_manifest_rejects_legacy_car_identity() -> None:
    payload = _record()
    payload["legacy_car_id"] = "legacy-106"

    with pytest.raises(ValueError, match="legacy car records cannot be used"):
        validate_catalog_manifest(ConfiguratorVehicleCatalogManifest.model_validate(payload))


def test_manifest_accepts_verified_available_variant() -> None:
    manifest = ConfiguratorVehicleCatalogManifest.model_validate(_record())

    assert validate_catalog_manifest(manifest) == manifest


def test_manifest_batch_accepts_unique_verified_variants() -> None:
    first = ConfiguratorVehicleCatalogManifest.model_validate(_record())
    second = ConfiguratorVehicleCatalogManifest.model_validate(
        _record(
            variant_id="tata-nexon-creative-plus-diesel",
            variant_name="Creative+ Diesel",
            fuel_type="diesel",
        )
    )

    result = validate_catalog_manifest([first, second])

    assert result == [first, second]
