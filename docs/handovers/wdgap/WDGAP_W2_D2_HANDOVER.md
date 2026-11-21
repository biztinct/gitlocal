# WDGAP W2-D2 — Pay a past-month difference as back-pay lines in this month's pay run

Read first: `WDGAP_WAVE_RULES.md`, `WDGAP_OWNER_RULINGS_2026-11-15.md` (R1, R2, C-6),
`WDGAP_LEDGER.md`, `WDGAP_W2_D1_REPORT.md` (origin/19.1 — especially "what D2 needs" and
the options table), `WDGAP_W2B_DEPLOY_REPORT.md`, `WDGAP_PR_B_REPORT.md` (loans: the
paid-once reservation pattern, never-below-zero pass from PR-E), `WDGAP_PR_D_REPORT.md`
(Extra run: what feeds regular runs only), `WDGAP_W2_A_REPORT.md` (year-to-date reads),
`WDGAP_W2_B_REPORT.md` (fund payments: owed amounts), memory `one-pay-band-rule.md`,
`feed-to-payslip-chain.md`, `valuekind-program.md`. Branch `wdgap-w2d2`, db prefix
`wdgap_w2d2_`. RISKY tier: this phase is ALLOWED to change payslip figures, only as
specified here.

## 1. What the owner decided

A worked-out re-work (`pb.retro.review`, live since 2026-11-15) shows per person, per
past month, per pay item: was / would be / difference. The owner wants that difference
PAID IN THIS MONTH'S PAY RUN as its own lines, carrying the exact tax and insurance
worked out for the past months — NOT re-taxed by this month's formulas. Past months stay
closed. Re-work sources stay as they are (contract amount changes + typed figures).

## 2. Scope (module `pb_retro`; smallest possible seam in the pay-run path)

1. **Send for payment.** On a worked-out re-work: "Pay the difference in the next pay
   run". Pre-checks per person, each with a calm plain reason when it fails: payslip
   "cannot be compared exactly" (baseline drift) → NOT payable automatically (list
   them; the pay team may still type a one-off in Updates); person has left or moved to
   another scheme/currency → not payable automatically; zero difference → skipped.
   State `worked out → waiting for approval → approved → paid (fully/partly) → closed`;
   withdraw allowed until a run has taken it.
2. **Approval.** New process key `backpay` in the one Approvals inbox, seeded ONE step:
   Head of pay (same seat as `loan`/`fundpay`; owner precedent "one sign-off"). Clone
   `pb_fund_payments`' wiring of `pb.money.approval.mixin`. The proposer may not approve
   their own (follow the mixin's existing independence setting per database — do not
   invent a new rule; rize has independence OFF by owner decision).
3. **Back-pay entries** `pb.retro.backpay` (one per person × pay item × source month,
   signed amount, currency, the review, state open/reserved/paid/cancelled, the payslip
   that took it). Created on approval from the STORED result lines — never recomputed
   later.
4. **Into the pay run.** The next REGULAR run of the same scheme (not top-up, not Extra —
   PR-D rule) picks up every open entry of its people and adds payslip lines:
   - one line per pay item with a difference, labelled "Back pay · <item name> ·
     <Aug–Oct 2026>" (months collapsed per item; the per-month detail stays on the
     entry and on the payslip's explain view);
   - each line carries the SAME pay role / band typing as the original item, so gross,
     deductions, employer cost and take-home read correctly through `pb_pay_totals`
     (one band reading), and the lines are FIXED amounts: this month's formulas neither
     see them as inputs nor re-tax them. Find the smallest seam that appends typed lines
     after formula evaluation and survives recompute (idempotent: recompute replaces,
     never doubles). If the engine has no such seam, add ONE narrowly-scoped hook in
     `pb_hr_payroll_formula` that `pb_retro` extends — report file/lines.
   - paid-once reservation exactly like loans/one-offs: reserved at compute, released
     when the payslip is deleted/reset or the run is reopened, marked paid when the run
     is finished.
   - **Never below zero take-home.** If the person OWES money (negative difference) and
     taking it all would push take-home below zero, take what fits and carry the rest to
     the next regular run (clone the PR-E loan pass; ONE extra pass, no loop). A back-pay
     set is taken per person all-or-fitting — never the tax part without its earning.
   - Runs with no open entries: byte-identical to today (golden test over the demo
     schemes' fixtures).
5. **Everything downstream reads the lines once.** Verify and test, fixing only inside
   `pb_retro` or by the reading's own extension points: payslip PDF and My Payobook
   payslip show a "Back pay for past months" block; year-to-date totals (W2-A) count
   them in the month PAID; fund payments' owed amounts (W2-B) include the back-pay tax
   and insurance lines under the right fund; bank file/take-home total includes the net
   effect; Pay & deliver "left out"/held/"paid another way" behave as for any payslip.
   Where a reader cannot include them without an out-of-lane edit, STOP that reader and
   report it.
6. **Screens.** Result view gains a "Payment" strip (waiting / approved / in run X /
   paid, per person with reasons for the not-payable ones); the pay-run review shows a
   calm chip "Includes back pay for 3 people" with a drill-in; the "What happens next"
   card text changes accordingly. Board glance: "Waiting to be paid". Excel export gains
   a Payment sheet. ⌘K unchanged.
7. **Undo.** Cancel an approved, not-yet-taken back pay (reason required). After a run
   took it: only by reopening that run through the normal path (entries go back to
   open). No raw deletes.

## 3. Rails

R1 golden: no entries → regular/top-up/extra payslips byte-identical. R2 paid once:
compute/recompute/reset/reopen/finish matrix. R3 sum of back-pay lines on payslips =
sum of approved entries per person, per item, per currency, always. R4 never two
currencies added; never crosses schemes. R5 take-home never below zero. R6 no formula,
`formula_program`, or stored past payslip is written. R7 portal employee sees only their
own back-pay lines. R8 silent on tenants: nothing appears until a re-work is approved.
R9 Extra/top-up runs never take entries. R10 determinism.

## 4. Tests (number them)

Each rail; positive and negative differences; progressive-tax example where the back-pay
tax differs from what this month's formula would charge (prove the past-month figure is
used); insurance-ceiling example; two people, one not payable (drift); person left;
approval route seed + migration on a database that already has `pb_retro`; reservation
matrix; carry-over of an owed amount; YTD, fund-owed, bank total, PDF block; rights.
Existing suites of `pb_retro`, `pb_hr_payroll_formula`, `pb_payruns`, `pb_payrun_wizard`,
`pb_loans`, `pb_fund_payments`, `pb_pay_delivery` — failure sets equal the recorded
baselines. Browser walk on a local copy: re-work → send → approve → run → payslip → PDF.

## 5. Report — `WDGAP_W2_D2_REPORT.md`

As in the wave rules, plus: the exact seam used to append lines and why it is safe; a
worked example a non-engineer can follow (one person, three months, the figures); what
the rehearsal on a rize copy should prove.
