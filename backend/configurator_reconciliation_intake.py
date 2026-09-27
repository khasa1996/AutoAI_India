"""Explicit authoritative mapping contracts for configurator reconciliation.

This module defines the intake boundary for reviewed OEM/authoritative mappings.
It contains no database access and cannot publish catalog records.
"""

from __future__ import annotations

from collections.abc import Iterable
from pydantic import BaseModel, ConfigDict, Field

from configurator_catalog_reconciliation import (
    AuthoritativeCatalogEvidence,
    AuthoritativeVehicleIdentity,
)


class AuthoritativeReconciliationMapping(BaseModel):
    """One explicitly supplied legacy-to-authoritative reconciliation mapping."""

    model_config = ConfigDict(frozen=True)

    legacy_car_id: str = Field(..., min_length=1, max_length=100)
    identity: AuthoritativeVehicleIdentity
    evidence: AuthoritativeCatalogEvidence


def validate_reconciliation_mappings(
    mappings: Iterable[AuthoritativeReconciliationMapping],
) -> tuple[AuthoritativeReconciliationMapping, ...]:
    """Validate uniqueness before mappings are consumed by reconciliation."""

    records = tuple(mappings)
    if not records:
        raise ValueError("at least one authoritative reconciliation mapping is required")

    seen_legacy_ids: set[str] = set()
    seen_variant_ids: set[str] = set()

    for mapping in records:
        legacy_id = mapping.legacy_car_id.strip().casefold()
        variant_id = mapping.identity.variant_id.strip().casefold()

        if not legacy_id:
            raise ValueError("legacy_car_id must not be blank")
        if not variant_id:
            raise ValueError("authoritative variant_id must not be blank")
        if mapping.identity.verification_status != "verified":
            raise ValueError(
                f"authoritative vehicle identity is not verified: {mapping.identity.variant_id}"
            )
        if not mapping.identity.source_url.startswith("https://"):
            raise ValueError(
                f"authoritative source_url must use HTTPS: {mapping.identity.variant_id}"
            )
        if legacy_id in seen_legacy_ids:
            raise ValueError(f"duplicate legacy_car_id: {mapping.legacy_car_id}")
        if variant_id in seen_variant_ids:
            raise ValueError(f"duplicate authoritative variant_id: {mapping.identity.variant_id}")

        seen_legacy_ids.add(legacy_id)
        seen_variant_ids.add(variant_id)

    return records
