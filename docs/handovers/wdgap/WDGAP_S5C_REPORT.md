# WDGAP S5-C — Rotating shift patterns: report

Branch `wdgap-s5c` (from `origin/19.1` @ `abc2259b6`). New module **`pb_shift_patterns` 19.0.1.0.0**.
No existing file edited (no pb_schedule, pb_mission or pb_hr_workforce file touched).

## 1. What was built (item 6 of the S5 FACTS)

| Piece | Where |
|---|---|
| **Pattern** `pb.shift.pattern`: name, company, department, "Day 1 of the cycle" (`start_date`), "Repeats every" `cycle_days` (1–56, DB check), "Work on public holidays" (default off), notes, last made on/by/up to | `models/shift_pattern.py` |
| **Slots** `pb.shift.pattern.slot`: one per cycle day (`day_index`, `template_id`; empty = off), unique per pattern+day | same |
| **Teams** `pb.shift.pattern.team`: "Team A/B/…", `offset_days` = starts this many days after Team A (0 ≤ offset < cycle, max 8 teams). A member works cycle day `((d − start_date) − offset) % cycle_days` | same |
| **Members** `pb.shift.pattern.member`: person, team, optional from/until; refuses the same person twice for overlapping days in one pattern | same |
| **"From pattern" mark**: `hr.shift.planning.pb_pattern_id` (set null on delete) + `pb_pattern_sig` (fingerprint: person, shift, day, start, end at making time). Shown on the shift form and as a repeat icon on every Schedule card (`_pb_shift_card` gains an additive `pattern` key) | `models/shift_planning.py`, `views/pattern_views.xml`, `static/src/xml/schedule_patch.xml` |
| **Engine** `pb.shift.pattern.engine`: plan → apply. Same caches and the SAME `_pb_check` worker as `copy_week_checked` (overlap, approved leave, young-worker night ban, overtime ceiling per month); block+warn skipped and reported, pending leave (info) does not stop a shift; plus **public holidays** (company closures in `resource.calendar.leaves`, no resource, time type leave, person's local day) unless the pattern works holidays; **never the past** (today counts); shifts made in the pass join the overlap cache. `apply` creates in one batch inside a savepoint, falls back to one savepoint per shift and reports any refusal | `models/pattern_engine.py` |
| **No duplicates on re-make**: the pattern's own shifts in the range are matched first — an untouched draft still wanted (same shift, same window) is kept; an untouched draft no longer wanted (cycle/team/hours changed, person left) is removed and its window taken out of the cache first; a draft changed by hand and every published/completed shift is left alone and its day not refilled | same |
| **Remove unpublished drafts**: untouched drafts from today on; edited and published kept | same `clear_drafts` |
| **Facade** `pb.shift.patterns` (filter-kit mixin): `get_board`, `get_page`, `get_pattern`, `find_people`, `save_pattern`, `archive_pattern`, `preview`, `make_drafts`, `clear_drafts` | `models/patterns_board.py` |
| **Patterns lens** on Mission Control (registered in `pb_mission_lens` by its literal name, sequence 30, gate attendance officer): headline, quiet glance (patterns / people / drafts to publish → Schedule / with nobody yet → filter), filter kit list of pattern cards with a cycle strip, first-start panel with three ready shapes (Days and nights swapping weekly, 4 on 4 off with four teams, Same every week). Drawer: basics, paint-the-cycle grid (pick a shift, press days; Fill Monday to Friday; Clear), teams with "starts N days after Team A" + Space evenly, a live "next two weeks" picture per team, people search with "also on another pattern" warning, per-person from/until, move between teams. "Make drafts" drawer: which patterns, starting week, 1–12 weeks, **Check first** (preview, writes nothing), **Make drafts**, result tiles (already there / old drafts replaced / changed by hand kept / published kept / not filled), reasons, skipped list, "Open the Schedule". Read-only for officers (server `can_edit`) | `static/src/js/patterns_board.js`, `xml/patterns_board.xml`, `scss/patterns_board.scss` |
| **⌘K rows** (5000 block, XMLID door + `requires: "pb_shift_patterns"`): "Shift patterns" (officers), "Make shifts from a pattern" (attendance managers; opens the lens with the make panel up via `pb_focus: "make"`, consumed once per action) | `static/src/js/patterns_palette.js` |
| **Schedule toolbar button "Patterns"** (attendance managers) beside Copy week, opening the lens; by `patch()` + `t-inherit` from this module | `static/src/js/schedule_patch.js`, `xml/schedule_patch.xml` |
| Standalone client action `pb_shift_patterns` (`action_pb_shift_patterns`), off-menu native list/form fallback | `views/pattern_views.xml` |
| vi_VN + id_ID: all 226 msgids. Vietnamese follows the words already on screen (Schedule = "Lịch ca", Publish = "Công khai", Templates = "mẫu", so a pattern is "lịch xoay ca", lens "Xoay ca") | `i18n/*.po` |

Nothing is published automatically — every shift is made in draft. Nothing is created on install
(no data rows, no job, no email, no menu).

## 2. Files edited outside the new module

None. The Schedule is extended by `t-inherit` (extension mode) and `patch(PbSchedule.prototype)`;
`hr.shift.planning` and `hr.shift.planning.grid` by `_inherit`; Mission Control through its registry.

## 3. Tests (local copy `wdgap_s5c_t` of `upd_p6_t_tpl`, brought to 19.1)

| # | Test | Result |
|---|---|---|
| T1 | Two teams, two-week day/night cycle (offsets 0/7), 3 weeks across a month end: 60 shifts, every one the right shift for its team, the teams never on the same shift the same day, both months filled | pass |
| T2 | Four teams "4 on, 4 off" (8-day cycle, offsets 0/2/4/6), 21 days across a month end: every day exactly one team (2 people) on days and one on nights; each person 9–12 shifts | pass |
| T3 | Approved leave → skipped + reported (person, day, reason); pending request → shift made | pass |
| T4 | Public holiday (company closure) → skipped + reported with its name; "Work on public holidays" → filled | pass |
| T5 | Make again → 0 made, 0 removed, 60 kept, same rows; wider run adds only the new week | pass |
| T6 | Draft changed by hand kept (not reverted), published kept, nothing doubled | pass |
| T7 | Cycle changed (nights → lates): 30 untouched night drafts replaced, published shift kept | pass |
| T8 | Person taken off the pattern → their 15 untouched drafts removed on the next run | pass |
| T9 | A shift the person already has (overlap) → skipped, theirs kept | pass |
| T10 | Young worker on nights → 10 skipped as `block`, never raised; days made (rule configured on this copy) | pass |
| T11 | Preview writes nothing; Make drafts then makes exactly what it said | pass |
| T12 | Overnight shift ends next morning (12 h); days before today never filled (counted as past) | pass |
| T13 | Rights: officer reads board/pattern, refused save/make/preview/archive/clear and ORM create; portal user: board "not allowed", AccessError on read; another company's pattern "no longer there" for read and make, absent from the list | pass |
| T14 | Drafts never reach My Schedule for the employee (portal); visible only once published | pass |
| T15 | Save replaces cycle/teams/people whole; shrinking the cycle drops the tail; 6 bad inputs refused; a person of another company refused | pass |
| T16 | Empty install: no cron, email template, pattern, shift, template or menu records from the module; quiet board | pass |
| T17 | Roster card carries the pattern mark | pass |
| T18 | Remove unpublished drafts: 58 untouched removed, edited + published kept | pass |
| S1–S5 | Static: lens joins via the registry with pb_mission's exact spelling and no import back; palette rows are XMLID doors with the probe; no vendor name in templates/views/security/msgstr/manifest; vi/id parse and carry the screen sentences; Schedule extended by inheritance only | pass |

Suites (same database, one at a time):

| Suite | Baseline (before the module) | After |
|---|---|---|
| pb_shift_patterns | — | 23/23 pass (29 incl. set-ups), 0 errors |
| pb_schedule (113) | 1 FAIL `TestP2Sidebar.test_the_hero_eyebrows_say_what_the_rail_says` | the same 1 FAIL, nothing else |
| pb_mission (61) | 0 | 0 |

Static gates: py_compile, `node --check` on every JS file, XML parse, white-label grep — clean.
Browser walk (Chrome, local copy, admin = attendance manager): Mission Control rail shows
"Patterns"; first-start panel; preset → drawer; people added to two teams; save; Make drafts
(Check first: 80 for 4 people, 4 weeks; made 80; re-check: 80 already there); Schedule shows the
drafts at the right local times (08:00–17:00 / 22:00–06:00) with the repeat mark and the Patterns
button; ⌘K "Make shifts from a pattern" opens the lens with the make panel up; Vietnamese
translations load (150 screen messages). Console clean.

## 4. Rails

- Drafts only; nothing published; `My Schedule` unaffected (T14).
- Every check Copy week makes, by the same worker (`_pb_check`), plus holidays; refusals reported, never raised.
- Re-making is idempotent and never overwrites a human change (fingerprint, T5–T8, T18).
- Server gates on every facade call; officers read, attendance managers write and make; company rules on all four models; another company's id reads "not there".
- No payslip, overtime, leave or attendance figure is touched. No cron, no email, no demo data.
- People/slot reads use sudo behind the gate (a bare attendance manager need not hold HR rights); every shift is searched, judged and created as the caller.

## 5. Contracts other phases may rely on

- `hr.shift.planning.pb_pattern_id` (Many2one `pb.shift.pattern`), `pb_pattern_sig`, `_pb_pattern_untouched()`.
- Schedule card payload: additive key `pattern` (pattern name or '').
- `pb.shift.pattern.engine.plan(patterns, first, last)` → dict (`creates`, `remove`, `skipped`, `counts`, `kept_*`, `off`, `past`); `apply(...)` → report; `clear_drafts(patterns)`.
- Mission lens key `patterns`; palette ids `wf_patterns`, `wf_patterns_make`; client action tag `pb_shift_patterns`.
- Skip codes: `overlap`, `leave_approved`, `young_worker_night`, `ot_ceiling` (from `_pb_check`), `holiday`, `refused`, `edited` (kept list).

## 6. Deploy notes

- Install `pb_shift_patterns` with `-i` on every database (new module; depends on `pb_schedule`, `pb_filter_kit`, `pb_import_kit`, `pb_wf_kit` — all already installed). Normal tier is enough on its own (no pay figure, no data rewrite); it adds two columns to `hr_shift_planning` (empty).
- Merge order in the step: A, B, then C; no shared file with S5-A or S5-B.
- Purge `/web/assets/%` and bump assets after install (new JS/SCSS, Schedule template extension).
- Seam check after the merge: Schedule loads in Mission Control with the Patterns button; `pb_schedule` suite = baseline (1 known sidebar failure).

## 7. Owner questions (plain words)

1. **Public holidays.** Right now, a pattern leaves public holidays empty unless its "Work on public holidays" switch is on (a 24-hour plant would switch it on). Is "empty on holidays" the right default for your customers?
2. **Overtime limit.** Like Copy week, a person already at 90% of their monthly overtime limit gets no new shifts that month and is listed in the report. Should a rota ignore that warning instead (rota shifts are normal hours, not overtime)?

## 8. Left for later

- Open shifts (a slot with nobody) — the shift model requires a person (FACTS risk); out of scope.
- More than one shift per cycle day (true split shifts) — one slot per day today.
- Making drafts on a schedule (e.g. every Monday, 4 weeks ahead) — deliberately not built (no job on install); owner choice.
- Phone width below 614 px not checked (Chrome window limit, QF2-G7); a 640 px media rule is in place.
- The filter panel shows its own "Nothing matches" note when a company has too few patterns for any filter to split them (filter-kit behaviour, same on other boards).

## 9. Gotchas → ledger rows

- **S5C-1**: A Mission Control guest lens reading its arrival (`pb_focus`) in `onMounted` sees the PREVIOUS action: the action service makes the new controller current only after mount. Retry briefly (`_arrival`, 10 × 100 ms) and consume once per action object.
- **S5C-2**: The filter kit's "of N" comes from `pbf_layout` at load; a board that starts empty and gets its first record shows "1 of 0" after `kit.refresh()`. Call `kit.load()` when the total changes.
- **S5C-3**: `WfDrawer` is a 320 px person panel; a wider surface sets `.wfdr { width }` inside its own root (the drawer renders in the lens).
- **S5C-4**: A bare attendance manager cannot run `get_schedule_data` (AccessError on `hr.employee.version_id`) — pre-existing; tests read the roster as the administrator.
- **S5C-5**: An attendance OFFICER reads only their own `hr.shift.planning` rows (record rule `workforce_rule_employee_own_shifts`) and cannot create shifts: any planner-side "preview" must be manager-gated or it plans against an empty roster.
