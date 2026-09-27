"""Production database authority checks for configurator onboarding."""

from __future__ import annotations

from typing import Optional


def assess_database_authority(
    configured_database_name: str,
    expected_database_name: Optional[str],
) -> dict[str, object]:
    """Require an explicitly configured expected database and exact name match."""
    expected = expected_database_name.strip() if isinstance(expected_database_name, str) else ""
    configured = configured_database_name.strip()

    if not expected:
        return {
            "ready": False,
            "reason": "expected production database name is not configured",
        }

    if configured != expected:
        return {
            "ready": False,
            "reason": "configured database does not match expected production database",
        }

    return {"ready": True, "reason": None}
