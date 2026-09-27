"""Auto AI India configurator API routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from configurator_runtime_capabilities import resolve_authoritative_asset_revision
from configurator_schemas import (
    AIConfiguratorIntent,
    AIConfiguratorResponse,
    ConfigurationPriceRequest,
    ConfigurationPriceResponse,
    ConfigurationValidationRequest,
    SavedConfigurationCreate,
    ValidationResult,
)
from configurator_ai import build_interaction_state, resolve_ai_selection
from configurator_persistence import revalidate_saved_configuration
from vehicle_schemas import BrandSummary, ConfiguratorStatus, ModelSummary, VariantDetail, VariantSummary
from pricing_engine import calculate_configuration_price, validate_asset_url
from rules_engine import get_available_options_for_variant, validate_configuration


async def _require_catalog_variant(
    db: AsyncIOMotorDatabase,
    variant_id: str,
) -> Dict[str, object]:
    """Require a canonical configurator variant; never fall back to legacy cars."""
    variant = await db.variants.find_one({"variant_id": variant_id}, {"_id": 0})
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return variant


async def _resolve_optional_user_phone(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """Resolve the application's canonical optional auth dependency lazily."""
    from server import optional_user_phone

    return await optional_user_phone(authorization)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_saved_configuration_document(
    request: SavedConfigurationCreate,
    owner_phone: str,
    server_price_snapshot: Dict[str, object],
    server_asset: Optional[Dict[str, object]],
    config_id: str,
    share_token: str,
    now: str,
) -> Dict[str, object]:
    """Build a persisted snapshot from server-authoritative values."""
    configuration = request.configuration.model_dump()
    stale_reason = None if server_asset else "Published verified configurator asset is unavailable"
    estimated_on_road = int(server_price_snapshot.get("estimated_on_road", 0))
    return {
        "config_id": config_id,
        "owner_phone": owner_phone,
        "share_token": share_token,
        "configuration": configuration,
        "city": request.city,
        "price_snapshot": estimated_on_road,
        "price_breakdown": server_price_snapshot,
        "asset_id": server_asset.get("asset_id") if server_asset else None,
        "asset_version": server_asset.get("version") if server_asset else None,
        "asset_revision_id": server_asset.get("revision_id") if server_asset else None,
        "stale": bool(stale_reason),
        "stale_reason": stale_reason,
        "created_at": now,
        "updated_at": now,
    }


async def resolve_saved_configuration_asset(
    db: AsyncIOMotorDatabase,
    variant_id: str,
    requested_asset_id: Optional[str],
) -> Optional[Dict[str, object]]:
    """Resolve only the current published verified asset assigned to a variant."""
    variant = await db.variants.find_one(
        {"variant_id": variant_id},
        {"_id": 0, "configurator_asset_id": 1},
    )
    assigned_asset_id = variant.get("configurator_asset_id") if variant else None
    if not assigned_asset_id:
        return None
    asset_id = assigned_asset_id
    if not asset_id:
        return None
    asset = await db.configurator_assets.find_one(
        {
            "asset_id": asset_id,
            "variant_id": variant_id,
            "published": True,
            "validation_passed": True,
        },
        {"_id": 0},
    )
    if not asset:
        return None
    try:
        revision = resolve_authoritative_asset_revision(
            asset,
            asset.get("revisions", []),
        )
    except (TypeError, ValueError):
        return None
    return {
        "asset_id": asset["asset_id"],
        "revision_id": revision.revision_id,
        "version": revision.version,
        "checksum_sha256": revision.checksum_sha256,
    }


def make_configurator_router(
    db: AsyncIOMotorDatabase,
    optional_user_phone: Optional[Callable[..., Awaitable[Optional[str]]]] = None,
) -> APIRouter:
    """Build the versioned configurator router with database/auth dependencies."""
    auth_dependency = optional_user_phone or _resolve_optional_user_phone
    router = APIRouter(prefix="/api/v1", tags=["configurator"])

    @router.get("/brands", response_model=List[BrandSummary])
    async def list_brands(active_only: bool = Query(True)):
        query: Dict[str, object] = {"active_in_india": True} if active_only else {}
        return await db.brands.find(query, {"_id": 0}).sort("name", 1).to_list(200)

    @router.get("/brands/{brand_id}")
    async def get_brand(brand_id: str):
        doc = await db.brands.find_one({"brand_id": brand_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Brand not found")
        return doc

    @router.get("/models", response_model=List[ModelSummary])
    async def list_models(
        brand_id: Optional[str] = Query(None, max_length=60),
        body_type: Optional[str] = Query(None, max_length=40),
        segment: Optional[str] = Query(None, max_length=40),
        include_discontinued: bool = Query(False),
    ):
        query: Dict[str, object] = {}
        if brand_id:
            query["brand_id"] = brand_id
        if body_type:
            query["body_type"] = body_type
        if segment:
            query["market_segment"] = segment
        if not include_discontinued:
            query["discontinued"] = False
        return await db.models.find(query, {"_id": 0}).sort("name", 1).to_list(500)

    @router.get("/models/{model_id}")
    async def get_model(model_id: str):
        doc = await db.models.find_one({"model_id": model_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Model not found")
        return doc

    @router.get("/variants", response_model=List[VariantSummary])
    async def list_variants(
        model_id: Optional[str] = Query(None, max_length=80),
        brand_id: Optional[str] = Query(None, max_length=60),
        fuel: Optional[str] = Query(None, max_length=40),
        active_only: bool = Query(True),
    ):
        query: Dict[str, object] = {}
        if model_id:
            query["model_id"] = model_id
        if brand_id:
            query["brand_id"] = brand_id
        if fuel:
            query["specs.fuel_type"] = fuel
        if active_only:
            query["active"] = True
        return await db.variants.find(query, {"_id": 0}).to_list(500)

    @router.get("/variants/{variant_id}", response_model=VariantDetail)
    async def get_variant(variant_id: str):
        doc = await db.variants.find_one({"variant_id": variant_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Variant not found")
        pricing = await db.variant_pricing.find_one({"variant_id": variant_id}, {"_id": 0})
        colors = await db.variant_colors.find({"variant_id": variant_id}, {"_id": 0}).to_list(30)
        wheels = await db.variant_wheels.find({"variant_id": variant_id}, {"_id": 0}).to_list(20)
        interiors = await db.variant_interiors.find({"variant_id": variant_id}, {"_id": 0}).to_list(15)
        return {**doc, "pricing": pricing, "colors": colors, "wheels": wheels, "interiors": interiors}

    @router.get("/configurator/{variant_id}/availability")
    async def get_configurator_availability(variant_id: str):
        variant = await _require_catalog_variant(db, variant_id)
        pricing = await db.variant_pricing.find_one({"variant_id": variant_id}, {"_id": 0})
        colors = await db.variant_colors.find({"variant_id": variant_id}, {"_id": 0}).to_list(30)
        wheels = await db.variant_wheels.find({"variant_id": variant_id}, {"_id": 0}).to_list(20)
        interiors = await db.variant_interiors.find({"variant_id": variant_id}, {"_id": 0}).to_list(15)

        asset = None
        asset_id = variant.get("configurator_asset_id")
        if asset_id:
            asset = await db.configurator_assets.find_one(
                {
                    "asset_id": asset_id,
                    "variant_id": variant_id,
                    "published": True,
                    "validation_passed": True,
                },
                {"_id": 0},
            )

        from configurator_vehicle_readiness import assess_vehicle_configurator_readiness

        readiness = assess_vehicle_configurator_readiness(
            variant,
            pricing,
            colors,
            wheels,
            interiors,
            asset,
        )
        configured_status = variant.get(
            "configurator_status",
            ConfiguratorStatus.COMING_SOON,
        )
        status = (
            ConfiguratorStatus.AVAILABLE
            if readiness["ready"]
            else (
                ConfiguratorStatus.COMING_SOON
                if configured_status == ConfiguratorStatus.AVAILABLE
                else configured_status
            )
        )
        return {
            "variant_id": variant_id,
            "configurator_status": status,
            "available": bool(readiness["ready"]),
            "asset_id": asset_id if readiness["ready"] else None,
            "message": _status_message(status),
            "blockers": readiness["blockers"],
            "warnings": readiness["warnings"],
        }

    @router.get("/configurator/{variant_id}/asset")
    async def get_configurator_asset(variant_id: str):
        from configurator_runtime_capabilities import build_runtime_capability_contract

        contract = await build_runtime_capability_contract(db, variant_id)
        if not contract["ready"]:
            return {
                "variant_id": variant_id,
                "available": False,
                "message": "3D asset is not ready for production runtime",
                "readiness_blockers": contract["blockers"],
            }

        variant = await db.variants.find_one(
            {"variant_id": variant_id},
            {"_id": 0, "configurator_status": 1, "configurator_asset_id": 1},
        )
        if not variant or variant.get("configurator_status") != ConfiguratorStatus.AVAILABLE:
            return {
                "variant_id": variant_id,
                "available": False,
                "message": _status_message(
                    variant.get("configurator_status", ConfiguratorStatus.COMING_SOON)
                    if variant else ConfiguratorStatus.COMING_SOON
                ),
            }
        asset_id = variant.get("configurator_asset_id")
        if not asset_id:
            return {"variant_id": variant_id, "available": False, "message": "3D asset not assigned"}
        asset = await db.configurator_assets.find_one(
            {
                "asset_id": asset_id,
                "variant_id": variant_id,
                "published": True,
                "validation_passed": True,
            },
            {"_id": 0},
        )
        if not asset:
            return {
                "variant_id": variant_id,
                "available": False,
                "message": "3D asset is not yet published or has not passed validation",
            }
        try:
            revision = resolve_authoritative_asset_revision(
                asset,
                asset.get("revisions", []),
            )
        except (TypeError, ValueError):
            return {
                "variant_id": variant_id,
                "available": False,
                "message": "3D asset active revision is not published or is invalid",
            }
        return {
            "variant_id": variant_id,
            "available": True,
            "asset": {
                "asset_id": asset["asset_id"],
                "url": asset.get("cdn_url") or asset["url"],
                "format": asset["format"],
                "revision_id": revision.revision_id,
                "version": revision.version,
                "lod_level": asset["lod_level"],
                "supported_interactions": asset.get("supported_interactions", []),
                "paint_material_names": asset.get("paint_material_names", []),
                "interior_material_names": asset.get("interior_material_names", []),
                "interior_material_mappings": asset.get("interior_material_mappings", {}),
                "wheel_mesh_names": asset.get("wheel_mesh_names", {}),
                "option_mesh_names": asset.get("option_mesh_names", {}),
                "camera_preset_names": asset.get("camera_preset_names", []),
                "interaction_animation_names": asset.get("interaction_animation_names", {}),
            },
        }

    @router.get("/configurator/{variant_id}/options")
    async def get_configurator_options(variant_id: str):
        await _require_catalog_variant(db, variant_id)
        options = await get_available_options_for_variant(variant_id, db)
        return {"variant_id": variant_id, **options}

    @router.get("/configurator/{variant_id}/rules")
    async def get_configurator_rules(variant_id: str):
        rules = await db.configurator_rules.find(
            {"active": True, "$or": [{"variant_id": variant_id}, {"variant_id": None}]},
            {"_id": 0},
        ).to_list(200)
        return {"variant_id": variant_id, "rules": rules}

    @router.post("/configurator/validate", response_model=ValidationResult)
    async def validate_config(request: ConfigurationValidationRequest):
        await _require_catalog_variant(db, request.configuration.variant_id)
        return await validate_configuration(request, db)

    @router.post("/configurator/price", response_model=ConfigurationPriceResponse)
    async def calculate_price(request: ConfigurationPriceRequest):
        await _require_catalog_variant(db, request.configuration.variant_id)
        validation = await validate_configuration(
            ConfigurationValidationRequest(configuration=request.configuration), db
        )
        if not validation.valid:
            raise HTTPException(
                status_code=422,
                detail={"message": "Invalid configuration", "errors": validation.errors},
            )
        try:
            return await calculate_configuration_price(request, db)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @router.post("/configurator/configurations")
    async def save_configuration(
        request: SavedConfigurationCreate,
        auth_phone: Optional[str] = Depends(auth_dependency),
    ):
        """Persist only a server-validated, server-priced configuration."""
        if not auth_phone:
            raise HTTPException(status_code=401, detail="Authentication required")

        validation = await validate_configuration(
            ConfigurationValidationRequest(configuration=request.configuration.purchasable), db
        )
        if not validation.valid:
            raise HTTPException(
                status_code=422,
                detail={"message": "Invalid configuration", "errors": validation.errors},
            )

        price_request = ConfigurationPriceRequest(
            configuration=request.configuration.purchasable,
            city=request.city,
        )
        try:
            server_price = await calculate_configuration_price(price_request, db)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

        server_asset = await resolve_saved_configuration_asset(
            db,
            request.configuration.purchasable.variant_id,
            request.asset_id,
        )

        config_id = str(uuid.uuid4())
        share_token = uuid.uuid4().hex
        now = _utcnow_iso()
        doc = build_saved_configuration_document(
            request=request,
            owner_phone=auth_phone,
            server_price_snapshot=server_price.model_dump(mode="json"),
            server_asset=server_asset,
            config_id=config_id,
            share_token=share_token,
            now=now,
        )
        await db.configurations.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/configurator/configurations/{config_id}")
    async def get_configuration(
        config_id: str,
        auth_phone: Optional[str] = Depends(auth_dependency),
    ):
        """Load a private configuration by owner or a public share token."""
        shared_doc = await db.configurations.find_one({"share_token": config_id}, {"_id": 0})
        if shared_doc:
            return _public_configuration_response(shared_doc)

        doc = await db.configurations.find_one({"config_id": config_id}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Configuration not found")
        if not auth_phone:
            raise HTTPException(status_code=401, detail="Authentication required")
        if doc.get("owner_phone") != auth_phone:
            raise HTTPException(status_code=403, detail="Configuration access denied")

        async def current_price_resolver(
            configuration: Dict[str, object],
            city: Optional[str],
        ) -> Dict[str, object]:
            price_request = ConfigurationPriceRequest(configuration=configuration, city=city)
            price = await calculate_configuration_price(price_request, db)
            return price.model_dump(mode="json")

        async def current_asset_resolver(
            variant_id: str,
            requested_asset_id: Optional[str],
        ) -> Optional[Dict[str, object]]:
            return await resolve_saved_configuration_asset(db, variant_id, requested_asset_id)

        try:
            return await revalidate_saved_configuration(
                doc,
                current_price_resolver,
                current_asset_resolver,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @router.post("/configurator/ai", response_model=AIConfiguratorResponse)
    async def ai_configurator(intent: AIConfiguratorIntent):
        """Resolve natural-language intent through the catalog, rules engine and price engine."""
        try:
            configuration, explanation, unavailable = await resolve_ai_selection(intent, db)
        except ValueError as exc:
            return AIConfiguratorResponse(
                configuration=None,
                price=None,
                explanation=str(exc),
                unavailable_options=[],
                valid=False,
            )

        validation = await validate_configuration(
            ConfigurationValidationRequest(configuration=configuration), db
        )
        if not validation.valid:
            return AIConfiguratorResponse(
                configuration=None,
                price=None,
                explanation="AI selection was rejected by the configurator rules engine: " + "; ".join(validation.errors),
                unavailable_options=unavailable,
                valid=False,
            )

        try:
            price = await calculate_configuration_price(
                ConfigurationPriceRequest(configuration=configuration), db
            )
        except ValueError as exc:
            return AIConfiguratorResponse(
                configuration=None,
                price=None,
                explanation=str(exc),
                unavailable_options=unavailable,
                valid=False,
            )

        if intent.max_budget is not None and price.estimated_on_road > intent.max_budget:
            explanation = (
                f"The best resolved configuration is estimated at ₹{price.estimated_on_road:,}, "
                f"which exceeds the requested ₹{intent.max_budget:,} budget."
            )
            return AIConfiguratorResponse(
                configuration=None,
                price=price,
                explanation=explanation,
                unavailable_options=unavailable,
                valid=False,
            )

        configuration_state = {
            "purchasable": configuration.model_dump(),
            "interaction": build_interaction_state(intent).model_dump(),
        }
        return AIConfiguratorResponse(
            configuration=configuration_state,
            price=price,
            explanation=explanation,
            unavailable_options=unavailable,
            valid=True,
        )

    @router.post("/configurator/assets/validate-url")
    async def validate_asset_url_endpoint(payload: Dict[str, str]):
        return await validate_asset_url(payload.get("url", ""))

    return router


def _public_configuration_response(doc: Dict[str, object]) -> Dict[str, object]:
    """Return only fields intentionally exposed through a share link."""
    public_fields = (
        "config_id",
        "configuration",
        "city",
        "price_snapshot",
        "price_breakdown",
        "asset_id",
        "asset_version",
        "asset_revision_id",
        "stale",
        "stale_reason",
        "created_at",
        "updated_at",
    )
    return {key: doc[key] for key in public_fields if key in doc}


def _status_message(status: ConfiguratorStatus) -> str:
    messages = {
        ConfiguratorStatus.AVAILABLE: "3D Configurator Available",
        ConfiguratorStatus.COMING_SOON: "3D Configurator Coming Soon",
        ConfiguratorStatus.UNAVAILABLE: "3D Configurator Unavailable",
        ConfiguratorStatus.UNDER_REVIEW: "3D Configurator Under Review",
        ConfiguratorStatus.DISABLED: "3D Configurator Disabled",
    }
    return messages.get(status, "3D Configurator Status Unknown")
