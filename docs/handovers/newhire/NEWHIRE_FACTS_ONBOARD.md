# NEWHIRE — verified plumbing facts: everything around the new person

Scope: details, papers, bank, welcome link, joining checklist, sign-in, equipment, letters, custom fields,
Hiring hand-over, Learn impact, deploy. The core create path, pay scheme, contract and the studio shell are in
the sibling fact sheet. Target design: `docs/design/new-hire-studio-poc.html` (STEPS :398-405, vWho "From Hiring"
:428-439, vDocs :518-541, vWelcome :551-565, vCheck :568-594).

Read at worktree `gitlocal-worktrees/newhire`, HEAD `36dd3afcf` (origin/19.1), 2026-11-25. All paths are
relative to the repo root. **Do not re-derive these facts.** If a line has moved, grep the quoted name.

**White-label rule (binding on every implementer):** the word "Odoo" never appears in a user-visible string
(labels, help, toasts, mail bodies, PDFs, `.po` msgstr). Technical identifiers stay as they are.

**Two POC claims the code does not support today:**
1. **"Bank account, tax numbers and papers come across" from Hiring** (vWho :433, :439). Hiring stores **files
   only**. It has no typed bank, tax or ID value anywhere (§K3).
2. **"One welcome link that works on a phone, with no password"** (vDocs :526). Every `/my` page that writes is
   `auth='user'`. No public token page can write to the employee record, bank or documents (§B). The
   recommended link (§B5) asks the person to choose a password once.

---

## A. Employee self-entry on My Payobook

Every write route below is `type='http', auth='user'`. Every request model is approved through the one approval
engine (`biz.approval.chain.mixin` + `register_chain`). Approvers decide in the one Approvals inbox: client action
`pb_approval_inbox` (`pb_approval_config/views/actions.xml:30-32`), data model `pb.approval.inbox`
(`pb_approval_config/models/inbox_facade.py:86-87`).

### A1. `/my/profile` → `pb.profile.change.request` (pb_me_portal)

**Model:** `pb_me_portal/models/pb_profile_change_request.py:61`. It inherits `mail.thread` and
`biz.approval.chain.mixin` (:63).

**Fields:**
- `employee_id` (:69) and `note` (:71).
- Proposed values, all Char: `x_phone`, `x_private_email`, `x_address`, `x_emergency_contact`, `x_emergency_phone`
  (:74-78).
- Snapshots of the current values: `cur_*` (:81-85).
- `state`: `draft → hr_review → approved | refused` (:87-92).

**Rules:**
- The editable fields are a whitelist in the config parameter `pb_me_portal.editable_fields` (:36-37). It is
  seeded in `data/pb_me_portal_data.xml:15-18`.
- On create, a non-manager is forced onto their own employee record (:184-218).

**Routes** (`pb_me_portal/controllers/portal.py`):
- GET `/my/profile` (:163)
- POST `/my/profile/request` (:230)
- `/my/profile/request/<int:request_id>` (:258) and `.../submit` (:271)
- `/my/requests` (:303)

pb_form_studio_portal overrides `/my/profile` (`pb_form_studio_portal/controllers/portal.py:324-332`) and adds
`/my/profile/page/send` (:148-202). That route splits the post: custom fields go to `pb.me.detail.request`, and
the 5 contact boxes go to `pb.profile.change.request`.

**Approval:**
- `register_chain('pb.profile.change.request', 'master', submit_state='hr_review', driven=('approved',))` is at
  `pb_me_portal/models/pb_profile_change_approval.py:38-42`.
- The default route is one "HR lead" step, from `om_hr_payroll.group_hr_payroll_user` (:122-134).

**Written on approval:** `_apply_to_master()` (:335-352) writes to hr.employee under sudo, using `_MASTER_FIELDS`
(:41-47):

| Proposed field | hr.employee field |
|---|---|
| `x_phone` | `private_phone` |
| `x_private_email` | `private_email` |
| `x_address` | `private_street` |
| `x_emergency_contact` | `emergency_contact` |
| `x_emergency_phone` | `emergency_phone` |

These 5 fields are audited by a `biz.audit.rule` (`data/pb_me_portal_data.xml:32-37`).

### A2. `/my/details` → `pb.me.detail.request` (pb_me_details)

**Model:** `pb_me_details/models/detail_request.py:80`.

**Constants:**
- `KINDS` (:30-37): `family_add`, `family_change`, `family_remove`, `id_paper`, `photo`, `marital`.
- `PAPERS` (:40-44): `national_id`, `passport`, `permit`.
- `MARITAL` (:54-60).

**Fields** (:85-133, all readonly):
- `kind`, `state`, `employee_id`, `member_id` (M2O `pb.employee.family`).
- Family: `f_name`, `f_relationship`, `f_birthdate`, `f_id_number`, `f_counts_for_tax`, `f_insured`.
- Papers: `paper_kind`, `paper_number`, `paper_expiry`.
- `marital`, `attachment_id`, `before_json`, `note`, `decision_note`, `submitted_on`, `decided_on`.
- `document_id` (M2O `pb.employee.document`).

**States** (:93-99): `draft`, `hr_review` ("Waiting for HR"), `approved`, `refused`. "Sent back" means `draft`
with a `decision_note` (`pb_portal_state` :509-513).

**Files** (:74-76, checked in `_pb_file` :214-228): png or jpeg for a photo, pdf/png/jpeg for a scan, 10 MB
at most.

**Entry point:** `pb_portal_create(self, employee, kind, values, member=None, upload=None, request_id=None)`
(:231-232).
- `upload` is a `(bytes, filename, mimetype)` tuple. The method returns the request (sudo).
- **Guard:** it raises AccessError unless `employee.user_id == env.user` (:237).
- `create()` only runs under sudo (:141-150).
- `_pb_send()` (:315-323) seeds a route if there is none and advances to `hr_review`.

**Approval:** process key `me_details` (`models/detail_approval.py:21-28`). The default route is one "HR lead"
step (:150-161), and it is seeded on each new company (:164-178).

**Written on approval** (`_pb_apply` :359-423):
- **Family:** creates, changes or deactivates a `pb.employee.family` row (`models/family.py:44`). If the person
  counts for tax, `_pb_mark_for_tax` runs (:111) and HR then confirms on People › Family (`action_confirm_tax`
  :151).
- **ID paper:** writes `identification_id`, or `passport_id` + `passport_expiration_date`, or `permit_no` +
  `work_permit_expiration_date` (`PAPER_FIELDS` :46-52). Then `_pb_file_paper` (:425-453) files the scan as a
  **verified** `pb.employee.document` in category `cat_id_document` or `cat_work_permit`.
- **Photo:** `image_1920` (:418). **Marital:** `marital` (:421).

**Routes** (`pb_me_details/controllers/portal.py`):
- GET `/my/details` (:194)
- `/my/details/family/new` (:208) and `/my/details/family/<int:member_id>` (:216)
- `/my/details/papers?kind=` (:227)
- `/my/details/photo` (:236) and `/my/details/marital` (:244)
- POST `/my/details/send` (:253)
- `/my/details/request/<id>` (:280) and `.../withdraw` (:297)
- Bank:
  - GET `/my/details/bank` (:311)
  - POST `/my/details/bank/upload` (:326)
  - `/my/details/bank/<id>` (:358), `.../send` (:366), `.../withdraw` (:380)

Account and ID numbers are masked to the last 4 characters on display (:31-35). The bank flow uses a different
model (§D).

### A3. `/my/tax` (pb_me_tax)

**Routes** (`pb_me_tax/controllers/portal.py`):
- `/my/tax` (:72)
- `/my/tax/change/<string:kind>` (:83). Only the kinds allowed for the person's country (:89).
- POST `/my/tax/send` (:93). It calls `pb.me.detail.request.pb_portal_create(emp, kind, post, upload=...)`.
- `/my/tax/request/<id>` (:111) and `.../withdraw` (:126)

**Model:** the same `pb.me.detail.request`, with new kinds (`models/tax_request.py:48-51`) and the same
`me_details` route.
- Fields (:53-64): `t_country`, `t_number`, `t_use_nik`, `t_ptkp`, `t_regime`, `t_fund`.
- Form whitelist: `TAX_PORTAL_FIELDS` (:37-42).
- Country comes from the person's pay scheme (`_pbtx_country`, `pb_me_tax/models/hr_employee.py:171-190`).

**Kinds and written fields:** `KINDS_BY_COUNTRY` is at `pb_me_tax/models/tax_rules.py:39-44`, `NUMBER_FIELD` at
:50-53 and `CHOICE_FIELD` at :57-60. The table is in §E.

**Proof:** a file is required for a number, PTKP status or tax regime (`PROOF_REQUIRED` :47). On approval the
proof is filed as a **verified** `pb.employee.document` in `pb_me_tax.cat_tax_paper` (`tax_request.py:219-243`).

**VN:** the tax code is also copied to the running contract's `vietnam_tax_code` (:198-217).

`/my/taxsheet` (`pb_me_portal/controllers/portal.py:458`) is read-only.

### A4. `/my/documents/upload` (pb_me_portal)

**Route:** POST, `pb_me_portal/controllers/portal.py:388-453`. png/jpeg/pdf only, 10 MB at most (:41-42).

**Self-upload flag:** `pb.employee.document.category.ess_uploadable` (Boolean, "Employee Self-Upload",
`pb_me_portal/models/employee_document_ext.py:17`).
- It is enforced on the model as well (:29-43). The route also checks it (:407).
- Seeded True for `cat_id_document`, `cat_certificate`, `cat_health_check` and `cat_other`
  (`data/pb_me_portal_data.xml:41-52`).
- **No view shows this flag.** It can only be set through data files.

**Records created:** an `ir.attachment` (:426), then a `pb.employee.document`
`{employee_id, category_id, name, attachment_id, expiry_date?}` (:431-444), then the attachment is re-bound to it
(:452). `verified` stays False.

### A5. Privacy consent (pb_me_privacy)

**Models:**
- `pb.privacy.notice` (`models/notice.py:48`).
- `pb.privacy.consent` (`models/consent.py:27`). Fields (:31-52): `employee_id`, `notice_id`, `version`,
  `answer` (agree/disagree), `how` (screen/paper), `wording`, `lang`, `answered_on`, `user_id`, `recorded_by`,
  `note`. Rows are only ever appended (`_pb_record_screen` :109-137).

**Routes:** `/my/privacy/notice` (:55), POST `/my/privacy/answer` (:77), `/my/privacy` (:112).

**Gate:** `ir.http._pre_dispatch` (`models/ir_http.py:46-89`) sends every GET under `/my` to the notice first and
keeps the original target in `?next=` (:85-89). So a deep link survives the first-visit consent.

Candidates have their own consent fields: `hr.applicant.pb_consent_on` and `pb_consent_text`
(`pb_hiring/models/forms_p2.py:846-847`).

### A6. Existing "things you still need to do" on `/my`

**Home provider:** `pb.me.home.get_home_data(emp, now=None)` (`pb_me_portal/models/pb_me_home.py:282-319`).
- Returns `{person, pay, leave, week, needs_you, docs, extra_cards, tiles}`.
- `_pbme_needs(emp, today, monday, now)` (:646-727) returns `([{key, n, url, days?, label?, sub?, icon?, tone?,
  sentence?}], docs)`. The order is `NEEDS_ORDER` (:83-87).

**Extension hooks:**
- `_pbme_needs_extra(emp, put)` (:730-740), where `put(key, n, url, label=, sub=, icon=, tone=, sentence=)`.
  Precedents: `pb_me_details/models/pb_me_home.py:34-53` (`details_sent_back`) and
  `pb_me_tax/models/pb_me_home.py:44,51` (`tax_sent_back`, `tax_number_missing`).
- `_pbme_extra_cards(emp)` (:337-347) returns `[{'key','template','data'}]`.

**→ The "asked items" list on /my belongs in `_pbme_needs_extra`** (one row per open item, url = the sub-page).

**Profile completeness:**
- `PROFILE_FIELDS` (`pb_onboarding/models/hr_employee.py:31-42`): `image_1920`, `birthday`, `sex`,
  `private_street`, `private_city`, `private_phone`, `emergency_contact`, `emergency_phone`, `identification_id`,
  `account_number`.
- Computed `profile_complete_pct` (Integer) and `profile_missing` (Char) (:74-77, compute :105-131).
- Overridden by pb_employee_bank_panel (`models/joining_checklist.py:36-80`): the bank line becomes
  done/waiting/missing from `pb_bank_on_record`, and a new `pb_profile_waiting` field is added.

**`/my/journey`** (`pb_onboarding/controllers/portal.py:78-96`, `_journey_values` :98-151):
- The "Still to fill in" card links **only to `/my/profile`** (`views/portal_templates.xml:191-196`).
  `/my/profile` cannot edit bank, ID or photo.
- The step "Finish your own details" has no link and is closed by hand: `/my/journey/step/<id>/done` (:153).

### A7. Deep link "open /my on the bank section"

- **Use the sub-page: `/my/details/bank`.** Others: `/my/details/papers?kind=passport|national_id|permit`,
  `/my/details/photo`, `/my/details/family/new`, `/my/tax/change/<kind>`, `/my/documents` (upload).
- `#bank` does **NOT** work: the `<section>` blocks have no `id` (`pb_me_details/views/portal_templates.xml:93`,
  :112, :131, :145, :184).
- A `?section=` parameter **DOES NOT EXIST**. `?done=` is a toast key (`controllers/portal.py:196`,
  `_DONE` :27).
- Hash precedents elsewhere: `/my/team#probation` (`pb_me_team/models/pb_me_home.py:42`) and
  `/my/work/leave#pbew-lv-<id>` (`pb_timeoff/models/leave_sent_back.py:279`).

---

## B. No-login links

### B1. `/journey/p/<token>` (one-tap pulse)

- Route: `pb_onboarding/controllers/pulse_pages.py:33-59`. `auth='public'`, and the submit is `csrf=False` (:44).
- Model `pb.newhire.pulse` (`models/newhire_pulse.py:44`). Token `portal_token` (:76-77), from
  `secrets.token_urlsafe(24)` (:105).
- Lookup (:118-130) rejects keys shorter than 12 characters. **No expiry, no rate limit.** It is single-use by
  state.
- It writes only `score`, `comment` (500 chars, :28), `state`, `answered_at` and `red_flag` (:234-251).

### B2. "Tell us about you" = `/journey/t/<token>`

This is a `pb.journey.task` form step, not the pulse.
- Step data: `pb_onboarding/data/journey_template_data.xml:86-96` (`assignee_rule='candidate'`,
  `step_kind='form'`, `form_questions_json`).
- Route: `pb_lifecycle/controllers/token_pages.py:106-136`. `auth='public'`, submit `csrf=False` (:116).
- Token `pb.journey.task.portal_token` (`pb_lifecycle/models/journey_task.py:61-63`), from `token_urlsafe(24)`.
  It is made for form/confirmation steps or candidate steps (:78-88; `TOKEN_KINDS` in `lifecycle_common.py:88`).
- `_task_for_token` (:99-115): **no expiry, no rate limit.** Single-use by task state.
- It writes `payload_json` only, through `action_done` (:130). Answers are capped at 4,000 chars
  (`token_pages.py:58`).
- Question types are `text`, `rating` and `choice` only. **There is no file upload** (`journey_task.py:205-206`).
- **No code sends this link.** `pb_lifecycle.mail_template_task_link` exists (`mail_template_data.xml:144`), but
  nothing calls it. The link only leaves through the "Copy link" button (`pb_lifecycle/static/src/xml/journeys.xml:312`).

### B3. `/workflow/t/<token>` — the hardened token precedent

- Routes: `pb_lifecycle/controllers/token_pages.py:217-262`.
- Token `pb.workflow.step.access_token`. Only `base.group_system` can read it (`models/workflow_people.py:90`),
  and it is unique (:96). It comes from `token_urlsafe(32)` (:724).
- Expiry: 30 days, or the due date + 14 days (:50-51, :726-730).
- Resending mints a new key and kills the old link (:775-789). Lookup requires a 32-80 character key and checks
  expiry (:791-807).
- **CSRF on.** The row is taken with `FOR UPDATE NOWAIT` and the token is re-checked before the write (:241-248).
- Per-IP rate limit: 10 misses per 600 s (`token_pages.py:38-55`, :207-215). The submitting IP is stored in
  `link_done_ip` (:95, :648).
- **No files:** `LINK_UNSUPPORTED = ('file','lookup')` (:55).

### B4. Hiring candidate document request (pb_hiring)

**Models** (`pb_hiring/models/docreq.py`):
- `pb.hiring.doc.template` (:44): `name`, `sequence`, `required`, `help_text`, `active`, `company_id`.
- `pb.hiring.docreq` (:76): `token` Char, unique (:99-100, :120-121), minted with `token_urlsafe(24)` (:156).
  One request per offer (:122-123). `deadline` (:102) is a chase date only.
- `pb.hiring.docreq.item` (:430): `docreq_id`, `name`, `sequence`, `required`, `help_text`, `received_at`,
  `attachment_id` (:442), `company_id`.
  - **The item has no template link and no vault category**, so it cannot be mapped to a document category
    automatically.

**Routes** (`pb_hiring/controllers/token_pages.py`): GET `/hiring/d/<token>` (:132) and POST `.../upload` (:156),
both `auth='public'`. The upload is `csrf=False` (:157). The page template is `hiring_documents_page`
(`views/offer_token_templates.xml:32`).

**Files:**
- Size: the controller reads at most 5 MB (:38).
- `receive(item_id, filename, content, mimetype=None)` (`docreq.py:322-370`) enforces 5 MB and
  pdf/doc/docx/jpeg/png (`hiring_common.py:520-529`).
- Each file is stored as `ir.attachment(res_model='pb.hiring.docreq', res_id=<request>)` (:348-354) and set on
  `item.attachment_id` with `received_at` (:356-357). A replacement upload deletes the old file (:358-361).

**Link lifetime** (`_request_for_token` :274-290): the link closes only when the offer is joined, dropped,
declined or refused, or when everything is in. **There is no time expiry.**

**Seeded lines** (`data/hiring_doc_templates.xml`): `doc_id` (:17), `doc_degree` (:25), `doc_payslip` (:33),
`doc_bank` (:41, **a file only**), `doc_photo` (:49), `doc_tax` (:57, optional).

- **Typed bank, tax or ID values: DOES NOT EXIST** anywhere in pb_hiring.
- **Verification of the papers: DOES NOT EXIST** (docstring :19-21).

### B5. Security assessment and the ONE recommended mechanism

| Link | Token | Expiry | Single-use | Rate limit | CSRF | Files | Can write employee / bank / documents |
|---|---|---|---|---|---|---|---|
| `/journey/p` | 24 B | none | yes | none | off | no | no |
| `/journey/t` | 24 B | none | yes | none | off | no | no |
| `/workflow/t` | 32 B, system-only, rotates on resend | 30 d | yes (row lock) | 10 misses / 10 min / IP | on | no | no |
| `/hiring/d` | 24 B, never rotated | only when the offer closes | no | none | off | 5 MB | no (files stay on the docreq) |
| `/my/*` (session) | login | — | — | — | on | 10 MB, OCR for bank | yes, via approval |

**Verdict:** no existing token page may collect bank details, ID numbers or papers, for two reasons.
1. Four of the five tokens never expire and have no rate limit or CSRF.
2. Both write entry points refuse a caller who is not signed in as that employee:
   - `pb_portal_create` (`detail_request.py:237`)
   - `pb.bank.change.request.pb_portal_start` (`pb_bank_ocr/models/pb_bank_self_service.py:270`)

**RECOMMENDED: the welcome link = a sign-up invitation that lands on the real `/my` pages.**

**What already exists:**
- The person's employee login: `pb.zoho.pipeline._auto_create_login(employee, company, summary)`
  (`pb_zoho_bridge/models/zoho_pipeline.py:586-626`). It creates a portal user with `no_reset_password=True`,
  sets `hr.employee.pb_portal_user_id` (`pb_zoho_bridge/models/hr_employee.py:48`) and `user_id`
  (`_link_employee_login` :628). Hiring already reuses this (§G).
- The link: `hr.employee.pb_portal_signup_url` (computed, `pb_zoho_bridge/models/hr_employee.py:54-79`). It calls
  `partner.signup_prepare(signup_type='signup')` and then `partner._get_signup_url_for_action()`.

**Behaviour of the stock link (server copy, `addons/auth_signup/models/res_partner.py`):**
- **Signed:** `tools.hash_sign`, which covers `[partner id, user ids, last login date, signup_type]` (:171-190).
- **Valid for 144 h by default** (`auth_signup.signup.validity.hours`). That parameter is unset on all five
  databases.
- **Dies at first sign-in**, because the last login date is part of what is signed.
- **Accepts `url=`**, which becomes `?redirect=` (:61-62). So the link can carry `/my/details/bank` or `/my`.

**After the person has signed in,** every existing page, model, approval, mask, file check, OCR and audit
applies unchanged. The privacy gate keeps `?next=`.

**Gaps to close:**
1. The person chooses a password once. Change the POC wording "no password".
2. 144 h is shorter than a normal offer-to-start gap. Each reminder must mint a fresh link with
   `_get_signup_url_for_action(url=...)`. Or set `auth_signup.signup.validity.hours` per database, but that
   changes every invitation in the system.
3. **Email address:**
   - `_auto_create_login` uses `work_email` only (:597-601) and skips anyone without one.
   - A joiner often has only a personal email before day one (the POC sends to `pemail`).
   - Fix: a variant that uses `private_email` as the login and address.
   - Logins by employee number (`create_worker_logins`, §G) get no email at all, so they cannot receive a link.
4. Today the login is active from creation (only the email waits). Sending the link before day one simply moves
   the email earlier. No new exposure.
5. **New:**
   - An "asked items" record or list for the New joiners board (§F6) and the `/my` needs row (§A6).
   - Reminders every 2 days (§F7 machinery).
   - Contact details (phone, address, emergency) live on `pb.profile.change.request`, but bank, papers, family
     and photo live on `pb.me.detail.request`. The studio must send each item to its own page.
6. The bank still goes to a second person. With a link the proposer is the employee's own user, which the rule
   already handles: `_pb_never_decide` at `pb_bank_self_service.py:111-116`.

**Rejected alternative:** a new token page cloned from `/workflow/t` (B3).
- It needs new sudo entry points that bypass the two `user_id == env.user` guards.
- It would rebuild the five `/my` forms.
- It would leave "who proposed this bank account" undefined. Higher risk, more code.

---

## C. Documents (pb_employee_vault)

### C1. `pb.employee.document.category` (`pb_employee_vault/models/employee_document.py:36-48`)

**Fields:**
- `name` Char, required, translate (:41)
- `code` Char, required (:42)
- `requires_expiry` Boolean (:43)
- `sequence` Integer, default 10 (:47)
- `active` Boolean (:48)
- `ess_uploadable` Boolean, added by pb_me_portal (`employee_document_ext.py:17`)

**Country, "required" and "at joining": DOES NOT EXIST.** There is no such field on the category and no
`required_document` or checklist model anywhere.

### C2. `pb.employee.document` (`employee_document.py:51-97`)

**Fields:**
- `employee_id` M2O, required, cascade (:56)
- `category_id` M2O, required (:59)
- `name` Char "Title", required (:61)
- `attachment_id` M2O, required (:62)
- `issue_date` (:64), `expiry_date` indexed (:65), `note` (:66)
- `verified`, `verified_by`, `verified_at` (:69-72)
- `company_id` (:74), `active` (:77)
- `expiry_state` (computed): none/valid/soon/expired; "soon" means within 90 days (:80, :85-97)

**Fields added by other modules:**
- `pbdc_contract_id`, `pbdc_version` (`pb_doc_contracts/models/employee_document.py:12,15`)
- training fields (`pb_training/models/document_ext.py:78-112`)
- `pb_rf_private` (`pb_review_forms/models/vault_ext.py:34`)

**HR-verified flag:**
- Only `action_verify()` and `action_unverify()` set it (:157-171). Both require HR. A direct write raises
  (:136-142).
- Changing the attachment, category or employee clears it (:147-154).
- The approval flows in pb_me_details and pb_me_tax file their papers already verified.

**Expiry rules:**
- Constraint `_check_expiry_required` (:174-180).
- Daily cron `pb_employee_vault.cron_pb_employee_document_expiry` → `_cron_expiry_check()`
  (`data/ir_cron_expiry.xml:6-14`, method :227).
  - Warn window: config parameter `pb_employee_vault.expiry_warn_days`, default 30.
  - It creates one todo activity per document on the employee, assigned to a payroll HR user (:193-224).
  - **This cron is OFF on payobook and payobook_template and ON on p0clone, rize and sudima** (checked live).

### C3. Shipped categories (`noupdate="1"`)

| xml id | code | expiry | seq | self-upload |
|---|---|---|---|---|
| `pb_employee_vault.cat_resume` | RESUME | – | 8 | no |
| `pb_employee_vault.cat_offer_letter` | OFFER | no | 9 | no |
| `pb_employee_vault.cat_labor_contract` | LABOR | no | 10 | no |
| `pb_employee_vault.cat_id_document` | ID | **yes** | 20 | yes |
| `pb_employee_vault.cat_certificate` | CERT | no | 30 | yes |
| `pb_employee_vault.cat_health_check` | HEALTH | **yes** | 40 | yes |
| `pb_employee_vault.cat_work_permit` | PERMIT | **yes** | 50 | no |
| `pb_employee_vault.cat_other` | OTHER | no | 99 | yes |
| `pb_training.cat_licence` | LIC | yes | 31 | – |
| `pb_review_forms.cat_performance_review` | REVIEW | – | 60 | – |
| `pb_me_tax.cat_tax_paper` | TAX | – | 65 | – |
| `pb_conduct.vault_category_conduct` | pb_conduct | – | 90 | – (a record rule reads this code) |

Sources: `pb_employee_vault/data/document_category_data.xml:3-46`, `pb_training/data/document_category.xml:9`,
`pb_review_forms/data/review_forms_data.xml:14`, `pb_me_tax/data/document_category.xml:5`,
`pb_conduct/data/conduct_data.xml:15`.

### C4. Upload API used by the side panel

**JS:** `pb_employee_vault/static/src/js/employee_360.js:282` calls
`orm.call("pb.people", "vault_upload_batch", [empId, catId, documents])`.
- Each item in `documents` is `{payload:{name,title,mime,data(base64)}, issue_date, expiry_date}` (:276-281).

**Python:** `pb.people.vault_upload_batch(self, employee_id, category_id, documents)`
(`pb_employee_vault/models/pb_people_360.py:204`).
- HR only (`_require_hr` :43).
- 1 to 20 files, png/jpeg/pdf. Each file at most 10 MB, 50 MB in total.
- Expiry is enforced when the category requires it.
- All of it runs in one savepoint.

**Returns** `get_employee_360(emp.id)` (:137-150), a dict with:
- `profile, details, costcenter, documents[], legacy_documents[], categories[], timeline…, can_manage,
  unmask_wage, is_hr`
- each document from `_doc_payload` (:51-77)

**Related calls:**
- `vault_upload(employee_id, category_id, payload, issue_date=False, expiry_date=False, note=False)` (:197)
- `vault_verify(document_id, verified=True)` (:260)
- `vault_delete` (:272)
- `get_employee_documents(employee_id)` (:108-116)

**→ Studio step 5, "I have it" + file:** after the employee is created, call `vault_upload_batch` once per
category.

### C5. Where tenants edit categories today

Settings › Technical › Employee Vault › Document Categories:
- Menus `pb_employee_vault.menu_employee_vault_root` / `menu_document_category`
  (`views/employee_vault_config_views.xml:101-105`), **`base.group_system` only**.
- Action `action_document_category` (:40).
- Editable list `view_document_category_list` (:8).

There is **no tenant-facing screen**.

### C6. PROPOSAL — "papers needed per country of work"

One category can be required in one country and optional in another, so this needs a **small table, not a flag
on the category**.

**New model `pb.employee.document.requirement`** in pb_employee_vault:

| Field | Type | Notes |
|---|---|---|
| `category_id` | M2O category | required, cascade |
| `country_id` | M2O res.country | required |
| `need` | Selection | `first_pay` ("Needed before first pay") / `joining` ("Asked at joining") / `optional` |
| `when_rule` | Selection | `all` / `foreign_only` (SG work pass, VN work permit) |
| `sequence` | Integer | |
| `company_id` | M2O | empty = shipped default; a company row overrides the shipped one for that country |
| `active` | Boolean | |

- Unique on (`category_id`, `country_id`, `company_id`).
- Plus a reverse O2M `requirement_ids` on the category.
- Reader: `pb.people.joining_papers(country_id)` → `[{category_id, name, code, need, requires_expiry,
  ess_uploadable}]`. Country of work = `payroll_country`, the same thing `pbfs_country_of_work_id` reads
  (`pb_form_studio_people/models/hr_employee.py:76-90`).

**Seeds** (`noupdate`). Rows that point at `pb_me_tax.cat_tax_paper` must be seeded in **pb_me_tax** data, because
the vault cannot depend on it.

| Country | Needed before first pay | Asked at joining / optional |
|---|---|---|
| Indonesia | `cat_id_document` (KTP), `pb_me_tax.cat_tax_paper` (NPWP card) | `cat_other` (family card KK; no KK category exists, so a new `cat_family_card` would be cleaner), `cat_certificate` optional |
| Vietnam | `cat_id_document` (CCCD), `cat_health_check` | `cat_certificate` optional; `cat_work_permit` foreign_only |
| India | `cat_id_document` (Aadhaar), `pb_me_tax.cat_tax_paper` (PAN card) | `cat_certificate` optional; `cat_other` (relieving letter) optional |
| Singapore | `cat_id_document` (NRIC/FIN) | `cat_work_permit` foreign_only (first_pay); `cat_certificate` optional |

**Tenant editing**, two options:
- **(a) Recommended:** an editable "Needed for new joiners" sub-list on the category form, plus the
  `ess_uploadable` toggle (shown nowhere today). This requires opening the category screen to the HR manager
  role, not only `base.group_system`.
- (b) A card on the existing Settings › HR › Documents screen (pb_doc_studio). That is a new screen surface, so
  more work.

Bank documents are **not** a vault category for this purpose: the bank paper rides on `pb.bank.change.request`
(§D).

---

## D. Bank

### D1. `pb.bank.change.request` (`pb_bank_ocr/models/pb_bank_change_request.py:63`)

It inherits `mail.thread`, `mail.activity.mixin` and `biz.approval.chain.mixin` (:66).

**Fields:**
- `employee_id` required (:72), `attachment_id` (:77)
- `doc_kind` confirmation_letter/statement/passbook/cheque/other (:79)
- `state` (:87), `ocr_state` (:96)
- `x_bank_name`, `x_bank_branch`, `x_account_name`, `x_account_number`, `x_iban`, `x_swift` (:105-110)
- `cur_*` snapshots (:113-116)
- `v_format_ok`, `name_match_score`, `name_match_band`, `duplicate_ids`, `duplicate_ack`, `resolved_bank_id`
  (:119-132)

**Fields added by extensions:**
- `pb_origin` staff/self_service (`pb_bank_self_service.py:54`), plus `import` (`pb_bank_import_hold.py:85`)
- `proposed_by_id` (:58), `pb_decision_note` (:61)
- `pb_import_key` / `pb_import_label` (`pb_bank_import_hold.py:87-90`)
- A document is required unless `pb_origin=='import'` (:92-96).

**States:** `draft → hr_review → finance_review → approved | refused` (:87-93).

**Approval:**
- `register_chain('pb.bank.change.request','bankchange', submit_state='hr_review',
  driven=('finance_review','approved'))` (`pb_bank_change_approval.py:29-35`). The default route is HR lead, then
  Finance (:122-137).
- If the `records_bank` process exists it takes over (`pb_bank_self_service.py:41`, :86-90): **one second
  person** decides.
- The proposer and the employee's own user can never decide (`_pb_never_decide` :111-116).

### D2. `_pb_hold_new_hire(self, employee, vals, proposer)` (`pb_bank_import_hold.py:159-176`, `@api.model`)

- Key `'pb.newhire,<emp.id>'`, label "New hire: <name>".
- Runs as the proposer and calls `_pb_hold_from_import(employee, vals, hold)` (:100-155). That method:
  - merges the `x_*` values over the current `vietnam_bank_*` values
  - returns `'same'` when nothing changed or there is no account number
  - if an identical request is already open, returns it without creating anything
  - otherwise creates the request with `pb_origin='import'`, `ocr_state='done'`, `doc_kind='other'`, runs
    `action_validate()`, then `action_submit()` as the proposer inside a savepoint
  - on a UserError (for example a duplicate account) the request stays draft and the reason goes to
    `pb_decision_note`
- **Returns** the newest request with that key (sudo), or an empty recordset. **It never writes the employee.**
- **Caller:** `pb_people_advanced/models/people_wizards.py:151`, in `_pb_send_bank` (:127-166).
  - It sends `{x_account_number, x_bank_name, x_account_name}`.
  - Problems are found first by `_pb_bank_problem` (:105-119).
  - The screen outcome is `{'state':'sent'|'check'|'not_sent','message','reference'}` (:121-123).
  - Bank choices come from `_pb_bank_choices()` (:79-93), which reads `pb.bank.registry`.

### D3. Written on approval (`_apply_to_master` :302-336)

1. On hr.employee (context `from_bank_request=_BANK_AUDIT_TOKEN`, :318):
   - `vietnam_bank_name` ← `x_bank_name`
   - `vietnam_bank_branch` ← `x_bank_branch`
   - `vietnam_bank_account_name` ← `x_account_name`
   - `vietnam_bank_account_number` ← `x_account_number`
   - These are Char fields at `pb_hr_payroll_vietnam/models/hr_employee_vietnam.py:48-51`. Mapping at :32-37.
2. `_pb_mirror_to_accounts` (`pb_bank_two_stores.py:74-128`) writes `res.partner.bank` on `emp.work_contact_id`:
   - It finds an account by number or creates `{acc_number, partner_id, bank_id, acc_holder_name, company_id}`.
   - `res.bank` is found or created by `_pb_res_bank` (:53-72).
   - `put_first()` (:155-170) adds the account to `bank_account_ids` and puts it first.
3. A `pb.employee.bank.history` row, `change_source='ocr_request'` (:323-335; model
   `pb_employee_bank_history.py:25`).

### D4. Payroll-ready and `pb_bank_on_record`

**`pb_bank_on_record`:** a computed, non-stored Boolean on hr.employee (`pb_employee_form_tidy/models/pb_people.py:24`,
compute :55, search :64). It is True when `bank_account_ids` is set or `vietnam_bank_account_number` is not blank.
- `_pb_bank_on_record_facts()` (:71-106) returns `{on_record, store, bank, holder, last4, vn_file_last4}`.

**Payroll-ready:**
- `pb_people.py:186-188`: `row['ready'] = bool(e.contract_id and row.get('state') == 'open' and bank)`
- the same test at :201
- the KPI `ready_pct` at :151-157
- **So a new hire whose bank request is waiting is NOT payroll-ready until it is approved.**

### D5. `pb.bank.registry` (`pb_bank_ocr/models/vn_bank_dictionary.py:84`)

- Fields: `name`, `short_name`, `swift_prefix`, `aliases`, `active`, `company_id`, `country_id` (empty = VN,
  :99), `clearing_code` (:102).
- `match(raw_name, country=None)` (:128).
- Seeds: 40 Vietnamese banks (`data/vn_bank_registry_data.xml`) and 27 more (`data/bank_directory_data.xml`:
  9 ID, 12 IN, 6 SG).

### D6. Bank OCR (pb_bank_ocr 19.0.1.6.1)

Cockpit AbstractModel `pb.bank.ocr` (`models/pb_bank_ocr_cockpit.py:22`):
- `create_from_upload(payload{name,mime,data,employee_id?})` → request id (:130-149)
- `run_ocr(request_id)` (:152), `save_fields` (:158), `validate` (:169)
- `do_action(request_id, action, note=False)` (:175)
- `get_request` (:191)

**OCR path:** `action_run_ocr()` (:416) → `biz.doc.ocr._extract(schema, attachment_ids)`
(`biz_doc_ocr/models/biz_doc_ocr.py:26`).
- The provider is whatever `payroll.ai.config` has `purpose='doc_ocr'`: openai, anthropic, ollama or tesseract.
- A fixed clean-up then always runs (`_ocr_post_process` :357).

**Self-service:**
- `pb_portal_start(employee, data, filename, mimetype, doc_kind='other')` (`pb_bank_self_service.py:265-312`)
  requires `employee.user_id == env.user` (:270).
- The employee may type `x_bank_name`, `x_bank_branch`, `x_account_name`, `x_account_number` and `doc_kind`
  (:45-46).

**→ A Hiring `doc_bank` file** can become a bank request: `create_from_upload` with `employee_id`, then
`run_ocr`, then `do_action('submit')`. That is how "bank comes across from Hiring" can be honest (§K3).

---

## E. Tax, insurance and ID numbers per country (all on `hr.employee` unless stated)

The display list is `_SPEC` (`pb_employee_vault/models/employee_details.py:35-181`). Its country groups are VN
:135-153, ID :154-161, IN :165-170, SG :171-174 and VN dependants :178-180. A group shows when `payroll_country`
or `country_id` matches (:233-239). Core `identification_id` is on `hr.version` (`hr/models/hr_version.py:62`) and
is mirrored on the employee.

| Country | What | Field | Type | Defined at |
|---|---|---|---|---|
| ID | NIK | **DOES NOT EXIST as its own field** — the 16-digit `identification_id` is used | Char | `pb_form_lines/models/fund_id.py:39-41`; `/my/tax` `has_nik` `pb_me_tax/controllers/portal.py:52` |
| ID | NPWP | `pb_npwp_number` | Char | `pb_employee_vault/models/payroll_profile.py:22` |
| ID | PTKP | `pb_id_ptkp_status` | Selection | `pb_me_tax/models/hr_employee.py:47` (values `tax_rules.py:70`) |
| ID | BPJS Ketenagakerjaan / Kesehatan | `pb_bpjs_employment_number` / `pb_bpjs_health_number` | Char | `payroll_profile.py:24-25` |
| ID | Family card | `pb_family_card_number` | Char | `payroll_profile.py:23` |
| VN | Citizen ID (CCCD) | `vietnam_citizen_id` (`_SPEC` shows `identification_id` instead) | Char | `pb_hr_payroll_vietnam/models/hr_employee_vietnam.py:15` |
| VN | Tax code | `vietnam_tax_code` (also on `hr.contract`, `hr_contract_vietnam.py:26`) | Char | `hr_employee_vietnam.py:14` |
| VN | Social insurance no. | `vietnam_social_insurance_number` (also on contract :25) | Char | `hr_employee_vietnam.py:13` |
| VN | Dependants | `vietnam_dependents_count` Integer (:43); `vn_dependent_ids` O2M `vietnam.employee.dependent` (:157); `vn_eligible_dependent_count` computed (:162) | | `hr_employee_vietnam.py` |
| VN | Others in `_SPEC` | `vn_residency_status` (:148), `vn_tax_regime` (:144), `vn_si_enrolled` (:97), `vn_work_region` (:132), `vietnam_work_permit_type`/`_number` (:18,:25); `pb_vn_is_local`, `pb_vn_in_insurance`, `pb_vn_tax_resident` (`pb_payroll_mapping_vn/models/hr_employee.py:27-35`) | | |
| IN | PAN | `pb_in_pan_number` (also `hr.contract.pan_number`, `pb_hr_payroll_india/models/hr_contract.py:22`) | Char | `pb_me_tax/models/hr_employee.py:51` |
| IN | Aadhaar | **DOES NOT EXIST on employee or contract** (only on connected-system staging: `om_hr_payroll/models/hr_zoho.py:37`) — use `identification_id` | | |
| IN | UAN / ESI | `pb_in_uan_number` / `pb_in_esi_number` (also on contract: `uan_number`, `esi_number`, `hr_contract.py:20-21`) | Char | `pb_me_tax/models/hr_employee.py:56,59` |
| IN | Tax regime | `pb_in_tax_regime` new/old | Selection | `pb_me_tax/models/hr_employee.py:53` |
| SG | NRIC/FIN | **two stores**: `singapore_nric_fin` (`pb_hr_payroll_singapore/models/hr_employee_singapore.py:11`, also on contract) **and** `identification_id`, which `/my/tax` shows (`pb_me_tax/models/hr_employee.py:255`) | Char | |
| SG | Work pass | `singapore_work_permit_type` citizen/pr/ep/sp/wp/lwp (:16), `_number`, `_expiry` (:25-26) | Selection/Char/Date | `hr_employee_singapore.py` |
| SG | Residency | **two stores**: `pb_sg_tax_residency` (`pb_me_tax/models/hr_employee.py:63`, read by `_SPEC` and `/my/tax`) **and** `singapore_tax_residency` (`hr_employee_singapore.py:29`) | Selection | |
| SG | Self-help fund | `pb_sg_shg_fund` CDAC/ECF/MBMF/SINDA | Selection | `pb_me_tax/models/hr_employee.py:66` |

**What the employee can change on `/my/tax`.** Every change is approved by HR and needs a proof file.

| Country | Kinds | Field written |
|---|---|---|
| VN | `tax_number` | `vietnam_tax_code` (10 or 12 digits) |
| ID | `tax_number`, `tax_status` | `pb_npwp_number` (15 or 16 digits), `pb_id_ptkp_status` |
| IN | `tax_number`, `tax_regime` | `pb_in_pan_number` (PAN pattern), `pb_in_tax_regime` |
| SG | `tax_fund` | `pb_sg_shg_fund` |

**Shown as "Kept by HR"** (`pb_me_tax/models/hr_employee.py:241-263`): BPJS numbers, UAN, ESI, NRIC, SG
residency. **Not on `/my/tax` at all:** VN social insurance number, CCCD, Aadhaar, work pass. The ID number goes
through `/my/details/papers?kind=national_id`. So in the welcome link, "tax and ID numbers" =
`/my/tax/change/tax_number` + `/my/details/papers?kind=national_id`. Insurance numbers stay with HR (studio
"I have it").

---

## F. Joining checklist (pb_lifecycle + pb_onboarding)

### F1. Models

**`pb.journey.case`** (`pb_lifecycle/models/journey_case.py:42`):
- `employee_id` (:54), `case_type` (:57), `template_id` (:60), `anchor_date` "Key date" (:62), `state` (:66)
- `source` manual/zoho/portal (:69)
- `task_ids` (:76), `checkin_ids` (:77)
- `progress` / `task_count` stored (:80-83), `open_task_count` / `overdue_task_count` / `next_due_date`
  (:84-90)
- Selections in `lifecycle_common.py`:
  - `CASE_TYPES` (:9), `ANCHORS` case_open/doj/lwd/probation_end/key_date (:21)
  - `ASSIGNEE_RULES` hr/hrbp/manager/buddy/it/finance/admin/employee/candidate/user (:34)
  - `STEP_KINDS` task/confirmation/form/email/letter (:47), `TASK_STATES` (:55)

**`pb.journey.template`** (`journey_template.py:16`):
- `pick_for(case_type, country_id=False, company_id=False)` (:67). A country-specific template beats a
  no-country one.

**`pb.journey.template.step`** (:86):
- `anchor` (:96), `offset_days` (:98), `assignee_rule` (:102), `assignee_user_id`, `step_kind`,
  `escalation_days` (default 3), `mail_template_id`, `letter_template_id`, `form_questions_json`
- `automation_key` is added by pb_onboarding (`journey_ext.py:54`)

**`pb.journey.task`** (`journey_task.py:26`):
- `assignee_user_id` (:42), `due_date` (:44), `portal_token`, `payload_json`, `reminded_on` (:71)
- `action_done(payload=None)` (:130), `action_skip`, `action_block`, `action_reassign(user_id)` (:167)
- `automation_key`, `auto_ran_at`, `auto_error` are added by pb_onboarding (`journey_ext.py:64-67`)

### F2. The live template

`pb_onboarding.journey_template_rize_onboarding` "New joiner — the full welcome"
(`pb_onboarding/data/journey_template_data.xml:34`). The old `pb_lifecycle.journey_template_onboarding` is
switched off (:26-27).

| xml id | line | Step | Owner | Anchor / offset | Kind | automation_key |
|---|---|---|---|---|---|---|
| `step_rize_buddy` | :48 | Choose their buddy | manager | case_open 0 | task | `buddy_invite` |
| `step_rize_laptop` | :61 | Laptop and equipment | it | doj −12 | task | `asset_laptop` |
| `step_rize_access` | :74 | Tool access | it | doj −5 | task | – |
| `step_rize_intro_form` | :86 | Tell us about you | candidate | doj −1 | form | – |
| `step_rize_poster` | :99 | Welcome card | hr | doj 0 | email | `poster` |
| `step_rize_day1` | :111 | Day-one introduction | hr | doj 0 | email | `day1_ics` |
| `step_rize_credentials` | :123 | Send their sign-in details | hr | doj 0 | email | `credentials` |
| `step_rize_data` | :136 | Finish your own details | employee | doj +3 | task | – (**nothing ticks it automatically**) |
| `step_rize_orientation` | :148 | Welcome session | hr | doj +7 | task | – |

### F3. `pb.journeys.open_case`

`pb_lifecycle/models/pb_journeys.py:413`:

```python
@api.model
def open_case(self, employee_id, case_type, template_id=None, anchor_date=None)
```

- Needs `_require_write()` (:72): lifecycle manager or admin.
- When no template is given it uses `pick_for` (:425).
- Creates the case with `source='manual'` (:429-436), then calls `action_open()` (:437).
- Returns `{'case_id': int, 'steps': int, 'template': str}` (:438).
- **It does NOT check for a case that is already running.**

The duplicate-safe alternative is `pb.zoho.pipeline._open_case(employee, case_type, anchor_date, company)`
(`pb_zoho_bridge/models/zoho_pipeline.py:555`). It returns `(case, opened)`. Hiring uses it (`offer_closure.py:445`).

**→ Recommend `_open_case` (then `_after_onboard`), the same pair Hiring uses.**

**Today's People › Add employee opens NO case and creates NO login.** No caller in pb_people, pb_people_advanced,
pb_updates or pb_orgchart. Only Hiring and the connected-system bridge do.

### F4. Dates and owners

- **Due date:** `_generate_tasks` (`journey_case.py:278`) sets `due_date = _anchor_base(anchor) + offset_days`
  (:305).
- **Joining date** for `doj` (`_joining_date` :157), first match wins:
  1. `anchor_date`
  2. `first_contract_date`
  3. the earliest contract start
  4. today
- **Owners:** `_resolve_assignee(rule, employee)` (:218).
  - manager → `parent_id.user_id`; employee → `employee.user_id`; candidate → nobody.
  - buddy / hrbp → read from `buddy_id` / `hrbp_user_id`.
  - hr/it/finance/admin → config parameters `pb_lifecycle.{hr,it,finance,admin}_user_id`, else the first
    lifecycle manager.
  - If nothing resolves, the case creator (:293-320).
- Dates are fixed when the case opens. **The case must be opened after the start date and manager are final.**

### F5. Buddy, laptop and day one

**Buddy:**
- Fields: `hr.employee.buddy_id` M2O hr.employee (`pb_onboarding/models/hr_employee.py:54`), plus
  `buddy_temp_id/_from/_to` (:59-63) and `hrbp_user_id` (:49).
- Choosing one: `pb.onboarding.buddy_choose(employee_id, candidate_id, case_id=None)` (`pb_onboarding.py:427`),
  which wraps `pb.buddy.nomination.choose` (`buddy_nomination.py:258`). It writes `buddy_id`, plans the
  catch-ups, sends mail and ticks `buddy_invite`.

**Laptop:**
- `setup_onboarding()` (`pb_onboarding/models/journey_case_ext.py:75`) runs `_raise_asset_requests` (:172-213).
- For each task with `automation_key=='asset_laptop'` it creates a `pb.asset.request` **in draft**
  (`Request.create` :197): `{employee_id, category_id=pb_assets.cat_laptop (hard-coded :191), needed_by=task due,
  justification, journey_task_id, company_id}`.
- Other parts of `setup_onboarding`: `_assign_hrbp` (:97), `_plan_checkins` (:120), `_enrol_orientation` (:160),
  `_plan_pulses` (:167).

**Day one:**
- `_run_auto_steps` (`pb_onboarding/models/onboarding_automation.py:64`) picks up open tasks that are due. It is
  gated by `pb_onboarding.auto_steps` (default `'1'`, `onboarding_common.py:83`). It calls
  `action_auto(force=False)` (`journey_ext.py:99`).
- Handlers (:70):
  - `credentials` → `_auto_credentials` (:161) → `hr.employee.send_credentials()`
    (`pb_zoho_bridge/models/hr_employee.py:84`), which returns `{'sent','skipped'}`
  - `poster` (:239), `day1_ics` (:181), `buddy_invite` (:308)
  - generic email steps (:143)

### F6. New joiners board row

Provider: `pb.onboarding._row(case, today=None)` (`pb_onboarding/models/pb_onboarding.py:325`). It is called by
`get_joiners_page(filters=None, search=None, sort=None, offset=0, limit=60)` (:298), which returns
`{rows,total,offset,steps?}`.

Row keys (:343-386):
- `id, employee_id, employee, initials, avatar, job, dept, country, doj, month, days, when`
- `progress, open_tasks, overdue`
- `buddy, buddy_id, buddy_temp, hrbp, hrbp_id, orientation`
- `complete, missing`
- `pulses[{mark,mark_label,state,score,word,red}], pulse_last, pulse_score, pulse_red`

Precedent for extending a row: pb_employee_bank_panel adds `waiting` (`models/joining_checklist.py:90`). **Add an
`asked` key `{n_open, n_done, items:[{key,label,state,url}]}` the same way.** Each card is wrapped in `_safe`
(:53, :315). Detail: `get_joiner(case_id)` (:390).

### F7. Reminders, scheduled jobs and check-ins

**The one scheduled job:** `pb_lifecycle.cron_lifecycle_reminders` → `_cron_lifecycle_reminders()`
(`pb_lifecycle/data/ir_cron.xml:10-17`).
- Base part (`lifecycle_reminders.py:50`), gated by `pb_lifecycle.reminders_enabled` (default on, :33-35) and
  `remind_days` (default 2):
  - `_remind_due_tasks` (:108), at most once a day via `reminded_on`
  - `_escalate_overdue_tasks` (:148)
  - `_remind_checkins` (:193)
  - mail helper `_mail(xmlid, record, email_to)` (:81)
- pb_onboarding adds `_run_auto_steps`, `_plan_missing_pulses` (:89) and `_send_due_pulses` (:109)
  (`onboarding_automation.py:43`).
- **Live state: OFF on payobook** (demo mail lock), ON on payobook_template, p0clone, rize and sudima.
- payobook also has `pb_onboarding.poster_mail`, `pulse_mail` and `buddy_mail` set to 0.

**→ "Remind every 2 days until done" should be a new piece inside `_cron_lifecycle_reminders`,** gated by its own
parameter. Do not add a new scheduled job: the template-job list in `pb_tenants.template_active_crons` would need
it too.

**Check-ins:**
- `pb.employee.checkin` (`pb_lifecycle/models/checkin.py:30`), kinds d30/d60/d90/…, from `CHECKIN_PLAN`
  (`journey_case_ext.py:30`, `_plan_checkins` :120).
- Pulses on days 7/30/60: `pb.newhire.pulse` (`newhire_pulse.py:43`; `ensure_for_case` :134; sent by
  `_cron_send_due` :176).

---

## G. Sign-ins

| Call | File | Tier | Email | Hold until day one | Links the employee |
|---|---|---|---|---|---|
| `pb.access.create_user(name=None, email=None)` | `biz_access/models/pb_access_facade.py:1339` | **staff only** (`share=False`, `base.group_user`, :1369-1380) | sends at once (`action_reset_password` :1386) | no | no |
| `pb.access.create_worker_logins(employee_ids)` | `biz_access/models/account_workers.py:136` | employee (portal) | none; login = employee code (`_pb_sign_in_code` :76), password `Abcd-2345-efgh` (`first_password` :45), `pb_must_change_password=True` | n/a | `user_id` yes, `pb_portal_user_id` **no** |
| `pb.zoho.pipeline._auto_create_login(employee, company, summary)` | `pb_zoho_bridge/models/zoho_pipeline.py:586` | employee (portal) | none (`no_reset_password=True`) | yes — the email goes on day one through step `step_rize_credentials` → `send_credentials` | `pb_portal_user_id` + `user_id` |

Details:
- `create_user` returns `{id,name,invitation_sent,message}` (:1405) and needs `_require_manage`.
- `create_worker_logins` returns `{'created':[{employee_id,name,department,login,password}],'skipped':[{name,why}],
  'message','url'}` (:198). The batch limit is 300.
- `_auto_create_login`:
  - is gated by `pb_zoho_bridge.auto_create_logins` ('1' on all five databases)
  - needs `work_email`
  - links an existing login with the same address and never changes it (:605-610)
- **"Held" means only the email waits.** The login itself is active from creation.

**Which call does "employee login + invitation held until day one"?** The pair below, and only when a joining
case exists:
1. `_auto_create_login`
2. the `credentials` step of an onboarding case

It is a private method on the connected-system bridge model. No public facade exists.

**→ For studio "Email invitation":** call `_auto_create_login` (as Hiring does), then open the case.
**→ For "Employee number":** call `create_worker_logins([emp_id])`, show the password once, and also write
`pb_portal_user_id`. Otherwise `send_credentials` skips the person.

**Hiring reuses `_auto_create_login`:** `pb_hiring/models/offer_closure.py:402-425`, called at :419-420, writes
`login_user_id` on the offer (:423).

Account type switch: `pb.access.set_account_type(user_id, kind, reason=None)` (`biz_access/models/account_type.py:163`).

---

## H. Equipment (pb_assets)

**"Every joiner gets one":** `pb.asset.category.auto_assign_at_joining` Boolean (`pb_assets/models/asset_category.py:38`).
- True on `cat_laptop`, `cat_idcard`, `cat_email` and `cat_login` (`data/asset_category_data.xml:27,55,83,93`).
- **The flag drives nothing.** It is only read for the board's category list (`pb_assets_board.py:438`).
  Onboarding raises a laptop request only (§F5).

**Request model `pb.asset.request`** (`asset_request.py:22`):
- Fields: `employee_id`, `manager_id`, `category_id`, `country_id`, `needed_by`, `justification`,
  `spare_asset_id`, `asset_id`, `assignment_id`, `journey_task_id` (:54), `state`, `fulfilment`.
- States (`asset_common.py:66`): draft/submitted/manager_approved/approved/refused/cancelled.
- Approval: `register_chain('pb.asset.request','assets', submit_state='submitted',
  driven=('manager_approved','approved'), date_field='needed_by')` (`asset_request_approval.py:30`). Default route:
  manager, then the "equipment" role (:84).
- Actions: `action_submit` (:217), `action_manager_approve` (:222), `action_final_approve` (:226).
- `action_fulfil(asset_id=None, condition_out=None)` (:250) ticks `journey_task_id` (:276-279).

**Facade:** `pb.assets.create_request(vals)` (`pb_assets_board.py:630`).
- vals: `employee_id, category_id, country_id, needed_by, justification, submit`.
- Returns `{id,name,spare}` or `{id,name,warning}`.
- **It does not accept `journey_task_id`.**

**Assignment:**
- `pb.assets.assign(asset_id, employee_id, condition=None)` (:580) returns True and needs the assets manager.
- The model method `pb.asset.action_assign(employee_id, condition_out=None, notes=None)` (`asset.py:240`) returns
  the `pb.asset.assignment`.
- `find_spare(category_id, country_id=None)` (`asset.py:369`).

**→ Studio equipment chips:** have `_raise_asset_requests` read the chosen categories, or every
`auto_assign_at_joining` category, instead of the hard-coded `cat_laptop`. Link each request to the laptop task,
or to a new generic equipment task. Keep requests in draft as today, or submit them. That is a design decision,
listed in the questions.

---

## I. Letters (pb_doc_contracts 19.0.1.0.0)

**API on AbstractModel `pb.contracts`** (`pb_doc_contracts/models/pb_contracts.py:52`). It works on `hr.contract`
and refuses a contract with no employee (:93-96).

| Call | Line | Returns / notes |
|---|---|---|
| `contract_document_available(contract_id)` | :56 | bool, never raises |
| `contract_document(contract_id, lang=None, template_id=None)` | :291-344 | preview `{ok, html, lang, langs, documents, document, missing, left_out, pay_blocked, can_file, file_msg, versions, next_version, …}` or `{ok:False,msg}` |
| `contract_document_pdf(...)` | :389-397 | `{ok,name,data}`; files nothing |
| `contract_document_save(...)` | :401-454 | `{ok, version, name, document_id, versions, next_version}` |

**`contract_document_save` filing:**
- Creates `ir.attachment` (:426) and a `pb.employee.document`
  `{employee_id, category_id, name "<doc> · vN · <date>", attachment_id, issue_date, company_id, pbdc_contract_id,
  pbdc_version}` (:433-442).
- The category is the template's `vault_category_id`, else `cat_labor_contract` (:421).
- Every save is a new version.

**Templates** (`pb.letter.template`, `letter_type='employment_contract'`, `data/contract_templates.xml`):
- `contract_template_generic` (:22, English)
- `contract_template_vn` (:62, `vi_VN`)
- `contract_template_id` (:130, `id_ID`)
- **No India or Singapore contract wording exists.**

**Country and language:**
- Country swap: `_pbds_swap_template` (`pb_doc_studio/models/hr_letter.py:104`) by `_pbds_country_of_work`
  (`doc_studio.py:111`), which is `payroll_country`, else the company country.
- Languages: `_pbdc_langs` (:107) and `_pbdc_pick_lang` (:131).

**States:** documents have no workflow state, only `verified`.

**E-signature: DOES NOT EXIST** for contracts (`__manifest__.py:22` "No e-signature"). It exists only for Hiring
offers (`pb_hiring/models/esign.py`, `docusign.py`).

**→ Studio toggle "Prepare the contract letter":** after the contract is created, call
`contract_document_save(contract_id)`.

---

## J. Custom fields (pb_form_studio)

**`render(self, host_key, record_id)`** (`pb_form_studio/models/form_studio.py:1576`):
- Returns `{sections:[{id,title,icon,tone,kind,note,fields:[… value, display, writable]}], version, can_write,
  currency}` (:1626-1629).
- Overridden for `employee_detail` (`pb_form_studio_people/models/form_studio.py:302`): AccessError unless the
  caller is HR.
- **It cannot run without a record.** `browse(int(record_id)).exists()` is followed by
  `raise UserError('This record no longer exists.')` (:1584-1586). `None` raises a TypeError.

**`write_values(self, model, record_id, vals)`** (:1697):
- Accepts only `x_pbfs_*` fields with `meta.custom` (:1726).
- Checks the field's countries against the record (:1732) and enforces `is_required` (:1740).
- Returns `{ok:True, values:{name:{value,display}}}` or `{ok:False, error?, errors:{name:text}}` (:1705-1706).
- It needs a saved record (:1713-1715).

**Employee host** `employee_detail` on hr.employee (`pb_form_studio_people/models/form_studio.py:18-19`,
:117-175):
- Locked sections: `profile`, `personal`, `job`, `pay`, `documents`, `resume`, `settings`, `timeline`.
- Open sections: `custom` ("Company details"), `job_more`, `person_more`.
- `country_field='pbfs_country_of_work_id'`, computed from `payroll_country` (`models/hr_employee.py:76-90`).
- The contract host is `contract` (`pb_form_studio_contracts/models/form_studio_host.py:20-21`).

**Field settings, `pb.form.field.meta`** (`pb_form_studio/models/form_field_meta.py`):
- `is_required` (:30)
- `country_ids` (:34; empty = every country)
- `portal_show` ("show on My Payobook", :43)
- `portal_edit` (employee can change, :44)
- `portal_mode` approve/instant (:45)
- also `vis` (:28), `list_ok`, `formula_ok`, `custom`, `host_key`

**The definitions-only seam:** `fields_for(self, model, purpose='list', record=None)` (:1756). It is public and
needs no record.
- `purpose` is `'list'`, `'formula'`, `'all'` or `'portal'`; anything else returns nothing (:1776-1778).
- `purpose='all'` gives, per custom field, `{name,label,help,type,kind,type_label,vis,required,list_ok,formula_ok,
  countries,options,comodel}` (:1794-1801).
- **It is not filtered by country and has no section.** `'portal'` adds `section` and `edit`/`mode`, but only for
  `portal_show` fields (:1825-1831).
- Section placement lives in the private `_pbfs_effective(host_key)` (:737).

**→ Studio flow:**
1. Call `fields_for('hr.employee','all')` and filter on `countries` ∋ the chosen country.
2. Collect the values.
3. After the employee is created and `payroll_country` is set, call `write_values('hr.employee', emp_id, vals)`,
   or `pb.people.pbfs_save_employee` (`pb_form_studio_people/models/pb_people.py:109`).

**Caution:** when the hire waits for approval, `create_employee` returns `employee_id=0`
(`pb_people_advanced/models/people_wizards.py:217`, `pb.newhire.proposal` at `newhire_approval.py:55`). The
custom values, the asked items, the login choice, the buddy, the equipment and the letter flag must then **ride in
the proposal payload** (`payload={'values': ...}`, :203-215) and be applied when it is approved. That seam belongs
to the core fact sheet.

---

## K. Hiring hand-over (pb_hiring 19.0.2.23.8)

### K1. `pb.hiring.offer.action_confirm_joined(self, joined_on=None)` (`pb_hiring/models/offer_closure.py:70`), in order

1. If already `joined`, it returns True. If not `signed`, it raises (:81-88).
2. Writes `joined_on` (:93).
3. `_ensure_employee` (:160). This is the only step that can stop everything.
   - It uses `applicant._get_employee_create_vals()` (:194) plus `work_email`, `job_title`, the manager as
     `parent_id`, and the company (:195-208).
   - It copies `applicant.attachment_ids` to the employee as plain `ir.attachment` (:213-215), **not vault
     documents**.
4. Separate steps, where one failure does not undo the others:
   1. `_mark_applicant_hired` (:226)
   2. `_ensure_contract` (:252): a direct ORM `hr.contract` create with `wage`, `date_start`, `company_id`,
      `resource_calendar_id` (:298-309). It is gated by `P_CREATE_CONTRACT` and **does not use the Add employee
      path**.
   3. `_ensure_package` (:345): a draft `pb.employee.comp`.
   4. `_ensure_benefits` (:331).
   5. `_ensure_login` (:402) → `_auto_create_login`.
   6. `_ensure_case` (:430) → `_open_case` (:445) + `_after_onboard` (:452).
   7. `_hand_over_buddy` (`joining_p6.py:1227`).
   8. `_hand_over_laptop` (`joining_p6.py:1298`): notes on the laptop step and on the `pb.asset.request`.
   9. `_file_signed_copy` (:463-525): each `pb.hiring.offer.document` becomes a `pb.employee.document` (:513),
      category `cat_labor_contract` or `cat_other`.
5. Writes `state='joined'`, `join_status='confirmed'`, `closed_on` (:124).
6. `_stamp_hire_date` (:146), `requisition_id._on_filled` (:135), `_tell_them_they_joined` (:530).

Extensions: `hooks_p8.py:186` (the "joined" automation) and `pb_hiring_internal/models/offer.py:172` (internal
moves).

**Overlap with the studio:** the employee, contract, login, case, buddy, laptop and letter filing all duplicate
studio steps 1-6.

**→ If "Confirm they joined" opens the studio** (POC :439), the studio must:
- either call `action_confirm_joined` after its own create, passing the employee so that `_ensure_employee`
  reuses it
- or the hand-over legs must check for a contract, login or case that already exists, which `_open_case` and
  `_auto_create_login` already do

`_ensure_contract` and its reuse of an existing contract were not checked here (see the open questions).

### K2. "Signed offers waiting to join"

- `pb.hiring.offer.state == 'signed'` (`offer.py:179`; `OFFER_STATES` in `hiring_common.py:380-390`).
- Optionally `join_status in ('pending','changed')` (`joining_p6.py:854`; values in `hiring_common.py:402`).
- Date: `expected_join_date` (`joining_p6.py:851`), else `start_date` (`offer.py:122`).
- **A ready-made "all waiting offers" query DOES NOT EXIST.** The closest is the week-before job's domain
  (`joining_p6.py:1391-1394`).
- **Live: 0 signed offers on all five databases.** payobook has 4 joined, the rest 0. So "From Hiring" shows an
  empty list everywhere today.

**"Before they join":**
- `pb.hiring.prejoin` (`joining_p6.py:210-262`): `kind` buddy/laptop/chat/todo, `owner`, `state`, `due_date`,
  `answer_json`. Laid out by `_lay_out_prejoin` (:1041) from `pb.hiring.prejoin.template` (:171).
- Rows come from `pb.hiring._item_row(item, offer, can_recruit)` (`facade_p6.py:77`) inside
  `_joining_payload(offer, can_recruit)` (:135-206).

### K3. Where candidate files and values live, and how to copy them

| What | Where | Copied on join today? | How to copy |
|---|---|---|---|
| Requested papers | `pb.hiring.docreq.item.attachment_id` (`docreq.py:442`); attachment `res_model='pb.hiring.docreq'` | **NO** ("docreq" does not appear in `offer_closure.py`) | Per received item: `vault_upload_batch(emp, category, [{payload: base64 of the attachment}])`, or create a `pb.employee.document` directly with a copied attachment. **The item has no category**, so add `vault_category_id` to `pb.hiring.doc.template` + item and seed `doc_id`→`cat_id_document`, `doc_degree`→`cat_certificate`, `doc_tax`→`pb_me_tax.cat_tax_paper`, `doc_payslip`→`cat_other`, `doc_photo`→`image_1920`. |
| Bank paper (`doc_bank`) | the same, a file | **NO** | `pb.bank.ocr.create_from_upload({name,mime,data,employee_id})`, then `run_ocr`, then `do_action('submit')`. It goes to a second person. |
| Typed bank, tax or ID numbers | **DOES NOT EXIST** in pb_hiring | – | Only the bank OCR result. Tax and ID numbers must be asked for in the welcome link, or typed by HR. |
| Signed offer papers | `pb.hiring.offer.document` (`joining_p6.py:124-160`), `vault_doc_id` | YES (`_file_signed_copy`) | – |
| Applicant attachments | `hr.applicant.attachment_ids` | as plain `ir.attachment` on hr.employee (:214) | – |
| Laptop and buddy wishes | `pb.hiring.prejoin.answer_json` | YES (`_hand_over_laptop`, `_hand_over_buddy`) | – |

### K4. Background-check gate

- `pb.hiring.bgv.state` open/complete/flagged (`bgv.py:92`). Override fields `override_user_id`, `override_on`,
  `override_note` (:99-103).
- `check_ready()` returns `(ok, sentence)` (:206). `action_override(note)` is for managers only (:235).
- **It does not block on the server.** It is only shown as a warning (`pb_hiring_a3.py:353`,
  `hiring_board.xml:1129`) and decides when the papers request goes out (`requests_p3.py:1231,1272`). Neither
  `offer.py:312` nor `action_confirm_joined` checks it.

---

## L. Learn and coach impact

**The current wizard:**
- Client action `pb_onboard_wizard` (`pb_people_advanced/static/src/js/onboard_wizard.js:127`,
  `views/wizard_actions.xml:3`).
- Opened from `pb_people/static/src/js/people.js:324` and `pb_orgchart/static/src/js/orgchart_edit.js:360`.
- Code that inherits it: `pb_pay_scales/models/joiners.py:86`, `pb_orgchart/models/onboard_fill.py:20`,
  `pb_pay_scales/static/src/xml/joiner_hint.xml:41`, `pb_updates/models/updates_joiners.py:824`.

**Coach anchors:**
- `onboard_wizard.xml` has no `data-coach` anchors.
- The Add employee button (`pb_people/static/src/xml/people.xml:26`) sits inside `data-coach="pe-head"` (:11).
- pb_coach or tours for this screen: **DOES NOT EXIST**.

**Hits to update when the wizard becomes the studio:**
- `pb_learn/static/src/anchors.json:587-590`: `pe-head` text "three-step onboarding wizard (pb_people_advanced)…
  `addperson` intent".
- `anchors.json:2224-2227`: `rep-newemp-open/name/div/save`.
- `pb_learn/static/content/learn_content.json`:
  - :5831 "three-step wizard… person, role, contract"
  - :5866-5868 step "Add employee — person, role, contract"
  - :5890
  - :5900-5925 intent `addperson` (`show_me` `pe-head`, `ct-roster`; `try` `sc_people`)
  - :15209-15365 lesson `sc_people` "Add your first employee" (steps `rep-newemp-*` at :15254, :15289, :15330,
    :15365)
  - :21468
- `pb_learn/static/src/engine/screens.js`: :370-389 `newEmployeeHTML` replica form, :593, :638 `pe-head`, :641
  `rep-newemp-open`.
- `pb_learn/static/src/engine/fixture.js:2432`: `rep-newemp-name`.
- `pb_learn/tests/test_scenario.py:504-507`: asserts the four `rep-newemp-*` steps.
- `pb_people/learn_manifest.py:190`: comment.

**Standing rule:** a screen change updates its lessons and replicas in the same work. Remember the trap where the
Learn generator wipes `pb_learn/i18n/vi_VN.po`.

---

## M. Deploy conventions (read-only summary)

**Sources:**
- `CLAUDE.md` deploy contract
- `docs/deploy/PENDING.md:1-35`
- `tools/deploy_status.py:1-60`
- `docs/handovers/wfsetup/WFSETUP_P5B_DEPLOY_HANDOVER.md` §0, §2
- `WFSETUP_P5B_REPORT.md` §1, §4, §5
- server `/opt/deploy-notes.md` (last 40 lines read 2026-11-25)

### M1. Live databases

**Five: `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`.**

Every deploy-notes line since 21 Nov names these five. **Never `abm`.**

Two docs are out of date:
- Root `CLAUDE.md` still names four, without sudima.
- `PENDING.md` (:4-5, :19) still talks about `abm`.

There is also a leftover database `_test_sudima_policy_20261119` on the server. It is not in the deploy set; do
not touch it.

### M2. Real recipe (risky / full tier, as run for WFSETUP P5b)

1. Merge in a fresh worktree from `origin/19.1`, run the suites, and push. Stage from `git archive` of the
   **pushed** commit, named modules only. Never the vendored standard addons; split them with
   `git -C /odoo/odoo-server ls-files addons`.
2. Read `/opt/deploy-notes.md`. Stop if there is an open START or a HOLD. Append a `START` line in the format
   `date UTC | who | START | modules+versions | dbs | commit | what/why`. Take
   `flock /tmp/payobook-studio-deploy.lock`; an empty lock left by root counts as stale and is noted. Announce the
   deploy to the other live sessions.
3. Quiet check: 15 minutes with no signed-in activity on rize, payobook and sudima.
4. Cron snapshot per database. **Compare counts of active jobs; do not grep `,f$`.**
5. Backups ×5 with `pg_dump -Fc` into `/odoo/backups/<prog>-<ts>/`, again right before the stop.
6. Rehearse on a hidden copy:
   - switch off every scheduled job and mail server on it immediately
   - use a separate addons path for the rehearsal
   - `dropdb --force` it afterwards
7. Go-live:
   1. Clean staging: `sudo rm -rf /tmp/deployX && mkdir -p`.
   2. `rsync -az --exclude=__pycache__ --exclude='*.pyc'`.
   3. Per module: `sudo rsync -a --delete /tmp/deployX/<m>/ /odoo/odoo-server/addons/<m>/`. **Never `--delete`
      into the addons root.**
   4. Stop the service.
   5. Per database, one at a time: a detached unit with an exit sentinel running `-i/-u`. Order:
      payobook_template → p0clone → sudima → rize → payobook.
   6. Per database: asset purge (`DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'`),
      `orm_signaling_assets`, `web.assets.version` bump.
   7. Start the service and warm every site (expect 200).
8. Verify:
   - module tree hashes on both sides (skip `__pycache__`, `*.pyc`, `.DS_Store`)
   - manifest vs `latest_version` ×5, normalising the `19.0.` prefix; `python3 tools/deploy_status.py`
   - jobs vs the snapshot (payobook job 156 stays off; payobook_template jobs that an upgrade switched back on
     go off again, and a new job's id is added to `pb_tenants.template_active_crons`)
   - server log 0 ERROR
   - Chrome walk with the QA login
9. Append `DONE` (downtime seconds, per-database exit/time) and a `NOTE` (verification). Remove the lock. Commit a
   non-sensitive report.

**Remember:** a new stored field must be upgraded on all five in the same window, because one addons directory
serves every database.

### M3. Installed matrix (live, 2026-11-25; repo manifest = installed everywhere unless marked)

| Module | Repo | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|---|
| biz_access | 19.0.1.14.1 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_assets | 19.0.1.3.0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_bank_ocr | 19.0.1.6.1 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_clock | 19.0.1.4.3 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_doc_contracts | 19.0.1.0.0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_doc_studio | 19.0.1.1.0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_employee_bank_panel | 19.0.1.1.1 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_employee_form_tidy | 19.0.1.4.1 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_employee_vault | 19.0.1.6.5 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_form_studio | 19.0.1.8.0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_form_studio_people | 19.0.1.9.0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_form_studio_portal | 19.0.1.2.0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_hiring | 19.0.2.23.8 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_learn | 19.0.20.8.10 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_lifecycle | 19.0.1.21.0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_me_details | 19.0.1.0.2 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_me_portal | 19.0.3.8.1 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_me_privacy | 19.0.1.0.0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_me_tax | 19.0.1.0.1 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_onboarding | 19.0.1.4.0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_orgchart | 19.0.1.7.0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_pay_scales | 19.0.1.2.0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_people | 19.0.1.3.5 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_people_advanced | 19.0.1.2.0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_probation | 19.0.1.6.0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_scheme_map | 19.0.2.5.6 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_updates | 19.0.1.8.0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| pb_workforce_setup | 19.0.1.4.1 | ✓ | **not installed** | **not installed** | **not installed** | ✓ |
| pb_zoho_bridge | 19.0.1.2.1 | ✓ | ✓ | ✓ | ✓ | ✓ |

✓ = installed at the repo version. **No version drift.**

**Live settings that matter:**
- `auth_signup.invitation_scope=b2c` on all five.
- `auth_signup.signup.validity.hours` unset (144 h default) on all five.
- `pb_zoho_bridge.auto_create_logins=1` on all five.
- `cron_lifecycle_reminders`: off on payobook, on elsewhere.
- `cron_pb_employee_document_expiry`: off on payobook and payobook_template.

**→ Everything the studio needs is installed on all five databases.** A new module that depends on pb_hiring,
pb_onboarding, pb_me_details, pb_me_tax, pb_bank_ocr, pb_assets, pb_doc_contracts and pb_form_studio_people can
be installed everywhere. **Do not** depend on pb_workforce_setup: it is installed on 2 of the 5.

---

## Open questions / risks

1. **Password wording (owner).** The welcome link asks the person to choose a password once, unlike the POC's
   "no password". The alternative is a new no-login token page that writes bank and ID numbers before sign-in.
   We recommend against it.
2. **Personal email (owner + design).** A joiner without a work email gets no login from `_auto_create_login`
   (it is `work_email` only). The link must go to the personal email, which needs a variant that uses
   `private_email` as the login.
3. **Hiring "Confirm they joined" vs the studio (design).** Both create the employee, contract, login, case,
   buddy and laptop. Pick one owner of each step. `_ensure_contract` writes `hr.contract` directly and
   bypasses the scheme and approval path. Check whether it reuses an existing contract.
4. **"Bank, tax numbers come across" from Hiring is not true today.** Only files exist. Bank can come across via
   OCR → bank request. Tax and ID numbers cannot. The POC copy must change, or Hiring gains typed fields.
5. **Approval-pending hires (`employee_id=0`).** Everything around the person must ride in the
   `pb.newhire.proposal` payload and be applied on approval. That includes asked items, custom fields, papers
   attached by HR, login choice, buddy, equipment and the letter. Uploaded files waiting in a proposal need a
   storage decision.
6. **Who edits "papers per country"?** The category screen is system-admin only today. Opening it to HR managers
   is a permission change, so the owner decides.
7. **Equipment.** `auto_assign_at_joining` does nothing today. Should the studio's chips raise requests already
   submitted (manager → equipment approval), or drafts as the laptop does today?
8. **Singapore NRIC and residency are stored twice** (`singapore_nric_fin` vs `identification_id`;
   `singapore_tax_residency` vs `pb_sg_tax_residency`). The studio must write the one payroll reads. There is no
   Aadhaar field and no NIK field: `identification_id` is used for both.
9. **No contract wording for India or Singapore** (only generic, VN, ID). On payobook the reminder job and the
   onboarding mails are off, so the welcome link's reminders cannot be shown working there. Test them on a copy.
10. **Leftover database `_test_sudima_policy_20261119` on the live server.** Every database answers on the
    internet. Flag it to the owner. Do not drop it without asking.

## Corrections and additions found in P2 (2026-11-25)
- §F3 `_open_case` picks the template by `employee.country_id` (nationality), not the Country of Work (NH19).
- §F4 `case_open` steps are dated `fields.Date.today()` (UTC) — NH26.
- §F5 buddy: `pb.onboarding.buddy_choose` = `open_for` + `choose` behind the lifecycle-manager gate; Hiring's
  `_hand_over_buddy` calls `pb.buddy.nomination.sudo().open_for(...).choose(...)` directly — the studio does the same.
  `choose` sends the buddy mails (`P_BUDDY_MAIL`); only the joiner's goes when the buddy has no work email.
  `check_candidate(False, person)` works without a joiner record (location rule skipped): the studio shows its verdict.
- §F7 `pb_probation.auto_trigger` is OFF by default (NH25); check-ins d30/d60/d90 and pulses 7/30/60 are always planned
  by `setup_onboarding`.
- §G `create_worker_logins` needs the access-manager role (`_require_manage`), sudo does not help (NH23). No employee code
  is generated; the sign-in code is barcode → clock number → identification number (NH24). Slips print only at creation.
- §H `pb.asset.request.action_cancel` works from draft under sudo; `pb.asset.category.icon` names are mostly in the
  shared Lucide registry (unknown ones fall back to `package` in the studio).
- §I the letter needs the payroll-manager right to file (NH20); templates in the walk DB are shared (company empty).
- New joiners board: `pb_onboarding.action_pb_onboarding_board` (tag `pb_onboarding_board`), gate `_can_read`
  (Lifecycle roles or admin) — NH30.
