# RIZE P4 — pb_offboarding: resignation to final settlement

Read FIRST: `docs/handovers/RIZE_LEDGER.md` + phase-log entries for P0–P3 (APIs, hooks,
automation keys — code wins over this file; reconcile by reading it). Design doc:
`docs/design/rize-hrms-blueprint.html` §04.

## Scope

ONE new module `pb_offboarding` (depends: pb_lifecycle, pb_zoho_bridge, pb_assets,
pb_me_portal; uses pb_hr_fullandfinal):
1. `pb.resignation` — portal submission, manager→HR approval (biz_approval_chain),
   notice-period policy, withdrawal, regrettable flag (HR-only).
2. Full RIZE offboarding journey template (supersedes P0 skeleton): KT/handover, per-dept
   clearances, exit feedback, experience letter, F&F cover, post-exit docs, farewell email.
3. KT/handover items with 15-day HR pings.
4. `pb.exit.clearance` — IT/HR/Finance/Admin clearance board.
5. **Final-settlement guard**: settlement can't be closed while blocking items remain
   (P2 `open_items_for`, clearances, blocking_ff tasks).
6. **"Exits" lens** on the Lifecycle hub: clearance grid + F&F readiness.
7. Portal `/my/resignation` (submit/track/withdraw, exit checklist, feedback form).
8. Experience letter + farewell via P0 letter/mail engines (auto-steps with new
   `automation_key`s following P3's mechanism).

### Binding NON-goals
- No changes to the F&F CALCULATION (pb_hr_fullandfinal math untouched — only a closure
  guard + cover letter). No PIP hooks yet beyond a clean extension point (P6 wires
  auto-terminate). No Payobook→Zoho status push (on hold).

## Verified plumbing facts (do NOT re-derive)
- F&F: `hr.full.final.settlement` in `pb_hr_fullandfinal/models/full_and_final.py:10-129`
  — settlement_date, JSON snapshots, computed breakdown; auto-generated per employee with
  `departure_date` by the payroll batch path
  (`pb_hr_fullandfinal/models/payroll_import_batch.py:19-71`, dedup on settlement_date ==
  departure_date); wizard defaults settlement_date to departure_date; PDF report
  `report/full_and_final_report.xml` (bilingual QWeb canon); employee download button in
  `models/hr_employee.py:10-19`. READ the model for its state/flow — if it has no
  final/confirm state, ADD `pb_closed` Boolean + "Close settlement" button (VU-skinned
  form enhance) whose action runs the guard.
- Departure fields (standard hr): `departure_date`, `departure_reason_id`,
  `departure_description` (`hr/models/hr_employee.py` ~1410-1465; seed reasons Fired/
  Resigned/Retired in `hr/data/hr_data.xml:57-69`). P1 writes departure_date on offboard
  if empty. Resignation approval must write departure_date = approved last working day +
  departure_reason_id = Resigned.
- P0: journey engine + letters + reminder cron + token/feedback routes. P2:
  `pb.asset.open_items_for(employee_id)` + auto-appended return/switch-off tasks on
  offboarding case open (blocking_ff on tangibles). P3: auto-step mechanism
  (`automation_key` on steps — reuse; register new keys 'experience_letter', 'farewell',
  'ff_cover', 'postexit_doc').
- Approval mixin canon: `pb_business_trip/models/pb_business_trip.py:26` (chain config,
  stepper widget in views). Portal change-request canon (employee-initiated + approval):
  `pb_me_portal` profile change requests.
- Notice period: NO existing model. Simple `pb.notice.policy`: country_id, days Integer
  (default 30), company_id — used to prefill requested last working day; HR can override
  on approval.
- Journeys/Exits lens registry + palette ranges: per P0 report (2100s taken by P0, 2200s
  P2, 2300s P3 — use 2400s).

## Architecture

### Models
**`pb.resignation`** — mail.thread + biz.approval.chain.mixin. employee_id (default from
session user's employee for portal creates), submit_date, reason_text, requested_lwd Date
(prefilled today + notice days for employee country), approved_lwd Date (HR sets),
notice_days related/int, regrettable Boolean (groups=HR only, tracked),
departure_reason_id m2o (default Resigned ref), state via mixin (map: employee submit →
manager step → HR step → approved) + 'withdrawn' + 'rejected', case_id m2o (the
offboarding journey opened on approval), source manual/portal/zoho, company_id.
Methods: `action_submit()` (notifies manager+HR), `action_withdraw()` (only before final
approval), on final approval: write employee.departure_date=approved_lwd +
departure_reason_id, open offboarding case (anchor=approved_lwd, source per origin,
idempotent — P1 may have already opened one for a Zoho-initiated exit: attach, don't
duplicate), create clearances, notify employee. Extension point `_on_resignation_approved`
(P6 overrides for PIP auto-terminate).

**`pb.kt.item`** — case_id, topic, from_employee_id (default the leaver), to_employee_id,
doc_link Char, notes, state todo/in_progress/done, company_id. 15-day ping: extend the P0
reminder cron via inherit — while a case has open KT items, email HR every 15 days
(config `pb_offboarding.kt_ping_days` default 15; idempotent stamp last_kt_ping on case
via inherit-added field or an ir.config-free Date on... put `kt_last_ping` Date on the
case via _inherit in this module).

**`pb.exit.clearance`** — case_id required, dept Selection
`[('it','IT'),('hr','HR'),('finance','Finance'),('admin','Admin')]`, owner_user_id
(config params `pb_offboarding.<dept>_user_id` fallback lifecycle managers),
state pending/cleared/na, cleared_at/by, note, company_id. One row per dept created at
case open. `action_clear(note)`.

**F&F guard** (`models/full_final_guard.py`, _inherit hr.full.final.settlement):
`pb_ready` computed: no open blocking_ff journey tasks for the employee's active
offboarding case, no pending clearances, `open_items_for()` empty. Add `pb_closed`
Boolean + `action_pb_close()` raising a PLAIN-ENGLISH UserError naming exactly what's
still open ("2 assets not returned: VN-LT-0003…; Finance clearance pending") when not
ready; on success stamps closed + chatter. Surface `pb_ready` as a chip on the Exits lens
and a banner on the F&F form (view inherit, no `[@string]` xpaths).

### Journey template (seed, replaces P0 skeleton exit template)
Steps: Manager handover plan [manager, lwd−20] · KT tracking [manager, lwd−15, info task
pointing at KT items] · Exit feedback [auto-create pb.feedback.request kind exit at
case open; step marks the chase, hr, lwd−7] · Access/asset returns [auto-appended by P2 —
nothing to seed] · Clearances [created as records, board-driven] · Experience letter
[auto 'experience_letter', lwd+1] · F&F cover letter [auto 'ff_cover', fires when
settlement pb_closed] · Post-exit documents [hr, lwd+30, automation_key 'postexit_doc' —
just a reminder task] · Farewell email [auto 'farewell', lwd+0, gated
`pb_offboarding.farewell_mail` default '0' until tested; HR-editable draft: the step's
task payload holds the message, cockpit lets HR edit before the day].

### Exits lens (Lifecycle hub)
Facade `pb.exits` get_board(): rows = active offboarding cases {employee, last working
day, days left, resignation state, KT open count, clearance grid (4 dots), assets
outstanding count, F&F readiness chip, feedback submitted?}; kpis (leaving this month,
blocked settlements, overdue clearances); facets (country, month, dept). Row actions:
clear a clearance (if owner/HR), open case, open F&F record, nudge KT. Clearance-grid
cells click → clear dialog with note. ⌘K 2400s.

### Portal `/my/resignation`
- No active resignation: a considered, calm page — notice policy shown for my country,
  expected last working day auto-computed, textarea reason, Submit (confirmation modal:
  "your manager and HR will be notified").
- Active: status timeline (submitted → manager → HR → approved), approved LWD, Withdraw
  (while allowed), my exit checklist (my visible tasks: feedback form link, document
  downloads pointer to /my/documents & /my/payslips), farewell note.
- `/my` counter via `_prepare_home_portal_values`.
- Security: portal creates go through a controller (route-boundary sudo, employee from
  session) — model ACL for portal users read-own via
  `[('employee_id.user_id','=',user.id)]` rule; approval writes stay internal.

## Safety rails
- NEVER auto-close an F&F; the guard only GATES a new explicit close action.
- Never write departure_date over an existing different value (align with P1's rule) —
  raise a review note instead.
- Farewell + any team-wide mail behind config param, default OFF during tests.
- Test with @example.com employees end-to-end; do NOT submit resignations for demo/real
  employees — create 2 disposable test employees and clean up.
- Deploy `-i pb_offboarding` (+ `-u pb_hr_fullandfinal` only if you inherit-add fields
  there — you will: the guard fields → include it).

## Numbered test cases
T1. Deploy clean.
T2. Portal: as test employee, submit resignation → manager + HR mails queued; status page
    shows the chain; withdraw works pre-approval (then resubmit for the rest).
T3. Approve as manager then HR (stepper) → departure_date + reason written; offboarding
    case opened (once), clearances created (4), exit feedback request created; asset
    return tasks appended for the employee's test assets (assign one first).
T4. Notice policy: requested LWD prefilled = today + country days; HR overrides
    approved_lwd → case anchor uses the approved date.
T5. KT: add 2 KT items; force the 15-day ping (manipulate kt_last_ping) → ONE HR mail;
    run again same day → no duplicate.
T6. Clearances: clear IT+HR+Admin, leave Finance → F&F record (create via existing wizard
    for the test employee) shows NOT ready; `action_pb_close` raises the plain-English
    error naming Finance + unreturned asset.
T7. Return the asset (P2), clear Finance → pb_ready true; close works; F&F cover letter
    auto-step fires (letter generated + vault-filed).
T8. Experience letter auto-step at lwd+1 (force-run) → PDF letter from P0 template,
    ${...} substituted, vault-filed, mail queued to employee.
T9. Exit feedback token page: submit as the leaver (logged out) → stored; lens shows
    "feedback ✓"; regrettable flag editable by HR only (verify a non-HR internal user
    can't see/write it).
T10. Farewell: with param '0' → skipped honestly; set '1', HR edits the draft in the
    cockpit, force-run → ONE mail to the department, capped.
T11. Exits lens: board correct (clearance dots, F&F chip states), row actions work,
    ⌘K entries navigate; light+dark screenshots.
T12. Zoho-origin exit (P1 simulated resignation payload) → case + clearances appear, NO
    duplicate when the same employee also has a portal resignation (attach behaviour).
T13. Withdraw-after-approval is refused with a friendly message.
T14. White-label grep zero; plain English throughout.
T15. Regressions: P0/P2/P3 lenses load; onboarding case flow unaffected; F&F PDF still
    renders for an untouched historical settlement.
T16. Clean up test employees/records; report leftovers + final param states.

## Deliverables / report back
Commits, per-test results, deploy EXIT, deviations, ledger gotchas, new automation_keys,
the `_on_resignation_approved` extension-point signature (P6 needs it), Exits lens
registry entry + palette numbers, and the F&F guard behaviour documented for P7's
finance-pack step.
