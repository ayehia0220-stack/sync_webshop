# -*- coding: utf-8 -*-
"""
Shipping companies and payment methods as records the owner creates in ERPNext.

Adding a courier or a payment method is a new document — no code, no deploy.
The DocTypes are written to the app folder as well as the database, so they
travel with the app and can be reinstalled anywhere.
"""
import frappe


def _field(fieldname, label, fieldtype, **kw):
	field = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype}
	field.update(kw)
	return field


SHIPPING_ZONE = {
	"name": "Webshop Shipping Zone",
	"istable": 1,
	"fields": [
		_field("zone_name", "اسم المنطقة / Zone", "Data", in_list_view=1, reqd=1),
		_field("governorates", "المحافظات / Governorates", "Small Text", in_list_view=1,
		       description="اكتب المحافظات مفصولة بفاصلة. سيبها فاضية عشان تكون المنطقة الافتراضية."),
		_field("shipping_cost", "تكلفة الشحن / Cost", "Currency", in_list_view=1),
		_field("free_shipping_threshold", "شحن مجاني فوق / Free Over", "Currency"),
		_field("delivery_days", "أيام التوصيل / Days", "Int", in_list_view=1),
	],
}

SHIPPING_COMPANY = {
	"name": "Webshop Shipping Company",
	"autoname": "field:company_name",
	"title_field": "company_name",
	"fields": [
		_field("company_name", "اسم الشركة / Company", "Data", reqd=1, unique=1, in_list_view=1),
		_field("enabled", "مفعّل / Enabled", "Check", default="1", in_list_view=1),
		_field("cb1", "", "Column Break"),
		_field("label_ar", "الاسم للعميل (عربي)", "Data"),
		_field("label_en", "Label shown to customer (English)", "Data"),
		_field("sec_rates", "الأسعار الافتراضية / Default Rates", "Section Break"),
		_field("shipping_cost", "تكلفة الشحن / Shipping Cost", "Currency", in_list_view=1,
		       description="التكلفة لو مفيش منطقة مطابقة."),
		_field("free_shipping_threshold", "شحن مجاني فوق / Free Shipping Over", "Currency",
		       description="سيبها صفر عشان تلغي الشحن المجاني."),
		_field("cb2", "", "Column Break"),
		_field("min_delivery_days", "أقل عدد أيام / Min Days", "Int", default="1"),
		_field("max_delivery_days", "أكبر عدد أيام / Max Days", "Int", default="5"),
		_field("sec_zones", "مناطق التوصيل / Delivery Zones", "Section Break",
		       description="سعر مختلف لكل منطقة. أول منطقة تطابق محافظة العميل هي اللي تتحسب."),
		_field("zones", "المناطق", "Table", options="Webshop Shipping Zone"),
		_field("sec_acct", "المحاسبة والتتبّع / Accounting & Tracking", "Section Break"),
		_field("shipping_account", "حساب إيراد الشحن / Income Account", "Link", options="Account",
		       description="إجباري لو فيه تكلفة شحن — هنا بيترحّل مبلغ الشحن."),
		_field("cb3", "", "Column Break"),
		_field("tracking_url_template", "رابط التتبّع / Tracking URL", "Data",
		       description="مثال: https://bosta.co/tracking?id={tracking_number}"),
		_field("sec_notes", "", "Section Break"),
		_field("notes", "ملاحظات داخلية / Internal Notes", "Small Text"),
	],
}

PAYMENT_GATEWAY = {
	"name": "Webshop Payment Gateway",
	"autoname": "field:gateway_name",
	"title_field": "gateway_name",
	"fields": [
		_field("gateway_name", "اسم الطريقة / Name", "Data", reqd=1, unique=1, in_list_view=1),
		_field("enabled", "مفعّل / Enabled", "Check", default="0", in_list_view=1),
		_field("gateway_type", "النوع / Type", "Select", reqd=1, in_list_view=1,
		       options="Cash on Delivery\nBank Transfer\nPaymob\nFawry\nStripe\nCustom Redirect",
		       description="الدفع عند الاستلام والتحويل البنكي شغّالين بالإعدادات دي بس. الباقي محتاج مفاتيح."),
		_field("sort_order", "الترتيب / Order", "Int", default="0"),
		_field("cb1", "", "Column Break"),
		_field("label_ar", "الاسم للعميل (عربي)", "Data", reqd=1),
		_field("label_en", "Label shown to customer (English)", "Data"),
		_field("extra_fee", "رسوم إضافية / Extra Fee", "Currency",
		       description="رسوم تحصيل مثلًا. تتضاف على إجمالي الطلب."),
		_field("sec_instructions", "تعليمات للعميل / Customer Instructions", "Section Break"),
		_field("instructions_ar", "التعليمات (عربي)", "Small Text",
		       description="تظهر للعميل لما يختار الطريقة دي — مثلًا بيانات الحساب البنكي."),
		_field("instructions_en", "Instructions (English)", "Small Text"),
		_field("sec_keys", "مفاتيح البوابة / Gateway Keys", "Section Break",
		       description="تُملأ من لوحة مزوّد الدفع. المفاتيح السرية متخزّنة مشفّرة."),
		_field("mode", "الوضع / Mode", "Select", options="Test\nLive", default="Test"),
		_field("public_key", "المفتاح العام / Public Key", "Data"),
		_field("secret_key", "المفتاح السري / Secret Key", "Password"),
		_field("cb2", "", "Column Break"),
		_field("webhook_secret", "سر الـ Webhook", "Password"),
		_field("merchant_id", "رقم التاجر / Merchant ID", "Data"),
		_field("integration_id", "Integration ID", "Data",
		       description="Paymob بيحتاجه."),
		_field("sec_redirect", "", "Section Break"),
		_field("redirect_url_template", "رابط التحويل / Redirect URL", "Data",
		       description="لنوع Custom Redirect. متاح: {order_id} {amount} {currency} {email}"),
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
	# Writing DocTypes to disk needs developer mode; it is switched back off
	# straight afterwards so production keeps its safe setting.
	was_dev = frappe.conf.get("developer_mode")
	frappe.conf["developer_mode"] = 1
	try:
		created = [_sync(SHIPPING_ZONE), _sync(SHIPPING_COMPANY), _sync(PAYMENT_GATEWAY)]
	finally:
		frappe.conf["developer_mode"] = was_dev or 0

	frappe.db.commit()
	frappe.clear_cache()
	print("DOCTYPES=" + ", ".join(created))
