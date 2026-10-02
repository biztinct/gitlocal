# SUDIMA Phase E — Young Worker Rules (Under-18 Compliance Guard)

**Scope item:** Sudima demo requirement **#10 Young Worker Rules** (*Not Built*): age validation gates, daily/weekly hour caps, absolute overtime blocks, payroll exception warnings for underage/young employees.
**Module:** NEW `pb_young_worker` (single module, config-driven and country-agnostic — VN Labor Code values are DATA, not code).
**Ledger:** `docs/FORMULA_ENGINE_CONVENTIONS.md` — **C1, C2, C18 binding**.
**Prerequisites:** Phase B shipped (the grid's per-row `flags` seam — this phase populates `flags.is_minor`); sidebar `shield` icon exists from Phase A. (Independent of C and D.)

---

## 1. Scope

1. **Config-driven rule engine**: age bands with daily/weekly hour caps, absolute OT block, night-work block — per company, shipped with Vietnam Labor Code defaults as data.
2. **Four enforcement gates** (three hard, one advisory): OT requests (hard), daily attendance cap (hard), night-shift assignment (hard), payroll run warnings (advisory, via the existing exceptions surface).
3. **Young Worker Guard cockpit**: under-18 roster, hour gauges, violation feed, rules settings.

### Binding non-goals
- **NO under-15 hiring workflow / work-permit management** — we gate hours and OT for existing employees; contract/permit compliance docs are out of scope.
- **NO payroll blocking** — payroll gate WARNS via the exceptions list; it never skips or blocks an employee's slip.
- **NO retro-enforcement**: constraints apply to new/modified records; existing historical data is reported in the cockpit's violation feed, not mutated.
- **NO changes to Phase B grid internals** — only its published seams: `flags` payload + server-side `save_week_entries` validation hook.
- **NO hardcoded ages/caps anywhere** — config records only.

---

## 2. Verified plumbing facts (do not re-derive)

- ✓ **Payroll warning seam**: `pb_payrun_wizard/models/pb_payrun_wizard.py` — `pb.payrun.wizard` AbstractModel; `create_and_compute(vals)` (lines 93-162) and `compute_batch` (line 211+) accumulate `exceptions: [{'emp': name, 'why': str}]` into the returned summary (`summary['exceptions']`, line 160), which the Run Payroll cockpit renders in its "Review exceptions" step — **inherit, wrap with super, append entries; zero new payroll UI needed**.
  ⚠ `pb_demo` OVERRIDES `create_and_compute`/`prepare_run`/`compute_batch` with a division-scoped formula path (memory `payobook-deploy`, `pb_demo/models/demo_payrun.py`) — the inherit must land on the base AbstractModel so Python MRO puts our wrapper around BOTH paths; verify the demo wizard actually surfaces the warnings (test 9).
- ✓ **OT request model**: `hr.overtime.request` (`pb_hr_workforce/models/overtime_request.py:7-115`) — constrain here blocks every entry path (form, Phase B grid upsert, RPC).
- ✓ **Attendance**: `hr.attendance` core (`check_in/check_out/worked_hours`); `@api.constrains('check_in','check_out')` fires on create/write from all sources (kiosk, systray, Phase A GPS, Phase B grid).
- ✓ **Shifts**: `hr.shift.planning` (`pb_hr_workforce/models/shift_planning.py:10`) — `employee_id`, `date`, `start_datetime/end_datetime`, template with `start_hour/end_hour/is_overnight` (`shift_template.py:7`).
- ✓ **Phase B seams**: `hr.attendance.weekentry.get_week_entries` emits per-row `flags` (empty by default) and `save_week_entries` re-validates server-side, refusing cells whose flags lock them (Phase B handover §3.2, §5.1 forward-compat rule).
- ✓ **Age source**: core `hr.employee.birthday` (standard Odoo field; `hr.version` carries personal info in Odoo 19 but `birthday` remains readable on the employee — verify the exact field name on the live registry before coding: `birthday` vs `private`-scoped access, and note HR-officer visibility).
- ✓ Cockpit/sidebar/theming as Phase A §2.

---

## 3. Architecture

### `pb_young_worker` (depends: `hr`, `hr_attendance`, `pb_hr_workforce`, `pb_payrun_wizard`, `pb_sidebar`, `pb_import_kit`)

```
pb_young_worker/
├── models/
│   ├── young_worker_rule.py     pb.young.worker.rule (config) + pb.young.worker AbstractModel (engine)
│   ├── overtime_request.py      hard OT gate
│   ├── hr_attendance.py         daily-cap gate
│   ├── shift_planning.py        night-shift gate
│   ├── attendance_weekentry.py  flags injection + weekly-cap validation (inherits Phase B transient)
│   └── payrun_wizard.py         advisory payroll gate
├── data/young_worker_vn.xml     VN Labor Code default bands (noupdate="1")
├── security/                    ACLs (config: payroll manager write, user read)
├── views/ actions.xml + rule form/list (native views for config)
└── static/src/ js|xml|scss      Guard cockpit (tag pb_young_worker)
```

**Config — `pb.young.worker.rule`** (one rule set per company; bands as lines `pb.young.worker.band`):
- Rule: `company_id`, `active`, `night_from` Float default 22.0, `night_to` Float default 6.0
- Band: `rule_id`, `age_min` Integer, `age_max` Integer (exclusive upper), `max_hours_day` Float, `max_hours_week` Float, `ot_blocked` Boolean, `night_blocked` Boolean, `note`
- **VN data** (`young_worker_vn.xml`): band <15 → 4 h/day, 20 h/week, OT blocked, night blocked; band 15–<18 → 8 h/day, 40 h/week, OT blocked, night blocked. (Adults = no band = no restrictions.)

**Engine — `pb.young.worker` AbstractModel** (all gates call these; no logic duplicated):
- `get_band(employee, on_date)` → band record or False (age = full years at `on_date` from birthday; **no birthday on file → treated as adult but flagged in the cockpit** — never guess an age)
- `is_minor(employee, on_date)` → bool
- `check_day_hours(employee, date, extra_hours=0)` → `{ok, cap, actual}` (sum of that day's attendance + extra)
- `check_week_hours(employee, any_date_in_week, extra=0)` → same for the ISO week
- `check_period(employees, date_from, date_to)` → violations list `[{employee_id, name, kind: 'day_cap'|'week_cap'|'ot'|'night'|'no_birthday', date, detail}]` — batch, read_group-based (this feeds both the payroll gate and the cockpit feed)

**Gates**
1. **OT (hard)** — `hr.overtime.request`: `@api.constrains('employee_id','date')` + create/write → if band `ot_blocked` on `date` → `ValidationError(_("Overtime is not permitted for workers under 18 (Vietnam Labor Code). %s is %d."))`. This is authoritative for every entry path.
2. **Daily cap (hard)** — `hr.attendance`: `@api.constrains('check_in','check_out','employee_id')` → when a band exists and the day's total (all records that local day) exceeds `max_hours_day` **+ 0.5 h grace** → ValidationError naming cap and total. Weekly cap is NOT enforced per-punch (perf + partial-week semantics).
3. **Night shift (hard)** — `hr.shift.planning`: constraint on assignment → if band `night_blocked` and the shift window (template hours; handle `is_overnight`) overlaps `night_from→night_to` → ValidationError.
4. **Weekly cap + grid flags** — inherit `hr.attendance.weekentry`: `get_week_entries` → for banded employees set `flags = {'is_minor': True, 'band': {caps…}}` and mark OT measures `editable:false`; `save_week_entries` → before write, run `check_week_hours` including the pending payload deltas; violating REG cells return `{ok:False, error:'week_cap', detail}` (per-cell, others commit).
5. **Payroll (advisory)** — inherit `pb.payrun.wizard`: wrap `create_and_compute` and `compute_batch` — after `super()`, run `check_period(run employees, ds, de)` and append to `result['exceptions']`: `{'emp': name, 'why': 'Young worker: 44.0h in week of 10 Mar exceeds the 40h cap'}` (one row per violation kind/week, capped at 3 per employee + "…and N more"). Never raise; never skip slips.

**Cockpit** (tag `pb_young_worker`, AbstractModel `pb.young.worker.guard.get_guard_data()`):
- Roster of banded employees (companies-scoped): avatar, age + **days-to-18 countdown chip**, band label, this-week hours vs cap gauge, MTD violations count, missing-birthday flag list.
- Violation feed: last 30 days from `check_period`, newest first, kind icons.
- Rules card: read-only band table + "Edit rules" button (opens native config form; payroll-manager gated).
- Sidebar item "Young Workers" (icon `shield`), section `compliance`, groups HR officer+.

---

## 4. WOW-UX specification

1. **Guard cockpit**: calm compliance aesthetic — white cards on `--pbim-bg`, `--pbim-primary` accents, shield motif. Top KPI strip: Protected workers · Compliant this week · Violations (30 d) · Missing birthdays. Roster cards with the **age-countdown chip** ("17 y 9 m — adult in 84 days", flips green at 18) and a slim week-hours gauge (green → amber ≥ 80 % → rose over cap).
2. **Violation feed**: timeline rows — kind icon (clock = day cap, calendar = week cap, moon = night, zap-off = OT attempt, help = missing birthday), employee, date, human sentence ("Attempted 2 h weekend OT — blocked").
3. **Inline guards elsewhere** (already specified in their phases, listed here for the demo story): locked OT cells with shield glyph + tooltip in the Phase B grid; amber shield rows in the payrun "Review exceptions" step; the hard ValidationErrors read as helpful law citations, not stack traces.
4. **Rules card**: band table styled like a statutory table (age range, day cap, week cap, OT ✕, night ✕) with an "VN Labor Code defaults" caption.

---

## 5. Safety rails

1. **Hard gates raise `ValidationError` with human messages** (translated EN/VI) — never a bare exception; messages cite the cap and the computed figure.
2. **The payroll gate never blocks pay** — advisory only; a violating minor still gets a slip (labor-law remediation is HR's job, not the payroll engine's).
3. **Missing birthday ≠ minor**: treat as adult for gates (no false blocks), surface prominently in the cockpit as a data-quality task.
4. **Timezone/day boundaries**: daily totals computed on the employee-tz local day (consistent with Phase B's synthesis rule); week = ISO week.
5. **Perf**: constraints touch only the record's employee/day (indexed reads); `check_period` is batch/read_group — payroll wrap adds ≤ 2 queries per run per check kind, and must be measured on the 4.5k-employee demo run (report-back item).
6. **`pb_demo` wizard override compatibility** (§2 ⚠): base-class inherit + live verification that demo runs surface the warnings.
7. Config edits are payroll-manager gated; bands validated (no overlapping age ranges, min < max).

---

## 6. Test cases

Fixture: use persistent demo employees (memory `demo-payroll-test-fixtures`) — add two REUSABLE named minors to the pb_demo roster (17-year-old, 14-year-old) rather than throwaway records, plus one employee with no birthday.

**Server:**
1. Band resolution: 14 → <15 band; 17 → 15–<18 band; 18 on the birthday → no band; no birthday → no band + `no_birthday` violation in `check_period`.
2. OT gate: creating an `hr.overtime.request` for the 17-year-old raises ValidationError (any type, any path incl. Phase B upsert).
3. Daily cap: attendance totaling 8.6 h for the 17-year-old (cap 8 + 0.5 grace) raises; 8.4 h passes; the 14-year-old blocks past 4.5 h.
4. Night gate: assigning the 17-year-old a 21:00–05:00 shift raises; a 06:00–14:00 shift passes; overnight-template handling correct.
5. Weekly cap via grid: payload pushing the 17-year-old's week to 42 h → that REG cell returns `week_cap`, other cells commit; grid payload carries `flags.is_minor` + locked OT measures.
6. `check_period` on a seeded violation week returns exactly the expected violation rows (kinds + dates).
7. Payroll wrap: base `create_and_compute` on a run containing the minors returns `exceptions` including the young-worker rows appended AFTER super's own (contract-missing etc. preserved).
8. Config integrity: overlapping bands rejected; per-company isolation (company B without a rule set = no gates).
9. **pb_demo path**: run the demo division wizard (formula path) → young-worker warnings appear in its returned exceptions (the §2 ⚠ check).
10. Adults are untouched: no constraint fires for a 30-year-old at 12 h/day (no band) — prove zero behavior change for the general population.

**Chrome MCP:**
11. `/odoo/action-pb_young_worker`: roster shows the two minors with countdown chips and gauges; missing-birthday employee flagged (screenshot).
12. Phase B grid for the minors' week: OT cells shield-locked with tooltip; enter REG hours over the week cap → rose cell + message (screenshot).
13. Run Payroll (demo cockpit) through the exceptions step: young-worker warnings visible with shield styling (screenshot).
14. Native OT request form: submitting for a minor shows the friendly ValidationError toast.
15. Rules card renders the VN band table; editing requires payroll-manager (demo read-only user sees no edit button).

---

## 7. Deploy & verify

Memory `payobook-deploy` ritual. `-i pb_young_worker -u pb_hr_workforce,pb_payrun_wizard,pb_sidebar`. Never `-u pb_hr_payroll_formula` (the payrun wrapper lives in `pb_payrun_wizard`'s inherit chain — pure Python, but the module carries data/views so real `-u` for it). Bump versions (C2). Verify §6.11-15 live; then run one full demo-division payroll to confirm no perf regression (compare wall-clock vs a pre-install run; §5.5).

---

## 8. Report back

1. Tests 1–15 results + the three screenshots (§6.11-13).
2. The exact birthday-field access story found on Odoo 19 live (field name, group visibility) — §2 verification.
3. Payroll wall-clock delta on the demo division run (before/after) — §5.5.
4. Confirmation the pb_demo wizard override surfaces the warnings (test 9) — if it does NOT, the wrapper landed on the wrong class; fix before reporting.
5. Deviations (what + why), file list, manifest versions.
6. New gotchas → proposed C18 addendum wording.

---

## Kickoff line (paste into the Opus session)

> Read `docs/handovers/SUDIMA_PHASE_E_YOUNG_WORKERS.md` and `docs/FORMULA_ENGINE_CONVENTIONS.md` (C1, C2, C18 binding), then implement Phase E exactly as specified: new `pb_young_worker` with the four gates (three hard, payroll advisory), VN bands as data, Guard cockpit, tests §6, live deploy §7. Report back with the six numbered items in §8. The payroll gate warns — it must never block or skip a payslip.
