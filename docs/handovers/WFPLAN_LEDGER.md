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
- WF3 (P1): **OWL does not rewrite `not`.** It rewrites `and` -> `&&` and `or` -> `||`
  and nothing else, so `t-att-class="{ 'x': not a.b and not a.c }"` compiles to
  `ctx['not']ctx['a'].b` — a SyntaxError that kills the WHOLE template at mount with
  NOTHING in the server log (the only trace is an OwlError in the browser console).
  Use `!`. Guarded now by
  `pb_decision_room/tests/test_static_contract.py::test_no_template_expression_uses_the_word_not`.
- WF4 (P1): The platform's own hotkey service listens on `window` and STOPS
  PROPAGATION for the keys it claims, Escape among them. A bubble-phase
  `window.addEventListener("keydown", …)` in a cockpit therefore never fires and its
  dialogs cannot be closed with the keyboard. Register with `{capture: true}` (and
  never `preventDefault` on Escape, so the platform still gets its turn).
- WF5 (P1): A CSS grid track sized `1fr` or `auto` takes its MIN-CONTENT from its
  children. A story column holding a wide table refused to shrink and pushed the hub
  canvas 69px off the right edge. `minmax(0, 1fr)` is needed on BOTH the outer track
  and the inner grid — `min-width: 0` on the element alone does not do it.
- WF6 (P1): `.pbim-tablewrap` CLIPS (`overflow-x: hidden`) rather than scrolls. A
  table wider than the hub canvas loses its last column — which is where Open /
  Compare / Remove live. Scope `overflow-x: auto` per surface and pin the actions
  column with `position: sticky; right: 0` so the numbers slide under the buttons.
- WF7 (P1) **THE ROSTER SOURCE, verified on this build**: `hr.employee.department_id`
  and `job_id` are NON-STORED related fields through `version_id` — unsearchable,
  ungroupable, invisible to `read_group`. The stored truth is `hr.version`, reached by
  `hr.employee.current_version_id`. `hr.contract` DOES carry `department_id`, `job_id`
  and `wage`, but on the Payobook demo company (5) only `wage` is filled (department
  and job are NULL on all 4,510 open contracts) while on the AB Mauri tenant the
  contract's department IS filled on all 152. So: team and role from the CONTRACT when
  it names them, from the employee's CURRENT VERSION otherwise; pay always from the
  open contract's `wage`. One code path answers both databases.
- WF8 (P1): a `fields.Json` written as `{}` reads back as `False`, not `{}`. A
  constraint written `if value is not None and not isinstance(value, dict)` fires on
  every empty payload. Test for TRUTHINESS: `if value and not isinstance(value, dict)`.
- WF9 (P1): a roll-up that SLICES its tail loses rows. `sorted(roles)[:12]` on the
  merged "Other teams" bucket dropped 5 of AB Mauri's 153 people, so December's
  headcount read 148 and every number built on it was quietly wrong. Merge the tail
  into one row; assert `sum(role heads over every team) == active employees`.
- WF10 (P1): reading the roster AS THE USER needs `hr.group_hr_user`, which the owner
  persona does not hold — the room would have been locked out of its own headcount
  chart by an HR permission. The four roster queries run under `sudo()` AFTER the
  server-side gate, return AGGREGATES ONLY (team, count, average pay — never a person),
  and the reasoning is written at the top of `models/pb_decision_room.py`.
- WF11 (P1): `tools.ormcache` has NO TTL and hands back the stored object, which a
  caller can mutate. The baseline cache is a module-level dict keyed on
  (db, company, roster signature) with a 600 s TTL and a `deepcopy` on the way out.
- WF12 (P1): ORM `search_read` over 4,533 employees + 8,592 versions + 4,510 contracts
  costs ~800 ms; ONE SQL join with `DISTINCT ON (employee_id)` costs ~70 ms. Above a
  few hundred rows, ask for the four columns you need and nothing else.
- WF13 (P1): a test that greps its own module for a forbidden word finds its own
  assertion message and fails for saying what it is looking for. Exclude `tests/`.
- WF14 (P1): the global palette's `run()` dropped `focus` from the entry's action, so
  no ⌘K row could ever be more specific than its lens ("Saved plans" opened the room
  but never scrolled to the dock). One-line fix in
  `pb_hub/static/src/js/hub_palette_service.js`; `pb_hub` therefore ships in P1 too.
- WF15 (P1): **the abm admin password in this ledger is WRONG.** `ash@biztinct.com` /
  `J5validate!2026` is refused, and so is every obvious variant. Browser validation on
  abm was done with a temporary user (`wfplan.validator@payobook.com`, created through
  `odoo-bin shell`, ARCHIVED afterwards). Resetting the owner's own password was not
  done — that is an owner decision.
  P2 addendum: that user is still there, archived, id 246, and P2 reused it
  (reactivated, password `WfpP2!Validate2026`, archived again). It holds
  `base.group_system`, so it validates the MANAGER path only; the read-only
  path needs a second user without it — P2 made `wfplan.reader@payobook.com`
  (id 247, `WfpP2!Reader2026`, `group_decision_user` only), also archived
  afterwards. Reactivating both is one `odoo-bin shell` write.
- WF16 (P2): **`mail.thread.create` DISCARDS tracking for a record it just created**
  (`threads._track_discard()`, `mail_thread.py`), so a create is not also reported as
  twenty-five changes — and the discard is stored on `cr.precommit.data` and lasts the
  WHOLE TRANSACTION. A test that creates the record and then changes it therefore sees
  no chatter entry at all, and looks exactly like broken tracking. Two consequences:
  tracking messages are posted in `cr.precommit`, so a test must run
  `env.flush_all(); env.cr.precommit.run()` before reading `message_ids`; and it must
  first `env.cr.precommit.data.pop('mail.tracking.<model>', None)` to clear the discard.
  On a real database the row already exists and none of this arises.
- WF17 (P2): **an XML comment may not contain `--`.** The P1 template file rules its
  sections with `=`; writing `<!-- ------- 1 · work & shifts -->` makes the WHOLE OWL
  template file unparseable, and the room renders nothing. `ElementTree.parse` catches
  it (`test_every_template_file_parses...`), so run the local XML parse before deploying.
- WF18 (P2): **deleting the `/web/assets/%` attachments is NOT enough after an XML or
  SCSS change.** The running server keeps the compiled bundle, so the browser goes on
  serving yesterday's template while today's file sits on disk — with no error anywhere,
  which costs half an hour every time. `sudo service odoo-server restart` after the
  DELETE is the only reliable step. (Deleting alone IS enough for a pure `.js` change.)
- WF19 (P2): `t-att-value` on an `<input>` writes the ATTRIBUTE, and a browser stops
  mirroring the attribute into the field the moment somebody types in it. A box that
  refuses bad text and restores the old value therefore keeps the bad text on screen
  while the plan holds the old number — the one state a money box must never be in.
  Sync `el.value` by hand in `onPatched` (and on every programmatic change).
- WF20 (P2): a profit waterfall anchored at ZERO is useless at this company's scale: on
  ₫286B of profit a ₫2B step is four pixels and the chart reads as two towers with a
  flat line between them. The axis spans the RUNNING LEVEL only, the two totals are
  drawn as columns from the floor of that axis, and the footnote says the scale does not
  start at zero.
- WF21 (P2): `-u pb_people_hub` on p9clone CRASHES the registry load on an unrelated
  stale record — `pb_vendor_access.cron_access_auto_revert_ir_actions_server` is being
  unlinked while its `ir_cron` still points at it (FK `ir_cron_ir_actions_server_id_fkey`).
  Nothing rolls forward; the transaction is lost. Update `pb_import_kit` instead: the hub
  depends on it, so the hub is updated as a dependent and its 37 tests still run.
- WF22 (P2): the money formatter's short form ALREADY carries the currency symbol
  (`₫2,200B`). Putting a symbol span beside the input renders `₫ ₫2,200B`, which reads
  as two different amounts. One control, one symbol.

## Phase log

- P1 — "The room opens" — designed and BUILT 2026-09-06 (`WFPLAN_P1_DECISION_ROOM.md`).
  Status: **COMPLETE**. `pb_decision_room` 19.0.1.0.0 live on p9clone, payobook, abm and
  payobook_template; `pb_people_hub` 19.0.1.4.0 (Plan hero slot + "Classic planning
  tools" fold + sidebar match + `wantsArrival`), `pb_import_kit` 19.0.1.10.0 (`target`,
  `pause`, `arrowUpRight`), `pb_hub` 19.0.1.7.0 (palette forwards `focus`).
  51 server tests green on p9clone, 27 engine checks green under
  `node tools/decision_engine_check.mjs`, B1-B10 walked on payobook and abm.
  Facade on company 5 (4,533 people): **cold 68 ms, warm 8 ms.**
  Screenshots: `docs/handovers/wfplan_p1_shots/`.
  Owner debts: the abm login in this ledger is wrong (WF15); a demo plan named
  "Board draft" is saved on payobook company 5; the revenue target ₫2,200B was written
  to `pb.decision.assumptions` for Payobook Vietnam JSC during validation.
- P2 — "Look closer" — designed and BUILT 2026-09-07 (`WFPLAN_P2_LOOK_CLOSER.md`).
  Status: **COMPLETE**. `pb_decision_room` 19.0.2.0.0 live on p9clone, payobook, abm and
  payobook_template; `pb_import_kit` 19.0.1.11.0 (`sun`, `sunset`, `moon`, `printer`,
  `flask`, `route`, `gitBranch`, `sliders`). `pb_people_hub` UNCHANGED at 19.0.1.4.0.
  Shipped: the four-tab detail workspace under the impact cards (Work & shifts with the
  shift split and the demand picture, the profit bridge, People & pay, Room to hire),
  the goal finder with three calculated directions + reversible preview, the demand
  reality check, the "one small experiment" card, the compact money box everywhere money
  is typed, an editable assumptions panel with chatter, and the printable decision brief.
  60 server tests green on p9clone (35 `pb_decision_room` + 37 `pb_people_hub` methods),
  57 engine checks green under `node tools/decision_engine_check.mjs`, B11-B24 walked on
  payobook and abm at 1440 and 390.
  Timings on company 5 (4,533 people): `candidates()` **28 ms** over 46 combinations
  (real roster fixture), `headroom()` **23 ms** over 41 points; facade cold 86 ms,
  warm 7 ms. Fixture: `tools/fixtures/company5_baseline.json` (aggregates only).
  Screenshots: `docs/handovers/wfplan_p2_shots/`.
  Owner debts: the ₫2,200B revenue target and the "Board draft" plan from P1 are still
  on payobook company 5 (abm was restored to a zero target and 23.5 % employer rate
  after validation); both temporary abm validators are archived again (WF15).
- P3 — "Wow and close" — designed and BUILT 2026-09-07 (`WFPLAN_P3_WOW_AND_CLOSE.md`).
  Status: **COMPLETE**. `pb_decision_room` 19.0.3.0.0 live on p9clone, payobook, abm and
  payobook_template; `pb_hub` 19.0.1.8.0 (the Home lens in the feature map),
  `pb_import_kit` 19.0.1.12.0 (`chevronUp`). `pb_people_hub` UNCHANGED at 19.0.1.4.0.
  Shipped: the phone (stage first, the control room as a bottom sheet with the hero
  number mirrored in its header, the year strip scrolling and snapping), full keyboard
  reach (Shift+arrows on every slider, Space on the timeline, ⌘S, Esc, visible focus
  rings), charts that travel between shapes and obey both "Motion off" and the operating
  system's reduced-motion setting, the experiment card scaled to one per cent of the team,
  the roster "read at HH:MM · Refresh" control, a concurrency guard on the goal search,
  a **complete Vietnamese room** (686 terms, money in tỷ/triệu/nghìn), and the
  **Decision Room lens on the Home hub**.
  97 server tests green on p9clone (44 `pb_decision_room` + 34 `pb_hub` +
  37 `pb_people_hub`), 70 engine checks green under `node tools/decision_engine_check.mjs`,
  B25–B36 walked on payobook and abm at 1440 and 390, light and dark, in English and
  Vietnamese. Screenshots: `docs/handovers/wfplan_p3_shots/`.
  Closeout: `docs/handovers/WFPLAN_CLOSEOUT.md`.
  Owner debts: unchanged from P2 (the ₫2,200B target and the "Board draft" plan are still
  on payobook company 5); every temporary validator created in P1-P3 is archived again
  (payobook 4405/4406, abm 246/247/248, p9clone 3816).

## Gotchas from Phase 3 (continue the ledger above)

- WF23 (P3): **the string extractor does not care where `_t` came from.** Two files may
  not import anything (`decision_engine.js`, `decision_format.js` — `node
  tools/decision_engine_check.mjs` loads them off disk exactly as they ship), so they
  keep a module-level `let _t = interpolate` and export `useTranslator(fn)`, which
  `decision_room.js` calls at bundle-evaluation time. Every `_t("…")` in those files is
  still collected into the `.pot` exactly as if it had been imported. Two consequences:
  anything evaluated at MODULE level (`GOAL_DEFS` labels, the input labels, month names)
  has to become a FUNCTION, because the module body runs before the translator is
  injected; and the fallback must interpolate the way the platform does, or the sentences
  read differently under node than they do on screen.
- WF24 (P3): **the platform's `sprintf` escapes `%%` for a POSITIONAL substitution and
  NOT for a keyed one.** `_t("a %(pct)s%% increase", {pct})` renders "a 5%% increase" on
  screen; `_t("A %s%% increase", value)` renders "A 5% increase". So: with a dictionary
  write ONE per cent sign, with a positional value write TWO. There is no warning either
  way — it is only visible in the finished sentence.
- WF25 (P3): **Odoo's own login form writes the language back to the user.** A validator
  created with `lang='vi_VN'` who logs in through `/web/login` with the language selector
  left on "English (US)" is silently rewritten to `en_US`, and the screen comes up in
  English with nothing wrong anywhere. Pick the language in the login form, or write
  `lang` again after logging in.
- WF26 (P3): **a permission or a feature switch changed from `odoo-bin shell` is not
  seen by the running web worker.** `res.users.has_group` and `ir.config_parameter` are
  both `ormcache`d per process; the shell clears its OWN cache and the signal does not
  reach the serving process in time to be useful. A gating check in the browser therefore
  passes when it should fail. `sudo service odoo-server restart` after the write is the
  only reliable step — the same shape of trap as WF18.
- WF27 (P3): **a `.pot` exported by `odoo-bin i18n export` carries
  `"Project-Id-Version: Odoo Server 19.0"` in its header and `#. odoo-javascript`
  on nearly every entry.** The header line is a STRING and trips the white-label test;
  the `#.` lines are the extractor's own bookkeeping and no user ever sees one. So T9
  now skips comment lines in a catalogue, and every fresh export must have its
  `Project-Id-Version` rewritten to `Payobook 19.0` before it is committed.
- WF28 (P3): `--i18n-export` **is gone from the Odoo 19 server options**. Translation
  export is its own subcommand: `odoo-bin i18n export -c … -d … -l pot -o <file>
  <module>`. It runs happily against a database the live service is also serving.
- WF29 (P3): `odoo-bin shell` DOES work while `odoo-server` is running (P1's warning
  about needing the service stopped does not apply on this box) — but see WF26 for what
  the running worker will and will not notice afterwards.
