# VALUEKIND — Phase 1: a value knows what it is

**Programme:** VALUEKIND (`VK`) · **Phase:** 1 of 3 · **Date:** 2026-08-27
**Ledger:** `docs/FORMULA_ENGINE_CONVENTIONS.md` — binding, read C12/C13/C18 before starting.
New gotchas from this phase append to C18 starting at **115**.

---

## 0. The one-paragraph version

A payroll column arrives from a connected system, passes through two coercion layers that
each guess whether it is a number, and lands in `hr_payslip.formula_input_values`. Neither
layer knows what the column is *for*, and both fail toward `float()`. On ABM's live June
2026 run that turns `"Ho Chi Minh Branch"` into `0.0`, `"2025-06-02"` into `0.0`,
`"11709"` into `11709.0`, and `"0071001182392"` into `71001182392.0`. The Source Atlas grid
then faithfully renders what it was given. This phase gives every component a **declared
value kind**, derives it from evidence the schema already holds, and makes the two coercion
layers and the display honour it.

**The kind is not cosmetic.** ABM's own scheme reads `LOCATION` inside
`IF(F5="La Nga", …)`. It is a *text input to the pay calculation*, and it is currently `0.0`.

---

## 1. Scope

### In scope

1. `value_kind` + `value_kind_source` + `value_kind_reason` on `hr.formula.rule`, with an
   auto-classifier and a person-wins override.
2. The classifier's strongest new signal: **operator context** — does a formula apply
   arithmetic to this reference, or compare it to a string literal?
3. Honour the kind at the **wire** (`transform_value` / `_feed_values_for`).
4. Honour the kind at the **resolver** (`normalize_input_value`).
5. Honour the kind in the **Source Atlas** grid, journey drawer and XLSX download.
6. A read-only **audit** action that lists, per scheme, every component whose stored values
   disagree with its kind — the thing that would have caught this in March.

### Binding non-goals

- **Do NOT recompute any payslip.** `pb_source_atlas` is strictly read-only (its
  `test_07` counts rows before and after every endpoint). Repairing ABM's June run is
  Phase 3 and is the owner's call, run by run.
- **Do NOT change `column_role`, `net_role`, or their classifiers.** `value_kind` *reads*
  them. Two classifiers writing one another's fields is how COLROLES and NETROLE would
  start disagreeing.
- **Do NOT touch `formula_dependencies`' existing output.** Operator context is a NEW,
  separate field. `_compute_dependencies` feeds the topological order of the whole engine;
  changing what it emits changes evaluation order.
- **Do NOT rewrite the Excel→Python converter.** Read `excel_formula`; do not re-derive
  `python_formula`.
- **No new user-visible string may contain "Odoo".** Standing rule, all products. Use
  "Payobook", "the system", or a neutral phrase. Technical identifiers (`from odoo import`,
  model/XML ids, `odoo-bin`, log messages, this document) are untouched.

---

## 2. Verified plumbing — do NOT re-derive any of this

Every fact below was read off the code or the live `abm` database on 2026-08-27.

### 2.1 Where the value dies

| # | Site | File:line | What it does |
|---|---|---|---|
| S1 | Wire | [`integration_field_mapping.py:389-398`](../../pb_hr_payroll_formula/models/integration_field_mapping.py#L389-L398) | `if source_data_type in ('number','float','integer','currency'): value = float(value)`; on `ValueError` **returns `self.default_value`** (a Float, default `0.0`). The original text is discarded. |
| S2 | Wire default | [`integration_field_mapping.py:73-74`](../../pb_hr_payroll_formula/models/integration_field_mapping.py#L73-L74) | `source_data_type = fields.Selection(SOURCE_DATA_TYPES, default='number')`. A mapping created without an explicit type IS a number mapping. |
| S3 | Resolver | [`payroll_import_batch.py:3761-3778`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3761-L3778) | `normalize_input_value` floats any string that `coerce_numeric_string` accepts. Its only escape hatch is `is_employee_code_rule(rule)` (header-marker match), which is why bank accounts still lose leading zeros. |
| S4 | Display | [`atlas.js:281-289`](../../pb_source_atlas/static/src/js/atlas.js#L281-L289) | `num()` — `typeof value === "number"` → `Intl.NumberFormat`. Cosmetic only; it is showing the truth. |

`_feed_values_for` ([`integration_field_mapping.py:567-632`](../../pb_hr_payroll_formula/models/integration_field_mapping.py#L567-L632))
is the single shared entry to S1 from both the import pre-pass and the live pay-run path.
Fix S1 there and both paths move together — that is exactly why J3 unified them.

### 2.2 Live evidence (abm, 2026-08-27)

Mapping rows with `target_rule_id` set: **25**. Typed `number`: 6 · `float`: 8 ·
`integer`: 1 · `string`: 10.

The four mistyped ones — all created with **no `source_sample_value`**, so nothing ever
corrected the `default='number'`:

```
source_field    source_data_type  sample   target_rule_code  column_role
Dateofjoining   number            <null>   DATEOFJOININ      contract
EmployeeID      number            <null>   EMPLOYEECODE      identity
Employeestatus  number            <null>   EMPSTATUS         contract
LocationName    number            <null>   LOCATION          profile
```

`Bank_Account_Number_VND` is correctly typed `string` with sample `0071001234567`, and
`EMPBANKACCOA` is *still* stored as `71001182392.0` — proof that S3 is an independent
defect from S1 and that fixing only the mapping types is not enough.

A payslip's `formula_input_values` on run 13 (152 slips):

```json
{"BANKNAME": "NHTMCP Ngoại Thương Việt Nam (Vietcombank)", "DEPARTMENT": "Human Resources",
 "EMPLOYMETYPE": "Probation", "SHUIPARTICIP": "YES",
 "DATEOFJOININ": 0.0, "LOCATION": 0.0, "EMPSTATUS": 0.0, "LASTWORKIDAY": 0.0,
 "EMPLOYEECODE": 11709.0, "EMPBANKACCOA": 71001182392.0}
```

The raw feed row (`hr_payroll_import_line.raw_data_json`, batch 873) still holds the truth:
`'Dateofjoining': '2025-06-02'`, `'LocationName': 'Ho Chi Minh Branch'`,
`'Employeestatus': 'Resigned'`, `'EmployeeID': '11682'`. **The source material is intact** —
Phase 3's repair reads it, it does not need a re-sync from the vendor.

Distinct `LocationName` values across batch 873: `Ho Chi Minh Branch` ×86, `La Nga` ×62,
empty ×4.

### 2.3 The signals available to a classifier

| Signal | Field | Notes |
|---|---|---|
| Formula references | `hr.formula.rule.formula_dependencies` (Char, stored, computed from `excel_formula` at [`formula_rule.py:1417-1491`](../../pb_hr_payroll_formula/models/formula_rule.py#L1417-L1491)) | **Holds COLUMN LETTERS, not codes** — `NETPAY → "BP,BP5,CC,CC5,CD,CD5"`. Match against `{code, column_letter, original_column_letter}`, as `is_excluded_people_column` already does. Regex-derived, so a bare letter match is NOISY. |
| Declared usage | `column_role` ∈ `payroll·identity·profile·contract·bank·reference`, `column_role_source` ∈ `auto·user` ([`formula_rule.py:611-625`](../../pb_hr_payroll_formula/models/formula_rule.py#L611-L625)) | COLROLES. On abm: EMPLOYEECODE/FULLNAMEVN/PITNUMBER = `identity`, BANKNAME = `bank`, LOCATION = `profile`. |
| Pay role | `net_role` ∈ `earning·deduction·net·employer_cost·info·mixed`, + `net_role_confidence` ([`formula_net_role.py:569-600`](../../pb_hr_payroll_formula/models/formula_net_role.py#L569-L600)) | NETROLE. No default — empty means "nobody has asked yet". |
| Counts-something | `looks_like_a_quantity(name, code)` ([`formula_net_role.py:447`](../../pb_hr_payroll_formula/models/formula_net_role.py#L447)) | Conservative: one money word anywhere → False. |
| Prints | `appears_on_payslip` | Weak on abm: `EMPBANKACCOA` and `INSBOOKNO` both have it True. Report this; do not act on it in Phase 1. |
| Value shape | `is_texty_sample(value)` ([`column_role_classifier.py:275-292`](../../pb_hr_payroll_formula/models/column_role_classifier.py#L275-L292)) | Already handles dates, and the leading-zero-integer case explicitly. **Reuse it. Do not write a second one.** |
| Vendor type | `hr.integration.endpoint.field.source_data_type`, vocabulary `SOURCE_DATA_TYPES` ([`integration_endpoint.py:92-101`](../../pb_hr_payroll_formula/models/integration_endpoint.py#L92-L101)) | Already includes `date`, `datetime`, `boolean`, `string`. The vocabulary is fine; the default and the failure mode are not. |

### 2.4 Why "used in a formula" is NOT the determinant

Two ABM formulas, both of which "use" their reference:

```
ACTUALMEAL   = IF(F5="La Nga", 0, (X5/AB5*AD5))
EMPTRADEUNIO = IF(F5="La Nga", 0, IF(F5="HCM", IF(AS5="YES", IF($BS5>0, 45000))))
```

`F5` = LOCATION (text, compared) · `X5` = BASESALARY (number, divided) ·
`AS5` = SHUIPARTICIP (text, compared — and it works today only because its mapping
happened to be typed `string`).

Bare-reference usage says LOCATION, BASESALARY and SHUIPARTICIP are all "used". **Only the
operator tells them apart.** That is the new signal this phase adds.

Consequence on the live run: all 152 payslips compute `EMPTRADEUNIO = 0`, because
`0.0 = "La Nga"` and `0.0 = "HCM"` are both false. `ACTUALMEAL` is 0 for all 152 as well,
but for an unrelated reason (`ACTUWORKHOUR`/`STANWORKHOUR` are themselves 0.0), so
restoring LOCATION does not move it. **Restoring LOCATION alone changes no money on run 13** —
verify this before and after; if a total moves, stop and report.

---

## 3. Architecture

### 3.1 The field

On `hr.formula.rule`, beside `column_role` — same file, same section, same shape, so the
two read as one family:

```python
value_kind = fields.Selection([
    ('money',      'Money'),        # currency; grouped, currency decimals
    ('quantity',   'Quantity'),     # hours/days/count; grouped, ≤2 dp, no symbol
    ('rate',       'Rate'),         # percentage or multiplier
    ('identifier', 'Identifier'),   # digits that are a NAME — verbatim, zeros kept
    ('text',       'Text'),
    ('date',       'Date'),
    ('boolean',    'Yes / No'),
], string='Value Kind', default='money', required=True,
   help="What this component's value IS. Decides how it is stored, compared and shown.")

value_kind_source = fields.Selection(
    [('auto', 'Auto-classified'), ('user', 'Set by a person')],
    default='auto', required=True)

value_kind_reason = fields.Char()   # the sentence the drawer shows
```

`default='money'` matches today's effective behaviour for a payroll column, so a legacy
scheme that never runs the classifier is byte-identical. The classifier is what moves a
component off it — **classification is a verb, not a reflex** (the NETROLE doctrine at
[`formula_net_role.py:565-568`](../../pb_hr_payroll_formula/models/formula_net_role.py#L565-L568)).

Write the same `_check`/`write` override COLROLES uses so any explicit user write flips
`value_kind_source` to `'user'` — clone [`formula_rule.py`](../../pb_hr_payroll_formula/models/formula_rule.py)'s
`column_role_source` handling; `test_column_roles.py:138-147` is the precedent test.

### 3.2 Operator context — the new signal

New module `pb_hr_payroll_formula/models/formula_operand_context.py`, import-free of
`odoo` (same doctrine as `column_role_classifier.py`, so `tools/*_battery.py` can load it
standalone — see C12).

```python
def operand_contexts(excel_formula) -> dict[str, set[str]]:
    """{REF: {'arith', 'strcmp', 'numcmp', 'textfn'}} for every ref in one formula."""
```

Rules, in order of confidence:

- `REF` adjacent to `+ - * / ^`, or inside `SUM/AVERAGE/MIN/MAX/ROUND/ABS/CEILING/FLOOR`
  → `arith`
- `REF = "literal"` or `REF <> "literal"` (either side) → `strcmp`
- `REF = 123` / `REF > 0` / `REF >= 0` → `numcmp`
- `REF` inside `LEFT/RIGHT/MID/LEN/TRIM/UPPER/LOWER/CONCATENATE/TEXT` → `textfn`

Strip string literals first — `_strip_string_literals` already exists on `hr.formula.rule`
([`formula_rule.py:1433`](../../pb_hr_payroll_formula/models/formula_rule.py#L1433)) — then
re-scan the ORIGINAL for the `= "…"` pattern, because that is the one place the literal
itself is the evidence.

Expose it as a stored Char on the rule, `formula_operand_roles`, computed alongside (NOT
inside) `_compute_dependencies`. **Its own `@api.depends('excel_formula')`, its own
method.** C18.115 below.

### 3.3 The ladder

`hr.formula.rule._classify_value_kind()`, first match wins, each rung writing
`value_kind_reason`:

| # | Rung | Verdict |
|---|---|---|
| 1 | `value_kind_source == 'user'` | keep — never overwritten |
| 2 | any formula applies **`arith`** to this ref, **or** `net_role ∈ (earning, deduction, net, employer_cost, mixed)` | `quantity` if `looks_like_a_quantity(name, code)` else `rate` if the label/formula says % else `money` |
| 3 | the ONLY contexts are `strcmp` / `textfn` | `text` — or `boolean` when every observed value is in a yes/no vocabulary |
| 4 | `column_role ∈ ('identity', 'bank')` | `identifier` |
| 5 | vendor `source_data_type ∈ ('date','datetime')` | `date`; `'boolean'` → `boolean` |
| 6 | observed values (see 3.4): all `is_texty_sample` | `text`; all leading-zero digits → `identifier` |
| 7 | `column_role != 'payroll'` | `text` |
| 8 | fallthrough | `money` |

**Rung 2 beats rung 3** only on `arith`. A bare column-letter reference with no operator
context is *not* rung 2 — it is noise, exactly as
[`payroll_import_batch.py:3915-3918`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3915-L3918)
already warns. This is the single most important line in the ladder: get it wrong and
LOCATION classifies `money` again.

**Rung 7's direction is deliberate.** Today's default is `number`, whose failure mode is
*destruction*. `text`'s failure mode is a value that looks slightly wrong and can be
corrected. Always fail toward keeping the data.

### 3.4 Observed values

Rungs 3, 6 need evidence. Read it from `hr_payroll_import_line.raw_data_json` for the most
recent `done` batch on the config, capped at 200 rows, via the mapping's `source_field`.
**Never** from `formula_input_values` — that blob is downstream of the coercion this phase
exists to fix, and would confirm its own damage.

### 3.5 Honouring the kind

**S1 — wire.** In `transform_value`: float only when the *target rule's* `value_kind` is
`money`/`quantity`/`rate`. When a float is required and fails, do **not** return
`default_value` — return the raw and set `has_transform_error` + `transform_error_msg`
(the flagging machinery is already there at
[`:360-375`](../../pb_hr_payroll_formula/models/integration_field_mapping.py#L360-L375)).
Silently substituting 0 for an unparseable value is the actual defect.
Keep the `is_required` `ValidationError` branch exactly as it is.

**S2 — default.** Change `source_data_type`'s default to `'string'` for NEW rows only.
Add a migration that re-types existing mappings from the endpoint-field catalogue where one
exists, and leaves the rest alone. **List every row changed in the migration log.**

**S3 — resolver.** `normalize_input_value(rule, value)` consults `rule.value_kind`:
`money/quantity/rate` → today's behaviour verbatim; everything else → return the stripped
string untouched. Delete nothing: `is_employee_code_rule` becomes rung 4's input, not a
special case in the resolver.

**S4 — Atlas.** `get_grid` puts `'t': component['kind']` on each cell next to `v`/`n`;
`_atlas_components` carries `value_kind` into the component meta. `atlas.js` gains
`fmtCell(cell, comp)`:

- `identifier` → `String(v)` verbatim, no grouping
- `date` → the user's locale via `formatDate` from `@web/core/l10n/dates` (VN → `04-04-2022`)
- `money` → existing `money()`
- `quantity`/`rate` → `Intl.NumberFormat`, no currency symbol
- `text`/`boolean` → `String(v)`

Same switch in the journey drawer and in `_atlas_write_value`
([`atlas_download.py:370-378`](../../pb_source_atlas/models/atlas_download.py#L370-L378)),
where `identifier` must use `write_string` so Excel keeps leading zeros.

### 3.6 The audit

`hr.formula.config.action_audit_value_kinds()` — read-only, returns per component:
declared kind, kind the evidence suggests, count of stored values that contradict it, and
the first three offending values. This is the surface that names the LOCATION class of
defect out loud instead of leaving it to a screenshot.

---

## 4. Safety rails

1. **Read-only means read-only.** No `create`/`write`/`unlink` anywhere in `pb_source_atlas`.
   `test_07` counts rows around every endpoint — keep it green.
2. **No payslip is recomputed in this phase.** Not by the classifier, not by the audit, not
   by a migration.
3. **Prove neutrality on run 13.** Capture `pb_total_gross` / `pb_total_net` /
   `pb_employee_count` for abm run 13 before and after deploying Phase 1. They must be
   identical — Phase 1 changes how *new* values are stored and how *stored* values are
   shown, not what run 13 already computed.
4. **`normalize_input_value` is on the hot path** for every payslip in every run. A regression
   there is a wrong payroll, not a wrong screen. Every branch needs a test.
5. **Migration must be idempotent and must not touch a `column_role_source='user'`-equivalent
   row** — i.e. never overwrite a `value_kind_source='user'`.
6. **`pb_hr_payroll_formula` must stay installable headless** (C1). The classifier may not
   import from `pb_formula_studio` or `pb_source_atlas`.
7. **Bump `version` in every manifest whose assets change** (C2). Current:
   `pb_hr_payroll_formula` `19.0.1.90.0`, `pb_source_atlas` `19.0.1.0.0`.
8. **Deploy to `/odoo/odoo-server/addons` only**, per-module `rsync -a --delete`, and upgrade
   **all four** databases (`payobook`, `payobook_template`, `abm`, `acme`). Never
   `--delete` into the addons directory itself.

---

## 5. Test cases

Numbered; report pass/fail against these numbers.

**Classifier — `tests/test_value_kind.py` (new)**

1. `operand_contexts('=IF(F5="La Nga",0,(X5/AB5*AD5))')` → `F` has `strcmp` and NOT `arith`;
   `X`, `AB`, `AD` have `arith`.
2. `operand_contexts('=IF(AS5="YES",IF($BS5>0,45000))')` → `AS` `strcmp`; `BS` `numcmp`.
3. `operand_contexts('=SUM(AE5:AX5)+BM5')` → every letter AE..AX and BM has `arith`.
4. A ref appearing in BOTH an arithmetic and a comparison context resolves to rung 2
   (numeric wins) and `value_kind_reason` says both were seen.
5. String literals containing operators (`=IF(A1="a+b",…)`) do not create a phantom `arith`.
6. LOCATION-shaped rule (role `profile`, `strcmp` only, 152 texty observed values) → `text`.
7. EMPLOYEECODE-shaped rule (role `identity`, no formula ref, numeric-looking values) →
   `identifier`.
8. Bank-account-shaped rule (role `bank`, values with leading zeros) → `identifier`, and
   the leading zeros survive `normalize_input_value`.
9. `value_kind_source='user'` survives a re-classification pass untouched.
10. A rule with no formulas, no role, no observed values → `money` (the neutral default).

**Wire — extend `tests/test_transform_preview.py`**

11. `transform_value("Ho Chi Minh Branch")` on a mapping whose target is `value_kind='text'`
    returns the string, not `default_value`.
12. Same mapping typed `number` with target `value_kind='money'` and an unparseable value:
    returns the raw AND sets `has_transform_error` — it does NOT return `0.0`.
13. `is_required=True` still raises `ValidationError`. Unchanged.
14. `_feed_values_for` neutrality: a numeric wire delivering a numeric value produces a
    byte-identical hit dict to before this phase.

**Resolver — extend `tests/test_journey_truth.py`**

15. `normalize_input_value` on a `money` rule: identical to today for `'12,500,000'`,
    `'1.5%'`, `''`, `None`, `True`, `12.0`.
16. `normalize_input_value` on an `identifier` rule with `'0071001182392'` returns the
    string with leading zeros intact.
17. `normalize_input_value` on a `date` rule with `'2025-06-02'` returns the string.

**Atlas — extend `pb_source_atlas/tests/test_atlas.py`**

18. `get_grid` returns `t` on every cell, and it matches the component's `value_kind`.
19. `test_07` (no writes) still passes with the classifier and audit reachable.
20. XLSX: an `identifier` cell is written with `write_string`; open the produced file and
    assert the leading zero survives.

**Live — abm**

21. Run 13's `pb_total_gross` / `pb_total_net` / `pb_employee_count` are byte-identical
    before and after deploy.
22. `action_audit_value_kinds()` on ABM's config names LOCATION, DATEOFJOININ, EMPSTATUS
    and EMPLOYEECODE as contradicted, and does not name BANKNAME or DEPARTMENT.
23. The Atlas grid shows Employee Code as `11450` (no comma) and Date of Joining as
    `04-04-2022` for a slip whose raw row carries that date. Chrome-MCP; screenshot.

---

## 6. Deploy & verify

```
sudo rm -rf /tmp/deployVK && mkdir -p /tmp/deployVK
rsync -az --exclude=__pycache__ --exclude='*.pyc' --exclude='.DS_Store' \
      pb_hr_payroll_formula pb_source_atlas Payobook19v2:/tmp/deployVK/
# per module:
sudo rsync -a --delete /tmp/deployVK/<m>/ /odoo/odoo-server/addons/<m>/
```

Then, **per database** (`payobook`, `payobook_template`, `abm`, `acme`):
upgrade both modules; after any JS/SCSS change
`DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'`; restart.

Verify: hash each module tree both sides (skip `__pycache__`, `*.pyc`, `.DS_Store`);
compare each manifest version to `ir_module_module.latest_version` per DB, normalising the
`19.0.` series prefix.

---

## 7. Report back

1. Pass/fail per numbered test, with the failure output where it failed.
2. Test 21's four numbers, before and after.
3. Test 22's audit output verbatim — the full contradicted list for ABM, not a summary.
4. The migration log from S2: every mapping row whose `source_data_type` changed.
5. Any component the ladder classified in a way you disagree with, and which rung did it.
6. New gotchas, drafted as C18 entries numbered from 115.
7. Anything you had to change that this document did not authorise, and why.

---

## 8. Ledger entries this phase creates

Append to `docs/FORMULA_ENGINE_CONVENTIONS.md` § C18, continuing the numbered list at 115:

> **115. `formula_dependencies` holds COLUMN LETTERS and throws the operator away.**
> `_compute_dependencies` (`formula_rule.py:1417`) regex-scrapes `excel_formula` into a
> flat comma list of refs — `NETPAY → "BP,BP5,CC,CC5,CD,CD5"` — and it feeds the engine's
> topological order, so its output must not change. It cannot answer "is this a number",
> because `IF(F5="La Nga",…)` and `X5/AB5` both produce a bare ref. Operator context is a
> SEPARATE stored field with its own `@api.depends`; never widen the dependency compute.
>
> **116. A type default whose failure mode is destruction is the wrong default.**
> `hr.integration.field.mapping.source_data_type` defaulted to `'number'`, and
> `transform_value` returned `default_value` (Float, 0.0) when the float failed. Four
> mappings on ABM created without an explicit type silently converted
> `"Ho Chi Minh Branch"`, `"2025-06-02"` and `"Resigned"` to `0.0` on every run, one of
> them load-bearing inside `IF(F5="La Nga",…)`. When a guess can destroy data, default to
> the option that preserves it and flag the disagreement.
>
> **117. Coercion happens in two places, not one.** Fixing the mapping's type is not enough:
> `normalize_input_value` (`payroll_import_batch.py:3761`) independently floats any
> numeric-looking string, which is why `EMPBANKACCOA` lost its leading zeros despite a
> correctly-typed `string` mapping. Any "the value has the wrong type" report must check
> both sites.
>
> **118. Never classify from `formula_input_values`.** It is downstream of both coercion
> sites, so evidence drawn from it confirms its own damage. The intact source material is
> `hr_payroll_import_line.raw_data_json`, which survives on every done batch.

---

## 9. Phases 2 and 3 (design only — do not build in this phase)

- **Phase 2 — the wire tells you.** Surface the audit on the Integrations mapping board:
  a wire whose declared type disagrees with what it has been delivering gets a chip and a
  one-click re-type. Plus `value_kind` on the Formula Studio component editor.
- **Phase 3 — repair ABM.** Re-resolve run 13's inputs from `raw_data_json` under the new
  contract, diff every payslip, and present the diff for approval before anything is
  written. **Includes the owner's ruling of 2026-08-27: change `EMPTRADEUNIO`'s `"HCM"`
  literal to `"Ho Chi Minh Branch"` to match the feed vocabulary.** That change makes
  45,000 start applying to the ~86 employees who also satisfy `SHUIPARTICIP="YES"` and
  `$BS5>0`, so it must ship WITH a before/after payslip diff, never on its own.
