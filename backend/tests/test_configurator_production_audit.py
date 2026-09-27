"""Tests for the production configurator catalog audit."""

from __future__ import annotations

import asyncio

from configurator_production_audit import audit_configurator_catalog, catalog_has_publishable_variants


class _Collection:
    def __init__(self, count: int = 0, distinct_values=None):
        self._count = count
        self._distinct_values = list(distinct_values or [])

    async def count_documents(self, _filter):
        return self._count

    async def distinct(self, _field):
        return self._distinct_values


class _DB:
    name = "autoai"

    def __init__(self):
        self._collections = {
            name: _Collection() for name in (
                "brands", "models", "variants", "variant_pricing",
                "variant_colors", "variant_wheels", "variant_interiors",
                "configurator_assets", "configurator_rules",
            )
        }

    def __getitem__(self, item):
        return self._collections[item]

    def __getattr__(self, item):
        return self._collections[item]


def test_audit_has_no_publishable_variants_when_empty():
    audit = asyncio.run(audit_configurator_catalog(_DB()))
    assert audit["database"] == "autoai"
    assert audit["production_data_write"] is False
    assert audit["verified_available_variants"] == 0
    assert catalog_has_publishable_variants(audit) is False


def test_audit_is_side_effect_free():
    db = _DB()
    before = dict(db._collections)
    asyncio.run(audit_configurator_catalog(db))
    assert dict(db._collections) == before
