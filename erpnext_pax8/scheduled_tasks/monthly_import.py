import frappe
from frappe.utils import now_datetime


def run_if_due():
    """
    Daily scheduled task. Triggers invoice import if:
    - today's day-of-month matches settings.import_day_of_month
    - no completed Import Log exists for the current billing period
    """
    today = now_datetime()
    billing_period = today.strftime("%Y-%m")

    all_settings = frappe.get_all(
        "Pax8 Settings",
        fields=["name", "import_day_of_month"],
    )

    for s in all_settings:
        if today.day != (s.import_day_of_month or 5):
            continue

        existing = frappe.db.get_value(
            "Pax8 Import Log",
            {"pax8_settings": s.name, "billing_period": billing_period, "status": "completed"},
            "name",
        )
        if existing:
            frappe.logger("erpnext_pax8").debug(
                f"Pax8 scheduler: import for {billing_period} already completed, skipping {s.name}"
            )
            continue

        frappe.logger("erpnext_pax8").info(
            f"Pax8 scheduler: triggering import for {billing_period} via {s.name}"
        )
        frappe.enqueue(
            "erpnext_pax8.api.import_invoices.import_period",
            pax8_settings=s.name,
            billing_period=billing_period,
            triggered_by="scheduler",
            queue="long",
            now=False,
        )
