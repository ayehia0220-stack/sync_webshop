# -*- coding: utf-8 -*-
"""
خطين واتساب — one number per business, and the log locked to the customer.

The shop runs two lines from one ERP: GPS and coffee. A GPS customer getting a
message from the coffee number, or the reverse, reads as a wrong number — so
each line gets its own WhatsApp account, and the line is chosen from what the
order actually contains.

Routing, in order:
  1. the item groups on the order — GPS items mean the GPS line
  2. the customer group — "GPS Customer" or "Coffee Customer"
  3. whichever line is marked default

Visibility: the messages are Communication records linked to a Customer, so
whoever cannot open the customer cannot read the conversation either. That was
not automatic — Communication is readable by anyone with desk access by default.
"""
import frappe

FIELDS = [
	{"fieldname": "line_name", "label": "اسم الخط", "fieldtype": "Data", "idx": 1,
	 "reqd": 1, "in_list_view": 1, "columns": 2,
	 "description": "مثال: البن · GPS"},
	{"fieldname": "phone_display", "label": "الرقم", "fieldtype": "Data", "idx": 2,
	 "in_list_view": 1, "columns": 2, "translatable": 0},
	{"fieldname": "is_default", "label": "الافتراضي", "fieldtype": "Check", "idx": 3,
	 "in_list_view": 1, "columns": 1},
	{"fieldname": "enabled", "label": "مفعّل", "fieldtype": "Check", "idx": 4,
	 "default": "1", "in_list_view": 1, "columns": 1},
	{"fieldname": "cb1", "fieldtype": "Column Break", "idx": 5},
	{"fieldname": "item_groups", "label": "مجموعات الأصناف", "fieldtype": "Small Text", "idx": 6,
	 "description": "مفصولة بفاصلة. الطلب اللي فيه صنف من دول يروح للخط ده."},
	{"fieldname": "customer_groups", "label": "مجموعات العملاء", "fieldtype": "Small Text", "idx": 7,
	 "description": "مفصولة بفاصلة."},
	{"fieldname": "sec_api", "label": "بيانات ميتا", "fieldtype": "Section Break", "idx": 8},
	{"fieldname": "phone_number_id", "label": "Phone Number ID", "fieldtype": "Data", "idx": 9},
	{"fieldname": "access_token", "label": "Access Token", "fieldtype": "Password", "idx": 10},
	{"fieldname": "cb2", "fieldtype": "Column Break", "idx": 11},
	{"fieldname": "template_confirm", "label": "قالب تأكيد الطلب", "fieldtype": "Data", "idx": 12},
	{"fieldname": "template_shipped", "label": "قالب الشحن", "fieldtype": "Data", "idx": 13},
	{"fieldname": "language", "label": "لغة القالب", "fieldtype": "Data",
	 "idx": 14, "default": "ar"},
]

HELPER = u'''

# ============================================================================
# اختيار خط الواتساب حسب نوع الشغل
# ============================================================================

def _split(text):
	return [p.strip() for p in str(text or "").replace("\\n", ",").split(",") if p.strip()]


def whatsapp_line_for(order_name=None, customer=None):
	"""
	Which WhatsApp number should speak to this customer.

	Decided from the order first, because that is the concrete thing: a box of
	coffee is a coffee conversation whatever group the customer sits in. The
	customer group is the fallback, and a default line catches the rest.
	"""
	settings = frappe.get_single("Webshop Content Settings")
	lines = [l for l in (settings.get("wa_lines") or []) if l.enabled]
	if not lines:
		return None

	groups = set()
	if order_name:
		groups.update(frappe.db.sql_list(
			"""
			SELECT DISTINCT i.item_group FROM `tabSales Order Item` soi
			JOIN `tabItem` i ON i.name = soi.item_code
			WHERE soi.parent = %s
			""",
			order_name))
		customer = customer or frappe.db.get_value("Sales Order", order_name, "customer")

	if groups:
		for line in lines:
			wanted = set(_split(line.item_groups))
			if wanted & groups:
				return line
		# An item group can sit under a configured parent rather than match it.
		for line in lines:
			for wanted in _split(line.item_groups):
				lft, rgt = frappe.db.get_value(
					"Item Group", wanted, ["lft", "rgt"]) or (None, None)
				if not lft:
					continue
				under = frappe.db.sql_list(
					"SELECT name FROM `tabItem Group` WHERE lft >= %s AND rgt <= %s",
					(lft, rgt))
				if groups & set(under):
					return line

	if customer:
		cg = frappe.db.get_value("Customer", customer, "customer_group")
		for line in lines:
			if cg in _split(line.customer_groups):
				return line

	for line in lines:
		if line.is_default:
			return line
	return lines[0]
'''

PERM = u'''

def communication_permission_query(user=None):
	"""
	A WhatsApp log is as private as the customer it belongs to.

	Communication is readable by anyone with desk access out of the box, which
	would have put every customer conversation in front of every employee. This
	narrows the chat records to customers the user can already open, and leaves
	email and everything else untouched.
	"""
	user = user or frappe.session.user
	if "System Manager" in frappe.get_roles(user):
		return ""

	if frappe.has_permission("Customer", "read", user=user):
		return ""

	# No access to customers at all — hide the chat records, keep the rest.
	return "(`tabCommunication`.communication_medium != 'Chat')"
'''


def execute():
	import io

	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	child = "Webshop WhatsApp Line"
	if not frappe.db.exists("DocType", child):
		frappe.conf["developer_mode"] = 1
		frappe.flags.in_migrate = True
		try:
			doc = frappe.get_doc({
				"doctype": "DocType", "name": child, "module": "Sync Webshop",
				"custom": 0, "istable": 1, "editable_grid": 1,
				"fields": FIELDS, "permissions": [],
			})
			doc.flags.ignore_permissions = True
			doc.insert()
			print("created:", child)
		finally:
			frappe.conf["developer_mode"] = 0
			frappe.flags.in_migrate = False

	create_custom_fields({"Webshop Content Settings": [{
		"fieldname": "sec_wa_lines",
		"label": "خطوط واتساب",
		"fieldtype": "Section Break",
		"insert_after": "wa_incoming_url",
		"description": "خط لكل نشاط. الطلب بيروح للخط حسب نوع الأصناف اللي فيه.",
	}, {
		"fieldname": "wa_lines",
		"label": "الخطوط",
		"fieldtype": "Table",
		"options": child,
		"insert_after": "sec_wa_lines",
	}]}, ignore_validate=True)

	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/notifications.py"
	s = io.open(p, encoding="utf-8").read()
	if "def whatsapp_line_for" not in s:
		io.open(p, "w", encoding="utf-8").write(s + HELPER + PERM)
		print("notifications.py: routing + permission")

	h = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/hooks.py"
	s = io.open(h, encoding="utf-8").read()
	if "communication_permission_query" not in s:
		block = ('\npermission_query_conditions = {\n'
		         '\t"Communication":'
		         ' "sync_webshop.api.notifications.communication_permission_query",\n}\n')
		if "permission_query_conditions" in s:
			print("  !! hooks already defines permission_query_conditions — merge by hand")
		else:
			io.open(h, "w", encoding="utf-8").write(s + block)
			print("hooks: communication permission")

	# --- seed the two lines --------------------------------------------------
	settings = frappe.get_single("Webshop Content Settings")
	if not settings.get("wa_lines"):
		settings.append("wa_lines", {
			"line_name": "البن", "phone_display": "01092301212",
			"item_groups": "Coffee - البن", "customer_groups": "Coffee Customer",
			"is_default": 1, "enabled": 1, "language": "ar",
		})
		settings.append("wa_lines", {
			"line_name": "GPS", "phone_display": "",
			"item_groups": "GPS", "customer_groups": "GPS Customer",
			"is_default": 0, "enabled": 1, "language": "ar",
		})
		settings.flags.ignore_permissions = True
		settings.flags.ignore_mandatory = True
		settings.save()
		print("seeded 2 lines")

	frappe.db.commit()
	frappe.clear_cache()
	print("WHATSAPP LINES READY")
