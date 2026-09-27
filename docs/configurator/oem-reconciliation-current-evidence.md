# Current OEM Reconciliation Evidence

## Kia Seltos legacy record

The legacy `autoai.cars` collection contains the record:

- Legacy ID: `kia-seltos`
- Brand: Kia
- Model: Seltos
- Variant: GTX+
- Fuel: Petrol
- Transmission: Automatic

The current Kia India Seltos showroom/specification pages reviewed on 2026-09-19 list the current trim family as:

`HTE, HTE(O), HTK, HTK(O), HTX, HTX(A), GTX, X-Line, GTX(A), X-Line(A), GTX(O), X-Line(O)`.

The current official pages do **not** list a `GTX+` trim in the reviewed trim family.

### Reconciliation decision

The legacy `GTX+` record remains:

`REVIEW_REQUIRED`

It must **not** be silently renamed to `GTX`, `GTX(A)`, `GTX(O)`, or another current trim.

This is an evidence checkpoint, not a production catalog record. It does not authorize pricing, options, colours, wheels, interiors, or 3D assets.

### Authoritative sources reviewed

1. Kia India Seltos showroom:
   https://www.kia.com/in/our-vehicles/seltos/showroom.html
2. Kia India Seltos specifications:
   https://www.kia.com/in/our-vehicles/seltos/specs.html

The official Kia pages also state that product colour, features, and price may vary and advise checking with a local Kia dealer. Any production configurator onboarding therefore requires the separate evidence gates already defined by Auto AI India.

## Policy

An OEM name similarity is not sufficient for canonical mapping. A legacy record may enter the production onboarding flow only after its identity and all required catalog/asset evidence have been explicitly verified.

Temporary or inferred mappings remain non-publishable.
