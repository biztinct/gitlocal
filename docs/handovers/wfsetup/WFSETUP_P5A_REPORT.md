# WFSETUP P5a — report (takeover of the old doors, menu trim, vi/id wording, lessons check, final pass)

Built 2026-11-25 in the worktree `gitlocal-worktrees/wfsetup`, branch `wfsetup`. Not pushed, not deployed.
Engineering document: real technical names on purpose. Screen strings and both translations contain no vendor name
(static gates S1 + test 4, and the PO checker).

## 1. Result summary

| What | Result |
|---|---|
| Numbered tests 1, 2, 4, 5 (`tests/test_p5a.py` `TestP5aStatic`) | **4 / 4 pass** |
| Test 3 — suites (see §1.1) | baseline **115 tests, 0 failed, 1 error** (snapshot-path artefact, WS36) → final **124 tests, 0 failed, 0 errors** (`pb_workforce_setup` 98, `pb_workforce_workspace` 11, `pb_attendance_policy` 10, `pb_shift_patterns` 29) |
| Test 6 — learning module's own checks (`pb_learn` `TestAnchorRegistry` + `TestMission`, 34 tests) | 33 pass; `test_05_no_stray_anchors` fails on anchors in six modules this programme never touched (WS38) — not caused here |
| Carry-over (a) — plan once (`TestP5aPlan`, 5 tests incl. N = 1 / 4 / 12 sums) | **5 / 5 pass** (after fixing the test's own write-date assumption, WS37) |
| Browser walk B1–B10 (manager, officer, administrator; English, Vietnamese, Indonesian) | **10 / 10 pass**, after six fixes found by the walk (§2 items 9–14) |
| Console | clean on all three logins, except the known `biz_debrand` manifest-icon warning; one transient 500 on the officer tab while the local server was being restarted, not reproducible afterwards |

Commands (private conf `p5.conf` in the scratch area; addons path = official addons + THIS worktree; DB `wfs5_base` =
copy of `upd_p6_t_tpl` + one `-u all`, ledger WS3; second DB `wfs5_ws` for B10, same recipe + `-i pb_workforce_workspace` only):
- baseline: `git archive HEAD pb_workforce_setup pb_workforce_workspace` snapshot first in the addons path,
  `-i pb_workforce_setup --test-tags /pb_workforce_setup,/pb_workforce_workspace,/pb_attendance_policy,/pb_shift_patterns`
- after (1st): worktree code, `-u pb_workforce_setup,pb_workforce_workspace,pb_attendance_policy,pb_shift_patterns,pb_learn`
  with the same tags + `/pb_learn:TestAnchorRegistry,/pb_learn:TestMission`
- final: same as after without `pb_learn`, on the finished code (the walk fixes landed after the first after-run).

### 1.1 Test 3 in detail
- Baseline (P4 code): `pb_attendance_policy 10, pb_shift_patterns 29, pb_workforce_setup 85, pb_workforce_workspace 11`
  → `0 failed, 1 error(s) of 115`. The error: `TestSetupStatic.test_s2_every_icon_exists` reads
  `../pb_import_kit/…/import_icons.js` next to the snapshot (WS36) — the snapshot layout, not the code.
- After (1st run, P5a code before the walk fixes): `pb_attendance_policy 10, pb_learn 34, pb_shift_patterns 29,
  pb_workforce_setup 98, pb_workforce_workspace 11` → `2 failed of 154`: `pb_learn test_05_no_stray_anchors` (WS38) and
  `TestP5aPlan.test_02_fingerprint…` (the test assumed `write_date` moves inside one transaction — WS37; test fixed).
- Final (finished code): `pb_attendance_policy 10, pb_shift_patterns 29, pb_workforce_setup 98, pb_workforce_workspace 11`
  → **`0 failed, 0 error(s) of 124 tests`**. The pre-existing failures of other suites listed in the P4 report
  (`pb_clock` HTTPS, `pb_timeoff` date-dependent, `pb_ess_workforce` QF3) were not re-run: P5a touches none of them.

### Numbered tests
| # | Case | Result |
|---|---|---|
| 1 | `takeover.js` re-registers Settings category `workforce_workspace` (sequence 39, `force`) with exactly one card, kind `tag` → `pb_workforce_setup_studio`; removes `attendance_calculation`; re-registers the old action tag and the `setup` lens; every Settings redirect names one of the seven real steps | pass |
| 2 | `workspace.js` `TRIMMED_GROUPS` = Overview, Roster, Timesheets, More; Timesheets = time, overtime, close; `SETUP_ONLY` = exactly the nine removed keys; none of them listed; the "More" catch-all excludes `SETUP_ONLY` + `setup`; the trim switches on only through `registry.category('actions').contains('pb_workforce_setup_studio')` | pass |
| 3 | suites, §1.1 | pass (pre-existing / artefact items named) |
| 4 | `.pot` (766 msgids) and both `.po` parse with `PoFileReader`; every msgid has a vi and an id msgstr; no vendor word in any msgstr; placeholders identical; every entry starts with `#. module: pb_workforce_setup`, has an occurrence line, and code entries carry `#. odoo-python` / `#. odoo-javascript` | pass |
| 5 | no `_t(…) +` / `+ _t(` in JS, no `_("…") +` in Python, no value glued between two words in one XML text run | pass (exceptions below) |
| 6 | learning checks, §1 | 33 / 34, the one failure pre-existing |
| (a) 1 | 12-week plan split per week sums to the direct N-week plan for N = 1, 4, 12 — on a roster with engine drafts, drafts no longer wanted (removed), a published row, a hand-made one-off (`by_hand`), a company day off (`holiday`); every number > 0 somewhere; both samples equal the direct check's | pass |
| (a) 2 | the fingerprint is stable on reads and moves on: a new member, a shift edit, a removed day of a working week, a new day off, a new roster row; another company's change leaves it alone | pass |
| (a) 3 | officer: `live_plan` refused, no key | pass |
| extra | default person is never an administrator's record; an archived chosen person falls back | pass |
| extra | the "…" menu flag and `set_workforce_menu`: administrators only, this company only | pass |

Test 5 exceptions (deliberate, listed in the test's docstring): step 4's rule sentences hold number boxes inside the
sentence (a form; each piece is its own msgid and both translators placed them to read naturally), and the right
panel's slider labels are label + value pairs ("Clocks in" / "12 min late").

### Browser walk (local server port 8195, host `wfs5.localhost`, `--max-cron-threads=0`; "Walk Furniture Co": 120 people, 3 shifts, 3 working weeks, 5 without a week, 2 PC clocks, a few drafts from today, grouped menu ON; "Empty Start Co": 8 people and nothing else. Logins: manager (attendance manager + HR user), officer, administrator)

| # | Result | Notes |
|---|---|---|
| B1 | pass | Settings › HR › "Workforce setup": one card "Set up Workforce" → studio opens on step 3 (first step not green), chip "Back to Settings" returns to Settings |
| B2 | pass | Workforce tabs: Overview (Factory overview, Today) · Roster (Roster board, Review roster — drafts exist) · Timesheets (Attendance & hours, Overtime approvals, Close & send to payroll) · More (Approvals, Field for this user) · "Workforce setup". No removed tab in the bar or in More. Officer: same four tabs |
| B3 | pass | overview "People" → step 3; "Review setup" → studio (landing step); "Check latest contact" → step 6; "Workforce setup" button → studio; Schedule "Templates" → step 1; OT desk rate card → step 4; each back chip returns to the same Workforce tab/sub-tab. A deep link to a removed lens (⌘K "Patterns") opens it with no tab lit and no sub-row |
| B4 | pass | Settings › HR has no "Attendance calculation"; Settings › Connect › Attendance → step 6 with "Back to Settings"; step 4 foot link "Advanced rules screen" opens the policies list with a way back |
| B5 | pass | administrator: "…" → Grouped tabs / Classic menu, focus on the checked item, Esc closes and returns focus, switch writes the company flag with a toast and no page reload; classic menu verified (old rail), switched back. Manager and officer: no "…" |
| B6 | pass | Vietnamese: all seven steps screenshotted; three drawers; toasts ("Đã thêm 12 ngày nghỉ lễ.", late-rule apply + "Hoàn tác"); refusal "Ca này đang được dùng trong 1 tuần làm việc…". A scripted scan of every text node and aria-label/title on each step found only customer data names (Factory day, Night line…) |
| B7 | pass | Indonesian: same; toast "Sel 8 Des sekarang menjadi hari libur perusahaan." + "Urungkan" → "…kembali menjadi hari kerja."; refusal "Shift ini dipakai di 1 minggu kerja…" |
| B8 | pass | Empty Start Co: lands on step 1 "No shifts yet" → Morning starter → Save → step 2 New working week + "Fill Mon to Fri" (autosaved) → step 3 tick all + give the week ("8 people now work …") → step 4 Confirm ("Rules confirmed for 8 people.") → step 5 "Add them all" (12) + Confirm → step 6 "Clocks are fine. Confirm" with no clock → step 7 all six green, "Publish 4 weeks" (144) → "Workforce is live." 7 of 7 — never left the studio |
| B9 | pass | reopening the studio with no step on the finished company lands on step 7, all seven green, banner "Roster published up to Sun 20 Dec 2026." |
| B10 | pass | `wfs5_ws` (workspace module only, the NEW workspace code): eight old tabs + "Guided setup", old setup screen with the adoption card and six steps, Settings card opens the old screen; console clean |

Carry-over checks in the walk: step 7 shows the step at once with the skeleton "Working out the roster for 120
people…" (≈5 s for 120 people × 12 weeks), then every −/+ press changes weeks, window dates, totals and the label in
~30 ms with no server call; returning to step 7 in the same visit reuses the plan (154 ms to the numbers). Phone
(400 px emulated): months one per row, day buttons 36 × 36 px, no page-level horizontal scroll.

## 2. Deviations from the handover (and why)
1. **Settings redirects work always, not only in the grouped menu.** The "Attendance calculation" category is gone
   whenever the studio is installed, so the remaining redirect (Settings › Connect › Attendance → step 6) must not
   depend on the menu arrangement. The daily-screen reroutes (Schedule Templates, OT rate cards) stay grouped-menu only,
   because in the classic menu they never landed on a removed tab and the daily screens must not change.
2. **The old action tag renders the studio itself** (re-registered with `force`) instead of a redirect stub;
   `pb_workspace_section` maps to a step (`SECTION_STEP`). The `setup` lens is a thin hand-over that replaces the
   Workforce action in the breadcrumbs (WS33), and the button path is intercepted in `PbMission.setLens`.
3. **Step context**: the studio reads `pb_wfs_step` (handover), `pb_setup_step` (P4) and `pb_workspace_section`.
4. **"Review roster" visibility** comes from a new `review_rows` in `pb.workforce.workspace.preferences()` (drafts
   from today on, this company; 0 for non-officers) — one count query per Workforce visit.
5. **Company switch through a facade method** `set_workforce_menu(grouped)`: a client `orm.write` on `res.company`
   reloads the whole web client (`reload_company_service`). The method checks administrator rights and writes the same
   field as the caller, so the field's own admin guard still applies.
6. **Overview "Setup library"** (shortcut buttons per catalogue) is kept; every button now opens the matching studio
   step (rosters stays the Review roster lens).
7. **Step 7 plan**: new `live_plan()` (12 weeks, per-week numbers incl. a first-seen people count, two samples);
   `live_check(weeks, with_plan=False)` now also returns `all_slices`, `headcount`, `missing`, `plan_key`.
   `live_check(n, True)` (direct plan) stays for tests and callers. `go_live_start` still runs the engine itself.
8. **Default person**: the existing P2 rule (never the default admin) widened to every Settings administrator; the
   "else anyone" fallback dropped; an archived/moved chosen person falls back instead of erroring.
9–14. Fixed during the walk: (9) step 7 waited for the whole 12-week plan inside `willStart`, so the previous step
   stayed on screen and the skeleton never showed — the plan is now fetched without blocking; (10) the "…" menu's
   focus ran before it was drawn (now `useEffect`); (11) Esc on a step-3 drawer returned focus to the first bulk button,
   not the one that opened it; (12) "150 %.Work on a rest day" — the template's line break between clauses is dropped
   when compiled (CSS word space); (13) one-letter weekday msgids could not be translated (WS34) — locale weekday
   names now; (14) the long Vietnamese / Indonesian phone-clock title was cut off ("Chấm công bằng điệ…") — wraps now.
15. **Holiday suggestion names** are translated through a fixed name table (`_suggestion_name`) — our 2027 list and the
   `pb_timeoff` reference rows for VN/ID; an unknown name shows as it is.
16. Removed: dead CSS from P1–P2 (`pbws-soon*`, `pbws-pv-days/dn/dt/note`), the never-shown "Coming next" status, the
   one-letter weekday msgids. No console logs were found.

## 3. Rerouted callers (`pbWorkforce.go(` / `pb_workspace_section` / setup doors)
| Caller (file) | Before | Now |
|---|---|---|
| Settings › HR card `workforce_workspace` (`workspace.js`) | old screen by xmlid, breadcrumb back | studio by tag, "Back to Settings" chip |
| Settings xmlid cards `action_policy`, `action_employee_policy`, `action_shift_planning_no_filter`, `action_resource_calendar_form`, `action_clock_connectors` (`PbSettingsHub.openCard` patch) | workspace section (grouped only) or native list | studio step rules / people / live / holidays / clocks, always (only the Connect › Attendance card still exists) |
| Settings › HR "Attendance calculation" (`pb_attendance_policy/settings.js`) | five native doors | category removed from the registry (doors are steps; advanced list from step 4) |
| Action tag `pb_workforce_setup` (`action_workspace_setup`, old bookmarks) | old `WorkforcePanel` | the studio, `pb_workspace_section` → step |
| Mission lens `setup` (deep link `pb_shell_lens: "setup"`) | old panel inside Workforce | hand-over to the studio, replacing the Workforce action |
| "Guided setup" button → now "Workforce setup" (`workspace.xml`) | `setup` lens | studio (landing step) |
| Overview "People" per workplace (`WorkforcePanel.go('people')`) | people lens | step 3 |
| Overview "Review setup" (`go('setup')`) | setup lens | studio (landing step) |
| Overview stat "Check latest contact" (`go('connectors')`) | connectors lens | step 6 |
| Overview "Setup library" buttons (`go(<catalogue>)`) | catalogue lenses | matching step (shifts 1, policies/rates/ceilings 4, people 3, calendars 5, connectors 6); rosters unchanged |
| Overview "Review roster" / "Review before publishing", Patterns "Review roster drafts" (`go('rosters')`) | rosters lens | unchanged (lens kept, listed when drafts exist) |
| Schedule "Templates" + template rows (`PbSchedule.openTemplates/openTemplate`, grouped menu) | shifts lens with the record | step 1 |
| OT desk rate cards (`PbOtDesk.openConfig`, grouped menu) | rates lens with the record | step 4 |
| ⌘K "Patterns", dashboard "Holidays" tile, time-off palette "Holidays", studio step 2 rotation editor (`pb_shell_lens`) | patterns / holidays lens | unchanged: the lens still opens; no tab lit, no sub-row |

## 4. Lessons, tours, help (§2.4)
Searched `pb_learn` (content JSON, anchors registry, engine screens, models), `pb_learning_hub`, `web_tour` registries,
the hub palettes and `docs/` (non-handover) for "Set up Workforce", "Guided setup", "Shift library", "Recurring
patterns", "Rules & calendars", "Connections", "Attendance policies", `pb_workforce_setup`, `action_workspace_setup`,
`pb_workspace_section`, `pbww-`.
- **Found, unrelated**: every "Guided setup" in lessons / glossary / `docs/tutorial_poc` is the PAYROLL guided setup
  (Settings › Guided setup › New configuration, `pb_blueprint`) — untouched. `pb_clock`'s "Guided setup / invite IT"
  button is the connector form — untouched. No Payobook tour (`web_tour`) covers Workforce.
- **Workforce lessons** use places `pb_workforce:today|time|time/clocks|timeoff|overtime|close` and anchors in
  `pb_today`, `pb_time_hub`, `pb_clock`, `pb_timeoff`, `pb_hr_workforce` (OT desk), `pb_mission` close lens and dock —
  none of them is a removed tab; all remain reachable in both menus. `wf-tabs` ("Workforce's lens rail") is the classic
  rail, already hidden in the grouped menu before this phase. **Nothing changed**; confirmed untouched.
- No learning generator was run, so no `.po` restore was needed.
- `pb_learn` checks: 33 / 34; the failure is pre-existing (WS38).

## 5. Translations
- `pb_workforce_setup/i18n/pb_workforce_setup.pot` (766 msgids: 509 screen JS/XML, 255 Python, model terms),
  `vi_VN.po`, `id_ID.po` — complete. Written by two translation passes against a fixed glossary (Vietnamese:
  ca làm việc, tuần làm việc, tăng ca, ngày nghỉ lễ, máy chấm công, công bố…; Indonesian: shift, minggu kerja, lembur,
  hari libur nasional, mesin absensi, terbitkan…), then checked with the product's own PO reader (coverage,
  placeholders, vendor word, the three loading markers) and on screen.
- "Workforce" = "Lực lượng lao động" (as the existing Vietnamese menu) / "Tenaga Kerja" (no Indonesian menu
  translation exists yet, so the menu itself still reads "Workforce" for an Indonesian user).
- Still English for a vi/id user, outside this module: the grouped Workforce tab names and the "Workforce setup"
  button (`pb_workforce_workspace` has no translations at all, pre-existing); numbers use the browser's digit grouping
  (2,402 rather than 2.402).

## 6. Modules and versions changed in the whole programme (for the deploy handover)
| Module | Version before → after | Install or upgrade | Stored fields / tables added |
|---|---|---|---|
| `pb_workforce_setup` | new → **19.0.1.4.0** | **install** (sudima + payobook first, R2) | `hr.shift.planning.pb_day_kind_manual` (Boolean); `res.company.pb_wfs_holidays_year` (Integer), `pb_wfs_clocks_ok` (Boolean), `pb_wfs_live_on` (Date), `pb_wfs_live_to` (Date); `pb.attendance.policy.pb_pending_rates` (Json); transient tables `pb_workforce_setup_undo`, `pb_workforce_setup_run` |
| `pb_workforce_workspace` | 19.0.1.0.0 → **19.0.1.1.0** | upgrade where installed | none (one new read in `preferences()`) |
| `pb_hr_workforce` | 19.0.4.24.1 → **19.0.4.25.0** (P3: overtime requests use the most specific rate row) | upgrade everywhere installed | none |
| `pb_attendance_policy` | unchanged code | **install where missing** (hard dependency of `pb_workforce_setup`, owner ruling R4) | its own tables (new on those sites) |
| other dependencies of `pb_workforce_setup` (`pb_shift_patterns`, `pb_timeoff`, `pb_wf_kit`, `pb_import_kit`, `pb_hub`, `pb_mission`, `pb_clock`, `pb_settings`, `pb_form_studio`) | unchanged | installed by the dependency chain where missing (check per DB; the local template lacked `pb_shift_patterns`, `pb_workforce_workspace`, `pb_form_studio` — WS3) | — |

Deploy notes: JS/SCSS/XML changed in both custom modules → purge `/web/assets/%` per DB. Translations are code
translations read from the `.po` files (no DB load step). Nothing is created on install; the menu trim and the Settings
takeover switch on by the studio's presence only.

## 7. Self-review against §3 (design bar)
| Bullet | Score /5 | Note |
|---|---|---|
| Zero dead-ends | 5 | every old door lands on a step with a way back; the advanced rules list is one link away; an empty company reaches "Workforce is live." without leaving the studio |
| Plain language, vi/id | 4 | complete, glossary-consistent; grouped tab names still English (other module) |
| Motion with purpose | 4 | calm skeleton for the plan, instant week stepping; the menu pops; reduced motion respected |
| Keyboard | 5 | drawers return focus to their own trigger, the menu takes and returns focus, Esc everywhere |
| One solid primary per bar | 5 | unchanged |
| Lucide only, white-label | 5 | static gates + PO checker |

**Weakest remaining point, honestly:** `go_live_start` still runs the engine over the whole window at publish time
(28.7 s for 700 people × 4 weeks in P4) — the check is now instant after the first ~12 s, but pressing Publish on a
700-person site still sits on "Making the roster…" for half a minute before the weeks start ticking. Second: the
Workforce tab names around the studio are English for Vietnamese and Indonesian users.

## 8. New gotchas → ledger WS32–WS38 (appended)

## 9. Commits (branch `wfsetup`)
- `abcc506a3` feat(pb_workforce_workspace): daily-only grouped menu when the setup screen is installed (WFSETUP P5a)
- `770c20b14` feat(pb_workforce_setup): take over the old Workforce setup doors, vi/id wording, step 7 plan worked out once (WFSETUP P5a)
- this report + ledger WS32–WS38 (docs commit on top)

Test databases `wfs5_base` and `wfs5_ws` and their filestores dropped after the run; the walk logins existed only there.

---

# P5c — polish pass (publish speed, translated Workforce tab bar, numbers in the user's language)

Built 2026-11-25 in the same worktree / branch. Not pushed, not deployed. One local DB `wfs5c` (copy of
`upd_p6_t_tpl` + one `-u all`, WS3), dropped with its filestore afterwards.

## P5c.1 Fix 1 — publish no longer plans the whole window first

**Chosen: the split, not the reuse.** Reusing the check's plan was not enough: `Eng.apply` re-plans anyway, the
12-week check plan is not stored server-side, and even with a stored plan the start would still create all
16,100 rows before the first week could tick (~25 of the 35 s). So the engine work moved into the week calls:

- `go_live_start` now only checks, re-marks the rows already there (`remark_days`), and opens the run
  (`per_week = True`, `made_to = yesterday`). 0.2 s at 700 people.
- New `go_live_make(run_id, index, day=None)`: makes the drafts up to `day` (whole week without it). The screen
  calls it a few days at a time — about 1,000 shifts a call (`round(1000 / headcount)` days, 1..7): one day at
  700 people, a whole week at 120. The bar counts a made day as 1 and a published week as 2.
- `go_live_week` first makes whatever is left of its week (`_make_until`), then publishes as before. So the
  P4 protocol (start → week → … → finish), the P4 tests 12–15 and a resumed run all still work unchanged.
- **Why it is the same roster** (proof in the `golive.py` docstring, test `test_p5c.py`): everything the engine
  decides is per person and day except the overlap test, which looks one day either side. A person on ONE working
  week is planned day after day, so splitting into consecutive day ranges keeps the order, provided the drafts the
  engine will remove on the NEXT day go first — `_live_make` takes `Eng.plan(next_day)['remove']` before applying
  (skipped when that day has no working-week draft). A person on TWO working weeks on the same day breaks the
  order (a later pattern's Sunday is judged against an earlier pattern's Monday): `_live_split_ok` detects it and
  then the start runs the old single pass (`per_week = False`). Day types do not depend on roster rows, so
  re-marking at the start + marking on create = re-marking after the engine.
- One knowing difference, in the new path's favour: a working-week shift refilled on a hand-decided day is deleted
  in the same call; in one pass it lived until the whole window was planned and could block the next day's shift
  (a "ghost"). Needs a shift that runs past midnight into the next day's shift.
- Safety unchanged: company-scoped searches, idempotent (`made_to` + `state = draft`), the make step has its own
  savepoint (a failure there is reported like a failed week and rolled back whole; Carry on makes it again), a
  failed publish keeps the week's drafts (test 15 unchanged). `go_live_make` is attendance-manager only.

**Equivalence test** (`TestP5cWeekByWeek.test_01`, fixture = 3 working weeks / 40 people / 4 weeks): drafts
already made for weeks 2–3, a company day off in week 2, a hand-edited draft, two one-off night shifts (one on a
pre-made day, one on a day the engine still fills), a hand-made rest-day shift, a shift published before, a draft
the week no longer wants, an untouched stale early-shift draft on week 2's Monday overlapping week 1's new Sunday
night, another company's draft. The P4 path (forced through `_live_split_ok = False`), the week-only protocol and
the screen's day-by-day protocol each run; the first two inside a rolled-back savepoint. Every row of both
companies from today on is compared field by field (person, day, shift, times, state, day type + by-hand flag,
working week, signature, late-rule set, acknowledgement token present) plus the finish card (published, people,
dates, made counts, summary): **identical**. Also: someone on two working weeks → one pass (`test_02`); a failing
make rolls back and carries on (`test_03`); officer refused (`test_04`); 700-people timing (`test_05`).

**Timings, 700 people × 4 weeks from a Tuesday/Wednesday = 16,100 shifts** (same machine, same DB):

| | Before (P4 code, `git archive HEAD`) | After, week-only calls | After, the screen's calls |
|---|---|---|---|
| Publish pressed → start returns | **35.5 s** | 0.2 s | **0.2 s** |
| First visible progress | **~38 s** (first week done) | ~11 s | **2.7 s** (first day made) |
| Each step | weeks 2.6 / 3.1 / 3.1 / 3.1 s | weeks 10.9–12.8 s | ~2.5 s per day (700 shifts), ~2.5–3 s per publish |
| Whole publish | ~47 s | ~48 s | ~71 s alone (77 s inside the full suite) |

The day-by-day calls cost ~0.7 s of fixed work each (the plan's per-call reads), so the whole 700-people publish
takes ~50 % longer in exchange for progress at 2.7 s instead of ~38 s. Smaller companies batch days (120 people =
one make per week), so they pay almost nothing: walk below.

## P5c.2 Fix 2 — the grouped Workforce tab bar is translated

- `pb_workforce_workspace/static/src/workspace.js`: tab names through `groupLabel(label)` (the English label stays
  the identity for comparisons and P5a test 2), sub-tab and lens names through `lensLabels()`, the page copy through
  `copy()`, the Settings card and lens registry entries as getters — every `_t` runs when shown. Sub-tabs of
  "More" (time off, approvals, field, insights) get their own names in the tab bar. Hard-coded English inside
  template expressions moved to getters (eyebrow, adoption card, stats "Not installed"/"Unavailable", week line,
  "N people / draft shifts / other roster rows" with the bold number as markup, "N records", pager, "Record",
  "Not assigned", the patterns-board button labels, weekday names through luxon, dates in the review list).
- `models/workspace.py`: section names (`_catalog_label`) and the six old setup steps through `_()`; counts with
  `formatLang`.
- `i18n/pb_workforce_workspace.pot` (148 msgids: JS, template, Python, field/model terms) + `vi_VN.po` + `id_ID.po`
  (complete; glossary as P5a: Lịch làm việc / Jadwal kerja for roster, Bảng công / Jam kerja for Timesheets…).
  Three loading markers on every entry; parse gate over all 5,662 `.po` files in the worktree: 0 bad (the known
  legacy country-module "unknown occurrence" warnings only). No "Odoo" in any msgid or msgstr (test).
- New `tests/test_static.py` (3 tests): translations load (parse, coverage, placeholders, vendor word, markers);
  no module-level `_t`, the exact `_t` import line (WS40), no `toLocaleString`; every tab has a translated name.
- Version **19.0.1.1.0 → 19.0.1.1.1**.
- Still English for a vi/id user, outside this module: a few roster field labels in the review list
  ("Suggested from punch history", "Pb Calculation Status" — other modules' field names), the "You don't have
  access to this yet" dialog, and the studio's "Kembali ke Workforce" back chip word "Workforce".

## P5c.3 Fix 3 — numbers in the user's language

- Studio JS: `fmtNum(n)` and `dec(v, digits)` in `setup_util.js` use the web client's `formatFloat`
  (`@web/core/utils/numbers`, the user's language settings). Every `toLocaleString()` is gone (step 7, rules,
  people, clocks); counts that can pass 999 in sentences (people, shifts, days, ticked, applied…) and in the
  template (no-week / no-clock-number chips, worker/manager counts) are formatted; hours (`hrs`, `hoursText`),
  percentages and read-only rule values use the user's decimal mark (8,8 jam / 7,5 h).
- Server sentences shown in the studio: `_num(n)` / `_dec(v)` on the facade (`formatLang`) replace every
  `'{:,}'.format` and the raw people/shift counts (publish label and finish card, re-mark summary, holiday
  re-mark toasts, rules confirmed, one-offs added, late rules set, "more than 5,000 shifts", band "h off").
- Years, week numbers, minutes and line numbers are left as they are on purpose.

## P5c.4 Tests

| Run | Result |
|---|---|
| `pb_workforce_setup` + `pb_workforce_workspace` full suites, final code | **0 failed, 0 errors of 101 tests** (`pb_workforce_setup` 89 incl. 5 new P5c, `pb_workforce_workspace` 12 incl. 3 new static); P4 tests 12–15 unchanged and green. In that run: case 17 start 0.36 s, weeks 11.9–13.8 s; P5c day-by-day first step 2.76 s, total 68.3 s |
| P5c tests alone (5) | 5 / 5 |
| Static tests (`TestSetupStatic` 4, `TestP5aStatic` 4, `TestWorkspaceStatic` 3) | pass |
| Before-timing run (P4 code: test 17 + test 12/13) | 2 / 2 |

## P5c.5 Browser walk (local, port 8196, host `wfs5c.localhost`, crons off; "Walk Furniture Co" and "Walk Two Co": 120 people, 3 working weeks, rules confirmed, grouped menu on; logins with attendance manager + HR officer rights)

| # | Result | Notes |
|---|---|---|
| W1 Vietnamese tab bar | pass | Tổng quan · Lịch làm việc · Bảng công · Thêm · "Thiết lập lực lượng lao động"; sub-tabs Tổng quan nhà máy / Hôm nay; Bảng lịch làm việc; Chấm công và giờ làm / Duyệt tăng ca / Chốt kỳ và gửi sang bảng lương; Phê duyệt / Hiện trường. Overview page, workplace card ("120 người · 0 ca nháp · 560 dòng lịch khác"), library, review-roster list ("560 bản ghi", "1–40 trên 560", "Tìm theo tên…") all Vietnamese |
| W2 Indonesian tab bar | pass (after fix WS40) | Ikhtisar · Jadwal kerja · Jam kerja · Lainnya · Penyiapan Tenaga Kerja; sub-tabs all Indonesian. Before the fix "More" read "Selengkapnya" (another module's word) and "Field" stayed English |
| W3 Vietnamese publish 4 weeks, fresh company, final code | pass | "2.480" shifts; bar moves at **1.8 s**, done at **10.6 s**; finish "Lịch làm việc có 2.480 ca cho 120 người…"; DB 2,480 published, 120 people, 0 duplicates |
| W4 Vietnamese publish of 4 more weeks (12-week window, day-at-a-time build) | pass | "2.720 ca mới · 5.320 ca đã công bố trước đó"; bar at 1.1 s, done 27.5 s |
| W5 Indonesian publish of 4 more weeks (8-week window, day-at-a-time build) | pass | bar at 0.66 s, done 23 s; "2.720 shift lagi diterbitkan"; preview "8,8 jam", "7,8 jam" |
| W6 First Vietnamese publish (4 weeks, before the walk fixes) | pass | "2.600", done 10.9 s |
| DB after W4–W6 | pass | 8,040 published, 0 duplicates, 0 chatter lines |
| Console | clean | no errors or warnings on all three logins |

Walk fixes: WS40 (the `_t` import spelling), the bold-count helper that called `_t(variable)` (WS39), dates in
the review list, and the per-call day batching (W4/W5 ran one day per call: ~0.6 s overhead per call at 120
people; W3 ran on the batched code).

## P5c.6 Updated module / version table (for the P5b deploy — replaces §6 above)

| Module | Version before → after | Install or upgrade | Stored fields / tables added |
|---|---|---|---|
| `pb_workforce_setup` | new → **19.0.1.4.1** | **install** (sudima + payobook first, R2) | as §6, plus `pb_workforce_setup_run.per_week` (Boolean), `made_to` (Date) on the transient run table |
| `pb_workforce_workspace` | 19.0.1.0.0 → **19.0.1.1.1** | upgrade where installed | none (new `i18n/` folder: code translations, no DB load step) |
| `pb_hr_workforce` | 19.0.4.24.1 → **19.0.4.25.0** | upgrade everywhere installed | none |
| `pb_attendance_policy` | unchanged | install where missing | its own tables |
| other dependencies | unchanged | by the dependency chain | — |

Deploy notes unchanged: purge `/web/assets/%` per DB (JS/XML changed in both modules). A user who signs in on an
English login page may land in English (the login sets the user's language): switch with the language menu.

## P5c.7 New gotchas → ledger WS39–WS42

## P5c.8 Commits (branch `wfsetup`)
- `735da7717` feat(pb_workforce_workspace): translated grouped tab bar, overview and review roster (WFSETUP P5c)
- `063855e44` feat(pb_workforce_setup): publish makes the roster day by day; numbers in the user's language (WFSETUP P5c)
  (fixes 1 and 3 share `golive.py` / `step_live.js`, so they are one commit for this module)
- this report section + ledger WS39–WS42 (docs commit on top)

Test database `wfs5c` and its filestore dropped after the run; the walk logins existed only there.

