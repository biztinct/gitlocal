# LEARNING L4 — Sessions, attendance and toolbox talks — report

Implementer: Opus, 2026-10-22. Spec: `L4_SESSIONS_SIGNOFF.md` minus the LD5 cuts (no practical sign-off). Ledger: `LEARNING_LEDGER.md` (candidate rows from LN45 in §5).
Status: **DEPLOYED ×4 DBs 2026-10-22 16:22 AEDT (DONE 05:22 UTC)** — live walk pending (Fable, LN16). Not pushed.

## 1. What shipped (committed on 19.1, not pushed)

| Module | Live now | After L4 |
|---|---|---|
| pb_training | 19.0.1.7.0 | **19.0.1.8.0** — two new tables (`pb_training_session`, `pb_training_attendance`), new columns on the course (`delivery` default "online", session hours, five switches), the assignment (`session_id`) and the certificate record (`attendance_id`); one new dependency, **`calendar`** (installed on all four live databases, checked read-only). No migration, nothing existing rewritten. |
| pb_training_growth | 19.0.1.0.0 | unchanged (reloads with `-u pb_training`, as in L3) |
| pb_lifecycle, every other module | — | **unchanged** (the calendar file's CANCEL variant is built inside pb_training, so only one module upgrades) |

### What a user sees
- **Learning › Courses › Sessions** (a second inner tab next to Courses; the rail is unchanged, ten items).
  - **Hero: the week strip** — seven days from today, a dot per session, today ringed; press a day to see that day only.
    One sentence over it ("1 session coming up · 14 seats booked · 1 to close") and the buttons **Log a toolbox talk** and
    **New session**. Quiet numbers under it: sessions in the next 7 days · seats still free · waiting for a seat (amber) ·
    did not come, last 30 days (rose) · ended, still to close (amber, press to filter).
  - **Session cards** (Coming up / The last 30 days): course, kind chip (Classroom · On site · Toolbox talk), when, where,
    trainer, "14 of 14 seats · 2 waiting" (amber edge when full with people waiting or ended and not closed, rose when
    cancelled), state chip.
  - **Session page:** header and a "what happens next" line for each state; **Book people** (people — accent-blind, people
    without a login included and marked —, a department with everything under it, a job, or everybody who still owes the
    course); **Send the invitations**; **Start the session** / Show the code; **Close the session**; **Open it again**
    (training managers); **Edit**; **Attendance spreadsheet**; **Sign-in sheet** (PDF, one document, QR printed);
    **Cancel the session**. A roster row per person with Mark attended / Did not come / take off.
  - **Attendance screen** (full screen): the big QR code, the course and time, "14 of 20 here" with a bar (asks every 10
    seconds), the roster ticking itself as people scan, a tick per row, **Everyone is here**, **Close the session**. On a
    phone only the code and the count show.
  - **New session drawer:** a classroom course (or a new one named on the spot), kind, start, minutes, seats (0 = as many
    as come), where, trainer (one of your people, or an outside trainer's name), join link, hours.
  - **Toolbox talk drawer:** topic (a classroom course or a new topic), when (now), minutes (15), where, who was there
    (search, tick, "Tick all shown"), photo of the paper sign-in sheet (back camera on a phone), notes → a closed session
    with everybody attended in one press.
- **Course drawer** (Courses tab): for a course taught in a room, a Sessions section; a row opens that session on the
  Sessions tab. **Course form:** "How it is taught" (Online / In a room or on site / Online and in a room), "A session
  usually lasts", "Attending finishes the course", "People may book a seat themselves", "Attending files a certificate"
  and its validity.
- **Overview:** a seventh queue chip **Sessions to close** (opens Sessions filtered) and a Sessions block (this week ·
  seats booked · waiting · to close).
- **Numbers:** a Sessions section (closed sessions in the range: hours, attended %, did-not-come %, by kind, by trainer,
  by course) and a **Sessions** sheet in the spreadsheet. The country reports read the hours through the finished course.
- **My learning:** **My sessions** (the next one in a tint with Add to my calendar / Join link, the rest, and "Sessions you
  can book yourself" with **Book a seat**); a classroom course card says "Booked · Wed 28 Oct …" instead of "0 of 0
  lessons"; a manager's team block has **Log a toolbox talk** (only for the people under them).
- **Portal `/my/training`:** the same My sessions block, the course card line, a Sessions section on the course page
  (with Book a seat), the **scan page** `/my/training/attend/<code>` ("You are marked as here", "You are not booked on this
  session — Ask to join", "This session is full", "closed", "not started yet", "not a session") and
  `/my/training/sessions/<id>/calendar.ics`.
- **Mails** (English, ledger LD10): you are booked (with the calendar file), it is tomorrow, a seat came free (with the
  file), cancelled (with a cancelling calendar file), and the trainer's copy. The diary entry in the calendar never mails
  anybody.
- **Morning job:** two legs — the day-before reminder (under the shared send cap and the reminders switch) and closing a
  session left "under way" a whole day after it ended.
- **LD11 (Vietnam group 4):** in a company whose country is Vietnam an employee with no safety group counts as group 4 in
  rule audiences (the yearly refresher included), the matrix ("Group 4 — Other workers (by default)"), the renewals report
  and the People chip ("Safety group 4 (by default)"); a set group always wins; outside Vietnam nothing changes. The
  Vietnam pack card in Settings says "Anyone with no safety group set counts as group 4. Set another group on the
  person's record."
- **Coordinator's extra:** the Numbers screen starts with `byPath: []`, `lists.paths: []` and every loop reads
  `(state.x || [])`, so a render during an interrupted read can no longer throw "undefined is not iterable".

## 2. Tests

Local runtime `/Users/adity/odoo19`, overlay `scratchpad/l4stage/{pb_training,pb_training_growth}` in front of the L0
staging tree. Test databases are copies of `am_l3_t2` (L3's walked DB, pb_training 19.0.1.7.0) plus its filestore
(LN30), run exactly as the live upgrade: `-u pb_training`.

| # | Result |
|---|---|
| T1 | **Pass** (4): stop computed, QR drawn, attend URL, seats words ("2 of 20 seats", "1 booked"), minutes/hours from the course; one row per person (second booking → "already", database refuses a duplicate); an online course cannot have a session; existing courses read "online". |
| T2 | **Pass** (3): seats → waiting list; taking a booked person off books the first person waiting; bulk by department reaches the sub-department; a plain user gets AccessError and `allowed: false`. |
| T3 | **Pass** (3): invitation only to the booked person, `text/calendar`, `METHOD:REQUEST`, stable UID; nobody waiting is mailed; the diary entry holds the booked person only and **no mail and no notification** came from the calendar; a second press sends nothing; booking after the invitations sends at once; a booking sends none of the course's own mails. |
| T4 | **Pass** (4): booked → attended by QR; unknown / too short code → invalid; a future session → not yet; cancelled → closed; not booked with seats → "ask", then joins and is attended; full → refused, nothing written; route and words checked. |
| T5 | **Pass** (2): close → did-not-come, 2 hours on the attendance and on the finished course, certificate filed with source "Attended a session", hours and a valid-until date, one record id per PDF render; a closed session refuses a trainer's tick; reopening is for training managers only. |
| T6 | **Pass** (3): a booking makes the course (One-off, due the session day, linked) — somebody already on the course keeps theirs; finished = attended for a classroom course, lessons still count for "online and in a room", nothing when the switch is off; a learning path whose first step is a classroom course opens the next step when the session closes. |
| T7 | **Pass** (3): one call makes the course, a closed toolbox session (15 min = 0.25 h), attended rows (a person with no login too — no course for them), the photo; a supervisor sees and may include only the people under them (AccessError otherwise), somebody managing nobody gets `allowed: false`, the person who logged it is not put on the new course; a bad file is refused. |
| T8 | **Pass** (3): day-before reminder once, not two days before; the send cap is shared; a session under way 3 days after it ended closes by itself (no-show written, note in its history), a fresh one does not. |
| T9 | **Pass**: cancel tells the 2 invited people with `METHOD:CANCEL` / `STATUS:CANCELLED`, archives the diary entry, cancels every booking, removes the course put on them only for this session; a second cancel is refused. |
| T10, T11 | **Skipped per LD5** (practical sign-off not in this phase). |
| T12 | **Pass** (2): My sessions shape (next, calendar link, words), calendar file for a booked person and not for a stranger, the course card says booked; self-booking off → nothing offered and refused; on → offered, booked; somebody not owing the course is refused. |
| T13 | **Pass** (3): Overview block and chip (count, lens, tab); the board's "to close" filter and week strip; Numbers add up (2 attended + 1 did not come = 3; 67% / 33%; 2 hours); spreadsheet has "Sessions"; attendance spreadsheet builds; the sign-in sheet's HTML has one `article`, the QR and the names; the PDF render gets one id. |
| T14 | **Pass** (3): no vendor word and no emoji in the ten new files; Vietnamese present; state words differ in Vietnamese. |
| LD11 | **Pass** (2): group-4 rule covers the empty and the group-4 person, not group 3; a group-3 rule does not pick up the empty one; matrix facts say "4, by default"; outside Vietnam the empty group stays empty; the Vietnam pack card says so. |
| Suites | `/pb_training,/pb_training_growth,/pb_learning_hub` on a fresh copy with `-u pb_training`: **369 tests, 2 failed, 0 errors** (§9). The only failures are `TestTheAssignmentsTab` ×2 (pre-existing in L0–L3 reports). One L0 rail test was updated: Courses now owns two inner tabs. |
| PO gate | pb_training 1,486 rows, 0 code rows without a value. |
| T15 | Local Chrome walk, `localhost:8072` / `am_l4_walk` (seeded with `l4_demo_seed.py`, company 1). Detail below. |

T15 detail (local):
- **Head of training (admin), EN:** Overview — chip "0 Sessions to close", Sessions block "1 session this week · 14 seats
  booked · 2 waiting for a seat · 0 sessions to close" → **Open the sessions** lands on Courses › Sessions. Week strip THU
  22 (today, ringed) … WED 28 with one dot; numbers line; three cards (next week's "14 of 14 seats · 2 waiting" with the
  amber edge, the toolbox talk "3 attended", last week's "9 attended · 1 did not come"). Pressing WED 28 filters to it.
  Screenshot `outputs/learning-l4-20261022/local-session-page.jpg`.
- **Session page:** 16 rows; taking one booked person off → "DEMO Đỗ Văn Nam is off this session." and the first person
  waiting moved up ("14 of 14 seats · 1 waiting").
- **Attendance screen:** QR code, "0 of 14 here"; a tick by hand → "1 of 14 here"; scanning the code (the scan page opened
  as a booked user) → "Bạn đã được ghi có mặt" with course, time, place; an invented code → "Mã này không phải của buổi học
  nào". `local-attendance-screen.jpg`, `local-scan-page-vi.jpg`.
- **New session drawer:** hint "Pick the course this session is for." with Save disabled; picked the course, a place, a
  trainer by typing "binh" → "One of your people." → "… is planned. Book people on it, then send the invitations."
  `local-new-session-drawer.jpg`. **Book people:** ticked three (one with no login, marked) → "3 people are booked." **Send
  the invitations** → "2 invitations sent, each with a calendar file." (the no-login person has no address); the queued
  mails carry `text/calendar` (cancelled afterwards — local DB).
- **Start → Everyone is here → Close** from the screen: "0 of 3 here" → "3 of 3 here" → "Closed. 3 attended and their
  course is marked finished; 0 did not come."
- **Toolbox talk drawer** (EN): new topic, search "nguyen", Tick all shown → "Toolbox talk logged: DEMO Ladders and steps, 1
  person." (wording fixed in the walk). `local-toolbox-drawer.jpg`.
- **Course drawer** → Sessions section with three rows → a row opens that session on the Sessions tab.
- **Numbers:** "3 closed sessions · 19 hours of training · 93% attended · 7% did not come", by kind / trainer / course.
  `local-numbers-sessions.jpg`.
- **Manager (manager.p3c, VI), My learning:** rail CỦA TÔI; "Buổi học của tôi — SẮP TỚI DEMO Site safety walk … Đã đặt chỗ ·
  Thêm vào lịch của tôi"; course card "Đã đặt chỗ · Th 4 28 thg 10 2026 · 13:00–15:00"; **Ghi buổi nói chuyện an toàn** in
  the team block opens the drawer listing only his four people with "Bạn có thể đánh dấu những người dưới quyền."
  `local-toolbox-team-vi.jpg`.
- **Plain employee (nam.p3c, VI), portal `/my/training`:** "Buổi học của tôi" with the closed session "Có mặt" and the
  course card line. `local-portal-my-sessions-vi.jpg`.
- **Found and fixed in the walk:** (1) the QR picture was broken — the stock `/report/barcode` route answers 500 locally
  **and on the live box** (reportlab has no `rlPyCairo` backend; checked with a read-only GET on the server) — the code is
  now drawn with the `qrcode` library (present locally and live, 10.2.0) as an inline PNG, also printed on the PDF sheet;
  (2) a planned session had no Start button; (3) mail subjects came out half Vietnamese — session mails now render in
  English end to end (LD10); (4) a course made on the spot (toolbox topic / new classroom course) landed on its creator's
  own page because the content engine enrols a course's responsible — that membership is taken off again; (5) "1 people";
  (6) the scan page's "My training" stayed English — translation occurrences for the new pages added.
- Console: no errors on any page walked. **Not walked:** phone width (the agent's window cannot be resized; CSS written:
  week strip narrows, drawers one column, the attendance screen shows only the code and the count), the PDFs (no PDF
  engine on this Mac — the sign-in sheet and the attendance certificate are first produced live), a real phone camera scan.

## 3. Deviations from the handover, and why

1. **QR (F3 was wrong):** the stock barcode route fails on the live box; the code is drawn in pb_training with `qrcode`
   as an inline PNG (no extra request, works in the PDF).
2. **No sign-off (LD5):** §3.4, §4.3, the checklist/sign-off models and T10–T11 are not built. The `signoff` source is
   reserved in a comment only; nothing offers it.
3. **CANCEL calendar file built in pb_training** (`build_session_ics(..., method=)`) rather than a kwarg on
   `pb_lifecycle.build_ics`, so only one module upgrades (normal tier). Same RFC shape, stable UID per session, SEQUENCE.
4. **The waiting list is attendance rows** (state "Waiting for a seat", first come first served by row), not a separate
   many-to-many; `waitlist_ids` is a read-only view of them. One source of truth.
5. **Demo next-week session has 14 seats, not 20:** "20 seats, 14 booked, 2 waiting" cannot happen — people wait only when
   the seats are full.
6. **People with no login can be booked and logged at toolbox talks** (attendance and hours on their record, a certificate
   if the course files one); they get no course on a training page (an assignment needs a login).
7. **Session courses are listed only when taught in a room:** the New session drawer lists courses set to "In a room or
   on site" / "Online and in a room", or names a new classroom course; an online course is refused by name.
8. **A course put on somebody only for a session goes away** when that booking is cancelled (or the session is), if they
   never started it — the L3 "never take away started work" rule.
9. **Attendance certificate:** a small "Certificate of attendance" PDF (one record, one document) filed in the vault with
   source "Attended a session", when the course says attending files one.
10. **Scan window:** a scan counts while the session is under way, or from an hour before to an hour after if the trainer
    never pressed Start.
11. **Course made on the spot:** its creator stays the responsible but is taken off its member list (walk finding 4).
12. **Overview headline** does not gain a sessions sentence; the chip and the block carry it (the headline is already long).

## 4. Vietnamese

`pb_training/i18n/vi_VN.po`: **290 new entries** (tab, board, page, drawers, attendance screen, scan page, portal blocks,
server sentences, selection labels and field labels, LD11 words, the weekday abbreviations T2…CN said through `tr()`),
and 35 existing entries gained a marker or an occurrence (the state words now said from `session.py`, and the view
occurrences the new pages need); text-level merge, pure additions (LN29). "Session" = **buổi học**, toolbox talk = **nói
chuyện an toàn đầu ca**. Mail bodies stay English (LD10). Auto-generated technical field labels ("Booked Count" …) are not
translated (they are not on any screen).

## 5. Ledger rows to add after the deploy (candidates, from LN45)

- LN45: **The stock `/report/barcode` route answers 500 on the live box and locally** — reportlab has no `rlPyCairo`
  backend. Draw QR codes with the `qrcode` library (10.2.0, present on both) as an inline `data:image/png` — it also
  prints in a PDF with no second request.
- LN46: **`website_slides` enrols a course's responsible as a member on create** (and on a `user_id` write), so a course
  created from a facade lands on the caller's own training page. Take it off with `channel._remove_membership(...)`
  (it archives the row). Publishing needs the caller to be the responsible or a slides manager — `user_id=False` with
  `is_published=True` raises even under sudo (`can_publish` reads `env.user`).
- LN47: A mail template with no `lang` renders computed words in the sender's context language — a Vietnamese date inside
  an English body. Send `template.with_context(lang='en_US')` while mail bodies are English (LD10).
- LN48: A `.po` entry for a view text translates only the views it names in `#: model_terms:ir.ui.view,arch_db:...`; a NEW
  view reusing an existing msgid ("My training") stays English until its occurrence is added. After an export, add the
  new views' occurrences to existing entries, not just new msgids.
- LN49: The portal palette (⌘K) carries `focus` but no `context`; a lens reading an arrival from the palette reads
  `ctx.pb_focus` (Courses → Sessions).

## 6. Score against the design bar

1. **Hero moments:** the week strip (seven days, dots, today ringed, press a day); the attendance screen (big code, live
   count, the roster ticking itself); the learner's "Next" session card with Add to my calendar.
2. **Zero dead ends:** every state of a session says what happens next; every scan answer says what to do; every drawer
   says what is missing before Save; empty board explains what a session and a toolbox talk are, with both buttons.
3. **Plain language EN + VI:** walked in both.
4. **Motion:** rise-in, drawer slide, count bar; off under reduced motion.
5. **Weakest:** phone width and a real camera scan not walked; PDFs only produced live.

## 7. Owner items (plain English)

1. **Vietnam group 4 is on (LD11).** In a Vietnamese company everybody without a safety group now counts as group 4, so on
   payobook the yearly group-4 rule covers far more people than before and the matrix will show more "missing" cells for
   it. HR changes a person's group on their record or many at once with "Set safety group".
2. **Session mails are English** for everybody, like the other training mails, until the mail texts are translated.
3. **A course made for a toolbox talk** has no lessons; it appears on the people's training page as "taught in a room".
   Say if toolbox topics should be hidden from the learner's course list.
4. **People without a login** can be booked and ticked; their attendance and hours count on their record, but nothing
   shows on a training page for them and no email goes to them.
5. **A course taught in a room with no session yet** shows on the learner's page as "the training team books you on a
   session". If a session is never booked, its due date still passes and the usual reminders run.

## 8. Deploy plan (as at the gate) — normal tier

**Why normal:** one module (`-u pb_training`), no new module, no migration, nothing existing rewritten; two new tables
and new columns with defaults. One new dependency (`calendar`), installed everywhere already. I still recommend the
backups (cheap; new tables). The coordinator's HOLD note (22:15 UTC) is cleared only by a DONE line containing
**"LEARNING L4 DONE"**.

**Live facts (read-only, 2026-10-22 ~05:10 AEDT):** pb_training 19.0.1.7.0 and calendar installed on p0clone, payobook,
payobook_template, rize; active jobs p0clone 26, payobook 37, payobook_template 0, rize 69; last lines of
`/opt/deploy-notes.md`: my HOLD note, then ChatGPT's two static payroll releases, both DONE (22:19, 22:24 UTC) — no open
START. Payobook demo facts: company 5; `lam.ngo@example.com` employee 17122 manages 29 people; `demo.hr@example.com`
employee 21182; 18 people in company 5 with an `@example.com` login; no "DEMO Site safety walk" / "DEMO Lifting safely"
course yet.

1. Read `/opt/deploy-notes.md` — no open START; check the HTTP server PID is up (ChatGPT restarts back to back). Lock with a
   detached unit (LN25): `sudo systemd-run --collect --unit=l4-lock /usr/bin/flock /tmp/payobook-studio-deploy.lock
   /bin/sleep 10800`. START line `… | Claude (LEARNING L4) | START | pb_training | p0clone,payobook,payobook_template,rize
   | ~8 min, service stopped during -u | sessions, attendance, toolbox talks, LD11`. Announce to peer sessions.
2. Versions before = pb_training 19.0.1.7.0 ×4 (nobody shipped L4 — the HOLD stands; LN15).
3. Backups (LN25): `sudo sh -c "sudo -u postgres pg_dump -Fc <db> > /odoo/backups/learning-l4-20261022/<db>.dump"` ×4, each
   checked with `pg_restore -l`.
4. Stage: `sudo rm -rf /tmp/deployL4 && mkdir -p /tmp/deployL4`; `git archive <L4 head> pb_training` (HEAD has only
   other people's payroll commits above; they do not touch pb_training — confirm with `git log <L4 head>..HEAD --
   pb_training` empty) → upload; scoped `sudo rsync -a --delete /tmp/deployL4/pb_training/ /odoo/odoo-server/addons/pb_training/`
   (never the addons root); tree hash = local (skip `__pycache__`, `*.pyc`, `.DS_Store`); PO gate on the box (expect 1,486 / 0);
   one addons path.
5. Snapshot active job ids per DB (expect 26 / 37 / 0 / 69).
6. Stop the service (wait on the PID, LN35). Detached unit + sentinel, one DB at a time, **p0clone first**:
   `odoo-bin -c /etc/odoo-server.conf -d <db> -u pb_training --stop-after-init`; grep EXIT, Traceback, ERROR; then payobook,
   payobook_template, rize. Stop at the first failure and restore that DB from its dump.
7. Asset ritual per DB (signal, delete `/web/assets/%` attachments, bump `web.assets.version`); start; registry loaded; warm
   payobook / rize / p0clone with one curl each; jobs back to the snapshot (payobook_template 72/73 off again if `-u`
   re-activated them, LN18).
8. Verify per DB: pb_training 19.0.1.8.0 installed; tables `pb_training_session`, `pb_training_attendance` (0 rows except
   payobook after the seed); columns `slide_channel.delivery` (every existing course "online"), `pb_training_assignment.
   session_id`, `pb_employee_document.attendance_id`; the five session mail templates exist; a QR draws
   (`env['pb.training.session'].new({...})._qr_src()` in a shell, rolled back, starts `data:image/png`); 0 ERROR lines since
   start; `/web/health` 200.
9. Demo data, **payobook only**, service stopped:
   `sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf -d payobook --no-http < docs/handovers/learning/l4_demo_seed.py`
   (course DEMO Site safety walk; next week 14 booked + 2 waiting, marked invitations sent without sending; last week 9
   attended / 1 did not come, closed — 9 attendance certificates rendered by the live PDF engine; toolbox talk DEMO Lifting
   safely yesterday by lam.ngo for up to 8 of his people; morning legs run once and rolled back; anything queued
   cancelled). Restart, warm.
10. DONE line containing **"LEARNING L4 DONE"** (clears the HOLD), release the lock (`systemctl stop l4-lock`).

**Live walk (Fable, ledger LN16), payobook.com:** as the HR lead — Overview "Sessions to close" chip and Sessions block;
Courses › Sessions week strip, day filter, numbers, cards; next week's session page (16 people, 2 waiting), take one off →
the first waiting moves up; Book people; Send the invitations (only if happy to mail a demo address — otherwise skip);
**Start the session → the QR code shows** (first time on the live engine), a tick by hand, the live count; **Sign-in sheet
PDF** (first live render) and the attendance spreadsheet; last week's session (closed) and one attendee's certificate in
Certificates (source "Attended a session"); Log a toolbox talk; Numbers Sessions section + spreadsheet sheet; the course
form's "How it is taught". As `lam.ngo@example.com` — My learning "Log a toolbox talk" lists only his people. As
`demo.field@example.com` — My learning / portal "My sessions", and the scan page by opening the session's code link while
it is under way. Settings › HR › Required training — the Vietnam card's group-4 line. Vietnamese labels. Console clean.

## 9. Final local state (before the gate)

- Commits on 19.1 (not pushed): `029e4c178` (WIP — models, facade, screens, portal, mails, reports, LD11, tests),
  `820873634` (WIP — Vietnamese, demo seed, test fixes), `2d5040acb` (walk fixes + screenshots), and the closing docs commit
  with this report. The WIP commits are kept as they are (the coordinator asked for them as safety points).
- **Final suites on the committed code** (fresh copy of `am_l3_t2` + filestore, `-u pb_training --test-tags
  /pb_training,/pb_training_growth,/pb_learning_hub`): **369 tests, 2 failed, 0 errors** — only `TestTheAssignmentsTab` ×2
  (pre-existing). The `ir_attachment` foreign-key line in the log is pre-existing (L2/L3 logs).
- Tree under test = repo tree (`diff -rq` of the overlay against the repo: identical).
- Walk server stopped; walk DB `am_l4_walk` kept.

## 10. Deploy record (GO DEPLOY 2026-10-22 05:15 UTC)

| Step | Result |
|---|---|
| Notes / lock | no open START (last: ChatGPT DONE 22:24 UTC 10-21 and my HOLD note); lock free; server process up, health 200. Lock held by detached unit `l4-lock` from 05:16 to the DONE line; START 05:16, DONE 05:22 UTC — the DONE line carries **"LEARNING L4 DONE"** (HOLD cleared); lock released |
| Versions before | pb_training 19.0.1.7.0 ×4 (nobody had shipped L4) |
| Backups | `/odoo/backups/learning-l4-20261022/` p0clone 24 MB, payobook 74 MB, payobook_template 24 MB, rize 32 MB (each `pg_restore -l` ok) |
| Files | `git archive 2d5040acb pb_training` (nothing after it touches pb_training) = the tested tree; clean `/tmp/deployL4`, scoped `rsync --delete` into `/odoo/odoo-server/addons/pb_training/`; tree hash equal both sides (183e24ff…); PO gate on the box 1,486 / 0; one addons path |
| Upgrade | service stopped 05:17:59 (gone by PID 05:18:09); detached unit `l4-upgrade`, `-u pb_training`, p0clone → payobook → payobook_template → rize: **EXIT=0 ×4** (≈20 s each), 0 tracebacks, 0 ERROR, 0 CRITICAL |
| Assets / start | signal + `/web/assets/%` deleted + `web.assets.version=learning-l4-20261022` ×4; started, health 200 at 05:20:09 (down ≈2 min) |
| Warm | payobook.com 200, rize.payobook.com 200, p0clone.payobook.com 200 (after the start and again after the seed) |
| Crons | 26 / 37 / 0 / 69 = snapshot; payobook_template 72/73 re-activated by `-u`, switched back off (LN18) |
| After | pb_training 19.0.1.8.0 **installed** ×4; tables `pb_training_session` / `pb_training_attendance` ×4 (0 rows except payobook); `assignment.session_id`, `employee_document.attendance_id`, `slide_channel.self_booking` ×4; every existing course "online" (payobook 5); five session mail templates ×4; `calendar` dependency recorded; a QR code draws on the live engine (`data:image/png`, 1,106 chars, shell rolled back); 0 ERROR lines since the start |
| Demo seed (payobook) | one stop 05:21:08–05:21:40 UTC. Course 290 **DEMO Site safety walk**; session **1** next week (Hall A, 14 seats): 14 booked + 2 waiting, invitations marked sent (none sent), diary entry 725 made quietly; session **2** last week: 9 attended, 1 did not come, closed — **9 attendance certificates filed** (the live PDF engine rendered them); session **3** toolbox talk **DEMO Lifting safely** yesterday, logged as lam.ngo for 8 of his people. 5 records on the demo register. Morning legs rolled back (0 / 0). 0 mail queued by the seed, 0 calendar mails, 0 ERROR lines. |
| Live walk | pending (Fable, LN16) |

### Live walk — what needs which login (for server-side facade calls)

The admin tab (head of training) covers: Overview chip/block; Courses › Sessions (week strip, day filter, numbers, cards);
session 1's page (take one person off → the first waiting moves up; Book people; Start the session → **QR shows**; a tick
by hand; live count); **Sign-in sheet PDF** `/report/pdf/pb_training.report_session_sheet/1` (first live render) and the
attendance spreadsheet; session 2 (closed) and its certificates in Certificates (source "Attended a session"); session 3;
Log a toolbox talk; Numbers › Sessions + spreadsheet "Sessions" sheet; the course form "How it is taught"; Settings › HR ›
Required training (Vietnam card's group-4 line); Vietnamese labels.

Needs a specific person — as server-side calls (`odoo-bin shell -d payobook`, `env(user=<uid>, context={'allowed_company_ids':[5],'lang':'vi_VN'})`, roll back):

| Walk item | Login (uid) | Call | Expect |
|---|---|---|---|
| Learner "My sessions" | demo.field@example.com (6533, booked on session 1) | `pb.my.training.home()['sessions']` | `next.id == 1`, `my_state 'booked'`, `ics_url '/my/training/sessions/1/calendar.ics'` |
| Learner calendar file | 6533 | `pb.my.training.session_ics(1)` | bytes starting `BEGIN:VCALENDAR`, `METHOD:REQUEST`; a stranger gets `None` |
| Learner course card | 6533 | `home()['courses']` → course 290 | `delivery 'session'`, `session.my_state 'booked'` |
| QR scan (only while session 1 is under way, or within an hour of its start) | 6533 | `pb.my.training.attend_by_token(<session 1 qr_token>)` | `'ok'` (then `'already'`); before that: `'not_yet'` |
| Self-booking | demo.field after the training team ticks "People may book a seat themselves" on course 290 (already ticked by the seed) and they owe it | `home()['sessions']['bookable']` / `book_my_seat(id)` | demo.field is already booked on session 1, so nothing bookable — expected |
| Manager toolbox talk | lam.ngo@example.com (2326) | `pb.training.toolbox_lists()`, `toolbox_people('')` | `allowed True`, `is_team` True only if lam has no training group; people = only those under him |
| Manager's own sessions | 2326 (booked on session 1) | `pb.my.training.home()['sessions']` | `next.id == 1` |
| HR lead's attended session | demo.hr@example.com (6678, attended session 2) | `pb.my.training.home()['courses']` → course 290 | `finished True`; Certificates register has their "DEMO Site safety walk — certificate (…)" |
| demo.learner@example.com (5344) | portal-only, no employee record (L3 finding) | — | not on any session: My sessions block absent (correct) |
