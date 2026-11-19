# TIDY-E2 — Country of Work fill second rule, Vietnamese label, Payroll-ready % (report)

Branch `tidy-e2` from `origin/19.1` @ `a68bd5866` (TIDY-E live ×5). Module
`pb_employee_form_tidy` 19.0.1.0.0 → **19.0.1.1.0**. Only files inside that module
changed. **Not deployed** — ships with the Form builder go-live.

## 1. What was built

| # | Ask | Built |
|---|---|---|
| 1 | Owner ruling R17 — "Fill Country of Work" gets a second rule | `models/country_of_work_fill.py`: (a) the pay set-up the person is paid under (unchanged: "Paid by" regular + advance, and the current contract's payslips; read only for people with a contract); (b) when (a) finds nothing — no contract, or no pay set-up — the country of the person's COMPANY (company record's country). Two countries from (a) stay undecided (never fall to the company). Still only empties, re-read in the same transaction, never overwrites; preview first. |
| 1 | Preview shows the two sources separately and what is still undecided, and why | Preview: "N people have no Country of Work" → table **From pay set-up** (per country) → table **From the company's country** (per country) → **Left empty, because**: "Paid under pay set-ups of two countries — choose by hand", "No pay set-up decides, and the company has no country", "No pay set-up decides, and the company's country is not one of the Country of Work choices" → names of two-country people → last fill. `preview_json` keys: `from_pay_setup`, `from_company`, `use_company`, `fill`, `left`, `two_countries`, `empty`. |
| 1 | HR manager can untick the "from company" part before confirming | Tick box above the preview **"Also fill from the company's country"** (shown only when the company part has someone; ticked by default). Unticked: the preview says "Not ticked: these people stay empty this time." and the fill leaves them. A bare model call (deployer shell) uses the default: ticked. The log keeps **"Of which from the company"** (`pb.cow.fill.log.company_count`, new column). |
| 2 | Vietnamese label still "Bảng lương Quốc gia" after install | Two fixes: (i) the .po — `i18n/vi_VN.po` / `id_ID.po` already carry "Quốc gia làm việc" / "Negara Kerja" for this module's own entry of the field (checked by a test and the PO gate); (ii) the STORED value — `hooks.py` `fix_country_of_work_label(env)`, run on a fresh install (`post_init_hook`) and on upgrade (`migrations/19.0.1.1.0/end-country_of_work_label.py`, after every module's translations load). It replaces only an old / untranslated wording ("Bảng lương Quốc gia", "Payroll Country", "Country of Work", empty) — a label a customer typed is left alone. Indonesian handled the same way ("Negara Kerja"). |
| 3 | Deploy report §7 source-level items in this module | TE-D1 = item 2. TE-D2 = item 1 (a tenant whose pay set-up is linked to nobody now decides from the company). **TE-D3 fixed**: the People list "Payroll-ready %" was people-with-bank ÷ headcount (Sudima: 99 % beside 651 "Not payroll-ready"); it is now the share that IS payroll-ready (running contract AND approved bank) = (headcount − not payroll-ready) ÷ headcount, the complement of the figure beside it (`models/pb_people.py`). |

Also: the People list button's tooltip and the wizard's opening sentence say "pay
set-up or company"; the wizard's internal name dropped "from pay set-up".

## 2. Tests

Local copy of the 19.1 test template, upgraded on `origin/19.1` code, plus
`pb_me_tax`, `pb_payroll_mapping_vn` and the LIVE module 19.0.1.0.0 (exported from
`origin/19.1`), DEMO data only.

| Test | Result |
|---|---|
| 07a preview: from pay set-up {SG: 1}, from company {VN: 1}, left {two countries 1, company without a country 1, company country not a choice 1}, sentences on screen, no vendor word | PASS |
| 07b both sources: pay set-up wins over the company (SG person inside a Vietnam company stays SG), company fills the no-contract person, set value untouched, two-country / no-country / US-company people stay empty, log 2 filled / 1 from company / 3 left, second run 0 | PASS |
| 07c "from company" unticked: only the pay set-up part fills; ticked on a later run, the company part fills then | PASS |
| 07d company source alone (the live Sudima / demo shape: nobody decided by a pay set-up) | PASS |
| 07e never overwrites a value set after the preview | PASS |
| 07f HR managers only (officer refused; button flag) | PASS |
| label: old "Bảng lương Quốc gia" → "Quốc gia làm việc" (row and what the screen reads); Indonesian → "Negara Kerja"; a customer's own wording left alone; second run does nothing; both .po files carry the entry | PASS |
| 05b Payroll-ready %: equals (headcount − not payroll-ready) ÷ headcount | PASS |
| Upgrade path on a copy shaped like live (vi = "Bảng lương Quốc gia", module 19.0.1.0.0) → `-u pb_employee_form_tidy`: EXIT 0, 0 ERROR, `latest_version` 19.0.1.1.0, label "Quốc gia làm việc" / "Negara Kerja", every employee row byte-identical before / after (md5) | PASS |
| PO gate (platform reader): vi_VN and id_ID 46 rows each (23 code + 23 model), 0 empty, vendor word in msgstr 0 | PASS |

Touched suites, scoped (`-u pb_employee_form_tidy,pb_people,pb_records,
pb_hr_payroll_formula`, tags `/pb_employee_form_tidy,/pb_people,/pb_records,
/pb_hr_payroll_formula:TestEmployeeWorkTimezone`), each on its own copy:

| Run | Tests | Failed + errors |
|---|---|---|
| baseline: `origin/19.1` with the LIVE module 19.0.1.0.0 | 149 (module 23) | 0 + 0 |
| `tidy-e2` (19.0.1.1.0) | 156 (module 30) | **0 + 0** |

No test skipped. (The full 18-module run of TIDY-E is not repeated: nothing outside
this module changed.)

## 3. Deploy notes (with the Form builder go-live)

1. Ship `pb_employee_form_tidy` (files) and **`-u pb_employee_form_tidy`** on the five
   databases (payobook, payobook_template, p0clone, rize, sudima). Version
   19.0.1.0.0 → 19.0.1.1.0 (new column `pb_cow_fill_log.company_count`; upgrade step
   writes the vi / id Country of Work label where it is still an old wording — on
   the five live sites it was already corrected by hand, so it changes nothing
   there). Purge `/web/assets/%` and restart (template and tooltip changed).
2. **Press the button again on sudima and payobook** (HR manager, all companies
   ticked): People › Employees → "Fill Country of Work" → read the preview →
   leave "Also fill from the company's country" ticked → "Fill Country of Work".
   Expected (from the deploy report's counts): sudima 651 empty — 0 from pay
   set-up, ~651 from the company (Vietnam) if the company's country is Vietnam;
   payobook 66 empty (53 no contract + 13 no pay set-up) — from the company.
   Record the preview's two tables and the "Left empty" lines (counts only).
3. Not asked: rize (3 people without a contract — the preview would now offer
   their company's country), payobook_template (1), p0clone (12). Press there only
   if the owner says so.
4. After: People list "Payroll-ready %" changes meaning to "share ready to be paid"
   (sudima 99 % → about 0 % while its contracts are drafts; on every site the new %
   = 100 − "Not payroll-ready" ÷ headcount — read both figures before / after).

## 4. Owner questions

1. Should Rize's 3 people without a contract (two office logins, one demo person)
   also get their company's country from the button, or stay empty?
2. The "Payroll-ready %" on the People list now means "share ready to be paid"
   (running contract and approved bank), so Sudima will show about 0 % until its
   contracts are started. Is that the number you want to see there?
