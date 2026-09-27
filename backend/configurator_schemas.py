"""Auto AI India — Configurator catalog identity contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from configurator_asset_revision import ConfiguratorAssetRevision


class AssetProvenance(str, Enum):
    OEM_AUTHORIZED = "OEM_AUTHORIZED"
    AUTO_AI_LICENSED = "AUTO_AI_LICENSED"
    LICENSED_THIRD_PARTY = "LICENSED_THIRD_PARTY"
    AI_GENERATED_CONCEPT = "AI_GENERATED_CONCEPT"
    UNKNOWN = "UNKNOWN"


_PUBLISHABLE_PROVENANCE = {
    AssetProvenance.OEM_AUTHORIZED,
    AssetProvenance.AUTO_AI_LICENSED,
    AssetProvenance.LICENSED_THIRD_PARTY,
}
_VALID_ASSET_EXTENSIONS = (".glb", ".gltf")
_MAX_ASSET_BYTES = 200 * 1024 * 1024


class AssetLODLevel(str, Enum):
    LOD0 = "LOD0"
    LOD1 = "LOD1"
    LOD2 = "LOD2"
    LOD3 = "LOD3"


class ConfiguratorAssetCreate(BaseModel):
    asset_id: str = Field(..., min_length=2, max_length=100)
    variant_id: str = Field(..., min_length=1, max_length=100)
    model_id: str = Field(..., min_length=1, max_length=80)
    brand_id: str = Field(..., min_length=1, max_length=60)
    format: str = Field(..., pattern=r"^(glb|gltf)$")
    url: str = Field(..., max_length=2000)
    cdn_url: Optional[str] = Field(None, max_length=2000)
    storage_key: Optional[str] = Field(None, max_length=500)
    storage_provider: Optional[str] = Field(None, max_length=40)
    storage_status: Optional[str] = Field(None, max_length=30)
    active_revision_id: Optional[str] = Field(None, max_length=120)
    revisions: List[ConfiguratorAssetRevision] = Field(default_factory=list)
    file_size_bytes: Optional[int] = Field(None, ge=0, le=_MAX_ASSET_BYTES)
    checksum_sha256: Optional[str] = Field(None, max_length=64)
    version: str = Field(..., min_length=1, max_length=30)
    lod_level: AssetLODLevel = AssetLODLevel.LOD0
    provenance: AssetProvenance = AssetProvenance.UNKNOWN
    license_name: Optional[str] = Field(None, max_length=200)
    license_url: Optional[str] = Field(None, max_length=500)
    publisher: Optional[str] = Field(None, max_length=200)
    supported_interactions: List[str] = Field(default_factory=list)
    paint_material_names: List[str] = Field(default_factory=list)
    interior_material_names: List[str] = Field(default_factory=list)
    interior_material_mappings: Dict[str, List[str]] = Field(default_factory=dict)
    wheel_mesh_names: Dict[str, str] = Field(default_factory=dict)
    option_mesh_names: Dict[str, List[str]] = Field(default_factory=dict)
    camera_preset_names: List[str] = Field(default_factory=list)
    interaction_animation_names: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    published: bool = False
    validation_passed: bool = False
    admin_reviewed: bool = False
    review_notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("url", "cdn_url")
    @classmethod
    def url_must_be_https(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.startswith("https://"):
            raise ValueError("Asset URL must use HTTPS")
        return v

    @field_validator("url")
    @classmethod
    def url_must_be_glb_gltf(cls, v: str) -> str:
        from urllib.parse import urlparse

        path = urlparse(v).path.lower()
        if not any(path.endswith(ext) for ext in _VALID_ASSET_EXTENSIONS):
            raise ValueError(f"Asset URL must end with one of {_VALID_ASSET_EXTENSIONS}")
        return v

    @field_validator("checksum_sha256")
    @classmethod
    def checksum_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        import re

        if not re.match(r"^[0-9a-f]{64}$", v.lower()):
            raise ValueError("checksum_sha256 must be a 64-char hex string")
        return v.lower()

    def is_publishable(self) -> bool:
        return (
            self.provenance in _PUBLISHABLE_PROVENANCE
            and self.validation_passed
            and self.admin_reviewed
            and bool(self.license_name)
            and bool(self.publisher)
        )


class ConfiguratorAsset(ConfiguratorAssetCreate):
    created_at: str
    updated_at: str


class ConfiguratorOptionType(str, Enum):
    PAINT = "paint"
    WHEEL = "wheel"
    INTERIOR = "interior"
    ROOF = "roof"
    ACCESSORY = "accessory"
    TRIM = "trim"


class ConfiguratorOption(BaseModel):
    """A purchasable option whose identity is bound to one vehicle variant."""

    option_id: str = Field(..., min_length=1, max_length=100)
    option_type: ConfiguratorOptionType
    variant_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=150)
    display_name: str = Field(..., min_length=1, max_length=150)
    price_delta: int = Field(0, ge=0)
    available: bool = True
    reference_id: str = Field(..., min_length=1, max_length=100)
    preview_color_hex: Optional[str] = Field(None, max_length=10)
    preview_image_url: Optional[str] = Field(None, max_length=500)


def validate_catalog_options(
    requested_variant_id: str,
    options: List[ConfiguratorOption],
) -> List[ConfiguratorOption]:
    """Validate that every catalog option belongs to the requested variant."""

    if not requested_variant_id:
        raise ValueError("requested variant_id must not be empty")

    mismatched = next(
        (option for option in options if option.variant_id != requested_variant_id),
        None,
    )
    if mismatched is not None:
        raise ValueError(
            f"Configurator option {mismatched.option_id} does not match "
            f"requested variant {requested_variant_id}"
        )
    return options


class RuleEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE = "require"
    EXCLUDE = "exclude"


class RuleConditionType(str, Enum):
    VARIANT_IS = "variant_is"
    OPTION_SELECTED = "option_selected"
    FUEL_TYPE = "fuel_type"
    MARKET_SEGMENT = "market_segment"
    DATE_BEFORE = "date_before"
    DATE_AFTER = "date_after"


class RuleCondition(BaseModel):
    condition_type: RuleConditionType
    value: Any = Field(..., description="The value to match against")


class ConfiguratorRule(BaseModel):
    rule_id: str = Field(..., max_length=100)
    variant_id: Optional[str] = Field(None, max_length=100)
    model_id: Optional[str] = Field(None, max_length=80)
    target_option_type: ConfiguratorOptionType
    target_option_id: str = Field(..., max_length=100)
    effect: RuleEffect
    conditions: List[RuleCondition] = Field(default_factory=list)
    explanation: Optional[str] = Field(None, max_length=500)
    active: bool = True
    priority: int = Field(0, ge=0)


class DoorState(BaseModel):
    front_left: bool = False
    front_right: bool = False
    rear_left: bool = False
    rear_right: bool = False


class LightingState(BaseModel):
    headlights: bool = False
    drl: bool = False
    taillights: bool = False
    fog_lights: bool = False
    left_indicator: bool = False
    right_indicator: bool = False
    hazard: bool = False
    interior: bool = False


class InteractionState(BaseModel):
    doors: DoorState = Field(default_factory=DoorState)
    hood_open: bool = False
    boot_open: bool = False
    frunk_open: bool = False
    sunroof_open: bool = False
    lighting: LightingState = Field(default_factory=LightingState)
    camera_preset: Optional[str] = Field(None, max_length=40)


class PurchasableConfiguration(BaseModel):
    variant_id: str = Field(..., max_length=100)
    paint_id: Optional[str] = Field(None, max_length=80)
    wheel_id: Optional[str] = Field(None, max_length=80)
    interior_id: Optional[str] = Field(None, max_length=80)
    roof_id: Optional[str] = Field(None, max_length=80)
    accessory_ids: List[str] = Field(default_factory=list)

    @field_validator("accessory_ids")
    @classmethod
    def max_accessories(cls, v: List[str]) -> List[str]:
        if len(v) > 30:
            raise ValueError("Maximum 30 accessories per configuration")
        return v


class ConfigurationState(BaseModel):
    purchasable: PurchasableConfiguration
    interaction: InteractionState = Field(default_factory=InteractionState)


class SavedConfigurationCreate(BaseModel):
    configuration: ConfigurationState
    city: Optional[str] = Field(None, max_length=80)
    price_snapshot: Optional[int] = Field(
        None,
        ge=0,
        description="Client snapshot retained for request compatibility; server recalculates before persistence",
    )
    asset_id: Optional[str] = Field(None, max_length=100)
    asset_version: Optional[str] = Field(None, max_length=30)
    asset_revision_id: Optional[str] = Field(None, max_length=120)


class SavedConfiguration(SavedConfigurationCreate):
    config_id: str
    owner_phone: Optional[str] = None
    share_token: Optional[str] = Field(None, max_length=64)
    price_breakdown: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str
    stale: bool = False
    stale_reason: Optional[str] = Field(None, max_length=500)


class PriceComponent(BaseModel):
    name: str = Field(..., max_length=80)
    amount: int = Field(..., ge=0)
    description: Optional[str] = Field(None, max_length=200)


class ConfigurationPriceRequest(BaseModel):
    configuration: PurchasableConfiguration
    city: Optional[str] = Field(None, max_length=80)
    state: Optional[str] = Field(None, max_length=80)
    offer_codes: List[str] = Field(default_factory=list, max_length=10)


class ConfigurationPriceResponse(BaseModel):
    variant_id: str
    city: Optional[str] = None
    base_ex_showroom: int
    option_deltas: List[PriceComponent] = Field(default_factory=list)
    total_options: int = 0
    subtotal_ex_showroom: int = 0
    rto: Optional[int] = None
    insurance_approx: Optional[int] = None
    tcs: Optional[int] = None
    other_charges: Optional[int] = None
    offers_applied: List[PriceComponent] = Field(default_factory=list)
    total_discount: int = 0
    estimated_on_road: int
    price_is_estimate: bool = True
    effective_date: str
    source: Optional[str] = None

    @model_validator(mode="after")
    def compute_totals(self) -> "ConfigurationPriceResponse":
        self.total_options = sum(c.amount for c in self.option_deltas)
        self.subtotal_ex_showroom = self.base_ex_showroom + self.total_options
        self.total_discount = sum(c.amount for c in self.offers_applied)
        return self


class ValidationResult(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    rules_applied: List[Dict[str, Any]] = Field(default_factory=list)


class ConfigurationValidationRequest(BaseModel):
    configuration: PurchasableConfiguration


class AIConfiguratorIntent(BaseModel):
    variant_id: str = Field(..., max_length=100)
    raw_request: str = Field(..., max_length=2000)
    preferred_segment: Optional[str] = Field(None, max_length=60)
    max_budget: Optional[int] = Field(None, ge=0)
    preferred_fuel: Optional[str] = Field(None, max_length=40)
    preferred_color_description: Optional[str] = Field(None, max_length=200)
    preferred_interior_description: Optional[str] = Field(None, max_length=200)
    open_hood: Optional[bool] = None
    open_doors: Optional[bool] = None
    open_boot: Optional[bool] = None
    open_sunroof: Optional[bool] = None
    lights_on: Optional[bool] = None
    camera_preset: Optional[str] = Field(None, max_length=40)


class AIConfiguratorResponse(BaseModel):
    configuration: Optional[ConfigurationState] = None
    price: Optional[ConfigurationPriceResponse] = None
    explanation: str = Field(..., max_length=2000)
    unavailable_options: List[Dict[str, str]] = Field(default_factory=list)
    valid: bool
