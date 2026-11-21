# RIZE Wave 2 — Phase B2: `pb_goals` — the year (check-ins, mid-year, changes, scoring, reports)

B1 is live. B2 makes goals live through the year: monthly manager–employee
check-ins, mid-year / joining-month applicability, formal change requests
after lock, KR scoring and the aggregate, completion and year-end archive,
the Insights **Goals** lens with XLSX, the Home card "Goals waiting on you",
and the manager-compliance view. Bump `pb_goals` to `19.0.1.1.0`; the change
route ⇒ a migration.

Read first: `RIZE_LEDGER.md` (all), `RIZE_W2_HANDOVER.md` A/B/C2, the B1
handover §1 and **B1's report row in the ledger's Wave 2 table** (set/goal/
KR/history API, facade verbs, the kick-off handler, the template step
xmlid), then this file. Read the B1 code first.

## 0. Scope and non-goals
**In scope:** `pb.goal.checkin` (monthly, auto-scheduled, must be marked
complete), applicability (`pb.goal.set.applies_mid_year`, `applies_year_end`,
`prorated`, with the plain-English explanation mailed to the employee),
`pb.goal.change` (after lock; manager → HR lead route; audit on the goal),
KR scoring (manager scores 0–5 per KR; goal score = weighted; set score =
Σ weight × goal score / 100), completion + year-end close/archive (HR
button; freezes scores), the Insights lens (progress, completion %, missed
check-ins, manager compliance, year-end scores; XLSX), the Home lens
"Goals waiting on you" (pending approvals, overdue check-ins, open change
requests), ⌘K 3640–3660.
**Non-goals:** calibration / bell curves, pay linkage, 360 feedback, any
change to B1's route.

## 1. Verified facts
- **B1 API** — from the ledger row (names are binding; do not rename).
- **Check-in precedent:** `pb.employee.checkin` (`pb_lifecycle/models/
  checkin.py:30`: `employee_id, case_id, kind, owner_user_id,
  scheduled_date, state, notes, red_flag, red_flag_note, company_id`;
  `action_done(notes, red_flag, red_flag_note)` :76, `action_missed` :93)
  and the probation 1:1 pattern in `pb_probation`. Reminders per
  `pb_lifecycle/models/lifecycle_reminders.py:193 _remind_checkins`.
- **Join date:** `pb_people._join_date` ladder (R77) — B1 stored
  `joined_on` on the set; if empty, compute at B2's first touch.
- **Route canon:** as B1; `_approval_manager_uids` (AM50); intermediate
  state (R132); savepoint legs (R131). Process key `goal_change`.
- **Hubs:** Insights `INSIGHTS_LENSES` (Budget 20, Hiring 30, Training 40)
  — **Goals = 50**; Home `HOME_LENSES` (Wall 20, Coming up 30 — C1) —
  **Goals = 40**; XLSX precedent `pb_budget/models/budget_export.py:73`;
  ⌘K block continues: `goals_checkins` 3640, `goals_changes` 3650,
  `goals_numbers` 3660 (Insights).
- **Actors:** as B1 (ess1.demo + manager lam.ngo + validator as HR; the
  November joiner from B1's T6 for the pro-rating case; set the server
  clock dates in fixtures, R36).

## 2. Design
- **Check-ins (`pb.goal.checkin`)**: `set_id, employee_id, manager_user_id,
  month` (Date, first of month), `scheduled_date` (the cycle's
  `checkin_day` (default 25) of the month; a new field on the cycle),
  `state` planned → done | missed, `progress_note` (Text), `blockers`
  (Text), `done_at`, `done_by_id`, `kr_snapshot_json` (KR progress at
  done). Created by the daily job for every LOCKED set for the current
  month (idempotent per set×month); marked `missed` the day after the
  month ends if still planned; reminders to both sides at −3, 0, +3 days
  (keys once); `/my/goals` and the manager's board show the current
  month's check-in with "Mark done" (either side may complete; the note
  is required; KR progress can be updated in the same form and is
  snapshotted). Switch `pb_goals.checkins` 1, `pb_goals.checkin_day` 25.
- **Applicability**: on the cycle, `mid_year_date` (B1) and rules:
  `mid_year_min_months` (3: a person who joined fewer than N months
  before mid-year has no mid-year review), `year_end_min_months` (3: a
  person who joined fewer than N months before the cycle end is carried
  to the next cycle with a pro-rated set — no year-end score). The set
  gets `applies_mid_year`, `applies_year_end`, `prorated` (bool, with
  `covered_from`) computed once at kick-off / cycle-open and stamped;
  the kick-off mail explains it in a sentence ("Because you joined in
  November and our year ends in March, your goals will be reviewed at
  the end of next year; this year's check-ins still happen."). A
  `pb.goal.review` row (`kind` mid_year|year_end, `set_id`, `due_date`,
  `state` planned → done, `manager_note`, `employee_note`) is created
  per applicable set by the daily job when the date is within 30 days,
  with reminders; the mid-year review is where the manager scores KRs
  for the first time (scores editable until year-end close).
- **Change requests (`pb.goal.change`)**: after `locked`: `set_id,
  goal_id` (optional), `kind` (edit / add / drop / reweight), `payload_json`
  (the proposed values), `reason` (required), `requested_by_id`, `state`
  draft → submitted → manager_ok → approved | refused; route
  `goal_change` = `manager_step` → `role_step('HR lead','hr_lead')`;
  `_approval_apply` applies the payload (edit fields / create / archive
  the goal / new weights — must still total 100 or refuse at submit),
  writes a `pb.goal.audit` row (`goal_id, set_id, change_id, at, by,
  before_json, after_json`) and a chatter line on the set; the goal shows
  "Changed on <date> via request #N". The employee raises from
  `/my/goals` ("Ask to change"), the manager from the board.
- **Scoring**: `pb.goal.kr.score` (0–5, manager-only write, rule-enforced
  field), `pb.goal.score` = Σ(KR score)/n (or weighted by a KR `weight`
  if you add one — keep KRs equal-weighted, say so), `pb.goal.set.score`
  = Σ(goal weight × goal score)/100, `score_band` (a label per the
  cycle's bands: `pb.goal.cycle.band_ids` (name, min, max) seeded
  company-less: Outstanding ≥ 4.5, Strong ≥ 3.5, Solid ≥ 2.5, Needs
  attention < 2.5 — editable). Live computed; frozen at close.
- **Completion + close**: `pb.goal.done_at/done_by` ("Mark complete" by
  the employee, manager confirms in the check-in); HR "Close the cycle"
  (preview: N sets, M unscored → refuse until scored or "close with
  missing scores" ticked + logged) → sets `closed`, scores frozen
  (`frozen_json`), goals archived (`active` False keeps history; the
  employee still sees the archive under "Past years" on `/my/goals`),
  the cycle `closed`, a year-end mail with the band (switch
  `pb_goals.yearend_mail` 1).
- **Reports (`pb.goal.analytics`, Insights lens seq 50)**: per cycle,
  company / department / manager facets: progress (mean KR progress),
  completion % (goals done / all), submission timeliness (on time / late
  / never), lock timeliness, missed check-ins (count and % by manager =
  **manager compliance**), change requests count, score distribution by
  band, time-in-state (draft→submitted→manager_ok→locked, mean days);
  `export_xlsx(cycle, filters)`; empty → sentence (R27). Reads
  company-scoped, never sudo.
- **Home lens "Goals waiting on you"** (seq 40): for the session user —
  sets to approve (route requests on `pb.goal.set` / `pb.goal.change`
  where they are the approver: read through the engine's inbox facade,
  `pb_approval_config/models/inbox_facade.py`, never a second inbox),
  overdue check-ins where they are manager or employee, reviews due,
  their own set's deadline. Each row a door. The card counts on Home
  are the same numbers.
- Switches: `pb_goals.checkins` 1, `checkin_day` 25, `mid_year_min_months`
  3, `year_end_min_months` 3, `yearend_mail` 1, `review_lead_days` 30.

## 3. Tests
T1  Unit + gates; migration lays `goal_change` once; B1 tests still pass.
T2  Check-ins: locked set → the job creates this month's check-in once;
    reminders −3/0/+3 once each; done with a note + KR progress → snapshot
    row; a planned one after month end → `missed`.
T3  Applicability: a joiner 2 months before mid-year → `applies_mid_year`
    False with the explanation mail; the November joiner (year end March)
    → `prorated`, no year-end review, mail explains; a January joiner in
    an April–March cycle → both apply. Reviews created within 30 days of
    their dates, once.
T4  Change: employee asks to drop a goal and reweight to 100 → manager →
    HR lead → applied, audit row, chatter, `/my/goals` shows the note;
    reweight to 90 refused at submit; refuse → nothing changes.
T5  Scoring: manager scores KRs; employee cannot (rule); set score and
    band equal a hand calculation (60 % × 4.0 + 40 % × 3.0 = 3.6, Strong);
    a KR without a score → goal score empty, set score "not yet".
T6  Close: preview counts; refuse with an unscored set; tick "close with
    missing" → closed, frozen JSON equals the live numbers at that
    moment, goals archived, year-end mail once; `/my/goals` shows "Past
    years"; a new cycle can open.
T7  Analytics: seed 6 sets across 2 managers with mixed timeliness and
    missed check-ins; the facade's compliance % equals a Python
    recomputation; XLSX re-read spot value; empty cycle → sentence.
T8  Home lens as lam.ngo: sets to approve + overdue check-ins listed with
    doors; as ess1.demo: own deadline + own check-in; counts match.
T9  Chrome light + dark: check-in form, change request, Insights lens,
    Home lens, `/my/goals` past years at 390 px; screenshots
    `RIZE/w2_b2_*.png`; no console errors; `unhandledrejection` listener.
T10 ⌘K 3640–3660; Insights lens `goals` at 50; Home lens at 40; deploy
    `19.0.1.1.0`, crons active, log clean.
T11 Reverts (seat, groups, passwords), mails cancelled; data stays named
    DEMO (ledger rule 9).

## 4. Report back
As B1, plus the scoring formula in words for the closeout, the close
procedure, what the Home lens reads, switches, new R-entries, ledger row,
owner items (bands, check-in day, the minimum-months rules).

## Demo-data rule (owner, 2026-09-16 — D18, ledger binding rule 9)
Every demo record this phase creates on `payobook` is KEPT for future demos, so it
must NOT carry the customer name ("RIZE"/"Rize") anywhere a viewer can see — names,
subjects, notes, chatter, logins, emails, job/department titles, letter bodies. Name
them starting with **DEMO** ("DEMO Town hall"), logins `demo.<role>@example.com`.
Register every one at creation, in the fixture code:
`seed = self.env.get('pb.demo.seed'); if seed is not None: seed.register(records, label)`
(the guard keeps `pb_demo_seed` optional on tenants). The report carries a "Demo
records" table (model, ids, label) and the register count. Any "named RIZE W2" wording
left in this file is superseded by this section.
