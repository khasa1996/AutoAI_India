"""Tests for the side-effect-free legacy catalog adapter."""

from legacy_configurator_adapter import (
    legacy_car_to_canonical_candidate,
    legacy_cars_to_canonical_candidates,
)


def test_legacy_car_maps_to_canonical_identity_without_promotion() -> None:
    car = {
        "id": "seltos-gtx-plus",
        "brand": "Kia",
        "model": "Seltos",
        "variant": "GTX+",
        "fuel": "Diesel",
        "transmission": "Automatic",
    }

    candidate = legacy_car_to_canonical_candidate(car)

    assert candidate["brand_id"] == "kia"
    assert candidate["model_id"] == "kia-seltos"
    assert candidate["variant_id"] == "kia-seltos-gtx-plus"
    assert candidate["fuel_type"] == "Diesel"
    assert candidate["transmission"] == "Automatic"
    assert candidate["verification_status"] == "unverified"
    assert candidate["configurator_status"] == "COMING_SOON"
    assert candidate["migration_status"] == "REVIEW_REQUIRED"
    assert candidate["legacy_car_id"] == "seltos-gtx-plus"


def test_legacy_adapter_does_not_mutate_input() -> None:
    car = {
        "id": "x",
        "brand": "Tata",
        "model": "Nexon",
        "variant": "XZ+",
        "fuel": "EV",
        "transmission": "AMT",
    }
    before = dict(car)

    legacy_car_to_canonical_candidate(car)

    assert car == before


def test_legacy_adapter_rejects_missing_identity() -> None:
    car = {
        "id": "x",
        "brand": "Tata",
        "model": "Nexon",
        "variant": "",
        "fuel": "Petrol",
        "transmission": "Manual",
    }

    try:
        legacy_car_to_canonical_candidate(car)
    except ValueError as exc:
        assert "variant" in str(exc)
    else:
        raise AssertionError("missing legacy identity must be rejected")


def test_batch_conversion_is_deterministic() -> None:
    cars = [
        {
            "id": "1",
            "brand": "Maruti Suzuki",
            "model": "Fronx",
            "variant": "Alpha",
            "fuel": "Petrol",
            "transmission": "Automatic",
        },
        {
            "id": "2",
            "brand": "MG",
            "model": "Hector",
            "variant": "Savvy Pro",
            "fuel": "Diesel",
            "transmission": "Automatic",
        },
    ]

    first = legacy_cars_to_canonical_candidates(cars)
    second = legacy_cars_to_canonical_candidates(cars)

    assert first == second
    assert all(item["migration_status"] == "REVIEW_REQUIRED" for item in first)
