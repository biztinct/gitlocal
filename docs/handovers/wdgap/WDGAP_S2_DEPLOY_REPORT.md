# WDGAP Step 2 — deploy report (merge S2-A, S2-B1, S2-B2, S2-C, S2-D; live ×5; verify)

Merge-deploy-verify agent, 2026-11-18 (UTC). Handover `WDGAP_S2_DEPLOY_HANDOVER.md` (copied beside this
report; method of the W3 / IDB1 deploy handovers and the proven IDB1-F scripts).

**Result: merged, LIVE on all five databases** (payobook, payobook_template, p0clone, rize, sudima) at
`34aaf505c` (`origin/wdgap-s2-merge`; `19.1` fast-forwarded to it with this report). Three new modules
installed ×5 (`pb_form_lines`, `pb_me_tax`, `pb_me_tax_cert`), nine upgraded ×5, three shipped as files
only. **429 s down** (09:21:41–09:28:50 UTC). Deploy notes START 08:45, DONE 09:41 UTC. abm, pbf_preview,
recruit_connect untouched; no Codex module touched (all 18 live trees were byte-identical to `origin/19.1`
before the merge — nothing newer on the server, nothing rolled back). Nothing held back.

Bank-copy batches: **rize 59 were approved earlier today by Codex with the owner's authority** (deploy
notes 03:19 UTC, before this deploy); **sudima 358 still waiting**, untouched.

## 0. Before anything

`git fetch`; every branch carried its Follow-up section(s): S2-A "9. Follow-up FG1"; S2-C "Follow-up BL1" +
"Follow-up BL4"; S2-D "Follow-up TD1–TD3" + "Follow-up ESI"; S2-B1 "7. Follow-up YE1–YE3"; S2-B2
"Follow-up (coordinator … FG1 + India ESI number)". Tips merged: s2a `cfa129a68`, s2b1 `b3e532709`,
s2b2 `544b5a31c`, s2c `90d97d739`, s2d `63db1ff41`.

## 1. Merge

Branch `wdgap-s2-merge` from `origin/19.1` @ `94f3adea2`, `--no-ff` in the order s2a, s2b1, s2b2, s2c, s2d.
Conflicts only in the s2b2 merge (`15fdf9708`): `pb_form_lines` manifest / `models/__init__.py` /
`tests/__init__.py` (union), `pb_form_lines` vi/id PO (merged by msgid: 102 entries added, 417 joined by
occurrence, no duplicate msgid), `pb_govt_reports` vi PO (union), `govt_reports.xml` (see task g).
s2c and s2d merged without conflict. Merge-time edits in `34aaf505c`.

### 1.1 Merge-time tasks

| # | Task | Done — file / lines |
|---|---|---|
| a | `pb_hub` palette Filings gate = FG1 three groups | `pb_hub/static/src/js/hub_palette_entries.js:143-146` `CMP_FILINGS` (officer, manager, Government reports). Fixes `test_deep_links_onto_a_tab_carry_its_gate` (passes). JS only — no version change, no `-u pb_hub` (asset purge) |
| b | `pb_form_lines` manifest + `models/__init__.py` union, ONE raise | `__manifest__.py` data/asset lists = S2-B1 + S2-B2 lines; version **19.0.1.1.0**; `pb_govt_reports` one raise **19.0.1.4.0** (both builders); `pb_hr_govt` 19.0.1.2.0 (B2's own). B2's shared-file diff (`get_govt_reports_data` sudo + country fallback) arrived through the merge |
| c | Identity probes = `pb_me_tax`'s real field names | Already exact on the branches: `reader.py:170` `pb_id_ptkp_status` first (monthly BPMP and year-end BPA1 share `_pb_identity_id`); `reader.py:231/238/268` `pb_in_pan_number`, `pb_in_tax_regime`, `pb_sg_tax_residency`; `fund_in.py:36/38` `pb_in_uan_number`, `pb_in_esi_number` FIRST (B2 task 6 — nothing to rename). Proved by new seam tests M1 (number on file → in, empty → left out with the reason) and B2's `test_esi_field_from_tax_details_when_installed` (now runs, passes) |
| d | `pb_me_portal` pinned "Me" list | `pb_me_portal/tests/test_me_home.py` test_02: `added` learns `'/my/tax', '/my/tax-certificates'` (+ comment) — test line only, no other edit. Tax certificates moved under "Me" right after Tax details: `pb_me_tax_cert/models/pb_me_home.py` group `me`, seq `GROUPS.index('me')*100 + 12` (B1 asked +11, which S2-D already uses); its own test line updated (`tests/test_tax_cert_portal.py:111`) |
| e | One Filings gate (FG1) | Six places name the Filings groups, all the same three: `pb_form_lines/models/form.py:54` `OFFICER_GROUPS`, `pb_govt_reports/models/pb_filing_flow.py:80` `_FILING_GROUPS`, `filing_approval.py:53` `_proposal_gate_groups`, `pb_compliance_hub/.../compliance_hub.js:73` `FILINGS_GATE`, `pb_hub` `CMP_FILINGS`, PayAI (below). "Accepted by the authority" + "Release to employees" = `MANAGER_GROUPS` (payroll manager only). Seam test M2 pins all of them. ACL: two rows added for the Government reports permission (`pb_govt_reports/security/ir.model.access.csv`: certificate read; "asked us to settle" read/write/create — S2-B1's FG1 note) |
| — | **PayAI "prepare a filing"** (handover addition) | One-place change: `pb_payai_actions/payai/actions_amber.py:63-73` `FILING_GROUPS` now IS the flow's `_FILING_GROUPS` (imported; fallback = the same three). Version 19.0.4.2.3 |
| f | Tax details → Tax certificates link | **Skipped**: neither report offers a hook for it (S2-D only says certificates "can sit on /my/tax"); both tiles now sit side by side under "Me" |
| g | (found at merge) Two tile groupings | S2-B1 grouped tiles by `tile_group`, S2-B2 by `filing_section`, both labelled "Shown under" (a load warning) and each asked the merger to keep ONE. Kept `filing_section` (B2 task 3): `year_end` added to `SECTIONS` (`fund_form.py:39`); B1's 8 year-end forms get `filing_section=year_end`, B2's 5 fund forms `tile_group=fund_file` (the two agree on every form — seam M3); `tile_group` relabelled "Tile group"; `get_govt_reports_data`: `forms` = tax returns, `year_end_forms` = year-end, `form_groups` = every group; the board renders ONE grouped loop (Year-end keeps its award icon and "A certificate for each person"); `needs_place` stays on for year-end (BPA1 carries the place-of-business number). B2's test pinned `['tax','fund']` for ID → now `['tax','year_end','fund']` |
| — | S2-C out-of-lane tasks | **Not done** (left for later): import column "IFSC/Bank code" still goes to the SWIFT/BIC lane; the bank-document check still reads only Vietnamese banks |
| — | Optional, not done | Compliance rail item for a payroll officer without the Government reports permission (S2-A task 2/5); S2-D M2 (proof link in the Approvals drawer) |

### 1.2 Static gates (merged diff vs `origin/19.1`, 200 files)
py_compile 122, XML 29, `node --check` 9 JS, PO parse 18 (polib): **0 failures**, 0 duplicate msgid, 0 msgstr
naming the vendor. Five pre-existing PO headers read "Odoo Server 19.0" (metadata, not shown; untouched).
Vendor word on added lines: only `<odoo>` tags, `@odoo/owl` imports and tests asserting its absence.
Credentials: none.

### 1.3 Combined local run (Mac, `wdgap_s2m_t` = copy of `upd_p6_t_tpl`, 63 behind modules `-u`,
`-i pb_retro, pb_fund_payments, pb_me_details, pb_form_lines, pb_me_tax, pb_me_tax_cert`: EXIT 0, 0 ERROR)

| Run | Suites | Result |
|---|---|---|
| A | pb_form_lines 61 (incl. 7 merge seams), pb_govt_reports, pb_compliance_hub, pb_hr_govt, pb_hr_payroll_vietnam, pb_me_tax 45, pb_me_tax_cert, pb_me_details, pb_employee_vault, pb_me_portal, pb_fund_payments, pb_payai_actions | **649 tests, 6 failed + 48 errors = recorded baselines**: compliance `test_generating_a_vn_filing_produces_a_real_file` (S2-A); pb_me_portal ×6 (test_05_grid E, test_01_profile E, test_06_font, test_01_registry, test_12_vi_po, test_t1_7); pb_payai_actions 1 + 46 — **identical set with the 19.1 version of that module** on a copy (new baseline, ledger S2M-3). pb_me_portal `test_02` (pinned "Me" list) now passes |
| B | pb_pay_delivery 145, pb_bank_ocr 65, pb_approval_config 184, pb_settings 93 | **381 tests, 4 failed + 5 errors = recorded baselines** (u10, the look, u13, z06d, z06e; bank_ocr 07, 07b, 09, 15). Both goldens (Vietnamese bank file, general payment list, also under both BL4 settings) pass |
| C | pb_hub 44 (needs `-u pb_hub`, ledger S2M-2) | **2 failed = recorded baselines** (`test_the_kit_stacks_nothing_above_twenty`, `test_every_tab_has_a_row_or_says_why_not`); `test_deep_links_onto_a_tab_carry_its_gate` passes |

### 1.4 Seams on the merged tree

| # | Seam | Proof |
|---|---|---|
| 1 | VN bank file + general payment list byte-identical; layout file refused before approval, other-name accounts out (BL1), close names in + flagged (BL3); BL4 default leave out / "Pay by file" in + flagged + counted; notice HR only, Mark as seen hides it + who/when; install writes no employee row | goldens + S2-C BL1/BL4 tests (run B); local browser walk: employee **form** (Personal tab) AND **side panel** (header chip row, amber, "Mark as seen") both show "This bank account is in another person's name: …"; pressing it on the panel hid it, who/when + stamp stored; console clean |
| 2 | VN social-insurance reports byte-identical while nothing is mapped | `pb_hr_govt` S2-B2 golden + S2-A golden (run A) |
| 3 | Silent install | local copy and rize copy and live ×5 (§2, §3): 17 forms / 314 lines, 0 mappings/filings/certificates/released/settle ticks, 0 approval requests on filings, 0 tax-detail changes, 0 rules reading tax sources, 0 employee tax fields set, every company "Leave out", nobody marked seen, no new job, no mail template, no mail queued by it. The "Add your tax number" home reminder never shows for a person whose number is on file (S2-D TD1.3) |
| 4 | Payslips identical; nothing written by install | S2-D T8/T8b/T8c + TD3.4 (run A); rize copy: 236 payslips 0 differing; counts/checksums ×5 (§3) |
| 5 | Access matrix (payroll officer, payroll manager, Government reports holder only, HR without payroll, line manager, employee, another employee, portal) | S2-A T9 + HTTP T9, S2-B1 T6/T7 web, S2-B2 T8 + HTTP, S2-C 9 / BL4-5b, S2-D T1/T10/H5 — all pass on the merged tree; seam M2 |
| 6 | End to end (map → ID monthly return → approve → download; year-end → release → own certificate → take back; YE1 ticked person gets none) | S2-A T4/T6/T7, S2-B1 T6 + web T6/T7, YE1-2/YE1-3 (run A) |
| 7 | vi/id PO gate; no vendor word in strings, files, names, PDF metadata | S2-A `test_s2a_po_gate` (scans every pb_form_lines string incl. merged ones), `TestTaxCertPoGate`, S2-C 11, S2-D T11; static gates §1.2 |

Local databases dropped (5), file folders removed.

## 2. Backups and rehearsal (server)

**Backups** `/odoo/backups/wdgap-s2-20261118T084544Z/`: payobook 83,320,268 bytes, payobook_template
30,608,785, p0clone 31,037,938, rize 45,576,194, sudima 32,936,966 — each read back (`pg_restore -l`);
file folders hard-linked (10,190 / 582 / 174 / 1,275 / 1,207 files); previous trees of the 15 existing
modules (`previous-trees.tgz`). Evidence `/tmp/wdgap-s2-20261118T084544Z/`. Staged = `git archive
34aaf505c` (18 trees = commit).

**Rehearsal — PASSED** (hidden rize copy, every job and mail server off, 1,330 s; a second short copy,
178 s; both dropped with `--force`, file folders removed):

| Check | Result |
|---|---|
| Install + upgrade | EXIT 0 in 87 s; **0 ERROR, 0 Traceback**; all 12 versions = manifests |
| Payslips old vs new — runs 2110 (India), 2111 (Indonesia), 2112 (Vietnam), 2115 (India) | **236 payslips, 7,542 lines, 0 differing**; 175 computed identical line for line; 61 refused identically before and after (pre-existing, as in IDB1) |
| Vietnamese bank file, old vs new, runs 1591 + 2112, all 7 layouts | digests identical; MB Bank Excel 1 byte shorter = its build-time stamp (IDB1M-3) |
| General payment list, old vs new, runs 2111 + 2110 | CSV identical (digest + size); Excel identical by content, 1 byte = build stamp |
| Counts / checksums (contracts + components + tax code, payslips, lines, line total, runs, employees + identity, dependants, bank accounts, banks, bank-file fields, bank changes, bank files, payment lists, releases, detail requests, approvals, outbox, trail, mails, to-dos, users, groups, documents) | identical except **messages +6** — empty "name" tracking notes on 3 Rize job records and 3 server actions (proved on the second copy; the known upgrade side effect, W3M-4). Expected movements: record rules +12, bank layouts 7 → 10, bank directory 40 → 67 |
| Silent install on real data | as §1.4 seam 3 (0 everywhere; approval requests 173 → 173) |
| Bank-copy batch on the copy | `approved=59` before and after (approved on live by Codex before this deploy) |

**On the copy only** (runs marked finished inside the probe's transaction; everything rolled back, 0
filings/files left, 0 emails tried — counts only):

| Probe | Result |
|---|---|
| Indonesian bank layout, run 2111 | **118 people in the file, IDR 1,185,257,601**; 4 left out: 3 "Bank code is missing", 1 "Account is in another name"; company setting "Leave out"; no vendor word in the bytes |
| ID monthly return (BPMP), Aug 2026, Suggest → saved 8 items | 122 people, 122 finished payslips, IDR; **gross IDR 1,460,075,990.85 = the payslips' own worked-out gross by hand to within 0.04** (per-person rounding over 122 people); 1 person has no NIK/tax number; **Suggest did not find the monthly tax item** ("Income tax withheld" line not mapped) — HR picks it by hand |
| ID BPJS TK / BPJS Kesehatan | **Suggest proposes nothing** on Rize's Indonesian scheme (its items are named e.g. `IDBPJS…`) — HR maps by hand; check step refuses with "No pay item is on any line of this form yet" |
| IN Form 138, Jul–Sep 2026, Suggest → 3 | 27 people, INR 8,572,060 paid = payslips by hand; **27 of 27 have no PAN** (tax details not yet filled); tax deducted line not mapped |
| IN EPF ECR, Aug 2026, Suggest → 6 | 27 people; EPF wages INR 405,000 = by hand; **27 of 27 left out — no UAN** (expected) |
| IN ESI, Aug 2026, Suggest → 3 | 27 people; **27 of 27 left out — no ESI number** (expected; the field exists now) |
| "Add your tax number" reminder | 2 of 6 rize people with a login (India) |

## 3. Go live

- Read-only live checks first (08:12 UTC): no open START (last: Codex verifications); disk 25 GB free;
  service one process; live trees of all 18 modules = `origin/19.1` (Codex's latest combined `fc339ff05`
  = 19.1 + docs only); Codex's 18 Nov connector change only replaced a file inside `pb_clock` (not ours).
- Activity check: rize busy until 09:03:48 (489 signed-in requests in the 15 min before 08:44); the
  go-live script found **no answered signed-in request on rize/payobook since 09:06:41** → stop 09:21:41.
- Per database (order payobook_template, p0clone, sudima, rize, payobook):
  `-i pb_form_lines,pb_me_tax,pb_me_tax_cert -u pb_govt_reports,pb_compliance_hub,pb_hr_govt,pb_hr_payroll_vietnam,pb_pay_delivery,pb_bank_ocr,pb_me_details,pb_employee_vault,pb_payai_actions`;
  signal row + bundle purge + `web.assets.version` = `wdgap-s2-20261118T084544Z`. Upgrades 79, 78, 80,
  83, 97 s — all EXIT 0, 0 ERROR. payobook_template jobs 45, 84, 85, 86, 91 were switched on by the
  upgrade and switched straight back off.
- Start 09:28:49, port up 09:28:50: **429 s down (7 min 9 s)**. Five sites warmed: 200.

### Versions before → after (all five)

| Module | Before | After |
|---|---|---|
| pb_form_lines | — | 19.0.1.1.0 (installed) |
| pb_me_tax | — | 19.0.1.0.0 (installed) |
| pb_me_tax_cert | — | 19.0.1.0.0 (installed) |
| pb_govt_reports | 19.0.1.2.2 | 19.0.1.4.0 |
| pb_compliance_hub | 19.0.1.2.2 | 19.0.1.2.3 |
| pb_hr_govt | 19.0.1.1.0 | 19.0.1.2.0 |
| pb_hr_payroll_vietnam | 19.0.1.2.3 | 19.0.1.2.4 |
| pb_pay_delivery | 19.0.1.8.1 | 19.0.1.9.0 |
| pb_bank_ocr | 19.0.1.5.0 | 19.0.1.6.0 |
| pb_me_details | 19.0.1.0.0 | 19.0.1.0.1 |
| pb_employee_vault | 19.0.1.6.0 | 19.0.1.6.2 |
| pb_payai_actions | 19.0.4.2.2 | 19.0.4.2.3 |
| pb_hub, pb_me_portal | 19.0.1.13.2, 19.0.3.8.0 | same (files: palette gate; test line) |
| pb_hr_payroll_{singapore,thailand,cambodia,malaysia} | 16.0.1.0.1 (uninstallable) | files 16.0.1.0.2 |

### Verification
- **Trees**: all 18 server trees byte-identical to `34aaf505c`. **Versions**: manifest = `latest_version`
  ×5 (14 installed per site), 0 mismatches.
- **Jobs**: equal to the snapshot on all five (111/58, 99/40, 99/48, 99/91, 99/90); payobook job 156
  still OFF; no new job.
- **Data before = after** on payobook, payobook_template, p0clone, sudima (every item of §2's list); rize
  identical except messages +6 (as rehearsed). Record rules +12, bank layouts 7 → 10, directory 40 → 67 ×5.
- **Silent ×5**: as seam 3 (approval requests unchanged: 86 / 0 / 6 / 173 / 362).
- **Bank-copy batches**: rize 59 approved (earlier, by Codex), sudima **358 waiting** — unchanged.
- Server log from the stop's line: **0 ERROR/CRITICAL, 0 Traceback** (first scan by time counted
  continuation lines of the whole log — ledger note in S2M rows); one service process; sites 200 ×5.

### Read-only counts per live database (handover §2)

| Site | Gain the Filings lens (FG1) | Hold "Government reports" | "Add your tax number" reminder | HR-only "dependants do not match" note | HR-only "account in another person's name" notice |
|---|---|---|---|---|---|
| payobook (demo) | 2 of 3 payroll officers/managers | 188 | 16 of 37 logins (Vietnam) | **2,454 of 4,581** | 1 |
| payobook_template | 0 | 0 | 0 | 0 | 0 |
| p0clone | 0 | 0 | 0 | 0 of 12 | 0 |
| rize | **5 of 5** (nobody had the lens before) | 0 | 2 of 6 logins (India) | 20 of 229 | 2 |
| sudima | 0 | 0 | 0 of 1 | 0 | **234 of 651** |

Nobody lost the lens. Registered-dependants figure per scheme (running contracts): **rize** `VNREGISTER`
"Registered tax dependents" (61 contracts, read first; `NGUOIPHUTHUO` "Người phụ thuộc" carries the same
values, not read); **sudima** none (as S2-D expected — no note can show); **payobook demo** `NPT` on 4,513
contracts but **empty on 4,512** → every demo person with confirmed dependants gets the note (ledger
S2M-4; owner question 1). No system-parameter change made.

## 4. Checks on payobook.com

Browser (QA Test, uid 6672, own tab, nothing pressed that saves) and server shell as QA (rolled back):

| Screen | Result |
|---|---|
| Compliance › Filings | country chips Indonesia + Vietnam; Vietnam: **Tax returns** (05/KK TT89, TT80), **Year-end** (05/QTT TT89, TT80, "A certificate for each person"), the social-insurance tiles, **Form lines** door; Indonesia: Tax returns (BPMP), Year-end (BPA1), **Fund files** (BPJS TK, BPJS Kesehatan); each tile says "Pay items to choose on Form lines" |
| Form lines → Suggest | Vietnam 05/KK TT89: **26 proposals**, cancelled (nothing saved); Indonesia: "Nothing to suggest" (no Indonesian scheme in the demo company). "Check with your adviser before first filing" shown |
| Pay & deliver › Payroll Manufacturing July 2026 › Payment list | "40 people • total 784,652,817 VND • 6 need a check"; **Bank layout** chips General / India / Indonesia / Singapore; Indonesia chosen on screen only → "Not confirmed by the bank. Check with your bank before the first upload.", "0 people in the … file", "40 people · 784,652,817.00 VND to pay another way" with each person's reasons; set back to General list |
| Settings › Payroll › Bank layouts | 10 shipped, 3 "Not confirmed", the "Accounts in another person's name" setting (Leave out / Pay by file), the "check with your bank" note on the shipped general layouts |
| Employee form + side panel ("in another person's name", BL4 addition) | **Form** (Personal tab): notice + "Mark as seen" + help line. **Side panel** (People › Employees): amber chip in the header row "This bank account is in another person's name: … · Mark as seen". Not pressed on the live site. (Two demo people share that name — the panel only shows it on the one whose account it is.) |
| My Payobook | QA Test's login is not linked to an employee (plain portal, known). As a demo employee login in the shell: home has **Tax details** and **Tax certificates** under "Me", "Add your tax number" in "Needs you", the Tax details page data shows no unmasked number, Tax certificates empty. **Not seen in a browser as an employee** (no demo employee password used) |
| Existing bank file + payslip PDF | Vietnamese bank file builds (40 rows, 0 left out); payslip 144281 PDF 200, 152,447 bytes (same as before) |
| Console | clean (one pre-existing manifest-icon warning) |

Other four sites (shell as a site administrator, rolled back): Filings opens (rize/sudima: Tax returns +
Year-end; template/p0clone: US company, no forms), Bank layouts 10, My Payobook tiles under "Me";
rize Pay & deliver shows 3 layout choices; p0clone's pay-run screen refused that plain administrator
(standard access rule, not this deploy).

## 5. INFERRED — what is not confirmed (from the five reports)

| Form / layout | What is not confirmed | What would confirm it |
|---|---|---|
| ID monthly tax return (BPMP, S2-A) | Tax facility only "N/A"; Rate = each person's tax ÷ gross; withholding date = last day of period; object code 21-100-01; place-of-business number defaults to tax number + 000000; resident = has a 16-digit NIK | One BPMP file a customer imported into Coretax without errors; the adviser on the place-of-business number |
| ID year-end slip (BPA1, S2-B1) | FullYear / PartialYear rule; no "Annualized"; gross-up "No"; facility "N/A"; withholding date = last day paid; `K/I/n` statuses left out | A BPA1 file accepted by Coretax for one leaver and one full-year person |
| VN 05/KK-TNCN TT89 + TT80 (S2-A) | Line list from secondary guides (official pages 403); new TT89 wording reconstructed; [16] counts every resident; no official XML | One filed declaration from a customer or adviser |
| VN 05/QTT-TNCN + certificate (S2-B1) | Read from third-party copies of the signed texts; residents with a labour contract = every resident; Part II only from mapped items; certificate = information copy (YE2) | One filed year-end declaration |
| IN Form 16 B, 24Q (S2-B1) | From published copies (site 403); rows 13–17 only from mapped items; payment date = end of payslip period; challan columns left to the preparer | A return preparer checking one Form 16 and one 24Q annexure |
| IN Form 130 C, Form 138 (S2-B1) | Layout from the Gazette; that an employer-made Part C is more than a working copy (marked "Information copy", YE3); date/challan choices | The preparer's upload of one quarter through the department's utility |
| SG IR8A (S2-B1) | Software name empty; authorised person = preparer; dates from contracts; address only for SG postcodes; adviser note as `_note` in the JSON | One IR8A upload accepted on myTax Portal |
| ID BPJS TK (SIPP) + BPJS Kesehatan (e-Dabu) (S2-B2) | Every column and date format (templates behind login) | One sheet Rize finance already uploaded (names blanked) |
| IN EPF ECR + ESI (S2-B2) | Whole layouts from guides (EPFO blocked); rounding; ESI days rounded up | One ECR file and one ESI sheet the portal accepted |
| SG CPF EZPay (S2-B2) | Record layout confirmed; CR LF, "Month Paid", advice code 01, status from contracts, CPF as payslips carry it | One file CPF Board accepted |
| Bank layouts ID / IN / SG "general" (S2-C) | All three (no bank publishes its format); 9 ID + 12 IN bank codes from press lists; SG codes from a 2011 bank guide | The paying bank's own upload template, then "Confirmed with our bank" on the company's copy |
| VN dependants check (S2-D) | Figure found by component CODE (`VNREGISTER`, `DEPS`, `NPT`); "approved count" = dependants with status eligible | HR confirming each customer's code (§3 table) |

## 6. Held / left off

- Nothing held back.
- **Not done on purpose**: approving or refusing the sudima bank-copy batch; pressing "Mark as seen",
  saving a mapping, preparing a filing or a bank-layout file on any live site; changing the dependants
  code setting on payobook; any approval route.
- Left for later (from the reports, unchanged by the merge): S2-C import "IFSC/Bank code" column lane and
  the bank-document check for other countries; S2-B2 board quirk (company number lost after Suggest →
  Save); Compliance rail item for payroll officers; the proof link in the Approvals drawer (S2-D M2).
- The local "outputs" folder was not written: no list was gathered (counts only, all in §2–§3).

## 7. Questions for the owner (plain words)

1. **Payobook demo:** about 2,450 demo people will show HR a note "tax dependants do not match the
   contract", because the demo contracts leave the dependants number empty. Should we fill the demo
   contracts' dependants number, or tell Payobook to ignore that demo field?
2. **Rize:** Payobook's "Suggest" found nothing for the two BPJS sheets and missed the monthly tax item
   on Rize's Indonesian pay scheme. Should HR pick those pay items by hand, or should we teach Suggest
   Rize's item names first?
3. **Sudima:** 234 employee records now show HR "This bank account is in another person's name". Who at
   Sudima should go through them (pressing "Mark as seen" once each is checked)?
4. **Rize:** all 27 India staff have no PAN, provident-fund (UAN) or ESI number on file, so the India
   files leave everyone out. Will Rize HR type them in, or should the 2 India staff with a login be
   reminded to send their tax number first?
5. Still open from the builders: which bank Rize pays Indonesian staff from (to make its exact file);
   whether close-but-not-same account names should also be left out of bank files; payment date default
   (today or last day of the period); Singapore — does Rize use one CPF submission number or more.

## 8. New gotchas (ledger)
S2B2-1..6, S2C-1..8, S2D-1..9 (asked of S2-A, added now) and S2M-1 (two parallel tile groupings with one
label), S2M-2 (`--test-tags` runs post-install tests only for modules in `-u`), S2M-3 (pb_payai_actions
baseline 1 + 46 on the template copy), S2M-4 (empty contract dependants figure = 0 → demo notes). Also:
a time-window `awk` over the server log lets untimestamped continuation lines through — cut the log by
line number from the stop instead (counted 61 "tracebacks" that were all older).
