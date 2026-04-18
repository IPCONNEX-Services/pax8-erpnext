import frappe

from erpnext_pax8.utils.pax8_client import get_pax8_client


@frappe.whitelist()
def sync_companies(pax8_settings: str) -> dict:
    """
    Pull all active companies from Pax8 and upsert Pax8 Customer docs.
    Returns counts: matched, unmatched, created.
    """
    client = get_pax8_client(pax8_settings)
    companies = client.get_companies()

    matched = 0
    unmatched = 0
    created = 0

    for company in companies:
        company_id = company.get("id")
        company_name = company.get("name", "")

        existing = frappe.db.get_value(
            "Pax8 Customer",
            {"pax8_company_id": company_id, "pax8_settings": pax8_settings},
            "name",
        )

        if existing:
            doc = frappe.get_doc("Pax8 Customer", existing)
            doc.pax8_company_name = company_name
            doc.synced_at = frappe.utils.now()
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.new_doc("Pax8 Customer")
            doc.pax8_company_id = company_id
            doc.pax8_company_name = company_name
            doc.pax8_settings = pax8_settings
            doc.unmatched_flag = 1
            doc.synced_at = frappe.utils.now()
            doc.insert(ignore_permissions=True)
            created += 1

        if doc.customer:
            matched += 1
        else:
            unmatched += 1

    frappe.db.set_value("Pax8 Settings", pax8_settings, "last_synced_at", frappe.utils.now())
    frappe.db.commit()

    return {"matched": matched, "unmatched": unmatched, "created": created}
