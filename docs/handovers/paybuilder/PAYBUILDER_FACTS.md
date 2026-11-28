# PAYBUILDER — verified plumbing facts (do not re-derive)

Read at **`2882e1a38`** (origin/19.1, 2026-11-28, "JOINING fix: HR brings the signed wage across without Hiring
rights") in a clean checkout. Every path is repo-relative; `:N` is a line at that revision. If a line has drifted,
search the identifier — the identifier is the fact, the line is a hint. "NOT VERIFIED" = could not be proved from code
(no database access was used). Engineering doc: technical names are fine here; every user-visible string the build
adds must obey the white-label rule (never the vendor name) and the plain-words rule.

Design of record: `docs/design/pay-builder-poc.html` (in the owner's main checkout, untracked; `PayBuilder(el, opt)`
:457, `compute` :464, `rowHtml` :490, `whyHtml` :513, `solve(target)` :639, "One block, four homes").
Companion fact files (still valid, cited and re-verified below): `docs/handovers/joining/JOINING_FACTS.md`,
`docs/handovers/newhire/NEWHIRE_FACTS_CORE.md`.

---

## 0. What moved since the earlier fact files

| Fact | Was | Now (at 2882e1a38) |
|---|---|---|
| Release script | JOINING_FACTS F0: local-only commit `840036012`, cherry-pick it | **On origin/19.1** (`e7c38a944`, later `3e220ee95`, `d7db27c7a`). `tools/release.sh`, `ops/pb_release.sh` exist. No cherry-pick needed. |
| `pb_new_hire` version | 19.0.1.8.1 | **19.0.1.8.2** (`pb_new_hire/__manifest__.py:49`) |
| `pb_joining` | — | **19.0.1.0.1** (`pb_joining/__manifest__.py:4`) |
| `create_employee` / `create_contract` | `people_wizards.py:183` / `:503` | `pb_people_advanced/models/people_wizards.py:225` / `:546`; contract `cvals['wage'] = float(vals.get('wage') or 0.0)` `:579` |
| `_get_formula_input_values` | `hr_payslip_formula.py:614`, BASIC/WAGE/BASE `:736-740` | `:616`, map `:739-743` |
| `_evaluate_rules_with_dependencies` (sample) | `formula_sample_data.py:595` | `:597` |
| `is_contract_component` / `default_value` / `is_text_component` / `value_kind` | `formula_rule.py:674 / 559 / 788 / 808` | `:694 / :579 / :808 / :828` |
| `_pb_usual_answer_rules` | "factor-out to do" | exists: `pb_hr_payroll_formula/models/contract_fill_in.py:255-271` |
| `template_for_rule` / `pb_fill` | `contract_fill_in.py:293 / 326` | `:311 / :344` |
| Joining's "From the signed offer" for HR without Hiring rights | refused | allowed (J-25): `pb_joining/models/studio.py:43-63` |

---

## A. Step 3 today ("Contract and pay")

### A.1 Template `pb_new_hire.StepPay` — `pb_new_hire/static/src/xml/new_hire_studio.xml:480-627`
| Lines | Block |
|---|---|
| 481 | root `.pbnh-step-in`, `data-coach="nh-step-pay"` |
| 482-488 | question: eyebrow "Step 3 of 7 · required", h1 "What is the contract, and what does it pay?", intro "…Type the monthly wage, then check the scheme's usual answers." |
| 490-499 | `!canPay` → card "Choose the team and the country of work first" + "Go to role and place" (`goRole`) |
| 501-520 | **Paid by** card (`.pbnh-paidby` + `paidCls`): scheme name, `scheme.why`, `wagesIn`, `dec.problem/fix`; chip "Picked in step 2" / "Set by the team" |
| 522-551 | **Monthly wage** card: label (required star) 523; `.pbnh-wage` box 524-529 (currency symbol `cur.symbol` 525, `<input id="pbnh-f-wage" inputmode="decimal">` 526-527 → `onWage`/`onWageBlur`, `<small>` `wageCode` 528); field error 530; pay-scale lines 531-533 (`scaleEmpty`, "From the pay scale: …", `scale.why`); off-scale pin 534-541 (reason `<select>` → `onReason`, "Use the scale amount" → `useScale`); band 542-550 (`.pbnh-band` + `bandPos`, `.pbnh-bandl` min/chip/max, else `bandNote`) |
| 553-595 | contract card: Permanent/Fixed term `.pbnh-seg` 557-562 (`setKind`), Starts 564-568, Ends 569-573, Contract category 574-583 (`showCats`, `onCat`), Trial period 584-593 (`.pbnh-tog` → `toggleTrial`) |
| 597-624 | **"The scheme's usual answers"** card (only `t-if="scheme"`): header 598-600 (`usualIntro`); skeleton while `usual.rows === null or usual.busy` 601-603; empty "This pay scheme has no usual answers to check." 604; rows 606-622: toggle (`control==='toggle'`) / `<select>` (`'choice'`) / text input (`'number'`), chip "Changed for {first}" + "Back to usual" (`changed(row)`/`back`) else teal chip "Usual answer" |

### A.2 Component `StepPay` — `pb_new_hire/static/src/js/step_pay.js` (180 lines)
- `setup` 17-21: `this.nh = useState(api.nh)`, `this.ui = useState({typing:null})`.
- Getters: `d` 23 (`nh.draft`), `cur` 25 (`api.currency`), `dec` 26 (`nh.decides`), `canPay` 29 (`department_id && payroll_country`),
  `scheme` 33, `paidCls` 34, `wagesIn` 35-37.
- Wage: `wageText` 40-45 (typing text, else `moneyNumber(d.wage, cur)`), `onWage` 46-56 (`groupTyped` → `parseMoney` →
  `api.set("wage", n|null)` — never NaN/"" (WS18)), `onWageBlur` 57, `wageCode` 58 ("%s a month").
- Band/scale: `band` 61 (`nh.hint.band`), `bandNote` 62, `bandPos` 63-73, `bandChip` 74-88, `scale` 89, `scaleEmpty` 90-95,
  `scaleOff` 96-99, `reasons` 100, `onReason` 101 (`pb_scale_pin_reason`), `useScale` 102-108 (`patch({wage: s.amount, pb_scale_pin_reason:""})`).
- Contract: `setKind` 111, `cats/showCats/catSuggested/catWhy/catNone/onCat` 113-123, `onDate` 124, `endErr` 125-132,
  `trial/trialLine/trialWhy/toggleTrial` 133-150.
- Usual answers: `usual` 153 (`nh.usual`), `usualIntro` 154-158, `value(row)` 159-162 (`d.usual[code]` else `row.value`),
  `changed` 163, `toggleRow` 165-168, `isOn` 169 (`>= 0.5`), `onChoice` 170, `onNumber` 171-176, `numberText` 177, `optSelected` 178,
  `back` 179 → `api.setUsual` / `api.resetUsual`.

### A.3 Draft keys step 3 reads/writes (root `pb_new_hire/static/src/js/new_hire_studio.js`)
- Blank draft 113-114: `wage: null, contract_kind: "permanent", date_end: "", trial_on: true, usual: {}, pb_scale_pin_reason: ""`;
  `type_id` via `P2_KEYS` 47-75 (`type_id: [false, …]`).
- `nh.usual = { configId: 0, rows: null, busy: false }` 147; `nh.hint = null` 148; `nh.cats` 150; `nh.example`/`exampleBusy` 160-161.
- `api.setUsual/resetUsual` 180-181 → `setUsual(code, amount)` 1190-1202 (only codes present in `nh.usual.rows`; an amount equal
  to `row.value` deletes the key) / `resetUsual` 1203-1207. Draft `usual` = `{code: amount}`.
- **When `nh.usual` loads:** `loadUsual(configId)` 1014-1034 → RPC `usual_answers([configId])`; called from the `decides`
  reply (`refreshDecides` 917-943, call at 941) and the `places` reply (987). A different scheme clears `draft.usual` (1019-1023).
- Band/scale: `refreshHint` 1036-1050 → RPC `pay_hint([job_id, date_start, wage|false, payroll_country])`; on `wage` change it is
  debounced 350 ms (1104-1105); job/date/country refresh at once (1102-1103).
- Currency shown: `get currency()` 1223-1229 = `nh.decides.currency` else `data.currencies[payroll_country]`.
- Ready/status: `payReady` 1268-1273 (wage > 0 or `scaleFound` 1230-1233, and a valid end date for fixed term); rail text
  1294-1301 ("Wage needed" / "End date needed" / "%s a month").
- Sent as: `sendDraft` 1466-1487 — `wage: d.wage === null ? "" : d.wage`, `usual: [{code, amount}]` (list form), `pb_scale_pin_reason`,
  `contract_kind`, `date_end`, `trial_on`, `type_id`, `scheme_id`, `advance_scheme_id` (`advanceArg` 83-86).
- Server whitelist `DRAFT_KEYS` `pb_new_hire/models/studio.py:58-78` (includes `wage`, `usual`, `pb_scale_pin_reason`,
  `pb_scale_pin_note`, `type_id`, `offer_id`, `scheme_id`, `advance_scheme_id`); `pb_joining` adds `joining_id`
  (`pb_joining/models/studio.py:25-26`); `_draft_keys()` hook `studio.py:936-938`. **A new draft key (e.g. contract lines,
  what-if amounts) must be added here or `send` drops it** (`studio.py:952-953`).

### A.4 The payslip example request (right panel)
- Inputs that re-run it: `EXAMPLE_INPUTS` `new_hire_studio.js:78-79` (`name, date_start, department_id, job_id, job_title,
  payroll_country, country_id, wage, contract_kind, date_end, usual, type_id, scheme_id, advance_scheme_id`); dispatch at 1125-1127.
- Debounce `EXAMPLE_MS = 500` (80); busy retry `EXAMPLE_RETRY_MS = 600`, `EXAMPLE_TRIES = 8` (89-90).
- `exampleReady` 460-465 (name, first day, team, country, wage>0 or scale, valid end date); `exampleDraft` 466-471 (the subset of
  `sendDraft`); `refreshExample` 478-491; `runExample` 492-534: ONE request in flight (`exampleInFlight`), a change during flight is
  re-sent (`examplePending`), stale answers dropped by `exampleToken`; `res.busy` → quiet retry; error →
  `{ok:false, reason: errorText(err), fix:"The hire is not affected. Try again in a moment."}`; busy after 8 tries →
  "The example is busy for a moment." / "Change any answer to try again." (531-533).
- Panel `RecordPanel` (`pb_new_hire/static/src/js/record_panel.js`): scroll-into-view effect 20-33; `get slip()` 118-157 has four
  states: `wait` (not ready; text "A month's payslip appears here once the name, team, country of work and wage are in."), `load`,
  `no` (`reason, fix, step, stepLine` "Go to step N, Title"), `ok` (`month` = "month_label · scheme", `lines[{key,name,cls,text}]`
  where `band==='deduction'` → `is-ded` and "− amount", `band==='info'` → `is-info`; `net`; `sums` = "Gross … · Taken off … [· Employer
  cost …]"; `notes[]`). `get paid()` 163-180. Template `pb_new_hire.RecordPanel` xml:1216+, slot `data-coach="nh-example"` 1259-1297.
- **Server payload rendered** (`pb.new.hire.payslip_example`, `pb_new_hire/models/payslip_example.py:111-135`, shape :267-285):
  ```python
  {'ok': True, 'month_label', 'month', 'lines': [{'name','amount','band': 'earning'|'deduction'|'info'}],
   'gross', 'deductions', 'net' (None when the scheme has no NET line), 'employer_cost',
   'currency': {'symbol','name','position','decimals'}, 'scheme', 'scheme_id', 'notes': [str], 'cached', 'took_ms'}
  # refusal: {'ok': False, 'reason', 'fix', 'step'} (+ 'busy': True)  — _no() :137-140
  ```

### A.5 SCSS (`pb_new_hire/static/src/scss/new_hire_studio.scss`, 787 lines; tokens `--pbnh-*` :12-35 on `.pbim.pbnh`)
`.pbnh-card` 138, `.pbnh-cardh` 147, `.pbnh-chip` 149-158 (`--ok/--warn/--p/--teal`), `.pbnh-seg` 230-232, `.pbnh-tog` 233-236
(38×22 switch, `.is-on`), `.pbnh-paidby` 316-322, **`.pbnh-wage` 323-335** (`-cur` 329, input 330, `small` 335, `.is-bad` 328),
`.pbnh-band/-bandl` 336-339, `.pbnh-scale/-scale-off` 340-343, `.pbnh-trial` 344, **`.pbnh-row` 345-352** (`-row-t`, `-row-r`,
inputs 130 px right-aligned), `.pbnh-empty` 353, `.pbnh-num` 53 (tabular), right panel `.pbnh-pv` 571+, dark payslip `.pbnh-pvo*`
644-675, `.pbnh-pvno*` 676-684; grid `236px / 1fr / 328px` :98; breakpoints 1180 / 820 / 600 (:735, :740, :752).

### A.6 Wage validation and where it is written
- `_validate` `pb_new_hire/models/studio.py:773-815`: wage lines 803-808 — a given non-number or negative → "The wage must be a number
  above zero."; **empty or 0 and no pay-scale amount → refused "Type the monthly wage."** (step `pay`, field `wage`). Same rule in the
  example refusal `payslip_example.py:156-158`.
- `_values` `studio.py:855-933`: `'wage': wage if wage else ''` (884); `'usual': self._usual_choices(d, config)` (890);
  `'pb_nh_scheme_id'` (891). `send` `studio.py:940-986`: proposal `amount = vals['wage'] or self._scale_amount(d)`, fact `wage` (959-967).
- Written to **`hr.contract.wage`** only: `create_employee` passes `'wage': vals.get('wage')` to `create_contract`
  (`people_wizards.py:309-318`) → `cvals['wage'] = float(...)` (`:579`). An empty wage is filled from the pay scale by
  `pb_pay_scales/models/joiners.py:63-74`. Contract `payroll_country` is set at create by `HrContractNewHire.create`
  (`pb_new_hire/models/create_ext.py:294-313`, NH3) so the Monetary wage rounds in the right currency.

---

## B. Why Rize India shows 0

### B.1 How the contract wage reaches a scheme — exactly two ways
1. **Hard-coded code map** in the no-file resolver: `hr_payslip_formula.py:739-751` — only input rules whose code (upper) is
   `BASIC`, `WAGE` or `BASE` read `contract.wage`:
   ```python
   contract_mapping = {'BASIC': 'wage', 'WAGE': 'wage', 'BASE': 'wage'}
   contract_field = contract_mapping.get(rule.code.upper())
   ...  if raw_contract: src, key, via = 'employee_field', contract_field, 'contract_field'
   ```
2. **A record mapping** `hr.payslip.import.mapping` (`destination_type='field'`, `target_model_id.model='hr.contract'`,
   `target_field_id.name='wage'`) on that component — read by `Batch._mapped_record_value` in the records lane (:704-713, :806-820).
   The same two ways are what Formula Studio's take-home card calls "wage codes": `pb_formula_studio/models/take_home.py:47-50`
   (`WAGE_CODES`) and `_th_wage_codes` :359-389.
- There is **no** "wage" source kind: `_SOURCE_RANK = ('feed','rule','excel','employee_field','contract_field','bank_account')`
  (`formula_rule.py:267-268`). `source_field_mapping` (`formula_rule.py:177-181`) is the connected system's field name;
  `data_source_field` (`:574-577`, editor label "Source field mapping") is a spreadsheet-header alias used by import/classifier
  (`formula_config.py:2104`, `column_role_classifier.py:538-545`) — neither reads the contract wage. `declared_sources()`
  (`formula_rule.py:352-411`) lists `source_ids` by rank + a trailing `contract_component` (when ticked) + `pay_run` (`period_key`).

### B.2 The full input ladder — `hr.payslip._get_formula_input_values(config, provenance=None)` `hr_payslip_formula.py:616-916`
Per **input** rule (`column_type == 'input'`, :636), keyed by `rule.code`:
1. start: `value = '' if rule.is_text_component else rule.default_value`, `src='none', via='default'` (:735-736);
2. contract wage for `BASIC/WAGE/BASE` (:739-751) → `src 'employee_field', via 'contract_field'`;
3. worked days for codes `WD_*` / `HOURS*` from `slip.worked_days_line_ids` (:754-763) → `via 'worked_days'`;
4. the two ranked readers, order from the scheme's lanes (`config._source_kind_rank()` `formula_config.py:513-524`,
   `_LANE_KINDS` :439-445, `source_priority` default `'api,excel,records'` :462-467; `records_first` :652-654):
   - `_from_api` — connected-system hit (`_j3_feed_hits_by_rule`, :660) → `src 'feed'|'rule', via 'connector_mapping'`;
   - `_from_records` — mapped employee/contract field (`_mapped_record_value`) → `src 'employee_field', via 'employee_mapping'`;
     else **contract line present** in `Batch._contract_component_values(contract, config)` (`payroll_import_batch.py:2318-2341`,
     amounts from `_contract_component_amounts` :2291-2316) → `src 'contract_component', via 'contract'` (presence wins, zero included);
5. **no reader answered and the rule is a contract component** (:835-840):
   ```python
   elif records_lane_ok and rule.is_contract_component:
       value = component_amounts.get(code, '' if rule.is_text_component else 0.0)
       src, key, via = ('contract_component', rule.code, 'contract_default')
   ```
   → **a contract component with no line on the contract is 0 — its `default_value` is NOT used on this path.**
6. pay-period codes (`pay_period.fill_wired_inputs` / `fill_period_inputs`, `PAYMONTH`, `STDDAYS`… from the payslip dates and run)
   :852-871 → `src 'period'`;
7. clock hours `config._pb_clock_apply(employee, date_from, date_to, values, provenance)` :876-877;
8. work segments `pb.work.segment.apply_to_inputs` :903-910 (reduces fixed pay to covered days).
- `provenance[code] = input_provenance.entry(src, key=key, via=via)` (:845-846); `src == 'none'` means default
  (`pb_count_sourced` :606-614). Constants are not added (rule evaluator reads `constant_value`, :912-916).

### B.3 Why `_pb_usual_answer_rules()` returns nothing for INANNFIX
`pb_hr_payroll_formula/models/contract_fill_in.py:255-271`:
```python
return self.rule_ids.filtered(
    lambda r: r.is_contract_component
    and not r.is_text_component
    and (r.value_kind or 'money') in NUMERIC_FILL_KINDS
    and (r.code or '').strip()
    and abs(r.default_value or 0.0) > 1e-9          # <- a 0 usual answer is excluded
).sorted(lambda r: (r.sequence, r.id))
```
`NUMERIC_FILL_KINDS = ('money','decimal','integer','quantity','rate','boolean')` (:46-47). By design "No" = absence of a line; zero
defaults are never filled. Consequences in Add employee:
- `usual_answers` (`studio.py:662-686`) lists only these rules → empty → "This pay scheme has no usual answers to check." (xml:604).
- `_usual_choices` (`studio.py:831-852`) accepts only codes in those rows, and `_pb_nh_lines` (`create_ext.py:232-270`) only codes
  in `_pb_usual_answer_rules()` → **today there is no way to put an INANNFIX line on the new contract from Add employee.**
- The wage box writes `hr.contract.wage`, which INANNFIX never reads (code ≠ BASIC/WAGE/BASE; a wage mapping row on the live
  scheme is NOT VERIFIED — no database access). INANNFIX resolves via rung 5 to 0 → every formula driven by it is 0 → example Gross 0 /
  Take-home 0. The same would happen on the real pay run for that hire until someone adds the line in the contract panel.
- Repo evidence of the shape: `tools/data/rize_focused_payroll_plan.json:1583-1588` (`INANNFIX` "Annual Fixed CTC", column L,
  source ""), formulas `{INANNFIX}/12`, `ROUND({INANNFIX}*{INBASICRATE},0)` in `docs/configuration/rize-india-client-master-2026.json:252-342`.
  Live default_value/ticks: NOT VERIFIED (owner's observation).

---

## C. The rules model (`hr.formula.rule`, `pb_hr_payroll_formula/models/formula_rule.py` unless noted)

| Field | Type / values | Meaning |
|---|---|---|
| `config_id` :52 | M2o `hr.formula.config` | the scheme |
| `column_letter` :79-85 | Char, stored compute + inverse | Excel letter A…AA; formulas reference **letters with a row number** (`=A1*0.2`) |
| `sequence` :87-91 | Integer, default 10 | column order (evaluation fallback order) |
| `name` :96 / `code` :102 | Char required | label / code (underscore-free contract, see memory "formula converter contract") |
| `category_id` :108-112 | M2o `hr.salary.rule.category` | fallback band when no pay role (`pay_bands.py:47-55`) |
| `column_type` :123-133 | `input` "Input (from data source)", `formula` "Calculated (formula)", `constant` "Constant Value"; default `formula` | |
| `source_ids` :214 | O2m sources (`kind` feed/rule/excel/records…) | declared bindings |
| `excel_formula` :521-524 | Char | `=IF(A1>1000,B1*0.1,0)` |
| `formula_dependencies` :539-543 | Char, stored compute `_compute_dependencies` :1708+ | comma list of referenced letters AND codes (ranges expanded; BRACKET expanded first); over-reports |
| `default_value` :579-583 | Float | "usual answer for a new contract" when `is_contract_component`, else the input's fallback |
| `constant_value` :588-593 | Float digits (20,8) | constant columns |
| `appears_on_payslip` :669-673 | Boolean default True | **creates a payslip line** (with `wants_number`) |
| `payslip_sequence` :676-680, `visibility_rule` :681-686 (`always`/`when_nonzero`/`never`), `report_visible` :688 | | payslip print order/visibility |
| `is_contract_component` :694-698 | Boolean, string "Contract Component", help "Marks this component as a contract component sourced from contract advantages." | input read from the contract's line (B.2 rung 4/5) |
| `period_key` :723 | Selection (pay-run period codes) | the pay run as a declared source |
| `requires_new_contract` :778-782 | Boolean, help "If enabled, changes to this component will trigger a new contract effective date." | **a label only** — nothing creates a contract version from it (`pb_contract_360.py:949-950`, xml "usually starts a new contract" `contract_360.xml:138`) |
| `is_text_component` :808-813 | Boolean | value in `text_value`, not `amount` |
| `value_kind` :828-845 | `money` Amount (currency), `decimal`, `integer` Whole number, `quantity` (hours, days), `rate` Percentage / rate, `identifier` Reference code, `text`, `date`, `boolean` Yes / No; default `money` | `value_kind_classifier.wants_number(kind)` (`value_kind_classifier.py:478-484`) = kind in `NUMERIC_KINDS` (:73-74: money, decimal, integer, quantity, rate) — **`boolean` is NOT a number → never a payslip line**, though it IS a fill kind |
| `net_role` (`formula_net_role.py:602-614`) | `earning` Added to net pay, `deduction` Taken off net pay, `net` Net pay itself, `employer_cost` Employer cost, `info` Information only, `mixed` Both added and taken off; no default | pay role → band (F) |
| `net_role_detail` (`formula_net_role.py:615-620`) | Boolean "Included in another total" | line shows but totals skip it |
| `value_labels` (`contract_fill_in.py:150-155`) | Char `"0=No;1=Yes"` | words per number; `value_labels_hint` :158-162 |
- Word helpers (`contract_fill_in.py`, class `HrFormulaRuleValueLabels` :147): `value_label_is_yes_no` :164, `value_to_text(amount, short)`
  :169-180, `value_from_text` :182, `value_label_options()` :189-193, `value_label_for(amount)` :195-207 (`''` when none),
  **`value_label_control()` :209-220 → `'toggle'` (options exactly {0,1}, or `value_kind=='boolean'`), `'select'` (other words), `''`**,
  `value_word_choices()` :222-229 (Yes first for a toggle). All record-free (work on `Rule.new({...})`, precedent
  `pb_formula_studio/models/studio_fillin.py:30-45`).
- `_pb_component_rules(codes, company)` :231-249 — `{code: rule}` with the contract panel's preference (same company, active scheme).

### C.1 Rule → contract line
- Lines live on `hr.contract.advantage` (`om_hr_payroll/models/hr_contract.py:7-43`): `contract_id`, `advantage_template_id`,
  `advantage_template_code` (related code), `advantage_lower_bound/upper_bound` (related), `amount` Float; **bounds constraint**
  `_check_bound_limits` :31-43 raises outside non-zero bounds. Extensions: `value_type` (related) + `text_value`
  (`contract_advantage_typed.py:36-44`); `pb_fill` `[('auto','Filled in by Payobook')]`, `pb_checked_by`, `pb_checked_at`
  (`contract_fill_in.py:344-349`; any amount/text write without context `pb_fill_in_write` clears the mark :351-368).
  **No date fields** on a line.
- Catalogue `hr.contract.advantage.template` (`om_hr_payroll/models/hr_contract.py:143-151`: `name, code, lower_bound, upper_bound,
  default_value`; + `value_type` amount/text `contract_advantage_typed.py:25-32`). **No company field — matched globally by code.**
- Rule ↔ template **by code**: `template_for_rule(rule)` `contract_fill_in.py:311-339` (search by `code`, create when missing with
  bounds 0/0, never flips `value_type`). **Nothing creates the template when the box is ticked** (no write hook on
  `is_contract_component`); it is created lazily by: fill-in (`contract_fill_in.py:539`), import sync
  (`payroll_import_batch.py:5372-5382`), Add employee lines (`create_ext.py:257`), contract panel save `_cd_template_for_code`
  (`pb_contracts/models/pb_contract_360.py:1646-1663`, deliberately restated to avoid a formula-engine dependency), offer split
  (`pb_pay_package/models/offer_total.py:116`).
- Trail `hr.contract.advantage.change` (`contract_component_change.py`): fields :42-75 (`old/new_amount`, `old/new_text_value`,
  `effective_date` required, `change_source` import/import_default/manual/auto_default/checked (+ `pay_scale`
  `pb_pay_scales/models/change_source.py:9-12`, `pay_review` `pb_pay_scales/models/review_dated.py:65-68`), `changed_by/at`, `notes`);
  writer `log(contract, template, old, new, source, notes, user, effective_date=None→today, import_batch, old_text, new_text)` :78-110.
- Add employee writes lines in `_pb_nh_lines` `create_ext.py:232-270`: only CHANGED usual answers; `Line.create({contract_id,
  advantage_template_id, amount})` (sudo, NH6); trail `Change.log(contract, template, rule.default_value, item['amount'], 'manual',
  notes="Chosen when the person was added", effective_date=contract.date_start)` :258-265. Order: contract created with
  `pb_skip_fill_in` → `_pb_nh_lines` → `flush_all` → `_pb_fill_in_defaults()` (`create_ext.py:208-230`), so the fill fills the rest.
  Values ride in context `NH_CTX` from `_pb_nh_extra` (`create_ext.py:104-122`: `contract.usual [{code, amount}]`, `scheme_id`,
  `payroll_country`, `contract_kind`, `pin_note`, `type_id`).

---

## D. The evaluation kernel

### D.1 `hr.formula.sample.data._evaluate_rules_with_dependencies(input_values, readonly=False, errors=None)`
`pb_hr_payroll_formula/models/formula_sample_data.py:597-640+`.
- `input_values`: dict **keyed by rule code** → value (numbers, or text for text/date kinds). Returns a NEW dict: inputs + every
  rule's result by code (inputs missing → `default_value`; constants → `constant_value`).
- `readonly=True` → `steps = config._pb_formula_steps(rules)` (memoised `application_payroll_source.py:290-296`) →
  `formula_program.run_sample(steps, input_values, errors)` (`formula_program.py:133-181`). Docstring: "`readonly=True` guarantees
  ZERO writes" (no `_compute_dependencies`, no `evaluate()` diagnostics). `readonly=False` writes on the shared rules (do not use).
- `errors` out-param `{code: message}` — **almost never filled**: `formula_program._evaluate` (:109-130) catches every eval error and
  returns 0.0 (NH52). Precedent that finds real errors: `_Engine.diagnose(results)` `pb_formula_studio/models/take_home.py:150-181`
  (re-runs each compiled formula letting the exception through; `why` = `zero` | `unreadable` | `other`).
- Engine: `build_steps` :79-104 (topological sort `FormulaEvaluator._topological_sort`, column map letter→code, Excel→Python,
  `excel_semantics.assert_safe_expression`, `compile`); `run_sample` = one pass + up to 2 forward-reference passes (:154-180).

### D.2 Record-free evaluation — **possible, and already shipped twice**
- **`_Engine(env, config)`** `pb_formula_studio/models/take_home.py:68-181`: compiles once; `evaluate(inputs)` = `run_sample`;
  in-memory lines through `hr.payslip.new({'line_ids': [Command.create(v)…]})` (:114-124 — the lines MUST belong to a payslip, see F);
  `net()`, `totals()`, `diagnose()`, `upstream(codes)` :183-205. Line specs = `appears_on_payslip` and `wants_number` (:85-99), band asked
  once per spec via `pb_pay_band()` / `pb_counts_in_totals()` (:102-107).
- Used with **no employee, contract or payslip**: `pb.pay.package._offer_subject` returns `{'inputs': {}, 'employee': None, 'contract':
  None, 'source': 'defaults'}` (`pb_pay_package/models/offer_total.py:202-227`) and `offer_open` builds `_Engine` on it (:229-271).
  `take_home_open(config_id)` with neither payslip nor contract also runs on `{}` inputs (`_th_subject` `take_home.py:239-318`; `take_home_open` :433-470).
- What a plain `{code: value}` dict LACKS vs. `_get_formula_input_values` (which needs a payslip: `self.contract_id` lines and wage,
  `self.employee_id` mapped fields and feed hits, `worked_days_line_ids`, `date_from/date_to` + `payslip_run_id` for period codes,
  clock hours, work segments — B.2): worked days, `PAYMONTH`/`STDDAYS`/period codes, mapped record fields, connected-system values,
  clock hours, segment proration. A record-free builder must fill period codes itself (`pay_period.default_standard_work_days`,
  `fill_period_inputs` are pure helpers used at :852-871) or state that they are the scheme's usual values.
- Cost: real-records example **~1.0 s (11 rules) / ~1.5 s (300 rules) uncached, ~45 ms cached** (`NEWHIRE_P4_REPORT.md:139-147`); the
  cost is the employee+contract create (~0.8 s in 17 `hr.employee.create` overrides), evaluation ~0.05 s on 300 rules.
  Record-free: **~3 ms per evaluation** on a 50-component scheme (`WDGAP_W2_D1_REPORT.md:175`); the take-home search takes 30-34
  evaluations, ceiling 200 (`WDGAP_W2_C_REPORT.md:161`, `take_home_solver.py:47-51`). Before compilation: 8.77 s/person on 409 rules
  (`formula_program.py:8-9`).
- Example cache: `CACHE_SECONDS = 300`, `CACHE_SIZE = 256` per worker (`payslip_example.py:85-86`), key = db, company, scheme,
  write_date, rule count, md5 of rule content incl. `is_contract_component`/`default_value` (`_example_key` :288-305, NH53).
- Locks/refusals (real-records path only): `_example_lock` `pg_try_advisory_xact_lock(company, calendar)` → "busy" (:174-184, NH54);
  `_seat_refusal` → "An example cannot be shown because your plan has no free employee place." (:186-203, NH7).

### D.3 Dependency graph ("this line uses these lines")
- Stored: `formula_dependencies` (C). Walk: `_Engine.upstream(codes)` `take_home.py:183-205` (letters → codes via `column_letter`,
  transitive). Studio: `_expand_refs(formula, by_col)` `pb_formula_studio.py:251-271` (ranges expanded, strings masked). Validator
  `get_dependency_order` `formula_engine/validator.py:350`. No ready "used by" (downstream) API — invert `formula_dependencies` yourself.
- Client-side AST + evaluator: `parseFormula(formula)` / `evalFlowNode(node, ctx)` `pb_formula_studio/static/src/js/formula_flow_eval.js:178-260`
  (nodes `num, str, ref{col}, range{start,end}, op, cmp, fn{name,args}`; IF/functions; `ctx.values` = letter→value). A "small mirror"
  of the engine for the Studio flowchart, kept equal by batteries (:1-21); in `web.assets_backend` of pb_formula_studio (manifest :112).
  Formula Studio's tree builder `dnode()` `formula_studio.js:3098-3110`.

### D.4 Functions the engine supports — ONE list
`pb_hr_payroll_formula/formula_engine/functions.py` `_TABLE` :61-152: SUM, AVERAGE, MIN, MAX, ABS, ROUND, IF, IFERROR, ISBLANK, AND, OR,
NOT, COUNTA, POWER, SQRT, CEILING, FLOOR, SUMIF, SUMIFS, ROW, SUBTOTAL, MOD, SIGN, ROUNDUP, ROUNDDOWN, INT, DATE, YEAR, MONTH, DAY, DAYS,
DATEDIF, EDATE, EOMONTH, VLOOKUP, BRACKET (tax-table lookup), TRUE, FALSE. Refused: TODAY, NOW (:175-178). `FUNCTION_NAMES` :155,
`function_list()` :213 (palette RPC). Text comparison (`IF(F5="La Nga",…)`, `<>`) is supported (strings tokenised; `value_kind` note
`formula_rule.py:820-826`). Rounding is Excel's (`excel_semantics.excel_round`), never Python `round()` on money.

---

## E. Explaining a formula (all on AbstractModel `pb.formula.studio`, `pb_formula_studio/models/pb_formula_studio.py`)

- `OP_GLYPH = {'+': '+', '-': '−', '*': '×', '/': '÷'}` :58.
- `_col_to_rule(rules)` :237-239 → `by_col = {column_letter: rule}` (the usual way `by_col` is built; inline copies at :1425, :2477…).
- **`_tokenize(rule, by_col)`** :273-301 → list of `{'kind': 'src'|'num'|'ref'|'op', 'text', ['col']}`: input → `[{'kind':'src','text':'From
  contract / import'}]`; constant → one `num` ('{:,.0f}'); empty → `src` "No formula yet". Regex `[A-Za-z]+\d+|\d+\.?\d*|[+\-*/()%]`
  (:286) — **drops function names (IF, ROUND, MIN…), commas, comparisons, strings, `:` ranges and bare codes.**
- **`_explain(rule, by_col)`** :303-332 → one English sentence: input "Comes from each employee's contract or the monthly import.",
  constant "A fixed value applied to every employee.", complex (parens or >3 refs) "<name> is calculated from A, B, …", simple
  "<name> is computed as A times 0.2." — **hard-coded English, not wrapped in `_()`** (untranslatable). `_explain_vi` :15122-15135
  (hard-coded Vietnamese); `_explain_localized(rule, by_col, lang)` :15118-15120.
- **`_readable_formula(formula, by_col)`** :15052-15064 → `'Basic × 0.2'` style string (same token regex, names for known letters).
- **`explain_formula_ai(rule_id, lang='en')`** :15075-15094 → `{'text', 'source': 'ai'|'deterministic'}`; `lang` is `'vi'` or `'en'` only
  (no Indonesian); tries `_llm_chat(_build_explain_prompt(...))` (:15096-15115: sends component name, category, excel_formula,
  depends_on names) to an **OpenAI-compatible endpoint** (`LLM_BASE_URL/API_KEY/MODEL` params :43-47, default `gpt-4o-mini`);
  on `LLMUnavailable` or any error → deterministic floor. `ai_status()` :15066-15070.
- **Gates.** None of these methods checks a group. `explain_formula_ai` browses `hr.formula.rule` in the caller's env → needs read on
  `hr.formula.rule`, which is **`pb_hr_payroll_formula.group_formula_user` (read) / `group_formula_manager` (write)**
  (`pb_hr_payroll_formula/security/ir.model.access.csv:2-7`; group implies `om_hr_payroll.group_hr_payroll_user`,
  `formula_security.xml:21-29`); company rule `formula_rule_comp_rule` `formula_security.xml:82-91`. A plain HR officer
  (`hr.group_hr_user`) has **no read on rules or schemes**. Studio edit affordances `_can_edit()` :1736-1745 (system or formula manager).
  Take-home calculator gate `PAY_TEAM_GROUP = 'om_hr_payroll.group_hr_payroll_user'` (`take_home.py:44`, `_th_may_use` :216-218).
  Add employee reads schemes with **sudo behind `require_hr`** (`studio.py:123-125`, `_scheme` :653-659) — the precedent for an HR
  officer: compute server-side under sudo, return plain words/numbers, never call Studio RPCs from the studio client.

---

## F. Pay bands and totals — the one pay-band rule (`om_hr_payroll/models/pay_bands.py`)

- `hr.payslip.line.pb_pay_band()` :57-69 → `'GROSS'|'BASIC'|'ALW'|'DED'|'NET'|'ERCOST'|False`: from `pay_role` first
  (`_PB_BAND_BY_ROLE` :35-42: earning→GROSS, deduction→DED, net→NET, employer_cost→ERCOST, info/mixed→False), else category code
  (`_PB_BAND_BY_CATEGORY` :47-55). The line's `pay_role` is the rule's `net_role`, `component_detail` its `net_role_detail`.
- `pb_counts_in_totals()` :71-89 → False when no band; True for NET; otherwise `not component_detail`.
- `pb_pay_totals()` :91-117 → `{'gross','deductions','net','employer_cost'}`; DED and ERCOST summed as `abs()`; gross = the scheme's own
  GROSS band, else BASIC+ALW. `pb_lines_in_band(band)` :119-134, `pb_net_line()` :168-189; `hr.payslip.pb_pay_totals()/pb_net_amount()` :195-203.
- **Overrides:** `pb_payruns/models/payslip_money.py:21-41` totals **per `slip_id`** (signed-deduction refunds) — lines without a payslip
  total 0 → in-memory lines must be created inside `hr.payslip.new(...)` (`take_home.py:114-124`); `pb_retro/models/retro_backpay.py:868+`
  (back-pay lines).
- Employer cost: band ERCOST from `net_role='employer_cost'`. "Build from a total" leaves out an employer line that already reaches gross
  (India `ERCOST = GROSS + …`) — `pb_pay_package/models/package.py:16-21, 57-76`.
- The example maps bands to kinds: GROSS/BASIC/ALW → earning, DED → deduction (abs), else skipped; zero lines hidden; not counted →
  `info` (`payslip_example.py:372-386`); the take-home card `_BAND_KIND` `take_home.py:53-54` adds `net`, `employer`.

---

## G. Formula Studio component editor (`pb_formula_studio/static/src/xml/studio.xml`)

- INPUT body :1351-1381: "Source field mapping" (`data_source_field`) :1354-1355; `data-coach="fs-usual-answer"` field :1359:
  label **"Usual answer for a new contract"** when ticked, else "Default value" (:1360-1361); Yes/No buttons (`usualControl==='toggle'`)
  :1362-1368, `<select>` of words :1369-1376, number input :1377; help (ticked only) **"Every new contract for a person this scheme pays
  starts with this value. Leave 0 for none."** :1378. "Words for each value" :1382-1386.
- **The tick box** sits inside the collapsed **"Advanced"** section, under the heading **"Manual classification (does not affect
  import)"** (:1387-1391, :1392): `<label class="ce-tog">…<span>Contract component</span>` :1525 and, when ticked, "Requires new
  contract" :1526. **No help text is rendered for either.** Field `string` is "Contract Component" (C).
- Save: JS `formula_studio.js:3028` → `pb.formula.studio.save_component(rule_id, vals)` (`pb_formula_studio.py:2705-2762`; allow-list
  `_EDIT_FIELDS` :2647-2655 includes `default_value`, `is_contract_component`, `requires_new_contract`; extended with `value_labels` by
  `pb_formula_studio/models/studio_fillin.py:23-26, 75-84`); snapshot `get_component_edit` :2659-2703 (+ `value_labels`, `value_kind`,
  `value_label_view` `studio_fillin.py:48-59`). F7 version row for `VERSIONED_FIELDS` (`formula_rule.py:21-27`, not incl.
  `is_contract_component`/`default_value`).
- **Live scheme:** the isolation gate refuses only `MONEY_FIELDS = {'excel_formula','python_formula','constant_value','column_type'}`
  on an ACTIVE scheme with a "Scheme change" route (`pb_hr_payroll_formula/models/scheme_gate.py:43-44, 219-239`). **Ticking/unticking
  "Contract component" or changing the usual answer on a live scheme needs no approval and takes effect at once.**
- Translations: `pb_formula_studio/i18n/vi_VN.po:3713` msgid "Contract component" (shared with `source_vocab.js:65` source chip and
  `pb_formula_studio.py:849/9952`), :11064 "Requires new contract", :16578 "Usual answer for a new contract", :16584 the help;
  `pb_hr_payroll_formula/i18n/vi_VN.po:3321` "Contract Component", :10529 "Requires New Contract" (also stray `vi_VNnew2.po`).
  **`id_ID.po` of both modules has none of these msgids.** No pb_learn lesson quotes "Contract component" or the usual-answer label
  (only the coach anchor `fs-usual-answer` exists in the template).

---

## H. Hiring offer

- **Stored pay** — `pb.hiring.offer` (`pb_hiring/models/offer.py`): `currency_id` required, default company (:135-137; `draft_for`
  takes the requisition's :330); `line_ids` O2m `pb.hiring.offer.line` (:138-139); stored computes `monthly_total`, `annual_total`
  (:140-145, `_compute_totals` :237-252, `OFFER_PERIOD_YEAR` `hiring_common.py:496`). **No country field** (requisition
  `country_id` or company country — `offer_cost.py:57,74`, `offer.py:347`). Line model `offer.py:844-885`: `name, kind, amount, period,
  note, annual_amount`; `kind` ∈ earning/statutory/benefit/perquisite/bonus (`hiring_common.py:475-481`), `period` ∈
  monthly/yearly/one_time (:483-487); deductions typed negative (:863-865).
- `pb_pay_package` adds `pb_item_code`, `pb_item_wage`, `pb_from_total` on lines and `pb_total_config_id` ("Split with pay scheme"),
  `pb_total_note` on the offer (`pb_pay_package/models/offer_total.py:36-56`); `_basic_line()` override prefers the tagged wage line
  (:60-69), base `pb_hiring/models/offer_closure.py:313-326` (biggest positive monthly earning).
- **Record-free scheme split already on the offer:** "Build from a total" — `pb.pay.package.offer_open/offer_solve/offer_use`
  (`offer_total.py:229-375`) on `_Engine` with `{}` inputs; schemes from `_offer_schemes` (`pb.scheme.map.usual_scheme` first, :169-199);
  `offer_use` writes the split as the offer's monthly lines (:353-366); refuses when offer money ≠ scheme money (:283-290). Gate
  `_offer_get` :146-157 = `_require_recruit` + `_is_hiring_reader` ("The offer's figures are with the hiring team."). Card
  `BuildTotalCard` `pb_pay_package/static/src/js/build_total.js:28-202` (+ `xml/build_total.xml`: totals :106-111, items :113-123,
  payslip lines :125-140), opened from the offer by `offer_total.js:15-34` / `xml/offer_total.xml:9-22` (draft, money not locked,
  `canRecruit`). Older: employer-cost profile `pb.hiring.cost.profile` + `action_calculate_employer_cost` (`pb_hiring/models/offer_cost.py:13-128`,
  inline eval, strict, writes HTML `pb_cost_result`).
- **Offer editor UI:** `pb_hiring/static/src/xml/hiring_board.xml:1192-1290` (inside `pb_hiring.RoleDetails` :1034; totals/lock
  :1202-1217, line list :1219-1242, add/letter/preview :1253-1268), line dialog :844-893 (`type="number" step="1000"`); JS
  `pb_hiring/static/src/js/hiring_board.js` `startLine/cancelLine/saveLine/removeLine/setOfferField` :1481-1517; server
  `_act_offer_line` `pb_hiring/models/pb_hiring_a3.py:548-590` (draft only), payload `_offer_row(full=True)` :398-451.
- **Letter:** report `pb_hiring/report/hiring_offer_report.xml:23-74` prints `o.rendered_html`; `action_prepare_letter` `offer.py:431-462`
  with `_placeholder_values` :377-405 and `${lines}` = `_lines_table()` :407-429 (name, money, period word); seeds
  `data/letter_template_offer.xml:44-48, 84-88`; doc-studio override `pb_doc_studio_hiring/models/offer.py:166-209`. Candidate page
  `/hiring/o/<token>` facts `page_facts()` `offer.py:682-710`, template `views/offer_token_templates.xml:204-223` — **the candidate already
  sees every line and the totals**.
- **Into Add employee:** `pb.new.hire._offer_wage` `pb_new_hire/models/hiring.py:212-217` (sudo `_basic_line()`), `_offer_row` :220-250
  (`wage`, `wage_currency`), `offer_draft(offer_id)` :268-313 → draft keys `name, offer_id, personal, date_start, department_id,
  payroll_country (team's), job_id|job_title, parent_id, parent_name, buddy_id, buddy_name, wage` — `wage` only when the offer currency
  equals the country's, else `wage_note` "The offer's pay is in %(theirs)s. Type the monthly wage in %(mine)s." (:305-312). **No scheme,
  no offer lines travel.** `bringAcross` `new_hire_studio.js:574-612`. Joining: `joining_draft` `pb_joining/models/studio.py:93-120`,
  `_offer` override :43-63 (J-25); JS `pb_joining/static/src/js/studio_joining.js:30-57`. `load(prefill)` (`studio.py:296-346`) accepts
  only `department_id, job_id, job_title, parent_id, fill_job_id` — no pay keys.
- Offer lines → contract: only Hiring's own "Confirm they joined" `_ensure_contract` + `pb_pay_package._pbpk_contract_lines`
  (`offer_total.py:71-138`). The studio's override `PbHiringOfferNewHire._ensure_contract` (`pb_new_hire/models/hiring.py:738-746`)
  returns the studio's contract without `super()` — whether `pb_pay_package`'s lines are still written depends on MRO order of the two
  overrides: **NOT VERIFIED**.
- **Who sees the offer wage:** `monthly_total`, `annual_total`, `line.amount`, `line.annual_amount` have
  `groups='pb_hiring.group_hiring_user'` (`pb_hiring/models/privacy_p4.py:584-604`); payload masking `facade_p4.py:206-232`
  (`money_locked`, `_is_hiring_reader` :51-58); record rules `pb_hiring/security/pb_hiring_security.xml:331-388, 442-451`. Add employee reads
  the wage with sudo (`hiring.py:215,221`) for anyone past `require_hr` who can reach the offer (since J-25 also HR without Hiring rights).

---

## I. Contract panel and "change pay"

- Files: `pb_contracts/models/pb_contract_360.py` (2021 lines), `models/contract_approval.py` (`pb.contract.proposal`),
  `static/src/js/contract_360.js` (`CdEditor` :305, `Contract360Drawer` :442, registry `pb_contracts_drawer` "contract_360" :1656),
  `static/src/xml/contract_360.xml` (`CdEditor` :65, `CdComponentRow` :127-181, drawer :183), `scss/contract_360.scss`. Opened from
  `pb_employee_vault/.../employee_360.js:164`, `pb_people/.../people.js:137`, `pb_contract_lifecycle/.../contractlife_board.js:429`,
  `pb_pay_scales/.../scales_tab.js:552`.
- Payload `_cd_payload` :545-568 (`ok, error, currency, can_write, unmask_wage, header, terms, readiness, components, history`); terms
  table `_TERMS` :82-115 (wage `('money','wage',"Monthly wage",…)` :83).
- `_cd_components(contract, symbol, can_write, unmask)` :1024-1110 → `{rows, count, fillin{n, can_check}, other_rows, other_count,
  scope{state: scoped|unassigned|off, schemes}, total (False unless unmask), explainer, addable}`; row from a line `_cd_comp_row`
  :910-957:
  ```python
  {'edit_kind','options','value_hint', **fill_tag, 'id','virtual': False,'code','name','value_type','amount','text_value',
   'display','lower','upper','bounded','bounds_hint','value_kind','requires_new_contract','template_id','writable',
   'fills_from','fills_label','fills_tone'}
  ```
  virtual row (scheme component with no line) `_cd_virtual_row` :960-1014 (`id: False, virtual: True, amount 0.0`).
- `save_contract_360(contract_id, terms=None, components=None, note=None)` :1711-1816; `components = {edits: {line_id: {amount}|{text_value}},
  adds: [{template_id|code, amount|text_value}], removes: [line_id]}` (built `contract_360.js:1347-1368`); terms written in place
  (:1745-1749), lines `sudo().write/create/unlink` (:1762-1807), trail `_cd_log_component` :1947-1969 with **`effective_date` = today,
  source `manual`**; returns `{ok, saved, refusals, msg, detail}`. Judges: `_cd_judge` :1325-1359 (allow-list `_cd_writable_map`
  :1316-1322 = `_TERMS` fields on hr.contract; picker models `_M2O_WHITELIST` :58-61), `_cd_judge_components` :1447-1616 (edit must name a
  line of this contract, no text/amount mix, bounds `_cd_bounds_refusal` :1666-1679, duplicates refused, a mapping-filled line cannot be
  removed :1608-1612).
- `_cd_propose` :1819-1919: skipped under context `pb_contract_approved_write` (CONTRACT_WRITE); approval when a money term
  (`MONEY_TERMS` `contract_approval.py:45-46`: wage, dates, structure, calendar, state) or any component changes; `propose('terms', …,
  payload={contract_id, terms, components, note, shown}, facts={wage, touches_pay, components})` :1858-1872 (wage unit = company
  currency); route HR lead, + Finance only when `touches_pay` (`contract_approval.py:137-152`) — **components alone skip Finance**;
  apply `_apply_terms` replays `save_contract_360` (:123-133). **Bug:** approver detail `_proposal_rows` slices
  `payload['components'][:20]` (`contract_approval.py:113`) but the payload holds a dict → raises (KeyError/TypeError by Python version);
  wrapped by `_safe` in the inbox (`pb_approval_config/models/inbox_facade.py:1046-1047`) → detail table probably empty. NOT VERIFIED live.
- Gates (`pb_contract_360.py:41-46, 229-263`): read = `hr.group_hr_user` | payroll officer | admin; write = read + `hr_contract.group_hr_contract_manager`
  + ACL write; **wage visible only to `om_hr_payroll.group_hr_payroll_manager` or admin (`_cd_unmask_wage` :261-263); component amounts are
  NOT masked** (only `wage` and `total`, :605, :696, :1104).
- UI today: wage cell → `CdEditor` money input (`contract_360.xml:96-101, 296-311`; `startTerm`/`commitTerm` `contract_360.js:841-867`);
  doors beside it: **"Work back from take-home"** (xml:322-325, js:881-898, registry `pb_take_home` from
  `pb_formula_studio/static/src/js/take_home.js:308-319`) and **"Build from a total"** (xml:327-330, js:909-944, registry `pb_build_total`
  `pb_pay_package/static/src/js/build_total.js:202`); Components tab xml:350-496 (Paid by + "Change pay scheme" :355-382, rows :403-407,
  `startComp/commitComp` js:1106-1142, other values :432-448, adds :451-484); preview `runPreview` js:1370-1396 → `preview_contract_360`
  (:1975); save js:1457-1500 ("Sent for approval").
- **Dated changes:** lines have no dates; the contract panel writes in place dated today; it never makes a new contract version
  (docstring :16-19). Dated pay change EXISTS in **`pb_job_change`** ("Change job", `reason_kind 'pay'` "Pay change",
  `pb_job_change/models/job_change.py:84-89`; `effective_date` "Starts on" :159; `change_pay`, `new_wage`, `line_ids` :187-192; writes wage +
  lines + `Change.log(..., effective_date=effective)` at start date, future = `scheduled`, cron `_cron_start_due` :1507; approval process
  `jobchange` :57; `GATE_GROUPS` :60-64 (HR manager, pay manager, payroll manager), `PAY_GROUPS` :66-69, `_may_see_pay` :282-285; RPC
  board `job_change_board.py` `get_flow` :309, `preview` :513, `save` :573, `send` :591; doors `pb_start_for_employee` :1742-1786 with
  `START_KEYS` incl. `wage`, `lines`, `effective_date`). Others: `pb.pay.change` (`pb_pay/models/pb_pay_change.py:57`, applies at once
  :402-447, ignores its date), scale rise (`pb_pay_scales/models/scale_raise.py`, dated), dated pay review
  (`pb_pay_scales/models/review_dated.py:131-262`), Records desk (`pb_records`, dated by start date). Proration of a mid-period line change
  only on the import path when `config.use_proration` (`payroll_import_batch.py:2642-2772`); back pay `_prepare_retro_adjustments` :2795-2884.
- Dependency note: `pb_contracts` must not depend on the formula engine (`pb_contract_360.py:1648-1652`, "binding non-goal"); the
  pay doors are registered INTO it by `pb_formula_studio` / `pb_pay_package` registries — the precedent for a "Change pay" builder door.

---

## J. Joining page (`pb_joining`)

- Files: `controllers/joining.py` (360 lines), `controllers/papers.py`, `models/joining.py`, `codes.py`, `items.py`, `http.py`,
  `studio.py`, `hiring.py`; template `views/joining_pages.xml` (`pb_joining.phone` :11-102), `views/papers.xml`; frontend assets
  `static/src/js/joining_page.js`, `signature.js`, `joining_icons.js`, `phone_icons.js`, `scss/joining_page.scss` (root `.pbjp`)
  (`__manifest__.py:12-27`). ACL system only.
- Page states in `pb_joining.phone`: inactive/problem :27, code :28-38, **welcome :39-44** (manager card :41, note :42), **hub :45-56**
  (progress ring, section list, "Send to HR"), section :57-94, sent/day_one :95-97 (`day_card` :6-10); sign list/paper `papers.xml:20-37`.
  Sections `_section_info` `models/joining.py:145-153` (personal, id_number, bank "Where your pay goes", tax, emergency, papers, sign, day).
- Gate: token `secrets.token_urlsafe(32)` (`joining.py:42`), `_for_token` :197-211 (sudo search, expires `first_day` + 14 days);
  address limit 10 / 600 s (`controllers/joining.py:25-38, 65-71`); 6-digit one-time code, sha256 of `token:code`, 10 min (48 h when HR
  shows it), 5 issues/h, 1/min, 5 wrong → 15 min lock, `hmac.compare_digest` (`models/codes.py:28-86`); session `session['pbj']` 14 days
  + signed host-only cookie `pbj_device` (`codes.py:89-115`); every POST `csrf=True`; no-store / no-referrer / noindex headers, path
  redacted (`models/http.py:8-35`).
- Data access: controller rebinds `j = j.with_env(request.env).sudo().with_company(j.company_id)` (`controllers/joining.py:75`); reads
  offer buddies, manager, prejoin, contact, catalogue `_catalogue()` via `pb.new.hire` sudo (`joining.py:102-106`). **It never reads
  `hr.contract`, offer lines or totals today; no figure is shown.** `pb.joining.offer_id` `joining.py:28` (ondelete set null),
  `origin` `invited|hiring` :27 — an **invited** person has no offer, hence no pay source. `employee_id` :65 not rendered.
- A read-only "Your pay" card fits as an `<article class="pbjp-card">` on `welcome` (beside the manager card) or in `hub` above the list;
  it must NOT become a key of `_section_states` (it would change `progress` and block `_send_to_hr`, `joining.py:155-193`). Public QWeb:
  no OWL, no `ic()` (inline icon template `pb_joining.icon`), words from Python as plain values (RC49), `[hidden]` rule (RC72).
- Existing rules on showing pay to the person: `/my/pay` "Your pay, explained" (`pb_pay/controllers/portal.py:58-145`, rails: session's own
  employee, no comparison, company switch :11-19) gated by **`pb.pay.settings.portal_enabled`** default True "People can see their own pay
  explained" (`pb_pay/models/pb_pay_settings.py:26-30`; off text `portal.py:68-74`); payslips `/my/payslips[/<id>]`
  (`pb_me_portal/controllers/portal.py:540, 638-664`, held payslips hidden `models/hr_payslip_ess.py:23-33`). No `/my/contract` route.
  The design principle for joining: the wage is "shown as already held, never asked again" (`docs/handovers/joining/JOINING_DESIGN.md:32-33`).

---

## K. Build conventions

- **Worktree** from `origin/19.1` (never the main checkout, ~180 commits behind). Release tooling is on origin now (§0).
- **Local runtime** (`docs/handovers/wfsetup/WFSETUP_FACTS.md:599-606`): `~/odoo19`, `./venv/bin/python odoo/odoo-bin -c odoo-local.conf`;
  addons path official addons FIRST then the repo; Postgres 16 `/usr/local/opt/postgresql@16/bin`, role `odoo`; `./runtests.sh <module> [db]`;
  manual `-d <db> -i|-u <module> --test-enable --test-tags /<module> --stop-after-init --log-level=info`. Recipe DB `upd_p6_t_tpl`
  (no active scheme, US/USD company, lacks pay scales / contract rules — NH16, NH67) → copy + `-u all`; walk DBs used: `nh1_base`…`nh6_base`
  (NEWHIRE reports). `--test-enable` hangs after "post-tests" (NH39); post_install tests only run for `-u`'d modules (NH39); exact
  dbfilter (J-1); test run binds `http_port` (NH82); two local servers share a cookie (NH81).
- **Tests:** `@tagged('post_install', '-at_install', 'newhire')` (`pb_new_hire/tests/test_new_hire.py:16`), `TransactionCase`,
  `new_test_user`; bases `NewHireCommon` (`test_new_hire.py:17`, `studio()`, `draft(**kw)`, `approve()`), example tests
  `tests/test_payslip_example.py` (:25; `took_ms` :277). Static gate `pb_new_hire/tests/test_static.py`: S1 no vendor name :47, S2 every
  icon exists :71, S3 no emoji :85, S4 `_t` import form :90, S6 every screen sentence in the `.pot` :100, S5 action tags :118.
- **Icons:** `icon(name, size=16)` cached over `ic()` (`pb_new_hire/static/src/js/studio_util.js:24-31`; a new markup per call re-inserts DOM).
  Set = `IC` map in `pb_import_kit/static/src/js/import_icons.js` (173 names, e.g. `banknote, calculator, coins, wallet, percent, sigma,
  scale, sliders, target, trendingUp, trendingDown, chevronDown, chevronUp, pencil, sparkles, info, lock, eye, eyeOff, undo, refresh,
  fileText, layers, landmark, receipt, shield, building, calendar, plus, minus, x, check`); unknown name = a tick. Money helpers
  `moneyNumber/money/parseMoney/groupTyped` `studio_util.js:97-156`.
- **Translations:** `i18n/vi_VN.po`, `i18n/id_ID.po` (+ `.pot`); three markers per entry (`#. module:`, `#. odoo-python|odoo-javascript`,
  `#: code:addons/<m>/<path>:0`); export `odoo-bin i18n export -c <conf> -d <db> -l vi_VN -o x.po <module>`; append as text, never
  `polib.save` (NH87); JS `import { _t } from "@web/core/l10n/translation";` exactly (WS40), literal first argument (WS39), no `%%` (WS22);
  `_()` not inside lambdas/generators (NH93); a word on a new QWeb view needs that view's occurrence (NH86).
- **Assets** `pb_new_hire/__manifest__.py:94-122`: backend = scss, `studio_util, step_who, step_role, step_pay, step_soon, step_docs,
  step_sched, step_welcome, step_check, record_panel, new_hire_studio, takeover` + `xml/new_hire_studio.xml` + joiners board + hiring patch;
  frontend = `welcome_page.scss`. Dependency closure of `pb_new_hire` already contains `pb_formula_studio` and `pb_hr_payroll_formula`
  (`pb_scheme_map` depends on the formula module, `pb_scheme_map/__manifest__.py:42-52`); `pb_contracts`' closure contains neither;
  `pb_hiring`'s contains `pb_hr_payroll_formula` but not `pb_formula_studio`; `pb_pay_package` depends on `pb_formula_studio, pb_contracts,
  pb_hiring` (`pb_pay_package/__manifest__.py:28-32`).
- **Versions at 2882e1a38:** `pb_new_hire 19.0.1.8.2`, `pb_joining 19.0.1.0.1`, `pb_formula_studio 19.0.1.217.0`,
  `pb_hr_payroll_formula 19.0.1.176.1`, `pb_contracts 19.0.1.17.0`, `pb_hiring 19.0.2.23.9`, `pb_pay_package 19.0.1.1.1`,
  `pb_job_change 19.0.1.1.0`, `pb_learn 19.0.20.12.0`, `om_hr_payroll 19.0.1.8.7`, `pb_payruns 19.0.3.6.0`.
- **Release:** `tools/release.sh <looks|normal|risky> <sync,csv> [upgrade,csv]` (`tools/release.sh:1-30`: stages `git archive` of committed
  modules, refuses standard addons via the server's tracked list, refuses uncommitted changes) → `ops/pb_release.sh` on the server (lock,
  notes START/DONE, nightly-backup check, stop, per-module copy, upgrade the five DBs, cron restore, asset purge, start, warm, hash+version
  check). Five DBs: payobook, payobook_template, p0clone, rize, sudima; never abm (`JOINING_LEDGER.md` R3-R4,
  `JOINING_BUILD_HANDOVER.md:451-475`). Note: `-u pb_hr_payroll_formula` upgrades a large dependent tree (cf. NH83 for pb_bank_ocr) — plan the window.
- **Ledger gotchas that will bite this feature:**
  - NH3 (wage rounds to contract currency), NH6 (HR officer read-only on lines, refused by bands → sudo behind `require_hr`), NH7 (seat
    limit refuses the preview create), NH8 (proposal payload JSON-plain, replayed by another user — new line keys must be plain),
    NH12 (`0 in (None,'',False)` is True — an "off"/0 line was dropped once), NH11 (no JS globals in OWL templates), NH27 (child reading
    another component's reactive does not re-render), NH50/NH51 (savepoint side effects), NH52 (errors → 0), NH53 (write_date static in a
    transaction; hash content), NH54/NH55 (example lock, one request at a time), NH18 (screens we do not own read company currency),
    NH20/NH32 (contract letter pay gate = payroll manager), NH44 (asset bundle not rebuilt locally), NH61-NH64 (Chrome translation, cached
    web translations, language switch, `with_context(lang=)`), NH70 (Learn is en+vi only), NH86/NH87/NH93 (PO rules), NH1 (contract
    `payroll_country` VN/ID/IN/SG/MY only).
  - WS18 (never NaN/"" into reactive state — every amount box), WS11/J-8 (Sass `min()/max()` — use `calc`/`unquote`), WS17 (inline inputs
    need `display:inline-block`), WS24 (no state writes in `onWillStart`), WS39/WS40/WS42 (`_t` literals/import, `formatFloat` never
    `toLocaleString`).
  - J-10 (public QWeb `editable` name is the website's), RC49 (public pages get plain values), RC72 (`[hidden]` on public pages), RC14
    (asset purge — the release script does it), RC68/70 (new dependency in the shared addons dir).

---

## L. Lessons and screen replicas that describe step 3 (a screen change must update them)

- `pb_learn/static/content/learn_content.json`: scenario `sc_people` step `wage`, anchor `rep-newemp-wage` (:15375) — "Step 3, Contract and
  pay. Type 9,500,000 in the Monthly wage box and press Enter." (:15384), title "Type the monthly wage" (:15399); intent `addperson`
  (:5831, :5878 "…contract and pay, then Send"); intent `whosees` "Inside a contract, the Monthly wage is hidden unless…" (:11386);
  lesson **L29** contract slide-over (key :35762; steps `cd-tabs` :35964, `rep-cd-terms` :36001-36010 "The Monthly wage here is what the
  next pay run reads." :35998, `rep-cd-comps` :36034, `rep-cd-history` :36067, `cd-save` :36100; "Monthly wage" :35815); lesson **L33** step 2
  `rep-cd-terms` (:38983). No hit for "usual answer", "Contract Component", "Usual answer for a new contract", "Example payslip".
- `pb_learn/static/src/engine/screens.js`: practice Add employee `newEmployeeHTML` :355-437 ("filled in with the company's usual answers"
  :360, "Monthly wage" :370, rail "Contract and pay" :377, "Steps 4 to 6 already hold your company's usual answers." :394, step 3 :422,
  input `rep-newemp-wage` "Monthly wage, ₫" :423-425); practice contract slide-over in `employees()` :633-716 (`rep-cd-comps` "Paid by"
  :705-706); fixture `pb_learn/static/src/engine/fixture.js:1160-1190` (terms "Monthly wage" :1164, components BASIC/ALW/OT/UNION).
- `pb_learn/static/src/anchors.json`: `rep-newemp-wage` :2552, `nh-step-pay` (reserved) :2226-2230 "…the monthly wage in the scheme's money,
  the trial period and the scheme's usual answers for this person.", `nh-example` (reserved) :2262-2266, `nh-rail` :2196-2199, `cd-*` :2088-2103,
  `rep-cd-*` :2537-2539. No lesson uses an `nh-*` anchor.
- `learn_manifest.py`: `pb_people/learn_manifest.py:153` (column "Monthly wage"); `pb_formula_studio/learn_manifest.py:397, 598`
  ("Components in the contract drawer"). Joining report asks L29 to mention Joining (`JOINING_REPORT.md:114-118`).
- Product strings that will change (with `.po` entries): "Monthly wage" `new_hire_studio.xml:523,527` (`pb_new_hire/i18n/vi_VN.po:2709`,
  `id_ID.po:2709`); "The scheme's usual answers" xml:599 (`vi_VN.po:4751`, `id_ID.po:4751`); "Usual answer for a new contract"
  `studio.xml:1360` (`pb_formula_studio/i18n/vi_VN.po:16578`).

---

## M. Risks a designer should know

1. **The Rize India gap is a real-pay gap, not a preview bug.** A studio hire on a scheme whose pay is driven by a contract component
   (INANNFIX) gets `hr.contract.wage` = 6,000 that nothing reads, and no INANNFIX line → 0 on the real pay run too (B.2 rung 5, B.3).
   The "You set" lines must therefore be ALL contract components (zero default included) — a new filter beside
   `_pb_usual_answer_rules()`, which must stay as is for the automatic fill (`_pb_fill_one`), and `_usual_choices` / `_pb_nh_lines` must accept
   the new set. Whether the wage box survives on schemes with no BASIC/WAGE/BASE input (or wage mapping) is a design decision; the
   wage is still a required field in `_validate` (`studio.py:807-808`) and `hr.contract.wage` is required.
2. **A contract component's `default_value` is only a "usual for new contracts" — the pay run uses 0 when the line is missing**
   (`hr_payslip_formula.py:835-840`). A record-free builder that starts from `default_value` would disagree with the pay run for any
   existing contract lacking a line. Corollary: **ticking "Contract component" on a live scheme instantly turns that input to 0 for every
   person without a line** (no approval: `scheme_gate.py:43-44`). Renaming the tick box should come with that warning.
3. **Two evaluation paths can disagree.** The real-records example (~1-1.5 s, full input ladder incl. period codes, worked days, clock,
   mapped fields) vs. `_Engine` on a dict (~3 ms per evaluation, scheme usual values only, D.2). Live as-you-type per line needs the fast
   path; honesty needs a stated rule for which number the screen shows (and the existing notes in `_notes`).
4. **Errors become 0 silently** (NH52); use the `diagnose` probe (`take_home.py`) before claiming a figure.
5. **Boolean components** are fill kinds but never payslip lines (C, `wants_number`); text components need a text editor (C.1).
6. **Explanations:** `_tokenize/_explain/_readable_formula` cannot read IF/ROUND/MIN/ranges/strings and are hard-coded English
   (`_explain_vi` the only other language; no Indonesian; not `_()`); `explain_formula_ai` sends component names and formulas to an external
   LLM endpoint when an API key is set, and has no group gate beyond rule read (which HR officers lack). The JS `parseFormula`/`evalFlowNode`
   (D.3) is the only parser that understands functions — but it is a mirror, not the engine.
7. **Access is uneven across the four homes:** Add employee = `require_hr` (sudo reads, HR officer sees wage + payslip example today);
   contract panel = wage only for payroll managers but **every component amount visible to any reader** (I); Change job pay = `PAY_GROUPS`;
   take-home calculator = payroll user; offer money = hiring reader (H); joining page = the person (no switch today besides `/my/pay`'s
   `portal_enabled`). A Pay Builder showing take-home and every component in Add employee/contract panel widens who sees salary — decide per home.
8. **Pay totals need a payslip parent** (`pb_payruns/models/payslip_money.py:21-41`): build lines inside `hr.payslip.new()`.
9. **Three existing pay-change paths** (contract panel in place/today, Change job dated + approval, Pay › Changes immediate). "Change pay
   (before/after)" in the contract panel either routes through `pb_job_change` (dated) or stays in-place (undated); `requires_new_contract`
   is only a label. Contract-panel approval detail likely broken for component changes (`contract_approval.py:113`), and component-only
   changes skip the Finance step.
10. **Templates are global by code** (no company): two schemes using the same code share one catalogue row and its bounds; out-of-bounds
    amounts raise (`om_hr_payroll/models/hr_contract.py:31-43`).
11. **Offer → studio carries only the wage**, not lines or the split scheme; offer currency can differ from the scheme's (offer_solve refuses,
    studio drops the wage with a note). `pb_pay_package` lines reach a studio contract only if MRO lets its `_ensure_contract` run — NOT VERIFIED.
12. **Joining page:** public, sudo, no OWL; numbers must be computed server-side and passed as plain values; invited joiners have no offer;
    showing pay behind link+code is a new privacy surface (the candidate offer page already shows lines, `offer_token_templates.xml:204-223`).
13. **Formula Studio label rename:** the msgid "Contract component" is shared by the source chip (`source_vocab.js:65`) and two Python
    occurrences; change the studio.xml label with a NEW msgid; `id_ID.po` lacks the editor's words in both modules today.
14. **The scheme-state question:** usual answers/fill use ACTIVE schemes only (`_pb_fill_schemes`, `contract_fill_in.py:495-512`); whether the
    Rize India "focused payroll" scheme is active, and whether it carries a wage mapping row, is NOT VERIFIED (no DB access).
15. `pb_contracts` must stay free of a formula-engine dependency — a Pay Builder in the contract panel must enter through a registry door
    (precedents `pb_take_home`, `pb_build_total`).
