# Ultra 3D Configurator — Production Onboarding

## Purpose

This document defines the production-safe path for onboarding a vehicle variant into the Ultra 3D Configurator. Validation is side-effect-free: it evaluates records in memory and does not write to MongoDB or publish assets.

## Required record set

A production variant requires:

1. A real vehicle variant with a stable `variant_id`, active status, and verified vehicle identity.
2. Authoritative `variant_pricing` with the same `variant_id`, a positive base ex-showroom price, a verified status, and source traceability.
3. At least one available color, wheel, and interior option matching the same `variant_id`.
4. A configurator asset whose identity and `variant_id` match the vehicle.
5. Asset provenance that is publishable: `OEM_AUTHORIZED`, `AUTO_AI_LICENSED`, or `LICENSED_THIRD_PARTY`.
6. Asset license/publisher metadata, SHA-256 checksum, file size within the 200 MB limit, validation evidence, a version, and `PUBLISHED` storage status.

## Temporary assets

Temporary, non-OEM, AI-generated, or otherwise unverified assets must never be represented as verified production assets. If such an asset is used for development or preview purposes, the product must clearly identify it as temporary/non-OEM and it must remain outside the production-ready catalog path.

## Authority rules

- Vehicle identity, compatibility, availability, and pricing are backend-authoritative.
- AI may select only option IDs supplied by the verified catalog; it must not invent IDs or prices.
- Missing or invalid production assets result in a blocked/coming-soon state rather than a silent asset substitution.
- The frontend must respect the backend readiness gate.
- No production catalog write should occur until the authoritative production MongoDB database is explicitly established from the live Render `DB_NAME` configuration.

## Validation flow

`ConfiguratorOnboardingRecordSet` is validated with `validate_onboarding_record_set()`. The validator delegates to the existing deterministic vehicle configurator readiness rules so onboarding and runtime readiness do not drift into separate rule sets.

The validator returns `valid`, `errors`, and `warnings` and does not mutate the supplied records or perform persistence.

## Production onboarding sequence

1. Establish the authoritative production database from the live deployment configuration.
2. Obtain real OEM-authorized or appropriately licensed vehicle assets and their provenance evidence.
3. Verify vehicle, variant, pricing, colors, wheels, interiors, and asset identities.
4. Run the side-effect-free onboarding validator.
5. Reject any record set with blockers; do not auto-fill missing production data with synthetic records.
6. After all evidence is verified, onboard records through an approved production data process.
7. Re-run readiness and runtime checks before exposing the variant to users.

## Non-goals

This contract does not seed production data, download OEM assets, infer missing specifications, or change Render secrets. Those actions require separate verification and approval.
