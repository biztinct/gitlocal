# WDGAP Step 6: plumbing facts for "More for employees to do themselves"

Verified by a read-only code survey on 2026-11-15 at `origin/19.1` @ `7f0fa3aad` (W2 deploy report,
live on all five databases). Paths are relative to the repo root. Do not re-derive these; spot-check a
line before relying on it. No code, database or live server was touched.

The study rows behind this step are in `outputs/workday-gap-study-2026-11-14/research-data/01-worker-data.json`,
`02-hiring.json`, `05-talent-skills.json`, `12-ai-security-integrations.json` and `13-adjacent-products.json`
(`outputs/` is never committed). The **must** rows are:
- change my personal details, with approval
- change my bank details safely
- employment and salary certificates on request
- employee consent for personal data
- claim against a yearly benefit allowance
- cash advances and paying them back
- paying the employee back

The **should** rows are:
- family members and dependants
- employee photos
- see all my details in one place
- staff apply for internal roles
- assistant for employees on self-service
- answers from company policy documents
- running totals and yearly caps per category

The employee area is **My Payobook** (`/my`, module `pb_me_portal` 19.0.3.7.0).

Binding for every builder: ledger `WDGAP_LEDGER.md` conventions 1–10. In particular:
- The word "Odoo" never appears in anything a user can see or receive.
- "Payobook" never appears in generic `biz_*` modules (QFM-1).
- Every new string gets `vi` and `id` entries.
- Lucide icons only.
- The design mandate is "extreme WOW, best in class".
- Tenant email is off on purpose on `rize`, `sudima` and `p0clone`.

## 0. Corrections and surprises (read first)

1. **Two bank stores, and the bank file reads only one of them (a live-data finding outside this step).**
   - The pay bank file and the payslip delivery read the four Vietnam fields `vietnam_bank_*` on `hr.employee`:
     - `pb_pay_delivery/models/bank_export_wizard.py:113`
     - `pb_pay_delivery/models/payslip_delivery.py:111`
     - The fields are defined at `pb_hr_payroll_vietnam/models/hr_employee_vietnam.py:47-50`.
   - The bank document check (`pb_bank_ocr`) writes those same fields (`pb_bank_ocr/models/pb_bank_change_request.py:289-319`).
   - The **Updates / Records bank lane writes `res.partner.bank`** through `bank_account_ids` (`pb_records/models/pb_records_desk.py:1759-1803`, `:1773`).
   - No code copies one store to the other. A grep for writes of `vietnam_bank_account_number` finds only:
     - `pb_bank_ocr` (`:298`)
     - the demo generator
     - the old VN import wizard (`pb_hr_payroll_vietnam/wizards/vietnam_employee_import_wizard.py:141`)
   - So a bank change approved through Updates may never reach the bank file. **Check live data before building**; the self-service bank change must write the store the bank file reads.
2. **The letter engine lives in `pb_lifecycle` (19.0.1.20.0), which is the Performance team's area.**
   - Certificates must be built in a NEW glue module that inherits it, never by editing `pb_lifecycle` files (§3).
3. **`pb_bank_ocr` has dead code.**
   - In `write()` (`pb_bank_ocr/models/pb_bank_change_request.py:215`), the lines after `return super().write(vals)` (`:216-232`) never run.
   - They are the body of an `_approval_can(from_state, to_state)` override whose `def` line was lost.
   - Without a published route, the base rule `biz_approval_chain/models/biz_approval_mixin.py:42-55` applies. Submit is then open to anyone, and the finance step admits only `group_hr_payroll_manager` (`:143`).
4. **An internal hire through today's Hiring pipeline would go wrong in two ways:**
   - **A second employee record.** `pb.hiring.offer._ensure_employee` (`pb_hiring/models/offer_closure.py:160-224`) reuses an employee only if `offer.employee_id` is set or the applicant is already in `applicant_ids` (`:176-183`). No hiring path sets either for a current employee.
   - **The old contract is silently reused.** `_ensure_contract` (`:287-294`) reuses ANY existing contract, so the offer's new pay would never apply. The onboarding case and login steps (`action_confirm_joined` `:70-135`) would also run.
5. **PayAI's group is implied for every internal user in code, but not on payobook.**
   - `base.group_user` implies `group_payai_user` in code (`pb_payroll_ai_insights/security/payroll_ai_security.xml:103-106`).
   - On payobook that implication was removed on purpose (owner ruling 2026-10-20, memory `payai-does-it-program`). There, only people given the "AI assistant" role have PayAI.
   - Portal (Employee-tier) logins never have it.
6. **A yearly-allowance precedent already exists: the training allowance.**
   - `pb.training.allowance` (`pb_training/models/allowance.py:33-56`) holds a company figure per year plus an optional per-person figure. Lookup is `allowance_for` / `amount_for` (`:130-175`).
   - The "allowance, agreed, left" arithmetic and a refusal sentence are in `pb_training/models/claim.py:257-330`. The over-allowance switch is `pb_training.claim_over_allowance` (`:20-29`).
   - Training claims are paid through `pb.incentive` → `pb.oneoff.feed` (`pb_training/models/incentive_ext.py:11-49`). That feed is blocked in application-data mode (ledger PRB-W2).
7. **Step 2 overlap: dependants feeding tax.**
   - The study's Step 2 item "Employees enter their own tax details (dependants, tax number) on My Payobook" is postponed (ledger D3, `WDGAP_DEFERRED.md` row 2).
   - Vietnam tax dependants drive the tax allowance (`pb_hr_payroll_vietnam/models/hr_employee_vietnam.py:214-284`). Family members that change pay are therefore an owner question (§10 Q1).

## 1. Shared My Payobook plumbing (every phase uses this; none of it needs editing)

### 1.1 Who is an employee-tier login

| Check | Where | What it does |
|---|---|---|
| `res.users._pb_employee_only()` | `pb_me_portal/models/ess_landing.py:66-102` | True for a share (portal) user with an employee (`:90-91`) |
| `_pb_portal_only()` | `:105-142` | Share users are always portal-only (`:132`). Internal users are portal-only unless they hold a role, a hand-given backend group, direct reports or an open approval seat (`:144-186`). It fails open. |
| Backend fence | `pb_me_portal/controllers/ess_landing.py:26-75` | Sends portal-only users to `/my` |

Employee logins are mostly **portal (share) users** (TIERS T4). Almost every grant and record rule in the custom modules is for `base.group_user` only: `pb_me_portal/security/ir.model.access.csv`, `pb_bank_ocr/security/ir.model.access.csv:2`, `pb_me_expense/security/ir.model.access.csv:2`. So every portal path works as **"check ownership, then sudo"**:
- The rule is stated at `pb_me_portal/controllers/portal.py:12-20`.
- `_ess_employee()` (`:55-64`) finds the session user's employee, preferring the current company.
- `_ess_own_employees()` (`:66-77`) returns all of their employee records (one person can have several across companies).
- **No route may accept an employee id from the request.**
- Precedents:
  - `pb_me_expense/controllers/portal.py:138-343` (upload, send, withdraw)
  - `pb_ask_hr/controllers/portal.py:44-57` (`_ask_hr_own`)
  - `pb_loans` `/my/loans`

### 1.2 Extension seams on the home (all inherit-only; MEHOME rule M-R2: modules never edit pb_me_portal)

**Tiles.**
- The module-level registry is `_TILE_ROWS` / `_TILE_WORDS` / `TILES` (`pb_me_portal/models/pb_me_home.py:94-205`). An unknown URL lands in "More" (`TILE_DEFAULT` `:208-209`).
- **To place a new tile without editing pb_me_portal**, follow `pb_training/models/me_home_tile.py:21-36`: `pb_me_home.TILES.setdefault(url, {group, icon, tone, seq})` at import.
  - Keep the short `text` out of the registry: pb_me_portal's home test wants every short text in its own `.po`.
- The tile itself is a `portal.portal_docs_entry` call in the module's own template (e.g. `pb_me_expense/views/portal_templates.xml:34`, `pb_ask_hr/views/portal_templates.xml:31`).
- `tile_meta(url)` (`pb_me_home.py:221`) is read by `pb_me_portal/views/portal_templates.xml:90`.

**Icons.**
- `pb_me_portal.ess_icon` (`pb_me_portal/views/portal_templates.xml:498-550`) draws a FIXED set. A source test checks that icon names exist.
- Available icons include file-text, download, user, users, user-check, user-plus, image, shield, briefcase, banknote, wallet, receipt, plane, heart, message-circle-question, list-checks, paperclip, send, inbox, megaphone, check-circle, alert.
- **Reuse these.** A new glyph (e.g. sparkles, id-card, landmark) is an edit to pb_me_portal. If one is wanted, it goes in ONE prep commit before the builders start (the ETP precedent: pb_me_portal 19.0.3.4.0 carried the three ETP tiles/glyphs so the agents never edited it).

**Cards on the bento.**
- `_pbme_extra_cards(emp)` returns `{key, template, data}` (`pb_me_home.py:328-340`) and is drawn by `pbme_bento` (`portal_templates.xml:197-250`).
- The home root class is `.pbme-home`, not `.pbme` (PRB-W5). Precedent: `pb_loans/models/pb_me_home.py`.

**Needs you.**
- `_pbme_needs_extra(emp, put)` (`pb_me_home.py:721-731`). `NEEDS_ORDER` (`:83-87`) is fixed; extra keys are appended after it (`:716-717`).

**My requests.**
- `_my_requests_sources()` (`pb_me_home.py:739-864`) is read softly as superuser for the user's own employee (`:866-928`).
- A source dict holds `key, model, label, icon, employee_field, date_field, state_field, states, url, title`.
- Precedents: `pb_me_expense/models/pb_me_home.py:47-66`, `pb_ask_hr/models/pb_me_home.py:40-57`, pb_me_trip.

**Soft reads.**
- `pb.me.home.optional(model_name, fn, fields=())` (`pb_me_home.py:236-260`) runs inside a savepoint and never returns a 500 on `/my`.

**Assets.**
- `web.assets_frontend` is deliberately lean (`pb_me_portal/__manifest__.py:54-69`).
- Each new module adds its OWN files to `web.assets_frontend` in its own manifest. That is not a shared-file edit.
- Backend PayAI assets must never leak into the portal (§6.5).

**Profile page.**
- Template `pb_me_portal.portal_my_profile` (`pb_me_portal/views/portal_templates.xml:676-751`). Its subtitle says "Bank changes go through a separate secure flow" (`:681`) but links nowhere.
- New cards on it go in through QWeb `inherit_id` + xpath from the new module (no file edit).

### 1.3 The one approval engine and the one Approvals inbox

- **The inbox.** `pb.approval.inbox` (`pb_approval_config/models/inbox_facade.py:77`) lists `biz.approval.request` rows. It shapes what is shown; it grants nothing (`:1-15`). "Mine" means an open seat (`:406-410`).
- **Registering a new process (all from the new module's own files):**
  1. A `biz.approval.process` record in the module's own `data/approval_process.xml`. Precedents: `pb_loans/data/approval_process.xml`, `pb_me_expense/data/approval_process.xml:13-21` (`money=True`).
  2. `register_chain(model, key, submit_state=…, driven=(…), amount_field=…)` at import. The shim is `biz_approval_workflow/models/chain_shim.py:63-102`.
  3. The `_chain_title/_chain_facts/_chain_fact_specs/_chain_kinds/_chain_revision_values/_approval_detail` adapter.
  4. `_approval_seed_default(company)` using `biz.approval.seed.fill_role_from_group` and `lay`. The seed relay is `pb_approval_config/models/seed.py:251-279`.
  - The shim gives `_approval_context/validate/freeze/advance/apply/return/reject` (`chain_shim.py:343-521`).
  - Cleanest precedents: `pb_loans/models/loan_approval.py` (80 lines), and `pb_me_portal/models/pb_profile_change_approval.py` (same shape as item 1).
- **Engine facts:**
  - `submit` checks `record.check_access('write')` (`biz_approval_workflow/models/engine.py:842-854`).
  - A route with no active step takes the fast lane and applies at once (`:902-910`).
  - Independence rule: whoever sent it, prepared it, or is its subject cannot approve (`:445-452`, `:1240-1255`).
- **Ledger traps:**
  - PRB-W1: register no `date_field` when the date can be in the past.
  - W2B-2: the context and apply hooks run as the deciding person, so read under sudo.
  - QF3-6: a withdraw hook that writes holds its own savepoint.
  - QF2-G1 / W2B-5: set `allowed_company_ids` explicitly.
- **Direct `state` writes are blocked** on chain models (`biz_approval_chain/models/biz_approval_mixin.py:118-122`).

## 2. Item 1: family, ID papers, photo, marital status and bank details changed on My Payobook

### 2.1 What exists today

**The profile change request** (`pb_me_portal/models/pb_profile_change_request.py`):
- **Fields.** Only five contact fields can change: `x_phone, x_private_email, x_address, x_emergency_contact, x_emergency_phone`. They map to `private_phone, private_email, private_street, emergency_contact, emergency_phone` (`:41-47`).
  - The allowed set is parameter `pb_me_portal.editable_fields` (`:36-37`, `:110-116`, seeded `pb_me_portal/data/pb_me_portal_data.xml:15-18`). It can only narrow the five, never add to them.
- **States** `draft → hr_review → approved/refused` (`:87-92`). The model uses `biz.approval.chain.mixin` (`:63`).
- **Engine registration.** `register_chain('pb.profile.change.request', 'master', submit_state='hr_review', driven=('approved',))` (`pb_me_portal/models/pb_profile_change_approval.py:31-42`).
  - The default route is one "HR lead" step (`:123-134`).
  - Catalogue row: `pb_approval_config/data/processes.xml:158-165`.
- **Guards:**
  - Non-whitelisted fields are stripped (`:193-195`, `:229-231`).
  - `employee_id` is forced to the session's own employee (`:201-214`).
  - The request freezes under review (`:238-248`).
  - The `cur_*` snapshot is taken at submit (`:280-289`).
  - The diff is shown to the employee (`:310-332`) and to approvers as before/after (`pb_profile_change_approval.py:99-119`).
- **Applying.** `_apply_to_master` (`:335-352`) writes changed, allowed, non-blank values via `employee_id.sudo().write()`, called from `_after_approval_transition('approved')` (`:261-263`). An audit rule covers the five fields (`pb_me_portal_data.xml:31-36`).
- **Routes** (`pb_me_portal/controllers/portal.py`):
  - `/my/profile` (`:156`)
  - POST `/my/profile/request` (`:222-248`)
  - `/my/profile/request/<id>` (`:250-261`)
  - `/submit` (`:263-276`)
  - `_own_request` (`:278-290`)
- **Templates:**
  - `portal_my_profile` (`portal_templates.xml:676-751`), which shows a contact card only (`portal.py:174-187`)
  - `portal_profile_request` (`:754-806`)
  - `ess_stepper` (`:823`)
- **Needs you rows** `profile_waiting` / `profile_approved` (`pb_me_home.py:693-703`). My requests entry: `:804-817`.

**Bank document check: `pb_bank_ocr`** (19.0.1.2.2), model `pb.bank.change.request` (`pb_bank_ocr/models/pb_bank_change_request.py`):
- **Fields:**
  - required `attachment_id` and `doc_kind` (`:72-80`)
  - OCR status, provider and text (`:91-97`)
  - proposed `x_bank_name/branch/account_name/account_number/iban/swift` (`:100-105`) and their `cur_*` snapshot (`:108-111`)
  - check results `v_format_ok/msg`, `name_match_score/band`, `duplicate_ids`, `duplicate_ack`, `resolved_bank_id` (`:114-127`)
- **States** `draft → hr_review → finance_review → approved/refused` (`:82-88`).
- **Document read.**
  - `_biz_doc_ocr_run` → `biz.doc.ocr._extract` (`:374-397`), queued by `action_run_ocr` (`:399-412`).
  - The provider comes from `payroll.ai.config.get_config_for_purpose('doc_ocr')` (`biz_doc_ocr/models/biz_doc_ocr.py:48-52`). Without one it uses rules only (`:57-61`); with one it uses vision (`:75`), or Tesseract (`:85`).
  - `_extract` reads attachments AS SUPERUSER and is private (`:29-32`). Callers must prove ownership of the attachment first.
- **Checks.**
  - `action_validate` (`:415-450`): number format and SWIFT; the holder name is scored against the employee (≥85 green, ≥60 amber).
  - `_find_duplicates` (`:452-476`): same company, `vietnam_bank_account_number` ONLY.
  - A duplicate needs `duplicate_ack` (`:242-245`). Everything is re-checked before final approval (`:248-260`).
- **Writes** the four `vietnam_bank_*` fields only (`:289-319`). IBAN and SWIFT are never written, and `res.partner.bank` is not touched. History goes to `pb.employee.bank.history` (`pb_bank_ocr/models/pb_employee_bank_history.py:52-80`).
- **Engine.**
  - `register_chain(..., 'bankchange', submit_state='hr_review', driven=('finance_review','approved'))` (`pb_bank_ocr/models/pb_bank_change_approval.py:29-35`).
  - Default route: HR lead → Finance approver (`:123-137`).
  - Catalogue row: `pb_approval_config/data/processes_p6.xml:28-35`.
- **No controller.** The only screen is a staff sidebar item (`pb_bank_ocr/data/pb_sidebar.xml:12-21`, `group_hr_payroll_user`). An Employee-tier login cannot start a bank change.

**Updates bank rule (owner rulings UPDATES D13–D15: ONE second person, never the proposer; named approvers on rize)** (`pb_records/models/records_approval.py`):
- `_bank_excluded` (`:322-336`): self-service, support and demo logins never decide.
- `_second_people` (`:344-352`)
- `_approval_step_people` (`:384-427`): the proposer is removed.
- `_approval_may_decide` (`:429-444`)
- `_bank_refusal` (`:473-483`)
- Process key `records_bank` (`:46`; `pb_records/data/records_bank_process.xml:14-22`). The default route is "A second person" from the Finance role (`:1099-1110`, `:1167-1187`).
- The engine hooks come from `pb_records/models/records_engine.py:1-40`.
- `pb.bank.change.request` gets only the engine's general independence rule, not this one.

**Family and dependants:**
- **Vietnam tax dependants.** `vietnam.employee.dependent` (`pb_hr_payroll_vietnam/models/vietnam_employee_dependent.py:14-90`) holds name, relationship, date of birth, ID number, tax code, eligibility dates, status eligible/ineligible/pending (`:63-67`) and `tax_allowance`.
  - It has **no `company_id` and no record rules**. Access is for payroll base user/manager only (`pb_hr_payroll_vietnam/security/ir.model.access.csv:12-13`).
  - It feeds the tax allowance (`hr_employee_vietnam.py:214-284`). There is also a manual count `vietnam_dependents_count` (`:42`).
  - Note: `pb_hr_payroll_vietnam` is a "legacy" country module (memory `payobook-current-design`). Check it is installed per database before relying on it.
- **Benefit cover.** `pb.benefit.enrollment.dependants_json` "Family covered" (`pb_comp_ben/models/benefit.py:338-341`, parser `:382`). It is read-only on `/my/compensation` (`pb_comp_ben/controllers/portal.py:211`; `pb_comp_ben/views/portal_templates.xml:211`).
- **Stock Odoo 19.** `marital`, `spouse_complete_name`, `children`, `identification_id`, `passport_id` and `private_street` are on **`hr.version`**, restricted to `hr.group_hr_user`. `permit_no`, `visa_expire` and `emergency_contact` are on `hr.employee`. These are in core, outside the repo: `~/odoo19/odoo/addons/hr/models/hr_version.py:73,79,87,107,114,116`; `hr_employee.py:162,164,172`. HR's 360 view lists them at `pb_employee_vault/models/employee_details.py:36-72`.
- **There is no single "family members" list per employee.** The study row 04 "no single family list reused across plans and tax" is confirmed.

**ID papers** (`pb_employee_vault` 19.0.1.5.0):
- `pb.employee.document` (`pb_employee_vault/models/employee_document.py:51-90`) holds `issue_date`, `expiry_date`, `expiry_state`, and a `verified` flag only HR can set (`:146-170`).
- Categories (`pb_employee_vault/data/document_category_data.xml:17-38`): ID (expiry required), PERMIT, HEALTH.
- `/my/documents` (`pb_me_portal/controllers/portal.py:340-355`) lists every vault document of the person. Upload is at `:380-445`.
  - ID, certificate, health and other are self-uploadable; permits and labour contracts are HR-only (`pb_me_portal_data.xml:38-52`).
  - **An upload goes straight in, unverified, with no approval, and no number reaches `identification_id`.**
  - The attachment-ownership precedent is at `employee_document.py:124-136`.

**Photo:**
- No `/my` route writes `image_1920`.
- Photos are served at `/my/photo/<id>/<size>` (avatar_128/256 only, `portal.py:44-45`, `:133-151`). The guard is `pb.me.home._pbme_photo_allowed`: own record, or an active colleague of one of the user's companies (`pb_me_home.py:402-433`). Tests: `pb_me_portal/tests/test_t3b_photos.py`.
- Photos are shown to staff on the clock and attendance screens (`pb_clock/models/clock_lens.py:562`, `pb_attendance_flow/models/attendance_exception.py:228`). A self-changed photo is what a supervisor sees when checking a person, which is a reason to keep the photo under approval.

### 2.2 What is missing

- Family members (add, change, remove) with relationship, date of birth, ID number, "counts for tax" and "covered by insurance". Today these are not on `/my` at all.
- Marital status.
- ID paper numbers: national ID, passport and permit, with expiry, linked to the uploaded scan, with approval. The approved number writes the `hr.version` / `hr.employee` field and marks the vault document verified.
- A photo change with approval.
- A portal start for the bank check:
  - an owned upload
  - the document read
  - the checks shown in plain words
  - the employee's own `/my` page of progress
  - the bank route following the Updates rule (one second person, never the proposer, D13–D15)
  - writing the store the bank file reads (§0.1)
  - duplicate check across both stores
- "See all my details in one place": identity, ID papers, family and bank cards (masked) on `/my/profile`.

### 2.3 Precedents to clone

- **Request + approval:** `pb_profile_change_request.py` with `pb_profile_change_approval.py` (same shape, key `master`), or a new key per kind.
- **Portal upload/send/withdraw:** `pb_me_expense/controllers/portal.py:138-343`.
- **Second-person bank rule:** the `pb_records/models/records_approval.py:322-483` hooks, attached to the new model the way `records_engine.py` attaches them.
- **Tile:** `pb_training/models/me_home_tile.py`.

### 2.4 Risks

- **Privacy.** Every portal path is sudo. Force the employee from the session, never from a parameter. `pb.bank.change.request.employee_id` defaults from `env.user.employee_id` (`:69-71`), so the portal path must force it.
- **Document theft.** `_extract` reads any attachment as superuser. Only an attachment the user created, unlinked to any record, may be passed in.
- **Money.** A bank change redirects pay, so mark the process `money=True`. A share (portal) user can never approve (`records_approval.py:329-330`). A bank account number must be masked on every `/my` page and in My requests.
- **Audit.** A write to an `hr.version` field through `hr.employee` may bypass the `hr.employee` audit rule. Verify before adding those fields.
- **Tax.** A Vietnam dependant change alters take-home. If wired to tax at all, it must arrive `pending` (`vietnam_employee_dependent.py:63-67`) and HR confirms. This is owner question Q1, and the Step 2 overlap.
- **Dependants' record scope.** There is no `company_id` and no rules on `vietnam.employee.dependent`. A portal read must go through the ownership guard only.

### 2.5 Modules a builder would edit

- New module (proposed `pb_me_details`):
  - request model(s), approval adapter, own process data
  - `/my/profile/*` routes in a `CustomerPortal` subclass
  - QWeb xpath into `portal_my_profile`
  - `pb.me.home` overrides
  - a family-members model
  - vi/id `.po`
- `pb_bank_ocr`:
  - fix the dead `_approval_can`
  - a portal-safe entry method
  - write both bank stores
  - duplicate check over both
  - second-person hooks
- Optional, only if owner Q1 says "feeds tax": `pb_hr_payroll_vietnam` (company scope and rules on dependants).
- Optional: `pb_records` (the §0.1 two-store fix on the Updates bank lane). Decide with Fable; it is a fix to a shipped feature.

## 3. Item 2: salary or employment certificate as a PDF

### 3.1 What exists today

**The letter engine (`pb_lifecycle` 19.0.1.20.0):**
- **Models.**
  - `pb.letter.template` (`pb_lifecycle/models/letter.py:56-77`): `letter_type`, `subject`, `body_html`, `vault_category_id` (`:71`).
  - `pb.hr.letter` (`:84-119`): employee, template, `case_id`, `rendered_html`, `state` draft/generated/sent, `attachment_id`, `document_id`, `context_json`, `generated_by`.
- **Placeholders** (`:37-45`): `employee_name, job_title, department, company, date, joining_date, extra`. Any `context_json` key adds or overrides one (`:148-159`). Every value is HTML-escaped (`:160`) and filled by `string.Template.safe_substitute` (`:178`). The joining date is `first_contract_date`, falling back to the earliest contract start (`:162-169`).
  - **No pay placeholder exists.**
  - The pay letters build their figures server-side into `context_json` (`pb_pay/models/pb_pay_apply.py:363-379`). That is the precedent for a salary certificate.
- **Letter types.** `LETTER_TYPES` (`pb_lifecycle/models/lifecycle_common.py:71-85`) has no salary or employment certificate.
  - **Gotcha:** add a type with `selection_add` on `pb.letter.template.letter_type` ONLY, with `ondelete`. `pb.hr.letter.letter_type` is a related selection, and a `selection_add` there FAILS THE REGISTRY LOAD (`pb_hiring/models/offer.py:63-81`, the comment at `:71-81`).
- **Shipped templates.** The experience letter (`pb_lifecycle/data/letter_template_data.xml:11-37`, filed under `pb_employee_vault.cat_certificate` `:17`) reads "To whom it may concern … employed by ${company} as ${job_title} … since ${joining_date} … issued … at the employee's request". It already works as an employment certificate.
- **PDF.**
  - Report `pb_lifecycle.action_report_hr_letter` (`pb_lifecycle/report/hr_letter_report.xml:8-17`), QWeb `report_hr_letter_document` (`:23-51`), `web.external_layout`.
  - `_make_pdf` (`letter.py:193-218`) renders it under sudo as an `ir.attachment` on the letter.
- **Filing.** `_file_in_vault` (`:220-255`) runs INSIDE `action_generate` (`:188-189`), i.e. **before approval**. A letter still waiting for approval is already on `/my/documents`.
- **Email.** `_action_send_now` (`:310-345`) uses mail template `pb_lifecycle.mail_template_letter_delivery` (`pb_lifecycle/data/mail_template_data.xml:121-141`). `email_from` is the current user, and the address falls back to the PRIVATE email (`letter.py:320`).
- **Approval.**
  - Key `letters` (`pb_lifecycle/models/letter_approval.py:34`; catalogue row `pb_approval_config/data/processes_p7.xml:14-21`).
  - Facts: `letter_type` and `has_pay_figures` (`:40`, `:70-72`, `:86-91`; true for pay_review, pay_change, incentive, ff_cover).
  - Default route: "HR lead" (`:158-169`).
  - `_approval_apply` sends the letter (`:149-155`). `action_send` → `biz.approval.engine.submit` (`letter.py:268-296`).
- **Access.** Lifecycle groups and seats only (`pb_lifecycle/security/ir.model.access.csv:17-30`). Portal users have none.
- `pb_lifecycle` already depends on `pb_me_portal` and `pb_employee_vault` (`pb_lifecycle/__manifest__.py:63-80`).
- **All other letters use this engine:**
  - offboarding (`pb_offboarding/models/offboarding_automation.py:63-121`)
  - contracts (`pb_contract_lifecycle/data/letter_template_data.xml:27,61`)
  - probation (`pb_probation/models/probation_review.py:1017`)
  - pay (`pb_pay`)
  - PIP (`pb_pip/models/letter_ext.py`)
  - comp & ben (`pb_comp_ben/models/letter_ext.py:42-52`)
  - Hiring offers reuse the template library (`pb_hiring/models/offer.py:18-23`).
- No hit anywhere for "salary certificate" or "employment certificate".

**PDF and download precedents on `/my`:**
- **Payslip PDF.** `/my/payslips/<id>` with `report_type=pdf` (`pb_me_portal/controllers/portal.py:630-656`, `:638-641`).
  - Ownership: `_document_check_access` (`:615-628`). Held payslips are refused (PR-C).
  - Report: `pb_hr_payroll_formula.action_report_payslip_themed`, else `om_hr_payroll.action_report_payslip` (`:674-682`).
- **Tax sheet.** `/my/taxsheet` (`:450-505`) is HTML only.
- **Documents.** `/my/documents` downloads by attachment token through `/web/content` (`:367-378`). A filed letter appears there automatically.
- **Pay figures for a salary certificate:**
  - the agreed wage on the contract/version
  - or payslip net via `line_ids.pb_net_line()` (`om_hr_payroll/models/pay_bands.py:168`)
  - One-pay-band rule (memory `one-pay-band-rule`): Gross / Deductions / Net read `pb_pay_totals`, never the rule category.
  - A plain internal login can read its own `hr.payslip` (PRC-W1).

**Ask HR (`pb_ask_hr` 19.0.1.3.0):**
- `pb.ask.hr.ticket` (`pb_ask_hr/models/ticket.py:70-110`). Categories include `documents` "Documents & letters" (`:37-44`). It is a conversation, not an approval (`pb_ask_hr/__manifest__.py:21`).
- `/my/ask-hr/new?category=documents` pre-selects the category (`pb_ask_hr/controllers/portal.py:186-191`). Hand-offs can therefore be a plain link, with no pb_ask_hr edit.

### 3.2 What is missing

- `/my` request page: pick "Employment certificate" or "Salary certificate", purpose (bank, visa, rental, other), language, and how many months of pay. Then a status, the PDF download, and a My requests row.
- Two letter types with templates (vi/id/en wording).
- Server-built pay figures. The employee never writes `context_json`.
- Filing only when approved or issued, so the PDF is not visible before.
- Sending the PDF to the work email (not the private one) with the system as sender, or no email at all: download on `/my` is enough, and tenant email is off on 3 databases.

### 3.3 Precedents to clone

- Request form: `/my/ask-hr/new` POST.
- Figures: `pb_pay_apply._make_letters` (`pb_pay/models/pb_pay_apply.py:363-379`).
- Download: the `/my/documents` token link.
- Listing: a `_my_requests_sources` entry on the letter (`employee_field='employee_id'`).
- Route fact: set `has_pay_figures` for the salary certificate so routes can treat it apart.

### 3.4 Risks

- **The letter shows up before it is approved.** Override `_file_in_vault` timing for the new types in the glue module, never in `pb_lifecycle`.
- **Sender.** `action_send` from an employee login makes the employee `submitter_uid` and `email_from`. Run under sudo with an explicit sender.
- **Pay figures on paper.** Show only the person's own figures. The salary certificate must not be issued for a person on pay hold, or with a draft payslip.
- **Two templates per language.** Rize uses English and Indonesian, Vietnam companies Vietnamese.

### 3.5 Modules

- New glue module (proposed `pb_me_letters`), which inherits:
  - `pb.letter.template` (`selection_add`)
  - `pb.hr.letter` (`_placeholder_values`, `_file_in_vault`, send)
  - plus its own data templates, own controller and templates, `pb.me.home` overrides, and vi/id `.po`.
- **No edit to `pb_lifecycle`** (the Performance team's area).

## 4. Item 3: consent for personal data, recorded per employee

### 4.1 What exists today

- **Nothing for employees.** A grep for GDPR, Decree 13, 13/2023, PDPA and "data subject" finds nothing.
- **Voice consent for PayAI.** `payroll.ai.consent` (`pb_payroll_ai_insights/models/payroll_ai_consent.py:37-60`) is keyed on the USER: `user_id`, `voice` unset/granted/declined, `decided_at`.
  - Only the person reads their row; managers are excluded on purpose (`pb_payroll_ai_insights/security/payroll_ai_security.xml:64-76`).
  - It is a clone of `learn.consent` (`pb_learn/models/learn_question.py:47-96`).
- **Candidate consent** (`pb_hiring` 19.0.2.23.8):
  - A locked "consent" question on every application form (`pb_hiring/models/forms_p2.py:100-101`), worded at `:65-66`, with months from the market retention rule (`:422-431`).
  - The exact sentence shown is stored as `hr.applicant.pb_consent_on` / `pb_consent_text` (`:639-642`, `:846-847`), sudo-only write (`:855-857`).
  - It drives retention and anonymising (`pb_hiring/models/privacy_p4.py:26-29`, `:366-395`).
  - **It is not carried to the employee at hire.**
- **Acknowledgement precedents:**
  - PIP `employee_ack` / `ack_at` (`pb_pip/models/pip_case.py:139-141`) is stamped once by `action_acknowledge` (`:584-601`) via POST `/my/growth/ack`, with the plan taken from the session (`pb_pip/controllers/portal.py:211-233`).
  - Notice read receipts `pb.me.notice.read` (`pb_me_portal_comm/models/notice_read.py:12-34`) record "opened" only.
  - Onboarding confirmation steps: `/my/journey/step/<id>/done` (`pb_onboarding/controllers/portal.py:153-180`).
- **Marketing privacy page.** `/privacy` (`pb_website/controllers/legal.py:9`, text `pb_website/legal_content.py:12-70`) says the employer is responsible for notices to its staff.
- **No first-sign-in gate on `/my`.** Precedents for one:
  - `home()` overrides: `pb_hiring/controllers/agency_portal.py:132-137` (redirect) and `pb_pip/controllers/portal.py:99-125` (context key).
  - `ir.http` hooks: `biz_access/models/ir_http.py:94`, `pb_tenancy/models/ir_http.py:88`.
  - The home is built in `pb_me_portal/controllers/portal.py:39,90-113` → `pb.me.home.get_home_data` (`pb_me_home.py:273-310`).

### 4.2 What is missing

- A per-company privacy notice with a version, wording per language, and published / replaced states.
- A per-EMPLOYEE record: notice version, exact wording shown, language, when, by which login, how (screen or paper recorded by HR), withdrawn on. This must not be keyed on the user: one person can have several employee records (`_ess_own_employees`).
- The employee's view of what they agreed, and a way to withdraw (or to ask HR).
- An HR list of who has and has not agreed; a re-ask when the notice changes; a paper path for people with no login.
- Optionally, carrying the candidate's consent across at hire.

### 4.3 Precedents to clone

- Wording snapshot: `pb_consent_on/pb_consent_text`.
- Row shape: `payroll.ai.consent`.
- Recording: the PIP session-derived POST.
- Showing: `_pbme_extra_cards` + `_pbme_needs_extra`. A gate only through a fail-open `home()` override if the owner wants one (Q3).

### 4.4 Risks

- A gate that raises turns `/my` into a 500. Every hook needs a savepoint and must fail open.
- Deep links (`/my/payslips`) bypass a `home()`-only gate. An `ir.http` gate is heavier and touches every request.
- Who may read refusals: follow the consent precedent (HR yes, managers no).
- A notice's wording is the customer's legal text. Ship a neutral default, and never say "Odoo" or name a law the customer is not under.

### 4.5 Modules

- New module (proposed `pb_me_privacy`): notice and consent models, staff list (HR), `/my/privacy` routes, card, needs-you, vi/id.
- No shared file edits.

## 5. Item 4: apply for internal roles

### 5.1 What exists today

**The Refer page** (`pb_hiring/controllers/portal.py`, class `PbHiringPortal` `:49`):
- `_hiring_employee` (`:52-59`) takes the employee from the session.
- `/my/refer` (`:212-231`, template `pb_hiring.portal_my_refer` `pb_hiring/views/portal_templates.xml:100`).
- POST `/my/refer/submit` (`:233-289`). CV PDF/Word up to 5 MB (`:28-33`). Consent and a relationship declaration are required (`:279`).

**Roles listed** (`_open_roles` `:61-71`): `pb.hiring.requisition` where all of these hold:
- `state='open'`
- `referral_open=True` (`pb_hiring/models/requisition.py:218`)
- `role_type!='sensitive_replacement'`
- `is_confidential=False` (`pb_hiring/models/requests_p3.py:336`)
- same company; at most 60 rows

`referral_open` is set automatically when parameter `pb_hiring.referral_auto` is on (`requisition.py:841-848`) and is cleared on close or fill (`:564`, `:575`).

**A referral becomes an applicant:**
- `pb.hiring.referral.refer()` (`pb_hiring/models/referral.py:108-146`) → `_make_applicant` (`:149-183`) creates an `hr.applicant` under sudo.
  - `pb_requisition_id` is set; `source_id` is the "Referral" `utm.source`, looked up by name (`_referral_source` `:185-193`).
  - The override at `pb_hiring/models/journey.py:567-599` checks `employee.user_id == env.user` and stores the consent and declaration (`:547-558`).
- There is **no `hr.candidate` model** on this build; everything lives on `hr.applicant`.

**Other pages:**
- `/my/hiring` (`portal.py:132-160`) is the manager/interviewer page: roles asked for, interviews in the next 14 days, feedback owed, `.ics` (`:182`).
- Both pages are `auth='user'`, sudo after the session check, and tested for share users (`pb_me_portal/tests/test_portal_accounts.py:412-425`).

**Publishing:**
- Stock `hr.job.website_published` (`website_hr_recruitment/models/hr_job.py:38`); portal and public users see only published jobs.
- `pb.hiring.posting.publish_for` (`pb_hiring/models/posting.py:66-100`) refuses confidential roles (`:79`).
- The apply rule is `hr.job.pb_hiring_accepts_applications` (`pb_hiring/models/hr_job_ext.py:19-31`).
- The careers page is `pb_hiring/controllers/application.py` (POST `/hiring/apply/<job_id>` `:317`, `auth='public'`).
- **There is no "staff only" or "internal" flag anywhere.**

**At hire:** see §0.4 (`offer_closure.py:70-135`, `:160-224`, `:287-294`, `:402-424`). `hr.applicant.employee_id` (stock `hr_recruitment/models/hr_applicant.py:72`) links to an existing employee but is never set by pb_hiring for staff.

**Retention:** applicant anonymising runs from the consent date (`privacy_p4.py:381-397`). Internal applicants must be excluded, or they keep their history differently.

### 5.2 What is missing

- A posting choice per role: public / staff only / both. Staff-only roles must stay off the careers page (`hr_job_ext.py`) and on `/my`.
- "Apply for this myself" on `/my` (or a new `/my/jobs`), with:
  - no CV upload needed (the employee record is the profile)
  - an optional note and CV
  - an `hr.applicant` with `employee_id` set and source "Internal"
  - a My requests row and status
- Privacy: their application is not visible to their current manager unless the owner decides otherwise (Q4).
- The end of the process: an internal hire must NOT run `action_confirm_joined`'s new-joiner steps. It ends as a job change for the existing person: new job, manager, pay, start date. That is the Contracts team's "Change job" flow (Step "Job changes, contracts and structure"). Until it exists, the internal offer ends with a "job change to do" for HR and no automatic contract write.
- A count of internal moves (study row 02): the source "Internal" on the applicant is enough to count them.

### 5.3 Precedents to clone

- `/my/refer` + `referral.refer()` / `_make_applicant`.
- The `selection_add` / `_inherit` pattern used by `pb_hiring/models/offer.py` for the letter template.

### 5.4 Risks

- **Duplicate employee or silently unchanged pay** (§0.4). The glue must override `_ensure_employee` / `_ensure_contract` / `_ensure_login` / `_ensure_case` for internal applicants, or block `action_confirm_joined` for them.
- **Manager visibility.** Hiring managers and interviewers see applicants of their own roles. The person's CURRENT manager sees nothing today unless they sit on that role. Keep it that way, or follow Q4.
- **Retention clock and anonymiser** (`privacy_p4.py`) must not anonymise an employee's internal application as if they were an outside candidate.

### 5.5 Modules

- New glue module (proposed `pb_hiring_internal`):
  - `_inherit` `pb.hiring.requisition` (posting choice field)
  - `hr.job` (`pb_hiring_accepts_applications` refuses staff-only on the careers page)
  - `pb.hiring.offer` (internal end)
  - own controller and templates (xpath into `pb_hiring.portal_my_refer`, or a new `/my/jobs` page), tile via `TILES.setdefault`, vi/id
- **No edits to `pb_hiring` files** if done this way. This matters because the Contracts team may edit `pb_hiring` (hiring freeze, Decision Room → open roles, "would rehire").

## 6. Item 5: PayAI on My Payobook, answering from the company's own policy documents

### 6.1 Where PayAI lives today

**Backend only:**
- Every PayAI asset is in `web.assets_backend`: `pb_payroll_ai_insights/__manifest__.py:106`, `pb_payai_actions/__manifest__.py:44`, `pb_learn/__manifest__.py:153`, `pb_training_payai/__manifest__.py:40`.
- No portal controller or template calls `payroll.ai.*`.

**Entry points:**
- floating pill (`pb_payroll_ai_insights/static/src/js/ai_insight_chat.js:1960`)
- one-chat helper drawer (`:2685-2692`)
- full page `payai_chat_full` (`pb_payroll_ai_insights/views/payroll_ai_chat_views.xml:4-7`)
- command palette (`payai_palette.js:10-16`)
- Coach (`pb_payai_actions/static/src/js/coach_patch.js:28`)

**Chat calls** are ORM RPCs on `payroll.ai.conversation`:
- `rpc_send_message` (`pb_payroll_ai_insights/models/payroll_ai_conversation.py:281`) → `payroll.ai.engine.process_message` (`payroll_ai_engine.py:360`)
- The router is `learn.helper.route` (`pb_learn/models/learn_helper.py:1020`).
- `_payai_available` (`:33-45`) checks the group and a configured provider.

**Group:**
- `group_payai_user` (`pb_payroll_ai_insights/security/payroll_ai_security.xml:21`), implied by the manager group (`:31`) and, in code, by `base.group_user` (`:103-106`). See §0.5 for payobook.
- Access on conversations and messages is for this group only (`ir.model.access.csv:7-8`). Portal users have none.

**Who has it** (memory `payai-does-it-program`):
- payobook: only people given the "AI assistant" role.
- rize: "look" tier only.
- payobook_template: all switches off.
- The owner wants ChatGPT on for Rize, but a key must be pasted by an admin. Agents never enter keys.

### 6.2 Provider plumbing (names only, no values)

- **`payroll.ai.config`** (`pb_payroll_ai_insights/models/payroll_ai_config.py:14-85`). Field names:
  - `provider_type` (openai / anthropic / ollama / tesseract)
  - `purpose` (insights / doc_ocr)
  - `api_key` (`:33`, no `groups=`; model readable by PayAI manager/admin)
  - `model_name`, `base_url`, `timeout`, `max_tokens`, `temperature`, `is_active`, `company_id`
- **Lookup.**
  - `get_active_config` (`:100-124`, sudo, user's company first, then any company).
  - `get_config_for_purpose(purpose)` (`:126-144`): that purpose in this company → that purpose anywhere → **any active config in this company → any active config at all**.
  - So a new purpose silently uses the insights key, possibly another company's in the same database.
- **Providers.** `ai_providers/provider_factory.py:20`. The base is `base_provider.py:10` (`generate_chat`, `generate_tools`, `generate_vision`, `accepts_pdf`).
- **Switches:**
  - database parameter `payai.voice_enabled` (`payroll_ai_consent.py:29`; set from `pb_learn/models/learn_settings.py:49,149`)
  - `pb_learn.compose_enabled` (`learn_intent.py:247`)
  - per company `payai_tier_look/prepare/decide`, `payai_voice_go_ahead` (`pb_payai_actions/models/res_company.py:23-44`)
- **Redaction.** `pb_payroll_ai_insights/models/ai_redaction.py` (`redact_names` `:460`, `restore_names` `:490`, `generic_scrub` `:333`) is "a reduction, not a guarantee" (`:46-56`). The egress source tests are `pb_payroll_ai_insights/tests/test_egress.py:111-497`.
- **No usage or cost count** exists (that is the study's Step 10 item "A count of AI use per customer").

### 6.3 Knowledge today

- **The "knowledge" intent has no company source.** `_process_knowledge_query` (`payroll_ai_engine.py:693-739`) sends the system prompt (`PAYAI_SYSTEM_PROMPT` `:71`) plus the redacted question; the model answers from general knowledge.
- **pb_learn answers from shipped content.** `pb_learn/static/content/learn_content.json` is read via `learn.content` (`learn_content.py:1-30,101`). Tenants fill only named slots (`learn_tenant_override.py:1-35`).
  - Order (`learn.intent._ask_raw`, `learn_intent.py:1352-1420`): curated intents → glossary → optional composer (LLM over pb_learn's own text only, `:1420-1500`) → an honest "I don't know".
- **No embeddings, vector store, retrieval, or upload place for a handbook.** `pb.employee.document` is per employee (`employee_document.py:56`, `employee_id` required).
- **Text extraction precedents:**
  - `pb_training_payai/models/draft.py:116-160` (`docx_text`, `pdf_text`, `MAX_CHARS`, `MAX_PAGES`)
  - `biz_doc_ocr` (scans)

### 6.4 Safe personal answers for an employee

All of these resolve the employee from the session:

| Answer | Source | Notes |
|---|---|---|
| Leave left | `pb.ess.workforce.get_my_leave` (`pb_ess_workforce/models/ess_workforce.py:445-475`) | Owned by the leave/time team: call it, never edit it |
| Ask for a day off | `/my/work/leave/apply` (`pb_ess_workforce/controllers/portal.py:162`), preview `:180` | Link only |
| Last payslip | `/my/payslips` (`pb_me_portal/controllers/portal.py:532,630`) | Done/cancel only; refuse a held payslip |
| Public holidays | `/my/holidays` (`pb_timeoff/controllers/portal.py:75`) | |
| Home summary | `pb.me.home.get_home_data` (`pb_me_home.py:273`) | |

### 6.5 Risks

- **Do not expose today's PayAI to portal users.** `payroll_data_query.py:354-1158` answers company-wide salary, headcount, cost, recruitment and leave as the asking user. The pulse reads every payslip under sudo (`payroll_ai_pulse.py:215,268`). The action runner has 18 sudo calls (`pb_payai_actions/payai/runner.py:503+`). Prompts are written for back-office users (`ONBOARDING_SYSTEM_PROMPT` `:162`).
- **The employee assistant must be a separate path:**
  - own model and endpoint
  - grounded ONLY in the company's published policy text, plus the person's own figures from §6.4
  - never calling `payroll_ai_engine` or `payroll_data_query`
  - never reaching Settings → Access and delegations (owner ruling 2026-10-13)
- **Names and personal data in the question go to the provider.** Reuse `generic_scrub` and `redact_names`. Policy text is company data leaving the database, so it needs a company switch (off by default) and a plain notice on screen.
- **Key fallback across companies** (§6.2): a new purpose must be explicit and must not borrow another company's key.
- **Cost.** Every question is a paid call on the customer's account. Add a per-company daily cap and a count (this also feeds Step 10's AI-use count).
- **Wrong answers.** Always show which policy and section the answer came from. With no match, say so and offer "Ask HR" pre-filled (`/my/ask-hr/new?category=…`).

### 6.6 Modules

- New module (proposed `pb_me_payai`), depends on `pb_payroll_ai_insights`, `pb_me_portal`, `pb_ask_hr` (soft):
  - `pb.policy.document` (company, title, file, extracted text, language, published, audience by company/department)
  - simple keyword/section search first (no vector store)
  - a portal-safe ask method (sudo after guard, own scrub)
  - `/my/ask` page and assets in `web.assets_frontend`
  - staff upload screen for HR
  - a company switch and a daily cap, a usage count
  - an egress test copied from `test_egress.py`
  - a new purpose on `payroll.ai.config` via `selection_add` in its own module
- Reuse without editing: `payroll.ai.config`, `ai_redaction`, `pb_training_payai` extraction.

## 7. Item 6: expenses paid back through the pay run, trip advances, yearly claim allowances

### 7.1 What exists today

**Expense claims: `pb_me_expense` 19.0.1.2.0, `pb.expense.claim`** (`pb_me_expense/models/expense_claim.py:83`):
- It carries 1..N stock `hr.expense` (`hr.expense.pb_claim_id`, `pb_me_expense/models/hr_expense.py:25`).
- **Fields** (`:102-130`): `total`, `receipt_count`, state, note, refusal_reason, submitted_on, decided_on, paid_on.
- **States** (`:46-52`): draft, submitted, approved, refused, paid.
- **Engine.** `register_chain(..., 'expense', amount_field='total')` (`:66-73`). The default route is "Their manager → Finance approver" (`:76-80`, seeded `:408-423`).
  - On approve, it calls stock `_do_approve(check=False)` (`:196-202`); on refuse `_do_refuse` (`:203-211`); back to draft `_do_reset_approval` (`:214-227`).
- **There is no `hr.expense.sheet` on Odoo 19.** One receipt is one `hr.expense` (`pb_me_expense/models/me_expense.py:257-294`, `payment_mode` at `:275`). Sending writes `approval_state='submitted'` under sudo (`:372-390`).
- **"Paid" means accounting only.** `_sync_paid` (`expense_claim.py:370-379`) moves the claim to paid when every expense is in `('paid','done')`, triggered from `hr.expense.write` (`hr_expense.py:19,58-65`). Stock `_compute_state` reads the journal entry's payment state (`~/odoo19/odoo/addons/hr_expense/models/hr_expense.py:454-488`).
- **Categories.** `product.product` with `can_be_expensed` (`me_expense.py:146-156`). There are no limits or rate tables; the only caps are 20 receipts, 10 MB and 60 days back (`:32-39`).
- **Routes.** `/my/expenses*` (`pb_me_expense/controllers/portal.py:138-343`), templates `pb_me_expense/views/portal_templates.xml:213,281,378`.
- **Staff board.** `pb.expense.claims` (`pb_expenses_hub/models/pb_expense_claims.py:38-41`, gated on `hr_expense.group_hr_expense_team_approver` `:23`) has an "Approved, not yet paid" view (`:138-141`).

**Trips:**
- `pb.business.trip` (`pb_business_trip/models/pb_business_trip.py:24`):
  - `advance_amount` "Cash Advance" (`:54`)
  - states draft … approved / refused / cancelled (`:65-73`), with **no "settled"**
  - fields locked once approved (`:10-13`, `:292-314`)
  - the chain amount is `advance_amount` (`pb_business_trip_approval.py:27-33`)
- **The trips board's "advance outstanding" just adds the advances of pending and approved trips** (`pb_trips_cockpit.py:69-70,289-298`). Nothing records that the advance was paid out, how much was spent, or the balance.
- `pb_me_trip` 19.0.1.0.0 takes the advance on `/my/trips/new` (`pb_me_trip/models/me_trip.py:379-392`).
- `pb_trip_expense_bridge` 19.0.1.0.1, on trip approval, makes draft `hr.expense` per receipted line plus a per-diem expense (`pb_trip_expense_bridge/models/pb_trip_expense_bridge.py:57-115`).
  - These have **no `pb_claim_id`**, so they skip claim approval.
  - Cancelling a trip deletes them (`:118-133`).
  - A claim receipt can also be tagged to an approved trip (`me_expense.py:168-186,279-284`), which is a double-count risk.
- `pb_trip_payroll_bridge` 19.0.1.2.0 feeds `TRIPDAYS` / `PERDIEM` (`pb_trip_payroll_bridge/models/hr_payslip.py:9`) through `_get_formula_input_values` (`:25-89`) for `payroll`-channel trips (`:74-76`).
  - It feeds Regular runs only since PR-D (`:15-23,45-49`) and keeps no paid-once record.
  - The cash advance never reaches pay.

### 7.2 How a one-off reaches a payslip (the seams)

| Store | Paid-once | No-file path | Pay data file path | Application-data path | Notes |
|---|---|---|---|---|---|
| `pb.updates.oneoff` (`pb_updates/models/updates_oneoff.py:118`) | yes (`_sync_slip` `:362-401`, `_release` `:403-418`) | yes (`updates_payrun.py:82-124`) | yes + clash stop (`:264,327`; `OneoffClash` `:101`) | no (`:19-22,84`) | ONE row per (employee, code, month) (`:181-183`): two claims in one month do not fit; no run-kind filter |
| `hr.payroll.period.input` (`pb_hr_payroll_formula/models/payroll_period_input.py:34`) | reserve `:318-331`, consume `:333-349`, release `:351-358` | — | — | only (`:322-325`) | payroll-manager approval |
| **`pb_loans`** 19.0.1.1.0 (`pb_loans/models/loan_payroll.py`) | yes (`_sync_slip` `:407-465`; cancel/done/reset `:749-762`; payslip delete `:764-766`; run delete `:772-775`) | `_get_formula_input_values` `:525-547` | `_transform_data_to_formula_inputs` `:784-833`, `_create_payslip` `:835-859` | typed source `loans.instalment` answered `resolved` (`:198-246`), reserved in `_application_resolve_inputs` (`:728-746`) | gates in `_plan_for_slip` `:256-331`: Regular run only `:272`, never mid-month `:275`, the paying scheme only `:334-349`, `FOR UPDATE` `:288-292`; take-home never below zero `:34-44,626-662` (PR-E E3) |
| `pb.oneoff.feed` (`pb_comp_ben/models/oneoff_feed.py:100`) | marked paid on release `:480-494` | push + recompute `:25-50,259-268` | push | **blocked** (PRB-W2) | no release on delete; used by training reimbursements |
| trip / workforce bridges | no | seam 1 | no | legacy carry (`application_payroll_source.py:763,810-822`) | Regular only |

- **Clone `pb_loans`** for "approved claim → next regular pay run as a reimbursement" and for "unspent advance → deduction". It is the only seam that covers all three paths, pays once, releases on delete, and has the Regular / scheme / mid-month gates.
- **An unspent advance can simply become a `pb.loan` of kind `advance`** (`pb_loans/models/loan.py:44`), which reuses the balance, instalments and the never-below-zero cut.
- **Pay item.** There is no "reimbursement" or "untaxed" flag in the engine. `net_role` has earning, deduction, net, employer_cost, info, mixed (`pb_hr_payroll_formula/models/formula_net_role.py:602-613`); tax treatment is the scheme's formula. Needed: a per-scheme setting like `pb_loan_rule_id` (`loan.py:157-177`) pointing at an input earning the scheme keeps out of taxable income (blueprint vocabulary `OTHEREXMP` "Other exempt reimbursement", `pb_blueprint/models/workbook_vocabulary.py:57`).
- **Ledger traps:** PRB-W2, PRB-W1, PRB-W3, PRB-W4, PRD-4, PRD-5, PRM-1, PRM-2, PRE-1, PRE-2/W2C-3 (build test schemes whole), PRE-5, W2M-4.
- **Full-and-final prefixes.** `pb_hr_fullandfinal` reads deduction codes by prefix (`full_and_final.py:305-313,339-347`): `MED`/`HI` mean health insurance, `ADV`/`LOAN`/`TAM` mean advance/loan. Never code a reimbursement `MED*`/`HI*`; code an advance recovery `ADV*`.

### 7.3 Yearly allowances

- Nothing exists in expenses. `pb.benefit.plan` (`pb_comp_ben/models/benefit.py:47-76`) only describes cover.
- **The precedent is `pb.training.allowance` plus the claim arithmetic** (§0.6): company figure per year, person override, "left" computed from agreed claims, refusal with numbers, a switch to allow over.

### 7.4 What is missing

**(a) Claims through pay:**
- a company choice "pay claims through the pay run / through accounts"
- a per-claim reservation tied to the payslip
- a scheme pay item setting
- an application-data source
- claim and expenses to paid when the payslip is done or released, and the accounting path must then never pay it too
- the employee sees "paid in your <month> pay"

**(b) Advances:**
- paid-out date and reference
- settle: claims tagged to the trip minus the advance
- the balance owed either way: a top-up to the employee, or recovery through pay (a `pb.loan` advance)
- a real outstanding figure on the trips board

**(c) Allowances:**
- a cap per category (product) per year, optionally per person
- used / left from approved + paid claims
- a check at receipt and at send (`me_expense.py:192` `check_receipt`, `:372` `send`), plus an approval-route fact
- a card on `/my`

### 7.5 Risks

- **Double payment:**
  - accounting and pay run both paying a claim
  - trip lines that are also claim receipts
  - `PERDIEM` with no reservation
  - Extra / top-up runs (clone the Regular-only gate)
- **Pay calculation tier.** The deploy is risky: rehearse with the recompute counting refusals (W2M-4).
- **Currency must match the scheme** (`loan_payroll.py:310-312`).
- **Portal write rights.** An internal employee login has write on its own claim (`pb_me_expense/security/ir.model.access.csv:2`). New fields such as pay route and paid flags need write guards (precedent `pb_training/models/claim.py:597`).
- **PRB-W5.** Never use `%` formatting inside `t-att-*` on a portal page.

### 7.6 Modules

New modules:

| Proposed module | Depends on | Holds |
|---|---|---|
| `pb_expense_payroll` | pb_me_expense, pb_hr_payroll_formula, pb_payruns | reservation, scheme setting, three seams, source, payslip/run hooks, `_sync_paid` override |
| `pb_trip_advance` | pb_business_trip, pb_trip_expense_bridge, pb_loans | paid-out, settle, recovery via `pb.loan` |
| `pb_expense_allowance` | pb_me_expense | caps, used/left, checks, `/my` card |

Small edits, owned by Phase C only:
- `pb_me_expense/views/portal_templates.xml:378`: the "paid in your pay" line; an xpath is preferred.
- `pb_expenses_hub/models/pb_expense_claims.py:101-141`: filters.
- `pb_business_trip/models/pb_trips_cockpit.py:69-70,289-298`: the real outstanding figure.

## 8. Proposed builder phases (can run at the same time)

Each phase owns its modules outright. All `/my` placement goes through the inherit-only seams in §1.2, so **no phase edits `pb_me_portal`**. If a new icon is wanted, Fable makes ONE prep commit to `pb_me_portal` (icons in `ess_icon`) before launch, as ETP did.

| Phase | Items | Owns (new modules) | Owns (existing modules it may edit) | Deploy tier |
|---|---|---|---|---|
| **S6-A "My details, papers and consent"** | 1, 2, 3 | `pb_me_details`, `pb_me_letters`, `pb_me_privacy` | `pb_bank_ocr` (dead-code fix, portal entry, both stores, second-person rule); optional `pb_hr_payroll_vietnam` (only if Q1 = feeds tax); optional `pb_records` (§0.1 fix, if Fable folds it in) | risky (bank details = money, access rules) |
| **S6-B "Apply and ask"** | 4, 5 | `pb_hiring_internal`, `pb_me_payai` | none | risky (AI egress, access) |
| **S6-C "Claims paid in pay"** | 6 | `pb_expense_payroll`, `pb_trip_advance`, `pb_expense_allowance` | `pb_me_expense`, `pb_expenses_hub`, `pb_business_trip` (small; xpath / inherit preferred) | risky (pay calculation) |

Files only READ or CALLED (never edited) by these phases:
- `pb_lifecycle` (letters, A)
- `pb_hiring` (B)
- `pb_payroll_ai_insights`, `pb_learn`, `pb_ask_hr`, `pb_ess_workforce`, `pb_timeoff` (B)
- `pb_loans`, `pb_hr_payroll_formula`, `pb_payruns`, `pb_updates`, `pb_trip_payroll_bridge`, `pb_trip_expense_bridge` (C)
- `pb_employee_vault`, `pb_approval_config`, `biz_approval_workflow` (all)

Unavoidable shared surfaces (no file is shared, but they meet at runtime; give each a merge seam test as in PRM-1):
- **`pb.me.home` overrides.** A, B and C all add tiles, cards, needs-you rows and My requests sources. Every override must call `super()` and append.
- **`web.assets_frontend`.** A, B and C each add their own files. CSS must be scoped to the module's own root class under `.pbme-home`.
- **`hr.payslip` input seams.** Only C, within this step. They also meet the leave/time team's work (below).
- **Approvals inbox.** A adds keys for details and letters; C adds a reimbursement key if it needs one. Each ships its own process record.

## 9. Collision list with the other teams building now

| Other team | Their likely files | What Step 6 needs there | Plan |
|---|---|---|---|
| Leave and time (leave types, accrual, `pb_clock`, shifts) | `pb_timeoff`, `pb_clock`, `pb_schedule`, `pb_ess_workforce`, `pb_attendance_flow`, `pb_today`, `pb_me_team`, `pb_workforce_payroll_bridge` | **No edits.** B calls `pb.ess.workforce.get_my_leave` (`pb_ess_workforce/models/ess_workforce.py:445`) and links to `/my/work/leave/apply` (`pb_ess_workforce/controllers/portal.py:162`) and `/my/holidays` (`pb_timeoff/controllers/portal.py:75`). C adds a new override of `hr.payslip._get_formula_input_values` / `_application_resolve_inputs` / `_create_payslip`; if they feed late minutes or time off in lieu to pay through the same methods (e.g. in `pb_workforce_payroll_bridge/models/hr_payslip.py`), the overrides stack. | Agree that `get_my_leave`'s return shape stays stable. Seam test at merge: a payslip carrying both a claim and their new time inputs. |
| Job changes, contracts, pay scales | `pb_contracts`, `pb_workforce*`, `pb_hr_workforce`, `pb_contract_lifecycle`, `pb_decision_room`, and possibly `pb_hiring` (`requisition.py`, `requests_p3.py`, `hr_job_ext.py` for hiring freeze / plan → open roles / would rehire) | **No edits.** B's internal hire must END in their "Change job" flow (new job, manager, pay, start date on the existing person). A's salary certificate reads the agreed wage (`hr.version` / contract), read only. | Agree one entry point the internal offer calls, e.g. "start a job change for employee X from offer Y". Until it exists, B leaves a "job change to do" for HR. B does all Hiring work in `pb_hiring_internal` (inherit), never in `pb_hiring` files. |
| Performance, surveys, people reports | `pb_lifecycle` (letters, cases, review forms, disciplinary), `pb_goals`, `pb_pip`, growth, `pb_explorer` | **No edits.** A's certificates inherit `pb.letter.template` (`selection_add` on the TEMPLATE only), and override `pb.hr.letter._placeholder_values` / `_file_in_vault` / send from `pb_me_letters`. | Tell them A depends on the signatures of `action_generate`, `_placeholder_values`, `_file_in_vault`, `_action_send_now` (`pb_lifecycle/models/letter.py:140-345`) and the report `pb_lifecycle.action_report_hr_letter`. If they need to change those, they say so first. |

## 10. Owner questions (plain words; recommended option first)

**Q1. Family members and tax.** When an employee adds or changes a family member (for example a new baby) on My Payobook and HR approves it, should it also change the family tax relief in their pay? Today only Vietnam uses family members for tax, and the tax part of this programme is on hold.
- (a) **Recommended:** HR sees the change and approves it. For Vietnam it then shows as "waiting for HR to confirm for tax", and pay only changes when HR ticks it. Nothing reaches pay by itself. *Cost:* one extra tick for HR per change.
- (b) Once HR approves, it counts for Vietnam tax from the next pay run. *Faster, but a wrong approval changes take-home.*
- (c) Employees can see their family members but not change them, until the tax work restarts. *Simplest, but the most common request stays with HR.*

**Q2. Salary and employment certificates.** When an employee asks for a certificate, should it come out at once or wait for HR?
- (a) **Recommended:** the employment certificate (no pay figures) comes out at once as a PDF. The salary certificate (shows their agreed monthly salary) waits for one HR click.
- (b) Both come out at once. *Fastest; nobody checks the pay figure before it goes to a bank.*
- (c) Both wait for HR. *Safest; HR still handles every request.*

**Q3. Consent for personal data.** How should employees give their consent?
- (a) **Recommended:** the first time they open My Payobook after go-live, they read the company's notice and press "I have read and agree". It is asked again only when the company changes the notice. HR sees who has and has not agreed, and records paper consent for people with no login. *Cost:* one screen, once.
- (b) A card on the home page they can do any time; nothing waits for it. *Smoother, but many people never do it, so audits show gaps.*
- (c) No screen at all; HR records signed paper forms. *Least change for employees; most work for HR.*

**Q4. Applying for roles inside the company.** When an employee applies for another role, when is their current manager told?
- (a) **Recommended:** only when an offer is about to be made. Until then only the hiring team for that role sees the application.
- (b) The moment they apply. *Open, but people may not apply for fear of upsetting their manager.*
- (c) The employee must tick "I have told my manager" before they can apply.

**Q5. PayAI for employees.** What should PayAI answer on My Payobook?
- (a) **Recommended:** questions about the company's own policies (from the handbook and policy files HR uploads), plus the person's own leave left and last payslip. It always shows which policy it used. When it cannot answer, it offers "Ask HR" with the question filled in. It is switched on per customer, with a daily limit, because every question costs money on that customer's AI account. *Rize would need its AI account key added first.*
- (b) Policy questions only, no personal figures. *Simpler and safer; employees still open the leave and pay pages themselves.*
- (c) Also general questions (for example "how is overtime usually paid in Vietnam"). *More helpful, but answers may not match the company's own rules.*

**Q6. Paying back expense claims and trip advances.** How should approved claims be paid back, and what happens to unspent trip cash?
- (a) **Recommended:** each company chooses "pay claims in the next pay run" or "finance pays them". In the pay run, a claim is a separate untaxed line on the payslip, paid once. When a trip's claims are settled, any unspent advance is taken back from the next pay as a deduction. The employee sees the figure first, and their take-home never drops below zero.
- (b) Always through the pay run, for every company. *Simplest; companies that pay expenses from finance today must change how they work.*
- (c) Finance always pays claims; the pay run only takes back unspent advances.

Design defaults applied without asking (from earlier owner rulings):
- An employee's own bank change uses the same bank approvers as the Updates sheet: one second person, never the proposer, with the named approvers on rize (UPDATES D13–D15).
- Yearly claim limits follow the training allowance: a company figure per category per year, a per-person figure that wins over it, and a refusal that shows "limit, used, left" unless the company allows going over with approval.

## 11. Tests, translations, versions (starting points)

**Tests to read or extend:**
- `pb_me_portal/tests/test_portal_accounts.py` (share-user smoke, `:412-425`), `test_t3b_photos.py`
- the pb_me_portal home test (short texts must be in pb_me_portal's `.po`, which is why tile text is kept out of the registry)
- `pb_bank_ocr/tests/`
- `pb_lifecycle` letter tests
- `pb_hiring` portal / referral tests
- `pb_payroll_ai_insights/tests/test_egress.py`
- `pb_loans/tests/` (incl. `test_wdgap_pr_merge_seams.py`)
- `pb_me_expense/tests/`
- `pb_trip_payroll_bridge/tests/` (PRD-4: errors at baseline)

**Browser:** walk every new portal page as a portal login (PRB-W5) on `http://127.0.0.1:<port>` (W2A-6).

**Translations:** vi + id for every string. Keep sentences on one line in OWL/QWeb (PRD-3). Check with `fetch('/vi/my/...')`, not a screenshot (W2A-8).

**Manifest versions today:**

| Module | Version |
|---|---|
| pb_me_portal | 19.0.3.7.0 |
| pb_bank_ocr | 19.0.1.2.2 |
| pb_employee_vault | 19.0.1.5.0 |
| pb_records | 19.0.1.10.1 |
| pb_updates | 19.0.1.8.0 |
| pb_approval_config | 19.0.1.9.0 |
| pb_lifecycle | 19.0.1.20.0 |
| pb_ask_hr | 19.0.1.3.0 |
| pb_hiring | 19.0.2.23.8 |
| pb_payroll_ai_insights | 19.0.3.13.0 |
| pb_payai_actions | 19.0.4.2.2 |
| pb_learn | 19.0.20.8.8 |
| pb_training | 19.0.1.14.0 |
| pb_training_payai | 19.0.1.0.0 |
| pb_me_expense | 19.0.1.2.0 |
| pb_expenses_hub | 19.0.1.2.0 |
| pb_business_trip | 19.0.1.4.0 |
| pb_me_trip | 19.0.1.0.0 |
| pb_trip_expense_bridge | 19.0.1.0.1 |
| pb_trip_payroll_bridge | 19.0.1.2.0 |
| pb_loans | 19.0.1.1.0 |
| pb_hr_payroll_formula | 19.0.1.167.0 |
| pb_comp_ben | 19.0.1.8.0 |
| pb_pay | 19.0.3.8.0 |
| biz_approval_workflow | 19.0.1.8.0 |
