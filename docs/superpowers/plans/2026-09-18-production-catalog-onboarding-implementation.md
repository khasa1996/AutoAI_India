# Production Catalog Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a production-safe, backend-authoritative catalog onboarding foundation for real Indian vehicle variants without synthetic production data, unverified pricing, arbitrary assets, or cross-variant configuration.

**Architecture:** Extend the existing FastAPI/Pydantic/MongoDB configurator contracts and readiness source of truth. Keep `variants`, `variant_pricing`, `variant_colors`, `variant_wheels`, `variant_interiors`, and `configurator_assets` as the persistence authorities; keep asset revisions nested in `configurator_assets`. The implementation remains validation-first and side-effect-free for onboarding, with runtime failing closed whenever authoritative identity, pricing, options, asset, or active revision evidence is invalid.

**Tech Stack:** FastAPI, Pydantic, Motor/MongoDB, pytest, existing React frontend/Jest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-18-production-catalog-onboarding-design.md`

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

### Task 1: Lock catalog identity and option compatibility

**Files:**
- Modify: `backend/configurator_schemas.py`
- Test: `backend/tests/test_configurator_catalog_contract.py`

**Interfaces:**
- Preserve existing `PurchasableConfiguration`, `ConfiguratorOption`, and `ConfiguratorAssetCreate` compatibility.
- Add deterministic validation that catalog options consumed for a variant carry the same `variant_id`.

- [ ] **Step 1: Write failing tests** for an option with a different `variant_id` and for missing/empty option identifiers.
- [ ] **Step 2: Run the focused tests** with `cd backend && pytest tests/test_configurator_catalog_contract.py -q`; expected result is RED because the new boundary is absent.
- [ ] **Step 3: Implement the smallest schema/helper validation** without changing persistence or existing public route signatures.
- [ ] **Step 4: Run focused and related configurator tests**:
  `cd backend && pytest tests/test_configurator_catalog_contract.py tests/test_configurator_vehicle_readiness.py tests/test_configurator_runtime_capabilities.py -q`.
- [ ] **Step 5: Commit** with `git add backend/configurator_schemas.py backend/tests/test_configurator_catalog_contract.py && git commit -m "feat: enforce configurator catalog identity"`.

### Task 2: Complete deterministic vehicle readiness

**Files:**
- Modify: `backend/configurator_vehicle_readiness.py`
- Modify only if route behavior requires it: `backend/configurator_vehicle_readiness_routes.py`
- Test: `backend/tests/test_configurator_vehicle_readiness.py`
- Test: `backend/tests/test_configurator_vehicle_readiness_route.py`

**Interfaces:**
- Preserve `assess_vehicle_configurator_readiness(vehicle, pricing, colors, wheels, interiors, asset)`.
- Preserve `GET /api/v1/configurator/variants/{variant_id}/readiness`.

- [ ] **Step 1: Write failing tests** for missing/inactive/unverified vehicle, missing/unverified/mismatched pricing, missing compatible color/wheel/interior, and invalid asset publication/provenance/license/integrity evidence.
- [ ] **Step 2: Run the focused readiness tests** and verify RED only for missing required behavior.
- [ ] **Step 3: Implement deterministic blocker evaluation** while retaining existing readiness behavior and warning semantics.
- [ ] **Step 4: Run `cd backend && pytest tests/test_configurator_vehicle_readiness.py tests/test_configurator_vehicle_readiness_route.py -q`** and require GREEN.
- [ ] **Step 5: Commit** with `git add backend/configurator_vehicle_readiness.py backend/configurator_vehicle_readiness_routes.py backend/tests/test_configurator_vehicle_readiness.py backend/tests/test_configurator_vehicle_readiness_route.py && git commit -m "feat: harden configurator readiness gate"`.

### Task 3: Preserve authoritative pricing and compatibility

**Files:**
- Inspect/modify: `backend/pricing_engine.py`
- Inspect/modify: `backend/configurator_routes.py`
- Test: `backend/tests/test_configurator_pricing_authority.py`

**Interfaces:**
- Preserve `calculate_configuration_price(request, db) -> ConfigurationPriceResponse`.

- [ ] **Step 1: Write failing tests** proving absent/unverified `variant_pricing` blocks production pricing and unavailable selected options cannot be priced.
- [ ] **Step 2: Run `cd backend && pytest tests/test_configurator_pricing_authority.py -q`** and verify RED.
- [ ] **Step 3: Implement only the missing authority checks**; keep any compatibility fallback only where current non-production behavior requires it.
- [ ] **Step 4: Run `cd backend && pytest tests/test_configurator_pricing_authority.py tests/test_configurator_vehicle_readiness.py -q`**.
- [ ] **Step 5: Commit** with `git add backend/pricing_engine.py backend/configurator_routes.py backend/tests/test_configurator_pricing_authority.py && git commit -m "feat: enforce authoritative configurator pricing"`.

### Task 4: Harden AI catalog authority

**Files:**
- Modify: `backend/configurator_ai.py`
- Modify if required by tests: the existing configurator AI test module containing `resolve_ai_selection`

**Interfaces:**
- Preserve `resolve_ai_selection(intent, db)`.

- [ ] **Step 1: Write a failing test** where the model proposes an unknown option ID and assert that the resolved configuration does not accept it.
- [ ] **Step 2: Run the smallest relevant AI test and verify RED**.
- [ ] **Step 3: Implement minimum catalog filtering/fallback** so only backend-supplied option IDs can survive resolution.
- [ ] **Step 4: Run AI, pricing, readiness, and rules-engine configurator tests together**.
- [ ] **Step 5: Commit** with `git add backend/configurator_ai.py backend/tests && git commit -m "feat: constrain AI to verified configurator catalog"`.

### Task 5: Harden saved-configuration freshness

**Files:**
- Modify: the existing saved-configuration module containing `revalidate_saved_configuration`
- Test: its existing freshness test module

**Interfaces:**
- Preserve `revalidate_saved_configuration(saved_document, current_price_resolver, current_asset_resolver)`.
- Preserve `assess_saved_configuration_freshness(saved_document, current_price_snapshot, current_asset)`.

- [ ] **Step 1: Write failing tests** for authoritative price changes and published asset active-revision changes.
- [ ] **Step 2: Run the focused freshness tests and verify RED**.
- [ ] **Step 3: Implement stale-state comparison** without changing the user's selected purchasable options.
- [ ] **Step 4: Run the focused freshness suite plus all configurator backend tests**.
- [ ] **Step 5: Commit** with a message describing saved-configuration freshness authority.

### Task 6: Validate the side-effect-free onboarding contract

**Files:**
- Create: `backend/configurator_onboarding_contract.py`
- Test: `backend/tests/test_configurator_onboarding_contract.py`
- Create/verify: `docs/CONFIGURATOR_PRODUCTION_ONBOARDING.md`

**Interfaces:**
- `validate_onboarding_record_set(records: ConfiguratorOnboardingRecordSet) -> OnboardingValidationResult`.
- The validator performs no MongoDB writes and delegates eligibility to `assess_vehicle_configurator_readiness(...)`.

- [ ] **Step 1: Write failing tests** for missing verified pricing, missing compatible options, missing/unpublishable asset evidence, and record immutability/no database access.
- [ ] **Step 2: Run `cd backend && pytest tests/test_configurator_onboarding_contract.py -q`** and verify RED.
- [ ] **Step 3: Implement the pure validator** with deterministic errors/warnings.
- [ ] **Step 4: Run the focused contract tests and existing readiness tests**.
- [ ] **Step 5: Verify documentation** covers `OEM/licensed source → vehicle verification → manifest → authoritative production DB → pricing → options → asset intake/review/publication → readiness` and explicitly labels temporary/non-OEM assets as non-production.
- [ ] **Step 6: Commit** with `git add backend/configurator_onboarding_contract.py backend/tests/test_configurator_onboarding_contract.py docs/CONFIGURATOR_PRODUCTION_ONBOARDING.md && git commit -m "feat: add production configurator onboarding contract"`.

### Task 7: Add safe production diagnostics and manifest validation

**Files:**
- Create/modify: `backend/configurator_production_diagnostics.py`
- Create/modify: `backend/configurator_database_authority.py`
- Create/modify: `backend/configurator_vehicle_catalog_manifest.py`
- Test: corresponding diagnostics and manifest test modules
- Inspect: `render.yaml`

**Interfaces:**
- `assess_database_authority(configured_database_name, expected_database_name) -> dict[str, object]`.
- `assess_production_configurator_diagnostics(configured_database_name, expected_database_name, variant_count, pricing_count, asset_count) -> dict[str, object]`.
- `validate_catalog_manifest(manifest) -> ConfiguratorVehicleCatalogManifest | list[ConfiguratorVehicleCatalogManifest]`.

- [ ] **Step 1: Write failing tests** for explicit database-name mismatch, missing expected database, secret exclusion, verified/active/AVAILABLE manifest requirements, duplicate variant IDs, and legacy identity rejection.
- [ ] **Step 2: Run the focused diagnostics/manifest tests and verify RED**.
- [ ] **Step 3: Implement pure validation/formatting only**; do not add a public unauthenticated diagnostics endpoint and do not read or change Render secrets.
- [ ] **Step 4: Run focused tests plus independence validation**.
- [ ] **Step 5: Commit** with `git add backend/configurator_production_diagnostics.py backend/configurator_database_authority.py backend/configurator_vehicle_catalog_manifest.py backend/tests && git commit -m "feat: add safe configurator production diagnostics"`.

### Task 8: Make asset intake and revision evidence authoritative

**Files:**
- Create/modify: `backend/configurator_asset_intake.py`
- Create/modify: `backend/configurator_asset_revision.py`
- Modify: `backend/configurator_runtime_capabilities.py`
- Modify: `backend/configurator_routes.py`
- Test: `backend/tests/test_configurator_asset_intake.py`
- Test: `backend/tests/test_configurator_asset_revision.py`
- Test: `backend/tests/test_configurator_asset_revision_runtime.py`
- Test: `backend/tests/test_configurator_runtime_capabilities.py`

**Interfaces:**
- `validate_asset_intake(request, expected_variant_id=None) -> AssetIntakeValidationResult`.
- `can_transition_revision(current, target) -> bool`.
- `select_active_revision(active_revision_id, revisions, expected_variant_id=None) -> ConfiguratorAssetRevision`.
- Preserve `build_runtime_capability_contract(db, variant_id)`.
- Preserve `resolve_saved_configuration_asset(db, variant_id, requested_asset_id)`.

- [ ] **Step 1: Write failing tests** for provenance/license/integrity, temporary assets, revision transitions, missing/superseded/unpublished/cross-variant active revisions, and arbitrary requested asset IDs.
- [ ] **Step 2: Run focused asset/revision/runtime tests and verify RED**.
- [ ] **Step 3: Implement minimal evidence and revision resolution contracts**, keeping revisions nested under `configurator_assets`.
- [ ] **Step 4: Verify runtime exposes only the selected published revision's metadata and URL.
- [ ] **Step 5: Run asset, runtime, saved-configuration, readiness, and pricing tests**.
- [ ] **Step 6: Commit** with `git add backend/configurator_asset_intake.py backend/configurator_asset_revision.py backend/configurator_runtime_capabilities.py backend/configurator_routes.py backend/tests && git commit -m "feat: make configurator asset revisions authoritative"`.

### Task 9: Gate the frontend on backend readiness

**Files:**
- Modify: `frontend/src/services/configuratorApi.js`
- Modify only relevant configurator page/components
- Test: existing frontend configurator test modules

**Interfaces:**
- Frontend consumes the backend readiness/runtime contract.
- `ready === false` must produce an explicit unavailable/coming-soon state and must not initialize an unverified asset.

- [ ] **Step 1: Write a failing frontend test** for false readiness and absence of a usable runtime asset.
- [ ] **Step 2: Run `cd frontend && CI=true npm test -- --watchAll=false --runInBand`** and verify RED for the new behavior.
- [ ] **Step 3: Implement minimal readiness gating while preserving request deduplication and lifecycle ownership.
- [ ] **Step 4: Run focused frontend tests and `cd frontend && npm run build`.
- [ ] **Step 5: Commit** with `git add frontend/src/services/configuratorApi.js frontend/src && git commit -m "feat: gate configurator UI on backend readiness"`.

### Task 10: Full regression, review, and draft-PR verification

**Files:** all changed files; documentation required by verified implementation.

- [ ] **Step 1: Run backend configurator regression**: `cd backend && pytest tests/test_configurator*.py -q`.
- [ ] **Step 2: Run frontend regression**: `cd frontend && CI=true npm test -- --watchAll=false --runInBand`.
- [ ] **Step 3: Run frontend production build**: `cd frontend && npm run build`.
- [ ] **Step 4: Run repository validation/independence checks and inspect GitHub Actions results for the current head SHA.**
- [ ] **Step 5: Review the complete diff for synthetic vehicle/pricing/asset records, hardcoded production DB selection, credentials, arbitrary asset fallback, unverified OEM claims, and main-branch mutations.**
- [ ] **Step 6: Request code review on PR #66 after verification.**
- [ ] **Step 7: Keep PR #66 draft and unmerged; do not merge without explicit user approval.**
