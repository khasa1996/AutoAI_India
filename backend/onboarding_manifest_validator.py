"""Additional production onboarding validation helpers.

These helpers validate an external, source-backed onboarding manifest before any
production catalog write is attempted. They are intentionally side-effect free.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable

REQUIRED_IDENTITY_FIELDS = ("brand_id", "model_id", "variant_id")
REQUIRED_SOURCE_FIELDS = ("source", "source_url")
REQUIRED_ASSET_FIELDS = (
    "asset_id",
    "variant_id",
    "version",
    "published",
    "validation_passed",
    "provenance",
    "license_name",
    "publisher",
    "checksum_sha256",
    "file_size_bytes",
)


def validate_onboarding_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a source-backed onboarding manifest without performing writes."""
    blockers: list[str] = []

    variant = manifest.get("variant") or {}
    pricing = manifest.get("pricing") or {}
    options = manifest.get("options") or {}
    asset = manifest.get("asset") or {}

    for field in REQUIRED_IDENTITY_FIELDS:
        if not variant.get(field):
            blockers.append(f"variant {field} is missing")

    if variant.get("verification_status") != "verified":
        blockers.append("variant verification is not complete")

    for field in REQUIRED_SOURCE_FIELDS:
        if not pricing.get(field):
            blockers.append(f"pricing {field} is missing")

    if pricing.get("variant_id") != variant.get("variant_id"):
        blockers.append("pricing variant identity does not match")
    if pricing.get("verification_status") != "verified":
        blockers.append("pricing verification is not complete")

    for group in ("colors", "wheels", "interiors"):
        rows: Iterable[Dict[str, Any]] = options.get(group) or []
        if not any(
            isinstance(row, dict)
            and row.get("variant_id") == variant.get("variant_id")
            and row.get("available", True) is True
            for row in rows
        ):
            blockers.append(f"no available {group[:-1]} option is present for the exact variant")

    for field in REQUIRED_ASSET_FIELDS:
        if field not in asset or asset.get(field) in (None, ""):
            blockers.append(f"asset {field} is missing")
    if asset.get("variant_id") != variant.get("variant_id"):
        blockers.append("asset variant identity does not match")

    return {"ready": not blockers, "blockers": blockers}
