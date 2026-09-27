"""TDD coverage for production configurator catalog authority."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

import configurator_routes


class FakeDatabase:
    def __init__(self) -> None:
        self.variants = _Collection()
        self.cars = _Collection()


class _Collection:
    async def find_one(self, query, projection=None):
        if query.get("id") == "legacy-only" and "id" in query:
            return {"id": "legacy-only"}
        return None


def _client(db: FakeDatabase) -> TestClient:
    app = FastAPI()
    app.include_router(configurator_routes.make_configurator_router(db))
    return TestClient(app)


def test_availability_does_not_treat_legacy_car_as_configurator_variant() -> None:
    response = _client(FakeDatabase()).get(
        "/api/v1/configurator/legacy-only/availability"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Variant not found"


def test_options_do_not_treat_legacy_car_as_configurator_variant(monkeypatch) -> None:
    async def should_not_read_options(variant_id, database):
        raise AssertionError("legacy-only vehicle must be rejected before option lookup")

    monkeypatch.setattr(
        configurator_routes,
        "get_available_options_for_variant",
        should_not_read_options,
    )

    response = _client(FakeDatabase()).get(
        "/api/v1/configurator/legacy-only/options"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Variant not found"
