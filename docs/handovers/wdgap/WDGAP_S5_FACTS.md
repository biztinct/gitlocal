# WDGAP S5: plumbing facts for "Leave and time rules that fit the law"

This is a read-only code survey, done on 2026-11-15 against `origin/19.1` @ `7f0fa3aad`, the code that is live after the W2 deploy. The references are verified plumbing: do not re-derive them, but spot-check a line before you rely on it. Paths are relative to the repo root.

- **Study source:** `outputs/workday-gap-study-2026-11-14/research-data/07-absence-time-scheduling.json`, the rows for "Leave set-up and rules", "Balances, accruals and carry-forward", "Overtime and pay rules for time" and "Rosters and shifts". It is never committed.
- **Ledger:** read `docs/handovers/wdgap/WDGAP_LEDGER.md` first. Conventions 1–10 bind every phase below. D2 also applies: country statutory PAY numbers in `pb_pack_*` are postponed.

**Caveat on the standard addons.** `hr_holidays`, `hr_attendance` and `hr_holidays_attendance` line numbers below come from the repo's **vendored snapshot**. CLAUDE.md rule 4 says these copies are OLDER than the server's own git clone. A builder must confirm every standard-addon behaviour against `/odoo/odoo-server/addons/<m>` on the server before relying on it. The repo's `hr_holidays/__manifest__.py:6` says `1.6`.

## Seven findings that change the plan most

1. **There is no product screen for kinds of leave.** It only exists in the stock Time Off app's Configuration menu (`hr_holidays/views/hr_holidays_views.xml:93-106`). That menu tree is invisible to every tenant user: `pb_dashboard/models/menu_rails.py:14-26` lets only the platform admin on the apex (or the recovery login on a tenant) see stock app roots. Every tenant user sees the Payroll root only (`:61-70`, `:72-96`). Payobook's own leave switches (pay treatment, backdating, carry warning) are bolted onto that unreachable stock form.
2. **Overtime and late minutes do not reach a payslip made from a pay data file.** The file path builds inputs with `_transform_data_to_formula_inputs` (`pb_hr_payroll_formula/models/payroll_import_batch.py:3764-3810`), and its Recompute does the same (`hr_payslip_formula.py:1140-1154`). Neither ever calls `_get_formula_input_values`, which is the seam the overtime bridge and the approved-weeks code override.
   - Approved overtime therefore reaches **file-less** runs and application-mode runs only.
   - The ledger (PRM-2) says rize has 15 schemes that ask for a file, and sudima has 1.
   - Any new late-minutes or time-off-in-lieu input built on the same seam has the same blind spot. That must be said on screen, never silently dropped.
3. **Late-arrival detection is dead outside demo data.**
   - Exceptions read the shift's stored `compliance_status` (`pb_attendance_flow/models/attendance_exception.py:248`). Its inputs `actual_check_in/out` are written only by demo seeders (`pb_close/models/close.py:21-32`, and the grep confirms only `pb_demo` writes them).
   - So a real customer with clock machines never gets a "late" row.
   - The only live derivation of punch vs shift is `pb.close._punch_deviation` (`close.py:600-621`).
   - `count_late_as` is unused (`attendance_rule.py:76-84`, "future").
4. **Holiday overtime classification is dead.** `attendance_weekentry._holidays` reads `hr.holidays.public.line` (`pb_hr_workforce/models/attendance_weekentry.py:99-106`), which comes from a v16 module that is not available on 19. It swallows the error and returns an empty set. Real public holidays are company closures in `resource.calendar.leaves` with no resource, written by `pb.holidays` (`pb_timeoff/models/pb_holidays.py:178-186`, `:298-305`). Any "kind of day" logic must read those.
5. **Leave balances ignore expiry everywhere Payobook draws them.** Both readers sum every validated allocation with no `date_to` filter:
   - employee: `pb_ess_workforce/models/ess_workforce.py:463-466` in `get_my_leave`;
   - HR board: `pb_timeoff/models/pb_timeoff.py:298-346` in `_balances`.

   The manager's "balance after" uses core `virtual_remaining_leaves`, which honours validity (`pb_me_team`; QF3 facts §4). So an expiring time-off-in-lieu or carried balance would show two different numbers.
6. **Rize's policy engine already posts yearly leave and refuses overlaps.**
   - `post_annual_credit` (`pb_timeoff/models/rize_policy.py:278-318`) raises "Existing annual allocations overlap this year" when another allocation overlaps (`:311-316`).
   - The policy is seeded only on the `rize` database (`:186-197`).
   - A new monthly-earning engine must leave alone any person or kind under a published Rize policy edition, or the two will fight.
7. **The extension seams are all soft registries,** so all three phases below can ship as NEW modules without editing hub files:
   - Settings categories;
   - Mission Control lenses;
   - the ⌘K palette;
   - approval processes declared in the module's own data.

---

## Item 1: a set-up screen for kinds of leave

### What exists today
- **Model:** core `hr.leave.type` (`hr_holidays/models/hr_leave_type.py:44-123`). The fields that matter:
  - `name` (translate), `company_id` (:69), `country_id` (:71);
  - `leave_validation_type` (:83), `requires_allocation` Boolean (:88), `employee_requests` (:89), `allocation_validation_type` (:92);
  - `time_type` (:103), `request_unit` day/half_day/hour (:105, QF3 §2), `unpaid` (:109), `include_public_holidays_in_duration` (:110);
  - `support_document` (:113), `allows_negative` / `max_allowed_negative` (:121-123), `accruals_ids` (:118).
- **Payobook additions on the same model:**
  - `pb_timeoff/models/leave_rules.py:59-82`:
    - `pb_backdate_ok` "Can be asked for after it happened";
    - `pb_backdate_alert` "Tell HR when it is";
    - `pb_carry_cap_days` "Warn above this many days".
  - `pb_timeoff/models/rize_policy.py:877-897`:
    - `pb_policy_category` (17 categories, `:19-29`), `pb_policy_country_id`, `pb_policy_code` (unique, `:883`);
    - `pb_pay_treatment` (paid / unpaid / partial / "Needs pay review" default), `pb_paid_fraction`;
    - `pb_pay_funding` (employer / external / mixed / none / "Needs funding review" default), `pb_employer_paid_fraction`;
    - the `_check_explicit_pay` constraint (`:889-897`), whose rules are in `_classification` (`:41-67`).
  - `om_hr_payroll/models/hr_leave_type.py:9`: `code` (feeds worked-day lines).
- **Where they are edited:**
  - `pb_timeoff/views/hr_leave_type_views.xml:17-30` adds a group headed **"Payobook rules"** to the stock form. That label is fine, because it is the product's name.
  - `pb_timeoff/views/rize_policy_views.xml:23-24` adds "Payroll and policy" (manager group only).
  - Both sit on `hr_holidays.edit_holiday_status_form`, reached only through the stock action `hr_holidays.open_view_holiday_status` (`hr_holidays/views/hr_leave_type_views.xml:172-176`) under a hidden menu. See finding 1.
- **Who can edit:**
  - `hr.leave.type` gives write/create/unlink to `hr_holidays.group_hr_holidays_manager` and read to the officer and to `base.group_user` (`hr_holidays/security/ir.model.access.csv:8-10`).
  - Accrual plans and levels give the manager full rights and the officer read (`:20-23`).
- **The Settings hub (`pb_settings`, 19.0.1.10.1) has no leave entry.** Its categories are at `pb_settings/static/src/js/settings_hub.js:136-249`, and its rail groups are Company / Access / Payroll / HR / Workflows / Connect / System (`:286-296`).
  - Soft registry: `SETTINGS_CATEGORIES = "pb_settings_category"` (`:271`). A registered descriptor is an ordinary category (`:250-270`), placed by `group:` (`:304-323`).
  - Precedents to clone:
    - `pb_clock/static/src/js/connector_settings.js:6-14`, a 9-line single-card category;
    - `pb_hiring/static/src/js/hiring_palette.js:129-160`, `group: "hr"` with several cards.
- **What reads the leave type today, in the order a person meets it:**
  - **Offered to the employee:** `pb_ess_workforce/models/ess_workforce.py:555-569` `_my_appliable_types`. It offers the company's kinds plus shared ones, filtered by country via `pb.timeoff._type_country` / `_emp_country` (`pb_timeoff/models/pb_timeoff.py:102-116`). It does **not** read `employee_requests`, so every kind is offered to everybody of that country.
  - **Offered to HR for "Apply for":** `pb_timeoff.py:358-367` `_apply_types`.
  - **Balance tiles:** `requires_allocation=True` kinds only (`ess_workforce.py:459-460`; HR board `pb_timeoff.py:310-311`, which has **no company filter**, QF3 gotcha).
  - **Pay:**
    - application-mode runs: `leave._pb_payroll_classification()` (`rize_policy.py:982-992`), from the policy rule or the kind's four pay fields. An unconfigured kind is a run conflict "Leave payment or funding is not configured." (`rize_policy.py:44-46` → `pb_hr_payroll_formula/models/application_payroll_source.py:454-458`).
    - file-less runs: worked-day lines by the leave type `code` (QF3 §8; `hr_payslip_formula.py:753-763`, `WD_*` / `HOURS*`).
- **The policy layer is shaped around one customer** (Rize). `pb.leave.policy.edition` and `pb.leave.policy.rule` (`rize_policy.py:70-180`, `584-646`) carry length, medical-after-N-days, event evidence, and pay per category. Seeding is rize-only (`:196-197`). Menus are under the stock Time Off app (`rize_policy_views.xml:36-39`, `policy_year_opening_views.xml:7`), so they are unreachable for tenants too.

### What is missing
- A Payobook screen to list, add, edit and archive kinds of leave, reachable from Settings › HR.
- A guided "new kind" flow covering:
  - name (translated);
  - unit (day / half day / hours);
  - paid, unpaid or partly paid, plus who funds it;
  - whether it is counted against an allowance;
  - who approves;
  - whether employees may ask for it themselves, "Only HR can enter this", and backdating;
  - certificate needed;
  - country and company;
  - the carry warning;
  - how it is earned (item 2).
- A live "what the employee will see" preview: the My Leave tile and the form option.
- A set-up check card listing kinds whose pay treatment is still "Needs pay review" (the study's "Set-up health check" row).
- "Only HR can enter this": a new boolean read by `_my_appliable_types`. That is a pb_ess_workforce method, see the collisions list. It can be done by overriding `pb.ess.workforce._my_appliable_types` from the new module (`_name='pb.ess.workforce'`, `ess_workforce.py:102-103`).

### Precedent to clone
- **Cockpit pattern** (memory `payobook-cockpit-pattern`): an OWL client action plus a facade AbstractModel with `_require_*` gates and sudo reads.
  - Closest cousin: `pb.timeoff` (`pb_timeoff/models/pb_timeoff.py:48-70`, gate `_require_officer` at :55).
  - Filter-kit list: `_inherit = ['pb.filter.mixin']` (`pb_timeoff.py:50`) with `_pbf_*` hooks (`:378-491`).
- **Quiet board** for the set-up check: `pb_import_kit/static/src/xml/quiet_board.xml:26` `pb_import_kit.QuietGlance`, used for example at `pb_offboarding/static/src/xml/exits_board.xml:71`.
- **Drawer:** `WfDrawer` (`@pb_wf_kit/js/wf_drawer`, imported at `pb_mission/static/src/js/pb_mission.js:49`).
- **Palette row:** `registry.category("pb_hub_palette").add(...)` (`pb_timeoff/static/src/js/timeoff_palette.js` lines after the lens add; `requires:` names the client action tag).

### Risks
- **Rize kinds are bound to policy rules.** `_bind_policy_types` writes the pay fields from the rule (`rize_policy.py:262-276`), and `_pb_payroll_classification` prefers the rule (`:984-989`). Editing pay treatment on a policy-bound kind changes nothing for requests carrying `pb_policy_rule_id`. The screen must say "set by your leave policy" and lock those fields when `pb_policy_category` is set and a published edition exists.
- **`pb_policy_code` is globally unique** (`rize_policy.py:883`). A starter set (item 3) must never write it.
- **Changing `request_unit` on a kind that already has requests** changes how core counts them (QF3 §2: half/hours flags are computed from the type). Refuse it, or warn when `is_used` (`hr_leave_type.py:68`).
- **Translations:** `name` is `translate=True`. The vi/id names must be written into the field's translations, not only the `.po` (LOOK ledger: "a translation fix is TWO fixes").

### Modules a builder would edit
New module (proposed `pb_leave_setup`), plus overrides only. The builder may edit `pb_timeoff/models/pb_timeoff.py` (`_balances` expiry and company filter; `_apply_types`). Nobody else in S5 edits it.

---

## Item 2: leave that builds up monthly, plus extra days for long service

### What exists today
- **Yearly grant (Rize policy only):**
  - `post_annual_credit` (`rize_policy.py:278-318`) grants one native allocation per person, kind and year (`_create_posting` `:348-363`; posting key `'%s:%s:%s:annual'` `:306`).
  - Joiner proration options: daily, monthly-if-joined-on-the-1st, or an HR-reviewed figure (`:292-303`).
  - The entitlement is flat (`annual_days` `:86`). There is no seniority logic anywhere.
- **Scheduled openings:** `pb.leave.policy.year.opening` with `_cron_open_year` (`pb_timeoff/models/policy_year_opening.py:10-28`, `:93-121`), rollover then credit. It needs `employment_start` "Verified service start" (`:20`).
- **Audit trail:** `pb.leave.policy.posting` (`rize_policy.py:648-692`), kinds annual / carry / opening (`:658`). Postings are frozen, and a guarded write on posted allocations is at `:695-720`.
- **Core accrual (vendored, unused by Payobook):**
  - `hr.leave.accrual.plan` (`hr_holidays/models/hr_leave_accrual_plan.py:14-71`) and levels `hr.leave.accrual.level` (`hr_leave_accrual_plan_level.py:18-145`):
    - `start_count` / `start_type` "after N days/months/years **from the allocation start date**" (:23-30);
    - `frequency` hourly → yearly (:45-53);
    - caps `maximum_leave` / `maximum_leave_yearly` (:104-112);
    - carry-over options and validity (:113-145).
  - The daily cron is `hr_leave_allocation_cron_accrual` → `_update_accrual` (`hr_holidays/data/ir_cron_data.xml:4-11`).
  - The allocation has `allocation_type` regular/accrual (`hr_leave_allocation.py:121`), `accrual_plan_id` (:124), `lastcall` / `nextcall` (:112-116) and `date_to` expiry (:69, constraint :137-139).
  - No `pb_*` module creates accrual plans. The only link is the legacy `pb_hr_flow/models/hr_flow_wizard.py:235` (`'leaves-accrual'` → `hr_holidays.open_view_accrual_plans`).
- **Service start dates available:**
  - `hr.employee.date_of_joining` (`pb_hr_payroll_formula/models/hr_employee.py:31`);
  - core `first_contract_date` (`hr_contract/models/hr_employee.py:24`).
  - The product's own precedence is `date_of_joining` → `first_contract_date` → contract start (`hr_payslip_formula.py:1377-1381`). PR2 §1 D27 warns that the contract start does not prove the service start.
- **Other allocation creators** (each a precedent and a collision risk for a new engine):
  - `rize_policy.py:357-363`;
  - People › Updates opening balances `pb_updates/models/updates_leave.py:315-331` (`date_to=False`, approve, refuse when a second approval is still needed);
  - demo `pb_demo/models/demo_timeoff.py:101-108`.
- **Carry warning:** `pb_timeoff/models/carry_watch.py` (switches `:38-40`, cron `cron_carry_watch` `:126`, data `pb_timeoff/data/pb_timeoff_config.xml:36-67`).

### What is missing
- **How it is earned**, per kind: all at once each year / a share each month / none.
- Joiner and leaver proration on the monthly share.
- Waiting period ("starts after N months").
- A maximum balance.
- **Service steps** table on the kind ("after 5 years +1 day a year"), measured from a verified service start.
- A "next step-up on …" line on the employee record.
- An "earned so far / next credit" line on My Leave.

### Two ways to build it (choose in the handover)

| | A. Thin Payobook engine (recommended) | B. Core accrual plans |
|---|---|---|
| **Mechanism** | Monthly cron posts each month's share into ONE native allocation per person, kind and leave year (`date_from` = year start, `date_to` = year end + carry rules), plus a posting row per month (clone `pb.leave.policy.posting`) | One `allocation_type='accrual'` allocation per person and kind, run by core `_update_accrual` |
| **Service steps** | Read from `date_of_joining` / `first_contract_date` at each monthly run; the step-up applies from a defined point (owner default) | Levels count from the ALLOCATION's start date. A step-up at 5 years of SERVICE means backdating the allocation to the service start, and core would then accrue years of leave retroactively |
| **Audit** | Month-by-month rows like the Entitlement Posting Audit; undo per month | Core chatter only |
| **Verifiability here** | All code ours | The behaviour is the server's newer hr_holidays, which cannot be read in this repo (caveat at top) |
| **Balance readers** | `number_of_days` grows, so the existing readers (`ess_workforce.py:463`, `pb_timeoff.py:323`) show "earned so far" with no change | Same |

### Precedent to clone
- `_create_posting` / `_lock_posting` idempotency (`rize_policy.py:344-363`) with its posting key.
- The yearly-opening cron with `FOR UPDATE SKIP LOCKED` per job and a savepoint per job (`policy_year_opening.py:93-121`).
- The People › Updates review-then-apply sheet for a "preview next month's credits" desk (`pb_updates/models/updates_leave.py`, `updates_leave_desk.py`).

### Risks
- **Double credit with Rize.** Skip any employee with `pb_leave_policy_id` whose edition binds this kind's `pb_policy_category` (`rize_policy.py:765`, `:790-799`). Also skip any kind with `pb_policy_category` set under a published edition of that company.
- **Opening balances from People › Updates** create their own allocation (`updates_leave.py:315-331`). The engine must add to the leave-year allocation and never treat the opening allocation as "this year's".
- **Writes to a validated allocation:** core may refuse `number_of_days` writes on validated rows for non-managers. Run under sudo inside the engine, with the posting row as the authority (the rize guard pattern `:707-720`).
- **People with no service start** get no step-up. List them on the set-up check card. Never guess from the contract start (D27).
- **Half-day/hour kinds:** `number_of_days` vs hours for `hour` units (QF3 §2).
- **Expiry:** see finding 5. The balance readers must filter `date_to >= today` (or `False`) once anything expires.
- **Scale:** the demo world has about 4,500 people (`pb_timeoff.py:39` comment). Batch per company, chunk 200 (carry_watch `_CHUNK`, `:44`).

### Modules a builder would edit
`pb_leave_setup` (new), plus the `pb_timeoff` balance readers. Override `pb.ess.workforce.get_my_leave` from the new module rather than editing `pb_ess_workforce` (collision list).

---

## Item 3: ready-made statutory leave per country, as an optional starter set outside the packs

### What exists today
- **The packs hold pay only.** `pb_pack_vn|id|in|sg|th|my/data/` each have just `config_template_*.xml` and `legislation_pack_*.xml`. A grep finds no `hr.leave.type` and no "leave" anywhere in `pb_pack_*`.
- **There is no `pb_pack_kh`.** Cambodia exists only as the legacy `pb_hr_payroll_cambodia` (memory `payobook-current-design`: country modules are LEGACY).
- **Rize's supplied leave policy** sits as a 15-row reference table for SG/ID/VN/IN (`pb_timeoff/data/leave_reference.json`). It is turned into `pb.holiday.policy.note` rows **on the rize database only** (`pb_timeoff/models/holiday_journey.py:195-207`), as "draft reference". These are Rize's company policy (for example "20 days" annual for all four countries), **not statutory minimums**. They must not be reused as a statutory set.
- **Rize policy rule definitions** (`rize_policy.py:212-248`) are also company policy, rize-only (`:196-197`).
- **Public holiday lists** (`pb_timeoff/data/holiday_reference.json`, 55 rows) can be used only on rize and only for 2026 (`holiday_journey.py:99`).
- **The guided payroll set-up (`pb_blueprint`, 19.0.1.11.8)** is a six-step pay-scheme journey (`pb_blueprint/models/blueprint.py:21-23`) and has no leave step. Its Settings door is registered at `pb_blueprint/static/src/js/blueprint_doors.js:38` (`guided_setup`).

### The answer to "can it live outside the packs?"
**Yes. Nothing ties leave kinds to the pay packs.** A kind is a plain `hr.leave.type` row scoped by `company_id` and `pb_policy_country_id` (or `country_id`). That is exactly what `_type_country` reads to offer it (`pb_timeoff.py:102-107`).

A starter set can therefore be:
- a versioned JSON per country inside the new module (no XML records, so nothing is created on install);
- applied on demand, per company, from the Kinds of leave screen: "Add the standard Vietnam leave kinds";
- shown first as a review list (each kind editable, untick to skip);
- then created as ordinary kinds with explicit pay treatment and funding.

It never touches `pb_pack_*` (D2 respected) and never writes `pb_policy_code` or `pb_policy_category` (Rize-only semantics).

### What the starter set must carry, and why it overlaps items 1 and 2
Several countries' statutory annual leave is itself a monthly or service-stepped rule. The figures below are **indicative, from general knowledge, and NOT verified in this survey**. They need the same legal-review discipline as D2 before anything ships, and the source clause should be cited in the JSON.

| Country | Annual leave shape (to be legally checked) | Engine feature it needs |
|---|---|---|
| VN | 12 working days, +1 day per 5 years of service | service steps |
| ID | 12 days after 12 months of service | waiting period |
| MY | 8 / 12 / 16 days by length of service (<2 y, 2–5 y, >5 y) | service steps |
| SG | 7 days in the first year, +1 per year to 14 | service steps |
| TH | at least 6 working days after 1 year | waiting period |
| KH | 1.5 days per month of service, plus extra days with seniority | monthly earning + service steps |
| IN | varies by state law (for example 1 day per 20 days worked in factories) | earning "per days worked", not in scope |

Sick leave in several countries is paid by a social-insurance fund, not by the employer. That corresponds to `pb_pay_funding='external'` (`rize_policy.py:32-34`), and the starter set must set it explicitly. Otherwise the run conflicts (finding on `_classification`).

### Risks
- **Legal liability** if presented as "statutory" without review. That is an owner question.
- **Duplicates:** applying the set twice, or onto a company that already has "Annual leave". Match by a starter key stored in a new field on the kind (not `pb_policy_code`).
- **Cambodia** has no pay pack, so offering leave there implies a market decision.
- **Names in three languages:** write the `name` translations for vi_VN and id_ID at creation. TH/MS/KM screens do not exist (study step "Reach people").

### Modules a builder would edit
`pb_leave_setup` (new) only.

---

## Item 4: time off in lieu (comp-off)

### What exists today
- **Overtime request:** `hr.overtime.request` (`pb_hr_workforce/models/overtime_request.py:22`).
  - Fields: `planned_hours` (:40), `actual_hours` (:42), `approved_hours` (:43), `bonus_hours` (the part over the ceiling, :51), `total_hours` (:55).
  - Type: `overtime_type` weekday / weekend / holiday / night (:58-63; `extended` added in `overtime_extended.py:10`).
  - State: draft / submitted / approved / refused (:76-81).
- **Sealed fields** `{'state','approved_hours','bonus_hours'}` (`:10-12`): only writable with the module token, sudo or admin, and a plain create silently drops them (`:120-146`).
- **Rate lookup** uses `rec.employee_id.country_id` (`overtime_request.py:93-107`). That is the employee's **nationality** field on hr.employee, not the country they are paid in. **Gotcha:** a VN national paid in ID gets VN rates. Do not copy this lookup.
- **Approval:** process key `overtime` (`overtime_request_approval.py:32,47`; process record `pb_approval_config/data/processes.xml:226-233`).
  - `_approval_apply` runs `action_approve` under sudo with the engine flag (`:273-303`).
  - "Clean for bulk approve" needs planned == actual (`:194-249`, at :217-220).
  - Desk bulk actions: `pb.ot.desk.act` (`pb_hr_workforce/models/ot_desk.py:422-449`), per row in a savepoint.
- **Money paths: three places pay approved overtime.**
  1. **File-less bridge:** `pb_workforce_payroll_bridge/models/hr_payslip.py:38-101`.
     - `OTHRS150/200/300/NGT` = Σ `approved_hours` per type (:73-84), and `BONHRS` = Σ `bonus_hours` (:89-99).
     - Regular runs only (`_pb_ot_bridge_feeds` :28-36).
     - It has no domain hook.
  2. **Approved weeks:** `pb_timesheet_approval/models/hr_payslip.py:69-114`, active when `company.pb_timesheet_payroll` is on. It **replaces** OTHRS*/BONHRS from packets. It depends on the bridge (`pb_timesheet_approval/__manifest__.py:45-52`), so it sits above it in the MRO. Unlike the bridge, it has no run-kind check (a likely top-up/extra double-pay; survey note, not verified by test).
  3. **Application mode:** `pb_hr_payroll_formula/models/application_payroll_source.py`.
     - Packet path: `:540-558` sums `approved_hours` and `bonus_hours`.
     - Contractual path: `:595-613`, inline, with no hook except the undefined `_application_policy_errors` on the request (`:603-604`).
     - Facts are written at `:615-625` (`period.ot.<kind>.approved_hours`).
- **Legal cap:** `pb.ot.ceiling` counts approved plus submitted `approved_hours` (`ot_ceiling.py:101-130`). Time-off-in-lieu hours are still overtime, so they must keep counting.
- **Core alternatives, not to use:**
  - `hr_holidays_attendance` (vendored, `auto_install: True`, `hr_holidays_attendance/__manifest__.py:10-11`) has `overtime_deductible` on the leave type (`models/hr_leave_type.py:10`). It validates against core `hr.attendance.overtime`, not Payobook's requests (`models/hr_leave_allocation.py:34-40`). A comp-off kind must keep `overtime_deductible=False`.
  - Core attendance overtime is computed but read by nothing in `pb_*`. The bridge docstring (C18.3) makes approved requests the ONE overtime source.
  - Whether `hr_holidays_attendance` is installed on the five databases is unknown here. The deploy agent should check `ir_module_module`.
- **Employee and manager side:**
  - `/my/work/overtime` (`pb_ess_workforce/controllers/portal.py:221-228`, `get_my_overtime` `ess_workforce.py:1053-1091`, template `portal_my_work_overtime` `views/portal_templates.xml:540`) is read-only.
  - The manager's `/my/team` overtime block is read-only (`pb_me_team/models/pb_me_team.py:537-576`).

### What is missing
- A "Pay it / Give time off" choice per request, and who makes it (owner question).
- Conversion: hour for hour, or at the overtime rate.
- A per-company "Time off in lieu" kind, created on demand with:
  - `requires_allocation=True`, unit hours;
  - pay treatment paid / employer (otherwise application-mode runs conflict);
  - `pb_backdate_ok=False`.
- On approval with "time off", one allocation of that kind with `date_to` = approval + N months (expiry).
- An expiry warning.
- Pay exclusion of those hours in all three money paths.
- Showing it on My Overtime and in the leave tiles (an allocation of a `requires_allocation` kind already shows as a tile, `ess_workforce.py:483-491`).

### Precedent to clone
- **Allocation creation:** `updates_leave.py:315-331` (create, approve, handle second approval).
- **Hook point:** override `_approval_apply` after super in the new module.
- **Pay exclusion without editing the bridge or the packet code:** a new module that **depends on `pb_timesheet_approval`** (and so on the bridge) overrides `_get_formula_input_values`. It calls super and subtracts the period's time-off hours per type from `OTHRS*` (and `BONHRS` if bonus hours can be given as time off). That puts it above both producers in the MRO.
- **Application mode:** override `hr.formula.config._application_time_values` (`application_payroll_source.py:400`) after super, or refuse "Give time off" for employees on application-mode schemes in v1. Subtracting changes the fact fingerprint only where time off exists (W2A-2), but it is a money path: rehearse it.
- **Approval process:** declare any new process in the module's own data (`pb_loans/data/approval_process.xml`, `pb_fund_payments/data/approval_process.xml`). More likely, no new process is needed: the choice rides the existing overtime route, and it shows in the inbox through an override of `_approval_detail` (`overtime_request_approval.py:256`).

### Risks
- **Finding 2:** pay data file runs never had overtime from requests, so time off in lieu changes nothing for them. Say so.
- **The seal:** add the new field to a seal of the module's own. Once approved, the choice must not change (an approved choice is money).
- **Day lock and week freeze:** `pb.wf.lock._check_days_open` (`pb_close/models/wf_lock.py:260-289`) and `pb.timesheet.freeze.check_open` (`pb_timesheet_approval/models/week_freeze.py:65-72`, `:177-207`; sudo does NOT bypass it, only `_TS_CHAIN_TOKEN` does). Changing a request inside a frozen week must refuse.
- **Expiry display** (finding 5).
- **Whether `pb_timesheet_approval` is installed on all five databases** (memory `tenant-module-sync-rule` says tenants get every master module) has to be confirmed by the deploy agent before a hard dependency is taken.

### Modules a builder would edit
New module (proposed `pb_time_pay`). It overrides `hr.overtime.request`, `hr.payslip` and `hr.formula.config`, with optional view inheritance of `pb_ot_desk` (OWL `t-inherit`) and `portal_my_work_overtime` (QWeb xpath). No edits to `pb_workforce_payroll_bridge`, `pb_timesheet_approval` or `pb_hr_payroll_formula` files are needed.

---

## Item 5: overtime suggested from clock punches, and late minutes feeding pay

### How time reaches a payslip today (verified chain)
- **Punches become work days.** `pb.clock.pairing._pair_employee` (`pb_clock/models/clock_pairing.py:278-397`) does the pairing:
  - repeat taps are dropped (:308-312);
  - a day runs from the first punch for up to `pb_clock_max_span_h` hours, default 21 (:283, :314-318);
  - the day is the LOCAL date of the first punch, so a night shift is one day dated when it began (:17-18, :330);
  - it writes `hr.attendance` rows with `pb_entry_source='device'` (:490-506) and never touches rows a person made (:473-487);
  - it skips locked, frozen and corrected days (:443-470).
- **Entry sources:** grid (`pb_hr_workforce/models/hr_attendance.py:16`), correction/import (`pb_attendance_flow/models/hr_attendance.py:33`), device (pb_clock), portal (`pb_ess_workforce/models/hr_attendance.py:27`).
- **Local day:** computed, not stored (`pb_hr_workforce/models/hr_attendance.py:38-80`).
- **Planned hours:** `hr.shift.planning.planned_hours` = template `duration` = span minus `break_duration` (default 1 h) (`pb_hr_workforce/models/shift_planning.py:37-39`; `shift_template.py:23,53-60`).
  - Every reader uses **published** shifts only: exceptions `attendance_exception.py:186-190`, Close `close.py:112,379-383`, time hub `pb_time_hub/models/time_hub.py:67,344-351`, week entry `attendance_weekentry.py:502-506`.
  - The timesheet packet's weekly figure comes from the resource calendar instead (`timesheet_packet.py:373-389`).
- **Scheduled vs actual:** `pb.close._classify` (`pb_close/models/close.py:358-551`). The schedule sum is at :455, the actual (`_att_hours`, raw span) at :456, and the difference at :458. `_punch_deviation` is at :600-621.
- **Overtime reaches pay ONLY as approved `hr.overtime.request` rows** that someone typed:
  - the Week Grid's `_save_ot` (`attendance_weekentry.py:593-644`, sudo create with planned = actual = the hours entered);
  - or the form.
  - Pay paths: item 4, three places. Employees cannot ask (ESS is read-only).
- **`threshold_hours` "Overtime After (hrs)"** (`overtime_config.py:65-69`, default 8) is display-only. It is read only by the desk gallery (`ot_desk.py:401`).
- **Rates** are seeded only for VN and Global (`pb_hr_workforce/data/overtime_config_data.xml:6-75`).
- **No "suggested overtime" exists anywhere.** The nearest is the stale `compliance_status='overtime'` (`pb_attendance_flow/models/shift_planning.py:50-51`). A static gate (`pb_mission/tests/test_static.py`) forbids `pb_close` from reading that field.

### Lateness today
- **Rule record:** `pb.attendance.rule` (`pb_attendance_flow/models/attendance_rule.py:35`), with `grace_in_minutes` / `grace_out_minutes` (default 15), lookup company then global (:121-132), and `count_late_as` report_only / deduct_flag "(future)", unused (:76-84).
- **The minutes** are computed at read time from `shift.actual_check_in − start_datetime` (`attendance_exception.py:262-267`), are stored nowhere, and are dead in production (finding 3). Late and early are an `elif`, so a day that is both reports late only (`shift_planning.py:46-49`).
- **There is no excuse flow.** The nearest are a Close waiver (`pb.close.review`, `close_review.py:37,47`) or a punch correction (`attendance_correction.py:60-72`, process key `correction`).
- **CLOCK backlog:** "CLOCK-4: late minutes and early leave as payslip inputs (from the shift + the paired day), with the approval the overtime desk already has, ~1 day" (`docs/handovers/clock/CLOCK_CLOSEOUT.md:70,79`).

### Seams for a new pay input (late minutes, for example `LATEMIN` / `EARLYMIN`)
1. **The code:** underscore-free and not a substring of any code (formula converter contract; PR2 §0). Add a `post_init_hook` collision scan (clone `pb_workforce_payroll_bridge/__init__.py:3-38`).
2. **File-less:** override `hr.payslip._get_formula_input_values(config, provenance=None)`. It must forward `provenance` (bridge docstring `:47-53`), fill only the codes the scheme declares (`:57-61`), and apply the run-kind rule (`_pb_ot_bridge_feeds` `:28-36`).
3. **Provenance:** `input_provenance.VIAS` (`pb_hr_payroll_formula/models/input_provenance.py:51-87`). An unknown via silently becomes `'default'` (`:136`). A new via needs a **one-line edit to this shared file**, or reuse of `'timesheet_packet'` if late minutes travel inside approved weeks.
4. **Source Atlas label:** `VIA_LABELS` (`pb_source_atlas/models/pb_source_atlas.py:124-145`, used at :749), another **one-line shared edit**.
5. **Application mode:** override `hr.formula.config._application_source_catalogue` (`application_payroll_source.py:337-354`, "Extension seam") and `_application_domain_values` (`:356-357`, returns `{}`) from the new module. No file edit is needed.
6. **Pay data file runs:** not reachable through either seam (finding 2). The Run payroll screen should say "late minutes are not taken from a pay data file".

### What is missing
- **Overtime suggestions.** Per person-day, compare worked time beyond the published shift (or the working hours, owner question) and classify the kind of day:
  - weekday / weekend from the config's day flags (`attendance_weekentry.py:108-117` `_config_applies`);
  - holiday from `resource.calendar.leaves` closures, not `hr.holidays.public.line` (finding 4);
  - night from the config window.
  - Then show "suggested" chips in the Close lens. The manager accepts them in bulk, which creates `hr.overtime.request` rows (planned = actual = suggested, so they are "clean"; one row per employee, date and type, as the grid assumes at `attendance_weekentry.py:610-616`) and submits them on the existing route.
- **Late minutes:** live derivation from punches vs the published shift start minus grace (the `_punch_deviation` shape), confirmed per week (owner question), stored as rows (counted / excused), and fed as an input.

### Risks
- **Lunch break skew.** `planned_hours` is net of the break, but `_att_hours` is the raw span (`attendance_weekentry.py:89-97`). A naive comparison suggests about +1 h every day. Use `worked_hours` (core, net of the calendar lunch), as application mode does (`application_payroll_source.py:562-566`), and compare like with like.
- **Time zones differ by reader:** employee tz then calendar tz (`pb_hr_workforce/models/hr_attendance.py:49`), employee tz only (`close.py:594`, `attendance_exception.py:210`), calendar tz first (`attendance_weekentry.py:70-72`). Pick one: the Close lens's employee-local day.
- **Night shifts** cross midnight (Sudima 07:30→04:00+1, clock memory). The device day is dated by its start.
- **Locks:** an overtime submit, approve or refuse on a locked day is refused (`pb_close/models/overtime_request.py:35-50`), and the week freeze blocks any create or write (`week_freeze.py:177-207`). Suggestion acceptance must respect both and report per row.
- **Approve sequentially.** The dock loops one by one (`pb_mission/static/src/js/pb_dock.js:257-320`).
- **Period mismatch:** the overtime `date` is a plain Date and the bridge filters on the payslip dates (`hr_payslip.py:74-80`), but packets assign a week to the month its Monday falls in (`timesheet_packet.py:802-819`). Late minutes must pick one rule and state it.
- **No roster, no lateness.** A company that does not publish shifts gets no late minutes from a roster. Owner question on working hours.

### Modules a builder would edit
- `pb_time_pay` (new): suggestion model and engine, late entries, pay input overrides.
- `pb_close` (server read for suggestions beside `_classify`).
- `pb_mission/static/src/js/pb_close_lens.js` plus its XML (the chips; the Close lens has no extension slot; tiles at `pb_close_lens.js:308-314`).
- `pb_hr_payroll_formula/models/input_provenance.py` (1 line).
- `pb_source_atlas/models/pb_source_atlas.py` (1 line).
- Optionally `pb_attendance_flow` (relabel `count_late_as`, or override from the new module).

---

## Item 6: rotating shift patterns

### What exists today
- **Shift template:** `hr.shift.template` (`pb_hr_workforce/models/shift_template.py:8`).
  - `start_hour` / `end_hour` (:19-22), `break_duration` 1.0 (:23), `duration` (:24, :53-60).
  - `shift_type` morning / afternoon / night / split / flexible (:27-33). Split is a label only.
  - `is_overnight` (:35), `resource_calendar_id` (:39-41, read by nothing).
  - `_sql_constraints` (:47) is ignored on 19 (see `pb_schedule/models/schedule_budget.py:67-73`).
- **Planned shift:** `hr.shift.planning` (`pb_hr_workforce/models/shift_planning.py:11`), with mail.thread.
  - `employee_id` **required** (:17-19), `shift_template_id` required, `date` required.
  - `start/end_datetime` required, UTC.
  - `state` draft / published / completed / cancelled (:49-54); `action_publish` (:103).
  - There is no pattern link.
  - **Name clash:** the module `hr_shift` declares another `hr.shift.planning` (`pb_schedule/models/schedule_grid.py:33-38`).
- **Schedule screen (`pb_schedule`, 19.0.1.10.0):**
  - `schedule_grid.py` may only ADD methods; the base facade shapes are frozen (`:1-16`).
  - Read: `get_schedule_data` (`:176-325`, row cap 200 `:50`).
  - Exact UTC window: `_pb_shift_window` (`:69-96`).
  - Checks: `_pb_check` (`:623-681`), with codes overlap / leave_approved / leave_pending / young_worker_night (block; `pb.young.worker` probe `:596-620`) / ot_ceiling.
  - Caches: `_pb_leave_map` (`:522-549`), `_pb_ceilings` (`:552`), `_pb_shift_windows` (`:570`).
  - **`copy_week_checked` (`:744-827`) is the generator precedent.** It builds caches once, skips block/warn, creates drafts, and appends each new window so later rows see it. It returns `{created, skipped[...], considered, target_start}`.
  - Publish: base `publish_shifts` (`shift_planning_grid.py:312`), or `publish_shifts_notified` (`pb_ess_workforce/models/publish_notify.py:72`).
- **JS:** `PbSchedule` (`pb_schedule/static/src/js/pb_schedule.js:55`).
  - `_applyPbCmd` (:570) handles `copy_week` / `set_budget` / `quick_create`.
  - Toolbar in `pb_schedule/static/src/xml/pb_schedule.xml:20-70`; Copy modal :338-399; drawers via `WfDrawer` :450-584.
  - Open-shift row: "cannot fill: employee_id required" (`pb_schedule.js:193-205`; xml :191-206).
- **Doors:** Mission Control lens `schedule` (`pb_mission.js:139-144`, plus palette rows `:85-90`).
  - Soft registry for new lenses: `MISSION_LENSES = "pb_mission_lens"` (`pb_mission.js:206-212`). Guests must carry a test that reads pb_mission.js and asserts the spelling (precedent `pb_timeoff/tests/test_holidays.py:234-238`).
- **Employee side:** My Schedule `/my/work/schedule` (`pb_ess_workforce/controllers/portal.py:75`) shows only published or completed shifts, two weeks ahead (`ess_workforce.py:57-59,153`). Confirming is per shift (`shift_planning_ack.py:72-190`).
- **No rotation, cycle or pattern model exists.** `two_weeks_calendar` is unused by `pb_*`.

### What is missing
- **A pattern:** name, company, department, cycle length in weeks, an anchor date, and the slots (day N of the cycle → template or "off").
- **Members:** employee, team offset (A/B/C/D), from and to.
- **"Generate N weeks ahead as drafts"** with the same checks and a skip report.
- A "made from pattern X" mark on generated shifts.
- Re-generating after a change replaces only untouched drafts of that pattern.

### Precedent to clone
`copy_week_checked`, verbatim in shape; `_pb_shift_window` for the UTC times; `WfDrawer`; a registered lens "Patterns" plus palette rows ("Generate from a pattern"), so `pb_schedule` and `pb_mission` need no edits. A toolbar button in `pb_schedule.xml` is optional, and S5-C owns `pb_schedule` if it is wanted.

### Risks
- **No-person slots are impossible** (employee required). Open shifts are out of scope.
- **Overnight templates and a cycle anchored across DST** (most S5 markets have no DST).
- The 200-row cap on the read model.
- **Young-worker blocks** (`pb_young_worker/models/shift_planning.py:16-31`) raise on create, so `_pb_check` must run first, as copy does.
- **Generated drafts count as coverage supply** (`schedule_grid.py:865`) but not as planned hours until they are published (the readers above). The planner must publish.
- **Leave on generated days:** approved leave is a warn → skipped. Pending leave is info → created.

### Modules a builder would edit
`pb_shift_patterns` (new). Optionally `pb_schedule` (toolbar button plus a cmd in `_applyPbCmd`).

---

## Cross-cutting precedents and rules (all phases)

- **Gates:** every facade enforces its own server gate; JS `groups` are hints only (`pb_mission.js` comment at the LENSES block). Officer groups:
  - Time Off: `TIMEOFF_OFFICERS` (`pb_timeoff/static/src/js/timeoff_palette.js`), i.e. `hr_holidays.group_hr_holidays_user`, `hr.group_hr_manager`, `om_hr_payroll.group_hr_payroll_manager`.
  - Set-up writes: `hr_holidays.group_hr_holidays_manager` (`rize_policy.py:18`, `_manager` :37-39).
  - Schedule: `hr_attendance.group_hr_attendance_officer`. Close and overtime decisions: `hr_attendance.group_hr_attendance_manager` or payroll manager (`pb_mission.js:127-183`).
- **Probe for optional models:** `self.env.get('hr.overtime.request')` (`application_payroll_source.py:596`) and `hasattr(leave, '_pb_payroll_classification')` (`:454`). Feature gate in JS: `featureGate(env, key)` (`pb_hub/static/src/js/hub_features.js:166`).
- **Employee home cards:** `_pbme_extra_cards(emp)` hook (`pb_me_team/models/pb_me_home.py:14`, `pb_me_project_time/models/pb_me_home.py:26`). The Leave card reads `get_my_leave` (`pb_me_portal/models/pb_me_home.py:526-530`).
- **Portal pages:** QWeb plus `.pbme` kit. Root is `.pbme-home` on home (ledger PRB-W5). Build `t-att` strings with `str()+` (PRB-W5). One translatable sentence per line (PRD-3).
- **Translations:**

  | Module | vi | id |
  |---|---|---|
  | `pb_timeoff` | `vi_VN.po` | `id_ID.po` |
  | `pb_me_team` | `vi_VN.po` | `id_ID.po` |
  | `pb_mission` | `vi_VN.po` | `id_ID.po` |
  | `pb_ess_workforce` | `vi.po` + `vi_VN.po` | none |
  | `pb_schedule` | `vi.po` + `vi_VN.po` | none |
  | `pb_hr_workforce`, `pb_close`, `pb_clock`, `pb_attendance_flow`, `pb_timesheet_approval`, `pb_workforce_payroll_bridge`, `pb_source_atlas` | `vi_VN.po` | none |

  New modules ship `vi_VN.po` and `id_ID.po` (ledger convention 3).
- **White-label:** no "Odoo" in any label, help, error or `.po` msgstr. Generic `biz_*` modules never say "Payobook" (QFM-1). S5 touches no `biz_*` module.
- **Versions now:**

  | Module | Version |
  |---|---|
  | `pb_timeoff` | 19.0.1.11.0 |
  | `pb_ess_workforce` | 19.0.1.4.0 |
  | `pb_me_team` | 19.0.1.2.0 |
  | `pb_settings` | 19.0.1.10.1 |
  | `pb_mission` | 19.0.1.13.1 |
  | `pb_close` | 19.0.1.3.0 |
  | `pb_hr_workforce` | 19.0.4.24.0 |
  | `pb_schedule` | 19.0.1.10.0 |
  | `pb_attendance_flow` | 19.0.1.4.0 |
  | `pb_clock` | 19.0.1.4.3 |
  | `pb_timesheet_approval` | 19.0.1.1.0 |
  | `pb_workforce_payroll_bridge` | 19.0.1.3.0 |
  | `pb_hr_payroll_formula` | 19.0.1.167.0 |
  | `pb_source_atlas` | 19.0.1.14.0 |
  | `pb_me_portal` | 19.0.3.7.0 |
  | `pb_blueprint` | 19.0.1.11.8 |

- **Existing tests to keep green:**
  - pb_timeoff: `test_leave_rules.py`, `test_rize_policy.py`, `test_policy_year_opening.py`, `test_timeoff.py`, `test_wdgap_qf3_withdraw.py`, `test_holidays.py`.
  - pb_ess_workforce: `test_p8_portal.py`, `test_p8_adversarial.py`.
  - Bridge: `test_bridge.py`, `test_wdgap_prd_run_kinds.py`.
  - pb_hr_workforce: `test_ot_engine.py`, `test_overtime_approval.py`, `test_weekentry.py`, `test_wf2p2b_overtime.py`.
  - pb_timesheet_approval: `test_timesheet_packet.py`, `test_local_day.py`.
  - pb_close: `test_close.py`, `test_locks.py`, `test_clean_batch.py`.
  - pb_hr_payroll_formula: `test_application_payroll_source.py`, `test_sc1_catalog_truth.py`.
  - pb_source_atlas: `test_atlas.py`.
  - pb_mission: `test_static.py`.
  - pb_young_worker: `test_young_worker.py`.

---

## Proposed split: three builders at the same time

| Phase | Scope | Owns (may edit) | Must not edit |
|---|---|---|---|
| **S5-A Kinds of leave and how they are earned** (items 1, 2, 3) | New module **`pb_leave_setup`**: <br>• Settings › HR "Kinds of leave" card (registry), cockpit with guided drawer and employee preview, set-up check card; <br>• new kind fields (earning method, service steps, waiting period, max balance, carried-days expiry, only-HR, starter key); <br>• monthly earning engine (engine A) with posting audit and cron; <br>• statutory starter sets as reviewed JSON per country, applied on demand; <br>• balance readers filter expired allocations | `pb_leave_setup/**` (new); `pb_timeoff/models/pb_timeoff.py` (`_balances` expiry and company filter, `_apply_types`), `pb_timeoff/i18n/*`, `pb_timeoff/__manifest__.py` version; overrides of `pb.ess.workforce.get_my_leave` / `_my_appliable_types` and an xpath on `portal_my_work_leave` FROM `pb_leave_setup` | `pb_pack_*` (D2), `pb_hr_workforce`, `pb_mission`, `pb_schedule`, `pb_ess_workforce` files |
| **S5-B Time into pay** (items 4, 5) | New module **`pb_time_pay`**: <br>• overtime suggestions from punches with bulk accept into requests; <br>• late (and early) minutes derived live, confirmed in the weekly Close, fed as inputs (file-less + application mode); <br>• "Pay it / Give time off" on overtime with a time-off-in-lieu kind, allocation with expiry, subtraction above the bridge and the approved-weeks code | `pb_time_pay/**` (new); `pb_close/models/*` (suggestion and late reads), `pb_mission/static/src/js/pb_close_lens.js` + its XML + `pb_mission/i18n/*`; `pb_hr_payroll_formula/models/input_provenance.py` (1 line); `pb_source_atlas/models/pb_source_atlas.py` (1 line); optional `pb_attendance_flow/models/attendance_rule.py` (relabel `count_late_as`) | `pb_workforce_payroll_bridge`, `pb_timesheet_approval` files (override only), `pb_timeoff`, `pb_schedule` |
| **S5-C Rotating shift patterns** (item 6) | New module **`pb_shift_patterns`**: pattern, slots and members; "Generate N weeks as drafts" with `copy_week_checked` checks and a skip report; "from pattern" mark; registered Mission Control lens "Patterns" plus ⌘K rows | `pb_shift_patterns/**` (new); optional `pb_schedule/static/src/{js,xml}/pb_schedule.*` (toolbar button + `_applyPbCmd`) and `pb_schedule/i18n/*` | `pb_mission/static/src/js/pb_mission.js` (use the registry), `pb_hr_workforce` files (inherit `hr.shift.planning` from the new module) |

**Shared files inside S5: none edited by two phases.** The only seams the phases touch in common are these:
- **A and B both create leave kinds.** B creates its "Time off in lieu" kind with plain core and pb_timeoff fields. A's new fields must have defaults and **no required constraints**, so that B's create and older kinds keep working.
- **A and B both inherit `pb.ess.workforce`**, but different methods (A: `get_my_leave` / `_my_appliable_types`; B: `get_my_overtime`) and different templates (A: `portal_my_work_leave`; B: `portal_my_work_overtime`).
- **B's expiring time off shows correctly only with A's expiry filter.** Merge A before B, or ship both in one deploy (the step's deploy agent merges all three anyway). B's tests must not assert tile numbers that depend on A.
- **Install order:** `pb_time_pay` depends on `pb_timesheet_approval` (MRO above both overtime producers), `pb_close` and `pb_attendance_flow`. `pb_leave_setup` depends on `pb_timeoff` and `pb_ess_workforce`. `pb_shift_patterns` depends on `pb_schedule`. None depends on another S5 module.

## Collision list with the other teams building in parallel

| Other team's area | File S5 would touch | How | Plan |
|---|---|---|---|
| Self-service on /my (`pb_me_portal` and friends) | `pb_ess_workforce/models/ess_workforce.py` `get_my_leave` (:445-512), `_my_appliable_types` (:555-569), `get_my_overtime` (:1053-1091) | **override from S5 modules, no edit** | The self-service team must not rename these methods or change their return keys (`balances[*].balance`, `types`) without telling S5. If they also edit `get_my_leave`, agree the merge order. |
| same | `pb_ess_workforce/views/portal_templates.xml` `portal_my_work_leave` (:345), `portal_my_work_overtime` (:540) | **xpath from S5 modules, no edit** | xpath anchors on stable classes or ids. Ask the team to keep the tile loop (`:360-366`) and the overtime table. |
| same | `pb_me_team/models/pb_me_team.py` (`_balance_after` :251-264, overtime block :537-576) | read only. B may show "time off instead" in the manager's approval detail through the inbox adapter (`_approval_detail`), not through pb_me_team | none unless the team edits the overtime block |
| same | `pb_me_portal/models/pb_me_home.py:526-530` Leave card | read only (sums `get_my_leave` balances) | none |
| Job changes, contracts, pay scales (`pb_contracts`, `pb_workforce*`) | `pb_workforce_payroll_bridge/models/hr_payslip.py` | **B overrides above it, no edit** | If that team edits the bridge's `_get_formula_input_values`, B's subtraction must be re-tested. Tell them. |
| same | `pb_hr_payroll_formula/models/input_provenance.py` (VIAS) | **B: one-line edit** | the only unavoidable shared file. If pay scales also add a via, both lines merge trivially. Name it in both handovers. |
| same | `pb_hr_payroll_formula/models/application_payroll_source.py` | B overrides `_application_time_values`, `_application_source_catalogue` and `_application_domain_values` from its own module, no edit | A pay-scales change to the same methods must be merged with care (money path, W2A-2 fingerprint). |
| same | `pb_workforce_insights` | none | none |
| same | service start: `hr.employee.date_of_joining` (`pb_hr_payroll_formula/models/hr_employee.py:31`) | A reads it | If "Change job" or contracts changes how the service date is kept, tell S5-A. |
| Performance, surveys, people reports (`pb_lifecycle`, growth, `pb_explorer`) | none | none | Leave and lateness facts in Explorer are a later step, not S5. |
| Other WDGAP shared seams | `pb_settings`, `pb_mission.js`, `pb_hub` palette, `pb_approval_config/data/processes.xml` | registries and own-module data only, no edits | none |

## Decisions only the product owner can make

1. **Ready-made leave by country: how sure must we be before we offer it?** On the Kinds of leave screen there would be a button such as "Add Vietnam's standard leave". It fills in the usual kinds for that country, and HR checks and edits each one before it goes live.
   - **(a) Recommended.** Offer it now for Vietnam, Indonesia, Singapore, Malaysia, Thailand and India, clearly labelled "a starting point: check it against your own legal advice". HR must review every kind before it turns on. This is fast, but it carries a risk that a figure is out of date.
   - (b) Wait until a local adviser has checked each country. Nothing is offered until then (weeks to months), and every customer types their leave by hand meanwhile.
   - (c) Vietnam and Indonesia only for now, which are the countries we know best. Other countries get nothing yet.
   - In every option: should Cambodia be included, given that we have no Cambodia pay rules today?

2. **When leave builds up month by month, can people take days they have not earned yet?** Example: a 12-day allowance builds 1 day a month, and in March someone asks for 5 days.
   - **(a) Recommended.** A setting on each kind of leave, which starts at "Only what is earned so far". The request is refused with "You will have 5 days on 1 May", and HR can switch a kind to "the whole year's allowance".
   - (b) Always only what is earned. This is the strictest option and protects the company, but staff complain at the start of the year.
   - (c) Always the whole year's allowance, with earning mattering only when someone leaves. This is the friendliest, but the company can be owed days when people leave early.

3. **Time off instead of overtime pay: who chooses, and how much time off does an hour earn?**
   - **(a) Recommended.** The manager chooses "Pay it" or "Give time off" when approving the overtime, and 1 hour worked earns 1 hour off.
   - (b) The employee asks for time off when the overtime is entered, and the manager confirms. 1 hour earns 1 hour.
   - (c) A company rule per kind of day (for example, public-holiday work always becomes time off), at the overtime rate, so 1 hour earns 1.5 hours off. This is the most generous and the most work to explain.

4. **What happens to time off in lieu that is not used in time?** Say the default is 3 months.
   - **(a) Recommended.** It is paid out as overtime in the next pay run, with a reminder to the person a month before. This is the safest option where the law says overtime must be paid, but the build is larger.
   - (b) It disappears after a reminder a month before. This is simpler, but it may break the law in some countries and upset staff.
   - (c) It never runs out. This is the simplest, but balances grow without limit.

5. **Late minutes and pay: straight in, or confirmed first?**
   - **(a) Recommended.** Late minutes appear in the manager's weekly Close with an "Excuse" button. Only the minutes still counted when the week is locked go to the pay run, where the customer's own pay rule decides any deduction.
   - (b) Every late minute over the grace time goes to the pay run automatically. This is faster, but there is no chance to excuse a traffic jam or a machine fault.
   - (c) Show late minutes in reports only and never send them to pay, which is what happens today.

6. **Suggesting overtime for people who have no rostered shift.** Machines record when people come and go, but many companies never publish a roster.
   - **(a) Recommended.** Compare punches with the person's normal working hours (for example 8:00–17:00) when there is no shift, and mark the suggestion "compared with working hours". Late minutes then work the same way.
   - (b) Suggest only where a shift was published. There are fewer false suggestions, but companies without a roster get nothing.
   - (c) Suggest anything over a fixed number of hours a day (for example 8), whatever the roster says.

## Ledger candidates (new gotchas seen in this survey; add them when a phase hits them)

- **S5-1:** pay data file runs never call `_get_formula_input_values`. Overtime, approved weeks and any new input added through that seam do not reach them (`payroll_import_batch.py:3764-3810`, `hr_payslip_formula.py:1140-1154`).
- **S5-2:** late exceptions read the stale stored shift status, so they are dead outside demo data (finding 3).
- **S5-3:** holiday overtime reads `hr.holidays.public.line` (a v16 model) inside try/except, so it always gets an empty set. Real holidays are `resource.calendar.leaves` with no resource.
- **S5-4:** leave balance readers ignore allocation `date_to` (`ess_workforce.py:463-466`, `pb_timeoff.py:319-323`). The manager's balance-after does not.
- **S5-5:** the overtime rate lookup uses `employee_id.country_id` (nationality), not the payroll country (`overtime_request.py:93-107`).
- **S5-6:** stock Time Off configuration menus (kinds of leave, earning plans, Rize policy editions, openings, settlements) are invisible to every tenant user, because the launcher is pruned to the Payroll root (`pb_dashboard/models/menu_rails.py:14-26,61-96`).
- **S5-7:** the approved-weeks code (`pb_timesheet_approval/models/hr_payslip.py:69-114`) has no run-kind check, unlike the bridge. A Top-up or Extra run may take a week's overtime again (survey reading, needs a test).
