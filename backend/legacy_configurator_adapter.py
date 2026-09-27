"""Pure adapter from legacy cars records to canonical configurator onboarding candidates.

Legacy cars are input evidence only. This adapter never marks a record verified,
never promotes it to AVAILABLE, and never performs persistence.
"""

from __future__ import annotations

import re
from typing import Any, Dict


def _slug(value: str) -> str:
    normalized_value = value.strip().lower().replace("+", " plus ")
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized_value).strip("-")
    if not normalized:
        raise ValueError("cannot build canonical identifier from empty value")
    return normalized


def _normalize_fuel(value: Any) -> str:
    text = str(value or "").strip()
    aliases = {
        "petrol": "Petrol",
        "diesel": "Diesel",
        "electric": "Electric",
        "ev": "Electric",
        "cng": "CNG",
        "lpg": "LPG",
        "hybrid": "Petrol Hybrid",
        "petrol hybrid": "Petrol Hybrid",
        "diesel hybrid": "Diesel Hybrid",
    }
    return aliases.get(text.lower(), text)


def _normalize_transmission(value: Any) -> str:
    text = str(value or "").strip()
    aliases = {
        "manual": "Manual",
        "automatic": "Automatic",
        "amt": "AMT",
        "cvt": "CVT",
        "dct": "DCT",
        "imt": "IMT",
    }
    return aliases.get(text.lower(), text)


def legacy_car_to_canonical_candidate(car: Dict[str, Any]) -> Dict[str, Any]:
    """Convert one legacy cars document into a non-publishable canonical candidate.

    The returned candidate is intentionally marked unverified/COMING_SOON.
    It is suitable for human review and migration tooling, not production
    configurator publication.
    """
    required = ("id", "brand", "model", "variant", "fuel", "transmission")
    missing = [field for field in required if not str(car.get(field) or "").strip()]
    if missing:
        raise ValueError(f"legacy car is missing required fields: {', '.join(missing)}")

    brand = str(car["brand"]).strip()
    model = str(car["model"]).strip()
    variant = str(car["variant"]).strip()
    legacy_id = str(car["id"]).strip()

    brand_id = _slug(brand)
    model_id = f"{brand_id}-{_slug(model)}"
    variant_id = f"{model_id}-{_slug(variant)}"

    return {
        "brand_id": brand_id,
        "brand_name": brand,
        "model_id": model_id,
        "model_name": model,
        "variant_id": variant_id,
        "variant_name": variant,
        "fuel_type": _normalize_fuel(car["fuel"]),
        "transmission": _normalize_transmission(car["transmission"]),
        "verification_status": "unverified",
        "active": True,
        "configurator_status": "COMING_SOON",
        "source": "legacy_cars_collection",
        "source_url": "",
        "legacy_car_id": legacy_id,
        "migration_status": "REVIEW_REQUIRED",
    }


def legacy_cars_to_canonical_candidates(
    cars: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    """Convert legacy cars deterministically without mutating input records."""
    return [legacy_car_to_canonical_candidate(car) for car in cars]
