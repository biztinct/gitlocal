# WORKFORCE P1a — The Time hub: Timecards + Weekly Entry + Attendance Control become one surface

Program docs: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` (W-rules; W0.1 self-review applies),
`docs/WORKFORCE_REDESIGN_OPTIONS.html` (mockup A's Time hub is the visual target).
Prior phase: P0 report is reflected below — its six open questions are answered in §2.

## §1 Scope

Build **`pb_time_hub`** — one cockpit with lens tabs over the attendance dataset — and retire the
three sidebar items it replaces. This is the flagship Option-A merge: the owner's originally named
pain ("time entry display of individual employee + entry in a table format") must be fully solved by
the Week-Grid lens + person drawer.

**Binding non-goals:**
- No Today board, no renumbering of other sidebar items, no Payroll-Report move, no Overtime-Rules
  retirement — all P1b.
- Do not touch `pb_business_trip/data/pb_sidebar.xml` (P1b unfreezes it).
- Do not delete the legacy Timecards JS/CSS or the standalone actions — dead-code cleanup is a later
  phase; retired surfaces just leave the sidebar.
- No new approval logic, no engine work (P4). No Schedule work (P2).
- Don't rebuild pb_attendance_flow's composer/import internals — they're good; they get *embedded*.

## §2 P0 open questions — design answers (binding)

1. **Frozen sidebar files:** P1a ships the W13.1 unfreeze migration for `pb_attendance_flow` (clone
   the `pb_timeoff/migrations/19.0.1.0.3/post-migrate.py` precedent; version bump). `pb_business_trip`
   waits for P1b. Every sidebar assertion reads the DATABASE after `-u` (W13.1).
2. **`wf_context.state` writability:** keep the reactive exposed (consumers need `useState`), but the
   law is now **W16: `set()` is the only write door** — direct `ctx.state.x =` assignments are
   forbidden in reviews and grep-checked (T4). No proxy ceremony.
3. **Context shape:** grow `wf_context` with **`day`** (ISO date, defaults to today). Rules: `set()`
   normalizes; when `weekStart` changes, clamp `day` into that week (same weekday if possible);
   keep localStorage key `pbwf.ctx.v1` (additive field, no migration). No `rangeEnd` — the week is
   the canonical range; lenses derive.
4. **Person segment:** the person drawer in this phase is the first real consumer: clicking ANY
   avatar in any lens does `ctx.set({personId})` and opens the drawer (W5). The bar's typeahead does
   the same. Clearing = drawer close sets `personId:false`.
5. **Ribbon data:** per-cockpit for now — `pb.time.hub` exposes an officer-gated count/summary that
   internally calls the exception engine. The shared exceptions endpoint is deferred to P4 (noted).
6. **Legacy breadcrumb/goHome:** confirmed throwaway — Timecards dies now; Live Attendance,
   Workforce Dashboard die in P1b; Shift Roster in P2. Leave the handlers alone.

## §3 Verified plumbing facts (P0-current — do not re-derive)

- **pb_wf_kit (P0, commits f7b5e492/29aa05e6/8d3bb2b9):** service `wf_context`
  (`{departmentId, weekStart, personId, search}`, `set(patch)`, `onChange(cb)→unsub`, localStorage
  `pbwf.ctx.v1`, Monday-normalized local date math); `<WfContextBar features="…"/>` (already mounted
  in Weekly Entry — the pilot); `<WfDrawer title subtitle onClose>` 320px chassis (ESC + ✕);
  `<WfRibbon tone text actionLabel onAction/>`. Icons via `ic()`/`IC` in
  `pb_import_kit/static/src/js/import_icons.js` (W2).
- **Week Grid (lens source):** cockpit `pb_hr_workforce/static/src/js/attendance_weekgrid.js` (~373 L)
  + `attendance_weekgrid.xml` (embeds generic `<WeekGrid>` from
  `biz_week_grid/static/src/js/week_grid.js` at xml :49-55 with adapter/params/onData/onDirty/
  onFocus/onSaved props); facade `hr.attendance.weekentry`
  (`pb_hr_workforce/models/attendance_weekentry.py`, ~609 L) over hr.attendance,
  hr.overtime.request, hr.overtime.config, pb.ot.ceiling, hr.shift.planning,
  hr.holidays.public.line; right ceilings rail + sticky OT tray (submit/approve) live in the cockpit.
- **Timecards (lens source — UI dies, READ-MODEL survives):** facade `hr.attendance.timecard`
  (day-bars per employee on an hour axis, OT-type classification, Duration column), extended by
  `pb_business_trip/models/attendance_timecard_trip.py` (`_inherit = 'hr.attendance.timecard'`,
  trip bars + violet `.tc-bar-trip` overlay — re-tint that inline color to pbim primary when you
  render it in the new lens). The legacy UI `attendance_timecard.js` (inline template, orange,
  13 gradients) is NOT reused.
- **Attendance Control (lens source — embedded, not rebuilt):** component in
  `pb_attendance_flow/static/src/js/pb_attendance_flow.js` (~320 L) with INTERNAL views
  `board | composer | import`; template `pb_attendance_flow.xml` (~396 L); facade `pb.attendance.flow`
  (`models/attendance_cockpit.py`); exception engine `pb.attendance.exception.engine` whose
  `_get_exceptions` is DELIBERATELY underscore-private (security fix G-C1) — **never re-expose it
  publicly**; wrap it behind an officer-gated method (copy its own `_require_*` gate pattern).
- **Sidebar items to retire (verify `noupdate` per W13!):**
  - `item_wf_timecards` — `pb_sidebar/data/pb_sidebar_data.xml` :284-288, file noupdate 0, seq 30.
  - `item_wf_weekentry` — `pb_hr_workforce/data/pb_sidebar.xml` :6-15, file noupdate 0, seq 35.
  - `item_attendance_control` — `pb_attendance_flow/data/pb_sidebar.xml` :4-13, **file was
    noupdate 1 → W13.1 migration required**, seq 25.
- Cockpit assets pattern: `web.assets_backend`, scss → js → xml; client-action test URL
  `/odoo/action-<tag>`.
- C18 span-vs-worked_hours lesson (Sudima E): `check_in→check_out` span ≠ Odoo's lunch-deducted
  `worked_hours`. The drawer and lenses must be INTERNALLY consistent — see §4 WP-2 data contract.

## §4 Work packages (one commit each)

**WP-1 `pb_wf_kit` v-bump — context `day` + W16.** Add `day` per §2.3 (normalize, clamp-on-week-
change, default today). Extend `WfContextBar` with an optional day segment (`features` gains `day`) —
a small "‹ day ›" pill shown only when enabled. Tests for clamp behavior. Append **W16** (set()-only
writes) and **W17** (embedding pattern, from WP-3 below) to the conventions ledger in this commit.

**WP-2 New module `pb_time_hub`** (deps: `pb_wf_kit`, `pb_import_kit`, `pb_hr_workforce`,
`pb_attendance_flow`; NOT pb_business_trip — its timecard overlay arrives via the facade
inheritance automatically when installed).
- `ir.actions.client` tag `pb_time_hub`; OWL cockpit `PbTimeHub`, external templates, pbim tokens,
  indigo primary (W1).
- Shell per mockup A: hub header "Time" + `<WfContextBar features="dept,week,search">` + lens tabs
  **Timeline · Week Grid · Exceptions (n) · Import** + `<WfRibbon>` under the tabs when open
  exceptions > 0 ("N entries need review — … · Review exceptions →" jumps to the Exceptions lens).
- AbstractModel facade **`pb.time.hub`** (officer-gated like the flow cockpit):
  - `get_hub_summary(department_id, week_start)` → ribbon text + per-lens badge counts (internally
    calls the exception engine via its private method — gate first).
  - `get_person_week(employee_id, week_start)` → `{employee:{id,name,job,dept,badge,on_shift_now},
    days:[{date, sched, actual, entered, delta, flags[]}], totals:{sched,actual,entered,delta},
    ot:[{label, hours, tone}]}`. **Data contract:** `sched` = hr.shift.planning planned_hours (0/“—”
    when unplanned); `entered` = the same rows the Week-Grid lens edits (hr.attendance.weekentry);
    `actual` = sum of `worked_hours`; `delta` = entered − sched. Put this contract in the model
    docstring — future phases inherit it.
- **Person drawer** (`WfDrawer` first real consumer): opens on any avatar click in any lens or bar
  typeahead pick (§2.4); renders the §WP-2 payload as mockup A's drawer (Scheduled/Actual/Δ header
  chips, per-day table, OT chips, actions **File correction** → Exceptions lens composer prefilled
  for that employee+day, **Full profile** → `hr.employee` form `target:"new"` per W5).
- Security: sidebar item + facade both gated `hr_attendance.group_hr_attendance_user`+ (matches the
  Weekly Entry persona; Timecards was previously ungated — deliberate narrowing, note it in report).

**WP-3 Lens embedding (the W17 pattern — do it the same way twice).** Refactor minimally so each
source cockpit's BODY becomes an embeddable component while its standalone client action keeps
working (P1b retires the actions; other callers may still doAction them until then):
- Week Grid lens: extract the grid+ceilings-rail+tray body of `attendance_weekgrid` into an
  `embedded`-capable child (suppress its own header/context bar when embedded — the hub's bar rules,
  W4); mount in the hub.
- Exceptions + Import lenses: give `PbAttendanceFlow` an `embedded` prop + `initialView` (`board` |
  `import`); embedded mode hides its hero (hub header rules) and binds its date window to the
  context week; mount twice (Exceptions lens = board+composer flow, Import lens = import stepper).
- No logic forks (W6): one component, one facade, two mount points.

**WP-4 Timeline lens (the one genuine rebuild).** New OWL lens rendering the `hr.attendance.timecard`
read-model on pbim tokens: per-employee rows for the context week, hour-axis day bars (flat fills:
regular = pbim soft-indigo w/ indigo edge; OT types = amber/rose/cyan per the W1 chart order; trips =
primary-soft w/ plane glyph), per-row totals (Reg/OT/Total), a slim OT legend, avatar →
person drawer. No gradients (W3), no "With hours only" checkbox unless trivial (search covers it).
If the legacy facade returns presentation baked as inline styles (bar_left/bar_width %), reuse the
numbers — they're geometry, not chrome.

**WP-5 Sidebar swap + migration.** New item "Time" (icon `clock`, seq 30, action_tag `pb_time_hub`,
gate per WP-2) in `pb_time_hub`'s own data file (`noupdate="0"` — W13). Deactivate the three retired
items: `item_wf_timecards` + `item_wf_weekentry` via their (unfrozen) files, `item_attendance_control`
via the W13.1 unfreeze+deactivate migration in `pb_attendance_flow` (version bump). DB-assert all
four states in tests.

**WP-6 Cross-links (W5 sweep).** Grid cell flagged over-cap → Exceptions lens; Exceptions row
employee chip → person drawer; drawer "File correction" prefill; ribbon → Exceptions lens. Every new
avatar/row is a door — no dead ends in the hub.

## §5 Tests (committed with features, W9; never bare `--test-tags`)

- **T1** `pb_wf_kit` day-clamp tests green.
- **T2** `pb_time_hub` server tests: person-week math (planned vs entered vs worked_hours on a
  seeded week incl. an empty day), summary counts == engine output, non-officer RPC → AccessError,
  `get_person_week` on a cross-company employee → error/empty (scope to `env.companies`).
- **T3** Sidebar DB assertions AFTER `-u` (W13.1): Time item active @30, the three retired items
  `active=False` — read from `ir_model_data`-resolved records, not the repo.
- **T4** Static: `grep -rn "ctx\.state\.[a-z]* *=" <all workforce modules>` → 0 (W16);
  `grep -rn "linear-gradient\|fa-" pb_time_hub/` → 0; new-hex audit of pb_time_hub (only pbim
  values / var() fallbacks).
- **T5** Regression: existing `pb_hr_workforce` + `pb_attendance_flow` suites green under scoped `-u`.
- **T6–T14 Chrome-MCP live (W10):** hub loads at `/odoo/action-pb_time_hub`; all four lenses render
  + switch with zero console errors; Week-Grid lens saves an entry (verify the attendance row in DB,
  then restore it); context sync — set dept+week in the hub, open the standalone weekgrid action →
  same dept+week; person drawer numbers match a hand-checked DB query for one employee-week;
  drawer→File-correction lands in the composer prefilled; import lens dry-run works; ribbon count ==
  board count; retired items absent from the sidebar, Time present; screenshots
  (`p1a_hub_<lens>.png`, `p1a_drawer.png`, `p1a_sidebar.png`).
- **T15** Regression sweep of the remaining sidebar items (13 → 12 after this phase? count and
  assert: 14 − 3 retired + 1 new = **12 items**), all load, console clean.

## §6 Deploy & verify

Same live ritual as P0 (W10; ssh alias Payobook19v2, apex DB `payobook`, detached systemd-run unit,
`-i pb_time_hub -u pb_wf_kit,pb_hr_workforce,pb_attendance_flow,pb_sidebar`, asset-purge fallback,
never bare pkill, Chrome-MCP on https://payobook.com). Version bumps: every touched module patch-level;
`pb_attendance_flow` bump is REQUIRED for its migration to run (W13.1).

## §7 Report back

Commit hashes per WP; T1–T15 evidence; self-review notes (W0.1); W-rules appended; deviations +
reasons; explicitly answer: (a) does the Week-Grid lens still pass the P0 pilot behaviors
(persistence, refetch)?; (b) any facade slowness on the Timeline lens with a full-dept week
(row counts + ms)?; open questions for the P1b design (Today board + IA finale: Live Attendance /
Workforce Dashboard / Driver Tracking fold-in, Payroll Report relocation, Overtime Rules retirement,
section renumber + pb_business_trip unfreeze).
