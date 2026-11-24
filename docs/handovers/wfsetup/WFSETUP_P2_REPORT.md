# WFSETUP P2 — report (step 3 "Who works what": tick people, bulk actions, undo)

Built 2026-11-24 in the worktree `gitlocal-worktrees/wfsetup`, branch `wfsetup`. Not pushed, not deployed.
Engineering document: real technical names on purpose. Screen strings contain no vendor name (static gate S1).

## 1. Result summary

| What | Result |
|---|---|
| Numbered tests 1–16 (`tests/test_people.py`, tag `wfsetup`) | **16 / 16 pass** (+2 extra cases, below) |
| Case 17 static gates (`tests/test_static.py`, 4 methods) | **4 / 4 pass** |
| P1 tests (`tests/test_setup.py`, 17) | **17 / 17 pass** |
| Baseline (P1 code + `pb_attendance_policy` installed) | `0 failed, 15 error(s) of 61 tests` — all 15 in `pb_shift_patterns` (see §3, WS9) |
| After P2, all four suites | `pb_shift_patterns` 29, `pb_workforce_workspace` 11, `pb_attendance_policy` 10, `pb_workforce_setup` 39 (stats line 45): **0 failed, 0 errors** (the one failure in the first full run was my own test 1 expecting the old initials; fixed and re-run, see §1 note) |
| `pb_attendance_policy` standalone engine (`python -m unittest test_engine_standalone`, run from its tests folder) | 11 / 11 OK |
| Browser walk B1–B10 | **10 / 10 pass** (notes below) |
| Console during the walk (manager + officer) | no errors; one unrelated warning (biz_debrand manifest icon size) |
| `people()` on 710 people (case 16) | **0.337 s, 12 queries** |

Commands (private conf in the scratch area, addons path = this worktree, DB `wfs2_base` = copy of `upd_p6_t_tpl` + one `-u all`):
- baseline: `-i pb_workforce_setup,pb_attendance_policy --test-enable --test-tags /pb_shift_patterns,/pb_workforce_workspace,/pb_attendance_policy,/pb_workforce_setup` (P1 code)
- after: `-u pb_workforce_setup,pb_shift_patterns,pb_workforce_workspace,pb_attendance_policy` with the same tags, then
  `-u pb_workforce_setup --test-tags /pb_workforce_setup` after the test-1 fix.

`pb_attendance_policy` installs cleanly on the template copy; it pulled in **only itself** (its dependencies
`pb_clock, pb_schedule, pb_timesheet_approval, pb_hr_payroll_formula, pb_attendance_flow, pb_settings,
pb_shift_patterns` were already installed or came in through `pb_workforce_workspace`). Its 15-minute cron arrives with it
(it only calculates ACTIVE policies).

### Numbered tests
| # | Case | Result |
|---|---|---|
| 1 | `people()` gate (basic refused, officer reads), shape (exact key set), only this company, archived absent, team counts, HR-only clock number read behind the gate | pass |
| 2 | current member; next-month member → `week_from` + `week_now False`; ended member → no week; two weeks → `also_on` | pass |
| 3 | 4 people without a week → member rows Team A from today; `moved 4`; rail count drops by 4; `without_week` = rail | pass |
| 4 | replace: X row ends the day before; a not-yet-started X row is deleted; `ends` lists X for 2 | pass |
| 5 | keep: X row untouched (date_to + write_date), counted in `kept`; people without a week assigned | pass |
| 6 | same week again → `already 3`, `undo_id False`, snapshot of 5 tables identical, member write_dates identical | pass |
| 7 | 14-day rotation, start 3 weeks back, `start_week=1` from a Wednesday → `_pb_cycle_index(monday) == 7` and every day of that week = 7+i (proved, not inspected); `start_week=0` → index 0; same start reused; 10-day cycle: 7 new start points then the 9th refused in preview (sentence) and apply (UserError) | pass |
| 8 | preview = apply inside every case 3–7 (helper) + a mixed keep/replace case; previews write nothing (count, max write_date, max id of 4 tables + employee write_date) | pass |
| 9 | undo after 3, 4 (ended row's old end date and deleted row come back), 7 (created team removed); second undo refused; other manager refused; after a later change → "Someone changed these people after you. Nothing was undone." and nothing changed | pass |
| 10 | Mon–Sat × 2 weeks × 3 people = 36 rows, UTC = `_pb_shift_window`, company set, no working-week mark, 07:30 VN = 00:30 UTC; run as an attendance manager **without** HR rights | pass |
| 11 | draft replaced; published day skipped; approved leave skipped; past days skipped; > 62 days refused (preview sentence + apply UserError) | pass |
| 12 | 22:00–06:00 on the last day ends 06:00 the next calendar day | pass |
| 13 | undo removes the 10 added rows and recreates the replaced draft with the same employee/shift/date/UTC times/state/company; a published row refuses the undo | pass |
| 14 | late rule as attendance manager without HR rights; undo restores; with exactly one non-retired rule set people without one are linked (and undo unlinks); with two, nobody is | pass |
| 15 | officer: all 7 write/preview/undo methods → AccessError | pass |
| 16 | 700 + 10 people, 6 teams, 300 on a week, 200 on a rotation: `people()` 0.337 s, 12 queries (limits 2 s / 40) | pass |
| 17 | static: no vendor name, every icon exists, no emoji, new tag | pass |
| extra 17b | right-panel default person = first by name with a week, never the administrator's employee (owner addition) | pass |
| extra 17c | `make_drafts` by an attendance manager without HR rights works with the policy module installed (WS9 guard) | pass |

### Browser walk (local server, port 8190, host `wfs2.localhost`, `--max-cron-threads=0`, 301 people in 7 teams)
Clicks were driven with the Chrome tools: keyboard items with real key presses (`press_key`, `type_text`); mouse items
with `evaluate_script` dispatching click / Shift-click events on the real elements (a full page snapshot of 200 rows is
too large for the snapshot tool). Screenshots were taken at each step.

| # | Result | Notes |
|---|---|---|
| B1 | pass | "Spray line" card filters to 60 rows (`aria-pressed`), "Tick all of Spray line" → bulk bar rises: "60 people ticked" |
| B2 | pass | Shift-click row 2→6 ticks 5; header box indeterminate then ticks the list (60), again clears; real **Cmd+A** ticks the list; real **Shift+↓ ×2, ↓, Space** ticks 4 and moves the panel; real **Escape** clears (needed the fix WS10) |
| B3 | pass | 60 people → "60 people move to Factory week, days from Tue 24 Nov." → Apply → card "All 60 have a working week" (bar 100 %), rail 199 → 139, toast with Undo; Undo on a second team (UV coating) → card back to "0 of 42", rail back to 139 |
| B4 | pass | Packing (6 of 54 already on Factory week) → Office week: Replace "54 move… / Factory week, days ends on Mon 23 Nov for 6 of them" + "Apply to 54"; Keep "48 move… / 6 keep the week they already have" + "Apply to 48" |
| B5 | pass | 2 CNC people → Day and night rotation, "They begin on Week 2" → "In the week of Tue 24 Nov they work week 2 of the rotation."; clicking one row → panel "Day and night rotation · week 2", Tue–Sat Factory night 19:30 |
| B6 | pass | 3 people, Mon 23 – Sun 29, Mon–Sat: "14 one-off shifts will be added… 4 days are left out: in the past (3), already published (1)" + examples; "+5 one-off" chips; Undo → chips back (the pre-existing published row keeps its "+1") |
| B7 | pass | 5 people → Manager: options show the real lateness lines; "5 people change… 5 people are also linked to your late rules"; column reads Manager; Undo → Worker |
| B8 | pass | "No working week yet" (137) + typed "nguyen" → 12 rows (accent-free match on "Nguyễn"); " zzz" → "Nobody matches. Clear the search or the filter." + Clear → filters reset, focus back in search |
| B9 | pass | officer: read-only line, no tick boxes, no bulk bar, Cmd+A / Space tick nothing, clicking a row still moves the panel; console clean |
| B10 | pass | 301 rows: 200 rendered, scrolling the list loads the rest; typing in search 32–100 ms per keystroke incl. two frames; widths 1440 / 1100 / 800 (window) and 400 (emulated viewport, WS6) — no page-level horizontal scroll, nothing clipped outside the table's own scroll area; drawer is full width at 400 |

### Visual differences from the prototype at 1440 that remain
1. Display font falls back to Inter (Manrope not hosted) — as P1.
2. Name and staff number are stacked in two lines (the prototype has them on one line); on one line the names were cut to "Bùi Đức H…" in the 750 px centre column.
3. Week names are cut with "…" in the Working week column at 1100 px and below (full name in the tooltip).
4. The toast is the web client's notification (top right, white), not the prototype's dark bottom-centre pill.
5. Team card text is "N of M have a working week" (prototype "N of M scheduled"), so cards wrap to two lines at 1440.
6. The rows the right panel is showing get a 3 px indigo edge (not in the prototype) so the "follow the row" link is visible.

## 2. Deviations from the handover (and why)
1. **New `hr.shift.planning.create` override in `pb_workforce_setup` (`models/roster.py`).** Installing `pb_attendance_policy`
   (the new dependency) made 15 `pb_shift_patterns` tests fail: the policy module's roster hook reads an HR-only employee
   field as the caller, so every roster create by an attendance manager without HR rights raises AccessError — the working-week
   draft engine included (WS9). That would have reached every site at deploy. The override fills `pb_policy_id` from a sudo read
   before that hook; same value, no new behaviour. The handover's non-goal (no change to `pb_attendance_policy` code) is kept.
2. `people()` row has two extra keys: `week_no` (rotation week shown as "· week N") and `week_now` (covers today). Payload
   also has `capped`, `cap`, `today`.
3. "Has a working week" keeps P1's rule (covers today, P1 case 16). A future start shows a "starts <date>" chip and still counts
   under "No working week yet" until that day. The drawer's default date is **today** (prototype: 1 Dec) so the team bar fills on
   Apply; a past date is refused ("Pick today or a later date. Past weeks stay as they were.").
4. Previews return refusals as `problems: [sentence]` instead of raising (the drawer shows them); applies raise UserError.
   Previews are edit-gated as case 15 asks.
5. Preview payloads carry ready-made date text (`date_text`, `ends_text`) and `rotation_weeks`/`kept`; one-off preview carries
   `skipped_list` (code, label, count) next to `skipped`.
6. One-off: a day is also skipped when the new shift would overlap a shift on a neighbouring day ("overlaps another shift"),
   and when the day's draft has clock-ins ("already has clock-ins"). OT-ceiling warnings do not skip (they are advisory).
   Holidays are not skipped (a one-off is a deliberate choice).
7. Late rule: when nobody changes group but people get linked to the one rule set, the summary says so; the drawer's options
   show the real lateness lines of that rule set ("under 1 min: nothing off · 1 to 9 min: 0.5 h off · …").
8. Undo toast sentences are fixed per kind ("Undone. Their working weeks are back as they were.") rather than echoing the summary.
9. Initials skip words that do not start with a letter ("Bùi Đức Tuấn 222" → BT).
10. Row clicks set the right panel through `person_week()` only (debounced 120 ms), not a whole `load()`.
11. Drawer focus lands on the drawer itself, not its first option (a ring on the first option read as a second choice).
12. `StepSoon` lost its step-3 copy (step 3 is live).

## 3. Facts that proved wrong or stale
- D / J.1: with `pb_attendance_policy` installed, `pb_shift_patterns` is **not** green: 15 errors (AccessError on
  `hr.employee.pb_attendance_policy_id` from `policy.py:242` create hook) for an attendance manager without HR rights. The facts
  note the field is HR-only (K24) but not that the roster create hook trips on it. Live on Sudima today for such users.
- J.1 test counts: `pb_attendance_policy` reports 10 in `odoo.tests.stats`; the standalone engine suite (11) must be run from
  its `tests/` folder (`python -m unittest test_engine_standalone`); `-I` or a dotted path from the repo root fails to import.
- H: `useExternalListener(window, 'keydown')` never sees Escape inside the web client (the hotkey layer stops it) — capture phase needed (WS10).

## 4. Self-review against §3 (design bar)
| Bullet | Score /5 | Note |
|---|---|---|
| Hero: tick a team, one button, one honest sentence, Apply, bar fills, Undo in reach | 5 | server-computed sentence before Apply; bar animates to full; rail and panel refresh; toast Undo |
| Zero dead-ends | 4 | no weeks → "Build a working week first" + Go; no match → Clear; read-only explains itself; nobody → plain card (no link to People: no safe action id in this module) |
| Plain language | 5 | working week / one-off shift / late rule / team; gate grep for pattern/member/category/policy/draft is clean |
| Motion with purpose, reduced motion | 4 | bulk bar rises, drawer slides, bars and mini strips animate; all off under reduced motion |
| Keyboard + bulk ergonomics | 5 | click / Shift-click / Space / Shift+arrows / header box / Cmd+A / Esc / "Tick all of team" / "Tick all N in this list"; drawer traps Tab, Esc closes, focus returns to the bar |
| One solid primary per bar | 5 | bulk bar: white "Give a working week" only; drawer footer: Apply only |
| Lucide only, no gradients, white-label | 5 | static gates |

**Weakest point:** the table at 1100 px and below. With a fixed five-column layout in a ~750 px centre column the working-week
name is cut ("Factory we…", "Day and n…") and the rotation's "· week 2" disappears into the ellipsis; the mini strip carries the
meaning but not the name. A second line for the week name, or folding the From column into the chip, would fix it. Second:
the toast is the standard top-right notification, far from where the eye is (the bulk bar at the bottom).

## 5. New gotchas → ledger WS9–WS15 (appended).

## 6. Commits (branch `wfsetup`)
- `88c430d10` feat(pb_workforce_setup): step 3 Who works what — people table, bulk working week / one-off shift / late rule with undo (WFSETUP P2)
- this report + ledger WS9–WS15 (docs commit on top)

Test database `wfs2_base` and its filestore were dropped after the run. One CSS-only touch made after the last walk restart
(focus ring + panel edge on the same row) was not re-screenshotted.
