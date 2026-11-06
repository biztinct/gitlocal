# LEARNING L7 — The learner's phone

Programme: LEARNING. Design page `docs/design/rize-learning-blueprint.html` §5 "My learning",
§7 phase L7, §8 decisions 6–8. Ledger binding. Predecessors L0–L6 reports.

**DECIDED 2026-10-22: LD7, LD8, LD9 all as recommended below — build §3 as written.** **Owner decisions asked at launch:** LD7 phone depth (recommended: phone-first pages that
keep their place when the signal drops; no native/offline app), LD8 badges (recommended: a
badge on each certificate and a streak on My learning; no leaderboards), LD9 PayAI drafting
(recommended: yes, drafts only, a trainer publishes). SCORM import is **out**: stock Odoo 19
has no SCORM player and no package format (F7); record as an owner item ("bought courses
arrive as video/PDF/links, or through an outside-course entry").

Report back to `docs/handovers/learning/L7_REPORT.md`.

## 1. Scope
1. **Lesson player on a phone** (§3.1): a small plain-JS layer on the portal lesson page:
   remembers the place (scroll, video time) per lesson; "Mark as done" and quiz answers go
   by fetch with an offline queue that replays when the signal returns; full-page fallback
   without JS; thumb-sized controls; a home-screen manifest for `/my/training`.
2. **Micro-lessons** (§3.2): a "Three minutes today" card that picks one short unfinished
   lesson; courses flagged "short lessons".
3. **"Next for you"** (§3.3): one rule engine behind the hero on My learning and the portal.
4. **Badges and streaks** (LD8, §3.4): badge image on the certificate wallet; on-time streak.
5. **Both languages** (§3.5): a lesson page toggle showing EN and VI content together when
   the lesson has a translation; the course editor shows which lessons lack one.
6. **PayAI drafts a course** (LD9, §3.6): upload a procedure (PDF/DOCX/text) on "New course"
   → PayAI returns an outline, lessons and a ten-question quiz → a draft, unpublished course;
   the trainer edits and publishes. Never auto-published.
7. Lessons in Help updated for the new learner screens (R7). Tests, demo, deploy.

**Binding non-goals.** No native app, no service worker caching of content, no SCORM, no
leaderboards or karma pages (stay blocked), no AI publishing, no outside AI call without a
configured provider, no face/biometrics.

## 2. Verified plumbing facts
| # | Fact | Where |
|---|---|---|
| F1 | Lesson page `portal_training_lesson` (`portal_templates.xml:620-781`): stage renders embed/pdf iframe/image/article by type (:662-686), quiz form radios `q<id>` + hidden `next_id` (:689-721), foot with prev/next, "Mark as done" POST form (:738-750). Content from `pb_my_training.py:392-409` (video `embed_code`, document `/slides/slide/<id>/pdf_content`, infographic `get_image`, article `html_content`), questions :411-418. Routes GET `/my/training/<c>/<s>` (:197-216), POST `/done` (:218-240, refuses lessons with questions), POST `/quiz` (:242-282, server-graded). **No JS on the portal**: `web.assets_frontend` lists only `portal_training.scss` (`__manifest__.py:150-152`). | `pb_training` |
| F2 | PWA precedent: `pb_driver_checkin` manifest route `/driver/manifest.webmanifest` + service worker via mixin `biz_geo_tracking/controllers/pwa_shell.py` (`_make_manifest` :14, `_make_service_worker` :34); page avoids asset bundles; offline queue in localStorage (`driver_app.js:64-65, 133-153`). `biz_deroute/static/src/js/deroute_sw.js` only unregisters `/odoo`-scoped workers. | |
| F3 | Bilingual: `slide.slide.name/description/html_content` are translated fields (`slide_slide.py:49-111`), channel `name/description/description_html` too; portal language = URL lang → `frontend_lang` cookie → context → website default (`http_routing/models/ir_http.py:361-364`). `pb_learn` switches languages (`{en, vi}` pairs, `tx()` `runtime.js:96`) and never shows both, except one key-value line (`screens.js:2380`). | |
| F4 | Badges: `gamification.badge` / `gamification.badge.user` installed via `website_profile`; course karma fields (`slide_channel.py:182-188`); `survey.survey.certification_badge_id` + `certification_give_badge` (:142-144); L0 gate blocks profile / leaderboard / ranks pages (`slides_gate.py:162-174`). `pb.training.certificate` has no badge reference. | |
| F5 | Recommendations precedent: `pb_learn/models/learn_runtime.py choose_next()` (:134-222): five ordered rules, first match wins, each returns `(key, kind, line, reason_key)`; `next_best()` :536-590 behind a flag, returns `{key, kind, line, reason_key, reason:{en,vi}}`. pb_training has only per-course `next_slide_id` (`pb_my_training.py:142-148`). | |
| F6 | PayAI: actions registry `pb_payai_actions/payai/registry.py` (`@payai_action`, `Action` attrs `key, title, tier, summary, examples, slots, screen_keys, door_id, phrases(_vi), priority`, methods `method_gate, param_gate, preview, execute, undo`; tiers look/prepare/decide/blocked; `tools_schema` strings only); example `actions_green.py:106-117`. Provider: `payroll.ai.config` (`provider_type` openai/anthropic/ollama/tesseract, `purpose` insights/doc_ocr, `get_config_for_purpose`), base provider `generate_text/chat/structured/tools/vision`, `accepts_pdf`. **The chat has no file upload.** Extraction precedent `biz_doc_ocr/models/biz_doc_ocr.py _extract(schema, attachment_ids, post_processor)` (:26, private, doc_ocr provider via `generate_vision`, deterministic fallback). Rulings PA-R1–R5 (no sudo inside an Action, server resolves ids, plain English), PA19 doors = navigation only, PA54 revert `vi_VN.po`/`fixture.js` after regen, PA58 `.pot` entries; LN5 no Access content. | |
| F7 | SCORM: nothing in the repo or stock Odoo 19 (`slide_category` = infographic/article/document/video/quiz). | |
| F8 | Phone rules: NAV R5 (< 768 px horizontal rail strip); `.pbme` breakpoints 768 ("the phone surface"), 700, 560; `portal_training.scss` breakpoints 860/700/640/680/560; portal light-only. | |

## 3. Architecture
### 3.1 Phone lesson player (`pb_training/static/src/js/portal_lesson.js`, added to `web.assets_frontend`; progressive enhancement)
- On load: restore `scrollY` and `<video>`/embed time from `localStorage['pbtr.lesson.<id>']`
  (YouTube/Vimeo embeds: store only scroll; local video: `currentTime`). Save every 5 s and
  on `visibilitychange`.
- "Mark as done" and quiz submit: intercept the forms; POST the same route via `fetch`
  (`X-Requested-With`, csrf token); on success render the server's JSON (`{ok, next_url,
  result, chosen}` — the two routes gain a JSON branch when the header is present, the HTML
  branch stays); on network failure push `{route, body, at}` into `localStorage
  ['pbtr.queue']` (cap 50), show a quiet banner "Saved on your phone. It will send when you
  are back online.", and replay on `online` and on the next page load (oldest first, stop at
  the first failure). Replayed quiz answers are graded then; the result shows on the course
  page ("Sent while you were offline: passed").
- Thumb layer: foot buttons 48 px, the stage never traps the scroll, document iframe gets a
  "Open the file" link for phones that block iframes.
- Home-screen manifest: route `/my/training/manifest.webmanifest` from the pwa_shell mixin
  (name "My training", start_url `/my/training`, icon = the Payobook icon); **no service
  worker** (LD7). Link it from the portal training pages' `<head>` via the layout hook.

### 3.2 Micro-lessons
- `slide.channel.pb_short` Boolean ("Short lessons, 3–5 minutes each"); `pb.my.training.
  three_minutes()` picks the shortest unfinished lesson (≤ 5 min by `completion_time`, else
  the shortest) across the person's open courses; My learning and portal show the card
  "Three minutes today · <lesson> · Start" under the hero; hidden when nothing fits.

### 3.3 Next for you (`pb.my.training.next_best()`)
Ordered rules, first match wins, each returning `{kind, title, line, url, reason_key,
reason}` (EN/VI words): overdue step or course → path current step → renewal due within
30 days → required training missing (L2) → sign-off pending (L4, "Ask your supervisor") →
course in progress nearest to done → booked session today/tomorrow → feedback waiting →
three-minute lesson → nothing ("Nothing to do right now."). Used by the My learning hero
(L0) and the portal hero; a test asserts the order.

### 3.4 Badges and streaks (LD8)
- Certificate badge: a drawn SVG badge (Lucide award + course initials, brand colour) on the
  wallet card and in the certificate mail; no `gamification.badge.user` rows (keeps the
  blocked pages irrelevant). Streak: `pb.my.training.streak()` = consecutive assignments
  finished on or before their due date, shown as "3 in a row, on time" on My learning;
  resets on a late finish; never shown to others.

### 3.5 Both languages
- Lesson page toggle "Show both languages" (remembered in localStorage): the server returns
  `html_content` and `name` in both `en_US` and `vi_VN` (`with_context(lang=…)`) when the
  translation differs; render stacked with a thin divider and language chips. Course editor
  (Courses lens course page) shows a "Missing Vietnamese" chip per lesson for trainers.

### 3.6 PayAI drafts a course (LD9; module `pb_training_payai`, auto_install with `pb_payai_actions` + `pb_training`)
- "New course" drawer gains "Draft it with PayAI from a document": file input (PDF/DOCX/
  TXT, 10 MB, bounded read) → facade `pb.training.draft_course(attachment_id, language)`
  (training groups; runs as the user, no sudo on business data): text extraction (PDF via the
  doc_ocr provider's `accepts_pdf`/`generate_vision` path as `biz_doc_ocr._extract` does;
  DOCX via `python-docx` if installed, else "Save it as PDF first"; TXT direct) → provider
  `generate_structured` with schema `{title, blurb, lessons:[{title, html, minutes}] (3–8),
  quiz:[{question, options:[4], correct}] (10)}` in the chosen language → creates an
  **unpublished** `slide.channel` (`channel_type='training'`, `visibility='members'`,
  `enroll='invite'`, `pb_draft_source=attachment`) with article lessons and one quiz lesson
  → opens the course page with the banner "Drafted by PayAI from <file>. Read every lesson
  before you publish." No provider configured → "PayAI is not set up for documents yet. Ask
  the administrator to add a provider under Settings › PayAI." Audit line in the course
  chatter with the file name and the model used.
- Also a PayAI action (tier **prepare**) `draft_course` whose slot is the file name of a
  document already in the course's attachments; it only opens the drawer pre-filled (PA19:
  doors are navigation) — the actual draft runs from the drawer.

## 4. Safety rails
Ledger L1–L8; no sudo on business data in the AI path; never publish from AI; the offline
queue holds only lesson ids and answers (no personal data beyond that); localStorage reads
wrapped in try/catch; the JS must not break when the bundle is absent (page still works).
Commits: (a) player + manifest; (b) micro + next-best + streak/badge; (c) both languages;
(d) PayAI draft module; (e) Help lessons + demo + docs.

## 5. Tests
- **T1** JSON branches of `/done` and `/quiz` (header present) return `{ok, next_url}` / `{result}`; HTML branch unchanged.
- **T2** queue replay order and stop-at-first-failure (JS unit test with a fake fetch, in the repo's JS test runner as pb_learn uses).
- **T3** `three_minutes()` picks ≤ 5 min first; none → `None`.
- **T4** `next_best()` rule order with fixtures for each rule; EN/VI reason words.
- **T5** streak counts on-time finishes only; resets.
- **T6** both-languages payload only when the translation differs; toggle state.
- **T7** draft_course: fake provider returns the schema → unpublished course with N lessons + quiz; no provider → plain error; a DOCX without python-docx → the "save as PDF" sentence; non-training user → AccessError; never sudo on the attachment read for a file the user cannot read.
- **T8** PayAI action registers with tier prepare and opens the drawer only.
- **T9** manifest route returns valid JSON with the right start_url; no service worker registered.
- **T10** no "Odoo", no emoji; VI.
- **T11** Chrome walk on a phone-sized window: lesson resume after reload, mark done offline (devtools offline) then replay, quiz offline, three-minute card, next-for-you hero, badge on wallet, both-languages toggle, PayAI draft end-to-end with the configured provider on payobook (if present) else the honest message; console clean.

## 6. Deploy
`pb_training` next minor; new module `pb_training_payai` → risky tier for the install;
usual ritual; stop at the deploy gate.
