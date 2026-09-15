# RIZE Wave 2 — Phase D1: Leave & attendance gaps + field check-in (EXTEND, D10)

No new module for leave. Six gaps are filled inside the modules that own the
screens: `pb_timeoff` (Leave Command Center + the `hr.leave` route adapter),
`pb_driver_checkin` (the GPS + selfie PWA and the live map), `pb_today` (the
"who is in" board) — plus ONE additive edit to `pb_mission` (Mission Control =
the **Workforce** rail item) so two new lenses can be bolted on through a soft
registry, exactly as P7/P8/P9/P11 did to the other hubs.

Read first: `RIZE_LEDGER.md` (all), `RIZE_W2_HANDOVER.md` A/B/C4, D13 and
D16 in the ledger, then this file. Version-bump every module you change; a
changed seeded route needs a migration.

## 0. Scope and non-goals
**In scope:** (1) public-holiday calendar for everybody (Workforce lens +
`/my/holidays`); (2) leave escalation to the HR lead after 2 days — VERIFY
first, it may already be in force (§1.3); (3) backdated requests: alert to
HR, allowed only for sick-type leave (with an optional certificate), refused
otherwise with a sentence; (4) past leaves cannot be edited by the employee;
(5) carry-forward watch 6 months before the cut-off; (6) field staff: the
driver PWA generalised to a **Field staff** group (D16), copy renamed "Field
check-in", status on Today, leave overlaps on the map; (7) `pb_mission` soft
lens registry + the two lenses; ⌘K 3800 block; switches; tests; deploy.
**Non-goals:** face matching or any biometric (D13); a new leave model; the
leave types themselves; anything in `hr_holidays`/`hr_attendance` (standard,
never deployed from this repo); shift schedules.

## 1. Verified facts
### 1.1 Modules and facades
- `pb_timeoff/models/pb_timeoff.py`: facade `get_board(month, balance_page)`
  (:103), `_kpis` (:117), `_queue` (:169), `_heatmap` (:196), `_balances`
  (:244), `act(leave_id, action, note)` (:314 — whitelist approve/refuse
  through the model's own actions AS THE USER), `apply_on_behalf` (:340),
  `search_employees` (:372). Adapter `hr_leave_approval.py`: `create`
  overrides at :314 and :419 (read both — two classes), seed at :380:
  `route(manager_step(condition validation_type in manager/both),
  role_step('HR lead','hr_lead', condition in hr/both))`, model `hr.leave`,
  process key `LEAVE_PROCESS_KEY`. Rail item `pb_timeoff.item_leave_center`
  is RETIRED into Mission Control (`pb_timeoff/data/pb_sidebar.xml:20`,
  `active False`).
- `pb_driver_checkin`: group `pb_driver_checkin.group_pb_driver`
  ("Driver", implies `base.group_user`, `security/*.xml:8`); controller
  `controllers/driver_app.py` — `_is_driver()` (:22: driver group OR
  attendance officer), routes `/driver` (:65), `/driver/manifest.webmanifest`
  (:76), `/driver/service-worker.js` (:89), `/driver/state` (:95),
  `/driver/check_in_out` (:100), `/driver/ping` (:117); selfie ≤ 5 MB
  jpeg/png/webp (:15-16), stored on `hr.attendance.pb_selfie_attachment_id`
  (`models/hr_attendance.py:16`). PWA titles "Payobook Driver"
  (`views/driver_pwa_templates.xml:20/48/68`), copy "…enable driver
  check-in" (:56). Map facade `pb.driver.map` (`models/pb_driver_map.py:27`;
  `_driver_group` :39, `_driver_users` :43 — searches `res.users.group_ids`
  (DIRECT membership, R7 — use `all_group_ids` / the group's `all_user_ids`
  when you generalise), `_driver_employees` :52, officer gate :67,
  `get_driver_trail(employee_id, date)` :138). Map template copy: "Drivers",
  "No drivers yet", "Assign the Driver role…" (`static/src/xml/driver_map.xml:47-55`).
- `pb_today/models/pb_today.py`: `get_today_data(department_id, day)`
  (:129), `_row(emp, day_shifts, day_atts, leave, grace, now, is_today)`
  (:253) → dict keys `id, name, job, dept, avatar_url, shift_label,
  shift_start, check_in, check_out, state, is_late, minutes_late,
  leave_type, can_correct` — add `field_checkin` (bool: today's attendance
  has a selfie), `field_selfie_url`, `last_ping` (from the geo ping if the
  map facade exposes it; else omit and say so).
- `pb_mission/static/src/js/pb_mission.js`: `LENSES` literal (:143-197,
  keys today/schedule/time/timeoff/overtime/trips/approvals/close, shape
  `{key, icon, groups, features:{department,week,person,day,search},
  ownsPersonDrawer?}`), `LENS_KEYS` (:198); components mounted by
  hard-coded `t-if="state.lens === '<key>'"` blocks in
  `static/src/xml/pb_mission.xml:100-139` with `embedded="true"`; palette
  rows `pb_hub/static/src/js/hub_palette_entries.js:149-171` use
  `{tag: "pb_workforce", lens, lensKey: "pb_shell_lens"}`. Tests
  `pb_mission/tests/test_sidebar.py` (:76 "seven cockpits one rail item",
  :126 rail lights up, :144, :163, :216) and `test_static.py` — read both
  before touching the file; add the registry test beside them.
- **Public holidays** = `resource.calendar.leaves` with `resource_id`
  empty (`resource/models/resource_calendar_leaves.py:13`: `name,
  company_id, calendar_id, date_from, date_to, time_type`). Live: ONE row,
  company 1; **none for company 5** — the test seeds Vietnam 2026 (Tết,
  Hùng Kings, 30 Apr, 1 May, 2 Sep — the real 2026 dates) on company 5
  and Singapore's on company 6 as demo rows.
- **Leave rules on the server** (`hr_holidays/models/hr_leave.py`): `write`
  (:917) blocks a NON-officer from changing a begun leave only in
  states other than confirm/draft (:920-923) — so an employee CAN still
  edit a past-dated request that is `confirm`; `_check_date_state` (:758)
  blocks edits in validate states. There is NO past-date guard on create
  (grep `allows_request_in_past` = nothing). `hr.leave.type`
  (`hr_leave_type.py`): `leave_validation_type` (:83), `requires_allocation`
  (:88), `support_document` (:113), `allows_negative` (:121). Live types
  (company-less): 1 Paid Time Off (both), 2 Sick Time Off (hr), 7 Sick
  Leave 50 % (hr), 8 Sick Leave 0 % (hr), 3 Compensatory, 4 Unpaid, … 12
  Training Time Off. Allocation: `hr.leave.allocation.date_to` (:68),
  `expiring_carryover_days` (:129), `carried_over_days_expiration_date`
  (:130); accrual plans carry `carryover_date` (`hr_leave_accrual_plan.py:40`).
  Balance: `hr.leave.type.get_allocation_data(employees, target_date)`
  (:493).
- **Engine escalation:** every seeded route carries `late: {remind_days: 1,
  escalate_days: 2}` (`chain_shim.py:120-143`); `engine.py:1551
  escalate_cron` acts after `escalate_days`. **Read `escalate_cron` to
  learn WHO it escalates to** (the step's backup? the next step? the
  responsibility's backup?). If it already reaches the HR lead for a
  manager step, the sheet's requirement is met — prove it with a test and
  record it; if not, ship a migration that rewrites the leave route's
  `late` block (or adds an escalation target the engine supports) — never
  a bespoke cron.
- **Responsibilities:** `biz.approval.responsibility.resolve(company, role,
  scope_keys, on_date)` (`responsibility.py:90`) → the `hr_lead` holder for
  a company (fallback `backup_user_id`, then the pool). Address helpers
  read as the system (R56/R104).
- **Actors:** ess1.demo (uid 1984, employee 10080, company 5; manager
  17122 = lam.ngo uid 2326), validator (holds leave manager + attendance
  manager), a field employee: give `rize.p10.a` (17140) a login
  `rize.w2.field@example.com` / `RizeW2!2026` for the PWA test (D9, listed
  for the owner). Passwords drift (R74).

## 2. Design
### 2.1 `pb_mission` soft registry (additive, own commit, version bump)
`export const MISSION_LENSES = "pb_mission_lens"`; `extraLenses()` spread
at the end of `LENSES` (same shape + `Component`), `LENS_KEYS` derived
after the spread; ONE generic block in the XML after `close`:
`<t t-foreach="extraLenses" t-as="l" t-key="l.key"><div class="pbms-lens"
t-if="state.lens === l.key"><t t-component="l.Component" embedded="true"/></div></t>`.
Rail highlight and arrival routing must accept the new keys (read
`_arrival()` / `_restoreLens()` — a remembered unknown key must fall back
to the first allowed lens). Test: a later module can bolt a lens on
without editing this hub (clone `pb_home_hub/tests/test_home_hub.py`'s
registry test). No palette rows move.

### 2.2 Holidays (`pb_timeoff`)
- Facade `pb.holidays` (`@api.model`, `_safe`, company-scoped): `year(year)`
  → per company: country, rows `{date, name, weekday, days}` from
  `resource.calendar.leaves` (`resource_id` empty, `time_type leave`,
  within the year), plus "next holiday" and counts; `add(company_id,
  name, date_from, date_to)` (officer gate) and `add_many(company_id,
  lines_text)` ("Name | 2026-04-30" per line) — creates rows on the
  company's default calendar (`company.resource_calendar_id`; a company
  with none → the sentence).
- Lens **Holidays** on Mission Control (key `holidays`, icon `sun`, groups
  `[]` — everybody who can open Workforce), `features` all false: year
  strip, one column per company/country side by side, today marker, "Add
  a holiday" / "Paste a list" (officer), empty column teaches.
- `/my/holidays`: every company's list for the year (the sheet: all
  countries visible to all), the session employee's own company first;
  Home card "Holidays · next: Tết in 12 days" (eager key R62). The
  portal read is sudo over public rows only (never a person's leave).
### 2.3 Escalation, backdating, past edits (`pb_timeoff`)
- Escalation: §1.3 verify-first. Outcome either "already in force —
  proven" or a migration that sets it. Switch `pb_timeoff.escalate_days`
  2 read by the seed/migration.
- `hr.leave.type.pb_backdate_ok` (bool, default False; migration sets True
  on the three sick types by name), `pb_backdate_alert` (bool, default
  True). `hr.leave.create` (extend the existing override): a non-officer
  request with `request_date_from < today`: type not `pb_backdate_ok` →
  refused: "Time off in the past can only be entered by HR. Sick leave is
  the exception — pick a sick-leave type."; type ok → allowed, and when
  `pb_backdate_alert` an activity + mail to the company's HR lead
  (responsibility resolve; fallback the leave officer group; R6). The
  Command Center queue card shows a "backdated" chip and the certificate
  (`supported_attachment_ids`) if attached.
- Past edits: `hr.leave.write`/`unlink` (extend): a non-officer touching
  a leave whose `request_date_from < today` (any state) → refused with
  "This time off has already started, so it cannot be changed here. Ask
  HR." Officers unaffected. Switch `pb_timeoff.lock_past` 1.
### 2.4 Carry-forward watch (`pb_timeoff`)
`hr.leave.type.pb_carry_cap_days` (float, 0 = no watch) and company param
`pb_timeoff.carry_cutoff` (`MM-DD`, default `12-31`), `pb_timeoff.carry_warn_months`
6. Monthly job (1st, 06:00; `pb_timeoff.carry_watch` 1): for each employee
× watched type, `remaining = get_allocation_data(...)` today; if
`remaining >= cap` and today is within `warn_months` of the cut-off → one
mail to the employee + one to the manager per (employee, type, year)
(log model `pb.timeoff.carry.log`), an HR summary line. Log-only when
the switch is off (R54); cap as a parameter (R76); test writes dates from
the server clock (R36).
### 2.5 Field check-in (`pb_driver_checkin`, `pb_today`)
- New group `pb_driver_checkin.group_pb_field_staff` ("Field staff");
  `group_pb_driver` gets it in `implied_ids` (drivers remain a case of
  field staff, D16). `_is_driver` → `_is_field` accepts either or the
  attendance officer; the map's `_driver_users` reads the FIELD group
  via `all_user_ids` (R7). Copy: PWA titles "Payobook Field check-in",
  map rail "Field staff", empty state "No field staff yet — give someone
  the Field staff role", action name "Field check-in map", palette row
  label "Open the field map" (it lives in `hub_palette_entries.js:95` —
  a one-word edit in pb_hub is allowed here, own commit). `/field` →
  redirect to `/driver` (the PWA URL stays: an installed app must keep
  working). The selfie stays a photo on the attendance (D13) — no new
  storage.
- Lens **Field** on Mission Control (key `field`, icon `mapPin`, groups
  attendance officer): the existing map component embedded (add an
  `embedded` prop branch that drops its own H1, as every hub lens does).
  Leave overlaps: the map rail lists today's field staff on approved
  leave (`hr.leave` validate covering today) as a chip "On leave —
  Sick", read via the existing leave helpers, company-scoped.
- Today: `_row` gains `field_checkin` + `field_selfie_url`
  (`/web/content/<attachment id>` only for officers) and the board draws
  a camera-pin chip; the person drawer shows the selfie thumbnail.
### 2.6 Palette, switches
⌘K **3800**: `wf_holidays` 3800 ("Public holidays" → Workforce lens
`holidays`), `wf_field` 3810 ("Field check-in map" → lens `field`),
`wf_carry` 3820 ("Carry-forward watch" — opens the Leave lens on the
balances tab, officer gate). Switches: `pb_timeoff.escalate_days` 2,
`pb_timeoff.lock_past` 1, `pb_timeoff.carry_watch` 1, `carry_cutoff`
`12-31`, `carry_warn_months` 6; the Field staff group ships EMPTY (D16).

## 3. Tests
T1  Unit + gates for pb_mission, pb_timeoff, pb_driver_checkin, pb_today;
    the registry test; `pb_mission/tests` still pass.
T2  Holidays: seed VN 2026 on company 5 + SG on 6; `year(2026)` returns
    both columns; `add_many` with a bad line refuses naming the line;
    `/my/holidays` as ess1.demo shows both, own company first; the Home
    card names the next holiday from the server clock.
T3  Escalation: a leave submitted by ess1.demo sits 3 days (move the
    request's dates on the server, R36) → `escalate_cron` acts; assert
    `escalated_at` and WHO now holds the step; if it is not the HR lead,
    the migration fixes it and the test proves the fixed route.
T4  Backdated: Paid Time Off dated last week as ess1.demo → refused with
    the sentence; Sick Time Off dated last week → created, HR lead mail +
    activity, "backdated" chip on the queue card; officer creating a
    backdated PTO → allowed, no alert.
T5  Past edit: ess1.demo changes/deletes a leave that started yesterday →
    refused; officer → allowed; with `lock_past=0` the stock behaviour
    returns.
T6  Carry watch: cap 12 on PTO; ess1.demo with 14 remaining, today within
    6 months of 12-31 (server clock) → 2 mails once; rerun → none; 8
    remaining → none; switch off → log only.
T7  Field: `rize.w2.field` in Field staff (not Driver) opens `/driver`,
    checks in with a selfie (the PWA's own route, 5 MB rule); the map lists
    them; lam.ngo (no group) is refused; a driver still works; the Field
    lens embeds the map; today's leave overlap chip appears for a field
    person on approved leave; Today shows the camera chip for the check-in.
T8  Chrome light + dark: Holidays lens, Field lens, Today chip, the Leave
    queue's backdated chip, `/my/holidays` at 390 px, the PWA at 390 px;
    screenshots `RIZE/w2_d1_*.png`; no console errors.
T9  ⌘K 3800/3810/3820; `pb_mission_lens` holds `holidays` and `field`;
    deploy all changed modules, migrations ran, crons active, log clean.
T10 Reverts (groups, seat, passwords), mails cancelled; the field login
    and the holidays stay (demo, listed).

## 4. Report back
As A1, plus: the escalation verdict (already in force or fixed how), the
registry name, the field group xmlid, every string you renamed, switches,
new R-entries, ledger row, owner items (who is field staff, real carry
caps per type, the cut-off date).
