# Production Configurator Onboarding Gate

The production configurator uses the `autoai` MongoDB database as its authoritative catalog boundary.

## Activation rule

A variant may be exposed to the production 3D configurator only when the backend readiness contract returns `ready: true`.

Required evidence:

- verified canonical variant identity;
- authoritative verified pricing with source evidence;
- compatible color, wheel, and interior records for the exact variant;
- exact published and technically validated 3D asset;
- production-suitable asset provenance and licensing;
- validated semantic material, mesh, camera, and interaction mappings.

## Data safety

This gate does not insert, update, delete, migrate, copy, or infer production catalog records.

No synthetic vehicle, pricing, option, or asset data may be used to satisfy readiness.

The legacy `auto_ai` database and legacy `cars` collection are not fallback sources for production configurator activation.

## Operational sequence

1. Acquire source-backed vehicle identity evidence.
2. Validate canonical brand/model/variant relationships.
3. Acquire authoritative pricing evidence.
4. Validate exact-variant colors, wheels, and interiors.
5. Acquire licensed/provenance-backed 3D asset evidence.
6. Validate asset checksum, revision, publication state, and runtime mappings.
7. Run the variant readiness endpoint.
8. Expose the variant only when all blockers are cleared.
