# CLOCK-2 — Machines push to Payobook (the ADMS receiver)

Read first: `CLOCK_LEDGER.md` (§0 rules bind verbatim; §1 facts; §2 decisions
D1–D12; §3 gotchas G1–G8 — G2 says the live box alias is `Payobook19v2`),
`CLOCK_P1_REPORT.md` (what exists: ledger, pairing, lens, upload), then
`docs/design/biometric/BIOMETRIC_DESIGN.md` §3.2, §12.1, §12.4.

## 1. Scope

In this order, one commit each:

1. **Receiver** — the ZK PUSH / ADMS ("iclock") HTTP routes, serial-gated,
   company-scoped, writing the CLOCK-1 ledger. Nothing pairs inline.
2. **Machine onboarding** — a machine that calls in with an unknown serial
   appears as **pending** in the Time clocks lens; a manager presses Allow.
   History cut-off, time-zone, stamps.
3. **Time sync + commands** — skew measured from live punches; `SET OPTIONS
   DateTime` sent through the command channel; "Resend punches since…".
4. **Plain connection on port 80** (owner ruling 3, reworded in D12) —
   nginx `location ^~ /iclock/` on the port-80 servers + the company switch.
5. **Pairing rule D11** (a forgotten check-out no longer blocks later days)
   and the three CLOCK-1 cosmetic gaps.
6. **Emulator + tests**, Vietnamese, setup-day runbook, deploy ×4, browser
   validation, report.

### Binding non-goals

- No alerts, emails, Integrations card, nightly re-check — CLOCK-3.
- No Bridge, no `.mdb` reader (the Mitaco daily sheet upload from CLOCK-1 is
  the history path; CLOCK-3 revisits `.mdb` only if the sheet is not enough).
- No user / fingerprint / face management on the machine. `USERINFO`,
  `BIODATA`, `FP`, `FACE`, `USERPIC`, `ATTPHOTO` tables are acknowledged
  (`OK`) and dropped unread (ledger rule 8). Never request them.
- No PUSH 3.x feature work beyond answering its registration so a 3.x
  device does not loop (§3.4).
- No tenant provisioning (sudima.payobook.com is an ops step the coordinator
  runs with `pb_tenants` before setup day).

## 2. Verified facts for this phase (do not re-derive)

- **Routing by host**: `dbfilter = ^%d$`, `list_db = False`
  (`docs/SAAS_RUNBOOK.md:11`); the first hostname label is the database. So
  `sudima.payobook.com/iclock/cdata` lands in DB `sudima` with no db
  parameter. Tenants with their own nginx block (`pb-tenant-cert` writes it)
  take precedence over `sites-available/pb-wildcard`; the apex is
  `sites-available/_` (`SAAS_RUNBOOK.md:14-17`, memory
  `saas-multitenant-platform`). **Read the real files on the box before
  touching nginx**; the odoo user cannot run nginx — use the SSH user's sudo,
  back the files up, `nginx -t`, `systemctl reload nginx`. No Odoo restart.
- **Paused tenants**: the tenancy door `pb_tenancy/models/ir_http.py:183-228`
  returns early when there is no uid (`if not uid: return`, :201-203). An
  `auth='none'` route is therefore never stopped by it. The receiver must
  call `request.env['pb.tenancy'].sudo().access_state()` itself when
  `'pb.tenancy' in request.env` and answer HTTP 403 when
  `access == 'suspended'`.
- **Controller precedents**: `pb_zoho_bridge/controllers/zoho_webhook.py:40-90`
  (uniform "unauthorized", `hmac.compare_digest`, `type='jsonrpc'` not the
  deprecated alias). The receiver is `type='http'`, `auth='none'`,
  `csrf=False`, `methods=['GET','POST']`, returns `werkzeug` text responses
  (`Response(body, content_type='text/plain; charset=utf-8')`).
- **Ledger** (CLOCK-1): `pb.clock.punch.create` is multi, computes
  `dedup_key = sha1(company|serial-or-'upload'|user_code|punch_local)` and
  swallows duplicates per row; `pb.clock.device` has `serial`, `kind`
  (`upload`/`terminal`), `allowed`, `tz`, `last_punch_at`, `last_seen_at`,
  `_find_terminal(company, token)` (`pb_clock/models/clock_device.py`). The
  pairing cron is "Time clocks: pair punches" (5 min) and
  `cron.sudo()._trigger()` runs it soon.
- **Company settings** live on `res.company` and are edited from the lens
  settings card (`pb_clock/models/res_company.py`, `clock_lens.py
  save_settings`).
- **G3**: `filter_deploy.sh full` restores the pre-deploy cron set — switch
  any new cron on by hand per DB after the deploy (none planned here).
- **TLS on the box**: wildcard cert `payobook-wildcard` expires
  **2026-11-12**; per-tenant HTTP-01 certs renew by `certbot.timer`. Report
  `sudo certbot certificates` output (names + expiry only) in §10 so the
  coordinator can act; do not renew anything yourself.

## 3. The receiver (`pb_clock/controllers/iclock.py`)

### 3.1 Routes (PUSH 2.x, what ZMM100/200/510 firmware speaks)

| Method + path | Device sends | We answer |
|---|---|---|
| `GET /iclock/cdata?SN=…&options=all&pushver=…&language=…` | registration / handshake, repeated after every reboot and every `ErrorDelay` | **allowed**: the options block (3.2) · **pending/blocked/unknown**: HTTP 403 body `pending` (device retries in `ErrorDelay` s) |
| `POST /iclock/cdata?SN=…&table=ATTLOG&Stamp=…` | punch lines (3.3) | `OK: <n lines parsed>` — only after rows are in the ledger (so a crash means the device resends) |
| `POST /iclock/cdata?SN=…&table=OPERLOG&Stamp=…` | operation log | `OK: <n>` — count only, body dropped; bump `operlog_stamp` |
| `POST /iclock/cdata?SN=…&table=<anything else>` | user info, templates, photos | `OK: <n>` — dropped unread; log at INFO once per device per table per day |
| `GET /iclock/getrequest?SN=…[&INFO=…]` | poll for commands every `Delay` s; `INFO` = firmware, user count, fp count, attlog count, ip, … | `OK` when no command, else one `C:<id>:<command>` per line (3.5); store the INFO fields on the device |
| `POST /iclock/devicecmd?SN=…` body `ID=<id>&Return=<rc>&CMD=<cmd>` | command result | `OK`; mark the command done/failed with `rc` |
| `GET /iclock/ping`, `GET /iclock/push`, `POST /iclock/registry`, `POST /iclock/push`, `GET /iclock/querydata`, `GET /iclock/rtdata` | 3.x firmware or odd builds | 3.4 |

Every route: resolve `SN` (strip; 6–32 chars `[A-Za-z0-9]`), else HTTP 400.
Load the company's `pb.clock.device` by serial **across the whole DB**
(sudo; a DB is one tenant, several companies possible — the serial decides
the company; see 3.6 for first contact). Touch `last_seen_at`, `ip`
(`X-Forwarded-For` first hop, else remote addr), `last_proto`
(`X-Forwarded-Proto`, default `https`). Tenancy check (§2) before anything
else; a suspended tenant gets 403 `paused` on every route.

Plain-connection rule (D12): if `last_proto == 'http'` and the device's
company has `pb_clock_allow_plain` off → HTTP 403 body `https required`.
When on, serve normally and set `device.plain_connection = True` (the lens
shows a quiet chip "plain connection").

Limits: body ≤ 2 MB and ≤ 5 000 lines per POST (else 413 — ZK firmware
splits large uploads already); per serial ≥ 240 requests/min → log a
warning, keep answering (a 429 only makes a device loop harder). Nothing
is ever written for a device that is not `allowed`, except the pending
registration row (3.6).

### 3.2 Handshake body (allowed device)

```
GET OPTION FROM: {SN}
ATTLOGStamp={device.attlog_stamp or 0}
OPERLOGStamp={device.operlog_stamp or 0}
ATTPHOTOStamp=0
ErrorDelay=30
Delay=10
TransTimes=00:00;12:00
TransInterval=1
TransFlag=TransData AttLog\tOpLog
TimeZone={offset hours of device.tz, e.g. 7}
Realtime=1
Encrypt=0
ServerVer=2.4.1
```

Lines end `\r\n`. `TransFlag` names only attendance + operation logs so the
device never pushes user data or templates (rule 8). `Realtime=1` makes it
push each punch within seconds. **A fresh `allowed` device starts with
`attlog_stamp = 0`**: the device then uploads every log it still holds
(the 4000TID-C / FA110 hold ~100 000) — that is the backfill. The history
cut-off (3.6) decides what of it is paired.

### 3.3 ATTLOG lines

Tab-separated, one punch per line, `\n` or `\r\n` terminated:

`PIN \t YYYY-MM-DD HH:MM:SS \t status \t verify [\t workcode [\t reserved…]]`

Parse by position; tolerate 2–8 columns; some firmware inserts a machine
number as column 3 — detect by shape (an integer column 3 **and** column 4
looks like a status 0–5/255) and keep whatever is there in `direction_raw`
/ `verify_mode` as strings. A line that does not parse is counted, logged
at WARNING with the serial and the first 80 chars, and skipped; the `OK: n`
still counts it (a wrong count makes the device resend forever).

Write ledger rows with `source='adms'`, `device_id`, `user_code=PIN`,
`punch_local` from the string (device local time; `punch_utc` from
`device.tz`), `direction_raw=status`, `direction` = in/out when the company
trusts direction and status is 0/1 (ZK: 0 check-in, 1 check-out, 2 break
out, 3 break in, 4 OT in, 5 OT out), else `unknown`; `verify_mode` 1 fp,
4 card, 15 face, 0 password, else the number. Rows older than the
company's history cut-off get `state='ignored_before_start'` at create
(new state; the lens counts them under the machine card, "1 240 older
punches kept but not paired"). Update `attlog_stamp` from the `Stamp`
query argument after the rows are in. Then `cron._trigger()`.

### 3.4 Other firmware

- `GET /iclock/ping` → `OK`.
- `GET /iclock/push?SN=` (3.x asks for options here) → the same options
  body as 3.2 plus `ServerVersion=3.0.1`, `PushProtVer=3.0.1`,
  `RequestDelay=10`, `TransTables=Transaction`, `SessionID=<random>`,
  `TimeoutSec=10`, one `key=value` per line.
- `POST /iclock/registry?SN=` → `RegistryCode=<16 hex>` (store it; a 3.x
  device then sends `POST /iclock/push`); `POST /iclock/push` → the options
  body. 3.x punches arrive as `table=ATTLOG` too (some as
  `table=transaction` → treat as ATTLOG). Do not implement more; log the
  firmware string so CLOCK-3 can decide.
- Unknown `/iclock/*` → 200 `OK` (a 404 makes some firmware re-register in
  a loop — precedent in the design's sources).

### 3.5 Commands (`pb.clock.command`, new)

`device_id`, `command` (Char, the text after `C:<id>:`), `kind`
(`set_time`, `resend`, `check`, `custom`), `state` (`queued`, `sent`,
`done`, `failed`), `return_code`, `queued_at`, `sent_at`, `done_at`,
`note`. `getrequest` hands out at most 3 queued commands per poll, marks
them `sent`; `devicecmd` closes them (`Return=0` done, else failed with the
code). A `sent` command older than 10 min with no result → `failed`,
note "no answer".

- **Time sync.** For each allowed device keep a rolling skew: for each
  ATTLOG POST where the newest line is < 15 min old, `skew_s = received_at
  − punch_utc(newest)` (Realtime pushes arrive within seconds; a big skew is
  the clock, not the network). Store `clock_skew_s` = median of the last 7
  samples. When `|clock_skew_s| > 60` and no `set_time` command in the last
  6 h → queue `SET OPTIONS DateTime=<zk>` where `<zk>` encodes the device's
  current LOCAL time as ZK seconds: `((Y−2000)·12·31 + (M−1)·31 + (D−1))
  ·86400 + h·3600 + m·60 + s`. After it is done, reset the samples. Note
  this in plain words on the machine card ("Clock corrected 2 h ago, was
  4 min fast").
- **Resend punches since** (manager, machine card menu): queues `DATA QUERY
  ATTLOG StartTime=<YYYY-MM-DD 00:00:00>\tEndTime=<now>`; if the device
  answers a non-zero code or nothing in 10 min, queue `CHECK` as the
  fallback and say so. Dedup makes a resend harmless.

### 3.6 First contact, pending machines, history cut-off (D10)

- Unknown serial on any route → create one `pb.clock.device` row per
  serial with `kind='terminal'`, `state='pending'`, `serial`, `ip`,
  `firmware` (from `pushver`/INFO), `first_seen_at`, `company_id` = the
  DB's main company (`env.ref('base.main_company')`; a manager can move it
  while allowing). Cap: 50 pending rows per DB; beyond that answer 403 and
  log, create nothing. Answer 403 `pending`.
- `pb.clock.device.state` (new): `pending`, `allowed`, `blocked`;
  `allowed` (the CLOCK-1 Boolean) becomes a computed mirror of
  `state == 'allowed'` — keep it so CLOCK-1 code and tests still read.
  Upload pseudo-devices are `allowed`.
- Lens: a **"Machines asking to connect"** strip at the top of the Machines
  row (grey when empty, indigo with a count when not): serial · first seen
  "2 min ago" · IP · firmware · **Allow** (opens a 4-field sheet: name,
  location, time zone, history from) · **Ignore** (`blocked`; a blocked
  serial keeps answering 403 and never shows again unless un-blocked from
  the machine card). Hero moment of setup day: HR types the address into
  the machine, turns round, and the machine is already on the screen asking
  to be let in.
- `pb.clock.device.history_from` (Date). Default on Allow = first day of
  the current month in the device tz (Sudima: 1 Dec if allowed in
  December). Punches older than it → `ignored_before_start` (3.3). The
  Allow sheet says in one sentence what that means.
- Company setting `pb_clock_allow_plain` (Bool, default False; lens
  settings card, manager only; help: "Lets an older machine send over a
  plain web connection when it cannot make a secure one. Only the number,
  the time and the machine's serial travel.").

## 4. nginx — plain connection on port 80 (D12)

Goal: `http://<tenant>.payobook.com/iclock/…` reaches Odoo instead of being
redirected to HTTPS; everything else on port 80 keeps redirecting.

1. Read `/etc/nginx/sites-available/_`, `pb-wildcard`, one tenant block
   (e.g. `rize`), and `/usr/local/bin/pb-tenant-cert` (its server-block
   template). Write what you found in the report (paths and the port-80
   `server {}` shapes), then:
2. Create `/etc/nginx/snippets/pb-clock-plain.conf`:
   ```nginx
   location ^~ /iclock/ {
       proxy_pass http://127.0.0.1:8069;   # match the existing upstream name/port used by the HTTPS blocks
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto http;
       client_max_body_size 4m;
       proxy_read_timeout 60s;
   }
   ```
   and `include snippets/pb-clock-plain.conf;` as the FIRST location in the
   port-80 server of `_`, of `pb-wildcard`, of every existing tenant block,
   and in the template inside `pb-tenant-cert` (source copy in
   `pb_tenants/tools/pb-tenant-cert` — commit that too) so future tenants
   get it. Back each file up as `<file>.bak-clock2` first.
3. `sudo nginx -t`, then `sudo systemctl reload nginx`. Prove it:
   `curl -s -o /dev/null -w '%{http_code}' 'http://rize.payobook.com/iclock/ping'`
   → 200 `OK`; `curl -sI http://rize.payobook.com/web/login | head -1` → still
   a 301/302 to HTTPS. Also confirm the HTTPS blocks allow TLS 1.2
   (`ssl_protocols`) — ZK firmware cannot do TLS 1.3-only; report, do not
   change.

Also set `proxy_mode = True` expectation: check `/etc/odoo-server.conf`
has `proxy_mode = True` (it should — HTTPS works today); if not, say so,
do not edit the conf.

## 5. Pairing D11 + CLOCK-1 gaps

- **D11**: when a new work day's anchor arrives for an employee whose
  latest `device` attendance is still open and belongs to an EARLIER work
  day, close that earlier row with `check_out = check_in` (0 h), set the
  new Boolean `hr.attendance.pb_clock_auto_closed = True`, note the
  punch "Check-out missing; closed so later days can be paired", then pair
  the new day normally. The lens gets a **"Days missing a check-out"**
  table (person · day · check-in · door to a correction prefilled with that
  day) — grey at zero. Test it: two anchors on consecutive days, first day
  with one punch → day 1 closed 0 h + flagged, day 2 paired, nothing held.
- Week Grid locked-cell message for device rows: "Punch from a time clock —
  change it with a correction" (EN + VI), where CLOCK-1 left
  "Device/kiosk punch — edit on the attendance form".
- Person-search avatars in the lens show blank → use the same
  `avatar_url` the Time hub person drawer uses.
- Machine card title truncates "Files you upload" → let the title wrap to
  two lines.

## 6. Emulator + tests

`pb_clock/tools/zk_emulator.py` (stdlib only): `--base
http://host[:port] --sn TEST-0001 --tz 7 --pushver 2.4.1` runs the 2.x
loop: handshake, prints the options it got, posts ATTLOG lines read from a
file or generated (`--punch PIN,YYYY-MM-DD HH:MM:SS,status,verify`), polls
`getrequest`, executes `SET OPTIONS DateTime` by printing the decoded time,
answers `devicecmd`. `--v3` does the 3.x registry/push dance. Used by the
HttpCase tests (`odoo.tests.HttpCase`, `self.url_open`) and by you against
rize for the browser check.

Numbered tests (`pb_clock/tests/test_iclock.py`, `test_commands.py`,
`test_d11.py`):

1. Unknown serial handshake → 403 `pending`, one pending device row with ip
   + firmware; a second call creates no second row.
2. 51st unknown serial → 403, no row, one WARNING.
3. Allow the device → handshake 200 with `ATTLOGStamp=0`, `TimeZone=7`
   for Asia/Ho_Chi_Minh, `TransFlag` naming AttLog+OpLog only.
4. ATTLOG POST of 5 lines (4 valid, 1 garbage) → `OK: 5`, 4 ledger rows
   `source='adms'`, `attlog_stamp` = the `Stamp` arg, cron triggered
   (assert the trigger row exists).
5. Same POST again → `OK: 5`, still 4 rows (dedup).
6. Lines with a machine-number third column → still parsed, times right.
7. Punch dated before `history_from` → `ignored_before_start`, never paired;
   punch after → paired.
8. OPERLOG / USERINFO / BIODATA POSTs → `OK: n`, zero rows anywhere, one
   INFO log line.
9. `getrequest` with `INFO=` → device `firmware`, `users_count`,
   `attlog_count`, `ip` updated; answer `OK`.
10. Skew: 7 realtime posts whose punch time is 4 min behind "now" →
    `clock_skew_s ≈ -240`, one `set_time` command queued with the correct
    ZK encoding (unit-test the encoder against three known values);
    `getrequest` returns `C:<id>:SET OPTIONS DateTime=…`; `devicecmd`
    `Return=0` → done; a second skew burst within 6 h queues nothing.
11. "Resend since" → `DATA QUERY ATTLOG` command queued; `Return=-1` →
    failed + `CHECK` queued with a note.
12. Blocked device → 403 on every route, no writes, no pending row.
13. Suspended tenant (mock `pb.tenancy.access_state` → `suspended`) → 403
    `paused` on every route, nothing written.
14. Plain proto (`X-Forwarded-Proto: http`) with `pb_clock_allow_plain`
    off → 403 `https required`; on → 200 and `plain_connection` True.
15. 3.x dance: `registry` → `RegistryCode`, `push` → options with
    `PushProtVer`; `ping` → `OK`; `/iclock/whatever` → 200 `OK`.
16. Body > 2 MB or > 5 000 lines → 413, nothing written.
17. D11 scenario (§5).
18. Security: the receiver writes only through sudo on its own models; a
    plain user cannot read `pb.clock.command`; a manager can queue
    "Resend since", an officer gets `{'error': …}`.
19. No "Odoo" in any string of the phase (grep gate).
20. CLOCK-1 tests 1–18 still pass (run them).

Run on a throwaway copy of p0clone (G7/G8), SCHEMECTX recipe; HttpCase
needs the alternate `--http-port`.

## 7. Setup-day runbook (deliverable, plain English + Vietnamese)

`docs/handovers/clock/SETUP_DAY.md`, for Sudima's HR/IT, no technical
vocabulary: per model (4000TID-C orange menu, FA110 green menu) the exact
taps: Menu › Comm. › Cloud Server (Cài đặt máy chủ đám mây): server type
ADMS, enable domain name OFF, address = `sudima.payobook.com`, port `443`,
proxy OFF, HTTPS ON, save, restart the machine; then "within a minute the
machine appears under Machines asking to connect; press Allow". If after 5
minutes it does not appear: HTTPS OFF, port `80` (the plain connection;
only after Payobook's switch is on), restart again. What HR sees next: the
machine card, first punches, the history count. Where the Mitaco daily
sheet goes (Import › Time-clock punches). A 10-line checklist to print.
Photos not needed; one screenshot of the lens per state from rize.

## 8. Browser validation (Chrome MCP, mandatory)

On rize.payobook.com with the emulator run from the box (`ssh
Payobook19v2`, python3, base `https://rize.payobook.com`, SN `TST-0002`):
see the pending strip appear within the 30 s refresh; Allow with
`history_from` = today; emulator posts 6 punches (two people, one before
`history_from`); watch the machine card (last punch, punches today, clock
chip), the Week Grid cells, the ignored-before-start count; queue "Resend
since" and watch the command go sent → done; set the clock 5 min off in the
emulator and watch "Clock corrected"; try the plain URL on port 80 with the
company switch off (403) and on (200). Console clean; screenshots to
`docs/handovers/clock/shots/p2-*.png`. Then delete every test punch,
attendance, command and the `TST-0002` device, and switch plain back off.
payobook.com pass only if a session is open; say so otherwise.

## 9. Deploy

Normal tier ×4 with `/odoo/ops/filter_deploy.sh full` for `pb_clock
pb_hr_workforce pb_time_hub pb_attendance_flow pb_tenants` (only those
with changes), staged from committed HEAD; G2 alias `Payobook19v2`;
`/opt/deploy-notes.md` START/DONE; heads-up to other sessions via
`ListAgents` → `SendMessage` (if the tool is unavailable say so, as P1
did); lock check; asset purge + `web.assets.version` bump; PO gate; SCSS
gate; versions and hashes verified ×4. The nginx step (§4) is separate,
after the Odoo deploy, with its own START/DONE line.

## 10. Report back (`docs/handovers/clock/CLOCK_P2_REPORT.md`)

Format of `CLOCK_P1.md` §10, plus: the nginx diff (before/after of each
port-80 server), `certbot certificates` names + expiry, the exact handshake
body a real device will receive on rize (from the emulator log), the
setup-day runbook link, and the list of what CLOCK-3 must alert on (silent
machine, skew, pending machines ignored > 24 h, auto-closed days).
