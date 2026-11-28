# WDGAP W2-D1 — Re-work a past month: see exactly what would change (no money moves)

Read first: `WDGAP_LEDGER.md`, then `WDGAP_PR2_FACTS.md` §0, §3 ("ways to compute one
person without writing anything") and §4 "Retro" (verified plumbing — do not re-derive;
re-locate by name where lines moved), `WDGAP_W2_C_REPORT.md` (the read-only evaluation
path and the separate formula-error check it had to write — reuse it, do not write a
third), `WDGAP_PR_A_REPORT.md` (three evaluation places), memory
`feed-to-payslip-chain.md`, `one-pay-band-rule.md`, `valuekind-program.md`,
`multi-scheme-currency-gaps.md`, `payobook-cockpit-pattern.md`, `quiet-board-pattern.md`,
`design-mandate.md`.

You are the implementer AND tester/self-reviewer. You do NOT deploy.
White-label (binding): the word "Odoo" never appears in anything an end user can see.

## 0. Why, and why two phases

Today "retro" only pro-rates a contract-amount change into ONE input on the uploaded-file
path; it never re-runs the earlier month's formulas, so tax and insurance on the
difference are whatever this month's formulas make of it (FACTS §4). The owner wants
true re-working of past months. Phase D1 (this one) builds the engine of that — re-work
a finished payslip with today's data and show the difference line by line — and STOPS
before any money: nothing is posted to a pay run. Phase D2 (later, after the owner has
seen real differences) decides how differences are paid. D1 must therefore be exact,
read-only and explainable.

## 1. Scope — new module `pb_retro` ("Payobook Past-Month Re-work")

Depends on `pb_hr_payroll_formula`, `pb_payruns`, `pb_hub`, `pb_formula_studio` only if
the reusable read-only evaluation helper lives there (prefer calling it over copying).
No edits inside other modules.

1. **A re-work** `pb.retro.review`: company, scheme, months covered (from–to, finished
   regular runs only in D1; Extra/top-up payslips of those months are listed as "not
   re-worked" in the result), people (all in those runs, or picked), reason (required),
   state `draft → worked out → closed` (+ `cancelled`), who/when. No approval in D1 (it
   moves nothing).
2. **Working it out** — for each finished payslip in scope:
   a. take the payslip's STORED inputs (`formula_input_values` — what the month was
      actually computed from) as the base;
   b. overlay ONLY the values that have changed since, from an explicit, listed set of
      sources, each shown to the user as "what changed": contract amount changes
      effective in or before that month that were entered AFTER the payslip was computed
      (`hr.contract.advantage.change` — the existing retro source; clone
      `_prepare_retro_adjustments`'s reading but with Excel-style rounding, C12), and
      a manual "what if" grid where the pay team types a corrected input value for a
      person and month (with a note). Nothing else is re-read (attendance, leave, feeds:
      D2 or later — list them in the report with what each would need);
   c. evaluate the scheme AS IT WAS FOR THAT MONTH if the product keeps scheme versions
      per run (find out: is the formula set of a finished run recoverable? If not, D1
      evaluates with the CURRENT scheme and says so in a clear banner on the result:
      "Worked out with today's version of the scheme") — report which is true;
   d. read-only evaluation (same path as the take-home calculator; assert nothing is
      written to payslips, lines, inputs, reservations — loans and one-offs must NOT be
      reserved or re-consumed: feed the loan/one-off inputs exactly as the stored inputs
      had them);
   e. compare with the STORED payslip lines, per pay item: was / would be / difference;
      roll up per person and per month into gross, each deduction, take-home and
      employer cost using the one band reading (`pb_pay_totals`), per currency.
   Sanity gate per payslip: re-evaluating with NO overlay must reproduce the stored
   lines; where it does not (the scheme or data moved since), the payslip is marked
   "cannot be compared exactly" with the items that differ at baseline, and its
   differences are shown net of that baseline drift, clearly labelled. (On payobook the
   stored demo figures are known not to reproduce — the tool must say this calmly, not
   fail.)
3. **Result lines** `pb.retro.line` (stored snapshot: person, month, pay item, was,
   would be, difference, currency, the cause — which overlay rows drove it), so the
   result is stable and exportable even if data changes later; "Work out again" replaces
   the snapshot while draft/worked-out.
4. **Screen** "Past-month re-work" (cockpit pattern, quiet, filter kit, Lucide): list of
   re-works; a guided "New re-work" (scheme → months → people → what changed, with the
   detected contract changes pre-listed and the what-if grid); result view: per person a
   was/would-be/difference table by month, totals per currency on a glance strip
   ("Take-home +4,200,000 across 3 people · Tax +310,000 · Insurance +150,000 · Employer
   cost +5,100,000"), drill to the payslip, Excel export (one block per currency), and a
   plain "What happens next" card: "Nothing has been paid or changed. To pay a
   difference today, add it as a one-off in Updates" (link if `pb_updates` is installed —
   probe, no dependency).
5. **Reach**: ⌘K palette entry and a Payroll hub lens if it takes a client action
   cleanly (test inside the hub).
6. **Rights**: pay team manager groups (mirror who may reopen/approve a pay run);
   company rule; chunked working-out (40 payslips per request like the run driver) with
   a progress bar; cap 12 months × 500 people per re-work.

## 2. Binding non-goals

No posting to any pay run, no retro components, no change to the existing
`hr.payroll.retro.adjustment` flow or `use_auto_retro`, no reopening of runs, no change
to formulas/engine/`formula_program`, no `pb_pack_*`, no demo data, no cron.

## 3. Safety rails

R1. Read-only towards payroll: counts and `write_date` of payslips, lines, inputs, loan
    repayment lines, one-off reservations identical before/after a full working-out.
R2. Baseline honesty: the sanity gate above; a difference is never reported without the
    baseline check for that payslip.
R3. Deterministic: working out twice gives identical lines.
R4. Never adds two currencies. C12 rounding helpers only.
R5. Silent install on every tenant (module-sync rule): empty board, one palette entry.
R6. A formula that errors → that payslip is listed as "could not be worked out" naming
    the pay item; the rest continue.
R7. `vi_VN.po` + `id_ID.po`; PO gate; white-label grep.

## 4. Tests (write and run; number them in the report)

No-overlay re-evaluation reproduces stored lines on a fixture; contract change effective
two months back → per-month differences equal a hand-computed forward evaluation, incl.
progressive tax and an insurance ceiling; what-if grid value; baseline drift labelled;
errored formula isolated; loans/one-offs untouched (R1); Extra-run payslip listed as not
re-worked; two currencies; rights/company; determinism; caps; export; silent install.
Existing suites of `pb_hr_payroll_formula` retro tests and `pb_formula_studio` — failure
sets equal recorded baselines. Browser walk on a local copy (small demo set is fine —
disk): new re-work for two people over two months with a what-if value, result, export;
console clean. Static gates.

## 5. Working rules

Branch `wdgap-w2d1` from current `origin/19.1`, own worktree, feature-scoped commits,
explicit paths, push, no merge, no deploy, no live-server access. Another builder is in
`pb_payrun_wizard`, `pb_fund_payments`, `pb_formula_studio` (views/panel only) — do not
edit those. Disk is tight: one test database at a time (prefix `wdgap_w2d1_`), drop when
done. Never wait silently on a background run — poll with a bounded loop. Usage-limit
error → WIP commit, "Where I stopped", PAUSED. Commit messages end with:
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## 6. Report back — `docs/handovers/wdgap/WDGAP_W2_D1_REPORT.md` (commit it)

What was built; whether a past run's scheme version is recoverable (2c) and what the
banner says; test table vs baseline; R1–R7; timing per 40 payslips; what D2 needs
(per source: attendance, leave, feeds; and the options for paying differences, each with
its consequence for tax and fund totals) — written so the orchestrator can turn it into
one plain owner question; deploy notes; gotchas → ledger. Final message under 250 words.
