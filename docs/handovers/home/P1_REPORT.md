# HOME P1 — report (server data for the new Home)

Builder: Opus, 2026-10-12. Commits: `291c56388` (payload), `4226948d9` (tests), plus this report + ledger.
Not pushed, not deployed.

## What shipped
- `pb.dashboard.get_home_data()` in `pb_dashboard/models/home_data.py` (`_inherit = 'pb.dashboard'`, one
  AbstractModel). Payload keys exactly as the handover contract; `get_dashboard_data` behaviour unchanged.
- The activation checklist block moved verbatim into `pb.dashboard._activation(employees, contracts, runs,
  optional)`; both payloads call it (H19). All existing activation source tests still pin `pb_dashboard.py`.
- `tests/test_home_data.py` (tests 1–12, 16 methods) and the two `test_activation.py` changes.
- Manifest `19.0.2.0.0`.

## Tests (bench: `p0clone`, staged addons path first, `--test-tags /pb_dashboard`)
`pb_dashboard: 62 tests … 0 failed, 0 error(s)`. **New file: 16 passed, 0 skipped.**

| # | Test | Result |
|---|---|---|
| 1 | shape (all keys, 12 months oldest first, last = period, year marks, steps, needs order, timing ints) | pass |
| 2 | money = sums of `pb_total_*` / `pb_employee_count` / `pb_balance_ok` for two seeded runs last month | pass |
| 3 | another company's run absent from `runs` / `prepared` / `months`, visible from its own company; mixed run counts my slips only (3b) | pass ×2 |
| 4 | stage = `pb.pay.hub.get_period_state()['stage']`; seeded calendar row sets cutoff/payday; expected = distinct open-contract employees | pass |
| 5 | in-progress month, `latest` on the newest done month only, draft month not done | pass |
| 6 | (a) reader in an empty company → `needs_you == []`, `approvals_total == 0`; (b) one-person route, run submitted, approver's Home → first chip `runs_to_approve 1`, `awaiting_run.id`, approve step `wait`; (c) leave in confirm → chip equals the inbox's own leave cards | pass ×3 |
| 7 | joiner / leaver / no contract deltas; (7b) validated leave today → `out_today` +1, `week[0].n` +1 | pass ×2 |
| 8 | upcoming ascending, none before today, ≤ 6, `cutoff` present | pass |
| 9 | AST sweep of home_data.py: unguarded reads ⊆ {hr.employee, hr.contract, hr.payslip, hr.payslip.run}; guarded set == HOME_MODELS; no line-table token | pass |
| 10 | whole-word module check: `pb_import_kit` passes, `pb_import` / `pb_learn` caught (and test_05 narrowed with the same negative proof) | pass |
| 11 | timing total < 1500, every section < 600, the `home_data N ms` log call observed | pass |
| 12 | `get_home_data()['activation'] == get_dashboard_data()['activation']` | pass |

Pre-existing skips in `test_activation` (TestPayrollMonth p4–p8: "no payroll on this database") are unchanged.

## Clone timing (ms, warm, from test 11 with nothing seeded)
| period | needs_you | months | runs | people | hiring | learn | schemes | **total** |
|---|---|---|---|---|---|---|---|---|
| 8 | 8 | 2 | 0 | 6 | 4 | 0 | 1 | **34** |

Seeded calls in other tests ranged 35–210 ms (the 166/209 ms calls were approver users whose People section hit
AccessError). The clone is empty (H20) — this proves nothing at payobook scale. The log line now reads
`home_data N ms period=… needs_you=… months=… runs=… people=… hiring=… learn=… schemes=…`, so Fable can read
the split straight from the payobook server log after deploy.

## Discovery answers
- **Leave key**: the inbox card's `process_key == 'leave'` (its `area` is `time`, shared with overtime /
  timesheet / correction / unlock — too wide; H12).
- **Settlements to check**: stored boolean `pb_to_check` (not a state; H13).
- **Test-result pass flag**: `hr.formula.test.result.status == 'passed'` (selection passed/failed/warning/error);
  link field read from `test_result_ids.inverse_name`.
- **Over budget**: `pb.hiring.requisition.budget_status == 'over'` (counted over OPEN requisitions).
- **Offers waiting**: `pb.hiring.offer.state == 'sent'` ("With the candidate"). **Referrals**:
  `pb.hiring.referral.submitted_on >= 1st of month`. **Candidates**: `hr.applicant.pb_requisition_id in open roles`.
- **Bank account**: `hr.employee.bank_account_ids` (Many2many, `employee_bank_account_rel`) — there is no
  `bank_account_id` on this build (H11).
- **Tết**: `pb.holidays._column()` exposes holiday names cheaply (one search); a month is marked `'tet'` when a
  public holiday in it is named Tết / Tet / Lunar New Year. No lunar arithmetic.

## Sections that were `None` on the clone
- `learn`: `learn.runtime.next_best()` returns `{}` — the next-best flag is off on the template (H15).
- Everything else returned data (hiring readable by the test superuser; holidays none left this year, so no
  `holiday` in upcoming; no calendar row unless seeded).
- For a payroll-officer reader without contract rights, `people` is `None` (H14).

## Ledger rows added
H11 bank M2M · H12 leave process key · H13 `pb_to_check` · H14 officer has no contract ACL · H15 next_best flag
· H16 `feedback_late` not stored · H17 `assertLogs` blind · H18 run state via UPDATE in tests · H19 activation
extracted · H20 empty clone · H21 run currency.

## Deviations (with reasons)
1. **Stage** is the hub's own `_stage()` rule applied to the runs Home lists (company-visible), not the raw
   `get_period_state()['stage']` — the hub does not scope runs by company, and the stage must never disagree with
   the runs shown beneath it. Equal on a single-company database (test 4). `run_count` / `delivered_count` are
   likewise counted over the visible runs.
2. **Run visibility**: a run with NO payslips at all is visible (the hub counts empty draft runs as stage 2); a run
   whose payslips are all in other companies is not.
3. **Activation** extracted into `_activation()` instead of calling `get_dashboard_data()` (H19).
4. **`leaving`** excludes people whose ending contract is already followed by a later one (a renewal is not a
   leaver); counted as distinct employees.
5. **Money only in the company currency** (H21); runs in another currency count in `runs` / `people` only.
6. **`awaiting_run.initials`** are the submitter's (for the avatar next to "submitted by"); the run's own
   monogram is in `runs[].initials`.
7. **`now_run.done / total`**: `done` = payslips past draft, `total` = payslips in the run. No per-run "people to
   prepare" count is stored, so the prototype's "400 of 2,110" cannot be produced honestly for one run; the
   period-level `prepared` / `expected` is the honest pair.
8. **Timing**: steps and upcoming are timed into `period` (the contract's timing keys are fixed); the activation
   counts are inside `total` only.
9. **`schemes.last_run`** is UTC (`YYYY-MM-DD HH:MM`); P2 should render it relative ("2 hours ago").
10. **Steps** carry at most one `now`: stage 1 → setup, 2 → prepare, 3 → approve (or `wait` when it waits on me),
    4 → deliver; `approve.when` = the period month's latest approval day.

## Open questions for P2
- Should the hero use `period.prepared / period.expected` and drop `now_run.done/total` (deviation 7)?
- Two-currency tenants (rize): show a second figure, or a note that runs in another currency are left out?
- `people` for readers without contract rights: hide the card (current) or show employee-only figures?
- `upcoming` could add next month's cut-off when this month's has passed; today it shows only this month's.
- `out_breakdown` labels are leave-type names (data); "Travelling" in the prototype would need the trips module —
  not read in P1.
- Fields I would add: `months[].other_currency_runs` (int) if the answer to the currency question is "say so".
