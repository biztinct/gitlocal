# ETP — close-out (16 October 2026)

Expenses, Business trips and Project time are live on My Payobook on all five databases (payobook, rize,
payobook_template, abm, p0clone). Program doc `ETP_PROGRAM.md`; ledger `ETP_LEDGER.md` (E-R1…R13, rows E1–E34);
handovers `E1/E2/E3_HANDOVER.md`; build reports `E1/E2/E3_REPORT.md`.

## What shipped
| Module | Version | Pages | Commit |
|---|---|---|---|
| pb_me_expense (new) | 19.0.1.0.1 | `/my/expenses`, `/my/expenses/new`, `/my/expenses/<id>` + receipt/send/withdraw/reopen POSTs; `pb.expense.claim` carrier, process key `expense` (Their manager → Finance approver, laid per company on first send); `hr.expense.pb_claim_id`; stock Approve/Refuse/Reset guarded inside a sent claim | a68214fe4, 541363483 |
| pb_me_trip (new) | 19.0.1.0.0 | `/my/trips`, `/my/trips/new`, `/my/trips/<id>` (+ edit, send, withdraw, reopen, line add/remove, `?copy=`); drives stock `pb.business.trip` under sudo after the ownership guard | 0a6827a5a |
| pb_me_project_time (new) | 19.0.1.0.0 | `/my/project-time` week grid (+ jsonrpc cell/row/copy/fill, no-JS save); per-company switch `pb_me_project_time.enabled.<company>` + settings boolean; home card + needs-you row | 3422b3ef1 |
| pb_me_portal | 19.0.3.4.0 | three tiles, words EN/VI, glyphs `receipt` / `plane` / `clipboard-list` | 875f3b89b |
| pb_ess_workforce | 19.0.1.2.1 | reverse link on `/my/work/timesheet` → Project time | 3422b3ef1 |

Tests: pb_me_expense 34, pb_me_trip 27, pb_me_project_time (E3.1–E3.13) — all green on their clones; browser walks
at 390 px and desktop in the reports. Live walk on payobook as ess2.demo (portal login) 2026-10-16 11:45–11:55
Sydney: home tiles; claim EXP/2026/0001 (receipt preview, amount formatting, Meals chip, stepper, blocked at
"Their manager" because the demo manager has no login — the designed safe stop; finance step names a real person);
trip BT/2026/0346 (live card, 3 days × 150,000 ₫; authorised on send because company 5's trip route is "no approval
needed" since 2026-09-23 — owner chose to KEEP it); project time (Internal · Meeting, keyboard-only 8 / 7.5 / 1:30,
ring 17 of 40 h, needs-you "1 day this week has no project time"); My requests lists both; console clean.
One defect found in the walk and fixed before the batch: `?trip=` did not pre-select the trip on the claim form.

## Owner decisions in this program
Phased workflow; all three pieces in release 1; keep "no approval needed" for trips at Payobook Vietnam JSC.

## Leftovers (not blocking, not started)
- Approval engine: write the consumer's status under `sudo()` after a seated decision (ledger E14); mirror an
  inbox withdrawal on trips (`_approval_withdraw` in the shim, ledger E8). Both listed in E2_REPORT §6.
- Project time "Send week" approval (E3_REPORT §5 proposal: carrier `pb.project.week`, process key `project_week`,
  never the attendance packet).
- Demo data: ess2.demo has an attendance open since ~59 days ("Clocked in since 08:02 · 1415 h"); ess demo
  employees' managers have no logins, so expense claims block at the manager step until HR sets one.
- payobook_template: all 76 scheduled jobs are OFF since an unknown session's run at 00:06 UTC (ledger E34);
  raised with the owner, not changed.
- Expenses in days-unit companies, mileage, foreign currency, OCR: non-goals (E1_HANDOVER).
