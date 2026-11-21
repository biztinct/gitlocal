# WDGAP W2-C — Work back from take-home ("net to gross")

Read first: `WDGAP_LEDGER.md`, then `WDGAP_PR2_FACTS.md` §0 and §3 (verified plumbing —
do not re-derive; re-locate by name if lines moved after PR-A), `WDGAP_PR_A_REPORT.md`
(function table, three evaluation places), memory `feed-to-payslip-chain.md`,
`one-pay-band-rule.md`, `formula-studio-toolbar.md`, `design-mandate.md`,
`contract-drawer-program.md`, `employee-drawer-detail-tabs.md`.

You are the implementer AND tester/self-reviewer. You do NOT deploy.
White-label (binding): the word "Odoo" never appears in anything an end user can see.

## 0. Why

Customers agree a take-home figure with a person ("12,000,000 net") and need the gross
that produces it under the scheme's own tax and insurance formulas. Nothing exists
(FACTS §3). This phase is a CALCULATOR: it never changes a payslip or a pay run by
itself.

## 1. Scope (`pb_formula_studio` server + UI; contract drawer entry)

1. **The solver** — one server method (pure, read-only, no writes, no savepoints
   needed): given a scheme, a person's input values (from a finished/draft payslip's
   stored inputs via the `preview_from_payslip` reading, or from the person's current
   contract values via the guided-setup sample reading), the pay item to change (one
   INPUT component, default: the scheme's base-pay input — find how the product
   identifies it; else the user picks) and a target take-home: find the value of that
   item for which the scheme's take-home equals the target.
   - Take-home is read the ONE way the product reads net (`pb_pay_totals`).
   - Method: build the compiled steps once (`config._pb_formula_steps(config.rule_ids)`),
     then `run_sample` per guess (FACTS "Fastest loop"). Bracket then bisect: start from
     [target, target×1.6], widen the upper bound ×2 up to 8 times until net(upper) ≥
     target; then bisect until |net − target| ≤ the currency's smallest unit or 60
     iterations; finally snap the answer to the currency's rounding and re-evaluate so
     the reported net is the REAL net of the reported gross.
   - Honest outcomes, each with a plain sentence: exact; "closest possible" (rounding or
     a tax step makes the exact figure unreachable — show both neighbours: gross G1 → net
     N1, gross G2 → net N2); "not possible" (net does not rise with this item / never
     reaches the target — e.g. the item is not in the net formula); "this scheme has a
     formula with an error" — the compiled path swallows errors to 0 (FACTS §3 gotcha),
     so before solving run ONE evaluation through the non-compiled path that reports
     errors (`_evaluate_rules_with_dependencies(..., errors=dict)`) and refuse if it
     reports any, naming the pay item.
   - Non-monotonic guard: sample 12 points across the bracket first; if net ever falls
     as the item rises, say so and return the lowest gross that reaches the target with
     a note, never loop.
   - Limits: 200 evaluations per request; pay-team groups only; company rule; the
     person's data never leaves the server beyond the figures shown.
2. **Where**
   a. Formula Studio real-pay preview: a "Work back from take-home" action beside the
      preview — target box, item picker, result card: "To take home 12,000,000, Basic
      pay must be 14,235,000", then the full payslip preview at that figure with the
      changed lines highlighted (gross, each tax/insurance line, employer cost).
   b. Contract drawer (the editable contract slide-over): beside the wage field a quiet
      "Work back from take-home" link opening the same card for that person and their
      scheme; "Use this amount" copies the figure into the wage field of the OPEN form
      (not saved until the user saves the contract the usual way, with whatever approval
      a wage change already needs). If the drawer cannot host it cleanly, ship (a) plus
      a ⌘K palette entry "Take-home calculator" (pick person → same card) and say so.
   c. Guided setup's example person: nothing in this phase.
3. **Several people at once**: no (later phase; report demand as an owner question).

## 2. Binding non-goals

No stored "net basis" contracts, no automatic gross-up inside a pay run, no tax-on-tax
component, no change to formulas, the converter, the function table, `formula_program`
or any other `pb_hr_payroll_formula` code (another builder is in that module — if you
truly need a hook there, add ONE small additive method in a new file and say so
prominently), no `pb_pack_*`, no pay-run modules.

## 3. Safety rails

R1. Read-only: a test asserts no row of any model is created/written by a solve
    (compare `write_date`/counts on payslip, contract, inputs).
R2. The reported gross, fed back through the normal preview, gives the reported net —
    asserted for every test case (no "solver's own arithmetic").
R3. Terminates: bounded iterations; a formula that returns garbage → refusal, never a
    hang (test with a deliberately non-monotonic and a constant-net scheme).
R4. Rounding per the currency with the Excel-style helpers (C12; no Python `round()` on
    money); VND has no decimals, USD two.
R5. Rights: pay team only; a person outside the user's companies refused.
R6. Demo world untouched; `vi_VN.po` for new strings; PO gate; version bump.

## 4. Tests (write and run; number them in the report)

Flat-rate scheme (closed-form expected value); progressive-tax scheme with caps
(insurance ceiling) — verify by forward evaluation; target on a tax-step boundary →
"closest possible" with both neighbours; item not in net → "not possible"; errored
formula → refusal naming it; non-monotonic → note; iteration cap; R1; R2 on all cases;
two currencies; rights. One case on each demo scheme of the demo world using a real demo
payslip's inputs (forward-check only). Existing suites of `pb_formula_studio` — failure
set equals the baseline in `WDGAP_PR_A_REPORT.md`. Browser walk on a local copy: Studio
preview → work back → result + highlighted payslip; contract drawer link → "Use this
amount" fills the field, nothing saved until Save; console clean. Static gates.

## 5. Working rules

Branch `wdgap-w2c` from current `origin/19.1`, own worktree, feature-scoped commits,
explicit paths, push, no merge, no deploy, no live-server access. Disk is tight: one test
database at a time (prefix `wdgap_w2c_`), drop when done. Never wait silently on a
background run — poll with a bounded loop. Usage-limit error → WIP commit, "Where I
stopped", PAUSED. Commit messages end with:
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## 6. Report back — `docs/handovers/wdgap/WDGAP_W2_C_REPORT.md` (commit it)

What was built and where it is reached; solver outcomes table; test table vs baseline;
R1–R6; timing per solve on a demo scheme; owner questions in plain words (several
people at once? a "net basis" contract later?); deploy notes; gotchas → ledger. Final
message under 250 words.
