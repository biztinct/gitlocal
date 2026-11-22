# DOCSTUDIO phase A2 — employment contract documents — REPORT (PAUSED, partial)

Branch `docstudio-a2` (from `origin/19.1` + `origin/docstudio-f` merged, `f72bc4ec7`). New module
**`pb_doc_contracts`** 19.0.1.0.0. Builder and tester: Opus. Not deployed. **Paused on the
coordinator's request (usage limit)** — see "Where I stopped" at the end.

## 1. What is built

| Item | Built |
|---|---|
| 1 Kind | `selection_add` `employment_contract` on `pb.letter.template.letter_type` only; gallery group "Employment contracts" (key `employment`, `selection_add` on `pbds_kind` / `pbds_kind_set`, placed right after the studio's "Contract" group in `board()`); vault category `pb_employee_vault.cat_labor_contract`; "New document" in the group makes an employment contract. |
| 2 Fields | 22 "This document" fields (`contract_common.py`): reference, end date or "no end date", trial end, short dates (22/11/2026) for bilingual papers, working schedule, hours per week, job / department / place of work on the contract, pay currency, pay scheme, employer representative (+ title, from the page design's signatory, else the company), ID / passport number, home address, date of birth, nationality. Studio fields (start, end, type, monthly pay, own contract fields) follow the contract the document is made for (context `pbdc_contract_id`, `_pbds_contract` override). Not "filled in later": the designer shows real values. Conditions added: "Contract length" (fixed / open-ended), "Trial period end date". |
| 3 Wording | `data/contract_templates.xml` (noupdate, company-less): English original + COPIES for Vietnam (Vietnamese \| English) and Indonesia (Indonesian \| English), clause by clause in two-column tables; fixed-term / open-ended and trial paragraphs by rule; neutral, no statutory claims. Only words are stored: rules, page (no letter signature block — both parties sign in the wording) and main language (vi/id for the copies) are built-in defaults until the first studio save (`_pbdc_rules`, `_pbdc_page`, `_pbds_main_lang` override) — so install writes no studio data (the studio's own silent-install test stays green). Designer note "Starting wording. Have it checked against your local labour law before use." above the page, never printed (template inheritance of `pb_doc_studio.Designer`). Contract CSS for the two-column clauses added to the page frame by QWeb inheritance (`report/contract_frame.xml`). |
| 4 Hero | "Contract document" button in the panel's action area (inside "Next step" for writers, own "Paperwork" row for readers), OWL `patch` of `Contract360Drawer` + template inheritance. Sheet: real A4 preview of THIS contract (values ink in one after another), language picker (only languages the wording really exists in), document picker when a company has more than one, amber chips for missing values that jump to the field in the panel (or open the employee panel), folded "N paragraphs are left out" with reasons, starting-wording card, Download PDF (⌘P), Save to documents · vN (⌘S), Change the wording (designer, people allowed only), saved versions list. Esc closes. |
| 5 Saving | New `pb.employee.document` per save, `pbdc_contract_id` + `pbdc_version` (fields added by `_inherit`), name "Employment contract · v2 · 22 Nov 2026"; earlier versions kept; version number taken under a row lock on the contract. |
| 6 Server | `pb.contracts` (`_inherit`): `contract_document_available`, `contract_document`, `contract_document_pdf`, `contract_document_save`. Access = `_cd_require_read` + `_cd_contract` (as the caller). Pay: the panel's own mask (`_cd_unmask_wage`) AND field access as the caller; masked → plain refusal; the person's own contract → their own pay (F-b ruling 2). A letter made from the Letters list with this document prints the same rules and page (`pb.hr.letter` overrides). |

## 2. Tests so far

| # | Test | Result |
|---|---|---|
| 1 | Install silent, no other template written, no job/mail, labour category | PASS |
| 2 | VN / ID / third-country contract → right copy, read in vi / id / en | PASS |
| 3 | Fixed-term vs open-ended paragraph | PASS |
| 4 | Trial paragraph (and its "left out" reason + jump) | PASS |
| 5 | Bilingual table survives the report (test-mode HTML); real PDF screenshots | PASS (HTML); real PDF + glyph screenshot NOT YET |
| 6 | Every contract field has a value or an amber chip; real PDF prints nothing in their place | PASS |
| 7 | Pay rail: payroll manager figure; masked HR user plain refusal (preview, PDF, save); own contract own pay, colleague blocked | PASS |
| 8 | Save → v1, print again → v2, both kept, distinct files | PASS |
| 9 | Customer edits the VN copy → next print uses it; put back → built-in again | PASS |
| 10 | Company copy beats shipped country copy; other company keeps the shipped copy | PASS |
| 11 | Button only for contract readers; other company refused; all switched off → no button + sentence | PASS |
| 12 | Designer group, fields not "later", real preview values, conditions, new document in group | PASS |
| 13 | Made as a letter prints the same | PASS |
| 14 | Hostile text inert | PASS |
| 15 | Language picker | PASS |
| 16 | `pb_doc_studio` suite (43) | PASS, 0 failed (incl. F's silent-install and golden tests) |
| 17 | `pb_contracts` suite (79) | 1 failure = baseline: `TestCd1Contract360.test_01_payload_carries_every_top_level_key` expects no `components.fillin`, a key `pb_contracts` itself adds (`pb_contract_360.py:1098` on origin/19.1); not caused by this module (its payload is untouched — availability is a separate call) |
| 18 | PO gate + no platform name + window actions (4 gate tests) | PASS (93 entries vi / id) |
| 19 | Browser walk | PARTIAL — see below |

Own suite: 22/22 (run `suites3`, 2026-11-22 12:22).

Browser walk so far (local server, `a2.localhost:8492`, payroll-manager login, 1568 wide): Contracts board → Lan's panel → "Contract document" button shown in the Next step bar → sheet opened with the Vietnam copy, "Using the wording for Vietnam", Vietnamese long date, bilingual clauses, 1 amber chip "No pay scheme", 1 paragraph left out, starting-wording card, versions empty. Found and fixed in the walk (commit `bba73204d`, NOT yet re-walked): the sheet waited for the server behind the global loader (now slides in on blank paper first), key hints drew an empty box on the primary button, the fold line was centred.

## Where I stopped

- **Built and committed**: everything in §1 (commits `0c7797128`, `848166ec6`, `bba73204d`), pushed.
- **Tested**: tests 1–18 as above.
- **Left to do**:
  1. Re-walk after `bba73204d` (purge `/web/assets/%`, restart): sheet slides in first; Download PDF (real wkhtmltopdf PDF, screenshot Vietnamese glyphs + two-column table); Save → v1 → Save → v2 in the list; chip jump to a panel field and to the employee panel; language picker; HR masked login `walk.hr` (refusal card, buttons disabled); reader without write (Paperwork row); designer: gallery group, VN copy note banner, Change the wording from the sheet; Vietnamese UI; 1280 and 1440 wide; console clean.
  2. Lessons check: `pb_learn` anchors `cd-tabs` / `cd-body` and the contract-drawer replica (`pb_learn/static/src/engine/screens.js` ~590–670) do not draw the action area — expected "nothing affected"; confirm and say so.
  3. Finish this report: hero self-score, deploy notes (`-i pb_doc_contracts` on the five DBs; asset purge + restart; report frame inheritance), owner questions, left for later (e.g. pay in words, e-signature out of scope, a letter made from the Letters list uses the person's current contract, not a chosen one), gotcha rows (DS-A2-1: an AbstractModel recordset is always empty — `panel or self.Panel` in a test silently ran as the superuser; DS-A2-2: `pb_contracts` asserts the exact payload keys — add data by a separate call; DS-A2-3: shipping studio data on templates breaks the studio's silent-install test — ship words only, defaults in code).
- **Exact next step**: `bash scratchpad/a2/serve.sh` after the asset purge, sign in as `walk.pay` on `http://a2.localhost:8492/web/login` (session via `/web/session/authenticate`), open People › Contracts → DEMO Nguyễn Thị Lan → Contract document.
- **Local state left in place**: worktree `/Users/adity/Documents/GitHub/gitlocal-worktrees/docstudio-a2` (sparse); database **`docstudio_a2_t`** (seeded walk data: 3 DEMO contracts VN/ID/SG, logins `walk.pay`, `walk.hr`, throwaway password on the recovery login — this database only) and its filestore `~/odoo19/data/filestore/docstudio_a2_t`; scratch folder `scratchpad/a2/` (overlay addons, `odoo.conf`, `t.sh`, `serve.sh`, `run.py`, `seed_walk.py`, `make_po.py`). Walk server stopped. Drop the database and filestore when the phase is done.
- **Edits outside `pb_doc_contracts`**: none (this report only).
