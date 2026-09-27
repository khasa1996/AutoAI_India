"""Tests for explicit authoritative reconciliation mapping intake."""

import pytest

from configurator_catalog_reconciliation import (
    AuthoritativeCatalogEvidence,
    AuthoritativeVehicleIdentity,
)
from configurator_reconciliation_intake import (
    AuthoritativeReconciliationMapping,
    validate_reconciliation_mappings,
)


def make_mapping(legacy_car_id: str, variant_id: str) -> AuthoritativeReconciliationMapping:
    return AuthoritativeReconciliationMapping(
        legacy_car_id=legacy_car_id,
        identity=AuthoritativeVehicleIdentity.from_verified_source(
            brand_id="kia",
            brand_name="Kia",
            model_id="kia-seltos",
            model_name="Seltos",
            variant_id=variant_id,
            variant_name="GTX+",
            fuel_type="Petrol",
            transmission="Automatic",
            source="OEM",
            source_url="https://example.com/kia/seltos",
        ),
        evidence=AuthoritativeCatalogEvidence(),
    )


def test_mapping_intake_requires_unique_legacy_and_variant_ids() -> None:
    first = make_mapping("legacy-a", "kia-seltos-gtx")
    duplicate_legacy = make_mapping("legacy-a", "kia-seltos-gtx-2")

    with pytest.raises(ValueError, match="duplicate legacy_car_id"):
        validate_reconciliation_mappings([first, duplicate_legacy])


def test_mapping_intake_rejects_duplicate_authoritative_variant_ids() -> None:
    first = make_mapping("legacy-a", "kia-seltos-gtx")
    duplicate_variant = make_mapping("legacy-b", "kia-seltos-gtx")

    with pytest.raises(ValueError, match="duplicate authoritative variant_id"):
        validate_reconciliation_mappings([first, duplicate_variant])


def test_mapping_intake_rejects_unverified_identity() -> None:
    mapping = make_mapping("legacy-a", "kia-seltos-gtx")
    unverified = mapping.identity.model_copy(update={"verification_status": "unverified"})
    invalid = mapping.model_copy(update={"identity": unverified})

    with pytest.raises(ValueError, match="not verified"):
        validate_reconciliation_mappings([invalid])


def test_mapping_intake_is_non_mutating() -> None:
    mapping = make_mapping("legacy-a", "kia-seltos-gtx")

    result = validate_reconciliation_mappings([mapping])

    assert result == (mapping,)
    assert mapping.legacy_car_id == "legacy-a"
