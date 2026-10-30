# FILTER wave 7 — Time, trips, leave, claims

Read first: `FILTER_LEDGER.md`, `FILTER_WAVE_COMMON.md`, INVENTORY.md §25–§28.
Wave id `w7`, stage `/tmp/pbf_stage_w7`, preview holder `w7`.
Report: `docs/handovers/filter/FILTER_W7_REPORT.md`.

### 1. Business Trips — `pb_business_trip` (§26)
- `_pbf_model='pb.business.trip'`, screen `trips`, base = company.
- PIN `step` (`state`), PIN `employee`, PIN `department`; `country`
  (`destination_country_id`), `starts` (`date_from`, past+future: presets
  past + custom), `ends`, `policy`, `advance` (money), `cost` (money),
  `manager`, `company`, `mine` (choice via `domain_method` if
  `_can_current_user_act` can be expressed in one query — else glance).
- Views: Open trips · Travelling this month · Awaiting authorisation · With a cash advance · Refused or cancelled.
- Kanban: 5 lanes stay; lane rows = the kit's page rows of that state; lane
  counts = kit `step` counts (R1). The collapsed closed list = the view
  "Refused or cancelled". Unbounded search goes (page 120 for the board).
- Embedded in the Expenses hub: no title (W17).

### 2. Leave Command Center queue — `pb_timeoff` (§27)
- `_pbf_model='hr.leave'`, screen `leavequeue`, base = the queue's domain
  (state in confirm/validate1 + employee company) and the same sudo
  (`_require_officer` gate first: override `pbf_layout` to refuse when it refuses).
- PIN `status` (choice: To approve / 2nd approval / Approved / Refused —
  the built-in view "Waiting for approval" is the default and keeps today's
  behaviour), PIN `type` (`holiday_status_id`), PIN `department`;
  `employee`, `from` (`request_date_from`), `to`, `days` (number),
  `backdated` (choice `pb_backdated`), `papers` (choice
  `supported_attachment_ids != False`), `company`.
- Views: Waiting for approval · Backdated requests · Starting this week · Approved this month · Refused.
- Heatmap and balances stay untouched; approve/refuse reload the page only.
- Learn: `wf-leave-queue` stays; replica `wftime()` draws the queue — add
  the strip; add `coach="'wf-leave-filters'"` + declare.

### 3. Attendance Control › corrections — `pb_attendance_flow` (§25)
- R5: the exceptions queue (engine rows, no model) stays as it is. Convert
  the corrections pipeline: `_pbf_model='hr.attendance.correction'`, screen
  `corrections`, base = what the record rules already allow (no company
  domain beyond today's). Embedded hosts hand week/department/person via
  `wf_context` → `initial` filters (`day` range, `department`, `employee`).
- PIN `status` (`state` choice), PIN `employee`, PIN `department`; `day`
  (`date`), `type` (`correction_type`), `from_exc` (`exception_kind` char),
  `manager`, `company`, `failed` (choice `apply_error != False`).
- Views: Waiting for approval · Applied this week · Failed to apply · Mine to review · All.
- Keep the W21 rule: `_changed()` never runs from `load()`.

### 4. Expense claims lens — `pb_expenses_hub` (§28)
- There is no OWL list today (a native list in a lens). Build a small
  card/table list in the lens: a facade `pb.expense.claims` with the mixin,
  `_pbf_model='pb.expense.claim'`, screen `claims`, base = company +
  the approver gate the lens already applies; row click opens the native
  form exactly as `claims_lens.js` does now.
- PIN `status` (`state`), PIN `employee`, PIN `total` (money; verify
  `store=True` on the preview — if not stored, drop it and note it);
  `department`, `sent` (`submitted_on`), `decided`, `paid`, `receipts`
  (number if stored), `company`.
- Views: Waiting approval (default) · Approved, not yet paid · Paid this month · Refused · Sent this month.
- No bulk (decisions are taken from Approvals). Portal `/my/expenses` untouched.

## Wave-specific tests
- W7-T1 Trips: tick a department → lanes narrow, lane counts match chips.
- W7-T2 Leave queue: approve one request on the preview → it leaves the
  page, counts update, heatmap unchanged.
- W7-T3 Corrections embedded in the Time hub with a pinned person → the
  panel shows the person chip, removable.
- W7-T4 Claims: row click opens the native claim form; back returns with
  filters kept.

## Report back
`FILTER_W7_REPORT.md` per `FILTER_WAVE_COMMON.md §E`.
