# -*- coding: utf-8 -*-
"""
Customer segmentation from purchase history — RFM.

Three numbers per customer, all from their own orders:
  Recency   — days since the last order
  Frequency — how many orders
  Monetary  — total spent

Each is scored 1–5 against the rest of the customer base, then a short set of
readable rules turns the scores into a segment. Nothing here uses age, gender,
location or anything else about the person — only what they bought and when.
The rules are plain thresholds on purpose: the owner can check any customer's
segment by hand and see why.
"""
import frappe

SEGMENTS_AR = {
	"champions": "أبطال",
	"loyal": "أوفياء",
	"potential_loyalist": "على وشك الولاء",
	"new": "جدد",
	"promising": "واعدون",
	"need_attention": "محتاجين انتباه",
	"at_risk": "بدأوا يبعدوا",
	"cant_lose": "مهمين وبيضيعوا",
	"hibernating": "نايمين",
	"lost": "مفقودون",
}


def _score(value, breaks, reverse=False):
	"""1–5 against the quintile breaks. Recency is reversed: sooner is better."""
	for i, edge in enumerate(breaks):
		if value <= edge:
			return 5 - i if reverse else i + 1
	return 1 if reverse else 5


def _quintiles(values):
	"""Four cut points splitting the sorted values into five groups."""
	if not values:
		return [0, 0, 0, 0]
	ordered = sorted(values)
	n = len(ordered)
	return [ordered[min(int(n * q), n - 1)] for q in (0.2, 0.4, 0.6, 0.8)]


def _segment(r, f, m):
	"""Standard RFM rules, written out so they can be read and argued with."""
	if r >= 4 and f >= 4 and m >= 4:
		return "champions"
	if r >= 3 and f >= 4:
		return "loyal"
	if r >= 4 and f >= 2 and m >= 3:
		return "potential_loyalist"
	if r == 5 and f == 1:
		return "new"
	if r >= 4 and f <= 2:
		return "promising"
	if r == 3 and f == 3:
		return "need_attention"
	if r <= 2 and f >= 4 and m >= 4:
		return "cant_lose"
	if r <= 2 and f >= 3:
		return "at_risk"
	if r <= 2 and f <= 2 and m <= 2:
		return "lost"
	return "hibernating"


def compute(update_customers=True):
	"""
	Recalculate every customer's segment.

	Only submitted, non-cancelled sales orders count — drafts and cancellations
	are not purchases.
	"""
	rows = frappe.db.sql(
		"""
		SELECT
			so.customer,
			COUNT(*) AS frequency,
			SUM(so.base_grand_total) AS monetary,
			DATEDIFF(CURDATE(), MAX(so.transaction_date)) AS recency,
			MAX(so.transaction_date) AS last_order,
			MIN(so.transaction_date) AS first_order
		FROM `tabSales Order` so
		WHERE so.docstatus = 1
		GROUP BY so.customer
		""",
		as_dict=True,
	)
	if not rows:
		return {"customers": 0, "segments": {}}

	r_breaks = _quintiles([r.recency for r in rows])
	f_breaks = _quintiles([r.frequency for r in rows])
	m_breaks = _quintiles([float(r.monetary or 0) for r in rows])

	counts = {}
	for row in rows:
		r = _score(row.recency, r_breaks, reverse=True)
		f = _score(row.frequency, f_breaks)
		m = _score(float(row.monetary or 0), m_breaks)
		segment = _segment(r, f, m)
		counts[segment] = counts.get(segment, 0) + 1

		if update_customers:
			frappe.db.set_value(
				"Customer",
				row.customer,
				{
					"rfm_recency_days": row.recency,
					"rfm_frequency": row.frequency,
					"rfm_monetary": row.monetary,
					"rfm_score": f"{r}{f}{m}",
					"rfm_segment": SEGMENTS_AR.get(segment, segment),
					"rfm_last_order": row.last_order,
					"rfm_updated_on": frappe.utils.nowdate(),
				},
				update_modified=False,
			)

	if update_customers:
		frappe.db.commit()

	return {
		"customers": len(rows),
		"segments": {SEGMENTS_AR.get(k, k): v for k, v in sorted(counts.items(), key=lambda x: -x[1])},
		"breaks": {"recency_days": r_breaks, "frequency": f_breaks, "monetary": m_breaks},
	}


def daily_refresh():
	"""Scheduled nightly so the segments never go stale."""
	compute(update_customers=True)


@frappe.whitelist()
def refresh_now():
	"""Manual recalculation from the Desk."""
	frappe.only_for(("System Manager", "Sales Manager"))
	return compute(update_customers=True)
