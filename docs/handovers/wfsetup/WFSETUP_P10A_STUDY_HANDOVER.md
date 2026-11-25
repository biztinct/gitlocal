# WFSETUP P10a — study Sudima's pay scheme and propose exactly how clock hours feed it from 1 Dec 2026 (read-only)

Owner rulings (`WFSETUP_OWNER_RULINGS.md` R8–R12): from **1 Dec 2026** Sudima's pay takes HOURS from the clocks (via the
late/overtime rules), everything else stays on the pay data spreadsheet; pay formulas read PAID hours only; ACTUAL
punched hours travel as a separate, clearly labelled number that no formula reads; late minutes reduce pay; Sep–Nov
unchanged. This phase is a **study + proposal only**. No code, no writes on any database. Output a design note that the
build phase (P10b) will implement.

## Verified facts (2026-11-25 study; do not re-derive — line refs are `git show origin/19.1:<path>`)
- Rules engine per shift (`pb_attendance_policy/models/policy.py:191-200, 342-432`): `hr.shift.planning.pb_normal_hours`
  (paid normal, already minus late minutes and band penalty), `pb_overtime_hours`, `pb_deduction_hours` (band penalty,
  already removed from normal), `pb_worked_hours` (actual after unpaid break); JSON `pb_calculation_json` has
  `late_minutes`, `gross_hours`, `night_hours`. On rest days/holidays all paid hours are overtime (`engine.py:47-51`).
  It creates DRAFT `hr.overtime.request` rows (type weekday/weekend/holiday + a separate night row);
  `hr.overtime.request.actual_hours` = PAID overtime (naming trap). Rates live on the request (`rate_multiplier`, from
  `hr.overtime.config._pb_pick`); NO payroll code reads the multiplier — codes `OTHRS150/200/300/NGT` carry hours by type.
- Weekly timesheet `pb.timesheet.packet` (`pb_timesheet_approval/models/timesheet_packet.py:62-363, 637-705, 802-819`):
  manager → HR lead approval also approves the week's draft overtime; cap split `approved_hours` / `bonus_hours`.
  Double-count trap: on the timesheet route `OTHRS*` = approved + bonus and `BONHRS` = bonus again.
- Three payslip input paths, never mixed (`hr_payslip_formula.py:195-204, 1135-1159, 1194`): (A) application-data
  run (typed keys, `application_payroll_source.py`, policy-aware, effective-from date), (B) pay-data file (import line;
  gets NO timesheet/clock codes), (C) chain (`REGHRS`, `TOTHRS`, `WORKDAYS`, `OTHRS*`, `BONHRS`, `LATEMIN`…). Sudima
  today runs path B. `data_source` on a scheme input is a label nobody reads.
- Scheme inputs = `hr.formula.rule` `column_type='input'` with `source_ids` (kinds feed/rule/excel/employee_field/
  contract_field/bank_account, `formula_rule.py:102-268`); unfilled input → `default_value or 0`.
- Second lateness engine `pb_time_pay` (`LATEMIN`/`EARLYMIN`) ignores rule-made shifts → double deduction risk.
- `tools/install_sudima_payroll_review.py:58-62` makes a Sudima draft scheme (payroll_basis timesheet, effective
  2026-09-01) — unknown whether it is the live scheme (7844 per the P8 report).
- Live sudima (2026-11-25): rules not confirmed; 12,384 DRAFT roster rows 19 Nov–16 Dec; 0 attendance; clock-ins off.

## What to find out (read-only on live sudima via `Payobook19v2`, psql `-At`, heredoc quoting)
1. Sudima's live scheme(s) and pay runs: ids, names, structure; which scheme a December run would use.
2. Every input of that scheme (code, label, default) and every formula that reads an hours/days/overtime/late-type
   input — print the formulas. Identify: paid days, standard days, overtime hour inputs (by rate/type), Sunday/holiday
   hours, night, any lateness/absence deduction, and how basic pay is computed (monthly salary × paid days / standard
   days? hourly?). Same for the trial pay runs' uploaded pay data: which columns are hours/days.
3. How paid leave and paid public holidays enter today (file columns? leave records?) — clock hours must not drop them.
4. Whether `LATEMIN`/`REGHRS`/`OTHRS*` or `pb_time_pay` are already referenced anywhere in Sudima's schemes.

## Propose (the design note `WFSETUP_P10A_PROPOSAL.md`)
- **Mechanism** to give path-B (file) payslips the clock-derived values for ONLY the hour inputs, from an effective
  date, without touching the file's other columns. Preferred shape, refine or reject with reasons: a per-input source
  kind `clock` (key + from-date) on `hr.formula.rule.source_ids`, editable on screen in the scheme editor; when the
  payslip period starts on/after the date, the clock value replaces the file value for that code; the pay-data review
  screen shows the cell as "From the clock" (read-only) with the actual hours beside it. Compare with switching
  Sudima to path A from 1 Dec and say which is safer and why.
- **Exact clock keys** (paid normal hours, paid work days, overtime hours weekday/weekend/holiday/night from APPROVED
  requests' `approved_hours`, bonus/over-cap handling without double count, late minutes, band deduction hours,
  actual hours [info only]) — each with its precise definition: which rows, which dates (per shift date inside the
  pay period, not "weeks whose Monday is in the period"), approval required or not, cancelled/refused handling.
- **Mapping table** Sudima input → clock key (or "stays on the file"), with the before/after formula effect for one
  worked example employee (anonymised) for a December-like month: e.g. 26 working days, 2 days 15 min late (band X),
  4 h weekday OT, 8 h Sunday, 1 public holiday, 1 day paid leave.
- **Lateness**: show exactly how R10 is met with no double deduction (paid hours already exclude late time? or a
  deduction input?), and guard against `pb_time_pay` for Sudima.
- **Pre-run check**: what must be true before a December run (rules confirmed, roster published, every week approved,
  calculations current) and what the pay run screen shows when it isn't (a refusal list, never silent zeros).
- **Built-in extra hours (R12)**: the on-screen way to stop them on Sudima (study `hr_attendance` overtime ruleset:
  `hr_version.py:17-23`, `hr_attendance.py:296-318`; is archiving the ruleset enough, or must rules be emptied / the
  field cleared per person?) — prove on reading, do not change live.
- **Leading zeros (R8)**: confirm one place (`pb.clock.pairing._code_index`, `clock_pairing.py:229-253`) plus the two
  copies (`clock_lens.py:640-650`, `policy.py:286-302`) and propose the normalisation (strip leading zeros on both
  sides, keep exact match first; collisions "012" vs "12" both existing → report count on sudima, never auto-pick).
- Open questions for the owner, phrased as real-world choices (plain English), if any remain.

Rules: read-only everywhere; no names or employee numbers in committed files (anonymise); white-label (no "Odoo" in
anything user-visible you propose); commit the note to 19.1 (branch from origin/19.1, explicit path, rebase if needed),
message ending `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not use the shared checkout.
