"""Safe preparation contract for production configurator onboarding."""

from __future__ import annotations

from pydantic import BaseModel, Field

from configurator_database_authority import assess_database_authority
from configurator_onboarding_contract import (
    ConfiguratorOnboardingRecordSet,
    validate_onboarding_record_set,
)
from configurator_vehicle_catalog_manifest import (
    ConfiguratorVehicleCatalogManifest,
    validate_catalog_manifest,
)


class ConfiguratorOnboardingPreparation(BaseModel):
    """Non-persistent onboarding decision."""

    ready: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    write_allowed: bool = False
    variant_id: str | None = None


def prepare_configurator_onboarding(
    manifest: ConfiguratorVehicleCatalogManifest,
    records: ConfiguratorOnboardingRecordSet,
    configured_database_name: str,
    expected_database_name: str | None,
) -> ConfiguratorOnboardingPreparation:
    """Validate an onboarding package without performing any database writes."""
    database = assess_database_authority(
        configured_database_name,
        expected_database_name,
    )
    if not database["ready"]:
        return ConfiguratorOnboardingPreparation(
            ready=False,
            errors=[str(database["reason"])],
            write_allowed=False,
            variant_id=manifest.variant_id,
        )

    if records.vehicle.get("variant_id") != manifest.variant_id:
        return ConfiguratorOnboardingPreparation(
            ready=False,
            errors=["manifest and runtime variant identities do not match"],
            write_allowed=False,
            variant_id=manifest.variant_id,
        )

    if records.vehicle.get("model_id") != manifest.model_id:
        return ConfiguratorOnboardingPreparation(
            ready=False,
            errors=["manifest and runtime model identities do not match"],
            write_allowed=False,
            variant_id=manifest.variant_id,
        )

    if records.vehicle.get("brand_id") != manifest.brand_id:
        return ConfiguratorOnboardingPreparation(
            ready=False,
            errors=["manifest and runtime brand identities do not match"],
            write_allowed=False,
            variant_id=manifest.variant_id,
        )

    validate_catalog_manifest(manifest)
    validation = validate_onboarding_record_set(records)

    return ConfiguratorOnboardingPreparation(
        ready=validation.valid,
        errors=validation.errors,
        warnings=validation.warnings,
        write_allowed=False,
        variant_id=manifest.variant_id,
    )
