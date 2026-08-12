# Debranding audit — remaining user-visible "Odoo" on live (payobook.com)

> **STATUS 2026-08-12: FIXED AND DEPLOYED.** See §5 for what shipped, how each
> seam was verified live, and the three residual items that were deliberately
> left alone. Sections 1–4 are the original audit, kept as the record of what
> was wrong and why.


**Date:** 2026-08-12 · **Target:** live server `Payobook19v2`, DB `payobook`, Odoo 19 CE
**Scope:** *visible* branding only — labels, titles, tooltips, notifications, stored content.
Code identifiers, module technical names, `odoo.` JS namespace, file paths, config-parameter
**keys**, and licence headers are explicitly **out of scope**.

**Method:** (1) static scan of every **installed** module's source on the live server
(`/odoo/odoo-server/addons`, `/odoo/odoo-server/odoo/addons`, `/odoo/custom/addons`) for
translated strings, field labels/help, XML attributes and QWeb text containing the word
"Odoo"; (2) full sweep of every `text`/`varchar`/`jsonb` column in the live database;
(3) live browser verification on https://payobook.com as a logged-in backend user.

---

## 1. Root cause — why the existing debranding modules miss these

`web_debranding` (the OPL engine that `biz_debrand` orchestrates) was **stubbed out during the
Odoo 19 port**. Four of its rewrite paths are dead:

| File | State |
|---|---|
| `web_debranding/translate.py` | Whole module is a no-op — *"Odoo 19 compatibility: Translation internals have changed, monkey-patching disabled"*. Python `_()` is **never** rewritten. |
| `web_debranding/static/src/js/translation.js` | `debrandTranslation()` is an empty stub — *"Odoo 19: translatedTerms is no longer exported"*. Client-side `_t()` is **never** rewritten. |
| `web_debranding/views.xml` | *"Odoo 19: Most template inherits removed due to changed structure"* — only the `<title>` xpath survives. QWeb template debranding is gone. |
| `web_debranding/models/ir_ui_view.py::_create_debranding_views` | `return True` — no-op. |

The one translation hook that *does* still run, `ir_http._get_translations_for_webclient`, rewrites
entries **inside the translation catalogue**. The live UI runs in **`en_US`** (verified:
`get_session_info` → `lang: "en_US"`), and Odoo serves *no catalogue entries for the source
language* — `_t("Install Odoo")` returns its own msgid. **So in English, every hardcoded
`_t()`/`_()` string containing "Odoo" passes through untouched.**

`biz_theme` already hit and documented exactly this for error-dialog titles
(`biz_theme/static/src/js/biz_error_dialogs.js:204-228` — *"web_debranding cannot reach these —
source-language terms aren't in the translation catalog"*). That component-level strip is the
**working precedent** for the fix.

### What still works (do not touch)
Verified live via RPC — these paths are healthy:
- Field labels, help and selection values → `In Payobook`, *"The model (Payobook Document Kind)…"*, `Payobook Enterprise Edition License v1.0`. ✔
- Backend **view arch** (`base.get_view` / `get_combined_arch` → `debrand()`), so `string=`/`help=` in view XML is rewritten. ✔
- Browser tab title → `Payobook - Dashboard`. ✔
- `partner_root` renamed to a neutral name; user-menu Documentation / Support / Odoo Account items removed. ✔
- Outgoing email (`biz_mail_debrand` send-time rewrite). ✔
- Login page and public website body text. ✔

---

## 2. Findings

Severity: **P1** = seen by ordinary backend users in normal use · **P2** = seen by
admins / in specific screens · **P3** = view-source, demo data, or rarely reached.

### P1 — the screenshot, and its neighbours

| # | What the user sees | Where it comes from | Notes |
|---|---|---|---|
| 1 | **"Install Odoo"** in the Messages systray dropdown | `mail/static/src/core/web/messaging_menu_patch.js:76` — `_t("Install Odoo")` | **Confirmed live.** Hardcoded JS string. |
| 2 | **PWA manifest name = `"Odoo"`** — the name Chrome shows in the install prompt and on the installed app icon | `web/controllers/webmanifest.py:44` — `get_param('web.web_app_name', 'Odoo')`; the parameter is **unset** in this DB | **Confirmed live** (`GET /web/manifest.webmanifest` → `{"name": "Odoo", …}`). Also ships Odoo's purple `#714B67` theme/background colour, `/web/static/img/odoo-icon-*.png` icons and `scope: "/odoo"` (which also disagrees with `biz_deroute`'s `/bizapp`). |
| 3 | **"Hello, Odoo's chat helps employees collaborate efficiently…"** — the bot's welcome message, shown in the same dropdown and in Discuss | `mail_bot/models/res_users.py:39` (`_()`) → already **written into `mail_message.body`** for 5+ users | **Confirmed live in the same dropdown as the screenshot.** Both the source string and the stored copies need fixing. |
| 4 | Chat named **"Demo User, OdooBot"** in Discuss / chat list | `discuss_channel.name` — 5 stored rows | Stale stored names; the partner itself is already renamed. |
| 5 | Scheduled activities reading **"New Allocation Request created by OdooBot: …"** | `mail_activity.note` — 23 rows on `hr.leave` / `hr.leave.allocation` | This is the "scheduled activities" surface you asked about. |
| 6 | Browser notification toasts: **"Odoo will send notifications on this device!"** / **"Odoo will not send notifications on this device."** | `mail/static/src/core/common/notification_permission_service.js:69,74` | Fires from the "Turn on notifications → Enable" button in the very same dropdown. |
| 7 | **`Odoo Session Expired` / "Your Odoo session expired…"** | `web/static/src/public/error_notifications.js:16-17` | The `error_dialogs` family is already fixed by `biz_theme`, but this **public/frontend** notification pair is a separate file and is **not** covered. |
| 8 | Camera permission prompt: **"Odoo needs your authorization first."** | `web/static/src/barcode/barcode_video_scanner.js:74` | Any barcode/QR scan. |
| 9 | Offline splash: **"Check your network connection and come back here. Odoo will load as soon as you're back online."** + `alt="Odoo logo"` | `web/views/webclient_templates.xml:365-367` | Shown whenever the connection drops. |
| 10 | Error messages surfaced as dialogs, e.g. *"Odoo is unable to merge the generated PDFs."*, *"Odoo is currently processing another module operation."*, *"…this might be a multi-company issue. Switching company may help — in Odoo, not in real life!"* | `base/models/ir_actions_report.py:792,811,1090`; `base/models/ir_module.py:614,621,631`; `base/models/ir_rule.py:246` | Python `_()` — **completely uncovered** since `translate.py` is disabled. Batch payslip PDF printing hits the first one. |

### P2 — admin / settings screens

| # | What the user sees | Where |
|---|---|---|
| 11 | **Apps list module names**: `Odoo 19 HR Payroll`, `Odoo 16 HR Payroll Accounting`, `OdooBot`, `OdooBot - HR`, `Remove Odoo Branding from Portal`, `Remove Odoo Branding from Website`, `Remove odoo.com Bindings`, `Mail Debrand`, plus our own `biz_*` summaries | `ir_module_module.shortdesc` / `.summary` — **12 installed modules**. Record *data*, not field metadata, so the `fields_get` debrand does not reach it. **Confirmed live via RPC.** |
| 12 | Apps → module detail page long description | `ir_module_module.description` — 111 rows (24 in installed modules incl. `account`, `mail`, `web`, `base`, `om_hr_payroll`, `pb_explorer`, `pb_sidebar`, `pb_login_language`, `pb_hr_payroll_demand`, `biz_theme`, `biz_deroute`) |
| 13 | Settings → General Settings help bubbles: *"This name will be used for the application when Odoo is installed through the browser"* (with placeholder literally **`Odoo`**), *"API Keys allow your users to access Odoo with external tools…"*, *"When populating your address book, Odoo provides a list of matching companies…"* | `base_setup/views/res_config_settings_views.xml:110,124,136,137` — the `help=` attributes *are* covered by the arch debrand, but the **`placeholder="Odoo"`** is a value, not a label, and reads as brand text |
| 14 | Settings help in other apps: *"Allow Users to Check in/out from Odoo"* (Attendance), *"Make and receive calls from Odoo with Ringover's dialer"* (CRM), *"…integrated into Odoo through Stripe Issuing"* (Expenses), page title **"Odoo IAP"** | `hr_attendance`, `crm`, `hr_expense`, `iap` config views — covered by arch debrand at render time; listed for completeness/verification |
| 15 | Empty-state "no content" help texts on 18 actions: *"Odoo helps you keep track of your sales pipeline…"*, *"The configuration wizards are used to help you configure a new instance of Odoo…"*, *"Views allows you to personalize each view of Odoo…"*, *"Manage and customize the items available and displayed in your Odoo system menu…"* | `ir_act_window.help` — 18 rows. `ir_actions.act_window.read()` **is** patched to rewrite `help`, but only when `help` is in the requested field list; the stored data is still dirty and leaks anywhere it is read raw |
| 16 | Security group **"Receive notifications in Odoo"** (Settings → Users → Groups) | `res_groups.name` id 16 |
| 17 | Report action **"Invoice report generated by Odoo"**; document body *"Invoice generated by Odoo"* / *"Generated by Odoo"* in e-invoice XML | `ir_act_report_xml` id 1214; `account_edi_ubl_cii` templates + `account_edi_ubl.py:3918,3923` — appears in **files sent to customers/tax authorities** |
| 18 | Digest emails: subject **"Payobook: Your Odoo Periodic Digest"** and 27 tips mentioning Odoo | `digest_tip` (27 rows), `mail_message.subject` | `biz_mail_debrand` disables the digest cron *and* rewrites at send time, so this is dormant — but the records are still dirty and visible in Settings → Technical → Digest |
| 19 | Website settings → Social links pointing at Odoo's own accounts (`facebook.com/Odoo`, `twitter.com/Odoo`, `linkedin.com/company/odoo`, `github.com/odoo`, `instagram…/odoo/`, `tiktok.com/@odoo`) — **rendered in the public site footer** | `website.social_*` — both website records |
| 20 | Third-party app links: **"Third-Party Apps" → `apps.odoo.com/apps/modules`**, **"Theme Store" → `apps.odoo.com/apps/themes`** | `ir_act_url` ids 40, 41 |
| 21 | Spreadsheet: chart types listed as **"Odoo Bar Chart", "Odoo Line Chart", … "Odoo Funnel Chart"** (11 strings) and panel title **"Odoo Spreadsheet"** | `spreadsheet/static/src/chart/plugins/odoo_chart_core_plugin.js:15-26`, `spreadsheet/static/src/hooks.js:144,174` |
| 22 | Import wizard column header **"Odoo Field"** | `base_import/static/src/import_data_content/import_data_content.xml:37` |
| 23 | Scoped-app install page: heading `Odoo` + link **"Odoo S.A."** | `web/static/src/core/install_scoped_app/install_scoped_app.xml:24` — this is the page the "Install" button in the screenshot leads to |
| 24 | Settings → Technical → Views: four views literally named `Odoo Information`, `Show Odoo Information`, `Odoo Menu`, `Remove Odoo Promotional Link`; asset `Odoo Menu 000 SCSS` | `ir_ui_view.name` (4), `ir_asset.name` (1) |
| 25 | User tours pointing at `/odoo` (7 tours) — starting a tour navigates the user off `/bizapp` | `web_tour_tour.url` |

### P3 — low priority / demo data / view-source

| # | Item | Where |
|---|---|---|
| 26 | `<meta name="generator" content="Odoo">` on every public page; `title="Go to your Odoo Apps"` on the frontend→backend button | `website` / `portal` templates. Not a rendered label but visible in view-source and SEO tools; the `title=` **is** a hover tooltip. |
| 27 | `alt="Odoo"` / `alt="Odoo Logo"` on logos (web client, portal, attendance kiosk) — surfaces to screen readers and when images fail | `web/views/webclient_templates.xml:92,365`, `portal/views/portal_templates.xml:283`, `hr_attendance/.../public_kiosk_app.xml:134,139` |
| 28 | Demo/sample records: skill **"Odoo"**, résumé line **"Odoo SA"**, employee *Rachel Perry* with `work_email = jod@odoo.com`, 2 `hr_job` descriptions, `Bank of odoo` on the statement report sample, CRM demo mail templates | `hr_skill`, `hr_resume_line`, `hr_employee`/`res_partner`, `hr_job`, `account/views/report_statement.xml:116` |
| 29 | Product/skill placeholders: `e.g. Odoo Inc.`, `e.g. Odoo Enterprise Subscription` | `hr_skills/views/hr_views.xml:51`, `product/views/product_views.xml:339` |
| 30 | Onboarding/product tour strings: *"Odoo will save all modifications as you navigate"* (CRM, Project, Expenses tours) | `*/static/src/js/tours/*.js` |
| 31 | Website snippet copy shipped with the theme: *"50,000+ companies run Odoo to grow their businesses."* (5 snippets), *"Happy Odoo Anniversary!"* countdown default, *"Your changes might be lost during future Odoo upgrade."* | `website/views/snippets/*`, `website/static/src/builder/…` — only appears if an editor drags those snippets in |
| 32 | `mail_message.email_from` / `reply_to` = `"OdooBot" <odoobot@example.com>` on **8,490** historical messages (and `odoobot@example.com` on 6,264 more that already say "Payobook") | Stored history. Not rendered in chatter (author comes from `author_id`), and `biz_mail_debrand` rewrites at send time — but it is in the data and visible in Technical → Emails. |
| 33 | `pb_learn` content that *deliberately* names Odoo when describing legacy salary structures (3 records) | `pb_learn/data/learn_stations.xml:305`, `learn_columns.xml:365`, `learn_screens.xml:103` — **intentional**; needs a product decision, not a blind rewrite |
| 34 | Our own module summaries that contain "Odoo" by design (`biz_debrand`, `biz_deroute`, `biz_mail_debrand`, `biz_theme`) | These are only visible in the Apps list; covered by finding #11 |

### Explicitly checked and CLEAN ✔
- **Cron jobs** — `ir_cron` / `ir_act_server.name`: **0** matches. (You asked specifically; they're clean.)
- **Menu items** — `ir_ui_menu.name`: 0 matches.
- **Activity types** — `mail_activity_type`: 0 matches.
- **Company name**, `res_partner.name`, `ir_filters`, `ir_model.name`: 0 matches.
- Login page, browser tab title, user menu, field labels/help/selections, backend view `string=`/`help=`.

---

## 3. Recommended fix shape (for discussion — nothing changed yet)

Three mechanisms, in priority order. All of it belongs in **`biz_debrand`** (the portable layer),
so it survives module upgrades and travels to every SaaS tenant.

1. **Component/registry-level strips for JS `_t()` strings** — the `biz_theme` error-dialog
   pattern, applied to the messaging menu, notification-permission service, public error
   notifications, barcode scanner and spreadsheet chart names. Patch the *component*, not the
   translation layer, so it is language-independent. Covers #1, #6, #7, #8, #21.
2. **A data-scrub function run on install/upgrade** (extend the existing
   `res.config.settings._biz_debrand_apply_brand` hook that `data/apply_brand.xml` already
   calls). It would set `web.web_app_name`, `web.web_app_theme_color`/icons, and rewrite the
   stored rows: `ir_module_module.shortdesc/summary/description`, `ir_act_window.help`,
   `res_groups.name`, `digest_tip`, `discuss_channel.name`, `mail_activity.note`,
   `mail_message.body`, `website.social_*`, `ir_act_url.url`, `web_tour_tour.url`,
   `ir_ui_view.name`, `ir_act_report_xml.name`. Covers #2-5, #11, #12, #15-20, #24, #25.
   Idempotent, brand read from the config parameters, and re-run on every upgrade so
   reinstalled core data is re-scrubbed.
3. **Restore a Python `_()` catch-all for Odoo 19** — the highest-leverage single item, since it
   is the mechanism that was silently disabled. Rather than resurrect the removed
   `_get_translation` monkey-patch, wrap the two places user-facing Python strings actually
   reach the client: exception serialisation in `ir_http._handle_exception` / the JSON-RPC error
   payload, and `ir.actions.act_window.help`. Covers #10 and anything similar we have not
   enumerated.

**Deliberately excluded from any automated rewrite:** the `pb_learn` legacy-structure copy (#33),
`odoo.com`-hosted URLs that must keep working, and everything at code level.

**Deploy note:** JS/SCSS changes need the prod asset-bundle cache cleared
(`DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'`) or a real `-u`, per the
deploy ledger.

---

## 4. Verification gaps

- Admin-only screens (Settings → General Settings, Apps list rendering) were verified from
  **source and database**, not in the browser — the `ash@biztinct.com / admin1234` password no
  longer works on live, so the live session ran as `demo@payobook.com`. Worth a re-check with a
  working admin login before/after any fix.
- The scan covers **installed** modules only. Uninstalled modules in the addons path were not
  scanned; installing any new app can reintroduce leaks, which is the argument for the
  upgrade-time re-scrub in mechanism 2.

---

## 5. What shipped (2026-08-12)

All of it lives in **`biz_debrand`** (now `19.0.2.2.0`), so it survives module upgrades and
travels to every SaaS tenant. Nothing was patched in Odoo core.

### Five seams, not thirty patches

| Seam | File | Covers |
|---|---|---|
| Python `_()` / `_lt()` / `env._()` | `models/translate_patch.py` | Wraps `odoo.tools.translate.get_translation`, the one funnel all three idioms reach. **Both** bindings are patched — `odoo.orm.environments` does `from … import get_translation` (environments.py:21), so patching only the module attribute would have missed every `self.env._(...)` in core. The vendor name is stripped from the *template*, never from interpolated arguments, so a record whose own name contains the word is left alone. |
| JS `_t()` | `static/src/js/biz_debrand_runtime.js` | Patches `TranslatedString.prototype.valueOf` — language-independent, and it covers modules installed later. |
| OWL templates | same file, `registerTemplateProcessor` | Prose and prose-attributes inside `static/src/xml/**`. |
| Server-rendered QWeb | `models/ir_ui_view.py` | `_get_view_etrees` — the single entry point `ir.qweb._preload_trees` uses (ir_qweb.py:1229), and the reason website/portal/report templates escaped `web_debranding`'s `get_combined_arch` patch. Sits before the compile cache, so it costs once per template per registry. |
| Apps list | `models/ir_module_module.py` | `_read_format`, **not** `read` — Odoo 19's `search_read` calls `_read_format` directly (orm/models.py:5785). A `read()` override was written first and silently missed the Apps kanban; the live probe caught it. |

Plus `controllers/webmanifest.py` (PWA name, colours, icon, and `scope`/`start_url` follow
`biz_deroute`'s prefix), `views/brand_layout.xml` (publishes the brand to the browser
synchronously via `web.layout`, so the JS seams work on the first render and on frontend pages
too), and `models/scrub.py` (one-off rewrite of content already materialised into rows, re-run
on every install/upgrade/save).

### Safety rails
The rewrite rules are in one place (`models/brand.py`), mirrored character-for-character in JS,
and covered by `tests/test_rewrite.py`:
- prose vs **URLs** are separate rules — URLs only get the domain rewrite, so `/odoo/action-1`,
  `odoocdn.com` assets and `apps.odoo.com` keep working;
- `t-*` attributes are never touched (they are QWeb expressions);
- `<script> <style> <code> <pre> <samp> <kbd>` text is opaque — help panels quote real Python;
- the generic word rule excludes `odoo.x`, `odoo[`, `odoo =`, `@odoo-module`, `odoo-bin`, `/odoo/`.

### Verified live on payobook.com
- `_t("Install Odoo")` → **"Install Payobook"**; `odoo.define('x')` and `/odoo/action-1` unchanged.
- PWA manifest: `name: "Payobook"`, `scope: "/bizapp"`, brand colour, brand icon.
- Messaging systray (the reported screenshot): **zero** vendor references.
- `/`, `/web/login`, `/bizapp`: zero visible vendor text or prose-attributes; `<meta generator>` = `Payobook`.
- Apps list: `mail_bot` reads "Payobook" / "Add Payobook in discussions".
- Python: "Odoo is unable to merge the generated PDFs." → "Payobook is unable to…"; both bindings confirmed patched.
- Stored data re-scan: every target **0** except the two noted below.
- Field labels/help/selections still correct (`In Payobook`) — no regression.

### Deliberately left alone
1. **`odoocdn.com` image URLs** in 27 digest tips — asset URLs; rewriting them breaks the images.
   The tip *names and text* are clean.
2. **`/odoo/…` routes** — routing, not prose. `biz_deroute` 301s them, and stored deep links in
   chatter/mail templates were repointed at `/bizapp`.
3. **`apps.odoo.com`** — a vendor subdomain that cannot be half-rewritten into a host that
   exists. The two menu items that navigated there ("Third-Party Apps", "Theme Store") are
   archived instead.

### Still unverified
Admin-only screens (Settings → General Settings, the Apps kanban rendering) were checked by RPC
and database, not visually — the live admin password is not available to this session. Worth one
pass with a working admin login.
