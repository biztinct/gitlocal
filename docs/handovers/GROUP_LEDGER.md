# GROUP Programme Ledger — one group, every payroll, one truth

Every GROUP phase handover references this file. Read it FULLY before coding. Append
(never rewrite history) when you hit a new gotcha — that is part of every phase deliverable.

Programme: make Payobook world class for a group with many companies, countries,
currencies, divisions and payroll schemes. Owner-facing design:
`docs/design/group-blueprint.html` (the blueprint; Parts A–H) built on the verified
findings in `docs/design/one-group-many-payrolls.html`. Owner asked for this on
2026-09-07 and chose the phased model (Fable designs, Opus builds + tests + deploys,
phases back to back, only destructive actions or genuine scope decisions stop the run).

The seven phases (Part H of the blueprint):
P1 The group · P2 Who is paid by what · P3 Numbers that remember · P4 Planning with
scope · P5 People in two places · P6 Pay Review / Pay Bands / Merit Matrix + retire
legacy · P7 Visibility, Vietnamese, closeout.

Sibling ledgers you must also honour: `docs/handovers/WFPLAN_LEDGER.md` (Decision
Room, gotchas WF1–WF29, deploy ritual, credentials), `docs/handovers/RIZE_LEDGER.md`
(platform contract for new modules, Odoo 19 gotchas R-series).

## Target & credentials

- Master DB `payobook` at https://payobook.com. Admin `ash@biztinct.com` /
  `{withheld: rize-admin}`. Demo company **Payobook Vietnam JSC** (id 5, VN, VND): 4,533
  people, 40 departments (9 top-level), 42 jobs, 15 active schemes. Company 6
  **Payobook Singapore Pte Ltd** (SG, SGD) exists with 0 employees — use it as the
  second-currency member of the demo group. Companies 1 (USD), 2 (VND), 7 (SGD) also
  exist; NO company has `parent_id` set.
- Tenant `abm` (AB Mauri, company 1, VND, 153 people, 1 scheme). The ledger login for
  abm is WRONG (WFPLAN WF15); use the archived validators recorded under WF15's P2/P3
  addenda (reactivate via `odoo-bin shell`, archive again after).
- `p9clone` = rehearsal + tests. `payobook_template` = golden template, must get every
  module. Order: p9clone → payobook → abm → payobook_template, `pg_dump` before each.
- ssh alias `Payobook19v2`; `/odoo/odoo-server/addons` needs `sudo` to list; Odoo core
  lives at `/odoo/odoo-server/odoo/addons/base` (NOT vendored in the repo).

## Binding rules (violations = phase failure)

1. **White-label**: never "Odoo" in any user-visible string or `.po` msgstr.
2. **Plain English** on every label, toast, empty state, sentence. Screen words, not
   code words ("payroll scheme", "kind of run", "group currency", "division").
3. **ONE addons dir**; never `rsync --delete` into `/odoo/odoo-server/addons/` itself;
   never deploy vendored standard addons.
4. **Commit per feature**, explicit paths, `Co-Authored-By: Claude Opus 5
   <noreply@anthropic.com>`, never push. Unrelated dirty files exist in the tree.
5. **Design system**: Lucide via the single `ic()` registry
   (`pb_import_kit/static/src/js/import_icons.js`, add there); no emoji/glyphs; no
   gradients; `.pbim-*` kit, root class `pbim pbim-page <prefix>`; Payobook palette
   (primary `#5A4BB0`, dark `#241F52`, soft `#EDEAF8`, canvas `#F4F5FB`, ink `#1E1B2E`,
   good `#2E7D4F`, rose `#DC2668`, warn `#D97706`, teal `#0F766E`).
6. **Design bar (verbatim, score against it in every report): "extreme WOW, intuitive,
   out-of-this-world experience, best in class."** Hero moment named; zero dead-ends;
   plain language; motion with purpose; keyboard + bulk ergonomics; Chrome-MCP validate
   light/dark, 1440/390, every flow clicked.
7. **Never store a converted amount.** Conversion happens at read time through `pb.fx`,
   returns `(value, known, meta)`, and a missing rate is shown, never guessed.
8. **Payroll safety**: a company with exactly one active scheme and no map entries must
   produce the IDENTICAL pay-run population before and after P2 (test-enforced).
   Nothing in P1–P4 writes to `hr.payslip`, `hr.contract` or `hr.employee` pay data.
9. **Tenant parity**: tenants get every module the master gets. `pb_group` and every
   GROUP module are tenant-safe (a tenant is one group). Nothing GROUP builds goes into
   `pb_tenants` sync-never lists.
10. **Rehearse on p9clone, run the tests there**, then production. Chrome-validate on
    payobook AND abm.

## Rulings (Fable, 2026-09-07 — binding unless the owner overrules)

- **G1 The group is its own record, not Odoo's branch tree.** Odoo 19
  `res.company._get_company_root_delegated_field_names()` returns `['currency_id']`:
  a child company (branch) copies the root's currency and shows it read-only
  (`/odoo/odoo-server/odoo/addons/base/models/res_company.py:98-106, 184-189, 300-305`).
  A VND parent with an SGD child is therefore impossible via `parent_id`. `pb.group`
  holds the members via `res.company.pb_group_id`. Odoo's `parent_id` stays untouched.
- **G2 Divisions are group-level records** (`pb.division`), attached to departments
  through effective-dated links; a department belongs to at most one division on a date.
- **G3 `pb.fx` is the only conversion service.** `pb.budget.fx` becomes a thin shim
  over it (same public API) so pb_budget's callers and tests keep working.
- **G4 Rate policy** lives on the group: `month_end` (rate row dated ≤ last day of the
  month, latest wins), `payment_date` (rate ≤ the run's end date), `month_avg` (mean of
  the month's rate rows; none → unknown). Rate rows are searched with
  `company_id in (False, member companies, group companies)` — never
  `self.env.company` alone (the bug in `budget_fx._has_rate`).
- **G5 Single-scheme companies never notice P2.** The resolution ladder falls to "the
  company's only active scheme" before it reaches "nobody".
- **G6 Kind of run** = `hr.formula.config.cycle_type` (regular / mid_cycle / end_cycle /
  full_final). Reports default to non-advance runs; headcount = distinct persons.
- **G7 Component tagging (`wfp_category`) is retired** in favour of the engine's own
  `value_kind` / `net_role` classification (VALUEKIND programme).
- **G8 Split-month pay pattern is configurable** (owner, 2026-09-07): a group setting
  `split_pay_policy` = `each_pays` (each entity pays its own days) | `home_pays` (home
  entity pays, host is charged), with a per-work-segment override. Home = the entity of
  the person's standing employment. The charge is an internal cost line
  (`pb.cost.transfer`) shown in reports and exportable; no accounting posting (owner's
  earlier ruling: no accounting connection).
- **G9 Part G is rebuilt from first principles, not ported** (owner, 2026-09-07: the old
  screens are unused; design what a world-class tool would do). The area is **Pay** with
  four surfaces: Pay Review (guidance pre-filled from a grid, worksheet, calibration
  scatter, live fairness, self-explaining limits, manager→HR→finance→CEO cascade on
  `biz.approval.chain.mixin`, apply with 24 h undo, letters via `pb.letter.template` /
  `pb.hr.letter`, portal "Your pay, explained"), Pay Bands (band picture with people
  dots, health cards, place-a-new-hire, import), Fairness (gap by gender/level/division,
  same-job spread, computed from facts + contracts, live inside reviews), Pay changes
  (one-off promotion/correction through the same guidance, limits, approvals, letter).
  Merit matrix = the guidance grid inside review settings; component tagging is gone.
  Legacy data migrates (grades→bands, matrices→grids, cycles→read-only history,
  contract compa recomputed), pb_budget re-homed, then `pb_hr_workforce_planning` is
  uninstalled. Benchmark: Lattice, Pave, Carta, Workday; our edge = payroll-native apply.

## Plumbing facts (verified 2026-09-07 — do not re-derive)

### Currency today
- `pb_budget/models/budget_fx.py:48-160` `pb.budget.fx`: `presentation_currency(company)`
  :54 (probes `presentation_currency_id` on the root via a 10-hop `parent_id` walk),
  `_has_rate(currency, day)` :80 (**hard-codes `self.env.company`**), `rate_known(src,
  dst, date)` :107 (refuses implicit 1.0), `convert(amount, src, dst, date, manual_rate)`
  :131 → `(float, bool)`, `unknown_rate_note` :150. Callers: `pb_budget/models/pb_budget.py:167-168, 293, 423`,
  `budget_ext.py:210-215` (injectable `fx=`), `budget_actuals.py:373, 398`,
  `tests/test_budget.py:237`.
- `res.company.presentation_currency_id` is defined in **pb_demo**
  (`pb_demo/models/res_company.py:16-20`, no view), set by
  `pb_demo/models/demo_generator.py:172-173`; `convert_to_presentation` :31-38 silently
  returns the raw amount when no rate (a lie — do not copy).
- No `_convert()` / `currency_id.rate` use in pb_explorer, pb_insights,
  pb_payrun_results, pb_payruns, pb_govt_reports, pb_decision_room,
  pb_hr_payroll_analytics, payroll_analytics_approval. `hr.payslip` has no
  `currency_id` field (rounding uses `contract.company_id.currency_id`).
  `hr.formula.config.currency_id` is computed from `country_code` only.

### Schemes and the employee link
- `hr.formula.config` (`pb_hr_payroll_formula/models/formula_config.py`): company-scoped
  (`company_id` :171 required; record rules `security/formula_security.xml:60-64` allow
  `company_id = False` as shared), `code` unique per company (:979), required
  `country_code` :104, `cycle_type` :62-67, `pb_division` Char exists only when pb_demo
  is installed (`pb_demo/models/demo_generator.py:37`).
- **No `formula_config_id` on `hr.employee` / `hr.contract` / `hr.version`.** Operative
  field: `hr.payslip.formula_config_id` (`hr_payslip_formula.py:32`), resolved by
  `_find_formula_config()` :302 down five rungs (sibling slip in run :329 → import batch
  :338 → unique structure :345 → employee nationality :361 → first active config :370).
- `hr.formula.scheme.assignment` (`pb_hr_payroll_formula/models/formula_scheme_assignment.py`,
  46 lines): `config_id` (required), `department_id` (optional), `domain` (Char),
  `sequence`, `active`; constraint `unique(department_id, config_id)`; helpers
  `_employee_domain()` :36, `employee_count()` :45. ACL: formula user + manager full.
  Written/read ONLY by the Formula Studio canvas:
  `pb_formula_studio/models/pb_formula_studio.py:8403 scheme_mapping_data` (departments
  with ≥1 employee, unscoped by company; configs `state='active'` and
  `cycle_type != 'mid_cycle'`), `:8455 scheme_mapping_create` (deletes other
  assignments for the department first), `:8471 scheme_mapping_delete`; JS
  `pb_formula_studio/static/src/js/mapping/mapping_studio.js:769` (generic two-column
  wire canvas, mode `"scheme"`).
- Pay run population: `pb_payrun_wizard/models/pb_payrun_wizard.py:47 _eligible_employees`
  = every open `hr.contract` (record rule → `company_ids`, the whole switcher), narrowed
  by feed statuses and an explicit shortlist only. `get_defaults` :25 offers no scheme
  or department picker; `vals['division']` is carried into `compute_batch` :~420 but
  only pb_demo populates it (`pb_demo/models/demo_payrun.py:139-168`, filters
  `[('division','=',key),('is_demo','=',True)]`). Slips are created with
  `company_id: emp.company_id.id` but no `formula_config_id`.
- `hr.employee.division` (Char, `pb_hr_payroll_formula/models/hr_employee.py:8`) is
  filled on 4,502 of 4,533 on company 5 (manufacturing 1000, retail 902, construction
  800, logistics 700, it 600, corporate 500).
- Demo shape: 6 divisions × (End-Month + Mid-Month) schemes; a top-level department per
  division; 12,621 employee-months sit on two schemes (advance + main).

### Departments and rosters
- `hr.department`: `company_id` (indexed, default env.company), `parent_id` (indexed,
  **`check_company=True`** — a department cannot parent across companies),
  `child_ids`, `complete_name` (recursive, `_rec_name`), `parent_path` (indexed).
  `pb_budget/models/hr_department_ext.py:27` overrides `write()` to refresh
  `wfp.budget.actual` functions when `parent_id`/`manager_id` change.
- Roster truth (WFPLAN WF7): `hr.employee.department_id`/`job_id` are non-stored
  related fields via `version_id`; stored truth is `hr.version` via
  `hr.employee.current_version_id`; `hr.contract` carries `wage` always, and
  `department_id`/`job_id` on abm but NULL on company 5. One SQL join with
  `DISTINCT ON (employee_id)` costs ~70 ms for 4.5k people (`pb_decision_room/models/pb_decision_room.py:_build_baseline`).
- `hr.employee.country_id` is NATIONALITY (on `hr.version`); there is no work-country or
  tax-residence field. `hr.payslip.run` has no `company_id`.

### Analytics facts
- `pb_explorer/models/pb_fact.py`: `pb.fact.run` :49, `pb.fact.line` :108, `pb.fact.emp`
  :149 — dimensions company, month, quarter, cycle, division (Char), basis, department
  (as-at period end via `hr.version`, `pb_fact_builder.py:57-69`), job, category, code.
  **No `config_id`, no `currency_id`.** T1 SELECT at `pb_fact_builder.py:207-231`
  already `LEFT JOIN hr_formula_config fc` (:108-116). **New columns must be APPENDED
  last** — consumers read rows positionally (C18.127). Dimensions/filters:
  `pb_explorer.py:86-96 _DIMENSIONS`, `:109-120 _FILTERS`, `:85 _T2_ONLY`. Build:
  cron every 30 min (`views/pb_explorer_action.xml:11-26`), `ensure_fresh` lazy,
  `build_runs` the only writer, `rebuild_all`.
- `pb_hr_payroll_analytics/models/hr_payslip_line_analytics.py:19-27` already stores
  `formula_config_id`, `category_type`, `department_id` on `hr.payslip.line`.
- Known defects to fix in P3: `hr_analytics_personnel_costs.py:423-435` and
  `hr_analytics_statutory_contrib.py:385-407` search payslips with NO company filter;
  `pb_payruns/models/pb_payruns.py:60` lists runs with `search([])` and prices all in
  `env.company`'s currency; `pb_insights.py:324` stamps `env.company`'s symbol on totals
  summed over `env.companies`; `payroll.analytics` has no `company_id`.

### Platform seams
- Settings hub category registry: `pb_settings/static/src/js/settings_hub.js:277`
  `SETTINGS_CATEGORIES = "pb_settings_category"`; precedent
  `pb_vendor_access/static/src/js/vendor_palette.js:60-95` (category `{key, icon,
  label, blurb, groups, cards:[{id, tag, icon, label, sub}]}` seq 20 + palette row seq
  3200). Hub action `pb_settings.action_pb_settings_hub` (tag `pb_settings_hub`);
  company profile sibling `pb_settings.action_pb_company_profile`
  (`pb_settings/views/pb_settings_action.xml:9-23`). Platform-only lists in
  `pb_settings/models/pb_settings.py:63-79` — `pb_group` is NOT platform-only.
- ⌘K palette: `registry.category("pb_hub_palette")`; next free deep-link block **3300**
  (RIZE closeout). Rows must be gated via `get_sidebar_data` (pb_hub
  `test_palette_restrictions.py`).
- **No new `pb.sidebar.item`** — `pb_sidebar/tests/test_ia_c5.py:31 TARGET_RAIL` asserts
  the rail exactly. Reach screens via Settings categories, hub lenses and ⌘K.
- People hub lenses: `pb_people_hub/static/src/js/people_hub.js:82 PEOPLE_LENSES`
  (precedent `pb_assets/static/src/js/assets_palette.js:41-47`). The employee drawer
  slot `pb_people_drawer` is single-occupant (`pb_employee_vault`), not a chip seam —
  "Paid by" (P2) goes on the Employee 360 drawer via a registry that P2 adds, or on
  the pb_people row/detail template.
- Cockpit shape: `pb_assets` (manifest assets order scss → leaf js → palette js → xml;
  `ir.actions.client` RECORD; AbstractModel facade with `_safe()`, own `_can_*`,
  `env.companies` scoping, row caps, no sudo in reads except argued aggregates).
- Tests that bite every new module: `pb_hub/tests/test_static.py` (:98 bundle ==
  disk, :140 no invented hex, :159 no gradients/emoji, :172 icons in `IC`, :189 z-index
  ≤ 20, :221 kit class prefixes, :238 namespaced localStorage, :262 no implicit string
  concat, :305/:336/:343 palette rows, :430 yield selectors vs roots, :526 templates
  parse, :536 one class attr); `pb_settings/tests/test_company_profile.py:479-491`
  (no "Odoo" in `_t()`/text nodes — mirror it in each new module); hubs assert
  `pb_hub_palette_yield` absent from their own JS.
- Tenant deny-list: `pb_tenants/models/sync_rules.py:49 TENANT_SYNC_NEVER` (pb_tenants,
  pb_demo, pb_demo_portal, pb_website) + prefix `pb_platform`. `pb_group` needs no entry.

### Legacy module (pb_hr_workforce_planning) — what P6 must absorb
19 models, ~4,400 lines. External writes: `compensation_cycle.py:163` →
`hr.contract.wage`; tagging wizard → `hr.formula.rule.wfp_category`. Contract columns
`grade_id`, `compa_ratio`, `range_penetration` (stored) read by pb_contracts
(`pb_contract_360.py:50`). `pb_budget` inherits `wfp.budget.actual`
(`pb_budget/models/budget_ext.py:61`) and writes it from 7 sites (`budget_upload.py:163,
179,188`, `budget_actuals.py:261-445`, `budget_expense.py:87`, `hr_department_ext.py:42`)
+ 5 record rules in `pb_budget/security/pb_budget_security.xml`. Worth porting:
`wfp.employer.cost.calculator` (`employer_cost_calculator.py:19`, costs a person through
their scheme's rules with a fixed-point pass) and `wfp.increase.rule` targeting.
`pb_people_hub/tests` walks the legacy directory asserting it is untouched — that test
is retired in P6 when the module is.

## Odoo 19 gotchas (inherited; see WFPLAN + RIZE ledgers for the full lists)
`safe_eval` no `nocopy`; `res.users.group_ids`; `_sql_constraints` ignored → `models.Constraint`;
`ir.cron` no `numbercall`; `post_init_hook` install-only; `fields.Json` `{}` reads
back `False`; OWL does not rewrite `not`; hotkey service eats Escape (capture-phase
listeners); `minmax(0,1fr)` on both grids; `.pbim-tablewrap` clips; Sass mixed-unit
`min()/max()` kills the bundle; `-u` hides SCSS errors; `--i18n-export` is gone → `odoo-bin
i18n export`; `-u pb_people_hub` crashes p9clone on a stale pb_vendor_access cron (WF21);
`ormcache` has no TTL; `hr.department.parent_id` is `check_company=True`.

## Deploy ritual
Exactly the WFPLAN ledger ritual (clean stage `/tmp/grp_stage`, scoped per-module
`rsync --delete`, tests on p9clone with `--http-port=8199 --gevent-port=8198`, detached
`systemd-run` upgrades, `pg_dump` per DB, asset cache purge, manifest-vs-`latest_version`
and tree-hash verification, never `pkill -f odoo-bin`).

## Gotcha ledger (append below; G-numbers)

- GR1 (2026-09-07): Odoo 19 branches copy `currency_id` from the root (read-only). A
  multi-currency group can never use `res.company.parent_id`. See ruling G1.
- GR2: `pb.budget.fx._has_rate` filters rate rows by `self.env.company` — every rate row
  on a tenant belongs to company 1, so converting FOR a subsidiary while viewing another
  company answers "unknown". `pb.fx` searches `company_id in (False, group members)`.
- GR3: `scheme_mapping_data` searches departments and configs with no company domain —
  a group makes that canvas cross-company on day one; P2 scopes it.
- GR4: `pb_explorer` fact consumers read rows positionally — append new columns LAST.

## Phase log
- P1 — "The group" — designed 2026-09-07 (`GROUP_P1_THE_GROUP.md`). Status: building.
- P2 — "Who is paid by what". Not yet designed.
- P3 — "Numbers that remember". Not yet designed.
- P4 — "Planning with scope". Not yet designed.
- P5 — "People in two places". Not yet designed.
- P6 — "Pay: Review, Bands, Fairness, Changes; retire legacy" (ruling G9; may split into
  6a bands+fairness and 6b review+changes). Not yet designed.
- P7 — "Visibility, Vietnamese, closeout". Not yet designed.
