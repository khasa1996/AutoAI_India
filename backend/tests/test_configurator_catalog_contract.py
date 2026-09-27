"""TDD gate for configurator catalog identity boundaries."""

import pytest
from pydantic import ValidationError

from configurator_schemas import ConfiguratorOption, ConfiguratorOptionType, validate_catalog_options


def _option(variant_id: str = "variant-1") -> ConfiguratorOption:
    return ConfiguratorOption(
        option_id="paint-1",
        option_type=ConfiguratorOptionType.PAINT,
        variant_id=variant_id,
        name="Obsidian Black",
        display_name="Obsidian Black",
        reference_id="ref-1",
    )


def test_catalog_rejects_option_from_different_variant() -> None:
    with pytest.raises(ValueError, match="does not match requested variant"):
        validate_catalog_options("variant-1", [_option("variant-2")])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("option_id", ""),
        ("variant_id", ""),
        ("reference_id", ""),
    ],
)
def test_catalog_rejects_empty_required_option_identifiers(field: str, value: str) -> None:
    payload = _option().model_dump()
    payload[field] = value

    with pytest.raises(ValidationError):
        ConfiguratorOption.model_validate(payload)


def test_catalog_rejects_overlong_option_identifiers() -> None:
    payload = _option().model_dump()
    payload["option_id"] = "x" * 101

    with pytest.raises(ValidationError):
        ConfiguratorOption.model_validate(payload)


def test_catalog_accepts_matching_variant_options() -> None:
    result = validate_catalog_options("variant-1", [_option()])

    assert result == [_option()]
