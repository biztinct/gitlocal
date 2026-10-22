# LEARNING L5 — Outside courses, requests, versions, results, feedback, skills — report

Implementer: Opus, 2026-10-22. Spec: `L5_COURSES_REQUESTS_SKILLS.md` (LD6: outside catalogue = our own list). Ledger:
`LEARNING_LEDGER.md` (candidate rows from LN52 in §5).
Status: **COMPLETE** — LIVE ×4 DBs 2026-10-22 20:27 AEDT (DONE 09:27 UTC, EXIT=0 ×4); live walk by Fable passed (§11). Not pushed.

## 1. What ships (committed on 19.1, not pushed)

| Module | Live now | After L5 |
|---|---|---|
| pb_training | 19.0.1.8.0 | **19.0.1.9.0** — also carries the unreleased 19.0.1.8.1 (the 7-day sessions figure). Five new tables (`pb_training_outside_course`, `pb_training_request`, `pb_training_followup`, `pb_training_skill_grant`, the outside course ↔ job link), new columns on the course (version, version note/date/log/queue, re-read days, "people may ask to take it"), the assignment (`course_version`, `request_id`), the claim (`outside_course_id`, `request_id`) and the feedback request (`assignment_id`, `training_request_id`, `channel_id`, `outside_course_id`, `followup_id`, two new kinds). A new approval catalogue row **"Course request"** and a migration (`19.0.1.9.0/post-course-requests.py`) that lays its route on every company and writes four new switches. Two dependencies named: `pb_lifecycle`, `hr_skills` — both already installed on all four live databases (checked read-only). |
| pb_training_growth | 19.0.1.0.0 | unchanged (reloads with `-u pb_training`) |
| pb_approval_config and every other module | — | **unchanged**. The Inbox bug was in pb_training's own claim detail (§3.7), so the fix is in pb_training. |

### What a user sees
- **Learning › Courses › Outside courses** (third inner tab). Hero: the outside list as cards — name, provider, "Outside" chip,
  kind (Online · In a classroom · An exam or licence), cost in words ("3,000,000 ₫" / "Free"), hours, certificate, rating
  ("4.3 · 17 ratings"), an amber "2 waiting" when somebody has asked and nobody has decided. Quiet numbers (courses · requests
  waiting · taken this year · archived), filters (kind, job, search, archived). **New outside course** drawer (name, provider, kind,
  link, cost, hours, blurb, certificate + months, jobs). A card opens the **course page**: who asked and where each request is,
  claims against it, what people said, skills it gives (add / remove), **Put someone on it**, Edit, Archive / Bring it back.
- **Learning › Claims › Requests** (second inner tab; Overview's "Course requests waiting" lands here). One sentence ("1 request is
  waiting for a decision · 1 agreed and not taken yet · 3,000,000 ₫ set aside") over four numbered steps (Waiting · Agreed, not taken
  yet · Taken or claimed back · Turned down or cancelled), filters, rows with who / what / cost / "Waiting on <name>" / why, and
  **Agree / Turn down** (only for the person whose seat is live), **Mark as taken** (agreed outside course), Open. **Put someone on a
  course** drawer (ours · outside · something else, people, why).
- **Course drawer** (Courses tab): **Version** ("Version 2, since 22 Oct 2026. What changed: …", history, **Publish a new version**
  for training managers: what changed + days to read it again), **What people said** (average, count, % who would recommend, last
  comments, managers' "work changed x/5 · y% used it"), **Skills it gives** (add / remove), **Asking to take it** (switch). Cards
  carry a "v2" chip and the rating.
- **Learning › Tests** (rebuilt): list of tests (course, pass mark, goes, how questions are drawn, people, pass rate, grey at zero).
  **Results drawer** — hero: pass-rate ring, ten score bars that add up to the attempts, the hardest questions (wrong ÷ asked),
  "Questions drawn per attempt" to change the pool, Open the test editor. **New test** drawer: name, pass mark, goes, "Draw a few
  questions per attempt from a bigger pool" + how many → makes the test (one section drawing N) and opens the editor.
- **Learning › SKILLS** (new rail item, seq 75, sparkles; offered to the training team and to anybody who manages people — managers see
  their own people only). Hero: "On average a person has 4 of 6 required skills · 38 gaps across 120 people"; quiet numbers; filters
  (department, job, skill, only gaps); People view (a chip per required skill: green at level, amber below, rose missing; each gap shows
  the course that closes it and, for the training team, **Close it: <course>**); By skill view (who needs it, at level, below, missing,
  covered %, course that gives it). The rail now has **eleven** items (twelve is the hard maximum).
- **My learning**: **Tell us how it went** (feedback / follow-ups waiting), **My requests** with **Ask to take a course** (drawer: ours ·
  outside list · something else; when; why; says the allowance left and who decides), "Claim this course back", Cancel; **My skills**
  (what is on my record, what my job also needs).
- **Portal**: `/my/training` gains "Ask to take a course" and the feedback asks; **`/my/training/requests`** (ask + my requests, no
  JavaScript); **`/my/training/claims?request=<id>`** opens the claim form already filled in; **`/my/training/feedback/<token>`** — our
  own token page worded for the course ("How was …?", "Has Lan's work changed since …?"), stars 1–5, Yes / Partly / No.
- **Overview**: two quiet chips — **Course requests waiting**, **Follow-ups waiting on managers**.
- **Numbers**: **Ratings** (by course), **Did it work?**, **Requests and spend**, **Skills** (coverage by skill).
- **Inbox** (Approvals): a claim's Receipt and Certificate rows now show (they were silently dropped); a course request shows its
  chips, link and why.
- **Mails** (English, LD10): request agreed (link + how to claim back), request turned down (with the reason), course changed (what
  changed + due), how was the course (feedback link), has the course made a difference (manager's follow-up link).
- **Morning job**: two legs — carry on with re-reads after a new version (capped 500 per press / per morning), and send the
  manager follow-ups that are due.

## 2. Tests

Local runtime `/Users/adity/odoo19`, overlay `scratchpad/l5stage/{pb_training,pb_training_growth}` in front of the L0 staging tree.
Test databases are copies of `am_l4_walk` (L4's walked DB, pb_training 19.0.1.8.0) plus its filestore (LN30), run exactly as the live
upgrade: `-u pb_training`.

| # | Result |
|---|---|
| T1 | **Pass** (3): shape, cost words ("3,000,000", "Free", "8 hours"), negative cost refused; catalogue filters kind / job / search; plain user `allowed: false`; save checks (no name refused, `https://` added), archive hides it. |
| T2 | **Pass** (3): route = manager, then HR lead with condition `amount > 0`; the condition is false for one of ours and true for a paid outside course; the route passes the engine's own validator; catalogue row exists; `seed_all` twice lays nothing new and the new company has its route; `_approval_detail` rows are dicts with exactly `head/sub/cells/tone`. |
| T3 | **Pass** (3): a waiting request books nothing; agreed → committed 3,000,000, left 7,000,000; the claim raised from the request is pre-filled and not counted against itself; claim agreed → request "Claimed back", committed 0, agreed 3,000,000, left unchanged (never counted twice, never dropped); over-allowance sentence names "set aside" and the arithmetic, refusal leaves nothing behind; `claim_over_allowance` switch lets it through; a request never creates an award. |
| T4 | **Pass** (4): ours → one assignment (reason One-off, linked), a second "agreed" makes none, finishing it → "Taken"; refusal mails the reason; cancel while waiting; a stranger cannot cancel; training team "Put someone on it" → agreed, `put_on_by`; plain user refused. |
| T5 | **Pass** (3): options list the outside course until asked, duplicate refused, empty "why" refused, own rows only, "Waiting for a decision"; VI state word differs; portal routes present. |
| T6 | **Pass** (3): only the finisher is reset (lesson not done) and gets one re-read (v2, not for the trial period), certificates untouched, "has changed" mail queued, a second batch adds none; cap 1 with 2 finishers → 1 now, pending, morning leg does the other; a trainer cannot publish, an empty note is refused. |
| T7 | **Pass**: a 2-of-3 pool + a multi-choice question, three attempts: pass rate 67, histogram sums to 3, hardest uses the asked denominator (Q3 1/1, Q1 3 asked / 1 wrong), the multi-choice question counted once per attempt. |
| T8 | **Pass**: New test with "draw 3" → `questions_selection='random'`, one section with `random_questions_count=3`, pass mark kept, editor action; without a pool → "all"; set_pool 0; plain user refused. |
| T9 | **Pass** (HTTP): a survey user with no training group is sent to `/my/training` from a TEST's results page; an ordinary survey's results page is untouched; a trainer sees it. (Plain staff were already refused by the stock route — 403 — so the gate is for survey users outside training.) |
| T10 | **Pass** (3): feedback asked once on finishing, rolls up (4.0 · 1 rating, 100% recommend, the comment shows in the course drawer); switch off → none; token URL and course name. |
| T11 | **Pass** (2): follow-up planned at finish + 30 with the manager, not sent early, sent once on its day to the manager, answered → "Answered", effect 4.0 and 100% used; no manager → "Skipped". |
| T12 | **Pass** (2): finishing gives the skill — the old Basic row is kept as history and closed (valid until yesterday), never edited; no downgrade; an outside course marked taken gives its skill. |
| T13 | **Pass** (3): states ok / missing / below, the closing course suggested, headline; only gaps; a manager sees their team only and cannot "Close it"; somebody managing nobody is not offered the lens; Close it puts our course on. |
| T14 | **Pass**: a submitted claim's detail through the Inbox facade itself (`pb.approval.inbox._detail`) carries Receipt and Certificate rows with the file names. |
| T15 | **Pass** (5): no vendor word, no emoji in the new files; Vietnamese present; "Changed course" reason; Overview chips; Numbers sections. Rail tests updated: eleven lenses, Skills gate + probe, Courses and Claims tabs, Overview queue now six quiet chips at zero. |
| Suites | `/pb_training,/pb_training_growth,/pb_learning_hub` on a fresh copy with `-u pb_training`: **408 tests, 3 failed** in the first full run — `TestTheAssignmentsTab` ×2 (pre-existing since L0) and T9 (the website added its own 301 hop; the test now reads where the page lands — rerun green). **Final run on the committed code: 408 tests, 2 failed (the two pre-existing), 0 errors** (§9). |
| PO gate | pb_training 2,113 rows, 0 code rows without a value. |

**T16 — local Chrome walk** (`localhost:8073`, `am_l5_walk`, seeded with `l5_demo_seed.py`, company 1):
- **Head of training (admin), EN:** rail OVERVIEW … CLAIMS · **SKILLS** · NUMBERS (11). Overview chips "1 Course requests waiting",
  "0 Follow-ups waiting on managers"; the chip lands on Claims › Requests with the sentence and four steps.
- **Courses › Outside courses:** "3 outside courses · 1 request waiting", "Agreed this year: $ 3,000,000.00", quiet numbers, kind and job
  filters, three cards (amber "1 waiting" on Soil science). Licence page: provider, cost, 8 hours, "Certificate, valid 24 months",
  provider link, Who asked (Agreed), Skills it gives "DEMO Spraying · DEMO Good"; Add a skill drawer lists skill types, skills, levels.
- **Course drawer** (DEMO Leading a line): card chips "v2" and "4.2 · 5 ratings"; Version section, history, Publish a new version
  drawer ("Version 3 · Nobody has finished this version yet…"); What people said 4.2 · 5 ratings · 80% would recommend + four comments;
  managers 3.5/5 · 100% used; Skills it gives; Asking to take it switch.
- **Tests:** list with "Each attempt draws 5 of 8 questions"; results drawer (empty states); New test drawer guards ("Give the test a name.").
- **Skills:** "On average a person has 0 of 2 required skills · 4 gaps across 2 people", chips, "No course gives it yet".
- **My learning (admin):** My requests + Ask to take a course drawer (allowance sentence, three kinds, guards).
- **Manager (manager.p3c, VI):** rail CỦA TÔI · KỸ NĂNG (the probe offers Skills to a manager); My learning "Cho chúng tôi biết khóa học
  thế nào" with the follow-up ask, "Yêu cầu của tôi", "Kỹ năng của tôi". **Approvals inbox:** "Course request · DEMO Đỗ Văn Nam · DEMO
  Soil science online", facts, the Link row, chips, route "Their manager" then "HR lead — Not needed" (free course); **Phê duyệt** →
  request Agreed and the "You can take …" mail queued (cancelled — local).
- **Turn down from Requests (admin as HR lead):** a paid request (First aid, 1,200,000) agreed by the manager, then turned down by the HR
  lead from the drawer → "refused" with the reason stored (seen in the database; the browser extension disconnected during this press).
  Before the fix, Agree / Turn down showed to a training user who did not hold the seat and the engine answered "This step is not
  waiting for you" — now only the live seat sees them.
- **Plain employee (nam.p3c, VI), portal:** `/my/training/requests` (three forms, outside list with costs, my request "Agreed" with The link
  / Cancel); feedback token page "How was DEMO Leading a line?" → stars → "Thank you"; the follow-up page "Has DEMO Đỗ Văn Nam's work
  changed since …?" with Yes / Partly / No. Claim prefill (server-side, as the owner of the paid request): form open, request id hidden,
  course and 3000000 filled, the sentence in Vietnamese.
- **Found and fixed in the walk:** badges capitalised words ("5 Ratings") → no capitals; ISO dates on the version line and the feedback
  link → formatted dates; "your manager decides." → whole sentences; the Inbox showed "why" twice → one; sentence fragments split around
  values (VI word order) → whole translatable sentences; decide buttons for non-seat users (above).
- **Console:** no errors on the screens read after tracking started. **Not walked in the browser** (extension down; unit-tested): the
  Put someone on a course drawer's submit, a results drawer with real attempts, the Publish press from the drawer, phone width.

## 3. Deviations from the handover, and why

1. **The route is one route with a condition** on the HR lead rung (`amount > 0`) — the engine supports conditions; the fact type is
   `decimal` (the engine's validator refuses `float` in a condition — the claim's specs use `float` but have no condition).
2. **Pre-booked money moves when the claim is AGREED**, not when it is linked: linked-but-not-agreed it stays "set aside" (the claim does
   not count its own request against itself), so the money is never in neither bucket.
3. **Outside courses: `job_ids` instead of `tag_ids`** (the filter the handover asks for is "By job"; course tags need a tag group).
   Outside courses are their own inner tab (Courses › Outside courses), not mixed into the Courses grid.
4. **Feedback uses our own token page** `/my/training/feedback/<token>` (worded for the course) and our own two mail templates, storing
   on `pb.feedback.request` (house pattern) — pb_lifecycle's page says "a few words about <person>", wrong for course feedback.
5. **Skills:** the stock skills engine's own create command is used (it closes the old row "valid until yesterday" and adds the new one;
   a row added within the last day is replaced, its rule). Managers see suggestions but no **Close it** (putting people on courses is the
   training team's job; a manager asking for a report would be the approver of their own request).
6. **Results-page gate** covers tests only (certifications and course tests) for people without a training group; ordinary surveys (HR
   pulse) untouched. Plain staff never reached it (stock 403).
7. **Version finishers are worked out once** at the press and queued on the course; the morning job carries on with the queue.
8. **"Outside" request taken:** the training team marks an agreed outside course "Taken" (or the agreed claim makes it "Claimed back");
   skills and feedback follow either.
9. **Help (pb_learn) is not touched** — L1/L3 added rail items without it either; the Help screen's Learning description still lists the
   L0 tabs (owner item 7).

## 4. Vietnamese

`pb_training/i18n/vi_VN.po`: **505 new entries** and 54 existing entries gained the marker or occurrence the new screens need (LN48);
text-level merge, **pure additions** (3,261 lines added, 0 removed — LN29). Words said through `tr()` (outside kinds, request kinds and
states, follow-up states, "Changed course") are `odoo-python` entries. "Outside course" = **khóa học bên ngoài**, request = **yêu cầu**,
set aside = **giữ chỗ**, skills = **kỹ năng**. Mail bodies and subjects stay English (LD10).

## 5. Ledger rows to add after the deploy (candidates, from LN52)

- LN52: **The approval engine's validator types a fact `decimal`/`int`/`percent` for size comparisons**; a `float` fact (the claim's
  specs) works only while no rung has a condition on it — a `gt` condition on a `float` fact makes `Seed.lay` refuse the whole route
  (`operator_type_mismatch`) and the migration "lays it for 0 companies".
- LN53: **The stock `/survey/results/<id>` already answers 403 to staff with no survey group** (the record converter checks read access
  before the controller runs); a results gate is for survey users outside the training team. And the website may add its own 301 hop —
  HTTP tests read where a page LANDS (`res.url`), not the first status.
- LN54: **`slide.channel.partner._recompute_completion` never touches a "completed" membership** — to reset somebody's progress, set the
  membership back to "joined" first, then mark the lessons not done (the slide-partner write triggers the recompute).
- LN55: **Under a published route the engine refuses a decision from anybody but the live seat** ("This step is not waiting for you"),
  admins included — a board that shows Agree must check `_chain_my_seat()` for the reader.
- LN56: **An engine-built chain title is frozen in the language of whoever sent the request** (the seed ran in English, so Vietnamese
  inboxes show "Course request · …").
- LN57 (walk): the Courses lens shows the "looked after by the training team" refusal when its board read fails — L6 candidate.
- LN58 (walk): ChatGPT started a payroll release two minutes after L5's DONE; read the deploy log before calling a live walk failure a
  bug (LN41 again).
- All written into the ledger as LN52–LN58.

## 6. Score against the design bar

1. **Hero moments:** outside cards with cost / rating / "waiting"; Requests' sentence over four steps; Tests' ring + ten bars + hardest
   questions; Skills' sentence and coloured chips with "Close it"; the course drawer's version line and "4.2 · 5 ratings".
2. **Zero dead ends:** every empty state says what the thing is and what to press; every refusal is a sentence with the arithmetic
   (allowance); a decide button only where the reader can decide; the portal works without JavaScript.
3. **Plain language EN + VI:** walked in both; sentence fragments around values removed.
4. **Motion:** card lift, bar grow, ring; off under reduced motion.
5. **Weakest:** phone width not walked; the last browser presses checked server-side.

## 7. Owner items (plain English)

1. **The demo's "new version" uses a small course of its own, "DEMO Safe chemical storage"**, not course 27 (the coordinator's call:
   course 27 is the first step of the demo learning paths and re-reading it would have reopened that step). Three demo people finished
   it and now have a re-read: Trần Minh Khôi, Ngô Bảo Lâm, Lâm Tuấn Kiệt. In real use, publishing a new version of a course that is on
   a learning path does reopen that step for the people who re-read it — say if you want paths to ignore re-reads.
2. **Paid outside courses go to the HR lead after the manager.** Free ones and our own courses go to the manager only. Change it in the
   Approval Matrix if you want, for example, the HR lead only above five million.
3. **Agreed outside courses hold money aside** from the person's allowance until the claim is agreed, so the allowance page can show
   less left than "agreed" alone.
4. **Course feedback and the 30-day manager follow-up are on** for every company (two switches). Each person gets at most one email per
   course; managers one per course per person.
5. **Managers see the Skills tab for their own team**, but only the training team can press "Close it".
6. **Emails are English** like the other training emails (LD10).
7. **Not Learning's:** the Help screen's description of Learning still lists only the first eight tabs (Certificates, Paths and now
   Skills are missing) — a job for whoever regenerates the Help lessons.
8. **When the Courses screen cannot reach the server** (for example while another release restarts it) it shows "Training is looked
   after by the training team" instead of "could not load — try again". It is harmless and comes right on the next load; a plain retry
   message is planned for L6.
9. **Demo:** the demo company's training allowance is 5,000,000 ₫ for 2026; the licence (3,000,000 ₫) put on a demo person leaves
   2,000,000 ₫ for them.

## 8. Deploy plan (as at the gate) — risky tier

**Why risky:** five new tables, new columns on four existing tables, a new approval catalogue row, a migration that lays a route on every
company. No existing data is rewritten. **Backups first.**

**Live facts (read-only, 2026-10-22 ~09:05 UTC):** pb_training 19.0.1.8.0, pb_training_growth 19.0.1.0.0, pb_lifecycle 19.0.1.5.0,
hr_skills installed on p0clone, payobook, payobook_template, rize; active jobs p0clone 26, payobook 37, payobook_template 0, rize 69;
`hr_lead` responsibility exists on all four; HTTP server pid up, health 200. `/opt/deploy-notes.md` last line: my HOLD note (08:59 UTC);
no open START. Payobook demo facts: company 5 allowance 2026 = 5,000,000; course 27 "DEMO Agronomist basics" (7 finished assignments,
2 completed memberships); lam.ngo 2326 / employee 17122; demo.field 6533 / 17140 (manager 17122); demo.hr 6678 / 21182; DEMO agronomist
jobs 147 / 762 / 1009 / 1010; no "DEMO Line leader" job (the seed makes one).

1. Read `/opt/deploy-notes.md` — no open START; HTTP pid up. Lock with a detached unit (LN25):
   `sudo systemd-run --collect --unit=l5-lock /usr/bin/flock /tmp/payobook-studio-deploy.lock /bin/sleep 10800`. START line
   `… | Claude (LEARNING L5) | START | pb_training | p0clone,payobook,payobook_template,rize | ~8 min, service stopped during -u | outside courses, course requests + route, versions, test results, feedback, skills; git <head>; backups first; p0clone first`.
   Announce to peer sessions.
2. Versions before = 19.0.1.8.0 ×4 (nobody shipped L5 — the HOLD stands; LN15).
3. Backups (LN25): `sudo sh -c "sudo -u postgres pg_dump -Fc <db> > /odoo/backups/learning-l5-20261022/<db>.dump"` ×4, each `pg_restore -l`.
4. Stage: `sudo rm -rf /tmp/deployL5 && mkdir -p /tmp/deployL5`; `git archive <L5 head> pb_training` (check `git log <L5 head>..HEAD --
   pb_training` empty, LN44) → upload; scoped `sudo rsync -a --delete /tmp/deployL5/pb_training/ /odoo/odoo-server/addons/pb_training/`
   (never the addons root); tree hash = local (skip `__pycache__`, `*.pyc`, `.DS_Store`); PO gate on the box (expect 2,113 / 0); one
   addons path.
5. Snapshot active job ids per DB (expect 26 / 37 / 0 / 69).
6. Stop the service (wait on the PID, LN35). Detached unit + sentinel, one DB at a time, **p0clone first**:
   `odoo-bin -c /etc/odoo-server.conf -d <db> -u pb_training --stop-after-init`; grep EXIT, Traceback, ERROR, and the migration lines
   "4 L5 switch(es) materialised" and **"the course-request route was laid for N compan(ies)"** (N = companies on that DB; 0 means the
   route was refused — stop and look). Then payobook, payobook_template, rize. Stop at the first failure and restore that DB.
7. Asset ritual per DB (signal, delete `/web/assets/%`, bump `web.assets.version`); start; registry loaded; warm payobook / rize /
   p0clone; jobs back to the snapshot (payobook_template 72/73 off again if `-u` re-activated them, LN18). The ONE pb_training job runs
   the two new legs — no new cron record.
8. Verify per DB: 19.0.1.9.0 installed; the five tables exist (0 rows except payobook after the seed); `biz_approval_process` key
   `training_request` and an active binding per company; columns `slide_channel.pb_version` (every course 1) / `pb_requestable` (true),
   `pb_training_assignment.course_version`, `pb_training_claim.request_id`, `pb_feedback_request.assignment_id`; switches
   `pb_training.feedback_on=1`, `followup_on=1`, `followup_days=30`, `reread_cap=500`; 0 ERROR lines; `/web/health` 200.
9. Demo data, **payobook only**, service stopped:
   `sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf -d payobook --no-http < docs/handovers/learning/l5_demo_seed.py`
   (three DEMO outside courses; DEMO skill types; course 27 gives Field safety · Basic; DEMO agronomist job + DEMO Line leader require
   two skills each; demo.field asks for Soil science online (waiting on lam.ngo); the training team (demo.hr) puts one demo person on the
   licence (agreed, 3,000,000 set aside); a small "DEMO Safe chemical storage" course finished by three demo people and published as
   v2 (course 27 is NOT versioned — coordinator); test "DEMO Field safety quiz" draws 5 of 8; 6 feedback answers + 2 follow-ups answered
   on course 27; morning legs rolled back; **every mail it queued cancelled**). Restart, warm.
10. DONE line containing **"LEARNING L5 DONE"** (clears the HOLD), release the lock (`systemctl stop l5-lock`).

### Live walk — what needs which login (server-side facade calls, ledger LN43)

The admin tab (head of training, company 5) covers: Overview chips; Courses › Outside courses (cards, filters, the licence page, Add a
skill drawer, Put someone on it drawer — do not submit); course 292 "DEMO Safe chemical storage" drawer (v2 chip, version line, Publish drawer — do not publish);
course 27's drawer (What people said 4.2 · 6 ratings, managers 3.5/5, Skills it gives "DEMO Field safety · DEMO Basic"); Claims › Requests (sentence, steps, rows); Tests (the drawn quiz,
results drawer, New test drawer — do not save); Skills (gaps, Close it — do not press); Numbers (four new sections); Vietnamese labels.

`odoo-bin shell -d payobook`, `env(user=<uid>, context={'allowed_company_ids':[5],'lang':'vi_VN'})`, strip `tz` for times (LN51), roll back:

| Walk item | Login (uid) | Call | Expect |
|---|---|---|---|
| Manager decides in the Inbox | lam.ngo@example.com (2326) | `env['pb.training.request'].browse(1)._chain_my_seat()` | seat open for 2326 on request 1 (demo.field, DEMO Soil science online); `action_approve()` → `approved` (roll back) |
| Inbox detail rows | 2326 | `env['pb.approval.inbox']._detail(<request record of that request>)` | dict rows (Link), chips Course / What it costs / Who runs it |
| Claim receipt row in the Inbox (the live bug) | admin | `_detail` on any submitted claim's approval request | rows Receipt / Certificate present |
| Learner request list | demo.field@example.com (6533) | `pb.my.training.my_requests()` | the Soil science row, `Đang chờ quyết định` |
| Learner options + allowance | 6533 | `request_options()['allowance']['words']` | "Ngân sách đào tạo năm 2026 của bạn: còn …" |
| Claim prefill | khoi.tran@example.com (2324, put on the licence — request 2) | `pb.my.training.claim_prefill(2)` | course, provider, 3000000, sentence |
| Re-read after v2 | khoi.tran@example.com (2324), lam.ngo (2326), kiet.lam@example.com (2327) | `home()['courses']` → course 292 "DEMO Safe chemical storage" | reason "Khóa học đã thay đổi", 0 of 2 lessons done; assignment 536/537/538 `course_version` 2 |
| Skills for a manager | 2326 | `pb.training.can_see_skills()`, `skills_board({})` | True; `team` True, only his people |
| Feedback page | khoi.tran / lam.ngo / kiet.lam (pending asks 93/94/95, from finishing the storage course) | `my_feedback()` → url; GET it as public | "Khóa DEMO Safe chemical storage thế nào?" |
| Results page gate | a survey user without a training group (none on payobook — skip) | — | covered by T9 |

## 9. Final local state (before the gate)

- Commits on 19.1 (not pushed): `dc32e99a0` (wip — server side; installs), `4b1fb816a` (wip — screens, Vietnamese, demo seed; installs),
  `9933ec554` (fix — decide buttons only for the live seat; T9 lands), and the closing docs commit with this report.
- Final suite on the committed code (fresh copy of `am_l4_walk` + filestore, `-u pb_training --test-tags
  /pb_training,/pb_training_growth,/pb_learning_hub`): **408 tests, 2 failed, 0 errors** — only `TestTheAssignmentsTab` ×2
  (pre-existing since L0; they count the copied database's own assignments). The `ir_attachment` foreign-key line in the log is
  pre-existing (L2–L4 logs).
- Tree under test = repo tree (`diff -rq` of the overlay against the repo: identical).
- Walk server on 8073 left running for the coordinator; walk DB `am_l5_walk` kept.

## 10. Deploy record (GO DEPLOY 2026-10-22 09:15 UTC)

| Step | Result |
|---|---|
| Notes / lock | ChatGPT started another payroll release at 09:16 (open START, lock held, site down) — waited for its DONE at 09:22. Lock by detached unit `l5-lock` 09:22–09:27; START 09:22, DONE 09:27 UTC — DONE carries **"LEARNING L5 DONE"** (HOLD cleared); lock released |
| Versions before | pb_training 19.0.1.8.0 ×4 (nobody had shipped L5) |
| Backups | `/odoo/backups/learning-l5-20261022/` p0clone 25 MB, payobook 74 MB, payobook_template 24 MB, rize 31 MB (each `pg_restore -l` ok) + `crons_before.txt` |
| Files | `git archive 9933ec554 pb_training` (nothing after it touches pb_training) → clean `/tmp/deployL5` → scoped `rsync --delete` into `addons/pb_training/`; tree hash equal both sides (dcf747b0…); PO gate on the box 2,113 / 0; one addons path |
| Upgrade | service stopped 09:24:21 (gone by PID 09:24:23); detached unit `l5-upgrade`, `-u pb_training`, p0clone → payobook → payobook_template → rize: **EXIT=0 ×4** (~16 s each), 0 tracebacks, 0 ERROR, 0 CRITICAL; "4 L5 switch(es) materialised" ×4; "course-request route was laid for N compan(ies)": p0clone 1, payobook 4, payobook_template 1, rize 1 |
| Assets / start | signal + `/web/assets/%` deleted + `web.assets.version=learning-l5-20261022` ×4; health 200 at 09:25:46 (down ≈1.5 min) |
| Warm | payobook.com 200, rize.payobook.com 200, p0clone.payobook.com 200 (after the start and again after the seed) |
| Crons | 26 / 37 / 0 / 69 = snapshot (exact id sets); payobook_template 72/73 re-activated by `-u`, switched back off (LN18) |
| After | 19.0.1.9.0 **installed** ×4; the five tables ×4; `training_request` route active on every active company (payobook: companies 1, 2, 5, 6 — company 7 "SG Company" is archived and has no training routes at all, like the claim and delay routes); every course version 1 and open to requests; new columns ×4; switches feedback_on=1, followup_on=1, followup_days=30, reread_cap=500 ×4; five new mail templates ×4; 0 ERROR lines since the start |
| Demo seed (payobook, 7892621aa) | one stop 09:26:33–09:26:59. Outside courses 1 DEMO Pesticide applicator licence (3,000,000 ₫), 2 DEMO Soil science online (free), 3 DEMO First aid at work (1,200,000 ₫); DEMO skill types, course 27 gives "DEMO Field safety · DEMO Basic", the licence "DEMO Spraying · DEMO Good"; DEMO Site Agronomist (147, 4 people) and a new DEMO Line leader (1016, 2 people) require two skills each → Skills board "On average a person has 0 of 2 required skills · 11 gaps across 6 people"; request 1 demo.field → Soil science, **waiting on Ngô Bảo Lâm**; request 2 Trần Minh Khôi → licence, **agreed by the training team**, 3,000,000 ₫ set aside; course **292 "DEMO Safe chemical storage"** (online, on no path) finished by Khôi, Lâm, Kiệt and published as **v2** → 3 re-reads (assignments 536–538); course 27 untouched (version 1); test 177 "DEMO Field safety quiz" draws 5 of 8; course 27 "4.2 · 6 ratings", 2 follow-ups answered (3.5/5); 36 records on the demo register; morning legs rolled back (0 / 0); **11 queued mails cancelled, 0 outgoing since**; 0 ERROR lines |
| Live walk | passed (Fable, §11) |

## 11. Live walk (Fable, payobook.com, 2026-10-22 ~20:30 AEDT) — PASSED

Admin tab (head of training, company 5) plus the §8 server-side calls as the named users (`tz` stripped, rolled back).

- **Screens:** rail with 11 tabs incl. SKILLS; Overview chips "1 Course requests waiting", "0 Follow-ups waiting on managers"; Courses ›
  Outside courses "3 outside courses · 1 request waiting · Agreed this year: 3,000,000 ₫", three cards (kind / cost / hours / certificate
  chips, "1 waiting" on Soil science, Put someone on it), kind and job filters; Claims › Requests sentence "1 request is waiting for a
  decision · 1 agreed and not taken yet · 3,000,000 ₫ set aside", four steps, kind filters, rows; Tests "4 tests · 8 people took one ·
  50% passed", DEMO Field safety quiz "Each attempt draws 5 of 8 questions", Results buttons; Skills "On average a person has 0 of 2
  required skills · 11 gaps across 6 people", numbers 6 / 11 / 9 / 2, People / By skill, "No course gives it yet"; Numbers sections
  Ratings, Did it work?, Requests and spend, Skills.
- **Console:** clean apart from two warnings at 20:29 AEDT when another release restarted the server (get_board 502 — not ours); during
  that outage Courses showed the "looked after by the training team" panel and loaded normally afterwards (owner item 8, LN57).
- **Server-side:** lam.ngo holds the seat on request 1 and `action_approve` → approved; the Inbox detail for the request = dict rows
  (Đường dẫn) + chips Khóa học / Chi phí / Đơn vị tổ chức / Khi nào; **a claim's Inbox detail now has the Receipt and Certificate rows —
  the live bug is fixed**; demo.field `my_requests` "Đang chờ quyết định", allowance words "Ngân sách đào tạo năm 2026 của bạn: còn
  5.000.000 ₫."; khoi.tran `claim_prefill(2)` course / provider / 3,000,000 + sentence; re-reads on course 292 for 2324 / 2326 / 2327 =
  "Khóa học đã thay đổi", 0 of 2, due in 14 days; lam `can_see_skills` True, `skills_board` team True (3 people, 6 gaps); khoi
  `my_feedback` link present.

## 12. Commits (on 19.1, not pushed)

- `dc32e99a0` wip — server side (installs); `4b1fb816a` wip — screens, Vietnamese, demo seed (installs)
- `9933ec554` fix — decide buttons only for the live seat; T9 reads where the page lands — **the deployed tree**
- `71fe975cc` docs — report at the gate; `7892621aa` docs — seed versions its own DEMO course, not course 27; `c6180e7c8` docs — deploy record
- closing commit — this walk section, ledger rows LN52–LN58, phase log
