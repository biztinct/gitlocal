# FILTER programme — screen inventory

Read-only audit, 2026-10-31. Every Payobook OWL cockpit that shows a multi-record
list and must adopt the shared filter panel (`pb_filter_kit`). Nothing in this
file is a design decision; it is the plumbing each conversion handover starts from.
Companion: `docs/handovers/filter/FILTER_LEDGER.md` (conventions + gotchas).

**Reference (already converted — the shape every row is compared against):**
`pb_people/models/pb_people.py:222-353` (`_pbf_model/_pbf_screen/_pbf_base_domain/_pbf_search_fields/_pbf_sorts/_pbf_spec/_pbf_builtin_views`),
paged `get_roster_page` `:395-414` via `self.pbf_domain(...)`;
`pb_people/static/src/js/people.js:42-46` (`useFilterKit`), `:135-156` (`loadPage`);
`pb_people/static/src/xml/people.xml:61` (`<PbFilterLayout kit="kit" coach="'pe-filters'">`).

**Kit facts that shape the candidate sections** (`pb_filter_kit/models/filter_mixin.py`):
`LIST_TYPES` = many2one/selection/char/choice (`:40`); `_pbf_resolve` walks dotted
paths **only through many2one hops** (`:100-115`) — a one2many/many2many hop drops
the section; date/number sections `:230-250`; `pbf_domain` `:263`. One
`_pbf_model()` per screen — a screen with several row models needs one thin
facade per model (or a `kind`-switched spec).

Learn plumbing: anchors live in `pb_learn/static/src/anchors.json` (`product`
map keyed by `data-coach` name, each with `screen` + `file`);
`pb_learn/static/src/engine/screens.js` is a practice REPLICA that redraws many
product screens by anchor name (not only Pay Run); lessons in
`pb_learn/static/content/learn_content.json`. "Lessons follow screen changes" is
a standing rule — a filter-area change on a replicated screen is two edits.

---

## 0. Summary — 35 candidate screens

| # | Module · screen (as the user sees it) | Action tag | Kind | Records model | Cap · paged? | Filter-area coach | Learn replica? | Effort |
|---|---|---|---|---|---|---|---|---|
| 1 | pb_contracts · Contracts | `pb_contracts` | card list + 4-step strip | `hr.contract` | 240 · no | `ct-filters` | yes | M |
| 2 | pb_contract_lifecycle · Contracts (renewals) | `pb_contractlife_board` | card grid + 4-step strip | `hr.contract` (2 searches merged) | 300 · no | none | yes | L |
| 3 | pb_probation · Probation | `pb_probation_board` | card grid + 5-step strip | `hr.employee` | 300 · no | none | yes | L |
| 4 | pb_pip · Growth plans | `pb_pip_board` | card grid + 4-step strip + open/closed | `pb.pip.case` | 300 · no | none | yes | M |
| 5 | pb_onboarding · New joiners | `pb_onboarding_board` | card grid + 3-step strip | `pb.journey.case` | 300 · no | none | yes | M |
| 6 | pb_offboarding · Exits | `pb_exits_board` | card grid + 4-step strip | `pb.journey.case` | 300 · no | none | yes | L |
| 7 | pb_lifecycle · Journeys | `pb_journeys` | card list + 3-step strip | `pb.journey.case` | 400 · no | none | no | S/M |
| 8 | pb_comp_ben · Awards | `pb_comp_ben_incentives` | table + 5-step strip | `pb.incentive` | 400 · no | none | yes | S |
| 9 | pb_hiring · Hiring › Roles | `pb_hiring_board` | card grid + 4-step strip | `pb.hiring.requisition` | 300 · no | none | yes (heavy) | L |
| 10 | pb_hiring · Hiring › Interviews | `pb_hiring_board` (tab) | list | `pb.hiring.interview` | 300 · no | none | shares `hiring` | M |
| 11 | pb_hiring · Hiring › Applicants register | `pb_hiring_board` (tab) | kanban + list toggle | `hr.applicant` | 600 · no (cursor reserved) | `hi-applicants` (wrapper) | shares `hiring` | L |
| 12 | pb_hiring · Hiring › Offers register | `pb_hiring_board` (tab) | table + 5-step strip | `pb.hiring.offer` | 200 · no | `hi-offers` (wrapper) | shares `hiring` | M |
| 13 | pb_ask_hr · Home › Ask HR | Home lens `askhr` (no tag) | step-strip board + cards | `pb.ask.hr.ticket` | 500 open + 60 closed · no | none | partial | M |
| 14 | pb_assets · Assets (register) | `pb_assets` | table + bulk bar | `pb.asset` | 400 · no | none | no | M |
| 15 | pb_rnr · Praise | `pb_rnr_board` | list + 4-step strip | `pb.rnr.nomination` | 300 · no | none | no | S/M |
| 16 | pb_vendor_access · Vendors | `pb_vendors_board` | card list | `pb.vendor` | 800 · no | none | no | S |
| 17 | pb_approval_config · Approvals (inbox) | `pb_approval_inbox` | card list + tabs + scope | `biz.approval.request` | 120 · cursor exists, unused | none | yes (42 lessons) | L |
| 18 | pb_payruns · Pay Runs | `pb_payruns` | 3-lane step board + list toggle | `hr.payslip.run` | 60 · no | `pk-divchips` | yes | L |
| 19 | pb_payslip_review · Payslip review | `pb_payslip_review` | split list + detail, one run | `hr.payslip` | none (one run) · no | `ps-chips` (steps) | yes | M |
| 20 | pb_payrun_ledgers · Full & Final / Proration / Retro | `pb_fullfinal` `pb_proration` `pb_retro` | card list (+3-step strip on F&F) | 3 models (one per tag) | 400 · no | `lg-facets` | yes | M |
| 21 | pb_hr_workforce · Payroll Report | `payroll_report_dashboard` | table, 3 tabs, one run | derived rows from `hr.payslip` | none · no | none (`rp-pick` on run select) | yes | L |
| 22 | pb_records · Records Desk | `pb_records_desk` | bulk-edit grid, WHO rail | `hr.employee` | 100/page · **yes, server-paged already** | `rd-who` (rail) | yes | M |
| 23 | pb_structures · Salary Structures | `pb_structures` | card list | `hr.payroll.structure` | 240 · no | `sr-filters` | yes | S (catalogue) |
| 24 | pb_statutory · Statutory (policies / tax / Data) | `pb_statutory` | 3 list views behind a segment | 5 models, tax = union of 2 | 120/400 · no | `st-filters` (policies only) | yes | L |
| 25 | pb_attendance_flow · Attendance Control (corrections) | `pb_attendance_flow` | 2-column board | `hr.attendance.correction` (+ engine-derived exceptions) | 80 · no | none | partial | L |
| 26 | pb_business_trip · Business Trips | `pb_trips` | 5-lane kanban + closed list | `pb.business.trip` | **none** · no | none | no | L |
| 27 | pb_timeoff · Leave Command Center (queue) | `pb_timeoff` | queue list + heatmap + balances | `hr.leave` | none · no | none (`wf-leave-queue` on panel) | partial | M |
| 28 | pb_expenses_hub · Expenses › Claims | `pb_expenses_hub` lens `claims` | native list view in a lens | `pb.expense.claim` | web client 80 · yes (native) | none | no | M |
| 29 | pb_hr_workforce_planning · Workforce Planning › Employee Forecast Detail | `wfp_dashboard` | sortable table in a tab | `wfp.employee.forecast` | none · no | none | no | M |
| 30 | pb_hr_workforce · Overtime Desk | `pb_ot_desk` | approval queue + bulk tray | `hr.overtime.request` | none · no | none (`wf-ot-queue` on panel) | partial | M |
| 31 | pb_integrations · Integrations (Connectors) | `pb_integrations` | card list | `hr.integration.connector` | none · no | `ig-filters` | yes | S (borderline) |
| 32 | pb_integrations · Integrations › Data | `pb_integrations` (view `data`) | table + tab strip | 3 models (mapping / store / rule) | 400 · no | none (`ig-data` undeclared) | no | L |
| 33 | pb_import · Import Data › Recent batches | `pb_import` | table | `hr.payroll.import.batch` | **20** · no | `im-batches` (panel) | yes | S/M |
| 34 | biz_access · Access › People | `pb_access_board` lens | master-detail list | `res.users` (composite rows) | 200 · no | none | partial | M–L |
| 35 | pb_pay · Pay review › worksheet | `pb_pay` (`pb_tab: review`) | editable table + bulk | `pb.pay.review.line` | 120/page · **yes, server-paged** (Python filter, not domain) | none (`pp-worksheet`) | yes | M |

Effort key: S = template + one model, ≤ 1 h; M = one model but steps/bulk/second
mount point to re-wire; L = several row sources, derived facets with no field, or
bulk actions tied to the filtered set.

Screens whose rows have **no records model** (cannot use `_pbf_model` as-is):
Attendance exceptions queue (#25, engine-derived), Review monthly inputs
(rejected), Payroll Report figures (#21 — rows are `hr.payslip` but every number
is computed per slip). Access › People (#34): the role facet's domain path is
**unverified** (`res.users` → role profile → groups).

---

## A. People lifecycle boards

Shared shape (verified on all eight): `AbstractModel` facade, `@api.model get_board()`,
hard cap, no paging, facets counted in Python from the capped rows then filtered
**client-side** in a `visibleRows`/`filtered` getter. No sort control. All use
`QuietGlance` + `QuietSteps` from `pb_import_kit`.

### 1 · pb_contracts · Contracts · `pb_contracts`
Action `pb_contracts/views/pb_contracts_action.xml:3-6`; also mounted by the People hub (`pb_people_hub/views/pb_people_hub_action.xml:29-33`). h1 `pb_contracts/static/src/xml/contracts.xml:16`.
- **Kind:** card list (`contracts.xml:75-96`) under a numbers line + 4-step strip (Draft / Running / Ending soon / Ended).
- **Rows:** `hr.contract`; `pb.contracts.get_board(step=None)` `pb_contracts/models/pb_contracts.py:57-148`; `ROSTER_LIMIT = 240` (`:14`, applied `:112`); not paged. Step counts are server `search_count`s (`:98-108`); `step` is a server param (`:109`).
- **Current filters** (`contracts.js:38`): `search` client (`:95,:122`); `step` server via `load()` (`:72,:167-170`) AND re-checked client-side (`:120`, `"open"` = both running steps); `structure` chip by **name string** (client `:93,:118`, chips from `read_group` `:82-91`); `dateFilter` all/month/year/custom + `from`/`to` on `date_start` (client `:102-113`). Template: search `contracts.xml:50`, date chips `:55-63`, structure chips `:65-70`.
- **Coach:** `ct-filters` `contracts.xml:44` (anchors.json `reserved: true`, screen `contracts`); also `ct-head`, `ct-kpis`, `ct-roster`. Replica `screens.js` `contracts()` `:656` draws all four. Lessons: screen `contracts` 4 refs; `ct-roster` 6, `ct-kpis` 1, `ct-filters` 0.
- **Sections:**

| key | path (`hr.contract`) | type | label | PIN |
|---|---|---|---|---|
| status | `state` | selection | Contract status | PIN |
| structure | `struct_id` | many2one | Pay structure | PIN |
| ends | `date_end` (presets future) | date | Contract ends | PIN |
| starts | `date_start` (presets past) | date | Started | |
| department | `employee_id.department_id` | many2one | Department | |
| job | `job_id` | many2one | Job position | |
| category | `type_id` (`om_hr_payroll/models/hr_contract.py:72`) | many2one | Contract category | |
| wage | `wage` (money) | number | Monthly wage | |
| trial | `trial_date_end` | date | Trial period ends | |
| company | `company_id` | many2one | Company | |
| step | choice cloning `step_dom` `pb_contracts.py:98-106` (draft / running / ending ≤30d / ended) | choice | Where it is | |

Client-derived today: `days_to_expiry`/`stepOf` (`contracts.js:143-150`) → the `step` choice.
- **Views:** All · Running `{status:[open]}` · Ending within 30 days `{step:[ending]}` · Draft · Started this month `{starts:{preset:this_month}}`.
- **Effort: M** — simplest template of the eight, but the step strip must keep server counts while becoming a `choice`, and the `"open"` double-step case (`:120,:133`) must be re-expressed.
- **Risks:** structure chips key on name (`:93`); `showingLine` mixes server counts with client `filtered.length` (`:175-185`); soft registry `pb_contracts_drawer` (`:57-60`) + deep-link `?contract=` (`:46-51`); `HubBackChip` (`:34`); replica draws `ct-filters` — re-point the reserved anchor.

### 2 · pb_contract_lifecycle · Contracts (renewals; Learn `contractends`) · `pb_contractlife_board`
Action `pb_contract_lifecycle/views/contract_lifecycle_views.xml:249-252`; h1 `static/src/xml/contractlife_board.xml:46` (same wording as #1 — this one is People › Contracts renewals, `contractlife_board.js:658-677`).
- **Kind:** card grid (`:210`) + numbers line + 4-step strip (Running / Decision needed / Being agreed / Decided) + decision drawer + 2 dialogs.
- **Rows:** `hr.contract`, **two searches merged** in `pb.contractlife.get_board()` `pb_contract_lifecycle/models/pb_contractlife.py:87-177`: (a) contracts with `date_end`, state draft/open (`:104-109`); (b) active employees whose `employee_type` ∈ `NON_PERMANENT_TYPES` (`:113-127`) filling the remainder. `BOARD_LIMIT = 300` (`:39`); not paged; re-sorted by days-left in Python (`:136`). Per row **two searches** on `pb.contract.review` (`:185-200`) → `review_state`.
- **Current filters** (`contractlife_board.js:93-100`): `q`, `kind`, `dept`, `month`, `reviewState`, `attentionOnly`, `focus`, `step` — all client (`visibleRows :160-189`; steps from rows `:265-293`). Template: search `contractlife_board.xml:126`, kinds `:136`, attention `:142`, months `:150`, review states `:160`, departments `:168`.
- **Coach:** none on the filter panel (`:122-176`). Anchors `cl-run, cl-numbers, cl-steps, cl-list, cl-drawer, cl-decide, cl-raise` (screen `contractends`). Replica `contractends()` draws 5. Lessons: screen 5 refs; each of numbers/steps/list/raise/decide 1.
- **Sections:**

| key | path (`hr.contract`) | type | label | PIN |
|---|---|---|---|---|
| ends | `date_end` (future) | date | Contract ends | PIN |
| decision | choice over `pb_review_ids.state` (REVIEW_STATES `contract_common.py:23-30`): not raised / decision needed / extension requested / evaluation running / decided / ended undecided | choice | Decision | PIN |
| department | `employee_id.department_id` | many2one | Department | PIN |
| kind | `employee_id.employee_type` (related, non-stored, searchable — `contract_common.py:50-53`) | selection | Employment type | |
| status | `state` | selection | Contract status | |
| category | `type_id` | many2one | Contract category | |
| manager | `employee_id.parent_id` | many2one | Manager | |
| starts | `date_start` | date | Started | |
| attention | choice: `date_end <= today+lead` and no review in (extension, conversion, done) | choice | Needs somebody | |

Client-derived: `needs_decision`, `urgent`, `review_state` (`:202-208`, `:240-247`); the "live review" rule (`:193-200`) is approximated by a `pb_review_ids.state` domain. Cleanest: stored `pb_review_state` on `hr.contract`.
- **Views:** All · Ending within lead days `{ends:{preset:next_60}}` (lead is a param `:96`) · Nobody has decided `{decision:[decide,upcoming]}` · Waiting to be agreed `{decision:[extension]}` · Interns & contractors `{kind:[intern,contractor,freelance,student,trainee]}`.
- **Effort: L** — two row sources with fill-the-remainder semantics; the main facet lives on another model and is derived per row; numbers/steps computed from rows in both Python and JS.
- **Risks:** `kpis.converted`/`would_raise` count other models (`:139-146`); lead-days param; drawer via soft `pb_contracts_drawer` (`contractlife_board.js:399-433`); `canRegister` gate (`:664-669`); employee fields read via sudo per row (`:216-226`) — a kit search on `employee_id.department_id` may hit field-access for lifecycle-only users; Learn replica.

### 3 · pb_probation · Probation · `pb_probation_board`
Action `pb_probation/views/probation_views.xml:342-344`; h1 `static/src/xml/probation_board.xml:47`.
- **Kind:** card grid (`:182`) with a 5-stop rail per card + numbers line + 5-step strip + drawer + 3 dialogs.
- **Rows:** `hr.employee` with `pb_probation_state in ('in_probation','extended')` (`pb_probation/models/pb_probation.py:85-89`); `BOARD_LIMIT = 300` (`:35`); not paged; sorted by days-left (`:97`). Per row: `pb.probation.review.for_employee()` (`:135`; `probation_review.py:1152-1163`), training summary, check-in red flags (`:139-146`), `review_gate` (`review_journey.py:283-287`).
- **Current filters** (`probation_board.js:79-85`): `q`, `country`, `dept`, `reviewState`, `attentionOnly`, `focus`, `step` — all client (`:159-185`; steps via `flowStepOf` `:253-260`). Template: search `probation_board.xml:116`, states `:124`, departments `:130`, countries `:138`, attention `:142`.
- **Coach:** none on filter panel (`:112-148`). Anchors `pr-run, pr-numbers, pr-steps, pr-list, pr-drawer, pr-peers, pr-choose-peers, pr-verdict` (screen `probation`). Replica `probation()` `screens.js:2857`. Lessons: screen 5 refs; `pr-numbers` 4, `pr-verdict` 3, `pr-peers` 2, `pr-steps` 2, `pr-list` 2.
- **Sections:**

| key | path (`hr.employee`) | type | label | PIN |
|---|---|---|---|---|
| trial_ends | `trial_date_end` (related to `hr.version`, read via sudo `hr_employee.py:117`) | date | Trial period ends | PIN |
| stage | choice over `pb_probation_review_ids.state` (`probation_common.py:41-49`) + `pb_probation_review_ids.pb_gate` for sign-off (`review_journey.py:54`) | choice | Review stage | PIN |
| department | `department_id` | many2one | Department | PIN |
| trial | `pb_probation_state` (`hr_employee.py:44-50`) | selection | Trial status | |
| country | `country_id` | many2one | Country | |
| manager | `parent_id` | many2one | Manager | |
| job | `job_id` | many2one | Job position | |
| joined | `first_contract_date` | date | Joined | |
| company | `company_id` | many2one | Company | |
| answers_late | choice: `pb_probation_review_ids` any [state=feedback, feedback_deadline < today] | choice | Answers overdue | |
| round | `pb_probation_review_ids.round` | number | Review round | |

No path: `training_ok`, `red_flags` (`pb.employee.checkin` has no one2many on employee), `urgent`. `pb_probation_review_id` (`hr_employee.py:52`) is a non-stored compute — not searchable; use the one2many `pb_probation_review_ids` (`:50`).
- **Views:** All in trial · Ending within 7 days · Waiting on a decision `{stage:[verdict]}` · Answers overdue · Extended `{trial:[extended]}`.
- **Effort: L** — four of five numbers and all five steps derive from per-row probes on three other models.
- **Risks:** `pb_probation_state` has `groups='hr.group_hr_user'` (`hr_employee.py:46`) — a domain on it by a lifecycle-only user can raise; NAV P3c arrival `person:<id>` auto-opens the drawer (`probation_board.js:102-107`); `pr-numbers`/`pr-steps` are the most-cited anchors.

### 4 · pb_pip · Growth plans · `pb_pip_board`
**No `ir.actions.client` record** with this tag (only `action_pb_pip_request`, `pip_views.xml:282-284`); tag registered `pip_board.js:699`, matched by `pb_talent_hub/data/pb_sidebar.xml:24`. h1 `static/src/xml/pip_board.xml:46`.
- **Kind:** card grid (`:199`) + numbers line + 4-step strip + **Open / Closed toggle** (`:57`) + drawer + 4 dialogs.
- **Rows:** `pb.pip.case`; `pb.pip.get_board(closed=False)` `pb_pip/models/pb_pip.py:127-178`; domain company + `state in/not in PIP_OPEN` (`:139-141`); `BOARD_LIMIT = 300` (`:38`); not paged; ordered `end_date`. `closed` is a server param.
- **Current filters** (`pip_board.js:100-105`): `q`, `stateFilter`, `owner` (name), `driftingOnly`, `focus`, `step` — client (`:168-191`); `closedView` server (`:126-127`, `:160-165`). Template: search `pip_board.xml:131`, states `:140`, drifting `:146`, owners `:154`.
- **Coach:** none on filter panel (`:126-163`). Anchors `gw-run, gw-numbers, gw-steps, gw-list, gw-objectives` (screen `growth`). Replica `growth()` `screens.js:2880`. Lessons: screen 5 refs.
- **Sections:**

| key | path (`pb.pip.case`) | type | label | PIN |
|---|---|---|---|---|
| stage | `state` (PIP_STATES `pip_common.py:16-24`) | selection | Stage | PIN |
| owner | `hr_owner_user_id` (`pip_case.py:85`) | many2one | HR owner | PIN |
| ends | `end_date` (`:122`) | date | Plan ends | PIN |
| department | `employee_id.department_id` | many2one | Department | |
| asked_by | `requested_by_user_id` (`:81`) | many2one | Asked by | |
| template | `template_id` (`:88`) | many2one | Plan template | |
| starts | `start_date` (`:121`) | date | Plan starts | |
| rhythm | `checkin_freq` (`:119`) | selection | Check-in rhythm | |
| seen | choice on `employee_ack` (`:139`) | choice | Seen by the person | |
| outcome | `verdict` (`:147`) | selection | Outcome | |
| overdue | choice: `end_date < today` and `state = active` | choice | Past its end date | |

Client-derived: `drifting`/`adherence` (`pb_pip.py:246-250`) and `at_risk_count` are **non-stored** computes (`pip_case.py:125-136`) → propose a stored `pb_drifting` refreshed nightly, or keep as a badge.
- **Views:** Open plans `{stage:[requested,coaching,active,evaluation]}` · Closed plans · Waiting on a decision `{stage:[evaluation]}` · Ending within 7 days · Not yet seen `{seen:[no], stage:[active]}`.
- **Effort: M** — stage maps 1:1 to `state`; the toggle becomes two views; only drifting needs a stored field.
- **Risks:** `_can_read` returns a refusal *payload* (`pb_pip.py:134-135`, `:45-65`) — kit calls must be gated the same way; employee fields read via sudo (`:208-225`); owners facet keys on names; step strip hidden in closed view (`pip_board.xml:111`).

### 5 · pb_onboarding · New joiners · `pb_onboarding_board`
Action `pb_onboarding/views/onboarding_views.xml:208-210`; h1 `static/src/xml/onboarding_board.xml:40`.
- **Kind:** card grid (`:168`) + numbers line + 3-step strip (Getting ready / Settling in / Checklist done) + drawer + buddy / stand-in dialogs.
- **Rows:** `pb.journey.case` with `case_type='onboarding'`, state draft/active/on_hold, `anchor_date >= today-120` or unset (`pb_onboarding/models/pb_onboarding.py:87-92`); `BOARD_LIMIT = 300` (`:34`); not paged. Per row: `pb.newhire.pulse`, `pb.orientation.batch`, `emp._pb_buddy_now()` (`:131-142`).
- **Current filters** (`onboarding_board.js:55-61`): `q`, `country`, `dept`, `month`, `needsOnly`, `focus`, `step` — client (`:109-136`; `stepOf` `:187-191`). Template: search `onboarding_board.xml:95`, months `:104`, departments `:112`, countries `:122`, needs `:128`.
- **Coach:** none on filter panel (`:90-135`). Anchors `nj-run, nj-numbers, nj-steps, nj-list, nj-buddy-pick, nj-drawer, nj-buddy` (screen `joiners`). Replica `joiners()` `screens.js:2830`. Lessons: screen 6 refs; `nj-numbers` 3, `nj-drawer` 3, `nj-list` 3, `nj-steps` 2.
- **Sections:**

| key | path (`pb.journey.case`) | type | label | PIN |
|---|---|---|---|---|
| first_day | `anchor_date` (`journey_case.py:62`) | date | First day | PIN |
| step | choice: ready = `anchor_date > today`; settling = `anchor_date <= today` & `progress < 100`; done = `progress >= 100` (stored `:80`) | choice | Where they are | PIN |
| department | `employee_id.department_id` | many2one | Department | PIN |
| buddy | `employee_id.buddy_id` (`pb_onboarding/models/hr_employee.py:54`), none "No buddy yet" | many2one | Buddy | |
| hrbp | `employee_id.hrbp_user_id` (`:49`) | many2one | HR partner | |
| country | `employee_id.country_id` | many2one | Country | |
| checklist | `template_id` | many2one | Checklist used | |
| status | `state` | selection | Status | |
| source | `source` (`journey_case.py:69`) | selection | Started by | |
| manager | `employee_id.parent_id` | many2one | Manager | |
| overdue | choice: `task_ids` any [state in pending/in_progress/blocked, due_date < today] | choice | Steps overdue | |

Client-derived: `overdue_task_count` non-stored (`journey_case.py:86`) → `any` subdomain; `pulse_red` and `profile_complete_pct` (non-stored `hr_employee.py:74`) have no searchable path.
- **Views:** All · Joining this week · Still without a buddy `{buddy:['none']}` · Steps overdue · Started, checklist open `{step:[settling]}`.
- **Effort: M** — one model, one domain; steps become a choice.
- **Risks:** `buddy_id` alone misses stand-ins (`buddy_temp_id`, `_pb_buddy_now`, `pb_onboarding.py:142,167`); the 120-day floor (`:85`) must stay in `_pbf_base_domain`; country facet falls back to company country (`:154-157`).

### 6 · pb_offboarding · Exits · `pb_exits_board`
Action `pb_offboarding/views/offboarding_views.xml:268-270`; h1 `static/src/xml/exits_board.xml:42`.
- **Kind:** card grid (`:170`) with a 4-light clearance grid per card + 6-figure numbers line + 4-step strip (Working their notice / Signing off / Ready to settle / Settled) + drawer + 3 dialogs.
- **Rows:** `pb.journey.case` with `case_type='offboarding'`, state draft/active/on_hold, `anchor_date >= today-120` (`pb_offboarding/models/pb_exits.py:86-91`); `BOARD_LIMIT = 300` (`:33`); not paged. Per row: `clearance_ids`, `pb.asset.open_items_for`, `pb.resignation` (sudo), `hr.full.final.settlement.pb_gate_for` (sudo, `full_final_guard.py:258-270`), `kt_item_ids`, farewell task, `pb.feedback.request` (`:138-164`).
- **Current filters** (`exits_board.js:65-71`): `q`, `country`, `dept`, `month`, `blockedOnly`, `focus`, `step` — client (`:121-146`; `stepOf` `:211-216` reads `ff.closed`/`ff.ready`/`lwd`). Template: search `exits_board.xml:97`, months `:106`, departments `:114`, countries `:124`, blocked `:130`.
- **Coach:** none on filter panel (`:92-137`). Anchors `ex2-run, ex2-numbers, ex2-steps, ex2-list, ex2-clearance, ex2-drawer, ex2-settle, ex2-card, ex2-send, ex2-handover, ex2-farewell` (screen `exits`; `ex-*` belongs to pb_explorer). Replica `exits()` `screens.js:2916`. Lessons: screen **13 refs** (highest in group A); `ex2-clearance` 4, `ex2-settle` 4, `ex2-numbers` 3.
- **Sections:**

| key | path (`pb.journey.case`) | type | label | PIN |
|---|---|---|---|---|
| last_day | `anchor_date` | date | Last day | PIN |
| department | `employee_id.department_id` | many2one | Department | PIN |
| clearances | choice: `clearance_ids` any [state=pending] (`exit_clearance.py:211`; states `offboarding_common.py:24-28`) / none pending | choice | Clearances | PIN |
| country | `employee_id.country_id` | many2one | Country | |
| handover | choice: `kt_item_ids` any [state != done] (`kt_item.py:123`) | choice | Handover items open | |
| status | `state` | selection | Status | |
| checklist | `template_id` | many2one | Checklist used | |
| source | `source` | selection | Started by | |
| manager | `employee_id.parent_id` | many2one | Manager | |
| overdue | choice: `task_ids` any [open, due_date < today] | choice | Steps overdue | |
| desk | `clearance_ids.dept` (`exit_clearance.py:43`) | selection | Desk still open | |

No path from the case: settlement ready/closed/to_check/issue (found by `employee_id`, `pb_exits.py:150-154`), assets not back, resignation state (`pb.resignation.case_id` exists `resignation.py:134`, no reverse one2many). Two of four steps and three of six numbers depend on the settlement → propose a stored `pb_ff_state` on the case written by `pb_hr_fullandfinal`, or a `settlement_ids` one2many.
- **Views:** All leaving · Leaving this month · Last day has passed · Clearances still open `{clearances:[pending]}` · Ready to settle (needs the settlement path).
- **Effort: L** — heaviest per-row fan-out (seven other models); half the steps/numbers have no searchable path; widest Learn coverage.
- **Risks:** settlement gate is sudo by design (`pb_exits.py:9-13`); `depts` drives the clearance grid, not a filter; replica mirrors the six-figure line and clearance grid.

### 7 · pb_lifecycle · Journeys · `pb_journeys`
Action `pb_lifecycle/views/pb_lifecycle_action.xml:18-20`; h1 `static/src/xml/journeys.xml:39`. Standalone since NAV P2 (`lifecycle_hub.js:41-60` is a redirect map).
- **Kind:** card list (`:157`) + numbers line + 3-step strip + drawer + start/prompt/picker/add-step dialogs.
- **Rows:** `pb.journey.case` in draft/active/on_hold (`pb_lifecycle/models/pb_journeys.py:89,112-115`); `BOARD_LIMIT = 400` (`:30`); not paged; no per-row probes (`_case_row :152-178`). KPIs are server `search_count`s (`:90-110`).
- **Current filters** (`journeys.js:75-80`): `q`, `type`, `lifeState`, `lateOnly`, `focus`, `step` — client (`:130-148`; `stepOf :186-190`). Template: search `journeys.xml:93`, type chips `:102-109`, state chips `:112-116`, late `:117`.
- **Coach:** none. **No** product anchors for `journeys.xml`, no replica, 0 lessons. Learn-free.
- **Sections:**

| key | path (`pb.journey.case`) | type | label | PIN |
|---|---|---|---|---|
| type | `case_type` (CASE_TYPES `lifecycle_common.py:9-16`) | selection | Journey type | PIN |
| status | `state` (draft/active/on_hold) | selection | Status | PIN |
| department | `employee_id.department_id` | many2one | Department | PIN |
| key_date | `anchor_date` | date | Key date | |
| checklist | `template_id` | many2one | Checklist used | |
| source | `source` | selection | Started by | |
| progress | `progress` (stored `journey_case.py:80`) | number | Done (%) | |
| opened | `date_opened` (`:91`) | date | Opened on | |
| job | `employee_id.job_id` | many2one | Job position | |
| company | `company_id` | many2one | Company | |
| late | choice: `task_ids` any [open, due_date < today] | choice | Running late | |
| step | choice: start = draft; wrap = active & no open tasks; running = rest | choice | Where it is | |

Client-derived: `late`/`overdue` read non-stored `next_due_date` / `overdue_task_count` (`journey_case.py:84-90`).
- **Views:** All · Running now `{status:[active]}` · Steps overdue · Not started `{status:[draft]}` · Nothing left to do `{step:[wrap]}`.
- **Effort: S/M** — one model, no per-row probes, no Learn; `any` subdomains for the two task-based facets.
- **Risks:** `HubBackChip` when not embedded (`journeys.js:56`); `templates`/`types` lists feed the start dialog (`journeys.xml:439`) and must stay in the head payload.

### 8 · pb_comp_ben · Awards · `pb_comp_ben_incentives`
Action `pb_comp_ben/views/comp_ben_views.xml:465-467`; h1 `static/src/xml/incentives_board.xml:32`.
- **Kind:** table (`:115-116`) + numbers line + 5-step strip (Being prepared / Waiting for approval / Agreed, not in a run / In a pay run / Paid) + "New award" + "Queue this month" dialogs.
- **Rows:** `pb.incentive`; `pb.incentives.get_board(month=None)` `pb_comp_ben/models/pb_incentives.py:78-123`; domain company or no company (`:82-85`), order `period_month desc`; `BOARD_LIMIT = 400` (`:28`); not paged; `month` param unused. `_row` (`:126-150`) reads the employee via sudo (`incentive.py:102-107`).
- **Current filters** (`incentives_board.js:62-66`): `q`, `step` (`stepOf :142-151` on `state`+`fulfilment`, plus a `"refused"` pseudo-step `:195`), `kindFilter` — client (`:118-132`). Template: search `incentives_board.xml:86`, kind chips `:90-97`.
- **Coach:** none on filter area (`:82-98`). Anchors `aw-put, aw-steps, aw-table` (screen `awards`). Replica `awards()` `screens.js:3055`. Lessons: 1 ref.
- **Sections:**

| key | path (`pb.incentive`) | type | label | PIN |
|---|---|---|---|---|
| where | choice: draft / submitted / approved & `fulfilment in (pending,letter)` / `fulfilment=queued` / `fulfilment=paid` / refused (clone of `stepOf`) | choice | Where it is | PIN |
| kind | `kind` (INCENTIVE_KINDS `comp_common.py:88-92`) | selection | Kind | PIN |
| month | `period_month` (`incentive.py:65`) | date | Pay it in | PIN |
| person | `employee_id` | many2one | Who it is for | |
| department | `employee_id.department_id` | many2one | Department | |
| run | `run_id` (`:79`) | many2one | Pay run | |
| amount | `amount` (money) | number | Amount | |
| approval | `state` (`:71`) | selection | Approval | |
| fulfilment | `fulfilment` (`:73`; `comp_common.py:108-113`) | selection | Where it has got to | |
| source | `source` (`:84`) | selection | Where it came from | |
| asked_by | `requested_by_user_id` (`:90`) | many2one | Asked by | |
| letter | choice on `letter_id` set | choice | Letter on file | |

- **Views:** All · Waiting for approval `{where:[submitted]}` · Agreed, not in a run (+ this month) · In a pay run `{where:[queued]}` · Paid this month.
- **Effort: S** — flat table, every facet a stored field; the queue dialog is server-driven (`preview_queue` `:223-226`) and does not read `visibleRows`.
- **Risks:** refusal payload (`_refusal :31-39`) must cover kit calls; `company_id = False` rows are in scope (`:83`); search on `employee_id.name` by an awards-only user may hit employee field access.

---

## B. Hiring and HR services

### 9 · pb_hiring · Hiring › Roles · `pb_hiring_board`
Action "Hiring" `pb_hiring/views/hiring_views.xml:596-599`; hub door `pb_hiring_hub` `:605-608` mounts the same component with `startTab` (`hiring_hub.js:81-99`).
- **Kind:** card grid (`hiring_board.xml:276-277`) under a glance line (`:100`) and a 4-step strip (`:115`).
- **Rows:** `pb.hiring.requisition`; `pb.hiring.get_board()` `pb_hiring/models/pb_hiring.py:146-205` → `Requisition.search([('company_id','in',co_ids)], order='id desc', limit=cap)` `:154-155`, `BOARD_LIMIT = 300` (`:41`); `_row` `:229`; `capped` `:191`. Not paged. The same RPC also returns `interviews` (`:164`) — a second row source in one call.
- **Current filters** (`hiring_board.js:162-167`, `journeyFocus :138`): `q` (`:416-417`), `dept`, `country`, `stage`, `recruiter` selects (xml `:218-230`), `focus` glance (`:406-413`), `journeyFocus` step strip (`stageOf :436-445`). **All client** (`get filtered :386-423`; clear `:620-625`). No sort.
- **Coach:** NONE on the panel (`xml:212`). Neighbours `hi-numbers :100`, `hi-steps :115`, `hi-tabs :180`, `hi-row :276`, `hi-card :277`. Anchors: 12 keys for `hiring_board.xml` (screen `hiring`). `screens.js`: `hiring` 9 hits, `hi-` 17. Lessons: `hiring` **105 hits**, `hi-` 29.
- **Sections:**

| key | path (`pb.hiring.requisition`) | type | label | PIN |
|---|---|---|---|---|
| step | choice cloning `stageOf` (setup / open & not published & no applicants / open & (published or applicants) / filled) | choice | Where it is | PIN |
| status | `state` (REQUISITION_STATES `hiring_common.py:151`) | selection | Role status | PIN |
| department | `department_id` | many2one | Department | PIN |
| country | `country_id` | many2one | Country | |
| recruiter | `recruiter_id` | many2one | Recruiter | |
| request | `request_state` (`requests_p3.py:290`) | selection | Hiring request | |
| budget | `budget_status` (`hiring_common.py:194`) | selection | Budget | |
| role_type | `role_type` (`:137`) | selection | Kind of role | |
| manager | `reporting_manager_id` | many2one | Hiring manager | |
| wanted_by | `target_start_date` | date | Wanted by | |
| opened | `opened_on` | date | Opened on | |
| headcount | `headcount` | number | Seats | |

- **Views:** Open roles · Over budget · Nobody asked yet · Filled · Opened this quarter.
- **Effort: L** — cover-scope/record-rule reads, `_row` with pipeline + per-reader `waiting_mine` (`_waiting :231`), glance and step counts over loaded rows, interviews in the same RPC.
- **Risks:** `waiting`/`waiting_mine`/`mine` are per-reader Python facts (keep as glance); `shareOnly` readers (xml `:243`); heaviest Learn screen; `applicant_count` is computed (`requisition.py:230`) → "has candidates" needs `applicant_ids != False`.

### 10 · pb_hiring · Hiring › Interviews · `pb_hiring_board` (tab `interviews`)
- **Kind:** list (`t-call="pb_hiring.IvList"` `hiring_board.xml:420`).
- **Rows:** `pb.hiring.interview`; `_interview_rows(co_ids)` `pb_hiring.py:352-367`: company ∧ (start ≥ now−42d ∨ (state ∈ scheduled,done ∧ feedback pending)), order start, limit 300; loaded inside `get_board` `:164`. Not paged.
- **Current filters:** `ivQ` (`hiring_board.js:193`; `:906-908`) and `ivFocus` chips today/week/awaiting/late (`IV_FOCUS :70`; `bucket` server-side `:374-386`; filtered client `:895-913`). Clear xml `:384`. "Send the reminders due now" sits in the filter row (`:385-387`).
- **Coach:** none (`xml:371`). Shares screen `hiring`; no interview-specific anchors.
- **Sections:** when `start` date PIN · state `state` (INTERVIEW_STATES `hiring_common.py:240`) PIN · role `requisition_id` PIN · kind `kind` (STEP_KINDS `:207`) · mode `mode` (`:251`) · recruiter `recruiter_id` · job `job_id` · round `round_no` number · opinions — derived `feedback_late` / `feedback_in<feedback_total` (`interview.py:214-216`, computed NOT stored) → use `feedback_ids.state='pending'` + `feedback_due_at < now`.
- **Views:** Today · This week · Opinions late · Called off recently.
- **Effort: M** — one model; late/awaiting rest on non-stored computes and a 42-day window; a second kit inside the same OWL component as Roles.
- **Risks:** `panel_employee_ids` is many2many → not a kit path; two `useFilterKit` instances in one component or split the tab into its own component.

### 11 · pb_hiring · Hiring › Applicants (register) · `pb_hiring_board` (tab `applicants`)
`data-coach="hi-applicants"` wraps the register (`pb_hiring/static/src/xml/hiring_p9.xml:19`).
- **Kind:** kanban (one column per stage `:115`) with a List alternative (`:152`), toggled by `appsF.view`.
- **Rows:** `hr.applicant`; `pb.hiring.get_applicants(filters)` `pb_hiring/models/registers_p9.py:158-258`: roles the reader may see (`_p9_roles :113-126`), `job_id in jobs` + family domains (`FAMILY_DOMAINS :65-73`) + q ilike (`:198-204`), `Applicant.sudo().with_context(active_test=False).search(..., order='date_last_stage_update desc, id desc', limit=APPLICANTS_CAP)` `:205-208` (= `BOARD_CANDIDATES` 600, `board_p1.py:51`); cards rebuilt per role via `_candidates(req)` `:219-221`; flag chips post-filter `:244-247`. Not paged (`cursor` reserved `:164`).
- **Current filters** (`appsF` `hiring_registers_p9.js:93`, localStorage `APPS_DEFAULT :43`): q (server, debounced `:352-357`), role / recruiter / family selects (server), flag chips waiting_mine/late/iv_week/duplicate (**client** `regCards :383-387` via `APP_FLAG_TEST :47-52`), glance `:389-402`, list-view sort (client `regListRows :491`). Clear `:376-381`.
- **Coach:** `hi-applicants` (`:19`), `hi-applicants-board` (`:115`/`:152`); the panel itself (`:41`) none. Both keys in anchors.json (screen `hiring`); neither quoted in lessons.
- **Sections:** family — choice over `stage_id.pb_family` / `stage_id.pb_key` / `active` (FAMILY_DOMAINS) PIN · role `pb_requisition_id` (`hr_applicant_ext.py:30`) PIN · recruiter `pb_requisition_id.recruiter_id` PIN · stage `stage_id` · screen `pb_screen` (`:34`) · applied `create_date` · moved `date_last_stage_update` · source `source_id` · hold `pb_hold_until` · authorisation `pb_work_authorization` (`journey.py:309`). Client-only flags `waiting`/`late`/`iv`/`duplicate` (`board_p1.py:602`) — keep as post-filter chips or store on the applicant.
- **Views:** In play · Waiting on me (chip) · Opinions late (chip) · Interview this week (chip) · Possible duplicates (chip).
- **Effort: L** — kanban with drag + bulk move keyed on filtered cards (`sel`, `register:true :231`), cards built per role through `_candidates` with the privacy mask, column counts from cards (`_p9_columns :261`), two view modes, localStorage memory to migrate.
- **Risks:** `openRegister` doors from the Overview set `flag` programmatically (`hiring_board.js:509-514` → `:125-134`) — the kit needs a "set filters from code" entry (`toggleFilters` exists); per-reader cover scope; `by_job` dedupe (`:182-186`).

### 12 · pb_hiring · Hiring › Offers (register) · `pb_hiring_board` (tab `offers`)
`hi-offers` `hiring_p9.xml:206`; 5-step strip `hi-offers-steps :209-215`; rows `hi-offer-row :290`.
- **Kind:** table under a step strip.
- **Rows:** `pb.hiring.offer`; `pb.hiring.get_offers(filters)` `registers_p9.py:413-474` → `_p9_offer_set :328-334` `Offer.search(company, order='id desc', limit=OFFERS_CAP=200)` (`:46`); rows then filtered in Python `:440-456` — but JS calls with `{}` (`hiring_registers_p9.js:568`) and filters **client-side** in `offRows :646-669`. Not paged.
- **Current filters** (`offF :99`, `OFFERS_DEFAULT :44`, localStorage): step strip (`pickOfferStep :593`), role / recruiter selects, flag chips (`OFFER_FLAG_TEST :54-60`), q (`:656`). All client; `joining_soon` re-sorts (`:661-667`). Clear `:600-604`.
- **Coach:** panel (`:218`) none. Three keys in anchors.json (`hiring`); none quoted in lessons.
- **Sections:** step — `state` grouped (OFFER_STEPS `:55-61`) PIN · state `state` (OFFER_STATES `hiring_common.py:380`) PIN · role `requisition_id` PIN · recruiter `requisition_id.recruiter_id` · start `start_date` · sent `sent_on` · decision `candidate_decision` · manager `reporting_manager_id` · joined `joined_on` (`joining_p6.py:853`) · docs — choice "overdue" = `docreq_id.deadline < today ∧ docreq_id.state ≠ complete` (`:396-398`) · check `bgv_id.state` · monthly `monthly_total` number (hide unless `show_money :384`). Python-derived `waiting_mine` = `_chain_my_seat()` (`:368-369`) — no domain.
- **Views:** With the candidate · Joining in 30 days · Documents overdue · Joined this month · Turned down.
- **Effort: M** — flat list, single model; money masking stays in `_offer_row`.
- **Risks:** Overview tiles reuse `_p9_offer_rows` (`_offer_kpis :480-484`, "tile and filter never disagree") — tiles must read the kit's counts; localStorage memory; `openRegister(tab,{flag,step})` programmatic entry.

### 13 · pb_ask_hr · Home › Ask HR · Home lens `askhr` (no action tag)
Registered `registry.category(HOME_LENSES).add("askhr", …)` `pb_ask_hr/static/src/js/askhr_lens.js:562-570` (`HOME_LENSES="pb_home_hub_lens"`, `pb_home_hub/static/src/js/home_hub.js:102`); door = "Home" `pb_home_hub` (`pb_home_hub/views/pb_home_hub_action.xml:15-17`). Titles `askhr_lens.xml:49-50`.
- **Kind:** step-strip board (QuietSteps `:78-84`, one step's cards at a time) + card list (`:154`) with bulk select.
- **Rows:** `pb.ask.hr.ticket`; `pb.ask.hr.get_board()` `pb_ask_hr/models/askhr_board.py:209-271`: open `search([('state','in',OPEN_STATES)], order='create_date desc', limit=OPEN_CAP)` `:224-225` (500, `:37`) + closed `limit=CLOSED_CAP` `:226-227` (60, `:35`); counts via `_read_group :220`; record rules split employee/HR. Not paged.
- **Current filters** (js `:78-89` + `readFilters :57-64`, localStorage `pbhub.askhr.filters.v1` per user): `step` (client `cards :286-292`), `week` (`:216-220`), `q` (`:257`; `:281-282`), `mine` (`:240`), `nobody` (`:246`), `cat` chips (`:252`; categories in use `:268-271`). All client. Bulk `sel :85/:341-365` → take/hand/close over `cards` (`:481-545`).
- **Coach:** filter area `pbah-filters` (xml `:87`) NONE; `ah-glance :69`, `ah-steps :78`, `ah-card :154`, `ah-take :194`. Anchors 4 keys (screen `askhr`); `screens.js` `askhr` 2, `ah-` 5; lessons `askhr` 1, no `ah-` keys.
- **Sections:** step `state` (STATES `ticket.py:56-61`) PIN · category `category` (`:37-44`) PIN · owner `user_id` (none "Nobody has it yet") PIN · mine — `user_id = env.uid` choice · asker `employee_id` · department `employee_id.department_id` · asked `create_date` · answered `answered_on` · closed `closed_on` · closed_by `closed_by` · company `company_id`. Python-derived `late` (>2 working days), `waiting_days` (computed not stored `ticket.py:106-107`) — keep `new_late` as a glance figure.
- **Views:** Nobody has it yet · Mine · Answered this week · New, waiting.
- **Effort: M** — embedded lens (no action), `railKeydown` keyboard nav, bulk verbs over shown cards, per-user localStorage filters, closed cap of 60 to lift.
- **Risks:** the step strip is the primary filter today; employees see only their own tickets so counts differ by reader.

### 14 · pb_assets · Assets (The register) · `pb_assets`
h1 `pb_assets/static/src/xml/assets_board.xml:36`; action `pb_assets/views/pb_assets_action.xml:12-13`.
- **Kind:** table with row checkboxes (`:178+`) and a bulk bar (`:320-333`); two segments The register / Requests (`:71-82`).
- **Rows:** `pb.asset`; `pb.assets.get_board()` `pb_assets/models/pb_assets_board.py:96-168`: `Asset.search(CO, order='code desc, id desc', limit=BOARD_LIMIT)` `:125-127` (400, `:32`); facets in Python `:136-142`; `capped :150`. Not paged. Second source `_request_digest :272-297` (`pb.asset.request`, limit 60) for Requests.
- **Current filters** (`assets_board.js:72-76`): `q` (`:166`; `:148-150`), `kind` chips, `status` chips (used statuses `:177-180`), `categoryId` chips, `countryId` select. All client `visibleRows :132-152`; clear `:160`. Bulk `picked :79`, `pickAllVisible` over `visibleRows :282-286`, `bulk_set_state :594`.
- **Coach:** NONE anywhere. No Learn entries.
- **Sections:** status `state` (ASSET_STATES `asset_common.py`) PIN · kind `kind` (related stored `asset.py:46-48`) PIN · category `category_id` PIN · country `country_id` · holder `current_employee_id` (stored compute `:60-62`) · department `current_employee_id.department_id` · warranty `warranty_end` date (`warranty_state` is computed NOT stored `:78-82`) · bought `purchase_date` · arrived `delivery_date` · cost `cost` · reused `is_reused` choice · company `company_id`.
- **Views:** Spare physical · Out with people · Under repair · Warranty ending in 60 days · Switched-off accounts.
- **Effort: M** — flat list; bulk bar must read kit rows; status labels differ by kind (`state_label(kind,state)`) so a plain selection shows "Assigned" where digital rows say "Active". Requests segment stays.
- **Risks:** `leavers_holding` KPI is Python (`:171`); facets from rows; capped newest-400.

### 15 · pb_rnr · Praise · `pb_rnr_board`
h1 `pb_rnr/static/src/xml/rnr_board.xml:34`; action `pb_rnr/views/rnr_views.xml:337-338`.
- **Kind:** list (`:137`) under a glance line (`:66`) and 4-step strip (`:73-77`).
- **Rows:** `pb.rnr.nomination`; `pb.rnr.get_board()` `pb_rnr/models/pb_rnr.py:94-148`: `Nom.search(company, order='id desc', limit=BOARD_LIMIT+1)` `:98-101` (`BOARD_LIMIT = 300` `:34`); kpis Python over rows `:130-146`. Not paged.
- **Current filters** (`rnr_board.js:58-60`): `q` (`:140`; `:133-135`), `stateFilter` (step strip `pickStep :180` and glance "refused" `:192`; matches state or step `:128`), `valueFilter` chips (`:141`). All client `visibleRows :124-137`; `showAll :215`.
- **Coach:** NONE. No Learn.
- **Sections:** step — `state` grouped (draft / submitted / manager / done+refused; NOMINATION_STATES `rnr_common.py:86`) PIN · value `value_id` PIN · nominee `nominee_id` PIN · outcome `outcome` (`:99`) · nominator `nominator_id` · department `nominee_id.department_id` · cycle `cycle_id` · written `submitted_at` · decided `decided_at` · winner `is_winner` · public `public` · amount `award_amount`.
- **Views:** Waiting on a manager · Waiting on HR · Not this time · Given money this quarter · Quarter winners.
- **Effort: S/M** — one model, no bulk; `this_month`/`awarded_qtd` become kit counts or stay in `get_board`.
- **Risks:** names via `Nom._person` sudo (`:168-169`); "refused" is both a step and a state.

### 16 · pb_vendor_access · Vendors · `pb_vendors_board`
h2 `pb_vendor_access/static/src/xml/vendors_board.xml:45`; action `pb_vendor_access/views/vendor_access_views.xml:210-213`.
- **Kind:** card list (after `:135`) under a glance line (`:70-73`).
- **Rows:** `pb.vendor`; `pb.vendors.get_board(vendor_type, department_id, state, search, limit)` `pb_vendor_access/models/pb_vendors_facade.py:88-127`: type/department/state **server-side** (`:94-100`), `Vendor.search(domain, limit=801, order='name')` `:101` (`VENDOR_ROW_CAP = 800`, `vendor_common.py:90`); text search in **Python** over a folded haystack (`:109-114`). Not paged; `truncated` flag.
- **Current filters** (`vendors_board.js:64-67`): `type` chips (server; facets from rows `:171-184`), `agreementState` chips (server), `search` (server round-trip per keystroke `:151-154`, no debounce), `department_id` (server param, **no chip rendered**). Glance press → `setState` (`:139-140`). Clear `:156-162`.
- **Coach:** none. No Learn.
- **Sections:** type `vendor_type` (`vendor_common.py:42`) PIN · agreement `agreement_state` (stored compute `pb_vendor.py:87`; none "No agreement yet") PIN · owner `responsible_user_id` PIN · department `department_id` · country `country_id` · next_end `next_end_date` (stored `:84-86`) · mine — `responsible_user_id = uid` choice · company `company_id`. Not usable: `agreement_count` (computed not stored `:79-80`).
- **Views:** Coming up for renewal · Already run out · Nothing recorded · I look after.
- **Effort: S** — filters already server-side, no bulk, no steps.
- **Risks:** kit search is `ilike` — the folded Python search exists because `ilike '%bui%'` misses "Bùi" (`:109-112`); keep a fold or accept the regression. Headline sentence derives from shown rows (`:156-169`).

### 17 · pb_approval_config · Approvals ("Waiting for a decision") · `pb_approval_inbox`
h1 `pb_approval_config/static/src/xml/inbox.xml:25`; action `pb_approval_config/views/actions.xml:31-32`.
- **Kind:** card list (`:135`) with four tabs (`:89-96`) and a scope row Mine / My team / Everyone (`:77-87`); drawer per request.
- **Rows:** `biz.approval.request`; `pb.approval.inbox.list_requests(tab, {area,due}, cursor, scope)` `pb_approval_config/models/inbox_facade.py:178-230`: scope picks the searching model (user vs `sudo()`, `_scoped :130-176`), tab/area/due/process_key as domain (`:184-207`), `Request.search(domain, limit=MAX_CARDS, order='submitted_at desc')` `:209-210` (`MAX_CARDS = 120` `:30`); "mine" post-filtered in Python `_is_mine :212-213`. Cursor exists (`:206-207`, `:229`) but JS passes `false` (`inbox.js:226-231`) → not paged in the UI.
- **Current filters** (`inbox.js:128-140`): `tab`, `scope`, `area` chips (xml `:107-114`, server), `due` today/late chips (`:116-120`, server). No search, no sort. Persisted via `useNavigationState :143-148`; deep-link `arrival`/focus `:157-171`.
- **Coach:** `pbam-filters` (`:106`) NONE; `ai-scope :77`, `ai-tabs :89`, `ai-card :135`. Anchors 13 `ai-*` keys (screen `approvals`); `screens.js` `approvals` 2, `ai-` 14; lessons `approvals` **42**, `ai-` 31.
- **Sections:** pile — `state` grouped (pending+blocked / returned / finished; STATES `request.py:13`) PIN · area `process_id.area` (AREAS `process.py:6`) PIN · due `due_at` (presets today / late) PIN · process `process_id` · company `company_id` · submitted `submitted_at` · sent_by `submitter_uid` · amount `amount` (never summed across currencies) · currency `currency_id`. Python-derived: "My turn" needs `seat_ids.acting_user_id = uid` (one2many hop, not a kit path) AND `_is_mine :304`; `subject_user_ids` is many2many.
- **Views:** My turn today · Late · Sent back to me · Finished this month · Pay area waiting.
- **Effort: L** — scope swaps the model/sudo, "mine" is Python, the four tabs are a vocabulary Learn (42 lessons) and PayAI doors depend on; counts `_counts :239-255`.
- **Risks:** external doors by tag with `arrival` context — `pb_records/static/src/js/records_desk.js:671`, `pb_statutory/static/src/js/statutory_wizards.js:50,96`, `pb_tenants/static/src/js/tenants.js:2186`, `pb_payruns/static/src/js/payruns.js:889`; `locate_request :428` chooses tab+scope for a focused request — the kit must accept an initial filter set from context.

---

## C. Payroll

Learn note: `screens.js` replicates every one of these — `payruns()` `:1097`, `payslips()` `:1212`, `reports()` `:861`, `structures()` `:1550`, `statutory()` `:1597`, `fullfinal/proration/retro()` `:1772-1782` (all via `ledgerHTML()` `:261`), `records()` `:2106`.

### 18 · pb_payruns · Pay Runs · `pb_payruns`
Action `pb_payruns/views/pb_payruns_action.xml:3-6`; hub mount `pb_payhub/static/src/js/pay_hub.js:104-110`; registered `payruns.js:1023`.
- **Kind:** step-strip board — three lanes (Draft / Waiting for approval / Done) whose header IS the step, a "This month" hero whose phrases filter, Done lane grouped by month, a switchable list view, multi-select bulk bar, quick-look panel.
- **Rows:** `hr.payslip.run`; `pb.payruns.get_board_data()` `pb_payruns/models/pb_payruns.py:54-242`. `Run.search([], order='date_end desc', limit=BOARD_LIMIT*4)` then company-filtered and sliced to `BOARD_LIMIT = 60` (`:68-75`, `:18`). **Not paged.** `rejectedBatches` is the same array filtered to `state='cancel'` (`payruns.js:935-938`).
- **Current filters (all client):** `useState` `payruns.js:129-141` — `step`, `hero` (drafts/waiting/topay/paid), `months` ('all'|'month'), `division`, `q` (`:261-265`), `view`, `sort {k,d}` (list view `:775-794`), `showRejected`. Predicate `visible(b) :250-267`. Template: months `payruns.xml:97-100`, division chips `:103-110`, search `:113-117`, board/list toggle `:118-121`, sortable headers `:198-206`. Persisted via `useNavigationState :147-157`. Demo users: the **native kanban twin** pre-filters to June 2026 (`payruns_kanban.js:36-42`); the OWL board does not.
- **Coach:** `pk-divchips` (`payruns.xml:103`); none on search/months. `pk-steps :139`, `pk-tabs :134`. Anchors (screen `payruns`): pk-kpis, pk-run, pk-tabs, pk-divchips, pk-card, pk-card-actions, pk-hero-next, pk-peek, pk-bulk, pk-checks, pk-owner, pk-deadline, pk-steps, pk-route, pk-rejected, pk-reject-why; `pk-datechips` is the kanban file's. Replica `payruns()` `:1097-1212` draws pk-divchips, pk-steps, pk-tabs, pk-kpis, pk-run, pk-hero-next, pk-deadline, pk-rejected. Lessons: 21 entries `screen: payruns`; pk-divchips 1, pk-steps 3, pk-kpis 3.
- **Sections:**

| key | path (`hr.payslip.run`) | type | label | PIN |
|---|---|---|---|---|
| stage | `state` (PB_STATES `pb_payruns/models/hr_payslip_run.py:169`) | choice with tones | Where it is | PIN |
| period | `date_end` (this / last month, this quarter) | date | Pay period | PIN |
| division | `pb_division` (stored Char `:296`; labels `pb_division_label :301`) | char | Division | PIN |
| scheme | `pb_formula_config_id` (`pb_scheme_map/models/hr_payslip_run.py:33`) | many2one | Payroll scheme | |
| company | `slip_ids.company_id` (run has no company_id; `_run_companies` `pb_payruns.py:830`) | many2one (one2many hop — **not a kit path**; needs a stored company on the run) | Company | |
| currency | `pb_currency_id` (`:292`) | many2one | Money | |
| mine | `pb_awaiting_me` (computed with `search=` `:537`) | choice | Waiting on me | |
| health | `pb_balance_ok` / `pb_unsourced_count > 0` (`:271`, `:288`) | choice | Checks | |
| sentback | `pb_return_note != False` (`:182`) | choice | Sent back to be fixed | |
| prepared | `pb_prepared_uid` (`:189`) | many2one | Prepared by | |
| people | `pb_employee_count` (`:244`) | number | People paid | |
| net | `pb_total_net` (`:246`) | number | Net pay | |
| refund | `credit_note` | choice | Refund runs | |

Client-only: `delivery.paid/delivered` (joined from `pb_pay_delivery` per run `pb_payruns.py:311`) — "to pay"/"paid" need a stored flag or a domain over the payment models.
- **Views:** All live runs `{stage:[draft,approval_pending,done]}` · Waiting on me · This month · Approved, not paid (needs the flag) · Sent back · Rejected `{stage:[cancel]}`.
- **Effort: L** — lanes/hero/month-groups/keyboard cursor/FLIP/bulk bar all read one in-memory array; lane counts are deliberately *un-narrowed* (W82 `payruns.xml:94-95`) so counted chips change a design ruling; two mount points; demo pre-filter lives only in the kanban twin.
- **Risks:** bulk submit reads `state.selected` (`payruns.js:642-654`), hero bulk-submit reads filtered `monthBatches` (`:473`); shift-select walks `columnBatches` (`:627-636`). `pb_payruns_learn.py` ("Right now") reads `get_board_data` (`:7`) — the RPC must keep returning the un-paged board. `useNavigationState` keys must migrate to kit state.

### 19 · pb_payslip_review · Payslip review · `pb_payslip_review`
h1 `payslip_review.xml:13`; action "Payslips" `pb_payslip_review/views/pb_payslip_review_action.xml:3-6`; hub lens `pay_hub.js:111-112`; registered `payslip_review.js:139`.
- **Kind:** split list + detail, numbers line, 3-step strip; scoped to ONE pay run picked in a `<select>`.
- **Rows:** `hr.payslip` within one run; `pb.payslip.review.get_review_data(run_id)` `pb_payslip_review/models/pb_payslip_review.py:102-147` — `run.slip_ids` filtered to active companies, **no limit, not paged**. Run picker `get_runs()` `:66-69` capped at 20. Detail `get_slip_detail :150-165`.
- **Current filters:** `state.filter` only (`payslip_review.js:32`): all | flag | draft | verify (+level1/level2) | done — client `get filteredSlips :49-61`. Run selector server (`onRunChange :47`). No search, sort or facet. Template: run select `payslip_review.xml:17-21`, glance `:30-38`, steps `:45-61`, list `:70-87`.
- **Coach:** `ps-chips` on the step strip (`:45`), `ps-kpis :30`, `ps-runsel :17`. Anchors (screen `payslips`): ps-runsel, ps-kpis, ps-why, ps-chips, ps-list, ps-detail, ps-status, ps-breakdown. Replica `payslips()` `:1212-1275` draws all. Lessons: 20 entries; ps-chips 1, ps-kpis 5, ps-runsel 2, ps-list 7.
- **Sections:** run `payslip_run_id` (base-domain default = picked run; keep the picker OR make this the pinned section) PIN · status `state` (`om_hr_payroll/models/hr_payslip.py:53`; fold verify/level1/level2 into "Waiting for approval") PIN · review — needs a server flag; today `flag` comes from `run.pb_review_flags()` (`review_flags.py`, not stored); candidate stored `pb_review_change_pct` (`review_flags.py:155`) PIN · department `employee_id.department_id` · job `contract_id.job_id` · structure `struct_id` · company `company_id` · net — no stored net on the slip (`pb_pay_totals()` is a per-line helper); propose stored `pb_net` · paid `paid` · refund `credit_note` · period `date_to`.
- **Views:** All in this run · Need review · Waiting for approval · Done · Refunds.
- **Effort: M** — flag/net need a stored field or a domain helper; the run picker is a scope control that must stay (`xml:9-12`, W17); the detail pane auto-selects the first flagged slip (`js:42-44`) so `onChange` must re-select.
- **Risks:** `totals.flagged`/step counts are over the whole run (matches the kit's counted model). `vnd()` hard-codes "₫" (`js:125-126`) — pre-existing. Search fields proposal: `employee_id.name`, `number`, `employee_id.barcode`.

### 20 · pb_payrun_ledgers · Full & Final / Proration Audit / Retro Adjustments · `pb_fullfinal` `pb_proration` `pb_retro`
`ledger_actions.xml:3-13`; hub lenses "Settle" and "Adjust › Retro | Proration" (`pay_hub.js:133-168`; tabs choose the RPC model `ledger.js:108-111`); registered `ledger.js:370-376`.
- **Kind:** card list with numbers line, facet chips/selects, date chips, search; Full & Final adds a 3-step strip and a row action; in a hub a row opens `WfDrawer`.
- **Rows:** three abstract data models, one `get_data()` each — `pb.fullfinal` → `hr.full.final.settlement` (`pb_payrun_ledgers/models/ledger_cockpits.py:266-357`, `LIMIT = 400` `:13`); `pb.proration` → `hr.payroll.proration.line` (`:457-507`); `pb.retro` → `hr.payroll.retro.adjustment` (`:555-607`). Domain company only (`_co_dom :68`). **Not paged.** Steps counted server-side over the whole domain (`_fnf_steps :370-404`).
- **Current filters (client over ≤400 rows):** `search`, `f{facetKey}`, `step`, `dateFilter/from/to` — `ledger.js:61-70`; `_match :205-217`, `_inDate :191-204`. Facets built server-side from loaded rows (`_rows_facet :43-51`) or a Selection (`_sel_facet :35-40`): F&F = source, dept, config (`:345-349`); proration = state, component, config, batch (`:495-500`); retro = state, component, config, applied batch (`:595-600`). KPIs press-to-filter (`:280-299`). Template: facets `ledger.xml:79-101`, search `:102-105`, date chips `:108-121`, steps `:61-74`.
- **Coach:** `lg-facets` (`ledger.xml:79`); search none; `lg-steps :62`, `lg-kpis :41`, `lg-tabs :25`, `lg-rows :125`, `lg-rowact :146`, `lg-drawer :175`, `lg-openfull :162,:165`. Anchors: lg-kpis/lg-facets/lg-rows/lg-openfull/lg-drawer screen `['fullfinal','proration','retro']` (shared); lg-tabs `['proration','retro']`; lg-steps, lg-rowact `fullfinal`. Replica `ledgerHTML()` `:261-345` draws lg-tabs, lg-kpis, lg-steps, lg-facets, lg-rows, lg-drawer. Lessons: fullfinal 9, proration 5, retro 6; lg-facets 2, lg-kpis 2, lg-steps 1, lg-rows 5.
- **Sections (per mode; keys shared where the field exists on all three):**

| key | path | type | label | PIN |
|---|---|---|---|---|
| status | `state` (F&F draft/pending/approved/returned/rejected `fnf_approval.py:41`; proration draft/posted; retro draft/posted/cancelled) | choice | Where it is | PIN |
| department | F&F `department_id` (`full_and_final.py:38`); proration/retro `employee_id.department_id` | many2one | Department | PIN |
| scheme | `formula_config_id` (all three) | many2one | Configuration | PIN |
| when | F&F `settlement_date`; proration `effective_date`; retro `period_from` | date | Settled on / Effective / Period start | |
| component | proration/retro `component_id` | many2one | Component | |
| batch | F&F/proration `import_batch_id`; retro `applied_in_batch_id` | many2one | Batch | |
| source | F&F `source` (`:79`) | selection | Source | |
| check | F&F `pb_to_check` (`fnf_approval.py:66`) / `pb_compute_issue != False` (`:62`) | choice | Checks | |
| mine | F&F `seat_user_ids in [uid]` + state pending (`:99`, `_fnf_steps :380`) | choice (many2many — verify the kit accepts a raw domain here) | Waiting on me | |
| job | F&F `job_id` (`:44`) | many2one | Job position | |
| money | F&F `net_payable`; proration `prorated_amount`; retro `delta_amount` | number | Net payable / Prorated / Delta | |
| company | `company_id` | many2one | Company | |

- **Views:** F&F: Ready to check · Waiting on me · Approved this month · Manual. Proration/Retro: Posted this month · Still draft · Cancelled (retro).
- **Effort: M** — one template, three data models → three mixin implementations (or one mixin with per-descriptor `_pbf_model`), and the hub `tabs` switch must re-create the kit for the new model; strip + press-to-filter KPIs map onto `choice` cleanly.
- **Risks:** `setTab` resets filters and reloads (`ledger.js:129-140`) — saved views need a distinct `_pbf_screen()` per mode. `rowAction` reloads the whole board (`:340-362`). Currency sign is grid-wide from the scheme (`_grid_symbol :107-130`).

### 21 · pb_hr_workforce · Payroll Report · `payroll_report_dashboard`
Title chip `payroll_report.xml:16`; menu `menu_views.xml:27-32`; Insights hub lens "Reports"; registered `payroll_report.js:232`; also opened per run via `action_open_payroll_report` (`models/payroll_report.py:225-233`).
- **Kind:** table report with three tabs (Earnings / Deductions / Dept Summary) for ONE run vs the previous; row click expands a breakdown.
- **Rows:** derived, one per `hr.payslip` of the chosen run — `hr.payroll.report.api.get_batch_report(batch_id)` `pb_hr_workforce/models/payroll_report.py:49-202` iterates `batch.slip_ids` (no limit, not paged) computing gross/net/deductions/diffs/events in Python; run picker `get_all_batches() :205-218` capped 24 (`:209`). Dept Summary = `dept_chart` aggregates (`:165-175`).
- **Current filters:** `searchQuery` (client, name/job/department `payroll_report.js:100-108`), `activeTab`, `batchId` (server `:156-162`), `expandedEmp` — `useState :70-82`. Template: run select `payroll_report.xml:18-25`, search `:26-29`, tabs `:32-48`. No sort/facets/dates.
- **Coach:** none on search; `rp-pick :18`, `rp-tabs :32`, `rp-kpis :53`. Anchors (screen `reports`): rp-pick, rp-kpis, rp-tabs. Replica `reports()` `:861-911`. Lessons: 6 entries; each anchor 1.
- **Sections (records model `hr.payslip`, base domain `payslip_run_id = picked run`, `state != cancel`):** run `payslip_run_id` PIN · department `employee_id.department_id` PIN · changed — **client-derived** (`events` non-empty `py:104-117`); server equivalent compares `pb_pay_totals` with the prior slip inside `_pbf_section_domain` — no stored field PIN · job `contract_id.job_id` · structure `struct_id` · company `company_id` · status `state` · gross/net/deductions — **client-derived** via `lines.pb_pay_totals()` (`py:82-85`); propose stored `pb_gross/pb_net` · manager `employee_id.parent_id` · newjoiner `employee_id.first_contract_date`.
- **Views:** Everyone in this run · Pay changed · By department · New joiners this run.
- **Effort: L** — three tabs render different column sets of the same derived rows; every figure is Python per slip, so a server filter on money or "changed" means persisting those figures or re-computing in the domain hook; Dept Summary is an aggregate.
- **Risks:** donut re-renders from `deptChart` (`js:184-229`) — recompute from the filtered set or leave un-narrowed; `prev_batch` picked by `date_end < date_start` regardless of scheme (`py:59-63`, pre-existing); two mount points; a 4,500-slip run loads all rows today.

### 22 · pb_records · Records Desk · `pb_records_desk`
Action name `pb_records_action.xml:14`; People hub lens "Records"; registered `records_desk.js:1072`.
- **Kind:** bulk-edit spreadsheet grid: WHO rail (search + facets) × WHAT strip (mapped fields of one scheme) × virtualised grid; staged edits → review drawer → apply; history with undo.
- **Rows:** `hr.employee`; `pb.records.desk.search_people(config_id, filters, field_ids, offset, limit=100, with_facets)` `pb_records/models/pb_records_desk.py:546-580` — **already server-side and paged** (`fetchPage` `records_desk.js:325-356`, virtual rows `records_grid.js:295-330`). Domain `_people_domain :439-461` (company, q over name/barcode/work_email/employee_id, department_ids, job_ids, employee_ids); post-filters `_apply_post_filters :514-536` for `contract_states` (latest contract, one query `:478-496`) and `statuses` (feed signal from `pb.payrun.wizard._employee_signals` `:499-502`). Facets with own-filter-dropped `_facets :583-637`. `matching_ids :640-648` for "select all matching".
- **Current filters (server):** `state.filters {q, department_ids, job_ids, contract_states, statuses, employee_ids}` `records_desk.js:69-72`; `onSearch` debounced `:370-374`; `toggleFacet :376-381`; `clearFilters :391-398`; hand-picked arrival `employee_ids :385-389`. Template: rail `records_desk.xml:570-618` — search `:577-581`, hand-picked chip `:583-590`, four facet groups `:592-609`, match line `:611-616`. No sort/dates.
- **Coach:** `rd-who` on the rail (`:570`); others rd-head `:497`, rd-scheme `:503`, rd-file `:164,:193`, rd-history `:528`, rd-review `:533`, rd-empty `:544`, rd-fields `:623`. Anchors (screen `records`): all eight. Replica `records()` `:2106-2171` draws rd-who, rd-fields, rd-head, rd-scheme, rd-file, rd-history, rd-review. Lessons: 14 entries; rd-who 0, rd-fields 1, rd-head 2, rd-scheme 3.
- **Sections (mirror pb_people so saved views can be shared):** department `department_id` PIN · status `contract_id.state` (today: latest-contract post-filter `:478`; pb_people uses `contract_id.state` `pb_people.py:261`) choice incl. "No contract" PIN · employment — **non-domain** feed signal `statuses` (`:531-535`); keep as a custom section via `_pbf_section_domain` override returning `('id','in',ids)` PIN · job `job_id` · scheme `contract_id.struct_id.active_formula_config_id` or run-time `records_config_id` · company `company_id` · manager `parent_id` · bank `account_number` set/empty · joined `first_contract_date` · ends `contract_id.date_end` · picked `id in employee_ids` (arrival, hidden).
- **Views:** All people · Running contracts · No contract · Resigned per feed · Hand-picked (transient).
- **Effort: M** — mostly mapping `filters` → `pbf_domain` and swapping the rail for `PbFilterLayout`; the virtual window, "Set for all N shown" and "select all matching" must keep calling `matching_ids` with the kit's filters.
- **Risks:** bulk actions read the filtered set — `setForTargets` scope 'shown' (`records_desk.js:511-515`), `menuClear` (`records_grid.js:594-598`), `onSelectAllMatching` → `matching_ids(filters)` (`:496-499`). Facet counting is RD11-sensitive (147 s incident, `py:466-476`) — `pbf_counts` must not re-introduce per-person questions for the feed-status facet. `statuses` is not a domain and `_pbf_list_values` assumes a field. Export reads the same filters (`:738-760`).

### 23 · pb_structures · Salary Structures · `pb_structures`
h1 `structures.xml:13`; action `pb_structures_action.xml:4`; registered `structures.js:106`. **Small config catalogue** (typically < 30 rows).
- **Kind:** card list with a numbers line whose Active/Draft/Deprecated figures filter, search, date chips, country chips, schedule chips.
- **Rows:** `hr.payroll.structure`; `pb.structures.get_board()` `pb_structures/models/pb_structures.py:45-93` — `S.search([], order='name', limit=ROSTER_LIMIT)` `:59` (`ROSTER_LIMIT = 240` `:20`), **no company domain by design** (`:49-51`), not paged; `total = search_count([])` `:91`.
- **Current filters (client):** `search`, `status`, `country`, `schedule` (derived from rows `get schedules :42-45`), `dateFilter/from/to` over `write_date[:10]` — `useState :28-31`, `get filtered :86-96`, `_inDate :77-85`. Template: glance-as-filter `structures.xml:23-28`, search `:32-35`, date chips `:38-48`, country + schedule chips `:49-58`, foot `:78-81`.
- **Coach:** `sr-filters` on the whole panel (`:30`); `sr-kpis :23`, `sr-roster :62`, `sr-new :16`, `sr-openall :80`. Anchors (screen `structures`): all five. Replica `structures()` `:1550-1597` draws all five. Lessons: 9 entries; sr-filters 0, sr-kpis 2, sr-roster 2.
- **Sections:** status `structure_state` (`pb_hr_payroll_base/models/hr_payroll_structure_base.py:118`; fallback `active`) PIN · country `payroll_country_code` (`:54`) or `country_id` (`:51`) PIN · schedule `schedule_pay` (`:83`) PIN · company `company_id` · base `is_base_structure` (`:79`) · currency `currency_id` (`:68`) · formula `use_formula_computation` (`hr_payroll_structure_formula.py:40`) · contract_type `contract_type_ids` (many2many — not a kit path) · parent `parent_id` · employees `employee_count` (`:115`, manually refreshed) · updated `write_date`.
- **Views:** All · Active · Drafts · Deprecated · Updated this month.
- **Effort: S** — one template + one abstract model, no bulk, no second source. The kit buys consistency and saved views, not scale.
- **Risks:** `_pbf_base_domain` must stay `[]` (company ignored on purpose) unless the owner decides otherwise; `country` chip matches the derived `_country(s)` string (`py:23-25`); `HubBackChip` arrival.

### 24 · pb_statutory · Statutory · Insurance & Tax · `pb_statutory`
h1 `statutory.xml:17`; action `pb_statutory_action.xml:4`; registered `statutory.js:312`.
- **Kind:** settings cockpit with THREE list views behind a segment: (a) Insurance policies cards, (b) Tax tables cards, (c) Data — four VN tables (policy / tax / adjustment / dependent) as a facet grid + drawer. (a)/(b) are small catalogues; (c) adjustments/dependents can be large.
- **Rows (several):** `pb.statutory.get_statutory_data(country)` `pb_statutory/models/pb_statutory.py:116-299` — policies `vietnam.insurance.policy.search([], limit=120)` `:222-230`; tax = **union** of `vietnam.tax.table` (`:233-242`, 120) and `hr.payroll.tax.table` (`:245-256`, 120). `get_ledger(kind) :329-344` → `_ledger_policy :411-445` (400), `_ledger_tax :500-526` (400), `_ledger_adjustment :569-603` (400, `_employee_scope :303-326`), `_ledger_dependent :651-690` (400). Not paged.
- **Current filters (client):** rosters: `showActive`, `year` (tax) — `js:69-72`, `filteredPolicies :269`, `filteredTax :270-272`; `taxCountry` select server (`setTaxCountry :110-120`). Data: `lsearch`, `f{facet}` per ledger (`:187-215`), facets from rows (`py:399-407`). Template: "Active only" `statutory.xml:117`/`:137`, year chips `:138-140`, ledger facets `:177-200`, ledger search `:201-204`.
- **Coach:** `st-filters` on the policies "Active only" group only (`:116`); tax chips and Data facets none; `st-data :161`. Anchors (screen `statutory`): st-new, st-kpis, st-rates, st-effective, st-slabs, st-filters, st-roster. Replica `statutory()` `:1597-1710` draws all; `st-data` 0. Lessons: 15 entries; st-filters 0, st-kpis 1, st-roster 5.
- **Sections (one spec per list):** active — policy `active` (`vietnam_insurance_policy.py:45`) / tax `active` or `hr.payroll.tax.table.state` (`payroll_tax_table.py:55`) PIN · company `company_id` PIN · effective — policy `effective_date` (`:30`); tax `tax_year` or `effective_from` PIN · ends policy `end_date` (`:35`) · country tax `country_code` (`:47`) · method tax `method` (`:51`) / `basis` (`:54`) · Data: adjustment `state` (`vietnam_insurance_adjustment.py:124`), `insurance_type` (`:66`), `adjustment_type` (`:59`), `adjustment_date` (`:39`); dependent `status` (`vietnam_employee_dependent.py:63`), `relationship` (`:31`); `employee_id.department_id` for both.
- **Views:** Policies: Active · All incl. archived. Tax: Published this year. Adjustments: Draft · This month. Dependents: Pending · Approved.
- **Effort: L** — six row sources across five models in one component; the tax roster is a **union of two models** which one `_pbf_model` cannot express; the Data view is the cleaner first target (one `_pbf_model` per `kind`).
- **Risks:** `_employee_scope` subquery (`:303-326`, W97) must be carried into `_pbf_base_domain` for adjustments/dependents; `taxCountry` switches `kind` (`js:113-118`); legacy VN tax rows open a different detail (`openTax :275-283`).

---

## D. Workforce, time and expenses

Learn plumbing for this group: no product anchors for pb_attendance_flow, pb_business_trip, pb_expenses_hub, pb_me_expense, pb_hr_workforce_planning, biz_week_grid; pb_timeoff has `wf-timeoff, wf-outtoday, wf-leave-queue` (screen `wftimeoff`), OT desk `wf-overtime, wf-ot-bonus, wf-ot-queue, wf-ot-rules` (`wfovertime`); `screens.js` has `wftoday()/wftime()/wfclose()` (`:2220/:2255/:2299`) and the `wftime()` replica draws the leave queue (`:2276-2277`) and OT queue (`:2284-2291`).

### 25 · pb_attendance_flow · Attendance Control (Exceptions & corrections) · `pb_attendance_flow`
Action `pb_attendance_flow/views/attendance_flow_action.xml:3-5`; h1 `static/src/xml/pb_attendance_flow.xml:21`. Also mounted twice by the Time hub as "Exceptions" and "Import" lenses (`pb_time_hub/static/src/js/time_hub.js:27,38,122-123`).
- **Kind:** two-column board: exceptions queue (kind tabs) + corrections pipeline cards; composer and import stepper views (`view: board|composer|import`, JS `:78`).
- **Rows:** (a) Exceptions are NOT records — derived from `pb.attendance.exception.engine._get_exceptions()` (`models/attendance_exception.py:83-219`) over `hr.shift.planning` + `hr.attendance`; cohort cap 400 employees (`models/attendance_cockpit.py:23,95-97`), 14-day window (`:22,:146`). (b) Corrections: `hr.attendance.correction`, `Corr.search([], limit=80)` (`:213`), not paged. Both via `pb.attendance.flow.get_control_data(date_from,date_to,department_id,employee_id)` (`:124`).
- **Current filters:** `activeKind` (`pb_attendance_flow.js:80`) → `visibleExceptions` client (`:183-187`), tabs xml `:64-75`. Embedded only: week + department + pinned person from `wf_context` server-side (`:124-130`), person chip clearable (xml `:54-62`; `clearPersonFilter :138`). No search; no filter on corrections.
- **Coach:** none. Time hub's `wf-exceptions` (screen `wftime`) wraps the lens; replica shows only a chip + note (`:2257-2258, :2271`); lessons `wftime` 6, `wf-exceptions` 0.
- **Sections (corrections — the only model-backed rows, `hr.attendance.correction`):** status `state` (`attendance_correction.py:77-82`) choice PIN · employee `employee_id` PIN · department `department_id` (`:55`) PIN · day `date` (`:58`) · type `correction_type` (`:60-64`) · from_exc `exception_kind` (`:72`) char · manager `manager_id` (`:52`) · company `company_id` (`:84`) · failed `apply_error != False` choice. Exceptions queue would need a facet over `hr.shift.planning.compliance_status` (`shift_planning.py:37-53`) + `hr.attendance` with `check_out=False` — two models, not one `_pbf_model`.
- **Views (corrections):** Waiting for approval · Applied this week · Failed to apply · Mine to review · All.
- **Effort: L** — two row sources, one computed (no model); week/department/person come from shared context when embedded; mounted in two hosts.
- **Risks:** exceptions need a materialised model or a non-model row source; corrections scoped by record rules not company (`:210-213`); `_changed()` must never run from `load()` (W21 loop, JS `:141-153`); `seed` prop opens a correction on mount (`:94-96`).

### 26 · pb_business_trip · Business Trips · `pb_trips`
Action `pb_business_trip/views/pb_trips_action.xml:3-5`; also the Expenses hub "Trips" lens (`pb_expenses_hub/static/src/js/expenses_hub.js:48-50`).
- **Kind:** kanban — 5 lanes by state under QuietGlance + QuietSteps, plus a collapsed "refused / cancelled" list (xml `:33-37, :44-92, :95-108`).
- **Rows:** `pb.business.trip`; `pb.trips.get_pipeline_data()` `pb_business_trip/models/pb_trips_cockpit.py:24-90`, `Trip.search([('company_id','in',co_ids)])` with **NO limit** (`:27`), not paged; outputs `lanes` (open) and `closed`.
- **Current filters:** `step` (`pb_trips.js:51`) and `mine` (`:52`) → `visibleLanes` client (`:189-197`); `showClosed :47`. No search/date/department.
- **Coach:** none. No Learn (prose mentions only).
- **Sections (`pb.business.trip`):** step `state` (`pb_business_trip.py:65-74`) PIN · employee `employee_id` (`:32`) PIN · department `department_id` (`:38`) PIN · country `destination_country_id` (`:43`) · starts `date_from` (`:45`) · ends `date_to` (`:46`) · policy `policy_id` (`:50`) · advance `advance_amount` (`:54`) · cost `estimated_total` (`:62`) · manager `manager_id` (`:35`) · company `company_id` (`:76`). "Waiting on me" (`can_act`) is per-record `t._can_current_user_act()` (`pb_trips_cockpit.py:40`); `can_manager_approve` etc. non-stored (`pb_business_trip.py:85-91`) — no domain.
- **Views:** Open trips · Travelling this month · Awaiting authorisation `{step:[finance_approved]}` · With a cash advance · Refused or cancelled.
- **Effort: L** — lanes ARE the step facet (lane counts must come from kit counts), second source for closed trips, per-card approve/refuse + modal, `mine` has no field.
- **Risks:** unbounded search today; money per company currency (`:68-72`); embedded in the Expenses hub (`:26-31`).

### 27 · pb_timeoff · Leave Command Center (approval queue) · `pb_timeoff`
Action "Time Off" `pb_timeoff/views/pb_timeoff_action.xml:4-6`; h1 `static/src/xml/pb_timeoff.xml:24`; Workforce "timeoff" lens (`pb_mission/static/src/js/pb_mission.js:55,163`).
- **Kind:** board — approval queue list (xml `:57-104`) + department×day heatmap (`:107-142`) + paged balance table (`:146-187`); apply-on-behalf modal.
- **Rows:** queue = `hr.leave`, `pb.timeoff._queue()` `pb_timeoff/models/pb_timeoff.py:169-176`: state ∈ (confirm, validate1), `employee_id.company_id` in companies, order `date_from`, NO limit, not paged. Heatmap scan cap 3000 (`:38,:218-226`); balances = `hr.employee` paged 30 (`:39,:259-267`). All via `get_board(month, balance_page)` (`:103`), sudo behind `_require_officer :49-59`.
- **Current filters:** `month` (`pb_timeoff.js:43`, server, heatmap only) and `balancePage` (`:44`). Queue has NO filter/search/sort.
- **Coach:** `wf-timeoff` hero (xml `:15`), `wf-outtoday :44`, `wf-leave-queue` on the queue panel (`:57`) — none on a filter area. Anchors screen `wftimeoff` ×3; no `wftimeoff()` scene but `wftime()` replica uses `wf-leave-queue`/`wf-timeoff` (`:2276-2277`); lessons `wftimeoff` 1, `wf-leave-queue` 2.
- **Sections (`hr.leave`, `hr_holidays/models/hr_leave.py`):** status `state` → choice (confirm "To approve", validate1 "2nd approval", validate, refuse) PIN · type `holiday_status_id` (`:138`) PIN · department `department_id` (`:161`) PIN · employee `employee_id` (`:153`) · from `request_date_from` (`:212`) · to `request_date_to` · days `number_of_days` · backdated `pb_backdated` (`pb_timeoff/models/leave_rules.py:85`) · papers `supported_attachment_ids != False` · company `employee_id.company_id`.
- **Views:** Waiting for approval (default) · Backdated requests · Starting this week · Approved this month · Refused.
- **Effort: M** — three row sources on the board; only the queue converts; approve/refuse per row then `load()` reloads everything (`:132-148`).
- **Risks:** reads are sudo'd (`:105`) — counts must run under the same sudo + company scope; `pbCmd` nonce channel (`:199-203`); replica draws the queue without filters.

### 28 · pb_expenses_hub · Expenses › Claims ("Expense claims") · `pb_expenses_hub` lens `claims`
Hub action `pb_expenses_hub/views/pb_expenses_hub_action.xml:8-10`; lens title `expenses_hub.js:51-53`, gated `hr_expense.group_hr_expense_team_approver` (`:28`).
- **Kind:** **native list view** mounted through `View` (`claims_lens.js:14,26-40`; xml `:14-18`) — not an OWL card list.
- **Rows:** `pb.expense.claim` (`pb_me_expense/models/expense_claim.py:84`); standard list model (web-client paging, default 80); no facade method.
- **Current filters:** the model's search view (`pb_me_expense/views/expense_claim_views.xml:89-106`): fields name, employee_id; filters Waiting approval / Approved / Refused / Paid; group by Status / Employee; default `search_default_waiting` (`claims_lens.js:29`). All server-side via the control panel.
- **Coach:** none. No Learn.
- **Sections (`pb.expense.claim`):** status `state` (CLAIM_STATES `:46-52`) PIN · employee `employee_id` (`:104`) PIN · total `total` (`:117` — **verify `store=True`**) PIN · department `employee_id.department_id` · sent `submitted_on` (`:127`) · decided `decided_on` (`:128`) · paid `paid_on` (`:130`) · receipts `receipt_count` (`:115`, verify stored) · category `expense_ids.product_id` (one2many hop — not a kit path) · company `company_id` (`:107`).
- **Views:** Waiting approval (default) · Approved, not yet paid · Paid this month · Refused · Sent this month.
- **Effort: M** — there is no OWL list to re-skin: the lens needs a facade model + a card/table template, keeping "row opens the native form" (`claims_lens.js:44-53`).
- **Risks:** decisions are taken from Approvals, not here (`:7-9`) — no bulk to wire; the native search view remains for the act_window (`expense_claim_views.xml:108-114`). Portal `/my/expenses` (`pb_me_expense/controllers/portal.py:138-140`) is the employee's OWN claims — out of scope.

### 29 · pb_hr_workforce_planning · Workforce Planning › Employee Forecast Detail · `wfp_dashboard`
Action `pb_hr_workforce_planning/views/workforce_planning_dashboard_views.xml:4-6`; h1 xml `:13`; table h3 `:234-235`.
- **Kind:** sortable table inside the Compensation tab of a 5-tab chart dashboard (xml `:231-281`).
- **Rows:** `wfp.employee.forecast` (`models/employee_forecast.py:12`); `wfp.planning.scenario.get_dashboard_data(scenario_id)` (`models/planning_scenario.py:423`), list `:461-486` = every non-excluded forecast (`:429-431`), NO limit, not paged, sorted by |increase|.
- **Current filters:** `searchQuery` (`workforce_planning_dashboard.js:102`), `sortField`/`sortOrder` (`:103-104`) → `filteredEmployees` client (`:424-437`); search xml `:237-239`; column sort `:245-254`. Scenario `<select>` (xml `:18`) is the server param.
- **Coach:** none. No Learn.
- **Sections (`wfp.employee.forecast`):** department `department_id` (`:44`) PIN · rule `applied_rule_id` (`:163`) PIN · pct `increase_pct` (`:137`) PIN · job `job_id` (`:50`) · manager `manager_id` (`:56`) · amount `increase_amount` (`:132`) · country `country_code` (`:62`) char · location `location` (`:66`) char · grade `contract_id.grade_id` · tenure `tenure_months` (`:172`) · excluded `is_excluded` (`:175`). Base domain `scenario_id = selected`. `compa_ratio` is read off the contract at serialisation (`:484`) — not a field.
- **Views:** Everyone in the scenario · Increases over 10% · No rule applied · Biggest increases (sort) · Excluded people.
- **Effort: M** — sorts map 1:1 to `_pbf_sorts`; but the component is a 1,595-line legacy dashboard (fa icons, Chart.js, 5 tabs) and the dept chart reads the unfiltered map (`:433-444`).
- **Risks:** mixin should go on a new facade or on `wfp.planning.scenario` with `_pbf_model()='wfp.employee.forecast'`.

### 30 · pb_hr_workforce · Overtime Desk ("Approve overtime & manage limits") · `pb_ot_desk`
h1 `pb_hr_workforce/static/src/xml/pb_ot_desk.xml:25`; Workforce "overtime" lens (`pb_mission.js:56,169`). No standalone `ir.actions.client` found; tag registered `pb_ot_desk.js:314`.
- **Kind:** approval queue of cards with checkbox bulk tray (xml `:42-104`) + config gallery (`:107-140`); second view "Bonus Hours review" with its own filter rail + grouped table (`:148-230`).
- **Rows:** `hr.overtime.request` (`models/overtime_request.py:22`); queue = `pb.ot.desk.get_desk()` (`models/ot_desk.py:86-137`): `state='submitted'`, company-scoped, sudo, order date desc, NO limit (`:101-105`). Bonus view = `get_bonus_hours(filters, page, group_by)` (`:348`), domain `_bonus_domain :294-330`, scan cap 5000 (`:24`).
- **Current filters:** queue: none (only `selected` bulk map JS `:44`; `selectAll` reads `this.queue :119-122`). Bonus view: preset/date_from/date_to/employee/department/overtime_type/min_hours/group_by/page — all server (JS `:61-75, :248-259`; xml `:162-200`).
- **Coach:** `wf-overtime` (`:13`), `wf-ot-bonus :28`, `wf-ot-queue :42`, `wf-ot-rules :107`; none on a filter area. Anchors screen `wfovertime` ×4; `wftime()` replica carries three (`:2284-2291`); lessons `wf-ot-queue` 4, `wf-ot-rules` 3.
- **Sections (`hr.overtime.request`):** status `state` (`:76-81`) PIN · department `department_id` (`:31`) PIN · type `overtime_type` (`:58-63`) PIN · employee `employee_id` (`:28`) · day `date` (`:38`) · planned `planned_hours` (`:40`) · bonus `bonus_hours` (`:51`) · rule `overtime_config_id` (`:65`) · manager `manager_id` (`:34`) · company `company_id` (`:83`). Ceiling bars (`q.ceiling`, `q.split`) come from `hr.attendance.weekentry.get_ot_ceilings` (`ot_desk.py:109-110`) — card decoration, not a facet.
- **Views:** To approve (default) · Approved this month · With bonus hours · Weekend & holiday · This week.
- **Effort: M** — bulk approve/refuse reads `selectedIds` and `selectAll` iterates `this.queue` (must become the filtered page); the Bonus review is a second surface over the SAME model with a different base domain — second `_pbf_screen` facade or leave the rail.
- **Risks:** a pure bonus viewer gets an empty queue (`:87-96`); `pbCmd` channel (JS `:223-239`); `wf-ot-queue` must stay on the queue panel.

---

## E. Integrations, import, access, pay review

### 31 · pb_integrations · Integrations (Connectors) · `pb_integrations`
Action `pb_integrations/views/pb_integrations_action.xml:3`; h1 `static/src/xml/integrations.xml:19`.
- **Kind:** card list (`:85-107`) with a KPI quiet-line and a Connectors / Data segment (`:43-52`).
- **Rows:** `hr.integration.connector` (`pb_hr_payroll_formula/models/integration_connector.py:29+`); `pb_integrations/models/pb_integrations.py:111` `get_board` → `C.search([], order='name')` `:115`, **no limit, not paged**. `types` counts from rows `:161-172`.
- **Current filters (client):** `integrations.js:76-77` `search`, `status` (`STATUS_CHIPS :39`), `type`, `recency` (`RECENCY_CHIPS :43`); `get filtered :167-176`; recency derived in JS (`_hoursSince :142`, `_matchRecency :156`). Template: status chips `:58-63`, search `:64-67`, recency `:70-75`, type `:76-81`. KPI line toggles the status chip (`glance :255-273`).
- **Coach:** `ig-filters` (`:56`), `ig-roster :85`, `ig-kpis :32`. Anchors `ig-connect, ig-kpis, ig-filters, ig-roster` (screen `integrations`). Replica draws all 4. Lessons: ig-roster 4, ig-kpis 1, ig-connect 1, ig-filters 0; screen 17 hits.
- **Sections:** status `connection_status` (`:200`) PIN · type `connector_type` (`:35`) PIN · synced `last_sync` (`:207`; none "Never synced") PIN · company `company_id` (`:60`) · country `country_code` (`:265`) · sync_result `last_sync_status` (`:228`) · auth `auth_type` (`:80`) · feeds `endpoint_count` (`:174`) · synced_records `total_synced_records` (`:257`) · active `active` (`:54`; base domain must drop active_test).
- **Views:** All · Needs attention `{status:[error]}` · Never synced · Synced today · Spreadsheet feeds `{type:[excel]}`.
- **Effort: S — borderline value:** live tables hold ~24–31 connectors (`pb_import.py:139-144` comment); close to the "< 30 config rows → keep chips" line. Convert only if the module is being touched anyway.
- **Risks:** the same `get_board` payload feeds `composerConnectors` (`integrations.js:483-490`) and the Data view's deep-link scope — keep `get_board` or add a light `connectors()` call; `hasMapping` door per card (`:229-247`); `feeds_known` honesty flag (`:217`).

### 32 · pb_integrations · Integrations › Data (Field mappings / Data store / Transformation rules) · `pb_integrations` (view `data`)
- **Kind:** table with tab strip (`integrations.xml:117-137`), row click → `WfDrawer` (`openRow integrations.js:416-449`); rule rows open the Rule Composer (`:421-428`).
- **Rows — THREE models** (`LEDGERS` `pb_integrations.py:47-60`): `get_ledger(kind, connector_id, data_type, endpoint_id)` `:240-282` → `hr.integration.field.mapping` (`_ledger_mapping :341`, `:344`); `hr.api.data.store` (`_ledger_store :469`, `order='pull_date desc' :473`); `hr.api.transformation.rule` (`_ledger_rule :568`, `active_test=False :573-574`). `LIMIT = 400` (`:42`); **not paged**; `total` is a `search_count` so the footer says "newest 400 loaded" (`footLabel :400-409`).
- **Current filters:** server-side scope only (connector / data_type / endpoint deep-link `:257-280`); everything else client: `lsearch` + `f{}` (`integrations.js:96`), `_matchRow :348`, `ledgerRows :356`, `chipCount :360`, `clearLedgerFilters :367`. Facets built **from the loaded 400 rows** (`_facets :825-840`) — the same count lie People fixed. Template: facets `:166-188`, search `:189-192`, scope chips `:141-160`.
- **Coach:** `ig-data` (`:118`) — **not declared in anchors.json product**; check pb_learn's stray-anchor gate before touching. 0 replica / lesson hits.
- **Sections (per model, `pb_hr_payroll_formula/models/`):** *Data store* (`api_data_store.py`): `connector_id` (`:50`) PIN · `state` (`:153`) PIN · `data_type` (`:73`) PIN · `endpoint_id` (`:54`) · `employee_id` (`:80`) · `pull_date` (`:141`) · `period_from` (`:88`) · `pull_triggered_by` (`:148`) · `has_changes` (`:134`) · `import_batch_id` (`:164`) · `company_id` (`:169`). *Field mappings* (`integration_field_mapping.py`): `connector_id` (`:35`) PIN · `active_state` (`:261`) PIN · `endpoint_id` (`:53`) PIN · `target_rule_id` (`:96`) · `transformation_type` (`:178`) · `has_transform_error` (`:276`) · `is_severed` (`:133`) · `source_data_type` (`:85`) · `is_required` (`:217`) · `active` (`:253`). *Rules* (`api_transformation_rule.py`): `connector_id` (`:319`) PIN · `active` (`:436`) PIN · failing `last_error != False` (`:485`) PIN · `rule_type` (`:352`) · `source_data_type` (`:358`) · `builder_mode` (`:441`) · `record_source` (`:447`) · `last_error_at` (`:490`). "Feeds" column (`:598`) is Python-derived.
- **Views (Data store):** Everything · Pulled today · Failed pulls · Not matched to anyone · Changed since last pull.
- **Effort: L** — three models under one action → three thin `AbstractModel`s or a `kind`-switched spec. Data store alone = M and is the one that actually outgrows 400 rows.
- **Risks:** two deep-link scopes must become pre-set, droppable filters; row payload (`cells/badge/_f/_s`) shared with the drawer (`get_ledger_detail :285`) and the Rule Composer; `_facets` is copy-pasted in `pb_insights.py:1160` and the pay-run ledgers — retire per conversion; "New rule" lives in the tab strip (`:133-136`).

### 33 · pb_import · Import Data › Recent batches · `pb_import`
Action `pb_import/views/pb_import_action.xml:3`; h1 `import.xml:12`. Also the Pay Run hub's Import lens (`props.embedded`, `import.xml:10`; `connectorBack import.js:28,178`).
- **Kind:** table (`import.xml:96-111`), row click → batch cockpit (`openBatch import.js:147`).
- **Rows:** `hr.payroll.import.batch` (`pb_hr_payroll_formula/models/payroll_import_batch.py:92`); `pb_import/models/pb_import.py:89` `get_import_data` → `Batch.search_read(DOM, [...], order='create_date desc, id desc', limit=20)` `:109-114`, DOM = company only (`:92`). **Cap 20, not paged.** KPIs/pipeline counts via `read_group` over ALL batches (`:100-107`) → chips count 20 rows while the KPI counts everything.
- **Current filters (client over 20 rows):** `import.js:57-58` `filter` (all/draft/in_progress/done/errors) and `step`. `_inFilter :126-133`, `filteredBatches :134`, `countFor :135-142`, `setFilter :143`, `pickStep :103`, `showingLine :107-119`. Template: QuietGlance `import.xml:18-23`, QuietSteps `:56-67`, status chips `:88-94`. No search/sort/date.
- **Coach:** `im-batches` on the whole panel incl. chips (`:85`); `im-pipe :56`; `im-kpis :18`. Anchors `im-kpis, im-cta, im-launches, im-pipe, im-batches` (screen `import`). Replica: im-batches 1, im-kpis 1. Lessons: im-batches 1, im-pipe 2, im-cta 8; screen 16 hits.
- **Sections (`payroll_import_batch.py`):** state `state` (`:263`) PIN · source `source_type` (`:119`) PIN · period `date_from` (`:167`) PIN · scheme `formula_config_id` (`:131`) · connector `connector_id` (`:125`) · company `company_id` (`:203`) · country `country_code` (`:183`) · errors `error_lines` (`:239`) number or choice >0 · run `payslip_run_id` (`:353`) has/none · one_time `one_time` (`:298`) · created `create_date`. Client "in_progress" (`IN_PROGRESS import.js:29`) → built-in view over `state`; "errors" (`state=error OR error_lines>0`) → OR-domain choice.
- **Views:** All · Needs attention · In progress `{state:[loaded,matched,validated,processing]}` · Done this month · Drafts.
- **Effort: S–M** — one model; QuietSteps/Glance must read kit counts instead of `pipeline`/`kpis` from the 20-row payload. M only for the embedded-lens mode.
- **Risks:** `PbFilterLayout` inside the Pay Run hub lens (W17 title ownership); `pb_filter_kit` becomes a new manifest dependency; replica draws `im-batches`; six modules `_inherit` the batch model — field paths above are all on the base.

### 34 · biz_access · Access › People ("People with access") · `pb_access_board` lens
Action `biz_access/views/access_views.xml:360`; lens strip `access_board.xml:179`; people lens `:425-488`.
- **Kind:** master-detail — left list (`:459-487`), right "passport" (`:491+`).
- **Rows:** `res.users` (sudo) — `biz_access/models/pb_access_facade.py:1286` `people(search)`: `res.users.sudo().search([active, share=False OR employee login])` `:1313-1315`, then `visible_people()` `:1316` (Python), name/login substring in Python `:1317-1319`, me-first sort `:1326`, cap `PEOPLE_CAP = 200` (`access_common.py:182`) `:1327`; not paged. Non-managers get a list of one (`:1295-1304`). Row = composite (`_person_row`: holders per profile, lent counts, job title).
- **Current filters:** `peopleSearch` only (`access_board.js:168`; `loadPeople :429` re-RPCs; `onPeopleSearch :459`). Template: search `access_board.xml:439-445`. No chips/sort/date.
- **Coach:** none on the people list. Anchors for `access_board.xml`: `ac-head, ac-seeas, ac-handover, ac-newrole, ac-banner, ac-tabs, ac-rolecard, ac-builder` (screen `access`). Replica draws 6. Lessons: screen 13 hits.
- **Sections (`res.users`):** kind — choice employee/staff (`share` + employee link; mirrors `ps.kind :472`) PIN · role — holders come from `_holders_by_profile :1321` backed by `pb.role.profile` → groups; needs a domain-able path (e.g. `groups_id`) — **unverified** PIN · department `employee_ids.department_id` (one2many hop — not a kit path; use `employee_id` if present) PIN · company `company_ids` · job `employee_ids.job_id` · lent — choice (active delegation, `_lent_counts :1322`, model `pb.access.delegation`) · login — choice (`login_date` none = never signed in) · created `create_date`.
- **Views:** Everyone · Employee logins · Never signed in · Holding a lent role.
- **Effort: M–L** — composite rows built in Python; `visible_people` and the "list of one" rule are not domains; `_pbf_base_domain` must reproduce both or the kit widens what a non-manager can see.
- **Risks:** **security-sensitive** (sudo + explicit visibility rule) — a Fable-coded phase, not Opus, if converted; first-row auto-pick (`loadPeople :440-448`) depends on `rows[0]`/`is_me`.

### 35 · pb_pay · Pay review › worksheet · `pb_pay` (`pb_tab: 'review'`)
Action `pb_pay/views/pb_pay_action.xml:31`; h1 `pay.xml:24`; worksheet `pay_review.xml:200-300`.
- **Kind:** editable table, row select/multi-select + bulk actions (`pp-bulk :212-246`), inline % edit (`:288-293`).
- **Rows:** `pb.pay.review.line` (`pb_pay/models/pb_pay_review.py:207+`); `pb_pay/models/pb_pay_reviews.py:286` `open_review(review_id, page, filters)` → `_filtered_lines :332-357` (Python `filtered()` lambdas over `review.line_ids`, then sorted), window `PAGE = 120` (`:36`) `:294-295`; **paged yes** (server), filtered server-side **but not by domain**.
- **Current filters:** `state.filters {which, text}` (`pay_review.js:162`); `setFilter :306`, `setSearch :311` → re-call. `which` ∈ Everybody / My team / Not scored / Stops approval / Paid below the band / No rise (`filterDefs :93-102`). Template: chips `pay_review.xml:203-207`, search `:208-210`. No sort control (server sorts team, name `:355`).
- **Coach:** `pp-worksheet` (`:200`), `pp-bulk :212`; plus `pp-reviews, pp-review-row, pp-meters, pp-stepper, pp-review-actions, pp-stops, pp-calibration, pp-second-look, pp-changes` → screen `payreview`. Replica draws 13 `pp-*`. Lessons: screen 23 hits; pp-worksheet 2, pp-bulk 1.
- **Sections (`pb_pay_review.py`):** team `department_id` (`:219`) PIN · score `rating` (`:228`) number / choice "Not scored" = 0 PIN · band position — choice on `has_band` (`:227`) & `position_pct < 0` (`:226`) PIN · manager `manager_id` (`:217`) ("My team" = manager = my employee) · job `job_id` (`:220`) · division `division_id` (`:221`) · band `band_id` (`:222`) · rise `proposal_pct` (`:233`) · state `state` (`:262`) · stops approval — **JSON-derived** (`chips` Json `:238`; `_filtered_lines :342`) → needs a stored boolean (e.g. `blocks_approval`).
- **Views:** Everybody · My team · Not scored · Stops approval (after the stored field) · Paid below the band · No rise.
- **Effort: M** — base domain `review_id = X`; search fields employee/job/department names; the four bulk actions and calibration read `rows`/`selection` ids and must keep working on a kit page; `can_names` privacy stays.
- **Risks:** 4,500-row reviews exist (`pay_review.js:127-130`); `unrated`/`total_rows` header counts should move to kit counts; the "awaiting" focus and list/calibration `view` are outside the panel.

---

## F. Cross-cutting findings

1. **Only eight screens carry a coach anchor on the filter area today**: `ct-filters` (reserved), `sr-filters`, `st-filters` (policies only), `ig-filters`, `lg-facets`, `pk-divchips`, `rd-who` (whole rail), `im-batches` (whole panel), `ps-chips` (steps). Every other filter block is un-anchored, so the converted layout can carry one `coach` key per screen (as `pe-filters`) without breaking existing Learn refs, which sit on glance/steps/tabs/cards. `ig-data` is a live `data-coach` **absent from anchors.json**.
2. **The replica is wider than Pay Run.** `screens.js` redraws Contracts, Contract renewals, Probation, Growth plans, New joiners, Exits, Awards, Hiring, Ask HR, Approvals, Matrix, Pay Runs, Payslips, Ledgers, Reports, Records, Structures, Statutory, Integrations, Import, Access, Pay review, Time (leave + OT queues). Any of those conversions is a two-edit job (template + replica + lessons), per the standing rule.
3. **Facets counted from a capped window** (`_facet(rows)` / `_facets(rows, spec)` / `_rows_facet`) exist in pb_contract_lifecycle, pb_probation, pb_pip, pb_onboarding, pb_offboarding, pb_lifecycle, pb_hiring, pb_assets, pb_rnr, pb_integrations (`:825`), pb_insights (`:1160`), pb_payrun_ledgers (`:43`), pb_statutory (`:399`), pb_import (20-row window vs all-batch KPIs). Each is the People defect ("chip says 208, list holds 11"); every conversion should delete its copy.
4. **Bulk actions reading the client-filtered array** (the kit's page must become the bulk scope): Applicants (`sel` move), Ask HR (take/hand/close), Assets (`picked` → `bulk_set_state`), Pay Runs (`monthBatches`, `columnBatches`), Records Desk (`setForTargets 'shown'`, `matching_ids`), Overtime (`selectAll` over `this.queue`), Pay review (four bulk verbs), Matrix (rejected).
5. **Per-reader "mine / waiting on me" facts** are Python, not domains, on Hiring roles, Applicants, Offers, Ask HR, Approvals, Trips, F&F, Pay Runs (`pb_awaiting_me` is the one with a `search=`). Keep as glance figures or chips layered after the kit's domain, or add a stored "current approver" field.
6. **Kit path rule** (`_pbf_resolve` only walks many2one): blocked paths include interview `panel_employee_ids`, approval `seat_ids`/`subject_user_ids`, pay run `slip_ids.company_id`, structures `contract_type_ids`, expense `expense_ids.product_id`, access `employee_ids.*`. The `any` subdomains proposed for journeys/probation/exits (one2many `task_ids`, `clearance_ids`, `pb_probation_review_ids`) need either a `choice` section with a literal domain or a mixin extension — confirm the mixin accepts a raw domain in `choice.options[].domain` for one2many `any` (it does for plain fields, `pb_people.py:255-256`).
7. **localStorage filter memory** on Ask HR (per user), Applicants, Offers; `useNavigationState` on Pay Runs and Approvals — migrate or deliberately drop.
8. **Programmatic entry** (a door sets filters): Hiring `openRegister(tab,{flag,step})`, Approvals `arrival`/`locate_request`, People → Records `employee_ids`, Probation `person:<id>`. The kit has `toggleFilters`; the handover should name the "set filters from context on mount" seam.
9. **Refusal payloads** (`_can_read` returning `{refused: …}`) on Growth plans, Awards, Group room — kit calls (`pbf_layout`, `pbf_counts`) need the same gate.
10. **Sudo reads per row** (pb_contract_lifecycle, pb_probation, pb_pip, pb_comp_ben, pb_timeoff, pb_ot_desk, access) — a kit search over `employee_id.*` by a narrow-group user may hit field access (R56). `pb_probation_state` carries `groups='hr.group_hr_user'`.
11. **Two mount points** (standalone + hub lens with `embedded`): Pay Runs, Payslips, Ledgers, Import, Payroll Report, Attendance Control, Trips, Time off, OT desk, Ask HR (lens only), Claims (lens only). `PbFilterLayout` must respect W17 (host owns the title).
12. **Unbounded searches today**: Trips, Time-off queue, OT queue, Payslip review (one run), Payroll Report (one run), Integrations connectors, Workforce planning — paging is a win, not just consistency.

---

## G. Rejected (examined, not a multi-record records list)

| Where | Path | Reason |
|---|---|---|
| pb_comp_ben · Payroll calendar | `paycal_board.js`, `comp_ben_views.xml:460-462` | Countdown hero + 12-month strip for one year; numbers line filters nothing (`paycal_board.js:101`). |
| pb_contracts · Contract drawer / page | `contract_360.js`, `contract_detail.js`, `pb_contracts_action.xml:8-11` | Single record. |
| pb_pip · "Ask HR about someone in my team" | `pip_request.js`, `pip_views.xml:282-284` | Single-record request wizard. |
| pb_lifecycle · Lifecycle hub | `lifecycle_hub.js:110` | Redirect function, no UI. |
| pb_contract_lifecycle · decision drawer, extension/typing dialogs; `pb.contract.review`/`.extension` registers | `contractlife_board.xml:317-631`; `contract_lifecycle_views.xml:144,231` | Single-record panels; the registers are native act_window lists. |
| pb_probation / pb_onboarding / pb_offboarding drawers + dialogs | — | Single-record panels keyed on the open row. |
| pb_hiring · Role page › Board (`hb-board`, `filteredCards`) | `hiring_board_p1.xml:107`, `hiring_board.js:1520` | One role's ≤120 cards with one glance toggle; is the Applicants register narrowed to one job. Drag, `sel` bulk, column folding, keyboard nav all keyed on `filteredCards`. Fold into #11 later. |
| pb_hiring · Resume bank | `hiring_privacy_p4.xml:164`, `hiring_privacy_p4.js:321-377` | Already a paged server search (`search_bank`); not examined in depth — a later S/M candidate, not in this wave. |
| pb_rnr · The recognition wall | `rnr_wall.xml:29`, `pb_rnr_wall.py:55-103` (`WALL_CAP = 30` `:33`) | 30-tile mood wall, one chip row, "what you can take in standing up" by design. |
| pb_approval_config · Approval Matrix › Matrix tab | `matrix_room.xml:191` (`am-filters`), `matrix_facade.py:207-247` (`MAX_ROWS = 400` `:39`) | Config table; row `status` is Python-derived from workflow versions; bulk "No approval needed" bound to the client-filtered set. Keep its chips. |
| pb_approval_config · Matrix › People & backups | `people.xml:17`, `people_tab.js:109` | Role × scope grid; search lives inside the assign drawer. |
| pb_approval_config · `PickerDrawer` | `picker_drawer.js:113-119` | In-dialog people picker. |
| pb_approval_config · Matrix › History tab | `history_tab.js:38-55` | Audit feed, one chip row, already server-side + cursor paged. |
| pb_assets · Requests segment | `pb_assets_board.py:272-297` | 60-row digest with a 4-step strip only. |
| Typeahead pickers inside dialogs (Ask HR hand-to, R&R employee options, Vendors owner/department, Assets hand/ask) | — | Not screens. |
| pb_payroll_templates · "Review monthly inputs" / "Input changes" | `monthly_review.js:43-48,67-73`; `run_input_review.js:58-76`; `input_review.py:205-327` | Modal `Dialog`s over an in-memory workbook grid with cell-level filters and column tabs; no records model; edits and `selectVisible` act on the filtered page. Main action "Configure Templates" is a layout designer. |
| pb_group · Your group | `pb_group_room.py:124` (`Group.search([], limit=1)`), `group_room.xml:273-301` | One-record settings room; division cards have no filter. |
| pb_hr_workforce · Payroll Report › Dept Summary tab | `payroll_report.py:165-175` | Aggregate table + donut. |
| pb_payruns · native kanban twin | `payruns_kanban.js:275-278` | `searchModel` wrapper on the native kanban (own status/date/division chips, demo June-2026 pre-filter). Retire or leave out — not an OWL cockpit list. |
| pb_statutory · rates / brackets panels | `statutory.xml:50-89` | Single-record detail. |
| pb_hr_workforce · Weekly Entry + biz_week_grid | `week_grid.js:88-95, :267-279`; `attendance_weekentry.py:28,139`; `attendance_weekgrid.js:55-56,128-130` | Timesheet EDITOR (employees × Mon–Sun cells, staged edits/undo); week + department come from shared `wf_context`; patched by `pb_timesheet_approval/.../week_approval.js:20-22`. |
| pb_workseg · "Where they work" / "Same person?" | `assignments.js:154-160, :171-184`; `pb_assignments.py:303` | ONE person's month strip + computed merge-suggestion review. The `pbim-chip` strip at `workseg.xml:99-101` is that person's employments. |
| pb_team · Team Approvals | `pb_team.js:24-44` | Redirect to the Approvals inbox. |
| pb_home_hub · Home › Team lens | `team_lens.xml`, `team_facade.py:55,195`, `team_lens.js:62,115-125` | Face strip of direct reports (cap 40) lit by hero numbers, sections capped at 5 rows; no search. |
| pb_ess_workforce | `controllers/portal.py:69-276`, `ess_workforce.py:97` | Portal-only (`/my/work/*`), own-employee gate; clock page is a clock-in screen. |
| pb_me_expense · `/my/expenses` | `controllers/portal.py:138-140`, `me_expense.py:591,442` | Portal, employee's OWN claims. |
| pb_me_project_time | `controllers/portal.py:173-338`, `project_time.py:114` | Portal-only weekly timesheet editor. |
| pb_trip_expense_bridge | `views/pb_trip_expense_views.xml:4,21` | Models + two form inherits; no screen. |
| pb_timeoff · Public holidays | `pb_holidays.js:51,80`, `pb_timeoff_action.xml:17-19` | Per-company year calendar + import workspace. |
| pb_attendance_flow · composer and import stepper | `pb_attendance_flow.js:219-426` | Single-record editor and a 4-step wizard. |
| pb_integrations · Rule Composer | `rule_composer.js:349, :90, :850-878, :1038` | Builder dialog for ONE rule; `pbim-fchip`s are step-count chips. |
| pb_formula_studio · Mapping › Connections (connection desk) | `connection_desk.js:53`, `connection_desk.xml:10` | Input components of ONE scheme from `props.data.components` (in memory), 3 fixed chips; anchors `md-list`, `md-inspector`. Keep chips. |
| pb_formula_studio · Payroll sources (application sources) | `application_sources.js:44,:55`, `application_sources.xml:39-40` | Per-scheme settings page (toggles + per-item source picker). |
| pb_source_atlas · Where the numbers come from | `atlas.js:48-65`, `pb_source_atlas.py:527-617` | Per-run employees × components matrix; search server-side and paged (`_GRID_LIMIT 40` `:60`) but `lane`/`band` filter **cells** (`:567,:583`); no `data-coach`. A trace tool. Defer. |
| pb_insights · Insights (Pulse) + people ledger overlay | `insights.js:36-50`, `insights.xml:459-540`, `pb_insights.py:1171-1276` | KPI board; overlay rows are a cohort of ids from the attendance-exception engine (`:1194`), not a domain; anchor deliberately absent (`insights.xml:460-464`). |
| pb_insights · Module insights | `module_insights.xml:8,:108-112`, `module_insights.js:52` | Report catalogue + measure/dimension explorer. |
| pb_import_batch · Import Batch cockpit | `batch_cockpit.js:54-71`, `batch_cockpit.py:71` (`import_line_ids[:500]`) | Per-batch line review with inline fix/match; 4 client chips over ≤500 lines of one batch. |
| pb_blueprint · New configuration | `steps.xml:7,:230`, `blueprint_steps.js` | Guided wizard; no `pbim-fchip` in `steps.xml`/`blueprint.xml` despite the grep hit. |
| pb_approval · Approvals | `approval_redirect.js:17-43` | Redirect to Home › Approvals (the real inbox is #17). |
| pb_govt_reports · Government Reports | `govt_reports.js:40`, `pb_govt_reports.py:25-46` | Static per-country catalogue of filing tiles (< 10) + month picker; filing flow is a wizard. |
| pb_pay · Pay bands / Fairness | `pay.xml:132-150,:163,:564` | Band picture + stats with scope selects; aggregates. |
| pb_pay · Pay changes | `pay_review.js:1383-1440`, `pb_pay_reviews.py:158` (`limit=60`) | ≤60-row table with **no filters today**; `pb.pay.change` has state/kind/effective_date/employee — a cheap S later, nothing to migrate now. |
| pb_budget · Budget | `budget_board.xml:75-83,:256-330` | Function × month heat-map with year/type selects; aggregates. |
| pb_explorer · Analytics Explorer | `explorer.xml:336-400`, `pb_explorer.py:605` | Pivot/chart over fact tables; `ex-filters` are dimension filters on aggregates. |
| pb_workforce_insights · Workforce Insights | `workforce_insights.xml:48-75`, `pb_workforce_insights.py:95` | KPI board; chips scope aggregates. |
| biz_access · Roles lens / Screens lens | `access_board.xml:188-202,:219`, `pb_access_facade.py:93-121` | Roles: small `pb.role.profile` catalogue, area chips + search already server-side; Screens: the menu tree. Keep chips. |
