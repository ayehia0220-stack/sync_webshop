# -*- coding: utf-8 -*-
"""
Put the dpono palette on the ERP's own portal pages.

The customer portal inside ERPNext still wore Bootstrap's default blue, so a
customer following an order link left the brand behind. Same graphite and teal
as the storefront, added as an override block so nothing already in the theme is
lost.
"""
import frappe

MARK = "/* === ألوان دبونو === */"

OVERRIDE = u"""

/* === ألوان دبونو === */
/* نفس ألوان تيشيرت البولو المستخدمة في المتجر، عشان بوابة العميل
   جوه ERPNext متبقاش بلون تاني. */
$primary:        #2E8F9C;
$secondary:      #343A40;
$brand-graphite: #343A40;
$brand-teal:     #2E8F9C;
$brand-teal-lt:  #4FB3C0;
$brand-ink:      #22272B;

:root {
  --dpono-graphite: #343A40;
  --dpono-teal:     #2E8F9C;
  --dpono-teal-lt:  #4FB3C0;
  --dpono-ink:      #22272B;
  --primary:        #2E8F9C;
  --primary-color:  #2E8F9C;
  --text-color:     #22272B;
}

.navbar, .navbar.navbar-light { background-color: #343A40 !important; }
.navbar .navbar-brand,
.navbar .nav-link { color: #ffffff !important; }
.navbar .nav-link:hover { color: #4FB3C0 !important; }

.btn-primary,
.btn-primary:focus {
  background-color: #2E8F9C !important;
  border-color: #2E8F9C !important;
  color: #fff !important;
}
.btn-primary:hover {
  background-color: #26757F !important;
  border-color: #26757F !important;
}

.web-footer, footer.web-footer { background-color: #2B3034 !important; color: #fff; }
.web-footer a { color: #9FD9E0 !important; }

/* التركواز على أبيض واطي في التباين للنص الصغير، فالروابط بتاخد نسخة أغمق. */
a { color: #1F6D78; }
a:hover { color: #2E8F9C; }

.page-head, .page-title, h1, h2, h3 { color: #22272B; }
.indicator-pill.blue, .indicator.blue { background: #E6F4F6; color: #1F6D78; }
"""


def execute():
	theme = frappe.get_doc("Website Theme", "D PONO")
	scss = theme.theme_scss or ""
	if MARK not in scss:
		theme.theme_scss = scss + OVERRIDE
		theme.flags.ignore_permissions = True
		theme.save()
		print("theme_scss extended")
	else:
		print("already applied")

	# A theme that is not the active one changes nothing.
	current = frappe.db.get_single_value("Website Settings", "website_theme")
	if current != "D PONO":
		frappe.db.set_single_value("Website Settings", "website_theme", "D PONO")
		print("activated D PONO (was %s)" % current)

	frappe.db.commit()
	frappe.clear_cache()
	print("ERP THEME READY")
