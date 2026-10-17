# GROUP Phase 1 — "The group": `pb_group`, `pb.fx`, divisions, the Group settings screen

Read `docs/handovers/GROUP_LEDGER.md` FIRST and fully (rules, rulings G1–G7, verified
plumbing, gotchas GR1–GR4, deploy ritual), then Parts B, D and H of
`docs/design/group-blueprint.html` (open it in a browser: `cd docs/design && python3 -m
http.server 8768`). The WFPLAN ledger's deploy ritual and credentials apply.

## 0. What you are building, in one paragraph

A new tenant-safe platform module `pb_group` that gives a customer's database the idea of
a **group**: one record naming the member companies, the currency the board reads in,
the exchange-rate policy and the fiscal start month; a **conversion service** `pb.fx`
that every later screen will use, lifted from the Budget screen's correct implementation
and fixed for groups; **divisions as group-level records** that departments in any
company attach to with effective dates; and a **Group settings screen** (a Settings hub
category with its own client action) where all of this is set up visually: the companies
as a tree under the group, the currency and policy card, a rate-coverage strip, and a
divisions board. The Budget screen is rerouted to `pb.fx` and must behave identically.
No pay-run, payslip, analytics or Decision Room behaviour changes in this phase.

## 1. Scope and binding non-goals

Deliverables:
1. `pb_group` 19.0.1.0.0: models `pb.group`, `pb.division`, `pb.division.link`,
   `res.company` extension, `pb.fx` service, facade `pb.group.room`, client action
   record + OWL screen, Settings category + ⌘K rows, security, tests, `vi_VN.po` stub.
2. `pb_budget` bump: `pb.budget.fx` becomes a shim over `pb.fx` (public API unchanged);
   its tests still pass unchanged.
3. `pb_demo` bump: its `presentation_currency_id` definition is kept byte-identical in
   type and string to `pb_group`'s (Odoo merges identical redefinitions) OR removed if
   `pb_demo` can depend on `pb_group` without a cycle — check and choose; document.
   `demo_generator.py:172-173` must still work (sets VND on the group it creates).
4. Demo data on payobook (company 5 + 6): one group "Payobook Group" with members 5 and
   6, presentation currency VND, policy month_end; divisions bootstrapped from company
   5's nine top-level departments. Do this through the screen, not SQL, and screenshot it.
5. Deployed p9clone (tests) → payobook → abm → payobook_template; hashes and versions
   verified; Chrome walks on payobook and abm; commits; ledger appended; report.

Non-goals (do NOT build):
- No change to `_find_formula_config`, the pay-run wizard, facts, Explorer, Insights,
  Decision Room, or any report. No `formula_config_id` on employees (P2).
- No `res.company.parent_id` writes, ever (ruling G1). No sidebar item (TARGET_RAIL).
- No rate fetching from an external source (a "connect a rate source" card may say
  "coming later"; rates are entered in the standard currency rates list, which the screen
  links to).
- No person identity, no work segments (P5).

## 2. Design (the bar, the hero, the copy)

**The bar (owner's words, verbatim): "extreme WOW, intuitive, out-of-this-world
experience, best in class."** Hero moment: the **group tree** — the group as a card at
the top with its currency and policy, the member companies beneath it as cards with
flag, currency, people count and scheme count, connected by drawn lines, with a
"+ Add a company" ghost card; tick a company and it slides into the tree with a count-up
of people. Second hero: the **rate coverage strip** — one row per currency pair the
group needs (SGD→VND for the demo), twelve month cells for the current year, green when a
rate exists under the chosen policy, amber when missing, click a cell to open the rate
list filtered to that month. Zero dead-ends (§8). Plain language: "Group currency",
"How rates are picked", "Fiscal year starts in", "Divisions", "Attach a department",
never "presentation currency" or "FX" on screen (use "group currency" and "exchange
rates"). Motion: cards slide into the tree, the strip fills left to right on load, a
division's people count counts up when a department is attached. Keyboard: every card
focusable, Enter opens, Esc closes drawers (capture-phase, WF4), arrow keys move between
month cells.

Layout: root class `pbim pbim-page grp`; a page heading ("Your group" / "The companies,
currency and divisions every report and plan will use"); then three stacked cards:
**Group** (tree + currency/policy/fiscal card), **Exchange rates** (coverage strip +
"Open the rate list" + "How rates are picked" select), **Divisions** (board: one card
per division with people count, member departments as chips grouped by company, an
"Attach a department" picker, effective dates in a drawer; plus "Suggest divisions
from your departments" which proposes one division per distinct top-level department
name across member companies and lets the user accept/rename/merge before creating).
Below 720 px everything stacks; the tree becomes an indented list.

Copy: group card sub-line "Nothing is stored in the group currency. Every figure keeps
the money it was paid in and is converted when you look at it." Rate policy help texts:
month end = "the last rate on or before the end of the month"; payment date = "the rate
on or before the day the pay run ends"; month average = "the average of that month's
rates; if there are none, the figure is shown unconverted".

## 3. Server design

### 3.1 `pb.group`
`name` (required), `code`, `presentation_currency_id` (required, `res.currency`),
`fx_policy` Selection `month_end` | `payment_date` | `month_avg` (default `month_end`),
`fiscal_start_month` Integer 1–12 (default 1), `company_ids` One2many via
`res.company.pb_group_id`, `active`, `note`; `mail.thread` with tracking on currency and
policy. Constraint: a company belongs to at most one group (the Many2one guarantees it);
`_code_uniq = models.Constraint('unique(code)', ...)`. Helper `for_company(company)` →
the group or an empty recordset. Display name = name.
`res.company`: `pb_group_id` Many2one `pb.group` (index, ondelete set null),
`presentation_currency_id` kept for compatibility as a related-readonly to
`pb_group_id.presentation_currency_id` **if** pb_demo's field is removed; otherwise leave
pb_demo's plain field and have `pb.fx` read the group first, the company field second.

### 3.2 `pb.division` and `pb.division.link`
`pb.division`: `name` (required), `code` (unique), `sequence`, `color` (Integer 0–11,
kit palette index), `active`, `note`, `link_ids`, computed non-stored `people_count`,
`company_ids`. No `company_id` (group-level; record rule: readable by everyone who can
read `hr.department`, writable by `pb_group.group_group_admin`).
`pb.division.link`: `division_id` (required, cascade), `department_id` (required,
`hr.department`, index), `company_id` (related stored from department), `date_from`
(required, default today), `date_to`, `active`. Constraint (Python `@api.constrains`):
no two active links for the same department with overlapping dates; plain sentence.
Helpers on `pb.division`: `division_for(department, on_date=None)` — walks the
department's `parent_path` upward, returns the first division linked on that date (so
attaching "Retail" at the top covers Groceries and Bread); `suggest()` — one candidate
per distinct top-level department name across the group's member companies (case- and
accent-insensitive), returning `{name, departments:[{id, complete_name, company, heads}]}`.

### 3.3 `pb.fx` (AbstractModel — the only conversion service)
- `group_for(company=None)` → `pb.group` or empty.
- `presentation_currency(company=None)` → `res.currency`, never empty: group currency →
  `company.presentation_currency_id` if that field exists → `company.currency_id`.
- `rate_companies(company=None)` → ids used to filter `res.currency.rate.company_id`:
  `False` + the group's member companies (+ the company itself). Fixes GR2.
- `rate(src, dst, when, company=None, policy=None)` → `{rate, known, policy, rate_date,
  note}`; `when` is a date (payment_date) or any date inside the month (month_end,
  month_avg). Implementation reads `res.currency.rate` rows directly (both directions:
  rows exist per currency with `rate` relative to the company currency; compute
  `dst_rate / src_rate` for the chosen date(s)); `known=False` when either side lacks a
  row on or before the date (or in the month for `month_avg`); an implicit 1.0 between
  different currencies is unknown; same currency → rate 1, known True.
- `convert(amount, src, dst, when, company=None, policy=None, manual_rate=0.0)` →
  `(value, known, meta)`; manual rate wins; unknown → `(0.0, False, meta)`; value rounded
  to `dst.decimal_places`.
- `convert_many(rows, ...)` for bulk use later (P3), same contract per row.
- `unknown_note(src, dst, when)` → translated sentence naming the pair and the month.
- `coverage(pairs, year, company=None)` → `{pair: [12 booleans]}` for the strip.
`pb.budget.fx`: keep `_name`, keep every method signature, delegate to `pb.fx`
(`convert` returns the two-tuple it always did). `pb_budget` tests unchanged and green.

### 3.4 Facade `pb.group.room` (AbstractModel, `@api.model`)
`get_room()` → `{allowed, can_edit, group: {...}|null, companies: [{id, name, country,
flag_code, currency, people, schemes, member}], currencies: [...], policies: [...],
coverage: {pairs, year, cells}, divisions: [{id, name, code, color, people, links:[{id,
department, complete_name, company, date_from, date_to, heads}]}], suggestions: [...],
rate_list_action: xmlid}`. Writes: `save_group(vals)`, `set_members(company_ids)`,
`create_division`, `update_division`, `archive_division`, `attach_department(division_id,
department_id, date_from)`, `detach(link_id, date_to)`, `accept_suggestions(list)`.
People counts by one SQL over `hr_employee` + `hr_version` (current_version_id) grouped
by department, rolled up the `parent_path` — copy the pattern in
`pb_decision_room/models/pb_decision_room.py:_build_baseline`. Every read in its own
`_safe()`. Aggregate reads may run under `sudo()` after the gate (WFPLAN WF10 argument).

### 3.5 Security
`pb_group.group_group_admin` (implied by `base.group_system`) edits; anyone with
`hr.group_hr_user` or `pb_decision_room.group_decision_user` reads. ACLs for the three
models; `pb.division.link` company rule `['|', ('company_id','=',False),
('company_id','in', company_ids)]`; `pb.division` and `pb.group` global read.

## 4. Client design

- `pb_group/static/src/js/group_room.js` — OWL `PbGroupRoom`, template
  `pb_group.PbGroupRoom`, registered `registry.category("actions").add("pb_group", ...)`;
  action record `pb_group.action_pb_group` (name "Group", tag `pb_group`). Loads via
  `orm.call("pb.group.room", "get_room")`; every write re-reads.
- `group_palette.js` (loaded after): Settings category `{key: "group", icon:
  "landmark", label: _t("Group"), blurb: _t("Companies, group currency, exchange rates
  and divisions"), groups: [...], cards: [{id: "group", tag: "pb_group", icon:
  "landmark", label: _t("Your group"), sub: ...}, {id: "rates", ...opens the standard
  currency rate list by xmlid}]}` seq 30; ⌘K rows 3300 ("Group"), 3310 ("Divisions" →
  same action with `pb_focus: 'divisions'`, declare `wantsArrival`), 3320 ("Exchange
  rates" → rate list xmlid). Icons: `landmark` exists; add `globe`, `coins`, `link`
  (exists), `gitBranch` if missing.
- SCSS `.pbim.grp` on kit tokens only; tree lines drawn with CSS borders (no SVG paths
  by hand); strip cells `role="grid"`.
- Drawers: division detail (links with dates, detach with a date), attach-department
  picker (search across member companies, grouped by company, shows people count and
  whether the department is already in another division), "Suggest divisions" review
  list (accept / rename / merge by ticking two suggestions).
- Company flags: two-letter country code in a rounded chip (no flag emoji).

## 5. Tests (all on p9clone; numbered)
- T1 `pb.fx.rate` month_end picks the latest row ≤ month end; payment_date picks ≤ the
  given date; month_avg averages the month's rows and is unknown when none.
- T2 `pb.fx` refuses an implicit 1.0 between different currencies; same currency is
  known with rate 1; `convert` rounds to the target's decimals; unknown → `(0.0, False)`.
- T3 rate rows owned by company 1 are found when converting for company 6 in the same
  group (GR2 fixed); rows owned by a company outside the group are not.
- T4 `pb.budget.fx` shim: every existing `pb_budget` test passes unchanged; a spot-check
  that `convert` still returns a two-tuple.
- T5 a company can belong to one group only; `set_members` moving a company between
  groups updates both; archiving a group detaches members.
- T6 `pb.division.link` overlap constraint refuses two active links on one department
  with overlapping dates (plain sentence) and allows sequential ones.
- T7 `division_for(Groceries)` resolves through Retail's link at the top-level
  department; a department with no linked ancestor resolves to empty.
- T8 `suggest()` on the demo group proposes one division per distinct top-level name
  across companies 5 and 6, merges "Retail" if both have it, and skips names already
  linked.
- T9 `get_room` people counts per division equal a direct SQL count; company 5 nine
  top-level departments → nine suggestions; timing < 500 ms.
- T10 facade gates: a reader without the group can read but `save_group` raises a plain
  AccessError; admin edits.
- T11 no user-visible string contains "Odoo" (xml/js/py/pot, mirror pb_settings' test).
- T12 static contract: bundle == disk in order; icons in `IC`; action is a record; yield
  root registered; palette rows resolve; no sidebar item added; TARGET_RAIL test green.
- T13 `pb_demo`'s generator still runs on p9clone (`presentation_currency_id` compatible).
- T14 `res.company.parent_id` is never written by this module (grep test).

Browser (Chrome MCP; payobook then abm; 1440 + 390; light + dark; screenshots in
`docs/handovers/group_p1_shots/`):
- B1 Settings → Group opens; empty state explains what a group is and offers "Create
  your group"; create "Payobook Group", tick companies 5 and 6 → tree draws, counts.
- B2 Change group currency to VND and policy to month end → tracked in chatter;
  coverage strip shows SGD→VND cells; click an amber month → rate list opens filtered.
- B3 Divisions: "Suggest divisions" → nine suggestions → rename one, merge two, accept →
  cards with people counts that sum to 4,533 (+ Unassigned); attach a Singapore
  department to "Logistics" → counts update; detach with a date → history kept.
- B4 Overlap refusal shows the sentence inline, not a dialog.
- B5 ⌘K "Group", "Divisions" (scrolls to board), "Exchange rates".
- B6 abm: a single-company group creates fine; strip says no pairs are needed.
- B7 390 px: stacked, indented tree, no horizontal scroll; dark mode readable.
- B8 Budget screen on payobook before/after: identical numbers and notes (compare
  screenshots).

## 6. Build order
1. Models + `pb.fx` + shim + T1–T8, T13, T14 on p9clone.
2. Facade + T9–T10.
3. Screen: tree → rates → divisions → drawers → suggestions; static tests T11–T12.
4. Palette/settings category; Chrome walks; demo group on payobook via the screen.
5. Deploy ritual to all DBs; verify; commits; ledger (GR5+); report.

## 7. Report back (plain-English first)
1. Three sentences a CEO understands: what "your group" now means on screen, what the
   rate strip tells them, what divisions do.
2. T1–T14 / B1–B8 table with evidence; `pb.fx` timing for 1,000 conversions.
3. Deploy evidence per DB; the demo group as created (name, members, currency, policy,
   divisions and counts).
4. Deviations; new gotchas GR5+; phase log updated.
5. Self-score against the bar and the one thing to improve first.
6. Commit list.

## 8. States (zero dead-ends)
No group yet (teach + create) · one company only (group still useful: fiscal start,
divisions) · company in another group (explain, offer move) · no rates for a pair
(amber cells + link + sentence) · a department already in a division (chip says which,
offer move with a date) · division with no departments (ghost card "Attach the first
department") · a suggestion that matches an existing division (offer "add to it") ·
reader without edit rights (values visible, buttons absent, "Ask an administrator") ·
facade failure (sentence + Retry).
