# Production 3D Asset Intake Package

This checklist defines the minimum evidence package required before Auto AI India can onboard a real production vehicle asset.

## 1. Vehicle identity

Provide:

- brand identifier
- model identifier
- exact variant identifier
- fuel/powertrain
- model year or applicable model period
- authoritative source for the variant identity
- verification status

The repository must not infer a production variant from a filename, image, or third-party listing.

## 2. Commercial data

Provide:

- authoritative ex-showroom price
- currency
- market/state/city scope where applicable
- effective date
- source reference
- option prices and effective dates where applicable

Pricing must remain backend-authoritative. Client-provided price snapshots are never publication authority.

## 3. Configurator options

For the exact variant, provide the canonical option records for:

- exterior colours
- wheels
- interiors
- roof options where applicable
- accessories/trim where applicable

Each option must have an explicit compatibility relationship with the variant.

## 4. 3D asset package

Provide:

- GLB or GLTF binary
- asset version
- file size
- SHA-256 checksum
- storage key after controlled upload
- inspected mesh/node names
- material names
- animation names
- camera presets
- supported interaction mappings
- LOD information where applicable

Unsupported interactions must remain unavailable. Do not create fake animations or infer interaction mappings from naming alone.

## 5. Rights and provenance

Provide documentary evidence for the actual binary and its intended production use.

Acceptable evidence categories include:

- OEM authorization
- license agreement
- license record
- provenance record
- rights declaration

Every attached evidence record must be:

- `VERIFIED`
- linked to a non-empty reference
- associated with a verifier identity
- associated with a valid verification timestamp

A provenance label by itself is not evidence of rights.

## 6. Technical validation

The asset must pass:

1. file-size limit
2. GLB/GLTF structural validation
3. checksum verification
4. manifest/name validation
5. required capability mapping validation
6. storage/finalization validation

## 7. Administrative approval

Before publication:

- technical validation is passed
- provenance evidence is completely verified
- license and publisher metadata are present
- administrator review is approved
- immutable publication revision exists
- active revision points to the exact published revision

## 8. Runtime acceptance

The final smoke path is:

`variant -> options -> compatibility validation -> authoritative price -> runtime capability contract -> published 3D asset -> viewer`

If any authority gate fails, the public experience must fail closed and show the configured unavailable/3D Coming Soon state rather than inventing or exposing an unverified asset.

## 9. Rollback safety

A rollback target must itself be:

- published
- technically validated
- admin reviewed
- storage-backed with checksum
- backed by complete verified provenance evidence

Rollback must not bypass the current provenance authority rules.

## External input boundary

The following values must come from the authorized asset owner, rights holder, or authoritative commercial/vehicle data source. They must not be fabricated by Auto AI India:

- production vehicle asset
- rights documentation
- canonical variant identity
- production pricing
- exact option availability
- asset capability mappings where they depend on the inspected binary
