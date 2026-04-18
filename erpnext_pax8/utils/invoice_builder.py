import frappe
from frappe.utils import get_last_day, getdate


def _get_or_create_item(product_name: str, pax8_product_id: str, company: str) -> str:
    """Return ERPNext Item name, creating it if it doesn't exist."""
    existing = frappe.db.get_value(
        "Item", {"item_name": product_name}, "name"
    )
    if existing:
        return existing

    item_group = frappe.db.get_value("Item Group", {"is_group": 0, "item_group_name": "Services"}, "name") \
        or frappe.db.get_value("Item Group", {"is_group": 0}, "name")

    item = frappe.new_doc("Item")
    item.item_name = product_name
    item.item_code = product_name[:140]
    item.item_group = item_group
    item.is_stock_item = 0
    item.description = f"Pax8 product: {product_name}"
    item.insert(ignore_permissions=True)
    return item.name


def _period_end_date(billing_period: str) -> str:
    """Return last day of YYYY-MM as a date string."""
    year, month = billing_period.split("-")
    return str(get_last_day(getdate(f"{year}-{month}-01")))


def create_purchase_invoice(
    items: list,
    billing_period: str,
    settings,
) -> str:
    """
    Create and submit a Purchase Invoice for all Pax8 line items.
    items: list of Pax8 invoice item dicts with keys: productName, quantity, unitCost
    Returns the Purchase Invoice name.
    """
    company = settings.company
    supplier = settings.default_supplier
    if not supplier:
        frappe.throw("Please set a Default Supplier on Pax8 Settings.")

    posting_date = _period_end_date(billing_period)

    pi = frappe.new_doc("Purchase Invoice")
    pi.supplier = supplier
    pi.company = company
    pi.posting_date = posting_date
    pi.set_posting_time = 1

    expense_account = frappe.db.get_value(
        "Account",
        {"account_type": "Expense Account", "company": company, "is_group": 0},
        "name",
    )

    for line in items:
        product_name = line.get("productName") or line.get("product_name") or "Pax8 Product"
        pax8_product_id = line.get("productId") or line.get("product_id") or ""
        qty = float(line.get("quantity", 1))
        rate = float(line.get("unitCost") or line.get("unit_cost") or 0)

        item_name = _get_or_create_item(product_name, pax8_product_id, company)
        pi.append("items", {
            "item_code": item_name,
            "qty": qty,
            "rate": rate,
            "expense_account": expense_account,
        })

    pi.insert(ignore_permissions=True)
    pi.submit()
    frappe.db.commit()
    return pi.name


def create_sales_invoice(
    customer: str,
    items: list,
    billing_period: str,
    company: str,
) -> str:
    """
    Create and submit a Sales Invoice for one customer's Pax8 subscriptions.
    items: list of Pax8 line item dicts with keys: productName, quantity, unitPrice (sell price)
    Returns the Sales Invoice name.
    """
    posting_date = _period_end_date(billing_period)

    income_account = frappe.db.get_value(
        "Account",
        {"account_type": "Income Account", "company": company, "is_group": 0},
        "name",
    )
    receivable_account = frappe.db.get_value(
        "Account",
        {"account_type": "Receivable", "company": company, "is_group": 0},
        "name",
    )

    si = frappe.new_doc("Sales Invoice")
    si.customer = customer
    si.company = company
    si.posting_date = posting_date
    si.set_posting_time = 1
    if receivable_account:
        si.debit_to = receivable_account

    for line in items:
        product_name = line.get("productName") or line.get("product_name") or "Pax8 Product"
        pax8_product_id = line.get("productId") or line.get("product_id") or ""
        qty = float(line.get("quantity", 1))
        rate = float(line.get("unitPrice") or line.get("unit_price") or 0)

        item_name = _get_or_create_item(product_name, pax8_product_id, company)
        si.append("items", {
            "item_code": item_name,
            "qty": qty,
            "rate": rate,
            "income_account": income_account,
        })

    si.insert(ignore_permissions=True)
    si.submit()
    frappe.db.commit()
    return si.name
