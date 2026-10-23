# LEARNING L3 — Learning paths

Programme: LEARNING. Design page `docs/design/rize-learning-blueprint.html` §5 "Paths",
§6 "A learning path", §7 phase L3. Ledger `docs/handovers/learning/LEARNING_LEDGER.md` is
binding. Predecessors: `L0_REPORT.md`, `L1_REPORT.md`, `L2_REPORT.md` — take the Learning
hub registry, the Overview facade, the My learning lens blocks, the certificate record and
the requirement model from the reports, not from memory. If L2 has not shipped when L3
starts, build L3 without the requirement link (§3.6) and say so in the report.

Report back to `docs/handovers/learning/L3_REPORT.md` (same template as L0 §9).

## 1. Scope

**Goal.** A path is an ordered set of courses with a purpose (role, career or skills) that
a person is put on as one thing; the system opens each step when it is due, shows where
everyone is on a station line, and gives the path to new joiners by job or department.

**In scope.**
1. Models `pb.training.path`, `pb.training.path.step`, `pb.training.path.enrolment` (§3.1).
2. Steps are courses in L3 (kinds for sessions, sign-offs and outside courses are reserved
   for L4/L5). A step can be a **gate**: later steps wait until it is finished.
3. Enrolment creates the step assignments through the existing assignment engine, so
   reminders, more-time, probation link, analytics and certificates work unchanged (§3.2).
4. Day-one auto-enrolment by job or department through the existing joining checklist step
   (§3.3). Enrol one person, a department, a job or everyone from the board.
5. PATHS lens on the Learning rail (seq 35): path cards with the station line, path page
   with a per-person progress table, "New path" and "Enrol people" drawers (§4.1).
6. My learning: "My path" block with the dot rail and the next step; portal page block (§4.2).
7. Growth plans: an objective may point at a path; the Growth board shows the path's
   progress chip; "Enrol" from the objective (bridge module, §3.5).
8. Overview "Paths" block; Numbers "By path" split and spreadsheet sheet (§4.3).
9. Demo data (§6), tests T1–T14 (§7), normal-tier deploy (§8; one new bridge module =
   risky tier for the install step — see §8).

**Binding non-goals.** No skills model (L5). No sessions or sign-offs (L4). No outside
courses (L5). No change to `pb_pip`/`pb_goals` code except through the bridge module. The
stock `prerequisite_channel_ids` on courses is **not** used (it is website-only and global
per course — F3); gates live on the path step.

## 2. Verified plumbing facts (do not re-derive)

| # | Fact | Where |
|---|---|---|
| F1 | Growth plans: `pb.pip.case` (`pb_pip/models/pip_case.py:69-170`: `employee_id`, `requested_by_user_id`, `hr_owner_user_id`, `state` from `PIP_STATES` requested/coaching/active/evaluation/passed/failed/terminated, `objective_ids`, `checkin_ids`); `pb.pip.objective` (`pip_objective.py:16-50`: `case_id`, `employee_id`, `name`, `metric`, `target`, `weight`, `status` on_track/at_risk/met/not_met, `sequence`). Facade `pb.pip` (`pb_pip.py:68`): `get_case(case_id)` :310-355 returns `{row, coaching, objectives[], checkins[], evaluation, blockers}`; `add_objective` :403, `set_objective_status` :439. Board `PbPipBoard` (`pip_board.js:71`, xml `pip_board.xml:21`, tag `pb_pip_board`). **No course/training reference anywhere in pb_pip**; its manifest depends on `pb_lifecycle, pb_talent_hub, pb_import_kit, pb_hub`, not `pb_training`. | `pb_pip` |
| F2 | `pb.goal` has no linked-course concept (`pb_goals/models/goal.py:33`). Not touched in L3. | |
| F3 | Stock `slide.channel.prerequisite_channel_ids` exists (`website_slides/models/slide_channel.py:192-201`) but is enforced only in website templates ("Course Locked"); backend `_action_add_members` ignores it. Tags: `slide.channel.tag.group` / `slide.channel.tag` (`slide_channel_tag.py:10-35`), `channel.tag_ids`; the demo tags were deleted (R182). `slide.channel.partner`: `member_status` invited/joined/ongoing/completed, `completion` %, `next_slide_id`. | server addon |
| F4 | Assignment fields (`assignment.py:51-131`); `assign_many(channel_id, employee_ids, reason='adhoc', due_date=None, counts_for_probation=None)` (:588-645) — no extra-values parameter, skips no-login and open rows, one savepoint per person, returns `{made, already, no_login, failed, message}`. `ASSIGN_REASONS` now `day_one, probation, compliance, adhoc, leadership, renewal` (`training_common.py:151-159`; L2 adds `required`). `_guard_one_open` = one open assignment per person per course. | `pb_training` |
| F5 | Overview facade `pb_training_overview.py`: `overview()` :37-86 builds blocks via `self._safe(...)`, returns `allowed, people, courses, headline, certificates, calm, queue[], month, departments`; client `learning_overview.js:31-47`, template sections hero :44, month :63, certificates :74, departments :98. | |
| F6 | Learner: `pb.my.training.home()` base `pb_my_training.py:101-118` → `{partner_id, name, courses[tile], in_progress, finished, passed, total}`; `_due.py:120-145` adds `overdue, due_soon, delay_kinds, manages` with defaults in an `except`; tile shape `{id, name, blurb, done, total, left, percent, finished, test, score, next_id, next_name, duration, assignment}`; pattern = override `home()`, call super, add a key inside try/except. `PbMyLearningLens` (`my_learning_lens.js:31`, `MODEL="pb.my.training"`, parallel calls :58-74), template `my_learning_lens.xml:9` blocks: loading :15, failed :23, hero :40 / calm :67, courses :77, certs :129, team :166, allowance :201 — "My path" goes after the hero (:74). Portal `/my/training` (`controllers/portal.py:118-126`) → `portal_my_training` (`portal_templates.xml:243`: notices → hero → overdue :254 → three numbers :297 → nothing-yet :316 → courses grid :332). | |
| F7 | Station line precedent: `pb_import_kit.QuietSteps` (`quiet_board.xml:39-58`, contract `qSteps [{key, n:'01', title, countLabel, count, sub, flag, flagTone, mine, on}]`, `qStepPick(key)`; CSS `quiet_board.scss:55-113`; `nav.pbim-steps` + `button.pbim-st` with `.pbim-st-c` count bubble; `is-many` when > 4 steps); live use `pip_board.xml:111-118` with builder `pip_board.js:245-275`. Per-person dot rail: `pip_board.xml:218-228` `div.pip-rail > div.pip-stage.pip-stage--{done|now}` + `.pip-stage-dot/-l/-n`, CSS `pip.scss:104-149` (`grid-template-columns: repeat(4,1fr)` hard-coded → make it a CSS variable in the clone). | |
| F8 | Day-one dispatch: `pb.journey.task.automation_key` Char; `_automation_handlers()` dict (`pb_onboarding/models/journey_ext.py:70-82`); `action_auto` :98-136 (return False = leave open; string = done note). `pb_training/models/journey_ext.py:37-110` registers `training_day1` → `_auto_training_day1` (reads `pb.training.rule._for_employee`, switch `pb_training.day1_auto`, creates assignments directly with reason `day_one`). Step data `pb_training/data/journey_step.xml` (noupdate, seq 65; running checklists do not pick up new steps — R31). | |
| F9 | Demo: only course 27 "DEMO Agronomist basics" is a known course on payobook (R181); stock courses 1–7 deleted (R182); day-one rule 19 "DEMO Induction"; schedules 7/8; `pb_demo_seed` not installed on payobook (`DEMO_SEED_GUIDE.md:173`) — register with `env.get('pb.demo.seed')` guard only. Demo jobs on company 5 (`demo_catalog.py:277-302`) incl. Machine Operator, Line Leader, Safety Officer. | |
| F10 | Analytics `_split(rows, key)` (`analytics.py:330-362`) buckets by department/course/reason via `_core(group)` → `{name, total, done, overdue, completion, performance}`; payload keys at :175-180; spreadsheet loop :526-529; `_lists` :422-447 returns `{courses, departments}`. | |
| F11 | Working tree: L1 is mid-build (`pb_training` modified, `migrations/19.0.1.5.0/`, `data/document_category.xml`, `data/mail_template_certificates.xml`). L3 starts only after L1 (and L2 if scheduled first) have been committed; rebase first. | |

## 3. Architecture

### 3.1 Models (`pb_training/models/path.py`)
- **`pb.training.path`**: `name` (translate), `purpose` Selection `role / career / skills`
  (labels "For a role", "For a career move", "For a skill"; VI "Cho vai trò", "Cho lộ trình
  thăng tiến", "Cho kỹ năng"), `blurb` (Text, one sentence shown on the card and to the
  learner), `step_ids`, `active`, `company_id`, `due_days` (whole path, default 90),
  `counts_for_probation`, `day_one` Boolean, `department_ids` (child_of), `job_ids`,
  `enrolment_ids`, computed `steps_count`, `people_count`, `done_count`, `stations` (JSON
  for the station line: per step `{key, title, count, sub}`), `requirement_id` (M2o, L2
  optional, §3.6). `_sql_constraints`: name unique per company.
- **`pb.training.path.step`**: `path_id`, `sequence`, `kind` Selection `course` (reserved:
  `session`, `signoff`, `outside`), `channel_id` (required for `course`), `gate` Boolean
  ("Later steps wait for this one"), `due_days` (optional per-step, from the day it opens;
  default = course default), `name` (related channel name), `hours` (related
  `channel_id.pb_hours` if L2 shipped, else computed from `total_time`).
- **`pb.training.path.enrolment`** (`mail.thread`): `path_id`, `employee_id`, `partner_id`,
  `reason` (same `ASSIGN_REASONS` + new `path` only if needed — reuse the person's reason:
  `day_one`, `probation`, `adhoc`, `leadership`), `started_on`, `due_date`, `state`
  Selection `not_started / in_progress / overdue / done` (computed, stored), `current_step_id`
  (first unfinished step in order), `percent` (finished steps / steps), `assignment_ids`
  (one2many via `path_enrolment_id`), `assigned_by_id`, `company_id`, `objective_id` (M2o
  `pb.pip.objective`, set null — only when the bridge is installed; define it in the bridge),
  word helpers `state_words`, `where_words` ("At step 2 of 4: Pesticide handling").
  Constraint: one open enrolment per person per path (`_guard_one_open_path`).
- **Assignment** gains `path_enrolment_id` (M2o, set null) and `path_step_id` (M2o, set
  null); `assign_many` gains `extra=None` dict merged into each create (used for the two
  links and `rule_id` later). The assignment's `course_name`/`reason_words` unchanged; the
  row payload (`assignment.py:529-555`) adds `path_name` and `step_words` so the Assigned
  lens can show "Step 2 of 4 · DEMO New agronomist".

### 3.2 Enrolment engine (`pb.training.path.enrolment`)
- `enrol_many(path_id, employee_ids, reason='adhoc', due_date=None)` (`@api.model`, manager
  or trainer): per person in a savepoint: skip no-login; skip an open enrolment (`already`);
  create the enrolment; then `_open_steps()`.
- `_open_steps()`: walk steps in order; for each step not yet having an assignment for this
  enrolment: if every earlier **gate** step is `done` (assignment state done), create the
  assignment through `assign_many(channel_id, [employee], reason, due, extra={links})`
  (due = today + step `due_days` or the course default, capped by the enrolment `due_date`);
  else stop (the step stays "waits for …"). A person already on that course outside the path
  (open assignment) is **adopted**: link the existing assignment to the enrolment instead of
  failing the guard.
- `_refresh()` (called by the daily job leg `_refresh_paths` and after any assignment
  `_refresh_one` that carries `path_enrolment_id`): recompute `current_step_id`, `percent`,
  `state` (done when all steps done; overdue when any step assignment overdue or
  `due_date < today`; in_progress when any step started; else not_started); then
  `_open_steps()` to unlock the next steps. Hook: in `assignment._refresh_one`, after the
  write, `if self.path_enrolment_id: self.path_enrolment_id._refresh()` inside `leg()`.
- Removing a person from a path (`unenrol`): cancels enrolment and **unassigns only the
  not-started step assignments**; started ones stay as ordinary assignments.
- Chasing: no new mails; the step assignments are chased by the existing ladder. The
  enrolment's chatter logs enrol/unenrol/done.

### 3.3 Day-one auto-enrolment
- Extend `_auto_training_day1` (F8): after the rule courses, find active paths with
  `day_one=True` matching the employee's department (child_of) or job; `enrol_many` with
  reason `day_one`; the note lists the paths. Honour the same `day1_auto` switch. No new
  journey step (R31 — new steps do not reach running checklists anyway).
- Board: "Day one" inner tab on REQUIRED (L2) or the Required lens list (if L2 not shipped:
  the Paths page shows a "Given on day one to …" chip per path).

### 3.4 Daily job
- Leg `_refresh_paths(today)`: refresh every open enrolment (savepoint each). Order: after
  `_refresh_all` (assignments) and before reminders.

### 3.5 Bridge module `pb_training_growth` (new, `auto_install: True`, depends `pb_pip, pb_training`)
- `pb.pip.objective.path_id` (M2o `pb.training.path`, set null) + `path_enrolment_id`
  (computed: the employee's open enrolment on that path) + `path_percent`/`path_words`.
- Facade extension `pb.pip.get_case`: each objective dict gains `path: {id, name, percent,
  words, enrolment_id}` (empty dict when none). New verb `pb.pip.enrol_objective_path
  (objective_id)` → `enrol_many(path, [employee], reason='leadership')`, links
  `objective_id` on the enrolment (field defined in the bridge on the enrolment model).
- Growth board (`pip_board.xml` objective rows): a quiet chip "Path · 40%" with an "Enrol"
  button when `path` is set and no enrolment — done through a template `t-inherit` in the
  bridge, not by editing `pb_pip`. Objective drawer: a "Learning path" picker (select).
- Test the bridge installs cleanly on a DB without `pb_training` (it is auto_install only
  when both are present).

### 3.6 Requirement link (only if L2 is live)
A requirement with `target='path'` (new selection value) counts as valid when the person's
enrolment is `done` within `validity_months`. `_status_for` gains the branch; the matrix
shows the path name. Skip if L2 is not shipped; note it.

## 4. Surfaces

### 4.1 PATHS lens (`pb_training/static/src/js/paths_lens.js` + xml + scss; rail seq 35, label "Paths" / VI "Lộ trình", icon `route`)
- Facade `pb.training.paths_board()` → `{allowed, paths:[{id, name, purpose, purpose_word,
  blurb, steps:[{id, name, gate, hours}], stations:[...QuietSteps shape], people, done,
  overdue, day_one, audience_words}], kpis}`; `path_page(path_id)` → path + rows
  `[{enrolment_id, employee, department, job, state, state_words, where_words, percent,
  current_step, due_words, late}]` + per-step counts; verbs `new_path(values)`,
  `save_path(path_id, values)` (steps as an ordered list with gate flags; reorder = resequence),
  `archive_path`, `enrol(path_id, employee_ids|department_id|job_id|everyone, reason,
  due_date)`, `unenrol(enrolment_id)`.
- **Hero moment:** each path card draws its station line (QuietSteps, F7): stations are the
  steps, the count bubble is how many people are at that step right now, a flag "N late" in
  rose when any; clicking a station opens the path page filtered to that step. Cards: title,
  purpose chip, blurb, "N people · M finished", "Given on day one to Agronomists" chip.
- Path page: header with the station line (big), table of people with the dot rail per row
  (F7 per-person rail, CSS var for the column count), filter chips Not started · In progress
  · Late · Finished, search; row actions "Open their courses" (Assigned lens filtered),
  "Remove from path". Buttons: "Enrol people" (drawer: people picker reused from the board,
  or department / job / everyone, reason, due date), "Edit path".
- New-path drawer: name, purpose, blurb, steps builder (add course from a searchable list;
  drag to reorder — keyboard: move up/down buttons too; gate toggle per step with the
  sentence "Later steps wait for this one"), day-one audience (departments, jobs), due days,
  counts for probation. Zero dead ends: a path with no steps cannot be saved ("Add at least
  one course"); a course that is not published shows a warning chip.
- Empty state: "No paths yet. A path puts several courses in order — for a role, a career
  move or a skill." with "New path".

### 4.2 My learning and portal
- `home()` adds `paths: [{enrolment_id, name, purpose_word, percent, state_words,
  where_words, steps:[{name, state: done|now|next|waits|locked, channel_id, assignment_id}],
  next: {channel_id, name}}]`.
- Lens block "My path" after the hero (F6): one card per enrolment with the dot rail (done
  tick, now ring, waits grey with "after <gate step>"), the sentence "At step 2 of 4:
  Pesticide handling" and a "Continue" button that opens the current step's course page.
  Portal template: the same block after the three numbers (:297).
- The Next-up hero prefers a path's current step when the person is on a path (so the
  learner sees one thing to do).

### 4.3 Overview and Numbers
- Overview `paths` block: "6 paths · 48 people on a path · 9 finished this quarter" + queue
  row "Late on a path: N" → Paths page filtered Late. Headline fragment only when late > 0.
- Numbers: `by_path` split (F10) with a "Not on a path" bucket so rows still add up;
  spreadsheet sheet "By path"; `lists.paths`.

## 5. Safety rails
1. Ledger L1–L8; EN + VI for every string; QuietSteps contract: a person is at exactly one
   station so counts add up (test it).
2. Never create a second open assignment for a person on a course: adopt the existing one.
3. Unenrol never deletes a started assignment or a certificate.
4. The bridge is the only place `pb_pip` is touched; it must not break `pb_pip` tests.
5. Commits (explicit paths): (a) `feat(training): learning paths — models, enrolment engine,
   day-one, daily leg`; (b) `feat(training): PATHS lens, path page, drawers`; (c)
   `feat(training): My path on My learning and the portal; Overview and Numbers`; (d)
   `feat(training-growth): growth plan objective → path bridge`; (e) demo + docs.

## 6. Demo data (payobook, "DEMO …", registered with the seed guard)
- Create three short DEMO courses (one article lesson each, published, invite-only, no
  test): "DEMO Pesticide handling", "DEMO Field data on the phone", "DEMO Leading a line".
- Path "DEMO New agronomist" (role): 27 Agronomist basics (gate) → Pesticide handling (gate)
  → Field data on the phone; day-one for job Agronomist / department Agronomy if present.
- Path "DEMO Operator to line leader" (career): Leading a line → Pesticide handling.
- Enrol 8 demo people spread over the stations (use the existing assignment states so the
  station counts show 3 / 3 / 2 and one late). Growth plan: one existing DEMO case's
  objective linked to the career path.

## 7. Numbered tests (`tests/test_paths.py`, bridge `tests/test_growth_bridge.py`)
- **T1** path/step/enrolment shape; name unique per company; no steps → UserError in plain words.
- **T2** `enrol_many`: step 1 assignment created; gated step 2 not until step 1 done; non-gated steps open immediately; skip no-login; already-open enrolment → `already`.
- **T3** adoption: an existing open assignment on step 1's course is linked, not duplicated.
- **T4** `_refresh`: percent, current step, done/overdue/in_progress; assignment `_refresh_one` triggers the enrolment refresh; the next gated step opens the day the gate finishes.
- **T5** unenrol: not-started assignments removed, started kept; enrolment state.
- **T6** day-one: a joiner in a matching department/job gets enrolled by the journey task; switch off → note only; no duplicate on re-run.
- **T7** daily leg refreshes all open enrolments under savepoints; one bad row does not stop the rest.
- **T8** `paths_board` stations: every enrolled person counted at exactly one station; late flag.
- **T9** `path_page` rows and filters; `enrol` by department (child_of) / job / everyone.
- **T10** `home()` `paths` block shape; next-up prefers the path step; `where_words` EN and VI.
- **T11** Overview and Numbers `by_path` add up; spreadsheet sheet.
- **T12** bridge: objective `path_id`; `get_case` carries `path`; `enrol_objective_path` enrols once; pb_pip's own tests still green.
- **T13** no "Odoo", no emoji; rail label "Paths"/"Lộ trình" fits.
- **T14** Chrome walk (local then live): PATHS cards with station lines, new path drawer (reorder, gate), enrol people drawer, path page filters and dot rails, My learning "My path" + Continue, portal block, growth plan chip + Enrol, Overview/Numbers, console clean.

## 8. Deploy
- `pb_training` → `19.0.1.7.0` (or next free after L2); new module `pb_training_growth`
  (`-i` on every DB → **risky tier** for the install step: backups, p0clone first). Then the
  usual ritual: deploy-notes START/DONE, flock, named modules from `git archive HEAD`, scoped
  rsync, cron snapshot, stop, `-i pb_training_growth -u pb_training` per DB one at a time,
  asset ritual, start, warm, crons, versions, live walk. Stop at the deploy gate for Fable's go.
