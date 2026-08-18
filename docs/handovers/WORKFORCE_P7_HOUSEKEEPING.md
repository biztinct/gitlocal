# WORKFORCE P7 — Housekeeping: honest tests, dead code buried, Close at scale, small debts paid

Program docs: `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` — W-rules now through **W74** (a parallel
session's entries were renumbered W69–W74 after a ledger collision; read the whole tail).
This phase executes closure-report items 2/3/5/6 plus the debts P5/P6 handed forward.

## §0 SHARED SERVER — read first (W68)

A **parallel IA-program session (`pb_hub`, handovers in `docs/handovers/ia/`) is active on this
repo and this server.** Rules of engagement, non-negotiable:
- Before every `service stop` / `-u`: check for a foreign run (`ps` for odoo-bin `-u`/`-i` you
  didn't start; a `/tmp/*.done` sentinel that isn't yours; `git log` for foreign commits landing
  mid-run). If found, WAIT and re-check; never kill their process.
- Never touch `pb_hub/**` or `docs/handovers/ia/**`. If the backend bundle breaks because of a
  foreign file, diagnose and REPORT (bundle-splitting technique is in W68's history) — never patch
  their file.
- After any write-bearing live test, re-assert row counts from `psql`, not the UI (their restarts
  can cut a round-trip in half).
- Ledger appends: `git pull`-less repo, but re-read the ledger file immediately before appending
  (they append too); if your numbering collides, renumber yours (P5 precedent).

## §1 Scope — five work packages

**WP-1 Honest MRO tests + append-after-super audit** (closure item 2).
- Rewrite `pb_young_worker` test_09: it asserts the advisory reaches the payroll path via
  append-after-super, but the measured MRO is `pb_demo → pb_close → pb_young_worker` and P4 moved
  the demo path onto `_pb_demo_advisories` hooks. Make the test assert the TRUE mechanism (hook
  registration + advisory content on both the generic and demo paths).
- Audit every other append-after-super/wrapper assumption repo-wide: grep wrappers of
  `create_and_compute` / `prepare_run` / `compute_batch` / `_get_formula_input_values` /
  `get_*_data` overrides where a module assumes it is outermost; verify each against the actual
  MRO on the live registry; fix stale tests, FILE (report) anything needing a real design change.

**WP-2 Demo polish** (P5/P6 debts — extend `ensure_workforce_current`, keep idempotency):
- The demo company's `resource.calendar.tz` is still **Europe/Brussels** (W55 fixed employees,
  not the calendar) — grid-created punches land at 13:00 ICT via `_emp_tz`'s calendar-first
  resolution. Fix the live data (one field) AND make the seeder stamp calendar tz so regen holds.
- Seed a meaningful slice of punches with `pb_entry_source='grid'` (the grid's REG fast-path is
  read-only on device punches — right behavior, but the keyboard story needs editable cells to
  demo). Concentrate 6–10 OT chips in **Stores - North** across the settled + current week so
  chips are visible without a live edit.
- Rerun the seeder live; verify grid editability + chip density; non-demo untouched proofs as P6.

**WP-3 Legacy deletion pass** (closure item 3) — **caller-audit first, delete second**:
- Candidates: `workforce_dashboard.*` (py transient + views + js/css), `attendance_live.*`,
  `attendance_timecard.*` (js/css; the `hr.attendance.timecard` FACADE stays — Timeline reads it),
  `overtime_rules.*` (js/css + action), legacy `shift_planning_grid` **client UI only** (js/css +
  action — the `hr.shift.planning.grid` facade is pb_schedule's base and STAYS), their
  `ir.actions.client` records + legacy `menu_views.xml` menu tree, and the retired sidebar-item
  records (900-band + the 2 parked at 25/35) via migration.
- Known callers to remap first (P1b audit): `pb_hr_flow/models/hr_flow_wizard.py:181-186` tertiary
  map (`wf-dashboard`→shell Today, `wf-live-attendance`→shell Today, `wf-timecards`→shell Time,
  `wf-overtime-rules`→shell Overtime, `wf-payroll-report` stays — payroll_report LIVES in the Pay
  Run section; keep `payroll_report.*` and `wf_breadcrumb.css` (its only remaining consumer)).
- Re-run the caller audit at implementation time (the IA program may have added references —
  if a LIVE caller exists outside your scope, keep the target and report). Registry must load
  clean; screenshot proof the shell + Pay Run report still work; note the asset-bundle size delta.

**WP-4 Close at scale + the metrics gate** (closure items 5/6):
- Close board: group flags **by kind** with counts; per-kind "Review all N…" bulk action (manager
  gate, one note applied to all, the self-review refusal preserved per row — skipped rows
  reported); paged flagged table (W45: cap + true totals, "showing X of Y"); a "reviewed" filter
  chip. Validate on the live demo week (66 flags pre-P5-threshold → fewer now; seed more if the
  bulk path needs volume, then clean).
- `pb.team._build_metrics` still routes through the officer-gated ceilings door inside try/except
  → OT metrics silently blank for HR/payroll managers (W53 shape). Point it at the ungated
  private twin; test as an HR-manager-without-attendance-groups.

**WP-5 Grid i18n + the hoot gap** (P5 debts):
- `_t`-wrap ALL user-facing strings in `biz_week_grid` (component was never wrapped; include the
  new editor/tray/legend strings) + `vi.po` with W7 markers; spot-verify two strings live in vi.
- The 22-case hoot suite is committed but nothing executes it (registered in
  `web.assets_unit_tests`; `-u` doesn't run it). Execute it: drive `/web/tests` filtered to the
  suite via Chrome MCP and paste the pass count; then add the lightest durable runner you can
  justify (a `browser_js`-style server test if this build supports it — investigate; if not,
  document the manual `/web/tests` step in the ledger as the ritual).

**Binding non-goals:** no new features beyond the listed; no ESS (P8); no touching `pb_hub`/IA
files; no payroll-path changes (WP-1 fixes TESTS, not bridges); the legacy country payroll modules
stay; `compliance_status` and its old consumers stay (W48 governs new code).

## §2 Tests

- WP-1: rewritten test_09 green on live; the audit table (wrapper → MRO position → verdict) in
  the report; any fixed tests green.
- WP-2: seeder idempotency re-proven; calendar tz asserted in DB; a live grid edit on a seeded
  'grid' punch (then reverted, psql-proven per W68).
- WP-3: registry loads (W33 tell); zero grep hits for deleted symbols outside git history; the
  remap covered by a test on `get_tertiary_action`; sidebar-record deletion migration DB-asserted;
  full regression suite — no NEW failures.
- WP-4: bulk-review tests (per-kind, note propagation, self-review skip, paging true-totals);
  metrics-gate test as HR manager; live Chrome pass on the Close board + dock metrics.
- WP-5: `msgfmt --check-format`; two vi strings live; hoot pass count pasted.

## §3 Deploy & verify

Ritual per W10 + **§0 foreign-run check before every stop**. Scoped `-u` for every touched module
(+ `-i` nothing), version bumps everywhere (migrations must run — W13.1), asset purge expected
(deletion phase), Chrome-MCP on https://payobook.com (/bizapp). Known: `--test-enable
--stop-after-init` does NOT exit on this build — confirm `0 failed` in the log, then kill by PID
(P5 precedent).

## §4 Report back

Commit hashes per WP; evidence per §2; the WP-1 audit table; the WP-3 deletion inventory (files,
records, LOC removed, bundle delta) + caller-audit verdicts; self-review notes (W0.1); W-rules
appended (re-read the ledger tail first, §0); deviations + reasons; and open questions for the
**P8 design (ESS Workforce: employee surface in pb_me_portal — my schedule + ack, my timesheet,
my leave, shift-end pulse; token-URL sign-off precedent `pb_formula_studio/controllers/review.py:19`;
activity_schedule precedent `overtime_request.py:193-197`)** — in particular report: pb_me_portal's
current controller/template structure and auth pattern, which demo employees have portal/internal
users, and how the driver PWA's checkout flow could host the pulse prompt.
