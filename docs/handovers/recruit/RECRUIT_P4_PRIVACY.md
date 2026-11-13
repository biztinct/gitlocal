# RECRUIT — Phase 4: private until shared — sharing, money locks, recruiter notes, the Resume bank, retention

Delivers register lines **G-08, G-26, G-36, G-41 (masking half), G-45 (retention half)**:
a candidate is recruiter-only until the recruiter shares parts of the record with the
role's hiring manager or named panel members; money (expected pay, offer figures, role
budget) is hidden from everyone who is not entitled; private recruiter notes visible to
the author and the Talent lead only, shareable per note with a named hiring manager; a
Resume bank tab (search by skill, role, country, tag) hidden from hiring managers; and
consent-based retention with an anonymise job and a preview, per country.

Read first, in order: `docs/handovers/recruit/RECRUIT_LEDGER.md` (all rows incl. P1–P3),
the **P1, P2, P3 phase reports** (shapes: `get_candidate`, `_card`, `get_timeline`,
`get_requisition`, `pb_form_answers`, `pb_consent_*`, `pb_country_id`, `request_state`),
the blueprint sections "Seven promises" (07), "The candidate drawer" (locks, Share
with…), "Who sees what", the register lines, then this file. Facts verified 2026-09-30;
re-locate moved lines by name.

---

## 0. Scope and binding non-goals

**In scope (P4):** `pb_hiring` **19.0.2.3.0** with a migration.
1. **Share model** `pb.hiring.share` and the "Share with…" control (drawer + bulk from
   the selection bar); per-role default sharing set by the Talent lead; shares shown as
   chips on the card ("Shared with Minh") and as the lock lines in the drawer.
2. **Visibility enforcement in every payload** (`_parts_for(applicant, user)`): board
   cards for non-hiring users show name + stage + interview dates only until shared;
   drawer sections appear only for shared parts; CV/portfolio links for a non-hiring user
   use per-file access tokens; timeline entries filtered (no internal notes, no
   recruiter notes, no money events) for non-hiring users; scorecard section per share.
3. **Money locks**: expected pay, offer figures and role budget hidden from everyone
   except Recruiter / Talent lead / Head of hiring, the offer's sign-off seat holders
   (in the inbox), and a hiring manager the recruiter shared `expected_pay` with. Field
   `groups` on the native offer/requisition money fields; payload masks everywhere.
4. **Private recruiter notes** `pb.hiring.note` (author + Talent lead/Head only; share
   per note with named users) — the drawer's "Recruiter notes" section with the lock and
   "Share with <manager>".
5. **Resume bank** tab on the Hiring home (hiring groups only): search over future-fit
   candidates, pool members and (toggle) everyone who ever applied; facets skill / role
   family / country / tag / source; "Add to a role" (copy into the role's Applications
   received); "Keep in touch" tag editing; expiry column from retention.
6. **Retention**: `retention_months` + `purge_mode` per company+country on
   `pb.hiring.country.rule` (default 12, anonymise), a daily anonymise leg with a
   preview ("What will go") in Hiring set-up → "Consent & retention" card, a per-candidate
   "expires on" line, and a manual "Run now". Consent snapshot from P2 is the clock.
7. Tests, deploy (three DBs, never abm), Chrome validation, report.

**Binding non-goals:** scorecard templates and hidden-until-all-in changes (P5 — but keep
the existing hidden-between-panellists behaviour intact); re-consent emails ("still
interested?") (P8); agency visibility (P7); changing `biz_approval_workflow`; a merge of
duplicate candidates; the stock applicant form's own field layout beyond `groups`.

---

## 1. Verified plumbing facts (do not re-derive)

### 1.1 Who can read an applicant today
- Stock rules `hr_recruitment/security/hr_recruitment_security.xml`: company rule
  :10-15; interviewer rule :49-60 (`job_id.interviewer_ids` / `interviewer_ids`, no
  create/unlink); user rule :62-67 `(1,=,1)`. Groups: interviewer :17 (implies
  `base.group_user`), officer :25, admin :32; `base.group_user` implies only
  `group_applicant_cv_display` :44-46. ACL `hr_recruitment/security/ir.model.access.csv`:
  interviewer r/w :5, officer full :6, **no row for `base.group_user`**; talent pool :7-8;
  category :19. **pb_hiring adds no rule on `hr.applicant`.**
- pb ladder `pb_hiring/security/pb_hiring_security.xml`: Recruiter :40-46, Talent lead
  :48-57, Head :59-68. Interview rules :156-168 (own = panel user / recruiter / requester
  / reporting manager; all = Recruiter), feedback :188-200 (own = panel user or the
  interview's recruiter; the comment :184-187 says the hiring manager is EXCLUDED on
  purpose), stage log :202-214 (requester or recruiter), offer :347-359 (+ seat read
  :427-436), requisition :228-240 (+ seat :405-414). ACLs `pb_hiring/security/ir.model.access.csv`
  (interview :31-35, feedback :41-45, stage log :51-55, offer :82-91, requisition :2 —
  staff read/write/create).
- **Line managers hold no recruitment group** → no ORM read on `hr.applicant`; everything
  they see comes from sudo payloads gated by `_role_readable` (`board_p1.py:220-229`,
  `check_access('read')` on the requisition) and `_applicant` (`board_p1.py:231-251`,
  sudo, allows hiring group / `_can_recruit(req)` / `_role_readable(req)`). `_candidates`
  override `board_p1.py:436-464` (sudo, no per-user filter, cap `BOARD_CANDIDATES=600`
  :51); `get_requisition` override :428-434; A3 :200-235. Line-manager move switch
  `_line_managers_move` / `_can_move` :195-210.
- `get_candidate` `board_p1.py:669-737`: `money` only when `can_recruit` (:697-702);
  `scorecards` incl. each panellist's `notes[:280]`, score, verdict for ANY role reader
  (:681-696); `documents` with `/web/content/<id>` only when `can_recruit` (:730-733),
  `doc_count` always (:734); `timeline` from `get_timeline` :825-877 (sudo `mail.message`
  `model='hr.applicant'`, types comment/email :847-858, first line + author for anyone
  passing `_applicant`, no subtype/`is_internal` filter). `_card` :466-568 carries
  `'shared': ''` placeholder :563 and `has_cv` :562. Board notes `_act_candidate_note`
  :340-350 (anyone who can read the role; `mail.mt_note` on a sudo applicant); stage
  reasons posted the same way :300-305.
- **Budget not masked**: `budget_cost`, `budget_over_by` in every board row
  (`pb_hiring.py:272-273`). **Offer money not masked**: `_offer_row(full=True)`
  (`pb_hiring_a3.py:225-228`, :389-440) readable by the hiring manager via `rule_offer_own`.

### 1.2 Field groups and how Odoo enforces them
- Only four applicant fields carry groups, all `hr_recruitment.group_hr_recruitment_user`:
  `salary_proposed_extra` :95, `salary_expected_extra` :96, `salary_proposed` :97,
  `salary_expected` :98 (`hr_recruitment/models/hr_applicant.py`). No groups on
  `applicant_notes` :137, `categ_ids` :85, `talent_pool_ids` :139, or any pb field
  (`journey.py:~294-306`). No `groups=` anywhere in pb_hiring models (offer
  `monthly_total` :140, `annual_total` :143, line `amount` :860 / `annual_amount` :868;
  requisition `budget_cost` :162 … `budget_note` :180).
- Enforcement (core `odoo/orm/models.py`): `_has_field_access` :3375-3388,
  `_check_field_access` :3390-3439 (read :3846/:3860, search/order :2934, write :3559/
  :4387/:4661); `fields_get` skips :3364; `Field.__get__` checks unless `env.su`
  (`odoo/orm/fields.py:1649-1652`) — **sudo reads bypass**, so payload masking must be
  explicit. Views drop nodes for fields the user cannot see (`ir_ui_view.py:1650-1661`,
  :1318-1360).

### 1.3 Attachments
- CV stored `controllers/application.py:124-125` (`public: False`); referral CV
  `referral.py:171-180`; `.ics` `interview.py:520-528`. No `access_token` use in pb_hiring.
- Core checks (`odoo/addons/base/models/ir_attachment.py`): `_check_access` :514-588
  (public readable; res_model/res_id needs read on the parent via
  `_inaccessible_comodel_records` :590-618); `_search` security domain :637-676;
  `/web/content` → `ir.binary._find_record` (`ir_binary.py:23-54`): access token :50,
  else `check_access('read')` :54. **A line manager cannot open a CV URL without the
  parent read** → use `attachment.generate_access_token()` and
  `/web/content/<id>?access_token=<t>` for shared files (tokens are per attachment,
  revocable by regenerating).

### 1.4 Notes, identity, pools, skills, country, retention
- `applicant_notes` Html :137 no groups; written only by referrals (`referral.py:162-164`);
  not in any pb payload. No private/shared note precedent in pb/biz; closest:
  `payroll_ai_dashboard.is_shared` rule (`pb_payroll_ai_insights/security/payroll_ai_security.xml:57-62`),
  HR-only field groups (`pb_offboarding/models/resignation.py:101-107`), HR-only paired
  rules in `pb_pip/security/pb_pip_security.xml:128-180`.
- Identity on a role: `requested_by_id` (employee) `requisition.py:138`,
  `requested_by_user_id` stored compute :141-143/:257-262, `reporting_manager_id`
  (employee) :144, `recruiter_id` (user) :146; `pb.hiring.step.owner_id` is **res.users**
  :62-63; interview `panel_employee_ids` (employees) `interview.py:113-115`; feedback
  `panel_employee_id` :90 / `panel_user_id` :93-95. Employee→user: `hr.employee.user_id`
  (`hr/models/hr_employee.py:85`) and `pb_portal_user_id` (`pb_zoho_bridge/models/hr_employee.py:44-48`)
  — resolve BOTH when matching a share to the current user. `_panel_people`
  `pb_hiring.py:562-582` (`[{id,name,role,fold}]`, no user id).
- Talent pool `hr_recruitment/models/hr_talent_pool.py` (`active` :15, `name` :16,
  `company_id` :17, `pool_manager` :23, `talent_ids` groups base.group_user :32,
  `categ_ids` :40); rule officer `(1,=,1)` :76-81, no company rule. Applicant
  `talent_pool_ids` :139, `pool_applicant_id` :140, `is_pool_applicant` :141, pool logic
  :149-420. Keep-in-touch add `hr_applicant_ext.py:141-153` — **lookup by name only
  without company filter** (:147) — fix. Skills: `hr_recruitment_skills/models/hr_applicant.py`
  `applicant_skill_ids` :11, `skill_ids` :20, matching :21-31; rules
  `hr_recruitment_skills/security/…:5-20`. **pb_hiring does not depend on
  `hr_recruitment_skills`** — it is installed on payobook (wave-2 note); verify on rize
  and template before depending; if absent there, install it (standard addon, allowed).
- Country: applicant has `pb_location` / `pb_nationality` Char only (`journey.py:~296-297`);
  **P2 adds `pb_country_id`** — use it, fall back to `requisition.country_id or
  company.country_id` (pattern `offer.py:351`, `requisition.py:761`). `pb.hiring.country.rule`
  `country_rule.py:28-49` (company, country, recruiter, recruiter_manager, active, note).
- Retention: nothing in hr_recruitment or pb_hiring. Precedents: `biz_audit_trail/models/biz_audit_entry.py:88-120`
  (`_retention_days` param, `_gc_vacuum`, cron in a savepoint; cron xml :6-14),
  `pb_learn/models/learn_question.py:201-215`. Applicant `active` :42,
  `application_status` :129-134 / :509-519; pb reject sets `active=False` + `refuse_date`
  (`hr_applicant_ext.py:133`); leaving a closed stage reactivates (`board_p1.py:295-298`).
  Referral consent `pb_consent` `journey.py:~465`. P2 adds `pb_consent_on`,
  `pb_consent_text`, `pb_lang`.
- Panel token page exposes exactly candidate/role/round/when/due/company/late/
  recommendations (`panel_feedback.py:208-226`), no CV link (template
  `views/token_templates.xml:63-102`).
- Access screen: `ROLE_ABILITY_GROUPS` `pb_vendor_access/hooks.py:402+` (hiring :434-436),
  `NEW_ABILITIES` :492+, `ensure_abilities` :871-918; grant API `pb.access.grant(profile_id,
  user_id, reason)` `biz_access/models/pb_access_facade.py:248-291`.
- Tests: `with_user` precedents `test_interviews.py:770-805` (`TestWhoMayReadAnOpinion`),
  `test_hiring.py:144-180` (`_plain_user()` :146-152); fixtures `InterviewCase.setUp`
  :38-80+ (recruiter, panel user + employee, panel member without login). No test covers
  `get_candidate`, money masking or document visibility.

---

## 2. Architecture

### 2.1 Data
- `pb.hiring.share`: `applicant_id`, `user_id` (res.users; resolve from employee via
  `user_id` or `pb_portal_user_id` when sharing with an employee), `employee_id`
  (optional, for display), `parts` (Char CSV of: `profile`, `cv`, `portfolio`,
  `assignment`, `attachments`, `scorecards`, `expected_pay`, `answers`), `granted_by_id`,
  `granted_on`, `note`; unique (applicant, user); `active`. Method
  `parts_for(applicant, user)` → set; hiring groups → ALL; else union of shares;
  additionally the role's `requested_by_user_id` / `reporting_manager` user always get
  `{'card'}` (name, stage, interview dates) for their roles — never more without a share.
- Role defaults: `pb.hiring.requisition.default_share_parts` (Char CSV, default
  `profile,cv`) and `default_share_with` Selection (`nobody` / `hiring_manager` /
  `hiring_manager_and_panel`, default `hiring_manager`) — applied when an applicant
  is created on the role (public form, referral, manual add, bank copy) and editable in
  the role Details tab ("What the hiring manager sees by default").
- `pb.hiring.note`: `applicant_id`, `author_id` (res.users), `body` (Html), `shared_user_ids`
  (m2m), `created_on`; rules: read/write for author; read for `group_hiring_manager`
  (Talent lead) and admin; read for `shared_user_ids`; Recruiter tier sees only own +
  shared-with-me. Never in `mail.message`.
- Money groups: `groups="pb_hiring.group_hiring_user"` on offer `monthly_total`,
  `annual_total`, line `amount`, `annual_amount`, `currency_id`? (currency can stay), and
  on requisition `budget_cost`, `budget_confirmed`, `budget_remaining`, `budget_over_by`,
  `budget_note`, `budget_status`. Sign-off seat holders (HR lead / Finance / the named
  approver) read figures via the Approval inbox card (`_approval_detail(request)` runs
  sudo — verify it still renders amounts for a seat holder without the hiring group; if
  the inbox card reads the record directly, provide the figures in `_approval_detail`).
- Retention on `pb.hiring.country.rule`: `retention_months` (Integer, default 12),
  `purge_mode` (`anonymise` default / `delete`), `retention_note`; company fallback when
  no rule for a country: `res.company.pb_retention_months` (P2 added it; keep as the
  fallback). Applicant: `pb_retention_until` (computed stored: consent_on or create_date
  + months, recomputed when the rule changes), `pb_anonymised_on`, `pb_retention_extended_by/on`
  (a recruiter may extend once by the same number of months, recorded — owner item on
  whether re-consent is required).
- `_pb_keep_in_touch` pool lookup fixed to filter by company.

### 2.2 Server API (on `pb.hiring`)
- `get_candidate` / `_card` / `get_timeline` / `get_requisition` honour `parts_for`:
  non-hiring readers get `card` fields only unless shared; `documents` come with
  tokenised URLs for shared `cv`/`portfolio`/`attachments`; `money` only with
  `expected_pay`; `scorecards` only with `scorecards` (and the hidden-until-all-in rule
  still applies to panellists); `answers` (P2) only with `answers`; timeline for
  non-hiring readers: stage moves, interviews, shares made to them; never notes, emails'
  bodies, money events.
- `_act_share({applicant_ids, targets:[{user_id|employee_id}], parts, note})`,
  `_act_unshare({share_ids})`, `get_share_options(requisition_id)` → hiring manager,
  reporting manager, panel members of the role's rounds, plus a people search
  (`_panel_people` reuse); `_act_role_share_defaults({requisition_id, parts, with})`.
- Notes: `get_notes(applicant_id)`, `_act_note_add`, `_act_note_edit`, `_act_note_share`,
  `_act_note_delete` (author or Talent lead).
- Resume bank: `search_bank({q, skill_ids, country_ids, role_family, tag_ids, source_ids,
  include_all, page})` → `{rows:[{id, name, last_role, country, skills[], tags[],
  screen, source, applied_on, expires_on, in_pools[]}], facets:{…}, total}`; hiring
  groups only (`_require_recruit`); `_act_bank_add_to_role({applicant_ids,
  requisition_id})` (copy to the role's `screening`, link `pb_origin_applicant_id`),
  `_act_bank_tag({applicant_ids, tag_ids, add|remove})`, `_act_bank_skills` (uses
  `hr_recruitment_skills` if installed, else `categ_ids` only — say which in the UI).
- Retention: `get_retention_preview()` → per country: rule, count expiring within 30
  days, count due now, sample names (hiring groups only); `_act_retention_run()` (Head of
  hiring only; runs the same leg as the cron), `_act_retention_extend({applicant_id})`.
  Daily leg in `cron_hiring_daily`: applicants with `pb_retention_until < today`, not
  hired/employee-linked, not in an open stage → anonymise (name "Candidate (removed)",
  blank email/phone/linkedin/portfolio/location/answers/`applicant_notes`; unlink
  attachments; delete `pb.hiring.note` rows; delete `pb.hiring.share` rows; keep stage
  log + counts for analytics; `pb_anonymised_on`), or delete when `purge_mode=delete`
  (then also drop the stage log? NO — keep analytics rows by deleting the applicant only
  if the log model tolerates a null applicant; otherwise anonymise regardless and say so).
  Each candidate in its own savepoint (`leg`).

### 2.3 UI
- Card: "Shared with Minh" chip (or "Not shared" grey for hiring readers) — from `_card`.
- Drawer: hero locks ("Private to hiring"), "Shared with … · Change" line → a sheet:
  people (checkboxes with role labels: Hiring manager, Reporting manager, Panel · Round 2,
  Search…), parts (checkboxes with one-line meanings), note; "Recruiter notes" section
  with the lock sentence, add/edit, per-note "Share with <manager>" chips; "Expires on
  12 Oct 2027 · Keep 12 more months" line at the bottom (hiring readers only).
- Selection bar: "Share with…" for the ticked cards.
- Role Details: "What the hiring manager sees by default" (parts + with).
- Hiring home: **Resume bank** tab (hiring groups only) — search box, facet chips, result
  rows (name, last role, country, skills, tags, source, applied, expires), row hover
  actions "Add to a role" / "Open", multi-select + bar; empty state teaches ("Nobody has
  been tagged Future-fit yet — the first look tag puts people here").
- Hiring set-up: "Consent & retention" card live: per-country table (months, mode),
  the preview ("What will go" with counts and the next run), "Run now" (Head of hiring),
  the consent wording per market (link to P2 forms).
- The line manager experience (verify with the demo hiring-manager login): board shows
  cards with name/stage/interview only; a shared candidate opens with exactly the shared
  parts; the CV opens from the tokenised link; no money anywhere; no notes.

---

## 3. Design (build to the blueprint)

Design bar verbatim (ledger): **"exceptional premium, extreme WOW, a novice can work
without training"**. Hero moment for P4: the Share sheet — tick "Minh · Hiring manager"
and "CV", and the card's chip and the drawer's lock lines change in place; Minh's own
board (open the demo hiring-manager login) now shows the CV button. Locks are visible,
never silent: every hidden thing is a labelled lock, not a blank. Zero dead-ends: a
line manager who opens an unshared candidate sees "The recruiter has not shared this
person's details with you yet" and nothing else. Plain words: "Shared with", "Private to
hiring", "Only you and the talent lead", "Expires on". Every new string translated
(vi_VN + id_ID). Light and dark checked.

---

## 4. Rules (plain English on screen)
- A candidate is private to the hiring team until a recruiter shares parts of the record.
  Sharing is per person and per part; the chip names the person.
- Money is never shared by accident: "Expected pay" is a separate part, off by default.
- Recruiter notes are yours and the talent lead's. Sharing a note is per note.
- A hiring manager sees the board for their roles (names, stages, interview dates) so
  they know where things stand; details need a share.
- Retention counts from the consent the candidate gave; hired people are never
  anonymised by this job; a recruiter may extend once and it is recorded.

---

## 5. Numbered test cases
1. `parts_for`: hiring groups → all; requester → card only; after a share → the parts;
   employee shares resolve through `user_id` and `pb_portal_user_id`.
2. `get_candidate` as the demo hiring manager: unshared → card fields + the sentence;
   shared cv → tokenised document URL that returns 200 for that user and 403 for a
   stranger; regenerate token on unshare → old URL 403.
3. `money` absent without `expected_pay`; present with it; offer figures absent from
   `get_requisition` for a non-hiring reader; budget fields absent from board rows for a
   non-hiring reader; the approval inbox card still shows offer amounts to a seat holder
   without the hiring group.
4. Timeline for a non-hiring reader has no notes/emails/money events; for a recruiter it
   has them.
5. Notes: author read/write; other Recruiter cannot read; Talent lead reads; shared user
   reads; delete by author or Talent lead only; never in `mail.message`.
6. Role defaults apply on public apply, referral, manual add and bank copy; changing the
   defaults does not change existing shares.
7. Bulk share from the selection bar creates/updates N shares idempotently.
8. Resume bank: `search_bank` respects `_require_recruit`; facets count correctly; `q`
   matches name/email/skills; `include_all` widens; add-to-role copies into the target's
   `screening` with `pb_origin_applicant_id`; keep-in-touch pool lookup is per company.
9. Retention: `pb_retention_until` = consent_on + months (country rule, else company
   fallback); preview counts; the leg anonymises exactly the due, non-hired, closed
   candidates, one savepoint each, and never touches an open-stage or hired candidate;
   extend once records who/when and moves the date; `delete` mode either deletes or
   falls back to anonymise as documented.
10. Field `groups` on money fields do not break the native offer form for a recruiter,
    and hide the fields for a plain user.
11. Existing tests pass.
Browser (payobook.com, recruiter + talent lead + demo hiring manager logins, light + dark):
12. Share sheet from the drawer; chip and locks update; the hiring manager login sees
    exactly the shared parts and opens the CV.
13. Unshare → the manager's view loses the part; the old CV link fails.
14. Recruiter notes: add, share with the manager, the manager sees only that note.
15. Resume bank: search, facet, add to a role, tag; hidden for the hiring-manager login.
16. Consent & retention card: preview, run now (on a demo candidate with a past date),
    the candidate reads "Candidate (removed)" and the counts still show on Hiring numbers.
17. No console errors; no red style bar.

## 6. Deploy and verify
Tier **risky** (security rules, field groups, anonymise job). Backups ×3; rehearse on a
clone of payobook; ship the retention cron leg DISABLED by parameter
`pb_hiring.retention_enabled=0` on all three DBs and say so (owner switches it on after
reviewing the preview); the rest live. Asset purge etc.; hash + versions; one Chrome
walk; cheap checks elsewhere. Demo: three shares, two notes, five future-fit candidates
with skills, one past-date candidate for the preview — registered. Commits per feature;
no push. Ledger rows; phase log.

## 7. Report back
P1 §7 format; tests 1–17; self-score; deviations; ledger rows + shapes for P5–P8
(`parts_for`, `pb.hiring.share`, `search_bank`, retention params); owner items
(retention months per market and whether "extend" needs the candidate's re-consent; who
may run the purge; whether hiring managers should see scorecards by default); demo table.
