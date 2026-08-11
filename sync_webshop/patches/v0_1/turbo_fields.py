# -*- coding: utf-8 -*-
"""
شحنة تربو — the Turbo panel on the Sales Order.

Everything Turbo reports back gets a home on the order itself, so the shipping
desk reads one screen instead of logging into a second system to answer "where
is it". The fields are read-only: they mirror what Turbo says, and letting
someone type over them would produce an ERP that disagrees with the courier.

The area alias table lives here too. Our territory tree and Turbo's list agree
on 3,914 of 3,942 areas; the rest are the same place written differently
("المنصورة" vs "مركز المنصورة"). Without the aliases those orders come back as
"Location is uncovered" and the customer never learns why.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# Ours → Turbo's spelling. Only where both clearly mean the same place.
AREA_ALIASES = {
	("أسيوط", "ساحل سليم"): "مركز ساحل سليم",
	("البحيرة", "بدر"): "مركز بدر",
	("البحيرة", "شبراخيت"): "مركز شبراخيت",
	("الدقهلية", "البيضا"): "البيضا الدقهلية",
	("الدقهلية", "السعودية"): "السعودية الدقهلية",
	("الدقهلية", "الصفا"): "الصفا الدقهلية",
	("الدقهلية", "المنصورة"): "مركز المنصورة",
	("الدقهلية", "ام السعود"): "ام السعود الدقهلية",
	("الدقهلية", "تاج العز"): "تاج العز الدقهلية",
	("الدقهلية", "صدقا"): "صدقا الدقهلية",
	("الدقهلية", "ظفر"): "ظفر الدقهلية",
	("الدقهلية", "كفر الاميرية"): "كفر الاميرية دقهلية",
	("الدقهلية", "كفر سنجاب"): "كفر سنجاب الدقهلية",
	("الغربية", "المحلة الكبرى"): "المحلة",
	("القليوبية", "قليوب"): "قليوب البلد",
	("المنيا", "سمالوط"): "مركز سمالوط",
}

FIELDS = {
	"Sales Order": [
		{
			"fieldname": "sec_turbo",
			"label": "شحنة تربو",
			"fieldtype": "Section Break",
			"insert_after": "webshop_phone_alt",
			"collapsible": 0,
			"depends_on": "eval:doc.docstatus==1",
			"description": "بيتحدّث من تربو تلقائيًا. مش محتاج تفتح لوحة تربو.",
		},
		{
			"fieldname": "turbo_order_number",
			"label": "رقم البوليصة",
			"fieldtype": "Data",
			"insert_after": "sec_turbo",
			"read_only": 1,
			"bold": 1,
			"in_list_view": 1,
			"translatable": 0,
		},
		{
			"fieldname": "turbo_status_text",
			"label": "حالة الشحنة",
			"fieldtype": "Data",
			"insert_after": "turbo_order_number",
			"read_only": 1,
			"bold": 1,
			"translatable": 0,
		},
		{
			"fieldname": "turbo_delivery_date",
			"label": "تاريخ التوصيل",
			"fieldtype": "Date",
			"insert_after": "turbo_status_text",
			"read_only": 1,
		},
		{
			"fieldname": "turbo_last_sync",
			"label": "آخر تحديث من تربو",
			"fieldtype": "Datetime",
			"insert_after": "turbo_delivery_date",
			"read_only": 1,
			"description": "لو التاريخ ده قديم، يبقى تربو مبعتش تحديث.",
		},
		{"fieldname": "turbo_cb1", "fieldtype": "Column Break", "insert_after": "turbo_last_sync"},
		{
			"fieldname": "turbo_captain_name",
			"label": "اسم المندوب",
			"fieldtype": "Data",
			"insert_after": "turbo_cb1",
			"read_only": 1,
			"translatable": 0,
		},
		{
			"fieldname": "turbo_captain_phone",
			"label": "موبايل المندوب",
			"fieldtype": "Data",
			"insert_after": "turbo_captain_name",
			"read_only": 1,
			"translatable": 0,
		},
		{
			"fieldname": "turbo_branch",
			"label": "الفرع",
			"fieldtype": "Data",
			"insert_after": "turbo_captain_phone",
			"read_only": 1,
			"translatable": 0,
		},
		{
			"fieldname": "turbo_status_code",
			"label": "كود الحالة",
			"fieldtype": "Int",
			"insert_after": "turbo_branch",
			"read_only": 1,
			"hidden": 1,
		},
		{
			"fieldname": "sec_turbo_issue",
			"label": "",
			"fieldtype": "Section Break",
			"insert_after": "turbo_status_code",
			# Only surfaces when something actually went wrong.
			"depends_on": "eval:doc.turbo_delay_reason || doc.turbo_return_reason || doc.turbo_error",
		},
		{
			"fieldname": "turbo_delay_reason",
			"label": "سبب التأخير",
			"fieldtype": "Small Text",
			"insert_after": "sec_turbo_issue",
			"read_only": 1,
			"translatable": 0,
		},
		{
			"fieldname": "turbo_return_reason",
			"label": "سبب الإرجاع",
			"fieldtype": "Small Text",
			"insert_after": "turbo_delay_reason",
			"read_only": 1,
			"translatable": 0,
		},
		{
			"fieldname": "turbo_error",
			"label": "رسالة خطأ من تربو",
			"fieldtype": "Small Text",
			"insert_after": "turbo_return_reason",
			"read_only": 1,
			"translatable": 0,
			"description": "مثال: Location is uncovered — يعني المنطقة مش في تغطية تربو.",
		},
	],
}


def execute():
	create_custom_fields(FIELDS, ignore_validate=True)

	# Store the alias table where the sync code and the owner can both reach it.
	frappe.db.set_default("turbo_area_aliases", frappe.as_json(
		{"%s|%s" % k: v for k, v in AREA_ALIASES.items()}))

	frappe.db.commit()
	frappe.clear_cache()
	print("TURBO FIELDS READY — %d aliases stored" % len(AREA_ALIASES))
