from types import SimpleNamespace

from configurator_routes import build_saved_configuration_document


def test_saved_document_uses_server_price_and_preserves_interaction_state():
    request = SimpleNamespace(
        configuration=SimpleNamespace(
            model_dump=lambda: {
                "purchasable": {"variant_id": "v1", "paint_id": "red"},
                "interaction": {"hood_open": True, "camera_preset": "interior"},
            }
        ),
        city="Delhi",
        price_snapshot=1,
        asset_id="asset-client",
        asset_version="client-version",
    )

    document = build_saved_configuration_document(
        request=request,
        owner_phone="9876543210",
        server_price_snapshot={"estimated_on_road": 456789, "effective_date": "2026-09-11T00:00:00+00:00"},
        server_asset={"asset_id": "asset-server", "version": "2.0", "revision_id": "rev-7"},
        config_id="cfg-1",
        share_token="share-1",
        now="2026-09-11T00:00:00+00:00",
    )

    assert document["price_snapshot"] == 456789
    assert document["price_breakdown"] == {
        "estimated_on_road": 456789,
        "effective_date": "2026-09-11T00:00:00+00:00",
    }
    assert document["asset_id"] == "asset-server"
    assert document["asset_version"] == "2.0"
    assert document["asset_revision_id"] == "rev-7"
    assert document["configuration"]["interaction"]["hood_open"] is True
    assert document["owner_phone"] == "9876543210"


def test_saved_document_marks_missing_server_asset_as_stale():
    request = SimpleNamespace(
        configuration=SimpleNamespace(model_dump=lambda: {"purchasable": {"variant_id": "v1"}, "interaction": {}}),
        city=None,
        price_snapshot=999999,
        asset_id="client-asset",
        asset_version="1.0",
    )

    document = build_saved_configuration_document(
        request=request,
        owner_phone="9876543210",
        server_price_snapshot={"estimated_on_road": 100000, "effective_date": "2026-09-11T00:00:00+00:00"},
        server_asset=None,
        config_id="cfg-2",
        share_token="share-2",
        now="2026-09-11T00:00:00+00:00",
    )

    assert document["price_snapshot"] == 100000
    assert document["price_breakdown"]["estimated_on_road"] == 100000
    assert document["asset_id"] is None
    assert document["asset_version"] is None
    assert document["stale"] is True
    assert "asset" in document["stale_reason"].lower()
