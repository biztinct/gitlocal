# LEARNING L2 — Required training and country packs

Programme: LEARNING. Design page `docs/design/rize-learning-blueprint.html` §5 "Required",
§6 "A requirement rule", §7 phase L2. Ledger `docs/handovers/learning/LEARNING_LEDGER.md`
is binding (L1–L8, LD1–LD4, LN1–LN15 + L1's rows). Predecessors: `L0_REPORT.md`,
`L1_REPORT.md` — take the Learning hub registry, the Overview facade, the certificate
record fields (`pb.employee.document` + training fields) and the renewal leg from the L1
report, not from memory.

Owner decision LD4 (2026-10-21): **all four country packs ship in this phase** (Vietnam,
India, Indonesia, Singapore).

Report back to `docs/handovers/learning/L2_REPORT.md` (same template as L0 §9).

## 1. Scope

**Goal.** The system can answer "who must hold what, and who is missing it" for any job,
department, site, country or safety group, show it as a live matrix, chase the gaps itself,
and encode the four countries' statutory training rules as switch-on packs.

**In scope.**
1. New model `pb.training.requirement` (§3.1): audience × target × validity × cadence, with
   kinds `always` (hold at all times), `day_one` (within N days of joining), `recurring`
   (every N months), `statutory` (a pack row). Day-one rules and recurring schedules keep
   working; new ones are created as requirements (§3.2).
2. A new employee field **safety group** (`pb_safety_group`, Vietnam groups 1–6, blank
   elsewhere) on the employee form and the People drawer chip (§3.3).
3. **Hours**: a course carries hours (`pb_hours` override of the stock total time);
   an assignment stores `hours` when it finishes; a certificate stores `hours` (§3.4).
4. **The matrix** (§4.1): people × requirements, cells valid / expiring / missing / in
   progress / not due, filters by site, department (tree), job, country, safety group,
   requirement; click a cell to assign now; spreadsheet and PDF for an auditor; row cap and
   paging for 500+ people.
5. **Enforcement leg** in the daily job: for every missing cell whose requirement has
   `auto_assign`, create the assignment (reason `required`), with due date = joining date +
   `due_days` for day-one, else today + `due_days`; never a second open one (§3.5).
6. **Country packs** (§3.6): data shipped per country, switched on per company from a new
   "Required training" Settings card; each pack = requirement templates + its report
   (Vietnam renewals due in 30 days with the six groups and hours; India awareness-session
   attendance register; Indonesia licence register; Singapore training hours by course and
   person).
7. REQUIRED lens rebuilt (§4.2): Matrix · Rules · Day one · Comes round again as inner
   tabs; the stock forms stay as admin fallbacks off-menu.
8. Overview compliance tiles and headline fragment; Numbers "Required" section and the
   statutory exports (§4.3).
9. Trainer access mismatch fixed (§3.7). Day-one rule department match made consistent
   with schedules (child_of) (§3.2).
10. Demo data (§6), tests T1–T16 (§7), **risky-tier** deploy (new tables, employee field,
    migration; §8).

**Binding non-goals.** No sessions, sign-offs, paths, skills, feedback (later phases). No
clock-in gating. No native `event` module. No change to `pb_compliance_hub` (it has no
registry for outside tabs — F8). No change to how an assignment is chased or how a claim
becomes money. No Zoho field writes (`job_id` stays Payobook-maintained — F9).

## 2. Verified plumbing facts (do not re-derive)

| # | Fact | Where |
|---|---|---|
| F1 | Employee work fields live on `hr.version` via `version_id` (`hr/models/hr_employee.py:43`); ORM domains only, never raw SQL on `hr_employee` columns (`pb_contract_lifecycle/models/hr_typing.py:16-23`). Fields: `department_id` :116, `job_id` :119, `employee_type` :108-115 (+ `intern` added by pb_contract_lifecycle), `work_location_id` → `hr.work.location` :131 (name, company_id, location_type, address_id required), `country_id` = **nationality** :60, `company_country_id` related :171. **No site/plant/estate/region field exists in pb_*.** Demo "sites" are department names ("Site - Project Alpha", "Assembly Line A", "Fleet - HCMC"…, `pb_demo/models/demo_catalog.py:275-302`). `work_location_id` is never populated by pb_* or Zoho. | `hr/models/hr_version.py` |
| F2 | Country resolver precedent `pb.probation.policy._employee_country` (`pb_probation/models/probation_policy.py:88-99`): work address country → nationality → company country; `policy_for` (:102-118) picks the country row first then the catch-all; data per country with `ref="base.vn"` and no company (`data/probation_policy_data.xml`). Per-country data-file precedent with `noupdate="1"`: `pb_pack_vn/data/legislation_pack_vn.xml:13-24`. **Use work address → company country only** (skip nationality: a Vietnamese national working in Singapore is under Singapore rules). | |
| F3 | `pb.training.rule` (day one): `name, sequence, company_id, channel_ids (M2M), due_days 14, department_ids, job_ids, active` (`schedule.py:34-95`); `_matches` (:89-95) is an **exact department match** (no child_of) — inconsistent with schedules. Applied by `journey_ext.py:39-105` (`training_day1` automation; switch `pb_training.day1_auto` default '0'; one assignment per course, reason `day_one`, `rule_id` set; skips anyone with an open assignment). Checklist step `data/journey_step.xml:26-36` (noupdate). | `pb_training` |
| F4 | `pb.training.schedule`: `name, channel_id, audience (company/department/job/everyone), department_id, job_id, every_months 12, due_days 30, next_run, last_run, last_count, active, company_id` (:98-133); `_people()` (:151-169, department = `child_of`, everyone = no filter at all); `run_now()` (:171-244) skips no-login / open assignment / already assigned by this schedule since `today − every_months + 1 day`; creates rows directly with reason `compliance`, `schedule_id`; roll-forward of `next_run`. Nightly `_run_schedules` (`automation.py:132-144`). | |
| F5 | Board verbs for the two tabs: `open_schedules, new_schedule, open_rules, new_rule` (`pb_training_assignments.py:43-49`), **no edit, no per-row run-now**; "New" opens stock forms via `_door` (:348-409); tables `_schedule_rows` :187-205, `_rule_rows` :207-218; `training_board.xml:439-578`. **Access mismatch:** verbs gate on `_require_write` = `_can_read` (trainer tier allowed) but ACL gives trainers read-only on rules/schedules (`ir.model.access.csv:10,13`) → the form cannot be saved. | |
| F6 | Grid precedent: `pb_schedule` roster — server `get_schedule_data` (`pb_schedule/models/schedule_grid.py:176-314`) returns `{days, employees:[{… shifts:{date:[card]}}], truncated, row_cap}` with `WF_ROW_CAP = 200` (:50) and a "Showing N of M — narrow by department" banner (`xml/pb_schedule.xml:149-155`); CSS grid `grid-template-columns: 232px repeat(n, minmax(112px,1fr))` (`pb_schedule.js:237`) in a scrolling wrapper (`scss/pb_schedule.scss:374-381`); sticky header `.pbsc-h {position:sticky; top:0; z-index:3}` (:388-391), sticky first column `.pbsc-emp {position:sticky; left:0; z-index:2}` (:483-486), corner `.pbsc-h--emp {left:0; z-index:4}`; cell state classes. Windowed 4,500-row precedent: `pb_records/static/src/js/records_grid.js` (`ROW_H 46`, `PAGE 100`, `MAX_WINDOW 120`), pages fetched on scroll (`records_desk.js:325-351`). | |
| F7 | Spreadsheet download precedent: `analytics.export_xlsx` (:398-507) returns `{file_b64, filename, mimetype}`; the browser builds a data URL (`training_numbers.js:201-218`), no route, no attachment. PDF-from-board precedent: transient `pb.budget.export` (`pb_budget/models/budget_export.py:30-70`), `_pdf` (:190-214) renders `pb_budget.report_budget_year_document` **without sudo** (company mixing) and returns base64; explicit `ir.actions.report` record (`report/budget_report.xml:6-13`); template `web.external_layout` + `doc.board()`. | |
| F8 | `pb_compliance_hub` tabs are hard-coded (`compliance_hub.js:101-128`) with a test fixing their order; no outside registry. Do not touch. `LEARNING_LENSES` and `INSIGHTS_LENSES` are the registries to use. | |
| F9 | Employee field precedent: `pb_probation/models/hr_employee.py:42-48` (`pb_probation_state` Selection, `index=True, tracking=True, groups='hr.group_hr_user'`); form page precedent `pb_payroll_mapping_vn/views/hr_employee_views.xml:9-41` (inherit `hr.view_employee_form`, xpath `//notebook` inside, anchor on fields never on `@string`); People drawer header chip registry `pb_employee_360_chips` (`pb_employee_vault/static/src/js/employee_360.js:46-63`), precedent `pb_workseg/static/src/js/workseg_chip.js:26-58` (`orm.silent.call(MODEL,"chip_for",[empId])`). Zoho writes only `name, work_email, work_phone, job_title, department_id, parent_id, gender` (`pb_zoho_bridge/models/zoho_pipeline.py:50-59`) — never `hr.job`; custom `pb_*` employee fields are Payobook's (RIZE_LEDGER D8). | |
| F10 | Hours: `slide.channel.total_time` (stock, sum of lesson `completion_time`, auto-filled from YouTube/PDF pages, may be 0); `pb.my.training` shows `duration_words(minutes(channel.total_time))` (`pb_my_training.py:163`); helpers `minutes()`/`duration_words()` at `training_common.py:368-392`. Assignments and certificates store no hours. Course 27's durations are unverified on the DB. | |
| F11 | `hr.job`: no custom fields in pb_*; stock `job_skill_ids` from `hr_skills`. Demo jobs on company 5: Machine Operator, Production Operator, Line Leader, Quality Inspector, Maintenance Technician, Driver, Warehouse Operative, Construction Worker, Steel Fixer, Safety Officer, Site Engineer, Foreman, Store Supervisor, Cashier (`demo_catalog.py:277-302`). Demo departments: Retail, Manufacturing, Logistics, Corporate Office, Information Technology, Construction and their children; live also has 656 Facilities, 657 Quality Assurance. | |
| F12 | Assignments: `reason`/`rule_id`/`schedule_id` set by the creators (`journey_ext.py:87-95`, `schedule.py:213-221`), both `ondelete='set null'`; analytics "Why" groups by reason label (`analytics.py:291-292`); board "Why:" chips counted from rows (`pb_training_assignments.py:155`); the row payload has `reason_word` but no rule/schedule name (`assignment.py:529-555`). `ASSIGN_REASONS` gains `renewal` in L1. | |
| F13 | Settings: `pb_training` registers **no** Settings card; switches are `ir.config_parameter` rows from `DEFAULTS` (`training_common.py:60-127`, created by `hooks.py:89-99`). Registry `SETTINGS_CATEGORIES = "pb_settings_category"` (`pb_settings/static/src/js/settings_hub.js:256-309`, `GROUP_OF_CATEGORY` has no learning entry — add one under the `hr` group); card precedent `pb_lifecycle/static/src/js/lifecycle_palette.js:57-71`; multi-card with `xmlid` doors `pb_hiring/static/src/js/hiring_palette.js:114-139`; server gate `pb_settings/models/pb_settings.py resolve_gates` (:109). | |
| F14 | Test style: `TrainingCase` (`tests/test_training.py:48-164`), `AssignmentCase.setUpClass` (`tests/test_assignments.py:38-116`: `person(tag, name)` helper, survey questions via `question_and_page_ids` (R171), `_finish(user, channel, lessons)`), rule fixture :537-543, schedule tests :625-695 calling `self.Auto._run_schedules(today)`; `@tagged('post_install','-at_install')`; fixture names "DEMO …"; force `lang='en_US'` (LN14). | |
| F15 | Daily job legs and `_leg()` savepoint pattern, `reminder_cap`, `_hr_email` — see L1 handover F7. The L1 renewal leg is the template for the enforcement leg. | |

## 3. Architecture

### 3.1 `pb.training.requirement` (new, `pb_training/models/requirement.py`)
- Identity: `name` (translate), `code` (Char, unique per company, used by packs), `kind`
  Selection `always / day_one / recurring / statutory`, `pack_key` (Char: `vn_osh`, `in_posh`,
  `id_k3`, `sg_hours`, empty for own rules), `active`, `company_id` (required), `sequence`,
  `note` (Html, plain help for the matrix tooltip, e.g. the legal reference).
- Audience (all optional; empty = everyone in the company): `department_ids` (child_of),
  `job_ids`, `employee_types` (Char CSV of `employee_type` values; helper selection widget),
  `work_location_ids`, `country_ids` (work country via the F2 resolver without nationality),
  `safety_groups` (Char CSV of `1..6`), `include_contractors` Boolean (default True: India
  POSH covers them; the matrix shows them).
- Target: `target` Selection `course / certificate / licence / hours`; `channel_id` (course),
  `survey_id` (optional: the test whose certificate counts), `document_category_id` + `name_pattern`
  (for `certificate`/`licence`: a vault document in that category whose name contains the
  pattern, e.g. "Forklift"), `hours_required` (Float, for `hours` and for VN initial hours).
- Timing: `validity_months` (0 = never expires; overrides the test's validity for this
  requirement), `due_days` (how long someone has once they fall due; default 30),
  `every_months` (recurring only), `grace_days` (matrix shows "expiring" inside this window
  before expiry; default = `pb_training.renew_before_days`), `refresher_channel_id` (optional
  different course for the renewal), `refresher_hours` (VN: % of initial → stored as hours).
- Behaviour: `auto_assign` Boolean (default True for own rules, False for packs until the
  company switches the pack on), `counts_for_probation` Boolean.
- Links: `rule_id` / `schedule_id` (M2o, set null) when the row was created from a legacy row
  (§3.2).
- Methods: `_people()` (sudo, active employees in company matching the audience; department
  `child_of`; `employee_type` filter; `work_location_id`; country via resolver; safety group),
  `_status_for(employee, today)` → `{state: valid|expiring|missing|in_progress|not_due|exempt,
  valid_until, evidence: {kind: assignment|document, id, words}}` evaluating, in order: an
  unrenewed vault document matching the target with `expiry_date` ≥ today (valid; expiring
  if inside `grace_days`); a `done` assignment on the course within `validity_months` of
  `completed_on` (valid/expiring); an open assignment (in_progress); day-one not yet due
  (`not_due` when joining date + due_days > today and nothing done); else `missing`.
  `evaluate(employees=None)` returns the matrix rows for the given people (used by the lens,
  the leg and the exports). Keep it set-based: prefetch assignments and documents in two
  reads per call, never per cell.

### 3.2 Legacy rules and schedules
- Migration `19.0.1.6.0/post-requirements.py`: for each active `pb.training.rule` create one
  requirement per course (`kind=day_one`, `due_days`, departments, jobs, `rule_id`); for each
  active `pb.training.schedule` one requirement (`kind=recurring`, `every_months`, `due_days`,
  audience mapped, `schedule_id`, `validity_months = every_months`). Idempotent (match on
  `rule_id`/`schedule_id`).
- The legacy models stay and keep running (the journey step and the nightly schedule leg
  are untouched) so nothing regresses; the enforcement leg skips a requirement that has
  `rule_id`/`schedule_id` set (their own mechanism assigns). The REQUIRED lens's "Day one"
  and "Comes round again" inner tabs now **create requirements** (`kind=day_one` /
  `recurring`) through a drawer instead of stock forms; the old rows are listed read-only
  with a "Converted" chip. Fix F3: `rule._matches` uses `child_of` for departments (one line;
  add a test).

### 3.3 Safety group on the employee (`pb_training/models/hr_employee_ext.py`)
- `pb_safety_group` Selection `1..6` with plain labels: "Group 1 — Managers", "Group 2 —
  Safety officers", "Group 3 — Strict-safety jobs", "Group 4 — Other workers", "Group 5 —
  Health staff", "Group 6 — Safety-hygiene officers" (VI per the decree's wording),
  `groups='hr.group_hr_user'`, `tracking=True`, `index=True`, help text names the Vietnam
  decree. Form: a field after `employee_type` (F9 precedent). People drawer chip via
  `pb_employee_360_chips` ("Safety group 3") shown only when set. Bulk tool: on the matrix
  "Set safety group" for the selected rows (verb `set_safety_group(ids, group)`), training
  manager only.
- `work_location_id` is shown in the matrix filter as "Site" and in the People drawer chip
  when set; the handover does **not** add a site register (owner item: Rize decides whether
  sites are work locations or department names — the matrix supports both).

### 3.4 Hours
- `slide.channel.pb_hours` Float ("Hours", override; empty = stock `total_time` in hours)
  on the course form; `pb.training.assignment.hours` Float stored at the `done` crossing
  (from the course's hours at that moment); `pb.employee.document.hours` (L1 record) set for
  test certificates from the course; uploads take an optional hours field.
- `pb.my.training` tiles and the record PDF show hours; analytics gains `hours_total` and
  per-person hours (Singapore export).

### 3.5 Enforcement leg (`automation.py`)
- Leg 5 `_enforce_requirements(today)`: for every active requirement with `auto_assign` and
  no `rule_id`/`schedule_id`, for every person in `_people()` whose status is `missing` (or
  `expiring` with a `refresher_channel_id`/course target), create the assignment (reason
  `required`, new value in `ASSIGN_REASONS`, VI "Bắt buộc"; `requirement_id` new M2o on the
  assignment; due date per §1.5) in a savepoint; respect `_guard_one_open`; cap per run
  `pb_training.enforce_cap` (default 500) with a counts dict. The L1 renewal leg must not
  double-assign the same person for the same course: the enforcement leg skips when an open
  assignment exists (the guard already does), and the renewal leg skips documents whose
  course has a requirement with `auto_assign` (one owner per course).
- Reminders and escalation apply unchanged.

### 3.6 Country packs (data + report each; `pb_training/data/pack_<cc>.xml`, noupdate=1, company_id empty = template)
- A pack is a set of **template** requirement rows (`company_id` empty, `active=False`,
  `pack_key` set) plus a per-company "pack switch" (`ir.config_parameter`
  `pb_training.pack.<cc>.<company_id>` = '1'). Turning a pack on (Settings card, §4.4) copies
  the templates into that company (`auto_assign=False` by default — HR reviews the rows and
  switches auto on per row), tagging `pack_key`; turning it off archives the copies; copying
  is idempotent (match on `pack_key + code + company`).
- Pack rows need courses/certificates to exist: each template names the target by
  `name_pattern` on a certificate/licence (works with uploads from day one) and leaves
  `channel_id` empty; the matrix shows "No course linked — link one" on such rows (quiet,
  not red) until HR links a course in the drawer.
- **The exact rule tables for the four packs are in §3.6.1–3.6.4 (filled from the verified
  statutory research; if a line says UNVERIFIED, ship it as a template row with `note`
  saying "confirm with Rize" and `active=False` after copying).**

#### 3.6.1 Vietnam — `vn_osh` (Decree 44/2016/NĐ-CP, amended 140/2018; fire: Decree 105/2025/NĐ-CP, in force 1 Jul 2025; first aid: Circular 19/2016/TT-BYT)
Legend: [P] read from the primary text; [S] secondary source; [U] unverified → template row ships `active=False` with note "confirm with Rize".

| code | Who (audience) | target | initial hours | validity / cadence | refresher | issuer / evidence |
|---|---|---|---|---|---|---|
| `vn_osh_g1` | safety group 1 (managers, deputies in charge of OSH) | certificate "OSH group 1" | 16 [P] | 24 months [P] | 8 h (50%) every 2 years [P] | training provider certificate → upload |
| `vn_osh_g2` | safety group 2 (OSH staff, direct OSH supervisors) | certificate "OSH group 2" | 48 [P] | 24 months [P] | 24 h [P] | provider certificate → upload |
| `vn_osh_g3` | safety group 3 (strict-OSH jobs, MOLISA list Circular 06/2020, 32 jobs [S]) | licence "Safety card" (`LIC`, pattern "Safety card") | 24 [P] | 24 months [P] | 12 h [P] | **employer issues the card** after a pass [P] → the certificate record from our own test counts; print the card (Form 06/08 [U]) |
| `vn_osh_g4` | safety group 4 (everyone else incl. apprentices, probation) | course (`always`, our course; no certificate) | 16 [P] | **12 months** [P] | 8 h yearly [P] | employer's own record (Form 11 book) [P] = the assignment |
| `vn_osh_g5` | safety group 5 (occupational-health staff) | certificate "OSH group 5" | 16 (Decree 140/2018) [P/S] | 24 months [P]; OH profession certificate 60 months [P] | 50% | provider → upload |
| `vn_osh_g6` | safety group 6 (safety-hygiene representatives) | certificate "OSH group 6" | +4 on top of own group [P] | 24 months [P] | 50% | provider → upload |
| `vn_osh_retrain` | any group, trigger rule: job/equipment/technology change → retrain before the new assignment unless trained < 12 months ago; absence > 6 months → retrain at 50% hours (Art 21.3) [P] | (rule only: the matrix marks `missing` when `job_id` changed after the last pass or `completed_on` < return date − 6 months [U on how we detect absence: use contract/leave gaps if available, else skip]) | | | | |
| `vn_fire_g1/g2/g3` | fire groups [S]: 1 = facility heads, workers in fire/explosion-risk areas, vehicle operators; 2 = facility fire brigade; 3 = fire inspectors, specialised brigade | certificate "Fire training group N" | 8–12 / 16–24 / 24–32 [S] | **60 months** full cycle + **12-month** refresher [S] | 4–8 / 4–8 / 8–12 h yearly [S] | Public Security bodies → upload [S]; `active=False` until Rize confirms |
| `vn_first_aid` | first-aiders: headcount rule (strict-OSH site: ≥1 per 100 workers [S/U 150]; others ≥1 per 150 [S]); all workers 4 h [S] | certificate "First aid" 16 h [S]; course for all workers 4 h | 16 / 4 | 12 months retraining [S] | [U] | employer-organised → our course or upload; `active=False` (ratio unverified) |
| `vn_renewals_report` | report: everyone whose certificate/card expires within **30 days** (legal duty to list them to the trainer, Art 25.2 [P]) | columns: person, group, course/card, hours done, valid until, card number, trainer | | | | Numbers › Country reports › Vietnam |

Encode: expiry = issue date + 24 months (12 for group 4); "expiring" window 30 days (the legal list) in addition to the general `grace_days`; the Vietnam export is the §4.3 "Renewals due in 30 days".
Needs Rize to confirm (owner items): group-3 job list; first-aider ratio (100 vs 150) and annual hours; fire-group per site and whether Decree 347/2026 applies; safety-card form number.

#### 3.6.2 India — `in_posh` (POSH Act 2013 s.19(c), Rules 2013 r.13/r.14, s.21; Factories Act 1948 s.41C/s.111A; OSH Code 2020 in force 21 Nov 2025, central rules 8 May 2026 [S])

| code | Who | target | cadence | evidence | report |
|---|---|---|---|---|---|
| `in_posh_all` | every employee **including contractors, interns, consultants** (`include_contractors=True`, employee_type any) | course "Harassment-awareness session" (`recurring`) | law says "at regular intervals" with **no fixed frequency** [P/S]; pack default **12 months**, a company setting | the finished assignment (session attendance) | counted into the annual report |
| `in_posh_ic` | Internal Committee members (a job or a Boolean tag `pb_posh_ic_member` on the employee — add the Boolean, HR sets it) | course "Internal Committee orientation" (`recurring`, 12 months default) | r.13 orientation + capacity building [S] | assignment | |
| `in_posh_report` | report per company per **calendar year**: number of awareness sessions held, attendance register (person, type incl. contractor, date, evidence) | | due date = **per-location setting, default 31 January** (no statutory date; District Officers set 31 Dec–28 Feb [S/U]); nil report still required [S]; fine up to ₹50,000 (s.26) [S] | | Numbers › Country reports › India |
| `in_hazardous_medical` | workers in hazardous processes (job tag, `active=False` by default) | companion rule, not training: medical exam before assignment and ≤ 12-monthly (s.41C) [P] | 12 months | licence/certificate upload "Medical fitness" | |
| `in_mock_drill` | Maharashtra factories: mock drills every 6 months (2025 amendment r.73-ID) [S/U] | course/session "Mock drill" `recurring` 6 months, `active=False` | | | |

Needs Rize to confirm: each office's District Officer deadline; whether any site is a hazardous-process factory or a construction establishment; state rules (Maharashtra 6-monthly drills) that apply.

#### 3.6.3 Indonesia — `id_k3` (Permenaker 8/2020 lifting equipment; Permenaker 4/1987 → 13/2025 P2K3; Permenaker 38/2016; Kepmenaker 186/1999 fire; UU 1/1970 Art 9)

| code | Who | target | validity / cadence | evidence | notes |
|---|---|---|---|---|---|
| `id_lic_lifting` | operators, technicians and riggers of lifting/transport equipment (forklift, crane, hoist) — jobs tagged by HR | licence `LIC` pattern "Lisensi K3" / "SIO" | **60 months**, renewal application **≥ 30 days before expiry** (Art 162) [P] | upload (Dirjen Kemnaker issues) | licence is valid only while employed by the applying company (Art 163) [P] → the matrix flags `missing` when `company_id` changed after issue |
| `id_ak3u_skp` | the appointed general OSH expert(s) (Ahli K3 Umum; job "Safety Officer" or tag) | licence pattern "SKP" | **36 months** (Permenaker 4/1987 Art 11(1)) [P]; lapsed > 1 year → full course again [S] | upload | reminder 60/30/7 as L1 |
| `id_ak3_lifting_skp` | company lifting-equipment expert | licence pattern "SKP Pesawat Angkat" | 36 months (Art 162(1)) [P] | upload | |
| `id_lic_production` | operators of power/production machines | licence pattern "SIO" | 60 months [U — Permenaker 38/2016 scanned; partly revoked by 11/2026] | upload | `active=False` until confirmed |
| `id_k3_induction` | every new worker (`day_one`, due 1 day) | course "K3 induction" | no legal re-cadence (UU 1/1970 Art 9) [S] → company setting, default none | assignment | |
| `id_fire_warden` | headcount rule: **≥ 2 fire wardens per 25 workers** (Art 6(1)) [P]; fire team + fire K3 specialist when ≥ 300 workers or moderate-II/III/heavy risk site (Art 6(2)) [P]; coordinator 1 per 100 workers (Art 6(3)) [P] | certificate "Fire warden (Dasar I)" | no expiry stated [P]; drills "periodically" (no cadence) [P] | upload (Minister-signed certificate, Art 13) | the matrix shows a **site-level** shortfall row ("Site needs N wardens, has M") — implement as a per-site summary line above the grid, not per person |
| `id_p2k3_report` | companies with ≥ 100 workers or high-risk (P2K3 committee) | report reminder, not training: report every **3 months** (4/1987 Art 12) [P] → **6 months** under 13/2025 from 19 Nov 2025 [S/U] | | | `active=False`; setting for the interval |
| `id_smk3_audit` | companies ≥ 100 workers or high hazard (PP 50/2012 Art 5(2)) [P] | certificate "SMK3" 36 months [U] | | upload | `active=False` |

Needs Rize to confirm: Permenaker 13/2025 reporting interval and SKP term; SMK3 re-audit interval; effect of Permenaker 11/2026 on operator licences; the fire-risk class of each site.

#### 3.6.4 Singapore — `sg_hours` (SSG Absentee Payroll; WSH (First-Aid) Regulations reg 5; MOM Safety Orientation Courses; SDL; bizSAFE)

| code | Who | target | validity / cadence | evidence | notes |
|---|---|---|---|---|---|
| `sg_soc` | Work Permit holders in construction / shipyard / metalworking / process sectors (job or tag) | certificate "Safety Orientation Course" | **24 months**; **48 months** once the person has > 6 years' sector experience (MOM FAQ) [P] — pack row carries both; HR picks per person via a Boolean `pb_sg_experienced` (or validity override) | upload | work-permit renewal needs SOC valid ≥ 1 month → warn at 30 days; fail → must pass within 3 months of expiry [P] |
| `sg_first_aider` | first-aiders: when a workplace has **> 25 persons**, **1 per 100 persons or part thereof, per shift** (reg 5) [P] | certificate "Occupational first aid" | provider certificates **24 months** [S] | upload | site-level shortfall line like Indonesia; names list must be posted (reg 5(4),(5)) → the export lists them |
| `sg_hours_report` | every resident employee (citizen/PR/LTVP+) on an SSG-funded course | report: **training hours** per person per course per calendar year; Absentee Payroll **S$4.50 per hour, cap S$100,000 per company (UEN) per calendar year** [P-snippet] | | the assignment's `hours` (§3.4) | Numbers › Country reports › Singapore; residency words from the employee's nationality/permit if present, else blank |
| `sg_bizsafe` | Level 1: CEO/director 3-h course (valid 6 months, not renewable); Level 2: Risk-Management Champion 2-day course (6 months); Level 3: audit, 36 months; renew 2 months before expiry [P] | certificates "bizSAFE Level N" | 6 / 6 / 36 months | upload | `active=False` by default (company-level, not per employee: model as a requirement on the tagged person) |
| `sg_sdl_note` | (information only, not a requirement): Skills Development Levy 0.25% of monthly wages, min S$2 (< S$800), max S$11.25 (> S$4,500) [P] — payroll already handles it; show as a note on the Settings card | | | | |

Needs Rize to confirm: which sector SOCs apply; first-aid retraining term (2 years per providers; regulator page not found); whether they claim Absentee Payroll; WSH Officer registration cycle.

**Sources for all four packs** (keep in the pack data file's comment header): Decree 44/2016 EN https://apolatlegal.com/wp-content/uploads/2025/06/Decree-44_2016_ND-CP.pdf · Decree 140/2018 EN (luatvietnam) · Circular 06/2020 (vbpl.vn) · Decree 105/2025 (pccc.vn) · Circular 19/2016 Art 7 (hethongphapluat) · Permenaker 8/2020 (peraturan.bpk.go.id) · Permenaker 4/1987 (its.ac.id PDF) · Kepmenaker 186/1999 (damkar.dumaikota) · PP 50/2012 (peraturan.go.id) · Permenaker 13/2025 (peraturan.go.id) · POSH Rules r.13 (taxclue) · r.14/s.21 (mondaq) · Factories Act s.41C/s.111A (advocatekhoj) · OSHWC Central Rules 2026 (sansalegal) · MOM SOC FAQs (mom.gov.sg) · WSH (First-Aid) Regulations (sso.agc.gov.sg) · St John OFAC · CPF Board SDL · SSG funding for employers · bizSAFE (tal.sg).

### 3.7 Access
- Trainers (`group_training_user`): read requirements; may not create/edit rules, schedules
  or requirements. Hide the "New …" buttons for them on the REQUIRED lens and make the verbs
  `_require_manager` (fixes F5). Managers/head: full. Employees: no access to the model
  (their own status appears on My learning as "Required for you" chips through the facade).
- Record rules: "my companies" + manager-wide, as the precedent.

## 4. Surfaces

### 4.1 The matrix (REQUIRED lens, inner tab "Matrix", default)
- Facade `pb.training.requirement.matrix(filters)` → `{allowed, columns:[{id, name, kind_word,
  pack}], rows:[{employee_id, name, department, job, site, country, safety_group,
  cells:{req_id:{state, words, evidence_id}}}], summary:{people, cells, valid, expiring,
  missing, in_progress, not_due, percent}, truncated, row_cap, page, pages}`; row cap 200
  per page (F6) with paging; filters `department_id (child_of), job_id, work_location_id,
  country_code, safety_group, requirement_id, state, q`. Rows sorted missing-first then name.
- Component `PbRequirementMatrix`: clone the roster grid CSS (sticky header + first column,
  F6); cells are quiet chips: green tick (valid), amber (expiring, with "in 12 d"), rose
  (missing), indigo ring (in progress), grey (not due / exempt); click a missing/expiring
  cell → popover "Assign now · due in N days" → verb `assign_from_cell(req_id, employee_id)`;
  column header click → the requirement drawer (edit); row click → the person's status list.
  Multi-select rows (checkbox) → bulk "Assign now", "Set safety group". **Hero moment:** the
  summary sentence above the grid: "92% in date across 214 people · 12 expiring · 5
  missing" with the percent as a quiet ring. Phone: the grid scrolls inside its box; the
  summary and filters stack.
- Exports: "Download the spreadsheet" (matrix as one sheet, people × requirements, plus a
  "Gaps" sheet) via the F7 data-URL pattern; "Print for an auditor" → PDF through a
  transient `pb.training.matrix.export` cloned from `pb.budget.export` (F7), landscape A4,
  one page per 40 rows, legend, filters printed in the header, company and date.

### 4.2 REQUIRED lens inner tabs
`Matrix` · `Rules` (requirements list: kind, audience words, target words, validity, auto
chip, pack chip; drawer to create/edit; "Turn auto-assign on/off") · `Day one` · `Comes
round again` (legacy rows read-only + new ones as requirements). Rail label stays
"Required / Bắt buộc".

### 4.3 Overview, Numbers, My learning, exports
- Overview: compliance tile "Required training in date: 92%" + queue row "Missing required
  training: 5" → matrix filtered `missing`; headline fragment.
- Numbers: section "Required training" (in date %, by department, by requirement, by site);
  tiles `required_pct`, `required_missing`, `required_expiring`; the four statutory exports
  as buttons on the Numbers page under "Country reports" (only for packs switched on):
  Vietnam "Renewals due in 30 days" (person, group, course, hours, valid until, card
  number), India "Awareness session register" (person, type incl. contractor, session date,
  evidence), Indonesia "Licence register" (person, licence, number, issuer, valid until),
  Singapore "Training hours" (person, course, hours, finished on, residency words). Each via
  the data-URL spreadsheet pattern; the pack email (L0/L1 pack) mentions counts.
- My learning: "Required for you" chips (state words, "Start" when assigned).

### 4.4 Settings card "Required training" (`pb_settings` registry, group `hr`)
Cards: Renewal window (days), Enforcement cap, Country packs (four switches per company with
a one-line description each and "Review the rules" door to the Rules tab filtered by pack),
Day-one automation (the existing `day1_auto` switch moves here).

## 5. Safety rails
1. Ledger L1–L8; EN + VI for every string; the decree names appear only in help text.
2. Matrix evaluation is set-based; never N×M queries. A test asserts the query count for 50
   people × 5 requirements stays under 30.
3. Enforcement and renewal legs never double-assign; both run in savepoints; both capped.
4. Packs are templates until a company switches them on; switching on never auto-assigns
   until HR turns a row's auto on.
5. Commits (explicit paths): (a) requirement model + migration + employee field + hours;
   (b) matrix facade + lens + exports; (c) enforcement leg + reasons; (d) country packs +
   settings card + reports; (e) demo + docs.

## 6. Demo data (payobook, registered, "DEMO …")
Set `pb_safety_group` on ~20 demo employees in Manufacturing/Construction (3 and 4), two
Safety Officers (2), two managers (1). Link course 27 to a "DEMO Field safety basics"
requirement (`always`, validity 12, department Manufacturing child_of). Switch the Vietnam
pack on for company 5 and link one pack row to a DEMO course so the matrix shows all five
cell states. One DEMO forklift licence requirement (`licence`, pattern "Forklift") matching
L1's demo upload.

## 7. Numbered tests (`tests/test_requirements.py`, `tests/test_packs.py`)
- **T1** audience resolution: department child_of, job, employee_type contractor, work
  location, country via work address then company (never nationality), safety group.
- **T2** `_status_for` all six states with document and assignment evidence; validity from
  the requirement overrides the test's months.
- **T3** matrix payload: counts add up; truncated flag at 201 people; paging; filters.
- **T4** migration converts rules and schedules once; re-run makes no duplicates.
- **T5** enforcement leg: creates reason `required` with `requirement_id`; no second open;
  cap; skips rule/schedule-backed requirements; `auto_assign` off → nothing.
- **T6** renewal leg vs enforcement leg: one course, one person, one assignment.
- **T7** day-one requirement due date = joining date + due_days; not_due before.
- **T8** hours: course override beats stock total; assignment stores hours at done.
- **T9** trainer cannot create a requirement; manager can; employee gets AccessError.
- **T10** packs: switch on copies templates once (idempotent), off archives, on again
  restores; copies carry `pack_key`; `auto_assign` False after copy.
- **T11** Vietnam pack rows: groups → cadence/hours per §3.6.1; the "renewals due in 30
  days" export lists the right people.
- **T12** India/Indonesia/Singapore exports produce the documented columns.
- **T13** Overview/Numbers tiles equal independent recomputation.
- **T14** spreadsheet and PDF export render for 0, 1, 250 rows; PDF has no sudo company
  mixing (cloned F7 comment honoured).
- **T15** no "Odoo", no emoji, VI labels ≤ two lines on the rail.
- **T16** Chrome walk (local, then live): matrix with all cell states, assign from a cell,
  bulk assign, set safety group, exports download, Rules drawer create/edit, pack switch on
  from Settings, Overview and Numbers, My learning chips, console clean.

## 8. Deploy
Risky tier (new tables + employee field + migration): backups, p0clone first, then the
other three one at a time; `-u pb_training` (+ `pb_settings` if a registry file changed);
asset ritual; warm; crons; versions; live walk; deploy-notes START/DONE; flock; stop at the
deploy gate for Fable's go.
