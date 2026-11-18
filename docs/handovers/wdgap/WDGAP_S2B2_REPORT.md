# WDGAP S2-B2 report — fund files outside Vietnam + Vietnam social insurance onto Form lines

Builder, 2026-11-18. Branch `wdgap-s2b2` (from `origin/wdgap-s2a` @ 2a822298d). Not merged, not
deployed. Handover: `WDGAP_S2_HANDOVER.md` §"WAVE 2" / S2-B2 (main checkout). Local copy
`wdgap_s2b2_t` (from `upd_p6_t_tpl`, 47 behind modules `-u`, `pb_form_lines` +
`pb_fund_payments` + `pb_retro` installed), port 8762 — dropped at the end.

## 1. What was built

| # | Item | Where |
|---|---|---|
| 1 | Indonesia: **BPJS Ketenagakerjaan** monthly wage report for SIPP "Upload Upah" (NIK, KPJ, name, birth date, wage, month) + summary; **BPJS Kesehatan** member/contribution sheet for e-Dabu (NIK, card no., name, birth date, wage, 1 % / 4 % shares, total) + summary. Forms `ID_BPJS_TK` (11 lines: wage, JHT ee/er, JKK, JKM, JP ee/er, employee/employer/total, people) and `ID_BPJS_KES` (5 lines) | `pb_form_lines/models/fund_id.py`, `data/forms_fund_id.xml` |
| 2 | India: **EPF ECR 2.0** text file (11 fields, `#~#`, no header, whole rupees half up) + summary; **ESI** monthly contribution sheet (the MC template's six columns; days rounded up to whole days; reason code 0 when days > 0, else left for the portal with a check) + summary. Forms `IN_EPF_ECR` (13 lines), `IN_ESI` (6 lines) | `models/fund_in.py`, `data/forms_fund_in.xml` |
| 3 | Singapore: **CPF EZPay** FTP file to CPF Board's published spec (150-byte records: header, summaries 01/02/03/04/05/10/11, details sorted by CPF account then payment code, trailer count + amount; file name `<CSN><MMMYYYY><advice>.DTL`), SDL as the summary record 11, self-help funds as detail records with donor counts, employment status E/N/L/O from contracts + summary. Form `SG_CPF_EZPAY` (15 lines) | `models/fund_sg.py`, `data/forms_fund_sg.xml` |
| 4 | Every fund file is a `pb.gov.form` on the S2-A engine: monthly, `filing_section='fund'` (tiles under **"Fund files"**), same approval route `filing`, approved-bytes-only download + trail, adviser note **"Check with the fund before the first upload"** chosen by the new form field `adviser_wording` (default unchanged). Member numbers read by probe; a person without one is **left out with the reason** on the summary workbook; the summary prints "everyone read from payslips" beside "in the file", and says the file's totals leave them out | `models/fund_form.py`, `models/fund_common.py` |
| 5 | Fund payments link (read only, by probe): the check step adds "Fund payments for <month>: X — the same as this file" / "… They differ by Z", for the funds whose pay items are on the form's compared lines; a month Fund payments has not worked out yet is read the way it would work it out, and the sentence says so. Also a "left out" line with the file's total without them | `models/fund_compare.py` |
| 6 | Vietnam social-insurance reports: form `VN_SI_ITEMS` (lines SICK, MAT, ALLOW, EXTRA; `filing_section='reports'`: no tile, no file, no adviser note on Form lines). `pb_hr_govt` reads it per line by probe: nothing mapped for the company → the fixed code exactly as before; mapped → the reader's figure and one sentence under the rows ("Lấy từ khoản lương đã chọn ở Dòng biểu mẫu: …"). Who can open the reports: unchanged | `pb_form_lines/models/vn_si_items.py`, `data/forms_vn_si.xml`; `pb_hr_govt/models/report_base.py` (`_pb_si_items`, `_pb_si_amount`, `_pb_si_note`), `report/bhxh630_report.py`, `giam_ld_report.py`, `tang_ld_report.py` |
| 7 | Filings board: tiles grouped by section — "Tax returns", "Year-end" (slot for S2-B1), "Fund files"; `forms` keeps its S2-A meaning (tax returns only); fund tiles say the fund sentence. Two board fixes found on the walk: a company with no country of its own opened on Vietnam whatever it paid (now its schemes' country); a payroll officer without formula rights saw no country chips (scheme countries now read under sudo — country codes of the company's own schemes only) | `pb_govt_reports/models/pb_govt_reports.py`, `static/src/xml/govt_reports.xml` |
| 8 | Screens: fund wording, the company number's label per form (e.g. "CPF submission number (CSN), for example 201912345APTE01"), no "Prepare a filing"/settings/adviser note for the reports-only form — all by OWL `t-inherit` in a NEW file; no S2-A screen file edited | `pb_form_lines/static/src/xml/fund_files.xml` |

Files edited outside new files: `pb_form_lines/__manifest__.py` (data + asset lines appended),
`models/__init__.py`, `tests/__init__.py` (lines appended), `i18n/vi_VN.po`, `i18n/id_ID.po`
(entries appended, 16 existing entries got extra `#:` occurrences); `pb_hr_govt` (lane);
`pb_govt_reports` model + template + tests `__init__` + `vi_VN.po`. `reader.py`, `filing.py`,
`form.py`, `board.py`, the board JS/templates: **not edited** (extended by `_inherit` /
`t-inherit`).

### Contracts other phases rely on

* `pb.gov.form.filing_section` Selection `tax` (default) / `fund` / `reports`; the Filings board
  groups by it (`_form_groups`, order `tax, year_end, fund`, icon per key). **S2-B1: put year-end
  forms under `filing_section='year_end'`** — see merge task 3.
* `pb.gov.form.adviser_wording` `adviser` (default) / `fund`; `pb.gov.form._pb_adviser_sentence()`;
  `pb.gov.filing._pb_adviser_text()` now follows the record's form (or, inside `prepare`, the
  context key `pb_adviser_form_id`).
* `pb.gov.form.employer_label` (translated) — the company number's name on Form lines (value still
  in `pb.gov.form.company.employer_tax_id`); `compare_line_codes` — lines compared with Fund
  payments.
* `pb.gov.form.reader._pb_identity` dispatches `filing_section == 'fund'` forms to
  `_pb_fund_identity_<code>`; every other form still goes to `_pb_identity_<cc>` (S2-B1's
  `_pb_identity_in` / `_pb_identity_sg` are untouched by this). `_pb_probe(employee, names,
  contract_names)` reads a member number by field name (employee, then running contract).
* Board card extras: `section`, `section_label`, `adviser_wording`, `adviser_text`,
  `employer_label`, `can_prepare`, `needs_settings`.
* `pb.govt.report.base._pb_si_items(company, date_from, date_to)` → None or `{'mapped', 'values'}`.

## 2. Layout sources (and what is INFERRED)

| Form | Source | Confirmed? |
|---|---|---|
| SG_CPF_EZPAY | CPF Board, "CPF EZPay (FTP) File Specifications (effective from 16 January 2025)", FTPSPEC/FILESPEC, last updated Jan 2025, https://www.cpf.gov.sg/content/dam/web/employer/making-cpf-contributions/documents/CPFEZPayFTPSpecifications.pdf (read in full, incl. its sample file) | **Record layout confirmed.** INFERRED choices (on the record): CR LF line ends; "Month Paid" in the file name = contribution month; advice code 01; status E/N/L/O from contracts; the CPF amount = employee + employer CPF as the payslips carry them (no re-rounding); adviser note on the summary, not in the file |
| IN_EPF_ECR | EPFO "Introduction ECR 2.0" (https://www.epfindia.gov.in/site_docs/PDFs/EPFOUnifiedPortal/Introduction_ECR2.0.pdf) — **answered 403 from here (CloudFront block)**; layout from published guides that agree (laabam.one "How to File PF Return (ECR 2.0)", fundraksha.com "PF ECR Format Explained", keka.com "PF ECR Version 2.0") | **INFERRED** (field list/order, whole-rupee rule, half-up rounding) |
| IN_ESI | ESIC portal "Monthly Contribution" MC Excel template (login only); guides: treelife.in "ESI Returns and Challan Filing", docs.pockethrms.com "ESI Return File" | **INFERRED** (column heads, sheet name `Sheet1`, days rounded up, reason code / last working day left to the portal) |
| ID_BPJS_TK | BPJS Ketenagakerjaan SIPP "Upload Upah" template (login only); guide: gadjian.com "5 Fitur SIPP BPJS Ketenagakerjaan" (24 Aug 2022) | **INFERRED** (columns NIK, NO KPJ, NAMA LENGKAP, TGL LAHIR dd-mm-yyyy, UPAH, BLN/THN; sheet name) |
| ID_BPJS_KES | BPJS Kesehatan e-Dabu (login only); guide: detik.com "Edabu BPJS Kesehatan" (2021) | **INFERRED** (every column) |
| VN_SI_ITEMS | Not a layout: names the pay items the existing reports read; report templates unchanged (their origin is not recorded) | INFERRED note says so |

INFERRED list, also on each record and shown as "Not fully confirmed from an official source":
1. EPF ECR: the whole layout (EPFO page blocked). 2. ESI: the whole sheet. 3. BPJS TK: the SIPP
upload columns and date format; the contributions are summary-only (SIPP works them out from the
wage). 4. BPJS Kesehatan: the whole sheet. 5. CPF: the five choices in the table. 6. For text
files (ECR, CPF) the adviser note cannot go in the file without breaking the upload: it is the
first row of the summary workbook in the same filing and on every screen; upload workbooks get a
second sheet "Check first" (portals read the first sheet).

## 3. Tests

Numbered cases (`pb_form_lines` `test_s2b2_fund_files.py` + `test_s2b2_access_http.py`,
`pb_hr_govt` `test_wdgap_s2b2_items.py`, `pb_govt_reports` `test_wdgap_s2b2.py`; tag `wdgap_s2b2`):

| # | Case | Result |
|---|---|---|
| 1 | Each file's totals = the mapped payslip figures; employee and employer shares apart (BPJS TK/KES, ESI, CPF; ECR in 2) | pass |
| 2 | ECR: 11 fields, `#~#`, no header, trailing newline, whole numbers, 1,800.50 → 1801, 1,249.50 → 1250, 550.49 → 550 | pass |
| 3 | CPF: every record 150 bytes + CR LF, no forbidden characters, header/summary/detail/trailer positions, summary codes order, donor counts, details sorted, status N for a joiner, trailer count = records, trailer amount = sum of summaries; no CSN → plain refusal | pass |
| 4 | Missing UAN / CPF account number → left out with the reason (summary + People sheet "No"), totals "everyone read" vs "in the file", the check step's left-out line names the count and the total without them; a foreign employee with SDL only is not "left out"; nobody with a number → refusal | pass |
| 5 | Fund payments comparison: not yet worked out (same, says so), worked out (same), a fund that counts another item (differ, amount); nothing written to Fund payments | pass |
| 6 | VN reports: nothing mapped → every workbook part except `docProps/` byte-identical with `origin/wdgap-s2a` (golden recorded on that tree: `pb_hr_govt/tests/data/s2b2_vn_si_parts.json`); mapped → sick days and allowances from the company's own items, MAT/EXTRA still the codes, one note naming the items | pass |
| 7 | Route with a waiting step, decider without payroll rights, approved bytes only, changed bytes refused, trail names the file and no member number (history + audit) | pass |
| 8 | Access: officer/manager yes; HR without payroll + portal refused on every board call, the download method and the record; Filings board gives HR no fund group; download address as real logins: officer 200 + bytes + `.DTL` name, HR/portal 303/403/404 | pass |
| 9 | Silent install: 5 fund forms + the VN items form, nothing mapped/filed/no company setting, catalogue `noupdate`, sources + INFERRED notes present, S2-A forms keep `tax` / `adviser` | pass |
| 10 | No "Odoo" in any file made, name or warning; PO gate (S2-A `test_s2a_po_gate`, which scans every .py/.js of the module, now incl. these files): parse, module line, markers, header, every code string translated vi + id | pass |
| 11 | Browser walk (§3.2) + a static test that every template extension finds its target | done / pass |
| 12 | S2-A suites unchanged | see 3.1 |

### 3.1 Suites vs baseline

Baseline (frozen `origin/wdgap-s2a` copy of the 8 touched/related modules, same DB):
`/pb_form_lines,/pb_govt_reports,/pb_compliance_hub,/pb_hr_govt,/pb_fund_payments,/pb_hr_payroll_vietnam,/pb_pay_delivery:TestIdb1VnGolden,/pb_hub:TestPaletteRowsFollowTheirTabs`
→ 142 tests, 4 failed 4 errors; the 4 `pb_compliance_hub` errors and 2 of the `pb_hub` failures
come from the frozen copy missing sibling modules those tests read by path (artefact). Compared
with S2-A's recorded set instead.

Branch, same tags (157 tests incl. the new ones), failures:
* `TestFilingFlow.test_generating_a_vn_filing_produces_a_real_file` — S2-A baseline;
* `pb_hub` `test_every_tab_has_a_row_or_says_why_not` — S2-A baseline;
* `pb_hub` `test_deep_links_onto_a_tab_carry_its_gate` — S2-A merge-time task 1 (unchanged);
* `pb_govt_reports` `test_s2a_3_tiles_for_the_form_catalogue` — failed on the first run (fund
  forms leaked into `forms`); fixed (`forms` = tax returns only), re-run `/pb_form_lines,/pb_govt_reports`:
  **45 tests, 0 failed**; after the walk fixes + T11: re-run, see 3.3.
* VN bank-file golden passes; `pb_fund_payments`, `pb_hr_payroll_vietnam`, `pb_hr_govt`
  (incl. S2-A golden 11a–d) pass.

### 3.2 Browser walk (local, `localhost:8762`, isolated browser context, DEMO walk user = payroll manager)

Compliance › Filings (Singapore DEMO company): "Fund files" group with the CPF tile, amber
"Pay items to choose on Form lines" → Form lines: fund sentence, "CPF submission number (CSN),
for example …" label, source note → Suggest → 7 proposals, all right (OW, AW, CPF ee/er, SDL,
MBMF, CDAC) → Save → Prepare a filing → Check: 4 people, "1 person is left out of the file (No
CPF account number …). The file's total leaves out their S$ 745.00: S$ 3,010.50." → Prepare
and send → Approved (fast lane) → "These files say 'Check with the fund before the first
upload'" → download URL: 200, `201912345KPTE01OCT202601.DTL`, 13 records × 150 + CR LF, trailer
`0000013` / `301050`. India (RPC): Suggest proposes all 8 ECR lines right; check step: "2 people
have no UAN …" + left-out line. vi_VN / id_ID: form names, section label, fund sentence, CSN
label, line labels all translated. Phone width (500 px, the browser minimum): no sideways scroll.
Console: clean after the fix below.

Found and fixed on the walk: (a) an xpath in the new template targeted `div.pbgf-detail` while
S2-A's template has `section.pbgf-detail` → Form lines did not open ("Something went wrong") — no
Python test could see it; fixed + static test T11 added; (b)/(c) the two board fixes in §1 item 7.
Seen, not fixed (S2-A board JS, the other builder's file): after "Suggest → Save", the company
number box still shows what was typed but the screen's copy was reset from the server, so the
next "Save" stores an empty number — reported in §6.

### 3.3 Final re-run

After the walk fixes and T11: `/pb_form_lines,/pb_govt_reports` → 46 tests, 1 failed: T9, because
the walk seed had been committed into the local copy (ledger S8D-6) — its "nothing filed"
checks made company-scoped like S2-A's T12; re-run `/pb_form_lines:TestS2B2FundFiles` → **12
tests, 0 failed**. `pb_hr_govt` (golden + mapped), `pb_fund_payments`,
`pb_hr_payroll_vietnam`, the VN bank golden: unchanged since the full run (pass).

## 4. Version raises

| Module | Version | Note |
|---|---|---|
| pb_form_lines | **leave at 19.0.1.0.0 — deployer raises to 19.0.1.1.0** (both wave-2 builders, handover rule) | `-u` |
| pb_govt_reports | **leave at 19.0.1.3.0 — deployer raises to 19.0.1.4.0** (both builders touch it) | `-u` |
| pb_hr_govt | 19.0.1.1.1 → **19.0.1.2.0** (this lane only) | `-u` |

## 5. Merge-time tasks (exact)

1. `pb_form_lines/__manifest__.py`, `models/__init__.py`, `tests/__init__.py`: keep BOTH builders'
   appended lines (mine: data `forms_fund_id/in/sg.xml`, `forms_vn_si.xml`; asset
   `static/src/xml/fund_files.xml`; models `fund_form, fund_common, fund_id, fund_in, fund_sg,
   fund_compare, vn_si_items`; tests `test_s2b2_fund_files, test_s2b2_access_http`). Raise to
   19.0.1.1.0.
2. `pb_form_lines/i18n/vi_VN.po` and `id_ID.po`: both builders append at the end → merge
   text-level, then remove duplicate msgids (likely shared: "Employee share", "Employer share",
   "In the file", "Gross wages", "NIK", "UAN" …) by joining their `#:` lines; the S2-A PO gate
   fails on a duplicate msgid.
3. Year-end tiles under "Year-end": the board already orders `tax, year_end, fund` and has an
   icon for `year_end`. Add the value in `pb_form_lines/models/fund_form.py`:
   `SECTIONS = [('tax', 'Tax returns'), ('year_end', 'Year-end'), ('fund', 'Fund files'), ('reports', 'Used by reports')]`
   (+ vi "Quyết toán cuối năm" / id "Akhir tahun" with occurrence
   `model:ir.model.fields.selection,name:pb_form_lines.selection__pb_gov_form__filing_section__year_end`)
   and set `<field name="filing_section">year_end</field>` on S2-B1's year-end forms. If S2-B1
   built its own grouping in `pb_govt_reports`, keep one: `_form_groups` + the
   `state.data.form_groups` loop in `govt_reports.xml`.
4. If S2-B1 edits `gov_filing_flow.xml` / `form_lines_board.xml`: re-run
   `TestS2B2FundFiles.test_t11_screen_extensions_find_their_targets` — it fails if an xpath of
   `fund_files.xml` lost its target (the screen would not open).
5. S2-A task 1 (`pb_hub` `CMP_FILINGS`) still open.

## 6. Deploy notes

* `-u pb_form_lines,pb_govt_reports,pb_hr_govt` (after the merge; `pb_form_lines` is new in Step 2,
  so `-i` at the step's go-live). Asset purge + restart (new template file, `govt_reports.xml`).
* Silent install proof: `pb_gov_form` 9 rows (3 S2-A + 5 fund + `VN_SI_ITEMS`), lines 53 + 54;
  `pb_gov_form_map`, `pb_gov_filing`, `pb_gov_form_company` unchanged (empty on a fresh
  install); no `ir_cron`, no `mail_template`; the 3 S2-A forms show `filing_section='tax'`,
  `adviser_wording='adviser'`.
* Nothing writes payslips, contracts, employees or Fund payments. The VN social-insurance reports
  are byte-identical until somebody maps `VN_SI_ITEMS` (rize/sudima: nobody has).
* Rize rehearsal (read only, on a copy): map BPJS TK/KES for the ID scheme and ECR for the IN
  scheme in the copy, run the check step for a finished month, compare totals by hand with the
  payslips and with Fund payments; expect **everyone left out of ECR** (no UAN field until S2-D's
  `pb_me_tax` is installed and filled) and of ESI (no ESI-number field exists anywhere). Check
  rize's `filing` route (whatever rize published applies).
* Member numbers on the live databases (read by probe): ID `pb_bpjs_employment_number`,
  `pb_bpjs_health_number` (pb_employee_vault) + NIK from the national ID; IN UAN
  `pb_in_uan_number` (S2-D) / legacy contract `uan_number`; IN ESI: **no field anywhere**
  (`pb_in_esi_number`, `esi_ip_number`, `esi_number` probed); SG CPF account = NRIC/FIN from
  `pb_sg_nric` / `singapore_nric_fin` / legacy contract field, else the national ID when it has
  the S/T shape.

## 7. Left for later

* An ESI insurance-number field (and a Singapore NRIC field) on the employee record — owner
  question 2; until then those files leave people out, by design.
* The S2-A board quirk in §3.2 (company number lost after Suggest → Save) — board JS owner.
* CPF: Community Chest (code 10) is written as zero; CPF penalty interest (07) not written; one
  payment advice per file (advice 01).
* ESI: reason code for zero days and last working day are typed on the portal.
* BPJS: rapel (back pay) column not written (not confirmed in the template).
* Fund payments comparison matches funds by shared pay items; a fund whose items are not on the
  form is not compared.

## 8. Gotchas → ledger (rows to add)

| # | Gotcha |
|---|---|
| S2B2-1 | An OWL `t-inherit` xpath that misses its target breaks the WHOLE screen at open ("Something went wrong"), and no Python test sees it. Check the target's tag (S2-A's Form lines detail is a `<section>`, not a `<div>`); keep a static test that evaluates every xpath (T11). |
| S2B2-2 | Changing a static template file is not enough for a running local server: the bundle hash stays the same until `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` + restart. |
| S2B2-3 | EPFO's own document site (epfindia.gov.in → epfo.gov.in) answers 403 to non-browser fetches (CloudFront); SIPP/e-Dabu/ESIC templates are behind login — only CPF Board publishes its file spec openly. |
| S2B2-4 | `pb.govt.reports.get_govt_reports_data` read scheme countries without sudo: a payroll officer without formula rights saw no country and a company with no country opened on Vietnam. Fixed in S2-B2. |
| S2B2-5 | The `upd_p6_t_tpl` admin user (id 2) is archived: a local walk needs its own DEMO user. |
| S2B2-6 | Text-level PO merge: replace the matched block by its POSITION, not with `str.replace(..., 1)` — identical `#.`/`#:` blocks repeat in a PO and the first one is not the one you matched. |

## 9. Owner questions (plain)

1. Only Singapore's CPF Board publishes its upload file layout. For the Indonesian BPJS sheets
   and the Indian provident-fund and ESI files we followed published guides. Can Rize's finance
   team send one file they have already uploaded successfully for each (any month, names can be
   blanked) so we can check the columns?
2. Payobook has nowhere to keep an employee's Indian ESI insurance number (and no Singapore NRIC
   box — we use the ID number when it looks like an NRIC). Until there is one, those people are
   left out of the ESI file with the reason shown. Should we add an "ESI number" box to the
   employee record (and to My Payobook tax details)?
3. The CPF file needs the company's CPF submission number (for example 201912345APTE01). Does
   Rize Singapore pay through one submission number, or more than one?

## Follow-up (coordinator, 2026-11-18 — owner ruling FG1 + India ESI number)

### FG1 — one shared gate, no restated group lists

Checked every line this phase added (`git diff 2a822298d..wdgap-s2b2`, tests excluded):
**no production line names a group.** Who may see and use a fund file is decided only by S2-A's
helpers on `pb.gov.form.rights` (`pb_form_lines/models/form.py:39-42` `OFFICER_GROUPS` /
`MANAGER_GROUPS`, `:250` `_pb_is_officer`, `:258` `_pb_require_officer`), reached through code
S2-A owns:

| Way in | Gate | Owner |
|---|---|---|
| Fund files tiles on Compliance › Filings | `pb_govt_reports/models/pb_govt_reports.py` `_forms_for` → `Rights._pb_is_officer()` (S2-A line, unchanged here) | S2-A |
| Form lines / check / prepare / send / download of a fund file | `pb.gov.form.board._door` → `_pb_require_officer`; `pb.gov.filing.prepare` / `_pb_download` → `_pb_require_officer`; my `flow_check` override calls `super()` (the door) before anything else | S2-A |
| VN social-insurance reports (mapped items) | unchanged: the report wizard's own rights; `_pb_si_items` reads under sudo AFTER them | pb_hr_govt |

So when the S2-A builder widens the shared gate for FG1, the fund files follow with no change
here; nothing to re-point. (The tests' `OFFICER`/`MANAGER` strings are fixture logins, not
gates; the HR-only login they refuse holds `hr.group_hr_user`, not
`pb_hr_govt.group_pb_hr_govt_user`, so FG1 does not change their expectation.)

The two board fixes are in **shared `pb_govt_reports` code** (`get_govt_reports_data`); they
touch no S2-B1 file and no gate. Exact diff for the merger (on top of `origin/wdgap-s2a`
`pb_govt_reports/models/pb_govt_reports.py`):

```diff
         try:
-            cfgs = self.env['hr.formula.config'].with_context(active_test=False).search(
+            # sudo: only the country codes of this company's own schemes are read
+            # (a payroll officer without formula rights saw no country — S2-B2)
+            cfgs = self.env['hr.formula.config'].sudo().with_context(active_test=False).search(
                 [('company_id', '=', company.id)])
             present |= {(c.country_code or '').upper() for c in cfgs if c.country_code}
         except Exception:
             pass
         present.discard('')
 
-        sel = (country_code or home_cc or 'VN').upper()
+        # WDGAP S2-B2: a company with no country of its own opens on its pay
+        # schemes' country (it used to open on Vietnam whatever it paid)
+        sel = (country_code or home_cc or (sorted(present)[0] if present else 'VN')).upper()
```

plus the grouping hunks listed in §5 task 3 (`_forms_for` drops `section == 'reports'`,
`_SECTION_ORDER`, `_SECTION_ICON`, `_form_groups`, `'forms'` = tax returns only,
`'form_groups'`), and in `static/src/xml/govt_reports.xml` the "Form lines" door condition
`state.data.form_groups and state.data.form_groups.length`, the `form_groups` panel loop and the
fund flag line. If the FG1 gate change rewrites `get_govt_reports_data`, re-apply these hunks on
top; they do not depend on who passes the gate.

### India ESI number — one list

Every member-number field the fund files look for is now a named constant at the top of its
file (the only place to edit):

| Constant | Value today | File |
|---|---|---|
| `ESI_EMPLOYEE_FIELDS` | `('pb_in_esi_number', 'esi_ip_number', 'esi_number')` | `pb_form_lines/models/fund_in.py` |
| `ESI_CONTRACT_FIELDS` | `('esi_number',)` (legacy, uninstallable) | same |
| `UAN_EMPLOYEE_FIELDS` / `UAN_CONTRACT_FIELDS` | `('pb_in_uan_number', 'uan_number')` / `('uan_number',)` | same |
| `NRIC_EMPLOYEE_FIELDS` / `NRIC_CONTRACT_FIELDS` | `('pb_sg_nric', 'singapore_nric_fin')` / `('singapore_nric_fin',)`, then the national ID when it has the S/T shape | `fund_sg.py` |
| `BPJS_TK_FIELDS` / `BPJS_KES_FIELDS` | `('pb_bpjs_employment_number',)` / `('pb_bpjs_health_number',)` | `fund_id.py` |

**Merge-time task 6:** when `WDGAP_S2D_REPORT.md` "Follow-up ESI" names the HR-only ESI field,
put that name FIRST in `ESI_EMPLOYEE_FIELDS` (`pb_form_lines/models/fund_in.py`). If it is
`pb_in_esi_number`, nothing to do — it is already first. (`origin/wdgap-s2d` @ d157190ca does
not name it yet.)

Tests added (`TestS2B2FundFiles`):
* `test_esi_number_on_the_record_puts_the_person_in_the_file` — no mock of the probe: a real
  employee field is put on `ESI_EMPLOYEE_FIELDS` and filled for one person → that person is IN
  the ESI file under the number ("In the file: Yes"); the others are left out with "No ESI
  insurance number on the employee record".
* `test_esi_field_from_tax_details_when_installed` — uses the first listed name that exists on
  `hr.employee` (S2-D's field after the merge), fills it → the person is IN the file; skipped
  until such a field exists (skipped on this branch).
* The helper that stands in for the missing UAN/ESI fields now keys on the constants, so
  renaming the list does not break it.

Results (fresh `wdgap_s2b2_t` from `upd_p6_t_tpl`, same upgrade set, `/pb_form_lines,/pb_govt_reports`):
**48 tests, 0 failed, 0 errors**; `test_esi_number_on_the_record_puts_the_person_in_the_file`
passes; `test_esi_field_from_tax_details_when_installed` skipped (no ESI field on this branch —
it runs after the S2-D merge). Database dropped afterwards.
