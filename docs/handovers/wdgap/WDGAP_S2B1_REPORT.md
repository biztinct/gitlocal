# WDGAP S2-B1 report — year-end tax paperwork (ID, VN, IN, SG) + the employee's own certificate

Builder, 2026-11-18. Branch `wdgap-s2b1` (from `origin/wdgap-s2a` @ 2a822298d). Not merged,
not deployed. Handover: `WDGAP_S2_HANDOVER.md` §"WAVE 2" / S2-B1; facts `WDGAP_S2_FACTS.md`;
reader contract: `WDGAP_S2A_REPORT.md` §1 (kept unchanged — only additive keys). Local copy
`wdgap_s2b1_t` (from `upd_p6_t_tpl`, 47 behind modules `-u`, `pb_form_lines` + `pb_fund_payments`
+ `pb_retro` installed, then `pb_me_tax_cert`), port 8771. Database dropped at the end.

## 1. What was built

| # | Item | Where |
|---|---|---|
| 1 | **Indonesia BPA1** (year-end slip 1721-A1): tax-office XML `A1Bulk` (validates against the published schema), the converter's DATA sheet (C1 employer NPWP, headings B3:AB3, people from row 4), a summary workbook (everyone, who is left out and why), one PDF per person. Months from the person's payslips in the year (FullYear for Jan–Dec, PartialYear otherwise — a leaver/joiner), withholding date = last day paid, `Article21IncomeTax` 0 as the tax office's guide says. Tax status read from a mapped item, else the employee record: `pb_id_ptkp_status` (pb_me_tax, merge-time task 3 of S2-A done) added to the probe list; `K/I/n` is not in the schema list → left out with the reason | `pb_form_lines/models/render_id_bpa1.py`, `data/forms_year_end_id.xml`, `reader.py` `_pb_identity_id` |
| 2 | **Vietnam 05/QTT-TNCN**: two layouts by tax year — `VN_05QTT_TT89` (tax year 2026 on, [15]–[45]) and `VN_05QTT_TT80` (up to 2025, [16]–[41]). Workbook: the declaration in line order + sheets 05-1 (residents), 05-2 (non-residents), 05-3 (dependants, months from/to) + "To check". Dependants = `vietnam.employee.dependent` records with status eligible overlapping the year; when the running contract's registered-dependants component (codes from system parameter `pb_me_tax.vn_registered_dependants_codes`, default `VNREGISTER` — the same parameter pb_me_tax reads, so Sudima's own label works) differs → person check + warning `dependants_to_check` (level warn, never blocks). Per-person "Tax withheld in the year" PDF laid out like the sample 03/TNCN (fields [13]–[19]) | `models/render_vn_qtt.py`, `data/forms_year_end_vn.xml` |
| 3 | **India**: `IN_FORM16B` (Form 16 Part B, tax years ≤ 2025-26) and `IN_FORM130C` (Form 130 Part C, 2026-27 on): workbook (summary + one row per person) + per-person PDF; `IN_24Q` (≤ Jan–Mar 2026) and `IN_FORM138` (from Apr 2026): workbook with Annexure I (one row per person per month paid, published column numbers/letters) and, for the January–March quarter only, Annexure II read from the year-end certificate form of the same tax year. Every file and the form say "Figures for your return preparer: the upload file itself is made with the tax department's own utility." Identity hook `_pb_identity_in` (PAN `pb_in_pan_number`, regime `pb_in_tax_regime`, both by probe; legacy contract `pan_number` probed too) | `models/render_in.py`, `data/forms_year_end_in.xml`, `reader.py` |
| 4 | **Singapore IR8A**: the AIS-API 2.0 JSON payload (every key, header counts/totals), the myTax Portal "IR8A Import Template" sheet (version cell, 44 headings, ≤ 200 people per workbook), a summary, one PDF per person. Income rounded down, deductions up, C21/C22 added from the rounded parts. Appendix 8A/8B out of scope: warning `appendix_8a` / `appendix_8b` when such items carry figures. Identity hook `_pb_identity_sg` (NRIC/FIN from the national ID box → IRAS id type 1/2, work permit 4, passport 12; date of birth; sex; `pb_sg_tax_residency` by probe) | `models/render_sg.py`, `data/forms_year_end_sg.xml`, `reader.py` |
| 5 | Catalogue rows + Suggest words/roles for every new line (data, `noupdate="1"`, source note + URL, `inferred` flags); tiles under **"Year-end"** on Compliance › Filings for the company's country (`tile_group` on the form) | `data/forms_year_end_*.xml`, `models/form.py`, `pb_govt_reports` |
| 6 | **Per-person certificates + release**: a form with `employee_certificates` makes one PDF per person at prepare time (`_pb_certificate_<code>` → spec → `cert_pdf.build`, ReportLab + the DejaVu fonts `pb_hr_payroll_formula` ships; title/author/subject/creator/producer all set by us) + one zip as an ordinary filing file. Each certificate's sha256 is part of the filing's one stamp. "Release to employees" / "Take back" on the approved filing (payroll manager only, stamp checked again, logged in history + audit trail). New module **`pb_me_tax_cert`**: My Payobook › Tax certificates (`/my/tax-certificates`, under "More"), own released certificates only, download logged on the filing, "Needs you" row while a released certificate is not downloaded | `models/certificate.py`, `models/cert_pdf.py`, `pb_me_tax_cert/` |

### Engine changes (B1-owned files, additive)

* `form.py`: `tile_group` (tax_return / year_end / fund_file), `year_start_month` (the authority's
  tax year, India = 4), `employee_certificates`, `screen_note` (translated); sign rule
  `positive_part`; a sum operand written `-code` is taken away.
* `reader.py`: `period_bounds` uses the form's `year_start_month` when no scheme is given; per
  person new keys `date_from`, `date_to`, `months`; identity hooks `_pb_identity_in`,
  `_pb_identity_sg` (+ VN `passport`, `nationality`, `address`); form hook
  `_pb_checks_<code>(form, company, out)` at the end of `_pb_read` (warn-only checks).
  The S2-A return shape is unchanged.
* `filing.py`: hooks `_pb_after_render(data)` (before the stamp) and `_pb_hash_parts()`
  (more digests under the one stamp); tax-year period label "2026" / "2026–27".
* `board.py`: period keys `YYYY` (tax year) and India quarters (`2026-Q1` = Apr–Jun 2026);
  `flow_start` returns `year_options` / `quarter_labels`; `_form_card` adds `tile_group`,
  `screen_note`, `employee_certificates`; `get_filing` adds certificates/release facts;
  new RPC `set_released(filing_id, value)`.
* Flow screen (`gov_filing_flow.js/xml` + new `year_end.scss`): tax-year picker, quarter
  names from the server, the form's note, the "N personal certificates" strip with
  Release / Take back.

### Contracts other phases rely on

* `pb.gov.form.tile_group` — S2-B2's fund forms should carry `tile_group = 'fund_file'`
  (selection value already there).
* `pb.gov.filing._pb_after_render(data)` / `_pb_hash_parts()` — hooks for anything else stored
  with a filing and covered by its approval.
* `pb.gov.form.reader._pb_checks_<code lower>(form, company, out)` — a form's own warn-only checks.
* `pb.gov.filing.certificate._pb_employee_certificates(employee)` — released, approved, intact
  certificates of one person (sudo; call only after the caller's own "is this the session's
  employee" check); `_pb_portal_download(employee)` → `(filename, bytes)`, logged.
* `pb.govt.reports.get_govt_reports_data()` adds key `year_end_forms`; `forms` stays the
  monthly tax returns.

## 2. Layout sources (read 18 November 2026)

| Form | Source | Confirmed? |
|---|---|---|
| ID_BPA1 | Direktorat Jenderal Pajak, "Template XML dan Converter Excel ke XML" (Coretax), row BPA1: "BPA1 Excel to XML.xlsx" (dated 7 Nov 2024; https://pajak.go.id/sites/default/files/2024-12/BPA1%20Excel%20to%20XML.xlsx — schema `A1Bulk` copied unchanged to `pb_form_lines/tests/data/bpa1_a1bulk.xsd`), "bpa1.zip" (official sample, validates), Coretax guide "Pembuatan Bukti Pemotongan PPh Pasal 21 Tahunan A1" v20251223 (line words, filling rules). PER-11/PJ/2025 revoked PER-2/PJ/2024 | **Confirmed** (schema, element order, enumerations, sheet cells) |
| VN_05QTT_TT89 | Thông tư 89/2026/TT-BTC (signed 30 Jun 2026, in force 1 Jul 2026), 05/QTT-TNCN + 05-1/05-2/05-3, official signed text via MISA copy https://amis.misa.vn/wp-content/uploads/2026/07/89_15072026_180604.pdf pp. 312–318; certificate: Nghị định 254/2026 Điều 23–24, sample 03/TNCN of Thông tư 91/2026 Phụ lục V | **INFERRED** (official text read from a third-party copy; see list) |
| VN_05QTT_TT80 | Thông tư 80/2021/TT-BTC Phụ lục II form pack (VCCI copy https://vanban.vcci.com.vn/hm_content/uploads/van-ban/80-2021-TT-BTC__Bieu_mau.rar); 05-1/05-2 column order checked against MISA's guides | **INFERRED** |
| IN_FORM16B | Income-tax Rules 1962 Form 16 Part B as substituted by Notification 28/2023 (G.S.R. 379(E), 22 May 2023) + rows 19–21 Notification 112/2024 (G.S.R. 639(E)); read from published copies (incometaxindia.gov.in answered 403) | **INFERRED** |
| IN_FORM130C | Income-tax Rules 2026, G.S.R. 198(E), 20 Mar 2026, rule 215, Form 130 Part C (Gazette https://egazette.gov.in/WriteReadData/2026/271092.pdf pp. 2274–2280) | layout confirmed; **INFERRED** that an employer-made Part C is more than a working copy (rule 215(1): generated from the portal) |
| IN_24Q | Form 24Q as substituted by Notification 99/2021 (G.S.R. 612(E)), Annexure I cols 314–329, Annexure II 330–390 (+388A), amended 2023/2024; published copies | **INFERRED** |
| IN_FORM138 | Income-tax Rules 2026 rule 219, Form 138 (Gazette pp. 2300–2307): Annexure I A–O, Annexure II A–BQ | layout confirmed; date/challan choices INFERRED |
| SG_IR8A | IRAS AIS-API 2.0 spec v2.6 (11 Sep 2026, https://file.go.gov.sg/aisapi2-specs.pdf), "Data Items and Validation Rules" v2.5 (30 Jan 2026, https://go.gov.sg/aisapi2-dataitems), "IR8A Import Template" v1.0 (https://go.gov.sg/ir8a-import-template), Form IR8A YA 2027 + explanatory notes | payload keys/rules **confirmed**; choices INFERRED (list) |

### INFERRED list (also on the form records, shown on screen as "Not confirmed")

1. ID: FullYear for Jan–Dec, PartialYear otherwise; "Annualized" never chosen; gross-up "No";
   facility "N/A"; object code 21-100-01; withholding date = last day paid; place-of-business
   number defaults to NPWP + 000000; `K/I/n` statuses left out (not in the schema list).
2. VN: the two declarations and appendices were read from third-party copies of the signed texts.
   "Residents with a labour contract" ([16], 05-1) = every tax resident (contract length not
   checked); non-residents go to 05-2 (residents without a contract are not separated).
   Part II ([37]–[45]) is filled only from items HR maps (no recalculation); [37] counts people
   with an amount on "tax due for the year". The per-person statement has no official series or
   number. Columns "authorised" / "foreigner < 12 months" are left empty.
3. IN: rows 13–17 only from mapped items (no recalculation); 10(d) not capped; 2(g)/2(d) shown
   as one total; Annexure I date of payment/deduction = last day of each payslip period;
   challan/deposit/section-code columns left for the preparer; deductee type from the date of
   birth; old-form texts from published copies (site refused).
4. SG: `softwareCompanyName` empty; authorised person = the preparer (name, e-mail; phone =
   company phone digits); `validateOnly` true, `submissionType` "O"; dates of commencement/
   cessation from contracts; address only for a Singapore address with a 6-digit postal code;
   the import workbook repeats the official sheet/columns but is not the official file; the JSON
   carries the adviser sentence as a top-level `_note` key until the form is accepted (JSON has
   no comments — the summary says to remove it).

## 3. Tests

Numbered cases (`pb_form_lines/tests/test_s2b1_year_end.py`, `pb_me_tax_cert/tests/`, tag `wdgap_s2b1`):

| # | Case | Test | Result |
|---|---|---|---|
| 1 | Totals = sum of mapped payslip figures for the tax year (independent SQL), calendar years and India April–March, a leaver mid-year (ID Budi months 10–10 PartialYear; IN Priya Jul–Sep; SG Tan contract dates) | T1a–T1e | pass |
| 2 | BPA1 XML validates against the published XSD; XML order ≠ sheet order; DATA sheet cells; left-out people listed | T2 | pass |
| 3 | SG payload: every key in published order, record ids, id types, lengths, ≤ 9 digits, C21/C22 sums, header count/total; rounding down/up; import workbook headings; Appendix 8A warning | T3 | pass |
| 4 | VN dependants: eligible + in-year only, months from/to, mismatch → "to check" (warn), 05-1/05-2/05-3 sheets, layouts refuse each other's years | T4 | pass |
| 5 | Per-person PDF: right person, right year, adviser note until accepted, none after; producer/creator "Payobook"; no "Odoo" in text, metadata, bytes or name; zip has every certificate; VN/IN/SG certificates print | T5 | pass |
| 6 | Release: before approval refused; officer refused; manager releases; own only; download logged (no tax number); take back hides; a changed certificate breaks the stamp → hidden; superseded filing → gone | T6 + web `test_t6_t7_own_certificate_only_screen_and_address` | pass |
| 7 | Access: officer/manager/HR without payroll/portal on the server (RPC + records + company rule); employee, line manager, another employee, HR without payroll as real logins on the page and the direct address (404) | T7 + web T6/T7 | pass |
| 8 | Two currencies → block, nothing added; split by currency; identity missing (SG, IN) → warning, no crash | T8 | pass |
| 9 | Silent install: no certificate, nothing released, nothing mapped for the main company, no job, no mail template | T9 | pass |
| 10 | PO gate vi/id (S2-A gate scans every new string of `pb_form_lines`; `pb_me_tax_cert` own gate) + no "Odoo" | `test_s2a_po_gate`, `TestTaxCertPoGate` | pass |
| 11 | Browser walk | §3.2 | done |
| 12 | S2-A's suites unchanged | §3.1 | see table |
| — | Year-end tiles on the Filings board, `forms` stays S2-A's | `test_year_end_tiles_on_the_filings_board` | pass |
| — | Home tile under "More", "Needs you" until downloaded | `test_home_tile_and_needs_you` | pass |

### 3.1 Suites vs baseline

Baseline: an archive of `origin/wdgap-s2a` on the same database, tags
`/pb_form_lines,/pb_govt_reports,/pb_compliance_hub,/pb_hr_govt,/pb_hr_payroll_vietnam,`
`/pb_pay_delivery:TestIdb1VnGolden,/pb_hub:TestPaletteRowsFollowTheirTabs,/pb_me_portal` —
**209 tests, 7 failed, 2 errors**:
`pb_hub` `test_deep_links_onto_a_tab_carry_its_gate` (S2-A merge-time task 1) and
`test_every_tab_has_a_row_or_says_why_not` (Step 6 tabs); `pb_compliance_hub`
`TestFilingFlow.test_generating_a_vn_filing_produces_a_real_file` (S2-A baseline);
`pb_me_portal` `TestMeHomeCards.test_05_grid` (error), `test_06_font`,
`TestMeHomeSource.test_01_registry_covers_every_tile`, `test_12_vi_po_parses_and_covers_the_new_words`,
`TestPbMePortal.test_01_profile_change_flow_and_audit` (error),
`TestPortalOnlyDoors.test_t1_7_portal_only_person_is_bounced_to_my` — all pre-existing on this
template copy (no S2-B1 module loaded).

Branch, same tags + `/pb_me_tax_cert` — **228 tests, 7 failed, 2 errors: exactly the baseline
set**; the 19 new tests (14 `pb_form_lines` S2-B1 + 5 `pb_me_tax_cert`) and all S2-A tests
pass, including S2-A's PO gate over every new `pb_form_lines` string and S2-A's tile test
(`forms` = tax returns only). VN bank-file golden (`TestIdb1VnGolden`) and the VN
social-insurance golden pass — bytes unchanged.

### 3.2 Browser walk (local `s2b1.localhost:8771`, isolated contexts)

Compliance › Filings (inside the hub) for a DEMO Indonesian company: "Tax returns" and the new
"Year-end" group (BPA1 tile: "Check with your adviser before first filing", "A certificate for
each person"). Prepare → Tax year 2026 → Check (2 people, 20 finished payslips, lines 1–22) →
Prepare and send → Approved (fast lane) → 4 files + "2 personal certificates" → Release to
employees → "Released to employees by … on …" + Take back; phone width (500 px window): strip
stacks, no sideways scroll. India company: the Year-end group lists Form 16 B / Form 130 C /
24Q / Form 138; Form 138 picker shows "2026–27" and "April – June … January – March"; Oct–Dec
quarter prepared and approved. Employee (portal login, phone width): My Payobook tile "Tax
certificates — Your year-end tax certificates"; page lists "Year-end income tax slip (BPA1) ·
Tax year 2026 · New"; the PDF downloads (200, application/pdf, file
`BPA1_2026_DEMO_Walk_Ani.pdf`); another person's certificate address → 404. Console: no errors
from these screens (one 500 on the template's missing website logo — template filestore,
pre-existing, ledger S6A-7). Rendered certificates were also checked as images (all four
countries). Fix from the walk: the tax-year label "Jan 2026 – Dec 2026" → "2026" / "2026–27";
the portal page title.

## 4. Version raises and deploy notes

| Module | Version | Action |
|---|---|---|
| pb_form_lines | 19.0.1.0.0 → **raise to 19.0.1.1.0 at the merge** (left to the deployer, both B1 and B2 add to it) | `-u` |
| pb_govt_reports | 19.0.1.3.0 → raise (deployer; e.g. 19.0.1.3.1, or one raise for B1+B2) | `-u` (Python + OWL template) |
| pb_me_tax_cert | 19.0.1.0.0 (new) | `-i` (depends pb_form_lines, pb_me_portal, portal) |

* JS/SCSS/XML changed (pb_form_lines backend assets, pb_govt_reports, pb_me_tax_cert frontend
  scss) → asset purge + restart.
* New data: 8 forms, 207 lines (`noupdate="1"`); new model `pb.gov.filing.certificate` (+ ACL:
  payroll officer read, system all; company rule); new fields on `pb.gov.form` and `pb.gov.filing`
  (`pb_released*`).
* Silent install to check: `pb_gov_filing_certificate` empty; no `pb_gov_filing` with
  `pb_released`; `pb_gov_form_map` unchanged; no new `ir_cron`, no mail template; 11 forms / 260
  lines in the catalogue.
* No payslip figure changes (nothing writes payslips, contracts or employees). Rize rehearsal
  (read-only): map a few items on a copy for rize's ID scheme (7121) and IN scheme (7119, April
  year) and compare the BPA1 / Form 130 totals by hand with the payslips; rize's `filing` route
  decides whether filings wait for an approver. The PDF engine is ReportLab (pure Python) — no
  wkhtmltopdf needed, works the same on the server.
* India PAN / regime and Indonesian PTKP are read from `pb_me_tax` fields by probe: install order
  does not matter; without `pb_me_tax` the identity warnings say "no PAN" etc.

### Merge-time tasks (other lanes / the sibling builder)

1. **S2-B2 fund forms**: set `tile_group = 'fund_file'` on their `pb.gov.form` records (the
   value exists) and show them from a key of their own beside `year_end_forms` in
   `pb_govt_reports` (`get_govt_reports_data`: `forms` must stay the tax returns — ledger S2B1-5).
   If B2 grouped its tiles another way, keep one mechanism: `tile_group`.
2. `pb_govt_reports/models/pb_govt_reports.py` and `static/src/xml/govt_reports.xml`: B1 inserted
   `all_forms` / `year_end_forms` lines right after `forms = _forms_for(...)` and a "Year-end"
   panel right after the "Tax returns" panel; B2's additions belong beside them (text-level merge).
3. `pb_form_lines/__manifest__.py`, `models/__init__.py`, `security/ir.model.access.csv`,
   `tests/__init__.py`, both `.po` files: B1 appended at the end — keep both sides' lines.
4. `pb_me_portal` home test pins the "Me" tiles: to move "Tax certificates" under "Me" (owner
   ruling ME1 spirit), change `pb_me_tax_cert/models/pb_me_home.py` group to `'me'` with
   `seq = GROUPS.index('me') * 100 + 11` AND add `'/my/tax-certificates'` to the `added` list in
   `pb_me_portal/tests/test_me_home.py` test_02 (after `/my/certificates`).
5. `pb_hub` ⌘K palette row for "Prepare a filing" / year-end (pb_hub lane) — optional.

## 5. Left for later

* Appendix 8A / 8B (Singapore benefits in kind, share gains); IRAS API submission itself.
* India FVU/TRACES upload file; challan details; Form 12BA/Form 123 perquisites.
* Vietnam official XML for the tax office's software; a numbered official withholding
  certificate (needs the company's registered 03/TNCN series); "authorised the employer to
  settle" flag per person (Part II and the certificate rule of Nghị định 254/2026 Điều 24 khoản 2).
* Indonesia BPA2 (civil servants) / A1 for foreigners leaving mid-year ("Annualized").
* Monthly BPMP (S2-A) still says December goes on the year-end slip — not enforced.

## 6. Gotchas → ledger

S2B1-1 … S2B1-8 added to `WDGAP_LEDGER.md`; phase row S2-B1 added.

## 7. Follow-up YE1–YE3 (owner rulings 2026-11-18 ~17:10)

| Ruling | What was built | Where |
|---|---|---|
| **YE1** Vietnam "Asked us to settle year-end tax" per person per tax year | New model `pb.gov.year.settlement` (employee, company, country, tax year, asked, marked by/on, history) in `pb_form_lines` — no `pb_me_tax` needed. Ticked on "Prepare a filing" › Check for the 05/QTT-TNCN forms (panel "Asked us to settle year-end tax", one tick per person; payroll officer/manager through the Filings door `_pb_require_officer`; HR without payroll and employees refused; no portal route reads it). Effect: the person stays in every declaration figure; 05-1 column [10] = X; Part II [37] counts them and [38] (TT80 [35]/[36]) holds their tax withheld; balance lines [44]/[45] (TT80 [40]/[41]) are worked out only when a pay item gives the year's tax due on [40] ([38]), else 0 with a warning; summary ("To check" sheet + the check screen) says "asked us to settle"; NO certificate is made for them. A certificate already released is hidden as soon as the person is ticked, and stays hidden after an untick (any change after the filing was prepared) until HR prepares and releases the year again — never silently. | `models/settle.py`, `models/render_vn_qtt.py` (`_pb_vn_settled`, `_pb_cert_withheld`), `models/certificate.py` (hook `_pb_cert_withheld`), `models/board.py` (`flow_check['settle']`, RPC `set_settle`), flow JS/XML/SCSS, security (ACL officer rwc / system, company rule) |
| **YE2** Vietnam certificate = information copy | PDF banner "Information copy · Bản sao thông tin · Salinan informasi" (all three languages on every copy); no series/number field; "Information copy" beside the download on My Payobook | `render_vn_qtt.py`, `cert_pdf.py` (`banner`), `certificate.list_note`, `pb_me_tax_cert` page |
| **YE3** India: employees keep Payobook's copy | PDF banner and the line beside the download: "Information copy — your official certificate comes from the tax department" | `render_in.py`, `pb_me_tax_cert` page |

Data: the Part II count line note now says it counts the people HR marked (and is no longer
INFERRED); the stale translation of the old note was removed. Not done (left for later, owner):
IRAS approved-software application (direct sending of Singapore files) — needs an outside account.

Tests (numbered, `TestS2B1FollowUpYE` + web):

| # | Case | Result |
|---|---|---|
| YE1-1 | Officer ticks per tax year, who/when kept; 2025 is its own answer; HR without payroll and an employee login refused (screen RPC + records); a form without the choice refuses it | pass |
| YE1-2 | Ticked person: declaration figures unchanged ([15]–[34]); [37]=1, [38]= their tax withheld, [44]/[45]=0 + warning without the tax due; with the tax due mapped, [45] = withheld − due; no certificate made; 05-1 [10]=X; "To check" lists them | pass |
| YE1-3 | After release: tick hides at once, others unchanged; untick does NOT bring it back; prepare + release again shows the new one | pass |
| YE2 | VN PDF says the three-language "Information copy", no "Ký hiệu"/"Số chứng từ"; note beside download; no "Odoo" in text/metadata | pass |
| YE3 | IN PDF says "Information copy — your official certificate comes from the tax department"; same line beside the download (web, real employee login) | pass |

Suites (fresh copy of `upd_p6_t_tpl`, same tags as §3.1 + `/pb_me_tax_cert`): **234 tests,
7 failed, 2 errors — exactly the §3.1 baseline set**; the 25 S2-B1 tests (19 + 6 follow-up)
pass, S2-A's PO gate included. vi/id: 25 new entries per language appended text-level (plus
the new model's field occurrences on existing entries); the old Part II note's entry removed.

Browser walk (local, isolated contexts): Vietnam company › Year-end › 05/QTT-TNCN (2026) › Check:
the "Asked us to settle year-end tax" panel lists the people; ticking one shows "Marked by … on
…", the count and [37]=1 update at once; Prepare and send → Approved → "1 personal certificate"
(the ticked person has none) → Release. India employee login (phone width, no sideways scroll):
Tax certificates row "Salary and tax deducted — Form 130 Part C (figures) · Tax year 2026–27"
with "Information copy — your official certificate comes from the tax department" beside the
PDF button. Console: clean apart from the template's missing website logo (pre-existing, S6A-7).

### FG1 (Filings open to payroll officers/managers AND "Government reports") — merge note

* Every S2-B1 door asks S2-A's shared helpers, never a restated group list: board RPCs
  (`flow_check`, `set_settle`, `get_filing`, `set_released`) → `pb.gov.form.board._door()` →
  `pb.gov.form.rights._pb_require_officer()`; Year-end tiles → `pb_govt_reports._forms_for()` →
  `Rights._pb_is_officer()`; the settle model's own check → `_pb_require_officer()`. When S2-A
  widens `OFFICER_GROUPS` / those helpers, Year-end follows with no change here.
* "Release to employees" stays payroll manager only: `certificate.py` `_pb_release` uses S2-A's
  `MANAGER_GROUPS` constant (not widened by FG1).
* Merge-time task: the ACL rows name the officer group directly, like S2-A's own rows —
  `pb_form_lines/security/ir.model.access.csv` rows
  `access_pb_gov_filing_certificate_officer` (read) and `access_pb_gov_year_settlement_officer`
  (read/write/create). If S2-A adds ACL rows for `pb_hr_govt.group_pb_hr_govt_user` on its
  filing models, add the same two rows for that group (certificate: 1,0,0,0; settlement:
  1,1,1,0). The screens read both models under sudo after the door, so the screens work either
  way; the rows matter only for direct record reads.

## 8. Owner questions

Answered 2026-11-18: 1 → YE1, 2 → YE2, 3 → YE3 (built, §7); 4 → deferred (outside account).
Still open: 5.

1. Vietnam: a company must NOT give a withholding certificate to people who asked it to settle
   their year-end tax for them. Payobook does not yet record who asked. Should HR tick that on the
   employee record (it would also fill the "settled for them" part of the year-end declaration)?
2. Vietnam's official certificate needs the company's own registered series and number. Do you
   want Payobook to number them (HR types the series once per company), or keep ours as an
   information copy and the official one stays in the company's e-invoice software?
3. India: from April 2026 the official certificate (Form 130) is downloaded from the tax
   department's portal. Should employees still see our copy of the salary figures on My
   Payobook, or only the Indonesian, Vietnamese and Singaporean certificates?
4. Singapore: IRAS only takes the yearly income records through approved payroll software or by
   upload on its website. Should Payobook apply to IRAS to become approved software (then we can
   send them directly), or is the upload workbook enough for now?
5. The Singapore and Indonesian files need the employer's tax number typed once on Form lines. Is
   that the right person (payroll officer) to type it, or should it come from the company's
   settings?
