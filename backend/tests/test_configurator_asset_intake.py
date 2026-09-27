"""TDD contract for production 3D asset provenance and intake evidence."""

import pytest
from pydantic import ValidationError

from configurator_asset_intake import (
    ConfiguratorAssetIntakeRequest,
    validate_asset_intake,
)


def _request(**overrides: object) -> ConfiguratorAssetIntakeRequest:
    values = {
        "asset_id": "asset-1",
        "variant_id": "variant-1",
        "model_id": "model-1",
        "brand_id": "brand-1",
        "format": "glb",
        "source_url": "https://assets.example.com/variant-1.glb",
        "provenance": "OEM_AUTHORIZED",
        "license_name": "OEM production license",
        "license_url": "https://assets.example.com/license",
        "publisher": "Example OEM",
        "version": "1.0.0",
        "file_size_bytes": 1024,
        "checksum_sha256": "a" * 64,
        "storage_key": "configurator/variant-1/1.0.0.glb",
        "storage_provider": "s3",
    }
    values.update(overrides)
    return ConfiguratorAssetIntakeRequest(**values)


def test_valid_intake_is_publishable_only_after_evidence_validation() -> None:
    result = validate_asset_intake(_request())

    assert result.valid is True
    assert result.publishable is True
    assert result.errors == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provenance", "AI_GENERATED_CONCEPT"),
        ("provenance", "UNKNOWN"),
    ],
)
def test_non_publishable_provenance_is_blocked(field: str, value: str) -> None:
    result = validate_asset_intake(_request(**{field: value}))

    assert result.valid is False
    assert result.publishable is False
    assert "asset provenance is not publishable" in result.errors


def test_missing_license_evidence_is_blocked() -> None:
    result = validate_asset_intake(_request(license_name=None, publisher=None))

    assert result.valid is False
    assert result.publishable is False
    assert "asset license evidence is incomplete" in result.errors


def test_invalid_integrity_evidence_is_rejected_by_the_intake_schema() -> None:
    with pytest.raises(ValidationError):
        _request(file_size_bytes=0)

    with pytest.raises(ValidationError):
        _request(checksum_sha256="bad")


def test_variant_identity_must_match_expected_identity() -> None:
    result = validate_asset_intake(
        _request(variant_id="variant-other"),
        expected_variant_id="variant-1",
    )

    assert result.valid is False
    assert result.publishable is False
    assert "asset and expected variant identities do not match" in result.errors


def test_temporary_asset_is_explicitly_non_publishable() -> None:
    result = validate_asset_intake(
        _request(
            provenance="AI_GENERATED_CONCEPT",
            temporary=True,
            temporary_label="TEMPORARY — NON-OEM",
        )
    )

    assert result.valid is False
    assert result.publishable is False
    assert "temporary assets cannot be published to the production catalog" in result.errors


def test_https_and_glb_validation_is_enforced_by_contract() -> None:
    with pytest.raises(ValidationError):
        _request(source_url="http://assets.example.com/variant-1.glb")

    with pytest.raises(ValidationError):
        _request(source_url="https://assets.example.com/variant-1.png")
