import frappe
from frappe.utils import flt, get_last_day, getdate

# Tax templates from canada_business_compliance app (IPCONNEX is QC).
# Move to Pax8 Settings as Link fields if multi-province support is needed.
PURCHASE_TAX_TEMPLATE = "CA GST + QST - IPX - IPX"
SALES_TAX_TEMPLATE = "CA GST + QST - IPX"


def _purchase_tax_rows(template_name: str, total_pax8_tax: float) -> list:
    """Build PI tax rows that match Pax8's reported per-invoice salesTax exactly.

    Pax8 ships a combined per-line salesTax (no GST/QST split). Split the
    total proportionally across the template's tax rows by their declared
    rate, preserving each row's account_head. Last row absorbs rounding so
    the sum is exact to the cent.
    """
    if not total_pax8_tax:
        return []
    template = frappe.get_cached_doc("Purchase Taxes and Charges Template", template_name)
    rows = list(template.taxes)
    total_rate = sum(flt(r.rate) for r in rows)
    if not rows or not total_rate:
        return []
    out = []
    running = 0.0
    for i, r in enumerate(rows):
        if i < len(rows) - 1:
            amount = round(total_pax8_tax * flt(r.rate) / total_rate, 2)
            running += amount
        else:
            amount = round(total_pax8_tax - running, 2)
        out.append({
            "charge_type": "Actual",
            "account_head": r.account_head,
            "tax_amount": amount,
            "description": f"{r.description} (per Pax8)",
            "category": getattr(r, "category", "Total") or "Total",
            "add_deduct_tax": getattr(r, "add_deduct_tax", "Add") or "Add",
        })
    return out


def _sales_tax_rows(template_name: str) -> list:
    """Copy template tax rows — IPCONNEX charges its own GST+QST on top of price."""
    template = frappe.get_cached_doc("Sales Taxes and Charges Template", template_name)
    return [{
        "charge_type": r.charge_type,
        "account_head": r.account_head,
        "rate": r.rate,
        "description": r.description,
    } for r in template.taxes]


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
    pi.taxes_and_charges = PURCHASE_TAX_TEMPLATE

    company_doc = frappe.get_cached_doc("Company", company)
    expense_account = company_doc.default_expense_account
    if not expense_account:
        frappe.throw(f"No Default Expense Account set for company '{company}'. Set it in Company Settings.")

    for line in items:
        product_name = line.get("productName") or line.get("product_name") or "Pax8 Product"
        pax8_product_id = line.get("productId") or line.get("product_id") or ""
        qty = flt(line.get("quantity", 1))
        rate = flt(line.get("cost") or line.get("unitCost") or line.get("unit_cost") or 0)

        item_name = _get_or_create_item(product_name, pax8_product_id, company)
        pi.append("items", {
            "item_code": item_name,
            "qty": qty,
            "rate": rate,
            "expense_account": expense_account,
        })

    total_pax8_tax = sum(flt(line.get("salesTax") or line.get("sales_tax") or 0) for line in items)
    for tax_row in _purchase_tax_rows(PURCHASE_TAX_TEMPLATE, total_pax8_tax):
        pi.append("taxes", tax_row)

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
    si.taxes_and_charges = SALES_TAX_TEMPLATE
    if receivable_account:
        si.debit_to = receivable_account

    for line in items:
        product_name = line.get("productName") or line.get("product_name") or "Pax8 Product"
        pax8_product_id = line.get("productId") or line.get("product_id") or ""
        qty = flt(line.get("quantity", 1))
        rate = flt(line.get("price") or line.get("unitPrice") or line.get("unit_price") or 0)

        item_name = _get_or_create_item(product_name, pax8_product_id, company)
        si.append("items", {
            "item_code": item_name,
            "qty": qty,
            "rate": rate,
            "income_account": income_account,
        })

    for tax_row in _sales_tax_rows(SALES_TAX_TEMPLATE):
        si.append("taxes", tax_row)

    si.insert(ignore_permissions=True)
    return si.name
