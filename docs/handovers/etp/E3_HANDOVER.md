# ETP E3 — Project time, the week on one screen (handover for Opus)

Read first: `ETP_PROGRAM.md`, `ETP_LEDGER.md` (rules E-R1…E-R13, rows E9–E11 are yours), then the precedents
`../tiers/T3B_HANDOVER.md` + `T3B_REPORT.md` (pb_ess_workforce's Clock page: a facade with sudo seams, a
per-company switch without a stored field, an interaction with a no-JS fallback, the tunnelled browser walk) and
`pb_ess_workforce/views/portal_templates.xml:240-326` (`/my/work/timesheet`, the attendance week page whose
`pbew-weeknav` chrome you reuse the look of). Repo `CLAUDE.md` applies. You do not deploy; Fable does. Plain words
in every string a person can see. **Your clone is `p2clone`, port 8097, staging `/tmp/deployE3`** (E-R7; set
`web.base.url` on p2clone to `http://localhost:8097` before the walk). Two sibling builds run at the same time on
p0clone/p1clone — never touch their staging dirs, databases or modules (`pb_me_expense`, `pb_me_trip`) and never
edit `pb_me_portal` or `pb_ess_workforce` (E-R1).

## What E3 is, in the owner's words
"Project timesheet entry on the portal … time sheet entry should allow user to enter for the week in one screen in
table format unless you have other better design." After E3 every employee can **enter the hours they spent on
each project, for a whole week, on one screen** from My Payobook — on a phone one day at a time — and see the
week's total against what they are expected to work. This is PROJECT time (`account.analytic.line` on projects
and tasks). It is not the attendance "My Timesheet" page (`/my/work/timesheet`, scheduled vs worked) — the two
pages link to each other and say so in one line each.

## Design (binding, E-R10)
Measured against Harvest / Toggl Track / Clockify's week view. **Hero moment: a grid that feels like a
spreadsheet.** Desktop (≥ 768 px): a sticky header row Mon–Sun with the date under each day name, today
highlighted, weekend columns dimmed; one row per project (+ task when a task is chosen) with the name on the left
(sticky), seven cells, a row total on the right; a **totals row** at the bottom with the day totals and, under
each, the day's expected hours as a thin bar that fills (grey under target, indigo at target, amber over);
top-right a **week ring** "32 of 40 h" that animates as cells change. Cells are inputs: click or arrow-key into a
cell, type `8`, `7.5`, `1:30` (accepted and normalised to decimal hours), Enter saves and moves down, Tab moves
right, Esc reverts, arrows move; a saved cell flashes a 300 ms soft green and shows nothing else (no "Saved!"
noise); an error cell turns rose with the reason under the grid. Each cell may carry a one-line note (`n` on a
focused cell or the small corner dot opens a popover; a cell with a note shows the dot). Rows: "Add a project"
opens a searchable picker (projects grouped by company, tasks under each when the project has tasks; the Internal
project's Training / Meeting first); a row with no hours all week can be removed; rows persist for the week they
have hours in and are proposed again next week ("last week's rows" are pre-listed empty so the person just types).
Bulk: **"Copy last week"** (fills empty cells from last week's rows and hours; never overwrites a non-empty cell);
"Fill the week with 8 h" on a row's menu (only cells that are empty, only working days). Leave days (lines made by
public holidays or time off) render as read-only grey cells with the leave name, counted in the day total. Phone
(< 768 px): a day strip Mon–Sun with the day totals as small bars, one day open at a time (swipe or tap), the
rows of that day as cards with a numeric input and ± 0.5 h buttons; the same picker; the week ring at the top.
Empty week + no rows ever: "Nothing logged this week yet. Add a project and type your hours — they save as you
go." + the Add button. Zero dead-ends: the per-company switch off → the quiet "switched off" block; no project
pickable → "No project lets you log time yet. Ask HR to open one."; the leave task never appears in the picker.
Motion: ring and bars animate on change; reduced-motion respected. No-JS fallback (E-R8): the whole grid is a form
with a "Save week" button that POSTs every cell; JS turns it into autosave per cell.

## Decisions already taken (do not re-open)
- **D1 No new table.** Hours are stock `account.analytic.line` rows (one per project/task/day, `unit_amount` in
  hours, `name` = the note or `'/'`, `employee_id` = the session employee, `date`, `project_id`, `task_id` or
  False, `company_id` from the project as stock derives it — let stock `create()` derive accounts/company; pass
  only the whitelist `project_id, task_id, date, unit_amount, name, employee_id`). Written under sudo after the
  ownership guard (E-R2/E-R3, ledger E9): a cell write finds the line by (employee, project, task, date) among
  lines that are NOT leave lines (`holiday_id` / `global_leave_id` falsy — read the field names
  `project_timesheet_holidays` adds, server copy `project_timesheet_holidays/models/account_analytic.py`), updates
  `unit_amount`/`name`, creates when absent, **unlinks when the new value is 0 and the note is empty**. More than
  one stock line for the same key (made in the backend) → the grid shows their sum and a write updates the first
  and unlinks the rest — say so in a comment and a test. Max 24 h per cell and per day; the grid refuses more with
  the reason.
- **D2 Who may log where** (ledger E10): `pickable_projects(emp)` = sudo search `project.project` `[('active','=',True),
  ('allow_timesheets','=',True), ('is_template','=',False), ('company_id','in',[False, emp.company_id.id])]` then
  keep `privacy_visibility in ('employees','portal')` OR `emp.user_id.partner_id in project.message_partner_ids`;
  tasks = active `project.task` of those projects minus `project.company_id.leave_timesheet_task_id` (and any task
  whose project is the leave project) — read the field names on the server copy of `project_timesheet_holidays`.
  A line can only be written against a pickable project/task (re-checked on every write). The Internal project of
  the employee's company is listed first; a company with none (Payobook Singapore) simply has no such row.
- **D3 Per-company switch, no stored field** (clone of T3b D3): `ir.config_parameter`
  `pb_me_project_time.enabled.<company_id>` (`'1'` on; **default on when unset**), a `res.config.settings`
  boolean "Employees enter project time on their self-service pages" placed in the stock Timesheets settings block
  (`hr_timesheet` settings view — find the block id on the server copy); when off the page shows the quiet
  switched-off block, the tile and the home card are not drawn, and writes raise the plain UserError.
- **D4 Expected hours**: per day from the employee's working calendar (`emp.resource_calendar_id` →
  `_get_work_hours`/attendance intervals for that date in the employee's tz — read `pb_ess_workforce/models/ess_workforce.py:305-339`
  `get_my_week` for how the attendance page computes the scheduled hours and reuse the same approach, not its
  code; soft-read its facade only if trivially possible, otherwise compute from the calendar); week target = the
  sum. A public holiday on the calendar (`global_leave_ids`) → target 0 that day and the leave line is shown.
- **D5 Week semantics**: Monday start (`_monday`), `?week=YYYY-MM-DD` (any date → its Monday), prev/next/This
  week nav like `/my/work/timesheet`; dates render in the employee's language; no future limit (a person may
  pre-fill next week), no past limit in this release (a lock is a non-goal).
- **D6 Autosave API**: `type='jsonrpc'` `POST /my/project-time/cell` `{project_id, task_id, date, hours, note}` →
  the facade's `set_cell` → returns `{ok, hours, day_total, week_total, row_total, error}`; `POST /my/project-time/row/add`
  `{project_id, task_id}` (returns the row's markup data), `POST /my/project-time/copy-last-week` `{week}`, `POST
  /my/project-time/row/fill` `{project_id, task_id, week, hours}`. The no-JS path: `POST /my/project-time` with
  every cell as `h-<project>-<task>-<date>` (+ `n-…` notes) → `save_week`. All through the same facade methods.
- **D7 Home**: tile `/my/project-time` (registry has it; draw it with `portal_docs_entry` guarded `t-if="pbme_home"`
  and only when the switch is on; `placeholder_count` = this week's hours as "32 h" is NOT a count — leave the
  count off); an extra card via `_pbme_extra_cards` "Project time this week" (seven thin bars + "32 of 40 h" +
  "Open the week") drawn only when the switch is on AND the employee has logged any project time in the last 8
  weeks (quiet at zero: a person who never uses it sees nothing); needs-you row via `_pbme_needs_extra` ("2 days
  this week have no project time" → the week, tone `amber`) under the same 8-week condition, counting past working
  days of the current week with a target > 0 and 0 logged hours. No My requests source (nothing is requested).
- **D8 Link both ways, one line each**: the attendance page is not edited (E-R1) — your page says "Looking for
  when you clocked in and out? That is My Timesheet." → `/my/work/timesheet` only when `'pb.ess.workforce' in self.env`;
  your home card carries the same link. The reverse link is listed in the report for Fable to add to pb_ess_workforce.
- **D9 No approval, no lock, no manager view** in this release; the report proposes how a "Send week" would attach
  to the engine (a separate process key and carrier, never the attendance packet — ledger row E9 §6).

## Scope (binding)
Module `pb_me_project_time`: name "Employee Self-Service Portal — project time", summary "Your hours by project,
week by week, from My Payobook", depends `['pb_me_portal', 'hr_timesheet']` (`project_timesheet_holidays` is a
soft check: `'global_leave_id' in Line._fields`), `auto_install: True`, category Hidden/Tools, version
`19.0.1.0.0`, assets `web.assets_frontend` only (`static/src/scss/project_time.scss`,
`static/src/interactions/project_time.js`).
Facade `pb.me.project.time` (AbstractModel): `enabled(company)`, `pickable_projects(emp)` → grouped rows for the
picker, `get_week(emp, monday)` → `{week:{monday, days:[{iso, label, dnum, is_today, is_weekend, target, total,
leave:[{name, hours}]}], total, target, prev, next}, rows:[{project_id, task_id, label, sub, company, cells:[{iso,
hours, note, line_ids, locked}], total}], can_copy_last_week, empty_ever}`, `set_cell(emp, project_id, task_id,
date, hours, note)`, `save_week(emp, monday, cells)`, `add_row(emp, project_id, task_id, monday)` (a row with no
hours is remembered for the session only: pass it back as a `rows=` query/hidden field — no table), `copy_last_week(emp,
monday)`, `fill_row(emp, project_id, task_id, monday, hours)`, `parse_hours(text)` (`8`, `7.5`, `7,5`, `1:30`, `1h30`,
`` → 0; refuses negatives, > 24, junk), `week_summary(emp)` for the home card.
Routes (`controllers/portal.py`, class extending `PbMePortal`): `GET /my/project-time` (`?week=`, `?rows=`), `POST
/my/project-time` (save week, no-JS), the four jsonrpc routes above, `GET /my/project-time/picker` (jsonrpc or
http fragment for the picker's search). Settings view + the switch. Translations `i18n/vi_VN.po` (E-R9). Learn: E-R12.

## Tests (numbered; clone run E-R7; fixtures: `share_emp` (portal login + employee in a company that has an
Internal project; give the employee a calendar with 8 h Mon–Fri), `plain` (full account + employee), `other`
(employee of another company); a project of the employee's company with two tasks; a `followers`-only project
the employee does not follow; a project of the other company)
- **E3.1** `pickable_projects`: the Internal project first, the company project with its two tasks, no leave task,
  not the `followers` project (then follow it as the employee's partner → present), not the other company's; a
  template project is never listed.
- **E3.2** `parse_hours` table: `8→8.0`, `7.5→7.5`, `7,5→7.5`, `1:30→1.5`, `1h30→1.5`, `0:45→0.75`, `''→0`,
  `-1`/`25`/`abc` → the plain error.
- **E3.3** `set_cell` as `share_emp`: creates one line with `employee_id` = their employee, `project_id`, `task_id`,
  `date`, `unit_amount`, `name='/'`, `create_uid` = the share user, `company_id` = the project's/their company;
  again with 7.5 → the same line updated, still one; with 0 and no note → unlinked; with a note → `name` = the note;
  a cell on a non-pickable project → refused, no line; > 24 → refused; a day total > 24 → refused.
- **E3.4** two backend lines on the same key → `get_week` shows their sum; `set_cell` → one line left with the
  new value.
- **E3.5** a leave line (create one the way `project_timesheet_holidays` does, or directly with `global_leave_id`
  / `holiday_id` set) → rendered `locked` with its name, counted in the day total, never written: `set_cell` on
  that key writes a separate non-leave line and leaves the leave line alone.
- **E3.6** `get_week`: targets from the calendar (8 × 5 = 40, weekend 0), `prev`/`next` Mondays, `is_today`,
  `empty_ever` True before any line; `copy_last_week` copies rows + hours into empty cells only (a filled cell
  keeps its value), `fill_row` fills only empty working-day cells with 8.
- **E3.7** the switch off (`'0'`) → `set_cell` raises the plain UserError, the page shows the switched-off block,
  the tile and the home card are absent; the settings field writes `'1'`/`'0'`.
- **E3.8** home: `week_summary` after 24 h logged → the extra card present with "24 of 40 h"; needs-you row counts
  the past working days with 0 h (run with a frozen "today" = a Wednesday: Mon logged, Tue empty → "1 day");
  with no line in 8 weeks → no card, no row (quiet at zero).
- **E3.9** ownership: `plain`'s lines are invisible in `share_emp`'s `get_week`; a jsonrpc `set_cell` as
  `share_emp` can never produce a line with another `employee_id` (the parameter is not even accepted).
- **E3.10** HttpCase as `share_emp` AND `plain` (T-R6): `GET /my/project-time` 200 (empty-state words, the seven
  day headers, the ring "0 of 40 h"); jsonrpc `row/add` → jsonrpc `cell` 8 on Monday → `{ok, week_total: 8}` →
  `GET` again: the row, the cell value, "8 of 40 h"; the no-JS `POST` with two cells → both saved; `?week=` prev →
  the previous week; `/my` shows the tile and (after the line) the card; `/my/work/timesheet` link present only
  when pb_ess_workforce is installed on the clone (it is).
- **E3.11** Existing suites green: `-i pb_me_project_time -u pb_me_portal,hr_timesheet --test-tags
  /pb_me_project_time,/pb_me_portal`. Known clone artefacts: T31/T35, M19.
- **E3.12** PO gate; every word of the page, picker, settings, tile, card and needs-you row has a VI line for its own
  view.
- **E3.13** Browser walk on the staged clone (port 8097 tunnelled; temporary employee login archived after):
  desktop: add a project, type hours with the keyboard only (arrows, Enter, Tab, Esc), see the ring and bars move,
  note popover, copy last week, remove a row, reload → values persist; phone 390 px: day strip, ± buttons; the
  switched-off block; console clean; screenshots named in the report.

## Non-goals (do not do)
- No approval/lock/"send week", no manager or HR view, no billing/customer fields, no timers/start-stop, no
  task creation, no changes to projects or tasks, no edits to `pb_me_portal`, `pb_ess_workforce`, `hr_timesheet`,
  `project`, `pb_hr_workforce`, `biz_week_grid` (E11 — write your own grid), no new stored field or table, no
  sidebar item, no days-unit encoding (companies here encode hours; if `timesheet_encode_uom_id` is days, show the
  switched-off block with "Your company counts project time in days, which this page does not do yet." and report).

## Safety rails
- Every write sits after the ownership guard and the pickable check; `employee_id` is never a parameter.
- Leave lines are never written or unlinked (E9); a write touches only lines whose `employee_id` is the person's.
- A failed cell write returns `{ok: False, error}`; the grid shows it and keeps the typed value for retry.
- Only `web.assets_frontend`; no backend bundle is loaded on the portal.

## Report back (write `docs/handovers/etp/E3_REPORT.md`)
1. Files changed/added. 2. E3.1–E3.13 results with the clone log's summary lines and the browser walk. 3. Design
self-score (hero moment named; what the grid does that Harvest's does not). 4. Learn impact. 5. Decisions +
proposed ledger rows + the "Send week" proposal (D9). 6. Shared-module changes you believe are needed (listed, not
done — including the reverse link on `/my/work/timesheet`). 7. Self-review per Scope and Non-goal item.
