# Sudima client confirmation — 25 November 2026

Configuration-only update using the existing Workforce setup UI workflows.
Source workbook remains private in SUDIMA; SHA256
`b34a12f840bc1f26171506eacd8f5e591ac5b3110af841f7050cea5b9395e12a`.
The private identity plan and deployment receipt contain employee-level evidence.

## Authorized configuration

- 606 unique badge codes and names match existing profiles: 151 Manager,
  444 Worker, 11 marked left employment. Apply the 595 explicit attendance
  classifications using `pb.workforce.setup.set_late_rule` (with its preview
  and undo record). Do not archive leavers without dated termination details.
- Worker 1–9 minutes: confirmed zero **additional** hours penalty. Keep the
  entire policy draft pending clarification whether actual missed minutes
  are paid. Worker >=10: additional 4h; manager >=10: additional 1h.
  Owner's earlier no-annual-leave-debit instruction remains in force.
- Nine confirmed shift definitions and their normal/OT boundaries:
  day 07:30 to 16:30/18:30/19:30/20:30/22:00; night 16:30 to
  01:30/04:30 and 19:30 to 04:30/07:30. Each has eight normal hours.
  Breaks are 11:30–12:30 or 23:30–00:30. Screen saves use
  `save_shift` and `save_rules`, with native notes/code fields retained.
- Existing calendar 202 contains six eight-hour days (48h). Do not assign
  a weekly rest day to an employee without resolving their proposed pattern.

## Unresolved / not payroll-ready

- Attendance allowance deduction amount/frequency and whether VNATTPLUS is
  affected. Both current allowance components are supplied amounts, not
  automated lateness formulas. Do not invent monthly disqualification.
- Worker lateness below ten minutes: actual missed-minute treatment.
- Person-to-night-shift assignments, rotations, confirmed working/rest days.
- 07:30–04:00 next-day span: screenshot's 10.5h OT implies two unpaid breaks.
  Existing policy supports only one scheduled break per shift; a reusable
  multi-break editor/calculation extension is needed if both apply. Do not
  substitute an incorrect two-hour lunch or pay 11.5h OT silently.
- Work after 20:30 requires workshop evidence and the existing attendance
  correction / overtime approval workflows. No fabricated clock-out and no
  blanket truncation of genuine night punches. Screenshot's separate cash
  1.5h payment route remains unconfigured until confirmed.
- Employee list marks 11 people left employment but gives no leaving dates.
- The newer combined branch includes deployed WFSETUP P10b. Live scheme
  7844 has clock-to-pay sourcing from 1 December, but the scheme and all
  650 contracts are still drafts; all six connectors have attendance
  publication off. Rules and rosters are drafts, with no attendance rows.
  Do not revive the deferred Actual Pay extra-bonus logic or exceed-limit
  payment workstream (owner ruling R14: paid OT stays within the limits).

## UI equivalents

Settings → HR → Workforce setup (also Workforce → Setup):

1. Shifts: editable shift definitions and unpaid break duration.
2. Working weeks: editable repeated working/rest days.
3. Who works what: select people → Late rule → Worker or Manager → Preview
   and apply; the same workflow offers Undo. Employee profile contains the
   attendance deduction group and calculation policy too.
4. Late and overtime rules: editable late bands, break start and overtime
   start per shift. Remains draft; **do not press Confirm yet**.
7. Check and go live: outstanding schedule checks and publication; not run.

## Delivery contract

Only data for database `sudima` changes; no application addon is modified,
no restart/module upgrade is required, and other databases retain their
configuration. Run the source-checked plan with the combined installed code,
under the shared deployment lock. Back up Sudima first. Validate actual
stored rules against the engine for all nine shift cases and both late
threshold boundaries, verify protected tables unchanged, then check the
deployed settings in Chrome. Report receipt and commit after verification.

## Follow-up answers received during verification

The owner confirmed paid grace (retain missed start minutes in paid time) below
ten minutes, one daily Attendance allowance removed for each late working day,
Additional attendance allowance unaffected, the existing proposed working weeks,
and both breaks on the long 07:30–04:00 shift. Cash/excess OT belongs to the
already deferred payment workstream; it is not enabled here.

Shared opt-in changes, with screen equivalents:
- Late-rule sentence checkbox: **Pay the missed minutes; keep the late-arrival
  record**. Stored on a band, false by default. Actual punches/worked hours remain
  actual; paid hours include the credit. Existing policies retain their output.
- Shift rule: split total unpaid break into two timed parts. No overlap, negative
  duration or out-of-shift break accepted. Native advanced form also exposes both.
- Pay schema clock-source picker: **Late working days (for allowance rules)**,
  counting distinct shift dates with lateness, including paid-grace arrivals.
  This is separate from the information-only late-minutes source, preventing
  accidental second deduction of missed minutes. No tenant rule is hard-coded.

Confirmed live facts: VNATT and VNATTPLUS are workbook inputs, not formulas, and
neither has a saved contract entitlement. VNDIVISOR is 26 on all 650 contracts.
A one-day allowance formula needs the un-reduced entitlement and confirmation
of its daily divisor. Do not turn a historically paid amount into an entitlement.

Of the 595 current source employees, 504 have a working week and 91 do not.
498 of those 504 have six days; six have confirmed proposed five-day weeks.
There are contracts for 572 current people, leaving 23 without one. All contracts
remain draft. Eleven source leavers need dates; 72 active database profiles are
outside the current source list. Do not auto-archive or include them in a pay run.

Second data application: `apply_sudima_attendance_final_rules_20261125.py`, after
the shared release. It adds the long shift, saves both groups' paid grace, and
marks only current employees' future draft rosters as reviewed. It keeps the
policy draft while the allowance/employee coverage remains unresolved, and never
publishes rosters, enables connector publication, approves overtime or runs pay.

Validation in progress: 13 standalone calculation tests pass. The isolated
application rehearsal passed 42/43 cases initially; the new late-day test correctly
refused undecided OT. After completing the fixture's approval workflow, its
source-to-payroll retest passed. The application behavior was not weakened.
