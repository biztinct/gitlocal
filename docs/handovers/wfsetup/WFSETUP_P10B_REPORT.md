# WFSETUP P10b — report: clock hours feed Sudima's pay from 1 Dec 2026

Agent: Opus 5.5, 25 Nov 2026 (times UTC). Handover `WFSETUP_P10B_HANDOVER.md`; design `WFSETUP_P10A_PROPOSAL.md`
with owner rulings R8–R16. Built in worktree `gitlocal-worktrees/wfsetup-p10b`, pushed to `19.1`
(code `55866e5cc` + `01ffeaff0`, scripts `p10b/`, deployed commit `92f9af278`). Engineering receipt: real
technical names on purpose; no names, employee numbers or credentials in this file (people are P1–P5).

## 1. What was built

| Where | What |
|---|---|
| `pb_hr_payroll_formula` 19.0.1.170.0 (`models/clock_source.py`) | `hr.formula.config.pb_clock_from` ("Hours from the clocks from", one date per scheme, tracked) and `hr.formula.rule.pb_clock_key` ("Answered by the clocks", 12 keys) written through `set_source_binding('clock', key)` / `clear_source_binding('clock')`. One overlay `_pb_clock_apply`, called by BOTH resolvers right after the pay-period fill (`_transform_data_to_formula_inputs`, `_get_formula_input_values`): no date or a period before it ⇒ returns at once (nothing touched); a period crossing the date ⇒ refused ("Split it at that date"); on/after ⇒ every clock-answered input takes the clock value, the file's number is kept beside it in the sources (`ignored`), any doubt refuses the payslip naming every reason. Never falls back to the file cell or the default. Provenance `src=employee_field, via=clock` (new `via`). `hr.payslip.pb_clock_stamp` written when clock values are used, re-checked on every move to Waiting / HR / GM / Done ("Clock hours changed after these payslips were computed. Recompute before approving."). Guards: an information-only clock fact must be "Information only", off the payslip lines and in no formula (R11); a clock scheme may not hold LATEMIN / EARLYMIN or `time.late_minutes` (R10, no double lateness); a clock key may not sit on an OTHRS*/BONHRS/REGHRS/WORKDAYS code. In a clock month the file validator no longer asks for the clock-answered columns. Clock facts are deliberately NOT in `declared_sources()` (WS75). |
| `pb_attendance_policy` 19.0.1.1.0 (`models/clock_payroll.py`, `clock_payrun.py`) | Provider `pb.clock.payroll`: per person and period, from published shifts (shift date = local start date), their calculated attendance (`_pb_policy_valid` live on a payslip, stored proof on the readiness list), overtime entries, approved time off and company holidays. Keys: paid days (R13) = worked-day equivalents (paid normal hours ÷ the shift rule's planned normal hours; lateness already cut, R10) + approved paid time off × its paid fraction + public/company holidays the person was due to work and did not; overtime hours = approved within the limit only, premium = hours × (rate − 1) (R14); over-limit, actual hours, paid normal hours, late minutes, deduction hours as information. Blockers (16): shift not under confirmed rules / not over yet / not worked out / changed since; one clock-in; no or shared clock number; punches outside every published shift's capture window; clock hours outside a shift; overtime waiting for a decision (R15); night overtime; overtime without a rate; time off waiting / type not set as paid or unpaid / on a day with clock-ins; no shifts. Zero punches on a published shift = an absence (0, listed). "Which days count" comes from the roster and the working week, never the work calendar (WS70). Run wizard: `prepare_run` / `create_and_compute` refuse with one grouped list; `pb_clock_readiness` feeds the data step panel. Leading zeros in the rules' own clock-number reading (R8). |
| `pb_clock` 19.0.1.6.0 (`models/clock_code.py`) | R8: `_code_index` exact pass unchanged, then a zero-free pass (one person ⇒ match; two ⇒ never picked, reported); auto-match uses it; the numbers screen says "Same number for two people". |
| `pb_payrun_wizard` 19.0.1.48.0 | Data step panel "Hours from the clocks": date, N of M people ready, the grouped list (click to open names and dates), "Check again", the lateness note. Absent for every scheme without a clock date and every period before it. |
| `pb_workforce_setup` 19.0.1.7.0 (`models/extra_hours.py`) | R12: step 4 foot "Built-in extra hours count: On / Off" with "Switch it off" / "Switch it on again" (managers): removes the rules of the rule sets this company's people use, keeps every field + data id on the company, "On" restores them exactly. Step 5 VN 2026 suggestions are our own list now (no Christmas, WS71). |
| `pb_blueprint` 19.0.1.11.9 + `pb_formula_studio` 19.0.1.215.0 | The scheme editor's Connect step gains the card "Hours from the clocks": the date, and per clock fact a choice of input column (information facts may only use information columns, or "+ Add a column for it", which creates one with an underscore-free CLK… code). The on-screen twin of every live mapping change. The via `clock` is bucketed on the Journey view. |
| Translations | vi_VN + id_ID for every new sentence (pb_attendance_policy, pb_hr_payroll_formula, pb_blueprint, pb_payrun_wizard get their first id_ID files; pb_workforce_setup .pot too). Parse gate on the box: every file ok, 0 empty new entries, 0 vendor words. |
| Learn | Checked: no lesson, tour or replica shows step 4's foot, the Connect card or a clock scheme's data step (the Run Payroll replica is a scheme without a clock date, where the panel never appears). Nothing to change. |

Not built (left for later, see §8): the pay data template header "From the clocks — leave blank"; a clock chip in the
component editor's source card (the Connect card and the component form carry it).

## 2. Tests

- New: `pb_attendance_policy/tests/test_clock_payroll.py` (18, proposal §9 cases 1–14 and 18 + readiness, time off on a
  worked day, unconfigured time off type), `pb_clock/tests/test_leading_zeros.py` (5, case 15),
  `pb_workforce_setup/tests/test_p10b.py` (2, case 16). Case 17 (September test cases) = the neutrality rehearsal (§3.1).
  **All 25 pass.**
- Full suites of the seven modules + `pb_timesheet_approval` on a local copy with every P10b module upgraded:
  1,876 tests. Failures compared with the unchanged `origin/19.1` code on the same database: all but three are
  pre-existing (blueprint components/finish/imported-Excel/outputs/tax/VN library, formula studio net-pay/mapping-home
  /board-lane/journey cold start, rd49 cron, R1 one-time default, currency fixture, timesheet s02, clock alerts and the
  HTTPS-only connector tests, WS62). The three that were mine were fixed and re-run green: the clock-lens test now
  expects R8 ("0885" is that person's punch), the scheme settings round-trip carries the clock date, the clock `via`
  has a Journey bucket.
- Local browser walk (Chrome, English): step 4 foot shows On, "Switch it off" → Off + toast "2 rules removed",
  "Switch it on again" → On; the Connect card shows the date and 12 rows, "+ Add a column for it" adds column G and
  selects it; the Run Payroll data step shows the clock panel for a period after the date. Console: 0 errors, 0 warnings.

## 3. Rehearsal on a hidden sudima copy (fake December = 1–23 Nov 2026, copy only)

Copy `zz_wfs_p10b_20261125` (template database, jobs + mail off at restore), served only by `odoo-bin shell` with the
P10b code first on its own addons path; live untouched. Copy-only shortcuts: working-week memberships started 19 Nov
(moved to 1 Nov, WS72); scheme put Active by SQL (live needs the scheme approval, WS73); leave types "Paid Time Off" /
"Unpaid" given a pay treatment and no allocation; the "this run only" pay data approval route applied as a Yes would
apply it. Both copies dropped after (0 left).

### 3.1 Before the clock date nothing changes (byte-identical)
September period, all 650 stored September test cases as file rows (sheet-qualified headings, 24,700 values, all
from the spreadsheet; paid days 26 ×457, 25 ×44, 24 ×31, 27 ×24…), on a second fresh copy:
today's code `d25e7a6d…`; P10b code, no mapping `d25e7a6d…`; P10b code with the full clock mapping and a clock date
of 1 Nov `d25e7a6d…` for the 38 existing inputs × 650 (the seven new information columns read 0 with no source and
feed no formula). **Identical.** Formulas untouched, so the September test cases compute as before.

### 3.2 The December story, numbers
| Step | Result |
|---|---|
| Rules confirmed (step 4's Confirm) | 678 people on the rules, 1–9 min band confirmed by the press |
| Roster 1–23 Nov published | 9,801 shifts, 517 people (7,739 made from the working weeks + the 19–23 Nov drafts), all normal-day |
| Clock-ins on, connectors 4–8 (never 1) | 124 batches 466 s + pairing 13 runs 47 s; **61,202 of 61,515 punches matched = 99.49 %** (P8: 90.3 %); 0 attendance outside a shift (the pairing skips people on confirmed rules); connector 1's 10,844 records left untouched |
| Rules calculation | 9,801 shifts in 976 s: 9,131 worked out, 659 "a first and last punch are required", 11 "punches do not overlap"; 8,896 weekday overtime entries (30,323 h) as drafts |
| **Readiness BEFORE decisions** (650 people with a running contract) | 40 s; **12 ready, 638 need attention**: overtime waiting for a decision 499 · only one clock-in on a shift 103 · no shifts this month 133 · punches on a day with no shift 71 · shift not worked out 9. The run was refused with that one grouped sentence. |
| Decisions | 3 paid + 1 unpaid time off on absent days; 1,566 rest-day / extra shifts added for punches with no shift (1,387 worked out); every overtime entry decided: 10,186 approved (22,000.8 h within the limit, **14,402.8 h above it**), 5 refused |
| **Readiness AFTER decisions** | 45 s; **432 ready, 218 need attention**: one clock-in 141 · no shifts 72 · shift not worked out 14 · punches on a day with no shift 9. Still refused for everybody; run for the 432 ready people. |
| Pay run (432 people, pay data file of September columns, "this run only") | file 377 s to load, 438 s to compute after the approval: **432 payslips, 0 refused, 432 with clock values, 432 stamped** |

Five people checked by hand (paid days = Σ normal hours ÷ 8 over weekday shifts + paid leave; overtime = Σ approved within
the limit; premium = Σ hours × (rate − 1); day rate and hourly rate from the person's rates): **5 / 5 match to the dong.**

| | Basis | Paid days | OT h | Premium h | Regular pay | OT pay | Premium pay | Information |
|---|---|---|---|---|---|---|---|---|
| P1 | daily | 16 | 40 | 20 | 3,632,000 | 1,135,000 | 567,500 | late 899 min, 34.6 h above the limit |
| P2 | daily | 17 | 40 | 20 | 4,692,000 | 1,210,000 | 605,000 | late 305 min, 28.9 h above |
| P3 | daily | 19 | 40 | 20 | 4,636,000 | 1,185,000 | 592,500 | 24.6 h above |
| P4 | daily | 19 | 40 | 20 | 4,503,000 | 1,185,000 | 592,500 | 34.0 h above |
| P5 | daily | 4 (3 worked + 1 paid leave) | 0.13 | 0.065 | 1,020,000 | 3,981 | 1,991 | — |

- **No double lateness:** no late-minute column on the scheme, 0 late rows held by these payslips, scheme refusals none;
  lateness reaches pay only as fewer paid days (P1: 899 late minutes ⇒ days with 0 paid normal hours).
- **Above the limit not paid, and shown:** overtime paid in the run 16,136.46 h = approved within the limit 16,136.46 h;
  "Overtime above the legal limit" 10,733.47 h = the limit overflow 10,733.47 h, never in the paid column.
- **File value shown beside:** a file row saying 17 paid days / 5.5 OT hours ⇒ 19 days and 40 h from the clocks, the
  file's 17 and 5.5 kept as "ignored" in the sources; allowances still from the file.
- **Sunday column guard:** the same row with Sunday hours 8 ⇒ refused: "“Sunday base hours” must be empty in months paid
  from the clocks — that work is paid as overtime from the clocks (the file says 8.0)."
- **Stamp:** a computed person's first punch moved to 15 min late, shift recalculated (7.04 → 2.79 paid hours) ⇒
  approval refused "Clock hours changed after these payslips were computed … Recompute before approving."; after
  Recompute paid days 16.18 and approval went through.

Findings the rehearsal surfaced (for Sudima, not code faults):
- **Overtime above the legal limit is large.** In 23 days 14,403 h of 36,404 approved overtime hours were above the
  limit; P1–P4 all hit the 40 h monthly cap exactly. Under R14 those hours are shown, not paid — backlog B1 has to be
  settled before the first December run or most workers are paid less than in September.
- **Afternoon workers rostered on the day shift lose the day.** 84 calculated shift-days started ≥ 10 min late, most
  with a first punch around 12:00–12:45: the 4 h band takes the whole 8 h normal day (0 paid normal hours, overtime
  still paid). The roster must carry each person's real shift.
- **One clock-in only** blocked 141 people (missed tap): each needs an attendance correction before the run.
- **People with no working week** get Saturday shifts marked "rest day" from the Mon–Fri calendar (WS69) and are paid
  rest-day overtime for them; 72 of the 650 contract holders had no shift at all after the fix-ups.

## 4. Live changes on sudima (owner-instructed, each through its screen's method) — 2026-11-25 05:56–05:59 UTC

Backup right before: `/odoo/backups/wfsetup-p10b-20261125T0700Z/sudima-before-data-changes.dump`.

| Change | Method (= the button) | Result | Undo |
|---|---|---|---|
| Vietnam's public holidays | Workforce setup step 5 "add the suggested holidays" (`add_suggested(2027)`) | December 2026 has **no** Vietnamese public holiday (the reference list's Christmas Day is not one — left out, WS71). 2027, 10 days: 1 Jan New Year · 5, 6, 7, 8, 9 Feb Tet (Lunar New Year 6 Feb) · 16 Apr Hung Kings · 30 Apr Reunification · 1 May Labour Day · 2 Sep National Day. Rows 5–14 (kind public). The government still announces the Tet days off and the second National Day day (1 or 3 Sep), and a day in lieu when a holiday falls on a Sunday. | Step 5: remove the day(s), or `remove_days_off([5..14])` |
| Built-in extra hours off (R12) | Step 4 "Switch it off" (`extra_hours_off`) | the 2 stock rules ("Employee Schedule Rule", "Non Working Days Rule") removed; fields + data ids kept on the company | Step 4 "Switch it on again" restores both exactly |
| Scheme 7844 "Hours from the clocks" | Scheme editor › Connect card (`bp_clock_bind`, `bp_save_settings`) | VNPAIDDAYS = paid days, VNOTHOURS = overtime within the limit, VNPREMHOURS = premium hours, VNSUNDAYHOURS = must stay empty; 7 information columns added (BD Days worked, BE Paid leave days, BF Public holiday days, BG Paid normal hours, BH Actual hours, BI Late minutes, BJ Overtime above the legal limit; codes CLK…, "Information only", off the payslip lines, in no formula); clock date **1 Dec 2026**. The scheme stays a **draft**. | Connect card: each row "— not used —", date emptied; the 7 columns can be deleted in the components grid |

Checked unchanged before → after: scheme draft, 0 running contracts, rules draft, 0 published roster, clock-ins off
on all six PCs, 0 overtime entries, 0 payslips. Not done (forbidden): confirming rules, publishing a roster, switching
clock-ins on, approving overtime, a pay run, activating the scheme or contracts.

Calendar study (handover item 2): no calendar re-assignment is needed. Days for time off and holidays come from the
roster and the working week; the leave/holiday day logic of the application-data path was NOT reused as is, because it
counts by the work calendar (Mon–Fri on Sudima) and would drop every Saturday (WS70).

Overtime limits (R14): Sudima has the global row 4 h/day, 40 h/month, 200 h/year (300 h for special sectors) — the
Labour Code 2019 limits the proposal used. Nothing invented. Whether Sudima's workers count as a special sector
(textile/garment/footwear, 300 h a year) is Sudima's call.

## 5. Deploy (normal tier, payroll-affecting) — LIVE ×5

START 04:40 UTC (`p10b/p10b_tries.sh` in a `systemd-run` unit); tries 1–2 waited (someone on rize), try 3: backups ×5
right before the stop (`/odoo/backups/wfsetup-p10b-20261125T0700Z/`), stop, scoped `rsync --delete` per module
(connector zip kept), `-u` of the seven modules one database at a time: payobook_template 103 s, p0clone 96 s, rize
99 s, payobook 121 s, sudima 93 s, exit 0 each (the known 3 `payroll_analytics` lines each), asset purge +
`web.assets.version` ×5, start. **Downtime 619 s.** DONE 05:04.
Verification (`p10b_verify.sh`): 7 trees = commit; versions ×5 below; jobs = prep snapshot ×5 (59/40/49/92/91 active;
payobook_template 84, 85, 86, 91 re-activated by the upgrade and switched straight back off); data before = after on
payobook_template + sudima, and on payobook / p0clone / rize apart from the new empty payslip column (md5 without it =
before; 0 stamps); rize +6 technical chatter notes on jobs (as in earlier deploys); clock connections unchanged ×5;
compiled code carries P10b ×5; 0 schemes with a clock date before the sudima change; server log 0 ERROR since start;
sites 200 ×5. R8 on existing data: 0 unmatched digit-only clock punches on any database, so nothing re-matched.
Live look (payobook.com, QA login): step 4 shows "Built-in extra hours count: On" with "Switch it off" (not pressed);
console clean.

## 6. Versions (installed = manifest on payobook, payobook_template, p0clone, rize, sudima)

pb_hr_payroll_formula 19.0.1.170.0 · pb_clock 19.0.1.6.0 · pb_attendance_policy 19.0.1.1.0 · pb_payrun_wizard
19.0.1.48.0 · pb_workforce_setup 19.0.1.7.0 · pb_formula_studio 19.0.1.215.0 · pb_blueprint 19.0.1.11.9

## 7. Sudima go-live checklist for December (plain English, in order)

1. **Decide how hours above the legal limit are paid** (owner + Sudima; backlog B1). Without it most workers' December
   overtime pay drops (in the test month 40 % of approved overtime hours were above the limit).
2. **Overtime limits** — confirm 4 h a day, 40 h a month, 200 h a year; tick "special sector" people if Sudima's work
   qualifies for 300 h (Sudima HR).
3. **Time off types** — mark each type Sudima uses as paid or unpaid (Time off settings). An unmarked type stops the
   run (Sudima HR).
4. **Everyone on a working week** — people without one get Saturdays paid as rest-day overtime (Workforce setup step 3,
   Sudima HR). Check each person is on the shift they really work (afternoon starters on the day shift lose the day).
5. **Confirm the late and overtime rules** — Workforce setup step 4 › Confirm (Sudima attendance manager). This also
   confirms the 1–9 minute line.
6. **Publish the December roster, 1–31 Dec** — step 7, including rest-day shifts for anyone working a Sunday
   (Sudima attendance manager).
7. **Switch clock-ins on for the five PCs** — step 6 (connector 1 stays off, owner's call). The PCs have sent nothing
   since 23 Nov: Sudima IT must get them reading the machines again (Sudima IT + attendance manager).
8. **During December** — enter every time off in Payobook; fix every "only one clock-in" day with a correction;
   approve or turn down every overtime entry (managers / HR).
9. **Put the scheme and contracts live** — "Propose for approval" on the pay scheme, then the 650 contracts to Running
   (Sudima, with the owner).
10. **Early January: Run Payroll for 1–31 Dec** — the data step's "Hours from the clocks" panel must say everyone is
    ready; the pay data file keeps every other column, leaves paid days / overtime / premium empty and **Sunday hours
    empty**; the file goes through Sudima's pay data approval; compute; approve (Sudima payroll).
11. **Before February** — check the government's Tet 2027 and National Day notice against step 5 (Sudima HR).

## 8. Unsure / chosen, and left undone

- **Worked public holiday** (R13 as written): a worked holiday earns holiday overtime only (300 %), no holiday day on
  top. Vietnamese law pays daily-paid workers the holiday's own pay as well (so 400 %). Built as ruled; owner question.
- Days are rounded to 6 places, not the proposal's 4 (a late day is 0.46875 day; WS68).
- Time off counted × its paid fraction (a partly paid type counts partly); company days off count like public
  holidays, collective leave does not.
- Readiness uses the stored calculations (650 people in 40 s); each payslip re-checks live (432 payslips in 438 s).
- The stamp lives in its own payslip field, not inside the sources blob (keeps the blob's one-entry-per-input rule).
- Clock facts are not added to `declared_sources()` (it would have moved pre-clock-date months, WS75).
- Left undone: the pay data template header "From the clocks — leave blank" (the shared template generator was not
  touched; the data step panel says it); a clock chip in the component editor's source card (the Connect card and the
  component form show it). Both in WFSETUP_BACKLOG.md.
- The rehearsal pay data file was a single "Audit" sheet, so its plain headings did not reach the sheet-qualified
  columns (the run took rates from the contracts); the file-shaped probes and the neutrality proof used the real
  sheet-qualified headings. Sudima's real workbook is what the scheme was built from.
