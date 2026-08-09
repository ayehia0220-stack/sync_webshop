# -*- coding: utf-8 -*-
import frappe

from sync_webshop.api.utils import full_url, set_cors_headers

LOGIN_MAX_ATTEMPTS = 8
LOGIN_WINDOW_SECONDS = 15 * 60
SIGNUP_MAX_PER_HOUR = 3


def _client_ip():
	return frappe.local.request_ip or "unknown"


def _throttle(bucket, limit, window, message):
	"""Simple per-IP counter in Redis. Keeps brute force and sign-up floods out."""
	key = f"webshop:{bucket}:{_client_ip()}"
	cache = frappe.cache()
	count = int(cache.get_value(key) or 0)
	if count >= limit:
		frappe.throw(message, frappe.ValidationError)
	cache.set_value(key, count + 1, expires_in_sec=window)


@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
	"""
	Sign in an existing account. The session cookie is what authenticates
	later requests — the session id is deliberately not returned in the body,
	so it can't end up in JavaScript-readable storage or a log.
	"""
	set_cors_headers()
	_throttle(
		"login",
		LOGIN_MAX_ATTEMPTS,
		LOGIN_WINDOW_SECONDS,
		frappe._("محاولات دخول كتير. جرّب تاني بعد شوية."),
	)

	try:
		login_manager = frappe.auth.LoginManager()
		login_manager.authenticate(user=usr, pwd=pwd)
		login_manager.post_login()
	except frappe.AuthenticationError:
		frappe.clear_messages()
		frappe.throw(frappe._("البريد أو كلمة السر غير صحيحة."), frappe.AuthenticationError)

	user = frappe.get_doc("User", frappe.session.user)
	return {"user": user.first_name, "email": user.email}


@frappe.whitelist(allow_guest=True)
def signup(email, first_name, password):
	"""
	Create a storefront account.

	Off unless "Enable Customer Signup" is ticked in Webshop API Settings.
	This endpoint used to create **System Users**, which carry access to the
	ERPNext desk — on an ERP holding this company's accounting and HR, a public
	sign-up form must never do that. Accounts here are Website Users only.
	"""
	set_cors_headers()

	settings = frappe.get_single("Webshop API Settings")
	if not settings.get("enable_customer_signup"):
		frappe.throw(frappe._("إنشاء الحسابات مقفول حاليًا."), frappe.PermissionError)

	_throttle(
		"signup",
		SIGNUP_MAX_PER_HOUR,
		3600,
		frappe._("محاولات كتير. جرّب تاني بعد شوية."),
	)

	email = (email or "").strip().lower()
	first_name = (first_name or "").strip()
	if "@" not in email or "." not in email.split("@")[-1]:
		frappe.throw(frappe._("اكتب بريد إلكتروني صحيح."))
	if len(first_name) < 2:
		frappe.throw(frappe._("اكتب اسمك."))
	if len(password or "") < 8:
		frappe.throw(frappe._("كلمة السر لازم تكون 8 حروف على الأقل."))

	if frappe.db.exists("User", email):
		# Same reply either way, so this can't be used to test which emails exist.
		return {"created": True}

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": first_name,
			"enabled": 1,
			"user_type": "Website User",
			"send_welcome_email": 0,
			"new_password": password,
			"roles": [{"role": "Customer"}],
		}
	)
	user.flags.ignore_permissions = True
	user.insert(ignore_permissions=True)
	frappe.db.commit()

	return {"created": True}


@frappe.whitelist()
def get_current_user():
	set_cors_headers()
	if frappe.session.user == "Guest":
		return None
	user = frappe.get_doc("User", frappe.session.user)
	return {
		"email": user.email,
		"first_name": user.first_name,
		"last_name": user.last_name,
		"full_name": user.full_name,
	}


@frappe.whitelist()
def logout():
	set_cors_headers()
	frappe.local.login_manager.logout()
	return {"logged_out": True}


@frappe.whitelist()
def get_wishlist():
	set_cors_headers()
	if frappe.session.user == "Guest":
		return []

	rows = frappe.get_all(
		"Webshop Wishlist", filters={"user": frappe.session.user}, fields=["item_code"]
	)
	if not rows:
		return []

	items = frappe.get_all(
		"Item",
		filters={"name": ["in", [r.item_code for r in rows]]},
		fields=["name as item_code", "item_name", "website_title", "image"],
	)
	return [
		{
			"item_code": i.item_code,
			"item_name": i.website_title or i.item_name,
			"image": full_url(i.image) if i.image else None,
		}
		for i in items
	]


@frappe.whitelist()
def add_to_wishlist(item_code):
	set_cors_headers()
	if frappe.session.user == "Guest":
		frappe.throw(frappe._("سجّل دخولك عشان تحفظ المنتج."), frappe.PermissionError)
	if not frappe.db.exists("Item", item_code):
		frappe.throw(frappe._("المنتج ده مش موجود."))

	if not frappe.db.exists("Webshop Wishlist", {"user": frappe.session.user, "item_code": item_code}):
		doc = frappe.get_doc(
			{"doctype": "Webshop Wishlist", "user": frappe.session.user, "item_code": item_code}
		)
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
	return {"saved": True}


@frappe.whitelist()
def remove_from_wishlist(item_code):
	set_cors_headers()
	if frappe.session.user == "Guest":
		return {"saved": False}
	frappe.db.delete("Webshop Wishlist", {"user": frappe.session.user, "item_code": item_code})
	return {"saved": False}
