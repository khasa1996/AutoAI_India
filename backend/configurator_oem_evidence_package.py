"""Explicit, read-only OEM evidence package contract for configurator onboarding.

This module records evidence metadata supplied by reviewers. It does not infer
vehicle identity, fetch OEM data, or persist production catalog records.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from configurator_schemas import AssetProvenance

from configurator_catalog_reconciliation import (
    AuthoritativeCatalogEvidence,
    AuthoritativeVehicleIdentity,
)


class EvidencePackageStatus(str, Enum):
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    READY = "READY"


class OemAssetEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_id: str = Field(..., min_length=1, max_length=100)
    revision_id: str = Field(..., min_length=1, max_length=120)
    asset_variant_id: str = Field(..., min_length=1, max_length=120)
    provenance: AssetProvenance
    license_name: str = Field(..., min_length=1, max_length=200)
    publisher: str = Field(..., min_length=1, max_length=200)
    checksum_sha256: str = Field(..., min_length=1, max_length=128)
    file_size_bytes: int = Field(..., gt=0, le=200 * 1024 * 1024)
    validation_passed: bool = False
    published: bool = False

    @field_validator("checksum_sha256")
    @classmethod
    def checksum_must_be_sha256(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            raise ValueError(
                "checksum_sha256 must be a 64-character hexadecimal SHA-256"
            )
        return value.lower()


class OemEvidencePackage(BaseModel):
    model_config = ConfigDict(frozen=True)

    legacy_car_id: str = Field(..., min_length=1, max_length=100)
    identity: AuthoritativeVehicleIdentity
    evidence: AuthoritativeCatalogEvidence
    asset: OemAssetEvidence | None = None
    authoritative_active_revision_id: str | None = Field(None, min_length=1, max_length=120)

    def evaluate(self) -> tuple[EvidencePackageStatus, tuple[str, ...]]:
        blockers: list[str] = []

        if self.identity.verification_status != "verified":
            blockers.append("authoritative vehicle identity is not verified")
        if not self.identity.source_url.startswith("https://"):
            blockers.append("authoritative source_url must use HTTPS")

        checks = (
            ("authoritative pricing is not verified", self.evidence.pricing_verified),
            (
                "compatible colors are not verified",
                self.evidence.compatible_colors_verified,
            ),
            (
                "compatible wheels are not verified",
                self.evidence.compatible_wheels_verified,
            ),
            (
                "compatible interiors are not verified",
                self.evidence.compatible_interiors_verified,
            ),
        )
        blockers.extend(message for message, passed in checks if not passed)

        if not self.evidence.licensed_3d_asset_verified:
            blockers.append("licensed 3D asset is not verified")
        elif self.asset is None:
            blockers.append("3D asset evidence metadata is missing")
        else:
            if self.authoritative_active_revision_id is None:
                blockers.append("authoritative active asset revision is not specified")
            elif self.asset.revision_id != self.authoritative_active_revision_id:
                blockers.append("3D asset revision does not match authoritative active revision")
            if self.asset.asset_variant_id != self.identity.variant_id:
                blockers.append("3D asset variant does not match authoritative variant")
            if self.asset.provenance not in {
                AssetProvenance.OEM_AUTHORIZED,
                AssetProvenance.AUTO_AI_LICENSED,
                AssetProvenance.LICENSED_THIRD_PARTY,
            }:
                blockers.append("3D asset provenance is not production-authorized")
            if not self.asset.validation_passed:
                blockers.append("3D asset validation has not passed")
            if not self.asset.published:
                blockers.append("3D asset revision is not published")

        if not self.evidence.asset_revision_published:
            blockers.append("active 3D asset revision is not published")

        if blockers:
            review_blockers = {
                "authoritative vehicle identity is not verified",
                "authoritative source_url must use HTTPS",
                "3D asset evidence metadata is missing",
                "authoritative active asset revision is not specified",
                "3D asset revision does not match authoritative active revision",
                "3D asset variant does not match authoritative variant",
                "3D asset provenance is not production-authorized",
            }
            has_review_blocker = any(
                message in review_blockers for message in blockers
            )
            return (
                EvidencePackageStatus.REVIEW_REQUIRED
                if has_review_blocker
                else EvidencePackageStatus.EVIDENCE_REQUIRED,
                tuple(blockers),
            )

        return EvidencePackageStatus.READY, ()

    @property
    def status(self) -> EvidencePackageStatus:
        return self.evaluate()[0]

    @property
    def blockers(self) -> tuple[str, ...]:
        return self.evaluate()[1]


def validate_evidence_package(
    package: OemEvidencePackage,
) -> tuple[EvidencePackageStatus, tuple[str, ...]]:
    return package.evaluate()
