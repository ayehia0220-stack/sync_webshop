# -*- coding: utf-8 -*-
"""
Delivery coverage counted from the shipping zones, and the About & Contact page.

The coverage tile was reading shipping addresses on old orders, which are empty
on the legacy ERP data, so it showed zero and got dropped. The zones are the
real statement of where the shop delivers, so it counts those instead — and it
stays right on its own whenever a governorate is added or removed.

An override is there for when the owner wants to state a different number, but
the default is the truth in the data.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# Arabic comma is the separator that is actually used in the zone fields.
SEPARATORS = (u"،", ",", "\n", "/")

ABOUT_AR = u"""
<h2>مين إحنا</h2>
<p>
  دبونو بيت تحميص بن مصري. بنشتري القهوة الخضرا، بنحمّصها على دفعات صغيرة،
  وبنشحنها في نفس الأسبوع — عشان اللي يوصلك يكون لسه طالع من المحمصة، مش قاعد
  على رف شهور.
</p>

<h2>ليه إحنا</h2>
<ul>
  <li><strong>تحميص طازة.</strong> بنحمّص على الطلب، مش بنخزّن.</li>
  <li><strong>طحن على مزاجك.</strong> قولنا ماكينتك إيه واحنا نظبط الدرجة.</li>
  <li><strong>الفلوس عند الاستلام.</strong> متدفعش قبل ما تشوف الطلب.</li>
</ul>

<h2>بنوصل فين</h2>
<p id="coverage-note">بنشحن لكل محافظات مصر. تكلفة الشحن بتختلف حسب المنطقة،
وبتظهرلك في صفحة إتمام الطلب قبل ما تدفع.</p>

<h2>كلّمنا</h2>
<p>
  أي سؤال أو مشكلة في طلب، إحنا موجودين:
</p>
<ul>
  <li><strong>واتساب:</strong> <a href="https://wa.me/201114021275">0111 402 1275</a> — أسرع طريقة</li>
  <li><strong>إيميل:</strong> <a href="mailto:info@dpono.com">info@dpono.com</a></li>
  <li><strong>تليفون:</strong> <a href="tel:+201092301212">0109 230 1212</a></li>
</ul>

<h2>المحمصة</h2>
<p>
  <a href="https://maps.app.goo.gl/i4mHLqTHTgdTG3Y99" target="_blank" rel="noopener">
    مرسيفل جروب (دبونو) — افتح الموقع على الخريطة
  </a>
</p>
<p>مواعيد الرد: من السبت للخميس، ٩ صباحًا – ٥ مساءً.</p>
"""

ABOUT_EN = u"""
<h2>Who we are</h2>
<p>
  dpono is an Egyptian coffee roastery. We buy green coffee, roast it in small
  batches, and ship the same week — so what reaches you is fresh from the
  roaster, not off a shelf.
</p>

<h2>Talk to us</h2>
<ul>
  <li><strong>WhatsApp:</strong> <a href="https://wa.me/201114021275">+20 111 402 1275</a> — fastest</li>
  <li><strong>Email:</strong> <a href="mailto:info@dpono.com">info@dpono.com</a></li>
  <li><strong>Phone:</strong> <a href="tel:+201092301212">+20 109 230 1212</a></li>
</ul>
<p>Saturday to Thursday, 9am – 5pm.</p>
"""


def count_governorates():
	names = set()
	for zone in frappe.get_all("Webshop Shipping Zone", pluck="name"):
		raw = frappe.db.get_value("Webshop Shipping Zone", zone, "governorates") or ""
		for sep in SEPARATORS[1:]:
			raw = raw.replace(sep, SEPARATORS[0])
		names.update(p.strip() for p in raw.split(SEPARATORS[0]) if p.strip())
	return names


def execute():
	found = count_governorates()
	print("governorates in zones: %d" % len(found))

	create_custom_fields({"Webshop Content Settings": [{
		"fieldname": "stats_cities_override",
		"label": "عدد المحافظات (اتركه صفر للحساب التلقائي)",
		"fieldtype": "Int",
		"default": "0",
		"insert_after": "stats_min_customers",
		"description": "بيتحسب لوحده من مناطق الشحن. حط رقم هنا بس لو عايز "
		               "تعرض رقم مختلف.",
	}]}, ignore_validate=True)

	# --- the About & Contact page ------------------------------------------
	slug = "about-contact"
	if not frappe.db.exists("Webshop Page", slug):
		doc = frappe.get_doc({
			"doctype": "Webshop Page",
			"slug": slug,
			"published": 1,
			"show_in_footer": 0,
			"sort_order": 5,
			"title_ar": u"من نحن والتواصل",
			"title_en": "About & Contact",
			"content_ar": ABOUT_AR,
			"content_en": ABOUT_EN,
			"meta_description_ar": u"دبونو — بيت تحميص بن مصري. اعرف مين إحنا، "
			                       u"وبنوصل فين، وكلّمنا على واتساب أو إيميل.",
			"meta_description_en": "dpono — an Egyptian coffee roastery. Who we are, "
			                       "where we deliver, and how to reach us.",
		})
		doc.flags.ignore_permissions = True
		doc.insert()
		print("page created: /page/" + slug)
	else:
		print("page already exists")

	# --- put it in the top nav, right after order tracking ------------------
	settings = frappe.get_single("Webshop Content Settings")
	target = "/page/" + slug
	if not any((r.link_url or "") == target for r in settings.nav_links):
		rows = [
			{"label_ar": r.label_ar, "label_en": r.label_en, "link_url": r.link_url}
			for r in settings.nav_links
		]
		entry = {"label_ar": u"من نحن والتواصل", "label_en": "About & Contact",
		         "link_url": target}
		at = next((i for i, r in enumerate(rows) if (r["link_url"] or "") == "/track"), None)
		rows.insert(at + 1 if at is not None else len(rows), entry)

		settings.set("nav_links", [])
		for r in rows:
			settings.append("nav_links", r)
		settings.flags.ignore_permissions = True
		settings.flags.ignore_mandatory = True
		settings.save()
		print("nav: " + " | ".join(r["label_ar"] for r in rows))
	else:
		print("nav link already there")

	frappe.cache().delete_value("webshop_store_stats")
	frappe.db.commit()
	frappe.clear_cache()
	print("DONE")
