# -*- coding: utf-8 -*-
"""
A visible way into the WhatsApp conversation from the customer.

The messages were already on the customer's timeline, mixed in with every
status change and comment, several scrolls down — technically present and
practically invisible. The owner looked and could not find them, which is the
only test that matters.

So the customer form gets a button with the message count on it, and it opens
the conversation in a dialog: newest last, sent on one side, received on the
other. Same records, somewhere a person will actually look.
"""
import frappe

SCRIPT = u"""// محادثة واتساب — زرار في صفحة العميل
//
// الرسايل كانت في التايم لاين مع باقي الأحداث، فمحدش كان بيلاقيها.

frappe.ui.form.on('Customer', {
    refresh(frm) {
        if (frm.is_new()) return;

        frappe.call({
            method: 'sync_webshop.api.notifications.customer_chat',
            args: { customer: frm.doc.name },
            callback(r) {
                const msgs = (r.message || {}).messages || [];
                const label = msgs.length
                    ? `💬 محادثة واتساب (${msgs.length})`
                    : '💬 محادثة واتساب';

                frm.add_custom_button(label, () => show_chat(frm, msgs));

                if (msgs.length) {
                    const last = msgs[msgs.length - 1];
                    frm.dashboard.add_indicator(
                        `آخر رسالة: ${frappe.datetime.prettyDate(last.creation)}`,
                        last.sent_or_received === 'Received' ? 'orange' : 'green');
                }
            },
        });
    },
});

function show_chat(frm, msgs) {
    const d = new frappe.ui.Dialog({
        title: 'محادثة واتساب — ' + (frm.doc.customer_name || frm.doc.name),
        size: 'large',
        primary_action_label: 'ابعت رسالة',
        primary_action() {
            const text = d.get_value('reply');
            if (!text) return;
            frappe.call({
                method: 'sync_webshop.api.notifications.send_test_message',
                args: { phone: frm.doc.mobile_no, text },
                freeze: true,
                freeze_message: 'جاري الإرسال…',
                callback(r) {
                    const res = r.message || {};
                    frappe.show_alert({
                        message: res.ok ? 'اتبعتت ✅' : 'مااتبعتش: ' + (res.detail || ''),
                        indicator: res.ok ? 'green' : 'red',
                    }, 6);
                    d.hide();
                    frm.refresh();
                },
            });
        },
    });

    const bubbles = msgs.length
        ? msgs.map((m) => {
            const mine = m.sent_or_received === 'Sent';
            return `
              <div style="display:flex;margin:6px 0;
                          justify-content:${mine ? 'flex-start' : 'flex-end'}">
                <div style="max-width:72%;padding:8px 12px;border-radius:12px;
                            background:${mine ? '#2E8F9C' : '#EDF0F1'};
                            color:${mine ? '#fff' : '#22272B'};font-size:13px;
                            line-height:1.7;white-space:pre-wrap">
                  ${frappe.utils.escape_html(m.content || '')}
                  <div style="font-size:10px;opacity:.75;margin-top:4px">
                    ${mine ? 'إحنا' : 'العميل'} · ${frappe.datetime.str_to_user(m.creation)}
                  </div>
                </div>
              </div>`;
        }).join('')
        : '<p style="text-align:center;color:#888;padding:24px">مفيش محادثات لسه.</p>';

    d.$body.html(`
        <div style="max-height:420px;overflow-y:auto;padding:4px 8px;
                    background:#FAFBFB;border-radius:10px">${bubbles}</div>
        <div style="margin-top:12px">
          <textarea class="form-control" rows="2"
                    placeholder="اكتب رسالة للعميل…"
                    onchange="cur_dialog.set_value('reply', this.value)"
                    oninput="cur_dialog.set_value('reply', this.value)"></textarea>
        </div>`);
    d.fields_dict.reply = { value: '' };
    d.set_value = (k, v) => { if (k === 'reply') d._reply = v; };
    d.get_value = (k) => (k === 'reply' ? d._reply : undefined);
    window.cur_dialog = d;
    d.show();
    // Land on the newest message, the way a chat app does.
    setTimeout(() => {
        const box = d.$body.find('div').first()[0];
        if (box) box.scrollTop = box.scrollHeight;
    }, 80);
}
"""

API = u'''

@frappe.whitelist()
def customer_chat(customer, limit=100):
	"""The WhatsApp messages for one customer, oldest first."""
	frappe.has_permission("Customer", "read", doc=customer, throw=True)

	rows = frappe.get_all(
		"Communication",
		filters={
			"communication_medium": "Chat",
			"reference_doctype": "Customer",
			"reference_name": customer,
		},
		fields=["name", "sent_or_received", "content", "phone_no", "creation"],
		order_by="creation asc",
		limit=int(limit))
	return {"messages": rows}
'''


def execute():
	import io

	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/notifications.py"
	s = io.open(p, encoding="utf-8").read()
	if "def customer_chat" not in s:
		io.open(p, "w", encoding="utf-8").write(s + API)
		print("notifications.py: customer_chat")

	name = "Customer WhatsApp Chat"
	doc = frappe.get_doc("Client Script", name) if frappe.db.exists("Client Script", name) \
		else frappe.new_doc("Client Script")
	if doc.is_new():
		doc.name = name
	doc.dt = "Customer"
	doc.view = "Form"
	doc.enabled = 1
	doc.script = SCRIPT
	doc.flags.ignore_permissions = True
	doc.save()

	frappe.db.commit()
	frappe.clear_cache()
	print("CHAT BUTTON READY")
