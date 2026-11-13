# RECRUIT — Phase 7: where the role goes — channels with tracked links, the agency portal, the 6-month rule

Delivers register lines **G-20 and G-21**: a "Publish to…" panel per role that gives a
tracked link per channel (careers page, LinkedIn, JobStreet Indonesia, VietnamWorks,
employee referrals, agencies) so every application carries its source even when the
posting is pasted on the board's own site; the existing advert-by-email pack behind the
same panel; a connector seam for direct posting later (per subscription); an external
agency portal (an agency login sees only the open roles assigned to it, submits
candidates through a form, every submission tagged Source = Agency, no internal data);
the 6-month cooling rule; agency performance on the vendor card and Hiring numbers.

Read first, in order: `docs/handovers/recruit/RECRUIT_LEDGER.md` (all rows incl.
P1–P6), the **P1–P6 phase reports** (shapes: `get_requisition`, the Details tab
sections, `pb_country_id`, `pb_possible_duplicate_id` (P2), `request_state` and
`is_confidential` (P3), `parts_for` (P4), `_sender` (P3), `get_funnel` (P6)), the
blueprint sections "Who sees what" (Agency row) and "Hiring home", the register lines,
then this file. Facts verified 2026-09-30; re-locate moved lines by name.

---

## 0. Scope and binding non-goals

**In scope (P7):** `pb_hiring` **19.0.2.6.0** with a migration; `pb_vendor_access`
**19.0.1.12.0** (agency portal users on the vendor).
1. **Channels** `pb.hiring.channel` (seeded per company: Careers page, LinkedIn,
   JobStreet (Indonesia), VietnamWorks (Vietnam), Employee referrals, Agencies) with
   a kind, a utm source, an optional email contact (the advert pack), countries where it
   applies, and a connector key (`manual` for all of them now).
2. **Publish to… panel** on the role (header button + Details tab "Where it has gone"):
   one row per channel that applies to the role's country: the tracked link (copy
   button), "Mark as posted" (date, by, optional link to the live posting), the advert
   email pack for channels with a contact ("Send the advert"), the referral link, the
   agency row (assign agencies, invite them, their portal link). Publishing to the
   careers page stays what it is today (job published + JD text).
3. **Attribution fixes**: utm names matched case-insensitively to seeded rows (today
   `linkedin` creates a second source beside `LinkedIn`); JobStreet and VietnamWorks
   `utm.source` rows seeded; each tracked link = a stock job tracker
   (`hr.recruitment.source`) so the stock "Trackers" data stays consistent.
4. **Connector seam**: `pb.hiring.channel.connector` (abstract) with `post(role)`,
   `status(role)`, `close(role)`; one working connector `manual` (records the posting)
   and the interface documented for JobStreet / VietnamWorks / LinkedIn later (owner item:
   subscriptions and API access).
5. **Agency portal** (`/my/agency`): agency logins are portal users linked to the
   vendor; the page lists the open roles assigned to the agency (title, department,
   country, JD text, close-by date, how many they have put forward), a submit form per
   role (name, email, phone, location, CV, note, "the candidate agreed to be put
   forward"), and "People you put forward" with a coarse stage (In review / Interviewing
   / Offer / Joined / Not selected). No internal notes, no money, no other candidates.
6. **6-month rule** on agency submissions: refused with a sentence when the same email
   or phone already exists as an active candidate in ANY of the company's pipelines, or
   applied/was submitted in the last 6 months (any state); the sentence gives only the
   date. Every submission attempt is logged (`pb.hiring.agency.submission`, incl.
   refused ones).
7. **Several agencies per role** (`agency_vendor_ids` m2m; migration copies the old
   single field); invite an agency (creates the portal login from the vendor's contact
   email, sends the invite with a set-password link); "agency assigned" mail to the
   hiring manager kept + a new mail to the agency with the portal link.
8. **Performance**: vendor card counters and Hiring numbers agency section switch to
   submission-based figures (submitted, reached interview, offers, joined, refused by
   the rule, days to fill on their roles).
9. Tests, deploy (three DBs, never abm), Chrome validation incl. the portal at phone
   width, report.

**Binding non-goals:** real board APIs (the seam only); the careers listing page
redesign (on hold, Rize); referral portal changes beyond the tracked link (exists);
email languages for agency mails (P8; agency mails are English); changing
`vendor_license_core`; anything on the agency side beyond submit + status.

---

## 1. Verified plumbing facts (do not re-derive)

### 1.1 Posting today (`pb_hiring/models/posting.py`)
- `pb.hiring.posting` :27-55 (`requisition_id`, `job_id`, `platform_id` → `hr.job.platform`,
  `platform_email`, `subject`, `body_html`, `state` ready/sent `hiring_common.py:151-154`,
  `sent_on`, `sent_by`, `company_id`; unique (requisition, platform) :53-55; no URL/utm/
  API fields). `publish_for` :65-132 (needs `state=='open'` + `jd_current_id` :76-84
  — P3 decoupled roles from requests: re-check that "open" now means the ROLE state;
  writes `website_published` + `website_description` sudo :86-92, `req.published` :93
  (field `requisition.py:216`); loops EVERY `hr.job.platform` with no company filter
  :95; refreshes `ready` rows / creates missing :97-111; returns `{made, refreshed,
  platforms, mail_on, note, job_id}`). `_render_pack` :134-169 (URL = `job.full_url`
  or `web.base.url + '/jobs'` :145-153 — same for every platform, no utm). `_send_one`
  :179-205 (flag `pb_hiring.platform_mail` default '0' `hiring_common.py:28,58`; template
  `mail_template_posting` `data/mail_template_data.xml:120`).
- `hr.job.platform` (`hr_recruitment/models/hr_job_platform.py:7-33`: `name`, `email`
  required unique, `regex`; seeds `hr_recruitment_data.xml:103-119` Linkedin / Jobsdb /
  Indeed; core uses the email for INBOUND parsing `hr_applicant.py:960-968`). No JobStreet
  / VietnamWorks rows.
- `hr.job` publish fields: `website_published` (mixin `website/models/mixins.py:280-297`;
  `website_hr_recruitment/models/hr_job.py:38`), `published_date` :50/:58-61, `full_url`
  :51-56 (`/jobs/<slug>` :70-76); closing unpublishes (`requisition.py:589-598`).
- Screens: `action_pb_hiring_jd` "Job descriptions" `views/hiring_views.xml:359`;
  `action_pb_hiring_posting` "Adverts" :519 (list :467-484, form :486-517); requisition
  form "Adverts" page :164-175; no menuitems. Board `_act_publish` `pb_hiring.py:681-684`
  → `action_publish` `requisition.py:834-836`; `_act_send_posting` :686-693; drawer
  `postings` :484 via `_postings` :506-515. P1 Details tab: `hiring_board_p1.xml:176-178`
  → `pb_hiring.RoleDetails` (`hiring_board.xml:983`); adverts section "Where it has gone"
  :1345-1363; "Advertise it" :1404; header Publish `hiring_board_p1.xml:29-31, 43-44, 90`.

### 1.2 Attribution
- `_pb_hiring_touch` `controllers/application.py:33-44` (utm_* ≤200 chars, referrer,
  landing_url via `clean_url` :15-24; session `pb_hiring_attribution` first/latest);
  called on `/jobs`, `/jobs/<job>`, `/jobs/apply/<job>` :46-63. Submit :108-121:
  `pb_first_touch`/`pb_application_touch` (Json `journey.py:308-309`, non-sudo writes
  blocked :317-318); utm records searched `('name','=',name)` (case-sensitive) or created
  with the RAW name :116-121 → duplicates like `linkedin` vs `LinkedIn`. Board reads
  `source_id.name` or `touch['source']` (`board_p1.py:477-479, 703, 715, 837-838`).
- Seeded utm: `utm/data/utm_source_data.xml` (… LinkedIn `utm.utm_source_linkedin`,
  Referral `utm.utm_source_referral` …); mediums `utm_medium_data.xml`; campaign
  `hr_recruitment.utm_campaign_job` "Job Campaign" (`hr_recruitment_data.xml:39`).
- Stock trackers: `hr.job.job_source_ids` (`hr_job.py:86`) → `hr.recruitment.source`
  (`hr_recruitment/models/hr_recruitment_source.py:7-59`, inherits `utm.source.mixin`
  `utm/models/utm_source.py:55-58`; fields `email`, `has_domain`, `job_id`, `alias_id`,
  `medium_id` default website, `campaign_id`; `create_alias` :27-47) with `url` from
  `website_hr_recruitment/models/hr_recruitment_source.py:12-24` =
  `<base>/jobs/<slug>?utm_campaign=Job Campaign&utm_medium=<medium>&utm_source=<source>`
  (the JOB page — our touch on `/jobs/<job>` captures it). Trackers tab
  `hr_recruitment/views/hr_job_views.xml:352-353`, action `action_hr_job_sources`
  (`hr_recruitment_source_views.xml:29`), URL column
  `website_hr_recruitment/views/hr_recruitment_views.xml:3-9`.
- Referral source: `referral._referral_source()` searches `utm.source` `=ilike 'Referral'`
  or creates (`referral.py:185-193`); `journey.py:505-524` writes
  `pb_application_touch={'source':'Referral','referrer_employee_id':…}`.

### 1.3 No board APIs; HTTP precedents
- Core `/Users/adity/odoo19/odoo/addons` has NO `hr_recruitment_integration_*`, no
  linkedin/indeed/jobstreet/vietnamworks module; `posting.py:4-9` docstring records
  ruling D12 (outside services off). `pb_zoho_bridge` is inbound-only
  (`controllers/zoho_webhook.py:50`). Outbound precedents: `pb_hr_payroll_formula/integrations/zoho_connector.py`
  (`ZohoConnector` :30, `_feed_request` timeouts 30/60 :125-136, `_payload` error
  mapping :220-248, no retries; creds on `hr.integration.connector` :90-130 with
  `groups=base.group_system`; status via `update_connector_status` `base_connector.py:338`);
  `pb_zoho_sso/controllers/main.py` (`_HTTP_TIMEOUT=10` :6, params :53-65,
  `RequestException` → friendly 502 :217-225).

### 1.4 Agency today
- `pb.vendor` `pb_vendor_access/models/pb_vendor.py:38-93` (`name`, `vendor_type`
  incl. `recruitment` `vendor_common.py:42-51`, `active`, `contact_name/email/phone`,
  `department_id`, `responsible_user_id`, `country_id`, `notes`, `company_id`,
  `agreement_ids` (`pb.vendor.agreement` :152), computed counts) — **no `partner_id`, no
  portal user link**; `pb_vendor_access` has NO controllers/routes; groups
  `group_vendor_user` (security :45-49), `group_vendor_manager` :53-57; rules company
  :73-77, owner :121-125; no portal ACLs; `pb.vendor.user` does not exist. Working copy
  has uncommitted edits in pb_vendor_access (manifest, `catalogue_vi.py`, `hooks.py`,
  `migrations/19.0.1.11.0`) — those are P1's (Talent lead rename); build on top, do not
  revert.
- `requisition.agency_vendor_id` `requisition_a3.py:32-38` (domain recruitment,
  tracking); picker `pb_hiring_a3.py:190-196`; drawer `agency_id`/`agency` :215-216;
  `_act_set_agency` :676-684; `<select>` `hiring_board.xml:1279-1285`. Mail on change:
  `write` `requisition_a3.py:148-165` → `_tell_them_about_the_agency` :167-193 (flag
  `closure_mail` default '1' `hiring_common.py:87`; to reporting manager or requester;
  template `mail_template_requisition_agency` `data/mail_template_offer.xml:262-286`).
  Vendor counters `vendor_ext.py:25-67` (`hiring_count` = Σ `filled_count` of its roles,
  NOT people it submitted; `hiring_avg_days` = `filled_on − opened_on`), stat buttons
  `views/vendor_views.xml:23-46`. `vendor_license_core` is unrelated — never touch.
- Analytics `_agency_split` `analytics.py:389-411` (with/without `agency_vendor_id`;
  spans of filled roles); UI `hiring_numbers.xml:213-221`, `hiring_numbers.js:59,115`.

### 1.5 Portal precedents, security, cooling
- `/my/refer` `controllers/portal.py:211-230` (+ submit :232-288, `auth='user'`;
  employee via `hr.employee.user_id` `_hiring_employee` :52-59; CV ≤5 MB :28, MIME
  :29-33, `?problem=` redirects :36-46) → `pb.hiring.referral.refer` (override
  `journey.py:505-524`: own user, role open + `referral_open` + not sensitive, consent +
  declaration + all fields + attachment; base `referral.py:107-146`, `_make_applicant`
  :148-183). Templates `views/portal_templates.xml` (`portal_my_refer` :100, roles
  :136-185, form :189, home card :62-71, `portal_my_hiring` :283); `_open_roles`
  `portal.py:61-70` (`state='open'`, `referral_open`, not sensitive, employee's company,
  limit 60; deep link `/my/refer?role=<id>#refer-form` :175); `referral_open` field
  `requisition.py:212` (auto :820-829, cleared :555/:568, toggle `pb_hiring.py:671-679`).
- Portal user creation precedent: `pb_zoho_bridge/models/zoho_pipeline.py:586-625`
  `_auto_create_login` (`res.users` with `group_ids=[(6,0,[base.group_portal])]`,
  `company_ids`, context `no_reset_password`; linked via `hr.employee.pb_portal_user_id`).
  No `portal.wizard` use in pb_*.
- **Portal users cannot read requisitions**: ACLs `pb_hiring/security/ir.model.access.csv:2-6`
  only internal groups; rules :77-80 (company), :228-233 (own, `base.group_user`),
  :235-239 (all, hiring user). Public job gate `hr_job_ext.py:19-30`
  (`pb_hiring_accepts_applications`: active, `is_published`, company == website company,
  website match, latest requisition open and not sensitive) used by `application.py:28-31`
  and `rize_website/views/careers_templates.xml:110`.
- Cooling/duplicates: core `email_normalized` :54, `partner_phone_sanitized` :64-66 /
  :218-223, `application_status` :128-133/:514-523, `_get_similar_applicants_domain`
  :311-336 (email / phone / linkedin / pool, `active_test=False`); stock
  `check_recent_application` (`website_hr_recruitment/controllers/main.py:203-253`):
  the 6-month rule there is ONLY refused applicants on the SAME job; advisory. P2's
  `pb_possible_duplicate_id` was NOT present in the working copy at the time of this
  read — take its final name from the P2 report.
- Careers listing: `rize_website` `rz_jobs_index` (`careers_templates.xml:20`) loops the
  stock `jobs` :41-47 (shows "Not public yet" for signed-in users); stock `/jobs`
  (`website_hr_recruitment/controllers/main.py:27+`, filters :120-137, domain
  `website.website_domain()` `website/models/website.py:105-106`; no explicit company
  filter — publication enforced by rules `website_hr_recruitment_security.xml:6-18,26-28`).
- Tests: `test_hiring.py` `TestReferrals` :308 (:316 asserts source "referral"),
  `TestPublishing` :366, `TestTheAdvert` :251, `TestTheDoors…no_menu` :711;
  `test_offer.py` `TestTheAgency` :680, `TestTheNumbers` :720; `test_interviews.py`
  `TestMyHiring` :740; no HttpCase for `/my/refer`.

---

## 2. Architecture

### 2.1 Channels and tracked links
- `pb.hiring.channel`: `name`, `key` (careers/linkedin/jobstreet/vietnamworks/referral/
  agency/custom), `kind` (Selection: careers / board / social / referral / agency),
  `company_id`, `utm_source_id` (m2o `utm.source`; seeded rows LinkedIn (existing),
  JobStreet, VietnamWorks, Careers page, Referral (existing), Agency (new)),
  `utm_medium_id` (default website / social / email), `platform_id` (m2o
  `hr.job.platform`, optional: gives the advert-by-email pack; seed JobStreet and
  VietnamWorks platforms with placeholder emails only if Rize supplies them — else leave
  empty and the row says "no email contact"), `country_ids` (applies to roles in these
  countries; empty = all), `connector` (Selection: manual / email_pack; later jobstreet /
  vietnamworks / linkedin), `posting_url_hint` (where to paste), `active`, `sequence`.
  Editable in Hiring set-up → "Channels" card (list, toggle per country, contact email).
- `pb.hiring.role.channel` (one per role × channel when the panel is opened or on
  publish): `requisition_id`, `channel_id`, `source_id` (m2o `hr.recruitment.source` —
  created via the stock tracker with the channel's utm source/medium and the job
  campaign; its `url` is the tracked link), `state` (not_posted / posted / closed),
  `posted_on`, `posted_by`, `external_url`, `posting_id` (the advert email row when the
  channel has a contact), `applications` (computed: applicants on the job whose
  `source_id` = the channel's utm source), `note`. Referral row: link
  `/my/refer?role=<id>`; agency row: no link (portal), lists `agency_vendor_ids`.
- Attribution fix in `application.py`: match utm names with `=ilike` and prefer seeded
  rows; never create a new `utm.source` when a case-insensitive match exists; write
  `pb_channel_key` on the applicant when the utm source maps to a channel.
- Publish panel (`get_publish_panel(requisition_id)` + acts `_act_publish_channel`,
  `_act_mark_posted`, `_act_send_pack`, `_act_close_channel`): rows in channel order;
  the careers row = today's publish (button "Publish on the careers page" → job
  published + JD text; "Unpublish"); board/social rows: tracked link + Copy + "Mark as
  posted" (sheet: date, link) + "Send the advert" when a contact exists; referral row:
  link + "Referrals: open / closed" toggle; agency row: assigned agencies with "Invite" /
  "Open their portal view" / "Assign another". Header pill "Published · 3 channels"
  from the rows in `posted`.
- Connector seam: `pb.hiring.channel.connector` AbstractModel with `post(role_channel)`
  → `{ok, external_url, note}`, `status(role_channel)`, `close(role_channel)`; registry
  by `channel.connector` key; `manual` (records only) and `email_pack` (sends the advert)
  implemented; the interface, timeouts (10 s), error surfacing ("could not reach <board>
  — posted nothing; paste it by hand") and credential storage (`ir.config_parameter`
  `pb_hiring.<key>.api_key` with `groups=base.group_system` on a settings field) written
  in the ledger for the later connectors.

### 2.2 Agency portal
- `pb.vendor.portal_user_ids` (m2m res.users, share users) + `pb.vendor.partner_id`
  (created from contact name/email on invite); `action_invite_portal({emails})` on the
  vendor (Talent lead / vendor manager): create portal users (pattern of
  `_auto_create_login`), link, send `mail_template_agency_invite` (from `_sender`) with
  the standard signup/reset link (`user.action_reset_password()` or the signup URL from
  `partner._get_signup_url_for_action`) and the portal link `/my/agency`.
- Requisition `agency_vendor_ids` (m2m; migration copies `agency_vendor_id`; keep the
  old field as a computed first-of for compatibility, read-only); `_tell_them_about_the_agency`
  mails the hiring manager as today for each newly added agency AND
  `mail_template_agency_assigned` to the agency's portal users / contact email with the
  portal link and the JD text.
- `pb.hiring.agency.submission`: `vendor_id`, `requisition_id`, `applicant_id`
  (empty when refused), `submitted_by_user_id`, `submitted_on`, `candidate_name`,
  `candidate_email`, `candidate_phone`, `state` (accepted / refused_rule / withdrawn),
  `refusal_reason` (Char: "already a candidate" / "applied on <date>"), `coarse_stage`
  (computed from the applicant: in_review / interviewing / offer / joined /
  not_selected), `company_id`. ACL: portal read own (`vendor_id.portal_user_ids` contains
  user), create via the controller (sudo). Applicant gets `pb_agency_vendor_id`,
  `source_id` = Agency utm, `pb_application_touch={'source':'Agency','vendor_id':…}`,
  default sharing per role (P4 defaults), and lands in `screening`.
- Routes (`controllers/agency_portal.py`, `auth='user'`, portal users only —
  `request.env.user.share` and a vendor found via `portal_user_ids`; internal users get
  redirected to the board): GET `/my/agency` (roles assigned + my submissions), GET
  `/my/agency/role/<id>` (JD text, close-by, "put someone forward" form), POST
  `/my/agency/role/<id>/submit` (multipart; CV ≤5 MB pdf/doc/docx with magic bytes as
  the apply route; required name, email, phone, agreement tick; cooling check; on refusal
  re-render with the sentence and log the attempt; on success → submission + applicant +
  recruiter to-do + "thanks" state), GET `/my/agency/people` (coarse stages). Every read
  is sudo and exposes ONLY: role title, department, country, JD text, close-by date, the
  agency's own submissions (name, date, coarse stage). Never other candidates, notes,
  money, panel, requester names.
- Cooling rule `pb.hiring.agency.submission._cooling_block(company, email, phone)` →
  `None` or a sentence: active candidate exists in any pipeline of the company
  (`hr.applicant` active, not in a closed-family stage, same email_normalized or
  phone_sanitized) → "This person is already a candidate with us."; any applicant/
  submission with `create_date ≥ today − 6 months` (any state, incl. inactive) →
  "This person applied to us on <date>. Under the 6-month rule this submission is not
  accepted." The window is a parameter `pb_hiring.agency_cooling_months` (6).
- Hiring numbers agency section → submission-based (per agency: submitted, refused by
  the rule, reached interview, offers, joined, days to fill on their roles); vendor card
  counters likewise (`vendor_ext.py`), exported.

### 2.3 UI
- Role header: "Publish to…" replaces the bare Publish button; pill "Published · N
  channels". Details → "Where it has gone" = the panel (rows with icon per channel,
  the link in a mono chip with Copy, state chip, "N applications from here"). Hiring
  set-up → "Channels" card (list + per-channel edit: name, kind, countries, contact
  email, hint) and "Agencies" card (vendors of type recruitment with Invite / portal
  users / roles / performance; links to the vendor register).
- Agency portal pages use the `pbme` kit (`/my/refer` precedent) with a plain header
  ("<Company> · Agency portal"), a roles list, the submit form as a single column, the
  "People you put forward" table with coarse stage chips, and clear refusal sentences.
  Phone width works.

---

## 3. Design (build to the blueprint)

Design bar verbatim (ledger): **"exceptional premium, extreme WOW, a novice can work
without training"**. Hero moment for P7: the Publish panel — one row per channel, a
link that copies with one click and a chip that counts the applications that came
through it, so the recruiter sees which channel works without a report. Zero dead-ends:
a channel with no contact says "no email contact yet · add one in Channels"; a board
with no connector says "paste the advert on <board> and press Mark as posted"; an
agency refusal names the rule and the date, nothing else. Plain words. Agency pages in
English (vi/id `.po` entries only for any candidate-facing sentence). Light and dark for
the internal screens.

---

## 4. Rules (plain English on screen)
- Every channel has its own link; the link is how we know where a person came from.
- Marking a posting as posted is a promise the recruiter makes; the count of
  applications from the link keeps it honest.
- An agency sees only the roles assigned to it and the people it put forward, with a
  coarse stage. Nothing else, ever.
- The 6-month rule: an agency cannot put forward someone who is already a candidate
  with us or who applied in the last six months. The agency is told the date, not the
  details.
- Invite an agency from its vendor record; take the access away by removing the login.

---

## 5. Numbered test cases
1. Seeds: six channels per company; utm rows exist once (case-insensitive); JobStreet /
   VietnamWorks sources; idempotent.
2. Opening the panel creates role-channel rows only for channels matching the role's
   country; each board row has a stock tracker whose URL carries the channel's utm
   source; applying through that URL tags the applicant with that source and channel
   (HttpCase using the touch on `/jobs/<job>?utm_source=…` then submit).
3. `linkedin` / `LinkedIn` / `LINKEDIN` all map to the one seeded source.
4. Mark as posted / close; "Send the advert" only with a contact and the mail switch;
   applications count per channel.
5. Connector seam: `manual` and `email_pack` behave; an unknown connector key raises a
   friendly UserError; the registry is documented.
6. Agency invite: portal user created and linked, invite mail from `_sender`, no
   internal group; a second invite for the same email links the existing user.
7. Assigning a second agency mails the hiring manager once per new agency and the
   agency with the portal link; migration copies the old single field.
8. Portal (HttpCase as the agency user): `/my/agency` lists only assigned open roles;
   another agency's role → 404; internal user → redirect; the JD text shows; no
   requester/panel/money/notes strings in the HTML.
9. Submit: valid → submission accepted, applicant on the role in `screening` with
   Agency source + vendor, recruiter to-do; missing CV → re-render with the sentence;
   wrong file → refused; cooling: active candidate elsewhere → refused sentence, no
   applicant, attempt logged; applied 5 months ago (inactive) → refused with the date;
   7 months ago → accepted; window parameter honoured.
10. "People you put forward" shows coarse stages that follow the applicant's stage;
    a refused submission shows "Not accepted (6-month rule)".
11. Performance figures per agency; vendor counters; export.
12. Existing tests pass (rewrite the single-agency tests).
Browser (payobook.com, light + dark; the agency portal at 360 px):
13. Role → Publish to… → copy a LinkedIn link → open it logged out → apply → the card
    shows "LinkedIn" and the panel row counts 1.
14. Mark JobStreet as posted; send the advert to a channel with a contact (mail queue).
15. Hiring set-up → Channels: turn VietnamWorks off for Indonesia; the panel on an
    Indonesian role hides it.
16. Agencies card → invite the demo agency → log in as the agency user → see the role →
    submit a person → the card appears on the board tagged Agency; try the same email
    again → the refusal sentence.
17. Hiring numbers agency section shows the demo agency's figures.
18. No console errors; no red style bar; no internal words on the portal pages.

## 6. Deploy and verify
Tier **risky** (migration of the agency field, new portal routes/ACLs). Backups ×3;
rehearse on a clone of payobook; payobook, rize, template; asset purge etc.; hash +
versions; one Chrome walk; cheap checks elsewhere. Demo (payobook): channels seeded,
one demo agency vendor with a portal login `demo.agency@example.com` / `RizeR7!2026`,
two submissions (one refused), registered. Commits per feature (pb_hiring and
pb_vendor_access separately); no push. Ledger rows; phase log.

## 7. Report back
P1 §7 format; tests 1–18; self-score; deviations; ledger rows + shapes for P8
(`pb.hiring.channel`, the connector registry, `pb.hiring.agency.submission`,
`coarse_stage`); owner items (Rize's board list and subscriptions/API access; JobStreet
/ VietnamWorks contact emails; whether agencies may see the salary band; the cooling
window); demo table incl. the agency login.
