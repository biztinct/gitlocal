# Workforce Redesign — Program Conventions & Gotcha Ledger (W-rules)

Program: rebuild the WORKFORCE section as **Option B "Mission Control", staged through Option A's
consolidation, powered by Option C's engine** — per the approved dossier
`docs/WORKFORCE_REDESIGN_OPTIONS.html` (mockups A/B/C + P0–P4 roadmap live there).

Every phase handover in `docs/handovers/WORKFORCE_P*.md` references this file. **Opus: when you hit a
new gotcha or make a binding convention decision, append a numbered W-rule here in the same commit.**
P4 closed the ledger at **W54**; **P6 reopened it** (demo-world sync was a post-P4 closure item) and
takes it to **W61**. 60 rules, not 61: there is no W32 — see the note below.
Numbering note: **there is no W32** (it was folded into W33 during a renumber), and the P3a handover
referred to "W-rules through W34" while the file in fact stopped at W33 — P3a opens the W34 slot, so
the numbering and the reference agree again from here on.
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
- **W34 A `position: sticky` header inside an `overflow-x: auto` wrapper never sticks — and
  the bug is invisible because it looks like "the header scrolled away".** (Found in P3a
  while proving the three root-scrollers, and the reason that proof is worth doing at all.)
  A sticky element resolves against its nearest SCROLLPORT, and per CSS Overflow a box with
  `overflow-x: auto` computes `overflow-y` to `auto` as well — so it *is* a scroll container
  even when it only ever scrolls sideways. `pb_timeoff`'s balance table puts
  `thead th { position: sticky; top: 0 }` inside `.baltable-wrap { overflow-x: auto }`, so
  its scrollport is that wrapper, which is exactly as tall as its content and never scrolls
  vertically. The header has therefore been inert since it was written, standalone and
  embedded alike (verified identical on both mounts, live). Two consequences:
  1. when you move a cockpit's scrollport for W20, the stickies that DO move are the ones
     whose scrollport is the root — check each one individually rather than assuming;
  2. `overflow-x: auto` on a table wrapper is not a free horizontal scroll. If a sticky
     header has to work, the wrapper needs a bounded height and `overflow: auto`, or the
     sticky belongs on an element outside it.
  P3a left pb_timeoff's alone deliberately: it behaves identically to before, and changing
  it is a cockpit fix, not a shell fix.
- **W35 A typed OPTIONAL OWL prop still rejects `null`.** `action: { type: Object, optional:
  true }` means "may be absent", not "may be null" — dev-mode validation throws the moment
  the prop is present with a null value, which is what a host does naturally when it models
  "no arrival payload yet" as `state.arrival = null`. Pass `{}` instead (precedent:
  `pb_time_hub`'s `seed: {}`), and keep the identity stable so the child is not recreated on
  every render. Corollary for the arrival protocol: because `PbTimeHub._arrival()` reads
  `props.action.context`, a HOST can deep-link an embedded hub by handing it a synthetic
  `{ context: {...} }` — W26's protocol works unchanged through a prop, so an embedding
  phase never needs to invent a second one.
- **W36 A shared kit component that a HOST re-configures at runtime needs
  `onWillUpdateProps`, and a shared component that reads a SERVICE needs an effect.** Two
  holes in `<WfContextBar/>` that only Mission Control could expose, both of which were also
  live bugs in the Time hub:
  1. departments were fetched in `onWillStart` only. A host that turns the department
     segment ON after mount (the shell does, on every lens switch) gets a permanently empty
     `<select>` — no error, and it looks like a data problem.
  2. `state.personLabel` was written ONLY by `pickPerson`. Every other person door — a lens
     avatar calling `openPerson`, a deep link, a restored pin — writes `wf_context.personId`
     directly, so the chip rendered with no name at all. The fix is a `useEffect` on
     `ctx.personId`; effects run AFTER the patch, so resolving the name there is a read, not
     a write inside somebody else's render fiber (W21).
  Rule: any kit component whose props are a per-context MAP must handle those props
  changing, and any kit component that mirrors service state must follow the service, not
  just its own handlers.
- **W37 The shell may not create a stacking context anywhere a lens can mount.** Cockpit
  modals are `position: fixed; z-index: 1050` and expect the ROOT stacking context. A
  z-index (or transform/filter/opacity) on the canvas or the lens box traps them, and 1050
  then means nothing: the modal renders UNDER the workspace's own command bar. Mission
  Control therefore stacks only its chrome — command bar 2, rail 1 — and
  `pb_mission/tests/test_static.py` asserts that `.pbms-canvas` and `.pbms-lens` carry no
  z-index at all. The ceiling is still 20, because below 1920px the biz sidebar is a 60px
  absolute hover-overlay at z-25 that must paint OVER the workspace (§2). Proved live by
  hit-testing `elementFromPoint` at the command bar's centre: with a lens modal open it
  returns the modal's scrim; with the rail expanded it returns the sidebar.
- **W38 W28's label-uniqueness rule is about the `pb.sidebar.item` TABLE, not about every
  rail-shaped thing on screen.** P3a's shell has its own lens rail, and its Approvals lens is
  labelled plainly "Approvals" while the sidebar record it replaced stays "Team Approvals" —
  because the collision W28 was written about (`pb_sidebar.item_approvals`, the payroll
  payslip-run cockpit) lives in that table and cannot appear inside a Workforce workspace.
  Applying W28 to in-surface navigation would import a disambiguation the user cannot see the
  reason for. Rule: grep the table before renaming a RECORD; judge an in-surface label by
  what else is visible in that surface.
- **W39 `margin: 0 auto` cancels a flex item's stretch, so a centred `max-width` wrap sizes
  to its CAP instead of to its host — and it only shows up on the screens nobody develops
  on.** (Found in P3a's self-review, at 1440×900, after the surface had already passed every
  gate at 1920.) `pb_timeoff`'s `.pbto-wrap` and `pb_ot_desk`'s `.pbot-wrap` are the classic
  readable-column recipe: `max-width: 1360px; margin: 0 auto`. The moment W20 promotes one of
  them to the embedded SCROLLPORT it becomes a flex item, and an auto margin on the cross
  axis suppresses `align-items: stretch` — so instead of filling a 1304px lens it laid itself
  out at its 1360px cap and hung 56px past the canvas. `min-width: 0` does not help: the box
  is not being squeezed by min-content, it is being sized by max-width. Nothing errored and
  the console was clean; at 1920 the lens is 1588px wide and the bug is literally invisible.
  Rules:
  1. when you turn an existing centred wrap into a flex scrollport, add `width: 100%` —
     `max-width` then clamps on wide screens and `margin: 0 auto` still centres;
  2. W20's belt and braces are `min-height: 0` + `min-width: 0` + **`width: 100%`** whenever
     the child carries a max-width;
  3. measure every embedded lens at the RAIL-OVERLAY width (1440), not only at 1920 —
     the shell is narrower there by the 60px rail AND by whatever the phase adds next, so
     this class of bug surfaces on the laptop and never on the monitor.
  Gated by `pb_wf_kit/tests/test_p3a_embedding.py::test_the_root_scrollers_move_their_
  scrollport_inside`.
- **W40 A `catch` that DISABLES a control turns a one-line API change into a missing feature,
  and nobody will ever see the error.** (Found in P3a, live, on a bug that had been shipping
  since P0.) `WfContextBar._search()` called
  `name_search(..., { name, args: [], operator, limit })`. Odoo 19 renamed that second
  parameter — the signature is `BaseModel.name_search(name, domain, operator, limit)` — so
  every keystroke raised `TypeError: name_search() got an unexpected keyword argument
  'args'`. The handler swallowed it and set `personDenied = true`, and the template hides the
  whole segment when that flag is set. Net effect: the person search silently DELETED itself
  on first use, in every Workforce cockpit, for three phases. No console error (the catch ate
  it), no toast, no empty dropdown to be suspicious about — the control was simply not on the
  page, which reads as "this build doesn't have that" rather than as a defect. It survived
  P0-P2 because the segment is one of several and nobody types in it during a screenshot pass.
  Rules:
  1. a `catch` may narrow a feature only for the reason it was written for. Degrading on
     "the persona cannot read hr.employee" means testing for `AccessError`; everything else
     must `console.warn` and leave the control alone;
  2. never `catch {}` without binding the error — the bare form makes the failure
     unobservable by construction;
  3. when you make an existing control the HEADLINE of a new surface, exercise it end to end
     live (type, pick, confirm the state landed) rather than checking that it renders. P3a's
     T4-T14 all passed on a search that could not work.
  Gated by `pb_wf_kit/tests/test_p3a_embedding.py::test_the_person_typeahead_calls_odoo_19s_
  name_search`. Related live fact worth knowing: this database has no `unaccent`, so
  "Bui Anh" matches nothing while "Bùi Anh" matches — P3b's palette needs an answer for that.
- **W41 An always-mounted, POLLED surface may carry write buttons — but only if
  its mount hooks and its poll are provably reads, and the gate has to be on
  `setup()`, not on the writers.** W25 concluded from P1a's 591 junk corrections
  that "a polled surface should not be able to write", and built `pb.today` with
  no `create`/`write`/`unlink` at all. P3b's dock breaks that shape on purpose:
  it is mounted beside every lens, polls every 60 s, and its whole reason to
  exist is a check and a cross on each card. What makes that safe is not care,
  it is where the gate points. `get_team_data` has no write path in it; every
  mutation goes through `pb.team.act`, which is reachable only from a
  `t-on-click`; and `pb_mission/tests/test_static.py::test_the_dock_never_
  writes_from_a_lifecycle_hook` asserts that neither `this.approve(`,
  `this.confirmRefuse(` nor the string `"act"` appears anywhere inside
  `setup()` — which is where every lifecycle hook AND the interval are
  registered. Gating the writer methods would have been the useless version of
  this test: they are supposed to exist. The thing that must not exist is a path
  from a hook to one of them. Corollary: a poll that repaints a list the user is
  mid-interaction with must be `quiet` — it may not clear an optimistic removal
  set or a half-typed refusal note (the dock's `load(quiet)`).
- **W42 Never make a field REQUIRED unless the thing behind it actually stores
  the value. (Caught in P3b's own live run, on the first version of the dock.)**
  The dock's refuse box demanded a reason for every source. Only TWO of the four
  keep one: `pb.business.trip.action_refuse_chain` and
  `hr.attendance.correction.action_refuse` take a `note` parameter and record
  it, and there it is the only account the employee will ever get of why.
  `hr.overtime.request.action_refuse` and `hr.leave.action_refuse` take no note
  at all — the facade's own `_ACT_MAP` says so with `'note': False` — so
  everything typed for them was discarded on the way in. A required field whose
  value is thrown away is a control that lies about what it does, and it is
  exactly the kind of lie nobody discovers, because the refusal still works.
  The fix is to let the SERVER answer per item: `takes_note` on each queue row,
  derived from the same whitelist `act()` dispatches on, so the requirement and
  the recording can never drift apart. Two corollaries:
  1. where the note IS kept, enforce it by DISABLING the confirm button, not by
     validating on submit — the officer must never compose a refusal that is
     then rejected;
  2. where it is not, say so in the placeholder rather than silently dropping
     the field ("Reason (optional) — this request type does not store it").
  General form: when a surface is stricter than the model beneath it, the extra
  strictness has to be derived from the model, not asserted over it.
- **W43 Put a floating panel in the OVERLAY when the alternative is winning a
  z-index argument.** The ⌘K palette has to paint above a lens's
  `position: fixed` modal at 1050. Any implementation inside the workspace would
  have to stack shell chrome above 1050, which is precisely the fight W37 exists
  to prevent — and the 60px biz-rail hover overlay at 25 would lose it too. The
  Odoo overlay service (`useService("overlay").add(Component, props, {onRemove})`)
  mounts into `.o-overlay-container`, a sibling of the whole action host, so the
  palette wins by LOCATION and pb_mission.scss does not change by one line for
  the feature. Two consequences worth writing down:
  1. the overlaid component renders OUTSIDE every `.pbim` root, so its `--pbim-*`
     custom properties do not resolve and the `var()` FALLBACK is what paints
     (W14 again, this time by construction rather than by accident) — the kit's
     `.wfcp-*` block is written with every fallback correct for that reason;
  2. `overlay.add()` returns its own `remove()`. Keep that handle and null it in
     `onRemove`, or the hotkey that opens the panel will happily open a second
     one on top of the first.
  Related geometry rule, hit on the dock's hovercard: a panel that must escape a
  scrolling ancestor is `position: fixed` off a MEASURED origin
  (`getBoundingClientRect` in the event handler), not `position: absolute` — an
  `overflow-y: auto` box clips horizontally too (W34), so an absolute hovercard
  is sliced off at its scroller's edge and looks like a rendering bug. And make
  such a card `pointer-events: none`: if the pointer can land on it, the gap
  between it and its trigger makes it flicker.
- **W44 A host→lens instruction is carried by a NONCE the lens tracks, never by
  a "consumed" callback.** P3b's `pb_cmd` protocol (extending W26's `pb_lens` /
  `pb_focus`): the shell holds `state.cmd = { name, nonce }` and passes it as a
  prop; each lens keeps `this._cmdNonce` and runs the instruction when the
  incoming nonce differs. The obvious alternative — the lens calling
  `props.onCmdConsumed()` — is a CHILD WRITING HOST STATE, and it would be
  called from `onWillStart`/`onWillUpdateProps` because that is where the
  instruction arrives: exactly W21/W21.1, which cost P1a 591 records and then
  bit a second time on a keyed child. With a nonce the host never has to be
  told, and the lens may re-read the prop as many times as OWL restarts its
  mount. Three rails that come with it:
  1. the prop is TYPED optional with a NON-NULL default (`{ name: "", nonce: 0 }`)
     — a typed optional prop still rejects `null` (W35);
  2. the instruction is consumed AFTER the lens's own load when it needs loaded
     data (a quick-create needs a day and an employee; the Bonus door needs
     `can_view_bonus`), i.e. at the end of `onWillStart`, not at its start;
  3. a lens ignoring an unknown command is CORRECT behaviour, and an entry is
     added to the palette registry only where the target affordance ALREADY
     EXISTS — a verb that lands on nothing is W29's "door that can only ever
     produce an error", and a static gate walks the registry checking each
     `cmd.name === "…"` really is implemented by the lens it names.
  Registry as of P3b: `schedule` → quick_create · copy_week · set_budget;
  `today` → map; `timeoff` → apply; `overtime` → bonus. The Time hub's two verbs
  (import, exceptions) ride W26's arrival protocol instead, because it already
  implements it — one protocol per target, chosen by what the target has.
- **W45 A capped read must carry the TRUE total beside the capped list, or the
  surface will report a shrinking backlog as the real one grows.** `pb.team`'s
  four queue searches were unbounded; P3b caps each SOURCE at 20 (per source, so
  a thousand pending leaves cannot starve three OT requests out of the list) and
  therefore had to add `queues.counts` as a `search_count` and
  `queues.has_more[source]`. The dock's header reads that total, never
  `items.length` — a gate asserts it — and the "+N more" link is computed from
  the difference. Same rule for `total`: it is emitted ALWAYS, 0 included,
  because it used to live on the `has_team` branch only and a manager with no
  reports would have rendered "Needs you · undefined". A missing key is not a
  zero, and JSON will not tell you which one you got.
- **W46 A "display" date field needs a machine twin, produced beside it.**
  `pb.team`'s `when` is built with `%d %b`: locale-shaped, year-less and
  un-sortable, and a client that wants to sort or age a queue item has nothing
  to parse. P3b adds `when_iso` next to it, from the same field in the same
  expression, so the two cannot drift into describing different days. The helper
  collapses a Date and a Datetime to the same `YYYY-MM-DD` and takes the date
  part as stored rather than converting, because the display twin does exactly
  the same thing.
- **W47 A wider READ scope must be gated on the model side AND advertised to the
  client, and it must not widen the WRITE by one inch.** `get_team_data(scope=
  'org')` returns every pending item in the active companies. Three separate
  things make that safe: `_require_org_approver()` raises for anyone who is not
  an HR manager or a payroll manager (the two MANAGER tiers only — an HR *user*
  is not a company-wide approver, even though `_HR_GROUPS` contains them);
  `can_org` in the payload tells the dock whether to render the Team/Org toggle
  at all, so an offer the server would refuse is never made; and `act()` is
  untouched — still whitelisted, still the real user through each model's own
  gated method, still scope-checked (W12). Deliberate design detail: both org
  groups are INSIDE `_HR_GROUPS`, so the read gate and the mutation gate cannot
  drift apart into "sees it, cannot act on it". Second rule that came with it:
  a scope that multiplies the population must also drop the per-population
  extras — org scope returns the BLANK metrics/roster shapes rather than walking
  4 500 employees through the OT-ceiling, shift-compliance and exception-engine
  builders four times a minute. Blank SHAPE, not a missing key.
- **W48 New code never reads the shift model's STORED compliance-status field —
  derive live.** (P4 §1, promoted from a per-phase non-goal to a standing rule.)
  `hr.shift.planning`'s compliance status is a STORED compute over `now()` with
  no cron to re-run it, and its `actual_check_in` / `actual_check_out` inputs are
  never written by any production code path — only by seeders. So it is stale by
  construction, and it is stale in the most dangerous way: it holds a plausible
  value. P4's Close board decides which weeks reach payroll, and deciding that
  from a field nobody maintains would be confidently wrong rather than obviously
  broken. The proven shape is live derivation (`pb_today.py`:295-317 for
  lateness; `pb.close._classify` for the whole week), from batched reads folded
  in Python. Existing consumers (`pb.team`'s metrics, the exception engine's
  late/early branch) are NOT being rewritten — this rule is about new code.
  Gated by `pb_mission/tests/test_static.py::test_new_code_never_reads_
  compliance_status`, a plain substring walk over `pb_close` and the Close lens.
  **Corollary about grep gates, learned the expensive way twice in this program:**
  a word-shaped gate fails on the DOCUMENTATION that explains the rule. P3b's
  ledger records a gate that forbade the string "Chart.js" and duly failed on the
  docstring saying the charts had been dropped. P4 therefore does not spell that
  field's name anywhere in `pb_close` — including in prose — and says so where a
  reader would otherwise wonder why the docs are vague.
- **W49 A bypass context key is honoured ONLY under `env.su`.** `wf_lock_bypass`
  opens every lock guard in `pb_close`, which is exactly the power a forged
  context would want. A bare `{'wf_lock_bypass': 1}` is trivially reachable over
  `call_kw` (C18.24, the same reasoning behind the `object()` sentinels in
  `pb_attendance_flow` and `hr.overtime.request`); `env.su` is not reachable from
  a JSON-RPC session at all. The PAIR means "a server-side process that has
  already crossed a real permission boundary", which is the only caller that
  should be able to rewrite a closed week: `pb_demo`'s regenerator (the key lives
  in its `_GEN_CTX`, so a lock left behind by a demo of the Close ritual cannot
  defeat a regen) and emergency shell surgery. Two consequences worth stating:
  `env.su` ALONE must not open the guard — the correction workflow's single
  writer `_apply()` runs sudo'd and must still be stopped — and `_is_admin()`
  must not either, because it opens plenty of other doors in this codebase
  deliberately. Tested from both sides: bypass works under su,
  bypass-without-su does nothing.
- **W50 A lock protects the AUDIT SUBSTRATE, not the money — say which, or the
  guard will be built in the wrong place.** Nothing on the payroll path reads
  `hr.attendance`: the `_get_formula_input_values` chain reads
  `hr.overtime.request` and trips, and OT hours are grid-entered by design. A
  punch could be rewritten a year after the fact without moving one payslip
  figure. What a locked day protects is the EVIDENCE behind the decisions the
  week produced — the OT approved because somebody really was there until 20:00,
  the correction a manager signed off, the variance an officer waived. Rewriting
  that after the week went to payroll turns a defensible payroll into an
  undefensible one, silently, because none of the numbers change. The one guard
  in P4 that IS about money is the overtime one (`approved_hours` feeds the OT
  bridge, `hr_payslip.py`:27), and it exists for the opposite reason: a closed
  week must not be able to GROW new approved overtime. Stating which of the two a
  guard is for tells you where it belongs — the punch guard is on the ORM (six
  writers reach that table; guarding each is six places to forget), the OT guard
  is on the three state transitions.
- **W51 The lock, the board and the exception engine key a punch by the
  EMPLOYEE-LOCAL day; the Week Grid and `get_person_week` key it by
  `check_in.date()`. Know which you are in.** In VN (UTC+7) an 05:58 local punch
  is stored on the PREVIOUS UTC day, so UTC keying invents exactly the phantom
  missing punch C18.49 forbids — which is why `pb.attendance.exception.engine`
  already localizes (review G-M5) and why `pb.wf.lock` and `pb.close` follow it.
  The consequence that matters is not correctness but AGREEMENT: a lock chip and
  the board offering to set it must mean the same Tuesday, or an officer locks
  Tuesday and watches Monday's row go read-only. The pre-existing UTC keying in
  the grid is left alone (it is lossless for the day shifts it was built for and
  changing it is a cockpit fix, not an engine one), but any NEW surface that
  compares punches against shifts, leaves, trips or locks localizes first.
- **W52 An "unlock" that DELETES the lock deletes its own audit trail.** P4's
  handover specified `unlink = unlock` and, in the same paragraph, that the
  reason be `message_post`-ed and its test read the chatter back. Those cannot
  both be true: a `mail.thread` record takes its messages with it. `pb.wf.lock`
  therefore keeps the grain the handover asked for — `unique(company_id, date)`,
  and only a row in state `locked` locks anything — but reopening FLIPS the
  state. One row per day then accumulates that day's whole history in one place:
  locked by A, reopened by B because C, re-locked by D. `unlink()` still exists
  and is still manager-gated, for genuine surgery; it is simply not the door.
  General form: before modelling a state change as a deletion, ask what the
  record was the only copy of.
- **W53 A gated public facade method needs an ungated private twin the moment a
  SECOND gated caller needs its arithmetic.** `hr.attendance.weekentry.
  get_ot_ceilings` is `_require_officer`-gated, i.e. the ATTENDANCE tier only.
  P4's clean-overtime batch needed the same figures inside `pb.team`, which is
  read by HR and payroll MANAGERS as well — so calling the public door would have
  raised AccessError for half the dock's personas, been swallowed by the
  surrounding try/except, and made the whole feature silently not appear. That is
  W40's exact failure shape, and W40 cost this program its person search for
  three phases. The fix is not to widen the gate and not to copy the arithmetic
  (two places to drift): extract the body into an underscore-private method,
  which is not reachable over `call_kw` (C18.32), and leave the public method as
  gate + delegate. Each caller then gates itself with the question ITS surface
  actually asks. Same shape as `pb.attendance.exception.engine._get_exceptions`,
  which has been private for this reason since Phase G.
- **W54 A tolerance that accumulates over a period surfaces as ONE row for the
  period, not one row per day.** P4 §3.3 defines a clean employee-day as inside
  the per-punch tolerance AND inside the weekly one, which reads as "if the week
  busts, every day of it is flagged". Implemented literally, a person eight
  minutes short on each of five days — inside the per-punch tolerance every
  single time — produces five identical rows a manager must waive one by one,
  burying the days that genuinely need attention, and on a 200-person department
  it produces a thousand. The week-level miss is ONE FACT ABOUT ONE PERSON, so
  `pb.close` emits a single `week_variance` row carried on that person's worst
  day, reviewable like any other flag. General form: a rollup threshold produces
  a rollup row. Same instinct as the "a rest day is neither clean nor flagged"
  and "an approved leave IS the explanation" rules in the same classifier — every
  one of them is the difference between an instrument and an ignored instrument.
- **W55 A demo world's WALL CLOCK is not in its `resource.calendar`. (Found live in
  P6, and it cost the phase a whole seeding run.)** The demo company's working
  calendar is Odoo's stock "Standard 40 hours/week" and carries
  `tz = Europe/Brussels` — nobody ever set it, because nothing in payroll reads
  it. `pb_demo`'s workforce seeders nevertheless derived their shift hours from
  it (`demo_workforce.py`:71-72), so an "08:00" shift in a company called
  *Payobook Vietnam JSC* was written at 06:00 UTC, i.e. **13:00 in Ho Chi Minh
  City**, and the afternoon template ended at 03:00 the following local morning
  — straight across the midnight W51's surfaces key their days on. The visible
  symptom was worse than the cosmetics and pointed nowhere near the cause: at
  08:56 Vietnamese time the P6 seeder produced `open_today: 0`, because in
  Brussels the working day had not started, so the Today board came out EMPTY
  from the run whose entire purpose was to fill it. Rules: a seeder pins the
  demo world's timezone to its COUNTRY (`_p6_tz` returns `Asia/Ho_Chi_Minh`
  outright, with the reasoning in its docstring), and any test of seeded times
  asserts the LOCAL wall clock, not just that the UTC value is plausible — the
  Brussels rows passed a "punch is before 16:00 UTC" check without trouble.
- **W56 Completing a shift DELETES the exception it raised — so a seeder that
  tidies up the past empties the very queue it exists to fill.** W24 records
  that `pb.attendance.exception.engine._get_exceptions` only reads
  `state = 'published'` shifts, and that pb_demo completes every past punched
  shift. P6 makes the consequence a rule, because the naive shape of "settle
  the past" is to complete every day that has a punch pair: `late` and
  `early_leave` are DERIVED from a published shift's stored compliance status,
  so completing a day that went wrong is indistinguishable from deleting its
  exception, and Time·Exceptions ends up showing absences only. The seeder
  therefore carries an explicit `_COMPLETABLE` whitelist of day flavours
  (on-time, within-grace, long day) and leaves late / early / missing-checkout
  days published on purpose. General form: when a state transition is also a
  filter somewhere else, enumerate what may cross it rather than defaulting.
- **W57 A deliberately OPEN punch costs that employee every LATER punch until it
  is closed.** Core `hr.attendance` refuses a create while the employee's
  previous punch is open ("Cannot create new attendance record for X, the
  employee hasn't checked out since …"). A demo that seeds two or three open
  punches as `missing_checkout` material therefore cannot also clock those
  people in today — the batch create is refused, the row-by-row fallback logs
  three warnings, and the counter says it made something it did not. Two rules
  came out of it: exclude the still-open population from the next day's punch
  plan (the resulting story is the CORRECT one — a person whose Friday punch was
  never closed is an open exception, not somebody who quietly started a new
  day), and **count what LANDED, never what was intended** — `open_today` is now
  computed from the created recordset, so a refusal can never be reported as a
  success.
- **W58 A rail gate is a FLOOR, not an inventory — never assert `groups_id` by
  equality.** Four sidebar tests asserted `item.groups_id.ids == [the one
  group]`, and all four fail on any database where pb_demo is installed:
  `pb_demo._pb_demo_rewire` (`data/pb_demo_sidebar_access.xml`, a `<function>`
  that re-runs on every upgrade) deliberately joins "Payobook Demo User" onto
  every gated rail item, so the live apex database has two ids where the test
  demanded one. The failure reports which MODULES are installed, not whether the
  gate survived — and W8's actual requirement is only that the rail never
  advertise a cockpit the facade would refuse. `assertIn`, matching the
  pb_wf_kit precedent that already got this right
  (`test_p0.py::test_payroll_report_keeps_its_payroll_gate`). Fixed in P6 for
  pb_today (×2), pb_time_hub and pb_schedule.
- **W59 An idempotency test asserts the WORLD, not the run's creation counts.**
  P6's first version of "it seeded something" checked
  `counts['punches'] > 0` — true on a virgin database and false on every
  correct rerun, which is precisely the state the live demo is in and precisely
  what the neighbouring idempotency test demands. The two assertions were
  therefore in direct contradiction, and the one that failed was the one that
  was wrong. A seeder has two separate contracts and they need two separate
  shapes: *this run created nothing* (counts, on a rerun) and *the window is
  full* (`search_count` over the seeded window, always).
- **W60 Demo ownership is the EMPLOYEE, and that is enough — do not add an
  `is_demo` column to a satellite table.** P6 seeds shifts, punches, overtime,
  leaves, trips and corrections, none of which carry `is_demo`. The instinct to
  add one is wrong twice over: `pb_demo.clean_demo_employees` already unlinks
  every one of those models BY `employee_id` (attendance cascades), and §5's
  safety proof is itself phrased over the employee ("count the rows whose
  employee is NOT a demo employee, before and after"). Adding the column would
  ALTER six tables, one of which is the punch table, to restate a fact the
  employee row already carries. What the seeder owes instead is the *never
  destructive* rule: because it cannot tell a previous run's row from an
  officer's, it treats every existing row on a seeded day as the officer's and
  only ever adds. The two exceptions are stated and bounded — closing an open
  punch on a past day, and completing a settled shift — both of which are what
  an officer would have done anyway.
- **W61 `service odoo-server stop` can leave the old process alive, and it holds
  `ir_ui_view`.** P6 stopped the service, waited 4 s, saw no `odoo-bin` in a
  racy `pgrep`, and launched a detached `odoo-bin shell`. `systemctl is-active`
  said *inactive* while PID 2637869 was still running, and the shell died 80 s
  into its registry load with
  `psycopg2.errors.LockNotAvailable: canceling statement due to lock timeout —
  while updating tuple in relation "ir_ui_view"`. Nothing was written; the run
  simply cost eight minutes and looked like a code failure. The check is
  `ps -eo pid,cmd | grep "[o]doo-bin"` (the bracket keeps grep from matching its
  own command line, which is what made the first check lie), repeated until it
  is empty, and the fix is `sudo kill <PID>` — BY PID, never `pkill -f odoo-bin`.
