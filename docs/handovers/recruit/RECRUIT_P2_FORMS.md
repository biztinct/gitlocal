# RECRUIT — Phase 2: application forms the talent lead builds, in three languages

Delivers register lines **G-01, G-02, G-22, G-23, G-27, G-29** and the consent capture
half of **G-45** (retention/purge stays in P4): a per-role application-form builder with a
template library and own questions, required files that cannot be skipped, expected pay,
a country pick-list, a consent tick with market wording, a duplicate flag at apply time,
and English / Vietnamese / Bahasa Indonesia versions of every form, of the confirmation
page and of the "Application received" email. Recruiter-side screens stay English
(ruling R11 / RC-D2).

Read first, in order: `docs/handovers/recruit/RECRUIT_LEDGER.md` (all, including the
rows P1 appended), the **P1 phase report** (the API shapes it left: `get_setup` cards,
`journey_stage` payload, `get_timeline`), `docs/design/rize-hiring-experience.html`
(section "Application form builder" and "Rules that bind every screen"), register lines
above, then this file. Everything marked **verified** was checked on 2026-09-30 against
the repo — do not re-derive it. P1 may have moved line numbers inside `pb_hiring`; the
facts still hold, re-locate by name.

---

## 0. Scope and binding non-goals

**In scope (P2):**
1. `pb_hiring` **19.0.2.1.0** (P1 left it at 19.0.2.0.0).
2. Models `pb.hiring.form` and `pb.hiring.form.field` (§2.1), answers on the applicant,
   the role's form (`pb_form_id`), a seeded template library (Standard, Field roles,
   Senior roles, Tech roles) per company, idempotent.
3. The **Application forms** screen inside Hiring set-up (P1's card becomes live):
   list, live preview (the real public page in an iframe, in the language being edited),
   side panel with drag reorder / required toggles / inline label editing / "Add a
   question" / language tabs with a "N missing" nudge / "Use this form for…".
4. The **public apply page** rebuilt from the form definition: one column, progress line,
   inline validation, file drop zones, language switch, brand header; the Rize frame
   (`rize_website.rz_application`) keeps working unchanged.
5. Server-side enforcement: required fields (files included), file types and sizes,
   consent required, phone format by country when `phone_validation` is installed.
6. **Duplicate flag** at submit (same email or phone in the company in the last 6 months):
   `pb_possible_duplicate_id` + a chip on the card and drawer ("Possibly the same person
   as …", opens the other record) + "Same person" link action. No merge yet (say so).
7. **Languages**: install `id_ID` on the three DBs, add `vi_VN` + `id_ID` to the website's
   languages, translatable form labels/help/options/consent text, `pb_hiring/i18n/id_ID.po`
   (new) and `vi_VN.po` entries for every public-page chrome string, `hr.applicant.pb_lang`
   captured from the page language, the `received` message rendered in that language.
8. The drawer's new "Answers" section (P1 drawer) showing the candidate's answers in the
   order of the form, files with preview links, the consent line.
9. Tests (§5), deploy to payobook / rize / payobook_template (never abm), Chrome
   validation light + dark on payobook.com incl. the PUBLIC page on a phone-width viewport,
   phase report.

**Binding non-goals:** retention months and purge (P4); Share-with / money masking
(P4); email language versions other than the `received` message (P8); automations
(P8); the careers listing page and job detail page design (Rize put the careers page on
hold — do not restyle `rz_jobs_index` / `rz_job_detail`); CV parsing; assessments
(deferred); agency submissions (P7); the stock `/website/form/` route (leave it; our
route replaces it for our jobs); Odoo's website editor / form builder plugin (do not use
it; the builder is ours).

---

## 1. Verified plumbing facts (do not re-derive)

### 1.1 Apply flow today (`pb_hiring/controllers/application.py`)
- `class HiringApplications(WebsiteHrRecruitment)` :27 overrides `jobs` :46-49, `job`
  :51-54, `jobs_apply` :56-63 with bare `@http.route()` (path/flags inherited from stock
  `website_hr_recruitment/controllers/main.py:190-201`, `/jobs/apply/<model("hr.job"):job>`,
  public, website=True). `_pb_hiring_public_job` :28-31 → `hr.job.pb_hiring_accepts_applications`
  (`hr_job_ext.py:19-30`). Render helper `_pb_hiring_render` :65-72 (context: job, brand,
  values, role_country, role_location, error, done, authorizations, relocations).
- Submit `/hiring/apply/<int:job_id>` POST, public, website=True :74; CSRF on. Reads
  name/email/phone/location/linkedin/portfolio/authorization/relocation/motivation :79-80;
  validations :82-106 (honeypot `company_website` + session `pb_application_opened`,
  30 s throttle `pb_application_last`, required set, `email_normalize`, `clean_url`,
  choice keys, 150–250 words, CV present, 5 MB, suffix pdf/doc/docx, magic bytes
  `%PDF` / `PK` / `\xd0\xcf\x11\xe0`).
- Attribution `_pb_hiring_touch` :33-44 (utm_* 200 chars, referrer, landing_url via
  `clean_url` :15-24; session `pb_hiring_attribution` first/latest).
- Create :107-125: vals incl. `pb_requisition_id`, `pb_location`, `pb_linkedin`,
  `pb_portfolio`, `pb_work_authorization`, `pb_relocation`, `pb_motivation`,
  `pb_first_touch`, `pb_application_touch`; utm records searched/created :116-121; sudo
  create in a savepoint :122-123; CV → `ir.attachment` res_model hr.applicant, public
  False :124-125. Field defs `journey.py:65-74`; touch fields write-blocked :79-80.
- Confirmation :126-132: `pb.hiring.message.template` key `received` for the company,
  only if `flag(env, 'pb_hiring.candidate_mail')` (`hiring_common.py:37`, default '1' :64,
  `flag()` :345-349); `_render` `{{token}}` substitution `journey.py:256-272`; model
  `journey.py:243-254` (keys received, phone, assignment, on_hold, cv_reject; body is
  plain Text, NOT translatable today). Thank-you = same template `done=True` :134;
  `UserError` re-renders with error :135-136.
- Template `pb_hiring/views/application_templates.xml`: single `application_journey` :2
  (calls `website.layout`; root `main.pb-apply > .pb-apply-wrap`; heading :5; done :6; form
  :7 multipart → `/hiring/apply/<id>`; csrf :8; honeypot :9; error :10; nav :11; sections
  `#personal` :12-17, `#profile` :18-22 (portfolio "Optional", cv accept .pdf,.doc,.docx),
  `#fit` :23-27; footer sentence :28, no checkbox). Labels hard-coded English; select labels
  from `AUTHORIZATION`/`RELOCATION` constants `journey.py:22-26` (not `_()`).
- Styles `pb_hiring/static/src/scss/portal_hiring.scss:491-507` `.pb-apply` (literal
  colours #f7f8fc / #241f52 / #5a4bb0 / #e6e3ef / #dcd8e8 / #6d6982; card radius 20, button
  9; grid → 1 col ≤600px). `.pbhf-*` token pages :231+. `/my/refer` uses `.pbme .pbhr`
  (`portal_templates.xml:102`); `.pbme` kit `pb_me_portal/static/src/scss/me_portal.scss:6-9`
  includes `pbim-root-vars`.
- **Rize frame**: `rize_website/views/careers_templates.xml` `rz_application` :180-190
  inherits `pb_hiring.application_journey`, priority 90, REPLACES `main.pb-apply` with
  `rz_shell` wrapping `$0` — so the new page MUST keep a root `<main class="pb-apply">`
  or the Rize frame breaks. `rz_job_detail` :98 links to `/jobs/apply/<slug>` :149/:170.
  `rz_job_thanks` (`pages_templates.xml:41-54`) is the STOCK thank-you page, unused by
  us. Rize tokens `rize_website/static/src/scss/rize.scss:8-18` (`--rz-night #07110A`,
  `--rz-forest #101F0B`, `--rz-gold #CC9900`, `--rz-cream #FAEED3` …); `.rz-site .pb-apply`
  overrides :877-915 (cream card, gold pill button). No `rize_website/i18n`, no lang handling.
- Stock form for reference only: `website_hr_recruitment/views/website_hr_recruitment_templates.xml`
  `apply` :177 posts to `/website/form/` (`data-model_name="hr.applicant"`); whitelist
  `data/config_data.xml:21-37`; properties expansion `website/models/website_form.py:32-120`
  (forces required=False :112). We do not use it.

### 1.2 Properties, survey (facts; NOT the chosen mechanism)
- `hr.job.applicant_properties_definition` (`hr_job.py:79`), `hr.applicant.applicant_properties`
  (`hr_applicant.py:136`), core `odoo/orm/fields_properties.py` (`ALLOWED_TYPES` :80-87;
  html names must end `_html` :1027-1031). Properties are per-job, not per template, have no
  per-language labels and the website builder forces optional — hence our own models.
- `hr_recruitment_survey` is an interview form sent to an EXISTING applicant
  (`hr_job.survey_id` :9, `hr_applicant.response_ids` :12, `action_send_survey` :34-67);
  pb_hiring does not depend on `survey`. Not the apply form.

### 1.3 Languages
- `id_ID` exists in base (`odoo/addons/base/data/res.lang.csv:41`, "Indonesian / Bahasa
  Indonesia", url_code `id`); `vi_VN` :92 (url_code `vi`). Neither `id_ID` nor any `id`
  `.po` exists in custom modules; `pb_hiring/i18n/vi_VN.po` has 35 msgids (board only).
- Website language routing: `http_routing/models/ir_http.py` `_match` :323, order URL
  prefix → `frontend_lang` cookie → context → website default :404-409; redirects
  :419-460; `website/models/website.py` `language_ids` :124-126, `default_lang_id` :128,
  `auto_redirect_lang` :129; `website/models/ir_http.py` `get_nearest_lang` :273,
  `_get_default_lang` :285-289. A page reached as `/vi/jobs/apply/...` renders with
  `request.env.lang = 'vi_VN'` once `vi_VN` is in `website.language_ids`.
- Translatable fields: `fields.Char(translate=True)` examples `pb_hiring/models/bgv.py:48`,
  `panel_feedback.py:51`, `docreq.py:49`; ORM `update_field_translations` (`odoo/orm/models.py:3498`,
  `_update_field_translations` :3510), `get_field_translations` :3670 — signature
  `get_field_translations(field_name, langs=None)` → `(translations, context)`;
  `update_field_translations(field_name, {lang: value})`. Web dialog `web/static/src/views/fields/translation_dialog.js:9`
  (calls at :77 / :103) — reference for the RPC shape; no pb JS uses it yet.
- Login page language `pb_login_language/controllers/main.py:10-45` (select shown when
  >1 language installed) — unaffected, but installing `id_ID` will make it appear there
  with three choices; that is fine and expected.

### 1.4 Attachments, duplicates, tests
- `web.max_file_upload_size` read `web/models/ir_http.py:92-95`; pb document requests use
  `UPLOAD_MIME_OK` (`hiring_common.py:317`) + `UPLOAD_MAX_BYTES` 5 MB (:326) enforced in
  `docreq.py:322-351` — reuse these helpers for form files.
- `hr.applicant.email_normalized` :55 (trigram), `partner_phone_sanitized` :65-66,
  `application_count` :135, `_compute_application_count` :256-300 (email, phone,
  linkedin). Stock `check_recent_application` `website_hr_recruitment/controllers/main.py:203-261`
  (6-month window logic to copy). No `candidate_id` / `hr.candidate` on this build.
- No HttpCase in `pb_hiring/tests`. Patterns: `website_hr_recruitment/tests/test_website_hr_recruitment.py:105-106`
  (`authenticate(None,None)` + `url_open`), `pb_onboarding/tests/test_portal_pages.py:20,32,63-67`;
  `url_open` signature `odoo/tests/common.py:2336`. `phone_validation` is a core addon —
  check `ir_module_module` state before relying on it; guard with `env.get('phone.validation.mixin')`
  or `'phone_validation' in env.registry._init_modules` style checks (verify the idiom).

### 1.5 P1 leaves you
- Hiring set-up screen (`pb_hiring_setup` client action) with the "Application forms" card
  pointing at the old "Recruitment identity" settings form — replace its action with the
  new Forms screen. `get_setup()` cards shape from the P1 report.
- The candidate drawer (sections: hero, Next, scorecards, timeline, documents) — add
  "Answers" between hero and Next? No: after Next, before scorecards.
- The role Details tab — add "Application form: <name> · Change".

---

## 2. Architecture

### 2.1 Data
- `pb.hiring.form`: `name` (Char, translate), `company_id`, `is_template` (Boolean; a
  template is what "Use this form for…" copies from — a role always gets its OWN copy so
  edits never leak across roles), `origin_template_id`, `requisition_id` (the role that
  owns a copy; empty for templates), `language_codes` (Char, comma list of enabled codes
  among en_US/vi_VN/id_ID; default all installed), `consent_text` (Text, translate;
  default "I agree that <brand> keeps my application for <N> months to consider me for
  this and similar roles." — the `<N>` is filled from the company's `pb_retention_months`
  Integer, default 12; P4 adds the purge), `field_ids`, `active`, `sequence`,
  `is_default`. `_compute_missing_translations()` → `{lang: count}` for the nudge.
- `pb.hiring.form.field`: `form_id`, `sequence`, `kind` Selection —
  built-ins (fixed key, cannot be deleted, some cannot be un-required): `name`*, `email`*,
  `phone`*, `country`* (pick-list `res.country`), `city` (text), `linkedin`, `cv`* (file),
  `portfolio` (file or link, mode Selection file/link/either), `expected_pay` (money +
  currency from the role's country), `authorization` (choice, seeded options), `relocation`
  (choice), `motivation` (long text with min/max words), `consent`* (always last, always
  required); custom kinds: `short_text`, `long_text`, `choice`, `multi_choice`, `yes_no`,
  `number`, `date`, `file`, `link`. Fields: `key` (Char; built-ins fixed, customs
  `q_<slug>` unique per form), `label` (Char translate), `help` (Char translate),
  `placeholder` (Char translate), `options` (Text translate, one per line), `required`,
  `min_words`, `max_words`, `file_kinds` (pdf/doc/image/zip set), `max_mb` (default 5,
  hard cap 15), `store_to` (computed from kind). `*` = required and locked.
- `hr.applicant`: `pb_form_id`, `pb_form_answers` (Json `{key: value}`; files stored as
  `ir.attachment` with `pb_form_key` Char on the attachment), `pb_country_id` (m2o
  res.country; also fill `pb_location` text for back-compat), `pb_lang` (Char code),
  `pb_consent_on` (Datetime), `pb_consent_text` (Text snapshot of the exact sentence in
  the language shown), `pb_possible_duplicate_id` (m2o hr.applicant), `pb_same_person_id`.
  Built-in answers ALSO land in the real fields as today (partner_name, email_from,
  partner_phone, pb_linkedin, pb_portfolio, salary_expected, pb_work_authorization,
  pb_relocation, pb_motivation).
- `pb.hiring.requisition.pb_form_id` (the role's own copy). On role create: copy the
  company's default template (or the one matching the role type, see seeds). "Change"
  copies another template (answers already given are untouched — they keep their keys).
- `pb.hiring.message.template.body` and `subject` become `translate=True`; the `received`
  render uses `with_context(lang=applicant.pb_lang)`.
- Seeds (idempotent, per company): templates **Standard** (name, email, phone, country,
  city, linkedin, cv, portfolio optional link, expected pay, "Where are you based right
  now?" short text, "Are you willing to relocate for this role?" choice, consent),
  **Field roles** (+ "Do you hold a driving licence?" yes/no, "Which provinces can you
  cover?" short text; no portfolio), **Senior roles** (+ motivation 150–250 words, notice
  period), **Tech roles** (+ portfolio REQUIRED file-or-link, "Link to code you are proud
  of" link). Vietnamese and Indonesian labels for every seeded label/option/consent
  (write them via `update_field_translations`; keep them in one Python dict in
  `data/form_seed_i18n.py`).

### 2.2 Public page
- Routes: keep `jobs_apply` override → renders `pb_hiring.application_journey` from the
  ROLE's form in `request.env.lang`; keep `/hiring/apply/<job_id>` POST; add
  `/hiring/preview/<int:form_id>` (auth user, website=True, `?lang=`) for the builder
  iframe (renders the same template with `preview=True`: submit disabled, banner "Preview
  — nothing is sent"). Keep `main.pb-apply` as the root element (Rize frame).
- Rendering is field-driven: one `t-foreach` over `form.field_ids` with a `t-call` per
  kind (`pb_hiring.apply_field_<kind>`); labels via the translated field values (the
  page is rendered in `request.env.lang`, so `field.label` already comes translated —
  verify by rendering `/vi/...`). Chrome strings ("Send my application", "Optional",
  "Drop your CV here or choose a file", "required", the progress line, error sentences)
  through QWeb `_()` → `.po` entries for `vi_VN` and `id_ID`.
- Language switch: top-right pills for the form's `language_codes` that are installed and
  on the website: link to the same path under the language's url_code (`/vi/jobs/apply/...`,
  `/id/...`, `/jobs/apply/...` for the default). The role's country PRE-SELECTS the language
  on first visit when no `frontend_lang` cookie: VN → vi, ID → id, else en (do this by
  redirecting once from `jobs_apply` when `request.env.lang` is the default and the role's
  country maps to another enabled language and no cookie is set).
- Progress line "N of M answered" updates client-side (tiny inline script, no framework);
  inline validation on blur; a required file shows a red sentence under the drop zone on
  submit attempt; the server re-validates EVERYTHING (the portfolio hole).
- Draft kept in `sessionStorage` per job (try/catch) so a failed submit or a language
  switch does not lose typed answers; files are never kept.
- Duplicate check happens server-side at submit (does not block; sets the flag).
- Thank-you: same page `done=True`, in the page language, with the brand line and "What
  happens next" (three plain sentences), plus the confirmation email in `pb_lang`.

### 2.3 Builder screen (Hiring set-up → Application forms), client action `pb_hiring_forms`
- Layout: left rail = forms (Templates section, then "Used by roles" section with the
  role name); centre = live preview iframe (`/hiring/preview/<id>?lang=<tab>`, reloads
  debounced 400 ms after a save); right = side panel: language tabs (EN / VI / ID with
  "N missing" badge), the field list (`useSortable` drag to reorder, required toggle,
  lock icon on built-ins, click a row → inline editor for label / help / placeholder /
  options / required / file kinds / words), "Add a question" (kinds list), "Add a built-in
  field" (the built-ins not yet on the form), footer "Use this form for…" (pick a role →
  copies; or "Make this the default template").
- Server API on `pb.hiring` (all `_require_write`): `get_forms()` → `{templates:[…],
  role_forms:[…], languages:[{code,name,installed,on_website}], can_edit}`;
  `get_form(id, lang)` → `{form, fields:[…], missing:{code:n}}` where labels come back for
  the requested lang AND `en_US`; `_act_form_save({id, lang, values})` (writes translated
  values for that lang via `update_field_translations` for translate fields and plain
  `write` for the rest); `_act_form_field_save`, `_act_form_field_add`,
  `_act_form_field_remove` (refuses locked built-ins with the sentence), `_act_form_reorder`,
  `_act_form_copy_to_role({template_id, requisition_id})`, `_act_form_set_default`,
  `_act_form_new_template({name, from_id})`.
- Hero moment: type a label in Vietnamese on the right and watch the real page change on
  the left. Zero dead-ends: a language not installed shows "Bahasa Indonesia is not
  installed on this system — ask your administrator" with the exact next step; a form
  with no role shows "Not used by any role yet · Use it for a role".

### 2.4 Board & drawer touches (P1 surfaces)
- Drawer "Answers" section (after Next): every field of the form in order — label (in
  the RECRUITER's language: English), value, files as links; consent line "Agreed on
  12 Oct 2026 (Tiếng Việt)". Duplicate chip on the card ("Possibly the same person") and
  in the drawer with "Open the other record" and "Same person" (sets `pb_same_person_id`
  both ways, no merge).
- Role Details tab: "Application form: Tech roles (copy) · Change · Preview".

---

## 3. Design (build to the blueprint)

The design bar, verbatim from the ledger: **"exceptional premium, extreme WOW, a novice
can work without training"** — hero moment (the live preview), zero dead-ends, plain
words, motion with purpose, keyboard + bulk ergonomics, measured against the best
form builders (Typeform / Tally), never against stock.

- Public page: single column, generous spacing, one question per row, big touch
  targets, drop zones with the file name after choosing, the language pills, the brand
  header (company `pb_hiring_brand`, `pb_hiring_intro`), the progress line, a reassuring
  footer sentence about who sees the application. Works at 360 px wide. Under the Rize
  frame it must still look right (check `/jobs/apply/...` on payobook.com — the frame is
  installed there? verify; if not, check the plain page and say so).
- Builder: the `pbim` kit; Lucide via `ic()`; side panel rows are one object (same
  padding/baselines); drag handle visible on hover; required toggle is a real switch;
  a locked built-in shows a lock with "Always asked" on hover.
- Every new user-visible string: `_t()` in JS / `_()` in QWeb / plain text in XML, and a
  Vietnamese entry in `vi_VN.po` + an Indonesian entry in `id_ID.po`, each with the three
  comment lines. Seeded form labels are DATA translations, not `.po` — keep the two apart.
- Dark: the builder follows `.pbhr` dark tokens from P1; the public page is light-only by
  design (it sits inside the client's website) — paint every colour explicitly.

---

## 4. Rules (plain English on screen)

- A role gets its own copy of a template; changing a template never changes a role's
  form ("Presets fill in new roles" pattern from P1 — say it on the screen).
- Locked built-ins (name, email, phone, country, CV, consent) cannot be removed or made
  optional. Portfolio required-ness is per form.
- Required means the server refuses the submission without it, files included, in every
  language. The error sentence names the field in the candidate's language.
- A language tab with missing translations still renders: the English label shows with
  a small "(English)" mark on the preview so the gap is visible, never a blank.
- Duplicate flag never blocks; it is a chip and a sentence.
- Consent text snapshot is stored with the answer; changing the wording later does not
  change what people agreed to.
- The `received` email goes out in the page language; if that language's text is empty,
  English is used and the drawer timeline says so.

---

## 5. Numbered test cases

Python (`tests/test_forms_p2.py`, `tests/test_apply_p2.py` (HttpCase)):
1. Seeds create the four templates per company with all fields, locked built-ins, and
   VI + ID translations on every label/option/consent; re-seeding changes nothing.
2. Creating a role copies the default template (or the role-type match); editing the
   copy leaves the template untouched and vice versa.
3. Locked built-ins refuse removal / un-requiring with the sentence.
4. `get_form(id,'vi_VN')` returns Vietnamese labels + English fallbacks + `missing` counts;
   `form_save` for `id_ID` writes only the Indonesian translation.
5. HttpCase: GET `/jobs/apply/<job>` renders the role's fields in order; GET `/vi/jobs/apply/...`
   renders Vietnamese labels once `vi_VN` is on the website.
6. HttpCase: POST without a required custom question → re-rendered with the field's error
   in the page language, nothing created.
7. HttpCase: POST without the required portfolio file on a Tech-roles form → refused;
   with a 20 MB file → refused; with a .exe renamed .pdf → refused (magic bytes).
8. HttpCase: full valid POST → applicant with real fields + `pb_form_answers` + files with
   `pb_form_key` + `pb_country_id` + `pb_lang` + consent snapshot; the `received` mail is
   queued in that language.
9. Second POST with the same email within 6 months → `pb_possible_duplicate_id` set,
   applicant still created.
10. Country VN + no cookie → first GET redirects to `/vi/...`; with a cookie → no redirect.
11. Preview route requires a login and never creates anything on POST.
12. Drawer payload includes `answers` in form order; timeline shows "Applied (Tiếng Việt)".
13. Existing tests still pass.

Browser (payobook.com, light + dark for the builder; the public page also at 360 px):
14. Hiring set-up → Application forms: the four templates listed; open Tech roles; preview
    shows the real page.
15. Switch to Tiếng Việt, edit a label → the preview updates within a second.
16. Drag a question above another → order changes in the preview.
17. Add a Yes/No question, mark required, fill VI and ID labels; missing badge drops.
18. Try to remove "Email" → the sentence, nothing removed.
19. "Use this form for <role>" → the role's Details tab shows it; the public page for that
    role shows the new question.
20. Public page as a candidate: language pills, progress line, drop zone, submit without a
    file → red sentence; submit complete → thank-you in the language; the confirmation
    email in the mail queue in that language.
21. Apply twice with the same email → the card shows the duplicate chip; drawer "Open the
    other record" works.
22. Rize frame: `/jobs/apply/...` under the Rize site frame still shows the form correctly
    (if `rize_website` is installed on that DB; otherwise state it).
23. No console errors; no red style bar; the login page now offers three languages and
    still works.

---

## 6. Deploy and verify

Tier = **risky** (new models, language install, translation loading). Backups of the
three DBs first. Language install per DB in the detached unit
(`res.lang._activate_lang('id_ID')` + add `vi_VN`/`id_ID` to `website.language_ids`,
via a small idempotent script run through `odoo-bin shell` with the service STOPPED,
or a post-init in the module guarded to run once) — expect `.po` loading for every
installed module; grep the log for translation errors. Then `-u pb_hiring` on payobook,
rize, payobook_template; asset purge + version bump + signaling row per DB; hash + version
checks; one Chrome walk on payobook.com (14–23), cheap checks elsewhere. Demo: apply as a
candidate on payobook only (register the applicants with `pb.demo.seed`). Commits per
feature; no push. Append gotchas RC-next; fill the P2 phase-log line.

## 7. Report back

Same format as P1 (§7 of `RECRUIT_P1_BOARD.md`): live where/versions/commits; tests
1–23; design-bar self-score; deviations; ledger rows + API shapes left for P3/P4
(`get_forms`, `get_form`, the answers shape, `pb_consent_*`, `pb_possible_duplicate_id`);
owner items (e.g. the consent wording per market, retention months default 12); demo
records table.
