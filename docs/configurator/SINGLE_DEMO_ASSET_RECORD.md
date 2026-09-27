# Single Demo Asset Record

The isolated demonstrator uses the following generic vehicle asset:

- Display identity: **Aureon GT**
- Source asset: **City car — Car Park and Road Vehicle Fleet**
- Source publisher: 3DAssets.dev
- Asset URL: https://cdn.3dassets.dev/assets/32487/v1/model.glb
- License: **CC0 1.0 Universal**, as stated by the source
- Approximate geometry: 31,000 triangles
- Published animations: door open/close, bonnet open/close, boot open/close, steer, wheel roll
- Intended use in Auto AI India: visual demonstrator only
- Production catalog impact: none

The source describes this asset as a generic road vehicle and explicitly states commercial use and modification are permitted under CC0. The application does not identify it as a Porsche, Panamera, or any other OEM product.

This asset is not an OEM production asset and must not be represented as verified OEM geometry, pricing, trim data, or sponsorship.

Future OEM vehicles must continue through the normal provenance, licensing, asset validation, compatibility, pricing, and publication gates in the production autoai catalog.

## Runtime boundary

The demo is exposed at /configurator-demo and is intentionally separate from /configurator/:variantId. It does not write demo vehicle, pricing, option, or asset records to MongoDB.