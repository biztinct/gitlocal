# RECRUIT — Phase 3: roles without friction — requests, budget flag, the one offer rule

Delivers register lines **G-12, G-13, G-14, G-15, G-16, G-17, G-19, G-39, G-40, G-43**:
a role can be opened directly (no request needed), a recruiter can ask a line manager to
complete the request from an emailed one-page form with reminders and escalation, the
manager types the expected budget and an over-budget figure is flagged by email to the
CEO / Head of HR / Finance without blocking anything, every sign-off becomes record +
notify, the job description is shared for input instead of approved, the background check
and document request stop gating the offer, a Confidential toggle hides a role, recruiter
auto-assignment happens on submission, and the ONE hard rule exists explicitly: no offer
is sent unless the role's request is agreed (RC-D5).

Read first, in order: `docs/handovers/recruit/RECRUIT_LEDGER.md` (all, incl. P1/P2 rows),
the **P1 and P2 phase reports** (API shapes: `get_board` rows, `get_requisition`,
`journey_stage`, `get_setup` cards, `get_timeline`, the role Details tab, the Hiring home
buttons P1 hid), the blueprint sections "Hiring home", "Requests without friction" and
"From offer to joined" (offer sentence only), the register lines above, then this file.
Facts below were verified 2026-09-30; P1/P2 moved lines inside `pb_hiring` — re-locate by
name.

---

## 0. Scope and binding non-goals

**In scope (P3):** `pb_hiring` **19.0.2.2.0** with a migration.
1. **Role lifecycle split from the request** (RC-D6): `state` becomes the ROLE's life
   (`setup` "Being set up" / `open` "Open for candidates" / `filled` / `closed`) and a new
   `request_state` is the REQUEST facet (`none` "No request yet" / `asked` "Waiting on
   <manager>" / `writing` "Being written" / `sent_in` "Sent in" / `agreed` / `not_approved`).
   Migration maps old states (§2.1). "Open for candidates" is a button any `can_recruit`
   user can press at any time (creates/links the job, assigns the recruiter, opens
   referrals unless confidential) — it no longer waits for the request.
2. **"Open a role"** on the Hiring home (P1 left it pointing at the raise wizard): a
   5-field sheet (title, department, country, seats, recruiter) → a role in `setup`,
   `request_state = none`, form + stages pre-filled (P1/P2 defaults), then the role page
   with a Next box: "Publish it, add candidates, or ask <manager> for a hiring request."
3. **"Ask a manager"** (home button + role Next box): pick the manager (employee), the
   role (existing or new), a line, a reminder cadence (default every 2 business days) →
   `request_state = asked`; the manager gets an email + (if internal) a to-do with a link
   to the **request page** `/hiring/r/<token>` (works for portal AND internal users, no
   login hunt): one page, the role at the top, the request questions in order, autosave
   per field, a progress line, budget with the live over-budget note, "Send in" at the
   end. Reminders on the cadence; after 3 business days (parameter) the Talent lead / Head
   of hiring get a to-do + email; "Remind now" on the role card; the card shows "Waiting on
   Budi · reminded 2 days ago".
4. **Budget** (R2): the manager types `budget_cost` (expected); `budget_confirmed`
   (Monetary, entered by recruiter/HR after checking with Finance) is new; `budget_status`
   = over when expected > confirmed (if confirmed set) or > department budget remaining
   (existing `_read_budget`, when a budget exists), else within/unknown. Over → email +
   in-app to the company's **budget-flag people** (`res.company.pb_budget_flag_user_ids`,
   m2m res.users, Settings card "Who is told when a request is over budget", seeded empty
   with a sentence naming the gap) on send-in and whenever either figure changes. Nothing
   blocks. `budget_agreement` Selection (not yet / agreed / declined) for tracking only.
5. **Sign-offs = record + notify**: the `hiring_request` route becomes ONE approve step
   (`hr_lead`, "Head of HR") plus the optional company override approver
   (`pb_mr_approver_id`) as a second approve step when set; **Finance is removed from the
   route** (today an over-budget request blocks forever because nobody holds the seat —
   verified). The manager's submission of the form IS the manager's agreement (record
   `manager_agreed_on/by` at send-in; a request raised by the manager themselves counts
   the same). `agreed` is set by `_approval_apply`. Rejection → `not_approved` with the
   reason on the role; the role itself stays usable.
6. **JD**: drop the `hiring_jd` route. JD states: draft / final. "Share draft with
   <manager> for input" → email with the text + a token page `/hiring/j/<token>` (read +
   a comment box → chatter + to-do for the recruiter). "Make final" versions it and pushes
   to the advert with a "Republish" nudge. JD templates by role family:
   `pb.hiring.jd.template` (name, family Selection = department-ish free Char, body Html
   translate) seeded with four (Field, Sales, Tech, Finance) per company.
7. **Referral opening** tied to publish (not to request agreement) and to
   `is_confidential`; an employee announcement email on opening (template exists? no —
   add `mail_template_referral_open`).
8. **Confidential toggle** `is_confidential` (replaces the visibility part of
   `sensitive_replacement`; keep that role_type value for wording): hides from referrals,
   from the careers page, from the "other roles" pick-lists, and from everyone except
   `can_recruit` users, the requester, the reporting manager and HR (record rule on the
   requisition + the board/home payloads).
9. **Recruiter auto-assignment on submission**: `_apply_country_rule` runs at role
   creation / send-in when the country is known (no longer only at open); the recruiter +
   their manager get the existing emails/to-do then.
10. **Offer gates rewired** (`offer.py`): `draft_for` no longer needs `check_ready()`;
    `action_send_to_candidate` no longer needs `_documents_ready`; BOTH need
    `requisition.request_state == 'agreed'` at SEND with the sentence "The request for
    this role is not agreed yet. Ask <names> to press Agree." (names = current seat
    holders, or the Head of HR role holders); the Offer column/drawer Next box says it
    before the recruiter hits it. Document request trigger becomes a setting
    `pb_hiring.docreq_trigger` (before_offer / on_check_clear / on_accept; default
    on_check_clear) and its 2-day escalation to the Talent lead is added. Adverse
    background-check results raise a to-do + email to the HR lead holders (no gate).
11. **Sender address**: `_sender(company)` on `pb.hiring` (clone `pb_goals` `_sender`,
    parameter `pb_hiring.sender`, fallback company email) used by EVERY pb_hiring mail
    template (`email_from`) — closes the wave-2 "no sender address" owner item.
12. Home/board updates: step strip mapping (`setup` → "Set up", open unpublished/no
    candidates → "Publish", open → "Recruit", filled → "Joined"), role card chips
    ("No request yet" amber / "Waiting on Budi" amber / "Request agreed" green /
    "Not approved" rose), Details tab "Request" section rewritten (status, figures, the
    Agree trail, "Ask <manager>", "Remind now", budget note, Confidential toggle).
13. Tests (§5), deploy (payobook / rize / template, never abm), Chrome validation, report.

**Binding non-goals:** Share-with / money masking / private notes (P4); scorecards,
Calendly (P5); offer signing / joining (P6); channels/agency (P7); email languages and
the automations list (P8 — the reminder cadence here is a field on the role, not a rule);
rebuilding the Approval Matrix UI; touching `biz_approval_workflow` code (use its API;
if a capability is missing, work around it in pb_hiring and record it).

---

## 1. Verified plumbing facts (do not re-derive)

### 1.1 Requisition lifecycle (`pb_hiring/models/`)
- States `hiring_common.py:103-112` (draft/submitted/manager_ok/hr_ok/open/filled/closed/
  refused), `REQUISITION_LIVE` :115. Fallback ladder `_approval_transitions`
  `requisition.py:99-111`. Route registration `requisition_approval.py:33-41`
  (`submit_state='submitted'`, `driven=('manager_ok','hr_ok','open')`,
  `employee_field='requested_by_id'`, `amount_field='budget_cost'`,
  `date_field='target_start_date'`); route :44-52 = manager step → `role_step('hr_lead')`
  → `role_step('finance', condition over_budget)`; seed :130-142 fills only `hr_lead` from
  the hiring-manager group (finance never filled → "Nobody holds…" `engine.py:380-390`).
- `_approval_apply` / `_approval_reject` are inherited from `chain_shim.py:462-476` /
  :491-504 (`_approval_return` :478-489); intermediate states mirror steps done
  (:438-460). `_after_approval_transition` `requisition.py:630-634` → `_on_opened` when
  state becomes open.
- Methods: `action_submit` :513-527 (needs `jd_ids` or `requirements`), `action_*_agree`
  / `action_open_role` :529-542, `action_refuse` :544, `action_mark_filled` :547-557,
  `action_close` :559-571, `action_reopen` :573-587, `_chain_engine_write` :603-628
  (sudo), `_on_filled` `requisition_a3.py:85-113`.
- `_on_opened` :662-684 legs (`_leg` :636-660): `opened_on`; `_apply_country_rule`
  :751-775 (`pb.hiring.country.rule.rule_for(company, country)`); `_ensure_job` :686-738
  (find by title+company+department or create; `no_of_recruitment` = `_wanted_on`
  :740-749; `user_id`, `manager_id`, `website_description` from `jd_current_id.body`);
  `_notify_recruiters` :777-821 (flag `pb_hiring.notify_mail`; templates
  `mail_template_requisition_recruiter` / `_recruiter_manager`; to-do "Start hiring: …");
  `_open_referrals` :823-829 (flag `referral_auto`; skipped for `sensitive_replacement`).
- `_can_raise(user)` :455-479 (hiring manager/admin group, or manages a department);
  `_require_raise` :481-488; create guard :233-241; `_approval_can` :490-508.
- Raise: `_act_create` `pb_hiring.py:602-633` (needs an employee for the login; title +
  department) extended in `journey.py` (~:422-453 working copy: level, assignment, close
  date, reporting manager same company, currency, JD/assignment files ≤10 MB, steps with
  owner in company). JS steps `hiring_board.js:361-363`, mandatory checks
  `validateRequestStep` :565-574, `saveRaise` :608-622 (P1 may have moved these).
- Company `pb_mr_approver_id` (`journey.py` ~:149); `_approval_manager_uids` (~:275-278)
  returns it instead of the requester's manager; `seed_journey` (~:541-544) sets it to the
  user named "Dhruv%" on a DB named `rize` — REMOVE that hard-coded name (it is a customer
  person; set nothing by default).

### 1.2 Approval engine (`biz_approval_workflow`, `pb_approval_config`)
- `chain_shim.py`: `register_chain(model, key, submit_state, driven, draft_state='draft',
  refuse_state='refused', reverse_to=None, employee_field, amount_field, currency_field,
  date_field)` :63-94; `manager_step(title, key='mgr', condition=None, kind='approve')`
  :97-101; `role_step(title, role, key=None, scope='company', condition=None,
  kind='approve')` :104-117; `route(*steps, independent=True, due_days=2, reassign=False,
  escalate_days=2, escalate_role=None)` :120-149.
- Step kinds `definition.py:27` review/approve/joint/any/notify/fast. `notify` fires AT
  SUBMIT (`engine.py:964-971`, `_notify_step` :1013-1036, outbox kind `notified`), creates
  no seat, and a notified person cannot open the request (read rule
  `biz_approval_workflow/security/biz_approval_workflow_rules.xml:107-111`) nor see it in
  the inbox. Notify-only route auto-approves (`engine.py:900-911`). No blocking flag, no
  ack/inform kind, no auto_approve.
- `biz.approval.request` `request.py:44-104` (state :13-22, steps :130-151, seats
  :158-175). `_approval_apply` only after every step (`_complete` → `_run_apply`
  `engine.py:1096-1141`); `decide()` :1179-1304.
- Outbox `outbox.py` kinds :18-28; `_queue` REFUSES portal (share) and inactive users :70;
  `_deliver` :103-123 (message + to-do for your_turn/reminder/escalation/returned only).
  Cron `cron_outbox` 5 min (`data/ir_cron.xml:17-23`); `cron_escalate` hourly :27-33 →
  `escalate_cron` `engine.py:1559-1606`, `_escalate_to` :1608-1651, `_late_reassign`
  :1653-1686.
- `Seed.lay(company, process_key, workflow_name, definition, binding_note='',
  model_name=None, role_keys=(), reason='')` `seed_helper.py:169-280` — publishes only
  when no published version exists (a live route is never revised by a seed → your route
  change needs a MIGRATION that publishes a new revision via `action_new_draft`
  `workflow.py:70` + `engine.publish` `engine.py:773`, or documents that tenants keep
  the old route; do the migration). `fill_role_from_group` :111-167.
- Roles are a global catalogue (`biz.approval.role`), holders per company
  (`biz.approval.responsibility`): `hr_lead` `pb_approval_config/data/roles.xml:22`,
  `finance` :30, `director` :46, `budget` :62 … **no `ceo` role, no company CEO/Head of
  HR/Finance contact fields anywhere** → hence `pb_budget_flag_user_ids` in §0.4.
- Admin UI: `pb_approval_config.action_pb_approval_matrix` (tag `pb_approval_matrix`).
- Catalogue rows `pb_hiring/data/approval_process.xml` (noupdate): `hiring_request`
  :21-29, `hiring_jd` :31-38, `hiring_offer` :45-53, `hiring_cover` :55-62. Retiring
  `hiring_jd`: mark its row inactive in a migration (do not delete).

### 1.3 Budget
- `_read_budget` `requisition.py:327-385` (+ `_refresh_budget` :404-426, `_fy_window`
  :313-325 via `pb.budget._current_fy` / `_fy_months` `pb_budget/models/pb_budget.py:113-128`,
  param `pb_budget.fy_start_month`): reads `pb.budget.line` sudo by company + department +
  `period_month` in FY (not filtered by `pb_budget_type`); remaining = Σforecast − Σactual
  vs `budget_cost`; no FX; unknown when no department :336-338 / no rows :346-349 / mixed
  currencies :351-356 / currency mismatch :360-366. Outputs `budget_status` (unknown "No
  budget set"/within/over `hiring_common.py:117-121`), `budget_remaining`,
  `budget_currency_id`, `budget_over_by`, `budget_note`, `budget_checked_on` (fields
  :159-181). Auto-refresh on write only while draft/submitted :443-450.
- `pb.budget.line` fields `pb_budget/models/pb_budget_line.py:51-129`.

### 1.4 JD, offer, BGV, docreq
- `pb.hiring.jd` `jd.py:27-72` (`version` auto :88-100, one in submission at a time
  :102-113, `action_submit` :116-126, `action_approve` :128, `_become_current` :152-176
  writes `job.website_description` only if a job exists); route `jd_approval.py:28-34`,
  :110-117 (`_jd_approver_uids` `jd.py:199-225`); nudge `hiring_automation.py:126-165`
  (param `jd_reminder_days` 3); nobody-recruiting nudge :168-208; daily cron
  `cron_hiring_daily` `data/ir_cron.xml:15-22`.
- `offer.py` `draft_for` :285-339 (needs request, `selected_applicant_id`,
  `bgv.check_ready()`), `action_send_to_candidate` :602-642 (state hr_ok/sent,
  `_documents_ready` :581-600 or force, candidate email, letter); route
  `offer_approval.py:39-56` (manager → hr_lead; `_offer_manager_uids` :154-181). **No
  request-state check at offer time anywhere** (only `posting.py:76`, `hr_job_ext.py:29`,
  `referral.py:123`, `journey.py:~316`). Stage help text mentions the rule (`journey.py:~75`).
- `bgv.py` `check_ready` :206-233, `action_override` :235-257. `docreq.py` `action_send`
  :216 (param `doc_deadline_days` 2, `_due_date` :190-214), `action_remind` :236,
  `_raise_deadline_todo` :390; chase `hiring_automation.py:345-395` (param
  `doc_reminder_days` 1).

### 1.5 Mail, tokens, portal, precedents
- Templates: `mail_template_data.xml` `mail_template_requisition_recruiter` :19,
  `_recruiter_manager` :58, `mail_template_referral_recruiter` :87, `mail_template_posting`
  :120; `mail_template_interviews.xml` (interview_candidate :31 … candidate_rejected :331);
  `mail_template_offer.xml` (docreq_ask :28, docreq_remind :68, offer_candidate :102,
  offer_answered :153, offer_closed :190, requisition_filled :221, requisition_agency
  :263). Every one uses `email_from = {{ user.email_formatted }}` (the "no sender" item,
  `RIZE_W2_CLOSEOUT.md:114`); precedent fix `pb_goals/models/goal_set.py:468` `_sender()`
  (param `pb_goals.hr_sender`, company email fallback). Board candidate mails use
  `company.email or user.email_formatted` (`journey.py:~530-533`). No `_notify`/`_todo`
  helpers; to-dos are inline `activity_schedule('mail.mail_activity_data_todo', …)`
  (`requisition.py:806-820`, `offer.py:556-569`, `hiring_automation.py:146-157, 192-203`);
  savepoint wrapper `hiring_common.leg` :330.
- Tokens: `secrets.token_urlsafe(24)` in `create` (`offer.py:211`, `docreq.py:156`,
  `panel_feedback.py:160`); `_request_for_token` patterns (`offer.py:670-685`,
  `docreq.py:273-290`, `panel_feedback.py:185-201`) — state-based, no time expiry. Routes
  `token_pages.py` all `auth='public'`, POST `csrf=False`: `/hiring/f/<token>` :57 (+
  `/submit` :66), `/hiring/d/<token>` :104 (+ `/upload` :128), `/hiring/o/<token>` :174
  (+ `/answer` :187, `/letter` :201). Clone this pattern for `/hiring/r/<token>` (request
  page, with `/save` JSON autosave + `/send`) and `/hiring/j/<token>` (JD comments).
- `/my/hiring` `portal.py:131-159` (`auth='user'`, employee via `hr.employee.user_id`
  :52-59; shows requests where requester/reporting manager :123-129). **New hires are
  PORTAL users** (`offer_closure._ensure_login` :339-362 → `pb_zoho_bridge`
  `zoho_pipeline.py:585-623`, `employee.pb_portal_user_id`, ruling D6) → the outbox skips
  them, `_can_raise` fails, `/my/hiring` redirects. Assume Rize line managers may be
  portal users: everything a manager must do in P3 works from the emailed token page; the
  inbox is a bonus for internal users.
- "Ask someone" precedents: `pb.feedback.request` (`pb_lifecycle/models/feedback.py:31-66`,
  `action_send` :137, `action_extend` :159, cron `cron_lifecycle_reminders`
  `pb_lifecycle/data/ir_cron.xml:10-16`, `_remind_feedback` :223); journey task escalation
  `lifecycle_reminders.py:108-180`; docreq reminders (above); panel feedback `_chase`
  `panel_feedback.py:312`.
- Tests: `HiringCase` `test_hiring.py:39-91` (`_requisition` :61, `_budget` :74); opening
  is simulated with `req._chain_state_write('open'); req._on_opened()` :188-236; route
  shape `TestTheApprovalWiring` :723-768; `test_offer.py` `_agreed` :370-373 writes
  `state='hr_ok'`. Engine test helpers `biz_approval_workflow/tests/common.py:12-47,50,69+`
  (`role_step`, `notify_step`, `build`, `ApprovalCase`: `_user`, `hold`, `workflow`,
  `publish`, `bind`, `ask`, `submit`, `decide`, `reload`).

---

## 2. Architecture

### 2.1 State split and migration
- `state` Selection → `setup` / `open` / `filled` / `closed` (labels "Being set up",
  "Open for candidates", "Filled", "Closed"). `request_state` Selection → `none` / `asked`
  / `writing` / `sent_in` / `hr_ok` / `agreed` / `not_approved` (labels "No request yet",
  "Waiting on the manager", "Being written", "Sent in", "Head of HR agreed", "Agreed",
  "Not approved"). `register_chain(... submit_state='sent_in', driven=('hr_ok','agreed'),
  draft_state='writing', refuse_state='not_approved', reverse_to='writing')` on the
  `request_state` field — verify `chain_shim` can drive a field other than `state`; if
  it is hard-wired to `state`, add a `state_field` kwarg in the shim (that IS a
  `biz_approval_workflow` change — allowed only for this kwarg, record it in the ledger).
- Migration (`migrations/19.0.2.2.0/post-request_facet.py`): old draft → (setup,
  writing); submitted/manager_ok → (setup, sent_in) with `manager_agreed_on` = old
  submit date; hr_ok → (setup, hr_ok); open → (open, agreed); filled/closed → keep +
  agreed; refused → (setup, not_approved). Requests with a job but old state open keep
  everything. Publish a new revision of every company's `hiring_request` route (one
  hr_lead step) and mark `hiring_jd` inactive.
- New fields: `request_state`, `asked_user_id`/`asked_employee_id`, `asked_on`,
  `ask_message`, `remind_every_days` (default 2), `last_reminded_on`, `remind_count`,
  `escalated_on`, `request_token`, `manager_agreed_on/by`, `budget_confirmed`,
  `budget_agreement`, `is_confidential`, `jd_template_id`; company
  `pb_budget_flag_user_ids`; params `pb_hiring.ask_escalate_days` (3),
  `pb_hiring.docreq_trigger`, `pb_hiring.sender`.
- Board/home payload: `request_state`, `request_label`, `request_tone`, `asked_name`,
  `reminded_ago`, `budget_flag` (sentence or ''), `is_confidential`, `can_open_role`,
  `can_send_offer` + `offer_block_reason` (the sentence).

### 2.2 The request page (`/hiring/r/<token>`)
- Public token page (clone the docreq page chrome `.pbhf-*`), shows the role title,
  department, country, who asked and their line; the questions: reason/role type,
  headcount, city, reporting manager (pick from employees of the company), role level,
  requirements or JD file, discussion focus per round (optional here; P1 steps), expected
  budget + currency, target close date, Confidential toggle. Autosave per field (JSON
  route `/hiring/r/<token>/save` with `csrf=False` like the others, but rate-limited),
  progress "6 of 9 answered", the budget note under the money field (live when
  `budget_confirmed` or a department budget exists: "This is above the department's
  budget by ₫X. The CEO, Head of HR and Finance will be told when you send it in. Nothing
  stops." — when neither exists: "No budget to compare with; the people who watch the
  budget will still see this figure."), "Send in" → validations (title/department/
  country/headcount/reporting manager/budget/close date required; requirements or JD)
  → `request_state = sent_in`, `manager_agreed_on/by` recorded, route started, budget
  flag mail if over, recruiter emailed; thank-you state on the page. Re-opening the link
  after send-in shows the read-only summary + the Agree trail. Token invalid/closed pages
  as the other token pages.
- Internal managers ALSO get a to-do; the link is the same page.

### 2.3 Reminders and escalation
- Daily leg in `cron_hiring_daily`: for `request_state == 'asked'`: if `now − max(asked_on,
  last_reminded_on) ≥ remind_every_days` (business days via `resource.calendar`? use the
  company calendar if any, else weekdays) → resend the ask email (template
  `mail_template_request_ask` with "reminder N"), bump counters; if `asked_on + escalate
  days` passed and not yet escalated → to-do + email to the Talent lead group members of
  the company (and Head of hiring) with "Budi has not completed the request for <role>
  after N days", `escalated_on` set. `_act_remind_now` from the card (max once per hour).

### 2.4 Offer rule, checks, documents
- `pb.hiring.requisition.request_is_agreed` computed; `offer.draft_for` allowed without
  BGV; `action_send_to_candidate` and the Offer column Next box use
  `_offer_block_reason(requisition)` → '' or the sentence with names
  (`_agree_holders_names()`: current open seat holders' names, else Head of HR role
  holders, else "the Head of HR"). Adverse BGV → `_flag_adverse()` to HR lead holders
  (to-do + mail) once per line. Docreq trigger setting honoured in the offer flow (fire at
  the configured moment; never gate).

### 2.5 UI
- Home: buttons "Open a role" (sheet) + "Ask a manager for a request" (sheet); role card
  chips per §0.12; the step strip mapping. Role page Details → Request section: status
  line, figures (expected / confirmed / department remaining), the trail (asked → sent in
  → HR agreed → agreed, with dates and names), "Ask <manager>" / "Remind now" / "Send in
  myself" (for `_can_raise` users), budget agreement tag, Confidential toggle (with the
  sentence of what it hides), "Who is told when over budget: <names> · Change" (opens the
  Settings card). JD section: draft/final, "Share draft with <manager>", comments list,
  "Make final", template picker. Sheets follow P1's dialog style (`pbim` modal).
- Settings → Hiring set-up gains the "Who does what" card content: budget-flag people,
  the MR approver override, the line-manager move switch (P1), the docreq trigger.

---

## 3. Design (build to the blueprint)

Design bar verbatim (ledger): **"exceptional premium, extreme WOW, a novice can work
without training"**. Hero moment for P3: the manager's one-page request that saves as
they type and tells them, in one gentle sentence, what will happen with an over-budget
figure — and the role card that says "Waiting on Budi · reminded 2 days ago · Remind
now". Zero dead-ends: a role with no request explains what it can and cannot do; an
offer that cannot be sent names who must press Agree; a token that is closed says why
and who to contact. Plain words: "Agreed", "Sent in", "Waiting on", "Not approved". Every
new string translated (vi_VN + id_ID `.po` entries, three comment lines).

---

## 4. Rules (plain English on screen)
- A role never waits for its request. The request only matters for sending an offer.
- The manager's "Send in" is their agreement. HR (and the company's named approver, if
  any) press Agree from the inbox or their email; nothing waits for them.
- Over budget tells people; it blocks nothing. The figure and who was told are on the
  role's timeline.
- Confidential hides the role from referrals, adverts and everyone but the hiring team,
  the requester and the reporting manager.
- Reminders stop the moment the request is sent in; "Remind now" never sends twice in an
  hour.

---

## 5. Numbered test cases
1. Migration maps every old state pair as §2.1; a role that was open keeps its job,
   recruiter and referrals; routes re-published with one hr_lead step; `hiring_jd`
   process inactive.
2. "Open a role" creates a role in setup/none with defaults; "Open for candidates" works
   with `request_state = none` (job created, recruiter assigned by country, referrals
   opened unless confidential).
3. Ask a manager: token created, mail sent from `_sender`, to-do for internal manager,
   `request_state = asked`; the token page renders; autosave writes fields; send-in with a
   missing required field re-renders with the sentence; complete send-in sets sent_in +
   manager agreement + starts the route + assigns the recruiter.
4. Reminders: cadence honoured in business days; escalation after 3 days to Talent lead
   members; "Remind now" throttled; reminders stop after send-in.
5. Budget: expected > confirmed → over; flag mail + to-dos to `pb_budget_flag_user_ids`;
   no people configured → the timeline says "Nobody is set to be told about over-budget
   requests" and a to-do goes to Head of hiring; nothing blocks; changing either figure
   re-flags once per change.
6. Route: hr_lead decides → agreed; reject → not_approved with reason; the role stays
   usable either way; the company override approver adds a step when set.
7. Offer: draft without BGV OK; send with request not agreed → UserError with the names;
   send after agreed OK; docreq trigger setting fires at the right moment; adverse BGV
   flags HR lead once.
8. JD: share sends mail + token page; a comment lands in chatter + to-do; make final
   versions + pushes the advert text; templates seeded per company; `hiring_jd` route no
   longer created.
9. Confidential: hidden from referral portal, careers page, other-roles lists, and from a
   non-team internal user's board/home.
10. Sender: every hiring template renders `email_from` from `_sender`, never empty when
    the acting user has no email.
11. Existing tests pass (rewrite the ones asserting the old ladder / gates).
Browser (payobook.com, light + dark; the token page also at 360 px):
12. Home: Open a role → role page → Publish → board usable with no request; card chip "No
    request yet".
13. Ask a manager → email (check mail queue) → open the link logged out → fill → over-budget
    note → send in → chip "Sent in" → inbox shows the HR step → Agree → chip "Request agreed".
14. Try to send an offer on a role without an agreed request → the sentence with names;
    after Agree → the send proceeds (stop before the actual candidate email if the demo
    address is real).
15. Remind now; escalation to-do visible to the talent lead login after forcing the date.
16. Confidential on → the role disappears from the referral page and careers page.
17. No console errors; no red style bar; translations present.

## 6. Deploy and verify
Tier **risky** (migration + route re-publish + security rule). Backups ×3, rehearse the
migration on a clone of `payobook` (it has the most requests), then payobook, rize,
template; asset purge + version bump + signaling row; hash + version checks; one Chrome
walk on payobook.com; cheap checks elsewhere. Demo: one asked request, one over-budget
request, one confidential role on payobook, registered with `pb.demo.seed`. Commits per
feature; no push. Ledger rows; phase log.

## 7. Report back
P1 §7 format: live where/versions/commits; tests 1–17; design-bar self-score;
deviations (esp. anything you had to change in `biz_approval_workflow`); ledger rows +
API shapes for P4–P6 (`request_state`, `_offer_block_reason`, `_sender`, the token
routes); owner items (who the budget-flag people should be per company; whether Rize's
line managers are portal or internal users); demo records table.
