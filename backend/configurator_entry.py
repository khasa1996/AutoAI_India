"""Production composition entrypoint for the Auto AI India configurator.

This module imports the existing production FastAPI application unchanged and
adds the versioned configurator router with the canonical database and auth
services. Render should use this module as the production ASGI entrypoint while
PR #43 is being integrated; no duplicate application, database, or auth stack
is created here.
"""

from server import app, db, optional_user_phone
from configurator_composition import mount_configurator_router
from configurator_production_audit_routes import make_configurator_production_audit_router


mount_configurator_router(app, db, optional_user_phone)
app.include_router(make_configurator_production_audit_router(db))


@app.on_event("startup")
async def ensure_configurator_indexes() -> None:
    """Create configurator persistence indexes idempotently at startup."""
    await db.configurations.create_index("config_id", unique=True)
    await db.configurations.create_index("share_token", unique=True, sparse=True)
