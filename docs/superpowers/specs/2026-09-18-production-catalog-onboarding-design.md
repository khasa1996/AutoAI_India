# Production Catalog Onboarding — Design Specification

**Status:** Approved in chat; awaiting written-spec review before implementation planning  
**Date:** 2026-09-18  
**Repository:** khasa1996/Auto-AI  
**Target branch:** phase-3/production-configurator-catalog-foundation

## 1. Purpose

Establish a production-safe onboarding boundary for the Ultra 3D Configurator so real Indian vehicle variants can be introduced only when their identity, pricing, compatible configuration options, and 3D asset evidence are verified and mutually consistent.

The onboarding boundary is validation-first and side-effect-free until the authoritative production MongoDB database is explicitly established from the live Render `DB_NAME` configuration and a separately approved production data process is used.

This design does not seed production data, invent vehicle/pricing records, download or claim OEM assets, change Render secrets, or merge `main`.

## 2. Product invariants

1. **Canonical vehicle identity**
   - Production configurator identity is `Brand → Model → Variant`.
   - `variant_id` is the stable identity shared by vehicle data, pricing, compatible options, AI selection, saved configurations, readiness, and the assigned configurator asset.
   - Legacy `cars` records are not promoted implicitly into the configurator catalog.

2. **Backend authority**
   - Vehicle identity, active status, configurator availability, compatibility, option availability, asset capability, and pricing are backend-authoritative.
   - AI may select only IDs supplied by the verified catalog.
   - AI must not invent vehicle IDs, option IDs, prices, compatibility, or 3D capabilities.

3. **Asset provenance**
   - Publishable 3D assets must have acceptable provenance: `OEM_AUTHORIZED`, `AUTO_AI_LICENSED`, or `LICENSED_THIRD_PARTY`.
   - License and publisher evidence are required.
   - SHA-256 and bounded file-size evidence are required.
   - Temporary/non-OEM, AI-generated, unknown, or otherwise unverified assets cannot be represented as verified production assets.
   - If temporary assets are used for development or preview, the UI and documentation must identify them explicitly as temporary/non-OEM and the production readiness gate must remain blocked.

4. **Revision authority**
   - Asset revisions follow the lifecycle:
     `INTAKE → VALIDATING → VALIDATED → REVIEWED → PUBLISHED → SUPERSEDED`.
   - `active_revision_id` is the single authoritative selector for the asset's runtime revision.
   - Only a matching `PUBLISHED` revision may be exposed to runtime consumers.
   - Missing, superseded, unpublished, or cross-variant active revisions fail closed.
   - Revision evidence remains nested with the existing `configurator_assets` persistence authority; no competing revision collection is introduced.

5. **Pricing authority**
   - `variant_pricing` is the authoritative production pricing source.
   - Pricing must match `variant_id`, be verified, have a positive base ex-showroom price, and have source traceability.
   - AI is never a pricing authority.

6. **Readiness**
   - A variant is configurator-ready only when the required vehicle, verified pricing, compatible color/wheel/interior options, published validated asset, and authoritative active revision all pass deterministic readiness checks.
   - Failure produces an explicit blocked/coming-soon state; the system must not silently substitute another vehicle, asset, revision, or price.

## 3. Existing persistence authorities

The design intentionally extends the existing MongoDB model rather than creating competing sources of truth.

| Domain | Existing authority |
|---|---|
| Vehicle variants | `variants` |
| Variant pricing | `variant_pricing` |
| Exterior colours | `variant_colors` |
| Wheels | `variant_wheels` |
| Interiors | `variant_interiors` |
| 3D configurator assets + revision evidence | `configurator_assets` |
| Legacy/general vehicle catalog | `cars` |

No migration between `auto_ai` and `autoai` is permitted based on local defaults or assumptions.

## 4. Onboarding contract

The onboarding boundary accepts an in-memory record set containing:

- canonical vehicle/variant identity and verification metadata;
- authoritative pricing evidence;
- compatible color, wheel, and interior records;
- the assigned configurator asset and its publication/revision evidence.

Validation delegates to the existing deterministic vehicle configurator readiness source of truth so onboarding and runtime do not develop separate eligibility rules.

The contract returns:

- `valid`;
- deterministic `errors` / blockers;
- non-blocking `warnings`.

It performs no MongoDB writes and does not mutate supplied records.

### Required identity checks

- `variant_id` is present and stable.
- Vehicle is active and verified.
- Configurator status is `AVAILABLE` for production publication.
- Manifest identity and runtime vehicle identity match.
- Legacy `car_id` identity is not used as configurator authority.

### Required option checks

At least one available option of each required category must match the same `variant_id`:

- exterior color;
- wheel;
- interior/upholstery.

The onboarding boundary must reject cross-variant option identity rather than silently treating an option as compatible.

### Required asset checks

The assigned asset must:

- identify the same `brand_id`, `model_id`, and `variant_id`;
- use GLB/GLTF-compatible evidence;
- have valid provenance/license/publisher evidence;
- have valid SHA-256 and file-size evidence;
- have a version;
- pass validation and administrative review requirements;
- have published storage status;
- declare an authoritative `active_revision_id`;
- resolve that selector to a matching `PUBLISHED` revision.

## 5. Manifest boundary

The vehicle catalog manifest is a side-effect-free boundary between externally verified vehicle information and the Auto AI India configurator catalog.

A manifest record contains:

- brand identity;
- model identity;
- variant identity;
- fuel type;
- transmission;
- verification status;
- active status;
- configurator status;
- source and HTTPS source URL;
- optional legacy identity only for explicit rejection/diagnostic handling.

A production manifest is accepted only when the vehicle is verified, active, `AVAILABLE`, unique within the onboarding batch, and not relying on a legacy `cars` record.

## 6. Asset intake and revision flow

Asset intake is evidence-first.

### Intake

An asset enters `INTAKE` with immutable identity/evidence fields such as asset ID, variant ID, version, checksum, provenance, licensing, publisher, and storage evidence.

### Validation

The asset moves through the lifecycle only in the declared order. Invalid integrity, provenance, license, identity, or compatibility evidence blocks publication.

### Review and publication

A production asset must reach `REVIEWED` before `PUBLISHED`. Runtime resolution never treats `VALIDATED`, `REVIEWED`, or `SUPERSEDED` as published runtime state.

### Active revision

Runtime reads the asset's `active_revision_id`, resolves it against nested revision evidence, requires `PUBLISHED`, and verifies asset/variant identity. If resolution fails, the runtime returns no usable asset URL/capability.

## 7. Database authority gate

Production onboarding must not begin until the authoritative application database is explicitly established from the live Render deployment's `DB_NAME`.

The diagnostic boundary:

- compares configured and explicitly expected database identity;
- reports non-secret catalog counts;
- never exposes credentials, connection strings, or environment secret values;
- does not change Render configuration;
- does not migrate, copy, rename, or delete records.

Because the live Render secret value is not available to the repository tooling, the implementation must not guess whether `auto_ai` or `autoai` is authoritative.

## 8. Runtime data flow

The production flow is:

`verified source → manifest → authoritative variant → verified pricing → compatible options → licensed 3D asset intake → revision validation/review/publication → active revision → readiness → runtime configurator`.

At runtime:

1. resolve canonical `variant_id`;
2. load variant from `variants`;
3. resolve authoritative `variant_pricing`;
4. resolve only compatible options for that variant;
5. resolve the variant-assigned `configurator_asset_id`;
6. resolve `active_revision_id`;
7. require `PUBLISHED` revision and matching identity;
8. expose only verified runtime metadata/capabilities;
9. calculate price from authoritative backend data;
10. allow AI to operate only within the resulting catalog.

Any failed gate is fail-closed.

## 9. Error handling and safety

Errors should be deterministic and actionable. The system must prefer an explicit unavailable/coming-soon state over a plausible-looking but unverified result.

The following must never happen in production:

- fallback from configurator variant to an arbitrary legacy car;
- fallback from an assigned asset to a caller-selected arbitrary asset;
- exposure of a superseded or unpublished revision;
- acceptance of cross-variant options;
- use of unverified pricing;
- AI-generated pricing or compatibility;
- silent replacement with temporary/non-OEM 3D assets;
- hardcoded selection of a production database;
- production writes before database authority is established.

## 10. Frontend contract

The frontend consumes backend readiness and runtime capability contracts.

When readiness is false:

- do not initialize a production 3D asset;
- show an explicit unavailable/coming-soon state;
- preserve the reason in an appropriate user-safe form;
- never silently substitute an unverified asset.

When readiness is true, the frontend may consume only the backend-selected asset/revision and capabilities. Existing request deduplication and lifecycle ownership remain intact.

## 11. Testing strategy

All behavior changes use TDD:

1. write the smallest failing test;
2. verify the failure is caused by the missing behavior;
3. implement the minimum production-safe change;
4. run focused tests;
5. run related configurator regressions;
6. run frontend tests/build where frontend behavior changes;
7. run the production gate;
8. review the diff for synthetic data, secrets, arbitrary fallbacks, and unverified asset claims.

Required coverage includes:

- manifest identity and publication validation;
- cross-variant option rejection;
- missing/unverified pricing;
- missing compatible options;
- asset provenance/license/integrity;
- revision transition and active revision selection;
- missing/superseded/unpublished/cross-variant active revision;
- saved-configuration asset authority;
- AI catalog authority;
- frontend readiness gating;
- database diagnostic secrecy and identity mismatch;
- regression coverage for existing configurator behavior.

## 12. Non-goals

This design does not:

- seed real production vehicle records;
- invent or estimate OEM specifications;
- scrape or download OEM assets without appropriate rights;
- assert that any specific 3D asset is OEM-authorized without evidence;
- determine the authoritative Render database from local configuration;
- change Render secrets;
- replace existing `configurator_assets` persistence;
- create a second variant/pricing/asset source of truth;
- merge the branch into `main`;
- implement the full production 3D viewer, AR, dealer commerce, or mobile release in this slice.

## 13. Acceptance criteria

The catalog onboarding foundation is ready for the next implementation stage when:

1. Canonical vehicle identity is enforced.
2. Production pricing is backend-authoritative and verified.
3. Required compatible options are variant-scoped.
4. Asset provenance and integrity evidence are enforced.
5. Revision lifecycle and `active_revision_id` are authoritative.
6. Runtime fails closed for invalid active revisions.
7. Frontend respects backend readiness.
8. Database authority is an explicit prerequisite and no production data is written by this work.
9. Tests cover the safety gates and existing configurator behavior remains green.
10. The implementation remains isolated on the feature branch and PR #66 remains draft until explicit merge approval.
