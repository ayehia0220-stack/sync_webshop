import frappe
from sync_webshop.api.utils import set_cors_headers
from sync_webshop.api.catalog import _get_price_list


def _get_default_customer_group():
	"""
	Customer records must point at a non-group (leaf) Customer Group -
	"All Customer Groups" itself is just an organizing node and will be
	rejected by ERPNext's validation. Prefer the value configured in
	Selling Settings if it's actually a valid leaf group; otherwise fall
	back to any leaf group that exists on this site.
	"""
	configured = frappe.db.get_single_value("Selling Settings", "customer_group")
	if configured and not frappe.db.get_value("Customer Group", configured, "is_group"):
		return configured

	fallback = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
	if fallback:
		return fallback

	frappe.throw(
		"No non-group Customer Group exists on this site. "
		"Please create at least one Customer Group (with 'Is Group' unchecked) in ERPNext."
	)


def _get_default_territory():
	"""Same issue as customer_group - Territory also needs a leaf node."""
	configured = frappe.db.get_single_value("Selling Settings", "territory")
	if configured and not frappe.db.get_value("Territory", configured, "is_group"):
		return configured

	fallback = frappe.db.get_value("Territory", {"is_group": 0}, "name")
	if fallback:
		return fallback

	frappe.throw(
		"No non-group Territory exists on this site. "
		"Please create at least one Territory (with 'Is Group' unchecked) in ERPNext."
	)


def _get_default_company():
	"""Sales Order requires a Company - use the site's default company."""
	company = frappe.defaults.get_global_default("company")
	if not company:
		company = frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw("No Company exists on this site. Please set up a Company in ERPNext first.")
	return company


def _get_default_warehouse(company):
	"""Stock items need a source Warehouse on Sales Order Item rows."""
	warehouse = frappe.db.get_value(
		"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
	)
	if not warehouse:
		frappe.throw(
			f"No usable Warehouse found for company {company}. "
			"Please create at least one non-group Warehouse in ERPNext."
		)
	return warehouse


def _find_or_create_customer(customer):
	"""
	Looks for an existing Customer by phone or email via their linked
	Contact. If none is found, creates a new Customer + Contact so repeat
	visitors don't create a duplicate Customer record every time they
	check out with the same phone/email.
	"""
	email = (customer.get("email") or "").strip()
	phone = (customer.get("phone") or "").strip()
	full_name = (customer.get("name") or "Guest Customer").strip()

	contact_name = None
	if email:
		contact_name = frappe.db.get_value("Contact", {"email_id": email}, "name")
	if not contact_name and phone:
		contact_name = frappe.db.get_value("Contact", {"phone": phone}, "name")
	if not contact_name and phone:
		contact_name = frappe.db.get_value("Contact", {"mobile_no": phone}, "name")

	if contact_name:
		links = frappe.get_all(
			"Dynamic Link",
			filters={"parent": contact_name, "parenttype": "Contact", "link_doctype": "Customer"},
			fields=["link_name"],
		)
		if links:
			return links[0].link_name

	# No match - create a new Customer + Contact
	customer_doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": full_name,
			"customer_type": "Individual",
			"customer_group": _get_default_customer_group(),
			"territory": _get_default_territory(),
		}
	)
	customer_doc.flags.ignore_permissions = True
	customer_doc.insert()

	contact_doc = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": full_name,
			"email_ids": [{"email_id": email, "is_primary": 1}] if email else [],
			"phone_nos": [{"phone": phone, "is_primary_mobile_no": 1}] if phone else [],
			"links": [{"link_doctype": "Customer", "link_name": customer_doc.name}],
		}
	)
	contact_doc.flags.ignore_permissions = True
	contact_doc.insert(ignore_mandatory=True)

	return customer_doc.name


@frappe.whitelist(allow_guest=True)
def create_order(customer, items, submit=False):
	"""
	Creates a Sales Order from checkout data. Guest-accessible by design -
	there is no API key to manage or rotate. Security comes from this
	endpoint only ever being able to do one narrow thing (create a
	Customer/Contact and a Sales Order from a cart), not from a credential.
	Basic abuse protection (rate limiting) is worth adding at the web
	server layer before a real public launch, same as any storefront
	checkout endpoint.

	customer: {"name": str, "email": str, "phone": str}
	items: [{"item_code": str, "qty": number}, ...]
	submit: bool - if true, submits the Sales Order instead of leaving it
	        as a draft
	"""
	set_cors_headers()

	if not items:
		frappe.throw("Cart is empty - no items provided.")

	for row in items:
		if not frappe.db.exists("Item", {"item_code": row.get("item_code"), "disabled": 0}):
			frappe.throw(f"Unknown item: {row.get('item_code')}")

	customer_name = _find_or_create_customer(customer or {})
	company = _get_default_company()
	warehouse = _get_default_warehouse(company)

	so = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"customer": customer_name,
			"company": company,
			"selling_price_list": _get_price_list(),
			"delivery_date": frappe.utils.add_days(frappe.utils.nowdate(), 3),
			"items": [
				{
					"item_code": row["item_code"],
					"qty": row.get("qty") or 1,
					"warehouse": warehouse,
				}
				for row in items
			],
		}
	)
	so.flags.ignore_permissions = True
	so.insert()

	if frappe.utils.cint(submit):
		so.submit()

	return {
		"sales_order": so.name,
		"customer": customer_name,
		"status": so.status,
		"grand_total": so.grand_total,
		"currency": so.currency,
	}
