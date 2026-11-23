# DOCSTUDIO phase A2 — employment contract documents per country — REPORT

Branch `docstudio-a2` (from `origin/19.1`, with `origin/docstudio-f` merged in: `f72bc4ec7`). New
module **`pb_doc_contracts`** 19.0.1.0.0 (depends `pb_doc_studio`, `pb_contracts`,
`pb_employee_vault`). Builder and tester: Opus. Not deployed. NO e-signature (owner).
Paused twice for the usage limit (once by the coordinator, once by a 429), then resumed and finished.

**Shipped "show only when" paragraphs and page work before anyone opens the designer.** The shipped
documents print with their built-in rules (fixed term or open-ended, trial period) and the contract
page (no letter signature block) from the moment the module is installed.

- Tests 2–4 and 13 run on the shipped documents exactly as installed.
- The browser walk ran on a database where all three documents had never been saved (`pbds_edited`
  empty, `pbds_rules` / `pbds_page` NULL in the database):
  - Lan's fixed-term contract printed the fixed-term and trial clauses and left out the open-ended one.
  - Tan's open-ended contract with no trial printed "has no end date" and left out the trial clause.

"Built-in until someone saves" only means where the settings are stored, not whether they apply:

- They are code defaults (`_pbdc_rules`, `_pbdc_page`, `_pbds_main_lang` on `pb.letter.template`)
  until the first save, which then stores them like any document's.
- Every way of printing reads them: the contract panel, a letter made from the Letters list, the
  designer's preview, and copies made with "Make a copy for…".
- Why they are not in the data file: if this module writes studio data at install, the studio's own
  silent-install test (`pb_doc_studio` test_01) fails. Kept in code, that suite stays at 43/43.

## 1. What was built

| Item | Built |
|---|---|
| 1 Kind | `selection_add` `employment_contract` on `pb.letter.template.letter_type` only (never on `pb.hr.letter`). Gallery group **"Employment contracts"** (key `employment`; `selection_add` on `pbds_kind` / `pbds_kind_set`; placed right after the studio's "Contract" group by a `board()` override; briefcase icon). Vault category `pb_employee_vault.cat_labor_contract`. "New document" in that group makes an employment contract with the contract page. |
| 2 Fields | 22 "This document" fields (`models/contract_common.py`).<br>- Contract: reference, end date or "no end date", trial period end, working schedule, hours per week, job / department on the contract, place of work, pay currency, pay scheme.<br>- Short dates in 22/11/2026 style (start, end, trial end, today, date of birth), so the two-language contracts carry one date that reads in both columns.<br>- Employer representative and title: from the page design's signatory, else the company and "Authorised signatory".<br>- Employee: ID number, passport number, home address, date of birth, nationality.<br><br>The studio's own fields (start, end, contract type, monthly pay, the customer's own fields) follow the contract the document is made for, through context `pbdc_contract_id` and an override of `_pbds_contract`. The designer shows real values for all of them.<br><br>New "Show only when" conditions: **Contract length** (fixed term / open-ended) and **Trial period end date**. |
| 3 Wording | `data/contract_templates.xml` (noupdate, company-less):<br>- an **English original**, used for every country of work;<br>- two **copies for a country of work**: Vietnam (Vietnamese \| English) and Indonesia (Indonesian \| English). They put the two languages side by side, clause by clause, in two-column tables.<br><br>Clauses: parties, position, term (fixed / open-ended by rule), trial period (only with a trial end date), working time, pay, leave, confidentiality, ending the contract, other terms, signatures of both parties.<br><br>The wording is neutral and structural: no notice periods, no severance amounts, no article numbers.<br><br>A designer-only note sits above every shipped contract until it is edited: "**Starting wording.** Have it checked against your local labour law before use. This note is not printed."<br><br>The contract page CSS reaches the PDF and the preview by QWeb inheritance of `page_frame`, and the designer's paper by SCSS. |
| 4 Hero | **"The finished contract, in one press."** A "Contract document" button in the panel's action area: inside "Next step" for people who may change the contract, in its own "Paperwork" row for people who may only read it. Built with an OWL `patch` and template inheritance.<br><br>The sheet slides in at once on blank A4 paper, then the contract for THIS contract is written onto it and the person's values ink in. It holds:<br>- a language switch, only for languages the wording exists in;<br>- a document switch, when there is more than one document;<br>- amber chips for missing values. Each jumps to the field in the panel and opens its editor, or opens the employee panel for employee fields;<br>- a folded list of left-out paragraphs, each with its reason;<br>- a starting-wording card;<br>- **Download PDF** (⌘P) and **Save to documents · vN** (⌘S);<br>- **Change the wording**, which opens the designer, for people allowed only;<br>- the saved versions.<br><br>Esc closes the sheet. If the panel has unsaved typed changes, it asks to save or discard them first. |
| 5 Saving | Each save adds a new document to the employee's documents (`pbdc_contract_id` + `pbdc_version` added by `_inherit`), named like "Employment contract · v2 · 22 Nov 2026". Earlier versions are kept. The version number is taken under a row lock. |
| 6 Server | Four methods added to `pb.contracts`: `contract_document_available`, `contract_document`, `contract_document_pdf`, `contract_document_save`.<br><br>Access is the panel's own gate, read as the caller.<br><br>Pay:<br>- the panel's own mask applies, and the wage must also be readable as the caller;<br>- someone who is masked gets a plain refusal, and the PDF and save are refused;<br>- on their own contract a person sees their own pay.<br><br>The studio pipeline is reused (copy rule, language order, rules / fields / escaping, page frame / report). Nothing is stored for a preview or a download. |

## 2. Tests

| # | Test | Result | Evidence |
|---|---|---|---|
| 1 | Install silent; no other template written; no job / mail; labour category | PASS | `test_01` |
| 2 | VN / ID / third-country contract → right copy, read in vi / id / en | PASS | `test_02`; walk w01, w11, w03 |
| 3 | Fixed-term vs open-ended paragraph | PASS | `test_03`; walk on never-saved documents |
| 4 | Trial paragraph only with a trial end date | PASS | `test_04`; walk |
| 5 | Two-column table survives the REAL PDF; Vietnamese letters | PASS | `test_05` + real wkhtmltopdf 0.12.6 PDFs: `evidence_a2/pdf_vn_page1.png`, `pdf_vn_page2_signatures.png`, `pdf_vn_glyphs_150dpi.png`. All Vietnamese letters and tone marks are correct; A4, 2 pages, no row split. Fixed during this check (`bf0145c5f`): the company layout boxed the clause tables, and the signing lines were missing. |
| 6 | Every field has a value or an amber chip; the PDF prints nothing in their place | PASS | `test_06`; walk w03 |
| 7 | Pay rail, three users | PASS | `test_07`; walk w06 (Vietnamese, masked) |
| 8 | Save → v1, again → v2, both kept | PASS | `test_08`; walk w02 |
| 9 | Customer edits the VN copy → next print uses it; put back → built-in again | PASS | `test_09` |
| 10 | Customer copy for their company beats the shipped country copy | PASS | `test_10` |
| 11 | No button without read access; other company refused; all switched off → sentence | PASS | `test_11` |
| 12 | Designer: group, fields, real preview values, conditions, new document | PASS | `test_12`; walk w09, w10 |
| 13 | Made from the Letters list prints the same rules and page | PASS | `test_13` |
| 14 | Hostile text inert | PASS | `test_14` |
| 15 | Language picker | PASS | `test_15` |
| 16 | `pb_doc_studio` suite | PASS 43/43 | = F-b result |
| 17 | `pb_contracts` suite | 78/79 = baseline | `TestCd1Contract360.test_01_payload_carries_every_top_level_key` fails because `pb_contracts` itself adds `components.fillin` (`pb_contract_360.py:1098` on origin/19.1); this module adds nothing to the panel's data |
| 18 | PO + static gates | PASS | vi_VN / id_ID 94 entries each; no platform name |
| 19 | Lessons check | PASS, nothing to update | `pb_learn` anchors are `cd-tabs`, `cd-body`, `cd-save`; the replica never draws the "Next step" area; no lesson text mentions it |
| 20 | Browser walk | PASS | below |

Own suite after the last change: 22/22 (18 numbered tests + 4 gate tests).

**Browser walk:** local server, real PDF engine; screens 1568, 1280 and 1440 wide. Three logins: a payroll manager, an HR user with the wage masked (Vietnamese screens), and a read-only contract reader.

- **Fixes from before the pause, checked on screen:** the sheet slides in on blank paper, the key hints are readable, and the "paragraphs left out" line is left-aligned.
- **Saving:** v1 and v2 saved and both listed.
- **Chip "No pay scheme":** opens the Salary structure editor.
  - A change there needs approval, so the chip stays until approval (correct).
  - The same walk found the sheet could open over unsaved panel changes; fixed in `fbe09fdca`.
- **Chip "No ID number":** opens the employee panel.
- **Masked user:** gets the refusal card; both buttons are off.
- **Screen widths:** nothing clipped at 1280 or 1440.
- **Change the wording:** opens the designer on the Indonesian copy, with its note; the gallery shows "Employment contracts 3".
- **Read-only reader:** gets the "Paperwork" row.
- **Console:** clean for every flow done by clicks. One "Error: Na" came from the browser tool's own injected script (stack "eval at xhr.onreadystatechange") and did not come back after a reload.

## 3. Rails

- No edit to `pb_contracts`, `pb_doc_studio`, `pb_employee_vault`, `pb_lifecycle`, `pb_pack_*`.
- Silent install.
- Pay is never read as sudo "to be safe" (DS-3/8/16).
- Hostile text is escaped and the preview is sandboxed.
- No platform name anywhere.
- vi_VN and id_ID translations for every string.

## 4. Edits outside `pb_doc_contracts`

None (this report and `docs/handovers/docstudio/evidence_a2/` only).

## 5. Deploy notes (new module = risky tier)

- Run `-i pb_doc_contracts` on the five databases after `pb_doc_studio` is live.
- The install creates:
  - 3 noupdate templates;
  - 2 empty fields on `pb.employee.document`;
  - new selection values;
  - 1 inherited QWeb view on `page_frame`.
- There is no job, no mail and no access row.
- Asset bundles change: purge `/web/assets/%` on each database and restart.
- The VN / ID copies read in vi_VN / id_ID only where that language is active.
- Real PDFs need the PDF engine to load the report CSS (`report.url` / `web.base.url`), like any report.

## 6. Design self-score ("extreme WOW, intuitive, out-of-this-world experience, best in class")

| Bar | Score | Why |
|---|---|---|
| Hero moment | 9/10 | One press → the real contract on A4, values ink in, the right country's two-language wording; true PDF and filed versions from the same sheet. The first drawing on a busy server takes seconds. |
| Zero dead ends | 9/10 | Chips land on the field or the person; left-out paragraphs explain why; every refusal says why and what next. |
| Paper quality | 8/10 | Two columns that never split a row, signing lines, letterhead. Cosmetic: the space after a bold label renders narrow in the English column (old WebKit). |
| Keyboard | 8/10 | ⌘P, ⌘S, Esc; chips and buttons focusable. |
| Palette / quiet board | 9/10 | Locked indigo, amber only for missing, rose only for pay refusal, Lucide, no gradients. |
| Overall | 8.6/10 | |

## 7. Owner questions (plain words)

1. **Should a lawyer check the shipped contract wording before customers use it?** It makes no legal
   claims, and every customer sees "Starting wording — have it checked against your local labour law"
   until they edit it. Enough, or lawyer-reviewed Vietnamese and Indonesian versions before go-live?
2. **Who may file the contract in the employee's documents?** Today HR and payroll roles. Someone who
   may only view the contract can download the PDF but not file it. Keep that?

## 8. Left for later

- Pay in words (out of scope).
- E-signature (owner: out of scope).
- A contract made from the Letters list uses the person's current contract, not a chosen one.
- Version names stay in the saver's language.
- The narrow-space quirk in the PDF (cosmetic).

## 9. New gotcha rows (for the ledger)

- DS-A2-1 | An AbstractModel recordset is always empty: `panel or self.Panel` in a test ran as the superuser | `self.Panel if panel is None else panel`.
- DS-A2-2 | `pb_contracts` asserts the exact keys of its panel data | separate RPC; never add keys to `get_contract_360`.
- DS-A2-3 | Shipping studio data on a template breaks the studio's silent-install test | ship words only; built-in rules / page are code defaults applied while unedited, so they print from day one.
- DS-A2-4 | Local real PDFs come out unstyled because a template database's `web.base.url` points at the live host | set `report.url` to the local server in the throwaway database only.
- DS-A2-5 | The company report layout draws borders on every PDF table | use `!important` in page-frame CSS for tables with their own look.
- DS-A2-6 | Heavily loaded Mac (load ~200): asset bundles take 20–60 s, browser screenshots time out | wait in a bounded loop for a known element.

## Where I stopped

Finished. Local database `docstudio_a2_t` and its filestore dropped. The sparse worktree
`/Users/adity/Documents/GitHub/gitlocal-worktrees/docstudio-a2` is left for the merge agent.
