# WDGAP W2 second go-live — merge, go live ×5, verify (W2-F, W2-D1)

Method: EXACTLY as `WDGAP_W2_DEPLOY_HANDOVER.md` / `WDGAP_PR_DEPLOY_HANDOVER.md` and the
command sequence proven in `WDGAP_W2_DEPLOY_REPORT.md` (all in `origin/19.1`). Read
those, `WDGAP_LEDGER.md`, and the two phase reports: `WDGAP_W2_F_REPORT.md`
(`origin/wdgap-w2f` 27b28cc1f) and `WDGAP_W2_D1_REPORT.md` (`origin/wdgap-w2d1`
d515295bf, NEW module `pb_retro`). Only the differences are written here.

Databases: `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima` only. RISKY tier
(W2-F touches the pay run path in the payroll engine module; new module install).
White-label: the word "Odoo" never in anything an end user can see. Commit messages end
with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## 1. Merge (branch `wdgap-w2b-merge` from `origin/19.1`; order: w2f, w2d1)

Expected conflicts: ledger (UNION), `.po` headers. Seams (test on the merged tree):
a. `pb_retro` re-working a month that contains an Extra-run payslip whose advance was
   NOT taken again (W2-F F-1): the Extra payslip is listed "not re-worked"; the regular
   payslip's stored advance input is fed unchanged; nothing written.
b. `pb_retro` palette/lens and W2-F's Formula Studio Health-tab row both load in one
   assets bundle (browser smoke on the local copy, console clean).
Combined gates; combined local run (install `pb_retro`; the two phases' new tests
together; full suites of touched modules — failure set equals the union of recorded
baselines). Disk: one test database at a time; remove leftover `wdgap_w2f_*` /
`wdgap_w2d1_*` databases (list first). Never wait silently on a background run — poll
with a bounded loop. Ledger phase map; push to `origin 19.1` (never force).

## 2. Rehearsal — LIGHTER, by owner agreement (2026-11-15)

- `rize` copy: FULL old-vs-new recompute of finished regular runs as last time (it took
  minutes) — must be identical line for line.
- `payobook` copy: a SAMPLE only — per demo scheme the most recent finished regular run,
  first 20 payslips, old vs new — identical. Do not recompute whole demo runs.
- Both copies: jobs + mail off before the live service can touch them; `dropdb --force`
  after. Any difference → do NOT go live; report scheme, person, line, both figures.

## 3. Read-only live checks before anything changes

As before (deploy notes — another deployer may have an open START; disk; cron snapshot
with job 156 OFF on payobook and the 8 template jobs), plus:
a. `fundpay` route per database: still the seeded two-step and never used? (expected
   yes ×5 → the migration switches all five to one step, Head of pay). Report what each
   became after the upgrade and whether the seat has a holder.
b. `rize` scheme 7119 `RIZE_IN_FOCUSED_2026` has `tax_year_start_month = '4'` (owner
   decision, set by hand on 2026-11-15) — must still be '4' after the upgrade.
c. `pb_retro` dependencies installed ×5 → install everywhere; after install: no rows, no
   job, no email queued.

## 4. Go live — same RISKY sequence. Then two DEMO-only data tasks on `payobook`

Owner rulings 2026-11-15 ("a demo person approves on the demo site"; payobook database
ONLY; keep-demo-data rule: add or re-assign seats, delete nothing; no other database):
D-1. Approval seats: for every demo company on `payobook`, the seats that the `loan` and
     `fundpay` routes resolve to (Head of pay, and any other step on those two routes)
     must be held by a DEMO person, not the owner's own account, and "SG Company" must
     have a holder. Use the demo person who already holds a comparable pay seat in that
     company (or in a sibling demo company if none). Do this through the product's own
     seat-assignment model/method in an odoo shell (not raw SQL), record before → after
     for each seat in the report and in `/opt/deploy-notes.md` (so it can be undone).
     Do not change who approves pay runs, bank files or anything else.
D-2. On each of the 12 demo schemes set "Loan repayments go into" to the scheme's loan
     repayment input (the W2-F report names it; demo precedent `INLOAN`). Only where the
     scheme has exactly one obvious such input; otherwise leave and list. Then confirm
     Suggest no longer offers "Loan Repayment" on a demo company. Recompute nothing.
     Record before → after.
If either task cannot be done cleanly through the product's own methods: do not force
it; report what is needed.

## 5. Check on the real system (payobook.com, QA login; look-only where it would email a
real person)

Past months screen opens empty from Payroll and ⌘K; start a re-work for two DEMO people
over one month with one what-if value, see the result and the banner, then cancel/delete
it if deletion is clean (else leave it clearly named DEMO and say so). Funds & tax →
Suggest on a demo company: no loan/advance rows. Formula Studio Health tab shows "Tax
year starts in" (do not change). Offer calculator shows Earnings and Deductions boxes.
Run payroll → Extra run step still loads (stop before computing). Then the cheap checks
on the other four sites.

## 6. Report — `docs/handovers/wdgap/WDGAP_W2B_DEPLOY_REPORT.md` (commit + push)

Merge + seams; combined test counts; §3 numbers; rehearsal proof and how long it took;
versions before → after ×5; downtime; verification; D-1/D-2 before → after; the walk;
anything held; owner questions as plain real-world questions (carry forward: how a
past-month difference should be paid — copy the comparison table from the W2-D1 report
in plain words; whether attendance/leave should also be re-checked); gotchas → ledger.
Final message under 300 words. Usage-limit error mid-deploy: finish the database you are
on, START the service, write DONE/FAILED, then PAUSED.
