# CLOCK-1 — paused 2026-11-05 ~02:25 UTC (owner asked)

## State in one line

Steps 1–6 are built, tested and **live on all four databases**
(payobook, payobook_template, p0clone, rize). What is left is the browser
walk-through of the upload, a few clean-ups, and the report.

## Done (commits on 19.1)

| Step | Commit | What |
|---|---|---|
| 1 local-day fix | 2512ca3e2 | grid read/save, person drawer, packet (`_week_bounds`, `_scan_week`, unapproved-weeks finder), freeze pairs, correction day check — all by the person's local day; helpers on `hr.attendance` in pb_hr_workforce |
| 2 pb_clock models | f73696c4d | ledger, machines, clock number, company settings, `device` entry source, ACL + company rules |
| 3 pairing + job | e66f3042b | `pb.clock.pairing`, cron "Time clocks: pair punches" (5 min) |
| 4 upload mode | 60713c171 | importer `mode='punches'` (attlog.dat, daily sheet, table), Import lens mode cards |
| 5 lens | e0636b905 | Time hub lens registry (pb_time_hub 19.0.1.4.0) + Time clocks lens |
| 6 i18n | 0c5708cad | pb_clock vi_VN.po (221 entries, from the server's own export), 65 new in pb_attendance_flow |
| fix | e5e99b885 | lens template did not compile (an `if` in an inline handler) — fixed, looks deploy |

Tests: 36 pb_clock tests + 9 local-day tests pass (175-test run, the 6 failures
are pre-existing and identical on unchanged HEAD: weekentry test_06,
attendance_flow 04/05/07/13, packet s02 — data-dependent on the p0clone copy).
Cases 1–18 all covered; run on a throwaway copy of p0clone (`clk1test`), not
p0clone itself.

Deploy: `/tmp/clock1-run-20261105021444` OK ×4, EXIT 0 errors 0, versions
match; fix 1 looks deploy OK. Cron ON payobook (id 148), p0clone (84), rize
(84); OFF on payobook_template with 84 appended to
`pb_tenants.template_active_crons`. START/DONE lines written.

## Half-done (nothing half-written in code)

Browser validation on rize: Time hub shows the new tab; Import mode cards
render; Time clocks empty state renders; "Upload a punch file" opens the
importer on punch mode. **Not yet done:** upload the 20-row CSV, toast /
badge / hero, assign + auto-match, Week Grid check, settings change, console
read, screenshots into `docs/handovers/clock/shots/`, payobook.com pass.
No test punches were written on rize (ledger count 0 when paused).

## Resume exactly here

1. On rize, Mission Control › Time › Import (Time-clock punches): upload a
   CSV of codes RIZ002/RIZ013/RIZ017/RIZ018 (no attendance on 2–4 Nov) plus
   TST-A/TST-B; walk §8 of CLOCK_P1.md. The file input can be fed by JS
   (DataTransfer) — `file_upload` only takes shared paths.
2. Afterwards remove every test punch AND the device attendances it made
   (sudo unlink in a shell; rize company tz is Australia/Sydney).
3. **Drop the throwaway database `clk1test`** on the box
   (`sudo -u postgres dropdb clk1test`) — it is a copy of p0clone, so it has
   p0clone's logins; scratch dirs `/tmp/clk_test`, `/tmp/clk_t2`,
   `/tmp/clk_base`, `/tmp/clk_stage*` can go too.
4. Write `CLOCK_P1_REPORT.md` (format CLOCK_P1.md §10) and push.

## Deviations so far (for the report)

- `pb_hr_workforce/models/hr_attendance.py` already existed; helpers added to it.
- Two more UTC-day sites converted: the Time hub person drawer and the
  correction "is the punch on this day" check; plus the packet's
  unapproved-weeks finder (raw SQL by `check_in::date`).
- `work_day` = anchor's local day in the **employee** zone (ledger rule 11),
  not the device zone; identical when they agree.
- Icons: the shared registry has no fingerprint/radio/pause-circle; used
  `scan`, `pause`, `userX` rather than touching pb_import_kit (its `-u`
  cascades widely).
- "Assign now" sits on the import's Done card, not the check card: before the
  import the numbers are not in the ledger, so the lens would show nothing.
- Test 2 text says "Tuesday's cell" — 4 Nov 2026 is a Wednesday; asserted
  Wednesday.
- Iterated tests on a copy of p0clone so p0clone never held a module its live
  server could not load.
- SSH alias `Payobook19` points at the old address (refused); used `Payobook19v2`.

## Gotchas (also appended to CLOCK_LEDGER.md §3)

G2–G7 there.
