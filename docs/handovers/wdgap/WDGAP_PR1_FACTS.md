# WDGAP PR — plumbing facts: loans and advances, run types and one-person runs, holding pay

Verified by a read-only code survey on 2026-11-14 (branch 19.1). Do not re-derive; spot-check a line before relying on it.

I checked everything below against the code on branch 19.1 (read-only). Every path is under `/Users/adity/Documents/GitHub/gitlocal/`.

## A. How a value reaches a payslip today

There are two separate input paths, and any new value source has to cover both.

**1. Regular path (no pay-data file).** The entry point is `hr.payslip._get_formula_input_values(self, config, provenance=None)` in `/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_formula/models/hr_payslip_formula.py:609-904`.
- It reads contract fields, worked days, the connector feed, employee mappings, and finally the contract components (rank 5) at `:810-833`.
- Then it fills period values at `:858-868` and work segments at `:890`.
- **Contract pay items:** `hr.contract.advantage` and its template live in `/Users/adity/Documents/GitHub/gitlocal/om_hr_payroll/models/hr_contract.py:8,144`, with typed versions in `pb_hr_payroll_formula/models/contract_advantage_typed.py:26,36`. They are read by `_contract_component_amounts` / `_contract_component_values` in `/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_formula/models/payroll_import_batch.py:2212,2239`.
- Contract lines have no dates. Dated history is kept separately in `hr.contract.advantage.change` (`contract_component_change.py:48`, `effective_date`).
- **Pay-data file runs** go through `payroll_import_batch._transform_data_to_formula_inputs` (`:4196`). Proration, retro and carry-over are applied there (`:4947-4961`).

**2. Application-data mode** (`hr.payslip.run.application_data_mode`, `/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_formula/models/application_payroll_source.py:962`).
- Each input rule names an `application_source_key`.
- The extension points are both on `hr.formula.config`:
  - `_application_source_catalogue()`, the declared seam ("domain modules add typed sources") at `application_payroll_source.py:337`, extended at `application_domain_sources.py:146` and `payroll_period_input.py:392`.
  - `_application_domain_values(employee, contract, date_from, date_to)` at `:356`, `application_domain_sources.py:197` and `payroll_period_input.py:404`.
- The dispatcher is `_application_domain_value` (`application_domain_sources.py:235-303`). Static keys go in `DOMAIN_SOURCES` (`:52-77`).
- **Precedent to clone for a loan source:** `awards.*` → `_application_award_value` (`:444-475`). It requires a full calendar month, returns a conflict if the award is already queued or paid, and returns `consumption_required=True`.
- When `consumption_required` is set, the cell is blocked unless a paid-once reservation exists (`application_payroll_source.py:720-727, 838-839`).

**`hr.payroll.period.input`** (`/Users/adity/Documents/GitHub/gitlocal/pb_hr_payroll_formula/models/payroll_period_input.py`)
- Fields at `:40-88`: `reserved_run_id`, `reserved_payslip_id`, `consumed_payslip_id`, `settlement_kind` (`none` / `cashout_days` / `cashout_amount` / `recovery_amount`), `exit_reference` (an approved `pb.resignation`).
- States: `draft` / `approved` / `superseded`.
- Unique partial indexes at `:104-125`. `action_approve` is at `:253`, `action_supersede` at `:308`.
- `_application_reserve(run, slip)` `:318`, `_application_consume(slip)` `:333`, `_application_release(slip)` `:350`.
- The slip hooks reserve on resolve (`:479-489`), consume on a write to `state` done/paid (`:498-507`), and release on cancel or unlink (`:499-502, 509-513`).
- **This only works in application mode.**

**Paid-once precedent on the regular path** (the best one to clone): `pb.updates.oneoff`.
- Model and states: `/Users/adity/Documents/GitHub/gitlocal/pb_updates/models/updates_oneoff.py:118`, states at `:148`, `LIVE_STATES` / `DONE_SLIP_STATES` at `:50-52`.
- Reader `_for_slip` `:316`, reserve/pay/release `_sync_slip` `:361`, `_release` `:403`, `_slips_done` / `_slips_gone` / `_runs_gone` `:421-442`.
- Slip and run hooks at `:741-775`.
- Seam overrides: `/Users/adity/Documents/GitHub/gitlocal/pb_updates/models/updates_payrun.py:82` (`_get_formula_input_values`) and `:264` (batch transform).
- Paid-once token: `used_start` / `used_of` / `used_end` `:54-69`, wrapper `_pb_compute_sheet_with_formulas` `:166`, `action_recompute_formula_lines` `:184`.
- Demo seam: `_pb_updates_merge_inputs` / `_done` `:127,157`.
- It refuses to run in application mode (`:84`).

**Bridge precedents:**
- `/Users/adity/Documents/GitHub/gitlocal/pb_trip_payroll_bridge/models/hr_payslip.py:15-74` (codes TRIPDAYS, PERDIEM).
- `/Users/adity/Documents/GitHub/gitlocal/pb_workforce_payroll_bridge/models/hr_payslip.py:28-86` (codes OTHRS*, BONHRS).
- Pattern: call `super()` first, add only the codes the scheme declares as inputs, read with `sudo()`, and always forward `provenance`.
- **Double-pay guard: none**, beyond "approved" plus the period window (and the trip per-diem channel check). A top-up run for the same month would pay them again.
- New codes must have no underscores and must not be substrings of each other (C18.2 registry list at workforce bridge `:16-21`).

**`hr.payslip.input`** is only read by classic salary rules (`om_hr_payroll/models/hr_payslip.py:502,598`). The formula engine never reads it. The wizard just copies it from onchange (`pb_payrun_wizard.py:1163,1366`).

## 1. Loans and salary advances

**What already exists:**
- **Demo only:** `hr.loan` in `/Users/adity/Documents/GitHub/gitlocal/pb_demo/models/hr_loan.py:11-50`. Fields: principal, installment_amount, balance_amount, total_months, paid_months, state draft/running/closed.
  - It feeds input `INLOAN`, and the demo formula is `LOANREP = -INLOAN` (`pb_demo/models/demo_catalog.py:86,112`), via `_loans_for` (`demo_payrun.py:277,437`).
  - **The balance is never reduced.** It is only set when the demo data is seeded (`demo_employees.py:187`).
- **Mid-month advance netting:**
  - `hr.payroll.cycle.carryover` (`pb_hr_payroll_formula/models/payroll_cycle_carryover.py:7`).
  - The mid-to-end link is `hr.payroll.cycle.component.mapping` (`payroll_cycle_component_mapping.py:12-33`, mid/end config and component). Per-scheme fields are at `formula_config.py:170-181`.
  - Records are created by `_create_mid_cycle_carryovers` (`payroll_import_batch.py:2404`), triggered at `hr_payslip_formula.py:1249-1283`.
  - The month-end run nets the advance in `_apply_mid_cycle_carryover` (`:2514`), called **only on the pay-data-file path** (`:4959-4961`).
  - **Gotchas:** carry-over records stay `posted` forever and have no consumed marker, so running a second month-end batch would net the advance again. The regular wizard path never applies carry-over; the demo instead reads `ADVPAY` from the mid run's lines (`demo_payrun.py:262`).
  - The person's advance scheme is `hr.employee.pb_paid_by_advance_id` (`pb_scheme_map/models/hr_employee.py:51`).
- **Business trip:** `pb.business.trip.advance_amount` (`pb_business_trip/models/pb_business_trip.py:54`) is used only in the self-service trip screen (`pb_me_trip/models/me_trip.py:379,863`). Nothing sends it to payroll.
- Nothing matched `salary_advance`, `tam_ung` or `kasbon` outside of code-name lists.

## 2. Bonus / off-cycle run / one person

- **Run kind:** `PB_RUN_KINDS = [('regular','Regular'),('topup','Top-up')]` at `/Users/adity/Documents/GitHub/gitlocal/pb_payruns/models/hr_payslip_run.py:65`. The field `pb_run_kind` is at `:352`; it can only be changed while the run is a draft (`:720-727`).
  - It affects only the "Compared with" check (`pb_payruns.py:1053-1055`), the kanban tag, and the wizard's guard, clean-up and adopt steps.
- **Scheme cycle type** (`formula_config.py:74-79`: regular / mid_cycle / end_cycle / full_final) is separate from run kind, and it picks the approval route (`_pb_kind_key`, `hr_payslip_run.py:812`).
- **Where it is chosen in the wizard:** `pb_payrun_wizard/static/src/xml/payrun_wizard.xml:125-147` and `static/src/js/payrun_wizard.js:625-630`; `get_defaults` sets `run_kinds` at `pb_payrun_wizard.py:643`.
  - The on-screen note says it outright: a top-up "still makes a payslip for everyone this scheme covers" (xml `:146`).
- **Wizard server code** (`/Users/adity/Documents/GitHub/gitlocal/pb_payrun_wizard/models/pb_payrun_wizard.py`):
  - `_eligible_employees(statuses, employee_ids, formula_config_id, date_start, date_end)` `:646`.
  - `_scheme_population` `:321`.
  - `_run_kind_from_vals` / `_run_kind_vals` / `_run_kind_of` `:867-889`.
  - **Scheme- and kind-aware duplicate guard:** `_period_runs(ds, de, config, kind)` `:908-952`, message from `_exists_message` `:955`, clean-up `_clean_period(runs, kind)` `:1046`, blockers `_clean_blockers` `:132`.
  - Adopt step: `_adopt_loose_slips` `:1011` (a top-up adopts nothing, `:1021`).
  - Entry points: `create_and_compute` `:1094`, `prepare_run` `:1225`, `compute_batch` `:1324`.
- **Payload example** sent to `prepare_run`: `{name, date_start, date_end, formula_config_id, run_kind:'topup', statuses:[...], employee_ids:[42], force_clean, spreadsheet_skipped}`.
- **Running for ONE person today:** possible through `employee_ids`, but blocked in practice in four ways:
  - (a) The "Run for just a few people…" picker is shown, and `employee_ids` is sent, only when `hasStatusFilter` is true (xml `:161,178`; js `:843,1101-1105`). Application mode always sends it (js `:460`).
  - (b) A second Regular run, or a second Top-up, for the same scheme and month hits "already exists", and Clean and Run would delete the first one.
  - (c) The person's slip computes their whole month.
  - (d) The demo override ignores `employee_ids`.
- **pb_demo overrides** (`/Users/adity/Documents/GitHub/gitlocal/pb_demo/models/demo_payrun.py`): `get_defaults` `:197`, `prepare_run` `:289`, `compute_batch` `:409`, `create_and_compute` `:502`. They skip `super()` on the division path; kind handling is at `:316,345,537,570`. Any new wizard entry point must be overridden here too.
- **Awards precedent:** `pb.oneoff.feed` (`pb_comp_ben/models/oneoff_feed.py`): `queue_for_run` `:259`, `_apply_to_payslip` `:440` (re-computes the existing slip and never creates one), `mark_paid_for_run` `:480`.

## 3. Hold one person's pay

- **No hold or exclude flag exists** on `hr.payslip` anywhere.
- **Payslip states:** draft / verify / level1 / level2 / done / cancel (`om_hr_payroll/models/hr_payslip.py:53-60`). The run-to-slip state map is `PB_SLIP_STATE` at `hr_payslip_run.py:70`.
- **Bank file:**
  - Slip selection: `_resolve_slips` (done only) at `/Users/adity/Documents/GitHub/gitlocal/pb_pay_delivery/models/bank_export_wizard.py:81`.
  - Exclusion reasons: `_row_sources` `:95-131` (`no net pay` `:115`). File built in `_generate` `:219`.
  - `pb.bank.file.prepare` `bank_file.py:125` (the run must be `done`). It sets `excluded_json` / `excluded_count` (`:85`) and supersedes earlier files (`:181`).
  - **Gotcha:** `_control_total_matches_run` (`:233-241`) sums every done slip, so held people will show up as a mismatch.
- **Release:** `pb.payment.release` (`payment_release.py:89`).
  - **Gotcha:** `_approval_apply` stamps `pb_paid_on` on **every** done slip in the run (`:289-292`). There is one release per file (`:113-118`).
- **Payslip delivery:** `_do_send` (`payslip_delivery.py:187-258`) sends every done slip.
- **"Pay & deliver" screen:**
  - Backend: `pb_pay_delivery/models/pb_pay_delivery.py`: `_done_slips` `:50`, `_validation_preview` `:57`, `get_delivery_data` `:224`. Totals: `total_net` = total take-home `:256`, `bank_ready_net` `:257`.
  - Front end: `/Users/adity/Documents/GitHub/gitlocal/pb_pay_delivery/static/src/js/pb_pay_delivery.js` and `static/src/xml/pb_pay_delivery.xml` (left-out list `:88-145`).
- **Review screen:** `pb_payslip_review/models/pb_payslip_review.py` (`get_slip_detail` `:428`, `advance_state` `:446`), with UI in `static/src/js/payslip_review.js` and `static/src/xml/payslip_review.xml:146`. Flags come from `review_flags.py:49` (`pb_review_flags`; the zero-pay flag is at `:132`).
- **Run bulk bar:** `action_pb_slips(verb, slip_ids)` at `hr_payslip_run.py:1500`, with `_PB_SLIP_VERBS=('recalc','pdf','delete')` at `:1498`. It only works on draft runs (`:1538`), and a hold has to work on done runs. The UI is `pb_payruns/static/src/js/payrun_screen.js`.
- **Results grid** (`pb_payrun_results/static/src/xml/payrun_results.xml:67`): its only row action is `openPayslip`.

## Full & final

- **Model:** `hr.full.final.settlement` in `/Users/adity/Documents/GitHub/gitlocal/pb_hr_fullandfinal/models/full_and_final.py`. `c_loan` (`:128`) is filled by matching payslip component codes LOAN/ADV/TAMUNG (`:345-347`). It is a classification of payslip lines, not a pull of outstanding balances.
- Settlements are generated in `pb_hr_fullandfinal/models/payroll_import_batch.py:32`. The approval adapter is `fnf_approval.py:32` (process key `fnf`).
- **Assets do not become money.** They only block closing the settlement: `pb_offboarding/models/full_final_guard.py:117` (`open_items_for`), `_pb_blocker_list` `:64`.
- **Precedent for recovering a balance:** a period input with `settlement_kind='recovery_amount'` plus `exit_reference` (`payroll_period_input.py:68-79, 270-298`).
- The ledger display is at `pb_payrun_ledgers/models/ledger_cockpits.py:352`.

## Employee self-service

- `/Users/adity/Documents/GitHub/gitlocal/pb_me_portal/controllers/portal.py`: `/my/payslips` `:500`, `/my/taxsheet` `:450`, `_PAYSLIP_STATES=('done','cancel')` `:47`.
- Templates in `pb_me_portal/views/portal_templates.xml`: `portal_my_payslips` `:587`, `portal_my_taxsheet` `:904`, home cards `:31`.

## Approvals

- **Existing keys:** payrun, bankfile, release, payslips, paychange (`pb_pay/models/pb_pay_approval.py:40`), awards, fnf, month, runonly, loads.
- There is no loan or advance key. A new one needs:
  - an entry in `/Users/adity/Documents/GitHub/gitlocal/pb_approval_config/data/processes.xml` (awards entry at `:183-190`, with `money=True`);
  - optionally, aliases in `pb_approval_config/models/matrix_import.py:98-112`.
- **Adapter to clone:** `/Users/adity/Documents/GitHub/gitlocal/pb_comp_ben/models/incentive_approval.py`. It uses `register_chain(...)`, `_approval_process_key`, `_chain_facts`, `_approval_detail`, `_approval_seed_default` and `seed_all`. The base mixin is `biz_approval_workflow/models/adapter.py:19`.

## Tests, i18n and manifest versions

| Module | Version | Tests | i18n |
|---|---|---|---|
| pb_payruns | 19.0.3.5.0 | 10 files | vi_VN, id_ID |
| pb_payrun_wizard | 19.0.1.43.0 | `test_run_kind.py`, `test_two_schemes_one_month.py`, `test_run_adopts_the_period.py`, and others | vi_VN |
| pb_pay_delivery | 19.0.1.4.2 | `test_pay_delivery.py`, `test_money_out.py` | vi_VN |
| pb_hr_payroll_formula | 19.0.1.165.0 | 60 files, incl. `test_payroll_period_input.py`, `test_application_payroll_source.py` | `vi_VN.po` (plus stray `vi_VNnew*`) |
| pb_comp_ben | 19.0.1.7.0 | 2 files | vi_VN |

Other versions: pb_updates 19.0.1.7.4, pb_demo 19.0.1.14.1, pb_hr_fullandfinal 19.0.1.4.1, pb_payslip_review 19.0.1.4.0, pb_payrun_results 19.0.1.5.3, pb_payrun_ledgers 19.0.1.4.0, pb_me_portal 19.0.3.5.3, trip bridge 19.0.1.1.0, workforce bridge 19.0.1.2.0.