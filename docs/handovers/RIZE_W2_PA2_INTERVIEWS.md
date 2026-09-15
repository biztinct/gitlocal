# RIZE Wave 2 — Phase A2: `pb_hiring` interview loop

A1 is live (`pb_hiring 19.0.1.0.0`, commits 17260086a…95ae021f1, ledger
R131–R142). A2 adds everything between "candidates are in the pipeline" and
"we have decided": scheduling with invitations, reminders, rescheduling with
a reason, no-shows, panel feedback by personal link with a 24-working-hour
timer, next-round / rejection mails, and the debrief on the final round.

Read first: `docs/handovers/RIZE_LEDGER.md` (all — note **R131** savepoint
legs and **R132** intermediate states, both found by A1), then
`RIZE_W2_HANDOVER.md` Parts A, B, C1, then `RIZE_W2_PA1_HIRING.md` §1 (the
verified store facts still hold), then this file. Bump `pb_hiring` to
`19.0.1.1.0`; new routes get a migration.

---

## 0. Scope and binding non-goals

**In scope:** `pb.hiring.interview` (+ reschedule history, no-show log),
`calendar.event` behind it (stock invitation mails silenced; OUR mails with
ICS), 24-hour and 30-minute reminders, the panel feedback form on a token
page (`/hiring/f/<token>`) with criteria, the 24-working-hour timer and the
urgent reminder, "Next round" / "Reject" doors with editable mail templates,
debrief notes + decision on the final round, a stage log on the applicant
(A3's time-in-stage needs it), the board's Interviews view, `/my/hiring`
for hiring managers and panel members, ⌘K 3550/3560.

**Non-goals (A3):** BGV, document request, offer, pay package, letter,
candidate review page, closure → onboarding, recruiter cover, agency tag,
analytics lens. Do not add Google Calendar (D12). Do not edit A1's routes.

---

## 1. Verified facts (beyond A1 §1)

- **A1 API (from the A1 report):** `pb.hiring.requisition` states
  `draft → submitted → manager_ok → hr_ok → open → filled|closed` (+`refused`),
  fields `title, role_type, department_id, country_id, location, headcount,
  target_start_date, requested_by_id, requested_by_user_id,
  reporting_manager_id, recruiter_id, recruiter_manager_id, job_id,
  jd_current_id, step_ids, posting_ids, referral_ids, applicant_ids,
  referral_open, published, opened_on`; hooks `_on_opened()`, **`_leg(name,
  fn)`** (savepoint per paperwork leg — use it for every mail/activity leg),
  `_ensure_job()`, `_person(emp)`. `pb.hiring.step`: `requisition_id,
  sequence, name, kind (screen/call/interview/test/panel/final/other),
  owner_id, days_expected, notes`. Facade `pb.hiring.act(verb, payload)`
  with gates `_require_recruit()` / `_require_write()`. Referral state map
  `received / in_progress / hired / not_this_time`. Country rule
  `pb.hiring.country.rule.rule_for(company, country)`. Process keys
  `hiring_request`, `hiring_jd`. Groups `pb_hiring.group_hiring_user|manager|admin`.
- **Calendar:** `calendar.event` create sends alarms/invitations unless
  context `dont_notify` (`calendar/models/calendar_event.py:725`) and
  attendee mails are skipped with context `no_mail_to_attendees`
  (`calendar_attendee.py:140`). Create the event
  `with_context(dont_notify=True, no_mail_to_attendees=True)` so the
  stock (branded) invitation never goes out. `hr_recruitment/models/
  calendar.py:33` adds `applicant_id` to the event — set it. Fields:
  `name, start, stop, duration, allday, partner_ids, user_id, location,
  description`.
- **ICS:** `pb_lifecycle/models/ics.py:48 build_ics(summary, dt_start,
  dt_end=None, organizer=None, attendees=None, description='',
  location='', uid=None)` → bytes; naive UTC datetimes. Attachment pattern:
  `pb_onboarding/models/journey_ext.py:181-236 _auto_day1_ics` (creates
  `ir.attachment` with `datas`, passes `attachment_ids` in `email_values`).
- **Working hours:** `resource.calendar.plan_hours(hours, day_dt,
  compute_leaves=False, domain=None, resource=None)`
  (`resource/models/resource_calendar.py:849`) — the company's
  `resource_calendar_id`; fallback `+ 24h` when a company has none, and say
  so in the log. `get_work_hours_count` (:798) for reporting.
- **Token page precedent:** `pb.feedback.request` (`pb_lifecycle/models/
  feedback.py:31`): `token` minted with `secrets.token_urlsafe(24)` in
  `create` (:84), `_token_url` (:89), `_request_for_token(token)` → `(rec,
  'invalid'|'used'|'closed'|'ok')` (:96), `questions()` JSON shape (:110),
  `submit_answers` (:170). Controller `pb_lifecycle/controllers/
  token_pages.py:112-160` (auth public, `sitemap=False`, render key is
  `feedback` never `request` R4, POST `csrf=False`, redirect `?done=1`).
  No field-level `groups=` on the token (R13); protect with ACL + rule +
  never in a view/payload.
- **Applicant stage move:** write `stage_id`; the stock model handles
  `date_closed`/`hired_stage` (A1 §1.1). Refuse = write `refuse_reason_id`
  + `active=False` via the stock `action_refuse`-like path you used in A1's
  `screen`.
- **Portal:** A1's `/my/refer` controller and `.pbme` kit; `pb_offboarding`
  home-card precedent (eager key R62).
- **Actors:** recruiter `rize.w2.recruiter@example.com` / `RizeW2!2026`
  (A1, company 5); hiring manager `diep.thai@example.com` / `RizeP9!2026`
  (uid 2336, employee 17139); panel members: `lam.ngo@example.com` (uid
  2326, employee 17122, HAS a login) and employee **17140** (rize.p10.a, NO
  login — give it `work_email = rize.p10.a@example.com` if empty; this is the
  "panel member without a login gets a link by mail" case); candidates = the
  A1 test applicants on "RIZE W2 Site Agronomist". Validator
  `igc1.validator` / `RizeP0!2026` for admin work. Passwords drift (R74).

---

## 2. Models

- **`pb.hiring.interview`** (`mail.thread`, `mail.activity.mixin`):
  `requisition_id` (req), `applicant_id` (req, domain = the requisition's
  job), `step_id` (pb.hiring.step, optional), `round_no` (int, computed:
  1 + earlier non-cancelled interviews of this applicant), `kind` (related
  `step_id.kind`, fallback `interview`), `start`, `duration_minutes`
  (default 45), `stop` (computed stored), `mode` (in_person / video /
  phone), `location` (Char: room or link), `panel_employee_ids` (m2m
  hr.employee), `recruiter_id` (default requisition.recruiter_id),
  `candidate_name/email` (related sudo, R56), `event_id`
  (calendar.event), `state` scheduled → done | no_show | cancelled |
  rescheduled, `no_show_by` (candidate/interviewer), `no_show_note`,
  `reminder_24h_sent`, `reminder_30m_sent` (Datetime), `feedback_ids`,
  `feedback_due_at` (computed at scheduling: `plan_hours(24, stop)`),
  `debrief_notes` (Text), `decision` (select / hold / reject, final rounds
  only), `company_id`. Constraint: start in the future at creation; panel
  non-empty.
- **`pb.hiring.reschedule`**: `interview_id, old_start, new_start, reason`
  (required), `delay_kind` internal/external (required), `by_user_id`,
  `at`. A reschedule = cancel the event, create a new one, `state =
  rescheduled` on the old interview and a NEW interview row linked by
  `rescheduled_from_id` (history stays whole; analytics count delays).
- **`pb.hiring.feedback`**: `interview_id, panel_employee_id, token`
  (unique, minted in create), `due_at`, `state` pending → submitted |
  expired, `ratings_json` (per criterion 1–5), `recommendation`
  (strong_yes / yes / no / strong_no), `notes`, `submitted_at`,
  `urgent_sent_at`, `company_id`. `_request_for_token` clone. Criteria:
  **`pb.hiring.criterion`** (`name, sequence, company_id`, seeded
  company-less R8 with five defaults: Role skills, Problem solving,
  Communication, Values fit, Motivation) — the "template" the sheet asks
  for, editable under Settings → Hiring.
- **`pb.hiring.stage.log`**: `applicant_id, from_stage_id, to_stage_id, at,
  by_user_id`; written from a `write` override on `hr.applicant` when
  `stage_id` changes (additive, in `hr_applicant_ext.py`).
- Security: same ladder; rules the PAIR (R60). Feedback rows readable by
  recruiters+ and by the panel member's own user (`panel_employee_id.user_id
  = user.id`); the token page reads under sudo after `_request_for_token`.

## 3. Behaviour

- **Schedule** (`act('schedule', {...})`, recruiter gate): creates the
  interview + `calendar.event` (silenced context, `applicant_id`,
  `partner_ids` = panel users' partners + recruiter, `user_id` recruiter),
  then three legs under `_leg`: candidate invite (mail + ICS, only if
  `candidate_email`), panel invite (one mail per member, to `user.email`
  or `work_email` read as sudo, with ICS and the agenda = step notes + JD
  link), recruiter copy. Applicant stage moves to the step's stage if the
  step names one, else untouched. Feedback rows minted per panel member
  with `due_at = plan_hours(24, stop, compute_leaves=True)` on the
  company calendar. Feedback link mail goes out **after the interview**
  (the 10-minute job, once `stop < now`), not at scheduling.
- **Reminders** (`ir.cron` every 10 min, `pb_hiring.reminders` switch
  default 1): interviews `scheduled` with `start` in `[now+23h50, now+24h10]`
  and `reminder_24h_sent` empty → mail candidate + panel + recruiter, stamp;
  `[now+25m, now+35m]` → 30-minute mail, stamp. Idempotent by the stamps;
  cap as a parameter (R76); server clock (R36).
- **Reschedule** (`act('reschedule', {reason, delay_kind, start, …})`):
  refuses without reason or kind; cancels the event (unlink or `active`
  False — check what the stock event supports), mails a cancellation +
  new invitation, opens the new row. "Must notify 30 min before" from the
  sheet = a warning chip on the board when a reschedule is made inside 30
  minutes, not a block.
- **No-show** (`act('no_show', {by, note})`): mandatory `by`; `state =
  no_show`; feedback rows for it are cancelled (state `expired`, note
  "no-show"); recruiter activity; applicant stays where it is.
- **Done**: an interview whose `stop` has passed cannot be marked `done`
  while feedback is pending, unless `no_show` — the board shows "waiting
  for 2 of 3 opinions".
- **Feedback page** `/hiring/f/<token>`: our portal-theme page (no login):
  the candidate, the role, the round, the criteria with 1–5 dots, the
  recommendation, notes; submit once; `used` shows thanks; `closed` shows
  "this window has closed — tell the recruiter". Submitting marks the row
  and, when every row of the interview is in, posts a summary in the
  interview chatter and an activity for the recruiter. The daily job
  (06:00) sends ONE urgent reminder per late row (`urgent_sent_at`) and an
  activity for the recruiter.
- **Next round / reject** (`act('next_round', {applicant, step?})`,
  `act('reject', {applicant, reason_id, template?})`): next round moves the
  applicant to the next stage (job stages in sequence; or the given step's
  stage) and sends the "next step" mail; reject sets the reason, refuses,
  sends the rejection mail. Both templates editable; `pb_hiring.candidate_mail`
  switch (default 1) gates candidate mails everywhere.
- **Debrief** (final-kind interviews only): `debrief_notes` + `decision`;
  `select` writes `requisition.selected_applicant_id` (add the field) and
  a chatter note; A3's BGV/offer starts from that pointer.
- **`/my/hiring`**: for the session employee — requests I raised (state,
  candidates, next interview), interviews I sit on (next 14 days, with
  "add to calendar" ICS download route), feedback I owe (links). Home card
  "Hiring · N things waiting on you" (eager key).
- **Board**: a top-level **Interviews** tab (today / this week / awaiting
  feedback / late feedback), and inside a requisition's drawer each
  applicant card carries Schedule / Reschedule / No-show / Next round /
  Reject / Debrief with the feedback chips (in / late / pending) and the
  average recommendation. Every door dict carries `views` (R125).
- ⌘K: `hiring_interviews` 3550 ("Interviews this week"),
  `hiring_feedback` 3560 ("Feedback owed", recruiter gate).
- Switches: `pb_hiring.reminders` 1, `pb_hiring.candidate_mail` 1,
  `pb_hiring.feedback_hours` 24, `pb_hiring.urgent_after_hours` 0 (urgent
  at due), `pb_hiring.interview_duration` 45.

## 4. Tests

T1  Unit tests + gates pass; upgrade path `-u pb_hiring` on a DB holding
    A1 data re-lays nothing twice (migration idempotent).
T2  Schedule round 1 for the referral applicant, panel = 17122 + 17140,
    tomorrow 10:00 (server clock), 45 min: interview + event created;
    NO stock calendar mail (assert `mail.mail` count before/after shows
    only ours); 4 of ours (candidate, 2 panel, recruiter) each with a
    `.ics` attachment whose DTSTART matches; `feedback_due_at` = 24
    working hours after the stop on company 5's calendar (assert against
    `plan_hours` directly).
T3  Reminders: set `start` to now+24h and run the job → 24h mails once;
    run again → none; set to now+30m → 30-minute mails once.
T4  Reschedule without reason → refused with a sentence; with reason +
    `external` → old row `rescheduled`, new row scheduled, cancellation +
    new invites sent, a `pb.hiring.reschedule` row; inside 30 minutes →
    the warning chip.
T5  No-show without `by` refused; with `by=candidate` → state, feedback
    rows expired, recruiter activity.
T6  Feedback page for 17140's token: renders without login, 5 criteria;
    submit → row submitted, the second token still open; submit the
    second → chatter summary + activity; the used token shows thanks; a
    12-char junk token shows invalid.
T7  Urgent: a pending row with `due_at` in the past → one urgent mail +
    activity; run again → none.
T8  Done blocked while feedback pending; allowed after; no-show bypasses.
T9  Next round → applicant on the next stage, mail sent, a stage-log row;
    reject → refused with the reason, rejection mail, log row; with
    `candidate_mail=0` no candidate mail but the stage still moves.
T10 Debrief on a final-kind interview → `selected_applicant_id` set;
    refused on a non-final round.
T11 `/my/hiring` as diep.thai (raised the request) and as lam.ngo (panel):
    each sees their own things; a plain employee with nothing sees the
    empty state; the ICS download route answers `text/calendar`.
T12 Board Interviews tab + drawer actions in Chrome light + dark (the kit's
    dark gap is noted, not fixed — A1 report); screenshots
    `RIZE/w2_a2_*.png`; no console errors; `unhandledrejection` listener.
T13 ⌘K 3550/3560 present; feedback rows invisible to a user who is neither
    recruiter nor the panel member (rule test).
T14 Deploy to payobook: version `19.0.1.1.0` landed, migration ran, cron
    rows exist and are active, service up; the real log clean.
T15 Reverts: groups against snapshot, passwords, mails cancelled; test
    data stays named RIZE W2.

## 5. Report back
As A1, plus: the interview/feedback/stage-log API for A3 (fields, `act`
verbs, `selected_applicant_id`, the reschedule and stage logs A3's
analytics read), mail template xmlids, cron xmlids and cadence, switches,
new R-entries, the ledger Wave 2 row for A2, owner items.
