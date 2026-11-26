# DOCSTUDIO — close-out (Report and document studio), 2026-11-26

Department started 2026-11-22 from the owner's ticked lines on the Workday gap study (900, 881, 961,
830, 204 without e-signature, 920). Phased build (Fable designs, Opus builds and tests). **Everything
below is LIVE on all five databases** (payobook, payobook_template, p0clone, rize, sudima); abm never
touched. Last release: close-out L + Z, commit `06defa5ae`, 26 Nov 02:45–02:53 UTC (488 s down).
Reports: W1A / W1B / W2 / PDFFIX / CLOSE_L / CLOSE_Z / CLOSE_DEPLOY in this folder; ledger
`DOCSTUDIO_LEDGER.md` (main checkout, not in git).

## 1. What shipped, per study line (versions live on all five)

| Line | What the customer can do now | Module(s) and live version |
|---|---|---|
| **900** Build your own report | Insights › Build a report: pick what each row is, add fields, filter, group, total, save, share, Excel. HR officers get the Insights button with only this tab. | `pb_report_builder` 19.0.1.1.1 |
| **920** Fill my own Excel layout | Upload their own workbook, click cells, map fields, "Try it", save; works from a built report and a saved Explorer view; "Send regularly" can send it. | `pb_excel_layout` 19.0.1.0.1, `pb_explorer` 19.0.2.10.0 |
| **830** Document studio | Settings › HR › Documents: every letter in one gallery, the designer (wording, fields, "Show only when…", preview with a real person, language versions, page design, a company's/country's own copy, put back the built-in wording). | `pb_doc_studio` 19.0.1.5.0 |
| **961** Every document in the designer | Offer letters (Hiring group, preview with a real offer, language of the letter in the Hiring offer panel) and certificates (My Payobook) in the designer; every caller honours the letter's language; built-in offer pay table in vi/id. | `pb_doc_studio_hiring` 19.0.1.2.0, `pb_doc_studio_me` 19.0.1.0.1, `pb_hiring` 19.0.2.23.9 |
| **204** Contract documents per country (no e-signature) | Shipped wording for generic / Vietnam (two-language) / Indonesia (two-language), "Sample wording…" note on screen only; contract panel › Contract document: preview, Download PDF, Save to documents (versions). | `pb_doc_contracts` 19.0.1.2.0 |
| **881** Design the PDF of a report | PDF button on built reports and saved Explorer views: paper, letterhead, font (Clean / Classic serif), text size, column widths, heading, real first page; "Send regularly" can send the PDF. | `pb_report_pdf` 19.0.1.1.1, `pb_report_pdf_send` 19.0.1.0.1 |
| Lessons | Six lessons (Build your own report, Fill my own Excel layout, Design a letter, Offer letters and certificates, Contract documents per country, Design the PDF of a report), English + Vietnamese, in the HR and owner paths; PayAI knows them. | `pb_learn` 19.0.20.10.0, `pb_payroll_ai_insights` 19.0.3.13.2 |
| Leftover | The three old analytics PDFs that never had a page design are off the Print menu and the old dashboard's Export button. | `pb_hr_payroll_analytics` 19.0.1.4.1 |

**PDF engine (PDFFIX, 2026-11-25):** the server prints with wkhtmltopdf 0.12.6.1 **with patched Qt**
(was the Ubuntu build): every PDF now carries the company letterhead, footer, page numbers and real
text. Payslip layouts were adjusted to keep their size (`om_hr_payroll` 19.0.1.8.7,
`pb_hr_payroll_formula`, `pb_hr_payroll_vietnam` 19.0.1.2.6, `pb_hr_fullandfinal` 19.0.1.4.2,
`pb_training`). **Rollback** (templates work on both engines):
`sudo service odoo-server stop; sudo rm /usr/bin/wkhtmltopdf; sudo dpkg-divert --local --rename --remove /usr/bin/wkhtmltopdf; sudo service odoo-server start`.
The patched engine is kept at `/odoo/backups/docstudio-pdffix-20261124T1020Z/engine/`.

## 2. Owner rulings (all built)

| Date | Ruling |
|---|---|
| 2026-11-22 | HR officers get the Insights button, with only "Build a report" (no payroll tabs). |
| 2026-11-22 | Excel layout: every row is filled (up to the export cap); a fixed Currency column on money reports; a quiet "recalculate" line. |
| 2026-11-22 | A company's or country's own copy of a letter always wins; a person sees their own pay on their own document; the main wording may be in any language. |
| 2026-11-23 | Offer letter language: unknown → the hiring company's language; an explicit choice wins; the recruiter can choose before sending. |
| 2026-11-24 | View-only people on a contract download but do not file. |
| 2026-11-24 | Shipped contract wording carries "Sample wording. Have your own lawyer check it before you use it." on screen, never in a PDF or filed document. |
| 2026-11-24 | No extra fonts installed on the server (report PDFs offer Clean and Classic serif only). |
| 2026-11-26 | Hide the three broken analytics PDFs (do not build them). |
| (programme start) | Out of scope: 933 (charts board → Reports later), 414 (→ Performance later), e-signature, 953. |

## 3. Open items (for the owner / a later department)

1. **View-only on a contract cannot happen today.** Every role that can open a contract (HR officer,
   payroll officer, administrator) may also file documents, and every internal login may create a
   document through the My Payobook self-upload permission. The guard itself works (checked on the live
   code with a synthetic read-only reader: no Save button, the sentence shows, the server refuses). For
   the ruling to matter, two things would have to change: an Access role that reads contracts without the
   HR/payroll officer role, and the "may file" check reading a real filing permission rather than
   "may create a document" (which the self-upload rule gives everyone). Owner decision.
2. **No plain "HR officer" role on the Access screen**, and giving any role there goes to the owner for
   approval. The HR-officer check was therefore done on the live code with a synthetic person (Insights
   on, only Build a report, payroll screens refused, build + save + Excel work, contracts and pay
   refused with "You cannot see contracts. Ask your administrator for contract access."), not as a
   real signed-in HR officer.
3. **No Indonesian lesson text** (Learn is English + Vietnamese only).
4. **Report PDFs keep two fonts** (Clean, Classic serif). Friendly/Modern stay closed until a long
   report is proven in them on the server (`DOCSTUDIO_CLOSE_Z_REPORT.md` §5 has the test).
5. **Print about 15% larger** on the patched engine at the default sharpness; payslips and settlement
   are pinned to today's size; letters are not pinned (ledger DS-PF-7).
6. The space before bold text can still be squashed in a few report/table cells on the patched engine
   (letters are cured; DS-PF-4).
7. Candidate's web offer page still shows "Every month" / "One-off" in English; older lifecycle letters
   ("Probation passed", "Experience letter", …) have no vi/id names; "Make a copy for…" names the copy
   from the English name.
8. Phone width (about 400 px): the Documents gallery and a lesson work; **the PDF designer header is
   cramped** (the title is covered by the "Standard look" chip, "Save look" and "Download PDF" wrap to
   two lines, the settings take half the screen above a small preview). The PayAI button sits over the
   corner of a lesson's bottom bar.
9. rize: the nightly trial-period job fails on review 34 (pre-existing, seen since 22 Nov).
10. The PDF designer's page estimate is rough ("About 114 pages" for 84).
11. Deferred lines: 933, 414, e-signature, 953.

## 4. Traps for the next department

- Builders branch from the LATEST `origin/19.1`; other sessions ship hourly. Stage from a commit that
  contains current `19.1`, and refuse to go live if a live tree differs from it (`cd/cd_golive.sh`).
- A `-u` of a module that others depend on (pb_hiring, pb_explorer, pb_learn) cascades; expect rize
  "+4/+6 technical change notes" and re-activated jobs on copies — snapshot jobs and switch back.
- `pb_learn`'s generator can wipe `i18n/vi_VN.po`: compare the deployed file to the commit.
- Shell probes: a savepoint rollback leaves stale cache (flush before, invalidate after); Vietnamese PDF
  text needs NFC comparison; `res.company.country_id` is not stored.
- PDFs: check a PDF made by the live site, not the preview; a probe while the service restarts makes
  unstyled PDFs; "Clean" PDFs had no text on the old engine.
- Chrome MCP: a network-response file with a relative path lands in the main checkout root — move it.
- Giving a role on the Access screen may need the owner's approval: a check that needs a role cannot
  be finished alone; withdraw test requests (`biz.approval.engine.cancel`).
- Mail to `@example.invalid` is cancelled on payobook ("test or demo address"); still prefer it for
  throw-away logins.
