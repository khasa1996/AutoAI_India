# OEM Evidence Review Queue

The OEM evidence review queue is a **read-only review artifact** between the
legacy `cars` collection and the production Ultra 3D Configurator catalog.

## Contract

Each `OemEvidenceReviewItem` records:

- the legacy vehicle identity and legacy ID;
- reconciliation status and derived review state;
- an explicitly supplied canonical variant identity, when one exists;
- the authoritative source and HTTPS source URL, when supplied;
- temporal identity scope (`model_year`, `effective_from`, `effective_to`), when supplied;
- six evidence gates: pricing, compatible colours, wheels, interiors,
  licensed 3D asset, and published asset revision;
- blockers returned by the reconciliation engine.

The queue is sorted by `legacy_car_id` and does not mutate its inputs.

## Review states

| State | Meaning |
|---|---|
| `REVIEW_REQUIRED` | Authoritative identity is missing or does not reconcile. |
| `EVIDENCE_REQUIRED` | Identity is explicitly verified, but one or more catalog evidence gates remain incomplete. |
| `READY` | Identity and every required catalog evidence gate are satisfied. |

A `READY` item is still a review/onboarding candidate; it is not a production
write and does not publish a vehicle or 3D asset.

## Non-inference rule

The queue never derives an OEM mapping from a legacy name, legacy ID, image,
seeded price, or similarity. An identity must be supplied explicitly with its
authoritative source. Temporary/unverified 3D assets cannot satisfy the
production evidence gate.

## Current Seltos checkpoint

The live legacy record is `kia-seltos` / Kia Seltos / GTX+ / Petrol /
Automatic. The current OEM reconciliation evidence records that the reviewed
Kia India Seltos showroom/specification pages do not list GTX+ in the current
trim family. Therefore this legacy record remains `REVIEW_REQUIRED`; it must
not be silently renamed to another trim.

## Persistence boundary

This module performs no MongoDB reads or writes. It is safe to use in CI,
offline review tooling, or an administrative evidence workflow before any
production catalog mutation is considered.
