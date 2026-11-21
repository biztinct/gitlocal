# CLOCK-2 report — machines push to Payobook

Delivered 2026-11-05. Live on payobook, payobook_template, p0clone, rize
(see §4). Setup-day runbook: [`SETUP_DAY.md`](SETUP_DAY.md) (English + Vietnamese).

## In plain words (for the owner)

- **A machine can now send its punches straight to Payobook.** HR types the
  workspace address into the machine (Menu › Comm. › Cloud Server), restarts
  it, and within a minute the machine appears at the top of **Time › Time
  clocks** under **"1 machine is asking to connect"**. Nothing is accepted from
  it until a manager presses **Allow**.
- **Allow asks four things**: a name, a location, the time zone and the first
  day to pay from (filled in with the first day of the month). The machine
  then sends everything it still holds; punches from before that day are kept
  on record but never become work days. The card says how many.
- **Each machine has a card**: connected or silent since when, punches today,
  whether its clock is right ("Clock corrected 2 h ago, was 4 min fast"), and
  a menu with **Resend punches since…** and **Ignore this machine**.
- **The machine's clock is checked from its own punches.** If it drifts more
  than a minute, Payobook sets it — at most once every six hours.
- **Machines you do not know** can be ignored; they are never listened to
  and never shown again unless someone lets them ask again.
- **Older machines that cannot make a secure connection** can use a plain one,
  but only after a manager switches on "Allow a plain connection" in the
  settings card. It is off everywhere.
- **A forgotten check-out no longer blocks the next days.** That day is closed
  at its check-in (0 hours) and listed under **"Days missing a check-out"**
  with a "Fix this day" button.
- The Week Grid now says "Punch from a time clock — change it with a
  correction" on a machine day.
- **One thing to know for setup day:** on the machine, "Enable domain name"
  must be **ON** (the handover said off). With it off the machine only takes
  a number address, and a number address cannot tell Payobook which company
  it belongs to.

## 1. Commits (branch 19.1, pushed)

| Hash | What |
|---|---|
| 63f55b34d | Steps 1–3 core — `/iclock/*` receiver, pending machines, plain-connection gate, command channel, measured time sync, migration |
| 21c98416f | Steps 2–3 screens — asking-to-connect strip, Allow sheet, machine card + menu, Resend since, settings switch; emulator; tests 1–16, 18, 19 + HTTP test |
| 160b771ea | Step 4 — nginx snippet, `pb-tenant-cert` template, `pb-wildcard` copy |
| 0d28bd8a6 | Step 5 — D11 pairing rule, command sweep in the job, Week Grid sentence, title wrap, test 17 |
| 8d4a2d122 | Step 6 — Vietnamese (pb_clock 351 entries; pb_hr_workforce 2 new), runbook EN+VI, ledger G9–G15 |
| d4ea4731d | browser fix — top sentence says when a machine is asking / connected; card name gets its own row; setup text names "Enable domain name ON"; repo copy of pb-wildcard = live file |
| 3ba5aa982 | browser fix — machine menu opens to the right (was cut off behind the side bar) |
| 2d5efa794 | browser fix — "Before start" chip (and counted under Ignored); the plain switch saves with its own toast; picture placeholder while loading; test 7 asserts the chip |
| (this) | report, shots |

Versions: pb_clock 19.0.1.1.0, pb_hr_workforce 19.0.4.24.0; pb_tenants files
only (version unchanged; its tools are not loaded by the server).

## 2. Tests 1–20

Run on a throwaway copy of p0clone (`clk2test`, jobs and logins off, scratch
addons dir, ports 8193/8192), `-u pb_clock,pb_hr_workforce --test-tags
/pb_clock,/pb_hr_workforce`: **106 tests, 0 failed, 1 error** — the error is
`pb_hr_workforce` `TestWeekEntry.test_06_submit_week_and_approve` (overtime
approval route on this data), the same test CLOCK-1 recorded as failing on
unchanged code. **pb_clock: 64 of 64 pass** (CLOCK-1's 30 + CLOCK-2's 34),
re-run after the last browser fix (2d5efa794): 64 of 64 again. The throwaway
copy, scratch addons and scratch config were removed afterwards.

| # | Case | Test | Result |
|---|---|---|---|
| 1 | unknown serial → 403 `pending`, one pending row with IP + firmware; second call no new row | test_iclock 01 (+01b bad serial → 400) | PASS |
| 2 | 51st unknown serial → 403, no row, one warning | 02 | PASS |
| 3 | Allow → handshake 200, `ATTLOGStamp=0`, `TimeZone=7`, `TransFlag=TransData AttLog\tOpLog` only | 03 (+03b a machine an upload created waits for Allow too) | PASS |
| 4 | 5 lines (1 garbage) → `OK: 5`, 4 rows `adms`, stamp stored, job triggered (trigger row counted) | 04 (+04b trusted In/Out) | PASS |
| 5 | same post → `OK: 5`, still 4 rows | 04 | PASS |
| 6 | machine-number third column; 2- and 8-column lines | 06 | PASS |
| 7 | before `history_from` → `ignored_before_start`, never paired; after → paired; card counts 2 | 07 (+ HTTP test) | PASS |
| 8 | OPERLOG / USERINFO / BIODATA → `OK: n`, zero rows, one log line each per day | 08 | PASS |
| 9 | `getrequest` INFO → firmware, people, fingerprints count, punches count, LAN address | 09 | PASS |
| 10 | 7 live posts 4 min slow → skew ≈ −243 s, ONE `SET OPTIONS DateTime=` with the right local time; handed out once; `Return=0` → done, corrected, samples reset; second burst within 6 h → nothing; encoder against 3 known values | test_commands 10 ×2 (+10b on-time clock and backfill measure nothing, 10c three per poll, other machine cannot close it) | PASS |
| 11 | Resend since → `DATA QUERY ATTLOG StartTime=…`; `Return=-1` → failed + `CHECK` queued with a note, stamp back to 0; no answer in 10 min → failed "No answer." + fallback | 11, 11b | PASS |
| 12 | blocked → 403 on every route, no write (write_date unchanged), no pending row | 12 | PASS |
| 13 | paused tenant (`pb.tenancy.access_state` mocked) → 403 `paused` on every route, nothing written | 13 | PASS |
| 14 | `X-Forwarded-Proto: http` switch off → 403 `https required`; on → 200, plain chip, chip clears on HTTPS | 14 (+ HTTP test with the real header) | PASS |
| 15 | registry → `RegistryCode`, push → `PushProtVer`, ping, unknown path 200 `OK`, `.aspx`, `table=transaction` | 15 (+ HTTP test) | PASS |
| 16 | > 2 MB, Content-Length too big, > 5 000 lines → 413, nothing written | 16 | PASS |
| 17 | D11: day 1 one punch, day 2 → day 1 closed 0 h + flagged, day 2 paired, nothing held, idempotent | test_d11 17 (+17b across runs + lens row + late check-out heals; 17c a hand-made open row is never closed) | PASS |
| 18 | receiver writes through sudo whoever calls; plain user cannot read commands; officer cannot create one; manager queues Resend, officer gets `{error}`; officer sees pending, only a manager allows / ignores / lets it ask again | 18 | PASS |
| 19 | no brand name in any pb_clock file (incl. tools, controllers) nor pb_hr_workforce msgstr | 19 (+ CLOCK-1 test 17) | PASS |
| 20 | CLOCK-1 tests 1–18 | test_clock, test_clock_upload, test_clock_lens (30 tests) | PASS |

Also: `test_iclock_http` (2 tests) drives the REAL route with the emulator
over HTTP — pending → Allow → handshake → 3 punches (one before the start
day) → poll with INFO → Resend since answered by the emulator → a body
labelled as a web form (G10) → unknown path; and the plain header + 3.x
dance. Lens: pending strip + Allow sheet validation, Allow merges with a
machine an upload already knew, rate warning at 240 requests/min.

## 3. Browser validation

**rize.payobook.com** (open session, Chrome), emulator run FROM THE BOX
(`ssh Payobook19v2`, `python3 zk_emulator.py --base https://rize.payobook.com
--sn TST-0002 --tz 11`; Rize Farms runs on Sydney time). Shots in `shots/`:

| Shot | What it proves |
|---|---|
| p2-01-empty-with-address | new empty state: two doors, the address and port to type in |
| p2-02-asking-to-connect | **hero moment**: the emulator called once, the 30-second refresh brought "1 machine is asking to connect" with serial, first heard, address it calls from, push version — no reload |
| p2-03-allow-sheet | Allow sheet: name focused, zone filled (Australia/Sydney), pair-from day; the sentence updates live ("Punches from before 05 Nov 2026 are kept…"); Enter let it in; toast "Test gate (emulator) is connected…" |
| p2-04a / p2-04 | the card before / after the layout fix: "5 today · Connected · Clock on time · Pairing from 05 Nov 2026 · 1 older punch kept, not paired"; later "Silent since 7 min ago" when the emulator stopped polling |
| p2-05a | card menu → Resend punches since… (date defaults to the pair-from day) |
| p2-06 | after the emulator answered: "Clock corrected 1 min ago, was 5 min fast" and "Resend since 05 Nov 2026 done 1 min ago" |
| p2-07 | settings: "Allow a plain connection" switched on, saved |
| p2-08 | Week Grid: Nguyễn Anh Đào (RIZ002) Thu 10.81 h, cell says "Punch from a time clock — change it with a correction." |
| p2-09 | person search with pictures (they render; CLOCK-1's "blank" was the picture still loading — a soft placeholder now fills the spot) |
| p2-10 | recent punches: In / Break tap / Out / Double tap / Unknown / **Before start**; tab badge 1 for the unknown number |
| p2-11 | payobook.com (session open, read only): the empty state with its own address |

Server side during the walk-through: 6 punches → `OK: 6`, paired within
seconds (RIZ002 08:01→18:49, RIZ013 08:10→18:49, middle taps as Break tap,
4 Nov kept as before-start); Resend → `C:1:DATA QUERY ATTLOG StartTime=2026-11-05
00:00:00\tEndTime=…` → emulator re-sent 3 → `Return=0` → done, ledger still 6
(repeats kept once); fast clock (+300 s) × 3 live punches → `C:2:SET OPTIONS
DateTime=862857864` → emulator "clock set to 18:44:24 (was 18:49:31)" → done,
corrected by 300 s; plain `http://rize.payobook.com/iclock/cdata?SN=TST-0002`
→ 403 `https required` with the switch off, 200 handshake + plain chip with
it on, 403 again after switching off. Console: no errors on either site.

Clean-up (logged in `/opt/deploy-notes.md`): the machine, its 10 punches, the
2 days it made, its 2 commands removed through the model layer; plain switch
off on every company; a probe pending row removed. rize holds no time-clock
data again.

Interruptions: two other sessions' deploys restarted the server during the
walk-through (07:20 and 07:31 UTC); the Resend step was repeated after them.

## 4. Deploy

| Commit | Module → version | Window (UTC) | EXIT per DB | Jobs before → after | Evidence |
|---|---|---|---|---|---|
| 8d4a2d122 | pb_clock 19.0.1.1.0 (-u, migration), pb_hr_workforce 19.0.4.24.0 (-u), pb_tenants files | 07:13:15–07:19:31 | p0clone 0 · template 0 · rize 0 · payobook 0 (errors 0) | 33/29/76/44 → same (no new job) | `/tmp/clock2-run-20261105071315`, backups `/odoo/backups/clock2-run-20261105071315` |
| d4ea4731d | pb_clock (-u for the new Vietnamese) + pb_tenants files | 07:27:16–07:30:55 | 0 ×4 | unchanged | `/tmp/clock2b-run-20261105072716` |
| 3ba5aa982 | pb_clock SCSS (looks, no restart) | 07:42 | OK | unchanged | `/tmp/clock2c-run-…` |
| 2d5efa794 | pb_clock (-u) | 07:52–07:54:23 | 0 ×4 | unchanged | `/tmp/clock2d-run-…` |

Before the first deploy: live trees of all three modules equalled the
pre-change commit; SCSS compiled with the box's libsass; PO gate pb_clock
410 → 417 rows, pb_hr_workforce 664, none empty. After: tree hashes equal
the stage, `latest_version` = manifest on all four, sites 200. The migration
seeded `state` on every existing machine row (0 rows needed it on these
databases — no terminals were registered yet). The 05:06 hold another
session asked for was respected (deploy started 07:13, when no replay was
left). `ListAgents` is not available in this session, so no heads-up could be
sent; every START/DONE is in the notes file.

## 5. nginx — plain connection on port 80 (D12)

Found on the box (read first): port-80 servers in `sites-available/_`
(apex; certbot's `if ($host = payobook.com) { return 301 … }` + `return 404`
at server level), `pb-wildcard` and `pb-tenant-rize.payobook.com.conf`
(server-level `return 301 https://$host$request_uri;`), `pb-default`
(default_server catch-all, left alone), `pb-tenant-abm…` (retired, 410, left
alone), two custom-domain blocks for rize (`jobs.rize.farm`,
`people.rize.farm`) that are port-80-only pass-throughs already (left alone).
Upstream `http://127.0.0.1:8069` everywhere. `proxy_mode = True` in
`/etc/odoo-server.conf` (not edited).

A server-level `return` runs before any location is chosen (G13), so each
port-80 server became:

```nginx
# before (pb-wildcard / rize)              # after
server {                                    server {
  listen 80;                                  listen 80;
  server_name *.payobook.com;                 server_name *.payobook.com;
  return 301 https://$host$request_uri;       # CLOCK D12: … (comment)
}                                             include /etc/nginx/snippets/pb-clock-plain.conf;
                                              location / { return 301 https://$host$request_uri; }
                                            }
```

The apex block lost certbot's `if`/`return 404` pair for the same shape
(its server_name is only payobook.com, so behaviour is the same). Backups:
`<file>.bak-clock2` for all three, and `/usr/local/bin/pb-tenant-cert.bak-clock2`
(new template installed from 160b771ea, so sudima.payobook.com gets the
include when its block is written). New file
`/etc/nginx/snippets/pb-clock-plain.conf` (passes `/iclock/` only, sets
`X-Forwarded-Proto: http`, 4 MB, 60 s, own access log).

Proof: `nginx -t` OK, `systemctl reload nginx` (no application restart);
`http://{rize,payobook,p0clone}.payobook.com/iclock/ping` → 200 `OK`;
`http://…/web/login` → still 301 to https on all three; HTTPS unchanged
(`/iclock/ping` 200, `/web/login` 200); TLS 1.2 offered (`ssl_protocols
TLSv1.2 TLSv1.3`, a TLS 1.2 handshake to rize negotiates
ECDHE-ECDSA-AES256-GCM-SHA384).

**Certificates** (`sudo certbot certificates`, nothing touched):

| Name | Domains | Expires |
|---|---|---|
| payobook-wildcard | *.payobook.com | **2026-11-12 (6 days)** — manual DNS renewal; any tenant without its own block (and a new sudima tenant until `pb-tenant-cert` runs for it) depends on it |
| payobook.com | payobook.com | 2027-01-28 |
| pb-tenant-rize.payobook.com | rize.payobook.com | 2026-12-09 (auto-renews) |
| pb-tenant-abm.payobook.com | abm.payobook.com | 2027-01-13 |

## 6. The handshake a real machine receives on rize

From the emulator log (allowed machine, first contact after Allow); lines end
`\r\n`, the tab in TransFlag is a real tab:

```
GET OPTION FROM: TST-0002
ATTLOGStamp=0
OPERLOGStamp=0
ATTPHOTOStamp=0
ErrorDelay=30
Delay=10
TransTimes=00:00;12:00
TransInterval=1
TransFlag=TransData AttLog	OpLog
TimeZone=11
Realtime=1
Encrypt=0
ServerVer=2.4.1
```

(`TimeZone=7` for a Vietnam machine — test 3.) A machine nobody let in gets
HTTP 403 `pending`; a plain connection with the switch off gets 403 `https
required`; a paused workspace gets 403 `paused`.

## 7. Design bar — self-score 8.5/10

- **Hero (setup day):** the machine appears by itself within 30 s under an
  indigo "1 machine is asking to connect" strip with a radar pulse and an
  arrival ripple; Allow opens in place; the top sentence now says what is
  happening ("A machine is asking to connect. Press Allow to let it in." /
  "<name> is connected. Waiting for the first punch.").
- **States:** empty (two doors + the address), asking, allowed-and-waiting,
  live, quiet/silent, ignored machines (folded), resend queued / sending /
  done / failed with the fallback, clock on time / off / corrected, plain
  chip, days missing a check-out (grey at zero), before-start count.
- **Plain language:** every line in words ("Silent since 14:02", "Clock
  corrected 2 h ago, was 4 min fast", "Pairing from 01 Dec 2026 · 1,240 older
  punches kept, not paired"); EN + VI for all; no brand name (test 19).
- **Motion:** radar pulse on the strip, arrival ripple, sheet rise, spinner on
  a command that is on its way; nothing moves at rest.
- **Keyboard:** the Allow sheet focuses the name, Enter lets it in, Esc closes.
- **Gaps:** the machine menu is a click menu, not keyboard-navigable; no bulk
  Allow for seven machines at once (each takes one sheet — fine for seven);
  the time-zone field is a plain list box with typing, not a searchable
  picker; the card does not yet show users/fingerprint counts outside the
  menu.

## 8. Deviations

1. **Steps 1–3 were built together** — the machine model carries the
   stamps, the skew and the commands, so it could not load in three parts.
   Committed as core (63f55b34d) then screens + tests (21c98416f).
2. **"Enable domain name" ON**, not OFF (§7 of the handover) — see G14.
3. **Serial pattern** also allows `-` and `_` (`[A-Za-z0-9_-]{6,32}`): the
   handover's own test serials (`TEST-0001`, `TST-0002`) carry a dash.
4. **Skew sign**: stored as machine time − server time (positive = fast), so
   "4 min behind" is −240 as test 10 asks; §3.5 wrote the subtraction the
   other way round.
5. **When a sample is taken**: newest line within 15 min of now (as specified)
   OR a small live post (≤ 2 lines, newer than anything the machine sent
   before, within a day) — otherwise a clock off by more than 15 min would
   never be corrected. Acts after 3 samples (median), not only after 7.
6. **Return code**: `>= 0` is done (ZK answers a count for some queries),
   negative is failed.
7. **Resend fallback** also puts the punch stamp back to 0 before `CHECK`, so
   a machine that ignores DATA QUERY sends everything it holds (dedup keeps
   it harmless).
8. **INFO's address** is stored as "address on the local network"
   (`lan_ip`); `ip` stays the internet address the machine calls from.
9. **A machine an upload created** (CLOCK-1 `<serial>_attlog.dat`) turns
   pending on its first network call and waits for Allow — so a machine with
   months of history never pairs it unasked. Allow then keeps that machine
   (and its punches) and drops the empty pending row.
10. **Pending machines are shown to every officer of the database** (a
    database is one tenant); Allow places the machine in the manager's
    current company.
11. **Blocked machines** answer `pending` (not a distinct word) so a
    stranger's machine learns nothing.
12. **Other Week Grid lock sentence**: rows typed or imported outside the
    grid now say "Entered outside the Week Grid — change it with a
    correction." (the old sentence called them kiosk punches).
13. **Custom-domain blocks** (`jobs.rize.farm`, `people.rize.farm`) were not
    edited: they are plain port-80 servers that already pass everything to
    the application with `X-Forwarded-Proto: http`. The `abm` block was not
    touched (retired).

## 9. Gotchas

Appended to `CLOCK_LEDGER.md` §3: G9–G15.

## 10. What CLOCK-3 must alert on

1. **Silent machine** — `last_seen_at` older than 15 min (it polls every
   10 s) on an allowed machine; punches stop > 6 h on a working day.
2. **Clock skew** — `clock_skew_s` beyond 60 s with ≥ 3 samples and no
   correction done in 6 h (the command failed or was ignored); also punches
   landing as "Ignored" for the future (a fast clock).
3. **Machines asking to connect for more than 24 h** (`state = pending`,
   `first_seen_at` older than a day).
4. **Days missing a check-out** (`hr.attendance.pb_clock_auto_closed`) without
   a correction after N days, and before the pay period closes.
5. Commands failed twice in a row (Resend did not work either way).
6. A plain connection in use (`plain_connection`) — tell the owner which
   machine, so firmware can be updated.

## 11. Open questions for CLOCK-3

1. **The wildcard certificate expires 12 Nov.** sudima.payobook.com must get
   its own certificate (`pb-tenant-cert`, which now carries the plain
   snippet) when the tenant is made, or the wildcard must be renewed first —
   a machine that cannot verify the certificate will never connect.
2. **Machines that only take a number address** (ZMM100 "New office" if its
   firmware has no domain-name option): a number address cannot pick the
   workspace. Options: a dedicated port on the box mapped to `sudima`, or a
   per-IP nginx block. Needs the client's photo of that machine's menu.
3. **Firmware that ignores DATA QUERY** falls back to sending everything
   again (stamp 0 + CHECK) — fine for 100 000 lines (dedup), but CLOCK-3 should
   show progress for a big backfill (today the card shows the count only).
4. **Time zone of a machine vs the person:** Rize shows Vietnamese staff on a
   Sydney machine — punches are stored by the machine's zone and the day by
   the person's zone (ledger rule 11). Correct, but CLOCK-3's alerts should
   name the zone when they disagree.
5. **Rate:** seven machines polling every 10 s = 0.7 requests/s, each a small
   read plus at most one write a minute. Watch it on setup day; raise `Delay`
   if the box is busy.
6. `ListAgents` was not available, so other sessions were not told directly;
   two of their deploys restarted the server mid-walk-through. A shared
   "deploy in progress" signal other than the lock would help.
