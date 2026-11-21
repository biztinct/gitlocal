# WDGAP PR-D — An extra run: a bonus run, or one extra payslip for one person

Read first: `WDGAP_LEDGER.md`, then `WDGAP_PR1_FACTS.md` §A (bridge precedents and their
missing double-pay guard) and §2 "Bonus / off-cycle run / one person" (verified plumbing,
file:line — do not re-derive), then memory `two-schemes-one-month.md`,
`run-screen-scheme-field.md`, `payrun-screen-program.md`, `demo-world-payroll-figures-fixed.md`
and the tests `pb_payrun_wizard/tests/test_run_kind.py`, `test_two_schemes_one_month.py`,
`test_run_adopts_the_period.py`.

You are the implementer AND tester/self-reviewer. You do NOT deploy.

## 0. The honest shape of this feature

A scheme's formulas work out a person's WHOLE month. So "pay only a bonus" is done with a
scheme that only contains the bonus (and the tax on it). What is missing today is the
ability to run such a scheme — or any scheme — for a few chosen people, more than once in
a month, without touching the regular run (FACTS §2 "Running for ONE person today" a–d).

## 1. Scope (`pb_payruns`, `pb_payrun_wizard`, the two bridges, `pb_demo`)

1. **A third kind of run: "Extra run"** — `PB_RUN_KINDS` (`pb_payruns/models/hr_payslip_run.py:65`)
   gains `('extra', 'Extra run')`. On the Run payroll screen's first step
   (`pb_payrun_wizard/static/src/xml/payrun_wizard.xml:125-147`, js `:625-630`) the choice
   reads: Regular — "Everybody this scheme pays, once a month" · Top-up — (existing text) ·
   Extra run — "Only the people you pick. Use it for a bonus, a correction or one extra
   payslip. It never changes another run."
2. **People are picked, always**: for an Extra run the "Run for just a few people…"
   picker is shown regardless of the status filter (today only when `hasStatusFilter`,
   xml `:161,178`, js `:843,1101-1105`), at least one person is required, and
   `employee_ids` is always sent. People offered = those the chosen scheme may pay
   (`_scheme_population`, `pb_payrun_wizard.py:321`; `_eligible_employees` `:646`).
3. **Several in a month**: the duplicate guard `_period_runs(ds, de, config, kind)`
   (`:908-952`) never treats two Extra runs — or an Extra and a Regular/Top-up — as
   duplicates; an Extra run never offers Clean & Run of another run (`_clean_period`
   `:1046`, `_clean_blockers` `:132`) and never adopts loose payslips
   (`_adopt_loose_slips` `:1011`, as a top-up already does `:1021`). It requires a name
   (suggested: "Extra run — <scheme> — <date>"), and the run board shows a quiet
   "Extra run" tag like the top-up tag. "Compared with" (`pb_payruns.py:1053-1055`): an
   Extra run is compared with nothing (say "An extra run has nothing to compare with").
4. **Nothing is paid twice by an Extra run.** Values that are meant to be paid once per
   month must not flow into an Extra run automatically:
   - the trip bridge (`pb_trip_payroll_bridge/models/hr_payslip.py:15-74`) and the
     workforce bridge (`pb_workforce_payroll_bridge/models/hr_payslip.py:28-86`) feed
     ONLY `regular` runs (today they also re-feed a top-up — FACTS "Double-pay guard:
     none"; make them feed regular only and say so in the report as a behaviour change
     for top-ups, with the before/after);
   - `pb.updates.oneoff` and awards (`pb.oneoff.feed`) already have paid-once guards —
     verify by test that an Extra run in the same month cannot take an item a regular
     run has reserved or paid, and that an item explicitly waiting can be paid by an
     Extra run when no regular run has it (state what happens, do not change their logic);
   - attendance/leave/worked-days inputs are read as usual (the scheme decides whether it
     uses them).
   The first step shows one calm line: "An extra run works out everything this scheme
   contains for the people you pick. To pay only a bonus, pick a scheme that only
   contains the bonus."
5. **Approvals, bank file, payslips**: an Extra run follows the same route as the
   scheme's cycle type decides today (`_pb_kind_key`, `hr_payslip_run.py:812`) — no new
   process. Its bank file and payslip delivery work as for any finished run (do not edit
   `pb_pay_delivery`; verify by test/walk). The payslip PDF and My Payobook list show the
   run's name so an employee can tell the extra payslip from the monthly one (check what
   they show today; smallest change).
6. **Reports stay right**: totals that sum a month (Explorer facts, year-to-date sheet,
   tax summary) already sum finished payslips — confirm with one test that an Extra
   run's payslip is counted once in the month's totals, and note any report that assumes
   one payslip per person per month.
7. **Demo world**: `pb_demo/models/demo_payrun.py` overrides `get_defaults` `:197`,
   `prepare_run` `:289`, `compute_batch` `:409`, `create_and_compute` `:502` and ignores
   `employee_ids` on the division path — make the demo path honour `employee_ids` and the
   `extra` kind (kind handling at `:316,345,537,570`) so the feature can be shown on
   payobook.com, without changing any existing demo run's figures.

## 2. Binding non-goals

- No bonus-scheme template or wizard, no automatic tax true-up across runs, no change to
  formulas or the engine (`pb_hr_payroll_formula` untouched), no change to top-up
  semantics beyond the bridge fix in 4, no `pb_pay_delivery`/`pb_updates`/`pb_comp_ben`
  code changes, no `pb_pack_*`.

## 3. Safety rails

R1. Regular and top-up runs behave exactly as before except the documented bridge change
    for top-ups: `test_run_kind`, `test_two_schemes_one_month`,
    `test_run_adopts_the_period` stay green; add golden checks that a regular run's
    payslip lines for a fixture are identical before and after.
R2. An Extra run can never delete, clean, adopt or modify another run's payslips — test
    each path, including "Clean and Run" being unavailable.
R3. An Extra run with zero people is refused; with a person the scheme does not pay →
    plain refusal naming the person.
R4. The run kind can only change while draft (existing rule `:720-727`) — keep.
R5. Demo: all existing demo runs keep `pb_balance_ok` (recompute one per demo scheme
    before/after, compare lines); the demo Extra run for one person produces exactly one
    payslip.
R6. White-label, plain words; `vi_VN.po` (+ `id_ID.po` for `pb_payruns`); PO gate;
    version bumps.

## 4. Numbered test cases (T = Odoo test; write and run)

`pb_payrun_wizard/tests/test_wdgap_prd_extra_run.py` (+ bridge tests).
1. T `prepare_run` with `run_kind:'extra'`, two people → exactly two payslips; nobody else.
2. T Extra run while a finished Regular run exists for the same scheme and month → both
   exist; regular untouched (R2).
3. T Two Extra runs same scheme, same month → allowed; names required.
4. T Extra run with no people → refused; person outside the scheme → refused (R3).
5. T Clean & Run not offered / refused for Extra; loose slips not adopted.
6. T Bridges: approved overtime and per-diem feed a Regular run; do NOT feed an Extra
   run; do NOT feed a Top-up (document change); regular golden identical (R1).
7. T One-off (`pb.updates.oneoff`) reserved by a regular run is not taken by an Extra
   run; an unreserved one for that month is taken once (state the observed rule).
8. T Month totals count the Extra payslip once (scope 6).
9. T Demo path honours `employee_ids` and `extra`; demo regular run lines unchanged (R5).
10. T Existing suites: `pb_payrun_wizard` (all), `pb_payruns` (10 files), both bridges,
    `pb_demo` — failure set equals baseline.
11. Browser, local copy: Run payroll → Extra run → pick one DEMO person → compute →
    review → finish; the board shows the tag; the regular run for the month is unchanged;
    the person sees two payslips with different names on /my; console clean.
12. Static gates.

## 5. Working rules

- NEW git worktree from `origin/19.1` (after the QF merge is pushed), branch `wdgap-prd`.
- Feature-scoped commits, explicit paths; push. Do NOT merge. Do NOT deploy.
- Commit messages end with: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- Usage-limit error → WIP commit, "Where I stopped", PAUSED. Drop test databases.

## 6. Report back — `docs/handovers/wdgap/WDGAP_PR_D_REPORT.md` (commit it)

What was built; test table + suites vs baseline; self-review R1–R6; the top-up bridge
behaviour change in plain words (before/after, who could be affected); what an employee
sees; reports that assume one payslip per month; owner questions in plain words; deploy
notes (RISKY: pay run path); new gotchas → ledger.

Final message: under 250 words.
