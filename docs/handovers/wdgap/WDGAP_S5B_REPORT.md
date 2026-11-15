# WDGAP S5-B — Time into pay (`pb_time_pay`) — report

Branch `wdgap-s5b` (from `origin/19.1` @ `abc2259b6`). Builder: implementer and
self-reviewer. No deploy, no live-server access. Local database `wdgap_s5b_t` (copy of
`upd_p6_t_tpl`), dropped at the end.

## 1. What was built, per item

### Item 5a — overtime suggested from clock punches (owner ruling L6)
- `pb.time.pay._week` works out, live and with no writes, for every person-day of a
  Close week: the expected window from a published/completed shift first, otherwise
  from the person's **working schedule** (the calendar's own interval engine, lunch
  excluded). With neither, the day is a rest day. A company public holiday (company
  closure, `resource.calendar.leaves` with no resource) makes it public-holiday overtime.
- Suggested hours = the smaller of "time punched outside the window" and "worked hours
  (core `worked_hours`, net of the calendar lunch) beyond the expected hours", so a late
  arrival who stays late to make it up is NOT offered overtime, and lunch is never
  overtime. Rest day / holiday: all worked hours. Hours inside the company's night
  window (its `night` overtime rule) become a night suggestion. Rounded DOWN to the
  quarter hour; nothing at or under the Close tolerance (10 min by default).
- Only real punches count (device, the employee's own clock page, corrections,
  imports). A day holding a weekly-grid entry (typed hours, made-up 08:00 start) is
  skipped.
- In the Close: the "Time into pay" section lists suggestions; a manager accepts one or
  many (choosing "Pay it" or "Give time off" first) and they become ORDINARY overtime
  requests (planned = actual = suggested, so they are "clean"), sent on the existing
  overtime route, marked "Suggested from clock punches". "Not overtime" hides one and
  keeps the reason (`pb.time.ot.dismiss`). Suggestions never pay anything themselves.
  A suggestion disappears once any request of that kind exists for that person and day.
- Refused per row and reported on screen: your own record, a locked day, a frozen week,
  a young-worker block (the model's own words).

### Item 5b — late and early minutes from real punches (owner ruling L5)
- Same expected windows. Late = first punch-in after the expected start; early = last
  punch-out before the expected end (only when every punch of the day is closed).
  Counted from the expected time, in whole minutes, once past the company's grace
  minutes (`pb.attendance.rule` grace in/out, 15 by default). Skipped on holidays, trip
  days, whole-day leave and days with part-day leave.
- Shown in the Close with **Confirm** (counts for pay) and **Excuse** (never reaches
  pay, optional note), one by one or for the ticked rows. A decision is stored
  (`pb.time.late`) with the minutes as shown; if the punches change later, the row says
  "Changed since decided" and must be decided again. Refused: own attendance, locked
  day, minutes already paid.
- ONLY confirmed minutes reach pay, as input pay items **`LATEMIN`** / **`EARLYMIN`**
  (no-file runs) or the typed sources **`time.late_minutes`** / **`time.early_minutes`**
  (application-data runs). Regular runs (or no run) only, never a Top-up or Extra run.
  Each confirmed row is held by one payslip (`pb.time.late.payslip_id`): free → held →
  paid when the payslip is done; a deleted payslip lets go (set null), a cancelled one is
  read as letting go, and a decision on a paid row cannot change.
- **Off until mapped:** until some live scheme of the company has one of those pay
  items, the section says "Shown for information" and the minutes hold nothing. Once a
  scheme has one, undecided rows add a checklist line and keep "Lock week & send to
  payroll" disabled, exactly like an open flag.

### Item 4 — pay it or give time off (owner rulings L3, L4)
- `hr.overtime.request.pb_comp_choice` (empty = pay, so install rewrites no stored
  overtime). Changed only through `_pb_set_choice` by somebody the overtime model lets
  decide it, while draft or sent in; refused on a locked day or frozen week; sealed once
  approved (own token, the overtime seal pattern).
- On approval with "Give time off": one allocation of the company's **"Time off in
  lieu"** kind of leave, for exactly approved + bonus hours (hour for hour), from the
  overtime's day, **no end date** (never runs out, no payout — L4). The kind is created
  the first time it is needed (hours, needs an allowance, paid / employer-funded, no
  backdating, not deducted from core overtime), with Vietnamese and Indonesian names
  written into the field. If the allocation cannot be validated, the approval is rolled
  back with a plain message: overtime that is neither paid nor given as time off never
  exists.
- Not also paid: above both producers (`hr_payslip.py`), for each approved time-off
  request, exactly the hours the producer that actually answered counted are taken back
  out of `OTHRS*` / `BONHRS` — the approved-weeks rung when the company pays from
  approved weeks and a week was approved, otherwise the bridge when the run is one it
  feeds. Application mode: taken out of the `period.ot.*` / `period.approved_bonus_hours`
  facts by the request ids each fact lists; evidence key `time_off_in_lieu_hours` is
  added only to a fact that changed.
- Where the manager chooses: the Close (when accepting suggestions), the Overtime desk
  ("Time off" beside Approve on each card, "Approve as time off" in the bulk tray), and
  the overtime form ("Give time off instead" / "Pay it instead"). The Approvals inbox
  shows a "When approved: Pay it / Give time off" chip (and "From: Clock punches").
- My Overtime (`/my/work/overtime`): "Given as time off" tile and a "Time off in lieu"
  badge on those rows (`get_my_overtime` keeps every key, adds `time_off` and
  `total_time_off` — contract C-4).

### Fix inside the lane — holiday overtime (ledger S5-3)
`hr.attendance.weekentry._holidays` is extended from `pb_time_pay` to add company
closures of the user's companies (the old v16 list is still read underneath). The
weekly grid now offers public-holiday overtime on public holidays.

### Known gap, handled honestly — pay data file schemes (ledger S5-1)
The file path is NOT changed. When the company has live schemes that ask for a pay data
file (same test as the Run payroll file step), the Close section names them: "Paid from
a pay data file … Confirmed minutes and approved overtime do not reach these payslips by
themselves. They are shown here for you to include in the file." and offers the month's
figures per person (overtime to pay by kind, excluding time off, bonus hours, confirmed
late and early minutes). See owner question 1 for what a real fix needs.

## 2. Files edited outside the new module (only the ones the lane allows)

| File | Change |
|---|---|
| `pb_hr_payroll_formula/models/input_provenance.py` | ONE line: `'late_minutes'` added to `VIAS` |
| `pb_source_atlas/models/pb_source_atlas.py` | ONE line: its label in `VIA_LABELS` |
| `pb_mission/static/src/js/pb_close_lens.js` + `pb_mission/static/src/xml/pb_close_lens.xml` | A section slot: `export const CLOSE_SECTIONS = "pb_close_lens_section"`, getters `sections` / `sectionCtx`, `reloadBoard()`, and the `t-foreach` under the flag table. No new user-visible strings, so `pb_mission/i18n` is unchanged |

`pb_close/models/*` was NOT edited: the Close payload is extended by `_inherit =
'pb.close'` from `pb_time_pay`. Nothing in `pb_workforce_payroll_bridge`,
`pb_timesheet_approval`, `pb_timeoff`, `pb_schedule`, `pb_hr_workforce`,
`pb_ess_workforce`, `pb_attendance_flow` was edited (all by inheritance).

## 3. Tests

### 3.1 New tests — `pb_time_pay/tests/` (tag `wdgap_s5b`), 48 tests, **48 / 48 pass**

| # | What |
|---|---|
| T01 | Past the shift → 3 h weekday, compared with the shift |
| T02 | No shift → working hours 08–17 with lunch: 08–19 punch = 2 h |
| T03 | Late and stayed late to make up → no suggestion |
| T04 | Rest day → all 4 h, weekend kind |
| T05 | Company holiday → 4 h public-holiday kind; no late/early rows |
| T06 | 08–23 against 08–16 → 6 h weekday + 1 h night |
| T07 | 8 min over → nothing; 40 min over → 0.5 h (rounded down) |
| T08 | Weekly-grid typed hours → no suggestion, no late row |
| T09 | Accept → submitted request, planned = actual = 3 h, marked from punches; gone from board; accepting again refused |
| T09b | Accept as time off carries the choice |
| T09c | Own record and locked day refused per row |
| T10 | "Not overtime" hides it and keeps the note and hours |
| T10b | An officer who may not decide cannot accept (AccessError) |
| T10c | An existing request of that kind suppresses the suggestion |
| T11 | Grace: 14 min late = on time, 16 = 16; out 15:44 = 16 early, 15:46 = none |
| T12 | No shift → working-hours basis, 30 min late |
| T12b | Open punch → late counted, no early leave yet |
| T13 | Confirm and Excuse stored, note kept, stats move |
| T13b | Punches changed after a decision → "changed", counted open again |
| T13c | Own and locked refused, nothing stored |
| T13d | A paid decision cannot be changed or removed |
| T14 | Minutes hold the week only once a scheme maps `LATEMIN`; decided → checklist ticks |
| T14b | On an otherwise clean board, open mapped minutes disable the lock |
| T15 | Time off on approval: validated allocation, no end date, hours = approved + bonus; kind made once and reused; nothing made by install |
| T15b | Pay it → no time off |
| T16 | Choice sealed: direct write refused, non-decider refused, after approval refused (even superuser) |
| T16b | Locked day refuses the change |
| T17 | Desk "approve as time off" approves and gives the hours; card says so |
| T18 | Inbox chip says what approving will do |
| T19 | My Overtime keeps its keys, flags time-off rows, totals them |
| **T20** | **GOLDEN: no new data → no run / Regular / Top-up / Extra payslips computed with and without this module's rung are identical (stored inputs, their sources, computed values, every line, compared as sorted JSON); nothing held** |
| T20b | Scheme without the items → identical values and sources |
| T21 | Bridge: time-off hours (and their bonus) taken out; paid hours still paid |
| T21b | Top-up never fed → nothing taken |
| T22 | Approved weeks: the week's 5 h → 3 h after the time-off request |
| T23 | Application facts: taken out by listed request id, evidence key only on the changed fact, untouched otherwise |
| T24 | Confirmed minutes 46 late + 20 early fed and held; idempotent; second regular payslip takes nothing; Top-up takes nothing; excused never counted |
| T24b | Letting go: excused after taken, deleted payslip, cancelled payslip → next payslip may take it |
| T24c | Full compute pays the minutes through the scheme formula |
| T25 | Application source answers free + own rows only, lists row ids |
| T26 | Weekly grid reads company closures (S5-3) |
| T27 | Pay data file schemes named; month figures exclude time off |
| T28 | Empty week / no people → quiet |
| T29 | Rights: no-role user refused; officer reads but cannot decide; portal cannot read decisions; nobody creates decisions directly |
| T30 | Silent install: no scheduled job, no data files |
| T31 | Collision scan warns about `LATEMI` |
| T32 | No vendor name in this module's screens, scripts or translations |
| T33 | The Close section writes only from clicks (no read of its own, no RPC in setup); the slot exists in the lens |

### 3.2 Suites of every module edited or extended, against the baseline

Baselines were recorded BEFORE any edit on the same database.

| Suites | Baseline | With S5-B |
|---|---|---|
| `/pb_close,/pb_mission,/pb_workforce_payroll_bridge,/pb_timesheet_approval,/pb_hr_workforce,/pb_ess_workforce,/pb_attendance_flow,/pb_young_worker` | 441 tests, 4 failed + 4 errors | **489 tests (441 + the 48 new), 4 failed + 4 errors — the identical set** (log `after3.log`) |
| `/pb_hr_payroll_formula,/pb_source_atlas` | 848 tests (835 + 13), 4 failed | **848 tests, 4 failed — the identical set** (log `after2.log`) |
| `/pb_time_pay` | — | 48 / 48 (with `-u pb_time_pay,pb_mission`, together with `/pb_mission` 61 / 61) |

Baseline failures (all pre-existing, unchanged code): TestAttendanceFlow 04 (F), 05 /
07 / 13 (E); TestWeekEntry 06 (E); TestP8Adversarial ack_week (F); TestYoungWorker 09b
(F); TimesheetPacketCase s02 approving_the_week (F); TestRd49SyncCost 02ab + 02i;
TestRecordsR1OneTime 07b; TestSchemeCtxCurrency 04.

### 3.3 Static gates
`pyflakes` clean on models and tests; PO gate (Odoo `PoFileReader`): `pb_time_pay`
vi_VN + id_ID 188 rows each, 0 msgstr naming the vendor, 0 placeholder mismatches;
`pb_mission` i18n unchanged and parses.

### 3.4 Browser walk (local copy, `localhost:8473`, cron off, Chrome at 614 px — the window is
shared with other builders so it was not resized; seeded DEMO people in Vietnam time)
- Mission Control › Close, department "DEMO Packing", week 45: section "Time into pay"
  under the flag table. 3 suggestions (An 3 h weekday vs the shift — worked 11 h,
  expected 8 h; Binh 2 h weekday vs working hours; Binh 4 h rest day), 3 late/early rows
  (An 25 min late, An 30 min early, Chi 40 min late vs working hours), the pay data file
  notice naming "DEMO File scheme", and — because a DEMO scheme maps `LATEMIN` — the rail
  checklist line "3 late or early minute row(s) to confirm or excuse" with the lock
  disabled.
- "Give time off" + tick + "Accept 1" → "1 overtime request sent for approval."; the row
  left the board. Chi "Confirm" → Confirmed, 40 minutes confirmed; An early "Excuse" with
  note → Excused with the note; the checklist count fell to 1.
- Overtime desk: "Time off" beside every Approve, the accepted request carries the chip
  "Time off when approved". "Time off" on Dung's request → approved, allocation 1.5 h
  (0.1875 days), validated, no end date, kind "Time off in lieu" / vi "Nghỉ bù", hours.
  Approving the request the same admin had ACCEPTED was refused by the existing approval
  rule ("You were part of preparing or sending this in…") — correct; see owner note in §7.
- Overtime form: "Paid or time off: Time off when approved", "Suggested from clock
  punches" ticked; "Pay it instead" (under the header's More menu at this width) →
  "Paid".
- My Overtime as Dung (portal): tile "Given as time off 3.5 h", "Time off in lieu" badge
  on both rows; the Vietnamese page (`/vi/…`, fetched as HTML) shows "Đã cho nghỉ bù" and
  "Nghỉ bù". Close-section strings load in Vietnamese (74 entries for the web client).
- Console: no errors or warnings from any page of this module (two pre-existing log
  lines from other modules only). One visual fix made during the walk: a missing gap
  between two sentences (CSS `span + span`).
- At 614 px the Close lens's own two-column layout leaves the flag-table column ~236 px,
  so the section's tables scroll sideways inside their cards (the lens itself does not
  stack at that width — existing behaviour, not changed here).

## 4. Rails
- Golden: no new data → byte-identical payslips (T20/T20b); every new value only where a
  time-off request or a confirmed minute exists.
- Paid once: confirmed minutes held by one payslip, row lock (`FOR UPDATE`) before
  taking; only a payslip still being worked out (draft / waiting) writes holds; a
  finished one only reads what it holds.
- Time off is never also paid; overtime never ends up neither paid nor given.
- Silent install: no job, no data, no kind of leave, nothing switched on; existing
  overtime rows untouched (no column default).
- Rights: reads behind the Close officer gate; every write behind the Close review gate
  (attendance or payroll manager) or the overtime model's own decider rule; no-self on
  every decision; decisions are not writable by anyone but the system; company rules.
- The Close board can never break because of this section (its read is wrapped; the
  board is returned as before on any error).

## 5. Contracts other phases rely on
- `registry.category("pb_close_lens_section")` — `{ Component }`; props `data` (whole
  Close payload), `ctx` (`departmentId`, `weekStart`, `search`), `onChanged()`.
- `pb.close.get_close_data(...)` adds key `time_pay` and (when mapped) checklist key
  `late_minutes`.
- `pb.time.pay`: `accept_suggestions(keys, choice, department_id, week_start, search)`,
  `dismiss_suggestion(key, note, …)`, `decide_late(keys, decision, note, …)`,
  `set_overtime_choice(request_ids, choice)`, `_toil_kind(company, create=True)`,
  `_closure_days(companies, d_from, d_to)`, `_week(emps, d_from, d_to)`.
- `hr.overtime.request`: `pb_comp_choice` ('pay' / 'time_off' / empty = pay),
  `pb_toil_allocation_id`, `pb_from_punches`, `_pb_set_choice(choice)`,
  `_pb_toil_hours()`.
- `hr.leave.type.pb_toil_kind` (default False, not required — S5-A creates kinds without
  knowing it).
- `pb.ess.workforce.get_my_overtime()` rows gain `time_off`; result gains
  `total_time_off`. No existing key changed.
- `pb.ot.desk.act(ids, 'approve_time_off')`; queue cards gain `time_off`,
  `time_off_label`, `from_punches`.
- Pay item codes `LATEMIN`, `EARLYMIN`; application keys `time.late_minutes`,
  `time.early_minutes`; provenance via `late_minutes`.

## 6. Deploy notes (for the step's deploy agent)
- **Risky tier** (touches pay). Merge order for step 5: A, then B, then C.
- **Install** `pb_time_pay` with `-i` on all five databases (it installs silently).
  Depends on `hr_holidays`, `pb_timesheet_approval`, `pb_workforce_payroll_bridge`,
  `pb_close`, `pb_attendance_flow`, `pb_hr_workforce`, `pb_ess_workforce`,
  `pb_import_kit` — confirm `pb_timesheet_approval` is installed on all five first
  (FACTS item 4 risk).
- **Shared modules that need a version raise at deploy** (I did not edit their manifests,
  to stay in lane):
  | Module | Now | Raise to | Why |
  |---|---|---|---|
  | `pb_hr_payroll_formula` | 19.0.1.168.0 | 19.0.1.169.0 | one Python constant (`VIAS`); a restart alone loads it, the raise is for `latest_version` proof |
  | `pb_source_atlas` | 19.0.1.14.0 | 19.0.1.15.0 | one Python constant (`VIA_LABELS`) |
  | `pb_mission` | 19.0.1.13.1 | 19.0.1.14.0 | Close lens JS + XML (asset change): `-u` + asset purge (`DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'`) + restart |
  If another phase also raises one of these, take the higher number.
- After install: asset purge per database (new JS/SCSS/XML), restart.
- **Rehearsal** (pay): on a rize copy, recompute a regular run old vs new — expected 0
  differences (no time off and no confirmed minutes exist yet anywhere). Check
  `hr_holidays_attendance` presence per database (the time-off kind sets
  `overtime_deductible = False` when it exists).
- Seam tests for the step: S5-A's expiry filter + this module's never-expiring
  allocations (date_to empty → always counted); S5-A creating a kind while
  `pb_toil_kind` exists (default False).
- No data migration.

## 7. Owner questions (plain words)

1. **Payslips made from a pay data file.** Rize pays 15 schemes from a file. Overtime
   that a manager approves in Payobook, and late minutes that a manager confirms, do not
   go into those payslips on their own today — the Close now lists them for the team to
   type into the file. A real fix would let those payslips also take approved overtime
   and confirmed minutes from Payobook, but ONLY for pay items the file has no column
   for (so the file still wins where it has one), with the same "paid once" check.
   It touches the file import, which is another team's money path, so it needs its own
   step and a rehearsal. **Do you want this built, or should file-paid schemes keep
   taking everything from the file?**
2. **How late minutes count.** Today a person 20 minutes late with 15 minutes' grace
   counts as 20 minutes late. The other common rule counts only the 5 minutes past the
   grace. Which do you want?
3. **Rounding suggested overtime.** Suggestions are rounded down to the quarter hour and
   nothing under 10 minutes (the Close tolerance) is suggested. Keep that, or round to
   the half hour / full hour?
4. **Choosing "time off" in the Approvals inbox.** Managers can choose "Pay it" or "Give
   time off" on the Overtime desk, in the weekly Close and on the overtime form. In the
   Approvals inbox and on My team they only SEE the choice (another team owns those
   screens). Do you want the choice there too? It needs one small change in the inbox.
5. **Who accepts suggested overtime.** Whoever accepts a suggestion becomes the person
   who sent the overtime in, and the approval rules then stop that same person approving
   it (someone else must). If the line manager should be able to accept AND approve in
   one go, the overtime route needs an exception — or we change who counts as the
   sender. Keep it as it is?
6. **Employees seeing their own late minutes.** Should an employee see their confirmed
   late minutes on My Payobook? Not built (left for later).

## 8. Left for later
- Choice buttons inside the Approvals inbox drawer and on My team (owner question 4).
- Employee view of own late / early minutes (owner question 6).
- My Overtime badge is capitalised by the portal badge style ("Time Off In Lieu").
- Pay data file runs taking approved overtime / confirmed minutes (owner question 1).
- `count_late_as` in `pb_attendance_flow` left untouched (optional in the lane); the
  pay mapping is the switch instead.
- An "expired time off in lieu" warning is not needed (L4: never runs out).

## 9. Gotchas (ledger rows)
- **S5B-1** Locally the repo's vendored `hr_contract` loads (absent from core 19):
  creating an attendance for an employee on a FLEXIBLE working schedule raises
  `_get_expected_attendances() takes 3 positional arguments but 4 were given` in core
  attendance overtime. Fixtures use fixed schedules. Worth checking which copy the server
  loads.
- **S5B-2** A pay item code with digits after letters (`S5BNET`) is read by the formula
  converter as a cell reference (`S` + row 5). Use letters only for new codes.
- **S5B-3** `set_no_approval_needed(company, 'overtime')` makes `action_submit` approve
  at once; a suite that needs a SUBMITTED request must not seed it.
- **S5B-5** In a scratch run script, `touch $2.done` AFTER `shift 3` names the done-file
  after an odoo argument, so every "wait for done" loop waits for ever. Save the log name
  in a variable before shifting.
- **S5B-4** A test run with `-u X --test-tags /A,/B` runs post-install tests only for
  the updated modules (and what they pull in): the eight workforce suites did not run
  under `-u pb_time_pay,pb_mission`. Run the suites in a second pass without `-u`.
- **S5-1 / S5-3** (FACTS) confirmed and handled as above.
- Test database `wdgap_s5b_t` and its filestore dropped at the end.
