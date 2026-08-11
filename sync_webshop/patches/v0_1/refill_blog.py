# -*- coding: utf-8 -*-
"""
Re-fetch the article bodies, one at a time, base64 encoded.

The first import shipped every post in one tab-separated dump and the bodies
came back clipped — WordPress content is full of newlines and quotes, and no
choice of delimiter survives that. Asking for one post at a time and encoding
the column removes the question entirely.
"""
import base64
import html
import re
import subprocess

import frappe

from sync_webshop.patches.v0_1.make_blog import localise


def wp(query):
	out = subprocess.run(
		["docker", "exec", "-e", "Q=" + query, "wp_db", "sh", "-c",
		 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 '
		 '-N --raw -e "$Q" wordpress'],
		capture_output=True, text=True)
	return out.stdout.strip()


def execute():
	# TO_BASE64 wraps every 76 characters, which would split one row across
	# several lines — strip the wrapping inside SQL so a row stays a row.
	pairs = wp("SELECT CONCAT(ID, '|', REPLACE(TO_BASE64(post_name), CHAR(10), '')) "
	           "FROM wp_posts WHERE post_type='post' AND post_status='publish';")

	from urllib.parse import unquote
	import unicodedata

	fixed, missing = [], []
	for line in pairs.split("\n"):
		if "|" not in line:
			continue
		post_id, b64name = line.strip().split("|", 1)
		slug = unicodedata.normalize(
			"NFC", unquote(base64.b64decode(b64name).decode("utf-8"))).strip()
		if not frappe.db.exists("Webshop Post", slug):
			missing.append(slug)
			continue

		encoded = wp("SELECT TO_BASE64(post_content) FROM wp_posts WHERE ID=%s;" % post_id)
		encoded = "".join(encoded.split())
		if not encoded:
			continue
		body = base64.b64decode(encoded).decode("utf-8", "replace")
		body = localise(body)

		plain = html.unescape(re.sub(r"<[^>]+>", " ", body))
		words = len(plain.split())
		excerpt = re.sub(r"\s+", " ", plain).strip()[:180]

		doc = frappe.get_doc("Webshop Post", slug)
		doc.content_ar = body
		doc.reading_minutes = max(1, int(round(words / 180.0)))
		if not doc.excerpt_ar or len(doc.excerpt_ar) < 60:
			doc.excerpt_ar = excerpt
			doc.meta_description_ar = excerpt[:160]
		doc.flags.ignore_permissions = True
		doc.save()
		fixed.append((slug, len(body), words))

	frappe.db.commit()
	frappe.clear_cache()
	print("FIXED=%d MISSING=%d" % (len(fixed), len(missing)))
	for slug, size, words in fixed:
		print("  %-42s %6d chars  %4d words" % (slug[:42], size, words))
