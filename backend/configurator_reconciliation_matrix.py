"""Deterministic review-matrix builder for legacy configurator migration.

The matrix is a review artifact only. It never writes to MongoDB and does not
claim that legacy vehicle data is current OEM data.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from configurator_catalog_reconciliation import (
    AuthoritativeCatalogEvidence,
    AuthoritativeVehicleIdentity,
    CatalogReconciliationResult,
    reconcile_legacy_vehicle,
)


def build_reconciliation_matrix(
    legacy_records: Iterable[Mapping[str, object]],
    identities: Mapping[str, AuthoritativeVehicleIdentity] | None = None,
    evidence: Mapping[str, AuthoritativeCatalogEvidence] | None = None,
) -> list[CatalogReconciliationResult]:
    """Build a deterministic, non-persistent review matrix keyed by legacy id.

    Missing identity/evidence deliberately remains blocked. Input records and
    supplied mappings are never mutated.
    """

    identity_by_legacy_id = dict(identities or {})
    evidence_by_legacy_id = dict(evidence or {})
    results: list[CatalogReconciliationResult] = []

    for legacy in legacy_records:
        legacy_id = str(legacy.get("id", "")).strip().casefold()
        if not legacy_id:
            raise ValueError("legacy vehicle id is required")

        results.append(
            reconcile_legacy_vehicle(
                legacy,
                identity_by_legacy_id.get(legacy_id),
                evidence_by_legacy_id.get(legacy_id),
            )
        )

    return results
