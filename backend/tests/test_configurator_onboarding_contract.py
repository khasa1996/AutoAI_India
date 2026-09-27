"""TDD gate for the side-effect-free production configurator onboarding contract."""

from configurator_onboarding_contract import (
    ConfiguratorOnboardingRecordSet,
    validate_onboarding_record_set,
)


def _verified_asset() -> dict:
    return {
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
    }


def _complete_records() -> ConfiguratorOnboardingRecordSet:
    return ConfiguratorOnboardingRecordSet(
        vehicle={
            "variant_id": "variant-1",
            "model_id": "model-1",
            "brand_id": "brand-1",
            "active": True,
            "verification_status": "verified",
            "configurator_status": "AVAILABLE",
            "configurator_asset_id": "asset-1",
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
        asset=_verified_asset(),
    )


def test_complete_onboarding_record_set_is_valid() -> None:
    result = validate_onboarding_record_set(_complete_records())

    assert result.valid is True
    assert result.errors == []


def test_missing_verified_pricing_blocks_onboarding() -> None:
    records = _complete_records()
    records.pricing = None

    result = validate_onboarding_record_set(records)

    assert result.valid is False
    assert "authoritative variant pricing is missing" in result.errors


def test_missing_option_category_blocks_onboarding() -> None:
    records = _complete_records()
    records.wheels = []

    result = validate_onboarding_record_set(records)

    assert result.valid is False
    assert "no available wheel option for the vehicle" in result.errors


def test_unpublishable_asset_blocks_onboarding() -> None:
    records = _complete_records()
    records.asset = {**_verified_asset(), "provenance": "AI_GENERATED_CONCEPT"}

    result = validate_onboarding_record_set(records)

    assert result.valid is False
    assert "configurator asset provenance is not publishable" in result.errors


def test_missing_active_revision_blocks_onboarding() -> None:
    records = _complete_records()
    records.asset = {key: value for key, value in _verified_asset().items() if key not in {"active_revision_id", "revisions"}}

    result = validate_onboarding_record_set(records)

    assert result.valid is False
    assert "configurator asset active revision is not published or is invalid" in result.errors


def test_onboarding_validation_is_side_effect_free() -> None:
    records = _complete_records()
    before = records.model_dump()

    result = validate_onboarding_record_set(records)

    assert result.valid is True
    assert records.model_dump() == before
