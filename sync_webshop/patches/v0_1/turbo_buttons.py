# -*- coding: utf-8 -*-
"""
Buttons on the Sales Order, and stop shadowing the field that was already there.

An earlier n8n integration kept the waybill number in custom_turbo_tracking_code,
and the existing "طباعة ستيكر الشحنة" script only draws its button when that
field is filled. Writing the code to a new field of my own silently switched
that button off — the shop noticed before I did. Both fields are written now,
so the old print button and the new panel both work.
"""
import io

import frappe

SCRIPT = u"""// أزرار تربو داخل أمر المبيعات
//
// الشحنة بتتعمل من هنا بدل ما حد يفتح لوحة تربو. الأزرار بتظهر بعد
// تأكيد الطلب بس، لأن شحنة لطلب لسه مسودّة معناها بضاعة بتتشحن قبل
// ما حد يوافق عليها.

frappe.ui.form.on('Sales Order', {
    refresh(frm) {
        if (frm.doc.docstatus !== 1) return;

        if (!frm.doc.turbo_order_number) {
            frm.add_custom_button('🚚 اعمل شحنة تربو', function () {
                frappe.confirm(
                    `هتتبعت شحنة لـ <b>${frm.doc.customer_name || frm.doc.customer}</b><br>`
                    + `تحصيل: <b>${format_currency(frm.doc.grand_total, frm.doc.currency)}</b>`,
                    function () {
                        frappe.dom.freeze('جاري إنشاء الشحنة…');
                        frappe.call({
                            method: 'sync_webshop.api.turbo.create_shipment',
                            args: { order_name: frm.doc.name },
                            callback(r) {
                                frappe.dom.unfreeze();
                                const res = r.message || {};
                                if (res.ok) {
                                    frappe.show_alert({
                                        message: `تم — رقم البوليصة ${res.order_number}`,
                                        indicator: 'green',
                                    }, 7);
                                    frm.reload_doc();
                                } else {
                                    // Turbo's own words, not a generic failure —
                                    // "Location is uncovered" tells the desk what to fix.
                                    frappe.msgprint({
                                        title: 'تربو رفض الشحنة',
                                        message: res.message || 'خطأ غير معروف',
                                        indicator: 'red',
                                    });
                                }
                            },
                            error() { frappe.dom.unfreeze(); },
                        });
                    }
                );
            }, 'تربو');
        } else {
            frm.add_custom_button('🔄 حدّث الحالة من تربو', function () {
                frappe.dom.freeze('بنسأل تربو…');
                frappe.call({
                    method: 'sync_webshop.api.turbo.refresh_status',
                    args: { order_name: frm.doc.name },
                    callback() { frappe.dom.unfreeze(); frm.reload_doc(); },
                    error() { frappe.dom.unfreeze(); },
                });
            }, 'تربو');

            frm.add_custom_button('❌ ألغي الشحنة', function () {
                frappe.confirm('متأكد إنك عايز تلغي الشحنة عند تربو؟', function () {
                    frappe.call({
                        method: 'sync_webshop.api.turbo.cancel_shipment',
                        args: { order_name: frm.doc.name },
                        callback(r) {
                            const res = r.message || {};
                            if (!res.ok) {
                                frappe.msgprint({
                                    title: 'تربو رفض الإلغاء',
                                    message: res.message || '',
                                    indicator: 'orange',
                                });
                            }
                            frm.reload_doc();
                        },
                    });
                });
            }, 'تربو');

            frm.dashboard.add_indicator(
                `تربو: ${frm.doc.turbo_status_text || 'اتبعتت'} — ${frm.doc.turbo_order_number}`,
                frm.doc.turbo_status_text ? 'green' : 'blue'
            );
        }
    },
});
"""


def execute():
	# --- keep the older field in step, so the print button keeps working -----
	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/turbo.py"
	s = io.open(p, encoding="utf-8").read()
	if "custom_turbo_tracking_code" not in s:
		old = '''	order.db_set({
		"turbo_order_number": str(number),'''
		new = '''	order.db_set({
		"turbo_order_number": str(number),
		# The waybill print button predates this integration and reads the
		# older field; leaving it empty switched that button off.
		"custom_turbo_tracking_code": str(number),'''
		if old not in s:
			frappe.throw("db_set block not found")
		s = s.replace(old, new, 1)

		# --- a refresh-one-order endpoint for the button ---------------------
		s += u'''

@frappe.whitelist()
def refresh_status(order_name):
	"""Ask Turbo about one order now, for the button on the form."""
	creds = _credentials()
	if not creds:
		frappe.throw(frappe._("\\u062a\\u0631\\u0628\\u0648 \\u0645\\u0642\\u0641\\u0648\\u0644."))

	number = frappe.db.get_value("Sales Order", order_name, "turbo_order_number")
	if not number:
		frappe.throw(frappe._("\\u0645\\u0641\\u064a\\u0634 \\u0634\\u062d\\u0646\\u0629 \\u0644\\u0644\\u0637\\u0644\\u0628 \\u062f\\u0647."))

	ok, result = _call("/external-api/search-order",
	                   {"search_Key": str(number)}, creds)
	if not ok:
		return {"ok": False, "message": result}

	rows = result.get("result") or result.get("feed") or []
	if isinstance(rows, dict):
		rows = [rows]
	if not rows:
		return {"ok": False, "message": "not found at Turbo"}

	_apply_status(order_name, rows[0])
	frappe.db.commit()
	return {"ok": True}
'''
		io.open(p, "w", encoding="utf-8").write(s)
		print("turbo.py: tracking code mirrored + refresh_status")

	# --- the buttons ---------------------------------------------------------
	name = "Turbo Shipment Buttons"
	if frappe.db.exists("Client Script", name):
		doc = frappe.get_doc("Client Script", name)
	else:
		doc = frappe.new_doc("Client Script")
		doc.name = name
	doc.dt = "Sales Order"
	doc.view = "Form"
	doc.enabled = 1
	doc.script = SCRIPT
	doc.flags.ignore_permissions = True
	doc.save()

	# --- backfill so the print button returns on the order already shipped ---
	fixed = 0
	for row in frappe.get_all(
		"Sales Order",
		filters={"turbo_order_number": ["not in", ["", None]]},
		fields=["name", "turbo_order_number", "custom_turbo_tracking_code"],
	):
		if not row.custom_turbo_tracking_code:
			frappe.db.set_value("Sales Order", row.name, "custom_turbo_tracking_code",
			                    row.turbo_order_number, update_modified=False)
			fixed += 1

	frappe.db.commit()
	frappe.clear_cache()
	print("BUTTONS READY — backfilled %d order(s)" % fixed)
