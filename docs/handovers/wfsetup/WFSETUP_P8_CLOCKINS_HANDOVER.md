# WFSETUP P8 — Sudima: turn the 71,063 received clock records into attendance (rehearse, then live)

Owner instruction 2026-11-25: "is there anything which is stopping you from moving the raw records to the attendance
records? Otherwise do it so that we are able to do pay runs." Sudima is a production tenant not yet in real use (pay
runs so far are trials) — but treat its data as real.

## Verified facts (2026-11-24 21:48 UTC, read-only; do not re-derive)
- sudima `pb_clock_connector_event`: 71,063 rows, ALL state `ready`, punch_local 2026-09-01 … 2026-11-23 12:27,
  663 distinct user codes, 60,219 distinct row hashes; received 12–23 Nov. `pb_clock_punch` 0 rows. `hr_attendance` 0 rows.
- Six `pb.clock.connector` rows, all `publish_punches` = False ("Send accepted records to attendance").
- `pb_clock/models/clock_connector.py:322-372`: `_interpret` leaves a row `ready` while the switch is off;
  `_cron_process` picks up `ready` rows of connectors with the switch on, 500 per run, re-triggering itself, creating
  `pb.clock.punch` via `_ingest` (state `posted` / `duplicate` / `review`), then triggers `pb_clock.cron_pair_punches`.
- Ledger WS47: rules read connector events directly; legacy pairing into `hr.attendance` is skipped for people on an
  ACTIVE rule set (`pb_attendance_policy/models/policy.py:578-587`). Sudima today: 678 active people, 27 without a rule
  set, rule sets NOT confirmed/active; 12,384 DRAFT roster rows 19 Nov–16 Dec, nothing published.
- On-screen twin exists: Workforce setup › step 6 › "Switch clock-ins on" (`pb_workforce_setup/models/clocks.py:271-277`).
- Outgoing mail on sudima is off by owner choice — do not turn it on, do not raise it.

## Step A — rehearsal on a hidden copy (mandatory, decides go/no-go)
Copy sudima to `zz_wfs_p8_<date>`; the instant it exists switch OFF every scheduled job and mail server in it; run it
on a separate port from the LIVE addons dir (code is identical; clone `p5b/wfs_rh_serve.sh`). A peer agent (P7) may
stop/restart the live service for ~10 minutes while you work — a dropped connection is that, retry.
On the copy: switch all six on (through the studio method), then run `_cron_process` by hand until no `ready` row is
left, then the pairing job until idle. Record and judge:
1. Time taken; errors; final event states (posted / duplicate / review / historical) with the top review reasons.
2. Punches created; how many attach to an employee vs unmatched user codes (list the count of unmatched codes and of
   active employees with no punches at all — numbers only in the committed report, no names).
3. `hr.attendance` created: count, date range, people; open (no check-out) rows; absurd rows (> 16 h, negative,
   overlapping per person) — counts and five anonymised examples; worked-hours total per month.
4. Side effects: any mail queued (`mail_mail`), notifications/activities, overtime requests, late/early flags,
   approvals, timesheet lines, anything written outside punches/attendance/events. Count tables before and after
   (clone `p5b/wfs_counts.sh`, extend it).
5. Idempotence: run both jobs again → zero new rows.
6. Reversibility: write and TEST on the copy an undo script that returns the database to the exact pre-switch counts
   (events back to `ready`, punches and derived attendance removed, switches off). Keep it in `p8/`.
7. What a pay run then needs: on the copy, take one trial month (October) for a handful of people and follow the
   chain attendance → timesheet/hours → pay data, and state precisely what is still missing for a Sudima pay run to
   pick up worked hours, overtime and lateness (e.g. rules not confirmed, roster not published for past dates, period
   close). Do NOT fix those; list them plainly for the owner.
Drop the copy and its filestore at the end (after step B if you want it for comparison).

**Go only if**: no errors; ≥ 95 % of non-duplicate records become punches attached to an employee; no mail or
approval/notification flood; undo script proven; absurd attendance rows < 2 % of rows. Otherwise STOP after A and
report — the owner decides.

## Step B — live (only on Go, and only after P7's DONE line is in `/opt/deploy-notes.md`, or if P7 has not put a
START there yet — never between its START and DONE)
- deploy-notes START (data change on sudima only, no restart, no code); shared lock; fresh `pg_dump -Fc` of sudima
  kept permanently under `/odoo/archives/sudima-clockins-<date>/` with the undo script beside it.
- Switch the six clocks on ON SCREEN through step 6 (owner rule: what we do must be doable on screen) with a login
  enabled for this and disabled + rotated afterwards; let the live jobs drain the backlog (trigger the processing job
  rather than waiting; do not run 71k rows in one transaction). Watch the log.
- Verify: counts equal the rehearsal's (± records that arrived since); zero mail queued; step 6 shows the clocks as
  sending/“not heard from” truthfully; Attendance screens show September–November; console clean.
- Do NOT confirm rules, do NOT publish a roster, do NOT run or alter a pay run.
- deploy-notes DONE with counts.

## Report (`WFSETUP_P8_REPORT.md`, committed + pushed to 19.1; scripts in `p8/`)
Go/no-go and why; the seven rehearsal results; live counts; the undo recipe and backup path; the plain list of what
still stands between Sudima and a pay run that uses these hours, each item phrased as a decision or a button.
No names or employee numbers in committed files; no credentials. White-label: no "Odoo" in anything a user sees.
Commit messages end `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Never abm. Usage limit: leave the
server consistent, "Where I stopped", PAUSED.
