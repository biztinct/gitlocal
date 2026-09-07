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
  `Rize#Payobook2026`. Demo company **Payobook Vietnam JSC** (id 5, VN, VND): 4,533
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

### Legacy module (pb_hr_workforce_planning) — RETIRED 2026-09-08 in P6b
**It is uninstalled on p9clone, payobook, abm and payobook_template and none
of its tables remain.** Everything below is kept as the record of what was
absorbed and where it went: merit matrices → `pb.pay.guidance`, compensation
cycles → read-only `pb.pay.review` history, the per-person score →
`pb.pay.rating` plus `hr.employee.pb_performance_rating`, guardrails →
`pb.pay.review.limit` templates on `pb.pay.settings`, `wfp.budget.actual` →
`pb.budget.line` (in `pb_budget`, natively), pay grades → `pb.pay.band` (P6a).
Not absorbed on purpose: planning scenarios, forecasts and monthly projections
(the Decision Room is a different product with no sensible mapping) and the
component tagging (retired by ruling G7). The files stay in the repository as
history; nothing may import from them.

### What the legacy module used to hold (historical)
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
- GR5 (P1): **a hand-written `.po` whose entries carry no `#. module: <name>`
  comment takes the WHOLE DATABASE DOWN on install.** `odoo/tools/translate.py:857`
  does `re.match(r"(module[s]?): (\w+)", entry.comment).groups()` with no guard, so a
  missing comment is `AttributeError: 'NoneType' object has no attribute 'groups'`
  during `_update_translations`, the registry fails to load and nothing rolls forward.
  Every entry needs `#. module: pb_group` (plus `#: code:addons/…` for the occurrence);
  a free-form comment block at the top of the file is fine, entry comments are not
  optional. Validate before deploying:
  `python3 -c "import polib,re; [re.match(r'(module[s]?): (\w+)', e.comment).groups() for e in polib.pofile(PATH)]"`.
- GR6 (P1): `hr.department.complete_name` is a NON-STORED compute on Odoo 19.
  Naming it in `order=` is a hard `ValueError: Cannot convert … to SQL because it is
  not stored` — not a slow query, a crash. Read it as a field, sort in Python.
- GR7 (P1): a manifest `description` is shown to a person in the Apps list, so the
  white-label test treats it as a user-visible string. Engineering prose — model
  names, the platform's own field names, why the branch tree is unusable — belongs in
  module docstrings, which the test skips.
- GR8 (P1): a client action that renders no control panel has NO breadcrumb name, so
  anything it opens draws a trail whose first crumb reads "Unnamed". Two halves to the
  fix: `this.env.config.setDisplayName(_t("…"))` in `setup()`, and the return chip
  written on the ACTION RECORD's `context` (`{'pb_back': {...}}`) rather than at each
  door, so the Settings card, a ⌘K row and a bookmark all arrive with the same way
  out. (The Settings hub itself still crumbs as "Unnamed" — it is opened by a bare tag
  from the rail. Platform-wide, pre-existing, not this programme's.)
- GR9 (P1): every `res.currency.rate` row on payobook belongs to **company 1**, and
  Odoo's own `_get_rates` filters on `company.root_id` — company 5's root is itself.
  So a group of companies 5 + 6 genuinely has no SGD→VND rate, and the coverage strip
  is right to say so. GR2's widening is to the GROUP's members, never to every company
  on the database.
- GR10 (P1): `pb.fx._as_currency(<id>)` runs `browse().exists()` — one query. Resolving
  the currencies per ROW cost 2,000 queries and 539 ms for 1,000 conversions;
  memoising them inside `convert_many` took it to **52 ms**. `convert()` one row at a
  time is 2.1 s per 1,000 and always will be — P3 must use `convert_many`.
- GR11 (P1): companies 6 and 7 on payobook are ARCHIVED, and a company picker that
  respects `active_test` cannot build the group this product exists for. The Group
  screen reads companies with `active_test=False`, labels a parked one "Not in use
  right now", and says on the tick that adding it switches it back on.
- GR12 (P1): a refusal about something the reader is LOOKING AT belongs beside it. The
  detach dialog shows its sentence inline (`state.dialogError`); a toast over an open
  dialog is a sentence about a control the reader can no longer see.
- GR13 (P2): **`env.invalidate_all()` FLUSHES before it invalidates**
  (`invalidate_all(flush=True)` is the default), so a raw `UPDATE` followed by
  `invalidate_all()` has its work silently undone by whatever the ORM was still
  holding. `_pb_mark_paid_by_stale` wrote `pb_paid_by_stale = TRUE` in one
  statement and then invalidated; the pending `False` from the recompute a few
  lines earlier was flushed on top of it and the flag read back False every
  time — with no error anywhere. The order that works is
  `env.flush_all()` → raw statement → `env.invalidate_all(flush=False)`.
  Any raw-SQL write to a field the ORM also writes needs this shape.
- GR14 (P2): a `ir.cron` row lands in the database the moment its module
  installs, and **a worker process that is already running does not have the
  code yet**. On p9clone (where the live service stays up during a rehearsal
  install) the nightly job fired against a stale registry and logged
  `AttributeError: 'hr.employee' object has no attribute
  '_pb_cron_recompute_paid_by'`. Harmless — the next registry load fixes it —
  but it is an ERROR in the log nobody can act on. Guard the cron's code on the
  REGISTRY (`… if 'pb.scheme.map' in env else None`), not on the method.
- GR15 (P2): a sentence that names a record has to be handed the NAME of that
  record, and the record it names is very often not the one the query was
  about. `resolve_many` read department names for the people's OWN teams, but
  the scheme is normally attached to the team ABOVE them, so every explanation
  read "from this team's team map" instead of "from Bread's team map" — a
  sentence that is technically true and completely useless. Resolve names for
  everything a sentence can point at (here: the roster's teams AND every team
  on the map), not for the rows you started from.
- GR16 (P2): the pay-run population was scoped by the RECORD RULE, which
  follows the company switcher — so an administrator with three companies
  switched on produced one run holding three companies' people, and nothing
  said so. A pay run happens inside one legal entity: scope the contract
  search to `self.env.company` explicitly. (Same family as GR3: a screen with
  no company domain looks right until there are two companies.)
- GR17 (P2): **the platform's own RPC error object says "Odoo Server Error" in
  its `message`**, and the server's real sentence is at `error.data.message`.
  The `(e.message.data.message) || e.message || fallback` ladder several
  cockpits carry therefore does two wrong things at once: it never finds the
  sentence (the shape is `error.data`, not `error.message.data` on this
  platform), and it falls back to the one word this product may never say —
  printed in a red box on the screen the reader is looking at. Seen live in the
  P2 browser walk, where a perfectly good refusal about a duplicate scheme line
  rendered as "Odoo Server Error". The ladder is `error.data.message` →
  `error.message.data.message` → OUR OWN sentence, and `error.message` is not a
  rung. Fixed in `pb_scheme_map` and `pb_employee_vault`; **`pb_group`'s
  `_msg()` still carries the old shape** (owner debt, one line).
- GR18 (P2): a map made entirely of SPECIFIC kinds of run read as no map at
  all. `_pick` answered "any kind of run" with `bucket.get('any')`, and the
  drafted map writes only `end_cycle` and `mid_cycle` lines — so the board
  reported 0 of 4,533 people covered over a map it had itself just written.
  Asked about no particular kind, the fallback runs a ladder of what "the
  scheme that pays you" normally means: `any` → `end_cycle` → `regular` →
  `full_final` → `mid_cycle`, with the advance LAST, because an advance is
  never the answer to "who pays this person" unless somebody asked for it.
  The same shape bit the counts a second time: a scheme's coverage must be read
  for the scheme's OWN kind of run, or every mid-month card says "nobody yet".

- GR19 (P3): **a rate between two currencies is one rate row DIVIDED BY
  another**, so pricing only the foreign currency answers "nobody has priced
  this". `pb.fx._side_rate` looks up a `res.currency.rate` row for EACH side;
  a company's own currency usually has no row at all (it is the implicit 1.0),
  and the group's presentation currency is normally exactly that currency. So
  a fixture — or a customer — that adds one SGD row and expects SGD→VND to
  work gets `known=False` and a perfectly correct refusal. BOTH sides need a
  row under a company the group may read (`pb.fx.rate_companies`). Cost half
  an hour in the P3 test suite before it was written down.
- GR20 (P3): **`res.company.country_id` is NOT STORED on Odoo 19** — it is a
  related field through the company's partner. `('country_id', 'in', ids)` in
  a domain is therefore not a slow search, it is a hard
  `ValueError: Cannot convert res.company.country_id to SQL because it is not
  stored`, and the screen goes blank. Exactly the family of GR6
  (`hr.department.complete_name`). Match countries in PYTHON over the handful
  of companies in scope; the READ (`company.country_id.code`) is fine, only
  the domain is not.
- GR21 (P3): **a JavaScript class may not hold a getter and a method of the
  same name** — the later definition silently wins, with no warning anywhere.
  The Explorer already had a `money(value)` FORMATTER and P3 added a
  `get money()` for the currency metadata; the formatter won, so
  `this.money?.rates` read a property off a function, and every rate badge and
  the whole "Not converted" list vanished while the payload was perfectly
  correct. Two hours of looking at the right JSON and the wrong screen. One
  name, one meaning: the getter is `moneyMeta`.
- GR22 (P3): **the whitespace between two adjacent `t-esc` nodes is whitespace
  the browser may collapse**, even under `xml:space="preserve"`. A rate
  sentence assembled from four template nodes rendered as
  `1 SGD = 20,000VND· 2026-08-31`. A sentence that must read as a sentence is
  built as ONE string in JS and printed with a single `t-esc`.
- GR23 (P3): **an effective-dated attachment defaults to TODAY, and that
  silently erases all of history.** `pb.division.link.date_from` defaults to
  `context_today`, so the eight divisions P1 created this month were not live
  on any date the demo's payroll history covers: the first full fact rebuild
  produced 197,834 rows of which **35** had a division, and the phase's hero —
  a breadcrumb that walks down to a division — had nothing to walk. A period
  earlier than a department's FIRST attachment now uses that first attachment
  and is counted in `pb.fact.run.division_fallback_count`, the same honesty as
  the as-of department fallback. A department that genuinely MOVED between
  divisions still reads its old one for old periods. Any effective-dated
  dimension added later needs the same "before the first record" answer
  decided on purpose.
- GR24 (P3): **the payobook admin password in this ledger is WRONG.**
  `ash@biztinct.com` / `Rize#Payobook2026` is refused by `res.users` on the
  master database (verified directly, not just through the login form); the
  same shape as WFPLAN's WF15 for abm. P3 validated with a temporary
  `group.p3@payobook.com`, archived afterwards. Resetting the owner's own
  password is an owner decision and was not done.

- GR25 (P4): **an `ir.cron` whose `model_id` names a model the running
  worker has never heard of throws inside the PLATFORM, where no guard of
  ours can reach it.** GR14 said to guard a cron's CODE on the registry; that
  is not enough. Odoo builds a server action's eval context with
  `self.env[model_name]` (`base/models/ir_actions.py:1125`) BEFORE a line of
  the action's code runs, so a cron pointing at a table this upgrade created
  is a `KeyError` on the first pass after install — one ERROR in the log with
  nothing anybody can act on, exactly as GR14's was. The cron therefore names
  a model every worker has had since an earlier phase (`pb.decision.plan`)
  and the code does `env['pb.decision.exact.job']._cron_run() if
  'pb.decision.exact.job' in env else None`. A cron is also the wrong place
  for `noupdate="1"`: it is plumbing, and a fix to it has to reach a database
  that already has yesterday's version.
- GR26 (P4): **a value the TEMPLATE reads has to live in `useState`.** The
  Decision Room deliberately keeps its heavy results (three computed years) on
  the instance and off the reactive state, and every getter that reads them
  starts `void this.state.rev;` to subscribe. Copying that shape for a small
  metadata object — which rules this scope follows — and forgetting the `void`
  produced a dialog that rendered `{}` for the whole session: the heading read
  "Rules typed for " with an empty name and the override button never
  appeared, while the RPC beside it returned the data in full. Nothing is
  logged, and the JSON in the network tab is perfect, so it looks like a
  server bug for as long as you are willing to believe one. Small metadata
  goes in `useState`; only genuinely heavy, wholesale-replaced results earn a
  place on the instance, and those must be read through a `state.rev` gate.
- GR27 (P4): **the company RECORD RULE follows the switcher, not the scope.**
  P4 resolves a scope from every company the reader is ENTITLED to
  (`res.users.company_ids`), because a person planning a group should not have
  to tick five boxes in a menu first. But the global rule on a plan reads
  `company_ids` from the CONTEXT — `allowed_company_ids`, the switcher — so
  saving a plan for Payobook Vietnam while standing in the head office was
  refused with the platform's "top-secret records" dialog. The fix is
  `_with_companies()`: widen `allowed_company_ids` to the intersection of the
  scope and `user.company_ids`, which is not a privilege (that context may
  only ever be a subset of the user's own companies) and is needed on every
  read AND write of a plan or a set of assumptions. Same family as GR16 and
  GR3: a screen with no company domain looks right until there are two.
- GR28 (P4): **two transactions may not write the same row on this
  platform.** The exact-cost job reports progress on a cursor of its own so a
  chip on screen can move while the work is still running. The job's MAIN
  transaction also wrote `state='running'` at the start and `state='done'` at
  the end — and Odoo runs on REPEATABLE READ, so the final write failed with
  `could not serialize access due to concurrent update` and left the row
  saying "running" for ever. One writer per row: every field of the queue row
  is written by the side cursor, and the main transaction writes only the
  RESULT, which lives on the plan.
- GR29 (P4): **a loop variable called `job` two hundred lines below a
  parameter called `job`.** `for _emp, scheme, dep, job, wage, company in
  rows:` rebound the queue record to an integer, and the next progress write
  died on `'int' object has no attribute 'id'` — after the expensive part had
  already run. Unpacking a wide SQL row is where this happens; name the
  columns you do not use `_something`, and never a name the method already
  holds.
- GR30 (P4): **one classified component out of sixty is not a classified
  scheme.** The exact-cost lane buckets a payslip by `net_role`, and it read
  "somebody has classified this" as "any rule carries a role". On payobook
  exactly one rule of the Retail scheme carries one (`INCENTV`, an input
  worth zero), so the whole scheme priced at **₫0** against an estimate of
  ₫230B, with `ok: true` and no note. The test that means what it says is
  whether the scheme knows which component IS net pay: without a `net` role
  nothing can be bucketed. Failing that, the scheme's own net-pay formula is
  walked read-only through `_build_net_role_classification()` (which does not
  write, unlike `classify_net_roles()`), the answer says it was derived, and
  the figure came out at ₫182B — 20.6 % under the average-based estimate.

- GR31 (P4): **a side-cursor write is invisible inside a test, and a no-op
  against a row the test has not committed.** GR28's fix — the exact-cost
  queue row written on its own cursor — means a `TransactionCase` that creates
  a job and runs it reads back `state = 'queued'` for ever: its own
  transaction cannot see the other one's commit, and the other one's `UPDATE`
  matched nothing because the row only exists inside the test. Assert on what
  the MAIN transaction wrote (here `plan.exact_result`) and treat the queue
  row's state as a thing only a browser can see.
- GR32 (P4): **`search([('company_id', '=', X)], limit=1)` stopped meaning
  one row.** P4 gives a company several sets of assumptions — one for the
  company, one for each division and scheme inside it — so a lookup by
  company alone returns whichever the database felt like. The baseline's
  "which teams earn revenue" was reading a division's row on a company view.
  Every lookup of a settings row now carries its SCOPE, and a lookup by
  company means `('scope_kind', '=', 'company')` out loud.

- GR33 (P5): **a demo-generated pay run cannot be reproduced by re-running
  it, and never could.** GROUP P2's T10 recorded a June re-run of Retail
  End-Month coming back "identical to the digit"; the same recipe now
  produces ₫14.77B against a stored ₫4.88B, and the difference is not this
  phase's. The run's INPUTS (`INCOMM` ₫6,355,041, `INKPI` ₫1,166,451, `OTWD`
  10 days on the first payslip alone) were written by the demo generator, not
  by anything the batch-free resolver can read back: with no pay-data file
  and no import batch those components resolve to their defaults, so the
  recompute is a different — and perfectly correct — calculation. So a
  PARITY test must not compare a recompute against the stored numbers. It
  must compare the SAME payslips computed twice, once with the change and
  once with it neutered, inside one savepoint. P5's T1 does that over all 902
  payslips: `Seg.apply_to_inputs` is monkey-patched to a no-op for the second
  pass, both totals come to ₫14,768,030,400, and 0 of 902 differ. Any later
  phase that touches compute should use that shape and not P2's.
- GR34 (P5): **a stored compute with `readonly=False` never runs if the field
  also has a `default`.** `pb.work.segment.fte` was declared
  `compute='_compute_fte', store=True, readonly=False, default=0.0`, and the
  ORM treats the default as a value the caller supplied — so the compute was
  skipped on every create and every stretch of days was worth ZERO full-time
  people, which is the entire figure the field exists to carry. Nothing is
  logged and the field looks perfectly well defined. An editable stored
  compute takes its initial value from the compute or from nowhere.
- GR35 (P5): **"the components net pay ADDS" is not the same set as "the
  components that mean per month", and on this build it is empty.** The first
  attempt at deciding what a fraction of a month may scale used the VALUEKIND
  classification: input rules whose `net_role` is `earning`. On the live
  Retail scheme that set has NO members — its earnings are all derived
  columns and its inputs are raw — so a 45 %-of-a-month segment reduced
  nothing at all, silently, with `ok` everywhere. The test that means what it
  says is WHERE THE NUMBER CAME FROM: a value the provenance attributes to
  the contract (`via` in `contract_field` / `contract` / `contract_default`,
  or `src == 'contract_component'`) is a standing monthly amount and is
  scaled; everything else — a pay-data file, a feed, overtime, a one-off —
  is already this month's figure and is left alone. And a no-op is now
  LOGGED with the factor and the scheme, because an empty set is the one
  answer a payroll rail may not give in silence.
- GR36 (P5): **two ways to compute a run, and a hook in only one of them.**
  `hr.payslip._get_formula_input_values` is the batch-free producer; a run
  built from an uploaded pay-data file resolves its values in
  `hr.payroll.import.batch._resolve_input_values` and never reaches it. A
  hook placed only in the first is honoured on one of the two ways a customer
  can run payroll and silently ignored on the other. `pb.work.segment` now
  exposes `apply_to_inputs` (payslip) and `apply_to_batch_inputs` (batch)
  over ONE body, and the batch call goes through `_run_adjustment('segment',
  …)` so the source chips say the number was scaled rather than pretending it
  arrived that way.
- GR37 (P5): **`env.companies` is the switcher, again — this time it made a
  review lie.** "Same person?" looked for duplicate employee records across
  `self.env.companies`, i.e. the companies ticked in the menu. The whole
  point of the review is that the two records are in DIFFERENT companies, so
  with one company switched on it found the pair and reported "nobody looks
  like a duplicate" — the most convincing possible way to be wrong. It now
  reads `res.users.company_ids`, every company the reader is entitled to,
  which is P4's `_with_companies` reasoning (GR27) applied to a read. Third
  time this family has cost a bug: GR3, GR16, GR27.
- GR38 (P5): **the `pbim` kit has no dark palette at all.** Every phase of
  this programme has reported walking its screens "light and dark"; what
  actually happens is that the PLATFORM's chrome re-tints and the `.pbim`
  surface stays exactly as designed, because `pb_import_kit`'s
  `import_tokens.scss` defines one set of `--pbim-*` values and no
  `prefers-color-scheme` block and no `.o_dark_mode` override. Emulating a
  dark colour scheme therefore changes nothing inside a cockpit. This is
  programme-wide and pre-existing, not P5's; it is written down here so the
  next phase stops claiming a pass it cannot make. Giving the kit a dark
  palette is a `pb_import_kit` job and belongs to P7 or later.

- GR39 (P6a): **a fragment of `sql` built with `%` formatting eats the
  placeholders psycopg is meant to fill.** The position pass assembles a
  `VALUES` list whose rows are `(%s, %s, …)` and then drops it into a
  larger statement; written as `sql = """WITH %s, …""" % (band_cte, where)`
  the outer format consumes the INNER `%s` and psycopg is handed a
  statement with the wrong number of parameters. There is no safe way to
  format a SQL string that itself contains placeholders: build it by
  CONCATENATION, and let `%s` mean exactly one thing.
- GR40 (P6a): **`position: sticky; bottom: 0` on a control that answers a
  drag is a control nobody sees.** The band picture is four screens tall,
  so a bar at the foot of the CARD sticks to the bottom of the card, not
  of the window, and the sentence that has to be true while the mouse is
  down renders three thousand pixels below the mouse. A running answer to
  a gesture is `position: fixed`, or it is decoration.
- GR41 (P6a): **`companies[:1]` is "the lowest id", and on this group that
  is the entity with nobody in it.** Fairness opened on Payobook Singapore
  (0 people) and its first sentence was "there is nobody to measure" — true
  and useless — while 4,510 Vietnamese people sat one menu away. The same
  bug in its second form: refusing to mix two currencies KEPT the first
  company's currency and dropped 4,510 people to keep 0. A default scope is
  the company the reader is standing in, and failing that the one with the
  most people; a majority currency is the one a refusal keeps.
- GR42 (P6a): **the platform's `_()` has no plural form, and "1 people" is
  the first thing a reader sees.** On AB Mauri most suggested bands hold
  one person, so the screen read "1 people · ₫22M to ₫27M" twenty-nine
  times. There is no `ngettext` here: write the phrase once
  (`_people_phrase`), branch on `count == 1` inside it, and pass the PHRASE
  into the sentence rather than the number.
- GR43 (P6a): **a shared money axis is squashed by one outlier, and the
  fix has to stay honest.** One person paid four times the top of the
  highest band stretched every band into a sliver. The axis now runs to the
  top of the highest BAND or the 95th percentile of pay, whichever is
  greater; the handful beyond sit ON the right edge, are always
  "above the band" anyway, and the lane says how many and what the edge is
  worth. Also: an axis label at 0% or 100% centred on its tick hangs half
  off the picture — the first is left-aligned and the last right-aligned.
- GR44 (P6a): **a rebuild queued on every `hr.contract.write` turns a
  payroll import into a ten-minute one.** 4,500 position rows rebuilt after
  each of several hundred contract writes is quadratic work for a figure
  nobody reads until a screen opens. The work goes on the cursor's
  PRECOMMIT (`cr.precommit.add`), so it runs ONCE per transaction, inside
  it, and a rollback takes it with it. The cost: a `TransactionCase` never
  commits, so a test that changes a wage must call
  `env.cr.precommit.run()` itself — the same family of surprise as WF16.
- GR45 (P6a): **`/odoo/action-<name>` resolves a bare xmlid for some
  records and silently lands on Discuss for others.** `action-pb_pay`
  worked and `action-pb_pay_fairness` did not. Always write the full
  `module.name` in a test or validation URL; the short form is a
  coincidence, not a contract.

- GR46 (P6b): **a contract write queues a rebuild of the whole position
  table, and anything that flushes the cursor mid-loop runs it.** GR44 put
  that rebuild on `cr.precommit` so it happens ONCE per transaction — which
  is exactly right for a person saving one contract. Apply writes four
  thousand, and something inside the loop flushes the cursor on nearly every
  iteration, so the queued pass ran again and again: 4,510 rows rebuilt every
  450 ms, for ever, with the apply never finishing and nothing in the log but
  a wall of "positions rebuilt". The fix is the context flag the trigger
  already honours — `pb_pay_no_rebuild=True` on the bulk write — and ONE
  `recompute_all()` at the end. Any bulk write to a model that carries a
  precommit trigger needs the same treatment; a precommit hook is a guard
  against repetition, not against a loop.
- GR47 (P6b): **`pb_demo` already defines `hr.employee.pb_performance_rating`,
  and 4,502 people on the demo company carry one.** A new field of the same
  name in another module is not an error on this platform — the two
  definitions are merged and whichever loads last wins on `string`, `groups`
  and `help`. Declaring a SECOND field for the same fact would have stranded
  the demo's scores and opened every pay review saying "nobody has been
  scored" on a database full of scores, so `pb_pay` deliberately declares the
  SAME field with the same five values and, critically, WITHOUT the
  `groups="hr.group_hr_user"` it was first written with: a shared field is
  only safe while neither owner narrows it. Two modules, one column, written
  down here because the next person to grep for it will find two definitions
  and assume one is a mistake.
- GR48 (P6b): **server-side QWeb compiles an expression as PYTHON, so `!x` is
  a SyntaxError there and `not x` is a SyntaxError in the browser.** WFPLAN
  WF3 taught the browser half: OWL rewrites `and`/`or` and not `not`. The
  portal page is the first screen this programme has shipped on the OTHER
  engine, and `t-if="!enabled"` came out as a five-hundred error page with the
  real message four hundred lines up the log (`SyntaxError: invalid syntax
  (<>, line 1)`), under a heap of unrelated favicon tracebacks. One product,
  two template languages, and their rules are mirror images.
- GR49 (P6b): **uninstalling a module cannot delete a group another module's
  record rule still points at, and it does not come back for it.** The
  platform tries `DELETE FROM res_groups WHERE id IN (…)`, the foreign key
  refuses, it drops one id and tries again, and whatever is left at the end
  simply survives — with its xmlid row, its users and its implications
  intact. After the first rehearsal `pb_hr_workforce_planning.group_wfp_user`
  was still there, showing in every tenant's list of roles as a group called
  plainly "User" belonging to nothing. `pb.pay.retire.tidy_up()` runs after
  the uninstall, scoped to `ir.model.data` rows the retired module owned by
  name, and reports what it took. Any future retirement needs the same sweep.
- GR50 (P6b): **a picture of a categorical scatter is a picture of four dots
  until you jitter it.** Nine hundred people on five ratings and one guidance
  grid land on five coordinates, and the calibration view drew five dots over
  eight hundred and ninety-five invisible ones. Two things fix it and both
  are needed: a deterministic sideways nudge per row (from the row's own id,
  so a person does not move between reads), and a SENTENCE for the case where
  the picture is genuinely flat — "everybody is still on the guidance, so each
  score sits on one line" — because the honest version of that screen looks
  exactly like the broken one.
- GR51 (P6b): **a rating of 5 read by a four-level grid must be the top, not
  the middle.** The first `pct_for` treated any out-of-range score as
  "nobody has told us" and fell to the middle rating, which on the day a
  company upgrades from a five-point scale to a four-level grid quietly
  halves the rise of every one of its best people. Out of range HIGH is the
  top; out of range LOW (zero, unscored) is the middle, and only that one
  carries the "nobody has scored this person" chip. The default grid also now
  SIZES ITSELF from the scores the reader can already see, across every
  company they are entitled to rather than the one they are standing in
  (GR41's family, on a different screen).
- GR52 (P6b): **the migration read eleven columns another module had added to
  a table it did not own, and the platform had just dropped them.** Removing
  a field from a model removes its column, and `pb_budget`'s eleven additions
  to `wfp.budget.actual` went the moment `budget_ext.py` did — AFTER the
  post-migrate had copied the rows, so the data was safe and the same
  migration re-run from a test blew up on `column "pb_budget_type" does not
  exist`. A migration reads `information_schema.columns` first and selects
  `NULL AS <name>` for anything that is not there; and it matches rows on the
  columns that SURVIVE, or a second run duplicates every row whose kind the
  old table can no longer state.
- GR53 (P6b): **two grand totals are the wrong parity check for a table the
  product writes to.** The pre-flight gate first compared
  `SUM(actual_cost)` on the old table with the new one, which is true on the
  day of the move and false for ever afterwards — the moment anybody enters a
  budget the gate refuses and nobody can tell why. The check that keeps
  meaning what it says is ROW BY ROW: every old row has a row on the new side
  for the same company, team and month, and what was spent on it is the same
  figure. The new table is allowed to hold more than the old one; it is not
  allowed to hold less.

- GR54 (P7): **the platform's own `_()` reads the CALLING FRAME's local
  variables, and a local called `user` that is `None` kills it.**
  `odoo/tools/translate.py:517` is `return int(frame.f_locals['user'])` with
  no guard — the translator looks one frame up for the reader whose language
  to answer in, and any local of that name is taken to BE that reader. So a
  perfectly ordinary method signature — `def scope_note(self, user=None)` —
  that calls `_()` anywhere in its body dies with
  `TypeError: int() argument must be a string, a bytes-like object or a real
  number, not 'NoneType'`, raised hundreds of lines away inside the platform,
  with nothing in the traceback that names the parameter. It cost an hour and
  three probes, and it only appears when the argument is actually left out,
  which is exactly how every internal caller calls it. **Never name a local
  or a parameter `user` in a method that calls `_()`** — this programme's
  convention is now `who`. (The same trap is waiting for `lang` and `env`,
  which `_get_translation_source` also reads out of the frame.)
- GR55 (P7): **a record rule's `domain_force` may read a COMPUTED,
  NON-STORED field off `user`, and that is the cheapest way to make one
  rule shape answer four models.** `safe_eval` allows attribute access and a
  ternary, so `[(1, '=', 1)] if not user.pb_vis_kind else [...]` is a legal
  domain; the three fields are computed on `res.users` from
  `pb.group.visibility` and stored nowhere, so there is nothing to keep in
  step and a division that gains a department is honoured on the next read.
  The compute must do its own reads under `sudo()` or the rule recurses into
  itself. A method CALL in a domain would also have worked; a field read is
  what every rule the platform ships already does, which is the reason to
  prefer it.
- GR56 (P7): **`odoo-bin i18n export` is a SUBCOMMAND and rejects the server
  options** — `--http-port` / `--gevent-port` are `unrecognized arguments`,
  and it needs no ports because it never binds one (WF28 said the subcommand
  exists; this is the other half). It also writes as the `odoo` user, so a
  staging directory made with `sudo mkdir` under `/tmp` is a
  `PermissionError` on the first file with the rest of the loop still
  running. Make the directory as `odoo`, or `chmod 777` it.
- GR57 (P7): **the test-run log does not come back on stdout.** The server
  config names a `logfile`, so a detached `--test-enable` run writes its
  results into `/var/log/odoo/odoo-server.log` INTERLEAVED with the live
  service's own lines, and the redirect captures nothing but docutils
  warnings about the manifest descriptions. Every test run in this phase
  passes `--logfile=/tmp/<name>.log`, which also has to exist and be owned by
  `odoo` before `systemd-run` starts.

- GR58 (P7): **a selection LABEL is not a string `_()` can find, and the two
  halves of the same catalogue live in different places.** A `.po` entry whose
  only occurrence is `#: model:ir.model.fields.selection,name:…` is imported
  into the database column and is invisible to `code_translations`, which is
  what `_()` reads — so `_("The last rate of the month")` came back in ENGLISH
  on a screen where every other server-built sentence in the same method was
  Vietnamese. Going the other way is no better: `fields_get` translates a
  selection through `ir.model.fields._get_fields_cached`, which is `ormcache`d
  on the language with `cache='stable'`, so a `.po` imported by another process
  does not reach the running worker until it is restarted. The rule this
  programme now follows: **a label a person reads is a string the module owns**
  — written with `_()` in the facade, never read back out of `fields_get` —
  and the same literal then appears in the catalogue with BOTH a `model:` and a
  `code:` occurrence, which is what makes it work on both paths. Re-export the
  `.pot` after any such change and refresh the `.po`'s occurrences from it,
  because an entry with the wrong references is silently half-loaded.
- GR59 (P7): **`('country', _("One country"))` puts the bare word `country`
  into the catalogue as a term somebody has to translate.** The Python string
  extractor collects the first string of a tuple that also contains a `_()`
  call, so a list of `(key, label)` pairs produces one junk one-word msgid per
  pair — and the completeness test then fails on words no reader will ever
  see. Build the labels as a DICT keyed by the value and derive the ordered
  list from it.
- GR60 (P7): **the P2 board was invisible on any database whose OLD mapping
  canvas had nothing to say.** `pb_formula_studio`'s scheme tab renders the
  generic "Nothing to map yet" empty state in a `t-elif` that came BEFORE the
  branch mounting `pb_scheme_map`'s board, so a company with four and a half
  thousand mapped people was shown an empty state belonging to a canvas it no
  longer uses. The board's branch now answers first; it has an empty state of
  its own and a much better one. Any soft-registry board mounted into a tab
  that already has its own data call needs the same ordering.


## Phase log
- P1 — "The group" — designed and BUILT 2026-09-07 (`GROUP_P1_THE_GROUP.md`).
  Status: **COMPLETE**. `pb_group` 19.0.1.0.1 live on p9clone, payobook, abm and
  payobook_template; `pb_budget` 19.0.1.1.0 (`pb.budget.fx` is now a shim over
  `pb.fx`, same public API, `payment_date` policy and 2-decimal rounding so its
  numbers are unchanged to the digit); `pb_import_kit` 19.0.1.13.0 (`globe`, `coins`).
  `pb_demo` UNCHANGED — `pb.fx` probes `res.company.presentation_currency_id` instead
  of redefining it, so the demo generator keeps writing the column it always wrote.
  Shipped: `pb.group` (members via `res.company.pb_group_id`, group currency, rate
  policy, fiscal start, chatter), `pb.fx` (three policies, rate date on every answer,
  group-scoped rate rows, `convert_many`, `coverage`), `pb.division` +
  `pb.division.link` (effective-dated, one division per department per day,
  attachment at the top of a branch covers everything under it, accent-folded
  suggestions), `pb.group.room`, and the Group screen behind the Settings cog
  (category seq 30, ⌘K rows 3300/3310/3320, no new rail item).
  43 post-install tests green on p9clone (34 `pb_group` + 21 `pb_budget` methods).
  Timings on company 5 (4,533 people): `get_room` **49 ms**, 1,000 conversions
  through `convert_many` **52 ms**. B1–B8 walked on payobook and abm at 1440 and 390.
  Screenshots: `docs/handovers/group_p1_shots/`.
  Demo group on payobook: **"Payobook Group" (PBG)**, VND, "the last rate of the
  month", year starts January, members Payobook Vietnam JSC (5) and Payobook
  Singapore Pte Ltd (6, switched back on as it joined); eight divisions —
  Manufacturing 1,002 · Retail 902 · Construction 799 · Logistics 700 · Technology
  600 · Corporate Office 500 · Production 1 · Singapore 0, plus 29 people not in a
  division (4,533 exactly).
  Owner debts: company 6 was ARCHIVED and is now active on payobook; the two "RIZE …
  (test)" top-level departments were left out of the divisions on purpose; the
  Settings hub's own breadcrumb still reads "Unnamed" (platform-wide, GR8).
- P2 — "Who is paid by what" — designed and BUILT 2026-09-07
  (`GROUP_P2_WHO_IS_PAID_BY_WHAT.md`). Status: **COMPLETE**.
  `pb_scheme_map` 19.0.1.0.0 live on p9clone, payobook, abm and
  payobook_template; `pb_hr_payroll_formula` 19.0.1.122.0 (the ladder consults
  the map, the run's own scheme beats everything, the sibling rung demoted),
  `pb_payrun_wizard` 19.0.1.19.0 (the scheme picker, one-company scoping, the
  scheme stamped on the run and on every payslip), `pb_formula_studio`
  19.0.1.179.0 (scheme mode company-scoped — GR3 closed — advances no longer
  filtered out, attaching replaces only the same kind of run, the board slot),
  `pb_employee_vault` 19.0.1.1.0 (the Employee 360 chip registry),
  `pb_import_kit` 19.0.1.14.0 (`unlink`, `userX`, `arrowRight`), `pb_demo`
  19.0.1.10.0 (its division run and the scheme picker reconciled).
  Shipped: `hr.formula.scheme.assignment` grown a KIND OF RUN, a division, a
  company and a provenance; `pb.scheme.map` (the six-rung resolver,
  `resolve_many`, `coverage`, `draft`, `accept_draft`, `get_exceptions`);
  `hr.employee.pb_paid_by_id` / `pb_paid_by_advance_id` / `pb_paid_by_rung` /
  `pb_paid_by_stale` with SQL-marked staleness, a bulk recompute and a nightly
  job; `hr.payslip.run.pb_formula_config_id`; `pb.scheme.board` and the
  "Who is paid by what" board inside the Mapping screen (drafted map, coverage
  rings, wires with cycle badges, the exceptions queue, bulk attach); the pay
  run's scheme cards; ⌘K rows 3330/3340. No rail item, no Settings category.
  27 `pb_scheme_map` test methods green on p9clone, and the neighbouring suites
  (`pb_formula_studio` 410, `pb_payrun_wizard` 40, `pb_group` 34, `pb_budget`
  21, `pb_hub` 34, `pb_people_hub` 37, `pb_decision_room` 44,
  `pb_employee_vault` 14) show the SAME 2 failures + 12 errors as a pristine
  HEAD checkout on the same database — zero regressions; those 14 are p9clone
  data drift and predate this phase.
  Timings on company 5 (4,533 people): `resolve_many` **57 ms**, `coverage`
  **75 ms**, `draft` **108 ms** over 30,500 payslips.
  The drafted map on Payobook Vietnam JSC: **12 lines**, six end-of-month and
  six mid-month, every one at 0.997–1.000 agreement; accepted whole; coverage
  4,503 of 4,533, the 30 uncovered being the RIZE test departments and the
  people with no team.
  T10 parity, rehearsed on p9clone and rolled back: re-running Retail
  End-Month for June 2026 into a scratch run produced **902 payslips and a net
  of ₫4,878,568,644 — identical to the digit** to the existing run.
  Rule 8 proven live on abm: 152 people with no scheme named and 152 with the
  scheme named, the same people.
  B1–B6 walked on payobook and abm at 1440 and 390.
  Screenshots: `docs/handovers/group_p2_shots/`.
  Owner debts: the demo map on payobook company 5 is now WRITTEN (12 accepted
  lines) — that is real configuration, not a test fixture; `pb_group`'s
  `_msg()` still carries the "Odoo Server Error" fallback (GR17, one line);
  the abm validator (id 246) was reactivated for the walk and archived again.
- P3 — "Numbers that remember" — designed and BUILT 2026-09-07
  (`GROUP_P3_NUMBERS_THAT_REMEMBER.md`). Status: **COMPLETE**.
  `pb_explorer` 19.0.2.0.8 live on p9clone, payobook, abm and
  payobook_template (it now DEPENDS on `pb_group` — `pb.fx` and
  `pb.division`); `pb_insights` 19.0.5.0.0, `pb_payruns` 19.0.1.18.0,
  `pb_hr_payroll_analytics` 19.0.1.2.0, `payroll_analytics_approval`
  19.0.1.3.0, `pb_group` 19.0.1.1.0 (GR17 closed). `pb_import_kit`
  UNCHANGED — every icon this phase needed was already in the shared set, and
  `pb_explorer`/`pb_insights` now fall through to it rather than keeping a
  second registry.
  Shipped: the fact tables remember their scheme, its name and the version in
  force, the currency, the group division as at the period end, the person and
  the full-time equivalent, and whether the row is a mid-month advance — all
  APPENDED LAST (GR4), with `test_01_aggregate_parity` pinning the column
  count; the Explorer's breadcrumb (Group › Country › Company › Division ›
  Department › Job, built server-side from the rungs that exist, singular
  rungs skipped, the whole view in the URL hash); the group-currency switch
  through `pb.fx.convert_many` with a rate badge on every converted figure and
  a "Not converted" list with the reason; "Main runs only" as a removable
  default; People and full-time equivalents "counted once across the group";
  "Per person" on any money measure; the Compare schemes lens (months across,
  schemes down, a sparkline per row) and ⌘K row 3350; seven new plain-English
  phrases. Insights names the money it is showing and measures each person
  against their OWN company's overtime ceiling; the pay-run board is scoped to
  the switcher's companies and prices each run in its own currency; the two
  old analytics reports and the period comparison filter by company (and their
  country filter no longer dies on Odoo 19's removed `address_home_id`).
  46 `pb_explorer` tests green on p9clone; the neighbouring suites show the
  SAME 2 failures + 12 errors as before this phase over 675 tests — zero
  regressions.
  Full fact rebuild (`rebuild_all_timed`): p9clone **92.6 s**, payobook
  **90.6 s** (45 runs, 6,158 T1 rows, 197,834 T2 rows), abm **0.7 s**,
  payobook_template **0.0 s** (no payroll yet). 1,000 conversions through
  `convert_many` stay at P1's 52 ms.
  On payobook: 197,806 of 197,834 fact rows carry a division across the
  group's six real ones, 92,596 are advance rows, 5,223 are dated before their
  department joined a division and say so.
  B1–B10 walked on payobook, p9clone (the two-currency rehearsal) and abm at
  1440 and 390, light and dark. Screenshots: `docs/handovers/group_p3_shots/`.
  The p9clone rehearsal (a group, an SGD→VND rate of 20,000 for August, a
  Singapore run of S$6,000) was DELETED afterwards and verified gone.
  Owner debts: the payobook admin password in this ledger is wrong (GR24) —
  P3 used a temporary `group.p3@payobook.com`, archived again, as were
  p9clone's copy and abm's `wfplan.validator@payobook.com` (id 246); the
  Explorer's ⌘K row could not be opened by a synthesised keypress in the
  automation, so the row was proven by its registration and by opening its
  destination — a person should press ⌘K once to confirm; `pb_insights`'s new
  scheme chips stay empty on the demo data because P2 stamps the run's scheme
  only on runs created since, which is correct and will fill itself.
- P4 — "Planning with scope" — designed and BUILT 2026-09-07
  (`GROUP_P4_PLANNING_WITH_SCOPE.md`). Status: **COMPLETE**.
  `pb_decision_room` 19.0.4.0.0 live on p9clone, payobook, abm and
  payobook_template (it now DEPENDS on `pb_group` — `pb.fx` and
  `pb.division`); `pb_group` 19.0.1.2.0 (its "nobody has priced this pair"
  sentence is now Vietnamese — the Decision Room is the first screen that
  prints it to a Vietnamese reader). `pb_import_kit` UNCHANGED: every icon
  this phase needed — `globe`, `mapPin`, `building`, `layers`, `route`,
  `chevron`, `chevronDown`, `landmark`, `history`, `checkCircle` — was
  already in the shared set.
  Shipped: the SCOPE chip at the top of the stage and its tree picker with a
  head count on every node (group › country › company › division › payroll
  scheme), remembered per person and carried in the link; `pb.decision.scope`
  and a scope-aware baseline that reproduces the company view to the digit
  (T1); `pb.decision.ruleset` with eight countries shipped as `noupdate` data
  and a resolution order scheme → company → country → Vietnam, with a
  contribution ceiling that is dropped and EXPLAINED when it is written in a
  currency the company does not keep its books in; a group stage that
  computes each company in its own money under its own rules and converts
  only for reading, with the rate badge, the "Not converted" strip and an
  "Each in its own money" switch; the actual line over the plan from
  `pb.fact.emp`, naming the last month that reads like a full payroll and
  saying so when it does not; propose / approve / send back with versions
  that keep the levers, goals, numbers, scope and what could not be
  converted; the exact-cost lane (`pb.decision.exact` + a queue table + a
  cron) that runs a plan's people through their own scheme's formulas,
  bucketing by `net_role`/`value_kind` (ruling G7) and reading the scheme's
  own classification when nobody has confirmed one; ⌘K rows 3360 "Plan the
  group" and 3370 "Plans awaiting approval"; and 210 new Vietnamese terms.
  **The Home decision: a CHIP, not a second lens.** Approvals reach the
  reader on the Decision Room lens they already have. A rail the IA
  programme cut from thirty-eight items to eight does not get a ninth whose
  content is empty on most days.
  164 tests green on p9clone (`pb_decision_room` 71 methods incl. the new
  `test_decision_scope.py`, plus `pb_group` 34, `pb_scheme_map` 31,
  `pb_explorer` 50, `pb_hub` 34, `pb_people_hub` 37) — 0 failed, 0 errors,
  zero regressions. 89 engine checks green under
  `node tools/decision_engine_check.mjs` (19 new: T48 identity, T49–T52
  group conversion, T53–T54 actuals, T55 the search functions over a group).
  Timings on company 5 (4,533 people): `get_room` cold **157 ms**, warm
  **110 ms**; the exact-cost lane priced 902 people in 229 pay bands in
  **9 s** on payobook.
  On payobook the Retail scheme's exact cost came to **₫182B against an
  estimated ₫230B — 20.6 % under**, derived from the scheme's own net-pay
  formula because only one of its sixty components has ever been classified.
  B1–B10 walked on payobook, abm and p9clone at 1440 and 390, light and
  dark, in English and Vietnamese. Screenshots:
  `docs/handovers/group_p4_shots/`.
  The p9clone rehearsal (a group of companies 5 + 6, twelve months of
  SGD and VND rate rows at 18,000, three scratch Singapore contracts at
  S$8,000) proved the converted group total — ₫1,382B = ₫1,376B + ₫6.88B —
  and was DELETED afterwards and verified gone.
  Owner debts: `pb_group`'s Vietnamese catalogue holds 29 of its 225 terms —
  P4 translated only the one sentence it prints, and the rest belongs to P7;
  four sets of assumptions now exist against company 5 (the company's own,
  plus one each for the group, the Retail scheme and the Logistics division)
  because a scope creates its settings row on first read — that is the model
  working, not litter; every temporary validator is archived again (payobook
  4408/4409, abm 246, p9clone 3968); the "Board draft" plan and the ₫2,200B
  revenue target from WFPLAN P1 are still on payobook company 5.
- P5 — "People in two places" — designed and BUILT 2026-09-07
  (`GROUP_P5_PEOPLE_IN_TWO_PLACES.md`). Status: **COMPLETE**.
  `pb_workseg` 19.0.1.0.2 live on p9clone, payobook, abm and
  payobook_template; `pb_group` 19.0.1.3.1 (the split-pay policy and the
  "How split months are paid" card), `pb_hr_payroll_formula` 19.0.1.123.0
  (the three guarded hooks and the segment proration row),
  `pb_payrun_wizard` 19.0.1.20.1 (host employments in the population, the
  Split chip, both payslips previewed), `pb_explorer` 19.0.2.1.1 (person,
  full-time equivalent, charged-to / charged-from and the "Paid in two
  places" chip), `pb_decision_room` 19.0.4.1.1 (the full-time figure and the
  split note), `pb_scheme_map` 19.0.1.1.1 (rung 1 answers), `pb_import_kit`
  19.0.1.15.0 (`circle`, `userCheck`).
  All eight module trees verified byte-identical to the repository on the
  server, and every manifest version verified against
  `ir_module_module.latest_version` on all four databases.
  Shipped: `pb.person` (one human, however many employments, bootstrapped
  one-per-employee on install and on upgrade, with `merge`, `suggest_merges`
  and a "Same person?" review); `pb.work.segment` (the days somebody spent
  elsewhere, with working days from the home calendar, a share, a full-time
  equivalent, the two payment patterns and a per-stretch override, and
  refusals in plain sentences for a month-crossing stretch, an overlap, more
  than a full month, a host employment in the wrong entity and a month that
  is already paid); `pb.cost.transfer` (what one entity carried for another,
  stored in the money it was paid in and converted only at read time);
  `res.company.prorate_joiners_leavers`, shipped OFF; `factor_for` and ONE
  guarded, wrapped hook on each of the two ways a run can be computed;
  proration rows with `basis='segment'` so the payslip's own drawer explains
  a split month; the Assignments screen with the month strip, the popover,
  the two-payslip preview and the history; ⌘K rows 3380 and 3390; and a
  Vietnamese catalogue for every sentence the screens print.
  On p9clone: 80 tests green (`pb_workseg` 34 + `pb_explorer` 46) and 63
  green (`pb_decision_room`), 0 failed and 0 errors in both; `pb_group` 34
  and `pb_scheme_map` 31 green in the combined 184-test run. The 12 errors
  that run reports in `pb_payrun_wizard` are the SAME 12 the ledger has
  recorded since P2 as p9clone data drift — `prepare_run` answers
  "this month's payroll already exists" on a clone that has it, so the
  test's `prep['adopted']` is not in the payload — and they predate this
  phase.
  Persons bootstrapped: payobook 4,561 · abm 153 · payobook_template 1 ·
  p9clone 4,562. Segments, charges and companies with day-based joiner pay:
  ZERO on all four. The module ships inert.
  The hook is on BOTH compute paths (GR36): the payslip's own input builder
  and the import batch's, over one body, so a run built from an uploaded pay
  file honours a split month too.
  `pb.fact.emp.charged_from` is written only where the two entities keep
  their books in the same money — a charge carries the PAYER's currency and
  a fact row carries its company's, and printing one as the other is a lie
  no rate badge can repair (rule 7). `charged_to`, on the payer's own rows,
  is always right.
  **T1 parity (GR33's shape): 902 Retail End-Month payslips computed twice
  inside one savepoint, hook live and hook neutered — ₫14,768,030,400 both
  times, 0 of 902 differing.** Run BEFORE anything was built on the hook and
  again AFTER every change this phase made; both runs identical, both left
  0 scratch rows. On payobook and abm five existing computed payslips were
  re-read after the install and came back to the digit
  (payobook 144,281 ₫15,245,550 · 144,280 ₫16,996,050 · 144,279
  ₫14,583,875 · 144,278 ₫27,767,200 · 144,277 ₫17,600,400).
  Timings on company 5 (4,533 people): the full 902-payslip compute
  **288.8 s** with the hook live and **430.1 s** with it neutered (the
  difference is warm caches, not the hook); the Assignments screen reads in
  **under 200 ms**; both payslips preview in about 20 s, which is two real
  payroll computes.
  On p9clone the rehearsal proved the whole story end to end: one person
  with a Vietnam home and a Singapore host employment, ten days in one
  stretch and four in another, ₫43,749,067 and S$3,335,066 under "each
  entity pays its own days", and ₫62,389,245 plus "₫11,343,488 charged to
  Payobook Singapore Pte Ltd" under "home pays". A real September run for
  the pair wrote basic pay of ₫129,800,000 → ₫70,800,059 and S$8,000 →
  S$5,091, each with its own `basis='segment'` proration row and its own
  sentence; the Explorer then read the person ONCE and the full-time
  equivalents as **0.36 in Vietnam + 0.64 in Singapore = 1.00**. The
  Decision Room read **4,534 people · 4,533.4 full-time · 1 person is paid
  in two places this month**. Previewing both payslips left **0** payslips
  behind.
  Note for a later phase: the full-time figure follows PRESENCE (where the
  person was), and the money follows the PATTERN (who pays). Under "home
  pays" those two deliberately differ, and both are right.
  B1–B10 walked on p9clone, payobook and abm at 1440 and 390.
  Screenshots: `docs/handovers/group_p5_shots/`.
  Owner debts: the p9clone rehearsal (a group, a copied Singapore scheme,
  one host employment and two stretches of days) was deleted afterwards and
  verified gone; every temporary validator is archived again; the `pbim`
  kit still has no dark palette (GR38), so "dark" means the platform's
  chrome only.
- P6a — "Pay, part one: bands and fairness" — designed and BUILT 2026-09-08
  (`GROUP_P6A_PAY_BANDS_AND_FAIRNESS.md`). Status: **COMPLETE**.
  `pb_pay` 19.0.1.0.0 live on p9clone, payobook, abm and
  payobook_template; `pb_contracts` 19.0.1.4.0 (the drawer reads the band
  and the position, and names the old grade fields nowhere),
  `pb_import_kit` 19.0.1.16.0 (`scale`, `userPlus`). All three module
  trees verified byte-identical to the repository on the server, and every
  manifest version verified against `ir_module_module.latest_version` on
  all four databases.
  Shipped: `pb.pay.family` / `pb.pay.band` (min ≤ mid ≤ max, no two
  ranges over the same days, chatter on the three amounts) /
  `pb.pay.band.job` (one band per job at a time) / `pb.pay.position` (a
  DERIVED table rebuilt in one SQL statement, the job read as
  `COALESCE(c.job_id, v.job_id)` so both databases answer, the person
  carried where `pb_workseg` is installed); read-only `pb_band_id`,
  `pb_position_pct` and `pb_band_state` on `hr.contract`, computed and
  stored nowhere; `pb.pay.bands` with the band picture, the five health
  cards each carrying its own definition, `move_edge` (dry run, commit,
  and the three previous numbers for an exact Undo), `place_hire`,
  import with a per-row preview, export, `suggest_families` and
  `suggest_bands`; `pb.pay.fairness` computed on every read and stored
  nowhere, with the weighted median gap level-by-level, by level, by
  division, the same-job spread, who is paid least for the same work
  (names gated), the five-person floor, the two-currency refusal through
  `pb.fx`, and a self-contained printed statement; the Pay lens on the
  People hub at sequence 45 (Bands · Fairness live, Review · Changes
  greyed "soon"); ⌘K rows 3400 "Pay bands", 3410 "Fairness", 3420 "Place
  a new hire"; an idempotent migration from `wfp.pay.grade`; and a
  299-term `vi_VN.po`.
  **THE EMPTY STATE IS A PROPOSAL, NOT A TUTORIAL.** A company that has
  never written a band opens the screen and sees its OWN bands already
  drawn from the wages it already pays, dashed and saved only on "Use
  these" — 21 bands over 4,500 people on Payobook Vietnam JSC, 29 over
  152 on AB Mauri. Nothing is written until somebody presses the button,
  which is what let this phase validate the hero on production without
  leaving a row behind.
  56 `pb_pay` tests green on p9clone (T1–T11). The wider run over 288
  tests (`pb_contracts` 48, `pb_explorer` 50, `pb_group` 34, `pb_hub` 34,
  `pb_people_hub` 37, `pb_scheme_map` 31, `pb_workseg` 38) reports 3
  failures and 0 errors — and a CONTROL run with `pb_contracts` reverted
  to HEAD reports the SAME three (`pb_contracts`
  `test_22_the_picker_is_whitelisted`, `test_05_the_picker_is_whitelisted_and_answers`,
  `pb_group` `test_t9_the_screen_counts_what_the_roster_counts_and_is_quick`).
  They are p9clone data drift and predate this phase; zero regressions.
  Timings on company 5 (4,517 open contracts): the position pass
  **227 ms** for every company and **217 ms** for company 5 alone, well
  under the two seconds the handover asked for; **477 ms** once bands
  exist; the band board **411–671 ms** (halved from 1,070 ms by handing
  the positions and the tenure query down to the health cards rather than
  reading them twice); fairness **144 ms** over 4,510 people.
  Positions built on install: payobook 4,517 · abm 152 ·
  payobook_template 0 · p9clone 4,517. Migration: **0 grades → 0 bands**
  on every database — `wfp.pay.grade` is empty everywhere, so the
  migration is proven by T9's fixture (a grade created on p9clone became
  a band under family "Migrated" at the right level and midpoint, and a
  second run made nothing new) rather than by production data.
  On p9clone's copy of company 5, with the suggested bands accepted:
  **352 paid below the band, 537 above, 198 newer people paid more than
  the middle of the long-serving, 0 managers paid less than a report, 5
  bands at least twice as wide as their floor**; the hero read
  "₫2.4B a year to bring 24 people back in" while the edge was held, saved
  on release (47M → 61.3M), and Undo put all three numbers back exactly.
  Fairness on the same company: **"Women earn 2.4% less than men doing
  work at the same level"**, measured on 4,510 people from the November
  2026 payroll, 1,662 women and 2,840 men. On payobook, with no bands, the
  same question falls back to job-by-job and answers **0.5%**, with the
  six group divisions ranging from −7.8% (Manufacturing) to +20.8%
  (Technology). On abm, 152 people have no gender on record, so the gap
  says "not enough people to compare fairly" and the card explains why.
  In group mode on payobook the screen keeps VND's 4,510 people, names
  SGD as left out, and refuses to invent a rate (GR9 — there is genuinely
  no SGD→VND rate on that database).
  B1–B9 walked on p9clone, payobook and abm at 1440 and 390, in English
  and Vietnamese. Screenshots: `docs/handovers/group_p6a_shots/`.
  The p9clone rehearsal (21 accepted bands, 11 families, 30 job links,
  2 imported bands) was DELETED afterwards and verified gone; every
  production database carries **0 bands** and the derived positions only.
  Owner debts: the payobook admin password in this ledger is still wrong
  (GR24) — P6a used temporary `group.p6a@payobook.com`,
  `group.p6a.reader@payobook.com` and `group.p6a.vi@payobook.com`, all
  archived again (payobook 4411/4412/4413, abm 250, p9clone
  4024/4025/4026); the p9clone validator was granted
  `hr_contract.group_hr_contract_manager` for the contract-drawer walk
  and is archived; NOTHING was written to payobook, abm or
  payobook_template beyond the module install and its derived position
  rows, so the demo company still has no pay bands and the screen opens
  on the suggestion; the `pbim` kit still has no dark palette (GR38).
- P6b — "Pay, part two: review, changes, and the old module retired" —
  designed and BUILT 2026-09-08 (`GROUP_P6B_PAY_REVIEW_AND_RETIRE.md`).
  Status: **COMPLETE**. `pb_pay` 19.0.2.0.0, `pb_budget` 19.0.2.0.0,
  `pb_people_hub` 19.0.2.0.0, `pb_decision_room` 19.0.4.2.0, `pb_lifecycle`
  19.0.1.3.0, `pb_hr_flow` 19.0.1.2.0, `pb_pip` 19.0.1.1.0, `pb_probation`
  19.0.1.1.0 — all eight live on p9clone, payobook, abm and
  payobook_template, every manifest version verified against
  `ir_module_module.latest_version` on all four. `pb_import_kit` UNCHANGED:
  every icon this phase needed was already in the shared set.
  Shipped: `pb.pay.guidance` (+ cells) — how well somebody did across, where
  their pay sits down, born seeded so a new grid answers rather than reading
  zero, and sized from the scores the company already holds;
  `pb.pay.rating` (one per person per review, typed, pasted with a preview,
  or read in, plus the legacy snapshot); `pb.pay.review` (+ lines + limits) —
  a worksheet that OPENS FULL with a suggested rise on every row, a budget
  meter, a live fairness line, five kinds of self-explaining limit and a
  "what stops approval" panel; the four-signature cascade on
  `biz.approval.chain.mixin` with a real task raised for the next person and
  a Drop that is logged rather than a delete; calibration (a dot per person,
  jittered, draggable, outliers ringed on two tests); `pb.pay.apply` — one
  preview, one write, one row per contract holding the old figure, letters
  through `pb.hr.letter`, and a full undo for 24 hours; `pb.pay.change` for a
  promotion or a correction between reviews, refused while a review is open
  for that person; `/my/pay` "Your pay, explained" on the portal kit;
  `pb.pay.settings` per company; `pb.pay.retire` — a ten-check pre-flight
  gate and the sweep that follows the uninstall; ⌘K rows 3430 "Pay review",
  3440 "New pay change", 3450 "Waiting for my approval".
  `pb.budget.line` REPLACES `wfp.budget.actual`: the budget row came home,
  all seven writers, both readers, five record rules (new xmlids, because a
  `noupdate` record is never rewritten) and four views repointed, with a
  migration that moved every row and proved the totals.
  The People hub's Plan lens is now a MOUNT POINT: the seven legacy cards and
  the "Classic planning tools" fold are gone, the gate is the planning room's
  own roles, and `pb_hr_workforce_planning` is in no manifest.
  Migration parity, per database: payobook 332 budget rows moved,
  ₫1,667,834,296,228 on both sides, 2 performance scores kept, 0 matrices,
  0 cycles, 0 guardrails; abm 10 rows, ₫1,818,376,130 both sides, 0 of
  everything else; payobook_template 0 of everything; p9clone 332 rows and
  the same total. The pre-flight gate answered "everything has been carried
  across" on all four, on all ten checks.
  **`pb_hr_workforce_planning` is UNINSTALLED on p9clone, payobook, abm and
  payobook_template.** Zero `wfp_*` tables remain on any of them, zero
  tracebacks in any uninstall log, and the Budget screen reads the same to
  the digit before and after (payobook: 2.0tn budgeted, 1.7tn spent, 348.4bn
  left, 83% against 67% of the year).
  Tests: 203 green on p9clone before the uninstall (`pb_pay` 103 incl. the
  new `test_pay_review.py`, `pb_decision_room` 71, `pb_people_hub` 33,
  `pb_budget` 26) — 0 failed, 0 errors. The wide run over 410 tests reports
  the SAME 3 failures the P6a entry recorded as p9clone data drift
  (`pb_contracts` ×2, `pb_group` ×1) and nothing else: zero regressions.
  Timings: a review of 902 people on payobook built in **2.6 s** and opens in
  **162 ms** server-side; 4,510 people on p9clone built in **10.3 s** and
  opened in **575 ms**; 450 rows renumbered in one gesture in **2.3 s**;
  apply over 4,312 contracts **78 s** and undo **52 s**, both to the digit.
  On payobook the Retail scheme review narrows to exactly **902 people**
  through the scheme map, proposes **₫7.0B of a ₫15B budget** and says
  "this review widens the gap in Payobook Retail — End-Month Payroll from
  0.4% to 0.6%" — the number a pay round most needs to be told and never is.
  B1-B10 walked on p9clone (every write flow, including apply and undo over
  4,312 contracts and the portal page), payobook and abm (read and preview
  only) at 1440 and 390. Screenshots: `docs/handovers/group_p6b_shots/`.
  The p9clone rehearsal — one guidance grid, three reviews, one applied pay
  change, 4,312 applied wages and 25 letters — was UNDONE and DELETED
  afterwards and verified gone (the rehearsed wage is back at ₫9,396,000);
  payobook and abm carry **0 reviews, 0 guidance grids, 0 ratings, 0 pay
  changes and 0 applied rows** — nothing was written to production beyond the
  module upgrade, the budget rows coming home and the two performance scores
  being kept.
  Owner debts: the payobook admin password in this ledger is still wrong
  (GR24) — P6b used temporary `p6b.hr@`, `p6b.finance@`, `p6b.ceo@`,
  `p6b.vi@` and `p6b.me@payobook.com`, all to be archived; the `pbim` kit
  still has no dark palette (GR38); the six "Planning and pay" cards in the
  old flow menu now point at the Decision Room and the Pay screens rather
  than at the retired ones; `hr.employee.pb_performance_rating` is now shared
  with `pb_demo` (GR47).
- P7 — "Visibility, Vietnamese, closeout" — designed and BUILT 2026-09-08
  (`GROUP_P7_VISIBILITY_VIETNAMESE_CLOSEOUT.md`). Status: **COMPLETE**.
  `pb_group` 19.0.2.0.0, `pb_scheme_map` 19.0.2.0.0, `pb_explorer`
  19.0.2.2.0, `pb_decision_room` 19.0.4.4.0, `pb_workseg` 19.0.1.1.0,
  `pb_pay` 19.0.3.0.0, `pb_insights` 19.0.5.1.0, `pb_import_kit`
  19.0.1.17.0 (`eye`, `grip`), `pb_formula_studio` 19.0.1.180.0 — all nine
  live on p9clone, payobook, abm and payobook_template, every manifest
  version verified against `ir_module_module.latest_version` on all four and
  every module tree verified byte-identical to the repository on the server.
  Shipped: **`pb.group.visibility`** — one named person, one scope
  (Everything / one country / one company / one division), narrowing only and
  never widening (every answer intersected with `res.users.company_ids`); the
  `pb.group.scoped` mixin that every GROUP facade now inherits, so there is
  ONE definition of what somebody may see; three computed, unstored fields on
  `res.users` and four global record rules of the same two-branch shape
  (`pb.division.link`, `pb.pay.review.line`, `pb.work.segment` +
  `pb.cost.transfer`, `pb.decision.plan` via a new derived
  `pb_division_id`); a dead scope falling back to everything the person could
  see before, with a warning for the administrator; and the **"Who sees what"
  card** whose right half is the hero — pick a person and it says, in one
  sentence, exactly what they would see, before anything is saved.
  **THE PROMISE, TEST-ENFORCED: a person with no row is narrowed by nothing
  at all** — on the helper, on the rules and on every facade
  (`test_t1_nobody_is_narrowed_until_somebody_says_so`,
  `test_t2b_an_everything_reader_is_unchanged`,
  `test_t2c_every_group_facade_narrows`).
  The seven polish items: bulk attach in the department picker (tick many,
  one call, a footer that counts the people and the moves first); the scheme
  wires as a GESTURE (drag a team onto a scheme, hover or tab a line to trace
  it, pull a line off onto a `position: fixed` bar, every one with a keyboard
  equivalent written on the screen); a "look inside Retail → departments" cue
  on Explorer bars with an animated descent and real focusable doors over the
  canvas; the Decision Room dock as cards below 1200 px and pinned actions
  above; a live estimate under the Assignments month strip while dragging,
  each entity in its own money and never a total; "Fit to this family" and
  "Dense rows" on Pay Bands; and the review worksheet's chips under the
  person's name, the table measuring 1,282 px inside a 1,282 px canvas at
  1440 with no column dropped.
  Vietnamese: **100% of every exported term**, with the `.pot` now COMMITTED
  beside each catalogue and a completeness test in each module comparing the
  two — `pb_group` 332, `pb_scheme_map` 149, `pb_explorer` 230, `pb_workseg`
  237, `pb_pay` 761, 0 survivors each, 0 lost placeholders, 0 fuzzy, and the
  word "Odoo" in no translation anywhere.
  Tests: **892 on p9clone across ten modules** (`pb_formula_studio` 410,
  `pb_pay` 108, `pb_decision_room` 71, `pb_explorer` 55, `pb_group` 54,
  `pb_contracts` 48, `pb_workseg` 43, `pb_scheme_map` 36, `pb_hub` 34,
  `pb_people_hub` 33) with **5 failures, every one pre-existing p9clone data
  drift**: the three the ledger has recorded since P6a (`pb_contracts` ×2,
  `pb_group` `test_t9`) and two in `pb_formula_studio`
  (`test_07a2_the_board_opens_on_a_connector_that_HAS_rules`,
  `test_03j_the_run_lane_is_a_ghost_when_nothing_was_processed`) that a
  CONTROL RUN with `mapping_studio.xml` reverted to HEAD reproduces exactly.
  Zero regressions.
  Proven live on p9clone, same database, same minute: a division head reads
  **902 people, one division, one company, 5 departments and 5 Explorer
  series**, and the "Everything" reader reads **4,533 people, 6 divisions, 30
  departments and 24 series** — and the preview said 902 before either was
  opened. The Decision Room answered the division head **"You plan Retail",
  902**. On payobook, country HR held to Vietnam reads one company and the
  sentence "You are seeing Vietnam only."
  Timings: a full fact rebuild on p9clone **112.2 s** (45 runs, 6,158 T1 rows,
  197,834 T2 rows); a 902-person review built in **2.3 s**; the Group screen,
  the scheme board and the Pay screens unchanged.
  B1–B12 walked on p9clone (every write flow, both gestures, the bulk attach,
  the live estimate, the band toggles and the worksheet), payobook and abm at
  1440 and 390, in English and Vietnamese. Screenshots:
  `docs/handovers/group_p7_shots/`. Closeout:
  `docs/handovers/GROUP_CLOSEOUT.md`.
  The p9clone rehearsal — a group, eleven divisions and their links, twelve
  accepted map lines, one drag-created attachment, one 902-person review and
  five validators — was DELETED afterwards and verified gone (0 groups, 0
  divisions, 0 links, 0 assignments, 0 reviews, 0 visibility rows, company 6
  archived again). **payobook, abm and payobook_template carry 0 visibility
  rows**: nothing was written to production beyond the module upgrade.
  Owner debts: the payobook administrator password in this ledger is still
  wrong (GR24) and so is abm's (WF15) — P7 used `p7.ceo@`, `p7.country@`,
  `p7.head@`, `p7.me@` and `p7.vi@payobook.com`, all archived again on all
  three databases; `pb_insights` narrows by COMPANY and by its department
  leaderboard but has no division dimension of its own, so a division head
  inside a single company reads that board at company level (recorded as a
  deviation in the P7 report and as a Phase 8 candidate); the `pbim` kit
  still has no dark palette (GR38), which is a platform release of its own;
  and the two `pb_formula_studio` drift failures above are now part of the
  p9clone baseline.
