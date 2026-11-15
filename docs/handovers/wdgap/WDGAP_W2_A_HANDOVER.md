# WDGAP W2-A — Running totals that follow the tax year (and are fast)

Read first: `WDGAP_LEDGER.md`, then `WDGAP_PR2_FACTS.md` §0 and §2 (verified plumbing,
file:line — do not re-derive; line numbers may have moved a little after PR-A, re-locate
by name), `docs/handovers/updates/UPDATES_LEDGER.md` (U42 "tax year is the calendar
year", D27 "not known, never a confident 0"), memory `feed-to-payslip-chain.md`,
`one-pay-band-rule.md`, `updates-desk-program.md`.

You are the implementer AND tester/self-reviewer. You do NOT deploy. Governing rule:
**with the default setting (tax year starts in January) no figure anywhere changes.**

White-label (binding): the word "Odoo" never appears in anything an end user can see.

## 0. Why

Year-to-date figures exist in three places and all hard-code the calendar year: the
engine's `history.ytd.<CODE>` source (application mode), the Updates desk year-to-date
sheet (`pb_updates/models/updates_ytd.py`), and the employee's tax sheet on My Payobook.
India (April–March) and any non-calendar tax year cannot be served. The engine source
also does one search per person.

## 1. Scope

1. **One setting, one helper.** `hr.formula.config` gains `tax_year_start_month`
   (Selection 1–12, label "Tax year starts in", default January, shown in the scheme's
   settings next to the cycle fields; changing it follows whatever approval the scheme's
   other settings follow today — find and mirror). One helper, in ONE place
   (`pb_hr_payroll_formula`), `tax_year_bounds(config, on_date) -> (first_day, last_day)`
   and `tax_year_label(config, on_date)` ("2026" for calendar, "2026–27" otherwise).
   Do NOT reuse the group's financial-year month (`pb_group.fiscal_start_month`): a
   company's books year and its tax year differ in several countries — but when a scheme
   is created by guided setup for a country pack, leave the default alone (no `pb_pack_*`
   change; ledger D2).
2. **Engine source** `history.ytd.<CODE>` (`application_domain_sources.py`
   `_application_history_value`): year start comes from the helper instead of
   `replace(month=1, day=1)`. Add siblings registered the same way: `history.qtd.<CODE>`
   (quarter of the TAX year) and `history.mtd.<CODE>` (earlier payslips in the same
   calendar month — relevant for extra/top-up runs). D27 behaviour, the no-gap rule and
   the catalogue wording pattern stay. An Extra or top-up payslip in the range counts
   once (it is a finished payslip like any other) — test with one.
3. **Fast**: replace the one-search-per-person read with one batch read per chunk,
   cached on the request memo (`_application_memo`), cloning the batch SQL precedent
   `_ledger(emp_ids, first, last, codes)` in `updates_ytd.py`. Same answers as the old
   reader for every person in a golden test (old function kept in the test as the oracle).
4. **Updates desk year-to-date sheet**: `_plan_for_slip` and the sheet's year choice use
   the helper for the scheme concerned; opening figures (`pb.updates.ytd.figure`) carry
   the tax-year label they belong to; existing rows (all calendar) keep meaning exactly
   what they mean today — migration sets nothing, the label is computed.
5. **My Payobook tax sheet** (`/my/taxsheet`): sums the employee's CURRENT tax year per
   the scheme of their most recent payslip, titled with the label ("Tax year 2026–27");
   a year switcher only if one exists today.
6. **Explorer / reports**: do not change; list in the report any report that says "year
   to date" and still means calendar year (owner follow-up).

## 2. Binding non-goals

No stored running-total table, no change to formulas/converter/function table, no
change to `pb_pack_*`, `pb_payruns`, `pb_payrun_wizard`, `pb_pay_delivery`, `pb_loans`
(another builder is in those), no tax true-up logic, no period-13.

## 3. Safety rails

R1. Default (January) → byte-identical results: golden tests for the engine source (old
    reader as oracle), the Updates sheet plan for a fixture, and the tax sheet totals.
R2. Changing the month on a scheme with finished payslips is allowed but warned in plain
    words ("Year-to-date figures for this scheme will be counted from April from now
    on. Finished payslips are not changed."). Nothing is recomputed.
R3. D27: unknown stays unknown — never a confident 0 because of the batch read.
R4. Per-currency: a running total never adds two currencies (scheme changes mid-year
    with another currency → treat as a gap per the existing rule; test).
R5. Multi-company and record rules respected by the batch SQL (company filter explicit).
R6. Demo recompute: one regular demo run per demo scheme identical before/after.
R7. Vietnamese for every new string (`vi_VN.po`; `id_ID.po` where present); PO gate;
    version bumps.

## 4. Tests (write and run; number them in the report)

Helper bounds for month 1, 4, 7 incl. leap years and a date before/after the start;
ytd/qtd/mtd values for an April–March scheme across the March/April boundary; extra-run
payslip counted once; gap → not known; batch = oracle for 60 people; Updates plan under
April start; tax sheet label and totals; R1 goldens; R2 warning; R4; R5; existing suites
of `pb_hr_payroll_formula`, `pb_updates`, `pb_me_portal` — failure set equals the
baselines in `WDGAP_PR_A_REPORT.md` / deploy report. Browser walk on a local copy: set a
demo scheme to April, read the warning, open the year-to-date sheet and the employee tax
sheet; console clean. Static gates.

## 5. Working rules

Branch `wdgap-w2a` from current `origin/19.1`, own worktree, feature-scoped commits,
explicit paths, push, no merge, no deploy, no live-server access. Disk is tight: one test
database at a time (prefix `wdgap_w2a_`), drop when done. Never wait silently on a
background run — poll with a bounded loop. Usage-limit error → WIP commit, "Where I
stopped", PAUSED. Commit messages end with:
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## 6. Report back — `docs/handovers/wdgap/WDGAP_W2_A_REPORT.md` (commit it)

What was built; test table vs baseline; R1/R6 proof; timing before/after for a 40-person
chunk; reports still on calendar year; owner questions in plain words; deploy notes
(RISKY: pay calculation inputs; new stored field); gotchas → ledger. Final message under
250 words.
