# WDGAP W2-F — owner rulings and leftovers after round W2 (2026-11-15)

Read first: `WDGAP_LEDGER.md`, `WDGAP_W2_DEPLOY_REPORT.md` (findings F2/F3, live
numbers, approval seats on payobook), and for the code you touch the reports that hold
the verified plumbing — do not re-derive: `WDGAP_PR_E_REPORT.md` (Extra run + pay data
file, the advance flag), `WDGAP_PR_D_REPORT.md`, `WDGAP_W2_B_REPORT.md`
(`pb_fund_payments`: Suggest, approval seed), `WDGAP_W2_A_REPORT.md` (tax-year field),
`WDGAP_W2_C_REPORT.md` (the older offer calculator finding). All in `origin/19.1`.

You are the implementer AND tester/self-reviewer. You do NOT deploy and do NOT touch the
live server. Branch `wdgap-w2f` from current `origin/19.1`; one commit per item.
White-label (binding): the word "Odoo" never appears in anything an end user can see.
`vi_VN.po` (+ `id_ID.po` where the module has one) for every new/changed string; PO
gate; version bumps.

## F-1 — An Extra run never takes the mid-month advance a second time (owner ruling)

Ruling: "An Extra run ignores the advance from the file when the month's regular run
already took it, and says so on screen."
- Today (PR-E): Extra run + pay data file nets the mid-month advance again for the picked
  people; only a review flag. Find how the advance reaches a payslip (pay-data-file
  column(s) mapped to the advance input and/or `payroll_cycle_carryover`; PR1 FACTS §A
  and the PR-E report name the path).
- New rule, per picked person: if a FINISHED or COMPUTED regular (or mid-month-cycle
  carry-over consuming) payslip of the same scheme family and pay month already carries
  that advance deduction, the Extra run feeds 0 for the advance input(s) and records why;
  if no regular payslip has taken it, behaviour is unchanged (the Extra run may be the
  one that takes it — state this in the report).
- Screen: before computing, one calm line — "The mid-month advance was already taken in
  <run name> for 3 of the people picked. This extra run will not take it again." On the
  payslip review the flag becomes informational: "Advance not taken again (already in
  <run name>)". Remove the old warning flag for those cases; keep it where the rule could
  not decide (say why).
- Identification of "the advance input" must come from how the scheme/cycle already
  types it (carry-over setting / component typing) — never from a hard-coded code. If a
  scheme has no such typing, nothing changes and the old flag stays.
- Regular/top-up runs: byte-identical (golden). Demo recompute identical.
- Tests: taken-before → 0 fed + line + info flag; not-taken-before → unchanged; scheme
  without typing → unchanged + old flag; recompute idempotent; regular golden.

## F-2 — Fund payments: one sign-off to start with (owner ruling)

- The seeded default route for process `fundpay` becomes ONE step: Head of pay (the same
  seat `pb_loans` uses). New installs get it from the seed.
- Existing databases: a migration (module version bump) rewrites the route ONLY where it
  is still exactly the seeded two-step route and no fund payment has ever been sent for
  approval; otherwise it is left alone. Test both branches.

## F-3 — "Suggest" leaves out things that are not funds

- `pb_fund_payments` Suggest must not offer loan repayments, the mid-month advance or
  any other non-statutory deduction as a fund. Use the components' own typing (the
  authoritative attribute W2-B chose) plus: the scheme's "Loan repayments go into"
  component (`pb_loans` setting, probe-style — no hard dependency) and the advance typing
  from F-1 are always excluded. Remove the "untick these" note. Test with a scheme that
  has a loan input and an advance.

## F-4 — "Tax year starts in" on the Formula Studio scheme panel

- Add the field as its own row in the Studio's scheme panel (W2 deploy report F3: there
  is no cycle field beside it, so it is a new row), same label, same change warning and
  the same approval path as on the scheme form. Browser check.

## F-5 — The older offer calculator in Formula Studio shows no earnings/deductions boxes

- W2-C report "Found, not fixed". Reproduce on a local copy, find the cause, fix with the
  smallest change (likely a reading that expects rule categories — reports must read
  `pay_role` / `pb_pay_totals`, memory `one-pay-band-rule`, `valuekind-program`). If the
  cause is demo-data typing rather than code, do NOT change demo data: report it.

## Non-goals

No change to carry-over design beyond the F-1 read, no new approval processes, no
`pb_pack_*`, no formula engine internals, no retro work (separate phase).

## Tests and rules

Tests per item as listed; existing suites of every touched module — failure set equals
the baselines in the W2 reports; browser walk on a local copy for F-1, F-3, F-4, F-5
(console clean); static gates. Disk is tight: one test database at a time (prefix
`wdgap_w2f_`), drop when done. Never wait silently on a background run — poll with a
bounded loop. Usage-limit error → WIP commit, "Where I stopped", PAUSED. Commit messages
end with: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Report — `docs/handovers/wdgap/WDGAP_W2_F_REPORT.md` (commit), push `wdgap-w2f`

Per item: what changed, tests vs baseline, deviations; deploy notes (F-1 touches the pay
run path → rehearsal applies; F-2 migration); owner questions in plain words; gotchas →
ledger. Final message under 250 words.
