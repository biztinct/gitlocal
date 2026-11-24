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
