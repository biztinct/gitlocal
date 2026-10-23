# RECRUIT — Phase 5: scorecards people fill in, Calendly on the move, Google Meet, the finalists side by side

Delivers register lines **G-18, G-30, G-32, G-37, G-38** (and keeps G-31/G-33/G-34
behaviour intact): scorecard templates per role family and per discussion round
(free-text areas, star rating, decision Yes / Maybe / No / Hold, optional scored lines);
an interviewer page from a private link that is actually sent; "Enter it for them" for
recruiters; reminders that repeat until done and tell the Talent lead when late; the
recruiter's own Calendly link sent automatically when a candidate moves into Recruiter
review; Google Calendar + Google Meet for interviews (RC-D3), with a transcript slot; and
a finalists comparison with one-click decisions.

Read first, in order: `docs/handovers/recruit/RECRUIT_LEDGER.md` (all rows incl.
P1–P4), the **P1–P4 phase reports** (shapes: `_act_journey_stage` payload and its
`interview_prompt`, `get_candidate.scorecards`, `parts_for`, `pb.hiring.share`,
`_sender`), the blueprint sections "Scorecards that people actually fill in" and "The
candidate drawer", the register lines, then this file. Facts verified 2026-09-30 on the
working copy; re-locate moved lines by name.

---

## 0. Scope and binding non-goals

**In scope (P5):** `pb_hiring` **19.0.2.4.0** with a migration; new dependency
`google_calendar` (core CE; brings `google_account`).
1. **Scorecard templates** `pb.hiring.scorecard` + `pb.hiring.scorecard.part`; seeds per
   company: Recruiter review, Tech, Non-tech, Operations, Go-to-market (Anita's four +
   one); chosen per role round (`pb.hiring.step.scorecard_id`), with a role-family
   default; the Hiring set-up "Scorecards" card becomes live (list, parts editor with
   drag reorder, preview of the interviewer page).
2. **Feedback answers** stored per part (`answers_json`), `decision` Yes / Maybe / No /
   Hold (+ migration of `recommendation`), `score_avg` from rating parts; the interviewer
   page rebuilt from the template; the "please share your opinion" email actually sent
   (at scheduling with the link, and again when the interview ends); late links stay open;
   hidden-between-panellists kept.
3. **Enter it for them** (recruiter proxy) with the source note; repeating reminders
   (due → daily), Talent lead told at 2 days late; "Remind" on the card; opinions still
   accepted after the candidate moved on (already true — keep it and test it).
4. **Calendly rule**: `res.users.pb_scheduling_link`; a move into `phone` (Recruiter
   review) sends the "Let's chat" message with the recruiter's link automatically (switch
   `pb_hiring.phone_auto_mail`, default 1); the toast names it; missing link → the toast
   says how to add it. (P8 generalises into the automations list; P5 ships the rule.)
5. **Google Calendar + Meet**: when the interview's organiser (recruiter) has connected
   Google, the calendar entry is created on Google with a Meet link, which lands on the
   interview (`videocall_url`), in the invites, the `.ics`, the board and `/my/hiring`;
   reschedule and cancel follow; "Connect Google Calendar" from Hiring set-up → People
   and from the scheduling sheet; without a connection everything works as today (link
   typed by hand). `transcript_url` + `transcript_attachment_id` slot (hiring groups only).
6. **Finalists side by side**: `get_finalists(requisition_id)` + a Compare view on the
   role page (columns = candidates, rows = round × panellist, decision chips, ratings,
   notes; "Choose", "Keep warm", "Not this time" per column); choosing sets
   `selected_applicant_id` as the debrief does today.
7. Tests, deploy (three DBs, never abm), Chrome validation, report.

**Binding non-goals:** the automations list UI (P8); email language versions beyond what
P2 did (P8); transcript auto-pull from Google Drive/Meet (later — record as owner item);
SMS; changing `biz_approval_workflow`; the Interviews tab redesign beyond adding the
Meet link, transcript slot and proxy entry; assessments.

---

## 1. Verified plumbing facts (do not re-derive)

### 1.1 Interview (`pb_hiring/models/interview.py`)
- Fields: `requisition_id` :65, `applicant_id` :68, `step_id` :71 (`pb.hiring.step`),
  `round_no` :80 (from `_next_round` :258-280), `kind` :96 (from `step_id.kind`
  :194-199), `start` :100, `duration_minutes` :102, `stop` :105, `mode` :107, `location`
  :109 (Char; room / address / video link), `panel_employee_ids` :113, `recruiter_id`
  :116, `candidate_name/email` :124-127, `job_id` :128, `event_id` :132, `state` :136,
  `no_show_by` :139, `no_show_note` :141, `cancel_note` :142, `reminder_24h_sent` :144,
  `reminder_30m_sent` :146, `rescheduled_from/to_id` :149-154, `reschedule_ids` :155,
  `late_notice` :157, `feedback_ids` :163, `feedback_due_at` :165, `feedback_in/total/late`,
  `recommendation_avg` :169-173 (:219-236), `debrief_notes` :175, `decision` :176,
  `decided_on` :178, `company_id` :181. Selections in `hiring_common.py`: `STEP_KINDS`
  :134-142, `INTERVIEW_STATES` :167-173, `INTERVIEW_MODES` :178-182, `NO_SHOW_BY` :184,
  `DELAY_KINDS` :191, `DEBRIEF_DECISIONS` :212-216, `FINAL_KINDS=('final','panel')` :220.
- `schedule()` :362-416 → `create` (:241-261 refuses >5 min in the past) →
  `_after_scheduled` :418-440 (legs: `feedback_due_at`, `_ensure_event`, `_mint_feedback`,
  `_move_candidate_stage`, `_invite_candidate`, `_invite_panel`, `_invite_recruiter`).
  `_check_panel` :282-289 (≥1 panel member); `journey.py:519-527` referrer-not-on-panel.
- `_ensure_event` :445-481: context `dont_notify`, `no_mail_to_attendees`,
  `mail_create_nolog`, `mail_notrack`; `partner_ids` = panel users' partners + recruiter's
  partner; **the candidate is not an attendee and has no partner**; vals name/start/stop/
  allday/duration/location/description/`user_id` (recruiter or current user)/`applicant_id`;
  no videocall fields. `_event_title` :483, `_agenda_text` :490.
- `.ics`: `_ics` :503-518 (`pb_lifecycle.models.ics.build_ics`; organiser recruiter,
  attendees panel + candidate, uid `pbhiring-interview-<id>@payobook`), `_ics_attachment`
  :520-528, `_send` :533-554 (`email_to`, `force_send=False`), `_invite_candidate` :556
  (gated `P_CANDIDATE_MAIL`), `_invite_panel` :570 (one mail each), `_invite_recruiter`
  :586. Templates `data/mail_template_interviews.xml`: candidate :31, panel :75 (**no
  token link inside**), recruiter :119, tomorrow :148, soon :178, off :203,
  feedback_ask :237 (**defined, never sent by any code**), feedback_urgent :272,
  candidate_next_round :303, candidate_rejected :331.
- `_mint_feedback` :597-619 (one row per panel member, no duplicates);
  `_move_candidate_stage` :621-635 (plain write, no `just_moved`). Reschedule
  `reschedule()` :640-727 (reason + `delay_kind` required; new row same `round_no`;
  `pb.hiring.reschedule` :919-957; old row `rescheduled`; `_tell_everybody_it_is_off`
  :738; `_drop_event` :729-736 archives the event with the silent context;
  `fresh._after_scheduled(move_stage=False)`); `LATE_NOTICE_MINUTES=30` :55. No-show
  `action_no_show` :755-778 (expires pending feedback, to-do :780). `action_mark_done`
  :797-822 relaxed by P1 (posts "N of M opinions still to come"). `action_cancel`
  :824-837. Debrief `action_debrief(notes, decision)` :842-875 (only `kind in FINAL_KINDS`;
  `select` writes `requisition.selected_applicant_id` :206-210 and posts).
- Steps: `pb.hiring.step` `requisition.py:42-84`; `journey.py:618-627` creates
  "Discussion N" steps with `kind='interview'` and stage `discussion_N`.
- Reminders: `hiring_automation.py` `run_reminders` :220-242 (switch `P_REMINDERS`),
  `_due_interviews` :262-281, `_remind_day_before` :284, `_remind_half_hour` :291,
  `_remind_each` :298-309; model `interview._remind` :880-896; cron
  `cron_hiring_interview_reminders` `data/ir_cron.xml:39-46` (10 min); daily
  `cron_hiring_daily` :14-22. Working hours `interview._feedback_due` :327-357
  (`company.resource_calendar_id.plan_hours(hours, when, compute_leaves=True)`; no
  calendar → plain hours, logged).
- Portal `/my/hiring` `controllers/portal.py:131-158` (`_feedback_owed` :98-103,
  `_my_interviews` :105-121), `.ics` route :181-208; template `views/portal_templates.xml`
  owed :318-345 (link `ask._token_url()` :341), interview cards :353-390.

### 1.2 Feedback (`pb_hiring/models/panel_feedback.py`)
- `pb.hiring.criterion` :45-79 (`name`, `sequence`, `help_text`, `active`, `company_id`;
  `criteria_for(company)` :66-79) — one global list, no role/round link; seeds
  `data/hiring_criteria.xml` (5 company-less rows: role_skills, problem_solving,
  communication, values, motivation).
- `pb.hiring.feedback` :82-132: `interview_id`, `panel_employee_id`, `panel_user_id`,
  related applicant/requisition, `token` :108 (`secrets.token_urlsafe(24)` :156-161),
  `due_at` :110, `state` :111 (pending/submitted/expired `hiring_common.py:196`),
  `ratings_json` :114 (`[{id,name,score}]`), `recommendation` :115 (strong_no/no/yes/
  strong_yes :203; `RECOMMENDATION_SCORE` :210), `notes` :117, `submitted_at`,
  `urgent_sent_at` :120, `score_avg` :122; constraints unique(token), unique(interview,
  panel member). `_token_url` :178 (`/hiring/f/<token>`), `_request_for_token` :184-201
  (late link stays open), `page_facts` :208-226, `submit` :231-260 (validates criterion
  ids + 1–5), `_summarise_if_complete` :262-307 (chatter line + recruiter to-do), `_chase`
  :312-343 (ONE urgent mail + to-do, stamps `urgent_sent_at`; leg
  `hiring_automation._chase_late_feedback` :315-339), `action_copy_link` :354-370 (proxy
  `pb_hiring.py:_act_copy_feedback_link` :867-876), board remind `board_p1._act_remind_opinion`
  :352-368.
- Controller `controllers/token_pages.py` GET `/hiring/f/<token>` :57-64, POST `/submit`
  :66-89 (`c_<id>`, `recommendation`, `notes`); template `views/token_templates.xml:45-125`
  (`hiring_feedback_page`: radios :86-97, "Would you hire them?" :99-110, notes :112-116).
- Security: company rule :127-131; `rule_feedback_own` :188-193 (panel user or the
  interview's recruiter); `rule_feedback_all` :195-200 (hiring_user); ACL csv :41-50
  (criterion write only admin/system).

### 1.3 Stage-move hook and messages
- `hr_applicant_ext.py write` :54-81 only logs the move (`pb.hiring.stage.log.note_move`,
  `stage_log.py:57`; skip with `pb_no_stage_log`). `journey.py HiringApplicant.write`
  :307-312 guards the touch fields. **`_act_journey_stage` lives in
  `board_p1.py:254-338`** (class `PbHiringBoardP1(_inherit='pb.hiring')` :191): payload
  `applicant_ids|applicant_id`, `key|stage_id`, `reason`, `hold_until`, `send_email`,
  `undo`; writes with `just_moved=True` :299; posts a note only with a reason / undo
  :300-305; emails only for `cv_reject`/`interview_reject` when `send_email` :308-313
  (`_pb_tell_candidate` `hr_applicant_ext.py:259-279`); returns `interview_prompt` when
  a scheduled interview has ended. Stage `template_id` never fires on board moves
  (`_track_template` `hr_applicant.py:884-898` suppressed by `just_moved`); P1 clears
  `template_id` on retired stock stages (`journey.py:282`).
- Recruiter review: key `phone`, name "Recruiter review" (`journey.py:25`); `MEANINGS`
  :63 deliberately does NOT promise Calendly and `tests/test_stages_p1.py:239-243`
  enforces that → update both meaning and test in this phase (the promise becomes true).
- "Let's chat" message: `data/journey_content.json` key `phone` (line 12) with
  `{{hr_name}}`, `{{duration}}`, `{{scheduling_link}}`; model `pb.hiring.message.template`
  `journey.py:530-558`; `_render` :543-558 (base tokens first_name, role, brand, website,
  linkedin, company_intro, sender_name, hr_name; unknown tokens raise unless supplied in
  `values`; P2 made body/subject translatable); `_act_message_preview` :665-673,
  `_act_message_send` :675-689 (posts a note, creates `mail.mail`, gated
  `P_CANDIDATE_MAIL`); `seed_journey` :692-709; test `tests/test_journey.py:53-56`.
- No scheduling/Calendly field exists on `res.users` or `hr.employee` in pb_hiring.
- `P_*` params and defaults (`hiring_common.py:28-93`): platform_mail 0, referral_auto 1,
  notify_mail 1, referral_mail 1, jd_reminder_days 3, recruiter_nudge_days 3, reminders 1,
  candidate_mail 1, feedback_hours 24, urgent_after_hours 0, interview_duration 45,
  reminder_cap 400, doc_deadline_days 2, doc_reminder_days 1, offer_mail 1, closure_mail
  1, create_contract 1, line_managers_move 0 (+ P2–P4 additions).

### 1.4 Google on this build (core `/Users/adity/odoo19/odoo/addons/`)
- Present: `google_account` (no version key, depends `base_setup`), `google_calendar`
  (1.0, depends `google_account`, `calendar`), `google_gmail` (1.2, auto_install). **No
  pb/biz module references them**; whether installed on payobook is unknown from code —
  check `ir_module_module` on each DB first.
- `google_calendar/models/calendar.py`: `MEET_ROUTE` :19; `videocall_source` adds
  `google_meet` :25 (compute :40-44); synced fields incl. `videocall_location` :47-49;
  `create` passes `dont_notify` :57-63; `_get_sync_domain` :126-139 syncs only events
  whose `partner_ids.user_ids` contain the syncing user; `_odoo_values` :164 reads the
  Meet URL via `get_meeting_url()` (`utils/google_event.py:235-239`); `_google_values`
  :302-377 builds `conferenceData={'createRequest':{'requestId':uuid}}` ONLY when no
  `google_id`, no `videocall_location` **and no `location`** (:350-351) → leave
  `location` empty for video interviews (put the room in the description for in-person);
  `organizer = user_id.email`; `_get_event_user` :390-394 (organiser if they hold a
  token, else current user).
- `google_calendar/models/google_sync.py`: `after_commit` :27-48 (skipped by context
  `no_calendar_sync`); `create` :80-97 inserts into Google right away when the creating
  user's sync is not paused and `need_sync`; `_google_insert` :303-316;
  `_get_post_sync_values` :287-293 writes ONLY `google_id` → **the Meet URL only arrives
  on the next Google→Odoo sync** unless you read it from the insert response. Utils
  `google_calendar/utils/google_calendar.py`: `insert` :74-81 (`conferenceDataVersion=1`,
  `sendUpdates` from context `send_updates` all|none), `patch` :84, scope :118-120,
  `_google_authentication_url` :122-137, `_can_authorize_google` :139 (`group_erp_manager`).
  Verify what `insert` RETURNS (the created event resource with `hangoutLink` /
  `conferenceData.entryPoints` when `conferenceDataVersion=1`); if it returns only the
  id, call `get_events`/`_sync_google2odoo` for that user right after, in the same leg.
- `google_calendar/models/res_users.py`: token fields :20-25 (`groups=base.group_system`),
  `_get_google_calendar_token` :27-31, `_get_google_sync_status` :33,
  `_sync_google_calendar` :52-86, `_sync_all_google_calendar` :141; storage
  `res_users_settings.py:16-22`, `_set_google_auth_tokens` :37,
  `_refresh_google_calendar_token` :52. `google_account/models/google_service.py`:
  `_get_client_id` :41-44 (param `google_<service>_client_id`), `_get_client_secret`
  :22-34, `_get_authorize_uri` :47, `_get_google_tokens` :72, `_refresh_google_token`
  :94, `GOOGLE_TOKEN_ENDPOINT` :18; callback `google_account/controllers/main.py:13`
  (`/google_account/authentication`). Settings `google_calendar/models/res_config_settings.py:9-11`
  (`cal_client_id` → `google_calendar_client_id`, secret, `cal_sync_paused`); per-user
  connect = jsonrpc `/google_calendar/sync_data` (`controllers/main.py:12-60`) from the
  calendar view JS; cron `ir_cron_sync_all_cals` every 12 h (`data/google_calendar_data.xml`).
- Core `calendar.event` (`calendar/models/calendar_event.py`): `videocall_location` :141,
  `access_token` :142, `videocall_source` :143 (discuss/custom), `_compute_videocall_location`
  :529-533, `_set_videocall_location` :544, `_compute_videocall_source` :555-561,
  `_set_discuss_videocall_location` :563-573; `alarm_ids` :212; `create` :658 (attendees
  from `partner_ids` :660-669; invitation mails :713 blocked by `no_mail_to_attendees` /
  `calendar.block_mail` `calendar_attendee.py:141`; alarms unless `dont_notify` :725);
  write `dont_notify` :839, `skip_attendee_notification` :851-855.
  `hr_recruitment/models/calendar.py:33` adds `applicant_id`. `calendar_no_videocall`
  has no reader in core CE.

### 1.5 Debrief and tests
- `_act_interview_panel` `pb_hiring.py:878-897` (per opinion who/state/verdict/score/
  notes/due/chased); `_interview_row` :361-407 (`recommendation_avg`, `decision`,
  `can_debrief`); `get_candidate.scorecards` `board_p1.py:681-696` (per interview:
  round_no, when, state, rows who/state/late/score/verdict/notes[:280]); no per-part
  breakdown, no cross-candidate payload. `selected_applicant_id` readers: `offer.draft_for`
  (`offer.py:286-305`; P3 keeps the selection precondition), `pb_hiring_a3._journey` :260,
  `bgv.py:164`, `pb_hiring.py:463`; `journey.py:421-428` moves the applicant to `offer` on
  draft. Interviews tab `static/src/xml/hiring_board_p1.xml:164-172` → `pb_hiring.IvList`
  (`hiring_board.xml:1416+`); drawer opinions `hiring_board_p1.xml:294-307`.
- Tests `tests/test_interviews.py`: `InterviewCase` :38-134 (`setUp` :43-100: recruiter,
  `panel_one` with login, `panel_two` without, opened requisition, applicant), `_tomorrow`
  :103, `_mails` :107, `_schedule(**extra)` :110-121, submit pattern :471-500, source check
  `test_the_calendar_is_silenced_both_ways` :991-998 (asserts `dont_notify=True` and
  `no_mail_to_attendees=True` appear in `_ensure_event` — keep them true); no mocks anywhere.
  `tests/test_board_p1.py:17` reuses `_schedule`.

---

## 2. Architecture

### 2.1 Scorecards
- `pb.hiring.scorecard`: `name`, `company_id`, `role_family` (Char, free; matched
  case-insensitively against the role's department name / `pb_role_level`? NO — keep a
  simple Selection `family`: recruiter_review / tech / non_tech / operations / gtm /
  other), `applies_to` (Selection: any_round / discussion_1 / discussion_2 / discussion_3
  / final), `intro` (Text shown to the interviewer), `part_ids`, `active`, `is_default`.
- `pb.hiring.scorecard.part`: `scorecard_id`, `sequence`, `kind` (`text` free-text with
  a prompt / `rating` 1–5 stars with a prompt / `line` scored line 1–5 from a criterion /
  `yes_no`), `prompt` (Char), `help` (Char), `required`. The **decision** (Yes / Maybe /
  No / Hold) is not a part — every scorecard ends with it, always required.
- Seeds per company (idempotent): Recruiter review (text "How did the conversation go?",
  rating "Overall fit", text "Anything to check next round?"); Tech (line role skills,
  line problem solving, rating "Depth", text "Strengths", text "Concerns"); Non-tech
  (rating communication, rating values, text, text); Operations (rating "Field readiness",
  rating "Judgement in scenarios", text); Go-to-market (rating "Commercial reasoning",
  rating "Stakeholder skills", text). Owner item: Anita's actual designs replace these.
- Assignment: `pb.hiring.step.scorecard_id` (default from the role: the role's
  `scorecard_family` (new Selection on the requisition, set from the department preset
  or by the Talent lead) + the round's `applies_to` match, else the company default);
  `pb.hiring.interview.scorecard_id` (related to step, editable before the interview).
- Feedback: `answers_json` `[{part_id, kind, prompt, value}]`, `decision` Selection
  yes/maybe/no/hold, keep `recommendation` + `ratings_json` for old rows (migration:
  strong_yes/yes → yes, no/strong_no → no; ratings → `line` answers under a synthetic
  "Legacy scorecard"); `score_avg` = mean of rating + line values; `entered_by_user_id`,
  `entered_via` (Char, e.g. "Slack message, 3 Oct"), `reminder_count`, `last_reminded_at`,
  `lead_told_at`.
- Interviewer page: header (candidate, role, round, when, panel), the shared CV button
  when the role's share defaults give the panel `cv` (P4 `parts_for` with the panellist's
  user; if no user, only when the Talent lead set "panel sees CV" on the role), the
  intro, the parts (textarea / 5 stars / 1–5 line / yes-no), the four big decision
  buttons, the sentence "Your answers stay hidden from the other panellists until
  everyone is in.", autosave draft in sessionStorage, submit; after submit a thank-you
  with "You can still change this until the recruiter decides" (allow re-submission
  while the interview is not decided — `state` stays submitted, a new `submitted_at`).
- Emails: `mail_template_feedback_ask` SENT at scheduling (inside the panel invite:
  add the token link to `interview_panel` template instead of a second mail) AND when
  the interview `stop` passes (10-minute cron leg: "How did it go? Fill in your
  scorecard" with the link; stamp `ask_sent_at`). Chase: at `due_at` (24 wh), then
  every 24 h (`reminder_count`, `last_reminded_at`), Talent lead members + Head get a
  to-do + mail at 2 days late (`lead_told_at`), all in `_chase_late_feedback`. Stop when
  submitted / interview cancelled / candidate closed.
- Proxy: `_act_feedback_proxy({feedback_id, answers, decision, notes, source})`
  (`_require_recruit`) → same validation as `submit`, stamps `entered_by_user_id`,
  `entered_via`; the summary line and the drawer say "entered by An (Slack message,
  3 Oct)". Board: "Enter it for them" on each pending opinion (drawer + Interviews tab).

### 2.2 Calendly rule
- `res.users.pb_scheduling_link` (Char, URL-validated with `clean_url`), editable in
  Preferences (user form inherit, own record) and in Hiring set-up → People ("Recruiters'
  scheduling links" table). Switch `pb_hiring.phone_auto_mail` (default 1).
- In `_act_journey_stage` after the write: for each moved applicant, if `key == 'phone'`
  and the switch is on and `applicant.email_from`: sender = the role's `recruiter_id` or
  the current user; if they have a link → `_act_message_send` equivalent with
  `values={'scheduling_link': link, 'duration': 30}` (message key `phone`, in
  `applicant.pb_lang`) and add `mail_sent: "the Calendly email went out"` to the toast;
  else add `warning: "No Calendly link on your profile yet · Add it in Preferences"` (the
  toast shows it with a link). Undo of the move does not unsend (say so in the toast).
- Update `MEANINGS['phone']` to "A 30-minute conversation with the recruiter. Moving here
  sends the Calendly link." and `tests/test_stages_p1.py:239-243`.

### 2.3 Google Calendar + Meet
- Depend on `google_calendar`. Hiring set-up → People card: "Google Calendar: connected /
  not connected" per recruiter with a "Connect" button that opens the standard authorise
  URL (`GoogleCalendarService._google_authentication_url` with `from_url` back to the
  Hiring set-up); the company-level client id/secret stay in Settings → General
  (`cal_client_id`/`cal_client_secret`) — show a sentence + link when they are empty
  ("Google Calendar is not set up for this company yet. An administrator pastes the
  Google client id and secret in General settings.").
- `_ensure_event`: keep the silent context for Odoo mails; if the organiser
  (`user_id`) has a Google token and `mode == 'video'` and no `location` → create the
  event with `location` empty (`_google_values` will request a Meet) and context
  `send_updates='none'` (pb sends its own branded invites); after creation, read the Meet
  URL from the insert response (verify `insert` return; else run a one-off
  `_sync_google2odoo` for that user in the same leg) and write it to
  `interview.videocall_url` (new Char) and `event.videocall_location`; the `.ics` and all
  three invite templates include the link; if the link is not available within the leg,
  send invites without it and a follow-up "Your video link" mail once the sync fills it
  (10-minute cron leg watches `videocall_url` empty + `event.videocall_location` set).
  Add the candidate as an attendee: create/reuse `applicant.partner_id` (verify the field
  exists on this build; else a `res.partner` with the applicant email, `type='contact'`,
  linked via `pb_partner_id`) so Google shows them on the event; Odoo invitation mails
  stay blocked. Reschedule → the new row's event patches Google (write start/stop on the
  same event instead of archive+create when Google-synced, to keep the Meet link; else
  as today); cancel → archive → Google delete (`_google_delete` via sync). In-person /
  phone modes: no Meet; `location` used as today.
- `transcript_url` (Char) + `transcript_attachment_id` on the interview; "Paste the
  recording or transcript link" in the Interviews tab row and the drawer's scorecards
  section; visible only to hiring groups (payload-masked).
- Testing: unit tests mock `GoogleCalendarService` (`unittest.mock.patch` on
  `insert`/`patch`/`delete`) — the first mocks in pb_hiring; document the pattern in the
  ledger. Real-account end-to-end: if `google_calendar_client_id` is set on payobook, run
  the connect flow with the QA login and one real interview; if not, STOP at the connect
  button, report exactly what the owner must do (create an OAuth client in Google Cloud,
  paste id/secret), and mark the end-to-end test as "blocked on credentials".

### 2.4 Finalists side by side
- `get_finalists(requisition_id)` → `{candidates:[{id, name, stage, rounds:[{round_no,
  scorecard, when, opinions:[{who, decision, score, notes}]}], avg, decision_counts}],
  rounds:[…], can_decide}` for candidates in `discussion_*`, `reference`, `offer` (not
  closed); `_act_finalist_decide({applicant_id, decision: choose|warm|no, note})` →
  choose = `requisition.selected_applicant_id` + move to `offer` (+ post as the debrief
  does); warm = `on_hold` with the note; no = `interview_reject` (+ optional email).
  No gate on missing opinions (show "2 of 3 in").
- UI: role page header button "Compare finalists" → a full-width grid view (columns
  candidates, sticky first column with rounds × panellists, decision chips coloured, star
  ratings, notes on hover/expand, an "Overall" row with average and decision counts),
  per-column footer buttons; keyboard ←/→ between columns.

---

## 3. Design (build to the blueprint)

Design bar verbatim (ledger): **"exceptional premium, extreme WOW, a novice can work
without training"**. Hero moment for P5: the interviewer page — one screen, the four
big decision buttons, stars that light on hover, the reassuring "hidden until everyone
is in" line; and the finalists grid where a decision is one click per column. Zero
dead-ends: a missing Calendly link says where to add it; Google not connected says who
connects it; a late opinion says who is late and offers "Enter it for them". Plain words
("Yes / Maybe / No / Hold", "How did it go?", "Your video link"). Translations (vi_VN +
id_ID) for candidate-facing strings; interviewer page is English (call decision R11).
Light and dark.

---

## 4. Rules (plain English on screen)
- Every discussion has a scorecard; the Talent lead decides which one per role and round.
- Interviewers never move candidates; they give their opinion.
- Opinions are hidden from other panellists until all are in; recruiters and the Talent
  lead see them as they arrive.
- A late opinion is chased daily and the Talent lead is told after two days; the
  candidate never waits for it.
- A recruiter may enter an opinion for a panellist; the record says who typed it and
  where it came from.
- Moving into Recruiter review sends the recruiter's own Calendly link; nothing else in
  the product schedules that call.

---

## 5. Numbered test cases
1. Seeds create five scorecards per company with parts; idempotent; a step picks the
   right scorecard by family + round; company default fallback.
2. Migration converts old feedback rows (`recommendation` → `decision`, ratings → legacy
   answers) with `score_avg` unchanged.
3. Interviewer page renders the template's parts; submit validates required parts and
   the decision; re-submit before the interview is decided updates; after a candidate
   moved on, submit still works.
4. Panel invite contains the token link; the "How did it go?" mail goes once after
   `stop`; chase at due, daily after, Talent lead told at 2 days late, stops on submit /
   cancel / candidate closed.
5. Proxy entry stamps who/via; the summary and drawer show it; a non-recruit user cannot
   proxy.
6. Calendly: move to `phone` with a link → `mail.mail` queued in `pb_lang` with the link
   and the toast text; without a link → warning text, no mail; switch off → nothing;
   bulk move sends one per candidate; undo does not unsend.
7. Google (mocked): organiser with token + video mode → event created without location,
   `conferenceData` requested, Meet URL written to `videocall_url`/`videocall_location`,
   invites and `.ics` contain it; organiser without token → today's path; reschedule
   patches the same event; cancel deletes; the candidate partner is an attendee; Odoo
   attendee mails still blocked (source check kept).
8. `get_finalists` shape; `finalist_decide` choose/warm/no effects; no gate on missing
   opinions.
9. Transcript fields masked from non-hiring readers.
10. Existing tests pass (update `test_stages_p1.py` meaning assertion).
Browser (payobook.com, light + dark; the interviewer page at 360 px):
11. Hiring set-up → Scorecards: list, parts editor, drag reorder, preview.
12. Role Details → rounds: pick a scorecard per round.
13. Schedule an interview (no Google) → open the panel link → fill → submit → drawer shows
    the answers per part and the decision chip.
14. "Enter it for them" on a pending opinion → stamped line visible.
15. Move a card into Recruiter review with the demo recruiter's Calendly link set → toast
    names the email; check the mail queue.
16. Compare finalists → grid → "Choose" moves the card to Offer and marks selected.
17. Google connect button state; if credentials exist: connect the QA account, schedule a
    video interview, see the Meet link on the interview and in the invite mail.
18. Transcript link paste → shows for the recruiter, absent for the hiring-manager login.
19. No console errors; no red style bar.

## 6. Deploy and verify
Tier **risky** (new dependency install on three DBs, migration of feedback rows). Backups
×3; rehearse on a clone of payobook; install `google_calendar` (brings `google_account`)
where missing; `-u pb_hiring`; asset purge etc.; hash + versions; one Chrome walk; cheap
checks elsewhere. Demo (payobook): scorecards on two demo roles, three opinions incl. one
proxy, one Calendly link on the demo recruiter, one transcript link — registered.
Commits per feature; no push. Ledger rows (incl. the mock pattern); phase log.

## 7. Report back
P1 §7 format; tests 1–19; self-score; deviations (esp. the Google insert-response
finding); ledger rows + shapes for P6–P8 (`answers_json`, `decision`, `get_finalists`,
`videocall_url`, `pb_scheduling_link`, the phone rule hook point for P8); owner items
(Anita's real scorecards; Google OAuth client credentials; transcript auto-pull); demo table.
