import json
import re

import frappe

from sync_webshop.api.catalog import _get_price_list, _website_item_groups
from sync_webshop.api.utils import set_cors_headers

MAX_LINES = 50
MAX_QTY_PER_LINE = 999

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


def _settings():
	return frappe.get_single("Webshop API Settings")


def _company():
	company = _settings().get("default_company")
	if not company:
		company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
	return company


def _warehouse(company):
	warehouse = _settings().get("default_warehouse")
	if warehouse and frappe.db.exists("Warehouse", warehouse):
		return warehouse
	return frappe.db.get_value("Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name")


def _customer_group():
	group = _settings().get("default_customer_group")
	if group and not frappe.db.get_value("Customer Group", group, "is_group"):
		return group
	configured = frappe.db.get_single_value("Selling Settings", "customer_group")
	if configured and not frappe.db.get_value("Customer Group", configured, "is_group"):
		return configured
	return frappe.db.get_value("Customer Group", {"is_group": 0}, "name")


def _territory():
	territory = _settings().get("default_territory")
	if territory and not frappe.db.get_value("Territory", territory, "is_group"):
		return territory
	configured = frappe.db.get_single_value("Selling Settings", "territory")
	if configured and not frappe.db.get_value("Territory", configured, "is_group"):
		return configured
	return frappe.db.get_value("Territory", {"is_group": 0}, "name")


# ---------------------------------------------------------------- validation


def _clean_customer(customer):
	"""Validate what the shopper typed before it reaches the ERP."""
	customer = customer or {}
	if isinstance(customer, str):
		customer = json.loads(customer)

	name = (customer.get("name") or "").strip()
	email = (customer.get("email") or "").strip().lower()
	phone = (customer.get("phone") or "").strip()
	address = (customer.get("address") or "").strip()
	city = (customer.get("city") or "").strip()

	if len(name) < 3:
		frappe.throw(frappe._("Please enter your full name."))
	if not email or not EMAIL_RE.match(email):
		frappe.throw(frappe._("Please enter a valid email address."))

	digits = "".join(ch for ch in phone if ch.isdigit())
	if len(digits) < 9:
		frappe.throw(frappe._("Please enter a valid phone number."))
	if len(address) < 10:
		frappe.throw(frappe._("Please enter the full delivery address."))

	return {"name": name, "email": email, "phone": phone, "address": address, "city": city}


def _clean_items(items):
	"""
	Reduce the cart to item codes and quantities. Prices are deliberately
	ignored — whatever the browser sends, the order is priced from the server's
	price list.
	"""
	if isinstance(items, str):
		items = json.loads(items)
	if not items:
		frappe.throw(frappe._("Your cart is empty."))
	if len(items) > MAX_LINES:
		frappe.throw(frappe._("Too many different products in one order."))

	allowed = _website_item_groups()
	merged = {}
	for row in items:
		code = (row.get("item_code") or "").strip()
		if not code:
			continue
		try:
			qty = int(float(row.get("qty") or 1))
		except (TypeError, ValueError):
			qty = 1
		if qty < 1 or qty > MAX_QTY_PER_LINE:
			frappe.throw(frappe._("Quantity for {0} is not valid.").format(code))

		item = frappe.db.get_value("Item", {"name": code, "disabled": 0}, ["name", "item_group"], as_dict=True)
		if not item or (allowed is not None and item.item_group not in allowed):
			frappe.throw(frappe._("{0} is no longer available.").format(code))

		merged[code] = merged.get(code, 0) + qty

	if not merged:
		frappe.throw(frappe._("Your cart is empty."))
	return merged


def _server_prices(item_codes):
	price_list = _get_price_list()
	rows = frappe.get_all(
		"Item Price",
		filters={"item_code": ["in", list(item_codes)], "price_list": price_list, "selling": 1},
		fields=["item_code", "price_list_rate", "currency"],
	)
	prices = {r.item_code: r for r in rows}
	missing = [c for c in item_codes if c not in prices]
	if missing:
		frappe.throw(frappe._("{0} is not available for sale right now.").format(missing[0]))
	return prices


def _shipping_for(subtotal):
	"""The single enabled shipping rule, priced from the server-side subtotal."""
	rule = frappe.db.get_value(
		"Webshop Shipping Rule",
		{"enabled": 1},
		["name", "rule_name", "shipping_cost", "free_shipping_threshold", "shipping_account"],
		as_dict=True,
	)
	if not rule:
		return {"cost": 0.0, "rule": None, "account": None, "free_over": 0.0}

	threshold = float(rule.free_shipping_threshold or 0)
	cost = 0.0 if (threshold and subtotal >= threshold) else float(rule.shipping_cost or 0)
	return {"cost": cost, "rule": rule.rule_name, "account": rule.shipping_account, "free_over": threshold}


def _quote(item_qty):
	prices = _server_prices(item_qty.keys())
	currency = None
	lines = []
	subtotal = 0.0

	for code, qty in item_qty.items():
		rate = float(prices[code].price_list_rate)
		currency = currency or prices[code].currency
		amount = rate * qty
		subtotal += amount
		lines.append(
			{
				"item_code": code,
				"item_name": frappe.db.get_value("Item", code, "item_name"),
				"qty": qty,
				"rate": rate,
				"amount": amount,
				"currency": prices[code].currency,
			}
		)

	shipping = _shipping_for(subtotal)
	return {
		"items": lines,
		"currency": currency,
		"subtotal": round(subtotal, 2),
		"shipping_cost": round(shipping["cost"], 2),
		"free_shipping_threshold": shipping["free_over"],
		"shipping_rule": shipping["rule"],
		"grand_total": round(subtotal + shipping["cost"], 2),
		"_shipping_account": shipping["account"],
	}


# ---------------------------------------------------------------- endpoints


@frappe.whitelist(allow_guest=True)
def get_checkout_settings():
	set_cors_headers()
	payment_settings = frappe.get_single("Webshop Payment Settings")
	content_settings = frappe.get_single("Webshop Content Settings")

	gateways = []
	if payment_settings.stripe_enabled:
		gateways.append(
			{
				"name": "stripe",
				"label_en": "Card",
				"label_ar": "بطاقة",
				"publishable_key": payment_settings.stripe_publishable_key,
			}
		)
	if payment_settings.cod_enabled:
		gateways.append(
			{
				"name": "cod",
				"label_en": payment_settings.cod_label_en or "Cash on delivery",
				"label_ar": payment_settings.cod_label_ar or "الدفع عند الاستلام",
			}
		)

	shipping_rules = frappe.get_all(
		"Webshop Shipping Rule",
		filters={"enabled": 1},
		fields=["rule_name", "shipping_cost", "free_shipping_threshold"],
	)

	return {
		"payment_gateways": gateways,
		"shipping_rules": shipping_rules,
		"delivery_settings": {
			"min_days": content_settings.min_delivery_days or 1,
			"max_days": content_settings.max_delivery_days or 7,
		},
	}


@frappe.whitelist(allow_guest=True)
def quote_order(items):
	"""
	Authoritative totals for a cart. The storefront shows these numbers rather
	than adding up prices itself, so what the shopper sees is what the order
	will cost.
	"""
	set_cors_headers()
	quote = _quote(_clean_items(items))
	quote.pop("_shipping_account", None)
	return quote


def _upsert_address(customer_name, customer):
	"""Keep the delivery address on the customer record — it used to be dropped."""
	title = f"{customer['name'][:60]} - Web"
	existing = frappe.db.sql(
		"""
		SELECT a.name FROM `tabAddress` a
		JOIN `tabDynamic Link` dl ON dl.parent = a.name AND dl.parenttype = 'Address'
		WHERE dl.link_doctype = 'Customer' AND dl.link_name = %s AND a.address_title = %s
		LIMIT 1
		""",
		(customer_name, title),
	)

	values = {
		"address_title": title,
		"address_type": "Shipping",
		"address_line1": customer["address"][:240],
		"city": customer["city"] or "-",
		"country": frappe.db.get_value("Company", _company(), "country") or "Egypt",
		"phone": customer["phone"],
		"email_id": customer["email"],
		"is_shipping_address": 1,
		"is_primary_address": 1,
	}

	if existing:
		address = frappe.get_doc("Address", existing[0][0])
		address.update(values)
	else:
		address = frappe.get_doc(
			{
				"doctype": "Address",
				**values,
				"links": [{"link_doctype": "Customer", "link_name": customer_name}],
			}
		)
	address.flags.ignore_permissions = True
	address.flags.ignore_mandatory = True
	address.save()
	return address.name


def _find_or_create_customer(customer):
	email, phone = customer["email"], customer["phone"]

	contact_name = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")
	if not contact_name:
		digits = "".join(ch for ch in phone if ch.isdigit())[-9:]
		if digits:
			row = frappe.db.sql(
				"""
				SELECT parent FROM `tabContact Phone`
				WHERE REPLACE(REPLACE(REPLACE(phone, ' ', ''), '-', ''), '+', '') LIKE %s
				LIMIT 1
				""",
				(f"%{digits}",),
			)
			contact_name = row[0][0] if row else None

	if contact_name:
		links = frappe.get_all(
			"Dynamic Link",
			filters={"parent": contact_name, "parenttype": "Contact", "link_doctype": "Customer"},
			fields=["link_name"],
		)
		if links:
			return links[0].link_name

	# This ERP marks phone and customer source mandatory on Customer, so both
	# have to be filled or the order cannot be created at all.
	customer_doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": customer["name"],
			"customer_type": "Individual",
			"customer_group": _customer_group(),
			"territory": _territory(),
			"custom_mobile_phone": phone,
			"custom_مصدر_العميل": _settings().get("customer_source_value") or "الموقع الالكتروني",
		}
	)
	customer_doc.flags.ignore_permissions = True
	customer_doc.insert()

	contact_doc = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": customer["name"],
			"email_ids": [{"email_id": email, "is_primary": 1}],
			"phone_nos": [{"phone": phone, "is_primary_mobile_no": 1}],
			"links": [{"link_doctype": "Customer", "link_name": customer_doc.name}],
		}
	)
	contact_doc.flags.ignore_permissions = True
	contact_doc.insert(ignore_mandatory=True)

	return customer_doc.name


@frappe.whitelist(allow_guest=True)
def create_order(
	customer, items, payment_method=None, delivery_date=None,
	note=None, idempotency_key=None, submit=True, **kwargs
):
	"""
	Turn a cart into a Sales Order. Everything that decides money — prices,
	shipping, totals — is read from the server. The browser only says what and
	how many.
	"""
	set_cors_headers()

	# A double-tapped button must not become two orders.
	if idempotency_key:
		existing = frappe.db.get_value(
			"Sales Order",
			{"webshop_idempotency_key": idempotency_key},
			["name", "customer", "status", "grand_total", "currency"],
			as_dict=True,
		)
		if existing:
			return {
				"sales_order": existing.name,
				"customer": existing.customer,
				"status": existing.status,
				"grand_total": existing.grand_total,
				"currency": existing.currency,
				"duplicate": True,
			}

	clean_customer = _clean_customer(customer)
	item_qty = _clean_items(items)
	quote = _quote(item_qty)

	method = (payment_method or "cod").lower()
	payment_settings = frappe.get_single("Webshop Payment Settings")
	if method == "cod" and not payment_settings.cod_enabled:
		frappe.throw(frappe._("Cash on delivery is not available."))
	if method == "stripe" and not payment_settings.stripe_enabled:
		frappe.throw(frappe._("Card payment is not available."))

	company = _company()
	warehouse = _warehouse(company)
	customer_name = _find_or_create_customer(clean_customer)
	_upsert_address(customer_name, clean_customer)

	# Cost centre, sales partner and sales team are mandatory on Sales Order in
	# this ERP. Online orders have no salesperson, so they are credited to the
	# website itself rather than to a person who did not make the sale.
	settings = _settings()
	sales_person = settings.get("default_sales_person")

	so = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"customer": customer_name,
			"company": company,
			"order_type": "Sales",
			"cost_center": settings.get("default_cost_center"),
			"sales_partner": settings.get("default_sales_partner"),
			"sales_team": (
				[{"sales_person": sales_person, "allocated_percentage": 100}] if sales_person else []
			),
			"selling_price_list": _get_price_list(),
			"currency": quote["currency"],
			"delivery_date": delivery_date or frappe.utils.add_days(frappe.utils.nowdate(), 3),
			"is_webshop_order": 1,
			"webshop_payment_method": method,
			"webshop_payment_status": "COD" if method == "cod" else "Pending",
			"webshop_idempotency_key": idempotency_key,
			"webshop_customer_note": (note or "")[:500] or None,
			"contact_email": clean_customer["email"],
			"contact_mobile": clean_customer["phone"],
			"items": [
				{
					"item_code": line["item_code"],
					"qty": line["qty"],
					"rate": line["rate"],
					"warehouse": warehouse,
					"delivery_date": delivery_date or frappe.utils.add_days(frappe.utils.nowdate(), 3),
				}
				for line in quote["items"]
			],
		}
	)

	if quote["shipping_cost"] > 0:
		account = quote["_shipping_account"]
		if not account:
			frappe.throw(
				frappe._(
					"A shipping cost is configured but no Shipping Income Account is set "
					"on the shipping rule. Please set it in ERPNext."
				)
			)
		so.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": account,
				"description": frappe._("Shipping"),
				"tax_amount": quote["shipping_cost"],
				"add_deduct_tax": "Add",
				"category": "Valuation and Total",
			},
		)

	so.flags.ignore_permissions = True
	so.insert()

	# The order the shopper agreed to must be the order that gets saved.
	if abs(float(so.grand_total) - quote["grand_total"]) > 0.5:
		frappe.db.rollback()
		frappe.throw(frappe._("The order total changed. Please refresh your cart and try again."))

	if frappe.utils.cint(submit):
		so.submit()

	frappe.db.commit()

	return {
		"sales_order": so.name,
		"customer": customer_name,
		"status": so.status,
		"subtotal": quote["subtotal"],
		"shipping_cost": quote["shipping_cost"],
		"grand_total": float(so.grand_total),
		"currency": so.currency,
		"payment_method": method,
		"duplicate": False,
	}
