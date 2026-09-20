# COLROLES Phase 1 — Roles exist (backend, invisible, zero behavior change)

Read `docs/handovers/COLROLES_LEDGER.md` FIRST — its standing rules (white-label, terse output,
commit, deploy ritual, migration house style) and locked decisions CR-A1…A7 bind this phase.

## Scope

1. `column_role` + `column_role_source` on `hr.formula.rule`; `column_role` joins VERSIONED_FIELDS.
2. Pure-Python classifier module + lexicons (single source of truth for identity markers).
3. Typed contract components (amount|text) via `_inherit` in pb_hr_payroll_formula (CR-A3).
4. Both import wizards assign roles + apply role defaults to NEW imports; red/green font semantics (CR-A4).
5. Migration backfilling roles on existing rules (conservative, idempotent).
6. De-triplicate identity marker lists in payroll_import_batch.py (classifier is the source).
7. `pb.formula.studio.reclassify_roles(config_id)` RPC (backend only, no UI).
8. Role column in multisheet Review list + backend formula-rule views.
9. Deploy to all 4 DBs; live-validate; ABM one-off remediation (21 red columns → contract components).

**Binding non-goals**: NO studio frontend changes beyond the reclassify RPC (no lens, no sidebar,
no serializer changes — Phase 2). NO input_values exclusion (Phase 3). NO bank/mapping model changes
(Phase 3). NO change to what existing configs compute (CR-A7): a payslip computed before and after
this phase must be identical.

## Verified plumbing facts (do not re-derive)

- `hr.formula.rule`: pb_hr_payroll_formula/models/formula_rule.py. VERSIONED_FIELDS :16-22.
  `column_type` :110 (input/formula/constant, required). `component_type` :124 (free-text Char —
  DO NOT touch, CR4). `data_source_field` :228 (raw header text). `appears_on_payslip` :323
  (default True). `report_visible` :342 (bold header). `is_contract_component` :348 (red header).
  `requires_new_contract` :354. `is_visible_in_grid` :360 (default True). `formula_dependencies`
  :193 — comma-joined referenced codes (built at :1217 `','.join(unique_refs)`), CR2.
- Advantage models (om_hr_payroll/models/hr_contract.py — READ ONLY, extend via _inherit):
  `hr.contract.advantage.template` :117-125 (name, code, lower/upper_bound, default_value);
  `hr.contract.advantage` :8-44 (contract_id, advantage_template_id, related code/bounds, amount:Float);
  `_check_bound_limits` @api.constrains :32-44; `HrContract.create()` :107-114 auto-creates one
  advantage line per existing template on every new contract.
- Audit model `hr.contract.advantage.change`: pb_hr_payroll_formula/models/contract_component_change.py:6-67
  (old_amount, new_amount, change_source import|import_default|manual, import_batch_id).
- Batch (pb_hr_payroll_formula/models/payroll_import_batch.py):
  - Triplicated `employee_code_markers = ('MSNV','EMP CODE','EMPLOYEE CODE','EMPLOYEE ID','EMPLOYEEID')`
    at :1999, :2259, :2729; header-candidate identity lists at :422-425, :751-755, :1778-1781
    (+ :531-533, :2619-2625). Replace the marker tuples with an import from the classifier module;
    KEEP behavior identical (same strings, one definition). Header-candidate lists likewise import
    from the classifier lexicon but keep the exact same effective candidate sets.
  - `_is_employee_code_rule` :2728-2741 — make it role-first (`rule.column_role == 'identity'` short-
    circuits True) with the existing marker heuristic as fallback. Since all migrated identity-role
    rules would ALSO match the markers (migration only certain-assigns identity on marker/mapping
    evidence), behavior stays identical.
  - `_sync_contract_components` :2859-2946 writes `amount`; `_get_or_create_advantage_template`
    :2804-2819 creates templates (hardcoded 0.0 bounds); `_log_contract_component_change` :2832.
  - `_transform_data_to_formula_inputs` builds `contract_component_amounts` from
    `contract.advantages_ids` at :2261-2269 — filter to amount-typed templates only.
  - `_get_rule_raw_value` :2695-2726; `normalize_input_value` :2378-2395.
- Single-sheet wizard (pb_hr_payroll_formula/wizards/formula_import_wizard.py):
  - Color path `_import_from_excel_color_coded` :492-978. Identifier row = header_block_start-1
    (:573); identifier_map :765-771; rule vals :884-906 — `report_visible = is_bold_in_merge` :885,
    `is_contract_component = is_red_in_merge` :886, `requires_new_contract = … and
    is_underline_in_merge` :887. Red font thresholds in `is_red_font` :641-661 (rgb r>150,g<150,b<150
    or r>200,g<180,b<180,r>g,r>b; indexed 2|10). Merge-aware helpers `is_*_in_merge` :629-685.
    GREEN font precedent for value cells: `is_green_color` :1497-1520 (indexed 3|11; rgb g-dominant)
    — mirror those thresholds for a new `is_green_font`/`is_green_in_merge` on header cells.
  - Plain path `_import_from_excel` :231-491 (HeaderDetector; no font reading) — classify with
    header text + sample values only (no colour signals available).
  - `data_workbook` (data_only=True) is loaded :255 — sample values for a column = first ≤10
    non-empty cells below the header row in the data sheet.
- Multisheet wizard (pb_hr_payroll_formula/wizards/multisheet_import_wizard.py):
  - `_analyze_sheet_color_coded` :1960-2202 (contract_component_map/requires_new_contract_map built
    :2085-2129); poured into `hr.formula.multisheet.column.selection` :652-704 (model :3638-3665,
    has `sample_value`); then `hr.formula.multisheet.component.preview` :1154-1157 (model :3447-3470);
    final `rule_vals` :2822-2841. Review Components list view: wizards/multisheet_wizard_views.xml
    ~:191-207 (component preview list). Add `column_role` to both transient models, classify during
    analysis, carry through, render as editable selection column in the Review list.
- Migrations: `pb_hr_payroll_formula/migrations/19.0.1.66.0/post-<slug>.py`; house style per ledger.
  Manifest currently 19.0.1.65.0 → bump to **19.0.1.66.0**.
- Studio RPC home: pb_formula_studio/models/pb_formula_studio.py (AbstractModel `pb.formula.studio`);
  `_can_edit()` gate :663-673. Version 19.0.1.107.0 → **19.0.1.108.0** (Python-only change still
  bumps for per-DB `-u` bookkeeping).
- Existing mappings for migration evidence: `hr.payslip.import.mapping`
  (pb_hr_payroll_formula/models/payslip_import_mapping.py) — target_model_id/target_field_id/
  salary_structure_id/component_id.

## Build spec

### 1. Fields (formula_rule.py)

Exactly as CR-A1. Add `column_role` to VERSIONED_FIELDS. Selection labels are user-visible →
translatable, no "Odoo". Help texts: role = "What this column is for. Only Payroll columns feed
the calculation."; source = "Whether the role was auto-classified or set by a person."

### 2. Classifier — models/column_role_classifier.py (pure Python, no model class)

```python
EMPLOYEE_CODE_MARKERS = ('MSNV', 'EMP CODE', 'EMPLOYEE CODE', 'EMPLOYEE ID', 'EMPLOYEEID')
IDENTITY_HEADERS = (…)   # superset of the batch header-candidate lists :422-425 etc., normalized
PROFILE_HEADERS  = (…)   # phone/gender/marital/address/location/department/job/status/email variants
CONTRACT_HEADERS = (…)   # joining/start/end date, last working day, contract type/status, probation
BANK_HEADERS     = (…)   # account no/number, a/c, bank, bank name, branch, swift, bic, ifsc,
                         # beneficiary, account holder, số tài khoản, ngân hàng, chi nhánh
def normalize_header(s) -> str        # casefold, strip punctuation/diacritics-preserving, collapse ws
def is_texty_sample(v) -> bool        # numeric iff float-coercible AND NOT leading-zero-integer-string
def classify_column(header, *, column_type='input', is_contract_component=False,
                    is_text_component=False, on_identifier_row=False, band_label=None,
                    sample_values=None, is_referenced=False) -> (role, tier, reason)
```

Order (first hit wins; tier certain/likely/default):
1. column_type != 'input' OR is_referenced → ('payroll','certain',…)
2. is_text_component (green font) → ('contract','certain','explicit text component')
3. is_contract_component (red font): samples all-numeric or empty → ('payroll','certain','amount
   component'); any texty sample → ('contract','certain','text component (inferred)')
4. on_identifier_row OR normalized header hits EMPLOYEE_CODE_MARKERS → ('identity','certain',…)
5. Exact normalized-lexicon hit → (role,'certain',…) — bank checked BEFORE profile (\"bank name\"
   must not fuzzy-match a profile term).
6. difflib.SequenceMatcher ratio ≥ 0.82 vs lexicon entries → (role,'likely',…)
7. sample_values present and ALL texty and no lexicon home → ('reference','likely',…)
8. → ('payroll','default','no signal — payroll by policy') (CR-A6)

Vietnamese variants in every lexicon (MSNV, mã nhân viên, họ tên, ngày vào làm, số tài khoản,
ngân hàng, phòng ban, chức vụ …). Keep the module import-clean (stdlib only) so it runs under
plain python3 for tests.

### 3. Typed components — new file models/contract_advantage_typed.py (pb_hr_payroll_formula)

- `_inherit = 'hr.contract.advantage.template'`: add `value_type` Selection
  [('amount','Amount'),('text','Text')], default 'amount', required.
- `_inherit = 'hr.contract.advantage'`: add `text_value` Char; add related
  `value_type` (template's, readonly). Override `_check_bound_limits` (same method name,
  @api.constrains('advantage_template_id','amount')) to skip text-typed rows, else super-logic
  (re-implement the bound check — read om's :32-44 first).
- `_inherit = 'hr.contract.advantage.change'` (or edit our own model file directly —
  contract_component_change.py is OURS): add `old_text_value`/`new_text_value` Char.
- Contract form view (om_hr_payroll/views/hr_contract_views.xml:71-83 shows the components list):
  new inherited view IN pb_hr_payroll_formula adding `text_value` column (optional=show) and
  `value_type` (optional=hide) to that embedded list. Check the exact parent xpath in the om view
  before writing.
- `_sync_contract_components` + `_get_or_create_advantage_template`: accept the rule's inferred
  value kind. Rule-side signal: new Boolean `is_text_component` on hr.formula.rule (set by green
  font or red+texty inference at import; default False; add to _EDIT-adjacent whitelists ONLY in
  later phases). Template find-or-create: if template exists with wrong value_type, DO NOT flip it
  (log warning, respect existing); on create use the rule's kind. Sync branch: text →
  compare/write `text_value` (string compare, strip), log change with old/new_text_value,
  change_source as today; amount → exactly today's float path.
- `_transform_data_to_formula_inputs` :2261-2269: only `value_type == 'amount'` (or no template —
  defensive) advantages enter `contract_component_amounts`.

### 4. Wizards

Single-sheet color path: add `is_green_font`/`is_green_in_merge` (thresholds mirroring :1497-1520,
header band only). At rule-vals time (:884-906): green → is_contract_component=True,
is_text_component=True; requires_new_contract = (red OR green) AND underline. Collect ≤10 sample
values per column from the data sheet; call classifier; set `column_role`, `column_role_source='auto'`.
Role defaults for NEW rules: role != 'payroll' ⇒ `appears_on_payslip=False, is_visible_in_grid=False`
(text components: role 'contract' ⇒ hidden from payslip — correct, they are not pay lines).
Plain path (:231-491): classify with header+samples only; same defaults.
Multisheet: green detection in `_analyze_sheet_color_coded` alongside the red maps (:2085-2129);
`column_role` + `is_text_component` on both transients; classified values poured :652-704 and
:1154-1157; carried into rule_vals :2822-2841; Review list gains editable Role selection column
(place AWAY from component_type nodes — CR4).

### 5. Migration — migrations/19.0.1.66.0/post-<sentence-slug>.py

Schema upgrade pre-creates columns with defaults ('payroll','auto','amount' etc.) on all rows.
The migration only SELECTIVELY downgrades rows still ('payroll','auto'):
1. Skip: column_type != 'input'; is_contract_component; code ∈ any formula_dependencies (split ',').
2. Certain via mappings: hr.payslip.import.mapping rows → hr.employee.account_number/bank_name →
   'bank'; other hr.employee targets → 'identity' if field ∈ {identification_id, barcode,
   employee_id-ish, name, work_email} else 'profile'; hr.contract targets → 'contract'.
3. Certain via markers: normalized data_source_field/name hits EMPLOYEE_CODE_MARKERS → 'identity'.
4. Likely via lexicon exact/fuzzy → assign.
5. Else stays 'payroll'. NO sample-value inference (no reliable samples at migration time).
Does NOT touch appears_on_payslip / is_visible_in_grid / is_text_component on existing rows.
table_exists guard; idempotent (WHERE role='payroll' AND source='auto'); INFO log per config:
counts per role. House docstring per ledger.

### 6. reclassify_roles RPC (pb_formula_studio.py)

`@api.model def reclassify_roles(self, config_id)` — `_can_edit()` gate; run classifier over the
config's rules (with is_referenced from formula_dependencies union; no samples unless
hr.formula.sample.data provides them cheaply — optional); write only column_role_source='auto'
rows whose role would change; return `{'ok': True, 'changed': [{id, code, from, to, tier, reason}],
'counts': {...}}`. No UI this phase.

### 7. Backend views

formula_rule_views.xml: `column_role` in list (optional=show) + form + a Role group-by filter in
search view. Multisheet Review list per §4. Respect CR4 placement.

## Numbered test cases

Classifier (pure python — MUST run and pass locally, e.g. `python3 -m pytest pb_hr_payroll_formula/tests/test_column_role_classifier.py` or a plain script):
1. Table of ≥30 headers (EN+VN: MSNV, Mã nhân viên, Employee Code, Bank Name, Số tài khoản, Date of
   Joining, Phone Allowance, OT 1.5 Hours, Adjustment…) → expected (role, tier).
2. Unknown header, no signals → ('payroll','default').
3. is_referenced=True forces payroll even for 'Bank Name'.
4. on_identifier_row → identity regardless of header.
5. Red + all-numeric samples → payroll; red + ['0071000123456'] → contract (texty leading-zero).
6. Green → contract certain regardless of samples; green+underline handled by wizard flag test 9.
7. is_texty_sample: '123'→False, '0123'→True, 'abc'→True, ''/None excluded, '12.5'→False, '12,5'→False.

Odoo tests (write TransactionCase in pb_hr_payroll_formula/tests/; run locally is NOT possible —
validate via post-deploy probes, but code them for CI):
8. Single-sheet color import fixture: identifier-row column → identity; red numeric → payroll +
   is_contract_component; red texty → contract + is_contract_component + is_text_component;
   green → same as red-texty; bank header → bank role; non-payroll rules get
   appears_on_payslip=False, is_visible_in_grid=False.
9. Green+underline → requires_new_contract=True.
10. Multisheet: role survives selection → preview → rule; Review list renders role column.
11. Text component sync: batch line with text value → template created value_type='text', line
    text_value written, no bound-constraint error, change logged with new_text_value; re-import
    with changed text updates + logs; amount path unchanged (regression fixture).
12. contract_component_amounts excludes text-typed advantages.
13. Migration: fixture config (mix of mapped/marker/lexicon/plain rules) → expected roles; running
    twice = same result; a source='user' row is never touched.
14. `_is_employee_code_rule`: role='identity' rule short-circuits True; unflagged MSNV rule still
    True via fallback.
15. Neutrality (CR-A7): on a fixture config with existing payslip computation, recompute after all
    changes → identical input_values and line amounts.

## Deploy + live verification

1. Local: python syntax compile all touched files; classifier tests green; XML parse checks.
2. Deploy per ledger ritual: `-u pb_hr_payroll_formula,pb_formula_studio` on abm, acme, payobook,
   payobook_template. EXIT=0 ×4. Grep upgrade log (-a) for the migration's INFO lines; record
   per-DB role counts.
3. Post-deploy probes (JSON-RPC via curl or odoo shell-free psql where read-only):
   - psql each DB: `SELECT column_role, count(*) FROM hr_formula_rule GROUP BY 1` — plausible split.
   - payobook: pick one legacy config (e.g. Payobook Retail — End-Month) — confirm all its
     formula/constant rules are payroll; spot-check 'Employee Code'-ish rules got identity.
   - abm config id 7: run `reclassify_roles` via JSON-RPC as admin; record diff.
4. **ABM remediation one-off** (closes the outstanding owner item): on abm, set
   `is_contract_component=True` on config 7 rules matching these 21 workbook-red columns by NAME
   (match on rule.name, fallback data_source_field): Base Salary; Gas Allowance; Phone Allowance;
   Meal Allowance; Responsibility Alowance (sic — match loosely); Parking Allowance; Taxi allowance;
   Recognition Bonus; Other Income; Paid Leave Unused; Other Bonus; Bonus - STIP; Marsh Insurance
   refund (Non-tax); Adjustment; SHUI Participation; TU Participation; Sales Incentive; Thirteenth
   Month Salary; Severance Allowance; Reimbursement Payment; Other Deduction.
   All are numeric → amount components: leave is_text_component False, leave role payroll.
   Use a psql UPDATE or JSON-RPC write; report exactly which rules matched (expect 21 — investigate
   any mismatch, do not force).
5. Chrome-MCP smoke: payobook studio (action-1160) still loads clean, no console errors, problems
   rail loads. (No visual role features expected this phase.)
6. Commit (per ledger): one feature-scoped commit; do not push.

## Report back

- Per-test pass/fail with output for failures; classifier table results.
- Per-DB migration counts + reclassify diffs; ABM remediation match list (21?).
- Any deviation from this spec (what + why), any new gotcha (append to COLROLES_LEDGER.md yourself
  with CR-numbers), files touched, final manifest versions, commit hash.
