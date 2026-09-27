from configurator_persistence import assess_saved_configuration_freshness


def test_saved_configuration_is_fresh_when_price_and_asset_match():
    assert assess_saved_configuration_freshness(
        {"price_snapshot": 1250000, "asset_id": "asset-1", "asset_version": "2.0"},
        {"estimated_on_road": 1250000},
        {"asset_id": "asset-1", "version": "2.0"},
    ) == (False, None)


def test_saved_configuration_is_stale_when_authoritative_price_changes():
    assert assess_saved_configuration_freshness(
        {"price_snapshot": 1250000, "asset_id": "asset-1", "asset_version": "2.0"},
        {"estimated_on_road": 1275000},
        {"asset_id": "asset-1", "version": "2.0"},
    ) == (True, "Authoritative configurator price has changed")


def test_saved_configuration_is_stale_when_published_asset_version_changes():
    assert assess_saved_configuration_freshness(
        {"price_snapshot": 1250000, "asset_id": "asset-1", "asset_version": "2.0"},
        {"estimated_on_road": 1250000},
        {"asset_id": "asset-1", "version": "3.0"},
    ) == (True, "Published verified configurator asset has changed")


def test_saved_configuration_is_stale_when_current_asset_is_missing():
    assert assess_saved_configuration_freshness(
        {"price_snapshot": 1250000, "asset_id": "asset-1", "asset_version": "2.0"},
        {"estimated_on_road": 1250000},
        None,
    ) == (True, "Published verified configurator asset is unavailable")

def test_saved_configuration_is_stale_when_active_asset_revision_changes():
    assert assess_saved_configuration_freshness(
        {"price_snapshot": 1250000, "asset_id": "asset-1", "asset_version": "2.0", "asset_revision_id": "rev-1"},
        {"estimated_on_road": 1250000},
        {"asset_id": "asset-1", "version": "2.0", "revision_id": "rev-2"},
    ) == (True, "Published verified configurator asset revision has changed")
