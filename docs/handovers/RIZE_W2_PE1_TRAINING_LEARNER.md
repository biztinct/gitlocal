# RIZE Wave 2 — Phase E1: `pb_training` learner flow (the owner checkpoint phase)

Owner approved the Wave 2 blueprint on 2026-09-15 including **D15: install the
Surveys test engine on the live `payobook` database** — this phase is the one
module install of the wave and it is pre-authorised by that approval. E1 ends
at an **owner checkpoint**: the owner looks at the learner flow before E2/E3 are
designed. Build it to be looked at.

Read first, in order: `docs/handovers/RIZE_LEDGER.md` (all), then
`docs/handovers/RIZE_W2_HANDOVER.md` Parts A, B and C5, then this file. Facts
marked **verified** were checked 2026-09-15 on the live box — do not re-derive.

---

## 0. Scope and binding non-goals

**In scope (E1):**
1. Install `survey` + `website_slides_survey` on `payobook` (D15). Nothing
   else is installed or uninstalled.
2. Module `pb_training` (new, `19.0.1.0.0`): the employee's own training pages
   under `/my/training` — my courses, a course, a lesson (video / document /
   article / image / quiz rendered on OUR page), "Mark as done", the test that
   unlocks only when every lesson is done, the score shown immediately, the
   certificate download.
3. Gate the stock E-Learning pages (`/slides…` listing, course and lesson pages,
   `/profile…`) to internal users; content-serving routes stay.
4. **White-label sweep** of everything an employee can now reach: the survey
   page, the certification PDF, the survey and course mail templates, the
   stock strings the debrand seams do not already rewrite.
5. The **Learn hub**: ONE additive edit to `pb_learn` — a `HubShell` around the
   existing lessons journey with a soft lens registry `LEARN_LENSES`
   (the R73/R83/R96/R119 pattern), test-enforced; `pb_training` bolts its HR
   **Training** lens on (courses, tests, people, enrol) at sequence 20.
6. A minimal "Enrol people" door (needed to test the flow; E2's assignments sit
   on top of it), ⌘K rows in the **3900** block, switches, tests, deploy,
   Chrome validation light + dark, screenshots for the owner.

**Binding non-goals (E2/E3 own these):** assignments with due dates and
reasons (mandatory / probation / compliance / ad hoc), reminders and
escalation, delay reasons, the probation-gate adapter over
`pb.training.item`, recurring schedules, budget claims → pay run, analytics,
the report pack, certificates into the vault. Do not touch `pb_probation`.
Do not rebuild a video player or a quiz engine — render what E-Learning holds.
`pb_learn` (product lessons) keeps its content and behaviour; only its shell
changes.

---

## 1. Verified plumbing facts

### 1.1 E-Learning (`website_slides`, installed) — server files `/odoo/odoo-server/addons/website_slides/`
- `slide.channel` (`models/slide_channel.py:21`): `channel_type` (:66,
  training/documentation), `slide_ids` / `slide_content_ids` (:77-78),
  `nbr_*` counts (:96-100), `total_time` (:104), `completed_template_id`
  (:123, the stock "course completed" mail — set it False on courses you
  create in tests), `enroll` (:127 public/invite/payment), `visibility` (:136
  public/connected/members), `members_completed_count` (:160), `completed`
  (:168, current user), karma fields (:183-188).
  `_action_add_members(target_partners, member_status='joined',
  raise_on_access=False)` (:694) — enrol; `_remove_membership(partner_ids)`
  (:816).
- `slide.channel.partner` (`slide_channel_partner.py:6`): `member_status`
  invited/joined/ongoing/completed (:13), `completion` % (:19),
  `completed_slides_count` (:20), `partner_id` (:21), `next_slide_id` (:29),
  `_recompute_completion()` (:88).
- `slide.slide` (`slide_slide.py:24`): `slide_category` (:87 infographic /
  document / article / video / quiz — plus `certification` once
  `website_slides_survey` is in), `slide_type` (:117 image/article/quiz/pdf/
  sheet/doc/slides/youtube_video/google_drive_video/vimeo_video),
  `source_type` (:95 local_file/external), `url` (:100), `binary_content`
  (:101), `html_content` (:107), `question_ids` (:76, `slide.question` →
  `slide.answer.is_correct`), `is_published` (:170), `is_category`,
  `completion_time` (:58). Completion API: `action_set_viewed()` /
  `_action_set_viewed(target_partner)` (:805/:811) creates the
  `slide.slide.partner` row; `action_mark_completed()` (:830, requires
  membership via `can_self_mark_completed`) → `_action_mark_completed()`
  (:836, uses `env.user.partner_id`, calls `_action_set_quiz_done`, writes
  `completed=True` under sudo). Call it `with_user(session user)` after
  enrolment. Verify whether an `embed_code` field exists on this build
  (grep `embed_code`); if not, build the video iframe from `url` +
  `slide_type` (`YOUTUBE_VIDEO_ID_REGEX` :43, `VIMEO_VIDEO_ID_REGEX` :45) —
  `slide_embed.py` and the `/slides/embed/<id>` route are the fallback.
- `slide.slide.partner` (`slide_slide_partner.py:5`): `completed` (:17),
  `quiz_attempts_count` (:18), `vote`.
- Routes (`controllers/main.py`): listing `/slides` (:402), `/slides/all`
  and course page (:521), `/slides/<channel_id>/invite` (:800), lesson
  `/slides/slide/<slide>` (:970), **content-serving** `/slides/slide/<slide>/pdf_content`
  (:1034), `/slides/slide/<id>/get_image` (:1042), `get_html_content` (:1059),
  `set_completed` (:1068/:1077), quiz `get`/`submit`/`reset` (:1244-1262).
  Live: **`/slides` answers 200 to the public today** (curl with the Host
  header) — the gate in §3.3 closes that.
- Live data: 7 stock demo courses (Gardening / Furniture …, ids 1-7, mixed
  visibility, published), 40-ish slides, 12 memberships. Two `website` rows
  (1 and 2, both "Payobook"). 46 internal users; everybody else is portal.
- Groups: `website_slides.group_website_slides_officer`,
  `website_slides.group_website_slides_manager`; the validator holds both.

### 1.2 Surveys (`survey`, NOT installed; files present on the server) + `website_slides_survey` (auto_install, depends `website_slides`,`survey`)
- `survey.survey` (`survey/models/survey_survey.py:19`): `survey_type` (:39),
  `questions_layout` (:75), `access_mode` (:92 public/token),
  `users_login_required` (:97), `scoring_type` (:108 no_scoring /
  scoring_with_answers / scoring_without_answers / …), `scoring_success_min`
  (:114, default 80), `is_attempts_limited` / `attempts_limit` (:117-119),
  `is_time_limited` / `time_limit` (:120-121), `certification` (:123),
  `certification_mail_template_id` (:125), `certification_report_layout`
  (:129), `certification_give_badge` (:142). Constraint: a certification needs
  a scoring type (:181).
  `_create_answer(user=, partner=, email=, test_entry=, check_attempts=,
  **additional_vals)` (:535) — the door to an attempt; `get_start_url()`
  (:1177). `survey.user_input` (`survey_user_input.py:19`): `access_token`
  (:45), `partner_id` (:47), `state` (:32 new/in_progress/done),
  `scoring_percentage` (:53), `scoring_success` (:55), `deadline` (:30),
  `get_start_url()` (:268 → `<survey start url>?answer_token=…`),
  `get_print_url()` (:272). `survey.question` (`survey_question.py:45`):
  `is_page` (:77), `random_questions_count` (:82, the question-bank draw),
  `question_type` (:87), `answer_score` (:108).
- Routes (`survey/controllers/main.py`): `/survey/start/<survey_token>`
  (:209, auth public), begin/next/submit jsonrpc (:490-521), `/survey/print/…`
  (:662), **`/survey/<int:survey_id>/get_certification`** (:704, auth user —
  portal users are users), `/survey/results/…` (:731, internal).
- `website_slides_survey`: `slide.slide.slide_category += certification`,
  `slide.slide.survey_id` (`models/slide_slide.py:49-55`);
  `slide.slide.partner.user_input_ids` + `survey_scoring_success` (:10-11);
  `survey.user_input.slide_id` / `slide_partner_id` (`survey_user.py:9-11`).
  Passing the certification slide's survey marks the slide complete (:33-42).
- Depends of `survey`: `auth_signup`, `http_routing`, `mail`, `web_tour`,
  `gamification` (all installed). Install = `-i survey,website_slides_survey`.
  The survey app adds a backend "Surveys" menu; the Payobook shell hides
  native app menus — verify no stray door appears for a portal user.

### 1.3 The Learn mission today
- Rail item `pb_learn.item_learn_journey` (`pb_learn/data/learn_sidebar_item.xml:16`,
  section `sec_learn` seq 40): `action_xmlid pb_learn.action_learn_journey`,
  `action_tag learn_journey`, `match_action_tags learn_journey`, icon
  `book-open`. Client action `learn_journey` (`pb_learn/views/learn_actions.xml:9`);
  component `LearnJourney` (`pb_learn/static/src/journey/journey.js:76`,
  `static props = ["*"]`, template `pb_learn.Journey`). It is NOT a hub.
- `pb_sidebar/tests/test_ia_c5.py` pins the rail: `('pb_learn.item_learn_journey',
  10, 'book-open', 'Learn')` (:50), tags `['learn_journey']` (:142) and the
  probe `('the learn journey', dict(tag='learn_journey'), 'Learn')` (:543) —
  update all three in the same change.
- HubShell contract: `pb_hub/static/src/js/hub_shell.js:57-83` (config
  `{key, brand, feature?, lenses:[{key, icon, label, Component, groups,
  props?}], cog?, defaultLens?}`); a clone of a hub with a soft registry:
  `pb_lifecycle/static/src/js/lifecycle_hub.js:58-95`.

### 1.4 Portal, mail, deploy, actors
- Portal precedent: `pb_offboarding/controllers/portal.py` (route = gate,
  session employee, sudo after proof, `_prepare_home_portal_values`) and its
  home card `views/portal_templates.xml:46` with an eager key (R62). `.pbme`
  kit classes: `pbme-hero`, `pbme-tiles`/`pbme-tile`, `pbme-card`, `pbme-kv`,
  `pbme-lines`, `pbme-empty`, `pbme-eyebrow`, `pbme-num`, `pbme-pager`
  (`pb_me_portal/static/src/scss/me_portal.scss`). Frontend bundle only,
  literal colour fallbacks (R39), `t-attf-class` (R42), no `t-key` (R5), no
  render key `request` (R4).
- Debrand: `biz_debrand/models/ir_ui_view.py:27 _get_view_etrees` rewrites
  the brand in every server-rendered QWeb view; mail bodies are scrubbed at
  send by `biz_mail_debrand`. What it does NOT cover: strings in `.py`
  (`_()` in controllers/models), PDF report layouts rendered from data
  records, `mail.template` subjects. Sweep those.
- Mail: explicit `email_to` (R6), `mail.mail` assertions, cancel test rows
  (R37/R47), `@example.com`/`@payobook.com` demo addresses only.
- Deploy: ledger ritual; `-i survey,website_slides_survey,pb_training -u
  pb_learn`; asset check per R116; registry check in the browser
  (`registry.category("pb_learn_lens")`, `("pb_hub_palette")`).
- Actors: admin `igc1.validator` / `RizeP0!2026` (uid 2065, holds E-Learning
  manager + officer); learner `ess1.demo@payobook.com` (uid 1984, employee
  10080, company 5, PORTAL user — re-set password to `RizeP7!2026`, R74);
  manager view later (E2). Test data stays, named "DEMO …" (D18, ledger rule 9).

---

## 2. Architecture

```
pb_learn (additive edit, own commit, version bump 19.0.x+1)
  static/src/hub/learn_hub.js      LearnHub extends Component, HubShell config
                                   {key:"learn", brand:{label:"Learn", icon:"bookOpen"},
                                    defaultLens:"lessons",
                                    lenses:[{key:"lessons", icon:"bookOpen", label:"Lessons",
                                             Component: LearnJourney}, ...extraLenses()]}
                                   export const LEARN_LENSES = "pb_learn_lens"
  static/src/hub/learn_hub.xml     <HubShell config="config"/>
  views/learn_actions.xml          + ir.actions.client tag "learn_hub", name "Learn"
  data/learn_sidebar_item.xml      item → action_xmlid pb_learn.action_learn_hub,
                                   action_tag learn_hub, match_action_tags "learn_hub,learn_journey"
  tests/test_learn_hub.py          the soft-registry test (clone pb_home_hub's)
  + pb_sidebar/tests/test_ia_c5.py :50/:142/:543 updated

pb_training/
  __manifest__.py   depends: base, hr, mail, portal, website, website_slides,
                    survey, website_slides_survey, pb_hub, pb_import_kit,
                    pb_me_portal, pb_learn
  hooks.py          post_init_hook: white-label sweep of the mail templates
                    (§3.4) — idempotent, logged
  models/
    training_common.py     counted(), fold() (R78), _as_employee(), _partner_for()
    pb_training.py         AbstractModel facade for the HR lens (board + enrol)
    pb_my_training.py      AbstractModel: the learner's reads/writes (all sudo,
                           ownership proven by the caller) — ONE place, used by
                           the controller and by tests
    slide_channel_ext.py   pb_* helpers only (no field changes to stock models)
  controllers/
    portal.py              /my/training, /my/training/<channel>, /<channel>/<slide>,
                           /<channel>/<slide>/done, /<channel>/<slide>/quiz (POST),
                           /<channel>/test (start), /<channel>/certificate
    slides_gate.py         inherits website_slides' controller class; the
                           listing/course/lesson routes redirect non-internal
                           users to /my/training (switch)
  security/  pb_training_security.xml (ladder), ir.model.access.csv (facades need none;
             ACLs only for models you add — E1 adds none)
  data/      training_params.xml
  views/     portal_templates.xml (the learner pages), training_views.xml (ir.actions.client
             for the hub lens/board), skinned doors to slide.channel / survey.survey
  static/src/js  training_board.js, training_palette.js (LEARN_LENSES + ⌘K 3900)
  static/src/xml training_board.xml
  static/src/scss training.scss (backend), portal_training.scss (frontend)
  tests/     test_training.py + the standard gates (white-label incl. the stock
             strings the sweep touches; act_window views; nolabel colspan)
```

---

## 3. The rules (plain English on screen)

### 3.1 The learner's pages (`/my/training`)
- **My training** (`/my/training`): hero "Your training" with three numbers
  (courses in progress · finished · tests passed) and a tile per course the
  session employee's partner is a member of (`slide.channel.partner`,
  `member_status != 'invited'`, channel published): title, lessons done /
  total, a progress bar, "Continue" → next lesson (`next_slide_id`), a
  "Test" chip (locked / ready / passed N% / not passed N%). Empty state:
  "Nothing assigned to you yet. When HR enrols you on a course it appears
  here." Home card "My training · N courses" (eager key).
- **A course** (`/my/training/<channel_id>`): membership proven or 404-as-
  redirect with a sentence; description, the lesson list in order (published
  content slides that are not categories, grouped under their category
  headings), each with done/not-done, duration; the test card at the bottom:
  locked ("Finish every lesson first — 3 to go") until every non-certification
  published content slide is complete for this partner; then "Take the test"
  (attempts left, time limit if any, pass mark); after an attempt: score,
  pass/fail, "Try again" if attempts remain, "Download certificate" when
  `scoring_success`.
- **A lesson** (`/my/training/<channel_id>/<slide_id>`): OUR page. Render by
  `slide_type`: video → responsive iframe (YouTube nocookie / Vimeo player /
  Google Drive preview) from `url`; pdf/doc/sheet/slides → `<iframe>` on
  `/slides/slide/<id>/pdf_content` for local files, the Google preview URL
  for external; article → `html_content` (already sanitised by the field);
  image → `/slides/slide/<id>/get_image`; quiz → our form over
  `slide.question` / `slide.answer` (single choice per question), graded
  server-side against `is_correct`, wrong answers shown with "try again",
  all-correct marks the lesson done. "Mark as done" button (video / document
  / article / image) → `_action_set_viewed(partner)` then
  `slide.with_user(session user)._action_mark_completed()`, then
  `channel_partner._recompute_completion()`; redirect back to the course with
  the next lesson highlighted. Previous / next lesson links. Nothing here
  links to `/slides`.
- **The test**: "Take the test" → the certification slide's `survey_id`;
  `survey.sudo()._create_answer(user=session user, partner=…, slide_id=,
  slide_partner_id=)` → redirect to `user_input.get_start_url()`. The stock
  survey page runs under the website layout (this box's theme) — read it in
  Chrome as the learner, in light and dark, and fix wording through the
  sweep. When the survey is submitted the stock page shows the score
  immediately (`scoring_type = scoring_with_answers` on the test you create;
  set `users_login_required = True`, `access_mode = 'token'`,
  `is_attempts_limited = True`, `attempts_limit = 3`, `scoring_success_min
  = 70`, `certification = True`). Our course page reads the latest
  `survey.user_input` for (partner, survey) and shows score + state.
  `/my/training/<channel>/certificate` → redirect to
  `/survey/<survey_id>/get_certification` (auth user; works for portal).
- **Who is "me"**: the session user's partner (`request.env.user.partner_id`)
  is the membership key — E-Learning is partner-based; the employee record
  is read only for the name and company. Never accept a partner or employee
  id from the URL.

### 3.2 The HR lens (Learn → Training, backend, `pbim pbim-page pbtr`)
- Gate: `group_training_user`+ (ladder in §3.5). KPIs: courses · learners
  enrolled · finished this month · tests passed / taken. Course rows: title,
  type, lessons, has-test chip, members, average completion, published
  chip. Drawer: lessons in order with type icons, the test (pass mark,
  attempts), members with their % and test result, "Enrol people" (people
  picker folding accents R78, company-scoped, `_action_add_members`),
  "Remove", "Open the course" (native form, `'views'` R125), "Open the
  test" (native survey form), "See it as a learner" (opens
  `/my/training/<id>` in a new tab — an admin who is not a member sees the
  membership refusal sentence, which is correct; say so in the tooltip).
- Doors: "New course" (native `slide.channel` form), "New test" (native
  `survey.survey` form with `certification=True` default), "Question bank"
  (`survey.question` list, the sheet's question bank).
- Empty state teaches the three steps: make a course, add lessons and a
  test, enrol people.

### 3.3 The gate on stock pages
- `pb_training.stock_pages_internal_only` (default 1): in `slides_gate.py`
  override the listing (:402), all/course (:521), lesson (:970) and the
  `website_profile` user pages if present, so a user who is not
  `base.group_user` is redirected to `/my/training` (public visitors to
  `/web/login`). Content routes (`pdf_content`, `get_image`,
  `get_html_content`, embed, quiz jsonrpc) are NOT gated — the learner pages
  use them. Survey routes are NOT gated. Record the exact method names you
  overrode as an R-entry.

### 3.4 The white-label sweep
- After install, list every user-visible string an employee can reach:
  survey page templates, certification PDF layouts (`survey/report/*.xml`),
  `mail.template` rows from `survey` and `website_slides` (subject + body),
  `survey.survey` / `slide.channel` demo data names, the "Powered by"
  footer, the `web_tour` hints. For each: if `biz_debrand` already rewrites
  it at render (prove with a rendered page as the learner), leave it; else
  fix it (`post_init_hook` writes over the seeded row — data rows, not
  views; R57 for noupdate; keep the list in the hook's docstring and in the
  report). The gate test greps the module's own strings; add one that
  renders `/survey/start/<token>` as the learner and asserts "Odoo" is
  absent.
- Stock demo courses (ids 1-7): leave them (demo DB, D9) but make sure
  none is `visibility = 'public'` after the gate — set them to `connected`
  with a note in the report.

### 3.5 Groups, switches, palette
- Ladder: `group_training_user` (implies
  `website_slides.group_website_slides_officer` + `survey.group_survey_user`),
  `group_training_manager` (implies user + `website_slides.group_website_slides_manager`
  + `survey.group_survey_manager`), `group_training_admin`. Verify the survey
  group xmlids after install (`survey/security/`). Privilege name without
  `&` (R124).
- Switches (`data/training_params.xml`): `pb_training.stock_pages_internal_only`
  = 1; `pb_training.completion_mail` = 0 (documented: the stock per-course
  "completed" mail is `slide.channel.completed_template_id` — the facade's
  "New course" sets it False while the switch is 0).
- LEARN lens: `registry.category(LEARN_LENSES).add("training", {key, icon:
  "graduationCap" (add to `ic()` if missing — camelCase, in pb_import_kit),
  label: "Training", Component, groups}, {sequence: 20})`. Label 8 chars
  (R63 — measure).
- ⌘K block **3900**: `training_board` 3900 ("Training", Learn),
  `training_courses` 3910 ("Courses"), `training_tests` 3920 ("Tests and
  question bank"), `training_my` 3930 ("My training" → opens `/my/training`
  in the browser; the palette contract needs a door — check whether a URL
  door exists (`action: {url}`); if not, skip 3930 and say so).

---

## 4. Numbered tests

T1  Install on a clean test DB: `survey`, `website_slides_survey`,
    `pb_training` install; `pb_learn` upgrades; `learn_hub` action exists;
    `pb_sidebar` tests pass with the updated TARGET_RAIL; the gates pass.
T2  Learn hub in the browser as the validator: rail "Learn" opens the hub on
    the Lessons lens and the lessons journey renders exactly as before
    (compare a screenshot to a pre-change one); the Training lens is
    offered to the validator and absent for a user without the group.
T3  Create "DEMO Agronomist basics" (company 5, `visibility='members'`,
    `enroll='invite'`, `completed_template_id=False`): a YouTube video
    lesson, a PDF lesson (small local file), an article, a quiz (2
    questions), and a certification lesson on a new survey "DEMO
    Agronomist basics — test" (3 scored single-choice questions, pass 70,
    3 attempts, certification). Enrol ess1.demo (employee 10080) through
    the HR lens "Enrol people" (accent-folded search "dem" finds them).
T4  `/my/training` as ess1.demo: the course tile shows 0/4 lessons, test
    locked; the home card says "My training · 1 course".
T5  Lesson pages: video iframe present with the right embed host; PDF
    iframe loads `pdf_content` (HTTP 200 as the learner); article shows
    `html_content`; each "Mark as done" creates/updates the
    `slide.slide.partner` row and `channel_partner.completion` moves
    (assert the numbers after each).
T6  Quiz: a wrong answer returns the form with the wrong ones marked and the
    lesson NOT done; all correct marks it done.
T7  Test unlocks only when 4/4: with one lesson undone the "Take the test"
    POST is refused with the sentence; when done it creates a
    `survey.user_input` linked to the slide partner and redirects to
    `/survey/start/...?answer_token=...`; the page renders for the learner
    (200, no "Odoo" in the HTML).
T8  Submit the test through the survey JSON routes as the learner (mirror
    `begin` → `submit`): score ≥ 70 → `scoring_success`, the certification
    slide completes, `channel_partner.member_status = 'completed'`; the
    course page shows the score and "Download certificate";
    `/my/training/<id>/certificate` answers a PDF (200,
    `application/pdf`). A second learner failing (< 70) sees "not passed,
    2 attempts left".
T9  Stock gate: as ess1.demo `/slides`, `/slides/all`, `/slides/<id>`,
    `/slides/slide/<id>` → 303 to `/my/training`; as the validator they
    still open; `/slides/slide/<id>/pdf_content` still 200 for the enrolled
    learner; with the switch 0 the gate is off.
T10 A learner who is NOT a member: `/my/training/<id>` → redirect with the
    sentence; a forged `slide_id` from another course → the same.
T11 White-label: render as the learner `/my/training`, the course, a lesson,
    the survey start page, the survey result page, the certificate PDF
    text, and the two mail templates' rendered bodies → grep "Odoo" = 0;
    list what the hook changed.
T12 Portal dark check = every colour resolves (R39); backend lens light +
    dark screenshots; no red style bar; `unhandledrejection` listener on
    every door.
T13 ⌘K rows 3900–3920 (3930 if a URL door exists) present; `pb_learn_lens`
    holds `training` at 20; "Training" label fits.
T14 Passwords re-set to ledger values; group grants reverted against a
    snapshot; demo courses' visibility change noted; test data stays, named
    DEMO (ledger rule 9).

---

## 5. Deploy and the checkpoint
Ledger ritual. `-i survey,website_slides_survey,pb_training -u pb_learn`
on `payobook` only. Verify: module states + versions, the served bundle
contains `.pbtr` and the Learn hub, `/my/training` as ess1.demo, `/slides`
redirects, `/survey/start` renders for the learner. **Save screenshots**
`RIZE/w2_e1_*.png` (my training, course, lesson, quiz, test start, test
result, certificate, HR lens light/dark) — the owner looks at these.

## 6. Report back
Commits (pb_learn hub as its own commit first); per-test results; deploy
verdict; the sweep list (what was branded, what was changed, what the seams
already covered); the exact stock controller methods overridden; deviations;
palette rows; registry names; **API for E2/E3**: `pb.my.training` reads
(`courses_for(partner)`, `course(channel, partner)`, `mark_done(...)`,
`start_test(...)`), the enrol helper signature, how "every lesson done" is
computed, the survey link fields; test accounts; switches; new R-entries;
the ledger's Wave 2 table row for E1; the owner's checkpoint items (what to
look at and where).

## Demo-data rule (owner, 2026-09-16 — D18, ledger binding rule 9)
Every demo record this phase creates on `payobook` is KEPT for future demos, so it
must NOT carry the customer name ("RIZE"/"Rize") anywhere a viewer can see — names,
subjects, notes, chatter, logins, emails, job/department titles, letter bodies. Name
them starting with **DEMO** ("DEMO Town hall"), logins `demo.<role>@example.com`.
Register every one at creation, in the fixture code:
`seed = self.env.get('pb.demo.seed'); if seed is not None: seed.register(records, label)`
(the guard keeps `pb_demo_seed` optional on tenants). The report carries a "Demo
records" table (model, ids, label) and the register count. Any "named RIZE W2" wording
left in this file is superseded by this section.
