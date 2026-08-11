# -*- coding: utf-8 -*-
"""
مساحة عمل تربو — one page for everything the courier touches.

The shipping desk was bouncing between the ERP and Turbo's panel to answer
simple questions: what is waiting to go out, what is on the road, what came
back, and how much money is sitting with the courier. All of that already lives
in the sales orders once the integration writes it, so it belongs on one screen
here.
"""
import frappe

MONEY_SQL = """
SELECT
    so.turbo_status_text                                   AS status,
    COUNT(*)                                               AS orders,
    ROUND(SUM(so.grand_total), 0)                          AS amount
FROM `tabSales Order` so
WHERE so.docstatus = 1
  AND IFNULL(so.turbo_order_number, '') != ''
GROUP BY so.turbo_status_text
ORDER BY amount DESC
"""

MONEY_COLUMNS = [
	{"label": "حالة الشحنة", "fieldname": "status", "fieldtype": "Data", "width": 220},
	{"label": "عدد الشحنات", "fieldname": "orders", "fieldtype": "Int", "width": 120},
	{"label": "المبلغ", "fieldname": "amount", "fieldtype": "Currency", "width": 160},
]

PENDING_SQL = """
SELECT
    so.name                                AS "أمر البيع:Link/Sales Order:170",
    so.customer_name                       AS "العميل::200",
    so.custom_preparation_status           AS "تحرك الطلبات::170",
    so.custom_operation_status             AS "حركة المخزن::200",
    so.grand_total                         AS "التحصيل:Currency:120",
    so.transaction_date                    AS "تاريخ الطلب:Date:110",
    DATEDIFF(CURDATE(), so.transaction_date) AS "عدد الأيام:Int:100"
FROM `tabSales Order` so
WHERE so.docstatus = 1
  AND IFNULL(so.turbo_order_number, '') = ''
  AND so.status NOT IN ('Closed', 'Completed')
ORDER BY so.transaction_date ASC
"""

ONROAD_SQL = """
SELECT
    so.name                     AS "أمر البيع:Link/Sales Order:170",
    so.turbo_order_number       AS "رقم البوليصة::130",
    so.turbo_status_text        AS "الحالة::160",
    so.customer_name            AS "العميل::200",
    so.grand_total              AS "التحصيل:Currency:120",
    so.turbo_captain_name       AS "المندوب::140",
    so.turbo_captain_phone      AS "موبايل المندوب::130",
    so.turbo_delivery_date      AS "تاريخ التوصيل:Date:110",
    so.turbo_last_sync          AS "آخر تحديث:Datetime:150"
FROM `tabSales Order` so
WHERE so.docstatus = 1
  AND IFNULL(so.turbo_order_number, '') != ''
ORDER BY so.turbo_last_sync DESC
"""

PROBLEM_SQL = """
SELECT
    so.name                  AS "أمر البيع:Link/Sales Order:170",
    so.turbo_order_number    AS "رقم البوليصة::130",
    so.turbo_status_text     AS "الحالة::150",
    so.customer_name         AS "العميل::180",
    so.turbo_delay_reason    AS "سبب التأخير::220",
    so.turbo_return_reason   AS "سبب الإرجاع::220",
    so.turbo_error           AS "رسالة الخطأ::220"
FROM `tabSales Order` so
WHERE so.docstatus = 1
  AND (IFNULL(so.turbo_delay_reason,'') != ''
    OR IFNULL(so.turbo_return_reason,'') != ''
    OR IFNULL(so.turbo_error,'') != '')
ORDER BY so.modified DESC
"""

REPORTS = [
	("تربو — في انتظار الشحن", PENDING_SQL, None),
	("تربو — شحنات على الطريق", ONROAD_SQL, None),
	("تربو — شحنات فيها مشكلة", PROBLEM_SQL, None),
	("تربو — الفلوس عند الشركة", MONEY_SQL, MONEY_COLUMNS),
]


def make_report(name, query, columns):
	if frappe.db.exists("Report", name):
		doc = frappe.get_doc("Report", name)
	else:
		doc = frappe.new_doc("Report")
		doc.report_name = name
		doc.ref_doctype = "Sales Order"
		doc.report_type = "Query Report"
		doc.module = "Sync Webshop"
		doc.is_standard = "No"
		doc.append("roles", {"role": "System Manager"})
		doc.append("roles", {"role": "Sales Manager"})
	doc.query = query
	doc.json = frappe.as_json({"columns": columns}) if columns else "{}"
	doc.disabled = 0
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.name


def execute():
	made = [make_report(n, q, c) for n, q, c in REPORTS]

	name = "تربو"
	if frappe.db.exists("Workspace", name):
		ws = frappe.get_doc("Workspace", name)
		ws.shortcuts = []
		ws.links = []
	else:
		ws = frappe.new_doc("Workspace")
		ws.name = name
		ws.title = name
		ws.label = name

	ws.module = "Sync Webshop"
	ws.icon = "delivery"
	ws.public = 1
	ws.is_hidden = 0
	ws.parent_page = ""
	ws.content = frappe.as_json([
		{"id": "hdr", "type": "header",
		 "data": {"text": "<span class='h4'>شحنات تربو</span>", "col": 12}},
		{"id": "sc", "type": "card", "data": {"card_name": "الشاشات", "col": 4}},
		{"id": "st", "type": "card", "data": {"card_name": "الإعدادات", "col": 4}},
	])

	for label, link_to, link_type in [
		("في انتظار الشحن", "تربو — في انتظار الشحن", "Report"),
		("شحنات على الطريق", "تربو — شحنات على الطريق", "Report"),
		("شحنات فيها مشكلة", "تربو — شحنات فيها مشكلة", "Report"),
		("الفلوس عند الشركة", "تربو — الفلوس عند الشركة", "Report"),
	]:
		ws.append("shortcuts", {
			"label": label, "link_to": link_to, "type": link_type,
			"doc_view": "Report Builder" if link_type == "DocType" else "",
		})

	ws.append("shortcuts", {
		"label": "إعدادات تربو", "link_to": "Webshop Turbo Settings", "type": "DocType"})
	ws.append("shortcuts", {
		"label": "كل أوامر البيع", "link_to": "Sales Order", "type": "DocType"})

	ws.flags.ignore_permissions = True
	ws.flags.ignore_mandatory = True
	ws.save()

	frappe.db.commit()
	frappe.clear_cache()
	print("WORKSPACE READY")
	for m in made:
		print("  •", m)
