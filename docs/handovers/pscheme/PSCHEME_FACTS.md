# PSCHEME — facts study ("the pay scheme belongs to the person")

Study engineer, 26 Nov 2026. Read-only: no module code changed, no server or live database touched.
Worktree `gitlocal-worktrees/pscheme`, branch `pscheme` from `origin/19.1` at `8eb27c95e` (NEWHIRE P8 closeout).
**Every line number below is from that HEAD.** Engineering document: real technical names on purpose.
No credentials, client names or client data in this file. "(inferred)" marks a claim not proved by reading code.

**Owner decision (2026-11-26, binding).** The scheme moves to the PERSON: stored on the person with a start date,
pre-filled from Country of work (`payroll_country`, never the work site). HR can pick another scheme of that country.
The PAY RUN follows the person's own scheme. Team lines remain only as a bulk shortcut and as the fallback for people
with no scheme of their own. Existing people are filled once, from the scheme that pays them today, else from Country
of work, with a review list and undo. A Country of work change asks to change the scheme from a date.
Split work: two sites in the same country = one scheme. A short trip = the home scheme. A permanent move = the scheme
changes from a date. An ongoing two-country split = later, as a second contract.

**Scope note (owner, mid-study).** No pay run or payslip is in production yet; every run on rize and sudima is a test.
This study therefore does NOT analyse keeping past runs or payslips the same. The one-time fill only has to give each
person a sensible scheme from now on. Q7, Q8 and Q9 are about pay runs created from now on.

White-label rule for every handover that follows: never "Odoo" in a user-visible string (labels, help, toasts, .po
msgstr, reports). Technical names stay.

---

## 0. The ten facts a builder must not miss
1. There is ONE resolver: `pb.scheme.map.resolve_many` (`pb_scheme_map/models/pb_scheme_map.py:338-428`). The pay
   run, the payslip, "Paid by", Mapping coverage, the Updates sheets, loans, expenses, retro and PayAI all go through
   it (§1.3). Add the person rung there, plus the mirror in `resolve_for_draft` (`:537-567`), and almost every reader
   follows for free.
2. The pay run judges membership on the **period's first day**. `_scheme_population(..., on_date=date_start)` is at
   `pb_payrun_wizard/models/pb_payrun_wizard.py:557,728`. A person row dated from a mid-month hire date is NOT in force
   on the 1st (§7, trap T1).
3. The **kind of run** is the scheme's own `cycle_type` (`regular / mid_cycle / end_cycle / full_final`,
   `pb_hr_payroll_formula/models/formula_config.py:74-79`). A run asks `resolve_many(ids, config.cycle_type)`
   (`pb_payrun_wizard.py:334-336`). The pairing of a mid-month advance with its end-of-month scheme exists only as
   `hr.payroll.cycle.component.mapping` (`pb_hr_payroll_formula/models/payroll_cycle_component_mapping.py:7-40`).
   **"Scheme family" is NOT that pairing.** It means a scheme plus its edit BRANCHES (`parent_branch_id`,
   `advance_once.py:113-129`).
4. Rung 1, the work segment (`pb.work.segment`), is month-bounded (`_check_dates`, `pb_workseg/models/pb_work_segment.py:269-281`).
   It changes pay through `factor_for` (`:407-511`). It must NOT carry the person's scheme (§2).
5. **Nothing marks "Paid by" stale when Country of work changes.** No `'payroll_country' in vals` hook exists anywhere,
   yet rung-4 rules on rize read `payroll_country` (§6.7). The new rung needs its own stale marks, plus a daily
   boundary job for rows that start or end on a date (trap T3).
6. The advance answer is filtered by an **allow-list of rung names**, repeated in three places:
   `pb_scheme_map/models/hr_employee.py:155-158`, `pb_scheme_board.py:690-692`, `scheme_component_scope.py:114-115`.
   The third copy differs and also includes `'segment'`. A new rung name missing from them silently drops advance
   schemes (trap T2).
7. Dependency rail: `pb_hr_payroll_formula` and `pb_payrun_wizard` must NOT depend on `pb_scheme_map`. This is pinned by
   `pb_scheme_map/tests/test_static_contract.py:258-271` (`test_t12_the_ladder_edit_is_guarded`). The new model belongs
   in `pb_scheme_map`. `pb_contracts` and `pb_employee_vault` do not depend on it either, so they need soft probes or
   registries.
8. `hr.employee.payroll_country` is a plain column on `hr_employee`, defined at `pb_hr_payroll_base/models/hr_payroll_structure_base.py:261-273`
   and relabelled "Country of Work" at `pb_employee_form_tidy/models/hr_employee.py:28-31`.
   `hr.contract.payroll_country` is a SEPARATE column (`hr_payroll_structure_base.py:275-286`). It drives the
   contract's currency (`_compute_contract_payroll_currency`, `:296-303`). Nothing keeps the two in step.
9. Approval precedent: `pb.schememap.proposal` (`pb_hr_payroll_formula/models/schememap_approval.py:40-157`). It
   dispatches on kind (`_apply_<kind>`) and has a fast lane when the route is "No approval needed". Adding a kind is a
   method plus a label (§5).
10. The people the ladder answers "nobody" for today include every new Vietnamese joiner on rize. The rize Vietnam
    rule is a list of employee codes (P8 §2.4), so the fill's Country-of-work fallback matters there (§9).

---

## 1. The ladder as it is

### 1.1 `resolve_many(employee_ids, cycle_type='any', on_date=None)`, `pb_scheme_map.py:338-428`
`RUNGS = ('segment', 'department', 'division', 'rule', 'only', 'none')` is at `:67`. No test asserts the tuple; the
order is pinned by behaviour tests (§10).

Reads, done once for the whole roster:

| Step | Code | What it reads |
|---|---|---|
| roster | `_departments_for` `:101-143` | ONE SQL query. `hr_employee e WHERE e.active`. Team = `COALESCE(open hr_contract.department_id, hr_version.department_id of e.current_version_id)`; the open contract with the highest wage wins (`:118-124`). Returns `{emp: (dept, company)}`, capped at `MAX_EMPLOYEES=20000`. **Undated**: the team today, whatever `on_date` says. Overridden for what-if previews by `pb_job_change/models/job_change_inherits.py:106-123`. |
| team chains | `_chains` `:145-163` | `hr_department.parent_path` |
| map lines | `_map_rows(company_ids, on_date)` `:175-190` | `hr.formula.scheme.assignment`: active, scheme `state='active'`, `date_from <= day <= date_to` (open ends allowed), company or shared. Order `sequence, id`. `day = on_date or today`. |
| by team / division | `_by_department` `:192-200`, `_by_division` `:202-209` | `{id: {cycle_type: row}}`, first row wins |
| division links | `_division_of_department(on_date)` `:211-220` → `pb.division._links_on` (`pb_group/models/pb_division.py:94-106`) | dated links |
| rules | `:353-373` | Lines with a `domain` and neither a team nor a division. One `search` per rule over all ids. **A rule line's `cycle_type` is ignored** (any rule hit answers every kind). |
| segments | `_segment_schemes(ids, on_date)` `:294-336` | Soft probe on `'pb.work.segment' in self.env`. Confirmed segments with `config_id`, `date_from <= day <= date_to`, keyed by `host_employee_id`. |

Per-person order (`:382-427`):

| # | Rung | Answer `rung` / `via` (user-visible) | Notes |
|---|---|---|---|
| 1 | segment | `'segment'` / "from the days worked in %(company)s" | no kind-of-run filter |
| 2 | department | `_rung_department` `:434-447`: deepest team first; `_pick(bucket, cycle_type)` `:222-250` / "from %(team)s's team map" | |
| 3 | division | `_rung_division` `:449-468` / "from the %(division)s division" | |
| 4 | rule | `:405-418` / "from a rule on the map" | first rule in sequence order |
| 5 | only | `_rung_only` `:470-485` → `_only_scheme` `:253-270`: the company has exactly 1 active scheme (of that kind when a kind is asked) / "the only scheme in this company" | "ledger rule 8" |
| 6 | none | `_blank` `:289-292` / "No scheme covers this person yet." | |

`_pick` semantics (`:222-250`):
- Asked for a kind: an exact `cycle_type` line wins, else an `'any'` line.
- Asked for no kind (`'any'`): tried in the order `any, end_cycle, regular, full_final, mid_cycle`.
- A mid-month advance is never the answer to "who pays this person" unless the advance was asked for.

`resolve(employee, cycle_type, on_date)` (`:273-287`) is `resolve_many([id])`.

### 1.2 The draft and team variants
- `resolve_for_team(s)` (`:487-534`): rungs 2, 3 and 5 only (no person exists).
- `resolve_for_draft(department_id, values, company_id, cycle_type, on_date)` (`:537-567`):
  - rung 2, then rung 3;
  - then `_rung_rule_draft` (`:569-602`), which judges the rules on `hr.employee.new(values)` with `payroll_country`,
    `job_id`, company and team;
  - then rung 5.
  - No segment rung. Never raises.
- `_country_schemes(company_id, code)` (`:604-613`): active schemes of a country, this company's or shared, never
  `mid_cycle`. This is the chooser list.
- `suggest_by_country` (`:615-759`), `_latest_paid` (`:761-775`), `coverage` (`:777-824`), `get_exceptions`
  (`:826-836`), `draft` / `_draft_rows` / `_draft_row` (`:838-1029`), and `accept_draft` (`:1031-1082`), the only writer.

### 1.3 Every caller

**Pay run and payslip**
- `pb_payrun_wizard/models/pb_payrun_wizard.py:322-353` `_scheme_population(config_id, base_ids, on_date)` →
  `resolve_many(base, config.cycle_type, on_date)`. Covered = answer equals the run's scheme. Missed = no answer at
  all. A person answered with ANOTHER scheme is silently left out.
- Callers of `_scheme_population`:
  - `scheme_preview` `:544-574` (`on_date=date_start`, `:557`)
  - `_eligible_employees` `:661-737` (`:728`, `on_date=date_start`), reached from the step views `:810`, `:859`, `:957`
    (Extra run check), and the run builders `:1473` and `:1642` (`prepare_run` `:1557`)
  - `pb_timesheet_approval/models/payrun_wizard.py:96`
  - `pb_attendance_policy/models/clock_payrun.py:41`
  - `pb_payroll_templates/models/templates.py:126`
  - `pb_payai_actions/payai/actions_amber.py:1080`
  - `pb_payrun_wizard/models/application_payroll_wizard.py:19`
- The pay-run cards' "people covered": `_scheme_cards` `pb_payrun_wizard.py:230-276` → `Map.coverage(company, kind, 0)`.
- The payslip's own scheme: `pb_hr_payroll_formula/models/hr_payslip_formula.py:393-511` `_find_formula_config`.
  1. the run's `pb_formula_config_id`
  2. the import batch's scheme
  3. `pb.scheme.map.resolve(employee, context pb_cycle_type)` `:461-475`, **with no on_date (today)**
  4. a sibling payslip
  5. the structure, when exactly one
  6. the employee's nationality country
  7. any active scheme
  Reached only when `formula_config_id` is empty. The wizard stamps the run's scheme (`:1616-1623`;
  field `pb_scheme_map/models/hr_payslip_run.py:28-37`).
- The pay-run approval scopes' headcount: `pb_payruns/models/hr_payslip_run.py:1074-1100`
  `_approval_coverage_scopes` → `Map.coverage(company)`.

**"Paid by" and the screens that read it**
- `pb_scheme_map/models/hr_employee.py:115-188` `_pb_recompute_paid_by`: `resolve_many(ids, _pb_main_cycle(company))`
  plus `resolve_many(ids, 'mid_cycle')`, with the advance counted only for rungs `department / division / rule`
  (`:155-158`). It writes `pb_paid_by_id`, `pb_paid_by_advance_id`, `pb_paid_by_rung` and `pb_paid_by_stale=False`.
  - Trap: **`pb_paid_by_rung` stores the `via` SENTENCE**, not the rung key (`:159-183`).
  - `_pb_main_cycle` `:63-78`: `end_cycle` if the company has an active one, else `regular`, else `any`.
  - Nightly `_pb_cron_recompute_paid_by` `:212-218` (`CRON_BATCH=20000`), cron in `pb_scheme_map/data/ir_cron.xml:24-26`.
- `pb.scheme.board.paid_by` `pb_scheme_board.py:670-710` (resolves live when stale). Called from
  `pb_scheme_map/static/src/js/scheme_map_chip.js:45-46` (chip `scheme_map.xml:625-638`).
- `hr.formula.config.schemes_for_employee` `pb_hr_payroll_formula/models/scheme_component_scope.py:64-125`: reads
  `pb_paid_by_*`, or `_sc_resolve` when stale or empty. Its callers are pay setups, the contract drawer, comp &
  benefits, pay scales, tax, Country of Work fill, take-home and offers (§8 D).

**Mapping**
- `pb_scheme_board.get_board` `:129-215`, which uses `coverage` per kind and `draft`.
- `country_suggestions` `:570-579` → `suggest_by_country`.
- `pb_formula_studio/models/pb_formula_studio.py:10121-10240`: the fallback two-column board.

**Updates sheets**
- `pb_updates/models/updates_schemes.py:51-83` `_people_schemes` → `resolve_many(ids, cycle, on_date)` at `:72-73`
  (callers `updates_desk.py:487,513`, `updates_oneoff_desk.py:130`).
- `updates_ytd.py:489`, `updates_ytd_desk.py:1699` (`on_date=start`).
- `updates_joiners.py:219-268` `_department_schemes` **re-implements rungs 2, 3 and 5 from map internals** (§6.5).

**Add employee**
- `pb_new_hire/models/studio.py:456-520` `_scheme_for` → `resolve_for_draft` (`:485`).
- `:522-531` `_scheme_teams` → `resolve_for_teams`.
- `pb_new_hire/models/places.py:76,122` `resolve_for_team(s)` (`TEAM_RUNGS` `:34`).

**Pay-adjacent**
- `pb_retro/models/retro_backpay.py:342-380` (resolve per kind)
- `pb_loans/models/loan_payroll.py:335-350` (`on_date`), `pb_loans/models/pb_loans_board.py:427`
- `pb_expense_payroll/models/common.py:68-85` `scheme_pays` (`on_date`)
- `pb_pay/models/pb_pay_review.py:755-791` (`resolve_many`)
- `pb_job_change/models/job_change.py:411-440` `_scheme_now_and_after` (no date), `job_change_board.py:327`
- `pb_payai_actions/payai/actions_amber.py:2046-2058` `_scheme_of`
- `pb_pay_package/models/offer_total.py:165-176`: reads team lines directly (`_map_rows` + `_pick`), not the resolver
- `pb_hr_payroll_formula/models/contract_fill_in.py:517` (fill-in via `schemes_for_employee`)
- `tools/prepare_rize_august_scenarios.py:65` and `tools/migrate_rize_work_timezones.py:22` (one-off tools)

**JS that shows "Paid by"**
- `pb_scheme_map/static/src/js/scheme_map_chip.js:31-68`
- `pb_contracts/static/src/xml/contract_360.xml:355-372` (strip), `:400-407` ("Choose who is paid by what")
- `pb_job_change/static/src/xml/job_change.xml:160,351`
- `pb_new_hire/static/src/xml/new_hire_studio.xml:491,1242`, `step_check.js:69`
- `pb_learn/static/src/engine/screens.js:405-411,697`

### 1.4 Cache and stale flag
- Stored on `hr.employee` (`hr_employee.py:47-60`): `pb_paid_by_id`, `pb_paid_by_advance_id`, `pb_paid_by_rung`
  (holds the via sentence) and `pb_paid_by_stale` (default True).
- `_pb_mark_paid_by_stale(company_ids, employee_ids)` `:81-113` is ONE SQL `UPDATE`. Order: `flush_all`, then the SQL,
  then `invalidate_all(flush=False)` (gotcha GR13).
- Stale marks fire on:
  - map line create / write / unlink (`formula_scheme_assignment.py:184-215`, whole company);
  - `hr.version.write` with `department_id` (`hr_employee.py:221-233`);
  - `hr.contract.write` with `department_id` or `state` (`:236-250`);
  - `hr.formula.config.write` with `state` or `cycle_type` (`:253-267`);
  - `pb.division.link` create / write / unlink (`:270-301`).
- **NOT marked stale on:** a `payroll_country` write; a `pb.work.segment` write (`pb_work_segment.py:380-392`); a date
  passing a map line's `date_from` / `date_to`.

---

## 2. Rung 1, the work segment
- Model: `pb.work.segment`, `pb_workseg/models/pb_work_segment.py:75-163`. Fields:

  | Field | Meaning |
  |---|---|
  | `person_id` | `pb.person`, required |
  | `home_employee_id` | required |
  | `home_company_id` | stored, related |
  | `host_company_id` | required |
  | `host_employee_id` | |
  | `division_id` | |
  | `config_id` | "Host payroll scheme" |
  | `date_from`, `date_to` | both required |
  | `month` | stored |
  | `days`, `month_days`, `share`, `fte` | |
  | `pay_policy`, `effective_policy` | |
  | `kind` | `split / transfer / joiner / leaver / parttime` (`KINDS` `:51-57`) |
  | `state` | `draft / confirmed / cancelled` |
  | `derived` | |
  | `note`, `active` | |

- Created by:
  - the "Where they work" screen (client action `pb_assignments`, `pb_workseg/views/pb_workseg_action.xml:13-17`);
    server `pb.assignments.save_segment` `pb_workseg/models/pb_assignments.py:471-500` writes `state='confirmed'` at
    `:491`, and `:618` for the preview;
  - the nightly `derive_joiners_and_leavers` (`pb_work_segment.py:870-919`), only for companies with
    `res.company.prorate_joiners_leavers` (`pb_workseg/models/res_company.py:20`). Derived rows have **no `config_id`**,
    so they never answer rung 1.
- Confirmation: `action_confirm` `:395-397`, or written confirmed by `save_segment`.
- Dates: yes, but **one month only**. `_check_dates` `:269-281` says "A stretch of days belongs to one month".
- Other rails on segments:
  - at most a full month per person per month (`:302-346`);
  - no confirmed segment over a paid month (`:348-378`);
  - rung 1 keys on `host_employee_id` only (`pb_scheme_map.py:316`).
- **Why it must not carry the person's own scheme:**
  1. It is month-bounded, so an open-ended "from 1 Dec" is impossible.
  2. Any confirmed segment changes pay. `factor_for` / `_factor` (`:407-511`) cuts the home payslip or pays the host
     its share.
  3. It needs a `pb.person` and a host employment.
  4. It answers only for host employments.
  5. Application payroll refuses any person with segments (`pb_hr_payroll_formula/models/application_payroll_source.py:769-772`).
- Use: keep rung 1 for cross-company days only, above the new person rung.
- Live use: not verifiable from code. Whether any live database has confirmed segments that name a scheme must be
  counted on a copy (§9.3).

---

## 3. Kinds of run, and what a person-level assignment must store

### 3.1 Facts
- A scheme's kind is `hr.formula.config.cycle_type` (`formula_config.py:74-79`: `regular`, `mid_cycle`, `end_cycle`,
  `full_final`). A map line adds `'any'` (`CYCLE_SELECTION`, `formula_scheme_assignment.py:52-58`; field `:77-82`).
- Uniqueness: one line per team or division per kind (`_check_one_scheme_per_kind_of_run` `:137-162`).
  - It counts active lines that point at ARCHIVED schemes (NH95).
  - The base model also has a legacy uniqueness rule on (department, scheme), handled in `accept_draft`
    (`pb_scheme_map.py:1043-1071`, NH94).
- A pay run asks for its scheme's own kind (`pb_payrun_wizard.py:334`). "Paid by" asks for the main kind and for
  `mid_cycle` (`hr_employee.py:142-158`).
- The advance ↔ end-of-month pairing: `hr.payroll.cycle.component.mapping` (`mid_cycle_config_id`,
  `end_cycle_config_id`, one row per carried component). Read by:
  - `advance_once.py:78-110`
  - `payroll_import_batch.py:2291-2297,2531`
  - `updates_ytd.py:671-673`
  - `updates_oneoff.py:249`
  - `pb_blueprint/models/blueprint_connect.py:263`
  - It exists only where a carry-over is configured: zero rows means no derivable sibling.
- "Scheme family" = `_pb_scheme_family` (`advance_once.py:113-129`): the scheme, its `parent_branch_id` root and every
  `child_branch_ids` descendant (edit branches, `formula_config.py:220-245`). It is used only to stop an Extra run
  taking the advance twice. It is **not** the advance pairing. Do not reuse the word for it.

### 3.2 Options

| Option | Stores | Advance + regular both find the person | Cost / risk |
|---|---|---|---|
| **A. One row per scheme the person is on; the kind is DERIVED from `config_id.cycle_type`** (stored related) | `employee, config, date_from, date_to`; no free cycle field | The person rung builds `{config.cycle_type: row}` per person and uses the same `_pick` (`pb_scheme_map.py:222-250`). An end-of-month run finds the `end_cycle` row; an advance run finds the `mid_cycle` row. | Two rows for advance people. The fill copies `pb_paid_by_id` → row 1 and `pb_paid_by_advance_id` → row 2. No mismatch is possible between a row's kind and its scheme. Overlap rule: one live row per (person, kind) per day. |
| B. One row (the main scheme); derive the advance from `hr.payroll.cycle.component.mapping` | `employee, config, dates` | The advance run reads the mapping rows where `end_cycle_config_id = row.config`. | It breaks when zero or several advances map to one end scheme, or when the mapping is per-component only. It hides a pay fact inside setup data. A carry-over row deleted later silently drops people from the advance run. |
| C. One row with a free `cycle_type` (`any` …), cloned from map lines | `employee, config, cycle_type, dates` | As map lines | A row can say `end_cycle` while naming a `regular` scheme (map lines have the same weakness). It needs `_check_one_scheme_per_kind_of_run`-style checks. |

**Recommended: A.** It is cheaper (no inference, `_pick` reused as is) and safer (the advance is an explicit,
approvable fact). The pairing table is used only as the screen's DEFAULT for the advance row when the person's main
scheme has exactly one paired advance. Otherwise the default is the team's own advance line.

**Fall-through rule (needs a ruling, Q12-D2):** a person with own rows but no own row for the asked kind. Recommended:
the person rung answers `none` for that kind and the ladder does NOT fall through to team lines. That way a team's
Vietnamese advance line can never pay a person moved to Singapore. The fill writes advance rows for everyone who has
`pb_paid_by_advance_id` today, so nobody loses an advance on day one.

Two more points:
- `full_final` schemes: leave them out of person rows (inferred: they are per-leaver runs). The person rung answers
  `full_final` by falling through.
- The no-kind question (`'any'`) keeps `_pick`'s order: end_cycle, then regular, then full_final, then mid_cycle.

---

## 4. Where a person-level, dated assignment lives

| | (a) New model `pb.person.scheme` in `pb_scheme_map` | (b) Fields on `hr.version` / `hr.contract` | (c) Reuse `pb.work.segment` |
|---|---|---|---|
| Precedent to clone | `pb.division.link` (`pb_group/models/pb_division.py:269-325`): dated `date_from` (required, default today) / `date_to`, `active`, `_check_no_overlap` `:289-325` with a named sentence; `_links_on(on_date)` `:94-106` = the read | `hr.version` fields (`pb_contract_lifecycle/models/hr_typing.py:59`, R14); contract drawer terms `pb_contracts/models/pb_contract_360.py:82-115` | the model itself |
| Effective dating | native (`date_from` / `date_to`, many rows = history) | `hr.version.date_version` is one version per date per employee (`hr/models/hr_version.py:191-192`), with every other version field copied forward. `hr.contract` has `date_start` / `date_end`, but a change mid-contract needs a sub-row anyway. | month-bounded (§2): no |
| Read cost in `resolve_many` | one search per roster, like `_segment_schemes` | (b-version): version fields are NOT columns of `hr_employee` (R14: a raw SELECT fails); the roster SQL would need another join. (b-contract): the open contract only. | — |
| Approval hooks | new kind on `pb.schememap.proposal` (§5) | contract drawer: `_cd_propose` `pb_contract_360.py:1819` (process `contract`, `pb_contracts/models/contract_approval.py:33`); Records Desk process `records` | — |
| Import / Updates reach | needs a special target like `SCHEME_TARGET` / `WHEN_TARGET` (`pb_updates/models/updates_desk.py:65,68`) | employee fields reach the Records Desk as `f:hr.employee:<field>`, but **undated** (`DATED_GROUPS=('contract','component')` `updates_desk.py:74`) | — |
| Module rail | `pb_scheme_map` already depends on `pb_hr_payroll_formula` + `pb_group`; the wizard and formula engine stay independent (soft `in self.env` probes) | `pb_contracts` does not depend on `pb_scheme_map` (manifest) | pay factor side-effects |
| Risk | low: one new table, read by one rung | Two "employment records" exist on this build: ported `hr.contract` (`hr_contract/models/hr_contract.py:18`) is what pay reads, and Odoo 19 `hr.version` (`hr/models/hr_employee.py:43` `_inherits`). A scheme on either would follow THAT record's lifecycle (renewals, version copies). The VN-default gate trap (selection / boolean defaults on every employee read as evidence) applies to any defaulted field; a Many2one with no default avoids it. | changes pay; rejected |

**Recommended: (a).** A new `pb.person.scheme` in `pb_scheme_map`.

Fields:
- `employee_id` (required, index, cascade)
- `company_id` (related `employee_id.company_id`, stored)
- `config_id` (required, `ondelete='restrict'`)
- `cycle_type` (related `config_id.cycle_type`, stored, index)
- `date_from` (required)
- `date_to`
- `source` selection: `fill / hire / hand / team / import / job_change`
- `note`, `active`
- optional `contract_id` (empty now; the seam for the owner's "two-country split = second contract, later")

Constraints:
- no overlap per (employee, cycle_type), cloned from `_check_no_overlap`;
- the scheme's company is the employee's, or shared;
- no `full_final`.

Writes mark the person stale. A daily job marks people whose row starts or ends today (clone the shape of
`pb_job_change` `_cron_start_due` `job_change.py:1360`; the existing nightly recompute then settles them).

---

## 5. Approval and audit
- **Mapping board today.** `pb.scheme.board.attach` / `detach` / `accept_draft` / `accept_country_suggestions`
  (`pb_scheme_board.py:464-624`) call `_map_held()` (`:627-636`). That is True whenever `pb.schememap.proposal` exists
  and the context lacks `SCHEMEMAP_WRITE` (`'pb_schememap_approved_write'`, `schememap_approval.py:37`).
- It then calls `pb.schememap.proposal.propose(kind, title, payload, snapshot, facts, target).answer()`. The mixin is
  `biz_approval_workflow/models/proposal.py`: `propose` `:255-296`, `answer` `:298-326`.
- The engine `submit`s:
  - **Fast lane:** a route with a `fast` step, or none (`route_mode` `:193-223`), applies inside the same call.
  - Otherwise the result is "Sent for approval".
- On approval, `_approval_apply` (`:586-612`):
  - snapshot re-check (`_live_snapshot`, `_proposal_moved`);
  - gate on the final approver (`_proposal_check_gate` `:551-574`, groups `_proposal_gate_groups` =
    `pb_hr_payroll_formula.group_formula_manager`, overridable per kind via `_proposal_gate_xmlids` `:546-549`);
  - `_apply_<kind>` (`:576-584`);
  - an audit line `biz.audit.entry` (`:614`).
- Kinds today: `attach, detach, accept_draft, map_create, map_delete` (`schememap_approval.py:48-54`), applied through
  the board with `SCHEMEMAP_WRITE` (`:105-143`). Route seed: "Payroll manager" `role_step` (`:145-158`), process key
  `schememap`.
- **Add employee.** `pb.new.hire._values` (`studio.py:820-892`) puts `pb_nh_scheme_id` (`:854`) and names
  `scheme` / `scheme_note` into ONE `pb.newhire.proposal` (`pb_people_advanced/models/newhire_approval.py:54-157`,
  process `newhire`).
  - On apply, `create_ext._pb_nh_extra` (`pb_new_hire/models/create_ext.py:104-121`) carries `scheme_id` into the
    contract context. It is used ONLY for the usual answers (`_pb_nh_lines` `:186-221`).
  - **No scheme is written on the person.** The approver's card shows "Paid by" and "Who pays them"
    (`create_ext.py:312-313`).
- **Cheapest correct route for a person change:** add kind `person_set` to `pb.schememap.proposal`.
  - payload `{employee_ids, config_ids (main [+ advance]), date_from, company_id}`
  - snapshot: each person's live rows in force on `date_from`
  - fact `employees_moved`
  - `_apply_person_set` → a board method under `SCHEMEMAP_WRITE`
  - Same route, same fast lane, same audit.
  - Gate: decide whether HR managers may carry it out (`_proposal_gate_xmlids` per kind; Q12-D4).
- **The hire path writes the row inside the hire apply** (`source='hire'`, `date_from` = first day, §7 T1), with no
  second approval: the hire approver already sees "Paid by".

---

## 6. Screens that must show or edit it

### 6.1 Seams

| Screen | Today (file:line) | What changes | Precedent to clone |
|---|---|---|---|
| Employee side panel | rows `pb_employee_vault/models/employee_details.py:119-125` (`pb_paid_by_id` "Paid by", `pb_paid_by_advance_id` "Advance paid by" opt, `payroll_country` labelled **"Payroll country"**, not Country of Work); built by `_e360_details` `:242-285`; rendered read-only `pb_employee_vault/static/src/xml/employee_360.xml:162-169` | show "Pay scheme (from <date>)" + the next dated change; a link to change it | group replaced by a custom kind: `pb_employee_bank_panel/models/bank_panel.py:60-102` + `bank_panel.xml:11-20`; chip registry `pb_employee_360_chips` (`employee_360.js:63-75`); chip `scheme_map_chip.js:31-68` |
| Full details (native form) | `payroll_country` editable: `pb_hr_payroll_formula/views/hr_employee_views.xml:4,11`; `pb_employee_form_tidy/views/hr_employee_views.xml:21,35-41`; Paid by is NOT on the form | a Country of work change opens "Change the pay scheme from a date?" | — |
| Employee workspace Pay tab | `pb_form_studio_people/models/premium_section.py:36-37` (`SECTIONS['pay']`: `payroll_country`, `pb_paid_by_*`; only `payroll_country` is drawn, `native_section.py:41-42`) | the same prompt on a `payroll_country` save | — |
| Contract drawer | "Paid by" strip `pb_contracts/static/src/xml/contract_360.xml:355-372`; "Choose who is paid by what" `:400-407` → `openWhoIsPaidBy` `contract_360.js:1135-1145`; server `_cd_scope` `pb_contract_360.py:773-801`, `_cd_symbol` `:514-540`; terms `_TERMS` `:82-115` (no `payroll_country`); save `save_contract_360` `:1711`, `_cd_propose` `:1819` | the strip names the person's own scheme + its date; the button becomes "Change pay scheme" | dated custom terms via `pb_form_studio_contracts/models/contract_drawer.py:74-170` (`KIND` includes `date`); `pb_contracts` lacks the dependency, so use a soft probe or a bridge |
| Add employee step 2 | `_scheme_for` `pb_new_hire/models/studio.py:456-520`; amber lines in `decides` `:564-600`; `_why` `:395-404`; XML `new_hire_studio.xml:275,395,425,455` | `resolve_for_draft` gains the person rung judged on the draft's chosen scheme, so `honoured` is true whenever a country scheme is chosen. Retire "the pay run follows the team", "To pay them by X, pick one of its teams", "Set who pays <team> in Mapping…". Keep "No pay scheme for <country> yet". Write the person row on approval. | P8 §2.5 seam note |
| Mapping "Who is paid by what" | board `pb_scheme_map/static/src/js/scheme_map_board.js` (registered `:936`), rows `scheme_map.xml:142-247`, wire chip `:198-220`, attach dialog text `:337-339`, "Nobody pays these people yet" `:571-580`; server `attach` `pb_scheme_board.py:464-515`; "Suggest who pays each team" panel `scheme_map.xml:469-563`, JS `startCountry` `:765` … `acceptCountry` `:833` | re-word a team line as "Usual pay scheme for <team> (for people without their own)". Add "Set for everyone in this team…" as a second action beside attach: it writes `person_set` rows for the team's CURRENT people from a date (§5). Coverage reasons `pb_scheme_map.py:808-811` must also name "has their own scheme". | the `accept_country_suggestions` proposal path `pb_scheme_board.py:581-624` |
| Updates sheets | No writable scheme column. Lasting sheets: `SCHEME_TARGET='check:scheme'` (`updates_desk.py:68`, headings `updates_joiners.py:62-63`, `read_columns` `:1163-1201`). Joiner sheet: a CHECK against the team (`_judge_row` `updates_joiners.py:597-640` via `_department_schemes` `:219-268`). `updates_schemes.py` reads only. | the joiner sheet's "Pay scheme" becomes a VALUE (must be a scheme of the row's Country of work); a lasting-sheet "Pay scheme" column with the row's start date → `person_set`; `_department_schemes` must not decide anyone with own rows | `WHEN_TARGET='when:start'` (`updates_desk.py:65,442-466`) for the date |
| Job change / transfer | `pb.job.change` `pb_job_change/models/job_change.py:129-227`: `effective_date`, `new_department_id`, `new_company_id` …; **no country, no scheme**; `EMPLOYEE_MAP` `:90-98`; applies `_approval_apply` `:948-966` → `_write_change` `:1035-1160` (scheduled → `_start_scheduled` `:1327`, cron `_cron_start_due` `:1360`, undo `action_undo` `:1432`); what-if `_scheme_now_and_after` `:411-440` (no date) via `_departments_for` override `job_change_inherits.py:106-123` | add "new Country of work" + "new pay scheme" (from `effective_date`); `_write_change` writes a `person_set` row with `source='job_change'`; the what-if becomes "person row first" | its own dated / scheduled machinery |
| Pay data file import | `payroll_import_batch.py:1739,1815` `_create_employee` sets `payroll_country` from the batch scheme | also write a person row for the batch scheme (`source='import'`) | — |
| Hiring offer | `pb_pay_package/models/offer_total.py:165-176`: default scheme from the requisition TEAM's line | default from the offer's Country of work, as in Add employee | `_scheme_for` |

### 6.2 Every write path to `payroll_country`
Each one must offer or trigger "change the scheme from a date".
1. Full details form and Pay tab (native `web_save`), §6.1.
2. Records Desk / Updates lasting sheet `f:hr.employee:payroll_country`:
   - field list `pb_hr_payroll_formula/models/application_domain_sources.py:23`;
   - card `pb_records/models/master_records.py:12`;
   - write `pb_records/models/pb_records_desk.py:1659-1705`;
   - classed as pay in `pb_records/models/records_approval.py:58-62` (process `records`).
3. Mapping lane "job" (`pb_employee_form_tidy/models/country_of_work_import.py:216-221`) via `_update_employee_from_raw_data`
   (`payroll_import_batch.py:3599,3694`).
4. Pay data file creating a person (`payroll_import_batch.py:1815`).
5. "Fill empty Country of Work" (`pb_employee_form_tidy/models/country_of_work_fill.py:259-300`): fills only empties,
   and **derives the country FROM Paid by** (`_pb_plan` `:91-158`). It becomes circular once the scheme is pre-filled
   from the country, so run it BEFORE the scheme fill.
6. Add employee (`create_ext.py:59` `EMPLOYEE_EXTRA`, `:226-238`).
7. Not written by: `pb_zoho_bridge` (whitelist `zoho_pipeline.py:50-59`), `pb_job_change`, the portal
   (`pb_form_studio_people/models/form_studio.py:71`). The legacy Zoho staging is commented out
   (`pb_hr_payroll_base/models/__init__.py:7-8`).
8. `hr.contract.payroll_country` is written only by `create_ext.py:247-256` (Add employee) and an onchange
   (`hr_payroll_structure_base.py:339-343`). `pb_form_studio_contracts/models/hr_contract.py:8-9,56-73` calls it a
   "currency hint … NOT used".

The prompt hook: one `hr.employee.write` override in `pb_scheme_map` that, on `'payroll_country' in vals`:
- marks the person stale, which fixes today's gap;
- returns nothing to the screen.

The screens ask the question client-side before saving. The server never changes a scheme because a country changed.
That is inferred to be the owner's intent: "the screen should ask".

---

## 7. Pay-run date question
- Membership is judged on **`date_start`** (the first day of the period):
  - `scheme_preview` `pb_payrun_wizard.py:557`;
  - `_eligible_employees` `:728`.
- The contract filter before it is period overlap (`:693-707`): a contract open on any day of the period. A mid-month
  joiner is therefore in the base list, but the scheme check is made on the 1st.
- "Scheme in force on D" plugs in at `resolve_many(..., on_date)`: a new `_person_schemes(ids, on_date)` beside
  `_segment_schemes` (`pb_scheme_map.py:294-336`), called once at `:378`, answered between rung 1 and rung 2. The
  same goes into `resolve_for_draft` (`:537-567`) from `values['scheme_id']`.
- **T1 (decision needed, Q12-D1).** A row dated from a hire day (say the 15th) is not in force on the 1st. The hire's
  first run would miss the person rung and fall to the team / rule (or "none"). The same happens for a permanent move
  dated mid-month.
  - Options: snap `date_from` to the first day of its pay period; or judge person rows as "in force on the period's
    first day, else the first row starting inside the period".
  - Recommended: the second option, inside `_person_schemes` only. It leaves map-line date semantics as they are; the
    test `test_historical_rule_mapping_does_not_expand_later_payrolls` `pb_scheme_map/tests/test_scheme_map.py:137-157`
    pins those. Screens default a change to the 1st of next month.
- The payslip rung 3 (`hr_payslip_formula.py:464`) passes no date. It should pass `self.date_from` (same rule) when the
  person rung lands. It is reached only for payslips without a stamped scheme.
- "Paid by" is today's answer (`_pb_recompute_paid_by` passes no date). A future-dated row flips it only when something
  marks the person stale, hence the daily boundary job (§4).
- **Proration facts** (state only):
  - No engine splits one person's month across two schemes of the SAME company. NEWHIRE ledger: "no engine-wide joiner
    proration".
  - What exists:
    - (i) a scheme's `use_proration` + `proration_component_ids` (`formula_config.py:80-87`) prorates CONTRACT
      COMPONENT changes inside a period, from `hr.contract.advantage.change.effective_date`
      (`payroll_import_batch.py:2563-2600`; also `om_hr_payroll/models/hr_payslip.py:1713`);
    - (ii) `pb_workseg` derived joiner / leaver segments behind the company switch `prorate_joiners_leavers`
      (`pb_work_segment.py:870-960`), which cut the home factor (`:483-511`);
    - (iii) cross-company split days (rung 1 + `_segment_hosts` `pb_payrun_wizard.py:371-415`).
  - So a scheme change inside a period means the whole period goes to one scheme. That is a design fact for D1.

---

## 8. Reports and analytics that go through the TEAM

| Reader | file:line | Goes through | After the change |
|---|---|---|---|
| Coverage counts per scheme, missing per team | `pb_scheme_map.py:777-824` | `resolve_many`, so per person | counts become right automatically; the reason sentences `:808-811` and `by_department` stay team-worded |
| Pay-run scheme cards "people covered" | `pb_payrun_wizard.py:230-276` | `coverage` | right automatically |
| Pay-run approval scope headcount | `pb_payruns/models/hr_payslip_run.py:1074-1100` | `coverage` | right automatically |
| Joiner sheet scheme check | `pb_updates/models/updates_joiners.py:219-268,501` | **team → scheme, re-implemented** | WRONG once people in a team differ (§6.1) |
| Offer total default scheme | `pb_pay_package/models/offer_total.py:165-176` | **team line directly** | wrong for a person of another country |
| Add employee team grouping by scheme / country | `pb_new_hire/models/places.py:70-127` (`TEAM_RUNGS`), `studio.py:522-531` `_scheme_teams`, `_most_paid` `:435-454` | team lines | team ordering only; acceptable as a hint |
| Suggest / draft the map | `pb_scheme_map.py:615-759`, `:838-1029` | team by design | stays (bulk shortcut) |
| Fallback two-column board | `pb_formula_studio.py:10121-10240` | team lines | stays |
| Explorer facts | `pb_explorer/models/pb_fact_builder.py:108-134,834-841` | payslip `formula_config_id` / run `pb_formula_config_id` | correct |
| Decision Room | `pb_decision_room/models/pb_decision_room.py:419-440`, `pb_decision_scope.py:409-413`, `pb_decision_exact.py:252-260` | `pb_paid_by_id` | correct |
| Payroll analytics, results, ledgers, insights, AI cost | `pb_hr_payroll_analytics/models/hr_formula_config_analytics.py:188-199`, `pb_payrun_results/models/payrun_results.py:198,497`, `pb_payrun_ledgers/models/ledger_cockpits.py:109,221`, `pb_insights/models/pb_insights.py:512-516`, `pb_payroll_ai_insights/models/payroll_data_query.py:856-938` | payslip or run scheme | correct |
| Currency signs, report-builder currency | `pb_people/models/pb_people.py:51-67`, `pb_report_builder/models/subjects.py:107` | `pb_paid_by_id` | correct |

No other report joins `hr_formula_scheme_assignment` on department. Searched pb_group, pb_hr_workforce_planning,
pb_dashboard, pb_people_reports, pb_workforce_insights and pb_budget: none found.

---

## 9. The one-time fill (going forward only, per the scope note)

### 9.1 Query shape
Per company, active employees only (the roster SQL `pb_scheme_map.py:110`):
1. Recompute "Paid by" first: `hr.employee._pb_recompute_paid_by(company_ids=[c])`.
2. For each person:
   - Main row ← `pb_paid_by_id` (rung is not `none`).
   - Advance row ← `pb_paid_by_advance_id` (already filtered to department / division / rule rungs).
   - Both get `date_from` = the first day of the current pay period (so T1 never bites) and `source='fill'`.
3. Where `pb_paid_by_id` is empty, fall back to `payroll_country` → `_country_schemes(company, code)`
   (`pb_scheme_map.py:604-613`):
   - exactly 1 scheme → that one;
   - 0 or several → the review list ("No pay scheme for <country>" / "Pick one of N");
   - empty Country of work → the review list.
   Run "Fill empty Country of Work" first (§6.2 item 5).
4. Exclude `pb_demo` demo people on payobook from automatic writes or not? Decide D6. Their runs are division-driven
   and never read the map (`pb_demo/models/demo_payrun.py:114-160,312`).
5. Never overwrite a person who already has a row (re-read in the same transaction, as `country_of_work_fill.py:277`).

### 9.2 Known shapes (from the P8 report; counts must be re-taken on a copy, read-only)
- rize: 313 people; 231 active checked in P8; no team mapped; everyone is paid through per-country rules (rung 4).
  - India, Singapore and Indonesia rules read `payroll_country` (+ company).
  - The Vietnam rule is a list of employee codes, one of them limited to August 2026 (P8 §2.4).
  - So new Vietnamese joiners answer `none` today and take the Country-of-work fallback (VN has one scheme).
  - 8 scheme-map proposals are still waiting on rize (P8 §8.6). If approved after the fill they write team lines,
    which rank below person rows, so harmless.
- payobook (demo): 4,583 people. Company 5 Vietnam has 7 schemes (mid + end pairs, so many people get 2 rows).
- Local databases are not representative: `nh12_base` has 19 active people and 5 `any` team lines; local `rize` and
  `payobook` are September stubs. **Counts must be taken on a hidden copy of each live database:**
  - active people; with / without `pb_paid_by_id`; with an advance;
  - per rung: `pb_paid_by_rung` holds the via sentence, so count per sentence;
  - empty `payroll_country`; country with 0 / 1 / several schemes;
  - confirmed `pb_work_segment` rows with `config_id`.

### 9.3 Precedents to clone
- On-screen tool:
  - `pb.cow.fill.wizard` (`pb_employee_form_tidy/models/country_of_work_fill.py:59-300`): preview `_pb_plan`, the
    "left" list with reasons, `action_fill`, the log model `pb.cow.fill.log` `:46-56`;
  - plus the P8 "Suggest who pays each team" drawer: Can be set now / Needs your choice, ticked rows.
- Rehearse / apply script with undo: `docs/handovers/newhire/p8/nh8_map.py`
  - `NH8_MODE=dry|apply`; dry = everything rolled back;
  - before / after snapshot of every paying scheme;
  - the undo CSV is written at `:120-122`.
  Clone it as `pscheme_fill.py`, with `person_scheme_undo.csv` = the created row ids. Undo = unlink those rows only.

---

## 10. Tests that pin today's ladder, and lessons that say "the team decides"

### 10.1 Tests (need a deliberate update or a new case)
- `pb_scheme_map/tests/test_scheme_map.py` `TestSchemeMap` (`:33`):
  - `test_historical_rule_mapping_does_not_expand_later_payrolls` `:137`
  - `test_t1_the_ladder_climbs_in_order` `:160` (none, only, rule, division, team above, own team, kind beats any). Add
    the person rung here.
  - `test_t4_paid_by_is_worked_out_again_when_it_could_have_changed` `:311`
  - `test_t7_rule_8_one_scheme_and_no_map_changes_nothing` `:488`
  - `test_t8_the_payslip_ladder_asks_the_map` `:535`
  - `test_t9_the_pay_run_asks_which_scheme_and_writes_it_down` `:572`
  - `test_t11_paid_by_for_one_person` `:652`
- `pb_scheme_map/tests/test_static_contract.py:258` `test_t12_the_ladder_edit_is_guarded` (dependency rail).
- `pb_new_hire/tests/test_p8.py` `TestP8Scheme` (`:14`):
  - `test_a5_hand_pick_kept_with_a_note` `:89` asserts "…and the pay run follows the team.";
  - `test_a6_values_old_and_new_payloads` `:109`;
  - `test_a7_pay_run_takes_the_chosen_scheme` `:123`;
  - `test_a9_resolver_agrees_with_the_pay_run_in_every_branch` `:156` (rung set; add `person`);
  - `test_a4_unmapped_team_most_paid_and_honest` `:76`;
  - `test_a10` `:196`.
- `pb_new_hire/tests/test_p8.py` `TestP8Suggest` `:231` (b1–b5).
- `pb_new_hire/tests/test_new_hire.py`:
  - `test_t01_resolve_for_team_equals_resolve` `:158`
  - `test_t04_decides` `:220` ("Because DEMO NH Finance is paid by this scheme.")
  - `test_t16_team_defaults` `:483`
- `pb_job_change/tests/test_job_change.py:511` `test_jc12_paid_by_what_if_is_read_only`.
- `pb_updates/tests/test_updates_p3b.py:318` `test_H6_pay_scheme_column` (the team check); `test_updates_p2b.py:175-295`
  (team-line fixtures).
- `pb_hr_payroll_formula/tests/test_fillin_p1.py:351` `test_t10_paid_by_becoming_known_fills_the_contract`.
- Tests that write `pb_paid_by_id` directly survive (listed in the sweep):
  - `pb_contracts/tests/scheme_scope.py:42`
  - `pb_me_tax/tests/common.py:68`
  - `pb_decision_room/tests/test_decision_scope.py:209-212`
  - and others

### 10.2 Lessons, tours and replicas (standing rule: lessons follow screen changes)
- `pb_learn/static/content/learn_content.json`:
  - `:5841` (vi `:5842`): "The team you pick decides the pay scheme, and the currency and the trial period follow from it."
  - `:15353` (vi `:15354`): "…The team you pick then decides which pay scheme pays this person."
  - `:15337` "…Paid by on the right shows the scheme."
  - `:3462` "…the division people work in decides which rulebook pays them."
  - `:25294/:25298` "Who is paid by what"
  - `:34401/:34405` "Paid by names the pay scheme…"
- `pb_learn/static/src/anchors.json`:
  - `:2223` "…The team decides the pay scheme; the country is checked against it."
  - `:2304` `rep-newemp-team` "…choosing the team is choosing which pay scheme pays this person…"
- `pb_learn/static/src/engine/screens.js:405-411`: the new-employee replica runs Team, then "Paid by".
- Product help text in the same family:
  - `pb_new_hire/static/src/xml/new_hire_studio.xml:275` "…The team then decides who pays."
  - `:395` "The pay scheme follows the team…"
  - `pb_payrun_wizard/static/src/xml/payrun_wizard.xml:93-96` "Attaching their team to a scheme fixes everybody in it at once."
  - `pb_scheme_map/static/src/xml/scheme_map.xml:571-580`

---

## 11. Translations (vi and id)

| Module | Files | State |
|---|---|---|
| `pb_new_hire` | `i18n/pb_new_hire.pot`, `vi_VN.po`, `id_ID.po` | all strings below present and translated in vi + id |
| `pb_scheme_map` | `pb_scheme_map.pot`, `vi_VN.po`, `id_ID.po` | vi complete. **`id_ID.po` is a stub: 33 of 182 msgids.** |
| `pb_hr_payroll_formula` | `vi_VN.po`, `id_ID.po` | the proposal kind labels ("Wire a team to a scheme" …) are plain literals, never `_()`; `proposal.py:387-389` returns them untranslated |
| `pb_employee_vault`, `pb_contracts`, `pb_job_change`, `pb_payrun_wizard`, `pb_updates` | vi; id where present | `pb_contracts` has no `id_ID.po` |
| `pb_learn` | content JSON carries vi inline | no `id_ID` |

English source strings that change. Lines are .pot / vi / id.

`pb_new_hire`:
- "%(team)s is paid by %(run)s, and the pay run follows the team." 6339/6376/6376
- "No pay scheme pays %(team)s yet." 2992/3018/3018
- "Set who pays %(team)s in Mapping to make %(scheme)s theirs." 6429/6471/6468
- "%(scheme)s is used for the example. Set who pays %(team)s in Mapping so the pay run includes them." 6317/6350/6350
- "You can still add the person. Set who pays this team in Mapping before the first pay run." 5573/5599/5599
- "To pay them by %(scheme)s, pick one of its teams (they are listed first) or change who pays %(team)s in Mapping." 6497/6543/6541
- "The pay run will pay them by %(run)s, not %(scheme)s." 6459/6503/6500
- "%(scheme)s pays them through a rule on the map. Set who pays %(team)s in Mapping to make it the team's own." 6325/6360/6360
- "Because %(team)s is paid by this scheme." 1190/1216/1216
- "Because %(team)s's division is paid by this scheme." 1196/1222/1222
- "Pick the country of work first… The team then decides who pays." 6214/6240/6240
- "They follow the country of work. The pay scheme follows the team…" 6477/6521/6519
- "Who pays them" 6517/6565/6563

`pb_scheme_map` (pot / vi; id missing unless noted):
- "Paid by" 484/82
- "Advance paid by" 122/209
- "How that was worked out" 370/431
- "from %(team)s's team map" 853/892
- "from the %(division)s division" 865/904
- "from a rule on the map" 859/898
- "the only scheme in this company" 927/75
- "No scheme covers this person yet." 412/69
- "Their team is not attached to a scheme yet." 675/707
- "They are not in a team, so no team map can reach them." 687/719
- "Everyone in this part of the business will be paid by the scheme you pick…" 334/396
- "Suggest who pays each team" 1121/1309 (id 203)
- "Who pays each team, by country of work" 1133/1321 (id 215)

New strings will need vi + id. Follow the PO loading rules (memory: three things a PO entry needs; parse gate). The
`pb_scheme_map` id file needs a fill pass.

---

## 12. Risks and traps (most dangerous first), and questions for the designer

### 12.1 Traps
- **T1. Mid-period dates silently drop people from runs.** Membership is judged on `date_start` (§7). The pay run
  covers only `answer == run scheme` (`pb_payrun_wizard.py:343`). A person answered by ANOTHER scheme is neither
  covered nor listed as "not covered" (`:345` lists only blank answers). A wrong person row makes someone vanish from a
  run with no warning.
  - Mitigation: the D1 rule.
  - Recommend adding a third list, "paid by another scheme this month", to `scheme_preview`.
- **T2. The advance allow-list is in three places** (`hr_employee.py:155-158`, `pb_scheme_board.py:690-692`,
  `scheme_component_scope.py:114-115`, and they already disagree on `segment`). Add the new rung name to all three,
  ideally behind one constant in `pb_scheme_map`. Otherwise person advance rows never show as "Advance paid by" and
  are left out of `schemes_for_employee`, which feeds the pay items, the contract drawer, take-home and tax.
- **T3. Stale flags.** Nothing marks stale on `payroll_country` writes, segment writes or dates passing. A
  future-dated row needs a daily boundary mark. Until then "Paid by", currency signs (`pb_people._pay_symbol`) and
  pay-item scope show the old scheme. Also note `_pb_mark_paid_by_stale`'s GR13 order (flush, then SQL, then
  `invalidate_all(flush=False)`).
- **T4. Raw SQL roster and `flush_all`.** `_departments_for` is SQL (NH4). The new `_person_schemes` must read with the
  ORM, or flush first. Any writer that then resolves in the same transaction (the hire apply, the fill) must call
  `env.flush_all()`.
- **T5. A rule line ignores kind of run** (§1.1). On rize every person resolves through rules. After the fill, person
  rows take over, so a rule matters only for people with no row. Keep the fill complete.
- **T6. Contract currency follows `hr.contract.payroll_country`, not the scheme** (`hr_payroll_structure_base.py:296-303`).
  A person moved to another country's scheme keeps the old contract currency unless the contract country also changes
  (multi-currency memory: no total ever adds two currencies).
- **T7. The FILLIN usual answers run only for people "newly known"** (`hr_employee.py:177-187`). A scheme CHANGE does
  not fill the new scheme's usual answers, and old-scheme component lines stay on the contract (inferred; check
  `contract_fill_in.py`).
- **T8. Two kinds and two rows.** An advance-scheme person needs 2 rows. Every screen that changes "the" scheme must
  change both, or say which.
- **T9. `pb_demo` runs bypass the map** (division-driven `prepare_run`, `pb_demo/models/demo_payrun.py:312`). On
  payobook, person rows will not decide demo runs. Do not "fix" that; the demo stays as it is (memory: keep demo data,
  demo world not auto-classified).
- **T10. Circularity.** "Fill empty Country of Work" derives the country from Paid by (§6.2 item 5). Once Paid by is
  person-owned and pre-filled from the country, run that fill first and never the other way round.
- **T11. `pb_paid_by_rung` stores the via sentence, not the rung.** Counting by rung needs `resolve_many`, not the
  column.
- **T12. Dependency rail.** The formula engine and the wizard reach the map only through `'pb.scheme.map' in self.env`.
  New code there must keep that (`test_t12`).
- **T13. `_check_one_scheme_per_kind_of_run` counts archived schemes (NH95), and `accept_draft` unlinks clashes (NH94).**
  The "Set for everyone in this team" action must write person rows, never go through `accept_draft`'s replace path.

### 12.2 Questions for the designer, each with a recommended answer
- **D1. Which date decides the scheme for a period?** Recommended: the row in force on the period's first day, else
  the first row starting inside the period (one rule, inside the person rung only). Screens default changes to the
  1st of next month. A change inside a period applies to the whole period, because no engine splits one month across
  two schemes of one company.
- **D2. A person with their own regular scheme but no own advance:** fall through to the team's advance line, or no
  advance? Recommended: no advance (no cross-country leak). The fill copies today's advances, and Add employee offers
  the paired advance.
- **D3. "Set for everyone in this team" (the shortcut):** does it override people who already chose their own scheme?
  Recommended: it updates the team's usual scheme (a team line, the fallback for future joiners). It then offers,
  unticked, "also move the N people of this team who have their own scheme, from <date>", with each move as a
  person row (`person_set`).
- **D4. Who may change a person's scheme?** Today's gate is the payroll-manager group plus the "Who is paid by what"
  route. Recommended: the same route; HR managers may PROPOSE, a payroll manager carries it out (unchanged gate), with
  the fast lane where no second approver is set.
- **D5. Must Country of work become dated too?** Today it is a plain field: tax and insurance boxes, the trial period
  and the checklist follow it at once. Recommended: no. Only the scheme is dated, and the Country of work prompt
  offers the scheme change from a date.
- **D6. Demo people on payobook in the fill?** Recommended: fill them (seeds only add); their runs ignore the rows anyway.
- **D7. `full_final` (final settlement) schemes on person rows?** Recommended: not stored; those runs keep using the
  ladder.
- **D8. A person moved to another company** (job change `new_company_id`): a scheme must belong to the person's
  company. Recommended: the job change writes a new row for the new company's scheme, from its effective date. The
  old row ends the day before.
