# TIDY-E — employee "Full details" clean-up by Country of Work: report

Branch `tidy-e` (from `origin/19.1` @ `5a54fe057`). New module `pb_employee_form_tidy`
19.0.1.0.0. **No module code outside the new module was edited** (no hook in
pb_people, pb_employee_vault, pb_me_tax, legacy country modules, pb_records,
pb_formula_studio, pb_payrun_wizard, pb_lifecycle, pb_pack_*, pb_me_portal). One
test assertion outside it was widened (see §5). Built against
`FIELD_TIDY_HANDOVER.md`, `FIELD_AUDIT_FACTS.md`, `FS_HOST_FACTS.md`, the audit
spreadsheet (verdicts) and the WDGAP wave rules.

## 1. What was built (per handover item)

| Item | What | Where (all in `pb_employee_form_tidy/`) |
|---|---|---|
| 1a/1b | 32 boxes leave the form for everyone; 40 country boxes (+ the two Vietnam summaries) show only when Country of Work matches; groups / sections / tabs left empty close by the same rule; no Country of Work = no country box + the line "Set Country of Work to see country details" (HR only) | `models/form_rules.py` (`FORM_RULES` table + `apply_rules`), applied in `hr.employee._get_view` (`models/hr_employee.py`) to the combined `hr.view_employee_form` |
| 1c | Root cause (FACTS §3) closed: Insurance (BH), Tax & Dependents and Payroll facts tabs carry `payroll_country != 'VN'`, so non-Vietnam staff never fall back to the old Vietnamese boxes; Vietnam staff keep today's summary/old-box swap | same |
| 1d | Every date box on the form (incl. Date of Joining, birthday, contract dates in the smart buttons, dates inside lists) shows the year (`options numeric`) | `form_rules.show_full_dates` |
| 1e | Field label "Country of Work" everywhere (form, Updates/Records sheet heading, Mapping card, filters, exports; vi "Quốc gia làm việc", id "Negara Kerja"); moved from Settings to the top of the form (globe icon line under the phones); timezone note says "Country of Work: …" | `models/hr_employee.py`, `views/hr_employee_views.xml` |
| 2 | Payroll-ready figure, "Not payroll-ready" tab, Payroll-ready and Bank details filters, roster cards and the employee page's bank badge read the APPROVED bank account (`hr.employee.pb_bank_on_record`: an employee bank account — the store the payment list reads, written only after approval — or the Vietnamese bank file's account, also approval-gated). The old Account Number box leaves the form. | `models/pb_people.py` |
| 3a | Country of Work from files: pay data file accepts key / label in any language / ISO-3 / local spellings; unknown word = row loads, value unchanged, log line + a sentence on the pay run load result; Updates/Records sheets accept the same words; Mapping lists it under "Job & organisation" | `models/country_of_work_import.py`, `static/src/xml/people_country_fill.xml` (load-result note) |
| 3b | People list button "Fill Country of Work" (HR managers, only while someone has none) → preview (per country, left-empty reasons, two-country names) → "Fill Country of Work" → fills only empties, logs who/when/how many (`pb.cow.fill.log`), second run does nothing | `models/country_of_work_fill.py`, `views/country_of_work_fill_views.xml`, `static/src/js/people_country_fill.js` |
| 4 | My Payobook › Tax details: the hint under the tax number box sat 30px below it → 6px (measured) | `static/src/scss/me_tax_hint.scss` (frontend asset of this module) |

Seams used (re-checked at origin/19.1): `BaseModel._get_view` / `_get_view_cache_key`
(core precedent `res.currency`); `pb.people._roster_kpis`, `_pbf_spec`, `_roster_row`,
`get_roster_data`, `get_employee_detail` (`pb_people/models/pb_people.py:91,301,408,167,487`);
`hr.payroll.import.batch._coerce_mapped_value` / `_get_mapping_updates`
(`payroll_import_batch.py:1982,3365`); `pb.records.desk._selection_key`
(`pb_records_desk.py:1069`); `pb.formula.studio._EC_LANES` (class attribute,
`pb_formula_studio.py:10275`); `pb.payrun.wizard.attach_spreadsheet`
(`pb_payrun_wizard.py:2408`) + template `pb_payrun_wizard.PayrunWizard` (after the
`bank_waiting` line, `payrun_wizard.xml:507`); `PbPeople` patch + `pb_people.PbPeople`
template (`.ppl-head-actions`); `hr.formula.config.schemes_for_employee`
(`scheme_component_scope.py`).

Why `_get_view` and not one XML view per owning module: the boxes come from eight
modules, two of which (`pb_me_tax`, `pb_payroll_mapping_vn`) are not on every
database. A table applied to the combined form needs no second bridge module, a box
that is absent is simply skipped, and the test reads the same verdicts. The form is
cached per language as before (one extra key: the test-only switch).

## 2. Final per-box table

Boxes not listed stay exactly as they were (116 general boxes; Bank kept — see §3).
"Off the screen" = the box is hidden for everyone; the field, its column, values,
import mappings and formula sources are untouched.

| Box (field code) | Shown to |
|---|---|
| `level_of_health_compensation` | nobody (off the screen; value kept) |
| `trade_union_participation` | nobody (off the screen; value kept) |
| `funeral_fund_participation` | nobody (off the screen; value kept) |
| `female_excluding_pregnant` | nobody (off the screen; value kept) |
| `osh_worker_code` | nobody (off the screen; value kept) |
| `trade_union_fee_code` | nobody (off the screen; value kept) |
| `basic_overtime_electricity` | nobody (off the screen; value kept) |
| `bd_phsk` | nobody (off the screen; value kept) |
| `deduction_of_funeral_money` | nobody (off the screen; value kept) |
| `different_subjects` | nobody (off the screen; value kept) |
| `legal_entity_pays_salary` | nobody (off the screen; value kept) |
| `account_number` | nobody (off the screen; value kept) |
| `pb_position_reference` | nobody (off the screen; value kept) |
| `pb_emergency_relationship` | nobody (off the screen; value kept) |
| `vn_foreign_insurance_exempt` | nobody (off the screen; value kept) |
| `vn_si_number` | nobody (off the screen; value kept) |
| `vn_si_effective_date` | nobody (off the screen; value kept) |
| `vn_hi_number` | nobody (off the screen; value kept) |
| `vn_hi_effective_date` | nobody (off the screen; value kept) |
| `vn_ui_number` | nobody (off the screen; value kept) |
| `vn_ui_effective_date` | nobody (off the screen; value kept) |
| `vn_employer_insurance_cost` | nobody (off the screen; value kept) |
| `vn_employee_insurance_cost` | nobody (off the screen; value kept) |
| `vn_total_insurance_contribution` | nobody (off the screen; value kept) |
| `vn_tax_table_id` | nobody (off the screen; value kept) |
| `vn_tax_effective_date` | nobody (off the screen; value kept) |
| `vn_personal_tax_rate` | nobody (off the screen; value kept) |
| `vn_monthly_tax_allowance` | nobody (off the screen; value kept) |
| `vn_dependent_tax_allowance` | nobody (off the screen; value kept) |
| `pb_vn_enrol_family_health` | nobody (off the screen; value kept) |
| `pb_vn_enrol_private_health` | nobody (off the screen; value kept) |
| `pb_vn_enrol_dep_health` | nobody (off the screen; value kept) |
| `pb_safety_group` | Country of Work = VN only |
| `pb_posh_ic_member` | Country of Work = IN only |
| `pb_sg_experienced` | Country of Work = SG only |
| `overtime_status` | Country of Work = VN only |
| `fire_prevention_officer` | Country of Work = VN only |
| `tham_gia_bhxh` | Country of Work = VN only |
| `subject_to_pit` | Country of Work = VN only |
| `insurance_code` | Country of Work = VN only |
| `pb_npwp_number` | Country of Work = ID only |
| `pb_family_card_number` | Country of Work = ID only |
| `pb_bpjs_employment_number` | Country of Work = ID only |
| `pb_bpjs_health_number` | Country of Work = ID only |
| `pb_vn_dependants_check` | Country of Work = VN only |
| `pb_id_ptkp_status` | Country of Work = ID only |
| `pb_in_pan_number` | Country of Work = IN only |
| `pb_in_tax_regime` | Country of Work = IN only |
| `pb_in_uan_number` | Country of Work = IN only |
| `pb_in_esi_number` | Country of Work = IN only |
| `pb_sg_tax_residency` | Country of Work = SG only |
| `pb_sg_shg_fund` | Country of Work = SG only |
| `vn_payroll_insurance_summary` | Country of Work = VN only |
| `vn_insurance_policy_id` | Country of Work = VN only |
| `vn_work_region` | Country of Work = VN only |
| `vn_exempt_oa_od` | Country of Work = VN only |
| `vn_si_enrolled` | Country of Work = VN only |
| `vn_si_enrollment_status` | Country of Work = VN only |
| `vn_si_salary_base` | Country of Work = VN only |
| `vn_hi_enrolled` | Country of Work = VN only |
| `vn_hi_salary_base` | Country of Work = VN only |
| `vn_ui_enrolled` | Country of Work = VN only |
| `vn_ui_salary_base` | Country of Work = VN only |
| `vn_payroll_tax_summary` | Country of Work = VN only |
| `vn_tax_regime` | Country of Work = VN only |
| `vn_residency_status` | Country of Work = VN only |
| `vn_dependent_record_count` | Country of Work = VN only |
| `vn_eligible_dependent_count` | Country of Work = VN only |
| `vn_dependent_ids` | Country of Work = VN only |
| `pb_vn_is_local` | Country of Work = VN only |
| `pb_vn_tax_resident` | Country of Work = VN only |
| `pb_vn_tax_commitment` | Country of Work = VN only |
| `pb_vn_in_insurance` | Country of Work = VN only |
| `pb_vn_union_member` | Country of Work = VN only |

Tabs that close: Insurance (BH), Tax & Dependents, Payroll facts → Vietnam only.
Inside Tax details the Indonesia / India / Singapore groups and the Vietnam
dependants alert close per country; Payroll Info and Employment profile stay (they
hold general boxes). The name-free verdict copy the test reads:
`pb_employee_form_tidy/tests/data/form_box_verdicts.csv` (field code, verdict, country).

## 3. Verdicts I changed or interpreted

| Box | Spreadsheet | Now | Why |
|---|---|---|---|
| 5 unsure (`pb_position_reference`, `pb_emergency_relationship`, 3× Payroll-facts health cover) | UNSURE | off the screen | owner ruling R12 / handover |
| `account_number` | KEEP | off the screen | handover item 2: Payroll-ready now reads the approved account; nothing pays from this box |
| `bank_name` (Bank) | KEEP | KEEP | handover: remove only if nothing else reads it — the side panel (`employee_details.py:128`), the employee page's bank line (`pb_people.py:544`) and the new-hire wizard (`people_wizards.py:110`) still read/write it |
| `vn_payroll_insurance_summary`, `vn_payroll_tax_summary` | KEEP (VN) | Vietnam only | they were already shown only to Vietnam staff; the rule lets their tabs close for everyone else. Nothing changes for any person (test 9) |
| No Country of Work | FACTS §4 suggested falling back to the company's country | **no fallback** | handover 1b is explicit: no Country of Work = no country box + the hint line. sudima / payobook (everyone "Not recorded") therefore need the fill (deploy step 4) or their Vietnamese boxes disappear until it runs |

## 4. Tests

Run on a local copy of the 19.1 test template (`tidy_e_*`, DEMO data only).

| # | Test | Result |
|---|---|---|
| 1 | VN / ID / IN / SG / none: visible boxes = general + own country, against the committed verdict table (`test_01*`, evaluates every `invisible` on the rendered form, with and without the rules); no ID/VN box for an Indian employee; no country box + hint for none; tabs close; Country of Work at the top, label in DB | PASS |
| 2 | removed boxes: field + column kept, values written and read back | PASS |
| 3 | save of the form (test `Form`, as an HR manager) with hidden boxes holding values → all unchanged | PASS |
| 4 | Date of Joining and every date box carry `numeric` (browser: "05/11/2026") | PASS |
| 5 | approved account → ready; waiting change (`pb.bank.change.request` in HR review) → not; Vietnam-file account → counts; old box only → no longer counts; figures, tab, filter domains, cards | PASS |
| 6 | Mapping card "Country of Work" in Job & organisation; file column sets VN/ID/IN/SG for 13 spellings; "Atlantis" → value unchanged, row listed, log line; Updates sheet (`_selection_key`, `_coerce`, card label) | PASS |
| 7 | fill: preview counts, fills only empties, never overwrites (also when set after the preview), two-country person left + listed, log row, second run fills 0, HR officer refused, button only for managers | PASS |
| 8 | one payslip per country identical before/after a form save (in-module test) **and** across databases: `golden.py` on the copy WITHOUT the module and WITH it → identical lines for VN/ID/IN/SG (NETPAY 5,000; WAGE 12,345) | PASS |
| 9 | HR manager and HR officer: no box newly visible to anyone for any of the 5 people | PASS |
| 10 | touched suites vs baseline — see §5 | PASS (same 21 pre-existing failures) |
| 11 | silent install: md5 of every `hr_employee` row before / after `-i` on a fresh copy → identical (`b0e48894…` both); module ships no employee data; no fill at install | PASS |
| 12 | PO gate (platform `PoFileReader`): vi_VN 41 rows / id_ID 41 rows, 21 code + 20 model, 0 empty; brand word in msgstr: 0; grep of every new user-visible string: 0 | PASS |
| 13 | browser walk (local, HR manager login, desktop 1400 + phone): India, Vietnam, Indonesia, Singapore, no-country employee; People list button → preview → fill → figures refresh; phone layout; My Payobook tax number hint (portal login) — screenshots `tidy_e_shots/01…11`; console: no script errors (only pre-existing 404s for absent app icons and a favicon 500 from the copy's missing filestore) | PASS |

Module suite: 23 tests, 0 failed, 0 errors.

## 5. Touched suites vs baseline (test 10)

Suites of pb_records, pb_formula_studio, pb_payrun_wizard, pb_hr_payroll_formula,
pb_hr_payroll_vietnam, pb_employee_vault (static-contract tests that read vault
source included via pb_scheme_map / pb_workseg), pb_me_tax, pb_training, pb_updates,
pb_scheme_map, pb_workseg, pb_payroll_mapping_vn, pb_hr_payroll_base, biz_debrand,
pb_dashboard, pb_bank_ocr, pb_pay_delivery, pb_people — each on a fresh copy of the
same upgraded template, `-u` of all of them + `--test-tags`.

| Run | Tests | Failed + errors |
|---|---|---|
| baseline: 19.1 code, module NOT installed (`tidy_e_bl`) | 2,753 | 15 + 6 = 21 |
| with module (`tidy_e_af`), first run | 2,776 | 16 + 6 = 22 |
| with module, after the one test fix below | — | **same 21 as baseline** |

The one extra failure was `pb_hr_payroll_formula` `TestEmployeeWorkTimezone.
test_custom_calendar_preserved_and_unknown_country_not_guessed`, which pinned the
old wording "Payroll Country: Asia/Jakarta" in the Settings tab's timezone note —
the wording this phase renames on purpose. **The only file edited outside the new
module**: `pb_hr_payroll_formula/tests/test_employee_work_timezone.py:67` (test
only, no version change) now accepts either wording, so it passes with and without
the module. Rerun: that suite + this module's 23 → 29 tests, 0 failed.

The 21 baseline failures are pre-existing on this local template (bank-document
checks, mapping-home, product-name / debrand scans, command bar, ladder, currency
fallback, sync cost, one-time file, board lane) and identical in both runs.

## 6. Payroll-ready before / after (local data)

Walk data, 8 active people (VN with Vietnam-file account, ID with approved account,
IN with ONLY the old free-text box, SG, three without country, the admin):

| | with bank | not payroll-ready | Payroll-ready |
|---|---|---|---|
| before (old box) | 1 | 7 | 12% |
| after (approved account) | 2 | 6 | 25% |

The India person (old box only) now counts as "missing bank" — on purpose (nothing
pays from that box). The Vietnam-file person counts (no Vietnam figure gets worse).

## 7. Deploy notes (this phase goes live first, on its own)

Read `/opt/deploy-notes.md` first and announce. Deploy set: `payobook`,
`payobook_template`, `p0clone`, `rize`, `sudima` (never `abm`).

1. **Ship one module**: `pb_employee_form_tidy` (new) to `/odoo/odoo-server/addons/`
   (per-module rsync). No other module changes (the one widened test in
   `pb_hr_payroll_formula/tests/` needs no deploy or upgrade). Dependencies, all already installed
   everywhere: `hr`, `pb_hr_payroll_base`, `pb_hr_payroll_formula`, `pb_people`,
   `pb_records`, `pb_formula_studio`, `pb_payrun_wizard` — verify `state='installed'`
   per database before `-i` (an absent one would be pulled in).
2. **Before**, per database (read-only SQL, counts only):
   ```sql
   -- old figure: "bank details on file" = the free-text box
   SELECT count(*) FROM hr_employee WHERE active AND coalesce(account_number,'') <> '';
   -- new figure: approved account (either store)
   SELECT count(*) FROM hr_employee e WHERE e.active AND (
     EXISTS (SELECT 1 FROM employee_bank_account_rel r WHERE r.employee_id = e.id)
     OR coalesce(e.vietnam_bank_account_number,'') <> '');
   -- Country of Work empty (what the fill will look at)
   SELECT count(*) FROM hr_employee WHERE active AND payroll_country IS NULL;
   ```
   (`vietnam_bank_account_number` exists only where the Vietnam payroll module is
   installed — it is on all five today.) Also note the People list's "Not
   payroll-ready" and "Payroll-ready %" figures as an HR manager.
3. **Install**: `-i pb_employee_form_tidy -d <db> --stop-after-init` per database;
   check `ir_module_module.latest_version` = `19.0.1.0.0`. Then
   `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` per database (JS, SCSS,
   templates) and restart. Install writes nothing on employees (test 11).
4. **The fill, on screen, per database** (the same action an HR manager has — not a
   script): sign in as an HR manager with **all companies ticked** in the company
   switcher (the fill covers the companies in use), People › Employees → button
   **"Fill Country of Work"** (shows how many are empty) → read the preview: "Will be
   set to" per country, "Left empty, because" (no contract / no pay set-up pays this
   person yet / two countries), and the names paid under two countries → press
   **"Fill Country of Work"** → the notice says how many were filled. Record the
   preview counts (counts only; the two-country names stay on screen for HR).
   If a shell is used instead, it must be this same action as an HR manager:
   `w = env['pb.cow.fill.wizard'].with_user(<hr manager uid>).with_context(allowed_company_ids=[...]).create({}); print(w.preview_json); w.action_fill()`.
   Expected: rize — the 2 "Not recorded" staff logins have no contract → left empty;
   sudima / payobook — everyone was "Not recorded"; people with a contract and a
   "Paid by" scheme get that scheme's country (sudima: Vietnam).
5. **After**: rerun the SQL of step 2 and read the People list figures again. On
   rize "with bank" should jump from 0 to about 194 (FACTS §2); no database's count
   of people with an approved account goes down.
6. **Look** (QA login, one employee per country): Full details shows only general +
   own-country boxes; Date of Joining shows the year; Country of Work at the top.
7. **Rize rehearsal**: on a copy, `-i`, open one VN / ID / IN / SG employee; load one
   pay data file of the India and Singapore schemes (their "Country" column is mapped
   to Country of Work today) and check nothing changes; run the fill preview.
   Downloaded Updates sheets keep working (they carry hidden column ids); a
   hand-made file headed "Payroll Country" is no longer matched by name — the user
   picks "Country of Work" once and it is remembered.

Rollback: uninstalling the module restores the previous form, label and figures; no
data to undo except Country of Work values written by the fill (the log row
`pb.cow.fill.log` says when and how many; the employee chatter is not used).

## 8. Merge-time notes / risks

- `_EC_LANES` is overridden as a class attribute built from pb_formula_studio's own
  tuple at import time (one name added to the "job" lane) — a future lane change in
  pb_formula_studio flows through.
- The readiness override swaps any `('account_number', …)` term in pb_people's
  domains; if pb_people renames that test, the swap stops matching (tests 5 catch it).
- The form rules match boxes by field name anywhere in the combined form; a new box
  with a listed name would follow the same rule.

## 9. Gotchas (for the ledger)

- FS-1 (TIDY-E): an HR manager who is not "Payroll Base User" cannot open an
  employee's Full details at all — the form reads the Vietnamese dependants list,
  which only payroll groups may read. Pre-existing, not changed here.
- FS-2: a group added to a user from another process (shell) is not seen by a
  running server until it restarts (group cache) — local walks only.
- FS-3: the People list header overflowed on a phone once a third button joined
  "Contracts / Select / Add" (Select pushed off the left edge) — this module lets
  the row wrap at phone width.
- FS-4: `position="move"` only works as a DIRECT child of an `<xpath>` spec, not
  inside new markup — move into the new element with a second xpath.
- FS-5: the platform adds invisible helper copies of fields used in `invisible`
  expressions to the rendered form — tests that walk boxes must skip
  `invisible="True"` helpers.

## 10. Left for later (not in this phase)

- Side panel, Home dashboard "paid with bank" (`pb_dashboard/home_data.py:668`),
  joining checklist and new-hire wizard still read / write the old Account Number
  box (handover: form only, except the Payroll-ready figure).
- New joiners sheet still has no Country of Work column (FACTS §6.4).
- The side panel decides country groups by its own rule (Country of Work or
  nationality); the form now uses Country of Work only (FACTS §4 "decide one rule").

## 11. Owner questions

1. People with no Country of Work now see no country boxes at all. On sudima and the
   demo, everyone is in that state until the fill runs right after go-live. Is it
   fine that someone with no contract (for example the two office-staff logins on
   Rize) keeps no country boxes until HR sets it by hand?
2. A person who only had the old typed "Account Number" (no approved bank account)
   now shows as "missing bank" on the People list. Do you want HR told how many such
   people each company has, so they can add the account through the approved route?
3. The "Bank" box stays on the record because the side panel still shows it. Shall
   the side panel and Home's "paid with bank" figure move to the approved account in
   a later step, so the Bank box can leave too?
