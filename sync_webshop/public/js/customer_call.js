// كارت العميل: زرار الاتصال + قسم مكالمات العميل بتسجيلاتها.
//
// التسجيلات بتترفع من السنترال أول ما المكالمة تخلص وبتتعلّق على المكالمة،
// فالموظف بيسمعها من هنا على طول من غير ما يفتح لوحة السنترال.

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

		render_calls(frm);
	},

	custom_call_button(frm) {
		frm.trigger("refresh");
		$(".btn-custom:contains('اتصل')").first().click();
	},
});

function render_calls(frm) {
	frappe.call({
		method: "sync_webshop.api.telephony_pbx.customer_calls",
		args: { customer: frm.doc.name },
		callback(r) {
			const calls = (r.message || []);
			if (!calls.length) return;

			const withRec = calls.filter((c) => c.recording_url).length;
			const title = withRec
				? __("مكالمات العميل ({0} منها متسجّلة)", [withRec])
				: __("مكالمات العميل");

			frm.dashboard.add_section(build_html(calls), title);
		},
	});
}

function build_html(calls) {
	const rows = calls.map((c) => {
		const when = c.start_time
			? frappe.datetime.str_to_user(c.start_time)
			: "—";

		const dir = c.type === "Incoming"
			? `<span style="color:var(--text-muted)">↙ ${frappe.utils.escape_html(c.type_label)}</span>`
			: `<span style="color:var(--text-muted)">↗ ${frappe.utils.escape_html(c.type_label)}</span>`;

		const secs = Math.round(c.duration || 0);
		const dur = secs
			? `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}`
			: "—";

		const answered = ["Completed", "In Progress"].includes(c.status);
		const badge = `<span class="indicator-pill ${answered ? "green" : "orange"}">
				${frappe.utils.escape_html(c.status_label)}</span>`;

		const player = c.recording_url
			? `<audio controls preload="none" style="height:32px;width:220px;vertical-align:middle"
					src="${frappe.utils.escape_html(c.recording_url)}"></audio>`
			: `<span style="color:var(--text-light);font-size:12px">مفيش تسجيل</span>`;

		return `<tr>
			<td style="white-space:nowrap">${frappe.utils.escape_html(when)}</td>
			<td>${dir}</td>
			<td style="font-variant-numeric:tabular-nums">${frappe.utils.escape_html(dur)}</td>
			<td>${badge}</td>
			<td>${player}</td>
			<td><a href="/app/call-log/${encodeURIComponent(c.name)}">فتح</a></td>
		</tr>`;
	}).join("");

	return `<div style="overflow-x:auto">
		<table class="table table-borderless" style="margin:0;font-size:13px">
			<thead><tr style="color:var(--text-muted);font-size:12px">
				<th>الوقت</th><th>الاتجاه</th><th>المدة</th>
				<th>الحالة</th><th>التسجيل</th><th></th>
			</tr></thead>
			<tbody>${rows}</tbody>
		</table>
	</div>`;
}
