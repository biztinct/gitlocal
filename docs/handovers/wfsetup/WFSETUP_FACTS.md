# WFSETUP — verified plumbing facts for the guided "Workforce setup" screen

Gathered 2026-11-24 from the main checkout (`19.1` @ `8067b4834`), read-only. Every claim
carries `file:line`. If a line moved, re-locate by the quoted name — do not re-derive.
"NOT FOUND" means searched and absent. Engineering document: real technical names are used
on purpose. **User-visible strings in the build must never say "Odoo"** (white-label rule).

Design prototype: `outputs/workforce-setup-poc/index.html` (never committed). Its JS state
`S` (line ~312 of the file) is the data shape the UI wants:
`shifts[{id,name,start'HH:MM',end,brk(min),color(name)}]`,
`patterns[{id,name,weeks:[[shiftId|null ×7], …]}]`,
`people[{id,code,name,dept,site,grp:'worker'|'manager',pat,from,extra}]`,
`rules{late:{worker:[{from,to,ded}],manager:[…]},otAfter,otRate,restRate,holRate,otApprove,night,nightFrom,nightTo,nightPct,before,after}`,
`hol{iso:name}`, `co:Set(iso)` (company days off), `clocks[{n,w,st,seen,cnt}]`.
Its preview `calc()` (POC "live preview" block) is a SIMPLIFIED model — see §D.6 for how it
differs from the real engine.

---

## 0. The thing being replaced — `pb_workforce_workspace` (19.0.1.0.0)

- Manifest `pb_workforce_workspace/__manifest__.py:7`: depends
  `['pb_mission','pb_shift_patterns','pb_clock','pb_settings','pb_form_studio']`. **Not**
  `pb_attendance_policy`. Data: `views/workspace.xml` only. Assets: `static/src/workspace.{js,xml,scss}`.
- Client action: `views/workspace.xml:2-4` → `pb_workforce_workspace.action_workspace_setup`,
  name "Workforce setup", tag `pb_workforce_setup`.
- Facade `pb.workforce.workspace` (AbstractModel) `models/workspace.py:35`:
  - `_gate()` `:39` — needs `hr_attendance.group_hr_attendance_officer` or `base.group_system`, else AccessError.
  - `preferences()` `:44` → `{enabled, company, company_id, can_configure}`; any internal user.
  - `catalog(key, search='', offset=0, location_id=None, week_start=None, drafts=False)` `:67` —
    fixed allowlist `CATALOGS` `:12-21` (shifts, policies, people, calendars, rates, ceilings,
    connectors, rosters); domain `company_id in [False, env.company]`; 40/page; returns
    `{model,label,fields,rows,total,can_create,can_write,domain}`. Unknown key → ValidationError;
    model not installed → ValidationError "This optional feature is not installed for this database."
  - `overview(week_start=None)` `:88` → catalogs counts, `active_policies`, `draft_rosters`,
    `contacted_connectors`, `unassigned_people` (None when policy module absent), 6 `steps`,
    `locations` (grouped by `hr.employee.work_location_id`).
  - **Optional-module detection** = `'pb.attendance.policy' in self.env` (`:112`) and the
    generic `if name not in self.env` in `_catalog` (`:58`).
  - `Patterns._row` override `:140-147` adds `cycle_start` to `pb.shift.patterns` rows.
- Company flag `res.company.pb_workforce_workspace_enabled` (Boolean, "Use unified Workforce
  workspace", default False) `:26`; `write` refuses unless `base.group_system` (`:29-32`).
- Hard-coded English strings throughout `workspace.py` and `workspace.js`/`.xml`; **no `_t()`,
  no `i18n/` folder** (`pb_workforce_workspace/i18n` NOT FOUND).
- JS `static/src/workspace.js`:
  - `WorkforcePanel` `:44`, `mode = props.mode || action.context.pb_workspace_section || 'setup'` (`:55`).
  - Registers every key in `['overview','setup',...COPY keys]` as a Mission lens (`:130-135`,
    groups officer, sequence 95), the client action `pb_workforce_setup` (`:136`), and a
    Settings category `workforce_workspace` (`:137-143`, group `hr`, one card → xmlid
    `pb_workforce_workspace.action_workspace_setup`).
  - Patches: `PbMission` (grouped nav when enabled, `:145-181`), `PbSchedule.openTemplate`
    (`:185-190`), `PbOtDesk.openConfig` (`:191-196`), `PbShiftPatterns` (preview-before-create
    in workspace mode, `:197-211`), `WfDock` (`:214-222`), `PbSettingsHub.openCard` (redirects
    5 xmlids to workspace sections when enabled, `:225-243`).
  - Imports used (copy these spellings): `@pb_form_studio/js/record_form` (PremiumRecordForm),
    `@pb_mission/js/pb_mission` (PbMission), `@pb_mission/js/pb_dock` (WfDock),
    `@pb_schedule/js/pb_schedule`, `@pb_shift_patterns/js/patterns_board`,
    `@pb_hr_workforce/js/pb_ot_desk`, `@pb_import_kit/js/import_icons` (`ic`),
    `@pb_hub/js/hub_nav` (`HubBackChip, hubBack`), `@pb_settings/js/settings_hub`
    (`PbSettingsHub, SETTINGS_CATEGORIES`), service `wf_context`.
- Tests `pb_workforce_workspace/tests/test_workspace.py` — 9 tests, `@tagged('post_install','-at_install')`,
  fixtures: manager (attendance manager + `hr.group_hr_manager`), officer, basic user; two companies.

---

## A. Shifts — `hr.shift.template` (`pb_hr_workforce/models/shift_template.py`)

| Field | Type | `string=` | Req/default | Line |
|---|---|---|---|---|
| name | Char | Shift Name | required | :12 |
| code | Char | Code | **required** | :13 |
| sequence | Integer | — | 10 | :14 |
| color | Integer | Color Index | 0 (Odoo palette index, not a colour name) | :15 |
| active | Boolean | — | True | :16 |
| start_hour | Float | Start Time | required; 8.0 = 08:00 wall clock | :19 |
| end_hour | Float | End Time | required | :21 |
| break_duration | Float | Break Duration (hrs) | 1.0 | :23 |
| duration | Float compute stored | Work Duration (hrs) | `_compute_duration` | :24 |
| shift_type | Selection morning/afternoon/night/split/flexible | Shift Type | required, 'morning' | :27-33 |
| is_overnight | Boolean | Overnight Shift | **manual tick, NOT computed** | :35 |
| resource_calendar_id | Many2one resource.calendar | Work Schedule | — | :39 |
| company_id | Many2one res.company | Company | env.company (may be False) | :43 |
| note | Text | Notes | — | :46 |

- `_sql_constraints = [('code_company_uniq', 'unique(code, company_id)', …)]` (`:48-51`) is
  **NOT enforced on Odoo 19**: `~/odoo19/odoo/odoo/orm/model_classes.py:162-163` only logs
  "Model attribute '_sql_constraints' is no longer supported". Codes are therefore NOT unique
  in practice (an existing table may still carry an index from an older install — unverified).
  `code` is still **required**, so the new UI must generate one (POC has none), and should
  check uniqueness itself (patterns UI and roster cards display `code`).
- Overnight: `_compute_duration` `:53-60`: `raw = (24-start)+end` if `is_overnight` else `end-start`;
  `duration = max(0, raw - break_duration)`.
- `_check_hours` `:62-71` raises ValidationError: start/end outside [0,24); `end <= start` while
  not overnight ("End time must be after start time (or mark as overnight shift)"). POC's
  "an end before the start is overnight automatically" therefore needs the facade to SET
  `is_overnight = end <= start`.
- `name_get` `:73` is dead in v19 (display_name), harmless.
- Unlink: **no override**. Blocked at DB level (FK restrict) wherever referenced:
  `hr.shift.planning.shift_template_id` (required → Odoo default `ondelete='restrict'`,
  `~/odoo19/odoo/odoo/orm/fields_relational.py:282`), `pb.shift.pattern.slot.template_id`
  (`ondelete='restrict'`, `pb_shift_patterns/models/shift_pattern.py:152-154`),
  `pb.attendance.policy.shift.template_id` (required → restrict, `pb_attendance_policy/models/policy.py:155`).
  Archive (`active=False`) is the safe "remove".
- ACL `pb_hr_workforce/security/ir.model.access.csv:2-3`: attendance **manager** CRUD; attendance
  **officer** read only.
- Record rules on `hr.shift.template`: **NONE** (no company rule). Company scoping is only by
  the callers' domains (`workspace.py:63`, `patterns_board.py:113-114` uses
  `company_id False or in env.companies`; `schedule_grid.py:121-123 _pb_template_map` searches ALL).
- Readers that format: `hr.shift.planning.grid._pb_float_hhmm` (`pb_schedule/models/schedule_grid.py:498`);
  `pb.shift.patterns._templates()` (`pb_shift_patterns/models/patterns_board.py:111-123`) returns
  `{id,name,code,color,shift_type,start,end,hours,is_overnight,company_id}` — closest existing
  payload to the POC shift list (no break minutes; add `break_duration`).
- "Used in N working weeks" (POC) = count of `pb.shift.pattern.slot` with that template — no
  existing method; trivial search_count.
- Name clash: a different module `hr_shift` (repo root) ALSO defines `hr.shift.template` /
  `hr.shift.planning` (`hr_shift/security/ir.model.access.csv:2-10`). `pb_schedule` docstring
  forbids depending on it (`pb_schedule/models/schedule_grid.py:34-40`). Do not depend on `hr_shift`.

---

## B. Patterns — `pb_shift_patterns` (19.0.1.0.0)

Manifest depends `pb_schedule, pb_filter_kit, pb_import_kit, pb_wf_kit` (`pb_shift_patterns/__manifest__.py:37-48`);
NOT pb_mission (lens joins by registry string).

### B.1 Data model (`models/shift_pattern.py`)
- Docstring `:1-33`: a pattern is a CYCLE of `cycle_days` days anchored at `start_date`; one
  SLOT per cycle day (template or off); TEAMS start the cycle `offset_days` later; MEMBERS are
  people in a team with optional dates. Cycle index formula `:14`:
  `((d - start_date).days - team.offset_days) % cycle_days` (`_pb_cycle_index` `:114-118`).
- Limits `:40-43`: `MAX_CYCLE_DAYS=56`, `MAX_TEAMS=8`, `TEAM_LETTERS='ABCDEFGH'`.
- `pb.shift.pattern` `:46`: name (Char "Pattern name", req), active, company_id (req, index,
  default env.company), department_id (m2o, "Department"), start_date (Date "Day 1 of the
  cycle", req, default = Monday of this week `_default_start` `:96-99`), cycle_days (Integer
  "Repeats every (days)", req, default **14**), work_on_holidays (Bool "Work on public
  holidays", False), note, slot_ids/team_ids/member_ids (o2m), shift_ids (o2m
  hr.shift.planning via `pb_pattern_id`), last_made_on/by/to (readonly), member_count/team_count
  (compute). DB check `cycle_days 1..56` `:92-94`; `_check_cycle` `:120-138` (cycle bounds,
  ≤8 teams, slot day inside cycle, team offset `0 <= offset < cycle`).
- `pb.shift.pattern.slot` `:141`: pattern_id (cascade), company_id (related stored),
  day_index (Integer, 0 = day 1), template_id (m2o, **restrict**; empty = off).
  `UNIQUE(pattern_id, day_index)` `:156-158`.
- `pb.shift.pattern.team` `:161`: pattern_id, company_id, name (req), sequence, offset_days
  ("Starts this many days after Team A", 0).
- `pb.shift.pattern.member` `:178`: pattern_id, company_id, team_id (req, cascade),
  employee_id (req, cascade), date_from ("From"), date_to ("Until"). `_check_member` `:194-212`:
  team must belong to pattern; to ≥ from; **same person twice in ONE pattern with overlapping
  dates refused**. A person on TWO DIFFERENT patterns at once is NOT refused (only flagged as
  `also_on` by `_other_patterns`).
- POC mapping: POC `weeks[w][d]` ⇒ `cycle_days = 7*len(weeks)`, `slot.day_index = 7*w + d`,
  which aligns to weekdays only if `start_date` is a Monday (default is; `save_pattern` does not
  enforce it). POC "They begin on week k" ⇒ a team with `offset_days`; to make a person start
  week k on date X, `offset_days ≡ (X - start_date).days - 7k (mod cycle)` — no helper exists.
- ACL `security/ir.model.access.csv`: officer read, manager CRUD on all four models. Global
  company rules `security/pattern_security.xml:9-35` (`company_id in company_ids`).

### B.2 Board facade `pb.shift.patterns` (`models/patterns_board.py`, AbstractModel, `_inherit pb.filter.mixin`)
Gates: `_can_read` officer or system (`:42-45`); `_require_maker` = reader + engine maker
(attendance **manager** or system, `pattern_engine.py:61-71`). `_scope` = `company_id in env.companies` (`:67`).

| Method | Line | Gate | Returns / writes |
|---|---|---|---|
| `get_board()` | :127 | reader (soft: `allowed False`) | kpis, templates, departments, today, this_monday, max_weeks 12, max_cycle 56, max_teams 8, archived |
| `pbf_layout(**kw)` / `get_page(filters, search, sort, offset, limit≤200)` | :210/:216 | reader | rows via `_row` (`:250`, + workspace `cycle_start`) |
| `get_pattern(pattern_id)` | :280 | reader | `{id,name,department_id,company_id,start_date,cycle_days,work_on_holidays,note,slots[{day,template_id}],teams[{key:'t<id>',name,offset}],members[{employee_id,name,job,department,avatar,team_key,date_from,date_to,also_on}],drafts,published,made_to,…}` |
| `find_people(query='', limit=20≤50)` | :351 | reader | active employees in env.companies (sudo read) |
| `save_pattern(vals, pattern_id=False)` | :389 | maker | **replaces slots, teams AND members whole** (`rec.team_ids.unlink()` then recreate, `:480-496`); `vals = {name,cycle_days,start_date,department_id,work_on_holidays,note,slots,teams[{key,name,offset}],members[{employee_id,team_key,date_from,date_to}]}`; raises UserError for: no name, cycle outside 1..56, no start date, dept other company, template not in company, team offset out of range, no team, >8 teams, member other company. Returns `{id}` |
| `archive_pattern(pattern_id, archive=True)` | :501 | maker | toggles `active` |
| `preview(pattern_ids, start, weeks)` | :509 | maker | engine `plan()` report, **writes nothing** |
| `make_drafts(pattern_ids, start, weeks)` | :519 | maker | engine `apply()` report, writes drafts |
| `clear_drafts(pattern_id)` | :528 | maker | removes untouched drafts **from today on** (no date parameter) |

Implication for "Who works what" bulk assign: there is NO "add these people to pattern P from
date X" method. Via the existing API you must `get_pattern` → append members → `save_pattern`
with the full list (members are recreated; nothing references member ids). "Replace their
current week" = also `save_pattern` the OTHER pattern(s) with `date_to = X-1` for those people.
A new facade method is the clean seam (manager-gated, one transaction, returns undo data).

### B.3 Draft engine `pb.shift.pattern.engine` (`models/pattern_engine.py`)
- `_pb_range(start, weeks)` `:75-87`: start snaps back to Monday; `1 <= weeks <= MAX_WEEKS=12`
  else UserError.
- `_pb_holiday_map` `:91-134`: company closures = `resource.calendar.leaves` with
  `resource_id False`, `time_type 'leave'`, person's company; calendar-tied rows count only for
  people on that calendar (employee's or company's). Local days via `Grid._pb_shift_tzname`.
- `_pb_wanted(pattern, first, last, today)` `:138-164`: walks active members over their
  date window; off days and **past days (< today)** skipped.
- `plan(patterns, first, last)` `:167-292` — pure read. Matches the patterns' own live shifts
  (`_LIVE_STATES = draft/published/completed` `:53`): untouched & still wanted → kept_same;
  untouched & no longer wanted → `remove`; hand-edited drafts and published/completed → kept,
  day not refilled. Then per wanted day: holiday skip (unless `work_on_holidays`) → `Grid._pb_check`
  (overlap / approved leave = warn; young-worker night = block; OT ceiling ≥90% = warn;
  pending leave = info only) → `block`/`warn` skipped and reported, else a create dict
  `{employee_id, shift_template_id, date, start_datetime, end_datetime (UTC), state 'draft',
  company_id, pb_pattern_id, pb_pattern_sig}`. Each planned shift is appended to the overlap
  windows so a later row sees it (`:278`).
- `apply` `:309-352`: `_require_maker`; re-plans; unlinks `remove`; creates in one savepoint
  with tracking disabled; on UserError/ValidationError falls back to one savepoint per row and
  reports `refused`. Stamps `last_made_*` (sudo). Returns report + `{created, removed, done:True}`.
- `_pb_report` `:355-374` (JSON-safe): `first,last,created,removed,skipped_total,skipped[≤300],
  counts{code:n},kept_same,kept_published,kept_edited_total,kept_edited[≤300],off,past,people`.
  Reason codes: `holiday, overlap, leave_approved, young_worker_night, ot_ceiling, refused`
  (labels in `static/src/js/patterns_board.js:605-613`).
- Fingerprint: `pb_pattern_sig = employee|template|date|start|end` (`models/shift_planning.py:16-22`);
  "untouched" = draft with pattern mark and same sig (`:39-44`). No write override.

### B.4 Board JS
`static/src/js/patterns_board.js`: class `PbShiftPatterns` `:50`, components `PbFilterLayout`,
`WfDrawer`; filter kit `useFilterKit` `:71`; RPCs at `:110,135,276,441,479,494,508,559,572`;
client action `pb_shift_patterns` `:624`. Lens registered in `static/src/js/patterns_palette.js:41`
(`pb_mission_lens` "patterns", literal string `:34`). Schedule toolbar patch `schedule_patch.js:19-43`.

### B.5 Publishing roster rows — where it happens
- Base: `hr.shift.planning.action_publish` `pb_hr_workforce/models/shift_planning.py:103-104`
  (draft → published only). Overridden by `pb_ess_workforce/models/shift_planning_ack.py:123`
  (mints acknowledgement tokens).
- Grid: `hr.shift.planning.grid.publish_shifts(week_start_str, department_id=False, num_days=7)`
  `pb_hr_workforce/models/shift_planning_grid.py:312-327` — officer gate, domain = date window +
  `state='draft'` (+ department). **No company filter and no pattern filter** — publishes every
  visible draft in the window, including `pb_inferred` suggestions. Returns count.
- `publish_shifts_notified(...)` `pb_ess_workforce/models/publish_notify.py:72-92` — same
  domain, then `_ess_notify_published` (portal/mail; mail switch param, tenant mail is off on
  rize/sudima/p0clone). Returns `{published, notified, portal, emailed, no_channel, mail_enabled, capped}`.
  The Schedule calls this first, falls back to `publish_shifts` (`pb_schedule/static/src/js/pb_schedule.js:758-769`).
- `num_days` is honoured as any integer by both (base takes it raw; notified `int(num_days or 7)`),
  so "publish N weeks" = one call with `num_days = 7*N` from a Monday.
- Rights: officer has READ-only ACL on `hr.shift.planning` and an own-rows record rule
  (`pb_hr_workforce/security/workforce_security.xml:21-30`); manager rule `[(1,'=',1)]` (`:32-37`).
  ⇒ publishing/creating needs attendance **manager** (ledger S5C-5). `hr.shift.planning` has
  **no company record rule** — a manager with several allowed companies publishes all of them
  unless the domain adds `company_id`.

---

## C. Roster rows — `hr.shift.planning` (`pb_hr_workforce/models/shift_planning.py`)

Fields (`:16-59`): name (compute stored "emp - code - dd/mm"), employee_id (req, tracking,
index), department_id (related stored), shift_template_id (req), date (req, index),
start_datetime / end_datetime (Datetime **UTC**, req), actual_check_in/out, actual_hours
(compute), planned_hours (related `shift_template_id.duration`, stored), compliance_status
(compute: pending/on_time/late/early_leave/absent/overtime; 15-min tolerance `:92-101`;
overridden by `pb_attendance_flow/models/shift_planning.py:23` with company grace), state
(draft/published/completed/cancelled, default draft, `:49-54`), color (related), note,
company_id (default env.company). `_inherit mail.thread, mail.activity.mixin`.
State methods `:103-113`: publish (draft→published), complete (published→completed), cancel
(≠completed), reset_draft (cancelled→draft).

Extra fields from other modules: `pb_pattern_id`, `pb_pattern_sig` (pb_shift_patterns
`models/shift_planning.py:28-31`); policy fields `pb_policy_id, pb_day_kind, pb_category,
pb_inferred, pb_evidence, pb_calculation_*` … (pb_attendance_policy `policy.py:186-200`, §D);
ack fields (pb_ess_workforce `shift_planning_ack.py:72-80`).

Creating one shift (existing API, `hr.shift.planning.grid`, TransientModel used as @api.model facade):
- `quick_create_shift(employee_id, date_str, template_id)` `pb_hr_workforce/models/shift_planning_grid.py:258-299`
  — officer gate but create needs manager ACL; builds wall-clock start/end (overnight → next
  day), converts to UTC via `_pb_shift_utc` (`:44-54`) using `_pb_shift_tzname` ladder
  employee.tz → calendar.tz → user.tz → UTC (`:19-41`); state draft; **no overlap/duplicate
  check, no company_id set** (default env.company). Returns id.
  Minor drift: it computes minutes with `int((h%1)*60)` while `_pb_shift_window` uses
  `int(round(...))` (`pb_schedule/models/schedule_grid.py:84-87`) — identical for :00/:15/:30/:45.
- `delete_shift(shift_id)` `:302-309` — drafts only, returns bool.
- `copy_week(...)` `:329` legacy unchecked; `copy_week_checked(source, target, department_id, num_days)`
  `pb_schedule/models/schedule_grid.py:744-829` — validates each target with `_pb_check`,
  skips block/warn, returns `{created, skipped[{employee_id,employee_name,date,template,reasons,severity}], considered, target_start}`.
- Checks (pure reads, reusable for a "one-off shift for date range" bulk action):
  `_pb_shift_window(template, day, tz)` `:69-97`; `_pb_shift_windows(emp_ids, from, to)` `:570-586`;
  `_pb_leave_map` `:522-549`; `_pb_ceilings(emp_ids, ref_date)` `:552-567`;
  `_pb_check(employee, day, template, windows, leaves, ceilings, exclude_shift_id)` `:623-681`
  → `[{severity: warn|info|block, code, text}]`; `check_shift` `:684`; `check_day` `:708`.
- Read model for a week: `get_schedule_data(week_start_str, department_id=False, num_days=7, search='')`
  `:176` (capped at `WF_ROW_CAP=200` `:51`; a bare attendance manager without HR rights gets
  AccessError on `hr.employee.version_id` — ledger S5C-4).
- Duplicates per employee/day: **NO SQL or Python constraint**. Only the advisory overlap warning
  in `_pb_check` (and `copy_week_checked` / pattern engine skip on it). Hard constraints that
  can raise on create/write: `pb_young_worker/models/shift_planning.py:16-31` (minor + night,
  ValidationError); `pb_attendance_policy` `_policy_scope` `policy.py:223-230` when `pb_policy_id`
  set — employee/shift template/policy must share the roster's company (**a template with
  `company_id=False` fails here**), local start date must equal `date`, duration (0, 24h].
- "One-off shift replaces what was planned on those days" (POC): no existing method. Must
  delete/cancel overlapping DRAFTS (published ones need a decision) then create; pattern drafts
  deleted by hand are refilled by the next `make_drafts` unless the day holds a non-pattern
  shift (the overlap check then skips it).

---

## D. Attendance rules — `pb_attendance_policy` (19.0.1.0.0, OPTIONAL)

Manifest `pb_attendance_policy/__manifest__.py`: depends `pb_clock, pb_schedule,
pb_timesheet_approval, pb_hr_payroll_formula, pb_attendance_flow, pb_settings, pb_shift_patterns`;
data ACL, rules, views, cron (15-min "Attendance policies: calculate published shifts",
`data/cron.xml:1`, active). Installed only on **sudima** (handover
`docs/handovers/sudima-attendance-20261119/README.md:3` "Install it only in Sudima";
`docs/handovers/workforce-workspace/RELEASE_STATUS.md:19` "eight catalogs on Sudima, seven elsewhere").
No `i18n/` folder (NOT FOUND). Settings card registered in `static/src/js/settings.js:5-21`
(manager-only category "Attendance calculation").

### D.1 Models
`manager(env)` helper `policy.py:17-19`: AccessError unless superuser or attendance manager.

`pb.attendance.policy` `:22` (`mail.thread`, `_check_company_auto`):
name (req), company_id (req), tz (Selection `_tz_get`, req, default 'UTC'), state
(draft "Draft / review" / active / retired, default draft), capture_before / capture_after
(Float, default 2.0, "Capture before/after shift (hours)"), night_premium (Bool "Calculate
overlapping night-premium hours"), night_start (22.0) / night_end (6.0) ("Night starts/ends
(local hour)"), band_ids, shift_ids, note ("Source and assumptions"), pairing / deduction_basis
/ allocation (single-value selections, fixed). Constraint `_bounds` `:45-51`: capture 0..6 h;
night hours in [0,24) and distinct.
- `write` `:53-59`: manager only; **non-draft policy: only `state` may change**
  ("Duplicate an active policy to change its rules…"); `state` only via the action context token.
- `create` `:61-66`: manager; must be draft.
- `action_activate` `:68-84` preconditions (UserError): state draft AND has shift rules; for
  BOTH categories worker and manager: bands exist, **all `confirmed`**, sorted by minimum start at
  0, contiguous (`b.minimum == previous maximum`), last band `open_ended`.
- `action_retire` `:86-88`; `copy` → draft "(revision)" `:90-91`; `unlink` only drafts `:93-96`.

`pb.attendance.policy.child` `:99` (abstract): create/write/unlink require manager and a draft parent.

`pb.attendance.policy.band` `:126`: policy_id, company_id (related stored), category
(worker / "Manager / supervisor", req), minimum ("From minutes (inclusive)", req), maximum
("To minutes (exclusive)"), open_ended ("No upper limit"), hours ("Additional hours deducted"),
confirmed (False), note. `_check_band` `:141-145`: min ≥0, 0 ≤ hours ≤ 24, max > min unless open.
**Semantics: [minimum, maximum) minutes; POC uses inclusive integer "from–to".**

`pb.attendance.policy.shift` `:148`: policy_id, company_id, template_id (m2o hr.shift.template,
req, check_company), normal_end_offset ("Normal window ends after (elapsed hours)", default
9.0), break_start_offset ("Unpaid break starts after (elapsed hours)", 4.0), break_hours
("Unpaid break hours", 1.0), normal_hours (compute = normal_end − overlap of break), note.
`UNIQUE(policy_id, template_id)`. `_check_rule` `:168-174`: `0 < normal_end <= span`,
break inside span. ⇒ **the overtime boundary is per shift, in elapsed hours from shift start
(break included)** — not "after N paid hours a day".

`hr.employee` additions `:177-180`: `pb_attendance_category` (worker/manager, "Attendance
deduction group"), `pb_attendance_policy_id` (m2o, "Attendance calculation policy",
check_company) — **both `groups='hr.group_hr_user'`**: an attendance manager without HR
officer rights can neither read nor write them (fields_get omits them).

ACL `security/ir.model.access.csv`: manager CRUD, officer read on policy/band/shift. Rules
`security/rules.xml` company rules on all three.

### D.2 Roster hooks (`policy.py:184-262`)
- On create, `pb_policy_id` is copied from the employee's policy if absent (`:241-244`) —
  **drafts created before the employee got a policy have no `pb_policy_id`** and the cron ignores them.
- `pb_day_kind` (weekday / weekend "Rest-day overtime" / holiday "Public-holiday overtime",
  default weekday, `:187`) is **never set automatically anywhere** (only the form,
  `views/policy.xml:21`). Holiday/rest-day work is weekday unless a person edits each row.
- Calculated fields guarded by context token (`:236-257`); rows with generated attendance
  cannot be moved/unlinked (`:250-262`).

### D.3 The calculation
- Pure function: `pb_attendance_policy/engine.py:10-61`
  `calculate(punches, start, normal_end, end, breaks, bands, category, day_kind='weekday', night_intervals=())`
  — tz-aware datetimes; NO database access; never writes. Returns
  `{first,last,late_minutes,gross_hours,break_hours,worked_hours,penalty_hours,requested_penalty_hours,normal_hours,overtime_hours,night_hours,segments[],day_kind}`
  or `{'error': …}`. Errors: <2 punches; normal_end outside shift; no single band covers the
  lateness (`:23-24`); **matching band not confirmed (`:25-26`)**; punches do not overlap shift.
  Rules: early arrival not paid (`low = max(first, start)`), penalty removed from worked hours
  chronologically (normal first then OT), non-weekday day_kind makes every paid hour overtime
  of that kind, night hours counted inside intervals. Standalone test loads it by file path
  (`tests/test_engine_standalone.py:5-6`, 11 tests).
- DB-bound wrapper: `hr.shift.planning._policy_calculate()` `policy.py:264-334` — reads REAL
  punches (`pb.clock.connector.event` matching `connector_id.tz == policy.tz`, and `pb.clock.punch`),
  refuses overlapping capture windows, missing clock code, unfinished capture window
  (`:318-319`). Not usable for a hypothetical.
- `action_preview_calculation` `:336-348` (manager) WRITES the result onto the row;
  `_process_calculation` `:356-433` creates `hr.attendance` + `hr.overtime.request` rows.
- **Preview entry point for hypothetical in/out: NOT FOUND.** Smallest chain to wrap
  (no writes) — copy of `_policy_calculate` lines 266-276, 320-330:
  1. `policy = employee.pb_attendance_policy_id`; `rule = policy.shift_ids.filtered(template_id == T)` (exactly one).
  2. `category = employee.pb_attendance_category` (required).
  3. `start_utc, end_utc = env['hr.shift.planning.grid']._pb_shift_window(T, day, Grid._pb_shift_tzname(employee))`;
     localise both with `pytz.timezone(policy.tz)`.
  4. `normal_end = start + rule.normal_end_offset h`; `breaks = [(start+break_start_offset, +break_hours)]`.
  5. `bands = [{category, minimum, maximum (None if open_ended), hours, confirmed}]` from `policy.band_ids`.
  6. night intervals exactly as `:323-329` when `policy.night_premium`.
  7. `punches = [start + in_offset, end + out_offset]`; `calculate(..., day_kind)`.
  The UI's draft (unsaved) rule edits can be fed as plain dicts in steps 4–6 — engine is pure.
- Money side is NOT in this module: rates live in `hr.overtime.config` (§E). OT requests
  created by `_process_calculation` carry `overtime_type` = day kind or 'night' and are
  always "approval required" (`:401-407, :415-421`).

### D.4 Clock capture window
`capture_before/after` (0..6 h) define which punches belong to a shift (`:276`). POC "Reading
the clock" maps 1:1. Sudima draft policy: before 2, after 6
(`docs/handovers/sudima-attendance-20261119/configure.py:41`).

### D.5 Pairing guard
`pb.clock.pairing._pair_employee` skips legacy pairing for employees whose policy is active (`policy.py:578-587`).

### D.6 POC preview vs real engine (differences the screen must respect)
| POC `calc()` | Real |
|---|---|
| OT after `otAfter` paid hours/day | OT after `normal_end_offset` elapsed hours from shift start, per shift rule |
| bands inclusive `from..to` | `[minimum, maximum)`; last band open-ended; unconfirmed band ⇒ error, not 0 |
| one global rest/holiday rate | rate per `hr.overtime.config` row, resolved by type/country/company |
| night % on toggle | policy `night_premium` + hours; % from `hr.overtime.config` type `night` |
| early arrival counted | early arrival not paid |
| "approve overtime" switch | `requires_approval` is display-only (§E) |

### D.7 A second, separate late/OT engine exists
`pb_time_pay` (`pb_time_pay/models/time_pay.py:1-45`) computes suggested OT and late/early
minutes for the weekly Close from punches vs published shift or working hours, with company
grace from `pb.attendance.rule` (`pb_attendance_flow/models/attendance_rule.py:35-79`,
`grace_in_minutes`, `grace_out_minutes`, `_grace_for_company` `:135`), and treats company
closures as public-holiday OT (`time_pay.py:151-170`). It runs on every tenant; the policy
engine only where installed. A "Late rules" step on non-Sudima tenants would be editing
`pb.attendance.rule` grace, not bands.

---

## E. Overtime — `pb_hr_workforce`

### E.1 `hr.overtime.config` (`models/overtime_config.py`)
Fields `:12-72`: name ("Rule Name", req), sequence, active, country_id ("Country", blank =
global), company_id (default env.company), overtime_type (weekday "Weekday Overtime" /
weekend "Weekend Overtime" / holiday "Public Holiday Overtime" / night "Night Shift Premium" /
extended "Extended Overtime (>8hrs OT)", req), rate_multiplier (Float "Rate Multiplier", req,
1.5 = 150%), rate_display (compute "150%"), max_hours_per_day (4.0) / max_hours_per_month
(40.0) (legacy, never enforced — `ot_ceiling.py:13-16`), requires_approval (Bool "Requires
Approval", True), apply_monday…apply_sunday, applicable_days_display, time_from / time_to
("Applies From/To", 22.0/6.0 for night via onchange), time_display, threshold_hours
("Overtime After (hrs)", 8.0), note (Html), color. Constraint `rate_multiplier >= 1.0` `:145-150`.
- Seeds `pb_hr_workforce/data/overtime_config_data.xml` (noupdate): VN weekday 1.5, weekend
  2.0, holiday 3.0, night 1.3 (22–06, approval False); global weekday 1.5, weekend 2.0,
  holiday 2.5. `company_id` not set in XML ⇒ default company at install time.
- Resolution used at runtime: `hr.overtime.request._compute_overtime_config`
  `pb_hr_workforce/models/overtime_request.py:93-107`: same `overtime_type`, employee country
  or global, request company or global, order `country_id desc, company_id desc`, limit 1.
  (NULLs-first-on-DESC trap documented in `ot_ceiling.py:150-158` applies here too: a global
  row can win over a specific one.)
- `threshold_hours` and `requires_approval` are **display-only**: only read by
  `pb_hr_workforce/models/ot_desk.py:401-402` (and the workspace catalog). Neither drives any
  calculation or auto-approval. Night premium as "+30 %" is stored as multiplier 1.3.
- ACL: manager CRUD, officer read (`security/ir.model.access.csv:6-7`). No record rules.
- "Rest day" = `weekend` type; there is no separate rest-day concept.

### E.2 `pb.ot.ceiling` (`models/ot_ceiling.py`)
Company caps, not rates: name, company_id (blank = global fallback), daily_cap, weekly_cap,
biweekly_cap (0 = not enforced), monthly_cap (40), annual_cap (200), annual_cap_special
(300), active (`:32-53`). **No `country_id` field** (the workspace CATALOGS lists it; filtered
out harmlessly at `workspace.py:62`). `_allowance`/`_split`/`_for_company` `:96-161`.
Employee flag `pb_ot_special_sector` (`groups='hr.group_hr_user'`) `:169`. Seed
`data/ot_ceiling_data.xml:7`. ACL manager CRUD / officer read (`ir.model.access.csv:20-21`).

---

## F. Holidays and company days off

- Storage: `resource.calendar.leaves` rows with `resource_id = False`, `time_type = 'leave'`,
  on the company's working calendar (`company.resource_calendar_id`). Extension
  `pb_timeoff/models/holiday_journey.py:7-14`: `pb_holiday_kind` Selection
  (public "Public / festival holiday" / collective "Collective leave" / company "Company
  holiday"), `pb_holiday_batch_id`. **Company days off = kind `company`.**
- Readers of these rows: pattern engine `_pb_holiday_map` (§B.3), `pb_time_pay`
  (`time_pay.py:151-170`), `pb_blueprint/models/blueprint_calendar.py:227-249` (payday),
  standard resource/payroll working-days logic. The policy engine does NOT read holidays
  (day kind is manual, §D.2).
- Screen + API: `pb.holidays` AbstractModel `pb_timeoff/models/pb_holidays.py:50`; client
  action `pb_timeoff.action_pb_holidays` (tag `pb_holidays`, `pb_timeoff/views/pb_timeoff_action.xml:18-21`;
  JS `static/src/js/pb_holidays.js:242`); Mission lens "holidays" (`static/src/js/timeoff_palette.js:55-62`, groups []).
  - `year(year=False)` `:119` → `{year, today, years, companies[{id,name,country,country_code,has_calendar,calendar,rows[{id,date,date_to,name,weekday,month,label,day,days,is_past,is_today,kind,source}],count,next}], can_edit, next, next_ahead}` — everyone may read (sudo over public rows), up to 8 companies.
  - `add(company_id, name, date_from, date_to=False)` `:322` — refuses duplicate name on same days.
  - `add_many(company_id, lines_text)` `:340` — "Name | YYYY-MM-DD | [end]" per line, all-or-nothing.
  - `remove(row_id)` `:396` — public rows only.
  - `_create_row` `:271-319` — creates 100 years out then writes real dates (works around the
    stock create's timezone shift; keep using it, never create rows directly).
  - Import journey (`holiday_journey.py:83-190`): `import_workspace(year)`, `prepare_import(company_id, year, source, lines_text, use_source)`
    (4th column kind public/collective/company), `resolve_import`, `publish_import` (batch versioned).
  - Write gate: `pb.timeoff._require_officer` (`pb_timeoff/models/pb_timeoff.py:55-65`) —
    `hr_holidays.group_hr_holidays_user`, `hr.group_hr_manager`, `om_hr_payroll.group_hr_payroll_manager`
    or system. **Attendance managers are NOT in it.** Plus `_company_for_write` requires the
    company in `env.companies` (`holiday_journey.py:67-70`) and a working calendar (`pb_holidays.py:242-255`).
- Vietnam public holidays seeded? **Not as data.** Only `pb_timeoff/data/holiday_reference.json`
  (55 rows, 2026 only, VN 13 rows incl. Tết 16–20 Feb 2026), usable only on db `rize` for 2026
  (`holiday_journey.py:98-100`). No 2027 list anywhere (NOT FOUND). POC's 2027 dates are
  illustrative.

---

## G. Clocks — `pb_clock`

- `pb.clock.connector` (`pb_clock/models/clock_connector.py:28`, Windows PC bridge for Mitaco
  Access databases): name (req), company_id, source_type (only `mitaco_mdb`), source_group
  (req; same group = same terminals), tz (req), history_from, interval_minutes (5..1440),
  code_field, publish_punches ("Send accepted records to attendance", False), state
  (new "Awaiting setup" / connected / revoked, readonly), **last_contact**, last_read ("Last
  successful database read"), latest_source_punch, source_rows, pending_rows, client_version,
  last_error, invitation_until ("IT invitation expires"), device_id, event_ids (`:34-60`).
  Secrets (`token_hash`, `pairing_hash`, `invitation_hash`) are `groups='base.group_no_one'`.
- Write rules `:73-95`: manager only; connection-status fields refused; source settings locked
  once records exist. ACL `pb_clock/security/ir.model.access.csv:12-16`: officer read; manager
  read/write/create, **no unlink**.
- Health for a list row: `state`, `last_contact`, `last_read`, `pending_rows`, `bool(last_error)`.
  Allowlisted summary `_setup_status()` `:177-187` → `{name, company, timezone, history_from,
  interval_minutes, state, last_contact, last_read, pending, needs_attention, invitation_until}`.
- "Copy setup link for IT": `_new_invitation()` `:130-139` (private, manager, row lock) makes a
  5-day token and returns the RAW token; the link is built client-side as
  `location.origin + '/clock-bridge/setup#' + token` (`pb_clock/static/setup/setup.js:132-137`).
  Reachable today only through HTTP: `POST /clock-bridge/manage/<id>/invite` (auth user,
  HTTPS required, `pb_clock/controllers/connector.py:122-130, 158-159`) → `{invitation, ...status}`.
  **No ORM/RPC public method returns the link** (a facade would call `_new_invitation` itself).
  Replacing an invitation invalidates the previous one. Revoke: `_revoke_invitation` `:141-149`
  (`POST …/revoke-invite`). Full guided page: `action_setup` `:120-123` → `/clock-bridge/manage/<id>`.
- `action_pair` `:97-109` (30-min code wizard, revokes existing installation!), `action_revoke`
  `:111-118`, `action_records` `:189-192`, `action_download` `:194-195`.
- Push-protocol machines are a separate model `pb.clock.device` (`clock_device.py:46`):
  serial, location, state, allowed, last_seen_at ("Last heard from"), last_punch_at,
  punches_today, users_count, … Lens API `pb.clock.lens` (`clock_lens.py:40`): `get_lens`,
  `set_device`, `allow_device`, `ignore_device`, … A "Time clocks" step should list both kinds.
- Employee clock number `hr.employee.pb_clock_code` ("Clock number", `groups='hr.group_hr_user'`,
  `pb_clock/models/hr_employee.py:11-15`); policy engine falls back to `barcode` (`policy.py:286`).

---

## H. Hosting, navigation and the shared UI kit

- **Client action registration**: XML `ir.actions.client` with tag + JS
  `registry.category('actions').add(tag, Component)` (`workspace.js:136`). Replacing the
  `setup` mode = re-registering `pb_workforce_setup` (registry `add` with `{force:true}` from a
  module loading later) or changing `WorkforcePanel` when `mode==='setup'`.
- **Settings card**: `registry.category(SETTINGS_CATEGORIES)` (`pb_settings/static/src/js/settings_hub.js:281`,
  descriptor shape `:255-280`). Card kinds (`:123-133`): `tag` → `openHub` with
  `pb_back = backToSettings` (`:809-812`, `:838-871`) — the cockpit shows `HubBackChip`;
  `xmlid` → `doAction(xmlid, {clearBreadcrumbs:false})`. A one-card category opens its card
  directly (`:788-789`). Today's card uses `xmlid` (`workspace.js:141`), so `hubBack` returns
  `{fromStack:true}` and the chip uses the breadcrumb.
- **Back chip**: `hubBack(props)` `pb_hub/static/src/js/hub_nav.js:149-155`; `HubBackChip`
  `:208-240` (props `back`, `tone` dark|light — use `light` on a white header); `openHub`
  `:94-137` writes `pb_back`; `goBack` `:182-190`.
- **Mission lenses**: `registry.category("pb_mission_lens").add(key, {key, icon, label,
  Component, groups, props, features, ownsPersonDrawer}, {sequence})` (contract documented at
  `pb_mission/static/src/js/pb_mission.js:200-227`, `MISSION_LENSES` export `:227`). Mission
  action xmlid `pb_mission.action_pb_workforce` (`pb_mission/views/mission_action.xml:15`),
  lens chosen by context `pb_shell_lens`. Guest lens arrival trap: ledger S5C-1.
- **Sidebar stays visible**: `PbSidebar._resolveVisibility` `pb_sidebar/static/src/js/pb_sidebar.js:188-…`
  shows the rail when the current action's tag/xml_id/res_model starts with `pb_` or `pb.`,
  or is rail-claimed, or an ancestor in the URL path is ours (RIZE_LEDGER R126). Tag
  `pb_workforce_setup` qualifies; records opened from it keep the rail.
- **Icons**: `ic(name, size=16)` `@pb_import_kit/js/import_icons` (`import_icons.js:382-387`)
  returns `markup()` SVG; **unknown names silently render a check mark**. Present: check, plus,
  x, clock, calendar, users, search, arrowRight, sun, moon, alert, trash, copy, undo, repeat,
  sliders, plug, zap, send, eye, pencil, info, home, refresh, mapPin, layoutGrid, compass.
  Absent: `arrowLeft`, `alertTriangle`, `rotateCcw`, `edit`. Cache the markup (ledger: `t-out`
  of a NEW markup re-inserts DOM each render — `patterns_board.js:12` uses `pbfIcon`).
- **Kit classes**: `.pbim` root, `pbim-btn primary|ghost` (bare `pbim-btn` renders grey —
  S5A-6), `pbim-spin`; SCSS `pb_import_kit/static/src/scss/{import_tokens,import_kit,quiet_board,modal,…}.scss`.
- **Quiet board**: `t-call="pb_import_kit.QuietGlance"` (`qGlance`, `qGlanceOn`) and
  `pb_import_kit.QuietSteps` (`qSteps`, `qStepsLabel`, `qStepPick` — bind it, S8C-7);
  contract in `pb_import_kit/static/src/xml/quiet_board.xml:1-25`; styles `quiet_board.scss`.
- **Drawer**: `WfDrawer` `@pb_wf_kit/js/wf_drawer` (`wf_drawer.js:14-38`, props `title,
  subtitle, onClose, slots`; ESC closes; 320 px — widen inside own root, S5C-3). No generic
  wide slide-over component found beyond this (NOT FOUND).
- **Toast with Undo**: notification service `add(msg, {type, autocloseDelay, buttons:[{name:_t("Undo"), primary:true, onClick}]})`
  precedent `pb_orgchart/static/src/js/orgchart_edit.js:184-199` (server returns an `undo`
  payload; client keeps a small stack). Also `pb_doc_studio/static/src/js/doc_studio.js:296`.
- **Multi-select with Shift-range**: precedent `pb_blueprint/static/src/js/components_tab.js:243-266`
  (`onRowClick(row, ev)`: shift → range from last selected; ctrl/meta → toggle).
  People board "Select" mode `pb_people/static/src/js/people.js:252-268` has tick-select +
  `pb.people.bulk_apply(emp_ids, 'set_department', value)` (`pb_people/models/pb_people.py:473-485`)
  but **no Shift-range**. "Update many people at once" is `pb_updates` (spreadsheet desk,
  `pb_updates/static/src/xml/updates_desk.xml:32`) — not a tick table.
- **Filter kit**: `useFilterKit`, `pbfIcon` `@pb_filter_kit/js/filter_kit` (`:1009`, `:46`);
  `PbFilterLayout` `@pb_filter_kit/js/filter_components` (`:361`); server mixin `pb.filter.mixin`
  (`_pbf_model/_pbf_screen/_pbf_base_domain/_pbf_search_domain/_pbf_sorts/_pbf_spec/_pbf_builtin_views`,
  example `patterns_board.py:160-213`). Gotchas S5C-2, W2B-4.
- **Record editor host**: `PremiumRecordForm` `@pb_form_studio/js/record_form` (used `workspace.xml:21`).
- Week context: service `wf_context` (`pb_wf_kit/static/src/js/wf_context_service.js`), `state.weekStart`, `onChange`.

---

## I. Translations

- Comparable modules with PO files: `pb_shift_patterns/i18n/{vi_VN,id_ID}.po` (227 msgids),
  `pb_clock/i18n/vi_VN.po`, `pb_hr_workforce/i18n/vi_VN.po`. None for `pb_workforce_workspace`
  or `pb_attendance_policy`.
- Entry shape (`pb_shift_patterns/i18n/vi_VN.po:19-23`):
  ```
  #. module: pb_shift_patterns
  #. odoo-javascript
  #: code:addons/pb_shift_patterns/static/src/js/patterns_board.js:0
  msgid "…"
  msgstr "…"
  ```
- The three loading rules (memory `po-translation-loading-rules.md`): (1) `#. module: <name>`
  first or the registry load crashes; (2) `#. odoo-python` / `#. odoo-javascript` or the entry
  is silently dropped; (3) `#: code:addons/<module>/<path>:0` occurrence or dropped. Traps: a
  `.pot` is merged into/filters the `.po`; insert markers after the module line; test DBs have
  no second language, so green suites prove nothing. Parse gate (run with `PoFileReader` over
  every `addons/*/i18n/*.po`) before a deploy.
- Export: `odoo-bin i18n export -c <conf> -d <db> -o <file>.pot <module>` (S5A-7, S8B-4);
  keep each translatable OWL sentence on ONE line (PRD-3); selection labels via
  `field._description_selection(env)` (S8B-4); reused msgid must fit its new meaning (W2F-1).
- Static gate precedent: `pb_shift_patterns/tests/test_static.py:1-9` (no "Odoo" in
  user-visible text; vi/id parse and coverage; lens registry spelling).

---

## J. Tests, local runs and the deploy + verify procedure

### J.1 Local
- Runtime `~/odoo19/README.md`: `./venv/bin/python odoo/odoo-bin -c odoo-local.conf`; addons
  path official addons FIRST then the repo (`~/odoo19/odoo-local.conf`); Postgres 16 at
  `/usr/local/opt/postgresql@16/bin`, role `odoo`; `./runtests.sh <module> [db]`; manual:
  `-d <db> -i|-u <module> --test-enable --test-tags /<module> --stop-after-init --log-level=info`.
- Use small templates (`upd_p6_t_tpl` ~150 MB, vi+id installed; admin uid 2 archived there —
  QF1-W4, QF3-2); one `createdb -T` at a time; `ALTER DATABASE <copy> OWNER TO odoo` for a
  browser walk (W2C-4); `--max-cron-threads=0` for walks (QF1-W3); own hostname
  `<phase>.localhost:<port>` for cookies (S8A-2); own port block (S8B-7); drop DB + filestore after.
- Test tags in this area: `pb_workforce_workspace` post_install (9 tests);
  `pb_shift_patterns` `@tagged('post_install','-at_install','wdgap_s5c')` (`tests/test_patterns.py:38`, 18 tests + static);
  `pb_attendance_policy` post_install (`tests/test_policy.py:11`, 8 tests) + standalone engine
  (`python3 -m unittest pb_attendance_policy/tests/test_engine_standalone.py`-style, file-path import).
- `-u X --test-tags /A,/B` runs post-install suites only of modules in `-u` (S5B-4, S8M-1).
- Recorded flaky/date-dependent baselines: S5M-1 (pb_ess_workforce), PRB-W6 (pb_payruns in a close week).

### J.2 Deploy + verify (as the recent handovers do it; do not run from a build phase)
Sources: repo `CLAUDE.md` deploy contract; `WDGAP_LEDGER.md` "Deploy rules"
(`docs/handovers/wdgap/WDGAP_LEDGER.md:70-86`); `docs/handovers/formstudio/FS_DEPLOY_HANDOVER.md:3-21`;
the workspace release `docs/handovers/workforce-workspace/RELEASE_STATUS.md:5-15`.
1. Read `/opt/deploy-notes.md`; never over another deployer's open START; append START.
2. Merge branch → `origin/19.1`; `git archive` from the pushed commit.
3. Backups ×5 (`sudo -u postgres pg_dump -Fc`); risky tier (new install / access / pay
   calc) → rehearse on a clone with crons + mail servers off, `dropdb --force` after (restore
   via `sudo cat dump | sudo -u postgres pg_restore`, assert row counts — QFM-2).
4. Clean staging dir; per-module `rsync -a --delete /tmp/deployX/<m>/ /odoo/odoo-server/addons/<m>/`;
   never `--delete` into the addons root; never ship vendored standard addons.
5. 15 quiet minutes on customer DBs (activity check S8M-7); stop service; `-i`/`-u` each DB
   one at a time in a detached unit with an `EXIT=` sentinel; allow only the 3 known
   `payroll_analytics` ERROR lines (PRM-4).
6. `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` per DB + `web.assets.version` bump; start; warm each site.
7. Verify: hash every module tree both sides (skip `__pycache__`, `*.pyc`, `.DS_Store`);
   manifest version vs `ir_module_module.latest_version` in every DB (normalise `19.0.` prefix);
   cron counts vs snapshot; browser walk (payobook QA login) console clean; append DONE; report.
- Database set: `CLAUDE.md` lists four (`payobook, payobook_template, p0clone, rize`); the WDGAP
  programme and the workspace release use **five incl. `sudima`** (WDGAP D4; RELEASE_STATUS
  "Installed … on payobook, payobook_template, p0clone, rize, and sudima"). Never `abm`.
  Server alias `Payobook19v2`; one addons dir `/odoo/odoo-server/addons`.

---

## K. Gotchas relevant to a new OWL client action + abstract-model facade + bulk writes

1. Officers read only their OWN `hr.shift.planning` rows and cannot create shifts; any preview or bulk write must be attendance-manager gated (WDGAP S5C-5; `workforce_security.xml:21-37`).
2. `hr.shift.planning` and `hr.shift.template` have no company record rule; scope every domain by `company_id` yourself (`publish_shifts` does not — §B.5).
3. Sudo reads only BEHIND an explicit gate (C18.73 note `shift_planning_grid.py:56-63`; `patterns_board.py:9-11`).
4. Rights tests must `env.flush_all(); env.invalidate_all()` before calling as another user, or they pass on the bug (W2M-1).
5. `with_context(dict)` carries over `allowed_company_ids`; set it explicitly with `with_user` (QF2-G1, W2B-5).
6. `t-out` of a NEW `markup()` re-inserts DOM every render — cache icon markup (WDGAP conventions §4; `patterns_board.js:12`).
7. Unknown `ic()` names render a check mark silently (`import_icons.js:386`).
8. `pbim-btn` needs `primary`/`ghost` (S5A-6); `.pbim-badge` capitalises text (QF4-W3).
9. QuietSteps `qStepPick` must be bound (S8C-7); `q`-prefixed t-call params (quiet_board.xml:19-23).
10. OWL template expressions cannot call `Number(...)` — use a getter (S8C-5).
11. Patching: one object literal per class; never merge patch objects (`super` binding, S8A-1).
12. Mission guest lens reads arrival context in `onMounted` too early — retry/consume once (S5C-1).
13. Filter kit "of N" needs `kit.load()` when the total changes (S5C-2); screen-value base domains need `defer:true` + `kit.kw` (W2B-4).
14. `WfDrawer` is 320 px; widen inside own root (S5C-3).
15. CSS prefix clash: grep the repo before choosing one (`pbls-` taken; S5A-1). Workspace uses `pbww-`, patterns `pbsp-`.
16. Test every lens INSIDE its hub (no-scroll trap; WDGAP conventions §4).
17. Asset purge alone does not refresh browsers; bump `web.assets.version`, fetch with `cache:'reload'`, restart local server (QF1-W1, QF2-G6, QF5-W7).
18. Translations: each OWL sentence on one line (PRD-3); new msgids also in `.pot` where one exists; three markers (§I).
19. Bulk create: batch in one savepoint, fall back to per-row savepoints and report refusals (precedent `pattern_engine.py:322-343`); disable tracking for mass rows (`:317-318`).
20. Hooks that write inside an approval/cancel path need their own savepoint (QF3-6).
21. `-u` only runs suites of modules in that `-u` (S5B-4, S8M-1); `pb_hub` palette test `_NARROWER` list for manager-only ⌘K rows (S8M-5).
22. Worktree shell guard refuses compound commands with "gitlocal" paths — use scratch scripts (PRA-5, PRD-1, PRM-3).
23. Local disk is nearly full; one small DB, drop as you go, `--log-level=info` (QF2-G5, QF4-W5, W2A-5).
24. `hr.employee` attendance fields (`pb_attendance_category`, `pb_attendance_policy_id`, `pb_clock_code`, `pb_ot_special_sector`) are `groups='hr.group_hr_user'` — attendance-only users cannot read/write them (sudo-after-gate or require HR) (§D.1, `ot_ceiling.py:167-173` K-F8 note).
25. Shift template hours are wall clock; stored shift datetimes are UTC (P5 WP-0b, `schedule_grid.py:69-97`); any preview must use `_pb_shift_window` + `_pb_shift_tzname`, never naive math.

---

## L. Sudima data reality (docs only, no server access)

- Employees: 651 at the 2026-11-19/rehearsal stage, all without a workplace
  (`IMPLEMENTATION.md` "Sudima at rehearsal"); **678** latest live, all 678 without workplace;
  **27 people without an attendance policy** (`RELEASE_STATUS.md:45`).
- Roster: **12,384 draft rows**, none published (`RELEASE_STATUS.md:43`), range 19 Nov–16 Dec 2026,
  made by `configure.py` from October punches (`sudima-attendance-20261119/README.md:30`);
  rows flagged `pb_inferred=True` with evidence text (`configure.py:91`).
- Patterns: **three weekly patterns**, 517 provisional employee assignments; 84 employees
  inconsistent, 50 insufficient data (`README.md:30`). Live preview on 2026-11-24 reported
  4,645 potential new drafts and 7,739 existing entries (`RELEASE_STATUS.md:21`).
- Policy: **one draft policy**, zero active (`RELEASE_STATUS.md:43`): name "Sudima attendance -
  review before activation", tz Asia/Ho_Chi_Minh, capture 2 h before / 6 h after, night premium
  off (`configure.py:40-43`). Bands: worker [0,1) 0 h confirmed; worker 1–9 min **unconfirmed
  placeholder** (blocks activation); worker ≥10 → 4 h; manager ≥10 → 1 h; manager below 10 → 0
  (`README.md:7-9`, `configure.py:35-39`). Employees default to Worker (651 set).
- Shifts: day `SD-DAY-0730-1630` (break 11:30–12:30, normal_end 9 h) and two review-only
  night templates `SD-NIGHT-1930-0430`, `SD-NIGHT-1630-0130` (`configure.py:24-34`).
- Working calendars: matching calendars prepared but not assigned (`README.md:13`).
- Clocks: five client sources backfilled October; four non-test connectors started 18 Nov
  (`README.md:18, :30`). Workspace enabled only on Sudima (`RELEASE_STATUS.md:12`).
- Tenant email is off on sudima (publish notifications will report "no channel").

---

## Open questions / risks (could not verify from code)

1. Whether Sudima's 12,384 drafts carry `pb_policy_id` (set only if the employee had a policy
   at create time, `policy.py:241-244`) — if not, publishing them will not feed the calculation cron.
2. `_sql_constraints` on `hr.shift.template` (`shift_template.py:48`) is ignored by Odoo 19
   (§A); whether the live tables still hold a `code_company_uniq` index from an earlier
   version is unverified (check `\d hr_shift_template` on the server).
3. Whether `hr_shift` (conflicting model names) is installed on any of the five databases.
4. "Approval needed" toggle (POC) has no effect today: `requires_approval` is display-only and
   policy OT is always approval-required — scope decision for the owner.
5. POC "after N paid hours" overtime vs real per-shift elapsed `normal_end_offset`; POC global
   rates vs per-type `hr.overtime.config`; holiday/rest-day pay never auto-applied
   (`pb_day_kind` manual) — the preview must show the real model or the build must add logic.
6. Late rules on tenants without `pb_attendance_policy` (4 of 5 DBs): only `pb.attendance.rule`
   grace exists; installing the policy module elsewhere is an owner decision.
7. Holidays writes need a time-off officer, not an attendance manager; a Workforce setup
   manager may be refused on the Holidays step.
8. "Copy setup link for IT" has no RPC method; a facade calling the private `_new_invitation`
   must keep its manager check, row lock and the one-active-invitation semantics.
9. Bulk "give a working week from date X" and "one-off shift replaces planned days" have no
   existing server method; `save_pattern` replaces members whole and `clear_drafts` has no date.
10. `publish_shifts` has no company filter and publishes inferred drafts too; a go-live
    "publish N weeks" should filter by company and, if wanted, by `pb_pattern_id`/people set.
11. No 2027 Vietnam public-holiday list exists in the repo; only Rize's 2026 reference.
12. Local test DB templates may lack `pb_attendance_policy`; tests touching it must install it.
