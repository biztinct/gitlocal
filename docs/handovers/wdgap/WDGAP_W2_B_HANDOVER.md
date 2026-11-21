# WDGAP W2-B — Payments to funds and tax offices: what is owed, what was paid, the proof

Read first: `WDGAP_LEDGER.md`, then `WDGAP_PR2_FACTS.md` §5 (verified plumbing — do not
re-derive; re-locate by name if lines moved), `WDGAP_PR_C_REPORT.md` (money-out records
and the shared approval base), the APPROVAL MATRIX closeout and memory
`approval-matrix-program.md`, `payobook-cockpit-pattern.md`, `quiet-board-pattern.md`,
`design-mandate.md`, `payobook-design-system.md`, `multi-scheme-currency-gaps.md`,
`one-pay-band-rule.md`, `valuekind-program.md` (reports read `pay_role`, never the rule
category).

You are the implementer AND tester/self-reviewer. You do NOT deploy.
White-label (binding): the word "Odoo" never appears in anything an end user can see.

## 0. Why

After a pay run the company owes money to social-insurance funds, health funds, pension
funds and the tax office. Payobook shows contribution figures for the latest run only
(`pb_statutory`, hard-coded Vietnam codes) and keeps no record that anything was paid.

## 1. Scope — new module `pb_fund_payments` ("Payobook Fund & Tax Payments")

Depends on `pb_pay_delivery` (for `pb.money.approval.mixin`), `pb_payruns`,
`pb_approval_config`, `pb_hub`. No edits inside those modules.

1. **Who we pay** `pb.fund.payee`: name (e.g. "Social insurance office", "Tax office"),
   company, currency, which pay items belong to it — a many2many to the scheme's
   components (`hr.formula.rule`), each line marked `employee share` / `employer share`
   (so the amount owed = employee deductions + employer contributions of those items),
   usual due day ("by day N of the following month"), bank details/reference text (free
   text, shown for the person making the payment; never a bank file in this phase).
   A "Suggest" action proposes payees and items from the components' own typing
   (`pay_role` / statutory flags as the product already types them — find the one
   authoritative attribute; do NOT hard-code country codes, do NOT read `pb_pack_*`).
2. **What is owed** `pb.fund.payment`: payee, pay month (or the runs it covers), amount
   owed = sum of the chosen items on FINISHED payslips of that month for that company
   (all run kinds incl. Extra runs; payslips on hold still count — the contribution is
   owed), split employee/employer, head-count, currency; state `to pay → waiting for
   approval → approved → paid` (+ `cancelled`); paid on, payment reference, evidence
   attachment (receipt), paid amount (may differ: a difference needs a note), late flag
   from the due day. Created by a "Work out what we owe for <month>" action on the board
   (idempotent: re-running updates `to pay` rows, never touches approved/paid ones; if
   payslips changed after approval the row shows a quiet "figures changed since
   approval: +1,250,000" chip rather than changing itself).
3. **Approval**: process key `fundpay` (area Payroll, `money=True`, never bulk),
   adapter on `pb.money.approval.mixin` cloned from `pb.payment.release`; default route
   seeded like the release route. Appears in the one Approvals inbox with payee, month,
   amount, head-count.
4. **Board** "Fund & tax payments" (cockpit pattern, quiet chips, filter kit, Lucide
   icons, month switcher): one row per payee per month — owed, paid, difference, due
   date, state; a drawer with the per-item breakdown, the people count, the payslip
   lines behind the figure (drill to a list), evidence, history. Reach: ⌘K palette entry
   and a lens in the Payroll hub if it takes a client action cleanly (test inside the
   hub — memory `filter-program` hub-lens no-scroll trap).
5. **A run flag / Home nudge**: none in this phase except one line on the board's glance
   strip ("2 payments are past their due date").
6. **Export**: the board's month to Excel (one block per currency).
7. **Rights**: pay team (mirror the groups that may prepare a bank file); company rule.

## 2. Binding non-goals

No bank file or electronic filing, no statutory return formats (that is `pb_govt_reports`),
no change to `pb_statutory`'s display, no accounting entries, no country tables, no
demo data shipped (the board must look good empty), no cron.

## 3. Safety rails

R1. Amount owed is DERIVED from payslip lines; no write path types it (paid amount and
    note are the only human figures).
R2. Never adds two currencies; one payment row per payee per month per currency.
R3. Approved/paid rows are immutable except by a "Reopen" that needs a reason and goes
    back through approval; an evidence file is required to mark paid.
R4. Idempotent "work out": running it twice creates nothing new; a unique index on
    (payee, month, currency) among live rows.
R5. New module on every tenant (module-sync rule): install must be silent — no data, no
    job, no email, nothing visible beyond the empty board and palette entry.
R6. Reads payslip lines through the same reading the reports use (pay_role / the
    component link), and matches the run's own totals for a fixture where the payee
    holds every deduction item (identity test).
R7. `vi_VN.po` and `id_ID.po`; PO gate; white-label grep.

## 4. Tests (write and run; number them in the report)

Payee suggestion from typed components; owed = employee + employer shares for a fixture;
Extra-run payslip included; held payslip included; two currencies → two rows; work-out
twice idempotent; figures-changed chip after a recompute post-approval; approval flow,
not bulk; mark paid needs evidence; difference needs a note; late flag; reopen; rights
and company rule; export; R6 identity; install on a database without demo data is
silent. Existing suites `pb_pay_delivery`, `pb_approval_config` — failure sets equal the
recorded baselines. Browser walk on a local copy with the demo world: set up two payees
with Suggest, work out a month, approve in the inbox, mark paid with a receipt; console
clean. Static gates.

## 5. Working rules

Branch `wdgap-w2b` from current `origin/19.1`, own worktree, feature-scoped commits,
explicit paths, push, no merge, no deploy, no live-server access. Disk is tight: one test
database at a time (prefix `wdgap_w2b_`), drop when done. Never wait silently on a
background run — poll with a bounded loop. Usage-limit error → WIP commit, "Where I
stopped", PAUSED. Commit messages end with:
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## 6. Report back — `docs/handovers/wdgap/WDGAP_W2_B_REPORT.md` (commit it)

What was built; how a customer sets it up in three steps (plain words); test table vs
baseline; R1–R7; owner questions in plain words; deploy notes (RISKY: new module ×5);
gotchas → ledger. Final message under 250 words.
