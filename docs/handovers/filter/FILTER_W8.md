# FILTER wave 8 — Workforce planning, Overtime desk, Payroll report, Pay review

Read first: `FILTER_LEDGER.md`, `FILTER_WAVE_COMMON.md`, INVENTORY.md §21,
§29, §30, §35. Wave id `w8`, stage `/tmp/pbf_stage_w8`, preview holder `w8`.
Report: `docs/handovers/filter/FILTER_W8_REPORT.md`.

### 1. Overtime desk queue — `pb_hr_workforce` (§30)
- `_pbf_model='hr.overtime.request'`, screen `otqueue`, base = `state =
  submitted` + company, same sudo as `get_desk` (gate first: `pbf_layout`
  refuses when the desk refuses). The Bonus review rail stays (R5-like:
  it is a second surface with its own server filters — leave it).
- PIN `department`, PIN `type` (`overtime_type`), PIN `day` (`date`, past
  presets + custom); `employee`, `planned` (number hours), `bonus` (number),
  `rule` (`overtime_config_id`), `manager`, `company`. Status is fixed by
  the base domain (submitted) — but add built-in views that widen it: the
  views below set a `status` choice section whose default view is
  "To approve".
- Views: To approve (default) · Approved this month · With bonus hours · Weekend and holiday (if a field says so; else drop) · This week.
- Bulk approve/refuse: `selectAll` picks the kit's page (R6); the tray
  reads selected ids.
- Learn: `wf-ot-queue` stays on the queue panel; replica `wftime()` OT
  strip; add `coach="'wf-ot-filters'"` + declare.

### 2. Payroll Report — `pb_hr_workforce` (§21)
- `_pbf_model='hr.payslip'`, screen `payreport`, base = `payslip_run_id =
  picked run` (ctx `{run_id}`, `reconfigure` on change) + `state != cancel`.
- PIN `department` (`employee_id.department_id`), PIN `changed` (choice via
  `domain_method`: ids of slips whose figures differ from the prior run —
  compute ONCE per request with the existing comparison code over the whole
  run, cache for the request; time it on the 900-slip demo run), PIN `job`
  (`contract_id.job_id`); `structure`, `company`, `status`, `manager`,
  `newjoiner` (choice `employee_id.first_contract_date >= run.date_start`).
- Views: Everyone in this run · Pay changed · New joiners this run.
- Gross/net/deductions numbers: not stored (R2) → no number sections; debt.
- The three tabs render the kit's page rows; Dept Summary aggregates the
  filtered set (recompute from the page is wrong — compute the summary on
  the server over `pbf_domain`, one grouped query).
- Learn: replica `reports()` strip; anchors `rp-*` unchanged; add `coach="'rp-filters'"`.

### 3. Workforce planning › Employee forecast detail — `pb_hr_workforce_planning` (§29)
- New facade `pb.wfp.forecasts` (AbstractModel + mixin) with
  `_pbf_model='wfp.employee.forecast'`, screen `wfpforecast`, base =
  `scenario_id = selected` (ctx `{scenario_id}`), excluded rows included
  (there is an `excluded` section).
- PIN `department`, PIN `rule` (`applied_rule_id`), PIN `pct`
  (`increase_pct` number); `job`, `manager`, `amount` (money), `country`
  (`country_code` char), `location` (char), `tenure` (number months),
  `excluded` (choice `is_excluded`).
- Sorts: `_pbf_sorts` = the table's columns (biggest increase first is the default).
- Views: Everyone in the scenario · Increases over 10% · No rule applied · Excluded people.
- The dept chart keeps reading the unfiltered map (say so in a template
  comment) — or compute it from `pbf_domain` on the server if cheap.
- Legacy dashboard: touch only the Compensation tab's table block; keep
  Chart.js and the other tabs as they are.

### 4. Pay review worksheet — `pb_pay` (§35)
- `_pbf_model='pb.pay.review.line'`, screen `payreview`, base = `review_id
  = X` (ctx `{review_id}`), with the `can_names` privacy kept in the row
  payload (never in counts of names).
- PIN `team` (`department_id`), PIN `score` (choice: Not scored = rating 0
  / scored), PIN `band` (choice: below the band = `has_band` and
  `position_pct < 0`; in band; above); `manager` (`manager_id`; "My team" =
  choice `manager_id.user_id = uid`), `job`, `division`, `band_id`, `rise`
  (number `proposal_pct`), `state`, `stops` (choice via `domain_method`
  reading the `chips` Json for the review's lines in one query — time it).
- Views: Everybody · My team · Not scored · Stops approval · Paid below the band · No rise.
- `_filtered_lines` (Python lambdas) → `pbf_domain`; keep the PAGE = 120
  window and sort (team, name) as the default `_pbf_sorts` entry; bulk
  verbs and calibration act on the page or "everything matching" via one
  server call (R6). `unrated`/`total_rows` header counts from the kit.
- Learn: `pp-worksheet` stays; replica `payreview` strip; add
  `coach="'pp-filters'"` + declare.

## Wave-specific tests
- W8-T1 OT desk: select all + approve on the preview acts only on the page.
- W8-T2 Payroll report: "Pay changed" view count equals the number of rows
  with events in the old payload for the same run; `changed` timed (ms).
- W8-T3 Forecast: sort by biggest increase matches the old default order.
- W8-T4 Pay review: "Stops approval" equals the old chip count; a bulk
  action with a filter on touches only matching lines (preview only).

## Report back
`FILTER_W8_REPORT.md` per `FILTER_WAVE_COMMON.md §E`.
