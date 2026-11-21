# CLOCK — biometric / ID-card punches into Payobook (engineering design)

Status: DESIGN STAGE, 2026-11-02. Nothing built. Client facts unknown — the
client questionnaire (owner-facing Claude Doc) closes them. Owner report is the
plain-English companion; this file is for engineers and future handovers.

White-label rule binds every phase: no "Odoo" in any user-visible string
(UI, installer, tray app, emails, exports, .po msgstr). Technical identifiers
stay as they are.

---

## 1. Problem

A client's staff punch in/out on a terminal (ID card / fingerprint / face).
The terminal's vendor software on a basic Windows PC on the client LAN pulls
the punches into a local database. There is no API, no inbound network path
from the internet, and nobody technical on site. We need those punches in
Payobook (`hr.attendance`) reliably enough to pay people from.

## 2. How the industry does it (summary — sources in §11)

| # | Pattern | Who uses it | Needs on site | Reliability | Client effort |
|---|---------|-------------|---------------|-------------|---------------|
| P1 | **Connector agent on the PC reads the attendance software's DB** and pushes over HTTPS | Zoho People (Tomcat + ZAttendance.war, JDBC to MSSQL/Access/MySQL), greytHR / Keka / HROne-style "sync utilities" | PC on, agent installed | High (DB is the system of record the client already trusts) | Low after install |
| P2 | **Agent on the PC talks to the terminal directly** over LAN (ZK 4370 / Hikvision ISAPI / BioTime API) | Odoo-app ZK modules (pyzk), many Indian HRMS | PC on, terminal reachable | Medium (one connection at a time, collides with vendor software; firmware variance) | Low |
| P3 | **Terminal pushes straight to the cloud** (ZKTeco ADMS / "Cloud Server" iclock HTTP) | Keka, greytHR, ZKBio cloud, factoHR | Terminal with internet + ADMS firmware | High when it works; no PC needed | Medium (menu change on device, often plain HTTP) |
| P4 | **Vendor REST API** (BioTime, BioStar 2, COSEC, CrossChex Cloud) | Most HRMS for premium terminals | That vendor product | High | Low |
| P5 | **File upload** (Excel / CSV / USB `attlog.dat` export) | Everyone, as fallback | Nothing | Depends on a human | High, every period |

Market detail (research 2026-11-02): Keka offers SQL / SDK / Push / API
(sync tool: Win10, 4 GB RAM, always-on PC, MS-SQL table with device no +
attendance no); uKnowva's Windows sync app has the best public spec
(forward-only cursor on DeviceLogId/DownloadDate, connection test, tray +
auto-start); Zimyo reads `eTimeTrackLite.mdb` directly; Mekari Talenta ships
"Mekari Agent" (Windows, reads the fingerprint DB) + per-machine file import;
MISA AMIS (VN) pairs its desktop tool with a **connection code** created in
the web app; greytHR has a per-location **Health Status card** and **remote
re-sync by date range**; Frappe's sync tool keeps success/failed logs per
device and a per-device IN/OUT rule; Gadjian/ATGO/ECOSIRE use device push
(ADMS) with an unknown-employee review queue; US vendors (BambooHR, Workday,
UKG, ADP) avoid the problem by selling or certifying their own cloud clocks.
Odoo-store ZK modules pull the device from the server over the internet
(port-forwarding, exposed 4370) — the weakest option for a SaaS; do not copy.

Decision: **build one cloud intake + pairing engine, fed by (a) file upload
from day one, (b) terminal push (P3/ADMS) when the client's terminal has a
"Cloud server / ADMS" menu and internet — no install at all, the most
reliable route — and (c) our Windows "Clock Bridge" (P1, with P2/P4 recipes
inside it) when it doesn't, or when the client wants to keep the vendor
software as the master.** All routes land in the same append-only punch
ledger, so payroll never cares which route a punch took. Which of (b) or (c)
is built first is decided by the client questionnaire.

Zoho's weak points we fix in (c): Tomcat+Java (200 MB+, fragile on reboot —
their own guide says a crash "may corrupt the configuration page"),
hand-written SQL, OAuth token copy-paste, manual time-zone matching, no
health view.

ADMS caveats for (b): many firmwares speak plain HTTP only; some accept an IP
address but not a host name (so `<tenant>.payobook.com` routing fails) →
needs one shared receiver (e.g. `clock.payobook.com`, fixed IP) that routes by
**terminal serial number** to the tenant DB via a serial→tenant registry, and
only accepts registered serials. Punches carry only code + time, but plain
HTTP allows tampering → serial allow-list, anomaly alerts, and prefer HTTPS
where the firmware supports it. The terminal can keep serving the vendor
software over the LAN at the same time (its software pulls on 4370; ADMS
pushes out) — verify on the client's model.

## 3. Architecture

```
 Terminal(s) ──LAN──▶ vendor software on Windows PC ──▶ local DB (Access .mdb / SQL Server / MySQL / Postgres)
                                                              │ read-only
                                                   ┌──────────▼──────────┐
                                                   │  Payobook Clock      │  Windows service, outbound HTTPS only
                                                   │  Bridge (agent)      │  local queue, cursor, heartbeat
                                                   └──────────┬──────────┘
                                                              │ HTTPS POST (bridge token)
            ┌─────────────────────────────────────────────────▼──────────────────────────┐
            │ <tenant>.payobook.com  /pb_clock/v1/*                                         │
            │  punch ledger (pb.clock.punch, append-only, dedup key)                        │
            │      │ match device user code → employee                                      │
            │      ▼                                                                        │
            │  pairing engine → hr.attendance (pb_entry_source='device')                    │
            │      ▼                                                                        │
            │  existing: exceptions (pb_attendance_flow) → weekly packet (pb_timesheet_     │
            │  approval) → payslip REGHRS/TOTHRS/WORKDAYS/OT                                │
            └──────────────────────────────────────────────────────────────────────────────┘
   Also into the same ledger: file upload (P5), ADMS receiver (P3, later).
```

### 3.1 Cloud module `pb_clock` (new)

Depends: `pb_hr_workforce`, `pb_attendance_flow`, `pb_timesheet_approval`,
`pb_integrations` (cockpit card), `pb_close` (lock respect).

Models:

- **`pb.clock.bridge`** — one installed agent. `name`, `company_id`,
  `site_tz` (IANA, required — e.g. `Asia/Ho_Chi_Minh`), `token_hash`
  (sha256; never store plaintext — note `hr.integration.connector.api_key`
  is plaintext Char, do NOT copy that), `pairing_code` + expiry (short code
  shown once on screen, exchanged for a long token by the installer),
  `recipe` (selection: etimetracklite_sql, etimetracklite_access,
  att2000_access, att2000_sql, biotime_api, wiseeye_sql, crosschex,
  generic_sql, zk_device, hik_isapi, adms_local), `recipe_config` (JSON,
  editable by support remotely), `last_heartbeat`, `agent_version`,
  `pc_clock_offset_s`, `last_punch_at`, `last_error`, `state`
  (draft/paired/online/silent/revoked).
- **`pb.clock.device`** — a terminal seen by a bridge: `serial` / machine
  number, `name`, `location`, `last_punch_at`, `clock_drift_s` (when the
  source exposes device time), `active`.
- **`pb.clock.punch`** — the ledger. Append-only (no write except the
  matching/pairing fields; unlink only by system admin). Fields:
  `bridge_id`, `device_id`, `user_code` (as on device), `punch_local`
  (naive, as read), `punch_utc` (computed with `site_tz` at ingest; stored),
  `direction_raw` (char), `direction` (in/out/unknown), `verify_mode`,
  `work_code`, `source_row_id`, `source_download_at`, `received_at`,
  `dedup_key` (unique: sha1 of company + device serial-or-bridge + user_code
  + punch_local to the second), `employee_id` (resolved), `state`
  (new/unmatched/matched/paired/ignored_duplicate_tap/ignored_outlier),
  `attendance_id`, `note`.
- **Employee mapping** — add `hr.employee.pb_clock_code` (Char, indexed,
  unique per company where set). Default match order on first sight of a
  code: `pb_clock_code` → `barcode` ("Badge ID") → `identification_id`
  → none (unmatched). Mapping screen: list of unmatched codes with punch
  count and first/last seen, inline "assign to employee", bulk import (code,
  employee code), "auto-match by employee code" suggestion. When a code is
  assigned, re-run matching + pairing for its back-log.
- `pb_entry_source` selection_add `('device', 'Time clock')`,
  ondelete `set null` (same pattern as
  `pb_attendance_flow/models/hr_attendance.py:33-35`).
  **Gotcha:** today a *blank* source means "device"
  (`pb_attendance_flow/models/hr_attendance.py:37-40`,
  `application_payroll_source.py:364`). Make `_is_device_row` return true
  for blank **or** `'device'`, and update the mixed-source check in
  application payroll the same way.

### 3.2 Intake API

Base: `https://<tenant>.payobook.com/pb_clock/v1/` (dbfilter `^%d$`, the
host picks the DB — no db param; see `docs/SAAS_RUNBOOK.md:11-13`; custom
domains via `biz_host_db`).

| Route | Purpose |
|---|---|
| `POST pair` | body `{pairing_code, machine_name, agent_version}` → `{bridge_token, bridge_id, site_tz, recipe, recipe_config}`; code single-use, 30-min expiry, 5 attempts then lock |
| `GET config` | bridge pulls recipe/config/interval every N min (support can fix remotely) |
| `POST punches` | batch ≤ 1000 rows; response `{accepted, duplicates, rejected:[{i, reason}], ack_cursor}`; idempotent by `dedup_key` |
| `POST heartbeat` | `{pc_time, queue_depth, last_read_ok_at, last_error, sources:[...]}` every 5 min even with no punches |

- `auth='none'`/`csrf=False` + `Authorization: Bearer <token>`; constant-time
  compare against `token_hash` (precedent `pb_zoho_bridge/controllers/
  zoho_webhook.py:50-87` uses `hmac.compare_digest`; same uniform
  "unauthorized" on every failure).
- **Paused tenants:** the tenancy door (`pb_tenancy/models/ir_http.py:183-228`)
  only fires with a uid. The route must call the tenancy access check itself
  and refuse (HTTP 403 "account paused") — otherwise a paused tenant keeps
  ingesting.
- Rate: per bridge max 60 requests/min; reject bigger batches with 413.
- Ingest = insert ledger rows with `ON CONFLICT (dedup_key) DO NOTHING`
  semantics (create in savepoints or SQL upsert), then enqueue matching +
  pairing as a queued job per (employee, local day) — never pair inline in
  the HTTP request.

### 3.3 Pairing engine (punch ledger → `hr.attendance`)

Run per employee per **local work day** (employee tz via `_get_tz()`,
`hr/models/hr_employee.py:1517-1522`).

1. Work-day window: anchored on the employee's shift / calendar start minus
   a configurable lead (default 4 h) to plus 20 h, so a 22:00–06:00 night
   shift stays one day. No shift → local calendar day.
2. Drop double taps: same employee within `pb_clock_double_tap_min`
   (default 2 min) → keep first, mark the rest `ignored_duplicate_tap`.
3. Drop outliers: punch in the future (> now + 10 min) or year < 2015 →
   `ignored_outlier` + health alert (device clock reset).
4. Build pairs:
   - Direction trusted (company setting, or recipe says the source has
     reliable in/out): pair in→out in order; an `in` without `out` = open
     attendance + "missing check-out" exception.
   - Direction not trusted (default; `state 255`/blank is common): **first
     punch = in, last punch = out**; middle punches kept in the ledger and
     shown on the day (breaks) but not paid unless the company turns on
     "pay breaks by punches" (then alternate in/out).
   - Single punch in the day → open attendance + "missing punch" exception
     (existing `pb_attendance_flow` reporting picks it up).
5. Write `hr.attendance` rows with `pb_entry_source='device'`, one savepoint
   per row (precedent `pb_attendance_flow/wizards/attendance_import.py:323-372`)
   because `_check_validity` (`hr_attendance/models/hr_attendance.py:206-245`),
   the `pb_close` lock guard (`pb_close/models/hr_attendance.py:93-113`) and the
   young-worker cap can each refuse.
6. **Re-pairing** when a late punch arrives for an already-paired day:
   - day not locked, week packet not approved, no correction on the day →
     replace that day's `device` attendances.
   - otherwise → do not touch; raise an exception "late punch after the
     week was approved / day was closed" for HR to accept via the existing
     correction flow. Device data never silently overrides a human.
7. Never pair on the agent; the agent ships raw rows only.

### 3.4 Payroll — no new payroll path

Device attendances flow into the path that already exists:
`pb.timesheet.packet._scan_week` reads `hr.attendance`
(`pb_timesheet_approval/models/timesheet_packet.py:240-300`) → approved week →
`HrPayslip._get_formula_input_values` fills REGHRS/TOTHRS/WORKDAYS/OT
(`pb_timesheet_approval/models/hr_payslip.py:69-110`), gated by
`res.company.pb_timesheet_payroll`. Application payroll
(`payroll_basis='timesheet'`) cross-checks packets vs live punches
(`application_payroll_source.py:296-390`).

Note: `om_hr_payroll` `get_worked_day_lines` never reads attendance
(`om_hr_payroll/models/hr_payslip.py:496-497` TODO). Do not wire there;
the packet path is the one in use.

**Blocking gotcha — day convention.** The packet and week grid key a punch by
the stored **UTC** date (`timesheet_packet.py:213-229`, docstring explains it),
while `pb.wf.lock` and the exception engine use the **employee-local** day.
For UTC+7 (Vietnam) a 06:30 check-in is 23:30 UTC the *previous* day → the
hours land on the wrong day/week in the grid and packet. Device punches make
this common (every early shift). CLOCK-1 must move the grid + packet to the
employee-local day (one helper, both callers) with a migration note, or
early-shift weeks will be wrong. Treat as in-scope, not a follow-up.

Late arrival / early leave minutes: `pb.attendance.rule.count_late_as` exists
"reserved for future payroll wiring" (`pb_attendance_flow/models/attendance_rule.py:34-84`).
Wiring late minutes into a payslip input is a later phase (CLOCK-5), only if
the client deducts for lateness.

### 3.5 Health and alerts (best-in-class gap vs Zoho)

Card in the Integrations cockpit (`pb_integrations/models/pb_integrations.py`,
`_feed_summary` at `:211-236` is the stale-feed precedent) + a "Time clocks"
screen:

- Bridge: online / silent since HH:MM (no heartbeat > 15 min), agent version,
  queue depth, last error in plain words ("The attendance program's data file
  could not be opened — is the program updating?").
- Per terminal: last punch seen, punches today vs same weekday average,
  clock drift warning (> 3 min).
- Unmatched card numbers (count + one-click mapping).
- Days with missing punches (link to existing exceptions).
- Alert email/notification to the HR admin when a bridge is silent > 2 h in
  working hours, or a terminal has zero punches on a working day by 11:00.
- "Last full re-check" timestamp (see §4.4).

### 3.6 File upload (P5) — ships in CLOCK-1

Extend the existing attendance import (`pb.attendance.import.wizard`,
officer-only, 2000-row cap) with a "Time-clock punches" mode: accepts raw punch
lists (code, date-time, optional direction, optional device) from Excel/CSV
and ZK `*_attlog.dat` (tab-separated; sniff columns — order varies by
firmware). Rows go into the **ledger** (not straight to `hr.attendance`), so
they get dedup + pairing like any other path. This gives the client value
before the Bridge exists and is the permanent fallback when the PC is dead.

## 4. The Windows Bridge (agent)

### 4.1 Technology

**.NET Framework 4.8, x86, Windows Service + small settings window, signed
MSI (WiX).** Reasons: runs on Windows 7 SP1 → 11; built-in `System.Data.OleDb`
with the Jet 4.0 provider reads `.mdb` with **no driver install** when the
process is 32-bit (64-bit needs ACE and collides with installed Office
bitness); built-in SqlClient; ~2–3 MB installer, ~40 MB RAM. Rejected: .NET 8
(no Win7), Go (no clean Access driver), Python (AV false positives, ODBC
driver needed), Java/Tomcat (Zoho's choice: 200 MB+, fragile). `.accdb` sources
need ACE x86 — installer offers it only if such a file is detected.

Win7 note: TLS 1.2 needs KB3140245 + SystemDefaultTlsVersions registry;
installer checks and tells the user in plain words.

This is a new code base outside the addons tree: `tools/clock_bridge/`
(own build, own version). It is not an addon — never rsync it to the server.

### 4.2 What it does

- Install wizard: (1) enter the 8-character pairing code shown on the
  Payobook "Time clocks" screen; (2) auto-detect: scan Program Files /
  Program Files (x86) for known folders (ZKTeco\att2000, eTimeTrackLite,
  Wise Eye, CrossChex, BioTime), look for `att2000.mdb`, `eTimeTrackLite1.mdb`,
  local SQL Server instances and DB names (`etimetracklite1`, `Att2000`,
  BioTime Postgres on 7496) and propose a recipe; (3) test read: "We found
  12,431 punches, the latest at 08:02 today for card 1043" — the user sees
  real data before going live; (4) first sync with a chosen start date.
- Loop every 2 min (configurable from the cloud): read new rows by recipe →
  local queue (SQLite file) → POST in batches → mark sent on 2xx ack.
  Survives offline days; retries with backoff.
- Heartbeat every 5 min regardless.
- Read-only by construction: separate read-only SQL login recommended; Access
  opened `Mode=Read` + share-deny-none; fallback copy-to-temp if locked. **It
  never writes to the vendor DB and never sends a "clear logs" command to a
  terminal.**
- Self-update: checks version on `GET config`, downloads signed MSI from our
  domain, side-by-side swap.
- Runs as LocalSystem; proxy auto-detect + manual override; outbound 443 only.
- Logs locally (rolling, 10 MB) + last error reported to the cloud.

### 4.3 Recipes (read logic per source)

| Recipe | Where | Read | Cursor |
|---|---|---|---|
| eTimeTrackLite (SQL Server or Access) | DB `etimetracklite1`; `DeviceLogs` **and/or** monthly `DeviceLogs_{M}_{YYYY}` (no leading zero; table appears with first log of month) | UNION current + previous month table (+ `DeviceLogs`); `UserId`, `LogDate`, `Direction`/`AttDirection`, `DeviceId`, `DownloadDate`, `DeviceLogId` | `DeviceLogId` (unique across tables) + rescan `DownloadDate` ≥ cursor − 30 min |
| ZKTime / Att2000 (Access or SQL) | `att2000.mdb` (often `C:\Program Files (x86)\ZKTeco\ATT2000\`) or DB `Att2000` | `CHECKINOUT` **JOIN `USERINFO` ON USERID** → send `BADGENUMBER` (USERID is internal autonumber — classic trap), `CHECKTIME`, `CHECKTYPE` (I/O/…, 255→NULL), `SENSORID`, `WorkCode` | no reliable row id → `CHECKTIME` with a 7-day overlap rescan; cloud dedup absorbs repeats |
| BioTime / ZKBio Time | LAN web server | REST `api-token-auth` → `GET /iclock/api/transactions/?start_time&end_time` (`emp_code`, `punch_time`, `punch_state`, `terminal_sn`) | `upload_time`/page + overlap |
| Wise Eye (VN) | SQL Server / Access | `CheckInOut` (`UserEnrollNumber`, `TimeStr`, …) **schema unverified — dump a real install first** | time + overlap |
| CrossChex (Anviz) | Access / SQL | `Checkinout` (unverified) | time + overlap |
| Generic SQL | any ODBC/OLEDB/SqlClient | support-written query returning `user_code, punch_time, direction?, device?, row_id?, download_at?` with `@from/@to` | row_id if given else time + overlap |
| ZK terminal direct (4370) | terminal IP | read attendance log only (pyzk-equivalent in C#); comm key | time + overlap; **only when no vendor software is downloading** (one connection at a time) |
| Hikvision ISAPI | terminal IP | `POST /ISAPI/AccessControl/AcsEvent` paged, Digest auth | `serialNo`/time + overlap |
| ADMS local receiver | agent listens on LAN HTTP | terminal "cloud server" pointed at the PC; reply `OK: n`; idempotent | device stamp |

All sources store **local naive time** (BioStar 2 is UTC) — the agent sends
`punch_local` plus the bridge's `site_tz`; the cloud converts. Never trust the
PC's own time zone setting for conversion.

### 4.4 No data loss rules

1. Cloud dedup key makes every resend safe, so the agent can rescan overlap
   windows freely.
2. Overlap rescans: 30 min (row-id recipes) / 7 days (time-only recipes).
3. Nightly full re-check of the last 35 days: agent sends per-day
   (code-count) digests; cloud compares and asks for any day that differs.
   Covers "device downloaded a week late" and agent reinstalls.
4. Before a pay run closes, the Pay Run screen shows "Time clock data
   complete up to <time>" from the bridge's last good read; a silent bridge
   blocks nothing but shows a warning.

## 5. Security & privacy

- Only **card/enrol number + time + terminal** leave the client. No
  fingerprint/face templates, photos or names are read. Say so in the client
  material (biometric data is "sensitive personal data" under Vietnam
  Decree 13/2023 and India's DPDP Act 2023 — we stay out of scope by not
  collecting it).
- Outbound HTTPS only; no port forwarding, no inbound firewall change.
- Token per bridge, hashed at rest, revocable on screen; pairing code
  single-use.
- Agent signed (code-signing cert needed — budget item).

## 6. Phases (proposal — owner opts in to the phased workflow first)

| Phase | Scope | Value on its own |
|---|---|---|
| CLOCK-1 | `pb_clock` cloud: ledger, employee clock code + mapping screen, pairing engine → `hr.attendance`, `'device'` source, **local-day fix for grid/packet**, file upload of raw punches (Excel/CSV/attlog.dat) | Client can upload exports and get paid hours immediately |
| CLOCK-2 | **DECIDED 2026-11-05: the shared ADMS receiver** (serial→tenant registry, `OK: n` acks, serial allow-list, time-sync in the handshake, HTTPS first with a per-tenant plain-HTTP fallback host if the owner allows it — §12.4). Plus a one-off **Mitaco `.mdb` import** (Access, via the file-upload path with an `mdb-export`/`pyodbc`-free reader: `access-parser` or an Excel export from Mitaco) for history from the period start. The Bridge moves to CLOCK-5. | Automatic sync for Sudima, no PC dependency |
| CLOCK-3 | Health screen + cockpit card + alerts + late-punch-after-approval exceptions + nightly re-check | Trustworthy for payroll |
| CLOCK-4 | More recipes: eTimeTrackLite/att2000/BioTime/Wise Eye/CrossChex, ZK direct, Hikvision ISAPI, local ADMS receiver, auto-detect | Sell to the next client without custom work |
| CLOCK-5 (optional) | Whichever of ADMS receiver / Bridge was not built in CLOCK-2; remote re-sync by date range from the web screen; late/early minutes into payslip inputs | Covers every client shape; lateness deductions |

Rough size: CLOCK-1 ~1.5 wk, CLOCK-2 ~2 wk (new C# code base), CLOCK-3 ~1 wk,
CLOCK-4 ~2 wk, CLOCK-5 ~1.5 wk. CLOCK-2's Bridge is a security-adjacent,
installer/service code base — Fable reviews its token handling directly.

## 7. Test cases to carry into handovers (seed list)

1. Same punch file uploaded twice → 0 new ledger rows, 0 new attendances.
2. Vietnam employee, 06:30 local check-in → attendance on the local date in
   grid, packet and payslip.
3. Night shift 22:00–06:05 → one attendance, one work day.
4. Three taps within 60 s → one punch used, two `ignored_duplicate_tap`.
5. Only one punch on a day → open attendance + "missing punch" exception.
6. Unknown card number → `unmatched`; assign it → back-log pairs.
7. Late punch arrives after week approved → no change to attendance,
   exception raised.
8. Punch dated 2000-01-01 → `ignored_outlier` + health alert.
9. Bridge offline 3 days then reconnects → all punches arrive once, in order.
10. att2000 recipe sends `BADGENUMBER`, not `USERID`.
11. eTimeTrackLite month rollover: punches on the 1st land via the new
    `DeviceLogs_{M}_{YYYY}` table.
12. Paused tenant → `POST punches` refused 403.
13. Wrong / revoked token → uniform 401, nothing written.
14. No "Odoo" string anywhere in installer, tray app, screens, emails.

## 8. Open facts — CLOSED 2026-11-05 by the first client (see §12)

The questionnaire came back from Sudima Panels VN on 2026-11-04. Every
item below is answered in §12; the route for CLOCK-2 is decided (ADMS).

Originally open: terminal brand/model/firmware and whether it has a
cloud-server (ADMS) menu; the PC software name/version; its DB engine and
location; whether it clears logs from the terminal after download; whether
the PC runs 24×7; internet and proxy; Windows version/RAM/bitness; admin
rights; card number = employee code?; shifts incl. night shifts; break
punching; IN/OUT keys used; number of sites/terminals/employees; time
zone(s); pay-period cut-off; history start date; IT and vendor contacts.

## 9. Non-goals

- Enrolling fingerprints/cards or managing users on terminals.
- Door/access-control events.
- Replacing the vendor's attendance software.
- Pushing anything back to the terminal (time sync included) in v1.

## 10. Precedents in this repo

- Webhook auth + ingest shape: `pb_zoho_bridge/controllers/zoho_webhook.py:50-87`,
  `pb_hr_payroll_formula/controllers/darwin_webhook.py:38-70`,
  `hr.integration.connector.webhook_ingest` (`integration_connector.py:2077-2104`).
- Per-row savepoint writes + employee lookup by barcode: `pb_attendance_flow/wizards/attendance_import.py:187-205, 323-372`.
- Local-time import conversion: `attendance_import.py:61-72`.
- Stale-feed health: `pb_integrations/models/pb_integrations.py:211-236`.

## 11. Sources

Zoho People biometric guide (repo root `Biometric guide.pdf`, 2026-03).
ZK/eSSL/BioTime/BioStar/Hikvision facts: research notes 2026-11-02 —
zkteco-poller (github paKymoK), HRMS eSSL integration doc (github
sunilsoni101290/HRMS), zk-protocol (github adrobinoga), pyzk, HTTP PUSH SDK
2.0.1, Suprema support articles, ipcamtalk ISAPI threads, Odoo BioTime doc.
Unverified items are marked in §4.3 and must be checked on a real install.

## 12. Client A — Sudima Panels VN (questionnaire returned 2026-11-04)

Source files (NOT in the repo — personal data; kept in `SUDIMA/`, excluded via
`.git/info/exclude`): `Attendance_Machine_Questions_EN_VI (SUDIMA).docx`
(50 answers + 8 embedded screenshots), `Attendance machine (SUDIMA).xlsx`
(14 photos: fronts + device-info screens). Owner summary (plain English):
https://claude.ai/artifact/J1d7CppsQNDLSYDhX4Vrg6

### 12.1 Terminals — all ZKTeco OEM (MAC OUI `00:17:61`), ZK firmware menus

| Site | Model | Serial (last 4; full list in the client file) | Board | Algo | Note |
|---|---|---|---|---|---|
| Factory 1 #1 | 4000TID-C | …0149 | ZMM200_TFT | Finger VX10.0 | MCU 23 |
| Factory 1 #2 | FA110 | …0652 | ZMM510_TFT | Finger VX10.0 / Face VX3.5 | face+finger |
| Factory 2 | 4000TID-C | …0362 | ZMM200_TFT | Finger VX10.0 | |
| Factory 3 | 4000TID-C | …0251 (blurry) | ZMM200_TFT | Finger VX10.0 | re-photograph |
| Factory 4 #1 | FA110 | …0546 | ZMM510_TFT | Finger VX10.0 / Face VX3.5 | |
| Factory 4 #2 | FA110 | …0727 | ZMM510_TFT | Finger VX10.0 / Face VX3.5 | |
| New office | 4000TID-C | …0254 | **ZMM100_TFT** | **Finger VX9.0** | oldest; ADMS menu unconfirmed |

Client wrote "five"; photos show seven. Factory 1 label photos are swapped
relative to their captions; table above is reconciled by the front photos.

The returned **Comm › Cloud Server** screenshot ("Cài đặt máy chủ đám mây":
server type, enable domain name OFF, server address `0.0.0.0`, port `8081`,
proxy OFF, **HTTPS ON**) is the standard ZK PUSH (iclock/ADMS) config page →
P1 route is available at least on the ZMM510/ZMM200 units. Address empty =
nobody receives their pushes today. Device clock photo: 2026-11-04 09:46:33,
24 h, `YYYY-MM-DD`; front photos show FA110s at 08:52 and 4000TID-Cs at 08:54
taken within minutes — clocks agree. Rare power cuts; built-in battery.

### 12.2 PC + software

- **Mitaco 5 v2** (MitaPro). Data: `D:\MAY CHAM CONG\Data\MITADATA.mdb`
  (Access/Jet). Manual **Download once a day**; **does not clear** the
  terminal after download (terminal history intact; ~100k log capacity ≈
  60 days at 800 staff × 2 punches). Supplier **Khang Việt Cường**
  installed it, no longer supports, charges per change.
- PC (hostname in the client file): Windows 11 **Home** 25H2 build
  26200.9711, x64, i5-11400, 16 GB, 88/477 GB used. **On Mon–Sat 07:30–16:30,
  Sun 07:30–13:30 only; shared by all staff; Trend Micro.** "Five computers"
  have the program (unclear whether one DB or five — follow-up asked).
- Mitaco's daily sheet (pasted into the answers) shows `Mã NV | Ngày | Lần 1 |
  Lần 2` = first/last punch per calendar day. Night-shift employee 227
  (CA DEM): 26/10 `19:18 —`, 27/10 `7:36 19:15` → Mitaco splits a night shift
  across two calendar days. Confirms §3.3's work-day window is required.

### 12.3 Workforce + rules (feed §3.3 / §3.4 parameters)

- 600–800 punching employees, growing. **Terminal user id = Payobook employee
  code**, one id on every terminal, never reused. New starters enrolled same
  day by each workshop's HR. Contractors punch too (few) → `unmatched`, never
  paid. Non-punchers (boss's driver, hardware packaging, rental truck) use a
  signed confirmation → unchanged, outside pb_clock.
- Shifts: day 07:30→16:30/18:30/19:30/20:30/22:00/**04:00+1**; night
  16:30→01:30+1, 16:30→04:30+1, 19:30→04:30+1, 19:30→07:30+1. Night shifts
  cross midnight → work-day window must tolerate a 20.5 h span (07:30→04:00).
  Pairing default for Sudima: work-day starts 05:00 local; first punch in,
  last punch out; duplicate-tap window 2 min.
- Lunch 11:30–12:30 or 11:45–12:45 **unpaid**; staff "go out the gate during
  break" (whether they tap is a follow-up). Normal day = 2 punches. Break
  deduction is a rule, not punch-driven.
- No rounding. OT = after shift end. Late → loses attendance bonus (needs
  late-minutes per day → CLOCK-5 scope confirmed useful). Forgotten punch →
  signed confirmation; approver = General Manager.
- Pay period = calendar month; attendance final on the 1st; history from
  period start; **avoid start/end of month** for setup; screen share after
  15:00. Approvals for cloud/software: "will check with Sashi" (IT).
- Time zone: all sites Vietnam (UTC+7) — §3.3 local-day fix is mandatory.

### 12.4 Route decision for CLOCK-2 and the engineering consequences

**ADMS receiver (P1) is the route.** Reasons: all terminals are ZK-firmware
with the Cloud Server page; PC is off nights/Sundays and shared; supplier is
hostile to change; Mitaco keeps polling over TCP 4370 in parallel (PUSH and
SDK pulls coexist on ZK firmware), so there is no cut-over risk.

Consequences for the handovers:

1. **Serial allow-list** seeded with the 7 serials above; unknown `SN` →
   `OK` with no persistence? **No** — refuse (HTTP 403) and log; a silent OK
   would let a stranger's terminal believe it delivered.
2. **Handshake** (`GET /iclock/cdata?SN=…&options=all`) must return
   `ServerTZ`/time so terminals sync their clock from us (§9 non-goal
   "no time sync in v1" is **relaxed** for ADMS: it is free in the protocol
   and removes the clock-drift risk).
3. **HTTPS first, HTTP fallback host** (owner decision pending): ZK TLS
   stacks on 2015–2019 firmware may not negotiate modern chains. Design:
   `clock.<tenant>.payobook.com` (TLS) and `clock-plain.<tenant>…` (port 80)
   both route to the same controller; the plain host is enabled per tenant
   by a flag and carries only `SN`, user id, timestamp, verify type.
4. **Handle both record layouts**: ZMM100/ZMM200 send the legacy
   `ATTLOG` tab-separated `PIN\tTIME\tSTATUS\tVERIFY[\tWORKCODE…]`; ZMM510
   the same, sometimes with extra columns. Parse by position, tolerate
   extras. `OPERLOG`, `USERINFO`, `BIODATA`, face templates → acknowledge and
   drop (never store biometrics).
5. **Backfill**: after first registration send `DATA QUERY ATTLOG
   StartTime=<period start> EndTime=<now>` (firmware-dependent; if ignored,
   fall back to the Mitaco `.mdb` import). Keep `dedup_key =
   sha1(SN|PIN|TIME)` so backfill + live overlap is harmless.
6. **Mitaco `.mdb` reader** for history and for the New-office fallback:
   first inspect the schema live (table names unknown; Zoho-style
   `Attendance(employeeID,eventTime,…)` not guaranteed). Read-only copy of
   the file (`copy` then open the copy; Jet locks are per-process) — if the
   schema is awkward, accept Mitaco's **Excel export** through the CLOCK-1
   upload instead (it already has first/last punch per day; mark rows as
   `source=mitaco_export`, trust lower than raw punches).
7. **Tenant**: Sudima needs its own tenant/hostname before setup day;
   changing it later = re-typing 7 terminals.
8. Health (CLOCK-3) terminal-level: last-seen per SN, punch-time vs
   receive-time skew > 5 min → alert; silent terminal > 6 h on a working
   day → alert.

### 12.5 Follow-ups sent to the client (2026-11-05)

Confirm 7 terminals; Comm-menu photos for every 4000TID-C (esp. New office
ZMM100); clear Factory 3 label; menu admin password owner; "five computers"
= one DB or five; break tapping; second night break; Sashi call.
