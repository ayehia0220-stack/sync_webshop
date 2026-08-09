# -*- coding: utf-8 -*-
"""
Order emails the customer actually receives, with the wording living in
ERPNext Email Templates so it is edited in the Desk.

The copy states only what the order record says. No delivery promises, no
guarantees, no offers.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

TOGGLES = {
	"Webshop Content Settings": [
		{
			"fieldname": "notifications_section",
			"label": "رسائل الطلبات — Order Emails",
			"fieldtype": "Section Break",
			"insert_after": "email_address",
			"collapsible": 0,
		},
		{
			"fieldname": "send_order_confirmation",
			"label": "Send Order Confirmation",
			"fieldtype": "Check",
			"default": "1",
			"insert_after": "notifications_section",
			"description": "رسالة تأكيد للعميل أول ما الطلب يتأكد. القالب: Webshop Order Confirmation",
		},
		{
			"fieldname": "send_shipping_notification",
			"label": "Send Shipping Notification",
			"fieldtype": "Check",
			"default": "1",
			"insert_after": "send_order_confirmation",
			"description": "رسالة أول ما يتكتب رقم شحنة على الطلب. القالب: Webshop Order Shipped",
		},
	],
}

CONFIRMATION_HTML = """<div dir="rtl" style="font-family:Tahoma,Arial,sans-serif;max-width:560px;margin:auto;color:#253D4E">
  <h2 style="color:#21504C;margin:0 0 6px">تم استلام طلبك</h2>
  <p style="margin:0 0 18px;color:#5B6A72">شكرًا {{ customer_name }} — ده ملخص طلبك من {{ store_name }}.</p>

  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <tr><td style="padding:6px 0;color:#7E7E7E">رقم الطلب</td><td style="text-align:left"><b>{{ order_id }}</b></td></tr>
    <tr><td style="padding:6px 0;color:#7E7E7E">تاريخ التوصيل</td><td style="text-align:left">{{ delivery_date }}</td></tr>
  </table>

  <table style="width:100%;border-collapse:collapse;margin:18px 0;font-size:14px">
    <thead>
      <tr style="background:#DEF9EC">
        <th align="right" style="padding:8px">المنتج</th>
        <th align="center" style="padding:8px">الكمية</th>
        <th align="left" style="padding:8px">الإجمالي</th>
      </tr>
    </thead>
    <tbody>
      {% for item in items %}
      <tr style="border-bottom:1px solid #ECECEC">
        <td style="padding:8px">{{ item.item_name }}</td>
        <td align="center" style="padding:8px">{{ item.qty }}</td>
        <td align="left" style="padding:8px">{{ item.amount }}</td>
      </tr>
      {% endfor %}
    </tbody>
    <tfoot>
      <tr><td colspan="2" style="padding:10px 8px"><b>الإجمالي</b></td>
          <td align="left" style="padding:10px 8px"><b style="color:#21504C;font-size:16px">{{ grand_total }}</b></td></tr>
    </tfoot>
  </table>

  <p style="font-size:14px">تقدر تتابع طلبك من <a href="{{ track_url }}" style="color:#21504C">صفحة تتبّع الطلب</a> برقم الطلب والبريد ده.</p>
  <p style="font-size:13px;color:#7E7E7E;margin-top:24px">{{ store_name }}</p>
</div>"""

SHIPPED_HTML = """<div dir="rtl" style="font-family:Tahoma,Arial,sans-serif;max-width:560px;margin:auto;color:#253D4E">
  <h2 style="color:#21504C;margin:0 0 6px">طلبك في الطريق</h2>
  <p style="margin:0 0 18px;color:#5B6A72">{{ customer_name }}، طلبك رقم <b>{{ order_id }}</b> اتشحن.</p>

  {% if tracking_number %}
  <p style="background:#DEF9EC;padding:14px;border-radius:10px;font-size:15px">
    رقم الشحنة: <b>{{ tracking_number }}</b>
  </p>
  {% endif %}

  <table style="width:100%;border-collapse:collapse;font-size:14px;margin:14px 0">
    {% for item in items %}
    <tr style="border-bottom:1px solid #ECECEC">
      <td style="padding:8px">{{ item.item_name }}</td>
      <td align="center" style="padding:8px">×{{ item.qty }}</td>
    </tr>
    {% endfor %}
  </table>

  <p style="font-size:14px">تقدر تتابع الحالة من <a href="{{ track_url }}" style="color:#21504C">صفحة تتبّع الطلب</a>.</p>
  <p style="font-size:13px;color:#7E7E7E;margin-top:24px">{{ store_name }}</p>
</div>"""

TEMPLATES = [
	("Webshop Order Confirmation", "تأكيد طلبك رقم {{ order_id }} — {{ store_name }}", CONFIRMATION_HTML),
	("Webshop Order Shipped", "طلبك رقم {{ order_id }} في الطريق — {{ store_name }}", SHIPPED_HTML),
]


def execute():
	create_custom_fields(TOGGLES, ignore_validate=True)

	for name, subject, html in TEMPLATES:
		if frappe.db.exists("Email Template", name):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Email Template",
				"name": name,
				"subject": subject,
				"use_html": 1,
				"response_html": html,
				"response": html,
			}
		)
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert()

	settings = frappe.get_single("Webshop Content Settings")
	changed = False
	for field in ("send_order_confirmation", "send_shipping_notification"):
		# A Custom Field default only applies to new documents. Content Settings
		# already existed, so the flag arrives as 0 and has to be set here.
		if hasattr(settings, field) and not settings.get(field):
			settings.set(field, 1)
			changed = True
	if changed:
		settings.flags.ignore_permissions = True
		settings.flags.ignore_mandatory = True
		settings.save()

	frappe.db.commit()
	print("EMAIL TEMPLATES READY")
