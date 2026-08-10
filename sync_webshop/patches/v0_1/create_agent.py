# -*- coding: utf-8 -*-
"""
The ERP assistant.

Three documents, all editable in the Desk:

  Webshop Agent Skill    — one thing the assistant can do, and the words that
                           ask for it. This is where the agent is "trained".
  Webshop Agent Settings — switch, greeting, whether writing is allowed at all.
  Webshop Agent Log      — every question, who asked, what ran, what came back.

The assistant runs as whoever is logged in. Every lookup goes through Frappe's
own permission checks, so a salesperson sees exactly what they would see in the
Desk and nothing more. Writing is off until it is switched on deliberately.
"""
import frappe


def _f(fieldname, label, fieldtype, **kw):
	return {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, **kw}


# Each action is a named, reviewed function — the assistant never builds a query
# from what the user typed.
ACTIONS = (
	"sales_today\nsales_month\nopen_orders\norder_status\ncustomer_orders\n"
	"item_stock\nitem_price\nlow_stock\ntop_customers\nat_risk_customers\n"
	"webshop_orders\nhelp"
)

AGENT_SKILL = {
	"name": "Webshop Agent Skill",
	"autoname": "field:skill_name",
	"title_field": "skill_name",
	"fields": [
		_f("skill_name", "اسم المهارة", "Data", reqd=1, in_list_view=1),
		_f("enabled", "مفعّلة", "Check", default="1", in_list_view=1),
		_f("cb1", "", "Column Break"),
		_f("action", "اللي بتعمله", "Select", options=ACTIONS, reqd=1, in_list_view=1,
		   description="الإجراءات دي مكتوبة ومراجعة في الكود. المساعد ما بيبنيش استعلام من كلام المستخدم."),
		_f("sec_kw", "كلمات التطابق", "Section Break",
		   description="لو المستخدم كتب أي كلمة من دول، المهارة دي هي اللي تشتغل."),
		_f("keywords_ar", "كلمات عربية", "Small Text", reqd=1),
		_f("keywords_en", "English words", "Small Text"),
		_f("sec_help", "", "Section Break"),
		_f("example_question", "مثال لسؤال", "Data",
		   description="بيظهر للمستخدم في قائمة «أقدر أعمل إيه»."),
		_f("times_used", "عدد مرات الاستخدام", "Int", read_only=1),
	],
}

AGENT_SETTINGS = {
	"name": "Webshop Agent Settings",
	"issingle": 1,
	"fields": [
		_f("enabled", "المساعد شغّال", "Check", default="0"),
		_f("cb1", "", "Column Break"),
		_f("agent_name", "اسم المساعد", "Data", default="مساعد دبونو"),
		_f("sec_msgs", "الرسائل", "Section Break"),
		_f("greeting", "رسالة الترحيب", "Small Text",
		   default="أهلاً. اسألني عن المبيعات أو الطلبات أو المخزون — بشوف اللي مسموحلك تشوفه بس."),
		_f("fallback", "لو مفهمش السؤال", "Small Text",
		   default="مش فاهم السؤال ده. اكتب «مساعدة» تشوف اللي أقدر أعمله."),
		_f("sec_write", "الكتابة والتنفيذ", "Section Break",
		   description="التنفيذ مقفول افتراضيًا. المساعد بيقرا بس."),
		_f("allow_write", "اسمح للمساعد بالتنفيذ", "Check", default="0",
		   description="لسه مش مفعّل — كل إجراءات التنفيذ محتاجة بناء ومراجعة قبل ما تتفتح."),
		_f("require_confirmation", "اطلب تأكيد قبل أي تنفيذ", "Check", default="1"),
		_f("sec_log", "السجل", "Section Break"),
		_f("log_conversations", "سجّل كل المحادثات", "Check", default="1"),
	],
}

AGENT_LOG = {
	"name": "Webshop Agent Log",
	"autoname": "hash",
	"fields": [
		_f("asked_by", "المستخدم", "Link", options="User", read_only=1, in_list_view=1),
		_f("question", "السؤال", "Data", read_only=1, in_list_view=1),
		_f("skill", "المهارة", "Link", options="Webshop Agent Skill", read_only=1, in_list_view=1),
		_f("outcome", "النتيجة", "Select", options="نجح\nمفيش مهارة\nممنوع\nخطأ",
		   read_only=1, in_list_view=1),
		_f("channel", "المصدر", "Select", options="ERP\nTelegram", read_only=1, default="ERP"),
		_f("response", "الرد", "Small Text", read_only=1),
	],
}

PERMS_ADMIN = [
	{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
	{"role": "Sales Manager", "read": 1, "write": 1, "create": 1},
]
PERMS_LOG = PERMS_ADMIN + [{"role": "Sales User", "read": 1}]

SKILLS = [
	("مبيعات النهارده", "sales_today", "مبيعات النهارده, بيع النهارده, ايه مبيعات اليوم, مبيعات اليوم",
	 "sales today, today sales", "إيه مبيعات النهارده؟"),
	("مبيعات الشهر", "sales_month", "مبيعات الشهر, الشهر ده, مبيعات شهري",
	 "sales this month, monthly sales", "مبيعات الشهر كام؟"),
	("طلبات مفتوحة", "open_orders", "طلبات مفتوحة, لسه متسلمتش, تحت التنفيذ, طلبات جارية",
	 "open orders, pending orders", "فيه كام طلب مفتوح؟"),
	("حالة طلب", "order_status", "حالة الطلب, الطلب رقم, فين الطلب, طلب رقم",
	 "order status, where is order", "حالة الطلب SAL-ORD-2026-00001"),
	("طلبات عميل", "customer_orders", "طلبات العميل, عميل اسمه, طلبات عميل",
	 "customer orders, orders for", "طلبات العميل أحمد"),
	("رصيد صنف", "item_stock", "رصيد, المخزون, كام قطعة, متوفر كام",
	 "stock, how many left, inventory", "رصيد أكياس بن 500"),
	("سعر صنف", "item_price", "سعر, بكام, السعر بتاع",
	 "price of, how much is", "سعر أكياس بن 500"),
	("أصناف قربت تخلص", "low_stock", "قربت تخلص, رصيد قليل, ناقص مخزون, هيخلص",
	 "low stock, running out", "إيه الأصناف اللي قربت تخلص؟"),
	("أفضل العملاء", "top_customers", "أفضل العملاء, أكبر عملاء, الأبطال",
	 "top customers, best customers", "مين أفضل عملائي؟"),
	("عملاء بيضيعوا", "at_risk_customers", "عملاء بيضيعوا, عملاء بعدوا, مهمين وبيضيعوا, عملاء وقفوا",
	 "at risk customers, churn", "مين العملاء اللي بيضيعوا؟"),
	("طلبات المتجر", "webshop_orders", "طلبات الموقع, طلبات المتجر, أونلاين",
	 "webshop orders, online orders", "فيه طلبات من الموقع؟"),
	("مساعدة", "help", "مساعدة, ساعدني, بتعمل ايه, ايه اللي تقدر تعمله, الأوامر",
	 "help, what can you do, commands", "مساعدة"),
]


def _sync(spec, perms):
	if frappe.db.exists("DocType", spec["name"]):
		doc = frappe.get_doc("DocType", spec["name"])
		doc.fields = []
	else:
		doc = frappe.new_doc("DocType")
		doc.name = spec["name"]

	doc.module = "Sync Webshop"
	doc.custom = 0
	doc.engine = "InnoDB"
	doc.issingle = spec.get("issingle", 0)
	if spec.get("autoname"):
		doc.autoname = spec["autoname"]
	if spec.get("title_field"):
		doc.title_field = spec["title_field"]

	for idx, field in enumerate(spec["fields"], start=1):
		doc.append("fields", {**field, "idx": idx})

	doc.permissions = []
	for perm in perms:
		doc.append("permissions", perm)

	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.save()
	return doc.name


def execute():
	was_dev = frappe.conf.get("developer_mode")
	frappe.conf["developer_mode"] = 1
	try:
		names = [
			_sync(AGENT_SKILL, PERMS_ADMIN),
			_sync(AGENT_SETTINGS, PERMS_ADMIN),
			_sync(AGENT_LOG, PERMS_LOG),
		]
	finally:
		frappe.conf["developer_mode"] = was_dev or 0

	created = []
	for name, action, kw_ar, kw_en, example in SKILLS:
		if frappe.db.exists("Webshop Agent Skill", name):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Webshop Agent Skill",
				"skill_name": name,
				"action": action,
				"keywords_ar": kw_ar,
				"keywords_en": kw_en,
				"example_question": example,
				"enabled": 1,
			}
		)
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert()
		created.append(name)

	frappe.db.commit()
	frappe.clear_cache()
	print("AGENT=" + ", ".join(names) + " | skills=" + str(len(created)))
