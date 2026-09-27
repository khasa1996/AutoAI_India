# OEM Evidence Package

The OEM evidence package is the explicit, read-only evidence contract used before a vehicle variant can enter configurator onboarding.

## Required identity

The package carries the authoritative vehicle identity already defined by the reconciliation boundary:

- brand/model/variant
- fuel and transmission
- verification status
- authoritative HTTPS source
- optional model-year and effective-date scope

No identity is inferred from a legacy name, ID, image, price, or trim similarity.

## Catalog evidence

The package carries the six production evidence gates:

1. verified pricing
2. compatible colours
3. compatible wheels
4. compatible interiors
5. licensed/authorized 3D asset
6. published active 3D asset revision

## 3D asset evidence

When licensed 3D evidence is claimed, the package requires:

- asset ID
- revision ID
- provenance
- license name
- publisher
- SHA-256 checksum
- file size within the 200 MB limit
- validation passed
- published state

Temporary, AI-generated, unknown, or otherwise non-publishable assets cannot be used to satisfy the production evidence contract.

## States

- `REVIEW_REQUIRED`: identity or structural evidence is not acceptable.
- `EVIDENCE_REQUIRED`: authoritative identity is verified, but required catalog evidence is incomplete.
- `READY`: all package evidence gates are satisfied.

`READY` is an onboarding candidate only. This module performs no MongoDB reads or writes and does not publish production catalog records.
