"""Operational endpoint for the side-effect-free configurator catalog audit."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from configurator_production_audit import audit_configurator_catalog
def make_configurator_production_audit_router(db: Any, require_admin_dependency: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["configurator-ops"])

    @router.get("/admin/configurator/catalog-audit")
    async def catalog_audit(_: str = Depends(require_admin_dependency)) -> Dict[str, Any]:
        return await audit_configurator_catalog(db)

    return router
