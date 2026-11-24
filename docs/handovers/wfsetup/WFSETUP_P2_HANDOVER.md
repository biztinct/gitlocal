# WFSETUP P2 — Step 3 "Who works what": tick people, bulk actions, undo

Read first: `WFSETUP_LEDGER.md` (binding rules), `WFSETUP_OWNER_RULINGS.md` (R4 matters here), `WFSETUP_FACTS.md` sections
B, C, D.1, H, K (**do not re-derive**), `WFSETUP_P1_REPORT.md` (what exists, its gotchas), then click through step 3 of
`docs/design/workforce-setup-prototype.html` — including the three drawers and the Undo toast. That is the design of record.

Worktree `/Users/adity/Documents/GitHub/gitlocal-worktrees/wfsetup`, branch `wfsetup`. No deploy, no server access.

## 1. Scope
Replace the P1 "arrives next" panel of step 3 with the working step:
1. Team strip (one card per department: name, progress bar, "N of M have a working week"); clicking filters the table.
2. Table of every active employee of the company: tick box, person (avatar initials, name, staff number), team and site,
   late rule (Worker / Manager), working week (mini 7-day strip + name, "+N one-off" chip, or amber "Not set"), from-date.
3. Selection: click a row or its box to tick; **Shift-click ticks the range**; header box ticks everything in the current
   list; "Tick all of <team>"; "No working week yet" quick filter with its count; search by name / number / team.
   Clicking a row also makes that person the one shown in the right panel.
4. Sticky bulk bar when ≥1 ticked: **Give a working week** (primary) · **One-off shift** · **Late rule** · clear.
5. Three drawers, each with a real "What will happen" summary computed by the server BEFORE applying, then Apply, then a
   toast with **Undo**.
6. Step-3 status in the rail stays truthful after every action.

### Binding non-goals
- No roster drafts are made and nothing is published by "Give a working week" (that is step 7, P4). The drawer says so.
- No change to `pb_shift_patterns`, `pb_schedule`, `pb_hr_workforce`, `pb_attendance_policy` code. New server code lives in
  `pb_workforce_setup` only.
- Do not use `pb.shift.patterns.save_pattern` (replaces members whole — facts B.2).
- No editing of a single person's details here (name, department, site) — the row is not a form.

## 2. Plumbing decisions (made)

**Dependency**: add `pb_attendance_policy` to `depends` (owner ruling R4: detailed late rules on every site). Bump the module
version to 19.0.1.1.0. Confirm it installs on the local test DB; report what it pulls in.

**New transient model** `pb.workforce.setup.undo` (`user_id`, `company_id`, `kind`, `payload` Json, `summary`): one row per
bulk action, readable/usable only by its creator, auto-vacuumed. ACL: attendance manager CRUD.

**Facade additions** (`pb.workforce.setup`, all behind `_gate_read()` / `_gate_edit()`, all scoped to `env.company`):
- `people()` → `{rows:[…], teams:[{id,name,total,with_week}], sites:[…], total, without_week}`. Row:
  `{id, name, number, initials, department_id, department, site, group:'worker'|'manager'|false, week_id, week_name, team_name,
  week_from, week_days:[shift_id|false ×7], also_on:[names], oneoff:int}`.
  - Employees are read with sudo AFTER the gate and only these fields leave the server (facts K3, K24).
  - `number` = `pb_clock_code` or `barcode` or empty. `week_*` = the member row covering today, else the next one starting in
    the future (then `week_from` is that date and the chip reads "from <date>"). `also_on` lists other active working weeks
    covering the same days (facts B.1: not refused by the model) → the row shows an amber "2 working weeks" chip.
  - `oneoff` = count of this person's non-pattern (`pb_pattern_id` empty) draft/published roster rows from today on.
  - Return ALL rows in one call (Sudima: 678). The client filters, searches and sorts in memory so every keystroke is
    instant; it renders rows in chunks of 200 as the list scrolls. Hard cap 5,000 with a truthful "showing the first 5,000" line.
- `assign_week_preview(employee_ids, week_id, date_from, start_week=0, mode='replace')` → `{will_move, keep_theirs, already,
  ends:[{week_name, people}], team_name, new_team:bool, problems:[sentence]}` — pure read.
- `assign_week(employee_ids, week_id, date_from, start_week=0, mode='replace'|'keep')` → `{moved, kept, already, undo_id, summary}`.
  Rules, per person:
  - Same working week, already covering `date_from` on the SAME team → `already` (untouched).
  - Same working week, other team or later start → the existing member row is ended the day before / removed if it has not
    started, and a new one created (the model refuses overlapping rows for one person in one pattern — facts B.1).
  - Other working week(s) covering `date_from` or starting later: `replace` → set `date_to = date_from − 1 day`, or delete the
    row when it starts on/after `date_from`; `keep` → leave this person entirely alone (counted in `kept`).
  - Team choice: the person must be in week `start_week` of the rotation on the Monday of `date_from`'s week. Needed offset
    (facts B.1 formula) `= ((monday(date_from) − pattern.start_date).days − 7·start_week) mod cycle_days`. Reuse the team
    with that offset, else create the next lettered team ("Team B"…). More than 8 teams → UserError "This working week
    already has 8 different start points. Pick another start week." Add a unit test that proves the formula with
    `_pb_cycle_index` — do not trust it by inspection.
  - One transaction; the undo payload records every ended row's previous `date_to`, every deleted row's values, every
    created row id and every created team id.
- `oneoff_preview(employee_ids, shift_id, date_from, date_to, weekdays)` → `{days, will_add, replace_drafts, skipped:{reason:count}, examples:[≤5 sentences]}` — pure read.
- `oneoff_apply(...)` → `{added, replaced, skipped, undo_id, summary}`.
  - Range ≤ 62 days and ≤ 5,000 rows per call, else a plain UserError saying how to split it.
  - Past days are skipped ("in the past").
  - For each person/day: run the existing check `Grid._pb_check` (facts C) — `block` → skip with its reason; `warn` for
    approved leave → skip ("on approved leave"); overlap handled next.
  - Existing rows that day: DRAFT → removed (their values kept for undo); PUBLISHED / COMPLETED → the day is skipped
    ("already published"). Rows with generated attendance cannot be removed (facts D.2) → skipped.
  - Create with the ORM: `company_id = env.company`, wall-clock → UTC through `Grid._pb_shift_window` + `_pb_shift_tzname`
    (facts K25 — never naive math), state `draft`, no `pb_pattern_id`. One savepoint for the batch with per-row fallback and
    tracking disabled (precedent `pattern_engine.py:309-352`, facts K19).
- `set_late_rule_preview(employee_ids, group)` / `set_late_rule(employee_ids, group)` → writes `pb_attendance_category` with
  sudo after the edit gate (field is HR-officer-only — facts K24); when the person has no `pb_attendance_policy_id` and the
  company has exactly one non-retired policy, set it too. Returns `{changed, unchanged, undo_id, summary}`.
- `undo(undo_id)` → reverts exactly what its payload recorded, refuses (plain sentence) when something changed since
  ("Someone changed these people after you. Nothing was undone.") rather than half-undoing; consumes the row.

**Client**
- `StepPeople` component + a `pbws-drawer` (own 480 px slide-over as in the prototype — `WfDrawer` is 320 px, facts H; ESC
  and scrim close, focus moves into the drawer and returns to the bulk bar on close) + toast with Undo through the
  notification service (precedent `pb_orgchart/static/src/js/orgchart_edit.js:184-199`).
- Shift-range precedent: `pb_blueprint/static/src/js/components_tab.js:243-266`.
- Drawers call the `*_preview` method (debounced 250 ms) whenever a choice changes; Apply is disabled while the preview is
  loading or reports nothing to do; Apply shows the count ("Apply to 38"). The "They begin on: Week 1 / Week 2" choice appears
  only for rotations. "N already have a different week → Replace it / Keep theirs" appears only when N > 0.
- After Apply: drawer closes, ticks clear, table + team strip + rail status + right panel refresh, toast
  "38 people now work "Factory week, days"." with Undo (kept ~8 s; Undo calls `undo`, then refreshes).
- Keyboard: Space toggles the focused row, Shift+Arrow extends, Ctrl/Cmd+A ticks the current list, Esc clears ticks.
- States: loading skeleton rows; no employees at all; search with no match ("Nobody matches. Clear the search or the
  filter." + a Clear button); 0 working weeks exist ("Build a working week first" → step 2); read-only officer (table
  visible, no tick boxes, the read-only line); everyone scheduled (green chip in the heading, as prototype).

## 3. Design bar (verbatim, binding)
"extreme WOW, intuitive, out-of-this-world experience, best in class." Hero moment for this phase: tick a whole team, press
one button, read one honest sentence about what will happen, apply, and watch the team's bar fill — with Undo in reach.
Zero dead-ends, plain language, motion with purpose (bulk bar rises, progress bars animate, respect reduced motion),
keyboard + bulk ergonomics (above). Lucide via `ic()`, never emoji. One solid primary per bar. No "Odoo" in any user-visible
string. Screen words: "working week", "one-off shift", "late rule", "team" — never pattern, member, category, policy, draft rows.

## 4. Numbered test cases
Python (`tests/test_people.py`, tags `post_install, -at_install, wfsetup`):
1. `people()` gate + shape; officer may read, basic user refused; only `env.company` employees; archived employees absent.
2. Row week resolution: current member; member starting next month ("from"); ended member → no week; two patterns → `also_on`.
3. `assign_week` to people with no week → member rows on Team A from `date_from`; `moved` count; rail count drops.
4. `replace`: person on week X moves to Y from the 1st → X row `date_to` = day before; a not-yet-started X row is deleted.
5. `keep`: people on another week untouched and counted in `kept`; people with none are still assigned.
6. Same week again → `already`, nothing written (assert member ids and write_date unchanged).
7. Rotation start: 14-day rotation, `start_week=1`, `date_from` a Wednesday → for the Monday of that week
   `_pb_cycle_index` gives 7; a second call with `start_week=0` reuses/creates the right team; 9th distinct offset → the plain refusal.
8. Preview equals apply: for cases 3–7 the preview's counts match what apply then does, and preview writes nothing
   (compare table row counts and max(write_date) before/after).
9. `undo` after 3, 4 and 7 restores member rows exactly (same employee/team/dates) and removes created teams; a second
   `undo` of the same id is refused; another manager cannot use it; after a later change it refuses with the sentence.
10. `oneoff_preview`/`oneoff_apply` Mon–Sat over two weeks for 3 people → 36 rows, UTC datetimes equal `_pb_shift_window`,
    company set, no `pb_pattern_id`.
11. One-off over an existing DRAFT → draft replaced; over a PUBLISHED row → skipped and reported; approved leave → skipped;
    past dates → skipped; > 62 days → refusal sentence.
12. Overnight one-off (22:00–06:00) on the last day of the range ends on the following calendar day.
13. `undo` of a one-off removes the created rows and restores the replaced drafts.
14. `set_late_rule` as an attendance manager WITHOUT HR rights succeeds; policy auto-filled only when exactly one
    non-retired policy exists; undo restores previous values.
15. Officer → AccessError on every write method; preview methods allowed for officer? **No** — previews are edit-gated too.
16. 700-employee fixture: `people()` under 2 s and one SQL-count sanity check (no per-row queries — assert query count < 40).
17. Static test from P1 still green (no "Odoo", icon names exist, no emoji).
Re-run all P1 tests and the `/pb_shift_patterns`, `/pb_workforce_workspace`, `/pb_attendance_policy` suites.

Browser walk (same local recipe as P1; seed ~300 employees over 6 departments so scale is visible):
B1 team card filters; "Tick all of <team>"; bulk bar rises with the right count.
B2 Shift-click range; header box; Ctrl/Cmd+A; Esc clears.
B3 Give a working week to a team with none: summary sentence → Apply → bar fills, rail count drops, toast → Undo restores.
B4 Mixed selection (some already on another week): Replace vs Keep changes the numbers in the summary and the button.
B5 Rotation: "They begin on Week 2" → the right panel for one of them shows week 2's shifts this week.
B6 One-off shift for a date range on chosen weekdays; summary shows skipped reasons; "+N one-off" chips appear; Undo.
B7 Late rule to Manager for 5 people; column updates; Undo.
B8 Search + "No working week yet" filter together; empty result state and its Clear button.
B9 Officer: read-only, no boxes, no bulk bar.
B10 300 rows: scrolling smooth, typing in search instant; widths 1440 / 1100 / 800 / 400 without page-level horizontal scroll.
Console clean throughout. Screenshot step 3 at 1440 next to the prototype; list visual differences you could not close.

## 5. Report back (`WFSETUP_P2_REPORT.md`, committed)
As P1 §5: results per numbered item, deviations, wrong facts, self-review against §3 with the weakest point named, new
gotchas appended to the ledger, commits. On a usage limit: WIP commit, "Where I stopped", end with PAUSED.
