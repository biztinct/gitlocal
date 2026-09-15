# RIZE Wave 2 — Phase B1: `pb_goals` foundations

New module. Cycles, goals with key results, the Day-1 kick-off for new
joiners, the one route employee → manager (weightage) → HR lock, the
employee's `/my/goals`, the **Goals** lens on the People hub. B2 adds monthly
check-ins, mid-year / joining-month logic, change requests after lock,
scoring roll-ups, the Insights lens and the Home card — do not start those.

Read first: `RIZE_LEDGER.md` (all, through the newest R), `RIZE_W2_HANDOVER.md`
A/B/C2, the A1 handover §1.2 (adapter canon) and A1's `requisition_approval.py`
(the newest adapter, with `_leg()` savepoints R131 and the intermediate-state
lesson R132), then this file. Version `19.0.1.0.0`, `post_init_hook` seeds
the route + a migration file (as A1).

## 0. Scope and non-goals
**In scope:** `pb.goal.cycle`, `pb.goal`, `pb.goal.kr`, the `goals_kickoff`
automation key on the joiner journey (2-week deadline, reminders), the
`goal_set` route (manager weights + approves, HR lead locks) with SLA
escalation through the route, visibility rules (own / team / HR), goal
templates, editable mail templates with an HR sender address, `/my/goals`
(create, edit until submitted, progress on key results), the People hub
**Goals** lens (seq 70) with the manager's team view and HR's cycle view,
⌘K 3600–3630, switches, tests, deploy.
**Non-goals (B2):** monthly check-ins, mid-year/joining-month applicability,
change requests after lock, scoring aggregates and year-end archive, the
reports lens, the Home lens, the manager-compliance report.

## 1. Verified facts
- **Adapter canon:** `biz_approval_workflow.models.chain_shim` —
  `register_chain(model, key, submit_state, driven, draft_state, refuse_state,
  reverse_to, employee_field, amount_field, currency_field, date_field)`
  (:63), `manager_step(title, key, condition, kind)` (:97), `role_step(title,
  role, key, scope, condition, …)` (:104), `route(*steps, independent=True,
  due_days=2, reassign=False)` (:120 — the safeguards block carries `late:
  {remind_days: 1, escalate_days: 2}`; the engine's `escalate_cron`
  (`engine.py:1551`) escalates after `escalate_days`; **the SLA the sheet
  asks for IS this** — expose `pb_goals.sla_days` and pass it as
  `due_days`, and set `late.escalate_days` from `pb_goals.escalate_days` by
  editing the dict `route()` returns before `Seed.lay`). Intermediate
  states (R132): the middle approver (the manager) may hold no group on
  the goal — A1's fix is the shape to copy. `_approval_manager_uids` (:379)
  → `employee_id.parent_id.user_id` (AM50).
- **Joiner journey:** template `pb_onboarding.journey_template_rize_onboarding`
  (`journey_template_data.xml:34`); Day-1 step `step_rize_day1` (seq 60,
  `anchor doj`, `offset_days 0`, `automation_key day1_ics`); the step's
  `automation_key` is a **Char** (`pb_onboarding/models/journey_ext.py:54`,
  task copy :64) — no selection to extend. Handlers: override
  `pb.journey.task._automation_handlers()` (:70), `super()` + your key;
  the step runs on its due date via `action_auto` (:96). Add a step
  `step_rize_goals` (seq 65, anchor doj, offset 1, `automation_key
  goals_kickoff`, `assignee_rule hr`) from `pb_goals/data/`. Running cases
  do not get new steps (R31).
- **Hubs:** People hub `PEOPLE_LENSES` (`pb_people_hub/static/src/js/
  people_hub.js`, clone `pb_rnr/static/src/js/rnr_palette.js:52-69`);
  seqs taken 40 Records, 50 Assets, 60 Praise (+ Decision Room rows) —
  **Goals = 70**, label "Goals" (5 chars). ⌘K contract
  `pb_hub/static/src/js/hub_palette_entries.js:1-25`; block **3600**:
  `goals_board` 3600, `goals_my` 3610 (opens the lens on "mine"),
  `goals_cycles` 3620 (HR), `goals_templates` 3630 (HR).
- **Portal / mail / cron / tests / deploy:** exactly as A1 §1.5–1.6
  (`pb_offboarding` controller + home card R62, `.pbme` kit, R6 explicit
  `email_to`, R37/R47 cancel, vault cron shape, R11 test flags, R116 asset
  check).
- **Employee reads** as the system (R56/R104); accents folded in Python
  (R78); `hr.employee.parent_id` is the manager; join date via
  `pb_people._join_date` ladder (R77) — B2 needs it, B1 stores
  `joined_on` on the goal set for later.
- **Actors:** employee ess1.demo (uid 1984, employee 10080, company 5 —
  set `parent_id` = 17122 if empty, demo D9), manager lam.ngo (uid 2326,
  `RizeP4!2026`), HR = validator (`hr_lead` seat on company 5: borrow and
  return, R123), a joiner through the connected-system path (R112 recipe)
  for the kick-off test. Passwords drift (R74).

## 2. Models and rules
- **`pb.goal.cycle`**: `name` ("FY2026"), `company_id`, `date_start`,
  `date_end`, `mid_year_date`, `submission_days` (14), `state` draft →
  open → closed, `active`. One open cycle per company at a time (refuse
  a second with a sentence). "Open for everyone" is a BUTTON (HR gate)
  that creates a goal SET per active employee of the company — and it is
  off the automatic path (blueprint switch: never automatic; log-only
  preview shows the count first, R54).
- **`pb.goal.set`** (one per employee per cycle; the thing the route
  carries): `employee_id`, `cycle_id`, `manager_user_id` (computed from
  `parent_id`), `deadline` (kick-off date + `submission_days`),
  `joined_on`, `state` draft → submitted → manager_ok → locked (+
  `returned`, `refused`), `locked_at`, `locked_by_id`, `goal_ids`,
  `weight_total` (must be 100 at manager approval — the MANAGER assigns
  weightage: editable in the inbox drawer? No: the manager opens the set
  from the inbox card's "Open" door, sets weights on the native form, then
  approves in the inbox; the adapter's `_approval_validate` (:401) refuses
  the manager's approve while `weight_total != 100`, with the sentence),
  `company_id`. Route `goal_set`: `manager_step(_('Their manager'))` →
  `role_step(_('HR lead'), 'hr_lead')`; `_approval_apply` = lock
  (`locked_at`, `locked_by_id` = the approver, goals read-only, mail the
  employee); `_approval_return` → `returned` with the comment shown on
  `/my/goals`. Facts: goals count, weight total, deadline; revision =
  the goals' titles + weights (a changed goal reopens).
- **`pb.goal`**: `set_id`, `employee_id` (related stored), `title`
  (required), `description` (Text, required), `date_start`, `date_end`
  (required, inside the cycle), `weight` (0–100, manager-editable, the
  employee sees it read-only), `self_rating` (1–5, required at submit),
  `kr_ids`, `progress` (computed mean of KR progress), `state` follows the
  set + `done` / `archived` (B2), `template_id`, `sequence`, `company_id`.
  At least one KR to submit.
- **`pb.goal.kr`**: `goal_id`, `title`, `measure` (Char: "leads / month"),
  `target` (Float), `current` (Float), `progress` (0–100 %, writable by
  the employee after lock — progress is not a change), `due_date`,
  `history_ids` → **`pb.goal.kr.history`** (`kr_id, at, progress,
  current, note, by_user_id`) written on every progress change.
- **`pb.goal.template`**: `name, title, description, kr_titles` (Text,
  one per line), `job_ids`, `department_ids`, `company_id`; "Use a
  template" on `/my/goals` copies it in.
- **Kick-off** (`goals_kickoff` handler): the case's employee gets a set
  in the open cycle (none open → the step settles with a note "no goal
  cycle is open", never raises), `deadline` = today + `submission_days`,
  mail the employee ("write your goals by <date>") + activity; idempotent
  (R30). Switch `pb_goals.kickoff_auto` **1** (it only ever touches one
  new joiner at a time, which is safe).
- **Reminders** (daily 06:00, `pb_goals.reminders` 1): employee at
  deadline −3, −1, 0 and every 3 days late; the manager's review reminder
  is the route's own `remind_days`; HR escalation is the route's
  `escalate_days` (log it on the request — the engine does). Keys once
  (`reminder_log`), caps as parameters, honest counts.
- **Visibility (rules, the PAIR R60):** employee: own set/goals/KRs
  (`employee_id.user_id = user.id`); manager: sets of people whose
  `parent_id.user_id = user.id` (read + write `weight` only — enforce
  the field in `write`); HR (`group_goals_manager`+) everything in
  their companies. Ladder `group_goals_user` (managers are plain users —
  no group needed, the rule carries them), `group_goals_manager` (HR),
  `group_goals_admin`. Privilege name without `&` (R124).
- **Mail templates** (editable, `data/mail_template_data.xml`, sender =
  `pb_goals.hr_sender` param → fallback company email): kick-off,
  reminder, returned-with-comments, locked, manager-review-due (the
  route's own remind covers the inbox; this one is the optional
  courtesy, switch `pb_goals.manager_mail` 1).
- **Screens:** People → **Goals** lens (`pbim pbim-page pbgl`): HR view —
  cycle strip (open cycle, counts by state as a segmented bar), rows per
  person (name, manager, deadline, state chip problem-first R113, goals
  count, weight total, progress), facets (department, state, manager),
  drawer: the set with its goals and KRs, weights editable by the manager
  or HR, "Open the record" (`views` R125), "Send back with a note"; the
  manager's view = the same board scoped to their team (facade decides by
  rule); "Open a cycle" / "Open for everyone" (HR). `/my/goals`: the open
  set (deadline, state, manager's comments), goals as cards with KRs,
  add / edit / delete while draft or returned, "Use a template", the
  self-rating, "Submit for review"; after lock: read-only with KR
  progress sliders that write history. Home card "My goals · due in N
  days" (eager key R62). Native forms skinned (`nolabel` + `colspan`
  R128; search `<group>` bare R129).
- Switches: `pb_goals.kickoff_auto` 1, `pb_goals.reminders` 1,
  `pb_goals.sla_days` 5, `pb_goals.escalate_days` 2, `pb_goals.manager_mail`
  1, `pb_goals.hr_sender` (empty → company email).

## 3. Tests
T1  Install + gates; route laid per company; migration idempotent.
T2  Cycle FY2026 for company 5 (Apr–Mar, mid-year 1 Oct); a second open
    cycle refused; "Open for everyone" preview counts N employees and
    creates N sets with deadlines; run again → none new.
T3  `/my/goals` as ess1.demo: template picked, 2 goals with 2 KRs each,
    self-rating; submit without a KR on a goal → refused with the
    sentence; submit → `submitted`, manager (uid 2326) sees it in the
    inbox with the facts.
T4  Manager approve with weights 60/30 → refused ("weights add up to 90,
    not 100"); set 60/40 → approve → `manager_ok`; HR lead approve →
    `locked`, `locked_at/by`, employee mailed; the employee cannot edit a
    title (refused) but can move a KR to 40 % → a history row.
T5  Return with a note → `returned`, note visible on `/my/goals`; resubmit
    → route restarts; a changed title after `manager_ok` reopens
    (revision).
T6  Kick-off: a connected-system arrival opens the journey with your step;
    on its due date the handler makes a set with deadline +14 and mails;
    rerun → no second set; no open cycle → note, no raise.
T7  Reminders: deadline −3 / −1 / 0 / +3 mails once each; the route's own
    reminder and escalation fire per `sla_days`/`escalate_days` (assert
    the request's `escalated_at`, `request.py:150`).
T8  Visibility: ess1.demo reads own only; lam.ngo reads the team's and
    may write `weight` but not `title`; a company-2 HR user reads none of
    company 5's; the validator reads all.
T9  Lens light + dark (HR view, manager view as lam.ngo, drawer),
    `/my/goals` at 390 px; screenshots `RIZE/w2_b1_*.png`; no console
    errors; `unhandledrejection` listener.
T10 ⌘K 3600–3630; People lens `goals` at 70; deploy `19.0.1.0.0`, crons
    active, log clean.
T11 Reverts (seat, groups, passwords), mails cancelled; sets/goals/joiner
    stay, named RIZE W2.

## 4. Report back
As A1, plus the set/goal/KR/history API for B2 (fields, states, facade
verbs, how progress is computed, the kick-off handler name, the template
step xmlid), mail template xmlids, switches, new R-entries, ledger row,
owner items (the real cycle dates, HR sender address).
