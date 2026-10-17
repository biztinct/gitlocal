# GROUP Phase 2 — "Who is paid by what": the scheme map becomes the truth

Read `docs/handovers/GROUP_LEDGER.md` FIRST and fully (rules incl. rule 8, rulings G1–G9,
plumbing, gotchas GR1–GR12), then `GROUP_P1_THE_GROUP.md` and the P1 phase-log entry for
what is live (`pb_group` 19.0.1.0.1: `pb.group`, `pb.division`, `pb.division.link` with
`division_for(department, on_date)`, `pb.fx`), then Part B of
`docs/design/group-blueprint.html` (the resolution ladder) and Part A's "Structure" table.

## 0. What you are building, in one paragraph

Today nothing on a person says which payroll scheme pays them; the pay run takes everyone
with a running contract and works the scheme out afterwards, per payslip, down a ladder
that ends in "the first scheme I can find". This phase makes the department-to-scheme map
the truth. A new module `pb_scheme_map` extends the existing assignment record with the
kind of run and a division-level option, computes "Paid by" on every employee, lists the
people nobody pays as an exceptions queue, gives the Mapping screen's scheme canvas
coverage rings and a one-click **draft map read from the last three months of payslips**,
and changes the pay run so it asks "Pay run for which scheme?", offers exactly the people
that scheme covers with the count shown first, names anyone not covered, stays inside one
company, and writes the scheme onto each payslip as it is created. A company with exactly
one active scheme and no map entries must produce the identical run population as today
(ledger rule 8, test-enforced). Analytics, the Decision Room and payslip computation
rules are untouched.

## 1. Scope and binding non-goals

Deliverables:
1. `pb_scheme_map` 19.0.1.0.0: model extension of `hr.formula.scheme.assignment`, the
   resolver, `hr.employee` "paid by" fields, exceptions facade, Mapping canvas upgrade
   (scheme mode), pay-run wizard changes, Employee 360 "Paid by" chip, ⌘K rows 3330–3340,
   tests, i18n stub.
2. `pb_formula_studio` bump (scheme mode: company scoping GR3, cycle types, coverage,
   draft-from-payslips, division attachments), `pb_payrun_wizard` bump (scheme picker,
   population, stamping, company scoping), `pb_hr_payroll_formula` bump (ladder consults
   the map; assignment fields), `pb_employee_vault` bump (a chip registry on the Employee
   360 drawer), `pb_demo` bump only if its pay-run override must be reconciled (§4.5).
3. Deployed p9clone (tests + a re-run rehearsal) → payobook → abm → payobook_template;
   Chrome walks on payobook and abm; commits; ledger appended; report.

Non-goals (do NOT build):
- No change to how a payslip is COMPUTED once it has its scheme. No change to facts,
  Explorer, Insights, reports, Decision Room (P3/P4). No work segments (P5).
- No deletion or archiving of any existing assignment, payslip or run.
- Do not remove pb_demo's ability to run a demo division; reconcile it (§4.5).

## 2. Design (the bar, the hero, the copy)

**The bar (owner's words, verbatim): "extreme WOW, intuitive, out-of-this-world
experience, best in class."** Hero moment: **the drafted map.** Open the Mapping screen's
"Who is paid by what" canvas on a company with schemes and no map, press "Draft the map
from what you paid", and the wires draw themselves: for every department, the scheme that
paid most of its people in the last three closed runs, with a confidence ring ("902 of
902 people agree") and a sentence per wire ("Retail → Retail End-Month payroll: every one
of Retail's 902 people was paid under it in June, July and August"). Accept all, or fix
the amber ones. Second hero: **the pay run asks the right question.** Step one reads
"Pay run for" with the schemes as cards — name, kind of run, people covered, last run —
and the moment you pick one the people count and the "not covered" names appear before
anything is created.

Copy: "Paid by", "Kind of run" (Regular / Mid-month advance / End of month / Final
settlement), "Not covered by any scheme", "Draft the map from what you paid", "Covered",
"Attach a division", "Attach a department". Never "config", "assignment", "domain",
"cycle_type" on screen. Zero dead-ends (§8). Motion: wires draw with a 240 ms ease when
drafted; coverage rings fill; the pay-run count ticks up. Keyboard: canvas nodes focusable,
Enter attaches, Esc closes drawers (capture, WF4).

## 3. Server design

### 3.1 `hr.formula.scheme.assignment` (extend in `pb_scheme_map`, fields added to the
existing model — no new table)
Add: `division_id` (Many2one `pb.division`, optional; exactly one of `department_id`,
`division_id`, `domain` must be set — plain-sentence constraint), `cycle_type` Selection
`any` | regular | mid_cycle | end_cycle | full_final (default `any`), `company_id`
(related stored from `config_id.company_id`), `source` Selection `manual` | `drafted`
| `accepted`, `confidence` Float (0–1, for drafted rows), `note`. Replace the DB
constraint with: unique (department_id, cycle_type) and unique (division_id, cycle_type)
among active rows (Python constraint, plain sentence: "Bread already has a scheme for end
of month: Retail End-Month payroll. Replace it?"). `scheme_mapping_create` must stop
deleting every other assignment for the department; it replaces only the same cycle type.

### 3.2 The resolver (`pb.scheme.map` AbstractModel)
`resolve(employee, cycle_type, on_date=None)` → `{config, rung, via}` in this order:
1. **segment** — reserved for P5 (returns nothing now; keep the rung so P5 is one edit);
2. **department map** — the employee's department (contract `department_id` else
   current version's, WFPLAN WF7), walking `parent_path` upward, first active row whose
   `cycle_type` is the requested one, then `any`;
3. **division map** — `pb.division.division_for(department)` then the division's row;
4. **rule** — active rows with a `domain` (ordered by `sequence`) matched against the
   employee;
5. **only scheme** — the company has exactly one active `hr.formula.config` (any cycle
   type when `cycle_type='any'`, else of that type) → it;
6. **nobody** → `config=False`, `rung='none'`.
`resolve_many(employee_ids, cycle_type)` does it in SQL for thousands (one query for
department per employee, one for the map, Python for the walk) — < 300 ms for company 5.
`coverage(company, cycle_type)` → `{covered, not_covered: [ {employee_id, name, department,
reason} ], by_config: {config_id: count}}`.
`draft(company)` → proposals: for each department with people, the config that produced
the most payslips for its people over the last three `hr.payslip.run`s that contain them,
per `cycle_type` of those configs; `confidence = share`; `agree = n`; plus the sentence.
Never writes; `accept_draft(rows)` writes rows with `source='accepted'`.

### 3.3 `hr.employee` fields (in `pb_scheme_map`)
`pb_paid_by_id` (Many2one `hr.formula.config`, stored, index) = resolve for the main run
(`end_cycle` if the company has any end_cycle config, else `regular`);
`pb_paid_by_advance_id` (stored) = resolve for `mid_cycle`; `pb_paid_by_rung` (Char);
`pb_paid_by_stale` (Boolean). Recompute triggers: any write on the assignment model,
`pb.division.link`, `hr.version.department_id`, `hr.contract.department_id/state`,
config `state`; plus a nightly cron and an explicit "Recompute who is paid by what"
button on the canvas. Recompute in bulk via `resolve_many`, never per record.

### 3.4 The ladder in `_find_formula_config` (`pb_hr_payroll_formula`, minimal edit)
Insert the map immediately after the import-batch rung and before the unique-structure
rung: `self.env['pb.scheme.map'].resolve(self.employee_id, wanted_cycle)` where
`wanted_cycle` = the run's chosen kind (carried on the run, §3.5) else `any`. Guard with
`'pb.scheme.map' in self.env` so `pb_hr_payroll_formula` does not depend on the new
module. Sibling-slip rung stays first ONLY when the slip already carries a config set by
this phase; otherwise the map wins (a mixed run must not infect itself — GR3's cousin).

### 3.5 Pay run (`pb_payrun_wizard`, minimal but real)
- `get_defaults()` adds `schemes`: for `env.company` only, active configs → `{id, name,
  cycle, cycle_label, covered, not_covered, last_run: {name, date_end, employees}}`;
  `eligible` becomes per scheme.
- `prepare_run(vals)` takes `formula_config_id` (required when the company has more
  than one active scheme; optional otherwise): population = `coverage(...)` for that
  scheme ∩ the existing status/shortlist narrowing; contract search scoped to
  `env.company` explicitly (not the switcher); `hr.payslip.run` gets a new stored field
  `pb_formula_config_id` (in this module) and `name` defaults to "<Scheme> · <Month>".
- `compute_batch` creates slips with `formula_config_id` set. `pb_division` on the run
  keeps working (first slip) — untouched.
- **Rule 8 identity test**: on a company with one active scheme and no map rows, the
  population set is byte-identical to the pre-change set (fixture on p9clone using abm's
  shape: create a throwaway single-scheme company on the clone).
- Client (`payrun_wizard.js`): the step-one scheme cards; picking one shows "N people ·
  M not covered (see who)"; the "not covered" drawer lists names with department and the
  reason, and a button "Open the map" that deep-links to the canvas for that company.
  Single-scheme company: the card is pre-selected and the step reads as today.

### 3.6 `pb_demo` reconciliation (payobook has pb_demo installed)
Its override returns `divisions` and its division path filters by the employee's
`division` tag. Keep it working AND make the core picker the product: when the wizard
receives both `schemes` and `divisions`, it shows the scheme cards and hides the demo
selector; `prepare_run` maps the chosen scheme → its `pb_division` for the demo compute
path (`compute_batch` division-scoped formula compute stays as is). Rehearse on p9clone:
re-run Retail End-Month for an existing closed month into a scratch run and compare
employee count and net total with the existing run; both must match. Do not touch demo
data on payobook.

### 3.7 Exceptions facade and Employee 360 chip
`pb.scheme.map.get_exceptions(company_id, cycle_type)` for the queue; the Mapping canvas
shows the count as a rose chip and lists names in a drawer with "Attach a scheme" per row
(department-level fix suggested first). `pb_employee_vault`: add
`registry.category("pb_employee_360_chips")` rendered in the drawer header (bump
pb_employee_vault); `pb_scheme_map` registers "Paid by: <scheme> · Advance: <scheme>"
with a tooltip naming the rung ("from Bread's department map").

## 4. Client design (Mapping canvas, scheme mode)
- Scoped to the active company (GR3); a company switcher chip at the top when the user
  has several. Left column = divisions (from `pb.division`) and top-level departments,
  expandable to departments; right = schemes grouped by kind of run; wires carry the
  cycle badge. Coverage ring per scheme ("902 covered"), per department ("all covered" /
  "12 not covered").
- "Draft the map from what you paid" → a review drawer: rows with the proposed wire, the
  sentence, the confidence ring, accept/skip per row, "Accept all green". Amber < 0.9.
- Attach flows: drag a department or division onto a scheme (existing canvas gesture),
  choose the kind of run in a small popover (default "any"), confirm. Detach from the
  wire. Bulk: tick several departments → attach.
- Exceptions chip + drawer (§3.7). "Recompute" button with a toast naming how many
  changed. Empty state: "No schemes yet — create one in the Formula Studio."

## 5. Tests (p9clone; numbered)
- T1 resolver rungs in order (department, parent walk, division, rule, only-scheme,
  nobody) with `cycle_type` specificity beating `any`.
- T2 `resolve_many` on company 5 < 300 ms and equals per-record `resolve` on a 200 sample.
- T3 uniqueness per (department, cycle_type) and (division, cycle_type) with the plain
  sentence; `scheme_mapping_create` replaces only the same cycle type.
- T4 `pb_paid_by_id` recomputes on map write, division link write, version department
  change, config archive; nightly cron runs; bulk path used (query count assertion).
- T5 `draft()` on company 5 proposes the six division schemes with confidence ≥ 0.99 and
  never writes; `accept_draft` writes `source='accepted'`.
- T6 `coverage()` names the 29 people not in a division on company 5 (or their current
  count) with department and reason.
- T7 **rule 8 identity**: single-scheme company, no map rows → identical population
  before/after (fixture); with one map row added, population narrows to the covered set.
- T8 `_find_formula_config` consults the map after the batch rung and before the
  structure rung; a mixed run of Retail + Manufacturing people yields two configs, one per
  person, never one for all (the GR3 cousin).
- T9 `prepare_run` refuses without a scheme on a multi-scheme company with a plain
  sentence; stamps `formula_config_id` on every created slip; run gets
  `pb_formula_config_id`; contract search is company-scoped (a second allowed company's
  people are absent).
- T10 pb_demo rehearsal: Retail End-Month re-run for a closed month into a scratch run on
  p9clone equals the existing run's employee count and net total (then delete the scratch).
- T11 Employee 360 chip renders "Paid by" for a covered person and "Not covered" for an
  uncovered one; registry present in pb_employee_vault.
- T12 no "Odoo" in user-visible strings (all touched modules); static contract (bundle,
  icons, action records, palette rows 3330–3340 resolve, no rail item).
- T13 earlier suites still green: `/pb_group`, `/pb_budget`, `/pb_payrun_wizard`,
  `/pb_formula_studio`, `/pb_hr_payroll_formula` (scheme-related tags at least),
  `/pb_people_hub`, `/pb_decision_room`.
Browser (payobook + abm; 1440 + 390; light + dark; `docs/handovers/group_p2_shots/`):
- B1 Mapping → scheme mode scoped to company 5; draft → six wires with sentences; accept
  all; coverage rings; exceptions chip lists the uncovered people.
- B2 Attach a division to a scheme with kind of run; detach; the plain refusal inline.
- B3 Employee 360 shows "Paid by" for a Bread person; tooltip names the rung.
- B4 Pay run step one on payobook: scheme cards; pick Retail End-Month → 902 people,
  not-covered drawer; create the run into a scratch month on p9clone only (never a real
  month on payobook) and confirm every slip carries the scheme; delete the scratch run.
- B5 abm: single scheme, pre-selected card, step reads as today; population count equals
  today's 152.
- B6 ⌘K "Who is paid by what", "People not covered"; 390 px; dark.

## 6. Build order
1. Model extension + resolver + employee fields + T1–T6 on p9clone.
2. Ladder edit + wizard server + rule-8 fixture + pb_demo reconciliation + T7–T10.
3. Canvas upgrade + exceptions + chip + palette + T11–T12; Chrome walks.
4. Deploy ritual (backups!) to all DBs; verify; commits; ledger (GR13+); report.

## 7. Report back (plain-English first)
1. Three sentences: what "Paid by" means on a person now, what the pay run asks first,
   what the drafted map did on the Vietnam company.
2. T1–T13 / B1–B6 table with evidence; resolver timing on company 5.
3. Deploy evidence per DB; proof that the demo re-run matched; proof that abm's
   population is unchanged.
4. Deviations; new gotchas; phase log updated.
5. Self-score against the bar and the one thing to improve first.
6. Commit list.

## 8. States (zero dead-ends)
No schemes (teach + link to Studio) · no map yet (the draft button is the hero) · a
person with no department (exception with "give them a department" link) · a department
in two divisions on different dates (the current one wins, history shown) · a company
with one scheme (everything pre-selected, nothing new to learn) · a scheme with zero
covered people (card says so; suggests the map) · a run started while people are
uncovered (drawer names them; "Start without them" or "Open the map") · a drafted wire
below 0.9 confidence (amber, sentence says what disagreed) · resolver failure (sentence +
Retry; the pay run refuses rather than guesses).
