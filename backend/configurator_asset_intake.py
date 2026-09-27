"""Production-safe intake validation for Ultra 3D configurator assets."""

from __future__ import annotations

import re
from enum import Enum
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

_MAX_ASSET_BYTES = 200 * 1024 * 1024
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class AssetIntakeProvenance(str, Enum):
    OEM_AUTHORIZED = "OEM_AUTHORIZED"
    AUTO_AI_LICENSED = "AUTO_AI_LICENSED"
    LICENSED_THIRD_PARTY = "LICENSED_THIRD_PARTY"
    AI_GENERATED_CONCEPT = "AI_GENERATED_CONCEPT"
    UNKNOWN = "UNKNOWN"


_PUBLISHABLE_PROVENANCE = {
    AssetIntakeProvenance.OEM_AUTHORIZED,
    AssetIntakeProvenance.AUTO_AI_LICENSED,
    AssetIntakeProvenance.LICENSED_THIRD_PARTY,
}


class ConfiguratorAssetIntakeRequest(BaseModel):
    """Evidence package required before a 3D asset can enter production intake."""

    asset_id: str = Field(..., min_length=2, max_length=100)
    variant_id: str = Field(..., min_length=1, max_length=100)
    model_id: str = Field(..., min_length=1, max_length=80)
    brand_id: str = Field(..., min_length=1, max_length=60)
    format: str = Field(..., pattern=r"^(glb|gltf)$")
    source_url: str = Field(..., min_length=1, max_length=2000)
    provenance: AssetIntakeProvenance = AssetIntakeProvenance.UNKNOWN
    license_name: str | None = Field(None, max_length=200)
    license_url: str | None = Field(None, max_length=500)
    publisher: str | None = Field(None, max_length=200)
    version: str = Field(..., min_length=1, max_length=30)
    file_size_bytes: int = Field(..., gt=0, le=_MAX_ASSET_BYTES)
    checksum_sha256: str = Field(..., min_length=64, max_length=64)
    storage_key: str | None = Field(None, max_length=500)
    storage_provider: str | None = Field(None, max_length=40)
    temporary: bool = False
    temporary_label: str | None = Field(None, max_length=100)

    @field_validator("source_url", "license_url")
    @classmethod
    def urls_must_be_https(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("https://"):
            raise ValueError("asset URLs must use HTTPS")
        return value

    @field_validator("source_url")
    @classmethod
    def source_url_must_be_model_format(cls, value: str) -> str:
        path = urlparse(value).path.lower()
        if not path.endswith((".glb", ".gltf")):
            raise ValueError("source_url must point to a .glb or .gltf asset")
        return value

    @field_validator("checksum_sha256")
    @classmethod
    def checksum_must_be_sha256(cls, value: str) -> str:
        if not _SHA256_PATTERN.fullmatch(value):
            raise ValueError("checksum_sha256 must be a 64-char hex string")
        return value.lower()

    @model_validator(mode="after")
    def temporary_assets_require_label(self) -> "ConfiguratorAssetIntakeRequest":
        if self.temporary and not self.temporary_label:
            raise ValueError("temporary assets require an explicit temporary_label")
        return self


class AssetIntakeValidationResult(BaseModel):
    valid: bool
    publishable: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def validate_asset_intake(
    request: ConfiguratorAssetIntakeRequest,
    expected_variant_id: str | None = None,
) -> AssetIntakeValidationResult:
    """Validate provenance and integrity evidence without persistence side effects."""
    errors: list[str] = []
    warnings: list[str] = []

    if expected_variant_id is not None and request.variant_id != expected_variant_id:
        errors.append("asset and expected variant identities do not match")

    if request.provenance not in _PUBLISHABLE_PROVENANCE:
        errors.append("asset provenance is not publishable")

    if not request.license_name or not request.publisher:
        errors.append("asset license evidence is incomplete")

    if request.file_size_bytes <= 0 or request.file_size_bytes > _MAX_ASSET_BYTES:
        errors.append("asset integrity evidence is invalid")
    if not _SHA256_PATTERN.fullmatch(request.checksum_sha256):
        errors.append("asset integrity evidence is invalid")

    if request.temporary:
        errors.append("temporary assets cannot be published to the production catalog")
        warnings.append(
            request.temporary_label
            or "temporary/non-OEM asset"
        )

    publishable = not errors
    return AssetIntakeValidationResult(
        valid=not errors,
        publishable=publishable,
        errors=errors,
        warnings=warnings,
    )
