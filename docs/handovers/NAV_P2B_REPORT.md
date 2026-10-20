# NAV P2 — Part B (Learn) report

Agent B, 2026-10-21. Scope: handover `docs/handovers/NAV_P2_REGROUP.md` Part B (B1–B8). Only `pb_learn/` and
`docs/tutorial_poc/` were edited, plus this report and six rows appended to `NAV_LEDGER.md`. Nothing pushed.
`pb_learn` 19.0.20.5.11 → **19.0.20.5.12** (the only manifest touched).

## 1. Breadcrumb and label changes (counted by the replacement script, EN / VI)

Every change was an exact-string replacement in `docs/tutorial_poc/author/data.js` or `practice-data.js`
(script kept at the session scratchpad, `words.py`), then regenerated. Where EN is higher than VI the extra
hits are engineering comments in `practice-data.js` section headers (no Vietnamese twin).

| Old words | New words (EN / VI) | EN | VI |
|---|---|---|---|
| Pay Run › X | Payroll › X / Lương › X | 72 | 63 |
| Pay Run › Import | Payroll › Inputs / Lương › Đầu vào | 3 | 2 |
| Pay Run › Deliver | Payroll › Pay out / Lương › Chi trả | 2 | — (VI was already "Chi trả") |
| "Pay Run" as the page name ("Access to Pay Run", "Four Pay Run tabs", "first tab of Pay Run"…) | Payroll / trang Lương | 6 | 6 |
| "Deliver" as the tab name ("Deliver sends…", kicker, quiz answer, "That opens Deliver…") | Pay out (VI "Chi trả" unchanged) | 7 | 0 |
| Lifecycle › Hiring (incl. bold forms) | Hiring › Overview / Tuyển dụng › Tổng quan | 12 | 10 |
| Lifecycle › New joiners, "under New joiners" | People › Joiners / Con người › Người mới | 7 | 6 |
| Lifecycle › Probation | People › Probation / Con người › Thử việc | 5 | 4 |
| Lifecycle › Exits | People › Exits / Con người › Nghỉ việc | 7 | 5 |
| Lifecycle › Contracts | People › Contracts / Con người › Hợp đồng | 3 | 2 |
| Lifecycle › Growth plans | Talent › Growth / Nhân tài › Phát triển | 2 | 1 |
| "Lifecycle access." (4 prerequisites) | "Access to the <Joiners/Probation/Contracts/Exits> tab on People." / "Quyền mở tab … trong Con người." | 4 | 4 |
| Home › Approvals | Home › Inbox / Trang chủ › Hộp thư | 17 | 16 |
| "Approvals" as the Home tab ("opens on Approvals", hub next line) | Inbox / Hộp thư | 3 | 3 |
| People › Announce | Home › Announce › Calendar / Trang chủ › Thông báo › Lịch | 3 (+1 replica heading) | 2 (+1) |
| Insights › Payroll Report | Insights › Payroll / Phân tích › Lương | 1 | 1 |
| Young workers (as the Compliance tab) | Safeguards / Bảo vệ | 4 | 3 |
| Workforce tab lists with Trips | Trips removed | 2 | 2 |
| "nine pages" (glossary, Home lesson step title and list) | "eleven pages", new list | 3 | 2 |
| "Lifecycle line" | "Joining and leaving line" | 1 | 1 |
| Hand edits: "where do I find things" answer (rewritten for eleven pages and new tab names), Tab glossary ("point at them to read the names" → names shown under icons, a P1 leftover), station titles Import → **Inputs / Đầu vào** and Approvals → **Inbox / Hộp thư**, the "rest of People" station + lesson L28 (Goals/Praise now on Talent, tiles Goals + Praise), Journey line labels | | | |

Journey line labels (chrome `lines`): `lifecycle` "Lifecycle" → **"Joining and leaving" / "Gia nhập và nghỉ việc"** (B4,
key and `LINE_ORDER` unchanged); `payrun` "Pay Run"/"Chạy lương" → **"Payroll"/"Lương"** (not in B4; done so the
Journey chapter matches the menu — see deviations).

Left as is on purpose: the Workforce "Needs you" panel still groups **Trips** (the dock, `pb_mission/static/src/js/pb_dock.js:62`,
is unchanged by Part A), the "Pay & Deliver" run-card button (product label in pb_payruns), the "Approvals inbox"
glossary term, the "Payroll Report" heading inside the Insights screen and "Young workers" heading inside the Compliance
screen (full names), "Settings › <category>" breadcrumbs (categories still exist as titled sections of their group).

## 2. Hub screens (B1)

| | Screen | Detail |
|---|---|---|
| Added | `hub_hiring` | tag `pb_hiring_hub`, xmlid `pb_hiring.action_pb_hiring_hub`; tabs Overview / Interviews / Talent pool (VI Tổng quan / Phỏng vấn / Kho ứng viên) |
| Added | `hub_expenses` | tag `pb_expenses_hub`, xmlid `pb_expenses_hub.action_pb_expenses_hub`; tabs Trips / Claims (Công tác / Hoàn chi phí) |
| Added | `hub_talent` | tag `pb_talent_hub`, xmlid `pb_talent_hub.action_pb_talent_hub`; tabs Goals / Growth / Training / Praise (Mục tiêu / Phát triển / Đào tạo / Khen ngợi) |
| Removed | `hub_lifecycle` | dropped entirely, so no place resolves to the retired hub |
| Renamed | `hub_pay` | "Pay Run"/"Đợt lương" → **"Payroll"/"Lương"**; tabs import → Inputs/Đầu vào, deliver → Pay out/Chi trả |
| Changed | `hub_home` | approvals tab → Inbox/Hộp thư; new `askhr` tab (Ask HR / Hỏi Nhân sự); Announce line mentions its Calendar tab |
| Changed | `hub_people` | + newjoiners (Joiners/Người mới), probation, exits, contracts; − praise, goals, announcements; Employees line no longer mentions a Contracts button; Contracts line names "All contracts" |
| Changed | `hub_workforce` | − trips |
| Changed | `hub_insights` | payroll tab → Payroll/Lương |
| Changed | `hub_compliance` | young tab → Safeguards/Bảo vệ (key `young` is the real key; the handover's `young_workers` is the feature name) |
| Changed | `hub_learn` | − training; settings tab → Setup/Thiết lập |
| Changed | `hub_settings` | seven group tabs first (company, access, payroll, hr, workflows, integrations, system), each line listing its categories; non-colliding category keys kept (see deviations) |

## 3. Places re-pointed (B2)

| Screen | Old | New |
|---|---|---|
| hiringrole | `pb_lifecycle_hub:hiring/role` | `pb_hiring_hub:overview/role` |
| hiring | `pb_lifecycle_hub:hiring` | `pb_hiring_hub:overview` |
| joiners | `pb_lifecycle_hub:newjoiners` | `pb_people_hub:newjoiners` |
| probation | `pb_lifecycle_hub:probation` | `pb_people_hub:probation` |
| exits | `pb_lifecycle_hub:exits` | `pb_people_hub:exits` |
| contractends | `pb_lifecycle_hub:contracts` | `pb_people_hub:contracts` |
| growth | `pb_lifecycle_hub:pip` | `pb_talent_hub:pip` |
| peoplemore | praise/goals/announcements on People | praise/goals on `pb_talent_hub`; announcements dropped (now inside Home › Announce); People places first so it stays in the People group |

Help answers whose `screens` named `hub_lifecycle`: raisehire → `hub_hiring`; newjoiner, leaver, endtrial → `hub_people`.
`sidebar_key` → `pb_lifecycle.item_lifecycle`: **none existed** (grep of `learn_content.json` before the change: 0 hits for
`item_lifecycle`; `SIDEBAR_KEYS` has no Lifecycle entry), so nothing to re-point. `SCREEN_ACTION_TAGS` unchanged (the
standalone board tags `pb_hiring_board`, `pb_onboarding_board`, … still exist); two comments updated.

Practice copy (B5, `practice-data.js` MENU): Payroll (Inputs, Pay out), People regrouped, Lifecycle removed, Hiring /
Expenses / Talent added, Workforce without Trips, Insights "Payroll", Compliance "Safeguards", Learn without Training
(Setup), Home with Inbox and Ask HR, Settings as seven groups each holding its categories (`cats`). `SUB_SCREENS`
unchanged. `pb_learn/static/src/engine/screens.js` was taught the `cats` shape (the Settings page draws one titled
section per group; the breadcrumb reads Settings › group › category; `screenTitle` stays Settings › category) and the
Announce calendar heading. One small style rule added (`.lrn-setgroup`, `journey.scss`). Node render check, both
languages: rail = Home | Payroll | People | Hiring | Workforce | Expenses | Insights | Compliance | Talent | Learn |
Settings; Settings groups Company | Access | Payroll | HR | Workflows | Integrations | System; Formula breadcrumb
"Settings › Payroll › Formula Engine" / "Cài đặt › Lương › Bộ máy công thức".

## 4. MENU_ORDER and tests (B6, B7)

- `library.js` MENU_ORDER: home, payrun, people, **hiring** (`pb_hiring.item_hiring`, `pb_hiring_hub`), workforce,
  **expenses** (`pb_expenses_hub.item_expenses`), insights, compliance, **talent** (`pb_talent_hub.item_talent`),
  **learn** (`pb_learn.item_learn_journey`, `learn_hub`), settings. LINE_GROUP lifecycle → **hiring** (see deviations).
- `learn_hub.js:96` lens label "Settings" → "Setup"; `.po` entry added (below).
- `tests/js/library.test.mjs`: 11 entries in MENU_ORDER; the 9 drawn groups in order; names
  Home, Payroll, People, Hiring, Workforce, Insights, Compliance, Talent, Settings; new check that the old Lifecycle
  boards land under Hiring / People / Talent.
- `tests/test_learnrev_p3.py`: `test_b` expects 11. **`test_c` — chose option 1, read the data files on disk**: an item not
  in the database is read from `<module>/data/*.xml` (section, sequence, active) and placed in the order check; an item
  in neither fails with the list. Ran with Agent A's three new data files present on disk → passed.
- `tests/test_learnrev_p2.py:95` 'Next: Payroll › Run'; `guide_panel.test.mjs:441` message text; `test_scenario.py:491`
  comment. `test_coach.py:261,399` and `test_nextbest.py:336` needed nothing (docstring / line order unchanged).

## 5. Generator, checks, tests (B8)

| Check | Result |
|---|---|
| `gen_learn_data.py` | wrote learn_content.json, fixture.js, anchors.json (practice block, 1 line); `vi_VN.po`, sidebar and slot XML unchanged |
| `gen_learn_data.py --check` | ✓ generated data is up to date (6 files) |
| `check_contract.py` | ✓ 73 checks passed |
| `test_step_shape.py` / `test_scenario_rules.py` / `simulate_resolver.py` | 0 failed / 20 refusals + 1 acceptance / every property holds |
| `replay_tests.py` | 238 pass, 16 skip, 3 fail — all three not mine: `pb_payroll_ai_insights` voice-consent test (the card was removed by owner ruling) and two node harness runs that cannot resolve `@web/core` from `runtime.js` |
| JS `library.test.mjs` | **111 passed, 0 failed** (108 before) |
| JS `guide_panel.test.mjs` | **117 passed, 0 failed** |
| JS `lesson_panel.test.mjs` | **113 passed, 0 failed** |
| Odoo pb_learn tests (local, `odoo-local.conf`) | 480 tests run: 4 failed, 11 errors — **the identical set to the baseline run before any change** (diffed by test name), plus the same TestBundle setUpClass error in both |

Baseline and after runs: DB `navp2b_base` = copy of `am_tpl` upgraded with `-u all` (needed: every local template is
older than `pb_sidebar_item.access_customized`); after-run on a copy of it, `-u pb_learn --test-tags /pb_learn`.
Pre-existing failures: TestCoach.test_12, TestFeatureGate.test_09, TestLearnrevP3.test_d, TestLearnrevP4.test_b1,
TestMission.test_09, TestQuestionMining.test_04e, TestReachability.test_02/03/04/07, TestTenantOverride.test_01/02/04,
TestGuideTruth.test_03 (mostly `KeyError: 'learn.tenant.override.value'` and reachability on this local data).
No browser walk: nothing is deployed, and the practice copy was checked by rendering it in node (section 3).

## 6. The `.po` (proof nothing hand-kept was lost)

- Copied `pb_learn/i18n/vi_VN.po` before running the generator, compared after: **byte-identical** (`cmp`), so the
  generator's merge rewrote and dropped nothing.
- `git diff pb_learn/i18n/vi_VN.po`: **+6 lines, 0 removed** — one new entry:
  `#. module: pb_learn` / `#. odoo-javascript` / `#: code:addons/pb_learn/static/src/hub/learn_hub.js:0` /
  `msgid "Setup"` / `msgstr "Thiết lập"`. The old "Settings" entry is kept (harmless; no code reads it now).
- The module loaded the file on `-u pb_learn` with no translation warning.

## 7. Lessons whose recordings need redoing

None. Walkthroughs point at anchors, not page addresses; they reach the moved boards through the screen's place,
which now names the new hub tab. They will open the new places once Part A's hubs are installed.

## 8. Deviations and why

1. **LINE_GROUP lifecycle → `hiring`, not `people`.** Only one station uses that fallback: "Hiring set-up and numbers"
   (no hub tab). Under People it would sit among Joiners and Exits; under Hiring it sits with the hiring lessons.
2. **Settings keeps the non-colliding category keys** in `hub_settings.tabs` beside the seven groups. Screen guides and
   deep links still name categories (`pb_formula_studio` manifest path `pb_settings_hub:formula`); dropping them fails the
   truth gate. The helper still lists only what the page publishes (the groups). The four colliding keys
   (company, access, payroll, integrations) now carry the group's name and line.
3. **Home › Approvals → Home › Inbox, Young workers → Safeguards, Payroll Report → Payroll** were not in B3's list but
   are Part A label changes (A1, A7), so R7 required them.
4. **Station titles renamed** to match the rail: Import → Inputs, Approvals → Inbox; the "rest of People" station
   now reads "The rest of People, Home and Talent".
5. **Journey line "Pay Run" → "Payroll"** (chapter name), so the Journey does not use the retired page name.
6. **Not added: a full-name tooltip for Learn › Setup** ("Learn settings"). Part A's shell now takes a `title` on a
   lens, but that needs a second `.po` entry and the brief allowed one. The tab line says "Learn settings: …" instead.
7. **Workforce dock keeps "Trips"** (handover listed `data.js:6597`): the panel still groups trip requests; only the
   tab went.

## 9. For Agent A / Fable (cross-checks)

- **Vietnamese labels Learn now uses — align the product `.po` files or tell me to change Learn:** Payroll **Lương**,
  Inputs **Đầu vào**, Pay out **Chi trả**, Inbox **Hộp thư**, Ask HR **Hỏi Nhân sự**, Joiners **Người mới**
  (note `pb_workforce_insights` uses "Người mới vào" for its own "Joiners"), Hiring **Tuyển dụng**, Overview **Tổng quan**,
  Interviews **Phỏng vấn**, Talent pool **Kho ứng viên**, Expenses **Chi phí**, Trips **Công tác**, Claims **Hoàn chi phí**,
  Talent **Nhân tài**, Growth **Phát triển**, Safeguards **Bảo vệ**, Insights Payroll **Lương**, Setup **Thiết lập**,
  Settings groups Công ty / Truy cập / Lương / Nhân sự / Phê duyệt / Kết nối / Hệ thống.
- **Screen guides outside pb_learn still say "Pay Run"** and show in Learn: `pb_payruns/learn_manifest.py:103,141`
  ("Pay Run › Results" / "Đợt lương › Kết quả") and `pb_formula_studio/learn_manifest.py:823`. Owner module must fix;
  then rerun the generator (it re-exports manifests).
- Learn's places assume: the Hiring board publishes `pb_hiring_hub:overview/role` for a role page; People publishes
  `newjoiners/probation/exits/contracts`; Talent publishes `pip`.

## 10. R11 self-score

1. Plain words: every new line is short, uses only the words on the new rail, in both languages.
2. Zero dead ends: no lesson or helper answer points at Lifecycle any more; the retired hub has no Learn screen.
3. The practice copy shows the same eleven pages and seven Settings groups as the product will.
4. Hero moment: unchanged by this phase (content follow-up, not a new experience).
5. Weakest point: a few Vietnamese tab names are Learn's choice until Part A's `.po` files land.

## 11. Commit

Files: `docs/tutorial_poc/author/{data.js,practice-data.js,tools/gen_learn_data.py}`, `pb_learn/__manifest__.py`,
`pb_learn/i18n/vi_VN.po`, `pb_learn/static/content/learn_content.json`, `pb_learn/static/src/{anchors.json,
engine/fixture.js,engine/screens.js,hub/learn_hub.js,journey/journey.scss,journey/library.js}`,
`pb_learn/tests/{js/guide_panel.test.mjs,js/library.test.mjs,test_learnrev_p2.py,test_learnrev_p3.py,test_scenario.py}`,
`docs/handovers/NAV_P2B_REPORT.md`, `docs/handovers/NAV_LEDGER.md` (six appended rows). Hash: see `git log` (one commit,
`feat(nav-p2): Learn follows the regrouped menu`). Not pushed.
