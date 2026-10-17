# BLUEPRINT Programme Ledger — the guided "New configuration" journey

Every BLUEPRINT phase handover references this file. Read it FULLY before coding. Append
(never rewrite history) when you hit a new gotcha — that is part of every phase deliverable.

## Where this programme came from

On 2026-09-10 the owner approved an interactive prototype
(`design_poc/vietnam_configurator/Payroll_Blueprint_Option2.html`, handoff
`design_poc/vietnam_configurator/IMPLEMENTATION_HANDOFF.md`, rationale `OPTION2_DESIGN.md`)
that replaces the 5-step "New Formula Config" popup in Formula Studio with a full-screen,
six-step guided journey: **Start → Pay rules → Connect → Outputs → Test → Finish**, with a
live "see it in someone's pay" panel, plain-language rule sentences that generate the Excel
formulas underneath, and hand-offs to the existing Mapping Studio and Payslip Studio.
Approved plan: `/Users/adity/.claude/plans/i-want-you-to-polymorphic-shore.md` (copied
verbatim as `docs/handovers/BLUEPRINT_PLAN.md`).

Method: Fable designs each phase handover; an Opus agent builds, tests, deploys, Chrome-
validates, self-reviews and reports; phases run back to back. Only a destructive action
or a genuine scope decision stops the run.

| Phase | Name | Delivers |
|---|---|---|
| **B1** | Shell, Start, draft lifecycle | module `pb_blueprint`, client action, rail, hero panel, Start step, idempotent draft, picker rewiring, Resume setup, import return door |
| **B2** | Guided rules engine + Components tab | recipe fields, `compile_recipe`, sentence editor (guided + Excel lanes), include/exclude, bulk + keyboard |
| **B3** | Tax & Calendar tabs + Vietnam · Complete starter | PIT band editor, relief/caps, calendar/payment prefs, `config_template_vn_complete.xml` |
| **B4** | Connect step | Mapping Studio + Payslip Studio round-trips, readiness counts, status semantics, Approvals info card |
| **B5** | Outputs + Test steps | money-flow strip, outputs table + inspector, scenario runner, confirm-expected gate, evidence hash |
| **B6** | Finish, VI, polish | Finish step, discard, `vi_VN.po`, motion/keyboard pass, all-DB walkthrough |

## Owner decisions (2026-09-10) — binding

- **Approvals** card on the Connect step is **information only** ("Pay runs already follow
  Officer → HR → Finance approval. Custom approval rules per configuration are coming").
  No button. The existing enforced chain (`pb_payruns/models/hr_payslip_run.py`) is untouched.
- **Excel workbook** starting point creates a blank draft and launches the **existing**
  multisheet import review, which returns to the journey. Re-skinning that screen is a later phase.
- **Two Vietnam starters**: *Vietnam · Essentials* (= existing `pb_pack_vn` template
  `vn_standard_2026`, untouched) and *Vietnam · Complete* (Essentials + the 38 workbook
  components with guided rules; built in B3). **Complete is pre-selected.**
- **Vocabulary on screen**: "configuration" (the picker is titled "Payroll configurations").
  Never "schema", "blueprint", "config", "rule set" in anything a user reads. "Blueprint" is
  an internal/engineering name only (module, docs, commit messages).

## Parent ledgers — everything in them binds here

Read before B1: `docs/handovers/GROUP_LEDGER.md` (binding rules 1–10, GR-series, deploy
ritual), `docs/handovers/TIDY_LEDGER.md` (rules 11–15, T-series), `docs/handovers/WFPLAN_LEDGER.md`
(W-series incl. **W2** Lucide registry only, **W17.4** `@pb_import_kit/js/import_icons`),
`docs/handovers/MAPFIX_LEDGER.md` (code contract), `docs/handovers/JOURNEY_LEDGER.md` (Mapping
Studio doors), `docs/FORMULA_ENGINE_CONVENTIONS.md`.

## Target & credentials

- Live databases on the cluster (verified 2026-09-10): **`p9clone`** (rehearsal + tests),
  **`payobook`** (master, https://payobook.com), **`abm`** (tenant), **`payobook_template`**
  (golden template). There is **no `acme`** database any more — older memory/docs that
  list it are stale. Deploy order: p9clone → payobook → abm → payobook_template, `pg_dump` before each.
- All four already have `pb_formula_studio 19.0.1.181.0`, `pb_hr_payroll_formula 19.0.1.123.0`,
  `pb_import_kit 19.0.1.17.0`, `pb_hub 19.0.1.8.1`, `pb_integrations 19.0.1.13.0`,
  **`pb_pack_vn 19.0.1.0.1` installed** (so the Essentials starter exists everywhere).
- Master admin `ash@biztinct.com` / `{withheld: rize-admin}`; demo company **Payobook Vietnam JSC**
  (id 5, VN, VND, 4,533 people, 15 active configurations incl. the 12 `DEMO_*` division ones).
  Demo login `demo@payobook.com` / `{withheld: demo-user}` (locked to company 5).
- ssh alias `Payobook19v2`; Odoo runs as `odoo`, `sudo service odoo-server {stop,start}`,
  conf `/etc/odoo-server.conf`, log `/var/log/odoo/odoo-server.log`. ONE addons dir
  `/odoo/odoo-server/addons` (needs `sudo` to list).

## Binding rules (violations = phase failure)

1. **White-label**: never "Odoo" in any user-visible string, manifest `description`, or `.po` msgstr.
2. **Plain English** on every label, toast, empty state, sentence. Screen words, not code words.
3. **ONE addons dir**; scoped per-module `rsync --delete` only; never `--delete` into
   `/odoo/odoo-server/addons/` itself; never deploy vendored standard addons.
4. **Commit per feature**, explicit paths, `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`,
   never push. Unrelated dirty files exist in the tree (RIZE/ folders) — never stage them.
5. **Design system**: Lucide via the single `ic()` registry (`pb_import_kit/static/src/js/import_icons.js`;
   add missing icons THERE); `t-out` never `t-esc` for `ic()`; no emoji; no gradients; kit primitives
   `.pbim-*` where they fit (`.pbim-modal` for popups); palette primary `#5A4BB0`, dark `#241F52`,
   soft `#EDEAF8`, soft2 `#DDD6F2`, canvas `#F4F5FB`, ink `#1E1B2E`, muted `#6B7280`, line `#E8E9F3`,
   good `#2E7D4F`, rose `#DC2668`, warn `#D97706`, teal `#0F766E`; font Inter.
6. **Design bar (verbatim, score against it in every report): "extreme WOW, intuitive,
   out-of-this-world experience, best in class."** Hero moment named; zero dead-ends (every
   empty/loading/error/partial/huge state designed, every failure names its reason and next step);
   plain language; motion with purpose; keyboard + bulk ergonomics; Chrome-MCP validate at
   1440 and 390, every flow clicked, not just rendered.
7. **Never edit `pb_formula_studio/models/pb_formula_studio.py`** (13.5k lines, parallel
   programmes). Extend via `_inherit = 'pb.formula.studio'` in `pb_blueprint`. JS/XML seams in
   `pb_formula_studio` are allowed but must be minimal and listed in the phase report.
8. **The draft is the working copy.** Never mutate an active configuration as the wizard's
   working copy; never half-create (draft creation is one transaction; on failure nothing exists).
8a. **Settings are not pay logic** (SCHEMECTX P3, 2026-09-19). *"Edit mode writes settings to
   the live configuration, as the studio always has; it never writes pay logic to a configuration
   that is not a draft or that has paid anyone."* Rule 8 protects the RULES — formulas, bands,
   brackets, calendar, components. Identity, accounting, connections, export options, part-month
   pay, back-pay and the source lanes are not rules and have ALWAYS been written straight to a
   live configuration through the studio's `save_config_settings`; edit mode keeps exactly that
   contract and adds nothing to it. The lock is one expression, in one place
   (`blueprint_edit.py::_edit_locks`): `pay_logic = state != 'draft' or has_payslips`,
   `country = has_payslips`.
9. **Server decides readiness.** Client flags (`configured`, `passed`, `is_valid`) are display
   only; every gate (finish, include/exclude, tax write) is enforced in the RPC.
10. **Tenant parity**: every module deploys to every database (rule from `tenant-module-sync-rule`).
11. **Tests on p9clone** with `--http-port=8199 --gevent-port=8198`, then production. Chrome-validate
    on payobook AND abm.

## Rulings (Fable, 2026-09-10 — binding unless the owner overrules)

- **BP-R1 Full-screen client action, not a popup.** Tag `pb_blueprint`, action xmlid
  `pb_blueprint.action_pb_blueprint` (name "New configuration"). The old modal stays in
  the studio as the fallback when the tag is not registered.
- **BP-R2 Steps are keys, not numbers**: `start, rules, connect, outputs, test, finish`
  (`pb_payrun_wizard/static/src/js/payrun_wizard.js:26-33` pattern). Rail labels:
  Start · Pay rules · Connect · Outputs · Test · Finish.
- **BP-R3 Recipe provenance lives on the rule** (`_inherit hr.formula.rule`): `bp_recipe_json`,
  `bp_generated_formula`, `bp_generated_revision`, `bp_formula_source` generated|manual —
  mirrors `column_role_source`/`value_kind_source` (`formula_rule.py:660-664, 722-727`, guard
  `:1682-1690`). A `write()` override flips to `manual` when `excel_formula` changes to
  anything other than `bp_generated_formula`. Regeneration only rewrites `generated` rules.
- **BP-R4 Generated formulas reference column LETTERS** (`=A+H`, `=BRACKET(VNTAX,AE)`), never
  codes: letters are frozen for life (`formula_rule.py:1615`), the converter substitutes codes by
  regex (`:1225-1238`), the VN pack is letter-based. Recipes reference codes; the compiler
  resolves via a `{code: letter}` map. Validate with `pb.formula.studio._check_formula`
  (`pb_formula_studio.py:11636`) + `FormulaValidator.check_circular_references`.
- **BP-R5 Tax writes go through existing paths**: bands → `save_rate_table` (`:11558`);
  relief/caps/rates → `constant_value` on constant rules (`_legis_constant` `:3466`, with
  `formula_version_reason='legislation'`). Pack pin lives on the blueprint, not the config.
  `vn_tax_table_id` / `vn_insurance_policy_id` are left alone (engine computes from VNTAX).
- **BP-R6 Draft creation does NOT use `create_config`** (hard-codes VN, ignores company).
  `bp_start` creates `hr.formula.config` with explicit `company_id`, then
  `hr.formula.config.template.seed_config` (`formula_config_template.py:213`). `token` unique → idempotent.
- **BP-R7 Include/exclude**: no `active` on `hr.formula.rule`. Exclude = delete the rule (warn if
  edited by hand); include = re-seed that one component from the template JSON (new letter), then
  regenerate dependants.
- **BP-R8 Reuse by hand-off, not import.** Studio JS files export nothing; reach Mapping
  Studio / Payslip Studio / Formula Studio via `doAction` with `pb_back`
  (`pb_hub/static/src/js/hub_nav.js:52-101`).
- **BP-R9 Bilingual labels = the rule's translatable `salary_rule_id.name`**
  (`hr_payslip_formula.py:1212`). No new label fields.
- **BP-R10 Evidence hash** = sha256 of sorted `(code, column_type, excel_formula, constant_value)`
  + rate brackets; `tests_hash` stamped at run time; stale = mismatch. Samples with
  `expected_confirmed=False` are pending, never passed.
- **BP-R11 Company chip is read-only** (the current company); switching company happens in the
  top bar. The draft, the blueprint and every search are scoped to `env.company`.

## Plumbing facts (verified 2026-09-10 — do not re-derive)

### The old wizard and the picker (pb_formula_studio)
- Wizard methods `formula_studio.js:5753-5807` (`openWizard` … `importExcel`); markup
  `studio.xml:3855-3994`; styles `studio.scss:604-660` (`.pbfs-wz-scrim/.pbfs-wz/.wz-rail/.wz-step`).
  State keys `wizardOpen, wizardStep, wizardForm, wizardTemplates, wizardBusy` (`:390-394`).
- Three doors into it: empty-state button `studio.xml:35`; switcher footer `studio.xml:3081-3084`;
  native list "New" → `formula_config_views.js:12-18` (`doAction({tag:"pb_formula_studio", params:{open_wizard:1}})`)
  consumed at `formula_studio.js:575-579`.
- Picker ("Payroll configurations") = Config Switcher: markup `studio.xml:2946-3088`, styles
  `scss/cfgsw.scss`, methods `formula_studio.js:4059-4142` + board loader `:2027-2065`
  (`bureau_board`, `bureau_clone`, `csRemove`). Card template `studio.xml:3016-3069`.
  Cold start with no config → switcher auto-opens (`:610-616`).
- Arrival contract (`formula_studio.js:569-617`), each key read from `action.params` OR
  `action.context`: `open_wizard`, `config_id`, `open_settings`, `pbfs_open_people_mapping`,
  `pbfs_preview_payslip_id`, `pbfs_readonly`. `pb_back` chip via `HubBackChip` (`studio.xml:47`).
- Server: `wizard_templates()` (`pb_formula_studio.py:13330`) → built-ins `vn_standard`+`blank`
  (`_BUILTIN_TEMPLATES :13313`) + every `hr.formula.config.template` not superseded, each with
  `key,name,country,flag,version,effective_date,state,certified,builtin,desc,components[],rate_tables[],refs,preview`.
  `create_config` (`:13384`) — DO NOT USE (BP-R6). `_seed_template` (`:13402`), `apply_starter` (`:13451`).
  `bureau_board` (`:3430-3480`) card dict keys: `id,name,company,division,cycle_type,state,score,rule_count,
  problem_counts,problem_count,pending_changes,release_count,employees,code,country,currency,active,
  sample_count,is_branch,is_variant,is_master,can_delete,delete_blocked_by`.
- Studio action registration `formula_studio.js:5928`; `pb.formula.studio` is an **AbstractModel**
  (`pb_formula_studio.py:144`); `load(configId)` → `get_studio_data`.

### Configuration + rule models (pb_hr_payroll_formula)
- `hr.formula.config` (`formula_config.py`): `name :36`, `code :42` (required, auto via
  `_generate_unique_code :984` → `NAME_WITH_UNDERSCORES`), `cycle_type :62`
  (`regular|mid_cycle|end_cycle|full_final`), `country_code :104` (required; `VN|ID|IN|SG|MY|TH|KH|PH`),
  `currency_id` computed from country, `company_id :171` (required, default env.company),
  `rule_ids :186`, `rate_table_ids :194`, `sample_data_ids`, `state :486`
  (`draft|testing|validated|active|archived`), branch/variant fields `:208-257`.
  **No** `division`, `effective_from`, `legislation_pack_id`, cutoff/payday fields.
  `pb_division` exists only when `pb_demo` is installed (`pb_demo/models/demo_generator.py:37`).
  Transitions `:1033-1078`; `action_regenerate_formulas :1156-1204`; `action_validate_formulas :1207-1235`;
  `studio_people_mapping_action :1605-1632` (import return choke point); `PEOPLE_ROLES :1604`.
- `hr.formula.rule` (`formula_rule.py`): `config_id :49`, `salary_rule_id :57` (translatable label),
  `column_letter :76`, `name :93`, `code :99`, `column_type :120` (`input|formula|constant`),
  `excel_formula :457`, `constant_value`, `default_value`, `visibility_rule :617`, `appears_on_payslip :605`,
  `column_role :650` + `column_role_source :660`, `value_kind :686` + `value_kind_source :722`,
  `is_required :762`. Code regex: letters+digits, no underscore (`:1911-1923`); readable ≤12, ≥6 preferred.
  `python_formula` is a stored compute over `excel_formula` (`:916`); `_normalize_excel_formula :483`.
- Template registry `hr.formula.config.template` (`formula_config_template.py:56`): `code, name,
  country_code, flag, description, version, effective_date, state (draft|certified|superseded), components_json,
  rate_tables_json, sample_tests_json, legislation_refs_json`; `seed_config(config, pack_version=None) :213`
  (rate tables → rules with frozen letters → regen → sample tests `_seed_sample_tests :321`);
  raises if the B4 pack is unpublished (`:270-278`) or any formula fails conversion.
- VN pack `pb_pack_vn/data/config_template_vn.xml`: code `vn_standard_2026`, name "Vietnam Standard 2026",
  version 2026.1, effective 2026-01-01, state draft, 37 components (A..AK: inputs BASIC DEPS STDDAYS OTHRS15/20/30
  BONUS ALLOWIN; constants DEDUCTSELF 15.5m DEDUCTDEP 6.2m SIRATE HIRATE UIRATE SIEMPR HIEMPR UIEMPR CAPLO 46.8m CAPHI 99.2m
  MULT15/20/30; formulas HOURRATE OTPAY GROSS SIBASE UIBASE SIDED HIDED UIDED EEDED TAXABLE PIT `=BRACKET(VNTAX,AE1)`
  NET SICOMP HICOMP UICOMP ERCOST), rate table VNTAX **7 brackets** (5%…35%), 5+ sample tests
  (`pack_version 2026.1`, `tol 1.0`). ⚠ The prototype shows a **5-band 2026 schedule** (Law 109/2025) —
  a content question for B3/owner; the band editor must handle either.
- Rate tables `formula_rate_table.py`: `hr.formula.rate.table` (`code` letters/digits, unique per config),
  `.bracket` (`lower, rate`), `compile_brackets_excel :38-65`, `expand_brackets :132`,
  `_refresh_dependent_rules` on bracket create/write/unlink (`:180-218`).
- Samples/tests: `hr.formula.sample.data` (`formula_sample_data.py:17`; `input_values_json`,
  `expected_values_json :97`, `expected_confirmed` from `formula_boundary.py:94`), `hr.formula.test.result :733`.
  RPCs on `pb.formula.studio`: `compute_preview(config_id, sample_id) :2031` → `{sample_id, values{col: float}}`,
  `get_test_data :12094`, `get_sample_detail :12330`, `save_sample_inputs :12345`, `add_manual_sample :12366`,
  `generate_boundary_samples :12719`, `run_tests :11777`, `get_test_coverage :12245`,
  `confirm_sample_expected :12734`, `confirm_all_samples :12748`, `_sample_verdict :12073`.
- Studio formula save: `save_formula` (`:2426`), `bulk_save_formulas` (`:2330-2350`) with
  `formula_version_reason` context; `save_rate_table` (`:11558`); `_check_formula` (`:11636`); `delete_component` (`:11752`);
  `add_component(config_id, vals)` (`:11659`); `legislation_diff/apply` (`:3630/:3642`); `_legis_constant` (`:3466`).

### Mapping Studio + Payslip Studio doors
- Mapping Studio action tag `pb_mapping_studio` (`mapping_studio.js:2172`), xmlid
  `pb_formula_studio.action_pb_mapping_studio`. Arrival context: **`pb_config`** (not `pb_config_id`),
  `pb_mode` ∈ `journey|api|transform|import|employee|scheme|cycle|treatment` (`MODES :101-153`),
  `pb_connector`, `pb_endpoint`, `pb_back`. Invalid config id is silently swapped —
  `mapping_pickers` returns `defaults.fell_back` (`pb_formula_studio.py:5610-5640`).
  Round-trip precedent: `formula_studio.js:4694-4711` (`openMapping`). Guard every door with
  `registry.category("actions").contains("pb_mapping_studio")`.
- Mapping lanes for coverage: `hr.integration.field.mapping.target_rule_id` (API),
  `hr.payslip.import.mapping.salary_structure_id/component_id` (employee/contract/bank),
  `hr.payroll.cycle.component.mapping` (mid↔end). Pattern `pb_formula_studio.py:7104-7110`.
- Payslip Studio is an overlay INSIDE the Formula Studio cockpit (`state.psOpen`; `openPayslip`
  `formula_studio.js:4714-4724`; `payslip_studio_data(config_id, sample_id) :10461`; sections =
  `hr.payslip.config` bound by `salary_structure_id`; tray = unplaced). There is no arrival param
  for it yet — B4 adds `pbfs_open_payslip`.
- Import wizards: `hr.formula.multisheet.import.wizard` (7 states, `multisheet_import_wizard.py`),
  launched with `{default_config_id, pbfs_studio_import: true}` (`formula_studio.js:5811-5817`);
  terminal chain `:3092-3111` → `studio_people_mapping_action` → `category_review_action(next_action)`.

### Design-system + kit
- Studio tokens `.pbfs { --i --i600 --i-deep --i-soft --i-soft2 --i-border --ink --muted --line --bg }`
  (`studio.scss:1-6`); kit tokens `pb_import_kit/static/src/scss/import_tokens.scss`
  (`pbim-root-vars` mixin), primitives `import_kit.scss` (`pbim-rail/-step/-dot`, `pbim-card`, `pbim-btn`,
  `pbim-chip`, `pbim-badge`, `pbim-seg`, `pbim-busy`, `pbim-empty`, `pbim-note`, `pbim-eyebrow`, `pbim-h1/h2/sub`),
  `modal.scss` (`.pbim-modal-scrim/.pbim-modal`). Root class `pbim pbim-page pbbp`.
- Hub back chip: `openHub(actionService, {tag|xmlid, back:{label, xmlid|tag, context}})` and
  `hubBack(props)` + `<HubBackChip back="…" tone="light"/>` (`pb_hub/static/src/js/hub_nav.js:52-150`).
- Breadcrumb name for a control-panel-less client action: `this.env.config.setDisplayName(_t("…"))`
  in `setup()` (GR8).
- Hoot tests import pure helpers: `pb_payrun_wizard/static/tests/payrun_mode.test.js`. Python
  source-assertion tests: `pb_formula_studio/tests/test_one_mapping_home.py`.
- Translations: `i18n/vi_VN.po` (never `vi.po`); every entry needs `#. module: pb_blueprint` (GR5);
  tooling `tools/refresh_pb_vi.py`.

## Deploy ritual
Exactly the WFPLAN/GROUP ritual: clean stage `/tmp/bp_stage` (`sudo rm -rf` then `mkdir -p`),
`rsync -az --exclude=__pycache__ --exclude='*.pyc' <modules> Payobook19v2:/tmp/bp_stage/`,
per module `sudo rsync -a --delete --chown=odoo:odoo /tmp/bp_stage/<m>/ /odoo/odoo-server/addons/<m>/`,
tests on p9clone (`--test-enable --test-tags /pb_blueprint --http-port=8199 --gevent-port=8198`),
`pg_dump` per DB, detached `systemd-run` install/upgrade per DB (`-i pb_blueprint` first time,
`-u pb_blueprint,pb_formula_studio` after) with a sentinel + `EXIT=`, service start, asset purge
`DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` + bump `web.assets.version` param per DB,
manifest-vs-`ir_module_module.latest_version` and tree-hash verification on every DB,
never `pkill -f odoo-bin`, then Chrome-MCP walkthrough on payobook and abm.

## Gotcha ledger (append below; BP-numbers)

- BP1 (design): the arrival key is **`pb_config`**, not `pb_config_id` (`pb_source_atlas/static/src/js/atlas.js:173`).
- BP2 (design): `import { ic } from "@pb_import_kit/js/import_icons"` — the `js/` segment is mandatory
  (W17.4); expose as a method and render with `t-out`.
- BP3 (design): `save_rate_table` unlinks and recreates brackets — bracket ids change on every save;
  never hold them client-side.
- BP4 (design): `create_config` ignores `company_id` and hard-codes `'VN'` defaults; `seed_config`
  raises on an unpublished B4 pack — wrap draft creation in one savepoint and surface the reason.
- BP5 (design): Sass evaluates its own `min()/max()` — mixed `px`+`%` units break the WHOLE backend
  bundle at page load, not at upgrade. Chrome-load a page after every SCSS deploy.
- BP6 (design): a `.po` entry without `#. module:` takes the database down on install (GR5).
- BP7 (design): the picker's Division facet reads `pb_division` which only exists with `pb_demo`;
  `getattr` guards it — copy that guard if you read it.
- BP8 (design): `hr.formula.rule` has no `active`; "excluded" components do not exist as rows (BP-R7).
- BP9 (B1, cost 1 build): **an XML comment may not contain `--`.** The house style
  `<!-- ---------- section ---------- -->` makes a QWeb template file NOT WELL-FORMED, and the
  failure is silent at deploy time — the bundle simply has no templates from that file and every
  component using them dies at mount with "Missing template". Use `<!-- ========== section ========== -->`.
  `python3 -c "import xml.dom.minidom; xml.dom.minidom.parse('f.xml')"` on every template before deploy.
- BP10 (B1): W23 restated, because it bites hardest on a whole-page state machine: **a comment
  between `t-if` / `t-elif` / `t-else` siblings breaks the chain at runtime.** The loading, refusal
  and journey states painted at once. Keep the three siblings adjacent and put the explanation
  ABOVE the first one.
- BP11 (B1): **`pbim-page` is the wrong root class for a full-bleed cockpit.** It carries 26px of
  padding, `overflow:auto`, and two `body:has(.lrn-coachhost) .pbim.pbim-page { padding-bottom: 236px }`
  rules in `import_kit.scss` that another module cannot reliably out-specify (equal specificity,
  load order decides). Use `pbim <prefix>` — the tokens live on `.pbim`, which is the half you want —
  and lay the shell out yourself.
- BP12 (B1): **the kit's tokens are a MIXIN, not a stylesheet.** Never `@import`
  `pb_import_kit/.../import_tokens` by relative path from another module. Either
  `@include pbim-root-vars;` on your root or, when your root already carries `.pbim`, just read
  `var(--pbim-*, literal)` (the `pb_insights` / `pb_lifecycle` convention).
- BP13 (B1): **`env.company` is NOT guaranteed to be a member of `env.companies`.** A user's
  `company_id` can point at a company absent from their `company_ids` — on p9clone user 1's current
  company "Your Company" is missing from their allowed list, which failed 6 of 22 tests. Any guard
  written `company.id not in self.env.companies.ids` locks a user out of the company they are
  standing in. Always `set(env.companies.ids) | {env.company.id}`.
- BP14 (B1): **`router.pushState({config_id})` only survives a refresh when the client action was
  opened BY TAG.** `makeState` writes `action.path || action.id` when either exists and falls back to
  `action.tag` only for a bare client action; `_getActionParams` then hands `params: state` back only
  when `actionRegistry.contains(state.action)`. Opened by xmlid the URL is `/odoo/action-<id>` and the
  extra params are dropped. So every door into the journey uses
  `doAction({type:"ir.actions.client", tag:"pb_blueprint", params:{…}})`, never the xmlid.
  (`web/static/src/webclient/actions/action_service.js:505-560, 1798-1820`.)
- BP15 (B1): a white-label / vocabulary gate must read **string literals and template text only**.
  A whole-file regex flags `blueprint="state.blueprint"` — a prop name — and a gate that cries wolf
  on identifiers is a gate somebody deletes. Exclude docstrings and `_logger.*` arguments: engineers
  read those and the white-label rule exempts them.
- BP16 (B1): **`hr.formula.rule.net_role` is empty until somebody calls `classify_net_roles()`** —
  it has no default and no `@api.depends` by design (a formula edit must not silently re-decide a
  category a person accepted), and the VN pack does not ship it. `bp_start` calls the classifier
  once, non-fatally, right after seeding, so the pay panel can label its lines on a configuration
  whose codes are not the usual ones.
- BP17 (B1): `pb_import_kit` had no `wallet` or `fileSpreadsheet` glyph. Added to the ONE registry
  (`import_icons.js`, version → 19.0.1.18.0) per W2 — which means **pb_import_kit ships with any
  phase that adds an icon**, and its version must be bumped or `-u` runs nothing.
- BP18 (B2, cost 2 builds): **a reused CSS class name is not a specificity fight — it is two
  things wearing one name.** The sentence editor styled its inline choices `.pbbp-pill`, which B1
  already owns for the pay panel's status badge (`inline-flex`, `text-transform: uppercase`). The
  sentence rendered as a stack of full-width boxes shouting in capitals, and no amount of
  `select.pbbp-pill` out-specified it reliably. Renamed `.pbbp-word`. Grep the module's own SCSS
  for a class name before minting it.
- BP19 (B2): **the backend theme styles every bare `select` and `input`** — `display: block;
  width: 100%` plus `text-transform` — so any inline control inside a sentence has to name the
  ELEMENT in its selector (`select.pbbp-word`) to win without `!important`. The kit's `.pbim-badge`
  is `text-transform: capitalize`, which is right for a status word and wrong for a sentence
  fragment ("Tax Free", "Written As Excel").
- BP20 (B2, a real bug in front of a user): **the journey shell listens for Enter on the whole
  page and treats it as "continue".** Any inner surface with its own Enter must
  `stopPropagation()`, or opening a component also walks the person to the next step. Same for
  Escape: a hand-built `.pbim-modal` is not a framework Dialog, so nothing claims focus and the
  hotkey service has no surface to route to — take focus on mount (`tabindex="-1"` + `.focus()`)
  and handle the keys on the element as well.
- BP21 (B2): **`regenerate` must pass `bp_formula_source` explicitly.** The rule's own `write()`
  guard flips anything writing a formula other than `bp_generated_formula` to `manual`, and on the
  FIRST pass `bp_generated_formula` is still empty — so regeneration silently marked its own
  output as somebody's hand-written Excel and then refused to touch it ever again. Symptom: the
  backfill appeared to do nothing, every total kept its pack formula, and removing a component was
  refused with "used by GROSS, NET, TAXABLE, which is written as Excel".
- BP22 (B2): **a helper rule needs a `helper` group of its own.** `<CODE>TX` (the taxable slice of
  a conditionally-exempt payment) is a formula column with no recipe, so `derived_group` classified
  it as an earning and summed it into the very total it exists to feed. Anything the guided setup
  creates for its own plumbing carries `bp_template_key='helper'`, and `derived_group` reads that
  before it guesses.
- BP23 (B2): **the value beside a row has to follow the sample employee.** The list is loaded once
  and the pay panel refreshes on its own, so editing a sample input moved the take-home figure
  while the row that caused it still read 0. A number that is quietly wrong is worse than no
  number — pass a tick that changes whenever the panel gets a fresh answer.
- BP24 (B2): **`_normalize_excel_formula` keeps the leading `=`.** It strips row numbers only
  (`=Y1*K1` -> `=Y*K`). Two tests were written against `Y*K`.
- BP25 (B2): **a deleted record raises on every field access.** Read `column_letter` (or anything
  else you will assert on) BEFORE the unlink, not after.
- BP26 (B2): Python's implicit string concatenation across lines is a **syntax error in
  JavaScript**, and it takes the WHOLE backend bundle down with "Uncaught SyntaxError: missing )
  after argument list" — a blank page, not a broken component. `node --check` every `.js` file in
  the module before deploying; it costs a second and catches this class entirely.
- BP27 (B2): the Vietnam pack's first certification sample is **"Zero income"**, so
  `sample_data_ids[0]` is a column of zeroes and any "did the number change" assertion written
  against it passes for the wrong reason. Pick the sample that is actually paid (B1 hit the same
  edge in the pay panel; it bites in tests too).
- BP28 (B2): **a hoot test that reads a `_t()` label throws** — "Cannot translate string:
  translations have not been loaded" — because a unit test has no server to fetch them from, and
  `_t()` returns a lazy object whose `valueOf` refuses until they are. Six of ten tests failed on
  it. Fix, which is Odoo's own (`web/static/tests/core/l10n/translation.test.js:447`):
  ```js
  import { translatedTerms, translationLoaded } from "@web/core/l10n/translation";
  beforeEach(() => { translatedTerms[translationLoaded] = true; });
  ```
  English is the source language, so "loaded with nothing" is exactly right: every term falls
  through to its own source string. Run the suite at `/web/tests?filter=<suite name>` — the tab
  title carries ✔ or ✖, and a green Python run says nothing about the JavaScript.
- BP29 (B3, cost 2 rebuilds): **a starter cannot ship the helper inputs its own sentences need.**
  `hr.formula.config.template._check_converter_contract` refuses any code that CONTAINS another
  (`formula_config_template.py:199-208`), so `OTWDHRS` beside `OTWD` is a ValidationError at
  authoring time — and `TAXGROSS` is refused because `GROSS` is inside it. Two consequences that
  shape the whole Complete template: (a) a recipe may now NAME the input it reads
  (`inputs: {hours: 'HRSWD', enrol: 'ENROLPREM', amount: 'PRIVINSAMT', run: 'PAIDVAR'}`), falling
  back to the `<CODE><SUFFIX>` convention on a live configuration where the registry never looks;
  (b) a component whose amount is simply "an approved amount" ships as `type: input` rather than a
  formula, because an input-shaped formula would need a `<CODE>IN` companion the template may not
  carry. Run the substring check in the generator, where the message is useful.
- BP30 (B3): **`<data noupdate="1">` means a data file's second version never reaches an upgraded
  database.** The record is created if its xmlid is missing and otherwise left alone, so editing
  the template and running `-u` appears to do nothing — every number stays as first loaded. Right
  for a shipped starter (a new version is a new record with `supersedes_id`), fatal for iteration:
  during development delete the `ir.model.data` row AND the record, then upgrade.
- BP31 (B3, a real bug in somebody's tax): **"taxed the same way as the original" is about the
  TREATMENT, never the amount.** B2's `taxable_helper_formula` returned the SOURCE COMPONENT'S
  VALUE as this component's taxable part, so a correction to last month's salary would have added
  the whole of this month's salary to taxable income a second time. It now returns `=0` when the
  original is exempt and no helper at all when it is taxable.
- BP32 (B3): **a payment "the scheme decides" that is worked out from a salary is paid EVERY run.**
  `frequency: 'scheme'` gated nothing, so a variable bonus of 10% of salary was paid every month
  for ever — found because the Complete starter's first persona came out 3,000,000 too high. A
  recipe that names its `run` switch waits to be told; one that does not behaves exactly as before.
- BP33 (B3): **a benefit MIRROR is counted twice by the employer-cost total.** `PREMINSALW` is the
  taxable value to the employee of the dependants' cover the employer already pays as
  `PRIVHLTHDEP`; `employer_total` summed both. Totals now honour `of.exclude`.
- BP34 (B3): **a screen is only as clean as the data it renders.** The white-label gate reads our
  own files, and the Vietnam rule pack's `description` — "Serves both existing-config rollout (B4)
  and new-config template seeding (F113)" — reached a payroll manager through the pack popover
  because it came from `pb_pack_vn`, not from us. Scan RPC PAYLOADS, not just source files, and
  never render another module's free text without reading it first.
- BP35 (B3): **`_clamp` is for reading a stored preference, never for saving one.** Pulling a
  person's cut-off day of 31 silently back to 28 changes what they asked for without telling them.
  Two functions, two jobs: `_clamp` for display, `_whole` (range or None) for a write.
- BP36 (B3, unresolved): **four hoot tests in `blueprint_steps.test.js` still throw "translations
  have not been loaded"** when they stringify a `_t()` label from `blueprint_steps.js`'s own
  module scope, even with BP28's flag set at import time, in a root `beforeEach`, AND in a
  `beforeEach` inside every `describe`. The identical guard works for `recipe_text.test.js` and for
  B3's `tax_math.test.js` (16/16 green). Pre-existing since B1; diagnosed, not fixed. B4 should
  either mock the translation service or assert on the keys rather than the words.
- BP37 (B4, closes BP36): **the four hoot failures were a stale bundle, not a broken
  guard.** BP28's fix is correct and always was: `beforeEach` at a test file's top level
  registers on hoot's GLOBAL callback registry (`web/static/lib/hoot/core/runner.js:725-734`
  — no current suite means `this._callbacks`), so it runs before every test in the session,
  and the runner's order is `fifo` by default (`hoot/core/config.js:171`), so a run is
  deterministic rather than a lottery. All four are green on a freshly built
  `web.assets_unit_tests`, twice, in two tabs. **A hoot result is only as fresh as the
  bundle THAT TAB loaded** — reload with a new URL (and after an asset purge) before
  believing a red, and never carry a red forward from a tab that has been open since
  before the deploy. The way to make the whole class impossible: **build every `_t()`
  inside a function.** A label created at module scope is a lazy `TranslatedString` whose
  `valueOf()` can refuse; one created at call time, with the flag set, is an ordinary
  string. `connect_text.js` is written that way throughout and nothing in its 22 tests
  can ever hit the lazy path.
- BP38 (B4, a real bug in front of a user): **`router.pushState` called from `onWillStart`
  is overwritten a moment later, at mount, by the action manager's own route state.** It
  survives only for a door that carries its payload in `action.params` — which the picker's
  Resume button does and no *return* door does, because `openHub`/`pb_back` travel in the
  CONTEXT. Symptom: come back from the Mapping Studio or the payslip designer, press
  refresh, and land on an empty journey having lost the draft. Re-assert the URL in
  `onMounted` as well; one call, and every door's refresh then behaves the same.
- BP39 (B4): **a status hint must be a function of the same numbers the card shows, not of
  the status alone.** "You opened it, and nothing is connected yet" sat directly under a
  coverage line reading "1 of 52 inputs has a source" — at exactly the moment somebody is
  looking for confirmation that their work landed. Two things derived from one server
  answer must be derived from ALL of it.
- BP40 (B4, a walkthrough method): **"needs another look" can only be proven by changing
  something that was in the snapshot.** Placing a component AFTER pressing "Mark as done"
  and then removing it proves nothing — it was never part of what was agreed. The order is
  always: make the change, mark it done, THEN break it. Half an hour was spent reading a
  correct "Done" as a failure.
- BP41 (B5, cost the whole Test step until it was found): **a child that sets state on
  its parent from `onWillStart` is an infinite render loop, and Owl reports NOTHING.**
  `StepTest` handed its answer to the shell so the pay panel could become the scoreboard;
  the shell's state changed, which re-rendered the shell, which rebuilt the child, which
  asked again. The symptom is not an error — it is a step that never appears: the rail
  keeps its old highlight, the previous step stays painted, `state.step` IS the new step,
  and the console is silent, because Owl cancels the render and reverts. It was diagnosed
  by patching the component's `setup` and counting how many times it ran (30+ in 2.5 s).
  **Rule: nothing may reach the parent before `onMounted`.** Guard with a `_live` flag set
  there, and hand the first answer over from the same hook. A plain number is safe — Owl's
  reactivity does not notify when a set does not change the value — which is why
  `onRevision(res.revision)` has always been fine and a fresh object never is.
- BP42 (B5, a real bug in front of a user, and older than this phase): **`action_run_tests`
  starts by deleting the previous results, and no group could delete them.**
  `access_test_result_manager` shipped `1,1,1,0`, so the FIRST run of the checks worked (an
  empty set deletes fine) and every run after it failed with the framework's own refusal —
  "You are not allowed to delete 'Formula Test Result' … No group currently allows this
  operation" — for every user who is not a superuser. It affects the studio's own Test
  workbench too, and it has been true since that model shipped. Fixed by giving the formula
  manager `perm_unlink` in `pb_hr_payroll_formula/security/ir.model.access.csv`
  (19.0.1.125.0). **An ACL row that permits create and write but not unlink is a bug
  whenever the code's own first act is to clear what it wrote last time.**
- BP43 (B5): **a screen may not be confident about something it has not checked.** Three
  variants of the same mistake, all found in the browser: a scoreboard reading "5 / 5
  passed" beside a chip saying "Not checked yet"; the same score still reading green after
  a tax band moved; and a chip reporting the STORED counters from the last run while the
  list beside it showed six scenarios added since. The rule that fixes all three: the
  number and the words about the number must be computed from ONE answer, and where they
  cannot be (a stored stamp versus a live list) the payload overrides the stored half
  before it reaches the screen. Before a run there is no score at all — an em dash and
  "not checked yet" — and while stale the word is "passed — before the change".
- BP44 (B5): **the studio's step-by-step replay finds only SPREADSHEET references.**
  `replay_trace` collects what a formula read with `([A-Za-z]+)\d+` — `A1`, `Y1` — and every
  formula the guided setup writes is stored WITHOUT row numbers (`=A+H`, the shape
  `_normalize_excel_formula` produces). So the replay returns the right ANSWER for a
  generated rule and an empty list of reads, and the trace line read "→ 2,400,000" with
  nothing before the arrow. Fall back to the dependency edges (the same list "Feeds from"
  shows) when the replay's own list is empty; never "fix" it by writing row numbers back
  into the stored formula.
- BP45 (B5): **five columns whose minimum widths add up to more than the container is a
  button nobody can press.** At 1440 the journey's content column is 735 px; the outputs
  table's first draft asked for 878, and `overflow-x: hidden` on the body quietly clipped
  the Inspect column off the right-hand edge. Measure the container (`clientWidth`) against
  the row (`scrollWidth`) in the browser rather than trusting a `minmax()` that looks
  reasonable in the file.
- BP46 (B5): **a sentence built from a label is a sentence in the wrong grammar.**
  "Nothing in this configuration is a %s yet" reads correctly for exactly none of the nine
  filter chips ("is a edited by hand yet"). Quote the chip's own words instead — "Nothing
  here matches “Edited by hand”" — and check the empty state of a configuration with
  nothing in it separately, because "no component matches this filter" is the wrong answer
  to somebody who has not added one yet.
- BP47 (B6, and it invalidates the guard BP26 asked for): **`node --check
  file.js` PASSES a file whose module syntax is broken.** Node 24 parses an
  ambiguous `.js` as CommonJS, fails, retries as ESM, and reports success — so
  two files in this phase carrying `_t("a "\n   "b")` (Python's implicit
  concatenation, JavaScript's syntax error, and a BLANK BACKEND rather than a
  broken component) were pronounced fine by the very check B2 introduced to
  catch that class. The same bytes in a `.mjs` file are refused immediately.
  **Copy each `.js` to `<name>.mjs` and check THAT**, and keep a source scan as
  well (`test_i18n.py::test_no_javascript_string_is_split_across_two_lines`),
  because a check that depends on which extension somebody used is not a guard.
  The concatenation is also invisible to the translation extractor, which sees
  only the first half of the string — so it fails twice.
- BP48 (B6): **`tools/refresh_pb_vi.py` STRIPS edge whitespace from a msgid it
  extracts from source** (`:406`), so `_t(" and ")` is stored as `and`, never
  matches at runtime, and the screen keeps the English word with nothing
  reporting it. Four entries across two modules this phase. Fixed after the
  fact by `pb_blueprint/tools/vi_polish.py`, which restores every msgid the POT
  holds and re-pads the translation; the shared tool is left alone because
  forty modules' catalogues were built with its behaviour.
- BP49 (B6): **a translatable FIELD can be a JSON document.** The Vietnam ·
  Complete starter's `components_json` is 54,000 characters and the POT export
  offers it as a string to translate; a machine-translated copy of it would be
  a corrupted starter. Anything over ~1,500 characters is dropped from the
  catalogue (`vi_polish.py`), and the empty msgstr it would otherwise carry is
  not a safe answer either — the entry must go.
- BP50 (B6, closes B2 §11.4, B3 §12.5, B4 §11.6 and B5 §11.7): **the browser
  bridge CAN reach 390 px — with the right tool.** `resize_page` is floored at
  ~500 px by the window, but `emulate` with a device viewport
  (`390x844x3,mobile,touch`) sets the page's own viewport and reports
  `innerWidth === 390`. Four phases said a device-accurate phone capture was
  impossible; it was the wrong call, and the header's three-row wrap at 390 was
  found within a minute of using it.
- BP51 (B6, BP19's third sighting): **the kit's `.pbim-badge` is
  `text-transform: capitalize`.** It rendered the count chip as "8 Open". The
  fix is never a specificity fight — it is a class of your own
  (`.pbbp-fin-open`) for anything that is a phrase rather than a status word.
- BP52 (B6, the same shape as BP10): **a new `t-if` between the branches of a
  `t-if`/`t-elif`/`t-else` chain does not join the chain — it starts a second
  one, and the `t-else` after it then belongs to the NEW chain.** Adding a
  "was 500,000" span before the value span made the proof strip render its
  number while the calculation was still being worked out. Wrap the branch in a
  `<t t-else="">` and put the new element INSIDE it.
- BP53 (B6, a real bug in front of a user, caught in review): **a read RPC that
  re-validates is a write.** `bp_finish_data` calls `action_validate_formulas`
  so the gate answers about today's rules, and `is_valid` is a stored field —
  which means a person who may only LOOK at payroll setup got the framework's
  own access refusal instead of the Finish page. A re-check that cannot be
  written falls back to what was last stored; the gate is enforced again inside
  `bp_finish`, where writing is the point.
- BP54 (B6, and it is the biggest of this phase): **a translation entry is only
  visible to the half of the product whose EXTRACTOR COMMENT it carries.**
  `odoo/tools/translate.py:1856` builds the Python code translations by keeping
  only entries whose comments contain `odoo-python`; the web loader keeps
  `odoo-javascript` (`:1863`). A string the screen says in JavaScript AND the
  server says in Python is ONE entry in the catalogue, and the exporter writes
  whichever comment it saw first — so "Regular payroll" came back Vietnamese on
  the client and English from the server, in the same sentence, with a perfectly
  valid `.po` and nothing in any log. **97 entries in `pb_blueprint` and 38 in
  `pb_formula_studio` were in that state.** `pb_blueprint/tools/vi_polish.py`
  now scans `models/`, `wizards/` and `static/src/js/` for `_()`/`_t()`
  literals and marks each entry for both halves. Two corollaries: a
  module-level dict of plain strings (`CYCLE_LABELS = {'regular': "Regular
  payroll"}`) can never be translated at all — B2's `helper_label` rule applies
  to every label a server payload carries, not only to lazy `_t()`; and a
  screen that reads correctly in one language is not evidence, because the
  English fallback IS the source string and looks like a deliberate choice.
