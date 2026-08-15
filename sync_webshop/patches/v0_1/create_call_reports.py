# -*- coding: utf-8 -*-
"""
تقارير المكالمات في ERPNext — نفس اللي بتوفره تقارير Issabel وزيادة.

Issabel عنده cdrreport و billing_report و graphic_report، لكن قراءتها بتتم
من واجهته المنفصلة. هنا التقارير جوه ERPNext على نفس بيانات `Call Log`،
فالمكالمة مربوطة بالعميل وأوامر بيعه — وده اللي واجهة السنترال مبتعرفوش.
"""
import frappe

REPORTS = [
	{
		"name": "سجل المكالمات",
		"description": "كل مكالمة: مين اتصل، على مين، مدتها، ونتيجتها",
		"query": """
			select
				cl.start_time            as "الوقت:Datetime:150",
				cl.`from`                as "من:Data:120",
				cl.`to`                  as "إلى:Data:120",
				cl.type                  as "النوع:Data:80",
				cl.status                as "النتيجة:Data:100",
				round(cl.duration)       as "المدة (ثانية):Int:100",
				cl.customer              as "العميل:Link/Customer:180",
				cl.call_received_by      as "الموظف:Link/Employee:160",
				cl.summary               as "التحويلة:Data:110"
			from `tabCall Log` cl
			where cl.medium = 'Issabel'
			order by cl.start_time desc
		""",
	},
	{
		"name": "مكالمات الموظفين",
		"description": "مين رد على كام مكالمة وكام دقيقة اتكلم",
		"query": """
			select
				coalesce(cl.call_received_by, '(مش محدد)') as "الموظف:Data:200",
				cl.summary                                  as "التحويلة:Data:120",
				count(*)                                    as "إجمالي المكالمات:Int:130",
				sum(case when cl.status = 'Completed' then 1 else 0 end) as "ردّ عليها:Int:110",
				sum(case when cl.status in ('No Answer','Missed') then 1 else 0 end) as "فاتته:Int:100",
				round(sum(cl.duration)/60)                  as "دقايق الكلام:Int:120",
				round(avg(nullif(cl.duration,0)))           as "متوسط المكالمة (ثانية):Int:160"
			from `tabCall Log` cl
			where cl.medium = 'Issabel'
			group by cl.call_received_by, cl.summary
			order by count(*) desc
		""",
	},
	{
		"name": "أوقات ذروة المكالمات",
		"description": "المكالمات موزعة على ساعات اليوم — يحدد وقت تواجد الفريق",
		"query": """
			select
				hour(cl.start_time)      as "الساعة:Int:80",
				count(*)                 as "عدد المكالمات:Int:130",
				sum(case when cl.status = 'Completed' then 1 else 0 end) as "ردّ عليها:Int:110",
				sum(case when cl.status in ('No Answer','Missed') then 1 else 0 end) as "ضاعت:Int:100",
				round(100 * sum(case when cl.status in ('No Answer','Missed') then 1 else 0 end) / count(*)) as "نسبة الضياع:Int:130"
			from `tabCall Log` cl
			where cl.medium = 'Issabel'
			group by hour(cl.start_time)
			order by hour(cl.start_time)
		""",
	},
	{
		"name": "أرقام اتصلت وليست عملاء",
		"description": "فرص ضايعة — أرقام دوّرت عليك ومش مسجّلة عندك",
		"query": """
			select
				cl.`from`                as "الرقم:Data:140",
				count(*)                 as "اتصل كام مرة:Int:130",
				max(cl.start_time)       as "آخر اتصال:Datetime:150",
				sum(case when cl.status = 'Completed' then 1 else 0 end) as "ردّينا عليه:Int:120",
				sum(case when cl.status in ('No Answer','Missed') then 1 else 0 end) as "ضاع:Int:90",
				round(sum(cl.duration))  as "إجمالي الثواني:Int:130"
			from `tabCall Log` cl
			where cl.medium = 'Issabel'
			  and ifnull(cl.customer,'') = ''
			  and cl.type = 'Incoming'
			  and length(cl.`from`) >= 10
			group by cl.`from`
			order by count(*) desc, max(cl.start_time) desc
		""",
	},
	{
		"name": "مكالمات ضاعت ومحدش رجّعها",
		"description": "مكالمات فايتة والرقم ما اتصلش تاني ولا اتردّ عليه بعدها",
		"query": """
			select
				cl.`from`                as "الرقم:Data:140",
				cl.customer              as "العميل:Link/Customer:180",
				max(cl.start_time)       as "آخر محاولة:Datetime:150",
				count(*)                 as "حاول كام مرة:Int:130",
				cl.summary               as "رنّ على:Data:120"
			from `tabCall Log` cl
			where cl.medium = 'Issabel'
			  and cl.type = 'Incoming'
			  and cl.status in ('No Answer','Missed')
			  and not exists (
					select 1 from `tabCall Log` c2
					where c2.`from` = cl.`from`
					  and c2.status = 'Completed'
					  and c2.start_time > cl.start_time
			  )
			group by cl.`from`, cl.customer, cl.summary
			order by max(cl.start_time) desc
		""",
	},
	{
		"name": "مكالمات العملاء",
		"description": "كل عميل: اتصل كام مرة وآخر مرة إمتى",
		"query": """
			select
				cl.customer              as "العميل:Link/Customer:200",
				count(*)                 as "عدد المكالمات:Int:130",
				max(cl.start_time)       as "آخر مكالمة:Datetime:150",
				round(sum(cl.duration)/60) as "إجمالي الدقايق:Int:130",
				sum(case when cl.type = 'Incoming' then 1 else 0 end) as "اتصل بينا:Int:110",
				sum(case when cl.type = 'Outgoing' then 1 else 0 end) as "اتصلنا بيه:Int:110"
			from `tabCall Log` cl
			where cl.medium = 'Issabel' and ifnull(cl.customer,'') != ''
			group by cl.customer
			order by count(*) desc
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
	print("التقارير:", len(made))
	for m in made:
		print("   •", m)
	return made
