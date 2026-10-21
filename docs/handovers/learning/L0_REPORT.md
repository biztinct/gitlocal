# LEARNING L0 — The Learning menu — report

Implementer: Opus, 2026-10-21. Spec: `L0_LEARNING_MENU.md`. Ledger: `LEARNING_LEDGER.md` (new rows LN8–LN15).
Status: **AT DEPLOY GATE** — Parts 1 and 2 built, committed, tested locally (suites + Chrome walk). Not deployed by me.

> **Read first (07:53 UTC):** `/opt/deploy-notes.md` has an open **START from ChatGPT at 07:50 UTC** for
> `pb_hub, pb_learn, pb_learning_hub, pb_payroll_templates, pb_sidebar, pb_talent_hub, pb_training` on all four
> databases, from its combined commit `7db810a1e` (built on top of my `77c780413`; "owner requires combined
> deployment"). p0clone already shows the L0 versions. That deploy carries L0 commits (a)–(e) but **not** the walk
> fix `0f44540dd` (pb_training only). I did not touch the server beyond read-only checks. See §8.

## 1. What shipped (committed on 19.1, not pushed)

| Module | Before | After |
|---|---|---|
| pb_learning_hub (new) | — | 19.0.1.0.0 |
| pb_training | 19.0.1.3.0 | 19.0.1.4.0 |
| pb_talent_hub | 19.0.1.0.0 | 19.0.1.1.0 |
| pb_sidebar | 19.0.3.2.4 | 19.0.3.2.5 |
| pb_learn | 19.0.20.5.16 | 19.0.20.6.0 (+ migration `19.0.20.6.0/post-learning_l0_help_name.py`) |
| pb_hub | 19.0.1.12.0 | 19.0.1.12.1 |
| pb_tenancy, pb_import_kit, pb_vendor_access | — | **unchanged** (not in the deploy) |

Commits:
- `fa0112847` (a) feat(learning-hub): GROW › Learning entry and hub shell
- `a18753ff2` (b) feat(training): Learning rail lenses, board startTab/tabs, Overview, My learning, Remind
- `81feb6a7d` (c) chore(talent-hub): drop the Training tab, redirect old links to Learning, target icon
- `19c61fdfd` (d) chore(sidebar): target and life-buoy icons, GROW rail Talent · Learning · Help
- `77c780413` (e) feat(learn): Help rename + Learning hub screen
- `0f44540dd` fix(training): walk fixes — Tests empty state, due words in Vietnamese, team chip width
- (f) this report + ledger rows (after the deploy)

`git pull --rebase`: origin/19.1 had nothing newer than our base (behind 0); no rebase was needed. ChatGPT's
`7db810a1e` (pb_payroll_templates only) now sits between (e) and the walk fix in the local branch.

## 2. Tests

Local runtime `/Users/adity/odoo19`; staging tree = `git archive HEAD` (05c2b3fe5) minus outputs/RIZE, the seven
`7a2deccb4` modules pinned to `3f4ff7be4` (ledger P3b), my modules + `docs/tutorial_poc` rsynced over it.
Test DB `am_l0_t2` = fresh copy of `am_nav_p3d`, run exactly as the live upgrade:
`-i pb_learning_hub -u pb_training,pb_talent_hub,pb_sidebar,pb_learn,pb_hub --test-enable --test-tags
/pb_learning_hub,/pb_training,/pb_talent_hub,/pb_sidebar,/pb_learn,/pb_hub`. Baseline `am_l0_base` (same copy, HEAD
code before L0).

| # | Result |
|---|---|
| T1 | **Pass** (`test_learning_hub` T1 ×3): item_learning in GROW, seq 7, graduation-cap, no groups, tag pb_learning_hub; a plain employee's sidebar data lists it. Talent 5 target and Help 10 life-buoy "Help" asserted in T2. |
| T2 | **Pass**: test_ia_c5 TARGET_RAIL, icons in the closed set, no model/tag/xmlid claimed twice, labels unique, highlight matrix (learning hub, training board, assignment, course, test → Learning; learn hub → Help). Only `test_every_retired_item_still_points_at_something_that_resolves` fails — **also fails on the baseline** (workforce-planning actions absent locally). |
| T3 | **Pass** (11 tests): action, icon, assets, templates parse, no "Odoo"/emoji, HUB_LENS_GATES, VI entries, training registers into Learning not Talent. |
| T4 | **Pass** (10): exactly eight lenses in order with labels/icons/components/gates/props, nothing into Talent, depends pb_learning_hub (not talent/learn), Insights lens unchanged, assets, templates, white label, VI. |
| T5 | **Pass** (4): rows 3900–3960 → Learning hub at overview/courses/tests/mine/assigned/required/claims, "talent" keyword, 3930 "My learning" ungated, 3970 unchanged. |
| T6 | **Pass** (4): props declared, setTab(startTab) after load, single-tab hides row, Remind on Assigned rows. |
| T7 | **Pass** (5, in an isolated company): plain user → `{'allowed': False}`; zero state "Nobody is on a course yet."; "3 people are on 2 courses. 1 is past their date."; queue = get_assignments/get_claims KPIs; ≤6 named departments. |
| T8 | **Pass** (9): manager reminds a report (1 mail, `manual:` stamp); overdue template for a late course; second press → "A reminder already went today."; 25-hour-old stamp does not block; stranger → AccessError; HR trainer via board verb; morning job's d3 nudge still goes; finished course refused; `remind` on the allow-list. |
| T9 | **Pass** (11 talent tests): TABS without training, Training not a Talent tab, redirect source scan, blurb + VI. |
| T10 | **Pass**: generator `--check` "up to date (6 files)", readability max 28; `vi_VN.po` diff = only the intended rename (§4); "gõ DUYỆT" = 1; payruns tag `pb_payruns`; 0 "These figures do not add up"; `MENU_ORDER.length === 12`; JS library 111/0, guide_panel 117/0, lesson_panel 113/0; check_contract 73 passed; step shape 0 failed; scenario rules ok; resolver ok; pb_learn Odoo suite = baseline. |
| T11 | **726 tests: 6 failed, 8 errors — every one also fails on the baseline** (680 tests: 8 failed, 10 errors; its 2 extra are artefacts of the baseline overlay). Same names: TestIaCycle5Rail retired-items, TestGuideTruth.test_01, TestLearnrevP5.test_f2, TestStatutoryRightNow ×7, TestReminders.test_t4…, TestTheAssignmentsTab ×2. Nothing fails only with L0. PO gate (Odoo PoFileReader): pb_training 152, pb_learning_hub 4, pb_talent_hub 4, pb_learn 241, pb_hub 91 rows, 0 code rows without a value. |
| T12 | Local Chrome walk, `localhost:8069` / `am_l0_t2`, seeded (3 DEMO courses, 18 assignments; manager DEMO Trần Minh Quân with 3 reports). See below. |

T12 detail (local):
- **HR lead (admin, Head of training), EN:** left menu GROW = Talent (target) · Learning (cap) · Help (life-buoy).
  Learning rail OVERVIEW · MY LEARNING · COURSES · ASSIGNED · REQUIRED · TESTS · CLAIMS · NUMBERS. Overview hero
  "11 people are on 4 courses. 8 are past their date." with chips 0 Claims to agree (grey) · 0 More time requests
  (grey) · 8 Past their date (amber); month line; departments. "Past their date" → Assigned lens, inner tabs
  Assignments + More time. Courses: no tab row. Required: Comes round again + Day one (Day one on). Tests: list +
  New test / Question bank. Claims: no tab row. Numbers: the numbers board. Remind on an Assigned row → "… has been
  sent a reminder."; again → "A reminder already went today.". My learning → Continue opens `/my/training/80/285`
  (the lesson page); browser Back returns to Learning › My learning.
- Talent with `pb_lens: "training"` → lands on Learning › Courses. Talent rail GOALS · GROWTH · PRAISE.
- Help: brand and title "Help", rail LESSONS · TEAM · SETUP; the guide's top bar says Help. The Learn coach already
  greets the new page ("First time on Learning?") from the hub_learning screen.
- ⌘K: "training" and "talent" list Talent and Learning; "learn" lists Learning, Help and Training · Learning;
  "help" lists Help · Lessons and tours.
- Access › Screens (R8): GROW lists Talent (roles), **Learning — everyone with a login**, Help — everyone with a login.
- **Manager (VI):** menu Trang chủ · Học tập · Trợ giúp · Cài đặt (locked); Learning shows only CỦA TÔI. Next up
  "Tiếp tục", My courses with filters Đã giao/Đang học/Đã xong, Đội của tôi with quiet chips (4 quá hạn …) and Nhắc;
  Nhắc → "Đã gửi lời nhắc cho DEMO Nguyễn Thị Hoa."; again → "Hôm nay đã gửi lời nhắc rồi."; Nam (already reminded
  by HR from the board) → refused too (one rule, both doors). Screenshot `outputs/learning-l0-20261021/local-manager-my-learning-vi.jpg`.
- **Plain employee (nam.p3c):** `/bizapp/action-pb_learning_hub` → sent to `/my` by pb_me_portal (ledger LN8). Their
  portal home already shows "2 khóa học đã quá hạn" → `/my/training`. See deviation 5.
- Console: no errors on any page walked.
- Not walked: phone width (CSS written), a reader without the training module.

## 3. Deviations from the handover, and stale comments fixed

1. **F23 was wrong:** `ic()` already has `user`, `target`, `home`, `award`. Only `layoutDashboard` is missing; Overview
   uses the existing `layoutGrid`. `pb_import_kit` is not touched.
2. **Overview facade in its own file** `pb_training/models/pb_training_overview.py` (inherits `pb.training`, imported
   last) because it reuses `_assignment_rows/_assignment_kpis` and `_claim_rows/_claim_kpis` from the extensions.
3. **Remind stamp:** `reminder_log` is a JSON dict, so the stamp is the key `manual:<UTC datetime>` written by the
   assignment's own `_mark_sent`; the morning job's keys are untouched (T8 proves the d3 nudge still goes).
4. **T7 "queue counts equal get_board KPIs":** get_board's KPIs are per course (members, not started); the queue's
   three numbers equal the Assigned and Claims tabs' own KPIs (`get_assignments`, `get_claims`), which is what the
   chips open. Tested that way.
5. **Plain employees never see the Learning entry** — pb_me_portal sends an internal user with an employee record and
   no HR/payroll/hiring access to `/my` (NAV ledger P3d). "My learning" therefore serves staff who reach the back
   office (HR, payroll, department heads, managers who are back-office users); employees keep `/my/training`.
   Not changed (pb_me_portal is outside L0). Owner item 1.
6. **Talent keeps the training roles in SCREEN_GATES** (pb_vendor_access untouched by the non-goal): someone whose
   ONLY role is a training role sees Talent with no tabs (honest empty state) and works in Learning. L1 follow-up.
7. **Replica icons:** the Learn sprite has no life-buoy, so the Library/practice replica draws Help with
   `help-circle` and Talent with `target`; the real rail draws life-buoy.
8. **Learn chrome VI:** besides the EN keys, the VI top-bar words that said "Học tập" for the guide (top bar, hub
   title, "Lần cuối vào …", "Mở trang …", "lưu trong …") now say "Trợ giúp", so "Học tập" means only the new page.
9. **SCREEN_ACTION_TAGS:** `hub_learning` → `pb_learning_hub,pb_training_board`, so the Guide also knows the old
   standalone training board.
10. **Talent redirect** draws nothing and opens Learning › Courses in `onMounted` (a redirect from inside a mounting
    action is not safe earlier); verified in the walk.
11. **Walk fixes (commit 0f44540dd):** Tests lens empty state (View `noContentHelp`); My learning says due words and
    reasons from the date/key in the reader's language (the server sends English constants — ledger LN10); team
    chip no longer stretches.
12. Stale comments fixed: `training_board.js:3`, `training_views.xml:4`, pb_training manifest dependency comment,
    `training_palette.js` header, talent hub module description/JS header, library.js MENU_ORDER comment, data.js
    chrome comment.

## 4. `pb_learn/i18n/vi_VN.po` diff (the only change)

```
 #. module: pb_learn
 #. odoo-javascript
 #: model:pb.sidebar.item,name:pb_learn.item_learn_journey
+#: model:ir.actions.client,name:pb_learn.action_learn_hub
 #: code:addons/pb_learn/static/src/hub/learn_hub.js:0
-msgid "Learn"
-msgstr "Học cùng Payobook"
+#: code:addons/pb_learn/static/src/hub/learn_palette.js:0
+msgid "Help"
+msgstr "Trợ giúp"
```
Stored names (LN7): the migration sets `item_learn_journey` and `action_learn_hub` to `{"en_US": "Help", "vi_VN":
"Trợ giúp"}` in place only where the old word is stored (local: `{"en_US":"Learn","vi_VN":"Học cùng Payobook"}` →
Help/Trợ giúp, log "2 name(s) updated in place"). No overwrite reload anywhere.

## 5. Ledger rows

Added to `LEARNING_LEDGER.md` as LN8–LN15.

## 6. Score against the design bar

1. **Hero moments:** Overview — one 22px sentence with the three queue chips under it (grey at zero, amber when
   somebody waits; each opens the right tab). My learning — "Next up" with one button that drops you into the lesson.
2. **Zero dead ends:** every lens has reading / could-not-read (Try again) / not-for-you (with the way to My learning)
   / empty states that say what to do; Remind refusals are sentences; Tests empty list says what a test is (found in
   the walk). Remaining: plain employees are sent to the portal (by design of pb_me_portal), Talent can be empty for a
   training-only role (follow-up).
3. **Plain language EN + VI:** 114 VI entries in pb_training; walked in Vietnamese. Server words in the old board
   (due words, reasons, "30 min") are still English for VI readers outside My learning (LN10).
4. **Motion:** rise-in of hero/panels, bar fills; all off under reduced motion.
5. **Keyboard:** HubShell rail keys; every door is a button. Weakest: the Tests tab is the stock list (L5).

## 7. Owner items (plain English)

1. **Who sees "Learning"?** Today an ordinary employee who logs in goes straight to their own portal page and never
   sees the left menu, so they never see Learning — they use "My training" on the portal (it already shows their
   late courses). Managers and office staff see Learning with just "My learning". Do you want ordinary employees
   to get the new "My learning" screen too? That means changing where employees land, which is a bigger decision.
2. Someone whose only job is running training still sees an empty "Talent" entry. Fix planned for the next phase
   unless you object.

## 8. Deploy plan (as at the gate)

**Situation:** ChatGPT's combined deploy (START 07:50 UTC, commit `7db810a1e`) already includes L0 commits (a)–(e)
and is in progress (p0clone shows pb_learning_hub 19.0.1.0.0, pb_training 19.0.1.4.0, pb_learn 19.0.20.6.0,
pb_sidebar 19.0.3.2.5, pb_talent_hub 19.0.1.1.0, pb_hub 19.0.1.12.1; the other three DBs not yet). I will not start
while that START has no DONE.

**What remains after ChatGPT's DONE — normal tier, one module:** the walk fix `0f44540dd` (pb_training JS/XML/SCSS/.po
only, no Python, no data). Plan:
1. Read `/opt/deploy-notes.md`; no open START. `flock /tmp/payobook-studio-deploy.lock`; START line.
2. Verify ChatGPT's result first, per DB (payobook, payobook_template, p0clone, rize): `latest_version` of the six
   modules = manifests; stored names of `pb_learn.item_learn_journey` / `action_learn_hub` = Help / Trợ giúp
   (LN7); `pb_learning_hub.item_learning` active; cron counts 37 / 0 / 26 / 69.
3. Clean `/tmp/deployL0`, `git archive HEAD pb_training`, scoped `rsync -a --delete` into
   `/odoo/odoo-server/addons/pb_training/`, tree hash = local. PO gate on the box.
4. Bump pb_training to 19.0.1.4.1 first (so the version gate sees it), stop, `-u pb_training` p0clone first then the
   other three (detached unit + sentinel), asset ritual per DB, start, warm each site with one curl, crons back to
   the snapshot, versions, DONE line.
5. Live Chrome walk on payobook.com (T12) — note NAV ledger P1: an agent may not type the QA password on a
   production sign-in; if the coordinator cannot hand over a signed-in tab, the live walk is an owner step.

If the coordinator prefers, the walk fix can instead ride ChatGPT's next deploy; nothing in it is risky.
