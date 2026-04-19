# Pax8 for ERPNext

## Purpose
Imports Pax8 monthly invoices into ERPNext as Purchase Invoices and/or Sales Invoices.
Runs as a daily scheduled task that checks whether a monthly import is due.
Published on the Frappe Cloud marketplace. Version: 1.0.0.

## Paid Tier
FREE — all features included at no cost.

## Tech Stack
- Frappe v15+ / ERPNext v15+
- Python 3.10+
- Pax8 REST API (OAuth2 client credentials)
- ruff for linting

## Key Files
- `erpnext_pax8/hooks.py` — scheduler registration (daily job), doctype_js for Pax8 Settings
- `erpnext_pax8/api/` — Pax8 API client, authentication, invoice fetching
- `erpnext_pax8/config/` — configuration DocType definitions
- `erpnext_pax8/pax8_payments/` — Payment DocTypes
- `erpnext_pax8/scheduled_tasks/monthly_import.py` — `run_if_due()` entry point
- `erpnext_pax8/utils/` — shared helpers
- `.github/workflows/ci.yml` — CI: lint + import-check

## Common Tasks

### Modify the import logic
- Entry point: `erpnext_pax8/scheduled_tasks/monthly_import.py` → `run_if_due()`
- API calls live in `erpnext_pax8/api/`
- ERPNext document creation is in the scheduled task or a helper in utils

### Add a new Pax8 API endpoint
1. Add a method to the API client in `erpnext_pax8/api/`
2. Use the existing OAuth2 token pattern for authentication
3. Add a test (create `tests/` if it doesn't exist yet)

### Add a settings field
1. Edit the Pax8 Settings DocType JSON in `erpnext_pax8/config/` or `erpnext_pax8/pax8_payments/`
2. Update `js/pax8_settings.js` if the field needs client-side behavior
3. Write a patch if existing installs need migration

### Trigger import manually (for testing on bench)
```bash
bench --site site_name execute erpnext_pax8.scheduled_tasks.monthly_import.run_if_due
```

### Cut a release
1. Bump version in `setup.py` and `erpnext_pax8/hooks.py` (app_version)
2. Follow Release Procedure in the Frappe/ERPNext skill.

## Gotchas
- `run_if_due()` must check whether the monthly import already ran this month before proceeding — importing twice creates duplicate invoices
- Pax8 uses OAuth2 client credentials — token must be refreshed before expiry; do not store tokens in the database
- `setup.py` hardcodes version `"1.0.0"` — update both setup.py and hooks.py when releasing
- No tests/ folder yet — when adding tests, use pytest and mock the Pax8 API calls

## Secrets
Pax8 API client ID and secret — to be provided for testing. Store in Pax8 Settings DocType (encrypted field), never hardcoded.
