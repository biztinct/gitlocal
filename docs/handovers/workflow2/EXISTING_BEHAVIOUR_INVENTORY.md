# WORKFLOW-2 P0 — Existing behaviour inventory

**Date:** 11 November 2026 · **Branch:** `19.1` (baseline `c3f3993cd`) · **Read-only.** No code, no server, no database was touched.
**Feeds:** P2 module contract ("stages, what moves a record, what already happens") and the owner's overlap questions (ruling R2/R2a in `WF2_LEDGER.md`).

Conventions: citations are `path:line` from the repo root. **[inferred]** marks a statement not read directly in source. Engineering vocabulary is used in Parts 1–2; Part 3 is plain English for the owner. White-label rule (R7) applies to anything copied from here into a screen.

---

## 0. Ten facts that shape everything else

1. **Approval is attached in three shapes, all ending in the same engine.** (a) direct adapter (`biz.approval.adapter.mixin`, `biz_approval_workflow/models/adapter.py:19`) — pay run, leave, timesheet week, letters, F&F, overtime, pay-delivery files; (b) the **chain shim** (`register_chain(...)`, `biz_approval_workflow/models/chain_shim.py:63`) over the old fixed ladder (`biz_approval_chain/models/biz_approval_mixin.py:65`) — 21 record types; (c) proposal records (`biz.approval.proposal.mixin`) — contract change, new hire, verdict, records desk. 50 process keys are registered (list in §1.7).
2. **The chain shim is dormant when a company has no active route.** No binding → the record's own hard-coded ladder and group checks run (`chain_shim.py:211-232`, `:533-536`). With a binding → every button becomes an engine decision. So *the same record type behaves two ways depending on Matrix setup*.
3. **Module side effects still fire under the engine.** The shim calls the consumer's `_after_approval_transition` on freeze / advance / apply / reject (`chain_shim.py:440-521`). Anything a module does there (to-dos, emails) runs *in addition to* the engine outbox.
4. **The engine outbox never reaches employee (portal) logins.** `_queue` returns nothing for `user.share` (`biz_approval_workflow/models/outbox.py:70`); the submitter is `env.uid` (`chain_shim.py:365`). Requests sent from /my therefore get no engine "Approved / Turned down" message; only the module's own email (if any) reaches the employee.
5. **Outbox to-dos sit on the approval request, not on the business record** (`outbox.py:116-122`).
6. **Lifecycle (`pb.journey.*`) has one daily job and five modules ride it** (`pb_lifecycle/models/lifecycle_reminders.py:50`; extended by onboarding, offboarding, probation, PIP, contract lifecycle).
7. **Hiring owns a full automation product**: 19 events × 4 actions as editable rules plus 16 listed built-ins (`pb_hiring/models/automation_p8.py:53-160`), its own candidate-message store in three languages, its own forms and scorecards.
8. **`base.automation` is used only by Workflow Studio** (only `pb_lifecycle/__manifest__.py:68` depends on it; no other custom module references it).
9. **A per-module stage list already exists**: the employee home "My requests" registry declares, for each request type, its status values, a label and a tone (`pb_me_portal/models/pb_me_home.py:739-862`, extended by `pb_me_expense/models/pb_me_home.py:48`, `pb_me_trip`, `pb_ask_hr`).
10. **Several modules knowingly double-message approvers** (pay change, overtime, contract extension, org chart plan, resignation, goals, probation, stock leave). Listed in §3 items 2–3.

---

## Part 1 — Record types with a status

### 1.1 Expense claim — deep

| | |
|---|---|
| Model / module | `pb.expense.claim`, `pb_me_expense` (`models/expense_claim.py:84`). Lines are stock `hr.expense` (`pb_claim_id`). |
| Status field | `state`, fixed selection (`expense_claim.py:46-52`, field `:119`): `draft` Draft → `submitted` Waiting approval → `approved` Approved → `paid` Paid; exit `refused` Refused. Dead states `('refused','paid')` (`:100`). Declaration order puts Refused before Paid. |
| Subject person | `employee_id`. Manager for the route = `employee.expense_manager_id` else `parent_id.user_id`, internal active users only (`:256-266`). |
| Approval | key `expense`; chain shim, `submit_state='submitted'`, `driven=('approved',)` (`:66-73`); default route manager → Finance role (`:76-81`, seeded `:408`). |

Transitions:

| From → to | Who / verb | Engine? | Already happens |
|---|---|---|---|
| draft → submitted | Employee on /my: `pb.me.expense.send` (`me_expense.py:372-390`) writes `approval_state='submitted'` on lines, then `action_submit` → `_advance_state` (`expense_claim.py:403`). Lays a default route first if none (`me_expense.py:356-370`). | Yes when a route is bound; else legacy ladder, no group needed (`:95-99`) | Stamps `submitted_on` (`:194`). Engine outbox `your_turn` + to-do on the request for each seat (`engine.py:1083-1087`, `outbox.py:116`). [inferred] Stock "Review this expense" to-do is *not* created because stock `action_submit` is bypassed (ledger E1). |
| submitted → approved | Last approver in inbox; legacy: group `hr_expense.group_hr_expense_team_approver` (`:97`) | Engine `_complete`→shim `_approval_apply` | Lines `_do_approve` as the decider (`:197-201`); `decided_on`. Outbox `approved` to submitter (`engine.py:1138`) — not delivered to a portal employee (fact 4). |
| submitted → refused | Approver with reason (`action_refuse` `:394`; reason mandatory) | Engine reject | Lines `_do_refuse` → stock posts "refuse reason" message per expense (`hr_expense/models/hr_expense.py:1457`); outbox `rejected` (`engine.py:1389`). |
| submitted → draft | Sent back (engine return) or withdrawn by employee (`me_expense.py:393`) | Engine | Lines reset (`expense_claim.py:203-216`), reason kept; outbox `returned` (`engine.py:1362`). |
| approved → paid | Nobody presses it: every line reaches stock paid/done (`_sync_paid` `:370-380`, triggered from `hr.expense.write`, `hr_expense.py:58-65`) | No | `paid_on`; trail row. **No message to the employee** [inferred: none found]. |

Screens: back office `pb_expenses_hub` (`static/src/js/expenses_hub.js:81`); employee `/my/expenses/<id>` and "My requests" labels (`pb_me_expense/models/pb_me_home.py:48-66`). No cron.

### 1.2 Leave (time off) — deep

| | |
|---|---|
| Model / module | stock `hr.leave`, extended by `pb_timeoff` (`models/hr_leave_approval.py:51`) |
| Status field | stock fixed selection (`hr_holidays/models/hr_leave.py:129-135`): `confirm` To Approve, `validate1` Second Approval, `validate` Approved; exits `refuse` Refused, `cancel` Cancelled. No draft. |
| Subject / manager | `employee_id`; manager = `leave_manager_id` else `parent_id.user_id` (`hr_leave_approval.py:221-226`), same as stock (`hr_leave.py:1448-1460`). |
| Approval | direct adapter, key `leave`. Default route: manager step if the leave type asks for a manager, HR-lead step if it asks for an officer, escalation role `hr_lead`, escalate days param `pb_timeoff.escalate_days` (`:380-420`). Types set to "no validation" never reach a route. |

Transitions: **create in `confirm` auto-submits to the engine** when a route is bound (`:314-332`). Approve/Refuse buttons are re-pointed to one engine decision (`:334-378`); engine apply calls stock `action_approve` *as the last approver* (`:258-284`). Reject/return → stock `action_refuse` + note (`:286-311`). Officer cockpit verbs `approve`/`refuse` (`pb_timeoff/models/pb_timeoff.py:520-540`).

Already happens:

| Event | Effect | Source |
|---|---|---|
| Created/confirmed | Stock to-do "New … Request" to the leave manager (and second-approval to-do) | `hr_leave.py:1465-1519` |
| Same, with route | Engine `your_turn` message + to-do on the request | `engine.py:1083` |
| Approved | Stock message "Your … has been accepted" to the employee; balance consumed (stock); outbox `approved` to submitter | `hr_leave.py:1036`; `engine.py:1138` |
| Refused | Stock message "… has been refused"; outbox `rejected` | `hr_leave.py:1226`; `engine.py:1389` |
| Backdated request | To-do + email `pb_timeoff.mail_backdated_leave` to HR lead (switch per leave type `pb_backdate_alert`) | `leave_rules.py:172, 206-247` |
| Monthly | Carry-forward warning emails to employee/manager (`mail_carry_forward`) | `carry_watch.py:126, 262-279`; cron `pb_timeoff_config.xml:58` |
| Daily | Year opening of authorised balances | `policy_year_opening.py:93`; cron `policy_year_opening_views.xml:8` |
| Stock jobs | Accrual allocation, cancel invalid | `hr_holidays/data/ir_cron_data.xml:4,13` |

Screens: `pb_timeoff` (`static/src/js/pb_timeoff.js:349`), `pb_time_hub` (`time_hub.js:406`); manager area on /my reads the inbox and adds balance-after (`pb_me_team/models/pb_me_team.py:210-266`).

### 1.3 Pay run, payslip, pay delivery — deep

| | |
|---|---|
| Model | `hr.payslip.run` (base `om_hr_payroll`), extended by `pb_payruns` (`models/hr_payslip_run.py:153`) |
| Status | selection **replaced** (`:51-56`, `:207`): `draft` Draft → `approval_pending` Waiting for approval → `done` Done; exit `cancel` Rejected (board shows no column for it, `:60`). Old `level1/level2` states closed with refusals (`:1398-1408`). |
| Subject | none (a batch); makers = `pb_prepared_uid` + slip authors (`:226-230`). |
| Approval | direct adapter, key `payrun` (`:159`). |

Transitions: submit `action_approval_submit` / `done_payslip_run` (`:1226, :1392`); freeze → slips `verify`, run `approval_pending` (`:1098-1110`); apply → slips done, legacy accounting post for structure payroll only (`:1112-1154`); return → draft with note (`:1156-1168`); reject in inbox → cancel all slips (`:1170-1202`); preparer's own Reject with mandatory reason withdraws the request (`:1324-1366`); reopen `draft_payslip_run` (`:1410-1430`). Already happens: engine outbox only — **the module sends no message of its own** (no `message_post`/mail in `pb_payruns`). Screens: `pb_payruns` board (`static/src/js/payruns.js:1162`), Run payroll `pb_payrun_wizard` (`payrun_wizard.js:1246`), `pb_pay_hub`.

Payslip `hr.payslip.state` (`om_hr_payroll/models/hr_payslip.py:53-60`): `draft`, `verify` Waiting, `level1`/`level2` (dead), `done`, `cancel` Rejected — driven only by the run.

After the run, `pb_pay_delivery` has four separately approved records, each its own key: payslip sending `payslips` (`payslip_delivery.py:47`; Draft → Waiting for approval → Sending → Done, exits Sent back/Turned down; on apply emails each payslip through a template `:245`), bank file `bankfile` (`bank_file.py:39-46`, adds "Replaced by a newer file"), payment release `release` (`payment_release.py:32-38`), payroll journal `journal` (`payroll_journal.py:39-45`). Screen `pb_pay_delivery` (`pb_pay_delivery.js:313`).

### 1.4 Hiring — deep

**Candidate (`hr.applicant`)** — stage = `stage_id` → `hr.recruitment.stage` **rows**, made special by `pb_key` (17 fixed keys) and computed `pb_family` open / done / closed (`pb_hiring/models/journey.py:20-38, 172-186`). Names, order and one-line meanings are the client's (renames survive upgrades, `:191-240`). Order: Applications received, Shortlist, Hiring manager review, Recruiter review, Assignment, Discussion 1–3, Reference check, Offer, Post-offer, **Joined** (done); closed: CV reject, Interview reject, Drop-out, On hold, Offer drop. "Always on" and "hidden by default" sets (`:42-45`); per-role stage presets `pb.hiring.stage.preset` (`board_p1.py:69`).

- Move: one door `pb.hiring.act('journey_stage', …)` (`pb_hiring.py:601`; body `board_p1.py:261-330`, layered in `facade_p5.py:51`, `hooks_p8.py:289`, `registers_p9.py:290`). Only gate: **Joined cannot be set by hand** (`board_p1.py:281-284`), it comes from "Confirm they joined" on the offer. Reason kept on closed stages, hold date on On hold, chatter note on reason/undo (`:296-312`); optional "not this time" email on CV/Interview reject (`:315-320`). Stage rename/meaning/reorder verbs (`board_p1.py:1064-1077`).
- Already happens on entering a stage: Hiring rule dispatcher `_fire('stage_entered')` from `hr.applicant.write` (`hooks_p8.py:56-65`) → seeded rule "enter Recruiter review → send Let's chat (Calendly)" (`automation_p8.py:166`); arranging an interview round can move the stage (`requisition.py:66-71`). Full event list in §2.2.
- People: candidate (`partner_name`), recruiter (`user_id`), hiring manager, talent lead (`automation_p8.py:100-106`).
- Screens: `pb_hiring_board`, `pb_hiring_hub`, `pb_hiring_setup` (rules, emails, forms, scorecards), `pb_hiring_forms`, `pb_hiring_numbers`.

**Role / hiring request (`pb.hiring.requisition`)** — two fixed facets (`hiring_common.py:151-171`): role `state` Being set up → Open for candidates → Filled / Closed; request `request_state` No request yet → Waiting on the manager → Being written → Sent in → Head of HR agreed → Agreed; exit Not approved. Key `hiring_request`, shim on `request_state` (`requisition_approval.py:37-41`). Verbs `create`, `submit`/`send_in`, `request_agree`, `request_decline`, `open_role`, `close`, `mark_filled` (`pb_hiring.py:615-690`). Events `request_sent_in`, `request_agreed` (`hooks_p8.py:250-257`); 9 mail templates (`data/mail_template_requests.xml`).

**Offer (`pb.hiring.offer`)** — fixed (`hiring_common.py:380-392`): Being prepared → Sent for sign-off → Hiring manager agreed → Agreed → With the candidate → Accepted → Signed → They have joined; exits Turned down, Did not join, Not approved. Key `hiring_offer`, shim drives `manager_ok`, `hr_ok` (`offer_approval.py:39-42`). Sending emails the letter (built-in "offer"); signed → Post-offer, "Before they join" list laid out, manager and talent lead told (`joining_p6.py:1-30`). **Confirm they joined** creates employee, contract, pay package, login and opens the onboarding journey (`offer_closure.py:70, 157-441`; journey via `pb_zoho_bridge/models/zoho_pipeline.py:560-582`).

**Other hiring rows** (fixed selections, `hiring_common.py`): interview Arranged / Done / Nobody came / Called off / Moved (`:240-246`, reminders day-before and 30-min via 10-minute job); "Before they join" item To do / Done / Not needed / Called off (`:433-438`); cover Being written → Sent in → Agreed → Covering now → Finished, exit Not agreed (`:503-510`, key `hiring_cover`); JD Draft/Final (no approval; key declared `None`, `jd_approval.py:28`); referral, posting, document request, background check, panel feedback, agency submission (each own small selection).

### 1.5 Joiner and leaver journeys — deep

**Journey engine (`pb_lifecycle`).** Template `pb.journey.template` + steps (`journey_template.py:15-127`): anchor (journey open, joining date, last working day, probation end, key date), offset days, owner rule (HR, HRBP, Manager, Buddy, IT, Finance, Admin, Employee, Joiner, Specific person), kind (Task, Confirmation, Form, Automatic email, Letter), `blocking_ff`, `escalation_days`, `mail_template_id`, `letter_template_id`, `form_questions_json` (`lifecycle_common.py:9-60`).
- Case `pb.journey.case` state fixed (`lifecycle_common.py:63-69`): Draft → Running → Finished; On hold; Cancelled. Verbs `action_open/done/cancel/hold/resume/back_to_draft` each post a chatter line (`journey_case.py:263-357`). Opening generates tasks and resolves owners once (`:278-321`; unresolved owners fall back to the creator with a chatter note).
- Task `pb.journey.task` state To do / In progress / Blocked / Done / Skipped (`lifecycle_common.py:55-61`); verbs done/skip/start/block/unblock/**reassign** (`journey_task.py:130-176`). Confirmation and Form steps get a **token link** for people without a login (`journey_task.py:61-117`, pages `/journey/t/<token>` and `/journey/f/<token>`, `controllers/token_pages.py:79-141`).
- Daily job `cron_lifecycle_reminders` (`data/ir_cron.xml:10`, `lifecycle_reminders.py:50-241`): to-do on the case + email `mail_template_task_reminder` for steps due within `remind_days` (default 2); after `escalation_days` overdue, email `mail_template_task_escalation` to all lifecycle managers + chatter note, once; check-in-today email; feedback requests closed when their window ends and a last-day invite. Switch `pb_lifecycle.reminders_enabled`.
- Check-ins `pb.employee.checkin` Planned / Done / Missed / Cancelled (`checkin.py:47`); feedback requests `pb.feedback.request` Waiting / Answered / Closed / Extended with JSON questions (text, rating, choice) and token page (`feedback.py:52-60`) — reused by training, probation, PIP.
- Letters `pb.hr.letter` Draft → Ready → Sent (`letter.py:103`); **sending** goes through key `letters` (HR lead) (`letter_approval.py:1-54`); templates `pb.letter.template` (`letter.py:57`).
- Screens: `pb_journeys`, `pb_lifecycle_hub`.

**Automation handler tables** (a step with `automation_key` runs itself on its due date; runner `pb_onboarding/models/onboarding_automation.py:64-90`, deliberately *not* behind the reminders switch):

| Module | Handlers (`_automation_handlers`) | Other daily additions |
|---|---|---|
| `pb_onboarding` | `credentials`, `poster`, `day1_ics`, `buddy_invite`, plus any `email` step sends its template (`journey_ext.py:70-81, 143-321`) | plan and send new-joiner one-tap checks (pulses) (`onboarding_automation.py:44-48`) |
| `pb_offboarding` | `experience_letter`, `ff_cover`, `farewell`, `postexit_doc` (`offboarding_automation.py:51-58`) | backfill clearances; handover (KT) reminder at 15 days (`:282-360`) |
| `pb_probation` | — | open reviews inside lead time (switch `auto_trigger`, off on install); HR nudges at 15 and 5 days (to-do `:181`); close shut answer windows; **plus an hourly cron** "answer window closes today" (`data/ir_cron.xml:20`, `probation_automation.py:266-297`) |
| `pb_pip` | — | missed check-ins; plans past end date → to-do to HR owner, not moved (`pip_automation.py:40-110`) |
| `pb_contract_lifecycle` | — | raise contract decisions (switch, off on install), escalate unagreed extensions once, daily nudge last week, lapse undecided (`contract_automation.py:52-300`) |

**Resignation `pb.resignation`** (`pb_offboarding/models/resignation.py:128`): Draft → With the manager → With HR → Approved; exits Not accepted, Withdrawn (`offboarding_common.py:40`). Key `resign`, shim drives `manager_ok`, `approved` (`resignation_approval.py:29-32`). Filed → email `resignation_filed` to manager + HR (`:292-303, 559-563`). Approved → stamp leaving date on the employee (to-do if it conflicts, `:387-420`), open the leaving journey (`:429-490`), clearances, email employee `resignation_approved` (`:360-384, 571-575`). Withdrawn → email. Screen `pb_exits_board`. Exit clearance Waiting / Cleared / Not needed; handover items To do / In progress / Handed over (`offboarding_common.py:24-31`).

**Full & final `hr.full.final.settlement`** (`pb_hr_fullandfinal/models/fnf_approval.py:39-50`): Being prepared → Waiting for approval → Approved; Sent back, Turned down. Key `fnf` (HR lead → finance). Download blocked until approved (`:211-220`). Journey steps flagged `blocking_ff` block it (`pb_offboarding/models/full_final_guard.py`). No own messages.

**Probation review `pb.probation.review`**: Scheduled → Peers being chosen → Feedback running → Consolidating → Manager 1:1 → Awaiting decision → Closed (`probation_common.py:41`). Verdict: `pass` immediate; fail/extend/terminate go through key `verdict` as `pb.verdict.proposal` (`verdict_approval.py:1-45`). **In addition**, a built-in gate `pb_gate` Manager evaluation → HR lead review → CEO review / Changes requested → Approved with reviewers from the country probation policy, to-dos to the reviewer and chatter notes, and the comment "bypasses the earlier proposal engine" (`review_journey.py:54-56, 196-262`). Fail/terminate opens a leaving journey (`probation_review.py:1042`). Screen `pb_probation_board`.

**PIP `pb.pip.case`**: Requested → Coaching → Plan running → Being evaluated → Completed successfully / Not successful / Closed — left the company (`pip_common.py:16`); verbs take up, coaching, start plan, acknowledge, evaluate, verdict (via `verdict`), start exit, terminate (`pip_case.py:329-1011`), each with chatter lines. Screens `pb_pip_board`, `pb_pip_request`.

**Onboarding extras**: buddy nomination Being chosen → Chosen → Confirmed / Cancelled (email to buddy `buddy_nomination.py:362`); new-joiner pulse Planned → Sent → Answered / Cancelled (red flag → to-do `newhire_pulse.py:280`); orientation batch Upcoming → Held / Cancelled. Screen `pb_onboarding_board`.

### 1.6 Other record types (compact)

"Shim" = chain shim (fact 2); "drives" = statuses the route moves. Effects listed are the module's own, *on top of* the engine outbox.

| Record (model) | Status values (exits in *italics*) | Approval key | Module's own effects / jobs | Screen |
|---|---|---|---|---|
| Pay change `pb.pay.change` | Being written → With HR → With finance → With the CEO → Approved → Applied → Closed; *Sent back* (`pb_pay/models/pb_pay_change.py:40`) | `paychange`, shim drives hr_review/finance/approved | **to-dos to up to 10 members of the next group on every rung, also under a route** (`pb_pay_change.py:345-365`); apply writes contract, undo window, letter queue (cron `pb_pay/data/ir_cron.xml:31`) | `pb_pay` |
| Pay review `pb.pay.review` | same ladder (`pb_pay_review.py:58`) | `payreview` | same to-do pattern (`pb_pay_review.py:508`) | `pb_pay` |
| Pay bands | — | `bands` | nightly band position (`pb_pay/data/ir_cron.xml:18`) | `pb_pay` |
| Contract change `pb.contract.proposal` | proposal states | `contract` (proposal mixin) | apply re-checks terms (`pb_contracts/models/contract_approval.py:1-60`) | `pb_contracts`, `pb_contract_detail` |
| Contract extension | Being written → Waiting to be agreed → Agreed; *Turned down* (`contract_extension.py:38`) | `extension`, shim | **email `extension_ask` + to-do to approver, own deadline and own one-time overdue escalation email** (`:150-175, 234-260`) | `pb_contractlife_board` |
| Contract review | Waiting → Decision needed → Extension requested / Evaluation running → Decided; *Ended undecided* (`contract_common.py:23`) | — | lifecycle daily job (above) | same |
| New hire (employee + contract) | proposal | `newhire` | — | `pb_onboard_wizard` |
| Timesheet week `pb.timesheet.packet` | Not sent in → Waiting for approval → Approved; *Sent back*, *Turned down* (`timesheet_packet.py:41`) | `timesheet` direct | apply seals hours for payroll (`:637`) | `/my` timesheet; Workforce |
| Attendance correction | Draft → Submitted → Applied; *Refused* (`attendance_correction.py:77`) | `correction`, shim | apply writes attendance (`attendance_correction_approval.py:154`) | `pb_attendance_flow` |
| Overtime `hr.overtime.request` | Draft → Submitted → Approved; *Refused* (`pb_hr_workforce/models/overtime_request.py:76`) | `overtime` direct | **to-do to line manager on submit, then engine submit** (`overtime_request.py:189-197`, `overtime_request_approval.py:321-333`) | `pb_ot_desk` |
| Business trip | Draft → Submitted → Manager Approved → Finance Approved → Authorized; *Refused*, *Cancelled* (`pb_business_trip.py:65`) | `trip`, shim | warning note (`:210`) | `pb_trips`; /my trips |
| Asset request | Draft → Waiting for the manager → Manager approved → Approved; *Turned down*, *Cancelled* + second field fulfilment To arrange → … → Confirmed by employee (`asset_common.py:66-83`) | `assets`, shim | created by laptop journey step (`joining_p6.py:1270-1292`) | `pb_assets` |
| Profile change / bank change | Draft → HR Review (→ Finance Review) → Approved; *Refused* | `master` / `bankchange`, shim | apply writes employee / bank (`pb_profile_change_request.py:351`, `pb_bank_change_request.py:319`) | /my; `pb_bank_ocr` |
| Goal sheet `pb.goal.set` | Being written → Waiting on their manager → Waiting on the HR lead → Agreed and locked → Finished; *Sent back*, *Turned down* (`goals_common.py:140`) | `goal_set`, shim | **own emails locked / returned / manager-review (the last "a second message, behind its own switch")** (`goal_set.py:546-567`); daily reminder job (`pb_goals/data/ir_cron.xml:27`) | `pb_goals_board` |
| Goal change | … → Agreed and carried out; *Turned down* (`goals_common.py:219`) | `goal_change`, shim | own agreed / refused emails (`change.py:355-454`) | same |
| Training request / claim / more-time | Not sent yet → Waiting … → Agreed (→ Taken → Claimed back); *Turned down*, *Cancelled* (`training_common.py:225-310`) | `training_request`, `training_claim`, `training_delay`, shim | delay email (`delay.py:160`), claim email (`claim.py:523`) | `pb_training_board` |
| Training assignment / path enrolment | Not started → Under way → Overdue → More time agreed → Finished (computed) / path adds Taken off (`training_common.py:202`, `path.py:60`) | — | daily job assigns required courses, runs schedules, opens next path step, chases late (`automation.py:58-90`); feedback + 30-day manager follow-up via `pb.feedback.request` (`feedback.py:1-25`) | `pb_training_board` |
| Award `pb.comp.incentive` | Being prepared → Waiting for approval → Approved; *Not approved* + fulfilment Approved → Letter sent → In next pay run → Paid (`comp_common.py:96-115`) | `awards`, shim | award letter email (`incentive.py:187`) | `pb_comp_ben_incentives` |
| Recognition nomination | Being written → With their manager → With HR → Decided; *Not this time* (`rnr_common.py:86`) | `recognition`, shim | decision email (`nomination.py:371`); celebrations jobs (`pb_rnr/data/ir_cron.xml`) | `pb_rnr_board` |
| Announcement `pb.hr.comm.post` | Being written → Waiting on the HR lead → Scheduled → Going out now → Sent; *Cancelled* (`comm_common.py:90`) | `hr_comm_post`, shim drives `scheduled` | sends by mail every 10 min, nudges owner daily (`pb_hr_comm/data/ir_cron.xml:27,37`); shows on the employee notice board (`pb_me_portal_comm/models/notices.py:1-10`) | `pb_hr_comm_home` |
| Org chart plan | Being planned → Waiting for approval → Approved → Live; *Turned down*, *Discarded* (`pb_orgchart_plan.py:52`) | `orgplan`, shim | **to-do per live seat** (`:301-316`); daily apply on effective date (`pb_orgchart/data/ir_cron.xml:10`) | Org chart |
| Ask HR question `pb.ask.hr.ticket` | New → With HR → Answered → Closed (`ticket.py:56-61`) | none | to-do for the HR owner on create and hand-over (`:220, :291`); a public reply moves the state (`:227-256`) | Home lens `askhr` (`askhr_lens.js:547`); /my |
| Access request | own selection (`biz_access/models/pb_access_request.py:89`) | `roles` | — | Access |
| Records desk change | Being prepared → Waiting for approval → Carried out; *Sent back*, *Turned down* (`records_approval.py:59`) | `records` | — | `pb_records_desk` |
| Payroll month, unlock, filing, FX, mappings, schemes, statutory, pay data loads, arrivals, tenant, support | various | `month`, `unlock`, `filing`, `fx`, `mappings`, `schememap`, `scheme`, `statutory`, `runonly`/`loads`, `arrivals`, `tenant`, `support` | payroll-setup records; out of scope for Studio stages | — |
| "Other request" `biz.approval.generic.request` | Draft → Waiting for approval → Approved and done; *Sent back*, *Turned down*, *Withdrawn* (`generic_request.py:14-21`) | `generic` | ask anyone for a sign-off from the inbox (`inbox_facade.py:1287-1331`) | Approvals inbox |

### 1.7 All registered approval keys (50)

`assets correction bankchange trip unlock awards month extension contract goal_set goal_change filing fx hiring_request hiring_offer hiring_cover hr_comm_post fnf schememap statutory mappings runonly loads scheme demo overtime letters expense master resign orgplan paychange payreview bands journal release payslips bankfile payrun newhire verdict records recognition support tenant leave timesheet training_delay training_claim training_request arrivals roles generic workflow_studio` (constants grepped from each `*_approval.py`; Studio's own is `pb_lifecycle/models/workflow_models.py:232`).

---

## Part 2 — Engines and shared services

### 2.1 Approval engine, Approval Matrix, approvals inbox

| Piece | What it does | Where |
|---|---|---|
| Engine `biz.approval.engine` | resolve binding, submit, step activation with **cover** (`delegation.covering`) at the moment a step opens, decide (approve / return / reject, independence rule, exceptions), reassign, cancel, repair | `biz_approval_workflow/models/engine.py:57, 842, 1039-1094, 1179-1395, 1397-1540` |
| Request / step / seat | request states Not sent yet, Waiting for a decision, Approved, Done, Sent back, Turned down, Withdrawn, Stuck (`request.py:13-22`) | `request.py` |
| Outbox `biz.approval.outbox` | 9 fixed kinds: your turn, reminder, overdue, sent back, approved, turned down, exception used, covering, for your information (`outbox.py:18-28`). Delivered every 5 min as a chatter notification on the **request** plus a to-do for your-turn / reminder / overdue / returned (`:103-123`). Texts are fixed in code (`:31-43, 125-156`). Refuses portal and inactive users (`:70`). | cron `data/ir_cron.xml:17` |
| Late handling | hourly: remind after `remind_days` (1), escalate after `escalate_days` (2) to a named responsibility's holder+backup or the route owner, then optionally **pass to the seat's backup** (`engine.py:1560-1688`) | cron `ir_cron.xml:27` |
| Notify step | a route step kind "tell someone" (`engine.py:1013-1036`) | — |
| Responsibilities | role holder + **backup** + dates per company/scope (`responsibility.py:21-42`); catalogue roles (`role.py`) | Matrix "People" |
| Delegation | "covering for" with dates, one hop only, revocable (`delegation.py:35-126`) | Matrix + /my "I'm away" (`pb_me_team.py:753-815`) |
| Legacy ladder | `biz.approval.chain.mixin` transition table + trail `biz.approval.step.log` (`biz_approval_chain/models/biz_approval_mixin.py`) | dormant when routed |
| Matrix facade `pb.approval.matrix` | routes per process and scope, draft/preview/coverage/publish, people and backups, delegations, history, bulk "No approval needed" and undo, scheme panel (`pb_approval_config/models/matrix_facade.py:207-1352`) | client action `pb_approval_matrix` |
| Inbox facade `pb.approval.inbox` | tabs mine / all / returned / done, scopes me / team / org, decide, move, repair, cancel, team data, dock `act`, **"ask for a sign-off"** (`inbox_facade.py:33-44, 355-1331`) | `pb_approval_inbox`; reused by Home queue (`pb_home_hub/models/team_facade.py:201, 432`) and manager area on /my (`pb_me_team.py:1-20, 135-208`) |

### 2.2 Hiring automations, messages, forms, scorecards

- **Rules** `pb.hiring.automation.rule` (`automation_p8.py:194`): "When ⟨event⟩ (for these departments/countries) ⟨action⟩ ⟨now / after N hours⟩". Events (19): applies, enters a stage, waited in a stage, interview arranged / done / no-show, all opinions in, papers complete, check started, offer sent / accepted / declined / signed, joins, did not join, request sent in / agreed, referral, agency (`:53-73`). Actions: send email, to-do, move candidate, tag (`:94-99`). Recipients: candidate, recruiter, hiring manager, talent lead, addresses (`:100-106`). Run log `pb.hiring.automation.run` (`:672`). Depth cap 2 (`:115`). Dispatcher `_fire` (`:538`), queue `_run_queue` / `_run_waiting` (`:627-670`) on the 10-minute and daily hiring jobs (`:1067-1088`). Four seeded rows (`:166-180`). Editor: Hiring set-up → Automations (verbs `rule_save/toggle/delete/try`, `builtin_switch`).
- **Built-ins** (16, listed beside the rules with their switch, `:117-160`): application received, interview invitation, day-before/half-hour reminders, opinion chase + talent lead, papers in → recruiter to-do, papers reminders, check started to-do, offer email, close remaining finalists as Future-fit, week-before check, joined notice, recruiter assigned, referral, referral announcement, share notice, agency first look. Night nudges in `pb.hiring.automation` (`hiring_automation.py:38-80`).
- **Candidate messages** `pb.hiring.message.template` per company, per language (English / Vietnamese / Bahasa), one sender `_mail_candidate` (`comms_p8.py:1-25`, `journey.py:543`); internal emails stay standard templates (≈43 `mail.template` records in `pb_hiring/data/mail_template_*.xml`). Editor: Hiring set-up → Emails and languages.
- **Forms** `pb.hiring.form` / `.form.field` (`forms_p2.py:244, 659`): kinds, help, options, required, word limits, file kinds, three languages; per role copy/restore; client action `pb_hiring_forms`.
- **Scorecards** `pb.hiring.scorecard` / `.part` (`scorecards_p5.py:96, 225`), criteria `pb.hiring.criterion`, panel feedback (`panel_feedback.py:48-113`).
- Also: stage-visibility policy, retention rules, Google calendar notifications (1-minute cron), job boards (5-minute), connections (5-minute).

### 2.3 Lifecycle journeys

See §1.5. Additional services: token pages for no-login people (`controllers/token_pages.py`), `.ics` builder reused by Hiring (`models/ics.py`), letters library + approval, check-ins, feedback requests (house pattern for any short questionnaire with a deadline).

### 2.4 Other rule / reminder / notification engines and every custom cron

| Module | Job (name in data) | What it does | Moves records? |
|---|---|---|---|
| biz_approval_workflow | Approvals: tell the people who are waiting (5 min) | deliver outbox | no |
| biz_approval_workflow | Approvals: remind and pass up what is late (1 h) | remind / escalate / backup | reassigns seats |
| pb_lifecycle | Lifecycle: daily reminders (1 d) | §1.5 + five riders | runs auto steps; closes feedback; probation/contract triggers |
| pb_lifecycle | Workflow Studio: progress active runs (1 min) | Studio runs | yes (runs) |
| pb_probation | the answer window closes today (1 h) | alerts | no |
| pb_hiring | daily chase; interview reminders (10 min); boards (5 min); connections (5 min); calendar (1 min) | §2.2 | rules may move candidates; covers start/end |
| pb_goals | remind people whose goals are not in yet (1 d) | reminders | no |
| pb_training | daily (assign, schedules, paths, chase); training pack (1 d) | §1.6 | creates assignments |
| pb_hr_comm | send due announcements (10 min); remind owner (1 d) | sending | post → Sent |
| pb_rnr | birthdays/anniversaries; manager week ahead; monthly digest (1 d each) | emails | no |
| pb_comp_ben | payroll calendar cut-off reminders (1 d) | emails | no |
| pb_orgchart | make approved plans live (1 d) | apply | plan → Live |
| pb_pay | band positions (1 d); print waiting pay letters (10 min) | compute, letters | no |
| pb_timeoff | carry-forward warnings (1 mo); year opening (1 d) | emails; balances | balances |
| pb_employee_vault | document expiry check (1 d) | to-do on employee (`employee_document.py:254`) | no |
| pb_vendor_access | agreements running out (1 d) | alerts | no |
| pb_clock | pair punches (5 min); watch machines (15 min); re-check (15 min) | attendance | yes |
| pb_workseg, pb_scheme_map, pb_budget, pb_explorer, pb_decision_room, pb_hr_payroll_formula, pb_payroll_ai_insights, pb_hr_payroll_base | payroll / analytics computations | no workflow effect | — |
| biz_access | take back ended hand-overs (1 d); close leavers' logins (1 d); Access Studio expiry (1 min) | access | yes |
| pb_tenants, pb_demo_portal, pb_zoho_sso, biz_audit_trail, biz_doc_ocr, biz_geo_tracking, pb_learn | platform / housekeeping | — | — |

`pb_contract_lifecycle`, `pb_onboarding`, `pb_offboarding`, `pb_pip` have **no cron of their own**; they ride the lifecycle job. `pb_ask_hr`, `pb_me_expense`, `pb_assets`, `pb_business_trip`, `pb_attendance_flow` have **no reminder job at all** — lateness for them is only the engine's.

Other rule engines: training requirements and compliance schedules (`pb_training`); attendance rules `pb.attendance.rule` (late/missing-punch, `pb_attendance_flow/models/attendance_rule.py:35`); leave-type switches (`leave_rules.py:56-82`); Integrations Rule Composer (data mapping, not workflow; `pb_integrations/static/src/js/rule_composer.js`); PayAI "does it" actions (`pb_payai_actions`, can submit records, e.g. `actions_amber.py:2332`). `pb_hr_flow` is a static payroll dashboard named "HR Workflow Flow" (`pb_hr_flow/__manifest__.py`), not an engine.

### 2.5 `base.automation`

Used only by Workflow Studio for event capture. No other custom module creates or depends on it.

### 2.6 Catalogues of distinct mechanisms

| Kind | Distinct ones |
|---|---|
| Form / question builders | (1) Hiring application forms (`forms_p2.py`); (2) Lifecycle step questions JSON, 3 types (`journey_template.py:122`); (3) feedback request questions JSON (`feedback.py:56`), reused by training feedback and probation peers with hard-coded SOP questions (`review_journey.py:10-30`); (4) Studio forms JSON, 12 types (review F17); (5) Training tests on the standard survey + question bank (`question_bank.py`); (6) Hiring scorecards; (7) new-joiner one-tap pulse (fixed). |
| Condition / rule builders | (1) Matrix route conditions `{fact, op, value}`, 8 operators (`definition.py:30-40`); (2) filter panel sections (`pb_filter_kit`); (3) Studio nested conditions, 13 operators + domain compiler; (4) Hiring rule scope (departments, countries, stage, days); (5) Training requirements; (6) attendance rules; (7) Integrations rule composer (data). |
| Inbox / "my work" surfaces | (1) Approvals inbox + Home queue + /my manager area (one engine, three views); (2) standard Activities (to-dos on records **and** on approval requests); (3) Studio "My tasks"; (4) Hiring "Waiting on you" filters (`filters_w3.py:347, 859`); (5) Ask HR queue lens; (6) Journeys board; (7) employee "My requests" (own requests only). |
| Message / template stores | (1) standard email templates (most modules, Studio's shared editor); (2) Hiring candidate messages, 3 languages; (3) letters library `pb.letter.template`; (4) announcement templates `pb.hr.comm.template`, copied on use (`template.py:1-15`); (5) approval outbox fixed texts (not editable); (6) hard-coded chatter sentences in every module. |
| Delegation / backup / cover | (1) approval cover `biz.approval.delegation` (Matrix + "I'm away"); (2) responsibility backup + late pass-to-backup; (3) Access hand-overs `pb.access.delegation` (lends permissions, `biz_access/models/pb_access_delegation.py:1-35`); (4) Hiring cover `pb.hiring.cover` (a recruiter's roles, itself approved); (5) journey step manual reassign; (6) Ask HR "Hand to…" (`ticket.py:302`). Studio tasks honour none of them (review F4). |
| In-app notices | Announcements → employee notice board (`pb_me_portal_comm`); chatter notifications; approval outbox notifications. |

---

## Part 3 — Overlaps for the owner

Plain English. Each item: what overlaps, options, recommendation. Technical detail is in the Part 1–2 block named in brackets.

**1. Two ways of approving the same thing.** Expense claims, trips, equipment requests, timesheet fixes, bank and profile changes, resignations, pay changes and pay reviews, goals, hiring requests and offers, awards, recognition, training requests, announcements, org chart plans and contract extensions each still carry an old built-in approval ladder. If the company has no Approval Matrix route for that kind of request, the old ladder runs; if it has one, the Matrix runs. Probation has a third case: its decision goes through a fixed "HR lead, then CEO" check *and* can also go through the Matrix. [1.1, 1.5 Probation, 1.6, fact 2]
- Options: (A) make the Matrix the only way — every company gets a default route, the old ladders are switched off; (B) keep both, and Studio shows whichever is live for that company; (C) keep both but fold Probation's fixed check into the Matrix.
- **Recommendation:** B now (Studio just reads which one is live), and decide A + C as a separate clean-up. Studio must never add its own approval in either case.

**2. Approvers are told twice.** When a request reaches someone, the Matrix already sends "Your approval is needed" with a to-do. Several areas also send their own to-do or email to the approver: pay changes and pay reviews (to up to 10 people in the group), overtime (to the line manager), contract extensions (email, to-do, and their own overdue email), org chart plans, resignations (email to manager and HR), goals (an extra email to the manager, behind a switch), time off (the standard time-off to-do), probation (to-do to the reviewer). [1.2, 1.6, 1.5]
- Options: (A) when a Matrix route is live, only the Matrix tells approvers; switch the others off; (B) keep both; (C) leave it per area with a switch, like Goals.
- **Recommendation:** A. It removes noise without losing anything, because the Matrix message also escalates and covers absences. Needs your yes because people will receive fewer messages.

**3. Requesters are told twice, and employees sometimes not at all.** For time off, goals, resignations and goal changes, the area sends its own "approved / turned down" message and the Matrix sends another to the person who sent it. But the Matrix never writes to people who sign in as employees on the employee home, so for anything an employee asks for there (expenses, trips, equipment, resignations), only the area's own message reaches them — and expense claims send none at all when approved or paid. [fact 4, 1.1, 1.2]
- Options: (A) the area owns the message to the requester; the Matrix stops sending its "approved / turned down" when the area already does; (B) the Matrix learns to write to employees and the areas stop; (C) leave as is.
- **Recommendation:** A, plus fill the gaps (expense approved, expense paid) inside the Expense area. Studio shows these as "already happens" and warns if a designer adds the same message.

**4. Three separate chasers for late work.** Approvals remind after a day, pass up after two and can hand to a backup. Joiner and leaver checklists remind two days ahead and email the lifecycle managers when overdue. Hiring chases late opinions and missing papers. Training, goals and contract extensions have their own chasers. Workflow Studio tasks have none and turn into an error when late. [2.1 Late handling, 1.5 daily job, 2.4]
- Options: (A) Studio tasks reuse the approvals chaser (remind → pass up → backup); (B) Studio gets its own; (C) Studio reuses the checklist chaser.
- **Recommendation:** A. It already handles cover and backups and has a schedule. Leave the Hiring, checklist, training and goals chasers where they are; they chase different things. Separate question: contract extensions chase twice when a Matrix route is live — keep only one.

**5. Too many places to find "what I need to do".** Approvals inbox (also shown on Home and in the manager area of the employee home), the standard Activities list, Studio "My tasks", Hiring "Waiting on you", the Ask HR queue and the checklist board. Studio's own tasks show up in Activities but cannot be completed there. [2.6 Inbox]
- Options: (A) add Studio tasks to the existing approvals inbox, so Home and the manager area get them for free; (B) keep "My tasks" separate; (C) build a new "My work" page over everything.
- **Recommendation:** A. The inbox is already the one list three screens use.

**6. Four kinds of "someone covers for me".** Approval cover ("I'm away" and People & backups), lending access, Hiring cover between recruiters, and moving a checklist step by hand. Studio tasks honour none. [2.6 Delegation]
- Options: (A) Studio tasks follow approval cover and backups; (B) Studio gets its own cover.
- **Recommendation:** A. Leave access lending and Hiring cover as they are — they do different jobs (permissions, a recruiter's whole roles).

**7. Several question-form builders.** Hiring application forms, checklist step questions and feedback questionnaires, Studio forms, training tests, interview scorecards. [2.6 Forms]
- Options: (A) Studio's form is the general one; checklist questions move onto it later; Hiring application forms, scorecards and tests stay; (B) Studio reuses the checklist questionnaire instead.
- **Recommendation:** A, as the review proposed. The checklist questionnaire has only three answer types and Studio's has twelve.

**8. Several condition builders.** Approval routes ("amount over 5 million"), list filters, Studio conditions, Hiring rule scope, training requirements, attendance rules. [2.6 Conditions]
- Options: (A) Studio uses the same single-condition shape as approval routes and only adds "and / or" grouping; (B) keep Studio's own.
- **Recommendation:** A, so a condition reads the same on the Matrix and in Studio.

**9. Hiring already has its own "when this happens, do that".** Hiring automations cover 19 events (applies, enters a stage, offer signed, joins…) with emails, to-dos, moves and tags, plus 16 built-in messages. A Studio workflow on hiring candidates could send the same email twice. [2.2]
- Options: (A) Hiring automations stay the owner; Studio shows them in place and refuses a second one for the same event; (B) move Hiring automations into Studio; (C) let both run.
- **Recommendation:** A now. B only if you want one tool for all "when … then …" later; it is a large migration.

**10. Getting a new joiner ready is split between Hiring and the joining checklist.** Hiring's "Before they join" list asks for a buddy, laptop preferences and meet-the-team chats; the joining checklist also names a buddy, raises the laptop request and sends a day-one invite. Joiner checklists are also meant to move into Studio eventually. [1.4 Offer, 1.5]
- Options: (A) Hiring owns everything before day one, the checklist owns day one onward; (B) the checklist owns all of it from the signed offer; (C) leave as is.
- **Recommendation:** A, written down as the boundary Studio respects when joiner checklists move into it. Needs your decision.

**11. Several message libraries.** Standard email templates, Hiring candidate messages in three languages, the letters library, announcement templates (copied when used), and the fixed approval messages that nobody can edit. [2.6 Templates]
- Options: (A) Studio uses standard templates, but for candidate messages uses Hiring's library, and copies a template into the workflow by default; (B) one new library.
- **Recommendation:** A. "Copy when used" already works for announcements, so it is a known pattern.

**12. In-app notices.** Studio's proposed "in-app notice" step would do what Announcements already do (they appear on the employee notice board). [2.6 Notices]
- **Recommendation:** Studio's notice step creates an announcement for the chosen people rather than a second notice board.

**13. Letters.** Letters are made by checklists, pay changes, awards, leavers' steps and the letters screen, and sending one already needs approval. Studio's proposed "create a letter" step overlaps. [1.5 Letters]
- **Recommendation:** Studio creates the letter through the letters library and the sending approval stays as it is.

**14. "Ask for a sign-off on anything" versus a new Studio process with only an approval.** The approvals inbox already lets anyone ask for a sign-off on something with no record type. A brand-new Studio process that is just "ask, then approve" does the same. [1.6 Other request]
- Options: (A) a one-step sign-off stays "Other request"; Studio new processes are for several steps; (B) retire "Other request" into Studio.
- **Recommendation:** A.

**15. The list of statuses per area already exists once.** The employee home "My requests" already says, for each kind of request, its statuses in friendly words and colours. Studio's per-area stage list (next phase) would be a second copy. [fact 9]
- **Recommendation:** build the next phase's per-area stage list on top of that one, so the employee home and Studio always say the same words.

**16. Joiner and leaver steps that run themselves.** Checklists already send emails, create logins, posters, day-one invites, experience letters, farewells and settlement cover letters on their due dates. Studio "send email" steps on the same people would repeat them. [1.5 handler tables]
- **Recommendation:** until checklists move into Studio, Studio shows these as "already happens" for employees with a running checklist and warns on a repeat.

**17. Name clash.** An old payroll dashboard is called "HR Workflow Flow". Low priority; rename or retire so nobody confuses it with Workflow Studio.

---

## Part 4 — Not determined

- **Which companies have live Matrix routes** for which keys, in which of the four databases. Code only shows the switch; whether a record type runs on the old ladder or the Matrix is a data question (overlap 1).
- **Which switches are on** (e.g. `pb_lifecycle.reminders_enabled`, `pb_probation.auto_trigger`, `pb_contract_lifecycle.auto_trigger`, each Hiring built-in, goals manager email). Defaults are in code; live values are not.
- Whether the stock expense "Review this expense" to-do is ever created on the claim path [inferred: no].
- Whether `mail.activity` creation in the lifecycle reminder also sends its own email next to the reminder template [inferred: yes, it is created without `mail_activity_quick_update`, `lifecycle_reminders.py:127`].
- Legacy per-country payroll modules (`pb_hr_payroll_cambodia` … `thailand`, version 16.0) were skipped as not part of the current design.
- Platform modules (`pb_tenants`, `pb_vendor_access`, `pb_zoho_*`) were listed only for their jobs.
