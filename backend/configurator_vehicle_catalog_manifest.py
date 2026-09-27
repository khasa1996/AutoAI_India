"""Production-safe vehicle and variant catalog manifest contracts."""

from __future__ import annotations

from enum import Enum
from typing import Sequence

from pydantic import BaseModel, Field, field_validator


class VehicleVerificationStatus(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"


class ConfiguratorCatalogStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    COMING_SOON = "COMING_SOON"
    UNAVAILABLE = "UNAVAILABLE"


class ConfiguratorVehicleCatalogManifest(BaseModel):
    """Canonical identity and publication metadata for one real vehicle variant."""

    brand_id: str = Field(..., min_length=1, max_length=60)
    brand_name: str = Field(..., min_length=1, max_length=120)
    model_id: str = Field(..., min_length=1, max_length=80)
    model_name: str = Field(..., min_length=1, max_length=150)
    variant_id: str = Field(..., min_length=1, max_length=100)
    variant_name: str = Field(..., min_length=1, max_length=150)
    fuel_type: str = Field(..., min_length=1, max_length=40)
    transmission: str = Field(..., min_length=1, max_length=60)
    verification_status: VehicleVerificationStatus = VehicleVerificationStatus.UNVERIFIED
    active: bool = True
    configurator_status: ConfiguratorCatalogStatus = ConfiguratorCatalogStatus.COMING_SOON
    source: str = Field(..., min_length=1, max_length=100)
    source_url: str = Field(..., min_length=1, max_length=500)
    legacy_car_id: str | None = Field(None, max_length=100)

    @field_validator("source_url")
    @classmethod
    def source_url_must_be_https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("source_url must use HTTPS")
        return value


def validate_catalog_manifest(
    manifest: ConfiguratorVehicleCatalogManifest
    | Sequence[ConfiguratorVehicleCatalogManifest],
) -> ConfiguratorVehicleCatalogManifest | list[ConfiguratorVehicleCatalogManifest]:
    """Validate verified, canonical manifest records without database side effects."""

    records = [manifest] if isinstance(manifest, ConfiguratorVehicleCatalogManifest) else list(manifest)
    if not records:
        raise ValueError("catalog manifest must contain at least one variant")

    seen_variant_ids: set[str] = set()
    for record in records:
        if record.legacy_car_id:
            raise ValueError("legacy car records cannot be used as configurator variants")
        if record.verification_status is not VehicleVerificationStatus.VERIFIED:
            raise ValueError(f"vehicle verification is not complete for {record.variant_id}")
        if not record.active:
            raise ValueError(f"vehicle variant is inactive: {record.variant_id}")
        if record.configurator_status is not ConfiguratorCatalogStatus.AVAILABLE:
            raise ValueError(f"configurator status must be AVAILABLE for {record.variant_id}")
        if record.variant_id in seen_variant_ids:
            raise ValueError(f"duplicate variant_id: {record.variant_id}")
        seen_variant_ids.add(record.variant_id)

    return manifest if isinstance(manifest, ConfiguratorVehicleCatalogManifest) else records
