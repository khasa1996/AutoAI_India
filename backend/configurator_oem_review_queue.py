"""Structured, read-only OEM evidence review queue for configurator onboarding.

This module turns the reconciliation matrix into review items. It does not
infer OEM mappings, persist records, or change publication state.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from configurator_oem_evidence_package import EvidencePackageStatus, OemEvidencePackage
from configurator_catalog_reconciliation import (
    AuthoritativeCatalogEvidence,
    AuthoritativeVehicleIdentity,
    ReconciliationStatus,
)
from configurator_reconciliation_matrix import build_reconciliation_matrix


@dataclass(frozen=True)
class OemEvidenceReviewItem:
    """One deterministic review item for a legacy vehicle."""

    legacy_car_id: str
    legacy_brand: str
    legacy_model: str
    legacy_variant: str
    legacy_fuel: str
    legacy_transmission: str
    status: ReconciliationStatus
    canonical_variant_id: str | None
    canonical_brand: str | None
    canonical_model: str | None
    canonical_variant: str | None
    authoritative_source: str | None
    authoritative_source_url: str | None
    model_year: int | None
    effective_from: date | None
    effective_to: date | None
    pricing_verified: bool
    compatible_colors_verified: bool
    compatible_wheels_verified: bool
    compatible_interiors_verified: bool
    licensed_3d_asset_verified: bool
    asset_revision_published: bool
    blockers: tuple[str, ...]
    evidence_package_status: EvidencePackageStatus | None = None
    evidence_package_blockers: tuple[str, ...] = ()

    @property
    def review_state(self) -> str:
        """Return a stable workflow state without changing reconciliation status."""
        if self.status is ReconciliationStatus.REVIEW_REQUIRED:
            return "REVIEW_REQUIRED"
        if self.evidence_package_status is EvidencePackageStatus.REVIEW_REQUIRED:
            return "REVIEW_REQUIRED"
        if self.evidence_package_status is EvidencePackageStatus.EVIDENCE_REQUIRED:
            return "EVIDENCE_REQUIRED"
        if self.status is ReconciliationStatus.READY_FOR_ONBOARDING:
            return "READY"
        if self.status is ReconciliationStatus.IDENTITY_VERIFIED:
            return "EVIDENCE_REQUIRED"
        return "REVIEW_REQUIRED"


def build_oem_review_queue(
    legacy_records: Iterable[Mapping[str, object]],
    identities: Mapping[str, AuthoritativeVehicleIdentity] | None = None,
    evidence: Mapping[str, AuthoritativeCatalogEvidence] | None = None,
    evidence_packages: Mapping[str, OemEvidencePackage] | None = None,
) -> tuple[OemEvidenceReviewItem, ...]:
    """Build deterministic review items without persistence or inference.

    When evidence_packages are supplied, each package is the explicit source
    for that vehicle identity and evidence. A package whose internal legacy
    ID does not match its mapping key is review-blocked.
    """

    identity_by_legacy_id = dict(identities or {})
    evidence_by_legacy_id = dict(evidence or {})
    evidence_package_by_legacy_id = dict(evidence_packages or {})
    materialized_records = tuple(dict(record) for record in legacy_records)
    package_identity_by_legacy_id = {
        legacy_id: package.identity
        for legacy_id, package in evidence_package_by_legacy_id.items()
        if package.legacy_car_id == legacy_id
    }
    package_evidence_by_legacy_id = {
        legacy_id: package.evidence
        for legacy_id, package in evidence_package_by_legacy_id.items()
        if package.legacy_car_id == legacy_id
    }
    effective_identity_by_legacy_id = {**identity_by_legacy_id, **package_identity_by_legacy_id}
    effective_evidence_by_legacy_id = {**evidence_by_legacy_id, **package_evidence_by_legacy_id}
    matrix = build_reconciliation_matrix(
        materialized_records,
        identities=effective_identity_by_legacy_id,
        evidence=effective_evidence_by_legacy_id,
    )
    records_by_id = {
        str(record.get("id", "")).strip().casefold(): record
        for record in materialized_records
    }

    items: list[OemEvidenceReviewItem] = []
    for result in matrix:
        legacy_id = result.legacy_car_id
        legacy = records_by_id[legacy_id]
        package = evidence_package_by_legacy_id.get(legacy_id)
        identity = package.identity if package else effective_identity_by_legacy_id.get(legacy_id)
        item_evidence = package.evidence if package else effective_evidence_by_legacy_id.get(legacy_id)
        package_status = package.status if package else None
        package_blockers = package.blockers if package else ()
        queue_blockers = list(result.blockers)
        if package is None:
            mismatched_package = next(
                (candidate for candidate in evidence_package_by_legacy_id.values()
                 if candidate.legacy_car_id == legacy_id),
                None,
            )
            if mismatched_package is not None:
                queue_blockers.append("evidence package legacy_car_id does not match queue key")
        queue_blockers.extend(package_blockers)
        queue_blockers = list(dict.fromkeys(queue_blockers))
        items.append(
            OemEvidenceReviewItem(
                legacy_car_id=legacy_id,
                legacy_brand=str(legacy.get("brand", "")),
                legacy_model=str(legacy.get("model", "")),
                legacy_variant=str(legacy.get("variant", "")),
                legacy_fuel=str(legacy.get("fuel", "")),
                legacy_transmission=str(legacy.get("transmission", "")),
                status=result.status,
                canonical_variant_id=result.canonical_variant_id,
                canonical_brand=identity.brand_name if identity else None,
                canonical_model=identity.model_name if identity else None,
                canonical_variant=identity.variant_name if identity else None,
                authoritative_source=identity.source if identity else None,
                authoritative_source_url=identity.source_url if identity else None,
                model_year=identity.model_year if identity else None,
                effective_from=identity.effective_from if identity else None,
                effective_to=identity.effective_to if identity else None,
                pricing_verified=item_evidence.pricing_verified if item_evidence else False,
                compatible_colors_verified=item_evidence.compatible_colors_verified if item_evidence else False,
                compatible_wheels_verified=item_evidence.compatible_wheels_verified if item_evidence else False,
                compatible_interiors_verified=item_evidence.compatible_interiors_verified if item_evidence else False,
                licensed_3d_asset_verified=item_evidence.licensed_3d_asset_verified if item_evidence else False,
                asset_revision_published=item_evidence.asset_revision_published if item_evidence else False,
                blockers=tuple(queue_blockers),
                evidence_package_status=package_status,
                evidence_package_blockers=package_blockers,
            )
        )

    return tuple(sorted(items, key=lambda item: item.legacy_car_id))


def summarize_oem_review_queue(
    items: Iterable[OemEvidenceReviewItem],
) -> dict[str, object]:
    """Return a compact deterministic queue summary."""

    materialized = tuple(items)
    state_counts = {
        "REVIEW_REQUIRED": sum(item.review_state == "REVIEW_REQUIRED" for item in materialized),
        "EVIDENCE_REQUIRED": sum(item.review_state == "EVIDENCE_REQUIRED" for item in materialized),
        "READY": sum(item.review_state == "READY" for item in materialized),
    }
    return {
        "total_items": len(materialized),
        "review_state_counts": state_counts,
        "legacy_car_ids": [
            item.legacy_car_id
            for item in sorted(materialized, key=lambda item: item.legacy_car_id)
        ],
    }
