# Sudima attendance confirmation — 25 November 2026

## Result and source

The client employee workbook has 606 exact employee-code/name matches:
151 Manager, 444 Worker and 11 marked left employment. The 595 current employees'
attendance classifications are configured through the existing Workforce setup
assignment workflow. The 11 leavers are not archived without termination dates.
Source workbook SHA256:
`b34a12f840bc1f26171506eacd8f5e591ac5b3110af841f7050cea5b9395e12a`.
Employee-level evidence remains private under `/odoo/backups/sudima-rules-20261125`.

The follow-up configuration confirms the attendance policy using the same
`confirm_rules` method as the screen. This does not publish the roster, enable
punch publication, activate contracts, approve overtime, or run payroll.

## Confirmed calculation

- First check-in and last check-out within the assigned shift.
- Below 10 minutes late: retain missed start minutes in paid time for both groups;
  actual punches, actual worked hours and lateness remain visible.
- At 10 minutes or more: deduct actual missed time, then an additional four hours
  for Workers or one hour for Managers. Never debit an annual leave balance.
- Day break: 11:30–12:30. Night break: 23:30–00:30. Both apply to the long day.
- Normal day: 07:30–16:30, eight paid normal hours. Ten client shift definitions
  have been checked against the calculation engine:

| Start | End | Next day | Normal hours | OT hours | Unpaid breaks |
|---|---|---|---:|---:|---:|
| 07:30 | 16:30 | No | 8 | 0 | 1 |
| 07:30 | 18:30 | No | 8 | 2 | 1 |
| 07:30 | 19:30 | No | 8 | 3 | 1 |
| 07:30 | 20:30 | No | 8 | 4 | 1 |
| 07:30 | 22:00 | No | 8 | 5.5 | 1 |
| 16:30 | 01:30 | Yes | 8 | 0 | 1 |
| 16:30 | 04:30 | Yes | 8 | 3 | 1 |
| 19:30 | 04:30 | Yes | 8 | 0 | 1 |
| 19:30 | 07:30 | Yes | 8 | 3 | 1 |
| 07:30 | 04:00 | Yes | 8 | 10.5 | 2 |

These are measured overtime quantities, not automatic payment approval. Work not
recorded after 20:30 needs workshop evidence and the correction/OT approval
workflow. Do not fabricate a checkout or truncate genuine night punches.
The separate 1.5-hour cash/excess payment mechanism remains a deferred workstream;
only approved overtime within the configured limits reaches regular payroll.

## Attendance allowance — explicitly held

VNATT (Attendance allowance) and VNATTPLUS (Additional attendance allowance)
currently remain supplied amounts from the workbook. Neither has a full recurring
entitlement saved on employee contracts. They are not automatic lateness formulas.
VNDIVISOR is 26 on all 650 existing contracts.

Owner confirmed one day's **VNATT only** per late working day, using monthly
entitlement divided by 26. Intended future formula, once entitlement is supplied:

`max(0, full monthly Attendance allowance - full monthly Attendance allowance / 26 * late working days)`

Owner then instructed: **keep it as is for now; will ask client**. No allowance
amount, binding or formula is changed. Never treat September's paid amount as the
full entitlement; it may already include deductions. VNATTPLUS stays unchanged.

## Reusable UI controls

Settings → HR → Workforce setup (also Workforce → Setup):

1. **Shifts** — start/end and total unpaid break duration.
2. **Working weeks** — repeated working and rest days.
3. **Who works what** — select employees → Late rule → Worker / Manager → Preview
   and apply; Undo is available. Working-week assignments are managed here too.
4. **Late and overtime rules** — paid-grace checkbox per lateness band; break and
   OT start times per shift; split the total unpaid duration into two timed breaks.
   Confirm activates the policy. Change the rules creates an editable new version.
7. **Check and go live** — remaining coverage checks and roster publication.

Payroll schema → Hours from clocks / component source picker now also offers
**Late working days (for allowance rules)**. It counts distinct shift dates with
lateness, including paid-grace arrivals. It is separate from information-only
late minutes, avoiding a second time deduction. An ordinary input component can
be bound using the existing UI; no Sudima allowance binding is created.

Shared implementation: `pb_attendance_policy` 19.0.1.2.0,
`pb_workforce_setup` 19.0.1.8.0, `pb_hr_payroll_formula` 19.0.1.172.0.
Paid grace defaults off; second break defaults zero. Other tenants' policies and
calculations retain their previous behavior until they adopt these options.

## Remaining payroll readiness

- 504 of the 595 current people have owner-approved proposed working weeks;
  91 have none. Of the 504, 498 have six-day weeks and six have five-day weeks.
  The latter were retained as approved rather than silently rewritten to 48h.
- 572 current employees have contracts; 23 do not. All 650 existing contracts
  remain draft. Rates for new contracts must not be invented.
- 7,044 December draft roster rows for current employees are marked reviewed;
  roster publication remains off. No new night assignments are guessed.
- Scheme 7844 already has clock-to-pay sourcing from 1 December, but is draft.
  All six connectors still have attendance publication off, while raw sync is
  independent. No payroll-ready attendance has been generated by this change.
- Eleven source leavers need dated treatment; 72 active profiles are outside the
  current source list. Do not silently archive them or include them in a pay run.
- The full recurring allowance entitlement remains outstanding as above.
- The holiday calendar still needs confirmation. The live setup screen counts
  all 678 active profiles, so it shows 161 without a week and 517 publishable;
  the current source list contains 91 without a week and 504 with one. Review
  older/leaver profiles before publishing; do not publish all 517 blindly.

## Execution and validation

Initial data script: `tools/apply_sudima_attendance_confirmation_20261125.py`.
Follow-up: `tools/apply_sudima_attendance_final_rules_20261125.py`.
Both default to rollback and use the UI-facing model methods. Follow-up also
asserts pay, contract, leave, attendance and pattern membership records unchanged.

13 standalone engine tests passed. The application rehearsal covered 43 cases:
42 passed initially; one new late-day fixture correctly refused undecided OT.
After completing its approval workflow, that test passed, including source
binding and the payroll overlay. No application guard was weakened. The final
paid-grace/two-break round-trip test passed again after the generic UI default fix.

Chrome rehearsal: saved paid grace off/on and the second break 45/60 minutes,
reloaded to verify persistence, checked worker previews at 9 and 10 minutes
(8 and 3.83 paid normal hours), and confirmed the policy through the screen.
Two-break editor rendered correctly; no console errors. Screenshots were viewed
inline only; no screenshot files created. Concurrent-session images are preserved.

Release script: `tools/deploy_sudima_attendance_rules_20261125.py`. Combined
210-custom-module inventory includes the other session's PDFFIX-2 release;
only changed installed modules are upgraded. Targets: payobook, payobook_template,
p0clone, sudima, rize. Standard Odoo addons, cron states and the existing Windows
connector archive are preserved. Rize backup is permanent; other release backups
have seven-day retention with the latest usable snapshot preserved. ABM untouched.
### Deployment and live verification

Shared release `bd9f7b12e0d4f1ae95ad59d68c8ec70719aaecc9` completed on all five
databases; service downtime including stopped-state backups was 583 seconds.
All 210 custom trees and installed versions matched after deployment; cron
states restored and all four active website login checks returned HTTP 200.
Only legacy `payroll_analytics` null-column constraint messages appeared in
upgrade ERROR output (country/date_from/date_to); upgrades exited successfully.
The same existing data condition was present in the rehearsal copy. No unrelated
analytics data was repaired.

Follow-up data application passed dry run and commit, using configuration script
commit `d2cb8eb4a` (included in combined `7684b6a4c`). Policy 2 is active; 595
current classifications, ten shifts, 504 working weeks and 7,044 reviewed future
draft rows verified. Eleven protected pay/contract/leave/attendance/pattern tables
were byte-equivalent at row-JSON digest level; clock publication switches stayed
unchanged. No allowance amounts or formulas changed.

Live Chrome check on `sudima.payobook.com/bizapp/action-1220?step=rules` passed:
confirmed policy, Worker and Manager bands, second unpaid break, real-person
preview at 9 and 10 minutes (8 / 3.83 paid normal hours), and the actual go-live
readiness screen. Console had no errors. The rehearsal had already exercised
edit/save/reload/confirm through these same screens. No roster was published.

Final read-back: 595 current people (444 Worker / 151 Manager), 504 with working
weeks, 572 with contracts, zero running contracts, zero published roster rows and
zero attendance rows. Both allowance rules still have empty formulas, no clock
binding, and no contract entitlement lines. All five real PC connectors' latest
reports on 25 November showed successful reads, zero queued records and no error;
this is last-report evidence, not a claim that the PCs are continuously online.

Evidence: `/tmp/sudima-attendance-release-20261125/receipt.json` and
`/odoo/backups/sudima-rules-20261125/final-rules-applied.json`,
`final-verification.json`. The temporary QA account was disabled, its original
groups/language restored and password rotated; plaintext credentials removed.
The rehearsal server, database and its own filestore were removed. No screenshots
or PNG files were saved by this test run; unrelated images were preserved.
