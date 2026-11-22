# DOCSTUDIO phase A1 — every other document in the designer: offer letters and certificates — REPORT (PAUSED)

**PAUSED on the owner's usage-limit instruction. See "Where I stopped" at the end.**

Branch `docstudio-a1` (from `origin/19.1` 0e4a814b0, `origin/docstudio-f` 84237cb87 merged in —
fast-forward). Two new bridge modules, both `auto_install`:

- **`pb_doc_studio_hiring` 19.0.1.0.0** (depends `pb_doc_studio`, `pb_hiring`)
- **`pb_doc_studio_me` 19.0.1.0.0** (depends `pb_doc_studio`, `pb_me_letters`)

Not merged, not deployed. Sparse worktree `gitlocal-worktrees/docstudio-a1` (pb_doc_studio + the
two bridges + docs). Addons path for local runs: official addons, the worktree (overlay), the main
checkout (identical to `origin/19.1` for pb_hiring, pb_me_letters, pb_lifecycle, pb_me_portal,
pb_employee_vault — `git diff HEAD origin/19.1 -- <those>` is empty). Conf:
scratchpad `a1/a1.conf` (port 8571, `max_cron_threads = 0`).

## Built so far

**pb_doc_studio_hiring** (offer letters)
- Gallery: offer letters listed under a new first group "Hiring" (`pbds_kind` / `pbds_kind_set`
  `selection_add`, `_compute_pbds_kind` override, `board()` re-sort), card line "Printed when an
  offer is prepared in Hiring · Used by N offers", "New document" under Hiring makes an offer letter.
- Fields = the offer's own keys (candidate name, job title, department, location, manager, company,
  monthly total, yearly total, currency, pay lines table as ONE block chip, start date, date);
  unknown keys in the wording are amber "no longer exists" (they print nothing).
- "Show only when" on the offer: country (request's, else company's), company, department, job,
  employment type (job's `contract_type_id`) — context key `pbds_doc_kind='offer'` filters the
  studio's own condition list.
- Preview / sample PDF with a REAL OFFER the user may read (record rules, no sudo): same RPC shape
  (`preview(template, draft, offer_id, lang)`), new facade method `offers(term)`; JS patch: "Preview
  with: An offer / A person", offer search, offer-specific empty state (no Hiring access vs no offer
  yet), candidate signature line on the paper, copy sentence speaks of offers, `applyDoc` resets
  the preview record when switching between a letter and an offer letter.
- Hiring: `pb.hiring.offer.action_prepare_letter` / `_make_pdf` overridden — untouched template →
  Hiring's own code (super); studio template (or a company/country copy of it, ranked by the
  studio's `_pbds_pick_variant`, applied ON TOP of `letter_template_id` incl. a cost profile) →
  `_pbds_source` (candidate language: `pb_lang` → contact → company), `apply_rules`, Hiring's
  `_placeholder_values` + translated pay table, page via `pb_doc_studio.report_doc_letter`
  (page_frame, sign block drawn after the wording, then the candidate's "Signature and date"),
  rendered AS THE CALLER (R89). New fields `pbds_lang`, `pbds_lang_name`, `pbds_wording_note`
  (shown on the offer form); `pb.hiring._offer_row` names the copy that prints.

**pb_doc_studio_me** (certificates)
- Heading of the language version / copy reaches the certificate subject (`_pbds_generate`).
- Own pay: `${monthly_pay}` in a certificate wording = the certificate's own employee's pay, put into
  the certificate's own values (`_pb_values`) — also when HR's approver issues a salary certificate;
  only when the wording uses it.
- "This document" lists certificate number, purpose, salary, date issued, joining date (as
  printed); preview shows the dates as the certificate prints them.
- Gallery line "Printed at once when an employee asks for it on My Payobook" / "Printed when HR
  agrees an employee's request on My Payobook" + "Issued N times".

vi_VN + id_ID PO for both (71 / 11 entries, all translated, three loading markers).

## Edits outside the new modules

- `pb_doc_studio/tests/test_doc_studio.py:499` — F's `test_board_open_and_new` asserted offer
  letters are never in the gallery (F's `NOT_HERE_YET`, which A1 was meant to lift). Now: offer
  letters may appear only under "Hiring". No other pb_doc_studio file edited; no pb_hiring /
  pb_me_letters / pb_lifecycle edit.

## Tests so far

| # | Test | Result |
|---|---|---|
| A1-01 | install silent ×2 (`-i` exit 0, 0 ERROR; no template written; no job) | PASS |
| A1-02 | golden offers (both shipped templates = Hiring's formula + Hiring's report) | PASS |
| A1-03 | golden certificates en/vi/id (+ salary en/vi) | PASS |
| R1 script | before/after install, same DB state: 2 offers (html + PDF-html + file name), employment ×3 langs (html, subject, PDF-html, values), salary ×3 (html, subject), template rows — 25 hashes | IDENTICAL (record ids in the PDF normalised) |
| A1-04 | edited offer wording prints from Hiring (as a recruiter) | PASS |
| A1-05 | rule by country + by employment type; offer condition list | PASS |
| A1-06 | offer language (candidate vi → vi version + vi pay table; unknown → company's) | PASS |
| A1-07 | page design in the PDF (narrow, serif, 12 px, signer, plain paper; letterhead on) | PASS |
| A1-08 | company copy wins incl. a real cost profile naming the original; switched off → original; company+country beats company | PASS |
| A1-09 | certificate language / rule / page / copy | PASS |
| A1-10 | own pay on own certificate (employee and approver), colleague refused | PASS (after fixture fix: letters user given HR officer, as F's test 11) |
| A1-11 | user without Hiring access cannot preview offers | PASS |
| A1-12 | portal `/my/certificates` end to end (real portal login, vi, own pay, colleague 404) | PASS alone; timed out once while two suites ran at once (re-run pending) |
| A1-13 | gallery + fields (offers and certificates) | PASS |
| A1-14 | preview with a real offer, sample PDF, nothing stored | PASS |
| A1-15 | hostile text inert | PASS |
| A1-16 | studio offer PDF rendered as the recruiter, not sudo (R89) | PASS |
| A1-17 | PO + static gates (both modules) | PASS |
| Suites | pb_hiring, pb_me_letters, pb_doc_studio at baseline | IN PROGRESS (see below) |
| Walk | browser walk | NOT STARTED |

## Where I stopped

- **Committed + pushed:** both modules (`61955aebb`, `765b8d604`) and this WIP commit (JS `applyDoc`
  fix, F test line 499, this report).
- **Running when paused:** full suites on `docstudio_a1_t` (`-u pb_hiring,pb_me_letters,pb_doc_studio,
  pb_doc_studio_hiring,pb_doc_studio_me`), log scratchpad `a1/suite_after.log` (~145/700 tests,
  ~20 s per pb_hiring test). Failures seen so far: `pb_doc_studio TestDocStudio.test_board_open_and_new`
  (fixed by the line-499 edit, not yet re-run), `pb_doc_studio_me TestCertStudioPortal.test_a1_12`
  (HTTP timeout under load; passed alone), `pb_hiring TestRecruitApplyPage.test_05_...vietnamese`
  and `pb_hiring TestClientReview.test_hiring_only_cannot_read_access_directory` (to be checked
  against the baseline — likely baseline, not touched by A1).
- **Local databases present:** `docstudio_a1_t` (bridges installed), `docstudio_a1_base` (same
  state WITHOUT the bridges — the baseline; a killed baseline `-u` run may have left modules
  "to upgrade", harmless), `docstudio_a1_walk` (copy of base, for the browser walk, nothing
  installed yet). Filestores under `~/odoo19/data/filestore/<db>`.
- **Scratch:** `a1/golden.py` (R1 script), `a1/fill_po.py` (PO filler), `a1/walk_seed.py` (walk
  seed: DEMO walker `demo_a1_walk`, two offers vi/id, portal `demo_a1_portal`), wkhtmltopdf 0.12.6
  unpacked at scratchpad `wk/box/bin` (put on PATH for the walk server).

**Exact next steps**
1. When `suite_after.log` ends: list FAIL/ERROR; re-run each failing pb_hiring / pb_me_letters /
   pb_doc_studio test on `docstudio_a1_base` (`-u <module> --test-tags /<module>:<Class>.<test>`)
   to prove it is baseline; re-run `/pb_doc_studio` and `/pb_doc_studio_me` alone on
   `docstudio_a1_t` (line-499 fix, A1-12).
2. Walk DB: `-i pb_doc_studio_hiring,pb_doc_studio_me` on `docstudio_a1_walk`, run `walk_seed.py`
   in `odoo-bin shell`, start the server with `PATH=<scratch>/wk/box/bin:$PATH`,
   `--db-filter=^docstudio_a1_walk$`, host `a1.localhost:8571`; walk: Settings › Documents →
   Hiring group → open "Offer letter" → preview with the vi offer → edit, rule, Vietnamese tab,
   Page → sample PDF → save; Hiring → prepare the letter → open PDF; My Payobook
   `/my/certificates` as `demo_a1_portal` (vi) → PDF. Console clean, 1280/1440, Vietnamese.
3. Finish this report (design self-score, owner questions, left for later, gotcha rows), commit,
   push; drop the three databases and their filestores.

Left for later (known now): Hiring's own "Print › Offer letter" menu still prints its old frame for
a studio offer (the PDF made by "Write the letter" is the studio one); own fields (Form builder) are
not offered on offer letters (an offer has no employee or contract); conduct letters, review-form
PDFs and payslips are left out on purpose.
