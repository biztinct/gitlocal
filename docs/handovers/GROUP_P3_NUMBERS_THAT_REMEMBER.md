# GROUP Phase 3 — "Numbers that remember": scheme, currency and division on every fact; the Explorer finished

Read `docs/handovers/GROUP_LEDGER.md` FIRST and fully (rules incl. rule 7 "never store a
converted amount", rulings G1–G9, plumbing "Analytics facts" + "Currency today", gotchas
GR1–GR18 — GR4 positional columns and GR17 the RPC error fallback matter here), then the
P1/P2 phase-log entries and code (`pb_group`: `pb.fx.convert_many`, `pb.division.
division_for`; `pb_scheme_map`: `pb.scheme.map.resolve_many`, `hr.employee.pb_paid_by_id`,
`hr.payslip.run.pb_formula_config_id`), then Parts C and D of
`docs/design/group-blueprint.html` (the slicing contract and money).

## 0. What you are building, in one paragraph

The Analytics Explorer's summary rows learn to remember what they came from: the payroll
scheme and its version, the kind of run, the currency, the group-level division as at the
end of the period, and the person. With that, the Explorer gets the four things a group
needs and does not have: a **breadcrumb that walks Group › Country › Company › Division ›
Department**, a **scheme filter and a "Compare schemes" lens**, a **kind-of-run filter that
defaults to the main run** so advances never double count, and a **group-currency switch**
that converts at view time through `pb.fx`, stamps every converted figure with the rate and
date it used, and shows the parts separately with a plain reason when a rate is missing.
Insights and the pay-run board stop mixing currencies, the three old report screens that
forget the company are fixed, and one leftover from P2 (the error text in `pb_group`) is
closed. Nothing is stored converted. The Decision Room is untouched (P4).

## 1. Scope and binding non-goals

Deliverables:
1. `pb_explorer` bump: fact columns (appended LAST, GR4), builder changes, rebuild,
   dimensions/filters, breadcrumb, scheme compare lens, currency switch + rate badges,
   kind-of-run default, headcount as persons + FTE, NL parser additions, tests.
2. `pb_insights` bump: per-company currency, group total via `pb.fx` or per-currency
   parts, scheme filter chip; `pb_payruns` bump: company-scoped board, per-run currency;
   `pb_payrun_results` unchanged unless a test finds drift.
3. `pb_hr_payroll_analytics` bump: company filter in the two payslip searches; currency
   label from the record's company; `payroll_analytics_approval`: if any of its actions is
   reachable from a menu, palette or hub, add the company filter; if not reachable, leave
   it and list that in the report.
4. `pb_group` bump: GR17 fix (`.data.message` before `.message`, never "Odoo").
5. Deployed p9clone → payobook → abm → payobook_template with a timed full fact rebuild
   on each; Chrome walks; commits; ledger; report.

Non-goals (do NOT build):
- No change to the Decision Room, the pay run, the scheme map or payslip computation.
- No person identity or work segments (P5): `person_id` = `employee_id` and `fte` = 1.0 for
  now, but the columns exist so P5 is a builder change only.
- No new rate source. No accounting. No stored conversions of any kind (rule 7).
- No new `pb.sidebar.item`.

## 2. Design (the bar, the hero, the copy)

**The bar (owner's words, verbatim): "extreme WOW, intuitive, out-of-this-world
experience, best in class."** Hero moment: **the breadcrumb.** The Explorer's header reads
`Payobook Group › Vietnam › Retail › Bread`; click any crumb to go up, click a bar to go
down, and the whole canvas re-flows with a 240 ms ease while the header's currency chip
tells you what money you are looking at. Second hero: **the rate badge.** Every figure that
was converted carries a small chip — "at 17,450 · 31 Aug" — and a figure that could not
be converted shows in its own currency with an amber chip "no S$→₫ rate for August";
hover either and the sentence explains it. Third: **Compare schemes** — months across,
schemes down, one measure at a time, a sparkline in every cell, and a "cost per head"
toggle that turns absolute money into something a CEO can compare.

Copy: "Payroll scheme", "Kind of run" (Regular / Mid-month advance / End of month / Final
settlement), "Main runs only" (the default chip), "Group currency" / "Each in its own
money", "People" / "Full-time equivalents", "Counted once across the group". Never
"config", "cycle_type", "FX", "presentation currency". Zero dead-ends (§7). Keyboard:
crumbs and filter chips focusable; `←` goes up a level; Esc closes drawers (WF4).

## 3. Facts (`pb_explorer`)

Append to `pb.fact.run`, `pb.fact.line`, `pb.fact.emp` (in this order, LAST — GR4; extend
both SELECTs and the positional consumers together; `test_01_aggregate_parity` must stay
green): `config_id` (Integer, index), `config_name` (Char), `config_version` (Char —
`hr.formula.release` name if the payslip carries one, else the config's `write_date`
month), `currency_id` (Integer — the company's currency at build time), `division_id`
(Integer, index — `pb.division.division_for(department, r.date_end)`, resolved in SQL via a
temp table of active links for the period), `person_id` (Integer = employee_id for now),
`fte` (Float, 1.0). Keep `division` (Char) for compatibility.
Kind of run: `cycle` already exists; add `is_advance` (Boolean = cycle == 'mid_cycle').
Rebuild: `rebuild_all` on deploy per DB, detached, timed (company 5: ~30.5k payslips —
report the seconds). Dirty runs rebuild on the cron as today.

## 4. Explorer facade + UI

- `_DIMENSIONS` gains `scheme` (model `hr.formula.config`), `kind` (char, labels above),
  `division_id` (model `pb.division`), `country` (derived from company), `group` (one
  bucket); `_FILTERS` likewise; `_T2_ONLY` unchanged. Headcount measures: `people`
  (`COUNT(DISTINCT person_id)`) and `fte` (`SUM(fte)` over distinct persons per period).
- Default filters: `kind = main runs` (excludes `is_advance`) shown as a removable chip.
- **Breadcrumb**: levels group → country → company → division → department (→ job at
  employee grain). State in the URL hash so a link reproduces the view.
- **Currency**: header chip = the currency of what is shown. Modes: `own` (each row in
  its own currency; a mixed set shows per-currency subtotals, never a sum) and `group`
  (convert each row through `pb.fx.convert_many` with the group's policy at the row's
  period end; sum only the `known` rows; unknown rows listed under "Not converted" with
  the reason). Every converted total carries `{rate, rate_date, policy}`; the chart
  tooltip and the table cell show the badge. Single-currency sets never convert.
- **Compare schemes lens**: pick 2–6 schemes; months across; measures: workforce cost,
  gross, net, employer contributions, overtime, people, FTE, cost per head; sparkline
  per row; export the table.
- NL parser: "by scheme", "by division", "by country", "main runs", "including
  advances", "in group currency", "in dollars/dong" (map currency words to codes).
- Rate badge component reused by Insights.

## 5. Insights, pay-run board, old reports
- `pb_insights`: totals over `env.companies` convert through `pb.fx` in group mode or show
  per-currency parts; the header says which; the OT ceiling reads the row's company;
  an optional scheme chip.
- `pb_payruns`: `Run.search` scoped to `env.companies` via the runs' slips' companies
  (the run has no `company_id` — derive from `pb_formula_config_id.company_id` or first
  slip); price each row in its own company's currency; no cross-run total unless all
  one currency.
- `pb_hr_payroll_analytics`: `_get_payslips_for_period` in personnel costs and statutory
  contributions gain `('company_id','=',self.company_id.id)`; employee-detail gets a
  `company_id`; currency label from `company_id.currency_id`.
- `payroll_analytics_approval`: reachability check first (menus, palette, hubs); fix or
  list.
- `pb_group`: GR17 one-line fix; add a static test that no JS falls back to `e.message`
  without checking `e.data.message` first, across `pb_group`, `pb_scheme_map`,
  `pb_explorer`.

## 6. Tests (p9clone; numbered)
- T1 fact columns appended last; `test_01_aggregate_parity` green; a rebuilt run's
  `config_id` equals its slips' config; `division_id` equals `division_for` at period end;
  `person_id == employee_id`; `fte == 1.0`; `is_advance` true only for mid_cycle.
- T2 sum over any grouping (scheme, division, department, company) equals the sum over
  runs with the same filter (the invariant in the blueprint's engineer fold).
- T3 headcount = distinct persons: a person on advance + main in one month counts once
  with the default filter and once with advances included.
- T4 group mode: a two-currency set with rates converts only known rows, lists unknown
  rows with the reason, never sums across currencies in own mode; single-currency sets
  never call `pb.fx`.
- T5 rate badge meta present on every converted figure; policy and date match `pb.fx`.
- T6 breadcrumb state round-trips through the URL hash; going up restores the prior
  filters.
- T7 compare lens: cost per head = cost / people per cell; export matches the table.
- T8 NL parser: the seven new phrases map to the right filters/modes.
- T9 `pb_insights` per-company symbol; group total known/unknown split; OT ceiling per
  row company.
- T10 `pb_payruns` board lists only the switcher's companies' runs and prices each in its
  own currency.
- T11 old reports: personnel costs and statutory contributions filter by company (a second
  company's payslips excluded); employee-detail has `company_id`.
- T12 GR17: no `e.message`-first fallback in the three modules; no "Odoo" anywhere.
- T13 rebuild timing on company 5 recorded (< 120 s target; report actual).
- T14 earlier suites green: `/pb_group`, `/pb_scheme_map`, `/pb_explorer`, `/pb_insights`,
  `/pb_payruns`, `/pb_budget`, `/pb_decision_room` (same pre-existing p9clone drift set as
  P2, no new failures).
Browser (payobook + abm; 1440 + 390; light + dark; `docs/handovers/group_p3_shots/`):
- B1 Explorer breadcrumb walk Group › Vietnam › Retail › Bread and back; canvas re-flows.
- B2 Scheme filter: Retail End-Month only; then Retail + Manufacturing; Compare schemes
  lens with cost per head; export.
- B3 Kind of run: default "Main runs only" chip; remove it → people count changes and the
  chip explains double counting.
- B4 Currency: on payobook the group is VND-only today, so add one SGD→VND rate on
  p9clone for August, build a Singapore run there (scratch; p9clone only), and show:
  own mode with two subtotals, group mode with the badge, a missing-rate month with the
  amber chip and "Not converted" list. Delete the scratch after. On payobook show the
  single-currency behaviour (no badges, chip says ₫).
- B5 Insights header currency and the split total on p9clone's two-currency case.
- B6 Pay-run board on payobook: company-scoped list, per-run currency.
- B7 Old personnel-costs report on p9clone with two companies: totals differ by company.
- B8 abm: Explorer unchanged in feel (one company, one scheme), breadcrumb collapses to
  Company › Department; no badges.
- B9 390 px and dark; ⌘K "Compare schemes" (row 3350).
- B10 GR17: force an RPC error on the Group screen → the sentence, never the vendor word.

## 7. States (zero dead-ends)
No group (breadcrumb starts at Company; currency chip is the company's) · one currency
(no badges, no switch) · missing rate (amber chip + "Not converted" list + link to the
rate list) · a scheme with no runs in the period (row present, dashes, sentence) · a
division with no departments (absent from the crumb, present in "Not in a division") ·
advances included (chip warns about double counting) · facts stale (the "built at" line
+ Rebuild) · a person with no department (bucket "No department") · export blocked by
the browser (toast with the fix).

## 8. Report back (plain-English first)
1. Three sentences: what the breadcrumb does, what the rate badge tells you, what
   "Compare schemes" answers.
2. T1–T14 / B1–B10 table with evidence; rebuild seconds per DB; convert timing.
3. Deploy evidence per DB; the p9clone two-currency rehearsal (rate added, scratch run,
   deleted).
4. Deviations; new gotchas GR19+; phase log updated.
5. Self-score against the bar and the one thing to improve first.
6. Commit list.
