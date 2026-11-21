# WDGAP PR — plumbing facts: date functions, running totals, net-to-gross, retro, fund payments

Verified by a read-only code survey on 2026-11-14 (branch 19.1). Do not re-derive; spot-check a line before relying on it.

I verified everything below against the main tree at `/Users/adity/Documents/GitHub/gitlocal` (branch 19.1, read-only). Paths are relative to that root, and line numbers are from today.

**Corrections to your inputs:**
- The memory note `formula-converter-contract.md` is out of date on one point. Codes that contain other codes (`SI` inside `SIEMP`) are now safe. The real rules are in `docs/FORMULA_ENGINE_CONVENTIONS.md` §C5 (line 110), enforced at `formula_rule.py:2073` `_check_code_shape`:
  - codes match `^[A-Z][A-Z0-9]*$`, with no underscore;
  - a code must never equal a column letter used in the same scheme.
- Retro is implemented in `pb_hr_payroll_formula`, not `pb_payrun_ledgers`. The ledger only displays it.
- No test asserts "all 47 demo runs balance". That was checked by hand on the live database.

## 0. Formula engine architecture (shared by all five features)

- **Converter:** `formula_rule.py:1067` `_convert_excel_to_python(formula, column_map)`. It is regex-based, in this order:
  1. hide quoted text;
  2. `<>`→`!=`, `^`→`**`, and `&` is refused (:1106);
  3. expand `BRACKET` (:1118);
  4. cell references → `values.get('CODE', 0)` (:1318);
  5. `TRUE`/`FALSE` (:1324);
  6. bare column letters (:1346);
  7. codes (:1364);
  8. **function table (:1367–1399)**, then `IF`/`IFERROR` made lazy (:1421);
  9. text comparisons → `self._streq(raw_values…)`.
- **How a function is registered:** add one regex entry to `function_map`, e.g. `r'\bROUNDUP\(': 'self._roundup('`. Then add a `self._x` method on `hr.formula.rule` (helpers at :2499–2737) that calls `excel_semantics`. Add the same method on `FormulaEvaluator` (`evaluator.py:104–170`). C12 says no function may be written inline in either path.
- Functions the converter maps today: SUM, AVERAGE, MIN, MAX, ABS, ROUND, IF, IFERROR, ISBLANK, AND, OR, NOT, COUNTA, POWER, SQRT, CEILING, FLOOR, SUMIF, SUMIFS, ROW, SUBTOTAL, MOD, SIGN, ROUNDUP, ROUNDDOWN. VLOOKUP is special-cased at :1129. **INT, COUNT, IFS, LEFT/RIGHT/MID, DATE, YEAR, MONTH, DAY, TODAY and NOW are not mapped.**
- **Three places to evaluate, all with `__builtins__={}`:**
  - `_run_formula` `formula_rule.py:2312` (eval at :2429);
  - the compiled path `formula_program.py:52/78/108`. `build_steps` makes the eval context `{'self': rule, math, abs, round, pow, all, any}` (:99), so new helpers are reached through `self`;
  - `evaluator.py:223` `evaluate_single`.
- **The guard:** `excel_semantics.assert_safe_expression` (:299). It blocks the words listed at :289–296 (`date` is not one of them, `read` and `write` are). Any name you emit must avoid that list.
- **Payslip path:**
  - `hr_payslip_formula.py:154` `compute_sheet_with_formulas` → `:241 _evaluate_rules_with_dependencies(rules, input_values)`. In application mode it goes to `formula_program.run_payslip`; otherwise it does a topological sort plus two more passes.
  - Then `:917 _create_payslip_lines_from_formulas(rules, computed_values)`.
- **Validators disagree with each other:**
  - `validator.py:47` `SUPPORTED_FUNCTIONS` (also `parser.py:72`) accepts DATE/TODAY/NOW/YEAR/MONTH/DAY, and `TODAY()`/`NOW()` are let through the empty-brackets check (:202).
  - The rule-level `formula_rule.py:1916` `validate_formula` strips only 16 hard-coded function names (:1943). Anything else (YEAR, ROUNDUP, …) is reported as "Invalid column reference".
- **What YEAR/MONTH/DAY/DATE actually do today:** `YEAR(` survives conversion unchanged, because the bare-letter pass skips anything followed by `(` (:1346) and the function map has no entry for it. At eval time that is a `NameError`. `_run_formula` catches it at :2449, writes `has_evaluation_error`, and **returns 0.0**. The compiled `_evaluate` (`formula_program.py:120`) also returns 0.0. The stated reason is at `pay_period.py:55–59` ("in the allowed lists but NOT implemented").
- **Types (VALUEKIND):** `value_kind` selection is at `formula_rule.py:807`, including `'date'`. `value_kind_classifier.py:62` `KIND_DATE`; `NUMERIC_KINDS` at :73 (do not add `date` to it); `wants_number` at :478.
  - How a date travels: `_mapped_record_value` (`payroll_import_batch.py:2975`) and `scalar_value` (`application_domain_sources.py:113`) both return an **ISO string**.
  - `normalize_input_value` (:4339) keeps non-numeric kinds as that string.
  - `coerce_value` (`excel_semantics.py:92`) turns `'2024-01-15'` into **0** in `values`. The string survives only in `raw_values`.
  - So a date function must read `raw_values`, the same way the `ISBLANK` rewrite does at :1442.
- **Regression gate:** `python3 pb_hr_payroll_formula/tools/excel_semantics_battery.py`. C12 requires a new case for every new function.

## 1. Date functions

- **Dates formulas can read today:**
  - pre-split period numbers in `pay_period.py:60` `PERIOD_CODES` (PAYMONTH, PAYYEAR, PAYDAYS, STDDAYS, STARTDAY, ENDDAY);
  - the lowest-ranked filler `fill_period_inputs` (:165) and `fill_wired_inputs` (:223), called at `hr_payslip_formula.py:858/864` and `payroll_import_batch.py:4896/4902`;
  - the per-component wire `period_key` at `formula_rule.py:702`. Labels are at :714, and new keys come from `PERIOD_CODES` automatically (:724).
- **Record dates (application mode):**
  - `EMPLOYEE_FIELDS` at `application_domain_sources.py:19` includes `birthday` and `date_of_joining`;
  - `CONTRACT_FIELDS` at :39 includes `date_start`, `date_end`, `trial_date_end`, `pb_trial_date_start`, `pb_signed_date`;
  - `exit.*` dates at :58–61.
- **Record dates (file-less and file paths):** any mapped field via `_mapped_record_value`. The mapping catalogue is `pb_formula_studio.py:10828` `_ec_right_items`, with the eligibility test at `_ec_is_mappable` :10530. It is now 236 fields, not 193 (MAPFIX E handover line 10).
- **Joining-date precedent:** `hr_payslip_formula.py:1375` uses `date_of_joining`, then `first_contract_date`, then the contract start. D27 warns that the contract start does not prove the service start.
- **Clone:** `rule_formula.py:328` `_TABLE` (name → (python name, help line), with `SUPPORTED_FUNCTIONS` and `FUNCTION_HELP` built from it at :355–357). It is the cleanest table-driven precedent.
- **Gotchas:**
  - No reserved-word list exists (`component_code.py:253` takes `reserved=()`), so a scheme component coded `MONTH`, `DAY` or `DATE` would collide with a new function name.
  - The `\bDAY\(` pattern must not catch `ENDDAY` (already safe: it has become `values.get('ENDDAY',…)` and is not followed by `(`).

## 2. Running totals (YTD/QTD/MTD, tax year)

- **The engine's own source:**
  - catalogue key `history.ytd.<CODE>` for money/quantity rules (`application_domain_sources.py:188`);
  - reader `_application_history_value` :477;
  - **calendar year hard-coded**: `year_start = start.replace(month=1, day=1)` at :481;
  - D27's "not known, never a confident 0" at :487–495;
  - one `hr.payslip` search **per person** plus a JSON parse of `formula_computed_values` (:496–521);
  - it requires the periods to join with no gap (:508).
  - **Application mode only.** It runs when `_application_mode()` is true (`application_payroll_source.py:1070`, `run.application_data_mode`).
- **pb_updates opening figures:**
  - `pb_updates/models/updates_ytd.py`: models `pb.updates.ytd.figure` :158, `.map` :183 (bases `opening`/`before_period`/`with_period`, :63), `.line` :228, `.use` :1143;
  - "tax year is the calendar year (ledger U42)" at :12; `_plan_for_slip` uses `year = date_to.year` (:758);
  - **batch SQL precedent to clone: `_ledger(emp_ids, first, last, codes)` :473**, which reads `hr_payslip_line` and falls back to stored results. But `_plan_ledger` (:834) calls it one employee at a time.
  - The hook into pay runs is `updates_ytd_payrun.py:135` `_get_formula_input_values`, file-less path only, skipped in application mode.
- **My Payobook tax sheet:** `pb_me_portal/controllers/portal.py:450` `/my/taxsheet` sums the year of the most recent payslip, calendar year (:480–485), limit 48 done payslips.
- **Existing financial-year settings to reuse:** `pb_group.fiscal_start_month` with `fiscal_year_start(on_date)` (`pb_group/models/pb_group.py:135`); `pb_explorer.py:1389` `_fy_start_month` (group first, then parameter `pb_budget.fy_start_month`); `pb_budget.py:107–127`.
- **No per-component running-total table exists.** `pb_pay_totals` is the money-band helper in `om_hr_payroll/models/pay_bands.py`, not a store.
- **Scale:** the client sends chunks of 40 people (`pb_payrun_wizard/static/src/js/run_driver.js:35`) to `compute_batch` (`pb_payrun_wizard.py:1324`). The request memo is `_application_memo` (`application_payroll_source.py:248`), and compiled steps are cached per memo (:290).

## 3. Net-to-gross

- **Nothing exists.** A search for goal seek / solve / gross-up / grossup / tax-on-tax / net_to_gross found nothing.
  - `pb_salary_basis` gross/net is a label only (`pb_employee_vault/models/payroll_profile.py:33`, its help text says "conversion still follows the approved payroll formula").
  - The guided-setup tile is a label only (`pb_blueprint/models/blueprint_finish.py:223`).
  - Circular references are only warned about (`evaluator.py:371`; `validator.py:207`).
- **Ways to compute one person without writing anything:**
  - `hr.formula.sample.data.new({'config_id': id})._evaluate_rules_with_dependencies(input_values, readonly=True, errors=None)` (`formula_sample_data.py:597`), which goes to `formula_program.run_sample(steps, input_values, errors)` (:133).
  - **Fastest loop:** `steps = config._pb_formula_steps(config.rule_ids)` once, then `run_sample` per guess.
  - Users of this path: `payroll_preparation.py:302 _calculate`; `formula_config_template.py:516`.
  - Formula Studio real-pay preview: `preview_runs(config_id)` :2204, `preview_people(run_id, config_id)` :2236, `preview_from_payslip(config_id, payslip_id, anonymize=False)` :2271 (reads `formula_input_values`, uses `.new()`, no writes).
  - Guided-setup example person: `blueprint_components.py:270 _sample_values` → `pb.formula.studio.compute_preview(config_id, sample_id)` (:2174). `bp_outputs` is at `blueprint_outputs.py:68`.
  - Draft-formula overlay: `formula_simulation.py:41 _evaluate_config_overlay(config, input_values, overrides, value_overrides)`. It is slow because it re-converts every formula.
- **Gotcha:** the compiled `_evaluate` swallows every exception and returns 0.0 (`formula_program.py:120–122`). So `run_sample`'s `errors` dict is never filled on that path. A search loop cannot tell a broken formula from a real zero.

## 4. Retro

- **Model:** `hr.payroll.retro.adjustment` (`payroll_retro_adjustment.py:7`). Fields: `old_amount`, `new_amount`, `delta_amount`, `original_payslip_id`, `applied_in_batch_id`, `applied_in_payslip_id`, `advantage_change_id`, `state` (default `posted`). Unique constraint at :95.
- **Settings:** `formula_config.py:102` `use_auto_retro` and `:106` `retro_component_id`.
- **Flow (uploaded-file path only):**
  1. `payroll_import_batch.py:4955` calls `_apply_retro_adjustments` (:2695);
  2. `_prepare_retro_adjustments` (:2716) finds `hr.contract.advantage.change` rows (`contract_component_change.py:7`) effective before the period;
  3. for each done/paid payslip it takes (new − old) × segment days ÷ period days, using `_get_proration_days` (:2550);
  4. it adds the total to ONE input component (:2714);
  5. `_link_retro_adjustments` (:2807).
- **What it does not do:**
  - re-run earlier months' formulas, so tax and insurance on the difference come only from this month's formulas;
  - anything on the file-less path or in application mode (no "retro" in `hr_payslip_formula.py` or `application_payroll_source.py`);
  - filter past payslips by scheme (:2733);
  - Excel rounding: it uses Python's `round()` (:2773), which C12 forbids for money;
  - holds or exclusions per line.
- **Ledger:** `pb_payrun_ledgers/models/ledger_cockpits.py:792` `pb.retro` is a read-only list; Proration Audit is `pb.proration` at :626 over `hr.payroll.proration.line`.
- **Carrier precedent:** `hr.payroll.period.input` (`payroll_period_input.py:35`): approval :253, reserve/consume :318/:333, read in application mode at :404. Retro does not use it.
- **Reopening a finished run:**
  - `pb_payruns/models/hr_payslip_run.py:1410 draft_payslip_run` has no approval yet; its comment says the `reopen` process will come later.
  - `reopen` is mapped onto the `payrun` route at `pb_payruns/models/approval_seed.py:114`.
  - Sending back an approved run is `_approval_return` :1156.
  - Closed pay months: `pb_comp_ben/models/month_approval.py:78 _apply_reopen` with process key `month` (:25).

## 5. Fund and tax-office payments

- **Contribution actuals:** `pb_statutory.py:187–224` reads the latest run only, groups lines by code, and uses the hard-coded Vietnam codes `CONTRIB_MAP` (:43) for SI/HI/UI. It is a display, not a record.
- **No remittance model exists.**
- **Precedents to clone:**
  - `pb.payment.release` (`pb_pay_delivery/models/payment_release.py:42`): key `release`, fields amount, bank_reference, evidence attachment, state;
  - `pb.bank.file` (`bank_file.py:54`, key `bankfile`);
  - `pb.payroll.journal` (`payroll_journal.py:57`, key `journal`);
  - shared base `pb.money.approval.mixin` (`approval_common.py:43`); seeds in `approval_seed.py:141`;
  - filing: `pb_govt_reports/models/filing_approval.py:45` `pb.filing.proposal` (key `filing`); `pb_filing_flow.py:146`.

## Formula Studio UI

- **Function list:** `pb_hr_payroll_formula/static/src/js/formula_bar.js:44` `getSupportedFunctions` (it already advertises TODAY/NOW/YEAR/MONTH/DAY at :94–98, plus INT/IFS/LEFT etc., none of which work).
- **Examples:** `formula_autocomplete.js:106` `getExamples`.
- **The Studio's own flowchart calculator:** `pb_formula_studio/static/src/js/formula_studio.js:3053` `evalNode`. An unknown function returns its first argument.
- **Help text in data:** `data/formula_functions_data.xml:57–63` (mentions DATEDIF).

## Tests, translations, versions

- **Tests to extend:**
  - `pb_hr_payroll_formula/tests/`: `test_pay_period_source.py`, `test_runsrc_period_answers.py`, `test_feed_binding_and_period.py`, `test_application_history_ytd.py`, `test_payroll_period_input.py`, `test_payroll_preparation.py`, `test_formula_string_literals.py`;
  - `pb_formula_studio/tests/test_rd46_person_preview.py`;
  - `pb_updates/tests/test_updates_p5*.py`;
  - `pb_payruns/tests/test_run_totals.py`, `test_pay_bands.py`.
- **Demo balance:** this is the stored `hr.payslip.run.pb_balance_ok` / `pb_balance_gap` (`pb_payruns/models/hr_payslip_run.py:302/309`). `pb_demo` computes through `demo_payrun.py:409 compute_batch` → `_evaluate_rules_with_dependencies`. The only automated proof is the battery plus `test_run_totals`. To be sure a function change alters no existing result, re-check `pb_balance_ok` on the 47 runs.
- **Translations:** `vi_VN.po` in each module (`pb_hr_payroll_formula/i18n` also holds stray `vi_VNnew`, `vi_VNnew2.po`, `vi_VNorig`).
- **Manifest versions:** `pb_hr_payroll_formula` 19.0.1.165.0, `pb_formula_studio` 19.0.1.211.0, `pb_payrun_ledgers` 19.0.1.4.0, `pb_statutory` 19.0.1.5.0, `pb_pay_delivery` 19.0.1.4.2, `pb_updates` 19.0.1.7.4.