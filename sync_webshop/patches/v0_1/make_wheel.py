# -*- coding: utf-8 -*-
"""
عجلة الحظ — a spin-to-win wheel, with the prizes decided in the Desk.

The important part is not the animation, it is that the browser cannot pick the
winner. The page asks the server to spin; the server draws the segment by weight,
issues a real coupon, and answers with which slice to land on. The animation then
runs to that answer. Anyone editing the page's JavaScript changes nothing about
what they win.

One spin per person per cooldown, tracked by email so clearing cookies does not
hand out a second prize.
"""
import frappe

PRIZES = [
	# (label, coupon %, weight, colour) — weights are relative, not percentages.
	(u"خصم ٥٪", 5, 30, "#2E8F9C"),
	(u"خصم ١٠٪", 10, 22, "#343A40"),
	(u"شحن مجاني", 0, 18, "#4FB3C0"),
	(u"خصم ١٥٪", 15, 12, "#22272B"),
	(u"حظ أوفر", 0, 10, "#6B7378"),
	(u"خصم ٢٠٪", 20, 6, "#2E8F9C"),
	(u"خصم ٢٥٪", 25, 2, "#1F6D78"),
]


def field(fieldname, label, fieldtype, idx, **kw):
	d = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, "idx": idx}
	d.update(kw)
	return d


def make_doctype(name, module, fields, istable=0, title_field=None, autoname=None):
	if frappe.db.exists("DocType", name):
		print("  exists: " + name)
		return
	doc = frappe.get_doc({
		"doctype": "DocType", "name": name, "module": module,
		"custom": 0, "istable": istable, "editable_grid": 1 if istable else 0,
		"autoname": autoname, "title_field": title_field, "track_changes": 0,
		"fields": fields,
		"permissions": [] if istable else [
			{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
		],
	})
	doc.flags.ignore_permissions = True
	doc.insert()
	print("  created: " + name)


def execute():
	frappe.conf["developer_mode"] = 1
	frappe.flags.in_migrate = True
	try:
		make_doctype("Webshop Wheel Prize", "Sync Webshop", [
			field("label", "اسم الجايزة", "Data", 1, reqd=1, in_list_view=1, columns=3),
			field("discount_percent", "نسبة الخصم %", "Int", 2, in_list_view=1, columns=1,
			      description="صفر = مفيش خصم (زي شحن مجاني أو حظ أوفر)."),
			field("free_shipping", "شحن مجاني", "Check", 3, in_list_view=1, columns=1),
			field("weight", "فرصة الظهور", "Int", 4, default="10", in_list_view=1, columns=1,
			      description="رقم أكبر = بيطلع أكتر. مش نسبة مئوية."),
			field("color", "اللون", "Color", 5, columns=2),
			field("is_active", "مفعّلة", "Check", 6, default="1", in_list_view=1, columns=1),
		], istable=1)

		make_doctype("Webshop Wheel Settings", "Sync Webshop", [
			field("enabled", "شغّل عجلة الحظ", "Check", 1, default="0"),
			field("title_ar", "العنوان", "Data", 2, default=u"جرّب حظك!"),
			field("subtitle_ar", "سطر تحت العنوان", "Small Text", 3,
			      default=u"لفّة واحدة وخد خصم على أول طلب."),
			field("cb1", "", "Column Break", 4),
			field("cooldown_days", "كل قد إيه يقدر يلف تاني (أيام)", "Int", 5, default="30"),
			field("coupon_valid_days", "الكوبون صالح كام يوم", "Int", 6, default="7"),
			field("min_order_amount", "أقل قيمة طلب لاستخدام الكوبون", "Currency", 7, default="0"),
			field("sec_prizes", "الجوايز", "Section Break", 8,
			      description="غيّر الأسماء والنسب زي ما تحب. «فرصة الظهور» رقم نسبي — "
			                  "جايزة برقم 30 بتطلع ٣ أضعاف جايزة برقم 10."),
			field("prizes", "الجوايز", "Table", 9, options="Webshop Wheel Prize"),
		], autoname="")
	finally:
		frappe.conf["developer_mode"] = 0
		frappe.flags.in_migrate = False

	# Make it a Single after the fact — simplest reliable path in v15.
	if not frappe.db.get_value("DocType", "Webshop Wheel Settings", "issingle"):
		frappe.db.set_value("DocType", "Webshop Wheel Settings", "issingle", 1)
		frappe.clear_cache(doctype="Webshop Wheel Settings")

	settings = frappe.get_single("Webshop Wheel Settings")
	if not settings.prizes:
		for label, pct, weight, color in PRIZES:
			settings.append("prizes", {
				"label": label, "discount_percent": pct, "weight": weight,
				"color": color, "is_active": 1,
				"free_shipping": 1 if u"شحن" in label else 0,
			})
		settings.title_ar = u"جرّب حظك!"
		settings.subtitle_ar = u"لفّة واحدة وخد خصم على أول طلب."
		settings.cooldown_days = 30
		settings.coupon_valid_days = 7
		settings.enabled = 0
		settings.flags.ignore_permissions = True
		settings.flags.ignore_mandatory = True
		settings.save()
		print("  seeded %d prizes" % len(PRIZES))

	# Who has already spun.
	frappe.conf["developer_mode"] = 1
	frappe.flags.in_migrate = True
	try:
		make_doctype("Webshop Wheel Spin", "Sync Webshop", [
			field("email", "الإيميل", "Data", 1, reqd=1, in_list_view=1),
			field("prize_label", "الجايزة", "Data", 2, in_list_view=1),
			field("coupon_code", "كود الكوبون", "Data", 3, in_list_view=1),
			field("discount_percent", "الخصم %", "Int", 4),
			field("spun_on", "تاريخ اللفّة", "Datetime", 5, in_list_view=1),
			field("used", "اتستخدم", "Check", 6, in_list_view=1),
		], title_field="email", autoname="hash")
	finally:
		frappe.conf["developer_mode"] = 0
		frappe.flags.in_migrate = False

	frappe.db.commit()
	frappe.clear_cache()
	print("WHEEL READY")
