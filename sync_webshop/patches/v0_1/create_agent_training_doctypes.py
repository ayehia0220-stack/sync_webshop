# -*- coding: utf-8 -*-
"""
Agent training as documents the owner writes in ERPNext.

One place teaches every assistant: the Facebook comment bot, the website chat,
WhatsApp, anything added later. The owner edits a document; no code, no deploy.

The prompt each channel receives is assembled by `api/agent_training.py` from
these records, so what the assistant is allowed to say lives in ERPNext and
nowhere else.
"""
import frappe


def _field(fieldname, label, fieldtype, **kw):
	field = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype}
	field.update(kw)
	return field


AGENT_FACT = {
	"name": "Webshop Agent Fact",
	"istable": 1,
	"fields": [
		_field("topic", "الموضوع / Topic", "Data", in_list_view=1, reqd=1,
		       description="مثال: الشحن، مواعيد التسليم، الدفع، رقم خدمة العملاء"),
		_field("answer", "المعلومة الصح / The Answer", "Small Text", in_list_view=1, reqd=1,
		       description="اكتب الحقيقة بالظبط. المساعد ممنوع يقول غير اللي مكتوب هنا."),
	],
}

AGENT_EXAMPLE = {
	"name": "Webshop Agent Example",
	"istable": 1,
	"fields": [
		_field("customer_says", "العميل بيقول / Customer says", "Small Text", in_list_view=1, reqd=1),
		_field("public_reply", "الرد العام / Public reply", "Small Text", in_list_view=1,
		       description="الرد اللي بيتنشر تحت التعليق. سيبه فاضي لو القناة مش فيسبوك."),
		_field("private_reply", "الرد الخاص / Private reply", "Small Text", in_list_view=1,
		       description="الرسالة الخاصة أو رد الشات."),
	],
}

AGENT_TRAINING = {
	"name": "Webshop Agent Training",
	"autoname": "field:training_name",
	"title_field": "training_name",
	"fields": [
		_field("training_name", "اسم التدريب / Name", "Data", reqd=1, unique=1, in_list_view=1,
		       description="مثال: تعليقات فيسبوك، شات الموقع"),
		_field("enabled", "شغّال / Enabled", "Check", default="1", in_list_view=1),
		_field("cb1", "", "Column Break"),
		_field("channel", "القناة / Channel", "Select", in_list_view=1, reqd=1,
		       options="\n".join(["الكل / All", "فيسبوك / Facebook", "الموقع / Website",
		                          "واتساب / WhatsApp", "تليجرام / Telegram"]),
		       default="الكل / All",
		       description="«الكل» بيتضاف على كل القنوات — حط فيه الحاجات المشتركة."),
		_field("priority", "الأولوية / Priority", "Int", default="10",
		       description="لو فيه أكتر من تدريب لنفس القناة، الأقل رقمًا بيتقرا الأول."),

		_field("sec_persona", "شخصية المساعد / Persona", "Section Break",
		       description="مين هو المساعد وبيتكلم إزاي."),
		_field("persona", "الشخصية", "Small Text",
		       description="مثال: أنت موظف خدمة عملاء في متجر دبونو للبن، بتتكلم بالعامية المصرية، ودود ومختصر."),
		_field("cb2", "", "Column Break"),
		_field("tone", "اللهجة / Tone", "Select",
		       options="\n".join(["عامية مصرية", "عربي فصيح", "إنجليزي", "حسب لغة العميل"]),
		       default="عامية مصرية"),

		_field("sec_rules", "القواعد / Rules", "Section Break",
		       description="اللي المساعد لازم يعمله واللي ممنوع عليه."),
		_field("rules", "قواعد لازم يتبعها", "Text",
		       description="سطر لكل قاعدة. مثال: خلي الرد العام جملة واحدة."),
		_field("cb3", "", "Column Break"),
		_field("forbidden", "ممنوع يتكلم في", "Small Text",
		       description="سطر لكل موضوع. مثال: التكلفة، هامش الربح، الموردين، المرتبات."),
		_field("sec_unsure", "", "Section Break"),
		_field("when_unsure", "لو مش عارف الإجابة", "Small Text",
		       default="لو المعلومة مش مكتوبة في «المعلومات المؤكدة»، ممنوع تخترع. قول للعميل إن حد من الفريق هيرد عليه، وبس.",
		       description="مهم: ده اللي بيمنع المساعد يخترع أسعار وأرقام مش حقيقية."),

		_field("sec_facts", "المعلومات المؤكدة / Verified Facts", "Section Break",
		       description="المساعد مسموح له يقول الحاجات دي بس. أي رقم أو سعر مش هنا = ممنوع يقوله."),
		_field("facts", "المعلومات", "Table", options="Webshop Agent Fact"),

		_field("sec_examples", "أمثلة / Examples", "Section Break",
		       description="أمثلة حقيقية بتعلّم المساعد الأسلوب. كل ما تزود، كل ما بقى أحسن."),
		_field("examples", "الأمثلة", "Table", options="Webshop Agent Example"),

		_field("sec_advanced", "إعدادات متقدمة / Advanced", "Section Break", collapsible=1),
		_field("output_format", "شكل الرد المطلوب", "Small Text",
		       description="سيبها فاضية غير لو القناة محتاجة شكل معيّن (زي JSON لتعليقات فيسبوك)."),
		_field("extra_instructions", "تعليمات إضافية", "Text"),
		_field("sec_notes", "", "Section Break"),
		_field("notes", "ملاحظات داخلية / Internal Notes", "Small Text",
		       description="مش بتتبعت للمساعد."),
	],
}

PERMISSIONS = [
	{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
	{"role": "Sales Manager", "read": 1, "write": 1, "create": 1},
	{"role": "Sales User", "read": 1},
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
	doc.editable_grid = 1
	doc.engine = "InnoDB"
	if spec.get("autoname"):
		doc.autoname = spec["autoname"]
	if spec.get("title_field"):
		doc.title_field = spec["title_field"]

	for idx, field in enumerate(spec["fields"], start=1):
		doc.append("fields", {**field, "idx": idx})

	if not spec.get("istable"):
		doc.permissions = []
		for perm in PERMISSIONS:
			doc.append("permissions", perm)
		doc.track_changes = 1

	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.save()
	return doc.name


def execute():
	was_dev = frappe.conf.get("developer_mode")
	frappe.conf["developer_mode"] = 1
	try:
		created = [_sync(AGENT_FACT), _sync(AGENT_EXAMPLE), _sync(AGENT_TRAINING)]
	finally:
		frappe.conf["developer_mode"] = was_dev or 0

	frappe.db.commit()
	frappe.clear_cache()
	print("DOCTYPES=" + ", ".join(created))
