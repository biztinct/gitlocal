# LEARNREV P0 — report (six quick fixes to the live help)

Implementer: Opus, 2026-10-17. Handover: `P0_HANDOVER.md`. Ledger rows added: LR13–LR17.
Deploy tier: **normal**. Status: **all six fixes live on payobook, rize, payobook_template, abm**; versions bumped and
verified; browser walk done on payobook.com.

## How the code reached live (read this first)
1. My F1–F6 commits (739f5b3d4 … d79cac702) went live **first through another session's deploy**,
   `schema-headings-rollout-20261017` (03:22–03:32 UTC, not a Claude session on this machine). It staged 151 modules
   from a tree that already held my commits: its copies of my five modules were byte-identical to them, and it ran
   `-u` on all four DBs plus the asset purge. It stopped payobook.com at 03:23:14 without notice; a second unit of
   the same deployer (`schema-headings-polish-20261017`) stopped it again 03:38:16–03:43:54 (it changed
   pb_payroll_templates only). I did not touch either unit.
2. My own ship (`lrp0-deploy`, 04:04:54–04:08:56 UTC, holding `/tmp/payobook-studio-deploy.lock` so no other
   deploy could start in parallel): the five manifest bumps + the F5 follow-up (`gate.hub_open_for`), staged from
   `git archive HEAD` (e1f26e476), PA60 dry-run diff = exactly the files changed since the last ship.

## Per fix

| Fix | What changed (files) | Test | Browser check (payobook.com, QA Test) | Commit |
|---|---|---|---|---|
| **F1** chat opens at the latest message (G4) | `pb_payroll_ai_insights/.../ai_insight_chat.js` (onMounted → `_scrollToBottom(true)` after history + screen note); `pb_learn/static/src/coach/coach.js` toggle → `_scrollFallback()` for the guide-only stream | node suites (onechat_oc2 167/167, oc3 266/266, rich 90/90, client_fix 82/82, gaps_doors 10/10) local; module suites on clone | **B1 PASS** 03:36 UTC: open → close → reopen on Component treatment: scrollTop 7,099 of 7,683, gap 0, 49 messages, no "Jump to latest" (before: 0 of 7,099). Re-checked on the final build 04:12: gap 0. `walk/p0_b1_reopen.png` | 739f5b3d4 |
| **F2** "Open the lesson" opens THIS screen's lesson (G2) | `coach.js` `openLesson(answer)` + `_lessonStationFor` (station by key → `station_aliases` → station whose lesson walks the screen → answer's show_me anchors / walkthrough screens → map with a note, drawer stays open); `bundle.station_aliases`; click handler passes the turn's answer | **T2** `pb_learn/tests/test_learnrev_lesson_door.py` (3 tests) PASS | **B2 PASS** 03:37: Explain this screen → Open the lesson → Journey shows the "Component treatment" outline (title, 4 cards, Full lesson · 6 min); "Your journey" only as the back link. `walk/p0_b2_lesson.png` | 739f5b3d4 |
| **F3** ⌘K lesson rows without the warning (G16) | `pb_learn/static/src/hub/learn_palette.js`: `Promise.all([loadContent(), translationIsReady])` | browser (no unit layer for module-load timing) | **B3 PASS** 03:35 and 04:12 (bundles 472efba, 335684a): no "lesson rows not added" line (baseline 03:02 had it twice); 67 Learn rows registered; ⌘K "Component treatment" shows "Lesson · 6 min". `walk/p0_b3_learning.png`, `walk/p0_b3_cmdk.png` | 164a07a2c |
| **F4** "calculated" lane label (G21) | `pb_formula_studio/static/src/js/component_treatment.js` `calculated: _t("Calculated by a formula")`; `i18n/vi_VN.po` "Tính bằng công thức" | **T4** `pb_formula_studio/tests/test_lane_labels.py` (2) PASS | **B4 PASS** 03:36: 20 rows read "Calculated by a formula" (GROSS, NET, FULLPAY …), raw "calculated" 0 times. `walk/p0_b4_b6_treatment.png` | 40417e860 |
| **F5** PayAI door never dead-ends (G24) | new `pb_payai_actions/payai/catalogue.py` (server door list from the Learn content hubs/tabs/screens, both languages, ⌘K aliases, `pbdoor.` ids, own `hub` target, Access deny-list); `resolve.py` (`resolve_door` uses it when no rows came; poor match → closest 3 as chips with "I could not find a screen called …"; alias match without glue words); `runner.py` (`Ctx.server_doors`, `door_row` finds `pbdoor.` rows); `actions_green.py` (OpenScreen passes the row's `hub`); `gate.py` `hub_open_for` (the left-menu read, fb08); VI .po: dead-end sentence deleted | **T5** `pb_payai_actions/tests/test_learnrev_doors.py` 6/6 PASS; **T5b** (PayAI session's request) `test_07_t5b_never_a_door_into_access` PASS — 7/7 on a fresh clone 04:11 | **B5 PASS** 03:38 + 03:49 + 04:12: "open the pay okapi screen" → "Which screen do you mean? … I could not find a screen called "the pay okapi"." + Pay Run / Pay Runs / Pay & Deliver chips + Cancel; "open the pay runs board" → "Opening Pay Run Hub › Pay Runs." and the Runs board opens. `walk/p0_b5_miss.png`, `walk/p0_b5_door.png`, `walk/p0_post_ship_door.png` | 31858c3e7, 67dc64be3, f1ab6eb55, 1c11f8196, T5b with this report |
| **F6** "net pay", not the NET component's name (G33) | `pb_hr_payroll_formula/models/formula_net_role.py` (`net_name = _("net pay")`); `formula_config.py` (`_net_role_reason_net_words` / `_net_role_reason_read`: read-time swap of the NET name/code in stored reasons, other components' names that contain it protected, nothing written); VI msgstr "net pay" → "lương thực nhận" | **T6** `pb_hr_payroll_formula/tests/test_learnrev_net_words.py` (3) PASS | **B6 PASS** 03:36 on "Payobook Retail — End-Month Payroll": 162 reasons, 35 say "net pay", 0 contain "Net Salary (end-month)"; "…through Net Salary (full month)" stays (a real `via`, by design). `walk/p0_b4_b6_treatment.png` | d79cac702 |

Ship commit (manifest bumps): **e1f26e476**. Screenshots are in
`/private/tmp/claude-502/-Users-adity-Documents-GitHub-gitlocal/d3a7939f-6b40-427b-9e7d-c5a89b5a6ab8/scratchpad/walk/`.

## Deploy per database (`ir_module_module.latest_version`, before → after; all `-u` EXIT=0)

| Module | payobook | rize | payobook_template | abm |
|---|---|---|---|---|
| pb_learn | 19.0.20.5.4 → 19.0.20.5.5 | same | same | same |
| pb_payroll_ai_insights | 19.0.3.12.2 → 19.0.3.12.3 | same | same | same |
| pb_payai_actions | 19.0.4.2.0 → 19.0.4.2.1 | same | same | not installed (left so) |
| pb_formula_studio | 19.0.1.201.30 → 19.0.1.201.31 | same | same | same |
| pb_hr_payroll_formula | 19.0.1.148.14 → 19.0.1.148.15 | same | same | same |

- Files: all five modules byte-identical staged-commit ↔ `/odoo/odoo-server/addons` (`rsync -rcn`, 0 differing files).
- Asset purge + `web.assets.version` bump + `orm_signaling_assets` on all four DBs; new bundle 335684a served.
- Scheduled jobs: payobook 37 → 37, rize 69 → 69 (untouched). The upgrade switched **abm** jobs back on (18) and
  **payobook_template** jobs on (21) — both switched back off at once; both at **0** now.
- PayAI switches untouched; `payai.voice_enabled` on payobook still True. pb_payruns not touched.
- Log: no ERROR/CRITICAL in the four upgrade logs or the service log after start; payobook.com and rize 200.

## Test run (clone of payobook, `--http-port=8099 --gevent-port=8098`, dropped after)
Clone = `pg_dump --exclude-table-data=hr_payslip_line payobook` (payobook is 4 GB, 3.4 GB of it payslip lines; LR16).
Suites: pb_learn, pb_payai_actions, pb_payroll_ai_insights, pb_formula_studio (TestColumnRoles, TestStudioExperience,
TestLaneLabels), pb_hr_payroll_formula (TestNetRoleClassifier, TestLearnrevNetWords). Final full run (04:02):
**786 tests, 4 failed, 1 error**, then the two artefact cases and T5 re-run green. Every failure seen:

| Test | Cause | Mine? |
|---|---|---|
| pb_learn `test_questions.test_07b` | clone prep switches every job off (known baseline) | no |
| pb_payroll_ai_insights `test_egress.test_04e` | commit b43059c01 removed the voice-consent .po wording (known baseline, PayAI session) | no |
| pb_payai_actions `test_payai_fix_client.test_02`, `test_payai_p4.test_08` | test-run artefact: they read sibling modules (pb_home_hub, pb_hub, pb_approval_config) by relative path; passed once those were linked into the staging dir | no |
| pb_payai_actions `test_learnrev_doors.test_04` | my test phrase ("pay okapi" reaches People › Pay at 0.65, rightly); fixed (f1ab6eb55, 1c11f8196) → 6/6 | mine, fixed |
| pb_payai_actions `test_fb08` (run 2) | catalogue.py named `pb.sidebar.item`; moved into `gate.hub_open_for` (67dc64be3) → passes | mine, fixed |
| 171× `AccessError: not allowed to create 'PayAI Conversation'` (run 2) | **payobook's data no longer makes every internal user a "PayAI User"** (`base.group_user` does not imply `group_payai_user`; only Demo User and PayAI Manager do) — every PayAI suite fixture that relies on it fails on a payobook copy. For run 3 the module default was put back **on the clone only**; T5 now grants the group itself. | no — environment; owner/other program should confirm it is intended |
| pb_learn `test_coach.test_11` (run 1 only) | the clone still had payobook's live OpenAI connection, so the model answered "what should i do next here" instead of the honest miss; passes with the connection off | no — clone prep (LR17) |

**Incident on run 1:** the clone kept the live AI connection; the suites made **1,122 real OpenAI calls** in 20 min
(`test_coach.test_11b` alone 19 min) before I stopped my own run. Runs 2–4 had the connection off (0 calls). Standing
rule recorded as **LR17** (clone prep: AI connection off before tests).

Local checks: syntax of every changed JS file (node, as ES modules); offline `test_gaps_doors.py` 4/4,
`test_onechat_oc3.py` 13/13, `test_onechat_oc1.py` 39/40 — the one failure is the pre-existing check_contract
`scenario-anchors-exist` (`data-coach="grid-hint"` missing in Formula Studio), not touched by P0. PO parse gate on the
server: all six .po files of the five modules parse; the two new entries load as `code` rows with the right marker.

## Self-review against the handover
- Binding non-goals kept: no router (`learn_helper.py`), intents, content JSON, Journey, scenario engine or PayAI
  tier/gate change (gate.py only gained a read helper); no learn content regenerated; no stored data changed (F6 is
  read-time; the clone-only group link was on the clone).
- Deviations, each a decision: (a) F2 rung 1 also uses `station_aliases` and lesson-step screens (the Journey's own
  rule) — only wftimeoff / wfovertime land on the map + note; (b) F2's note is a bilingual constant in coach.js
  (LR13) because chrome keys must exist in the content plane; (c) F5 applies the "closest 3 as chips" miss to both
  paths (browser rows and server rows); (d) F5's server rows live in their own id space (`pbdoor.`) so
  `has_door('payhub_runs')` keeps its meaning (LR15).
- White-label: no new user-visible string contains "Odoo" (new strings: the lesson-map note EN/VI, "Calculated by
  a formula" / "Tính bằng công thức", "net pay" / "lương thực nhận").
- Plain English: screen words only in every new string.

## Design-bar self-score (1–5)
| Bullet | Score | Why |
|---|---|---|
| Hero moment | 4 | Reopening the chat lands on the latest turn; "Open the lesson" lands on this screen's outline. |
| Zero dead ends | 5 | The lesson door says so when there is no lesson; PayAI never asks for a panel repair and offers the closest screens. |
| Plain screen words | 5 | "Calculated by a formula", "net pay" in every reason; no component code in a sentence. |
| Motion with purpose | 3 | Unchanged (scroll is instant on open by design: no animation on a re-open). |
| Keyboard / bulk | 4 | ⌘K lesson rows register without a warning; chips are keyboard buttons. |
| Measured against best SaaS help | 4 | Re-open position and "did you mean" chips as in Linear and Notion; the Rize-type dead end is gone. |

## Not verified / open
- **F5 no-rows path on the live site**: the browser always registers its rows, so the server list is proven by T5/T5b
  on the clone, not by a click on payobook.com. The original Rize symptom was not reproduced on rize.
- **Vietnamese rendering** of the new strings was not browser-checked (PO entries parse and load as `code` rows).
- **Guide-only stream** (a person without PayAI): F1's `_scrollFallback` path not browser-checked (payobook's QA user
  has PayAI).
- **payobook "PayAI User" implication** is gone from payobook's data (see table) — not changed; owner/PayAI session to
  confirm it is intended. Every PayAI suite run on a payobook copy needs it put back on the clone.
- The shared Chrome on 9555 kept its tab "hidden" (0 frames/s) after 03:44; B5 retry and post-ship checks ran in my
  own headless Chrome on 9556 with the same QA session cookie copied over (no password typed).
- Not pushed (Fable pushes 19.1).
