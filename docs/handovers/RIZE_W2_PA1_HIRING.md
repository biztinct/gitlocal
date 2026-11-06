# RIZE Wave 2 — Phase A1: `pb_hiring` foundations

Owner approved the Wave 2 blueprint (`docs/design/rize-w2-blueprint.html`) on
2026-09-15, including D15 (survey install, not this phase), D16 and D17.
This phase builds the first third of Hiring & Recruitment: **the hiring request,
its budget check and sign-off, the job description, referrals, the posting pack,
the Hiring lens on the Lifecycle hub and the employee's "Refer someone" page.**
A2 (interview loop) and A3 (BGV → offer → closure → analytics) follow on top
of what you build here, so the API surface you leave behind matters.

Read first, in order: `docs/handovers/RIZE_LEDGER.md` (all — rules, ritual,
R1–R130, D1–D14), `docs/handovers/RIZE_W2_HANDOVER.md` Parts A, B and C1, then
this file. Everything marked **verified** below was checked on 2026-09-15
against the repo and the live `payobook` database — do not re-derive it.

---

## 0. Scope and binding non-goals

**In scope (A1):**
1. Module `pb_hiring` (new), version `19.0.1.0.0`.
2. `pb.hiring.requisition` — the hiring request, raised by function heads,
   with the budget check, the Approval Matrix route (manager → HR lead →
   Finance only if over budget) and the on-approval effects (job created or
   linked, recruiter + recruiter's manager notified by country rule, referral
   opened unless sensitive replacement).
3. `pb.hiring.jd` — versioned job description on the request, its own route
   (the hiring manager approves), the approved version copied onto the job.
4. `pb.hiring.referral` — `/my/refer` portal page → an applicant tagged
   Referral on the request's job; tracker on the board and on the page.
5. `pb.hiring.posting` — one row per job platform; "Publish" builds the
   ready-to-send pack (email per platform contact + the public careers page
   flag); the platform mail ships OFF (switch).
6. Screening tag on the applicant (Shortlisted / Rejected / Future fit / Fit
   for another role → move to that job) and the resume bank = the standard
   talent pool, readable by recruiters only.
7. `pb.hiring.country.rule` — per company + country: recruiter and recruiter's
   manager. Editable from a Settings card (or a board tab — see §4.8).
8. The **Hiring** lens on the Lifecycle hub (sequence 10), the `pb.hiring`
   facade + OWL board in the `pbim` kit, ⌘K rows in the **3500** block.
9. Mail templates (editable), one daily job (referral/JD reminders, idempotent),
   config switches, tests, deploy to `payobook`, Chrome validation light+dark.

**Binding non-goals (A2/A3 own these — do not start them):** interviews,
calendar events, ICS, reminders for interviews, panel feedback token pages,
next-round/reject mails, debrief, BGV, document request, offer, pay package,
offer letter, candidate review page, closure → onboarding, recruiter cover,
agency tag, the Insights lens. Do not touch `hr_recruitment`'s own views
beyond the additive applicant fields in §4.6. Do not build a second budget
table (D2). Do not add a rail item. Do not modify `vendor_license_core`.

---

## 1. Verified plumbing facts (do not re-derive)

### 1.1 The recruitment store on the server (Odoo 19, `hr_recruitment 19.0.1.1`)
- `hr.applicant` (`hr_recruitment/models/hr_applicant.py`): `partner_name`
  (:44, `_rec_name`), `email_from` (:45, computed/stored, writable),
  `partner_phone` (:55), `linkedin_profile` (:67), `job_id` (:93,
  company-domained), `stage_id` (:77), `company_id` (:85, computed stored
  writable), `user_id` = recruiter (:86), `department_id` (:98),
  `kanban_state` (:107), `refuse_reason_id` (:117), `source_id` (:124, a
  `utm.source`), `medium_id` (:123), `interviewer_ids` (:125),
  `application_status` (:128, computed: ongoing/hired/refused/archived),
  `talent_pool_ids` (:138), `attachment_ids` (:106), `date_closed` (:89, set
  when `stage_id.hired_stage`, :598-604). **No `hr.candidate` table on this
  build** — the applicant carries the person directly.
- `hr.recruitment.stage` (`hr_recruitment_stage.py`): `hired_stage` (:25),
  `fold`, `job_ids` (:15). Live stages (payobook): 1 New, 2 Qualification,
  3 First Interview, 4 Second Interview, 5 Contract Proposal, 6 Contract
  Signed (hired).
- `hr.job` (`hr_job.py`): inherits `mail.alias.mixin` + `mail.activity.mixin`;
  `user_id` recruiter (:36), `manager_id` (:54), `no_of_recruitment`,
  `department_id`, `company_id`, `address_id` (:38), `interviewer_ids` (:64),
  `job_source_ids` (:86). `website_hr_recruitment/models/hr_job.py` adds
  `website_published` (:38), `website_description` (:39), `job_details`
  (:44), `published_date` (:50), `full_url` (:51). Public page `/jobs`.
  Live: 52 jobs, 41 applicants; company-5 jobs 104–108 (Site Engineer …
  Project Manager).
- `hr.job.platform` (`hr_job_platform.py:8`): `name`, `email` (required).
  Live rows: 1 Linkedin `jobs-listings@linkedin.com`, 2 Jobsdb, 3 Indeed.
- `hr.talent.pool` (`hr_talent_pool.py:8`): `name`, `company_id`,
  `pool_manager`, `talent_ids` (groups `base.group_user`), `categ_ids`. Live:
  one pool "Developer" (company 1).
- `utm.source` live rows include **10 Referral**, 6 LinkedIn, 7 Monster,
  8 Glassdoor. Use id-by-name lookup (`Referral`), never a hard-coded id.
- `hr.applicant.refuse.reason` live: 1 Does not fit …, 2 Refused by
  applicant: job fit, 3 Job already fulfilled, 4 Duplicate, 5 Spam, 6 Refused
  by applicant: salary. 4 applicant categories exist.
- Groups: `hr_recruitment.group_hr_recruitment_user`,
  `hr_recruitment.group_hr_recruitment_manager`,
  `hr_recruitment.group_hr_recruitment_interviewer` (standard xmlids — verify
  with one `ref()` in a test before relying on them).
- **Not installed:** `survey`, `hr_recruitment_survey`, `hr_recruitment_skills`
  IS installed (ignore it).

### 1.2 Approval Matrix adapter canon
- Clone `pb_rnr/models/nomination_approval.py` end to end:
  `register_chain(model, PROCESS_KEY, submit_state=..., driven=(...),
  employee_field=..., amount_field=..., currency_field=...)` from
  `biz_approval_workflow.models.chain_shim` (:63 signature; `manager_step`
  :97 `(title, key='mgr', condition=None, kind='approve')`; `role_step` :104
  `(title, role, key=None, scope='company', condition=None, …)`; `route`
  :120 `(*steps, independent=True, due_days=2, reassign=False)`).
- The class sets `_approval_process_key`, `_chain_title`, `_chain_facts`,
  `_chain_fact_specs` (unit = a real unit, never a type, AM25),
  `_chain_revision_values` (never `write_date`, AM32), optional
  `_approval_detail(request)` (AM49), and `_approval_seed_default(company)`
  using `Seed.fill_role_from_group(company, role_key, group_xmlid)` then
  `Seed.lay(company, key, name, route(...), binding_note=, model_name=,
  role_keys=, reason=)` (`nomination_approval.py:88-101`). `seed_all(env)`
  loops companies with a per-company try/except (:103).
- Hooks you may override (all in `chain_shim.py`): `_approval_manager_uids`
  (:379) — WHO "their manager" is; `_approval_apply(request)` (:455) — the
  on-final-approval effect; `_approval_reject` (:484); `_approval_advance`
  (:431) maps intermediate states. Facts a route is chosen on are read under
  `sudo()` (AM40); "their manager" for a person without a login reads
  `employee_id.parent_id.user_id` directly (AM50).
- Roles that exist on every company (`biz_approval_role.key`): `approver`,
  `hr_lead`, `finance`, `finance_controller`, `budget`, `director`,
  `lifecycle`, `pay_head`, `payroll_mgr`, `equipment`, `access`, `reviewer`,
  `scheme_owner`, `signatory`, `platform_owner`.
- Module depends on `biz_approval_workflow` ONLY, never on
  `pb_approval_config` (AM52). New module ⇒ `post_init_hook` calls
  `seed_all(env)` for BOTH process keys; ALSO ship
  `migrations/19.0.1.0.0/post-hiring_approval.py` cloning
  `pb_offboarding/migrations/19.0.1.1.0/post-resign_approval.py` (guarded
  `if not version: return`) so a later `-u` can re-lay a missing route.
- Conditional steps: grep `condition=` under `pb_*/models/*_approval.py`
  for the live syntax before writing the Finance step; if no precedent
  exists, read `chain_shim.py` around `_chain_facts` / step evaluation and
  record what you found as an R-entry.

### 1.3 Budget canon (D2, R93–R95)
- `pb.budget.line` (`pb_budget/models/pb_budget_line.py:50`), inherits the
  `wfp.budget.actual` table: `company_id` (:61), `department_id` (:59),
  `period_month` (:56, a Date — first of month), `forecast_cost` = the
  BUDGET (:78), `actual_cost` = the SPEND (:79), `currency_id` follows the
  row. FY helpers on the facade `pb.budget` (`pb_budget.py`): `_fy_months(fy)`
  :113, `_current_fy(today)` :125, `_month_bounds(key)` :178 — private, so
  call them from Python only.
- Rule for the requisition: **remaining = Σ forecast_cost − Σ actual_cost for
  the request's department, company and current FY**, read under `sudo()`
  but with the explicit company clause (R89). No currency conversion (R23,
  R88) — show the number in the row currency; if the request's currency
  differs, status = `unknown`. No rows ⇒ `unknown` (never `over`).

### 1.4 Hub, palette, settings, home
- Lifecycle lens registry: `pb_lifecycle/static/src/js/lifecycle_hub.js`
  exports `LIFECYCLE_LENSES = "pb_lifecycle_lenses"` (:58) and
  `LIFECYCLE_GATE` (:50). Clone
  `pb_contract_lifecycle/static/src/js/contractlife_palette.js:39-45`:
  `registry.category(LIFECYCLE_LENSES).add("hiring", {key, icon, label,
  Component, groups}, {sequence: 10})`. Lens seqs taken: New joiners 20,
  Exits 30, Probation 40, Growth plans 50, Contracts 60. **Hiring = 10.**
  Label "Hiring" (6 chars, fits the 60px box, R63).
- Hub shell config and `embedded: true` cockpit rule: ledger "Platform
  contract". The hub xmlid is `pb_lifecycle.action_pb_lifecycle_hub`; every
  ⌘K door is an XMLID, never a bare tag (`contractlife_palette.js:54-86`).
- ⌘K contract: `pb_hub/static/src/js/hub_palette_entries.js:1-25`. Block
  **3500**: `hiring_board` 3500, `hiring_new` 3510 ("Raise a hiring
  request"), `hiring_jds` 3520 ("Job descriptions"), `hiring_referrals` 3530
  ("Referrals"), `hiring_rules` 3540 ("Hiring rules", admin gate).
- Settings categories: `pb_settings/static/src/js/settings_hub.js:277`
  `SETTINGS_CATEGORIES = "pb_settings_category"`; clone
  `pb_vendor_access/static/src/js/vendor_palette.js:60-78` (`{key, icon,
  label, blurb, groups, cards:[{id, tag, icon, label, sub}]}`, sequence 40
  — Vendors 20, Access 30 taken). Cards name a CLIENT ACTION `tag`; read
  `settings_hub.js` ~:565 (`registry.category("actions").contains(card.tag)`)
  before deciding whether an xmlid door is possible — see §4.8.
- Home lens registry (`HOME_LENSES`, `pb_home_hub/static/src/js/home_hub.js:101`)
  — NOT used in A1.
- Icons: the closed `ic()` set in `pb_import_kit/static/src/js/import_icons.js`
  has `search`, `userPlus`, `briefcase`, `fileText`, `send`, `users`, `flag`,
  `globe`, `checkCircle`, `alert`, `wallet`, `banknote`, `layoutList`. Use
  `userPlus` for the lens and `briefcase` for the request. Add a missing icon
  THERE (camelCase key), never a module-local map.

### 1.5 Portal
- Clone `pb_offboarding/controllers/portal.py` (route = the gate; employee
  re-resolved from the session, `_off_employee` :47; `sudo()` only after
  ownership is proven; `_prepare_home_portal_values` :63 for the counter;
  every refusal a redirect with a sentence). Home card: clone
  `pb_offboarding/views/portal_templates.xml:46` (`inherit_id=
  "portal.portal_my_home"`, `customize_show="True"`) — a card gated on a
  COUNTER is never drawn (R62): set an eager key in a `home()` override.
- Frontend bundle: `web.assets_frontend` only, every colour with a literal
  fallback (R39; `pb_offboarding/__manifest__.py:107-113`). The `.pbme`
  portal kit comes from `pb_me_portal`.
- Portal QWeb: `t-attf-class`, never dict `t-att-class` (R42); no `t-key`
  (R5); never a render key named `request` (R4).

### 1.6 Mail, reminders, tests, deploy
- Mail templates clone `pb_pay_delivery/data/mail_template.xml`; ALWAYS pass
  `email_values={'email_to': …}` (R6). Mail goes out within the second (R47)
  — assert on `mail.mail` rows and cancel test traffic in the same script
  (`state='cancel'`, R37). Test addresses `@example.com` only.
- Daily job clones `pb_employee_vault/models/employee_document.py
  _cron_expiry_check` (:227): search-before-create on open `mail.activity`,
  per-record try/except, honest counts, WARNING with `exc_info` (R92). No
  `numbercall`/`doall` on `ir.cron` (Odoo 19). Cap as a PARAMETER (R76).
- Test-run flags (R11): `--test-enable --test-tags /pb_hiring
  --http-port=8199 --logfile=/tmp/pb_hiring_test.log --stop-after-init`;
  `_read_group` and `_private` helpers are not RPC-callable (R40).
- Deploy ritual: ledger "Deploy ritual" verbatim; the real error lives in
  `/var/log/odoo/odoo-server.log` (R129); asset purge answers DELETE 0 on
  this box — check the served bundle with curl and reload with `ignoreCache`
  (R116); verify the lens in the browser via
  `odoo.loader.modules.get("@web/core/registry").registry.category("pb_lifecycle_lenses")`
  (R73/R110).

### 1.7 Live actors (payobook, company 5 "Payobook Vietnam JSC")
Logins were RENAMED as demo data (TIDY rule 15); the uids are stable:

| uid | login now | employee | role in A1 tests |
|---|---|---|---|
| 2065 | `igc1.validator` / `RizeP0!2026` | — | admin (16 groups incl. recruitment manager + user) |
| 2336 | `diep.thai@example.com` / `RizeP9!2026` | 17139, **manages department 657 "Quality Assurance"** | the FUNCTION HEAD who raises the request |
| 2326 | `lam.ngo@example.com` / `RizeP4!2026` | 17122 | "their manager" — set `hr.employee 17139.parent_id = 17122` for the test (17139 has no manager today; a demo-data write, D9) |
| 2333 | `tuan.quach@example.com` / `RizeP8!2026` | 17138 (manager 17122) | plain employee: refers a candidate on `/my/refer` |
| 2337 | `linh.quan@example.com` / `RizeP9!2026` | — | Finance approver (check the `finance` seat on company 5; seat them if empty and REVERT after) |
| new | `rize.w2.recruiter@example.com` / `RizeW2!2026` | create one (company 5, dept 657, manager 17122) | the recruiter named by the country rule |

Passwords drift (R74): re-set them as admin over `call_kw` before the first
portal login. Every group you grant is reverted against a snapshot (R123).
Test data stays, named "RIZE W2 …" (D9).

---

## 2. Architecture

```
pb_hiring/
  __manifest__.py            depends: base, hr, mail, portal, hr_recruitment,
                             website_hr_recruitment, utm, pb_hub, pb_import_kit,
                             pb_lifecycle, pb_me_portal, pb_budget,
                             biz_approval_workflow, pb_settings (JS import only
                             if you use the Settings card — otherwise omit)
  hooks.py                   post_init_hook → seed_all for both routes
  migrations/19.0.1.0.0/post-hiring_approval.py
  models/
    hiring_common.py         counted(), fold(), _as_employee(), FY helpers
    requisition.py           pb.hiring.requisition + pb.hiring.step
    requisition_approval.py  adapter, PROCESS 'hiring_request'
    jd.py                    pb.hiring.jd
    jd_approval.py           adapter, PROCESS 'hiring_jd'
    referral.py              pb.hiring.referral
    posting.py               pb.hiring.posting
    country_rule.py          pb.hiring.country.rule
    hr_applicant_ext.py      pb_screen, pb_other_job_id, action_pb_move_role
    pb_hiring.py             AbstractModel facade for the board
    hiring_automation.py     daily job
  security/  pb_hiring_security.xml (ladder + rules, THE PAIR), ir.model.access.csv
  data/      hiring_params.xml, ir_sequence.xml, mail_template_data.xml, cron.xml
  views/     hiring_views.xml (native forms, skinned by vu-form), portal_templates.xml
  controllers/portal.py      /my/refer, /my/refer/submit
  static/src/js  hiring_board.js, hiring_palette.js
  static/src/xml hiring_board.xml
  static/src/scss hiring.scss, portal_hiring.scss
  tests/     test_hiring.py (+ gates: white-label, act_window views, nolabel colspan)
```

Precedent to clone for the board trio: `pb_contract_lifecycle` (facade
`models/pb_contractlife.py` — `_safe` :53, `get_board` :87; board
`static/src/js/contractlife_board.js`, template `contractlife_board.xml`,
`contractlife.scss`). Security ladder: `pb_contract_lifecycle/security/
pb_contract_lifecycle_security.xml` (the commented "ship the pair" shape).

---

## 3. The rules of this module (plain English on screen)

- **Who can raise a request:** an internal user whose employee is the
  `manager_id` of any `hr.department` in the session companies, OR who holds
  `group_hiring_manager`/`group_hiring_admin`. Everyone else sees the lens
  (if lifecycle-gated) but the "Raise a hiring request" button is absent and
  the facade refuses with a sentence.
- **Group ladder** (`pb_hiring_security.xml`): `group_hiring_user`
  (recruiter; implies `hr_recruitment.group_hr_recruitment_user`),
  `group_hiring_manager` (implies user + `group_hr_recruitment_manager`),
  `group_hiring_admin` (implies manager). Privilege name WITHOUT `&` (R124).
- **Requisition visibility** (rules, the PAIR): plain users see requests they
  raised, are reporting manager on, or whose department they manage;
  `group_hiring_user`+ see every request in their companies. Company rule
  `['|',('company_id','=',False),('company_id','in',company_ids)]` on every
  model.
- **Budget status** computed on save and on demand (`action_refresh_budget`):
  `within` / `over` / `unknown` + `budget_remaining` + `budget_currency_id`.
  `over` ⇒ the Finance step applies and a chatter note + activity for the
  requester says by how much.
- **On final approval** (`_approval_apply`): (1) `job_id` created if empty
  (name = title, department, company, `user_id` = recruiter,
  `no_of_recruitment` = headcount, `manager_id` = reporting manager,
  `website_description` = approved JD if any, `website_published` False);
  (2) recruiter + recruiter's manager from the country rule (fallback: the
  company row with no country; fallback: nobody, logged) — mail each (two
  templates) + `mail.activity` on the request for the recruiter; (3)
  `referral_open = role_type != 'sensitive_replacement'` (switch
  `pb_hiring.referral_auto`, default 1); (4) state `open`, `opened_on`.
  All four legs in their own try/except — paperwork never fails an approval
  (R104).
- **JD**: `pb.hiring.jd` rows are versions (`version` int auto-increment per
  request); `state` draft → submitted → approved/refused; route = ONE step,
  "The hiring manager" = the request's `requested_by_id` (override
  `_approval_manager_uids` to return that uid; if the requester IS the
  submitter, fall back to `reporting_manager_id.user_id`, then the HR lead —
  and say so in `_chain_title`). Approving copies `body` to
  `requisition.jd_current_id` and to `job_id.website_description` if the
  job exists. The JD library = the JD list view filtered "approved", one
  place for every JD (the sheet's "centralized folder").
- **Referral**: `/my/refer` lists open requests with `referral_open` in the
  employee's companies; the form takes candidate name, email, phone, a note,
  an optional CV (≤ 5 MB, pdf/doc/docx). Submit creates `hr.applicant`
  (`partner_name`, `email_from`, `partner_phone`, `job_id`, `company_id`,
  `source_id` = utm.source "Referral" by name, `medium_id` unset,
  `description`/`applicant_notes` = note, attachment on the applicant) and
  a `pb.hiring.referral` row (employee, applicant, request, state computed
  from `applicant.application_status` + stage: received / in progress /
  hired / not this time). The referrer sees their own referrals and their
  states on the page; the recruiter is mailed once.
- **Posting**: on "Publish" (button on the request, `open` state only, JD
  approved required): set `job_id.website_published = True`, create one
  `pb.hiring.posting` per active `hr.job.platform` (skip existing), render
  the posting template (subject = title + location, body = JD + how to apply
  with `job_id.full_url`), store the rendered pack on the row; if
  `pb_hiring.platform_mail = 1` send to `platform.email` and mark `sent`,
  else mark `ready` with the sentence "Ready to send — platform emails are
  switched off". "Send now" per row for a human to push one.
- **Screening**: `hr.applicant.pb_screen` Selection (shortlisted / rejected /
  future_fit / other_role) + `pb_other_job_id`; `action_pb_move_role()` writes
  `job_id`, resets `stage_id` to the first stage of that job, posts a chatter
  line on both. `rejected` sets `refuse_reason_id` (default "Does not fit the
  job requirements") and archives via the standard refuse path; `future_fit`
  adds the applicant to the company's talent pool (create "Future fit —
  <company>" pool if none). Resume bank rule: `ir.rule` on `hr.talent.pool`
  + `hr.applicant` read for `group_hiring_user`+ only where the standard
  ACL is wider — CHECK the standard ACL first; if it is already recruiter-only,
  write nothing and record it.
- **Country rule**: `pb.hiring.country.rule` (`company_id`, `country_id`
  optional = fallback row, `recruiter_id`, `recruiter_manager_id`, `active`).
  Seed nothing; the board's empty state says "No hiring rule yet — add one
  in Settings → Hiring" and the requester still gets the request approved.
- **Daily job** (`pb_hiring.automation`, 06:00 company clock): (a) JD
  submitted > `jd_reminder_days` (3) without a decision → activity for the
  hiring manager, once; (b) open request with no recruiter → activity for
  the hiring admins, once; counts logged honestly ("2 job descriptions were
  nudged").
- **Switches** (`ir.config_parameter`, `data/hiring_params.xml`):
  `pb_hiring.platform_mail` = 0, `pb_hiring.referral_auto` = 1,
  `pb_hiring.jd_reminder_days` = 3, `pb_hiring.notify_mail` = 1 (recruiter /
  manager mails on approval), `pb_hiring.referral_mail` = 1.

---

## 4. Screens

### 4.1 The Hiring lens (board, `pbim pbim-page pbhr`)
- **Hero strip** (5 KPI tiles, `.lcj-kpis` grid clone R32): Open requests ·
  Waiting for sign-off · Candidates in play · Referrals this month · Over
  budget. Each tile is a filter.
- **Request rows**: title, function, location, headcount, budget chip
  (Within / Over by X / No budget set), stage chip (Draft / Waiting: <step
  title> / Open / Filled / Closed / Not approved), recruiter avatar
  (`avatar_128`, R82), candidates per stage as a mini bar, days open.
  Sorted problem-first (R113): waiting-on-me, then over budget, then open by
  age. Facets: function, country, stage, recruiter.
- **Drawer** (click a row): the request's facts; JD versions with "Open /
  Approve / New version"; postings with per-row state and "Send now";
  referrals; the candidate pipeline grouped by stage with the screening tag
  actions inline (Shortlist / Reject / Future fit / Move to… dropdown of open
  jobs); "Publish" and "Open the record" doors. Every `act_window` dict
  carries `'views'` (R125).
- **Empty state that teaches**: "No hiring requests yet. A function head
  raises the first one — it goes to their manager, then HR, then Finance
  only if it is over budget." with the button when allowed.
- Motion under `prefers-reduced-motion: no-preference` only (R85).

### 4.2 Native forms (vu-form skinned)
- Requisition form: header buttons Submit / Refresh budget / Publish / Open
  JD; statusbar; groups: About the role (title, role type, function,
  location, country, headcount, timeline), Budget (budget_cost + currency,
  status chip, remaining, refresh), People (requested by, reporting manager,
  recruiter, recruiter's manager), Interview steps (one2many editable),
  Requirements + Remarks (Text, `nolabel="1" colspan="2"` inside a group,
  R128). Chatter.
- JD form: request, version, body (Html — this is a real editor on a native
  form, so R61 does not bite), state, Submit/Approve doors through the
  Matrix inbox.
- Country rules list (editable) + form. Posting list. Referral list.
- Search views: `<group name="group_by">` bare (R129); no default group_by
  (R130).

### 4.3 `/my/refer` (portal, `.pbme` kit)
- Header "Refer someone"; a card per open request (title, function,
  location, "Refer for this role"); the form; below it "Your referrals" with
  state words. Home card "Refer someone · N open roles" (eager key).

### 4.8 Settings card vs board tab
Read `settings_hub.js` card contract (:565 region). If a card can only open
a client-action `tag`, register a 20-line client action `pb_hiring_rules`
whose `setup()` does `doAction("pb_hiring.action_pb_hiring_country_rule")`
and returns — precedent: none, so keep it minimal and document it — OR put a
"Rules" tab on the board (admin gate) and skip the Settings card. Either is
acceptable; the ⌘K row `hiring_rules` opens the rule list by xmlid in both
cases. Report which you chose.

---

## 5. Numbered test cases (record each result)

T1  Install `pb_hiring` on a clean test DB (`--test-enable`): both routes
    laid for every company (`biz.approval.seed`), zero WARN about missing
    xmlids; the gates pass (white-label grep of every user-visible string
    after stripping comments R118; act_window dicts carry `views`;
    `nolabel` in a group carries `colspan`).
T2  A plain user (no dept managed) cannot create a requisition (facade
    refuses with a sentence; ACL/rule refuses over RPC).
T3  As uid 2336 (manages dept 657): raise "RIZE W2 Site Agronomist", dept
    657, Vietnam, 2 heads, budget_cost 600,000,000 ₫ — budget status is
    computed from `pb.budget.line` for dept 657 FY-to-date; assert the
    number equals a psql sum of the same rows.
T4  Submit → request appears in the inbox of uid 2326 (their manager, after
    the parent write) with title, facts (budget cost with unit VND, over
    budget bool, headcount); approve → HR lead step; approve → state `open`
    (no Finance step because within budget). Assert `hr.job` created with
    the right fields; two `mail.mail` rows (recruiter, recruiter's manager)
    addressed explicitly; one activity on the request; `referral_open` True.
T5  A second request with budget_cost > remaining → `over`; the Finance step
    is present in the laid request (assert the step list of the open
    request); an activity names the overrun.
T6  Role type "sensitive replacement" → after approval `referral_open` False
    and `/my/refer` does not list it.
T7  JD: create v1 as the recruiter, submit → the request's hiring manager
    (uid 2336) is the approver; approve → `jd_current_id` set, job
    `website_description` updated; v2 created and approved → current moves
    to v2 and v1 stays readable in the library.
T8  Publish (JD approved): `website_published` True; 3 posting rows
    (Linkedin, Jobsdb, Indeed) in `ready` with the rendered pack; with
    `platform_mail=1` a "Send now" queues one `mail.mail` to
    `platform.email`; with 0 it refuses with the sentence. Cancel the mail.
T9  `/my/refer` as uid 2333: page lists the open request, not the sensitive
    one; submit a referral with a PDF → `hr.applicant` created on the job
    with `source_id` = Referral, attachment present, `pb.hiring.referral`
    row state "received"; the recruiter's mail row exists; the page shows
    the referral. A forged `job_id` for another company is refused.
T10 Screening: shortlist / future fit (talent pool row added) / reject
    (archived with reason) / move to another job (job + first stage,
    chatter on both) via the facade `act()`; the referral's state follows.
T11 Rule fallback: delete the country rule → approval still lands, no
    recruiter, a WARNING logged, the board chip says "No recruiter yet".
T12 Daily job: a JD submitted 4 days ago (server clock, R36) gets one
    activity; run twice → still one (idempotent); counts in the log.
T13 Board facade as uid 2336 (no hiring group): sees only own/department
    requests; as the recruiter: all company-5 requests; as a company-2
    user: none of them.
T14 ⌘K rows 3500–3540 present in `registry.category("pb_hub_palette")`;
    lens `hiring` at sequence 10 in `pb_lifecycle_lenses`; "Hiring" label
    ≤ 60px in the rail box.
T15 Chrome: board light + dark (screenshots), drawer, requisition form,
    JD form, `/my/refer` — no red style bar, no console error; the
    `unhandledrejection` listener attached before clicking every door.
T16 Group memberships and the `parent_id` you set: `parent_id` STAYS (demo
    data, D9, note it); every group grant reverted against the snapshot;
    passwords re-set to the ledger values; test mails cancelled.

---

## 6. Deploy and verify
Ritual verbatim from the ledger (fresh script name via `sudo tee`, R15).
`-i pb_hiring` on `payobook` only (D11). Check `ir_module_module.state` +
`latest_version` = `19.0.1.0.0`, the served bundle contains `.pbhr`, the
lens registry in the browser, `/my/refer` as uid 2333, the inbox shows the
"Hiring request" catalogue row for company 5 (`biz_approval_workflow_def`).

## 7. Report back
Commits (one per slice: model+adapter, JD, referral+portal, posting+screening,
board+lens+palette, job+tests); per-test results; deploy verdict from
`journalctl` + DB; deviations and why; palette rows used; registry names;
**API for A2/A3**: `pb.hiring.requisition` fields + states, `pb.hiring.step`
shape (A2 turns steps into interview rounds), `pb.hiring.jd` current pointer,
the facade's `act()` verbs, the referral state mapping, the country-rule
lookup helper signature; test accounts created; switches with defaults; new
R-entries (from R131) appended to the ledger; the ledger's "Phase plan &
status" gains a **Wave 2** table with the A1 row; anything the owner must
decide.
