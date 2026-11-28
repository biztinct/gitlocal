# PDR P3 — report (HR Responsible optional; the pay package skips yes/no answers)

Spec: `PDR_P3.md`; rules and gotchas: `PDR_LEDGER.md` (G22–G27 added by this phase).
Implementer: Opus, 2026-11-05. Live on all four databases at 13:31 UTC.

## 0. In plain words

* **The full contract form no longer demands HR Responsible.** The field is still
  there and can still be filled; leaving it empty no longer stops a save. This
  unblocks every rize Indonesia contract (none has one).
* **"Build from the contract" on a pay package no longer turns answers into pay.**
  BPJS TK covered = Yes, BPJS health covered = Yes, Employer reimburses BPJS = Yes
  and Tax allowance mode = Insurance tax / All tax used to arrive as earnings of
  1 or 2. They are now left out, as is any count, rate or code. Money components
  and components the scheme does not know about still come in as before.
* **Existing packages were not touched.** Only one existing line anywhere came from
  such an answer (payobook demo, a draft package — §3).

## 1. F1 — what demanded HR Responsible

| Where | What it does | Blocks a save? | Changed? |
|---|---|---|---|
| server `hr_contract/views/hr_contract_views.xml:169` (view `hr_contract.hr_contract_view_form`) | `<field name="hr_responsible_id" required="1"/>` | **Yes** — the only blocker | **Yes**: new inherited view `pb_contracts.hr_contract_view_form_pb_hr_responsible_optional` sets `required` = `0`; field still shown |
| server `hr_contract/models/hr_contract.py:76` | field on `hr.contract`, no `required=` (`ir_model_fields.required = f` ×4 DBs) | No | No |
| server `hr_contract/models/hr_contract.py:181` | activity on contract expiry: `user_id = hr_responsible_id or current user` | No (falls back) | No |
| server `hr/models/hr_version.py:192` | `hr.version.hr_responsible_id` is `required=True` with a default of the current user | No — a different model (`hr.version`), the contract form never writes it | No |
| server `hr` views (employee form, version list, contract template form) | show the field, none required | No | No |
| `pb_contracts/models/pb_contract_360.py:107` + `static/src/js/contract_360.js:61` | contract panel lists "HR responsible" as an ordinary term; its required flag is read from the model (`field.required`, :689) = False | No | No |
| Python constraints, other inherited views, approval rules, New contract dialog in every custom module (`git grep hr_responsible` outside the vendored `hr*/`) | nothing else | — | — |
| Views stored in the four databases (`ir_ui_view.arch_db` mentioning the field) | only the five standard views above | — | — |

The repo's `hr_contract/` is the older vendored snapshot (same line 169) and was
not deployed. Precedent check: `pb_contracts` did **not** already inherit the
contract form (only the history form) — see §6 D1.

## 2. F2 — what changed

`pb_comp_ben/models/employee_comp.py`:

* `_pdr_answer_codes(contract)` (new) — the set of component codes on the contract
  whose scheme rule has words (`value_label_options()` non-empty) or a `value_kind`
  other than `money`. The rule is found by `hr.formula.rule._pb_component_rules`
  — the same join and preference as the contract panel's `_cd_rule_by_code`
  (live scheme of the contract's own company first, id breaks ties). No rule →
  not in the set → today's behaviour.
* `_lines_from_contract` skips those codes. The "carries no wage and no
  components" message is unchanged and still fires only when nothing is left.

Real data (read-only shell on live rize after the deploy, rolled back): the 102
open Indonesia contracts holding BPJS TK covered = 1 would give **275** package
lines instead of **584**; the 309 skipped are exactly IDBPJSTKCOVERE 102,
IDBPJSHEALCOVE 102, IDTAXALLOWMODE 102, IDERREIMBUBPJS 3. Sample contract 3444
keeps Base salary, Annual insurance premium and the annual basic salary line.

## 3. Existing package lines from yes/no or worded components (not changed)

Package lines do not store a component code; the code is read from the note the
build writes ("… (CODE)."), then the rule is found with the same preference.

| Database | Packages | Lines built from a contract component | of which with a rule | **Answer lines** | Detail |
|---|---|---|---|---|---|
| payobook | 9 | 5 (+ 5 "Base salary") | 5 | **1** | line 27 in package 5 (draft), unchecked: `TYLETAMHQCV` "Tỷ lệ % tạm ứng thưởng HQCV", value kind Yes / No, amount 1 |
| payobook_template | 0 | 0 | 0 | **0** | — |
| p0clone | 0 | 0 | 0 | **0** | — |
| rize | 5 (all active) | 0 | 0 | **0** | all 25 lines were written by hand / seeded, none built from a contract |

Note for the owner: payobook package 5 also has `NPT` (number of dependants) = 3
as an earning. Its rule says **money** with no words, so F2 does not catch it —
the rule's value type is wrong, not the package code (G26).

## 4. Tests

Run on a throwaway copy of p0clone (`pdr3_p0`) with the new code in a scratch
addons directory first in the path; copy dropped afterwards.

| Suite | Result |
|---|---|
| pb_contracts + pb_comp_ben, all 71 tests, new code | **70 pass, 1 fail** — `TestCd1Contract360.test_01` (`fillin` key), pre-existing and already listed in `PDR_P2_REPORT.md` §2 |
| the 8 P3 tests on the **old** code (negative control) | 7 fail, as they should; `test_p3_f2_money_component_is_kept` passes on both (it guards the money) |

| Test | What | Result |
|---|---|---|
| F1-1 `test_p3_f1_field_shown_and_not_required` | combined form arch: field present, not invisible, not required; model field not required | Pass |
| F1-2 `test_p3_f1_new_contract_saves_without_hr_responsible` | `Form()` on `hr_contract.hr_contract_view_form`: new contract with HR Responsible cleared saves | Pass |
| F1-3 `test_p3_f1_existing_contract_edits_without_hr_responsible` | existing contract without it: wage edit saves through the form | Pass |
| F2-1 `test_p3_f2_flag_and_worded_components_are_skipped` | integer + "0=No;1=Yes" skipped; money kind with words (Tax mode) skipped | Pass |
| F2-2 `test_p3_f2_counts_and_rates_are_skipped` | quantity and rate skipped | Pass |
| F2-3 `test_p3_f2_money_component_is_kept` | money kept as an earning of 750,000 even though a **draft** scheme of the same company has a worded rule with the same code (live scheme wins) | Pass |
| F2-4 `test_p3_f2_component_without_a_rule_is_kept` | no rule → line kept (333) | Pass |
| F2-5 `test_p3_f2_nothing_left_message_only_when_nothing_is_left` | wage 0 + only answers → "carries no wage and no components"; wage 0 + one money line → builds 1 line | Pass |

Browser (Chrome, new tab):

| Check | Result |
|---|---|
| payobook demo contract 1 (Tô Thanh Liêm), full form: HR Responsible empty, no required marker (required fields on the form: name, start date, schedule, company, category, wage) | **Pass** |
| typed a note, Save → stored (DB `write_date` 13:33:37, HR Responsible still empty); note then cleared and saved again | **Pass** — shot `p3_shots/live_F1_payobook_saved_without_hr_responsible.jpg` |
| rize Indonesia contract 3512, full form: HR Responsible empty and not required (read only — not saved, real contract) | **Pass** (no shot committed: client employee name on screen) |
| Console errors | 0 |

## 5. Commits, versions, deploy

| Commit | What |
|---|---|
| `326880953` | F1 — view + tests, `pb_contracts` 19.0.1.12.2 → **19.0.1.13.0** |
| `514c215d4` | F2 — package build + tests, `pb_comp_ben` 19.0.1.6.0 → **19.0.1.7.0** |
| (this commit) | report, ledger G22–G27, shot |

Deployed 13:27:55–13:31:51 UTC from `git archive 514c215d4`, `filter_deploy.sh full`:
result OK, EXIT=0 errors=0 ×4, crons 33/29/76/44 unchanged, tree hash = stage
(`9057f740add2` / `33fb3f1b47bd`), `latest_version` ×4 OK, new view active ×4,
assets purged + version bumped ×4, sites 200. Live-vs-stage diff before the deploy
was exactly the 8 P3 files; no other session had commits on these two modules
after the live trees. Backups `/odoo/backups/pdr-p3-run-20261105132754`.
Code undo = redeploy `5851960ff`'s trees of the two modules and `-u` them (the
view is removed by the upgrade).

## 6. Deviations

1. **D1 F1 lives in a new file in `pb_contracts`** (`views/hr_contract_form_views.xml`).
   The spec said to prefer `pb_contracts` "that already inherits the contract
   form"; it only inherited the history form. Chosen over `pb_hr_payroll_formula`
   to keep the payroll engine out of this deploy.
2. **D2 "not money" read literally**: every `value_kind` other than `money` is
   skipped — the spec's list plus `decimal` and `boolean` (Yes / No). `boolean`
   is the yes/no case itself; `decimal` is shown as a plain number by the contract
   panel too.
3. **D3 the new `sudima` tenant** (created 13:21 UTC by another session, cloned from
   payobook_template) is not in the deploy set. Its files are the new ones (same
   disk), so F2 already applies there, but its `pb_contracts` is still 19.0.1.12.2,
   so the F1 view is **not** loaded on sudima until somebody runs `-u pb_contracts,pb_comp_ben`
   there. Owner / Fable call (the owner ruling says "every database").
4. **D4 browser check edit**: the demo contract's notes went from empty (NULL) to an
   empty paragraph after "add then clear" (G27). Looks the same on screen.
