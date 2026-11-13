# LEARNREV P5b — report (every lesson in the four lines, step thumbs, the Vietnamese pass)

Implementer: Opus 5.5 (lead) with seven Opus writers (one per product area, writing blocks only, validated by
`tools/p5b_blocks.py`) and one Opus Vietnamese reviewer (exact-replacement patch, applied by the lead).
Branch `learnrev-p5b` from 19.1 `2d8ba7e2b`, worktree `.claude/worktrees/agent-a8c2e8a6883928cde`.
**Not pushed, not deployed, no version bumps.** Scope per `P5_SPLIT.md` P5b + the coordinator's DUYỆT fix
(2026-10-20). The session paused on a usage limit mid-phase; the scratchpad was emptied meanwhile (LR70) — nothing
committed was lost; the two unfinished writers were resumed and re-wrote their blocks.

## Scope
| Item | Result |
|---|---|
| S1 lessons | **Done.** All **42 lessons / 297 steps** in the four lines (Look at · It means · It affects · Press); **0 legacy steps** (P4 left 209). 32 lessons rewritten here: the 31 + L31's five legacy steps. 31 field steps across lessons (means/affects generated from the manifest); 288 `source:` template citations for non-manifest steps; Press only on product anchors (135 Press lines, none on a `rep-*` step). One split: L11's file step taught two controls (6 → 7 steps). Quizzes kept; L19's quiz line no longer claims an automatic "yes" the code does not do. |
| S2 walkthroughs | **Done.** 19 rewritten; all **25 live walkthroughs / 167 steps** four-line, 17 field steps. Checks: **none added, on purpose** (below). |
| S5 Vietnamese pass | **Done.** Review of everything P1–P5a added + consistency over the new P5b text: 133 reviewed replacements + the DUYỆT fix + 12 Insurance & Tax fixes found on the clone + the Settings search box (details below). |
| S6 P4 items | **Done.** (a) Thumbs on every lesson step (Guide player), walkthrough card (overlay) and practice-copy card (Journey), one rating row through `rpc_feedback` (`lesson.<L>.<i>` / `walk.<sc>.<step>`), shown in Learn › Settings as "<lesson> · Step n: <title>". (b) Feedback card words moved to chrome `fbk*` (27 keys, VI reviewed). (c) Practice-copy fallback announces itself in both languages — fixed a gap seen on the clone: a lesson on a screen the reader cannot open now says "You can't open this screen, so this step plays on the practice copy." / "Bạn không mở được màn hình này…". (d) Press lines name the control in the reader's language (writers + reviewer). |
| S7 | **Done.** `P5_REPLICA_NOTE.md`: recommend extending the gate (cheap); generate only JourneyBoard / PayPreview later; owner question in plain words. |
| Coordinator fix | **Done.** Approvals `ai-approve` tip VI = "gõ DUYỆT trên thẻ của nó"; no other Vietnamese line names an English PayAI confirm word (TRẢ LẠI / TỪ CHỐI not quoted anywhere); in learn_content.json; pb_learn vi_VN.po untouched; `test_payai_p4.test_08` passes on the clone. |

## Lesson / walkthrough inventory (all four-line)
| Area | Lessons (steps) | Walkthroughs (steps) |
|---|---|---|
| P4 (unchanged shape, VI reviewed) | L1 10, L2 10, L3 7, L5 9, L6 8, L8 10, L9 7, L35 6, LA 10, LW 9 | sc_payrun 9, sc_payslips 8, sc_formula 18, sc_mapjourney 8, sc_treatment 7, sc_records 7 |
| Pay Run | L4 8, L30 7, L31 6, L32 8 | sc_import 9, sc_welcome 8 |
| Setup | L7 9, L10 8, L11 7, L12 7, L33 5, L34 6 | sc_blueprint 9, sc_matrix 7, sc_schemes 5 |
| People & pay | L29 9, L13 6, L14 9, L15 6, L28 5 | sc_people 5, sc_paybands 4, sc_payreview 9, sc_decisionroom 5 |
| Hiring | L16 9, L39 10, L40 8 | sc_hiring 9, sc_hiringrole 8 |
| Lifecycle | L17 6, L18 6, L19 5, L25 5, L26 5 | sc_joiners 3, sc_exits 7, sc_probation 3 |
| Workforce | L20 5, L21 6, L22 6 | sc_wftoday 3, sc_wftime 4, sc_wfclose 5 |
| Compliance / Access / Insights | L23 6, L24 6, L27 5, L36 6, L37 5, L38 6 | sc_access 4, sc_filings 3 |
| Totals | **42 lessons, 297 steps, 0 legacy** | **25 live, 167 steps, 0 legacy** (sc_mapping retired) |

## Checks (S2)
None declared. A server check moves Try onto the real screen (LR73). Of the remaining walkthroughs on manifest
screens only sc_import has real presses (open the flow, Commit) — but two of its five Try steps exist only on the
practice copy and a real import needs the person's own file, so a check would make Try worse. sc_people,
sc_payreview, sc_matrix act only on practice-copy controls; sc_wftime and sc_filings are Watch only.

## Vietnamese changes (S5)
| Group | Count |
|---|---|
| Chrome strings | 5 |
| P4 lessons and walkthroughs (press/look name the Vietnamese screen label, e.g. Tính lương, Số liệu không khớp, Kiểm thử / Đã xác thực / Đang hoạt động) | 57 |
| Other lessons, walkthroughs, Learn-map texts; practice data | 38 + 2 |
| Screen manifests (statutory 6, approval_config 3, formula_studio 2, pay 2, people 1, records 1) | 15 |
| Product .po msgstr (statutory 5, formula_studio 5 incl. English FROM/TO → TỪ/TỚI, settings 2, people, insights, payrun_ledgers, workforce_insights) | 16 |
| Approvals tip DUYỆT | 1 |
| Insurance & Tax, found on the clone: "Chân nhân viên/Chân chủ" (legs) → Phần người lao động/Phần doanh nghiệp, totals ("number of employees") fixed, "· hiệu quả" → "· hiệu lực từ"; 7 added (Tax country, Manage country tables, Refresh payroll constants, Up to, Above, two tax-method lines; two JS literals made text nodes) | 5 + 7 |
| Settings search box: "Search surfaces, actions…" → "Search screens and actions…" (+ its VI) | 2 |
| Feedback card words, reviewed while moving to chrome | 27 keys |
| **Total corrected or added** | **148** (+ 27 card keys; + all new P5b lesson Vietnamese) |
All 28 product msgstr changes are code terms: a restart + asset purge loads them; **no overwrite load is needed**
(LR76 — the message of `de607d11e` says otherwise and is wrong).

## Tests
| Test | Result |
|---|---|
| T1 `gen_learn_data.py --check` + every gate; `test_step_shape` | up to date; 0 failed; 0 sentences over 28 words; pb_learn `vi_VN.po` untouched (LR28) |
| T2 truth gate — offline (`tools/truth_offline.py`, new) and `TestGuideTruth` on the clone; replica gate | 16 manifests, 0 errors |
| `check_contract.py` / `replay_tests.py` / `test_scenario_rules.py` | 73/73 · 238 pass / 16 skip / 3 fail (= baseline) · pass |
| T4 node: lesson_panel **113** (+thumbs, +why on hand-over, all 42 lessons four-line), guide_panel 117, library 108; PayAI client_fix 82, gaps_doors 10, oc2 167, oc3 266, rich 90 | all pass |
| `test_learnrev_p5b` (a) step ratings, own screen, unknown refs write nothing, field cards unchanged; (b) report names the step EN+VI + CSV; (c) every step four-line, VI on every line, no brand word; (d) card words in chrome; (n) node suite | 10/10 on the clone |
| Clone run 3 (509 tests: /pb_learn, /pb_settings, PayAI TestOneChatClient + TestPayaiP4Catalogue, Studio TestLaneLabels/TestStudioExperience) | 3 failed, 1 error → after fixes: `test_07b` (baseline, jobs off), `pb_settings test_a` (pre-existing, untouched code, LR78); my tour-test assertion and the PayAI test_08 staging artefact fixed and re-run green |
| Clone runs 5 + 7 (focused re-runs on the final code: TestFeatureGate, TestPayaiP4Catalogue incl. test_08 DUYỆT, /pb_statutory, TestGuideTruth, TestLearnrevP5/P5b, statutory provider) | 22/22 and 58/58 |
Clone: `pg_dump payobook --exclude-table-data=hr_payslip_line | psql lrp5bclone`; AI connection off and every
`*api_key*` blank (checked, would abort otherwise), 0 jobs, mail off, PayAI user implied on the clone only; staged
from `git archive HEAD`; `systemd-run` units, unique names; waited for another session's p0clone run to finish before
starting (stopped my own first launch). **Dropped with `dropdb --force`, filestore removed, stage and logs removed,
no unit left, no clone login active.** Databases left: payobook, payobook_template, p0clone, rize. ABM untouched.

## Browser checks (clone on 127.0.0.1:8093 via ssh tunnel, QA user, Guide on)
Screenshots: `/private/tmp/claude-502/-Users-adity-Documents-GitHub-gitlocal/d3a7939f-6b40-427b-9e7d-c5a89b5a6ab8/scratchpad/p5b/walk/`
| # | Result | Evidence |
|---|---|---|
| B1 People (Employees), Workforce (Time), Compliance (Bank checks) lessons play in the docked Guide with the four lines beside the highlighted real control; labels match the screen | pass | `p5b_b1_people_lesson.png`, `p5b_b1_workforce_lesson.png`, `p5b_b1_compliance_lesson.png` |
| B2 a lesson on a screen the reader cannot open (Government filings) plays on the practice copy with the note, EN and VI | pass after the S6 fix (the note was missing) | `p5b_b2_gated_practice_en.png` (before fix), `p5b_b2_gated_practice_vi.png` |
| Thumbs-down on a lesson step appears in Learn › Settings: "Employees and contracts · 1 not helpful · Employees and their contracts · Step 1: The numbers line is the filter" | pass | `p5b_thumbs_in_settings.png` |
| B4 Vietnamese: Library, top search ("Tìm màn hình và hành động…"), a lesson (Insurance & Tax), a walkthrough (Time, Watch) with a rated card | pass | `p5b_b4_vi_library.png`, `p5b_b4_vi_lesson_statutory.png`, `p5b_b4_vi_walkthrough_rated.png`, `p5b_s5_vi_statutory_fixed.png` |
| B8 console | clean (collectors empty at every step; no error/warning in the console) | — |

## Design bar (1–5)
Hero 1 (every step four lines beside the real control, EN+VI) **5** · hero 2 (a thumbs-down reaches Learn › Settings
at once, named by lesson and step) **5** · zero dead ends **5** (unreachable screen now says why) · plain screen words
EN+VI **4** (product screens outside Learn still show English / machine Vietnamese — open items) · motion 4 (unchanged)
· keyboard 4 (thumbs are real buttons; no new shortcuts) · design system 5 (Lucide, tokens, no emoji/gradient) ·
vs best-in-class 4 (the walkthrough card's thumbs row wraps at the 372 px card width).

## Deviations
- L31 was on the "rewritten in P4" list but still had 5 legacy steps; rewritten here (32 lessons, not 31).
- Rep-* steps were rewritten too (not kept as `body`), so 0 legacy steps instead of "only the 48 replica steps".
- Out of the literal S5 list but on screens lessons quote: the Insurance & Tax figures/labels and the Settings search
  box were fixed (found on the clone / by the reviewer).
- `test_payai_p4.test_08` (PayAI's file) changed to read the four-line step: it had been erroring since P4.
- No server checks added (reason above).

## Deploy notes (for Fable)
- **Merge onto the latest 19.1 first**: the server has newer `pb_formula_studio` (26 files of other work),
  `pb_payruns` and PayAI tests than this branch's base (LR77). Let the PA60 dry-run decide the list (LR33).
- Changed modules: pb_learn (content, thumbs, card, notes, tests); pb_statutory (xml + .po + manifest);
  pb_formula_studio, pb_people (.po + manifest); pb_pay, pb_records, pb_approval_config (manifest); pb_settings
  (xml + .po); pb_insights, pb_payrun_ledgers, pb_workforce_insights (.po); pb_payai_actions (test only).
- Tier: normal (JS/SCSS/XML + .po, no stored field). `-u` the changed modules, asset purge + version bump +
  signalling, restart. **No Vietnamese overwrite load** (all code terms, LR76).

## Open items
1. Product Vietnamese outside Learn (LR74): Lifecycle boards ~80 labels with no Vietnamese; exits desk lights from a
   Python list; overtime ceiling names inline in pb_ot_desk.xml; the import commit label built in Python; scheme groups
   from `_cycle_label`; Run-screen dialog literals (`payrun_wizard.js:1047-1050`); Formula Studio stage array
   (`studio.xml:260`); machine Vietnamese in pb_close ("Thiếu cú đấm"), pb_mission, pb_audit ("Diễn viên hàng
   đầu"), pb_structures, pb_integrations, pb_import_advanced, pb_pay_delivery ("Hết tiền"), pb_payrun_results, Today
   board ("đấm", "ống kính"); "Bank file" has two Vietnamese names. Needs a product Vietnamese pass.
2. Practice-copy drift outside the 16 gated screens (LR75): Today, Close, Overtime chip, exits desk lights, Records'
   wide layout ("Export" vs "Export with data"), Govt filings "Statutory filings for" line, Headcount Increase in
   English on the VI practice copy.
3. English lessons say "These figures do not add up" in four places; the run card says "Figures don't add up"
   (L2 tip, L9 step 7, sc_treatment step 7, one Learn-map text) — next content pass.
4. `pb_settings test_a_single_card_category…` fails on untouched code (LR78).
5. The top-bar language switch wrote the QA user's language back to English on the clone during the walk (seen
   once; not Learn code) — worth a look by its owner.
6. Walkthrough card: the thumbs row wraps to two lines at 372 px; a one-line layout would be tidier.

## Commits (`git log 2d8ba7e2b..learnrev-p5b`)
1b45330bd writing guide + block tool · 05fd983e9 step thumbs · d4795b368 card words to chrome · 4b04bbd47 Workforce ·
f6dfa758b Lifecycle · 01b0bbb14 Hiring · 277401165 Compliance/Access/Insights · c28106596 People & pay · f54e4ce86
replica note · af47501c6 Pay Run + tour · 21fd5da6a Setup · b65e6f961 all-42 node test · 75469ae35 ledger LR70–75 ·
ead66d100 report first cut · c44aa3f8d two older tests · 337f20dfa practice-copy note (S6) · ab4e3f41f VI pass
(content + DUYỆT) · de607d11e VI on product screens/manifests · 6cba0fb8b offline truth gate tool · cf4cf77ad PayAI
test_08 · 1d3d1d37b tour body test · cf1e745ed Insurance & Tax Vietnamese · (this report + LR76–78).

## Ledger rows added
LR70 scratchpad emptied during a pause · LR71 sandbox refusals and how to run around them · LR72 step index as shipped
· LR73 checks move Try to the real screen · LR74 English / machine Vietnamese on non-manifest screens · LR75 practice
copy drift outside the gate · LR76 overwrite load only for stored terms · LR77 staging an older module breaks `-u` ·
LR78 pre-existing pb_settings failure.
