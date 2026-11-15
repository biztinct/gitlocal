# WDGAP W2-D2 — Back pay for past months in this month's pay run: report

## PAUSED (owner pause, 2026-11-15)

**Where I stopped.** The whole build is committed on branch `wdgap-w2d2`
(commit `39f641144`, feature; this WIP commit adds only this report). The
`pb_retro` suite is green on the local copy (57 tests in the runner count,
0 failed, 0 errors — B13 re-run alone after its last fix: green). The
"after" run of the seven regression suites was STARTED and STOPPED on the
pause before it finished (no result). Test database `wdgap_w2d2_t` is kept
(upgraded to this branch, `pb_retro` 19.0.1.1.0 installed).

**Exact next step.**
1. Re-run the regression suites on `wdgap_w2d2_t` with the branch tree:
   `bash scratchpad/w2d2/suite.sh scratchpad/w2d2/odoo.conf after
   pb_retro,pb_hr_payroll_formula,pb_payruns,pb_payrun_wizard,pb_loans,pb_fund_payments,pb_pay_delivery`
   (≈45 min, poll `logs/after.done`) and diff its fail set with
   `logs/baseline.failset` (baseline below).
2. Optional extra golden: `-i pb_demo` and its `TestDemoExtraRun` /
   PR-D demo tests (demo path goes through the same line producer).
3. Browser walk: `odoo-bin shell -d wdgap_w2d2_t < scratchpad/w2d2/walk_seed.py`
   (written, not run yet), server on 127.0.0.1 with `--max-cron-threads=0`:
   re-work → Pay the difference → Approvals as `payhead.walk` → November run
   (compute) → payslip → HTML/PDF report → board glance; console clean.
4. Finish this report (test table, worked example already below), add the
   ledger rows (draft in §9), drop `wdgap_w2d2_t` + its filestore, push.

## Baseline (recorded before any edit, pristine copies first on the path)

`/pb_retro,/pb_hr_payroll_formula,/pb_payruns,/pb_payrun_wizard,/pb_loans,/pb_fund_payments,/pb_pay_delivery`
on `wdgap_w2d2_t`: **1,135 tests, 9 failed, 0 errors** — all known:
TestRd49SyncCost ×2, TestRecordsR1OneTime 07b, TestSchemeCtxCurrency 04
(formula baseline since PR-A), TestRunScreen ×5 (close week, ledger PRB-W6).

## What was built (summary — full write-up to follow)

- Module `pb_retro` 19.0.1.0.0 → 19.0.1.1.0; no other module edited. New
  dependencies (all installed on every live database): biz_approval_workflow,
  pb_approval_config, pb_pay_delivery, pb_fund_payments.
- **The seam** (no hook needed in `pb_hr_payroll_formula`): both line
  producers are overridden from `pb_retro`, super() first, then
  `hr.payslip._pb_backpay_apply(fresh=True)` —
  `hr.payslip._create_payslip_lines_from_formulas` and
  `hr.payroll.import.batch._compute_and_create_payslip_lines`. Both delete
  every line before rebuilding, so a recompute replaces, never doubles.
  Nothing is fed to the formulas.
- Send for payment → pre-check per person (`pb.retro.person`: drift / error /
  left / moved / currency / no take-home line / already paid by another
  re-work → not paid automatically; no difference → skipped) → process
  `backpay`, one step Head of pay (seeded at install, migration 19.0.1.1.0,
  new companies) → on approval entries `pb.retro.backpay` from the stored
  result lines.
- Lines: one per pay item ("Back pay · Income tax · Aug–Oct 2026") with the
  item's own code, category, pay role and detail flag; the take-home
  difference is added to the payslip's one net line (`pb_backpay_net`).
- Band readers extended in `pb_retro` for payslips with back pay only: ORM
  `pb_pay_totals`, the run's SQL twin `_pb_slip_totals`, fund payments
  `_pb_read` (a back pay that LOWERS a deduction lowers the total), W2-A
  `_pb_history_read` (year-to-date counts it in the month paid), the themed
  payslip PDF ("Back pay for past months" block).
- Paid once (reserved / paid / released, FOR UPDATE), never below zero
  (whole months, rises first then cuts oldest first, the rest waits; one
  pass), Extra/top-up/no-run/earlier payslips never take it.
- Screen: Payment strip, "What happens next" follows the payment, board
  glance + filter "Waiting to be paid", Excel "Payment" sheet, review-flag
  note per payslip. vi + id (PO gate: 500 rows each, 0 empty, placeholders
  checked).

## Worked example (one person, three months)

Pay rise 44,000,000 → 50,000,000 from 1 August, entered after Aug–Oct were
paid (insurance base capped at 46,800,000; tax ladder 5/10/15/20 %).
Per past month: basic +6,000,000; insurance +294,000; income tax +1,141,200;
take-home +4,564,800; employer insurance +490,000. In November's regular pay
run: back-pay lines basic +18,000,000, insurance +882,000, tax +3,423,600,
employer +1,470,000; take-home 39,918,800 (November) + 13,694,400 =
53,613,200. Taxing the 18,000,000 as a November lump would have charged
3,600,000 — the back pay carries the past months' 3,423,600.

## 9. Draft ledger rows (to add when finished)

- W2D2-1: every take-home reader reads ONE net line (`pb_net_line()[:1]`); a
  second net-role line is never read — add to the net line instead.
- W2D2-2: band readers count deductions / employer cost by `abs()` per line,
  so a line that LOWERS them cannot be expressed; readers must be told
  (ORM, SQL twin, fund payments).
- W2D2-3: the themed PDF sums line totals by code (`dsal`): an extra line
  with an item's code merges into that item's printed figure.
- W2D2-4: `history.ytd/qtd/mtd` read `formula_computed_values`, not lines.
- W2D2-5: a second re-work of months already back-paid would measure from
  the stored payslip again and pay twice — guarded ('already').
- W2D2-6: `assertRaises` with a tuple fails in Odoo tests (W2M-2 again).
