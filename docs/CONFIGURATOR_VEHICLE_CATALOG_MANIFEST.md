# Ultra 3D Configurator — Vehicle Catalog Manifest

The vehicle catalog manifest is the side-effect-free onboarding boundary between external verified vehicle information and Auto AI India's authoritative configurator catalog.

## Canonical identity

Every production configurator record must identify the same:

**Brand → Model → Variant**

The canonical variant_id is the identity used by configurator pricing, compatible options, AI selection, saved configurations, readiness checks, and the assigned 3D asset.

The manifest also records:

- fuel type
- transmission
- verification status
- active state
- configurator publication status
- source and HTTPS source URL

Legacy cars records are not configurator variants and must not be promoted implicitly by this manifest.

## Validation rules

A manifest is accepted for production onboarding only when:

1. brand_id, model_id, and variant_id are non-empty.
2. Vehicle verification status is verified.
3. The variant is active.
4. Configurator status is AVAILABLE.
5. variant_id is unique within the onboarding batch.
6. No legacy_car_id is supplied.
7. The source URL uses HTTPS.

The validator is pure: it does not create, update, delete, migrate, or seed MongoDB records.

## Production onboarding sequence

Use this sequence for real Indian vehicles and variants:

**OEM/licensed source → vehicle verification → manifest validation → authoritative production DB → verified variant pricing → compatible options → licensed 3D asset intake → asset validation/review → publication → configurator readiness**

A vehicle may exist in the broader platform catalog without being configurator-ready.

## Asset policy

OEM or licensed 3D assets remain a separate production gate. A temporary/non-OEM asset may be used only when explicitly identified as temporary/non-OEM; it must never be represented as a verified production asset.

The asset publication contract continues to require provenance, licensing, publisher, checksum, size, validation, review, publication, and version evidence.

## Database safety

Do not populate production MongoDB from this manifest until the authoritative Render DB_NAME has been explicitly established.

Do not copy or migrate records between auto_ai and autoai based on local defaults or assumptions.

No synthetic vehicle, pricing, option, or 3D asset records are permitted in production.

## AI boundary

AI may consume the canonical catalog and select only IDs that the backend supplies. AI does not create vehicle IDs, option IDs, pricing, compatibility, or 3D capabilities.

The backend remains authoritative for all production catalog decisions.
