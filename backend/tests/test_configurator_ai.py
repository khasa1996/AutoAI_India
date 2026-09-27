from configurator_ai import _extract_json, _extract_live_context, _merge_selection, _safe_selection, build_interaction_state, build_ai_prompt, resolve_textual_preferences
from configurator_schemas import AIConfiguratorIntent, PurchasableConfiguration


def catalog():
    return {
        "colors": [{"color_id": "red", "display_name": "Passion Red"}, {"color_id": "black", "display_name": "Obsidian Black"}],
        "wheels": [{"wheel_id": "w1", "name": "18 inch Alloy"}, {"wheel_id": "w2", "name": "Sport Alloy"}],
        "interiors": [{"interior_id": "i1", "name": "Black Leather"}],
        "roofs": [{"option_id": "r1", "display_name": "Panoramic Roof"}],
        "accessories": [{"option_id": "a1", "display_name": "Floor Mats"}],
    }


def test_extract_json_accepts_markdown_fenced_json():
    assert _extract_json('```json\n{"paint_id":"red"}\n```')["paint_id"] == "red"


def test_safe_selection_rejects_unavailable_catalog_ids():
    unavailable_catalog = catalog()
    unavailable_catalog["colors"][0]["available"] = False
    selected = _safe_selection({"paint_id": "red"}, unavailable_catalog, "v1")
    assert selected.paint_id is None


def test_safe_selection_rejects_ai_invented_ids():
    selected = _safe_selection({"variant_id": "attacker-variant", "paint_id": "red", "wheel_id": "invented-wheel", "accessory_ids": ["a1", "invented-accessory"]}, catalog(), "v1")
    assert selected.variant_id == "v1"
    assert selected.paint_id == "red"
    assert selected.wheel_id is None
    assert selected.accessory_ids == ["a1"]


def test_interaction_filters_unsupported_capabilities():
    state = build_interaction_state(AIConfiguratorIntent(variant_id="v1", raw_request="open everything", open_hood=True, open_boot=True, open_sunroof=True, open_doors=True, lights_on=True, camera_preset="interior"), {"hood", "boot", "doors", "headlights", "drl", "camera_exterior"})
    assert state.hood_open is True
    assert state.boot_open is True
    assert state.sunroof_open is False
    assert state.doors.front_left is True
    assert state.lighting.headlights is True
    assert state.lighting.drl is True
    assert state.camera_preset is None


def test_interaction_defaults_closed_and_lights_off():
    state = build_interaction_state(AIConfiguratorIntent(variant_id="v1", raw_request="show exterior"))
    assert state.hood_open is False
    assert state.boot_open is False
    assert state.sunroof_open is False
    assert state.doors.front_left is False
    assert state.lighting.headlights is False


def test_textual_preferences_resolve_against_catalog_labels():
    selected = resolve_textual_preferences("make it black with sport alloy wheels", catalog())
    assert selected["paint_id"] == "black"
    assert selected["wheel_id"] == "w2"


def test_ai_prompt_contains_only_catalog_option_ids_and_interaction_contract():
    intent = AIConfiguratorIntent(variant_id="v1", raw_request="red with alloy wheels and open the boot")
    prompt = build_ai_prompt(intent, catalog())
    assert "invented" not in prompt
    assert '"id":"red"' in prompt
    assert '"id":"w1"' in prompt
    assert "open_boot" in prompt
    assert "open_sunroof" in prompt


def test_live_context_extracts_city_and_current_configuration():
    request = '__AUTO_AI_CONTEXT__{"city":"Delhi","current_configuration":{"variant_id":"v1","paint_id":"red"}}\nmake it sporty'
    user_request, context = _extract_live_context(request)
    assert user_request == "make it sporty"
    assert context["city"] == "Delhi"
    assert context["current_configuration"]["paint_id"] == "red"


def test_live_context_merge_preserves_unspecified_options():
    base = PurchasableConfiguration(variant_id="v1", paint_id="red", wheel_id="w1", interior_id="i1", roof_id="r1", accessory_ids=["a1"])
    resolved = PurchasableConfiguration(variant_id="v1", paint_id="black", wheel_id="w2", interior_id=None, roof_id=None, accessory_ids=[])
    merged = _merge_selection(base, {"paint_id": "black", "wheel_id": "w2"}, resolved)
    assert merged.paint_id == "black"
    assert merged.wheel_id == "w2"
    assert merged.interior_id == "i1"
    assert merged.roof_id == "r1"
    assert merged.accessory_ids == ["a1"]


def test_ai_prompt_includes_live_city_and_existing_build():
    intent = AIConfiguratorIntent(variant_id="v1", raw_request="make it black")
    base = PurchasableConfiguration(variant_id="v1", paint_id="red", wheel_id="w1")
    prompt = build_ai_prompt(intent, catalog(), base, "Delhi")
    assert "Pricing city: Delhi" in prompt
    assert '"paint_id":"red"' in prompt


def test_ai_prompt_includes_authoritative_price_and_verified_asset_capabilities():
    intent = AIConfiguratorIntent(variant_id="v1", raw_request="open the hood")
    base = PurchasableConfiguration(variant_id="v1", paint_id="red")
    runtime_context = {
        "authoritative_price": {"estimated_on_road": 2475000, "effective_date": "2026-09-15", "source": "verified"},
        "verified_asset": {
            "asset_id": "asset-v1",
            "version": "v3",
            "supported_interactions": ["hood", "doors", "camera_exterior"],
            "camera_preset_names": ["exterior", "front"],
        },
    }
    prompt = build_ai_prompt(intent, catalog(), base, "Delhi", runtime_context)
    assert '"estimated_on_road":2475000' in prompt
    assert '"asset_id":"asset-v1"' in prompt
    assert '"version":"v3"' in prompt
    assert '"supported_interactions":["hood","doors","camera_exterior"]' in prompt
    assert '"camera_preset_names":["exterior","front"]' in prompt


def test_ai_prompt_excludes_untrusted_client_price_from_authoritative_context():
    intent = AIConfiguratorIntent(variant_id="v1", raw_request="what is the price?")
    prompt = build_ai_prompt(intent, catalog(), PurchasableConfiguration(variant_id="v1"), "Delhi", {"client_price": 999})
    assert "client_price" not in prompt
    assert "999" not in prompt

def test_textual_preferences_ignore_unavailable_options():
    unavailable_catalog = catalog()
    unavailable_catalog["colors"][0]["available"] = False
    selected = resolve_textual_preferences("make it passion red", unavailable_catalog)
    assert selected["paint_id"] is None
