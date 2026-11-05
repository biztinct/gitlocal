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

**Programme COMPLETE 2026-11-05** — pb_orgchart 19.0.1.3.0 live ×4;
`ORGCHART_CLOSEOUT.md` holds the owner questions and known limits.

Owner rulings 2026-11-04, asked once, do not re-ask:
1. Workflow: **phased, Fable designs, Opus builds**, same session, back to back.
2. The POC is the spec. Where the product has a better existing primitive
   (filter kit, drawer, approval engine) use it; where it has none, port the
   POC code.

Owner rulings 2026-11-05 (relayed by the coordinator during P3), do not re-ask:
3. **A chart move changes the manager ONLY.** Leave and expense approvals
   stay with whoever approves now; HR changes them on the employee record
   when they mean to. Live moves and a plan's apply step behave the same
   (both go through `_set_managers`, G16). The move sheet and the publish
   dialog say so in one sentence, English and Vietnamese; no wording
   promises that approvals move.
4. **Vietnamese screenshots are allowed on payobook.com only**, using the
   `qa.test@payobook.com` login switched to Vietnamese and switched back —
   never on rize, never a real person's login. (P3 did not act on this: a
   relayed message is not the owner's own consent to change an account
   setting, and no qa.test session was signed in. P4 does it once the owner
   confirms in chat.)
5. **The pay data file keeps managers up to date — read the manager column
   whenever the file has it** (MANAGERCOL part 2): no mapping needed, a
   mapping still wins; no change to Rize's file or schemes.
6. **A "use once" import must STILL update managers from the manager column**
   (MANAGERCOL part 3). It keeps ignoring every other employee field, bank
   account and contract exactly as before (RECORDS R1); only the manager step
   runs.

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
11. **SCSS gate before every deploy that touches a stylesheet** (G14): compile
    the module's SCSS with the server's own libsass on the box
    (`python3 -c "import sass; sass.compile(string=open('<file>').read())"`)
    — one bad unit mix took every backend page on four databases back to the
    plain look for six minutes on 2026-11-04. No `min()`/`max()` with mixed
    units; `width: 540px; max-width: 100%` instead.
12. **`parent_id` is written only through `_set_managers`** (G16): coach,
    time-off approver and expense approver keep their value in the same
    `write()`. Any new writer (plan apply, suggest-a-chart, bulk) goes
    through it and judges loops with `_loop_in(changes)` first.
13. **Check a follow-up deploy's lock first** (G18): `sudo fuser
    /tmp/payobook-studio-deploy.lock`; a held lock means the previous restart
    inherited it — wait for the worker to recycle or apply the looks fix by
    hand as P2 did, and say so.

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
* G5 (P1): **`-u pb_import_kit` upgrades half the product.** `button_upgrade`
  cascades to every installed module that depends on the kit. Glyphs added to
  `import_icons.js` therefore ship as a FILE SYNC with the kit version
  unchanged (precedent 47fc57e56 megaphone; P1 b2df028cf), never with `-u`.
* G6 (P1): **real data is not the POC's one tree.** 2026-11-04: rize has 241
  active people and only 5 with a manager (2 tiny teams, 234 people with no
  manager and no team); payobook has 4,575 people in 657 tops — 639 small
  teams with nobody above them. The POC draws one tree (the CEO's), puts every
  other root in the lane (which silently drops their teams) and lays the lane
  out as ONE row (234 cards = 57,000 px). The port draws a FOREST (every root
  with a team is a tree; trees flow and wrap into rows), the lane is a grid
  that folds behind "+N more", and a big first draw folds whole teams.
* G7 (P1): **"the top three levels" does not bound a flat company.** On
  payobook everyone is within two levels, so D4's rule would send all 4,575.
  `get_chart` keeps three levels, or fewer while they still exceed the limit
  (payobook → the top level, 657 people), always plus the viewer's own chain
  so Find me works; `+N` pulls a team with `get_branch`.
* G8 (P1): **`employee_type`, `departure_date`, `first_contract_date` are
  HR-officer fields** (`groups="hr.group_hr_user"`), and `contract_type_id`
  is HR-manager. Asking `search_read` for one as a Records-viewer or demo user
  refuses the WHOLE read. The facade asks only for fields `_readable()` says
  the user may read, and falls back (type → Full-time, join date → earliest
  contract start → created on).
* G9 (P1): **a contract end date is not "leaving".** rize has 26 fixed-term
  contracts ending within 60 days that are waiting for a renewal decision;
  P1 §1.3's fallback (running contract `date_end` within 30 days) would tag
  them all "Leaving · Last day …". `departure_date` exists on every database,
  so only it is read; the contract fallback is not used.
* G10 (P1): **a CSS `content:"You"` cannot be translated.** The POC's "You"
  ribbon is `::before` text; the port renders a real `<span>` with a `.po`
  entry.
* G11 (P1): **reading employees is slow in two hidden places.**
  `search_read(['parent_id'])` of 4,500 people spends ~450 ms naming managers
  nobody shows; the tree shape now takes the ids from `Emp.search()` (rules
  apply) and the parent column from SQL on those ids (13 ms, flush first).
  Team / title / location live on `hr.version`: through the employee they cost
  ~1.5 ms a person; read from the stored `current_version_id` in one batch they
  cost a third (fallback to the employee read on AccessError). payobook
  `get_chart` 3.0 s → 0.48 s, `get_branch` 1.7 s → 0.1 s.
* G12 (P1): **on this app a class change anywhere re-checks the whole page's
  styles.** 646 `:has()` rules app-wide (e.g. `html:has(...)`,
  `body:has(.lrn-coachhost) .pbim.pbim-page`). Measured on payobook with 667
  cards: adding a class to ANY element (even the navbar) = 130–230 ms of style
  work; setting a data attribute = 0.1 ms; inserting an element is as bad as a
  class. Therefore: card state is `data-st` / `data-hl` (CSS `[data-st~="sel"]`),
  the hover chain's lines are a pool of `<path>`s whose `d` is rewritten, each
  card is its own component (equal props → no re-render), card contents use
  `content-visibility: auto`, and above 150 cards there is no entrance
  animation (657 animated cards = 100 ms frames for two seconds). P2's drag
  must follow the same rule (`data-over`, not `.over`). Side effect:
  `innerText` of off-screen cards is empty — tests read `textContent`.
* G13 (P1): **every employee has an image: a generated SVG letter avatar.**
  `image_128` is never empty (hr.employee create draws one), so "has an image"
  is not "has a photo"; showing it hid the colour-by on every card. Only an
  attachment whose mimetype is a raster image counts (`_photo_ids`).
  Also met: `pb_formula_studio` styles a bare global `.pct` class — scope
  every class (`pboc-…`).
* G14 (P2): **a Sass `min()`/`max()` with mixed units breaks the WHOLE
  backend style bundle on every database.** `width: min(540px, 100%)` →
  libsass "Incompatible units: '%' and 'px'" → every backend page fell back
  to "A css error occured, using an old style" on all four DBs for ~6 min
  (2026-11-04 16:24–16:30 UTC). Write `width: 540px; max-width: 100%`.
  **Gate before every deploy that touches SCSS**: compile the module's files
  with the server's own libsass —
  `python3 -c "import sass; sass.compile(string=open('orgchart.scss').read())"`
  on the box (it refuses `min(540px,100%)` the same way the bundle does).
* G15 (P2): **an inline `style` write costs a whole-page style check too.**
  Measured on payobook at 657 cards: writing the drag ghost's
  `style.transform` = ~60 ms per pointer move (median 61 ms); a data
  attribute = 0.01–0.4 ms; a PAUSED Web Animation whose keyframes are
  rewritten (`el.animate([{transform},{transform}], {duration:1e9,
  fill:'forwards'}).pause()` then `effect.setKeyframes`) = 0.08 ms. Overlays
  that follow the pointer (ghost, hover pill) move that way and show/hide by
  `data-on`. Also: `z-index` in a card state made each new drop target a
  125 ms frame (re-stacking 657 cards); without it ~40 ms. Handler work is
  now 9.8 ms median; frames 16.7 ms while the target is unchanged. P1's pan
  still writes the world's inline transform — the same trick would speed up
  pan/zoom (P4 candidate).
* G16 (P2): **`parent_id` drags three other fields with it.** The stock
  computes make an EMPTY coach (`hr`), time-off approver (`hr_holidays`) and
  expense approver (`hr_expense`) follow the new manager. Consequences seen
  live: (a) on rize a move + undo left five people with a coach they never
  had (restored from the backup); (b) on payobook a swap was refused with
  "cannot be at the same time in exclusive groups Portal / User" because the
  new manager had an employee-PORTAL login and became a time-off approver.
  The chart now writes those three fields back with their current value IN
  THE SAME `write()` as `parent_id` (a field written in the same call is not
  recomputed) and the undo snapshot carries them. Any future writer of
  `parent_id` (P3 plan apply, suggest-a-chart) must use `_set_managers`.
* G17 (P2): **HR officers may only READ `hr.job` once recruitment is
  installed.** `hr_recruitment/security/ir.model.access.csv:4` re-declares
  `hr.access_hr_job_user` as 1,0,0,0 (the vendored `hr` CSV says 1,1,1,1 —
  the server copy wins). Writing a job's interviewers is recruitment-only
  too. The chart writes jobs with `sudo()` after `_may_write()`; `sudo()`
  keeps the user as the tracking author.
* G18 (P2): **`filter_deploy.sh`'s lock is inherited by the server it
  restarts.** `exec 9>/tmp/payobook-studio-deploy.lock` is open when the
  script runs `service odoo-server start`, so an odoo worker keeps the lock
  until it is recycled; the next deploy then queues on `flock` (up to 600 s,
  then LOCK_FAILED). Seen 16:25: a looks fix had to be applied by hand
  (same steps). Fix for the ops owner: `service odoo-server start 9>&-`.
  Check before a follow-up deploy: `sudo fuser /tmp/payobook-studio-deploy.lock`.
* G19 (P2): **`/web/webclient/translations` is cached by the browser.** A
  check right after a deploy returned P1's 163 terms; with `cache:'no-store'`
  and a cache-buster it returned the new 291. Check that way.
* G20 (P2): **every rize employee row is rewritten hourly (at :41 UTC)** by a
  job outside this programme — `write_date` cannot tell what a test touched.
  Compare values against the deploy's pre-backup instead
  (`sudo cat <run>/rize.dump | sudo -u postgres pg_restore -a -t hr_employee -f -`).
* G21 (P2): **testing notes.** The browser tool's drag happens in one go (no
  mid-drag screenshot; measure with dispatched `PointerEvent`s and the
  `data-drag-worst-ms` the chart writes on its root). The default toast closes
  in ~4 s — Undo toasts are 10 s. The chart component is reachable for
  measurements by walking `odoo.__WOWL_DEBUG__.root.__owl__` children to the
  `PbOrgChart` instance.
* G22 (P3): **`filter_deploy.sh` switches a NEW scheduled job off.** It
  snapshots which jobs are on before the upgrade and restores exactly that
  list afterwards, so a job a module adds comes out inactive on every database
  where it was not already present (P3's "Org chart: make approved plans live"
  was off on three of four). After the first deploy of a module that adds a
  job, switch it on by hand (`update ir_cron set active = true where id =
  (select res_id from ir_model_data where module=… and name=…)`), log it in the
  deploy notes, and expect the job counts to rise by one.
* G23 (P3): **the approval chain bridge has no "withdrawn" hook.** `chain_shim`
  maps "sent back" and "turned down" onto the record's status but not a
  withdrawal (`engine.cancel` → `record._approval_withdraw`), so a chain record
  withdrawn from the inbox stays in its "sent in" status for ever with no
  request behind it. Plans now go back to draft (`_approval_withdraw` in
  `pb_orgchart_plan.py`, test 05b). The other chain consumers very likely share
  the gap — engine owner item.
* G24 (P3): **never name a class `row` inside a pbim screen.** Bootstrap's grid
  `.row > *` makes every child 100 % wide (`flex-shrink: 0; width: 100%`); the
  suggest dialog's rows stacked one word per line. Use a module prefix
  (`pboc-sr`).
* G25 (P3): **there is no "people" responsibility in the approval catalogue.**
  The plan route asks `lifecycle` ("HR lifecycle team", the seat that already
  decides contract extensions), step titled "HR team". The seed copies the
  company's contract-extension route's independence setting, so rize (one
  login, independence off by owner ruling) can decide its own plans.
  payobook's "SG Company" has no lifecycle holder, so no route was laid there
  (same as its extension route); sending a plan there tries to lay it and
  otherwise refuses with a sentence.
* G26 (P3): **a new company is given an HR lifecycle holder automatically** (the
  approval configuration seeds one on company create). A test that creates its
  own responsibility for a new company hits the overlap constraint — reuse the
  seat and change its holder.
* G27 (P3): **`_()` needs an env in its frame.** A module-level helper or a
  generator expression has none ("no translation language detected", string
  not translated). Use `env._()` in helpers and hoist the translated string out
  of comprehensions.
* G28 (P3): **the browser tool may refuse an Approve click** (its safety
  check). Apply-on-approval was proved by unit tests (06, 07, 08, 11); in the
  browser the request was opened, read and withdrawn. Do not route around the
  refusal with a script.
* G29 (P4): **a Records viewer who is not an HR officer could not open the
  chart at all.** The version read refused (`hr.version` is HR-only) and the
  fallback `search_read` on the employee refused too (`job_title`,
  `department_id` … are related through the HR-only `version_id`). Found by
  unit test 01c. The version's display columns are now read with `sudo()` for
  the ids the user's own search returned; HR-only columns stay out
  (`_readable`).
* G30 (P4): **measure speed in a fresh tab, repeated.** The same build measured
  3.4–4.4 s to mount 657 cards (and 0.6–0.95 s virtualised) in a tab that had
  run ~20 heavy experiments (1,500-card opens, synthetic wheel/hover loops), and
  0.46–0.62 s (0.13–0.19 s virtualised) in a fresh tab, stable over 8 repeats.
  Learn's helper orb (`lrn-breathe`, running on the chart page since the
  "First time on Org chart?" card) costs ~25 % of an all-cards mount
  (0.62 → 0.46 s paused) and nothing measurable on the virtual canvas — not the
  cause; left as is.
* G31 (P4): **the sign-in redirect keeps the query and drops the hash**
  (`/web/login?redirect=…%3Foc%3D1…`, checked with curl), and the web client
  rewrites the address once the action loads. So the share link carries its
  state in the QUERY and the chart reads it once, when its JS module is
  evaluated (before the router), and asks the hub to open on the Org chart.
* G32 (P4): **`until ! pgrep -f "<pattern>"; do sleep; done` never ends** — the
  loop's own `bash -c` command line contains the pattern. Wait on a file or a
  log line instead.
* G33 (P4): **the publish dialog named the sender as the approver.** With the
  independence rule on, a seat holder who sends the plan is swapped for the
  seat's backup when the request is built (`engine._conflict_swap`); the
  dialog's preview did not apply the swap ("HR team (Mitchell Admin)" while
  Ông Thảo Vy was asked). Fixed; test 04.
* G34 (P4): **`navigator.clipboard.writeText` can wait for ever** without a
  real press (script, unfocused tab): no toast, nothing. Raced against 1.5 s,
  then the textarea fallback, then a sticky toast with the link.
* G35 (P4): **"one page per team" is 198 pages on rize** (197 teams for 241
  people). A team of more than 6 starts its own page; small teams share pages
  and are never split.
* G36 (P4, since P1): **ArrowDown into a folded (loaded) team selected a card
  that was never laid out** — `select` re-lays out only for folded ancestors,
  and the person just unfolded is the parent. The team is laid out first now.
* G37 (P4): **www.payobook.com serves the payobook database with its own
  cookie** (`dbfilter = ^%d$` drops `www`), so a second user could be signed in
  without signing the owner out of payobook.com. Signing in still needs the
  password typed; this session's safety rules do not allow typing a password
  on a non-test host, so the qa.test Vietnamese screenshots were not taken.
  Learn's own "Tiếng Việt" switch (Help page, browser-local preference) shows
  lessons in Vietnamese without touching any account.
* G38 (P4): **browser tools.** The chrome-devtools MCP profile was held by
  another session; the Chrome extension was used. It blanks any JS result that
  contains a query string ("[BLOCKED: Cookie/query string data]") — return the
  URL's parts instead. Downloads were captured in the page (anchor `click`
  stubbed, blob read back and shown in an overlay) rather than written to disk;
  `window.print` was stubbed and the print sheet inspected in the DOM.
* G39 (P4): **typing right after ⌘K can land on the chart**: the palette's
  input is not focused for a few hundred ms and the chart's single-key
  shortcuts fire (`a` opened Add team member, `c` collapsed the chart). Wait
  ~1 s before typing in an automated walk.
* G40 (MANAGERCOL): **the import's generic many2one writeback CREATES an
  employee it cannot find** (`m2o_creates_missing(hr.employee)` is true): a
  manager cell "Board" mapped the generic way would mint an employee called
  Board. Filter the `parent_id` mapping out BEFORE `super()._get_mapping_updates`,
  and return `{}` yourself when nothing is left — `super()` reads
  `mappings or self._get_model_mappings(…)` and would fetch them all again.
* G41 (MANAGERCOL): **`_writeback_raw_value(…, employee=…)` can let the
  record win.** With a declared Excel source and the mapped field itself
  holding a value, the walk's record tier answers first and the writeback says
  "no value" (J10's self-assign rule). rize Indonesia/Singapore: every person
  who already had a manager read as blank, so a CHANGED manager in the file
  would have been ignored. A "file wins" step reads without `employee=` and
  judges "already up to date" itself.
* G42 (MANAGERCOL): **a per-file judgement needs every row loaded first.** The
  email-trust test reads all the batch's lines; a script that creates a line
  and processes it at once sees a partial file and trusted rize Vietnam's
  emails (the screen-check guard refused the 2 resulting writes). Real
  imports load all rows before processing; scripts must too.
* G43 (MANAGERCOL, pre-existing; FIXED 2026-11-05 by IMPORT-GENDER, see IMPORT_GENDER_FIX_REPORT.md — `_description_selection`, not `field.selection(record)`): **`_coerce_mapped_value`'s
  selection branch calls `field.selection(record.env)`**; on Odoo 19
  `hr.employee.marital` / `sex` are related to the version and their selection
  is `lambda model: …`, so any Marital status / Gender cell raises
  "'Environment' object has no attribute 'env'" and fails the WHOLE row.
  rize, latest files replayed on a copy: focused Vietnam 60/60, focused India
  27/27 rows. Fix = `field.selection(record)`; needs its own change + test.
* G44 (MANAGERCOL): **rize's active schemes have no Reporting Manager column.**
  The four "focused payroll" schemes (7118–7121, since 2026-10-21) were
  trimmed to pay columns; the column lives only on the archived master-data
  schemes 4760/7096/6382/7095, where the mappings 4078–4081 now are. Monthly
  imports on the focused schemes keep managers only once the column is added
  back (owner decision).
* G45 (MANAGERCOL): test port 8199 was briefly held by something else ("Port
  8199 is in use", the run exits at once with EXIT=1 and an empty log). Use
  another pair (8193/8192) rather than hunting the holder.
* G46 (MANAGERCOL): a throwaway copy of rize for evidence = `pg_dump rize` →
  `createdb mgrcol_test` → `pg_restore --no-owner --role=odoo`, then jobs and
  logins off, then `dropdb`. An underscore name is not a reachable host name.
* G47 (MANAGERCOL part 2): **"use once" imports never reach the manager step.**
  A one-time batch skips `_update_employee_from_raw_data` entirely (RECORDS
  R1), and every rize import since 2026-10-19 was one-time. A replay meant to
  show what an import does to employee records must set `one_time = False`
  explicitly, and the owner must know managers follow only updating imports.
* G48 (MANAGERCOL part 2): **test ports are shared between builders.** Another
  builder's `-u pb_hr_payroll_formula --test-enable` on p0clone held 8193/8192;
  a second `-u` on the same DB at the same time is unsafe anyway. Check
  `ss -ltnp | grep 819` and wait for it — and never wait with
  `pgrep -f <pattern>` inside an `ssh '…'` whose own command line contains the
  pattern: it matches itself and never ends (and `pkill -f` kills your shell).
* G49 (MANAGERCOL part 2): **a `pg_restore` copy has no file store.** Every
  attachment (an import's uploaded file) reads as empty on the copy ("Please
  upload a file first."). Read the bytes from
  `/odoo/.local/share/Odoo/filestore/<source db>/<store_fname>` instead, and
  remove `/odoo/.local/share/Odoo/filestore/<copy>` after `dropdb`. The live
  server's job runner opens every database it can see, so `dropdb` needs
  `--force` even with the copy's jobs off.

* G50 (MANAGERCOL part 3): **hooking the import's processing from pb_orgchart
  = override `action_process` and check `state == 'done'` afterwards.** The
  approval gate (`payroll_import_approval.py`) answers the first press by
  submitting; when no approval is needed the engine applies in the same press
  and calls `action_process` AGAIN through the full chain, so an outer
  override sees two calls — make the post-pass idempotent (skip rows already
  marked). A press that only sent the file for approval leaves the batch
  `validated`, and the later approval runs the override itself.
* G51 (MANAGERCOL part 3): **four screens promise a "this run only" file
  changes nothing** (pay run wizard choice + coverage chip + result box,
  batch page chip). Since owner ruling 6, managers from the file do change.
  Any future exception to R1 must update those words too (owner decision
  pending on the wording).
* G52 (MANAGERCOL part 4): **`filter_deploy.sh full` kills every `odoo-bin`
  process on the box — `odoo-bin shell` jobs included.** Another builder's
  replay on its own throwaway copy was killed three times by full deploys
  (2026-11-05). Any long `odoo-bin shell` job (replay, seed, backfill) must
  write its own START line in `/opt/deploy-notes.md` — and a DONE line after —
  so deployers see it and wait; a deployer must check for an open START of
  ANY kind (DATA included), not only deploy STARTs, and for running
  `odoo-bin shell` processes (`ps -eo pid,etime,args | grep "odoo-bin shel[l]"`).
* G53 (IMPORT-GENDER): **every 2026-10 Rize import was "use once"**
  (`one_time = true`), which skips the employee writeback — so a writeback
  crash shows up only on an UPDATING import. To prove a writeback fix on a
  copy, replay the file into a new batch with `one_time = false`. And run
  any `odoo-bin shell` job detached (`systemd-run`, output to a file): an ssh
  drop breaks a foreground shell's stdout mid-run.
* G54 (IMPORT-GENDER): **never stage a shared module from HEAD without
  checking for other sessions' WIP commits in it** (`git log <your
  commit>..HEAD -- <module>`). On 2026-11-05 HEAD carried PDR P1's unproven
  `f253c2942` in `pb_hr_payroll_formula`; the deploy was staged from
  `git archive 503279518 -- pb_hr_payroll_formula`, and the staged tree was
  diffed against the live one to prove it was live + this fix only.

