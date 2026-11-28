# WDGAP S2-A report — form lines, the filing engine, Indonesia + Vietnam monthly tax returns

Builder, 2026-11-18. Branch `wdgap-s2a` (from `origin/19.1` @ 116386329). Not merged, not
deployed. Handover: `WDGAP_S2_HANDOVER.md` §S2-A; facts: `WDGAP_S2_FACTS.md` (both copied
into this folder). Local copy `wdgap_s2a_t` (from `upd_p6_t_tpl`, 44 behind modules `-u`,
`pb_fund_payments` + `pb_retro` installed), port 8752.

## 1. What was built

| # | Item | Where |
|---|---|---|
| 1 | Catalogue `pb.gov.form` / `pb.gov.form.line` (country, code, period kind, files made, source note + URL, `inferred` + note, valid from/to, quarter allowed; line kind money / count / text / computed, per person / total, population all / residents / non-residents, `base_line_id`, `only_if_line_id`, sum / ratio / percent operands, sign rule, required, Suggest words + roles). Data `noupdate="1"`: ID_BPMP (5 lines), VN_05KK_TT89 (31 lines), VN_05KK_TT80 (17 lines) | `pb_form_lines/models/form.py`, `data/forms_id.xml`, `data/forms_vn.xml` |
| 2 | Mapping `pb.gov.form.map(line, rule, source payslip_line / computed_value, sign add / subtract, share %)`, company from the scheme, unique (line, item) only — one item may sit on several lines/forms; record rule per company. Suggest from line words + pay roles, one proposal per scheme per line, never saves | `models/form_map.py` |
| 3 | Reader contract (below) | `models/reader.py` |
| 4 | Filing `pb.gov.filing` + `pb.gov.filing.file` (sha256 per file, one stamp over all), states draft/pending/approved/returned/rejected/superseded, process key `filing` (no seed, capabilities = `pb.filing.proposal`'s when installed), seat hook, approved-bytes-only download (`/pb_form_lines/filing/download`, 403/404 otherwise) + history line + `biz.audit.entry` line (no tax number), prepare supersedes the last try (withdraws its request), G3 mark decided at prepare (`adviser_mark`) | `models/filing.py`, `controllers/download.py` |
| 4b | "Accepted by the authority" per company per form (`pb.gov.form.company`: payroll manager only, who/when kept, untick allowed and written in its history); employer's tax number + place of business number | `models/form.py` |
| 5 | Renderers `_pb_render_id_bpmp` (BPMP XML for the tax office's import + the converter's DATA sheet + a summary workbook with every person and why someone was left out) and `_pb_render_vn_05kk_tt89/_tt80` (workbook in the form's line order + a People sheet + To check sheet). No official VN XML (schema not confirmed) | `models/render_id.py`, `models/render_vn.py` |
| 6 | Filings board: tiles "Tax returns" for the company's country beside the VN social-insurance tiles (payroll officers only), Form lines door, stepped flow Period → Check → Approval and download (`pb_gov_filing`), Form lines board (`pb_form_lines`); gate fix S2F-8 | `pb_govt_reports` (models, js, xml, scss, ACL, learn manifest), `pb_compliance_hub/static/src/js/compliance_hub.js`, `pb_form_lines/static/` |
| 7 | False-claim doors retired (list in §4) | legacy country modules, `pb_govt_reports` catalogue/adapters |
| 8 | VN social-insurance honesty fixes (done payslips only; insurance-book number from `vietnam_social_insurance_number`, empty when missing; placeholder literals removed). Code→item reading (SICK/MAT/ALLOW/EXTRA) **unchanged — wave-2 candidate** | `pb_hr_govt/models/report_base.py`, `pb_hr_govt/report/*.py` |

### The reader contract (binding for wave 2)

```python
env['pb.gov.form.reader'].read(form, company, period_start, period_end,
                               scheme_ids=None, currency_id=None)
# form: record, id or code ('ID_BPMP'); company: record or id
-> {'lines': {line_code: amount},            # totals; text lines absent; counts are ints
    'employees': [{'employee_id', 'name', 'lines': {code: value}, 'identity': {...},
                   'resident': bool, 'payslip_ids': [...], 'scheme_ids': [...],
                   'checks': [str]}],
    'payslip_ids': [...],
    'warnings': [{'code', 'level': 'block'|'warn'|'info', 'message', 'employee_ids'}],
    # stable extras: 'form', 'company_id', 'period_start', 'period_end', 'currency',
    #   'currency_id', 'currencies', 'schemes', 'tax_years': {config_id: {key,label,start,end}},
    #   'unfinished_count'}
env['pb.gov.form.reader'].read_form(...)      # same, safe name (S2A-4)
env['pb.gov.form.reader'].period_bounds(form, day, config=None)  # month / tax quarter / tax year
env['pb.gov.form.reader']._pb_read(...)       # same without the officer check (server code after its own door)
```

Rules: done/paid payslips only; pay month = month the payslip period ENDS in (fund payments'
rule), `period_start <= date_to <= period_end`; lines by `(formula_config_id, code)` in one
SQL; deduction / employer-cost by size, back-pay lines of those roles by
`pb_backpay_band_amount` (probe of pb_retro), pre-stamp lines by category DED/DEDUCTION/COMP;
map sign × share applied after; worked-out values = `formula_input_values` then
`formula_computed_values`; two currencies → `block` warning `two_currencies`, nothing added,
`currencies` listed (pass `currency_id` to split); tax year per scheme with warning
`crosses_tax_year`; identity hooks `_pb_identity_<cc>(form, employee)` (wave 2 adds `_in`,
`_sg`); warning codes: nothing_mapped, two_currencies, currency_not_used, crosses_tax_year,
unfinished, scheme_not_mapped, no_payslips, identity_missing, line_not_mapped.

Filing renderer hook: `pb.gov.filing._pb_render_<form code lower>(self, data) ->
[(filename, bytes, mimetype)]`; `data` = the reader's answer + `adviser_mark`,
`adviser_text`, `settings` (employer_tax_id, place_of_business), `company_name`,
`period_label`. Board RPC: `pb.gov.form.board` get_forms / get_form / item_options /
save_line / suggest / accept_suggestions / save_settings / set_accepted / flow_start /
flow_check / flow_prepare / flow_submit / get_filing / download_check.

## 2. Layout sources

| Form | Source (published) | Confirmed? |
|---|---|---|
| ID_BPMP | Direktorat Jenderal Pajak, "Template XML dan Converter Excel ke XML" (Coretax), https://www.pajak.go.id/reformdjp/coretax/template-xml-dan-converter-excel-ke-xml — "BPMP Excel to XML v.3.xlsx" (updated 17 Apr 2025: DATA sheet + BPMP column guide + REF + XML map `MONTHLYPAYROLL`) and "bpmp.zip" (XML template, 7 Nov 2024). The schema is copied unchanged into `pb_form_lines/tests/data/bpmp_monthlypayroll.xsd`; every XML the tests make validates against it | **Confirmed** (layout, element order, enumerations) |
| VN_05KK_TT89 | Thông tư 89/2026/TT-BTC (in force 1 Jul 2026), quarterly only, [15]–[45]: comparison published by FAST, https://fast.com.vn/so-sanh-mau-05-kk-tncn-theo-thong-tu-89-2026-tt-btc-va-thong-tu-80-2026-tt-btc/ (cites Công văn 5746/CT-CS); transition (Q3 2026 onwards; TT80 allowed meanwhile, Art. 100): STAX, https://stax.com.vn/to-khai-thue-tncn-quy-3-2026-nop-theo-mau-tt80-hay-tt89-huong-dan-chi-tiet/ | **INFERRED** — official appendix pages answered 403; wording of new lines reconstructed |
| VN_05KK_TT80 | Thông tư 80/2021/TT-BTC Phụ lục II Mẫu 05/KK-TNCN [16]–[32]: indicator guide published by ECN, https://ecn.net.vn/tin-tuc/to-khai-thue-tncn-05-kk-tncn-huong-dan-chi-tiet | **INFERRED** (secondary source) |

INFERRED list (also on the records, shown on screen as "Not confirmed"):
1. ID: TaxCertificate — the schema says `N/A, DTP, ECT`, the converter's REF sheet and the official sample say `ETC` (the official sample fails its own schema); only `N/A` is written.
2. ID: Rate = the person's own tax withheld ÷ gross × 100 from their payslips (2 decimals), unless HR maps an item to the Rate line. Withholding date = last day of the period. Tax object code `21-100-01`. Place of business number defaults to the 16-digit tax number + `000000` (the converter's sample pattern). Resident = has a 16-digit NIK (or NPWP); foreign = passport and no NIK.
3. ID: December / last month of the tax year is reported on the year-end slip (BPA1, wave 2); BPMP is filed for the other months — not enforced, said in the source note.
4. VN TT89: the whole line list (secondary source); lines [26]–[28], [32]–[41] wording reconstructed; [16] counts every tax resident (contract length not checked); [29]–[31] "subject to withholding" taken as people with tax withheld (line 42 > 0).
5. VN TT80: the line list (secondary source); [17] and [26]–[28] as above (line 29).
6. VN: no official XML for the tax office's declaration software (schema not confirmed) — left out.

## 3. Tests

Numbered cases (all on `wdgap_s2a_t`):

| # | Case | Test | Result |
|---|---|---|---|
| 1 | Mapping CRUD, one item on two lines, company isolation | `pb_form_lines` T1 | pass |
| 2 | Suggest proposes, saves nothing; accepting saves only ticked | T2 | pass |
| 3 | Reader: done only, two schemes, worked-out value, deduction sign, back-pay line, April tax year, two currencies refused/split, contract shape + RPC gate | T3a–T3e | pass |
| 4 | ID return totals = sum of mapped figures; identity warning (no number in text); XML valid against the published XSD; converter cells; summary lists who is left out; no employer number → plain refusal | T4 | pass |
| 5 | VN return (TT89 Q3): counts, residents/non-residents, [20]/[29]/[32]/[42]/[45]; TT80 for June; each layout refuses the other's periods | T5 | pass |
| 6 | Route: pending → decider WITHOUT payroll group decides (seat = read) → approved → officer downloads approved bytes; decider cannot download; trail names the file, no tax number; changed bytes refused; fast lane | T6, T6b | pass |
| 7 | Supersede (approved one replaced, cannot be downloaded or re-sent) | T7 | pass |
| 8 | Adviser mark in every file until accepted, absent after; officer cannot tick; manager who/when; untick | T8 | pass |
| 9 | Officer/manager yes; HR without payroll + portal no — screen (RPC board), URL (HttpCase: 200 + bytes for officer, 303/403/404 for others), records | T9 + `test_s2a_access_http` | pass |
| 10 | Retired doors make no claim | `pb_hr_payroll_vietnam` `test_wdgap_s2a_retired`, `pb_compliance_hub` `test_the_false_claim_countries_are_retired`, `pb_govt_reports` `test_wdgap_s2a` 4 | pass |
| 11 | VN social insurance golden (recorded on origin/19.1) + three fixes | `pb_hr_govt` `test_wdgap_s2a_honesty` 11a–11d | pass |
| 12 | Silent install (nothing mapped/filed/asked, no job, no mail template, catalogue noupdate) | T12 | pass |
| 13 | PO gate (parse, three markers, header "Payobook 19.0", every code string translated vi+id, no "Odoo"); no "Odoo" in any file made or its name | `test_s2a_po_gate` + T4/T5 | pass |
| 14 | Browser walk | §3.2 | done |

### 3.1 Suites vs baseline

Baseline on an archive of `origin/19.1` (same DB, before any edit): `/pb_govt_reports,
/pb_compliance_hub,/pb_hr_govt,/pb_hr_payroll_vietnam,/pb_pay_delivery:TestIdb1VnGolden` —
**77 tests, 2 failed**: `TestFilingFlow.test_generating_a_vn_filing_produces_a_real_file`
(the local filing route waits for approval, so `done` is False) and
`TestFilingFlow.test_the_facade_can_only_generate` (a `getattr(w, 'submission_period')` the
test did not expect). `pb_hub:TestPaletteRowsFollowTheirTabs` on origin: **8 tests, 1 failed**
(`test_every_tab_has_a_row_or_says_why_not`: Step 6 tabs without ⌘K rows — not ours).

Branch, same tags + `/pb_form_lines` + `/pb_hub:TestPaletteRowsFollowTheirTabs` — 116 tests:
* `test_generating_a_vn_filing_produces_a_real_file` — baseline;
* `test_the_facade_can_only_generate` — **now passes** (the `submission_period` getattr went with the retired adapters);
* `pb_hub` `test_every_tab_has_a_row_or_says_why_not` — baseline;
* `pb_hub` `test_deep_links_onto_a_tab_carry_its_gate` — **expected, merge-time task 1** (the hub's restated Filings gate);
* `pb_form_lines` T2/T12 failed once because the browser-walk seed was committed into the test DB; made company-scoped (ledger S8D-6), re-run `/pb_form_lines`: **20 tests, 0 failed**.
* VN bank-file golden (`TestIdb1VnGolden`) passes — bytes unchanged.

### 3.2 Browser walk (local, `s2a.localhost:8752`, isolated browser context)

Compliance › Filings (Indonesia company): "Tax returns" tile with "Pay items to choose on Form
lines"; Form lines board (desktop 1440 two columns, 700 and phone 390 one column, no sideways
scroll): Suggest → 3 proposals → Save; employer's tax number saved; Prepare a filing → Check
(3 people, 30,000,000 gross, 1,045,000 tax, rate 3.48, "1 person has no NIK or tax number") →
Prepare and send → Approved (fast lane) → 3 files; Download (stubbed download helper, then the
URL fetched: 200, attachment, XML with the adviser comment). Vietnam company over RPC in
Vietnamese: TT89 Q3 lines in Vietnamese, route → "Chờ duyệt", waiting for the payroll manager.
Reload of the flow without a form id now falls back to the company's first form. Console: no
errors from these screens (one 500 on the template's missing website logo — template filestore,
pre-existing, ledger S6A-7). Fixes from the walk: small buttons lacked the kit base class
(S2A-7), singular "1 person" sentence, reload fallback (S2A-9), quarter file names.

## 4. Retired doors (item 7)

| Door | Before | Now |
|---|---|---|
| SG CPF `cpf.submission.wizard.action_generate_cpf_file` | toast "file generated" | UserError "This file is not available yet, so nothing was made…" |
| TH SSF `social.security.wizard.action_generate_ssf_file` | same | same |
| KH NSSF `nssf.wizard.action_generate_nssf_file` | same | same |
| MY EPF/SOCSO/EIS `epf.wizard.action_generate_epf_file` | same | same |
| MY / KH payroll import `action_import_{malaysia,cambodia}_data` | "imported successfully" | UserError "This import is not available yet, so nothing was imported…" |
| VN tax report wizard `action_generate_report` | "generated successfully" | UserError pointing to Compliance › Filings |
| VN dashboard `action_generate_vietnam_tax_report` | opened the false-claim wizard | same refusal |
| VN dashboard `action_generate_vietnam_social_insurance_report` | opened a model that does not exist | UserError pointing to the social-insurance reports on Filings |
| VN employee `action_vietnam_generate_tax_report` | opened the false-claim wizard | same refusal |
| Filings board SG/TH/KH/MY tiles + flow adapters | tiles only when the wizard model was installed | removed from `_CATALOG`, `ADAPTERS`, `_GENERATE` |

No model removed, no data migration. Note (S2A-1): the SG/TH/KH/MY/ID/IN legacy modules are
`16.0.x` manifests → uninstallable on 19; those doors were never reachable on any database.

## 5. Version raises and deploy notes

| Module | Version | Action |
|---|---|---|
| pb_form_lines | 19.0.1.0.0 (new) | `-i` (depends: mail, om_hr_payroll, pb_hr_payroll_formula, biz_approval_workflow, pb_approval_config, pb_hub, pb_import_kit, pb_filter_kit — no VN dependency) |
| pb_govt_reports | 19.0.1.2.2 → 19.0.1.3.0 | `-u` (ACL rows, board, flow) |
| pb_compliance_hub | 19.0.1.2.2 → 19.0.1.2.3 | `-u` (gate) |
| pb_hr_govt | 19.0.1.1.0 → 19.0.1.1.1 | `-u` |
| pb_hr_payroll_vietnam | 19.0.1.2.3 → 19.0.1.2.4 | `-u` (many dependents reload; Python only) |
| pb_hr_payroll_{singapore,thailand,cambodia,malaysia} | 16.0.1.0.1 → 16.0.1.0.2 | nothing (uninstallable) |

* JS/SCSS/XML changed → asset purge + restart.
* Silent install to check after `-i`: `pb_gov_form_map`, `pb_gov_filing`, `pb_gov_form_company` empty; no `biz_approval_request` with `res_model='pb.gov.filing'`; no new `ir_cron`; 3 forms / 53 lines.
* No payslip figure changes (nothing writes payslips). Rehearsal on rize: read-only — run the reader for a rize ID and VN month with a mapping made in the copy and compare totals by hand with the payslips; check rize's `filing` route (whatever rize published applies).
* Who sees the Filings lens (revised by FG1, §9): **nobody loses it**. Gainers = payroll officers/managers who do NOT hold `pb_hr_govt.group_pb_hr_govt_user` — count them per database before go-live (read-only: users in `pb_hr_payroll_base.group_payroll_base_officer` ∪ `…_manager` minus users in `pb_hr_govt.group_pb_hr_govt_user`, active, internal). Everybody who sees the lens can also prepare and download filings (the "Government reports" permission now prepares/downloads the new tax returns too).
* FG1: `pb_govt_reports` now depends on `pb_form_lines` (install `pb_form_lines` first or in the same `-i`/`-u` run).

### Merge-time tasks (other lanes)

1. `pb_hub/static/src/js/hub_palette_entries.js:143` →
   `const CMP_FILINGS = ["pb_hr_payroll_base.group_payroll_base_officer", "pb_hr_payroll_base.group_payroll_base_manager", "pb_hr_govt.group_pb_hr_govt_user"];`
   (three groups since FG1)
   (fixes `pb_hub` `test_deep_links_onto_a_tab_carry_its_gate`; ledger S2A-2).
2. Optional: `pb_compliance_hub/data/pb_sidebar.xml:34` — the Compliance rail item is shown to
   `pb_hr_govt.group_pb_hr_govt_user` + payroll manager; a payroll officer without either does
   not see the rail item (unchanged here — hub door, not the Filings lens).
3. S2-D: the Indonesian tax status (PTKP) field `pb_me_tax` adds on `hr.employee` — the reader
   probes `pb_ptkp_status`, `pb_tax_ptkp_status`, `ptkp_status`; if S2-D names it otherwise,
   add the name to `_pb_identity_id` (`pb_form_lines/models/reader.py`).

## 6. Left for later

* VN social-insurance reports onto form lines (still read SICK/MAT/ALLOW/EXTRA; wave 2). The
  BHXH630 bank holder still falls back to the company name (not a literal; left as is).
* ID: tax facility other than N/A; Rate from TER tables (Step 1 territory); December (BPA1).
* VN: official XML; contract-length test for [16]/[17].
* A ⌘K palette row for Form lines (pb_hub lane).

## 7. Gotchas → ledger

S2F-1..8 (facts) and S2A-1..9 added to `WDGAP_LEDGER.md`; D3 marked superseded by G1–G4;
phase rows S2-A / S2-C / S2-D / S2-B added.

## 8. Owner questions

1. The Indonesian file needs the company's tax number and "place of business" number. Should
   the place-of-business number always be the tax number followed by six zeros (what the tax
   office's own example shows), or will each company type its own?
2. The Indonesian rate is worked out from each person's own tax and gross pay. If your pay
   schemes already keep the official rate as a figure, do you want HR to point the Rate line at
   it instead?
3. Vietnam changed its tax declaration in July 2026. We built the new quarterly one and the old
   one from published guides, because the official pages could not be opened. Can an adviser
   or customer send one filed declaration so we can check the line numbers?
4. ~~Who sees Compliance › Filings~~ — answered by FG1 (§9).

## 9. Follow-up FG1 (owner ruling 2026-11-18 ~15:45)

**Ruling.** Compliance › Filings (the lens, the Tax returns tiles, Form lines, Prepare a
filing, download of approved files) is open to BOTH payroll officers/managers AND the
"Government reports" permission (`pb_hr_govt.group_pb_hr_govt_user`, incl. the
vendor-access role "govt-reports"). Nobody loses the lens. S2F-8's point stands — lens gate
= generate gate = download gate — all three were widened together. "Accepted by the
authority" stays payroll manager only; who approves stays whatever the `filing` route names.

**What changed (every gate, one list of three groups):**

| Gate | File:line |
|---|---|
| Screen gate (lens) | `pb_compliance_hub/static/src/js/compliance_hub.js` `FILINGS_GATE` (+1 entry) |
| VN social-insurance generate (flow) | `pb_govt_reports/models/pb_filing_flow.py` `_FILING_GROUPS` (+1 entry) |
| Carrying out an approved VN filing proposal | `pb_govt_reports/models/filing_approval.py` `_proposal_gate_groups` (officer, manager, government reports) |
| Tax returns: board RPC, reader officer check, prepare, download URL (all call `pb.gov.form.rights`) | `pb_form_lines/models/form.py:39-46` `OFFICER_GROUPS` (+ `pb_hr_govt.group_pb_hr_govt_user`, read by xmlid; `MANAGER_GROUPS` unchanged) |
| ACL rows for the permission on `pb.gov.form`, `.line`, `.form.map`, `.form.company`, `pb.gov.filing`, `.filing.file`, `pb.filing.proposal` | `pb_govt_reports/security/ir.model.access.csv` (+7 rows) |
| Record rules (all filings of the user's companies; proposals of the user's companies) | new `pb_govt_reports/security/filings_fg1_rules.xml` |
| Dependency so those rows can name the models | `pb_govt_reports/__manifest__.py` depends + `pb_form_lines` |

**Not touched:** `pb_form_lines/models/reader.py` and `pb_form_lines/models/filing.py`
(0 lines) — both already ask `pb.gov.form.rights`; the only `pb_form_lines` code line
touched is `models/form.py:39-46` (comment + the `OFFICER_GROUPS` tuple). Siblings
`wdgap-s2b1` / `wdgap-s2b2` merge cleanly unless they edited that tuple.

**Tests (access matrix).** `pb_form_lines` T9 now: yes = payroll officer, payroll manager,
Government reports permission alone (board, Check, reader, prepare, download of approved
bytes); no = HR without either, a plain internal login (line manager / employee), portal
(board RPC, records, download). HTTP T9: Government reports permission → 200 + approved
bytes; HR, plain login, portal → 303/403/404. T8: the Government reports permission alone
cannot tick "Accepted by the authority". `pb_govt_reports` `test_wdgap_s2a` 2/3: the
permission alone opens and generates the VN social-insurance filing and sees the tax-return
tiles; HR-only / plain login refused and see no tiles. `pb_compliance_hub`: lens gate ==
`_FILING_GROUPS` (3 groups), lens gate ⊆ the wizard's ACL groups.

Run on a fresh copy (`upd_p6_t_tpl` → `wdgap_s2a_t`, 44 behind modules `-u`,
`-i pb_form_lines` + `-u` touched): **116 tests, 3 failed = the same three as before FG1**:
`test_generating_a_vn_filing_produces_a_real_file` (origin baseline),
`pb_hub test_every_tab_has_a_row_or_says_why_not` (origin baseline),
`pb_hub test_deep_links_onto_a_tab_carry_its_gate` (merge-time task 1, now with three
groups). No new strings (no PO change).

**Merge-time tasks added by FG1:**
1. (updated in §5) `pb_hub` `CMP_FILINGS` = the three groups.
4. `pb_payai_actions/payai/actions_amber.py:64` `FILING_GROUPS` (PayAI "prepare a filing"
   command) still names officer/manager only — add `pb_hr_govt.group_pb_hr_govt_user` so
   PayAI follows the lens too (other lane; not changed here).
5. `pb_compliance_hub/data/pb_sidebar.xml:34` (Compliance rail item) already shows the item
   to the Government reports permission + payroll manager; a payroll OFFICER without either
   still has no rail item (unchanged; optional: add the officer group).
