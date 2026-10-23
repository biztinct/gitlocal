# SUDIMA Phase B — Overtime WOW Weekly-Entry Grid

**Scope item:** Sudima demo requirement **#9 Overtime Management** — the engine is *Present* (multipliers, ceilings, request workflow); what's missing is a **WOW tabular weekly entry UX** for the HR/manager persona, plus live Vietnam-labor-law ceiling feedback and the payroll wiring for approved OT hours.
**Modules:** NEW `biz_week_grid` (generic component) + cockpit files added inside `pb_hr_workforce` + NEW glue `pb_workforce_payroll_bridge`.
**Ledger:** `docs/FORMULA_ENGINE_CONVENTIONS.md` — **C1, C2, C18 binding** (especially C18.2 formula-code registry and C18.3 one-OT-source rule).
**Prerequisite:** Phase A shipped (sidebar `table` icon already exists in the ICONS const).

---

## 1. Scope

1. A **generic, reusable editable week-grid OWL component** (`biz_week_grid`) — spreadsheet feel, adapter-driven, usable later for project timesheets, roster hours, meal counts.
2. A **Weekly Entry cockpit** in `pb_hr_workforce`: rows = employees, columns = Mon–Sun, cells = regular hours + per-type OT chips; inline editing with live multiplier/ceiling feedback; bulk submit/approve of OT requests.
3. **Ceiling telemetry**: month-to-date and year-to-date OT per employee against configurable caps (VN defaults 40 h/month, 200 h/year, 300 h special-sector) with live bars.
4. **Payroll wiring**: approved OT hours become formula-engine inputs `OTHRS150 / OTHRS200 / OTHRS300 / OTHRSNGT`.

### Binding non-goals
- **NO employee self-entry / ESS flow** — HR/manager bulk persona only (locked decision; ESS comes with the Partial-items phase).
- **NO restyling of the legacy Timecards Gantt** or other `pb_hr_workforce` screens this phase — new screens are pbim-tokenized, old ones untouched.
- **NO autosave** — explicit Save only (attendance writes are heavy and constrained).
- **NO changes to `hr.overtime.config` semantics** — multipliers/types stay as-is.
- **NO merging/deleting of multi-record attendance days** from the grid (read-only cell + popover instead).
- **NO OT worked-days lines emission** — payroll input comes ONLY from approved `hr.overtime.request` (one-OT-source rule).

---

## 2. Verified plumbing facts (do not re-derive)

- ✓ **OT engine** (`pb_hr_workforce`): `hr.overtime.config` (`models/overtime_config.py:7-154`) — `overtime_type` (`weekday|weekend|holiday|night|extended`), `rate_multiplier`, `threshold_hours`, `max_hours_per_day/month`, day-applicability booleans, `time_from/time_to`; seeded 150/200/300/130 % (`data/overtime_config_data.xml:6-50`). `hr.overtime.request` (`models/overtime_request.py:7-115`) — `draft→submitted→approved/refused`, `planned/actual/approved_hours`, config auto-lookup by (type, country, company), workflow methods `action_submit/approve/refuse/reset_draft` at lines 87-113 (approve fills `approved_hours` if unset).
- ✓ **Timecards read path**: `hr.attendance.timecard.get_timecard_data(employee_id, week_start_str, department_id, show_only_with_hours)` (`models/attendance_timecard.py:14-309`) computes REG vs OT per employee-week from raw `hr.attendance` + configs + optional `hr.holidays.public.line`; returns `{days, employees:[{days:{date:{entries,regular,overtime}} , ot_breakdown}], ot_legend}`. **It is a TransientModel and inheritable** — the grid reuses its weekly aggregation for display; per-type colors hardcoded at `attendance_timecard.py:293-300`.
- ✓ **Attendance**: `hr.attendance` core — `check_in/check_out` Datetime, `worked_hours` computed stored; ≥2 records/day per employee possible. Shift source for default start time: `hr.shift.planning` (`models/shift_planning.py:10`, fields `employee_id,date,start_datetime,state`) — use published shifts only.
- ✓ **Formula input seam**: `pb_hr_payroll_formula/models/hr_payslip_formula.py:277-329` `_get_formula_input_values(config)` — worked-days branch fires on `code.startswith('WD_')/startswith('HOURS')` but strips only `WD_`/`HOURS_` (lines 305-306) ⇒ **underscore-free codes cannot ride it; the bridge must override the method, call `super()`, then inject** values for input rules whose code is in its registry. Codes MUST be underscore-free + pairwise non-substring (converter contract, memory `formula-converter-contract`).
- ✓ **Legacy OT double-count risk**: `om_hr_payroll/models/hr_payslip.py:471,483-491` emits `WORK100` + Zoho-sourced OT worked-day codes (`OT15/OT2/OT3/OTNW/…`) when a Zoho employee record exists. A formula config must consume OT from exactly ONE source (C18.3).
- ✓ **Cockpit + sidebar + theming pattern**: as Phase A §2 (clone `pb_people`; `.pbim` kit root + tint class; sidebar item via `action_tag`; `/odoo/action-<tag>` to test).
- ✓ `pb_hr_workforce` menus live in `views/menu_views.xml`; client actions in `views/shift_planning_grid_views.xml`; manifest asset list at `__manifest__.py:42-57`.
- ✓ Employee flags seam for Phase E: none exists — **this phase creates it** (per-row `flags` dict in the grid payload).

---

## 3. Architecture

### 3.1 `biz_week_grid` — generic component (depends: `web` only)

```
biz_week_grid/
├── __manifest__.py         assets → web.assets_backend
└── static/src/
    ├── js/week_grid.js     WeekGrid OWL component (+ registry category "biz_week_grid_adapters" optional)
    ├── xml/week_grid.xml
    └── scss/week_grid.scss  themeable via CSS custom props --bwg-* (defaults set; consumers override)
```

**`WeekGrid` component contract** (props):
- `adapter`: `{ fetch(weekStartISO) → {days[], rows[]}, save(payload) → {results:[{rowId,dayISO,measure,ok,error}]}, validate(cell) → {ok, warn?, error?} }` — validate is called synchronously on local edit (client-side rules the adapter precomputes into row meta).
- Row shape: `{id, label, sublabel, avatar_url, flags:{}, meta:{}, cells:{dayISO: {measures:{<key>: {value, editable, style?}}, note?}} }`.
- Measure defs: `[{key, label, color, min, max, step}]` — first measure renders as the number in the cell; extra measures render as chips.
- Behavior owned by the component: keyboard nav (arrows/Tab/Enter), type-to-edit, dirty tracking (amber dot per cell), **Ctrl+Z/Cmd+Z undo stack pre-save**, per-row revert, explicit Save button wiring (`save` returns per-cell results — failed cells highlight red WITHOUT losing the entered value), row filter/search slot, sticky header + first column, `flags`-driven cell locking (`flags` + per-cell `editable:false` render a lock glyph + tooltip).
- **No Payobook imports** — styling via `--bwg-*` custom props only; Lucide-style inline SVGs allowed (self-contained).

### 3.2 Weekly Entry cockpit (files inside `pb_hr_workforce`; new dep: `biz_week_grid`)

- New TransientModel **`hr.attendance.weekentry`** (`models/attendance_weekentry.py`):
  - `get_week_entries(week_start_str, department_id, search)` → grid payload. Reuses the aggregation logic of `get_timecard_data` (call it, then reshape) — REG measure per day + one measure per **applicable** OT type that week (from `hr.overtime.config` day-applicability); existing draft/submitted/approved request hours pre-fill OT measures (state shown as chip style); per-row `flags` (empty dict now — Phase E's hook) and `meta.multi_record_days` (those cells arrive `editable:false` with popover data); `ceilings` block (see below).
  - `save_week_entries(payload)` → per-cell results. **REG cell write path**: for (employee, day, hours):
    - 0 attendance records that day → create one: `check_in` = published `hr.shift.planning` start for that employee/day if any, else 08:00 in the employee's tz (convert to UTC); `check_out = check_in + hours` (hours are the net figure; no lunch arithmetic); set marker field.
    - exactly 1 record → adjust `check_out = check_in + hours` (keep `check_in`).
    - ≥2 records → refuse (`ok:False, error:'multi'` — the cell was read-only anyway; server re-checks).
    - hours 0 with an existing single grid-sourced record → unlink it; hours 0 + non-grid record → refuse.
  - **OT cell write path**: upsert ONE `hr.overtime.request` per (employee, date, overtime_type): none → create draft with `actual_hours`; existing draft → write `actual_hours`; existing submitted/approved → refuse edit (`error:'locked'` — chip shows state).
  - `submit_week(...)` / `approve_requests(request_ids)` → loop existing `action_submit` / `action_approve` (manager check = existing group gating on those methods' models; do NOT reimplement approval logic).
  - `get_ot_ceilings(employee_ids, ref_date)` → per employee `{mtd, ytd, cap_month, cap_year}` via two `read_group`s over `hr.overtime.request` (`state in submitted,approved`, sum `actual_hours` fallback `approved_hours`).
- New field `hr.attendance.pb_entry_source` Selection `[('grid','Week grid')]` (nullable) — marks synthesized rows; only `grid` rows may be unlinked by the grid.
- New model **`pb.ot.ceiling`** (config): `company_id`, `monthly_cap` default 40, `annual_cap` default 200, `annual_cap_special` default 300; data XML ships the VN record. New `hr.employee.pb_ot_special_sector` Boolean (flips the annual cap). Engine reads config records — no constants in code.
- New client action tag **`pb_attendance_weekgrid`**, OWL cockpit `attendance_weekgrid.js` composing `<WeekGrid>` with the attendance adapter; ceilings rail + submit/approve tray around it. New scss is **pbim-tokenized** (`.pbim.wfg` root class).
- Client-side ceiling liveness: baseline from `get_ot_ceilings` + **unsaved dirty deltas added locally** so bars move while typing.
- Sidebar: `pb.sidebar.item` "Weekly Entry" (icon `table`, `action_tag='pb_attendance_weekgrid'`) in the `workforce` section, sequence right after Timecards; also add a plain menuitem in `views/menu_views.xml` next to Timecards for parity.

### 3.3 `pb_workforce_payroll_bridge` — glue (depends: `pb_hr_workforce`, `pb_hr_payroll_formula`)

- One file: `models/hr_payslip.py` inheriting `hr.payslip`:
  ```
  OT_INPUT_MAP = {'OTHRS150':'weekday', 'OTHRS200':'weekend', 'OTHRS300':'holiday', 'OTHRSNGT':'night'}
  def _get_formula_input_values(self, config):
      values = super()...
      wanted = {r.code for r in config.rule_ids if r.column_type=='input'} & set(OT_INPUT_MAP)
      for code in wanted: values[code] = sum of hr.overtime.request approved_hours,
          employee=self.employee_id, date within [self.date_from, self.date_to],
          state='approved', overtime_type=OT_INPUT_MAP[code]
      return values
  ```
  (`extended` type intentionally unmapped this phase — flag in report-back if configs need it.)
- Install-time guard (per C18.2): a `post_init_hook` logs a WARNING listing any existing `hr.formula.rule` whose code collides with or is a substring-conflict of the four new codes.
- Keep `pb_hr_workforce` installable WITHOUT the formula engine — that is this module's whole reason to exist. No imports of formula models anywhere in `pb_hr_workforce`.

---

## 4. WOW-UX specification

1. **Weekly Entry grid**: full-width white sheet on `--pbim-bg`; sticky employee column (avatar, name, job) and sticky day header (today highlighted with `--pbim-primary-light` wash); REG hours as the big cell number, OT as small rounded chips below it colored by the existing `ot_legend` palette (weekday red / weekend purple / holiday orange / night dark — reuse `attendance_timecard.py:293-300` colors for continuity); weekend columns get a soft tint. Cell states: pristine → flat; dirty → amber corner dot; saving → subtle pulse; error → `--pbim-rose` ring + retained value + tooltip; locked (submitted/approved OT, multi-record REG, Phase-E minor) → lock/shield glyph + tooltip. Selection ring + smooth keyboard navigation must *feel* like a spreadsheet (this is the wow).
2. **Ceiling rail** (right, 300 px, collapsible): per selected/hovered employee — two horizontal budget bars "July OT 31.5 / 40 h" and "2026 OT 122 / 200 h", `--pbim-primary` fill, **amber ≥ 75 %, `--pbim-rose` pulse ≥ 90 %**, hard cap tick; a company mini-leaderboard of nearest-to-ceiling employees. Bars react live to unsaved edits.
3. **Submit/approve tray**: sticky footer bar appearing when drafts exist — "12 OT requests · 38.5 h drafted" + `Submit all` (primary) and, for managers, a pending-approval segment with `Approve selected`. Uses pbim button hierarchy.
4. **Week navigation**: same toolbar grammar as Timecards (‹ Today › + date range + department filter + employee search) for family resemblance.
5. Empty state: illustration-free, Lucide `table` icon + "No employees with entries this week" + the filter hint (match existing Timecards empty-state tone).

---

## 5. Safety rails

1. **Server re-validates everything** the client "already checked": editability (multi-record, locked states), hour bounds `0–24`, Phase-E flags (forward-compat: refuse if `flags` say locked even though this phase sends none).
2. **Never destroy non-grid attendance** — only rows with `pb_entry_source='grid'` may be unlinked/shrunk by the grid; multi-record days untouched.
3. **Timezone correctness**: synthesize `check_in` in the employee tz (`employee.resource_calendar_id.tz` fallback user tz) then store UTC; a 22:00-ish shift crossing midnight keeps date = shift date. Add a test.
4. **One-OT-source rule** (C18.3): the bridge feeds OT ONLY from approved requests; it must NOT also read Zoho OT worked-day lines. Do not remove the Zoho path — just never map both into one config.
5. **Ceilings warn, they don't block** in this phase (blocking is a labor-law judgment for HR); ≥ cap shows the rose state + a confirm dialog on submit ("exceeds the 40 h monthly cap — submit anyway?").
6. **Perf budget**: `get_week_entries` ≤ 3 queries per grid load for ≤ 200 employees (batch reads, no per-cell queries); `save_week_entries` batches creates/writes.
7. Concurrency: payload carries the fetched `write_date`-max snapshot token; if attendance changed since fetch, that cell returns `error:'stale'` (no blind overwrite).
8. All new strings `_`/`_t` wrapped; EN + VI `.po` entries.

---

## 6. Test cases

**Server:**
1. REG create path: no attendance + published shift 07:40 → record 07:40–15:40 for 8 h (UTC-converted correctly for Asia/Ho_Chi_Minh); without shift → 08:00 local.
2. REG adjust path: single existing record 08:00–12:00, cell 9 → check_out 17:00; multi-record day → refused `multi`.
3. Zero-hours: grid-sourced record unlinked; kiosk-sourced record refused.
4. OT upsert: new → draft request with `actual_hours`; edit draft → updated in place (no duplicate); submitted request → refused `locked`.
5. `submit_week` moves drafts → submitted via `action_submit`; `approve_requests` as manager sets approved + `approved_hours`.
6. Ceilings: seed 38 h approved weekday OT in-month → `mtd=38`, cap 40; special-sector employee gets 300 annual cap.
7. Bridge: formula config with input rules `OTHRS150`, `OTHRS200` → payslip `_get_formula_input_values` returns the summed approved hours per type within the slip period, 0 when none; config WITHOUT those rules → dict unchanged vs super.
8. Collision guard: create a rule coded `OTHRS15` (substring) → post_init/log warning fires.
9. Stale-cell: modify attendance after fetch → save returns `stale` for that cell only; other cells commit.
10. `pb_hr_workforce` installs/upgrades cleanly WITHOUT `pb_workforce_payroll_bridge` (no formula dep leak).

**Chrome MCP:**
11. `/odoo/action-pb_attendance_weekgrid` as Mitchell Admin: grid renders for the demo VN division; keyboard-walk 6 cells entering hours; dirty dots appear; Ctrl+Z reverts the last edit; Save → success flash; re-fetch shows persisted values; verify one synthesized attendance via RPC.
12. Enter 6 h weekend OT on a Saturday → purple chip; ceiling bar moves BEFORE saving; push an employee past 90 % → rose pulse; submit-with-overage confirm dialog appears.
13. Bulk tray: Submit all → chips flip to submitted style and lock; as manager approve → approved style.
14. Timecards screen still renders identically (untouched); screenshot both screens for the report.
15. Grid at 200 employees: initial load < 2.5 s (network tab timing), scroll stays smooth (no per-cell RPC).

---

## 7. Deploy & verify

Memory `payobook-deploy` ritual. `-i biz_week_grid,pb_workforce_payroll_bridge -u pb_hr_workforce,pb_sidebar`. **`pb_workforce_payroll_bridge` touches only its own new file — but it inherits `hr.payslip`, so a plain restart carries the Python; still list it in `-i`.** Never `-u pb_hr_payroll_formula`. Bump versions (C2). Chrome-MCP verify §6.11-15 live, using the persistent demo schemes (memory `demo-payroll-test-fixtures`) — do NOT create throwaway employees; use the pb_demo VN division roster.

---

## 8. Report back

1. Results of tests 1–15 (pass/fail each) + the two §6.14 screenshots and the §6.11 grid screenshot.
2. Query counts for `get_week_entries`/`save_week_entries` at 200 employees (prove the ≤3-query budget).
3. Whether any live formula config already contains `OTHRS*`/colliding codes (collision-guard output), and whether `extended` OT type needs a code (§3.3).
4. Any deviation from the write-path rules in §3.2 (what + why).
5. New gotchas → proposed C18 addendum wording.
6. `git status` proof that legacy Timecards/other workforce screens are untouched beyond the manifest/menu additions.

---

## Kickoff line (paste into the Opus session)

> Read `docs/handovers/SUDIMA_PHASE_B_OVERTIME_GRID.md` and `docs/FORMULA_ENGINE_CONVENTIONS.md` (C1, C2, C18 binding), then implement Phase B exactly as specified: new `biz_week_grid` + Weekly Entry cockpit in `pb_hr_workforce` + `pb_workforce_payroll_bridge`, tests §6, live deploy §7. Report back with the six numbered items in §8. Do not restyle legacy workforce screens or touch payroll modules beyond the bridge.
