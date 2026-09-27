"""Tests for explicit OEM asset-to-variant identity binding."""

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


def _asset(asset_variant_id: str) -> OemAssetEvidence:
    return OemAssetEvidence(
        asset_id="kia-seltos-3d",
        revision_id="rev-001",
        asset_variant_id=asset_variant_id,
        provenance=AssetProvenance.OEM_AUTHORIZED,
        license_name="OEM production license",
        publisher="Kia India",
        checksum_sha256="a" * 64,
        file_size_bytes=1024,
        validation_passed=True,
        published=True,
    )


def test_cross_variant_asset_evidence_requires_review() -> None:
    package = OemEvidencePackage(
        legacy_car_id="kia-seltos",
        identity=_identity(),
        evidence=_evidence(),
        asset=_asset("kia-seltos-gtx-plus"),
    )

    status, blockers = validate_evidence_package(package)

    assert status is EvidencePackageStatus.REVIEW_REQUIRED
    assert "3D asset variant does not match authoritative variant" in blockers


def test_matching_asset_variant_can_remain_ready() -> None:
    package = OemEvidencePackage(
        legacy_car_id="kia-seltos",
        identity=_identity(),
        evidence=_evidence(),
        asset=_asset("kia-seltos-gtx-o"),
        authoritative_active_revision_id="rev-001",
    )

    assert validate_evidence_package(package) == (EvidencePackageStatus.READY, ())


def test_asset_variant_identity_is_required() -> None:
    with pytest.raises(ValueError):
        OemAssetEvidence(
            asset_id="kia-seltos-3d",
            revision_id="rev-001",
            provenance=AssetProvenance.OEM_AUTHORIZED,
            license_name="OEM production license",
            publisher="Kia India",
            checksum_sha256="a" * 64,
            file_size_bytes=1024,
            validation_passed=True,
            published=True,
        )
