import frappe
from frappe.utils import now_datetime


def run_if_due():
    """
    Scheduled task — fires once per day at 01:00 site-local-time (see hooks.py).
    For each Pax8 Settings, enqueues an import_period for the *current* month
    unless an Import Log is already running/completed for that period.

    Pax8 issues invoices with invoiceDate = 1st of the current month (advance
    billing), so we poll for the current month. Daily polling acts as a backstop;
    if Pax8 hasn't issued yet, the import is marked `failed` and retried the
    next day. Once a run succeeds, subsequent days short-circuit on the dedup
    guard.
    """
    today = now_datetime()
    billing_period = today.strftime("%Y-%m")

    all_settings = frappe.get_all("Pax8 Settings", fields=["name"])

    for s in all_settings:
        existing = frappe.db.get_value(
            "Pax8 Import Log",
            {
                "pax8_settings": s.name,
                "billing_period": billing_period,
                "status": ["in", ["running", "completed"]],
            },
            "name",
        )
        if existing:
            frappe.logger("erpnext_pax8").debug(
                f"Pax8 scheduler: import for {billing_period} already running/completed, skipping {s.name}"
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
