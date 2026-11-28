# DOCSTUDIO wave 2 — merge and deploy report (phases A1 + A2 + B, RISKY tier)

Merge-and-deploy agent, 2026-11-24 (UTC). Handover `DOCSTUDIO_W2_DEPLOY_HANDOVER.md` (+ W1A/W1B
handovers and reports, main checkout).

**Result: merged, pushed to `19.1` at `705cd8046`, LIVE on all five databases** (payobook,
payobook_template, p0clone, rize, sudima) on 24 Nov 02:40–02:48 UTC, **470 s down**. abm untouched.
Nothing failed; nothing restored. Every letter wording that existed before, every letter, the document
vault, every offer, every certificate and the mail queue are identical before and after on all five.
Two things were found that this release did not cause but that matter for it (§7c, §8 first bullet):
"Clean" PDFs carry no real text, and **the company letterhead, footer and page numbers do not print in
any PDF on payobook.com** (letters since at least 5 Oct, so also the new contract and report PDFs).

## 1. Merge

Full release worktree `gitlocal-worktrees/docstudio-w2` (the Mac had 19 GB free this time, so no
sparse checkout was needed), branch `docstudio-w2-merge` cut from `origin/19.1` @ `f472be965`.

| Commit | What |
|---|---|
| `b7905a4d7` | merge `origin/docstudio-a1` (`28d73889c`) `--no-ff` — no conflict |
| `c99ec5737` | merge `origin/docstudio-a2` (`fb290c9ea`) `--no-ff` — no conflict |
| `7bf7f106c` | merge `origin/docstudio-b` (`fb3c7b065`) `--no-ff` — no conflict |
| `18a46258c`, `705cd8046` | deploy scripts `docs/handovers/docstudio/w2/` (clones of `w1b/`) — **pushed and deployed** (`f472be965..705cd8046`, fast-forward, no force) |
| (this report) | report, evidence pictures, the font-check script |

- Every module tree in the merge is byte-identical to the tip its builder tested
  (`git diff origin/docstudio-<x> HEAD -- <module>` empty for all eight).
- The 9 commits `origin/19.1` gained since the branches' base (`84237cb87`) touch only `pb_form_studio*`,
  `tools/` and `docs/` — none of `pb_explorer`, `pb_report_builder`, `pb_doc_studio`, `pb_lifecycle`,
  `pb_hiring`, `pb_me*`. No extra re-run was owed; the suites below ran anyway.
- `pb_doc_studio`: A1 changed one TEST file only, manifest version unchanged (19.0.1.1.0), so the tree
  ships (server = repo) but the module is NOT upgraded.
- Static gates on the eight modules: 92 Python files compile, 24 XML files parse; PO gate (also on the
  server's own reader) 5 modules × vi_VN + id_ID, 0 empty, 0 vendor word; the vendor word in added
  user-visible strings: 0 (only `<odoo>` tags, comments and existing code paths). Unpushed diff scanned
  for passwords/keys: none; no `outputs/`, `SUDIMA/`, `RIZE/`.
- Dependencies of the new modules (`pb_contracts pb_doc_studio pb_employee_vault pb_excel_layout
  pb_hiring pb_me_letters web`) are installed on all five databases — nothing extra installed anywhere.

## 2. Post-merge tests (local, ONE database `docstudio_w2_t`, dropped with its file folder)

Copy of `upd_p6_t_tpl`, `-u all` on the merged tree, `-i pb_job_change, pb_me_letters, pb_pay_scales,
pb_form_studio, pb_form_studio_people, pb_employee_form_tidy, pb_report_builder, pb_excel_layout,
pb_doc_studio` (the live-like set), goldens, then `-i pb_doc_studio_hiring, pb_doc_studio_me,
pb_doc_contracts, pb_report_pdf` (the send bridge installed itself), goldens again, then the suites.
Quiet Mac (load ~4), nothing else running.

| Run | Result |
|---|---|
| install of the wave-2 modules | exit 0, 0 ERROR; `pb_report_pdf_send` auto-installed |
| A1 golden (`a1/golden.py`: 2 offer letters html/PDF-html/file name, employment certificate en/vi/id, salary certificate en/vi/id, template rows — 25 hashes) before vs after | **IDENTICAL** |
| F golden (`w2_golden.py`: 9 shipped letters rendered + every template row) before vs after | 9 letters **identical**, the 13 existing template rows **identical**; 3 new rows (14–16) = A2's three shipped contract wordings |
| Own suites (`-u` + `--test-tags`): pb_doc_studio 43, pb_doc_studio_hiring 22, pb_doc_studio_me 14, pb_doc_contracts 23, pb_report_pdf 21, pb_report_pdf_send 5, pb_report_builder 31, pb_excel_layout 29, pb_explorer 101 | **237 tests, 0 failed, 0 errors** |
| Baseline suites: pb_hiring 690, pb_contracts 79, pb_me_letters 16, pb_insights_hub 40 | 11 failed + 2 errors = **exactly the baselines**: the 10 pb_hiring entries of the A1 report (8 FAIL + 2 ERROR, same names), pb_contracts `TestCd1Contract360.test_01_payload_carries_every_top_level_key` (78/79), pb_insights_hub `test_the_lens_order_matches_the_mockup` + `test_the_feature_set_is_intact` (the known hub failures; the third recorded one is data-dependent and passed here, as in wave 1a) |

Skipped: `pb_report_pdf` `test_03` (3,000-row real PDF) — **wkhtmltopdf is not installed on this Mac**
(`which wkhtmltopdf` → none; nothing was installed). All other PDF checks in the suites fall back to the
HTML the engine would print. Real PDFs were checked on the server instead (§3 rehearsal, §5, §6).

**Combined checks no builder could do alone:**
- PDF button and Excel-layout button side by side (contracts C2 + B), local browser on the test copy:
  Build a report → example "People by country and contract type": "Excel", "My Excel layout", "PDF";
  both layout and PDF disabled with "Save the report first." → saved → both enabled ("Fill your own Excel
  file…", "Design the PDF of this report") → PDF opens the designer with the real first page (letterhead,
  table, "Printed on … · Page 1 of 1"), fonts offered: **Clean, Classic serif** only. Explorer toolbar:
  "Download Excel", "My Excel layout", "PDF", both disabled with "Save this view first". Console: 0 errors,
  0 warnings. A saved Explorer view → PDF designer + real PDF was done server-side (§3).
- A1's kept golden script: untouched letters byte-identical (above, and again in the rehearsal §3).
- Contract document (A2) and offer letter (A1) on the same page design: yes. Server side (rehearsal + verify probes) both go through the studio's
  page frame: the offer sample PDF (payobook, 207 KB) and the contract PDF (payobook 35 KB, rize 35 KB,
  p0clone 20 KB) are real PDFs with the letterhead/margins/signature settings of their page. Seen side by
  side in the browser (designer preview of the Vietnam offer letter and the contract panel sheet): same
  letterhead block (logo + company + country), same date line, same margins, same signature block. The
  only differences are by design: offers print in "Clean" (default page), contracts in "Classic serif"
  (A2's fix for the late web font). In the real PDF neither shows the letterhead — see §8 (pre-existing).

## 3. Rehearsal (hidden copy of rize, dropped after)

`w2_rh_rize` restored from the prep dump, hidden as a template, jobs and mail servers off BEFORE anything
else; 312 employees = live. Then `-i pb_doc_studio_hiring,pb_doc_studio_me,pb_doc_contracts,
pb_report_pdf,pb_report_pdf_send -u pb_report_builder,pb_explorer` with the staged trees first:

- exit 0 in **68 s**; 0 ERROR, 0 Traceback (warnings = the usual duplicate-label notices).
- Versions: the five new modules installed (19.0.1.1.0 / 19.0.1.0.0 ×4), pb_report_builder 19.0.1.1.0,
  pb_explorer 19.0.2.10.0, pb_doc_studio unchanged 19.0.1.1.0.
- **F golden: 9 letters IDENTICAL, 13 existing template rows IDENTICAL, rows added: 14 15 16. A1 golden:
  IDENTICAL (25 lines).**
- Counts: identical except **messages +6** (DS-W1A-4, the `pb_explorer` cascade renames 3 jobs + 3 server
  actions and the brand rewrite names them back) and the expected `x_` moves: +3 record rules, 3 new
  letter wording rows (`pb_doc_contracts.contract_template_generic/_vn/_id`), the new table and columns
  (PDF looks 0, schedule PDF column, offer language columns, contract-document columns, sample flag).
- Jobs: 20 re-activated on the copy (all were off there) — the usual cascade; on live the snapshot repair
  switches back any that were off. No new job row.
- Probe after, administrator, real PDF engine, rolled back: gallery 16 documents, first group "Hiring" (2),
  "Employment contracts" (3); 3 shipped contract wordings carry the sample flag, none has studio data;
  certificate preview ok; **contract document: "Sample wording" note on screen = yes, note words in the
  paper = no; real contract PDF (1 page, 35 KB): note in the PDF = no**; PDF designer on a saved built
  report (5 columns, fonts Clean/Classic serif) → real PDF 230 rows, 5 pages, no empty page, 1.7 s; on a
  saved Explorer view → real PDF 10 rows, 1 page; "Send regularly" PDF field present; 0 looks stored.
- Copy dropped (0 left).

## 4. Go-live

- Notes read first: no HOLD, every START closed; lock `/tmp/payobook-studio-deploy.lock` found empty
  (root, 23 Nov 09:46 UTC), nobody holding it (`flock -n` free) and no upgrade process running — treated
  as stale and said so in the START line; the go-live wrote its own name + time into it, the tries script
  removed it at 02:48. The orchestrator relayed the notice to the peer sessions (this agent cannot list
  sessions). Python libraries for the service user: lxml 5.2.1, openpyxl 3.1.2, PyPDF2 2.12.1.
- START 01:47 UTC. **Tries 1–5 (01:47–02:27) refused: signed-in activity on sudima** — one person
  (one address) worked on shift patterns and the overtime desk until 01:46 and again around 02:14, and an
  open tab polled the approvals inbox once a minute until 02:14:56. Try 6 (02:37:58): 15 quiet minutes on
  rize/payobook/sudima → backups ×5 → notes re-read (no HOLD, no new START) → stop.
- **Service stopped 02:40:28, port up 02:48:18 — 470 s down** (5 × ~70–80 s per database; the asset
  purge and job check ran between databases). DONE 02:48, NOTE 03:07 UTC.
- Staged with `git archive 705cd8046` of the eight trees; staged = commit; per-module scoped
  `rsync -a --delete` into `/odoo/odoo-server/addons/<module>/`; addons = staged after the copy.
  Previous trees of pb_doc_studio, pb_report_builder, pb_explorer kept for a roll-back.

| Database | `-i` 5 new `-u pb_report_builder,pb_explorer` | New modules | pb_report_builder / pb_explorer | Jobs active (total) before → after | Backup (right before the stop) |
|---|---|---|---|---|---|
| payobook_template | exit 0, 82 s, 0 ERROR | 5 installed | 19.0.1.1.0 / 19.0.2.10.0 | 40 (99) → 40 (99) | golive-payobook_template.dump 31.8 MB |
| p0clone | exit 0, 67 s, 0 ERROR | same | same | 48 (99) → 48 (99) | golive-p0clone.dump 32.3 MB |
| sudima | exit 0, 68 s, 0 ERROR | same | same | 91 (100) → 91 (100) | golive-sudima.dump 37.6 MB |
| rize | exit 0, 71 s, 0 ERROR | same | same | 91 (99) → 91 (99) | golive-rize.dump 46.5 MB |
| payobook | exit 0, 82 s, 0 ERROR | same | same | 58 (111) → 58 (111); job 156 off | golive-payobook.dump 84.3 MB |

`pb_report_pdf_send` was named in `-i` (it would also have installed itself). No job was re-activated
by the upgrade on any database, so none needed switching back; payobook_template's jobs are exactly as
before. Backups folder `/odoo/backups/docstudio-w2-20261124T013657Z/` (prep dumps + file-folder hard
links + go-live dumps + `previous-trees.tgz`). Per database: asset purge + `web.assets.version` =
`docstudio-w2-20261124T013657Z` + signalling row. Five sites warmed (200).

## 5. Verification

Evidence `/tmp/w2-20261124T013657Z/verify.txt` on the server.

- **Trees**: all 8 server trees byte-identical to `705cd8046` (hash of sorted file md5s, skipping
  `__pycache__`, `*.pyc`, `.DS_Store`).
- **Versions**: manifest = `latest_version`, state installed — 8 modules × 5 databases, 40/40.
- **Jobs**: id lists and active states identical to the prep snapshot ×5; no new job row; payobook job
  156 off.
- **Data** (the FORM STUDIO counts chain: employees, contracts, payslips, lines, users, groups,
  approvals, documents, …): identical on payobook, payobook_template, p0clone, sudima; **rize messages
  +6** (DS-W1A-4, as rehearsed). Expected moves only: +3 record rules, 3 new letter wording rows per
  database (`pb_doc_contracts.contract_template_generic/_vn/_id` — ids 14–16, on p0clone 62–64), the new
  table (0 PDF looks) and columns.
- **"Changes nothing until someone edits"** (prep → right before the stop → now, ×5): wording checksum
  (name/subject/body + active/company/type/sequence) of the 13 letter templates that existed —
  **identical**; their latest change date identical (16 Nov); letters identical (payobook 28, rize 1);
  vault documents identical (payobook 54, rize 18, p0clone 1); **offers identical** (payobook 6);
  certificates identical (0); mail queue identical (payobook 3,141, rize 1,053, sudima 20, p0clone 34,
  template 0 — same counts, same highest id: nothing mailed). Saved reports on payobook read 1 at verify
  time = the report the QA walk saved (§6), deleted again afterwards (0 now).
- **Sample-wording note**: the 3 shipped contract wordings carry the note flag ×5, none has studio data;
  on screen the contract document says "Sample wording" = yes; the note's words in the paper = no; **the
  real contract PDF text does not contain the note** (payobook, rize: Vietnamese copy; p0clone: English
  original) — checked with PyPDF2 on the server and again with `pdftotext` on a PDF fetched through the
  site (0 matches for "Sample wording", "lawyer", "luật sư", "Nội dung mẫu").
- **Probe as administrator** ×5 (rolled back): gallery 16 documents, first group "Hiring" (2),
  "Employment contracts" (3); offer preview with a real offer (payobook: 6 offers to pick, preview + true
  sample PDF 207 KB); certificate preview; contract document + real PDF (payobook, p0clone, rize; template
  and sudima have no running contract); PDF designer on a saved built report and a saved Explorer view,
  fonts offered **Clean / Classic serif only**, real PDFs (payobook: 4,581 rows → 84 pages in 9.1 s, no
  empty page; sudima 651 rows → 13 pages, one page with almost no text = the last page holding only the
  grand total row); "Send regularly" PDF field present; 0 looks stored after.
- **Compiled screen code** ×5: PDF button registered, both toolbars look it up, contract-document,
  hiring-bridge and send-bridge files in the bundle; the certificate bridge (styles + one template only)
  confirmed separately on payobook and rize (its file and its `.pbdx-uses` style are in the bundle).
- **Server log since the stop**: 0 ERROR from this release; 0 asset errors; upgrade logs 0 ERROR /
  0 Traceback; one ERROR + its Traceback = rize's nightly trial-period job "could not consolidate review
  34" (`'int' object has no attribute 'get'`) — the same line was logged on 22 and 23 Nov, not this
  release (finding §8). Rehearsal copies left: 0. Five login pages 200. "service processes: 2" = the live
  service + another session's QA server (`pbqa_workforce_20261124`), not ours.

## 6. Browser walk on payobook.com

As the **QA login** (qa.test@payobook.com, uid 6672, company Payobook Vietnam JSC) in an isolated
Chrome MCP context, signed in by the session call, signed out and the page closed after. Console:
**0 errors, 0 warnings** over the whole walk.

| Step | Seen |
|---|---|
| Settings › HR › Documents | 16 documents; chips "Hiring 2 … Employment contracts 3 …"; **Hiring group first** with "Offer letter" and "Offer letter — Vietnam" ("Printed when an offer is prepared in Hiring", "Used by 6 offers") |
| Offer letter — Vietnam | Fields Candidate / Job / Company / Pay / Dates with the real offer's values; pay lines table block; **"Preview with · An offer" — Ngo Thanh Tam, DEMO Territory Manager**; language picker "English (US) (their language) / Indonesian / Vietnamese"; preview page with letterhead, pay table, company and candidate signatures (`evidence_w2/w3_offer_letter_real_offer.jpg`). Left without changes. |
| Employment contract — Vietnam (English screens) | Amber line **"Sample wording. Have your own lawyer check it before you use it." · NOT PRINTED**; two-column Vietnamese \| English clauses; three "Only when" pills; preview with a real person, missing-value chips (`w2_en_designer_sample_note.jpg`) |
| Same, **Vietnamese screens** (QA language switched to Tiếng Việt, put back to English after; Chrome's page translation was not involved — judged from the page's own text) | **"Nội dung mẫu. Hãy nhờ luật sư của bạn kiểm tra trước khi sử dụng." · KHÔNG IN RA**; gallery and designer in Vietnamese (`w1_vi_designer_sample_note.jpg`) |
| People › Contracts → a contract → **Contract document** | Sheet "Employment contract · Using the wording for Vietnam", language Vietnamese / Tiếng Việt, the sample line with "Make it yours", 5 missing-value chips, "2 paragraphs are left out", **Download PDF** → real PDF "Employment contract — Giang Tuyết Nhung.pdf", 34 KB (caught in the page, nothing filed); "Save to documents · v1" offered (the QA login may file — not pressed) (`w6_contract_panel_sample_note.jpg`) |
| Insights › Build a report → "Time off, attendance and assets per person" (4,553 rows) → saved | Toolbar "Excel", "My Excel layout", **"PDF"**, both enabled after saving |
| PDF designer | Real first page with letterhead, "About 114 pages · 4,553 rows · A4 · Upright (fit)", fonts **Clean / Classic serif** only; **dragged the edge between Name and Department** → widths 26 % / 30 % ("Unsaved changes") → **Download PDF**: "Your PDF is downloaded: 4,553 rows, made in 16.4 seconds." — 84 pages, 615 KB, DejaVu Sans; closed with "Close without saving" (no look stored) (`w4_report_pdf_designer_preview_with_letterhead.jpg`) |
| Long report, page by page (same report, made again through the site) | **every one of the 84 pages has rows**; but **no page has a page number or the "Printed on" line, and the letterhead is missing** — see §8 (`f3_long_report_p1_no_letterhead_no_footer.png`) |
| Explorer → saved view "DEMO W2 Net pay by division" (**real pay figures**, 6 divisions × 8 months, ₫) → PDF | Designer: "1 page · 6 rows · A4 · Sideways (fit)", grand total row; Download PDF → 1 page, landscape, 23 KB, DejaVu Sans (`w5_explorer_pdf_pay_figures.jpg`) |
| Explorer → Send regularly… | **SEND AS: Standard Excel / PDF in my look**; choosing PDF shows "Each person gets a PDF of their own figures, printed in your look for this view…"; Cancel (no schedule saved) |
| Hiring › Offers | The offer list opened; the offer panel's language picker beside "Which letter…" was **not reached** in the browser (the row opened the candidate panel) — checked server-side instead (below) |

Left behind: nothing. The saved report (id 4) and the saved Explorer view (id 3) made for the walk were
deleted with the QA login's own rights; afterwards 0 reports, 0 views, 0 PDF looks by the QA login; the
QA login's language is back to English.

**Owner rulings, checked as real payobook logins in a server shell (`w2/w2_walk_probe.py`, rolled back):**
- Offer letter language: 6 offers — 5 with no known candidate language **write in the hiring company's
  language** (en_US), 1 where the candidate applied in Vietnamese writes Vietnamese; the recruiter's
  choice through the board verb (offer "sent for sign-off", chose Indonesian) → the letter **writes in
  Indonesian** and a note is returned. **Rule holds.** (Screen: see the table — not reached.)
- View-only people (download, not file): **could not be verified on payobook.** No existing login reads
  contracts without also being allowed to file documents (0 found), and a throw-away payroll-officer-only
  or HR-officer-only login made inside a rolled-back transaction could not see any contract at all
  ("This contract is not available to you…", the company's contract access rules). Covered by A2's
  tests 11 and 16 and its local walk with a read-only reader ("Paperwork" row, download only).

## 7. The two font findings (owner ruling 2026-11-24: no extra fonts on the server — report, do not fix)

Checked on live payobook.com through the document designer's own "Download a sample PDF" (no letter
made, nothing filed), run as the QA login in a server shell (`w2/w2_fontcheck.py`, rolled back), real
PDF engine (wkhtmltopdf 0.12.6) fetching the page styles and fonts from the running site. PDFs copied to
the Mac and drawn with `pdftoppm`; fonts listed with `pdffonts`; text pulled with `pdftotext`.
Pictures in `evidence_w2/`.

**a. Vietnamese employment certificate in "Clean" (A1's reproduction: bold names squashed).**
Shipped Vietnamese wording, "Clean" (the default), text size 13, letterhead on, printed twice, then in
"Classic serif". **On the server the fault does NOT show**: "ông/bà **Abigail Peterson** đang làm việc…
vị trí **Consultant**, bộ phận…" — the space after each bold name is there, all Vietnamese tone marks are
correct, and the two "Clean" prints came out the same size (75,424 bytes each). Pictures:
`f1_vi_certificate_clean_bold_names.png`, `f1_vi_certificate_serif_bold_names.png`.

**b. A long letter (2+ pages) in "Clean" (B: long PDFs losing text with web fonts).**
The shipped experience letter plus 30 numbered paragraphs with bold words, printed twice in "Clean"
and once in "Classic serif". **No text is lost**: both pages carry every paragraph (1–19 on page 1,
20–30 and the signature on page 2), bold words are spaced correctly, the two "Clean" prints are the
same size. Pictures: `f2_long_letter_clean_p1.png`, `f2_long_letter_clean_p2.png`,
`f2_long_letter_serif_p1.png`.

**c. New finding — "Clean" PDFs carry no real text.** In every "Clean" PDF the words are drawn as
shapes, not as text: `pdffonts` lists **no font at all**, `pdftotext` returns **nothing** (1–2
characters), and the files are big (the 2-page letter is **1,029 KB** in "Clean" against **24 KB** in
"Classic serif"; the 1-page certificate 75 KB against 20 KB). "Classic serif" PDFs embed DejaVu Serif
normally and their text can be selected (4,995 characters, all 30 paragraphs found). What this means for
a customer: a letter printed in "Clean" looks right, but nobody can select, copy or search its words, a
screen reader cannot read it, and it is many times larger to email. This is the same font family of
fault the builders saw (the engine handles the web font badly); it affects every document printed from
the designer in "Clean" (tested) and very likely "Friendly" and "Modern" (the other two web fonts, not
tested) — and "Clean" is the default page font. Not fixed (owner
ruling: report only).

## 8. Findings

- **Company letterhead, footer and page numbers missing from PDFs on payobook.com (pre-existing,
  wider than this release).** The designer previews and the contract sheet show the company header
  (logo, name, country) and, for reports, the footer "Printed on … by … · Page 1 of N"; the PDFs the
  server makes have none of it: letters, the contract document, the offer sample and report PDFs —
  through the site and in a server shell alike. A letter stored on 5 Oct (before this programme)
  has no header either (`f3_letter_2026-10-05_no_letterhead.png`), so it is not caused by wave 2, but it
  means B's "page numbers always print exactly once" does not hold on the live server and report PDFs
  have **no page numbers**. The server reaches its own address (https://payobook.com 200 from the
  server) and the PDF engine logs no warning. Cause not investigated (no fixes in this agent's scope).
  Also in the long report PDF the right-most column is cut at the page edge
  (`f3_long_report_p1_no_letterhead_no_footer.png`, "Assets held now").
- Offer letter names stay English on Vietnamese screens ("Offer letter — Vietnam"; A1 noted it), and the
  designer's title box keeps "Employment contract — Vietnam" while the gallery card reads "Hợp đồng lao
  động — Việt Nam". Cosmetic.
- Preview language for a Vietnamese person on the Vietnam contract copy defaults to "English (US) (their
  language)" with the line "No wording in this language yet: the letter prints the main wording, in
  Tiếng Việt." — correct, but reads oddly; the contract panel picks Vietnamese for the same copy.
- The PDF designer's page estimate is rough: "About 114 pages" for a PDF of 84 pages (B noted "About").
- rize: the nightly trial-period job fails on review 34 every night (`'int' object has no attribute
  'get'` in `pb_probation`), seen 22, 23 and 24 Nov — not this release; nobody is told on screen.
- The "Send regularly" recipient list on payobook.com shows many outside sign-up accounts with their
  email addresses (people who can open the Explorer on the demo) — pre-existing, noted only.
- Another session's test server (`pbqa_workforce_20261124`) and a sudima bank-check shell were running
  on the server during verification — not touched.

## 9. Left undone

- Browser: the offer panel's language picker beside "Which letter…" was not reached on payobook.com
  (rule checked server-side); view-only download/no-file could not be checked with a real payobook login
  (none exists, see §6). Other databases: automated checks only.
- Real-PDF tests on the Mac: **wkhtmltopdf is not installed on this Mac** (nothing installed);
  `pb_report_pdf` test_03 skipped; all real-PDF checks were done on the server (rehearsal copy, verify
  probes, payobook.com walk).
- The missing letterhead/footer/page numbers (§8) and the "Clean" text-layer finding (§7c) are reported,
  not fixed.
- Local test database `docstudio_w2_t` and its file folder dropped; no `w2_rh_*` copy left on the server;
  release worktree `gitlocal-worktrees/docstudio-w2` removed after this report's push.

## 10. Gotchas → ledger

- DS-W2-1 | Prep/rehearsal evidence folders are `750 odoo`: a wait loop `ssh … 'test -f /tmp/w2-…/x'`
  as the login user never sees the file and spins forever | use `sudo test -f` in every wait loop.
- DS-W2-2 | An idle signed-in browser tab polls the approvals inbox once a minute
  (`pb.approval.inbox/get_team_data`), which the 15-minute quiet check counts as activity: one open tab on
  sudima blocks every try | expected and correct by the rule; plan for it (the tries loop runs 4 h).
- DS-W2-4 | On payobook.com no PDF carries the company header/footer (letters since at least 5 Oct, and
  wave 2's contract/report PDFs): report PDFs have no page numbers and no "Printed on" line although the
  designer preview shows them | check headers/footers on a PDF from the live site, not only the preview;
  cause open.
- DS-W2-3 | Text in "Clean" (web font) studio PDFs is drawn as shapes: `pdftotext`/PyPDF2 find nothing,
  so a "text present" check on such a PDF always fails | check the words on a "Classic serif" print or
  by drawing the page (`pdftoppm`), and say which font was used.
