"""Tests for the non-persistent configurator reconciliation matrix."""

from configurator_catalog_reconciliation import (
    AuthoritativeCatalogEvidence,
    AuthoritativeVehicleIdentity,
    ReconciliationStatus,
)
from configurator_reconciliation_matrix import build_reconciliation_matrix


def test_matrix_keeps_missing_records_blocked() -> None:
    records = [
        {
            "id": "A",
            "brand": "Kia",
            "model": "Seltos",
            "variant": "GTX+",
            "fuel": "Diesel",
            "transmission": "Automatic",
        },
        {
            "id": "B",
            "brand": "MG",
            "model": "Hector",
            "variant": "Savvy Pro",
            "fuel": "Petrol",
            "transmission": "Automatic",
        },
    ]

    result = build_reconciliation_matrix(records)

    assert [item.status for item in result] == [
        ReconciliationStatus.REVIEW_REQUIRED,
        ReconciliationStatus.REVIEW_REQUIRED,
    ]


def test_matrix_uses_only_explicit_identity_and_evidence() -> None:
    records = [
        {
            "id": "A",
            "brand": "Kia",
            "model": "Seltos",
            "variant": "GTX+",
            "fuel": "Diesel",
            "transmission": "Automatic",
        }
    ]
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
    evidence = AuthoritativeCatalogEvidence(
        pricing_verified=True,
        compatible_colors_verified=True,
        compatible_wheels_verified=True,
        compatible_interiors_verified=True,
        licensed_3d_asset_verified=True,
        asset_revision_published=True,
    )

    result = build_reconciliation_matrix(
        records,
        identities={"a": identity},
        evidence={"a": evidence},
    )

    assert result[0].status is ReconciliationStatus.READY_FOR_ONBOARDING
    assert result[0].canonical_variant_id == "kia-seltos-gtx"


def test_matrix_does_not_mutate_inputs() -> None:
    records = [
        {
            "id": "A",
            "brand": "Tata",
            "model": "Nexon",
            "variant": "XZ+",
            "fuel": "Petrol",
            "transmission": "Manual",
        }
    ]
    before_records = [dict(record) for record in records]
    identities = {}
    evidence = {}

    build_reconciliation_matrix(records, identities, evidence)

    assert records == before_records
    assert identities == {}
    assert evidence == {}
