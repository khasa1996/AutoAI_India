# Production Configurator Catalog Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a production-safe, backend-authoritative catalog contract that can onboard real Indian vehicle variants into the Ultra 3D Configurator without synthetic pricing, fake assets, or unverifiable compatibility.

**Architecture:** Keep the existing MongoDB collections and FastAPI configurator architecture, adding deterministic schema/validation boundaries rather than replacing working runtime components. A variant becomes configurator-ready only when verified vehicle identity, authoritative verified pricing, available purchasable options, and a published validated licensed 3D asset all match the same variant identity.

**Tech Stack:** FastAPI, Pydantic, Motor/MongoDB, pytest, React frontend/Jest, existing configurator pricing/rules/runtime/asset modules, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-18-production-catalog-onboarding-design.md` (approved design; repository state must be checked before relying on this path).

## Global Constraints

- Backend is authoritative for vehicle identity, pricing, option availability, compatibility, and 3D asset capability.
- AI may select only IDs present in the supplied catalog and may never invent prices or capabilities.
- Production 3D assets require provenance, licensing, publisher, checksum, size, validation, review, publication, and version evidence.
- Temporary/non-OEM assets must never be represented as verified production assets.
- Do not populate production MongoDB with synthetic vehicle, pricing, option, or asset records.
- Do not infer the authoritative production database from local defaults; live Render `DB_NAME` must be explicitly established before production onboarding.
- Do not modify or merge `main` as part of this implementation.
- Preserve existing lifecycle ownership and pricing-authority behavior.
- Production asset limit remains 200 MB per asset.
- Every behavior-changing production implementation must follow TDD: failing test first, then minimal implementation, then green verification.

---

### Task 1: Reconcile the existing readiness slice with current main

**Files:** inspect `backend/configurator_vehicle_readiness.py`, `backend/configurator_vehicle_readiness_routes.py`, `backend/configurator_runtime_capabilities.py`, `backend/configurator_routes.py`, `backend/configurator_schemas.py`; test `backend/tests/test_configurator_vehicle_readiness_route.py`.

**Interfaces:** preserve `assess_vehicle_configurator_readiness(...)` and `GET /api/v1/configurator/variants/{variant_id}/readiness`.

- [ ] Run `cd backend && pytest tests/test_configurator_vehicle_readiness_route.py tests/test_configurator_runtime_capabilities.py -q`; stop if baseline fails.
- [ ] Compare PR #59 with current main and discard obsolete hunks already superseded by merged work.
- [ ] Confirm readiness reads `variants`, `variant_pricing`, `variant_colors`, `variant_wheels`, `variant_interiors`, and `configurator_assets`.
- [ ] Record the verified baseline in the PR notes; do not change production data.

### Task 2: Harden catalog identity contracts

**Files:** modify `backend/configurator_schemas.py`; create/modify `backend/tests/test_configurator_catalog_contract.py`.

**Interfaces:** existing `PurchasableConfiguration`, `ConfiguratorOption`, and `ConfiguratorAssetCreate` remain compatible; new validation must reject cross-variant option identity at the catalog boundary.

- [ ] Write a failing test showing an option whose `variant_id` differs from the requested variant cannot be accepted.
- [ ] Write a failing test for bounded required option identifiers.
- [ ] Run `cd backend && pytest tests/test_configurator_catalog_contract.py -q` and verify the failures are caused by missing behavior.
- [ ] Implement only the minimal validation required by those tests.
- [ ] Run `cd backend && pytest tests/test_configurator_catalog_contract.py tests/test_configurator_vehicle_readiness_route.py tests/test_configurator_runtime_capabilities.py -q`.

### Task 3: Complete the production readiness gate

**Files:** modify `backend/configurator_vehicle_readiness.py` and, only if required by failing route tests, `backend/configurator_vehicle_readiness_routes.py`; tests `backend/tests/test_configurator_vehicle_readiness.py` and `backend/tests/test_configurator_vehicle_readiness_route.py`.

**Interfaces:** `assess_vehicle_configurator_readiness(...)` stays deterministic; route remains `GET /api/v1/configurator/variants/{variant_id}/readiness`.

- [ ] Write failing tests for missing/inactive/unverified vehicle.
- [ ] Write failing tests for missing/unverified/mismatched authoritative pricing.
- [ ] Write failing tests for missing available colour, wheel, and interior.
- [ ] Write failing tests for missing/mismatched/unpublished/unvalidated asset.
- [ ] Write failing tests for non-publishable provenance, incomplete licence metadata, invalid checksum/file size, and incomplete storage publication.
- [ ] Run focused readiness tests and verify RED.
- [ ] Implement minimal deterministic blocker evaluation without weakening existing gates.
- [ ] Run focused readiness tests and verify GREEN.

### Task 4: Preserve authoritative pricing

**Files:** inspect/modify `backend/pricing_engine.py`, inspect/modify `backend/configurator_routes.py`; test `backend/tests/test_configurator_pricing_authority.py`.

**Interfaces:** `calculate_configuration_price(request, db) -> ConfigurationPriceResponse` remains the authoritative price resolver.

- [ ] Write failing tests proving a production-ready configuration cannot rely on absent/unverified `variant_pricing`.
- [ ] Write failing tests proving unavailable selected options are rejected.
- [ ] Run `cd backend && pytest tests/test_configurator_pricing_authority.py -q` and verify RED.
- [ ] Implement only missing authority checks; retain legacy fallback only where existing non-production compatibility requires it.
- [ ] Run `cd backend && pytest tests/test_configurator_pricing_authority.py tests/test_configurator_vehicle_readiness.py -q`.

### Task 5: Harden AI catalog authority

**Files:** inspect/modify `backend/configurator_ai.py`; use the existing configurator AI test module containing `resolve_ai_selection`.

**Interfaces:** `resolve_ai_selection(intent, db)` must continue to constrain AI output through the authoritative catalog and backend price/asset context.

- [ ] Write a failing test where the model proposes an unknown option ID and assert that the resolved configuration does not accept it.
- [ ] Run the smallest relevant AI test and verify RED.
- [ ] Implement the minimum filtering/fallback behavior required.
- [ ] Run AI, pricing, and readiness tests together.

### Task 6: Harden saved-configuration freshness

**Files:** inspect the saved-configuration persistence module containing `revalidate_saved_configuration`; modify only the relevant module; test its corresponding freshness test module.

**Interfaces:** preserve `revalidate_saved_configuration(saved_document, current_price_resolver, current_asset_resolver)` and `assess_saved_configuration_freshness(saved_document, current_price_snapshot, current_asset)`.

- [ ] Write failing tests for an authoritative price change.
- [ ] Write failing tests for a verified asset revision change.
- [ ] Verify RED.
- [ ] Implement stale-state comparison without changing the user's purchasable selections.
- [ ] Verify focused freshness tests and all configurator tests.

### Task 7: Add a side-effect-free onboarding contract

**Files:** create `backend/configurator_onboarding_contract.py`; create `backend/tests/test_configurator_onboarding_contract.py`; create `docs/CONFIGURATOR_PRODUCTION_ONBOARDING.md`.

**Interfaces:** `validate_onboarding_record_set(records: ConfiguratorOnboardingRecordSet) -> OnboardingValidationResult`; validation is in-memory only and performs no MongoDB writes.

- [ ] Write failing tests for an onboarding package missing verified pricing.
- [ ] Write failing tests for missing compatible options.
- [ ] Write failing tests for missing/unpublishable verified asset evidence.
- [ ] Run `cd backend && pytest tests/test_configurator_onboarding_contract.py -q` and verify RED.
- [ ] Implement the pure validation contract.
- [ ] Verify GREEN.
- [ ] Document the sequence: OEM/licensed source → asset inspection → manifest → review → publication → variant linkage → verified pricing → options → readiness.
- [ ] Explicitly document temporary/non-OEM assets as temporary and never verified.

### Task 8: Add safe production diagnostics

**Files:** create `backend/configurator_production_diagnostics.py`; create `backend/tests/test_configurator_production_diagnostics.py`; inspect `render.yaml`.

**Interfaces:** `build_configurator_catalog_diagnostics(db_name: str, collection_counts: Dict[str, int]) -> Dict[str, object]`.

- [ ] Write a failing test that accepted application DB names produce non-secret diagnostic identity.
- [ ] Write a failing test that output excludes connection strings, credentials, and environment secret values.
- [ ] Verify RED.
- [ ] Implement a pure formatter; do not add a public unauthenticated endpoint.
- [ ] Verify GREEN.
- [ ] Do not change Render secrets.

### Task 9: Gate the frontend on backend readiness

**Files:** inspect `frontend/src/services/configuratorApi.js` and the configurator page/components; modify only the relevant files; use existing frontend configurator tests.

**Interfaces:** frontend consumes readiness and must display an explicit unavailable/coming-soon state when `ready === false`; it must never silently substitute an unverified asset.

- [ ] Write a failing frontend test for false readiness.
- [ ] Run with `cd frontend && CI=true npm test -- --watchAll=false --runInBand` and verify RED.
- [ ] Implement minimal readiness gating while preserving request deduplication.
- [ ] Verify focused tests and `cd frontend && npm run build`.

### Task 10: Regression, review, and draft PR

**Files:** all changed files plus documentation required by verified implementation.

**Interfaces:** no production data migration; no merge to main.

- [ ] Run `cd backend && pytest tests/test_configurator*.py -q`.
- [ ] Run `cd frontend && CI=true npm test -- --watchAll=false --runInBand`.
- [ ] Run `cd frontend && npm run build`.
- [ ] Review diff for synthetic vehicle/pricing/asset records, hardcoded production DB selection, credentials, placeholders, or unverified OEM claims.
- [ ] Open a draft PR from `phase-3/production-configurator-catalog-foundation` to `main`.
- [ ] Keep the PR unmerged until the user explicitly approves merging.


### Task 11: Make active asset revision authoritative

**Files:** modify `backend/configurator_runtime_capabilities.py`, `backend/configurator_routes.py`; test `backend/tests/test_configurator_runtime_capabilities.py` and create `backend/tests/test_configurator_asset_revision_runtime.py`.

**Interfaces:** preserve `build_runtime_capability_contract(db, variant_id)`; preserve `resolve_saved_configuration_asset(db, variant_id, requested_asset_id)`; use `ConfiguratorAssetRevision` and `select_active_revision(...)` as the revision lifecycle contract. Do not create a second persistence collection for revisions.

- [x] Write failing runtime tests proving a configured `active_revision_id` is required when the asset declares one, and only that selected revision may be exposed.
- [x] Write failing tests proving a missing selected revision, a `SUPERSEDED` selected revision, an unpublished selected revision, and a cross-variant selected revision all fail closed without exposing the asset URL.
- [x] Write failing tests proving saved-configuration asset resolution uses the authoritative active revision rather than accepting an arbitrary requested asset ID.
- [x] Run the focused revision/runtime tests and verify RED for the new behavior; CI observed the expected missing-helper import failure and later the expected arbitrary-asset fallback assertion failure.
- [x] Implement the smallest adapter that reads revision evidence from the existing asset record, validates it through `select_active_revision(...)`, and keeps the existing `configurator_assets` persistence model.
- [x] Ensure the runtime contract reports the selected published revision's version/checksum and never exposes superseded/unverified revision data.
- [x] Verify focused runtime, saved-configuration, readiness, and asset-revision tests are GREEN.
- [x] Run the complete configurator regression suite and production gate.
- [x] Complete the PR review checkpoint; PR #66 remains draft and unmerged pending explicit merge approval.
