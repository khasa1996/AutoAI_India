"""
Auto AI India — Configurator Rules Engine
==========================================
Evaluates compatibility rules for vehicle configurations.

Design rules:
  - The AI must NEVER bypass the rules engine.
  - All AI-selected options are validated here before application.
  - Rules come from the backend (configurator_rules collection).
  - Frontend provides immediate feedback but backend is authoritative.

Rule model:
  A rule targets a specific (option_type, option_id) combination.
  Conditions determine when the rule applies.
  Effects: ALLOW, DENY, REQUIRE, EXCLUDE.

Status:
  Core validation loop:   IMPLEMENTED
  Rule loading from DB:   IMPLEMENTED
  Full condition types:   FOUNDATION (variant_is, option_selected implemented;
                          date/market conditions Phase 3+)
  Mutually exclusive:     IMPLEMENTED
  Required co-selection:  IMPLEMENTED
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from configurator_schemas import (
    ConfiguratorRule,
    ConfigurationValidationRequest,
    PurchasableConfiguration,
    RuleConditionType,
    RuleEffect,
    ValidationResult,
)

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase


def _selected_option_ids(config: PurchasableConfiguration) -> Set[str]:
    """Return the set of all selected purchasable option IDs."""
    selected: Set[str] = set()
    if config.paint_id:
        selected.add(config.paint_id)
    if config.wheel_id:
        selected.add(config.wheel_id)
    if config.interior_id:
        selected.add(config.interior_id)
    if config.roof_id:
        selected.add(config.roof_id)
    selected.update(config.accessory_ids)
    return selected


def _evaluate_condition(
    condition: Dict[str, Any],
    config: PurchasableConfiguration,
) -> bool:
    """
    Evaluate a single rule condition against the current configuration.

    Returns True if the condition is met (rule should be applied).
    """
    ctype = condition.get("condition_type")
    value = condition.get("value")

    if ctype == RuleConditionType.VARIANT_IS:
        return config.variant_id == value

    if ctype == RuleConditionType.OPTION_SELECTED:
        return value in _selected_option_ids(config)

    # FOUNDATION: these condition types are defined but full evaluation
    # requires additional data (fuel_type lookup, date comparison).
    # They default to False (condition not met = rule not triggered).
    if ctype in (
        RuleConditionType.FUEL_TYPE,
        RuleConditionType.MARKET_SEGMENT,
        RuleConditionType.DATE_BEFORE,
        RuleConditionType.DATE_AFTER,
    ):
        return False  # FOUNDATION — Phase 3+ implementation

    return False


def _conditions_met(
    rule: Dict[str, Any],
    config: PurchasableConfiguration,
) -> bool:
    """Return True if ALL conditions in a rule are satisfied."""
    conditions = rule.get("conditions", [])
    if not conditions:
        # No conditions → rule always applies to its target scope
        return True
    return all(_evaluate_condition(c, config) for c in conditions)


def _requirement_gate_met(
    rule: Dict[str, Any],
    config: PurchasableConfiguration,
) -> bool:
    """Return True when non-requirement conditions allow a REQUIRE rule to apply."""
    conditions = rule.get("conditions", [])
    gating_conditions = [
        condition
        for condition in conditions
        if condition.get("condition_type") != RuleConditionType.OPTION_SELECTED
    ]
    return all(_evaluate_condition(condition, config) for condition in gating_conditions)


async def validate_configuration(
    request: ConfigurationValidationRequest,
    db: "AsyncIOMotorDatabase",
) -> ValidationResult:
    """
    Validate a purchasable configuration against the rules stored in MongoDB.

    Steps:
      1. Confirm the variant exists.
      2. Load all active rules for this variant/model.
      3. Evaluate each rule.
      4. Check selected options actually exist and are available.
    """
    config = request.configuration
    errors: List[str] = []
    warnings: List[str] = []
    rules_applied: List[Dict[str, Any]] = []

    # ── 1. Variant existence check ──────────────────────────────────────────
    variant_doc = await db.variants.find_one(
        {"variant_id": config.variant_id}, {"_id": 0}
    )
    if variant_doc is None:
        errors.append(f"Variant '{config.variant_id}' not found")
        return ValidationResult(valid=False, errors=errors)

    # ── 2. Option existence and availability checks ─────────────────────────
    if config.paint_id:
        color_doc = await db.variant_colors.find_one(
            {"color_id": config.paint_id, "variant_id": config.variant_id},
            {"_id": 0},
        )
        if not color_doc:
            errors.append(
                f"Paint option '{config.paint_id}' is not available for "
                f"variant '{config.variant_id}'"
            )
        elif not color_doc.get("available", True):
            errors.append(f"Paint option '{config.paint_id}' is currently unavailable")

    if config.wheel_id:
        wheel_doc = await db.variant_wheels.find_one(
            {"wheel_id": config.wheel_id, "variant_id": config.variant_id},
            {"_id": 0},
        )
        if not wheel_doc:
            errors.append(
                f"Wheel option '{config.wheel_id}' is not available for "
                f"variant '{config.variant_id}'"
            )
        elif not wheel_doc.get("available", True):
            errors.append(f"Wheel option '{config.wheel_id}' is currently unavailable")

    if config.interior_id:
        interior_doc = await db.variant_interiors.find_one(
            {"interior_id": config.interior_id, "variant_id": config.variant_id},
            {"_id": 0},
        )
        if not interior_doc:
            errors.append(
                f"Interior option '{config.interior_id}' is not available for "
                f"variant '{config.variant_id}'"
            )
        elif not interior_doc.get("available", True):
            errors.append(f"Interior option '{config.interior_id}' is currently unavailable")

    if config.roof_id:
        roof_doc = await db.configurator_options.find_one(
            {
                "option_id": config.roof_id,
                "variant_id": config.variant_id,
                "option_type": "roof",
            },
            {"_id": 0},
        )
        if not roof_doc:
            errors.append(
                f"Roof option '{config.roof_id}' is not available for "
                f"variant '{config.variant_id}'"
            )
        elif not roof_doc.get("available", True):
            errors.append(f"Roof option '{config.roof_id}' is currently unavailable")

    for accessory_id in config.accessory_ids:
        accessory_doc = await db.configurator_options.find_one(
            {
                "option_id": accessory_id,
                "variant_id": config.variant_id,
                "option_type": "accessory",
            },
            {"_id": 0},
        )
        if not accessory_doc:
            errors.append(
                f"Accessory option '{accessory_id}' is not available for "
                f"variant '{config.variant_id}'"
            )
        elif not accessory_doc.get("available", True):
            errors.append(f"Accessory option '{accessory_id}' is currently unavailable")

    # ── 3. Load and evaluate configurator rules ─────────────────────────────
    # Load rules that apply to this variant or its model
    rule_query: Dict[str, Any] = {
        "active": True,
        "$or": [
            {"variant_id": config.variant_id},
            {"variant_id": None, "model_id": variant_doc.get("model_id") if variant_doc else None},
            {"variant_id": None, "model_id": None},  # global rules
        ],
    }
    rules_cursor = db.configurator_rules.find(rule_query, {"_id": 0}).sort("priority", -1)
    rules: List[Dict[str, Any]] = await rules_cursor.to_list(200)

    selected_ids = _selected_option_ids(config)

    for rule in rules:
        target_id = rule.get("target_option_id", "")
        effect = rule.get("effect")
        explanation = rule.get("explanation", "")

        # Only evaluate if the target option is relevant to the current config
        if target_id not in selected_ids and effect not in (
            RuleEffect.REQUIRE, RuleEffect.ALLOW
        ):
            continue

        if effect == RuleEffect.REQUIRE:
            if target_id not in selected_ids or not _requirement_gate_met(rule, config):
                continue

            missing_requirements = [
                condition.get("value")
                for condition in rule.get("conditions", [])
                if condition.get("condition_type") == RuleConditionType.OPTION_SELECTED
                and condition.get("value") not in selected_ids
            ]
            if missing_requirements:
                required_id = missing_requirements[0]
                msg = (
                    explanation
                    or f"Option '{target_id}' requires '{required_id}' to also be selected"
                )
                errors.append(msg)
                rules_applied.append({
                    "rule_id": rule.get("rule_id"),
                    "effect": effect,
                    "target": target_id,
                    "result": "missing_requirement",
                })
            continue

        if not _conditions_met(rule, config):
            continue

        outcome = {"rule_id": rule.get("rule_id"), "effect": effect, "target": target_id}

        if effect == RuleEffect.DENY and target_id in selected_ids:
            msg = explanation or f"Option '{target_id}' is not compatible with this configuration"
            errors.append(msg)
            outcome["result"] = "blocked"

        elif effect == RuleEffect.EXCLUDE:
            # If target is selected, find what it excludes
            excluded = rule.get("conditions", [])
            for cond in excluded:
                if cond.get("condition_type") == RuleConditionType.OPTION_SELECTED:
                    excl_id = cond.get("value", "")
                    if excl_id in selected_ids and target_id in selected_ids:
                        msg = (
                            explanation
                            or f"Options '{target_id}' and '{excl_id}' cannot be selected together"
                        )
                        errors.append(msg)
                        outcome["result"] = "mutually_exclusive"

        elif effect == RuleEffect.ALLOW:
            outcome["result"] = "ok"

        else:
            outcome["result"] = "ok"

        rules_applied.append(outcome)

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        rules_applied=rules_applied,
    )


async def get_available_options_for_variant(
    variant_id: str,
    db: "AsyncIOMotorDatabase",
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Return all available options for a variant, grouped by type.

    The AI must use ONLY the options returned here.
    It must never invent option IDs outside this set.
    """
    colors = await db.variant_colors.find(
        {"variant_id": variant_id, "available": True}, {"_id": 0}
    ).to_list(50)

    wheels = await db.variant_wheels.find(
        {"variant_id": variant_id, "available": True}, {"_id": 0}
    ).to_list(30)

    interiors = await db.variant_interiors.find(
        {"variant_id": variant_id, "available": True}, {"_id": 0}
    ).to_list(20)

    other_options = await db.configurator_options.find(
        {"variant_id": variant_id, "available": True}, {"_id": 0}
    ).to_list(50)

    roofs = [o for o in other_options if o.get("option_type") == "roof"]
    accessories = [o for o in other_options if o.get("option_type") == "accessory"]

    return {
        "colors": colors,
        "wheels": wheels,
        "interiors": interiors,
        "roofs": roofs,
        "accessories": accessories,
    }
