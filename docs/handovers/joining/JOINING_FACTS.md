# JOINING — verified plumbing facts (do not re-derive)

Read at `c4564f127` (origin/19.1, 2026-11-27) with `git show` / `git grep`. Paths are repo-relative; `:N` is a
line at that revision. If a line has drifted, search the identifier — the identifier is the fact, the line is a hint.
Odoo 19, custom modules flat at the repo root.

## F0. Repo state traps

- The owner's main checkout `/Users/adity/Documents/GitHub/gitlocal` (branch `19.1`) is **182 commits behind and
  1 ahead** of `origin/19.1`. `pb_new_hire/` does not exist on disk there. **Never build in that checkout.**
  Build in a fresh worktree from `origin/19.1`.
- The one local-only commit is `840036012` ("Release: one script"): it adds `tools/release.sh` and
  `ops/pb_release.sh`. They are NOT on `origin/19.1`. Cherry-pick it into the build branch (it touches only
  `tools/`, `ops/`, `CLAUDE.md`, docs) or the release step has no script.
- The design pack (`docs/handovers/joining/*`, `docs/design/joining-portal-poc.html`) is untracked in the main
  checkout. Copy it into the build branch in the first commit.
- Module versions at this revision: `pb_hiring 19.0.2.23.9`, `pb_new_hire 19.0.1.8.1`, `pb_filter_kit 19.0.1.5.1`.
- Translation files are named `i18n/vi_VN.po` and `i18n/id_ID.po` (not `vi.po`/`id.po`).

## F1. Hiring: the offer and the "signed" seam (`pb_hiring`)

- `pb.hiring.offer` — `pb_hiring/models/offer.py:82` (mail.thread, activity mixin, `biz.approval.chain.mixin`).
- States (`hiring_common.py:380` `OFFER_STATES`): draft, submitted, manager_ok, hr_ok, sent, accepted, declined,
  **signed**, joined, dropped, refused. `join_status` (`joining_p6.py:854`; `JOIN_STATUS` `hiring_common.py:402`):
  pending, changed, confirmed, dropped.
- Dates: `start_date` (offer.py:122, required), `expected_join_date` (joining_p6.py:851), `joined_on` (:853),
  `signed_on` (offer.py:161).
- Links: `applicant_id` (:107), `requisition_id` (:104), `company_id` (related to requisition, stored, :197),
  `reporting_manager_id` (:125), `job_title` (:121), `location` (:124), `buddy_employee_ids`,
  `laptop_prefs_json` (joining_p6.py:866-869), outputs `employee_id/contract_id/case_id/login_user_id` (:182-192).
- **The offer has no job/department/country/contract-type/probation fields.** Those come from the requisition:
  `department_id` (requisition.py:130), `country_id` (:136), `reporting_manager_id` (:150), `recruiter_id` (:152),
  `job_id` (:193). Wage = `_basic_line()` (offer_closure.py:313), read the same way by
  `pb_new_hire/models/hiring.py:212`.
- **`_on_signed(kind, label, quiet=False)`** (`joining_p6.py:998`) is THE seam. It creates the
  `pb.hiring.offer.document` row, sets `expected_join_date` + `join_status='pending'`, runs
  `leg(_move_to_post_offer)` and `leg(_lay_out_prejoin)`, mails the manager. `hooks_p8.py:176` already overrides
  it (precedent): `super()` first, then extra work wrapped in `leg()` (`hiring_common.py:533`).
  **`quiet=True` is a migration replay** (`migrations/19.0.2.5.0/post-10_joining.py:74`) — do nothing then.
  All three ways into signing end here: `action_record_signed` (offer.py:768, joining_p6.py:991), e-sign provider
  completion (esign.py:170), facade `_act_record_signed` (facade_p6.py:551).
- `action_change_join_date(new_date, reason, source, by_name)` — joining_p6.py:1064.
  `action_did_not_join(reason, note, source, by_name)` — :1102. `action_confirm_joined(joined_on)` —
  offer_closure.py:70 (internal candidates diverted at `pb_hiring_internal/models/offer.py:172`).
- Patch-from-another-module precedent: `pb_new_hire/models/hiring.py:706` ("Never an edit in `pb_hiring`"),
  context key `NH_JOIN_CTX='pb_nh_joining_employee_id'`.
- Silencer context keys: `pb_no_automation`, `pb_no_stage_log`, `install_mode` (RC95).

## F2. Hiring: applicant, papers already collected

- Applicant: `partner_name`, `email_from`, `partner_phone`, `pb_requisition_id` (hr_applicant_ext.py:30),
  `pb_lang` (forms_p2.py:845), `pb_country_id` (:844), `pb_internal`
  (`pb_hiring_internal/models/applicant.py:66`).
- Papers page `/hiring/d/<token>`: `pb.hiring.docreq` (docreq.py:75; states sent/partial/complete/expired) with
  `pb.hiring.docreq.item` (:429; `name, required, received_at, attachment_id`). Templates
  `data/hiring_doc_templates.xml` (noupdate): doc_id, doc_degree, doc_payslip, doc_bank, doc_photo, doc_tax.
  Files are `ir.attachment` on `pb.hiring.docreq`, no access token. **Hiring holds files only — never typed
  bank/ID/tax values.**
- pb_new_hire already maps those files to step-5 items: `_offer_items` (pb_new_hire/models/hiring.py:178),
  `_template_names` (:162), `_received_for(d)` (:317-331) → `{identity|degree|tax|bank: {on, label}}`.
- "Before they join": `pb.hiring.prejoin` (joining_p6.py:209; kinds buddy/laptop/chat/todo; states
  open/done/skipped/cancelled; `due_date` computed from `expected_join_date` + offset), laid out once by
  `_lay_out_prejoin` (:1041). Laptop answer page `/hiring/l/<token>` (`controllers/joining_pages.py:154-197`).
  Drawer payload `facade_p6._joining_payload` (:135).

## F3. Hiring: public token pages (the pattern to clone)

- Routes: `controllers/token_pages.py` (`/hiring/f|d|o/<token>`), `controllers/joining_pages.py`
  (`/hiring/b|l|w/<token>`). GET = `type='http', auth='public', website=True, sitemap=False`; POST adds
  `methods=['POST'], csrf=False` (the joining portal must use `csrf=True` — see handover).
- One template renders every status (ok/invalid/closed/used/thanks) so a wrong key and a spent one look alike.
  Problems travel as `?problem=<key>`; success as `?done=1`; handlers catch everything; never pass `request`
  as a render key (R4); QWeb and mails call no private methods — pass plain values from the controller (RC49).
- Templates call `web.frontend_layout`: `views/joining_pages.xml` (`pbjn_icon` :14 inline-SVG icon set,
  `hiring_laptop_page` :127). **Best visual precedent: the laptop page** — 360 px first, visitor language,
  one template per status.
- Public-page assets go in `web.assets_frontend` (explicit file lists, no globs). SCSS precedents
  `static/src/scss/interviewer_page.scss:16` (`.pbiv`), `joining_pages.scss:9` (`.pbjn`). Those pages use accent
  `#4F46E5` — **do not copy that colour**; the brand is `#5A4BB0`. Public-page colours are literals (R39).
- On public pages `display:` beats `[hidden]` → add `.root [hidden]{display:none!important}` (RC72).
- Language: `_laptop_env` (joining_pages.py:144) → `request.env(context=dict(..., lang=lang))`, words from `.po`,
  template gets `page_lang` and sets `t-att-lang`.
- Uploads: read `MAX+1` bytes (token_pages.py:38/:177); allow-list `UPLOAD_MIME_OK` (hiring_common.py:520-529).
- Rate-limit precedents (all in-memory, one-process server): `pb_lifecycle/controllers/token_pages.py:35-55`
  (bad-link counter 10 / 600 s per address), `pb_tenancy/controllers/support.py:13-63` (5/min per IP),
  `pb_hiring/controllers/request_pages.py:32-56`.
- Hashed short-code precedent: `pb_clock/models/clock_connector.py:20,57-58,105-107` (`pairing_hash` +
  `pairing_until`); `pb_tenancy/models/support.py:74` (sha256 `token_digest`, expiry, single use);
  `hmac.compare_digest` at `pb_hiring/models/calendar_notifications.py:108`. **No email/SMS one-time code exists
  anywhere; `consteq` is unused; there is no shared OTP mixin.**

## F4. Hiring hub and People hub tabs

- Hiring hub: `pb_hiring/static/src/js/hiring_hub.js` — `config.lenses[]` at :69-108; extension registry
  `HIRING_LENSES = "pb_hiring_hub_lens"` (:51); `PROBE = {model:'pb.hiring', method:'can_open'}` (:48).
  **Precedent to clone:** `pb_hiring_internal/static/src/js/staff_moves.js:108-116` —
  `registry.category(HIRING_LENSES).add("staff_moves", {key, icon, label, title, Component, groups:[…],
  probe:{model, method:"can_open"}}, {sequence: 40})`. Extra tabs render after Set-up.
- People hub: `pb_people_hub/static/src/js/people_hub.js` — `PEOPLE_LENSES = "pb_people_hub_lens"` (:102).
  Precedent `pb_onboarding/static/src/js/onboarding_palette.js:44-52` (`newjoiners`, icon `userCheck`, label
  "Joiners", `groups: LIFECYCLE_GATE`, `feature:"lifecycle"`, `{sequence: 52}`). Other sequences: Contracts 38,
  Assets 50, Exits 56, Family 88.
- A tab receives `{embedded: true, ...props}` (`pb_hub/static/src/js/hub_shell.js:523/610`). A tab's `probe`
  hides it unless the call returns truthy; a group change needs an `orm_signaling` bump (RC11). A new tab in an
  existing hub needs no `pb.sidebar.item`.
- ⌘K row: `registry.category("pb_hub_palette").add(id, {id, label, sublabel, icon, groups, requires, action:
  {xmlid, lens}, keywords}, {sequence})` — `onboarding_palette.js:58-69`; sequences ≥ 2500 are free.
- Hiring groups (`pb_hiring_security.xml`): `group_hiring_user` Recruiter (:40), `group_hiring_manager` Talent
  lead (:48), `group_hiring_admin` Head of hiring (:59). Offer rules: `rule_offer_own` (:361), `rule_offer_all`
  (:368), `rule_offer_seat` (:442). **An HR person with no hiring group sees almost no offers** —
  `pb_new_hire` searches offers in the user's own rights (`hiring.py:148,253`).

## F5. The board precedent (New joiners) and shared UI

- Board to model on: `pb_onboarding/static/src/js/onboarding_board.js` (`PbOnboardingBoard`), template
  `static/src/xml/onboarding_board.xml`, SCSS `static/src/scss/onboarding.scss` (root `.obb`).
  Layout top→bottom: lock card (xml:26-33), header buttons (38-62), `QuietGlance` (69-72), `QuietSteps` (80-84),
  `PbFilterLayout` (91-234) wrapping empty/error states (93-129), card grid `obb-grid` / `pbim-panel obb-card`
  (132-225), "Show N more" (227-233); drawer `.obb-scrim > .obb-drawer` (242+).
- Server: `pb.onboarding` AbstractModel + `pb.filter.mixin` (`pb_onboarding/models/pb_onboarding.py:46-48`):
  `get_board()` (:95), `get_joiners_page(filters, search, sort, offset, limit)` (:298), `_row()` (:343-386),
  `get_joiner(case_id)` (:390), `_pbf_spec` (:195-259), `_step_domains` (:185-193). A refused reader gets
  `allowed:false`, not an access error (:61-70).
- Narrow-right precedent (system-rights read scoped to own companies, every id re-checked):
  `pb_new_hire/models/joiners_board_p8.py:58-76`, group `pb_new_hire.group_joiners_board` implied by
  `hr.group_hr_manager` (`pb_new_hire/security/joiners_board.xml:7-13`).
- **QuietGlance / QuietSteps are QWeb `t-call` templates** — `pb_import_kit/static/src/xml/quiet_board.xml:26-57`.
  Params: `qGlance=[{key,n,label,tone:''|'amber'|'rose'|'green',run,zero?}]`, `qGlanceOn`;
  `qSteps=[{key,n:'01',title,countLabel,count,sub,flag,flagTone,on}]`, `qStepsLabel`, `qStepPick(key)`. The `q`
  prefix is mandatory. Usage: `onboarding_board.xml:69-84` + `onboarding_board.js:169-266`.
- Filter kit (`pb_filter_kit`): `useFilterKit({model, onChange, noun})` (`static/src/js/filter_kit.js:1009`),
  `<PbFilterLayout kit coach searchPlaceholder>` (`filter_components.js:361`), server `pb.filter.mixin`
  (`models/filter_mixin.py:52`; hooks `_pbf_model/_pbf_spec/_pbf_builtin_views/_pbf_sorts/_pbf_search_fields/
  _pbf_base_domain`).
- **No shared drawer is in use**; every board draws `<m>-scrim > <m>-drawer` (copy `onboarding_board.xml:242`).
  A toast is hidden behind an open drawer — also show the message inline (`joiners_board.js:111-118`).
- Tokens: `pb_import_kit/static/src/scss/import_tokens.scss` — `$pbim-primary #5A4BB0` (:9), hover `#4A3D96`
  (:10), soft `#EDEAF8` (:17), line `#E2E8F0`, muted `#64748B`, bg `#F5F6FA`, semantic green/rose/amber/cyan/
  slate/teal/pink each with `-soft` (:32-46), radius `14/10/18/999px` (:49-52), shadows (:53-54); CSS custom
  properties `--pbim-*` from mixin `pbim-root-vars` (:58-94). Font Inter (self-hosted,
  `pb_import_kit/static/fonts/InterVariable.woff2`); the studio adds Manrope for display.
- Classes (`pb_import_kit/static/src/scss/import_kit.scss`): `.pbim-btn` + `primary|outline|ghost|danger`,
  `.pbim-btn-sm` (:156-168); `.pbim-badge` + `ok|info|warn|err|muted` (:133-139); `.pbim-chip` (:89);
  `.pbim-seg/.pbim-segbtn` (:150-153); `.pbim-panel` (:74), `.pbim-card` (:73); `.pbim-note` (:175),
  `.pbim-empty` (:176), `.pbim-busy/.pbim-spin` (:179-180); `.pbim-h1/.pbim-sub/.pbim-eyebrow` (:67-70).
  Page root `class="pbim pbim-page …"`.
- Icons: `pb_import_kit/static/src/js/import_icons.js` — `IC` map (name → Lucide inner path, :6-375),
  `ic(n, s=16)` (:382-387) returns markup; **an unknown name silently renders a tick** (test for it). Add an icon
  = one line in `IC`. In templates: `<t t-out="ic('lock',30)"/>`. Public QWeb pages cannot call `ic()` — inline a
  closed `<svg>` set per page (`pb_hiring/views/joining_pages.xml:14-34`).
- Toasts: `useService("notification").add(msg, {type})`.

## F6. Add employee studio (`pb_new_hire`)

- Client action `pb_new_hire.action_new_hire_studio`, tag `pb_new_hire_studio`, path `add-employee`
  (`views/studio_action.xml:6-10`). Root component `NewHireStudio` (`static/src/js/new_hire_studio.js:121`),
  template `pb_new_hire.Studio`; CSS prefix `pbnh-` on root `.pbim.pbnh`; grid 236px / fluid / 328px.
- **No stored draft.** `pb.new.hire` is an AbstractModel (`models/studio.py:118`); the draft lives in the
  browser (sessionStorage). `DRAFT_KEYS` (`studio.py:58-78`) is the whitelist — anything else is dropped by
  `send`. Step 5 keys: `items {key: ask|have|skip|later|number|hiring}`, `have {field: value}`, `remind`,
  `hiring_valid_until`.
- Server calls: `load`, `team_defaults`, `places`, `decides`, `details_options` (step 5), `hiring_offers`,
  `offer_draft`, `send(draft, files)`, `withdraw`, …
- Pipeline: `send` (`studio.py:936-981`) → `_validate` → `_validate_docs` → `_values` + `_values_docs` →
  `_held_files` → `pb.newhire.proposal.propose('employee', …, payload={'values': vals})`. Payload must be
  JSON-plain and is re-validated on replay (NH8). Approval → `_apply_employee` → `create_employee` override
  (`models/create_ext.py:166-201`) → `pb.new.hire.legs.run`.
- Legs (`LEG_ORDER`, `models/welcome_legs.py:50-64`), each in its own savepoint, a failed leg never undoes the
  hire: clock, week, own_fields, **details** (`docs_legs.py:104`, one `employee.write`), **papers**
  (`docs_legs.py:162`, `pb.employee.document` via `pb.people.vault_upload_batch` :179), **hiring**
  (`hiring.py:598`, copies Hiring files; `_file_copy` :539-554), **asks** (`docs_legs.py:194`), login, case,
  buddy, equipment, **hiring_close** (`hiring.py:664-681`), letter, invite.
- From Hiring: `hiring_offers` (`hiring.py:253`, domain `_offer_domain` :148), `offer_draft(offer_id)`
  (:268-313) returns `{ok, draft, offer, wage_note}`; the browser's `bringAcross`
  (`new_hire_studio.js:575-610`) patches the whole draft dict in. The received-file pattern: context key
  `RECEIVED_CTX`, `_detail_items` override (:334-385) sets `item['received']={on, line}`, `_values_docs`
  override (:419-440).
- Bank always goes to a second person: `_pb_send_bank` (`pb_people_advanced/models/people_wizards.py:157-222`)
  → `pb.bank.change.request._pb_hold_new_hire` (`pb_bank_ocr/models/pb_bank_import_hold.py:164`), created as
  the hire's sender (NH57). `_pb_never_decide` = proposer + the account holder's user.
- Studio gate: `require_hr` (`pb_people_advanced/models/newhire_approval.py:43`).

## F7. Step 5 catalogue — the ONE definition of what a person is asked

- `pb_new_hire/models/studio_docs.py`. Item shape (`item()`, :236-244): `key, group, icon, label, sub, need,
  can_ask, ask_why_not, can_have, can_skip, fields[{name,label,kind,required,hint,options}],
  upload{category_id,needs_expiry,label}|False, ask_url, merged, card_url, can_number, default`.
- Items (`_detail_items`, :222-350) and the hr.employee fields they write:

| key | fields | need | notes |
|---|---|---|---|
| `personal` | `birthday`, `sex`, `private_street`, `private_city`, `private_phone` | optional | |
| `emergency` | `emergency_contact`, `emergency_phone` | optional | |
| `id_number` | `identification_id` (required) | first_pay | merged with the country's ID paper (`pb_employee_vault.cat_id_document`, **requires an expiry date**, NH56). `ID_TWIN` (:75): VN also writes `vietnam_citizen_id`, SG `singapore_nric_fin` |
| `tax_number` | VN `vietnam_tax_code` (10/12 digits), ID `pb_npwp_number` (15/16), IN `pb_in_pan_number` | first_pay | merged with the tax paper for ID/IN (`pb_me_tax.cat_tax_paper`) |
| `tax_status` (ID) | `pb_id_ptkp_status` ∈ TK/0…K/I/3 | joining | |
| `tax_regime` (IN) | `pb_in_tax_regime` ∈ new/old | joining | |
| `tax_fund` (SG) | `pb_sg_shg_fund` ∈ cdac/ecf/mbmf/sinda/none | joining | |
| `insurance` | ID `pb_bpjs_employment_number`, `pb_bpjs_health_number`; VN `vietnam_social_insurance_number`; IN `pb_in_uan_number`, `pb_in_esi_number` | optional | `can_ask=False` today ("kept by HR", :323-324) — the portal opens it, see handover |
| `bank` | F8 | first_pay | |
| `paper-<cat_id>` | file only | per `pb.new.hire.paper` (`data/papers.xml`) | askable only if the category is `ess_uploadable` (:338-342) |

- Country papers (`data/papers.xml`): VN Citizen ID card, health check, certificate; ID KTP, NPWP card, Family
  card, certificate; IN Aadhaar card, PAN card, certificate; SG NRIC or work pass, certificate; MY MyKad or
  passport, certificate.
- Tax kinds: `pb_me_tax/models/tax_rules.py` — `SUPPORTED` VN/ID/IN/SG (:26), `KINDS_BY_COUNTRY` (:39-44),
  `NUMBER_FIELD` (:50-54), `CHOICE_FIELD` (:57-61), `PTKP/REGIMES/SG_FUNDS` (:70-96), `normalise_number` (:107).
  **No tax kinds for MY; TH/KH cannot be on a contract; no AU/NZ tax.** The studio can only pick the countries
  its scheme list allows (`studio.py:139-150`).
- Checks: `_check_value` (:512-539), `_doc_choices` (:483), `_validate_bank` (:628), `_bank_values` (:644),
  `SECRET_FIELDS` (:67-71, masked for the approver). Files in `send`: `files=[{key, name, mime ∈
  png|jpeg|pdf, data(base64), issue_date, expiry_date}]`, 10 MB each, 50 MB total (:542-566).
- `have` values land in `vals['pb_nh_details']` (+ top-level bank keys); `_leg_details` re-checks and writes
  only `DETAIL_FIELDS` present for that country (`docs_legs.py:46-53,104-140`); `CONTRACT_COPY` (:59-65).

## F8. Bank format by country — the ONE definition

- `pb.bank.format` — `pb_bank_ocr/models/bank_formats.py`. `FORMAT_CODES` VN, ID, IN, SG, MY, TH, KH, AU,
  `other` (:52-53); `RULES` (:61-76); `spec(code, banks)` (:225-261); `specs` (:264); `choices` (:152);
  **`check(code, values) -> (clean, problems)`** (:281-337); `first_problem` (:340); `bank_from_code` (:355).
- Value keys (`BANK_CHECK`, `studio_docs.py:81-83`): `bank_format, bank_name, bank_branch, bank_code,
  branch_code, account_number, account_holder, bank_swift`.
- Rules: VN 6–19 digits; ID 8–16 digits + optional 3-digit bank code; IN 9–18 digits + required IFSC; SG 7–14
  digits + required 4-digit bank code + optional branch; MY 7–17 + SWIFT; TH 10–12 + optional branch; KH 6–16 +
  SWIFT; AU 5–9 + required BSB; other 5–34 chars. ID/SG bank code auto-fills from `pb.bank.registry`.

## F9. Why a login-free typed page was a non-goal before — each must be answered

`NEWHIRE_LEDGER.md` D8 (:79-80), `NEWHIRE_P3B_HANDOVER.md:27-31`, `NEWHIRE_FACTS_ONBOARD.md:13-19,297-357`:

1. Existing token pages never expire and have no rate limit or CSRF.
2. The `/my` write entry points refuse anyone not signed in as that employee (`pb_portal_create`,
   `pb_portal_start` — `pb_bank_self_service.py:266-271`).
3. A cloned token page would need new sudo entry points and would rebuild five `/my` forms.
4. Who proposed the bank account would be undefined, which the second-person rule needs.

The owner reversed D8 on 2026-11-27 (one-time code). The handover's architecture answers 1–4; keep it that way.

## F10. Mail, language, signatures, journeys

- "This database cannot send mail" = no active `ir.mail_server`: `pb.new.hire.invite._mail_on()`
  (`pb_new_hire/models/invite.py:90-92`). **Three of the five live sites have no mail server on purpose.**
- Candidate emails: `pb.hiring.message.template` (journey.py:613; `key`, translated `subject/body`), sent ONLY
  through `env['pb.hiring']._mail_candidate(key, applicant, values=…, record=…, lang=…)` (comms_p8.py:265;
  returns sent/dry/mail_off/no_email/no_template/missing). Keys added by `selection_add` (comms_p8.py:112);
  seeds `EMAIL_ORDER`/`NEW_EMAILS` (comms_i18n_p8.py:32-98); never write `False` to a translated field
  (RC92/RC93); seeds must filter to installed languages (RC30). Sender `_sender(company)` (facade_p3.py:40).
- Built-in automation rules are tuples in `BUILTINS` (automation_p8.py:121): `(key, sentence, switch param,
  default, email_key, why_locked)`; switch `_act_builtin_switch` (:967); `flag(env, param, default)`.
- No SMS dependency anywhere; WhatsApp exists only for interview reminders (`pb_hiring/models/whatsapp.py`).
- **No on-page signature capture exists**; no `sign` module. PDF merge helper: `odoo.tools.pdf.merge_pdf`.
- `pb.journey.case.employee_id` is `required=True` (`pb_lifecycle/models/journey_case.py:54-55`) — the welcome
  checklist **cannot** start before the employee exists. The pre-hire list is `pb.hiring.prejoin` (F2).
- Existing post-hire welcome link (`pb_new_hire/models/invite.py`): sign-up link → `/my/welcome` (`auth='user'`).
  It stays as is.

## F11. Tests, translations, white-label tooling

- Hiring test bases: `OfferCase` (`pb_hiring/tests/test_offer.py:44`; `_offer()` :99, `_complete_documents`
  :118), `JoiningCase` (`tests/test_joining_p6.py:35`; **`_signed(start=None)`** :52 takes an offer all the way
  to signed), `TestRecruitJoiningPages(HttpCase, JoiningCase)` (:581, `url_open`).
- Studio test bases: `NewHireCommon` (`pb_new_hire/tests/test_new_hire.py:17`; `studio()`, `fast_lane()`,
  `draft(**kw)`, `approve()`, `hires()`, `assert_hire()` :104-152), `DocsCommon` (`tests/test_docs.py:17`;
  `docs_draft(items, have)`, `file(key)`).
- Run: `odoo-bin -c <conf> -d <db> -u <modules> --test-enable --test-tags /<module> --stop-after-init`; tags
  `@tagged('post_install','-at_install','<tag>')`. Known baseline: pb_hiring 3 data-dependent failures on a
  payobook clone (RC47), clean on a rize clone. Rule: run every touched module's suite before and after; accept
  only the same failures.
- Static tests to clone: `pb_new_hire/tests/test_static.py` — S1 no vendor name on screen (:47), S2 icons exist
  (:71), S3 no emoji (:85), `_t` import exactness (:90-98), every `_t` string is in the `.pot` (:100-116).
- PO rules: every entry needs, in order, `#. module: <m>`, `#. odoo-python` or `#. odoo-javascript`,
  `#: code:addons/<m>/<path>:0`. Export with `odoo-bin i18n export`; append `.po` entries as plain text, never
  `polib.save` (NH87). JS: `import { _t } from "@web/core/l10n/translation";` and literal strings only; literals
  in template expressions are not extracted — route them through a getter.
- `noupdate="1"` records are not reloaded on upgrade; changes need a migration (RC41). An act_window handed to
  `doAction` needs `'views': [[False,'form']]` (RC13).
