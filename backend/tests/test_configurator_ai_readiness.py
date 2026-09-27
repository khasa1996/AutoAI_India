import asyncio

import pytest

from configurator_ai_readiness import require_ai_configurator_readiness


def _ready_vehicle():
    return {
        "variant_id": "v1",
        "model_id": "m1",
        "brand_id": "b1",
        "active": True,
        "verification_status": "verified",
        "configurator_status": "AVAILABLE",
        "configurator_asset_id": "asset-1",
    }


def _ready_pricing():
    return {
        "variant_id": "v1",
        "base_ex_showroom": 1000000,
        "source": "verified-source",
        "verification_status": "verified",
    }


def _ready_asset():
    return {
        "asset_id": "asset-1",
        "variant_id": "v1",
        "version": "1.0",
        "published": True,
        "validation_passed": True,
        "provenance": "AUTO_AI_LICENSED",
        "license_name": "Production license",
        "publisher": "Auto AI India",
        "checksum_sha256": "a" * 64,
        "file_size_bytes": 1024,
        "storage_status": "PUBLISHED",
        "active_revision_id": "rev-1",
        "revisions": [{
            "revision_id": "rev-1",
            "asset_id": "asset-1",
            "variant_id": "v1",
            "version": "1.0",
            "checksum_sha256": "a" * 64,
            "state": "PUBLISHED",
        }],
    }


class Collection:
    def __init__(self, documents):
        self.documents = documents

    async def find_one(self, query, projection=None):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return document
        return None


class DB:
    def __init__(self, vehicle, pricing, asset):
        self.variants = Collection([vehicle] if vehicle else [])
        self.variant_pricing = Collection([pricing] if pricing else [])
        self.configurator_assets = Collection([asset] if asset else [])


def _options():
    return (
        [{"variant_id": "v1", "available": True}],
        [{"variant_id": "v1", "available": True}],
        [{"variant_id": "v1", "available": True}],
    )


def test_readiness_gate_returns_authoritative_context_for_ready_variant():
    colors, wheels, interiors = _options()
    result = asyncio.run(
        require_ai_configurator_readiness(
            "v1", DB(_ready_vehicle(), _ready_pricing(), _ready_asset()),
            colors, wheels, interiors,
        )
    )
    assert result["readiness"]["ready"] is True
    assert result["pricing"]["verification_status"] == "verified"
    assert result["asset"]["asset_id"] == "asset-1"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"verification_status": "unverified"}, "vehicle verification is not complete"),
        ({"active": False}, "vehicle variant is inactive"),
        ({"configurator_status": "COMING_SOON"}, "configurator status is not AVAILABLE"),
    ],
)
def test_readiness_gate_blocks_nonproduction_vehicle(change, message):
    vehicle = {**_ready_vehicle(), **change}
    colors, wheels, interiors = _options()
    with pytest.raises(ValueError, match=message):
        asyncio.run(
            require_ai_configurator_readiness(
                "v1", DB(vehicle, _ready_pricing(), _ready_asset()),
                colors, wheels, interiors,
            )
        )


def test_readiness_gate_blocks_unverified_pricing():
    colors, wheels, interiors = _options()
    pricing = {**_ready_pricing(), "verification_status": "unverified"}
    with pytest.raises(ValueError, match="variant pricing verification is not complete"):
        asyncio.run(
            require_ai_configurator_readiness(
                "v1", DB(_ready_vehicle(), pricing, _ready_asset()),
                colors, wheels, interiors,
            )
        )


def test_readiness_gate_blocks_missing_published_asset():
    colors, wheels, interiors = _options()
    with pytest.raises(ValueError, match="published verified configurator asset is missing"):
        asyncio.run(
            require_ai_configurator_readiness(
                "v1", DB(_ready_vehicle(), _ready_pricing(), None),
                colors, wheels, interiors,
            )
        )
