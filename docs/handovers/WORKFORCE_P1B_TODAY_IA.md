# WORKFORCE P1b — The Today board + the IA finale (Option A complete)

Program docs: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` (W-rules through **W21.1** — read them all;
W20/W21/W21.1 are P1a's hard-won embedding lessons and directly constrain this phase),
`docs/WORKFORCE_REDESIGN_OPTIONS.html` (visual targets: mockup B's Today canvas — tiles, list, map
card — rendered as a standalone hub for now; mockup A's sidebar is the end-state rail).
Prior phase: P1a report answers are baked into §2.

## §1 Scope

Two deliverables: (1) **`pb_today`** — the live triage board that replaces Live Attendance +
Workforce Dashboard and folds in Driver Tracking's map; (2) the **IA finale** — the Workforce rail
reaches its Option-A shape (Today · Schedule · Time · Time Off · Overtime · Trips · Approvals, plus
Shift Templates until P2), with Payroll Report relocated to the Pay Run section and Overtime Rules
retired.

**Binding non-goals:**
- No Mission Control shell (P3), no engine/tolerances (P4), no Schedule/roster work and no Shift
  Templates fold-in (P2).
- No deletion of legacy files or `ir.actions` records — retirement means leaving the rail (sidebar
  `active=False`, 900-band per W18). Dead-code deletion is a later cleanup with a doAction-caller
  audit (start that audit now: §4 WP-3 has you grep and REPORT callers, not delete).
- Don't rebuild My Team / Overtime Desk / Leave / Trips cockpits — renames are data-only.
- No new charts on Today: the old dashboard's Chart.js analytics die deliberately (deep analytics
  belong to Insights/Explorer). Today is triage, not reporting.

## §2 P1a open questions — design answers (binding)

1. **Retired band:** keep records, `active=False`, sequence 900+ (W18). Never delete. Renumbered
   ACTIVE set is canonical (§4 WP-3 table).
2. **`pb_business_trip` unfreeze:** yes, this phase — clone the migration precedent
   (`pb_attendance_flow/migrations/19.0.1.0.4/post-migrate.py`); version bump; DB-assert.
3. **`day` context:** the Today board is its exclusive owner for now — enable the bar's `day`
   segment ONLY on Today (features `dept,day,search`). Time hub stays week-scoped; no fifth lens.
4. **Exceptions person filter:** yes — optional `employee_id` on `get_control_data` + a person
   filter chip on the board; Today's late/missing rows deep-link to the Time hub's Exceptions lens
   pre-filtered to that employee (via `ctx.set({personId})` + an action param, your choice — assert
   it lands filtered).
5. **Shared counts endpoint:** still deferred to P4. `pb.today` computes its own tiles; where "late"
   is concerned, use the SAME grace source as the exception engine (`pb.attendance.rule`,
   company-else-global two-search) so Today and Exceptions never disagree on who is late.
6. **Row caps:** unify — a shared `WF_ROW_CAP = 200` exported from `pb_wf_kit` (JS) + mirrored
   constant in the facades that cap (timeline 120 → 200; week grid stays 200). Truncation notices
   stay (no silent caps).
7. **Legacy doAction callers:** grep the repo for the three retired legacy action tags/xmlids
   (`attendance_live`, `attendance_timecard`, `pb_hr_workforce.action_workforce_dashboard_server`,
   plus `overtime_rules_dashboard`, `payroll_report_dashboard`, `pb_driver_map`) and REPORT the
   caller list (the old dashboard's quick-action buttons are known callers and die with it).

## §3 Verified plumbing facts (do not re-derive)

- **Live Attendance (read-model to mine, UI dies):** facade `hr.attendance.live` in
  `pb_hr_workforce/models/attendance_live.py`; the legacy board computed Total / On Shift /
  Checked Out / Not Started / On Leave / Late from `hr.attendance` + `hr.shift.planning` +
  `hr.leave` + `hr.employee`. Read it first; write a FRESH `pb.today` facade (don't chain the
  legacy transient), but keep its state definitions unless §2.5 (grace source) overrides "late".
- **Workforce Dashboard (dies):** `hr.workforce.dashboard` TransientModel + DOM-polling Chart.js —
  nothing to reuse.
- **Driver map (embed, don't rebuild):** component `DriverMap`
  (`pb_driver_checkin/static/src/js/driver_map.js`, ~154 L, polls `POLL_MS = 5000`), template
  `driver_map.xml`, wraps shared `GeoMap` from `@biz_geo_tracking/js/geo_map`; facade
  `pb.driver.map` (`models/pb_driver_map.py`) with `_require_officer()` on every RPC. Make it
  W17-embeddable (`embedded` prop suppresses its KPI strip; W20 definite height; W21 mount hooks
  read only).
- **Person drawer + week data:** reuse `pb.time.hub.get_person_week` and the P1a drawer — `pb_today`
  depends on `pb_time_hub` (plus `pb_wf_kit`, `pb_driver_checkin`).
- **Grace rule:** `pb.attendance.rule` (pb_attendance_flow) — company-else-GLOBAL two-search, ships
  a `company_id=False` default row (Phase G).
- **Sidebar icon gotcha:** the rail's icons are a FIXED inline Lucide set in
  `pb_sidebar/static/src/js/pb_sidebar.js` — unknown names render a plain circle. Add any new names
  you use (e.g. `activity`, `inbox`, `zap`) to that set (Sudima precedent did exactly this).
- **Sidebar files & noupdate state (post-P1a):** everything unfrozen EXCEPT
  `pb_business_trip/data/pb_sidebar.xml` (still `noupdate="1"` → §2.2 migration). Items live in:
  `pb_sidebar/data/pb_sidebar_data.xml` (Workforce Dashboard :274-278, Live Attendance :279-283,
  Shift Roster :289-293, Shift Templates :294-298, Overtime Rules :299-303, Payroll Report
  :304-308 — all noupdate 0), `pb_hr_workforce/data/pb_sidebar.xml` (OT Desk), `pb_team/data/`
  (My Team), `pb_timeoff/data/` (Leave), `pb_driver_checkin/data/` (Driver Tracking),
  `pb_business_trip/data/` (Trips, frozen). Pay Run section xmlid: `pb_sidebar` defines sections —
  Pay Runs/Payslips items sit in `sec_payrun` (`pb_sidebar_data.xml` :63-76).
- **W13.1 applies to every record move in this phase** — assert final sequences/sections/active
  flags in the DATABASE after `-u`.

## §4 Work packages (one commit each)

**WP-1 `pb_today` — the triage board** (deps: `pb_wf_kit`, `pb_time_hub`, `pb_driver_checkin`).
- Client action tag `pb_today`; OWL cockpit on pbim tokens, indigo primary (W1); officer-gated
  facade `pb.today` (`_require_officer` pattern) — note in the report that Live Attendance was
  previously ungated (deliberate narrowing, same as P1a).
- `get_today_data(department_id, day)` → tiles `{on_shift, late, not_started, checked_out,
  on_leave, total}` + `rows[]` per person `{id, name, job, dept, shift_label, check_in, check_out,
  state, minutes_late}` (late per §2.5 grace). Day defaults to context `day` (today).
- Board per mockup B's canvas: tile strip (click = filter the list; tiles use semantic tones —
  late rose, not-started amber, on-shift green, on-leave gray); people list rows with avatar → the
  P1a person drawer (W5); row actions: late/missing → **File correction** deep-link into Time hub
  Exceptions pre-filtered (§2.4); a compact **map card** (embedded `DriverMap`, W17/W20/W21) with
  "Open map →" toggling a full-height Map view inside the hub; 30s poll for the board (the embedded
  DriverMap keeps its own 5s poll), manual refresh affordance, "Updated HH:MM".
- Context bar features `dept,day,search`; day pill's first consumer (§2.3).
- Empty states (before shifts start / everyone in / no drivers).
**WP-2 Time hub person filter + shared cap.** `get_control_data(employee_id=optional)` + board
person chip (clearable); timeline cap 120→`WF_ROW_CAP` 200 (export from pb_wf_kit, mirror in
facades); Today→Exceptions hand-off lands pre-filtered (assert in Chrome).
**WP-3 IA finale (data + migrations).** Final ACTIVE rail:
| seq | item | change |
|---|---|---|
| 10 | Today | NEW (pb_today data file, noupdate 0) |
| 20 | Schedule | rename of "Shift Roster" (label+icon only, action unchanged) |
| 30 | Time | (P1a) |
| 40 | Time Off | move from 32 |
| 50 | Overtime | rename of "Overtime Desk", move from 38 |
| 60 | Trips | move from 37 — **requires the pb_business_trip unfreeze migration** |
| 70 | Approvals | rename of "My Team" (label+icon `inbox`), move from 5 |
| 80 | Shift Templates | move from 50 (dies in P2) |
Retire to the 900-band (`active=False`): Live Attendance, Workforce Dashboard, Driver Tracking
(map lives in Today now), Overtime Rules (OT Desk's config gallery + native form is the editor of
record — confirm the gallery opens the form, it did in the audit). **Relocate Payroll Report** to
`sec_payrun` (section_id change, keep P0's gate, sequence after Payslips). Do the retired-action
caller grep (§2.7) and put the list in your report.
**WP-4 W5 sweep + regression.** Every Today row/tile/avatar is a door; retired items absent; sweep
count: **8 active Workforce items** + Payroll Report present under Pay Run.

## §5 Tests (with features, W9; scoped `-u` always)

- **T1** `pb.today` facade tests: tile math on a seeded day (one late-with-grace, one not-started,
  one on-leave, one checked-out), grace source parity with the exception engine (same employee
  flagged by both), non-officer AccessError, cross-company scoping.
- **T2** `get_control_data(employee_id=…)` filters; without arg unchanged (regression).
- **T3** Sidebar DB assertions after `-u` (W13.1): the §4 WP-3 table exactly (sequence, active,
  section, name), `ir_model_data.noupdate` = f for `pb_business_trip.item_wf_trips`, retired set at
  900-band inactive, Payroll Report in `sec_payrun` with its gate.
- **T4** Static gates (extend P1a's): W16 grep 0; no gradients/FA/emoji/invented hexes in
  `pb_today`; W5 doors on Today rows; `WF_ROW_CAP` used by both facades (no literal 120 left).
- **T5** Regression: `pb_time_hub` 30 + `pb_wf_kit` + `pb_hr_workforce` + `pb_attendance_flow`
  suites green.
- **T6–T13 Chrome-MCP live:** Today renders (tiles sum sanity vs a SQL count pasted in the report);
  tile click filters the list; a late row's File-correction lands in Time hub Exceptions
  pre-filtered to that employee; avatar opens the drawer with P1a-verified numbers; map card live
  pins + full Map view toggle (and the standalone `pb_driver_map` action still works, embedded:false
  proof like P1a's T9); day pill changes the board (pick yesterday — counts change accordingly);
  rail shows the §4 WP-3 order with correct labels/icons (screenshot `p1b_rail.png`); Payroll
  Report opens from Pay Run section; retired items gone; console clean everywhere; screenshots
  `p1b_today_board.png`, `p1b_today_map.png`, `p1b_handoff_exceptions.png`.
- **T14** Full sweep: 8 active Workforce items + relocated Payroll Report all load, 0 console
  errors; live-data residue: none (undo any test writes and prove it).

## §6 Deploy & verify

Same ritual (W10): ssh alias Payobook19v2, apex DB `payobook`, detached systemd-run unit,
`-i pb_today -u pb_wf_kit,pb_time_hub,pb_hr_workforce,pb_attendance_flow,pb_business_trip,pb_team,pb_timeoff,pb_driver_checkin,pb_sidebar`,
asset-purge fallback, no bare pkill, no daemon-reload, Chrome-MCP on https://payobook.com.
Version bumps everywhere touched; `pb_business_trip` bump REQUIRED for its migration.

## §7 Report back

Commit hashes per WP; T1–T14 evidence; self-review notes (W0.1); W-rules appended; deviations +
reasons; the retired-action caller list (§2.7); and open questions for the **P2 design (Schedule
instrumentation: roster reskin onto tokens, Deputy stats strip [cost per day column vs actuals],
coverage lens, edit-time ceiling/compliance warnings, templates drawer + Shift Templates
retirement)** — in particular report what `hr.shift.planning` + `hr.shift.template` already store
that P2's budget/coverage math could use (wage/cost fields on contracts? planned_hours? template
colors), so the P2 handover can be grounded.
