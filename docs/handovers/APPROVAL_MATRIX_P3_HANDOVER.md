# Approval Matrix · Phase 3 — Pay runs on the engine + New configuration reconciliation

**Handover from Fable (design) to Opus (build) · read `APPROVAL_MATRIX_LEDGER.md` first (AM1–AM14+) and append. Phases 1–2 are merged locally; read their reports (ledger) and the `pb_approval_config` code (`ApprovalSchemePanel` props, `_approval_scope_options` shape) before starting.**

## 1. Scope

1. **Pay run adapter** in `pb_payruns`: `hr.payslip.run` inherits `biz.approval.adapter.mixin` (`_approval_process_key = 'payrun'`), supplies scope keys (`scheme:<id>|division:<id>`, `scheme:<id>`, `division:<id>`, ``), `kind_key` from the run's cycle type, typed facts (`net_total` VND decimal, `gross_total`, `payslip_count` int, `variance_pct` vs previous run of the same scheme/kind, `overtime_included` bool, `employee_count`), makers (users who created/computed the slips: the wizard's actor + `create_uid` of slips), submitter, subjects (employees' users), evidence (control report attachment key `control_report` when present), `source_revision` = sha256 over sorted `(slip id, net, gross, write_date)`.
2. **Clean replacement of the old chain** (ledger: no payroll is live): remove `level0/level1/level2` states, `PB_TIER`, `_pb_officer_tier`, `officer_review` setting, send-back ladder and the three `action_payslip_run_levelN_done` entry points; add states `approval_pending` and keep `draft`, `done`, `cancel`. Submission = `action_approval_submit()`; the engine's final `_approval_apply` runs the legacy "done" body (slip cascade + accounting hooks, guarded exactly as today) under the request lock; `_approval_return` walks slips back to draft; fast lane applies immediately.
3. **Mixed-scope guard**: `_approval_validate` refuses a run whose slips resolve to more than one `(scheme, division, currency)`; offers `action_split_review_groups()` that creates one child run per group (draft only, conserving every slip exactly once, totals reconciled) — see §3.4.
4. **Every consumer of the old states** updated (list in §2). `pb_approval` module retired: its client action redirects to the Home Approvals lens; `pb_approval` removed from `pb_home_hub` depends; module kept installable as an empty shell for one release (so `-u` does not break), marked `auto_install: False`, with a migration that uninstalls nothing else.
5. **Close the sudo hole** at `payroll_analytics_approval/models/payroll_analytics.py:894` (finalises runs via sudo) → route through `engine.submit`/`decide` as the acting user, or remove the action.
6. **Blueprint Connect (3 of 6)**: the Approvals card becomes real: mounts `ApprovalSchemePanel` for `payrun` with `scope_key = scheme:<config id>` and a second one for `scheme_change` (read-only "Shared · Scheme change" line until P4 delivers the adapter); server guard no longer refuses the task; status derives from the engine (`inherit|shared|custom`, coverage ok/needs people); Finish shows real coverage and a working return link; finishing a draft never activates; activation checks coverage.
7. **Scheme Settings**: an "Approval workflows" panel (same component) on the formula configuration settings screen.
8. **Default workflow seed** for `payrun` per company: "Officer → HR → Finance" preset published as the company default (roles `payroll_mgr` → `hr_lead` (division) → `finance`), plus a migration that assigns today's group holders to those roles (officer group → `payroll_mgr`, HR manager group → `hr_lead` at company scope, final approver group → `finance`) so day one routes to the same people. Existing draft runs stay draft; no run is mid-chain (verify with a count and stop if any).
9. Inbox cards for pay runs (icon `zap`, amount, payslip count, run kind) and the run's own screen showing the route and a "Submit for approval" primary action; kanban/board/pipeline widgets read `approval_state`.
10. VI `.po`, tests, Chrome validation (local), deploy checklist.

**Non-goals:** timesheets, scheme-change proposals (P4); money-out and pay data adapters (P5); chain-mixin consumers (P5).

## 2. Verified plumbing (do not re-derive; re-read each file before editing)

Pay run engine and every consumer of `level0/1/2` (from the architecture check, file:line as of 12 Sep):
- `pb_payruns/models/hr_payslip_run.py`: `PB_TIER` :24-29, `PB_STAGE_NAME` :33, `PB_SEND_BACK` :51-60, `PB_SLIP_STATE` :88-92, seal `_PB_CHAIN_KEY` :100-124, state `selection_add` :140-142, testimony fields :147-164, `pb_stage_rail` :170-189, `_pb_officer_tier` :199 and helpers :206-235, totals :243-258, roles/tiers :483-566, `action_payslip_run_level0/1/2_done` :602-649, cancel :634, `action_pb_send_back` :708-749, slip walk-back :681, undo blocker :660, `done_payslip_run` :816-868, awaiting-me search :797. `pb_payruns/models/pb_payruns.py` (board: `next_action` :101-109, `can_send_back` :118, labels :148-150). JS: `static/src/js/payruns.js:33-36, 231`, `payruns_kanban.js`, `pipeline_field.js`. Views: `views/hr_payslip_run_form_enhance.xml:25-53`, `hr_payslip_run_kanban.xml:59-78, 95`. Settings switch: `pb_payruns/models/res_config_settings.py`. Tests: `tests/test_approval_chain.py`, `test_officer_tier_switch.py` (delete/replace).
- `pb_payrun_wizard/models/pb_payrun_wizard.py:1721-1729` `submit_for_approval` (calls `done_payslip_run`).
- `pb_approval/models/pb_approval.py:28-40, 81-83, 160-171, 206-228`; `static/src/js/approval.js:68`.
- `payroll_analytics_approval/models/payroll_analytics.py:279, 338-356, 880-894 (sudo finalize), 930 (raw SQL state write)`; `models/payroll_dashboard_integration.py:47-48`.
- `pb_hr_payroll_analytics/models/hr_formula_config_analytics.py:194`.
- `pb_payslip_review/models/pb_payslip_review.py:13-14`, `static/src/js/payslip_review.js:8-13`, `xml/payslip_review.xml:38-39` (slip-level states — slips keep the standard `draft/verify/done/cancel`).
- `pb_explorer/models/hr_payslip_run.py:7`; `pb_insights/models/pb_insights.py:230-231`; `pb_dashboard/models/pb_dashboard.py:267,280`; `pb_payhub/models/pb_pay_hub.py:42-44`; `pb_payrun_results/models/payrun_results.py:288-289`, `static/src/js/payrun_results.js:100`; `pb_blueprint/models/blueprint_connect.py:66-70`.
- Pay delivery filters on `done` only (`pb_pay_delivery/models/pb_pay_delivery.py:47,107`, `bank_export_wizard.py:84`, `payslip_delivery.py:153`) — unchanged.
- Accounting hook the legacy done body calls: `om_hr_payroll_account/models/hr_payroll_account.py:226-241` — keep calling it from `_approval_apply`.
- `hr.payslip.run` has NO `company_id` → derive from slips (`getattr` guard).
- Blueprint: `pb_blueprint/models/blueprint.py:27-30 (owner ruling comment), 40-46 (DEFAULT_OPTIONAL_STATUS approvals), 230-264 (optional_status)`; `blueprint_connect.py:60-72 (tier_rows → delete), 118, 144, 367-391 (_approval_tiers → replace with a binding read), 406-409 (guard refusal → remove), 498-499 (skip-all continue → remove)`; `static/src/js/step_connect.js:201-209, 312-325`; `static/src/xml/connect.xml:146-167, 190-197`; `models/blueprint_finish.py:65, 82, 647-648`; `static/src/js/finish_text.js:215-216`; `blueprint_steps.js:45` hint text.
- Scheme ↔ division ↔ run kind: `pb_scheme_map` (`pb.scheme.map.resolve_many`, `hr.formula.scheme.assignment.division_id/cycle_type`, `CYCLE_SELECTION` :52-68). Run kind on a run: check `hr.payslip.run` for the cycle field added by `pb_hr_payroll_formula` (grep `cycle_type` on the run model) — if absent, derive from the slips' formula cycle.
- Division of an employee on a date: `pb.division.division_for(department, on_date)`.

## 3. Architecture

### 3.1 Adapter on `hr.payslip.run` (module `pb_payruns`, add depends `biz_approval_workflow, pb_scheme_map, pb_group`)
- `_approval_context()`: company from slips; scope keys via `pb.scheme.map.resolve_many` + `division_for`; refuse mixed scope (§3.4); facts per §1; makers = distinct `create_uid` of slips + the wizard actor stored on the run (`pb_prepared_uid`, new Char/Many2one set by the wizard); `submitter_uid = env.uid`; `subject_uids` = slips' employees' `user_id`s.
- `_approval_capabilities()`: facts (typed + labels), kinds from `CYCLE_SELECTION`, evidence kinds (`control_report`, `variance_note`, `bank_control_total`), `scope_levels ['scheme','division']`, `manager_mode: False` (batch).
- `_approval_scope_options(company)`: scheme level from active `hr.formula.config` of the company (`pb_scheme_board` query), kind level from `CYCLE_SELECTION`.
- `_approval_coverage_scopes(company)`: every `(scheme, division)` pair with headcount from `pb.scheme.map.coverage()`.
- `_approval_freeze(request)`: mark slips `verify`, set run `approval_pending`, store `source_revision`.
- `_approval_apply(request)`: re-verify revision; run the legacy done body (`super().close_payslip_run()` equivalent — read the current `done_payslip_run` :816-868 and the level2 body, keep `_accountless` behaviour :844); set `done`.
- `_approval_return(request, reason)`: slips back to `draft`, run `draft`, store `pb_return_note/uid/date`.
- Run fields: `approval_state` (related to latest request state), `approval_request_id`, `pb_prepared_uid`, `pb_return_*`. Remove the level fields and the settings switch (`res_config_settings.py`), with a migration dropping the stored columns.

### 3.2 States
`draft → approval_pending → done`, `cancel`. Direct `write({'state': ...})` stays sealed with the existing token pattern; only the adapter's `_approval_freeze/_apply/_return` may move it.

### 3.3 Retire `pb_approval`
Keep the module directory with a manifest (bumped), an empty models package, and a client action tag `pb_approval` that redirects (JS shim) to `openHub(home xmlid, lens 'approvals')` — so old bookmarks and the palette keep working. Remove it from `pb_home_hub` depends. Delete its board JS/XML/SCSS and the pay-run-only facade.

### 3.4 Split into review groups
`action_split_review_groups()` on a draft run with mixed scope: groups slips by `(scheme, division, currency)`; creates one draft run per group (name suffix "· Retail", etc.), moves slips, verifies `sum(net)` per group equals the source and that the source ends empty then is deleted; logs an event on each child. Wizard exposes it when `_approval_validate` raises the mixed-scope error (button on the error toast).

### 3.5 Blueprint + scheme Settings
`blueprint_connect.py`: `approvals` task becomes a normal optional task with statuses `inherit|shared|custom` + `coverage: ok|needs`; `_approval_binding(config)` reads `pb.approval.matrix.get_scheme_panel('payrun', 'scheme:<id>', company)`; the guard no longer refuses; skip-all may skip it. `connect.xml` mounts `ApprovalSchemePanel` (import from `@pb_approval_config/js/scheme_panel`) — `pb_blueprint` adds `pb_approval_config` to depends. Copy: replace "already in place / coming later" with the POC strings ("Choose the checks for this scheme.", "Finish can save a draft. Activating the scheme and submitting a pay run both need a complete approval route."). Finish row: real status + change link. `formula_config` settings screen: same panel.

### 3.6 Seeds/migration
Per company: published `payrun` default (preset officer_hr_finance) + binding; responsibilities from today's group holders (first holder = person, second = backup; none → gap shows in People & backups). Migration verifies there is no run in a level state; if any, it aborts the upgrade with a plain message naming the runs.

## 4. Safety rails
1. Money still only leaves via pay delivery on `done`; nothing here touches delivery.
2. No `sudo()` to finalize; the analytics sudo hole is closed.
3. Slips cannot bypass the run: direct slip `action_payslip_done` on a slip whose run is `approval_pending` raises.
4. A run whose slips changed after submission cannot be applied (revision check) — the approver sees "Pay data changed since submission. Send it back so it can be resubmitted."

## 5. Tests (`pb_payruns/tests/test_approval_engine.py` + updates elsewhere)
| ID | Scenario |
|---|---|
| R01 | Submit a homogeneous run: request created, facts frozen, slips `verify`, run `approval_pending` |
| R02 | Mixed scheme/division run refused; split creates children conserving slips and totals (A22) |
| R03 | Full route approve → run `done`, slips `done`, accounting hook called once (A24) |
| R04 | Return → slips/run back to draft with note; resubmit = attempt 2 |
| R05 | Slip changed after submission → apply refused (A16) |
| R06 | Direct slip done / raw state write while pending → refused (A15/A24) |
| R07 | Fast-lane published for a scheme → submit applies immediately |
| R08 | Exact-kind binding (off-cycle) beats any-kind (A04) |
| R09 | Analytics approval can no longer finalize via sudo |
| R10 | Blueprint: Connect approvals task opens, status derives from engine; Finish shows coverage; draft finishes without activating; activation with a coverage gap is refused with the gap named (A27) |
| R11 | Seed: default workflow + responsibilities from group holders; migration aborts on a mid-chain run |
| R12 | Static contract + VI `.po` for touched modules |

## 6. Test, validate, deploy checklist
Local: `runtests.sh pb_payruns`, `runtests.sh pb_blueprint`, `runtests.sh pb_approval_config`; Chrome (local): Pay Run → run a demo payroll (pb_demo present locally? if not, create a small run via the wizard) → Submit for approval → inbox card → approve as the HR lead and Finance approver (two users) → run done; New configuration → Connect → Approvals card → Change → Customize → builder → back → Finish shows coverage. Deploy checklist for the wave: modules to install/upgrade per DB (`pb_payruns`, `pb_payrun_wizard`, `pb_approval` (shell), `pb_home_hub`, `pb_blueprint`, `pb_hr_payroll_formula` (settings panel), analytics modules touched), migrations, seeds, asset ritual yes.

## 7. Report back
Same items as P2 §8 plus: the exact list of removed public methods and any external caller you found for them; the migration's safety check output; the split algorithm's conservation proof in the test.
