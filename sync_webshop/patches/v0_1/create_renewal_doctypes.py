# -*- coding: utf-8 -*-
"""
حملة تجديد الاشتراكات: الإعدادات والنصوص والردود — كلها مستندات في ERPNext.

الأرقام (السعر، الحد اليومي، ساعات الإرسال) والنصوص بيكتبها المالك هنا،
والـ n8n بيقراها. تغيير سعر أو نص = تعديل مستند، من غير كود.
"""
import frappe


def _field(fieldname, label, fieldtype, **kw):
	f = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype}
	f.update(kw)
	return f


# ————— نص رسالة (قالب) —————
MESSAGE_TEMPLATE = {
	"name": "Renewal Message Template",
	"autoname": "hash",
	"title_field": "template_text",
	"fields": [
		_field("stage", "المرحلة / Stage", "Select", reqd=1, in_list_view=1,
		       options="\n".join(["قبل الانتهاء", "يوم الانتهاء", "بعد الانتهاء"]),
		       default="قبل الانتهاء"),
		_field("enabled", "شغّال", "Check", default="1", in_list_view=1),
		_field("cb1", "", "Column Break"),
		_field("times_used", "اتبعت كام مرة", "Int", read_only=1, in_list_view=1),
		_field("sec_text", "نص الرسالة", "Section Break",
		       description=("متاح تستخدم: {الاسم} {السيريال} {تاريخ_الانتهاء} {الأيام_المتبقية}\n"
		                    "متكتبش سطر الاختيارات (1 و 2) — بيتضاف تلقائيًا من الإعدادات.")),
		_field("template_text", "النص", "Text", reqd=1, in_list_view=1),
	],
}

# ————— إعدادات الحملة —————
CAMPAIGN_SETTINGS = {
	"name": "Renewal Campaign Settings",
	"issingle": 1,
	"fields": [
		_field("enabled", "الحملة شغّالة", "Check", default="0",
		       description="سيبها مقفولة لحد ما تجرب وتتطمن."),
		_field("cb0", "", "Column Break"),
		_field("instance_name", "رقم الواتساب المُرسِل", "Data", default="97",
		       description="اسم الـ instance في Evolution. الحالي: 97"),

		_field("sec_timing", "التوقيت / Timing", "Section Break",
		       description="الرسايل بتتبعت في ساعة مختلفة كل يوم عشان متبقاش نمط ثابت."),
		_field("send_hours", "ساعات الإرسال المسموحة", "Data", default="5,6,7",
		       description="أرقام الساعات مفصولة بفاصلة. كل يوم بيتختار واحدة منهم."),
		_field("cb1", "", "Column Break"),
		_field("skip_friday", "متبعتش يوم الجمعة", "Check", default="1"),

		_field("sec_safety", "حماية الرقم من الحظر / Anti-Ban", "Section Break",
		       description="أهم قسم. عندك أكتر من 1000 اشتراك — الإرسال المتسرّع بيتحظر."),
		_field("daily_limit", "أقصى عدد رسايل في اليوم", "Int", default="80",
		       description="ابدأ بـ 40-80 وزوّد بالراحة على مدى أسابيع. متعدّيش 200."),
		_field("min_delay_seconds", "أقل انتظار بين رسالتين (ثانية)", "Int", default="45"),
		_field("cb2", "", "Column Break"),
		_field("max_delay_seconds", "أكبر انتظار بين رسالتين (ثانية)", "Int", default="150"),
		_field("batch_pause_every", "استريح بعد كل كام رسالة", "Int", default="15"),
		_field("batch_pause_minutes", "مدة الاستراحة (دقيقة)", "Int", default="10"),

		_field("sec_choices", "سطر الاختيارات / Reply Options", "Section Break",
		       description="بيتضاف في آخر كل رسالة تجديد."),
		_field("choices_text", "نص الاختيارات", "Small Text",
		       default="ردّ بـ 1 للتجديد والاطلاع على الأسعار\nردّ بـ 2 لو مش عايز رسايل تانية"),

		_field("sec_prices", "الأسعار / Prices", "Section Break"),
		_field("price_yearly", "اشتراك سنة", "Currency", default="1040"),
		_field("price_lifetime", "اشتراك مدى الحياة", "Currency", default="2440"),
		_field("cb3", "", "Column Break"),
		_field("lifetime_until_year", "مدى الحياة لحد سنة", "Int", default="2099"),
		_field("prices_text", "نص رسالة الأسعار", "Text",
		       default=("أهلاً {الاسم} 🙏\n\n"
		                "أسعار تجديد الاشتراك:\n"
		                "▪️ سنة واحدة: {سعر_السنة} جنيه\n"
		                "▪️ مدى الحياة حتى {سنة_النهاية}: {سعر_مدى_الحياة} جنيه\n\n"
		                "ردّ بـ 1 عشان نبعتلك طرق الدفع\n"
		                "ردّ بـ 2 عشان يتصل بيك موظف خدمة العملاء"),
		       description="متاح: {الاسم} {سعر_السنة} {سعر_مدى_الحياة} {سنة_النهاية}"),

		_field("sec_payment", "طرق الدفع / Payment", "Section Break"),
		_field("payment_image", "صورة طرق الدفع", "Attach Image",
		       description="ارفع الصورة هنا وهي اللي هتتبعت للعميل لما يطلب طرق الدفع."),
		_field("cb4", "", "Column Break"),
		_field("payment_text", "نص طرق الدفع", "Text",
		       default=("طرق الدفع المتاحة 👇\n\n"
		                "بعد التحويل ابعتلنا صورة الإيصال وهنفعّل اشتراكك فورًا ✅"),
		       description="بيتبعت مع الصورة، أو لوحده لو مفيش صورة."),

		_field("sec_optout", "لو العميل رفض / Opt-out", "Section Break"),
		_field("optout_reply", "الرد على من يرفض", "Small Text",
		       default="تمام، مش هنبعتلك رسايل تانية عن التجديد. لو احتجتنا في أي وقت إحنا موجودين 🌹"),
		_field("cb5", "", "Column Break"),
		_field("support_reply", "الرد على طلب خدمة العملاء", "Small Text",
		       default="تمام 👍 حوّلت طلبك لخدمة العملاء، وحد من الفريق هيتصل بيك في أقرب وقت."),

		_field("sec_ticket", "تذكرة الموظف / Ticket", "Section Break"),
		_field("create_ticket", "اعمل تذكرة للموظف", "Check", default="1",
		       description="بتتعمل كـ ToDo على الموظف المسؤول."),
		_field("ticket_owner", "الموظف المسؤول", "Link", options="User",
		       description="التذاكر هتتسند له. سيبها فاضية عشان تروح لكل مدير النظام."),

		_field("sec_sales", "لما العميل يدفع / On Payment", "Section Break"),
		_field("auto_sales_order", "اعمل أمر بيع تلقائي", "Check", default="1"),
		_field("renewal_item", "صنف التجديد", "Link", options="Item",
		       description="الصنف اللي بيتحط في أمر البيع. لازم يتحدد عشان الأمر يتعمل."),
		_field("cb6", "", "Column Break"),
		_field("auto_payment_entry", "اعمل قيد دفع تلقائي", "Check", default="0",
		       description="سيبها مقفولة لحد ما تتطمن — القيد بيأثر على الحسابات."),
		_field("payment_account", "حساب استلام الفلوس", "Link", options="Account"),
	],
}

# ————— سجل المحادثة —————
CONVERSATION_LOG = {
	"name": "Renewal Conversation Log",
	"autoname": "hash",
	"title_field": "mobile_number",
	"fields": [
		_field("mobile_number", "رقم الموبايل", "Data", in_list_view=1, reqd=1),
		_field("customer_name", "اسم العميل", "Data", in_list_view=1),
		_field("cb1", "", "Column Break"),
		_field("direction", "الاتجاه", "Select", options="صادر\nوارد", in_list_view=1),
		_field("subscription", "الاشتراك", "Link", options="Customer Subscription"),
		_field("sec_body", "", "Section Break"),
		_field("body", "النص", "Text", in_list_view=1),
		_field("state_after", "حالة المحادثة بعدها", "Data"),
	],
}

PERMISSIONS = [
	{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
	{"role": "Sales Manager", "read": 1, "write": 1, "create": 1},
	{"role": "Sales User", "read": 1},
]

# ————— حقول جديدة على Customer Subscription —————
SUBSCRIPTION_FIELDS = [
	{
		"fieldname": "conversation_state",
		"label": "حالة المحادثة",
		"fieldtype": "Select",
		"options": "\n".join(["", "مستني رده على التذكير", "مستني اختيار طريقة الدفع",
		                      "مهتم — اتبعتله الأسعار", "طلب خدمة العملاء", "رافض التجديد"]),
		"insert_after": "customer_refused_to_renew",
		"read_only": 1,
	},
	{
		"fieldname": "last_bot_message_at",
		"label": "آخر رسالة اتبعتت",
		"fieldtype": "Datetime",
		"insert_after": "conversation_state",
		"read_only": 1,
	},
	{
		"fieldname": "messages_sent_count",
		"label": "عدد الرسايل المبعوتة",
		"fieldtype": "Int",
		"insert_after": "last_bot_message_at",
		"read_only": 1,
	},
]


def _sync(spec):
	if frappe.db.exists("DocType", spec["name"]):
		doc = frappe.get_doc("DocType", spec["name"])
		doc.fields = []
	else:
		doc = frappe.new_doc("DocType")
		doc.name = spec["name"]

	doc.module = "Sync Webshop"
	doc.custom = 0
	doc.istable = spec.get("istable", 0)
	doc.issingle = spec.get("issingle", 0)
	doc.editable_grid = 1
	doc.engine = "InnoDB"
	if spec.get("autoname"):
		doc.autoname = spec["autoname"]
	if spec.get("title_field"):
		doc.title_field = spec["title_field"]

	for idx, f in enumerate(spec["fields"], start=1):
		doc.append("fields", {**f, "idx": idx})

	if not spec.get("istable"):
		doc.permissions = []
		for p in PERMISSIONS:
			doc.append("permissions", p)
		doc.track_changes = 1

	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.save()
	return doc.name


def _custom_fields():
	added = []
	for spec in SUBSCRIPTION_FIELDS:
		name = f"Customer Subscription-{spec['fieldname']}"
		if frappe.db.exists("Custom Field", name):
			continue
		doc = frappe.new_doc("Custom Field")
		doc.dt = "Customer Subscription"
		doc.update(spec)
		doc.flags.ignore_permissions = True
		doc.insert()
		added.append(spec["fieldname"])
	return added


TEMPLATES = [
	("قبل الانتهاء",
	 "عزيزي {الاسم} 👋\nشركة رحيم جروب لأجهزة التتبع والأنظمة الأمنية.\n\n"
	 "اشتراك الجهاز {السيريال} هينتهي يوم {تاريخ_الانتهاء} — فاضل {الأيام_المتبقية} يوم.\n"
	 "حابين نجدده لك عشان الخدمة متنقطعش 🙏"),
	("قبل الانتهاء",
	 "أهلاً {الاسم} 🌹\nمعاك رحيم جروب لأجهزة التتبع.\n\n"
	 "فاكرينك بس إن اشتراك جهازك {السيريال} قرب يخلص ({الأيام_المتبقية} يوم).\n"
	 "التجديد بياخد دقيقة واحدة ومش هتحس بأي انقطاع في الخدمة."),
	("قبل الانتهاء",
	 "{الاسم} أهلاً بيك 👋\n\nجهاز التتبع بتاعك ({السيريال}) اشتراكه بينتهي {تاريخ_الانتهاء}.\n"
	 "عايزين نتأكد إن المتابعة تفضل شغالة معاك من غير توقف."),
	("يوم الانتهاء",
	 "عزيزي {الاسم} ⚠️\nشركة رحيم جروب لأجهزة التتبع.\n\n"
	 "اشتراك الجهاز {السيريال} بينتهي النهاردة.\n"
	 "جدده دلوقتي عشان الخدمة تفضل شغالة."),
	("يوم الانتهاء",
	 "{الاسم} 🔔\nآخر يوم في اشتراك جهازك {السيريال}.\n\n"
	 "لو جددت النهاردة الخدمة هتكمل من غير أي انقطاع."),
	("بعد الانتهاء",
	 "عزيزي {الاسم} 😔\nشركة رحيم جروب لأجهزة التتبع.\n\n"
	 "اشتراك الجهاز {السيريال} انتهى بالفعل والمتابعة واقفة دلوقتي.\n"
	 "تقدر تعيد تفعيله في أي وقت."),
	("بعد الانتهاء",
	 "{الاسم} أهلاً 🙏\nجهاز التتبع بتاعك ({السيريال}) اشتراكه خلص من فترة.\n\n"
	 "لسه تقدر ترجّع الخدمة بسهولة ومن غير أي رسوم إضافية."),
]


def execute():
	was_dev = frappe.conf.get("developer_mode")
	frappe.conf["developer_mode"] = 1
	try:
		created = [_sync(MESSAGE_TEMPLATE), _sync(CAMPAIGN_SETTINGS), _sync(CONVERSATION_LOG)]
	finally:
		frappe.conf["developer_mode"] = was_dev or 0

	fields = _custom_fields()
	frappe.db.commit()
	frappe.clear_cache()

	made = 0
	for stage, text in TEMPLATES:
		if frappe.db.exists("Renewal Message Template", {"template_text": text}):
			continue
		d = frappe.new_doc("Renewal Message Template")
		d.stage, d.template_text, d.enabled = stage, text, 1
		d.flags.ignore_permissions = True
		d.insert()
		made += 1
	frappe.db.commit()

	print("DOCTYPES=" + ", ".join(created))
	print("حقول جديدة على Customer Subscription: " + (", ".join(fields) or "(موجودة قبل كده)"))
	print(f"قوالب نصوص: {made} جديد | الإجمالي {frappe.db.count('Renewal Message Template')}")
