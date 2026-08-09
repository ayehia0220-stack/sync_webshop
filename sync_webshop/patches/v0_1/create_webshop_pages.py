# -*- coding: utf-8 -*-
"""
Content pages as documents: About, FAQ, Shipping, Returns, Privacy, Terms.

A page is a record with a slug and rich text in both languages. Adding a page
is a new document; it appears on the site and in the footer with no code.

The starter pages are created **unpublished and empty**. Shipping, returns,
privacy and terms are binding commitments and legal text — those have to be
written by the business, not generated.
"""
import frappe


def _field(fieldname, label, fieldtype, **kw):
	field = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype}
	field.update(kw)
	return field


PAGE_DOCTYPE = {
	"name": "Webshop Page",
	"autoname": "field:slug",
	"title_field": "title_ar",
	"fields": [
		_field("slug", "الرابط / Slug", "Data", reqd=1, unique=1, in_list_view=1,
		       description="يظهر في العنوان: shop.dpono.com/page/<الرابط>. حروف إنجليزية وشرطات فقط."),
		_field("published", "منشورة / Published", "Check", default="0", in_list_view=1,
		       description="مش هتظهر على الموقع غير لما تعلّم هنا."),
		_field("cb1", "", "Column Break"),
		_field("show_in_footer", "تظهر في التذييل / Show in Footer", "Check", default="1"),
		_field("sort_order", "الترتيب / Order", "Int", default="0"),
		_field("sec_ar", "المحتوى بالعربي", "Section Break"),
		_field("title_ar", "العنوان", "Data", reqd=1, in_list_view=1),
		_field("content_ar", "المحتوى", "Text Editor"),
		_field("sec_en", "English content", "Section Break"),
		_field("title_en", "Title", "Data"),
		_field("content_en", "Content", "Text Editor"),
		_field("sec_seo", "SEO", "Section Break", collapsible=1),
		_field("meta_description_ar", "وصف محركات البحث (عربي)", "Small Text"),
		_field("meta_description_en", "Meta description (English)", "Small Text"),
	],
}

PERMISSIONS = [
	{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
	{"role": "Sales Manager", "read": 1, "write": 1, "create": 1},
]

# Empty on purpose. A shipping or returns policy is a promise the business
# makes; inventing one would put words in the owner's mouth.
STARTER_PAGES = [
	("about", "من نحن", "About us", 1,
	 "اكتب هنا قصة المتجر: مين إنتم، وبتحمّصوا إزاي، وإيه اللي يميّزكم."),
	("shipping", "سياسة الشحن", "Shipping policy", 2,
	 "اكتب هنا مناطق التوصيل، والمدة المتوقعة، والتكلفة، ومواعيد العمل."),
	("returns", "سياسة الاسترجاع", "Returns policy", 3,
	 "اكتب هنا مدة الاسترجاع، وحالة المنتج المقبولة، وطريقة استرداد المبلغ، ومين يتحمّل الشحن."),
	("privacy", "سياسة الخصوصية", "Privacy policy", 4,
	 "اكتب هنا البيانات اللي بتجمعوها، وليه، ومين بيشوفها، وإزاي العميل يطلب حذفها."),
	("terms", "الشروط والأحكام", "Terms and conditions", 5,
	 "اكتب هنا شروط البيع والدفع والإلغاء. يُفضّل مراجعتها مع محامٍ."),
	("contact", "اتصل بنا", "Contact us", 6,
	 "اكتب هنا وسائل التواصل ومواعيد الرد."),
]


def _sync_doctype():
	if frappe.db.exists("DocType", PAGE_DOCTYPE["name"]):
		doc = frappe.get_doc("DocType", PAGE_DOCTYPE["name"])
		doc.fields = []
	else:
		doc = frappe.new_doc("DocType")
		doc.name = PAGE_DOCTYPE["name"]

	doc.module = "Sync Webshop"
	doc.custom = 0
	doc.engine = "InnoDB"
	doc.autoname = PAGE_DOCTYPE["autoname"]
	doc.title_field = PAGE_DOCTYPE["title_field"]
	doc.track_changes = 1

	for idx, field in enumerate(PAGE_DOCTYPE["fields"], start=1):
		doc.append("fields", {**field, "idx": idx})

	doc.permissions = []
	for perm in PERMISSIONS:
		doc.append("permissions", perm)

	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.save()


def execute():
	was_dev = frappe.conf.get("developer_mode")
	frappe.conf["developer_mode"] = 1
	try:
		_sync_doctype()
	finally:
		frappe.conf["developer_mode"] = was_dev or 0

	created = []
	for slug, title_ar, title_en, order, guidance in STARTER_PAGES:
		if frappe.db.exists("Webshop Page", slug):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Webshop Page",
				"slug": slug,
				"title_ar": title_ar,
				"title_en": title_en,
				"sort_order": order,
				"published": 0,
				"show_in_footer": 1,
				"content_ar": f"<p><em>{guidance}</em></p>",
			}
		)
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert()
		created.append(slug)

	frappe.db.commit()
	frappe.clear_cache()
	print("PAGES=" + (", ".join(created) if created else "none new"))
