"""Read-only reconciliation reporting for the legacy configurator catalog.

This module consumes reconciliation results and produces a deterministic review
report. It never reads or writes MongoDB and never changes publication state.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from collections.abc import Iterable, Mapping

from configurator_catalog_reconciliation import (
    AuthoritativeCatalogEvidence,
    AuthoritativeVehicleIdentity,
    CatalogReconciliationResult,
    ReconciliationStatus,
)
from configurator_reconciliation_matrix import build_reconciliation_matrix
from configurator_oem_evidence_package import OemEvidencePackage
from configurator_oem_review_queue import build_oem_review_queue


@dataclass(frozen=True)
class ReconciliationReport:
    """Deterministic aggregate of a reconciliation matrix."""

    total_records: int
    status_counts: dict[str, int]
    blocker_counts: dict[str, int]
    ready_legacy_car_ids: tuple[str, ...]
    blocked_legacy_car_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable report without mutating report state."""
        return {
            "total_records": self.total_records,
            "status_counts": dict(self.status_counts),
            "blocker_counts": dict(self.blocker_counts),
            "ready_legacy_car_ids": list(self.ready_legacy_car_ids),
            "blocked_legacy_car_ids": list(self.blocked_legacy_car_ids),
        }


def summarize_reconciliation_matrix(
    results: Iterable[CatalogReconciliationResult],
) -> ReconciliationReport:
    """Aggregate reconciliation results into a deterministic review report."""

    materialized = tuple(results)
    status_counts = Counter(item.status.value for item in materialized)
    blocker_counts = Counter(
        blocker
        for item in materialized
        for blocker in item.blockers
    )

    ready_ids = tuple(
        sorted(
            item.legacy_car_id
            for item in materialized
            if item.status is ReconciliationStatus.READY_FOR_ONBOARDING
        )
    )
    blocked_ids = tuple(
        sorted(
            item.legacy_car_id
            for item in materialized
            if item.status is not ReconciliationStatus.READY_FOR_ONBOARDING
        )
    )

    return ReconciliationReport(
        total_records=len(materialized),
        status_counts={
            status.value: status_counts.get(status.value, 0)
            for status in ReconciliationStatus
        },
        blocker_counts=dict(sorted(blocker_counts.items())),
        ready_legacy_car_ids=ready_ids,
        blocked_legacy_car_ids=blocked_ids,
    )




def summarize_oem_evidence_queue(
    legacy_records: Iterable[Mapping[str, object]],
    evidence_packages: Mapping[str, OemEvidencePackage],
) -> ReconciliationReport:
    """Summarize the OEM evidence review queue without persistence."""

    items = build_oem_review_queue(
        legacy_records,
        evidence_packages=evidence_packages,
    )
    results = tuple(
        CatalogReconciliationResult(
            status=(
                ReconciliationStatus.READY_FOR_ONBOARDING
                if item.review_state == "READY"
                else ReconciliationStatus.IDENTITY_VERIFIED
                if item.review_state == "EVIDENCE_REQUIRED"
                else ReconciliationStatus.REVIEW_REQUIRED
            ),
            legacy_car_id=item.legacy_car_id,
            canonical_variant_id=item.canonical_variant_id,
            blockers=item.blockers,
        )
        for item in items
    )
    return summarize_reconciliation_matrix(results)


def reconcile_and_summarize_legacy_catalog(
    legacy_records: Iterable[Mapping[str, object]],
    identities: Mapping[str, AuthoritativeVehicleIdentity] | None = None,
    evidence: Mapping[str, AuthoritativeCatalogEvidence] | None = None,
) -> ReconciliationReport:
    """Build and summarize a legacy reconciliation matrix without persistence."""

    matrix = build_reconciliation_matrix(
        legacy_records,
        identities=identities,
        evidence=evidence,
    )
    return summarize_reconciliation_matrix(matrix)
