# DOCSTUDIO phase F — Document studio foundation — REPORT

Branch `docstudio-f` (from `origin/19.1` 4eaee9db3). New module **`pb_doc_studio`** 19.0.1.0.0.
Builder and tester: Opus. Not deployed. Local database `docstudio_f_t` (copy of
`upd_p6_t_tpl`, every module upgraded to 19.1, plus pb_job_change, pb_me_letters,
pb_pay_scales, pb_form_studio, pb_form_studio_people, pb_employee_form_tidy) — dropped at the end.

## 1. What was built (F1–F8)

| Item | Built |
|---|---|
| F1 Home | Settings card **Documents** (HR group of the Settings rail, registry `pb_settings_category`, key `documents`, gated to `pb_lifecycle.group_lifecycle_admin` + `base.group_system`) and a ⌘K row (`pb_hub_palette`, "Documents · Letter wording and design"). Client action `pb_doc_studio.action_pb_doc_studio` (tag `pb_doc_studio`). Gallery grouped Joining / Trial period / Contract / Pay / Job changes / Leaving / Certificates / Other; each card: paper thumbnail with the first lines, name, "Your wording"/"Built-in wording" pill, "Switched off" pill, who it is for (company · countries, else "Everyone"), language codes, "Changed by X, 3 days ago", amber "1 field no longer exists", dashed border + "Copy" badge for copies. Kebab: Open, Make a copy for…, Switch off/on, Put back the built-in wording. Search (`/`), kind chips with counts (grey at zero), coach line "Pick a letter to make it yours.", empty, no-match, loading skeleton and error states. New document dialog (name + group tiles). Offer letters are NOT listed (they do not go through the letter engine; wave 2 A1). |
| F2 Designer | Three panes. Left: fields, searchable, grouped Employee / Job / Contract / Company / Dates / This document / Your own fields; each row shows the current preview person's real value; click inserts at the cursor, drag drops at the drop point; pay fields carry a lock. Centre: language tabs, toolbar (undo/redo, Text/Heading/Small heading, B/I/U, bullets, numbers, 4 alignments, table + table tools, picture + S/M/L/Full, Field `/`, Show only when…), and an A4 sheet (true 794×1123 px, zoomed to fit) with letterhead, date, editable heading, the body, signature block and "Page 2" break guides. `DocEditor` is a standalone reusable OWL component (`pb_doc_studio/static/src/js/doc_editor.js`): hand-built contenteditable, non-editable chip spans, own undo history, paste cleaning, pasted pictures uploaded as files, `/` picker, ⌘B/I/U, ⌘Z/⇧⌘Z, Tab in tables. Stored body = inert `${key}` text; nothing imported from pb_formula_studio. |
| F3 Show only when | Select paragraphs → "Show only when…" wraps them in `<div class="pbds-when pbds-r-rN">`; rule builder: field, is / is not / is one of / is empty / is filled in, plus more/less than (numbers) and after/before (dates), all-of / any-of, live sentence. On the page: quiet indigo bracket + pill "Only when Country of work is Indonesia" (amber dashed until a condition is chosen); click the pill to edit or "Show it for everyone" (unwrap). Cancel on a new rule unwraps. |
| F4 Preview (hero) | Real person (search, people the user may read, no sudo), language picker defaulting to their language ("Tiếng Việt (their language)"), page redrawn by the server ~400 ms after each keystroke from the UNSAVED draft, shown in a sandboxed frame (`sandbox="allow-same-origin"`, no scripts, CSP `default-src 'none'`). "2 paragraphs are hidden for this person" + "Show them faded" switch. Empty values = amber chip "No manager on this person"; caller-given fields = indigo chip "New pay — filled in when the letter is made"; pay the user may not see = "You may not see pay"; removed field = "A field that no longer exists". Values that change when you switch person glow for a moment. "Download a sample PDF" = the true PDF from the same report (no letter, nothing filed). "Open large" overlay. |
| F5 Languages | One wording per active language: main wording = the template's own `body_html` (en_US source); other languages = `pb.doc.version` (whole wording, `translate=False, sanitize=True`). Tabs show which languages have wording; empty tab offers "Copy from English", "Start from the translation" (when the product ships a translation, e.g. certificates) or blank; "Remove this language". A letter's language (`pb.hr.letter.lang`, set at create) = the person's language when active, else the company's, else the user's; certificates keep the language their caller chose. Dates `${today_long}` etc. are written in the letter's language. |
| F6 Page | Page tab: Letterhead switch, Margins Normal/Narrow/Wide (three paper formats + three report actions sharing one template), Font Clean (Roboto) / Friendly (Open Sans) / Classic serif (DejaVu Serif) / Modern (Montserrat) — all with Vietnamese letters, Text size 10–14, Signature block off / name and title / with a signature picture (+ "Signed by", "Their title", picture upload PNG/JPEG ≤ 2 MB). Saved per document in `pbds_page`. |
| F7 Copies | "Make a copy for…" (company and/or countries of work, live sentence "Letters for people at X who work in Y will use this copy."). `pb.hr.letter.create` swaps the template for the most specific ACTIVE copy of its root: company+country > company > country > the original (ties: sequence, id), one search per create batch, for every caller (fixed xml id, type-only search, journey steps). A copy handed to somebody it is not for falls back to the original. The same copy twice opens the existing one. |
| F8 Own fields | Form builder fields of the employee and the contract (`pb.form.studio.fields_for(model,'all')`, probed, no dependency) appear under "Your own fields", print through `_pbfs_values_for`, and can be used in rules (selection/boolean/char/date/many2one/number). |

## 2. Test table (handover §6)

| # | Test | Result | Evidence |
|---|---|---|---|
| 1 | Install on the live module set: no errors, no template changed | PASS | `-i pb_doc_studio` exit 0, no ERROR. md5 of name/subject/body jsonb of all 13 templates identical before/after (golden script). `test_01_install_is_silent`. |
| 2 | R1 golden: untouched templates byte-identical | PASS | 9 shipped templates rendered before/after install: identical md5 (§3). `test_02_…` (4 templates against the engine's own formula). |
| 3 | Edit wording → prepared letter shows it | PASS | `test_03_edited_wording_prints` (rendered + PDF + filed in the vault). Browser: saved wording; real PDFs made with the real PDF engine for 3 people. |
| 4 | Every new field; empty prints nothing; amber chip | PASS | `test_04_every_generic_field` (13 keys; "No manager on this person"). Browser: the field list shows each value for the chosen person. |
| 5 | "Country of work is Indonesia" shown/absent; unknown rule keeps text | PASS | `test_05_…` + `test_05b`. Browser: rule made on screen; Vietnamese person "1 paragraph is hidden", Indonesian person sees it; real PDFs `evidence_f/t05_*`, `t09_*`. |
| 6 | Every operator × type | PASS | `test_rules.py` (47 cases, every operator/type pair asserted covered, refused lines, no evaluation). |
| 7 | Language versions + long dates | PASS | `test_07_language_versions` (vi wording + "tháng" date + vi heading; id person without a version → main wording). Browser: Vietnamese tab "Copy from English", preview "22 tháng 11, 2026"; real PDF for the Vietnamese person in Vietnamese. |
| 8 | Company/country copies for every caller | PASS | `test_08_…`: fixed-xmlid caller, type-only caller (`pb.pay.apply._letter_template('pay_review')`), company+country beats company, company beats country-only, misfit copy → original, duplicate refused, switched-off copy ignored; `test_08b` one search per batch. Browser: copy for Indonesia made and opened ("For Indonesia"). Interpretation: "country variant beats company-only" read as "company + country beats company only", per the ranking in handover §3. |
| 9 | Narrow + no letterhead + signature image | PASS | `test_09_page_design` (narrow action/paper 12 mm, serif, 12 px, signer, picture inline, no company layout; letterhead on → company header). Real PDF (local wkhtmltopdf 0.12.6, A4 595×842 pt): `evidence_f/t09_pdf_vietnamese_narrow_no_letterhead_signature.png` — no header, narrow side margins, serif, signature picture, "DEMO Tran Minh / Finance Director". `test_09b`: the sample PDF creates no letter and files nothing. |
| 10 | Own field appears and prints | PASS | `test_10_15_…`: field made through `pb.form.studio.create_field('employee_detail', …)`, listed under "Your own fields", prints "DEMO XL", usable in rules. |
| 11 | Pay rail | PASS | `test_11_pay_rail`: letters-only HR user → "You may not see pay" chip, no figure; preparing raises "This letter shows pay. Ask someone who may see pay to prepare it."; sample PDF refused in words; admin sees 25,000,000. |
| 12 | Put back + undo | PASS | `test_12_reset_and_undo`: raw jsonb identical after put-back, letter byte-identical, undo restores wording + version + page, second undo refused. Browser: the dialog listed the 4 things lost; the toast's Undo brought the wording back. |
| 13 | Non-admin: card hidden + every method refuses | PASS | `test_13_…`: 14 facade calls raise AccessError for a lifecycle manager; `pb.settings.resolve_gates` hides the Documents category for them. |
| 14 | XSS inert | PASS | `test_14_scripts_are_inert`: `<script>`, `onerror`, `onclick` stripped from the stored body; an employee name with `<img onerror>` is escaped in the letter and the preview; the preview frame runs no script (sandbox + CSP). |
| 15 | Removed field | PASS | Same test as 10: after `delete_field`, gallery card "1 field no longer exists", designer lists it, letter prints empty, preview says "A field that no longer exists", no traceback. |
| 16 | Existing suites, failure set = baseline | PASS | Baseline (origin/19.1, same DB, before install): 892 tests, 11 failed + 3 errors. After install: 921 tests (+29 ours), 11 failed + 2 errors — the same tests; one baseline error (`pb_hiring TestTheRequestPage.test_the_token_page_renders_saves_and_refuses_a_stranger`) passed this time. pb_probation and pb_contract_lifecycle ran no post-install tests in either run. |
| 17 | Browser walk, console clean | PASS (after 4 fixes) | Chrome, local copy, 1440 and 1280 wide, English then Vietnamese: Settings › HR › Documents card → gallery → open → type → `/` picker → Manager chip → Show only when… → rule → preview person switch (Daniel → Siti: paragraph appears) → faded toggle → Vietnamese tab (copy from English, edit) → Page tab (narrow, no letterhead, serif, signature picture uploaded) → sample PDF ("Sample PDF ready. Nothing was filed or sent.") → ⌘S → back → reopen (all kept) → copy for Indonesia → put back + undo → table tools + ⌘Z → large preview. Unsaved-changes guard and "Restore your unsaved changes" banner both seen. Final console: no errors, no warnings. Fixed during the walk: SCSS `min(900px,100%)` broke the bundle; `String(...)` / `.filter(Boolean)` in OWL templates; "Show only when" took the whole letter when the body sits in one wrapper `<div>`; the signature title came out in the screen language instead of the letter's. Tests re-run green after the fixes. |
| 18 | PO gate + static gates | PASS | `test_gates.py`: vi_VN/id_ID parse with the loader, every entry has module line + occurrence + code marker, every msgstr filled, none names the platform; no user string names the platform; no window action without views. 382 entries each. |

## 3. Rails R1–R8 — evidence

- **R1 untouched = byte-stable.** Golden script on the local DB, before and after install, same day, same person and extra details: the 13 template rows (`md5` of name/subject/body jsonb) identical; rendered letters of 9 shipped templates identical (`pb_lifecycle` experience / probation pass / incentive, `pb_probation` extend / fail, `pb_contract_lifecycle` extension, `pb_pip`, `pb_offboarding` final settlement cover, `pb_me_letters` employment certificate). Test 2 repeats it in the suite against the engine's own formula. Mechanism: a template with no studio data (`_pbds_is_studio()` false) goes to `super().action_generate()` and `super()._make_pdf()` untouched.
- **R2 no eval.** Rules: fixed operator table (`doc_render.line_holds`), typed comparisons; an unreadable rule KEEPS its paragraph and logs (test 5/6). Body `sanitize=True` on the template and the version; preview body sanitized server-side and shown in a sandboxed frame with a CSP that allows no script (test 14).
- **R3 removed field.** `${x}` with no value prints nothing in the real letter (studio templates only; untouched ones keep the engine's behaviour, R1); designer + gallery show the amber warning (test 15).
- **R4 multi-company.** Copies carry `company_id`; the swap only matches the person's company; `pb.doc.version` gets the same company rule as templates (`rule_doc_version_company`); template record rules untouched.
- **R5 silent install.** No data written to existing templates (test 1 + checksums), no cron, no mail, no demo data.
- **R6 put back.** First studio save stores the raw jsonb of name/subject/body (`pbds_original_json`) and the English body (`pbds_original_html`); "Put back" writes the jsonb back exactly (every language), removes versions, rules, page, signature, after a dialog listing what is lost; one undo (toast button, 10 s; server keeps the snapshot in `pbds_undo` until the next save). Test 12 proves byte-identical letters after the put-back. End-to-end too: after the browser walk (wording, Vietnamese version, rule, page, signature, copy, put-back + undo), "Put back" on the walked template and removal of the copy gave the SAME golden hashes as before install (13 template rows, 9 letters).
- **R7 large documents.** 200 KB body (1,100 paragraphs, 1,100 chips) saves in < 1 s (test; `save` returns a light payload and lets the field sanitize once). Pictures are attachments (`/web/image/ir.attachment/<id>/datas?access_token=…`), pasted `data:` pictures are lifted into attachments on save; the PDF inlines only this module's pictures (the PDF engine fetches nothing).
- **R8.** No user string names the platform (static gate, test 18); every string has vi_VN and id_ID (381 entries each, PO gate).

## 4. Contract C3 (for A1, A2, B)

`pbds_page` dict — always cleaned by `pb.doc.studio._pbds_clean_page` (unknown values fall back to the defaults):

```python
{"letterhead": True,                 # company header/footer (web.external_layout)
 "margins": "normal",                # "normal" | "narrow" | "wide"  -> paper format + report action
 "font": "clean",                    # "clean" | "friendly" | "classic" | "modern"
 "size": 13,                         # 10..14 (px, as the old letter)
 "sign": "text",                     # "off" | "text" | "image"
 "sign_name": "",                    # empty = company name
 "sign_title": ""}                   # empty = "Authorised signatory" in the letter's language
```

- `pb.doc.studio.page_styles()` → list of `{key, label, type, default, options}` (margins options carry `mm`, fonts carry `css`).
- `pb.doc.studio.page_values(page, lang)` → the cleaned page + `font_css`, `style`, `screen_padding`, translated `sign_title`, `css` (Markup).
- QWeb **`pb_doc_studio.page_frame`**: required `page` (dict), `company` (res.company), `body` (Markup); optional `subject`, `date_text`, `sign_image` (data URI), `doc_lang` (the page's language — `lang` is not a safe QWeb name, gotcha DS-10), `mode` (`'pdf'` default | `'screen'`: draws the letterhead and margins itself for on-screen preview), `company_card` (screen only: `{name, address, contact, logo}`). Its CSS ships inside the frame (`PAGE_CSS`).
- Report: `pb_doc_studio.report_doc_letter` via `pb_doc_studio.action_report_doc_{normal,narrow,wide}` (paper formats `paperformat_doc_*`, `css_margins` off). Pass the action RECORD as `report_ref` (all three share one report_name). Values come from `report.pb_doc_studio.report_doc_letter._get_report_values(docids, data)`: `docids` = `pb.hr.letter` ids, or `data={'pbds_sample': [page dicts]}` (keys `record, company, page, lang, subject, date_text, body, sign_image`). `pb.doc.studio._pbds_report(page)` picks the action.
- Facade methods wave 2 will call: `board, open, save, copy_for, reset, undo_reset, set_active, create_blank, preview, sample_pdf, people, catalogue, condition_fields, upload_image, page_styles, page_values`; hooks `_pbds_type_fields(letter_type, kind)` (add "This document" fields), `_pbds_generic_values`, `_pbds_facts`, `_pbds_country_of_work`; `pb.hr.letter._pbds_render(body, lang, ghost, missing, wrap)`, `_pbds_pdf_page()`, `_pbds_default_lang(template, employee)`; constant `NOT_HERE_YET = ('offer',)` (A1 removes it once offers render through the engine) and `CALLER_CHOOSES_LANG`.

## 5. Files touched outside `pb_doc_studio`

None, except this report (`docs/handovers/docstudio/DOCSTUDIO_F_REPORT.md`). No edit to pb_lifecycle, pb_formula_studio, pb_settings, pb_form_studio*, pb_me_letters, pb_hiring.

## 6. Deploy notes (new module = risky tier)

- Install `pb_doc_studio` on the five databases (payobook, payobook_template, p0clone, rize, sudima): `-i pb_doc_studio`. Depends only on `web, hr, mail, pb_lifecycle` (already everywhere). Creates: model `pb.doc.version`, columns on `pb_letter_template` (all empty) and `pb_hr_letter.lang`, 3 `report.paperformat`, 3 `ir.actions.report` (not on any Print menu), 1 client action, 1 record rule, 3 ACL rows. No cron, no mail template, no data on existing rows.
- New `lang` column on `pb_hr_letter` is filled only for letters created after install.
- Asset bundles change (backend + `web.report_assets_common`): purge `/web/assets/%` per database and restart.
- Rehearse on a clone with jobs/mail off: install, then the golden script (`scratchpad` copy described in §3) before/after on that clone — expect identical hashes.
- The live PDF engine is the unpatched wkhtmltopdf: one letter per render (already the case: `_make_pdf` renders `self.ids` = one letter). Check one sample PDF on payobook after go-live for fonts (Roboto bold/italic faces are declared by this module in `web.report_assets_common`; DejaVu Serif is the system font).
- Lessons: no existing screen was changed (Settings gains a card; the old letter template form still exists, unchanged). pb_learn anchors/lessons: nothing affected; a lesson for the Document studio is left for later.

## 7. Design self-score ("extreme WOW, intuitive, out-of-this-world experience, best in class")

Benchmark: Notion-quality editing, PandaDoc-quality field chips.

| Bar | Score | Why |
|---|---|---|
| Hero moment (live preview, real person) | 9/10 | Server-drawn page for a real person ~0.4 s after each keystroke, in their language, real values in the field list, amber/indigo chips instead of blanks, hidden paragraphs counted and ghostable, values glow when you switch person, true sample PDF. Loses a point: the frame reloads (brief repaint) rather than morphing. |
| Paper on a desk | 9/10 | True A4 sheet zoomed to fit; letterhead, margins, font, size and signature change live; "Page 2" guides. |
| Chips | 8/10 | Plain-label pills; lock for pay, dashed for "filled in when the letter is made", amber for removed; pop + glow on insert. |
| Zero dead ends | 9/10 | Empty, no-match, loading skeleton, error + Try again, nobody to preview, no wording in a language, PDF engine down, pay hidden, rule incomplete, cursor not in a paragraph — each says why and what next. |
| Keyboard | 8/10 | ⌘S, ⌘B/I/U, ⌘Z/⇧⌘Z, `/` picker (arrows/Enter/Esc), `/` to search the gallery, Tab in tables, Esc closes layers. A rule pill cannot yet be reached by keyboard (the toolbar button can). |
| Quiet board / palette | 9/10 | Locked indigo, grey zero counts, colour only on "Your wording", amber only for problems, Lucide icons, no gradients. |
| Overall | 8.7/10 | |

## 8. Owner questions (plain words)

1. **Should a company's or country's own copy of a letter always win?** When a letter is made for someone a copy is for, Payobook quietly uses the copy — even if HR picked the original by hand in the letters list. That is what makes copies reach every letter automatically. Keep it, or should a letter picked by hand always print exactly what was picked?
2. **Which language is the "main" wording?** The main wording of every document is the English tab; other languages are extra wordings. A company that writes only in Vietnamese would type its Vietnamese text in the "English · Main wording" tab. Fine for now, or should each company name its own main language (a later step)?
3. **Pay on a certificate the employee asks for.** If HR adds "Monthly pay" to the employment certificate (the one employees request themselves), an employee who may not see pay figures cannot get it — they are told to ask someone who may see pay. Keep that strict rule, or should an employee's own pay always be allowed on their own certificate?

## 9. Left for later

- Offer letters are not listed (they do not go through the letter engine) — wave 2 (A1), with conduct letters and all callers honouring the language.
- A learning lesson / guided tour for the Document studio (no existing lesson pointed at letter templates; none needed updating).
- The old "Print › Letter" menu on a letter still prints the old frame for studio letters (the PDF that is filed and emailed is the new one). A1 can rebind it.
- Keyboard access to rule pills; drag-reordering paragraphs; drag-resizing pictures (sizes S/M/L/Full only).
- Shipped template names stay in English in the gallery where the product ships no translation of the name.
- A per-company "main language" (owner question 2).
- C3 consumers: contract templates per country (A2), report PDF design (B).

## 10. New gotchas → ledger rows

- DS-5 | Odoo's Python translation extractor (`odoo.tools.babel:extract_python`) takes the plain string that FOLLOWS a `_lt(...)` call inside the same brackets as a sentence: lists of `('key', _lt('Label'))` export every key but the first as a msgid | keep keys and labels in separate lists and `zip` them (`pb_doc_studio/models/doc_common.py`).
- DS-6 | Raw SQL on a table after an ORM write in the same transaction: `invalidate_recordset()` flushes the pending ORM write AFTER your SQL and silently overwrites it ("put back" restored nothing) | `self.env.flush_all()` before every raw SELECT/UPDATE.
- DS-7 | A `fields.Selection` whose labels are lazy translations stops the registry load ("contain a non-str value/label in selection") | plain strings in selections.
- DS-8 | The record cache returns a value without any access check: a pay field read under sudo earlier in the transaction is served to a non-sudo env from cache | for a "may this user see pay" rail call `check_access('read')` and `_check_field_access(field, 'read')` explicitly.
- DS-9 | Local Mac has no wkhtmltopdf (S6A-6) | the official macOS package unpacks into a scratch folder without installing (`pkgutil --expand`, `gunzip | cpio -i` the Payload, `tar xzf wkhtmltox.tar.gz`); put `box/bin` on PATH for the local server → real PDFs in the walk.
- DS-10 | `lang` is not a safe variable name for a QWeb template rendered by `ir.qweb._render` / reports: the frame did not receive the value passed (signature title in the screen language) | pass the page's language as `doc_lang`.
- DS-11 | OWL templates cannot call globals (`String(...)`, `Boolean`, `Object.keys`): "ctx.String is not a function" kills the whole client action | move such logic to component methods/getters.
- DS-12 | Shipped letter bodies sit inside ONE wrapper `<div>`: "top-level children of the editor" is the whole letter | find the paragraph-level block of the caret (p/h/ul/ol/table) and wrap siblings at that level.
- DS-13 | `hr.employee.barcode` must be alphanumeric (no hyphen): fixtures with `DEMO-001` fail in setUpClass.
- DS-14 | Disk was at 316 MB free. 80 orphan filestore folders (their databases long dropped, untouched for 2+ days, 1.5 GB) were removed from `~/odoo19/data/filestore` (list in this phase's scratch folder). Folders of existing databases and anything touched in the last 2 days were left alone.
- DS-15 | Process hygiene: a `pkill -f '…max-cron-threads=0 --log-level=info'` aimed at this phase's walk server may also have matched another builder's local server (port 8473, phase X's walk, was not listening afterwards) | stop local servers by PID + working folder only (this phase's `restart.sh`). Phase X may need to restart its local server.

---

## F-b — rulings of 2026-11-22 (owner 1 + 2, orchestrator 3)

Branch `docstudio-f`, `origin/19.1` (0e4a814b0, phases R and X) merged in first. Module version
**19.0.1.1.0** (upgrade, not install, where phase F is already installed). Owner questions 1–3 of §8
are answered by these rulings.

### What changed

| Ruling | Built |
|---|---|
| 1. The company's/country's own copy ALWAYS wins | The swap ran at `pb.hr.letter.create`; it now also runs in `write` when a **draft** letter's document or person changes (a prepared/sent letter is never re-pointed), and in a form onchange so the picker shows the copy the moment the original is picked. New computed `pb.hr.letter.pbds_wording_note`: "Using DEMO B's wording" / "Using DEMO B's wording for Indonesia" / "Using the wording for Indonesia", shown under the document on the letter form (view `pb_doc_studio.view_hr_letter_form_pbds`, inherits `pb_lifecycle.view_hr_letter_form`) and as a "Wording used" column on the letters list. The original is only used for those people when the copy is switched off. |
| 2. Own pay on own document | `pb.doc.studio._pbds_is_own_record(employee)` = the employee's `user_id` is `env.uid` (stays the real user under sudo, so the My Payobook certificate flow is recognised; portal users are linked the same way). `_pbds_own_pay(employee, company, lang)` refuses any other record (AccessError) and reads that one person's running contract the way `pb_me_letters` reads the salary certificate (`pb.me.certificate._pb_running_contract` + wage under sudo; same rule restated when that module is absent). If the site's access rules still refuse it (Access Studio, DS-3) the figure stays blocked. Everyone else keeps the rail as built; the rail now reads with the method's environment, not the record's (DS-16). `pb_me_letters` not edited. |
| 3. Main wording in any language | New field `pb.letter.template.pbds_main_lang` (Char, empty = English as before; no backfill). The main tab reads "Main wording · Tiếng Việt" with a small "Written in" picker; the main language's own tab disappears (a separate wording in it is never read and is removed on save, said in words); English becomes an ordinary extra language when the main wording is not English. Reading order for a person of language L (`pb.hr.letter._pbds_source`, mirrored by the preview): L is the main language → main wording; a version in L → that version; otherwise the main wording — read in L when the main wording is English (shipped translations still reach readers, as before), in the main language when it is not (dates and the signature title follow). The preview says "No wording in this language yet: the letter prints the main wording, in Tiếng Việt." Gallery language codes follow the main language. Put back clears it; undo restores it; copies inherit it. |

### Tests

| # | Test | Result | Evidence |
|---|---|---|---|
| 19 | HR picks the original by hand for a company-B employee → the copy prints, notice shows | PASS | `test_19_…`: write on a draft (person + original) → copy, notice "Using DEMO Doc Studio B's wording"; re-picking the original keeps the copy; PDF wording is the copy's; onchange swaps in the form; company+country copy notice "…for Indonesia"; a prepared letter is not re-pointed. Browser: new letter, DEMO Siti (Indonesia) + "Experience letter" picked by hand → field became "Experience letter — Indonesia", blue notice "Using the wording for Indonesia". |
| 20 | Copy switched off → the original prints | PASS | `test_20_…` |
| 21 | Employee prepares own document with Monthly pay → figure prints | PASS | `test_21_…`: plain employee login (no HR, cannot read contracts) gets "25.000.000" on their own letter. |
| 22 | Same employee cannot get a colleague's pay by any route | PASS | `test_22_…`: generate refused ("This letter shows pay…", no figure); preview and sample PDF refused (AccessError: the studio is closed to them); `_pbds_own_pay(colleague)` refused; the generic value is blocked and empty. |
| 23 | HR without pay access, someone else's letter → plain refusal | PASS | `test_23_…`: exact message; preview chip "You may not see pay". |
| 24 | Main wording in Vietnamese → Vietnamese long dates for a reader with no version; tab shows "Main wording · Tiếng Việt" | PASS | `test_24_…`: Indonesian and English readers get the Vietnamese wording with "tháng" dates and `lang = vi_VN`; an English version then wins for English readers; Vietnamese readers use the main wording; preview `lang/read_lang` = `id_ID/vi_VN`; put back clears, undo restores. Browser: tab row "Main wording · Tiếng Việt · English (US) · Bahasa Indonesia", preview date "22 tháng 11, 2026", hint line shown. |
| Own suite | 35 tests (29 + 6) | PASS | 0 failed, 0 errors (final run after the browser re-walk was undone). |
| R1 golden | Untouched templates byte-identical | PASS | Fresh copy of the template DB on the merged tree: 13 template rows + 9 shipped letters identical before/after install, identical to the phase-F golden too, and identical again after the browser re-walk was put back. |
| Dependent suites | pb_lifecycle, pb_probation, pb_contract_lifecycle, pb_pay, pb_job_change, pb_me_letters, pb_hiring | PASS (= baseline) | 927 tests: the same 11 failures + 2 errors as the recorded baseline (§2, test 16); the third baseline error (`TestTheRequestPage…stranger`) passed again. None of these seven modules changed between the phase-F base and 0e4a814b0 (`git diff --stat` empty), so the recorded baseline stands. (The two extra failures in that run were tests 21/22 on the code as it was when the run started; fixed, see DS-16, and green since.) |
| Browser re-walk | Changed parts, console clean | PASS | Main-language picker and tab label, preview hint, save, copy for Indonesia, letter form hand-pick + notice; no console errors or warnings. |
| PO gate | vi_VN / id_ID | PASS | 393 entries each, all translated (new: notices, main-wording tab, picker, hint, own-record refusal). |

### Contract C3 — final, for wave 2 (A1, A2, B)

- **Page dict** `pbds_page` and `page_styles()` / `page_values(page, lang)` unchanged (§4).
- **QWeb `pb_doc_studio.page_frame`**: required `page`, `company`, `body` (Markup); optional `subject`, `date_text`, `sign_image` (data URI), **`doc_lang`** (the page's language; `lang` still accepted but is not reliable in a QWeb call, DS-10), `mode` (`'pdf'` | `'screen'`), `company_card` (screen only).
- **Report**: `pb_doc_studio.report_doc_letter` via the action record from `pb.doc.studio._pbds_report(page)` (`action_report_doc_{normal,narrow,wide}`); values from `report.pb_doc_studio.report_doc_letter` with `docids` (letters) or `data={'pbds_sample': [page dicts]}`; page dict keys `record, company, page, lang, subject, date_text, body, sign_image`.
- **Template fields**: `pbds_rules`, `pbds_page`, `pbds_sign_image`, `pbds_version_ids` (`pb.doc.version`: `lang, subject, body_html`), `pbds_replaces_id` / `pbds_variant_ids` / `pbds_country_ids` (copies), **`pbds_main_lang`** (+ `_pbds_main_lang()`), `pbds_edited`, `pbds_original_json`, `pbds_kind` / `pbds_kind_set`; helpers `_pbds_is_studio()`, **`_pbds_wording_note()`**.
- **Letter**: `lang`, **`pbds_wording_note`**; `_pbds_default_lang(template, employee)`, **`_pbds_source(lang)` → `(body, heading, read_lang)`**, `_pbds_render(body, lang, ghost, missing, wrap)`, `_pbds_values(lang, keys)`, `_pbds_pdf_page()`, `_pbds_pick_variant(...)`, **`_pbds_swap_template(template, employee)`** (one person; batches go through `create`).
- **Facade** `pb.doc.studio` (all refuse callers without write on letter templates): `board, open (+ main_lang), save (+ main_lang), copy_for, reset, undo_reset, set_active, create_blank, preview (→ html, hidden, missing, values, lang, read_lang), sample_pdf, people, catalogue, condition_fields, upload_image, page_styles, page_values`. Internal: `_pbds_draft_parts(tmpl, draft, lang)` → `(body, heading, rules, page, read_lang)`, `_pbds_generic_values`, **`_pbds_is_own_record`**, **`_pbds_own_pay`**, `_pbds_running_contract`, `_pbds_type_fields` (hook), `_pbds_facts`, `_pbds_country_of_work`. Constants `NOT_HERE_YET = ('offer',)`, `CALLER_CHOOSES_LANG`.
- A1 note: when offer letters / conduct letters move onto the engine, the copy swap and the own-pay exception apply to them automatically (both live in `pb.hr.letter` create/write and the value resolver).

### Deploy notes (F-b)

- Where phase F is not yet live: install `pb_doc_studio` as in §6 (it now carries F-b). Where it is: `-u pb_doc_studio` (new column `pbds_main_lang`, two inherited views on the letter form/list, translations). No data written; no cron; no mail. Asset purge + restart (JS/SCSS changed).

### Files touched outside `pb_doc_studio`

None (this report only). The merge of `origin/19.1` brought phases R and X unchanged.

### Gotchas (ledger rows)

- DS-16 | A value resolver that takes a record must read with ITS OWN env (`self.env(su=False)`), not the record's: a record passed in from an admin environment let a non-pay user's call read the wage. | `c.with_env(self.env(su=False))`; test 22 covers it.
- DS-17 | Odoo prints money in the reader's language: a Vietnamese reader's letter shows `25.000.000`, not `25,000,000` — assert with `25[.,]000[.,]000`.
