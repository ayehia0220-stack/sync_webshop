# -*- coding: utf-8 -*-
"""
Fill the collection amount while the order is still a draft.

On the server the field fills itself during validate, so a script-created order
saves fine. In the browser it does not: Frappe checks mandatory fields before it
sends anything, finds the box empty, and refuses — which is what Doha kept
hitting. The old script only filled the box after submit, which is too late to
help her submit.

Now it fills as soon as there is a total, and refills whenever the total moves.
She can raise it, she cannot lower it, and ticking the review box is only
required to create the shipment — never to save the order.
"""
import frappe

SCRIPT = u"""// المطلوب تحصيله — بيتحسب وانت بتكتب الطلب
//
// بيتملّى وهو مسودّة عشان الحقل الإجباري ميوقفكش عند الحفظ. تقدر تزوّده
// لو في مصاريف زيادة، بس مش تقلله — ده الغلط الوحيد اللي بيضيّع فلوس.

frappe.ui.form.on('Sales Order', {
    refresh(frm) { dpono_sync_cod(frm); },
    grand_total(frm) { dpono_sync_cod(frm); },
    advance_paid(frm) { dpono_sync_cod(frm); },

    turbo_cod_amount(frm) {
        // The tick approved a number. A different number needs a new look.
        if (frm.doc.turbo_cod_confirmed) {
            frm.set_value('turbo_cod_confirmed', 0);
            frappe.show_alert({ message: 'المبلغ اتغير — راجعه وعلّم تاني', indicator: 'orange' }, 5);
        }
    },
});

function dpono_sync_cod(frm) {
    if (frm.doc.docstatus === 2) return;

    const total = flt(frm.doc.grand_total);
    const paid = flt(frm.doc.advance_paid);
    const owed = Math.max(0, Math.round((total - paid) * 100) / 100);

    frm.set_df_property('turbo_cod_amount', 'description',
        total
            ? 'الحد الأدنى ' + format_currency(owed, frm.doc.currency) + ' — تقدر تزوّد، مش تقلل.'
            : 'هيتحسب لوحده أول ما تضيف أصناف.');

    // Empty, or still equal to a total that has since changed — keep it in step.
    const current = flt(frm.doc.turbo_cod_amount);
    if (total && (!current || current < owed)) {
        frm.set_value('turbo_cod_amount', owed);
    }
}
"""


def execute():
	# The box is only required once there is something to collect, and by then
	# the script above has already filled it.
	name = frappe.db.get_value(
		"Custom Field", {"dt": "Sales Order", "fieldname": "turbo_cod_amount"}, "name")
	if name:
		frappe.db.set_value("Custom Field", name, {
			"mandatory_depends_on": "eval:doc.docstatus==1 && doc.grand_total>0",
			"description": "الإجمالي ناقص المدفوع. تقدر تزوّده، مش تقلله.",
			"read_only": 0,
			"permlevel": 0,
			"allow_on_submit": 1,
		})

	# She has to be able to tick it after the order is submitted, which is when
	# the shipment is actually created.
	conf = frappe.db.get_value(
		"Custom Field", {"dt": "Sales Order", "fieldname": "turbo_cod_confirmed"}, "name")
	if conf:
		frappe.db.set_value("Custom Field", conf, {
			"allow_on_submit": 1,
			"permlevel": 0,
			"read_only": 0,
		})

	doc = frappe.get_doc("Client Script", "Sales Order COD Amount")
	doc.script = SCRIPT
	doc.enabled = 1
	doc.flags.ignore_permissions = True
	doc.save()

	frappe.db.commit()
	frappe.clear_cache()
	print("COD UX READY")
