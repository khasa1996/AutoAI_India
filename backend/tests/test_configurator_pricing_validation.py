"""Regression tests for backend-authoritative configurator pricing validation."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

import configurator_routes
from configurator_schemas import ValidationResult


class FakeDatabase:
    def __init__(self) -> None:
        self.variants = _Collection()
        self.cars = _Collection()


class _Collection:
    async def find_one(self, query, projection=None):
        if query.get("variant_id") == "variant-1":
            return {"variant_id": "variant-1"}
        return None


def _payload() -> dict[str, object]:
    return {
        "configuration": {
            "variant_id": "variant-1",
            "paint_id": "invalid-paint",
        },
        "city": "Delhi",
    }


def _client(db: FakeDatabase) -> TestClient:
    app = FastAPI()
    app.include_router(configurator_routes.make_configurator_router(db))
    return TestClient(app)


def test_price_rejects_invalid_configuration_before_calculation(monkeypatch) -> None:
    db = FakeDatabase()
    calls = {"pricing": 0}

    async def invalid_validation(request, database) -> ValidationResult:
        return ValidationResult(valid=False, errors=["Paint option 'invalid-paint' is not available"])

    async def should_not_calculate(request, database):
        calls["pricing"] += 1
        raise AssertionError("pricing engine must not run for an invalid configuration")

    monkeypatch.setattr(configurator_routes, "validate_configuration", invalid_validation)
    monkeypatch.setattr(configurator_routes, "calculate_configuration_price", should_not_calculate)

    response = _client(db).post("/api/v1/configurator/price", json=_payload())

    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "Invalid configuration"
    assert response.json()["detail"]["errors"] == [
        "Paint option 'invalid-paint' is not available"
    ]
    assert calls["pricing"] == 0
