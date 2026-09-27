from configurator_vehicle_readiness import assess_vehicle_configurator_readiness

def test_non_available_configurator_status_blocks_readiness():
    vehicle = {
        "variant_id": "v1", "active": True, "verification_status": "verified",
        "configurator_status": "COMING_SOON", "configurator_asset_id": "a1",
    }
    pricing = {
        "variant_id": "v1", "base_ex_showroom": 1000000,
        "source": "verified-source", "verification_status": "verified",
    }
    options = ([{"variant_id": "v1", "available": True}],) * 3
    asset = {
        "asset_id": "a1", "variant_id": "v1", "version": "1",
        "published": True, "validation_passed": True,
        "provenance": "AUTO_AI_LICENSED", "license_name": "L",
        "publisher": "P", "checksum_sha256": "a" * 64,
        "file_size_bytes": 1024, "storage_status": "PUBLISHED",
    }
    result = assess_vehicle_configurator_readiness(
        vehicle, pricing, *options, asset
    )
    assert result["ready"] is False
    assert "configurator status is not AVAILABLE" in result["blockers"]
