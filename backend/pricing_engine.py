"""
Auto AI India — Pricing Engine
================================
Backend-authoritative pricing for vehicle configurations.

Design rules:
  - The frontend is NEVER the source of truth for pricing.
  - AI must NEVER invent prices.
  - City components are additive on top of ex-showroom.
  - All prices are integers in Indian Rupees (paise not used).
  - Unknown or unavailable selected components are rejected, not silently omitted.

Formula:
    base_ex_showroom
    + SUM(option price deltas)
    = subtotal_ex_showroom
    + rto
    + insurance_approx
    + tcs
    + other_charges
    - SUM(offer discounts)
    = estimated_on_road
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from configurator_city_pricing import validate_pricing_location
from configurator_schemas import (
    ConfigurationPriceRequest,
    ConfigurationPriceResponse,
    PriceComponent,
)

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_available_option(document: Optional[Dict[str, Any]], option_type: str, option_id: str) -> Dict[str, Any]:
    """Require a selected catalog option to exist and be available for pricing."""
    if not document or document.get("available", True) is not True:
        raise ValueError(f"{option_type} option '{option_id}' is not available")
    return document


async def calculate_configuration_price(
    request: ConfigurationPriceRequest,
    db: "AsyncIOMotorDatabase",
) -> ConfigurationPriceResponse:
    """Calculate the authoritative price for a vehicle configuration."""
    config = request.configuration
    variant_id = config.variant_id

    pricing_doc = await db.variant_pricing.find_one(
        {"variant_id": variant_id}, {"_id": 0}
    )

    if pricing_doc is None:
        raise ValueError("authoritative variant pricing is missing")

    if str(pricing_doc.get("verification_status", "unverified")).casefold() != "verified":
        raise ValueError("variant pricing verification is not complete")

    base_ex_showroom = pricing_doc.get("base_ex_showroom", 0)

    if request.city and not await validate_pricing_location(db, variant_id, request.city):
        raise ValueError(f"No verified pricing is available for city: {request.city}")

    option_deltas: List[PriceComponent] = []

    if config.paint_id:
        color_doc = _require_available_option(
            await db.variant_colors.find_one(
                {"color_id": config.paint_id, "variant_id": variant_id},
                {"_id": 0},
            ),
            "Paint",
            config.paint_id,
        )
        if color_doc.get("price_delta", 0) > 0:
            option_deltas.append(PriceComponent(
                name=color_doc.get("display_name", "Paint option"),
                amount=color_doc["price_delta"],
            ))

    if config.wheel_id:
        wheel_doc = _require_available_option(
            await db.variant_wheels.find_one(
                {"wheel_id": config.wheel_id, "variant_id": variant_id},
                {"_id": 0},
            ),
            "Wheel",
            config.wheel_id,
        )
        if wheel_doc.get("price_delta", 0) > 0:
            option_deltas.append(PriceComponent(
                name=wheel_doc.get("name", "Wheel option"),
                amount=wheel_doc["price_delta"],
            ))

    if config.interior_id:
        interior_doc = _require_available_option(
            await db.variant_interiors.find_one(
                {"interior_id": config.interior_id, "variant_id": variant_id},
                {"_id": 0},
            ),
            "Interior",
            config.interior_id,
        )
        if interior_doc.get("price_delta", 0) > 0:
            option_deltas.append(PriceComponent(
                name=interior_doc.get("name", "Interior option"),
                amount=interior_doc["price_delta"],
            ))

    if config.roof_id:
        roof_doc = _require_available_option(
            await db.configurator_options.find_one(
                {
                    "option_id": config.roof_id,
                    "variant_id": variant_id,
                    "option_type": "roof",
                },
                {"_id": 0},
            ),
            "Roof",
            config.roof_id,
        )
        if roof_doc.get("price_delta", 0) > 0:
            option_deltas.append(PriceComponent(
                name=roof_doc.get("display_name", "Roof option"),
                amount=roof_doc["price_delta"],
            ))

    for acc_id in config.accessory_ids:
        acc_doc = _require_available_option(
            await db.configurator_options.find_one(
                {
                    "option_id": acc_id,
                    "variant_id": variant_id,
                    "option_type": "accessory",
                },
                {"_id": 0},
            ),
            "Accessory",
            acc_id,
        )
        if acc_doc.get("price_delta", 0) > 0:
            option_deltas.append(PriceComponent(
                name=acc_doc.get("display_name", "Accessory"),
                amount=acc_doc["price_delta"],
            ))

    rto: Optional[int] = None
    insurance_approx: Optional[int] = None
    tcs: Optional[int] = None
    other_charges: Optional[int] = None

    if request.city and pricing_doc:
        city_pricing_list = pricing_doc.get("city_pricing", [])
        city_entry = next(
            (
                cp for cp in city_pricing_list
                if cp.get("city", "").strip().casefold() == request.city.strip().casefold()
                and str(cp.get("verification_status", "unverified")).casefold() == "verified"
            ),
            None,
        )
        if city_entry:
            rto = city_entry.get("rto")
            insurance_approx = city_entry.get("insurance_approx")
            tcs = city_entry.get("tcs")
            other_charges = city_entry.get("handling")

    offers_applied: List[PriceComponent] = []

    subtotal = base_ex_showroom + sum(c.amount for c in option_deltas)
    estimated_on_road = sum([
        subtotal,
        rto or 0,
        insurance_approx or 0,
        tcs or 0,
        other_charges or 0,
    ]) - sum(c.amount for c in offers_applied)

    return ConfigurationPriceResponse(
        variant_id=variant_id,
        city=request.city,
        base_ex_showroom=base_ex_showroom,
        option_deltas=option_deltas,
        rto=rto,
        insurance_approx=insurance_approx,
        tcs=tcs,
        other_charges=other_charges,
        offers_applied=offers_applied,
        estimated_on_road=max(estimated_on_road, 0),
        price_is_estimate=True,
        effective_date=_utcnow_iso(),
        source="auto_ai_india_pricing_engine_v1",
    )


async def validate_asset_url(url: str) -> Dict[str, Any]:
    """Validate a 3D asset URL structurally without downloading it."""
    from urllib.parse import urlparse

    errors: List[str] = []
    warnings: List[str] = []

    if not url:
        errors.append("URL is required")
        return {"valid": False, "errors": errors, "warnings": warnings}

    parsed = urlparse(url)

    if parsed.scheme != "https":
        errors.append("Asset URL must use HTTPS")
    if not parsed.netloc:
        errors.append("Asset URL must include a hostname")

    path = parsed.path.lower()
    if not any(path.endswith(ext) for ext in (".glb", ".gltf")):
        errors.append(
            "Asset URL must end with .glb or .gltf — "
            "image files, .jpg, .png, .mp4 etc. are not valid 3D assets"
        )

    if parsed.username or parsed.password:
        errors.append("Asset URL must not contain credentials")
    if parsed.fragment:
        warnings.append("Asset URL contains a fragment identifier — this may cause issues")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
