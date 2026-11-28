# RIZE Wave 2 — Phase A3: `pb_hiring` — BGV, documents, offer, closure, cover, agency, analytics

A1 and A2 are live. A3 finishes Hiring: from "we have decided" to "they are a
new joiner on day one", plus recruiter cover, the agency tag and the Insights
lens. Bump `pb_hiring` to `19.0.1.2.0`; two new routes ⇒ a migration.

Read first: `RIZE_LEDGER.md` (all, through the newest R), `RIZE_W2_HANDOVER.md`
A/B/C1, `RIZE_W2_PA1_HIRING.md` §1, `RIZE_W2_PA2_INTERVIEWS.md` §1, **the A2
report's API section as recorded in the ledger's Wave 2 table**, then this
file. Read the A1/A2 code before writing. Facts below marked verified were
checked 2026-09-15.

---

## 0. Scope and non-goals

**In scope:** `pb.hiring.bgv` checklist with uploads (blocks offer drafting);
document request to the candidate with a 2-day deadline, reminders and a
token upload page; `pb.hiring.offer` — salary proposal lines, hiring-manager
→ HR-lead route, country offer letter rendered through the letter engine's
templates, candidate review token page (accept / decline / comment),
"Record signed" by hand (D12) with the signed copy; closure — applicant
hired, employee created through the ORM, the pay package created for the
Comp team, the SAME onboarding path a Zoho arrival takes, position filled
when headcount is reached, careers page unpublished, hiring manager +
recruiter's manager told; recruiter cover with its own route; agency tag on
the requisition with the vendor card counting hires; the **Hiring** lens on
the Insights hub with XLSX; `/my/hiring` gains the offer state; ⌘K
3570/3580.

**Non-goals:** e-signature (D12), LinkedIn (D12), editing wave-1 modules
beyond the two additive inherits named below, any change to A1/A2 routes.

---

## 1. Verified facts

- **Letter engine:** `pb.hr.letter.employee_id` is **required** (`pb_lifecycle/
  models/letter.py:91`) and `_placeholder_values()` (:133) reads the
  employee — so a CANDIDATE letter cannot be a `pb.hr.letter`. Use the
  TEMPLATE side only: `pb.letter.template` (:57, `letter_type` from
  `LETTER_TYPES`, body with `${placeholder}` holes, `placeholder_help` :80)
  — add `('offer', 'Offer letter')` via `selection_add` in `pb_hiring`,
  seed one company-less template per country you need (Vietnam + a generic;
  R8 `company_id eval=False`), and render on `pb.hiring.offer` with your
  own placeholder dict (candidate_name, job_title, department, company,
  start_date, monthly_total, annual_total, currency, location, manager,
  date). Clone the escaping (:170) and the PDF path (`_make_pdf` :193 —
  read how it renders `rendered_html` to PDF and reuse the same report /
  wkhtml call; never `report.sudo()` R89). At closure, file the signed
  copy into the vault as `pb.employee.document` (category "OTHER" code,
  `pb_employee_vault/data/document_category_data.xml:37`) on the new
  employee — the vault's `create` has HR/system gates (`employee_document.py:100-114`),
  write as the system with `_vault_sys_write` semantics.
- **Pay package:** `pb.employee.comp.employee_id` required (`pb_comp_ben/
  models/employee_comp.py:39`), `effective_date`, `state` draft/active,
  `line_ids` of `pb.employee.comp.line` (`name, kind (COMP_KINDS), amount,
  period (COMP_PERIODS), checked, note`, :288-330); `action_activate`
  refuses while a line is unchecked (:122-146, R64). Import `COMP_KINDS` /
  `COMP_PERIODS` from `pb_comp_ben.models.comp_common` (verify the names
  there). The offer therefore carries its OWN lines (`pb.hiring.offer.line`,
  same shape) and creates the package at closure with `checked=True` (a
  human typed each line on purpose) and `effective_date = start_date`,
  left in `draft` for the Comp team.
- **Applicant → employee:** `hr.applicant.create_employee_from_applicant()`
  (`hr_recruitment/models/hr_applicant.py:993-1022`, verified on the
  server) creates the partner if missing, creates the employee from
  `_get_employee_create_vals()`, copies CV attachments, then writes
  `job_id, job_title, department_id, work_email = company email or
  email_from, work_phone`. Call `_get_employee_create_vals()` yourself and
  create through the ORM (R14: version fields), then write `work_email =
  candidate email`, `parent_id = reporting manager`, `company_id`. Joining
  date: `first_contract_date` is NOT writable (R77) — create the contract
  the way P10 does (`pb_contract_lifecycle/models/contract_extension.py`,
  `contract_common.term_end`) with `date_start = start_date`, wage = the
  offer's basic line, so `pb_people._join_date` finds it. Stage: the job's
  `hired_stage=True` stage (live: 6 "Contract Signed"), else the last stage.
- **Onboarding path (the SAME one a Zoho arrival takes):**
  `pb.zoho.pipeline._open_case(employee, case_type, anchor_date, company)`
  (`pb_zoho_bridge/models/zoho_pipeline.py:555` → `(case, created)`),
  `_auto_create_login(employee, company, summary)` (:~632, D6 — pass a
  `summary = {'logins': 0, …}` dict; read the method for the keys it
  increments), `_after_onboard(case, rec)` (:627; `pb_onboarding` extends
  it at `zoho_pipeline_ext.py:26` and calls `case.setup_onboarding()`).
  `rec` is the arrival dict — pass `{'name': employee.name}` at minimum
  (read what `_after_onboard` and its extensions read from `rec`). All of
  it under `_leg()` savepoints (R131); idempotent on re-run (R30: a second
  call finds the running case).
- **Vendor register:** `pb.vendor` (`pb_vendor_access/models/pb_vendor.py:39`):
  `name, vendor_type, contact_name, contact_email, contact_phone,
  department_id, responsible_user_id, country_id, company_id,
  agreement_ids`. Live: 11 "Talent Partners" (`recruitment`, company 5), 12
  Cloudline (`it`). Cross-module pointers are declared in the module that
  OWNS the pointer (`linked_models.py` docstring) — `pb_hiring` adds
  `agency_vendor_id` on the requisition (domain `vendor_type =
  'recruitment'`) and an inherit on `pb.vendor` with computed
  `hiring_count` / `hiring_avg_days` + a stat button on the vendor's native
  form via view inheritance. `pb_vendor_access` is NOT edited.
- **Insights lens:** `INSIGHTS_LENSES = "pb_insights_hub_lens"`
  (`pb_insights_hub/static/src/js/insights_hub.js:97`); clone
  `pb_budget/static/src/js/budget_palette.js:17-29` (Budget = 20). **Hiring
  = 30.** XLSX precedent `pb_budget/models/budget_export.py:73 _xlsx(board)`
  (openpyxl, styles, column widths).
- **Stage log / reschedules / no-shows** come from A2 (read its report row
  in the ledger for exact names). `utm.source` on the applicant is the
  source; "Referral" is id-by-name.
- **Token pages:** the A2 feedback page and `pb_lifecycle/controllers/
  token_pages.py` pattern; uploads = multipart POST, `ir.attachment` with
  `res_model/res_id` on the offer, ≤ 5 MB, pdf/jpg/png/doc/docx, filename
  slugged with accents folded (R28).
- **Cover:** NOT `pb.access.delegation` (too heavy). `pb.hiring.cover`
  below. The facade's recruit gate (`_require_recruit`) must accept an
  active cover.
- **Actors:** as A1/A2 (recruiter `rize.w2.recruiter@example.com` /
  `RizeW2!2026`, hiring manager uid 2336, manager uid 2326, finance/hr_lead
  seats on company 5 — borrow and put back as A1 did, R123). Candidate =
  A2's selected applicant on "RIZE W2 Site Agronomist" (email
  `@example.com`).

---

## 2. Models

- **`pb.hiring.bgv`** (one per selected applicant; `applicant_id,
  requisition_id, state` open/complete/flagged, `item_ids`) and
  **`pb.hiring.bgv.item`** (`bgv_id, name, required, result` pending/ok/
  flag/na, `note`, `attachment_ids`). Seed items from **`pb.hiring.bgv.template`**
  rows (company-less R8, each its own xmlid R58): Identity, Highest
  qualification, Previous employer 1, Previous employer 2, Two references,
  Criminal record (optional). `complete` when every required item is
  decided; `flagged` if any `flag` — the offer door then needs the HR
  lead's explicit "proceed anyway" (a button gated on `_require_write`,
  logged).
- **`pb.hiring.docreq`** (`offer_id, token, deadline` = 2 days from send in
  the company's calendar days, `state` sent/partial/complete/expired,
  `item_ids`) and **`pb.hiring.docreq.item`** (`name, required, received_at,
  attachment_id`) from **`pb.hiring.doc.template`** seeds: Passport / ID,
  Degree certificate, Last payslip or offer, Bank details, Photo, Tax code
  (optional). Daily reminder while not complete (idempotent, one per day,
  `pb_hiring.doc_reminder_days` 1), the recruiter gets an activity at the
  deadline.
- **`pb.hiring.offer`** (`requisition_id, applicant_id, bgv_id, docreq_id,
  start_date, job_title, currency_id, line_ids, monthly_total,
  annual_total` (computed from lines: `monthly` ×12, `annual` ×1, `once`
  ×1 — mirror comp's periods), `letter_template_id` (offer type, by the
  requisition's country), `rendered_html, attachment_id` (PDF),
  `signed_attachment_id, signed_on, token, candidate_decision`
  (pending/accepted/declined) + `candidate_comment`, `state`: draft →
  submitted → manager_ok → hr_ok (approved) → sent → accepted|declined →
  signed → closed. Route `hiring_offer`: `manager_step` = the hiring
  manager (`_approval_manager_uids` → requester uid, as the JD) then
  `role_step('HR lead','hr_lead')`; facts: monthly total (unit = currency),
  start date, job title; revision values: lines + start date (a changed
  number reopens the route, AM32). Doors: `draft_offer` (refused until
  BGV complete or overridden), `submit`, `send_to_candidate` (mails the
  PDF + token link; needs docreq complete? NO — the sheet orders documents
  BEFORE the offer prep; enforce: docreq `complete` before `send`, with a
  "send anyway" for the HR lead), `record_signed` (upload), `close`.
- **`pb.hiring.cover`** (`recruiter_id, cover_user_id, date_from, date_to,
  reason, state` draft → submitted → approved → active → ended | refused;
  route `hiring_cover` = one `manager_step` = `recruiter_manager_id` of
  the recruiter's requisitions — resolve via the country rule
  (`rule_for`) or the recruiter's own employee manager; say which in
  `_chain_title`). Active cover ⇒ `_require_recruit` passes for
  `cover_user_id` on every requisition whose `recruiter_id` is the covered
  recruiter; a chatter line on each requisition at start and end; the
  daily job ends covers past `date_to`.
- **Requisition additions:** `agency_vendor_id`, `selected_applicant_id`
  (A2), `offer_ids`, `filled_count` (hired applicants), `filled_on`;
  `_on_filled()`: `state='filled'` when `filled_count >= headcount`,
  `job_id.website_published=False`, mails to hiring manager + recruiter's
  manager (templates), `referral_open=False`.
- **`pb.hiring.analytics`** AbstractModel (company-scoped, no sudo in
  reads, date range `from`/`to` on `opened_on`): time to fill (opened →
  filled, median + mean), time to offer (opened → first `sent`), time in
  stage (stage log: mean days per stage), offer acceptance (accepted /
  sent), source effectiveness (applicants + hires per `utm.source`),
  delays (reschedules by `delay_kind`), no-shows by `no_show_by`, agency
  vs in-house time to fill. `export_xlsx(range)` → `ir.attachment` and a
  download door (clone the budget export). Empty months read "No requests
  opened in this range" (R27).
- **Security:** ladder as A1; PAIR rules; the offer's candidate fields
  never in a payload the board sends to a plain user; tokens never in a
  view (R13).

## 3. Screens
- Board drawer → the selected applicant's **path strip**: BGV → Documents
  → Offer → Candidate → Signed → Day one, each a chip with its state and a
  door. BGV panel (items, result dots, upload, "Proceed anyway"); Documents
  panel (items, received, "Send request", "Remind now"); Offer panel
  (lines editor with kind/period/amount, totals, template picker, "Preview
  letter", Submit, Send to candidate, Record signed (+ upload), Close);
  cover banner ("Covered by X until 20 Sep"); agency chip. Hero KPI tiles
  gain "Offers out" and "Filled this month".
- Token pages (portal theme, no login): `/hiring/d/<token>` document
  upload (items, per-item upload, progress, deadline, thanks); `/hiring/o/
  <token>` the offer (PDF embed + download, Accept / Decline with a
  comment, thanks; `used` shows their decision). Mobile-first — a
  candidate opens these on a phone.
- Insights → **Hiring** lens (`pbim`): range picker, 8 tiles, three
  tables (stages, sources, delays), "Download Excel". Empty state teaches.
- `/my/hiring`: requests I raised show the offer chip and "waiting on you"
  when the offer route waits for the session user.
- ⌘K: `hiring_analytics` 3570 ("Hiring numbers", Insights),
  `hiring_cover` 3580 ("Cover for a recruiter").
- Switches: `pb_hiring.doc_deadline_days` 2, `pb_hiring.doc_reminder_days`
  1, `pb_hiring.offer_mail` 1, `pb_hiring.closure_mail` 1,
  `pb_hiring.create_contract` 1 (the closure creates the contract; off =
  employee only, logged).

## 4. Tests
T1  Unit tests + gates; `-u` on a DB with A1/A2 data lays `hiring_offer`
    and `hiring_cover` once (migration idempotent).
T2  BGV: draft offer refused while an item is pending (sentence names the
    items); decide all → allowed; a `flag` → refused until "Proceed anyway"
    by the HR-lead gate, logged.
T3  Document request: send → mail with the token link; page renders on a
    phone viewport; upload two of five → `partial`, reminder job sends one
    mail per day (run twice same day → one); upload all required →
    `complete`; a 6 MB file refused with a sentence; a `.exe` refused.
T4  Offer: three lines (basic monthly 25,000,000 ₫, allowance monthly
    2,000,000 ₫, sign-on once 10,000,000 ₫) → monthly 27,000,000, annual
    334,000,000; letter preview renders every placeholder (no `${` left);
    submit → hiring manager (uid 2336) in the inbox → HR lead → `hr_ok`;
    change a line → the route reopens (revision).
T5  Send to candidate refused while docs incomplete (HR-lead "send anyway"
    works); send → mail with PDF attached + link; `/hiring/o/<token>`
    shows the PDF; Accept with a comment → `accepted`; a second visit
    shows the decision; a declined offer leaves the applicant in place and
    tells the recruiter.
T6  Record signed with a PDF → `signed`; close → applicant on the hired
    stage, employee created (name, work_email = candidate email, job,
    department, manager, company 5), contract with `date_start` = start
    date, pay package in draft with 3 checked lines and the right totals,
    onboarding case opened once (call close twice → still one case),
    login created per D6 (credentials mail held), the signed copy filed
    in the vault, two closure mails, `filled_count` 1 of 2 → still
    `open`; a second closure → `filled`, careers page unpublished,
    referrals closed.
T7  Cover: request as the recruiter → the recruiter's manager approves →
    active; the cover user can `publish`/`screen` on the recruiter's
    requisitions and NOT on another recruiter's; the daily job ends it
    after `date_to`; chatter lines present.
T8  Agency: set Talent Partners on a requisition → hiring manager mailed;
    the vendor form shows "Hires 1" after T6; analytics splits agency vs
    in-house.
T9  Analytics lens: numbers equal a psql/Python recomputation over the
    same range for time to fill, offer acceptance and sources; XLSX
    downloads and opens (openpyxl re-read: sheet names + a spot value);
    empty range shows the sentence.
T10 `/my/hiring` as uid 2336: offer chip + "waiting on you" while the
    route waits on them.
T11 Chrome light + dark: drawer path strip, offer panel, both token pages
    at 390px width, Insights lens; screenshots `RIZE/w2_a3_*.png`; no
    console errors; `unhandledrejection` listener.
T12 ⌘K 3570/3580; Insights lens `hiring` at 30 in `pb_insights_hub_lens`.
T13 Deploy: `19.0.1.2.0` landed, migration ran, crons active, service up,
    real log clean.
T14 Reverts: seats and groups against snapshot, passwords, mails
    cancelled; the new employee, contract, package, case and login STAY
    (demo, D9) and are listed for the owner with the login.

## 5. Report back
As A2, plus the closure chain's exact call order (for the closeout), the
seeded letter templates, the vendor-card inherit, what the analytics reads,
owner items (real agency, real templates, the `create_contract` switch).

## Demo-data rule (owner, 2026-09-16 — D18, ledger binding rule 9)
Every demo record this phase creates on `payobook` is KEPT for future demos, so it
must NOT carry the customer name ("RIZE"/"Rize") anywhere a viewer can see — names,
subjects, notes, chatter, logins, emails, job/department titles, letter bodies. Name
them starting with **DEMO** ("DEMO Town hall"), logins `demo.<role>@example.com`.
Register every one at creation, in the fixture code:
`seed = self.env.get('pb.demo.seed'); if seed is not None: seed.register(records, label)`
(the guard keeps `pb_demo_seed` optional on tenants). The report carries a "Demo
records" table (model, ids, label) and the register count. Any "named RIZE W2" wording
left in this file is superseded by this section.
