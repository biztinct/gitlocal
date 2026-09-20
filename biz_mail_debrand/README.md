# biz_mail_debrand

Portable, brand-agnostic debranding for **outgoing email** on Odoo 19 CE.
Complements the UI-focused stack (biz_debrand / web_debranding /
mail_debranding): those never touch email **subjects**, the bare word
"Odoo" in bodies, stored `mail.template` data, or the periodic digest.

## What it does

1. **Send-time catch-all** (`mail.mail`):
   - `_prepare_outgoing_body()` — rewrites Odoo words/links in every
     outgoing body (on top of mail_debranding's "Powered by" stripping).
   - `_prepare_outgoing_list()` — same for `subject` and `email_from`,
     and drops informational `X-Odoo-*` SMTP headers.
2. **Stored-data scrub** (on install and every upgrade, idempotent):
   - Every `mail.template` `name`/`subject`/`body_html` (all installed
     languages) and `email_from` (fixes stock `noreply@odoo.com`).
   - Renames `digest.digest` records, then **disables** digests: records
     deactivated, `digest.default_digest_emails` off, digest cron off.
     Opt out by setting config parameter
     `biz_mail_debrand.disable_digest = 0` before install/upgrade.

## Brand resolution (no hardcoded name)

First non-empty config parameter wins:

| Value   | Order |
|---------|-------|
| name    | `biz_mail_debrand.brand_name` → `biz_debrand.brand_name` → `web_debranding.new_name` → company name |
| website | `biz_mail_debrand.brand_website` → `biz_debrand.brand_website` → `web_debranding.new_website` → `web.base.url` |
| docs    | `web_debranding.new_documentation_website` → website |

## Safety rails

- `/odoo/...` backend deep-link paths are **never** rewritten (stock
  templates embed them; biz_deroute redirects them for visitors).
- `odoo.example.com`-style foreign subdomains and code tokens
  (`odoo =`, `odoo[`, `odooSMTH`, `.odoo`) are left alone
  (regex derived from web_debranding's proven `debrand()`).

Depends only on `mail` + `digest` — drops into any Odoo 19 database.
