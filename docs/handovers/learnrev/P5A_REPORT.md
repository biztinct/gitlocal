# LEARNREV P5a — report (manifests for 8 screens, the feedback loop, P2/P3 leftovers)

Implementer: Sonnet 5.5 (lead) with four Sonnet sub-builders for the eight manifests, branch `learnrev-p5a` from 19.1
`72e2cd8f5`, worktree `.claude/worktrees/agent-a2fd9ba6ba006b62f`. **Not pushed, not deployed, no version bumps.**
Scope per `P5_SPLIT.md` P5a. `data.js` and lesson/walkthrough content: **zero changes** (P5b owns them).

## Scope
| Item | Result |
|---|---|
| S3 manifests (statutory, employees, import, matrix, records, payreview, govreports, wftime) | Done, 16 manifests total. Truth gate 0 errors (offline file half + clone registry half), replica gate 0. VI gaps: none missing in the product .po files (the screens' Vietnamese already existed); 1 msgid added (`sent in by`, Approvals) and the matrix .pot gained the one msgid its .po already had. |
| S3 right-now providers | statutory (no active policy / no tax table), import (rows needing a match, errors, ready to commit), matrix (routes needing people, drafts), records (changes awaiting me / sent back / waiting). All run as the person, no sudo. |
| S4 feedback loop | `learn.feedback` (no new table): `report`, `export_csv`, `rpc_search_miss`; Learn › Settings card "What people asked and rated" (period, four counts, ratings by screen with per-field rows, helper no-answer by screen, top ten searches with no result, CSV). Admin only on the server. |
| S6 P2: Connections tabs, Approvals card | Tab names were untranslatable JS literals (fixed, `connection_desk.xml`); (i) on Storage (storage, value_kind) and Use in payroll (value_kind, pay_role) walked. Approvals request cards had no (i): the label words are now their own spans, (i) on sent in by / Waiting for / Due walked. |
| S6 P2: chat ≥ 50 % while a conversation is live | Done: Guide capped at 40 % once a message was sent (not while a lesson plays). Measured: chat 53 % of the drawer. |
| S6 P3: `learn.path` `why` | `ROLE_WHY` per role; bootstrap returns it only for a guessed role; the Continue card prints "Required because you hold a payroll officer seat."; role stays the fallback. |
| S6 P3: ⌘K Pay role first | `homeFirst()` in `learn_palette.js` (home screen = station whose own search words name the column). |
| S5 two fixes | Top search says "Search screens and actions…" (VI "Tìm màn hình và hành động…", also the palette box and aria-labels); rollup tick = "Đã tính trong một tổng khác" everywhere (field label + help in `pb_hr_payroll_formula` .po). |
| Extra | `check_contract.py` now 73/73 (the Studio keyboard hint carries `data-coach="grid-hint"`); the Library's undeclared event kinds declared (LR63); two replica words fixed (LR66). |

## Commits (branch `learnrev-p5a`)
b4844b3a7 manifests (S3) · c4797d749 feedback card (S4) · e3a4b649f seat + ⌘K (S6) · c5fd25f98 plain search words + one tick wording (S5) ·
the Connections tabs commit · the chat-share commit · the grid-hint commit · ledger rows LR63–LR69 · clone-run fixes ·
feedback-card class rename · (i) on request cards + walkthrough lists · 40 % cap · this report. (`git log 72e2cd8f5..learnrev-p5a`.)

## Tests
| Test | Result |
|---|---|
| T2 truth gate (16 manifests, file half offline + `TestGuideTruth` on the clone), replica gate, anchors registry | 0 errors |
| T3 `test_learnrev_p5.py` (report counts per screen/field, no person in report or CSV, window, admin-only, CSV guard, miss = hash + `library`, words only with both gates, scrub before hash, path why, event kinds, sources, 16 manifests, Library node suite) + provider tests s3a–s3d | pass on the clone |
| T4 node: guide_panel 117, lesson_panel 99, library **108** (was 103; +seat ×3, +⌘K ×2); PayAI client_fix 82, gaps_doors 10, oc2 167, oc3 266, rich 90 | all pass |
| `check_contract.py` | 73 of 73 |
| `replay_tests.py` | 238 pass / 16 skip / 3 fail — identical to baseline |
| `gen_learn_data.py --check`, `test_step_shape` | up to date, 0 failed |
| Full clone run 1 (554 tests) | 6 failures: 2 known baselines + 4 mine (Statutory button methods live on `pb.statutory.wizard`; Journey spine list; two fixture issues) — all fixed |
| Final clone run (670 tests: pb_learn, pb_hub, pb_payruns, PayAI TestOneChatClient, TestLaneLabels, TestStudioExperience, pb_approval_config) | 4 failed, 3 errors, **none mine**: `test_07b` (jobs off on the clone, baseline); pb_hub palette test and 5 `pb_approval_config` static/Vietnamese checks fail only because sibling modules are not staged (LR50 family: `pb_import_kit` files, other modules' .po). Every pb_learn, pb_payruns, Studio and PayAI test passed. |

Clone: `pg_dump payobook --exclude-table-data=hr_payslip_line | psql lrp5clone`, AI off and every `*api_key*` blanked (LR17),
jobs and mail off, PayAI user implied on the clone only (LR18), Guide ON and the QA user made an administrator and a
filings user **on the clone only**; staged from `git archive HEAD`; `systemd-run` units, unique file names. **Dropped
with `dropdb --force`, filestore and staging removed, no clone login left.** (An unrelated `p0clone` database from another
session exists on the server; not touched.)

## Browser checks (clone on 127.0.0.1:8093 via ssh tunnel, own headless Chrome 9563, QA login by fetch)
Screenshots in `/private/tmp/claude-502/-Users-adity-Documents-GitHub-gitlocal/d3a7939f-6b40-427b-9e7d-c5a89b5a6ab8/scratchpad/p5/walk/`.
| # | Result | Evidence |
|---|---|---|
| B3 feedback card after two thumbs and one failed search: counts 0 up / 2 down / helper 10 / search 1; per-field row "Pay role 0/2"; "Words not kept · 4aa4"; CSV downloads (header + rating, helper, search rows) | pass (after fixing a class clash with the field-card `.lrn-fb`, now `lrn-fbk`) | `p5_b3_feedback.png` |
| B5 Continue card reason with the QA role guessed: "Required because you hold a payroll officer seat." | pass | `p5_b5_continue.png` |
| B6 ⌘K "pay role": Component treatment's field row first; placeholder "Search screens and actions…" | pass | `p5_b6_cmdk.png` |
| B7 Connections: tabs Sources / Storage / Use in payroll; (i) on storage, value_kind, pay_role; Pay role card opens | pass | `p5_b7_conn_payroll.png` |
| B7 Approvals: request cards carry (i) for sent in by, Waiting for, Due; the Waiting for card opens | pass | `p5_b7_approvals.png` |
| Guide on the 8 new screens (statutory, employees, import, matrix, records, payreview, govreports, wftime): docked, four sections filled, path chips, live Right now where a provider exists (matrix shows "Expense claims needs people"), (i) cards | pass | `p5_s3_<screen>.png` |
| S6 chat share: after a sent message the Guide is 40 % and the chat 53 % of the drawer | pass | `p5_b8_chat_share.png` |
| Vietnamese: Guide titles and the whole feedback card | pass | `p5_b4_vi_guide.png`, `p5_b4_vi_feedback.png` |
| B8 console | the error / rejection / console.error collector was empty on every page load above | — |

## Design bar (1–5)
Hero 2 (a thumbs-down reaches the authors the same day) 4 — step thumbs are not built (see open items) · zero dead ends 4 ·
plain screen words EN+VI 4 (the new Vietnamese is mine and needs P5b's pass) · motion 4 · keyboard 4 · design system 5 (Lucide, tokens, no gradient/emoji) · vs best-in-class 4.

## Deviations
- The card's strings are bilingual pairs inside `learn_settings.js` (not content-plane chrome) so P5a does not regenerate `learn_content.json`; P5b should move them.
- Right-now on Pay review / Employees / Government filings / Time: none (handover asked for four providers only).
- Derived columns carry `used_by` only where grep found a function that names the thing (LR67): Statutory 12, Employees 7, Government filings 2, Records 1; the rest are empty, not guessed.

## Open items
1. **Step thumbs** (the other half of hero 2): lesson steps have no thumb; the report already counts any `guide_feedback` row, so adding thumbs to the panel player needs no server change. P5b (lesson player owner).
2. **Records Desk and Import header (i)**: Records' fields are buttons, and Import's Status header exists only once a batch exists; the Guide lists them, the (i) appears only where a header does.
3. **Pay review (i)** appears only with a review on screen; **Govt filings** only the Country (i) shows with one country.
4. Vietnamese of the 8 manifests and the new strings is unreviewed: P5b S5.
5. Deploy: modules to ship (LR33: let the PA60 dry-run decide) — pb_learn, pb_hub, pb_statutory, pb_people, pb_import, pb_approval_config, pb_records, pb_pay, pb_govt_reports, pb_time_hub, pb_formula_studio, pb_hr_payroll_formula (.po only). The reworded rollup msgstr and the new search msgids need the overwrite load for pb_hr_payroll_formula and pb_hub (LR20/LR29, vi_overwrite_guard). Asset purge + restart (LR47). `pb_learn.guide_enabled` already ON on payobook.
6. Inspector literals other than the three tabs ("Text component", "Keeps words…") are still English in Vietnamese (LR68).
