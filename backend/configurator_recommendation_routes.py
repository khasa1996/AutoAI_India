"""API routes for backend-authoritative multi-variant recommendations."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from motor.motor_asyncio import AsyncIOMotorDatabase

from configurator_recommendation_schemas import AIRecommendationRequest, AIRecommendationResponse
from configurator_recommendations import extract_recommendation_intent, rank_variant_recommendations


def _normalize_location(value: str | None) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _verified_city_price(pricing: Dict[str, Any], city: str | None, state: str | None) -> Optional[Dict[str, Any]]:
    """Return a verified city pricing record matching the requested city/state."""
    if not city:
        return None

    requested_city = _normalize_location(city)
    requested_state = _normalize_location(state)
    for entry in pricing.get("city_pricing", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("verification_status", "unverified")).casefold() != "verified":
            continue
        if _normalize_location(entry.get("city")) != requested_city:
            continue
        if requested_state and _normalize_location(entry.get("state")) != requested_state:
            continue
        return entry
    return None


def _candidate_price(pricing: Dict[str, Any], city: str | None = None, state: str | None = None) -> Optional[int]:
    if city:
        city_price = _verified_city_price(pricing, city, state)
        if city_price is None:
            return None
        for key in ("base_ex_showroom", "ex_showroom", "price"):
            value = city_price.get(key)
            if isinstance(value, (int, float)) and value >= 0:
                return int(value)
        return None

    if pricing.get("verification_status") not in {"verified", "VERIFIED"}:
        return None
    for key in ("base_ex_showroom", "ex_showroom", "price"):
        value = pricing.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            return int(value)
    return None


def _verified_pricing_by_variant(rows: list[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Keep only verified pricing records and resolve duplicate rows deterministically."""
    verified: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        variant_id = row.get("variant_id")
        if not variant_id:
            continue
        if str(row.get("verification_status", "unverified")).casefold() != "verified":
            continue
        key = str(variant_id)
        if key not in verified:
            verified[key] = row
    return verified


def make_configurator_recommendation_router(db: AsyncIOMotorDatabase) -> APIRouter:
    router = APIRouter(prefix="/api/v1/configurator", tags=["configurator-recommendations"])

    @router.post("/recommendations", response_model=AIRecommendationResponse)
    async def recommend_variants(request: AIRecommendationRequest) -> AIRecommendationResponse:
        variants = await db.variants.find({"active": True}, {"_id": 0}).to_list(500)
        if not variants:
            return AIRecommendationResponse(recommendations=[], explanation="No active vehicle variants are available for this request.", ai_assisted=False, valid=True)

        variant_ids = [str(item.get("variant_id")) for item in variants if item.get("variant_id")]
        pricing_rows = await db.variant_pricing.find({"variant_id": {"$in": variant_ids}}, {"_id": 0}).to_list(500)
        pricing_by_variant = _verified_pricing_by_variant(pricing_rows)

        candidates = []
        for variant in variants:
            variant_id = str(variant.get("variant_id"))
            pricing = pricing_by_variant.get(variant_id, {})
            candidate = dict(variant)
            price = _candidate_price(pricing, request.city, request.state)
            if price is not None:
                candidate["price"] = price
                candidate["pricing"] = pricing if not request.city else {
                    "variant_id": variant_id,
                    "city": request.city,
                    "state": request.state,
                    "ex_showroom": price,
                    "verification_status": "verified",
                }
            elif not request.city:
                candidate["pricing"] = {}
            else:
                # A requested location without verified pricing is not eligible
                # for a price-sensitive recommendation and must not fall back to
                # a generic or unverified price.
                continue
            candidates.append(candidate)

        if not candidates:
            return AIRecommendationResponse(
                recommendations=[],
                explanation="No active variants have verified pricing for the requested city/state.",
                ai_assisted=False,
                valid=True,
            )

        ai_intent = await extract_recommendation_intent(request.raw_request, candidates)
        ranking_request = request.model_dump()
        ranking_request["max_budget"] = request.max_budget if request.max_budget is not None else ai_intent["max_budget"]
        ranking_request["preferred_fuel"] = request.preferred_fuel or ai_intent["preferred_fuel"]
        ranking_request["preferred_segment"] = request.preferred_segment or ai_intent["preferred_segment"]
        ranking_request["required_features"] = request.required_features or ai_intent["required_features"]
        ranked = rank_variant_recommendations(candidates, ranking_request)
        by_id = {str(item.get("variant_id")): item for item in candidates}
        recommendations = []

        for item in ranked:
            candidate = by_id[item["variant_id"]]
            status = str(candidate.get("configurator_status", "COMING_SOON"))
            asset_id = candidate.get("configurator_asset_id")
            asset = None
            if asset_id:
                asset = await db.configurator_assets.find_one(
                    {"asset_id": asset_id, "variant_id": item["variant_id"], "published": True, "validation_passed": True},
                    {"_id": 0, "asset_id": 1, "variant_id": 1, "active_revision_id": 1, "revisions": 1, "version": 1},
                )
            configurator_available = False
            if asset is not None:
                try:
                    from configurator_asset_revision import resolve_authoritative_asset_revision

                    resolve_authoritative_asset_revision(asset, asset.get("revisions", []))
                    configurator_available = status == "AVAILABLE"
                except (TypeError, ValueError):
                    configurator_available = False
            vehicle = {key: candidate[key] for key in ("variant_id", "brand_id", "model_id", "name", "display_name", "slug", "body_type", "market_segment") if key in candidate}
            recommendations.append({
                **item,
                "availability_status": status,
                "configurator_available": configurator_available,
                "vehicle": vehicle,
                "pricing": candidate.get("pricing") or None,
                "tradeoff": "3D configurator is not currently available for this variant." if not configurator_available else None,
            })

        if not recommendations:
            explanation = "No eligible variants matched the explicit requirements. Try a wider budget or remove one strict filter."
        elif ai_intent["ai_assisted"]:
            explanation = "AI extracted the request preferences, then the backend deterministically ranked active catalog candidates. Pricing, availability and configurator readiness remain backend-authoritative."
        else:
            explanation = "Preferences were deterministically extracted, then the backend ranked active catalog candidates. Pricing, availability and configurator readiness remain backend-authoritative."

        return AIRecommendationResponse(recommendations=recommendations, explanation=explanation, ai_assisted=bool(ai_intent["ai_assisted"]), valid=True)

    return router
