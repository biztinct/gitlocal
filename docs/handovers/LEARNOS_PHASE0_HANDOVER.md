# LEARNOS Phase 0 — Truth on empty tenants

Read `docs/handovers/LEARNOS_LEDGER.md` and `docs/handovers/PBLEARN_LEDGER.md` first.

## Why
Fresh tenant `abm.payobook.com` (empty DB) shows "1230 headcount / ₫28.0M payroll / ₫23K avg /
₫4.4M contributions". These are hardcoded sample constants, not data. This phase makes every
number on the dashboard and the legacy analytics surfaces HONEST, adds a warm empty-state for
brand-new tenants, and deploys to all live DBs.

## Verified plumbing facts — do NOT re-derive
- `pb_dashboard/models/pb_dashboard.py` (109 lines total): real SQL KPIs at :56-77; the offending
  fallback at :78-85 reads `hr.analytics.dashboard` when `payroll` is falsy and overwrites
  headcount at :85. Payload shape at :95-108.
- `pb_hr_payroll_analytics/models/hr_analytics_dashboard.py`: `_compute_dashboard_stats` :178-240
  returns a per-country `sample_data` dict (key `'ALL'` = 1230/28M/4.39M/22764.23 at :225-230).
  Stat fields declared :107-128. The record every DB has ships from
  `pb_hr_payroll_analytics/data/hr_analytics_data.xml` (`hr_analytics_dashboard_main`,
  `selected_country='ALL'`).
- `pb_dashboard/static/src/js/pb_dashboard.js`: `vnd()` :48-54 hardcodes `₫`. Component fetches
  `pb.dashboard.get_dashboard_data` at :26. Lucide-style inline SVG icon helper :31-34, `ring()` :36-46.
- `pb_dashboard/static/src/xml/pb_dashboard.xml`: hero :8-23 with hardcoded "Good afternoon" :11;
  KPI strip :26-31; Company-overview card hardcodes `ring(100)` :55; anchors present:
  `dash-hero` :8, `dash-runpayroll` :18, `dash-kpis` :26, `dash-formula` :69 — pb_learn's
  anchors.json lists these as foreign anchors; they MUST all remain in the template.
- `pb_hr_payroll_analytics/models/hr_analytics_budget_variance.py`: `use_sample_data` field :35
  (default True); `action_generate_analytics` :77+ fabricates budget/actual dicts and sets
  `use_sample_data = True` at :126. View refs: `views/hr_analytics_budget.xml:16` (sample-data
  note, invisible unless flag) and `:31` (readonly field). Keep both working.
- `pb_hr_payroll_analytics/models/hr_payroll_employee_detail.py`: drill-down falls back to
  `_generate_sample_data` when the department is missing (:84-86) or no payslips (:90-93);
  `_generate_sample_data` :165+ invents employee rows with fake names.
- Odoo 19; `hr.payslip` states include `level1`/`level2`/`done`; mid/end cycle logic already
  handled by the SQL at :62-72 — do not touch that query.

## Scope

### 1. `pb_dashboard` — honest + localized + welcoming
- **Delete** the fallback block `pb_dashboard.py:78-85` entirely. Empty DB → zeros.
- Add to the payload: `currency: {symbol, position}` from `env.company.currency_id`
  (`symbol`, `position` fields; position is `'before'`/`'after'`), and
  `has_learn: bool(env['ir.module.module'].sudo().search_count([('name','=','pb_learn'),('state','=','installed')]))`.
- JS: replace `vnd()` with `money(n)` — same compact B/M/K formatting, but symbol + side from
  the payload (fallback `₫` before if payload missing). Add `greeting()` returning
  "Good morning" (<12h), "Good afternoon" (<18h), else "Good evening" from local browser time.
- XML: use `greeting()`; Company-overview ring shows only when `state.d.kpis.headcount` > 0
  (render nothing in its place when 0 — do not show a red 0 ring).
- **Empty-state setup panel**: when `headcount === 0 && !run.slips && formula.count === 0`,
  render a panel between hero and KPI strip (KPIs + cards stay, showing honest zeros — anchors
  intact). Design per payobook-design-system (white surface, left rail accent, Lucide inline SVG
  like the existing `icon()` helper, indigo primary buttons, NO gradients/emoji):
  - Title: "Let's set up your payroll". Sub: "Your workspace is ready. Three small steps and
    you'll see your first payslip."
  - Row 1 "Learn the basics — a 2-minute guided look around" → button opens
    `pb_learn.action_learn_journey` (render row only if `has_learn`).
  - Row 2 "Add your first employee" → resolve the action xmlid the sidebar Employees leaf uses
    (look in `pb_people`) and open it.
  - Row 3 "Import your Excel sheet — bring everyone in at once" → resolve the pb_import cockpit
    action xmlid (look in `pb_import`) and open it.
  - Hero sub-line when empty: "No payroll data yet — let's get you set up" instead of the
    "— · 0/0 payslips done" string.
- New CSS goes in pb_dashboard's existing stylesheet; match `.pbd-*` naming.

### 2. `pb_hr_payroll_analytics` — kill fiction
- `_compute_dashboard_stats`: delete the sample dict; compute REAL aggregates with the same
  shape as `pb_dashboard.py:56-75` (latest `date_from` month, company-scoped, GROSS sum,
  INSCO/COMP contributions, distinct-employee headcount, end-cycle-scoped) — factor or copy the
  SQL; zeros when no payslips. Ignore `selected_country` for these four stats (it was only ever
  a sample-data key selector).
- Add a module-level helper `_demo_world(env)` → True iff `pb_demo` is installed (via
  `ir.module.module`). 
- `action_generate_analytics` (budget variance): if not `_demo_world`, return a warning
  `display_notification` ("Budget analytics needs payroll history — nothing generated.") without
  writing any JSON and leaving `use_sample_data` False. Change the field default to False.
  In demo worlds the existing sample path may remain (it is labelled in the view).
- Employee-detail drill-down: when department missing or zero payslip rows and not
  `_demo_world`, return a `display_notification` ("No payroll data for <dept> yet.") and create
  NO records. `_generate_sample_data` runs only in demo worlds.

## Non-goals (binding)
- No changes to the KPI SQL at `pb_dashboard.py:56-77`, to pb_learn, pb_coach, pb_demo, or the
  golden-template contents. No new models/fields except nothing schema-level at all in
  pb_dashboard (payload only). Do not redesign the analytics cockpit UI. Do not remove the
  `hr_analytics_dashboard_main` record. Do not touch the four `data-coach` anchors.

## Tests / verification (numbered — report each)
Local (no Odoo runtime here):
1. `python3 -m py_compile` every changed .py; `python3 -c "import xml.etree.ElementTree as t; t.parse(...)"` every changed .xml.
2. Grep-proof: no occurrence of `1230`, `28000000`, `sample_data` remains in
   `hr_analytics_dashboard.py`; no `hr.analytics.dashboard` reference remains in `pb_dashboard.py`.
Live (deploy per ledger rule 5; memory `payobook-deploy` has the exact ritual):
3. Backup first: pg_dump `payobook`, `payobook_template`, `abm` to `/odoo/backups/pre_learnos_phase0_*.dump`.
4. rsync `pb_dashboard` + `pb_hr_payroll_analytics`; detached `-u pb_dashboard,pb_hr_payroll_analytics`
   on EACH of: `payobook`, `payobook_template`, `abm`, `acme`. EXIT=0 each, no tracebacks, service up,
   "Registry loaded".
5. Chrome-MCP `https://abm.payobook.com` (login ash@biztinct.com — credentials via the user if a
   session isn't live; if login is impossible, validate on a scratch clone of the template via
   Host-header): dashboard shows headcount 0, payroll 0-money, setup panel visible, correct
   greeting, no console errors. Screenshot.
6. Chrome-MCP apex `https://payobook.com`: dashboard numbers UNCHANGED vs real data (non-zero,
   from the SQL path), no setup panel, no console errors. Screenshot.
7. Apex legacy analytics dashboard (`pb_hr_payroll_analytics.action_open_hr_analytics_dashboard`):
   stats now reflect real payslips (non-zero on apex); on abm the same screen shows zeros.
8. Prod asset-cache rule: after JS/XML changes the `-u` regenerates bundles; still hard-reload in
   Chrome and confirm no "style error" toast.

## Report back
- Per-file diff summary; answers to tests 1-8 with EXIT codes + screenshot names; the resolved
  xmlids used for the Employees/Import buttons; any deviation from this doc with reasoning;
  anything that belongs in the ledger.

## Kickoff
"Implement docs/handovers/LEARNOS_PHASE0_HANDOVER.md exactly. Read it and both ledgers fully
before writing code. Do not commit; leave the working tree for review."
