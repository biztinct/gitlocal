# RECORDS Phase R2 — the Records Desk (bulk update over the scheme's mapped fields)

Program: RECORDS. Phase 2 of 3. New module **`pb_records`**; small doors in `pb_people` and
`pb_people_hub`. Read `docs/handovers/RECORDS_LEDGER.md` (standing rules + any `RD` entries R1
added) and CLAUDE.md's deploy contract first. R1 (`RECORDS_PHASE_R1_ONE_TIME.md`) is complete and
committed; do not touch its files.

## The ask (owner's words, 2026-08-29)

> "An easy way to update the Payobook employee/contract/bank etc details or fields in bulk. These
> fields are the ones which are mapped. … if I want to update SHUI to yes for all the employees OR
> selected employees after doing a search e.g. for Department/Designation, I should be able to do
> that. Also should be able to do it individually as well."

Owner rulings: contract fields are written **in place** on the employee's current contract (no new
contract version); the tool is its **own desk** reachable from People (R2), Mapping and the pay
run (R3); the picker offers **mapped fields only**.

## Scope

- New module `pb_records`: AbstractModel `pb.records.desk` (RPC facade), two stored audit models
  `pb.records.apply` / `pb.records.change`, one client action `pb_records_desk`, the OWL cockpit
  (`.rd-*`), a hoot test, Python tests.
- A **Records** lens in the People hub + a **Bulk update** button on the People roster's
  selection bar that opens the desk pre-filtered to the selection. A ⌘K palette row.

**Non-goals (binding):** export/import (R3); new contract versions; editing fields the scheme does
not map (the picker is mapped-only — the empty state links to Mapping); any change to
`pb_people.bulk_apply` or to the resolver/batch code; native list views.

## Design bar (binding — score the report against it)

> "Extreme WOW, intuitive, out-of-this-world experience, best in class." Every surface names its
> hero moment; zero dead-ends (empty/loading/error/partial/huge states designed, every failure
> names its reason and next step); plain language over code vocabulary; motion with purpose;
> keyboard + bulk ergonomics; measured against the best SaaS tool in the category, not stock Odoo.
> Lucide icons, never emoji. Chrome-MCP walk every flow. Never the word "Odoo" in a user-visible
> string.

**R2's hero moment:** a spreadsheet-feeling grid over real records. Pick "SHUI participation",
filter to a department, click the column header → *Set for everyone selected… → Yes*, and 140
cells flip with a staggered highlight; the Review drawer animates in with "140 changes on 140
people", every one shown as `No → Yes`; Apply; toast **"Updated 140 values on 140 people — Undo"**.
The benchmark is Airtable / Notion databases / Google Sheets, not a form view.

## Verified plumbing — do NOT re-derive

Mapping catalogue — `pb_hr_payroll_formula/models/payslip_import_mapping.py`:
`hr.payslip.import.mapping` rows: `salary_structure_id` (= `hr.formula.config`, the scheme),
`component_id` (`hr.formula.rule`), `destination_type` ∈ `field | bank_account`, `target_model_id`
(`hr.employee` | `hr.contract`), `target_field_id` (`ir.model.fields`), `bank_role` ∈
`acc_number | bank_name | bank_bic | acc_holder_name`. No unique constraint — duplicates possible;
lowest id wins (`pb_formula_studio.py:342`).

Contract components — rules with `is_contract_component` (amount) or `is_text_component` (text):
`pb_formula_studio.py:8332 _ec_component_codes(config)`; state `:8352`. Lines keyed by template
code: `payroll_import_batch.py:4653 _get_contract_advantage_map(contract)` → `{code: line}`;
`line.amount` / `line.text_value`; template `hr.contract.advantage.template` (`code`,
`value_type`); a template may not exist yet (created lazily by the first import — for the desk,
create it via `_get_or_create_advantage_template(rule, cache)` `:4626` on a probe, never flip an
existing template's `value_type`). CR18: every contract has an EMPTY seeded line per template —
existence proves nothing. Audit rows: `_log_contract_component_change` `:4664` (signature
`(contract, template, old_amount, new_amount, source, notes=None, old_text=None, new_text=None)`;
`change_source` selection has `'manual'` — use it, with `notes='Records Desk apply #<id>'`).

Field read/write pair (both are METHODS on `hr.payroll.import.batch`; call them on a probe
`Batch = env['hr.payroll.import.batch'].sudo().new({'formula_config_id': cfg.id})` — the
`preflight_spreadsheet` precedent `pb_payrun_wizard.py:899`):
- `_mapped_record_value(mapping, contract=, employee=)` `:2518` — m2o → `display_name`,
  selection → LABEL, boolean → bool, numbers → float, date → string; `None` = empty.
- `_coerce_mapped_value(record, field, value)` `:1709` — `field` is the ir.model.fields ROW;
  m2o resolved by `m2o_resolution_key(comodel)` `:62` and created only if
  `m2o_creates_missing(comodel)` `:71`; boolean from `1/true/yes/y/t`; selection validated
  against KEYS, **`None` on miss** `:1791`. **Selection labels must be turned into keys BEFORE
  calling it** — write `_selection_key(field, value)` in `pb_records`: accept a key or a label
  (case-insensitive), return the key, or `None` + a reason listing the allowed labels. Use
  `field._description_selection(env)` on the MODEL field (`record._fields[name]`), never
  `ir.model.fields.selection` (a Char — MF24, `payroll_import_batch.py:2543` note).
- Bank: `_bank_record_value(mapping, employee)` `:2570` reads `employee.bank_account_ids[:1]`;
  writing uses `_get_employee_bank_partner` `:2925`, `_resolve_bank` `:2942`,
  `acc_numbers_match` + `sanitize_acc_number` (`bank_account_util.py`), and
  `_link_employee_bank_account` `:2966` (ADD-never-replace). Assemble ALL four roles (existing +
  changed) and refuse a write when no `acc_number` results — the same rule `_sync_employee_bank_
  account` `:3014` applies. **Do not** touch the flat `hr.employee.bank_name/account_number`
  Chars unless they are themselves mapped fields (then they are ordinary `f:` columns).
- Contract to read/write: `_get_latest_contract(employee)` `:2858` on the probe (no dates set →
  latest).
- Self-assign rail (J10 §3.2): a change whose new value equals the current one is `same`, not a
  write.

Catalogue notes to reuse for card hints: `pb_formula_studio.py:8571 _ec_selection_note(field)`
(returns `{text,title,values?}`), `:8635 _ec_m2o_note(field)`, `:8664 _ec_notes_for(model)`.
`pb_formula_studio` is an optional dependency — guard with `self.env.get('pb.formula.studio')`
… actually these are `@api.model` methods on the studio's AbstractModel; check its `_name` and
call through `self.env[name]` when present, else omit the hint.

Employee filters — `pb_payrun_wizard.py:106 employment_status_options()` (merged across schemes,
`[{value,label?,count,worked}]`) and `_employee_signals()` `:86` (`{emp_id: {status,hours}}`) —
the status filter must read the FEED signal, exactly as the wizard does (`:59-62` explains why).
Departments: `hr.department`; designation: `hr.job` (and `job_title` text); contract state:
`hr.contract.state`; company: `env.companies`.

People door — `pb_people/static/src/js/people.js` select-mode state `:36`, `selected` `:137-143`;
template `pb_people/static/src/xml/people.xml` bulk bar `:27-38`. People hub —
`pb_people_hub/static/src/js/people_hub.js` lenses `:75-82` (`{key, icon, label, Component,
groups}` mounted with `embedded: true` by `HubShell`); palette rows `people_hub_palette.js:46-61`
(sequence block 1400; **door by XMLID, not tag** — W98). Hub icons must be in the fixed Lucide set
(`pb_sidebar.js`: home/calendar/users/file/file-text/calculator/layers/shield/percent/
trending-up/clipboard-check/lock/building/database/compass/settings/circle) — use `database` or
`layers` for Records.

Design kit — `pb_import_kit`: tokens `import_tokens.scss` (`--pbim-*`), primitives `import_kit.scss`
(`.pbim-*`), People layout `theme_people.scss` (root `pbim emp` = Celeste variant, see
`theme_setup.scss`), icons `import { ic } from "@pb_import_kit/js/import_icons"` (**`js/` segment
required**). Grid editing precedent: `pb_formula_studio/static/src/js/grid/grid_studio.js` —
selection `:444-607` (ctrl-toggle `:567`, shift-range `:576`, Escape `:607`), bulk `:736-755`,
paste `:868`, editor `:636`, IME `:942`; SCSS `grid.scss` `.g2-edit` `:151`, `.g2-bulkbar` `:177`.
It is column-oriented — transpose the ideas, don't fork the file.

Access precedent: `pb_audit/security/ir.model.access.csv` (payroll manager + system). Gate the
desk on `hr.group_hr_user` OR `pb_hr_payroll_base.group_payroll_base_officer` for read; writes
additionally require `hr.group_hr_user` (employee) / `hr_contract.group_hr_contract_manager`
(contract) — check the ACL of the model being written and refuse with a plain sentence rather than
letting an AccessError leak.

## Build

### Module `pb_records`

```
pb_records/
  __manifest__.py   depends: web, om_hr_payroll, pb_hr_payroll_base, pb_hr_payroll_formula,
                    pb_import_kit, pb_people, pb_people_hub  (pb_formula_studio optional)
  models/pb_records_desk.py      AbstractModel pb.records.desk
  models/pb_records_change.py    pb.records.apply + pb.records.change
  security/ir.model.access.csv
  views/pb_records_action.xml    ir.actions.client tag pb_records_desk, name "Records Desk"
  static/src/js/records_desk.js, records_grid.js, records_cells.js, records_palette.js
  static/src/xml/records_desk.xml
  static/src/scss/records_desk.scss   (.rd-*, on --pbim-* tokens, root "pbim emp rd-root")
  static/tests/records_grid.test.js
  tests/__init__.py, tests/test_records_r2_desk.py
```

### Server — `pb.records.desk` (every method `@api.model`, returns plain dicts, never raises to
the client for user mistakes — `{'ok': False, 'msg': …}`)

- `get_schemes()` → `[{id, name, mapped_count, is_default}]`; default = the config the pay-run
  gate would pick (`pb.payrun.wizard._spreadsheet_configs()[0]` when present, else the first
  active config); plus `{'id': 0, 'name': "All schemes"}` when > 1.
- `get_fields(config_id)` → `{groups: [{key: employee|contract|bank|component, label, fields:
  [card]}], statuses: [...]}`. Card = `{id: 'f:<model>:<field>' | 'b:<role>' | 'c:<CODE>', label,
  sub (component "SHUI participation ← SHUIPARTICIP"), ttype: char|text|integer|float|monetary|
  boolean|date|datetime|selection|many2one|bank|amount|text_component, selection: [{key,label}],
  m2o: {comodel, creates_missing, key}, hint: {text,title,tone}, component: {id, code, name}}`.
  `config_id = 0` unions all active schemes (dedupe by card id).
- `search_people(config_id, filters, field_ids, offset=0, limit=100)` → `{total, rows: [{id,
  name, code, avatar, department, job, contract_id, contract_state, values: {field_id: {v, label}}}],
  facets: {departments:[{id,name,count}], jobs:[…], contract_states:[…], statuses:[…]}}`.
  `filters = {q, department_ids, job_ids, contract_states, statuses, company_ids, employee_ids}`;
  `employee_ids` intersects, never overrides. `v` is the KEY/raw value; `label` the display
  (selection label, m2o display_name, formatted date). Read ONE probe, one contract lookup per
  employee, `sudo()` reads scoped to `env.companies`. Facet counts respect the other filters.
- `lookup_m2o(comodel, term, limit=12)` → `[{id, label}]` over `m2o_resolution_key`.
- `preview_changes(config_id, changes)` — `changes = [{emp_id, field_id, value}]` → `{items:
  [{emp_id, emp_name, field_id, field_label, old_label, new_label, status: 'ok'|'same'|'refused',
  why}], counts: {ok, same, refused, people}}`. Coercion via `_selection_key` then
  `_coerce_mapped_value`; booleans accept Yes/No/true/false/1/0; m2o accepts an id `{id}` from the
  typeahead or a name (then the catalogue promise applies: create-or-refuse). Refusal sentences in
  plain words: *"'Maybe' is not one of the choices — use Yes or No"*, *"No department called
  'Sales EU' exists, and departments are not created here"*, *"Bank details need an account number
  — add one in the same change"*.
- `apply_changes(config_id, changes, note='')` → runs `preview_changes` again server-side, writes
  only `ok` items inside ONE transaction, creates `pb.records.apply` `{name, user, date, note,
  source='desk', count_people, count_values}` + one `pb.records.change` per written value
  `{apply_id, employee_id, model, res_id, field_key, old_json, new_json}`; returns `{ok, apply_id,
  written, refused: [...], skipped_same}`. Employee fields → `employee.write`; contract fields →
  `contract.write` (in place); bank → assemble + link (above); components → advantage line write
  + `_log_contract_component_change(..., source='manual', notes=…)`. Use `_drop_taken_barcode`
  `:3149` when writing `barcode`. Whitelist rail: any `field_id` not in `get_fields(config_id)`
  → `UserError` BEFORE any write (the `bulk_update_components` precedent).
- `undo_apply(apply_id)` → for each change whose record still holds `new_json`, write `old_json`
  back (same routing); returns `{restored, skipped_changed_since, skipped_missing}` and marks the
  apply `undone=True` + `undone_date`. Undo is itself an apply (`source='undo'`) so it is auditable.
- `get_history(limit=20)` → recent applies with counts, user, note, undone flag.

### Client — the desk (`pb_records_desk`, props `action.params`: `config_id?`, `employee_ids?`,
`field_ids?`)

Layout (full-height, three zones; `.rd-root` on `pbim emp` tokens):
1. **Header**: title "Records Desk", subtitle *"Update the employee, contract and bank details
   your pay scheme reads — one person or hundreds at once."*, scheme pill (dropdown), History
   button, and the sticky **Review N changes** primary button (disabled at 0, pulses once when
   the count first becomes > 0).
2. **Left rail — Who** (collapsible, 280px): search box (name / code / email, debounced 250ms);
   facet chips with counts for Department, Designation, Contract state, Employment status (only
   when statuses exist), Company (only when > 1); "N people match" line; when arriving with
   `employee_ids` a pinned chip "Hand-picked · 12" that can be cleared.
3. **Top strip — What**: field cards grouped Employee · Contract · Bank · Contract components;
   click toggles a column; a card shows its hint on hover/focus; picked set remembered in
   `localStorage` per scheme (`pb_records.fields.<config_id>`). Empty state when the scheme maps
   nothing: illustration + *"This scheme doesn't map any employee, contract or bank fields yet"*
   + button "Open Mapping" (opens `pb_formula_studio`'s Mapping action when installed).
4. **Grid**: virtualised rows (windowed rendering — 4.5k people on payobook must scroll at 60fps;
   fetch pages of 100 as the window moves, keep `total`); pinned identity columns (avatar +
   name, code, department); one column per picked field; row checkbox, header checkbox =
   all-loaded, "Select all N matching" link when more than loaded; shift-click range;
   Ctrl/Cmd-click toggle; arrow keys move the focused cell, Enter/F2 edits, Escape cancels, Tab
   moves right, typing starts editing; Ctrl/Cmd-Z undo / Shift-Ctrl-Z redo (client stack of
   cell edits); paste TSV/CSV from the clipboard at the focused cell (fills down/right, only over
   editable cells, shows "Pasted 24 cells" toast). Dirty cells: accent left border + old value as
   a small strike-through under the new one; refused cells (from a live `preview_changes` run
   debounced 400ms after edits) get a red dot + tooltip with the reason.
   Cell editors by `ttype`: boolean = toggle chip (Yes/No); selection = dropdown of labels with
   type-ahead; many2one = typeahead over `lookup_m2o` (shows "Will be created" tag when
   `creates_missing` and no match); date/datetime = native date input; numbers = right-aligned
   input with thousands formatting on blur; char/text = input; amount component = number; text
   component = input; bank = text (acc_number gets `sanitize_acc_number` feedback).
   Column header menu (kebab, also via keyboard): *Set for selected… / Set for all N shown… /
   Clear for selected / Revert column / Hide column*. "Set for…" opens a small popover with the
   same editor as the cell.
5. **Review drawer** (slides from the right): summary line *"41 changes on 19 people · 2 need a
   look"*, grouped by person, each row `field: old → new`, refused rows in amber with the
   sentence, a note field ("Why? optional — shows in History"), **Apply** button (disabled while
   refused rows exist? NO — apply the ok rows and keep the refused ones in the grid; say so in
   the button: "Apply 39 · leave 2"). After apply: success toast with **Undo** (10s) AND the
   History drawer lists it with Undo forever; the grid reloads the affected rows with a green
   flash; refused cells remain dirty.
6. **History drawer**: last 20 applies — who, when, note, counts, Undo button (undo of an undone
   apply is disabled with "Already undone").

States to design: loading (skeleton rows), zero people match (offer to clear filters), zero
fields picked (grid shows identity columns + a nudge arrow to the strip), 4.5k rows, refused
value, network failure on apply (nothing written — say so), user lacks write access on a model
(cells read-only with a lock hint, not a crash), a person without a contract (contract cells
show "No contract" and are not editable).

Doors:
- People hub lens `{key: 'records', icon: 'database', label: 'Records', Component: PbRecordsDesk,
  groups: EMPLOYEE_GATE}` after Contracts; palette row `peoplehub_records` at 1440.
- People roster bulk bar: button **Bulk update** (icon `edit`) → opens the hub on the `records`
  lens with `employee_ids = state.selected` (use `openHub` from `@pb_hub/js/hub_nav` with the
  XMLID and `lens: 'records'` + params; check how HubShell forwards `action.params` to a lens and
  follow it).
- `views/pb_records_action.xml` also registers a standalone action (for deep links / R3 doors).

## Safety rails

- Nothing writes before Apply; Apply re-validates server-side; whitelist rail on field ids;
  company scoping on every search and write; ACL respected per model; audit row per value;
  Undo never overwrites a value that changed since (reported, not forced).
- `hr.payslip` is never touched: assert count + md5 of `formula_input_values` before/after the
  test suite and the live validation.
- No "Odoo" in UI; no emoji; Lucide via `ic()`; plain language on every string.

## Numbered test cases (`pb_records/tests/test_records_r2_desk.py`)

Fixtures: build a scheme + mappings the J10 way (`test_journey_j10_writeback.py:72-116`
helpers) — one selection field (`hr.employee.marital` or a real selection on hr.employee), one
boolean on hr.contract (or a Char if no boolean is mappable — verify with `_ec_is_mappable`), one
m2o (`department_id`), one bank `acc_number` + `bank_name`, one amount component rule. Three
employees in two departments, one without a contract.

1. `get_fields` returns exactly the mapped destinations, grouped, with `selection` pairs and
   `hint`; unmapped fields absent; `config_id=0` unions two schemes without duplicates.
2. `search_people` filters by department/job/contract state/q/employee_ids (intersection) and
   returns key + label for selection/m2o; the contract-less person has `contract_id=False`.
3. `preview_changes`: label → key for a selection; wrong label → `refused` with the sentence
   listing the choices; `same` when unchanged; boolean from "Yes".
4. `apply_changes` on 3 people × 2 fields writes exactly the diff; `write_date` of a fourth
   employee and of an unpicked field's sibling record unchanged; `pb.records.apply.count_values`
   correct; one `pb.records.change` per value with old/new JSON.
5. Bank apply: `acc_number` + `bank_name` create ONE `res.partner.bank` linked to the employee's
   partner; a second apply with a different `acc_number` ADDS, never replaces; `bank_name` alone
   (no acc_number anywhere) is refused with the sentence.
6. Component apply: writes the advantage line amount, creates the template if missing, logs an
   `hr.contract.advantage.change` with `change_source='manual'`; never flips an existing
   template's `value_type` (text vs amount) — refused instead.
7. `undo_apply` restores the old values; a value changed since is skipped and counted; the
   apply is marked undone; a second undo is refused.
8. Whitelist: a `field_id` not mapped by the scheme → `UserError`, nothing written (assert
   `write_date`s).
9. Company scoping: an employee of another company is neither listed nor writable.
10. Paging: 250 generated employees → `total=250`, two pages of 100 + one of 50, facets stable.
11. Payslip neutrality: `hr.payslip` count + md5 unchanged across the whole suite.
12. Source assertion: no "Odoo", no emoji in `static/src/xml/*.xml` and `models/*.py` strings.

Hoot (`static/tests/records_grid.test.js`): selection (click, shift-range, ctrl-toggle, Escape),
arrow-key focus, Enter edits / Escape cancels, paste fills a 2×2 block, undo/redo restore, "Set
for selected" fills only selected rows, dirty count feeds the Review button label.

## Deploy + verify

1. Baseline on abm first (C18.40/54): `-u pb_people,pb_people_hub --test-enable --test-tags
   /pb_people,/pb_people_hub`; then with `-i pb_records` add `/pb_records`.
2. Bump `pb_people` and `pb_people_hub` manifests (assets changed); `pb_records` is 19.0.1.0.0.
   A manifest `assets` change ⇒ full service RESTART (C18.53) + clear `/web/assets/%`.
3. Deploy abm → `-i pb_records -u pb_people,pb_people_hub` → restart → Chrome-MCP walk
   (ash@biztinct.com / J5validate!2026): open People hub → Records lens; pick the scheme; pick
   SHUI participation (or whatever abm maps — read the live mapping table first and NAME what
   you used); filter to one department; Set for selected → Yes; Review; Apply; verify by
   `call_kw` on the records; History → Undo; verify restored. Then a single-person edit via the
   cell. Then a refused value. Then the People roster → select 3 → Bulk update → desk opens
   pre-filtered. Screenshot every state; measure scroll smoothness on payobook's 4.5k roster.
   **Restore any live value you changed** and leave the audit rows (they are the proof).
4. payobook + payobook_template: install + upgrade, assets cleared, smoke the lens on both.
5. Verify tree hashes + `latest_version` on the three DBs.
6. Commit (explicit paths): `feat(records): Records Desk — bulk update of the scheme's mapped
   employee, contract and bank fields (R2)`.

## Report back (in this order)

- Test counts baseline vs after per DB; payslip md5 proof.
- Each numbered case + hoot: pass/fail with the evidence line.
- Chrome walk: the abm field you used, each state's exact strings, screenshot paths, the
  4.5k-row scroll observation, what you restored.
- Design-bar self-score (hero moment, dead-ends, plain language, motion, keyboard/bulk) and what
  you would still improve.
- `RD` entries appended to the ledger.
- Anything left out and why.
