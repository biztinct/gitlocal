# LEARNING L0 — The Learning menu

Programme: LEARNING (Rize L&D as its own top-level menu). Design page
`docs/design/rize-learning-blueprint.html` (§1 rail mock, §5 screens, §9 engineering notes).
Ledger: `docs/handovers/learning/LEARNING_LEDGER.md` — rows L1–L8 (standing rules), LD1–LD3
(owner decisions), LN1–LN5 (facts). Read the ledger first; it is binding. NAV programme
rows cited below live in `docs/handovers/NAV_LEDGER.md` (R1–R14) and the new-hub precedent in
`docs/handovers/NAV_P2_REGROUP.md` A8–A13 and B1–B8.

Report back to `docs/handovers/learning/L0_REPORT.md` (template in §9).

## 1. Scope

**Goal.** A new top-level left-menu entry **Learning** (VI **Học tập**) in the Grow section,
with its own HubShell rail of eight lenses, holding everything that today sits on the
Talent › Training tab plus a "My learning" lens for every staff member. The Talent hub loses
its TRAINING tab. The product-guide entry `pb_learn` is renamed from "Learn" to **Help**
(VI **Trợ giúp**). Nothing is rebuilt; everything is re-homed, and two small new surfaces
(Overview, My learning) are built from existing data.

**In scope.**
1. New module `pb_learning_hub` (clone of `pb_talent_hub`): action tag `pb_learning_hub`,
   xmlid `pb_learning_hub.action_pb_learning_hub`, registry
   `LEARNING_LENSES = "pb_learning_hub_lens"`, sidebar item `pb_learning_hub.item_learning`.
2. `pb_training` registers eight lenses into `LEARNING_LENSES` (§3) and stops registering
   into `TALENT_LENSES`. The six-tab Training board gains `startTab` and `tabs` props.
3. Two new lens components in `pb_training`: **Overview** and **My learning** (§4), each with
   one new `@api.model` facade method. One new verb: a one-tap **Remind** (§4.3).
4. `pb_talent_hub`: TRAINING lens gone; sidebar claims, blurb, icon and tests updated; an
   arrival on Talent asking for lens `training` redirects to the Learning hub (R10).
5. `pb_learn`: entry renamed "Help"; `hub_learning` screen for lessons; replicas and the
   practice menu updated; regenerated; version bumped (R7).
6. Sidebar plumbing: ICONS map gains two icons; `test_ia_c5.py` TARGET_RAIL and claims;
   `FEATURE_BY_TAG` and `hub_features.js` mirror; command-bar rows re-pointed.
7. Tests (§7), local Chrome walk, then a **risky-tier** deploy (new module install) on every
   active DB, gated by Fable (§8).

**Binding non-goals.** No new models or stored fields except the reminder stamp in §4.3. No
certificate register, paths, requirement matrix, sessions, sign-offs, outside courses,
feedback, skills, hours or cost (phases L1–L7). No change to the learner lesson pages under
`/my/training/…` beyond linking to them. No change to approval routes, mails or crons. No
redesign of the stock Tests/Question-bank list views (L5 does that; L0 wraps them). No new
lesson-opening tag or focus format and no Access tab on the Learning rail (ledger LN5).
Do not touch `pb_probation`, `pb_comp_ben`, `pb_employee_vault`, `pb_vendor_access`
(no SCREEN_GATES row: Learning is everybody's, like Home and Help — see §5.4).

## 2. Verified plumbing facts (do not re-derive)

| # | Fact | Where |
|---|---|---|
| F1 | HubShell lens shape: `{ key, icon, label, title?, groups?:[xmlid], probe?:{model,method}, feature?, Component?, props?, wantsArrival? }`. No seq/tag/action keys; order = registry `{sequence}`. A lens without `Component` shows "This lens has no surface yet." `lensProps = { embedded:true, ...def.props }`. | `pb_hub/static/src/js/hub_shell.js:68-93, 362-378`; `hub_shell.xml:130-152` |
| F2 | Add-on registry pattern `extraLenses()` (resolved once in `setup()`, never a getter — W21) and `HUB_LENS_GATES` registration. | `pb_talent_hub/static/src/js/talent_hub.js:58-65, 80-82`; `pb_hub/static/src/js/hub_gates.js:16-89` |
| F3 | Rail label: 9 px, 800 weight, uppercase, `-webkit-line-clamp:2`, width 64 px, words never break. Ten items by design, twelve max. Full name in `title`. The shell draws **no counts**; the Training board draws its own on inner tabs. | `pb_hub/static/src/scss/hub_shell.scss:216-296`; `hub_shell.xml:101`; `training_board.xml:95-121` |
| F4 | `pb_talent_hub` files: manifest (depends `pb_hub, pb_settings, pb_sidebar, pb_learn`; data `views/pb_talent_hub_action.xml`, `data/pb_sidebar.xml`; assets `talent_hub.js`, `talent_hub_palette.js`, `talent_hub.xml`; `post_init_hook` → `gate_menu`), `hooks.py` (30 lines), `i18n/vi_VN.po` (2 entries), `tests/test_talent_hub.py` (8 tests). Sidebar item quoted in the fact sheet: section `pb_learn.sec_learn`, groups `hr.group_hr_user`, icon `graduation-cap`, seq 5, `match_action_tags pb_talent_hub,pb_goals_board,pb_pip_board,pb_training_board,pb_rnr_board`, `match_models … pb.training,pb.training.assignment …`. | `pb_talent_hub/*` |
| F5 | Talent test `test_every_tab_registers_into_talent_and_not_its_old_hub` has `TABS` incl. `('pb_training','training_palette.js','training',30)` and asserts `pb_talent_hub` in pb_training's depends — must change. | `pb_talent_hub/tests/test_talent_hub.py:58` |
| F6 | `training_palette.js`: Talent lens `{key:"training", icon:"graduationCap", label:_t("Training"), Component: PbTrainingBoard, groups: TRAINING_GATE}` seq 30 (`:57-63`); `HUB_XMLID = "pb_talent_hub.action_pb_talent_hub"` (`:67`); command-bar rows `training_board` 3900 (sublabel "Talent", keywords `learn, đào tạo`), `training_courses` 3910, `training_tests` 3920, `training_my` 3930 (act_url `/my/training`, ungated), `training_assignments` 3940, `training_schedules` 3950, `training_claims` 3960, `training_numbers` 3970 (`requires:"pb_training_numbers"`); Insights lens `:158-164` seq 40. | `pb_training/static/src/js/training_palette.js` |
| F7 | `PbTrainingBoard`: `static props = ["*"]` (`:36`), `state.tab = "courses"` hard-coded (`:71`), `setTab(tab)` lazy-loads (`:362-371`), `onWillStart` only `load()` (`:130`) → `pb.training.get_board`. Tabs row `pbtn-tabs` at `training_board.xml:85-123`; keys `courses, assignments, requests, schedules, rules, claims` (labels Courses, Assignments, More time, Comes round again, Day one, Claims). Header title hidden when `props.embedded` (`:48`). | `pb_training/static/src/js/training_board.js`, `xml/training_board.xml` |
| F8 | `startTab` precedent: `pb_hiring/static/src/js/hiring_hub.js:79-93` registers the same component several times with `props:{startTab, placeLens}`; board honours it in `onWillStart` after load (`hiring_board.js:289-292`). | `pb_hiring` |
| F9 | `PbTrainingNumbers` exported from `@pb_training/js/training_numbers`, client action `pb_training_numbers` (`:230`), `props ["*"]`. Insights mounts it as `Component` directly. | `training_numbers.js`; `training_palette.js:158-164` |
| F10 | `pb.my.training` (AbstractModel, every public method `@api.model`, "me" = session user, no `_can_*` guard, works for internal users): `home()` → `{courses:[tile], in_progress, finished, passed, total, overdue, due_soon, manages}` with tile `{id, name, done, total, left, percent, finished, test, score, next_id, next_name, duration, assignment:{id, due, due_words, late, days_over, reason_word, state_word, can_ask, delay}}`; `i_manage_people()` bool; `team()` → `{manages, rows:[assignment payload], people, overdue, due, done}`; `claims(year)` → allowance words + rows; `certificate_url(channel_id)`; `ask_more_time(...)`. | `pb_training/models/pb_my_training.py:101-582`, `pb_my_training_due.py:114-247`, `pb_my_training_claims.py:39-117` |
| F11 | `pb.training.get_board` returns `{'allowed': False}` without a training group; board verbs go through `act()` with allow-list `_VERBS`. | `pb_training/models/pb_training.py:57-60, 92-94, 528` |
| F12 | Assignment reminder machinery: templates `assignment_due`, `assignment_overdue` in `data/mail_template_assignments.xml`; `reminder_log` field on `pb.training.assignment` (`assignment.py:61-131`); chase logic `automation.py:171-230`. | `pb_training` |
| F13 | Sidebar: `pb.sidebar.item` fields `name(translate), section_id, sequence, icon, action_xmlid, action_tag, badge, groups_id, match_action_xmlids, match_action_tags, match_models, restricted`. Match indexes are flat, last writer wins; `_resolveActive` checks xml_id, then tag, then res_model. Visibility: admin, or no groups, or any group held. | `pb_sidebar/models/pb_sidebar.py:31-107`; `static/src/js/pb_sidebar.js:311-374` |
| F14 | ICONS map is closed (`pb_sidebar.js:16-78`); unknown name draws a circle; test `test_every_rail_icon_exists_in_the_fixed_set` (`test_ia_c5.py:389`). Present: `graduation-cap` (:77, Talent), `book-open` (:61, Learn), `compass` (:35, Workforce). Absent: `life-buoy`, `help-circle`, `target`, `award`. | `pb_sidebar` |
| F15 | `test_ia_c5.py` TARGET_RAIL (`:31-58`) has Grow = `[('pb_talent_hub.item_talent',5,'graduation-cap','Talent'), ('pb_learn.item_learn_journey',10,'book-open','Learn')]`; uniqueness tests for models/tags/xmlids (`:443-489`); `MATCH_TAGS`/`MATCH_MODELS` (`:156-176`); label uniqueness (`:362`); highlight cases 'learn hub'→'Learn' (`:568-569`), 'Talent hub' (`:578`). | `pb_sidebar/tests/test_ia_c5.py` |
| F16 | `FEATURE_BY_TAG` (`pb_tenancy/models/pb_sidebar.py:61-79`) has `learn_hub: learn`, `learn_journey: learn`; Talent is absent on purpose (`:70`). JS mirror `pb_hub/static/src/js/hub_features.js:50-80`. | |
| F17 | `SCREEN_GATES` (`pb_vendor_access/hooks.py:778-809`): "Home and Learn are deliberately absent: they are everybody's." Talent row lists the training-* abilities. Access board Screens lens enumerates **all** `pb.sidebar.item` rows automatically (`biz_access/models/pb_access_facade.py:1841-1899`) — R8 needs no code. | |
| F18 | `pb_learn` is **generated**: sources are `docs/tutorial_poc/author/data.js` and `practice-data.js`; generator `python3 docs/tutorial_poc/author/tools/gen_learn_data.py` writes `learn_content.json`, `fixture.js`, anchors practice block, `learn_sidebar_item.xml`, `learn_tenant_slots.xml` and merges `vi_VN.po`. Recipe and checks: `docs/handovers/NAV_P2B_REPORT.md:107-120`. | |
| F19 | "Learn" sites: `SIDEBAR.leaf.name: B("Learn","Học cùng Payobook")` `data.js:15133`; `learn_hub.js:70` brand; `learn_palette.js:77,132` group; `views/learn_actions.xml:20-24` action name; `pb_hub/static/src/js/hub_palette_entries.js:220` `{id:"learn", label:"Learn", sublabel:"Guides", seq:170}`; journey top-bar `T("hubTitle")` `data.js:75`, `journey.js:2483-2486`; Chrome key `learn: "Learning"` top-bar suffix (VI "Học tập") `data.js:66-74, 15077-15111`; `contract.json:369` pins `"Learn": "Học cùng Payobook"`; `.po:324-329` `msgid "Learn"` → `"Học cùng Payobook"`; `msgid "Guide"` → `"Hướng dẫn"` already exists `:1037-1041`. Counts: data.js 31 lines "Learn", 3 "Learn ›", 12 "Học cùng Payobook"; "Eleven pages"/"mười một trang" at `data.js:1500-1501, 4356, 10826-10827`; `MENU_ORDER` `pb_learn/static/src/journey/library.js:33-45` and `library.test.mjs:112` asserts 11. | |
| F20 | Training in Learn content appears only as a tab name: `data.js:10002` (hub_insights), `:10050-10064` (hub_talent tabs goals/pip/training/praise), `:10081-10099` (hub_learn), `practice-data.js:2205, 2218-2235`, `fixture.js:2225-2240`. A hub-tab screen needs `SCREEN_ACTION_TAGS` in `gen_learn_data.py:97-197` (LR80). LR28: no English sentence over 28 words. | |
| F21 | Learn regeneration invariants (gitlocal-09): diff `vi_VN.po` — any removed or changed msgstr other than the intended rename is a regression; keep "gõ DUYỆT" = 1 in the Approvals lesson; keep action tag `pb_payruns` (LR80); 0 occurrences of "These figures do not add up". Owner VI words (VIFIX, not yet applied — do not introduce others): pay run "đợt lương", People "Nhân sự", Workforce "Chấm công". | |
| F22 | Versions now: `pb_learn 19.0.20.5.16`, `pb_training 19.0.1.3.0`, `pb_talent_hub 19.0.1.0.0`, `pb_sidebar 19.0.3.2.4`, `pb_tenancy 19.0.1.6.1`, `pb_hub 19.0.1.12.0`. NAV P3d (gitlocal-b6) is deploying `pb_ask_hr, pb_learn` ~15:00 AEDT and will push 19.1; pb_learn sources in the shared tree are theirs until then. | |
| F23 | Lens icon set `ic()` (`pb_import_kit/static/src/js/import_icons.js`) has `listChecks` (:337), `fileCheck` (:345), `graduationCap, bookOpen, userCheck, receipt, barChart, repeat, sunrise, clock`. It does **not** have `layoutDashboard`, `user`, `target`, `lifeBuoy`: add them to `import_icons.js` with Lucide paths (the set is extended per phase — A1 precedent) and bump `pb_import_kit` patch. | verified 2026-10-21 |
| F25 | No live sidebar item claims `slide.channel` or `survey.survey` (grep over `*/data/pb_sidebar.xml` empty) — the Learning item may claim them. The Training lens declares no `feature` — add nothing to `FEATURE_BY_TAG`. | verified |
| F26 | Arrival lens key is `pb_lens` in the action context (`hub_shell.js:19, 124-143`, routing in `pb_hub/static/src/js/hub_nav.js`). Redirect precedent: `pb_lifecycle/static/src/js/lifecycle_hub.js` (NAV P2 made the Lifecycle hub a redirector — clone its `setup()` pattern for Talent's `pb_lens === "training"`). | verified |
| F24 | View-wrapper lens precedent (window action inside a HubShell lens): `git show 2c1b3a2ba:pb_ask_hr/static/src/js/askhr_lens.js` — `View` from `@web/views/view`, `viewProps = { resModel, type:"list"|"kanban", context, display:{controlPanel:{}}, noBreadcrumbs:true, searchViewId:false, selectRecord, createRecord }`, template `<div class="… o_action"><View t-props="viewProps"/></div>`. | git history |

## 3. Architecture

### 3.1 Module `pb_learning_hub` (new; clone `pb_talent_hub` file for file)
- `__manifest__.py`: name "Payobook Learning", summary "Courses, tests, certificates and who is
  on what" (no "Odoo", no emoji), version `19.0.1.0.0`, depends `pb_hub, pb_settings,
  pb_sidebar, pb_learn`, data `views/pb_learning_hub_action.xml`, `data/pb_sidebar.xml`,
  assets `learning_hub.js`, `learning_hub_palette.js`, `learning_hub.xml`, `post_init_hook`
  → `gate_menu` (keep the hook; `ensure_screen_gates` is additive and will simply find no row).
- `learning_hub.js`: `export const LEARNING_LENSES = "pb_learning_hub_lens";` config
  `{ key:"learning", brand:{ label:_t("Learning"), icon:"graduationCap" }, defaultLens:"overview",
  cog: openSettings (back label "Learning"), lenses: this.extraLenses() }`; register action
  `pb_learning_hub`; register `HUB_LENS_GATES`.
- `learning_hub_palette.js`: mission row `learninghub`, label "Learning", sublabel "Courses,
  tests and certificates", seq 168 (between Talent 165 and Learn 170), groups
  `base.group_user`, keywords `["training","learn","courses","đào tạo","học tập","talent"]`.
- `data/pb_sidebar.xml` (`noupdate="0"`): `item_learning` — section `pb_learn.sec_learn`,
  **no groups** (everybody's; the HR lenses gate themselves), name "Learning", icon
  `graduation-cap`, sequence 7, `action_xmlid pb_learning_hub.action_pb_learning_hub`,
  `action_tag pb_learning_hub`, `match_action_tags pb_learning_hub,pb_training_board,
  pb_training_numbers`, `match_models pb.training,pb.training.assignment,pb.training.delay,
  pb.training.schedule,pb.training.rule,pb.training.claim,pb.training.allowance,slide.channel,
  slide.slide,survey.survey,survey.question`. **Check first** with
  `grep -rn "slide.channel\|survey.survey" */data/pb_sidebar.xml` that no live item already
  claims those models; if one does, leave them out (uniqueness tests F15).
- `i18n/vi_VN.po`: "Learning" → "Học tập"; the summary line in VI. Three-line header rule
  (NAV_P2_REGROUP A11).
- `tests/test_learning_hub.py`: clone the eight Talent tests, adapted (§7 T1–T3).

### 3.2 The rail (eight lenses, all registered from `pb_training/static/src/js/training_palette.js`)

| seq | key | label EN / VI | icon | Component / props | groups |
|---|---|---|---|---|---|
| 10 | `overview` | Overview / Tổng quan | `layoutDashboard` (or `home`) | `PbLearningOverview` (new, §4.1) | TRAINING_GATE |
| 20 | `mine` | My learning / Của tôi | `user` (or `userCheck`) | `PbMyLearningLens` (new, §4.2) | `base.group_user` |
| 30 | `courses` | Courses / Khóa học | `bookOpen` | `PbTrainingBoard` `{startTab:"courses", tabs:["courses"]}` | TRAINING_GATE |
| 40 | `assigned` | Assigned / Đã giao | `userCheck` | `PbTrainingBoard` `{startTab:"assignments", tabs:["assignments","requests"]}` | TRAINING_GATE |
| 50 | `required` | Required / Bắt buộc | `listChecks` | `PbTrainingBoard` `{startTab:"rules", tabs:["rules","schedules"]}` | TRAINING_GATE |
| 60 | `tests` | Tests / Kiểm tra | `fileCheck` | `PbTrainingTestsLens` (View wrapper, §4.4) | TRAINING_GATE |
| 70 | `claims` | Claims / Hoàn tiền | `receipt` | `PbTrainingBoard` `{startTab:"claims", tabs:["claims"]}` | TRAINING_GATE |
| 80 | `numbers` | Numbers / Số liệu | `barChart` | `PbTrainingNumbers` | TRAINING_GATE + `base.group_system` |

- Employees (no training group) see only MY LEARNING; the rail is still the rail (R6 hides
  the rest). `defaultLens:"overview"` falls back to the first visible lens — verify HubShell
  does that; if it does not, set `defaultLens` from `hubLensAccess` in `setup()`.
- Labels in VI must fit two lines at 64 px: TỔNG QUAN · CỦA TÔI · KHÓA HỌC · ĐÃ GIAO ·
  BẮT BUỘC · KIỂM TRA · HOÀN TIỀN · SỐ LIỆU (all ≤ 9 characters per word).
- The Insights "Training" lens (seq 40) stays unchanged.
- Remove the `TALENT_LENSES` import and registration from `training_palette.js`; import
  `LEARNING_LENSES` from `@pb_learning_hub/js/learning_hub`. Manifest: depends replaces
  `pb_talent_hub` with `pb_learning_hub`; keep `pb_learn` only if something else in the
  module still imports from it (grep) — otherwise drop it. Update the stale comments
  (`training_board.js:3`, `training_views.xml:4`, manifest dependency comment).
- Command-bar rows: `HUB_XMLID` → `pb_learning_hub.action_pb_learning_hub`; row 3900 sublabel
  "Learning", keywords add `"talent"` (R10); rows 3910–3960 sublabel "Learning" and open the
  hub at the matching lens (`courses`→courses, `tests`→tests, `assignments`→assigned,
  `schedules`→required, `claims`→claims); 3930 "My learning" (rename from "My training",
  keep "training" keyword) opens the hub at `mine`; 3970 unchanged.

### 3.3 `PbTrainingBoard` props (`training_board.js` / `training_board.xml`)
- `static props = { startTab:{type:String, optional:true}, tabs:{type:Array, optional:true},
  embedded:{type:Boolean, optional:true}, "*":true }`.
- `onWillStart`: after `await this.load()`, `if (this.props.startTab && this.props.startTab
  !== this.state.tab) await this.setTab(this.props.startTab)` (clone F8).
- Template: the `pbtn-tabs` row renders only the tabs in `props.tabs` when given; when the
  list has one entry, hide the row entirely (`t-if="!props.tabs || props.tabs.length > 1"`).
  Inner counts (`pbtn-tab-n`) keep working for the visible tabs.
- Nothing else in the board changes. The HR board opened via the old `pb_training_board`
  client action still shows all six tabs (no props).

### 3.4 Talent hub (`pb_talent_hub`)
- Sidebar item: drop `pb_training_board` from `match_action_tags`, drop `pb.training` and
  `pb.training.assignment` from `match_models`. Icon: Learning takes `graduation-cap`;
  Talent switches to `target` (add to ICONS, §3.6) and `brand.icon` `"target"` in
  `talent_hub.js`. Blurb "Goals, growth, training and praise" → "Goals, growth and praise"
  (VI "Mục tiêu, phát triển và khen ngợi"); palette keywords keep "training" and "đào tạo"
  (R10 — they now surface the Learning row too, which is fine).
- R10 redirect: in `PbTalentHub.setup()`, if `props.action?.context?.lens === "training"`
  (or whatever key the hub reads for an arrival lens — check `HubShell` `arrival` handling in
  `hub_shell.js`), call `openHub(this.actionService, { xmlid:
  "pb_learning_hub.action_pb_learning_hub", lens:"courses" })` and return. Precedent: the
  Lifecycle hub redirector from NAV P2 (grep `redirect` in `pb_lifecycle*/static/src/js`).
- Tests: `TABS` loses the training row; add
  `test_training_is_not_a_talent_tab_any_more` asserting `training_palette.js` has no
  `TALENT_LENSES`; version bump `19.0.1.1.0`.

### 3.5 `pb_learn` → "Help" and the new hub screen (do LAST, after gitlocal-b6's push — §8.1)
Edit the **sources** (`docs/tutorial_poc/author/…`), never the generated files:
1. `data.js:15133` `B("Learn","Học cùng Payobook")` → `B("Help","Trợ giúp")`.
2. Every user-visible "Learn" that means the menu entry → "Help": the roots list sentence
   `:4358` becomes "Home, Payroll, People, Hiring, Workforce, Expenses, Insights, Compliance,
   Talent, Learning, Help and Settings." (12 roots; ≤ 28 words); "Learn › Lessons" → "Help ›
   Lessons" (3 sites); `gLessonMap: "Open Learn"` → "Open Help"; "Your progress is saved in
   Learn." → "… in Help."; "Eleven pages"/"mười một trang" → "Twelve pages"/"mười hai trang"
   (4 sites). The Chrome top-bar suffix key `learn: "Learning"` (VI "Học tập") must become
   "Help"/"Trợ giúp" — otherwise the guide's own top bar says "Learning", the new area's name.
   `T("hubTitle")` likewise. Do **not** rename the in-screen "Guide" panel or the lesson-kind
   sublabel "Guide" (LD2).
3. `hub_talent` screen (`:10050-10064`): remove the `training` tab. New `hub_learning` screen
   (clone `hub_talent`) with tabs `overview, mine, courses, assigned, required, tests, claims,
   numbers` (EN/VI names as §3.2). `hub_learn` unchanged except its name. Add
   `pb_learning_hub` to `SCREEN_ACTION_TAGS` in `gen_learn_data.py` (LR80).
4. `practice-data.js` MENU (`:2218-2235`): talent loses `training`; add `learning` with the
   eight lenses; `learn` renamed Help. `library.js` `MENU_ORDER` gains `learning` after
   `talent` (12 entries); `library.test.mjs:112` → 12.
5. `contract.json:369` `"Learn": "Học cùng Payobook"` → `"Help": "Trợ giúp"`.
6. Also outside the generator: `learn_hub.js:70` brand label `_t("Help")`,
   `learn_palette.js:77,132` group `_t("Help")`, `views/learn_actions.xml:20-24` action name
   "Help", `pb_hub/static/src/js/hub_palette_entries.js:220` `{label:_t("Help"),
   sublabel:_t("Lessons and tours")}` + new row `{ id:"learning", label:_t("Learning"),
   sublabel:_t("Courses and training"), icon:"graduationCap", seq:168,
   action:{tag:"pb_learning_hub"} }` (if a palette row for the hub already comes from
   `learning_hub_palette.js`, do not duplicate — one row only). `.po`: `msgid "Help"` →
   `"Trợ giúp"` (check for an existing `msgid "Help"`; if it exists with another meaning,
   keep one msgstr "Trợ giúp" — it is the correct word for both).
7. Regenerate and run the full recipe (F18), then the invariants (F21). Bump `pb_learn` to
   `19.0.20.6.0` (minor, because the menu changed).

### 3.6 Sidebar plumbing
- `pb_sidebar/static/src/js/pb_sidebar.js` ICONS: add `target` (Lucide: three concentric
  circles r=10/6/2) and `life-buoy` (Lucide life-buoy) — Help's item icon becomes `life-buoy`
  (generated from `data.js` SIDEBAR leaf icon — change it there), Talent `target`, Learning
  `graduation-cap`. Bump `pb_sidebar` patch version.
- `test_ia_c5.py` TARGET_RAIL Grow = `[('pb_talent_hub.item_talent',5,'target','Talent'),
  ('pb_learning_hub.item_learning',7,'graduation-cap','Learning'),
  ('pb_learn.item_learn_journey',10,'life-buoy','Help')]`; `MATCH_TAGS`/`MATCH_MODELS`
  tables; highlight cases ('learn hub' → 'Help', add 'learning hub' → 'Learning').
- `FEATURE_BY_TAG`: add nothing (mirror Talent, F16) unless the existing Training lens
  declares a `feature` — grep `feature:` in `training_palette.js`; if it does, map
  `pb_learning_hub` to that feature in both Python and `hub_features.js`.
- No `SCREEN_GATES` row and no `pb_vendor_access` migration: the Learning entry is
  everybody's (F17). Record this in the report; the Access board lists it automatically.

## 4. New surfaces

### 4.1 Overview lens (`pb_training/static/src/js/learning_overview.js` + xml + scss)
- Facade `pb.training.overview()` (`@api.model`, in `pb_training.py`; same gate as
  `get_board`: `{'allowed': False}` without a training group). Returns
  `{ allowed, headline, queue:[{key, label, count, lens, tab}], month:{due, past, finished},
  departments:[{name, percent, people}] (top 6 by people, last 90 days, from
  `pb.training.analytics.get_numbers`) }`.
- `headline` is one sentence in plain words built server-side, e.g. "38 people are on 6
  courses. 4 are past their date. 11 finished this month." Zero state: "Nobody is on a course
  yet." (grey). Never a number without its noun.
- Queue rows (quiet-board: grey at zero, amber when > 0): "Claims to agree" → lens `claims`;
  "More time requests" → lens `assigned` tab `requests`; "Past their date" → lens `assigned`.
  Clicking a row calls `openHub(actionService, { xmlid, lens, context })` so the board opens
  on that tab (pass `startTab` through the lens `propsFromContext` if the registry supports
  it — F2 — else set the lens only).
- **Hero moment:** the headline sentence, 22 px, with the three queue chips under it.
- Empty / no-access: "Learning numbers are for the training team." with a link to My learning.

### 4.2 My learning lens (`pb_training/static/src/js/my_learning_lens.js` + xml + scss)
- Reads `pb.my.training.home()`, `i_manage_people()`, `team()` (only if manages),
  `claims()`. Four blocks:
  1. **Next up** (hero): the first unfinished course's `next_name` with `duration` and one
     primary button "Continue" → `window.location.assign('/my/training/<id>/<next_id>')`
     (the existing learner page; keeps the rail? No — it is a portal page. Open it in the
     same tab; the browser Back returns to the hub). If everything is finished: a grey tick
     and "Nothing to do right now."
  2. **My courses** with filters Assigned · In progress · Done (client-side on `tile.finished`
     and `percent`), each card: name, progress bar, due words, reason word, "Test locked /
     Take the test / Passed · score" chip, "Open".
  3. **My team** (only when `manages`): rows from `team().rows` with status chip and a
     one-tap **Remind** button (§4.3); counts overdue/due/done as quiet chips.
  4. **My allowance** (only when `claims().has_employee`): allowance, used, left in words,
     button "Claim a course back" → `/my/training/claims/new`.
- Phone: one column; the Next-up card fills the width.

### 4.3 One-tap Remind
- `pb.my.training.remind(assignment_id)` (`@api.model`): allowed when the assignment's
  employee has `parent_id.user_id == self.env.user` or the user holds a training group;
  refuses otherwise with `AccessError("You can only remind people who report to you.")`.
- Sends `mail_template_assignment_overdue` if `late` else `mail_template_assignment_due`
  (reuse the automation's send helper — find it in `automation.py:171-230` and call the same
  function so the `reminder_log` line is written the same way). Rate limit: one manual
  reminder per assignment per 24 h; store the stamp as a line in `reminder_log` prefixed
  `manual:` (no new field) and refuse with `UserError("A reminder already went today.")`.
- Also expose the same as board verb `remind` in `_VERBS` for the Assigned lens rows
  (button "Remind" per row, same rule).

### 4.4 Tests lens (View wrapper, L0 only)
- `PbTrainingTestsLens` wraps the existing Tests window action (certification surveys) as a
  `View` list (F24) with a small header row: buttons "New test" (opens the existing
  new-test action from `training_views.xml:52-69`) and "Question bank" (opens the existing
  `survey.question` action). This is a deliberate L0 shortcut; L5 redesigns it. Say so in a
  code comment.

## 5. Safety rails
1. Ledger L1 white label; L2 rail standard; L3 R7/R8/R10; L4 design mandate; L8 plain words.
2. Every new user-visible string in EN and VI (`.po` in both `pb_training` and
   `pb_learning_hub`; `pb_learn` via the generator).
3. Do not edit generated `pb_learn` files by hand. Do not touch `pb_learn` sources until
   Fable sends "GO LEARN" (§8.1).
4. No `git add .`; stage named paths; feature-scoped commits (L7):
   (a) `feat(learning-hub): …` new module + sidebar + tests; (b) `feat(training): Learning
   rail lenses, board startTab/tabs, Overview, My learning, Remind`; (c) `chore(talent-hub):
   drop Training lens, redirect, icon`; (d) `chore(sidebar): icons + target rail`;
   (e) `feat(learn): Help rename + Learning hub screen` (after regen); (f) docs/report.
5. Never commit passwords. Logins for the browser walk come from the agent prompt, not
   this file.
6. Exclude `.claude/worktrees/` from every grep (stale copies).

## 6. Design bar (verbatim, owner's words)
"extreme WOW, intuitive, out-of-this-world experience, best in class." Each surface names its
hero moment (§4), has zero dead ends (every empty/locked/error state says why and what next),
uses plain language on every label, chip and toast, motion with purpose only, keyboard
reachable rail (HubShell already), and is measured against Workday Learning / Docebo, not
stock screens. The phase report scores itself against this bar.

## 7. Numbered test cases
Python tests go in `pb_learning_hub/tests/` and `pb_training/tests/test_learning_rail.py`;
source-scan style as the existing suites.
- **T1** `pb_learning_hub.item_learning` exists, section Grow, seq 7, icon `graduation-cap`,
  no groups, action tag `pb_learning_hub`; Talent seq 5 icon `target`; Help seq 10 icon
  `life-buoy` name "Help".
- **T2** `test_ia_c5`: no model, tag or xmlid claimed twice; every rail icon in ICONS; label
  uniqueness; TARGET_RAIL passes.
- **T3** `pb_learning_hub` tests: action exists, icon in the closed set, every asset on disk in
  the bundle, templates parse, no "Odoo"/emoji in user-visible strings, hub registers
  `HUB_LENS_GATES`.
- **T4** `training_palette.js` registers exactly the eight lenses of §3.2 into
  `LEARNING_LENSES` with those sequences, and nothing into `TALENT_LENSES`; pb_training
  depends on `pb_learning_hub` and not on `pb_talent_hub`; Insights lens unchanged.
- **T5** Command-bar rows 3900–3970 point at the Learning hub; keywords include "talent";
  row 3930 label "My learning".
- **T6** Board props: source scan that `startTab`/`tabs` are declared and `onWillStart` calls
  `setTab(props.startTab)`; template hides the tab row for a single tab.
- **T7** `pb.training.overview()` → `allowed False` for a plain user; for a training manager
  the headline contains the course and people counts; zero-state sentence when no
  assignments; queue counts equal `get_board` KPIs.
- **T8** `pb.my.training.remind`: a manager can remind a direct report (mail queued,
  `reminder_log` gains a `manual:` line); a second call within 24 h raises the plain
  UserError; a stranger gets AccessError; HR trainer can remind anyone.
- **T9** Talent: TABS without training; arrival with lens `training` redirects (source scan
  for the `openHub` call with the Learning xmlid).
- **T10** `pb_learn`: regenerate `--check` clean; `vi_VN.po` diff shows only the intended
  rename lines (list them in the report); "gõ DUYỆT" = 1; `pb_payruns` tag present; 0 "These
  figures do not add up"; `MENU_ORDER.length === 12`; `library.test.mjs`,
  `guide_panel.test.mjs`, `lesson_panel.test.mjs` pass; `contract.json` spot-check passes;
  `-u pb_learn --test-tags /pb_learn` green.
- **T11** Whole suites green locally: `--test-tags /pb_learning_hub,/pb_training,
  /pb_talent_hub,/pb_sidebar,/pb_learn,/pb_hub` on a fresh local DB with `-i pb_learning_hub`.
- **T12** Local Chrome walk (then the live one in §8): as HR lead — Learning appears in the
  left menu between Talent and Help; all eight rail items open; Courses shows no tab row;
  Assigned shows two inner tabs; Required shows Day one + Comes round again; Claims; Numbers;
  Overview headline reads correctly; clicking "Claims to agree" lands on the Claims lens. As
  an employee with no training group — Learning shows only My learning; Next up → Continue
  opens the lesson page; Back returns. As a manager — My team block with Remind; second
  Remind shows the plain error toast. Talent rail has three items; old link to Talent with
  lens training lands on Learning › Courses. Help entry opens the guide; its top bar no
  longer says "Learning". ⌘K "training" and "talent" both list the Learning row. Access ›
  Screens lists Learning. Console: zero errors on every page.

## 8. Deploy and verify
### 8.1 Sequencing with other sessions
- Build everything except §3.5 first. When done, write the interim report and **message
  Fable** (`SendMessage to: "main"` is not available cross-session — instead end your turn
  with the report; Fable resumes you with "GO LEARN" once gitlocal-b6 has pushed). Then
  `git pull --rebase` (19.1), do §3.5, regenerate, T10, commit (e).
- Then stop at the **deploy gate**: report local test results and the exact deploy plan;
  Fable announces the service stop to peer sessions and sends "GO DEPLOY".

### 8.2 Deploy (risky tier: new module install)
1. `ssh Payobook19v2 cat /opt/deploy-notes.md` — if any START lacks a DONE, stop and report.
2. `flock /tmp/payobook-studio-deploy.lock` for the whole run. Append the START line
   (`YYYY-MM-DD HH:MM UTC | Claude (LEARNING L0, gitlocal-60) | START | modules | DBs |
   downtime | notes`).
3. Backups: `sudo -u postgres pg_dump -Fc <db> > /odoo/backups/learning-l0-<date>/<db>.dump`
   for all four DBs.
4. Stage from `git archive HEAD` of the named modules only (`pb_learning_hub pb_training
   pb_talent_hub pb_sidebar pb_learn pb_hub` + `pb_tenancy` only if changed) into a **clean**
   `/tmp/deployL0`; per-module scoped `rsync -a --delete` into `/odoo/odoo-server/addons/<m>/`
   (never the addons root). Hash-compare each tree.
5. Snapshot active cron ids per DB (expect payobook 37, rize 69, p0clone 26, template 0).
6. Stop the service; `p0clone` first: `-i pb_learning_hub -u pb_training,pb_talent_hub,
   pb_sidebar,pb_learn,pb_hub --stop-after-init` in a detached unit with a sentinel; grep
   EXIT and tracebacks; then `payobook`, `payobook_template`, `rize` one at a time, stopping
   at the first failure (restore from the dump if a DB is left half-upgraded).
7. Asset ritual per DB: `INSERT INTO orm_signaling_assets DEFAULT VALUES;` then `DELETE FROM
   ir_attachment WHERE url LIKE '/web/assets/%'`; bump `web.assets.version`.
8. Start; confirm registry loaded; warm payobook / rize / p0clone with one curl each; re-check
   cron counts and disable any NEW active cron; verify `ir_module_module.latest_version` for
   each module on each DB equals the manifest (normalise the `19.0.` prefix).
9. Live Chrome walk on payobook.com (T12) with the QA login and the demo HR / manager /
   learner logins given in the prompt. Console clean.
10. Append the DONE (or FAILED + what was restored) line; release the lock; message peers.

## 9. Report back (`L0_REPORT.md`)
1. What shipped: module versions before/after, commits (hashes, one line each).
2. T1–T12 results with evidence (test counts, screenshots under `outputs/learning-l0-<date>/`).
3. Deviations from this handover and why; stale comments fixed.
4. The exact `vi_VN.po` diff lines for `pb_learn`.
5. Ledger rows to add (new gotchas) — write them into `LEARNING_LEDGER.md` as LN6+.
6. Score against the design bar (§6): hero moment named per surface, dead ends found/fixed.
7. Owner items (anything needing a decision), in plain English.
8. Deploy record: START/DONE lines, downtime, per-DB EXIT codes, cron counts.
