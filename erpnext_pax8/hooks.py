app_name = "erpnext_pax8"
app_title = "Pax8 for ERPNext"
app_publisher = "IPCONNEX Services"
app_description = "Import Pax8 monthly invoices into ERPNext as Purchase and Sales Invoices"
app_email = "dev@ipconnex.com"
app_license = "MIT"
app_version = "1.0.0"

required_apps = ["frappe", "erpnext"]

doctype_js = {
    "Pax8 Settings": "js/pax8_settings.js",
}

scheduler_events = {
    # Run at 01:00 in the site's local timezone (DST-stable on tz-aware hosts).
    # Combined with run_if_due's idempotency guard, this is safe to fire daily
    # as a backstop to the Pax8 webhook — first successful import for a given
    # billing_period creates an Import Log; subsequent days short-circuit.
    "cron": {
        "0 1 * * *": [
            "erpnext_pax8.scheduled_tasks.monthly_import.run_if_due",
        ],
    },
}
