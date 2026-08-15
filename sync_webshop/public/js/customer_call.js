// زرار الاتصال على كارت العميل — السنترال بيرن على تليفونك الأول وبعدين يوصلك بالعميل
frappe.ui.form.on("Customer", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("📞 اتصل بالعميل"), () => {
			const number = frm.doc.custom_mobile_phone || frm.doc.mobile_no || frm.doc.phone;
			if (!number) {
				frappe.msgprint(__("مفيش رقم موبايل على كارت العميل ده"));
				return;
			}
			frappe.confirm(
				__("هيرن على تليفونك الأول، وأول ما ترد هيوصلك بـ {0}", [number]),
				() => {
					frappe.call({
						method: "sync_webshop.api.telephony_pbx.request_call",
						args: { to_number: number, customer: frm.doc.name },
						freeze: true,
						freeze_message: __("بيتصل…"),
						callback(r) {
							if (r.message && r.message.ok) {
								frappe.show_alert({
									message: __("التليفون بتاعك هيرن دلوقتي 📞"),
									indicator: "green",
								}, 7);
							}
						},
					});
				}
			);
		});
	},

	custom_call_button(frm) {
		frm.trigger("refresh");
		$(".btn-custom:contains('اتصل')").first().click();
	},
});
