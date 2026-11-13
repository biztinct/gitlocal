# ETP E3 — Project time, the week on one screen — implementation report (Opus)

Handover: `E3_HANDOVER.md`. Ledger: `ETP_LEDGER.md`. Not committed, not deployed.
Clone: `p2clone`, port 8097, staging `/tmp/deployE3` (cleaned first; staged `pb_me_project_time` + `pb_me_portal`).
The staged `pb_me_portal` differs from the server's copy in exactly the five files of commit 875f3b89b (manifest,
`vi_VN.po`, `pb_me_home.py`, `test_me_home_cards.py`, `portal_templates.xml`). The staged `pb_me_project_time` is
byte-identical to the repo (md5 of every file, checked after the last run). `web.base.url` on p2clone was set to
`http://localhost:8097` before anything else.

## 1. Files added (one new module, nothing else edited)

| File | What |
|---|---|
| `pb_me_project_time/__manifest__.py` | The name and summary from the spec. Depends on `pb_me_portal` and `hr_timesheet` (project_timesheet_holidays is a soft check). Auto-install, Hidden/Tools, 19.0.1.0.0, front-end assets only. |
| `models/project_time.py` | The facade `pb.me.project.time`: `_own` guard, `enabled` / `page_state` / `session_state`, `pickable_projects`, `parse_hours`, `get_week`, `set_cell`, `save_week`, `add_row`, `copy_last_week`, `fill_row`, `week_summary`, targets from the working schedule, and the helpers `fmt_h`, `parse_rows`, `parse_key`. |
| `models/pb_me_home.py` | Home hooks: `_pbme_extra_cards` (the "Project time this week" card) and `_pbme_needs_extra` ("N days this week have no project time", amber). Both stay hidden when the person has not logged anything recently. |
| `models/res_config_settings.py`, `views/res_config_settings_views.xml` | The non-stored boolean "Employees enter project time on their self-service pages", backed by the `pb_me_project_time.enabled.<company>` parameter, shown in the stock Timesheets "Time Encoding" block. |
| `controllers/portal.py` | Extends `PbMePortal`. `GET/POST /my/project-time` and the jsonrpc routes `/cell`, `/row/add`, `/copy-last-week`, `/row/fill`, `/picker`. Every helper is prefixed `_pt_` (see ledger E15). |
| `views/portal_templates.xml` | Own Lucide icon template, breadcrumb, home tile, home card, week ring, row, grid partial, picker, page, no-employee page. |
| `static/src/scss/project_time.scss` | The grid, the ring, the picker, the phone day view, the home card, and reduced motion. |
| `static/src/interactions/project_time.js` | One Interaction: autosave, keyboard, notes, picker, copy / fill / remove, phone day strip and swipe, keeps the address bar in step. |
| `i18n/vi_VN.po` | 100 entries, exported from the installed module (`odoo-bin i18n export`), then translated. |
| `tests/common.py`, `test_project_time.py`, `test_project_time_pages.py`, `test_po_gate.py` | E3.1–E3.10 and E3.12. |

## 2. Test results

Final run (E3.11 exactly as the handover writes it): `-u pb_me_project_time,pb_me_portal,hr_timesheet --test-tags
/pb_me_project_time,/pb_me_portal`. The first run was `-i pb_me_project_time -u pb_me_portal`.
```
odoo.tests.stats: pb_me_portal: 125 tests 59.31s · pb_me_project_time: 27 tests 21.81s
odoo.tests.result: 1 failed, 1 error(s) of 114 tests when loading database 'p2clone'
FAIL:  TestMeHome.test_02_tile_meta_default_and_hidden          <- pb_me_portal pin broken by 875f3b89b (below)
ERROR: TestPbMePortal.test_01_profile_change_flow_and_audit     <- known clone artefact M19 (AccessError in engine._as_request)
```
A module-only run (`--test-tags /pb_me_project_time`) gives `0 failed, 0 error(s)`, EXIT=0.

**`test_02_tile_meta_default_and_hidden` is not caused by E3.** It pins the visible "Me" tiles to
`['/my/profile', '/my/documents', '/my/taxsheet', '/my/assets', '/my/compensation', '/my/requests']`. The kick-off
commit 875f3b89b added `('/my/expenses', 'me', 'receipt', …)` to `_TILE_ROWS` but did not update the pin:
```
AssertionError: Lists differ: [... '/my/requests', '/my/expenses'] != [... '/my/requests']
First extra element 6: '/my/expenses'
```
The test reads the registry only, so it fails with or without my module. The fix is a one-line change in pb_me_portal
(§6). I did not weaken it.

| # | Test(s) | Result |
|---|---|---|
| E3.1 | `test_e3_1_pickable_projects` | pass. The employee's company comes first and the Internal project is first in it. The company project lists exactly its two tasks, in order. The time-off task is absent. The followers-only project is absent, then present once the employee's partner follows it. The other company's project and the template project are absent. The search narrows on task name. |
| E3.2 | `test_e3_2_parse_hours` | pass. `8→8.0, 7.5, 7,5→7.5, 1:30→1.5, 1h30→1.5, 0:45→0.75, ''→0, 45m→0.75, 2h→2, 24→24`. `-1` / `25` / `abc` / `1:75` / `8..5` each give a plain message ("Hours cannot be below zero.", "One cell holds 24 hours at most.", "Type hours like 8, 7.5 or 1:30.", "Minutes go up to 59, like 1:45."). |
| E3.3 | `test_e3_3_set_cell_creates_updates_unlinks` | pass. As the employee login, one line is created: employee, project, task, date, 8 h, `name='/'`, `create_uid` = the employee login, the company, `user_id`. Saving 7.5 updates the same line. 0 with no note removes it. A note is stored as `name`. 0 while keeping the note keeps the line at 0 h; 0 with the note cleared removes it. Refused with no line written: the followers project, the other company's project, the template, a task of another project, the time-off task, 25 h in a cell, and 20 + 5 h on one day ("A day has 24 hours"). |
| E3.4 | `test_e3_4_two_backend_lines_on_one_key` | pass. The cell shows 5 (2 + 3) with two line ids. After a save, one line is left with 6 h and its first note. |
| E3.5 | `test_e3_5_leave_lines_are_shown_and_never_written` | pass. A public holiday is made on the employee's schedule; project_timesheet_holidays creates the leave line itself. A second leave line sits on an ordinary work task. The "Time off and public holidays" row is read-only, shows the holiday's name, and counts in the day total. That day's target is 0 and the week target 32. A save on the same project/task/day writes a separate line of 3 h; the leave line stays at 1 h. Clearing the cell removes only the work line. |
| E3.6 | `test_e3_6_week_targets_copy_and_fill`, `_6b_save_week_moves_hours_between_rows` | pass. Any date maps to its Monday. Targets are `[8×5, 0, 0]` = 40. Previous / next week, today flag, nothing logged ever = True. Last week's rows are offered again. Copy last week fills 1 cell and keeps the cell that already had 2 h; a second copy copies 0. "Fill with 8 h" fills 4 cells (Tuesday already had hours) → `[8,4,8,8,8,0,0]`. An added row is not stored. A project the person may not use cannot be added. The no-JS save moves 20 h between two rows on one day (lowered cells are written first) and reports an "abc" cell as an error. |
| E3.7 | `test_e3_7_switch_off`, `_7b_days_unit_is_a_quiet_block`, `test_e3_7_switch_off_pages` | pass. With the switch off: saving a cell gives the plain error, `week_summary` returns None, the page shows the off block, a no-JS POST and a jsonrpc cell are both refused with no line written, and the home has no tile and no card. The setting writes `'1'` and `'0'`. A company that counts in days gets its own quiet block and is refused writes. |
| E3.8 | `test_e3_8_home_card_and_needs_you`, `test_e3_10c_home_card_this_week` | pass. "Today" is frozen to a Wednesday. With nothing logged in 8 weeks there is no card and no needs-you row. With Monday logged and Tuesday empty the row reads "1 day this week has no project time" (amber, opens `/my/project-time`). After 24 h the card renders "24 of 40 h" and "Open the week". Over HTTP the card appears on `/my` after a line in the current week. |
| E3.9 | `test_e3_9_ownership` + the jsonrpc step of E3.10 | pass. The full-account employee's line is invisible in the employee login's week. Another person's employee record, or a bare id sent as over RPC, raises AccessError. A jsonrpc `cell` call carrying `employee_id=<other company employee>` still writes the session's own employee. The employee login still cannot read timesheet lines directly (no portal access rule was added). |
| E3.10 | `test_e3_10_flow_for_an_employee_login`, `_10b_…full_account`, `_10d_no_employee…`, `_10e_add_without_script_and_vietnamese` | pass, for both kinds of login. `GET` returns 200 with the empty-state words, the seven day headers, "0 of 40 h", `data-i="0"` and the My Timesheet link. Then: `row/add` → `cell` 8 → `{ok, week_total: 8}` → `GET` shows the row, the value and "8 of 40 h". A no-JS POST of three cells ("7:30" + note, "6", unchanged "8") saves, redirects with `done=saved` and shows "21.5 of 40 h". A refused 30 shows "Some hours did not save" with the reason. `?week=` with any date shows that week. No-JS copy into next week gives "3 cells copied from last week." `/my` shows the tile. With no employee record the page shows its own block. Adding a row without the script works. `/vi/` renders the page title in Vietnamese. |
| E3.11 | the run above | pb_me_portal 125 + pb_me_project_time 27; only the two failures explained above. |
| E3.12 | `TestE3PoGate` (4) | pass. The PO parses (also checked with the gate command: 112 rows). Every entry has the module line, an occurrence and the `odoo-python` marker where needed, a translation, and no vendor name. Every word of the 11 views has a Vietnamese line for that very view. Every `_()` / `env._()` sentence in models and controllers has its line. |
| E3.13 | browser walk | done, below. |

The first runs found and I fixed:
- Registry load failure: my method was named `_ids` (ledger E14).
- A 500 on `/my/project-time?done=saved`: my controller's `_flash` clashed with pb_ess_workforce's `_flash` (E15).
- The walk found Monday missing from keyboard moves and from the phone day view: QWeb drops `data-i="0"` (E16). A regression assertion was added.
- A test fixture: a holiday ending at 23:59 left 0.02 h of target (E20).

### E3.13 — browser walk (staged clone, port 8097 tunnelled; my own headless Chrome over DevTools)
I used a small Chrome DevTools driver of my own, written for Node 24 with no dependencies, so the shared Chrome MCP browser was never touched.
Temporary employee login `e3.ui.employee@example.com` (employee login, 8 h Mon–Fri schedule, public holiday on
Tuesday 13 Oct on its own schedule, last week's hours on two projects). That login is now **archived with a
scrambled password**. The UI server is stopped, the tunnel is closed, and the switch is back to unset (= on).

- **Home** (`01-home-desktop`): the Project time tile sits in the Time section; the card reads "0 of 32 h" with
  seven bars, "3 days empty", the My Timesheet line and "Open the week". Needs you shows "3 days this week have no
  project time" (Mon/Wed/Thu are past working days with no hours; Tuesday is the holiday).
- **Week** (`02-week-proposed`): last week's two rows are offered empty. The holiday shows as a read-only
  "Time off and public holidays" chip with 8 h. The ring reads "0 of 32 h" with "plus 8 h time off" under it.
  Under Tuesday the totals band reads "Walk holiday" instead of "of 8". Today (Fri) is highlighted and the weekend is dimmed.
- **Copy last week** (`03-after-copy`): 8 cells filled (the holiday was skipped). Toast: "8 cells copied from last
  week…". Ring "32 of 32 h". The copy button hides itself.
- **Add a project, keyboard only** (`04-picker-search`): focus the button, Enter, type "mobile test", Enter. The row
  is added and the cursor lands on the first working day.
- **Keyboard-only entry** (`05-keyboard-entry`, `19-desktop-final`): arrows into Monday, `3` Enter (saved and moved
  down), `0:30` Tab (saved as 0.5, moved right), `2` Esc (put back), ArrowRight / ArrowUp, `7.5` Enter overwrote a
  value, `2,5` Enter stored 2.5. Row, day, week and ring numbers update on every save. Bars turn indigo at target and
  amber over it; the ring turns amber at 44.5 of 32.
- **Note** (`06-note-popover`): `N` opens the popover, typed text, Enter saves; the dot stays.
- **Error** (`07-error-cell`): `25` Enter turns the cell rose; under the grid it reads "Saturday 17 October ·
  Mobile app launch · Testing: One cell holds 24 hours at most."; Esc puts the value back and clears the message.
  "abc" gives the hours message.
- **Remove a row** (`08-row-menu`): an added empty row is removed from its ⋯ menu; the address bar `rows=` updates.
- **Fill the week** (`10-fill-week`): "2 empty working days now have 8 h." Friday was skipped because it would have
  passed 24 h.
- **Reload** (`09-after-reload`): every value, note and row comes back.
- **Phone 390 px** (`11-phone-day`, `12-phone-plus-swipe`, `16-phone-leave-day`, `17-phone-wed`, `13-phone-home`):
  day strip with each day's total and a small bar; it opens on today. Tapping Wednesday puts `day=` in the address bar.
  `+` on a card stepped 1 → 1.5. Swiping left moved to Thursday. Cards show −/input/+ and a note button. The holiday
  day shows the leave chip. The ring sits at the top.
- **No script** (`14-nojs`): with scripts disabled, typing `0:45` in a cell and pressing Save week gave
  `done=saved`, "Your week is saved." and the value 0.75.
- **Vietnamese** (`15-vietnamese`): "Giờ theo dự án", "62.75 trên 32 giờ", "thêm 8 giờ nghỉ", "TH 2 … CN".
- **Switched off** (`18-switched-off`): the quiet block "Project time is switched off for your company"; `/my`
  has no tile and no card.
- **Console**: nothing from these pages in any step. Every page carries the clone's website-logo 500 (the filestore
  lacks the file — same artefact as T3B). The CSS bundle has no error banner (T24 check).

Screenshots (19): `/private/tmp/claude-502/-Users-adity-Documents-GitHub-gitlocal/9153f94c-e140-4209-bac0-0a3b24429a97/scratchpad/walk/shots/` (not versioned).

## 3. Design self-score
**Hero moment: a grid that feels like a spreadsheet.** Click or arrow into a cell; it is selected, so typing
replaces it. Enter saves and goes down, Tab goes right, Esc undoes, N writes a note. A saved cell flashes soft green
for 300 ms and nothing else. Day totals sit in a sticky band at the bottom with a thin bar each (grey under target,
indigo at it, amber over). The week ring, top right, fills and bumps as you type.

What it does that Harvest's week view does not:
1. No Save button: every cell saves on Enter / Tab / arrow / leaving the cell. Harvest saves the week as one form.
2. A refused cell keeps what was typed and the reason appears in plain words under the grid.
3. Targets come from the person's own working schedule, so a holiday makes the week "of 32". Public holidays and
   time off appear in the grid as read-only chips with their names, and appear under the ring once ("plus 8 h time off").
4. "Copy last week" copies hours, not just rows, and never overwrites a typed cell.
5. One address on the phone: one day at a time, swipe or tap, ± half an hour, the same rows.
6. Works with no script at all.

Other parts of the bar:
- **Zero dead-ends**: switched off; counted in days; no project available ("No project lets you log time yet. Ask HR to open one." plus the Ask HR door); no employee record; a project closed for new time ("Closed for new time", read-only); the time-off task never offered.
- **Motion**: ring, bars, total bumps, the new-row glow, popovers. All switched off under reduced motion.
- **Icons**: Lucide SVG only, in the module's own icon template.

Self-score **8.5 / 10**. Short of 10:
- Weekend hours turn the day amber ("over"), which follows the spec but can read as a warning.
- Removing the last row does not bring back the empty-state picture until a reload.
- The picker shows at most 200 tasks per project, though searching on the server still finds them.

## 4. Learn impact
I grepped `learn_content.json`, `anchors.json`, `engine/screens.js`, `engine/fixture.js` and `docs/tutorial_poc/author/data.js`
for `/my`, the employee home and project time. The only `/my` mention is "Only an employee? You start on My
Payobook". **Nothing in Learn is affected.**

## 5. Decisions the handover did not make + proposed ledger rows + "Send week"
1. **Leave, targets and the ring.** The ring and the day bars compare the person's own project hours with the
   day's target. Leave hours count in the day total and the week total, and appear once under the ring. A day with only
   leave shows a grey "leave" bar and the leave name, never amber. Without this, D4 (holiday → target 0) plus "leave
   counted in the day total" would paint every holiday amber as "over".
2. **Approved personal time off also lowers that day's target.** This is the stock schedule rule (work time minus
   leave), the same treatment as a public holiday.
3. **Time-off task exclusion = each company's `leave_timesheet_task_id`.** It does not use stock's wider
   `is_timeoff_task` (which also catches any task carrying a leave line), because E3.5 requires writing on a project/task
   that has a leave line. Leave lines themselves are never written.
4. **Copy last week** skips days that have leave this week, does not copy notes, and skips a cell that would pass 24 h.
   **Fill** skips a day where 8 h would pass 24 h. Both say the real count.
5. **Closed tasks** are hidden from the picker but stay writable on an existing row. A row on a project the person
   can no longer use is read-only ("Closed for new time").
6. **Project-level rows** (no task) are allowed. The picker calls them "The whole project, no task". Projects that
   belong to no company sit in a group "Projects shared by every company".
7. **Empty rows travel in the address bar.** `rows=` is absent → last week's rows are offered; present → exactly those
   rows. The script keeps it in step so a reload shows the same rows. The phone's open day travels as `day=`. Nothing is
   stored (D1).
8. **Add / Copy / Fill answer with the grid re-drawn by the server** (only the grid swaps; the cursor lands in the
   new row). Every word stays in QWeb, and the jsonrpc routes render in the page's language (`lang` sent by the script).
9. **Over-24 refusal wording**: "That would make 25 h on Monday 12 October. A day has 24 hours."
10. The manifest summary keeps "from My Payobook" as specified. Nothing user-visible says the vendor's name.

### Proposed ledger rows
| # | Gotcha / fact | How to apply |
|---|---|---|
| E14 | A model method named `_ids` (or any BaseModel slot) breaks the registry load: `AttributeError: 'pb.me.project.time' object attribute '_ids' is read-only`. | Never name a method after a BaseModel attribute (`_ids`, `_fields`, `_name`…). Prefix helpers (`_key_ids`). |
| E15 | Portal controller helpers share one combined class with every other `/my` controller. My `_flash(Pt, done, n)` collided with pb_ess_workforce's `_flash(kw)` → a 500 on the page. | Prefix every helper in a phase controller with the module's code (`_pt_*`, `_ex_*`, `_tr_*`). |
| E16 | QWeb leaves out a `t-att-*` whose value is falsy: `t-att-data-i="c_index"` drew no `data-i` for Monday (0). Keyboard moves, the phone day view and Monday's totals silently skipped Monday. | Write `t-att-data-x="str(value)"` for anything that can be 0; assert `data-i="0"` in an HttpCase. |
| E17 | A parameter written from `odoo-bin shell` is not seen by a running clone server (cached). | In the shell: `set_param` → `env.registry.clear_cache()` → commit → `env.registry.signal_changes()` → commit. |
| E18 | `while pgrep -f "http-port=8097"` inside `ssh '…'` matches its own command line and never ends; `pkill -f "<that text>"` kills your own ssh. | Stop a clone server with `systemctl stop <unit>` and check `systemctl is-active`. |
| E19 | pb_me_portal `TestMeHome.test_02` pins the "Me" tiles; 875f3b89b added `/my/expenses` without updating it. | Fable: add `'/my/expenses'` to the expected list (§6). |
| E20 | A public holiday ending at 23:59 leaves one minute of work (0.02 h target; stock writes a 7.98 h leave line). | Fixtures and demo holidays run 00:00 → next day 00:00. |

### "Send week" proposal (D9 — not built)
- New carrier `pb.project.week`: employee, Monday, company, `state`, a list of the week's own non-leave line ids, and a
  hash of (line id, hours, note).
- Wired like `pb.expense.claim`: new process key `project_week`, default route Their manager → the project manager
  (or HR lead), registered with `register_chain`. **Never** the attendance packet `pb.timesheet.packet` (ledger E9 §6).
- While a week is submitted or approved, the facade refuses `set_cell` / `save_week` / copy / fill for that week
  ("Sent for approval — ask your manager to send it back"). A small `_check_can_write` override on
  `account.analytic.line` stops the backend editing too.
- Sending a week back unlocks it. The grid header gets the approval steps and a "Send week" button. My requests gets a source.

## 6. Shared-module changes I believe are needed (listed, not done — E-R1)
1. **pb_ess_workforce — the reverse link on `/my/work/timesheet`** (D8): one line under the week table, "Looking for
   the hours you spent on each project? That is Project time." → `/my/project-time`, drawn when
   `'pb.me.project.time' in env and env['pb.me.project.time'].session_state() == 'ok'`, plus its VI line.
2. **pb_me_portal `tests/test_me_home.py:68-70`**: add `'/my/expenses'` to the expected "Me" list (E19). It breaks on
   the current committed pb_me_portal regardless of the ETP modules.
3. Optional, pb_me_portal: no edit needed for the tile; the `/my/project-time` row and words already exist and the
   tile draws from this module.

## 7. Self-review against Scope and Non-goals
**Scope**
- Module: name / summary / depends / auto-install / category / version / front-end-only assets as specified. Done.
- Facade methods per the Scope list, with the `get_week` shape given. Done. Additions: `kind`, `pickable`, `has_lines`
  on rows; `logged` / `leave_hours` / `state` / `pct` on days and week (decision 1).
- Routes: page GET + no-JS POST, the four jsonrpc routes, and `/picker` (jsonrpc). Done.
- Settings box in the Timesheets block plus the parameter; translations; Learn. Done.
- D1: whitelist create, one line per project/task/day, duplicates summed then collapsed, 0 + no note removes, 24 h per
  cell and per day. Done.
- D2: the stock employee rule re-stated and re-checked on every write. Done (decision 3).
- D3: unset = on; off → off block, no tile, no card, writes refused. Done.
- D4: targets from the schedule, holiday → 0. Done.
- D5: Monday start, `?week=` any date, previous / next / back to this week, dates in the reader's language, no limits. Done.
- D6: API shapes. Done; `cell` also returns `hours_text`, the states and the percentages.
- D7: tile only when on; card and needs-you row only when on and active in the last 8 weeks; no count; no My requests
  source. Done.
- D8: page and card link to My Timesheet when pb_ess_workforce is installed. Done. The reverse link is listed in §6.
- D9: nothing built; proposal above.

**Non-goals (none crossed)**: no approval / lock / send week; no manager or HR view; no billing fields; no timers; no
task creation and no change to projects or tasks; no edit to pb_me_portal, pb_ess_workforce, hr_timesheet, project,
pb_hr_workforce or biz_week_grid (own grid); no new stored field or table; no rail item; days encoding shows the quiet block.

**Safety rails**:
- Every write follows `_own` (an `hr.employee` record whose user is the caller) and the pickable check. No route reads
  an employee.
- Leave lines are excluded from every write search.
- Failed cell writes return `{ok: False, error}` and the grid keeps the typed value.
- Every jsonrpc call runs in a savepoint; unknown exceptions are logged and answered in plain words.
- Front-end bundle only.

**Clone side effects (p2clone only)**:
- pb_me_project_time 19.0.1.0.0 is installed. pb_me_portal 19.0.3.4.0, hr_timesheet and its dependents were upgraded
  on p2clone only.
- The archived walk login, its employee, the "E3 walk 8 h" schedule with one holiday (13 Oct 2026), three walk projects
  ("Website refresh", "Mobile app launch", "Client onboarding — Rạng Đông") and the walk login's lines are left on p2clone.
- `web.base.url` = `http://localhost:8097`.
- No live service, live database, p0clone / p1clone or sibling staging directory was touched.
