"""Tests for read-only reconciliation reporting."""

from configurator_catalog_reconciliation import (
    AuthoritativeCatalogEvidence,
    AuthoritativeVehicleIdentity,
    CatalogReconciliationResult,
    ReconciliationStatus,
)
from configurator_oem_evidence_package import OemEvidencePackage
from configurator_reconciliation_report import (
    reconcile_and_summarize_legacy_catalog,
    summarize_oem_evidence_queue,
    summarize_reconciliation_matrix,
)


def test_report_aggregates_statuses_and_blockers_deterministically() -> None:
    results = [
        CatalogReconciliationResult(
            status=ReconciliationStatus.REVIEW_REQUIRED,
            legacy_car_id="kia-seltos",
            blockers=["authoritative vehicle identity is missing"],
        ),
        CatalogReconciliationResult(
            status=ReconciliationStatus.IDENTITY_VERIFIED,
            legacy_car_id="mg-hector",
            canonical_variant_id="mg-hector-savvy-pro",
            blockers=["licensed 3D asset is not verified"],
        ),
        CatalogReconciliationResult(
            status=ReconciliationStatus.READY_FOR_ONBOARDING,
            legacy_car_id="audi-q3",
            canonical_variant_id="audi-q3-premium-plus",
        ),
    ]

    report = summarize_reconciliation_matrix(results)

    assert report.total_records == 3
    assert report.status_counts == {
        "REVIEW_REQUIRED": 1,
        "IDENTITY_VERIFIED": 1,
        "READY_FOR_ONBOARDING": 1,
    }
    assert report.blocker_counts == {
        "authoritative vehicle identity is missing": 1,
        "licensed 3D asset is not verified": 1,
    }
    assert report.ready_legacy_car_ids == ("audi-q3",)
    assert report.blocked_legacy_car_ids == ("kia-seltos", "mg-hector")


def test_report_is_stable_for_repeated_input_order() -> None:
    ready = CatalogReconciliationResult(
        status=ReconciliationStatus.READY_FOR_ONBOARDING,
        legacy_car_id="z",
    )
    review = CatalogReconciliationResult(
        status=ReconciliationStatus.REVIEW_REQUIRED,
        legacy_car_id="a",
        blockers=["blocker"],
    )

    first = summarize_reconciliation_matrix([ready, review]).to_dict()
    second = summarize_reconciliation_matrix([review, ready]).to_dict()

    assert first == second



def test_reconcile_and_summarize_stays_non_persistent_and_blocks_unmapped_records() -> None:
    records = [
        {
            "id": "B",
            "brand": "MG",
            "model": "Hector",
            "variant": "Savvy Pro",
            "fuel": "Petrol",
            "transmission": "Automatic",
        },
        {
            "id": "A",
            "brand": "Kia",
            "model": "Seltos",
            "variant": "GTX+",
            "fuel": "Petrol",
            "transmission": "Automatic",
        },
    ]
    before = [dict(record) for record in records]

    report = reconcile_and_summarize_legacy_catalog(records)

    assert report.total_records == 2
    assert report.status_counts == {
        "REVIEW_REQUIRED": 2,
        "IDENTITY_VERIFIED": 0,
        "READY_FOR_ONBOARDING": 0,
    }
    assert report.blocker_counts == {
        "authoritative vehicle identity is missing": 2,
    }
    assert report.ready_legacy_car_ids == ()
    assert report.blocked_legacy_car_ids == ("a", "b")
    assert records == before


def test_oem_evidence_queue_report_includes_package_blockers() -> None:
    record = {
        "id": "kia-seltos",
        "brand": "Kia",
        "model": "Seltos",
        "variant": "GTX(O)",
        "fuel": "Petrol",
        "transmission": "Automatic",
    }
    package = OemEvidencePackage(
        legacy_car_id="kia-seltos",
        identity=AuthoritativeVehicleIdentity.from_verified_source(
            brand_id="kia", brand_name="Kia", model_id="kia-seltos", model_name="Seltos",
            variant_id="kia-seltos-gtx-o", variant_name="GTX(O)", fuel_type="Petrol",
            transmission="Automatic", source="Kia India",
            source_url="https://www.kia.com/in/our-vehicles/seltos/showroom.html",
        ),
        evidence=AuthoritativeCatalogEvidence(
            pricing_verified=True, compatible_colors_verified=True,
            compatible_wheels_verified=True, compatible_interiors_verified=True,
            licensed_3d_asset_verified=True, asset_revision_published=True,
        ),
    )
    report = summarize_oem_evidence_queue([record], {"kia-seltos": package})
    assert report.status_counts == {
        "REVIEW_REQUIRED": 1,
        "IDENTITY_VERIFIED": 0,
        "READY_FOR_ONBOARDING": 0,
    }
    assert report.blocker_counts == {"3D asset evidence metadata is missing": 1}
