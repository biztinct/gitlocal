# WDGAP S8 — plumbing facts: job changes, contracts and structure

Study build-order step "Job changes, contracts and structure" (`outputs/workday-gap-study-2026-11-14/roadmap.json`
step 8; research rows in `research-data/03-staffing-org.json`, `04-compensation-benefits.json`,
`13-adjacent-products.json`). Read-only survey, 2026-11-15, on `origin/19.1` @ `7f0fa3aad`
(W2 deploy report). Every `path:line` is relative to the repo root and is **verified plumbing — do not
re-derive**; spot-check one line before relying on it, because parallel steps are building on the
same branch.

Read with: `docs/handovers/wdgap/WDGAP_LEDGER.md` (conventions, D1–D6, gotchas). D2 binds this step:
**no `pb_pack_*` rate, tax method or component is touched** — that includes adding HRA / special
allowance codes to the India pack and putting minimum-wage figures in anything.

White-label (binding for every proposed string below and in every handover written from this file):
the word "Odoo" never appears in anything a user can see or receive; "Payobook" never appears in a
generic `biz_*` module (QFM-1). Every new module proposed here is `pb_*`.

---

## 0. Corrections to the inputs (memory notes are stale on these points)

| Memory claim | Today on 19.1 |
|---|---|
| contract-drawer: "`hr.contract.create` auto-creates one `hr.contract.advantage` per template" | **Gone.** SCHEMECTX P2 removed the fan-out; every writer get-or-creates the line it needs, a missing line reads as 0 (`om_hr_payroll/models/hr_contract.py:117-140`). |
| pay-scales: "pb_pay bands have NO target/default wage" | No field called target, but every band has `min_amount / mid_amount / max_amount` (`pb_pay/models/pb_pay_band.py:83-85`) and `place_hire` suggests the middle (`pb_pay/models/pb_pay_bands.py:1205-1207`). |
| pay-scales: "`place_hire` writes nothing and nothing calls it" | Writes nothing (returns a dict, `pb_pay_bands.py:1134`, `:1167-1226`) — but it IS called: the "Place a new hire" dialog (`pb_pay/static/src/js/pay_hub.js:1551`) opened from ⌘K (`pb_pay/static/src/js/pay_palette.js:80-88`). No server caller. |
| pay-scales: "the only wage-writing hire path is `pb.people.contract.wizard.create_contract`" | **Four hire paths write a wage, none defaults it** — see §3.2. |
| pay-scales: "`pb.pay.apply` writes `hr.contract.wage` and must stay the single writer" | `pb.pay.apply` is a LOG row (`pb_pay/models/pb_pay_apply.py:61-100`). Writers of `hr.contract.wage` today: `pb_pay_apply.py:223` (review) / `:323` (undo), `pb_pay/models/pb_pay_change.py:421-423` (pay change), `pb_contracts/models/pb_contract_360.py:1748` (contract drawer), every creation path in §3.2, legacy `pb_hr_workforce_planning/models/compensation_cycle.py:163` (module still installable, uninstalled on the DBs per GROUP P6b). |
| pay-scales: "⌘K block 3460+" | Still free: used 4-digit sequences jump 3450 → 3500 (grep of every `sequence: NNNN` in JS). Also free: 3460–3490, 4030–4390, 4420–4990 (pb_learn starts at 5000, `pb_learn/static/src/hub/learn_palette.js:24`). Highest static today 4410 (`pb_fund_payments/static/src/js/fund_palette.js:41`). |

---

## 1. Shared plumbing every phase of this step uses

### 1.1 Where a job, team and pay actually live (Odoo 19 in this build)

- `hr.version` holds `date_version` (`hr/models/hr_version.py:53`), `employee_type` (`:108-115`),
  `department_id` (`:116`), `job_id` (`:119`), `job_title` (`:120`), `work_location_id` (`:131`),
  `resource_calendar_id` (`:139`), `wage` (`:167`), `contract_type_id` (`:174`).
- `hr.employee` reaches them through `_inherits = {'hr.version': 'version_id'}`
  (`hr/models/hr_employee.py:43`); `employee.write` routes them to the CURRENT version **in place**
  (`:1417-1432`). `parent_id` (manager) lives on `hr.employee` itself (`:191`).
  `create_version(values)` needs `date_version` (`:556-627`). **No `pb_*`/`biz_*` code ever calls
  `create_version` or writes `date_version`** (grep `create_version(`, `'date_version'`).
- `hr.contract` (vendored `hr_contract`) has its OWN stored `department_id`, `job_id`,
  `resource_calendar_id` computed from the employee **only when `employee_id` changes**
  (`@api.depends('employee_id')`, `hr_contract/models/hr_contract.py:28-31`, `:86-93`). So changing
  the employee's job does NOT change the contract's job, and vice versa. `wage` is its own field
  (`:41`).
- Who reads which: Pay review roster `COALESCE(c.job_id, v.job_id)` — contract first
  (`pb_pay/models/pb_pay_review.py:686-687`); Explorer facts read department/job from `hr_version` as
  of the period end in raw SQL (`pb_explorer/models/pb_fact_builder.py:56-66`); Decision Room roster =
  contract wage + version dept/job (WFPLAN WF7).
- **Rule for any builder: a job/team change writes BOTH the employee (current version, in place) AND
  the running contract's `job_id` / `department_id`**, or screens disagree. Writing in place, no new
  contract and no new `hr.version`, is the standing owner ruling (Records Desk ruling 2026-08-29;
  UPDATES D2 "one contract + dated pay history").

### 1.2 Paths that can change a payslip figure (call these out in every handover)

1. **Contract wage** → input codes `BASIC` / `WAGE` / `BASE` read `contract_id.wage`, current value
   (`pb_hr_payroll_formula/models/hr_payslip_formula.py:736-748`).
2. **Contract pay lines** (`hr.contract.advantage.amount`, `om_hr_payroll/models/hr_contract.py:7-24`)
   → `contract_component` resolver rungs (`pb_hr_payroll_formula/models/payroll_import_batch.py:3149`,
   `:4753-4794`); the engine reads CURRENT amounts only (`_contract_component_amounts` /
   `_contract_component_values`, `payroll_import_batch.py:2212-2262`).
3. **Department** → which pay scheme pays the person: a team/contract department write marks
   "Paid by" stale (`pb_scheme_map/models/hr_employee.py:220-250`), and the map resolves team →
   division → rule → only scheme (`pb_scheme_map/models/pb_scheme_map.py:~380-457`). **A transfer can
   move a person to another scheme** (other formulas, other currency).
4. **Employee/contract fields that application-data schemes may read**: `EMPLOYEE_FIELDS` incl.
   `department_id`, `job_id`, `job_title`, `employee_type`, `pb_job_level`
   (`pb_hr_payroll_formula/models/application_domain_sources.py:19-33`) and `CONTRACT_FIELDS` incl.
   `costcenter`, `contract_type_id`, `pb_payroll_contract_type`, `date_end`
   (`:39-44`). Only rize uses application-data runs; `pb_payroll_contract_type` IS read by the VN
   formula (VNPTYPE, `tools/data/rize_focused_payroll_plan.json:888-893`).
5. **Dated history**: `hr.contract.advantage.change` (`pb_hr_payroll_formula/models/contract_component_change.py:6-110`,
   shared writer `log(...)` `:80-110`) is read by proration (`payroll_import_batch.py:2563-2583`) and by
   retro (`_prepare_retro_adjustments`, `:2716-2790`, uploaded-file path only — PR2 facts §4).
   **A wage write creates no change row on ANY path**, so neither proration nor back pay ever sees a
   wage change. Writers of change rows: Records Desk (`pb_records/models/pb_records_desk.py:1815`),
   contract drawer (`pb_contracts/models/pb_contract_360.py:1947-1969`, always dated today `:1964`),
   import batch (`payroll_import_batch.py:5297`).

### 1.3 Approval engine seams (clone, never edit)

- `register_chain(model, key, submit_state, driven, …, amount_field, date_field, state_field)`
  `biz_approval_workflow/models/chain_shim.py:63-101`; `biz.approval.chain.mixin` `:174`; route
  facts `_chain_facts` / `_chain_fact_specs` read by the route builder (`:286-298`, `:375`).
- Adapter hooks `biz_approval_workflow/models/adapter.py:20-182` (`_approval_context` :56,
  `_approval_apply` :79, `_approval_detail` :118, `_approval_return` :159, `_approval_reject` :163,
  `_approval_withdraw` :173).
- Proposal mixin `biz_approval_workflow/models/proposal.py:86` — `propose(...)` `:256-296`,
  `_apply_<kind>` dispatch `:576-584`, `_approval_apply` re-checks the snapshot `:586-612`.
- **Compact precedent to clone:** `pb.contract.proposal` (`pb_contracts/models/contract_approval.py:49-152`:
  `_live_snapshot` :74-82, `_proposal_rows` :100-120, `_apply_terms` :123-133, `_approval_seed_default`
  with `Seed.lay(...)` :136-152).
- A new process key ships in the NEW module's own data file (precedent
  `pb_orgchart/data/approval_process.xml:8-14`, `pb_records/data/records_bank_process.xml:14-15`), never
  in `pb_approval_config/data/processes.xml`. `seed_adapters` picks every model's
  `_approval_seed_default` up (`pb_approval_config/models/seed.py:251-279`).
- Gotchas that apply: PRB-W1 (no `date_field` whose date can be in the past), W2B-2 (`_approval_context`
  runs as the last decider → read under sudo), QF3-6 (withdraw hook holds its own savepoint).
- Existing keys near this step: `paychange` (`pb_approval_config/data/processes.xml:141-148`),
  `contract` (`:150-156`), `records` (`:107-113`), `records_bank`, `master` (`:158-164`), `payreview`,
  `extension` (`processes_p6.xml:18-19`, `:46-53`), `orgplan`, `letters` (`processes_p7.xml:15`),
  `hiring_request` (`pb_hiring/models/requisition_approval.py:34-45`).

### 1.4 Screen seams (all pluggable without editing the owner's file)

- People hub lens registry `pb_people_hub_lens` (`pb_people_hub/static/src/js/people_hub.js:102`; extras
  sit between Employees and Insights, `:117-144`). Sequences used: orgchart 30, contracts 38, records 40,
  updates 41, pay 45, where 48, assets 50, newjoiners 52, probation 54, exits 56. Rail never scrolls
  (MORE fold, RAIL FIT programme).
- HubShell lens config `pb_hub/static/src/js/hub_shell.js:62`, `:80-91`.
- ⌘K registry `pb_hub_palette` — free blocks in §0.
- Employee side panel `Employee360Drawer` (`pb_employee_vault/static/src/js/employee_360.js:22`, registered
  `pb_people_drawer`/`employee_360` `:330`). Tabs and header buttons are HARD-CODED in
  `pb_employee_vault/static/src/xml/employee_360.xml:50-78`; the only registry is the chip row
  `pb_employee_360_chips` (`employee_360.js:55-70`; users `pb_scheme_map/static/src/js/scheme_map_chip.js:68`,
  `pb_employee_vault/static/src/js/fillin_chip.js:59`). A new header button = OWL `t-inherit` +
  `patch()` from the new module.
- Contract drawer (`pb_contracts/static/src/js/contract_360.js`, registered `pb_contracts_drawer` `:1517`);
  soft registry precedent `pb_take_home` read at `contract_360.js:815-844`, button
  `contract_360.xml:310-314`, registered by `pb_formula_studio/static/src/js/take_home.js:319`.
- Quiet board + filter kit: `pb_contract_lifecycle/static/src/js/contractlife_board.js:243-260`
  (`useFilterKit`, `PbFilterLayout` :48-49); server `pb.contractlife` on `pb.filter.mixin`
  (`pb_contract_lifecycle/models/pb_contractlife.py:53-54`, `_pbf_*` hooks `:298-535`; mixin
  `pb_filter_kit/models/filter_mixin.py:50`). W2B-4 if a base domain depends on a screen value.
- My Payobook home extension hook `_pbme_extra_cards` (precedent `pb_me_project_time/models/pb_me_home.py:26`).
- Letters: `pb.letter.template` / `pb.hr.letter` (`pb_lifecycle/models/letter.py:57,85`); types
  `LETTER_TYPES` (`pb_lifecycle/models/lifecycle_common.py:71-85`, no promotion/transfer type). A new type
  = `selection_add` on `pb.letter.template.letter_type` from the new module (no edit). Pay's own template
  lookup falls back to `custom` + name marker (`pb_pay/models/pb_pay_apply.py:420-436`).

---

## 2. Item 1 — one guided "Change job" (promotion, transfer, pay change together)

### What exists today (four screens, four writers, three approvals)

| Piece | Where | What it writes | Approval | Dated? |
|---|---|---|---|---|
| Pay change | `pb.pay.change` `pb_pay/models/pb_pay_change.py:57-104`; KINDS promotion/correction/market/other `:35-40`; screen `PbPayChanges` `pb_pay/static/src/js/pay_review.js:1593` | `hr.contract.wage` in place under sudo (`:421-423`); `new_job_id` → **contract** `job_id` only, failure swallowed (`:424-431`); a `pb.pay.apply` log row (`:432-443`); letter (`pb_pay_apply.py:337-388`) | key `paychange`, HR lead → finance only if above guidance → director (`pb_pay/models/pb_pay_approval.py:40-71`); no `_approval_apply` — Apply is a separate manual action (`pb_pay/models/pb_pay_reviews.py:1215-1221`) | **No: wage written at once whatever `effective_date` says** (`:449-455` only prints the date) |
| Pay change undo | `action_undo` `pb_pay_change.py:460-478`; `_restore` `pb_pay_apply.py:312-334`; `UNDO_HOURS = 24` `:42` | old wage back | — | **does not restore the job** |
| Job on a pay change | server accepts `new_job_id` (`pb_pay_reviews.py:1193-1205`, `:1236-1251`) | — | — | the screen never sends it (`pay_review.js:1712-1718`); only the backend form shows it (`pb_pay/views/pb_pay_review_views.xml:141`) |
| Records Desk / Updates | `pb.records.desk.apply_changes(config_id, changes, note, source, start_date, hold_scope)` `pb_records/models/pb_records_desk.py:2043-2091`; catalogue `pb_records/models/master_records.py:12-20` (employee `department_id`, `job_id`, `job_title`, `parent_id`, `coach_id`, `work_location_id`, `resource_calendar_id`, `employee_type`, `pb_job_level`; contract `wage`, `date_start`, `date_end`, `type_id`, `department_id`, `costcenter`, …; pay lines `c:<CODE>`) | in place `record.write(vals)` (`:1695-1705`); pay lines + change rows (`:1713-1755`, `:1806-1825`) | keys `records` / `records_bank`; lanes details/pay/bank (`pb_records/models/records_approval.py:43-53`, `:91-100`); on the Records screen details+pay are ONE proposal, through Updates (`records_lanes` ctx) they split (`pb_records_desk.py:2094-2111`) | yes: future date → approved then held "Scheduled" (`records_approval.py:798-801`), hourly job `_cron_start_scheduled` (`:1039-1069`, `pb_records/data/records_cron.xml:13-22`), ≤ 366 days ahead (`:128`); past date = written now and "recorded as starting that day", **nothing recalculated** (`pb_updates/models/updates_dates.py:1-18`) |
| Org chart move | `pb_orgchart/models/pb_orgchart_write.py` `move`/`_do_move` `:255-286`, `move_many` `:288` → `_set_managers` `:171-189` | `parent_id` only; `fill_role` writes `job_id`/`job_title` (`:492`); **never `department_id`** | none for direct moves (`_run` `:192-209`, rights check only) | no |
| Org chart plan | `pb.orgchart.plan` `pb_orgchart/models/pb_orgchart_plan.py:33-91`, kinds `:60-69`, `_apply_one` `:482-530` | same as moves | key `orgplan`, `date_field='effective_date'` (`:38`, `:45-50`) | yes: daily `_cron_apply_due` (`:429-433`) |
| Contract drawer | `save_contract_360` `pb_contracts/models/pb_contract_360.py:1711-1816`; terms `_TERMS` `:82-106` | contract `job_id`/`department_id` straight through (`:1883-1891`); money terms through `pb.contract.proposal` (`contract_approval.py:45-46`) | key `contract` for money terms only | no (change rows dated today) |
| Manager side | `pb_me_team` | **nothing**: read + approve only (`pb_me_team/models/pb_me_team.py:62-847`; routes `pb_me_team/controllers/portal.py:37-156`) | — | — |

### What is missing

- One action that changes job, title, team, manager, work location, schedule, wage and named pay
  lines together, with **one reason, one start date, one approval, one letter, one undo**.
- A start date that is honoured for pay (pay change writes the wage at once).
- Undo that restores the job (pay change undo restores the wage only).
- A promotion/transfer letter type (`LETTER_TYPES` has none).
- A trail: "job history" on the person. The timeline only sees chatter/audit.

### Precedent to clone

- Proposal model on `biz.approval.proposal.mixin`, cloned from `pb.contract.proposal`
  (`pb_contracts/models/contract_approval.py:49-152`), own key (proposed `jobchange`), facts for the
  route builder: `kind`, `pay_rise_pct`, `above_band` (read `pb.pay.position`), `changes_team`,
  `changes_scheme`.
- Scheduling: clone the Records Desk "Scheduled" state + hourly cron (`records_approval.py:798-801`,
  `:1039-1069`), or the org-plan daily due job (`pb_orgchart_plan.py:429-433`). Writes at apply time,
  never before the start date.
- Wage + undo + letter: create `pb.pay.apply` rows through the ORM (fields `pb_pay_apply.py:61-100`;
  add a `job_change_id` M2O by inheritance from the new module) and call `_make_letters` — so the Pay
  area's "Changes" history, the 24-hour undo window and the letter queue (`_cron_letters` `:391-407`)
  work unchanged. Extend the restore in the new module to put job/team/manager back.
- Pay lines: `hr.contract.advantage.change.log(...)` (`contract_component_change.py:80-110`) dated with
  the change's start date — the one way proration will see a mid-month change.
- Drawer UI: `Employee360Drawer` look (indigo = contract, teal = person; contract-drawer ruling), a
  right slide-over with current → new columns, picker from `lookup_contract_m2o` style look-ups, the W2-C
  `pb_take_home` soft-registry link for "work back from take-home" beside the new wage.
- Entry points: Employee side panel header (t-inherit/patch `employee_360.xml:50-56`), org chart person
  card (patch, `pb_orgchart` JS), ⌘K block 4460–4469, Pay › Changes "New change" can deep-link in.

### Risks (LOUD)

- **Payslip figure:** wage and pay-line writes (§1.2 #1, #2). Written early = this month's payslip
  changes. The handover must forbid writing before the start date and must re-check, at the scheduled
  write, that no pay run for that month is already approved (pay-run awareness exists in pb_records
  P2c — reuse its check).
- **Payslip figure:** a team change can move the person to ANOTHER pay scheme (§1.2 #3). The drawer
  must show "Paid by changes from X to Y" before sending (`pb.scheme.map.resolve_many`, UPDATES P2b used
  it) and the route fact `changes_scheme` must exist.
- **Payslip figure (rize):** application-data schemes may read job/department/level/cost centre
  (§1.2 #4). Show a line when the person's scheme reads any field being changed (`declared_sources()`).
- **Back pay:** a start date in the past gets no back pay on any path (§1.2 #5). Owner question Q2.
- Two open contracts: never create a new contract (D1 of contract lifecycle,
  `pb_contract_lifecycle/models/contract_common.py:9-14`).
- Rights: CD3 — a plain HR officer cannot read `hr.contract`; adapters read under sudo after their
  own gate (W2B-2).

### Modules a builder edits

New module `pb_job_change` (proposal, scheduler, drawer, letters `selection_add`, ⌘K, own process row,
`pb.pay.apply.job_change_id`, tests, vi/id `.po`). **Edits no existing file** if the header button and the
org-chart card button are `t-inherit` + `patch()`. Depends on `pb_records`, `pb_pay`, `pb_orgchart`,
`pb_employee_vault`, `pb_contracts`, `pb_lifecycle`, `pb_scheme_map`, `biz_approval_workflow`.
Non-goals: editing `pb_pay_change.py` (its job-on-contract-only behaviour stays; flag it in the report),
manager-started proposals on `/my/team` (self-service team's area; leave a server method they can call
later), PayAI actions, `hr.version` dated versions.

---

## 3. Item 3 — pay scales with steps (already designed)

### 3.1 State of the design

- Blueprint `docs/design/pay-scales-blueprint.html` (commits `bc3c7eb05`, `7ba8dd8a2` "pay policy is
  scoped to the pay scheme"); artifact link in memory `pay-scales-program`. **Design stage, nothing
  built.** No `pb.pay.scale`, step, policy or floor model exists anywhere (grep `scale`, `step`,
  `pay_policy`; the only `rating_scale` is performance ratings, `pb_pay/models/pb_pay_guidance.py:60,145`;
  legacy `wfp.pay.grade` has ranges, no steps, `pb_hr_workforce_planning/models/pay_grade.py:8`).
  `hr.formula.config.pb_pay_policy_id` does not exist.
- Blueprint model (Part C + engineers' notes): `pb.pay.scale` (country, currency, company_ids, date_from,
  mode amount|coefficient, base_rate) + `pb.pay.scale.cell` (grade, step_no, amount|coefficient) +
  `pb.pay.scale.package` lines naming an `hr.contract.advantage.template`; contract fields `scale_state`
  on|pinned|drifted, `scale_cell_id`, `pin_reason`; `pb.pay.policy` keyed by scheme
  (`hr.formula.config.pb_pay_policy_id`, many schemes → one policy, never the advance scheme, fallback
  company house rules in `pb.pay.settings` `pb_pay/models/pb_pay_settings.py:15`); `pb.pay.revision` on
  the chain mixin producing `pb.pay.apply` rows; `pb.pay.floor` dated wage floors.
- Build plan in the blueprint: P1 ladder + floor + chip; P2 joiners + policy paragraph + portal page; P3
  revisions (true cost, approval, apply + undo, arrears, letters); P4 step-ups + group view + polish.
- **Open owner decisions (Part I), none answered:** above-step people keep pay; scale change needs HR +
  Finance approval; backdated → automatic arrears line; steps optional; grade packages fill
  allowances; employees see own grade/step; policy per scheme (owner asked, answered by
  recommendation only); VN floor region on company with location override; no benchmark data; phased
  build. → owner question Q4.

### 3.2 Verified against today's code

- (a)(b) see §0. Bands: `pb.pay.family` (`pb_pay/models/pb_pay_family.py:20-31`), `pb.pay.band`
  (`pb_pay_band.py:65-100`, `level` Integer `:74-76`, `MAX_LEVEL = 12` `:61`, no-overlap date check
  `:159-177` — the constraint to clone), `pb.pay.band.job` (one band per job, `:360-398`),
  `hr.contract.pb_band_id` / `pb_position_pct` / `pb_band_state` (`pb_pay/models/hr_contract.py:31-42`),
  `pb.pay.position` one row per open contract rebuilt by `recompute_all` (`pb_pay_position.py:44-78`)
  + daily cron (`pb_pay/data/ir_cron.xml:22`), rebuild on contract write in precommit (GR44) honouring
  `pb_pay_no_rebuild`.
- Pay lens tabs bands / fairness / review / changes in `tabDefs()` (`pb_pay/static/src/js/pay_hub.js:140-148`,
  default `:190`; action `pb_pay` `:1745`). **A new "Scales" tab needs an edit of `tabDefs` in pb_pay**
  — the one unavoidable edit of an existing file for this item (or a registry added there once).
- Wage-writing hire paths, none defaults the wage:
  1. `pb.people.contract.wizard.create_contract` (`pb_people_advanced/models/people_wizards.py:160-191`,
     `'wage': float(vals.get('wage') or 0.0)` `:191`; `pb.newhire.proposal` approval first `:165-187`);
     onboarding passes `vals['wage']` through (`:119-128`); renewal prefill `get_defaults(renew_from=)`
     (`:141-149`).
  2. Updates joiners sheet: typed cell, positive number required (`pb_updates/models/updates_joiners.py:556-564`)
     → `Onboard.create_employee` (`:824-828`).
  3. Hiring "joined": `action_confirm_joined` (`pb_hiring/models/offer_closure.py:70`) → `_ensure_contract`
     (`:252`) does `hr.contract.sudo().create` directly (`:263-269`), wage = largest monthly earning line on
     the offer (`:302`, `_basic_line` `:313-326`); **writes no pay lines**.
  4. Others: `pb_workseg/models/pb_assignments.py:598`, `pb_hr_payroll_base/wizards/employee_import_wizard.py:632`,
     `om_hr_payroll/models/hr_zoho.py:453,482`.
- Apply/undo/letters to reuse: `preview_review` (`pb_pay_apply.py:103`), `apply_review` (`:176`),
  `undo_review` (`:286`), `_restore` (`:312`), `_make_letters` (`:337`), `_cron_letters` (`:391`).
- Paid-by: `hr.employee.pb_paid_by_id` readonly indexed M2O to `hr.formula.config`
  (`pb_scheme_map/models/hr_employee.py:47`) + `pb_paid_by_advance_id`, `pb_paid_by_rung`,
  `pb_paid_by_stale` (`:51-60`).
- Legacy VN minimum wage: `_get_vietnam_minimum_wage` `pb_hr_payroll_vietnam/models/hr_contract_vietnam.py:65-73`
  (4,680,000 / 4,160,000 / 3,640,000 / 3,250,000 — 2022 figures), enforced on `vietnam_basic_salary`
  (`:75-85`). **This is Step-1 territory (D2, study Step 1 "update minimum wages", "minimum-wage check on
  every pay run") — the wage-floor table and its figures are NOT part of S8.**
- pb_pay manifest `19.0.3.8.0`, depends `base, hr, mail, portal, om_hr_payroll, biz_approval_chain,
  biz_approval_workflow, pb_group, pb_hub, pb_import_kit, pb_people_hub, pb_explorer, pb_lifecycle,
  pb_me_portal, pb_filter_kit` (`pb_pay/__manifest__.py:76-97`).

### What a builder needs (S8 scope = blueprint P1 + the joiner half of P2, minus floors and portal)

1. New module `pb_pay_scales` depending on `pb_pay`, `pb_contracts`, `pb_people_advanced`,
   `pb_updates`, `pb_hiring`, `pb_scheme_map`.
2. Models scale / cell / package as in the blueprint; job → grade by extending `pb.pay.band.job`
   (inherit, new field) — never a second job-to-grade map.
3. Contract status chip On scale / Pinned (reason) / Drifted in the contract drawer (pb_contracts — same
   phase owns it) and in the employee panel via `pb_employee_360_chips` (no edit).
4. Joiner default: override `create_contract`, `_ensure_contract`, and the joiners-sheet value by
   `_inherit` in the new module — **only when the wage box is empty**; a typed wage wins and pins with a
   reason. Explain chip "from Grade 3 step 1 of the Retail store scale".
5. Package lines get-or-create `hr.contract.advantage` for components the person's scheme HAS
   (SCHEMECTX: never another scheme's component), each logged with `contract_component_change.log`.
6. "Start from what you pay" proposal from median wages (precedent: band proposal from wages, GROUP P6a).
7. Wire check: warn when the scheme's `BASIC/WAGE/BASE` does not come from the contract
   (`rule.declared_sources()` + `_config_kind_rank()` — SOURCECTL accessors, CD5).
8. Non-goals in S8: wage floors (Step 1), revisions with true cost + arrears (blueprint P3), time-based
   step-ups (P4), policy sentence composer (P2 — may follow), portal "your pay on the scale" page
   (self-service team's `/my`; the `_pbme_extra_cards` hook keeps it pluggable later).

### Risks (LOUD)

- **Payslip figure:** joiner defaults write `hr.contract.wage` and pay lines (§1.2 #1, #2). Only on
  CREATE, only an empty box, always shown before saving. Nothing touches existing contracts in S8.
- A scale cell edit must never write any contract (blueprint safety rail); proven by a test that counts
  `hr.contract` writes.
- rize schemes on application data may not read the contract wage at all — the wire check must say so.

---

## 4. Item 4 — building pay from a total package (India CTC)

### What exists

- Contract pay = `hr.contract.wage` "monthly gross wage" (`hr_contract/models/hr_contract.py:41`) + pay
  lines `hr.contract.advantage` (`om_hr_payroll/models/hr_contract.py:7-43`: `contract_id`,
  `advantage_template_id`, related code, bounds, `amount`; template `code`, `default_value` `:143-151`).
  Lines are per scheme, get-or-create (SCHEMECTX).
- Package view `pb.employee.comp.annual_total` sums checked lines only (`pb_comp_ben/models/employee_comp.py:57`,
  `:80-104`); its docstring: "THERE IS NO CTC MODEL ANYWHERE IN THIS PRODUCT" (`:4`).
- Offer employer cost works UP from gross (`pb_hiring/models/offer_cost.py:71-127`: sums non-statutory
  offer lines `:90-92` → profile `gross_input_id` `:93` → strict rule evaluation `:100-117` → sums
  `employer_rule_ids` `:118-123` → HTML estimate only `:126-127`).
- **Solver precedent (W2-C, live):** `pb_formula_studio/models/take_home.py` —
  `take_home_open(config_id, payslip_id, contract_id)` `:433`, `take_home_solve(config_id, target,
  item_code, payslip_id, contract_id)` `:483`; inputs from the latest payslip of that scheme or the
  contract's component values (`:287-313`); `_Engine` compiles once (`_pb_formula_steps` +
  `formula_program.run_sample`, `:68-107`), builds lines inside an unsaved `hr.payslip.new(...)`
  (`:123-131`, W2C-1), reads totals via `pb_pay_totals` (`:142-147`), `diagnose` lets errors through
  (`:150-181`, W2C-2). Search `pb_formula_studio/models/take_home_solver.py:15-41` (bracket ×1.6 then
  doubling, 12 samples, bisect on the currency grid; `MAX_EVALS = 200`, `MAX_BISECT = 60`). Writes
  nothing (`take_home.py:8-16`); `can_use` only for the scheme's wage codes (`:638-639`). Contract
  drawer link via `pb_take_home` registry (§1.4).
- Employer-cost marker: `hr.formula.rule.net_role` value `employer_cost`
  (`pb_hr_payroll_formula/models/formula_net_role.py:602-610`) → band `ERCOST`
  (`om_hr_payroll/models/pay_bands.py:35-42`) → `pb_pay_totals()['employer_cost']` (`:116`). **Caveat:**
  a line with no role and category `COMP` falls back to `DED` (`:53`).
- India pack (report only — D2, do not touch): `pb_pack_in` `19.0.1.0.1` (`pb_pack_in/data/config_template_in.xml:18`):
  inputs `BASIC` ("Basic + DA"), `ALLOWIN`, `BONUS`; `GROSS`, `EPFBASE = MIN(BASIC,15000)`, `EPFDED`,
  `EPFCOMP = EPFBASE × 0.12`, `ESICOMP`, `ERCOST = GROSS + EPFCOMP + ESICOMP` (category COMP), PT, TDS,
  NET. **No HRA, no special allowance, no gratuity code.** Legacy `pb_hr_payroll_india` has no CTC field
  (has `pf_employer_rate`, `gratuity_*` on the contract, `pb_hr_payroll_india/models/hr_contract.py:11,25-26`).
- Known blemish: `offer_calc` (`pb_formula_studio/models/pb_formula_studio.py:13846`) still builds bare
  lines that total 0 where pb_payruns is installed (`:13954-13958`, W2C-1) — do not copy it.

### What is missing

Enter a yearly total (e.g. ₹12,00,000) and get every pay item of the person's scheme filled so that
12 × (gross + employer contributions) = the total, shown side by side before saving, then written to the
wage + pay lines in one approved save.

### Design facts a builder needs

- A CTC split is not a single-unknown search: the scheme's own formulas already define the dependent
  items (HRA = x% of basic, PF on min(basic, ceiling)); what the user chooses is (a) basic as a share of
  the total or a fixed amount, and (b) the ONE balancing item ("special allowance") that takes the rest.
  The W2-C solver is reused as-is for (b): target = monthly total, function = gross + employer_cost of
  the in-memory payslip, unknown = the balancing item.
- **Definition hazard:** in the pack, `ERCOST` is itself a COMP line equal to GROSS + EPF + ESI. If such a
  line carried `net_role = employer_cost`, gross would be counted twice. The tool must define the total
  from `pb_pay_totals` bands and a test must pin it on a DEMO India-shaped scheme built in the test
  (PRE-2/W2C-3: build the scheme whole, never edit a live one).
- Which scheme items exist decides what can be split; the pack has no HRA/special, so the demo needs a
  DEMO scheme with them (test fixture or demo data — never a pack edit).
- Write path: the drawer's normal save (`commitTerm` → `save_contract_360`, money terms through
  `pb.contract.proposal`), like W2-C's "use" button (`contract_360.js:841`).

### Risks (LOUD)

- **Payslip figure:** writes wage + several pay lines at once (§1.2 #1, #2). Read-only until the person
  presses Use; every value goes through the contract approval; components logged with change rows.
- Unknown live footprint: whether any live DB has an India scheme is not visible from the repo — the
  deploy agent checks (`hr.formula.config` country IN) before claiming a live demo.

### Modules a builder edits

New module `pb_pay_package` (server model reusing `take_home_solver` functions by import, OWL dialog
registered in a `pb_build_total` soft registry, Formula Studio Tools entry by registry). Contract drawer
button: edit `pb_contracts/static/src/xml/contract_360.xml` + `contract_360.js` (the only shared file,
owned by the same phase as pay scales). Non-goals: offers in Hiring (pb_hiring is crowded by the
self-service team's internal applications; seam = same server method later), Pay Review "raise the
total", any pack change.

---

## 5. Item 2 — fixed-term renewal limits (Vietnam, Indonesia)

### What exists

- Contract decisions module `pb_contract_lifecycle` `19.0.1.3.2`. Ruling D1: extend / make permanent
  always create a NEW contract; the old one is never edited (`contract_common.py:9-14`,
  `contract_review.py:31-36`). Vocabulary `REVIEW_STATES` (`contract_common.py:23-30`), `DECISIONS`
  terminate "Let it end" / extend / convert "Make it permanent" (`:42-46`), `NON_PERMANENT_TYPES`
  (`:67-68`), `TYPE_WORDS` (`:74-89`, "fixed-term" deliberately absent `:79-85`; 'agency'/'outsourced' →
  contractor `:86-87`), `P_EXTENSION_MONTHS` default 12 (`:102,116`).
- `pb.contract.review` (`contract_review.py:67-123`): `open_for()` reads one contract, not the chain
  (`:180-247`); **`decision_preview()` returns a `blocked` list (`:300-356`) and the board already
  disables the button for any choice with a non-empty list** (`static/src/js/contractlife_board.js:517-524`,
  `static/src/xml/contractlife_board.xml:543-550`) — the seam for a warning or a stop. Extend →
  `action_request_extension` (`:425-465`) → approval → `_on_extension_approved` (`:467-487`) →
  `_build_new_contract` (`:606-697`, via the People wizard `:633`, `:654`, draft `:650`,
  `pb_renewed_from_id = old.id` `:686`). Make permanent → `_convert_now` (`:585-601`), category swap
  `_permanent_contract_type` (`:699-730`).
- `pb.contract.extension` key `extension` (`contract_extension_approval.py:28-35`), route facts months /
  has_named_approver / escalated (`:48-64`), default route manager → lifecycle role (`:101-113`).
- Chain link `hr.contract.pb_renewed_from_id` / `pb_renewal_ids` (`pb_contract_lifecycle/models/hr_typing.py:320-331`).
  **No renewal counter, no total-length figure, no country policy.** Contracts made before Payobook have
  no link (imports create one contract).
- Contract kind fields: `hr.contract.type_id` "Employee category" (required, `om_hr_payroll/models/hr_contract.py:72-74`;
  `hr.contract.type.country_id` `pb_hr_payroll_base/models/hr_payroll_structure_base.py:36-38`; rize
  relabelled by country + end date on 2026-11-04, FILLIN note); `contract_type_id` (`hr/models/hr_version.py:174`);
  `vietnam_contract_type` indefinite/definite/seasonal/probation (`pb_hr_payroll_vietnam/models/hr_contract_vietnam.py:18-23`,
  read as formula meta fallback `hr_payslip_formula.py:1375-1376`); `pb_payroll_contract_type`
  permanent/probation (`pb_employee_vault/models/payroll_profile.py:37-40`, **read by the VN pay formula —
  never retype it from end dates**). Indonesia: no PKWT/PKWTT field anywhere (grep `pkwt` → one note
  in `tools/prepare_rize_sg_id_master.py:138`).
- Policy precedents: `pb.probation.policy` (`pb_probation/models/probation_policy.py:25-117`, country from
  work address → employee → company `:88-99`, `policy_for` country then blank `:102-117`, list + board
  button `probation_views.xml:189,210`, `probation_board.js:732`); `pb.notice.policy`
  (`pb_offboarding/models/notice_policy.py:23-112`, data rows `notice_policy_data.xml:18,28`).
- Tabs "With an end date / Open-ended / All contracts" (`pb_contractlife.py:315-347`, `:495-553`).

### Pre-existing gap found (flag, do not fix silently)

**A renewed contract does not carry the old contract's pay lines, `vietnam_contract_type` or
`pb_payroll_contract_type`.** `_build_new_contract` copies wage, structure, structure type, schedule
(wizard prefill `people_wizards.py:141-149`) plus `CARRIED_FIELDS` (`contract_review.py:59-64`: type_id,
job_id, department_id, legacy allowance columns, costcenter, company_id) — grep finds no
`advantage` in `pb_contract_lifecycle/models` or `pb_people_advanced/models`. FILLIN fills only the
scheme's non-zero usual answers on create. **When the draft renewal becomes the running contract, any
typed allowance on the old one reads 0 on the next payslip.** The renewal-limits builder must report this
with a measured count on a copy (contracts renewed through the board whose new contract has fewer pay
lines than the old) and the owner decides; the fix is a small carry in an override, but it changes pay.

### What is missing

A per-country "fixed-term contract rules" policy (renewals allowed, longest total length, what counts),
a counter of fixed-term contracts in a row per person (Payobook's chain + an "earlier fixed-term contracts
before Payobook" number), and the sentence on the decision drawer and extension request: "This would be
the 3rd fixed-term contract in a row; the law expects a permanent one".

### Legal facts for seed rows (policy data, not pay numbers; mark "to confirm with an adviser")

- Vietnam, Labour Code 2019 art. 20: a definite-term contract is at most 36 months; on expiry, ONE further
  definite-term contract may be signed; after that an indefinite one (exceptions for older workers,
  foreign workers, some union officials and state-enterprise managers).
- Indonesia, PP 35/2021 art. 8: a time-based PKWT, including extensions, totals at most 5 years.

### Precedent / modules

New module `pb_contract_rules` (policy model cloned from `pb.probation.policy`, seed VN + ID rows, a
chain counter, overrides of `decision_preview`, `action_request_extension`, `_build_new_contract` by
`_inherit`, a chip on the contract decisions drawer by `t-inherit` of `contractlife_board.xml`, an
"earlier fixed-term contracts" field added to the Updates catalogue by overriding `_master_fields`
(`pb_records/models/master_records.py:12-20`)). **Edits no existing file.** Payslip risk: none, unless the
pay-line carry fix is approved (then LOUD).

---

## 6. Item 5 — cost centres, job page with levels, hiring freeze, "would rehire"

### 6.1 Cost centres

- Exists as free text: `hr.contract.costcenter` Char (`om_hr_payroll/models/hr_contract.py:94`), shown in
  the contract drawer (`pb_contracts/models/pb_contract_360.py:106`) and employee panel
  (`pb_employee_vault/models/pb_people_360.py:87-113`), carried on renewal (`contract_review.py:63`),
  fed by the connected system (`om_hr_payroll/models/hr_zoho.py`, `pb_hr_payroll_indonesia/models/hr_zoho.py`),
  a formula source (`application_domain_sources.py:41`), editable through Records/Updates (`master_records.py`).
- **Stored on every payslip line as `related='slip_id.contract_id.costcenter', store=True`**
  (`om_hr_payroll/models/hr_payslip.py:900`) — **editing a contract's cost centre rewrites the stored
  cost centre on that contract's PAST payslip lines** (history rewrite; not a money figure, but finished
  payslips change). LOUD for any bulk cost-centre fill.
- No cost-centre list/model; analytic distribution comes from the salary rule, not the person
  (`om_hr_payroll_account/models/hr_payroll_account.py:131,146`); payroll journal groups by account + side
  only (`pb_pay_delivery/models/payroll_journal.py:98-133`); old analytics "By Cost Center" really groups by
  department (`pb_hr_payroll_analytics/models/hr_analytics_personnel_costs.py:66,503-504`).
- Precedent: divisions — `pb.division` (`pb_group/models/pb_division.py:54-109`, `division_for(department,
  on_date)` `:109`), effective-dated `pb.division.link` with no-overlap (`:269-291`).
- Explorer dimensions are module-level dicts `_DIMENSIONS` / `_FILTERS` (`pb_explorer/models/pb_explorer.py:119-190`)
  and raw SQL in the fact builder (`pb_fact_builder.py:56-66`, `:228-290`) — **an Explorer dimension is
  an EDIT of pb_explorer, which the people-reports team owns.** Hand it to them (see §10).
- Builder default: `pb.cost.centre` (code, name, company) + department default + contract
  `pb_cost_centre_id`, with the existing Char kept as the written mirror (so renewal carry, connected
  system, formulas and the drawer keep working untouched). Fixing the payslip-line history (stamp the
  value at payslip compute instead of the related store) is an `om_hr_payroll` edit and is **out of S8
  scope; report it as an owner item.**

### 6.2 Job page with levels

- `hr.job` has no level; custom `hr.job` fields only `pb_manager_id`, `pb_reason`
  (`pb_orgchart/models/hr_fields.py:26-41`); methods in `pb_hiring/models/hr_job_ext.py:16`,
  `requests_p3.py:1396`. Core `hr.job.description` Html (`hr/models/hr_job.py:24`), `contract_type_id`
  (`:40`).
- Level-like fields today, all free text: `hr.employee.pb_job_level` Char
  (`pb_employee_vault/models/payroll_profile.py:20`, also a formula source), requisition `pb_role_level`
  Char (`pb_hiring/models/journey.py:525`, text input `views/request_pages.xml:214`), band `level` Integer
  per family (`pb_pay_band.py:74-76`), legacy `grade_id` (`pb_hr_workforce_planning/models/formula_rule_extension.py:38`).
- JD templates `pb.hiring.jd` (no job/level, `pb_hiring/models/jd.py:26-76`), `pb.hiring.jd.template.family`
  Char (`requests_p3.py:117-131`), seeds (`jd_templates_seed.py:20-176`).
- No route condition on level/grade: none of the chain implementers exposes one (nearest `above_band`
  `pb_pay/models/pb_pay_approval.py:110`).
- Builder default: named ladder `pb.job.level` (Settings › People, sequence = order), `hr.job` gains
  level, job family (`pb.pay.family`), description, band (read from `pb.pay.band.job`); a "Jobs" People
  lens (seq 58, ⌘K 4500–4520); a `pb_job_level`/`pb_role_level` mirror so formulas reading the text keep
  working. Change job (§2) and pay scales (§3) read the job page later; neither depends on it in S8.

### 6.3 Hiring freeze

- Role states setup / open / filled / closed (`pb_hiring/models/hiring_common.py:151-156`); request states
  (`:165-178`); budget "blocks nothing" (`:181-198`; watchers told, "Nothing waits for them",
  `requests_p3.py:270-273`). Requisition `pb.hiring.requisition` (`requisition.py:87-193`; `_ensure_job`
  writes `hr.job.no_of_recruitment` `:698-750`). Create entry `pb.hiring.act('create')` → `_act_create`
  (`pb_hiring/models/pb_hiring.py:601-643`, needs `_require_raise()` `requisition.py:246-247`). Steps
  `_open_for_candidates` (`requests_p3.py:426`), `_request_send_in` (`:825`), `_request_agree` (`:904`).
  The one hard gate `_offer_block_reason` (`requests_p3.py:1130-1153`; enforced `offer.py:608`,
  `esign.py:100`, `docusign.py:113`). Roles tab per-role actions `_act_open_role` / `_act_close` /
  `_act_mark_filled` (`pb_hiring.py:609-677`); **no bulk role action** (bulk only for candidates,
  `hiring_board.js:270,2018,2026`).
- Org chart open role = `hr.job` with `no_of_recruitment > 0` (`pb_orgchart_write.py:93`);
  `add_open_role(manager_id, title, reason)` adds ONE (`:409-445`), `close_role` (`:500-514`); no freeze
  (grep freeze/frozen).
- Builder default: `hr.department.pb_hiring_paused` (+ reason, until) and the same on `hr.job`; new role
  state "On hold" by `selection_add`; overrides of `_act_create`, `_request_send_in`,
  `_open_for_candidates`, `_do_add_open_role` say "Hiring is paused for this team: <reason>"; careers page
  hides paused roles; offers already in progress get a warning, not a stop (Q6). Pause switch on the org
  chart team panel and on the role (patch, no edit). Payslip risk: none.

### 6.4 "Would rehire" mark

- No field anywhere (grep rehire → comments only: `pb_lifecycle/models/journey_case.py:161`,
  `pb_onboarding/models/hr_employee.py:138`, `probation_policy.py:167`). Nearest: `pb.resignation.regrettable`
  "Sorry to lose them" HR-only (`pb_offboarding/models/resignation.py:120-125`), backend views only.
- Leaving journey steps (`pb_offboarding/data/journey_template_data.xml:46-152`); leaver's own answers in
  `pb.feedback.request.answers_json` (`journey_case_ext.py:40-171`, `pb_lifecycle/models/feedback.py:31,60,174`);
  exits board drawer `pb.exits.get_exit` (`pb_offboarding/models/pb_exits.py:641-705`) rendered at
  `exits_board.xml:373-376`.
- Hiring duplicates search `hr.applicant` only, 6 months (`pb_hiring/models/forms_p2.py:144`, `:651-653`,
  `:848-874`); **no check against current or former employees**; on joining, an employee is reused only
  through `applicant_ids` (`offer_closure.py:179-180`). Identity anchor available: `pb.person`
  (`pb_workseg/models/pb_person.py:61-91`, `national_id` :70, `email` :75) via `hr.employee.pb_person_id`
  (`pb_workseg/models/hr_employee.py:16`).
- Builder default: `hr.employee.pb_rehire` yes / no / not sure + reason, field-level HR-only `groups=`
  (PRC-W1 lesson), asked in the exits drawer (t-inherit) and settable for past leavers; the candidate
  drawer shows a quiet "Worked here 2022–2024 · would rehire: yes" when email / phone / ID matches an
  archived employee (applicant create hook by `_inherit`, candidate drawer patch). Never shown to
  managers or agencies; never a block.

---

## 7. Item 6 — approved Decision Room plan → open roles

- `pb_decision_room` `19.0.4.4.2`, depends `base, hr, mail, pb_hub, pb_import_kit, pb_people_hub,
  pb_home_hub, pb_group` (`pb_decision_room/__manifest__.py:100-114`); no reference to pb_hiring /
  pb_orgchart / open roles (grep). Closeout: "there is no code path from the room to an employee, a
  contract, a payslip or a pay run" (`docs/handovers/WFPLAN_CLOSEOUT.md:12-14`).
- Plan `pb.decision.plan` (`models/pb_decision_plan.py:88`): levers JSON in `state` (`:136`), status
  draft / proposed / approved / rejected (`:49-54`, `:149`), `action_propose` (to-dos, `:292`),
  `action_approve` gated on `_can_manage()` (`:334-346`), approval freezes the plan (`:237-245`),
  versions `pb.decision.plan.version` (`:57-74`, `_keep_version` `:252`). **Not on the approval engine.**
- Hiring moves: `state.moves = [{team, role, n, month}]` (`static/src/js/decision_engine.js:205-215`);
  team key `t<root department id>` (`models/pb_decision_room.py:731`, roll-up `_department_roots` `:566`),
  role key `r<job_id>` (`:722`) or an "other roles"/`other_teams` bucket (`:710-716`, `:755`); `n` may be
  negative (leavers); no manager per team in the baseline.
- Targets: `pb.hiring.act('create', payload)` (`pb_hiring.py:601-643`) or `_act_new_role` (recruiters,
  headcount ≤ 500, `facade_p3.py:281-306`); required `title`, `role_type` (default `new_role`),
  `department_id`, `company_id`, `headcount ≥ 1`, `currency_id` (`requisition.py:120-139,166,287-292`);
  `request_state` written by the system only (`requests_p3.py:377-397`). A requisition that opens writes
  `hr.job.no_of_recruitment` (`requisition.py:720-740`) — **so a hiring request already shows on the org
  chart as an open role; a separate org-chart write is not needed.**
- Builder default: glue module `pb_plan_hiring` (depends pb_decision_room + pb_hiring); on an APPROVED
  plan, "Make these hiring requests" lists every positive move (team, role, how many, month) with a tick
  each; creates DRAFT requests (`request_state` writing) linked back by `pb_plan_id` + move key
  (idempotent: a second press never duplicates); the room shows "3 of 5 lines have a request". Rights:
  the presser must be allowed to raise requests (`_require_raise`); otherwise the line says who can.
  "Other roles" bucket lines ask for a title. Negative moves are listed as "not handled here".
  Payslip risk: none (touches `hr.job` and requisitions only).
- Files: new module + a button in the room (patch of `pb_decision_room/static/src/js/decision_room.js`
  from the glue module; no edit if patched).

---

## 8. Item 7 — agency staff not on payroll

- Employment types `employee/worker/student/trainee/contractor/freelance` (`hr/models/hr_version.py:108-115`)
  + intern (`pb_contract_lifecycle/models/hr_typing.py:61-63`); no agency value.
- Vendors register `pb.vendor` (`pb_vendor_access/models/pb_vendor.py:39-136`), agreements with
  `renewed_from_id` (`:153-258`), portal (`vendor_portal.py:31-44`); `VENDOR_TYPES` has no staffing type
  (`vendor_common.py:42-51`); no employee link. `pb_hiring/models/agency_p7.py:94-119` is recruitment
  agencies' candidate submissions, not agency workers.
- **Why a non-payroll person must NOT be an `hr.employee`:** the pay run population is contract-driven
  (`pb_payrun_wizard/models/pb_payrun_wizard.py:661-737`, overlap `:700-707`) and **falls back to every
  company employee when no open contract exists** (`_undated_contract_population` `:739-751`); same in the
  standard wizard (`om_hr_payroll/wizard/hr_payroll_payslips_by_employees.py:49-61`); no `employee_type`
  filter anywhere; `hr.contract.type.is_payroll_enabled` is never read. Other population callers:
  `pb_payrun_wizard.py:553,614,810,859,957,1406,1575`, `application_payroll_wizard.py:19`,
  `pb_payroll_templates/models/templates.py:126`, `pb_payai_actions/payai/actions_amber.py:1072`,
  `pb_timesheet_approval/models/payrun_wizard.py:96`. Headcounts count every active employee: People
  (`pb_people/models/pb_people.py:91-102`), Insights (`pb_insights/models/pb_insights.py:547-548`),
  analytics (`pb_hr_payroll_analytics/models/hr_analytics_headcount.py:157-193`); scheme map gives a blank
  "No scheme covers this person yet" (`pb_scheme_map/models/pb_scheme_map.py:440-454`,
  `pb_payrun_wizard.py:345-353`).
- Builder default (Q5): a separate light record `pb.agency.worker` (name, photo, supplied by =
  `pb.vendor`, site/team, manager, start/end, agreement, documents, rate optional, status), a People lens
  "Agency staff" (seq 59, ⌘K 4470–4490), counts shown BESIDE headcount ("+ 12 agency staff"), "ending soon"
  on the quiet board, vendor drawer lists their people. Never in a pay run by construction, never in
  payroll counts. Non-goals: time clock / timesheets for them (leave & time team), agency invoices,
  bill rates. Payslip risk: none.
- Files: new module `pb_agency_staff` (depends `pb_vendor_access`, `pb_people_hub`, `pb_filter_kit`);
  vendor drawer addition by patch. Edits no existing file.

---

## 9. Proposed split: three builders at the same time

All three are new modules; **no phase edits a file another phase edits**. Version-bump only modules whose
files change; new modules install with `-i` on all five DBs (D4; tenant sync rule). The deploy agent
checks first that `pb_hiring`, `pb_vendor_access`, `pb_decision_room`, `pb_orgchart` are installed on
`p0clone` and `sudima` (a glue module depending on them would force-install them).

### S8-A "Pay structure" — pay scales (blueprint P1 + joiner defaults) and build-from-a-total

- Owns: NEW `pb_pay_scales`, NEW `pb_pay_package`.
- Edits existing: `pb_pay/static/src/js/pay_hub.js` (`tabDefs` `:140-148`, add "Scales" tab — or a
  registry seam added once), `pb_pay/__manifest__.py` (version), `pb_contracts/static/src/xml/contract_360.xml`
  + `contract_360.js` (scale chip, "Build from a total" link beside the W2-C link), `pb_contracts/__manifest__.py`.
- Inherits (no edit): `pb.people.contract.wizard.create_contract`, `pb_hiring` `_ensure_contract`, Updates
  joiners, `pb.pay.band.job`, `pb_employee_360_chips`, `take_home_solver`.
- ⌘K 3460–3490 (scales) and 4420–4450 (package). Tier: risky (writes wage on create; new modules).
- Non-goals: wage floors (Step 1, D2), revisions/arrears/step-ups (blueprint P3–P4), portal page, offers.

### S8-B "A person's working life" — Change job, fixed-term rules, agency staff

- Owns: NEW `pb_job_change`, NEW `pb_contract_rules`, NEW `pb_agency_staff`.
- Edits existing: none planned. Header button in the employee panel and the org-chart card button by
  `t-inherit` + `patch()`; contract decisions chip by `t-inherit`.
- Inherits: `pb.pay.apply` (+ `job_change_id`), `pb.letter.template.letter_type` (`selection_add`),
  `pb.contract.review` (`decision_preview`, `action_request_extension`, `_build_new_contract`),
  `pb.records.desk._master_fields`.
- ⌘K 4460–4469 (change job), 4470–4490 (agency staff). People lens seq 59 (agency staff). Tier: risky
  (wage, pay lines, team → scheme).
- Must report, not fix: renewal drops pay lines (§5); pay change writes job to contract only and undo
  keeps the job (§2).

### S8-C "Organisation" — job page + levels, cost centres, hiring pause, would-rehire, plan → hiring requests

- Owns: NEW `pb_org_structure` (levels, job page, cost centres, hiring pause, rehire), NEW `pb_plan_hiring`.
- Edits existing: none planned (all `_inherit` / `t-inherit` / `patch()` of `pb_hiring`, `pb_orgchart`,
  `pb_offboarding`, `pb_decision_room`).
- Inherits: `pb.hiring` `_act_create`, `pb.hiring.requisition` (`_request_send_in`, `_open_for_candidates`,
  route facts `_chain_facts`), `pb.orgchart._do_add_open_role`, `pb.exits.get_exit`, `hr.applicant.create`,
  `pb.records.desk._master_fields` (cost centre in Updates), `hr.job`, `hr.department`, `hr.contract`.
- ⌘K 4500–4560. People lens seq 58 (Jobs). Tier: normal for `pb_plan_hiring`; risky for `pb_org_structure`
  only if it writes `costcenter` in bulk (payslip-line history, §6.1).
- Non-goal: Explorer cost-centre dimension (pb_explorer, other team).

### Shared seams inside S8 (no shared FILE, but two modules override the same thing)

| Seam | Phases | Rule |
|---|---|---|
| `pb.records.desk._master_fields` | B (earlier fixed-term count), C (cost centre) | each override calls `super()` and only adds its own field |
| `pb.contract.review._build_new_contract` | B (counter, maybe pay-line carry) | C must NOT override it: the cost-centre Char mirror is already carried (`CARRIED_FIELDS`) |
| Org chart JS (person card / team panel) | B (Change job button), C (pause hiring) | separate `patch()` per module, no edits to `pb_orgchart/static` |
| Employee panel header | B only (Change job); A uses the chip registry | — |
| `hr.contract` new fields | A (scale state), C (cost centre) | different field names; both precommit-safe (GR44) |
| `pb.pay.apply` | B (`job_change_id`) | A adds no field to it in S8 |

---

## 10. Collision list with the other parallel steps

| Other step | Their area | Files / seams S8 would touch there | Plan |
|---|---|---|---|
| Leave & time rules | `pb_timeoff`, `pb_clock`, `pb_schedule`, `pb_attendance_flow`, `pb_time_hub`, `hr_holidays*`, `pb_timesheet_approval` | **None.** Change job writes `resource_calendar_id` (employee + contract) — a value their shift rules read, no file. Agency staff deliberately get no clock-in. | Tell them a schedule can now change on a dated job change. |
| Self-service on `/my` | `pb_me_portal`, `pb_me_team`, `pb_ess_workforce`, `pb_me_expense`, `pb_me_trip`, internal job applications (→ **`pb_hiring`**: careers/roles, applicant create) | S8-C inherits `pb_hiring` (`pb_hiring.py` `_act_create`, `requests_p3.py`, `requisition.py`, `forms_p2.py` applicant create, `hiring_board.js` candidate drawer + roles tab, careers listing). S8-A inherits `offer_closure.py` `_ensure_contract`. No `/my` file touched (manager "propose a change" and "your pay on the scale" are non-goals). | **Real overlap: `pb_hiring`.** Both teams work by inheritance from new modules; neither edits `pb_hiring` source; internal-applications list must hide paused roles (S8-C exposes `hr.job.pb_hiring_paused` / role state "On hold" for them to read). Agree the role-state `selection_add` value name once. |
| Performance, surveys, people reports | `pb_lifecycle`, `pb_goals`, `pb_pip`, growth, `pb_explorer`, `pb_insights` | `pb_lifecycle/models/lifecycle_common.py` `LETTER_TYPES` — S8-B adds letter types by `selection_add` (no edit). `pb_lifecycle/models/feedback.py` exit answers — read only. **`pb_explorer/models/pb_explorer.py` `_DIMENSIONS`/`_FILTERS` and `pb_fact_builder.py`** — a cost-centre (and job-level) dimension needs edits there. `pb_insights.py:547` headcount — untouched (agency staff are a separate record). `pb_offboarding` exits board (`exits_board.xml`, `pb_exits.py`) — S8-C patches it for the rehire question. | Give the Explorer cost-centre/job-level dimension to the reports team as a follow-up reading `pb_cost_centre_id` / `hr.job.pb_level_id`. Check whether the surveys team touches the exits board; if so, S8-C's patch must target a different template node. |

---

## 11. Owner questions (plain words; recommended option first)

**Q1. Approving a job change.** When someone is promoted, moved to another team or given new pay in one
go, who signs it off?
- (a) **One sign-off for the whole change** on its own route: their manager, then HR, then Finance only
  when the pay rise is above the guidance — and you can change the route in the Approval Matrix like any
  other. *(recommended — one request in the inbox, one letter, one undo)*
- (b) Keep today's separate sign-offs: the pay part goes through the pay-change route and the job/team
  part through the employee-records route. Nothing new to set up, but one change becomes two requests
  that can be decided differently.
- (c) No sign-off for job and team, sign-off only when pay changes.

**Q2. A job change that starts on a date already paid.** Payobook today never adds back pay for a wage
change dated in the past. What should the new "Change job" do?
- (a) **Allow it, work out the difference and put it on the next pay run as a back-pay line you check
  before it is paid.** Tax and insurance on it follow that month's rules. *(recommended)*
- (b) Allow past dates for job and team only; a pay change must start today or later.
- (c) Allow it and only record the date; HR adds any back pay by hand (today's behaviour).

**Q3. Too many fixed-term contracts in a row (Vietnam, Indonesia).** When extending would break the
limit (Vietnam: a third fixed-term contract; Indonesia: more than five years), what should the screen do?
- (a) **Warn in red on the decision and the extension request, and ask for a reason before it can be
  sent; "Make it permanent" is offered beside it.** *(recommended — same "warn and record" habit as the
  rest of approvals)*
- (b) Stop the extension; only "Make it permanent" or "Let it end" remain.
- (c) A quiet note only.
Also: contracts signed before Payobook are not on the system. Recommended: HR types the number of
earlier fixed-term contracts once per person (or by an Updates sheet); otherwise Payobook counts only
the ones it holds and may under-count.

**Q4. Pay scales (designed in September, ten choices still open).** May we start building with the
defaults in the design: people already paid above their new step keep their pay; a scale change needs
HR then Finance sign-off before anyone's pay moves; steps are optional; a grade can also fill its
allowances; new joiners start on step 1 unless the recruiter types another amount?
- (a) **Yes, build the scale table, the "On scale / Pinned / Drifted" mark and new joiners starting on
  the scale now; legal minimum wages wait for the postponed country-numbers step; raising a whole scale
  comes next.** *(recommended)*
- (b) Yes, and include the minimum-wage table now (this brings country figures forward that you
  postponed).
- (c) Grades only, no steps (simpler screen; no automatic step-ups later).
- (d) Not yet.

**Q5. Agency staff who are not on our payroll.** How should they appear?
- (a) **As their own light record (name, agency, team, manager, dates, papers) with their own list under
  People, shown as "+ 12 agency staff" beside the headcount — never in a pay run, never in pay counts,
  no clock-in for now.** *(recommended — no risk of a payslip being made for them)*
- (b) As ordinary employee records marked "not on our payroll": they can use the time clock and appear in
  People, but every pay screen must learn to skip them, and a mistake would make a payslip.
- (c) Only as a list on the agency's page in Vendors.

**Q6. Pausing hiring for a team or a role.** What does "Pause hiring" stop?
- (a) **New hiring requests and adverts for that team or role; candidates already in progress carry on,
  and sending an offer shows a warning with the reason.** *(recommended)*
- (b) Everything, including offers already being prepared.
- (c) Nothing is stopped; it is a warning banner only.

Builder defaults taken without asking (reversible, reported in each phase report): approved plan lines
become DRAFT hiring requests (they appear on the org chart once opened); cost centre is set per team
and can be changed per person; "would rehire" is HR-only; job levels are a named list set once in
Settings.

---

## 12. Report-back items for every S8 phase

1. Each LOUD risk above: the test that proves it (wage/pay lines untouched before the start date; scheme
   change shown; payslip recompute old vs new on a copy = 0 differences for anybody the phase did not
   change — W2M-4: count refused recomputes).
2. Counts measured on a copy of rize and payobook: renewals whose new contract lost pay lines (§5);
   contracts whose job differs from the employee's job (§1.1); contracts with a typed cost centre.
3. Every new user-visible string in en/vi/id, none containing "Odoo"; no "Payobook" in any `biz_*` file.
4. Browser walk inside the People hub (hub-lens no-scroll trap), console clean.
