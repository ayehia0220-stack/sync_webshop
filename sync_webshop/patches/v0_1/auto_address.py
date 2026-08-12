# -*- coding: utf-8 -*-
"""
Fill "Address for Customer" from the customer's own address.

The field is typed by hand on 2,743 orders. The address is already on the
customer record, so retyping it is work that also introduces typos — and the
courier reads this field.

Two places, on purpose: the client script fills it the moment a customer is
picked, so whoever is on the form sees it and can correct it; the server hook
fills it on save, catching orders created by the API, an import, or a duplicate.

Anything already typed is never overwritten. A blank field means nobody has
decided yet; a filled one means somebody has.
"""
import io

import frappe

HELPER = u'''

# ============================================================================
# عنوان العميل — filled from the customer record
# ============================================================================

def _preferred_address(customer):
	"""
	The address to put on the order.

	Shipping beats billing because this field is what the courier reads, and
	the primary flag beats the rest. Falls back to whatever exists rather than
	leaving the field empty.
	"""
	rows = frappe.db.sql(
		"""
		SELECT a.name, a.address_type, a.is_primary_address, a.is_shipping_address
		FROM `tabAddress` a
		JOIN `tabDynamic Link` dl ON dl.parent = a.name AND dl.parenttype = 'Address'
		WHERE dl.link_doctype = 'Customer' AND dl.link_name = %s
		  AND IFNULL(a.disabled, 0) = 0
		ORDER BY a.is_shipping_address DESC, a.is_primary_address DESC, a.modified DESC
		LIMIT 1
		""",
		customer, as_dict=True)
	return rows[0].name if rows else None


def format_address(address_name):
	"""One readable line: street, area, city."""
	if not address_name:
		return ""
	addr = frappe.db.get_value(
		"Address", address_name,
		["address_line1", "address_line2", "city"], as_dict=True)
	if not addr:
		return ""
	parts = [(addr.address_line1 or "").strip(),
	         (addr.address_line2 or "").strip(),
	         (addr.city or "").strip()]
	# "-" is what the checkout writes when a city is unknown; it reads as noise.
	return " - ".join(p for p in parts if p and p != "-")


@frappe.whitelist()
def address_for_customer(customer):
	"""Called by the form the moment a customer is chosen."""
	if not customer:
		return {"address": ""}
	return {"address": format_address(_preferred_address(customer))}


def fill_customer_address(doc, method=None):
	"""Fill the field on save, but never over something a person typed."""
	if doc.get("custom_address_for_customer_"):
		return
	if not doc.get("customer"):
		return

	# An address already chosen on the order is more specific than the
	# customer's default, so it wins.
	source = doc.get("shipping_address_name") or doc.get("customer_address") \\
		or _preferred_address(doc.customer)
	text = format_address(source)
	if text:
		doc.custom_address_for_customer_ = text[:140]
'''

SCRIPT = u"""// عنوان العميل بيتملّى لوحده أول ما تختار العميل
//
// بيتملّى وهو قدامك عشان تقدر تصححه قبل الحفظ، مش بعده. ولو كاتب حاجة
// بإيدك، مش بيلمسها.

frappe.ui.form.on('Sales Order', {
    customer(frm) {
        if (!frm.doc.customer) return;
        if ((frm.doc.custom_address_for_customer_ || '').trim()) return;

        frappe.call({
            method: 'sync_webshop.api.turbo.address_for_customer',
            args: { customer: frm.doc.customer },
            callback(r) {
                const text = (r.message || {}).address;
                if (!text) return;
                frm.set_value('custom_address_for_customer_', text);
                frappe.show_alert({ message: 'اتجاب عنوان العميل', indicator: 'green' }, 4);
            },
        });
    },
});
"""


def execute():
	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/turbo.py"
	s = io.open(p, encoding="utf-8").read()
	if "def fill_customer_address" not in s:
		io.open(p, "w", encoding="utf-8").write(s + HELPER)
		print("turbo.py: address helpers")

	h = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/hooks.py"
	s = io.open(h, encoding="utf-8").read()
	if "fill_customer_address" not in s:
		old = '\t"Sales Order": {\n\t\t"on_submit":'
		new = ('\t"Sales Order": {\n'
		       '\t\t"validate": "sync_webshop.api.turbo.fill_customer_address",\n'
		       '\t\t"on_submit":')
		if old not in s:
			frappe.throw("Sales Order hooks block not found")
		io.open(h, "w", encoding="utf-8").write(s.replace(old, new, 1))
		print("hooks: validate")

	name = "Sales Order Customer Address"
	doc = frappe.get_doc("Client Script", name) if frappe.db.exists("Client Script", name) \
		else frappe.new_doc("Client Script")
	if doc.is_new():
		doc.name = name
	doc.dt = "Sales Order"
	doc.view = "Form"
	doc.enabled = 1
	doc.script = SCRIPT
	doc.flags.ignore_permissions = True
	doc.save()

	frappe.db.commit()
	frappe.clear_cache()
	print("AUTO ADDRESS READY")
