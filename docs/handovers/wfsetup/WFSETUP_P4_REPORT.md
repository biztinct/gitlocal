# WFSETUP P4 — report (step 5 Holidays, step 6 Time clocks, step 7 Check and go live)

Built 2026-11-25 in the worktree `gitlocal-worktrees/wfsetup`, branch `wfsetup`. Not pushed, not deployed.
Engineering document: real technical names on purpose. Screen strings contain no vendor name (static gate S1, and a
grep of every new file).

## 1. Result summary

| What | Result |
|---|---|
| Numbered tests 1–17 (`tests/test_golive.py`, 17 methods: 12 and 13 share one, plus carry-over (a) as `test_19`) | **17 / 17 pass** |
| Case 18 baseline (P3 code, `wfs4_base`) | part 1 `pb_clock 127, pb_ess_workforce 156, pb_timeoff 146` → **4 failed, 11 errors of 351**; part 2 `pb_attendance_policy 10, pb_shift_patterns 29, pb_workforce_setup 66, pb_workforce_workspace 11` → **0 failed, 0 errors of 98** |
| Case 18 after (P4 code, all seven suites in one run) | `pb_attendance_policy 10, pb_clock 127, pb_ess_workforce 156, pb_shift_patterns 29, pb_timeoff 146, pb_workforce_setup 85, pb_workforce_workspace 11` → **5 failed, 11 errors of 466**: the 15 baseline failures exactly, plus `pb_clock` `TestRecheck.test_14` — caused by the walk's seeded machine in a second company on the same database (`{298: 0, 312: 1} != {312: 1}`; 298 = the walk company). With that machine moved out, `TestRecheck` passes 2 / 2. Nothing new from P4 code |
| Browser walk B1–B10 | **10 / 10 pass** after seven fixes found by the walk (§2, items 12–18) |
| Console during the walk (manager + officer) | no errors; one unrelated warning (biz_debrand manifest icon size, as in P2) |
| Case 17 (700 people × 4 weeks from a Wednesday = 16,100 rows) | alone: `live_check` 12.1 s; `go_live_start` 28.7 s; weeks **1.9 / 2.3 / 2.2 / 2.3 s** for 3,500 / 4,200 / 4,200 / 4,200 rows. Inside the full 466-test run (busier machine): 23.0 s / 42.6 s / 2.5–3.0 s per week. **59–61 queries per week call, the same for every week** (no per-row queries) |
| Walk publish (115 people, 2,402 shifts, 4 weeks) | start 4.4 s, then ~0.3 s per week; finish card at 5.9 s |

Commands (private conf in the scratch area; addons path = this worktree; DB `wfs4_base` = copy of `upd_p6_t_tpl` +
one `-u all`, ledger WS3):
- baseline part 1: `-u pb_workforce_setup,pb_timeoff,pb_clock,pb_shift_patterns,pb_ess_workforce,pb_attendance_policy,pb_workforce_workspace --test-tags /…` against a `git archive HEAD` snapshot of `pb_workforce_setup` + `pb_import_kit` placed first in the addons path. Only the three suites of modules already installed ran (the template lacks `pb_workforce_setup`'s chain) — so
- baseline part 2: `-i pb_workforce_setup --test-tags /pb_workforce_setup,/pb_shift_patterns,/pb_attendance_policy,/pb_workforce_workspace` (same snapshot);
- after: the part-1 command with the worktree code (all seven modules installed by then).

### 1.1 Case 18 in detail
Baseline failures (P3 code, unrelated to this work, all reproduced unchanged in the after run):
- `pb_clock` `TestConnectorHttp` ×5 (4 FAIL + 1 ERROR): `400 != 200 {"error": "HTTPS required"}` — the local test server is plain HTTP.
- `pb_timeoff` ×9 ERROR: `test_holidays.test_a_run_of_days_counts_as_a_run_of_days` (IndexError), six `test_leave_rules` cases
  ("This time off has already started…" / AccessError), `test_timeoff.test_03_approve_and_refuse`, `test_05_balance_math` — date dependent.
- `pb_ess_workforce` `TestWdgapQf3.test_09_cancel_an_approved_leave` ERROR.
The two known P3 failures in `pb_hr_workforce` / `pb_schedule` are not in the case-18 list and were not re-run.

### Numbered tests
| # | Case | Result |
|---|---|---|
| 1 | `holidays()` exact key set; company with a calendar (editable) and without (`has_calendar False`, `can_edit False`, add refused with "working calendar first"); only `env.company` rows (another company's day off is not listed and vice versa); rest weekdays [5,6] for the five-day week, then [6] once the Mon–Sat week has most people; **2027 pinned: 365 − 52 Sundays = 313, after the 10 VN days 304** (Sun 7 Feb is a rest day anyway) | pass |
| 2 | attendance manager with neither time-off nor HR rights: `pb.holidays.add` itself refuses (AccessError), `add_day_off` works — kind `company`, the company calendar, no resource, local day right; same day again refused; officer AccessError; a company the user may not use → AccessError, nothing written | pass |
| 3 | remove takes only that row and returns the undo payload; another company's row refused ("not on this company's calendar"); officer refused; `restore_days_off` puts the same day back with its kind | pass |
| 4 | suggestions VN 2027: 10, note mentions the lunar calendar; a "duplicate" injected on the 4th row (`_create_row` → False) → UserError "… Nothing was added.", zero rows; real call → 10 rows on the right local days, all `public`; second call → `added 0`, "All of them are already on the calendar."; 2026 from the `pb_timeoff` reference = 12 (the conflict row left out); France → `suggestions False` and `add_suggested` refuses | pass |
| 5 | a company day off on a day with a planned, uncalculated shift → toast "1 planned shift is now paid as public holiday."; hand-set row and calculated row untouched; remove → "back to its usual pay", auto row back to normal | pass |
| 6 | status todo "Check and confirm" → confirm 2027 → `pb_wfs_holidays_year 2027`, status done "10 days off in 2027"; confirming 2026 later never lowers it; officer refused | pass |
| 7 | with one fixed `now`: ok (2 h) / quiet (30 h) / waiting / attention / off / machine ok; other company's clock absent; the PC's error text (`C:\Users\clerk\…mdb … 0x80004005`) never reaches the payload — one plain sentence instead; `later` = 3 | pass |
| 8 | `clock_invite`: token ≥ 40 chars, expiry 5 days, `_invited(token)` finds it; a second link makes the first stop matching; officer refused; other company's clock "no longer there"; card shows `invite_until` | pass |
| 9 | `clock_add('Office door', 'Head office')` → connector "Awaiting setup", this company, tz = calendar tz, place kept; empty name refused; officer refused; `no_number` = people with neither clock number nor badge (drops by 2 after setting one of each) | pass |
| 10 | default fixture: nothing blocking, `can_publish`, label "Publish for the 40 who are ready" (one person has no week), amber = people / holidays / clocks; everyone with a week → "Publish 4 weeks"; then each blocker: rules retired → only `rules` blocks and `go_live_start` refuses with "Confirm the late and overtime rules first (step 4)."; nobody covered → only `people`; every shift archived (own + shared) → only `shifts`; working weeks archived → `weeks` (and `people`, which cannot be avoided: nobody can have an archived week); officer gets the six checks, no plan, cannot publish | pass |
| 11 | `live_check` snapshot of 6 tables (count, max write_date, max id) unchanged; plan numbers add up; sample ≤ 6 rows × 7 days and takes one person per working week first | pass |
| 12+13 | 3 working weeks / 40 people / 4 weeks with a company day off in week 2 (the night week works holidays) and a one-off on a Sunday: every row of the window published, each (person, day) once, **exactly the engine's wanted set** (+ the one-off), all this company, count = the confirm-panel number; holiday rows only for the night week and marked `holiday`; the Sunday one-off `weekend`; every row has its acknowledgement token; `pb_wfs_live_on/to` set; rail "Roster published up to …"; mail off → `emailed 0`, `no_channel 40`; **the other company's two drafts in the same window are still drafts** | pass |
| 14 | a hand-edited pattern draft is kept and published as edited; a P2 one-off (night shift on a day-shift day) is published and **its day is not refilled**; re-run: `created 0`, published 0, "already published", total unchanged | pass (after fix, §2 item 3) |
| 15 | `_publish_chunk` broken for week 2: week 1 stays published, week 2 rolled back whole, sentence names "Week 2", the reason and "Carry on"; `failed_index 1`; `go_live_resume` returns the run; finish refused ("Week 2 is not published yet"); carrying on publishes 2–4, a done week is not redone; finish; no drafts left; resume then empty | pass |
| 16 | officer: all 13 write methods → AccessError; reads work | pass |
| 17 | scale, numbers above | pass |
| (a) `test_19` | a moved automatic row: Monday → Saturday on a five-day week becomes `weekend` in the same write; moved to a six-day person → `weekday`; hand-set row keeps its value; calculated row untouched; an explicit day type in the same write wins and counts as by hand | pass |

### Browser walk (local server, port 8194, host `wfs4.localhost`, `--max-cron-threads=0`; seeded "Walk Furniture Co": 120 people in 7 teams, 3 shifts, 3 working weeks, 5 people without a week, 30 without a clock number, 4 PC clocks — ok / quiet 40 h / waiting / error — and one machine, no rules yet)
Keys with real key presses (`press_key`, `type_text`); mouse with `evaluate_script` clicks on the real elements; DB
checked with psql after each publish.

| # | Result | Notes |
|---|---|---|
| B1 | pass | 2026 renders (12 months, Sundays shaded, "313 working days in 2026", nudge "Next year's holidays are not set yet. Go to 2027"); click Tue 8 Dec → purple, list "Company day off · Tue 8 Dec", toast "Tue 8 Dec is now a company day off." + Undo; Undo → "Tue 8 Dec is a working day again." |
| B2 | pass | 2027 card "Vietnam public holidays for 2027 · 10 days" → Add them all → 10 rows, chip 313 → **304**, card gone, lunar note still under the list, toast "10 public holidays added." + Undo |
| B3 | pass | focus Mon 4 Jan, ArrowUp at the year edge stays, ArrowLeft ×3 → Fri 1 Jan, Enter → inline "Remove New Year for everyone?" with focus on "Yes, remove it", Enter → removed (9), Undo → back (10) |
| B4 | pass | cards: Needs attention (plain sentence), Waiting for IT, "Quiet since Mon 23 Nov", Sending data ×2 ("Last heard from 6 minutes ago"); Copy → toast **"Setup link copied. It works for 5 days."**, clipboard held `http://wfs4.localhost:8194/clock-bridge/setup#<43-char token>`; second copy → "This replaces the link you sent before. Make a new one?" → new link; clipboard refused → the link box appears selected (after fix §2 item 16) |
| B5 | pass | Add a clock typed "Loading bay reader" / "Warehouse 2" + Enter → new card glows, "Waiting for IT", rail "3 clocks waiting for IT", bar "Continue, finish 4 clocks later"; "30 people have no clock number · Show them" → step 3 with the new "No clock number 30" filter on, 30 rows |
| B6 | pass | step 7 with rules not confirmed: red line + disabled publish ("1 thing above still needs you"); Fix → step 4 → "These rules are right. Confirm" → "Rules confirmed for 120 people." → back on step 7 the line is green and publish is enabled |
| B7 | pass | confirm panel "4 weeks · 115 people · 2,402 shifts." = plan; Enter on "Publish now"; recorded progress: making 0–4.4 s, weeks tick 4.4 / 4.7 / 5.0 / 5.4 s, finish 5.9 s; "Workforce is live." with "2,402 shifts … from Wed 25 Nov to Sun 20 Dec", mail-off line; DB: 2,402 published, 115 people, 0 duplicates, 2,402 tokens, 0 chatter lines; Open the roster → Schedule lens "428 shifts · 428 published" this week |
| B8 | pass | back on step 7: green "Roster published up to Sun 20 Dec 2026."; 6 weeks → "1,201 new · 2,402 published before · 115 days are left out" (New Year 2027); publish → 1,201 more; DB 3,603, 0 duplicates, nothing on 1 Jan; rail "up to Sun 3 Jan" |
| B9 | pass | officer: read-only line on all three steps; calendar clicks do nothing (no toast, no question); no Add them all / remove / Add a clock / Copy link / Clock details; no launch card or sample; banner "An attendance manager publishes more weeks."; phone option is information only; console clean |
| B10 | pass | after giving the 5 people a week (step 3 via the checklist's Fix), confirming 2027 holidays ("10 days off in 2027") and clocks ("4 to finish later"): **top "7 of 7"**; widths 1440 / 1100 / 800 (window) and 400 (emulated, WS6): no page-level horizontal scroll and nothing outside the root on steps 4–7 (scripted); toast re-centres on resize (695 → 706 px = stage centre) |

### Visual differences from the prototype at 1440 that remain
1. Step 5: a year strip (last year … two ahead) and an October–December nudge; the suggestion card is above the calendar (prototype pre-fills); the list says each day's kind under its name only when the name is not the kind itself.
2. Step 6: cards carry a place line with a pin, a "Clock details" link, a "needs attention" state and a box for the link when copying is refused; the "no clock number" strip is new; "No machine at a site?" shows what is on.
3. Step 7: the green "published up to" banner, a week stepper (1–12) with the window dates, the plan breakdown line and a "left out" line under the publish card; an inline confirm panel; a week-by-week progress card. Undo of a publish (prototype demo button) does not exist — published shifts are un-published one by one.
4. Display font falls back to Inter (as P1–P3).

## 2. Deviations from the handover (and why)
1. **Holiday writes use `pb.holidays._create_row` / `_forget_demo` directly.** `add` / `add_many` / `remove` call `pb.timeoff._require_officer`, which reads `env.user` groups — `sudo()` does not change `env.user`, so even with sudo an attendance manager is refused (pinned in test 2). The studio's own gate + "this company only" check, then the private writers with sudo; `add_suggested` re-implements `add_many`'s all-or-nothing in one savepoint.
2. **Kind `company`**: `pb.holidays.add` stores the field default `public`; the studio writes `pb_holiday_kind = 'company'` right after `_create_row` (the same pattern as `holiday_journey.publish_import`).
3. **Hand-made days are never refilled** (test 14). The engine only skips a wanted day when an existing shift OVERLAPS in time; a night one-off on a day-shift day was refilled. `live_check` leaves such creates out of the plan; `go_live_start` deletes the drafts the engine made on those days in that same call (only rows with an id above the call's starting id). Counted as "left out".
4. **The window starts today, through the engine directly** (`plan` / `apply` with first = today), not `pb.shift.patterns.preview/make_drafts`: those snap to Monday, and the engine then deletes this week's untouched drafts on past days (past days are never "wanted"). On Sudima that would have deleted Mon/Tue suggestions on go-live day.
5. **Publish writes run with tracking off** (`state` is tracked: one chatter line per row otherwise).
6. **Notification**: `_ess_notify_published()` is called per week on the published records (sudo, as `publish_shifts_notified` does). The finish card's portal / no-channel counts are recomputed once over everyone in the run with the same two-channel definition, so a person in four weeks counts once.
7. **`live_check(weeks, with_plan=True)`**: the screen asks for the checklist first and the plan second — the engine pass is ~12 s for 700 people.
8. Extra facade methods: `remove_days_off(ids)`, `restore_days_off(rows)` (the two Undos), `clock_details(id)`, `go_live_resume()` (a reload carries on), `_clock_rows(now)`. Extra transient model `pb.workforce.setup.run` (24 h, own rows only).
9. Payload extras: holidays `off_count`, `confirmed_year`, `nudge`, `calendar`; clocks `key`, `later`; options carry `can_open`; live `slices`, `max_weeks`, `blocked`, plan `already_published`, `removed`, `skipped_total`.
10. Clock "where": the connector has no place field and its `create` refuses extra keys for non-superusers, so the place is stored as `source_group` (a site's PC = one source group; the group only has to share time zone and code format). Displayed: the paired machine's location if any, else the group.
11. Holidays and clocks Confirm move straight on to the next step (prototype behaviour); rules Confirm (P3) still stays.
12–18. Fixed during the walk: (12) the bar set in a step's `willStart` re-rendered the studio and re-created the step → endless `holidays()` loop (WS24); (13) Enter on "Yes, remove it" was swallowed by the calendar's key handler (WS29); (14) "Company day off · Company day off" repeated in the list; (15) undo of a remove said only "Put back."; (16) the copy-fallback box was not selected (selected before it was drawn); (17) the phone option opened the admin-only settings for an attendance manager (WS30) — now a link only for administrators, information for everyone else; (18) a later publish said "from Wed 25 Nov" for only the new weeks — now "N more shifts published … The roster now runs to …".

## 3. Facts that proved wrong, stale or incomplete
- F: `pb.holidays` write gate is unreachable with sudo (above). `remove` refuses only rows with a resource ("public rows only" is loose).
- F: `pb.holidays.add` stores kind `public` (field default).
- B.3/C: the engine's "day holds a non-pattern shift" skip is the time-overlap check only (item 3).
- B.2: `preview/make_drafts` snap to Monday and so remove past-day untouched drafts of the current week (item 4).
- B.5: `_ess_notify_published` works on any recordset; `action_publish` + the acknowledgement mint stay batched (59–61 queries per 4,200-row week).
- G: `last_error` is the PC's own status text (`connector._receive`); `_new_invitation` needs the attendance manager group (a system admin without it is refused by the model).
- Stock public-holiday create is heavy: 10 suggested days = 449 queries, 4.6 s (hr_holidays work on create).
- Attendance settings (`hr_attendance.action_hr_attendance_settings`) need administrator rights.

## 4. How the lunar dates were verified
Two independent computations, both offline, both agree:
1. Ho Ngoc Duc's published Vietnamese lunar-calendar algorithm (new moons + solar terms, **time zone +7**), implemented in a
   scratch script: Tet 2024 10 Feb, 2025 29 Jan, 2026 17 Feb, **2027 6 Feb**; Hung Kings (10th day, 3rd month) 2024 18 Apr,
   2025 7 Apr, 2026 26 Apr, **2027 16 Apr** (the 2024–2026 values match the known dates; 2026 Hung Kings is a Sunday, which
   is why the reference sheet shows Monday 27 Apr).
2. macOS Foundation's Chinese calendar (`NSCalendar` identifier `chinese`, via `osascript -l JavaScript`), day by day over
   each year: lunar 1/1 and 3/10 fall on exactly the same dates for 2024–2027.
The government's Tet days off (5–9 Feb 2027) and the extra National Day day are not yet announced; the card says so.

## 5. "No machine at a site?" — which options survived
- **Upload a file** → Workforce › Time › Import (CSV / Excel of attendance days or clock punches) — a real link.
- **Supervisor enters hours** → Workforce › Time › Week Grid (the "+" cells) — a real link.
- **Phone clock-in** → kept as information ("On for this company" from `pb.ess.workforce.portal_clock_enabled`); a link to
  the attendance settings only for administrators — an attendance manager is refused there.

## 6. Notification behaviour when mail is off
`pb_ess_workforce.publish_mail` unset (= off): no email is queued; `_ess_notify_published` returns `mail_enabled False`,
`emailed 0`. The finish card says "No emails were sent: email is switched off here." plus "N people see their shifts in
My Payobook straight away." (people with an active login) and "N people have no login and no work email, so tell them in
person." Never shown as an error. Walk: 115 of 115 without a channel (seeded people have no login).

## 7. Measured publish timings
Case 17 (700 people, one Mon–Sat week, 4 weeks from Wednesday, 16,100 rows): live check 12.1 s; start (engine makes
16,100 drafts + day types) 28.7 s; week calls 1.9 / 2.25 / 2.21 / 2.25 s; 61 / 59 / 59 / 59 queries. Walk (115 people,
2,402 rows): start 4.4 s, weeks ~0.3 s each.

## 8. Self-review against §3 (design bar)
| Bullet | Score /5 | Note |
|---|---|---|
| Hero: Publish, weeks tick over, green "Workforce is live." | 5 | progress card, each week's dot pops green with its count, bar fills, tick pops; Carry on after a failure |
| Zero dead-ends | 4 | every amber/red line has Fix landing on the exact step (people → step 3 already filtered); the phone setting is information-only for non-admins |
| Plain language | 5 | public holiday / company day off / rest day / clock / setup link / publish / roster |
| Motion with purpose, reduced motion | 4 | day fills, question rises, card glow, week ticks, finish pop; all off under reduced motion |
| Keyboard | 5 | arrows / Page Up/Down / Home/End on the year, Enter / Space toggles, the question takes focus, Esc keeps; Enter adds a clock; the publish confirm takes focus |
| One solid primary per bar | 5 | Confirm in the bar on steps 5–6; on step 7 the only solid is in the publish card |
| Lucide only, no gradients, white-label | 5 | static gates + grep |

**Weakest point, honestly:** the go-live check on a big company. The plan is the engine's full pass over every person and
day — 12 s for 700 people over 4 weeks, again for every change of the week count, and `go_live_start` re-plans (28.7 s
at that size). The checklist now appears at once and the number shows "…" meanwhile, but on Sudima (678 people) the
screen will sit on "Working out the roster…" for ~12 s each time. Second: the calendar's day buttons are 17 px on a
phone — fine for the desktop owner, small for a thumb.

## 9. What a payroll person should check at deploy
1. Go-live on Sudima publishes this company's drafts from TODAY, including the 12,384 suggested rows that are still drafts
   and fall in the window (they carry the working-week mark, so the engine keeps them as "already planned"). Past drafts
   are never touched.
2. A day already holding a shift made by hand gets no working-week shift on top.
3. Rows published here have no chatter line ("published") — by design.
4. Holidays added from the studio re-mark the future roster at once; the toast says how many.

## 10. New gotchas → ledger WS24–WS31 (appended)

## 11. Commits (branch `wfsetup`)
- `75a5c3e41` feat(pb_workforce_setup): steps 5-7 holidays, time clocks, check and go live (WFSETUP P4)
- this report + ledger WS24–WS31 (docs commit on top)

Test database `wfs4_base` and its filestore dropped after the run; the walk logins existed only there.
