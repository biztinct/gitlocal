# WFPLAN Programme Ledger — the Decision Room (conventions, plumbing facts, gotchas, phase log)

Every WFPLAN phase handover references this file. Read it FULLY before coding. Append
(never rewrite history) when you hit a new gotcha — that is part of every phase deliverable.

Programme: build **the Decision Room** — a CEO-grade what-if workforce planner — inside the
People app under **People → Plan**, replacing the legacy `pb_hr_workforce_planning` screens
as the way a company plans its year. The approved concept is the Codex-built
**"Option 05 · The Decision Room"** at `design_poc/workforce_lab/public/option5.html`
(+ `option5.css`, `option5.js`, `decision-model.js`, `living-model.js`, `model.js`), approved
by the owner on 2026-09-06. Its money model is fictional USD; ours is the company's real
roster, real pay, real currency and Vietnam 2026 statutory rules, which already exist in
`design_poc/wfplan/src/core.js` (Claude's VN engine — port, do not re-derive).

Owner rulings (binding):
- Main user is **the CEO/owner**: few knobs, big picture, plain English. HR/Finance get a
  detail layer, never the front door.
- Profitability = **the user types a yearly revenue target** (and optional growth by
  December). No accounting connection. Profit and margin react live.
- Knobs: headcount per team/role, salary raises, overtime & shifts, hire timing, attrition,
  plus any the designer judges useful (demand growth, stress, productivity).
- The legacy `pb_hr_workforce_planning` module may be **discarded** — its screens stay
  reachable in a fold ("Classic planning tools") until the owner retires them. Do NOT
  modify anything inside `pb_hr_workforce_planning/` (a test walks the directory).
- Phased workflow: Fable designs handovers, Opus builds + tests each phase; phases run
  back-to-back; only destructive actions or genuine scope decisions stop the run.
- Name chosen by Fable (owner delegated): product name **"Decision Room"**, module
  `pb_decision_room`, lens key stays `plan`; the Plan lens now LANDS in the Decision Room.

## Target & credentials

- Master DB `payobook` at https://payobook.com — build and validate here first.
  Admin login for browser validation: `ash@biztinct.com` / `Rize#Payobook2026`.
  Demo company = **Payobook Vietnam JSC** (company id 5): 4,533 active employees, 40
  departments, 42 jobs, 4,510 open contracts with wage > 0, payslips through 2026-11-30.
- Tenant `abm` (AB Mauri, company 1: 153 employees, 24 departments, 65 jobs, 152 paid
  contracts, payslips to 2026-06-30). Login `ash@biztinct.com` / `J5validate!2026`.
- Clone DB `p9clone` exists on the server — use it to REHEARSE installs and to run the
  Odoo test suite (never run `--test-enable` against `payobook` or `abm`).
- Golden template `payobook_template` must also get the module (new tenants clone it).
- `acme` DB no longer exists (do not try to upgrade it).
- Live server ssh alias `Payobook19v2` (static IP 3.104.113.197). Odoo 19 CE, service
  `odoo-server`, config `/etc/odoo-server.conf`, log `/var/log/odoo/odoo-server.log`,
  passwordless sudo. Listing `/odoo/odoo-server/addons` needs `sudo`.

## Binding rules (violations = phase failure)

1. **White-label**: the word "Odoo" (or its branding) must NEVER appear in any
   user-visible string — labels, help, placeholders, errors, toasts, reports, menu names,
   `.po` msgstr. Use "Payobook" or neutral wording. Technical identifiers are untouched.
2. **Plain-English UI**: every label, toast, empty state and sentence uses the words a
   non-technical CEO knows. No internal jargon, no code names, no "scenario state JSON".
3. **ONE addons directory**: everything deploys to `/odoo/odoo-server/addons`.
   `/odoo/custom/addons` is DEAD (guard-filed). NEVER `rsync --delete` with
   `/odoo/odoo-server/addons/` itself as destination — scoped per module dir only.
4. **Never deploy vendored standard addons** (web, hr, hr_*, crm, website*, spreadsheet,
   resource…) — the server has newer copies from its own clone.
5. **Commit per feature**: explicit file staging (`git add <paths>`; never `git add .` /
   `-A` — the tree has unrelated dirty files from other streams: pb_settings/*,
   pb_vendor_access/*, docs/handovers/ACCESS_*). Reviewer-focused message, end with
   `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. Do NOT push.
6. **Design system**: Lucide icons only via the single `ic()` registry in
   `pb_import_kit/static/src/js/import_icons.js` (add missing icons THERE, camelCase keys).
   No emoji, no unicode glyph icons (✧ ↗ ☀ ◐ ☾ ↶ in the concept become `ic()` icons).
   **No colour gradients** (the concept's stage gradient becomes flat `#241F52`, a dot
   texture overlay is fine). Kit fonts only (no Georgia/serif). Uniform indigo kit:
   `.pbim-*` primitives from pb_import_kit, root class `pbim pbim-page dr`.
   Palette: primary `#5A4BB0`, soft `#EDEAF8`, mid `#CBC2EE`, dark `#241F52`, canvas
   `#F4F5FB`, ink `#1E1B2E`, sub `#64748B`, line `#E2E8F0`, money-good `#2E7D4F`,
   rose `#DC2668`, warn `#D97706`, teal `#0F766E`.
7. **Design bar (owner's words, verbatim, put it in every phase report and score against
   it): "extreme WOW, intuitive, out-of-this-world experience, best in class."** Hero
   moment named; zero dead-ends (every state — empty, loading, error, partial, huge — is
   designed and names its next step); plain language everywhere; motion with purpose;
   keyboard + bulk ergonomics; measured against the best SaaS planner (Causal, ChartHop),
   not stock forms. Validate with Chrome MCP (light AND dark, desktop AND 390px phone)
   before reporting done — click every button, walk every flow.
8. **Nothing the room does changes payroll, hiring or contracts.** It reads; it saves
   plans; it never writes to hr.* or payslips. Say so on screen ("Explore freely. Nothing
   here changes payroll.").
9. **Tenant parity**: tenants get every module the master gets. Order: install on
   `p9clone` (rehearsal, run tests there) → `payobook` → `abm` → `payobook_template`.
   Never a silent auto-install: backup (`pg_dump` to /tmp) before each tenant install.

## Plumbing facts (verified 2026-09-06 — do not re-derive)

### The People hub and its Plan lens
- The left rail with EMPLOYEES / CONTRACTS / RECORDS / ASSETS / PRAISE / PLAN is the
  **HubShell lens rail**, not `pb_sidebar`. Rail markup
  `pb_hub/static/src/xml/hub_shell.xml:85-105`; shell logic (gating, lens memory
  `pbhub.people.lens.v1`, feature gate) `pb_hub/static/src/js/hub_shell.js:110-355`.
- Hub config `pb_people_hub/static/src/js/people_hub.js:92-112`. Lenses: employees,
  contracts, `...extraLenses()` (registry `PEOPLE_LENSES = "pb_people_hub_lens"`,
  people_hub.js:82), then the hard-coded PLAN lens at :108-110
  `{ key: "plan", icon: "trendingUp", label: _t("Plan"), Component: PlanLauncher,
  groups: PLAN_GATE, feature: "people_plan" }`.
- A lens receives props `{ embedded: true, ...def.props }` only (hub_shell.js:319-336);
  `wantsArrival: true` adds `arrival`. Props identity must stay stable (W21).
- `PlanLauncher` = `pb_people_hub/static/src/js/plan_launcher.js` (template
  `pb_people_hub.PlanLauncher`, `pb_people_hub/static/src/xml/people_hub.xml:20-49`,
  SCSS `.pbpl*` in `pb_people_hub/static/src/scss/people_hub.scss`). Seven `PLAN_CARDS`
  (:70-114) open by xmlid via `actionService.doAction(xmlid, {clearBreadcrumbs:false})`.
  `PLAN_GATE` = the three `pb_hr_workforce_planning.group_wfp_*` groups (:60).
- **Tests that constrain edits to the launcher** (`pb_people_hub/tests/test_people_hub.py`):
  the `export const PLAN_CARDS = [ … \n];` block must survive (regex, :74); the card order
  and count (7) must survive; the file must contain `clearBreadcrumbs: false`,
  `"pb.settings", "resolve_actions"`, `registry.category("actions").contains`,
  `this._opening`; it must NOT contain `@pb_hr_workforce_planning/`, `embedded: true`, or
  any `wfp.` model name other than the seven; `pb_people_hub` must own no `models/` dir;
  `people_hub_palette.js` must import from `plan_launcher` and contain no `group_` literal;
  every lens `key: "x", icon:` in people_hub.js needs a `lens: "x"` palette entry.
  `git diff --quiet -- pb_hr_workforce_planning` must stay clean.
- Feature switch `people_plan` (`pb_tenants/data/pb_feature.xml:125`, mapped at
  `pb_hub/static/src/js/hub_features.js:102-103`, mode `hide`, default on).
- Outer rail item for People: `pb_people_hub/data/pb_sidebar.xml:47-58` — `match_action_tags`
  lists the tags that keep "People" highlighted; a new client action tag must be appended
  there (`pb_decision_room`) — that file is in `pb_people_hub`, so it is a
  `pb_people_hub` change (bump its manifest version).

### The cockpit precedent to clone: `pb_assets`
- Manifest `pb_assets/__manifest__.py:73-86`: assets order **scss → leaf component js →
  palette js → templates xml**. Depends on `pb_hub`, `pb_import_kit`, `pb_people_hub`.
- Client action RECORD (never a bare tag): `pb_assets/views/pb_assets_action.xml:11-14`.
- Registry line `pb_assets/static/src/js/assets_board.js:589`
  `registry.category("actions").add("pb_assets", PbAssetsBoard)`; class :42 with
  `static template = "pb_assets.PbAssetsBoard"`, `onWillStart(load)` :91, data via
  `this.orm.call("pb.assets", "get_board", [])` :99.
- Lens + ⌘K registration `pb_assets/static/src/js/assets_palette.js:41-63` (lens seq 50,
  palette seq 2200 block, `requires: "pb_assets"`, `action: {xmlid: HUB_XMLID, lens}`).
- Facade `pb.assets` AbstractModel `pb_assets/models/pb_assets_board.py:54-123`:
  `_safe()`, `_can_read/_can_write/_require_*`, `get_board()` returns
  `{allowed:false, …empty}` for a reader with no group (explained empty, not AccessError),
  `self.env.companies.ids` scoping on every search, row caps, no sudo in reads.
- SCSS precedent `pb_assets/static/src/scss/assets.scss` (root `.pbim.ast`, `--pbim-*`
  tokens only).

### Data the room reads (Odoo 19 on the live server)
- `hr_employee` has NO `job_id` / `department_id` columns on the live DB (Odoo 19 moved
  them to `hr.version`); it has `company_id`, `contract_id`. `hr_version`, `hr_contract`,
  `hr_job`, `hr_department`, `hr_payslip_run` tables all exist.
- `hr.contract` (from om_hr_payroll on this build) has `wage` (Monetary), `state`,
  `employee_id`, `company_id`; verify on p9clone whether it also carries `job_id` and
  `department_id` (it did in Odoo ≤17) — that is the preferred roster source since pay is
  there. Employees without an open contract still count as heads.
- `hr.payslip.run` has NO `company_id`. `hr.payslip` has `company_id`, `date_to`.
- Everything above 500 rows must be `read_group`/SQL, never per-record loops (4.5k staff).

### Chart/engine sources to port (read them; do not reinvent)
- `design_poc/wfplan/src/core.js` (510 lines): VN 2026 statutory (ER 23.5 %, EE 10.5 %,
  cap ₫46.8M, PIT ladder), Tet bonus in January, seasonality, recruit cost, severance,
  attrition + backfill, `compute(state)` → months/year/byDiv, demand mode
  (capacity follows revenue-earning heads × hours factor; revenue = min(demand, capacity);
  coverage/unserved), goal-seek `maxHeadsForMargin` / `maxRaiseForMargin`, `describe()`,
  `warnings()`, SVG chart kit (`lines/bars/waterfall/stack` with `endLabels`, wrapped
  category labels), `animateNumber`.
- `design_poc/workforce_lab/public/decision-model.js`: goal definitions, `evaluate`,
  `grade`, `candidates` (three lanes: hire / develop / balanced), `headroom`, `series`.
- `design_poc/workforce_lab/public/living-model.js`: `bridge` (profit waterfall that sums
  exactly), `stressBand`, `marginal`, `changes`, `story`, `stressOutcome`, `assumptions`.
- `design_poc/workforce_lab/public/option5.js`: the page behaviour — horizon canvas,
  hero number animation, month callout, stage tiles, year lens, impact journey + ripple,
  detail tabs, scenario dock, dialogs, undo/preview semantics.
- `design_poc/workforce_lab/public/option5.css`: the look (Payobook-tinted at the end of
  the file; the second `:root` block wins).
- Screenshot of the approved page: `docs/handovers/wfplan_shots/option5_approved.jpg`.

## Odoo 19 gotchas (all bit us before; do not rediscover)

- `safe_eval` has no `nocopy`. `res.users.groups_id` → `group_ids`/`all_group_ids`.
  `res.groups` has no `category_id`. `hr.employee.gender` → `sex`.
- `_sql_constraints` is SILENTLY IGNORED — use
  `_x_uniq = models.Constraint('unique(...)', 'msg')` class attributes.
- `ir.cron`: `numbercall`/`doall` REMOVED. `post_init_hook` fires on INSTALL only.
- `<report>`/`<act_window>` shortcut tags are gone — explicit `<record>`s.
- Recordsets cannot hold instance attrs — stateless builders.
- Unset Char reads as `False`. Private `_methods` are not callable over JSON-RPC.
- Sass: `min()/max()` with mixed px/% units kills the WHOLE asset bundle. `-u` does NOT
  surface SCSS compile errors — always Chrome-load a page after an SCSS deploy and look
  for the red style-error bar.
- OWL: `t-if/t-elif/t-else` must be adjacent siblings (a comment between them breaks the
  chain at runtime, W23). A getter returning a fresh object as child props re-renders the
  child every paint (W21) — memoise. Unknown props are hard errors in dev mode.
- `fields.Json` exists on Odoo 19 — use it for plan state and goals.
- Canvas in OWL: size with `getBoundingClientRect()` × `devicePixelRatio` on every draw;
  redraw on `ResizeObserver`, never assume the lens width (the hub rail takes 76px and
  the panel can be collapsed).

## Deploy ritual (proven; follow exactly)

1. Clean stage: `ssh Payobook19v2 'rm -rf /tmp/wf_stage && mkdir -p /tmp/wf_stage'`.
2. `rsync -az --exclude=__pycache__ --exclude='*.pyc' --exclude=.git pb_decision_room pb_people_hub pb_import_kit Payobook19v2:/tmp/wf_stage/`
   (only the modules you changed; NEVER vendored standard addons).
3. Per module: `sudo rsync -a --delete --chown=odoo:odoo /tmp/wf_stage/<m>/ /odoo/odoo-server/addons/<m>/`.
4. Rehearsal + tests on the clone (service may stay up; use spare ports):
   `sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d p9clone -i pb_decision_room -u pb_people_hub,pb_import_kit --test-enable --test-tags /pb_decision_room,/pb_people_hub --stop-after-init --http-port=8199 --gevent-port=8198 > /tmp/wf_test.log 2>&1; echo EXIT=$? >> /tmp/wf_test.log`
   (detach with `sudo systemd-run --collect --unit=wf-test /bin/bash /tmp/wf_test.sh`,
   poll for EXIT=, grep `Traceback|CRITICAL|ERROR|FAIL`). Bump manifest versions before
   every `-u` or `--test-enable` silently runs 0 tests.
5. Production install: `sudo service odoo-server stop`; detached
   `… -d payobook -i pb_decision_room -u pb_people_hub,pb_import_kit --stop-after-init`;
   then `-d abm …` and `-d payobook_template …`; `sudo service odoo-server start`; confirm
   `ss -ltn | grep 8069` and "Registry loaded" in the log (~50 s).
6. After JS/SCSS-only changes with no `-u`: per DB
   `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';` then hard reload.
7. Verify version landed: manifest version vs `ir_module_module.latest_version` per DB
   (series prefix `19.0.` is added). Verify files: hash the module tree both sides.
8. Never `pkill -f odoo-bin` (self-matches). One odoo master only. Prefer JSON-RPC /
   browser `call_kw` over `odoo-bin shell` (shell needs the service fully stopped).
9. Test URL for the cockpit: `https://payobook.com/odoo/action-pb_decision_room`
   (`/odoo` 301s to `/bizapp`; both work). The People hub: `/odoo/action-pb_people_hub`.

## Gotcha ledger (append below; W-numbers continue from WF1)

- WF1 (2026-09-06): Two AI tools editing one folder concurrently (Codex + Claude in
  `design_poc/workforce_lab`) broke the page mid-edit. Rule: one tool per folder; check
  `ps aux | grep codex` and mtimes before touching `design_poc/workforce_lab/`. The
  Decision Room build never edits that folder — it only reads it.
- WF2: The Codex concept uses USD, 240 fictional staff, `$150/hour`. None of that ships.
  Every number on screen comes from the company's roster, pay, currency and the
  assumptions record; the demand model is calibrated to the typed revenue target.

## Phase log

- P1 — "The room opens" — designed 2026-09-06 (`WFPLAN_P1_DECISION_ROOM.md`). Status: building.
- P2 — "Look closer" (detail workspace, goal finder, stress, compare, brief). Not yet designed.
- P3 — "Wow and close" (motion, phone, VI, home tile, legacy fold ruling, closeout). Not yet designed.
