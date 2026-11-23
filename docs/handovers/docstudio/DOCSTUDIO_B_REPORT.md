# DOCSTUDIO phase B — Design the PDF of a report (study line 881) — REPORT

Branch `docstudio-b` (from `origin/19.1` 0e4a814b0 with `origin/docstudio-f` 84237cb87 merged —
a fast-forward, F already contains 19.1). Builder and tester: Opus. Not merged, not deployed.
Sparse worktree `/Users/adity/Documents/GitHub/gitlocal-worktrees/docstudio-b`; local database
`docstudio_b_t` (copy of `wf2p6c_uitpl`, its 13 stale modules upgraded, then
`pb_report_builder`, `pb_excel_layout`, `pb_doc_studio` installed) — dropped at the end with its
filestore. Local PDF engine: wkhtmltopdf 0.12.6 unpacked into the session scratch folder (DS-9).

New modules:
- **`pb_report_pdf` 19.0.1.0.0** — depends `web`, `pb_doc_studio` (page frame C3). Report builder,
  Explorer and Excel layouts are probed at run time (no dependency).
- **`pb_report_pdf_send` 19.0.1.0.0** — `auto_install` bridge on `pb_report_pdf` + `pb_excel_layout`
  (the "Send as" row it extends belongs to pb_excel_layout; see Deviations).

## 1. What was built

| Item | Built |
|---|---|
| B1 "PDF" on any report with a table | OWL component `PbReportPdfButton` registered in `registry.category("pb_report_pdf")` key `"button"`, props `{sourceModel, sourceId, disabledReason?}` (C2 shape). Disabled with its reason on hover/focus ("Save the report first.", "Save your changes first.", "Save this view first"). Rendered by the report builder toolbar (after "My Excel layout") and by the Explorer head (after "My Excel layout"); nothing when the registry is empty. Server sources: built reports (`pb.report.definition`, richer path through `pb.report.builder._pbrb_table` so groups/totals print as on screen), saved Explorer views (`_pbxl_table` from pb_excel_layout; when that module is absent the same wrapper is built in `pb.report.pdf._pbrp_table_view` from `pb.explorer._export_rows`), and any other model with `_pbxl_table` (plain C1). |
| B2 Designer (hero) | Full-screen dialog: top bar (report name, look status "Your look / Shared by X / Company look / Standard look / Unsaved changes", Save look, Download PDF, close with an "unsaved look" guard). Left: Paper (A4/A3, Fit/Upright/Sideways + hint "Fit turns the page sideways when more than 7 columns print"), Page (company letterhead, font "Clean" or "Classic serif" shown as "Aa" tiles, text size 10–14 — C3 `page_styles`; see Deviation 6), Heading (title, second line on/off + text; defaults = report name, period + filters in the builder's own words), Table (header-row colour swatches from the locked palette: Indigo, Deep ink, Soft indigo, Slate, Plain; striped rows; group headings and subtotals as on screen; grand total row), Columns (tick to print, width "Auto · 24%" / "30% wide", "Let the widths fit the text again"), Footer ("Printed on … by …", a line saying where the page numbers come from, closing note), This look (share — report owner only; "Use this look for every new report" / "Stop using a company look" — administrators only; "Back to the standard look" with inline confirm). Right: the REAL first page drawn by the server (`pb.report.pdf.preview`) at true paper size, zoomed to fit, in a sandboxed frame (no scripts, CSP `default-src 'none'`), double-buffered so a redraw never flashes blank, redrawn ~220 ms after a change (450 ms while typing); chips "About 12 pages · 900 rows · A4 · Sideways (fit)", amber chip when the 5,000-row cap is hit, the source's own note (hidden columns). **Drag the edge between two column headings on the page** to resize (live dashed guide; the new widths are kept for every printed column so the next drawing is exactly what was dragged). Keyboard: Ctrl/⌘+S save, Ctrl/⌘+Enter (or +P) download, Esc closes. States: loading skeleton, cannot-open (reason + Try again), no columns ticked (amber, download disabled), preview failed (amber line, last page kept), empty report ("This report has no rows to print."), engine down ("The PDF could not be made right now…"). |
| Look storage | `pb.report.pdf.look` (`source_model`, `source_id`, `user_id`, `shared`, `look` Json, + `is_default`, `company_id`). Rules cloned from `pb.explorer.view`: read own / shared / company default of my companies; write own non-default; settings admins all. `create`/`write` refuse a company default for non-administrators even through the plain record API. Resolution: my own → the report owner's shared look → any shared → company default (page choices only: paper, turn, letterhead, font, size, colour, stripes, groups, total, printed, pages — never one report's columns or words) → built-in. Every look is cleaned on the server (`clean_look`): allowed values only, text capped, control characters removed, column keys pattern-checked, widths 2–90 %. |
| B3 Real PDF | QWeb `pb_report_pdf.report_table` through two explicit `ir.actions.report` (A4, A3; paper formats `paperformat_pdf_a4/_a3`, not on any Print menu). Orientation via the render context (`landscape`), top margin via `data-report-margin-top` (40 mm with letterhead, 16 without). Body = `pb_doc_studio.page_frame` (C3, `mode='pdf'`, sign block off) wrapping `pb_report_pdf.table_body`; letterhead on = `web.external_layout` (the company's own header and footer, page numbers included) and the "Printed on … by …" line is appended to that company footer by a scoped `_prepare_html` override (only for this report, only when the context carries it); letterhead off = own footer ("Printed on … by …", "Page 1 of 3"). Page numbers always print, exactly once (orchestrator ruling 2026-11-22). All text — table, company header/footer, our footer — prints in fonts installed on the server (DejaVu Sans; DejaVu Serif for Classic), never a web font (DS-B8). `thead` repeats on every page, `tr { page-break-inside: avoid }`, `table-layout: fixed` + column widths so long words wrap. Numbers right-aligned with `formatLang` in the reader's language; dates with `format_date` (reader's date format); money with its own currency (`formatLang(currency_obj=…)`), totals per currency on separate lines. 5,000-row cap with "Only the first 5,000 of 6,000 rows are printed. Add a filter to print fewer rows." under the title, in the footer and on screen. Built as the READER: the table is the source's own answer for the caller (`_pbxl_table` / `_pbrb_table` as `env.user`); file name `<product label> <title> <date>.pdf`. |
| B4 Scheduled sends | `pb_report_pdf_send`: "PDF in my look" button in the "Send as" row of the Explorer's Send regularly drawer (template inheritance of pb_excel_layout's extension; JS patch using the existing `scheduleExtraVals` seam), card line "As a PDF in your look". Field `pb.explorer.schedule.pbrp_pdf` (exclusive with `layout_id`). In `_pbx_attachment` each recipient's PDF is built through the facade AS THAT RECIPIENT (`view._pbxl_table_for(explorer, spec)`, their companies, divisions and language), in the look the schedule owner prints that view with. A failure sends the standard Excel, logged through pb_excel_layout's `LAYOUT_FAILS` as `layout_failed` with reason `pdf_failed|`, history line "Sent as the standard Excel — the PDF could not be made". The email line "The full table is in the attached Excel file." becomes "…attached PDF." when a PDF is attached. Mail off → `email_off` exactly as today (nothing built). |

Payslip layouts already have their own designer (study line 700 "have") — out of scope, untouched.

## 2. Tests

Suites run with `-u` on the local copy (`--test-tags /pb_report_pdf,/pb_report_pdf_send`), real PDFs
made with the local wkhtmltopdf (`force_report_rendering`), text extracted with PyPDF2.

| # | Test | Result | Evidence |
|---|---|---|---|
| 1 | Install silent | PASS | `test_01`: no look, no cron / mail template / menu from the module, both report actions unbound. `-i pb_report_pdf` clean (bridge auto-installed), no ERROR. |
| 2 | PDF of a built report = on-screen table | PASS | `test_02`: real PDF text holds every screen heading, first and last rows of the report's own table, "Department: X" headings, "Total X · n" per group = screen group counts, "Grand total · N" = screen total; file name ends `.pdf`, no platform name. |
| 3 | 3,000 rows | PASS | `test_03` (real PDF, table of 3,000 rows × 4 columns through the report path): **63 pages in 14.5–19.6 s** (24.6 s on the first run; machine load 100–220); heading row on every page; every row exactly once; no row split across pages. |
| 4 | 6,000 rows → 5,000 + note | PASS | `test_04`: preview capped, 5,000 of 6,000, note on screen and in the file, row 5,000 absent. |
| 5 | Sideways auto-fit | PASS | `test_05`: 7 cols A4 upright, 8 sideways, A3 8 upright / 12 sideways, forced upright/sideways; real PDF of 9 columns has a landscape page box. |
| 6 | Letterhead on/off + page numbers once | PASS | `test_06`: on = company layout + 40 mm top; off = own footer with "Printed on" + page counter, 16 mm; exactly one page counter in each document (an old look with the switch off still prints it); our footer line never adds a second one; real PDFs: one "Page n" per page; Clean prints DejaVu Sans, Classic DejaVu Serif. Against a RUNNING server (real assets): 37-page and 33-page attendance report (880 rows) and a 1-page report, with and without letterhead: every page has its rows, exactly one page number and the printed line. |
| 7 | Column resize saved and applied | PASS | `test_07`: widths 55/25/20 saved, reopened as "mine", preview widths equal, `width: 55.0%` in the file. |
| 8 | Hidden column absent | PASS | `test_07` (second half): Department neither in the preview nor in the real PDF text; all columns off → "Pick at least one column to print." and no file. |
| 9 | Groups + subtotals + grand total | PASS | `test_02` (one level, real PDF) + two levels: headings and subtotals at both levels, grand total last. |
| 10 | Two currencies not added | PASS | `test_10` (contracts, pay in two companies' money): grand total cell = 2 lines, no sum across currencies; `test_14b` (Explorer, VND + USD): 1,500,000 and 40.5 on separate lines, never 1,500,040. |
| 11 | Less access, same shared look | PASS | `test_11`: owner shares the report and its look (title, colour, A3); an HR user in one company without pay opens it: origin "shared", same title/colour/paper, no pay column, no other-company row, no pay figure; they may save their own copy but not share the owner's (AccessError); the owner's look is unchanged. |
| 12 | Vietnamese glyphs and dates | PASS | `test_12` (contract start dates — a column that really holds a date): Vietnamese format present, English format absent, "Lê Thị Hoà", "Báo cáo nhân sự Hoà", footer "In lúc …" and "Trang …". Walk: 33-page Vietnamese PDF, "Trang n / 33" on every page, dates 05/01/2026, numbers 7,82. |
| 13 | Hostile text inert, long words wrap | PASS | `test_13`: `<script>` name, `<img onerror>` title and `<script>` note escaped in preview and file; real PDF stays upright A4 and the 240-letter word is broken across lines. |
| 14 | Explorer saved view PDF | PASS | `test_14`: open/download of a saved view, columns Name/Currency(hidden)/…/Total, period line; the module's own wrapper = pb_excel_layout's `_pbxl_table` (same columns and rows); a user without the Explorer gate gets a sentence. |
| 15 | Scheduled send | PASS | `test_15`: "PDF in my look" saved (exclusive with a layout); mail off → `email_off`; mail on → each recipient's PDF built as THAT user (spy) in the owner's look, attachment `application/pdf`, own departments only (division-held readers), body says "attached PDF"; broken PDF → standard `.xlsx`, `layout_failed` / `pdf_failed|`, "Sent to 2 of 2", history "the PDF could not be made"; back to standard. |
| 16 | Registry button absent → nothing | PASS | `test_16` (static: both toolbars `get("button", null)` + `t-if`, no dependency) + browser (see 17). |
| rules | Looks follow the rules | PASS | `test_14_looks_follow_the_rules`: private look invisible to others, no write, no default by non-admins (ORM and facade), private report refused in words, company default reaches a new report (page choices only), clear, put back. `test_15_refusals`, `test_16_the_look_is_cleaned`. |
| 17 | Suites at baseline | SEE §2.1 | |
| 18 | Browser walk | SEE §2.2 | |
| 19 | PO + static gates | PASS | `test_18a` (no platform name in any user string/template, no emoji, no gradients, no Sass min/max, no `--` in XML comments), `test_18b` (vi_VN + id_ID complete for both modules, placeholders kept, module line on every entry). 133 + 13 terms. |

### 2.1 Dependent suites

Same local copy, `-u` of each module (DS-10), with the B edits in place:

| Suite | Result | Recorded baseline |
|---|---|---|
| `pb_report_builder` | 31 tests, 0 failed | R-b: 31/31 |
| `pb_explorer` | 101 tests, 0 failed (`test_08_facade_never_writes` passes) | X: 101, 0 failed |
| `pb_excel_layout` | 29 tests, 0 failed | X-b: 29, 0 failed |
| `pb_doc_studio` | all passed, 0 failed | F-b: own suite green |
| `pb_insights_hub` | 40 tests, 2 failed: `test_the_lens_order_matches_the_mockup`, `test_the_feature_set_is_intact` | R: the same two fail at baseline |
| `pb_report_pdf` + `pb_report_pdf_send` | all green (15 + 3 + 3 test methods) | new |

Final run after the resume fixes (fonts, page numbers, test 12): `pb_report_builder` 31 tests 0
failed; `pb_report_pdf` + `pb_report_pdf_send` all green (test 1 now checks that the install ships
no look — the walked database holds people's own looks). The other suites above were run before
those fixes; the fixes touched only `pb_report_pdf`.

The first hub run errored on 12 tests that read sibling modules' files (`pb_insights`, `pb_hub`, …)
through the overlay folder (DS-W1A-2); with those siblings added to the sparse checkout the run
equals the baseline above.

### 2.2 Browser walk

Chrome, local copy (`docstudio-b.localhost`), administrator, seeded with 8 DEMO people and 880
attendance rows. Console: no errors, no warnings on every page.

- **Insights › Build a report › "Attendance this year by department" › PDF** (1440): designer opens
  on "Standard look", "About 23 pages · 880 rows · A4 · Upright (fit)", the real first page with
  the company letterhead, the period line "This year, by Check in", "Department: DEMO Finance ·
  220 rows", footer "Printed on … · Page 1 of 23". Fixed during the walk: the sheet was not zoomed to
  the window (the dialog body grows with its content) — the designer now takes the window height.
- Dragged the edge between Employee and Department on the page: live dashed guide, widths 34 % /
  7 %, status "Unsaved changes" → Ctrl+S → "Your look". Sideways → "A4 · Sideways"; Deep ink header
  colour; Department unticked → 4/5 columns, gone from the page.
- **Download PDF**: "Your PDF is downloaded: 880 rows, made in 26.1 seconds." (machine under load),
  file "Payobook Attendance this year by department 2026-11-22.pdf". The real-PDF check against the
  running server found the web-font defect (DS-B8: blank first pages, everything bold) — fixed by
  printing in server fonts; re-checked page by page (§2 test 6).
- **Explorer**: before a view is saved the PDF button is disabled and says "Save this view first";
  saved view "DEMO Headcount by department" (`#pbxv=`) → PDF → designer with columns Department /
  Total, "1 page · 0 rows" and the page saying "This report has no rows to print." (the walk copy
  has no pay runs — the empty state, as designed; filled Explorer tables are covered by tests 14,
  14b, 15). **Send regularly** drawer: "Send as: Standard Excel / PDF in my look", choosing PDF
  lights it and shows "Each person gets a PDF of their own figures…".
- **Vietnamese, 1280 wide**: "Thiết kế bản PDF", "Kiểu của bạn", "Khoảng 39 trang · 880 dòng · A4 ·
  Đứng (vừa trang)", every section translated, the page in Vietnamese (dates 05/01/2026 08:00,
  7,82, "Phòng ban: DEMO Finance 220 dòng", "Trang 1 / 39"); download "Đã tải bản PDF của bạn: 880
  dòng, tạo trong 6.6 giây."

Not walked: a reader with less access in the browser (covered by test 11) and a real scheduled send
(mail is off locally; covered by test 15). The page estimate is approximate (shown as "About"):
23 or 39 estimated against 33 real pages for the walk report.

## 3. Rails

| Rail | Evidence |
|---|---|
| Never more than the screen | The table is always the source's own answer for the caller: `pb.report.definition` through `pb.report.builder._pbrb_table` after `_require` + `check_access` (the same call `_pbxl_table` makes), Explorer views through `_pbxl_table` / `_export_rows` as the reader, schedules through the facade `with_user(recipient)`. No superuser read of data anywhere in the module (looks are read with sudo — printing choices only, after the report check). Test 11, 15. |
| A look is not data | Saved looks hold choices and column keys; a key the reader does not have is ignored. A shared look never widens. |
| Preview cache | 90 s, 6 entries, keyed by database, user, report, its last change, language and companies; download always reads fresh. |
| Inert text | QWeb `t-esc` everywhere; the preview frame runs no script; test 13. |
| Money | Per currency, never added (test 10, 14b). |
| Silent install | Test 1; no cron, no mail, no data. |
| White-label | No platform name in templates, `_()`/`_t()`, msgstr, file names; the PDF `<title>` is the report title (the platform's default title is never used). |

## 4. Edits outside the new modules

| File | Line(s) | Edit |
|---|---|---|
| `pb_report_builder/__manifest__.py` | 26-27 | version 19.0.1.0.0 → 19.0.1.1.0 + comment |
| `pb_report_builder/static/src/js/report_builder.js` | 73-74 | `this.pdfButton = registry.category("pb_report_pdf").get("button", null);` |
| `pb_report_builder/static/src/xml/report_builder.xml` | 121 | `<t t-if="pdfButton" t-component="pdfButton" t-props="layoutProps"/>` (same props as the Excel layout button) |
| `pb_explorer/__manifest__.py` | 39-40 | version 19.0.2.9.0 → 19.0.2.10.0 + comment |
| `pb_explorer/static/src/js/explorer.js` | 1628-1632 | getter `reportPdfButton` (registry lookup, `null` when absent); no parameter named `s` |
| `pb_explorer/static/src/xml/explorer.xml` | 53-57 | `<t t-if="reportPdfButton" t-component="reportPdfButton" sourceModel="'pb.explorer.view'" sourceId="…" disabledReason="excelLayoutWhy"/>` |

`pb_explorer.py` untouched (never writes). No edit to pb_doc_studio, pb_excel_layout, pb_lifecycle.

## 5. Deviations

1. **Second new module `pb_report_pdf_send`** (auto-install bridge). Scheduled sends need a field and
   overrides on `pb.explorer.schedule` and a patch of the Explorer component — impossible from
   `pb_report_pdf` while keeping pb_explorer / pb_excel_layout soft. It installs by itself wherever
   both are present (all five databases today).
2. **Letterhead footer line** is joined to the company's own footer by a scoped `_prepare_html`
   override on `ir.actions.report` (only `pb_report_pdf.report_table`, only with the context key).
   The engine takes one footer per document, and the company footer already carries the page
   numbers, so with the letterhead the "Page numbers" switch follows the company footer (said on
   screen).
3. **Margins** are fixed for reports (12 mm sides, 22 mm bottom; 16 mm / 40 mm top) — the handover
   lists no margin option; C3's margins choice is not offered.
4. **Test 3 uses a 3,000-row table injected at the source** (the report path, the page engine and
   the real PDF are real; creating 3,000 people locally takes ~1 h, DS-R7). The browser walk used a
   real built report with 880 attendance rows.
5. **"Fit"** counts printed columns only (7 on A4, 11 on A3), as specified.
6. **Fonts**: report PDFs print in fonts installed on the server, so the font choice offers the two
   C3 fonts that differ on paper — "Clean" (DejaVu Sans) and "Classic serif" (DejaVu Serif); looks
   that hold "Friendly"/"Modern" print as Clean. Web fonts (Roboto, Open Sans, Montserrat) are not
   used in the PDF: the engine loses the text of the first pages of a long document in any web
   font, downloaded or carried inside the file, and draws all weights of a carried-in font with
   one face (DS-B8). The same fix covers the company header and footer of this report only.
7. **Page numbers** (orchestrator ruling): the "Page numbers" switch is gone; they always print
   exactly once — the company's own footer with the letterhead, ours without.

## 6. Deploy notes

- Ship `pb_report_builder` (19.0.1.1.0) and `pb_explorer` (19.0.2.10.0) with `-u` (asset-only
  changes), then `-i pb_report_pdf` on payobook, payobook_template, p0clone, rize, sudima — the
  bridge `pb_report_pdf_send` installs itself (pb_excel_layout is everywhere). Never abm.
- New: table `pb_report_pdf_look`, column `pb_explorer_schedule.pbrp_pdf` (empty), 2 paper formats,
  2 report actions (not on any Print menu), 3 record rules, 1 ACL. No cron, no mail, no data.
- Asset purge + `web.assets.version` bump (new JS/SCSS/XML in four modules).
- Fonts: the PDF uses the C3 fonts (Roboto / Open Sans / DejaVu Serif / Montserrat via
  `web.report_assets_common`, declared by pb_doc_studio). Check one PDF with the letterhead on
  payobook after go-live (header/footer CSS is fetched by the engine from the server's own URL;
  locally without a running server the company header/footer were unstyled — expected).
- Tier: normal (new module, read-only screen; no pay figure, no stored data rewritten).
- Lessons: the report builder and Explorer toolbars gain one button; `pb_learn` replicas of the
  Explorer show no toolbar buttons (X report §9) and no lesson covers the report builder toolbar —
  nothing to update. A "Design the PDF" lesson is left for later.

## 7. Design self-score ("extreme WOW, intuitive, out-of-this-world experience, best in class")

Benchmark: Looker Studio / Airtable print layouts. **8.5 / 10.**

| Bar | Score | Why |
|---|---|---|
| Hero moment (the real first page, live) | 9 | Server-drawn page at true paper size, double-buffered redraw, drag column edges on the page itself with a live guide, Fit turning the page sideways as columns are ticked, page and row estimate always visible. Short of 10: the preview shows page 1 only (later pages are in the file). |
| Zero dead ends | 9 | Loading, cannot open (+ Try again), nothing ticked, empty report, cap hit, engine down, unsaved look on close, shared/company/standard origin always named. |
| Keyboard | 8 | Ctrl/⌘+S, Ctrl/⌘+Enter, Esc, every control a real button/checkbox with focus rings; column widths by keyboard not offered (drag only). |
| Palette / quiet board | 9 | Locked indigo, Lucide icons, no gradients, amber only for problems, grey quiet states. |
| Truth | 9 | The preview and the PDF come from one document; the PDF is always the reader's own table. |

## 8. Owner questions (plain words)

Both earlier questions were ruled by the orchestrator (2026-11-22): the company footer keeps its
page numbers with the letterhead (never twice, always present without it), and only the person who
saved a report shares its look; administrators set the company default.

1. **Fonts in report PDFs.** Report PDFs print in the two fonts every server has ("Clean" and
   "Classic serif"); the two other screen fonts lose text on long PDFs. Fine, or should we install
   more fonts on the server (a small server change) so all four can print?

## 9. Left for later

- A "Design the PDF" lesson in Learning.
- Previews of pages after the first (the file has them); keyboard resizing of columns.
- Margin choice for report PDFs; reordering columns in the PDF only.
- PDF looks for other C1 sources as they appear (any model with `_pbxl_table` already works).
- Payslip layouts stay in their own designer (out of scope).

## 10. Gotchas → ledger rows

- DS-B1 | `ir.actions.report._get_report(record)` returns `record.sudo()` — a context set on the
  caller (`with_context(landscape=…, my_key=…)`) is LOST when a plain record is passed as
  `report_ref` | pass the SAME contexted record as `report_ref` (`r = rep.with_context(...);
  r._render_qweb_pdf(r, ...)`).
- DS-B2 | Calling `web.external_layout` with a QWeb variable named `doc` breaks it: the layout does
  `o = doc` when `o` is empty and then reads `o._name` ("'dict' object has no attribute '_name'")
  | never name report values `doc`/`o`/`docs` (B uses `rp`).
- DS-B3 | `'width: %s%%;' % x` inside a QWeb attribute expression in a data XML file reached the
  engine as `%s%` ("not enough arguments") | use `t-attf-style="width: {{ x }}%;"`.
- DS-B4 | PyPDF2 text of a wkhtmltopdf PDF separates words with TABS and lines with newlines |
  normalise whitespace before `assertIn`.
- DS-B5 | Locally the PDF engine fetches the report CSS from `web.base.url`; with no server running
  (shell, TransactionCase) the company header/footer come out unstyled and the engine logs
  "Exit with code 1 due to network error: ConnectionRefusedError" — the PDF is still made | judge
  header/footer looks only with a running server.
- DS-B6 | A test reading a shared report as a second user right after the owner sees the owner's
  linked names from the record cache (DS-8 again, in the report builder's filter words) |
  `env.invalidate_all()` between the two readers to model two requests.
- DS-B8 | wkhtmltopdf 0.12.6 + web fonts: in a long document (about 4,000+ table cells) the text
  of the FIRST pages is not drawn in any web font (served by the report assets OR carried inside the
  page as a data URI) while later pages print; a carried-in family with two weights is drawn with
  one face (all bold); the company header/footer (Lato) lose their text on the first pages the same
  way. Invisible locally without a running server (fonts fail fast, the fallback is used) | print
  report PDFs in installed fonts (DejaVu) and force them on the header/footer page too
  (`_prepare_html`); check real PDFs page by page against a RUNNING server. Letters of
  pb_doc_studio (C3 fonts) may show the same on long letters — worth a check by the deploy agent.
- DS-B7 | Sparse worktree: a NEW top-level folder (a second module) is outside the sparse set —
  `git add` refuses it | `git sparse-checkout add '/<module>/'` first.
