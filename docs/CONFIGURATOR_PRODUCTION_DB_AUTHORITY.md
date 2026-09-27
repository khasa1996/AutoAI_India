# Configurator Production Database Authority

## Scope

The Ultra 3D Configurator uses the existing `autoai` MongoDB database as its authoritative production configurator catalog boundary.

This does not migrate, rename, copy, or delete data from the legacy `auto_ai` database or from the legacy `cars` collection.

## Authoritative collections

The configurator catalog boundary is composed of:

- `brands`
- `models`
- `variants`
- `variant_pricing`
- `variant_colors`
- `variant_wheels`
- `variant_interiors`
- `configurator_assets`
- `configurator_rules`

## Legacy boundary

The legacy `cars` collection remains a broader platform catalog and is not implicitly promoted to configurator readiness.

A production variant must have a canonical `variant_id`, verified identity, authoritative pricing, compatible options, and a verified/published asset according to the existing onboarding contracts.

## Safety rules

1. Never seed synthetic production vehicles, prices, options, or assets.
2. Never infer production readiness from the existence of a legacy `cars` record.
3. Never copy records between `auto_ai` and `autoai` based on local defaults.
4. Keep backend catalog decisions authoritative; clients and AI may only select IDs supplied by the backend.
5. Keep 3D asset provenance, validation, licensing, checksum, revision, and publication evidence independent from vehicle identity.
6. Re-run configurator readiness after catalog or asset changes before exposing a variant.

## Database performance

Catalog lookup indexes are maintained on canonical IDs and the variant relationships used by the configurator routes. The indexes are infrastructure only; they do not imply that any vehicle is production-ready.

## Operational verification

Before a production data onboarding run, verify the live Render deployment's `DB_NAME` and the MongoDB Atlas project/cluster connection. Do not make destructive or cross-database writes when the runtime database cannot be established from deployment configuration.
