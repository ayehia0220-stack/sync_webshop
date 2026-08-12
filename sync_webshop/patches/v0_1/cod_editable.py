# -*- coding: utf-8 -*-
"""
Make the collection amount editable, confirmed, and impossible to lower.

It was read-only, which meant a wrong figure could only be fixed by changing the
payments. Now the desk can correct it — upwards. Downwards is refused, because
the one mistake that costs the shop money is sending the courier to collect less
than the customer owes, and that mistake is invisible until the cash is counted.

A tick beside it records that a person looked at the number. It has to be on
before the shipment goes, so nobody ships on an amount nobody read.
"""
import io

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELDS = {
	"Sales Order": [
		{
			"fieldname": "turbo_cod_confirmed",
			"label": "راجعت المبلغ ✔",
			"fieldtype": "Check",
			"default": "0",
			"insert_after": "turbo_cod_amount",
			"description": "علّم هنا بعد ما تتأكد إن المبلغ صح. لازم قبل إنشاء الشحنة.",
		},
	],
}

HOOK = u'''

def check_cod_amount(doc, method=None):
	"""
	Keep the collection amount honest.

	Empty means nobody has set it, so it takes the computed balance. A number
	below that balance is refused — raising it is a business call (a surcharge,
	a rounding up), lowering it is money the shop will not see.
	"""
	if doc.docstatus == 2:
		return

	expected = amount_still_owed(doc)
	current = doc.get("turbo_cod_amount")

	if current in (None, ""):
		doc.turbo_cod_amount = expected
		return

	if float(current) < expected - 0.01:
		frappe.throw(
			frappe._(
				"\\u0627\\u0644\\u0645\\u0637\\u0644\\u0648\\u0628 \\u062a\\u062d\\u0635\\u064a\\u0644\\u0647 \\u0645\\u0627\\u064a\\u0646\\u0641\\u0639\\u0634 \\u064a\\u0642\\u0644 \\u0639\\u0646 {0}. "
				"\\u0627\\u0644\\u0625\\u062c\\u0645\\u0627\\u0644\\u064a {1} \\u0646\\u0627\\u0642\\u0635 \\u0627\\u0644\\u0645\\u062f\\u0641\\u0648\\u0639 {2}."
			).format(
				frappe.format_value(expected, {"fieldtype": "Currency"}),
				frappe.format_value(doc.grand_total or 0, {"fieldtype": "Currency"}),
				frappe.format_value((doc.grand_total or 0) - expected, {"fieldtype": "Currency"}),
			),
			title=frappe._("\\u0645\\u0628\\u0644\\u063a \\u0627\\u0644\\u062a\\u062d\\u0635\\u064a\\u0644"),
		)
'''

SCRIPT = u"""// المطلوب تحصيله — بيتحسب لوحده وبيتقفل على حد أدنى
//
// الرقم بيظهر أول ما تفتح الطلب، وتقدر تزوّده بس مش تقلله. القفل ده
// عشان الغلط الوحيد اللي بيضيّع فلوس هو إن المندوب يحصّل أقل من المستحق.

frappe.ui.form.on('Sales Order', {
    refresh(frm) {
        if (frm.doc.docstatus !== 1) return;
        if (frm.doc.turbo_order_number) return;

        frappe.call({
            method: 'sync_webshop.api.turbo.expected_cod',
            args: { order_name: frm.doc.name },
            callback(r) {
                const owed = (r.message || {}).owed;
                if (owed === undefined) return;
                frm.set_df_property('turbo_cod_amount', 'description',
                    'الحد الأدنى ' + format_currency(owed, frm.doc.currency)
                    + ' — تقدر تزوّد، مش تقلل.');
                if (!frm.doc.turbo_cod_amount) {
                    frm.set_value('turbo_cod_amount', owed);
                }
            },
        });
    },

    turbo_cod_amount(frm) {
        // Changing the figure invalidates whoever confirmed the old one.
        if (frm.doc.turbo_cod_confirmed) {
            frm.set_value('turbo_cod_confirmed', 0);
            frappe.show_alert({ message: 'المبلغ اتغير — راجعه وعلّم تاني', indicator: 'orange' }, 5);
        }
    },
});
"""


def execute():
	create_custom_fields(FIELDS, ignore_validate=True)

	# Editable now, and required once a shipment is on the cards.
	name = frappe.db.get_value(
		"Custom Field", {"dt": "Sales Order", "fieldname": "turbo_cod_amount"}, "name")
	if name:
		frappe.db.set_value("Custom Field", name, {
			"read_only": 0,
			"mandatory_depends_on": "eval:doc.docstatus==1",
			"description": "الإجمالي ناقص اللي اتدفع. تقدر تزوّده، مش تقلله.",
		})

	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/turbo.py"
	s = io.open(p, encoding="utf-8").read()
	if "def check_cod_amount" not in s:
		s += HOOK + u'''

@frappe.whitelist()
def expected_cod(order_name):
	"""The floor for this order, for the form to show and default to."""
	order = frappe.get_doc("Sales Order", order_name)
	return {"owed": amount_still_owed(order)}
'''
		io.open(p, "w", encoding="utf-8").write(s)
		print("turbo.py: cod guard")

	h = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/hooks.py"
	s = io.open(h, encoding="utf-8").read()
	if "check_cod_amount" not in s:
		old = '\t\t"validate": "sync_webshop.api.turbo.fill_customer_address",'
		new = ('\t\t"validate": [\n'
		       '\t\t\t"sync_webshop.api.turbo.fill_customer_address",\n'
		       '\t\t\t"sync_webshop.api.turbo.check_cod_amount",\n'
		       '\t\t],')
		if old not in s:
			frappe.throw("validate hook line not found")
		io.open(h, "w", encoding="utf-8").write(s.replace(old, new, 1))
		print("hooks: cod validate")

	cs = "Sales Order COD Amount"
	doc = frappe.get_doc("Client Script", cs) if frappe.db.exists("Client Script", cs) \
		else frappe.new_doc("Client Script")
	if doc.is_new():
		doc.name = cs
	doc.dt = "Sales Order"
	doc.view = "Form"
	doc.enabled = 1
	doc.script = SCRIPT
	doc.flags.ignore_permissions = True
	doc.save()

	frappe.db.commit()
	frappe.clear_cache()
	print("COD GUARD READY")
