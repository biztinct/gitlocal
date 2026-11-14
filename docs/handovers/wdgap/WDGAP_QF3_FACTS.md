# WDGAP QF3 — plumbing facts: leave on My Payobook

Verified by a read-only code survey on 2026-11-14 (branch 19.1). Do not re-derive; spot-check a line before relying on it.

I've verified every item in the brief against the code; refs are file:line. Two findings change the plan most.

- **Half days aren't a per-request choice.** In this hr_holidays the half-day and hours flags are computed from the leave type, so the type has to be set up for half days or hours.
- **Portal `sudo()` skips the leave rules.** Because `apply_leave` runs under `sudo()`, the core state checks and `pb_timeoff`'s past-date refusal and lock are all bypassed. Withdraw and change requests must check state and dates themselves.

## 1. The /my leave page
- **Module:** `pb_ess_workforce`. Server-rendered QWeb with no OWL and no leave JS. The only scripts are the clock files.
  - Routes in `controllers/portal.py`: `GET /my/work/leave` (126-136) and `POST /my/work/leave/apply` (138-147), which redirects to `?done=leave_sent`. Both are `auth='user'`. Errors go through `_error_page` (293), messages through `_flash` (38-51).
  - Template `portal_my_work_leave` is at `views/portal_templates.xml:340-409`. It has balance tiles, a "My requests" table with no action column, and the "Request time off" form (392-402): `type_id`, `date_from`, `date_to`, `note`.
  - Entry points from `pb_me_portal`: the Leave card (`models/pb_me_home.py:524-535`, `_pbme_leave`), the hidden tile (118), and the leave row in `/my/requests` (773-787, no actions).
- **`get_my_leave()`** (`pb_ess_workforce/models/ess_workforce.py:406-481`). Employee comes from `_require_own_employee()` (82-101: matched on the session user, current company first). All reads are `sudo()`.
  - Balance = sum of `hr.leave.allocation.number_of_days` (state `validate`) − sum of `hr.leave.number_of_days` (state `validate` only), for `requires_allocation=True` types. Requests waiting for approval (`confirm`, `validate1`) are **not** deducted.
  - Gotcha: the types search (419) has no company filter.
  - Returns `{employee, balances[{id,name,allocated,taken,balance,balance_label,used_label,low}], requests[{id,type,date_from,date_to,days,state,state_label,note}], types[{id,name}], pending}`.
- **Leave types by country:** `_my_appliable_types` (484-497) = the company's types plus shared ones, filtered by `pb.timeoff._type_country(t) in ('', country)` (`pb_timeoff/models/pb_timeoff.py:102-116`). The type's country is the policy country, else the stock country; the employee's is their leave policy, else `payroll_country`, else the company's.
- **`apply_leave(type_id, date_from, date_to, note=False)`** (511-550). Validates that the type is in the offered list and the dates parse and are in order. Then `hr.leave.sudo().create({employee_id: emp forced, holiday_status_id, request_date_from, request_date_to, name})`. Caller is any login, portal (Employee tier) or internal.
- **Why `sudo()`:** TIERS rule T-R11 (`docs/handovers/tiers/TIERS_LEDGER.md:31`) says to use `sudo()` after an explicit ownership guard and never add a portal ACL. hr.leave ACLs are `base.group_user` only (`hr_holidays/security/ir.model.access.csv:4`).
- **Two side effects of `sudo()`** (`env.is_superuser()` is true under sudo):
  - `pb_timeoff` `_pb_is_officer` (`leave_rules.py:97`) returns True, so the past-date refusal (141-158) and the lock (283, 298) are skipped.
  - Core `_check_approval_update` (`hr_leave.py:1369`) and the non-officer guard in `write` (905) are skipped too.
  - The past-date bypass on portal applies looks unintended and untested: `test_leave_rules.py` runs as real users.

## 2. hr.leave in this build (`hr_holidays/models/hr_leave.py`)
- **States** (129-134): `confirm`, `refuse`, `validate1`, `validate`, `cancel`. There is **no `draft`**, and the default is `confirm`. `pb_timeoff` relabels them (`hr_leave_approval.py:75-78`).
- **Fields:**
  - `request_date_from`/`to` (212-213).
  - `request_hour_from`/`to`: Float, stored, computed but writable (215-216).
  - `request_date_from_period` / `request_date_to_period`: `am`/`pm`, defaults `am`/`pm` (218-223).
  - `request_unit_half` and `request_unit_hours` are **computed, stored, read-only**, from `leave_type_request_unit` (225-226, 467-475). Half day or hours only happens when the type's `request_unit` is `half_day` or `hour` (`hr_leave_type.py:105-108`).
- **How days are counted:** `_compute_date_from_to` (429-465) turns periods or hours into UTC `date_from`/`date_to`. `_get_durations` (552-630) works from the calendar, so a single half day gives 0.5. `ceil()` applies only to `day` types (627).
- **Cancel and withdraw:**
  - `action_cancel` (1081) opens the `hr.holidays.cancel.leave` wizard (`wizard/hr_holidays_cancel_leave.py:14`), which calls `_action_user_cancel(reason)` (1251), which requires `can_cancel` and then calls `_force_cancel` (sudo, sets state `cancel`, `_post_leave_cancel`).
  - Your own leave can be cancelled only from `validate1`, `validate` or `refuse`, and only if it hasn't started (1342-1345). **`confirm` → `cancel` is not allowed** for the employee.
  - Core's withdraw for a pending request is `unlink`: allowed for non-officers while in `confirm`/`validate1`/`cancel` and not past (945-959).
- **Refuse:** `action_refuse` (1212) needs `confirm`, `validate` or `validate1`. There is also `action_back_to_approval` (1114).
- **Documents:**
  - `attachment_ids` is a One2many on `res_id` (198).
  - `supported_attachment_ids` is computed, not stored, with an inverse (201, 710-732).
  - The type flag is `support_document` (`hr_leave_type.py:113`).
  - A non-officer may still write attachment fields on a begun leave (906).
- **Balance with pending requests:** `get_allocation_data` (`hr_leave_type.py:494`). `virtual_remaining_leaves` subtracts pending requests and supports the `ignored_leave_ids` context. For `hour` types the values are in hours.

## 3. pb_timeoff
- **Lock** (`leave_rules.py:45-51, 266-301`):
  - Fields covered by `SUBSTANCE_FIELDS`: dates, hours, `request_date_from_period`, the unit flags, `number_of_days`, type, employee, name.
  - Fires when the switch `pb_timeoff.lock_past` (default 1; one `ir.config_parameter` per database, not per company), the caller is not an officer, and the leave has started (server date).
  - The same check guards `unlink`.
  - Gap: **`request_date_to_period` is not in the set.**
- **Rize policy** (`rize_policy.py:900-1076`):
  - `pb_policy_medical_ref` is a Char restricted to `hr_holidays.group_hr_holidays_manager` (915), not an attachment.
  - It is checked in `_pb_validate_policy` when a leave moves to `validate1` or `validate` (1026-1031, 1080). An uploaded certificate does **not** satisfy it, so HR still types the reference.
  - Active only when the employee has `pb_leave_policy_id` and a published edition (790-799). Seeding is limited to the `rize` database (193).
- **Command Center queue:**
  - `_leave_card` (`pb_timeoff.py:211-248`) already returns `papers`: up to 4 attachments, with tokened download links (242-247).
  - It renders in `static/src/xml/pb_timeoff.xml:117`. The filter panel has an attachment filter on `attachment_ids` (462-469).
  - Officer actions are `act()` (523) and `apply_on_behalf` (549).

## 4. Approvals inbox
- **Process:** record `key=leave` in `pb_approval_config/data/processes.xml:236-241`.
- **Adapter:** `pb_timeoff/models/hr_leave_approval.py`.
  - `_approval_process_key='leave'` (61).
  - On create, `engine.submit(leave)` runs if the company has an active route binding (`_leave_engine_managed`, 103-113; called at 345-370). `submitter_uid` = `env.uid` (196), which is still the employee under sudo.
  - Default route (490-518): manager, then HR lead.
  - Gotcha: the `days` fact (175) is the only duration, so a half day shows "0.5 days" (265).
- **Withdraw:** `biz.approval.engine.cancel(request, reason)` (`biz_approval_workflow/models/engine.py:1464-1499`).
  - Allowed for the submitter or an admin; closes seats; then calls the record's `_approval_withdraw` (1491).
  - **hr.leave does not override `_approval_withdraw`** (base no-op, `adapter.py:173`), so the leave stays `confirm`. hr_holidays' own cancel also doesn't withdraw the open request, so it would be left pending in the inbox.
  - Inbox wrapper: `pb.approval.inbox.cancel` (`inbox_facade.py:1253`), `can_cancel` (743).
- **"Ask to change/cancel" an approved leave:** there is no existing path. The precedent for a second process key on one model is `_approval_process_keys` / `_approval_process_key_for` (`pb_records/models/records_approval.py:151,268`; `pb_hr_payroll_formula/models/payroll_import_approval.py:60,67`).
- **Showing the attachment to approvers:**
  - The inbox drawer `_detail` (`inbox_facade.py:955-997`) takes text chips and rows only (clipped to 40 characters), with no links.
  - `_evidence` (999) lists route requirements, not files.
  - A new `files` key, or the `pb_me_team` leave context, is needed.
- **Manager area on /my (`pb_me_team/models/pb_me_team.py`):**
  - `approval()` (168-189) adds `_leave_context` (210-248).
  - `_balance_after(leave)` (251-264) returns `virtual_remaining_leaves`, which already includes this pending leave. For the live preview before sending, compute `virtual_remaining − requested days`.
  - Bug: it tests `requires_allocation == 'no'`, but the field is Boolean in v19 (`hr_leave_type.py:88`), so the check never matches.
  - Template: `pb_me_team/views/portal_templates.xml:521`.

## 5. Upload precedents
- **`pb_me_portal` documents:** `/my/documents/upload` (`controllers/portal.py:380-445`).
  - Limits: 10 MB read with a bound, browser-declared type checked against png/jpeg/pdf (41-42).
  - Order: attachment `sudo().create`, then the document, then bind `res_model`/`res_id`.
  - Categories need `ess_uploadable` (`models/employee_document_ext.py:17`, on `pb.employee.document.category`, `pb_employee_vault/models/employee_document.py:36`). There's no seeded medical category.
- **`pb_me_expense` receipts (best to clone):**
  - `sniff_mimetype` checks the file's first bytes for jpeg/png/webp/pdf (`models/me_expense.py:56-68`); `check_receipt` (199-253); attachment created bound to the record (286-292).
  - Two file inputs, one with camera capture: `views/portal_templates.xml:121-141`, including `accept="image/*" capture="environment"` at 139. Read via `_ex_file` (`controllers/portal.py:113-122`). JS size check in `static/src/interactions/expense_form.js:23,187`.
- **Download links for share users** need `access_token` (TIERS_LEDGER T14/T20).

## 6. Withdraw precedents to clone
- **Expenses:** `pb.me.expense.withdraw` (`me_expense.py:392-418`) calls `engine.sudo().cancel(...)` inside a savepoint, plus `_approval_withdraw` on the record (`expense_claim.py:245-255`). Route: `/my/expenses/<id>/withdraw` (`controllers/portal.py:331-341`).
- **Trips:** `pb.me.trip.withdraw` (`me_trip.py:562-575`), route at `pb_me_trip/controllers/portal.py:364-367`. Approved trips are refused with "Ask HR".

## 7. i18n, versions, tests
- **Versions and i18n:**

| Module | Version | i18n files |
|---|---|---|
| `pb_ess_workforce` | 19.0.1.3.2 | `vi.po`, `vi_VN.po` (no `id`) |
| `pb_timeoff` | 19.0.1.10.0 | `id_ID`, `vi_VN` |
| `pb_me_team` | 19.0.1.1.0 | `id_ID`, `vi_VN` |
| `pb_approval_config` | 19.0.1.8.0 | `vi_VN`, `.pot` |
| `pb_me_portal` | 19.0.3.5.3 | `id_ID`, `vi_VN` |
| `pb_me_expense` | 19.0.1.2.0 | `id_ID`, `vi_VN` |
| `biz_approval_workflow` | 19.0.1.7.1 | `id_ID`, `vi_VN` |

- **Tests that cover `apply_leave`:**
  - `pb_ess_workforce/tests/test_p8_portal.py:120,129,200`
  - `pb_ess_workforce/tests/test_p8_adversarial.py:130`
  - `pb_me_portal/tests/test_portal_accounts.py:325` (portal login)
  - Lock tests: `pb_timeoff/tests/test_leave_rules.py:153-201`

## 8. Readers that treat leave as whole days
- **Safe (hour-based):**
  - `om_hr_payroll` `get_worked_day_lines` (`hr_payslip.py:415-449`), from calendar leave hours.
  - `pb_hr_payroll_formula/models/application_payroll_source.py:445-480`, which works in hours (and flags pending leave as an error).
- **Whole-day markers (show the person as away all day):**
  - `pb_attendance_flow/models/attendance_exception.py:43-63` (used at 106-123). This one affects pay inputs: a half-day leave suppresses missing-punch exceptions for the whole day.
  - `pb_schedule/models/schedule_grid.py:226-245, 522-537`
  - `pb_today/models/pb_today.py:163`
  - `pb_hr_workforce/models/shift_planning_grid.py:104`
  - `pb_driver_checkin/models/pb_driver_map.py:95`
  - `pb_timeoff` heatmap and KPIs (`pb_timeoff.py:155-200, 255-296`)
- **Policy maths:** `rize_policy.py:1023` counts `calendar_days` from request dates, so a half day counts as 1 for `counting='calendar'` rules. `_pb_policy_payroll_metrics` (864) errors on `hour` types.
- **Sums `number_of_days` (fractions fine):** `pb_workforce_insights.py:466`.