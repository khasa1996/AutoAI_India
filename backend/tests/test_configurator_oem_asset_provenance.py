"""Tests for production provenance gating in OEM evidence packages."""

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


def _asset(provenance: AssetProvenance) -> OemAssetEvidence:
    return OemAssetEvidence(
        asset_id="kia-seltos-gtx-o-3d",
        revision_id="rev-001",
        asset_variant_id="kia-seltos-gtx-o",
        provenance=provenance,
        license_name="OEM production license",
        publisher="Kia India",
        checksum_sha256="a" * 64,
        file_size_bytes=1024,
        validation_passed=True,
        published=True,
    )


@pytest.mark.parametrize(
    "provenance",
    [AssetProvenance.AI_GENERATED_CONCEPT, AssetProvenance.UNKNOWN],
)
def test_non_production_provenance_requires_review(
    provenance: AssetProvenance,
) -> None:
    package = OemEvidencePackage(
        legacy_car_id="kia-seltos-gtx-o",
        identity=_identity(),
        evidence=_evidence(),
        asset=_asset(provenance),
        authoritative_active_revision_id="rev-001",
    )

    status, blockers = validate_evidence_package(package)

    assert status is EvidencePackageStatus.REVIEW_REQUIRED
    assert "3D asset provenance is not production-authorized" in blockers
