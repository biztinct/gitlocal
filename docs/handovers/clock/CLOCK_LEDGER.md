# CLOCK — conventions and gotcha ledger

Programme opened 2026-11-05. Goal: punches from a client's biometric / card
attendance machines become paid hours in Payobook with no human re-typing.
The engineering design is `docs/design/biometric/BIOMETRIC_DESIGN.md` (read
§3, §3.3, §3.4, §3.6, §12 before any phase). First client: Sudima Panels VN —
seven ZKTeco-OEM terminals (Ronald Jack 4000TID-C / FA110), ADMS cloud-push
menu present, Mitaco 5 v2 on a shared Windows 11 PC that is off at night.

| Phase | What it delivers | Handover |
|---|---|---|
| CLOCK-1 | **Punches become attendance.** New module `pb_clock`: punch ledger, employee clock code + unknown-number matching, the pairing engine → `hr.attendance` source `device`, the **local-day fix** in grid / packet / freeze, "Time-clock punches" upload mode (Excel / CSV / ZK `attlog.dat` / Mitaco daily sheet), a **Time clocks** lens in the Time hub. | `CLOCK_P1.md` |
| CLOCK-2 | **Machines push to Payobook.** The ADMS (ZK PUSH / iclock) receiver, serial allow-list, time sync in the handshake, HTTPS + per-tenant plain-HTTP fallback host, backfill request, terminal health rows. | `CLOCK_P2.md` |
| CLOCK-3 | **Trust.** Health card in Integrations + alerts (silent terminal, clock skew, zero punches by 11:00), late-punch-after-approval exceptions, nightly 35-day re-check, Vietnamese, lessons. | `CLOCK_P3.md` |
| CLOCK-4/5 | More recipes / the Windows Bridge for clients whose machines cannot push; late-minutes into payslip inputs. | later |

Owner rulings 2026-11-05, asked once, do not re-ask:
1. Workflow: **phased, Fable designs, Opus builds**, same session, back to back.
2. **Route for Sudima = ADMS push.** The Windows Bridge is demoted to CLOCK-5.
3. **Plain-HTTP fallback host is allowed** for terminals whose firmware cannot
   negotiate TLS; switched on per company, carries only serial + user id +
   timestamp + verify type.
4. **Sudima gets its own tenant `sudima.payobook.com`** before setup day (ops
   step through `pb_tenants`, not a phase deliverable).
5. The owner talks to Sudima's IT (Sashi) and the supplier directly.
6. Earlier ruling 2026-11-02 "wait, design only" is superseded by 1.

## 0. Binding rules for every phase

Read `docs/handovers/orgchart/ORGCHART_LEDGER.md` §0 (which chains to
`fillin/FILLIN_LEDGER.md` §0 → `SCHEMECTX_LEDGER.md` §0). Those rules bind
here **verbatim**: plain English and never "Odoo" on screen; the design bar
(*"extreme WOW, intuitive, out-of-this-world experience, best in class"* —
hero moment named, every state designed, plain language on every label and
toast, motion with purpose, keyboard + bulk ergonomics, Lucide via the shared
`ic()` registry `@pb_import_kit/js/import_icons`, never emoji, grey at zero);
browser validation with Chrome MCP on `rize.payobook.com` and `payobook.com`;
deploy set = `payobook`, `payobook_template`, `p0clone`, `rize`, never `abm`;
`/odoo/ops/filter_deploy.sh` staged from committed HEAD, START/DONE in
`/opt/deploy-notes.md`, announce to other sessions first; tests on `p0clone`
with the SCHEMECTX §0.13 recipe (scoped `-u`, alternate ports, never
`--test-tags` without `-u`); commit per feature on `19.1` + push, secrets scan;
a read RPC never writes; PO three-marker rule; SCSS gate on the box; the
`act_window` dict needs `views` (memory `payobook-cockpit-pattern`).

Programme-specific additions:

7. **The ledger is append-only.** `pb.clock.punch` rows are created by the
   intake paths and only their matching / pairing fields are ever written
   (`employee_id`, `state`, `attendance_id`, `note`). No user-facing delete.
   System admin may unlink for data-protection requests only.
8. **Never store biometrics.** Templates, photos, face data arriving from any
   source (upload, ADMS `BIODATA`/`USERPIC`, Bridge) are acknowledged and
   dropped. The ledger holds a number, a time, a serial and a verify type.
9. **Device data never silently overrides a human.** Pairing writes only rows
   with `pb_entry_source = 'device'`; it never edits grid / import / correction
   rows; a day that is locked (`pb_close`), frozen (`pb.timesheet.freeze`) or
   has a correction is left alone and the punch is noted, not applied.
10. **Pairing is idempotent.** Running it twice on the same ledger changes
    nothing. Every phase's tests include that assertion.
11. **A day is the employee's LOCAL day everywhere.** Grid, packet, freeze,
    lock, exceptions and the ledger all key by local date after CLOCK-1. No
    new code may call `check_in.date()` on a UTC datetime to mean "the day".
12. **The upload mode is the permanent fallback** — every later intake path
    (ADMS, Bridge) writes to the same ledger and goes through the same
    pairing; nothing may pair "inline" in an HTTP request or a file import.
13. **Client files stay out of git.** `SUDIMA/` is excluded in
    `.git/info/exclude`; no name, phone, serial number or hostname from the
    client's answers goes into a committed file or a test fixture. Test data
    uses the shapes (codes `885`, `227`, the times) and invented serials.
14. **Pause rule** (memory `usage-limit-pause`): at a usage warning commit WIP
    with `PAUSED` in the message and stop; the coordinator resumes.

## 1. Verified facts — do NOT re-derive (2026-11-05, repo HEAD 8335eec06)

### Attendance today

- `pb_entry_source` on `hr.attendance` is a Selection extended by
  `pb_attendance_flow/models/hr_attendance.py:33-35` with `correction`,
  `import`; the grid writes `grid` (`pb_hr_workforce/models/attendance_weekentry.py:565`).
  **A blank value means a device/kiosk punch** (`_is_device_row`,
  `hr_attendance.py:37-40`); application payroll's mixed-source check does
  `pb_entry_source or 'device'` (`pb_hr_payroll_formula/models/application_payroll_source.py:364-370`)
  and the packet snapshot does the same (`pb_timesheet_approval/models/timesheet_packet.py:303-304`).
  Adding the explicit value `device` is therefore safe for those two; only
  `_is_device_row` must learn it.
- The grid refuses to edit a non-grid row (`attendance_weekentry.py:543-544`,
  error `notgrid`) — device rows are read-only in the Week Grid by construction.
- Exception kinds the feed computes (read-only, never writes):
  `missing_punch`, `missing_checkout`, `late`, `early_leave`
  (`pb_attendance_flow/models/attendance_exception.py:22-25`). An open device
  attendance (check_in only) surfaces as `missing_checkout` with no new code.
- Corrections model: `hr.attendance.correction` (`pb_attendance_flow/models/attendance_correction.py`),
  the one guarded writer under a module sentinel; a device punch can only be
  deleted through one (manifest description).
- Import wizard `pb.attendance.import.wizard` (`pb_attendance_flow/wizards/attendance_import.py`):
  officer gate `_require_officer` (:50-57), tz helper `_emp_tz`/`_to_utc`
  (:61-72), XLSX/CSV reader `_read_rows` (:83-130) with the surfaced 2000-row
  cap `_MAX_ROWS`, employee index by barcode / name (:187-205), per-row
  savepoint commit (:323-372). It writes `hr.attendance` directly with source
  `import`. The Import lens mounts the same cockpit component with
  `initialView="'import'"` (`pb_time_hub/static/src/xml/time_hub.xml:66-67`).

### The UTC-day bug (CLOCK-1 fixes it)

All three bucket a punch by the stored UTC `check_in.date()` and bound the
week search by UTC midnight:

- Week Grid read: `pb_hr_workforce/models/attendance_weekentry.py:196-211`
  (`ws_dt`/`we_dt` from `week_start`/`week_end`, key `check_in.date().isoformat()`).
- Week Grid save: `attendance_weekentry.py:468-477` (`att_map` keyed
  `(emp, check_in.date())`); the write side builds `check_in` from the local
  day at 08:00 in the employee tz (:559-560) or the shift start (:556-557), so
  grid-made rows already sit on the right local day — only the READ keying is wrong.
- Packet: `pb_timesheet_approval/models/timesheet_packet.py:213-229`
  (`_week_bounds`, docstring admits the convention) and `:253-267`
  (`by_day` by `check_in.date()`).
- Freeze: `pb_timesheet_approval/models/week_freeze.py:111-133`
  (`_pb_week_pairs`, `create`, `write` key `(employee, check_in.date())`).
- The CLOSE lock already keys by local day:
  `pb.wf.lock._local_day(employee, dt_utc, cache)` at
  `pb_close/models/wf_lock.py:232-254` (employee tz → company calendar tz →
  UTC). The guard `pb_close/models/hr_attendance.py:38-58` uses it.
- Dependency order (so the helper must live LOW): `pb_hr_workforce` ←
  `pb_attendance_flow` ← `pb_time_hub` ← `pb_close` ← `pb_timesheet_approval`.
  `pb_hr_workforce` depends on `hr_attendance, resource, biz_week_grid,
  pb_wf_kit, pb_import_kit, pb_filter_kit, …` (its manifest). Put the shared
  helper on `hr.attendance` in `pb_hr_workforce`; `pb_close._local_day` may
  delegate to it later (not in CLOCK-1 — it is correct already).
- Employee tz: `hr.employee._get_tz()` at `hr/models/hr_employee.py:1517-1522`
  (vendored = server standard set; do not edit `hr`).

### Payroll path (unchanged by CLOCK)

`pb.timesheet.packet._scan_week` (`timesheet_packet.py:240-320`) → approved
week → `HrPayslip._get_formula_input_values` REGHRS / TOTHRS / WORKDAYS / OT
(`pb_timesheet_approval/models/hr_payslip.py:69-110`), gated by
`res.company.pb_timesheet_payroll`. `om_hr_payroll.get_worked_day_lines`
never reads attendance (`om_hr_payroll/models/hr_payslip.py:496-497`) — do
not wire there.

### Time hub (where the new lens mounts)

- `pb_time_hub/static/src/js/time_hub.js`: `LENSES = ["timeline","grid",
  "exceptions","import"]` (:32), `get lenses()` (:118-125) returns
  `{key,label,icon}`; `lensCount(key)` (:127-130) reads
  `summary.lens_counts` from `pb.time.hub.get_hub_summary()`
  (`pb_time_hub/models/time_hub.py:117-177`, returns `lens_counts:
  {'exceptions': total}` at :173-174). Lens bodies are a `t-if/t-elif` chain in
  `pb_time_hub/static/src/xml/time_hub.xml:40-75`; each lens component is
  mounted with `embedded="true"`.
- The hub is itself the Time LENS of Mission Control (`pb_mission`, W17/W26);
  its own rail item is retired (`pb_time_hub/data/pb_sidebar.xml`, sequence
  908, `active=False`). A new lens appears inside Mission Control › Time
  automatically; **no new rail item**.
- Officer gate: `hr_attendance.group_hr_attendance_officer`
  (`pb.time.hub._require_officer`, `time_hub.py:95-100`).
- Shared week/department/person context: `wf_context` service (`pb_wf_kit`).

### Precedents to clone

- Cockpit facade + `_safe` + company scoping: `pb_time_hub/models/time_hub.py`,
  `pb_attendance_flow/models/attendance_cockpit.py`.
- Stale-feed health sentence: `pb_integrations/models/pb_integrations.py:211-236`.
- Cron `_trigger()` for "run soon": `pb_decision_room/models/pb_decision_exact.py:167`.
  There is **no `queue_job`** in this repo — use an `ir.cron` every 5 min plus
  `cron.sudo()._trigger()` after an upload.
- Per-row savepoints: `attendance_import.py:323-372`; `attendance_weekentry.py:505-524`.
- Lens with a typeahead and bulk actions: `pb_people/models/pb_people.py:467-481`
  (`bulk_apply` answers `{'error': 'plain sentence'}`).
- Sidebar / learn manifest: `pb_time_hub/learn_manifest.py` (lessons follow
  screen changes — CLOCK-3 adds the lesson; CLOCK-1 lists affected ones).

## 2. Design decisions (binding)

- **D1 — Pairing = anchor + span.** Per employee, punches sorted by local
  time. A work day opens at the first unassigned punch (the anchor) and takes
  every punch within `pb_clock_max_span_h` hours (company setting, default
  **21**, label "Longest possible work day"); the next punch after the span
  opens a new day. The day's **date = the anchor's local date**. First punch =
  check-in, last = check-out, middle punches stay in the ledger as `middle`
  (shown, not paid). Why not a fixed window: Sudima's shifts include
  07:30→04:00 next day and 19:30→07:30 next day; no clock-time boundary
  separates them, the anchor does. Why 21 h: longest shift 20.5 h, next day's
  start is ≥ 24 h after the anchor.
- **D2 — Double tap** = same employee within `pb_clock_double_tap_min`
  (default 2) → keep the first, mark `ignored_duplicate_tap`.
- **D3 — Direction is not trusted by default** (`pb_clock_trust_direction`
  false). Sudima's answer: nobody presses IN/OUT.
- **D4 — Live pairing.** A day is written as soon as its anchor arrives
  (open attendance), and updated as later punches land. Re-pairing a day =
  recompute desired `(check_in, check_out)` and reconcile with the existing
  `device` rows for that employee-day: update in place, create if none, never
  touch non-device rows (if one overlaps → skip, note `manual entry exists`).
  Locked / frozen / corrected days → skip + note; the punch stays `held`.
- **D5 — Matching order** for a device user id: `hr.employee.pb_clock_code`
  → `barcode` → `identification_id`, company-scoped, active employees first
  then archived (a leaver's late punches still match). Unmatched → state
  `unmatched`, surfaced in the lens with a one-click assign that re-pairs the
  back-log.
- **D6 — Outliers**: punch > now + 10 min or year < 2015 → `ignored_outlier`.
- **D7 — Sources** on the ledger: `upload`, `mitaco_export` (first/last per
  day from the Mitaco daily sheet — lower trust, `direction` set in/out),
  `adms` (CLOCK-2), `bridge` (later). `dedup_key = sha1(company|device
  serial or 'upload'|user_code|punch_local to the second)`, unique index.
- **D8 — Lens name "Time clocks"**, inside Time hub after Import. Badge =
  unknown numbers with punches in the context week. Hero = one sentence:
  "Last punch 3 minutes ago, Factory 2 · 612 people punched today" or, with
  no machine yet, "No machine connected. Upload a punch file to start." with
  the upload door.
- **D9 — Settings live on `res.company`** (`pb_clock_max_span_h`,
  `pb_clock_double_tap_min`, `pb_clock_trust_direction`) and are edited from a
  settings card in the lens (manager only); no native settings page.

## 3. Gotchas hit (append as they come)

| # | Date | Gotcha | Rule |
|---|---|---|---|
| G1 | 2026-11-05 | zsh expands `--include=*.py` as a glob ("no matches found"); quote it. | `--include='*.py'` in every grep on this box. |
| G2 | 2026-11-05 | SSH alias `Payobook19` resolves to 54.206.36.246 and refuses; the live box is `Payobook19v2` (3.104.113.197). | Use `Payobook19v2`. |
| G3 | 2026-11-05 | `filter_deploy.sh full` restores the PRE-deploy set of active crons, so a cron a new module installs comes out OFF everywhere. | After the deploy switch it on by hand per DB (off on payobook_template, id appended to `pb_tenants.template_active_crons` — it holds ids, not xmlids). |
| G4 | 2026-11-05 | OWL rejects statements inside inline handlers: `t-on-keydown="(ev) => { if (...) {...} }"` → "Failed to compile template … Unexpected token '{'" — only when the lens first renders, after a deploy. | Handlers that need `if` are methods. `t-on-click.stop` needs a method too, not `() => {}`. |
| G5 | 2026-11-05 | A word inside a template expression (`t-esc="n === 1 ? 'punch' : 'punches'"`, `t-att-title="'Show ' + x"`) is never extracted for translation. | Plural phrases and built tooltips live in JS getters with `_t()`. |
| G6 | 2026-11-05 | `odoo-bin --i18n-export` is gone on this build; it is `odoo-bin i18n export -c … -d … -l vi_VN -o file.po module`. Its output carries all three PO markers per entry; its header says the brand name — replace it before committing. | Generate PO files from the export, fill msgstr. |
| G7 | 2026-11-05 | Installing a NEW module on p0clone from a scratch addons dir leaves the live server's p0clone with an installed module it cannot load (views/cron referencing it) until deploy. | Iterate on a throwaway copy (`pg_dump p0clone | pg_restore` → `clk1test`, crons off); drop it after. |
