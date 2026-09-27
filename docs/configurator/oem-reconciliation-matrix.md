# Configurator OEM Reconciliation Matrix

## Purpose

This matrix is the controlled boundary between the legacy `cars` collection and the production Ultra 3D Configurator catalog.

It is a **review artifact**, not a production catalog. Building the matrix must never insert, update, or delete MongoDB configurator records.

## Status model

| Status | Meaning | Production publication |
|---|---|---|
| `REVIEW_REQUIRED` | Authoritative identity is missing, mismatched, or unverified | Blocked |
| `IDENTITY_VERIFIED` | Identity is explicitly reconciled, but required catalog/asset evidence is incomplete | Blocked |
| `READY_FOR_ONBOARDING` | Identity and all required evidence are present | May enter the existing onboarding/readiness gate |

## Evidence required for readiness

A vehicle cannot be treated as production-ready until all of these are explicitly verified:

1. Canonical OEM/authoritative variant identity.
2. Authoritative pricing.
3. Compatible exterior colours.
4. Compatible wheels.
5. Compatible interiors.
6. Licensed/authorized 3D asset.
7. Published active asset revision.

The existing onboarding contract remains the final readiness authority. A reconciliation result of `READY_FOR_ONBOARDING` does **not** itself create or publish a catalog record.

## Review rules

- Legacy `cars` records are migration inputs only.
- Never infer an OEM mapping solely from a legacy ID, name, image, or seeded price.
- Never silently rename a legacy variant to force a match.
- Preserve the legacy ID for auditability.
- Require explicit source and HTTPS source URL for authoritative identity.
- Keep unresolved vehicles blocked.
- Do not use temporary 3D assets as verified production assets.
- Any temporary asset used during development must remain visibly tagged as temporary/non-verified and must not satisfy the production asset gate.

## Current state

The project has 106 legacy car records available as migration input. No canonical configurator vehicle records have been created from them.

The matrix builder can process those records without database mutation. Actual OEM identity and evidence mappings must be supplied separately after review.

## Read-only reporting

The reconciliation matrix can be summarized without persistence through the summarize_reconciliation_matrix() function. The report contains:

- total legacy records processed;
- counts for each reconciliation status;
- deterministic blocker counts;
- legacy IDs that are ready for onboarding;
- legacy IDs that remain blocked.

The reporting layer does not create canonical catalog records, modify legacy records, or change publication state. It is suitable for a 106-record review run before authoritative OEM mappings and catalog evidence are supplied.
