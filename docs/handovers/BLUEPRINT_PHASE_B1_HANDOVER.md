# BLUEPRINT Phase B1 — Shell, Start step, draft lifecycle, Resume setup

Read `docs/handovers/BLUEPRINT_LEDGER.md` FULLY first (rulings BP-R1…R11, plumbing facts,
deploy ritual, gotchas). Then `docs/handovers/BLUEPRINT_PLAN.md` §"What the user will see" for
the whole journey so B1's shell leaves the right seams for B2–B6. Do not re-derive anything the
ledger states; verify only what B1 touches.

## 1. Goal (plain English)

Pressing **New configuration** on the Payroll configurations picker opens a full-screen guided
journey instead of the small popup. In B1 the **Start** step is complete and real: name, country,
pay cycle, effective date, starting point, "who are you paying", real-life checklist → one press
creates a draft configuration (once, idempotently), seeds the chosen starter and lands you on
step 2 with the right-hand **"See it in someone's pay"** panel showing a real sample employee's
pay computed by the real engine. Steps 2–5 exist as honest, designed thin panels (they say what
arrives next and let you continue); **Finish & open** works minimally. Leaving mid-way keeps a
resumable draft; the picker card shows **"Resume setup · step N of 6"**. The Excel-workbook
starting point launches the existing import review and **returns** to the journey.

## 2. Scope — in

- New module **`pb_blueprint`** ("Payroll Blueprint" — engineering name; the user sees "New configuration").
- Server: `pb.formula.blueprint` model, `pb.blueprint.studio` RPC façade, `bureau_board` override,
  `studio_people_mapping_action` override (import return door), security, tests.
- Client: client action `pb_blueprint` (shell: rail, header, footer, hero panel), Start step (full),
  steps rules/connect/outputs/test as thin panels, Finish (minimal), Save & close, Skip to the grid,
  starter-change confirmation, error/empty/loading states, 1440 + 390 layouts.
- `pb_formula_studio` seams (minimal, listed in §6): `openWizard` → the new action when registered;
  `open_wizard` arrival param honours the same; picker card "Resume setup"; `formula_config_views.js`
  "New" redirect.
- Deploy to p9clone → payobook → abm → payobook_template; Chrome validation; feature commits; report.

## 3. Scope — binding non-goals (B2–B6 own these)

- No guided sentence editor, no recipe fields on `hr.formula.rule`, no include/exclude (B2).
- No tax band editor, no calendar/payment tab, no Vietnam · Complete template (B3).
- No Mapping Studio / Payslip Studio round-trip cards, no readiness counts (B4).
- No outputs table, no test runner, no evidence hash (B5).
- No Vietnamese `.po` yet (B6) — but every string goes through `_t()` / QWeb text so B6 can extract.
- Do not touch the old modal's markup/logic beyond the door rewiring; it remains the fallback.
- Do not edit `pb_formula_studio/models/pb_formula_studio.py` (ledger rule 7).

## 4. Design (build to this — the bar is verbatim in ledger rule 6)

**"extreme WOW, intuitive, out-of-this-world experience, best in class."** Benchmark: the best
SaaS onboarding you know (Linear, Stripe, Notion), not stock Odoo.

### 4.1 Layout
Root `div.pbim.pbim-page.pbbp` inside the normal app frame (the app's own left sidebar stays).
Three columns at ≥1200px: **journey rail** 232px (`#241F52`, white text), **content** (fluid,
max 980px, canvas `#F4F5FB` with white cards), **pay panel** 344px (white, left border `#E8E9F3`).
At 900–1199px the pay panel becomes a sticky bottom bar showing only the take-home number and a
"Details" toggle that slides the full panel up. At ≤899px (390 phone) the rail becomes a
horizontal stepper under the header and the pay panel is the bottom bar. Nothing scrolls
horizontally, ever.

**Header** (white, 64px, sticky): back chip "Payroll configurations" (opens Formula Studio with
`{open_switcher: true}` — see §6.3) · crumb "New configuration" (becomes the configuration name
once created, with its code in muted mono beside it) · right side: status pill (before creation
"Not saved yet"; after: "Draft · saved just now / 2 min ago", green dot; while saving: spinner
"Saving…"; on error: rose "Could not save — retry") · button **Skip to the grid** (ghost; only
after the draft exists; opens Formula Studio on the config) · button **Save & close** (soft;
before creation it is "Close" and simply leaves).

**Rail**: eyebrow "NEW CONFIGURATION", six rows: number circle + label + one-line hint
(Start "Name, starter, who you pay" · Pay rules "Components, tax, calendar" · Connect "Sources,
payslip, approvals" · Outputs "Every formula, one table" · Test "Try the days that aren't ordinary"
· Finish "Review and open"). States: idle (circle `rgba(165,180,252,.16)`), active (white circle,
purple number, row tint `rgba(255,255,255,.08)`), done (green `#0EA371` check), attention (warn
`#D97706` dot — reserved for later phases). Rows are buttons; steps after `start` are disabled
until the draft exists (tooltip "Create the configuration first"). Footer of the rail: a compact
"Saved to <company name>" line with the company Lucide `building-2` icon.

**Footer** (content column, sticky bottom, white, top border): left "Step 1 of 6 · <starter name>
· <n> components" (after creation), right **Back** (ghost) and the primary **Continue to pay rules →**
(purple, 44px, keyboard Enter when a text field is not focused; ⌘/Ctrl+Enter always).

### 4.2 Hero moment — the pay panel (`pay_preview.js`)
Eyebrow "SEE IT IN SOMEONE'S PAY" + a `LIVE` pill (green when the last compute succeeded, grey
"Waiting" before the draft exists, rose "Couldn't compute" on error with a Retry link).
Row: avatar initials in `#EDEAF8` + sample name + subtitle (what the sample's inputs say, e.g.
"Basic 30,000,000 · 1 dependant"). **"Try a different situation"** select listing the
configuration's samples (`hr.formula.sample.data` of the config, ordered by sequence). Then
**Estimated take-home pay**: big number (36px, 800 weight) formatted like "31.16m" with the
currency symbol/code small beside it, **animated count-up/down over 420ms** on every change, and
a small delta chip beside it ("+1.20m" green / "−0.36m" rose) showing the change since the
previous value in this session; chip fades after 4s. Below: four lines — Cash earnings, Employee
deductions, Income tax, Employer cost — full-precision numbers right-aligned, `en-US` grouping,
negative values with a leading "− ". Then a link **Adjust sample inputs** that opens an inline
editor (kit modal) listing the config's input components (from `get_test_data`), editable numbers,
Save → `save_sample_inputs` → recompute. Then a muted footnote "Calculated by the real payroll
engine from this configuration. Sample data only."
Before the draft exists the panel shows a designed placeholder: the same layout with a dotted
avatar, "Your sample employee appears here the moment the configuration is created", and a muted
"— — —" number. No spinner-only states.

How the four lines are found (server, `bp_preview`): use the rule classification the engine
already carries — check `hr.formula.rule` for `net_role` / `pay_role` fields (VALUEKIND
programme; grep `pay_role\|net_role` in `formula_rule.py`) and use them if present; otherwise
fall back to codes: take-home = `NET`, cash earnings = `GROSS`, deductions = `EEDED`, tax = `PIT`,
employer cost = `ERCOST`. Return each as `{label, value, code}` and `None` (rendered as "—") when
the configuration has no such component (blank canvas). State which path you used in the report.

### 4.3 Start step
Eyebrow "01 / CHOOSE YOUR STARTING POINT", H1 **"A clear start. A connected payroll."**, lead
"Choose how to build this configuration. You can fill in the details now and connect the
optional parts whenever you are ready."

Card **Identity** (white, 18px radius): Company (read-only chip with `building-2` icon,
`env.company` name, hint "Switch company in the top bar") · Configuration name (text, required,
placeholder "Vietnam · Monthly payroll") · Country (select from `hr.formula.config.country_code`
selection, default VN) · Pay cycle (select from `cycle_type` selection, labels: Regular payroll ·
Mid-month advance · End-month payroll · Full and final) · Effective from (date, default the first
day of next month).

Section **"HOW WOULD YOU LIKE TO START?"** — starter cards in a responsive grid (3 per row at
≥1200, 2 at ≥900, 1 below). Cards come from `bp_templates()`; for the chosen country: one card per
registry template (name, Certified/Draft badge, "v2026.1 · effective 1 Jan 2026", "37 components
· 1 rate table", 2-line description), then always **Import Excel workbook** (`file-spreadsheet`
icon: "Review a payroll workbook, keep its formulas, map its inputs") and **Blank canvas** (`plus`
icon: "Start with your own components. The country's shared rules stay available"). Selected
card: purple border + `#EDEAF8` tint + check. Default selection = the template whose `key` is
`vn_complete_2026` if present else `vn_standard_2026` if present else the first registry template
for the country else Blank canvas. Hide the legacy built-in `vn_standard` (its `builtin` flag is
true and it is superseded by the pack) — never show two Vietnam cards with the same components.
Under the grid a one-line note in `#EDEAF8`: "The complete Vietnam library is selected. Tax
values come from the 2026 rule pack; you can review them in Pay rules."

Section **"WHO ARE YOU PAYING?"** — 2×2 tiles (multi-select, toggle): Local employees ("Salary,
allowances, insurance and income tax", `users`), International employees ("Residency, insurance
eligibility and payment currency", `globe`), Short-term employees ("Contract length, payment
threshold and tax commitment", `clock`), Guaranteed take-home pay ("A specialist recipe for
net-to-gross contracts", `wallet`). Local pre-selected. Stored in `situations_json.audiences`.

Section **"REAL LIFE BELONGS IN THE DESIGN"** — a card with four checkbox rows: Joiners & leavers
(on), Annual & event-based pay (on), Salary changes within a month (off), Corrections & arrears
(off), each with its one-line hint from the prototype. Stored in `situations_json.reallife`.
(B2/B3 consume these; B1 only stores and shows them as chips in the Finish summary.)

**Continue** (before creation) → validation inline (name required: red helper under the field,
focus it; no toast-only errors) → `bp_start`. During creation the button shows a spinner and the
content dims; a small three-line progress list appears in the identity card: "Creating the
draft ✓ · Adding the starter's components ✓ · Preparing a sample employee ✓" (each ticks as the
server reports it — the RPC returns after all three; animate the ticks 150ms apart on success).
On failure: an inline rose panel at the top of the step with the server's plain reason and a
**Try again** button; nothing was created (server transactional).

After creation: the identity card locks Country and starter (grey, with "Change" links); the
crumb shows the name; status pill "Draft · saved just now"; rail step 1 = done; navigate to
`rules`. **Change starter** later → confirmation dialog (kit modal): "Replace the components?
This removes all <n> components and formulas of this draft and adds the <starter> ones. Anything
you edited by hand is lost." Buttons "Replace components" (rose) / "Keep what I have". Server
`bp_restart` refuses if the config is not `draft` or has payslips (`hr.payslip` with
`formula_config_id`), returning the reason.

**Import Excel workbook** as the starter → `bp_start` with `template='blank'` then
`doAction` the multisheet import wizard (see §6.4) with `{default_config_id, pb_blueprint_return: true}`.
When the wizard chain finishes it lands back on `pb_blueprint` at step `rules` (§5.5).

### 4.4 Thin steps (rules, connect, outputs, test)
Each renders the real eyebrow/H1/lead from the plan (e.g. "02 / WHAT GOES INTO PAY — Every
component. One clear rule.") and a designed panel: a `pbim-note` card "This step arrives in the
next release. For now your components are ready in the grid — open it any time with Skip to the
grid." plus, for **rules**, a read-only list of the seeded components (code chip, name, type
badge input/formula/constant) so the step is not empty. Continue moves on; Back moves back.

### 4.5 Finish (minimal, real)
Eyebrow "06 / A CONFIGURATION YOU CAN EXPLAIN", H1 **"Ready to review. Built to evolve."**
Tiles: components / formula rules / inputs (counts from the config). Identity card (name, code,
company, country, cycle, effective from, starter, situations as chips). Button **Finish & open**
→ `bp_finish` → opens Formula Studio on the config. Muted line: "Finishing marks the setup as
complete. Activating the configuration for real pay runs stays a separate, checked step."

### 4.6 Zero dead-ends checklist (each must be demonstrated in the report)
no starters for a country (only Excel + Blank shown, note "No starter for <country> yet") ·
no samples on the config (panel shows "No sample employee yet" + **Add a sample** →
`add_manual_sample` then select it) · `compute_preview` error (rose LIVE pill + reason + Retry) ·
draft belongs to another company (server refuses `bp_load` with a plain reason; client shows a
full-panel message with "Back to Payroll configurations") · resume of a `finished` blueprint
(opens Formula Studio directly) · browser refresh mid-journey (URL carries `config_id`; state
reloads from the server) · double-click Continue (token; one draft) · RPC network failure
(toast with reason + retry; never a blank page).

## 5. Server design (`pb_blueprint`)

### 5.1 Manifest
`depends: ['web', 'pb_hr_payroll_formula', 'pb_formula_studio', 'pb_import_kit', 'pb_hub']`,
version `19.0.1.0.0`, category "Human Resources/Payroll", `application: False`. Manifest
`summary`/`description` are user-visible (GR7) — no engineering names, no "Odoo".
Assets in `web.assets_backend`: `static/src/scss/blueprint.scss`, then JS in import order
(`js/blueprint_steps.js` pure helpers → `js/pay_preview.js` → `js/step_*.js` → `js/blueprint.js`),
then `static/src/xml/*.xml`. `web.assets_unit_tests`: `pb_blueprint/static/tests/**/*`.
Data: `views/pb_blueprint_action.xml` (client action `action_pb_blueprint`, name "New configuration",
tag `pb_blueprint`), `security/ir.model.access.csv`.

### 5.2 `pb.formula.blueprint` (`models/blueprint.py`)
Fields: `config_id` M2o `hr.formula.config` required, `ondelete='cascade'`, unique (Odoo 19
`models.Constraint`, NOT `_sql_constraints`); `company_id` related `config_id.company_id` stored;
`token` Char required, unique per company (`models.Constraint`), index; `state` Selection
`draft|finished|abandoned` default draft; `step` Char default `start` (one of the six keys —
validate in `write`); `template_key` Char; `effective_from` Date; `situations_json` Text (JSON:
`{audiences:[…], reallife:[…]}`); `optional_status_json` Text (JSON, default
`{"mapping":"not_started","payslip":"not_started","approvals":"info"}`); `calendar_json`,
`review_items_json` Text (empty JSON for now); `pack_id` M2o the legislation pack model if it
exists (find it: grep `_name = 'hr.formula.legislation` in `pb_hr_payroll_formula/models`;
if the model name differs, use the real one) optional; `pack_version` Char; `evidence_hash`,
`tests_hash` Char; `revision` Integer default 1 (bump on every `bp_save`); `create_uid`
displayed as the owner. `_order = 'write_date desc'`. Helper `_ensure_company(self)` raises
`AccessError` with a plain message when `config_id.company_id` ∉ `env.companies`.
Access: `group_formula_user` read; `group_formula_manager` all (mirror
`pb_hr_payroll_formula/security/ir.model.access.csv`).

### 5.3 `pb.blueprint.studio` (AbstractModel, `models/blueprint_studio.py`) — all `@api.model`
Every method returns plain dicts; every failure returns `{'ok': False, 'reason': <plain sentence>}`
(never a raw traceback to the UI) except access errors which raise.
- `bp_templates(country_code=None)` → `{ok, country, starters:[…], countries:[{code,label}]}`.
  Wraps `pb.formula.studio.wizard_templates()`; drops `builtin` entries; filters by country;
  adds `kind: 'template'|'excel'|'blank'`, `component_count`, `rate_table_count`, `default: bool`.
- `bp_start(vals, token)` → `{ok, config_id, blueprint_id, step, rule_count, sample_id}`.
  `vals = {name, country_code, cycle_type, effective_from, template_key, situations}`.
  Idempotent: if a blueprint with this `token` exists for the company → return it unchanged.
  Inside ONE `self.env.cr.savepoint()`: create `hr.formula.config` `{name, country_code, cycle_type,
  company_id: env.company.id, state:'draft'}` (code auto), seed: `template_key=='blank'` → nothing;
  else `hr.formula.config.template.search([('code','=',template_key),('state','!=','superseded')], limit=1)`
  → `seed_config(cfg)`; then ensure at least one sample (`sample_data_ids` empty → create one
  `hr.formula.sample.data` named "Sample employee" with sensible inputs: for each input rule its
  `default_value` or, if the code is `BASIC`, 30,000,000; `STDDAYS` 26; `DEPS` 1); create the
  blueprint. On any exception: the savepoint rolls back everything, log at WARNING, return
  `{'ok': False, 'reason': …}` with the message made plain (e.g. seed errors → "The starter
  '<name>' could not be added: <error text>").
- `bp_load(config_id)` → `{ok, config:{id,name,code,country_code,country_label,cycle_type,cycle_label,
  currency,state,company}, blueprint:{id,state,step,template_key,template_name,effective_from,situations,
  optional_status,revision,owner,write_date}, counts:{components,formulas,inputs,constants,samples},
  components:[{id,code,name,column_type,column_letter}], samples:[{id,name,subtitle}], starters: bp_templates(country)}`.
  Refuse (plain reason) when the config is not visible or has no blueprint.
- `bp_save(config_id, patch, revision)` → `{ok, revision}`; allowed keys `name, effective_from,
  situations, step, cycle_type`; `cycle_type`/`name` write through to the config; conflict when
  `revision != blueprint.revision` → `{ok:False, conflict:True, reason:"Someone else changed this
  draft. Reload to see their version."}`.
- `bp_preview(config_id, sample_id=None)` → `{ok, sample_id, sample:{id,name,subtitle}, take_home:{value,code},
  lines:[{key:'cash'|'deductions'|'tax'|'employer', label, value, code}], currency:{symbol, code, decimals}}`.
  Calls `pb.formula.studio.compute_preview`; maps values by `column_letter` → rule code. Errors →
  `{ok:False, reason}`.
- `bp_add_sample(config_id)` → wraps `add_manual_sample`, returns `{ok, sample_id}`.
- `bp_restart(config_id, template_key)` → guards (draft only, no payslips, company) → unlink
  `rule_ids`, `rate_table_ids`, `sample_data_ids`, reset `col_letter_hwm` to 0 if that field is
  writable → reseed as in `bp_start` → `{ok, rule_count}`.
- `bp_close(config_id, step)` → saves the step, returns `{ok}`.
- `bp_finish(config_id)` → guards (config visible, blueprint draft; formulas valid:
  `not cfg.has_errors and not cfg.has_circular_refs` after `action_validate_formulas`) → state
  `finished`, step `finish` → `{ok, config_id}`; idempotent on a finished one.
- `bp_discard(config_id)` → allowed only while `draft` and the config has no payslips: unlink the
  config (cascade removes the blueprint) → `{ok}`. Used by nothing in B1's UI except a "Discard
  this draft" link in the header's overflow (kit kebab) with a confirmation — include it.

### 5.4 `bureau_board` override (`models/formula_studio_ext.py`, `_inherit='pb.formula.studio'`)
Call `super()`, then one `search_read` of blueprints `[('config_id','in',ids),('state','=','draft')]`
and set `card['blueprint'] = {'id': …, 'step': …, 'step_no': 1..6, 'total': 6}` else `False`.

### 5.5 Import return door (`models/formula_config_ext.py`, `_inherit='hr.formula.config'`)
Override `studio_people_mapping_action(self, rules)`: if `self.env.context.get('pb_blueprint_return')`
and a draft blueprint exists for `self` → write its step to `rules` and return
`{'type':'ir.actions.client','tag':'pb_blueprint','target':'current','params':{'config_id': self.id},
'context': {'config_id': self.id}}`; else `super()`. Read `formula_config.py:1605-1632` and
`multisheet_import_wizard.py:3092-3111` first; confirm the `category_review_action` chain still runs.

### 5.6 Tests (`pb_blueprint/tests/`, tag `post_install`, run on p9clone)
1. `test_bp_start_idempotent`: same token twice → same config id; one blueprint row.
2. `test_bp_start_seeds_starter`: `vn_standard_2026` → rule_count equals the template's component
   count, one rate table, ≥1 sample, config state draft, company = env.company.
3. `test_bp_start_blank`: zero rules, one sample created, blueprint step `start`.
4. `test_bp_start_failure_rolls_back`: unknown template key → `ok False` and NO config created.
5. `test_bp_load_refuses_other_company`: blueprint on company A, user of company B → refused.
6. `test_bp_save_revision_conflict`.
7. `test_bp_preview_lines`: take_home is the NET value from `compute_preview`; lines present.
8. `test_bp_restart_guard`: not-draft config → refused with reason; draft → reseeded counts.
9. `test_bp_finish_requires_valid_formulas` (inject an invalid formula → refused; fix → finished).
10. `test_bureau_board_carries_blueprint`.
11. `test_import_return_door`: with `pb_blueprint_return` context the action tag is `pb_blueprint`;
    without it, the super behaviour is unchanged.
12. `test_white_label_sources`: scan `pb_blueprint` XML/JS/py user strings + manifest for "Odoo"
    and for the banned on-screen words "schema", "blueprint", "config " (pattern from
    `pb_formula_studio/tests/test_one_mapping_home.py`; allow "Blueprint" only in module docstrings/comments).
Hoot: `static/tests/blueprint_steps.test.js` for the pure helpers (step order/next/prev, `fmtShort`
"31.16m"/"950k"/"0", delta formatting, continue label per step).

## 6. Client design (`pb_blueprint/static/src`)

### 6.1 Files
- `js/blueprint_steps.js` — pure exports: `STEPS = ["start","rules","connect","outputs","test","finish"]`,
  `STEP_META` (label, hint, eyebrow, title, lead), `nextStep/prevStep`, `continueLabel(step)`,
  `fmtShort(value, currency)`, `fmtFull(value)`, `deltaLabel(prev, next)`.
- `js/pay_preview.js` — `PayPreview` component (props: `configId`, `samples`, `sampleId`, `preview`,
  `status`, `onPickSample`, `onAdjust`, `onRetry`, `onAddSample`). Count-up via `requestAnimationFrame`.
- `js/step_start.js`, `js/step_thin.js` (rules/connect/outputs/test share one component with
  per-step meta), `js/step_finish.js`, `js/sample_inputs_dialog.js` (kit modal).
- `js/blueprint.js` — `PbBlueprint` client action: `setup()` → `this.env.config.setDisplayName(_t("New configuration"))`
  (GR8); services `orm`, `action`, `notification`; `useHotkey("control+enter", …)`; reads
  `props.action.params|context` for `config_id` (resume) and `open_switcher`; `onWillStart` loads
  templates or `bp_load`; state as one `useState`. Exports nothing but the class; registers
  `registry.category("actions").add("pb_blueprint", PbBlueprint)`.
- `xml/blueprint.xml`, `xml/pay_preview.xml`, `xml/steps.xml`; `scss/blueprint.scss` (prefix `pbbp-`,
  include `pbim-root-vars`; no Sass `min()/max()` with mixed units — BP5).
- Icons via `ic()` from `@pb_import_kit/js/import_icons` (BP2); if a needed Lucide glyph is missing
  add it to that registry (W2), never a local icon file.

### 6.2 Navigation contract
Rail buttons + footer Back/Continue set `state.step`; every change calls `bp_close(config_id, step)`
(debounced 400ms) so a refresh/resume lands on the same step. URL: push `config_id` into the action
params via `this.action.doAction` is NOT needed — instead call `this.env.services.router.pushState({config_id})`
if the router service is available (check how `pb_payrun_wizard` or `mapping_studio.js` handle
refresh; copy the working idiom and note it in the report).

### 6.3 Doors into and out of the journey (pb_formula_studio seams — keep them tiny)
- `formula_studio.js:5754 openWizard()`: at the top, `if (registry.category("actions").contains("pb_blueprint")) { this.state.configPickerOpen = false; this.state.configSwitcherOpen = false; return this.action.doAction({type:"ir.actions.client", tag:"pb_blueprint", params:{}}, {clearBreadcrumbs:false}); }` — the rest unchanged (fallback).
- `formula_studio.js:575-579` (`open_wizard` arrival): unchanged — it calls `openWizard()` which now redirects.
- `formula_studio.js:569-617`: honour a new arrival key `open_switcher` (params or context) → `this.openConfigSwitcher()` even when a config is loaded (the journey's back chip uses it).
- Picker card (`studio.xml:3016-3069`): when `c.blueprint` is truthy, replace the score ring block
  with a **setup ring** (same 52px SVG, stroke `#5A4BB0`, progress `step_no/total`, centre text
  "3/6") and a caption "Resume setup" under the metrics; in `.cs-card-actions` the first button
  becomes **Resume setup** (soft, primary tint) → `doAction({tag:"pb_blueprint", params:{config_id}})`,
  followed by "Open" (ghost, to the grid). Styles in `cfgsw.scss` (`.cs-ring.setup`, `.cs-resume`).
- `formula_config_views.js:12-18`: unchanged (it routes through `open_wizard`).
- Empty-state button `studio.xml:35`: unchanged (calls `openWizard`).

### 6.4 Excel door
`this.action.doAction({type:"ir.actions.act_window", name: _t("Import from Excel"), res_model:
"hr.formula.multisheet.import.wizard", view_mode:"form", views:[[false,"form"]], target:"new",
context:{default_config_id: cid, pb_blueprint_return: true}})` — do NOT set `pbfs_studio_import`.
`onClose`: reload `bp_load` (the wizard may have been cancelled). Verify in Chrome that a completed
import lands on the journey at step 2 with the imported components listed.

## 7. Deploy + verify (ledger "Deploy ritual")
1. Repo tests: on p9clone `-i pb_blueprint --test-enable --test-tags /pb_blueprint --stop-after-init`
   with the alternate ports; hoot tests via `/web/tests?module=pb_blueprint` in Chrome (or the
   headless runner if one exists — state which).
2. `pg_dump` each DB; install `-i pb_blueprint -u pb_formula_studio` on p9clone → payobook → abm →
   payobook_template (detached `systemd-run`, sentinel, `EXIT=0`, grep the log for ERROR/CRITICAL).
3. Asset purge + `web.assets.version` bump per DB; service start; "Registry loaded".
4. Verify per DB: tree hash repo vs server for `pb_blueprint` and `pb_formula_studio`; manifest vs
   `ir_module_module.latest_version` (normalise the `19.0.` prefix).
5. Chrome (payobook as ash, company Payobook Vietnam JSC; then abm): walk §8 cases, screenshots at
   1440×900 and 390×844, light theme (dark if the app supports it — check `biz_theme`).
6. Commits: (a) `feat(pb_blueprint): guided New configuration journey — shell, Start, draft lifecycle`,
   (b) `feat(pb_formula_studio): route New configuration to the guided journey + Resume setup cards`,
   (c) docs/ledger additions. Explicit paths only; never stage `RIZE/` or `design_poc/`.

## 8. Numbered acceptance cases (run all; report each as PASS/FAIL with evidence)
1. Picker → New configuration → full-screen journey opens with the back chip, rail, placeholder pay panel.
2. Name empty → Continue → inline red helper, focus on the field, no toast.
3. Vietnam · Essentials selected by default (until B3 adds Complete); note visible; Import Excel + Blank cards present.
4. Continue → progress ticks → lands on step 2; pay panel LIVE shows a take-home number; four lines populated.
5. Double-click Continue → exactly one configuration exists (check `hr.formula.config` count before/after).
6. Change sample in the picker → number animates; delta chip appears then fades.
7. Adjust sample inputs → change BASIC → Save → number changes; value persisted on the sample.
8. Config with no samples (delete via shell on p9clone) → "Add a sample" path works.
9. Save & close → picker card shows setup ring "2/6" + Resume setup; Resume → lands on step 2 with the name and starter locked.
10. Skip to the grid → Formula Studio opens on the config; Back chip in the studio not required.
11. Change starter → confirmation → components replaced; count on the footer updates.
12. Blank canvas → zero components; thin rules panel says so; Finish & open works with zero formula errors.
13. Excel workbook starter → import wizard opens; cancel → back on the journey; complete an import (use any small workbook from the repo's test fixtures — find one under `pb_hr_payroll_formula/tests` or `tests/fixtures`) → returns to step 2 with components.
14. Finish & open → blueprint `finished`; Formula Studio opens; picker card shows the normal ring (no Resume).
15. Refresh the browser mid-journey → same step and state.
16. Another company's draft (create on company 1 via shell) → open with company 5 → plain refusal panel + back door.
17. `compute_preview` failure (temporarily break a formula via the grid) → rose LIVE pill with reason + Retry; fix → recovers.
18. 390px: horizontal stepper, bottom pay bar, no horizontal scroll; all buttons reachable.
19. Keyboard: Tab order sane; Enter continues when not in a text field; Esc closes the modal; ⌘/Ctrl+Enter continues anywhere.
20. Old fallback: with `pb_blueprint` uninstalled on p9clone, the old modal still opens (test once, then reinstall).
21. White-label + vocabulary scan passes (test 12) and a manual read of every visible string.
22. All four DBs: module installed, version 19.0.1.0.0, journey opens.

## 9. Report back (write `docs/handovers/BLUEPRINT_PHASE_B1_REPORT.md`)
- Results table for cases 1–22 with screenshots' paths (keep PNGs out of git; describe them).
- Which classification path `bp_preview` used (net_role/pay_role vs code fallback) and the exact field names found.
- The refresh/resume idiom used (router vs params) and why.
- Every `pb_formula_studio` line touched (file:line, before → after).
- Seeded-sample defaults used for Essentials and what the hero showed (numbers).
- Time per DB install; any ERROR lines and how they were resolved.
- New gotchas appended to `BLUEPRINT_LEDGER.md` as BP9+ (mandatory, even "none found" is a line).
- Self-score against the design bar (hero, dead-ends, plain language, motion, keyboard) with one sentence each; list what you would improve given one more hour.
- Anything deferred, with the reason — never silently narrow the scope.
