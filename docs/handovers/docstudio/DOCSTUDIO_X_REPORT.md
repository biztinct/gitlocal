# DOCSTUDIO X — Fill my own Excel layout (study line 920) — report

Builder + tester: Opus (own worktree, branch `docstudio-x` from `origin/19.1` 4eaee9db3).
New module **`pb_excel_layout` 19.0.1.0.0**; **`pb_explorer` 19.0.2.8.0 → 19.0.2.9.0**
(three small seams only). Not deployed. Local database `docstudio_x_t` (copy of
`upd_p6_t_tpl`) and its filestore dropped at the end.

## 1. What was built, per item

| Item | Built |
|---|---|
| **X1** "Use my Excel layout" | A **My Excel layout** button beside *Download Excel* in the Explorer head (also inside the Insights hub's Explorer tab). It is the contract-C2 registry component, so any other screen gets it by rendering `registry.category("pb_excel_layout").get("button")`. Until a saved view is open it is disabled and says **"Save this view first"** on hover/focus. Click → a list card: your layouts and the ones shared with you, each with **Download in my layout**; owner menu: Change where the figures go · Replace the file · Rename · Share / Make it only mine · Delete (inline confirm). Empty state invites "Use my Excel layout". |
| **X2** Set-up dialog (hero) | Step strip (Your file → Where the figures go → Try it and save). Drop zone (drag or choose, .xlsx/.xlsm ≤ 10 MB) → reading skeleton → THEIR sheet as a 20 × 12 mini grid with column letters, row numbers, their bold and fill colours (white text on dark fills), Excel-style sheet tabs (chart sheets disabled, hidden sheets italic). Click a cell (or arrow keys, or type B6): the table area lights up in soft indigo with an indigo outline; the heading row shows the actual headings that will be written; values that will be replaced are struck through; a live chip says **"6 columns × 8 rows from B6"** (+ "Continues down to row 40 / across to column N"). Default start cell: the heading row of an Excel table on the sheet; else the team's own heading row (figures start under it, headings off); else the first empty row under the top rows; A1 on an empty sheet. "Write the column headings" switch with heading chips. Coaching line: "Point your formulas and charts at whole columns or an Excel table so they pick up new rows." Notes: macros ("This file contains macros. Payobook does not run or change them." — product name via `product_label`), Excel table found at the start, merged cells in the way (blocks Try it / Save), no figures yet. **Try it** downloads their own file filled with the current result and says "Your file is downloaded with N rows from B6…". **Save layout** with a name and a share switch. |
| **X3** Use it | "Download in my layout" per layout: fresh figures as the person clicking; `last_used` stamped. Layouts are owned and shareable like saved views; a shared one reaches only people who can open the view. |
| **X4** On a schedule | The Explorer's *Send regularly* drawer gets **Send as: Standard Excel / <layout>** (template inheritance + JS patch from this module; the drawer markup itself is untouched). The schedule card says "In your layout “X”". Each recipient's file is built through the Explorer facade AS THAT RECIPIENT (companies, divisions, language — the existing `_pbx_mail_for` rule), so each gets only their own figures. |
| **X5** Manage | Replace the file keeps sheet + start cell when the sheet is still there; otherwise the layout says plainly "The sheet “Data” is not in this file. Pick the sheet that receives the figures." Such a layout never fails a send or a download: the standard Excel goes instead and the history line says why (`layout_failed`, "Sent as the standard Excel — the layout could not be used: …", counted as sent). Rename, share, delete. Caps: 20 layouts per owner, name 80. |

### How the file is filled (zip surgery, ledger DS-2) — `pb_excel_layout/models/xlsx_fill.py`
1. Sheet resolved through `xl/workbook.xml` → `xl/_rels/workbook.xml.rels`; chart sheet / missing sheet refused plainly.
2. Only `<sheetData>` cells from the start row down, inside the table's columns, change; rows above, cells left and right kept (implied row/cell numbers handled).
3. Each column takes the style of the template's first data row; headings take the start-row styles; the first data row's height/row style is copied to new rows.
4. Text → `inlineStr` (never a formula; XML-illegal characters stripped; 32,767 cut + note); numbers `<v>`; booleans `t="b"`; dates → serial when the column's template style is a DATE format (1904 calendar honoured), else ISO text; None → no cell (styled empty cell kept).
5. Rows below a shorter result are emptied in the table columns (formatting kept, values/formulas removed).
6. `<dimension>` recomputed, stale `spans` dropped. Refused at set-up with a sentence: merged cells, shared/array formulas reaching out of the area, Excel-table headings inside the area.
7. An Excel table starting at the heading row is resized (ref + autoFilter, sortState dropped, column names = headings); column-count mismatch → left alone + note (names of headings written over it synced so Excel does not "repair").
8. `calcPr fullCalcOnLoad="1"` (inserted in schema order if absent), `refreshOnLoad="1"` on every pivot cache, `calcChain.xml` + its content type and relationship removed.
9. Every other member written back in the same order, date and compression, byte-identical content; the result is re-opened (zip checks + openpyxl read-only) before it is handed out.

## 2. Tests

Local copy of `upd_p6_t_tpl` → `docstudio_x_t`. The copy was 53 modules behind `origin/19.1`;
they were upgraded once first (DS-7). Baseline = `origin/19.1` `pb_explorer` exported into a
scratch addons folder placed first on the path.

| Suite | Baseline (origin/19.1) | Branch |
|---|---|---|
| `pb_explorer` (101 methods) | 0 failed, 0 errors | **0 failed, 0 errors** (with `pb_excel_layout` installed) |
| `pb_excel_layout` (26 methods) | — | **0 failed, 0 errors** (final run after the last Python change) |

| # | Case | Result |
|---|---|---|
| 1 | DS-2 proof. Workbook with an Excel-made chart (chart style + colour parts) and a text box: openpyxl load+save **loses** `xl/charts/style1.xml`, `colors1.xml`, the chart's relationship part and the text box; `fill` keeps every member in the same order, only `xl/workbook.xml` + the sheet change. NOTE: openpyxl 3.1.2 keeps a chart/picture of its OWN making — DS-2 holds for what real Excel writes (DS-5) | PASS (t01) |
| 2 | Headings + 3 cols × 50 rows at B6: values, types, positions exact; rows 1–5 byte-identical XML; cells left (A) and right (F formulas) kept; `<dimension>` A1:F59 | PASS (t02) |
| 3 | First data row bold / `#,##0.00` / `dd/mm/yyyy` → every row carries those style ids; dates read back as dates. A date column with no date style is readable text (not 46000) | PASS (t03, t02) |
| 4 | 50 rows then 10: rows 17–59 of B–D empty, A and F kept; 0 rows → headings only | PASS (t04) |
| 5 | `=SUM(Data!C:C)` on another sheet with a stale cached 999 and an Excel-style `calcPr`: `fullCalcOnLoad="1"` set (calcId kept); `calcChain.xml` + content type + relationship gone; opens in openpyxl; no `calcPr` → inserted in schema order. **Recalculated by LibreOffice (headless) to the new total 55,005**, with LibreOffice set to "recalculate on load: always" — its default ignores the flag and keeps 999 (DS-6). Not opened in Microsoft Excel | PASS (t05) — LibreOffice verified; Excel structural only |
| 6 | Excel table at the heading row: B6:D7 → B6:D26 + autoFilter, names = headings, openpyxl reads the new ref; 4-column table vs 3 columns → ref left + note, names under written headings synced; table headings inside the area → refused in words | PASS (t06) |
| 7 | Pivot cache → `refreshOnLoad="1"`, other attributes untouched | PASS (t07) |
| 8 | `.xlsm` with `vbaProject.bin`: bytes + CRC identical, `has_macros`, `.xlsm` type, macro note in words (product name, no "Odoo") | PASS (t08) |
| 9 | R1 over a rich workbook (Excel-made chart, picture, defined name, conditional format, pivot cache, calc chain, macros): only `[Content_Types].xml`, `xl/_rels/workbook.xml.rels` (calcChain lines only — compared canonically), pivot cache, `xl/workbook.xml`, the sheet change; same order, compression, dates | PASS (t09) |
| 10 | Zip bomb (81 MB unpacked), billion-laughs DTD, `../` member, 11 MB file, password-protected, `.xls`, CSV renamed `.xlsx`, `.csv` → each refused with its own plain sentence through the facade; no traceback, no "Error"/"zip"/"Odoo" in the text | PASS (t10) |
| 11 | `=1+1`, `+44…`, `-5 days`, `@SUM` written as text (no `<f>`); Vietnamese and emoji kept; control characters stripped (tab/newline kept); None no cell; NaN not written; 40,000 chars → 32,767 + note; bool; datetime without date style as text | PASS (t11) |
| 11b | Set-up reading: sheet names, 20 × 12 grid, bold look, merged ranges, table suggestion, team-heading-row suggestion (B4, headings off), empty sheet A1; merged in the way, missing sheet, bad cell, too wide → refused | PASS (t11b) |
| 11c | 1904 calendar; rows/cells written without numbers | PASS (t11c) |
| 12 | C1 on a saved view: exact shape and types, real totals (4,800); "each in its own money" with two currencies → ONE flat table with a `Currency` column; cut rows and unconverted amounts said in the note | PASS (t12) |
| 13 | C2: registry entry + props, the Explorer renders it; a stub source (`_pbxl_table` patched onto contacts) works for a user WITHOUT the Explorer gate: list, try, save (`b6` → `B6`), download; broken layout → plain standard Excel + reason; a model without the contract is refused | PASS (t13) |
| 13b | X2/X3/X5 through the facade: inspect, peek, save, list, download (fresh figures, last used), rename, change place, refusals; replace keeps the sheet → replace without the sheet says so → download falls back → pick the sheet again → works; a refused file never replaces a good one; delete | PASS (t13b) |
| 13c | Merged cells refused at set-up with the range; empty name; 20-layout cap and `can_add` | PASS (t13c) |
| 14 | Scheduled send in my layout: drawer lists it; saved with it; mail off → `email_off` as today; mail on → two readers held to different divisions each get THEIR file with only their department; broken layout → each gets the Explorer's standard workbook, history `layout_failed` "Sent as the standard Excel — … “Data” is not in this file …", summary "Sent to 2 of 2"; standard choice clears; a layout of another view refused | PASS (t14) |
| 15 | Hook behaviour-neutral: `pb_explorer` suite = baseline (101, 0 failed), `test_08_facade_never_writes` passes; core `_pbx_attachment` returns the standard triple unchanged; with no layout this module hands it back too | PASS (t15 + suite) |
| 16 | A reader who cannot open the (private) view — another analytics user, and a user without the Explorer gate — cannot list, inspect, try, detail or download its layouts (even a shared layout); the ORM shows them nothing. On a shared view the other analytics user may list and download a shared layout but never rename/delete/replace it; a private layout stays private | PASS (t16) |
| 17 | Browser walk (Chrome MCP), seeded local copy (40 people, 3 runs), Insights hub › Explorer tab, 1440 then 1280 px, English then Vietnamese, console clean (only the local copy's unrelated brand-icon manifest warning): disabled button + "Save this view first" → save view → empty state → set-up dialog → drop the board pack (DragEvent with the real file bytes — DS-9) → their sheet, area lit, size chip → click B6, headings off → **Try it** (download + success line, step 3) → **Save** → count badge → **Download in my layout** (file checked: title rows, team headings and "Share of total" formulas kept, figures under their headings, only the sheet + workbook flag changed) → owner menu → **Send regularly › Send as › Board pack** → saved, card "In your layout “Board pack”", Change keeps the choice → unreadable file state → (vi, 1280) change-place dialog, merged-cells state (amber, sentence, Try/Save blocked) | PASS |
| 18 | `.pot` exported by the platform from the installed module; `vi_VN.po` + `id_ID.po` 156/156; parse gate with the platform reader: every code term reaches the screen (module line, `odoo-python`/`odoo-javascript`, `code:` occurrence); placeholders match; no "Odoo" in any msgstr. Static gates: no emoji, no bracketed plurals, no `%%`, no gradients, no CSS min/max, no "Odoo" in visible strings | PASS (t18) |
| R6 | Silent install: no job, no template, no record, no setting | PASS (t19) |

Polish after the last suite run (looks only, verified on screen or trivial): white text on dark fills in the preview, the schedule chip aligned with the card text, a shorter grid on screens under 860 px high.

## 3. Rails — evidence

| Rail | Evidence |
|---|---|
| R1 byte-identical | t01, t09 (CRC, order, compression, dates); walk file: only the sheet and `xl/workbook.xml` changed |
| R2 only what the reader may see | the table is always built by the source as the caller (`_pbxl_table` → `pb.explorer._export_rows` with the caller's companies/divisions); scheduled sends rebuild it per recipient through the facade the core already narrowed (t14); every facade call checks the source gate + read access (t16) |
| R3 upload hardening | t10; XML parsed with `resolve_entities=False, no_network=True, huge_tree=False, load_dtd=False`; any DTD refused before openpyxl reads the file |
| R4 never a formula, macros never run | t11 (inline strings only), t08 (vbaProject byte-identical, note shown) |
| R5 never blocks a send | t14 (`layout_failed` + standard file); t13/t13b (download falls back with the reason) |
| R6 silent install | t19; no cron, no mail template, no data file |
| R7 white-label, plain words, vi + id | file names via `product_label(env)` (`payobook_board_pack_2026-11-22.xlsx`), t18 gates, Vietnamese walk |

## 4. Edits inside `pb_explorer` (the only existing files touched)

| File | Lines (branch) | Edit |
|---|---|---|
| `pb_explorer/__manifest__.py` | 36-39 | version 19.0.2.8.0 → 19.0.2.9.0 + comment |
| `pb_explorer/models/pb_explorer_schedule.py` | 444-445, 452, 461-470 | in `_pbx_mail_for`: `filename, data, mimetype = self._pbx_attachment(user, (filename, data, XLSX), explorer=explorer, spec=spec)`; the attachment's `mimetype` now comes from that triple; new method `_pbx_attachment(self, user, standard, explorer=None, spec=None)` returning `standard` unchanged |
| `pb_explorer/static/src/js/explorer.js` | 1617-1626, 1976, 1990-1993 | getters `excelLayoutButton` (registry lookup, `null` when absent) and `excelLayoutWhy` ("Save this view first" while no saved view is open); `...this.scheduleExtraVals(f)` spread into the `schedule_save` vals; new no-op method `scheduleExtraVals(_form)` |
| `pb_explorer/static/src/xml/explorer.xml` | 46-52 | after *Download Excel*: `<t t-if="excelLayoutButton" t-component="excelLayoutButton" sourceModel="'pb.explorer.view'" sourceId="…active view id or 0" disabledReason="excelLayoutWhy"/>` |

`pb_explorer.py` untouched. No JS parameter named `s`.

**Spec deviations (small, deliberate):**
- The hook's signature is `_pbx_attachment(user, standard, explorer=None, spec=None)`, not `_pbx_attachment(user)`: the standard workbook must still be built where it is (the email's headlines come from the same answer), so the hook receives it and may replace it; `explorer`/`spec` are the recipient-scoped facade and question it must reuse.
- `scheduleExtraVals(form)` — one extra no-op seam in `explorer.js`, needed so the "Send as" choice reaches `schedule_save` without copying the Explorer's save method.
- The `Currency` column is emitted only where the Explorer gives one block per currency ("each in its own money" or several monies), not in group-currency mode — in the walk an always-on Currency column pushed every figure one column right of the team's own headings (owner question 1).
- Dates are written as serials only when the template cell's style is a DATE format (stricter than "has a style"), so a number style never shows a date as 46000.
- Rows below a shorter result keep their formatting (values removed) instead of the cells being deleted, so a pre-formatted table keeps its borders.
- Record rule is tighter than the Explorer's: through the ORM people reach only their OWN layouts; shared ones only through the facade after the view check (the file may hold last month's figures). No company rule: the view the layout belongs to has none.

## 5. Contracts for phase R and wave 2

**C1** — implemented on `pb.explorer.view` exactly as the ledger says (`_pbxl_table()` → `{title, columns[{key,label,type}], rows, truncated, note}`), as the calling user. Two OPTIONAL extras a source may add (used when present):
- `_pbxl_require()` — the source's own gate, called before anything. Phase R: add it to `pb.report.definition`.
- `_pbxl_standard()` → `(filename, bytes)` — the source's own standard Excel used when a layout cannot be used. Without it the board makes a plain workbook (title, headings, rows; text never a formula).

The board refuses any model without `_pbxl_table`, abstract or transient models, and checks `check_access('read')` on the record as the caller.

**C2** — `registry.category("pb_excel_layout").add("button", PbExcelLayoutButton)`, props `{sourceModel: String, sourceId: Number, disabledReason?: String}`. With `sourceId` 0 or a `disabledReason` it renders disabled and shows the reason. Self-styled (`.pbxl-*`), same size as the Explorer's toolbar buttons.

Facade `pb.excel.layout.board`: `inspect, peek, try_it, save, list_for, detail, update, rename, share, remove, replace_file, download` (file problems come back as `{ok: False, msg}`).

## 6. Deploy notes

- Ship `pb_explorer` (19.0.2.9.0) and the NEW `pb_excel_layout` (19.0.1.0.0) together: `-u pb_explorer`, then `-i pb_excel_layout` on payobook, payobook_template, p0clone, rize, sudima (module-sync rule; it installs silently).
- New module install → "risky" ritual (backups, rehearsal). No stored data rewritten, no pay figure touched, no job added.
- Assets changed in both modules → asset purge + `web.assets.version` bump.
- Needs `openpyxl` + `lxml` only (already used). LibreOffice not needed.
- After go-live: Insights › Explorer shows "My Excel layout" beside Download Excel (disabled until a view is saved); the Send regularly drawer shows "Send as".
- Run the PO parse gate over the two new `.po` files.

## 7. Design self-score ("extreme WOW, intuitive, out-of-this-world experience, best in class")

- Hero (X2): their own sheet with their bold and fills, Excel-like letters, rows and sheet tabs; one click sets the place; the area lights up live with an outline sized to the real result; headings preview in place; values about to be replaced struck through; size chip. Smart default finds the team's own heading row (the walk's pack lined up first time). **9/10**
- Zero dead-ends: drop / reading / unreadable / merged in the way / table found / sheet missing after replace / no figures yet / cap / fallback with reason — each says why and what to do. **9/10**
- Motion and keyboard: pop-in list, area transitions, step strip; arrows move the start cell, Enter/Space opens the file picker, Escape closes; reduced motion respected. **8/10**
- Locked palette, Lucide only, no gradients, no emoji, quiet disabled state with its reason. **9/10**
- Gap to 10: no preview of the filled VALUES inside the grid (headings only).

## 8. Owner questions (plain)

1. When a view shows "group currency", the file has no Currency column, so the figures sit right under your team's own headings. When a view shows "each in its own money", a Currency column is added. If someone later switches a view between the two, the columns move by one. Is that fine, or should every money report always carry a Currency column (never moves, but your file must leave room for it)?
2. People who open the file in **LibreOffice** instead of Excel will see old totals in their own formulas until they press "recalculate" — LibreOffice ignores the "recalculate when opened" mark that Excel follows. Should the set-up screen say this in one line?
3. The Explorer gives at most the 24 largest rows per view (the rest are reported as "left out"). For a board pack that must list every department of a large company, should the Excel layout be allowed to take all rows? (That is a change to the Explorer, not part of this step.)

## 9. Left for later

- A filled-values preview inside the mini grid.
- Several tables per layout, column mapping, `.xls`, Google Sheets (binding non-goals).
- Microsoft Excel was not driven automatically on the shared Mac; recalculation was proven with LibreOffice forced to recalculate.
- Phase R: implement `_pbxl_require` (and `_pbxl_standard` if it has one) on `pb.report.definition` and render the C2 button.
- Learning: the Explorer lesson replica shows no toolbar buttons and the `ex-head` anchor is unchanged — no lesson change needed; a "Use your own Excel layout" lesson can join the Insights lessons later.

## 10. Gotchas → ledger rows

- DS-5 | openpyxl 3.1.2 KEEPS charts/pictures it made itself; on load+save it loses what real Excel adds: chart style/colour parts (`xl/charts/style1.xml`, `colors1.xml` + rels) and drawing shapes/text boxes, and rewrites the drawing. openpyxl also writes `fullCalcOnLoad="1"` itself | prove DS-2 with an "Excel-made" fixture (`pb_excel_layout/tests/fixtures.py` `excel_like_chart`); strip the flag from fixtures to test it.
- DS-6 | LibreOffice ignores `fullCalcOnLoad`: its default for Excel files is "never recalculate on load" (`OOXMLRecalcMode` 1) | to verify a recalculation locally, give soffice a throwaway profile whose `registrymodifications.xcu` sets `/org.openoffice.Office.Calc/Formula/Load` `OOXMLRecalcMode` = 0.
- DS-7 | `upd_p6_t_tpl` copies are 53 modules behind `origin/19.1` (2026-11-22): the registry fails ("pb.list.layout has no table", `res_company.pb_weekday_location_defaults`) | `-u` every installed module whose manifest version differs, once, no tests, before any suite; for a baseline, `git archive origin/19.1 <module>` into a scratch addons folder placed FIRST on `addons_path`.
- DS-8 | Under machine load ~40 the first `web.assets_web.min.js` build exceeded the threaded server's 120 s real-time limit and was killed (blank page) | start walk servers with `--limit-time-real=1800 --limit-time-cpu=1800` and warm the bundle with one curl.
- DS-9 | Chrome MCP `upload_file` refuses files outside its workspace roots (the session scratch folder is outside) | dispatch a `drop` DragEvent with a `File` built from the bytes (exercises the real drop path).
- DS-10 | With `-u <one module>`, post-install tests of other tagged modules did not run (`--test-tags /a,/b` ran only `/b`) | put every module whose suite you need in `-u`.
- DS-11 | A template sentence with `<t t-esc>` inside is split into fragments for translators | build such sentences in JS with `_t("… %s …")`; JS `_t` terms of any module reach other modules' screens through the global translation fallback (the Explorer's "Save this view first" is translated from this module's `.po`).

## X-b — owner rulings of 2026-11-22 (every row, fixed Currency column, recalculate note)

**What changed**
1. **Every row in a filled layout.** `_pbxl_table` on `pb.explorer.view` now asks the Explorer for every row of the view, up to the Explorer's existing export cap (20,000); when the cap is hit the table's note says "Only the largest 20,000 rows are in the file; N more were left out." The on-screen chart, *Download Excel* and the CSV still give the largest 24 + their own note, unchanged. Scheduled sends in a layout get every row too, still built as each recipient. (Answers owner question 3.)
2. **A Currency column on every money report**, always second, in both "group currency" and "each in its own money" — the columns never move. Counts (headcount, FTE…) have none. The set-up screen's outline ("N columns × M rows from B6") counts it, because it is read from the same table. (Answers owner question 1; replaces the X deviation "Currency only in own-money mode".)
3. **One quiet line on the set-up screen**, under the coaching line: "Totals and charts in your file refresh when it is opened in Excel. Some other spreadsheet programs need “Recalculate” pressed." — vi + id. (Answers owner question 2.)

**Exact edit inside `pb_explorer`** (one read-only seam, no write, version kept at the branch's unreleased 19.0.2.9.0):
| File | Lines | Edit |
|---|---|---|
| `pb_explorer/models/pb_explorer.py` | 554-560 | new `@api.model _pbx_series_cap(self)` returning `_MAX_SERIES` |
| `pb_explorer/models/pb_explorer.py` | 665 | in `_clean_spec`: `'limit': min(max(1, limit), self._pbx_series_cap())` (was `_MAX_SERIES`) |

`pb_excel_layout` overrides `_pbx_series_cap` on `pb.explorer` to return `_EXPORT_CAP` only when the context carries `pbxl_every_row` (set by `_pbxl_table_for`, which also sets the spec's `limit` to that cap). Nothing else ever sets the key, so every other caller gets 24 exactly as before.

**Tests (local copy rebuilt the same way: `upd_p6_t_tpl` + the 53 stale modules)**

| Suite | Result |
|---|---|
| `pb_explorer` (101) | 0 failed, 0 errors — equal to baseline; `test_08_facade_never_writes` passes |
| `pb_excel_layout` (29) | 0 failed, 0 errors |

| # | Case | Result |
|---|---|---|
| 19 | A view split by department with 32 departments: the layout table has all 32 rows, no note; `query` still 24 series + 8 truncated, `export_xlsx` and `export_csv` still 24 rows + 8 truncated, the plain series cap still 24; *Download in my layout* file has 32 rows; a scheduled send in the layout attaches 32 rows (as the recipient); with the cap patched to 10 → 10 rows + "Only the largest 10 rows are in the file; 22 more were left out." | PASS (test_t19_every_row_in_my_layout) |
| 20 | Net pay in "group currency" and in "each in its own money": identical column lists, `Currency` second, every row names its money; a headcount view has no Currency column; the set-up answer's column count = the table's | PASS (test_t20_currency_column_never_moves) |
| 21 | The recalculate line in English, Vietnamese and Indonesian (exact text from the shipped `.po`), and the dialog renders it | PASS (test_t21_recalculate_note_in_three_languages) |
| 18 | `.pot` re-exported, vi + id 157/157, parse gate | PASS |

**Browser re-walk** (1440 px, seeded copy, console clean except one error caused by the walker's own bad test URL): saved view → My Excel layout → drop the board pack → default start now B6 with headings off (the team's own heading row was found), outline "4 columns × 8 rows from B6" counting the Currency column, the recalculate line under the coaching line, dark heading fill readable. The 32-row case was proven in test 19 (the seeded walk data has 8 departments).

**Note for the deploy agent:** a filled layout of a view split by a large dimension (thousands of people) now reads all rows — still one query, capped at 20,000.
