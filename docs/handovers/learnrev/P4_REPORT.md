# LEARNREV P4 — report (lessons and walkthroughs beside the real screen)

Implementer: Opus, 2026-10-17/18, worktree `.claude/worktrees/agent-a5150794862cb9356`, branch `learnrev-p4` from
`f8d46509b`. The builder hit its session allowance after the last fix commit (`936961063`), with the browser walk
done (screenshots `p4_b1`–`p4_b10` present) but before writing this report; Fable wrote it from the commits, the
walk screenshots and a fresh offline + clone test run at the final commit. Handover: `P4_HANDOVER.md`.

## Scope
| Item | Result | Where |
|---|---|---|
| S1 Step shape | **Done.** Lesson steps carry `look / means / affects / press` (bilingual); `body` stays as the legacy line; `field: "<screen>.<key>"` steps are filled from the manifests through `docs/tutorial_poc/author/tools/export_manifests.py`; generator gates for the shape, `press` only on product anchors, unknown field refs, variants needing `generic`. | `92363dc48` |
| S2 Lesson player v2 in the Guide | **Done.** A lesson plays inside Understand beside the real screen with the real-screen spotlight; `rep-*` steps and unreachable screens fall back to the replica player with "This step shows the practice copy." on the card; spotlight fold class renamed `lrn-spot-docked`; a playing lesson is the only thing in the Guide and its controls stay in view. | `6aebe6295`, `2ac0a9bd7` |
| S3 Watch keeps the Guide | **Done.** `startScenario` no longer closes the drawer; Tasks shows "Playing · step N of M" with Stop; walkthrough cards draw the four lines; a card re-finds a control the screen redrew. | `952a06d0c`, `6fdbe0a65`, `936961063` |
| S4 Checked Try on the demo company | **Done.** `learn.scenario.check` (read-only, no sudo) with manifest `checks` for `sc_treatment` (fix + recompute), `sc_payrun` (June run computed / submitted) and `sc_records`; the card waits, polls, and advances with the check's note ("Done. Moving on. Basic Salary is now Taken off net pay, set by you."). | `c8c1c2e9e`, `93377fa0e` |
| S5 Replica truth | **Done.** Gate: every manifest column appears in the replica and every replica header in the manifest/template; the treatment replica now says Report group / Included in another total / Run signal. | `c6cafb58d` |
| S6 Country-aware statutory | **Done.** `variants` (VN / generic / ID / IN / SG) on L6 (6 steps), L5 (4), L3 (3), L1 (1), L31 (1); client picks by company country (scheme country wins on Mapping/Studio); `bootstrap.country`. | `d2991af0c` |
| S7 Lessons of the eight screens | **Done.** 84 steps rewritten in the four lines across 11 lessons (table below); 14 field steps. | `6bf5a403c`, `d2991af0c` |
| S8 Walkthroughs | **Done.** `sc_payrun` 9, `sc_payslips` 8, `sc_formula` 18, `sc_mapjourney` 8, `sc_treatment` 5→7, `sc_records` 7 steps, all four-line. | `6bf5a403c` |
| S9 Failure wording | **Done.** Slow screen → "Still loading" + Retry (`p4_b7_still_loading.png`), "You can't open this screen" only for a real refusal; `.pct-empty` in the refusal boxes. | `952a06d0c` |
| S10 Learn header + pill + P3 leftovers | **Done.** The Learn bar reads "Learn"; no launcher floats over the Library rows; Explain folds the Guide sections (`p4_explain_folds.png`); Runs "Right now" counts drafts by month (`p4_runs_right_now.png`). | `5293703ec`, `952a06d0c` |

## Lessons rewritten (steps before → after · four-line · field steps · country variants)
| Lesson | Station | Before | After | Four-line | Field | Variants |
|---|---|---|---|---|---|---|
| L1 | runpayroll | 10 | 10 | 10 | 1 | 1 |
| L2 | payruns | 10 | 10 | 10 | 2 | 0 |
| L3 | payslips | 7 | 7 | 6 | 1 | 3 |
| L5 | formula | 10 | 9 | 8 | 1 | 4 |
| L6 | statutory | 8 | 8 | 7 | 0 | 6 |
| L8 | mapping | 9 | 10 | 10 | 1 | 0 |
| L9 | treatment | 6 | 7 | 7 | 2 | 0 |
| L31 | fullfinal | 6 | 6 | 1 | 0 | 1 |
| L35 | insights | 6 | 6 | 6 | 0 | 0 |
| LA | approvals | 10 | 10 | 10 | 3 | 0 |
| LW | dashboard | 9 | 9 | 9 | 3 | 0 |
Total: 84 of 296 steps in the new shape; the other 31 lessons keep `body` (shown as "It means") and play in the
panel too (P5 rewrites them).

## Tests (run by Fable at the final commit `936961063`)
| Test | Result |
|---|---|
| T1 generator gates + `gen_learn_data.py --check` | up to date; readability report clean (no sentence over 28 words) |
| T2 node `pb_learn/tests/js/lesson_panel.test.mjs` | **99/99** |
| P2/P3 node suites (`guide_panel` 117, `library` 103) | **all pass** |
| PayAI node suites (client_fix 82, gaps_doors 10, oc2 167, oc3 266, rich 90) | **all pass** |
| `check_contract.py` | only the known `grid-hint` anchor |
| `replay_tests.py` | 238 pass / 16 skip / 3 fail — identical to the baseline before P2 |
| T3/T4 + full clone run (`lrp4clone`, dump-based, AI off, jobs off; tags pb_learn, pb_hub, pb_payruns, PayAI TestOneChatClient, Studio TestLaneLabels/TestStudioExperience) | **513 tests, 2 failed, 0 errors** — both known baselines: `pb_hub test_static::test_every_palette_entry_points_at_a_registered_action` (partial staging, LR50) and `pb_learn test_questions::test_07b` (jobs off on the clone). `test_learnrev_p4`, `test_guide_truth`, `test_scenario`, `test_feature_gate` all pass. |

## Browser checks (clone on 8093, Guide ON, QA user in the demo world on the clone only; screenshots in
`scratchpad/p4/walk/`)
| # | Result | Evidence |
|---|---|---|
| B1 lesson in the Guide, spotlight on the real "Pay role" header, nothing covered | pass | `p4_b1_lesson_step1.png` |
| B2 field step with the four lines and real "Used by" names | pass | `p4_b2_field_step.png` |
| B3 checked Try: waits, person sets the role + Save, advances with the note | pass | `p4_b3_try_waiting.png`, `p4_b3_try_passed.png` |
| B4 `rep-*` step → replica player with the note; Back returns to the real screen | pass | `p4_b4_practice_copy.png`, `p4_b4_back_real.png` |
| B5 Watch from the Guide keeps the drawer open, card beside the dock | pass | `p4_b5_watch_beside_guide.png` |
| B6 company country ID → BPJS variant; unknown → generic | pass | `p4_b6_id_variant.png`, `p4_b6_generic_variant.png` |
| B7 slow screen → "Still loading" + Retry, then lands | pass | `p4_b7_still_loading.png`, `p4_b7_retry_landed.png` |
| B8 Vietnamese lesson, field step, Try | pass | `p4_b8_vi_*.png` |
| B9 Library header "Learn", no pill over rows | pass | `p4_b9_library.png` |
| B10 quiz in the panel, station done | pass | `p4_b10_quiz_done.png` |
| B11 console | the builder's walk scripts collect errors per step; no error noted in its screenshots' captions — not re-verified by Fable (open item) | |

## Design-bar self-score (Fable, from the screenshots)
Hero moment 5 (the four lines beside the real header, nothing covered) · zero dead ends 4 (still loading / Retry,
practice-copy note; the B11 console pass not re-verified) · plain words 5 · motion 4 · keyboard 4 (← → and Esc kept)
· best-in-class 4.

## Deploy notes (for the P4 deploy)
Modules changed: `pb_learn` (29 files), `pb_formula_studio` (2), `pb_payruns` (1). No reworded msgstr (0 lines) →
no Vietnamese overwrite load. `-u pb_learn,pb_formula_studio,pb_payruns` ×4 DBs, asset purge + version bump +
signalling, jobs guard for abm/template.

## Open items
1. B11 console cleanliness not re-verified at the final commit (the builder's walk preceded its last three fixes).
2. The other 31 lessons are still in prose (P5).
3. Replica generation from definitions not built (owner decision stands: replicas on tenants; the truth gate keeps
   them honest).
4. The Opus builder could not add LR rows; gotchas Fable extracted from the commits: see LR57–LR59 in the ledger.
