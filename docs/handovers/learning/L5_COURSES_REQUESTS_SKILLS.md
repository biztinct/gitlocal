# LEARNING L5 — Outside courses, requests, versions, results, feedback, skills

Programme: LEARNING. Design page `docs/design/rize-learning-blueprint.html` §5 "Courses",
"Tests", "Skills", §6, §7 phase L5. Ledger `docs/handovers/learning/LEARNING_LEDGER.md` is
binding. Predecessors L0–L4 reports: take the hub registry, the assignment engine (`extra=`,
path links), the certificate record, hours, requirements, paths and sessions from the
reports. **Owner decision LD6 (outside catalogue: our own list now, paid connectors only if
Rize contracts one) is the recommendation in the design page §8 — ask it when this phase
launches; build §3.1 as "our own list" unless the owner says otherwise.**

Report back to `docs/handovers/learning/L5_REPORT.md`.

## 1. Scope

1. **Outside-course catalogue**: provider courses with link, cost, hours (§3.1).
2. **Course requests**: an employee asks to take a course (ours or outside); the manager
   decides, the HR lead too when money is involved; approval pre-books the allowance and
   pre-fills the later claim; an approved request for one of our courses assigns it at once
   (§3.2).
3. **Course versions**: "Publish a new version" resets progress for everyone who finished
   the old one and gives them a short re-read assignment (§3.3).
4. **Tests**: a results page per test (pass rate, score spread, hardest questions, attempts)
   and "ask N of M" random pools; the stock results page is gated to training users (§3.4).
5. **Feedback** after a course (two ratings + one text) and a **30-day manager follow-up**
   ("has their work changed?"); both on the course page and in Numbers (§3.5).
6. **Skills**: a course grants skills at a level when finished; SKILLS lens (seq 75): each
   person against their job's required skills, the gap, and the course that closes it (§3.6).
7. Fix the live Inbox bug: claim receipt rows are lists, the Inbox needs dicts (§3.7).
8. Demo (§6), tests (§7), deploy (§8).

**Binding non-goals.** No paid catalogue connectors (Go1, Udemy, LinkedIn). No SCORM import
(L7). No budget "committed" posting into `pb_budget` (no such concept exists — F8); the
allowance is the only money gate. No change to `pb_hr_workforce_planning`. No AI drafting
(L7). The feedback forms use our token pages, never the stock survey website.

## 2. Verified plumbing facts (do not re-derive)

| # | Fact | Where |
|---|---|---|
| F1 | Approval precedent: model inherits `biz.approval.chain.mixin`; the approval file registers `register_chain('pb.training.claim', 'training_claim', submit_state='submitted', driven=('approved',), employee_field='employee_id', amount_field='amount', currency_field='currency_id')` (`claim_approval.py:38-76`); route builders `route(role_step(_('HR lead'), 'hr_lead'))`, `manager_step(_('Their manager'))` (`chain_shim.py:105-125`); manager = `employee.sudo().parent_id.user_id` (:402-415); `_advance_state('submitted'/'approved')` (:533-566); hooks `_chain_title/_chain_company/_chain_facts/_chain_fact_specs/_chain_revision_values/_approval_detail/_approval_seed_default` + module `seed_all(env)`; **never set `date_field` to a past date** (claims went "blocked"); catalogue row `biz.approval.process` in `data/approval_process.xml` (claim seq 245, delay 240) — a module without it installs routeless (RIZE_LEDGER:2220-2227); seeding in `hooks.py:60-85` (`_seed_routes` tuple) + migrations. | `pb_training`, `biz_approval_workflow` |
| F2 | Allowance: `pb.training.allowance` (`allowance.py:32-56`), `amount_for(emp, year)` :153; **"used" = sum of approved claims** in `claim._facts_for(employee, year, skip_claim, currency)` (`claim.py:275-297`) returning `{allowance, agreed, left, over, currency, year}`; `_allowance_problem` :298-330 (skipped when `P_CLAIM_OVER` flag on) runs in `_before_approval_transition('submitted')`; claim `year` is computed from `paid_on` (:150-154). | |
| F3 | Random pools: `survey.survey.questions_selection` `all`/`random` (`survey_survey.py:75-84`); `survey.question.random_questions_count` on a **section** (`survey_question.py:79-84`); drawn at attempt creation into `survey.user_input.predefined_question_ids` (`survey_survey.py:621-647`); scoring is out of the drawn questions. `pb_training.new_test` (`pb_training.py:461-491`) sets context defaults (`default_certification`, pass 70, 3 attempts…) — add `default_questions_selection`. | server `survey` |
| F4 | Results: stock `/survey/results/<survey>` (`survey/controllers/main.py:731-763`, `auth='user'`, **no group check**); `pb_training/controllers/slides_gate.py` gates only slides pages (:107-175). Fields: `survey.user_input.line` (`user_input_id, survey_id, question_id, page_id, skipped, answer_type, suggested_answer_id, answer_score, answer_is_correct`), `survey.user_input` (`state, scoring_percentage, scoring_success, predefined_question_ids`), `survey.question.answer.is_correct`. Hardest question = wrong / **asked** (asked = in `predefined_question_ids`), one line per ticked answer on multi-choice. | |
| F5 | Feedback house pattern = `pb.feedback.request` (`pb_lifecycle/models/feedback.py:30-68`): `subject_employee_id, respondent_user_id, respondent_email, kind (FEEDBACK_KINDS probation_peer/exit/pip/other — extend with selection_add), case_id (optional), token, window_end, state sent/submitted/expired/extended, questions_json [{key,label,type text|rating|choice,options}], answers_json, submitted_at`; URL `/journey/f/<token>` (`auth='public'`); `action_send()` uses `pb_lifecycle.mail_template_feedback_invite` with explicit `email_to`; `submit_answers()`. Users: pb_offboarding `journey_case_ext.py:140`, pb_pip `pip_case.py:678`, pb_probation `review_journey.py:140`. 30-day timer precedent = new-hire pulse `pb.newhire.pulse` (`pb_onboarding/models/newhire_pulse.py:43-209`: rows planned per mark with `due_date`, `_cron_send_due()` from the lifecycle daily cron; low score → manager activity). | |
| F6 | Versions: no precedent anywhere (pb_learn has only a content version string; pb_hr_comm has no read receipts). Stock blocks: `slide.channel.partner.member_status/completion/completed_slides_count`, `slide.slide.partner.completed`, `slide.slide.date_published`. Retrain precedent = L1 renewal leg (`automation.py:250-343`: `_renewal_candidates`, `_renewals`, `_assign_renewal` with reason `renewal`, `counts_for_probation=False`). | |
| F7 | Skills: `hr.skill (name, skill_type_id)`, `hr.skill.type (skill_level_ids, is_certification)`, `hr.skill.level (level_progress 0-100, default_level)`, mixin `hr.individual.skill.mixin (skill_id, skill_level_id, skill_type_id, level_progress, valid_from, valid_to, is_certification)`; `hr.employee.skill`, `hr.job.skill (job_id)`; **no SQL unique — Python check one active row per skill** (`mixin.py:64-80`): archive + create, never edit in place; `hr.employee.current_employee_skill_ids` / `get_current_skills_by_employee()` (`hr_employee.py:18-30`); `hr.job.job_skill_ids/current_job_skill_ids`. Stock never grants a skill from a course. `pb_hr_workforce_planning.get_workforce_demand_data()` (`planning_scenario.py:1393-1427`) counts skills across all employees (`{skill, employees, coverage_pct, levels}`), no job comparison. | server `hr_skills` |
| F8 | Outside courses: `slide.channel` has no provider/cost/hours/link; claim fields `course_name (required), provider, amount, currency_id, paid_on, year, note, invoice/certificate attachments, state, fulfilment, incentive_id, over_allowance, refuse_note, decided_on, submitted_on` (`claim.py:67-146`). **No budget "committed" concept** in pb_budget (`pb.budget.expense` adds to spent only). | |
| F9 | Learner request precedent: `/my/training/delay` POST (`portal.py:290-317`) → `ask_more_time` → `pb.training.delay.ask()` (re-checks ownership, refuses duplicate submitted, `sudo().create` + `_advance_state('submitted')`, returns `{id, state, message}`); template `tr_ask` (`portal_templates.xml:185-215`, no JS, csrf). Inbox is generic over `biz.approval.request` (`pb_approval_config/models/inbox_facade.py:178, 592, 636-679`) — ship the catalogue row + seeded route and it appears. | |
| F10 | **Live bug:** `inbox_facade.py:657` skips non-dict rows; `claim_approval.py:150-155` builds `[_('Receipt'), name]` lists → claim receipt/certificate rows never show in the Inbox. Fix: `{'head': _('Receipt'), 'sub': name, 'cells': [...], 'tone': ''}`. | |
| F11 | `pb_training` manifest at `19.0.1.5.0` after L1 (uncommitted at research time; L1 adds `document_ext.py`, `learning_record.py`, `pb_my_training_certificates.py`, `pb_training_certificates.py`, `me_home_tile.py`, `certificates_lens.*`, `report/learning_record.xml`, migration `19.0.1.5.0`). L5 starts at the next free minor after L2–L4. | |

## 3. Architecture

### 3.1 Outside-course catalogue (`pb_training/models/outside_course.py`)
- `pb.training.outside.course`: `name`, `provider`, `url`, `cost` (Monetary) + `currency_id`,
  `hours`, `blurb`, `kind` Selection `online / classroom / exam`, `country_id` (optional),
  `tag_ids` (reuse `slide.channel.tag` for role/skill tags), `skill_grant_ids` (§3.6),
  `issues_certificate` Boolean + `validity_months`, `active`, `company_id`, counts
  `requests_count`, `taken_count`, `avg_rating`.
- The Courses lens shows outside courses as cards with the "Outside" chip (filters Ours ·
  Classroom · Outside · By job); card actions "Ask to take it" (everyone) / "Put someone on
  it" (HR: creates an approved request on their behalf). Course page for an outside course:
  provider, link, cost words, hours, who took it, ratings, claims against it.
- Claims gain `outside_course_id` (set null) and `request_id`; the claim form pre-fills
  `course_name`, `provider`, `amount` from the request.

### 3.2 Course requests (`pb_training/models/request.py` + `request_approval.py`)
- `pb.training.request` (`mail.thread`, `biz.approval.chain.mixin`): `employee_id`,
  `kind` Selection `ours / outside / other` (other = free text + link), `channel_id`,
  `outside_course_id`, `course_name` (computed/editable for `other`), `provider`, `url`,
  `amount` (Monetary, 0 for ours), `currency_id`, `year` (Integer, default this year),
  `when_words` (Char "When would you take it"), `why` (Text, required), `state`
  `draft / submitted / approved / refused / taken / claimed / cancelled`, `assignment_id`
  (set null; created on approval for `ours`), `claim_id` (set null), `decided_on`,
  `refuse_note`, `allowance_left_words`, `company_id`. Constraint: one open request per
  person per course.
- Approval: `register_chain('pb.training.request', 'training_request', submit_state=
  'submitted', driven=('approved',), employee_field='employee_id', amount_field='amount',
  currency_field='currency_id')` — **no `date_field`** (F1). Route: `manager_step(_('Their
  manager'))`, then `role_step(_('HR lead'), 'hr_lead')` only when `amount > 0` (the route
  builder reads the facts; if the engine cannot branch on amount, publish two routes keyed by
  `amount` through the existing matrix condition mechanism — check `biz_approval_workflow`
  for amount thresholds first and use them). Catalogue row seq 250 in
  `data/approval_process.xml`; `hooks.py` `_seed_routes` tuple += `'request_approval'`;
  migration seeds it on every DB. `_chain_facts`: amount, allowance left (after this
  request), course, provider, why; `_approval_detail` rows as **dicts** (F10).
- Pre-booking: `claim._facts_for` gains `committed` = sum of `approved` requests of that
  employee/year with no `claim_id` and `amount > 0`; `left = allowance − agreed − committed`;
  `_allowance_problem` (request version) checks the request amount against `left` the same
  way (same `P_CLAIM_OVER` switch). When a claim is linked to the request, the request moves
  to `claimed` and leaves the committed sum (no double count).
- On approval: `ours` → `assign_many(channel_id, [employee], reason='adhoc', due=…, extra=
  {'request_id': id})` and state `approved`; `outside/other` → mail `request_approved` with
  the link and the claim instructions ("keep the receipt and the certificate; claim it back
  on your training page"); the employee's portal claim form shows "Claim this course back"
  pre-filled. On refusal: mail with the reason.
- Learner: "Ask to take a course" on My learning (lens) and the portal `/my/training/
  requests` (list + form; picker: our courses open to requests (`slide.channel.
  pb_requestable` Boolean, default True), outside catalogue, or "something else" with a
  link); status chips; cancel while submitted. Manager decides in the Inbox (generic). HR:
  REQUESTS inner tab on the Claims lens (rail label stays "Claims"; tab "Requests" with
  waiting count) — rows, decide, "Put someone on a course" door.

### 3.3 Course versions (`slide_channel_ext.py`, verb on the course page)
- `slide.channel`: `pb_version` (Integer, default 1), `pb_version_note` (Text "What
  changed"), `pb_version_published_on` (Date), `pb_reread_days` (Integer, default 14),
  `pb_version_log` (Html, appended).
- Verb `publish_version(channel_id, note)` (training manager): bumps the version, stamps
  the date, logs the note, then for every person who **finished** the previous version (an
  assignment `done` for that course, or a `slide.channel.partner` with `member_status=
  'completed'`) and has no open assignment on it: resets their lesson progress (stock
  `slide.slide.partner.completed=False` for that channel's slides + the channel partner
  recompute — find the stock recompute method, e.g. `_recompute_completion`), then creates a
  re-read assignment (reason `reread` — new in `ASSIGN_REASONS`, "Changed course"; VI
  "Khóa học đã thay đổi"; `counts_for_probation=False`, due = today + `pb_reread_days`,
  `extra={'course_version': new}`). Capped per call (`pb_training.reread_cap` 500) with the
  remainder picked up by a daily leg `_rereads` (store `pb_version_pending` = True on the
  channel until all done). Certificates are **not** touched. Mail `course_changed` to each
  person (what changed, due words).
- Assignment gains `course_version` (Integer, the version it was done on); the Assigned
  lens shows "v2" chips; Numbers "By reason" picks up "Changed course".

### 3.4 Tests: results and pools
- Facade `pb.training.test_results(survey_id)` (training groups): `{attempts, people,
  pass_rate, avg, histogram:[{bucket:'0-9', n}…], hardest:[{question, asked, wrong, pct}]
  (top 10, denominator = asked), retake_policy_words, pool_words ("Each attempt draws 10 of
  30")}`. Tests lens: the L0 View wrapper is replaced by an OWL list of tests (name, course,
  pass mark, attempts, pool words, people, pass rate) with a results drawer (the hero: pass
  rate ring + histogram bars + hardest list) and buttons New test, Question bank, Open the
  test editor (stock form).
- "Ask N of M": new-test context adds `default_questions_selection='random'` only when the
  user ticks it in the New test drawer (a small pb drawer before the stock form: name, pass
  mark, attempts, "Draw N questions per attempt"); the drawer creates the survey with one
  section (`is_page=True`, `random_questions_count=N`) and opens the editor. Edit the
  setting later from the results drawer ("Questions drawn per attempt").
- Gate the stock results page: extend `slides_gate.py` to redirect `/survey/results/<id>`
  to `/my/training` for users outside the training groups (internal users without the group
  included).

### 3.5 Feedback and follow-up
- `FEEDBACK_KINDS` += `training` ("Course feedback") and `training_followup` ("Manager
  follow-up") via `selection_add` on `pb.feedback.request` (in `pb_training`, depends on
  `pb_lifecycle` already? — check the manifest; add it).
- Course feedback: on the assignment `done` crossing (same leg that files the certificate),
  create and send a `pb.feedback.request` for the employee (`respondent_user_id` = their
  user, `questions_json` = rating "Was it useful?", rating "Would you recommend it?", text
  "What would you change?", `window_end` = +14 days, `kind='training'`, and a new link
  field `assignment_id` on the request via `_inherit` in pb_training). Switch
  `pb_training.feedback_on` (default '1'). Course (ours or outside) gets `avg_rating`,
  `ratings_count`, `recommend_pct` computed from submitted answers; shown on the card and
  the course page ("4.3 · 17 ratings").
- Manager follow-up: on the same crossing create `pb.training.followup` (`assignment_id`,
  `employee_id`, `manager_id`, `due_date = completed_on + 30`, `state planned/sent/answered/
  skipped`, `feedback_request_id`); daily leg `_send_followups(today)` sends due rows as a
  `pb.feedback.request` kind `training_followup` to the manager (questions: rating "Has
  their work changed since the course?", choice "Did they use what they learned?" yes/
  partly/no, text); answers roll up to the course (`effect_avg`, `used_pct`) and to Numbers
  "Did it work?" tiles (L6 expands). Switch `pb_training.followup_on` (default '1'), days
  setting `followup_days` (30).

### 3.6 Skills (`skill_grant.py`; manifest depends += `hr_skills`)
- `pb.training.skill.grant`: `channel_id` or `outside_course_id` (one of), `skill_id`,
  `skill_level_id` (domain by type), `company_id`. Course page tab "Skills it gives".
- On the `done` crossing (and on an approved outside request marked `taken` with a claim
  or certificate): for each grant, if the person's current level for that skill is lower
  (by `level_progress`) or absent → archive the current `hr.employee.skill` row and create
  the new one (mixin rule F7, `valid_from` = today); chatter line on the employee.
- SKILLS lens (seq 75, "Skills" / VI "Kỹ năng", icon `sparkles` or `award`): facade
  `pb.training.skills_board(filters)` → `{people:[{employee, job, required:[{skill, level,
  have_level, state ok|below|missing, course_ids}], gap_count}], by_skill:[{skill,
  employees, coverage_pct, levels}] (reuse the WFP output shape, F7), courses_for_skill}`;
  filters department (child_of), job, skill, "only gaps". **Hero moment:** "On average a
  person has 4 of 6 required skills · 38 gaps across 120 people"; row = person with chips
  per required skill (green at level, amber below, rose missing) and "Close it: <course>"
  button → assign (or request for outside). Phone: cards. Managers see their team only
  (probe `i_manage_people`), training groups see all.

### 3.7 Inbox fix
`claim_approval.py:150-155` → dict rows (F10) + a test that `_approval_detail` rows are
dicts with `head/sub/cells/tone`. Same test guards the request's rows.

## 4. Surfaces (summary; follow the design bar)
Courses lens (Outside chip, request doors, version chip + "Publish a new version" drawer,
ratings), Tests lens (results drawer, New test drawer), Claims lens (Requests tab), SKILLS
lens, My learning (Ask to take a course, My requests, My skills chips), portal pages
(`/my/training/requests`), Overview queue rows ("Course requests waiting", "Follow-ups
waiting on managers"), Numbers ("Ratings", "Did it work?", "Requests and spend", "Skills").

## 5. Safety rails
1. Ledger L1–L8; EN + VI; Lucide; quiet board; plain words in mails.
2. Money: a request never writes money anywhere; only the claim → award lane does (L6 rule).
3. Version publish never deletes lesson content or certificates; progress reset is per
   person and logged.
4. Skills: never edit an `hr.employee.skill` in place; archive + create.
5. Feedback and follow-up switches default on but ship as settings; respondents get at most
   one mail per request.
6. Commits: (a) outside courses + requests + approval + allowance committed + Inbox fix;
   (b) versions + rereads; (c) tests results + pools + gate; (d) feedback + follow-up;
   (e) skills + SKILLS lens; (f) demo + docs.

## 6. Demo data (payobook, "DEMO …", registered)
Three outside courses (one with cost 3,000,000 ₫, 8 h); two requests (one waiting on the
manager, one approved); course 27 published as v2 with 3 people on a re-read; a test with
"draw 5 of 8"; 6 feedback answers on course 27; 2 follow-ups answered; skills: two skill
types with levels, course 27 grants "Field safety · Basic", jobs Agronomist/Line Leader
require two skills each so the SKILLS lens shows gaps.

## 7. Numbered tests
- **T1** outside course shape; catalogue filters; cost words.
- **T2** request route: ours → manager only; outside with amount → manager then HR lead; the catalogue row exists; `seed_all` idempotent; `_approval_detail` rows are dicts.
- **T3** committed pre-booking: approved request reduces `left`; linking the claim moves it out; over-allowance sentence; `P_CLAIM_OVER` switch.
- **T4** approval of `ours` creates the assignment once; refusal mails the reason; cancel while submitted.
- **T5** learner request page: ownership, duplicate refused, status words EN/VI.
- **T6** publish version: resets progress for completers only, creates `reread` rows once, cap + daily remainder, certificates untouched, mail sent.
- **T7** test results: pass rate, histogram sums to attempts, hardest uses asked denominator (random pool fixture), multi-choice lines counted once per question.
- **T8** New test drawer with pool creates one section with `random_questions_count=N`; `questions_selection='random'`.
- **T9** `/survey/results` redirect for a non-training internal user; allowed for a trainer.
- **T10** feedback request created on done once; answers roll up to `avg_rating`; switch off → none.
- **T11** follow-up planned at +30, sent by the leg, answered rolls up; skipped when the employee has no manager.
- **T12** skill grant on done: archive + create; no downgrade; outside course `taken` grants.
- **T13** skills board: gap states, team scope for managers, course suggestion.
- **T14** Inbox fix: claim detail rows reach `inbox_facade` (call the facade on a submitted claim and assert the Receipt row is present).
- **T15** no "Odoo", no emoji; VI fits.
- **T16** Chrome walk (local then live): Courses outside cards + Ask to take it; Inbox decide as manager; HR Requests tab; portal requests page; Publish a new version drawer + a learner's reset progress + reread chip; Tests results drawer + New test with pool; feedback token page as the learner; follow-up token page as the manager; SKILLS lens gaps + Close it; console clean.

## 8. Deploy
`pb_training` next minor; new tables + approval catalogue row + migration seeding the route
on every DB → **risky tier**; `-u pb_training` (and `pb_lifecycle` only if touched); verify
the route exists per DB (`biz.approval.process` key `training_request` and a published
route per company) before the live walk. Stop at the deploy gate.
