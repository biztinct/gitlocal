# WDGAP QF2 — plumbing facts: Explorer saved views, Excel, send regularly

Verified by a read-only code survey on 2026-11-14 (branch 19.1). Do not re-derive; spot-check a line before relying on it.

I've verified everything below in the repo and Odoo 19 core. One claim is my inference and is marked as such. Paths are relative to `/Users/adity/Documents/GitHub/gitlocal/`.

## 1. pb_explorer plumbing

- **Manifest** (`pb_explorer/__manifest__.py`): version `19.0.2.6.0`. Depends on `web, om_hr_payroll, pb_hr_payroll_base, pb_payruns, pb_import_kit, pb_insights, pb_group`. It has no `controllers/` folder.
- **Fact tables** (`models/pb_fact.py`): `pb.fact.run` (:50), `pb.fact.line` (:139, per-component grain) and `pb.fact.emp` (:188, per-employee grain). Every row carries `company_id`, `division_id`, `config_id` (the scheme) and `currency_id`.
- **The query** is `pb.explorer.query(spec)` (`models/pb_explorer.py:611`), on an AbstractModel (:344) that inherits `pb.group.scoped`. Each call first checks access with `_require()` (:353), then cleans the spec with `_clean_spec` (:421).
  - Spec shape: `{measure, dimension, grain, chart, filters:{key:[vals]}, date_from, date_to, limit, advances:'main'|'all', currency:'group'|'own', target_currency:int, per_head:bool, path:[{level,key,label}]}`.
  - Valid values come from the registries: `_MEASURES` :66, `_DIMENSIONS` :118, `_GRAINS` :157, `_CHARTS` :165, `_FILTERS` :170.
  - Payload: `categories, series[{key,raw,label,values,total}], grand_total, parts[], mixed, money{mode,converted,target,rates,unconverted}, currency, period, trail, heads, coverage, truncated` plus labels.
- **Other RPCs:** `resolve_spec(lens, spec)` :382, `get_schema()` :1716, `drill` :1927, `narrate` :2168, `ask` :2427.
- **CSV export** is a model method, not a route: `export_csv(spec)` at :2097.
  - It calls `self.query(spec)` and writes the period rows, then one block per `part` with an "Amounts in X" line, then a "Not converted" table.
  - It returns `{ok, csv_b64, filename, rows, truncated, cap}`.
  - The browser side is `exportCsv()` in `explorer.js:1433`, which downloads through a `data:text/csv;base64` anchor.
- **Starting views:** `_LENSES` at `pb_explorer.py:295-341` (11 entries). They reach the browser through `_lenses()` :2668 and `get_schema()['lenses']` :1883. The template draws them at `explorer.xml:109-150`.
- **JS state** is `this.state.spec` (`explorer.js:96-117`). The URL is written by `writeHash()` (:568-588), called from `run()` at :265, and read back by `readHash()` (:590-617).
  - The hash is `#pbex=` + `encodeURIComponent(JSON)` with short keys: `{m,d,g,c,f,p,a,u,t,h,s,e}` (`HASH_KEY` :78).
- **Toolbar:** `explorer.xml:31-40` holds the Refresh button (:32) and Export (:36, calls `exportCsv`). An Excel button goes next to these.
- **Access:**
  - Gate groups (`_GATE_GROUPS` :45-49): `pb_hr_payroll_base.group_payroll_base_manager`, `group_payroll_analytics_user`, `group_payroll_super_admin`, plus `base.group_system`.
  - The fact tables have read-only ACLs (`security/ir.model.access.csv`) and no record rules.
  - Rows are narrowed in SQL inside `_where` (:764):
    - by company, using `self.env.companies` passed through `_visible_companies` (`_co_ids` :366);
    - by division (`_visible_divisions`, :770).
  - **Department visibility is NOT applied to query rows.** It only trims the chip options in `get_schema` (:1790-1796).
  - Scheme is a filter only (`config_id`), not an access rule.
  - The definitions live in `pb_group/models/pb_group_visibility.py:440-460` and read `env.user`.
- **Multi-currency:** enforced by `_buckets` (:1121-1204) and `_query_one` (:1053).
  - In group mode amounts are converted with `pb.fx` at period end. Anything with no rate goes to `money.unconverted` and is left out of totals.
  - In own mode each currency becomes its own `parts[i]` with its own `grand_total`.
  - The Excel export must loop over `parts`, as `export_csv` does at :2124, and never add across them.

**Gotchas**
- `limit` is clamped to 24 series (`_MAX_SERIES` :53, :501). Exports therefore show the top 24 plus a `truncated` count, so the 20000 `_EXPORT_CAP` can never be reached.
- The spec stores only absolute dates. The resolved `period.preset` (`_resolve_period` :1526, presets :1462) gives `this_month` / `last_month` / … — a saved view should store that preset key so a schedule can move with the calendar.
- In a cron, `env.companies` with no `allowed_company_ids` in context falls back to all of the user's companies (`odoo/orm/environments.py:266-282`). So `query()` called with `with_user(recipient)` honours that person's own visibility.
- `_require` raises `AccessError`, so each recipient needs its own try/except.

## 2. pb_filter_kit saved views

- Model `pb.filter.view` (`pb_filter_kit/models/filter_view.py`). Fields: `name, screen, user_id, shared (bool), filters (Json), search_text, sequence`.
  - API: `pbf_save(screen, name, filters, search, shared)` :39, `pbf_update(vals)` :53, `pbf_delete` :69, `_pbf_payload` :74 (returns `key, mine, owner, …`).
- Record rules (`security/filter_view_rules.xml`): read own-or-shared, write only your own, `base.group_system` can edit any. ACL is `base.group_user` with full CRUD.
- It has no list method of its own. Views are listed by the mixin's `_pbf_views` (`filter_mixin.py:480-513`, search by `screen`, `VIEW_CAP=40`).
- JS calls are in `filter_kit.js:889-957` (`orm.call("pb.filter.view", …)`).
- **Reusable?** Only partly. `screen='explorer'` with the spec in `filters` (Json) would work, but:
  - there is no share-with-a-role field (a `group_ids` field plus a rule change would be needed);
  - `pbf_update` replaces `filters` with `{}` unless it is a dict;
  - it is wired to the list mixin.
- The cleaner choice is a new `pb.explorer.view` that copies this model and its three rules, plus `group_ids`.

## 3. Excel precedents (all openpyxl)

- **`pb_payrun_results/models/payrun_results.py:484` `export_grid`** — cleanest to clone.
  - Imports openpyxl inside a try and returns `{ok:False,msg}` if it is missing.
  - Returns `{ok, file_b64, mimetype, filename}`.
  - Number-format helper `_excel_fmt` at :479.
  - Download in OWL: `payrun_results.js:296-316` (atob → Blob → objectURL → anchor).
- **`pb_records/models/pb_records_io.py:262` `export_records`** — same return shape. Reusable `download(res)` at `records_desk.js:853`.
- **`pb_audit/models/pb_audit_console.py:778` `export_stream`** — uses xlsxwriter through a transient wizard (`wizards/audit_export.py:40-68`) and returns a `/web/content/...` URL. Heavier; skip it.
- **Best for a mail attachment:** `pb_demo_portal/models/signup_report.py:200` `_build_workbook` returns raw bytes and has `header()` / `widths()` / `table()` helpers.

## 4. Email and scheduled-job precedents

- **pb_demo_portal** (`signup_report.py`):
  - Hourly cron (`data/signup_report_data.xml:7`, `noupdate="1"`), with a local-time window and a stamp kept in `ir.config_parameter` (:89-100).
  - Creates `mail.mail` with `attachment_ids=[(0,0,{name,datas,mimetype})]` (:135-146), then `mail.send()`, and treats `state=='exception'` as a retry (:147-150).
  - Sender: `ir.mail_server._get_default_from_address()` (:79), which is just `config email_from`.
- **pb_rnr digest** (`models/digest.py`):
  - Daily cron plus a month stamp (:222).
  - Ships OFF behind a switch; when off it logs who would have received it (:256).
  - Queues `mail.mail` per address with `auto_delete=True` and per-address try/except (:306-344); does not force a send.
  - Crons are in `data/ir_cron.xml`. Note the comment there: `numbercall`/`doall` were removed in Odoo 19.
- **pb_clock** (`models/clock_alert.py`): `_send_digest` :732 groups managers by `lang` (`_by_lang` :725). `_send` :781 uses `mail.template.send_mail(force_send=False)`. Managers come from the group, filtered on active, internal, has email and company (:686).
- **None of these runs as each recipient — they all use sudo.** Running as the recipient has precedents elsewhere: `pb_explorer/tests/test_fact_engine.py:313` (`pb.explorer` with `with_user`) and `pb_lifecycle/models/workflow_people.py:300`.
- **No mail server on rize / sudima / p0clone** is a deliberate owner decision (`docs/handovers/workflow2/WF2_LEDGER.md:52`, D29): do not raise it, configure it, or re-send. On rize all 653 `mail.mail` sit in `exception` (`docs/handovers/whitelabel/WHITELABEL_AUDIT_2026-10-31.md:42`).
  - Existing digests just queue and fail quietly.
  - **There is no `_mail_is_configured` helper.** The closest are `pb_hiring/models/connections.py:129` (searches active `ir.mail_server`) and `pb_tenants/alert_service.py:907` `_mail_check` (checks for a sent mail in the last 7 days).
- **Debranding** (`biz_mail_debrand/models/mail_mail.py`) rewrites subject, body and from at send time (:51-91). It also cancels mail whose every recipient is on a blocked test domain such as example.com (:24-49). `pb_demo_portal/models/mail_debrand.py:44` also scrubs `body_html` on create.
  - New mail needs nothing special, except: name attachments with `product_label(env)` (as `export_csv` :2154 does), not "Payobook".
- **New tenants:** pb_tenants re-enables whichever crons were active on the template (`service.py:903`, `:1964`). A new cron that ships OFF stays off on new tenants.

## 5. "After each pay run" hook

- States are `draft / approval_pending / done / cancel` (`pb_payruns/models/hr_payslip_run.py:51`). The base model is `om_hr_payroll/models/hr_payslip.py:964`.
- A run finishes in `_approval_apply(request)` (`pb_payruns/.../hr_payslip_run.py:1112`), which writes `state='done'` at :1147. `write()` blocks state changes that don't come through approval (:712).
- **Precedent to clone:** `pb_pay_delivery/models/payroll_journal.py:380-402`. It calls super through `getattr`, checks the company flag `pb_post_payroll_journal` (:370), and wraps its own work in try/except so the approval is never undone.
  - The approval engine calls this inside a savepoint (`biz_approval_workflow/models/engine.py:1104-1117`), and any exception blocks the approval.
  - My recommendation (not something I verified): only mark the run as "due" here and let a cron send the mail.
- **Gotchas:**
  - The demo world moves runs with a raw sudo `write`, which skips `_approval_apply` (explained at `pb_explorer/models/hr_payslip_run.py:4-9`; that file hooks `write()` instead).
  - `hr.payslip.run` has no `company_id` (C18.43, `pb_explorer.py:592`).

## 6. Tests, translations, Insights tabs

- **Tests:** `pb_explorer/tests/` has `test_fact_engine`, `test_group_p3`, `test_p7_vietnamese`, `test_look_p4`, `test_schemectx_currency`, `test_schemectx_p2_country`. All are `post_install` TransactionCase.
- **Translations:** `pb_explorer/i18n/pb_explorer.pot` and `vi_VN.po` (275 entries each); `pb_filter_kit` and `pb_insights_hub` each have `vi_VN.po`.
  - `test_p7_vietnamese` checks completeness, so every new string needs a vi entry.
- **Insights tabs:** declared in `pb_insights_hub/static/src/js/insights_hub.js:165-174` (pulse, explorer, reports), with the gate list at :204-209. Add-on modules register their own tab through the `INSIGHTS_LENSES` registry (:77-94).
- **Constraints on a "Reports I receive" tab:**
  - `test_the_hub_ships_no_model_and_no_python_at_all` (`tests/test_insights_hub.py:245`) means it must live in pb_explorer or a new module, registered through that registry.
  - Any tab written directly into the hub file also needs a palette entry (`insights_hub_palette.js`, test :256).
  - The lens-order test (:202-208) expects exactly `[pulse, explorer]`, but the current file declares 3 tabs in the same format. It is probably already failing; check before relying on it.