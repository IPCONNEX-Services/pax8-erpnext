from collections import defaultdict

import frappe
from frappe import _

from erpnext_pax8.utils.invoice_builder import create_purchase_invoice, create_sales_invoice
from erpnext_pax8.utils.pax8_client import get_pax8_client


@frappe.whitelist()
def import_period(pax8_settings: str, billing_period: str, triggered_by: str = "manual") -> dict:
    """
    Import Pax8 invoices for a billing period (YYYY-MM).
    Creates one Purchase Invoice and one Sales Invoice per matched customer.
    Idempotent: skips if a completed or running Import Log exists for this period.
    """
    existing_log = frappe.db.get_value(
        "Pax8 Import Log",
        {
            "pax8_settings": pax8_settings,
            "billing_period": billing_period,
            "status": ["in", ["running", "completed"]],
        },
        "name",
    )
    if existing_log:
        msg = (
            f"Import for {billing_period} already in progress or completed (log: {existing_log}). "
            "Delete the log to re-import."
        )
        frappe.throw(_(msg))

    settings = frappe.get_doc("Pax8 Settings", pax8_settings)
    log = frappe.new_doc("Pax8 Import Log")
    log.pax8_settings = pax8_settings
    log.billing_period = billing_period
    log.status = "running"
    log.triggered_by = triggered_by
    log.insert(ignore_permissions=True)
    frappe.db.commit()

    try:
        client = get_pax8_client(pax8_settings)

        invoices = client.get_invoices(billing_period)
        if not invoices:
            frappe.db.set_value("Pax8 Import Log", log.name, {
                "status": "failed",
                "error_log": f"No invoices found for period {billing_period}",
            })
            frappe.db.commit()
            return {
                "status": "failed",
                "log": log.name,
                "purchase_invoice": None,
                "sales_invoices_created": 0,
                "customers_matched": 0,
                "customers_unmatched": 0,
            }

        all_items = []
        for invoice in invoices:
            invoice_id = invoice.get("id")
            items = client.get_invoice_items(invoice_id)
            all_items.extend(items)

        pi_name = create_purchase_invoice(all_items, billing_period, settings)

        by_company = defaultdict(list)
        for item in all_items:
            company_id = item.get("companyId") or item.get("company_id")
            if company_id:
                by_company[company_id].append(item)

        sales_count = 0
        matched = 0
        unmatched = 0
        error_lines = []

        for pax8_company_id, company_items in by_company.items():
            pax8_customer_name = frappe.db.get_value(
                "Pax8 Customer",
                {"pax8_company_id": pax8_company_id, "pax8_settings": pax8_settings},
                "name",
            )

            if not pax8_customer_name:
                error_lines.append(f"No Pax8 Customer doc for company ID: {pax8_company_id}")
                unmatched += 1
                continue

            pax8_customer = frappe.get_doc("Pax8 Customer", pax8_customer_name)
            if not pax8_customer.customer:
                error_lines.append(
                    f"Unmatched: {pax8_customer.pax8_company_name} ({pax8_company_id})"
                )
                unmatched += 1
                continue

            try:
                create_sales_invoice(
                    customer=pax8_customer.customer,
                    items=company_items,
                    billing_period=billing_period,
                    company=settings.company,
                )
                sales_count += 1
                matched += 1
            except Exception as e:
                error_lines.append(
                    f"Failed SI for {pax8_customer.pax8_company_name}: {e}"
                )
                unmatched += 1

        frappe.db.set_value("Pax8 Import Log", log.name, {
            "status": "completed",
            "purchase_invoice": pi_name,
            "sales_invoices_created": sales_count,
            "customers_matched": matched,
            "customers_unmatched": unmatched,
            "error_log": "\n".join(error_lines) if error_lines else None,
        })
        frappe.db.set_value("Pax8 Settings", pax8_settings, "last_imported_at", frappe.utils.now())
        frappe.db.commit()

        if unmatched:
            frappe.publish_realtime(
                "msgprint",
                {
                    "message": f"Pax8 import {billing_period}: {unmatched} unmatched customers skipped. Review Pax8 Customer list.",
                    "alert": True,
                },
            )

        return {
            "status": "completed",
            "log": log.name,
            "purchase_invoice": pi_name,
            "sales_invoices_created": sales_count,
            "customers_matched": matched,
            "customers_unmatched": unmatched,
        }

    except Exception:
        import traceback
        frappe.db.set_value("Pax8 Import Log", log.name, {
            "status": "failed",
            "error_log": traceback.format_exc(),
        })
        frappe.db.commit()
        raise
