# WDGAP QF3 — Leave on My Payobook: half days, withdraw, certificate, balance after

Read first: `WDGAP_LEDGER.md` (binding conventions, decisions), then `WDGAP_QF3_FACTS.md`
(verified plumbing, file:line — do not re-derive), then
`docs/handovers/tiers/TIERS_LEDGER.md` (T-R11 sudo rule, T14/T20 tokened downloads) and
`docs/handovers/updates/UPDATES_LEDGER.md` G94–G99 (worktree, portal CSP, test loader).

You are the implementer AND the tester/reviewer of this phase. You do NOT deploy.

## 1. Scope (what an employee gets on `/my/work/leave`)

1. **Half days and hours.** When the chosen kind of leave is counted in half days, the form
   offers "Full day / Morning / Afternoon" (single-day requests; a multi-day request may
   start in the afternoon and end in the morning — use `request_date_from_period` /
   `request_date_to_period`). When the kind is counted in hours, the form offers a from/to
   time on one day. Kinds counted in whole days show today's form unchanged.
   The unit comes from the leave type (`request_unit`); it is NOT a per-request choice
   (FACTS §2). Do not change any leave type's unit in this phase.
2. **Withdraw a request that is still waiting.** A "Withdraw" button on the person's own
   `confirm` / `validate1` rows that have not started. It retracts the open approval and
   leaves the leave in state `cancel` (history kept — do not unlink).
3. **Cancel an approved leave that has not started.** A "Cancel" button with a required
   reason on the person's own `validate` rows whose first day is in the future — the
   platform's own rule (`can_cancel`, `_action_user_cancel(reason)`, FACTS §2). The manager
   is told through the leave's normal message. No new approval process.
   "Change" = withdraw/cancel and ask again; say so in the helper text.
4. **Attach a certificate or document** when asking (two inputs cloned from
   `pb_me_expense`: choose file / take photo), and **"Add a document"** on an existing own
   row that is waiting or approved. Stored as `ir.attachment` on the `hr.leave`
   (`res_model='hr.leave'`, `res_id`), so the Leave Command Center's `papers` already shows
   it (FACTS §3). When the leave type has `support_document`, show the inputs prominently
   with "A document is needed for this kind of leave"; otherwise under "Add a document
   (optional)". Never block sending in this phase.
5. **"After this request" preview.** As type/dates/half-day change, show: days (or hours)
   this request counts, and "After this request: N days left" — computed on the server
   from `virtual_remaining_leaves` minus the requested amount (FACTS §4). Show a calm
   warning line when it goes below zero ("This is more than you have left. You can still
   send it; your approver will see that."). Balance tiles gain a quiet "N waiting for
   approval" line when pending requests exist.
6. **Approver sees it.** `pb_me_team` leave context: list the attached files as tokened
   links; show "Morning" / "Afternoon" / hours next to the dates. In the Approvals inbox
   the leave's own adapter adds a text fact ("1 document attached", "Half day, morning")
   — through `pb_timeoff/models/hr_leave_approval.py` only.

## 2. Binding non-goals

- Do NOT edit `pb_approval_config` or `biz_approval_workflow` (another phase, QF1, is
  editing the inbox in parallel). Everything the inbox shows comes from the hr.leave
  adapter in `pb_timeoff`. Clickable files inside the inbox drawer are a follow-up — list
  it in the report.
- No set-up screen for kinds of leave, no accrual, no comp-off, no new approval process
  key, no "ask to change" flow, no leave letters.
- Do not change the Rize policy medical-reference rule (`pb_policy_medical_ref` stays a
  typed reference HR enters); an uploaded file does not satisfy it. Do not seed policy data.
- No portal ACL for `hr.leave` or `ir.attachment` (T-R11): `sudo()` after an explicit
  ownership guard, as `apply_leave` does.
- Do not touch `pb_pack_*` (ledger D2).

## 3. Safety rails (this is the part that must not be wrong)

R1. **Ownership**: every new method resolves the employee with `_require_own_employee()`
    and refuses a leave whose `employee_id` is not that employee — before any `sudo()` write.
R2. **`sudo()` bypasses the rules (FACTS §1 "two side effects")** — so re-state them
    explicitly for the employee path, in one helper used by apply / withdraw / cancel /
    add-document:
    - past-date refusal: call the same `pb_timeoff` rule a non-officer would hit (find the
      check at `leave_rules.py:141-158` and expose it as a method that takes an explicit
      `as_officer=False`, rather than copying its logic); honour the `pb_timeoff.lock_past`
      switch;
    - withdraw only from `confirm`/`validate1`, not started; cancel only when the record's
      own `can_cancel` would be true for the employee (evaluate it `with_user(employee
      user)` where the user is internal; for portal-tier users replicate: state
      `validate`/`validate1`, `date_from` in the future);
    - add-document: own leave, state in `confirm`/`validate1`/`validate`.
    This also closes the existing hole where a portal apply could back-date a request.
    Add `request_date_to_period` to `SUBSTANCE_FIELDS` (FACTS §3 gap).
R3. **Withdraw must retract the approval**: add `_approval_withdraw` on `hr.leave` in
    `pb_timeoff/models/hr_leave_approval.py` that moves a pending leave to `cancel`
    (`_force_cancel` or the smallest equivalent that fires `_post_leave_cancel`), and make
    the employee path call `biz.approval.engine` `.sudo().cancel(request, reason)` inside a
    savepoint when an open request exists — clone `pb.me.expense.withdraw`
    (`pb_me_expense/models/me_expense.py:392-418`, `expense_claim.py:245-255`). When the
    company has no leave route (not engine-managed), cancel the leave directly. Cancelling
    an APPROVED leave must leave no open request behind either — test both.
    Also make sure a withdraw started from the Approvals inbox ("cancel my request") now
    cancels the leave through the same hook.
R4. **Uploads**: clone `pb_me_expense` exactly — magic-byte sniff (`sniff_mimetype`),
    jpeg/png/webp/pdf only, 10 MB bound read, at most 5 files per leave, attachment created
    with `sudo()` bound to the record, download links for share users carry
    `access_token`. Never trust the browser's declared type or filename (strip paths).
R5. **Half-day readers** (FACTS §8). Required in this phase:
    - `pb_attendance_flow/models/attendance_exception.py:43-63`: a half-day or hour leave
      must NOT suppress the missing-punch exception for the whole day (the person still
      works the other half). Whole-day leaves behave exactly as before.
    - `pb_today` and `pb_schedule` grid: where a leave marks the person "on leave", add the
      label "Half day" (am/pm) when cheap; if not cheap, leave unchanged and list it.
    - Do not change payroll readers (they are hour-based and already correct). List every
      other whole-day reader you did not touch in the report.
R6. **Portal CSP**: no inline `style=`; classes in a `web.assets_frontend` stylesheet
    (ledger G95). The preview uses a small frontend interaction cloned from
    `pb_me_expense/static/src/interactions/expense_form.js`, calling a new JSON route
    `POST /my/work/leave/preview` (`auth='user'`, read-only, own employee only). The form
    must still work with scripts off (server validates everything again on apply).
R7. Fix the Boolean bug in `pb_me_team._balance_after` (`requires_allocation == 'no'`
    never matches; FACTS §4) — with a test.
R8. White-label and plain words; every new string in `vi` and `id` `.po` where the module
    has them (`pb_ess_workforce` has only `vi.po`/`vi_VN.po` — add entries to the file the
    module actually loads; verify with the PO parse gate; do not create an `id` file unless
    the module already ships one elsewhere — report what you did).

## 4. Architecture — exact seams

- `pb_ess_workforce/models/ess_workforce.py`:
  `get_my_leave()` — add per type `unit` (`day|half_day|hour`), `needs_document`; per
  request `can_withdraw`, `can_cancel`, `can_add_document`, `period_label`, `files`
  (name + tokened url); per balance `pending`.
  `apply_leave(type_id, date_from, date_to, note=False, period_from=None, period_to=None,
  hour_from=None, hour_to=None, files=None)` — keep the old positional signature working
  (existing tests call it).
  New: `preview_leave(...)` (no write: build with `new()` or compute through
  `_get_durations`, never create+rollback), `withdraw_leave(leave_id)`,
  `cancel_leave(leave_id, reason)`, `add_leave_document(leave_id, files)`.
- `pb_ess_workforce/controllers/portal.py`: new POST routes
  `/my/work/leave/preview` (json), `/my/work/leave/<int:leave_id>/withdraw`,
  `/my/work/leave/<int:leave_id>/cancel`, `/my/work/leave/<int:leave_id>/document`;
  CSRF as the existing apply route; flash + redirect pattern as `?done=…`.
- `pb_ess_workforce/views/portal_templates.xml:340-409`: form controls, action column on
  "My requests", document chips. Also the leave row in `/my/requests`
  (`pb_me_portal/models/pb_me_home.py:773-787`) — add the Withdraw action only if that
  list already carries actions for other kinds; otherwise leave it.
- `pb_timeoff/models/hr_leave_approval.py`: `_approval_withdraw`; extra facts.
  `pb_timeoff/models/leave_rules.py`: expose the past-date rule; `SUBSTANCE_FIELDS`.
- `pb_me_team/models/pb_me_team.py` `_leave_context` + template `:521`.
- `pb_attendance_flow`, `pb_today`, `pb_schedule`: R5.
- Version bumps: every module touched (ledger convention 6).

## 5. Numbered test cases (write as Odoo tests where marked T; run them)

Put tests in `pb_ess_workforce/tests/test_wdgap_qf3.py` (+ `pb_timeoff/tests/` for the
adapter), tagged so they can be run alone. Use a portal-tier employee AND an internal one.

1. T Whole-day apply still works with the old call signature; existing suites green
   (`test_p8_portal`, `test_p8_adversarial`, `pb_me_portal` `test_portal_accounts`,
   `pb_timeoff` `test_leave_rules`).
2. T Half-day type: morning apply → `number_of_days == 0.5`, `request_date_from_period == 'am'`.
3. T Half-day params on a whole-day type are ignored/refused cleanly (plain sentence).
4. T Hour type: 2 hours → duration in hours; from ≥ to refused.
5. T Preview returns the same amount the created leave gets, and
   `after == virtual_remaining − amount`; preview writes nothing (count hr.leave before/after).
6. T Portal apply with a past date is refused when `pb_timeoff.lock_past` is on; allowed
   when the switch is off (documents the closed hole).
7. T Withdraw pending (engine-managed company): leave → `cancel`, approval request closed,
   nothing left in the approver's inbox. Same for a company with no leave route.
8. T Withdraw someone else's leave → refused; withdraw a started leave → refused;
   withdraw an approved leave → refused with "use Cancel".
9. T Cancel approved future leave with reason → `cancel`; without reason → refused;
   started/past → refused; balance returns.
10. T Inbox-side cancel of a pending leave request also cancels the leave (R3).
11. T Upload: a PDF and a JPEG accepted; an `.exe` renamed `.pdf` refused by magic bytes;
    11 MB refused; 6th file refused; attachment bound to the leave; another employee's
    leave refused.
12. T `pb_me_team` approval context lists the files with tokens and the half-day label;
    `_balance_after` correct for a type that needs no allocation (R7).
13. T Attendance exception: whole-day leave suppresses missing punch (unchanged);
    half-day leave does not.
14. Browser (local copy, Claude in Chrome, sign in by fetch per G99; phone width too):
    apply half day with a photo, see preview change live, withdraw it, cancel an approved
    one; approver view shows the file; console clean; scripts-off apply still works.
15. Static gates: `python -m py_compile` on changed files, XML well-formed, PO parse gate,
    grep the diff for the word "Odoo" in user-visible strings (must be none).

## 6. Working rules

- Work in a NEW git worktree branched from `origin/19.1`, branch `wdgap-qf3`. Local test
  runs: follow the recipe in the latest UPDATES reports (`docs/handovers/updates/UPDATES_P5E_REPORT.md`,
  `UPDATES_P6_REPORT.md`) and ledger rows G12, G19, G35, G97 (free ports; `-u` every
  module whose suite you run).
- Commit feature-scoped with explicit paths; push the branch `wdgap-qf3` to origin. Do NOT
  merge into 19.1 and do NOT deploy — the step's deploy agent does both.
- Commit messages end with: `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`
- If you hit a usage-limit error: one WIP commit, a "Where I stopped" section in the
  report, end with PAUSED.

## 7. Report back — write `docs/handovers/wdgap/WDGAP_QF3_REPORT.md` (commit it) containing

1. What was built, per scope item, with file list and version bumps.
2. Test table: each numbered case → pass/fail with the command and counts; full suite
   counts for every module touched.
3. Self-review against §2 non-goals and §3 rails, rail by rail.
4. Which leave types on a typical database are `half_day`/`hour` (from data files) — i.e.
   whether customers will actually see the half-day option without a set-up change.
5. Whole-day readers left unchanged (R5), follow-ups, and anything that needs an owner
   decision — each written as a plain real-world question.
6. Deploy notes for the deploy agent: modules to `-u`, tier (this phase touches
   access-adjacent portal writes → treat as normal unless you added stored-data changes),
   asset purge needed (yes: frontend assets), any data step.
7. New gotchas → also add rows to `WDGAP_LEDGER.md`.

Final message to the orchestrator: under 250 words — branch, last commit, test counts,
failures or deviations, owner questions.
