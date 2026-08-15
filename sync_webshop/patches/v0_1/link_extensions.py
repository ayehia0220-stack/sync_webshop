# -*- coding: utf-8 -*-
"""
يربط أرقام السنترال الداخلية بموظفي ERPNext عشان شاشة المكالمة تفتح عند صاحبها.

الربط بيتم بمطابقة الاسم اللي في السنترال بكارت الموظف. اللي مالوش كارت أو
حساب بيتقال صراحة بدل ما يتعمل له كارت ناقص — كارت موظف من غير بيانات
بيبوّظ التقارير أكتر ما بيفيد.

مش بيتحط أي باسورد: ERPNext بيبعت للمستخدم رابط يحطه بنفسه.
"""
import frappe

# الرقم الداخلي كما في السنترال -> الاسم المكتوب هناك
PBX = {
	"67": "islam yehia",
	"890": "doha",
	"891": "SHAZA",
	"893": "mahmod ibrahem",
	"894": "Fatma",
	"895": "donea",
	"896": "menna",
	"897": "asmaa",
	"898": "eman",
	"899": "dalia",
	"900": "MAI",
}

# مطابقات يدوية للأسماء اللي الكتابة فيها مختلفة
ALIASES = {
	"doha": ["doha samir", "ضحى", "ضحي"],
	"islam yehia": ["islam", "yehia", "يحيى", "إسلام", "اسلام"],
	"mahmod ibrahem": ["mahmoud", "محمود"],
	"asmaa": ["اسماء", "أسماء"],
	"eman": ["ايمان", "إيمان"],
	"menna": ["منة", "منه"],
	"dalia": ["داليا"],
	"fatma": ["فاطمة", "فاطمه"],
	"shaza": ["شذى", "شاذا"],
	"donea": ["دنيا", "دنيه"],
	"mai": ["مي", "ماي"],
}


def _norm(text):
	return " ".join(str(text or "").lower().replace("ـ", "").split())


def _match(pbx_name, employees):
	target = _norm(pbx_name)
	parts = [p for p in target.split() if len(p) > 2]
	candidates = ALIASES.get(target, []) + [target]

	for emp in employees:
		name = _norm(emp.employee_name)
		for c in candidates:
			if _norm(c) and _norm(c) in name:
				return emp
		# أول اسم مشترك
		for p in parts:
			if p in name:
				return emp
	return None


def execute():
	employees = frappe.get_all("Employee", filters={"status": "Active"},
	                           fields=["name", "employee_name", "user_id", "custom_extension"])
	linked, no_user, no_employee = [], [], []

	for ext, pbx_name in PBX.items():
		emp = _match(pbx_name, employees)
		if not emp:
			no_employee.append((ext, pbx_name))
			continue
		if not emp.user_id:
			no_user.append((ext, pbx_name, emp.employee_name))
			continue
		frappe.db.set_value("Employee", emp.name, "custom_extension", ext, update_modified=False)
		linked.append((ext, emp.employee_name, emp.user_id))

	frappe.db.commit()

	print("=" * 58)
	print("✅ اتربطوا — الشاشة هتفتح عندهم:")
	for ext, name, user in sorted(linked):
		print(f"   داخلي {ext:<4} → {name}  ({user})")

	print("\n⚠️  عندهم كارت موظف بس من غير حساب دخول:")
	for ext, pbx, name in sorted(no_user):
		print(f"   داخلي {ext:<4} → {name}  (بالسنترال: {pbx})")

	print("\n❌ مالهمش كارت موظف في ERPNext:")
	for ext, pbx in sorted(no_employee):
		print(f"   داخلي {ext:<4} → {pbx}")

	print("\n" + "=" * 58)
	print("الموظفين النشطين اللي عندهم حساب دخول:")
	for e in employees:
		if e.user_id:
			print(f"   {e.employee_name}  →  {e.user_id}")
