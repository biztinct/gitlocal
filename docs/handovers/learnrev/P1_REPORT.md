# LEARNREV P1 — report (the content engine)

Implementer: Opus, 2026-10-17, on branch `learnrev-p1` (worktree), merged into 19.1 at `3086feecd` by Fable.
Handover: `P1_HANDOVER.md`. Ledger rows added: LR19–LR28 (renumbered from the branch's LR13–LR22 at merge; P0 held
LR13–LR18). This file was written by Fable from the implementer's final message: the subagent environment refused to
write a report `.md` from inside the worktree.

Status: **built and tested on a clone; NOT deployed at the time of this report** (deploy is a separate step after the
merge, see "Deploy" below). No screen of its own; nothing browser-walked.

## Scope
| Item | Result | Where |
|---|---|---|
| S1 Manifest registry | Done. `learn_manifest.py` beside each screen in six modules: pb_formula_studio (treatment, mapping, formula), pb_payrun_wizard, pb_payruns, pb_payslip_review, pb_approval_config, pb_dashboard. pb_learn discovers them; no product module imports pb_learn. | `*/learn_manifest.py` |
| S2 `learn.guide` | Done. `guide(screen_key, args)` + `rpc_guide`; runs as the person, never sudo; returns a named `missing` reason instead of raising. Deviation: `learn_content.json` has no top-level `hubs` — hub names/tabs are read from the hub screens (LR19). | `pb_learn/models/learn_guide.py` |
| S3 Truth gate | Done, stricter than T1: a reader citation must read the field INSIDE the cited function; column/button text must be on the screen with the screen's own Vietnamese; only Vietnamese that actually loads counts; retired walkthroughs and retired labels in station outlines/help answers fail too. Caught 9 wrong reader citations and 6 VI mismatches in first drafts. | `pb_learn/tests/guide_truth.py` (offline), `test_guide_truth.py` |
| S4 Right-now providers | Done for Component treatment (`hr.formula.config.learn_right_now`) and the Runs board (`pb.payruns.learn_right_now`); both reuse the screen's own data and access check. | `pb_formula_studio/models/learn_right_now.py`, `pb_payruns/models/pb_payruns_learn.py` |
| S5 Manifests for 8 screens | Done, treatment first end to end. | as S1 |
| S6 Vietnamese gaps | Done: value type (label, help, 9 choices), run signal, the three "set by" markers, missing board headers, plus gaps the other seven screens exposed. Product fixes: value-type options translated (`_description_selection`); field labels renamed to the screen's words "Value type" and "Run signal"; readable help for the Runs balance check. | `pb_hr_payroll_formula/i18n/vi_VN.po`, `formula_rule.py`, `formula_config.py`, `pb_payruns/…` |
| S7 Lesson/anchor lint | Done: ~15 texts reworded EN+VI to remove "Group", "Subtotal"/"Tổng phụ", "Tells the run" incl. the `tr-table` anchor; content regenerated on a scratch copy; only `learn_content.json` changed; `--check` up to date. | `docs/tutorial_poc/author/data.js`, `pb_learn/static/content/learn_content.json`, `anchors.json` |

## Hero: the real Component treatment Guide
Pulled from live payobook data (scheme "Payobook Information Technology — Mid-Month Advance") in EN and VI: six field
cards (`lane`, `report_group`, `pay_role`, `rollup`, `run_signal`, `value_kind`), three actions, doors (station,
lesson L9, task `sc_treatment`, terms). The Pay role card: label/help from the field, six choices each with a "when"
sentence, `filled_by`, the two "set by" markers, 33 `used_by` readers ("Pay run totals: Gross, Deductions, Net",
"The figures on Home", "Gross, Deductions and Net on every payslip", …), `if_changed`. Vietnamese: "Vai trò trong
lương", choices "Cộng vào thực nhận / Trừ khỏi thực nhận / Chính là thực nhận / Chi phí doanh nghiệp / Chỉ để tham
khảo / Vừa cộng vừa trừ". Full dump kept in the session scratchpad (`p1guide.json`); `used_by` counts per screen:
treatment 33, mapping 25, formula 18, payruns 14, runpayroll 10, approvals 8.

## Tests (dump-and-restore clone of payobook, AI connection off, dropped afterwards)
| Test | Result |
|---|---|
| T1 truth gate | pass, 0 errors across 8 manifests |
| T2 treatment Guide EN/VI | pass: 6 cards, "Cộng vào thực nhận", 9 VI value types, path "Ánh xạ › Xử lý thành phần" |
| T3 treatment right now | pass |
| T4 Runs board right now | pass: unbalanced run named with scheme and amount |
| T5 no sudo | pass |
| T6 board value types translated | pass |
| T7 screen with no manifest | pass |
| `gen_learn_data.py --check`, resolver + scenario checks | pass |
| Odoo PoFileReader on all 9 changed .po/.pot | OK |
| Brand-word scan (manifests, providers, new VI, real Guide output) | clean |

First full run: 411 tests, 1 failed, 9 errors — 8 errors were the `_fields` method-name clash (LR22), fixed in
`4f902e069`; 1 error from staging (`test_learn_hub` reads pb_hub beside the staged pb_learn); 1 failure pre-existing
(`TestCoach.test_11`, PayAI's live model answering — same as P0's run). Re-run at the final commit: Guide, gate and
Learn hub tests 20/20. Studio, net-role and value-kind suites passed in the full run. `check_contract.py`: 1 failure
(`grid-hint` anchor missing in a Studio template P1 did not touch); the 6 failures the handover expected no longer fail.

## Commits (branch `learnrev-p1`)
`9c5361237` engine + treatment manifest + gate + VI gaps · `02fddd672` Runs board provider · `b18e749f7` the other
seven manifests, Connections tab, VI gaps · `5a9550ffe` lesson/anchor lint fixes · `3a7ece77e`, `4f902e069`,
`078109432` fixes · `d920c1d7e` ledger rows. Merge: `3086feecd`.

## Design-bar self-score
4–5 per bullet; the Pay role label ("Net Pay Role") and a few technical help texts cost a point (LR27).

## Remaining / decisions for later phases
- **LR27** rename in `formula_net_role.py` (P0's file, now merged): `net_role` label "Net Pay Role" → "Pay role",
  `net_role_detail` "Folded Into a Total" → "Included in another total", `net_role_source` help "subtotal flag" →
  "included-in-another-total tick". Do at the P1 deploy.
- **LR23** no `data-coach` anchors on Mapping › Connections or the Studio's default Table view; 16 `fs-*` anchors
  render nowhere. P2 lays anchors before field cards attach.
- **LR24** the `mapping` Learn screen describes Journey while its manifest describes Connections (the default tab).
  P2 decides: split into two screen keys or move `places`.
- **LR25** JS-literal strings in templates stay English on VI screens; fix with `_t` in a screen pass (P2).
- **Deploy** (LR20, LR26): `-u` pb_learn, pb_formula_studio, pb_hr_payroll_formula, pb_payruns, pb_payrun_wizard,
  pb_approval_config, biz_approval_workflow, pb_scheme_map; reworded existing Vietnamese reaches a DB only with
  `_load_module_terms([...], ['vi_VN'], overwrite=True)` for pb_hr_payroll_formula, pb_payruns, pb_scheme_map; test
  clones by dump, dropped with `--force`.
