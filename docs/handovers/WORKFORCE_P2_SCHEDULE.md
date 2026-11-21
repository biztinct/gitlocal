# WORKFORCE P2 — Schedule instrumentation: the roster becomes a canvas with cost, coverage & conscience

Program docs: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` (W-rules through **W28**),
`docs/WORKFORCE_REDESIGN_OPTIONS.html` (Gap 06 + the "Instrument the Schedule" roadmap row; Deputy
patterns in Part 3 are the behavioral reference: stats docked in the canvas, refuse-on-paste,
advisory warnings at edit time).
Prior phase: P1b's groundwork (§3 below quotes it) is verified — do not re-derive.

## §1 Scope

Rebuild the Deputy-inspired-but-2013 Shift Roster as **`pb_schedule`** — same capabilities, token
chrome, plus the three instruments the audit found missing: **labour cost per day column, coverage
required-vs-scheduled, and advisory warnings at edit time**. Retire the Shift Templates rail item
into a drawer. Rail lands at its final Option-A shape: **7 items**.

**Binding non-goals:**
- No Mission Control shell (P3), no tolerance/lock engine (P4), no AI auto-scheduling.
- No deletion of legacy files/actions (W18 retirement only; the legacy `shift_planning_grid` action
  keeps working until a later cleanup).
- **Do not depend on or import the `hr_shift` module** — it declares a DIFFERENT model also named
  `hr.shift.planning` (`hr_shift/models/shift_planning.py:15`); `pb_hr_workforce` correctly avoids
  it and so must you.
- Don't "fix" `hr.shift.planning.compliance_status` (stored, never refreshed — P1b finding); it's
  P4's decision. Base nothing new on it.
- Ceiling warnings are ADVISORY (overflow → bonus_hours by design, Phase K); never hard-block on
  them. The only hard rule surfaced pre-save is pb_young_worker's night constraint, which already
  raises on save.
- No payroll/money-path changes: `_pb_hourly_rate` is a READ helper for display math only (W12).

## §2 Verified plumbing facts (P1b groundwork — do not re-derive)

- **Legacy cockpit (chrome dies, plumbing survives):** `shift_planning_grid.js` (~540 L inline
  template; week⇄fortnight, Copy Week, Publish All + draft badge, Open Shifts row, leave overlay
  `spg-leave-cell`, conflict icons, 9-metric summary `.spg-summary-bar` at :86-108, template
  quick-create with color swatches; client talks to the facade via generic `_rpc` at :383 — **new
  facade methods need zero client plumbing**). Facade: TransientModel `hr.shift.planning.grid`
  (`shift_planning_grid.py`; `_detect_conflicts` :193 = overlaps only; `publish_shifts` bulk :261;
  `action_complete` exists on the MODEL but is not exposed via the facade). Data model:
  `hr.shift.planning` (stored `planned_hours` net of break, `actual_hours`, states
  draft/published/completed; W24: the exception engine sees `published`+, pb_demo completes past
  shifts). `hr.shift.template` (start/end/break, `shift_type`, `is_overnight`, `color` picker, NO
  search view). Extended by `pb_attendance_flow/models/shift_planning.py`.
- **Cost:** NO hourly wage anywhere in the dep chain (`hr.employee.hourly_cost` lives in
  `hr_hourly_cost`, NOT installed). `hr.contract.wage` Monetary on `state='open'` contracts,
  bulk-readable via `read_group(['wage:sum'])` (pb_people precedent). Denominators:
  `hr.payroll.structure.working_hours_per_day` (8.0) / `working_days_per_month` (22.0), fallback
  `resource.calendar.hours_per_day/hours_per_week`. The only existing derivation
  (`planning_scenario.py:644-655`) is a company average with hardcoded 176h + 1.5× — do NOT reuse.
  Anchor a per-contract rate on the `_get_contract_wage()` override point (`hr_contract.py:247`).
  OT rate multipliers: `hr.overtime.config.rate_multiplier`.
- **Coverage:** demand side does not exist at day grain anywhere (`pb.workforce.demand.line` is
  role×month; `hr.job.no_of_recruitment` is recruiting). Supply side exists (shift rows/day + the
  grid's `leaves` overlay).
- **Warnings:** `hr.attendance.weekentry.get_ot_ceilings()` (`attendance_weekentry.py:333`) is the
  RPC-safe per-employee `{mtd, ytd, cap_month, cap_year}` payload; the 90% "approaching" threshold
  precedent is `ot_desk.py:184`; `pb.ot.ceiling._allowance/_split` are private — call through the
  weekentry payload, not directly. Young-worker night hard rule: `pb_young_worker`
  (`shift_planning.py:17`), raises ValidationError on save.
- **Kit:** `pb_wf_kit` is already a dependency of `pb_hr_workforce`; `WfContextBar` / `WfDrawer` /
  `WfRibbon` / `WfPersonWeek` (extracted in P1b) are importable. `WF_ROW_CAP` = 200. Deep-link
  protocol = W26 (`pb_lens` + `pb_focus`).
- **Sidebar:** rail item "Schedule" (seq 20) currently points at the LEGACY `shift_planning_grid`
  tag; "Shift Templates" (seq 80) is `pb_sidebar/data/pb_sidebar_data.xml` :294-298 (noupdate 0).
  Rail labels are globally unique (W28). Hero titles still carry old names (P1b finding) — fixed in
  WP-6.

## §3 Design decisions (binding)

1. **New module `pb_schedule`** (deps: `pb_wf_kit`, `pb_import_kit`, `pb_hr_workforce`; NOT
  pb_young_worker — probe its model with `env.get()`/hasattr and degrade gracefully). New client
  tag `pb_schedule`; the rail item repoints to it; the legacy action stays registered.
2. **Facade strategy:** extend `hr.shift.planning.grid` (inherit in pb_schedule) with NEW methods —
  don't mutate existing payload shapes (the legacy UI still consumes them until cleanup).
3. **Rate contract** (document in the model docstring): `hr.contract._pb_hourly_rate()` = `wage /
  (working_days_per_month × working_hours_per_day)` from the employee's structure; fallback
  calendar `hours_per_week × 52 / 12` as monthly hours; 0.0 (never crash) when wage/denominators
  missing — cells render "—" and the strip footnotes "N employees without a rate". Display-only.
4. **Budget model `pb.schedule.budget`:** `(company_id required, department_id optional,
  week_start date, amount Monetary)`, SQL-unique on the tuple; edit gated attendance-manager or
  payroll-manager, read officer+. Set/edit inline from the stats strip ("Set budget" ghost button →
  small dialog). No budget row → strip shows scheduled/actual only (no fake zeros).
5. **Coverage model `hr.shift.coverage.requirement`:** `(company_id, department_id, weekday
  selection 0-6 OR date — date wins when both rows exist, template_id optional, required_headcount
  int)`; same gates as budget. Coverage math: per day (and per template when template-scoped rows
  exist): required vs count of scheduled (draft+published) shifts; gap > 0 → rose chip, exact →
  green, surplus → muted "+N". A "Coverage" toggle overlays chips on day headers; an editor drawer
  (WfDrawer) manages requirement rows.
6. **Warnings endpoint** `check_shift(employee_id, date_str, template_id, exclude_shift_id=False)`
  → `warnings: [{severity: 'block'|'warn', code, text}]`: overlap (existing `_detect_conflicts`
  logic), on-leave that day (approved → warn strongly; pending → info), young-worker night/daily
  breach when the model is present (severity `block` — mirrors the save-time constraint with its
  law citation), OT-ceiling ≥90% MTD (via the weekentry payload, severity `warn`). Called from the
  quick-create modal (live, debounced) and from **Copy Week**, which becomes revalidate-on-paste:
  blocked/warned targets are SKIPPED and a Deputy-style skip report lists who/why (refuse-on-paste).
  `block` prevents the create in the UI; the server constraint remains the real guard.
7. **Stats strip** (replaces the 9-dot summary): per day column — scheduled hours · scheduled cost ·
  actual cost (past days) · coverage state; week totals + budget variance bar (tones: under budget
  green, ≥90% amber, over rose; W1 palette). Costs = Σ planned/actual_hours × `_pb_hourly_rate`.
8. **Reskin:** pbim tokens, Lucide via `ic()`, no gradients/emoji (kill the ⚠️), context bar
  (dept/week/search — W4; fortnight = a local toggle that widens the window from context
  `weekStart`), sticky employee column with hours-vs-contract bar, Open Shifts row kept, leave
  overlay kept, avatar → `WfPersonWeek` drawer (W5), shift click → native form `target:"new"` +
  reload (W5), template colors from a fixed 11-entry soft-tint palette derived from pbim tones
  (data-identity colors, ink text — map the template `color` index; no inline hand-built hexes
  beyond that const). W17/W20/W21 apply to anything embedded.
9. **Templates drawer** (WfDrawer): list of `hr.shift.template` (name, code, times, type, swatch,
  usage count this week), row → native form `target:"new"` + refresh, "New template" ditto; add the
  missing search view for the native list while you're there. Retire the "Shift Templates" rail
  item (900-band, W18) → **rail = 7 items**.
10. **Hero-title alignment (data-only P1b debt):** cockpit hero/eyebrow titles match the rail —
  pb_team → "Team Approvals", pb_ot_desk → "Overtime", pb_timeoff → "Time Off", new pb_schedule →
  "Schedule". String-only edits (+ their .po entries per W7).

## §4 Work packages (one commit each)

- **WP-1** `_pb_hourly_rate` + rate tests (structure path, calendar fallback, no-wage → 0.0).
- **WP-2** `pb_schedule` cockpit reskin — grid, open shifts, leave overlay, conflicts, publish +
  draft badge, week⇄fortnight, quick-create modal (tokens), context bar, person drawer, rail
  repoint. Feature-parity checklist against the legacy screen goes in the commit message.
- **WP-3** Stats strip + `pb.schedule.budget` (+ dialog, gates, tests).
- **WP-4** Coverage model + overlay + editor drawer (+ tests).
- **WP-5** `check_shift` warnings + quick-create integration + Copy-Week revalidate-on-paste with
  skip report (+ parity tests: young-worker block matches the constraint; ceiling warn matches the
  90% precedent).
- **WP-6** Templates drawer + Shift Templates retirement (DB-assert, W13.1) + hero-title alignment
  across the four cockpits.

## §5 Tests (with features, W9; scoped `-u` always)

- **T1** Rate math (3 paths). **T2** Budget CRUD + unique tuple + officer-read/manager-write gates.
- **T3** Coverage math: weekday vs date precedence, template-scoped vs day-total, gap/exact/surplus.
- **T4** `check_shift`: overlap, approved-leave, pending-leave, young-worker block parity (skip
  gracefully if model absent), ceiling ≥90% warn parity, clean shift → [].
- **T5** Copy-Week revalidation: seeded week where one target is on leave + one would breach —
  those skip with reasons, the rest land; all copies reverted after assert.
- **T6** Sidebar DB assertions: rail = **7 active items** in P1b's order minus Shift Templates
  (900-band inactive); Schedule item repointed to `pb_schedule`.
- **T7** Static gates (extend P1a/P1b's): no gradients/FA/emoji/invented hexes in pb_schedule
  (template-palette const exempt but must be the 11 defined tints); W16 grep; W5 doors.
- **T8** Regression: pb_time_hub 30 · pb_today 44 · pb_hr_workforce 36 · pb_attendance_flow 29 ·
  pb_wf_kit 5 all green (legacy grid facade untouched shapes).
- **T9–T16 Chrome-MCP live:** cockpit renders for a real dept/week — screenshot; stats strip
  numbers vs a pasted SQL cross-check (Σ planned_hours × rate for one day); set a budget → variance
  bar appears with correct tone (then delete the budget row, prove residue zero); coverage overlay
  shows a real gap (seed a requirement, assert chip, remove it); quick-create on an employee who is
  on leave that day → warning renders, cancel (no write); Copy Week dry-run path exercised with the
  skip report visible (revert any created shifts, prove counts restored); templates drawer lists
  templates, opens native form `target:"new"`; hero titles: Team Approvals / Overtime / Time Off /
  Schedule screenshots; rail shows 7 items (`p2_rail.png`); standalone legacy `shift_planning_grid`
  action still renders (un-retired proof); console clean everywhere.
- **T17** Publish safety: do NOT bulk-publish on live — publish exactly ONE seeded draft shift you
  created, verify state + that no mail/bus storm follows (check the mail queue count before/after),
  then unlink it. Residue zero across `hr_shift_planning`, `pb_schedule_budget`,
  `hr_shift_coverage_requirement`, mail queue.

## §6 Deploy & verify

Ritual per W10 (ssh alias Payobook19v2, apex DB `payobook`, detached systemd-run,
`-i pb_schedule -u pb_wf_kit,pb_hr_workforce,pb_sidebar,pb_team,pb_timeoff` — pb_ot_desk lives in
pb_hr_workforce; add any module whose strings you touch — asset purge fallback, no bare pkill,
no daemon-reload). Version bumps everywhere touched. Chrome-MCP on https://payobook.com.

## §7 Report back

Commit hashes per WP; T1–T17 evidence; self-review notes (W0.1); W-rules appended; deviations +
reasons; the WP-2 feature-parity checklist result; and open questions for the **P3 design
(Mission Control shell: global command bar with synced context, icon-rail lenses hosting the P1/P2
hubs, the persistent Needs-you dock absorbing Team Approvals' queue, the universal person popover,
⌘K — note Formula Studio already ships a Command Center pattern to extend)**. For P3 grounding,
report: how each of the 7 rail cockpits currently mounts (client-action tag + root component +
whether it already tolerates W17 embedding), what `pb.team.get_team_data` returns for the dock, and
any global-layout constraints you can see (biz_theme rail/sidebar interplay, `pb_sidebar` DOM).
