# WDGAP PR-E — three owner rulings on the pay-run extras (2026-11-15)

Read first: `WDGAP_LEDGER.md` (conventions, gotchas incl. PRM-1..3), then the reports
that hold the verified plumbing for the code you will touch — do not re-derive:
`WDGAP_PR_D_REPORT.md` (Extra run), `WDGAP_PR_C_REPORT.md` (hold pay, who is marked
paid, follow-up file), `WDGAP_PR_B_REPORT.md` (`pb_loans`: reservation seam, flags),
`WDGAP_PR_DEPLOY_REPORT.md` (the Extra-run/pay-data-file finding on rize; seam tests),
`WDGAP_PR1_FACTS.md`. All are in `origin/19.1`.

You are the implementer AND tester/self-reviewer. You do NOT deploy. One branch
`wdgap-pre` from current `origin/19.1`, three feature-scoped commits (E1, E2, E3).

White-label (binding): the word "Odoo" never appears in anything an end user can see.
Plain words on screen. Vietnamese (`vi_VN.po`) for every new string, Indonesian
(`id_ID.po`) where the module already has one; PO parse gate; version bumps.

## E1 — An Extra run that loads a pay data file keeps only the people picked

Owner ruling: "The file can still be loaded, but the Extra run keeps only the rows of
the people you picked."
- Today (deploy report): with a scheme that asks for a pay data file, loading the file
  into an Extra run gives EVERYONE in the file a payslip. Find the exact place the file's
  rows become payslips/people for the run (pay-data-file batch transform / the wizard's
  file step) and filter to the run's picked people when `pb_run_kind == 'extra'`.
- The screen says what happened in one calm line: "This file has 214 people. This extra
  run keeps the 3 you picked." A picked person who is NOT in the file → named in a plain
  warning before computing (not silently given an empty payslip; follow what the regular
  path does for a person missing from the file and say which).
- Regular and top-up runs: byte-identical behaviour (golden test with the same file).
- Values that are once-a-month in the file (mid-month advance netting, loan amounts): the
  PR-D report raised that an Extra run with a file could take the advance again. State in
  the report what now happens for a picked person, with a test; if the advance would be
  netted a second time, do not redesign carry-over — add a review flag on the Extra run
  ("This file also takes the mid-month advance; check it has not been taken already")
  and report it as an owner question.
- Demo path (`pb_demo` overrides) must keep working; demo regular run figures unchanged.

## E2 — "Paid another way" (cash, cheque, separate transfer)

Owner ruling: add the button; lifting a hold stays one-person (no change there).
- In Pay & deliver, for a finished payslip that is NOT paid, NOT on hold and not in a
  released file (typically the "left out" list: no bank details, etc.): action "Paid
  another way" with a required method (Cash / Cheque / Other bank transfer / Other) and a
  required note (min 6 characters), optional date (default today, never in the future).
  It stamps the paid date and stores `pb_paid_method`, `pb_paid_note`, `pb_paid_by` on
  the payslip, writes a chatter line (and audit entry if PR-C found a one-call entry
  point), and the person leaves the "still to pay" total. Undo ("Not paid after all",
  with a reason) is allowed only for a payslip marked this way, never for one paid by a
  released bank file.
- Same pay-team groups as hold/release. Works for several people at once from the
  left-out list (one method/note for the selection; cap 50).
- Such a payslip can never afterwards enter a bank file or a follow-up file (test), and
  cannot be put on hold (already paid — existing rule R2 covers it; test).
- Totals on Pay & deliver gain "paid another way" beside paid / on hold / still to pay,
  per currency; the identity of PR-C R4 becomes: released files + paid another way +
  on hold + still to pay = run total (extend the test).
- The run shows as fully paid once nobody is "still to pay" (find what drives the run's
  paid state today — PR-C report — and make this path satisfy it).
- Payslip delivery: a payslip paid another way is delivered like any paid payslip.
- With nobody marked this way everything is identical to today (golden).

## E3 — A loan instalment never takes take-home below zero

Owner ruling: "Take what fits, move the rest to next month."
- Today: instalment > net → flag only, full amount taken, net may go negative.
- New: after the payslip is worked out with the planned instalment, if the scheme's
  take-home (read it the ONE way the product reads net — `pb_pay_totals`, memory
  `one-pay-band-rule`) is below zero, the instalment is reduced by the shortfall (to not
  less than zero), rounded per currency in the person's favour, the reservation line is
  updated to the reduced amount under the same lock, and the payslip is worked out once
  more. One extra pass at most; if after the second pass net is still below zero (other
  deductions), leave it and keep the existing flag wording for that case. Never loop.
- The untaken part simply stays in the balance: the plan runs longer (months left grows);
  nothing else is created. With "take the rest from the final pay" in the leaving month
  the same cap applies and what cannot be taken stays owed (existing "listed as owed").
- Several loans: reduce the newest loan's instalment first, then the next (state the
  order on the flag).
- Flag wording on the payslip review: "Loan instalment cut from 1,200,000 to 450,000 so
  take-home is not below zero · 6,750,000 left". The Loans drawer history shows the
  smaller amount for that month with the same reason.
- Both input paths (regular and pay-data-file) and application-data mode; when the file
  carries its own loan amount the existing "file wins, instalment skipped" rule stays.
- Safety: paid-once (R1), never more than owed (R2), derived balance (R3) and "never
  raise into the pay run" (R4) of PR-B all still hold — keep their tests green and add:
  recompute of the same payslip gives the same reduced amount (idempotent); deleting the
  payslip releases the reduced reservation; a person with no loan is computed exactly
  once as before (no second pass — assert by counting).
- Performance: the second pass happens only for payslips that have an instalment AND a
  negative net. Demo recompute identical; no loans exist on any live database today.

## Non-goals

No general net-pay floor for other deductions, no arrears engine, no second-person
approval for lifting a hold, no change to bank file layouts, formulas, the engine
internals or `pb_pack_*`.

## Tests (write and run; numbered in the report)

E1: extra+file keeps picked only; picked-but-absent warned; regular/top-up golden; demo.
E2: mark, undo, bulk, rights, cannot enter a file / be held, totals identity per
currency, run fully paid, delivery, golden with none. E3: cut to zero net, partial cut,
two loans order, leaving month, idempotent recompute, release on delete, no second pass
without a loan, file path, application mode. Existing suites of every touched module:
failure set equals the baselines recorded in the PR reports. Browser walk on a local copy
with the demo world for each of the three (console clean). Static gates.

Local test rules: disk is tight — one test database at a time (prefix `wdgap_pre_`),
drop when done. Never wait silently on a background run: poll it with a bounded loop.
Usage-limit error → WIP commit, "Where I stopped", PAUSED.
Commit messages end with: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Report back — `docs/handovers/wdgap/WDGAP_PR_E_REPORT.md` (commit it), push `wdgap-pre`

What was built per item; test table vs baseline; what an Extra run with a file does with
the mid-month advance; deploy notes (RISKY: pay run + money-out path; new stored fields);
owner questions in plain words; new gotchas → ledger. Final message under 250 words.
