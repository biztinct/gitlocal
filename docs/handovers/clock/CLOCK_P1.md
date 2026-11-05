# CLOCK-1 — Punches become attendance

Read first: `CLOCK_LEDGER.md` (§0 rules bind verbatim, §1 facts are
verified — do not re-derive, §2 decisions are final), then
`docs/design/biometric/BIOMETRIC_DESIGN.md` §3.1, §3.3, §3.4, §3.6, §12.

## 1. Scope

Deliver, in this order, each as its own commit:

1. **Local-day fix** in grid, packet, freeze (`pb_hr_workforce`,
   `pb_timesheet_approval`).
2. **`pb_clock` module**: ledger, device, employee clock code, company
   settings, `device` entry source, security.
3. **Pairing engine** + cron + the re-pair rules.
4. **Upload mode** "Time-clock punches" in the import wizard and the Import
   lens (Excel / CSV / ZK `attlog.dat` / Mitaco daily sheet).
5. **Time clocks lens** in the Time hub (lens registry in `pb_time_hub` + the
   lens itself in `pb_clock`).
6. Tests, Vietnamese strings, deploy ×4, report.

### Binding non-goals

- No HTTP intake (ADMS receiver, tokens, pairing codes) — CLOCK-2.
- No alerts / emails / Integrations card — CLOCK-3.
- No Windows Bridge, no shift auto-detection, no late-minutes into payslips.
- No change to the payroll path, `om_hr_payroll`, or `hr` (vendored).
- No new rail item; no native settings page; no native list/form on a menu.
- Do not touch `pb_close._local_day` (correct already) beyond calling it or
  leaving it.

## 2. Step 1 — the local-day fix

**Helper (new, in `pb_hr_workforce/models/hr_attendance.py`; create the file
and register it — `pb_hr_workforce` has no `hr.attendance` inherit today,
check `models/__init__.py`):**

```python
class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    def _pb_local_day(self, _cache=None):
        """The employee-local calendar day of check_in (tz: employee.tz →
        company calendar tz → UTC). One pytz lookup per employee per call."""

    @api.model
    def _pb_local_tz(self, employee, _cache=None): ...

    @api.model
    def _pb_week_window_utc(self, employees, week_start, week_end):
        """[start_utc, end_utc] wide enough to contain every punch whose LOCAL
        day is in [week_start, week_end] for any of these employees: take the
        min/max tz offset across the employees and widen by one day each side.
        Callers then bucket by `_pb_local_day()` and drop days outside."""
```

Semantics must equal `pb.wf.lock._local_day` (`pb_close/models/wf_lock.py:232-254`).

**Callers to convert (all of them, nothing else):**

| File:lines | Change |
|---|---|
| `pb_hr_workforce/models/attendance_weekentry.py:196-211` | search with `_pb_week_window_utc`, key cells by `a._pb_local_day(cache).isoformat()`, skip days outside the week |
| `attendance_weekentry.py:468-477` | same keying for `att_map` (the `_save_reg` stale token and `multi` checks then see the local day's rows) |
| `pb_timesheet_approval/models/timesheet_packet.py:213-229` `_week_bounds` | return the widened UTC window; rewrite the docstring: the grid and the packet now both key by the employee-local day, like the lock |
| `timesheet_packet.py:253-267` | bucket `by_day` by local day; drop punches whose local day is outside the week |
| `pb_timesheet_approval/models/week_freeze.py:111-133` | `_pb_week_pairs`, `create`, `write` key by local day (for `create` vals use `_pb_local_tz(employee)` on the parsed `check_in`) |

Also grep for any other `check_in.date()` in `pb_time_hub`, `pb_close`,
`pb_attendance_flow`, `pb_workforce_payroll_bridge` and convert if it means
"the day" (the earlier sweep found none outside the five sites above and
`shift_planning_grid.py:153-154`, which is leave dates — leave that).

**Migration note:** no data changes. Existing grid rows were created on the
local day already (`attendance_weekentry.py:559-560`). A week approved under
the old keying keeps its frozen snapshot; `_refresh_snapshot` is refused once
pending/approved (`timesheet_packet.py:231-237`) so history does not move.
Say so in the module descriptions (`pb_hr_workforce`, `pb_timesheet_approval`
version bumps) and in the report.

## 3. Step 2 — `pb_clock` module

`depends`: `pb_hr_workforce`, `pb_attendance_flow`, `pb_time_hub`,
`pb_import_kit`, `pb_wf_kit`, `pb_sidebar`. **Not** `pb_close`, **not**
`pb_timesheet_approval` (soft-hook them via `'pb.wf.lock' in self.env`,
`'pb.timesheet.packet' in self.env`, `'pb.timesheet.freeze' in self.env`).

Manifest summary (user-visible, white-label): "Time clocks: punches from
attendance machines become attendance days". Version `19.0.1.0.0`.

### Models

**`pb.clock.device`** — `name` (Char, required, e.g. "Factory 2"), `serial`
(Char, indexed, unique per company where set; blank for the `upload` pseudo
device), `location` (Char), `company_id`, `kind` (Selection: `upload`,
`terminal`), `allowed` (Bool, default True — CLOCK-2 uses it as the
allow-list), `tz` (Selection of pytz names, default company calendar tz),
`last_punch_at`, `last_seen_at`, `punches_today` (computed, non-stored),
`active`. One `upload` device per company is created lazily by the upload
path (`_get_upload_device(company)`).

**`pb.clock.punch`** — the ledger. `company_id`, `device_id` (required),
`source` (Selection D7), `user_code` (Char, indexed, stripped), `punch_local`
(Datetime, naive, as read), `punch_utc` (Datetime, stored, computed at create
from `device.tz`), `direction_raw` (Char), `direction` (Selection
in/out/unknown), `verify_mode` (Char), `work_code` (Char), `received_at`
(Datetime, default now), `dedup_key` (Char, required, `_sql_constraints`
unique), `employee_id` (m2o, index), `state` (Selection: `new`, `unmatched`,
`matched`, `paired`, `middle`, `held`, `ignored_duplicate_tap`,
`ignored_outlier`), `attendance_id` (m2o `hr.attendance`, ondelete set null),
`note` (Char, plain English, e.g. "Day locked 2026-11-03"), `work_day`
(Date, the anchor's local date once assigned).

`create()` is `model_create_multi`; it computes `dedup_key` and `punch_utc`,
and swallows the unique violation per row (savepoint) returning the existing
row — the intake paths rely on "same punch twice = one row". `write()` on
anything but the matching/pairing fields raises for non-system users (ledger
rule 7). `unlink()` system-admin only.

**`hr.employee.pb_clock_code`** — Char, indexed, help text in plain English
("The number this person has on the attendance machine. Leave blank when it
is the same as the employee code."). Unique per company where set
(constraint with a plain-English message). Show it on the employee form in
the HR Settings tab next to the badge id (xpath on `field[@name='barcode']`
or the `hr_settings` page — never on `string=`).

**`res.company`** — `pb_clock_max_span_h` (Float, default 21.0),
`pb_clock_double_tap_min` (Integer, default 2), `pb_clock_trust_direction`
(Bool, default False).

**`hr.attendance`** — `pb_entry_source` `selection_add=[('device', 'Time
clock')]`, `ondelete={'device': 'set null'}`; override `_is_device_row` to
`return not self.pb_entry_source or self.pb_entry_source == 'device'`.

### Security

- `ir.model.access.csv`: punch — read for `hr_attendance.group_hr_attendance_officer`,
  write/create for `hr_attendance.group_hr_attendance_manager` (the engine
  writes sudo); device — read officer, write manager; no unlink for anyone but
  `base.group_system`.
- Record rules: company-scoped on both models (`company_id in company_ids`).
- `pb_clock_code` is written only by officers (the assign RPC checks).

## 4. Step 3 — the pairing engine

`pb.clock.pairing` (AbstractModel) with:

- `@api.model run(company_ids=None, employee_ids=None, limit=5000)` —
  the cron body. Steps:
  1. **Match**: for `state='new'` punches, resolve `employee_id` by D5 using
     one batched index per company; unresolved → `unmatched`.
  2. **Outliers** (D6) and **double taps** (D2) in one pass per employee
     (sorted by `punch_utc`).
  3. **Anchor + span** (D1): assign `work_day` per punch; the anchor's local
     date, in the device tz (Sudima: all devices Asia/Ho_Chi_Minh; a device
     without tz falls back to the employee tz).
  4. **Reconcile** each touched `(employee, work_day)` (D4):
     - desired `check_in` = first kept punch (UTC), `check_out` = last kept
       punch if ≥ 2 kept punches else False;
     - skip if the day is locked (`pb.wf.lock` present and
       `_is_locked(company, day)` style check — read its API, it exists for the
       guard), frozen (`pb.timesheet.freeze.check_open` would raise — call it
       inside a savepoint and treat the raise as "skip"), or has an
       `hr.attendance.correction` that is not refused/cancelled on that
       employee-day → punches `held`, note says why in plain English;
     - find existing `device` rows for that employee whose local day is
       `work_day`: 0 → create; 1 → write if different; ≥ 2 → keep the first,
       unlink the rest (they are ours) — all in a per-day savepoint; any
       `ValidationError` (overlap with a manual row, young-worker cap) →
       `held` + the error's plain message as the note;
     - mark punches `paired` (first/last) / `middle`; set `attendance_id`.
  5. Update `device.last_punch_at`; return a summary dict
     `{matched, unmatched, paired_days, held, ignored}` for the lens toast.
- `@api.model repair_employee(employee_id, date_from, date_to)` — resets
  `work_day`/`state` for that span (except ignored kinds) to `matched` and
  reruns; used by the assign RPC (back-log) and the lens's "Re-pair this week".
- Cron `ir.cron` "Time clocks: pair punches" every 5 minutes,
  `numbercall=-1`, active; the upload path calls `cron.sudo()._trigger()`.
  **Template database rule**: `payobook_template` keeps crons off; append this
  cron's xmlid to `pb_tenants.template_active_crons` (see
  `docs/deploy/PENDING.md` paragraph on ids 59–76) so new tenants get it.

Timing facts for tests: a Vietnam punch at 06:30 local is 23:30 UTC the day
before; `punch_local` is naive local, `punch_utc` naive UTC.

## 5. Step 4 — upload mode

Extend `pb.attendance.import.wizard` (do not fork it) with `mode`
(`'days'` = today's behaviour, `'punches'` = new). In `punches` mode:

- `_read_rows` as today, plus two sniffers before the generic path:
  - **ZK `attlog.dat`**: no header, tab-separated, ≥ 2 columns, column 2
    parses as `YYYY-MM-DD HH:MM:SS` → columns `user_code, punch_local,
    status, verify, workcode`.
  - **Mitaco daily sheet**: header contains `Mã NV` (or the legacy-encoded
    `Maõ NV`) and `Lần 1` / `Laàn 1` → each row yields up to two punches
    (`Lần 1` in, `Lần 2` out) on `Ngày` (`dd/mm/yyyy`), `source='mitaco_export'`,
    `direction` set. Rows with an empty `Lần 1` and a filled `Lần 2` yield one
    `out` punch. Normalise the mojibake header spellings in one small map.
- Auto-mapping targets: `user_code` (aliases: code, id, mã nv, badge, user id,
  pin, employee), `punch_at` (datetime) **or** `punch_date` + `punch_time`,
  `direction` (optional), `device` (optional, serial or name).
- Preview (`parse`) answers for the stepper: punches found, people found,
  days covered, **unknown numbers (count + first five)**, duplicate rows
  within the file, already-in-ledger count (dedup preview). Nothing written.
- `commit` writes ledger rows (device = the company's `upload` device, or a
  named terminal when the file carries one), triggers the cron, and returns
  `{created, duplicates, unknown_codes, triggered: true}` plus the plain
  sentence "612 punches added · 3 numbers not matched · pairing runs in the
  background" for the toast.
- The Import lens (`pb_attendance_flow` cockpit, `initialView='import'`) gets
  a **mode switch** at the top of the stepper: two cards "Attendance days"
  (today) and "Time-clock punches" (new; sub-line "Raw taps from a machine or
  its program — we pair them for you"). Hero moment: the preview card shows a
  7-day mini sparkline of punches per day and the unknown-number chips with an
  "Assign now" door that opens the Time clocks lens on those codes.
- Keep the 2000-row cap surfaced; a Mitaco sheet with 800 people × 30 days
  exceeds it — raise the cap to **20 000 rows for `punches` mode only** (one
  ledger insert per row is cheap) and keep the truncation banner.

## 6. Step 5 — the Time clocks lens

### Lens registry (small edit in `pb_time_hub`)

In `time_hub.js` replace the `LENSES` constant and `get lenses()` with a
read of `registry.category("pb_time_hub.lenses")` merged after the four
built-ins (each entry `{key, label, icon, Component, props?, sequence}`);
in `time_hub.xml` render registered lenses with `t-component` in the
`t-elif` chain's final branch. `lens_counts` stays server-side:
`pb.time.hub.get_hub_summary` gains a hook `_extra_lens_counts(ctx)` that
other modules extend via `_inherit` (pb_clock returns `{'clocks': n_unknown}`).
Bump `pb_time_hub` to `19.0.1.4.0`. No behaviour change for the four
existing lenses (tests `pb_time_hub/tests/test_time_hub.py` must stay green).

### The lens (`pb_clock/static/src/js/clock_lens.js` + xml + scss, tokens `pbck-*`)

Facade `pb.clock.lens` (AbstractModel, officer-gated, company-scoped,
`_safe` per block) with `get_lens(week_start, department_id, person_id,
codes=None)` and write RPCs that each check the right and answer
`{'error': 'plain sentence'}` on refusal:

- `assign_code(code, employee_id)` → sets `pb_clock_code`, re-pairs the
  back-log for that code, returns the new counts.
- `auto_match()` → for unknown codes that equal exactly one active
  employee's code/barcode/identification in the company, assign in bulk;
  returns `{assigned, ambiguous:[...]}`.
- `repair_week(week_start, employee_ids=None)` → `repair_employee` per person.
- `save_settings(max_span_h, double_tap_min, trust_direction)` — manager only.
- `set_device(device_id, {name, location, tz, allowed})` — manager only.

Layout (top to bottom), every state designed:

1. **Hero sentence** (D8) with a pulse dot that is grey when nothing arrived
   in 2 h on a working day, indigo otherwise. Empty state (no device, no
   punches): one card with the upload door and a one-line "What happens next".
2. **Machines** row: a card per device — name, location, last punch
   ("3 min ago" / "yesterday 16:31"), punches today, a quiet tz chip, an
   "Allowed" toggle for managers; the `upload` pseudo device reads "Files you
   upload". Click → filters the punch list below.
3. **Unknown numbers** table (badge source): code · first seen · last seen ·
   punches · suggested person (exact code match, else none) · Assign
   (typeahead over active then archived employees) · bulk "Assign all
   suggested". Keyboard: ↑↓ to move, Enter opens the typeahead, Esc closes.
   Grey at zero with the sentence "Every number matches a person."
4. **Held punches** table: person · day · why (the note) · door to the
   corrections flow (`PbAttendanceFlow` exceptions lens with `pb_focus`).
5. **Recent punches** list (virtualised, 200 at a time, filter chips: today /
   this week / person / device / state): time (local) · person or code ·
   device · state chip (In / Out / Break tap / Double tap / Unknown / Held /
   Ignored) — plain words, never the state key.
6. **Settings card** (managers): the three company settings with one-line
   explanations ("Taps closer than this count once"). Save = toast + re-pair
   offer.

Motion: new punches slide in at the top of the list when the lens is open
(poll every 30 s via the facade; no bus). Icons via `ic()` (`radio`,
`fingerprint`, `user-x`, `pause-circle`, `list`, `settings`).

## 7. Tests (`pb_clock/tests/`, plus one file in `pb_timesheet_approval/tests/` for the day fix)

Fixtures: company tz `Asia/Ho_Chi_Minh`, employees `885` (barcode 885) and
`227` (pb_clock_code 227), a terminal device "Factory 1" (serial `TEST-0001`,
tz Asia/Ho_Chi_Minh), settings at defaults. Use `freeze_time` or pass
`now` into the engine for the outlier and "ago" cases.

1. **Dedup**: the same 10 punches created twice → 10 ledger rows.
2. **Local day**: punch 2026-11-04 06:30 local (23:30 UTC 11-03) → attendance
   whose `_pb_local_day()` is 11-04; the Week Grid payload for the week of
   11-03 shows it in Tuesday's cell, the packet `_scan_week` puts it on
   `2026-11-04`, `_pb_week_pairs` returns `(emp, date(2026,11,4))`.
3. **Night shift (Sudima 227)**: 26/10 19:18 and 27/10 07:36 → one
   attendance, `work_day` 2026-10-26, 12 h 18 min; 27/10 19:15 opens a new
   day dated 27/10.
4. **Long day shift**: 07:30 and 04:00 next day → one day, 20 h 30 min.
5. **Double tap**: 07:11:02, 07:11:40, 07:12:30 → one `paired` in, two
   `ignored_duplicate_tap`.
6. **Middle punches**: 07:11, 11:31, 12:29, 20:36 → in 07:11, out 20:36, two
   `middle`; hours = 13.42.
7. **Single punch**: 07:11 only → open attendance (check_out False); the
   exception feed lists `missing_checkout` for that employee-day.
8. **Unknown code**: code `999` → `unmatched`, lens badge 1; `assign_code('999',
   emp)` → the back-log pairs, badge 0.
9. **Held — locked day**: with `pb_close` installed in the test DB, lock the
   day, then a punch arrives → no attendance change, punch `held`, note names
   the day. (Skip with a clear message if `pb.wf.lock` is absent.)
10. **Held — manual overlap**: a grid row 08:00–17:00 exists; device punches
    07:11/20:36 → `held`, note "manual entry exists", grid row untouched.
11. **Outlier**: punch dated 2000-01-01 → `ignored_outlier`.
12. **Idempotent**: run twice → identical attendance ids/times, zero writes
    on the second run (count `write` calls or compare `write_date`).
13. **Mitaco sheet**: a 3-row sheet with the mojibake headers → 5 punches
    (one row has an empty `Lần 2`), `source='mitaco_export'`, pairs into 3 days.
14. **ZK attlog.dat**: 4 tab-separated lines → 4 punches, device resolved by
    name/serial when given.
15. **Upload cap**: 20 001 punch rows → 20 000 kept, `truncated: true`.
16. **Security**: an officer cannot `write` a ledger row's `user_code`; a
    plain user cannot read the ledger; `assign_code` by a non-officer →
    `{'error': ...}`.
17. **No "Odoo"** in any string of `pb_clock` (grep gate over py/js/xml/po).
18. **Time hub lenses unchanged**: existing `pb_time_hub` tests green; the
    registry adds `clocks` after `import`.

Run with the SCHEMECTX §0.13 recipe on `p0clone`
(`-u pb_hr_workforce,pb_timesheet_approval,pb_time_hub,pb_clock --test-tags
/pb_clock,/pb_timesheet_approval,/pb_time_hub`); `-i pb_clock` first time.

## 8. Browser validation (Chrome MCP, mandatory)

On `rize.payobook.com` after deploy, as the open officer session (say so if
none): Mission Control › Time › Time clocks: empty state; upload a 20-row
punch CSV with two unknown codes (codes `TST-A`, `TST-B` — remove the rows
after via the admin unlink); watch the toast, the badge, the hero sentence;
assign one code, auto-match the other (it will say ambiguous/none — check
the sentence); open Week Grid for that week and confirm the day cells and
that device cells are read-only; open a person drawer; change a setting;
read the console (zero errors). Screenshots into
`docs/handovers/clock/shots/`. Then the same upload on `payobook.com` demo
world with the `qa.test@payobook.com` session if open — otherwise rize only
and say so.

## 9. Deploy

Normal tier, four databases: `/odoo/ops/filter_deploy.sh full`, modules
`pb_hr_workforce pb_timesheet_approval pb_time_hub pb_attendance_flow
pb_clock` (`-i pb_clock` where not installed, `-u` the rest), staged from
committed HEAD, staging dir cleaned, `systemd-run` detached, polled. Before:
read `/opt/deploy-notes.md`, `ListAgents` → `SendMessage` the heads-up,
check `sudo fuser /tmp/payobook-studio-deploy.lock`. After: asset purge +
`web.assets.version` bump per DB, cron count per DB before/after (the new
cron must be ON for payobook, p0clone, rize and OFF on payobook_template with
its xmlid appended to `pb_tenants.template_active_crons`), hashes identical,
`latest_version` matches the manifests on all four, PO parse gate, SCSS gate.
Write START/DONE in `/opt/deploy-notes.md`.

## 10. Report back (`docs/handovers/clock/CLOCK_P1_REPORT.md`)

1. Commits (hash → what), module versions.
2. Each test 1–18: pass/fail with the assertion evidence.
3. Browser validation: screenshots list, console result, what you clicked.
4. Deploy table (FILLIN_P2_REPORT §3 format) incl. cron ids per DB.
5. Self-review against the design bar (hero, states, plain language, motion,
   keyboard/bulk) with a score and the gaps.
6. Deviations from this handover and why.
7. Gotchas to append to `CLOCK_LEDGER.md` §3 (append them yourself).
8. Learn lessons / tours that mention the Time hub lenses or Import (list
   xmlids; CLOCK-3 updates them).
9. Open questions for CLOCK-2 (anything about the ledger shape the ADMS
   receiver will need).
