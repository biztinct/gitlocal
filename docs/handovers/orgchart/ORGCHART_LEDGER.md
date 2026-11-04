# ORG CHART — conventions and gotcha ledger

Programme opened 2026-11-04. The owner asked for a world-class organisation
chart as a new tab inside the People hub, studied against Workday, Rippling,
ChartHop, HiBob, Lattice, Personio, Deel, Pingboard, Organimi and Lucidchart.
A proof-of-concept exists and is the **visual and behavioural spec**:

    docs/design/org-chart-poc.html  +  docs/design/org-chart-poc/{icons,data,app,actions}.js

Open it in a browser before reading any phase. Every phase builds the product
version of what the POC already shows; the POC's words, layouts, motions and
dialog copy are the target unless a phase says otherwise.

| Phase | What it delivers | Handover |
|---|---|---|
| P1 | **The chart, read-only.** New module `pb_orgchart`; an **Org chart** tab in People right after Employees; one payload RPC; tidy tree with leaf stacks; top-down / sideways / Teams / List; compact; expand/collapse with +N; levels cap; pan/zoom/fit/minimap; search + jump; team/location/employment filters; colour-by; six numbers that focus; person side panel (chain, facts, Team/Peers tabs); Find me; keyboard; spreadsheet export; print. | `ORGCHART_P1.md` |
| P2 | **Changing the chart, live.** Drag onto a new manager (whole team / only them), change manager, dotted-line manager (new field), add team member (existing / open role / new starter door), fill an open role, swap places, remove from team (no-manager lane), close a role, undo, History tab from field tracking. | `ORGCHART_P2.md` |
| P3 | **Planning mode, time machine, suggest a chart.** Draft plan with stacked changes and undo/redo → send for approval through the approval engine → applied on the effective date; past from tracking history; future from approved plans and future starters; suggest-a-chart for a company with no managers set. | `ORGCHART_P3.md` |
| P4 | **Finish.** Picture/PDF export, share deep link, ⌘K rows, lessons, Vietnamese, demo-world check, closeout. | `ORGCHART_P4.md` |

Owner rulings 2026-11-04, asked once, do not re-ask:
1. Workflow: **phased, Fable designs, Opus builds**, same session, back to back.
2. The POC is the spec. Where the product has a better existing primitive
   (filter kit, drawer, approval engine) use it; where it has none, port the
   POC code.

## 0. Binding rules for every phase

Read `docs/handovers/fillin/FILLIN_LEDGER.md` §0 (which chains to
`SCHEMECTX_LEDGER.md` §0). Those rules bind here **verbatim**. In short, and
with this programme's additions:

1. **Plain English on screen, never "Odoo"** in any user-visible string
   (labels, help, errors, chips, tooltips, `.po` msgstr, manifest summary).
   Technical names stay in code, comments, commits and these docs.
2. **Design bar is binding** (owner's words): *"extreme WOW, intuitive,
   out-of-this-world experience, best in class."* Name the hero moment, design
   every state (empty, loading, error, partial, huge), plain language on every
   label and toast, motion with purpose, keyboard + bulk ergonomics, measured
   against the best SaaS tool in the category. Lucide icons through the shared
   `ic()` registry (`@pb_import_kit/js/import_icons`), **never emoji**, never a
   module-local icon map. Grey at zero, colour only when there is something to
   do. Each phase report scores itself against this bar.
3. **Browser validation is mandatory** for every screen change: open it on
   `rize.payobook.com` (validation tenant) AND `payobook.com` (demo world)
   with Chrome MCP, click every control the phase added, read the console,
   screenshot. No login is written anywhere; if no session is open, say so.
4. **Deploy set is FOUR databases and no other**: `payobook`,
   `payobook_template`, `p0clone`, `rize`. **Never `abm`.** One addons
   directory `/odoo/odoo-server/addons`. Use `/odoo/ops/filter_deploy.sh`
   (`full` for Python/XML/manifest/security, `looks` for JS/SCSS/XML-template
   only), staged from committed HEAD, staging dir cleaned first, launched
   detached with `systemd-run`, result polled. Write START/DONE in
   `/opt/deploy-notes.md` (read it first). Announce to other live sessions
   (`ListAgents` → `SendMessage`) before starting. Report the deploy in the
   FILLIN_P2_REPORT §3 table format (commit, module → version, window, EXIT
   per DB, jobs before/after, evidence path).
5. **Tests**: Python unit tests in `pb_orgchart/tests/`; run with the
   SCHEMECTX §0.13 recipe (alternate ports, scoped `-u`, never `--test-tags`
   without `-u`). Report each numbered case with evidence.
6. **Commit per feature** on branch `19.1`, scan the diff for secrets, push.
   Commit message ends with the attribution line given in the session.
7. **A read RPC never writes.** Every write RPC checks the right server-side
   and answers `{'error': 'plain sentence'}` rather than raising
   (`pb.people.bulk_apply` style, `pb_people/models/pb_people.py:467-481`).
8. **Translations**: every new user-visible string gets a `vi_VN.po` entry
   with ALL THREE of `#. module: pb_orgchart`, `#. odoo-javascript` /
   `#. odoo-python`, and a `#: code:addons/pb_orgchart/<path>:0` occurrence
   (markers AFTER the module line). If you ship a `.pot`, every msgid must be
   in it too or the `.po` entry is dropped in silence. Run the PO parse gate
   on the box before deploying (`PoFileReader` over the module's i18n).
9. **Never block the page on one bad record.** The payload builder wraps each
   person in try/except and logs at DEBUG (`pb.people` `_roster_rows` style).
10. **Lessons follow screen changes**: P4 adds the lesson; P1–P3 note in their
    report which Learn lessons/tours mention People tabs so P4 can update them.

## 1. Verified facts — do NOT re-derive

### The People hub and its lenses
* Lens registry `PEOPLE_LENSES = "pb_people_hub_lens"`
  (`pb_people_hub/static/src/js/people_hub.js:102`); entries are read ONCE in
  `extraLenses()` `:162-169` and spread between Employees and Insights
  `:117-143`. Lens def shape (shell contract, `pb_hub/static/src/js/hub_shell.js:73-109`):
  `{ key, icon, label, title?, groups?, probe?, feature?, Component, props?,
  wantsArrival?, pinned?, under? }`. The shell hands a lens
  `{ embedded: true, ...def.props }` (`hub_shell.js:518-525`), never the
  action.
* **Precedents to clone**: `pb_workseg/static/src/js/workseg_lens.js` (a lens
  registration, sequence 48) and `pb_offboarding/static/src/js/exits_palette.js`
  (lens + ⌘K rows). Sequences in use: Records 40, Pay 45, Where 48,
  lifecycle boards 52–58. **Org chart takes sequence 30** — right after
  Employees, before Records.
* The hub's gate mirror for lessons (`people_hub.js:211-216`) already spreads
  the registry, so a registered lens needs nothing there.
* Read gate = `EMPLOYEE_GATE` exported from `people_hub.js:67-72`
  (`pb_records.group_records_viewer`, `base.group_system`, `hr.group_hr_user`,
  `pb_demo.group_payobook_demo`). Import it; do not restate it.
* Write gate (P2+): `hr.group_hr_user` or `base.group_system`, checked on the
  server in every write RPC. Precedent for a server-side "may write" judge:
  `pb_contracts/models/pb_contract_360.py:245-260` (`_cd_may_write`).
* A lens page root is `<div class="pbim pbim-page <mod>">` with
  `.pbim-busy` / `.pbim-spin` while loading
  (`pb_workseg/static/src/xml/workseg.xml:27-30`,
  `pb_offboarding/static/src/xml/exits_board.xml:17-21`). Tokens are the
  `--pbim-*` variables from `pb_import_kit/static/src/scss/`; the POC's hex
  values map onto them (primary `#5A4BB0` = `--pbim-primary`).
* The Employees cockpit is the component precedent:
  `pb_people/static/src/js/people.js` (`orm.call` on an AbstractModel facade,
  `notification` service, soft registry for the drawer `:63-71`).
* **Employee drawer**: `registry.category("pb_people_drawer").get("employee_360")`
  when `pb_employee_vault` is installed; props `{ empId, onClose }`
  (`pb_employee_vault/static/src/js/employee_360.js:24-27`). Absent → fall
  back to `pb_employee_detail` client action as `people.js` does. The org
  chart's "Open employee record" uses exactly this.
* Deep links into a hub lens: `openHub(actionService, { xmlid:
  "pb_people_hub.action_pb_people_hub", lens: "orgchart" })` from
  `@pb_hub/js/hub_nav` (`people_hub.js:184-186`). ⌘K rows go in
  `registry.category("pb_hub_palette")` with `{ id, label, sublabel, icon,
  groups, requires: "<client action tag>", action: { xmlid, lens } }`;
  pick the next free 2xxx block ≥ 2600 after grepping every `*_palette.js`
  (the seed file auto-numbers; count, do not trust comments).

### The employee record (Odoo 19 `hr`, vendored at repo root = the server's standard set)
* `hr.employee` `_inherits = {'hr.version': 'version_id'}`
  (`hr/models/hr_employee.py:43`) — `job_title` and `job_id` live on the
  version (`hr/models/hr_version.py:119-120`) and read/write through the
  employee transparently.
* `parent_id` Many2one `hr.employee` **tracking=True**, index
  (`hr_employee.py:191`); `child_ids` One2many `:193`.
  Tracking means every manager change lands in `mail.tracking.value`
  (field `parent_id`, `old_value_integer`/`new_value_integer`, with the
  `mail.message` date and author) — that is the History tab (P2) and the time
  machine's past (P3). Nothing else records it.
* `coach_id` `:194-199` is `compute='_compute_coach', store=True, readonly=False`
  and **auto-follows the manager**: when `parent_id` changes and the coach was
  the old manager or empty, coach becomes the new manager (`:794-800`).
  **Therefore `coach_id` is NOT the dotted line.** Decision D2 below.
* Useful fields: `department_id`, `company_id`, `active`, `work_location_id`,
  `address_id`, `user_id`, `first_contract_date`, `contract_ids`. Best-known
  join date helper: `pb_people/models/pb_people.py:23-32` (`_join_date`);
  initials `:18-20`. Employment type: use `employee_type` if
  `'employee_type' in Emp._fields` else the version's `contract_type_id.name`
  — verify with a grep in the phase, guard with `_fields` the way
  `_pay_symbol` does (`pb_people.py:59`).
* Stock `hr_org_chart` (vendored at repo root) adds `_get_subordinates`,
  `child_all_count` etc. on `hr.employee` — **we do not depend on it** (one
  pass over `parent_id` in our facade is cheaper and works where it is not
  installed). Check per DB whether it is installed only to report it.
* Open roles: `hr.job.no_of_recruitment` ("Target", `hr/models/hr_job.py:21`,
  CHECK ≥ 0 `:46`), `department_id`, `expected_employees`. An hr.job has no
  manager; D3 below.
* Demo worlds already have a tree: `pb_demo/models/demo_employees.py:192`
  (random manager among managers) and `pb_demo_seed/seeds/people.py:420-421`
  (`parent_id` + `coach_id`). rize: verify on the box how many active
  employees have `parent_id` set (report it; the "no manager yet" lane shows
  the rest).
* "Me": `self.env.user.employee_id` (may be empty — the Find-me button hides).

### Approval engine (P3)
* Chain shim `biz_approval_workflow/models/chain_shim.py`:
  `register_chain(model_name, process_key, submit_state, driven, date_field)`
  `:63`, `manager_step :105`, `role_step :112`, `route :128`; model mixin
  `biz.approval.chain.mixin`.
* **Precedent to clone**: `pb_contract_lifecycle/models/contract_extension.py:47-60`
  (model with `mail.thread`, `mail.activity.mixin`, the chain mixin,
  `_approval_transitions`) + `contract_extension_approval.py` (`_chain_title`,
  `_chain_facts`, `_chain_fact_specs`, `_approval_manager_uids`,
  `_chain_revision_values`, `_approval_detail`, `_approval_seed_default`,
  `seed_all`) + `action_submit :141`.

### Design system and kit
* `ic(name)` names available today (`pb_import_kit/static/src/js/import_icons.js`):
  users, user, userPlus, userX, userCheck, briefcase, building, mapPin,
  search, filter, sliders, layers, layoutGrid, layoutList, columns, list,
  table, gitBranch, workflow, route, maximize, printer, download, upload,
  link, fileSpreadsheet, history, calendar, calendarClock, clock, star,
  plane, triangleAlert, alert, info, lock, eye, eyeOff, pencil, trash, plus,
  minus, x, check, checkCircle, chevronDown/Up/Left, arrowUp/Down/Right/Left,
  arrowLeftRight, moveRight, undo, send, sparkles, target, circleDot, hash,
  tag, flag, grip, copy, externalLink. If a POC icon is missing (e.g. a
  "move" cross, "zoom in/out", "collapse", "dotted"), **add the Lucide path to
  the kit's shared map** (one commit, kit version bump) — never a local map.
* The POC CSS is the look. Port it into `pb_orgchart/static/src/scss/orgchart.scss`
  under `.pbim.pboc` with pbim tokens; keep the card, edge, lane, stack,
  minimap, tools and hint styling as drawn.
* Wheel/pan inside the hub: the hub page scrolls, so the canvas must
  `preventDefault` wheel events over itself (POC `app.js` pan block) and set
  `touch-action: none`.

## 2. Design decisions (binding)

**D1 — one module, `pb_orgchart`.** Depends on `pb_people_hub` (lens host),
`pb_people` (helpers, drawer registry name), `hr`, `mail`. Soft on
`pb_employee_vault` (drawer) and `pb_hiring` (never imported). Version
`19.0.1.0.0` at P1; bump the minor per phase.

**D2 — dotted line = new field** `hr.employee.pb_dotted_manager_id`
(Many2one `hr.employee`, tracking=True, string "Also reports to", help in
plain English). `coach_id` is left alone. Added in P2 with its migration-free
field add (a Many2one with no data needs no migration).

**D3 — an open role is an `hr.job` with `no_of_recruitment > 0`**, hung
under a manager through a new field `hr.job.pb_manager_id` (Many2one
`hr.employee`, "Reports to on the org chart"). Fallback when empty: the job's
`department_id.manager_id`; when that is empty too, the role sits in the
"no manager yet" lane. One card per job; the card shows "× N" when
`no_of_recruitment > 1`. Filling a role (P2) writes the person's `job_id`,
`job_title`, `parent_id` and decrements `no_of_recruitment`.

**D4 — one payload, computed client-side.** `pb.orgchart.get_chart()` returns
every active employee of the allowed companies in ONE call (people, open
roles, departments with colours, locations, `me`, `may_write`, counts).
Layout, KPIs, filters, search and views are client-side exactly as the POC.
Above 1,500 people the payload returns `truncated: true` and only the top
three levels; `get_branch(manager_id)` loads a branch when its +N is pressed.

**D5 — writes are explicit RPCs with a plain-English result**, never a
generic `write`. P2 lists them. Every write answers
`{'ok': True, 'label': 'Bình now reports to Giang', 'undo': {...}}` so the
client can offer one-step Undo without knowing the model.

**D6 — history is field tracking.** The History tab reads
`mail.tracking.value` rows for `parent_id` and `pb_dotted_manager_id` on the
employee; the move RPC posts nothing extra (tracking posts the message). The
time machine's past (P3) replays the same rows backwards.

**D7 — planning mode is a model, not a client trick** (P3):
`pb.orgchart.plan` + `pb.orgchart.plan.change`, approval chain key `orgplan`
(route: HR lifecycle/people team; seeded like contract extensions), applied
by a daily cron on/after `effective_date` once approved.

**D8 — no pay on the chart.** The POC's "Pay band · managers only" row is
dropped; a closeout item records the question for the owner.

**D9 — share link = a deep link into the app** (login required). A public
read-only page needs a public controller and a privacy decision; it goes in
the closeout as an owner question, not into a phase.

## 3. Gotchas hit (append as they come)

* G1 (POC): a `<button>` cannot contain a menu with buttons — the HTML parser
  closes the outer button. Wrap the trigger and its menu in a
  `position:relative` span. OWL templates have the same constraint.
* G2 (POC): HTML5 drag events do not fire under Chrome MCP's synthetic drag
  and never on touch. The POC uses pointer events with a ghost card; port
  that, not `draggable`.
* G3 (POC): a tidy tree with 21 leaves is 5,000 px wide; leaf *stacks* (3+
  leaf reports in one column) keep a 63-person chart at ~3,000 px and a fit
  of 42 % on a small laptop. Never let "fit" go below 0.42 — centre on the
  top instead and let people pan.
* G4 (POC): an edit inside a dialog must not `stopPropagation` when the page
  uses one delegated click handler; give the dialog body a no-op action
  instead. (OWL: use `t-on-click` handlers, this is moot — noted for the port.)
