import frappe
from frappe.utils import get_last_day, getdate


def _get_or_create_item(product_name: str, pax8_product_id: str, company: str) -> str:
    """Return ERPNext Item name, creating it if it doesn't exist."""
    existing = frappe.db.get_value("Item", {"item_name": product_name}, "name")
    if existing:
        return existing

    item_group = (
        frappe.db.get_value("Item Group", {"is_group": 0, "item_group_name": "Services"}, "name")
        or frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    )
    if not item_group:
        frappe.throw("No Item Group found. Please create a 'Services' Item Group in ERPNext.")

    item = frappe.new_doc("Item")
    item.item_name = product_name
    if pax8_product_id:
        item.item_code = f"{product_name[:120]}-{pax8_product_id}"[:140]
    else:
        item.item_code = product_name[:140]
    item.item_group = item_group
    item.is_stock_item = 0
    item.description = f"Pax8 product: {product_name}"

    frappe.db.savepoint("pax8_item_insert")
    try:
        item.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        frappe.db.rollback(save_point="pax8_item_insert")
        return frappe.db.get_value("Item", {"item_name": product_name}, "name") or ""

    return item.name


def _period_end_date(billing_period: str) -> str:
    """Return last day of YYYY-MM as a date string."""
    try:
        year, month = billing_period.split("-")
        return str(get_last_day(getdate(f"{year}-{month}-01")))
    except (ValueError, AttributeError):
        frappe.throw(f"Invalid billing_period '{billing_period}'. Expected YYYY-MM.")


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
    if not items:
        frappe.throw("Cannot create invoice: items list is empty.")

    company = settings.company
    supplier = settings.default_supplier
    if not supplier:
        frappe.throw("Please set a Default Supplier on Pax8 Settings.")
    if not company:
        frappe.throw("Please set a Company on Pax8 Settings.")

    posting_date = _period_end_date(billing_period)

    pi = frappe.new_doc("Purchase Invoice")
    pi.supplier = supplier
    pi.company = company
    pi.posting_date = posting_date
    pi.set_posting_time = 1

    company_doc = frappe.get_cached_doc("Company", company)
    expense_account = company_doc.default_expense_account
    if not expense_account:
        frappe.throw(f"No Default Expense Account set for company '{company}'. Set it in Company Settings.")

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
    if not customer:
        frappe.throw("customer is required to create a Sales Invoice.")
    if not company:
        frappe.throw("company is required to create a Sales Invoice.")
    if not items:
        frappe.throw("Cannot create invoice: items list is empty.")

    posting_date = _period_end_date(billing_period)

    company_doc = frappe.get_cached_doc("Company", company)
    income_account = company_doc.default_income_account
    receivable_account = company_doc.default_receivable_account
    if not income_account:
        frappe.throw(f"No Default Income Account set for company '{company}'. Set it in Company Settings.")

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
    return si.name
