# DOCSTUDIO PDFFIX — report (2026-11-24 / 25)

**Outcome: diagnosis confirmed; the fixed PDF engine was proven side by side but NOT switched in.**
The handover's stop rule fired: with the new engine a rize payslip gets worse, and the cause is in
the payslip modules (outside the studio). Nothing on the live server changed: no install, no
restart, no lock, no module upgrade. Downtime 0 s. Code for the studio's own part is ready on
branch `docstudio-pdffix` (not deployed).

## 1. Diagnosis — confirmed

- Live engine: `/usr/bin/wkhtmltopdf` = Ubuntu package `wkhtmltopdf 0.12.6-2build2`, "0.12.6"
  without patched Qt. Odoo finds it through the service PATH
  (`/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin`, init script) — `/usr/local/bin` is LAST, so a
  `.deb` install to `/usr/local/bin` would NOT be picked up (and the upstream `.deb` declares
  `Conflicts: wkhtmltopdf`, i.e. installing it removes the Ubuntu package).
- Minimal page with `--header-html`/`--footer-html`: the live engine prints
  "The switch --header-html, is not support using unpatched qt, and will be ignored" and the PDF
  has no header/footer; the patched build prints "HEADER …" and "FOOTER Page 1 of 4".
- Patched build: official release `wkhtmltopdf/packaging` `0.12.6.1-3`, asset
  `wkhtmltox_0.12.6.1-3.jammy_amd64.deb` (no noble build exists), 17,326,782 bytes, sha256
  `4f723b2691ad8638a9df960e0421d346d7315083e3583a334f33362280ddba15`. **The release publishes no
  checksum** (none in the release text, no digest on the asset, none on wkhtmltopdf.org); instead
  two independent downloads (server and Mac) gave the same sha256 and the package's own md5sums
  all check. Unpacked only (`dpkg-deb -x`), never installed: `--version` = "wkhtmltopdf 0.12.6.1
  (with patched qt)", no missing libraries on Ubuntu 24.04, binary is self-contained. Kept on the
  server at `/odoo/backups/docstudio-pdffix-20261124T1020Z/engine/` with `SHA256`.

## 2. How it was proven (nothing stored)

`pdffix/pdffix_side_by_side.sh` + `pdffix/pdffix_probe.py`: one server shell per database per
engine; only that process's PATH differs (`/usr/bin/wkhtmltopdf` vs the unpacked patched copy);
every record made (saved report, Explorer view) is rolled back. The script checks the site
answers 200 and the service PID is unchanged before and after each shell — **a first run on
24 Nov was invalid because another deployer restarted the service mid-run** (the engine fetches
page styles from the running site; with the site down it silently makes unstyled PDFs). The run
used for this report: payobook + rize + sudima on 24 Nov 10:22–10:49 UTC, payslips re-run on
rize + payobook on 25 Nov 05:47–05:51 UTC after the WFSETUP P10b release (same result).
`pdffix/pdffix_compare.sh` (pages, fonts, characters, page-number and "Printed on" lines) and
`pdftoppm` pictures on the Mac. Tenant PDFs stay on the server
(`/odoo/backups/docstudio-pdffix-20261124T1020Z/`, `750 odoo`); local copies were deleted.

## 3. Before / after per document (old engine → patched engine)

| Document | DB | Pages | Text selectable | Letterhead + page number | Verdict |
|---|---|---|---|---|---|
| Letter, Clean, Vietnamese certificate | payobook | 1 → 1 | no → yes | none → yes ("Trang 1/1") | better; **header crowds the date/heading** (fixed in code, §5) and **space before bold words lost** (§4) |
| Letter, Clean, 2-page (30 paragraphs) | payobook | 2 → 2 | 0 → 4,238 chars | none → "Page 1/2", "Page 2/2" | better; file 1,029 KB → 127 KB |
| Letter, Classic serif | payobook | 1 → 1 | yes → yes | none → yes | better |
| Letter on plain paper | payobook | 1 → 1 | no → yes | none → none (as designed) | better |
| Letter stored 2026-08 (old letter engine layout) | payobook | 1 → 1 | 6 → 494 chars | none → yes | better |
| Contract document | payobook | 1 → 1 | yes → yes | none → yes | better (`p2`) |
| Report PDF, 4,581 rows, 8 columns | payobook | 134 → 154 | yes → yes | none → **exactly one "Page x / 154" and one "Printed on" on all 154 pages** | better; right-most column inside the page on p1 and p77 (`p3`) |
| Report PDF, short, plain paper | payobook | 1 → 1 | yes | none → "Printed on … · Page 1 of 1" | better |
| Explorer view PDF | payobook | 2 → 2 | yes | none → 2/2 page numbers + "Printed on" | better |
| Payslip "Print Payslip (Themed)" (pay run board, My Payobook) | payobook, rize | 1 → 1 | **no → yes** | none → none (own layout) | **layout changes: logo drops under the name, grid lines on every row, bigger rows; net pay bar no longer right-aligned** (`p5`) |
| Payslip, 3 slips of a run | payobook, rize | 3 → 3 | no → yes | — | same change as above |
| Payslip "PaySlip" (standard, Print menu) | payobook, rize | **1 → 2** | yes | none → company header + "Page 1/2" | **worse: header pushes the net-pay block onto page 2; the logo prints twice** (`p4`) |
| Payslip "Vietnam PaySlip" (Print menu) | payobook, rize | 2 → 2 | yes | none → company header + page numbers | changed, not worse |
| Letter certificate en + vi | rize, sudima | 1 → 1 | no → yes | none → yes | better (pictures on server only) |
| Payslip | sudima | — | — | — | **not tested: sudima has no payslip** |

## 4. Fonts after the fix (letters; report PDFs print DejaVu since B)

| On-screen font | Before (live today) | With the patched engine |
|---|---|---|
| Clean (default) | drawn as shapes: no text, ~75 KB/page | Roboto embedded, words selectable; **some spaces just before a bold word print almost zero-width** ("vị tríConsultant" on paper; the text layer keeps the space) |
| Friendly | drawn as shapes | Open Sans embedded; **the space before a bold word is lost on paper AND in the text** |
| Modern | drawn as shapes | Montserrat embedded; same as Friendly |
| Classic serif | DejaVu Serif, text fine | unchanged on the shipped letters; the effect shows at 11 px in a test sheet |

The lost space is the engine's own text spacing at the boundary to bold/italic text (proved on a
4-font × 6-size × 4-sentence sheet: ~15% of boundaries squashed in every font; `--disable-smart-
shrinking` halves it, font hinting has no effect, `&nbsp;` or moving the space inside the bold
does not cure it). Vietnamese bold names: tone marks all correct; spacing as above
(`p6`, `p7`). The font choices B and A2 narrowed were not widened. Could be reopened once the
engine is in: Friendly/Modern for report PDFs (they now embed real text) — but only after the
spacing issue is addressed.

## 5. Code (branch `docstudio-pdffix`, NOT deployed)

- `pb_doc_studio` 19.0.1.1.0 → **19.0.1.2.0**: with the letterhead on, a letter's top margin and
  header spacing become paper top + 12 mm (normal 52/52 — the company's own A4 setting — narrow
  44/44, wide 58/58), passed as `data-report-*` from `report.pb_doc_studio.report_doc_letter`
  (covers letters, offer letters, certificates, contract documents). Measured on the server: the
  header bottom sits at `margin_top − header_spacing + ~39 mm` for a logo + 5-line address, so
  35 mm spacing overlapped by ~4 mm; 52 leaves ~13 mm. Plain paper unchanged.
- `pb_report_pdf` 19.0.1.0.0 → **19.0.1.1.0**: letterhead margins 40/35 → 52/52 (page estimate
  follows the constant).
- Tests: `test_09_page_design` (+ margins 44/52/58, none on plain paper), `test_06_letterhead_on_
  and_off` (52/52). No new user-visible strings (no .po change); no vendor word added.
- Harmless with the old engine except 12 mm more space above letters with a letterhead — ship it
  only together with the engine switch.

## 6. Not fixed / not verified — stated plainly

1. **Not switched**: the PDF engine on the server is still the old one; no PDF prints the company
   letterhead, footer or page numbers, and Clean/Friendly/Modern PDFs still have no selectable
   text. Both owner-visible faults remain.
2. **Blocker (outside the studio, not edited)**: `om_hr_payroll` standard payslip 1 → 2 pages
   with a doubled logo; `pb_hr_payroll_formula` themed payslip layout changes (the engine with
   patched Qt has an older page layout without the modern box layout the themed slip uses). Both
   on rize. Owner decision needed: fix those two payslip layouts first (their owners), or accept.
3. Space before bold words in Clean/Friendly/Modern (§4) — not fixed.
4. Local suites: green (§8).
5. Browser walk on payobook.com: not done (nothing changed live).
6. sudima payslip: none exists to test.

## 7. Switch recipe for the next window (not executed)

Keep the Ubuntu package; divert its binary and link the patched one (no conf change):
```
sudo install -D -m 755 /odoo/backups/docstudio-pdffix-20261124T1020Z/engine/wkhtmltopdf-0.12.6.1-patched /opt/wkhtmltox-0.12.6.1-3/bin/wkhtmltopdf
sudo service odoo-server stop
sudo dpkg-divert --local --rename --divert /usr/bin/wkhtmltopdf.ubuntu --add /usr/bin/wkhtmltopdf
sudo ln -s /opt/wkhtmltox-0.12.6.1-3/bin/wkhtmltopdf /usr/bin/wkhtmltopdf
sudo service odoo-server start      # log: "Will use the Wkhtmltopdf binary at /usr/bin/wkhtmltopdf"
```
Rollback: `sudo service odoo-server stop; sudo rm /usr/bin/wkhtmltopdf; sudo dpkg-divert --local
--rename --remove /usr/bin/wkhtmltopdf; sudo service odoo-server start`. Note the running service
caches only the PATH (`/usr/bin/wkhtmltopdf`), so any other Odoo process on the box (test servers)
picks up the new engine at its next PDF.

## 8. Local tests

Local copy of `upd_p6_t_tpl` (`docstudio_pdffix_t`), `-u all -i pb_doc_studio,pb_report_pdf`, then
`-i pb_report_builder` (soft dependency the report-PDF suite needs), then `-u pb_doc_studio,pb_report_pdf
--test-tags /pb_doc_studio,/pb_report_pdf`: **pb_doc_studio 43 tests, pb_report_pdf 21 tests, 0 failed,
0 errors** (`test_03` skipped: no PDF engine on the Mac, as in W2).
