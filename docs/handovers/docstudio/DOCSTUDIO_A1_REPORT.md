# DOCSTUDIO phase A1 — every other document in the designer: offer letters and certificates — REPORT

Branch `docstudio-a1` (from `origin/19.1` 0e4a814b0 with `origin/docstudio-f` 84237cb87 merged in —
fast-forward). Two new bridge modules, both `auto_install`:

- **`pb_doc_studio_hiring` 19.0.1.0.0** — depends `pb_doc_studio`, `pb_hiring`
- **`pb_doc_studio_me` 19.0.1.0.0** — depends `pb_doc_studio`, `pb_me_letters`

Builder and tester: Opus. Not merged, not deployed. Paused once on the owner's usage-limit
instruction (WIP `51b6e2e1c`) and resumed. Sparse worktree `gitlocal-worktrees/docstudio-a1`
(pb_doc_studio + the two bridges + docs). Local runs: addons path = official addons, the worktree
(overlay), the main checkout — identical to `origin/19.1` for every module this phase reads or
extends (`git diff HEAD origin/19.1 -- pb_hiring pb_me_letters pb_lifecycle pb_me_portal
pb_employee_vault` is empty). Databases: `docstudio_a1_t` (copy of `upd_p6_t_tpl`, `-u all` on the
19.1 tree + `-i pb_me_letters,pb_doc_studio,pb_form_studio,pb_job_change`, then the bridges),
`docstudio_a1_base` (the same state WITHOUT the bridges = the baseline) and `docstudio_a1_walk`
(copy of the base for the browser walk) — all three dropped with their filestores at the end.

## 1. What was built

### Item 1 — offer letters (`pb_doc_studio_hiring`)

| Part | Built |
|---|---|
| Gallery | Offer letters listed in a new FIRST group **"Hiring"** (`pbds_kind_set` / `pbds_kind` `selection_add`, `_compute_pbds_kind` override, `board()` puts the kind first and re-sorts stably so copies stay after their original). Card line: briefcase icon, "Printed when an offer is prepared in Hiring" and a pill "Used by N offers" (counted as the caller). "New document" under Hiring makes an OFFER letter (`create_blank('hiring')`: letter type `offer`, starter wording with `${candidate_name}`, `${job_title}`, `${start_date}`, `${lines}`; its "built-in wording" is that starter). |
| Fields | The offer's own keys (Hiring's `_placeholder_values` + `${lines}`), grouped Candidate / Job / Company / Pay / Dates: candidate name, job title, department, where they will be based, who they will report to, company name, monthly total, yearly total, currency, **pay lines table (one block chip, drawn as a dashed table block on the page)**, start date, today's date. A key the wording uses that an offer does not have is amber ("no longer exists") and prints nothing. |
| "Show only when" on the offer | Country (the hiring request's, else the company's), Company, Department, Job position, Employment type (the job's `contract_type_id`). Implemented by filtering the studio's own condition list (context `pbds_doc_kind='offer'`), so the rule builder, sentences and save checks are the studio's. |
| Preview with a REAL OFFER (hero) | Same RPCs as a letter: `preview(template, draft, offer_id, lang)` and `sample_pdf(...)` take the offer picked; new `offers(term)` lists offers the caller may read (Hiring's record rules, never sudo). Language defaults to the candidate's. The page shows the candidate's signature line under the company's. JS patch: "Preview with · An offer / A person" line, offer search ("Find an offer", rows "OF-2026-0003 · job · state"), offer empty states (no offer yet / no Hiring access), candidate line on the paper, copy dialog sentence "Offers for roles at X in Y will use this copy.", and the preview record resets when switching between a letter and an offer letter. |
| Prepared in Hiring | `pb.hiring.offer.action_prepare_letter` / `_make_pdf` overridden. The wording = `letter_template_id` (name pick, cost profile or recruiter's choice) swapped for the most specific ACTIVE company/country copy by the studio's own `_pbds_pick_variant` — the copy rule applies on top of the cost profile. Untouched wording → **Hiring's own code (super), byte-identical**. Studio wording → `_pbds_source` (language: the candidate's `pb_lang` → their contact's → the company's), `apply_rules` on the offer's facts, Hiring's values read in that language + the pay table in that language (headings Pay item / Amount / How often), `substitute`; PDF through `pb_doc_studio.report_doc_letter` + `page_frame` (letterhead, margins, font, size, signature block, signature picture), **rendered as the caller, never sudo (Hiring's R89)**. New fields on the offer: `pbds_lang` (stored), `pbds_lang_name`, `pbds_wording_note` ("Using DEMO B's wording") shown on the offer form; `pb.hiring._offer_row` names the copy that really prints. |

### Item 2 — certificates (`pb_doc_studio_me`)

Certificates already go through the letter engine, so phase F decides wording, language version,
rules, page, copies and own fields. Gaps found and closed:

| Gap | Fix |
|---|---|
| The certificate's heading came from the template `pb_me_letters` picked, BEFORE the studio swapped a copy in and read a language version: a designed Vietnamese heading or a copy's heading was lost. | `pb.hr.letter._pbds_generate` (studio certificates only): the heading the studio reads for that language + " " + certificate number, exactly the `pb_me_letters` shape. |
| Own pay: `${monthly_pay}` on an employee's own certificate printed only when the employee pressed the button; a salary certificate issued by HR's approver fell to the approver's pay rights. | `pb.me.certificate._pb_values`: when the wording (its copy, every language) uses `${monthly_pay}`, the figure is the certificate's OWN employee's running-contract wage, read exactly as `${salary}` is — handed to the letter as a certificate value. Anybody else's pay keeps the studio's rail. |
| "This document" | Certificate number, purpose, salary (pay lock) plus **Date issued** and **Joining date, as the certificate prints it**; the preview shows those dates in the certificate's short form ("22/11/2026"). |
| Gallery | Award icon + "Printed at once when an employee asks for it on My Payobook" / "Printed when HR agrees an employee's request on My Payobook", pill "Issued N times". |

### Item 3 — gallery polish

Kind chips and group headings carry counts (grey at zero, F's quiet board), Hiring first; the
"what this prints for" line on offer and certificate cards; "Preview with: a person / an offer"
by document kind.

### Item 4 — left out on purpose

Conduct letters and review-form PDFs (they keep their own storage for privacy), payslips (own
designer). Not touched.

## 2. Tests

Suites: `pb_doc_studio_hiring` (11 tests + 3 gates), `pb_doc_studio_me` (5 tests + 3 gates).

| # | Test | Result | Evidence |
|---|---|---|---|
| A1-01 | Install silent ×2 | PASS | `-i` exit 0, 0 ERROR on `docstudio_a1_t` and on the walk copy; `test_a1_01` (no shipped offer letter carries studio data, no job). |
| A1-02 | Golden offers (both shipped offer letters) | PASS | `test_a1_02`: `rendered_html` = Hiring's own formula, Hiring's own report (no `pbds-page`). R1 script below. |
| A1-03 | Golden certificates en / vi / id | PASS | `test_a1_03`: employment ×3 languages and salary ×2 = the engine's formula, subject as `pb_me_letters` writes it, no value added. R1 script. |
| R1 | Before/after install, same database state | IDENTICAL | `a1/golden.py` (kept beside this report) in `odoo-bin shell` on `docstudio_a1_base` (before) and `docstudio_a1_t` (after): 25 hashes — 2 offers (html, PDF-html, file name), employment ×3 (html, subject, PDF-html, values), salary ×3 (html, subject), the template rows. Record ids inside the PDF HTML normalised. |
| A1-04 | Edited offer wording prints from Hiring | PASS | `test_a1_04` (prepared AS A RECRUITER): new wording, candidate, pay table replaces its paragraph, no `${`, PDF on the studio page, candidate still signs. Browser: "Write the letter" on OF-2026-0003 → the designed wording. |
| A1-05 | Offer rule by country | PASS | `test_a1_05`: Vietnam paragraph present for a VN role, gone for ID; employment-type rule; the five offer conditions. Browser: rule made on screen ("Only when Country is Indonesia"), "1 paragraph is hidden for this person" with the Vietnamese offer, paragraph absent in the real letter. |
| A1-06 | Offer language | PASS | `test_a1_06`: candidate `pb_lang` vi → Vietnamese version + Vietnamese pay-table headings + Vietnamese heading in the PDF; unknown → the company's language. Browser: Vietnamese version ("Kính gửi", heading "Thư mời nhận việc"); offer form "Letter written in: Vietnamese / Tiếng Việt". |
| A1-07 | Offer page design in the real PDF | PASS | `test_a1_07`: narrow report (12 mm), serif, 12 px, signer + title once, before the candidate line; letterhead off → no company layout, on → company layout. **Real PDF** (local wkhtmltopdf 0.12.6, unpacked in scratch per DS-9): A4, company header, narrow margins, DejaVu serif, Vietnamese glyphs correct, pay table, "DEMO Lê Minh / DEMO Head of People", "DEMO Trần Thu Hà / Chữ ký và ngày", "Trang 1/1". |
| A1-08 | Company copy wins incl. a cost profile naming the original | PASS | `test_a1_08`: a REAL `pb.hiring.cost.profile` (formula config + input rule) names the original; `action_country_offer_setup` sets it; the company copy prints; another company's copy ignored; note + Hiring panel name the copy; copy switched off → Hiring's own original again; company+Vietnam copy beats company-only. |
| A1-09 | Certificate language / rule / page / copy | PASS | `test_a1_09`: Vietnamese version + its heading on letter and PDF, rule by country of work, narrow/serif/signer page, company+Vietnam copy chosen with its note. Browser: Vietnamese certificate on `/my/certificates` → PDF heading "Giấy xác nhận công tác CERT/2026/0020", Vietnamese wording. |
| A1-10 | Own pay on own certificate prints, colleague's refused | PASS | `test_a1_10`: own employment certificate shows 25.000.000; a salary certificate issued by HR shows both `${monthly_pay}` and `${salary}`; a colleague's certificate cannot be asked for (AccessError); a letter with pay for a colleague by a non-pay HR user → plain refusal; preview chip "You may not see pay"; wording without the field → nothing read. Browser: portal PDF "Lương tháng: $ 25.000.000,00". |
| A1-11 | No Hiring access → no offer preview | PASS | `test_a1_11`: a letters administrator without Hiring opens the offer letter (`preview_kind` offer, `offer_access` false, no sample offer), `offers()` empty, `preview` / `sample_pdf` refused; a recruiter without letter rights cannot use the studio at all. |
| A1-12 | Portal flow on `/my/certificates`, real portal user | PASS | `TestCertStudioPortal.test_a1_12` on a quiet machine (§2.1): real portal login over HTTP, ask in Vietnamese (a smuggled `employee_id` ignored), PDF 200 `application/pdf` with the designer's Vietnamese wording, own pay, heading, studio page; a colleague's PDF 404. Browser: same flow as `demo_a1_portal`. |
| A1-13 | Gallery + fields | PASS | `test_a1_13` ×2 (hiring first, cards, prints-for, uses, offer catalogue incl. block chip, sample offer, letters keep people, new Hiring document = offer letter; certificate "This document" fields, preview dates). |
| A1-14 | Preview with a real offer | PASS | `test_a1_14`: values, "3 lines", hidden count, missing chip for an unknown field, sample PDF, nothing stored on the offer, offer search. |
| A1-15 | Hostile text inert | PASS | `test_a1_15`: `<script>` stripped from the wording, a candidate named `<img onerror>` escaped in the letter and the preview. |
| A1-16 | Rendered as the caller (R89) | PASS | `test_a1_16`: a spy on `_render_qweb_pdf` sees the recruiter's uid, `su=False`. |
| A1-17 | PO + static gates | PASS | `test_gates` ×2: vi/id parse with the loader, every entry has module + occurrence + code marker, every msgstr filled, none names the platform; no platform word in templates/strings; window actions name their views. 71 entries (hiring), 11 (certificates). |
| Suites | `pb_hiring`, `pb_me_letters`, `pb_doc_studio` at baseline | see §2.1 | |
| Walk | Browser walk, console clean | PASS | §2.2 |

### 2.1 Existing suites vs baseline

__SUITES__

### 2.2 Browser walk (Chrome, host `a1.localhost:8571`, throwaway login on the walk copy)

1440 wide, English: Settings › Documents — "Hiring 2" chip and group first, both offer cards with
"Printed when an offer is prepared in Hiring", "Used by 2 offers". Open "Offer letter": fields
Candidate / Job / Company / Pay / Dates with the picked offer's real values; "Pay lines table" is a
dashed table block on the page; "Preview with · An offer" (DEMO Siti Rahmawati, previewed in
Indonesian: "Komponen gaji / Jumlah / Frekuensi", "Penandatangan yang berwenang", "Tanda tangan dan
tanggal"). Change → offer list (two offers with reference and state) → DEMO Trần Thu Hà: preview
switches to Vietnamese ("22 tháng 11, 2026", "Khoản lương", "Người ký được ủy quyền", "Chữ ký và
ngày"). Typed a sentence, "Show only when…": the rule builder offers Country, Company, Department,
Job position, Employment type; Country is Indonesia → "1 paragraph is hidden for this person".
Vietnamese tab → Copy from English → "Kính gửi", heading "Thư mời nhận việc". Page: Narrow, Classic
serif, signer DEMO Lê Minh / DEMO Head of People. ⌘S → "Saved. Letters made from now on use this
wording." Sample PDF (true PDF, 31 kB). Hiring › Offers › OF-2026-0003 → "Write the letter" → The
letter tab: Vietnamese wording, the Indonesia-only paragraph absent, "Letter written in Vietnamese /
Tiếng Việt", PDF filed (real PDF checked, A1-07). Back to the gallery → "Employment certificate"
(card: "Printed at once when an employee asks for it on My Payobook") → "Preview with · A person"
(the offer was replaced by a person), "This document" lists the certificate's fields, preview dates
"22/11/2026", "01/03/2025"; added "Monthly pay" to the main and the Vietnamese wording ("Start from
the translation") → saved. Portal (`demo_a1_portal`, `/vi/my/certificates`): asked an employment
certificate in Vietnamese → "Giấy xác nhận đã sẵn sàng" → PDF 200 with the designer's wording, the
heading and "Lương tháng: $ 25.000.000,00". 1280 wide, Vietnamese user: gallery ("Tuyển dụng 2"),
offer designer fully in Vietnamese ("Xem trước với · Một lời mời", "Bảng các khoản lương", "Chỉ khi
Quốc gia là Indonesia").

Console: no error and no warning on the studio and Hiring pages (after the asset purge below). The
only messages seen were environment artefacts of a template copy without filestore (S6A-7): asset
bundles (cleared with `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'`) and the website
favicon on the portal page (`website.favicon` attachment, file missing) — not this phase.

## 3. Rails

- **R1 untouched = byte-identical**: an untouched offer letter goes to Hiring's own
  `action_prepare_letter` / `_make_pdf` (super); an untouched certificate to the letter engine
  (F's rule) and `_pb_values` adds nothing unless the wording uses `${monthly_pay}`. Proven by
  A1-02, A1-03 and the before/after script (25 identical hashes).
- **No sudo for the PDF (R89)**: A1-16. Only the letter library (wording, page, signature picture)
  is read as the system — what Hiring already does.
- **Offer access = Hiring's record rules**: preview, sample and the offer list read as the caller
  (A1-11, A1-14).
- **Pay**: own pay only for the certificate's own employee; colleague refused (A1-10).
- **No eval, inert text**: rules use the studio's fixed operator table; values escaped (A1-15).
- **Silent install**: no data written to existing templates/offers/certificates, no job, no mail.
- **White-label**: no platform word in any new string or msgstr (A1-17).

## 4. Edits outside the new modules

- `pb_doc_studio/tests/test_doc_studio.py:499-500` — F's `test_board_open_and_new` asserted that
  offer letters are never in the gallery (F's `NOT_HERE_YET`, which A1 was asked to lift). It now
  asserts they may only appear under "Hiring". Nothing else in `pb_doc_studio`, and nothing in
  `pb_hiring`, `pb_me_letters`, `pb_lifecycle` was edited. F's golden test (`test_02`) stays green.
- `NOT_HERE_YET` itself was NOT edited: the bridge overrides `_template` and `_pbds_templates`, so
  offer letters appear only where `pb_doc_studio_hiring` is installed (no half state where the
  gallery shows offers whose wording would not reach Hiring).

## 5. Contracts other phases can rely on

- `pb.doc.studio.offers(term)` → `[{id, name, job, company, ref, state, lang, lang_name, avatar, kind:'offer'}]`.
- `open()` returns `preview_kind` ('person' | 'offer') and, for offers, `offer_access`.
- `pb.hiring.offer`: `_pbds_offer_template()`, `_pbds_offer_lang()`, `_pbds_offer_render(tmpl, body, lang, rules, ghost, missing, wrap)`, `_pbds_offer_page(...)`; fields `pbds_lang`, `pbds_lang_name`, `pbds_wording_note`.
- Gallery cards may carry `prints_for`, `uses`, `uses_text` (set in `_pbds_card`); the `.pbdx-prints` line style can be reused (A2: "Printed from the contract panel").

## 6. Deploy notes (new modules; risky tier — they change how two existing documents print once edited)

- Both bridges `auto_install`: `-i pb_doc_studio_hiring,pb_doc_studio_me` on all five databases
  AFTER `pb_doc_studio` (wave 1b) is in. Creates 1 inherited form view (offer form), 1 column
  `pb_hiring_offer.pbds_lang`, selection value `hiring` on `pbds_kind_set`. No data written, no
  job, no mail.
- Asset bundles change (backend JS/XML/SCSS): purge `/web/assets/%` per database and restart.
- Rehearsal on a clone ONLY (jobs and mail off): `docs/handovers/docstudio/a1/golden.py` in
  `odoo-bin shell` before and after the install — expect identical output (it rolls everything
  back; it creates DEMO records inside a savepoint and switches the company's country for the run).
- After go-live: one sample offer letter and one certificate as PDF on payobook (see owner
  question 3).

## 7. Design self-score ("extreme WOW, intuitive, out-of-this-world experience, best in class")

Hero moment: **"Preview with a real offer"** — the candidate's own letter, in their language, with
the pay table and both signatures, redrawn as you type, and the true PDF one click away.

| Bar | Score | Why |
|---|---|---|
| Hero moment | 9/10 | Real offer, candidate's language, translated pay table, hidden-paragraph count, sample PDF = real PDF. Loses a point: the offer list cannot be filtered by state. |
| Zero dead ends | 9/10 | No offer yet / no Hiring access / unknown field / no lines / switched-off copy all say what happens and what to do. |
| Consistency | 9/10 | All of it is the studio's own machinery (rule builder, chips, page, copies); offers add only their fields and their record. |
| Quiet board, palette, icons | 9/10 | Locked indigo, grey zero chips, Lucide briefcase/award/table icons, no gradient. |
| Plain words | 9/10 | "Preview with · An offer", "Used by 2 offers", "Printed when an offer is prepared in Hiring". |
| Overall | 9/10 | |

## 8. Owner questions (plain words)

1. **Which language should an offer letter be in when Payobook does not know the candidate's?**
   Today: the language they applied in, else the language on their contact card, else the
   company's language. The contact card language is usually just the recruiter's screen language
   at the time the candidate was added. Keep this order, or skip the contact card and use the
   company's language?
2. **Pay lines in Indonesian.** The "how often" words of the pay table ("Every month", "One-off")
   have no Indonesian translation in Hiring yet, so an Indonesian offer letter shows those two
   words in English. Add the Indonesian words in Hiring in a later phase?
3. **The "Clean" letter font prints bold words a little tight in Vietnamese on this Mac's PDF
   printer** (a bold name touches the next word); "Classic serif" is fine. Worth one look at a
   printed certificate on the live server; if it shows there too, the Document studio's "Clean"
   bold needs a fix (phase F's fonts).

## 9. Left for later

- Hiring's own "Print › Offer letter" menu on the offer still prints Hiring's old frame around the
  studio wording (the PDF made by "Write the letter" — the one filed and sent — is the studio page).
- Customer's own fields (Form builder) on offer letters: an offer has no employee or contract yet.
- The offer list in "Preview with" cannot be filtered by state or role.
- Shipped offer letter names stay in English in the gallery (no translation shipped).
- At 1280 px F's designer header shows "Make a copy for…" / "Built-in wording" as icons without an
  accessible name — F's markup, reported only.
- Conduct letters, review-form PDFs, payslips: left out on purpose (handover).

## 10. New gotcha rows (ledger)

- DS-A1-1 | The studio keeps the preview record from one document to the next: opening an offer
  letter after a letter would send an EMPLOYEE id as the offer id | `applyDoc` patch resets the
  preview record when the document kind changes.
- DS-A1-2 | A template copy (`createdb -T`) keeps asset/website attachments in the database but has
  no files: the walk logs 500s on `/web/assets/...` and the favicon | purge `/web/assets/%`
  attachments on the walk copy; the favicon 500 is harmless.
- DS-A1-3 | Two `odoo-bin --test-enable` runs at once on this Mac make HttpCase tests time out
  (12 s read timeout): `pb_hiring TestRecruitApplyPage.test_05` and A1-12 errored only then | run
  HTTP suites alone; re-run timeouts before calling them regressions.
- DS-A1-4 | `pb.hr.letter.new({'template_id': t})._pbds_source(lang)` reuses the studio's reading
  order for documents without an employee (offers), no second copy of it.
