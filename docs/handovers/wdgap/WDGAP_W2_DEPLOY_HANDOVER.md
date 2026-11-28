# WDGAP W2 — merge, go live ×5, verify (PR-E, W2-A, W2-B, W2-C)

This step follows EXACTLY the method of `WDGAP_PR_DEPLOY_HANDOVER.md` (copy it into your
worktree from `/Users/adity/Documents/GitHub/gitlocal/docs/handovers/wdgap/` if it is not
in `origin/19.1`) and the command sequence proven in `WDGAP_PR_DEPLOY_REPORT.md`. Read
both first, then `WDGAP_LEDGER.md` and the four phase reports ("Deploy notes" + gotchas):
`WDGAP_PR_E_REPORT.md` (`origin/wdgap-pre` bc803e58d), `WDGAP_W2_A_REPORT.md`
(`origin/wdgap-w2a` a7659ae0a), `WDGAP_W2_B_REPORT.md` (`origin/wdgap-w2b` d9ec49bde, NEW
module `pb_fund_payments`), `WDGAP_W2_C_REPORT.md` (`origin/wdgap-w2c` 7026cf618).
Everything below is what DIFFERS from the PR step.

Databases: `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima` only. RISKY tier.
White-label: the word "Odoo" never in anything an end user can see. Commit messages end
with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## 1. Merge (branch `wdgap-w2-merge` from `origin/19.1`; order: w2a, pre, w2c, w2b)

Expected conflicts: ledger (UNION), `.po` headers. W2-A edited `pb_hr_payroll_formula`,
`pb_updates`, `pb_me_portal`; PR-E edited the pay-run modules, `pb_pay_delivery`,
`pb_loans`; W2-C `pb_formula_studio` (+ contract drawer); W2-B is a new module. Any real
code conflict: stop and report.

Seams to check by reading and by a test on the merged tree:
a. W2-B owed amounts include a payslip marked "paid another way" (PR-E) and an Extra-run
   payslip; a held payslip still counts.
b. W2-A year-to-date / month-to-date with a loan instalment that PR-E cut: totals read
   the reduced amount actually on the payslip.
c. W2-C calculator on a person with a running loan: the loan input is taken as the
   payslip had it (no second reduction pass inside the solver, no reservation touched —
   re-assert "nothing written").
d. W2-A's deliberate change (an Extra/top-up payslip no longer breaks the year-to-date
   chain; it counts once) holds together with PR-D's Extra run on the merged tree.

Small fixes to make on the merge branch (each with a test, noted in the report):
F1. **Pay & deliver opens for every pay-team member after a release** (PR-E report,
    owner question 3: another pay-team member gets an access error because they cannot
    read who approved the release). Fix with the smallest read path that lets the pay
    team (the groups that may open Pay & deliver) see the approver's name and time —
    not wider than that; no change to who may approve.
F2. **W2-C vs demo schemes**: the W2-C report says both "all 12 demo schemes work" and
    "the two VPTQ demo schemes have no take-home line marked". Establish which is true on
    the demo world; if the calculator cannot work on a scheme it must say so plainly
    (it should already) — do not change demo data; report the fact.
F3. **"Tax year starts in" on the Formula Studio scheme panel** (W2-A question 2): add the
    field there only if the panel already lists the neighbouring cycle fields and it is a
    one-line view change; otherwise leave and report.
Not to fix here (report as owner questions): Extra run + pay data file still nets the
mid-month advance again (flag only); the older offer calculator in Formula Studio shows
no earnings/deductions boxes on live.

Combined gates and combined local run as in the PR step (install `pb_fund_payments`;
the four phases' new tests together; full suites of touched modules — failure set equals
the union of recorded baselines). W2-A could not recompute the demo world locally (disk):
do the before/after demo recompute in the REHEARSAL on the live server instead (below).
Disk on the Mac: one test database at a time; remove leftover `wdgap_pre_*`/`wdgap_w2*`
databases (list first). Never wait silently on a background run — poll it with a bounded
loop (the previous deploy stalled 7 hours this way). Update the ledger phase map; push to
`origin 19.1` (never force; merge it in first if it moved and re-run the gates).

## 2. Read-only live checks before anything changes (report each number)

As in the PR step (deploy notes, disk, cron snapshot incl. job 156 OFF on payobook and
the 8 template jobs), plus:
a. W2-A: per database, schemes by `tax_year_start_month` cannot exist yet — instead count
   schemes whose company country is India (owner question: April start?) and finished
   Extra/top-up payslips this calendar year per database (the year-to-date chain change
   applies to those people; list counts, do not block).
b. PR-E: per database, loans in state running (expected 0) and bank files released
   (expected 0) — if either is non-zero say so prominently; do not block.
c. W2-B: which databases have all dependencies of `pb_fund_payments` installed (install
   there; skip and report elsewhere). Confirm after install: no payee, no payment row,
   no new job, no email queued; one new approval rule "Fund and tax payments" — report
   who it routes to on each database and whether any step has nobody in the seat.
d. Loan approval seat: on `payobook`, "SG Company" has nobody to approve loans — put the
   DEMO person who already holds the equivalent seat for another payobook demo company
   into it if that is a plain seat assignment (demo database only, keep-demo-data rule:
   add, never delete); otherwise report. Do not touch any other database's seats.

## 3. Go live

Same RISKY sequence as the PR step, with the rehearsal on a copy of `rize` AND a copy of
`payobook` (jobs + mail off first): on the payobook copy recompute one finished regular
demo run per demo scheme with the OLD trees and again with the NEW trees in rolled-back
transactions — the two must be identical line for line (they need not equal the stored
demo figures; that mismatch is pre-existing and documented); on the rize copy recompute
the most recent finished regular run old vs new — identical. Any difference: do NOT go
live; report scheme, person, line, both figures.

## 4. Check on the real system (payobook.com, QA login; look-only where it would email
the owner or a real person)

Funds & tax board opens empty and tidy from Payroll and ⌘K; Suggest funds on a demo
company (then remove what you created, or leave clearly DEMO-named rows only if removal
is not clean — say which). Take-home calculator from Formula Studio on a demo person and
from a demo contract panel (do not save). Scheme settings show "Tax year starts in" =
January (do not change). Pay & deliver of a demo run shows the "left out" list with "Paid
another way" (do not mark anyone on a real tenant). Run payroll → Extra run step shows
the file line if a file scheme exists on demo (stop before computing). Loans board opens.
Then the cheap checks on the other four sites.

## 5. Report — `docs/handovers/wdgap/WDGAP_W2_DEPLOY_REPORT.md` (commit + push)

Merge + seams a–d + fixes F1–F3; combined test counts; §2 numbers; rehearsal proof;
versions before → after ×5; downtime; verification; the walk; anything held; owner
questions as plain real-world questions (carry forward the builders' open ones); new
gotchas → ledger. Final message under 300 words. Usage-limit error mid-deploy: finish
the database you are on, START the service, write DONE/FAILED, then PAUSED.
