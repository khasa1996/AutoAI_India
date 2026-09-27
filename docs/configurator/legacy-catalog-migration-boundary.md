# Legacy catalog migration boundary

The existing `cars` collection is a legacy flat vehicle dataset. It is useful as
migration input but is **not** a production configurator catalog.

## Adapter contract

`backend/legacy_configurator_adapter.py` converts legacy records into canonical
identity candidates without writing to MongoDB.

Every candidate remains:

- `verification_status: unverified`
- `configurator_status: COMING_SOON`
- `migration_status: REVIEW_REQUIRED`
- linked to the original `legacy_car_id`

The adapter does not manufacture pricing, options, 3D assets, provenance,
licenses, checksums, or publication evidence.

## Promotion boundary

A candidate must later be replaced by authoritative, verified records for:

1. Brand/model/variant identity.
2. Variant pricing and city pricing.
3. Compatible colors, wheels, and interiors.
4. Authorized/licensed 3D asset and published active revision.
5. Source/provenance and validation evidence.

Only then can the existing readiness contract evaluate the variant as production-ready.

No production database writes are performed by this adapter.

## Current OEM reconciliation checkpoint

A legacy record is not considered current merely because its brand/model names still exist.
The legacy database currently contains `Kia Seltos / GTX+` as one candidate. Kia India's current Seltos showroom/specification pages list the current trim family as HTE, HTE(O), HTK, HTK(O), HTX, HTX(A), GTX, X-Line, GTX(A), X-Line(A), GTX(O), and X-Line(O). The current official pages do not list `GTX+` as a current Seltos trim.

Therefore this legacy record must remain `REVIEW_REQUIRED` until a current authoritative OEM identity mapping is established. The adapter must not silently rename it, infer a successor trim, or promote its legacy price/specification data.

Official current source used for this checkpoint:
- https://www.kia.com/in/our-vehicles/seltos/showroom.html
- https://www.kia.com/in/our-vehicles/seltos/specs.html

This is a reconciliation example, not a production catalog record. No MongoDB catalog records are created by this checkpoint.
