"""Tests for the side-effect-free configurator catalog reconciliation boundary."""

from datetime import date

import pytest

from configurator_catalog_reconciliation import (
    AuthoritativeCatalogEvidence,
    AuthoritativeVehicleIdentity,
    ReconciliationStatus,
    reconcile_legacy_vehicle,
)


def _legacy() -> dict[str, str]:
    return {
        "id": "kia-seltos",
        "brand": "Kia",
        "model": "Seltos",
        "variant": "GTX+",
        "fuel": "Petrol",
        "transmission": "Automatic",
    }


def _identity() -> AuthoritativeVehicleIdentity:
    return AuthoritativeVehicleIdentity(
        brand_id="kia",
        brand_name="Kia",
        model_id="kia-seltos",
        model_name="Seltos",
        variant_id="kia-seltos-gtx",
        variant_name="GTX+",
        fuel_type="Petrol",
        transmission="Automatic",
        source="OEM",
        source_url="https://example.invalid/oem",
    )


def _complete_evidence() -> AuthoritativeCatalogEvidence:
    return AuthoritativeCatalogEvidence(
        pricing_verified=True,
        compatible_colors_verified=True,
        compatible_wheels_verified=True,
        compatible_interiors_verified=True,
        licensed_3d_asset_verified=True,
        asset_revision_published=True,
    )


def test_legacy_record_alone_requires_review() -> None:
    result = reconcile_legacy_vehicle(_legacy())

    assert result.status is ReconciliationStatus.REVIEW_REQUIRED
    assert result.canonical_variant_id is None
    assert "authoritative vehicle identity is missing" in result.blockers


def test_explicit_identity_mismatch_is_blocked() -> None:
    identity = _identity().model_copy(update={"variant_name": "GTX"})

    result = reconcile_legacy_vehicle(_legacy(), identity)

    assert result.status is ReconciliationStatus.REVIEW_REQUIRED
    assert result.canonical_variant_id is None


def test_verified_identity_without_evidence_is_not_ready() -> None:
    result = reconcile_legacy_vehicle(_legacy(), _identity())

    assert result.status is ReconciliationStatus.IDENTITY_VERIFIED
    assert result.canonical_variant_id == "kia-seltos-gtx"
    assert result.blockers


def test_complete_authoritative_evidence_is_ready_for_onboarding() -> None:
    result = reconcile_legacy_vehicle(_legacy(), _identity(), _complete_evidence())

    assert result.status is ReconciliationStatus.READY_FOR_ONBOARDING
    assert result.canonical_variant_id == "kia-seltos-gtx"
    assert result.blockers == []


def test_historical_model_year_must_match_explicitly() -> None:
    legacy = _legacy() | {"model_year": 2024}
    identity = _identity().model_copy(update={"model_year": 2024})

    result = reconcile_legacy_vehicle(legacy, identity, _complete_evidence())

    assert result.status is ReconciliationStatus.READY_FOR_ONBOARDING


def test_model_year_mismatch_is_blocked() -> None:
    legacy = _legacy() | {"model_year": 2024}
    identity = _identity().model_copy(update={"model_year": 2025})

    result = reconcile_legacy_vehicle(legacy, identity)

    assert result.status is ReconciliationStatus.REVIEW_REQUIRED
    assert "model year does not match" in result.blockers[0]


def test_model_year_scoped_identity_cannot_match_unscoped_legacy_record() -> None:
    identity = _identity().model_copy(update={"model_year": 2024})

    result = reconcile_legacy_vehicle(_legacy(), identity)

    assert result.status is ReconciliationStatus.REVIEW_REQUIRED
    assert "legacy model year is missing" in result.blockers[0]


def test_historical_gtx_plus_remains_distinct_from_current_gtx_o() -> None:
    current_identity = _identity().model_copy(
        update={
            "variant_name": "GTX(O)",
            "variant_id": "kia-seltos-gtx-o",
            "model_year": 2026,
        }
    )

    result = reconcile_legacy_vehicle(_legacy() | {"model_year": 2024}, current_identity)

    assert result.status is ReconciliationStatus.REVIEW_REQUIRED
    assert result.canonical_variant_id is None


def test_effective_date_scope_requires_legacy_scope() -> None:
    identity = _identity().model_copy(update={"effective_from": date(2024, 1, 1)})

    result = reconcile_legacy_vehicle(_legacy(), identity)

    assert result.status is ReconciliationStatus.REVIEW_REQUIRED
    assert "effective-date scope is missing" in result.blockers[0]


def test_effective_date_range_is_validated() -> None:
    with pytest.raises(ValueError, match="effective_to"):
        AuthoritativeVehicleIdentity(
            **_identity()
            .model_copy(
                update={
                    "effective_from": date(2025, 1, 1),
                    "effective_to": date(2024, 1, 1),
                }
            )
            .model_dump()
        )


def test_reconciliation_does_not_mutate_legacy_input() -> None:
    legacy = _legacy()
    before = dict(legacy)

    reconcile_legacy_vehicle(legacy, _identity(), _complete_evidence())

    assert legacy == before



def test_verified_source_factory_rejects_no_unverified_state() -> None:
    identity = AuthoritativeVehicleIdentity.from_verified_source(
        brand_id="kia",
        brand_name="Kia",
        model_id="kia-seltos",
        model_name="Seltos",
        variant_id="kia-seltos-gtx",
        variant_name="GTX+",
        fuel_type="Diesel",
        transmission="Automatic",
        source="OEM",
        source_url="https://example.invalid/oem",
    )

    assert identity.verification_status == "verified"
