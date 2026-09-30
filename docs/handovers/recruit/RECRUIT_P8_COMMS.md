# RECRUIT — Phase 8: every candidate email in three languages, and automations the talent lead owns

Delivers register lines **G-35, G-47, G-48, G-50**: every candidate-facing email is one
editable template with English, Vietnamese and Bahasa Indonesia versions chosen by the
candidate's language; the Talent lead edits them from Hiring set-up without developer
mode; an "Automations" list ("When a candidate enters Recruiter review, send Let's chat
to the candidate right away") the Talent lead edits, with built-in rows shown beside it
so the whole picture is one list; the remaining notification-matrix gaps closed
(document escalation to the Talent lead, background check started, referral
announcement, rejection wording per stage). Internal emails stay English (R11).

Read first, in order: `docs/handovers/recruit/RECRUIT_LEDGER.md` (all rows incl.
P1–P7), the **P1–P7 phase reports** (shapes: `pb_lang` and `_render` changes (P2),
`request_state` + `_sender` (P3), `parts_for` (P4), the Calendly hook in
`_act_journey_stage` and `feedback` reminders (P5), `join_status` + prejoin mails (P6),
`pb.hiring.channel` + agency mails (P7)), the blueprint "Rules that bind every screen",
the register lines, then this file. **The facts below were read before P2–P7 landed**
(the working copy had none of them yet) — treat every "today" as "before P2" and
reconcile with the phase reports first.

---

## 0. Scope and binding non-goals

**In scope (P8):** `pb_hiring` **19.0.2.7.0** with a migration.
1. **One mechanism for candidate email**: the five `pb.hiring.message.template` rows
   (received / phone / assignment / on_hold / cv_reject) become standard `mail.template`
   records on `hr.applicant` (QWeb placeholders replace `{{token}}`), with the `lang`
   field driven by the candidate; every existing candidate-facing template gets the
   same `lang` expression, Vietnamese and Indonesian subject/body translations
   (seeded), and `email_from` from `_sender`. The old model and its "Candidate emails"
   screen retire (migration converts rows; per-company edits preserved as per-company
   templates). Candidate copies of the shared interview mails (tomorrow / soon / off)
   become their own templates so the candidate text can differ from the panel text.
2. **Emails and languages screen** (Hiring set-up card, live): the candidate-facing
   templates as a list ("When it goes" sentence, languages complete / missing), open →
   an editor with EN / VI / ID tabs for subject and body (rich text through the native
   `mail.template` form in a dialog with a trimmed arch, VU-skinned), "Send me a test",
   "Reset to the standard text"; internal templates listed read-only with "English
   only" and a link for administrators.
3. **Permissions**: the Talent lead may edit templates on pb_hiring models and
   `hr.applicant` (a scoped write rule), never other apps' templates.
4. **Automations** `pb.hiring.automation` + `pb.hiring.automation.run` with a dispatcher
   hooked at every state-write point the phases left; editable rows as sentences; built-in
   rows shown read-only (application received, interview invites and reminders, opinion
   asks and chases, document request and reminders, offer sent, week-before, join
   confirmations); delayed actions through a queue on the 10-minute cron; waiting-days
   events on the daily cron; a run log; "Try it on a candidate" dry-run. The P5 Calendly
   rule becomes a seeded editable row (same behaviour).
5. **Matrix gaps**: document request escalation after 2 business days → Talent lead
   to-do + mail; background check started → recruiter to-do; referral announcement to
   employees when referrals open (template + switch, OFF by default — owner item);
   rejection templates per stage (CV reject / Interview reject / Offer declined) with
   the message keys mapped; opinion overdue → Talent lead (P5 did it — verify and keep).
6. Tests, deploy (three DBs, never abm), Chrome validation, report, and the **programme
   close-out** (§8).

**Binding non-goals:** SMS; re-consent emails; changing `biz_approval_workflow` (offer
and request sign-off reminders stay the engine's); `base_automation` (not used —
our list is simpler and owned by the Talent lead); an OWL rich-text editor (use the
native form in a dialog); internal emails in Vietnamese.

---

## 1. Verified plumbing facts (do not re-derive; read "today" as "before P2")

### 1.1 Candidate messages
- `pb.hiring.message.template` `models/journey.py:538-566`: `name`, `sequence`,
  `company_id` (required), `key` (received/phone/assignment/on_hold/cv_reject :545-546),
  `subject` Char, `body` Text (P2 made both `translate=True` — confirm), `active`;
  `_render(applicant, values)` :551-566 (regex `{{x}}`; built-ins first_name, role,
  brand, website, linkedin, company_intro, sender_name, hr_name; unknown token raises
  except website/linkedin/company_intro); senders query by company + key
  (`controllers/application.py:126-127`, `journey.py:677-678`); `_act_message_preview`
  :673-681, `_act_message_send` :683-696 (flag `P_CANDIDATE_MAIL`, posts a note, creates
  `mail.mail` directly with `text_html(body)`, `email_from=company.email or user`);
  the `received` send `controllers/application.py:126-132` (direct `mail.mail`); seed
  `data/journey_content.json` (`emails[{name,subject,body,key}×5]`, `sections`, `intro`),
  `seed_journey` :699-717 (per company, missing keys only). Screen: no action xmlid —
  inline act_window from `_act_open_templates` (`journey.py:668-671`) reached from the
  Setup card "Emails and languages" (`board_p1.py:946-948`); views
  `view_hiring_message_list/form` (`views/journey_views.xml:16-18`); company rule
  `hiring_message_company_rule` :2-6; ACL user read-only, talent lead/admin/system CRUD
  (`security/ir.model.access.csv:99-101,105`). Only test: `tests/test_journey.py:51-59`.
- Candidate-facing `mail.template`s (all: no `lang`, `email_from = {{ user.email_formatted }}`
  (P3 → `_sender`), `auto_delete=False`, hard-coded English):
  `mail_template_interview_candidate` (`mail_template_interviews.xml:31`; sent
  `interview.py:567`), `_interview_tomorrow` :148 (`interview.py:884`),
  `_interview_soon` :178 (:885), `_interview_off` :203 (:748) — **the same text goes to
  candidate, panel and recruiter** (`interview.py:888-894`, :741-751);
  `_candidate_next_round` :303 (`hr_applicant_ext.py:239-241` → `_pb_tell_candidate`
  :259-278), `_candidate_rejected` :331 (`hr_applicant_ext.py:254-256`,
  `board_p1.py:308-313` — one template for `cv_reject` AND `interview_reject`);
  `mail_template_docreq_ask` (`mail_template_offer.xml:28`; `docreq.py:226` → `_mail`
  :248-261, **not gated by any switch**), `_docreq_remind` :68 (`docreq.py:244`),
  `_offer_candidate` :102 (`offer.py:634` → `_mail` :644-662, gated `P_OFFER_MAIL`).
  All sends: `template.sudo().send_mail(id, force_send=False, email_values={'email_to':…})`;
  interview helper `_send` `interview.py:533-554`. P5/P6/P7 added more (feedback ask,
  join-week, prejoin buddy/laptop, agency invite/assigned) — take them from the reports.
- Core rendering: `mail.template.subject` translate (`addons/mail/models/mail_template.py:51`),
  `body_html` translate :69-72, `name`/`description` :39-41; `lang` Char on
  `mail_render_mixin.py:55`; `_render_lang` :721-748 (uses `self.lang` per record, else
  the record's partner lang via `_mail_get_partners` `addons/mail/models/models.py:151-170`
  which reads `partner_id`/`partner_ids`); `_classify_per_lang` :750-773;
  `_render_field(compute_lang=…)` :775; `_generate_template` :608. `hr.applicant.partner_id`
  exists and its inverse creates the partner with `lang = env.lang`
  (`hr_recruitment/models/hr_applicant.py:242-246`); interview/docreq/offer have NO
  partner → they render in English unless `lang` is set. Stock stage `template_id`
  auto-post unless `just_moved` (:885-897) — pb stages carry none (`journey.py:287`).
  Precedent `lang` expressions: `pb_timeoff/data/mail_template.xml:26,56`; translated
  template bodies in `.po`: `pb_pay_delivery/i18n/vi_VN.po:29,643,980`.

### 1.2 Internal mails, to-dos, toasts
- Internal templates (English, keep): `mail_template_requisition_recruiter` /
  `_recruiter_manager` (`mail_template_data.xml:19/:58`; `requisition.py:786-802`,
  flag `notify_mail`), `_referral_recruiter` :87 (`referral.py:207-213`, flag
  `referral_mail`), `_posting` :120 (`posting.py:193-197`), `_interview_panel`
  (`mail_template_interviews.xml:75`; `interview.py:581`), `_interview_recruiter` :119
  (:591), `_feedback_ask` :237 (no sender before P5), `_feedback_urgent` :272
  (`panel_feedback.py:321-326`), `_offer_answered` (`mail_template_offer.xml:153`;
  `offer.py:748`), `_offer_closed` :190 (`offer_closure.py:443-470`, flag
  `closure_mail`), `_requisition_filled` :221 (`requisition_a3.py:122-137`),
  `_requisition_agency` :263 (`requisition_a3.py:178-189`). 21 records in three files
  before P3.
- To-dos: all `mail.mail_activity_data_todo` (`_TODO` constants `hiring_automation.py:33`,
  `docreq.py:39`, `offer.py:49`, `interview.py:50`, `panel_feedback.py:39`); call sites
  `hiring_automation.py:150` (agree the advert → JD approver), :195 (name a recruiter →
  first hiring admin), `requisition.py:808` (start hiring → recruiter),
  `panel_feedback.py:297` (decide next step), :333 (chase an opinion), `interview.py:784`
  (no-show), `docreq.py:381` (papers in), :404 (chase the papers), `offer.py:561` (send
  the offer), :752 (accepted / turned down). No custom activity types; no notification
  model for hiring (`pb.alert` is tenant/vendor only). Toasts: `act` returns `{'note'}`
  → `hiring_board.js:636-647` `notification.add`; P1 undo toast `showToast`
  `hiring_board.js:1630-1635`; setup `hiring_setup.js:73`.

### 1.3 Automation precedents and hook points
- No pb module depends on `base_automation` (core `addons/base_automation/`,
  `base.automation` `models/base_automation.py:142`, triggers :173-197, date fields
  :216-237, domains :243-250, `action_server_ids` :153; server action `mail_post` +
  `template_id` `addons/mail/models/ir_actions_server.py:28,61,116`). Closest pb rule
  model: `pb.zoho.event.rule` (`pb_zoho_bridge/models/event_rule.py:50-77`: `trigger`,
  `match_value`, `action`, `sequence` first-match, computed sentence `name`; native
  views `event_rule_views.xml:13,30`). Journey steps `pb.journey.template.step`
  (`pb_lifecycle/models/journey_template.py:86-125`; `automation_key` +
  `_automation_handlers()` `pb_onboarding/models/journey_ext.py:54-82`, runner
  `pb_onboarding.py:266`). Approval routes are JSON built by `route()`
  (`chain_shim.py:120-155`) edited in the `pb_approval_config` builder cockpit.
- Hook points (before P2–P7; add the ones the reports name): stage write
  `hr_applicant_ext.py:54-82` (old stage snapshot unless `pb_no_stage_log`; `note_move`
  in `leg`); `journey.py:313-318` touch guard; `board_p1._act_journey_stage` :254-338
  (`just_moved=True` :299); other stage writes `hr_applicant_ext.py:236`,
  `interview.py:621-638`, `journey.py:396`, :261-262; `pb_no_stage_log` only at
  `journey.py:262,396`; `date_last_stage_update` core :91 (:661/:674; read
  `board_p1.py:445,475,750`). Interview: `schedule` :363 → `_after_scheduled` :418;
  `reschedule` :712; `action_no_show` :765; `action_mark_done` :812; `action_cancel`
  :830; `action_debrief` :862. Feedback `submit` → `state='submitted'`
  `panel_feedback.py:255`, `_summarise_if_complete` :259. Offer `action_submit` :506,
  `_after_approval_transition` :537, `_on_approved` :543, `action_send_to_candidate`
  :636, `record_decision` :724-729, `action_record_signed` :807, closure :94 (P6:
  `action_confirm_joined` / `action_did_not_join`). Requisition `action_submit`
  `requisition.py:513-527` (P3: `request_state` writes), `_after_approval_transition`
  :630 → `_on_opened` :662, `action_mark_filled` :547, `action_close` :559,
  `action_reopen` :573, agency hook `requisition_a3.write` :149. Referral `refer`
  `referral.py:108-146` (override `journey.py:493`). Docreq `receive` :322 → `_all_in`
  :372 (leg :368), `action_send` :223, `action_remind` :245. BGV `open_for` `bgv.py:152`
  (chatter only :177), `action_set` :309, `action_override` :235.
- Matrix gaps (before P5): late opinion → `_chase_late_feedback` `hiring_automation.py:315-339`
  → `_chase` `panel_feedback.py:312-344` (panel member mail + recruiter to-do only);
  document deadline → `_document_deadlines` :372-392 → `_raise_deadline_todo`
  `docreq.py:390-417` (one recruiter to-do, `deadline_todo_on`; `_chase_documents`
  :345-369 keeps mailing the candidate daily; default 2 working days
  `hiring_common.py:81`); BGV started → nothing; referral opened → `_open_referrals`
  `requisition.py:823-829` sets the flag only, no employee mail; rejection → one
  template; offer route `offer_route()` `offer_approval.py:50-55` defaults (`late`
  remind 1 / escalate 2 / `to_role` None → escalates to the route publisher).
- Crons: `cron_hiring_daily` (`data/ir_cron.xml:14-22`) → `run_now`
  (`hiring_automation.py:50-70`, `(key, fn)` list jd / recruiter / late_feedback /
  documents / doc_overdue / cover + `counts`; `describe` :73-120);
  `cron_hiring_interview_reminders` :38-46 (10 min) → `run_reminders` :219-242 (flag
  `reminders`). Helpers `hiring_common.py`: `leg` :335-348, `flag` :350-354, `number`
  :357-363 (no `param_int`), param constants :28-51, `DEFAULTS` :53-92, setup `SWITCHES`
  `board_p1.py:55-58`.
- Languages: `res.lang.get_installed()` core `res_lang.py:311`; `_pb_vi()` `journey.py:195-197`;
  stage-name translations via `update_field_translations` :221-244; `i18n/vi_VN.po`
  only (P2 adds `id_ID.po` — confirm the file name that loaded).
- Templates UI: `mail.action_email_template_tree_all` (`addons/mail/views/mail_template_views.xml:144-152`)
  under Technical (`base.group_no_one`); editing all needs `mail.group_mail_template_editor`
  (only `base.group_system` implies it, `mail_groups.xml:15-21`); otherwise the rule
  limits to own/assigned (`mail_security.xml:275-295`); no pb group implies the editor
  group. VU exclusion list `biz_theme/static/src/js/vu_form_renderer.js:16-21`
  (`mail.template` not excluded → the native form is skinned). No OWL HTML editor in
  any cockpit (plain `<textarea>`s: `hiring_board_p1.xml:371,449`, `hiring_board.xml:401,436`).
- Tests: `_mails()` `test_interviews.py:107-108` (diff before/after), `tearDown`
  :123-133 cancels mail; `test_t1_every_mail_this_phase_sends_resolves` :842-856.

---

## 2. Architecture

### 2.1 One mechanism for candidate email
- New `mail.template` records (xmlids `mail_template_c_received`, `_c_lets_chat`,
  `_c_assignment`, `_c_on_hold`, `_c_cv_reject`, `_c_interview_reject`,
  `_c_offer_declined_ack`? (no — declined is the candidate's own act; skip),
  `_c_interview_tomorrow`, `_c_interview_soon`, `_c_interview_off`) on `hr.applicant`
  (or the interview model for the three interview ones), each with
  `lang = {{ object.pb_lang or (object.partner_id and object.partner_id.lang) or 'en_US' }}`
  (interview/docreq/offer: `object.applicant_id.pb_lang …`), `email_from` from
  `_sender` (P3 pattern), QWeb placeholders (`object.partner_name.split(' ')[0]`,
  `object.job_id.name`, `object.company_id._hiring_brand()` …), and a `pb_hiring_kind`
  Char on `mail.template` (new field: `candidate` / `internal`, plus `pb_when` sentence
  and `pb_key`) so the Emails screen can list them. Seed Vietnamese and Indonesian
  translations for every candidate template (`update_field_translations` on `subject`
  and `body_html`, texts in `data/mail_i18n.py`; `.po` entries for `model:mail.template`
  as `pb_pay_delivery` does are ALSO acceptable — pick one, say which).
- Migration: for each company × `pb.hiring.message.template` row whose subject/body
  differ from the seed → a company-specific copy of the matching new template
  (`company_id` set, `pb_company_override=True`), translations copied when P2 added them;
  then the old rows are archived and the model kept read-only for one release (remove
  next). `_act_message_send` / preview and the P5 Calendly rule switch to the new
  templates through one helper `pb.hiring._mail_candidate(template_xmlid_or_key,
  applicant, values=None, attachments=None)` (company-specific override first, else the
  shared one; `send_mail(force_send=False)`; posts the note; respects
  `P_CANDIDATE_MAIL`; returns the `mail.mail`). The `received` send in the apply
  controller uses it. Docreq mails get gated by `P_CANDIDATE_MAIL` too (today ungated).
- Rejection per stage: `_pb_tell_candidate` picks `_c_cv_reject` for `cv_reject` and
  `_c_interview_reject` for `interview_reject`; on-hold move (with the "send email"
  tick) sends `_c_on_hold`.

### 2.2 Emails and languages screen
- `get_emails()` → `[{id, key, name, when, kind, langs:{en_US:'ok', vi_VN:'ok'|'missing',
  id_ID:…}, overridden}]` for candidate templates (per company: the override if any),
  and the internal list read-only; `_act_email_open({id})` → act_window dict WITH
  `views` (RC13) on `mail.template` form with a trimmed arch (name, subject, body_html,
  the translate button; `lang`/`model` hidden) opened as a dialog; `_act_email_test({id,
  lang})` sends to the current user with a sample applicant (dry render);
  `_act_email_reset({id})` restores the seed text + translations;
  `_act_email_override({id})` creates the company copy. Missing-language detection via
  `get_field_translations` (empty or equal to source).
- Permission: record rule on `mail.template` for `group_hiring_manager`: write/create/
  unlink on templates whose `model` ∈ pb_hiring models + `hr.applicant` and
  `pb_hiring_kind` set; read all. Verify against `mail_security.xml:275-295` that the
  rules OR correctly for a Talent lead who is also a plain user; if the base rule is
  global (not group-scoped) it will AND and block — then fall back to a sudo'd
  `_act_email_save` from our dialog with a server-side check, and say so.

### 2.3 Automations
- `pb.hiring.automation`: `company_id`, `name` (computed sentence), `sequence`,
  `active`, `builtin` (Boolean, read-only rows), `event` (Selection: `applied`,
  `stage_entered`, `stage_waiting`, `interview_scheduled`, `interview_done`,
  `interview_no_show`, `opinions_all_in`, `documents_complete`, `check_started`,
  `offer_sent`, `offer_accepted`, `offer_declined`, `offer_signed`, `joined`,
  `did_not_join`, `request_sent_in`, `request_agreed`, `referral_received`,
  `agency_submitted`), `stage_id` (for stage events), `days` (for waiting),
  `department_ids` / `country_ids` (optional filters on the role), `action` (Selection:
  `send_email` / `todo` / `move_stage` / `tag`), `template_id` (domain by
  `pb_hiring_kind`), `recipient` (Selection: candidate / recruiter / hiring_manager /
  talent_lead / panel / custom), `custom_emails`, `todo_text`, `target_stage_id`,
  `tag_id`, `delay_hours` (0 = right away), `once_per_candidate` (default True),
  `run_count`, `last_run_at`. `pb.hiring.automation.run`: `automation_id`,
  `res_model`, `res_id`, `applicant_id`, `due_at`, `state` (queued / done / skipped /
  failed), `result` (Char), `ran_at`.
- Dispatcher `pb.hiring.automation._fire(event, record, applicant=None, ctx=None)`:
  find active rows for the company + event (+ stage / filters); for each: skip if
  `once_per_candidate` and a done run exists; `delay_hours == 0` → run inline in a
  `leg` (never raise into the caller); else queue a run with `due_at`. Runner
  `_run_one(run)` executes the action (email via `_mail_candidate` / `_mail_internal`
  with `_sender`; to-do via `activity_schedule`; stage via `_act_journey_stage` with
  reason "automation"; tag). Queue processed by the 10-minute cron leg; `stage_waiting`
  evaluated daily (candidates whose `date_last_stage_update` ≤ now − days in that
  stage, once). Hook calls at every point in §1.3 (+ the P2–P7 ones): keep them
  one-liners inside `leg` so an automation can never break a move.
- Built-ins: rows with `builtin=True` describing the code-driven mails (application
  received, interview invite + 24 h + 30 min, opinion ask + chases, document request +
  reminders + escalation, offer sent, week-before, join confirmations, agency assigned)
  with `template_id` linked so "Edit the email" works; toggles on built-ins map to the
  existing `P_*` switches (`candidate_mail`, `reminders`, `offer_mail`, `closure_mail`,
  `referral_mail`, `notify_mail`, `phone_auto_mail`) — one switch each, shown as the
  row's toggle.
- Seeds (editable, per company): "When a candidate enters Recruiter review → send Let's
  chat to the candidate right away" (ON; replaces P5's hard-coded rule — remove that
  code path and keep its tests through this row); "When a candidate enters Assignment →
  send Assignment brief to the candidate right away" (ON); "When a candidate has waited
  7 days in Applications received → to-do for the recruiter 'Give them a first look'"
  (OFF); "When an offer is accepted → to-do for the hiring manager 'Name a buddy'" (OFF;
  P6 does this by the prejoin list — keep OFF and say it duplicates).
- UI (Hiring set-up → Automations, live): the list as sentences with a toggle per row,
  built-ins in a quiet group ("Always on unless you switch it off"), "Add a rule" → a
  sheet that builds the sentence from four pickers (When … / for … / then … / after …),
  a live preview of the sentence, "Try it on a candidate" (dry-run: what would happen,
  which template in which language), a run log tab (last 100 runs: when, what, result),
  and per-row "Edit the email" that opens the Emails editor.

### 2.4 Matrix gaps
- Document escalation: in `_document_deadlines`, when `deadline + 2 business days` has
  passed and not `escalated_on` → Talent lead members to-do + `mail_template_docreq_late`
  (English), stamp; the candidate chase continues.
- Check started: `bgv.open_for` → recruiter to-do "Background check started for <name>".
- Referral announcement: `_open_referrals` → if flag `referral_announce` (new, default
  '0') → `mail_template_referral_open` to every employee of the company with a work
  email (batched 50 per mail.mail BCC or one per employee — choose per-employee with
  `force_send=False`; cap 2000, log the count), from `_sender`; the Set-up switch says
  "Tell every employee by email when a role opens for referrals (off: the card just
  appears on their portal)".
- Rejection wording per stage: §2.1. Offer declined: candidate gets nothing (their
  act); the recruiter mail exists.
- Late opinion → Talent lead: verify P5's `lead_told_at` path; if missing, add here.

---

## 3. Design (build to the blueprint)

Design bar verbatim (ledger): **"exceptional premium, extreme WOW, a novice can work
without training"**. Hero moment for P8: the Automations list reads like sentences a
person would say, and "Try it on a candidate" shows exactly what would happen before a
rule is switched on. Zero dead-ends: a missing translation is a "missing" chip that
opens the right tab; a template with an error renders the error sentence in the
editor's preview, not in a candidate's inbox (the test-send catches it); a rule with no
recipient cannot be saved and says why. Plain words: "When … then …", "right away",
"after 2 days", "Send me a test". Light and dark.

---

## 4. Rules (plain English on screen)
- A candidate gets email in the language they applied in; if a translation is missing,
  English goes out and the timeline says so.
- The Talent lead edits candidate emails; internal emails stay English and are the
  administrator's.
- Built-in rules can be switched off but not deleted; your own rules can be anything the
  four pickers allow.
- A rule runs once per candidate unless you say otherwise; the run log shows every time
  it ran and why it was skipped.
- An automation can never stop a move; if it fails, the move still happens and the
  failure is in the log.

---

## 5. Numbered test cases
1. Migration: five message-template rows per company → templates; a company that edited
   a subject gets a company override; old rows archived; `_mail_candidate('received',
   applicant)` renders the override; `lang` picks `pb_lang`, then partner lang, then
   English; VI and ID translations present on every candidate template (seed), and an
   applicant with `pb_lang='vi_VN'` receives Vietnamese subject/body.
2. Interview candidate mails (invite / tomorrow / soon / off) use the candidate
   templates in the candidate's language while panel/recruiter mails stay English.
3. Docreq mails obey `candidate_mail`; rejection per stage picks the right template;
   on-hold email on request.
4. `get_emails` shape and missing-language detection; `email_test` sends to the current
   user; `email_reset` restores; the Talent lead can write a pb template and cannot
   write a template of another app (rule test with `with_user`).
5. Automations: `_fire` matches company/event/stage/filters; inline run; queued run
   with delay executed by the 10-minute leg; `once_per_candidate`; a failing action
   logs `failed` and the triggering move still succeeds; `stage_waiting` fires once per
   candidate after N days; built-in toggles map to the `P_*` switches; the seeded
   Calendly row reproduces P5's behaviour and P5's tests still pass through it.
6. Hook coverage: one test per event that a matching rule fires (applied, stage_entered,
   interview_done, opinions_all_in, documents_complete, check_started, offer_sent,
   offer_signed, joined, request_sent_in, referral_received, agency_submitted).
7. Matrix gaps: document escalation after 2 business days to Talent lead once; check
   started to-do; referral announcement respects the switch and the cap; late opinion →
   Talent lead (from P5) still works.
8. Dry-run returns the would-be actions without sending or writing.
9. Existing tests pass (retire message-template tests or port them).
Browser (payobook.com, light + dark):
10. Hiring set-up → Emails and languages: list with language chips; open "Let's chat";
    VI tab; edit the subject; save; "Send me a test" arrives in the mail queue in
    Vietnamese.
11. Automations: toggle the built-in reminders off and on; add a rule ("When a candidate
    has waited 3 days in Shortlist → to-do for the recruiter"); "Try it on a candidate";
    force the daily leg; the to-do appears; the run log shows it.
12. Move a demo candidate into Recruiter review → the seeded row sends Let's chat in
    the candidate's language; the toast names it.
13. No console errors; no red style bar.

## 6. Deploy and verify
Tier **risky** (migration of message templates, new hooks on every state write). Backups
×3; rehearse on a clone of payobook; payobook, rize, template; asset purge etc.; hash +
versions; one Chrome walk; cheap checks elsewhere. Demo (payobook): the seeded rules,
one custom rule, one company override, registered. Commits per feature; no push. Ledger
rows; phase log.

## 7. Report back
P1 §7 format; tests 1–13; self-score; deviations (esp. the template write-rule
finding); ledger rows; owner items (referral announcement default; which internal mails
Rize wants in Vietnamese despite R11; whether the Head of hiring should edit internal
templates); demo table.

## 8. Programme close-out (this phase also writes it)
`docs/handovers/recruit/RECRUIT_CLOSEOUT.md`: what is live per DB with versions; every
owner item from P1–P8 in one numbered list; every demo login; every switch and its
default; the register lines G-01…G-58 with their final status (Have / Built in Pn /
Deferred / Rize-side); the rulings R1–R12 and RC-D1…; unpushed commits count; what the
next session must know. Plus `docs/design/rize-recruit-closeout.html` — a plain-English
page for the owner mirroring the gap register's structure with the "after" column
filled in (publishable as an artifact by Fable).
