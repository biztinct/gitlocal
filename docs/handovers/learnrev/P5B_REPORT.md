# LEARNREV P5b — report (every lesson in the four lines, step thumbs, the Vietnamese pass)

Implementer: Opus 5.5 (lead) with seven Opus writers (one per product area) and one Opus Vietnamese reviewer,
branch `learnrev-p5b` from 19.1 `2d8ba7e2b`, worktree `.claude/worktrees/agent-a8c2e8a6883928cde`.
**Not pushed, not deployed, no version bumps.** Scope per `P5_SPLIT.md` P5b. Status: IN PROGRESS (this file is
written early on purpose and updated as tests and the browser walk finish).

## Scope
| Item | Result |
|---|---|
| S1 lessons | **Done.** All 42 lessons / 297 steps in the four lines (Look at · It means · It affects · Press); 0 legacy steps (P4 left 209). 32 lessons rewritten here (the 31 + L31's five legacy steps). 31 field steps in lessons; every non-manifest step carries a `source:` template citation (288 in data.js). Quizzes kept; one quiz line reworded (L19, an automatic "yes" the code does not do). |
| S2 walkthroughs | **Done.** 19 walkthroughs rewritten; all 25 live walkthroughs / 167 steps four-line, 17 field steps. Checks: none added — see "Checks" below. |
| S5 Vietnamese pass | (in progress — reviewer patch pending) |
| S6 P4 items | Step thumbs (the one allowed player change) **done**; feedback card words moved into the content plane **done**; practice-copy note in Vietnamese: chrome already bilingual (`lpPracticeNote`), browser check pending; `press` in the reader's language: written so by the writers, P4 lines in the reviewer's pass. |
| S7 | **Done** — `P5_REPLICA_NOTE.md` (recommend extending the gate; generate only JourneyBoard / PayPreview later). |

## Checks (S2)
None added, on purpose. A declared check moves Try onto the real screen (LR73). Of the remaining walkthroughs on
manifest screens only sc_import has real presses (open the import flow, Commit), but two of its five Try steps (fix a
cell, match a row) exist only on the practice copy and a real import needs the person's own file. sc_people,
sc_payreview, sc_matrix act only on practice-copy controls; sc_wftime and sc_filings are Watch only.

## Commits
See `git log 2d8ba7e2b..learnrev-p5b` (listed in the final section when the phase closes).

## Tests (so far)
| Test | Result |
|---|---|
| T1 `gen_learn_data.py --check` + gates, `test_step_shape` | up to date; 0 failed; no sentence over 28 words |
| T4 node: lesson_panel 112 (+thumbs, all-42-lessons), guide_panel 117, library 108; PayAI client_fix 82, gaps_doors 10, oc2 167, oc3 266, rich 90 | all pass |
| `check_contract.py` | 73 of 73 |
| `replay_tests.py` | 238 pass / 16 skip / 3 fail — the baseline |
| clone run | pending |

## Open items (so far)
See ledger LR74 (English / bad machine Vietnamese on non-manifest screens) and LR75 (practice-copy drift outside the
16 gated screens).
