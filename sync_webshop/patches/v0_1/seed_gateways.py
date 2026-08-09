# -*- coding: utf-8 -*-
"""
Starter records for payment methods and couriers.

Only cash on delivery is switched on, because it is the only one that needs no
outside account. Everything else is created ready and disabled, so the owner
fills in the keys and ticks Enabled — no code, no deploy.
"""
import frappe

GATEWAYS = [
	{
		"gateway_name": "Cash on Delivery",
		"gateway_type": "Cash on Delivery",
		"label_ar": "الدفع عند الاستلام",
		"label_en": "Cash on delivery",
		"instructions_ar": "هتدفع للمندوب وقت التسليم.",
		"instructions_en": "Pay the courier when your order arrives.",
		"enabled": 1,
		"sort_order": 1,
	},
	{
		"gateway_name": "Bank Transfer",
		"gateway_type": "Bank Transfer",
		"label_ar": "تحويل بنكي",
		"label_en": "Bank transfer",
		"instructions_ar": "اكتب هنا بيانات حسابك البنكي — هتظهر للعميل بعد ما يختار الطريقة دي.",
		"instructions_en": "Put your bank details here — the customer sees them after choosing this option.",
		"enabled": 0,
		"sort_order": 2,
	},
	{
		"gateway_name": "Paymob",
		"gateway_type": "Paymob",
		"label_ar": "بطاقة / محفظة إلكترونية",
		"label_en": "Card / mobile wallet",
		"enabled": 0,
		"sort_order": 3,
		"mode": "Test",
	},
	{
		"gateway_name": "Fawry",
		"gateway_type": "Fawry",
		"label_ar": "فوري",
		"label_en": "Fawry",
		"enabled": 0,
		"sort_order": 4,
		"mode": "Test",
	},
]

COURIERS = [
	{
		"company_name": "Bosta",
		"label_ar": "بوسطة",
		"label_en": "Bosta",
		"enabled": 0,
		"shipping_cost": 0,
		"min_delivery_days": 1,
		"max_delivery_days": 3,
		"tracking_url_template": "https://bosta.co/tracking-shipments?tracking={tracking_number}",
		"notes": "املأ التكلفة والمناطق وحساب الإيراد، وبعدين علّم مفعّل.",
	},
	{
		"company_name": "Mylerz",
		"label_ar": "ميلرز",
		"label_en": "Mylerz",
		"enabled": 0,
		"shipping_cost": 0,
		"min_delivery_days": 1,
		"max_delivery_days": 4,
		"notes": "املأ التكلفة والمناطق وحساب الإيراد، وبعدين علّم مفعّل.",
	},
]


def _insert(doctype, values, key):
	if frappe.db.exists(doctype, values[key]):
		return None
	doc = frappe.get_doc({"doctype": doctype, **values})
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.insert()
	return doc.name


def execute():
	created = []

	for row in GATEWAYS:
		name = _insert("Webshop Payment Gateway", row, "gateway_name")
		if name:
			created.append("gateway:" + name)

	for row in COURIERS:
		name = _insert("Webshop Shipping Company", row, "company_name")
		if name:
			created.append("courier:" + name)

	# Carry over anything already configured on the old single record, so the
	# live store keeps behaving the same.
	old = frappe.get_single("Webshop Payment Settings")
	if old.get("stripe_enabled") and not frappe.db.exists("Webshop Payment Gateway", "Stripe"):
		doc = frappe.get_doc(
			{
				"doctype": "Webshop Payment Gateway",
				"gateway_name": "Stripe",
				"gateway_type": "Stripe",
				"label_ar": "بطاقة",
				"label_en": "Card",
				"enabled": 0,
				"sort_order": 5,
				"mode": old.get("stripe_mode") or "Test",
				"public_key": old.get("stripe_publishable_key"),
			}
		)
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert()
		created.append("gateway:Stripe (disabled — needs rebuilding)")

	frappe.db.commit()
	frappe.clear_cache()
	print("SEEDED=" + (", ".join(created) if created else "nothing new"))
