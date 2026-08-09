import random

import frappe

from sync_webshop.api.utils import set_cors_headers

OTP_TTL_SECONDS = 10 * 60
OTP_MAX_PER_WINDOW = 3
OTP_WINDOW_SECONDS = 10 * 60


def _normalise_phone(phone):
	"""Compare phone numbers by digits only — people type them many ways."""
	return "".join(ch for ch in (phone or "") if ch.isdigit())[-9:] or None


def _find_customer(email=None, phone=None):
	contact_name = None
	if email:
		contact_name = frappe.db.get_value("Contact Email", {"email_id": email}, "parent") or frappe.db.get_value(
			"Contact", {"email_id": email}, "name"
		)
	if not contact_name and phone:
		digits = _normalise_phone(phone)
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
	if not contact_name:
		return None

	links = frappe.get_all(
		"Dynamic Link",
		filters={"parent": contact_name, "parenttype": "Contact", "link_doctype": "Customer"},
		fields=["link_name"],
	)
	return links[0].link_name if links else None


def _order_items(order_name):
	return frappe.get_all(
		"Sales Order Item",
		filters={"parent": order_name},
		fields=["item_code", "item_name", "qty", "rate", "amount"],
	)


def _order_payload(order):
	order = dict(order)
	order["items"] = _order_items(order["name"])
	notes = frappe.get_all(
		"Delivery Note Item",
		filters={"against_sales_order": order["name"]},
		fields=["parent"],
		group_by="parent",
	)
	order["delivery_notes"] = [
		frappe.db.get_value("Delivery Note", n.parent, ["name", "status", "tracking_number"], as_dict=True)
		for n in notes
	]
	return order


ORDER_FIELDS = [
	"name",
	"transaction_date",
	"delivery_date",
	"status",
	"grand_total",
	"currency",
	"docstatus",
	"tracking_number",
	"webshop_payment_status",
	"webshop_payment_method",
]


@frappe.whitelist(allow_guest=True)
def get_order_status(order_name, email=None, phone=None):
	"""
	Guest order lookup. The order number alone is not enough — order numbers run
	in sequence, so anyone could walk the whole list. The caller must also prove
	they know the email or phone the order was placed with.
	"""
	set_cors_headers()

	if not order_name:
		frappe.throw(frappe._("رقم الطلب مطلوب."))
	if not email and not phone:
		frappe.throw(frappe._("اكتب البريد أو رقم الموبايل اللي طلبت بيه."))

	customer = _find_customer(email=email, phone=phone)
	if not customer:
		# Same message either way, so this can't be used to test which emails exist.
		frappe.throw(frappe._("مفيش طلب بالبيانات دي."))

	order = frappe.db.get_value(
		"Sales Order",
		{"name": order_name, "customer": customer},
		ORDER_FIELDS,
		as_dict=True,
	)
	if not order:
		frappe.throw(frappe._("مفيش طلب بالبيانات دي."))

	return _order_payload(order)


def _otp_key(email):
	return f"webshop:otp:{(email or '').strip().lower()}"


def _otp_rate_key(email):
	return f"webshop:otp:rate:{(email or '').strip().lower()}"


@frappe.whitelist(allow_guest=True)
def request_order_access(email):
	"""
	Email a short code before showing someone every order on an address.
	Always reports success so the endpoint can't be used to discover customers.
	"""
	set_cors_headers()
	email = (email or "").strip().lower()
	if not email or "@" not in email:
		frappe.throw(frappe._("اكتب بريد إلكتروني صحيح."))

	cache = frappe.cache()
	attempts = int(cache.get_value(_otp_rate_key(email)) or 0)
	if attempts >= OTP_MAX_PER_WINDOW:
		frappe.throw(frappe._("طلبات كتير. جرّب تاني بعد شوية."))
	cache.set_value(_otp_rate_key(email), attempts + 1, expires_in_sec=OTP_WINDOW_SECONDS)

	customer = _find_customer(email=email)
	if customer:
		code = f"{random.randint(0, 999999):06d}"
		cache.set_value(_otp_key(email), code, expires_in_sec=OTP_TTL_SECONDS)
		frappe.sendmail(
			recipients=[email],
			subject=frappe._("كود الدخول لطلباتك"),
			message=(
				"<div dir='rtl' style='font-family:Tahoma'>"
				f"<p>كود الدخول لطلباتك: <b style='font-size:22px;letter-spacing:3px'>{code}</b></p>"
				"<p>الكود صالح لعشر دقائق. لو مطلبتش الكود ده، تجاهل الرسالة.</p>"
				"</div>"
			),
			now=True,
		)

	return {"sent": True}


@frappe.whitelist(allow_guest=True)
def list_my_orders(email=None, code=None, phone=None):
	"""
	Every order on an email address, behind the code sent by request_order_access.
	Without the code this would hand a customer's order history to anyone who
	could guess their email.
	"""
	set_cors_headers()
	email = (email or "").strip().lower()

	if not email:
		frappe.throw(frappe._("اكتب البريد اللي طلبت بيه."))
	if not code:
		frappe.throw(frappe._("اكتب الكود اللي وصلك على البريد."))

	expected = frappe.cache().get_value(_otp_key(email))
	if isinstance(expected, bytes):
		expected = expected.decode()
	if not expected or str(code).strip() != str(expected):
		frappe.throw(frappe._("الكود مش صحيح أو انتهت صلاحيته."))

	# One code, one use.
	frappe.cache().delete_value(_otp_key(email))

	customer = _find_customer(email=email)
	if not customer:
		return {"customer": None, "orders": []}

	orders = frappe.get_all(
		"Sales Order",
		filters={"customer": customer},
		fields=ORDER_FIELDS,
		order_by="creation desc",
		limit_page_length=50,
	)
	return {
		"customer": customer,
		"orders": [_order_payload(o) for o in orders],
	}
