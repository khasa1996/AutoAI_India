from configurator_production_diagnostics import assess_production_configurator_diagnostics


def test_diagnostics_fail_closed_when_database_authority_is_unknown():
    result = assess_production_configurator_diagnostics(
        configured_database_name="autoai",
        expected_database_name=None,
        variant_count=0,
        pricing_count=0,
        asset_count=0,
    )
    assert result == {
        "ready": False,
        "database": {
            "ready": False,
            "reason": "expected production database name is not configured",
        },
        "catalog": {
            "variants": 0,
            "verified_pricing": 0,
            "published_assets": 0,
        },
    }


def test_diagnostics_reports_authoritative_database_without_claiming_catalog_readiness():
    result = assess_production_configurator_diagnostics(
        configured_database_name="autoai",
        expected_database_name="autoai",
        variant_count=106,
        pricing_count=0,
        asset_count=0,
    )
    assert result == {
        "ready": False,
        "database": {"ready": True, "reason": None},
        "catalog": {
            "variants": 106,
            "verified_pricing": 0,
            "published_assets": 0,
        },
    }


def test_diagnostics_is_ready_only_when_database_and_all_catalog_inputs_exist():
    result = assess_production_configurator_diagnostics(
        configured_database_name="autoai",
        expected_database_name="autoai",
        variant_count=1,
        pricing_count=1,
        asset_count=1,
    )
    assert result["ready"] is True
