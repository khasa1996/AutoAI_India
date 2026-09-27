"""Side-effect-free contract for production configurator catalog onboarding."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from configurator_vehicle_readiness import assess_vehicle_configurator_readiness


class ConfiguratorOnboardingRecordSet(BaseModel):
    """In-memory catalog records required to validate one production variant."""

    model_config = ConfigDict(validate_assignment=True)

    vehicle: dict[str, Any]
    pricing: dict[str, Any] | None = None
    colors: list[dict[str, Any]] = Field(default_factory=list)
    wheels: list[dict[str, Any]] = Field(default_factory=list)
    interiors: list[dict[str, Any]] = Field(default_factory=list)
    asset: dict[str, Any] | None = None


class OnboardingValidationResult(BaseModel):
    """Deterministic validation result with no persistence side effects."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def validate_onboarding_record_set(
    records: ConfiguratorOnboardingRecordSet,
) -> OnboardingValidationResult:
    """Validate onboarding records using the existing readiness source of truth."""
    readiness = assess_vehicle_configurator_readiness(
        records.vehicle,
        records.pricing,
        records.colors,
        records.wheels,
        records.interiors,
        records.asset,
    )

    return OnboardingValidationResult(
        valid=bool(readiness["ready"]),
        errors=list(readiness["blockers"]),
        warnings=list(readiness["warnings"]),
    )
