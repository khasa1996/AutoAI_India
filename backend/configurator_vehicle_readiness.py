"""Production readiness checks for vehicle/configurator onboarding."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional

from configurator_asset_revision import resolve_authoritative_asset_revision

_PUBLISHABLE_PROVENANCE = {
    "OEM_AUTHORIZED",
    "AUTO_AI_LICENSED",
    "LICENSED_THIRD_PARTY",
}
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def _available_options(options: Optional[Iterable[Dict[str, Any]]]) -> list[Dict[str, Any]]:
    if not options:
        return []
    return [
        option
        for option in options
        if isinstance(option, dict) and option.get("available", True) is True
    ]


def assess_vehicle_configurator_readiness(
    vehicle: Optional[Dict[str, Any]],
    pricing: Optional[Dict[str, Any]],
    colors: Optional[Iterable[Dict[str, Any]]],
    wheels: Optional[Iterable[Dict[str, Any]]],
    interiors: Optional[Iterable[Dict[str, Any]]],
    asset: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return deterministic blockers for promoting a variant to live configurator use."""
    blockers: list[str] = []
    warnings: list[str] = []

    if not vehicle:
        blockers.append("vehicle variant is missing")
        return {"ready": False, "blockers": blockers, "warnings": warnings}

    variant_id = vehicle.get("variant_id")
    if not variant_id:
        blockers.append("vehicle variant_id is missing")
    if not vehicle.get("active", False):
        blockers.append("vehicle variant is inactive")
    if vehicle.get("verification_status") != "verified":
        blockers.append("vehicle verification is not complete")
    if vehicle.get("configurator_status") != "AVAILABLE":
        blockers.append("configurator status is not AVAILABLE")

    if pricing is None:
        blockers.append("authoritative variant pricing is missing")
    else:
        if pricing.get("variant_id") != variant_id:
            blockers.append("variant pricing identity does not match the vehicle")
        if not isinstance(pricing.get("base_ex_showroom"), (int, float)) or pricing.get("base_ex_showroom", 0) <= 0:
            blockers.append("authoritative variant pricing has no positive base ex-showroom price")
        if pricing.get("verification_status") != "verified":
            blockers.append("variant pricing verification is not complete")
        if not pricing.get("source"):
            blockers.append("authoritative variant pricing source is missing")

    option_groups = (
        ("color", colors),
        ("wheel", wheels),
        ("interior", interiors),
    )
    for label, options in option_groups:
        matching = [
            option for option in _available_options(options)
            if option.get("variant_id") == variant_id
        ]
        if not matching:
            blockers.append(f"no available {label} option for the vehicle")

    if asset is None:
        blockers.append("published verified configurator asset is missing")
    else:
        if asset.get("asset_id") != vehicle.get("configurator_asset_id"):
            blockers.append("configured asset identity does not match the variant")
        if asset.get("variant_id") != variant_id:
            blockers.append("configurator asset variant identity does not match the vehicle")
        if not asset.get("version"):
            blockers.append("configurator asset version is missing")
        if asset.get("published") is not True:
            blockers.append("configurator asset is not published")
        if asset.get("validation_passed") is not True:
            blockers.append("configurator asset has not passed validation")
        if asset.get("provenance") not in _PUBLISHABLE_PROVENANCE:
            blockers.append("configurator asset provenance is not publishable")
        if not asset.get("license_name") or not asset.get("publisher"):
            blockers.append("configurator asset license metadata is incomplete")

        checksum = asset.get("checksum_sha256")
        file_size = asset.get("file_size_bytes")
        if not isinstance(file_size, int) or file_size <= 0 or file_size > 200 * 1024 * 1024:
            blockers.append("configurator asset integrity evidence is incomplete")
        if not isinstance(checksum, str) or not _SHA256_PATTERN.fullmatch(checksum):
            if "configurator asset integrity evidence is incomplete" not in blockers:
                blockers.append("configurator asset integrity evidence is incomplete")

        try:
            active_revision = resolve_authoritative_asset_revision(
                asset,
                asset.get("revisions", []),
            )
        except (TypeError, ValueError):
            active_revision = None
            blockers.append("configurator asset active revision is not published or is invalid")
        else:
            if active_revision.checksum_sha256 != checksum:
                blockers.append("configurator asset checksum does not match active revision")

        if asset.get("storage_status") != "PUBLISHED":
            blockers.append("configurator asset storage publication state is not complete")

    if not vehicle.get("source") or not vehicle.get("source_url"):
        warnings.append("vehicle source traceability is incomplete")

    return {
        "ready": not blockers,
        "blockers": blockers,
        "warnings": warnings,
    }
