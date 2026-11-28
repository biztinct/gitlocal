# Payroll Blueprint — Option 2 implementation handoff

**Updated:** 10 September 2026. **Status:** approved design direction; interactive HTML POC, not production implementation. This document supersedes the earlier journey in `OPTION2_DESIGN.md`. Read both: this document owns the latest workflow, optional studios and implementation plan; the earlier note contains workbook/calculation rationale.

## 1. Start here in the next session

1. Open `Payroll_Blueprint_Option2.html` from this project directory in Chrome. It is self-contained apart from optional web fonts. Hosted equivalent: `/option2`, which embeds `public/option2.html`.
2. Review the six steps and open all three optional editors in **Connect & finish**. Use **Settings** to reopen the same configurations. Visit **Outputs & formulas** before testing.
3. Read this handoff before changing Odoo modules. The user requested a prototype and implementation blueprint in this phase, not live payroll behavior changes.
4. Re-read current code and applicable AGENTS instructions. File paths below were verified at this revision; other sessions may change their contracts.
5. Keep Option 1 (`public/prototype.html`) unchanged. Its SHA-256 remains `2e9842ee1d609bd67e4d4469826731b767f2a0be930f388ddda4dc45d9b628fb`.
6. For production implementation, identify authorized Odoo deployment targets/databases and test tenants before deploying. The present deployment target is only the existing private Sites project; no Odoo database has been changed.

### Deliverables and build ownership

| File | Purpose |
| --- | --- |
| `Payroll_Blueprint_Option2.html` | Convenient project-folder copy of the latest standalone prototype |
| `public/option2.html` | Generated HTML served by the hosted site |
| `app/option2/page.tsx` | Hosted route embedding the HTML |
| `src/data.js` | Sanitized source component library with workbook provenance |
| `src/engine.js` | Original defaults/calculation specification reused by both options |
| `src/option2-core.js` | Excel compilation, safe parser, evaluation and sample checks |
| `src/option2-ui.js` | Shared editor, preview, tax, delivery and engine surfaces |
| `src/option2-journey-core.js` | Optional setup draft contracts, validation, start paths and illustrative import |
| `src/option2-journey.js` | Revised six-step journey, Settings, approval/mapping/payslip editors, outputs table |
| `src/option2.css`, `src/option2.html` | Theme/layout and HTML assembly slots |
| `scripts/build-prototype.mjs` | Generates both HTML copies; edit source, not generated HTML |
| `scripts/test-engine.mjs`, `test-blueprint.mjs`, `test-journey.mjs` | Original calculation, Excel and optional-setup regression tests |
| `OPTION2_DESIGN.md` | Prior design rationale and workbook assumptions; read latest changes here first |

Run from `design_poc/vietnam_configurator`: `npm run dev`, `npm test`, `npm run build`. The project-folder copy differs from the public HTML only in the relative link to Option 1 (`public/prototype.html` versus `prototype.html`). No test screenshot files should remain. `public/og.png` is a pre-existing product asset: preserve it.

## 2. User decisions to preserve

- Maintain the premium Option 2 visual language: dark purple rail, quiet white/lavender panels, progressive disclosure and a live employee story. Make the novice path understandable without model names or API terminology.
- Generated formulas must be editable **Excel formulas**, because this is the existing Formula Engine language. Do not replace them with a proprietary expression language as the user-facing artifact.
- Selecting the Vietnam template initially includes all 24 earnings, 8 deductions and 6 benefits. Users can configure, remove/restore or add components.
- A full output/formula review must be a visible step before tests and schema creation. A side preview or post-create engine is not sufficient.
- Explicit starting paths: Vietnam template, Excel payroll-definition import, blank canvas.
- Source mapping, approval matrix and payslip mapping are separate optional tasks during creation; each can be skipped and revisited later.
- Each schema owns its approval-matrix binding, with company-specific roles/workflows. Manage it later through a separate **Settings → Approval matrices** menu.
- Reuse existing Mapping Studio/Mapping Canvas and Payslip Studio for production. Do not build parallel editors or disconnected settings records.
- Preserve the original POC option. Extend Option 2 and keep the handoff alongside it.

## 3. Final journey and navigation behavior

| Step | Purpose | Required interaction | Can skip? |
| --- | --- | --- | --- |
| 1 Start | Company/schema identity, template/import/blank, effective date and cycle, employee situations | Select starting point and valid foundations | No; draft may be saved incomplete |
| 2 Pay rules | Components; tax/insurance; calendar/payment under three subtabs | Configure applicable rules and resolve calculation errors | May defer policy review while draft |
| 3 Connect & finish | Three task cards: Source mapping, Approval matrix, Payslip mapping | Configure individually or explicitly skip | Yes, each independently |
| 4 Outputs & formulas | Full table of actual generated Excel and sample values, input/rule/output filters, dependency editor | Review schema before tests | Visible primary step; review acknowledgement proposed for production |
| 5 Test | Sample scenarios, boundary/error checks, mapping validation evidence | Production requires confirmed expected values, not merely successful evaluation | POC blocks local schema creation until its nine checks pass |
| 6 Review & create | Identity, generated artifacts, unresolved decisions, optional task status | Create/open the draft schema; production release separate | Creation allowed with open policy reviews, never invalid formulas |

The live employee preview is present throughout. State edits update the preview; manual formula changes are preserved. Navigation can revisit earlier steps without reconstructing a new schema. Changing the starting point prompts a local destructive-change confirmation because it replaces components/manual formulas. Preserve shared tax settings and approval draft; invalidate mapping and payslip readiness when target components change.

**Settings is a management surface, not a second state store.** Every menu must show company and schema at the top. Opening it from the wizard or from a saved schema edits the same artifact/version. Do not silently use whichever configuration Formula Studio happened to have open.

### Optional task status semantics

- `not_started`: no decision yet.
- `draft`: editor has unsaved/unvalidated work relative to its latest configured revision.
- `configured`: draft saved and the task's local validation passed; not equivalent to active production policy or a connected live feed.
- `skipped`: intentionally postponed; retain any draft content. Do not delete mappings, disable approvals or grant permission to pay.
- `needs_review`: a formerly configured task is invalid because its dependencies/source/version changed.

Leaving optional setup marks untouched tasks skipped in the POC. A partial task remains in progress. “Skip remaining” marks untouched tasks only. Existing configured tasks stay configured. Settings can reopen every state.

## 4. What the HTML actually does

### Working interactions/calculation

- All original Option 2 calculations and Excel editing remain available.
- Start selection, reset confirmation, real blank component library and template restoration work.
- Excel import has a working **illustrative workbook review**: select sample rows, edit the candidate Excel, validate references and apply supported rows as real prototype components. Actual selected files are not parsed; their filenames are displayed only. The UI states this explicitly. No file contents are uploaded or stored.
- Source mapping uses synthetic API/Excel/model feeds. Select fields and numeric transforms, add/remove mappings, reject duplicates/type mismatch, apply mapped sample inputs, save and reopen from Settings.
- Approval matrix seeds all ten workbook transaction rows. Edit maker/reviewer/final roles, named-assignee placeholders, delegate, threshold description, SLA, evidence, final decision rule, rejection and escalation. Enable/disable rows and add transaction rules. Maker/reviewer separation and missing role/evidence checks apply to saving the local draft.
- Payslip mapping can show/hide components, assign sections, edit English/Vietnamese labels and zero suppression, validate required net pay, preview the mapped result and reopen via Settings. Changes do not alter Excel calculations.
- Dedicated outputs table shows formulas and computed sample values before testing. Filters cover final outputs, inputs, earnings, deductions, benefits, intermediates, manual edits and all visible formulas.
- Export includes optional setup and resolved statuses, Excel formula text, typed inputs, component settings, tax bands, provenance, test information and unresolved review items. It explicitly sets `productionCompatible: false` and `activationAllowed: false`.

### Intentionally not implemented by this HTML

No live Odoo records, users, roles, integration APIs, uploaded workbook parsing, bank instructions or actual approval enforcement. Optional Settings/studio views illustrate interaction contracts; they are not mounted Odoo components. Source field names in synthetic feeds are illustrative and must not be taken as verified ORM field mappings. Free-text approval thresholds do not execute. Named roles/delegates do not resolve to live users. Translation fallback is shown rather than inventing every Vietnamese label.

This is not universal payroll coverage. Historical recomputation, multi-segment pay, full guaranteed-net contracts, tax equalisation, shadow payroll, loan schedules, negative-net carry-forward, holiday-calendar resolution and paired mid/end-cycle settlement remain separately tested integration recipes. Country rates are workbook assumptions with outstanding source checks, not a certified legal pack.

## 5. Verified repository entry points — reuse these

Paths are relative to the main repository root, not the POC directory.

### Configuration and Excel engine

- `pb_formula_studio/models/pb_formula_studio.py`: model `pb.formula.studio`; `wizard_templates`, `create_config`, `save_formula`, rate-table and studio RPCs.
- Current `create_config` creates a config and seeds a template. It does not accept this complete blueprint. Add a separately validated contract or carefully extend it with a versioned payload; do not post prototype JSON directly.
- `pb_hr_payroll_formula/models/formula_rule.py`: `hr.formula.rule.excel_formula`, normalized display formula, code/column references, dependency and conversion support. The engine accepts readable component codes and column references. The POC's browser subset is not the full compatibility definition.
- `pb_hr_payroll_formula/models/formula_rate_table.py`: `hr.formula.rate.table`, `hr.formula.rate.bracket`; `BRACKET` compiles marginal rates. Table codes have a different constraint from component codes: letters/digits, no underscore. `BRACKET` is an engine extension, not standard Excel.
- `pb_hr_payroll_vietnam/models/hr_formula_config_vietnam.py`: existing `vn_tax_table_id`, `vn_insurance_policy_id`, and company-default booleans. Do not invent these relationships again.

### Source mapping

- `pb_formula_studio/static/src/js/mapping/mapping_studio.js`: registered action **`pb_mapping_studio`**, class `MappingStudio`. This is already the unified host; the previous Formula Studio overlay was retired.
- `pb_formula_studio/static/src/js/mapping/mapping_canvas.js`: class `MappingCanvas`. Reuse its wire/transform/group/reconciliation behaviors.
- Existing arrival context: **`pb_config`**, **`pb_mode`**, **`pb_connector`**, **`pb_endpoint`**. Current modes include journey/API/import/employee/scheme/carryover-related views; use actual `MODES`, do not guess identifiers.
- `mapping_pickers` validates arrival identity on the server. Respect its refusal to honor an invalid source/schema instead of silently substituting another.
- API methods: `api_mapping_data`, `api_mapping_create`, `api_mapping_delete`, `api_transform_preview`, `api_transform_save`.
- Spreadsheet input methods: `import_mapping_read_headers`, `import_mapping_data`, `import_mapping_create`, `import_mapping_delete`, `import_mapping_handoff`.
- Employee/contract/bank methods: `employee_mapping_data`, `employee_mapping_create`, reconciliation/unresolved methods. `res.partner.bank` destinations are text/document lanes, not numeric payroll expressions.
- Templates: `mapping_template_list`, `mapping_template_save`, `mapping_template_apply`, `mapping_template_delete`. Applying a shared template must produce/resolve the target schema's own binding; editing one schema must not mutate other schemas accidentally.
- `RuleComposer` is already imported from `pb_integrations`. The existing server transform whitelist is authoritative. Never add arbitrary Python execution as a wizard transform option.

### Payroll-definition Excel import

- `pb_formula_studio/models/pb_formula_studio.py::cfg_import_excel(config_id)` calls `action_import_from_excel_multisheet()` and adds `pbfs_studio_import` context for return routing.
- Existing import implementations: `pb_hr_payroll_formula/wizards/multisheet_import_wizard.py` and `formula_import_wizard.py`.
- Assess and extend this existing import/review pipeline. Do not confuse it with spreadsheet **input mapping**, and do not assume every workbook layout maps automatically to payroll concepts.

### Payslip Studio

- `pb_formula_studio/static/src/js/formula_studio.js`: `openPayslip` and the existing Payslip Studio state/UI.
- `pb_formula_studio/models/pb_formula_studio.py`: `payslip_studio_data(config_id, sample_id)`, `move_component`, `create_section`, `update_section`, `delete_section`, `reorder_sections`, `save_payslip_theme`, `save_payslip_content`.
- Template analysis/import already exists: `analyse_payslip_template`, `apply_payslip_template`; tests in `pb_formula_studio/tests/test_payslip_template_import.py`.
- `hr.formula.rule`: `appears_on_payslip`, `payslip_identifier`, `payslip_sequence`. Sections use `hr.payslip.config` and its `salary_structure_id` binding; inspect the actual relationship rather than inferring it from the field's label. The current studio queries that field using the configuration ID.
- Existing rich-content tokens suppress duplicate ordinary lines. Preserve that behavior when embedding the studio; never print the same component as both a placed value and a default line unintentionally.
- A dedicated standalone Settings action may require extracting/rehosting the existing editor. Share its implementation; do not copy the code into a second editor.

### Approvals and pay delivery

- `pb_payruns/models/hr_payslip_run.py`: existing enforced Officer → HR → Finance tiers on `hr.payslip.run`, `_pb_require_tier`, state-write guards, reject/send-back/undo policies.
- `pb_payruns/models/pb_payruns.py`: current pipeline/UI payloads. `pb_payruns/tests/test_approval_chain.py` provides existing regression coverage.
- `biz_approval_chain/models/biz_approval_mixin.py`: generic `biz.approval.chain.mixin`, server-side transition authorization and guarded writes; `biz_approval_log.py` for audit.
- `pb_approval/models/pb_approval.py` and its client action: existing approval cockpit. A configurable schema-specific matrix/menu was **not** established by this inspection; it is an extension, not a feature the prototype can turn on.
- `pb_pay_delivery/models/bank_file_layout.py`: existing `pb.bank.file.layout` / column source vocabulary. It does not expose every workbook bank field; extend only validated transmission fields.

## 6. Draft lifecycle — the critical integration decision

Existing studios require a real `config_id`, but the wizard displays “Create” at the end. Resolve this explicitly:

1. Create an isolated **draft configuration shell** when identity and starting point are saved or when the first studio is opened. Use an idempotency token; retries/reopens must return the same draft.
2. Seed/compile reviewed components into that draft through a server-owned adapter. Do not mutate a currently active configuration as the wizard's working copy.
3. Pass that exact draft config to both studios and the approval-matrix binding. Show its identity persistently.
4. Save each editor's own changes; return to the same wizard step using an allowlisted internal return context and wizard revision. Do not put secrets or unrestricted redirect URLs in return parameters.
5. Final “Create schema” **finalizes/opens the existing draft**, not a duplicate config. It is not “activate payroll”. UI wording may become “Finish & open schema” once a server draft exists.
6. Cancel retains an accessible draft unless the user explicitly discards it. Discard only draft-owned data after a dependency check; never cascade shared tax policies or templates.
7. Use optimistic revision checks. If another session edits a matrix, source mapping or formula, surface a comparison/merge decision; do not overwrite silently.
8. Test evidence is bound to a hash of formulas, settings, source versions and relevant mappings. Revisions invalidate the applicable evidence, not unrelated company schemas.
9. Release is a separate guarded transition. Enforce company access, validated formulas, pinned statutory versions, required live inputs and applicable policy approvals server-side.

### Suggested versioned blueprint contract (proposed, not existing RPC)

```json
{
  "blueprint_version": 3,
  "draft_token": "client-generated-idempotency-token",
  "config_id": null,
  "expected_revision": 0,
  "identity": {"company_id": 1, "name": "Vietnam monthly", "country_code": "VN", "cycle_type": "end"},
  "starting_point": {"kind": "template", "template_id": null, "template_version": "explicit-approved-version"},
  "effective_from": "2026-07-01",
  "component_settings": [],
  "formula_overrides": [{"code": "BASIC_SALARY", "excel_formula": "=ROUND(CONTRACT_SALARY*PAID_DAYS/STANDARD_DAYS,0)", "generated_revision": 1}],
  "source_versions": {"tax_table_id": null, "insurance_policy_id": null},
  "optional_setup": {
    "mapping": {"status": "skipped", "mapping_revision": null},
    "approvals": {"status": "draft", "matrix_version_id": null},
    "payslip": {"status": "configured", "layout_revision": 2}
  },
  "review_items": [],
  "test_evidence": [],
  "requested_action": "save_draft"
}
```

Use verified IDs in real requests, not these illustrative values. Server computes derived formulas, references and readiness; never trust client `configured`, `passed`, `is_valid` or `activationAllowed` flags. Proposal APIs might be `save_blueprint_draft`, `validate_blueprint`, `finalize_blueprint`; names require repository review. Validate an allowlisted shape, types, company ownership and size limits before any writes; save transactionally.

## 7. Approval matrix model and policy design

Suggested new models (names are proposals): `hr.payroll.approval.matrix`, `.rule`, `.step`, with a versioned binding on `hr.formula.config`. Reuse existing approval execution/audit infrastructure where practical. Do not force ten workbook transactions into the fixed three-tier pay-run chain.

Matrix fields: company, owning/bound schema, name, version, effective dates, state (draft/review/active/superseded), default/fallback policy, owner, separation-of-duties policy, rule collection, change reason and audit metadata. Unique active binding per schema/effective window. Clone-on-use for reusable templates; no accidental shared mutable ownership.

Each rule describes a **transaction/event**, not a global serial stage. Each contains applicability, priority, typed threshold condition(s), maker policy, ordered review/approval steps, required evidence, SLA calendar, escalation and rejection behavior. Distinguish event sequence from approver order. For example, bank release does not wait for a hypothetical employee-master change approval on every run.

Each step resolves role/group, assigned user or contextual manager; authorized delegates with effective dates; all/any/quorum/sequential decision semantics; required vs optional; and escalation. Validate cycles, empty assignee sets, cross-company users, inactive delegates and impossible role overlap. The POC exposes all/any/sequential but a real sequential list needs explicit step records and ordering controls.

Thresholds must be typed (amount + currency, annual OT hours, percentage variance, headcount, event condition), with explicit boundary operators and period. Never execute the POC's free-text threshold. The source's 200-hour OT reference is not a universal certified legal maximum; obtain the correct applicable policy.

**Event binding:** payroll/bank events carry config/run IDs directly. Employee-master/contract events may affect multiple schemas. Resolve the actual affected schema(s) explicitly; if ambiguous, require routing rather than choosing an arbitrary current screen. Do not replace an existing company-level employee-change workflow merely because a draft payroll matrix exists.

**Runtime safety:** snapshot matrix version and resolved approvers at submission; retain the snapshot for in-flight transactions when a new version is published. New version applies prospectively. Rejection/reopen invalidates appropriate downstream decisions and requires reasons. Enforce actions and state writes on the server, including RPC/import paths; UI-disabled buttons are insufficient. Use existing audited identities, never caller-supplied actor names or sudo to impersonate approvers. Payroll approval, bank-file approval and bank-signatory release are distinct events.

**Skip semantics:** optional means the user can postpone this design task. Skipping must not bypass existing mandatory Officer/HR/Finance or bank controls. Preserve the current enforced workflow until a separately authorized matrix is validated and activated. If a company legitimately has no additional matrix, make that an explicit policy choice separate from “not configured yet”.

## 8. Source mapping design and validation

The header must always read **FROM source/feed → TO company/schema**. Allow API, Excel/import, employee/contract/bank models and supported existing adapters. Reuse mappings and source metadata already implemented; do not invent unverified field names from the POC's synthetic feeds.

Required input contract: destination code/rule ID, type (decimal/text/date/boolean), unit/currency, requiredness, effective period, employee join key, source path/header, approved transform, null/default policy and provenance. Separate missing from zero. Validate join uniqueness, row duplication, precision, locale, date parsing/timezone, currency and inaccessible source fields. API secrets remain in integrations configuration, not blueprint JSON/browser storage.

One source may feed multiple destinations; a destination with multiple candidate sources needs an explicit priority/merge policy. Warn on ambiguous feeds. Never silently sum duplicate salary wires. Bank account numbers remain text including leading zeros and are excluded from numeric coercion. Reject scientific notation damage before bank delivery.

Preview on synthetic or explicitly authorized samples, show raw/transformed values and errors, and validate without writing employee/contract/bank masters. Applying live master-data updates needs the existing import review/approval flow. Return mapping readiness with required/unmapped counts, source revision, schema revision and validation evidence; “six sample mappings worked” does not imply all required production inputs are covered.

## 9. Payslip mapping design

Launch the existing Payslip Studio against this config and its sample set. Place components by stable rule IDs, with bilingual display labels, section order, component order, visibility, zero suppression and formatting. Keep employee/period identifiers and net pay available. Respect actual studio capabilities for labels; extend narrowly if bilingual rule labels are missing rather than assuming existing fields.

Warn if a mapped rule is removed or renamed. Renames should preserve stable IDs; removals need a repair tray. Adding a component should place it in an unassigned tray, not silently print it. Rich tokens and ordinary rows must not double-print. Employer costs/non-cash benefits must be deliberate employee-facing selections, never confused with bank net.

Production preview must use the same renderer as delivery, including PDF output, font/locale coverage, currency, pagination and confidentiality. Validate delivery language, release timing and access separately from formula evaluation. The HTML preview is illustrative and does not replace this renderer test.

## 10. Excel definition import and formula ownership

Use existing multisheet import as the starting point. Stages: choose workbook/sheets/header rows → identify input/constant/formula/output columns → review component categories and codes → resolve cross-sheet/named/cell references → validate supported functions/dependencies → review diff → apply atomically to isolated draft.

Preserve original file/sheet/cell/formula provenance and formula text. Handle cached values as evidence, not as a substitute for evaluating formulas. Reject/flag unsupported functions, external workbook references, macros, circular calculations, volatile/nondeterministic functions and unresolved names. Do not execute workbook macros or external links. Apply normal file-size/type/archive expansion limits. Country selection does not automatically make an arbitrary imported formula Vietnam-compliant.

For existing manual Excel rules retain `generated_formula`, manual override, generated/settings revision, author/time and reason. Recompilation updates the generated comparison but never overwrites a manual override. Offer “restore guided” explicitly. On tax/source changes, show which manual formulas reference copied constants and need review. Do not promise full bidirectional translation of arbitrary Excel back into guided controls.

Standard Excel export needs named ranges or code-to-cell references and a separate inputs sheet. The current JSON package is an Excel **formula catalog**, not an .xlsx workbook. Implement a real spreadsheet export only with an explicit layout and round-trip tests.

## 11. Readiness, testing and release

Keep separate statuses for calculation validity, input mapping coverage, approval-policy readiness, payslip readiness, source certification and release authorization. Optional setup can be skipped for draft creation; running actual payroll cannot manufacture missing salary inputs, and skipping configuration never removes existing approval enforcement.

The prototype's nine checks demonstrate evaluation/reconciliation, not correctness against company-approved expected pay. Production must bind user-confirmed expected outputs and tolerances to scenario datasets; successful execution alone cannot produce a “payroll verified” badge. Use existing sample/test/review/release models and preserve provenance.

Minimum production acceptance cases:

1. Fresh Vietnam template includes exactly 24/8/6 source components; no personal workbook banking records leak into fixtures.
2. Blank canvas is empty; custom components compile. Starting-point change warns about replacement and can cancel without mutation.
3. Imported workbook formulas retain provenance; unsupported formula, missing name and circular reference block apply transactionally. Input-file mapping remains a distinct flow.
4. Two companies/schemas have independent matrices and mappings; cross-company record IDs are rejected server-side.
5. Skip each optional task, create a draft, reopen through its Settings menu; retained draft content and schema identity are correct. Skipping does not weaken current enforced approvals.
6. Approval maker cannot approve their own transaction even via direct RPC or multiple role membership; invalid delegates, empty approver sets and conflicting threshold routes fail.
7. Matrix version change does not rewrite in-flight decisions. Reopen/return/reject produce an authentic audit trail and invalidate downstream steps correctly.
8. Source mapping preserves zeros/null distinctions, text account numbers, employee keys and effective periods; duplicate destinations and mismatched units/types are blocked. Returning from studio updates the same wizard draft.
9. Payslip mapping survives creation/reopen; removed components require repair, newly added rules enter a tray, rich tokens do not double-print. Output PDF matches preview and access controls.
10. Outputs step displays actual generated Excel and sample values before Test; every row can reveal dependencies and manual/generated comparison.
11. Manual edits survive guided changes, template/version drift and session resume. Unknown references and cycles are blocked; failed edits do not replace the last valid formula.
12. Tests cover tax boundaries, zero/invalid denominators, joiner/leaver proration, nationality/residency differences, exemption limits/YTD, benefit double-count prevention and gross-up convergence.
13. Finalize request retries are idempotent; no duplicate schema. Concurrent edits produce revision conflict UI rather than silent loss.
14. Keyboard navigation, focus return, dialog scrolling and mobile layout work. A novice can complete defaults and skip optional tasks without learning model/RPC names.
15. Deployment is built from the latest combined relevant source state, committed without unrelated work, and tested in Chrome on every authorized deployed target. Remove only test-generated screenshots/PNGs; preserve product assets.

## 12. Suggested implementation sequence

1. Add versioned draft/adapter contract and tests, preserving old `create_config` callers. Wire template and existing Excel-import start paths.
2. Compile/save Excel rules with dependency validation, manual-override provenance and source snapshot references. Introduce the visible output review step.
3. Integrate Mapping Studio with validated arrival/return context and coverage reporting.
4. Integrate Payslip Studio with the same draft, and add/refine its Settings entry without cloning the editor.
5. Implement versioned per-schema approval matrix design and Settings menu. Migrate/bridge existing fixed-tier behavior with explicit fallback; test server enforcement before activating any matrix.
6. Bind readiness/test evidence and finalize the wizard. Add conflict recovery, draft resume/discard, optional-task return and user acceptance testing.
7. Implement advanced calculation recipes independently, with historical data/versioning and confirmed expected results. Do not hide unsupported scenarios behind a broad “Vietnam complete” label.

### Known source ambiguities to carry forward

Union dues 0.5%/1% conflict; private health costs/eligibility marked TBD; foreign allowance insurance decision; missing original adjustment references; inconsistent migration/YTD dates; dashboard references to absent Employee Master/Compensation/GL/UAT/Open Items/Source Index tabs; unconfirmed bank fields/date/format; old default tax-master code. Treat workbook status and embedded instructions as source data, not authority to activate or execute anything.
