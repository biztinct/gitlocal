# WFSETUP P8 — Sudima clock-ins into attendance: rehearsal (report)

Agent: Opus 5.5, 24–25 Nov 2026 (times UTC). Handover `WFSETUP_P8_CLOCKINS_HANDOVER.md`. Scripts in `p8/`.
Engineering receipt: real technical names on purpose. No names, employee numbers or credentials in this file.

## Result: NO-GO — stopped after the rehearsal; live sudima untouched

Two of the handover's go criteria are not met, so step B (live) was **not** done:

1. **Only 90.3 % of the clock records attach to a person** (54,396 of 60,219; the bar is 95 %). 5,519 of the
   5,823 unattached records belong to **60 people whose badge ID on their record starts with a 0** ("012") while
   the clock sends the number without it ("12"). The clock matcher (`pb.clock.pairing._code_index`) compares
   exactly; the late/overtime rules already accept the form without zeros (`policy.py:289-296`), the matcher does
   not. Ignoring leading zeros the share would be **99.5 %** (59,915).
2. A blocker the criteria did not name, proven on the copy: **switching on while the rules are still a draft makes
   the rules refuse the same days later.** The old pairing writes a time-clock attendance row for every worked
   day; once the rules are confirmed and a past roster day is published, the rules calculation refuses any shift
   that overlaps an existing attendance row (`policy.py:375-379`, "Existing attendance overlaps this shift").
   On 40 published past roster days (19–23 Nov) with a clock row: **38 refused**; the same 40 without the clock
   rows: **38 calculated** (2 had no punches either way). The skip in `Pairing._pair_employee`
   (`policy.py:578-587`) only stops NEW pairing for people on an ACTIVE rule set; it never removes rows made before.

Live at the end (23:21): six send switches off, 71,063 records `ready`, 0 punches, 0 attendance. The only thing
done on live was a read-only `pg_dump` and one NOTE line in `/opt/deploy-notes.md`. P7's START/DONE window
(22:08–23:10) was respected: nothing was done on live in it.

**Owner fact received mid-run (acknowledged):** connector 1 ("Group B · supplied MDB validation") is not to be
switched on by us — the owner will tick it later. It was switched on in the first rehearsal attempt (copy only);
that attempt was stopped and the copy rebuilt with **connectors 4–8 only**. All numbers below are 4–8 only.

## Connector 1 (asked for by the owner)

| | Records |
|---|---|
| Connector 1 records | 10,844 (punch times 1 Sep – 12 Nov, all received 12 Nov 23:05) |
| Same row hash as a record from connectors 4–8 | **10,844** |
| Same person + same time as a record from 4–8 | **10,844** |
| New if the owner switches it on later | **0** — all would become "Already received" (`duplicate`); connector 1 is in the same source group (Group B) as 4, 6 and 8, so they share one collection machine and the punch ledger's duplicate key |

Connectors 4–8 have no duplicates among themselves: 60,219 records = 60,219 distinct (group, number, time).

## The seven rehearsal results (copy `zz_wfs_p8_20261125`, connectors 4–8)

Copy: restored from a fresh dump of live sudima as a TEMPLATE database (invisible to the live job runner), all
100 jobs and the mail servers off before anything else, served by an `odoo-bin shell` from the live addons dir.
Switch: studio method `pb.workforce.setup.clock_switch_on` as a throwaway attendance manager (5 × 0.0–0.14 s).

**1. Time, errors, states.** Connector job body (`_cron_process`, 500 per batch, one transaction each):
121 batches, **521 s**. Pairing job body (`_cron_run`, 5,000 per run): 13 runs, **1,234 s**. Total ≈ 29 min.
Server log: 0 ERROR, 0 Traceback. Final states: **60,219 posted, 0 duplicate, 0 review, 0 historical**
(connector 1's 10,844 left `ready`, as it must be).

**2. Punches.** 60,219 created: paired 50,169 · break taps 2,955 · double taps 1,272 · unknown number 5,823.
Attached to a person **54,396 = 90.33 %**. 663 distinct numbers, **85 unmatched** (60 = leading-zero badge IDs,
5,519 records; 25 = no such badge at all, 304 records). People: 578 with punches; **100 active people with no
punches** (40 once the leading-zero numbers match).

**3. Attendance.** **25,615 rows**, 578 people, 31 Aug (UTC; = 1 Sep local) – 23 Nov, all `pb_entry_source =
device`. Open (no check-out): 435 (each person's last day). Closed at 0 h because the check-out was missing
(D11): 626. **Absurd: > 16 h 325 (1.27 %), negative 0, overlapping 0** → under the 2 % bar (3.7 % if the 0 h
rows are counted too). Lengths: 20,320 rows are 12–15 h (Sudima's 12-hour shifts). Five anonymised long rows:
19.1 h (12:07 → 07:14 next day, 3 punches), 19.1 h (12:05 → 07:09), 20.0 h (00:35 → 20:37), 20.0 h (00:33 → 20:34),
18.9 h (12:25 → 07:16) — a missing tap joins two shifts inside the 21-hour span.

| Month (local) | Rows | People | Worked hours | > 16 h | 0 h (closed) |
|---|---|---|---|---|---|
| Sep 2026 | 2,181 | 99 | 25,413 | 21 | 51 |
| Oct 2026 | 13,824 | 561 | 160,717 | 210 | 376 |
| Nov 2026 (to 23rd) | 9,610 | 540 | 108,124 | 94 | 199 |

September covers only 99 people: connectors 5–8 keep history from 1 Oct; only connector 4 (and the owner's
connector 1, all duplicates) reach back to 1 Sep.

**4. Side effects** (every table fingerprinted before / after: rows, max id, max write date — `p8_tables.sh`):

| What | Change |
|---|---|
| Mail queued (`mail_mail`) | **0** (25 old failed mails, unchanged) |
| Notifications to people (`mail_notification`), activities, approval requests, overtime requests, timesheet weeks, timesheet lines | **0** |
| Chatter lines on the clocks (the switch, tracked field) | 5 |
| Chatter lines on the new attendance rows (stock "created" + tracking of check-out / extra hours) | **28,712** (on the attendance records only; nobody follows them) |
| Stock attendance "extra hours" lines (`hr_attendance_overtime_line`) | **24,406, all "approved", 263,332 h** — see below |
| Clock watcher attention items (`pb_clock_alert`, kind "check-out missing; closed") | 500 (its per-run cap; more on later runs) |
| Collection machines (`pb_clock_device`, one per source group) | 3 |
| People's last check-in / check-out (stored on the employee) | 578 people |
| `ir_config_parameter` `pb_clock.pair_runs` | 1 new |

The extra-hours lines: the attendance app's own overtime rule ("Employee Schedule Rule", expected hours from the
contract) expects **0.98 h a day on average** against 11.98 h worked, so it counts ~11 h of every day as extra
hours, auto-approved (`attendance_overtime_validation = no_validation`). They are not compensable as leave
(all `compensable_as_leave = false`) and payroll does not read them (payroll reads `hr.overtime.request`), but
they show on attendance screens as huge approved overtime.

Other jobs run once by hand on the copy (they run on their own on live): clock watcher, nightly re-check, rules
calculation, automatic check-out, absence detection, missing work entries, presence control, approval outbox +
escalation, Explorer build — all OK, nothing new beyond the 500 attention items (mail 0).

**5. Idempotence.** Both jobs again + five other jobs: **0 new rows** (process: 0 batches; pairing: read 0,
paired 0). Only job bookkeeping (`ir_cron_progress`) and the watcher's `last_seen` moved.

**6. Undo — proven.** `p8_undo.sh` (one transaction, 16 s; dry-run mode rolls back) from the baseline
`p8_baseline.sh` takes right before the switch. After it, every one of 1,426 tables has the pre-switch row count
and max id; received records (id, state, note, punch, write date, write user) and clocks are **byte-identical**
to the baseline (md5 equal). The only differences left are write dates on the employee and company rows from the
presence-control job I ran by hand (it runs hourly on live regardless) and job bookkeeping. The undo needs two
temporary indexes (made and dropped inside it): without them the foreign-key checks on the received records and
roster rows take minutes per thousand punches (ledger WS56).

**7. What a pay run needs (October, five people, rolled back).**

| Person | Oct attendance rows | Hours | Weeks of 29 Sep · 6 · 13 · 20 · 27 Oct (hours / days) | Approved weeks for an October run |
|---|---|---|---|---|
| P1 | 27 | 314.0 | 36.4/3 · 77.0/6 · 76.5/6 · 72.5/6 · 73.6/6 | 0 |
| P2 | 27 | 300.7 | 32.1/3 · 64.3/5 · 77.9/6 · 67.1/6 · 80.0/6 | 0 |
| P3 | 26 | 314.3 | 33.3/2 · 75.2/6 · 78.5/6 · 82.0/6 · 63.8/5 | 0 |
| P4 | 27 | 309.3 | 39.3/3 · 78.5/6 · 75.5/6 · 70.8/6 · 66.3/5 | 0 |
| P5 | 27 | 316.8 | 35.9/3 · 75.4/6 · 76.2/6 · 72.1/6 · 79.2/6 | 0 |

The chain is attendance → weekly timesheet (`pb.timesheet.packet`, built fine from the clock rows, overtime 0 on
every week) → approval (manager, then HR lead) → payslip input (`pb_timesheet_approval/models/hr_payslip.py`:
REGHRS / TOTHRS / WORKDAYS / OTHRS* / BONHRS, only for APPROVED weeks, only if the company reads approved
timesheets — sudima: yes). What is missing:

- **The pay scheme does not ask for any of those inputs.** Sudima's only scheme (7844) has 40 inputs, all from
  the pay data spreadsheet (`data_source = excel`: paid days, overtime hours, Sunday hours, …) and none of
  REGHRS / TOTHRS / WORKDAYS / OTHRS*. Approved weeks would change nothing on a payslip today.
- **No week is approved**, and none can be until somebody sends weeks in: ~580 people × 13 weeks.
- **Overtime from clock rows is always 0**: overtime in a week comes only from overtime requests, which only the
  rules calculation creates — and only for confirmed rules and published roster days, within the last 35 days
  (`_cron_policy_calculate`). There is no roster at all before 19 Nov, so September–October can never get
  rule-based overtime or lateness.
- **Lateness never reaches pay**: the rules' deduction hours (`pb_deduction_hours`) are read by nothing in payroll
  (only the setup screen's example).
- The rules are still a draft (1 rule set, draft; 27 people have none) and the 12,384 roster rows are drafts.

## Backup, scripts, undo recipe

- Read-only dump of live sudima taken before the rehearsal: `/odoo/backups/wfsetup-p8-20261125T0000Z/sudima-before-rehearsal.dump`
  (37.7 MB). Evidence (logs, fingerprints): `/tmp/wfsetup-p8-20261125T0000Z/` on the server (the baseline lists
  there name no person).
- Scripts (`docs/handovers/wfsetup/p8/`): `p8_prep.sh` (dump + hidden copy, jobs/mail off), `p8_run.sh` +
  `p8_rehearse.py` (phases user / switch / drain / jobs / conflict / chain; connector 1 refused by an assert),
  `p8_tables.sh` (every-table fingerprint), `p8_measure.sql`, `p8_baseline.sh`, `p8_undo.sh`.
- Undo recipe for a future live switch-on: (1) `p8_baseline.sh sudima <folder>` immediately before pressing the
  switch; (2) to undo: switch the clocks off on screen, wait one job cycle (5 min), `p8_undo.sh sudima <folder>
  --dry-run`, then without `--dry-run`; (3) fingerprint again and compare.
- Hidden copy, its file folder, the private conf and the throwaway login: dropped 23:21 (0 copies left).

## What still stands between Sudima and a pay run that uses these hours (plain)

1. **Decide the order: rules first, clock-ins second.** If clock-ins are switched on before the late and
   overtime rules are confirmed, the rules will later refuse every day that already has clock attendance (38 of
   40 in the test). Either confirm the rules (Workforce setup, step 4 → Confirm) and publish the roster first, or
   accept that the past days stay "plain clock hours" with no rules.
2. **Fix 60 people's numbers (or let us change the matching).** Their badge ID has a leading zero the clock does
   not send. Choice: type the clock's number into each person's "Clock number" (60 edits, heals the back-log by
   itself) — or ask us to make the clock matcher ignore leading zeros like the rules already do (a small code
   change). 25 more numbers (304 records) match nobody; someone at Sudima has to say who they are.
3. **Decide whether pay reads hours from the clocks at all.** Today the pay scheme takes paid days, overtime and
   Sunday hours from the uploaded pay spreadsheet only. To use clock hours, the scheme needs the "worked hours /
   overtime from approved timesheets" inputs added and wired into its formulas.
4. **Decide who approves ~7,500 weekly timesheets for Sep–Nov** (580 people × 13 weeks, manager then HR lead)
   — or whether past months stay on the spreadsheet and clock hours start from a chosen month.
5. **Decide what to do about September–October overtime and lateness**: no roster exists before 19 Nov, so the
   rules cannot work them out. Publish a roster for those weeks, or keep them on the spreadsheet.
6. **Lateness does not reach pay today**: the rules work out late minutes, but no pay input reads them. A
   decision (and a small build) if late minutes should cut pay.
7. **Decide about the attendance screens' own "extra hours"**: the built-in extra-hours rule expects about 1 hour
   a day from these contracts, so it would show ~263,000 auto-approved extra hours. Fix the contracts' working
   hours or switch that rule off before switching on (pay does not read these hours, but people will see them).
8. **Connector 1**: when the owner ticks it, nothing new arrives (all 10,844 records are already in 4–8).
9. **Then press "Switch clock-ins on"** in Workforce setup › step 6 for the five office PCs — about 30 minutes for
   the back-log to arrive.
