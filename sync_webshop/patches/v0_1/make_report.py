# -*- coding: utf-8 -*-
"""
تحليلات المتجر — a shop report that lives in the Desk.

Google Analytics answers "who visited"; it cannot answer "what did they buy",
because that lives here. This report reads the sales orders directly, so the
owner opens one page in ERPNext and sees the months side by side, no export and
no second login.

Scoped to orders containing website products — the ERP carries other business
under the same company, and mixing them would make every figure wrong.
"""
import frappe

SQL = """
SELECT
    DATE_FORMAT(o.transaction_date, '%%Y-%%m')                        AS month,
    COUNT(DISTINCT o.name)                                           AS orders,
    ROUND(SUM(o.line_total), 0)                                      AS revenue,
    COUNT(DISTINCT o.customer)                                       AS customers,
    ROUND(SUM(o.line_total) / NULLIF(COUNT(DISTINCT o.name), 0), 0)  AS avg_order,
    ROUND(SUM(o.qty), 0)                                             AS packs
FROM (
    SELECT so.name, so.customer, so.transaction_date,
           SUM(soi.amount) AS line_total, SUM(soi.qty) AS qty
    FROM `tabSales Order` so
    JOIN `tabSales Order Item` soi ON soi.parent = so.name
    JOIN `tabItem` i ON i.name = soi.item_code
    JOIN `tabItem Group` g ON g.name = i.item_group AND g.show_in_website = 1
    WHERE so.docstatus = 1
    GROUP BY so.name, so.customer, so.transaction_date
) o
GROUP BY month
ORDER BY month DESC
"""

COLUMNS = [
	{"label": "الشهر", "fieldname": "month", "fieldtype": "Data", "width": 100},
	{"label": "عدد الطلبات", "fieldname": "orders", "fieldtype": "Int", "width": 110},
	{"label": "المبيعات", "fieldname": "revenue", "fieldtype": "Currency", "width": 140},
	{"label": "عملاء اشتروا", "fieldname": "customers", "fieldtype": "Int", "width": 120},
	{"label": "متوسط الطلب", "fieldname": "avg_order", "fieldtype": "Currency", "width": 130},
	{"label": "عبوات اتباعت", "fieldname": "packs", "fieldtype": "Int", "width": 120},
]

TOP_SQL = """
SELECT
    i.item_name                        AS product,
    COUNT(DISTINCT so.name)            AS orders,
    ROUND(SUM(soi.qty), 0)             AS qty,
    ROUND(SUM(soi.amount), 0)          AS revenue
FROM `tabSales Order Item` soi
JOIN `tabSales Order` so ON so.name = soi.parent AND so.docstatus = 1
JOIN `tabItem` i ON i.name = soi.item_code
JOIN `tabItem Group` g ON g.name = i.item_group AND g.show_in_website = 1
GROUP BY i.name, i.item_name
ORDER BY revenue DESC
LIMIT 50
"""

TOP_COLUMNS = [
	{"label": "المنتج", "fieldname": "product", "fieldtype": "Data", "width": 320},
	{"label": "عدد الطلبات", "fieldname": "orders", "fieldtype": "Int", "width": 110},
	{"label": "الكمية", "fieldname": "qty", "fieldtype": "Int", "width": 100},
	{"label": "المبيعات", "fieldname": "revenue", "fieldtype": "Currency", "width": 140},
]


def make(name, query, columns):
	if frappe.db.exists("Report", name):
		doc = frappe.get_doc("Report", name)
		doc.query = query
		doc.json = frappe.as_json({"columns": columns})
		doc.flags.ignore_permissions = True
		doc.save()
		print("  updated: " + name)
		return
	doc = frappe.get_doc({
		"doctype": "Report",
		"report_name": name,
		"ref_doctype": "Sales Order",
		"report_type": "Query Report",
		"module": "Sync Webshop",
		"is_standard": "No",
		"disabled": 0,
		"query": query,
		"json": frappe.as_json({"columns": columns}),
		"roles": [{"role": "System Manager"}, {"role": "Sales Manager"}],
	})
	doc.flags.ignore_permissions = True
	doc.insert()
	print("  created: " + name)


def execute():
	make("تحليلات المتجر — شهريًا", SQL, COLUMNS)
	make("تحليلات المتجر — أكثر المنتجات مبيعًا", TOP_SQL, TOP_COLUMNS)
	frappe.db.commit()
	frappe.clear_cache()
	print("REPORTS READY")
