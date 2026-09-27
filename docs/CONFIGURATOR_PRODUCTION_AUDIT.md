# Configurator Production Audit

The production audit is intentionally read-only.

## Endpoint

`GET /api/v1/admin/configurator/catalog-audit`

The endpoint requires the existing admin authentication dependency.

## What it checks

- Counts all authoritative configurator catalog collections.
- Counts active, verified, `AVAILABLE` variants.
- Detects verified/available variants without authoritative pricing.
- Counts published and validation-passed configurator assets.
- Explicitly reports that the audit performed no production data write.

## What it does not do

- It does not seed vehicles.
- It does not infer specifications or prices.
- It does not copy legacy `cars` records into the configurator catalog.
- It does not publish assets.
- It does not modify Render environment variables.
- It does not change existing production records.

The audit is an operational readiness signal. A variant becomes customer-facing only through the existing backend readiness and asset publication contracts.
