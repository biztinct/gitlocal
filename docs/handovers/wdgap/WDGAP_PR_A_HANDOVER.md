# WDGAP PR-A — Date functions that really work, and an honest function list

Read first: `WDGAP_LEDGER.md`, then `WDGAP_PR2_FACTS.md` §0–§1 and "Formula Studio UI"
(verified plumbing, file:line — do not re-derive), then
`docs/FORMULA_ENGINE_CONVENTIONS.md` (C5 codes, C12 one implementation in
`excel_semantics`, never inline) and memory `feed-to-payslip-chain.md`.

You are the implementer AND tester/self-reviewer. You do NOT deploy.
This phase changes the pay formula engine: the governing rule is **no existing payslip
figure may change**.

## 0. Why

The formula bar advertises YEAR, MONTH, DAY, TODAY, NOW, INT, IFS, LEFT… but the
converter maps none of them; a formula using one evaluates to **0 with no error on the
payslip** (FACTS §0 "What YEAR/MONTH/DAY/DATE actually do today"). Checked on live
2026-11-14: none of the 1,283 stored formulas on the five databases uses one — so this is
a trap, not yet a wrong payslip.

## 1. Scope

1. **Date functions** (Excel names and argument order; implemented ONCE in
   `excel_semantics`, reached from all three evaluation places — FACTS §0 "How a function
   is registered" and "Three places to evaluate"):
   `DATE(year, month, day)`, `YEAR(d)`, `MONTH(d)`, `DAY(d)`, `DAYS(end, start)`,
   `DATEDIF(start, end, "Y"|"M"|"D"|"YM"|"MD"|"YD")`, `EDATE(start, months)`,
   `EOMONTH(start, months)`. Also `INT(x)` (Excel: rounds DOWN toward −∞).
   - A date is an **Excel serial number** inside a formula (1900 system; the same number
     Excel shows) so a workbook formula gives the same answer. `DATE()` returns one;
     every date function accepts one.
   - A date **cell** (a component whose `value_kind` is `date`) is an ISO string that
     survives only in `raw_values` and is 0 in `values` (FACTS §0 "Types"). Inside the
     ARGUMENTS of a date function, a reference to a date-kind component is read from
     `raw_values` and turned into its serial — the same trick as the `ISBLANK` rewrite
     (`formula_rule.py:1442`). Outside a date function a date cell stays exactly what it
     is today (0). Do NOT add `date` to `NUMERIC_KINDS`, do NOT change `coerce_value`.
   - A blank or unreadable date inside a date function → the function returns 0 (Excel
     treats blank as 0 → year 1900; we return 0 so `IF(YEAR(x)=0, …)` is the documented
     blank test) — and never raises.
   - The pay period as dates needs no new codes: `DATE(PAYYEAR, PAYMONTH, ENDDAY)`
     (`pay_period.py:60` PERIOD_CODES). Put exactly this example in the help.
   - `TODAY()` and `NOW()` are **refused on save** with a plain sentence ("A payslip must
     give the same answer whenever it is worked out. Use the pay period instead, for
     example DATE(PAYYEAR, PAYMONTH, ENDDAY)."). They are removed from every list.
2. **One list of functions, everywhere.** Today three validators and two UI lists
   disagree (FACTS §0 "Validators disagree", "Formula Studio UI"). Make ONE table (name →
   helper, arity, one help line, example) the single source — clone the table-driven
   precedent `rule_formula.py:328` `_TABLE` — and derive from it: the converter's
   `function_map`, `validator.py:47` / `parser.py:72` `SUPPORTED_FUNCTIONS`, the
   hard-coded 16 names in `formula_rule.py:1943`, the formula bar list
   (`static/src/js/formula_bar.js:44`, served by an RPC or generated data — not a second
   hand-kept copy), autocomplete examples (`formula_autocomplete.js:106`), and the help
   data (`data/formula_functions_data.xml:57-63`). Everything the bar offers must work;
   remove IFS, LEFT/RIGHT/MID, COUNT, TODAY, NOW from the offer unless you implement them
   (do not implement them in this phase).
3. **Unknown function = refused on save**, in plain words naming the function and
   offering the nearest supported one — instead of today's "Invalid column reference" or
   a silent 0 at pay time. Applies to NEW saves/edits only; stored formulas are not
   re-validated or touched by the upgrade.
4. **The Studio's flowchart calculator** (`pb_formula_studio/static/src/js/formula_studio.js:3053`
   `evalNode`, where an unknown function returns its first argument): give it the same
   date functions (small pure-JS mirror with the SAME battery cases run in a JS test, or
   route preview through the server — choose the smaller change and say which).
5. **Reserved names.** A NEW component code may not equal a function name in the table
   (`formula_rule.py:2073` `_check_code_shape` / `component_code.py:253` `reserved=()`).
   Existing codes are left alone and keep working: the function patterns only match a
   name directly followed by `(` (FACTS §1 gotchas) — prove it with a test using a
   component coded `DAY` and one coded `ENDDAY`.

## 2. Binding non-goals

- No change to how any existing function, operator, IF/IFERROR laziness, rounding, text
  comparison or coercion behaves. No change to the silent-0 behaviour of runtime errors
  in general (report it as a follow-up with your recommendation).
- No new period codes, no running totals, no net-to-gross, no retro (later phases).
- No change to stored formulas, schemes, packs (`pb_pack_*`, ledger D2) or demo data.
- Do not edit `pb_payruns`, `pb_payrun_wizard`, `pb_pay_delivery`, `pb_updates`,
  `pb_demo` (other phases are in them).

## 3. Safety rails

R1. **Golden conversion test**: before changing anything, generate — from the UNCHANGED
    code — the converted Python for every formula found in the repo's data and demo
    catalogues (`pb_demo` catalogue formulas, `pb_pack_*` templates, country/demo data
    XML, test fixtures: collect them programmatically) and store them as a fixture. After
    your change, converting the same formulas must give byte-identical output. This is
    the proof that nothing existing moved.
R2. **Battery**: `python3 pb_hr_payroll_formula/tools/excel_semantics_battery.py` green,
    with a new case for every new function (C12), including: leap years, 1900-02-29
    serial quirk (match Excel: serial 60), month-end `EDATE`/`EOMONTH` (31 Jan + 1 month),
    negative months, `DATEDIF` each unit, `DAYS` negative, blank/garbage inputs → 0,
    `INT(-1.5) = -2`.
R3. **Same answer in all three evaluation places** (`_run_formula`, compiled
    `formula_program`, `evaluator.evaluate_single`): one parametrised test runs every
    battery date case through all three.
R4. `assert_safe_expression` (`excel_semantics.py:299`): the emitted helper names must
    not contain a blocked word; do not loosen the guard.
R5. **Demo runs still balance**: on a local copy with the demo world, recompute one
    regular demo run per demo scheme before and after and compare every payslip line
    (must be identical), and `pb_balance_ok` stays true.
R6. White-label, plain words; Vietnamese for every new string (`vi_VN.po` only — do not
    touch the stray `vi_VNnew*` files; PO parse gate). Version-bump modules touched.

## 4. Numbered test cases (T = automated; write and run)

`pb_hr_payroll_formula/tests/test_wdgap_pra_dates.py` (+ a JS/unit test for §1.4).
1. T Each function: Excel-verified values (take the expected numbers from the battery).
2. T A date-kind component inside `YEAR()`, `DATEDIF()`, `DAYS()` reads the ISO value;
   the same component outside a date function is still 0 (unchanged).
3. T Years of service: `DATEDIF(JOIN, DATE(PAYYEAR,PAYMONTH,ENDDAY), "Y")` for a joiner
   on 29 Feb, on the period end date, and one day after.
4. T `TODAY()` / `NOW()` refused on save with the plain sentence; unknown `FOO(` refused
   naming FOO; a stored formula containing `TODAY()` still loads and is not altered by upgrade.
5. T Function table is the single source: the converter map, both validators, the
   16-name strip and the RPC/list for the bar all contain exactly the same names.
6. T Reserved: new component code `YEAR` refused; existing-code simulation (`DAY`,
   `ENDDAY` as components) converts and evaluates as before.
7. T R1 golden conversion identical. 8. T R3 three-path equality. 9. R2 battery output.
10. T R5 demo recompute identical (may be a script run rather than a unit test — include
    its output in the report).
11. T Full suites of `pb_hr_payroll_formula` (60 files) and `pb_formula_studio`: failure
    set equal to the baseline on unchanged code (`-u` each, ledger G35).
12. Browser, local copy: in Formula Studio type a formula with `DATEDIF`, see it in the
    function list with its help, preview on a real person, try `TODAY()` and read the
    refusal; console clean.
13. Static gates: py_compile, XML, PO gate, "Odoo" grep on the diff.

## 5. Working rules

- NEW git worktree from `origin/19.1` (after the QF merge is pushed), branch `wdgap-pra`.
  Local test recipe: latest UPDATES reports + `WDGAP_QF*_REPORT.md` gotchas (disk is
  tight on this Mac: drop your test databases when done).
- Feature-scoped commits, explicit paths; push `wdgap-pra`. Do NOT merge. Do NOT deploy.
- Commit messages end with: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- Usage-limit error → one WIP commit, "Where I stopped" in the report, end with PAUSED.

## 6. Report back — `docs/handovers/wdgap/WDGAP_PR_A_REPORT.md` (commit it)

What was built; the function table; test table + full-suite counts vs baseline; R1/R5
proof outputs; decisions (JS mirror vs server); follow-ups (silent-0 runtime errors);
owner questions in plain words; deploy notes (tier RISKY — pay calculation; modules to
`-u`; asset purge yes); new gotchas → ledger.

Final message: under 250 words — branch, last commit, test counts, R1/R5 result,
deviations, owner questions.
