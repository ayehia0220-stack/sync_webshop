# -*- coding: utf-8 -*-
"""
صورتين لطرق الدفع: رحيم جروب (GPS) وميرسيفل جروب (البن).

نشاطين ببراند مختلف ورقم خدمة عملاء مختلف، فكل عميل لازم يشوف صورة نشاطه.
الأرقام اللي في الصور بتتحط كمان في «المعلومات المؤكدة» عشان المساعد
يقدر يقولها بدل ما يقول «هنبعتلك التفاصيل».
"""
import os

import frappe

IMAGES = [
	("payment_image", "/tmp/pay_gps.jpeg", "طرق-الدفع-رحيم-جروب-GPS.jpeg"),
	("payment_image_coffee", "/tmp/pay_coffee.jpeg", "طرق-الدفع-ميرسيفل-جروب-البن.jpeg"),
]

FACTS = [
	("تحويل فودافون كاش وإنستاباي", "رقم التحويل لفودافون كاش وإنستاباي: 01066858027 (نفس الرقم للاتنين)."),
	("خدمة عملاء البن — ميرسيفل جروب", "01092301212"),
	("خدمة عملاء الـ GPS — رحيم جروب", "01098982797"),
	("بعد التحويل", "العميل يبعت صورة الإيصال على نفس الرقم وبنفعّل طلبه فورًا."),
]


def _add_field():
	name = "Renewal Campaign Settings-payment_image_coffee"
	if frappe.db.exists("Custom Field", name):
		return False
	cf = frappe.new_doc("Custom Field")
	cf.dt = "Renewal Campaign Settings"
	cf.fieldname = "payment_image_coffee"
	cf.label = "صورة طرق الدفع — البن (ميرسيفل جروب)"
	cf.fieldtype = "Attach Image"
	cf.insert_after = "payment_image"
	cf.description = "بتتبعت لعملاء البن. الحقل اللي فوق بتاع الـ GPS (رحيم جروب)."
	cf.flags.ignore_permissions = True
	cf.insert()
	return True


def _attach(fieldname, path, filename):
	if not os.path.exists(path):
		return None, f"مالقيتش {path}"
	with open(path, "rb") as fh:
		content = fh.read()

	existing = frappe.get_all("File", filters={"file_name": filename}, pluck="name")
	for old in existing:
		frappe.delete_doc("File", old, force=1, ignore_permissions=True)

	f = frappe.new_doc("File")
	f.file_name = filename
	f.content = content
	f.is_private = 0          # عامة عشان تتشاف من الموقع كمان
	f.attached_to_doctype = "Renewal Campaign Settings"
	f.attached_to_name = "Renewal Campaign Settings"
	f.attached_to_field = fieldname
	f.flags.ignore_permissions = True
	f.insert()
	frappe.db.set_single_value("Renewal Campaign Settings", fieldname, f.file_url)
	return f.file_url, None


def _teach_facts():
	doc = frappe.get_doc("Webshop Agent Training", "معلومات دبونو العامة")
	have = {(r.topic or "").strip() for r in doc.facts}
	added = 0
	for topic, answer in FACTS:
		if topic in have:
			continue
		doc.append("facts", {"topic": topic, "answer": answer})
		added += 1
	if added:
		doc.flags.ignore_permissions = True
		doc.save()
	return added


def execute():
	print("حقل صورة البن:", "اتضاف" if _add_field() else "موجود")
	frappe.db.commit()
	frappe.clear_cache()

	for fieldname, path, filename in IMAGES:
		url, err = _attach(fieldname, path, filename)
		print(f"  {fieldname}: {url or ('✗ ' + err)}")
	frappe.db.commit()

	print("حقائق جديدة للمساعد:", _teach_facts())
	frappe.db.commit()

	s = frappe.get_single("Renewal Campaign Settings")
	print("\nالمحفوظ دلوقتي:")
	print("  GPS  :", s.get("payment_image"))
	print("  البن :", s.get("payment_image_coffee"))
