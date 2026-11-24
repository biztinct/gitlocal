# WFSETUP P3 — report (step 4 "Late and overtime rules", the live pay example, automatic holiday / rest-day marking)

Built 2026-11-25 in the worktree `gitlocal-worktrees/wfsetup`, branch `wfsetup`. Not pushed, not deployed.
Engineering document: real technical names on purpose. Screen strings contain no vendor name (static gate S1, now
scanning every `models/*.py`).

## 1. Result summary

| What | Result |
|---|---|
| Numbered tests 1–19 (`tests/test_rules.py`, tag `wfsetup`) | **19 / 19 pass** |
| Rate pin test (`pb_hr_workforce/tests/test_ot_config_resolution.py`, 3 tests) | **before the fix: 2 failed + 1 error (pin confirmed); after: 3 / 3 pass** |
| Case 20 baseline (P2 code, same DB) | `1 failed, 2 error(s) of 224 tests` — see §1.1 |
| Case 20 after | `1 failed, 1 error(s) of 246 tests` — the same two pre-existing ones as the baseline; nothing new |
| `pb_attendance_policy` standalone engine | 11 / 11 OK (run from its `tests/` folder) |
| `pb_workforce_setup` full suite after P3 | 58 tests, 0 failed, 0 errors (stats line 66) |
| Browser walk B1–B10 | **10 / 10 pass** after three fixes found by the walk (§2, items 9–11) |
| Console during the walk (manager + officer) | no errors, no warnings |
| Case 18 (3,000 rows) | day-type marking **0.14 s, 15 queries — the same 15 queries for 300 rows**; whole create of 3,000 roster rows **2.3 s, 66 queries** |

Commands (private conf in the scratch area; addons path = this worktree; DB `wfs3_base` = copy of `upd_p6_t_tpl` + one `-u all`):
- baseline: `-i pb_workforce_setup -u pb_hr_workforce,pb_attendance_policy,pb_shift_patterns,pb_schedule,pb_workforce_workspace --test-enable --test-tags /pb_attendance_policy,/pb_hr_workforce,/pb_shift_patterns,/pb_schedule,/pb_workforce_workspace,/pb_workforce_setup`,
  run against a `git archive HEAD` snapshot of `pb_workforce_setup` + `pb_hr_workforce` placed FIRST in the addons path
  (so the baseline really ran the P2 code while P3 was being written);
- pin run: `-u pb_hr_workforce --test-tags /pb_hr_workforce:TestOtConfigResolution` with the test file but without the fix;
- after: the same `-u` list and tags with the worktree code.

### 1.1 Case 20 in detail
Baseline (P2 code): `pb_attendance_policy 10, pb_hr_workforce 54, pb_schedule 113, pb_shift_patterns 29,
pb_workforce_setup 45, pb_workforce_workspace 11` → **1 failed, 2 errors of 224**:
- `pb_hr_workforce` `TestWeekEntry.test_06_submit_week_and_approve` — ERROR, `null value in column "reason" of relation
  "hr_overtime_request"` (approve path through `pb_close` / `pb_young_worker` / `week_freeze`). Pre-existing, not ours.
- `pb_schedule` `TestP2Sidebar.test_the_hero_eyebrows_say_what_the_rail_says` — FAIL, looks for "Team Approvals" in
  `pb_team`'s template. Pre-existing, not ours.
- `pb_workforce_setup` `test_s2_every_icon_exists` — ERROR only because the snapshot folder had no `pb_import_kit`
  next to it (the test reads the icon registry by relative path). Artefact of the baseline method; passes in the worktree.

After (P3 code): `pb_attendance_policy 10, pb_hr_workforce 59 (stats line; the new rate test file adds 3 test methods), pb_schedule 113,
pb_shift_patterns 29, pb_workforce_setup 66, pb_workforce_workspace 11` → **1 failed, 1 error of 246**: exactly the
`test_06_submit_week_and_approve` error and the `pb_team` "Team Approvals" failure above. No new failure; the snapshot
artefact is gone.

### Numbered tests
| # | Case | Result |
|---|---|---|
| 1 | `rules()` with no rule set: defaults, `state 'new'`, writes nothing (7-table snapshot); first save creates ONE draft (tz = company calendar), lines for the shifts used in a working week; second save edits the same draft | pass |
| 2 | `[1–9: 0, 10–29: 0.5, 30+: 1]` → `[0,1) 0, [1,10) 0, [10,30) 0.5, [30,∞) 1`; round trip identical; a `to` on the last line is dropped; saving never confirms | pass |
| 3 | gap, overlap, two open lines → the gap sentence, bands unchanged; non-quarter hours and `from 0` refused | pass |
| 4 | day 07:30–16:30 break 11:30 OT 16:30 → 4.0 / 9.0; overnight 19:30–04:30 break 23:30 OT 04:30 → 4.0 / 9.0; OT 18:00 / 07:30 / 06:00 → refusal sentence, nothing saved; a shift outside every working week gets a line only when touched | pass |
| 5 | step 1 break 60 → 30 re-syncs the draft's line, the ACTIVE line keeps 1.0; a shorter shift pulls the draft's times back inside | pass |
| 6 | the company row beats the global one; saving rates waits on the draft (`hr_overtime_config` snapshot unchanged), the screen and the example show the waiting value, Confirm writes this company's row (3.0 → 3.2) and CREATES a company row where only a shared one existed; the global row and another company's row never change; a person without a nationality gets the new rate; Change → save → Discard leaves the rates in use alone | pass |
| 7 | confirm: all bands confirmed, active, every active person pointed (count returned), no group → Worker, a group kept, another company untouched, future uncalculated rows pointed (2), past row and calculated row untouched, rail `done` | pass |
| 8 | managers without lines → `["Managers have no late lines yet."]`, snapshot of 7 tables identical, still draft, nobody pointed | pass |
| 9 | Change → draft copy; read-only save refused before; edits do not touch the active one; rail `warn`; Confirm → new active, old retired, people and future rows re-pointed; Change → Discard → draft gone, active untouched, rail `done` | pass |
| 10 | two active → `advanced`, `can_edit False`, the sentence in `problems`; save / confirm / change / discard refuse with the sentence; people on different rule sets → `advanced` too | pass |
| 11 | officer: `rules()` and `pay_example()` work; save / confirm / remark / change / discard → AccessError | pass |
| 12 | `pay_example` = `engine.calculate` built by hand (facts D.3) for: on time, 12 min late worker vs manager, 45 min late, 60 min after OT start, leaving 60 min early, 10 min early, rest day, public holiday, overnight with night extra on; plus absolute anchors (8 h / 8 h / 0 h on time; 0.5 h off + 1 h OT; manager 0 h off; early not paid; rest day all OT; 5.5 h night) | pass |
| 13 | unsaved late line and unsaved OT time are used (2 h off, 1 h OT); nothing written (policy, band, shift rule, roster, attendance, rates, employee: count + max write_date + max id) | pass |
| 14 | no working week / no group / no line for the shift / unknown person / engine refusal / clock-out outside the clock window → a sentence (and a `fix` step), never an exception, never the raw engine text | pass |
| 15 | on create: public holiday → holiday, off day in the working week → rest day, normal → normal, explicit value kept + `pb_day_kind_manual True` (both `holiday` and `weekday`); no working week → the working calendar decides (Sunday rest, Monday normal); the working-week engine's rows are marked in its one batch | pass |
| 16 | a hand-set row keeps its value through `remark_days`; an automatic row flips to holiday when a holiday is added; second run changes nothing and says so | pass |
| 17 | `remark_days` skips rows with a calculation status and rows with generated attendance | pass |
| 18 | 3,000-row batch: marking 0.14 s / 15 queries (300 rows: 15); create 2.3 s / 66 queries; holiday and Saturday rows marked right | pass |
| 19 | new person with one active rule set → pointed + Worker (a given group kept); other company / none / two active → untouched | pass |

### Browser walk (local server, port 8193, host `wfs3.localhost`, `--max-cron-threads=0`, seeded company "Walk Furniture Co": 120 people in 7 teams, 3 shifts, 3 working weeks incl. a 2-week rotation, 1,198 draft shifts over 2 weeks, one public holiday)
Keys typed with the Chrome tools' real key presses (`type_text`, `press_key`) where it matters (numbers, Tab, arrows,
Home/End on the slider); clicks on real elements with `evaluate_script`; screenshots at each step.

| # | Result | Notes |
|---|---|---|
| B1 | pass | line 1 "up to" 9 → 14 typed: line 2 starts at 15, "Saving…" → "Saved", bands `[1,15) 0, [15,30) 0.5` in the DB; the box for a 12-minute-late worker changed from "0.5 h comes off" to "nothing comes off", paid normal 7.3 h → 7.8 h |
| B2 | pass | Managers (8) show their lines; Add a line inserts "30–44" before "45 or more" and focuses its hours; Remove line 1 lets the next line take over its start; saved |
| B3 | pass | Factory day overtime 16:30 → 16:00: overtime 1 h → 1.5 h, normal 7.8 h → 7.3 h |
| B4 | pass | picker "CNC" → a rotation person on nights ("Day and night rotation · week 2", 19:30); night switch on → "6.5 h of it is night work, with 30 % extra" + a night row |
| B5 | pass | Rest day: "every paid hour counts at 200 %", total "Paid at 200 % (rest day) 8.8 h"; Public holiday at 300 %; back to Normal day |
| B6 | pass | Home / End / arrows on the clock-in slider: the box was never emptied (mutation observer: 0 empty states), same DOM node; "15 min early (not counted)" and "Coming in 15 min early is not paid"; 49 slider moves in 0.5 s ended on the answer for the LAST position |
| B7 | pass | a gap sent straight to the server → "The late lines must follow on from each other with no gap."; on screen the lines cannot leave a gap, so the deliberate fault was "managers with no lines": Confirm → red box "These rules cannot be confirmed yet · Managers have no late lines yet."; added a line, typed 0.5, Confirm → toast "Rules confirmed for 120 people.", rail green "Rules confirmed", progress 2 → 3 of 7, banner "These rules are in use." DB: 1 active, 120 people pointed, 0 without a group, 1,198 future shifts carry the rules, all lines confirmed |
| B8 | pass | Change the rules → banner + rail "Changes not confirmed yet" + bar button "Confirm the new version"; typed overtime 160 → note "The new rates are used once you confirm…", the live rate row stayed 1.75; Discard → "The new version is gone…", rate still 1.75; Change → 160 → Confirm → still green, rate row 1.6 |
| B9 | pass | a holiday added through the holidays screen's own method on a day with shifts; "Re-check holiday and rest-day shifts" → toast "Checked 1,198 shifts: 112 now public holiday."; DB: 112 rows `holiday`, not manual |
| B10 | pass | officer: read-only line, no inputs, no Change / Re-check, switch disabled, example works; widths 1440 / 1100 / 800 (window) and 400 (emulated viewport, WS6): no page-level horizontal scroll, nothing outside the root (scripted check); Tab walks from → to → hours, ArrowUp 0 → 0.25 and saves; console clean for both users |

Carry-over fixes from P2, walked too:
- (a) step 3 at 1100 px: every working-week name is whole (scripted: none clipped in the first 40 rows), the rotation week is its own chip "week 1" next to the strip; a container query moves the name under the strip when the cell is narrow.
- (b) the studio toast: dark pill centred over the working area, `role="status"` region, Undo, 8 s; at 1100 px its bottom sits 158 px from the window bottom, just above where the bulk bar's top was (142 px); the web client's top-right notification is no longer used by steps 1–4. Undo from the pill restored the two people's late rule.

### Visual differences from the prototype at 1440 that remain
1. Overtime is one line per shift with clock times (R5), not "After 8 paid hours in a day…"; the approval line is a fixed sentence with a tick icon (R6), not a switch.
2. The panel has a Normal day / Rest day / Public holiday choice above the sliders (handover §2.4) and a night row in the box when night work is on.
3. Banners above the card for "in use", "new version" and "more than one set of rules"; a people line under the card; the day-type hint with "Re-check holiday and rest-day shifts" under it. None are in the prototype.
4. Every late line has a remove button, the last one included (managers can be emptied — that is how B7's refusal is reached on screen).
5. The in-sentence boxes are 28 px tall (prototype ~42 px: native input padding); time boxes are 132 px wide to fit "11:30 AM" in 12-hour browser locales.
6. Display font falls back to Inter (as P1/P2). Example sentence: "on Monday (Factory day)" rather than "on Monday's factory day" (translatable word order).
7. The prototype's own maths differs (it shows 0.8 h overtime and 8 h paid for the same inputs); the build shows the real engine's 1 h and 7.3 h — by design.

## 2. Deviations from the handover (and why)
1. **Rates wait for Confirm** (new field `pb.attendance.policy.pb_pending_rates`, Json, `copy=False`, added from our module).
   Handover §2.2 said "On save: … write it". Found in B8: `hr.overtime.config` is read by every overtime request at once, so a
   save during "editing a new version" changed pay before Confirm and Discard could not undo it. Now a save stores the
   changed rates on the draft; Confirm applies them (inside the same savepoint, before activation); Discard drops them.
2. **A created rate row has NO country** (handover: "country = company country"). The runtime picks rows by the PERSON's
   nationality (`hr.employee.country_id`), so a company + Vietnam row is invisible to people with no nationality. Under the
   new ranking a company row without a country beats every shared row for everyone in the company. Where a company row is
   already in use for the company's country, it is written instead. See §4.
3. **The pay example applies the clock window** (`capture_before/after`) before calling the engine, as `_policy_calculate`
   does. Facts D.3 steps 1–7 leave it out; without it the example paid a clock-out 3 h after the shift that the real job
   ignores (seen in B4/B6). Outside the window → a sentence with a fix.
4. `pay_example` uses the rule set being edited (the managed record or the screen's values), not the employee's own
   `pb_attendance_policy_id` (facts D.3 step 1), except in the `advanced` state. Otherwise the example would show the old
   rules while a new version is edited.
5. A stored shift line is required for the example only when no screen values are sent (case 14); the screen always sends
   its values (with default lines for shifts that have none yet), so the hero works before the first save.
6. Confirm on a company with no rule set yet creates the draft from the defaults and confirms it in one go.
7. `remark_days` is not refused in the `advanced` state (it does not depend on the rule set).
8. `_single_policy` (P2 late-rule linking) now prefers the one ACTIVE rule set, so a new version being edited beside it no
   longer stops new people being linked. P2 case 14 still passes.
9. The right panel's default person prefers someone who has a late rule (the walk opened on "has no late rule yet").
10. Half-typed numbers (walk bug: typing "0.5" gave "50"): the box is marked, nothing is saved and the example keeps its
    last answer until the box holds a number again (WS18).
11. In-sentence inputs needed `display: inline-block` against a global rule in the backend bundle (WS17).
12. The right panel no longer lists the days under the strip (the strip keeps the times; the example takes the space).
13. Payload extras: `can_change`, `policy_id`, `rates_pending`, `approval`, per-shift `color`, `overnight`, `stored`,
    `problem`, people `no_group`; example extras `name`, `first_name`, `shift_start/end`, `early_minutes`, `break_hours`,
    `night_on`, `night_percent`, `overtime_from`, `fix`.
14. Day type is worked out on create only; moving an automatic row to another day by drag keeps its old type until the next
    re-check (`remark_days`). Not in scope; noted for P4/P5.

## 3. Facts that proved wrong, stale or incomplete
- **E.1 rate resolution — the suspicion is real.** With one global row (2.5) and the company's own Vietnam row (3.0), a
  Vietnamese person's holiday overtime request picked the global 2.5 (pin test failed before the fix). Live seeds have
  `company_id` = the default company, so on every database the "Default" row (no country) beats the "Vietnam" row for the
  same company: Vietnam weekday 1.5 vs 1.5 (same), weekend 2.0 vs 2.0 (same), **holiday 3.0 vs 2.5 (lower pay)**, night
  1.3 vs none.
- E.1: the runtime keys on the person's NATIONALITY (`hr.employee.country_id`, HR-only), not the company's country.
- F: `resource.calendar.leaves.company_id` is computed from `calendar_id` (none → the acting user's company), so a holiday
  without a calendar lands on the wrong company (WS16). The create-then-write trick of `_create_row` is needed for tests too.
- D.3: the chain leaves out the clock window, which the real job applies first (WS21).
- J.1 counts on this template: `pb_hr_workforce` 54 tests, `pb_schedule` 113, `pb_attendance_policy` 10.
- The template's filestore is incomplete: one attachment read logs a FileNotFoundError during tests and one login-page
  image request errors in the walk server log. Unrelated to this work.

## 4. Rate resolution: what changed in `pb_hr_workforce` (19.0.4.24.1 → 19.0.4.25.0)
- New `hr.overtime.config._pb_pick(overtime_type, country, company)`: candidates = active rows of that type with country in
  {that country, none} and company in {that company, none}; the winner has the highest score (company match 2 + country
  match 1), ties by `sequence`, `id`. Two tiers in Python, no `order=… desc`.
- `hr.overtime.request._compute_overtime_config` now calls it; the person's nationality is read with `sudo()` (HR-only field).
- New test file `tests/test_ot_config_resolution.py` (3 tests: the pin, the full ranking incl. no-nationality, the helper).
- Manifest version bump + a changelog line in the description. No data migration: stored `overtime_config_id` on existing
  requests is only recomputed when their type or company changes.

## 5. Which guard protects `pb_policy_id` on roster rows
None for a row WITHOUT generated attendance: `hr.shift.planning.write` (policy.py) checks the `_attendance_calc` context
token only for calculated fields, and its pairing / "do not move" checks only for rows that have `pb_attendance_id`.
`confirm_rules` therefore writes `pb_policy_id` through the ORM as the caller, on rows with no attendance and no
calculation status only. The constraint `_policy_scope` still applies (same company for person, shift and rules; local
start day in the rules' time zone = `date`; 0 < length ≤ 24 h): rows that would fail it (e.g. on a shift shared by every
company) are counted as `rows_skipped` and left alone; the write is one batch in a savepoint with a per-row fallback.

## 6. Self-review against §3 (design bar)
| Bullet | Score /5 | Note |
|---|---|---|
| Hero: change a number, the dark box re-works a real person's pay before you lift your finger | 5 | real engine on every keystroke and slider move (throttled 120 ms, newest answer wins, never blank) |
| Zero dead-ends | 5 | every refusal is a sentence; example errors carry a "Go to …" button; Confirm problems listed in one red box |
| Plain language | 5 | rules / late / overtime / rest day / public holiday / night work; no field or model words on screen |
| Motion with purpose, reduced motion | 4 | banners and toast rise, switch slides; all off under reduced motion |
| Keyboard ergonomics | 5 | Tab walks the numbers in reading order, arrows step them, slider Home/End/arrows |
| One solid primary per bar | 5 | the bar's button becomes "These rules are right. Confirm" while the rules can change |
| Lucide only, no gradients, white-label | 5 | static gates |

**Weakest point, honestly:** the sentences are long and dense at 1100 px and below — each shift line wraps to two lines
and the rate sentence breaks after "public holiday", leaving a lonely "300 %." on its own line. It reads, but it is not
calm. Second: the toast is positioned once when it appears (centre of the working area at that moment); resizing the
window while it is up leaves it where it was for its 8 seconds.

## 7. What a payroll person should double-check at deploy
1. **Overtime rates on each database** after `pb_hr_workforce` 4.25.0: with the fix, the company's own country row now wins
   over the "Default" row. With the seeded rows on the default company that means, for people of Vietnamese nationality,
   **public-holiday overtime 300 % instead of 250 %** (weekday 150 % and rest day 200 % are the same in both rows; night
   130 % only ever had the Vietnam row). Any hand-made company or country rows may now win where they did not before.
   Confirm this is wanted before the upgrade on payobook / sudima.
2. Overtime requests created before the upgrade keep the rate row they were given.
3. **Confirming the rules on Sudima turns on the new calculation for all 678 people at once**, and the clock pairing guard
   (facts D.5) then stops the old way of pairing clock records for every one of them: people with no published roster
   shift on a day get no attendance from the clock that day.
4. After Confirm, check the number of future shifts that got the rules (`rows_updated`) and any `rows_skipped` (shared
   shifts or time-zone mismatches): skipped shifts are NOT calculated.
5. Sudima's existing draft rule set has an unconfirmed "1–9 min" worker line and manager lines starting at 10: the screen
   shows them as editable lines; pressing Confirm confirms them as they are.
6. Day types: after deploy press "Re-check holiday and rest-day shifts" once per company; existing roster rows were all
   "normal day". Check a known holiday and a Sunday shift afterwards.
7. Rest day = the person's working week has that day off; people without a working week fall back to their working
   calendar. A one-off shift on a day off is a rest day.

## 8. New gotchas → ledger WS16–WS23 (appended)

## 9. Commits (branch `wfsetup`)
- `2e71b08b4` fix(pb_hr_workforce): overtime requests use the most specific rate row (WFSETUP P3)
- `12ce8958a` feat(pb_workforce_setup): step 4 late and overtime rules with a live pay example and automatic holiday / rest-day marking (WFSETUP P3)
- this report + ledger WS16–WS23 (docs commit on top)

Test database `wfs3_base` and its filestore were dropped after the run; the walk's logins existed only in that database.
