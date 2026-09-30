# Production vehicle onboarding

A vehicle variant may be exposed as a production configurator vehicle only when the readiness contract passes.

## Required evidence

- Active, verified variant identity.
- Authoritative verified pricing with source.
- Available color, wheel, and interior options for the exact variant.
- Exact published, technically validated, reviewed 3D asset assigned to the variant.
- Asset provenance and licensing suitable for production publication.
- At least one auditable provenance evidence record with `VERIFIED` status, a reference, verifier identity, and verification timestamp.
- Semantic material/mesh/animation mappings matching the inspected asset.

The readiness API is deterministic and reports blockers instead of inventing missing data. A failed readiness check must remain a `3D Coming Soon`/unavailable state.

## First production vehicle

GitHub issue #60 tracks the first authorized production asset onboarding. The external vehicle data and asset rights are intentionally not fabricated in the repository.


## Publication authority

A provenance label alone is not evidence of rights. Production publication requires a verified evidence record attached to the asset, such as an OEM authorization, license agreement/record, provenance record, or rights declaration.

The publication gate must remain closed when evidence is missing, pending, rejected, or unverifiable. Temporary/demo assets must not be promoted by changing metadata alone; their actual rights and binary must pass the same evidence and technical validation chain.
