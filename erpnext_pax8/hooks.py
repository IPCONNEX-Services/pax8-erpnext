app_name = "erpnext_pax8"
app_title = "Pax8 for ERPNext"
app_publisher = "IPCONNEX Services"
app_description = "Import Pax8 monthly invoices into ERPNext as Purchase and Sales Invoices"
app_email = "dev@ipconnex.com"
app_license = "MIT"
app_version = "1.0.0"

scheduler_events = {
    "daily": [
        "erpnext_pax8.scheduled_tasks.monthly_import.run_if_due",
    ]
}
