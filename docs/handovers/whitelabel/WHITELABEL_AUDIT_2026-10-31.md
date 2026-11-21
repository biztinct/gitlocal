# White-label audit — where "Payobook" still reaches a tenant (Rize), 2026-10-31

Status: AUDIT ONLY. No code changed. Owner to decide what each surface should show.

Tenant checked: `rize` (rize.payobook.com). Brand level on master `pb_tenant` row 3223 = `white`
("Their brand only"). Live params on rize: `biz_debrand.brand_name=Rize`,
`biz_debrand.product_name=Payobook`, `biz_debrand.powered_by=''`, `web.web_app_name=Rize`,
`biz_debrand.loader_logo_url=/rize_website/static/src/img/rize_logo.png`.

So the product rule IS on, and everything that passes a seam already reads "Rize". What follows is
what does NOT pass a seam. Live checks were done in the owner's own Chrome session on rize
(Ash Sohani, internal user) on 2026-10-31 17:50–18:00 AEDT.

## A. Confirmed LIVE on rize (seen on screen / in HTML)

| # | Where | Exact text | Source | Why it escapes |
|---|-------|------------|--------|----------------|
| A1 | Public site footer, every page (home, Open roles, Contact, 404) | `© Rize · Powered by Payobook` | `rize_website/views/frame_templates.xml:41` | hard-coded with `data-biz-brand="keep"` |
| A2 | Sign-in page + reset-password page, under the user chooser | `Powered by Payobook` | `rize_website/views/login_templates.xml:43` | same `keep` hatch |
| A3 | In-app left menu, expanded: brand block top-left | `P` badge, `Payobook` / `Payroll Suite` | `pb_sidebar/static/src/js/pb_sidebar.js:109`, `pb_sidebar.xml:12-13` | JS reads `window.odoo.session_info.biz_app_name`; on this build `window.odoo.session_info` is undefined (verified in console), so the fallback `"Payobook"` always wins. The collapsed rail shows the `P` badge at all times. |
| A4 | In-app left menu, expanded: user row bottom-left | `Ash Sohani` / `Payobook` | `pb_sidebar.xml:65` (same `brandName`) | same as A3 |
| A5 | Helper drawer (bottom-right "Ask PayAI" → guide text) | `Where Payobook is set up for your company: how pay is calculated…` | Learn content served from Python (`learn.content.text()`, no `_()`), class `lrn-gpurpose` | pb_learn never swaps the product name (grep: no `product_name`/`brand_name` in pb_learn) |
| A6 | `<meta name="biz-brand-product" content="Payobook">` in every page head | invisible | `biz_debrand/views/brand_layout.xml` | by design; not user-visible, listed for completeness |

Clean on live (checked, no hit): browser tab titles ("Rize - …"), home dashboard, every rail hub
landing (Calendar, Payroll, People, Hiring, Workforce, Expenses, Insights, Compliance, Talent,
Learning, Help, Settings), Settings › System › "About Rize" + What's new (release notes are
rewritten), language menu, Training hub first screens, payslip HTML reports
(`om_hr_payroll.report_payslip`, `pb_hr_payroll_formula.payslip_themed`,
`pb_hr_payroll_vietnam.report_payslip_vietnam`), PWA manifest, `/my` portal.
(`om_hr_payroll.report_payslip_details` returns HTTP 500 on rize — separate bug, not branding.)

## B. Stored in the rize DATABASE with "Payobook" (user-reachable rows)

Counts from `pg_dump --data-only rize | grep -i payobook`, 2026-10-31. Stored rows are NOT rewritten
for "Payobook": `biz_debrand/models/scrub.py` only scrubs rows matching `\modoo` and calls
`debrand_text` without the product argument.

| Table | Rows | What a user would see |
|-------|------|------------------------|
| mail_template | 28 | Email bodies/subjects: "Welcome to {{company}} — your Payobook account is ready" (pb_zoho_bridge, the employee welcome mail), "Open Settings in Payobook and go to Vendors", "Payobook shows who is eligible…", sign-offs "Payobook<br/>" (offboarding) |
| mail_mail / mail_message | 420 / 226 | Already-generated emails + chatter copies with the above bodies. NOTE: all 653 outgoing mails on rize are in state `exception` (no outgoing mail server) — none ever reached a mailbox. |
| learn_* (lesson, string, step, station, mission, glossary, column) | ~20 | Lesson text: "Get a month of attendance and overtime into Payobook…", chrome strings `brand=Payobook`, `coachName=Payobook Coach`, "Waiting for you to do this in Payobook", glossary "Payobook uses the latest effective date…" |
| ir_config_parameter `pb_tenancy.features` | 5 blurbs | Lock text "… Ask Payobook to switch it on …" — only shown when a feature is OFF; all 10 features are ON for rize today, so not visible now |
| ir_config_parameter `pb_tenancy.releases` | 3 notes | Release notes name Payobook; LIVE check shows the About page rewrites them (clean) |
| pb_zoho_event_rule | 4 | Rule notes: "Payobook adds them and starts their joining checklist" |
| pb_journey_template_step / pb_journey_task | 2 / 2 | Journey step descriptions ("Payobook shows who is eligible…", "Payobook sends the reminder") |
| hr_formula_rule | 8 | Rule descriptions: "pb.access.request governs Payobook internal user roles…" (formula studio, admin-facing) |
| hr_payroll_import_batch | 19 | `import_filename = Payobook-month-2026-10.xlsx` — the file the system generated and the user re-uploaded |
| pb_payroll_workbook_exchange | 18 | `filename: Payobook_VN_monthly_2026-10(1).xlsx` — downloaded workbook names |
| ir_cron / ir_act_server | 3 / 3 | "Payobook: build analytics facts", "Payobook: print the pay letters that are waiting", "Payobook: work out where everybody sits in their pay band" (Technical › Scheduled actions, admin only) |
| res_groups | 2 | Group descriptions "…from the Payobook Field check-in app" (user Access Rights tab) |
| ir_ui_view names | 28 | "Payobook Field check-in", "Payobook access paused" — view NAMES (technical); the rendered pages pass the view seam and read "Rize" |
| res_users | 5 | Logins `driver.hanoi@payobook.com`, `driver.hcmc@payobook.com`, `look.p4@payobook.com`, `runsrc.pc.validator@payobook.com`, `platform.recovery@payobook.com` (test/recovery accounts carried over from the template; "Platform support (recovery account)" appears in the owner's login chooser) |
| pb_asset | 2 | Demo asset notes "Payobook account" |
| ir_attachment | 5 | Excel instruction sheets ("Choose Update Payobook…", "Payobook keeps the formulas…"); compiled CSS carries `--biz-loader-logo: url(/pb_theme/static/src/img/payobook_logo.png)` as a default (overridden on tenants by `biz_loader_brand.js`; possible flash before JS runs) |
| mail_message.email_from | — | `"Rize" <bot@example.com>` (215 rows) and `"BizApp" <bot@example.com>` (6) — not Payobook, but the sender address is a placeholder |

## C. Code paths that bypass the seams (from the code sweep; not all verified live)

### C1. Seam gaps (platform-wide)
- `scrub.py`: product rule never applied to stored rows (see B).
- `biz_mail_debrand`: rewrites "odoo" only; never checks "Payobook" at send time.
- `brand.py:124` guards: `payobook.com`, `x@payobook.com`, `Payobook_…`, `Payobook-…`, `/payobook` survive even in source text; URL attrs never get the product rule.
- `biz_debrand_runtime.js:446` toasts: product rule off → raw Python notification strings pass.
- `act_window.help` only gets web_debranding's `.replace("Odoo", …)`.
- Seams rewrite vendor links INTO the tenant URL, so `rize.payobook.com` appears in documentation links, `noreply@rize.payobook.com`, etc.
- Provisioning never renames `base.partner_root` / `website.name` (by design, `brand_rules.py:36-44`); rize's website name is already "Rize".

### C2. Python strings not through `_()` (tenant-installed modules)
- `pb_tenancy/models/standing.py:80-85` trial banner "Your Payobook trial …"; `:44` paused-page default; `tenancy.py:110` default lock text; `support.py:174` 'Payobook support' (Settings › About › Support access log); `support.py:376,384,408`, `controllers/main.py:47` company-name fallback.
- `pb_sidebar/models/pb_sidebar.py:59-60` restricted-entry default reason "…full Payobook platform. Please contact Payobook…".
- `pb_hiring/services/board_catalogue.py` (many lines) job-board guidance "Payobook owns / must…", provider letter signed "Payobook https://payobook.com"; `models/board_catalogue.py:137` status 'Payobook integration pending'; `job_board_platform.py:24,27` SEEK/LinkedIn help; `:192-193` LinkedIn app name "Payobook - <company>" (external); `docusign.py:240` void reason "Cancelled by the hiring team in Payobook." (external, candidate sees it).
- `pb_zoho_sso/controllers/main.py:100,186,194,247,277,278,309` SSO error page texts; `models/zoho_sso.py:39` constraint message.
- `pb_hr_payroll_formula/controllers/zoho_oauth.py:20-28,108` raw HTML callback page.
- `pb_hr_payroll_formula/models/payroll_import_batch.py:43-44` import line error "Not in Payobook yet…".
- File names: `pb_payroll_templates/models/templates.py:601,960` (`Payobook_<cc>_monthly_template.xlsx`, `Payobook-month-<period>.xlsx`), Excel comment author 'Payobook' (`:590,905`; `pb_records/models/pb_records_io.py:304,317`; `excel_connector.py:707`), hidden sheets `_Payobook`/`_payobook`, `pb_explorer/models/pb_explorer.py:2147` CSV name `payobook_…csv`.
- `pb_source_atlas/models/pb_source_atlas.py:84` lane label 'Payobook records'.
- `pb_payrun_wizard/learn_manifest.py:147-155` "Update Payobook" guide; `pb_learn/models/learn_content.py:80` Python path has no `_()` (A5 is the live proof); `learn_intent.py:595,754` LLM prompts "help assistant for Payobook" (model answers can say Payobook); `pb_formula_studio.py:14869` same; `:4508` company fallback 'Payobook'.
- `pb_driver_checkin/controllers/driver_app.py:118` phone-app manifest name 'Payobook Field check-in'.
- 59 `_description = 'Payobook …'` on tenant-installed models → `ir_model.name` → core access-denied messages ("You are not allowed to access 'Payobook … cockpit data'").
- Master-side strings pushed to tenants: `pb_tenants/models/rollout_rules.py:492,496` maintenance banner "Payobook will be updated"; `support_service.py:338`, `support_rules.py:80` support log sentences; `feature_rules.py:44` default lock text; billing mails/invoice PDF (`billing_service.py`, `billing_rules.py`, `report/tenant_invoice.xml`) if the tenant is billed.

### C3. Data XML stored in DB (depends on scrub, which ignores Payobook)
- Mail templates: `pb_zoho_bridge/data/mail_template_data.xml:21,25,30-31` (welcome mail), `pb_contract_lifecycle/data/mail_template_data.xml:52,89,116,121,218,251`, `conversion_mail_data.xml:54,90,157`, `pb_hiring/data/mail_template_data.xml:49`, `pb_offboarding/data/mail_template_data.xml:42,175,208`, `pb_onboarding/data/mail_template_data.xml:138`, `pb_pip/data/mail_template_data.xml:43,203,234,298`, `pb_probation/data/mail_template_data.xml:38,113,183`, `pb_training/data/mail_template_assignments.xml:234`, `pb_vendor_access/data/mail_template_data.xml:49,88` (+ vi_VN .po copies).
- Action help panels: `pb_assets/views/asset_request_views.xml:142`, `pb_contract_lifecycle/views/contract_lifecycle_views.xml:149`, `pb_hiring/views/interview_views.xml:220,325,414`, `pb_onboarding/views/onboarding_views.xml:139`, `pb_vendor_access/views/vendor_access_views.xml:136`, `pb_zoho_bridge/views/event_rule_views.xml:100,102`, `inbox_views.xml:134,149`, `pb_hr_payroll_base/views/zoho_staging_views.xml:237`, `pb_zoho_sso/views/zoho_sso_identity_views.xml:50`.
- Other records: `pb_onboarding/data/journey_template_data.xml:52`, `pb_offboarding/data/journey_template_data.xml:156`, `pb_zoho_bridge/data/event_rule_data.xml:48,83,128,136`, `pb_driver_checkin/security/driver_security.xml:20-31`, `pb_hr_payroll_formula/data/mapping_templates.xml:139`, `pb_pay/data/ir_cron.xml:19,32`, `pb_explorer/views/pb_explorer_action.xml:15`, `pb_tenants/data/pb_feature.xml:32-76` (pushed lock texts).

### C4. keep markers / script / t-* literals
- `rize_website` A1/A2 (`keep`).
- `pb_hr_payroll_indonesia/views/payroll_country_selector_template.xml:445` `mailto:admin@payobook.com` inside `<script>`.
- `pb_hiring/static/src/xml/hiring_connections.xml:48` `t-esc="… ? 'Ready' : 'Payobook action'"`.

### C5. Static assets
- `pb_theme/static/src/img/payobook_logo.png` referenced unconditionally by `pb_theme/static/src/scss/pb_overrides.scss:13` as `--biz-loader-logo` default; `biz_theme/static/src/js/biz_loader_brand.js:42-46` overrides to `none` on tenants (possible flash).

### C6. Addresses / domains
- The tenant host `rize.payobook.com` itself (address bar, every email link, reset links, rewritten doc links). Only a custom domain removes it (see memory `rize-custom-domains`: ready pending Rize DNS).
- `admin@payobook.com` (C4), `https://payobook.com` (board_catalogue.py:129), `platform.recovery@payobook.com` recovery login (hidden by `pb_tenancy_security.xml:44`), demo driver logins.

## E. FIX SHIPPED 2026-10-31 (direct build, owner decisions: no credit on the white level; rewrite stored text too)

| Change | Where | Covers |
|---|---|---|
| `rebrand_prose(env, text)`, `rebrand_payload(env, value)`, `product_label(env)` — the product rule for Python-built strings and for *names* (file names, app titles, comment authors) | `biz_debrand/models/brand.py` | soft-imported (`try/except ImportError`) by modules that do not depend on biz_debrand |
| Stored-row scrub now applies the PRODUCT rule when `biz_debrand.product_name` is set (SQL prefilter `\m(odoo\|payobook)`), one savepoint per target; new targets: `mail_mail.body_html`, `ir_cron.cron_name`, `ir_model.name/info`, `ir_model_constraint.message`, `ir_act_server.name`, every translated `learn_*` column, `pb_zoho_event_rule`, `pb_journey_task`, `pb_journey_template_step`, `hr_formula_rule` notes, `hr_integration_mapping_template.note`, `pb_asset` notes | `biz_debrand/models/scrub.py` (2.9.0) | B (all stored rows). Runs on every `-u biz_debrand` and on Branding save. No-op on master/template (product empty). |
| Credit lines read `biz_debrand.powered_by`: shown on the `powered` level, absent on `white` | `rize_website/views/{login,frame}_templates.xml` (1.4.0) | A1, A2 |
| Sidebar reads `session.biz_app_name` from `@web/session` (old `window.odoo.session_info` was always undefined) | `pb_sidebar/static/src/js/pb_sidebar.js` (3.3.0); upsell default through `env._()` | A3, A4, sidebar default reason |
| Trial/paused/lock/notice/support sentences through `env._()` (the seam rewrites the msgid) | `pb_tenancy` standing.py, tenancy.py (`_tenant_words`), support.py, controllers/main.py (1.7.0) | C2 tenancy + master pushes (rollout banner, feature lock text, support log) at display time |
| Learn Python payloads: `guide()`, `ask()`, `answer_for()`, `explain_screen()` wrapped in `rebrand_payload` | `pb_learn/models/_brand.py` (new), learn_guide.py, learn_intent.py (20.7.4) | A5, learn_manifest texts |
| File names / comment authors use `product_label` (hidden meta sheets keep their names: the upload path looks them up) | `pb_payroll_templates/models/templates.py` (1.5.0), `pb_records/models/pb_records_io.py` (1.8.0), `pb_hr_payroll_formula/integrations/excel_connector.py`, `pb_explorer/models/pb_explorer.py` (2.6.0) | downloads |
| Driver PWA title `<brand> Field check-in` | `pb_driver_checkin/controllers/driver_app.py` (1.6.0) | phone app |
| SSO error page + Zoho OAuth result page through `env._()` | `pb_zoho_sso/controllers/main.py` (1.1.0), `pb_hr_payroll_formula/controllers/zoho_oauth.py` (1.163.0) | sign-in errors |
| Import-line error through `env._()` | `pb_hr_payroll_formula/models/payroll_import_batch.py` | import exceptions |
| Source Atlas lane labels via `rebrand_payload` | `pb_source_atlas/models/pb_source_atlas.py` (1.14.0) | "Payobook records" lane |
| Hiring: catalogue/guide/detail payloads via `rebrand_payload`; connection help via `env._()`; LinkedIn app name via `product_label`; DocuSign void reason via `_()`; readiness chip as template text | `pb_hiring` board_catalogue.py, connections.py, job_board_platform.py, docusign.py, `static/src/xml/hiring_connections.xml` (2.22.0) | job boards, LinkedIn, candidates |

### E2. REVERSE shipped 2026-11-01 (owner: "white-label → standard must work too")

| Change | Where | Behaviour |
|---|---|---|
| Brand journal `biz_debrand_rewrite` (plain table, `CREATE TABLE IF NOT EXISTS`, unique per table/row/column): every cell the PRODUCT rule changes is recorded with its raw pre-rewrite value and the value written, plus the product/brand pair in force | `biz_debrand/models/scrub.py` (2.10.0) `_biz_journal_write`, called from `_biz_scrub_text` / `_biz_scrub_jsonb` only when `product` is on and the vendor-only result differs | Vendor-rule ("Odoo") rewrites are never journaled: they are never reversed. |
| `_biz_debrand_restore_rows()` — runs FIRST on every `_biz_debrand_scrub_data()`; for each journal entry whose (brand, product) no longer matches the database (level left, brand renamed, product rule off): cell still equals the written value → raw value goes back (the forward pass that follows re-applies the vendor rule under the current brand); cell edited since → only the brand word is swapped back under the forward rule's own guards (`rize.payobook.com`, `rize_website`, `/rize/` untouched; case-sensitive); row gone → entry forgotten. Entries are deleted once handled. | same file | A tenant's OWN use of its brand name (a rule note they wrote) is never touched: it was never journaled. |
| Tenants cockpit calls restore + scrub on EVERY level change and reports "Stored text put back to the product name: N rows." / "Stored text rewritten to the brand: N rows." | `pb_tenants/models/service.py` `_apply_brand_to` (2.5.0) | Same path on the tenant's own Branding page and at the end of every `-u` (register_hook). |
| rize backfill: the 2026-10-31 rewrite pre-dates the journal, so its entries were rebuilt from `/odoo/backups/whitelabel-20261031/rize.dump` (only cells where today's forward rules applied to the dump value reproduce the current value exactly) | one-off `wl_backfill_rize.py` (odoo shell), evidence in `/tmp/wl4_*` on the server | After this rize can go back to standard with one Save. |

**Left out, on purpose:** `pb_hr_payroll_indonesia` mailto (module not installed on any live DB); pb_tenants billing mails/invoice PDF (master-only, Rize not billed); hidden Excel meta sheet names `_Payobook`/`_payobook` (machinery, looked up on upload); the tenant host `rize.payobook.com` (custom domain is the fix); LLM prompts in Learn/Formula Studio (model may still say "Payobook" — the reply goes through `rebrand_payload` in `ask()` only for the Learn path).

## D. Design facts to carry into the fix phase
- Three brand levels exist in `pb_tenants/models/brand_rules.py`: `product` (default), `powered` (brand + credit line, drawn by `biz_debrand_runtime.js renderPoweredBy()` on the sign-in page only), `white` (paid, no credit). Rize = `white`, yet `rize_website` hard-codes the credit → the module contradicts the level. Decision needed: honour the level (drop the two lines, or make them read `biz_debrand.powered_by` so the `powered` level shows them and `white` does not).
- A3/A4 is a plain bug: `pb_sidebar.js:109` must read the app name the way `biz_title_service.js:28` does (`session.biz_app_name` from `@web/session`), not `window.odoo.session_info`.
- Stored-row product scrub does not exist; adding one in `scrub.py` (product argument + `\mpayobook` match) would cover B in one pass, but the brand owner must decide whether a tenant ever wants "Payobook" in historical rows.
- Emails from rize do not send at all today (no `ir_mail_server`, 653 mails in `exception`) — separate ops item.
