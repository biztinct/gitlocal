# WDGAP PR-A — report: date functions that really work, and one honest function list

Branch `wdgap-pra` (from `origin/19.1` at `d3fba29ea`). Not merged, not deployed.
Modules: `pb_hr_payroll_formula` 19.0.1.165.0 → **19.0.1.166.0**, `pb_formula_studio`
19.0.1.211.0 → **19.0.1.212.0**. Nothing else touched (no `pb_pack_*`, `pb_payruns`,
`pb_payrun_wizard`, `pb_pay_delivery`, `pb_updates`, `pb_demo`).

Commits: `10c8b5486` R1 golden fixture (taken BEFORE any change) · `93847bcd7` engine ·
`fcd090e44` Studio · `5c91f63dc` test fixes · `e5a9f4607` help-line fix from the walk
(JS only; after the full-suite run) · this report + ledger.

## 1. What was built

1. **One function table** — `pb_hr_payroll_formula/formula_engine/functions.py` `_TABLE`
   (clone of `rule_formula._TABLE`): name, kind, emitted helper, min/max values, category,
   signature, one help line (lazy-translated), example. Derived from it:
   - the converter's `function_map` (`converter_function_map()`; the first 25 rows are the
     old hand-written map in the same order, so the regex pass is byte-identical);
   - `FormulaValidator.SUPPORTED_FUNCTIONS` and `FormulaParser.SUPPORTED_FUNCTIONS`;
   - the rule-level `validate_formula` strip (was 16 hard-coded names; now every called name
     is removed before references are read, and functions are judged by the table);
   - the save-time check `functions.problems()` → `hr.formula.rule._pb_formula_refusal()`;
   - the list RPC `hr.formula.rule.pb_formula_functions()` → Formula Studio component editor
     palette ("All functions", grouped, help line per function, a live help line for the
     function being typed) and the (unbundled) old `formula_bar.js` / `formula_autocomplete.js`;
   - the developer note in `data/formula_functions_data.xml` (now a pointer, not a copy).
2. **Date functions + INT**, implemented once in `excel_semantics` (C12) and reached through
   one-line delegates on `hr.formula.rule` and `FormulaEvaluator` (the compiled program reaches
   them through `self`): `excel_date/year/month/day/days/datedif/edate/eomonth/int`,
   `to_serial`, `date_operand`. Dates are Excel 1900 serials (serial 60 = Excel's phantom
   29 Feb 1900). Blank/unreadable/out-of-range → 0, never raises.
3. **Date cells inside date functions**: a converter post-pass
   (`_read_dates_in_date_arguments`) wraps every `values.get('X', 0)` inside the argument span
   of a date helper as `self._dateval(values.get('X', 0), raw_values.get('X'))`. Outside date
   functions nothing changes (a date component still reads 0). `NUMERIC_KINDS` and
   `coerce_value` untouched.
4. **Refused on save** (plain words, vi translated): TODAY()/NOW() with the handover's
   sentence; an unknown name, naming it and offering the nearest (`FOO` → "Did you mean
   FLOOR?"); a known function with the wrong number of values. Applied in the Studio's
   `save_formula`, `save_component` and `bulk_save_formulas` (only when the formula CHANGED),
   and in the live check (`validate_formula_live` / `_check_formula`), the scheme's
   "Validate All" and the rule's `validate_formula`. Stored formulas are never re-checked;
   no migration.
5. **Reserved codes**: a NEW component may not be coded like a function
   (`_pb_refuse_function_codes` on create, rename refused in `write`); the generators
   (`build_component_code`, `normalize_code`) never mint one. A code some component already
   carries (a copied scheme, a scheme made before PR-A) passes. The converter leaves a NEW
   function name followed by "(" alone even when a component has that code
   (`functions.NEW_IN_PRA`), so `DAY(…)+DAY` works with a component coded DAY.
6. **Studio flowchart calculator**: parser + evaluator moved unchanged from
   `formula_studio.js` into the self-contained `static/src/js/formula_flow_eval.js`, plus the
   date functions (pure-JS mirror). Decision: **JS mirror**, not server routing — the
   flowchart shows a value on every node, so routing would need a per-node RPC (larger
   change). One display fix rode along: a text value outside a date function now reads 0
   (as in the engine) instead of being glued on as text ("2024-01-15" + 1 = "2024-01-151").

## 2. The function table

| Kind | Names |
|---|---|
| numbers | SUM, AVERAGE, MIN, MAX, ABS, ROUND, COUNTA, POWER, SQRT, CEILING, FLOOR, SUMIF, SUMIFS, ROW, SUBTOTAL, MOD, SIGN, ROUNDUP, ROUNDDOWN, **INT** |
| conditions | IF, IFERROR, ISBLANK, AND, OR, NOT, TRUE, FALSE |
| dates (new) | **DATE, YEAR, MONTH, DAY, DAYS, DATEDIF, EDATE, EOMONTH** |
| look up (special passes) | VLOOKUP (same-scheme column), BRACKET (band tables) |
| refused on save | TODAY, NOW |
| no longer offered (never computed) | IFS, LEFT, RIGHT, MID, LEN, UPPER, LOWER, TRIM, CONCATENATE, HLOOKUP, INDEX, MATCH, CHOOSE, COUNT, COUNTIF, AVERAGEIF |

Help for DATE carries the handover's example: `DATE(PAYYEAR, PAYMONTH, ENDDAY)`.

## 3. Tests

Local: one database at a time. `wdgap_pra_t` = copy of `upd_p6_t_tpl` (vi + id installed),
brought to `origin/19.1` with the 24 modules that were behind; the baseline run used the
two modules exported from `d3fba29ea` first in the addons path, the PR-A run the worktree.
Dropped afterwards (filestore too). Port 8961, crons off, mail servers removed.

| # | Case | Where | Result |
|---|---|---|---|
| 1 | Every function, Excel values (72 shared cases: leap years, serial 60 = 29 Feb 1900, 31 Jan + 1 month, negative months, every DATEDIF unit, DAYS negative, blank/garbage → 0, INT(-1.5) = -2) | `tools/date_function_cases.json` via `test_wdgap_pra_dates` test_01_08 | PASS |
| 2 | A date component inside YEAR/DATEDIF/DAYS reads the date; alone (or in arithmetic) still 0 | test_02 | PASS |
| 3 | Years of service: 29-Feb joiner (4 at 29 Feb 2024, 4 at 28 Feb 2025), joined on the period-end date (1), one day after (0) | test_03 | PASS |
| 4 | TODAY()/NOW() refused with the sentence; FOO( refused naming FOO + "Did you mean FLOOR?"; wrong arity; quoted text ignored; no "Invalid column reference" for functions; a stored `=TODAY()` loads, renames, converts unchanged (computes 0) | test_04, test_04b; Studio `test_wdgap_pra_studio` 01–04 | PASS |
| 5 | One source: converter map ∪ special passes = validator set = parser set = RPC list = table; every listed function converts, passes the save check and is never a column reference | test_05; Studio test_05 | PASS |
| 6 | New code YEAR refused (with suggestion), rename to MONTH refused, existing DAY kept on write, a copied scheme with DAY copies, generators never mint DATE/DAY/…; `ENDDAY+DAY` and `DAY(DATE(…))+DAY` evaluate as before | test_06, test_06b; Studio test_06 | PASS |
| 7 | R1 golden conversion (inside Odoo, real model) | test_07 | PASS |
| 8 | R3: every case equal in `_run_formula`, compiled `formula_program.run_sample`, `FormulaEvaluator.evaluate_single` | test_01_08 | PASS |
| 9 | R2 battery | `python3 pb_hr_payroll_formula/tools/excel_semantics_battery.py` | **ALL GREEN**: primary 142/142 (70 old + 72 date), secondary 79/79 (8 old + 71 date; TODAY() left out there — evaluate_single raises by design, evaluate_all records 0) |
| JS | Studio flowchart mirror, same cases | `node pb_formula_studio/tools/date_functions_battery.mjs` (also run by test_09) | 66 PASS, 0 fail, 6 engine-only (component-code) cases skipped |
| 10 | R5 demo recompute | §4 | see §4 |
| 11 | Full suites `/pb_hr_payroll_formula,/pb_formula_studio`, `-u` both | log `scratchpad/pra/logs/{base_tests,new_tests2}.log` | baseline **1215 tests, 11 failed, 1 error**; PR-A **1231 tests, 11 failed, 1 error — the identical 12** (TestRd49SyncCost ×2, TestRecordsR1OneTime 07b, TestSchemeCtxCurrency 04, TestJourneyView ×2, TestNetPayCandidates 01, TestOneMappingHome ×4, TestRunsrcPcBoardLane 14 — all fail on unchanged code too) |
| 12 | Browser | §5 | see §5 |
| 13 | Static gates | py_compile (13 files) OK; studio.xml / data XML parse OK; `node --check` on 4 JS files OK; PO gate (Odoo `PoFileReader`) OK on both `vi_VN.po` (4,030 / 2,545 rows); "Odoo" in added user-visible text: none | PASS |

Also run: `tests/test_formula_string_literals.py` 21/21, `tests/test_component_code.py`,
`tests/test_dependency_order.py`, `tools/cell_refs_battery.py` 20/20, `tools/if_chain_battery.py`
18/18 — green. `tools/import_resolution_battery.py` (ImportError) and
`tools/provenance_battery.py` (2 failures) fail identically on unchanged code.

Two existing tests needed changing, both because the wording/rule changed by design:
`test_formula_string_literals` test_15 expected "Unsupported function: XLOOKUP" (now
"XLOOKUP is not a function formulas can use. Did you mean VLOOKUP?"), and
`pb_formula_studio/tests/test_payslip_document.py` created a NEW component coded `DAYS`
(now refused) — its fixture uses `WORKDAYS`.

## R1 proof

`python3 pb_hr_payroll_formula/tools/wdgap_golden_conversion.py` — fixture written from the
UNCHANGED converter in the first commit (`10c8b5486`), before any engine change:

```
NEW-FUNCTION pb_hr_payroll_formula/tests/test_value_kind_classifier.py
  formula: =DATE(2026,1,1)
  before : DATE(2026,1,1)
  after  : self._date(2026,1,1)
R1 golden conversion: 536 formulas from 73 sources: 535 identical, 1 use a new function (expected to change), 0 other differences -> IDENTICAL
```

Sources: 6 pack templates + the guided-setup template (real column maps), the demo scheme
XML, the `pb_demo` catalogue, and every formula literal in modules' tests, batteries and
`excel_formula` dict values (deterministic C5-shaped column maps). The one change is a
classifier test fixture that USES `DATE(` — it used to reach eval as an unknown name (0).
Stable across `PYTHONHASHSEED` 1/2/3/99.

## 4. R5 — demo runs recomputed before and after

Local copy `wdgap_pra_r5` of the demo world (`upd_p5e_pay`: 53 runs, 34,308 payslips),
crons and mail servers off, brought to `origin/19.1` with the unchanged modules first.
Script (`scratchpad/pra/r5_shell.py`, run in `odoo-bin shell`): for the latest run of each
end-month demo scheme, (A) every payslip's stored inputs through
`_evaluate_rules_with_dependencies`, (B) every payslip recomputed with
`compute_sheet_with_formulas`, its lines read, the run's totals and "Figures add up" check
recomputed — then **rolled back**. Run once with the unchanged modules, then `-u` both
modules with PR-A and run again; every value compared.

```
Payobook Manufacturing — End-Month Payroll   slips=1000 balance stored=True before=True after=True identical=True
Payobook Logistics — End-Month Payroll       slips= 520 balance stored=True before=True after=True identical=True
Payobook Corporate Office — End-Month Pay…   slips= 500 balance stored=True before=True after=True identical=True
VPTQ End Cycle (May-2026)                    slips=   7 balance stored=True before=True after=True identical=True
Payobook Information Technology — End-Mo…    slips= 400 balance stored=True before=True after=True identical=True
Payobook Construction — End-Month Payroll    slips= 800 balance stored=True before=True after=True identical=True
Payobook Retail — End-Month (latest = 1-slip bonus run)  slips=1  identical=True
TOTAL runs=7 slips=3228 lines=82023 evaluated values=61524 differences=0

-- Retail's latest REGULAR run, run separately (the latest Retail run is a 1-slip bonus run):
Payobook Retail — End-Month Payroll · October 2026  slips=902 balance before=True after=True identical=True
TOTAL runs=1 slips=902 lines=24354 evaluated values=18040 differences=0
```

All seven demo schemes, one regular run each: **4,130 payslips, 106,377 payslip lines,
79,564 evaluated values — 0 differences.** The database copy was dropped afterwards.

**Every payslip line, every evaluated value and every "Figures add up" answer is identical
before and after; `pb_balance_ok` stays true on every run.** Notes, all identical on both
sides (so not caused by PR-A): a full recompute does not reproduce the STORED lines on six of
the runs (the demo generator stages values that a plain recompute re-reads differently — the
comparison that matters is before vs after), and 6 payslips fail to recompute on the unchanged
code too ("could not convert string to float: 'x'" while writing a line — a pre-existing demo
data issue, recorded and compared like any other output).

## 5. Browser walk (T12) — local demo copy `wdgap_pra_r5`, PR-A code, port 8961

Signed in as the local copy's QA login (password set on the scratch copy only), Formula
Studio → Payobook Corporate Office — End-Month Payroll → Responsibility Allowance → Edit:

- Typed `=DATEDIF(DATE(2020,2,29),DATE(2024,2,29),"Y")`: pill **Valid**; the Functions row
  shows the everyday seven plus **All functions** → four groups exactly as the table
  (Numbers 20, Conditions 8, Dates 8, Look up 2), each with its help line. The live help
  line first showed DATE's help (last name typed) — changed so it follows the call being
  typed, outermost once complete (commit `e5a9f4607`).
- Typed `=YEAR(TODAY())-2020`: pill **Check formula**, red box with the exact sentence;
  **Save** refused with the same sentence in a warning toast; nothing written.
- Live preview → Preview a real employee → Corporate Office July 2026 → Bùi Anh Nam:
  values filled, "This worked out for Bùi Anh Nam · 07/01/2026".
- After the help-line fix (assets purged, server restarted): typing the same DATEDIF shows
  `DATEDIF(start, end, "Y")` with its help; pill **Valid**.
- Saving it was refused for this login with the standard "not allowed to modify" message —
  the QA login has no Formula Manager rights, so the save itself is covered by the Studio
  tests (save_formula / save_component write a DATEDIF formula and its converted Python).
- The flowchart calculator as bundled in the browser
  (`@pb_formula_studio/js/formula_flow_eval`): `DATEDIF(DATE(2020,2,29),DATE(2024,2,29),"Y")`
  = 4, `DATEDIF(I2, …)` with I = "2020-02-29" = 4, `EOMONTH(DATE(2024,1,31),1)` = 45351,
  `INT(-1.5)` = -2, `I2+1` = 1.
- Console: no errors on load or during the walk.

Not walked: the 614 px phone width (the editor is unchanged in layout except the grouped
list, which collapses to one column under 620 px by its own rule).

## 6. Decisions taken in the build

- **JS mirror, not server routing**, for the Studio flowchart (§1.6).
- **Kind-free date reading.** Inside a date function ANY component whose raw value is a date
  (ISO text or a date) is read as that date — not only `value_kind = 'date'` ones. This keeps
  the converter a pure function of (formula, column map), so compiled programs stay cached by
  formula text, and matches Excel (which reads a date text as a date inside YEAR()).
  Outside date functions nothing changes.
- **DAYS / DATEDIF with a blank date answer 0** (Excel would treat blank as 0 = 1900 and
  give a large number); DATEDIF with start after end, or an unknown unit, answers 0 (Excel
  #NUM!). Per the handover's "blank → 0, never raises".
- **Save-time refusal checks only a CHANGED formula** (the Studio sends the whole draft;
  renaming a component whose stored formula holds TODAY() is not refused). Imports, copies,
  restores and data files are not refused — they mark the component "needs attention" with
  the same plain sentence through the existing validity flag.
- **Reserved codes**: "new" = no component anywhere already carries the code. A copy of an
  old scheme with a `DAYS` component therefore still copies; a person cannot rename a
  component TO a function name. Generators append a letter (`DAYS` → `DAYSA`).
- **Converter collision fix limited to the NEW names** (`NEW_IN_PRA`): a component coded
  e.g. `ROUND` followed by "(" keeps its old (broken) treatment so no stored formula changes.
- `_compute_dependencies` (stored `formula_dependencies`) keeps its own 16-name strip on
  purpose: it feeds evaluation ORDER, and changing it recomputes nothing until a formula is
  edited anyway. Left for a later phase (follow-up 3).
- `formula_engine/converter.py` `FormulaConverter` (an unused second converter, not
  imported anywhere outside its package) was left alone.

## 7. Follow-ups (not built)

1. **Silent 0 on runtime errors** (non-goal here). `_run_formula` and the compiled
   `_evaluate` turn ANY evaluation error into 0 on the payslip. Recommendation: keep the
   0 (a pay run must finish) but collect the errors per run and show them as run
   exceptions ("3 people: SERVICE could not be worked out") — the compiled path's
   `errors` dict is never filled today (FACTS §3 gotcha), which is the first thing to fix.
2. Old function names that collide with a component code (`ROUND(` with a component coded
   ROUND) still break silently; same fix as `NEW_IN_PRA`, once a live check proves no stored
   formula relies on it.
3. Point `_compute_dependencies` at the one table (needs a recompute of the stored field and
   an evaluation-order proof).
4. A formula whose RESULT is a date (e.g. `=EDATE(JOINDATE, 2)`) shows the serial number
   (45351) on a payslip line; `value_kind_classifier` already calls DATE/EDATE/EOMONTH
   results dates, but nothing formats them as dates yet.

## 8. Owner questions (plain words)

- None blocking. One to know: a new component can no longer be given the code DATE, DAY,
  DAYS, MONTH, YEAR, INT, EDATE, EOMONTH or DATEDIF (or any other function name). Existing
  components with those codes keep working. If your teams type codes like "DAYS" by hand
  they will now be asked to pick another (Payobook suggests one, e.g. DAYSA).

## 9. Deploy notes (tier RISKY — pay calculation)

- Modules to `-u`: `pb_hr_payroll_formula`, `pb_formula_studio` (versions 19.0.1.166.0 /
  19.0.1.212.0). No migration, no data change; `python_formula` needs no regeneration
  (R1: stored formulas convert byte-identically).
- **Before the upgrade, on each database**, prove no live formula uses a newly mapped name
  (they would start computing instead of reading 0):
  `SELECT count(*) FROM hr_formula_rule WHERE excel_formula ~* '(^|[^A-Za-z0-9_])(INT|DATE|YEAR|MONTH|DAY|DAYS|DATEDIF|EDATE|EOMONTH)\s*\(';`
  (Fable's live check of 2026-11-14 found none of the advertised names in 1,283 formulas.)
  Any hit → stop and report.
- Asset purge: **yes** (new JS file in the backend bundle, SCSS, XML template) + restart.
- Browser check after deploy: Formula Studio → a component → Edit → Functions → "All
  functions"; type `=DATEDIF(` and read the help line; try `=TODAY()` and read the refusal.

## 10. New gotchas → ledger

PRA-1 … PRA-5 added to `WDGAP_LEDGER.md` (column-map order in fixtures; the old formula bar
is unbundled; function-name/code collision in the code pass; duplicate msgid with a model
term; local venv + worktree-guard tips).
