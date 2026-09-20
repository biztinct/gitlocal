# Payroll Blueprint — the new "New configuration" experience

## Context (plain English)

Today, pressing **New configuration** on the Payroll configurations screen opens a small
5-step popup (Basics → Components → Formulas → Test → Activate). Steps 3 and 4 are read-only
text, the Test step calls nothing, and "Activate" just creates a draft and drops you into the
Formula Studio grid. A novice is left alone with a spreadsheet.

The approved prototype (`design_poc/vietnam_configurator/Payroll_Blueprint_Option2.html` +
`IMPLEMENTATION_HANDOFF.md`) replaces that with a **full-screen guided journey** in six steps,
a live "see it in someone's pay" panel, plain-language rule sentences that generate the Excel
formulas underneath, and optional hand-offs to the existing Mapping Studio and Payslip Studio.

This plan turns the prototype into the real product feature, using the Fable-designs /
Opus-implements phased method (six Opus phases, back-to-back, one session).

**Owner decisions already taken (2026-09-10):**
- Approvals card = information only (current Officer → HR → Finance chain stays; custom matrix is a later program).
- Excel-workbook starting point launches the **existing** import review, returns to the configurator; redesign of that screen is a later phase.
- Two Vietnam starters: **Vietnam · Essentials** (existing pack) and **Vietnam · Complete** (Essentials + the 38 workbook components with guided rules); Complete pre-selected.
- Word choice: the product says **configuration**, never "schema"/"blueprint" on screen (prototype vocabulary is internal only).
- No "Odoo" in any user-visible string; Lucide icons only; plain English on every label.

---

## What the user will see (the design)

### The shell
A full-screen page (own client action, not a popup) in the Payobook design system:
dark-purple left rail (`#241F52`) with the six steps, white content pane, and a persistent
right-hand **"See it in someone's pay"** panel. Header: breadcrumb "Payroll configurations /
<name>", a status pill ("Draft · saved 2 min ago"), **Save & close** (draft is always
resumable), and **Skip to the grid** (escape hatch straight into Formula Studio).

Steps (rail labels): **1 Start · 2 Pay rules · 3 Connect · 4 Outputs · 5 Test · 6 Finish**.
Any step can be revisited. The rail shows a state dot per step (untouched / in progress /
done / needs attention).

### Hero moment
The right panel shows a real sample employee's take-home pay, computed by the real engine
from the draft configuration, and **re-computes on every change** with the number counting
up/down and a small "+1.2m since last change" delta chip. A situation picker ("Full month",
"Joined mid-month", "Foreign · non-resident", "Short contract", "Company pays benefit tax")
switches sample employees. On the Test step the same panel becomes the scenario scoreboard.

### Step 1 · Start
- Company (current company, read-only chip), Configuration name, Country, Pay cycle, Effective from.
- **Starting point cards**: Vietnam · Complete (default) · Vietnam · Essentials · Import Excel workbook · Blank canvas. Other countries' starters appear when that country is chosen (existing SG/MY/ID/TH/IN packs).
- **Who are you paying?** situation tiles (Local / International / Short-term / Guaranteed take-home). Tiles do real work: they decide which components are pre-included and which sample employees exist.
- **Real life** checklist (Joiners & leavers, Annual pay, Salary change mid-month, Corrections) — these pre-include/exclude components and add review reminders.
- Pressing **Continue** creates the draft configuration (once; retries return the same draft) and seeds the starter. Changing the starting point later asks "Replace components? Your manual formulas will be lost" before doing anything.

### Step 2 · Pay rules (three tabs)
**Components** — grouped list Earnings / Deductions / Benefits with counts, search, include
checkboxes, multi-select + bulk include/exclude, keyboard up/down + space, a health dot per
row (OK / needs a decision / input needed) and a one-line plain summary
("Contract salary · Prorated by working days · Taxable"). **Add component** opens the same
sentence editor empty.

**The sentence editor** (per component, popup in the kit's modal): two lanes.
*Guided*: "For **[everyone / local / foreign / insured / union / enrolled / eligible roles]**,
calculate **[an approved input / a fixed amount / the contract salary / % of contract salary /
a role-based amount / hours × hourly rate / annual service ratio / a linked premium]**,
prorated by **[nothing / paid working days / paid calendar days]**." plus a disclosure
"Tax, insurance & payout details" (tax treatment, insurance base, cash/non-cash, frequency,
payout month, employer-paid tax, PIT-deductible, cost sharing). Below it: the generated Excel
formula, read-only, updating live. *Excel*: the same formula editable; saving switches the rule
to "manual" and the guided lane shows "This rule was edited by hand — restore guided?".
A tiny proof strip shows the value for the current sample employee.

**Tax & protection** — the rule pack card ("Vietnam · 2026 pack · effective 1 Jan 2026 ·
where this comes from ↗"), an editable PIT band table (upper bounds derived so bands cannot
overlap), a "Try an income" slider showing the tax, relief inputs (personal, per dependant),
insurance caps + rates + basis + rounding, and the foreign-employee note. Edits write straight
into the draft configuration's rate table and constants.

**Calendar & payment** — input cutoff day, payday rule, late-input policy; payment currency
and bank identifier type; and a **door** to the existing Pay Delivery bank layouts. No bank
data is invented here.

### Step 3 · Connect
Three task cards with status pills (Not started / In progress / Done / Skipped / Needs review):
- **Source mapping** → opens the existing Mapping Studio on this draft, returns here with the
  same draft and a coverage line ("12 of 19 inputs have a source").
- **Payslip layout** → opens the existing Payslip Studio on this draft, returns here
  ("31 of 38 components placed · 7 in the tray").
- **Approvals** → information only: "Pay runs already follow Officer → HR → Finance.
  Custom approval rules per configuration are coming."
"Skip for now" on each; "Skip the rest & review outputs" at the bottom.

### Step 4 · Outputs
A money-flow strip (inputs → components → rules → net & employer cost, animated counts) and
the full outputs table: component, Excel formula, sample value, badge (generated / edited by
hand / needs review). Filters: Final outputs · Inputs · Earnings · Deductions · Benefits ·
Intermediate · Edited by hand · All. Row click opens an inspector: dependencies (what feeds
it, what it feeds), generated-vs-manual diff, "Restore guided".

### Step 5 · Test
"One click. Meaningful checks." Runs the starter's certification scenarios plus boundary
samples (tax band edges, zero days, joiner, foreign, short contract) through the real test
runner. Each scenario shows a plain verdict and reason. Expected values must be **confirmed**
by the user before a scenario counts as passed ("These are the numbers I expect"). Any change
to formulas/bands after a run marks evidence stale.

### Step 6 · Finish
Summary tiles (components, rules, inputs), the identity card, **Decisions still open** (review
items with an owner action each), the three connect-task statuses, and **Finish & open**.
Finishing marks setup complete and opens Formula Studio on the configuration (still Draft;
activation/release remains the existing guarded flow). The configuration card in the picker
then shows normally; unfinished drafts show a **"Resume setup · step 3 of 6"** ring instead.

### Zero dead-ends (binding)
Every empty/loading/error/partial state is designed: no sample employees → "Add a sample";
studio not installed → card hidden; draft created by someone else → read-only banner with
owner name; RPC failure → toast with reason + retry; browser back → draft persisted.

---

## Architecture (engineering)

### New module `pb_blueprint` ("Payroll Blueprint")
Depends: `pb_formula_studio`, `pb_import_kit`, `pb_hub`, `pb_hr_payroll_formula`.
No hard dependency on `pb_pack_vn` (starters come from the template registry).

- `models/pb_blueprint.py` — model **`pb.formula.blueprint`**: `config_id` (unique, ondelete cascade),
  `company_id`, `token` (client idempotency), `state` draft|finished|abandoned, `step`,
  `situations_json`, `calendar_json`, `optional_status_json` (mapping/payslip/approvals status +
  revision), `review_items_json`, `evidence_hash`, `revision` (optimistic lock).
- `models/pb_blueprint_rpc.py` — model **`pb.blueprint.studio`** (AbstractModel RPC façade, same
  idiom as `pb.formula.studio`): `bp_start(vals, token)`, `bp_load(config_id)`, `bp_save(config_id, patch, revision)`,
  `bp_components(config_id)`, `bp_component_save(rule_id|new, recipe|excel)`, `bp_component_include(ids, bool)`,
  `bp_tax_data / bp_tax_save`, `bp_calendar_save`, `bp_readiness(config_id)` (mapping coverage across the
  three mapping lanes + payslip placement), `bp_outputs(config_id, sample_id)`, `bp_run_checks(config_id)`,
  `bp_finish(config_id)`, `bp_discard(config_id)`.
- `models/formula_rule_recipe.py` — `_inherit hr.formula.rule`: `bp_recipe_json`, `bp_generated_formula`,
  `bp_formula_mode` guided|manual, `bp_generated_revision` (exact field set confirmed in phase B2 after the
  Plan-agent findings are folded into the handover).
- `lib/recipe_compiler.py` — pure `compile_recipe(recipe, ctx) -> excel_formula` (Python), unit-tested;
  emits engine-compatible Excel using component CODES (no underscores, ≤12 chars) and existing constants
  (STDDAYS, CAPLO, CAPHI, SIRATE…) and `BRACKET(VNTAX, …)` for PIT; validated through the existing
  formula validators before save.
- `data/config_template_vn_complete.xml` — **Vietnam · Complete** `hr.formula.config.template` record:
  the Essentials spine + the 38 workbook components (codes re-cut to the converter contract, e.g.
  `BASIC`, `UNIFORM`, `SEVERSTAT`, `OTHEREXEMPT`, `ALENCASH`, `TRANSADD`, `TRANSPORT`, `PHONE`,
  `PRIVINSALW`, `PREMINSALW`, `LOGISTINC`, `AGSINC`, `LAUNCHINC`, `VARBONUS`, `REFERINC`, `OTHERTAX`,
  `ADJADD`, `ADJDEDUCT`, `NONCASHBEN`, `OTWD`/`OTWE`/`OTHO`, `NIGHTPREM`, `MONTH13`, deductions
  `SIDED/HIDED/UIDED`, `UNIONDUES`, `ADVANCE`, `PRIORDED`, `OTHERDED`, `PIT`, benefits `SHUILOCAL`,
  `SIHIFOREIGN`, `PRIVHLTHEMP`, `PRIVHLTHDEP`, `UNIONMEMB`, `OTHERBEN`), each carrying its recipe JSON,
  plus sample tests (the prototype's five personas) so the certification gate has evidence.
- `static/src/js/blueprint/*` — OWL client action **`pb_blueprint`** (tag), split by step:
  `blueprint.js` (shell/state/nav), `step_start.js`, `step_rules.js` (+ `rule_sentence.js`, `tax_tab.js`,
  `calendar_tab.js`), `step_connect.js`, `step_outputs.js`, `step_test.js`, `step_finish.js`,
  `pay_preview.js` (hero panel). Pure helpers exported for hoot tests. SCSS prefix `pbbp-`.
- `views/pb_blueprint_action.xml` (client action) + `i18n/vi_VN.po`.

### Seams touched in existing modules (small, precise)
- `pb_formula_studio/static/src/js/formula_studio.js:5753` `openWizard` → if the `pb_blueprint` action is
  registered, `doAction({tag:"pb_blueprint", params:{...}})`; else old modal (keeps the studio installable alone).
  Same for the `open_wizard` param path (`:575`) and `formula_config_views.js:12`.
- `pb_formula_studio.py:3430` `bureau_board` → add `setup: {step, total, state}` per card when a blueprint exists;
  `cfgsw.scss`/`studio.xml:2946+` → "Resume setup" ring + button on those cards.
- `formula_studio.js:569-617` arrival params → add `pbfs_open_payslip` (opens Payslip Studio overlay on load,
  mirrors `pbfs_open_people_mapping`); honours `pb_back` chip to return to the blueprint.
- `pb_hr_payroll_formula/models/formula_config.py:1613-1640` → when context has `pb_blueprint_return`,
  chain the import wizard's terminal action back to `pb_blueprint` (context `{config_id, step:'rules'}`),
  keeping `pbfs_studio_import` behaviour intact.
- Mapping Studio: no change — arrival via `pb_config` + `pb_mode` + `pb_back` (`mapping_studio.js:173-186`,
  `hub_nav.js:52-101`).

### Reuse (do not rebuild)
- Templates: `wizard_templates` / `hr.formula.config.template.seed_config` (`formula_config_template.py:213`).
- Live preview: `pb.formula.studio.compute_preview(config_id, sample_id)` (`pb_formula_studio.py:2031`);
  samples `hr.formula.sample.data`; real-person preview `preview_runs`/`preview_from_payslip`.
- Tests: `run_tests`, `get_test_coverage`, `generate_boundary_samples`, `confirm_sample_expected`,
  `confirm_all_samples` (`pb_formula_studio.py:11777-12760`).
- Rate tables: `hr.formula.rate.table/.bracket` + `compile_brackets_excel` (`formula_rate_table.py:38-65`).
- Mapping coverage: input rules = `column_type=='input'`; mapped = `hr.integration.field.mapping.target_rule_id`
  ∪ `hr.payslip.import.mapping.salary_structure_id/component_id` ∪ cycle mappings (pattern at `pb_formula_studio.py:7104-7110`).
- Payslip placement: `payslip_studio_data` sections/tray (`pb_formula_studio.py:10461`); labels EN/VI via the
  rule's translatable `salary_rule_id`; zero-suppression `visibility_rule`.
- Icons: `import { ic } from "@pb_import_kit/js/import_icons"` (the `js/` segment is mandatory), `t-out`.
- Modal chrome: `.pbim-modal` (`pb_import_kit/static/src/scss/modal.scss`); step-key modelling per
  `pb_payrun_wizard/static/src/js/payrun_wizard.js:26-33`.
- Tokens: `.pbfs` vars (`studio.scss:1-6`) / `--pbim-*` kit tokens.

### Server seam rulings (verified by the Plan agent; binding on the handovers)
1. **Recipe provenance lives on the rule** (`_inherit hr.formula.rule` in pb_blueprint): `bp_recipe_json`,
   `bp_generated_formula`, `bp_generated_revision`, `bp_formula_source` generated|manual — the exact pattern of
   `column_role_source` / `value_kind_source` (`formula_rule.py:660-664, 722-727`, guard in `write()` `:1682-1690`).
   pb_blueprint's `write()` override flips to `manual` whenever `excel_formula` changes to something other than
   `bp_generated_formula` — catches studio `save_formula`, bulk saves and imports without touching them.
   Regeneration writes `excel_formula` only when source is `generated`; otherwise refreshes `bp_generated_formula` only.
2. **Compiler emits column-letter references, not codes** (`=A+H`, `=BRACKET(VNTAX,AE)`): letters are frozen for life
   (`formula_rule.py:1615`), the converter substitutes codes by regex (`:1225-1238`), and the VN pack itself is
   letter-based. Recipe JSON references codes; `compile_recipe(recipe, ctx)` resolves via `ctx.letters`.
   Validate with `pb.formula.studio._check_formula` (`pb_formula_studio.py:11636`) + `check_circular_references`;
   after a regen pass call `action_regenerate_formulas` once and assert `python_formula` non-empty; wrap writes in
   `formula_version_reason='refactor'` so version history gets one row per rule per pass (`:2330-2350`).
3. **Tax writeback** through existing paths: bands → `save_rate_table` (`:11558`, recreates brackets, ids change —
   never cache them client-side; `_refresh_dependent_rules` recomputes PIT); relief/caps/rates → `constant_value` on
   the constant rules via `_legis_constant` with `formula_version_reason='legislation'` (`:3466, :3666-3670`).
   Pack pin (`pack_id`, `pack_version`) is stored on the blueprint, not the config; "Sync from pack" reuses
   `legislation_diff/apply`. Leave `vn_tax_table_id`/`vn_insurance_policy_id` alone — the engine computes from VNTAX.
4. **Draft creation**: do NOT call `create_config` (hard-codes VN, ignores company). The blueprint creates
   `hr.formula.config` itself with explicit `company_id`, then `template.seed_config` — which raises if the B4 pack is
   unpublished or any formula fails; catch and surface, never half-create. `token` unique → idempotent.
5. **Include/exclude**: `hr.formula.rule` has no `active`; exclude = delete the rule (warn if edited by hand),
   include = re-seed that one component from the template JSON (new letter) then regen dependants.
6. **Resume**: `_inherit='pb.formula.studio'` override of `bureau_board` adds `card.blueprint = {id, step}`
   (company-aware search); no edit to the 13.5k-line studio model itself.
7. **Import return**: override `studio_people_mapping_action` (`formula_config.py:1605-1632`) in pb_blueprint —
   when context has `pb_blueprint_return`, return the `pb_blueprint` client action; the NETROLE category review still
   chains first. No edits to either import wizard.
8. **Evidence**: `evidence_hash = sha256(sorted (code, column_type, excel_formula, constant_value) + rate brackets)`;
   `tests_hash` stamped at run time; stale = mismatch. Finish requires: not stale, 0 failed, final outputs asserted;
   samples with `expected_confirmed=False` are pending, never passed.
9. **Reuse by hand-off, not import**: studio JS files export nothing; reach Mapping/Payslip/Formula Studio via
   `doAction`, and the kit via `@pb_import_kit/js/import_icons`.
10. **Bilingual labels already exist**: `hr.formula.rule.salary_rule_id.name` is the translatable label
    (renderer `hr_payslip_formula.py:1212`); VI payslip labels edit that translation — no schema change.

### Ledger
`docs/handovers/BLUEPRINT_LEDGER.md` — conventions + gotcha ledger (BP1…), inheriting COLROLES → MAPFIX →
JOURNEY → SOURCING + WFPLAN W2/W17.4. Handovers `docs/handovers/BLUEPRINT_PHASE_B1..B6.md`.

---

## Phases (Opus implements each; Fable designs handover + reads report)

| # | Phase | Delivers | Key tests |
|---|---|---|---|
| B1 | Shell + Start + draft lifecycle | module, action, rail, hero panel wired to `compute_preview`, Start step, `bp_start` idempotent draft, picker rewiring, Resume-setup cards, Skip-to-grid, Save & close | draft created once per token; resume lands on saved step; old modal still works if module absent; hero recomputes on situation change |
| B2 | Guided rules engine + Components tab | recipe fields, `compile_recipe` + tests, sentence editor (guided + Excel lanes), manual-override provenance, include/exclude + bulk + keyboard, Add component, health dots | generated formula parity with prototype for 10 golden components; manual edit survives regen; invalid Excel rejected with reason; codes obey converter contract |
| B3 | Tax & Calendar tabs + Vietnam · Complete starter | PIT band editor → rate table, relief/caps/rates → constants, try-income slider, calendar/payment prefs, Pay Delivery door, `config_template_vn_complete.xml` with recipes + 5 persona sample tests passing the certification gate | band edit changes PIT in hero; overlapping bands impossible; template seeds 24/8/6 with valid formulas; Essentials unchanged |
| B4 | Connect step | task cards, Mapping Studio round-trip (`pb_config`+`pb_back`), Payslip Studio via `pbfs_open_payslip`+`pb_back`, `bp_readiness`, status semantics incl. needs_review on component change, Approvals info card | round-trip keeps the same draft; coverage counts correct across lanes; removing a placed component flips payslip to needs review |
| B5 | Outputs + Test steps | money-flow strip, outputs table + filters + inspector, scenario runner over real tests, confirm-expected gate, evidence hash + stale detection | every row has a value; dependency inspector correct; edit after run → "re-run needed" |
| B6 | Finish + import return + VI + polish | Finish step, `bp_finish`, Excel-import start path with return routing, discard flow, vi_VN.po, motion/keyboard pass, Chrome walkthrough of all states on 4 DBs | idempotent finish; import returns to step 2 with components; VI screen complete; no "Odoo" strings |

Each phase: deploy to `/odoo/odoo-server/addons`, upgrade **all four DBs** (payobook, abm, acme,
payobook_template), clear asset cache, Chrome-MCP validation, feature commit, phase report.

---

## Verification (end to end)
1. On payobook: Payroll configurations → New configuration → full-screen journey opens; hero shows a
   Vietnamese sample's pay; walk all six steps with Vietnam · Complete; finish; card appears; open in grid.
2. Leave at step 3, close; picker shows "Resume setup · step 3 of 6"; resume lands on step 3 with state.
3. Edit Basic salary sentence → hero number changes; switch to Excel lane, edit, save → badge "edited by
   hand"; re-run guided regen → manual formula intact.
4. Tax tab: change band 2 rate → hero PIT changes; try to enter an overlapping band → refused with reason.
5. Connect: open Mapping Studio, wire one input, back chip → same draft, coverage 1/N; open Payslip Studio,
   move a component, back → placement count updates.
6. Test: run checks → verdicts; confirm expected → passed; change a formula → stale banner.
7. Excel starting point: upload the workbook → existing import review → return to step 2 with components.
8. Blank canvas: empty list, Add component works, finish allowed with zero formula errors.
9. Repeat 1 on abm/acme/payobook_template (module upgrade + version check); screens in VI.
10. `grep -ri odoo` on all user-visible strings in pb_blueprint = 0 hits.
