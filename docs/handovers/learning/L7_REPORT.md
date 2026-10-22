# LEARNING L7 — The learner's phone — report

Implementer: Opus, 2026-10-23. Spec: `L7_LEARNER_PHONE.md` (LD7, LD8, LD9 decided as recommended; SCORM out). Ledger:
`LEARNING_LEDGER.md` (candidate rows from LN66 in §5).
Status: **AT DEPLOY GATE** — built, committed (WIP commits, not pushed), tested locally (L7 tests, the full Learning + PayAI
suites, a node suite, a live-data run on a copy of p0clone) and walked in Chrome at phone width. Not deployed.

## 1. What ships (committed on 19.1, not pushed)

| Module | Live now | After L7 |
|---|---|---|
| pb_training | 19.0.1.10.0 | **19.0.1.11.0** — carries 19.0.1.10.1 (the two L6 wording fixes). One new column `slide_channel.pb_short`; one new frontend script + stylesheet; one new view file; JSON answers on two existing routes; one new public route (the home-screen manifest). No migration, nothing existing rewritten. |
| pb_training_payai | — | **19.0.1.0.0, NEW** (`auto_install` with pb_payai_actions + pb_training, so it installs itself on all four databases). One new column `slide_channel.pb_draft_source_id`; the "Draft it with PayAI" way of starting a course; one PayAI action, `draft_course`, registered from this module. |
| pb_learn | 19.0.20.6.1 | **19.0.20.6.2** — Help's Learning page describes the new learner screens (generated content only; `vi_VN.po` unchanged). |
| pb_payai_actions | 19.0.4.2.2 | **unchanged** — no file touched; the new action registers itself from pb_training_payai. |
| pb_learning_hub, pb_training_growth | 19.0.1.0.0 | unchanged (pb_training_growth reloads with `-u pb_training`). |

### What a user sees

**The learner, on a phone (`/my/training`, the portal):**
- **Next for you** — one card right under the page title: the one thing to do next, why, and one button that goes straight in
  ("DEMO Fire safety · 9 days overdue — It is past its date. Finish it, or ask your manager for more time. [Open]"). Amber when
  something is late or a certificate is running out. The same answer is the hero of **Learning › My learning**.
  The rules, first match wins: a late course or late path step → the path's next step → a certificate running out within 30 days
  → required training missing → (practical sign-off: not built, LD5) → the course nearest to done → a course not started yet →
  a session today or tomorrow → feedback waiting → a three-minute lesson → "Nothing to do right now."
- **Three minutes today** — one short lesson (5 minutes or less, shortest first; or any lesson of a course the training team marked
  "Short lessons"). Hidden when nothing fits — it never promises three minutes for a long lesson.
- **The on-time streak** — "3 in a row, on time" (or "Your last course was finished on time."). Only the person sees it.
- **A badge on every certificate** — a medal with the course's initials, brand purple while valid, amber when it needs renewing,
  grey once it has run out — on the certificates page and on My learning. The certificate reminder email carries the same badge.
- **The lesson page keeps its place** — scroll back to where you were when you open a lesson again (and a video's time when it is
  an uploaded video). **Mark as done and quiz answers work with the signal gone**: "Saved on your phone. It will send when you are
  back online." — and when the signal returns (or on the next training page that opens) they are sent, oldest first, with
  "Sent while you were offline: DEMO Quick check · passed". A quiz answered offline is marked then.
- **Thumb-sized** — every button the lesson asks a thumb to press is at least 48 px tall on a phone; a document lesson never fills
  the whole screen and has **Open the file** under it for phones that will not show a file inside a page.
- **Show both languages** — on a lesson that has been translated, the English and Vietnamese sit one under the other, each with
  its EN / VI chip; the phone remembers the choice. Without the script it is a plain link.
- **"My training" on the home screen** — the pages carry a home-screen icon (Payobook mark) that opens `/my/training`. There is
  **no offline app and nothing is stored for offline reading** (LD7).
- The lesson page's own buttons now speak Vietnamese too (Đánh dấu đã xong, Bài tiếp theo, Kiểm tra câu trả lời …).

**The training team (Learning › Courses):**
- **New course** opens a small drawer: **Start a blank course** (the old form) or **Draft it with PayAI from a document** — choose a
  PDF, Word or text file (10 MB at most), pick English or Vietnamese, press **Draft the course**. A few seconds later the course
  drawer opens on an **unpublished** course with three to eight short reading lessons and a ten-question quick check, and a line on
  top: "Drafted by PayAI from forklift-procedure.txt. Read every lesson before you publish." The course's history says who drafted
  it, from which file and with which model. **PayAI never publishes**; nobody is on the draft until somebody is put on it.
  With no PayAI provider set up the card says so ("PayAI is not set up for documents yet. Ask the administrator to add a provider
  under Settings › PayAI.") and nothing is sent anywhere.
- The course drawer marks every lesson with no Vietnamese (**Missing Vietnamese**, and "4 lessons missing Vietnamese" by the
  heading), and has the **Short lessons, 3 to 5 minutes each** switch.
- **PayAI chat:** "Draft a course from the forklift procedure" (or "soạn khóa học từ tài liệu …") finds that file among the courses'
  files the person can open and shows a card with **Open New course with this file** — no "Do it". The button opens New course
  with the file already picked; the draft is made there.

**Help:** the Learning page's "My learning" and "Courses" lines and the "what next" sentence describe the above; a new shortcut
"Draft a course from a document".

## 2. Tests

Local runtime `/Users/adity/odoo19`; overlay `scratchpad/l7stage/{pb_training,pb_training_growth,pb_home_hub,pb_learn,
pb_learning_hub,pb_payai_actions,pb_training_payai}` (= repo) in front of the L0 staging tree. Test databases are copies of
`am_l6_walk` (L6's walked DB, pb_training 19.0.1.10.0) plus filestore (LN30), upgraded exactly as live will be:
`-u pb_training,pb_learn -i pb_training_payai`.

| # | Result |
|---|---|
| T1 | **Pass** (4, HTTP): `/done` with `X-Requested-With` answers `{ok, done, next_url, lesson_name}` and the lesson is done; `/quiz` answers `{ok, passed, result{passed,wrong,unanswered,right,message}, next_url}` — the marks only, never which answer is right; a refusal (a quiz lesson posted to `/done`) is `{ok:false, problem:'quiz', message}`, never a page; the plain form post still redirects to the next lesson. Probes first and skips with the reason when the server's database filter logs the test session out (LN63). |
| T2 | **Pass**: node suite `pb_training/tests/js/portal_lesson.test.mjs` **19 passed, 0 failed** (order kept; cap 50, oldest dropped; replay oldest first and stops at the first press that cannot get through, the rest stay in order; a second replay sends the rest; a server refusal takes the press off the phone; a throwing send stops; blocked storage never throws; only `/my/training/<c>/<l>/(done\|quiz)` is ever read back or sent; the queue holds ids, answers and a time only). The Odoo test runs the same node file when `node` is on the server (it is on the live box, v18.19.1) and skips with a reason otherwise; plus a source check: plain script, no service worker, every storage call wrapped. |
| T3 | **Pass** (6): ≤ 5 min first (3 min picked over 30 min); none → `None`; a "Short lessons" course offers its shortest; a finished lesson is not offered; `home()['three']`; the switch through `act('set_short')` (trainer) and `get_course()['short']`. |
| T4 | **Pass** (4): the rule order, taking one fact away at a time: overdue → path → renewal → required → continue → start → session → feedback → three → none (`NEXT_RULES`, sign-off waits for LD5); the hero goes into the lesson (`/my/training/1/10`, Continue, "4 days overdue"); Vietnamese words differ from English for reason, button and "Nothing to do right now."; `home()['next']` on a real course. |
| T5 | **Pass** (3): counts on-time finishes only, a late finish resets it, "2 in a row, on time"; agreed more time counts, no due date is skipped; never on a board (source check of the Overview / Numbers files). |
| T6 | **Pass** (3): no second language when nobody translated the lesson; with a Vietnamese translation the English reader gets VI (name + text) and the Vietnamese reader gets EN; "Missing Vietnamese" true before, false after, count matches; the toggle is remembered (`pbtr.both`) and works without the script (`?both=1`). |
| Badge | **Pass** (2): initials ("Fire safety for the warehouse" → FS, "An toàn lao động" → AT, "DEMO Forklift licence" → FL), brand colour; drawn on the wallet and My learning; no `gamification.badge.user` rows. |
| T7 | **Pass** (9, pb_training_payai, **fake provider — no AI call from any test**): unpublished, members-only, by-invitation training course, made as the trainer, nobody enrolled (LN46), 3 lessons (script tags stripped), a 10-question quiz with one right answer each, linked file, chatter line with file and model, drawer banner, invisible to the learner pages; no provider → the sentence and nothing sent; a Word file is read **without python-docx**; an unreadable Word file → "Save it as a PDF first"; a plain user → AccessError; a file the trainer cannot open → AccessError (never sudo) and nothing sent; > 10 MB refused before decoding; a picture file refused; a useless answer → a sentence; a Vietnamese draft is stored in Vietnamese. |
| T8 | **Pass** (4): `draft_course` is registered, tier `prepare`, screen = the Learning entry, method gate = training team; English and Vietnamese phrasings match, a "how do I" question does not; the plan card has no "Do it", only the door to Learning › Courses with `pb_training_new_course` / `pb_training_draft_attachment` in its context; no course is made; a file the person cannot open is not found; the Courses lens reads the arrival and the drawer registers its way. |
| T9 | **Pass** (2): `/my/training/manifest.webmanifest` is JSON (`application/manifest+json`), start_url and scope `/my/training`, name "My training", icons on disk; no `serviceWorker.register` anywhere in pb_training, no service-worker route, the head carries the manifest link. |
| T10 | **Pass** (3+2): no vendor word, no emoji in the new files (both modules); Vietnamese for every new word; phone words one per line. |
| Suites | **Fresh copy `am_l7_t2`, `-u pb_training,pb_learn,pb_payai_actions -i pb_training_payai --test-tags /pb_training,/pb_learn,/pb_learning_hub,/pb_training_growth,/pb_training_payai,/pb_payai_actions`: 1,187 tests** (pb_training 696, pb_learn 487 … see note). Every failure there **also fails without L7**: pb_payai_actions 85 test names — **the identical set** on a baseline copy with the pre-L7 code (`am_l7_bl`, l6stage, `-u pb_payai_actions`, diffed by name): this computer's users are Vietnamese, so cards come back in Vietnamese where the tests expect English (LN14 / PA11 kind); pb_learn TestGuideTruth.test_01, TestLearnrevP5.test_f2, TestStatutoryRightNow ×7 and pb_training TestTheAssignmentsTab ×2 — the same baseline failures L0–L6 listed. One L7 test (T10 Vietnamese) failed there: it looked for "Open the file" where the catalogue holds the page term "&lt;span&gt;Open the file&lt;/span&gt;" (translated) — the test was wrong, corrected, and every L7 class rerun green on the final code (see below). |
| **Live-data run** | **Copy of live p0clone** (read-only `pg_dump` from the box, restored locally, no filestore; stage = `git archive` of commit `66e1868d5` = live payroll `dec04c7b2` + the L7 commits; `-u pb_training,pb_learn,pb_payai_actions -i pb_training_payai --test-tags /pb_training,/pb_learn,/pb_learning_hub,/pb_training_growth,/pb_training_payai,/pb_payai_actions`): **1,194 tests — pb_training 696, pb_learn 494, pb_payai_actions 323, pb_training_payai 21, pb_learning_hub 13, pb_training_growth 7 — 1 failed, 46 errors.** The 46 errors are pb_payai_actions tests that need a PayAI provider ("PayAI is not configured" — p0clone has none): **the identical 46 names on the same p0clone copy with the live code before L7** (`am_l7_p0bl`, stage `dec04c7b2`, `-u pb_payai_actions`). The 1 failure was my T10 test looking for "Open the file" where the catalogue holds the page's term "&lt;span&gt;Open the file&lt;/span&gt;" — test corrected, rerun green. **Every Learning test passed on live data**, the pb_learn baseline failures of this computer do not occur there. The p0clone dump and both local copies were deleted after the run. |
| PO gate | pb_training **2,358 rows, 0 code rows without a value** (was 2,291: 63 new entries, pure additions, 0 lines removed); pb_training_payai **50 / 0** (new catalogue). `pb_learn/i18n/vi_VN.po` unchanged by the regeneration. |
| Help checks | generator `--check` up to date (6 files); `check_contract` 73 passed; step shape 0 failed; scenario rules ok; jargon lint clean; "gõ DUYỆT" = 1; `pb_payruns` present; 0 "These figures do not add up"; JS library 111/0, guide_panel 117/0, lesson_panel 113/0; `fixture.js` unchanged. |

**T11 — local Chrome walk** (`localhost:8078`, `am_l7_walk` = L6's walked DB upgraded as live, seeded with
`l7_demo_seed.py`). The agent's Chrome window cannot be resized (`innerWidth` stays 1920), so phone width was walked in a same-origin
**390 px frame** — the page's own phone layout (media queries follow the frame). Screenshots `outputs/learning-l7-20261023/`.
- **Learner nam.p3c (Vietnamese), phone:** `/my/training` — "VIỆC NÊN LÀM TIẾP · DEMO Fire safety · Quá hạn 9 ngày · Đã quá hạn. Hãy
  hoàn thành, hoặc xin quản lý thêm thời gian. [Mở]" (amber), "BA PHÚT HÔM NAY · DEMO Đeo thẻ nhân viên · 3 phút [Bắt đầu]", the streak
  chip; manifest link and theme colour in the head (`local-phone-my-training-vi.png`).
- **Lesson page:** Show both languages → VI and EN title and text stacked with chips, label becomes "Hiện một ngôn ngữ"; Mark as done
  48 px (`local-phone-both-languages-vi.png`). **Place kept:** a lesson saved at 300 px reopened at exactly 300 px.
- **Dropped signal (fetch made to fail in the frame):** Mark as done → "Đã lưu trên điện thoại. Sẽ gửi khi bạn có mạng trở lại.", the
  button turns into "Đã lưu trên điện thoại", one item in the queue (`local-phone-mark-done-saved-offline.png`); next page load →
  "Đã gửi những gì bạn làm lúc mất mạng: DEMO Đeo thẻ nhân viên · đã xong", queue empty, the lesson done on the server.
  **Quiz offline:** both answers picked → "Câu trả lời đã lưu trên điện thoại…", queue holds the two answer ids
  (`local-phone-quiz-saved-offline.png`); signal back (`online`) → "… DEMO Kiểm tra nhanh · đạt" with a tick
  (`local-phone-quiz-replayed-passed.png`).
- **Certificates page:** three badges PH (grey, ran out), FO (amber, 19 days), WA (purple) (`local-phone-wallet-badges-vi.png`).
- **Head of training (admin), desktop:** My learning — "NEXT FOR YOU · Handling customer data — lesson 1 · Your path is late…"
  (amber) with progress, Three minutes today, the streak, the WA badge on My certificates (`local-my-learning-next-for-you.jpg`).
  Courses › New course — two ways; with no provider: the honest sentence (`local-new-course-no-provider.jpg`). With a **local
  stand-in provider** (a 127.0.0.1 endpoint answering one fixed draft — no outside call, no credit): a text procedure → the drawer opens
  "DEMO Forklift safety (local draft)", unpublished, banner, 4 lessons each "Missing Vietnamese", the Short lessons switch, 10
  questions, nobody enrolled, chatter "Drafted by PayAI from forklift-procedure.txt with ollama local-mock, for Administrator…"
  (`local-draft-course-drawer.jpg`). **PayAI chat:** "Draft a course from forklift-procedure" → the plan card, no Do it, "Open New
  course with this file" (`local-payai-draft-card.jpg`) → Courses with New course open and the file picked
  (`local-payai-door-prefilled.jpg`).
- **Console:** no errors on any screen walked.
- **Found and fixed in the walk:** the toggle's labels broke out of their paragraph (a block inside `<p>`); the language chips showed
  before "Show both languages"; a Vietnamese lesson text written over the English (LN66); the phone words were one translation term
  (LN67); after a saved press went through, the button now becomes "Next lesson"; the hero button is full width on a phone; the lesson
  kind ("Reading", "Quick questions") is said in Vietnamese.
- **Not walked:** a real AI provider (owner item), a real phone's home-screen install (needs the live site's HTTPS), the certificate
  email (no outgoing mail locally; tested by its builder only).

## 3. Deviations from the handover, and why

1. **Manifest without `biz_geo_tracking`.** The route clones the mixin's manifest shape inside pb_training; depending on the tracking
   module for one JSON answer would pull it into every database's Learning. No service worker, as LD7.
2. **"New course" had no drawer** (it opened the stock form). It now opens a small drawer with **Start a blank course** and any other
   way a module registers (`NEW_COURSE_WAYS`); with no other way installed it still opens the form straight away.
3. **Word files are read without python-docx** (neither the live box nor this computer has it): python-docx when present, otherwise the
   file's own XML through the standard library. "Save it as a PDF first" is said only when neither can read it.
4. **PDF words are read on the server first** (the PDF reader this build already has). The document-reading provider is asked only for a
   PDF with no words in it (a scan), and only when it reads PDFs itself (`accepts_pdf`, the `biz_doc_ocr._extract` rule). On payobook the
   document provider is OpenAI, which does not take PDFs directly — **a scanned PDF gets a sentence** asking for the Word file.
5. **The draft is written by the chat's provider** (`payroll.ai.config.get_active_config()`: an insights row first, never the OCR engine)
   — on payobook that is the active OpenAI row (gpt-4o-mini). Max tokens raised to 6,000 for the call.
6. **Three minutes:** "else the shortest" applies only inside a course marked "Short lessons", so the card never offers a long lesson as
   three minutes. A lesson nobody timed counts as unknown.
7. **Next for you** gained a **"start"** rule (an assigned course not started yet) after "continue" — without it a person with only
   untouched courses would read "Nothing to do right now."; the sign-off rule is in the order and answers nothing (LD5).
8. **The badge in the email** is email-safe markup (a round cell with the initials), not SVG (mail clients drop SVG), added to the queued
   reminder mail itself because the templates are `noupdate` and would not change on a live database.
9. **Streak words:** one on-time finish reads "Your last course was finished on time."; an agreed "more time" date counts; an assignment
   with no date is skipped (neither counts nor breaks).
10. **The phone script arrives with the frontend's lazy bundle**, a moment after the page. A tap in that first moment takes the no-script
    path (the plain form post / the `?both=1` link), which works the same.
11. **The lesson page's existing buttons and empty state** had no Vietnamese; translated (the page is L7's).
12. **pb_payai_actions is not changed at all**: the action is registered from pb_training_payai (`@payai_action` at import); its method
    gate also checks the module is installed in that database (the catalogue is per server process).
13. **The chat action finds documents among the courses' files** (attachments on courses) that the person can open; anything else is
    "I could not find a document called … Upload it in Learning › Courses › New course."

## 4. Vietnamese

`pb_training/i18n/vi_VN.po`: **63 new entries** and 14 existing entries gained the marker or occurrence the new screens need (LN48),
text-level merge, **pure additions**. "Next for you" = **Việc nên làm tiếp**, "Three minutes today" = **Ba phút hôm nay**, "Show both
languages" = **Hiện cả hai ngôn ngữ**, "Saved on your phone…" = **Đã lưu trên điện thoại. Sẽ gửi khi bạn có mạng trở lại.**, "Missing
Vietnamese" = **Chưa có tiếng Việt**. `pb_training_payai/i18n/vi_VN.po` is new (48 entries, one line per msgid). Help (pb_learn) carries
its own EN + VI in `data.js`. Mail bodies stay English (LD10).

## 5. Ledger rows to add after the deploy (candidates, from LN66)

- LN66: **Writing a rich-text translated field (a lesson's text, `html_translate`) in another language when it has no translation yet
  replaces it in EVERY language** (the walk's Vietnamese overwrote the English). Set a translation with
  `record.update_field_translations('html_content', {'vi_VN': {<English term>: <Vietnamese term>}})`; a plain translated field (`name`)
  is fine with `with_context(lang='vi_VN').write`.
- LN67: **Server-side QWeb view terms merge inline siblings**: `<span>a</span><span>b</span>` is ONE msgid with the markup in it. Give
  each word its own block element (`<div>`) — and never put a `<div>` inside an `<a>` inside a `<p>` (the HTML parser closes the `<p>`
  and splits the link).
- LN68: **A plain script in `web.assets_frontend` runs from the lazy bundle, after the page has loaded**; design so the no-script path
  works for that first moment (forms still post, toggles are links).
- LN69: **Phone width here:** the agent's Chrome window cannot be resized; walk in a same-origin 390 px `<iframe>` (media queries follow
  the frame). **Dropped signal:** replace the frame window's `fetch` with a rejecting one; restore it and dispatch `online` to replay.
- LN70: **`slide.channel.channel_partner_ids` are membership rows, not partners** — `_remove_membership(channel.channel_partner_ids
  .mapped('partner_id').ids)`; passing the row ids raises MissingError from `hr_skills_slides`.
- LN71: **A PayAI action can live in another module** (`@payai_action` at import fills the server-wide catalogue): its `method_gate` must
  also check its own module is installed in the database asking. Local walks of an AI feature use a 127.0.0.1 stand-in (provider type
  `ollama` needs only `requests`; this computer has no `openai` library, the live box has openai 2.44).
- LN72: **Owner standing rule (2026-10-23): never delete payobook demo data.** Seeds only add; no purge, reset or restore over payobook;
  a needed deletion goes to the coordinator first.

## 6. Score against the design bar

1. **Hero moments:** "Next for you" — one sentence and one button, the same on the phone and in My learning; the phone lesson that keeps
   its place and its answers through a dead signal, with "Sent while you were offline … passed"; PayAI's draft opening as a ready course
   with "Read every lesson before you publish".
2. **Zero dead ends:** no provider → a sentence naming where to set it up; a scan, a picture, a too-big file, an unreadable Word file →
   each a sentence with what to do; a refusal on the phone is words, never a stuck queue; Three minutes hides rather than lies.
3. **Plain language EN + VI:** walked in Vietnamese on the phone; every new word translated; the lesson page's own buttons too.
4. **Motion:** quiet rise-in for the new cards; off under reduced motion.
5. **Weakest:** a real AI draft has not been made (no credit spent); a real phone install is only possible on the live HTTPS site; the
   portal home page's older words ("Your training", the late alarm) are still English for Vietnamese readers (not L7's, §7).

## 7. Owner items (plain English)

1. **Try "Draft it with PayAI" yourself on payobook.** It uses payobook's own PayAI (the OpenAI account set up there), so each draft
   costs a little AI credit; I did not make one on live for that reason. Learning › Courses › New course › choose a procedure (PDF,
   Word or text) › Draft the course. The other three databases have no provider set up, so they show the "not set up" sentence.
2. **Scanned PDFs cannot be drafted on payobook** (its provider does not read PDF pictures). Upload the Word file, or a PDF saved from
   it, instead. Say if you want a provider that reads scans.
3. **No offline app** (your decision): with no signal a lesson that was already open keeps working and its presses are saved; a page
   that was never opened cannot be read offline.
4. **"My training" can be put on a phone's home screen** from the browser's menu (Add to Home Screen). It opens the training page.
5. **Badges are private medals on certificates** — no points, no ranking, nothing other people see. The streak is visible only to the
   person.
6. **Translating a lesson:** "Show both languages" appears only on lessons that have Vietnamese written for them; the course drawer now
   says which lessons have none ("Missing Vietnamese").
7. **Still English for Vietnamese readers (older pages, not L7):** the top of the portal training page ("Your training", "2 of your
   courses are past their date…") and "Lesson 1 of 3". Say if you want them translated in a follow-up.
8. **Demo on payobook** (after the deploy): one small course "DEMO Three-minute safety tips" (three short lessons in English and
   Vietnamese and a two-question quick check) is ADDED, and the HR lead `demo.hr@example.com` is put on it. Nothing is removed or
   changed elsewhere (your rule of 2026-10-23).

## 8. Deploy plan (at the gate) — **risky tier** (new module install)

**Why risky:** a new module is installed (`pb_training_payai`, auto-installs with pb_payai_actions + pb_training) and two new columns
are added (`slide_channel.pb_short`, `slide_channel.pb_draft_source_id`). No migration, no data rewritten.

**Live facts (read-only, 2026-10-22 ~20:30 UTC):** pb_training 19.0.1.10.0, pb_learn 19.0.20.6.1, pb_payai_actions 19.0.4.2.2,
pb_training_growth 19.0.1.0.0, pb_learning_hub 19.0.1.0.0 installed ×4; active jobs payobook 37, payobook_template 0, p0clone 26, rize 69;
vi_VN active ×4; openai 2.44 and node v18.19.1 on the box; payobook has an active OpenAI chat row (the others none); last notes line =
my HOLD (17:12 UTC), ChatGPT's last release DONE 17:08 (`dec04c7b2` = HEAD's parent of my commits).

0. **Owner rule:** nothing on payobook is deleted, reset or restored over without the coordinator — if payobook fails its upgrade,
   **stop and report** (do not restore it from the dump on my own); p0clone, payobook_template and rize may be restored from their dumps.
1. Read `/opt/deploy-notes.md` right before START (LN58) — no open START, HTTP pid up. Lock (LN25):
   `sudo systemd-run --collect --unit=l7-lock /usr/bin/flock /tmp/payobook-studio-deploy.lock /bin/sleep 10800`. START line
   `… | Claude (LEARNING L7) | START | pb_training,pb_learn,pb_training_payai(new) | p0clone,payobook,payobook_template,rize | ~8 min, service stopped during -u | learner phone, Next for you, badges, PayAI drafts; git <commit>; backups first; p0clone first`.
   Announce to peer sessions.
2. Versions before = 19.0.1.10.0 / 19.0.20.6.1 ×4, pb_training_payai absent (nobody shipped L7 — LN15/LN64).
3. Backups (LN25): `sudo sh -c "sudo -u postgres pg_dump -Fc <db> > /odoo/backups/learning-l7-20261023/<db>.dump"` ×4, each `pg_restore -l`.
4. Stage: `sudo rm -rf /tmp/deployL7 && mkdir -p /tmp/deployL7`; `git archive <commit> pb_training pb_learn pb_training_payai`
   (check `git log <commit>..HEAD -- pb_training pb_learn pb_training_payai` is empty, LN44; **do not ship pb_payai_actions** — unchanged);
   upload; per module `sudo rsync -a --delete /tmp/deployL7/<m>/ /odoo/odoo-server/addons/<m>/` (never the addons root; the new module's
   directory is created by rsync); tree hashes = local (skip `__pycache__`, `*.pyc`, `.DS_Store`); PO gate on the box (pb_training 2,358 / 0,
   pb_training_payai 50 / 0, pb_learn unchanged); one addons path.
5. Snapshot active job ids per DB (expect 26 / 37 / 0 / 69).
6. Stop the service (wait on the PID, LN35). Detached unit + sentinel, one DB at a time, **p0clone first**:
   `odoo-bin -c /etc/odoo-server.conf -d <db> -i pb_training_payai -u pb_training,pb_learn --stop-after-init`; grep EXIT, Traceback,
   ERROR, CRITICAL. Then payobook, payobook_template, rize. Stop at the first failure (restore that DB from its dump — except payobook,
   step 0).
7. Asset ritual per DB (signal, delete `/web/assets/%` — the frontend bundle gains the phone script, bump `web.assets.version`); start;
   registry loaded; warm payobook / rize / p0clone; **jobs back to the exact snapshot sets** (payobook_template 72/73 off again, LN18;
   L7 adds no job).
8. Verify per DB: pb_training 19.0.1.11.0, pb_learn 19.0.20.6.2, **pb_training_payai 19.0.1.0.0 installed**; columns
   `slide_channel.pb_short`, `slide_channel.pb_draft_source_id`; `curl -s https://<site>/my/training/manifest.webmanifest` JSON with
   start_url `/my/training` (payobook.com, rize.payobook.com, p0clone.payobook.com); the PayAI action registered (shell:
   `from odoo.addons.pb_payai_actions.payai.registry import ACTIONS; ACTIONS['draft_course'].tier == 'prepare'`); stored Help names
   unchanged (LN7); 0 ERROR lines since the start; `/web/health` 200.
9. Demo data, **payobook only, adds only**, service stopped:
   `sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf -d payobook --no-http < docs/handovers/learning/l7_demo_seed.py`
   (makes "DEMO Three-minute safety tips" — 3 short lessons EN + VI and a 2-question quick check — and puts demo.hr on it as a member,
   no assignment; prints Next for you / Three minutes / streak / badges / both languages as demo.hr in EN and VI; cancels anything queued —
   expect 0; no AI call). Restart, warm.
10. DONE line containing **"LEARNING L7 DONE"**, release the lock (`systemctl stop l7-lock`).

### Live walk — what needs which login (server-side facade calls, ledger LN43)

The admin tab (head of training, company 5) covers: **Courses › New course** (two ways; the PayAI card shows its upload — **do not
press Draft the course unless you accept the AI credit**, owner item 1); a course drawer's **Missing Vietnamese** chips and **Short
lessons** switch (read, do not change); **My learning** hero "Next for you", Three minutes today (the demo course), streak, badges; **PayAI
chat** "Draft a course from <a course file name>" → card with no Do it → the door opens New course with the file (press it; nothing is
drafted until "Draft the course"); Help › Learning lines. The portal pages are the employee's: walk them as the HR lead through the shell.

`odoo-bin shell -d payobook`, `env(user=<uid>, context={'allowed_company_ids':[5],'lang':'vi_VN'})`, strip `tz` (LN50/51), roll back:

| Walk item | Login (uid) | Call | Expect |
|---|---|---|---|
| Next for you, three minutes, streak | demo.hr@example.com (6678) | `h = env['pb.my.training'].home(); h['next'], h['three'], h['streak']` | `next.kind` one of the rules with a Vietnamese reason and a `/my/training/…` url; `three.name` "DEMO Đeo thẻ nhân viên" (3 phút) or the quick check; streak words or count 0 |
| Same in English | 6678, `lang en_US` | same | English words, same kinds |
| Both languages | 6678 | `l = env['pb.my.training'].lesson(<demo course id>, <first lesson id>); l['both']` | `other_code` 'EN' (VI reader), `name` "DEMO Wear your badge", article in English |
| Badges | 6678 | `[r['badge'] for r in env['pb.my.training'].my_certificates()['rows']]` | `{initials, tone, hex}` per certificate; tone muted / warn / brand by state |
| Phone answers | 6678 | `env['pb.my.training'].answer_quiz(<demo course>, <quick check>, [<right ids>])` | `{'passed': True, …}` — **roll back** (the JSON wrapper is T1; HTTP cannot reach the DB from the box, LN63) |
| Missing Vietnamese + short | admin (2) | `env['pb.training'].get_course(<demo course id>)` | `short` True, `missing_vi` 0 for the demo course; a course nobody translated shows its count |
| Draft refused without a provider | admin on **rize** (`-d rize`) | `env['pb.training'].draft_setup()` | `ready` False, `not_ready_words` "PayAI chưa được thiết lập…" (no call made) |
| Draft ready on payobook | admin (2) | `env['pb.training'].draft_setup()` | `ready` True — **do not call `draft_upload` / `draft_course` (AI credit)** |
| PayAI action | admin (2) | `from odoo.addons.pb_payai_actions.payai.registry import ACTIONS, match; match('Draft a course from the forklift procedure')` | `('draft_course', {'file': 'forklift procedure'})`; `ACTIONS['draft_course'].method_gate(env, env.user)` True; for demo.hr (training manager) True |
| Manifest | (none) | `curl -s https://payobook.com/my/training/manifest.webmanifest` | JSON, `start_url` `/my/training`, two icons that answer 200 |

## 9. Final local state

- Commits on 19.1 (not pushed): `4b9678af5` (wip — everything, installs), `1b2bdb28c` (wip — tests, Vietnamese, Help, seed, walk fixes),
  `66e1868d5` (wip — walk fixes, screenshots), and the docs commit with this report.
- Live-data run on a p0clone copy: 1,194 tests, every Learning test green; the 46 PayAI errors are the same without L7 (no provider on p0clone). Dump and copies deleted.
- **Final rerun of every L7 class on the final code** (`am_l7_t1`, `-u pb_training,pb_training_payai`): **49 tests, 0 failed, 0 errors**; node suite 19 / 0.
- Walk server on 8078 (`am_l7_walk`, with a local stand-in AI row and PayAI's look/prepare switches on — local only); test DBs
  `am_l7_t1`, `am_l7_t2`, `am_l7_bl` kept.

## 10. Programme close-out (LEARNING L0–L7)

### What the Learning menu now does, end to end (plain English)

- **For everybody (My learning, and the employee's own training page on a phone):** one card says what to do next and takes you
  straight there; a three-minute lesson for a spare moment; your courses with how far you have got and the date each is due; your
  learning paths step by step; your sessions in a room or on site (book a seat, add it to your calendar, scan the code to sign in);
  your certificates and licences, each with a badge and the date it runs out, and your learning record as a PDF; what is required
  for your job; asking to take a course and claiming one back against your yearly allowance; rating a course you finished. Lessons
  work on a phone, keep your place, and keep your answers when the signal drops. Lessons translated into Vietnamese can be read in
  both languages side by side.
- **For managers:** your team's courses, who is late, a one-tap reminder, more-time requests and course requests to decide, a short
  question a month after somebody finishes a course, and three quiet counts on Home › Team.
- **For the training team:** Courses (with sessions, toolbox talks and the outside-course list; a new course can be drafted by PayAI
  from a procedure and published after a read), Paths, Assigned (who owes what by when), Required (who must hold which course or
  licence, the matrix, the four country packs), Tests (results, question pools), Certificates (the register), Claims and course
  requests (against the allowance; agreed claims are paid as one-off amounts in a pay run, never written into a payslip), Skills
  (each person against their job's skills), Numbers (hours, cost, required training, ratings, by department / site / country, with a
  full spreadsheet and an optional report pack by email), and Overview (one sentence on how training stands and what waits, worst
  first). Settings › HR › Learning holds the switches.
- **Help** describes every tab, and PayAI can open these screens or prepare a course draft for you.

### Owner items still open (collected from L0–L7)

| From | Item | What it needs from you |
|---|---|---|
| L0 | Ordinary employees never see the Learning menu; they use their own training page (which now has everything above). | Decide only if employees should land in the back office instead (a bigger change to where they land). |
| L1/L4/L5 (LD10) | All training emails (reminders, certificates, sessions, feedback) are in English for everybody. | Say when you want the email texts in Vietnamese. |
| L2 | Country-pack notes say "Confirm before switching on" instead of naming Rize. | Say if you want "Rize" in them. |
| L2 | A "site" is the employee's Work location, or their department when that is empty (it is empty for everybody today). | Fill in Work locations if sites should differ from departments. |
| L2 (LD12) | Rules marked "To confirm" stay off until Rize confirms them. | Ask Rize; HR switches each on in Settings › Learning › Country packs. |
| L3 | A course shared by two paths counts on both; a course somebody was already late on keeps its date when a path adopts it. | Say if a second path should hold the step back, or give a fresh date. |
| L3 | The demo learner login (`demo.learner@example.com`) has no employee record, so nothing assigned reaches it. | Say if it should get one (walks use the HR lead instead). |
| L4 | Toolbox-talk topics appear on people's training page as "taught in a room". | Say if they should be hidden there. |
| L4 | Demo company time zone (Brussels) vs demo users (Sydney) changes printed session times. | Say if the demo company should be on Vietnam time. |
| L5 | Publishing a new version of a course that is a path step reopens that step for people who re-read it. | Say if paths should ignore re-reads. |
| L6 | The report pack is off on every database. | Turn it on in Settings › HR › Learning › Report pack (preview and test first). |
| L6 | Only the head of training can change the Learning settings. | Say if training managers should too. |
| L6 | Combined releases by other deployers carried Learning work despite a HOLD note. | Say if releases that include Learning must wait for the Learning DONE line. |
| LD5 | Practical sign-off on a phone (supervisor signs a task off) is not built; the Overview counts "sessions to close" in its place. | A later decision. |
| L7 | Try "Draft it with PayAI" on payobook (uses AI credit); scanned PDFs need a provider that reads them. | §7 items 1–2. |
| L7 | Older portal words still English for Vietnamese readers ("Your training", the late alarm, "Lesson 1 of 3"). | Say if you want a follow-up to translate them. |

Closed along the way: Talent's empty tab for training-only roles (L1), certificates expired before go-live (LD10), double reminders
(LD10, revisit on complaint), Vietnam group 4 (LD11), Help listing the tabs (L6), the "could not load" panel (L6), "80%%" (L6).

### Deliberately left out

- **SCORM packages** — this build has no SCORM player; bought courses arrive as videos, documents or links, or as an outside course.
- **An offline / native app** (LD7) — lessons keep their place and their answers, but nothing is stored for reading offline.
- **Practical sign-off on a phone** (LD5).
- **Leaderboards, points, karma or ranking colleagues** (LD8) — badges are private medals; the stock karma and leaderboard pages stay blocked.
- **Paid course catalogues** (Go1, Udemy, LinkedIn — LD6) — the outside-course list is our own.
- **PayAI publishing anything** (LD9) — it drafts; a trainer reads, edits and publishes.
- **Vietnamese email bodies** (LD10) — English for now.
