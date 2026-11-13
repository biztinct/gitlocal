# COLROLES Phase 3 — Mapping surface + bank accounts + batch consumption

Read `docs/handovers/COLROLES_LEDGER.md` FIRST (standing rules, CR-A decisions, gotchas CR1–CR8+
— Phase 2 may have appended more; honour CR6 in every deploy). Phases 1-2 delivered: role fields +
classifier + typed components (backend, commit 1185009c) and the studio lens/hints (Phase 2 commit —
see git log). This phase delivers the mapping experience: bank destinations, role swim-lanes,
suggestions, and the role-aware batch consumption changes.

Line references: pb_hr_payroll_formula/models/payroll_import_batch.py references are pre-Phase-1
(Phase 1 edited it — re-locate by symbol). pb_formula_studio.py references are pre-Phase-1 symbols.
formula_studio.js references are pre-Phase-2 — Phase 2 edited it, re-locate by symbol.

## Scope

1. `hr.payslip.import.mapping`: `destination_type` ('field' default | 'bank_account') + `bank_role`
   ('acc_number'|'bank_name'|'bank_bic'|'acc_holder_name'); Python constraints; NO SQL unique
   constraint (live DBs may hold duplicates — an upgrade must never brick).
2. Batch: `_sync_employee_bank_account` + `_sanitize_acc_number`; `_get_mapping_updates` filters to
   destination_type='field'; role-based input_values exclusion (guarded).
3. Studio employee-mapping mode: role swim-lanes, bank lane, payroll filter chip, component badges,
   "make text component" action, suggest + accept-all (fixing CR3), unmapped counter chips.
4. Legacy mapping wizard copies the new fields in copy-from-structure.

**Binding non-goals**: NO import-wizard UI changes (Phase 4). NO export changes (Phase 4). NO new
overlay/component — extend the existing employee mode of the mapping overlay + MappingCanvas.

## Verified plumbing facts (do not re-derive; symbols > line numbers)

### Mapping model + legacy wizard
- `hr.payslip.import.mapping` (pb_hr_payroll_formula/models/payslip_import_mapping.py, 44 lines):
  `target_model_id` (ir.model, domain hr.employee|hr.contract), `target_field_id` (ir.model.fields,
  ttype not in o2m/m2m, readonly=False), `salary_structure_id` (→hr.formula.config, required,
  ondelete='cascade'), `component_id` (→hr.formula.rule). No uniqueness constraint.
  With the new fields: `target_model_id`/`target_field_id` become required-in-Python only when
  destination_type='field'; `bank_role` required when 'bank_account' (@api.constrains, clear
  messages, white-label).
- Legacy wizard `hr.payslip.import.mapping.wizard` (wizards/payslip_import_mapping_wizard.py):
  `_copy_mapping_fields` (:33-61) copies target_model_id+target_field_id with component_id=False —
  extend the copied shape with destination_type + bank_role.

### Batch (payroll_import_batch.py — symbols)
- `_get_mapping_updates` (was :1725-1745): iterates mappings, coerces via `_coerce_mapped_value`
  (was :1109-1170 — m2o path does search-by-name-ELSE-CREATE; bank rows must NEVER reach it).
  Filter: `mappings.filtered(lambda m: m.destination_type == 'field')` — do it in
  `_get_model_mappings` callers or inside `_get_mapping_updates` (choose one place, consistently;
  `_sync_employee_contract_mirror_fields` and `_get_mapped_value_for_field` consume mappings too —
  audit every `_get_model_mappings` consumer for bank-row leakage).
- `action_process` per-line order (symbol `def action_process`): employee find/create →
  `_update_employee_from_raw_data` → **INSERT `_sync_employee_bank_account(employee, raw_data)`
  here** → contract get/create+update → `_sync_contract_components` → payslip.
- `_transform_data_to_formula_inputs` (symbol): loop over input rules (`column_type == 'input'`).
  Add the exclusion: precompute `referenced_codes = set()` from all rules' `formula_dependencies`
  (comma-split, CR2); skip a rule iff `(rule.column_role or 'payroll') != 'payroll' AND rule.code
  not in referenced_codes AND not rule.appears_on_payslip`. Neutrality proof (cite in code
  comment): unreferenced ⇒ no formula reads it; not-on-payslip ⇒ line creation reads
  computed_values.get(code, 0) only when appears_on_payslip. Text-component sync is UNAFFECTED —
  `_sync_contract_components` reads raw_data via `_get_rule_raw_value` directly, not input_values.
- `_get_rule_raw_value(raw_data, rule, allow_column_letter=False)` (symbol) — reuse for bank value
  extraction so bank columns resolve by data_source_field/name/code exactly like field mappings.

### Bank sync spec
- Employee→partner: VERIFY the field on hr.employee in the vendored tree
  (/Users/adity/Documents/GitHub/gitlocal/hr/models/hr_employee.py — `work_contact_id` on Odoo 19;
  confirm before coding). `hr.employee.bank_account_id` m2o res.partner.bank exists (hr module).
- `_sanitize_acc_number(raw)`: float+is_integer → '%d' % int(raw); str → strip spaces, NBSP,
  dashes; never int-cast a string (leading zeros survive). Non-integer float / scientific notation
  → return None + line-level warning log ("account number damaged by spreadsheet — enter it as
  text in the source file"); do NOT guess.
- `_sync_employee_bank_account(employee, raw_data)`: collect bank-destination mappings for the
  config; resolve each bank_role's value via `_get_rule_raw_value`; if no acc_number value → no-op
  (never create a bank account without a number). Search res.partner.bank on the employee's partner
  where sanitized acc_number matches (compare sanitized-to-sanitized; acc_number stored sanitized).
  Found → write bank_id/acc_holder_name if provided and different. Not found → create
  {acc_number, partner_id, bank_id?, acc_holder_name?}. res.bank resolve: name =ilike, else BIC
  match if bank_bic provided, else create {name} (+bic if given). Set employee.bank_account_id ONLY
  if currently falsy. Idempotent across re-imports by construction. Wrap per-line in the batch's
  existing error-handling idiom (a bad bank row must not kill the batch line — log + continue).

### Studio mapping surface (pb_formula_studio)
- Overlay + modes: `_mapPrefix` (formula_studio.js, symbol; was :4251) maps mode→RPC prefix,
  covering cycle|api|import|scheme|employee. Overlay template studio.xml ~:1780-1910 (symbol:
  the mapping overlay block; Phase 2 may have shifted). Canvas component:
  static/src/js/mapping/mapping_canvas.js — props contract includes per-item `group` (:43-64);
  left-column filter state `f.left` (:95-97); suggested-wire rendering + confidence chips +
  accept-all (≥0.9 threshold) ALREADY EXIST in the canvas.
- **CR3 fix (mandatory)**: `mapSuggest`/`mapAcceptAll` (formula_studio.js, symbols; were
  :4462-4485) hardcode the `mapping_suggest` RPC — make them `_mapPrefix`-aware
  (`${prefix}_suggest` etc.) so employee mode drives `employee_mapping_suggest`. Verify the other
  modes' server methods actually exist under prefixed names before renaming calls — if a mode has
  no *_suggest, hide the Suggest button for it (`supports_suggest` flag in each mode's data
  payload; default false).
- Server family (pb_formula_studio.py, symbols; were :4727-4851): `_EC_TTYPES`, `_EC_CURATED`,
  `employee_mapping_data(config_id, context_id)` (LEFT=`config.rule_ids` via `_mc_item` — symbol,
  was :3695-3703 — {id,label,sublabel,meta:{col,type,group}}; RIGHT=curated+searched ir.model.fields;
  wires=existing mappings), `ec_search_fields`, `ec_model_fields`, `employee_mapping_create`
  (1:1 both sides via unlink-before-create — extend to bank wires), `employee_mapping_delete`.
  All `_can_edit()`-gated.
- **LEFT items**: `_mc_item` gains `group` = role display name; sort identity → bank → profile →
  contract → reference → payroll; payroll items EXCLUDED by default, included when the client asks
  (`include_payroll` arg or client-side filter chip "Show payroll components" using `f.left` state).
  Amount contract components (is_contract_component, not is_text_component): `meta.badge='Contract
  component'`, non-wirable (create RPC rejects), red-tinted chip, click shows "Synced to the
  contract automatically." Text components (is_text_component): badge 'Text component', also
  non-wirable, indigo-tinted.
- **"Make text component" action**: for a LEFT item with role 'contract'|'reference' and no wire:
  a small action (context menu or hover action consistent with canvas idiom) calling a new RPC
  `employee_mapping_make_text_component(rule_id)` → writes is_contract_component=True,
  is_text_component=True, column_role='contract', column_role_source='user'; returns refreshed
  payload. (Reverse action "Detach component" clears both flags — only when no advantage lines
  exist yet for its code on any contract: check hr.contract.advantage.template by code + its lines;
  else return a friendly refusal.)
- **RIGHT bank lane**: 4 synthetic items ids `b:acc_number`, `b:bank_name`, `b:bank_bic`,
  `b:acc_holder_name`, group "Bank account", labels + short sublabels ("Creates or updates the
  employee's bank account"). `employee_mapping_create` branches on the `b:` prefix →
  destination_type='bank_account', bank_role=<suffix>, target_model/field False.
  `employee_mapping_data` emits wires for bank rows (right id = `b:<bank_role>`).
- **Suggest RPC** `employee_mapping_suggest(config_id)`: for unwired non-payroll LEFT items,
  propose: bank-lexicon hit → matching `b:` card (acc-number-ish → b:acc_number etc.);
  identity/profile/contract → best ir.model.fields candidate from _EC_CURATED + ec_search by
  normalized-label difflib ratio. Confidence: classifier-certain 0.95, likely 0.75, difflib-only
  scaled ≤0.85. Return the canvas's existing suggested-wire shape. Set `supports_suggest: true`
  in employee_mapping_data payload only.
- **Counter chips**: employee payload gains `counts` {identity:{total,unmapped}, bank:{...}, ...};
  overlay header renders chips that toggle left-column role filters.
- **Phase-2 hint alignment**: get_problems' `bankunmapped`/`idunmapped` (Phase 2) should now count
  only destination-appropriate wires (bank role ⇒ bank_account destination). Update if Phase 2
  shipped a looser check.

### Versions
pb_hr_payroll_formula → 19.0.1.67.0 (new migration dir only if a data migration is actually needed
— new nullable columns need none; skip empty migrations). pb_formula_studio → one above Phase 2's
value (verify actual current in both manifests first).

## Numbered test cases

Pure-python (run locally, must pass):
1. `_sanitize_acc_number` table: '0071000123456'→unchanged; ' 007-100 0123 456 '→'0071000123456';
   1234567890.0→'1234567890'; 1.23456789012e+11→None(warn); 123.45→None(warn); ''/None→None.

Odoo TransactionCase (coded for CI; live-verified via the batch run below):
2. Mapping constraints: field-row without target_field → ValidationError; bank-row without
   bank_role → ValidationError; bank-row with target_field=False → OK.
3. `employee_mapping_create` with right='b:acc_number' persists destination_type/bank_role and
   enforces 1:1 (re-wiring the same rule replaces the old row).
4. Bank sync: batch line with acc_number+bank_name mapped → res.partner.bank created once, linked,
   employee.bank_account_id set; second import same number + changed bank name → same record
   updated, no duplicate; employee with pre-existing bank_account_id → not overwritten.
5. No acc_number value on the line → no bank record created even if bank_name present.
6. `_get_mapping_updates` ignores bank rows (a bank mapping never writes hr.employee fields).
7. Input exclusion: fixture with (a) reference rule unreferenced+hidden → absent from
   input_values; (b) same rule referenced by a formula → present; (c) appears_on_payslip=True →
   present; legacy all-payroll config → input_values identical pre/post (CR-A7 regression).
8. `employee_mapping_suggest`: fixture headers (Bank Name, Số tài khoản, Employee Code, Date of
   Joining) → expected targets + confidence tiers.
9. make_text_component RPC: flips flags + role/source; detach refused once an advantage template
   with lines exists for the code.
10. Suggest/accept-all mode regression: employee-mode acceptAll calls employee_* RPCs (the CR3 fix)
    — assert via method spy or by effect; cycle mode unaffected.

Live (payobook demo world — REUSE demo employees per standing rule, no throwaway ZZ records):
11. Wire 2-3 bank columns on a demo config via the UI; run a MINIMAL import batch
    (create_payslips=False, 1-2 demo-employee rows with bank values incl. a leading-zero account) →
    verify res.partner.bank rows + employee link in psql; re-run the same batch → no duplicates.
12. Chrome-MCP screenshots: swim-lanes with role groups, bank lane, badges (amount + text
    component), payroll filter chip off/on, suggest wires with confidence, accept-all result,
    counter chips. No console errors; no style-compilation toast.

## Deploy + verification

Ledger ritual with CR6 chmod + psql latest_version check; `-u pb_hr_payroll_formula,
pb_formula_studio` ×4 DBs; restart; port. Then live tests 11-12 on payobook. abm: no data changes —
just confirm the mapping overlay opens and shows ABM's identity/profile/contract columns in lanes.
Self-review diff vs spec; one feature-scoped commit, no push.

## Report back

Per-test results; bank-sync live evidence (psql rows); CR3 fix note with what other modes actually
support suggest; suggest quality on ABM's real headers (list the proposals); deviations; new ledger
CRs; files touched; manifest versions; commit hash.
