# -*- coding: utf-8 -*-
import json

import frappe

from sync_webshop.api.utils import set_cors_headers


def _coupon_error(message):
	"""One shape for every rejection, so a shopper always gets a reason."""
	return {"valid": False, "reason": message, "discount_amount": 0.0}


def validate_coupon(code, subtotal, currency=None, customer=None):
	"""
	Check a coupon against ERPNext's own Coupon Code and Pricing Rule records.

	Callable from Python so checkout can re-check at order time — a coupon that
	was valid when the shopper typed it may have expired or run out by the time
	they press the button.
	"""
	code = (code or "").strip()
	if not code:
		return _coupon_error(frappe._("اكتب كود الكوبون."))

	coupon = frappe.db.get_value(
		"Coupon Code",
		{"coupon_code": code},
		["name", "pricing_rule", "valid_from", "valid_upto", "maximum_use", "used"],
		as_dict=True,
	)
	if not coupon:
		return _coupon_error(frappe._("الكود ده مش صحيح."))

	today = frappe.utils.nowdate()
	if coupon.valid_from and frappe.utils.getdate(coupon.valid_from) > frappe.utils.getdate(today):
		return _coupon_error(frappe._("الكوبون ده لسه ما اشتغلش."))
	if coupon.valid_upto and frappe.utils.getdate(coupon.valid_upto) < frappe.utils.getdate(today):
		return _coupon_error(frappe._("الكوبون ده انتهت صلاحيته."))
	if coupon.maximum_use and (coupon.used or 0) >= coupon.maximum_use:
		return _coupon_error(frappe._("الكوبون ده اتستخدم بالكامل."))

	if not coupon.pricing_rule:
		return _coupon_error(frappe._("الكوبون ده مش مظبوط."))

	rule = frappe.db.get_value(
		"Pricing Rule",
		coupon.pricing_rule,
		[
			"name", "disable", "valid_from", "valid_upto",
			"rate_or_discount", "discount_amount", "discount_percentage",
			"min_amt", "max_amt", "currency",
		],
		as_dict=True,
	)
	if not rule or rule.disable:
		return _coupon_error(frappe._("الكوبون ده مش شغال دلوقتي."))
	if rule.valid_from and frappe.utils.getdate(rule.valid_from) > frappe.utils.getdate(today):
		return _coupon_error(frappe._("الكوبون ده لسه ما اشتغلش."))
	if rule.valid_upto and frappe.utils.getdate(rule.valid_upto) < frappe.utils.getdate(today):
		return _coupon_error(frappe._("الكوبون ده انتهت صلاحيته."))

	subtotal = float(subtotal or 0)
	if rule.min_amt and subtotal < float(rule.min_amt):
		return _coupon_error(
			frappe._("الكوبون ده محتاج طلب بحد أدنى {0}.").format(
				f"{float(rule.min_amt):.2f} {currency or ''}".strip()
			)
		)
	if rule.max_amt and subtotal > float(rule.max_amt):
		return _coupon_error(frappe._("الكوبون ده مش ساري على طلب بالحجم ده."))

	discount = 0.0
	if rule.rate_or_discount == "Discount Amount":
		discount = float(rule.discount_amount or 0)
	elif rule.rate_or_discount == "Discount Percentage":
		discount = subtotal * float(rule.discount_percentage or 0) / 100.0
	else:
		return _coupon_error(frappe._("نوع الكوبون ده مش مدعوم على الموقع."))

	# A discount can never exceed the order, and never turns into a payout.
	discount = max(0.0, min(round(discount, 2), subtotal))
	if discount <= 0:
		return _coupon_error(frappe._("الكوبون ده مش هيقلل قيمة الطلب."))

	return {
		"valid": True,
		"code": code,
		"coupon": coupon.name,
		"pricing_rule": rule.name,
		"discount_amount": discount,
		"description": (
			frappe._("خصم {0}%").format(frappe.utils.flt(rule.discount_percentage, 2))
			if rule.rate_or_discount == "Discount Percentage"
			else frappe._("خصم {0}").format(f"{discount:.2f} {currency or ''}".strip())
		),
	}


@frappe.whitelist(allow_guest=True)
def check_coupon(code, subtotal, currency=None):
	"""Storefront-facing check, used while the shopper is still on the cart."""
	set_cors_headers()
	return validate_coupon(code, subtotal, currency)


def mark_coupon_used(coupon_name):
	"""Called once an order is actually created."""
	if not coupon_name:
		return
	used = frappe.db.get_value("Coupon Code", coupon_name, "used") or 0
	frappe.db.set_value("Coupon Code", coupon_name, "used", used + 1)


@frappe.whitelist()
def sync_cart(cart_data):
	"""Keep a logged-in shopper's cart so it can be recovered if they leave."""
	set_cors_headers()
	if frappe.session.user == "Guest":
		return

	settings = frappe.get_single("Webshop Content Settings")
	if not settings.get("enable_abandoned_cart_recovery"):
		return

	user = frappe.get_doc("User", frappe.session.user)
	if isinstance(cart_data, str):
		cart_data = json.loads(cart_data)

	existing = frappe.db.get_value(
		"Webshop Abandoned Cart", {"user": user.name, "status": "Abandoned"}, "name"
	)
	if existing:
		doc = frappe.get_doc("Webshop Abandoned Cart", existing)
		doc.cart_data = json.dumps(cart_data, ensure_ascii=False)
		doc.last_updated = frappe.utils.now()
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Webshop Abandoned Cart",
				"user": user.name,
				"email": user.email,
				"cart_data": json.dumps(cart_data, ensure_ascii=False),
				"status": "Abandoned",
				"last_updated": frappe.utils.now(),
			}
		)
		doc.insert(ignore_permissions=True)

	return {"synced": True}


@frappe.whitelist(allow_guest=True)
def subscribe_newsletter(email):
	"""
	Store the subscription locally. Mailchimp is only called when it is
	configured, and a failure there never loses the address.
	"""
	set_cors_headers()
	email = (email or "").strip().lower()
	if "@" not in email:
		frappe.throw(frappe._("اكتب بريد إلكتروني صحيح."))

	if not frappe.db.exists("Email Group", "Webshop Newsletter"):
		group = frappe.get_doc({"doctype": "Email Group", "title": "Webshop Newsletter"})
		group.flags.ignore_permissions = True
		group.insert()

	if not frappe.db.exists("Email Group Member", {"email": email, "email_group": "Webshop Newsletter"}):
		member = frappe.get_doc(
			{
				"doctype": "Email Group Member",
				"email": email,
				"email_group": "Webshop Newsletter",
			}
		)
		member.flags.ignore_permissions = True
		member.insert()

	frappe.db.commit()
	return {"subscribed": True}
