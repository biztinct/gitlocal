# FILTER wave 5 — Payroll A (Pay Runs, Payslip review, Salary Structures)

Read first: `FILTER_LEDGER.md`, `FILTER_WAVE_COMMON.md`, INVENTORY.md §18, §19, §23.
Wave id `w5`, stage `/tmp/pbf_stage_w5`, preview holder `w5`.
Report: `docs/handovers/filter/FILTER_W5_REPORT.md`.

### 1. Salary Structures — `pb_structures` (§23) — warm-up
- `_pbf_model='hr.payroll.structure'`, screen `structures`, base `[]` (no
  company domain, by design — keep).
- PIN `status` (`structure_state`, fallback `active`), PIN `country`
  (`payroll_country_code` char, or `country_id`), PIN `schedule`
  (`schedule_pay`); `company`, `base` (choice `is_base_structure`),
  `currency`, `formula` (choice `use_formula_computation`), `contract_type`
  (`contract_type_ids`, many2many LAST hop → allowed as `type: 'many2one'`),
  `parent`, `employees` (number), `updated` (`write_date`, past).
- Views: All · Active · Drafts · Deprecated · Updated this month.
- Glance Active/Draft/Deprecated → `toggleFilters`.
- Learn: `sr-filters` → the layout's `coach`; replica `structures()` strip.

### 2. Payslip review — `pb_payslip_review` (§19)
- `_pbf_model='hr.payslip'`, screen `payslips`. The run picker stays as the
  screen's scope control above the panel; pass `ctx: {run_id}`;
  `_pbf_base_domain` = `payslip_run_id = run_id` + active companies;
  changing the run → `kit.reconfigure({ctx:{run_id}})`.
- PIN `status` (choice folding verify/level1/level2 into "Waiting for
  approval"; draft; done; cancel), PIN `review` (choice via `domain_method`:
  "Needs review" = ids from `run.pb_review_flags()` — one call per request,
  cached on the model for the request; time it on a 900-slip run), PIN
  `department` (`employee_id.department_id`); `job` (`contract_id.job_id`),
  `structure` (`struct_id`), `company`, `paid` (choice), `refund` (choice
  `credit_note`), `period` (`date_to`).
- Views: All in this run · Need review · Waiting for approval · Done · Refunds.
- Net pay: no stored net (R2) → no number section; debt note.
- The detail pane auto-selects the first flagged slip: after each page load
  re-select the first row of the page if the current one is not in it.
- Search: `employee_id.name`, `number`, `employee_id.barcode`.
- Learn: `ps-chips` stays on the step strip; add `coach="'ps-filters'"` on
  the layout + declare; replica `payslips()` strip.

### 3. Pay Runs — `pb_payruns` (§18) — the big one
- `_pbf_model='hr.payslip.run'`, screen `payruns`, base = the board's
  company rule (runs have no `company_id`: the facade filters by the slips'
  company — express it as `slip_ids.company_id in co_ids` using `any`, and
  verify on the preview that counts match `get_board_data`'s run set).
- PIN `stage` (choice with tones over `state` per `PB_STATES`), PIN `period`
  (`date_end`: this/last month presets + custom), PIN `division`
  (`pb_division` char with labels from `pb_division_label` — pass labels in
  the spec `labels` map if the kit's `_pbf_pretty` is not enough: the mixin
  has no labels map for char, so either rely on `_pbf_pretty` or add the
  labels as a `choice` with per-division domains); `scheme`
  (`pb_formula_config_id`), `currency` (`pb_currency_id`), `mine` (choice
  via `pb_awaiting_me` search — it has `search=`, so a literal domain
  `[('pb_awaiting_me','=',True)]` works), `health` (choices: checks failing
  = `pb_balance_ok = False` or `pb_unsourced_count > 0`), `sentback`
  (`pb_return_note != False`), `prepared` (`pb_prepared_uid`), `people`
  (number `pb_employee_count`), `net` (number `pb_total_net`, money), `refund`.
- Views: All live runs · Waiting on me · This month · Sent back · Rejected.
  ("Approved, not paid" needs the payment models → debt.)
- Lanes: the three lanes stay; each lane shows the kit's page rows of its
  state; lane counts = kit `stage` counts (ruling R1 supersedes W82 — write
  that in the template comment). The hero phrases → `toggleFilters`. List
  view sort → `_pbf_sorts`. Bulk submit reads the shown rows (R6); shift
  select walks the shown rows.
- `useNavigationState` keys → dropped; the kit remembers.
- `get_board_data` keeps returning the un-paged board for `pb_payruns_learn`
  ("Right now") — R4; the lanes read the new page method.
- Demo pre-filter (June 2026) lived only in the kanban twin → not carried.
- Learn: `pk-divchips` anchor → the layout's `coach`; replica `payruns()`
  strip; 21 lessons on `payruns`, 3 quote `pk-steps`, 1 `pk-divchips`.

## Wave-specific tests
- W5-T1 Pay Runs: tick a division → all three lanes narrow and their counts
  change; hero "waiting" phrase press → chip + lane lights.
- W5-T2 Pay Runs: bulk submit with a filter on → only shown runs are submitted
  (use draft demo runs on the preview; do NOT compute or approve anything).
- W5-T3 Payslip review: change run → panel reloads with that run's counts.
- W5-T4 Structures: `contract_type` section lists contract types with counts.

## Report back
`FILTER_W5_REPORT.md` per `FILTER_WAVE_COMMON.md §E`.
