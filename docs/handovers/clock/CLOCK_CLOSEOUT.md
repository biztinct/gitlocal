# CLOCK programme — closeout

Programme opened 2026-11-05, phases CLOCK-1, CLOCK-2 and CLOCK-3 delivered the
same day and live on payobook, payobook_template, p0clone and rize. The new
tenant `sudima` was made from the template after CLOCK-2, so it runs CLOCK-2
(pb_clock 19.0.1.1.0) until the coordinator upgrades it to CLOCK-3.

## What it does for you (plain words)

**Punches from fingerprint, face and card machines become paid hours, with no
re-typing, and Payobook tells you when something needs a person.**

1. **Machines send their punches straight to Payobook.** HR types the
   workspace address into the machine (Menu › Comm. › Cloud Server, "Enable
   domain name" ON, port 443). Within a minute the machine appears under
   "1 machine is asking to connect"; a manager presses Allow and picks the
   first day to pay from. The machine's clock is checked from its own punches
   and set when it drifts.
2. **Or upload a punch file** (Excel, CSV, the machine's own file or the
   attendance program's daily sheet) — the permanent fallback.
3. **Punches become work days by themselves**: first punch in, last punch out,
   night shifts kept as one day, double taps counted once, a forgotten
   check-out never blocks the next days. Days a person decided about are never
   changed; those punches wait "on hold" with the reason.
4. **The days flow into the Week Grid, the weekly timesheet and the pay run**
   like any other hours, and can only be changed with a correction.
5. **Trust (CLOCK-3)**: a note at the top of Time › Time clocks says, in one
   sentence each, what needs a person — a machine that went quiet, no punches
   on a working day, a clock that is off, a machine waiting to be let in, a
   day missing its check-out, requests that failed, a plain connection, punches
   on hold, a pile waiting to be paired. The same shows above the Time tabs, on
   the Integrations page, on Home, and in an 08:00 email to attendance
   managers (their language; never to employees; one switch per company).
6. **Every night at 02:30** the last 35 days are rebuilt from the punches and
   the screen says how many days that changed.
7. **A big history** shows its progress ("about 25 minutes left") and finishes
   in minutes.
8. **Learn** covers the new tab, and **payobook.com** has a demo machine with
   two weeks of punches for 24 demo people to show to prospects.

Setup day: follow [`SETUP_DAY.md`](SETUP_DAY.md) (English + Vietnamese).

## Before setup day at Sudima (things only you can do)

1. **Upgrade `sudima` to CLOCK-3** (coordinator): `-u pb_clock,pb_time_hub,
   pb_integrations,pb_dashboard,pb_learn`, then switch the two new jobs on
   ("Time clocks: watch machines and days", "Time clocks: nightly re-check")
   — the deploy script leaves new jobs off (ledger G3).
2. **Check the email switch** on Sudima's company (Time clocks › settings,
   "Email the attendance managers") — on by default; the managers need an
   email address on their user.
3. **Certificates**: sudima.payobook.com has its own certificate to
   2027-02-03 (made with the tenant). The **wildcard `*.payobook.com` still
   expires 2026-11-12** (manual DNS renewal) — every tenant without its own
   certificate depends on it. Pick the renewal day.
4. **Ask the client** (you talk to Sashi and the supplier):
   - a photo of the "Cloud Server" menu on each model, especially the older
     ZMM100 "New office" machine — does it have "Enable domain name"?
   - can each machine reach the internet on port 443 (firewall)?
   - which people are attendance managers (they get the emails)?
   - the first day to pay from for each machine.

## Known limits

| Limit | What it means | Way out |
|---|---|---|
| A machine that only takes a number address | It cannot tell Payobook which company it belongs to | Option A: a dedicated port on the server mapped to `sudima` (one nginx block, ~0.5 day). Option B: a block per machine IP (fragile if the factory's address changes). Needs the client's photo first. |
| The attendance program's `.mdb` database | Not read | Upload its daily sheet or the machine's own file (works today) |
| Machines that cannot push at all | Need someone to upload files | CLOCK-5 Windows Bridge |
| Late minutes | Hours are paid; minutes late are not yet a payslip input | CLOCK-4 |
| Someone with an old open day (a forgotten check-out typed by hand, never closed) | Their new still-running day waits "on hold: an earlier day has no check-out yet" — the system only closes days the machines made | Close the old day with a correction; a later phase could list such people in the strip |
| Doors from Home / Integrations | Open the Time clocks tab, not the exact block | The note at the top has the per-block doors |
| Time clocks in Learn | A step in Time's lesson and a walkthrough, no lesson of its own | A short lesson with a practice copy when the screen settles |

## CLOCK-4 / CLOCK-5 backlog (sizes are rough)

| Item | Size |
|---|---|
| CLOCK-4: late minutes and early leave as payslip inputs (from the shift + the paired day), with the approval the overtime desk already has | 1 phase (~1 day) |
| CLOCK-4: number-address machines — dedicated port mapped to one tenant | 0.5 day, after the client's photo |
| CLOCK-4: "mute for a day" and a bulk fix on the strip; doors that open the exact block from Home / Integrations | 0.5 day |
| CLOCK-4: list people blocked by an old open day in the strip | 0.25 day |
| CLOCK-5: Windows Bridge for machines that cannot push (reads the machine over the LAN, sends to the same ledger) | 2–3 days + an install on the client PC |
| CLOCK-5: `.mdb` reader for the attendance program | 1 day (only if the Bridge is not chosen) |

## The record

- Phases: [`CLOCK_P1_REPORT.md`](CLOCK_P1_REPORT.md),
  [`CLOCK_P2_REPORT.md`](CLOCK_P2_REPORT.md),
  [`CLOCK_P3_REPORT.md`](CLOCK_P3_REPORT.md); handovers `CLOCK_P1.md`–`CLOCK_P3.md`.
- Conventions and gotchas: [`CLOCK_LEDGER.md`](CLOCK_LEDGER.md) (G1–G23).
- Shots: `shots/` (CLOCK-1 `00`–`13`, CLOCK-2 `p2-*`, CLOCK-3 `p3-*`).
- Live versions: pb_clock 19.0.1.2.1, pb_time_hub 19.0.1.5.0, pb_integrations
  19.0.1.16.0, pb_dashboard 19.0.2.2.8, pb_learn 19.0.20.8.8, pb_demo
  19.0.1.14.1 (payobook), pb_hr_workforce 19.0.4.24.0.
