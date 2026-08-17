# -*- coding: utf-8 -*-
"""
سجل محادثات واتساب — WhatsApp messages on the customer's timeline.

Calls already land in Call Log, so the obvious question is why messages do not.
They can, and the right home is Communication: ERPNext's own record of "someone
said something to someone", already wired into every customer's activity feed
and already used for email here. A separate WhatsApp doctype would mean a second
place to look for the same kind of fact.

Two directions:
  * outgoing — logged by the sender itself, so nothing can be sent without a
    trace of it
  * incoming — logged by a webhook Meta calls when a customer replies

Matching a message to a customer is done on the phone number, normalised the
same way everywhere: an Egyptian mobile written six different ways is one
customer.
"""
import frappe

HELPER = u'''

# ============================================================================
# سجل محادثات واتساب
# ============================================================================

def _digits(phone):
	return "".join(ch for ch in str(phone or "") if ch.isdigit())


def customer_by_phone(phone):
	"""
	Which customer this number belongs to.

	Numbers are stored inconsistently — with the country code, without it, with
	spaces — so the last nine digits are what gets compared. That is enough to
	identify an Egyptian mobile and short enough to survive the formatting.
	"""
	tail = _digits(phone)[-9:]
	if len(tail) < 9:
		return None

	for query in (
		"SELECT name FROM `tabCustomer` WHERE REPLACE(REPLACE(IFNULL(mobile_no,''),' ',''),'+','') LIKE %s LIMIT 1",
		"""SELECT so.customer FROM `tabSales Order` so
		   WHERE REPLACE(REPLACE(IFNULL(so.custom_customer_phone_number,''),' ',''),'+','') LIKE %s
		   ORDER BY so.creation DESC LIMIT 1""",
	):
		rows = frappe.db.sql(query, "%" + tail)
		if rows and rows[0][0]:
			return rows[0][0]
	return None


def log_whatsapp(phone, message, sent=True, customer=None, reference=None):
	"""
	Record one WhatsApp message against the customer.

	Never raises: a logging failure must not stop a message going out or a
	webhook returning 200, or Meta will retry forever.
	"""
	try:
		customer = customer or customer_by_phone(phone)
		doc = frappe.get_doc({
			"doctype": "Communication",
			"communication_type": "Communication",
			"communication_medium": "Chat",
			"content": (message or "")[:5000],
			"subject": ("\\u0648\\u0627\\u062a\\u0633\\u0627\\u0628 " +
			            ("\\u0635\\u0627\\u062f\\u0631" if sent else "\\u0648\\u0627\\u0631\\u062f")),
			"sent_or_received": "Sent" if sent else "Received",
			"phone_no": str(phone or "")[:40],
			"status": "Linked" if customer else "Open",
			"reference_doctype": "Customer" if customer else None,
			"reference_name": customer,
		})
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert()

		# Also pin it to the order it was about, when there is one.
		if reference and frappe.db.exists("Sales Order", reference):
			doc.db_set("timeline_doctype", "Sales Order", update_modified=False)
			doc.db_set("timeline_name", reference, update_modified=False)
		return doc.name
	except Exception:
		frappe.log_error(title="WhatsApp log failed",
		                 message=frappe.get_traceback()[:2000])
		return None


@frappe.whitelist(allow_guest=True)
def incoming_webhook():
	"""
	Meta calls this when a customer sends a message.

	Verification (hub.challenge) and delivery share one endpoint, which is how
	Meta expects it. The reply is always 200 — an error here makes Meta retry
	the same message for hours.
	"""
	from sync_webshop.api.utils import set_cors_headers
	set_cors_headers()

	# Meta verifies the endpoint once, with a GET.
	args = frappe.local.form_dict
	if args.get("hub.mode") == "subscribe":
		settings = frappe.get_single("Webshop Content Settings")
		expected = settings.get_password("wa_verify_token", raise_exception=False)
		if expected and args.get("hub.verify_token") == expected:
			frappe.local.response["type"] = "page"
			frappe.local.response["page_name"] = args.get("hub.challenge")
			return
		return {"ok": False}

	try:
		data = frappe.request.get_json(force=True, silent=True) or {}
		for entry in data.get("entry", []):
			for change in entry.get("changes", []):
				value = change.get("value") or {}
				for msg in value.get("messages", []):
					body = ((msg.get("text") or {}).get("body")
					        or "[%s]" % msg.get("type", "media"))
					log_whatsapp(msg.get("from"), body, sent=False)
		frappe.db.commit()
	except Exception:
		frappe.log_error(title="WhatsApp webhook", message=frappe.get_traceback()[:2000])

	return {"ok": True}
'''


def execute():
	import io

	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields({"Webshop Content Settings": [{
		"fieldname": "wa_verify_token",
		"label": "كلمة التحقق للويب هوك",
		"fieldtype": "Password",
		"insert_after": "wa_language",
		"description": "اختار أي كلمة وحطها هنا وفي لوحة ميتا — بيتأكدوا بيها من اللينك.",
	}, {
		"fieldname": "wa_incoming_url",
		"label": "لينك استقبال الرسايل",
		"fieldtype": "Small Text",
		"insert_after": "wa_verify_token",
		"read_only": 1,
		"description": "انسخه لميتا في إعدادات الـ Webhook.",
	}]}, ignore_validate=True)

	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/notifications.py"
	s = io.open(p, encoding="utf-8").read()
	if "def log_whatsapp" not in s:
		s += HELPER
		# Every outgoing template send gets recorded where it happens.
		old = '\tif not ok:\n\t\t# Logged, not swallowed'
		new = ('\tlog_whatsapp(to, "\\u0642\\u0627\\u0644\\u0628: " + str(template), sent=True)\n\n'
		       '\tif not ok:\n\t\t# Logged, not swallowed')
		if old in s:
			s = s.replace(old, new, 1)
			print("send now logs")
		io.open(p, "w", encoding="utf-8").write(s)
		print("notifications.py: whatsapp log")

	settings = frappe.get_single("Webshop Content Settings")
	settings.wa_incoming_url = (
		"https://erp1.dpono.com/api/method/"
		"sync_webshop.api.notifications.incoming_webhook")
	settings.flags.ignore_permissions = True
	settings.flags.ignore_mandatory = True
	settings.save()

	frappe.db.commit()
	frappe.clear_cache()
	print("WHATSAPP LOG READY")
	print("  webhook:", settings.wa_incoming_url)
