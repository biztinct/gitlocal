# Workforce Redesign — Program Conventions & Gotcha Ledger (W-rules)

Program: rebuild the WORKFORCE section as **Option B "Mission Control", staged through Option A's
consolidation, powered by Option C's engine** — per the approved dossier
`docs/WORKFORCE_REDESIGN_OPTIONS.html` (mockups A/B/C + P0–P4 roadmap live there).

Every phase handover in `docs/handovers/WORKFORCE_P*.md` references this file. **Opus: when you hit a
new gotcha or make a binding convention decision, append a numbered W-rule here in the same commit.**
Cross-program rules (deploy ritual, formula-input registry, C18.x gotchas) stay in
`docs/FORMULA_ENGINE_CONVENTIONS.md` — reference them, don't duplicate.

## Program operating model (locked by owner, 2026-08-17)

- **W0.1** Cycle = Fable designs handover → **Opus 5 implements, tests, and self-reviews** → owner says
  "opus done" → Fable designs the next phase. **Fable does NOT code-review Opus's work in this program**
  (owner decision, token economy). Opus therefore owns quality end-to-end: every feature commit ships
  with its tests, and Opus performs an explicit self-review pass (read your whole diff against the
  handover before reporting done).
- **W0.2** Roadmap: P0 foundation → P1 consolidation (Today board + Time hub, 14→7 items) →
  P2 Schedule instrumentation → P3 Mission Control shell → P4 engine (tolerances, locks, ack, pulse).
  Each may split into sub-sessions (P1a/P1b…) — the handover says which.
- **W0.3** Commit-per-feature: one focused commit per work package, explicit file staging,
  reviewer-grade message. Never push unless the owner asks.

## Design-system laws

- **W1 One-accent law.** Every Workforce surface consumes `--pbim-*` tokens
  (`pb_import_kit/static/src/scss/import_tokens.scss`). Allowed identities: the indigo primary
  `#5A4BB0`, or the *promotion of an existing pbim semantic* (precedent: Overtime Desk promoted amber
  `#D97706` / hover `#B45309`). Canonical promoted-green scale (Leave): primary `#2E7D4F`, hover
  `#246A42`, soft `#E3F2E9`. **Never invent a hex.** Chart categorical order (CVD-validated):
  `#5A4BB0 → #D97706 → #2563EB → #DC2668`.
- **W2 Icons.** Lucide only, via `ic()` / the `IC` registry in
  `pb_import_kit/static/src/js/import_icons.js`. New icons are ADDED to that registry — no new
  per-module icon files from P0 onward. Never FontAwesome, never emoji.
- **W3 No gradients on chrome.** Flat fills only. Exception: `conic-gradient` as a *chart* fill
  (donut gauges, e.g. pb_team's compliance donut) is legitimate data-viz, not chrome.
- **W4 Context law.** Department, week and person selection come from the shared `wf_context` service
  (pb_wf_kit). Redesigned surfaces must not ship private department/week pickers.
- **W5 Every record is a door.** No dead-end surfaces: avatars/rows/KPIs open a drawer, popover, or a
  deep-link with a return path. Native-form escapes use `target:"new"` + `onClose` reload
  (Business Trips precedent) — never `target:"current"` with no way back.
- **W6 Kit-first.** Shared UI (context bar, drawer, ribbon, and later dock/popover) lives in
  `pb_wf_kit`. Cockpits import it; they never fork copies.

## Engineering rails

- **W7 i18n.** Every new `.po` entry carries `#. module: <name>` AND a `#. odoo-python` /
  `#. odoo-javascript` marker (Odoo 19 loads nothing without them — C18.74); run
  `msgfmt --check-format` before deploy.
- **W8 Sidebar hygiene.** `pb.sidebar.item` sequences are unique within a section; a sidebar item's
  `groups_id` must match any legacy menu twin's gate. `pb_sidebar/data/pb_sidebar_data.xml` is
  `noupdate="0"` (verified 2026-08-17) — record edits land via plain `-u pb_sidebar`.
- **W9 Testing.** Tests are committed WITH the feature commit, never promised. Never run a bare
  `--test-tags` without a scoping `-u` (C18.40 — legacy om_hr_payroll test imports crash DB init).
- **W10 Deploy.** Follow the established live ritual (Sudima A–M precedent): md5 parity repo↔server,
  scoped `-u`, kill stale odoo-bin before `-u`, stale-assets purge
  (`DELETE FROM ir_attachment WHERE name LIKE '%.assets_%' OR url LIKE '/web/assets/%'` + restart) when
  an OWL change doesn't appear, then **Chrome-MCP validation on the live site is mandatory** before
  reporting done (C18.71: OWL template errors only surface at runtime — `-u` + tests are not enough).
- **W11 Behavior freeze in restyle phases.** A phase marked "pixels only" (P0) touches CSS/SCSS/XML
  templates and explicitly listed data records — no model, facade, ACL, or workflow changes beyond the
  handover's list.
- **W12 Money/security rails.** Never widen sudo; existing gates and the C18 formula-input registry
  are untouchable except where a handover explicitly says otherwise.

## Ledger

- **W13 `noupdate` is per-FILE, and the Workforce sidebar items are spread over seven files.**
  W8 recorded that `pb_sidebar/data/pb_sidebar_data.xml` is `noupdate="0"`. That is only true of
  *that* file. The 14 Workforce items actually come from seven data files, and three of them ship
  `<odoo noupdate="1">`, so a plain `-u <module>` silently does nothing to their records:
  | file | noupdate (before P0) |
  |---|---|
  | `pb_sidebar/data/pb_sidebar_data.xml` | 0 |
  | `pb_hr_workforce/data/pb_sidebar.xml` | 0 |
  | `pb_team/data/pb_sidebar.xml` | 0 |
  | `pb_driver_checkin/data/pb_sidebar.xml` | 0 |
  | `pb_timeoff/data/pb_sidebar.xml` | **1** → flipped to 0 in P0 WP-H |
  | `pb_business_trip/data/pb_sidebar.xml` | **1** |
  | `pb_attendance_flow/data/pb_sidebar.xml` | **1** → flipped to 0 in P1a WP-5 |
  Rule: before editing any `pb.sidebar.item`, check the *declaring* file's `<odoo noupdate=…>`.
  **And flipping it to 0 is NOT enough on an existing database — see W13.1.**
- **W13.1 `noupdate` lives in the DATABASE, and Odoo never refreshes it. (Proven on the live server,
  2026-08-17 — this cost P0 a second deploy round.)** `ir_model_data.noupdate` is a per-record column.
  `IrModelData._build_update_xmlids_query` (Odoo 19, `base/models/ir_model.py` ~:2425) writes only
  `(model, res_id, write_date)` on conflict — the `noupdate` column is never in the UPDATE list — and
  `Model._load_records` (`odoo/orm/models.py` ~:5163) skips any record whose STORED flag is set:
  `if not (update and d_noupdate): to_update.append(data)`.
  Therefore editing `<odoo noupdate="1">` → `"0"` only changes what a *fresh* install records. On
  every existing database the record stays frozen **forever** and `-u <module>` silently applies
  nothing — no error, no warning, the log looks perfectly healthy. P0 shipped Leave seq 30→32,
  `-u pb_timeoff` returned EXIT 0, and the database still said 30.
  To actually move such a record: flip the file attribute (for future installs) **AND** ship a
  `migrations/<new-version>/post-migrate.py` that clears the stored flag and applies the value —
  bumping the manifest version, since migrations only run on a version change. Precedent to clone:
  `pb_timeoff/migrations/19.0.1.0.3/post-migrate.py`. Keep it idempotent and only overwrite the old
  value, so an admin's later customization is not overruled.
  **Still frozen as of P1a**: `pb_business_trip/data/pb_sidebar.xml` (Business Trips) only —
  `pb_attendance_flow` was unfrozen by P1a WP-5
  (`pb_attendance_flow/migrations/19.0.1.0.4/post-migrate.py`, cloned from the pb_timeoff
  precedent). P1b renumbers the section and must ship the same unfreeze for pb_business_trip,
  or Business Trips will not move.
  **Always assert the DB value after `-u`.** A repo-only "fix" is indistinguishable from a real one
  unless something reads the database back; that is what `pb_wf_kit/tests/test_p0.py
  ::test_moved_items_landed_on_their_new_sequences` is for, and it is what caught this.
- **W14 A `var()` fallback is a real colour, not a comment.** Surfaces that mount OUTSIDE a `.pbim`
  root — native-form field widgets (`pb_business_trip` trip composer), Leaflet pins rendered at
  document level (`pb_driver_checkin`) — never see the `--pbim-*` custom properties, because those are
  emitted by `@include pbim-root-vars` inside the `.pbim` selector only (`import_kit.scss` :7-8). In
  those files the fallback is what actually paints, so it must carry the correct pbim hex. Corollary:
  `--pbim-primary-soft` **does not exist** in `import_tokens.scss` — the soft indigo token is
  `--pbim-soft`. Referencing the wrong name yields a permanently-fallback colour that looks like a
  theme bug. Check the name against the `pbim-root-vars` mixin before using it.
- **W15 You cannot alpha-suffix a `var()`.** `var(--x, #abc)33` is invalid CSS; the whole declaration
  is dropped silently (found on two live borders in `trip_composer.scss`). Use
  `color-mix(in srgb, var(--x, #hex) 20%, transparent)`. Confirmed safe through Dart Sass — unlike
  mixed-unit `min()/max()`, `color-mix()` passes straight through to the bundle.
- **W16 `wf_context.set()` is the ONLY write door.** The service exposes its
  `reactive` state because every consumer needs `useState(ctxSvc.state)` to subscribe — that is
  the whole cross-cockpit sync mechanism and it cannot be hidden behind a proxy without breaking
  it. But the state is *read-only to consumers*: a direct `ctx.state.weekStart = x` /
  `this.wf.day = x` skips normalization (Monday snapping, day validation), skips the
  **`day` ∈ `[weekStart, weekStart+6]` invariant**, skips `localStorage` persistence AND skips the
  `onChange` fan-out — so the surface looks right while every other cockpit silently desyncs, and a
  reload throws the change away. Always `ctxSvc.set({...})` (or `shiftWeek` / `shiftDay` / `today` /
  `reset`, which all funnel through it). Enforced by a grep gate in each phase's static tests:
  `grep -rn "\.state\.\(departmentId\|weekStart\|personId\|search\|day\) *=" <workforce modules>`
  must be empty outside `wf_context_service.js` itself.
  Reconciliation rules `set()` owns (P1a): `weekStart` in the patch wins and the day is clamped
  keeping its **weekday** (Wed stays Wed when you page weeks); a bare `day` patch drags the week to
  that day's Monday; a junk `day` is ignored rather than stored.
- **W17 Embedding pattern: one component, one facade, two mount points.** When a hub absorbs an
  existing cockpit as a lens, do **not** copy its body into the hub and do not fork a "lens" variant
  (W6). Give the existing component an `embedded` boolean prop (plus, where it has internal views, an
  `initialView`), and:
  1. the component keeps its `registry.category("actions")` registration, so the standalone action
     and any `doAction` caller keeps working until the retirement phase deletes it;
  2. `embedded` suppresses **only chrome the hub already owns** — its hero/title, its own
     `<WfContextBar/>`, its back-to-board button. Never its logic, never its facade calls;
  3. the hub's context bar rules (W4): in embedded mode the child reads `wf_context` instead of any
     private week/department state, and re-fetches when the context changes;
  4. `export` the class so the hub can `import { X } from "@module/js/file"` — Odoo maps
     `@module/js/…` to `module/static/src/js/…`, and the file is already in `web.assets_backend`
     because the hub depends on the module.
  Applied twice in P1a: `AttendanceWeekGrid` (Week Grid lens) and `PbAttendanceFlow`
  (Exceptions + Import lenses, `initialView` `board` / `import`).
- **W18 A retired sidebar item still OCCUPIES its sequence.** `active = False` takes an item off
  the rail but not out of the section: `pb_wf_kit/tests/test_p0.py::test_workforce_sequences_are_
  unique` deliberately searches with `active_test=False`, because a duplicate only has to matter
  the moment an admin re-enables the record. So when a new surface inherits a retired item's
  sequence, the retired one must MOVE, not merely deactivate. P1a parks retirements in a **900+
  retired band** (`item_wf_timecards` 30 → 900) and leaves non-colliding retirements where they
  are (`item_wf_weekentry` 35, `item_attendance_control` 25), which keeps the live section's
  numbering readable while the uniqueness rule still holds over the whole set.
- **W19 A `var()` fallback also has to be a real *value*, not just a real colour.** W14's corollary
  extends past colours: `--pbim-pill` **does not exist** in the `pbim-root-vars` mixin
  (`import_tokens.scss` :55-86 emits `--pbim-r`, `--pbim-r-sm`, `--pbim-r-lg`, `--pbim-sh`,
  `--pbim-sh-lg` — no pill). `border-radius: var(--pbim-pill, 999px)` therefore renders permanently
  from its fallback, which *works* but silently claims a token that isn't there and would survive a
  future token change untouched. Write the literal (`999px`) or add the token; do not fake it.
  Check any `--pbim-*` name against the mixin before using it — colour or not.
- **W20 An embedded cockpit that scrolls ITSELF needs a DEFINITE height from the host.** Found live
  in P1a: the Week Grid lens was given `height: auto; min-height: 420px` so it would "just flow"
  inside the hub's scrolling page. It grew to its full content height (14 563 px on a 196-row week),
  and once the box was auto-height its flex child stopped shrinking — `.bwg` has `min-width: auto`,
  which resolves against min-content, so the grid rendered 1 496 px wide inside a 1 305 px parent and
  slid straight under the overtime-ceilings rail, covering the Save button. Nothing errored; it just
  looked broken. Rule: a lens whose cockpit owns internal scrolling keeps `height: 100%`, and the
  hub gives it a bounded box for the lenses that need it (`.pbth-body--fill`: the body stops being
  the scroller and becomes a flex column, the lens takes `flex: 1; min-height: 0`). Belt and braces:
  add `min-width: 0` to the flex child so a future auto-height regression cannot overlap anything.
- **W21 NEVER let an embedded child write HOST state during its mount. (Cost: 591 junk records on the
  live database in ~90 seconds, P1a.)** `PbAttendanceFlow.load()` ended with
  `props.onChanged(...)`, and the hub's handler refreshed its own `useState` summary. `load()` is
  awaited inside `onWillStart`, i.e. **during the host's render fiber** — so the callback invalidated
  that fiber, OWL restarted the render, the child remounted, `onWillStart` ran again, and the loop
  never terminated. The symptom is deceptive: **no console error, no crash**, the surface simply
  freezes — state writes land (localStorage showed the new lens) while the DOM never repaints, and
  every other component on the page keeps updating normally because only the host's fiber is stuck.
  Worse, the child's mount also *did work*: it created a correction record per iteration.
  Rules:
  1. a host→child callback fired from `onWillStart` / `onWillUpdateProps` may **read**, never write
     host state. Fire "something changed" hooks from EVENT HANDLERS only (click, save, commit);
  2. any mount-time write is idempotent or it does not belong in a mount — the facade's
     `create_correction` gained `reuse_draft`, which reopens the day's existing DRAFT instead of
     minting another;
  3. when a cockpit "stops responding" with a clean console, suspect a pending fiber before
     suspecting the event handler — check whether state writes are landing while the DOM is frozen;
  4. after any live UI test that can WRITE, count the rows. `pb_hr_workforce`'s own weekgrid header
     already warned about this class of bug ("no parent-state mutation during child mount → fetch
     loop"); P1a proved it applies to callbacks too, not just direct `setState`.
  **W21.1 — the same day, a second bite: a KEYED child's `onWillStart` can still run twice.** With the
  loop fixed, the drawer's "File correction" hand-off *still* produced two drafts, 69 ms apart. OWL
  **restarts an in-flight mount whenever the parent re-renders**, and the hub's handler legitimately
  re-rendered three times right after the click (`setLens`, `closePerson`, then the ctx `onChange`
  fan-out). A stable `t-key` does not save you: the mount had not completed, so it was discarded and
  re-run. Both `create_correction` calls were therefore in flight simultaneously, in separate
  read-committed transactions — so the server-side `reuse_draft` guard could not see the other row
  either. **A uniqueness guard cannot fix a concurrency problem.** The rule is absolute: *mount hooks
  READ, event handlers WRITE.* The hub now creates (or reuses) the correction in its click handler
  and hands the lens an `{correction_id}` to open; the lens's mount does a pure `get_correction`,
  which is safe to run any number of times. A `filing` flag guards the double-click.
- **W22 An XML comment may not contain a double hyphen — and OWL template files are XML.**
  `<!-- ------------- board ------------- -->` is not a comment, it is a parse error
  (`Double hyphen within comment`), and it takes the WHOLE template file down: every
  `t-name` in it silently fails to register, so the cockpit dies at mount with
  "Missing template", pointing at a component that is perfectly fine. Odoo's own
  templates use `=` rules for exactly this reason. Use `<!-- ==== section ==== -->`.
  Cheap gate: `xmllint --noout` every `.xml` you touched before committing — it also
  catches unescaped `&` and `<` in a `t-esc` default, which fail the same way.
- **W23 One `class` attribute per element, and nothing between a `t-if` and its `t-else`.**
  Two P1b near-misses, both silent:
  1. `t-att-class` and `t-attf-class` both compile to the SAME `class` attribute. An
     element carrying both gets whichever the compiler wrote last — so the tone class
     or the `is-on` class survives, never reliably both. Pick one: a static `class` +
     `t-att-class="{ 'x': cond }"` is a documented, safe pair (precedent:
     `time_hub.xml` `.pbth-body`); a `t-attf-class` that interpolates the condition
     itself (`{{ cond ? 'is-on' : '' }}`) is the safe way to combine a computed tone
     with a state class.
  2. `t-else` binds to the IMMEDIATELY PRECEDING sibling. An XML comment between the
     branches breaks the pairing, and the failure is a template compile error at
     runtime, not at `-u`. When a branch deserves a comment, put the comment INSIDE
     the branch or use an explicit `t-if` for the second one.
- **W24 The exception engine only sees `state = 'published'` shifts — Today sees
  `published` AND `completed`, on purpose.** `pb.attendance.exception.engine._get_exceptions`
  and `pb.attendance.flow._cohort` both filter `('state', '=', 'published')`, while
  `pb.time.hub` and `pb.today` use `_PLANNED_STATES = ('published', 'completed')`. That
  is not drift, it is two different questions: "what did we commit to and has it gone
  wrong" versus "who is working today". But it has a consequence worth knowing before
  you interpret any live screen — **pb_demo completes every past punched shift**
  (`demo_workforce.py`: `action_publish()` then `action_complete()` when not future and
  not absent), so on the demo world the Exceptions queue for a settled day is driven
  almost entirely by the ABSENT variant, whose shift stays `published`. A Today row
  that is late will therefore often have no matching exception row, and that is
  correct. What must never differ is the GRACE (§2.5): both resolve it through
  `pb.attendance.rule._grace_for_company`, and `pb_today/tests/test_today.py
  ::test_late_agrees_with_the_exception_engine` pins them together on a published shift.
- **W25 A polled surface should not be able to write.** P1a's 591 junk corrections came
  from a mount-time write on a surface nobody was even clicking. P1b's Today board is
  polled every 30 s and clicked reflexively, so `pb.today` was built with no `create`,
  `write` or `unlink` in it at all, and a static test asserts that. Its "File
  correction" door NAVIGATES — it pins the person on `wf_context` and hands over to the
  Exceptions lens, which mints the record one click later on a row the officer has
  actually looked at. Rule: for any surface with an auto-refresh, make the read-only
  property explicit and test it, rather than relying on every future contributor
  remembering W21. A door that only navigates cannot generate rows.
- **W26 The hub deep-link protocol: `pb_lens` + `pb_focus`.** A cockpit handing over to
  a hub passes intent through `doAction(..., { additionalContext: {...} })`, and the hub
  reads it ONCE in `setup()` from `props.action.context`:
  `pb_lens` names the lens to open; `pb_focus: "queue"` says *the pinned person is a
  FILTER, not a drawer to open*. Without the second one the hand-off is worse than
  useless: `wf_context.personId` drives the person drawer, so filtering the queue would
  also pop a panel on top of the very queue the officer was just sent to read. Any host
  whose drawer is context-driven needs this opt-out, and it must be cleared by the next
  real person-door click (`openPerson`) so the drawer is not stuck shut.
  Corollary: a surface that pins a person but shows NO person chip (Today) must not
  auto-open its drawer on arrival either — a pre-existing pin is context, not a request.
- **W27 Unfreeze a `noupdate` record in a PRE-migrate, not a post-migrate. (Found live,
  P1b — the third bite of W13.1 and the one that finally explains the pattern.)**
  An upgrade runs `pre-migrate → DATA FILES LOAD → post-migrate`. P0 and P1a both cleared
  the stored `ir_model_data.noupdate` flag in a POST-migrate and then hand-applied the one
  field they were changing, which worked only because each was changing exactly one field.
  P1b changed TWO on the same record (sequence 37→60 **and** the label "Business Trips" →
  "Trips") and the live database came back:
  `Business Trips | 60 | active` — the sequence moved because the script wrote it, the
  label did not, because the loader had skipped the file milliseconds earlier while the
  flag was still set. **EXIT 0, no error, no warning**, and because the flag is left clear
  a *second* upgrade silently repairs it — so the bug only exists on the first deploy to
  any given database, which is precisely where nobody looks for it.
  Rule: clear the flag in `migrations/<version>/pre-migrate.py`. Then the data file
  applies EVERY field it declares, in the same upgrade, and there is no hand-written
  `UPDATE` to keep in sync with the XML. Keep hand-applied values only for things the data
  file cannot express (a value that must not be overwritten if an admin changed it).
  Corollary — this is *why* W13.1 insists on asserting the DB after `-u`: the repo, the
  log and the migration were all "correct", and only reading `pb_sidebar_item.name` back
  showed the rail still had the old word on it.
- **W28 A rail label is unique across the WHOLE sidebar, not just its section.** P1b's
  handover specified renaming "My Team" → "Approvals". `pb_sidebar.item_approvals` already
  carried exactly that label in the OVERVIEW section — the payroll payslip-run approval
  cockpit (`action_tag` `pb_approval`, `match_models` `hr.payslip.run`), gated to the
  payroll approver tiers — so the literal rename would have put two identically-named
  entries on one rail, pointing at two different cockpits in two different domains. W8
  makes *sequences* unique within a section; nothing was checking LABELS, and a user reads
  labels, not sequences. Shipped as "Team Approvals". Before renaming any sidebar item,
  grep the live `pb_sidebar_item` table for the label you intend to use, across every
  section — the collision is invisible in the data file you are editing, because the twin
  lives in another module.
- **W29 A required field can make a whole feature UNREACHABLE, and the surface will
  still render it.** (Found in P2 while porting the roster.) `hr.shift.planning.employee_id`
  is `required=True` (`pb_hr_workforce/models/shift_planning.py`:17-19) and nothing in the
  dependency tree relaxes it. The legacy grid nevertheless shipped an "Open Shifts" row
  built from `shifts.filtered(lambda s: not s.employee_id)` — a predicate the ORM
  guarantees is never true — with a summary metric counting it, and a `+` in every cell
  wired to `quick_create_shift(false, …)`, i.e. a door into a create the ORM must refuse.
  It looked like a feature for years because an empty row looks exactly like a row with
  nothing scheduled in it.
  Rule: when you port a surface, check every "optional" reference against the FIELD
  DEFINITION, not against the UI that reads it. And a door that can only ever produce an
  error is worse than no door (W5) — P2 keeps the row for the day P4 relaxes the field,
  renders it only when the payload really has open shifts, and does not make it a create
  door. Same class of trap: a `t-if` on a value the server can never send.
- **W30 A PostgreSQL `UNIQUE` does not stop duplicate NULLs, so a scope-with-an-optional-
  dimension needs a Python constraint too.** The natural key for `pb.schedule.budget` is
  `unique(company_id, department_id, week_start)` where `department_id` empty means
  "company-wide". Under a plain UNIQUE index NULLs are DISTINCT, so `(1, NULL, 2026-03-02)`
  can be inserted any number of times and the constraint reports nothing — the one row
  that is most likely to be created twice (the company-wide default) is the one row it
  cannot protect. Keep the SQL constraint (it is the cheap guard for the non-NULL rows)
  **and** add an `@api.constrains` covering the NULL case, with a test that inserts the
  duplicate. `NULLS NOT DISTINCT` exists in PG15+ but is not expressible through Odoo's
  `_sql_constraints`, and silently does nothing on an older server.
- **W31 Gate a manager-only table on the MODEL, not only in the facade that edits it.**
  Both P2 config models (`pb.schedule.budget`, `hr.shift.coverage.requirement`) are edited
  through `hr.shift.planning.grid`, which is gated at ATTENDANCE OFFICER — one tier below
  the manager tier that may change money and demand figures. Putting the manager check in
  the facade helper would mean every future helper on that facade is a new place to forget
  it. The check lives in `create`/`write`/`unlink` on the model (alongside the
  `ir.model.access` rows, which cover generic ORM callers), so the facade physically
  cannot be a softer door — and each model ships a test that calls the facade AS an
  officer and asserts the AccessError, while its READ door still works.
- **W33 Two Odoo-19 API breakages that fail SILENTLY or CATASTROPHICALLY, both hit in one
  P2 deploy.** (Merged into the ledger as W32 in code comments; numbered W33 here after the
  renumber.)
  1. **`_sql_constraints = [...]` is no longer supported.** Odoo 19 logs
     `Model attribute '_sql_constraints' is no longer supported, please define
     models.Constraint on the model` once per model — a WARNING among hundreds of other
     warnings on this codebase — and then ignores the list. The constraint simply does not
     exist in PostgreSQL, and every test that only checks the Python `@api.constrains`
     still passes. Use `_name = models.Constraint('unique(...)', 'message')`
     (core precedent: `odoo/addons/base/models/res_currency.py`:49). Verify with
     `SELECT indexname FROM pg_indexes WHERE tablename = '…'` after the upgrade; a
     model-level assertion is not proof.
  2. **An invalid attribute in a view aborts the WHOLE module upgrade — and the modules
     that loaded BEFORE it are already committed.** A `<group expand="0" string="Group By">`
     in a search view (valid for years, rejected by Odoo 19's
     `odoo/addons/base/rng/search_view.rng` + `common.rng`) produced four
     `odoo.tools.view_validation` WARNINGs, then `Failed to load registry` /
     `Failed to initialize database`, and the run exited with the module still at its OLD
     `latest_version`. Because `load_module_graph` does `module.write({'state':'installed',
     'latest_version': ver})` **and `cr.commit()` PER MODULE**, half the deploy was live and
     half was not: `pb_sidebar` had shipped its new rail while `pb_schedule`'s new tables
     did not exist. Rules: copy view syntax from a CORE Odoo 19 file rather than from
     memory; after any deploy assert the DB `latest_version` of EVERY module you bumped,
     not just the one you were watching; and treat "no `Starting post tests` line in the
     log" as a failed run, because a registry that never loaded never reaches the tests.
