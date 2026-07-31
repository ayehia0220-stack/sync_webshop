import frappe
from sync_webshop.api.utils import set_cors_headers
from sync_webshop.api.catalog import _get_price_list


def _get_default_customer_group():
	configured = frappe.db.get_single_value("Selling Settings", "customer_group")
	if configured and not frappe.db.get_value("Customer Group", configured, "is_group"):
		return configured
	fallback = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
	return fallback


def _get_default_territory():
	configured = frappe.db.get_single_value("Selling Settings", "territory")
	if configured and not frappe.db.get_value("Territory", configured, "is_group"):
		return configured
	fallback = frappe.db.get_value("Territory", {"is_group": 0}, "name")
	return fallback


def _get_default_company():
	company = frappe.defaults.get_global_default("company")
	if not company:
		company = frappe.db.get_value("Company", {}, "name")
	return company


def _get_default_warehouse(company):
	warehouse = frappe.db.get_value(
		"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
	)
	return warehouse


def _find_or_create_customer(customer):
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
def get_checkout_settings():
	set_cors_headers()
	payment_settings = frappe.get_single("Webshop Payment Settings")
	content_settings = frappe.get_single("Webshop Content Settings")
	
	gateways = []
	if payment_settings.stripe_enabled:
		gateways.append({
			"name": "stripe",
			"label": "Stripe (Card / Apple Pay / Google Pay)",
			"publishable_key": payment_settings.stripe_publishable_key
		})
	if payment_settings.cod_enabled:
		gateways.append({
			"name": "cod",
			"label_en": payment_settings.cod_label_en,
			"label_ar": payment_settings.cod_label_ar
		})
		
	shipping_rules = frappe.get_all(
		"Webshop Shipping Rule",
		filters={"enabled": 1},
		fields=["rule_name", "shipping_cost", "free_shipping_threshold"]
	)
	
	return {
		"payment_gateways": gateways,
		"shipping_rules": shipping_rules,
		"delivery_settings": {
			"min_days": content_settings.min_delivery_days or 1,
			"max_days": content_settings.max_delivery_days or 7
		}
	}


@frappe.whitelist(allow_guest=True)
def create_order(customer, items, payment_method=None, stripe_payment_intent=None, delivery_date=None, submit=False):
	set_cors_headers()

	if not items:
		frappe.throw("Cart is empty - no items provided.")

	customer_name = _find_or_create_customer(customer or {})
	company = _get_default_company()
	warehouse = _get_default_warehouse(company)

	# Calculate shipping cost
	shipping_cost = 0
	total_amount = sum(float(row.get("price") or 0) * float(row.get("qty") or 1) for row in items)
	
	shipping_rule = frappe.db.get_value("Webshop Shipping Rule", {"enabled": 1}, ["shipping_cost", "free_shipping_threshold"], as_dict=1)
	if shipping_rule:
		if shipping_rule.free_shipping_threshold > 0 and total_amount >= shipping_rule.free_shipping_threshold:
			shipping_cost = 0
		else:
			shipping_cost = shipping_rule.shipping_cost

	so = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"customer": customer_name,
			"company": company,
			"selling_price_list": _get_price_list(),
			"delivery_date": delivery_date or frappe.utils.add_days(frappe.utils.nowdate(), 3),
			"webshop_payment_method": payment_method,
			"stripe_payment_intent": stripe_payment_intent,
			"webshop_payment_status": "Pending" if payment_method == "stripe" else "COD",
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
	
		# Add shipping cost to taxes and charges table
		if shipping_cost > 0:
			so.append("taxes", {
				"charge_type": "Actual",
				"account_head": frappe.db.get_value("Account", {"account_type": "Tax", "company": company, "is_group": 0}, "name") or "Shipping Charges - " + company,
				"description": "Shipping Charges",
				"rate": shipping_cost,
				"tax_amount": shipping_cost,
				"add_deduct_tax": "Add"
			})
		
		so.flags.ignore_permissions = True
		so.insert()
		so.run_method("calculate_taxes_and_totals")
		so.save()

	if frappe.utils.cint(submit):
		so.submit()

	return {
		"sales_order": so.name,
		"customer": customer_name,
		"status": so.status,
		"grand_total": so.grand_total + shipping_cost,
		"currency": so.currency,
		"shipping_cost": shipping_cost
	}
