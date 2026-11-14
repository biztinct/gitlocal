# WDGAP PR-B — Loans and salary advances with a running balance

Read first: `WDGAP_LEDGER.md`, then `WDGAP_PR1_FACTS.md` §A, §1, "Full & final",
"Employee self-service", "Approvals" (verified plumbing, file:line — do not re-derive),
then `docs/handovers/updates/UPDATES_LEDGER.md` (the one-off paid-once design, D11, U21),
`docs/FORMULA_ENGINE_CONVENTIONS.md` C5, memory `feed-to-payslip-chain.md`,
`one-pay-band-rule.md`, `two-schemes-one-month.md`.

You are the implementer AND tester/self-reviewer. You do NOT deploy. This phase takes
money out of people's pay: **never twice, never more than is owed, never silently**.

## 1. Scope — new module `pb_loans` ("Payobook Loans & Advances")

Depends on: `pb_hr_payroll_formula`, `pb_payruns`, `pb_approval_config`, `pb_hub`,
`pb_me_portal` (portal card; if that dependency is wrong for tenants without the portal,
split the card into an auto-install bridge `pb_me_loans` like `pb_me_expense`).

1. **The record** `pb.loan`: person, company, kind (`Loan` / `Salary advance`), amount,
   currency (the person's pay currency), reason, first pay month, repayment plan (either
   "amount each month" or "number of months" — the other is worked out; last instalment
   takes the remainder), `on_leaving` (`Take the rest from the final pay` default /
   `Leave it open`), state `draft → waiting → running → paused → closed` (+ `cancelled`,
   `refused`). Computed: repaid so far, **balance**, next instalment, months left.
   Lines `pb.loan.repayment`: pay month, amount, payslip, state
   `reserved / paid / released`, kind (`payroll` / `manual` — HR can record a repayment
   made outside payroll, with a reason and reference).
2. **Approval**: new process key `loan` (area People, `money=True`) in
   `pb_approval_config`-style data shipped by `pb_loans`; adapter cloned from
   `pb_comp_ben/models/incentive_approval.py`. Approved → `running`. Seeds a default route
   like the awards one. It appears in the one Approvals inbox (and is NOT bulk-approvable —
   it is a money process).
3. **The pay run takes the instalment — once.** Clone the paid-once machinery of
   `pb.updates.oneoff` (`pb_updates/models/updates_oneoff.py:316-442, 741-775`;
   seams `updates_payrun.py:82, 264`; token wrapper `:166, :184`): reserve when the slip
   is computed, mark paid when the slip is done/paid, release when the slip or run is
   cancelled, deleted or recomputed without it.
   - Both input paths: the regular path (`hr.payslip._get_formula_input_values`, call
     `super()` first, forward `provenance`) AND the pay-data-file batch transform.
   - Application-data mode: register a typed source `loans.instalment` through
     `_application_source_catalogue()` / `_application_domain_values()`
     (`application_payroll_source.py:337, 356`), cloned from the awards source
     (`application_domain_sources.py:444-475`) with `consumption_required=True`.
   - **Which pay item**: a new setting on the scheme (`hr.formula.config`), "Loan
     repayments go into" → one of the scheme's INPUT components. The instalment is fed as
     a positive number into that input; the scheme's own formula decides the sign
     (precedent: demo `LOANREP = -INLOAN`). No setting → nothing is fed, and see 5.
   - Only `regular` runs (`pb_run_kind`), only the scheme the person is paid by for that
     month; one instalment per loan per pay month whatever happens (unique index on
     loan + month among live lines). A top-up or any other kind of run never takes one.
   - Instalment = min(plan amount, balance). Several loans → the sum, each with its own line.
   - `paused`: skipped that month (HR pauses with a reason; the plan shifts by a month).
4. **Leaving**: when the pay period contains the person's last working day
   (`hr.employee.departure_date`) and `on_leaving` is "take the rest", the instalment for
   that month is the whole balance. If the balance is still above zero after the final
   payslip is done, the loan stays `running` and is listed as owed (see 5) — it never
   silently closes. Do not write into `hr.full.final.settlement`; its `c_loan` already
   picks up payslip components coded LOAN/ADV/TAMUNG (FACTS "Full & final") — report what
   a customer must name the component for that to show.
5. **Nothing silent — the run tells you.** A review flag on the pay run (clone
   `pb_payslip_review/models/review_flags.py:49` flags, zero-pay precedent `:132`):
   "3 people have a loan instalment due but this scheme has no pay item for loan
   repayments", and per slip "Loan instalment 1,200,000 taken · 6,000,000 left". If the
   instalment is larger than the person's net pay for the month the slip is flagged
   ("Loan instalment is more than this month's take-home") — the amount is NOT changed
   (net-pay protection is a later phase; report it).
6. **Closes itself** when the balance reaches zero (state `closed`, chatter line).
7. **Screens**: a Loans board for the pay team — list with quiet chips (Running, Waiting
   for approval, Paused, Closed), balance bar, filter panel (`pb_filter_kit`), a side
   drawer with the plan, the repayment history and actions (Pause, Resume, Record a
   repayment made outside payroll, Settle now, Cancel — each with a reason). "New loan"
   as a short guided form. Reach: ⌘K palette entry + a Payroll hub lens if `PAY_LENSES`
   (`pb_comp_ben/static/src/js/comp_ben_palette.js:43-60`) takes a client action cleanly
   (test inside the hub); follow the cockpit pattern (memory `payobook-cockpit-pattern`,
   `quiet-board-pattern`, design mandate in the ledger).
8. **My Payobook**: a "My loans" card/page (read-only): what I borrowed, what is left,
   what comes off next month, history. Portal rules per TIERS (sudo after ownership guard;
   no portal ACL on `pb.loan`).
9. **Rights**: pay team (`group_payroll_base_officer`/manager — check which groups the
   awards screens use and mirror them) create and manage; employees read only their own
   through the portal method; company record rule.

## 2. Binding non-goals

- No interest, no payroll tax treatment of loan benefit, no net-pay floor/arrears, no
  employee self-request (later), no bank payment of the loan itself (paying the money OUT
  is outside this phase — the loan starts as "given"), no change to mid-month advance
  schemes/carry-over (`payroll_cycle_carryover` — its double-netting risk is noted for a
  later phase), no change to `pb_demo`'s demo `hr.loan`, no `pb_pack_*` change.
- Do not edit `pb_payrun_wizard`, `pb_pay_delivery`, `pb_updates`, `pb_hr_payroll_formula`
  internals (extend through the declared seams only), `pb_approval_config` code.

## 3. Safety rails

R1. **Paid once**: unique partial index (loan, pay month) on live repayment lines;
    reservation tied to the slip; recompute of the same slip reuses its reservation;
    a second regular run for the same person and month (another scheme, or Clean & Run)
    cannot take it again; cancelling/deleting the slip or run releases it and the balance
    comes back. Clone the token logic — do not invent a new one.
R2. **Never more than owed**: instalment ≤ balance at reservation time under a row lock
    on the loan (`FOR UPDATE`); manual repayment larger than the balance refused.
R3. **Balance is derived**, never typed: amount − sum(paid lines). No write path sets it.
R4. The seam overrides never raise into the pay run for a loan problem: a loan that
    cannot be applied produces a flag and is skipped, the run continues (log + flag).
R5. Application mode and regular mode both covered by tests; `pb_updates`' own one-offs
    keep working beside loans in the same slip (test together).
R6. Money fields use the currency; totals never add two currencies
    (memory `multi-scheme-currency-gaps`). Rounding per the currency, Excel-style helpers
    (C12 — no Python `round()` on money).
R7. New module install is a RISKY deploy; `pb_tenants` module-sync rule means every
    tenant gets it — no demo data, no cron unless needed (none needed), nothing shown to
    customers who have no loans beyond an empty, well-designed board.
R8. White-label, plain words ("loan", "salary advance", "instalment", "left to repay"),
    Lucide icons; `vi_VN.po` and `id_ID.po` for the new module (both; the pay team at
    Rize Indonesia will read it). PO parse gate.

## 4. Numbered test cases (T = Odoo test; write and run)

`pb_loans/tests/…`, tagged.
1. T Plan maths: by amount, by months, remainder on the last instalment, currency rounding.
2. T Approval: waiting → approved → running; refused; not in `can_bulk`.
3. T Regular run takes one instalment into the configured input; payslip line shows the
   deduction via the scheme formula; balance drops only when the slip is DONE; while the
   slip is draft the line is `reserved`.
4. T Recompute same slip → still one line; delete slip → released; cancel run → released.
5. T Second regular run same month (other scheme / Clean & Run) → not taken twice.
6. T Top-up run → nothing taken.
7. T Two loans → two lines, one summed input. Paused → skipped. Closed at zero.
8. T Leaving month with "take the rest" → whole balance; with "leave it open" → normal.
9. T Scheme without the setting → nothing fed + run flag; instalment > net → slip flag.
10. T Application-data mode: source offered, consumption required, reservation honoured.
11. T Pay-data-file path: same result as the regular path for the same person.
12. T With a `pb.updates.oneoff` for the same person and month → both applied once.
13. T Rights: employee cannot read another's loan; portal method returns only own; other
    company hidden.
14. T Manual repayment and "Settle now" update the balance; over-payment refused.
15. T Existing suites of `pb_hr_payroll_formula` (period input, application source),
    `pb_updates`, `pb_payruns`, `pb_payslip_review` — failure set equals baseline.
16. Browser, local copy: create a loan, approve it in the inbox, run payroll for the
    person, see the flag and the balance, finish the run, see My loans on /my; console
    clean; phone width for the portal page.
17. Static gates: py_compile, XML, PO gate, "Odoo" grep.

## 5. Working rules

- NEW git worktree from `origin/19.1` (after the QF merge is pushed), branch `wdgap-prb`.
- Feature-scoped commits, explicit paths; push. Do NOT merge. Do NOT deploy.
- Commit messages end with: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- Usage-limit error → one WIP commit, "Where I stopped", PAUSED. Drop test databases.

## 6. Report back — `docs/handovers/wdgap/WDGAP_PR_B_REPORT.md` (commit it)

What was built; test table + suites vs baseline; self-review R1–R8; how a customer sets
it up in three steps (plain words, for the owner); what the F&F screen shows and what the
component must be named; follow-ups (net-pay floor, self-request, paying the loan out);
owner questions in plain words; deploy notes (RISKY: new module install ×5, backups,
rehearsal); new gotchas → ledger.

Final message: under 250 words.
