from onboarding_manifest_validator import validate_onboarding_manifest


def _valid_manifest():
    variant_id = "demo-variant"
    return {
        "variant": {
            "brand_id": "demo-brand",
            "model_id": "demo-model",
            "variant_id": variant_id,
            "verification_status": "verified",
        },
        "pricing": {
            "variant_id": variant_id,
            "source": "verified-source",
            "source_url": "https://example.com/pricing",
            "verification_status": "verified",
        },
        "options": {
            "colors": [{"variant_id": variant_id, "available": True}],
            "wheels": [{"variant_id": variant_id, "available": True}],
            "interiors": [{"variant_id": variant_id, "available": True}],
        },
        "asset": {
            "asset_id": "asset-1",
            "variant_id": variant_id,
            "version": "1.0.0",
            "published": True,
            "validation_passed": True,
            "provenance": "OEM_AUTHORIZED",
            "license_name": "Production license",
            "publisher": "OEM",
            "checksum_sha256": "a" * 64,
            "file_size_bytes": 1024,
        },
    }


def test_valid_manifest_passes_without_writes():
    result = validate_onboarding_manifest(_valid_manifest())
    assert result == {"ready": True, "blockers": []}


def test_manifest_blocks_missing_variant_identity():
    manifest = _valid_manifest()
    manifest["variant"]["variant_id"] = ""
    result = validate_onboarding_manifest(manifest)
    assert result["ready"] is False
    assert "variant variant_id is missing" in result["blockers"]


def test_manifest_blocks_wrong_asset_variant():
    manifest = _valid_manifest()
    manifest["asset"]["variant_id"] = "other-variant"
    result = validate_onboarding_manifest(manifest)
    assert result["ready"] is False
    assert "asset variant identity does not match" in result["blockers"]
