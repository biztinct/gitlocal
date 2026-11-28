# FILTER wave 6 — Payroll B + data (Ledgers, Records Desk, Statutory data, Import batches, Integrations)

Read first: `FILTER_LEDGER.md`, `FILTER_WAVE_COMMON.md`, INVENTORY.md §20,
§22, §24, §31, §32, §33. Wave id `w6`, stage `/tmp/pbf_stage_w6`, preview
holder `w6`. Report: `docs/handovers/filter/FILTER_W6_REPORT.md`.

### 1. Import batches — `pb_import` (§33)
- `_pbf_model='hr.payroll.import.batch'`, screen `import`, base = company.
- PIN `state`, PIN `source` (`source_type`), PIN `period` (`date_from`,
  past); `scheme` (`formula_config_id`), `connector`, `company`, `country`
  (`country_code` char), `errors` (choice `error_lines > 0`), `run` (choice
  `payslip_run_id` set/none), `one_time` (choice), `created`.
- Views: All · Needs attention (state error OR error_lines > 0) · In progress
  (`IN_PROGRESS` states) · Done this month · Drafts.
- QuietGlance/QuietSteps read kit counts (R1); the 20-row cap goes (page 60).
  Embedded in the Pay Run hub lens: no title (W17).
- Learn: `im-batches` → the layout's `coach`; replica strip.

### 2. Pay-run ledgers — `pb_payrun_ledgers` (§20)
- One generic component, three data models: give each of `pb.fullfinal`,
  `pb.proration`, `pb.retro` the mixin (three small implementations, shared
  helpers in the module), screens `fullfinal` / `proration` / `retro`. The
  hub `tabs` switch re-creates the kit (`reconfigure({model})`).
- Sections per §20's table (status as choice; department; scheme; when;
  component; batch; source; check; mine = F&F `seat_user_ids` many2many
  LAST hop → `type:'many2one'` path OR a choice `[('seat_user_ids','in',[uid]),('state','=','pending')]`;
  job; money (number); company).
- Views as §20. Steps on F&F → kit counts + `toggleFilters`. KPI press →
  `toggleFilters`. `rowAction` reloads the page, not the whole board.
- Learn: `lg-facets` → the layout's `coach` (shared by three screens);
  replica `ledgerHTML()` strip.

### 3. Records Desk — `pb_records` (§22)
- Already server-paged: the job is to swap the WHO rail for
  `<PbFilterLayout>` and map `pbf_domain` into `_people_domain`.
  `_pbf_model='hr.employee'`, screen `records`, base = company + active.
- Sections MIRROR Employees (`pb_people._pbf_spec`) so the same words
  appear: import the spec from `pb.people` (call
  `self.env['pb.people']._pbf_spec()`) and add `picked` (hidden arrival
  section: choice `id in employee_ids` via `initial`) and `employment`
  (choice with `domain_method` = the pay-feed signal ids, computed ONCE per
  request over the base domain — RD11 incident: never per person; time it).
- Views: All people · Running contracts · No contract · Resigned per feed · Hand-picked (transient, only when arriving with ids).
- Bulk: "Set for all N shown" = page; "select all matching" → the existing
  `matching_ids` now takes the kit's `filters`/`search` and runs `pbf_domain`.
  Export reads the same.
- Learn: `rd-who` stays as the layout's `coach`; replica `records()` rail.

### 4. Statutory › Data — `pb_statutory` (§24) — Data view only
- Ruling R5: the Insurance/Tax rosters (tax = union of two models) stay as
  they are; convert the DATA view's four tables with `ctx: {kind}` on
  `pb.statutory`: `policy` → `vietnam.insurance.policy`, `tax` →
  `vietnam.tax.table`, `adjustment` → `vietnam.insurance.adjustment`,
  `dependent` → `vietnam.employee.dependent`; `_pbf_screen()='statutory:<kind>'`;
  `_employee_scope` (W97) carried into the base domain for adjustments/dependents.
- Sections per §24; views per §24. Tab switch → `reconfigure`.
- Learn: `st-data` anchor stays; add `coach="'st-data-filters'"`; replica
  `statutory()` draws the data strip if it draws the Data view (check).

### 5. Integrations — `pb_integrations` (§31 Connectors + §32 Data)
- Connectors (R3: convert): `_pbf_model='hr.integration.connector'`,
  screen `connectors`, base `[]` with `active_test=False` in `_pbf_records`
  context. PIN `status` (`connection_status`), PIN `type`
  (`connector_type`), PIN `synced` (`last_sync`, past; none "Never synced");
  `company`, `country`, `sync_result`, `auth`, `feeds` (number), `active` (choice).
  Views: All · Needs attention · Never synced · Synced today · Spreadsheet feeds.
  `get_board` keeps shipping `composerConnectors` (R4).
- Data (three models, `ctx: {kind}` as `LEDGERS`): screens
  `integrations:mapping|store|rule`; sections per §32; the connector /
  data_type / endpoint deep-link scopes become `initial` filters (droppable
  chips). Views for the store per §32; mappings: Active · Severed · With a
  transform error; rules: Active · Failing.
- `ig-data` is a live anchor missing from `anchors.json`: declare it (and
  `ig-filters` → the layout's `coach` on Connectors). Delete the module's
  `_facets` copy.

## Wave-specific tests
- W6-T1 Records Desk: "select all matching" with two filters → the ids
  count equals the kit's matched count; `employment` section timed (ms).
- W6-T2 Ledgers: switch F&F → Proration → Retro in the Pay hub; each keeps
  its own filters; a saved view on F&F does not appear on Retro.
- W6-T3 Import: the glance "errors" figure equals the Needs attention view.
- W6-T4 Statutory Data: adjustments as a user outside `_employee_scope`
  (preview) see only their scope in counts and rows.

## Report back
`FILTER_W6_REPORT.md` per `FILTER_WAVE_COMMON.md §E`.
