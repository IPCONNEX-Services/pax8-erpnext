import hmac

import frappe
from frappe import _


def _prev_month_period() -> str:
    """Return billing period for the previous month as YYYY-MM."""
    from datetime import timedelta

    from frappe.utils import now_datetime

    first_of_this_month = now_datetime().replace(day=1)
    last_month = first_of_this_month - timedelta(days=1)
    return last_month.strftime("%Y-%m")


@frappe.whitelist(allow_guest=True)
def handle():
    """Webhook endpoint for Pax8 INVOICE.CREATED events."""
    pax8_settings_name = frappe.request.args.get("settings")
    if not pax8_settings_name:
        frappe.throw(_("Missing 'settings' query parameter"), frappe.PermissionError)

    settings = frappe.get_doc("Pax8 Settings", pax8_settings_name)
    webhook_secret = settings.get_password("webhook_secret")

    if not webhook_secret:
        frappe.throw(_("Webhook secret not configured on Pax8 Settings."), frappe.PermissionError)
    auth_header = frappe.request.headers.get("Authorization", "")
    if not hmac.compare_digest(auth_header, f"Bearer {webhook_secret}"):
        frappe.throw(_("Invalid webhook authorization"), frappe.PermissionError)

    import json

    payload = frappe.request.get_data(as_text=True)
    try:
        event = json.loads(payload)
    except Exception:
        frappe.throw(_("Invalid JSON payload"), frappe.ValidationError)

    topic = event.get("topic", "")
    action = event.get("action", "")
    entity_id = event.get("entityId") or event.get("entity_id") or ""

    frappe.logger("erpnext_pax8").debug(
        f"Pax8 webhook received: {topic}.{action} entity={entity_id}"
    )

    if topic == "INVOICE" and action == "CREATED":
        _handle_invoice_created(entity_id, pax8_settings_name)

    return {"status": "ok"}


def _handle_invoice_created(invoice_id: str, pax8_settings: str):
    """Trigger invoice import when Pax8 fires INVOICE.CREATED."""
    billing_period = _prev_month_period()

    existing = frappe.db.get_value(
        "Pax8 Import Log",
        {
            "pax8_settings": pax8_settings,
            "billing_period": billing_period,
            "status": ["in", ["running", "completed"]],
        },
        "name",
    )
    if existing:
        frappe.logger("erpnext_pax8").info(
            f"Pax8 webhook: import for {billing_period} already running/completed ({existing}), skipping"
        )
        return

    frappe.enqueue(
        "erpnext_pax8.api.import_invoices.import_period",
        pax8_settings=pax8_settings,
        billing_period=billing_period,
        triggered_by="webhook",
        queue="long",
        now=False,
    )


@frappe.whitelist()
def register_webhook(pax8_settings: str) -> dict:
    """Register the INVOICE.CREATED webhook endpoint with Pax8."""
    import urllib.parse

    from erpnext_pax8.utils.pax8_client import get_pax8_client

    settings = frappe.get_doc("Pax8 Settings", pax8_settings)
    webhook_secret = settings.get_password("webhook_secret")
    if not webhook_secret:
        frappe.throw(_("Set a Webhook Bearer Secret on Pax8 Settings before registering."))

    encoded_name = urllib.parse.quote(pax8_settings)
    endpoint_url = (
        f"{frappe.utils.get_url()}/api/method/erpnext_pax8.api.webhook.handle"
        f"?settings={encoded_name}"
    )

    client = get_pax8_client(pax8_settings)
    result = client.register_webhook(endpoint_url, webhook_secret)
    return {"endpoint_url": endpoint_url, "pax8_response": result}
