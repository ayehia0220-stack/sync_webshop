# -*- coding: utf-8 -*-
"""
الواتساب الوارد يتعالج في الـ ERP الأول، ويتمرّر لـ n8n بس لو محدش رد عليه.

`_handle_evolution` كانت بتسجّل الرسالة وتمرّرها لـ n8n على طول. دلوقتي
بتعرض الرسالة على المساعد جوّه الـ ERP الأول؛ لو الرقم من أرقام البوت
(1212) المساعد بيرد وخلاص، ولو رقم التجديد (97) بيمشي زي ما هو لـ n8n.
"""
import ast
import io
import shutil
import time

P = ("/home/frappe/frappe-bench-15/apps/sync_webshop/"
     "sync_webshop/api/notifications.py")

OLD = """	frappe.db.commit()
	_forward(payload, instance)"""

NEW = '''	frappe.db.commit()

	# المساعد جوّه الـ ERP بياخد فرصته الأول. لو رد، مافيش داعي
	# نمرّر الرسالة لـ n8n وترد تاني.
	handled = False
	try:
		from sync_webshop.api.social import handle_whatsapp
		handled = handle_whatsapp(payload, instance)
	except Exception:
		frappe.log_error(title="Social whatsapp",
		                 message=frappe.get_traceback()[:2000])

	if not handled:
		_forward(payload, instance)'''


def execute():
	src = io.open(P, encoding="utf-8").read()
	if "handle_whatsapp" in src:
		print("  — متوصّل بالفعل")
		return
	if OLD not in src:
		raise SystemExit("✗ مالقيتش مكان التعديل")
	shutil.copy(P, P + ".bak-%s" % time.strftime("%Y%m%d-%H%M%S"))
	src = src.replace(OLD, NEW, 1)
	ast.parse(src)
	io.open(P, "w", encoding="utf-8").write(src)
	print("  ✓ الواتساب بقى بيعدّي على الـ ERP الأول")
