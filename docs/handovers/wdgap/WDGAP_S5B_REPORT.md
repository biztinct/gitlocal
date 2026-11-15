# WDGAP S5-B — Time into pay (`pb_time_pay`) — report

## PAUSED (owner pause, 2026-11-15)

**Where I stopped.** All code for S5-B is written and committed as WIP on branch
`wdgap-s5b`. The module's own suite passed **48 / 48** (`/pb_time_pay`, log
`scratchpad/s5b/logs/t2.log`) before the last test edits; the `.po` files were then
generated and pass the parse gate. The full "after" suites were STOPPED part-way at the
pause (log `after1.log` is incomplete and must be ignored).

**Exact next step on resume.**
1. `bash scratchpad/s5b/after1.sh` (runs, on the kept database `wdgap_s5b_t`,
   `-u pb_time_pay,pb_mission` with tags `/pb_time_pay` + the eight workforce suites,
   then `/pb_hr_payroll_formula,/pb_source_atlas`). Compare with the baselines below.
2. Browser walk: `odoo-bin shell -d wdgap_s5b_t < scratchpad/s5b/walk_seed.py`, start
   a local server on `127.0.0.1` with `--max-cron-threads=0`, walk Mission Control ›
   Close (the "Time into pay" section), the Overtime desk ("Time off" buttons), the
   overtime form, and `/my/work/overtime`; console clean.
3. Finish this report (sections below marked TODO), drop `wdgap_s5b_t`, final commit +
   push.

## Baselines recorded BEFORE any edit (database `wdgap_s5b_t`, copy of `upd_p6_t_tpl`,
`-u` of the 33 modules behind HEAD)

| Run | Tests | Failures / errors (all pre-existing) |
|---|---|---|
| `/pb_close,/pb_mission,/pb_workforce_payroll_bridge,/pb_timesheet_approval,/pb_hr_workforce,/pb_ess_workforce,/pb_attendance_flow,/pb_young_worker` | 441 | 4 failed, 4 errors: TestAttendanceFlow 04 (F), 05/07/13 (E); TestWeekEntry 06 (E); TestP8Adversarial ack_week (F); TestYoungWorker 09b (F); TimesheetPacketCase s02 approving_the_week (F) |
| `/pb_hr_payroll_formula,/pb_source_atlas` | 848 (835 + 13) | 4 failed: TestRd49SyncCost 02ab + 02i, TestRecordsR1OneTime 07b, TestSchemeCtxCurrency 04 |

## What is built (summary — TODO full write-up after the after-runs)

- New module `pb_time_pay` 19.0.1.0.0: overtime suggestions from punches (shift first,
  else working hours — L6), bulk accept into ordinary requests / "Not overtime";
  late and early minutes from real punches with Confirm / Excuse in the weekly Close
  (L5), fed as `LATEMIN` / `EARLYMIN` (file-less + application mode `time.late_minutes`
  / `time.early_minutes`), paid once (`pb.time.late.payslip_id`); "Pay it / Give time
  off" with hour-for-hour never-expiring allocation into a per-company "Time off in
  lieu" kind (L3/L4), taken back above the bridge, the approved-weeks rung and in
  application facts; holiday-overtime reads company closures (S5-3 fix); pay-data-file
  schemes named on screen with the month's figures to put in the file.
- Shared-file edits (the allowed ones only): one line in
  `pb_hr_payroll_formula/models/input_provenance.py` (via `late_minutes`), one line in
  `pb_source_atlas/models/pb_source_atlas.py` (its label); `pb_mission` Close lens
  JS + XML gain a section slot `pb_close_lens_section` (no new strings). No manifest of
  another module was touched: the deploy agent should bump `pb_hr_payroll_formula`,
  `pb_source_atlas` (Python constant only) and treat `pb_mission` as an asset change.
- `pb_close/models/*` NOT edited (the Close payload is extended by inheritance).

## Gotchas seen (ledger candidates)

- S5B-1: locally the repo's vendored `hr_contract` loads (not in the 19 core addons):
  creating an attendance for an employee on a FLEXIBLE working schedule raises
  `_get_expected_attendances() takes 3 positional arguments but 4 were given` inside
  core attendance overtime. Test fixtures use fixed schedules.
- S5B-2: formula codes containing digits after letters (`S5BNET`) are read as cell
  references by the converter (`S`+`5`…). Test pay items use letters only.
- S5B-3: `set_no_approval_needed(company, 'overtime')` makes `action_submit` approve at
  once; suites that need a SUBMITTED request must not seed it.
