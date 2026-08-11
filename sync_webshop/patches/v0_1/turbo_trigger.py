# -*- coding: utf-8 -*-
"""
تحرك الطلبات — the shipment fires from the status the desk already sets.

The team was already marking "تم عمل الشحنه" by hand and then creating the
waybill in Turbo's own panel. That second step is the one that gets forgotten,
so setting the status now creates the shipment.

"تسليم لاتجاه اخر" means the goods left with someone who is not Turbo. Who that
was is the only record of where the stock went, so the field is required — an
order in that state with a blank handler is an untraceable parcel.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SHIPPED = "تم عمل الشحنه"
OTHER = "تسليم لاتجاه اخر"

FIELDS = {
	"Sales Order": [
		{
			"fieldname": "custom_other_handover_to",
			"label": "اتسلّم لمين؟",
			"fieldtype": "Data",
			"insert_after": "custom_preparation_status",
			"depends_on": "eval:doc.custom_preparation_status=='%s'" % OTHER,
			"mandatory_depends_on": "eval:doc.custom_preparation_status=='%s'" % OTHER,
			"translatable": 0,
			"description": "اسم الشخص أو الشركة اللي استلمت الطلب — إجباري.",
		},
		{
			"fieldname": "custom_other_handover_note",
			"label": "تفاصيل التسليم",
			"fieldtype": "Small Text",
			"insert_after": "custom_other_handover_to",
			"depends_on": "eval:doc.custom_preparation_status=='%s'" % OTHER,
			"translatable": 0,
			"description": "رقم تليفون، وقت الاستلام، أو أي ملاحظة.",
		},
	],
}

HOOK = '''

def on_preparation_status(doc, method=None):
	"""
	Create the Turbo shipment when the desk marks the order as shipped.

	Guarded three ways: the setting has to be on, the order has to be submitted,
	and it must not already carry a waybill — a status re-saved twice would
	otherwise book the same parcel twice.
	"""
	if doc.get("custom_preparation_status") != "\\u062a\\u0645 \\u0639\\u0645\\u0644 \\u0627\\u0644\\u0634\\u062d\\u0646\\u0647":
		return
	if doc.docstatus != 1 or doc.get("turbo_order_number"):
		return

	try:
		settings = frappe.get_single("Webshop Turbo Settings")
	except Exception:
		return
	if not settings.get("enabled") or not settings.get("auto_create"):
		return

	from sync_webshop.api.turbo import create_shipment

	result = create_shipment(doc.name)
	if result.get("ok"):
		frappe.msgprint(
			frappe._("\\u062a\\u0645 \\u0639\\u0645\\u0644 \\u0627\\u0644\\u0634\\u062d\\u0646\\u0629 \\u2014 ") + str(result.get("order_number")),
			indicator="green", alert=True)
	else:
		# Loud on purpose: a silent failure here means the desk believes the
		# parcel is booked when Turbo never heard about it.
		frappe.msgprint(
			frappe._("\\u062a\\u0631\\u0628\\u0648 \\u0631\\u0641\\u0636 \\u0627\\u0644\\u0634\\u062d\\u0646\\u0629") + ": " + str(result.get("message")),
			indicator="red", title=frappe._("\\u0627\\u0644\\u0634\\u062d\\u0646\\u0629 \\u0645\\u0627\\u062a\\u0645\\u062a\\u0634"))
'''


def execute():
	import io

	create_custom_fields(FIELDS, ignore_validate=True)

	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/turbo.py"
	s = io.open(p, encoding="utf-8").read()
	if "def on_preparation_status" not in s:
		io.open(p, "w", encoding="utf-8").write(s + HOOK)
		print("turbo.py: status hook")

	h = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/hooks.py"
	s = io.open(h, encoding="utf-8").read()
	if "on_preparation_status" not in s:
		# on_update_after_submit is already taken; Frappe accepts a list, so both
		# handlers run rather than one quietly replacing the other.
		old = ('\t\t"on_update_after_submit": '
		       '"sync_webshop.api.notifications.on_sales_order_update"')
		new = ('\t\t"on_update_after_submit": [\n'
		       '\t\t\t"sync_webshop.api.notifications.on_sales_order_update",\n'
		       '\t\t\t"sync_webshop.api.turbo.on_preparation_status",\n'
		       '\t\t]')
		if old not in s:
			frappe.throw("on_update_after_submit line not found")
		s = s.replace(old, new, 1)
		io.open(h, "w", encoding="utf-8").write(s)
		print("hooks: both handlers registered")

	frappe.db.commit()
	frappe.clear_cache()
	print("TRIGGER READY")
