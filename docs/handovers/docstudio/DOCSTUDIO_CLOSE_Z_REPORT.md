# DOCSTUDIO close-out wave — Stream Z report (five leftover fixes)

Branch `docstudio-close-z`, cut from `origin/19.1` at `95ba36ccf` (2026-11-26). Builder only:
nothing deployed, the live server not touched. Local test database `docstudio_cz_t` (copy of
`upd_p6_t_tpl`, `-u all` + the studio modules), dropped with its file folder at the end.

| # | Item | Outcome | Module + version |
|---|---|---|---|
| 1 | "Every month" / "One-off" in built-in offer letters | FIXED (Indonesian AND Vietnamese were missing) | `pb_hiring` 19.0.2.23.8 → **19.0.2.23.9** |
| 2 | Three Insights PDFs "template not found" | NOT BUILT — dead legacy buttons; owner decides hide vs repair (§2) | none |
| 3 | Offer-letter names English on Vietnamese screens; designer name box English | FIXED | `pb_doc_studio_hiring` → **19.0.1.2.0**, `pb_doc_studio` → **19.0.1.5.0** |
| 4 | Contract preview language in the designer | FIXED | `pb_doc_studio` **19.0.1.5.0** (hook + screen), `pb_doc_contracts` → **19.0.1.2.0** |
| 5 | Reopen "Friendly" / "Modern" for report PDFs | NOT REOPENED — the proof is not there (§5) | none |

Commits: `07c0c75f5` (Z1), `cc2eb72ad` (Z3), `2136c73c4` (Z4), this report. No new screen; no
pay logic; no data written by an upgrade; no "Odoo" in any new string.

## 1. "Every month" / "One-off" in built-in offer letters — FIXED

- **Cause.** An offer letter nobody edited prints through Hiring's own `${lines}`
  (`pb.hiring.offer._lines_table`). It took the "how often" word straight from the plain list
  `OFFER_PERIODS` in `pb_hiring/models/hiring_common.py` — a Python string never passed through
  translation. So the words were English in **every** language, Vietnamese included (the
  Vietnamese words already sat in `pb_hiring/i18n/vi_VN.po`, unused); Indonesian had no words at all.
- **Change (smallest, strings only).** `pb_hiring/models/offer.py` `_lines_table`: the word is read
  through `self.env._(…)` (Hiring's own code translations, the letter's language = the env language
  Hiring already renders in). `pb_hiring/i18n/id_ID.po`: three entries "Setiap bulan / Setahun sekali /
  Sekali saja" (the same words the studio bridge already uses), with the `#. odoo-python` marker and
  the `code:` occurrence. English output byte-identical (en_US never translates). The candidate's
  web offer page (`page_facts`) has the same English words — NOT touched (outside "the pay table of
  the letter"); a one-line follow-up if wanted.
- **Test CZ-1** (`pb_doc_studio_hiring`, `test_cz_01_…`): `_lines_table` in en / vi / id carries
  Every month·One-off / Hằng tháng·Một lần / Setiap bulan·Sekali saja; a real untouched letter written
  with letter language Indonesian has "Setiap bulan" and "Sekali saja" and no "Every month"; with no
  choice on an English screen it is the English table as before. PASS.
- **Module:** `pb_hiring` 19.0.2.23.9.

## 2. Three Insights PDFs "template not found" — NOT BUILT (owner decides)

- **Cause (verified locally).** `pb_hr_payroll_analytics/reports/hr_analytics_reports.xml` defines
  three PDF reports — "Personnel Costs Report", "Statutory Contributions Report", "Headcount
  Analysis Report" — pointing at page designs `pb_hr_payroll_analytics.report_personnel_costs`,
  `…report_statutory_contrib`, `…report_headcount`. **Those page designs do not exist and never did:**
  `git log -S` over the whole history finds no commit that ever had them. Rendering each one gives
  `MissingError: Template not found: 'pb_hr_payroll_analytics.report_…'`. Not a wrong id, not a
  missing file in a manifest — so not a small local fix. These are dead legacy buttons.
- **Where a person can meet them:**
  1. The **Print menu** of the three old analytics record screens (personnel costs, statutory
     contributions, headcount). Those screens have had **no menu** since the Sudima Phase M retired
     the analytics menu tree (`views/hr_analytics_menus.xml`); they are reached only from the old
     "HR Analytics Dashboard" or a typed link.
  2. The old **HR Analytics Dashboard** › **Export** button › export window, whose file format
     defaults to "PDF Report" for these three report kinds → the same error.
     The dashboard itself is reached only from legacy screens: the old country payroll dashboards
     (Indonesia, India: "action_open_analytics_dashboard" buttons, legacy per-country modules) and
     the old HR flow board's analytics badge (that badge opens "Salary Structure Analytics", not
     these three). The Insights board does NOT link to them (its report gallery was retired in Phase O).
  3. `static/src/js/hr_analytics_export.js` also names them but is switched off in the manifest
     (old JavaScript style) — not reachable.
- **Proposal for the owner (plain words):**
  - **Hide (recommended, small):** take the three off the Print menu and drop "PDF" from that Export
    window for these three kinds (one data file + one selection in `pb_hr_payroll_analytics`;
    vi/id strings unchanged). Nobody loses anything that ever worked. The same figures can already be
    printed as a designed PDF through Insights › Build a report and the Explorer (report PDF designer).
  - **Repair:** design three new PDF pages (a new piece of work, roughly a day with tests and
    translations), for screens that have no menu today.
- Nothing changed for this item.

## 3. Offer-letter names and the designer's name box — FIXED

- **Cause.** (a) The two shipped offer letters (`pb_hiring.letter_template_offer_generic`,
  `…_offer_vietnam`) had no Vietnamese/Indonesian names anywhere. (b) The designer's `open()` and
  its save answer returned the name read in English (`MAIN_LANG`) while the gallery card reads the
  screen's language — so the contract card said "Hợp đồng lao động — Việt Nam" and the name box
  "Employment contract — Vietnam".
- **Change.**
  - `pb_doc_studio_hiring` i18n (vi, id, pot): name translations of the two Hiring records as
    `#: model:pb.letter.template,name:pb_hiring.letter_template_offer_…` entries in the **bridge's**
    PO (the loader takes the module from the occurrence, so pb_hiring needs no edit): "Thư mời làm
    việc" / "Thư mời làm việc — Việt Nam", "Surat penawaran" / "Surat penawaran — Vietnam" (same words
    the bridge already used for "Offer letter").
  - `pb_doc_studio/models/doc_studio.py`: `open()` and `_pbds_saved()` give `tmpl.name` in the screen
    language. `save()`: the box untouched → **no name write** (so saving on a Vietnamese screen never
    copies the Vietnamese name over the English one); a new name → written in the screen's language
    when the document has a name of its own there (a shipped translation), else into the main name as
    before (a customer's own document keeps one name for everyone, as today). "Put back the built-in
    wording" still restores every language (raw snapshot).
- **Tests.** CZ-3 in `pb_doc_studio` (`test_cz_03_name_box_follows_the_screen_language`: open + card
  agree; untouched save writes nothing; rename on vi touches vi only; rename on en touches en only;
  rename on id with no id name renames the main name; reset restores both) and in
  `pb_doc_studio_hiring` (`test_cz_03_offer_letter_names_follow_the_screen_language`: en/vi/id names on
  the record, `open()` and the card; untouched vi save keeps both names). The guard in that test that
  reloads translations did not trigger here: the names were loaded by the module upgrade itself
  (checked in the database: `{"en_US": "Offer letter — Vietnam", "vi_VN": "Thư mời làm việc — Việt
  Nam", "id_ID": "Surat penawaran — Vietnam"}`).
- **Browser (local copy, Chrome MCP, screen in Tiếng Việt):** gallery cards "Thư mời làm việc",
  "Thư mời làm việc — Việt Nam"; name box of the Vietnam contract "Hợp đồng lao động — Việt Nam" and
  of the Vietnam offer letter "Thư mời làm việc — Việt Nam". Console: 0 errors, 0 warnings. Nothing saved.
- **Seen, not in scope:** the older letters of the lifecycle module ("Probation passed", "Contract
  extended", "Incentive letter", "Experience letter", "Growth plan" …) still show English names on a
  Vietnamese screen — they ship no name translations either. Same fix pattern if wanted (that module
  is another programme's lane). "Make a copy for…" names the copy from the English name + place.
- **Modules:** `pb_doc_studio_hiring` 19.0.1.2.0, `pb_doc_studio` 19.0.1.5.0.

## 4. Contract preview language in the designer — FIXED

- **Cause.** The designer set the preview language to the person's own language (`person.lang`, from
  `_pbds_default_lang(None, emp)`) for every document. The contract panel instead picks among the
  languages the wording really exists in (`pb.contracts._pbdc_pick_lang`: the person's if the wording
  exists in it, else their company's, else the main wording's). Vietnamese person whose own language is
  English + Vietnam copy (main wording Vietnamese) → designer "English (US) (their language)" + "No
  wording in this language yet: …", panel Vietnamese.
- **Change.**
  - `pb_doc_studio` JS (`doc_studio.js`): `previewPicked` — false when a document opens or a person is
    chosen; true when somebody picks a preview language, switches the wording tab, starts a language
    wording or changes the main wording's language. While false, `preview` / `sample_pdf` are called
    with context `pbds_preview_auto` (same arguments, so the offer-letter override in the hiring bridge
    is untouched).
  - `pb_doc_studio` Python: hook `_pbds_preview_lang(tmpl, employee, draft, lang)` (default: returns
    `lang` — letters, certificates and offers unchanged), called only under that context.
  - `pb_doc_contracts/models/doc_studio.py`: for a contract, the panel's own rule
    (`_pbdc_pick_lang(tmpl, employee, False, langs)`) over the saved languages plus the draft's (its
    main language, a wording started but not saved, a wording removed in the draft). The answer's
    `lang` is the picked one, so the screen's select shows it.
- **Test CZ-4** (`pb_doc_contracts`, `test_cz_04_…`): panel and designer both Vietnamese for the case
  above, read language Vietnamese; English picked by hand stays English (read in Vietnamese, as
  before); an unsaved English wording in the draft makes English the pick; generic contract for a
  Vietnamese reader = the panel's pick; a letter under the flag unchanged; sample PDF ok. PASS.
- **Browser (local, Vietnamese screen):** Vietnam contract with "Administrator" (English, company in
  the US) and with "DEMO CZ Walk Person" (English, Vietnam contract): select shows "Vietnamese / Tiếng
  Việt", no "No wording in this language yet" line. Picking "English (US) (ngôn ngữ của họ)" by hand:
  stays English, with the honest line "Chưa có nội dung bằng ngôn ngữ này: thư sẽ in nội dung chính,
  bằng Tiếng Việt.". Console clean. Small look note: on first open the select shows the person's
  language for the instant before the first preview answers, then turns to Vietnamese.
- No new or changed visible string (no vi/id work for this item).
- **Modules:** `pb_doc_studio` 19.0.1.5.0 (with JS), `pb_doc_contracts` 19.0.1.2.0.

## 5. "Friendly" and "Modern" for report PDFs — NOT REOPENED

The handover's test: reopen only if the PDFFIX report shows they print real text with correct spacing
at report sizes. It does not show that:
1. PDFFIX printed Friendly/Modern only in **letters** (short documents). Report PDFs were proven in
   DejaVu only; the long report (171 pages) was never printed in a web font on the new engine. The
   reason report PDFs dropped web fonts (ledger DS-B8: the text of the first pages of a long document
   is not drawn in any web font; every weight drawn with one face) was found on the old engine and has
   **not been re-tested** on the new one.
2. The space-before-bold cure (§11 of PDFFIX: `white-space: pre-wrap` + `doc_common.pdf_body`
   normalising) is measured on letter bodies (112 letter PDFs, a 4-font × 6-size test sheet). Report
   tables are not run through `pdf_body`, and report text sizes/table cells (bold headers, group
   rows) were not part of the measurement.
3. No fonts installed on the server (owner ruling) — so these would be web fonts, exactly the DS-B8 case.

So report PDFs keep two fonts ("Clean" = DejaVu Sans, "Classic serif" = DejaVu Serif); looks that hold
Friendly/Modern keep printing as Clean. To reopen later, the deploy agent (or a later phase) needs this
proof on the server: one long built report (≥ 4,000 cells, e.g. the 4,581-row one) and one 1-page
report, each in Friendly and Modern with the patched engine; page 1, a middle page and the last page
show every word (text layer present, `pdftotext` finds the first row), bold header row distinct from
body, and no squashed space before bold group headings. Only then change `PDF_FONTS` in
`pb_report_pdf/models/layout.py` (one line + its test). No code changed for this item.

## 6. Suites vs baseline (local, one database, Mac otherwise loaded by other builders)

Run 1 — `-u pb_hiring,pb_doc_studio,pb_doc_studio_hiring,pb_doc_contracts`, tags = the six studio
modules: **104 tests, 0 failed, 0 errors**.

| Suite | Recorded (W2 / PDFFIX-2) | Now | Failures |
|---|---|---|---|
| pb_doc_studio | 43 | 44 (+CZ-3) | 0 |
| pb_doc_studio_hiring | 22 | 24 (+CZ-1, +CZ-3) | 0 |
| pb_doc_contracts | 23 | 24 (+CZ-4) | 0 |
| pb_doc_studio_me | 14 | 14 | 0 |
| pb_report_pdf | 21 | 21 | 0 (`test_03` skipped: no PDF engine on this Mac, as before) |
| pb_report_pdf_send | 5 | 5 | 0 |

Run 2 — `-u pb_hiring`, tag `/pb_hiring`, alone (HTTP tests): **690 tests, 8 failed + 2 errors = exactly
the recorded baseline** (A1 report §2.1 / W2 deploy §2): TestClientReview.test_hiring_only_cannot_read_
access_directory, TestRecruitInterviewsP5.test_07b, TestRecruitJoining.test_11, TestTheCover.test_t7,
TestRecruitPrivacy.test_02 / test_02b (error) / test_08 (error), TestRecruitPrivacyFiles.test_02,
TestRegistersP9.test_08, TestRecruitStages.test_13. None touches the offer letter's pay table.

Static gates: PO parse (polib) of every changed PO — no duplicates, every entry translated; `msgfmt -c`
only the old header warnings. No "Odoo" in any new string. Upgrade log: 0 ERROR lines (missing picture
files of the template copy only — ledger S6A-7).

## 7. For the deploy agent (Stream D)

- **Upgrade:** `pb_hiring`, `pb_doc_studio`, `pb_doc_studio_hiring`, `pb_doc_contracts` on all five
  databases (normal tier: no data rewrite, no pay change; `-u pb_hiring` cascades its dependents as
  usual). Versions: pb_hiring 19.0.2.23.9, pb_doc_studio 19.0.1.5.0, pb_doc_studio_hiring 19.0.1.2.0,
  pb_doc_contracts 19.0.1.2.0. **JS changed** (`pb_doc_studio/static/src/js/doc_studio.js`): purge
  `/web/assets/%` per database. Check other branches for pb_hiring / pb_doc_studio version bumps at
  merge (NEWHIRE also works near Hiring).
- **A1 golden:** offer letters rendered in **Vietnamese or Indonesian** now differ by design (the pay
  table words); English renders must stay identical. Existing stored offer letters are not re-written.
- **Checks needing a real PDF (no engine on this Mac):**
  1. *Indonesian pay words on paper.* payobook, server shell, rolled back: take a demo offer with
     lines (monthly + one-off), untouched generic letter, `offer.sudo().pbds_letter_lang = 'id_ID'`,
     `offer.action_prepare_letter()`, open `offer.attachment_id` PDF → pay table reads "Setiap bulan" /
     "Sekali saja"; repeat with `'vi_VN'` → "Hằng tháng" / "Một lần"; `cr.rollback()`. (Or on screen:
     Hiring › a demo role › Offer & joining › Offer › Language: Bahasa Indonesia › Write the letter —
     this rewrites that demo offer's letter, so only on a demo offer still being prepared.)
  2. *Contract sample PDF language.* payobook.com as the QA login, screen in Tiếng Việt: Settings › HR
     › Documents › "Hợp đồng lao động — Việt Nam" › Preview with a person whose language is English and
     who works in Vietnam → select shows Tiếng Việt → "Tải PDF mẫu" → Vietnamese wording, no
     "No wording…" line. Nothing saved.
  3. *Names:* same screen — gallery cards and the name box of both offer letters and the Vietnam
     contract in Vietnamese; switch to Bahasa Indonesia: "Surat penawaran", "Surat penawaran — Vietnam".
     Do not press Save (if pressed with the name untouched, nothing changes — tested).
  4. Lessons: no anchor or lesson text uses the changed elements (checked `pb_learn` content); Stream L
     owns the new studio lessons.

## 8. Owner questions (plain)

1. Three old PDF buttons (personnel costs, statutory contributions, headcount) have never worked —
   their page designs were never made. They sit on old analytics pages that have had no menu since the
   Insights board replaced them. **Hide them** (small change, nothing that ever worked is lost; the same
   numbers print as PDF from Insights › Build a report), or **have them designed** (about a day of work)?
2. Report PDFs stay with two fonts ("Clean", "Classic serif") until a long report has been printed and
   checked in "Friendly" and "Modern" on the server. Fine to leave as is?

## 9. Left for later

- Candidate's web offer page still shows "Every month" / "One-off" in English (same one-line fix).
- Names of the older lifecycle letters untranslated on Vietnamese/Indonesian screens.
- A copy made with "Make a copy for…" is named from the English name only.
- Item 2 (owner decision) and item 5 (server proof) as above.

## 10. Gotcha rows (for the ledger)

- DS-CZ-1 | A Python list of `(key, 'Label')` tuples used for display is never translated — not even
  when a PO entry for the label exists (it was exported as a code term but nothing calls `_()` on it) |
  read the label through `self.env._(label)` at the point of use, or the field's
  `_description_selection(env)`.
- DS-CZ-2 | A bridge module can ship translations of ANOTHER module's records (`#: model:<model>,<field>:
  <other_module>.<xmlid>` in its own PO): the loader takes the module from the occurrence | an
  `i18n export` of the bridge does not regenerate those lines — re-add them by hand after an export.
- DS-CZ-3 | On the local template copy the only active admin (recovery login) has no HR rights: the
  document designer says "no one to preview" | on the throwaway copy add HR manager to that login and
  restart the local server (rights are cached).
