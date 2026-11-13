# RIZE P2 — pb_assets: the asset register

Read FIRST: `docs/handovers/RIZE_LEDGER.md`. Design doc: `docs/design/rize-hrms-blueprint.html`
§05. Check the ledger phase log for P0/P1 deviations before coding (P0 defines the journey
task API and the People-hub lens pattern reference; P1 defines the after-hooks you extend).

## Scope

ONE new module `pb_assets`:
1. Asset master — tangible + non-tangible (digital) items, per-country auto asset codes,
   lifecycle states, cost in local currency + USD.
2. Assignment history (who had it, condition in/out) + transfer flow.
3. Procurement/allocation requests with approval (biz_approval_chain) and spare-pool-first.
4. **Assets lens on the People hub** (soft registry) — the world-class board.
5. Employee portal page `/my/assets` (view + confirm receipt).
6. Exit hooks: open assignments block final settlement (enforced in P4 — here we EXPOSE the
   check), digital assets get deactivation tasks on offboarding (override P1's
   `_after_offboard`).
7. Excel exports (allocation, history, inventory, per-employee, per-country).

### Binding NON-goals
- No procurement purchasing/vendor-PO flow (P11 owns vendors; `vendor_id` on asset is a
  plain optional m2o to `pb.vendor` added LATER by P11 — leave a Char `supplier_note` now).
- No laptop-journey wiring into onboarding steps (P3 does that via journey task links).
- No F&F blocking enforcement (P4) — but ship the queryable method it will call.

## Verified plumbing facts (do NOT re-derive)
- NOTHING asset-shaped exists. `hr_maintenance` is UNINSTALLABLE (depends on absent
  `maintenance`) — do not touch it.
- People-hub lens soft registry: clone `pb_records/static/src/js/records_palette.js` →
  consumed by `pb_people_hub/static/src/js/people_hub.js` `extraLenses()` — read both files
  for the exact registry category + entry shape; P0's report in the ledger may also name it.
- Cockpit canon `pb_people` (facade/_safe/companies/row-cap; action record; OWL; `pbim`
  root; `props.embedded`). Kit classes + `ic()` icon registry per ledger.
- Approval mixin: `biz_approval_chain/models/biz_approval_mixin.py` — mixin name
  `biz.approval.chain.mixin`; consumers to clone: `pb_business_trip/models/pb_business_trip.py:26`,
  `pb_bank_ocr/models/pb_bank_change_request.py:63`. Stepper widget ships with the module.
- ESS portal canon: `pb_me_portal/controllers/portal.py` (employee resolved from session
  `:28-37`, `_prepare_home_portal_values` hook `:49`); own-record rule
  `[('employee_id.user_id','=',user.id)]` + ACL row pattern
  `pb_me_portal/security/` — clone for `/my/assets`.
- XLSX export canon: `pb_hr_workforce_planning/wizards/export_wizard.py` (report_xlsx is
  vendored+installed); simpler CSV/XLSX builders also in
  `payroll_analytics_approval/wizards/payroll_bank_export_wizard.py`.
- Sequences: `ir.sequence` with per-country codes — implement
  `pb.asset` create() pulling `pb.asset.sequence.<country_code>` (create sequence on the
  fly if missing) → codes like `IN-LT-00042`: `<country>-<category code>-<number>`.
- Currency: company currency for local cost; USD = `res.currency` search 'USD'
  (`convert` at date) — display only, don't store computed USD (compute field, non-stored).
- Employee card in People cockpit: `pb_people` roster exists; do NOT modify pb_people —
  the assets lens is self-contained; employee asset list also shows on `/my/assets` and in
  the asset board's employee facet.
- P1 after-hooks: `pb.zoho.pipeline` `_after_offboard(case, rec)` — override in pb_assets
  (guard with `if 'pb.zoho.pipeline' in env` — actually use a proper `_inherit` since P1 is
  a hard install on payobook; manifest depends may include pb_zoho_bridge — decide: depends
  `['pb_zoho_bridge']` is acceptable on this DB) to create deactivation tasks for the
  employee's active digital assets. ALSO override the equivalent journey path: when an
  offboarding `pb.journey.case` opens (P0 `action_open`), append per-asset return tasks —
  implement as an extension hook: inherit `pb.journey.case.action_open()` and, for
  case_type='offboarding', add one `pb.journey.task` per open assignment
  (name "Return: <asset>", blocking_ff=True) and one per active digital asset
  ("Switch off: <asset>").

## Architecture

### Models
**`pb.asset.category`** — name, code Char(2-4, used in asset code), kind Selection
`[('tangible','Physical'),('digital','Digital')]`, auto_assign_at_joining Boolean,
icon Char (ic() key), active, company_id optional. Seed: Laptop LT, Phone PH, SIM SM,
ID card ID, Credit card CC, Monitor MN (tangible); Email EM, System login LG,
Software licence SW, Phone number PN (digital).

**`pb.asset`** — mail.thread. code Char readonly (auto), name, category_id required,
kind related stored, country_id (res.country, required — drives code prefix),
company_id, state Selection tangible
`[('spare','Spare'),('assigned','Assigned'),('repair','Under repair'),
('to_scrap','To scrap'),('scrapped','Scrapped')]` / digital uses
`[('spare','Available'),('assigned','Active'),('deactivated','Switched off')]` — ONE
selection with all values, constrained per kind; current_employee_id computed from open
assignment (stored); serial Char (serial no / email address / number / licence key),
model_name Char, is_reused Boolean, purchase_date, delivery_date, warranty_end Date,
cost Monetary + currency_id (default company currency), cost_usd computed non-stored,
invoice_ref Char, supplier_note Char, movable_note Char, notes, active.
`_compute_display_name` → "CODE — name".

**`pb.asset.assignment`** — asset_id required index, employee_id required index,
assigned_date, returned_date, condition_out Char, condition_in Char,
receipt_confirmed Boolean, receipt_confirmed_at, state Selection
`[('open','With employee'),('returned','Returned')]`, assigned_by, notes, company_id.
Constraint: one open assignment per asset (models.Constraint or python constrains).
`action_return(condition_in)` → closes + asset back to 'spare' (tangible) with a chatter
note on the asset.

**`pb.asset.request`** — mail.thread + `biz.approval.chain.mixin`. employee_id (or
candidate_name Char when pre-DOJ and no employee yet — keep simple: employee_id required;
P3 creates employees before the laptop step), category_id, needed_by Date, country_id,
justification, spare_asset_id m2o (auto-suggested via `_find_spare()` — oldest spare of
category+country), state (mixin-driven) + fulfilment Selection
`[('todo','To arrange'),('spare','Assign from spares'),('buy','Buy new'),
('ready','Ready'),('delivered','Delivered'),('confirmed','Confirmed by employee')]`,
asset_id (the one finally assigned), journey_task_id optional (P3 links).
`action_fulfil()` assigns the chosen asset (creates assignment).

**Exit-check service**: `pb.asset` @api.model `open_items_for(employee_id)` →
{'tangible': [...], 'digital': [...]} — P4 calls this to block F&F; also used by the
board's "leaver check" chip.

### Assets lens (People hub) + cockpit
Facade `pb.assets` AbstractModel: `get_board()` → kpis (total, assigned, spare,
under repair, digital active, leavers holding assets), facets (country, category, state,
kind), rows cap 400 {code, name, category, kind chip, state chip, employee, country,
cost, warranty flag}; `get_asset(id)` → header + assignment timeline + request history;
actions: `assign(asset_id, employee_id, condition)`, `return_asset(assignment_id,
condition)`, `transfer(asset_id, to_employee)` (return+assign one step),
`set_state(asset_id, state)`, `create_asset(vals)`, `export(kind)` → xlsx download.
OWL cockpit `pb_assets` tag: hero + KPI stats, filter chips, table with state chips,
row → drawer (timeline of holders, condition trail, actions), "Add asset" +
"New request" dialogs, bulk select → bulk state change/export. Empty states teach.
Register as People-hub lens "Assets" (icon package) via the soft registry + ⌘K deep links
("Assets", "New asset request") in the 2200 range. NOT a rail item.

### Requests screen
Native list+form (VU-skinned) for `pb.asset.request` with the approval stepper widget —
clone the business-trip views. Reachable from the cockpit ("Requests" segment) via an
act_window record + from ⌘K.

### Portal `/my/assets`
Route (auth='user', frontend assets, clone pb_me_portal controller pattern): list my open
assignments (code, name, since, condition) + my digital assets; button "Confirm receipt"
on unconfirmed assignments (writes receipt_confirmed). Card added to `/my` home counters
via `_prepare_home_portal_values` (clone pb_me_portal `:49`). Own-record ir.rule on
pb.asset.assignment for portal/internal users + minimal ACL (read) — model-level write
stays closed; confirm goes through a controller `sudo()` scoped write (route-boundary
pattern), matching pb_ess_workforce security doctrine.

### Security
Groups: `group_assets_user` (read board), `group_assets_manager` (implied user; full CRUD +
approvals), wire into lifecycle admin: `pb_lifecycle.group_lifecycle_admin` implies
assets manager (read pb_lifecycle security xmlids from the P0 code). ACLs all models;
company ir.rule; portal own-record rule as above.

## Safety rails
- Don't modify pb_people / pb_people_hub source — registry-only integration.
- Additive inherit of pb.journey.case only (one method extension, guarded, super() first).
- Test records: create assets under a "RIZE-TEST" naming and clean up after tests
  (or deactivate); use existing demo employees for assignment tests — do NOT create
  throwaway employees.
- Deploy `-i pb_assets` (+ `-u` nothing unless you edited P0/P1 files) per ledger.

## Numbered test cases
T1. Deploy clean; registry loads.
T2. People hub shows the new "Assets" lens; opens the board; light+dark screenshots.
T3. Create categories exist (seeded); create a Laptop asset in Vietnam → code
    `VN-LT-00001` style; second → 00002; an India one starts its own sequence.
T4. Assign to a demo employee → state Assigned, employee shown, timeline entry; transfer
    to another employee → first assignment returned-with-condition, second open.
T5. Return → asset Spare again; condition trail visible in drawer.
T6. Request flow: create request needing approval → approve via stepper → fulfil from
    suggested spare → Delivered; the suggested spare was the oldest matching spare.
T7. Digital asset: create Email asset, assign; open an OFFBOARDING journey case (P0) for
    that employee → return/switch-off tasks auto-appended, blocking_ff on the tangible
    return; `open_items_for()` returns both.
T8. `/my/assets` as the demo employee's login (or a test portal user linked to an
    employee): sees own assets only; Confirm receipt works; another user's assets
    invisible.
T9. Exports: inventory + per-employee XLSX download open in a spreadsheet with sane
    columns.
T10. Bulk: select 3 assets → bulk state change works.
T11. White-label grep zero; plain-English labels; no emoji.
T12. P0 regression: Journeys cockpit still loads; an onboarding case opens fine (no
    interference from the case_open inherit).
T13. Tidy up test records; report what remains.

## Deliverables / report back
Commits (explicit staging), per-test results, deploy EXIT, deviations, ledger gotchas
appended, exact lens-registry entry + palette sequences used, the `open_items_for` API
signature confirmed for P4, and the journey-task auto-append behaviour documented for P3.
