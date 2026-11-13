# FILTER wave 2 — People lifecycle boards (the heavy three)

Read first: `FILTER_LEDGER.md`, `FILTER_WAVE_COMMON.md`, then INVENTORY.md
§2, §3, §6. Reference: `pb_people`, and wave 1's Contracts once merged (not
required). Wave id `w2`, stage `/tmp/pbf_stage_w2`, preview holder `w2`.
Report: `docs/handovers/filter/FILTER_W2_REPORT.md`.

These three boards derive half their facts from OTHER models per row. The
rule (ledger R2): no stored fields; a Python-only fact becomes a `choice`
with `domain_method` returning `[('id','in', ids)]`, computed with ONE or
two queries over the base domain (never per row), and timed on the preview
(report the ms). If a fact cannot be computed in < 300 ms, keep it as a
card badge and write it under debts.

### 1. Contracts (renewals) — `pb_contract_lifecycle` (INVENTORY §2)
- `_pbf_model='hr.contract'`, screen `contractends`. Base domain = the
  union of the two searches: `['|', '&', ('date_end','!=',False), ('state','in',['draft','open']),
  '&', ('employee_id.active','=',True), ('employee_id.employee_type','in', NON_PERMANENT_TYPES)]`
  plus company. (The "fill the remainder" cap goes; the panel pages.)
- PIN `ends` (`date_end`, future presets + custom), PIN `decision` (choice
  over `pb_review_ids.state` with literal `any` domains: not raised /
  decision needed / extension requested / evaluation running / decided; use
  `domain_method` only if the "live review" rule needs Python), PIN
  `department`; `kind` (`employee_id.employee_type`), `status`, `category`,
  `manager`, `starts`, `attention` (choice via `domain_method` cloning the
  `needs_decision`/`urgent` rule with the lead-days param).
- Views: All · Ending within the lead days · Nobody has decided · Waiting to be
  agreed · Interns and contractors.
- `kpis.converted`/`would_raise` keep their own counts (R4).
- Employee fields were read via sudo per row: counts on `employee_id.*`
  must not raise for lifecycle-only users — use `_pbf_records()` sudo ONLY
  if the current board already sudo-reads those fields (§2 risks), and
  keep the company restriction.
- Learn: replica `contractends()`; anchors `cl-*` unchanged; add
  `coach="'cl-filters'"` and declare it in `anchors.json`.

### 2. Probation — `pb_probation` (INVENTORY §3)
- `_pbf_model='hr.employee'`, screen `probation`, base = company +
  `pb_probation_state in ('in_probation','extended')`. Note the field has
  `groups='hr.group_hr_user'`: if the current board reads it under sudo,
  do the same in `_pbf_records()`; otherwise a non-HR user already cannot
  open this board.
- PIN `trial_ends` (`trial_date_end`, future), PIN `stage` (choice over
  `pb_probation_review_ids` `any` domains: feedback running / verdict
  waiting / sign-off — from `probation_common.py` states + `pb_gate`), PIN
  `department`; `trial` (`pb_probation_state`), `country`, `manager`, `job`,
  `joined`, `company`, `answers_late` (choice `any` [state=feedback,
  feedback_deadline < today]), `round` (`pb_probation_review_ids.round` is
  a one2many hop → NOT a path; drop it or make it a choice "2nd round or
  later" with an `any` domain).
- Views: All in trial · Ending within 7 days (custom range) · Waiting on a
  decision · Answers overdue · Extended.
- Training/red-flag facts stay card badges (debt).
- Arrival `person:<id>` keeps auto-opening the drawer (`initial` is not
  needed; the drawer logic is separate).
- Learn: replica `probation()`; add `coach="'pr-filters'"` + anchors entry.

### 3. Exits — `pb_offboarding` (INVENTORY §6)
- `_pbf_model='pb.journey.case'`, screen `exits`, base = offboarding + states + 120-day floor + company.
- PIN `last_day` (`anchor_date`, past+future: presets `past` plus custom),
  PIN `department`, PIN `clearances` (choice: still open = `clearance_ids any
  [state=pending]`; all cleared = not that); `country`, `handover` (choice
  `kt_item_ids any [state != done]`), `status`, `checklist`, `source`,
  `manager`, `overdue` (tasks `any`), `desk` (choice per `clearance_ids.dept`
  value with `any [dept=X, state=pending]`), `settlement` (choice via
  `domain_method`: ready / closed / to check — computed with one query on
  `hr.full.final.settlement` by `employee_id` over the base domain's
  employees, sudo as the board already does).
- Views: All leaving · Leaving this month · Last day has passed · Clearances
  still open · Ready to settle.
- Steps: the 4-step strip stays `QuietSteps`, counts from the kit's
  `settlement`/`clearances`/`last_day` sections; pressing = `toggleFilters`.
- Learn: 13 lesson refs on screen `exits`, replica `exits()` — redraw the
  filter strip; `ex2-*` anchors unchanged; add `coach="'ex2-filters'"`.

## Wave-specific tests
- W2-T1 Each `domain_method` timed on the preview (`odoo-bin shell`,
  `time.perf_counter`) with the base domain of the demo company; report ms.
- W2-T2 Probation as a user WITHOUT `hr.group_hr_user` (preview: create a
  test user from shell, log in through the tunnel): no traceback, either the
  board's own refusal or a working panel — report which.
- W2-T3 Exits "Ready to settle" count equals a manual count from shell.
- W2-T4 Renewals: the union base domain returns ≥ the old board's row count
  on the preview (it had a 300 cap; compare `search_count`).

## Report back
`FILTER_W2_REPORT.md` per `FILTER_WAVE_COMMON.md §E`, with the timing table.
