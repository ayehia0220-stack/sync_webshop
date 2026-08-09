# Sync Webshop

Headless webshop backend for ERPNext. This app never renders HTML itself -
the storefront is a separate React app that talks to this app's REST API.

The same version of this app is installed on every server. Everything that
differs per server (theme, colors, logo, quotes, banners, testimonials,
featured categories) lives in three Single doctypes, editable from the
Frappe desk by a non-technical admin:

- **Webshop Theme Settings** - logo, favicon, colors, fonts, layout style
- **Webshop Content Settings** - site name, taglines, about/footer text,
  banners, featured categories, testimonials (English + Arabic)
- **Webshop API Settings** - which frontend domain(s) may call the API,
  and whether the catalog is readable by guests

## Status

- [x] Step 1 - Architecture & doctype design
- [x] Step 2 - App scaffold + doctypes (this commit)
- [ ] Step 3 - Backend APIs (theme, content, catalog)
- [ ] Step 4 - Checkout API (Sales Order creation)
- [ ] Step 5 - React app scaffold
- [ ] Step 6 - Landing page
- [ ] Step 7 - Product listing + detail pages
- [ ] Step 8 - Cart + checkout flow
- [ ] Step 9 - Customer dashboard
- [ ] Step 10 - Multi-server packaging guide

## Installation (on erp1.dpono.com or any other bench)

```bash
bench get-app sync_webshop <git-remote-url-or-local-path>
bench --site erp1.dpono.com install-app sync_webshop
bench --site erp1.dpono.com migrate
```

After install, go to the Frappe desk and open:
- Webshop Theme Settings
- Webshop Content Settings
- Webshop API Settings

to configure this server's look, text, and allowed frontend domain.
