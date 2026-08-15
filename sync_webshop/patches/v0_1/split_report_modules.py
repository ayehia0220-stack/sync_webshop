# -*- coding: utf-8 -*-
"""
يفصل التقارير على موديولات حسب موضوعها.

كانوا كلهم تحت `Sync Webshop`، فقائمة التقارير كانت بتعرض تقارير تربو
والمكالمات والمتجر مرصوصين مع بعض. الموديول هو اللي بيحدد التجميع في
قائمة التقارير، مش المساحة.
"""
import frappe

MODULES = {
	"مكالمات دبونو": [
		"سجل المكالمات", "مكالمات الموظفين", "أوقات ذروة المكالمات",
		"أرقام اتصلت وليست عملاء", "مكالمات ضاعت ومحدش رجّعها", "مكالمات العملاء",
		"مقارنة المكالمات أسبوعيًا", "سرعة الرد على المكالمات",
		"مكالمات كل خط (دنجل)", "مكالمات أدّت لمبيعات",
	],
	"شحن تربو": [
		"تربو — في انتظار الشحن", "تربو — شحنات على الطريق",
		"تربو — شحنات فيها مشكلة", "تربو — الفلوس عند الشركة",
	],
	# الباقي يفضل في Sync Webshop: تحليلات المتجر وتقسيم العملاء
}

# المساحات كمان تتبع موضوعها
WORKSPACE_MODULE = {
	"المكالمات": "مكالمات دبونو",
	"تربو": "شحن تربو",
}

DOCTYPE_MODULE = {
	"Call Request": "مكالمات دبونو",
}


def _ensure_module(name):
	if frappe.db.exists("Module Def", name):
		return False
	doc = frappe.new_doc("Module Def")
	doc.module_name = name
	doc.app_name = "sync_webshop"
	doc.custom = 1
	doc.flags.ignore_permissions = True
	doc.insert()
	return True


def execute():
	for module in MODULES:
		print(("  + موديول جديد: " if _ensure_module(module) else "  موديول موجود: ") + module)
	frappe.db.commit()
	frappe.clear_cache()

	moved = 0
	for module, reports in MODULES.items():
		for r in reports:
			if frappe.db.exists("Report", r):
				frappe.db.set_value("Report", r, "module", module, update_modified=False)
				moved += 1
	print(f"\n  اتنقل {moved} تقرير")

	for ws, module in WORKSPACE_MODULE.items():
		if frappe.db.exists("Workspace", ws):
			frappe.db.set_value("Workspace", ws, "module", module, update_modified=False)
			print(f"  مساحة «{ws}» → {module}")

	for dt, module in DOCTYPE_MODULE.items():
		if frappe.db.exists("DocType", dt):
			frappe.db.set_value("DocType", dt, "module", module, update_modified=False)
			print(f"  دوك تايب «{dt}» → {module}")

	frappe.db.commit()
	frappe.clear_cache()

	print("\n=== التقارير بعد الفصل ===")
	rows = frappe.get_all("Report", filters={"is_standard": "No"},
	                      fields=["name", "module"], order_by="module, name")
	current = None
	for r in rows:
		if r.module != current:
			current = r.module
			print(f"\n  ▸ {current}")
		print(f"     • {r.name}")
