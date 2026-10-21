# LEARNING L1 — Certificates and expiry

Programme: LEARNING. Design page `docs/design/rize-learning-blueprint.html` §5 "Certificates",
§6 "A certificate record", §7 phase L1. Ledger `docs/handovers/learning/LEARNING_LEDGER.md`
(L1–L8, LD1–LD3, LN1–LN7 + whatever L0 added) is binding. Predecessor: `L0_LEARNING_MENU.md`
and its report `L0_REPORT.md` — take the Learning hub, lens registry, Overview facade and My
learning lens names from the L0 report, not from memory.

Report back to `docs/handovers/learning/L1_REPORT.md` (same template as L0 §9).

## 1. Scope

**Goal.** One register of every certificate and licence a person holds, with issued-on and
valid-until, so the system can say who is about to lapse and chase the renewal itself.

**In scope.**
1. The vault document (`pb.employee.document`) becomes the certificate record: `pb_training`
   extends it with training fields (§3.1). No second table.
2. Test certificates get a **valid-until** from the test's validity months (the installed
   `hr_skills_survey` field); the de-dup rule is fixed so a renewal files a **new** certificate
   and marks the old one renewed (§3.2).
3. **Uploads**: an employee adds an outside certificate or licence from their own page; HR
   adds one for anyone from the register. Verified flag as the vault already has it (§3.3).
4. **Renewal ladder**: a new daily leg mails the person at 60 / 30 / 7 days and on the day,
   the manager at 14 days, the HR lead on expiry; and **re-assigns the refresher course**
   automatically 60 days before expiry with reason "Renewal" (§3.4).
5. **CERTIFICATES lens** on the Learning rail (seq 65, between Tests and Claims): the
   register with filters Expiring 30 / 60 / 90 · Expired · Valid · No expiry · Renewed,
   search, by department and job, row actions, "Add a certificate" drawer (§4.1).
6. **My learning** gains a "My certificates" block; a new learner page `/my/training/
   certificates` (the wallet) with upload; a **learning record PDF** (§4.2, §4.3).
7. **Overview** headline and tiles gain certification status; **Numbers** gains four tiles
   and a "Certificates" breakdown (§4.4).
8. Demo data (§6), tests T1–T14 (§7), normal-tier deploy on all four DBs (§8).
9. Carried from L0 (ledger LN11): remove the three training roles from Talent's
   `SCREEN_GATES` row in `pb_vendor_access/hooks.py` so a person whose only role is a
   training role no longer sees an empty Talent entry; gates are additive, so ship a
   `pb_vendor_access` migration that edits the existing row on every DB (skip rows with
   `access_customized`). This is the ONE allowed touch of `pb_vendor_access` in L1.
10. Carried from L0 (ledger LN10, partial): the server-side English constants used on
    the learner pages and mails (`due_words`, `ASSIGN_REASONS`, `ASSIGN_STATES`,
    `duration_words`) are translated with `_()` so Vietnamese readers see Vietnamese on
    the old board, the portal pages and in mail. Add the VI msgstrs. (L0 already fixed the
    My learning lens client-side; this makes the words right at the source.)
- Ruling from L0 (not a change): plain employees never see the left menu (they land on
  their portal page by the owner's employee-only landing rule). "My learning" on the rail is
  for back-office staff and managers; employees keep `/my/training`. Both read the same
  facade, so every L1 learner feature must appear on BOTH the lens and the portal pages.

**Binding non-goals.** No requirement rules or matrix (L2). No sessions (L4). No change to
`pb_employee_vault`, `pb_me_portal`, `hr_skills_survey` code — extend by `_inherit` only. No
new approval route. No change to claims money flow. No gamification. The vault's own
expiry activity job stays as it is (it raises an HR to-do at 30 days; our ladder sends mail;
both may fire — say so in the report, do not switch either off).

## 2. Verified plumbing facts (do not re-derive)

| # | Fact | Where |
|---|---|---|
| F1 | `pb.training.certificate` (abstract) files PDFs into the vault: category by **code** `CERT` (`pb_employee_vault.cat_certificate`, "Degree / Certificate", `requires_expiry=False`); name builder `_document_name(course, provider)` = `"%s — certificate"` (+ ` (provider)`); **de-dup `_already(employee, name)`** by name incl. archived rows; `_file()` sets `issue_date=today`, **`expiry_date=False` on purpose**, `note`. Pass hook: `survey.user_input._mark_done` override (:241-263) → `file_course_certificate(channel, partner)` (:132-187) picks the latest `done, not test_entry, scoring_success` attempt and renders `survey.certification_report` (`_render` :189-201); `_refresh_one` hook (:266-286) also files on the `done` crossing. Claim path `file_claim_certificate` (:206-238) **copies** the claim's attachment. | `pb_training/models/certificate.py` |
| F2 | `pb.employee.document` fields: `employee_id, category_id, name, attachment_id, issue_date, expiry_date (indexed), note, verified/verified_by/verified_at (sentinel-guarded), company_id, active`, non-stored `expiry_state` none/valid/soon/expired (soon = 90 days hard-coded, :80-97). `create` rejects a non-HR caller binding an attachment they do not own (:113-134). `unlink` deletes attachments. Vault cron `_cron_expiry_check` (:226-269) raises one `hr.employee` activity per document within `pb_employee_vault.expiry_warn_days` (30). | `pb_employee_vault/models/employee_document.py` |
| F3 | `survey.survey.certification_validity_months` (Integer, 0 = never expires) comes from **`hr_skills_survey`** (vendored at repo root, installed on payobook per RIZE_LEDGER R173; **verify on payobook_template, p0clone, rize** before deploy — `-i` it where missing). Not stock survey. `pb_training` does not depend on it yet. | `hr_skills_survey/models/survey_survey.py:6-12`, form `views/survey_survey_views.xml:10` |
| F4 | `hr_skills_survey` also writes an `hr.resume.line` (type `resume_type_certification`) on pass with `date_end = today + validity months`; its `expiration_status` is stored and **never recomputes with time** (depends on `date_end` only; "expiring" = fixed 3 months). It rewrites the line in place on a re-pass. Both `pb_training` and `hr_skills_survey` override `survey.user_input._mark_done`; order is not fixed by depends today — adding the dependency fixes it. | `hr_skills_survey/models/survey_user.py:13-55`, `hr_resume_line.py:8-26` |
| F5 | `survey.user_input`: `end_datetime`, `scoring_percentage` (stored), `scoring_success` (stored, = `scoring_percentage >= scoring_success_min`), `test_entry`; `slide_id` from `website_slides_survey`. Stock certificate route `/survey/<id>/get_certification` (auth user, no token) renders on demand; `pb.my.training.certificate_url` (:581-601) returns `{url}` or `{code}`. | server `survey` addon; `pb_my_training.py` |
| F6 | Assignment: `ASSIGN_REASONS` = `day_one, probation, compliance, adhoc, leadership` (`training_common.py:135-141`), states `assigned, in_progress, overdue, excused, done` (:146-152), `ASSIGN_OPEN` (:158). `_refresh_one` (:244-274) sets `done` + `completed_on` (first time) + `score`. `create` → default due days (`pb_training.default_due_days` 14) → `_guard_one_open` (:328-344, UserError on a second open row) → `_enrol`, `_ensure_status`, `_refresh_one`, `_announce`. `assign_many(channel_id, employee_ids, reason, due_date, counts_for_probation)` (:585-642). `schedule.run_now` creates rows directly (not via assign_many). | `pb_training/models/assignment.py`, `schedule.py:171-244` |
| F7 | Automation `_cron_daily` (:50-77): legs `_refresh_all`, `_run_schedules`, `_chase` each through `_leg(label, fn, default)` (:94-102, savepoint + warning). Cap `pb_training.reminder_cap` 400 shared across sends (:148-168). `_chase_one` (:170-226) keys `d3/d1/d0/od<n>/mgr<n>/hr<n>`; send helper `assignment._mail(xmlid, email_to)` (:421-444, `send_mail(force_send=False)`); addresses `_their_email` (:446), `_manager_email` (:457); HR lead `_hr_email(company)` (`automation.py:231-250`, Approval Matrix seat `hr_lead`, fallback training managers). `reminder_log` = JSON `{key: iso_date}` via `_sent`/`_mark_sent` (:499-513). Settings via `flag()`/`number()` (`training_common.py:281-288`) with `DEFAULTS` (:60-126). | `pb_training/models/automation.py` |
| F8 | Mail templates file is `noupdate="1"`; every send passes `email_to` explicitly; clone target `mail_template_assignment_due` (:90-122): `email_from {{ user.email_formatted }}`, inline HTML, button to `/my/training/#{channel_id}` (its colour `#4F46E5` is the retired bright indigo — use `#5A4BB0` in new templates). | `pb_training/data/mail_template_assignments.xml` |
| F9 | Portal: home cards precedent (:109-121) + counter wiring `_prepare_home_portal_values` (`portal.py:95-107`); cards always drawn (R62); controller helpers prefixed `_tr_` (R186); page skeleton = `portal.portal_layout` → `div.pbme.pbtr` → `tr_notices` → back link → `pb_me_portal.ess_hero` → `pbme-card`; tiles `pbme-tiles/pbme-tile/-l/-v/-y`; expiry chip class in the vault page `pbme-exp pbme-exp--<state>` (`pb_me_portal/views/portal_templates.xml:819`). Documents page `/my/documents` (`pb_me_portal/controllers/portal.py:340-355`), download `_doc_download_url` (:367-378) = `/web/content/ir.attachment/<id>/datas?download=true&access_token=…`. Upload limits precedent `_UPLOAD_MAX_BYTES` 10 MB, MIME png/jpeg/pdf (:41-42, :380-). | `pb_training/views/portal_templates.xml`, `pb_me_portal` |
| F10 | Claim upload precedent: `_tr_upload(post.get('certificate'))` → `(filename, content)`; `claim._attach(upload, field)` creates `ir.attachment` with `raw` (:621-636); form `enctype="multipart/form-data"` + csrf + `<input type="file" accept="image/*,application/pdf">` (:968-1010); tokened download `_tokened_url` (:641-650). | `pb_training/controllers/portal.py:351-413`, `models/claim.py` |
| F11 | PDF precedent: `pb_lifecycle/report/hr_letter_report.xml:8-17` (`ir.actions.report` qweb-pdf, template `web.html_container` → `web.external_layout` → `div.page`), render+store in `pb_lifecycle/models/letter.py:193-218`; paperformat precedent `pb_hr_payroll_formula/report/payslip_themed.xml:14-35`. Odoo 19: no `<report>` shortcut tag — explicit `<record model="ir.actions.report">` only. | |
| F12 | Analytics `get_numbers` payload keys `allowed, from, to, total, empty, headline, tiles, by_department, by_course, by_reason, trend, claims, lists, reasons, core`; `_tiles(core)` (:233-259) returns `[{key,label,value,icon,sub}]`, icons from `ic()`; the numbers page renders any tile list unchanged (`training_numbers.xml:140-151`); `.pbim-stats` has no column count (R196). Gate `_can_read` (:66-77). | `pb_training/models/analytics.py`, `static/src/xml/training_numbers.xml` |
| F13 | Security precedent: CSV four tiers per model (`ir.model.access.csv:1-5`); rules file is `noupdate="1"` — rule changes to existing rules go through migrations; "my companies" rule (:37-42), "own + direct reports" rule (:44-53), trainer-wide rule (:59-64). The vault has its own ACLs/rules for `pb.employee.document` (do not duplicate; the register facade reads as sudo gated by training groups + `company_id in env.companies`). | `pb_training/security/*` |
| F14 | Demo: `env.get('pb.demo.seed').register(recordset, label)`; names start with "DEMO", never "Rize". On payobook: course 27 "DEMO Agronomist basics" (survey 17, pass 70, 3 attempts); assignments 127–135; schedules 7 "DEMO Fire safety, every year" and 8 "DEMO Site safety, every year"; vault documents **143** (claim certificate) and **145** (test certificate for Ngô Bảo Lâm) both with empty expiry. | `RIZE_LEDGER.md` R181/R190/R199 |
| F15 | `leg(env, label, fn)` (`training_common.py:266-278`) = savepoint + warning, never raises. `pb.training.get_board` gate pattern (`pb_training.py:92-104`). People picker that ignores accents already exists on the board (reuse for "Add a certificate for someone"). | |

## 3. Architecture

### 3.1 The certificate record = `pb.employee.document` + training fields (new `pb_training/models/document_ext.py`)
`_inherit = 'pb.employee.document'`, fields (all `copy=False`):
- `training_source` Selection `[('test','Passed a test here'), ('claim','Outside course, from a claim'), ('upload','Uploaded'), ('statutory','Statutory card or licence')]`, indexed. Empty = not a training certificate (ordinary vault file).
- `channel_id` M2o `slide.channel` (set null), `survey_id` M2o `survey.survey` (set null), `attempt_id` M2o `survey.user_input` (set null), `claim_id` M2o `pb.training.claim` (set null).
- `issuer` Char ("Issued by"), `reference` Char ("Certificate number").
- `renewed_by_id` M2o `pb.employee.document` (set null) + `renewal_assignment_id` M2o `pb.training.assignment` (set null).
- `pb_training_reminder_log` Text default `'{}'` (same JSON shape as F7).
- `training_state` non-stored Selection `valid / soon / expired / none / renewed` computed from `expiry_date`, `renewed_by_id` and the setting `pb_training.renew_before_days` (default 60) — **"soon" means inside the renewal window, not the vault's fixed 90 days**. Add `_search` so the register can filter on it.
- Plain-word helpers (non-stored Char): `source_words`, `valid_words` ("Valid until 14 Nov 2026", "Expired 3 days ago", "Never expires", "Renewed").
- New category `pb_training.cat_licence` (`pb.employee.document.category`, code `LIC`, name "Licence / permit", VI "Giấy phép", `requires_expiry=True`, sequence 31) shipped as data (noupdate=1); uploads choose "Certificate" (CERT) or "Licence" (LIC).
- Migration `pb_training/migrations/19.0.1.4.0/post-certificates.py`: for CERT documents whose name ends with "— certificate" (any provider suffix) set `training_source` = `claim` when a `(provider)` suffix is present else `test`; when `test`, try to link `survey_id/attempt_id` by the employee's passed attempt on the course whose name matches, and set `expiry_date = issue_date + validity months` when the survey has `certification_validity_months > 0`. Log counts. Idempotent.

### 3.2 Test certificates: validity and renewals (`certificate.py`)
- Manifest: add `hr_skills_survey` to depends (F3/F4) so `_mark_done` order is fixed and the validity field is guaranteed.
- `_file()` learns `extra` values: `training_source, channel_id, survey_id, attempt_id, claim_id, issuer, expiry_date`. For a test: `issue_date = attempt.end_datetime.date()` (fallback today), `expiry_date = issue_date + relativedelta(months=validity)` when validity > 0, `issuer = company name`.
- **De-dup fix:** `_already` for a test certificate checks `(employee_id, attempt_id)`; for a claim `(employee_id, claim_id)`; name-only de-dup stays for everything else. Name gains the year: `"%s — certificate (%s)" % (course, issue_year)` — only for rows created from now on; existing names untouched.
- On filing a new test certificate when an older unrenewed `test` certificate for the same `survey_id` exists for that employee: set old `renewed_by_id = new`; if the old row has `renewal_assignment_id` and that assignment is `done`, nothing else (it finished); the new row carries no renewal assignment.
- `pb.my.training.home()` tiles and `course()` payload: add `certificate: {valid_words, expiry_date, state}` where present (My learning block reads it).

### 3.3 Uploads
- Facade `pb.my.training.add_certificate(values, upload)` (`@api.model`): `values = {name, kind: 'CERT'|'LIC', issuer, reference, issue_date, expiry_date, note}`; `upload = (filename, bytes)`; size ≤ 10 MB and MIME in png/jpeg/pdf (clone F9 limits, plain-word UserErrors: "The file is bigger than 10 MB.", "Only PDF, JPG or PNG files."); creates the attachment on `hr.employee` as sudo, creates the document as sudo with `training_source='upload'`, `verified=False` (do not touch the sentinel). Employee must have an `hr.employee` (else AccessError "Only employees can add certificates.").
- Board verb `add_certificate` in `pb.training._VERBS` (HR path): same, plus `employee_id` and `training_source` in `('upload','statutory')`, `verified=True` with `verified_by/at` set the way the vault's own verify path does it (find its method; call it, never write the guarded fields directly).
- Board verb `verify_certificate(document_id)` and `assign_refresher(document_id)` (creates the renewal assignment now, see §3.4, UserError in plain words if one is open).

### 3.4 Renewal ladder and auto re-assignment (`automation.py`, new leg)
- Settings (add to `DEFAULTS`): `pb_training.renew_before_days` '60', `pb_training.cert_reminders` '1', `pb_training.cert_manager_days` '14'.
- `_cron_daily` gains leg 4 `_chase_certificates(today)` under the same cap (`counts['certificates']`), skipped when `cert_reminders` is off. Also leg 3b `_renewals(today)`: for every `test` document with `expiry_date`, not renewed, `expiry_date - today <= renew_before_days`, `channel_id` set and course still active, no open assignment on that course for the employee → create `pb.training.assignment` (reason `renewal`, `due_date = expiry_date`, `assigned_by_id` = SUPERUSER, `counts_for_probation=False`) in a savepoint and link `renewal_assignment_id`. One per document, ever (the link is the guard).
- `ASSIGN_REASONS` += `('renewal', 'Renewal')` (VI "Gia hạn"); `reason_words` picks it up; analytics `reasons` dict too (check `_split` by reason uses the constant).
- `_chase_cert_one(doc, today, mgr_days, counts)`: keys `x60, x30, x7, x0` to the person (template `certificate_expiring`; subject "{{ object.name }} — {{ object.valid_words }}"), `xm14` to the manager (`certificate_expiring_manager`), `xh0` on the day to the HR lead (`certificate_expired_hr`, via `_hr_email`). Nothing after expiry day (the overdue renewal assignment's own chase takes over). Skip rows with `renewed_by_id`. Mail helper: clone `assignment._mail` as `document._pb_training_mail(xmlid, email_to)` on the document model (templates render on `pb_employee_vault.model_pb_employee_document`; new file `data/mail_template_certificates.xml`, noupdate=1, button `/my/training/certificates`, brand colour `#5A4BB0`).

### 3.5 CERTIFICATES lens (Learning rail, seq 65, label "Certificates" / VI "Chứng chỉ", icon `award` — add to `ic()` if missing)
- Facade `pb.training.certificates_board(filters)` (`@api.model`, gate as `get_board`): `filters = {state, department_id, job_id, q, page}`; returns `{allowed, tiles:[expiring_30, expiring_60, expiring_90, expired, valid, no_expiry], rows:[{id, employee, department, job, name, source_words, issued, valid_words, state, renewal:{assignment_id, state_word}|null, verified, download_url}], total, page, pages}` (page size 50). Rows as sudo, `company_id in env.companies`, `training_source != False`.
- Component `PbCertificatesLens` (`pb_training/static/src/js/certificates_lens.js` + xml + scss, pbim kit like the board): filter chips (quiet: grey at zero, amber for Expiring, rose for Expired), search box (accent-insensitive on the server via the same helper the people picker uses), department/job selects, table with state chips, row actions **Assign the refresher**, **Verify**, **Download**; header button **Add a certificate** → drawer (person picker, name, kind, issuer, reference, issued on, valid until, file). Empty state: "No certificates yet. A passed test files one here by itself; uploads go through Add a certificate." **Hero moment:** the six tiles as one sentence above the table: "214 certificates. 12 expire within 30 days, 3 have expired." Phone: tiles wrap, table scrolls inside its own container.

### 3.6 My learning (L0 lens) + wallet page + record PDF
- L0's `PbMyLearningLens` gains block **My certificates**: chips per certificate (`valid_words`, state colour), "Start renewal" button when `renewal_assignment_id` is open (opens `/my/training/<channel_id>`), link "All my certificates" → `/my/training/certificates`, link "My learning record (PDF)" → `/my/training/record.pdf`.
- Portal page `/my/training/certificates` (GET: wallet list + "Add a certificate" form; POST `/my/training/certificates/new`): clone the claims page skeleton (F9/F10); home card "My certificates" priority 47 with counter `training_certificates_count` (facade `certificates_count()`); `_tr_` prefixes.
- Learning record: `ir.actions.report` `pb_training.report_learning_record` on `hr.employee` (qweb-pdf, explicit record, A4 paperformat clone), template lists finished courses (course, finished on, score) from `pb.training.assignment` `done` rows and certificates (name, issuer, issued, valid until, state). Route `/my/training/record.pdf` (auth user) renders for the session employee only (`_render_qweb_pdf` as sudo on `[employee.id]`, `Content-Disposition` attachment). HR: row action "Learning record" on the Assigned lens people? — not in L1; the register's row menu gets "Learning record (PDF)" opening `/my/training/record.pdf?employee_id=<id>` allowed only for training groups.

### 3.7 Overview and Numbers
- `pb.training.overview()` (from L0) adds `certificates: {expiring_30, expired, valid, no_expiry}` and a headline fragment "12 certificates expire within 30 days." (omit when zero). Queue row "Certificates expiring" → lens `certificates` with filter `expiring_30`.
- `analytics._tiles` adds `expiring_30` ("Expire within 30 days"), `expiring_90`, `expired`, `renewals_open` ("Renewals under way"); new breakdown `by_certificate` (top 10 certificates by holders with expiring/expired counts) rendered as a new section in `training_numbers.xml` cloned from "By course"; spreadsheet gains a "Certificates" sheet; the pack mentions the expiring count.

## 4. Safety rails
1. Ledger L1–L8. Every new string EN + VI (`pb_training/i18n/vi_VN.po`).
2. Never write `verified/verified_by/verified_at` directly — use the vault's own method.
3. The vault `create` guard (F2): create documents as sudo from the facades, after checking the caller's right yourself (own employee, or training group).
4. Renewal assignment creation must never raise out of the cron leg (savepoint per document) and must never double-create (`renewal_assignment_id` guard + `_guard_one_open`).
5. Migration must be idempotent and must not invent expiry dates where the survey has no validity.
6. Commits (explicit paths): (a) `feat(training): certificate record fields + migration + validity on test certificates`; (b) `feat(training): uploads, wallet page, learning record PDF`; (c) `feat(training): renewal ladder + auto re-assignment`; (d) `feat(training): Certificates lens, Overview and Numbers tiles`; (e) demo data + docs/report.

## 5. Design bar (verbatim)
"extreme WOW, intuitive, out-of-this-world experience, best in class." Hero moments: the
register's one-sentence status; the wallet's next-to-expire card with a single "Start
renewal" button; the record PDF that reads like a transcript. Zero dead ends: every state
word says what happens next ("Expires in 12 days — renewal course assigned, due 14 Nov").
Plain language everywhere; Lucide icons; quiet board; Chrome-validated.

## 6. Demo data (payobook only, registered with `pb.demo.seed`, names "DEMO …")
- Set `certification_validity_months = 12` on survey 17 ("DEMO Agronomist basics — test");
  the migration then stamps document 145's expiry.
- Create for two DEMO employees (pick from the register "DEMO HR programme data", e.g.
  20208/20209): "DEMO Forklift operator licence" (LIC, statutory, expires in 20 days),
  "DEMO First aid certificate" (CERT, upload, expires in 75 days), "DEMO Pesticide handling
  permit" (LIC, statutory, expired 10 days ago). Register all rows.
- Run the cron once in test mode on payobook after deploy and report what it did (renewal
  assignment created for document 145 only if inside the 60-day window — it will not be;
  say so).

## 7. Numbered test cases (`pb_training/tests/test_certificates.py`)
- **T1** A passed test with validity 12 files a document with `training_source='test'`, `attempt_id`, `expiry_date = issue + 12 months`, name with the year; validity 0 → `expiry_date False`.
- **T2** Passing the same test again a year later files a **second** document and sets `renewed_by_id` on the first; `_already` no longer blocks it; the resume line path (hr_skills_survey) still runs without error.
- **T3** Migration dry-run on a fixture: existing "— certificate" rows get source test/claim; expiry only when the survey has validity.
- **T4** `training_state`: valid / soon (inside `renew_before_days`) / expired / none / renewed; `_search` works in a domain.
- **T5** Employee upload: 11 MB → UserError in plain words; `.exe` → UserError; a good PDF → document `upload`, unverified, attachment owned by `hr.employee`; a user without an employee → AccessError.
- **T6** HR `add_certificate` verb → verified via the vault's method; a plain user calling the verb → `allowed False`/AccessError.
- **T7** Renewal leg: a test document expiring in 59 days → one renewal assignment (reason `renewal`, due = expiry); running the leg again → no second one; an open assignment already on that course → none created and no error; course archived → none.
- **T8** Ladder: keys `x60/x30/x7/x0/xm14/xh0` fire once each at the right day offsets; cap respected; `cert_reminders` off → nothing; renewed rows skipped; nothing after expiry day.
- **T9** Templates render on a document without error; subject contains `valid_words`; no "Odoo", no `#4F46E5`.
- **T10** `certificates_board` filters: expiring_30/60/90 counts match an independent recomputation; search ignores accents; department filter uses child_of; paging.
- **T11** Overview `certificates` block and headline fragment; Numbers tiles and `by_certificate` add up; spreadsheet has the Certificates sheet.
- **T12** Record PDF renders for an employee with 0, 1 and many rows; route refuses another employee's id for a plain user; allows it for a trainer.
- **T13** Home card and counter; wallet page lists own documents only; a second employee's document never shows.
- **T14** Whole suites green: `/pb_training,/pb_learning_hub,/pb_employee_vault,/pb_me_portal`.
- **T15 Chrome walk** (local then live): Certificates lens tiles/filters/row actions/Add drawer; My learning "My certificates" + Start renewal; wallet page upload with a real PDF; record PDF downloads; Overview headline; Numbers tiles; VI labels fit the rail. Console clean.

## 8. Deploy and verify
- Tier: **normal** (new fields and a migration on an existing module; no new module; no access
  changes) — but take backups anyway because the migration writes existing vault rows
  (one `pg_dump -Fc` per DB; ~1 min). Check `hr_skills_survey` is installed on every DB
  first; `-i` it where missing (p0clone first).
- Same ritual as L0 §8.2: deploy-notes START, flock, stage named modules from `git archive
  HEAD` (`pb_training` + `pb_import_kit` if icons changed), scoped rsync, cron snapshot,
  stop, `-u pb_training` per DB one at a time starting with p0clone, asset signal/purge/
  version bump, start, warm, cron re-check, latest_version check, live Chrome walk on
  payobook.com, DONE line. Stop at the deploy gate and wait for Fable's "GO DEPLOY".
