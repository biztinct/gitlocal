# WORKFORCE P6 — Demo world sync: pb_demo deployed current + a living present for Mission Control

Program docs: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` (W-rules through **W54**). Context: the
Workforce program (P0–P4) is complete and live; this phase executes closure-report item 4 —
**demo data stops at 2026-07-27 while today is later, so Mission Control opens on an empty week** —
plus the pb_demo repo↔server drift P2 found.

## §1 Scope

1. Deploy the repo's `pb_demo` to the live server (it has NEVER been deployed — P2 evidence: the
   server's `pb_demo/__manifest__.py` lacks `demo_chrome.scss` which the repo has) and `-u` it.
2. Build **`ensure_workforce_current()`** — an idempotent, is_demo-owned, TODAY-anchored seeder so
   every Mission Control lens shows real-looking data for the recent past, the current week, and
   next week — and run it live.
3. Fix the demo-interplay test drift P4 catalogued.

**Binding non-goals:** NO full world regen (no payslip/history regeneration — workforce surfaces
don't need payslips and the 4,500-employee compute is not to be re-run); no touching non-demo rows;
no schema changes outside pb_demo except nothing; no new UI. Don't lock any weeks. Don't break the
seeded Sudima fixtures (young-worker minors, ESS logins, timeoff demos).

## §2 Grounding (program records — VERIFY each on read before relying on it)

- pb_demo owns the regenerable VN demo world: `pb.demo.generator` (`demo_generator.py`), employee
  seeding `demo_employees.py` (incl. `ensure_young_worker_demos()` — generator-owned minors),
  `demo_timeoff.py` (`ensure_timeoff_demos()`, defensive per-section savepoints), ESS logins
  `ensure_ess_demo_users()` (passwordless manager.demo/employee.demo/minor.demo), and a workforce
  seeder `demo_workforce.py` (attendance/shift/trip seeding — read it first; extend, don't fork).
- History months are anchored (April–June + open July) — that's why the world "stops": nothing is
  today-relative. Your seeder must be TODAY-anchored so any future rerun refreshes the present.
- Demo rows carry `is_demo` ownership; regen adopts/refreshes by name (Phase-E precedent). Per-
  section `env.cr.savepoint()` wrapping (a single bad row otherwise poisons the batch —
  InFailedSqlTransaction lesson).
- The P4 test finding: `pb_today::test_payroll_report_moved_to_the_pay_run_section_with_its_gate`
  asserts `groups_id == [Payroll Officer]` but pb_demo legitimately adds "Payobook Demo User"
  (groups 81 + 445 live). Fix the TEST to assert "contains Payroll Officer" (subset, not equality).
- Company: the demo world lives on the demo company (company 5 in prior phases' evidence) —
  seed there; verify which company the demo employees belong to before writing.
- Locks exist now (`pb.wf.lock`, P4): none should exist on seeded days — assert none, don't bypass.
- Young-worker hard constraints fire even under sudo (daily/night caps) — keep minors' seeded days
  within caps (Phase-E grace lesson: each day ≤ cap, week total may exceed week_cap only for the
  two designated minors if you refresh their violation week; otherwise leave minors alone).

## §3 Design — `ensure_workforce_current()` (binding)

Method on the generator (TransientModel/api.model like its siblings), callable repeatedly, each
section in its own savepoint, everything created marked `is_demo=True` (or adopted by name where
the pattern exists). Window: **14 days back → 7 days forward**, all dates derived from
`fields.Date.context_today` (employee-local, W51 spirit — read how pb_today keys days first).

Cohort: ~60–100 demo employees across 3–4 departments of the demo company (pick departments that
already have demo employees + shift templates; include the 2 minors within their caps).

Per section:
1. **Shifts:** published `hr.shift.planning` rows for the window (weekdays + a Saturday subset),
   from existing `hr.shift.template`s, dept-scoped, no overlaps. Next week fully scheduled (the
   Schedule lens must look planned-ahead). A handful left `draft` for publish-flow demos.
2. **Punches:** `hr.attendance` for past days consistent with shifts, with a REALISTIC mix:
   mostly on-time (± a few min), some late-within-grace, ~5 late-beyond-grace, 2–3 missing
   punch-outs on yesterday/-2d (feeds Time·Exceptions + Close flags), nobody on locked days
   (assert no locks). **Today:** morning punch-ins for most of the cohort with NO check_out (the
   Today board must show a live "on shift now" population), a couple late, a couple absent.
   Any open punches from previous seeded days get closed by the rerun (self-healing).
3. **OT:** a few `hr.overtime.request`s: 2 approved (history), 2–3 `submitted` pending (dock),
   of which ≥2 are CLEAN by P4's `is_clean` definition (hours match grid, headroom, open day) so
   the dock's "Approve all N clean" moment demos; 1 draft in the grid tray.
4. **Leave:** keep the existing pending leaves; add 1–2 approved leaves overlapping the current
   week (Today's on-leave tile + Schedule overlay) if none exist in-window.
5. **Trips:** one submitted trip awaiting approval + one approved trip spanning 2 days of the
   current week (violet overlay on Time·Timeline).
6. **Corrections:** one submitted correction on a real missing-punch day (Attendance-Control
   pipeline card).
7. **Drivers:** refresh the driver demo employees' current-day punches so Driver map/Today map has
   live pins (read how `pb_driver_checkin`/geo sim seeds positions; if the route sim is the
   mechanism, ensure it's OFF after seeding — demo-mode pill governs live sim, don't leave it on).

## §4 Work packages (one commit each)

- **WP-1** pb_demo deploy parity: rsync, version-diff repo↔server manifests (ast.literal_eval both
  sides), `-u pb_demo` via the ritual, DB version stamp asserted. Report any server-side pb_demo
  local edits found (diff before overwriting — if the server has newer content than the repo, STOP
  and report instead of clobbering).
- **WP-2** `ensure_workforce_current()` + tests (idempotency: run twice → same counts; window
  math; is_demo ownership; savepoint isolation — one poisoned section doesn't kill the rest;
  minors within caps; no writes outside the demo company).
- **WP-3** The pb_today test fix (subset assertion) + any other demo-interplay test drift you find
  the same way.
- **WP-4** Run it LIVE + validate every lens shows data: Today tiles ≥ realistic non-zero split
  (on-shift/late/not-started), Schedule current+next week populated with cost strip numbers,
  Time·Week Grid current week with hours + drafts, Time·Timeline bars incl. the trip overlay,
  Time·Exceptions non-empty, Time Off queue + heatmap, Overtime desk pending, Trips pipeline,
  Approvals dock (incl. the clean batch footer), Close board with flags on the current week.
  Screenshot each (`p6_<lens>.png`). SQL cross-check the Today tile sums (P1b T6 style).

## §5 Tests & safety

- All WP-2 tests green under scoped `-u pb_demo`; full regression: no NEW failures vs the
  catalogued pre-existing set (which shrinks by the WP-3 fix — say by how much).
- Residue policy is DIFFERENT this phase: seeded demo data is the DELIVERABLE and stays. What must
  still be proven untouched: non-demo rows (count `hr_attendance`/`hr_overtime_request`/`hr_leave`
  where the employee is NOT a demo employee, before/after), locks (0), mail queue (no storm),
  tenant DBs (untouched — apex only).
- The seeder must never raise on rerun (savepoints + adopt-by-name).

## §6 Deploy & verify

Ritual per W10 (ssh alias Payobook19v2, apex DB `payobook`, detached systemd-run,
`-u pb_demo` [+ anything else touched], version bumps, asset purge fallback, W33 tell). Chrome-MCP
on https://payobook.com (/bizapp). The known first-load-blank-after-`-u` behavior applies.

## §7 Report back

Commit hashes per WP; evidence per §4/§5 (counts seeded per section, SQL cross-checks, screenshot
names); self-review notes (W0.1); W-rules appended; deviations + reasons; the server-side pb_demo
diff verdict (WP-1); and anything the next phase (P5 — Week-Grid redesign) should know about how
the grid renders with the new data (row counts, OT chip density, perf of get_week_entries on the
seeded cohort).
