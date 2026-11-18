# WDGAP Step 2 — "Government paperwork and bank files" — verified facts

Read-only fact-finding for the Step 2 design. **Source: `origin/19.1` @ `6843fa946`**
(2026-11-18 13:35 +1100), extracted with `git archive` into a scratch folder; every
`path:line` below is on that commit unless marked otherwise. Nothing was edited,
committed, checked out or run on the live server. UNVERIFIED = could not be proven from
the repo (usually a live-database fact).

Technical document: real model/module names are used. The white-label rule still binds
every user-visible string the build adds (ledger convention 1).

## 0. Scope rulings that override the ledger (read first)

| # | Fact | Where |
|---|---|---|
| 0.1 | Ledger D3 says Step 2 waits with Step 1 (only other-country bank files may proceed); WDGAP_DEFERRED row 2 says the same. | `docs/handovers/wdgap/WDGAP_LEDGER.md:19`; `WDGAP_DEFERRED.md:12` (main checkout) |
| 0.2 | **Owner started Step 2 on 2026-11-18 afternoon**: G1 countries first = Indonesia, Vietnam, India, Singapore (Malaysia NOT in the first set); G2 files read the customer's OWN pay figures, never the packs, Step 1 stays postponed, never edit `pb_pack_*`; G3 build from published official layouts, every file marked "Check with your adviser before first filing" until a customer confirms acceptance; G4 employees enter tax number + dependants on My Payobook, nothing reaches a payslip until HR approves, proof attachment. | `docs/handovers/wdgap/WDGAP_OWNER_RULINGS_2026-11-15.md:174-179` — **main checkout only, untracked, NOT on origin/19.1**. The ledger D-table and DEFERRED row 2 must be updated by the designer. |
| 0.3 | Ledger D2: do not touch `pb_pack_*` rates or tax methods. | `WDGAP_LEDGER.md:18` |

---

## A. What exists today for government output

### A.1 Module inventory

| Module (version) | What it is | Depends | Verdict |
|---|---|---|---|
| `pb_hr_govt` 19.0.1.1.0 | 5 Vietnamese social-insurance/labour XLSX reports via `report_xlsx` | base, hr, hr_contract, om_hr_payroll, report_xlsx (`pb_hr_govt/__manifest__.py:10-20`) | **Real file**, but see A.3 data issues |
| `pb_govt_reports` 19.0.1.2.2 | "Filings" board + stepped filing flow + approval proposal, front door over country wizards | web, pb_import_kit, **pb_hr_govt**, pb_hub, pb_hr_payroll_base, biz_approval_workflow (`pb_govt_reports/__manifest__.py:33,44-45`) | Real facade; honest about wizards that produce nothing |
| `pb_compliance_hub` 19.0.1.2.2 | Compliance hub, lenses Filings / Bank / Safeguards / Audit | — | Filings lens = `PbGovtReports` (`pb_compliance_hub/static/src/js/compliance_hub.js:102-115`) |
| `pb_statutory` 19.0.1.5.0 | Insurance & tax cockpit: rates, ceilings, brackets, "contribution actuals" of the latest run | om_hr_payroll, pb_hr_payroll_base, pb_import_kit… (`pb_statutory/__manifest__.py:5,10`) | Read-only board; produces no file |
| `pb_fund_payments` 19.0.1.1.0 | What is owed to each fund/tax office per month, from mapped pay items; approval; receipt; Excel export | mail, om_hr_payroll, pb_hr_payroll_formula, biz_approval_workflow, pb_approval_config, pb_pay_delivery, pb_payruns, pb_payhub, pb_hub, pb_import_kit, pb_filter_kit (`pb_fund_payments/__manifest__.py:35,40-52`) | Real; "no bank file is made from it" (`pb_fund_payments/models/fund_payee.py:116-119`) |
| `pb_hr_payroll_{vietnam,indonesia,india,malaysia,singapore,thailand,cambodia}` | Legacy per-country modules (memory `payobook-current-design`: LEGACY, not the live design) | — | Wizards below; mostly stubs |
| `pb_pack_{vn,id,in,my,sg,th}` 19.0.1.0.1 | Each = one `hr.formula.config.template` (scheme starter) + one legislation pack (rates). **No filing, no form, no bank content.** READ ONLY. | pb_hr_payroll_formula only (e.g. `pb_pack_id/__manifest__.py:16-20`) | Not a source for Step 2 (G2) |

### A.2 Every filing / file door and whether it really makes a file

| Door | Model.method | Produces | Numbers come from | Who | Real? |
|---|---|---|---|---|---|
| VN "Sickness & Maternity" BHXH630 | `pb.govt.report.wizard.action_export` → `report.pb_hr_govt.bhxh630_xlsx` | XLSX from template `pb_hr_govt/government/BHXH630.xls` | payslip lines by HARD-CODED codes `SICK`+`MAT` (`pb_hr_govt/report/bhxh630_report.py:73`); bank via `_bank_details` | ACL `group_pb_hr_govt_user` (`pb_hr_govt/security/ir.model.access.csv:5`) | Real file; placeholders `"SERIAL-001"` (`bhxh630_report.py:84`), `"0000000000"` account (`:90`) |
| VN Participant schedule BHXHDSTK01 (Mẫu 595) | same → `bhxhdstk01_xlsx` | XLSX, sheets Danhsach/Hogiadinh | "Tiền đóng" = `contract.wage` (`bhxhdstk01_report.py:75`); household sheet: headers only (`:87-98`) | same | Real, partial |
| VN Dossier cover D01-TS | same → `bangke_d01_xlsx` | XLSX | employee master | same | Real |
| VN Headcount increase / decrease (Tăng/Giảm lao động) | same → `tang_ld_xlsx` / `giam_ld_xlsx` | XLSX | `contract.wage`; codes `ALLOW`, `EXTRA` (`giam_ld_report.py:51-53`; `tang_ld_report.py:54`) | same | Real; note text still says "(TODO replace with actual codes)" (`giam_ld_report.py:60`) |
| VN "Mail report" | `pb.govt.report.wizard.action_mail_report` | nothing — info toast | — | — | **Stub** (`pb_hr_govt/wizards/govt_report_wizard.py:148-161`); unreachable from the flow by design (`pb_govt_reports/models/pb_filing_flow.py:24-28,71`) |
| SG CPF submission | `cpf.submission.wizard.action_generate_cpf_file` | **no file**; toast "CPF submission file generated successfully for %d employees." | lines matched by NAME `'CPF Employee' in l.name` (`pb_hr_payroll_singapore/wizards/cpf_submission_wizard.py:48-49`); payslips `state='done'`, **no company filter** (`:36-40`) | ACL payroll user (`pb_hr_payroll_singapore/security/ir.model.access.csv:2`) | **FALSE CLAIM** (`:56-73`) |
| TH SSF | `social.security.wizard.action_generate_ssf_file` | no file; "SSF submission file generated successfully…" | names `'SSF Employee'` (`pb_hr_payroll_thailand/wizards/social_security_wizard.py:48-49`) | payroll user | **FALSE CLAIM** (`:56-70`) |
| KH NSSF | `nssf.wizard.action_generate_nssf_file` | no file; "NSSF submission file generated successfully…" | names `'NSSF Employee'` (`pb_hr_payroll_cambodia/wizards/nssf_wizard.py:48-49`) | payroll user | **FALSE CLAIM** (`:56-70`) |
| MY EPF/SOCSO/EIS | `epf.wizard.action_generate_epf_file` | no file; "EPF submission file generated successfully…" | names `'EPF Employee'`, `'SOCSO …'`, `'EIS …'` (`pb_hr_payroll_malaysia/wizards/epf_wizard.py:56-61`) | payroll user | **FALSE CLAIM** (`:76-90`) |
| VN tax report (monthly/quarterly/annual) | `vietnam.tax.report.wizard.action_generate_report` | no file; "Vietnam tax report has been generated successfully" | nothing | no view and no ACL row found in repo (grep `vietnam.tax.report.wizard` in *.xml/*.csv: none) | **FALSE CLAIM, unreachable** (`pb_hr_payroll_vietnam/wizards/vietnam_tax_report_wizard.py:6-28`); opened by `hr_employee_vietnam.py:313-322`, `vietnam_payroll_dashboard.py:127-135` |
| VN social insurance report | `vietnam_payroll_dashboard.action_generate_vietnam_social_insurance_report` | opens model `vietnam.social.insurance.report.wizard`, **which does not exist** | — | — | **Dangling** (`pb_hr_payroll_vietnam/models/vietnam_payroll_dashboard.py:137-145`) |
| VN insurance analytics | `vietnam.insurance.analytics` | on-screen + PDF; Excel raises "will be implemented in a future update" (honest) | employee master `vn_si_salary_base` × policy rates, NOT payslips (`pb_hr_payroll_vietnam/wizards/vietnam_insurance_analytics.py:193,307-311`) | — | Analysis only |
| MY / KH payroll import wizards | `payroll.import.wizard.{malaysia,cambodia}` | toast "… imported successfully", imports nothing | — | — | **FALSE CLAIM** (`pb_hr_payroll_malaysia/wizards/payroll_import_wizard.py:18-35`; cambodia same file `:29`) |
| Base VN bank export wizard | `vietnam.bank.export.wizard.action_export_file` (base) | toast "exported successfully" | — | — | Stub in base (`pb_hr_payroll_vietnam/wizards/vietnam_bank_export_wizard.py:21-30`), **overridden with a real generator** by pb_pay_delivery (`pb_pay_delivery/models/bank_export_wizard.py:362-382`) |
| **Indonesia, India** | — | — | — | — | **Nothing at all**: not in the Filings catalogue (`pb_govt_reports/models/pb_govt_reports.py:22-49`), no wizard in either module; no year-end certificate/return anywhere (grep Form 16/24Q/1721/bupot/SPT/PND/EA/IR8A/05-QTT: no code hits) |

### A.3 The filing flow (pb_govt_reports) — the seam a new filing plugs into

* Catalogue `_CATALOG` country → wizard model + tiles (`pb_govt_reports/models/pb_govt_reports.py:22-49`); tile shown only if the wizard model is installed (`:86-95`). Countries chip row = company country + `hr.formula.config.country_code` of the company's schemes (`:72-83`).
* Flow `pb.filing.flow` (AbstractModel): `ADAPTERS` allow-list per country (model, key field, period kind, writable fields) (`pb_filing_flow.py:84-121`); generate method names are CONSTANTS `_GENERATE` (`:61-67`) guarded by `_ONLY_GENERATE` send/submit vocabulary (`:71`, test `pb_govt_reports/tests/test_p7_filing.py:155`).
* Permission: payroll officer or manager (`_FILING_GROUPS`, `pb_filing_flow.py:76-77`, `_require_officer` `:405-421`). The Filings LENS gate is a different group: `pb_hr_govt.group_pb_hr_govt_user` (`pb_compliance_hub/static/src/js/compliance_hub.js:66`).
* Approval: `generate()` writes a `pb.filing.proposal` (process key `filing`, one step "Payroll manager", seeded per company) and produces the file on apply (`pb_filing_flow.py:456-506`; `pb_govt_reports/models/filing_approval.py:37-118`; catalogue row `pb_approval_config/data/processes.xml:99`).
* Materialise: an `ir.actions.report` is rendered and stored as an `ir.attachment` with NO `res_model` (creator + admin only) (`pb_filing_flow.py:541-579`); a `display_notification` is reported as "produced no file" (`:515-539`). No download log line (UNVERIFIED that any trail is written beyond the proposal).

### A.4 Data issues inside the VN reports (pb_hr_govt)

| Issue | Where |
|---|---|
| Pay figures read by hard-coded rule CODES (`ALLOW`, `EXTRA`, `SICK`, `MAT`) — a customer's own scheme codes (e.g. Rize `LUONGHOPVND`, `NGUOIPHUTHUO`, `docs/handovers/fillin/FILLIN_P1_REPORT.md:207-208`) never match | `pb_hr_govt/models/report_base.py:58-65,81-87`; `report/giam_ld_report.py:52-53`; `report/bhxh630_report.py:73` |
| Payslips in range include `draft` and `verify` states | `report_base.py:47-56` |
| "Mã sổ BHXH" (insurance book no.) column written from `identification_id`; the real field `vietnam_social_insurance_number` exists but is unused | `bhxhdstk01_report.py:33,64`; `giam_ld_report.py:31,63`; field `pb_hr_payroll_vietnam/models/hr_employee_vietnam.py:12` |
| Wage = `contract.wage`, not the insurance base or a payslip figure | `bhxhdstk01_report.py:75`; `giam_ld_report.py:51` |
| Bank details resolved "as Pay & Deliver sees it" | `report_base.py:206-237` |

### A.5 Other statutory readers that use hard-coded codes (same disease)

| Reader | Codes | Where |
|---|---|---|
| `pb_statutory` contribution actuals | `CONTRIB_MAP` SI_EMP/SIEMP/HI…/UI… | `pb_statutory/models/pb_statutory.py:43-51,197-210` |
| My Payobook tax sheet `/my/taxsheet` | system parameter `pb_me_portal.tax_codes`, default `GROSS,SIEMP,HIEMP,UIEMP,PIT` | `pb_me_portal/models/hr_payslip_ess.py:12,16,43-63`; route `pb_me_portal/controllers/portal.py:450-505` |

---

## B. How a pay item is classified today

| Concept | Lives on | Values | Where |
|---|---|---|---|
| Pay item / component | `hr.formula.rule` (per scheme `hr.formula.config`) | code, name, `column_type` input/formula/constant | — |
| Scheme country | `hr.formula.config.country_code` | VN ID IN SG MY TH KH PH | `pb_hr_payroll_formula/models/formula_config.py:116-125` |
| Pay role (component) | `hr.formula.rule.net_role` (+ `net_role_detail` "Included in another total", source/confidence/reason) | earning, deduction, net, employer_cost, info, mixed | `pb_hr_payroll_formula/models/formula_net_role.py:602-622` |
| Pay role (payslip line, copied at compute) | `hr.payslip.line.pay_role`, `component_detail`, `component_type` | same | field `pb_hr_payroll_formula/models/hr_payslip_line.py:14,27,48-56`; copy `hr_payslip_formula.py:1012-1015` (also `payroll_import_batch.py:4037`) |
| Value type | `hr.formula.rule.value_kind` | money, decimal, integer, quantity, rate, identifier, text, date, boolean | `formula_rule.py:808-826` |
| Column role | `hr.formula.rule.column_role` | payroll, identity, profile, contract, bank, reference | `formula_rule.py:772-780` |
| Report group | `hr.formula.rule.component_type` (Char, "the category" people see) | free text | `formula_rule.py:142` |
| Legacy category type / taxable | `hr.salary.rule.category.category_type`, `is_taxable` | — | `pb_hr_payroll_base/models/hr_payroll_structure_base.py:229-239` — **unmaintained, do not use** (`hr_payslip_line.py:33-46` comment) |
| Pack link | `legislation_code` inside pack templates' `components_json` | e.g. JHTEE | `pb_pack_id/data/config_template_id.xml` (READ ONLY) |

**One pay-band rule.** `hr.payslip.line.pb_pay_band / pb_counts_in_totals / pb_pay_totals / pb_net_line` read `pay_role` first, category only for pre-stamp lines; DED/ERCOST counted by `abs()` (`om_hr_payroll/models/pay_bands.py:34-41,58-89,91-118,168`; payslip-level `:195`); per-payslip override in `pb_payruns/models/payslip_money.py:21`; SQL twin `pb_payruns/models/hr_payslip_run.py:398-407` `_pb_bucket_sql`. Bank file pays the take-home LINE (`pb_net_line`, `pb_pay_delivery/models/bank_export_wizard.py:74-83`; `pay_hold.py:92`).

**Is there any pay item → government form line mapping?** **No.** grep for form_line / filing_line / statutory_line / box_code / tax_box / statutory_role on origin/19.1: no model field. The only "pay item → outside body" mapping that exists is **`pb.fund.payee.item`** (rule_id + share employee/employer, one item one payee) (`pb_fund_payments/models/fund_payee.py:279-300`). The pack's `Tax Map` sheet maps statutory RATES to cells, not outputs (`docs/design/COUNTRY_TAX_WORKBOOK_MAPPING.md`, §"Tax Map").

**Where a form-line mapping would naturally attach**

| Option | Seam | Notes |
|---|---|---|
| 1 (closest precedent) | New model `(form, line, rule_id, sign/share)` keyed on `hr.formula.rule`, company-scoped, clone of `pb.fund.payee.item` | Read figures exactly as fund payments do: SQL over `hr_payslip_line` joined to `hr_payslip` on `(s.formula_config_id, l.code)`, done states, by pay month (`pb_fund_payments/models/fund_payment.py:262-310`). Suggest pass pairs EE/ER by name stem (`fund_payee.py:45-90`). |
| 2 | Extra column on Mapping › **Component treatment** (`pb_formula_studio/static/src/js/mapping/mapping_studio.js:143-146`, board `component_treatment.js:104-107`) via `hr.formula.config.value_kind_board` / `set_component_setup` (`pb_hr_payroll_formula/models/formula_config.py:2429`, `:2603`) | A plain new field on `hr.formula.rule` does NOT trip the live-scheme gate (gate only watches `excel_formula, python_formula, constant_value, column_type`, `pb_hr_payroll_formula/models/scheme_gate.py:43-44,219-235`) nor the content stamp (`scheme_gate.py:58-80`). One-field-per-rule cannot hold "one item on two forms". |

**Figures a form needs that are NOT payslip lines.** Lines exist only for rules with `appears_on_payslip` and a numeric value kind (`hr_payslip_formula.py:932-950`); tax bases, insurance bases, dependants count are often info-only inputs. Their per-payslip values sit in `hr.payslip.formula_computed_values` (JSON Text, `hr_payslip_formula.py:81-85`), which the engine's own year-to-date reads (ledger W2D2-4). Fund payments warns when a mapped item is not on payslips (`pb_fund_payments/models/fund_board.py:558-560`). A form-line reader must decide: lines only, or lines + `formula_computed_values`.

---

## C. Bank files

### C.1 The Vietnamese bank file (pb_pay_delivery 19.0.1.8.1, `__manifest__.py:32`, hard dep on `pb_hr_payroll_vietnam` `:39`)

| Piece | Fact | Where |
|---|---|---|
| Layout model | `pb.bank.file.layout` (name, `bank_format` Char unique, `file_type` csv/txt/xlsx, `delimiter`, `encoding`, `with_header`, `note`, audit mixin) + `pb.bank.file.column` (sequence, header, `source`, literal, `width`, `pad` right/left/zero, `number_format` none/int/int_grouped) | `pb_pay_delivery/models/bank_file_layout.py:33-108` |
| Column vocabulary | account_number, account_name, bank_name, bank_branch, employee_code, employee_name, net_amount, period, company_account, row_number, literal — **no** date, currency, bank code/BIC, total, count, reference sources | `bank_file_layout.py:18-30` |
| Shipped layouts (data, `noupdate="0"` — rewritten on every upgrade) | generic CSV, vietcombank, bidv, techcombank, mb_bank (xlsx), vietinbank (fixed-width txt), acb; all marked INFERRED | `pb_pay_delivery/data/bank_file_layouts.xml:2-13,16-300` |
| Generator | `vietnam.bank.export.wizard._generate` (inherits the base stub): resolve layout by `bank_format`, done slips minus paid-other/unpaid-only, rows sorted by name, exclusions with reasons, build csv / txt / xlsx, sha256 | `pb_pay_delivery/models/bank_export_wizard.py:34-335`; builders `:179-231` |
| Row sources | reads the four **`vietnam_bank_*` Chars** on `hr.employee` (`pb_hr_payroll_vietnam/models/hr_employee_vietnam.py:47-50`), matches the bank against the **VN-only** `pb.bank.registry`; reasons: On hold, invalid account (6–19 digits), missing holder, **unknown bank**, no net pay | `bank_export_wizard.py:106-146` |
| Writers | csv: `csv.writer`, CRLF, header = column headers only (`:179-187`); txt: concatenated padded cells, CRLF, optional header line (`:189-198`); xlsx: one sheet "Transfer", styled header (`:200-231`). **No header/trailer records, no control-total row, no batch record** | same |
| Stored file + approval | `pb.bank.file` (`_approval_process_key='bankfile'`, states draft/pending/approved/returned/rejected/superseded; attachment, `file_hash`, `approved_hash`, control total, rows, `excluded_json`, `slip_ids`) — `prepare()` is the only way a file is made; supersedes the last try | `pb_pay_delivery/models/bank_file.py:37-120,140-202` |
| Download gate | approved + re-hash equals `approved_hash`, writes `downloaded_*` + one audit line | `bank_file.py:602-639` |
| Who | `PAY_GROUPS` (payroll manager, finance groups) + admin, `require_pay` / `_require_access` | `pb_pay_delivery/models/approval_common.py:33,54-63`; `pb_pay_delivery.py:33-40` |
| Screen | Pay & deliver lists every layout as a bank choice (`pb_pay_delivery.py:405-407`); `prepare_bank_file(run_id, bank_format, company_account)` submits to the engine (`:496-504`); download `:506` | — |
| Catalogue row | process `bankfile` | `pb_approval_config/data/processes.xml:62-63`; seed `pb_pay_delivery/models/approval_seed.py:56,141-199` |

### C.2 "Payment list (any bank)" (WDGAP IDB1/IDB2)

| Piece | Fact | Where |
|---|---|---|
| Builder | `pb.payment.list` (AbstractModel): door = bank-file door + run read rule (`_pb_check_door`); slips = done, not paid-other, not held, not paid (`_pb_slips`) | `pb_pay_delivery/models/payment_list.py:91-155` |
| Account | **`hr.employee.bank_account_ids[:1]` (`res.partner.bank`)** = the approved account (S6-A); branch only when the VN chars hold the same number | `payment_list.py:234-245` |
| Amount | `pb_pay_totals()['net']`, rounded in the payslip's money; check when it differs from the take-home line | `payment_list.py:246-268` |
| Columns | employee number, name, holder, bank, branch, account, amount, currency, reference, in bank file, check | `payment_list.py:109-122` |
| Totals | one per currency, never added across | `payment_list.py:303-317` |
| Stored + approval | `pb.payment.list.file` on the **same** process key `bankfile` (no own seed, capabilities delegated to `pb.bank.file`); stores xlsx AND csv, sha256 of both; download = approved bytes only + trail line | `payment_list.py:512-840`; report `docs/handovers/wdgap/WDGAP_IDB1_REPORT.md:164-200` (IDB2) |
| Owner rulings | IDB1a general file now, bank-specific layout later once the paying bank is known; IDB2 same second approval; IDB3 list everyone | `WDGAP_OWNER_RULINGS_2026-11-15.md:166-171` (main checkout) |

### C.3 Bank identity storage

| Store | Fields | Where |
|---|---|---|
| `res.bank` (core) | name, bic, country, address… — **no national clearing code** | `~/odoo19/odoo/odoo/addons/base/models/res_bank.py:22-33` (local core checkout; server copy UNVERIFIED but same series) |
| `res.partner.bank` (core) | acc_number, **`clearing_number`**, acc_holder_name, bank_id, bank_bic (related), currency_id, allow_out_payment | same file `:88-103` |
| Our resolvers create `res.bank` with name (+ bic) only, never country or clearing code | `pb_bank_ocr/models/pb_bank_two_stores.py:52-72`; `pb_hr_payroll_formula/models/payroll_import_batch.py:3489-3511` |
| `pb.bank.registry` | name, short_name, swift_prefix, aliases, company — **Vietnamese banks only, no country field**, 40 records | `pb_bank_ocr/models/vn_bank_dictionary.py:68-115`; `pb_bank_ocr/data/vn_bank_registry_data.xml` |
| VN chars on employee | vietnam_bank_name/branch/account_number/account_name (also on `hr.contract` `hr_contract_vietnam.py:28`) | `hr_employee_vietnam.py:47-50` |
| Two stores kept in step | S6-A mirror + read-only check `hr.employee.pb_bank_store_check` | `pb_bank_two_stores.py:1-22` |
| Indonesian / Indian / Malaysian bank codes | **none stored anywhere.** IFSC/"bank code" headers are classified into the BIC lane on import (`pb_formula_studio/models/pb_formula_studio.py:11828-11829`; `pb_hr_payroll_formula/models/column_role_classifier.py:177-182`). Rize SG/ID doc: "domestic routing codes remain separate from BIC" — no field found that holds them (UNVERIFIED where, if anywhere, they were kept) | `docs/deploy/2026-10-19-rize-singapore-indonesia-client-masters.md:24-25` |
| Rize ID paying bank | client workbook had "BCA reports" (excluded from the template) — suggests BCA; owner has NOT confirmed the paying bank | `docs/design/COUNTRY_TAX_WORKBOOK_MAPPING.md:37`; ruling IDB1a |

### C.4 Cleanest seam for pluggable bank layouts (analysis)

* The layout engine is already data-driven, BUT the "adding a bank is a data file, zero code" claim (`bank_file_layout.py:7`, `bank_file_layouts.xml:2-12`) is **false**: `vietnam.bank.export.wizard.bank_format` is a `Selection` (`pb_hr_payroll_vietnam/wizards/vietnam_bank_export_wizard.py:11-17` + `selection_add` vietinbank/acb `pb_pay_delivery/models/bank_export_wizard.py:37-39`). A new layout row with `bank_format='bca'` is listed on Pay & deliver (`pb_pay_delivery.py:405-407`) but `pb.bank.file.prepare` → `wizard.create({'bank_format': 'bca'})` (`bank_file.py:160-166`) would be refused by the selection (by reading; not executed).
* The VN generator cannot serve non-VN banks: it reads the VN chars and refuses banks outside the VN registry (`bank_export_wizard.py:113-129`). The payment list already reads the right store (`res.partner.bank`) and the right amount, and already has its own approved-file record.
* Suggested seam (design input, not a fact): extend `pb.bank.file.layout` with `country_id`, optional currency, header/trailer line templates and extra column sources (date, bank BIC/clearing code, currency, total, count, reference), and render **payment-list rows** (`pb.payment.list._pb_build_rows`, `payment_list.py:221-323`) through a layout into `pb.payment.list.file` — no new module per bank, no `bank_format` selection. Layout data files must be `noupdate="1"` or per-company copies, since `noupdate="0"` overwrites edits (`bank_file_layouts.xml:2`). Keep the VN golden test (`pb_pay_delivery/tests/test_wdgap_idb1_vn_golden.py:105-107`) byte-identical.

---

## D. Employee tax details

### D.1 Fields that exist per country

| Country | Field | Model | Where |
|---|---|---|---|
| VN | `vietnam_tax_code`, `vietnam_social_insurance_number`, `vietnam_marital_status`, `vietnam_dependents_count`, `vietnam_spouse_name/_tax_code`, `vn_tax_regime`, `vn_residency_status` | hr.employee | `pb_hr_payroll_vietnam/models/hr_employee_vietnam.py:12-13,35-44,187-195` |
| VN | `vietnam_tax_code`, `vietnam_social_insurance_number` (duplicate copies) | hr.contract | `hr_contract_vietnam.py:25-26` |
| VN | dependants `vn_dependent_ids` → `vietnam.employee.dependent` (has `tax_registration_number`, `tax_allowance`), `vn_eligible_dependent_count` (computed) | hr.employee | `hr_employee_vietnam.py:214-227`; `vietnam_employee_dependent.py:44,72` |
| VN | `pb_vn_tax_resident`, `pb_vn_tax_commitment` | hr.employee | `pb_payroll_mapping_vn/models/hr_employee.py:33-35` |
| any | `subject_to_pit` (Char) | hr.employee | `pb_hr_payroll_formula/models/hr_employee.py:36` |
| ID | `pb_npwp_number`, `pb_family_card_number`, `pb_bpjs_employment_number`, `pb_bpjs_health_number` (HR group) | hr.employee | `pb_employee_vault/models/payroll_profile.py:22-25` |
| ID | PTKP status: **no field** on employee/contract (grep ptkp in model fields: none) | — | — |
| IN | `pan_number`, `uan_number`, `esi_number` (+ legacy rates) | **hr.contract** | `pb_hr_payroll_india/models/hr_contract.py:12-22` |
| IN | tax regime: **no field** (only pack text) | — | `pb_pack_in/__manifest__.py:9` |
| SG | `singapore_nric_fin`, `singapore_tax_residency` | hr.contract | `pb_hr_payroll_singapore/models/hr_contract_singapore.py:26-31` |
| MY | only Zoho staging (`epf_number`, `socso_number`, `income_tax_number`) — nothing on the employee | `pb_hr_payroll_malaysia/models/zoho_employee_data.py:11-13` |
| core | `marital`, `children`, `identification_id`, `passport_id`, `permit_no` | hr.employee (core) | — |
| HR "Full details" shows VN and ID tax groups only (no IN/SG/MY group) | `pb_employee_vault/models/employee_details.py:135-158` |

### D.2 What the pay formulas actually read

* A formula reads only COMPONENT values (pay data file / connected system / contract components `hr.contract.advantage` `om_hr_payroll/models/hr_contract.py:7-8` / application sources `hr.formula.rule.application_source_key` `pb_hr_payroll_formula/models/application_payroll_source.py:894`). No employee tax field is read directly.
* **VN dependants**: two different numbers at Rize. (a) "Dependents count / VNDEPCOUNT" = a Guided Count transformation over `vn_dependent_ids` at calculation time, **counting every saved record including pending** (`pb_hr_payroll_vietnam/models/dependent_count_source.py:19-79`, esp. `:39,47`); (b) "Registered tax dependents (VNREGISTER)" = a separate **contract component**, kept as the owner's final choice (`docs/deploy/2026-10-18-vietnam-dependents-and-records-template.md:3-8,19-24`). Which one Rize's PIT formula reads: **UNVERIFIED** (needs the live scheme 7118 formulas).
* pb_me_details E1 writes/ends `vietnam.employee.dependent` rows only after HR's tick (`pb_me_details/models/family.py:9-14,151-197`) — it never touches the VNREGISTER contract component.
* **ID PTKP**: Rize scheme reads PTKP status as a pay-data-file text column (S/0…M/3 guard, `tools/prepare_rize_sg_id_master.py:148`); the pack template uses inputs `DEPS` + `MARRIED` (`pb_pack_id/data/config_template_id.xml`, components_json). Nothing on the employee record feeds it.
* **IN**: at Rize, salary TDS, profession tax and employee PF are **approved monthly inputs** (not computed) (`docs/deploy/2026-10-19-rize-india-client-master.md:21-22`); no regime field. India tax year = April on scheme 7119 (memory `wdgap-program`, ruling 2026-11-15).
* **MY / SG**: SG CPF and self-help are reviewed monthly inputs on the Rize SG scheme (`docs/deploy/2026-10-15-rize-singapore-configuration.md:12-14`).

### D.3 The "employee proposes → HR approves" pattern to reuse (pb_me_details 19.0.1.0.0)

| Piece | Fact | Where |
|---|---|---|
| Request model | `pb.me.detail.request` (mail.thread + `biz.approval.chain.mixin`): kinds family add/change/remove, id_paper, photo, marital; states draft → hr_review → approved/refused; create only under sudo from the portal; write refused outside the chain | `pb_me_details/models/detail_request.py:30-160` |
| Per-kind whitelist | `PORTAL_FIELDS` | `detail_request.py:63-73` |
| Portal create | `pb_portal_create(employee, kind, values, member, upload, request_id)` — own employee only, one open request per kind/member, attachment made server-side, ONE savepoint, then `_pb_send` | `detail_request.py:231-300` |
| Apply | `_pb_apply` writes exactly what was proposed (sudo) | `detail_request.py:357-422`; adapter hooks `:454-493` |
| Approval | `register_chain('pb.me.detail.request', 'me_details', submit_state='hr_review', driven=('approved',))`, no date field; facts `kind`, `counts_for_tax`; before/after rows for the inbox | `pb_me_details/models/detail_approval.py:21-28,50-140` |
| Seed | `_approval_seed_default` (HR lead role step) + `res.company.create` + `seed_all` from `post_init_hook` | `detail_approval.py:150-191`; `pb_me_details/__init__.py:10`; catalogue row `data/approval_process.xml:6-13` |
| Tax tick (E1) | VN only: approved family change → `tax_state='waiting'`; only `action_confirm_tax` (pay team `om_hr_payroll.group_hr_payroll_user`) writes the dependant | `family.py:28-37,111-197` |
| Proof file | ID paper scan filed as a vault document; vault categories REQUIRE an expiry (ledger S6A-3) | `detail_request.py:46-53,423-450` |
| Bank precedent | bank changes go through `pb.bank.change.request` with ONE second person (S6-A BK1/BK2) | `WDGAP_S6A_REPORT.md` §"Bank details" |

### D.4 pb_me_portal hook points (never edit pb_me_portal itself)

| Hook | Where | Use |
|---|---|---|
| `TILES` registry (`TILES.setdefault(url, {group, icon, tone, seq})` at import), `GROUPS = ('me','time','growth','people','more')` | `pb_me_portal/models/pb_me_home.py:58,94-100,202-215`; example `pb_me_details/models/pb_me_home.py:14-27` | home tile; seq after pb_me_portal's own rows (ledger S6M-4) |
| `_pbme_needs_extra(emp, put)` | `pb_me_home.py:730-746` | "Needs you" row |
| `_pbme_extra_cards(emp)` (+ `_safe` savepoint wrapper) | `pb_me_home.py:323-349` | bento card |
| `_my_requests_sources()` | `pb_me_home.py:749-760`; example `pb_me_details/models/pb_me_home.py:54-88` | "My requests" rows |
| Controller base `PbMePortal` + `_ess_employee()` (session's own employee; no route takes an employee id) | `pb_me_portal/controllers/portal.py:55`; subclass `pb_me_details/controllers/portal.py:20,38` | new `/my/...` pages |
| QWeb inherit of `pb_me_portal.portal_my_profile` (`.pbme-detail-side`) and `portal.portal_my_home` | `pb_me_details/views/portal_templates.xml:22-43` | door cards |
| `/my/taxsheet` reads `pb_me_portal.tax_codes` param | `hr_payslip_ess.py:12,16`; `controllers/portal.py:450-505` | a year-end certificate download could sit beside it (design) |

---

## E. Which countries the live customers use (repo + memory only)

| Database | Countries | Pay worked out from | Where |
|---|---|---|---|
| `rize` (Rize Farms) | **VN** (scheme 7118 `RIZE_VN_FOCUSED_2026`), **IN** (7119 `RIZE_IN_FOCUSED_2026`), **SG** (7120 `RIZE_SG_FOCUSED_2026`), **ID** (7121 `RIZE_ID_FOCUSED_2026`) | **The customer's own scheme formulas**, rebuilt from the client's workbooks (VN 185→130 components; ID 461→403), not `pb_pack_*` | `docs/deploy/rize-focused-payroll-20261021.txt` (table "Rize replacement schemes"); `docs/deploy/2026-10-18-vietnam-payroll-master-v3.md:1-40`; `2026-10-19-rize-india-client-master.md:1-22`; `2026-10-19-rize-singapore-indonesia-client-masters.md:1-30` |
| `rize` headcounts (approx.) | ID ~113–122 people (126 at Indonesian banks); VN ~70; IN ~54 payslips on 7119; SG small | memory `paydata-review-program`, `wdgap-program`; `WDGAP_IDB1_DEPLOY_REPORT` via ledger row IDB1-deploy (`WDGAP_LEDGER.md:72`: 122 people, IDR) |
| `sudima` (Sudima Panels Vietnam) | **VN** only | Customer's own workbook ("Sudima September payroll review", audited cell extracts) | `docs/deploy/SUDIMA_PAYROLL_REVIEW.txt:1-20`; memory `sudima-demo-program` |
| `payobook` | demo; VN demo world (pb_demo) + an SG Company | pb_demo generator schemes (memory `pb-demo-environment`, `demo-world-payroll-figures-fixed`) | — |
| `payobook_template`, `p0clone` | UNVERIFIED | — | — |
| Real use | rize and sudima are production DBs but **pay runs are trials** (owner 2026-11-15) | memory `tenants-not-yet-in-use` |
| Pack use | "whether any live customer's pay is worked out from a pb_pack_* pack" was still marked open | memory `wdgap-program` line 23 — the repo docs above show Rize and Sudima are NOT pack-based (live confirmation UNVERIFIED) |
| Which legacy country modules are installed per DB | UNVERIFIED (needs `ir_module_module` on the server) | — |

Consequence (fact-based): every existing reader that keys on fixed codes or line names (A.4, A.5, A.2 SG/TH/KH/MY) would read nothing or the wrong thing on Rize/Sudima schemes. A Step 2 file must read the customer's items through a mapping (B).

---

## F. Precedents to clone

| # | Need | Precedent | Where |
|---|---|---|---|
| i | File-producing record with approval + hash + logged download | `pb.payment.list.file` (newest; stores xlsx+csv, sha256, shares `bankfile` route, approved-bytes-only download, trail line) and `pb.bank.file` | `pb_pay_delivery/models/payment_list.py:512-840`; `bank_file.py:53-639`; audit helper `approval_common.py:139-170` |
| i-b | Statutory filing produced on approval | `pb.filing.proposal` (`biz.approval.proposal.mixin`, process `filing`) + flow materialise | `pb_govt_reports/models/filing_approval.py:44-150`; `pb_filing_flow.py:456-579` |
| ii | Settings screen mapping pay items to a category | Fund payees: `pb.fund.payee` + `pb.fund.payee.item(rule_id, share)`, one-item-one-payee constraint, Suggest from pay roles; board methods `get_payees / item_options / save_payee / suggest / create_from_suggestions` | `pb_fund_payments/models/fund_payee.py:94-338`; `fund_board.py:537-700`; reading `fund_payment.py:247-330` |
| ii-b | Per-component axis on one board | Component treatment `value_kind_board` / `set_component_setup` | `pb_hr_payroll_formula/models/formula_config.py:2429,2603`; `pb_formula_studio/static/src/js/component_treatment.js:104` |
| iii | My Payobook page through hooks | `pb_me_details` (tile, needs-you, my-requests, controller subclass, QWeb door) | D.4 rows |
| iv | vi/id PO gate test | `pb_me_details/tests/test_po_gate.py:1-42` (parse, module line, occurrence, code marker, non-empty msgstr, no "odoo" in msgstr); header must say "Payobook 19.0" (ledger S6M-3) | — |
| v | Approvals-inbox process key + per-company seed | catalogue XML row + `_approval_seed_default` + `res.company.create` + `seed_all` in `post_init_hook` | `pb_me_details/data/approval_process.xml:6-13`, `detail_approval.py:150-191`; money variant `pb_fund_payments/data/approval_process.xml:8-17` (`money=True`, `bulk_ok=False`), `fund_approval.py:58-145`; sharing an existing key without a seed: IDB1-6 |
| vi | Byte-golden test for an existing file | `pb_pay_delivery/tests/test_wdgap_idb1_vn_golden.py:105-107` (compare xlsx minus `docProps/`, ledger IDB1M-3) | — |

---

## G. Risks and traps that bear on Step 2

### G.1 From the WDGAP ledger (`docs/handovers/wdgap/WDGAP_LEDGER.md`)

| Row | Why it matters here |
|---|---|
| D2 (`:18`), G2 | Never edit `pb_pack_*`; files read the customer's own pay items. |
| W2D2-1 (`:237`) | Take-home = FIRST net-role line (`pb_net_line`); a second net line is never read. |
| W2D2-2 (`:238`) | Deductions/employer cost counted by size (`abs()`); refunds count as more unless `pb_backpay_band_amount`. A tax-return total must use the same rule or say why. |
| W2D2-3 (`:239`) | Themed payslip PDF sums by CODE — back-pay lines land inside the item's figure. |
| W2D2-4 (`:240`) | Running totals read `formula_computed_values`, not lines; Updates YTD reads lines by code. Year-end certificates must pick one and match the payslips. |
| W2A-4 (`:206`), W2-A | Tax year follows the scheme (`tax_year_start_month`, helper `pb_hr_payroll_formula/models/tax_year.py`); India = April on rize 7119. Year-end = tax year, not calendar. Reports YTD still calendar (`WDGAP_DEFERRED.md:21-22`). |
| W2B-1 (`:197`) | `_pb_slip_totals` keeps any line whose CATEGORY is NET; fixtures must carry the category their pay role implies. |
| S6C-3 (`:335`) | An appended line on a payslip with no pay roles must carry none, or take-home becomes 0 everywhere. |
| W2B-2, S6A-1, W2D1-1 (`:198,:316,:223`) | Engine runs context/apply AS THE DECIDER; adapters read/write under sudo after their own gate; test with a decider who holds no payroll/formula group. |
| W2B-3 (`:199`) | `SEATED_MODELS` is a fixed tuple — a new money-out model inherits the seat hook itself. |
| PRB-W1 (`:171`) | No `date_field` in `register_chain` for anything that can be dated in the past. |
| IDB1-2 (`:357`) | `bank_account_ids` is HR-only in core — read under sudo after the door. |
| IDB1-3 (`:358`) | IDR has 2 decimals here ("7500000.00"); bank formats usually want integers. |
| IDB1-6, IDB1M-1 (`:361,:366`) | Same process key = same route; rize's `bankfile` route is "No approval needed" (owner decision 18 Sep) — a probe must not expect a waiting step. |
| IDB1M-2, IDB1F-1, IDB1F-3 (`:367,:370,:372`) | Door ≠ record rule mismatch on the list; `money_out_rules.xml` is `noupdate="1"` (rewrite by migration); real payroll officer = `pb_hr_payroll_base.group_payroll_base_officer` + app group. |
| IDB1M-3, IDB1M-4 (`:368-369`) | XLSX bytes differ by `docProps/core.xml` timestamp; a rolled-back probe still writes filestore files (patch `ir.attachment._storage`). |
| IDB1-1, S5M-3/S6C-2 (`:356,:262,:334`) | `hr.payslip.run` has no `company_id`; a two-company run breaks Pay & deliver with one company ticked. |
| QF2-G1, W2B-5 (`:142,:201`) | `with_context` carries `allowed_company_ids`; set it explicitly in jobs/tests. |
| S6A-3, S6A-6 (`:318,:321`) | Vault categories require expiry; portal create + PDF in ONE savepoint. |
| S6A-4, S9B-5, S6M-4 (`:319,:305,:347`) | New My Payobook tile: `pb_me_portal` home tests pin tiles; use `TILES.setdefault` with a seq after its rows. |
| S6A-8 (`:322`) | A published privacy notice sends every /my test to the notice first. |
| S6A-5, PRD-3, S5F-3, S8B-4, S6M-3, PRA-4 (`:320,:187,:294,:273,:346,:183`) | PO rules: name the alias `_`; one-line msgids; merge PO text-level; selection labels via `_description_selection`; header "Payobook 19.0"; no duplicate msgid. |
| S9A-4, W3M-3, S5M-5 (`:299,:355,:264`) | No PDF engine on the Mac (tests get HTML); shell renders need `force_report_rendering`; report preview title "Odoo Report" is a white-label leak — any PDF certificate must set its own title (S5F-2 `:293`: title via Python `_()`). |
| PRB-W5 (`:175`) | `%` formatting in portal `t-att-*` breaks the whole page; browser-walk every portal page. |
| S8B-1 (`:270`) | `vietnam_contract_type` defaults to `indefinite` on every contract — not a fact for a filing. |
| W2M-4 (`:227`), S5M-2 (`:261`) | Many rize trial runs refuse to recompute / give take-home 0 without the file: pick runs that compute for any golden or rehearsal. |
| Convention 9 (`:106-108`) | Tenant email is OFF on rize/sudima/p0clone: no "email the filing" path may fail. |
| PRE-3 (`:213`) | Pay & deliver AccessError for a pay-team member not involved in the release request (pre-existing). |

### G.2 New traps found in this fact-finding (add to the ledger)

| # | Trap | Where |
|---|---|---|
| S2F-1 | `pb.bank.file.layout` "zero code" is false: the wizard's `bank_format` is a Selection; a new layout key is listed on screen but refused at prepare. | C.4 |
| S2F-2 | `bank_file_layouts.xml` is `noupdate="0"`: every `-u pb_pay_delivery` rewrites shipped layouts (customer corrections lost). | `pb_pay_delivery/data/bank_file_layouts.xml:2` |
| S2F-3 | VN filings include draft/verify payslips and read fixed codes; the insurance-book column carries the national ID. | A.4 |
| S2F-4 | SG/TH/KH/MY wizards: no company filter, match lines by English NAME substrings, claim a file was made. Retire or rewire before any Step 2 tile reuses them. | A.2 |
| S2F-5 | VN dependants: record count (incl. pending) vs the VNREGISTER contract component; My Payobook E1 feeds only the records. A tax-details form must decide which number it changes. | D.2 |
| S2F-6 | Info-only figures (tax/insurance bases) have no payslip line; only `formula_computed_values` holds them. | B |
| S2F-7 | `pb_govt_reports` hard-depends on `pb_hr_govt` (VN); `pb_pay_delivery` hard-depends on `pb_hr_payroll_vietnam`. A non-VN filing module must not inherit those hard deps by accident. | `pb_govt_reports/__manifest__.py:44`; `pb_pay_delivery/__manifest__.py:39` |
| S2F-8 | Filings lens gate (`pb_hr_govt.group_pb_hr_govt_user`) differs from the generate gate (payroll officer/manager) — a person can see the board and be refused, or hold the right but not see it. | A.3 |
