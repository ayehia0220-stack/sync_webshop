# -*- coding: utf-8 -*-
"""زراير الصفحة: «حدّث دلوقتي» في القائمة، و«فعّل/اقفل» جوّه الورك فلو."""

import frappe

LIST_JS = """
frappe.listview_settings['Automation Job'] = {
	add_fields: ['health', 'is_active'],
	get_indicator: function (doc) {
		const colours = {
			'شغال': 'green', 'ميت': 'red',
			'فيه أخطاء': 'orange', 'متوقف': 'gray',
		};
		return [doc.health, colours[doc.health] || 'gray', 'health,=,' + doc.health];
	},
	onload: function (listview) {
		listview.page.add_inner_button(__('حدّث دلوقتي'), function () {
			frappe.dom.freeze(__('بنسأل n8n...'));
			frappe.call({
				method: 'sync_webshop.api.automation.sync_workflows',
				callback: function (r) {
					frappe.dom.unfreeze();
					const d = (r && r.message) || {};
					if (d.note) {
						frappe.msgprint({ title: __('فيه مشكلة'), indicator: 'red',
							message: d.note });
					} else {
						frappe.show_alert({ message: __('اتحدّثت — ') + d.count,
							indicator: 'green' });
					}
					listview.refresh();
				},
			});
		});
	},
};
"""

FORM_JS = """
frappe.ui.form.on('Automation Job', {
	refresh: function (frm) {
		if (frm.doc.open_url) {
			frm.add_custom_button(__('افتحها'), function () {
				window.open(frm.doc.open_url, '_blank');
			});
		}
		if (frm.doc.source !== 'n8n') { return; }

		const label = frm.doc.is_active ? __('اقفلها') : __('فعّلها');
		frm.add_custom_button(label, function () {
			frappe.confirm(__('متأكد؟'), function () {
				frappe.call({
					method: 'sync_webshop.api.automation.set_active',
					args: { job: frm.doc.name, active: frm.doc.is_active ? 0 : 1 },
					freeze: true,
					callback: function () { frm.reload_doc(); },
				});
			});
		});
	},
});
"""

SCRIPTS = [
	("الأتمتة — قائمة", "List", LIST_JS),
	("الأتمتة — زراير", "Form", FORM_JS),
]


def execute():
	for name, view, script in SCRIPTS:
		payload = {"dt": "Automation Job", "view": view,
		           "script_type": "Client", "enabled": 1, "script": script}
		if frappe.db.exists("Client Script", name):
			doc = frappe.get_doc("Client Script", name)
			doc.update(payload)
			doc.save(ignore_permissions=True)
			print("  ↻ %s" % name)
		else:
			frappe.get_doc(dict(doctype="Client Script", name=name,
			                    **payload)).insert(ignore_permissions=True)
			print("  ✓ %s" % name)
	frappe.db.commit()
	print("\n✓ الزراير جاهزة")
