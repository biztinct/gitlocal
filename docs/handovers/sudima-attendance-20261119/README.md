# Sudima attendance setup, 19 November 2026

The reusable `pb_attendance_policy` addon is opt-in. Install it only in Sudima for this release. It adds Settings → HR → Attendance calculation, employee deduction groups, roster calculation previews, and exact first/last punch calculation with fixed unpaid breaks, normal/OT separation and extra lateness deductions. Retain raw timestamps and require existing attendance/OT approval before payroll. Other tenants keep their existing behavior.

## Decisions

- Draft Sudima policy: day break 11:30–12:30; night break 23:30–00:30.
- Worker >=10 minutes late: subtract 4 additional hours from hours already worked. Manager/supervisor >=10 minutes: subtract 1 additional hour. No annual-leave debit.
- Worker 1–9 minutes: unconfirmed. The zero field is a placeholder, never a confirmed zero penalty. Activation is blocked until all bands are confirmed and cover the full range.
- Employee metadata does not identify supervisors/managers reliably. Set active employees to Worker, editable in Employee attendance settings.
- Use documented day normal window 07:30–16:30 less the confirmed one-hour lunch. Long observed days do not prove that all time is normal pay. Night templates are prepared for review, not automatically assigned.
- Infer only provisional schedules from October pairs. At least ten complete days, at least 85% starts in the day-start range, and 60% occurrence of each proposed weekday. Missing punches cannot distinguish rest from leave. Nothing inferred is published automatically.
- Existing recurring Patterns and Schedule own the rosters. Existing working calendars own standard payroll days and paid holidays; matching calendars are prepared but not assigned until review. Policy determines actual payable normal/OT hours, avoiding a partial roster reducing the monthly divisor.
- No extra Actual Pay bonus is implemented.

## Repeatable setup and review

`history.py` requests October history through the existing connector History from field. Four non-test client connectors previously started on 18 November; Ngoc already had October. Their next sync receives the changed config, and a subsequent scan can backfill older rows. No terminal download is initiated.

`infer_roster.py` accepts private `SUDIMA_EVIDENCE` and writes private `SUDIMA_SUGGESTIONS`. No employee data is committed here.

`configure.py` uses normal ORM fields and existing pattern engine actions as the authorized manager. Dry-run by default; `SUDIMA_POLICY_APPLY=1` commits. It creates draft policy/templates/patterns/calendars and future draft rosters; it does not generate attendance or pay. Every setting is editable through the application. Re-running preserves existing draft policy edits and existing patterns; it does not overwrite them.

After client review: assign the reviewed working calendar to employee/contract, check Worker versus Manager/supervisor, finish the unknown deduction band, review normal/OT boundaries and night-premium treatment, activate the confirmed policy, and publish the intended rosters. Preview/Recalculate is on the roster form. Scheduled calculation processes active policies and published rosters only. Approve generated OT and weekly attendance using existing workflows before certifying application-data payroll. Existing draft employment contracts still need their normal review/activation workflow.

## Verification

- 11 standalone exact-time tests.
- 42 isolated database tests: 8 policy integration tests plus 34 application-payroll regression tests. Overnight work belongs to shift start date; normal/OT is not subtracted twice; changed punches invalidate the payroll proof; approved correction recalculates while raw punches remain unchanged; activation/sealed fields/legacy behavior checked.
- Configuration dry-run on an isolated Sudima restore: 651 Worker settings, 88 provisional employee patterns, 11 grouped weekly patterns, 2,100 future draft shifts (19 November–16 December). Six employees with some paired October data lacked sufficient inference evidence; all other employees have no useful October history in the available export.
- Deployment receipt and Chrome results are recorded separately after deployment. Actual Windows connector window behavior is outside this change.
