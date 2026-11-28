# RIZE P0 — pb_lifecycle: the journey engine + the Lifecycle mission

Read FIRST: `docs/handovers/RIZE_LEDGER.md` (conventions, deploy ritual, gotchas, rulings).
Owner-approved design: `docs/design/rize-hrms-blueprint.html` (this phase = its "step 1").

## Scope

ONE new module `pb_lifecycle` plus the minimal edits to `pb_sidebar` it requires. Deliver:

1. The **journey engine** models (template/case/task, check-ins, feedback requests, letters,
   reminder cron) that P3–P10 will build on.
2. The new **Lifecycle rail mission** + **Lifecycle hub** with one real lens (**Journeys**
  cockpit) and a soft registry so later phases add lenses without touching this module.
3. A **login-less token page** for journey tasks (candidates confirm things before day one)
   and for feedback forms.
4. The **HR letter engine** (templates → generated PDF letters, filed into the employee vault).
5. Template **admin screens** (native views) + two seeded skeleton templates.

### Binding NON-goals (later phases; do NOT build now)
- No Zoho anything (P1). No asset models (P2). No buddy/HRBP/orientation logic (P3).
- No resignation/clearance models (P4). No probation/PIP records (P5/P6).
- No employee "/my" portal pages beyond the token routes (P3+ adds /my/journey etc).
- No changes to payroll, contracts, F&F.

## Verified plumbing facts (do NOT re-derive)

- Rail spec-as-test: `pb_sidebar/tests/test_ia_c5.py` `TARGET_RAIL` (~line 31) — 5 sections,
  8 items today. Sections declared in `pb_sidebar/data/pb_sidebar_data.xml`; the `operate`
  section is `pb_sidebar.sec_payrun`-style refs — read that file for exact section xmlids.
  Items: model `pb.sidebar.item` (fields at `pb_sidebar/models/pb_sidebar.py:26`), declared
  by the owning module (canonical example with rationale: `pb_home_hub/data/pb_sidebar.xml`).
  Icon map: `pb_sidebar/static/src/js/pb_sidebar.js:16-64` `ICONS` (kebab keys, inline Lucide
  paths; missing icon renders a silent circle and a test fails).
- Hub kit: `pb_hub/static/src/js/hub_shell.js:51` `HubShell`, config contract documented
  ~lines 62-75; `hub_nav.js` `openHub`/`hubBack`; palette contract
  `pb_hub/static/src/js/hub_palette_entries.js`. Canonical hub: `pb_home_hub`
  (`__manifest__.py` asset order, `views/pb_home_hub_action.xml` action RECORD,
  `static/src/js/home_hub.js` config built once in setup, registered at file end).
- Soft-registry lens pattern: `pb_records/static/src/js/records_palette.js` (registers a
  People-hub lens + ⌘K rows) consumed by `pb_people_hub/static/src/js/people_hub.js`
  (`extraLenses()`); copy the mechanism, with our own category name `pb_lifecycle_lenses`.
- Cockpit anatomy canon: `pb_people` — facade `pb_people/models/pb_people.py:32`
  (AbstractModel, `_safe()` at :35, `env.companies` scoping :49, row cap :15), action XML
  `pb_people/views/pb_people_action.xml`, OWL `static/src/js/people.js`, template root
  `pbim ... pbim-page` branching on `props.embedded` (`static/src/xml/people.xml:5,14`).
- Kit primitives: `pb_import_kit/static/src/scss/import_kit.scss` (`.pbim-page .pbim-hero
  .pbim-stat(s) .pbim-card .pbim-panel .pbim-table .pbim-chip(s) .pbim-badge .pbim-btn
  .pbim-seg .pbim-busy .pbim-empty .pbim-h1/.pbim-h2/.pbim-sub`); icons via
  `import_icons.js` `ic(name, size)` — ONE registry, add missing Lucide paths there.
- Reminder-cron canon: `pb_employee_vault/models/employee_document.py:227-268`
  `_cron_expiry_check` — idempotent (`mail.activity` search before create), config-param
  horizon, per-record try/except, responsible resolved by group with admin fallback.
  Cron record: `pb_employee_vault/data/ir_cron_expiry.xml`.
- Token-route canon: `pb_ess_workforce/controllers/ack.py:80,88` — `auth='public'` routes
  `/work/ack/<token>[/confirm]`, sudo reads scoped by token, no ACL for the model; security
  rationale documented in `pb_ess_workforce/security/pb_ess_workforce_security.xml:4-25`.
  Frontend-only assets: `pb_me_portal/__manifest__.py:47-53` shows the boundary.
- Bilingual QWeb PDF canon: `pb_hr_fullandfinal/report/full_and_final_report.xml`
  (explicit `ir.actions.report` record — remember the `<report>` shortcut tag is DEAD).
- Vault filing: `pb.employee.document` model + categories in
  `pb_employee_vault/data/document_category_data.xml` (LABOR/ID/CERT/HEALTH/PERMIT/OTHER).
- mail.template canon: `pb_pay_delivery/data/mail_template.xml` (noupdate=1, `{{ }}` fields).
- Group-ladder canon: `pb_hr_workforce_planning/security/` (user/manager/admin with
  `implied_ids`; NO `category_id` on groups in Odoo 19).
- Company rule string used everywhere:
  `['|',('company_id','=',False),('company_id','in',company_ids)]`.
- `hr.employee` has `parent_id` (manager) and contracts have `hr_responsible_id`;
  HRBP/buddy fields DO NOT exist yet (P3 adds them) — assignee resolution must degrade
  gracefully (fall back to HR group / case owner) when a rule can't resolve.

## Architecture

### Models (all in pb_lifecycle/models/, all with company_id + mail.thread where noted)

**`pb.journey.template`** — name, case_type Selection
`[('onboarding','Onboarding'),('offboarding','Offboarding'),('probation','Probation'),
('pip','Performance improvement'),('conversion','Conversion'),('other','Other')]`,
country_id (res.country, optional = applies everywhere), company_id, active, sequence,
step_ids One2many, note. Unique-ish guard: warn (not block) when two active templates share
case_type+country.

**`pb.journey.template.step`** — template_id, sequence, name, description,
anchor Selection `[('case_open','When the journey opens'),('doj','Joining date'),
('lwd','Last working day'),('probation_end','Probation end')]` default case_open,
offset_days Integer (signed), assignee_rule Selection
`[('hr','HR'),('hrbp','HRBP'),('manager','Manager'),('buddy','Buddy'),('it','IT'),
('finance','Finance'),('admin','Admin'),('employee','The employee'),
('candidate','The joiner (before day one)'),('user','Specific person')]`,
assignee_user_id (res.users, for 'user'), step_kind Selection
`[('task','Task'),('confirmation','Confirmation'),('form','Form'),('email','Automatic email'),
('letter','Letter')]`, blocking_ff Boolean (label: "Blocks final settlement"),
escalation_days Integer default 3, mail_template_id (mail.template, optional),
letter_template_id (pb.letter.template, optional), form_questions_json Text (for 'form').

**`pb.journey.case`** — mail.thread. name computed ("<Employee> — <Type label>"),
employee_id (hr.employee, required, index), case_type (same selection), template_id,
anchor_date Date, state Selection draft/active/on_hold/done/cancelled (tracked),
source Selection `[('manual','Manual'),('zoho','Connected system'),('portal','Portal')]`
default manual, company_id (default from employee), progress Integer computed
(done+skipped tasks / total, stored), task_ids, checkin_ids, open_task_count computed,
red_flag_count computed, date_opened, date_closed.
Methods: `action_open()` (draft→active: generate tasks from template steps — resolve
assignee + due_date = anchor-resolved date + offset_days; anchor dates: case_open→today,
doj→employee first contract date or anchor_date, lwd/probation_end→anchor_date),
`action_done()`, `action_cancel()`, `action_hold()`/`action_resume()`.
Assignee resolution helper `_resolve_assignee(rule, employee)`: manager→employee.parent_id.user_id;
employee→employee.user_id; candidate→None (token task); hr/it/finance/admin→users of
group_lifecycle_manager (hr) or config-param user ids `pb_lifecycle.<rule>_user_id`;
hrbp/buddy→None fallback to HR until P3 adds the fields (probe with `hasattr`/`_fields` so
P3's fields are picked up WITHOUT editing P0). Unresolved → assign to case creator, log note.

**`pb.journey.task`** — case_id (required, ondelete cascade, index), step_id (optional),
sequence, name, description, assignee_user_id, assignee_rule, due_date, state Selection
`[('pending','To do'),('in_progress','In progress'),('blocked','Blocked'),('done','Done'),
('skipped','Skipped')]` default pending, step_kind, blocking_ff, portal_token Char
(indexed, generated `secrets.token_urlsafe(24)` for candidate/confirmation/form kinds),
form_questions_json, payload_json Text (answers / confirmation details),
done_by (res.users), done_at Datetime, escalation_days, escalated Boolean, note.
Methods: `action_done(payload=None)`, `action_skip(reason)`, `action_block/unblock`.
Employee_id related stored (for own-record rule later).

**`pb.employee.checkin`** — employee_id required index, case_id optional, kind Selection
`[('d30','30-day'),('d60','60-day'),('d90','90-day'),('hrbp','HRBP catch-up'),
('buddy','Buddy connect'),('probation','Probation 1:1'),('pip','PIP check-in'),
('other','Other')]`, owner_user_id (who runs it), scheduled_date, state
scheduled/done/missed/cancelled, notes Text, red_flag Boolean, red_flag_note,
company_id. `action_done(notes, red_flag)`.

**`pb.feedback.request`** — subject_employee_id required, respondent_user_id optional,
respondent_email Char (external/loginless), kind Selection
`[('probation_peer','Probation peer'),('exit','Exit'),('pip','PIP'),('other','Other')]`,
case_id optional, token Char indexed unique-constraint (models.Constraint), window_end Date,
state Selection sent/submitted/expired/extended, questions_json Text
(list of {key,label,type:'text'|'rating'|'choice',options}), answers_json Text,
submitted_at, company_id. `action_send()` (emails the link), `action_extend(days=1)`.

**`pb.letter.template`** — name, letter_type Selection
`[('experience','Experience letter'),('probation_pass','Probation passed'),
('probation_extend','Probation extended'),('probation_fail','Probation not passed'),
('incentive','Incentive letter'),('ff_cover','Final settlement cover'),('pip','PIP letter'),
('custom','Custom')]`, body_html Html (placeholders `${employee_name}`, `${job_title}`,
`${department}`, `${company}`, `${date}`, `${joining_date}`, `${extra}` — document the list
in the form help), vault_category_id (m2o to the vault category model — read its real model
name from pb_employee_vault code), active, company_id.

**`pb.hr.letter`** — mail.thread. employee_id, template_id, letter_type related stored,
subject Char, rendered_html Html, state draft/generated/sent, attachment_id (ir.attachment),
context_json Text (extra placeholder values), generated_at/by, company_id.
`action_generate()`: substitute placeholders (str.Template-style `${}`; NEVER eval),
render through the QWeb report to PDF, attach, and file a `pb.employee.document` in the
vault (category from template, graceful if unset). `action_send()`: mail.template with the
PDF attached (pb_pay_delivery pattern).
QWeb report: generic wrapper (company header, rendered body, signature block) — clone the
F&F report structure; explicit `ir.actions.report` record.

**Reminder cron** (`models/lifecycle_reminders.py` + `data/ir_cron.xml`): one daily cron
`_cron_lifecycle_reminders()` on pb.journey.case (or a util model):
- tasks due within `pb_lifecycle.remind_days` (config param, default 2) or overdue →
  email assignee (one mail.template) + idempotent `mail.activity` (vault pattern);
- overdue past `escalation_days` and not `escalated` → email case company's lifecycle
  managers + mark escalated;
- check-ins scheduled today → email owner;
- feedback requests past window_end → state=expired; those expiring today → reminder email.
Per-record try/except, honest counts logged, config-param master switch
`pb_lifecycle.reminders_enabled` default '1'. NO `numbercall`/`doall` fields.

**ICS helper** (`models/ics.py` or utils): `build_ics(summary, dt_start, dt_end, organizer,
attendees, description)` returning bytes — used from P3 on; unit-testable pure function.

### Controllers (`controllers/token_pages.py`, frontend template in views/)

- `GET /journey/t/<token>` (auth='public', website-less http route): resolves an OPEN
  pb.journey.task by token via sudo; renders a minimal branded page (clone the ack page
  QWeb pattern from pb_ess_workforce `views/ack_templates.xml`): task title, description,
  and per step_kind: confirmation → "Confirm" button (+ optional note/condition fields);
  form → the questions rendered as inputs. POST `/journey/t/<token>/submit` writes
  payload_json + marks done. Invalid/used token → friendly "this link has expired" page.
  NO enumeration: uniform response for unknown tokens.
- `GET /journey/f/<token>` + POST submit — same for pb.feedback.request (writes
  answers_json, state=submitted). After window_end → polite expired page.
- Frontend-only assets (small scss for the two pages in `web.assets_frontend`).

### Cockpit — Journeys (`pb.journeys` facade + OWL)

Facade `models/pb_journeys.py` (AbstractModel `pb.journeys`, clone pb_people shape):
- `get_board()` → {kpis: active cases by type, tasks overdue, red flags open, letters
  generated this month; rows: active+on_hold cases (cap 400): id, employee, type label,
  progress, open tasks, next due date, red_flag_count, state; facets: type, state; can_admin}.
- `get_case(case_id)` → case header + ordered tasks (with assignee names, due, state,
  token indicator) + check-ins + letters for that employee case.
- Actions (all group-checked server-side): `open_case(employee_id, case_type, template_id,
  anchor_date)`, `task_done(task_id)`, `task_skip(task_id, reason)`, `task_reassign(task_id,
  user_id)`, `add_task(case_id, vals)`, `case_action(case_id, verb)`.
- List employees for the open-case dialog via existing hr.employee search (name_search).

OWL cockpit (`static/src/js/journeys.js|xml|scss`, tag `pb_journeys`):
- Hero: title "Journeys", KPI stats row (`.pbim-stats`), primary button "Start a journey"
  (dialog: employee picker, type, template auto-picked by type+country, anchor date).
- Board: case cards/table rows with progress bar, chips for type, red-flag badge; click →
  case drawer/detail pane: vertical task timeline (done/current/upcoming), inline actions
  (done / skip / reassign), check-ins strip, red flags highlighted.
- Empty state that teaches ("No journeys yet — start one, or they open automatically when
  the connected system announces a joiner").
- `props.embedded` branch drops the H1 (hub provides brand).

### Hub + rail + palette

- Hub component `pb_lifecycle_hub` (inside pb_lifecycle module): HubShell, brand
  {label:"Lifecycle", icon}, defaultLens 'journeys', lenses = [{key:'journeys', ...,
  Component: Journeys cockpit, embedded}], PLUS `extraLenses()` reading
  `registry.category("pb_lifecycle_lenses")` (sorted by sequence) so P5/P6/P10 add
  Probation/PIP/Contracts lenses. Action record `ir.actions.client` tag `pb_lifecycle_hub`.
- Rail: `pb_lifecycle/data/pb_sidebar.xml` — ONE `pb.sidebar.item`: label "Lifecycle",
  section = the operate section record (read exact xmlid from `pb_sidebar/data/pb_sidebar_data.xml`),
  sequence 25 (verify free), icon `refresh-cw` (ADD its Lucide path to `ICONS` in
  `pb_sidebar/static/src/js/pb_sidebar.js`), action_tag `pb_lifecycle_hub` +
  action_xmlid of the hub action record, match_action_tags `pb_lifecycle_hub,pb_journeys`.
- Update `TARGET_RAIL` in `pb_sidebar/tests/test_ia_c5.py` (9th item; keep table exact).
- ⌘K: mission entry sequence 190 ("Lifecycle") + deep links 2100+ ("Start a journey",
  "Journey templates", "Letters") via the palette contract.

### Admin screens (native views, VU-skinned automatically)

- `pb.journey.template` list+form (steps as editable list in a notebook page), menu-less;
  reachable via an `ir.actions.act_window` record wired to hub cog / ⌘K deep link, gated
  group_lifecycle_admin.
- `pb.letter.template` list+form (body_html widget). Same gating.
- `pb.hr.letter` list+form readonly-ish for audit.
- Seed data (`data/journey_template_data.xml`, noupdate="1"): "New joiner — standard"
  (case_type onboarding; steps: Laptop request [it, doj -12, task], Tool access [it, doj -5,
  task], Welcome email [hr, doj 0, email], Day-1 intro [manager, doj 0, task], Data
  completion [employee, doj +3, task]) and "Exit — standard" (case_type offboarding; steps:
  Handover plan [manager, lwd -20], IT clearance [it, lwd 0, confirmation, blocking_ff],
  HR clearance [hr, lwd 0, confirmation, blocking_ff], Experience letter [hr, lwd +1,
  letter]). Plus 3 seeded letter templates: experience, probation_pass, incentive
  (professional plain-English body with placeholders).
- Seed mail.templates: task reminder, task escalation, feedback invite, letter delivery.

### Security

- Groups: `group_lifecycle_user` (see own-company cases/tasks read + write on own
  assigned tasks), `group_lifecycle_manager` (implied user; full case/task/checkin/feedback
  CRUD), `group_lifecycle_admin` (implied manager; templates + letters admin).
  Ladder cloned from pb_hr_workforce_planning. Grant admin to the admin user via implied
  chain only (no hardcoding).
- ACLs for every model; global company ir.rule per owning model; feedback/task token models
  have NO public ACL (token routes use scoped sudo).
- Assignee visibility: rule for group_lifecycle_user on pb.journey.task:
  `['|',('assignee_user_id','=',user.id),('case_id.employee_id.user_id','=',user.id)]`
  (managers get the permissive rule).

### Module manifest

depends: `['web','hr','mail','pb_hub','pb_sidebar','pb_import_kit','pb_employee_vault']`
(check each is truly needed; keep minimal but include pb_sidebar since we ship a sidebar
item). Assets: backend scss→js→xml (leaf JS before importer); frontend bundle for token
pages. `application: False`. Version `19.0.1.0.0`. All strings white-labelled.

## Safety rails

- Do NOT touch payroll models, pb_contracts, or any existing module other than the two
  pb_sidebar files named above (data is additive; ICONS + TARGET_RAIL edits are surgical).
- Nothing in this phase sends bulk email to real employees: reminder cron is gated by
  `pb_lifecycle.reminders_enabled` and seeded mail goes only to task assignees you create
  during testing. Use YOUR test records; do not open journeys for real RIZE staff (none
  exist yet anyway).
- The live DB is production for other tenants' template — deploy exactly per ledger ritual;
  install `-i pb_lifecycle -u pb_sidebar` only.

## Numbered test cases (run all; report pass/fail each)

T1. Deploy per ledger ritual; install log EXIT=0, no Traceback/CRITICAL; registry loads.
T2. Login https://payobook.com as ash@biztinct.com. Rail shows "Lifecycle" between People
    and Workforce with the refresh icon (not a blank circle), light + dark screenshot.
T3. `/odoo/action-pb_lifecycle_hub` opens the hub: brand "Lifecycle", Journeys lens active.
T4. "Start a journey" → pick any existing employee, type Onboarding → case opens with the
    5 seeded steps, assignees resolved (manager step → that employee's manager's user or
    fallback), due dates = anchor+offsets.
T5. Mark a task done in the cockpit → progress % updates; skip another with a reason.
T6. A confirmation-kind task's token page: open `/journey/t/<token>` logged OUT (private
    window) → branded page renders; confirm → task done in backend; reopening the link
    shows the friendly used/expired page. Unknown token → same page, no error leak.
T7. Feedback request: create one (any kind) for an employee with 2 questions, send; open
    `/journey/f/<token>` logged out; submit answers → state submitted, answers stored.
T8. Letter: generate an Experience letter for an employee → PDF renders (placeholders
    substituted, no `${` residue), attachment on the letter record AND a vault document
    created; send → mail.mail created with PDF attached.
T9. Reminder cron: call the cron method directly (server action or JSON-RPC as admin) with
    an overdue task present → assignee reminder mail queued + ONE activity (run twice →
    still one activity: idempotent); escalation path marks `escalated`.
T10. Sidebar test suite: run `test_ia_c5.py` with the updated TARGET_RAIL — green. (Run
    odoo tests against a COPY of the template DB on the server, or if infeasible document
    exactly why and show the rail passes by inspection: no duplicate labels/sequences.)
T11. ⌘K: "Lifecycle" mission entry and the 3 deep links appear and navigate.
T12. Grep the module for user-visible "Odoo" strings → zero.
T13. As a NON-admin internal user without lifecycle groups: rail may show the item, but
    the hub's server calls refuse/empty gracefully (no traceback in log).
T14. Dark mode pass on hub + cockpit + token page (Chrome MCP emulate) — screenshots.

## Deliverables / report back

- Commits (explicit staging): (1) pb_lifecycle module, (2) pb_sidebar icon+data+test edit —
  or one commit if you prefer, but staged file-by-file. Message style per ledger.
- Report: per-test pass/fail with one-line evidence, deploy log tail (EXIT line), any
  deviations from this spec and why, new gotchas appended to the ledger's gotcha section,
  and the exact registry category name you used for extra lenses + palette sequences
  (P5/P6/P10 need them).
