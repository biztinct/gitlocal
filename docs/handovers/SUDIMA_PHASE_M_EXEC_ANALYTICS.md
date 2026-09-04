# SUDIMA Phase M — Executive Analytics WOW Rebuild (#1)

**Scope item:** #1 Executive Dashboard & Payroll Analytics (*Present + Needs-WOW*). Owner's directive (2026-07-24): the analytics surfaces are **"very archaic — need WOW out of the world."** Audit agrees on WHERE the archaism lives: the landing cockpit `pb_dashboard` and `pb_insights` are already design-compliant, but **`pb_hr_payroll_analytics`** (a native menu forest over 14 models, legacy JS disabled) and **`payroll_analytics_approval`** (gradient-era CSS, Chart.js from a CDN) are pre-design-system relics. Phase M rebuilds the analytics *experience* into one executive cockpit and retires the relic surfaces — **without touching the `payroll.analytics` data contract** that the approval workflow writes.
**Modules:** **`pb_insights`** (ground-up rebuild in place — it already owns the analytics slot) + menu retirement in `pb_hr_payroll_analytics` + CSS/CDN cleanup in `payroll_analytics_approval`. `pb_dashboard` is UNTOUCHED.
**Ledger:** C1, C2, C18 binding — esp. C18.11/18 (multi-company), C18.40, C18.53 (assets/restart), C18.55. 
**Prerequisites:** none hard. **Soft-consumes Phase G** (exception engine) and **Phase K** (bonus_hours) — every new tile MUST degrade gracefully (model/field-existence checks) so M can ship before or after K.

---

## 1. Scope

1. **Rebuild `pb_insights` as the executive Analytics cockpit**: payroll cost story (headline, 6-month trend from STORED run totals, gross/net/employer-cost series), cost-by-department from real payslip lines, statutory panel, **new workforce-pulse row** (attendance exceptions, leave today/pending, OT MTD + over-ceiling count, bonus-hours MTD — gated), and a report gallery replacing the archaic menu forest.
2. **Retire the `pb_hr_payroll_analytics` menuitems** (C18.42): its report views/actions stay off-menu (admin fallback, VU-skinned) and become gallery launches in the cockpit.
3. **`payroll_analytics_approval` cleanup only**: kill the gradient CSS + the CDN Chart.js asset; its model, auto-generation hook, approval workflow, menus and security are UNTOUCHED (data contract).
4. **Charting self-containment**: no CDN assets anywhere. Vendor Chart.js locally OR extend the existing bespoke SVG components (rings/bars precedents) — implementer's choice, but bespoke SVG is preferred for the executive look; either way the payload is local.

### Binding non-goals
- **NO `payroll.analytics` schema/state changes** — its JSON snapshot contract (employee_metrics, salary_components, comparison_data, anomaly_alerts) and draft/ready/approved/exported workflow are live consumers' territory (approval + bank export + the L-phase level2 hook). The cockpit reads it; never writes.
- **NO `pb_dashboard` changes** (it's compliant and is the landing surface, not the analytics one).
- **NO new stored fields / models** — M is a read-and-render phase; every series comes from existing stored data or bounded read_groups.
- **NO bank-export work** (Phase F owns money files; the legacy export in payroll_analytics_approval stays where it is).
- **NO deletion of the 14 `pb_hr_payroll_analytics` models** — only their menuitems go.

---

## 2. Verified plumbing facts (do not re-derive; agent-swept + spot-checked 2026-07-24)

- ✓ **`pb_insights` today** (all `pb_insights/models/pb_insights.py`): facade `pb.insights`; NET per run `_net_for_run` :34-42 (read_group on code NET); KPIs :48-97 (headcount :57, contracts :58, avg :61-65, statutory via `CONTRIB_CODES` :8, employee vs `_COMP` employer split :84-97); **6-month trend :102-115 = per-run `_net_for_run` loop** (6 read_groups — replace with stored totals, below); dept split :119-132 = **open-contract wage** read_group :120 (approximation — replace with payslip-line truth); quick-launch refs `REPORT_CANDIDATES` :11-18. OWL `insights.js` (bar fill :40-47), own token namespace `--pbi-*` in `insights.scss` (:45-46 bars, :50-56 dept rows).
- ✓ **Stored run totals (the fast trend source)**: `pb_payruns/models/hr_payslip_run.py:40-52` — `pb_employee_count`, `pb_total_net` (indexed), `pb_total_gross`, `pb_total_deductions`, computed by SQL roll-up :78-116 (category codes NET/GROSS/DED/DEDUCTION/COMP, buckets :5-7). Six months of trend = ONE search over runs reading stored fields.
- ✓ **Dept-cost truth source precedent**: the :98-106-style SQL (payslip_line ⋈ payslip ⋈ category) — clone with an employee⋈department join for latest-run NET by department.
- ✓ **`pb_dashboard`** (untouched context): facade `get_dashboard_data` `pb_dashboard/models/pb_dashboard.py:10-109`; run feed :25-42; SQL :57-76; company scoping :19,:52; ring gauge component `pb_dashboard.js:36-46` (SVG, reusable precedent).
- ✓ **Archaic surface #1 — `pb_hr_payroll_analytics`**: 14 models (personnel costs, headcount, statutory, dependents, budget variance, annual costs, employee detail, line analytics, cache, export wizard); menus under `om_hr_payroll.menu_hr_payroll_root > menu_hr_analytics_root` gated `group_payroll_base_manager`/`group_payroll_super_admin` (`views/hr_analytics_menus.xml:10`); legacy dashboard JS already DISABLED in the manifest (Odoo-19-incompatible `odoo.define`).
- ✓ **Archaic surface #2 — `payroll_analytics_approval`**: gradient `static/src/css/payroll_analytics.css:9` (`linear-gradient(135deg…)`) + off-palette hexes :22-46; **CDN Chart.js 3.9.1** loaded at `static/src/js/payroll_charts_v19.js:21`; menus under `pb_hr_payroll_base.menu_payroll_backup_root`; security rules `security/payroll_analytics_security.xml:5-37`.
- ✓ **`payroll.analytics` contract**: model `payroll_analytics_approval/models/payroll_analytics.py:22-125` (JSON fields, states draft/ready/approved/exported :65-70); auto-generated when a run reaches level2 — hook `om_hr_payroll/models/hr_payslip.py:1016-1018` → `_auto_generate_batch_analytics_on_level2` :1147-1215; refresh-preserves-state :227-263. **Its queries are NOT company-scoped** (:327-332) — a known risk; M surfaces its data read-only WITH a company filter applied at the cockpit query, without rewriting its internals.
- ✓ **New-tile data sources**: attendance exceptions — `pb.attendance.exception.engine.get_exceptions(employees, date_from, date_to)` (`pb_attendance_flow/models/attendance_exception.py:26,81`; kinds missing_punch/missing_checkout/late/early_leave; trip+leave-aware); leave — hr.leave states confirm/validate1/validate; OT — `hr.overtime.request` date :24, states :49-54, approved_hours (+ `bonus_hours` AFTER Phase K); ceilings via `get_ot_ceilings` (`attendance_weekentry.py:325-389`).
- ✓ **Multi-company posture**: pb_insights `co_ids = env.companies.ids` :48 — keep it (C18.11/18: render every selected company).
- ✓ **Vendored-lib precedent**: pb_website vendors its chart/animation libs locally; CDN assets are a violation (self-containment + demo-offline risk).

---

## 3. Architecture (`pb_insights` rebuild)

- **Facade `pb.insights`** keeps its name/action tag (sidebar slot unchanged — zero pb_sidebar churn). First-line gate `_require()` = `group_payroll_base_manager` | `group_payroll_super_admin` (matches the analytics menus it replaces); a second gate `_can_bonus()` = `om_hr_payroll.group_hr_payroll_manager` | super admin for the bonus tile (mirrors Phase K's viewer gate).
- `get_insights(period)` → ONE payload, sections:
  - **hero**: latest-run NET headline + MoM delta, headcount, avg cost, employer statutory total; 12-run sparkline from `pb_total_net` (stored — no line aggregation);
  - **trend**: last 6 months of runs — NET, GROSS, employer cost (`gross−net+COMP` bucket) series from stored fields; per-run drill chips (employee count, state);
  - **departments**: latest done-run NET by department via the SQL join (clone :98-106 + employee⋈department); fallback to the contract-wage read_group when no done run exists (flag `approx: true`, badge it in UI);
  - **statutory**: CONTRIB_CODES employee/employer split (existing :84-97 logic, restyled);
  - **pulse** (each sub-tile existence-checked, `null` when its module is absent — soft-deps): attendance = this-week exception counts by kind (engine call, bounded to allowed companies' active employees); leave = on-leave-today + pending-approval counts (read_groups); OT = MTD approved hours by type + over-90%-ceiling employee count; **bonus** = MTD `bonus_hours` total — only present when `_can_bonus()` AND the field exists (pre-K live = absent);
  - **snapshots**: latest `payroll.analytics` rows (read-only, company-filtered at THIS query), state chips, anomaly-alert count from the JSON;
  - **reports**: gallery entries resolved from the existing `pb_hr_payroll_analytics` actions (existence-checked xmlid list — the REPORT_CANDIDATES pattern :11-18 generalized).
- **Menu retirement**: remove `menu_hr_analytics_root` + children menuitems in `pb_hr_payroll_analytics` (actions/views stay off-menu). The cockpit's gallery is the new path to them.
- **`payroll_analytics_approval` cleanup**: delete the gradient/hex CSS in favour of a minimal pbim-token sheet for its (still-native, VU-skinned) views; remove `payroll_charts_v19.js` from the asset bundle (its legacy dashboard is already disabled — the CDN load must go). Nothing else.
- **Charts**: bespoke SVG components in `pb_insights` (extend the ring :36-46 and bar precedents: line/area sparkline, stacked bar, donut with center KPI). If Opus judges bespoke SVG insufficient for the trend interactions, vendor Chart.js 4 LOCALLY under `pb_insights/static/lib/` — never CDN. Either way: all assets local (test asserts no external URL in the bundle).

---

## 4. WOW-UX specification (owner mandate: out-of-the-world, executive-grade)

1. **Root `.pbin.pbim`** — migrate the `--pbi-*` names to the shared `--pbim-*` token vocabulary (indigo primary, white+rail hero, no gradients/emoji, Lucide via local `pbin_icons.js` — manifest + restart, C18.53).
2. **The screen reads like a briefing, top to bottom**: hero band (NET headline with animated count-up + MoM delta arrow + 12-run sparkline behind it, three companion KPIs), then the 6-month **cost story** chart (NET/GROSS/employer-cost, hover crosshair with per-run tooltip card, run-state chips beneath each column), then a two-pane row — **department leaderboard** (ranked bars with per-head normalization toggle, `approx` badge when contract-based) and **statutory donut** (employee vs employer, center total), then the **workforce pulse row** (four compact tiles: exceptions by kind with rose accents, leave today with avatar overflow, OT vs ceiling with amber bar, bonus tile — visible only when gated in), then **snapshots** (payroll.analytics cards with state + anomaly chips), then the **report gallery** (cards with Lucide glyphs replacing the retired menu forest).
3. **Motion discipline**: count-ups, bar/spark draw-ins ≤400ms, no parallax/gimmicks; empty/degraded states designed (no done runs; module-absent pulse tiles render as quiet "not installed" ghosts, not gaps).
4. **Responsive**: usable at 390px (tiles stack); the trend chart scrolls horizontally inside its own container.
5. `_()` strings + **vi.po** (`#. module:` on every entry).
6. Chrome-MCP: full board on live demo data (4.5k employees, 30.5k slips) with timings; pulse row with G-phase seeded exceptions; bonus tile present as payroll manager / absent as base manager; degraded run (a company with no done runs); 390px; screenshots of each.

---

## 5. Safety rails

1. **Read-only phase**: the facade performs ZERO writes (grep-assertable). Snapshots, exceptions, leaves, OT are read through each model's normal access (no sudo except where an existing precedent already sudo-reads for aggregate-only purposes — if needed, aggregates only, never row PII in the payload beyond name/avatar cards the user's groups could see anyway).
2. **Performance is a feature**: hero+trend from STORED `pb_total_*` (indexed) — the 6×read_group loop dies; every other section is ONE bounded read_group/SQL; the full payload must return <1.5s on live demo volume (report actuals). No unbounded searches (C18.18).
3. **Soft-deps never crash**: `'pb.attendance.exception.engine' in self.env` / field-existence for `bonus_hours` — M ships green whether or not G/K are live.
4. **Data contract**: `payroll.analytics` untouched (schema, states, hook); cleanup limited to CSS + asset-list line. The L-phase interplay (level2 hook) is unaffected — M never touches `action_payslip_run_level1_done`.
5. **No CDN/external asset anywhere** (test-asserted).
6. Menu retirement reversible (menuitems only).

---

## 6. Test cases

**Server:**
1. Gates: base-manager gets the board; non-manager AccessError; bonus section absent for base manager, present for payroll manager (when field exists).
2. Trend series matches stored `pb_total_net/gross` for the seeded runs (no line re-aggregation happens — assert query count stays flat as run count grows within the window).
3. Department split: seeded latest done run → NET-by-department matches a hand-computed fixture; no done run → contract fallback with `approx: true`.
4. Statutory split: employee vs `_COMP` employer sums match fixtures.
5. Pulse degradation: with `pb_attendance_flow` absent from the test registry (or engine mocked away) the payload carries `null` tiles, no exception; same for missing `bonus_hours` field.
6. Snapshot section: company-filtered (another company's `payroll.analytics` row excluded); read-only (no write occurs — grep-level facade assertion).
7. Report gallery lists only resolvable actions (a bogus xmlid in the candidate list is skipped silently-but-logged).
8. Multi-company: two allowed companies → counts include both; one → excludes the other (C18.11/18).
9. Asset self-containment: no `http://`/`https://` source in the module's asset bundle files.
10. Menu retirement: `menu_hr_analytics_root` xmlid gone; the report actions still resolve.
11. vi.po loads under vi_VN.

**Chrome-MCP:** §4.6 list with screenshots + timings.

---

## 7. Deploy & verify (Payobook19v2 — memory `payobook-deploy`)

`-u pb_insights,pb_hr_payroll_analytics,payroll_analytics_approval --test-tags /pb_insights` (C18.40; C18.54; `--uid=odoo`). Full restart + `/web/assets/%` clear (manifest asset changes — C18.53). Verify live: board <1.5s on demo volume (report actuals per section), analytics menus gone, gallery launches the old reports, snapshots render for the existing live `payroll.analytics` rows, no CDN request in the network tab (Chrome-MCP), payroll_analytics_approval native views still open (with the new minimal CSS).

---

## 8. Report back

1. Tests 1–11 + screenshots + live payload timings per section.
2. Chart approach chosen (bespoke SVG vs vendored Chart.js) and why; asset audit output (no external URLs).
3. Which report actions made the gallery (the resolved candidate list).
4. Confirmation the `payroll.analytics` hook path is untouched (diff scope proof) and its live rows render.
5. Deviations, file list, versions; gotchas → C18 wording.

---

## Kickoff line (paste into the Opus session)

> Read `docs/handovers/SUDIMA_PHASE_M_EXEC_ANALYTICS.md` and `docs/FORMULA_ENGINE_CONVENTIONS.md` (C1, C2, C18 binding — esp. C18.11/18/40/53/55), then implement Phase M exactly as specified: rebuild `pb_insights` in place as the executive Analytics cockpit (stored-total trend, payslip-truth department split, statutory panel, soft-dep workforce pulse row with the gated bonus tile, read-only payroll.analytics snapshots, report gallery), retire the `pb_hr_payroll_analytics` menu forest (actions stay off-menu), and strip the gradient CSS + CDN Chart.js from `payroll_analytics_approval` without touching its model/workflow. Read-only facade, all assets local, soft-deps never crash, <1.5s payload on live demo volume. Tests §6, deploy §7, report §8.
