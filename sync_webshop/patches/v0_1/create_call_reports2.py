# -*- coding: utf-8 -*-
"""تقارير المكالمات المتقدمة — الأسبوعي، سرعة الرد، الدناجل، والربط بالمبيعات."""
import frappe

REPORTS = [
	{
		"name": "مقارنة المكالمات أسبوعيًا",
		"query": """
			select
				yearweek(cl.start_time, 3)                          as "الأسبوع:Data:110",
				min(date(cl.start_time))                            as "من يوم:Date:110",
				count(*)                                            as "إجمالي المكالمات:Int:140",
				sum(case when cl.status = 'Completed' then 1 else 0 end) as "ردّينا:Int:100",
				sum(case when cl.status in ('No Answer','Missed') then 1 else 0 end) as "ضاعت:Int:90",
				round(100 * sum(case when cl.status in ('No Answer','Missed') then 1 else 0 end) / count(*)) as "نسبة الضياع:Int:120",
				round(sum(cl.duration)/60)                          as "دقايق الكلام:Int:120",
				count(distinct cl.`from`)                           as "أرقام مختلفة:Int:120"
			from `tabCall Log` cl
			where cl.medium = 'Issabel'
			group by yearweek(cl.start_time, 3)
			order by yearweek(cl.start_time, 3) desc
		""",
	},
	{
		"name": "سرعة الرد على المكالمات",
		"query": """
			select
				coalesce(cl.call_received_by, '(مش محدد)')          as "الموظف:Data:200",
				cl.summary                                          as "التحويلة:Data:120",
				count(*)                                            as "مكالمات:Int:100",
				round(avg(timestampdiff(second, cl.creation, cl.modified))) as "متوسط ثواني للرد:Int:150",
				max(timestampdiff(second, cl.creation, cl.modified))        as "أطول انتظار:Int:120",
				sum(case when timestampdiff(second, cl.creation, cl.modified) > 20 then 1 else 0 end) as "استنى أكتر من 20 ثانية:Int:180"
			from `tabCall Log` cl
			where cl.medium = 'Issabel'
			  and cl.status = 'Completed'
			  and cl.modified > cl.creation
			group by cl.call_received_by, cl.summary
			order by count(*) desc
		""",
	},
	{
		"name": "مكالمات كل خط (دنجل)",
		"query": """
			select
				coalesce(nullif(cl.custom_trunk,''), '(مش مسجّل)')  as "الخط:Data:130",
				count(*)                                            as "إجمالي المكالمات:Int:140",
				sum(case when cl.status = 'Completed' then 1 else 0 end) as "ردّينا:Int:100",
				sum(case when cl.status in ('No Answer','Missed') then 1 else 0 end) as "ضاعت:Int:90",
				round(sum(cl.duration)/60)                          as "دقايق:Int:90",
				count(distinct cl.`from`)                           as "أرقام مختلفة:Int:120",
				max(cl.start_time)                                  as "آخر مكالمة:Datetime:150"
			from `tabCall Log` cl
			where cl.medium = 'Issabel'
			group by cl.custom_trunk
			order by count(*) desc
		""",
	},
	{
		"name": "مكالمات أدّت لمبيعات",
		"query": """
			select
				cl.customer                                         as "العميل:Link/Customer:200",
				count(distinct cl.name)                             as "مكالمات:Int:100",
				max(cl.start_time)                                  as "آخر مكالمة:Datetime:150",
				count(distinct so.name)                             as "أوامر بيع بعدها:Int:150",
				round(sum(distinct so.grand_total))                 as "قيمة المبيعات:Currency:150",
				max(so.transaction_date)                            as "آخر أمر بيع:Date:130"
			from `tabCall Log` cl
			left join `tabSales Order` so
				on so.customer = cl.customer
			   and so.docstatus = 1
			   and so.creation >= cl.start_time
			   and so.creation <= date_add(cl.start_time, interval 7 day)
			where cl.medium = 'Issabel'
			  and ifnull(cl.customer,'') != ''
			group by cl.customer
			having count(distinct so.name) > 0
			order by count(distinct so.name) desc
		""",
	},
]


def execute():
	made = []
	for spec in REPORTS:
		name = spec["name"]
		doc = frappe.get_doc("Report", name) if frappe.db.exists("Report", name) else frappe.new_doc("Report")
		doc.name = name
		doc.report_name = name
		doc.ref_doctype = "Call Log"
		doc.report_type = "Query Report"
		doc.module = "Sync Webshop"
		doc.is_standard = "No"
		doc.disabled = 0
		doc.query = spec["query"].strip()
		doc.roles = []
		for role in ("System Manager", "Sales Manager", "Sales User"):
			if frappe.db.exists("Role", role):
				doc.append("roles", {"role": role})
		doc.flags.ignore_permissions = True
		doc.save()
		made.append(name)
	frappe.db.commit()
	frappe.clear_cache()
	return made
