# -*- coding: utf-8 -*-
"""Customer segmentation fields and the report that shows them."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

RFM_FIELDS = {
	"Customer": [
		{
			"fieldname": "rfm_section",
			"label": "تقسيم العملاء / Customer Segment",
			"fieldtype": "Section Break",
			"insert_after": "customer_group",
			"collapsible": 1,
		},
		{
			"fieldname": "rfm_segment",
			"label": "الشريحة / Segment",
			"fieldtype": "Data",
			"read_only": 1,
			"in_standard_filter": 1,
			"insert_after": "rfm_section",
			"description": "محسوبة من تاريخ الشراء. تتحدّث كل ليلة.",
		},
		{
			"fieldname": "rfm_score",
			"label": "درجة RFM",
			"fieldtype": "Data",
			"read_only": 1,
			"insert_after": "rfm_segment",
			"description": "ثلاث أرقام: حداثة الشراء / عدد الطلبات / إجمالي الإنفاق — كل واحد من 1 لـ 5.",
		},
		{
			"fieldname": "rfm_last_order",
			"label": "آخر طلب",
			"fieldtype": "Date",
			"read_only": 1,
			"insert_after": "rfm_score",
		},
		{"fieldname": "rfm_cb", "fieldtype": "Column Break", "insert_after": "rfm_last_order"},
		{
			"fieldname": "rfm_recency_days",
			"label": "أيام من آخر طلب",
			"fieldtype": "Int",
			"read_only": 1,
			"insert_after": "rfm_cb",
		},
		{
			"fieldname": "rfm_frequency",
			"label": "عدد الطلبات",
			"fieldtype": "Int",
			"read_only": 1,
			"insert_after": "rfm_recency_days",
		},
		{
			"fieldname": "rfm_monetary",
			"label": "إجمالي الشراء",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "rfm_frequency",
		},
		{
			"fieldname": "rfm_updated_on",
			"label": "آخر تحديث للتقسيم",
			"fieldtype": "Date",
			"read_only": 1,
			"insert_after": "rfm_monetary",
		},
	],
}

REPORT_NAME = "تقسيم العملاء"
REPORT_QUERY = """
SELECT
    c.name                AS "العميل:Link/Customer:220",
    c.rfm_segment         AS "الشريحة::130",
    c.rfm_score           AS "الدرجة::70",
    c.rfm_frequency       AS "عدد الطلبات:Int:100",
    c.rfm_monetary        AS "إجمالي الشراء:Currency:140",
    c.rfm_recency_days    AS "أيام من آخر طلب:Int:130",
    c.rfm_last_order      AS "آخر طلب:Date:110",
    c.customer_group      AS "المجموعة::140"
FROM `tabCustomer` c
WHERE IFNULL(c.rfm_segment, '') != ''
ORDER BY c.rfm_monetary DESC
"""


def execute():
	create_custom_fields(RFM_FIELDS, ignore_validate=True)

	if not frappe.db.exists("Report", REPORT_NAME):
		report = frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": REPORT_NAME,
				"ref_doctype": "Customer",
				"report_type": "Query Report",
				"is_standard": "No",
				"module": "Sync Webshop",
				"query": REPORT_QUERY,
				"disabled": 0,
			}
		)
		report.flags.ignore_permissions = True
		report.flags.ignore_mandatory = True
		report.insert()
		print("REPORT CREATED")

	frappe.db.commit()
	print("RFM FIELDS READY")
