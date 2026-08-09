import json
import re

import frappe

from sync_webshop.api.catalog import _get_price_list, _website_item_groups
from sync_webshop.api.marketing import mark_coupon_used, validate_coupon
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
		frappe.throw(frappe._("اكتب اسمك بالكامل."))
	if not email or not EMAIL_RE.match(email):
		frappe.throw(frappe._("اكتب بريد إلكتروني صحيح."))

	digits = "".join(ch for ch in phone if ch.isdigit())
	if len(digits) < 9:
		frappe.throw(frappe._("اكتب رقم موبايل صحيح."))
	if len(address) < 10:
		frappe.throw(frappe._("اكتب عنوان التوصيل بالتفصيل."))

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
		frappe.throw(frappe._("سلتك فاضية."))
	if len(items) > MAX_LINES:
		frappe.throw(frappe._("عدد المنتجات كبير في طلب واحد."))

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
			frappe.throw(frappe._("الكمية المطلوبة من {0} مش صحيحة.").format(code))

		item = frappe.db.get_value("Item", {"name": code, "disabled": 0}, ["name", "item_group"], as_dict=True)
		if not item or (allowed is not None and item.item_group not in allowed):
			frappe.throw(frappe._("{0} مش متاح دلوقتي.").format(code))

		merged[code] = merged.get(code, 0) + qty

	if not merged:
		frappe.throw(frappe._("سلتك فاضية."))
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
		frappe.throw(frappe._("{0} مش معروض للبيع دلوقتي.").format(missing[0]))
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


def _quote(item_qty, coupon_code=None, city=None, payment_method=None):
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

	# الخصم يُحسب على المجموع قبل الشحن، ودايمًا من الخادم
	discount, coupon = 0.0, None
	if coupon_code:
		checked = validate_coupon(coupon_code, subtotal, currency)
		if not checked.get("valid"):
			frappe.throw(checked.get("reason") or frappe._("الكوبون ده مش صحيح."))
		discount = float(checked["discount_amount"])
		coupon = checked

	shipping = _shipping_company(subtotal - discount, city)

	# A collection fee configured on the payment method, if any.
	fee = 0.0
	gateway = _gateway_doc(payment_method)
	if gateway:
		fee = float(gateway.extra_fee or 0)

	return {
		"payment_fee": round(fee, 2),
		"shipping_company": shipping["company"],
		"shipping_label_ar": shipping["label_ar"],
		"shipping_label_en": shipping["label_en"],
		"discount": round(discount, 2),
		"coupon": {k: coupon[k] for k in ("code", "coupon", "description")} if coupon else None,
		"_coupon_name": coupon["coupon"] if coupon else None,
		"items": lines,
		"currency": currency,
		"subtotal": round(subtotal, 2),
		"shipping_cost": round(shipping["cost"], 2),
		"free_shipping_threshold": shipping["free_over"],

		"grand_total": round(subtotal - discount + shipping["cost"] + fee, 2),
		"_shipping_account": shipping["account"],
	}


def _gateways_from_documents():
	"""
	Payment methods the owner created in ERPNext. Secret keys never leave the
	server — only what the storefront needs to draw the option.
	"""
	rows = frappe.get_all(
		"Webshop Payment Gateway",
		filters={"enabled": 1},
		fields=[
			"name", "gateway_type", "label_ar", "label_en",
			"instructions_ar", "instructions_en", "extra_fee", "public_key", "mode",
		],
		order_by="sort_order asc, name asc",
	)
	gateways = []
	for row in rows:
		gateways.append(
			{
				"name": row.name,
				"type": row.gateway_type,
				"label_ar": row.label_ar or row.name,
				"label_en": row.label_en or row.label_ar or row.name,
				"instructions_ar": row.instructions_ar,
				"instructions_en": row.instructions_en,
				"extra_fee": float(row.extra_fee or 0),
				# Public keys are meant to be public; secrets stay on the server.
				"publishable_key": row.public_key if row.gateway_type == "Stripe" else None,
				"mode": row.mode,
			}
		)
	return gateways


def _gateway_doc(name):
	if name and frappe.db.exists("Webshop Payment Gateway", {"name": name, "enabled": 1}):
		return frappe.get_doc("Webshop Payment Gateway", name)
	return None


def _shipping_company(subtotal, city=None):
	"""
	The enabled courier, priced by zone when the customer's city matches one.
	Falls back to the old single shipping rule while no company exists yet.
	"""
	company = frappe.get_all(
		"Webshop Shipping Company",
		filters={"enabled": 1},
		fields=[
			"name", "label_ar", "label_en", "shipping_cost", "free_shipping_threshold",
			"shipping_account", "min_delivery_days", "max_delivery_days",
		],
		order_by="modified asc",
		limit=1,
	)
	if not company:
		rule = _shipping_for(subtotal)
		return {
			"company": None,
			"label_ar": None,
			"label_en": None,
			"cost": rule["cost"],
			"free_over": rule["free_over"],
			"account": rule["account"],
			"min_days": None,
			"max_days": None,
		}

	company = company[0]
	cost = float(company.shipping_cost or 0)
	free_over = float(company.free_shipping_threshold or 0)
	min_days, max_days = company.min_delivery_days, company.max_delivery_days

	if city:
		needle = str(city).strip()
		for zone in frappe.get_all(
			"Webshop Shipping Zone",
			filters={"parent": company.name},
			fields=["governorates", "shipping_cost", "free_shipping_threshold", "delivery_days"],
			order_by="idx asc",
		):
			names = [g.strip() for g in (zone.governorates or "").replace("،", ",").split(",") if g.strip()]
			if names and not any(n in needle or needle in n for n in names):
				continue
			cost = float(zone.shipping_cost or 0)
			free_over = float(zone.free_shipping_threshold or free_over)
			if zone.delivery_days:
				min_days = max_days = zone.delivery_days
			break

	if free_over and subtotal >= free_over:
		cost = 0.0

	return {
		"company": company.name,
		"label_ar": company.label_ar or company.name,
		"label_en": company.label_en or company.label_ar or company.name,
		"cost": cost,
		"free_over": free_over,
		"account": company.shipping_account,
		"min_days": min_days,
		"max_days": max_days,
	}


# ---------------------------------------------------------------- endpoints


@frappe.whitelist(allow_guest=True)
def get_checkout_settings():
	set_cors_headers()
	payment_settings = frappe.get_single("Webshop Payment Settings")
	content_settings = frappe.get_single("Webshop Content Settings")

	gateways = _gateways_from_documents()
	if gateways:
		shipping = _shipping_company(0)
		return {
			"payment_gateways": gateways,
			"shipping_rules": [],
			"shipping_company": {
				"name": shipping["company"],
				"label_ar": shipping["label_ar"],
				"label_en": shipping["label_en"],
				"cost": shipping["cost"],
				"free_shipping_threshold": shipping["free_over"],
			},
			"delivery_settings": {
				"min_days": shipping["min_days"] or content_settings.min_delivery_days or 1,
				"max_days": shipping["max_days"] or content_settings.max_delivery_days or 7,
			},
		}

	# Nothing configured yet — fall back to the old single settings record.
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
def quote_order(items, coupon_code=None, city=None, payment_method=None):
	"""
	Authoritative totals for a cart. The storefront shows these numbers rather
	than adding up prices itself, so what the shopper sees is what the order
	will cost.
	"""
	set_cors_headers()
	quote = _quote(_clean_items(items), coupon_code, city, payment_method)
	quote.pop("_shipping_account", None)
	quote.pop("_coupon_name", None)
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
	note=None, coupon_code=None, idempotency_key=None, submit=True, **kwargs
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
	quote = _quote(item_qty, coupon_code, clean_customer.get("city"), payment_method)

	method = payment_method or "cod"
	gateway = _gateway_doc(method)
	if gateway:
		# Anything other than cash or a bank transfer needs its own integration
		# before it can be taken online.
		if gateway.gateway_type not in ("Cash on Delivery", "Bank Transfer"):
			frappe.throw(frappe._("طريقة الدفع دي لسه مش جاهزة على الموقع."))
	else:
		payment_settings = frappe.get_single("Webshop Payment Settings")
		method = method.lower()
		if method == "cod" and not payment_settings.cod_enabled:
			frappe.throw(frappe._("الدفع عند الاستلام مش متاح دلوقتي."))
		if method == "stripe":
			frappe.throw(frappe._("الدفع بالبطاقة مش متاح دلوقتي."))

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
			"webshop_payment_status": "COD" if (gateway.gateway_type if gateway else method) in ("Cash on Delivery", "cod") else "Pending",
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

	if quote["discount"] > 0:
		so.apply_discount_on = "Net Total"
		so.discount_amount = quote["discount"]

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
		frappe.throw(frappe._("إجمالي الطلب اتغيّر. حدّث السلة وجرّب تاني."))

	if frappe.utils.cint(submit):
		so.submit()

	if quote.get("_coupon_name"):
		mark_coupon_used(quote["_coupon_name"])

	frappe.db.commit()

	return {
		"sales_order": so.name,
		"customer": customer_name,
		"status": so.status,
		"subtotal": quote["subtotal"],
		"discount": quote["discount"],
		"coupon": quote["coupon"],
		"shipping_cost": quote["shipping_cost"],
		"grand_total": float(so.grand_total),
		"currency": so.currency,
		"payment_method": method,
		"duplicate": False,
	}
