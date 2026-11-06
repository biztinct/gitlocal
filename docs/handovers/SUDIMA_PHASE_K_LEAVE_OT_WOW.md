# SUDIMA Phase K — Leave Command Center + Overtime Desk + OT Limits & Bonus Hours

**Scope items:** #8 Leave Management (*Partial + Needs-WOW*: full hr_holidays engine exists, surface is stock "Time Off") and #9 Overtime Management (*Needs-WOW* **plus a client-directed engine extension**): multi-period OT limits (Daily / Weekly / Bi-weekly / Monthly / Annual) with **overflow-to-Bonus-Hours** — hours beyond the limits are never lost and never block entry (adults): they land in a per-day `bonus_hours` bucket that payroll formulas can consume via a new `BONHRS` input, with a **restricted** slice-and-dice review surface.
**Modules:** NEW **`pb_timeoff`** (HR Leave Command Center cockpit) + **`pb_hr_workforce`** (Overtime Desk cockpit, `pb.ot.ceiling` period extension, request split fields, native OT menus retired) + **`pb_workforce_payroll_bridge`** (BONHRS input).
**Ledger:** C1, C2, C18 binding — esp. C18.17 (facades act via the models' OWN actions), C18.11/18 (multi-company reads), C18.33-38 (young-worker gates + week-cap semantics), C18.40, C18.47/48 (live Gmail SMTP), C18.53, C18.55.
**Prerequisites:** B and E shipped (the grid + minor gates are seams here). **Boundary with Phase I:** I's "My Team" queue = manager persona; K = HR/officer org-wide surfaces.

---

## 1. Scope

1. **Leave Command Center** (`pb_timeoff`): org-wide HR cockpit — who's out today/this week, approval queue, department×day month heatmap, per-employee balance board, apply-on-behalf. All mutations ride core `hr.leave` actions.
2. **OT multi-period limits**: `pb.ot.ceiling` gains `daily_cap`, `weekly_cap`, `biweekly_cap` (0 = not enforced) alongside the existing `monthly_cap`/`annual_cap(+special)`. The **tightest remaining allowance across all enforced periods** is the day's OT allowance.
3. **Bonus Hours overflow**: at grid save AND (authoritatively) at approval, an adult's OT entry is **split**: `approved_hours` = the portion within allowance, new `bonus_hours` = the overflow. Nothing blocks, nothing is silently dropped. New formula input **`BONHRS`** (sum of approved requests' bonus_hours in period) exposed by the payroll bridge — the client defines the bonus formula themselves later.
4. **Bonus Hours Review** (restricted): a gated tab in the new Overtime Desk cockpit — filter rail (date range + presets, employee, department, OT type, company, min-hours) + group-by (employee / department / day / week / month) + totals + capped CSV export.
5. **Overtime Desk** (in `pb_hr_workforce`): approval queue with rate/ceiling context and live split preview, bulk approve with per-row results, config gallery. Native OT menus retired (C18.42; actions kept off-menu; forms stay VU-skinned).

### Binding non-goals
- **NO changes to the leave engine** — `pb_timeoff` is facade-only; core hr.leave actions do all mutations.
- **NO payroll formula authorship** — we expose `BONHRS`; the bonus formula is the client's (report the input as available; do not add rules to any config).
- **NO bonus hours for minors** — the Phase-E hard OT block stands unchanged; overflow-to-bonus must NEVER become a young-worker bypass (rail 5).
- **NO second limit system**: `pb.ot.ceiling` is THE limit source. `hr.overtime.config.max_hours_per_day/month` (:34-37) are legacy per-type metadata — do NOT enforce them a second time (one-source rule, same doctrine as one-OT-source C18).
- **NO ESS/portal surfaces** (Phase I), **NO new OT entry path** (entry stays the Phase-B grid), **NO allocation/accrual redesign**, **NO new mail code**.

---

## 2. Verified plumbing facts (do not re-derive; verified 2026-07-24)

- ✓ **No branded leave surface exists** — only a native link (`pb_hr_workforce/views/workforce_dashboard_views.xml` → `hr_holidays.hr_leave_action_action_approve_department`). No pb_* module extends hr.leave. Core source is NOT in the repo; hr.leave states confirm/validate1/validate/refuse + `action_approve/action_validate/action_refuse` are the installed-core contract (Phase-I facts).
- ✓ **Leave→payroll seam** (untouched context): `om_hr_payroll/models/hr_payslip.py:415` `get_worked_day_lines` → lines keyed by `holiday_status_id` `code` (:432-436, default 'GLOBAL'), WORK100 :471. `hr.leave.type.code` is om_hr_payroll's own extension (`om_hr_payroll/models/hr_leave_type.py:9`). `hr.leave.type` has core `color`; allocation-based types = `requires_allocation='yes'`.
- ✓ **OT request model** (`pb_hr_workforce/models/overtime_request.py`): fields :7-41 (employee/department/manager, `date` :24, planned/actual/approved_hours, overtime_type weekday|weekend|holiday|night, config m2o), states draft/submitted/approved/refused :49-54, `action_submit` :87, `action_approve` :97, `action_refuse` :105, `action_reset_draft` :111.
- ✓ **Ceiling model** (`pb_hr_workforce/models/ot_ceiling.py`): `pb.ot.ceiling` :13 — `name` :17, `company_id` :18, `monthly_cap` 40.0 :21, `annual_cap` 200.0 :22, `annual_cap_special` :23, `active` :27; `hr.employee.pb_ot_special_sector` :50. Per-company + F8 company-on-create conventions apply; C18.20 two-search company-else-global if a global row is introduced (it is NOT today — ceiling rows are per-company, Phase-B F8).
- ✓ **Ceiling read seam**: `hr.attendance.weekentry.get_ot_ceilings(employee_ids, ref_date)` → mtd/ytd vs caps (`attendance_weekentry.py:325-389`); bulk approve `approve_requests` :573-581; facade gates `_require_officer/_require_manager` :36-40. **C18.38**: the week-cap gate is positive-delta-only (reducing an over-cap week must stay allowed — preserve this in the new split logic).
- ✓ **Payroll bridge** (`pb_workforce_payroll_bridge/models/hr_payslip.py`): code→type map OTHRS150/200/300/NGT :9-12; `_get_formula_input_values` override-and-super :19-28; reads **approved** requests via sudo :36-40 (the Phase-B F1/F2 one-permission fix — clone this posture for BONHRS). **Code registry**: OTHRS150/200/300/NGT, TRIPDAYS, PERDIEM; **`BONHRS`** is underscore-free and pairwise non-substring vs all existing (also vs demo input codes like BONPROD) — grep `hr.formula.rule` data for collisions at install anyway (registry convention).
- ✓ **Young-worker gates** (Phase E): OT for minors hard-blocks via `@api.constrains` on hr.overtime.request; grid `flags.is_minor` greys OT cells; weekly cap checks ride `save_week_entries` (C18.33-38).
- ✓ **Native OT UI to retire from menus**: list/form/search/pivot `pb_hr_workforce/views/overtime_request_views.xml` :5-28/:30-81/:83-114/:116-127, actions :130-144; config views `overtime_config_views.xml` :8-27/:30-96, action :99-103. Remove the menuitems; keep actions/views.
- ✓ **VU Form Engine is ON by default** (`biz_theme/static/src/js/vu_form_compiler.js`, kill-switch `biz_theme.vu_form_engine` `biz_theme/models/ir_http.py:20-22`, per-view opt-out class `vu-form-native`) — native forms opened from cockpits are already themed; no form rebuilds.
- ✓ **Cockpit precedent = `pb_attendance_flow`**: facade with first-line `_require` gate (`models/attendance_cockpit.py:30-44`), local Lucide set `pbaf_icons.js` (+`ic(n,s)` helper), sidebar record `data/pb_sidebar.xml:4-13` (section `pb_sidebar.sec_workforce`). Sidebar ICONS available (`pb_sidebar/static/src/js/pb_sidebar.js:15-45`) include `calendar` and `zap` — use those; no pb_sidebar edit. C18.53: new asset files → manifest list + full restart.
- ✓ **pbim tokens are per-cockpit inline** `--pbim-*` blocks (`pb_attendance_flow.scss:17-34`, `pb_pay_delivery.scss:1-31`); tint via root class (`.pbaf.pbim` pattern).

---

## 3. Architecture

### 3a. OT limits + Bonus Hours engine (`pb_hr_workforce` + bridge)

1. **`pb.ot.ceiling` extension**: add `daily_cap`, `weekly_cap`, `biweekly_cap` Floats (default 0.0 = not enforced; monthly/annual keep their defaults). Period definitions (document in the model): daily = the request's `date`; weekly = ISO week; **bi-weekly = the ISO-week pair anchored on odd ISO weeks (1-2, 3-4, …)** — deterministic, no config; monthly = calendar month; annual = calendar year (special-sector cap logic unchanged).
2. **One allowance function** `pb.ot.ceiling._allowance(employee, date, exclude_ids)` → for each ENFORCED period: cap − Σ(approved+submitted `approved_hours` in that period window, excluding `exclude_ids`); returns `min` across periods (∞ if none enforced). Counting base = OT-countable hours only (`approved_hours`), never `bonus_hours` — bonus is definitionally outside the caps.
3. **The split, in exactly TWO call sites**:
   - **Grid save** (`save_week_entries` OT path): compute allowance for the day, set `approved_hours=min(entry, allowance)`, `bonus_hours=entry−approved_hours` on the draft request; return the split in the cell payload so the grid renders it live. The C18.38 positive-delta posture carries over: REDUCING hours is always allowed and re-splits.
   - **`action_approve` override**: recompute the split authoritatively at approval (data may have changed since save) before super; approval stores the final `approved_hours`/`bonus_hours`. This is the only pair of writers of `bonus_hours` (readonly on views/RPC — sentinel not needed since both writers are model-side and the field is facade-readonly; declare it `readonly=True` and write with the ORM from the two sites).
   - **Minors**: skip the split entirely — the Phase-E constraint still hard-raises on any minor OT (test it; rail 5).
4. **New fields on `hr.overtime.request`**: `bonus_hours` (Float, readonly), `total_hours` compute = approved + bonus (display). `planned_hours` stays the raw request.
5. **Bridge (`pb_workforce_payroll_bridge`)**: extend `_get_formula_input_values` — after the OTHRS* block, `BONHRS` = Σ `bonus_hours` of **approved** requests in the slip period (same sudo read posture :36-40, same period windowing as OTHRS*). Register `BONHRS` in the C18 code registry.
6. **VN seed data** on the existing ceiling rows: `daily_cap` 4.0 (VN Labor Code ~50%-of-normal-day practice), weekly/biweekly 0 (disabled) — data only, per-company editable; existing monthly 40 / annual 200/300 untouched.

### 3b. `pb_timeoff` (NEW — depends: `hr_holidays`, `om_hr_payroll`, `pb_sidebar`, `pb_import_kit`)

- **Facade `pb.timeoff`** (AbstractModel), first-line `_require_officer()` on every RPC (officer set = `hr_holidays.group_hr_holidays_user` | `hr.group_hr_manager` | `om_hr_payroll.group_hr_payroll_manager`; verify the hr_holidays xmlid on the installed core; report it).
- `get_board(month)` → `{kpis, queue, heatmap, balances}`:
  - kpis: on-leave-today employee cards (type chip + return date), pending count, this-week out-by-day;
  - queue: hr.leave `confirm`/`validate1`, allowed-companies scope (C18.11/18), items carry employee card, type chip (type color), span+duration, state chip (`To approve`/`2nd approval`), note;
  - heatmap: department × day counts for the month from ONE read_group over validated+pending leaves;
  - balances: employee × allocation-based type: validated allocations − validated taken; server-paged (~30 employees/page — 4.5k demo world, never unbounded).
- `act(leave_id, action, note)` — whitelist `{'approve': 'action_approve', 'validate': 'action_validate', 'refuse': 'action_refuse'}` **as the real user** (C18.17); refuse requires the note; the model's own error surfaces verbatim.
- `apply_on_behalf(employee_id, type_id, date_from, date_to, note)` → plain create + `action_confirm()`; core errors (overlap, balance) surface verbatim. **No sudo anywhere in this module.**
- Sidebar: "Leave" — `sec_workforce`, icon `calendar`, groups = officer set. Action tag `pb_timeoff`.

### 3c. Overtime Desk (`pb_hr_workforce`)

- **Facade `pb.ot.desk`** (new AbstractModel), gates cloned from `attendance_weekentry.py:36-40`; **plus `_require_bonus_viewer()`** = `om_hr_payroll.group_hr_payroll_manager` | `pb_hr_payroll_base.group_payroll_super_admin` — the Bonus tab's server-side gate (the user mandated restriction; approver-tier users do NOT see it).
- `get_desk()` → queue (submitted, org-wide, allowed-companies): employee card, date, type + rate chip, planned vs **split preview** (`approved + bonus` via `_allowance`), that employee's MTD/YTD vs caps (ONE batched `get_ot_ceilings` call); config gallery (rate, windows, day dots, caps incl. the new periods, requires_approval); month stats read_group.
- `act(ids, action, note)` → existing `action_approve`/`action_refuse` per record as the real user; bulk = per-row results (young-worker block message as a row chip, batch never aborts).
- `get_bonus_hours(filters, page)` → gated by `_require_bonus_viewer`; domain from filters (date_from/date_to + presets, employee_ids, department_ids, overtime_type, company, min_hours) over approved requests with `bonus_hours > 0`; returns rows + group-by aggregates (employee/department/day/ISO-week/month) + grand totals; paged and capped, cap surfaced (no silent truncation); `export_bonus_csv(filters)` same gate, row-cap surfaced.
- Sidebar: "Overtime Desk" — `sec_workforce`, icon `zap`, groups = manager set. Weekly-grid item untouched. Native OT menuitems removed.

---

## 4. WOW-UX specification (C18.42 — exceptional, not incremental)

1. **Leave Command Center** (root `.pbto.pbim`, fresh-green tint): white+rail hero with on-leave-today avatar strip + pending KPI pulse; three panes — queue cards (one-click ✓/✗, required-note popover on refuse, optimistic removal, first/second-approval chips), month heatmap (department rows × day columns, density tint, today marker, weekend shading, cell click → day drawer of absentees), balance board (paged matrix, `n / allocated`, amber at ≤2d, type-colored columns). Designed empty states.
2. **Overtime Desk** (root `.pbot.pbim`, amber tint per the grid's OT legend): hero KPIs (pending count, month OT by type stacked bar, over-90%-ceiling count red pulse, **month bonus-hours total** — visible only to bonus viewers); queue cards with **ceiling context bar** (all enforced periods as segmented mini-bars: D/W/2W/M/Y, red >90%) and a **live split chip** (`4h + 2h bonus`); multi-select sticky bulk-approve tray with per-row failure chips; config gallery (rate badge ×1.5/×2/×3/×1.3, day dots, time arc, the five period caps).
3. **Bonus Hours Review tab** (only rendered when the server payload says allowed — the gate is server-side regardless): filter rail on the left (date presets Today/This week/This month/Custom range, employee search, department, OT type, company, min-hours), grouped table with expandable groups + per-group and grand totals, group-by switcher (employee/department/day/week/month), CSV export button with row-cap notice. **Grid touch-up**: the Phase-B weekly grid OT cell shows the split (`4+2b` with an amber `b` chip + tooltip) when the save payload returns bonus > 0 — via the existing `flags`/cell-payload seam (C18.37: setdefault+update, never clobber).
4. Both cockpits: Lucide only via local sets (`pbto_icons.js`/`pbot_icons.js` — in the manifest, C18.53), no gradients/emoji, locked button hierarchy, 390px responsive, `_()` strings + **vi.po** (every entry with `#. module:`).
5. Chrome-MCP: leave queue approve + refuse-with-note, heatmap, balance page 2; OT bulk approve incl. one minor refusal chip; a grid entry that overflows daily cap → split chip visible; Bonus tab as payroll manager AND its absence as a plain approver; 390px both cockpits; empty states. Screenshots.

---

## 5. Safety rails

1. **Facades never write state and never sudo** (leave + desk act paths — C18.17); mutations are the models' own actions as the real user; errors surface verbatim.
2. **Bonus is never a cap bypass for payroll**: OTHRS* inputs keep counting ONLY `approved_hours` (within caps); `BONHRS` is a separate stream the client wires deliberately. The allowance counter never counts `bonus_hours`.
3. **Minors: the Phase-E hard block stands** — no split, no bonus, the constraint raises exactly as today (regression-tested).
4. **`bonus_hours` has exactly two writers** (grid save + approve recompute), field readonly everywhere else; the Bonus Review is read-only and server-gated.
5. **Mail caution (C18.47/48)**: core hr.leave approval can notify followers; live validation ONLY on email-free demo employees (SQL check first); tests TransactionCase; no new mail code.
6. **Bounded reads**: balances paged; bonus review paged + capped-and-surfaced; heatmap/queue company-scoped (C18.11/18).
7. **Demo-pristine**: validation records generator-owned — extend `pb_demo` `ensure_timeoff_demos()` (pending + validated leaves, submitted OT rows incl. one engineered daily-cap overflow so the demo shows a bonus split; report seeds).
8. **One limit source**: `hr.overtime.config.max_hours_*` are NOT enforced anywhere new.

---

## 6. Test cases

**Server:**
1. Facade gates: non-officer AccessError on every `pb.timeoff` RPC; non-manager on `pb.ot.desk.act`; **approver-without-payroll-manager AccessError on `get_bonus_hours` + export** (the restriction assertion).
2. Leave queue lists confirm+validate1 org-wide; other-company leave excluded.
3. `act('approve')` validates (or → validate1 per type — assert what CORE produces); refuse without note raises; core block message surfaces.
4. `apply_on_behalf` → confirm state; overlap → core error, no record.
5. Balance math: 12d allocated − 3d taken = 9; non-allocation types absent.
6. **Split math**: daily_cap 4, entry 6 → 4 approved + 2 bonus. Weekly cap 10 with 8 used → entry 6 → 2+4. **Tightest wins**: daily allows 4, monthly remaining 1 → 1+5. No caps enforced → all approved, bonus 0.
7. **Bi-weekly window**: entries in ISO weeks 27+28 count together; week 29 starts a fresh window.
8. **Approval recompute**: draft split 4+2; another request approved meanwhile eats the allowance → approve → split recomputed (e.g. 2+4).
9. **Reduction stays allowed** (C18.38 regression): shrinking an over-cap day re-splits without raising.
10. **Minor regression**: minor OT entry raises exactly as Phase E — no split, no bonus row.
11. **BONHRS**: slip period with approved requests 4+2 and 3+1 → BONHRS 3.0, OTHRS* unchanged (7.0 to its type); draft/refused requests contribute nothing; code-collision grep vs `hr.formula.rule` data clean.
12. Bonus review filters: date range, department, min_hours each narrow correctly; group-by employee/week aggregates match; cap surfaces when exceeded.
13. OT bulk act: 2 approvable + 1 minor → 2 approved, 1 per-row refusal, batch survives.
14. Menu retirement: OT menuitem xmlids gone; act_window actions still resolve.
15. Facades write no state directly (grep-level: no `.write({'state'` in facades); `bonus_hours` not writable via RPC on the request model (readonly).
16. vi.po loads under vi_VN.

**Chrome-MCP:** §4.5 list with screenshots.

---

## 7. Deploy & verify (Payobook19v2 — memory `payobook-deploy`)

`-i pb_timeoff -u pb_hr_workforce,pb_workforce_payroll_bridge,pb_demo --test-tags /pb_timeoff,/pb_hr_workforce,/pb_workforce_payroll_bridge` (C18.40; C18.54 background+PID-kill; `--uid=odoo`). Full restart (new manifest assets — C18.53) + `/web/assets/%` clear. Generator seeds timeoff demos (incl. the engineered overflow). Verify live: sidebar items per group; board timings at 4.5k employees (<1s per page — report); split chip on the seeded overflow in the grid; Bonus tab gate (two logins); native OT menus gone; VU-skinned form opens from a queue card. Chrome list on email-free demo employees only (C18.48).

---

## 8. Report back

1. Tests 1–16 + the screenshot set.
2. The hr_holidays officer-group xmlid used; VN leave types + `code`s live (payroll consumes them via :436).
3. **BONHRS registered**: confirm the C18 code-registry ledger line updated and the collision grep output.
4. `ensure_timeoff_demos()` seed list + generator diff; board payload timings.
5. Deviations, file list, versions; gotchas → C18 wording.

---

## Kickoff line (paste into the Opus session)

> Read `docs/handovers/SUDIMA_PHASE_K_LEAVE_OT_WOW.md` and `docs/FORMULA_ENGINE_CONVENTIONS.md` (C1, C2, C18 binding — esp. C18.11/17/18/33-38/40/47/48/53/55), then implement Phase K exactly as specified: NEW `pb_timeoff` (Leave Command Center — org queue, month heatmap, paged balance board, apply-on-behalf; every mutation via core hr.leave actions as the real user); the OT limits + Bonus Hours engine in `pb_hr_workforce` (`pb.ot.ceiling` daily/weekly/biweekly caps, ONE `_allowance` function, the split written ONLY at grid save + approve recompute, minors still hard-blocked, `BONHRS` in the payroll bridge); and the Overtime Desk cockpit (queue with ceiling bars + live split chips, per-row bulk results, config gallery, server-gated Bonus Hours Review with full filter rail; native OT menus retired). Facades never write state and never sudo; no new mail code; live validation only on email-free demo employees. Tests §6, deploy §7, report §8.
