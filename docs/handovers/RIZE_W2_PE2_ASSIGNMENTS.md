# RIZE Wave 2 — Phase E2: `pb_training` assignments, reminders, delay reasons, probation link

E1 is live and the owner has looked at the learner flow. E2 makes training
something HR ASSIGNS and the system CHASES: day-one mandatory courses for new
joiners, probation-linked courses that the probation verdict still gates on,
recurring compliance courses, ad hoc / leadership programmes, reminders and
escalation, and the employee's "I need more time" request with a reason the
manager approves. Bump `pb_training` to `19.0.1.1.0`; the delay route ⇒ a
migration.

Read first: `RIZE_LEDGER.md` (all), `RIZE_W2_HANDOVER.md` A/B/C5,
`RIZE_W2_PE1_TRAINING_LEARNER.md` §1, **the E1 report's API row in the
ledger's Wave 2 table**, then this file. Read the E1 code before writing.

---

## 0. Scope and non-goals
**In scope:** `pb.training.assignment` (+ bulk assign), reasons (day-one /
probation / compliance / ad hoc / leadership), due dates, enrolment on
assignment, completion mirrored from E-Learning + the test, reminders to the
employee and escalation to manager and HR (idempotent), the delay request
with a route (manager), recurring compliance schedules, the day-one
automation key on the joiner journey, the probation-gate link, `/my/training`
due dates + "Ask for more time", a manager's team view, the HR lens
"Assignments" tab, ⌘K 3940/3950.
**Non-goals (E3):** budget claims → pay run, analytics lens, the weekly /
monthly report pack, certificates into the vault. Do not change E1's learner
pages beyond the due-date/reason/delay additions. Do not touch
`pb_probation`'s code — link through data (§2.4).

## 1. Verified facts
- **E1 API:** as reported (`pb.my.training` reads/writes, the enrol helper,
  "every lesson done", survey link fields) — take names from the ledger row.
- **E-Learning membership:** `slide.channel._action_add_members(partners,
  member_status='joined')`; `slide.channel.partner.member_status`
  (`completed` when 100 %), `completion`, `completed_slides_count`
  (`slide_channel_partner.py:13-20`); certification result on
  `slide.slide.partner.survey_scoring_success` / `user_input_ids`
  (`website_slides_survey/models/slide_slide.py:10-11`),
  `survey.user_input.scoring_percentage / scoring_success` (:53/:55).
- **Automation keys:** `pb.journey.task._automation_handlers()` returns a
  dict; a later module overrides, calls `super()`, adds its key
  (`pb_onboarding/models/journey_ext.py:70-80`; contract note
  `onboarding_common.py:15-30`, `AUTOMATION_KEYS` list :26-32 — check
  whether `pb.journey.template.step.automation_key` is a Selection over it
  (then `selection_add` your key) or a Char). Steps run on their due date
  via `action_auto` (:96); a template step needs the key and R31 says
  `_generate_tasks` now copies it. The RIZE joiner template and its Day-1
  step: `pb_onboarding/data/journey_template_data.xml:111 step_rize_day1`
  (`automation_key day1_ics`). Add YOUR step to that template from
  `pb_training/data/` (a `<record>` on `pb.journey.template.step` with
  `template_id` ref to the seeded template — find its xmlid in the same
  file; sequence right after Day 1; `automation_key = 'training_day1'`).
  Existing running cases do not get new steps (R31) — say so.
- **Probation gate:** `pb.probation.review._check_training_gate()`
  (`probation_review.py:833`) reads `pb.training.status.pending_required_for(employee)`
  (`pb_probation/models/training.py:215`). Rows: `pb.training.track`
  (:39 `name, job_ids, item_ids, company_id, active`), `pb.training.item`
  (:139 `track_id, name, required, company_id`), `pb.training.status`
  (:164 `employee_id, item_id, track_id (related), required (related),
  state todo/done, score, done_at, note, company_id`; `action_done(score)`
  :198, `action_reopen` :209). `ensure_for_employee` (:105) spreads a track
  to everyone whose JOB is in `job_ids` — so a track you create for one
  assignment must have `job_ids` EMPTY (:88-92 says a job-less track is
  never spread).
- **Reminder job precedent:** `pb_employee_vault/models/employee_document.py:227`
  (`_cron_expiry_check`), `pb_lifecycle/models/lifecycle_reminders.py`
  (`_remind_due_tasks` :108, `_escalate_overdue_tasks` :148 — mail helper
  `_mail(xmlid, record, email_to)` :81). Address helpers read the employee
  as the system (R56/R104). Mail explicit `email_to` (R6). Server clock
  (R36). Log-only first run for anything that writes to people (R54).
- **Route seed:** A1's `requisition_approval.py` is the newest adapter;
  `_approval_manager_uids` → the employee's manager (`employee_id.parent_id.user_id`,
  AM50). Process key `training_delay`.
- **Actors:** learner ess1.demo (uid 1984, employee 10080, company 5; its
  manager — set `parent_id` to employee 17122 (lam.ngo, uid 2326) for the
  test if empty, demo data D9); HR = validator; a second learner ess2.demo
  (employee 9884, password `RizeP2!2026`, re-set R74). New joiner test:
  create "RIZE W2 Joiner" through the connected-system path (the P10 intern
  recipe, `RIZE_LEDGER.md` R112) so the joiner journey opens with your
  step.

## 2. Models and rules
### 2.1 `pb.training.assignment`
`channel_id` (course), `employee_id`, `partner_id` (related sudo),
`reason` (day_one / probation / compliance / adhoc / leadership),
`due_date`, `assigned_by_id`, `assigned_on`, `schedule_id` (compliance),
`state` assigned → in_progress → done | overdue | excused (computed +
stored by the daily job and by the E1 completion path: `in_progress` when
any lesson done, `done` when member_status completed AND — if the course
has a certification — the test passed; `overdue` when past due and not
done; `excused` while an approved delay moves `due_date`), `completed_on`,
`score` (latest `scoring_percentage`), `counts_for_probation` (bool, set by
reason probation, editable), `status_id` (`pb.training.status`, §2.4),
`reminder_log` (Text/JSON: keys sent), `company_id`. Unique per
(channel, employee, open) — a second assignment while one is open is
refused with a sentence; a finished one may be re-assigned (compliance).
On create: enrol the partner (`_action_add_members`, `joined`), mail the
employee AND their manager ("training start" template, one each), an
activity for the employee's user if any. Bulk: `assign_many(channel,
employee_ids, reason, due_date)` on the facade; people picker folds
accents (R78); department / job / "everyone in company" expanders.

### 2.2 Reminders and escalation (daily job 06:00, `pb_training.reminders` 1)
Employee: 3 days before, 1 day before, on the day, then every 3 days while
overdue. Manager: when 2 days overdue, then weekly. HR (`hr_lead`
responsibility holders for the company, via the Matrix roles; fallback
`group_training_manager`): when 5 days overdue, then weekly. Each key sent
once (`reminder_log`); caps as parameters (R76); counts logged honestly.
Course completion stops everything. Excused assignments are not chased
until the new due date.

### 2.3 Delay request (`pb.training.delay`)
`assignment_id, reason_kind` (sick / emergency / other), `note`,
`days_asked`, `state` draft → submitted → approved | refused; route
`training_delay` = `manager_step(_('Their manager'))`; facts: reason kind,
days asked; approval moves `due_date` by `days_asked`, state `excused`,
mails the employee; refusal keeps chasing. From `/my/training`: "Ask for
more time" (reason, days, note). The HR lens shows open delay requests.

### 2.4 Probation link (data, not code)
When `counts_for_probation` is set (reason probation, or ticked): ensure a
`pb.training.track` "Assigned training" (per company, `job_ids` EMPTY,
`active`), an item named after the course (`required=True`), and a
`pb.training.status` row for the employee (`state='todo'`) linked via a
new `assignment_id` field on `pb.training.status` (inherit in
`pb_training`). Completion → `status.action_done(score)`; re-open →
`action_reopen`. `_check_training_gate()` keeps working unchanged: an
unfinished probation course blocks the pass by name. Assignments that do
not count leave no status row.

### 2.5 Day-one mandatory
`pb.training.rule` (company, `reason` day_one, `channel_ids`, `due_days`
14, optional job/department filter, `active`). Handler `training_day1`:
for the joiner of the task's case, create one assignment per rule course
(idempotent: skip existing open ones); no rule ⇒ the task settles with
"no day-one courses set up" in `auto_error`-style note, never raises.
Switch `pb_training.day1_auto` **0** by default (D17-style: off until the
owner points it at a real course; when 0 the handler settles the step
with a note and logs what it WOULD have assigned, R54).

### 2.6 Compliance schedules (`pb.training.schedule`)
`channel_id, audience` (company / department / job / everyone), `every_months`
(12), `due_days` (30), `next_run`, `active`, `last_run`. Daily job: when
`next_run <= today`, create assignments for the audience (skip people with
an open one for this schedule period), stamp `last_run`, roll `next_run`.
Ships with none (blueprint switch "Compliance schedules OFF").

### 2.7 Screens
- HR lens (Learn → Training): new **Assignments** tab: rows (person,
  course, reason chip, due, state chip problem-first R113, score), facets
  (reason, state, department, course), bulk "Assign a course" dialog, "Ask
  for more time" requests list with the route state, schedules panel,
  rules panel (day-one). Hero tiles: overdue · due this week · waiting on
  a manager (delays) · done this month.
- `/my/training`: each tile shows reason, due date, "N days left / overdue
  by N", "Ask for more time"; a delay's state; the team view
  `/my/training/team` for a session employee who manages people (their
  reports' assignments and states, read as system, company-scoped).
- Home card for managers: "Training · N of your team overdue" (eager key).
- ⌘K: `training_assignments` 3940 ("Training assignments"),
  `training_schedules` 3950 ("Compliance schedules").
- Switches: `pb_training.reminders` 1, `pb_training.day1_auto` 0,
  `pb_training.manager_escalate_days` 2, `pb_training.hr_escalate_days` 5,
  `pb_training.default_due_days` 14.

## 3. Tests
T1  Unit + gates; migration lays `training_delay` once.
T2  Assign the E1 course to ess1.demo (adhoc, due in 10 days): enrolled,
    two mails (employee, manager 17122), state `assigned`; assigning again
    refused with a sentence.
T3  Completion mirror: finish the lessons → `in_progress`; pass the test →
    `done`, `score`, `completed_on`; a course WITHOUT a test → `done` at
    100 % completion.
T4  Reminders: due in 3 days → employee mail once; run again → none; move
    due to yesterday → overdue; +2 days → manager mail once; +5 → HR mail
    once; complete → nothing more (assert the log keys).
T5  Delay: ask 5 days (sick) → the manager (uid 2326) sees it in the inbox;
    approve → due +5, `excused`, employee mailed, no reminders until the
    new due; refuse → chasing resumes.
T6  Probation link: assignment with `counts_for_probation` → status row
    todo; open a probation review for the employee (P5 recipe) and try
    `pass` → refused naming the course; complete the course → status done
    with score → pass allowed; an assignment without the flag creates no
    status row; `ensure_for_employee` on a random employee creates nothing
    from the assigned-training track.
T7  Day-one: rule (company 5, the E1 course, 14 days) + `day1_auto=1`; a
    connected-system arrival opens the joiner journey with your step; the
    step runs on its due date → one assignment, due in 14 days, mails
    sent; rerun → no duplicate; with `day1_auto=0` the step settles with
    the note and assigns nothing.
T8  Compliance: schedule (department 657, every 12 months, 30 days) with
    `next_run` = yesterday → the job creates one per member of the
    department, rolls `next_run` a year, run again → none.
T9  Bulk assign 3 people by department through the facade; the accent-
    folded search finds "Bùi" by "bui".
T10 `/my/training` shows due/reason/overdue and the delay form; the team
    view as lam.ngo lists ess1.demo's row; a non-manager gets the empty
    state; the manager Home card counts.
T11 HR lens Assignments tab light + dark, screenshots `RIZE/w2_e2_*.png`,
    no console errors, `unhandledrejection` listener.
T12 ⌘K 3940/3950; deploy `19.0.1.1.0`, crons active, log clean.
T13 Reverts (groups, seats, passwords), mails cancelled; test data stays
    (the joiner, assignments, the probation review) named RIZE W2.

## 4. Report back
As E1, plus the assignment/delay/schedule API for E3 (fields, facade
verbs, how `done` and `score` are computed, the status-row link), cron
xmlids, switches, the template step xmlid you added, new R-entries, ledger
row, owner items (day-one rule and compliance schedules to set up, real HR
addresses).
