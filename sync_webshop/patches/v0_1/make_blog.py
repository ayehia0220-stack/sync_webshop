# -*- coding: utf-8 -*-
"""
The blog, carried over from WordPress with its addresses intact.

dpono.com used /%postname%/, so every article already has a URL that Google has
indexed and other sites link to. Those URLs are the asset here — the writing can
be re-typed, the ranking cannot. So the slug is copied verbatim and the new site
answers on the same path.

Images inside the articles are pulled out of the WordPress container and stored
locally; once the old site is switched off, any src still pointing at dpono.com
would render as a broken image.
"""
import base64
import html
import os
import re
import subprocess
import unicodedata
from urllib.parse import unquote

import frappe

BASE = "/home/frappe/frappe-bench-15/sites/erp1.dpono.com/public"


def field(fieldname, label, fieldtype, idx, **kw):
	d = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, "idx": idx}
	d.update(kw)
	return d


def wp(query):
	out = subprocess.run(
		["docker", "exec", "-e", "Q=" + query, "wp_db", "sh", "-c",
		 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 '
		 '-N --raw -e "$Q" wordpress'],
		capture_output=True, text=True)
	return out.stdout


def read_upload(rel):
	out = subprocess.run(
		["docker", "exec", "wp_app", "sh", "-c",
		 "base64 -w0 '/var/www/html/wp-content/uploads/%s' 2>/dev/null" % rel],
		capture_output=True, text=True)
	data = out.stdout.strip()
	return base64.b64decode(data) if data else None


def store(rel):
	"""Copy one upload into the site's files folder, return its new URL."""
	blob = read_upload(rel)
	if not blob:
		return None
	name = "blog-" + re.sub(r"[^\w.\-]", "-", os.path.basename(rel))
	target = BASE + "/files/" + name
	if not os.path.exists(target):
		with open(target, "wb") as fh:
			fh.write(blob)
	if not frappe.db.exists("File", {"file_name": name}):
		frappe.get_doc({
			"doctype": "File", "file_name": name, "file_url": "/files/" + name,
			"is_private": 0, "file_size": len(blob),
		}).insert(ignore_permissions=True)
	return "/files/" + name


def localise(content):
	"""Point every dpono.com upload in the article at our own copy."""
	seen = {}

	def swap(match):
		url = match.group(0)
		rel = match.group(1)
		if url not in seen:
			seen[url] = store(rel) or url
		return seen[url]

	return re.sub(
		r"https?://(?:www\.)?dpono\.com/wp-content/uploads/([^\s\"'<>)]+)", swap, content)


def make_doctype():
	if frappe.db.exists("DocType", "Webshop Post"):
		print("  exists: Webshop Post")
		return
	frappe.conf["developer_mode"] = 1
	frappe.flags.in_migrate = True
	try:
		doc = frappe.get_doc({
			"doctype": "DocType", "name": "Webshop Post", "module": "Sync Webshop",
			"custom": 0, "istable": 0, "autoname": "field:slug",
			"title_field": "title_ar", "track_changes": 0,
			"fields": [
				field("title_ar", "العنوان (عربي)", "Data", 1, reqd=1, in_list_view=1),
				field("slug", "الرابط", "Data", 2, reqd=1, unique=1,
				      description="ده اللي بيظهر في العنوان. متغيّروش للمقالات القديمة — "
				                  "جوجل عارفها بالرابط ده."),
				field("cb1", "", "Column Break", 3),
				field("published", "منشورة", "Check", 4, default="1", in_list_view=1),
				field("published_on", "تاريخ النشر", "Datetime", 5, in_list_view=1),
				field("reading_minutes", "وقت القراءة (دقيقة)", "Int", 6, read_only=1),
				field("sec_cover", "الصورة", "Section Break", 7),
				field("cover_image", "صورة الغلاف", "Attach Image", 8),
				field("excerpt_ar", "مقدمة قصيرة", "Small Text", 9,
				      description="بتظهر في قائمة التدوينات وفي نتائج البحث."),
				field("sec_body", "المحتوى", "Section Break", 10),
				field("content_ar", "المقال", "Text Editor", 11),
				field("sec_en", "English (اختياري)", "Section Break", 12, collapsible=1),
				field("title_en", "Title", "Data", 13),
				field("content_en", "Body", "Text Editor", 14),
				field("sec_seo", "SEO", "Section Break", 15, collapsible=1),
				field("meta_description_ar", "وصف الميتا", "Small Text", 16),
				field("legacy_url", "الرابط القديم على dpono.com", "Data", 17, read_only=1),
			],
			"permissions": [
				{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
				{"role": "All", "read": 1},
			],
		})
		doc.flags.ignore_permissions = True
		doc.insert()
		print("  created: Webshop Post")
	finally:
		frappe.conf["developer_mode"] = 0
		frappe.flags.in_migrate = False


def execute():
	make_doctype()

	rows = wp(
		"SELECT p.ID, p.post_name, p.post_title, p.post_date, p.post_excerpt, "
		"IFNULL(f.meta_value,''), REPLACE(REPLACE(p.post_content, '\\t', ' '), '\\n', '~NL~') "
		"FROM wp_posts p "
		"LEFT JOIN wp_postmeta t ON t.post_id=p.ID AND t.meta_key='_thumbnail_id' "
		"LEFT JOIN wp_postmeta f ON f.post_id=CAST(t.meta_value AS UNSIGNED) "
		"  AND f.meta_key='_wp_attached_file' "
		"WHERE p.post_type='post' AND p.post_status='publish' ORDER BY p.post_date;")

	made, skipped = [], []
	for line in rows.split("\n"):
		parts = line.split("\t")
		if len(parts) < 7:
			continue
		_id, post_name, title, date, excerpt, thumb, content = parts[:7]
		content = content.replace("~NL~", "\n")

		slug = unquote(post_name)
		slug = unicodedata.normalize("NFC", slug).strip()
		if not slug or not title.strip():
			continue
		if frappe.db.exists("Webshop Post", slug):
			skipped.append(slug)
			continue

		body = localise(content)
		cover = store(thumb) if thumb else None
		if not excerpt.strip() or excerpt.strip() == "NULL":
			plain = html.unescape(re.sub(r"<[^>]+>", " ", body))
			excerpt = re.sub(r"\s+", " ", plain).strip()[:180]

		words = len(re.sub(r"<[^>]+>", " ", body).split())
		doc = frappe.get_doc({
			"doctype": "Webshop Post",
			"slug": slug,
			"title_ar": html.unescape(title).strip(),
			"content_ar": body,
			"excerpt_ar": html.unescape(excerpt).strip(),
			"cover_image": cover,
			"published": 1,
			"published_on": date if date != "NULL" else None,
			"reading_minutes": max(1, round(words / 180.0)),
			"meta_description_ar": html.unescape(excerpt).strip()[:160],
			"legacy_url": "https://dpono.com/" + slug + "/",
		})
		doc.flags.ignore_permissions = True
		doc.insert()
		made.append(slug)

	frappe.db.commit()
	frappe.clear_cache()
	print("IMPORTED=%d SKIPPED=%d" % (len(made), len(skipped)))
	for s in made:
		print("  + " + s)
