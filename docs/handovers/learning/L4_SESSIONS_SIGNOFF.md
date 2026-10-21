# LEARNING L4 — Sessions and practical sign-off

Programme: LEARNING. Design page `docs/design/rize-learning-blueprint.html` §4 differentiators
(practical sign-off on a phone, toolbox talks), §5 "Courses" (Sessions tab), §7 phase L4.
Ledger `docs/handovers/learning/LEARNING_LEDGER.md` is binding. Predecessors: L0–L3 reports —
take the Learning hub registry, the assignment engine (incl. `extra=` and path links from L3),
the certificate record (L1), hours (L2) and the paths (L3) from the reports.

**Owner decision LD5 (practical sign-off on a phone) is asked when this phase launches.** If
the answer is "not now", skip §3.4 and §4.3 and say so; everything else stands.

Report back to `docs/handovers/learning/L4_REPORT.md`.

## 1. Scope

**Goal.** Training that happens in a room or on site becomes a record like any other: a
session with a date, place, trainer, seats and attendance, counted in hours and compliance;
a toolbox talk logged in a minute; and a supervisor signing off a practical task on a phone.

**In scope.**
1. Models `pb.training.session`, `pb.training.attendance`, `pb.training.checklist`,
   `pb.training.checklist.step`, `pb.training.signoff`, `pb.training.signoff.step` (§3.1).
2. A **classroom course** = a course (`slide.channel`) with `delivery = 'session'`; its
   completion for a person is attendance at a session (optionally + the course's test).
   Enrolment, assignment, reminders, paths, requirements and certificates work unchanged
   because attendance marks the step assignment `done` (§3.2).
3. Session lifecycle: planned → open (invites out) → held → closed; seats and waitlist;
   calendar invite by mail (ICS) + quiet diary entry (§3.3); QR attendance on the trainer's
   screen; manual attendance; hours per attendee.
4. **Toolbox talk**: a session created after the fact in one screen (topic, when, where, who
   was there, minutes) (§3.3).
5. **Practical sign-off** (LD5): checklist templates; the assessor opens the person's
   sign-off on a phone (QR or name), ticks each step pass/fail, adds a photo and a note, and
   presses Pass or Fail; a pass completes the step assignment and files a certificate (§3.4).
6. Surfaces: SESSIONS inner tab on COURSES (calendar + list), session page, toolbox-talk
   drawer, trainer's attendance screen, the assessor's phone page, learner's "My sessions"
   on My learning and the portal, Overview and Numbers (§4).
7. Demo data (§6), tests (§7), deploy (§8).

**Binding non-goals.** No `event` module; no outside catalogue (L5); no video conferencing
links beyond a free-text "join link"; no face matching or biometrics (ruling D13); no
payments; no change to `pb_hiring`'s calendar code (copy the quiet context, do not depend).

## 2. Verified plumbing facts (do not re-derive)

| # | Fact | Where |
|---|---|---|
| F1 | ICS: `build_ics(summary, dt_start, dt_end=None, organizer=None, attendees=None, description='', location='', uid=None)` → bytes with `METHOD:REQUEST` (`pb_lifecycle/models/ics.py:48-88`). Attachment + mail precedent `pb_hiring/models/interview.py:656-711` (`_ics`, `_ics_attachment` → `ir.attachment` `mimetype='text/calendar'`, `_send(..., with_ics=True)` sets `email_values['attachment_ids']=[(6,0,ids)]`). Download route precedent `pb_hiring/controllers/portal.py:182-206`. House pattern (ruling D12, RIZE_LEDGER:209-211): outside calendars OFF; our own mail carries the ICS **and** a quiet `calendar.event` gives the diary entry: `QUIET = dict(dont_notify=True, no_mail_to_attendees=True, mail_create_nolog=True, mail_notrack=True, send_updates=False, …)` (`pb_hiring/models/google_p5.py:47-49`, `_pb_quiet_create` :62-74) — copy the dict into `pb_training`, do not depend on `pb_hiring`. | |
| F2 | Token pages: `pb.feedback.request` pattern (`pb_lifecycle/models/feedback.py:30-110`: `token` Char index copy=False, `secrets.token_urlsafe(24)`, unique constraint, `_request_for_token(token)` → `(rec, status)` with `invalid/used/closed/ok`, `window_end`); routes `auth='public', website=True` (`pb_lifecycle/controllers/token_pages.py:79-144`); hiring feedback page `pb_hiring/controllers/token_pages.py:43-120` (never pass a render key named `request` — R4), public upload with bounded read 5 MB + MIME (:156-200). `/my/training…` routes are `auth='user'` with `_tr_` helper prefixes (`pb_training/controllers/portal.py:78-96`). | |
| F3 | QR: stock route `/report/barcode/<barcode_type>/<path:value>` and `/report/barcode?barcode_type=QR&value=…&width=200&height=200` (`web/controllers/report.py:55-90`, `auth='public'`, PNG, reportlab — no Python package needed). No QR code generation exists in pb_*. The scanner lib `zxing-library` is vendored under `web/static/lib` (reader side, optional). | |
| F4 | Attendance precedent: `pb_driver_checkin` inherits `hr.attendance` (`in_mode gps`, `pb_selfie_attachment_id`; `controllers/driver_app.py:132-195`: `/driver/check_in_out`, `/driver/selfie` with `_IMAGE_MIMES` jpeg/png/webp and 5 MB); phone capture `<input type="file" accept="image/*" capture="user">` (`driver_app.js:384-400`); back camera `capture="environment"` precedent `pb_me_expense/views/portal_templates.xml:138-139`. Ruling D13: location + selfie, never face matching. **Do not write `hr.attendance` for training sessions** (that is pay-side time); training attendance is its own table. | |
| F5 | Uploads: vault `pb_me_portal/controllers/portal.py:380-430` (`_UPLOAD_MIME_OK` png/jpeg/pdf, 10 MB, bounded read); claim `_tr_upload` (`pb_training/controllers/portal.py:409-425`, no size/MIME check — add the vault's guard when cloning); attachment via `claim._attach` (`claim.py:621-635`); tokened download `_tokened_url` (:640-650). | |
| F6 | Checklists: no per-step pass/fail model exists. Template/line/run/result precedent = journeys (`pb.journey.template` / `.step` / `pb.journey.case` / `pb.journey.task` with `state`, `payload_json`, `done_by`, `done_at`, `note`; `pb_lifecycle/models/journey_template.py:15-130`, `journey_task.py:25-73`). Assessor-fills-a-template precedent = hiring scorecard (`pb.hiring.scorecard` / `.part` with kind `yes_no`, results JSON on `pb.hiring.feedback.answers_json`, `parts_for_page()` :308, rendered on the public token page). | |
| F7 | People picker: `pb.training.search_people(term, channel_id=0)` (`pb_training.py:280-320`) with `fold()` accent-blind matching (`training_common.py:351-364`; no `unaccent` in Postgres — R78); `_partner_of(row)` :322. | |
| F8 | Hours: L2 adds `slide.channel.pb_hours`, `assignment.hours`, `document.hours` (if L2 is not live when L4 starts, add `pb_hours` on the course in L4 and note it). Duration helpers `minutes()`/`duration_words()` (`training_common.py:368-392`). | |
| F9 | Mail: `assignment._mail(xmlid, email_to)` (`assignment.py:421-444`) takes no attachments; attachment precedents `interview.py:705-710`, `pb_onboarding/models/journey_ext.py:226-235` (`email_values['attachment_ids']`). | |
| F10 | Nearest "date + place + people + outcome" record = `pb.hiring.interview` (`interview.py:96-221`: `start`, `duration_minutes`, `stop` computed stored, `mode`, `location`, `panel_employee_ids`, `event_id`, `state` scheduled/done/no_show/cancelled/rescheduled; board `hiring_board.js`, `interviewer_page.js`). Clone its shape, not its code. | |
| F11 | Demo cast (company 5): manager `lam.ngo@example.com` (uid 2326, employee 17122) manages 17139–17147 and 17338; `demo.field@example.com` (uid 6533, employee 17140 Ưng Hoàng Long, agronomist); `diep.thai@example.com` (uid 2336) manages department 657; HR lead `demo.hr@example.com`; jobs incl. Safety Officer, Foreman, Line Leader, Machine Operator; course 27 + L3's three DEMO courses. Passwords are NEVER written in this file: Fable passes them in the agent prompt. | |

## 3. Architecture

### 3.1 Models (`pb_training/models/session.py`, `signoff.py`)
- **`slide.channel`** gains `delivery` Selection `online / session / blended` (default online;
  "In a room or on site" / "Online and in a room"), `session_hours` default (Float), and
  `attendance_completes` Boolean (default True: attending a session marks the course done
  for that person; when the course also has a test and `blended`, the test still gates).
- **`pb.training.session`** (`mail.thread`): `name` (computed "Course · date"), `channel_id`
  (required, domain delivery in session/blended), `kind` Selection `classroom / onsite /
  toolbox` ("Classroom", "On site", "Toolbox talk"), `start` (Datetime), `minutes` (Integer),
  `stop` (computed stored), `place` (Char), `join_url` (Char, optional), `trainer_id`
  (`hr.employee`), `trainer_name` (Char for an outside trainer), `seats` (Integer, 0 =
  unlimited), `state` Selection `planned / open / held / closed / cancelled`, `attendance_ids`,
  `waitlist_ids` (M2M employees), `hours` (Float; default `minutes/60`, editable), `notes`
  (Html), `event_id` (`calendar.event`, set null), `qr_token` (Char, unique, minted like F2),
  `company_id`, counts `booked_count`, `attended_count`, `waiting_count`, words `when_words`,
  `where_words`, `seats_words` ("12 of 20 seats"), `state_words`.
- **`pb.training.attendance`**: `session_id`, `employee_id`, `partner_id`, `assignment_id`
  (set null — the step/course assignment this attendance completes), `state` Selection
  `booked / waitlisted / attended / no_show / cancelled`, `checked_in_at`, `how` Selection
  `qr / trainer / self`, `hours` (default session hours), `note`, `company_id`. Constraint:
  one row per person per session.
- **`pb.training.checklist`** (LD5): `name`, `channel_id` (optional: the course it belongs
  to; a sign-off may stand alone), `intro` (Text, shown to the assessor), `step_ids`,
  `pass_rule` Selection `all_steps / min_steps` + `min_pass` (Integer), `photo_required`
  Boolean, `issues_certificate` Boolean, `validity_months`, `active`, `company_id`.
- **`pb.training.checklist.step`**: `checklist_id`, `sequence`, `name`, `help`, `critical`
  Boolean (a fail here fails the whole sign-off).
- **`pb.training.signoff`** (`mail.thread`): `checklist_id`, `employee_id`, `assessor_id`
  (`hr.employee`), `assignment_id` (set null), `token` (Char unique, F2 pattern), `state`
  Selection `open / passed / failed / cancelled`, `started_at`, `finished_at`, `note`,
  `photo_ids` (M2M `ir.attachment`), `step_result_ids`, `result_words`, `company_id`.
- **`pb.training.signoff.step`**: `signoff_id`, `step_id`, `result` Selection `pending /
  pass / fail / na`, `note`.

### 3.2 Completion wiring
- `assignment._progress()` (F in L1 handover F6): for a course with `delivery='session'`
  and `attendance_completes`, `finished` = an `attended` attendance linked to the
  assignment (or any attended attendance on that course after `assigned_on`); `done` lesson
  counts are ignored; `test` as today when the course has one (blended). For a course with
  a checklist marked as the completion (`channel.signoff_checklist_id`, M2o), `finished` =
  a `passed` sign-off linked to the assignment. The state machine, `completed_on`, `score`,
  certificates (L1: a session/sign-off completion files a certificate when the course or
  checklist says so — add `training_source` values `session` and `signoff`), hours (L2) and
  paths (L3) follow without change.
- A booking for a person with no assignment on that course **creates** one (reason `adhoc`,
  due = session date) so every attendee shows in Assigned and Numbers.

### 3.3 Session lifecycle
- `planned`: HR/trainer creates it (drawer). `open`: "Send the invitations": mail
  `session_invite` to every booked person (and the trainer), ICS attached (F1, uid
  `pbtraining-session-<id>@payobook`), plus a quiet `calendar.event` with the attendees
  (copy `QUIET`); reminder mail `session_reminder` the day before (daily job leg
  `_session_reminders`). Booking after `open` sends the invite at once. `held`: the trainer
  presses "Start the session" → the **attendance screen** (§4.2) shows the QR; people scan
  it on their phone (`/my/training/attend/<qr_token>`, `auth='user'`, marks `attended`,
  `how='qr'`; refuses when not booked and no seats — offers "Ask to join" which books them
  if seats remain); the trainer ticks the rest manually. `closed`: "Close the session" marks
  booked-but-absent as `no_show`, writes hours, runs `_refresh` on the linked assignments,
  files certificates; the session becomes read-only (manager may reopen).
- Seats and waitlist: booking beyond `seats` → `waitlisted`; a cancellation promotes the
  first waitlisted person (mail `session_seat_free`). Bulk booking by department / job /
  everyone-on-the-course (people picker F7, same as Assign a course).
- Cancelling a session mails `session_cancelled` with an ICS `METHOD:CANCEL` (extend
  `build_ics` with a `method` kwarg — small, in pb_lifecycle; or build the CANCEL inline as
  the onboarding precedent does; prefer the kwarg + one test).
- **Toolbox talk**: one drawer: course (or "new toolbox course" created on the spot with
  `delivery='session'`, 0.25 h), when (default now), where, minutes (default 15), who was
  there (picker, multi), optional photo of the sign-in sheet → creates a `closed` session with
  `attended` rows in one go. Supervisors (any employee who manages people) may log one for
  their own reports; trainers/managers for anyone.

### 3.4 Practical sign-off (LD5)
- Creating: from a course (checklist attached) the assignment carries a "Sign-off pending"
  chip; the assessor's page lists their open sign-offs. From the Assigned lens: "Start a
  sign-off" picks the checklist and the assessor (default the person's manager).
- Assessor page `/my/training/signoff/<token>` (`auth='user'`; the user must be the assessor,
  the person's manager, or hold a training group): the person's name and photo, the intro,
  one card per step with two big buttons Pass / Fail (and "Not applicable" small), a note
  field, photo capture (`capture="environment"`, bounded read, jpeg/png/webp, 5 MB, up to 5
  photos), then one primary button "Pass" (enabled when the pass rule is met and no critical
  step failed) or "Fail". Autosave per step (RPC per tap, offline-tolerant: the page keeps
  unsent taps in memory and retries). Pass → `state=passed`, assignment refresh, certificate
  (L1 source `signoff`, validity from the checklist), mail `signoff_passed` to the person
  and manager. Fail → `failed`, a new sign-off can be started, the assignment stays open.
- QR hand-off: the learner's My learning shows "Show my code" (QR of `/my/training/signoff/
  start/<employee_token>`); the assessor scans it → the page opens with that person
  pre-selected (checklist picker if several). Employee token = `hr.employee.pb_training_token`
  minted on demand (F2 pattern).

### 3.5 Daily job
Leg `_session_reminders(today)` (day-before mails, cap shared) and `_sessions_autoclose`
(a `held` session 24 h past `stop` is closed automatically with a chatter note).

## 4. Surfaces

### 4.1 SESSIONS on the Courses lens (inner tab; plus a "Sessions" tab on each course page)
- Facade `pb.training.sessions_board(filters)` → `{allowed, upcoming:[...], past:[...],
  kpis:{this_week, seats_free, waiting, no_shows_30d}, calendar:[{date, count}]}`; session
  cards: course, kind chip, when/where words, trainer, "12 of 20 seats · 3 waiting", state
  chip; quiet colours (amber = seats full with waitlist, rose = cancelled).
- **Hero moment:** the week strip at the top: seven columns, a dot per session, today
  ringed; click a day to filter. Buttons "New session", "Log a toolbox talk".
- Session page: header (course, when, where, trainer, seats words, state), roster table
  (name, department, state chip, checked-in time, hours, note) with per-row actions Mark
  attended / No show / Remove; "Book people" drawer; "Send the invitations", "Start the
  session", "Close the session", "Cancel"; download the attendance sheet (xlsx, data-URL
  pattern) and a PDF sign-in sheet with the QR printed (report on `pb.training.session`).

### 4.2 Attendance screen (trainer)
Full-screen quiet page from "Start the session": big QR (stock `/report/barcode` PNG at
400 px), the course and time, a live count "14 of 20 here" (polls every 10 s), a roster
list that ticks itself as people scan, manual tick per row, "Everyone is here" button, and
"Close the session". Works on a laptop or a tablet; phone shows the QR only with the count.

### 4.3 Assessor phone page (LD5) — see §3.4. Design bar: one thumb, big targets, no scrolling
inside the step card, every state says what happens next ("2 steps left · 1 failed, this
sign-off cannot pass").

### 4.4 Learner: My learning and portal
"My sessions" block: next session card (when, where, "Add to my calendar" = the ICS download
route, "Show my code" when a sign-off is pending), list of booked/waitlisted sessions; the
portal `/my/training` gets the same block; course page shows "Book a seat" for open sessions
on that course (self-booking allowed when the course says so: `self_booking` Boolean).

### 4.5 Overview and Numbers
Overview: "This week: 3 sessions · 41 seats booked · 2 sign-offs waiting on assessors";
queue rows "Sessions to close" and "Sign-offs waiting". Numbers: hours by session kind,
attendance rate, no-show rate, by trainer, by course; spreadsheet sheets "Sessions" and
"Sign-offs"; the statutory exports (L2) read session hours too.

## 5. Safety rails
1. Ledger L1–L8; EN + VI; Lucide only; quiet board; every token page checks who may see it.
2. Never write `hr.attendance` from training (pay-side time). Never store faces (D13).
3. Attendance and sign-off writes are idempotent (one row per person per session; one open
   sign-off per person per checklist).
4. ICS mails go only to booked people; the quiet diary entry never mails anyone.
5. Commits: (a) models + completion wiring + migration; (b) sessions board, session page,
   attendance screen, toolbox talk, mails/ICS/diary; (c) sign-off models + assessor page +
   QR hand-off; (d) learner blocks + Overview/Numbers + exports; (e) demo + docs.

## 6. Demo data (payobook, "DEMO …", registered)
Course "DEMO Site safety walk" (`delivery='session'`, 2 h) with two sessions: one next week
(open, 20 seats, 14 booked, 2 waitlisted) and one last week (closed, 9 attended, 1 no-show).
One toolbox talk "DEMO Lifting safely" logged yesterday by `lam.ngo` for his reports.
Checklist "DEMO Forklift pre-start check" (6 steps, 2 critical, photo required, certificate
12 months) with one open sign-off (assessor `lam.ngo`, person 17140) and one passed.

## 7. Numbered tests (`tests/test_sessions.py`, `tests/test_signoff.py`)
- **T1** session shape, stop computed, seats words, one attendance per person.
- **T2** booking: seats → waitlist; cancel promotes; bulk by department (child_of).
- **T3** open: invite mails with ICS attachment (`text/calendar`, `METHOD:REQUEST`) only to booked; quiet `calendar.event` created with the QUIET context (assert no mail from calendar).
- **T4** QR attendance route: booked → attended/qr; unknown token → invalid page; not booked with seats → "Ask to join" books; no seats → refused in plain words.
- **T5** close: no-shows, hours written, assignment done, certificate filed with `training_source='session'`; reopen allowed for managers only.
- **T6** completion wiring: `_progress` for session/blended courses; a booking creates the assignment; a path step opens the next step on close (L3).
- **T7** toolbox talk: one call creates course (if new), closed session, attended rows; a supervisor can only include their reports.
- **T8** reminders leg day-before; autoclose after 24 h; caps.
- **T9** cancel: ICS CANCEL mail; diary entry archived; attendances cancelled.
- **T10** (LD5) checklist pass rules incl. critical fail; autosave per step; photo required; pass → assignment done + certificate `signoff`; fail → stays open; assessor rights (assessor / manager / trainer only).
- **T11** (LD5) QR hand-off token: mints once, opens the right person, a stranger is refused.
- **T12** learner block shape; self-booking honours the switch.
- **T13** Overview/Numbers add up; spreadsheet sheets; PDF sign-in sheet renders with the QR.
- **T14** no "Odoo", no emoji; VI words fit.
- **T15** Chrome walk (local then live): week strip, new session drawer, book people, invitations, attendance screen QR + manual ticks + live count, close, toolbox talk, assessor page on a phone-sized window (pass path and fail path, photo), learner "My sessions" + Show my code, portal block, console clean.

## 8. Deploy
`pb_training` → next minor; new tables and a migration (`delivery` default on existing
courses) → **risky tier** (backups, p0clone first); `pb_lifecycle` touched only if the ICS
`method` kwarg is added (then `-u pb_lifecycle` too). Usual ritual; stop at the deploy gate.
