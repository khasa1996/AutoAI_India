"""Tests for the explicit read-only OEM evidence package contract."""

import pytest

from configurator_schemas import AssetProvenance
from configurator_catalog_reconciliation import (
    AuthoritativeCatalogEvidence,
    AuthoritativeVehicleIdentity,
)
from configurator_oem_evidence_package import (
    EvidencePackageStatus,
    OemAssetEvidence,
    OemEvidencePackage,
    validate_evidence_package,
)


def _identity() -> AuthoritativeVehicleIdentity:
    return AuthoritativeVehicleIdentity.from_verified_source(
        brand_id="kia",
        brand_name="Kia",
        model_id="kia-seltos",
        model_name="Seltos",
        variant_id="kia-seltos-gtx-o",
        variant_name="GTX(O)",
        fuel_type="Petrol",
        transmission="Automatic",
        source="Kia India",
        source_url="https://www.kia.com/in/our-vehicles/seltos/showroom.html",
    )


def _evidence() -> AuthoritativeCatalogEvidence:
    return AuthoritativeCatalogEvidence(
        pricing_verified=True,
        compatible_colors_verified=True,
        compatible_wheels_verified=True,
        compatible_interiors_verified=True,
        licensed_3d_asset_verified=True,
        asset_revision_published=True,
    )


def _asset() -> OemAssetEvidence:
    return OemAssetEvidence(
        asset_id="kia-seltos-gtx-o-3d",
        revision_id="rev-001",
        asset_variant_id="kia-seltos-gtx-o",
        provenance=AssetProvenance.OEM_AUTHORIZED,
        license_name="OEM production license",
        publisher="Kia India",
        checksum_sha256="a" * 64,
        file_size_bytes=1024,
        validation_passed=True,
        published=True,
    )


def test_asset_revision_must_match_authoritative_active_revision() -> None:
    package = OemEvidencePackage(
        legacy_car_id="kia-seltos-gtx-o",
        identity=_identity(),
        evidence=_evidence(),
        asset=_asset(),
        authoritative_active_revision_id="rev-authoritative",
    )

    status, blockers = validate_evidence_package(package)

    assert status is EvidencePackageStatus.REVIEW_REQUIRED
    assert blockers == ("3D asset revision does not match authoritative active revision",)


def test_complete_package_is_ready() -> None:
    package = OemEvidencePackage(
        legacy_car_id="kia-seltos-gtx-o",
        identity=_identity(),
        evidence=_evidence(),
        asset=_asset(),
        authoritative_active_revision_id="rev-001",
    )

    assert validate_evidence_package(package) == (EvidencePackageStatus.READY, ())
    assert package.status is EvidencePackageStatus.READY
    assert package.blockers == ()


def test_verified_identity_without_evidence_is_evidence_required() -> None:
    package = OemEvidencePackage(
        legacy_car_id="kia-seltos-gtx-o",
        identity=_identity(),
        evidence=AuthoritativeCatalogEvidence(),
    )

    status, blockers = validate_evidence_package(package)

    assert status is EvidencePackageStatus.EVIDENCE_REQUIRED
    assert "authoritative pricing is not verified" in blockers


def test_missing_asset_metadata_blocks_complete_asset_evidence() -> None:
    package = OemEvidencePackage(
        legacy_car_id="kia-seltos-gtx-o",
        identity=_identity(),
        evidence=_evidence(),
    )

    status, blockers = validate_evidence_package(package)

    assert status is EvidencePackageStatus.REVIEW_REQUIRED
    assert blockers == ("3D asset evidence metadata is missing",)


def test_invalid_checksum_is_rejected() -> None:
    with pytest.raises(ValueError, match="64-character hexadecimal"):
        OemAssetEvidence(
            asset_id="asset",
            revision_id="rev",
            provenance="OEM_AUTHORIZED",
            license_name="License",
            publisher="Publisher",
            checksum_sha256="not-a-checksum",
            file_size_bytes=1024,
        )


def test_asset_size_is_capped_at_200mb() -> None:
    with pytest.raises(ValueError):
        OemAssetEvidence(
            asset_id="asset",
            revision_id="rev",
            provenance="OEM_AUTHORIZED",
            license_name="License",
            publisher="Publisher",
            checksum_sha256="a" * 64,
            file_size_bytes=200 * 1024 * 1024 + 1,
        )
