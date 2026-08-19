# Workforce Redesign — Program Conventions & Gotcha Ledger (W-rules)

Program: rebuild the WORKFORCE section as **Option B "Mission Control", staged through Option A's
consolidation, powered by Option C's engine** — per the approved dossier
`docs/WORKFORCE_REDESIGN_OPTIONS.html` (mockups A/B/C + P0–P4 roadmap live there).

Every phase handover in `docs/handovers/WORKFORCE_P*.md` references this file. **Opus: when you hit a
new gotcha or make a binding convention decision, append a numbered W-rule here in the same commit.**
P4 closed the ledger at **W54**; **P6 reopened it** (demo-world sync was a post-P4 closure item) and
takes it to **W61**; **P5** (the Week Grid redesign, run after P6) takes it to **W68**; the
**IA redesign programme** (`docs/handovers/ia/`) starts contributing at **W69** and Cycle 1 takes
it to **W74**; Cycle 2's deploy afternoon adds W93-W94 and **Cycle 3** takes it to **W100**;
**Cycle 4** (Insights + Compliance hubs, the filing flow) takes it to **W105**; **Cycle 5**
(Home + People hubs and THE RAIL CUTOVER — five sections, eight items, thirty-nine
retirements) closes the programme at **W110**; **Cycle 6** (the closure cycle: money
visibility, the VN filings' Odoo-19 field drift, pb_learn's reachability split, the
Insights drills, the tenant module-list repair and the restriction-aware palette)
takes it to **W119**; **Cycle 7** (the abm module-delta catch-up, the `hr_timesheet`
`session_info` 500 and the `pb_insights` sudo drop) takes it to **W126**.
73 rules, not 74: there is no W32 — see the note below.
Second numbering note: P5's W68 and IA-C1's first five entries were written the same afternoon in
two sessions and both claimed W68. P5 committed first, so P5 keeps W68 and the IA entries were
renumbered W69-W74. If a handover written that day cites a W-number in the 68-72 range, check the
text, not the number.
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
- **W62 When two surfaces answer the same question, they read the same
  threshold from the same place — and a boolean is not a threshold.**
  `pb.close._classify` flagged `missing_checkout` on `any(not a.check_out)`,
  with no threshold at all, while
  `pb.attendance.exception.engine._get_exceptions` has always gated the same
  kind on the company's `open_checkout_hours`
  (`attendance_exception.py`:214). Nothing errored and nothing looked wrong in
  isolation: on a SETTLED week the two agree perfectly, because every open
  punch there is days past any threshold. The disagreement only appears on the
  CURRENT day, which is the only day an officer looks at in the morning — on
  the P6 cohort roughly fifty of sixty-six Close flags were people who had
  simply clocked in, and the one genuinely forgotten Friday punch was buried
  under them. The officer cannot tell which surface to believe, so the
  instrument is worse than absent.
  Rules: (1) a "problem" predicate that has a configured tolerance ANYWHERE in
  the codebase must resolve it through the same helper
  (`pb.attendance.rule._grace_for_company`), never restate it and never omit
  it; (2) test the AGREEMENT, not the number — `pb_close/tests/test_close.py
  ::test_the_board_and_the_exception_engine_agree_on_open_punches` moves the
  company threshold and asserts both surfaces flip together, which no
  assertion about "16" could have caught; (3) a predicate that is exactly true
  on settled data and wrong on live data will pass every fixture-based suite in
  the repository — the fixture week has to be TODAY for the bug to exist.
- **W63 A wall-clock hour written into a `fields.Datetime` is a defect with no
  symptom until something localizes — and then it is a different shift, not a
  rounding error.** `hr.shift.template.start_hour` is a float meaning "08:00
  where the person works"; `hr.shift.planning.start_datetime` is a
  `fields.Datetime`, i.e. UTC by Odoo's contract.
  `quick_create_shift` (and `pb_schedule._pb_shift_window`, byte-identical to
  it on purpose) stored the wall clock verbatim, so on the VN tenant an 08:00
  shift sat at 08:00 UTC = 15:00 local. Every consumer that treats the column
  as UTC was quietly wrong about it: `_compute_compliance_status` compared a
  real punch to a start seven hours late, `weekentry._save_reg` derived a
  check-in from it, and `pb_schedule`'s roster printed it raw. Meanwhile
  `pb_demo` writes true UTC (W55), so ONE column held two conventions and the
  same code was right about half the rows.
  Rules: (1) fix the WRITE as well as the READ — P5 shipped `_pb_hhmm(dt, tz)`
  and would have made every quick-created shift render +7 if the create path
  had been left alone, i.e. a render-only fix trades one wrong screen for
  another; (2) keep the conversion in ONE place that both the writer and its
  predictor call (`hr.shift.planning.grid._pb_shift_utc` /
  `_pb_shift_tzname`, on the BASE facade, because the predictor lives in a
  module that depends on it — W53's shape); (3) any test of a stored time
  asserts the LOCAL wall clock AND the UTC value, on an employee whose tz is
  deliberately not UTC, or it proves nothing (W55's lesson again); (4) the
  retired legacy `get_grid_data` cockpit still prints the raw stored value —
  left alone under W18, and named here so the next reader does not think it is
  a second bug to hunt.
- **W64 A cell is a place to READ a value, not a place to declare what values
  mean — and the gate that keeps it that way has to be BOUNDED.** The old Week
  Grid drew one pill per APPLICABLE overtime rate in every cell, whether or not
  any hours existed: `150%` `130%` `200%` on 1 183 cells of an empty week, so
  the single real entry read as noise inside its own row. Every one of those
  pills said the same thing as every other pill in its column, which is the
  definition of configuration rather than data. The owner's whole review of the
  live screen was one sentence: *"the % pills are very confusing."*
  The rule: a rate, a multiplier, a policy name or any other fact that is
  IDENTICAL DOWN A COLUMN belongs in a legend (once) and in the editor where it
  is being applied (once) — never in the cell. A cell renders outcomes: the
  number, a chip for what was actually entered, a status dot, the consumer's
  badges. An empty cell is EMPTY; the affordance appears on hover/focus.
  And the gate: `biz_week_grid/tests/test_static.py::test_no_rate_ever_reaches_
  a_cell` greps a region of the template delimited by explicit
  `<!-- ==== day cells ==== -->` / `<!-- row total -->` markers, not the whole
  file. W48's corollary is why — a word-shaped gate over a whole file fails on
  the prose that explains the rule, and this file has to be able to say the
  word "rate" in a docstring. Its complement
  (`test_the_cell_region_still_renders_the_things_it_must`) exists because a
  region that renders NOTHING would pass the first gate perfectly.
- **W65 One payload key, one fact.** `get_week_entries` sent
  `state = '+2b'` when an overtime request had bonus hours and
  `state = 'draft'` otherwise — two unrelated facts multiplexed through one
  string, because the old chip had exactly one text slot and whoever needed the
  second one took it. Nothing errored: a client that renders `state` verbatim
  shows something plausible in both cases, so the overload survived until a
  redesign wanted to draw the state as a DOT and discovered that half the time
  it is not a state. The cost is not the string, it is that no consumer can
  ever ask "is this approved?" without knowing about the other meaning.
  Rule: when a renderer needs a second fact, add the second KEY (`bonus` was
  already there, unused); never widen the meaning of an existing one. Corollary
  for reviews: a field whose values come from two disjoint vocabularies
  (`draft|submitted|approved` and `+Nb`) is the signature, and it is visible in
  the producing expression long before it is visible on screen.
- **W66 A panel that mounts in the OVERLAY re-declares its own token block —
  fallbacks alone are a promise the next contributor will not keep.** W14
  established that `--pbim-*` does not resolve outside a `.pbim` root and W43
  that the overlay container is outside EVERYTHING, so `var()` fallbacks are
  what paint there. P5's cell editor is the first surface in this program that
  is overlaid AND heavily styled (50 `var()` uses), and "every one of them
  carries the right literal" is not a property you can maintain by care. So
  `.bwgx` opens by declaring the whole `--bwg-*` default set ON ITSELF — the
  same values the `.bwg` root declares — which makes the fallbacks a belt to
  the block's braces rather than the only thing standing up. The gate
  (`test_the_overlaid_panel_carries_real_fallbacks`) still walks every
  `var()` in the file and fails any that has no fallback, and skips the
  declaration lines themselves, because they are the source values.
  Corollary: an overlaid panel therefore CANNOT be re-themed by its host. That
  is a real limitation and it is the right trade — a host that needs a themed
  popover passes colours through props (the chips do exactly that with
  `--bwg-chip-c`), rather than hoping a custom property crosses a boundary it
  cannot cross.
- **W67 An OWL getter read inside a `t-foreach` is re-evaluated on every
  iteration — hoist aggregates with `t-set`.** The new footer needs a per-day
  sum and the row column needs a per-row sum, and the obvious shape is a
  `dayTotal(iso)` / `rowTotal(row)` method called from the template. On the
  live cohort that is 169 rows × 7 days, each walking 169 rows × 7 days × 5
  measures — about 700 000 reads per render, for a number that changes only
  when an edit lands. Nothing errors; the grid simply gets slow in exactly the
  case it exists for (a dense week), which is the hardest kind of regression to
  attribute. `totals` is therefore ONE getter returning
  `{byDay, byRow, grand}` from a single pass, read once via
  `<t t-set="tot" t-value="totals"/>` ABOVE the row loop and indexed from
  there. General form: a template may read a getter once per render; putting it
  inside a loop turns an O(n) computation into O(n²) silently.
- **W68 The live server is SHARED, and `service odoo-server stop` takes the
  whole site down for whoever else is on it. Check before you deploy; treat a
  broken bundle you did not write as a REPORT, not a fix.** P5's WP-4
  validation was interrupted twice by a second session upgrading `pb_hub` on
  the same box. The first collision cut an in-flight `save_week_entries` in
  half — nginx answered 502 mid-request, so the REVERT half of P5's edit
  round-trip silently did not commit and two rows were left on the demo world
  that every count in the report would otherwise have called residue. The
  second collision installed a `pb_hub` asset with a syntax error
  (`hub_demo.js`:95, an `_t()` string split across lines with no `+`), and
  because `web.assets_backend` is ONE bundle, a single unparseable file blanks
  the ENTIRE backend for every user and every cockpit — mine included, hours
  after mine had been validated green.
  Rules:
  1. before `service odoo-server stop`, run `ps -eo pid,cmd | grep "[o]doo-bin"`
     AND look for a foreign `-u`/`-i` in the command line. A run that is not
     yours means wait, not kill (W61's PID rule is about STALE processes, not
     live ones);
  2. after ANY write-bearing live test, re-assert the row counts from `psql`
     rather than from the UI. The UI's own confirmation is the thing a 502
     destroys, and `psql` keeps answering while Odoo is down — which is how
     P5 found the un-reverted rows and finished the revert through the same
     `save_week_entries` facade (token included) the tray uses;
  3. a bundle error from another module is diagnosed and REPORTED, never
     patched in place: the other session has that file open and will rsync
     over the fix, so the repair would vanish and the diagnosis with it. The
     way to name it precisely is to fetch the served bundle, split it on the
     `/* path/to/file.js */` markers Odoo emits, and `new Function()` each
     chunk — that returns the exact file in one pass over 1 800 of them.
- **W69 A boolean written as TEXT in a data file is `True`, whatever the text
  says — and a "retired" record can therefore ship for months.** (IA redesign
  Cycle 1, audit fix A1.) `pb_sidebar.item_emp_mapping` carried
  `<field name="active">False</field>` above a comment explaining that the item
  had been retired into the Formula Engine's Mapping canvas. Odoo's Boolean
  converter reads the element's TEXT and coerces any non-empty string to true,
  so the field was set to `True` on every install and upgrade, and the retired
  item was on the SETUP rail the entire time. Nothing warns: the record loads,
  the rail renders, the comment reads as documentation of a change that never
  happened. Booleans in data files take `eval` (`<field name="active"
  eval="False"/>`); the same trap covers any `eval`-shaped value written as
  text (`0`, `[]`, `{}` are all truthy strings). Corollary for reviews: when a
  comment claims a record is off, the proof is the DATABASE (W13.1), and
  `pb_sidebar/tests/test_ia_c1.py` asserts it through `get_sidebar_data()` —
  the payload the rail actually renders — rather than through the field.
- **W70 W8's sequence-uniqueness rule is invisible from inside the file you are
  editing, because the twin lives in another module.** (Cycle 1, audit fix A2 —
  the sequence counterpart of W28's label collision.) `pb_sidebar.item_menu_cfg`
  and `pb_audit.item_audit_console` both declared ADMIN sequence 30, in two data
  files neither of which mentions the other. The ORM orders by `sequence, id`,
  so the rail's ADMIN block silently ordered itself by whichever module happened
  to be installed first — a rail that differs between two databases with the
  same code. Rule: before setting a `pb.sidebar.item` sequence, scan the section
  across EVERY module's data files, not the one in front of you. Gated for good
  by `test_a2_no_section_has_two_items_on_one_sequence`, which buckets the whole
  table by `(section, parent)` with `active_test=False` (W18: a retired item
  still occupies its number).
- **W71 The rail's active-item index is FLAT and last-writer-wins, so a
  `match_models` / `match_action_tags` value claimed twice silently steals the
  highlight.** (Cycle 1, audit fix A3.) `pb_sidebar.js::_buildIndex` folds every
  item's match dimensions into three plain objects — `{model: itemId}` — with no
  collision check, and `_resolveActive` reads them in xmlid → tag → model order.
  `item_import` and `item_integrations` both claimed `hr.integration.connector`,
  so opening the connector cockpit lit up **Integrations** and Import Data could
  never light up for it. There is no error, no console warning and no visible
  tie: the user simply learns that the rail is unreliable. Rule: a res_model, an
  action tag and an action xmlid each belong to exactly ONE rail item, and the
  general form is gated by `test_a3_no_model_is_claimed_by_two_items` and
  `test_action_tags_are_claimed_once_too` rather than by the specific pair.
- **W72 An XML comment may not even NAME a CSS custom property.** (Cycle 1,
  caught by `xmllint` before commit — the cheap gate W22 already prescribes.)
  W22 records that a doubled hyphen inside an XML comment is a parse error that
  takes the whole template file down. Cycle 1 found the shape that makes it easy
  to walk into: the hub kit's template header EXPLAINED W22, and the palette's
  explained W14 by writing the pbim custom-property prefix — which is two
  hyphens — so three template files were parse errors written by someone
  thinking about the rule. This is W48's corollary about grep gates failing on
  their own documentation, one layer down: prose is not exempt from the parser.
  Write "the pbim custom properties" in a comment, and keep the literal token
  name in the SCSS where it belongs.
- **W73 Odoo's hotkey service dispatches ONE registration, newest first — so a
  global shortcut is defeated by mount ORDER, which is a coincidence until you
  declare it.** (Cycle 1, the global ⌘K.) `hotkey_service.dispatch()` builds its
  candidate list from `Array.from(registrations.values()).reverse()` and calls
  `candidates.shift()`: exactly one winner, newest registration first. A service
  starts before any component mounts, so a service-registered `control+k` is
  always the OLDEST and always loses to a component's `useHotkey("control+k")` —
  which is precisely the behaviour a global palette wants against Mission
  Control's and Formula Studio's own palettes. It is also invisible, untestable
  and one refactor away from silently producing two overlays.
  So `pb_hub_palette` states the rule instead of relying on it: the registration
  carries `isAvailable: () => !localPaletteOwnerOnScreen()`, and the owners are
  CSS root selectors in a `pb_hub_palette_yield` registry (`.pbms`, `.pbfs`).
  A candidate that fails `isAvailable` is filtered before the winner is picked,
  so the local palette wins by declaration; a third surface that grows its own
  ⌘K adds one line to that registry. Two things the gates then have to check,
  because each failure is silent in the opposite direction:
  `test_the_yield_selectors_match_real_roots` (a stale selector gives the global
  palette back and you get two overlays) and
  `test_both_local_palettes_still_register_their_own_hotkey` (an owner that
  stops registering ⌘K is left with NO palette, because the global one has
  already stood down for it).
- **W74 The JS habit that blanks the whole backend: Python-style implicit
  string concatenation.** W68 records the *consequence* — one unparseable file
  blanks `web.assets_backend` for every user and every cockpit, with a clean
  server log — from the outside, as the session that got hit by it. This is the
  same defect from the inside, so the next author does not write it again.
  `_t("first half "` on one line and `"second half")` on the next is Python.
  In JavaScript two adjacent string literals are a `SyntaxError`, and Odoo's
  asset pipeline CONCATENATES and MINIFIES without ever parsing: `-u` exits 0,
  the module's own tests pass, and the bundle is served with a 200 and a
  plausible byte count. Nothing in the Python test suite can see it.
  Rules: (1) `node --check <file>` every JS file you touched before rsync — it
  is instant and it catches this whole class; (2) after deploying JS, fetch the
  served `web.assets_web.min.js` and `node --check` THAT, because the bundle is
  what the browser parses and a 200 proves nothing (W68.3 has the finer tool for
  attributing an error to a file you did not write); (3) a blank backend with a
  clean log means the BUNDLE, not your surface — look for `SyntaxError` and its
  knock-on `Unexpected token '<' ... is not valid JSON` (the webclient's
  translations fetch getting an error page) before suspecting your component.
  The cheap half is gated by `pb_hub/tests/test_static.py
  ::test_no_python_style_implicit_string_concatenation`.
- **W75 A backgrounded Chrome renders NOTHING, and it looks exactly like a
  broken build.** (IA redesign Cycle 1. Cost: an hour of hunting a defect that
  did not exist, immediately after fixing one that did — which is what made it
  so convincing.) OWL flushes a completed render through its scheduler on
  `requestAnimationFrame`. Chrome throttles rAF to zero in a window that is
  occluded, minimised or simply behind another one, so a headful automation
  browser that never comes to the front boots the whole web client — every
  module loads, every service starts, `load_menus` / `translations` /
  `mail/data` all return 200, the root fiber renders to completion — and then
  never paints. `document.body` keeps the 50 bytes of whitespace the server
  sent. There is no error, no console output, no failed request and no
  traceback: on a server log it is indistinguishable from a healthy page load,
  and in the browser it is indistinguishable from W74's blanked bundle.
  How to tell them apart in one step, and the reason `__OWL_DEVTOOLS__` is worth
  knowing about: walk `window.__OWL_DEVTOOLS__.apps` and read the root fiber.
  `counter === 0` with every node at `status 0` and no pending `onWillStart`
  means the render FINISHED and only the paint is missing — that is throttling
  or a scheduler problem, never your component. A real bundle error leaves the
  loader with failed modules; a real hanging mount leaves nodes whose
  `fiber.bdom` is still null, and that names the component.
  Rule for any Chrome-MCP or CDP validation from here on: launch with
  `--headless=new`, or at minimum
  `--disable-backgrounding-occluded-windows --disable-renderer-backgrounding
  --disable-background-timer-throttling`. Headless is the honest default,
  because an automation browser is by definition never in the foreground.
  Second rule: when two sessions share one Chrome profile the second one gets
  "The browser is already running for …" and then orphans a browser of its own
  on every call — a dedicated `--user-data-dir` per session (and a driver of
  your own over `/json/list` + the CDP websocket) is worth the twenty lines.
- **W76 "Retire, never delete" has a shelf life, and it expires the day the
  thing it points at stops existing.** W18 was right for five phases: a
  replaced cockpit kept its client action and its rail record with
  `active = False`, so the decision stayed reversible and a bookmark kept
  working. P7 deleted the five Gen-0 surfaces themselves, and at that moment
  every one of those "reversible" records became the opposite of what the rule
  intended — an `ir.actions.client` whose tag nothing registers answers a
  bookmark with a broken screen, an `ir.ui.menu` whose action is gone is not a
  dead link but a module that will not INSTALL (Odoo resolves `action=` at load
  time), and a retired `pb.sidebar.item` whose `action_xmlid` no longer
  resolves is a button an admin can re-enable into nothing.
  Rules: (1) a retirement record and the surface it points at have exactly one
  lifetime — delete them in the same commit or neither; (2) the caller audit
  runs at IMPLEMENTATION time, not at design time, and a LIVE caller outside
  the phase's scope means keep-and-report, never a cascade into a module you
  were not asked to touch (P7 kept `hr.workforce.dashboard` for exactly this
  reason: `pb_business_trip` inherits it); (3) a gate that asserted the OLD
  rule gets its reversal written at the site, not silently flipped — six gates
  changed in P7 and each carries the paragraph explaining why the thing it used
  to demand is now forbidden, because a gate whose history is invisible is one
  the next reader will "fix" back.
- **W77 A program can pin a timezone in two places and still be wrong, because
  the WRITE path resolves a third one first.** W55 pinned Vietnam for
  everything `pb_demo` writes; P6 stamped `Asia/Ho_Chi_Minh` on 4 502 demo
  employees. Neither reached `hr.attendance.weekentry._emp_tz`, whose order is
  `emp.resource_calendar_id or company.resource_calendar_id` FIRST, employee
  second, viewer third — and the demo company shipped Odoo's stock 40-hour
  calendar, which carries `Europe/Brussels`. So every seeded row was in the
  right place and every HAND-ENTERED one was five hours out: typing "8" into a
  Week Grid cell wrote 08:00 Brussels = 13:00 in Ho Chi Minh City, straight
  past the UTC-day rule (W51) the whole seeder is built around.
  Rules: (1) when a value has a RESOLUTION CHAIN, the fix belongs at the first
  hop the chain actually takes, and you find that hop by reading the resolver,
  not by fixing the field you already know about; (2) assert it THROUGH the
  facade (`_emp_tz(emp)`), never on the field — the resolution order is the
  thing that was wrong, so a test on `emp.tz` passes while the bug is live;
  (3) no fixture suite can see this class of bug, because a fixture calendar is
  whatever the test made it — it is found on live data or not at all.
- **W78 A test guarded by `if <optional module> is installed`, on machines that
  never install it, is a test that cannot fail.** `pb_young_worker`'s test_09
  asserted `mro.index(pb_young_worker) < mro.index(pb_demo)` inside
  `if demo is not None`. The claim was false (the real order is
  `pb_demo -> pb_close -> pb_young_worker -> pb_payrun_wizard`; none of the four
  declares a dependency on another, so it is Odoo's `(depth, name)` accident),
  and CI installs pb_young_worker WITHOUT pb_demo — so a green test asserted a
  false statement about a configuration it had never seen, for three phases,
  while two module docstrings quoted it as proof.
  Rules: (1) a conditional guard around the ONLY assertion in a test is a smell
  — either the dependency is real and the test should skip loudly, or the
  assertion belongs somewhere it always runs; (2) never assert MRO POSITION,
  assert the MECHANISM: "the wrapper is registered on both seams", "the generic
  path appends after super and the run's own rows survive", "the demo hook
  produces our rows", "an injected failure does not reach the run" — four tests
  that each fail for one reason, none of which is an index nothing declares;
  (3) an ordering that no `depends` expresses is not a guarantee, and code that
  needs one must create it (an explicit hook call) rather than document it.
- **W79 A silent fallback makes a DEAD entry indistinguishable from an ABSENT
  one, so behaviour alone can never gate it.** `hr.flow.wizard.
  get_tertiary_action` maps ~100 route keys to xmlids and returns
  `act_window_close` both for an unknown key and for an xmlid that will not
  resolve. That is correct — the map names optional modules, and a launcher
  that raised on a database missing one would be worse — but it means a tile
  pointing at a DELETED action renders normally and answers a click with
  nothing: no traceback, no console message, nothing in the log. Five of them
  survived that way until P7 went looking.
  Rules: (1) any resolver with a swallowing fallback needs a SOURCE gate beside
  its behaviour tests, because only reading the file can distinguish "did
  nothing because absent" from "did nothing because wrong"; (2) the behaviour
  test compares the action's IDENTITY against `env.ref(expected).id`, never
  just "a dict came back"; (3) when a key is remapped, the user-facing LABEL
  moves with it — a tile still called "Live Attendance" that opens Today is a
  broken promise even though the click works.
- **W80 Odoo's translation extractor reads text nodes and translatable
  attributes; it does not reach a string literal inside a `t-att` EXPRESSION.**
  `t-esc="x or 'Locked'"`, `t-attf-title="Open {{ row.label }}"`,
  `props.emptyText || 'No rows to show'` — six of these in `biz_week_grid`.
  They read perfectly in English, never appear in any `.po`, and stay English
  forever in a translated UI with nothing to report them. The visible half of
  the module was translatable and the invisible half was not.
  Rules: (1) anything a user can read comes through `_t` in JS or a plain text
  node — an expression is not a place for a user-facing string; (2) a SENTENCE
  is one msgid: "3 cells edited · 4.5 h overtime drafted" is built by one getter,
  not assembled from `<t>` fragments, because a translator cannot reorder
  fragments and word order is exactly what differs; (3) keyboard glyphs (Tab,
  Esc, ⌫, Ctrl/⌘ D) are NOT translated — they are what is printed on the key;
  (4) `msgfmt --check-format` is the gate for placeholder drift, and named
  placeholders (`%(cells)s`) are what let the order change at all.
- **W81 A committed test suite that nothing executes is worse than no suite:
  it costs maintenance and reads as coverage.** `biz_week_grid`'s 23 hoot cases
  shipped in P5, registered in `web.assets_unit_tests`, and `-u` never built
  that bundle — compiled, served, never run. The trap in fixing it is sharper
  than the gap: hoot's URL filter is a HASH of the suite descriptor, so a
  descriptor that matches nothing filters EVERYTHING out, hoot runs zero tests
  and prints "[HOOT] Test suite succeeded". A green gate proving nothing is the
  one outcome worse than the original silence.
  Rules: (1) pair a browser runner with a STATIC gate that always runs — the
  suite still exists, is still in the unit bundle, still holds cases, still has
  unique names — because that half catches a suite silently ceasing to exist;
  (2) make the static gate a FLOOR (">= 15"), never a count, or every added case
  is a failing build; (3) derive the hash's input from the file's real path and
  assert it equals the constant the runner uses, so descriptor drift is loud
  rather than green; (4) tag the browser runner out of the standard run when the
  deploy host has no Chrome — a gate that errors on every deploy is a gate the
  next person disables — and write the manual `/web/tests` ritual down instead.
- **W82 A filter is a way of LOOKING at a week; it must never change what the
  week IS — and a batch must waive exactly the rows that were on screen.** Both
  halves of P7's Close work are the same mistake in two costumes. If the kind
  chip narrowed the stats, an officer could filter to one kind and watch "Lock
  week" turn green. If `review_kind` rebuilt its target set from a domain of its
  own instead of the read model's `_rows_for`, it would waive rows nobody saw
  and nothing would ever surface it.
  Rules: (1) stats, checklist and `can_lock` are computed over the whole scope;
  only the TABLE is filtered and paged, and the payload carries three numbers
  (scope total, filtered total, page size) because a paged table can lie in two
  directions at once (W45); (2) the read and the bulk write share ONE set
  builder — a second opinion about what is on the board is a silent data bug;
  (3) a per-row gate must survive a batch: each row in its own savepoint,
  refusals COLLECTED with the model's own words and reported to the caller, so
  "37 reviewed, 2 skipped" is possible — a batch reporting 40 when 39 landed is
  worse than one that refuses; (4) the batch is per KIND, because one note over
  forty assorted problems is not a decision anybody can defend; (5) past a cap
  it REFUSES rather than truncating — 200 of 300 leaves a board that looks
  almost clear with nobody knowing which hundred were left.
- **W83 `service odoo-server stop` can leave the process running, and systemd
  says so in one line nobody reads.** Twice during P7's deploy the journal
  logged `odoo-server.service: Unit process NNNN (python3) remains running
  after unit stopped` — `systemctl is-active` reported *inactive*, port 8069
  was closed, and an odoo-bin was still up holding database connections. That
  is not a foreign run and it is not a live server: it is an orphan, and it is
  exactly W61's kill-by-PID case. The way to tell the three apart, in order:
  a FOREIGN run has `-u`/`-i` in its command line (wait, never kill — W68); a
  LIVE server is listening on 8069; an ORPHAN is neither.
  Corollary, learned the same afternoon: `ps -eo pid,cmd | grep odoo-bin | grep
  -E " -u "` matches YOUR OWN ssh command line when the command you are about
  to run contains `-u`, so the foreign-run check reports a collision with
  itself and aborts the deploy. Put the check in a script FILE on the server
  and run that, rather than passing it as an ssh argument.
- **W84 The stop→upgrade→start ritual has an UNBOUNDED outage window, because
  the only thing that starts the service again is the operator. (Cost: ~2 h of
  502s on payobook.com during P8, and the owner found it, not the session that
  caused it.)** P8's first deploy stopped the service, launched the detached
  upgrade, and then the session hit a usage limit between those two steps. The
  upgrade itself completed perfectly — `EXIT=0`, every module at its new
  version — and the box sat with port 8069 closed until a human noticed the
  site was down. Nothing in the ritual notices, because every check it has runs
  *inside* the session that is no longer there.
  Two rules, and they are cheap:
  1. **Everything the window needs exists BEFORE `service odoo-server stop`** —
     the rsync done and md5-verified, the sentinel script written to the server,
     the foreign-run check (W83) already run. The stopped window is then exactly
     one registry load long and never waits on a decision, a file, or a
     round-trip. P8's later windows were built this way and each was ~7 minutes
     of a single `systemd-run` unit;
  2. **On ANY resume — a new session, a recovered one, a hand-back — the FIRST
     action is `systemctl is-active odoo-server` plus a public HTTP check, and
     restarting if the box was left stopped.** Before reading the diff, before
     re-orienting, before anything: an interrupted deploy is far more likely to
     have left a dead site than a corrupted one, and the dead site is the part
     that has users on it.
  Corollary on the health check itself: right after a stale-asset purge the
  first request rebuilds every bundle and legitimately takes 2–3 minutes, so a
  25-second `curl` timeout reports `000` and looks exactly like an outage. Warm
  the box with a long-timeout request before concluding anything from a fast one.
- **W85 `sudo()` does NOT change `create_uid`, so it cannot make a row
  anonymous. (Found by P8's own live test run, in the one model whose entire
  purpose is that no row is about a person.)** `pb.shift.pulse` was written with
  `self.sudo()` and a docstring explaining that this made the ORM's audit stamp
  say "the system" rather than the employee rating their own shift. That has
  been false since Odoo 13: `sudo()` raises the `su` FLAG and leaves `env.uid`
  exactly where it was, so every pulse row carried its rater's user id in
  `create_uid` — in a table with no employee column, behind a salted hash, under
  an anonymity floor, all of which were then decoration. The test asserted the
  claim (`create_uid == base.user_root`) and came back `1903 != 1`, which is the
  rater's id.
  Rules: (1) when anonymity or attribution is the POINT, write with
  `with_user(SUPERUSER_ID)` — it moves the uid and raises su; (2) assert BOTH
  `create_uid` and `write_uid`, because a refactor that fixes one and forgets
  the other leaks just as completely; (3) more generally, a privacy property
  that is only stated in a docstring is not a property — the reason this was
  caught at all is that the docstring's claim had been written down as an
  assertion.
- **W86 A feature that hooks a STATE TRANSITION only ever sees the future, so
  installing it onto a live world leaves the existing records outside its own
  contract — and only a row count says so.** P8 mints an acknowledgment token in
  `hr.shift.planning.action_publish`, which is the right seam (every publisher
  gets it, W31's shape). Every test passed, the deploy was clean, and
  `SELECT count(*) FROM hr_shift_planning WHERE ack_token IS NOT NULL` came back
  **0**: this tenant's roster had been published the week before the module
  existed, so no shift had ever crossed the transition. Nothing errored. The
  portal ack still worked and the badges still counted — only the mailed link,
  the channel built for the people who have no login, pointed at nothing.
  Rules: (1) a transition-hooked feature ships an idempotent BACK-FILL and calls
  it from `post_init_hook`, so the install brings the existing world into the
  contract; (2) bound the back-fill to records the feature can still act on
  (P8 mints only for published, not-yet-started shifts — a credential nobody
  can use is a credential somebody can leak); (3) after any install that adds a
  column the code is supposed to populate, COUNT THE POPULATED ROWS on the live
  database. A green suite proves the transition works, never that anything has
  taken it.
- **W87 A QWeb `t-set` BODY is rendered markup, and on a `website=True` page the
  editor's branding rewrites it — so `<t t-set="icon">calendar</t>` is not the
  string "calendar".** Every icon in P8's portal rendered as the same empty
  circle: the shared `work_icon` template compares `icon == 'calendar'`, and the
  value arriving from the call site was Markup carrying `data-oe-model` branding
  attributes, so every branch was False and all 24 call sites fell through to
  the else. There is no error, no console message and no visual clue beyond
  "the icons look wrong", and the identical pattern in `pb_me_portal` had been
  shipping the same way unnoticed because its else-branch is a plausible file
  icon.
  Rule: pass a literal with `t-value="'name'"`, never as a `t-set` body, whenever
  the value is COMPARED rather than printed. A body is for content; a value is
  for data. (`t-set` with a body remains correct for the markup blocks it was
  designed for — a hero's action buttons, a slot.)
- **W88 A badge derived from what the user can still DO will lie about what has
  HAPPENED.** P8's week header showed "All confirmed" over a week containing two
  unconfirmed past shifts, because its counter was `can_ack` — and a shift that
  has started can no longer be acknowledged, so it counted as nothing left to
  do. Both facts are real and they are different questions: the BUTTON is about
  remaining actions, the BADGE is about the record. Derived from the same
  number, one of them is always wrong. W42's rule ("a surface stricter than the
  model must derive the strictness from the model") has this mirror image:
  a surface SOFTER than the record has to derive from the record too.
  Same phase, same shape, second instance: 32 leave-type tiles all reading
  "0.0 days left" — every allocation-based type in the database rendered for an
  employee who had none. That is W64's "configuration in a cell" on a portal,
  and the fix is the same: a tile is a fact ABOUT THIS PERSON, so a type they
  have neither been allocated nor taken is not one.
- **W89 A raw SQL write does not reach the ORM cache, so the running server
  keeps serving the old value.** P8 restored a demo user's language with
  `UPDATE res_partner SET lang=...` after the psql-set value had been verified;
  `psql` showed `en_US`, and the session kept reporting `vi_VN` through a
  logout, a fresh login and a new browser context, because the worker held a
  cached `res.partner`. The database was right and the product was wrong, which
  is the opposite of W13.1's failure and the same lesson: the two have to be
  checked separately. Raw SQL is legitimate for setting a value nothing has read
  yet (the temp-password ritual) and wrong for correcting one the server is
  already serving — use the ORM (`res.users.write`) so the cache invalidates,
  and re-read through the SESSION rather than through psql to prove it landed.
  Related, from the same afternoon and worth knowing before it costs an hour:
  **this server cannot render ANY non-English backend.** `web_debranding`'s
  `_get_translations_for_webclient` (`addons/web_debranding/models/ir_http.py`
  :21) does `message["id"] = debrand(...)` on what Odoo 19 now hands it as a
  `ReadonlyDict`, so `/web/webclient/translations?lang=vi_VN` 500s, the
  webclient's boot rejects at `fetchTranslations` and the page stays blank with
  a clean module loader (W74's signature is absent: `odoo.loader.failed` is
  empty and 1 772 modules are loaded — that is how to tell this apart from a
  bundle error in one step). It is another module's defect and it is REPORTED,
  not patched (W68.3); until it is fixed, no Vietnamese backend surface can be
  visually validated on this box, and `.po` correctness has to be evidenced from
  the files and the database instead.
  **CLOSED in P9** (2026-08-19). The last two sentences no longer hold: the
  endpoint answers 200 for vi_VN, and P7's deferred Vietnamese visual check was
  taken on the live Week Grid the same afternoon. See W90 for the fix and for
  the part of the original diagnosis that turned out to be a trap.
- **W90 A read-only wrapper around a PROCESS-WIDE cache is a warning, not an
  obstacle — and the obvious repair (copy it and carry on) can still break the
  thing it was protecting.** (P9, fixing W89.) `web_debranding` rewrote the web
  translation catalogue in place; Odoo 19 now hands that catalogue back as
  `ReadonlyDict` entries out of `code_translations` (`odoo/tools/translate.py`,
  `CodeTranslations._load_web_translations`), so the assignment raised
  `TypeError` and every non-English `/web/webclient/translations` answered 500.
  Two things are worth keeping from the repair:
  1. **the wrapper had a reason.** `code_translations` is a module-level
     singleton shared by every database in the worker, so the in-place rewrite
     that "worked" on Odoo 16 was writing one tenant's branding into every
     other tenant's catalogue. On a DB-per-tenant SaaS box that is the more
     expensive bug of the two. Rebuild into plain dicts; never patch the
     cached objects, even where the runtime would now let you;
  2. **half of that catalogue is not text, it is a KEY.** Each entry is
     `{"id": msgid, "string": translation}` and the web client indexes on the
     first (`localization_service.js`: `terms[addon][message.id] =
     message.string`) — `id` is the literal `_t()` is called with in the JS
     sources. Rewriting it, which is what the original loop did, silently
     drops the translation of every term containing the word being replaced.
     So the fix rewrites `string` only. General form: before "fixing" a loop
     that mutates a mapping, ask which side of each pair is data and which is
     an index — the crash tells you the code cannot run, never that it was
     right.
  Diagnostic worth reusing: **English is the one language that cannot reproduce
  this class of bug**, because `en_US` carries no .po code translations at all,
  so any loop over `messages` has an empty body. A catalogue/translation test
  that only runs `en_US` is testing the empty case. Pin a real language
  (`web` ships `vi.po` and `fr.po`, and `get_po_paths` resolves `vi_VN` down to
  `vi.po`, so no language has to be INSTALLED for the test to have data).
- **W91 A `t-set` body only misbehaves under FULL branding, which is why W87's
  defect can sit in a module for months while every page you look at is fine.**
  (P9, converting `pb_me_portal`'s eight call sites.) `website/models/ir_qweb.py`
  :93-100 sets `inherit_branding=True` (branding on ir.ui.view TAG NODES — the
  case that turns `<t t-set="icon">download</t>` into unmatchable Markup) only
  in website EDIT mode; a restricted editor merely gets `inherit_branding_auto`,
  which brands FIELDS, and an ordinary portal user gets neither. Measured live
  on `/my/payslips`: zero `data-oe-model` attributes for both the seeded ESS
  portal user and an internal manager. So the broken icons were real and were
  invisible to the population that uses the page every day.
  Consequences: (1) "I loaded the page and the icons were fine" is not evidence
  — the source gate is the primary check and the render test must set
  `inherit_branding=True` explicitly (`ir.qweb._render(view_id, {},
  inherit_branding=True)`, both directions: the body form must NOT reach the
  right branch, the t-value form MUST); (2) when a rule's blast radius is
  narrower than the rule, write the radius down, or the next reader will
  quietly decide the rule does not apply to them.
- **W92 Upgrading a dependency runs its DEPENDENTS' suites, often for the first
  time ever — so a "new" failure may be a first execution.** (P9.)
  `-u web_debranding` pulled `biz_debrand`'s tests into the run, and
  `TestBizDebrandHttp::test_database_manager_debranded` failed: it asserts
  `/web/database/manager` carries no `odoo.com`, and biz_debrand has no
  db-manager seam at all — `grep` finds the string only in the test. The test
  has therefore been asserting an unimplemented feature since it was written,
  and nothing surfaced it because nothing had ever upgraded the module
  underneath it. Rules: (1) before calling a failure a regression, check
  whether the log has EVER run that test before (`grep` the name across the
  server log) — a first-ever execution is a discovery, not a break; (2) it is
  still REPORTED, not patched in the same phase (W68.3, and here also because
  the fix is a debranding seam and the phase's own constraint forbade adding
  debranding logic); (3) scope a deploy's `-u` deliberately: touching a
  low-level third-party module re-validates and re-tests everything above it,
  which is a feature — just budget for it.
- **W93 `--delete` belongs to the STAGING hop and NEVER to the hop into the
  shared addons directory. (IA Cycle 2. Cost: the entire
  `/odoo/odoo-server/addons` tree — 45 442 tracked Odoo files and 151 custom
  modules — deleted in under a second, on the live box, mid-afternoon.)**
  The deploy ritual is two rsyncs and only the FIRST one may prune:
  `rsync -az --delete <my modules> host:/tmp/stage/` is scoped to a directory
  this session owns, so `--delete` there means "the stage is exactly my
  modules". The second hop is `sudo rsync -a --chown=odoo:odoo /tmp/stage/
  /odoo/odoo-server/addons/` and its destination holds **every other module on
  the server**, so `--delete` there means "delete Odoo". Adding it out of
  symmetry — which is exactly how it happened, the flag was copied from the
  line above — is a one-character-per-word difference between a deploy and an
  outage.
  Three things made the recovery possible, and each is worth ensuring BEFORE
  the next deploy rather than after it:
  1. **`/odoo/odoo-server` is a git checkout of odoo/odoo at 19.0.**
     `sudo git -C /odoo/odoo-server checkout -- addons` restored all 45 442
     tracked files in 10 seconds. (It needs
     `git config --global --add safe.directory /odoo/odoo-server` first — root
     operating on an odoo-owned repo trips git's dubious-ownership guard — and
     a `chown -R odoo:odoo` afterwards, because root's checkout writes
     root-owned files.) The CUSTOM modules are untracked there and git cannot
     help with them: they come back from the repo.
  2. **`ir_module_module` is the inventory.** The list of what MUST be on disk
     is `SELECT name FROM ir_module_module WHERE state='installed'`; comparing
     it against `ls` of the two addons paths is what turns "something is
     missing" into a finite list (86 modules here, all of them present in the
     repo).
  3. **The running server survives the deletion.** Python has already imported
     what it needs, so the site keeps serving while the files are gone — which
     buys the whole recovery window, and is also why the FIRST instinct after
     such a mistake must be *do not restart*, not *restart and see*.
  Corollary about what the restore may NOT assume: this repository also
  contains a February-2026 SNAPSHOT of ~87 community modules (`web`, `website`,
  `hr`, `crm`, `spreadsheet`, …), which differ from the server's own checkout
  in 2 421 files. Those are upstream changes since February, not local forks —
  the server had never been rsynced from them, and pushing them "back" would
  have silently downgraded half of Odoo. Restore community modules from the
  server's OWN git; restore custom modules from the repo; and tell the two
  apart by asking whether git tracks the path, never by whether the name exists
  in both places.
- **W94 `rsync --files-from` turns recursion OFF, and `-a` does not turn it back
  on — so it copies the DIRECTORIES and none of the files, silently and with
  exit code 0.** (IA Cycle 2, the second half of W93's afternoon, and the reason
  the first restore attempt failed.) `rsync -az --files-from=list.txt --relative
  . host:/tmp/restore/` reported success, and `ls /tmp/restore | wc -l` said
  151 — the right number of module directories, every one of them EMPTY. The
  count that looks like the answer is the count of the thing that was NOT
  affected. The upgrade that followed then failed in a way that pointed
  nowhere near the cause: `some depends are not loaded (om_hr_payroll,
  pb_hr_payroll_base), skipped`, i.e. it read like a dependency-graph problem in
  the module being installed.
  Rules: (1) after any bulk transfer, count FILES (`find … -type f | wc -l`),
  never directories; (2) for a many-module transfer prefer `tar -czf` + extract,
  which has no such mode switch — but strip macOS AppleDouble resource forks
  afterwards (`find … -name "._*" -delete`), because bsdtar packs xattrs and
  3 464 `._`-prefixed files appear beside the real ones; (3) prove the restore
  by DIFFING the checksums against the source before starting the server, not
  by starting the server and reading the log.
- **W95 A gate copied from the RAIL is not a gate derived from the ACL, and only
  the second one can be right.** (IA Cycle 3, found on the live run within a
  minute of the Settings hub first rendering.) C1's palette rule was "every gate
  mirrors the rail item that owns the same door", and Cycle 3's Settings hub
  started out obeying it: Formula Engine gated at the pb_hr_payroll_base OFFICER
  tier, because that is what `pb.sidebar.item` says. `hr.formula.config` grants
  read to `pb_hr_payroll_formula.group_formula_user` / `_manager`, and on this
  database NEITHER tier implies the other — there are three parallel group
  families here (om_hr_payroll, pb_hr_payroll_base, pb_hr_payroll_formula) and
  they meet nowhere. So the card rendered, the click produced an access dialog,
  and that is W29's door-that-can-only-error reached through a brand-new
  entrance. The rail has been shipping the same defect.
  Rules: (1) derive an offer's gate from the `ir.model.access` of the model
  BEHIND it, not from whatever menu used to open it — narrower is always safe,
  because a gate can only hide a door, never manufacture a broken one;
  (2) group resolution FAILS OPEN by design (an unresolvable xmlid means the
  module is not installed), so a wrong or mistyped gate is invisible at runtime
  in both directions and needs a SOURCE gate:
  `pb_settings/tests/test_settings.py::TestSettingsGatesMatchTheAcls` reads the
  descriptor back out of the JS and checks each gate group against
  `ir_model_access`; (3) the consequence is allowed to change the product —
  `res.config.settings` is `base.group_system` only, so "Payroll defaults" is an
  ADMINISTRATOR card and the handover's table said manager. Say which, and why.
- **W96 An OWL template expression is compiled against the COMPONENT and nothing
  else, so a JavaScript global in a `t-att` becomes `ctx.<name>` and the surface
  dies at mount.** (IA Cycle 3.) `t-att-selected="form.config_id === String(c.id)"`
  is ordinary JavaScript and an ordinary-looking template; compiled, it is
  `ctx.String(c.id)`, and the whole onboarding flow answered its own button with
  "TypeError: ctx.String is not a function" — the action reverted to the previous
  screen with no dialog and nothing in the server log, which reads exactly like
  "the button does nothing". `node --check`, `xmllint` and the module's own
  Python suite are all blind to it: an OWL template error surfaces only at
  runtime (C18.71/W10). Put the expression in a METHOD. Gated by
  `pb_integrations/tests/test_one_door.py::test_no_template_expression_calls_a_
  javascript_global`, which reads `t-*` ATTRIBUTE VALUES only so the prose
  explaining the rule may still say the word (W48's corollary).
- **W97 A satellite table with no company of its own inherits its OWNER's record
  rule — and one unreadable row takes the whole table with it.** (IA Cycle 3,
  the second live finding.) `hr.integration.field.mapping`, `hr.api.data.store`
  and `hr.api.transformation.rule` all reach their connector by many2one and
  none carries a `company_id`; `hr.integration.connector` is multi-company
  gated. An unscoped ledger read all 207 mappings, dereferenced
  `connector_id.name` to render a column, hit the ONE row whose connector the
  caller may not see, and the client showed "This table could not be loaded" —
  199 perfectly readable rows lost to one refusal, and the message names neither
  the row nor the reason.
  Rules: (1) scope such a table through `owner.search([])`, which applies the
  record rules — that is not a permission decision (the rule already made it),
  it is refusing to ask a question whose answer would raise; (2) a deep link's
  id INTERSECTS that scope, never replaces it, or the browser can widen what the
  rules narrowed; (3) test it by walking the returned rows back to their owner
  (`test_no_row_names_a_connector_the_caller_cannot_read`) rather than by
  counting them — a correct count and a poisoned row look identical.
  Corollary about validation personas: a single-company probe cannot see a
  fixture that lives on another company, and the honest reading of an empty
  ledger is "the scope works", not "the feature is broken".
- **W98 `doAction("<tag>")` carries no action NAME, so anything that returns
  through a BREADCRUMB comes back to a crumb labelled "Unnamed".** (IA Cycle 3.)
  A bare tag makes the action service synthesise `{type: "ir.actions.client",
  tag}`; the `ir.actions.client` RECORD — with its name — is never loaded. That
  is invisible on a bespoke cockpit, because none of them render Odoo's control
  panel. It becomes visible the moment such a surface opens a NATIVE act_window
  without clearing the breadcrumbs, which is the only return path a back chip
  cannot provide (Odoo's own views cannot host one). Rule: a client action that
  will appear in a breadcrumb is opened by XMLID; the tag stays as the presence
  probe, because the registry is what tells you the module shipped its JS.
- **W99 A page-shaped cockpit is not a containing block, so the kit's drawer
  scrolls away inside it.** `WfDrawer`'s scrim is `position: absolute; inset: 0`
  and `.pbim-page` is `min-height: 100%; overflow: auto` with no `position` — so
  on a standalone cockpit the scrim resolves against the initial containing
  block, and an absolute child of a scrolling box scrolls WITH the content: the
  drawer slides off the top as the table moves under it. C2 solved this for the
  EMBEDDED case (`.pbl-ledger--hub`) and the shape is the same standalone: the
  root stops scrolling and becomes a definite-height flex column, the scrolling
  moves inside to `.pbim-wrap`, and that wrap needs `width: 100%` beside its
  `max-width` or `margin: 0 auto` cancels its stretch (W39). Two selector
  classes (`.pbim.itg-board`) so it outranks `.pbim.pbim-page`'s own overflow,
  and no z-index anywhere, because the scrim carries the kit's 60 and the box
  must not become a stacking context (W37).
- **W100 Adding a SECOND company to a user breaks their webclient on this build,
  and the traceback names a module nobody touched.** (IA Cycle 3, while trying
  to give a probe persona sight of a fixture on another company.)
  `hr_timesheet/models/ir_http.py:19` does
  `result["user_companies"]["allowed_companies"][company.id].update(...)` for
  every company on the user, while `allowed_companies` is built from the
  session's narrower allowed set — so `/bizapp` answers 500 with `KeyError: 1`
  for that user, and only for that user. It is a pre-existing multi-company
  defect in a core-adjacent module and it is REPORTED, not patched (W68.3).
  Practical consequence for anyone validating: keep probe personas
  SINGLE-COMPANY and re-point them when you need to see another company's data;
  and when a 500 appears mid-validation, check whether the PUBLIC site is still
  200 before assuming your own deploy did it (it was, throughout).
- **W101 A source gate written the obvious way fails on the paragraph that
  explains it — so every one of them needs a COMMENT STRIPPER, and W48's
  corollary is not a warning, it is a required helper.** (IA Cycle 4. Six of
  eighteen first-run failures, in three modules, all the same mistake.) The
  gates were "no `fa fa-` class survives", "`typeof Chart` is gone", "the board
  never says `clearBreadcrumbs: true`" and "the facade never names
  `action_mail_report`" — and every one of those strings is exactly what the
  file's own header has to say to explain why the thing was removed. A gate
  that reads the whole file therefore fails on its own documentation, and the
  tempting repair (delete the sentence) throws away the only thing that stops
  the next reader putting the code back.
  Rules: (1) a source gate reads `_code(src)` — the file with `//`, `/* … */`
  and `#` comments removed — never the raw text. The three Cycle-4 test files
  each carry that fourteen-line helper for exactly this reason; (2) a REGION
  gate is delimited at BOTH ends. `test_the_ledger_is_read_only_this_cycle`
  first split on the ledger header and ran to end of file, swallowing the
  config wizards below it — which create policies and tax tables because that
  is what they are for. Explicit start AND end markers, and a complementary
  assertion that the region still contains what it is supposed to (W64's
  shape); (3) a needle that stops at the first `)` is not a needle:
  `getattr\(([^)]*)\)` reported `getattr(w.with_context(x=True), method)` as a
  getattr on an expression. Gate the ARGUMENT that matters, which here is the
  second one.
- **W102 W97 again, in the module whose own docstring quotes it.** (IA Cycle 4,
  found on the live run within a minute of the Statutory Data view first
  rendering.) `vietnam.insurance.adjustment` and `vietnam.employee.dependent`
  are scoped by their OWN `company_id` rule; `hr.employee` is scoped more
  tightly on this database. So `search([])` returned rows the caller may read,
  the ledger dereferenced `employee_id.name` to render a column, it hit the one
  employee (id 28) the rules hide, and the client showed "This table could not
  be loaded" — 45 readable rows lost to one refusal, message naming neither the
  row nor the reason. The dependents table rendered perfectly at the same
  moment, because its newest 400 rows happened not to include that employee: a
  correct count and a poisoned row look identical, which is why W97 says to
  walk the rows BACK to their owner rather than count them.
  What Cycle 4 adds to the rule: (1) the scope is a SUBQUERY
  (`('employee_id', 'in', Emp._search([]))`), not a list of ids — this tenant
  has 4 500 employees and a domain is not a place to put them; (2) it keeps
  ownerless rows explicitly (`'|', ('employee_id','=',False), …`), because a row
  about no person is hidden by no rule; (3) a THIRD model reached from a drawer
  field (the adjustment's `applied_payslip_id`) is guarded at the dereference
  rather than by scoping the whole table — a drawer field degrading to blank is
  proportionate where a grid vanishing is not.
  General form, and the reason it recurred: the rule is about the models a row
  DEREFERENCES, not about the model you searched. Reading your own docstring is
  not the same as checking your own many2ones.
- **W103 A cloned database needs its SIGNALLING table repaired, and both of the
  obvious repairs report "0 tests" as a success line.** (IA Cycle 4, three test
  rounds lost to it.) Running a suite on a `pg_dump | pg_restore` clone keeps
  production out of the way entirely — no second stop-window for tests — but
  the restore leaves `orm_signaling_registry`'s SEQUENCE behind its rows, so the
  first registry load answers `duplicate key value violates unique constraint
  "orm_signaling_registry_pkey"` and the run ends
  `0 failed, 0 error(s) of 0 tests`. That is W81's trap exactly: a green line
  over a run that never happened.
  The obvious fix — `TRUNCATE orm_signaling_registry` — swaps one silent
  failure for another: `Registry.signal_changes` then reads NULL and dies with
  `unsupported operand type(s) for +=: 'NoneType' and 'int'`, printing the SAME
  "0 tests" line. The table needs a ROW and a sequence AHEAD of it:
  `setval(pg_get_serial_sequence('orm_signaling_registry','id'),
  GREATEST(COALESCE(MAX(id),0),1))` then one `INSERT … DEFAULT VALUES`.
  Rule that generalises past this table: after any clone, read the TEST COUNT,
  never the pass/fail line. "0 of 0" and "181 of 181" are both green and only
  one of them is evidence. Related: `--no-http` does NOT stop `odoo-bin`
  binding the configured port on this build — a suite run beside a live server
  needs `--http-port=<free>`, or it dies with "Port 8069 is in use" before a
  single test runs.
- **W104 A deleted file is still on the server, because the deploy's second hop
  may never prune.** (IA Cycle 4, and it is W93's price.) `--delete` belongs to
  the STAGING rsync and never to the hop into the shared addons directory, so a
  file removed from the repo — `payroll_report.css` and `wf_breadcrumb.css`
  here — stays on disk indefinitely. It is harmless as long as the MANIFEST no
  longer lists it (the bundle is built from the manifest, not from the
  directory), which is why the gate asserts the file out of
  `web.assets_backend` rather than off the disk. But it is not tidy and it is
  not nothing: a future author reading the addons directory sees a stylesheet
  that no longer exists in git.
  Rule: a deploy that DELETES a file removes it from the server BY NAME, in the
  same step, and the test asserts the manifest rather than the filesystem —
  because the test also runs on a machine where the file was never deployed.
- **W105 A cockpit that reads with the CALLER's rights shows zeros where a
  sudo'd one shows money, and neither of them is broken.** (IA Cycle 4,
  discovered while photographing the re-skinned Payroll Report.) The report
  renders 902 employees and `0` for gross, net, deductions and every variance,
  on a run whose payslip lines hold ₫21.0B of GROSS in SQL. The cause is not the
  report: `hr.payslip.line` carries exactly two non-global record rules on this
  database — "employee self-service (own)" and pb_demo's "all payslip lines" —
  and there is no OFFICER or MANAGER rule at all. So every payroll manager who
  is not a demo user reads zero lines through the ORM, silently, while
  `pb_insights` (which reads under `sudo()` behind its own `_require()` gate)
  shows ₫18.63B on the same screen ten seconds earlier.
  Rules: (1) when two surfaces over the same data disagree by everything, check
  which of them is sudo'd before suspecting either one's arithmetic — this is
  W62's "two surfaces, one threshold" with permissions in place of a tolerance;
  (2) a model whose ACL grants read to a tier that NO record rule then admits is
  a permission gap, not a permission decision, and it is invisible from the ACL
  alone; (3) it is REPORTED, never patched mid-cycle: a record rule on payslip
  lines is a money-visibility change and belongs to whoever owns that decision.
- **W106 `pb.sidebar.item.restricted` is INERT on an UNGATED item, so a demo lock
  cannot follow a door that became ungated.** (IA Cycle 5, remapping pb_demo's
  lock onto the cut-over rail.) `get_sidebar_data._state()` returns
  `(visible, NOT locked)` the moment `_has_access(item)` is true, and
  `_has_access` is true for everybody when the item carries no `groups_id` — the
  upsell branch is reachable only for an item the user could not otherwise open.
  pb_demo's lock has always worked because every item it named WAS gated (the
  ADMIN block at `base.group_system`, Import Data at the payroll tiers). The
  Cycle-5 rail is eight UNGATED hub items on purpose: each hub gates its own
  lenses from the ACL of the model behind them (W95), which is narrower and more
  honest than a rail gate. So `restricted = True` on the Settings item would have
  been a flag with no effect, written by a hook that logs a success line and
  proved by a test that reads the flag back and finds it set.
  `pb.sidebar.section.restricted` has no such condition — `get_sidebar_data`
  computes `sec_locked = section.restricted and not is_admin` and nothing else —
  so the lock moved up a level and the whole SYSTEM block renders with a padlock.
  General form: when a flag's effect is conditional on ANOTHER field, moving the
  flag to a record where that field is empty is a silent no-op. Read the
  CONSUMER, not the flag; and a lock is proven by opening the surface as the
  locked persona, never by asserting the boolean.
- **W107 A rail cutover is spread over as many modules as the rail is, and half
  their data files are frozen — so the retirement list belongs to the module that
  owns the RAIL, and a hand-applied migration needs a gate that reads the others
  back.** (IA Cycle 5: thirty-four items retired across eight modules.)
  `pb_sidebar`'s own file is `noupdate="0"`, so `-u pb_sidebar` applies its
  twenty-eight declaratively once the pre-migrate has cleared any stored flag
  (W27). The other six cannot be reached that way: five live in
  `<odoo noupdate="1">` files that are frozen ON PURPOSE, and one belongs to a
  module that may simply not be in this upgrade's `-u` list — and upgrading
  `pb_sidebar` alone must still produce the right rail, because `pb_learn`'s
  section sits on the sequence the System section now takes and two sections on
  one number order themselves by install accident (W70, one level up).
  So the post-migrate hand-applies those six plus three moves, and W27's warning
  about hand-applied values drifting from the XML is answered by a gate that
  walks each table back to the file that DECLARES the record and fails on any
  disagreement. Two corollaries: (1) idempotency is a property of the GUARD, not
  of the run — every retirement writes only while the record is still on a
  pre-cutover sequence, which is also what stops a later migration overruling an
  administrator who deliberately re-enabled one; (2) put the hub's rail ITEM in
  the hub's own module, never in `pb_sidebar` — a rail entry on a database whose
  hub module is not installed is a button whose action does not resolve (W79),
  and the convention already existed (`pb_mission`, `pb_audit`, `pb_tenants`);
  (3) **a migration script's own logger is silent by default.** Odoo loads it
  through `importlib` with the FILE STEM as the module name, so
  `logging.getLogger(__name__)` — the idiom every migration in this codebase
  uses — yields a logger called `post-migrate`, OUTSIDE the `odoo.` namespace
  that `--log-level=info` configures. Its INFO lines never reach the log. That
  is how Cycle 5 spent an hour unable to tell "the migration ran and wrote
  nothing" from "the migration never ran", with the retirements demonstrably
  applied on the database in front of it. Name the logger
  (`logging.getLogger('odoo.addons.<module>.migrations')`), and prove the
  script's IDEMPOTENCY by executing `migrate()` twice from a shell rather than
  by re-running `-u` — an upgrade only runs a migration on a version CHANGE, so
  the second `-u` proves nothing at all.
- **W108 Retiring a rail item does not only change the rail: anything that asks
  "is this in your menu" through `get_sidebar_data` gets a different answer.**
  (IA Cycle 5, found by reading `pb_learn` rather than by a failing test.)
  `learn.runtime._visible_sidebar_item_ids()` calls `get_sidebar_data()`
  deliberately — so the Coach and the sidebar can never disagree about what a
  reader can reach — and `bootstrap()` marks a station `visible: False` when its
  leaf is not in that set. Nineteen of pb_learn's stations name a leaf this
  cutover retired, so every one of them now reads "not in your menu", and
  `learn.intent._capability` answers `no_access` for their screens: a learning
  system telling a payroll manager they cannot see Payslips, on a database where
  they can. NOTHING FAILED. `test_bundle.py::test_07` only checks that the leaf
  still RESOLVES, which it does, because retirement is not deletion — the exact
  property W18 exists to preserve is what makes this invisible.
  Rules: (1) before retiring a rail record, grep for `get_sidebar_data` and for
  the xmlid across the WHOLE repo, not just the module that declares it;
  (2) a test that asserts a leaf EXISTS is not a test that the leaf is
  REACHABLE, and the two diverge exactly when a retirement happens, which is the
  only time it matters; (3) the repair is NOT to re-point the map at the hub
  leaves, and that is worth writing down because it is the obvious move and it
  is wrong: `learn.screen._primary()` reads its action matchers off the SAME
  leaf, so seven pay-run stations pointing at one Pay Run hub item would make
  the Coach ground every one of those screens on whichever resolved first —
  trading a wrong label for a confidently wrong answer. Separating "which leaf
  identifies this screen" from "which rail item reaches it" is a pb_learn design
  change, so this is a REPORTED hand-back rather than a cascade into a module
  the phase was not asked to touch (W76.2).
- **W109 A heuristic that decides whether your own CHROME renders has exactly
  one wrong answer, and it hides the chrome rather than showing it — so nobody
  reports it.** (IA Cycle 5, found by walking the highlight matrix rather than
  by anything failing.) `pb_sidebar.js::_resolveVisibility` showed the rail when
  the current app was a payroll app OR when the action's tag / xmlid / res_model
  "looked Payobook" — `startsWith("pb_")`, `includes("hr_payslip")`, and so on.
  Every client action in the product satisfies that except one: the Payroll
  Report's tag is `payroll_report_dashboard`. Opening that cockpit from a
  bookmark therefore rendered it with NO SIDEBAR AT ALL, which reads as a
  deliberately full-bleed screen rather than as a defect, and it had been doing
  so since the cockpit was written. The cutover surfaced it because the Insights
  item now CLAIMS that tag and the highlight could not land: there was no rail
  on screen to light.
  The repair is not a longer name list. `_isClaimed(action)` asks the three
  match indexes `_resolveActive` already resolves the highlight from, so
  "should the rail be here" and "which item is active" can no longer disagree —
  a surface a rail entry says it owns is a surface the rail belongs on.
  Rules: (1) prefer a question with an INDEX behind it to a question with a
  naming convention behind it, especially for chrome — a wrong answer that
  removes navigation is invisible to the person who most needs it; (2) when two
  pieces of logic answer neighbouring questions about the same object
  (is it mine / which of mine is it), give them one source; (3) a matrix walk is
  worth doing even where every individual case looks obvious — this one case was
  1 of 14 and nothing else would have found it.
- **W110 The DEFAULT value of a shared lazy string is a second object, so the
  rows that name nothing and the rows that name the constant land in different
  buckets.** (IA Cycle 5's ⌘K promotion.) Cycle 3 already knew `_t()` returns a
  new `String` subclass per call and exported `G_SURFACES` so that every module
  adding a palette row would key the render Map on ONE value. What nobody
  noticed is that `<HubPalette/>` also minted its own `_t("Surfaces")` as the
  fallback for a row with no `group` — and every hub's palette rows omitted
  `group`. Two objects, two Map keys, the word SURFACES drawn twice. It was
  invisible for three cycles because the hub rows all sorted to the BOTTOM of
  the list; Cycle 5 promoted them to the top, interleaved them with the seed
  rows, and the duplicate heading appeared in the middle of the palette.
  Rules: (1) a shared identity constant has to include the DEFAULT — export the
  fallback and re-export it as the shared name, rather than writing the same
  literal in two files; (2) when a bug's symptom is "a heading appears twice",
  suspect object identity before suspecting the data; (3) an ordering change can
  make a latent grouping bug visible without changing the grouping code at all,
  which is why a promotion is worth looking at with fresh eyes rather than only
  re-running the gates.
- **W111 An ACL without a record rule is UNLIMITED; a record rule without an ACL
  is INERT — and a user in two groups gets the UNION of whichever rules exist,
  which is how a payroll manager ends up reading one payslip's lines.** (IA
  Cycle 6, executing W105's owner ruling.) W105 recorded the symptom: ₫21.0B of
  payslip lines in SQL, `0` on the ORM-reading Payroll Report, and a sudo'd
  cockpit showing the money ten seconds earlier. This is the mechanism, because
  the mechanism is what makes the repair reviewable.
  Odoo ORs the record rules of every group the user holds and applies NO
  restriction at all when the user is in no group that has a rule for that
  model. `hr.payslip.line` had four ACLs and two rules, and the two rules were
  for `base.group_user` (own lines) and the demo group. Every payroll tier is
  ALSO `base.group_user` — so the ESS rule was the only one that applied to them
  and it won by being the only one there. The tier was not denied; it was
  quietly narrowed to itself. Had those tiers *not* been internal users, the
  same table would have read UNLIMITED.
  Rules: (1) a model whose ACL grants a tier read access with no rule admitting
  that tier is a permission GAP, and it reads as either "everything" or "almost
  nothing" depending only on what else the user happens to be in — never assume
  which; (2) mirror a rule by MODULE, GROUPS and DOMAIN together: the four
  mirrors this cycle live beside their twins (`om_hr_payroll`'s two,
  `pb_hr_payroll_base`'s two) with xmlids that pair by name, and
  `pb_payruns/tests/test_payslip_line_access.py` fails on a line rule that has
  no declared twin, on a pair whose groups differ, and on a pair whose domain is
  not the twin's re-rooted through `slip_id`; (3) the ACL is where breadth is
  decided, so a mirror ACL is granted READ only even where the payslip ACL also
  grants write — narrower than the twin is always safe, wider is a leak; (4) a
  payslip rule that admits nothing because its tier holds no ACL (the portal
  one) gets NO mirror, and the test asserts the tier still has no ACL, so the
  day somebody grants one this conversation happens before money moves.
  Adding records to a `noupdate="1"` data file is fine and needs no migration —
  `noupdate` blocks UPDATES of existing rows, and a new xmlid is a create.
- **W112 A broad `except` around a facade's button press turns a field-drift
  AttributeError into a sentence about the FILING, so the drift survives every
  release.** (IA Cycle 6, the five VN filings.) Odoo 19 deleted
  `hr.employee.address_home_id` and `hr.employee.bank_account_id` and renamed
  `gender` to `sex`. Four of the five VN government filings read one of those on
  every employee row. Nothing crashed visibly: `pb.filing.flow.generate` catches
  and re-raises as `UserError("This filing could not be generated: …")` at
  `_logger.info` level, so the operator read it as "this filing is not ready"
  and the traceback never reached a log anyone greps. C4 shipped 2 of 5 filings
  and recorded the other three as a data problem.
  Three rules came out of the repair: (1) when a country pack owns the master
  data, resolve from the PACK, not from core — `vietnam_province /
  vietnam_district / vietnam_ward` are already the three administrative levels a
  BHXH form asks for, which no core Odoo field is, and `private_city` is free
  text with nothing below it; (2) resolve a payment identifier the way the
  module that PAYS resolves it — `bhxh630` now reads the same three
  `vietnam_bank_*` columns and the same `pb.bank.registry.match()` that
  `pb_pay_delivery` pays salaries from, because a filing that names a different
  account from the transfer is a reconciliation problem nobody finds until the
  money has moved; (3) `work_contact_id` is NOT a home-address substitute — it
  is the office, and a confidently wrong address is worse than a blank one.
  Corollary about degrading gracefully: the probes are ORM-registry reads
  (`'vietnam_province' in emp._fields`), never `try/except`, and
  `pb_hr_govt/tests/test_odoo19_employee_sources.py` asserts that on a database
  WITH the pack the pack's branch is the one taken — a fallback chain whose
  first leg is never exercised is indistinguishable from one whose first leg is
  dead (W79).
- **W113 Separating "which leaf IS this screen" from "which rail item REACHES
  it" is one resolver, not two answers — and the surface nobody was looking at
  had the worse bug.** (IA Cycle 6, implementing W108's hand-back.) W108
  predicted the failure and forbade the obvious repair. The implementation added
  the third fact: `learn.intent._capability` tested rail membership too, and it
  tested it BEFORE the group ladder, so between Cycle 5 and Cycle 6 the Coach
  answered `no_access` for **every screen to every reader except a super
  admin** — a learning system telling a payroll manager they cannot see
  Payslips. The Journey map merely looked wrong; the Coach was actively lying,
  and no test saw either, because `test_bundle.py::test_07` asserts the leaf
  RESOLVES and `env.ref` resolves an inactive record.
  Shape of the repair: `learn.runtime._reach_index()` folds every LIVE rail
  item's four match dimensions into three flat maps — the server-side twin of
  `pb_sidebar.js::_buildIndex`, built from the same `get_sidebar_data()` payload
  the visibility set already comes from — and `_station_reach()` is the ONE
  place the three verdicts (visible / missing / reached-via) are decided, called
  by both `bootstrap` and `_capability`. Identity is untouched: `_primary` and
  `_matchers` still read the retired leaf through `env.ref`, and a gate asserts
  no two screens share a primary pair, so the "just re-point sidebar_key at the
  hubs" simplification breaks a test instead of grounding seven pay-run screens
  on one item.
  Two details worth carrying: the probe order is **tag first**, not
  `_resolveActive`'s xmlid-first — four retired leaves (Full & Final, Proration,
  Retro, Government Reports) declare an `action_xmlid` no live item claims, so
  an xmlid-first probe answers None for exactly those four and looks like
  "these really are unreachable". And the index uses `setdefault` where the
  rail's uses assignment: last-writer-wins is a defect on the rail (W71) and
  first-writer-wins is the safer half of it here, because a reader is sent to
  the item that declared the surface rather than to whichever indexed last.
- **W114 W101's comment stripper is not optional, and a SYNTACTIC pattern is
  better than a stripped one.** (IA Cycle 6 — the fifth and sixth bite, in two
  modules, in one afternoon, in gates written by someone who had just re-read
  W101.) W48's corollary noticed it, W72 hit it in XML comments, W101 made the
  stripper a required helper after six of eighteen first-run failures in Cycle
  4. Cycle 6 still shipped two gates without one: `pb_hr_govt`'s field-drift
  gate flagged the docstring that says "Odoo 19 renamed `hr.employee.gender` to
  `sex`", and `pb_hub`'s palette gate asserted `is_admin` does not appear in a
  file whose header explains why `is_admin` is computed server-side.
  What Cycle 6 adds to W101 is the better of the two fixes, because a stripper
  is a second thing to remember and a pattern is not: make the match
  SYNTACTIC, so prose cannot satisfy it. The drift gate now matches
  `(?<![\w.])[A-Za-z_]\w*\.<field>\b` — an attribute read off a BARE local
  name — and `hr.employee.gender` can never match it, because `employee`
  follows a dot. Reach for the stripper (W101) when the thing you are
  forbidding has no syntax of its own, as `is_admin` does not; reach for a
  syntactic pattern whenever it does. And note the shape of the near-miss both
  times: skipping lines that START with a comment marker survives neither a
  docstring nor a block comment.
- **W115 A partial staging tree on the addons path breaks every test that WALKS
  the addons directory — and the failure names your feature, not your setup.**
  (IA Cycle 6.) Production discipline says test before the shared tree changes,
  so the eight edited modules were rsynced to `/odoo/c6addons` and the clone run
  with `--addons-path=/odoo/c6addons,/odoo/odoo-server/addons`, which shadows
  correctly and keeps production files untouched. It also means
  `get_module_path('pb_hub')` resolves inside the staging dir, and
  `pb_hub/tests/test_static.py::test_every_palette_entry_points_at_a_registered_action`
  walks `os.path.dirname(...)` of it looking for `registry.category("actions")`
  registrations — finding eight modules instead of two hundred, and reporting
  twenty-five palette entries as pointing at nothing.
  Rules: (1) a shadowed addons path is the right tool for proving a DIFF and the
  wrong one for proving a SUITE; run the suite again against the real tree
  before claiming a green regression; (2) a test that walks the addons directory
  should say so in its docstring, because that is the sentence that turns a
  confusing failure into a five-second diagnosis; (3) the same run also disabled
  every `ir.cron` on the clone for safety, which failed a gate asserting a cron
  is active — `--max-cron-threads=0` is the control that actually stops crons
  firing, so the FLAG can and should be left matching production.
- **W116 `ir_module_module` is a PER-DATABASE snapshot, so a shared addons tree
  that gains a module silently disables every dependent on every database whose
  list is stale — and the only symptom is a cron.** (IA Cycle 6, workstream 5;
  root cause of the `acme` / `payobook_template` errors C5 reported as
  pre-existing.) The golden template was built on 2026-08-09. `pb_wf_kit` (P0)
  and `pb_hub` (IA C1) were written after it, so no tenant database has an
  `ir_module_module` row for either. Their code nevertheless sits in the shared
  addons tree that every database loads, and modules those tenants DO have
  installed — `pb_integrations`, `pb_structures`, `pb_govt_reports`,
  `pb_hr_workforce` — later gained a `depends` on them. On the next restart the
  module graph could not satisfy those depends and SKIPPED 27 modules.
  Everything about that is quiet: `module_graph` logs `some depends are not
  loaded (pb_hub, pb_wf_kit), skipped` at WARNING among hundreds of warnings,
  `ir_module_module.state` still says `installed` for all 27, and the registry
  loads in 0.9s and reports "Modules loaded." The only loud consequence is that
  an `ir.cron` whose server action names a model from a skipped module raises
  `KeyError: 'biz.doc.ocr.job'` every five minutes, forever.
  Rules: (1) adding a `depends` to an existing module is a DEPLOY step on every
  database, not just on the one you are working on — enumerate the DBs on the
  cluster and refresh each one's module list; (2) "0 modules skipped" belongs in
  the post-deploy check beside `latest_version` (W33.2), because a skipped
  module is invisible in `state`; (3) a cron failure that names a MODEL is
  almost never a data problem — ask whether the model is in the registry before
  reading the cron's code; (4) the repair is `-u base` (which runs
  `update_list()`) then `-i` the roots of the skip chain, and it must stop
  there: upgrading `pb_sidebar` on a pre-cutover tenant would run the Cycle-5
  rail migration and retire thirty-four items into hubs that database does not
  have (W79/W107.2).
- **W117 A one-shot instruction seeded on ARRIVAL starts at nonce 1, because 0
  is what the receiver already holds.** (IA Cycle 6, extending W44's `pb_cmd` to
  cross-cockpit deep links.) Insights' bonus-hours tile has an exact destination
  — the Overtime desk's bonus VIEW — and W26's arrival protocol carries a lens
  but not a verb, so `pb_mission` now also reads `pb_cmd` off the action context.
  The trap is arithmetic: every lens tracks `this._cmdNonce`, initialised to 0,
  and runs an instruction when the incoming nonce DIFFERS. Seeding the shell's
  state with `{name: "bonus", nonce: 0}` therefore delivers a verb the lens is
  guaranteed to ignore — a deep link that silently lands on the wrong view, with
  no error anywhere. Seed at 1. Two rails that keep it safe: the verb is
  accepted only for the lens being opened, and a lens that does not know the
  verb ignoring it is still correct behaviour (W44.3), so widening the protocol
  cannot make an unknown verb land on the wrong thing. And the gate that pinned
  the old literal default was REVERSED AT THE SITE with the reasoning (W76.3),
  not quietly deleted: it now pins the shape and the seeded value instead.
- **W118 A cached asset bundle can hide a STALE MODULE ON DISK for weeks, and
  the moment you purge the cache the missing file takes a whole cockpit with
  it.** (IA Cycle 6, and the one production incident of the cycle.)
  `/odoo/odoo-server/addons/pb_wf_kit` was at version **19.0.1.4.1** on disk
  while `ir_module_module.latest_version` said **19.0.1.5.1** — a stale rsync
  from an earlier session, exactly the "files never rsynced current" failure
  the deploy notes already warn about. The difference between the two versions
  was one line in the manifest: `wf_command_palette.js` in
  `web.assets_backend`. Because prod mode serves the COMPILED bundle out of
  `ir_attachment`, and the cached bundle had been built when the file was still
  listed, Mission Control kept working perfectly. Purging the bundle after a
  deploy — the standard ritual — rebuilt it from the stale manifest, and
  `@pb_wf_kit/js/wf_command_palette` vanished. `@pb_mission/js/pb_mission`
  declares it as a dependency, so the module was defined and never EXECUTED:
  the Workforce action tag was simply not in the registry, `doAction` rejected,
  and the drill that had worked ten minutes earlier did nothing at all. Zero
  console errors, zero failed module loads, `odoo.loader.failed.size === 0`,
  and the whole page rendering normally — because only one module of two
  hundred was missing.
  How to find it in one step: fetch the SERVED bundle and ask whether the
  module is `odoo.define`d in it, then diff `odoo.loader.modules` against the
  dependency list Odoo compiled into the `define(` call. A dep that is in the
  list and not in `modules` is a file that is not in the bundle, which is a
  MANIFEST fact, not a code fact.
  Rules: (1) version-diff repo↔server for EVERY module in the reverse-dependency
  closure before a deploy, not only the ones you edited — a checksum of the
  eight modules you rsynced proves nothing about the ninth; (2) an asset purge
  is a REBUILD, so treat it as a deploy of every module's manifest and re-check
  the page afterwards; (3) when a click stops working with a clean console,
  ask whether the component's module is in `odoo.loader.modules` before
  suspecting the handler — W74's blank-backend cousin, one module wide instead
  of one bundle wide.
- **W119 `service odoo-server stop` followed immediately by an upgrade can race
  the START, and the upgrade loses.** (IA Cycle 6, second production window.)
  W83 already records that the stop can leave the process running. This is the
  other half: a `stop; sleep 3; odoo-bin -u …` script had its `-u` answered with
  `psycopg2.errors.SerializationFailure: could not serialize access due to
  concurrent update` on `ir_module_module_dependency`, then `Failed to load
  registry`, then `EXIT=255` — because the service had come back up and was
  loading the same database at the same instant. The upgrade rolled back
  cleanly and the site stayed healthy, so the only evidence was the exit code:
  the log line the deploy prints is `UPG=255`, and everything after it in the
  script (the asset purge, the restart, the health check) succeeded and looked
  like a good deploy.
  Rules: (1) after `stop`, POLL for zero `odoo-bin` processes rather than
  sleeping a fixed three seconds; (2) an upgrade's exit code is part of the
  deploy evidence — a script that prints `UPG=$?` must also FAIL on it, or the
  number scrolls past; (3) `EXIT=255` with a healthy site means the upgrade did
  not happen, not that it was harmless — check `latest_version` (W33.2) before
  concluding anything shipped.
- **W120 `-u X` upgrades every INSTALLED module that DEPENDS on X, so an exclusion
  list is only honoured while nothing you upgrade is a dependency of the thing you
  excluded.** (IA Cycle 7, bringing `abm` up to `payobook`'s module set.) The
  cycle's binding non-goal was "`biz_debrand` stays untouched — another session's
  work", and the upgrade list was written accordingly: 37 modules, `biz_debrand`
  deliberately absent. It was upgraded anyway, from 19.0.2.1.0 to the disk's
  19.0.2.3.0, because `web_debranding` WAS on the list and `biz_debrand` depends
  on it: Odoo marks the reverse-dependency closure `to upgrade` so a dependent is
  never left running against a changed dependency.
  Rules: (1) an exclusion is a property of the CLOSURE, not of the list — compute
  `depends`-reverse of every excluded module and check the intersection before
  running, because the exclusion silently does not hold otherwise; (2) the damage
  radius of that mistake is the version gap: the module went to the version on
  DISK, which on a shared addons tree is whatever the other session has deployed,
  not what the reference database is running — so "parity with payobook" and
  "parity with the tree" are two different targets and the cascade always picks
  the second; (3) the tell is in the post-run version diff, which is why the
  evidence for a module-delta install is a version comparison per module and not
  a count.
- **W121 A post-migrate that UNFREEZES a `noupdate` record runs AFTER that
  upgrade's data load, so the record only starts tracking its file on the NEXT
  upgrade — and a catch-up that crosses both the unfreeze and a later data change
  needs TWO passes.** (IA Cycle 7, and the one thing the abm rehearsal caught that
  a version count would not have.) `abm` sat at `pb_timeoff` 19.0.1.0.1 and was
  upgraded straight to 19.0.1.2.0. That single upgrade contains both halves of the
  W13.1 story: the P0 post-migrate at 19.0.1.0.3 (clear the stored `noupdate`
  flag, move Leave 30 -> 32) and the Cycle-5 retirement in the data FILE (seq 909,
  `active` False). Odoo loads the data file BEFORE post-migrate, so the loader saw
  a still-frozen record and skipped it; the migration then cleared the flag and
  wrote 32. Result: exit code 0, `latest_version` correct, and one rail item live
  at sequence 32 on a database that was supposed to have the eight-item rail.
  Rules: (1) after any catch-up upgrade that crosses an unfreeze migration, run
  `-u <module>` a SECOND time — the data load is idempotent and the second pass is
  the one that lands the file; (2) never accept a version number as proof that a
  data file has been applied (W33.2 proves the code shipped, not the rows); (3)
  the assertion that actually catches it is a per-XMLID table diff against the
  reference database — `pb_sidebar_item` joined to `ir_model_data`, compared row
  by row — which found exactly one disagreement out of 60.
- **W122 A host-derived `dbfilter` rejects a CLONE by name, so every HttpCase in
  the run fails and the failures name YOUR feature.** (IA Cycle 7.) The box serves
  tenants with `dbfilter = ^%d$`, so a suite run against `abm_c7` logs
  `Logged into database 'abm_c7', but dbfilter rejects it; logging session out`
  once, at WARNING, and then answers 404 or 303 to every authenticated request the
  tests make. The first run showed 7 failed / 4 errors, and the two that looked
  most alarming were the new session-guard tests — which were, in that run, only
  measuring the dbfilter.
  Rules: (1) always pass `--db-filter='^<clone>$'` when running a suite on a clone
  of a tenant-filtered server (it is the same class of setup-not-feature failure
  as W103's signalling table and W115's staging path); (2) before believing ANY
  failure on a database shape that has never run the suite before, run the same
  suite from the untouched tree and diff the failure SETS — Cycle 7's combined run
  ended 12 failed / 17 errors of 1474, and the baseline run of the same suite with
  the pre-cycle code ended 12 failed / 17 errors of 1467 with a byte-identical
  failure list, which is what turned 29 red lines into evidence of nothing.
- **W123 `session_info`'s two company collections come from different places, and
  only a monkeypatch can guard the crash — an `_inherit` is on the wrong side of
  its own `super()`.** (IA Cycle 7, closing W100.) `web`'s `session_info` builds
  `allowed_companies` from `res.users._get_company_ids()`, which is
  `@tools.ormcache('self.id')` and is invalidated only by `res.users.write()`
  (`_get_invalidation_fields`). `hr_timesheet`'s override then iterates the LIVE
  `user.company_ids`. Link a company to a user from the COMPANY side —
  `res.company.write({'user_ids': …})`, the Users tab of the company form, a data
  file, SQL — and nothing clears that cache: `company_ids` gains an id
  `allowed_companies` has not got, `hr_timesheet` subscripts it, and the user's
  every backend page load answers 500 (`KeyError: <company id>`).
  Measured, because the obvious other hypothesis is wrong: ARCHIVING a company
  does NOT reproduce it. Reading the `company_ids` many2many applies
  `active_test`, so the archived id disappears from both sides; the two production
  `KeyError`s of 2026-08-19 named ACTIVE companies (1 and 5), which is this path's
  fingerprint and not the archived one's.
  Rules: (1) when two collections that "should" be the same disagree, find which
  of them is CACHED before theorising about the data — the cache key here is the
  user id and nothing about companies, so the entry cannot expire on a company
  event; (2) a model-inheritance override cannot guard a crash that happens inside
  its own `super()` call: our class is the OUTERMOST one, the KeyError is raised
  below it, and being inner would require `hr_timesheet` to depend on us. The
  crash SITE has to be replaced (`biz_deroute/models/ir_http_session_guard.py`
  rebinds `hr_timesheet.IrHttp.session_info` to a copy whose only difference is a
  `.get()` and a warning), with a source gate pinning upstream's shape so the day
  Odoo fixes it the patch fails a test instead of quietly shadowing a fixed
  upstream; (3) ship the CAUSE beside the symptom — a `res.company.write` override
  that calls `env.registry.clear_cache()` when `user_ids` is in `vals` is the one
  line core is missing, and it costs nothing on a write nobody makes in a loop.
- **W124 A monkeypatch takes effect on a process RESTART, not on `-u`, and the
  difference looks exactly like a broken patch.** (IA Cycle 7, ten minutes of
  believing a validated fix had not worked, on production.) The guard was rsynced,
  `-u biz_deroute` returned 0 on all four databases, `latest_version` moved, and
  the deliberately-divergent probe still got a 500 with the same traceback. Python
  had `odoo.addons.biz_deroute` in `sys.modules` from the running server's own
  startup — from BEFORE `models/` existed — and Odoo's registry reload re-reads
  data and rebuilds model classes, it does not re-import addon python. So the
  patch, and the new `ResCompany` class with it, existed on disk and in every
  short-lived `-u` process and in no request the site served.
  Rules: (1) any import-time patch, and any module that GAINS a `models/` package,
  is a RESTART deploy, not an upgrade deploy — put the restart in the same window
  or the change is not live; (2) the check that distinguishes "patch broken" from
  "patch not loaded" is a log line or an attribute the patch owns
  (`IrHttp.session_info.__name__`), asserted in the process that serves requests,
  not in the one that upgraded; (3) W68 still governs the restart: Cycle 7's ran
  at 21:43 UTC and another session stopped the same service at 21:45 for its own
  `-u` — two windows, ninety seconds apart, neither aware of the other, which is
  the argument for checking `ps -eo pid,cmd | grep "[o]doo-bin"` immediately
  before AND after, and for reporting contention rather than racing it.
- **W125 Dropping a cockpit's `sudo()` is a question about MODELS, not about the
  cockpit — and on a board whose money is raw SQL, the sudo was never hiding the
  money.** (IA Cycle 7, executing the owner's "Insights' sudo can now be dropped".)
  `pb_insights` reads its department leaderboard, statutory split and employer
  totals with `cr.execute` carrying an explicit `company_id IN %s`. Record rules
  have never applied to any of it, so removing `sudo()` cannot change one number
  there — what the blanket `su = self.sudo()` was actually covering was the ORM
  reads beside it: `hr.payslip.run` (no ACL for `group_payroll_analytics_user`),
  `hr.employee` (read granted to `hr.group_hr_user` and `base.group_system` only —
  none of the three gate groups), the hr_attendance ladder behind the pulse, and
  one `hr.payslip.line` `read_group` in the untyped-category fallback.
  So the sudo drop is four separate decisions, not one: `hr.payslip.run` gets a
  read-only ACL for the analytics tier (the model carries NO record rule, so the
  grant is exactly what sudo was giving) and the money reads as the caller; the
  headcount, the department-name lookup and the pulse keep a one-line sudo each,
  because dropping those does not narrow a section, it BLANKS it — `_safe()`
  swallows the AccessError and the tile renders as "not deployed", which is W105's
  symptom wearing a different hat; and the legacy line `read_group` keeps its sudo
  because `group_payroll_analytics_user` holds `hr.payslip.line` read only through
  `base.group_user`, whose one rule is employee self-service, so the caller-rights
  read would show that persona THEIR OWN payslip in place of the company's split
  (W111 exactly).
  Rules: (1) enumerate the ACL and the RULES of every model a facade touches
  before removing a sudo, and expect the answer to differ per model; (2) prove it
  with a payload diff per gate persona — Cycle 7 captured hero/trend/departments/
  statutory/snapshots/pulse for `base_manager`, `analytics_user` and `super_admin`
  on production data before and after, and the two JSON files hashed identically —
  a suite alone cannot say this, because the fixture has no ACL history; (3) every
  surviving sudo carries the paragraph that justifies it AND a row in
  `pb_insights/tests/test_sudo_drop.py::SUDO_SITES`, an AST gate rather than a text
  search, so a new sudo cannot arrive without that conversation and a removed one
  cannot vanish without noticing.
- **W126 Importing an addon you do not DEPEND on, at module level, reorders the
  class registry and can take a hook out of `ir.http` — the symptom was every
  database's LOGIN PAGE, and nothing else.** (IA Cycle 7, the cycle's production
  incident, 21:47-22:01 UTC, self-inflicted and self-found.) W123's guard has to
  patch `hr_timesheet.IrHttp.session_info`, and the obvious way to reach the
  class is `from odoo.addons.hr_timesheet.models.ir_http import IrHttp` at the
  top of the file. The file lives in `biz_deroute`, which depends on `web` alone
  and is `auto_install`, so it is imported very early — and that import drags
  hr_timesheet's `ir.http` class, and the chain behind it, into the class
  registry ahead of its place in the module graph. The `ir.http` composed from
  that order no longer runs `website`'s dispatch hook, so an anonymous request
  never receives its public user and `website.layout` renders against an empty
  `env.user`: `ValueError: Expected singleton: res.users()`, 500, on `/web/login`
  for **every database on the cluster at once**.
  Everything about that is quiet in the wrong way. `/web/health` stayed 200,
  `/` stayed 200, every already-authenticated `/bizapp` session stayed 200, the
  cockpit under validation rendered its money perfectly, and the log line is a
  `website/models/ir_ui_view.py` frame that names no custom module at all. It was
  found by a curl, twenty minutes late, while checking something else.
  How to isolate it in three runs, which is the durable part: start the SAME
  database on a private port with `--addons-path=<shadow>,<real>` and vary only
  the suspect module — (1) current tree: 500; (2) pre-cycle copy of the one
  module: 200; (3) a variant carrying every change EXCEPT the import: 200. The
  third run is what names the LINE rather than the commit, and none of the three
  touches the running service.
  Rules: (1) never import another addon's python at module level from a module
  that does not declare it in `depends` — and adding the depend is usually the
  wrong repair too, because it changes the install graph of every database;
  (2) do the reaching-into from `_register_hook()`, which runs after the registry
  is built: the import is then a `sys.modules` lookup that reorders nothing, and
  on a database without that addon nothing is imported at all. Some model in
  your module has to carry the hook — pick any model you already own, and NOT an
  `ir.http` inherit, which would put you back in the MRO you just broke;
  (3) `/web/health` is not a health check for this class of breakage. After any
  deploy that touches HTTP plumbing, curl `/web/login` and one anonymous website
  URL as well — the surfaces that have no session are exactly the ones a logged-in
  validator never sees.
