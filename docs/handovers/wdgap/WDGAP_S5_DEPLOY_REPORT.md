# WDGAP Step 5 — deploy report (merge S5-A, S5-B, S5-C + W2-D2; live ×5; verify)

Merge-deploy-verify agent, 2026-11-15/16 (UTC; one usage-limit stop and one session restart in
between, both before anything touched the live server). Handover `WDGAP_S5_DEPLOY_HANDOVER.md`
(method of `WDGAP_W2B_DEPLOY_HANDOVER.md` / `WDGAP_W2B_DEPLOY_REPORT.md`), plus the coordinator's
scope addition: merge `origin/wdgap-w2d2` (back pay, `pb_retro` only) after S5-C, one go-live for all
four branches.

**Result: merged, pushed to `19.1` at `d12b8d26b`, LIVE on all five databases** (payobook,
payobook_template, p0clone, rize, sudima); `pb_leave_setup`, `pb_time_pay`, `pb_shift_patterns`
installed ×5, `pb_retro` 19.0.1.1.0 (back pay) ×5. **431 s down.** ABM, pbf_preview,
recruit_connect and every other database untouched. Nothing held back.

## 1. Merge

Branch `wdgap-s5-merge` from `origin/19.1` @ `abc2259b6`; merged `--no-ff` in the order
`wdgap-s5a` (2daa86a7d), `wdgap-s5b` (9b3ed4379), `wdgap-s5c` (a8c34597f), `wdgap-w2d2` (4abd4d479).
**No conflict at all** (the four branches touch disjoint files; the ledger was edited by W2-D2 only).

Version raises the S5-B builder left for the merge (`83347992a`): `pb_hr_payroll_formula`
19.0.1.168.0 → **19.0.1.169.0**, `pb_source_atlas` 19.0.1.14.0 → **19.0.1.15.0**, `pb_mission`
19.0.1.13.1 → **19.0.1.14.0**. The builders raised their own: `pb_timeoff` → 19.0.1.12.0,
`pb_retro` → 19.0.1.1.0, three new modules 19.0.1.0.0.

Pushed `abc2259b6..d12b8d26b  19.1` (no force; `origin/19.1` had not moved — fetched just before).
Commits: 4 merges, `83347992a` (versions), `bba3ae61d` (S5 seams), `cfde936aa` (back-pay seam),
`d12b8d26b` (handover copies, ledger phase map, builders' gotcha rows), this report.

### 1.1 Seams (new tests on the merged tree, tag `wdgap_s5m`) — all pass

| # | Seam | Test | Result |
|---|---|---|---|
| a | S5-B's "Time off in lieu" kind made without knowing S5-A's fields | `pb_time_pay/tests/test_wdgap_s5_merge_seams.py::test_a` — approve 3 h as time off: the kind gets S5-A's defaults (not building up, no take-ahead, no expiry, not HR-only, not ready-made, not waiting for review); on the Kinds of leave screen as a tenant HR manager it is listed "Given by HR", "Hours", counted, switched on, pay decided; the drawer opens; the build-up engine and its daily run 400 days ahead post nothing and leave the allocation (days, hours, no end date) untouched | pass |
| b | S5-A "balances ignore days that ran out" + S5-B in-lieu hours | `test_b` — `_pb_expired_parts` answers nothing for the in-lieu kind today, +400 days and +10 years; the balance equals the hours given; a second grant adds up | pass |
| c | S5-C drafts vs S5-B overtime suggestions | `test_c` — a real pattern makes a DRAFT shift (06:00–14:00), moved onto the settled week the Close reads; punched 06:00–16:00: the suggestion is compared with the **working hours** (basis "hours"); after Publish it is compared with the **shift** (basis "shift", expected 8 h) | pass |
| d | One bundle, ⌘K, phone width | Local copy, own server `s5m.localhost:8693`, jobs off, window 500 px: the one `web.assets_web` bundle carries the Close section slot + "Time into pay", the Patterns lens, the Kinds of leave screen, the ⌘K rows `wf_leave_kinds`, `wf_leave_starters`, `wf_patterns`, `wf_patterns_make` (all registered in `pb_hub_palette`), the Settings › HR card, and the back-pay strings. Mission Control shows the PATTERNS and CLOSE tabs; Patterns opens on "No patterns yet" with the three ready shapes; Close shows "Time into pay" with its four zero counts. **Kinds of leave screen and the employee leave page at 500 px: no sideways scroll**; the employee page shows "PAID TIME OFF 10.0 days left". Console: no errors. | pass |
| e | (scope addition) One payslip carrying BOTH back pay (W2-D2) and confirmed late minutes (S5-B) | `pb_retro/tests/test_wdgap_s5_merge_backpay_late.py` — Aug–Oct 20M → 26M re-work approved; November payslip takes 40 confirmed late minutes through S5-B's input step and the back pay through the line producer: own late deduction 40,000, back-pay lines basic +18,000,000, insurance +1,890,000, employer insurance +3,150,000; take-home = own + 16,110,000; minutes and back pay both held by this payslip. **Recompute: identical lines, same take-home, nothing doubled**; a second regular payslip of the month takes neither. Totals: the payslip's own reading = the pay run's figures; gross − deductions = take-home. Finished → back pay paid, minutes stay with it. | pass |

### 1.2 Static gates (merged diff vs `origin/19.1`, 116 files)

py_compile 63 files: 0 failures. XML 17: 0. `node --check` on every changed JS: ok. PO gate
(`PoFileReader`) 8 changed `.po` locally, then the server's own reader on all 15 `.po` of the 8 staged
modules: all parse. Vendor name in added user-visible strings: **0** (flagged lines: an XML comment,
two `<odoo noupdate>` roots, two `.po` headers, a test grep). Product name in `biz_*`: none.
`starters.json` parses.

### 1.3 Combined local runs (Mac, ONE database `wdgap_s5m_t` = copy of `upd_p6_t_tpl`)

| Run | What | Result |
|---|---|---|
| A (before W2-D2) | `-i pb_loans,pb_fund_payments,pb_retro,pb_leave_setup,pb_time_pay,pb_shift_patterns` + `-u` 44 modules; full suites `/pb_leave_setup,/pb_time_pay,/pb_shift_patterns,/pb_timeoff,/pb_ess_workforce,/pb_me_team,/pb_close,/pb_mission,/pb_workforce_payroll_bridge,/pb_timesheet_approval,/pb_hr_workforce,/pb_attendance_flow,/pb_young_worker,/pb_hr_payroll_formula,/pb_source_atlas,/pb_schedule` | **1,500 tests, 11 failed, 12 errors.** 21 = the union of the recorded baselines (S5-A: TestLeaveRules ×6, TestTimeoff 03/05, TestP8Adversarial ack_week; S5-B: TestAttendanceFlow 04/05/07/13, TestWeekEntry 06, TestYoungWorker 09b, TestRd49SyncCost 02ab/02i, TestRecordsR1OneTime 07b, TestSchemeCtxCurrency 04; S5-C: TestP2Sidebar hero eyebrows). S5-B's TimesheetPacketCase s02 did not fail this time. **Two outside the baselines, both clock/calendar quirks, not Step 5** (ledger S5M-1): `TestT3bClockModel.test_t3b_1` (ran at 00:01 Vietnam time; passes on a re-run) and `TestP8Portal.test_the_week_badge…` (fails identically on `origin/19.1` with no S5 module — run `base1` on a fresh copy, Sunday evening UTC). New tests: S5-A 49, S5-B 63 (incl. seams a–c), S5-C 29 in the runner's count — all pass. |
| B (after W2-D2) | `-u pb_retro` (its 19.0.1.1.0 migration) + the seven suites the W2-D2 report names + `pb_time_pay`: `/pb_retro,/pb_hr_payroll_formula,/pb_payruns,/pb_payrun_wizard,/pb_loans,/pb_fund_payments,/pb_pay_delivery,/pb_time_pay` (cut off once by the session restart, re-run whole) | **1,216 tests, 9 failed, 0 errors — exactly W2-D2's recorded baseline** (TestRd49SyncCost ×2, TestRecordsR1OneTime 07b, TestSchemeCtxCurrency 04, TestRunScreen ×5 close week). `pb_retro` 60 incl. seam e — all pass. |

Leftover `wdgap_s5*` databases before starting: none. My copy, its filestore, the baseline copy and the
`origin/19.1` helper worktree were removed at the end.

## 2. Read-only checks on live (2026-11-15 ~20:00 UTC; notes and trees again 2026-11-16 07:50 and at prep)

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| Open START by anyone | none (last line: W2B NOTE 2026-11-15 10:57) | | | | |
| Server | disk 29 GB free of 77; memory 3.8 GB, 1.8 GB available; backups folder 18 GB; one service process; lock free | | | | |
| Jobs total / active | 105 / 52 (job 156 OFF) | 93 / 34 | 93 / 42 | 93 / 85 | 93 / 84 |
| The 8 module trees = `origin/19.1` | yes (5 existing; 3 new absent) | | | | |
| Dependencies of the 3 new modules installed | all ×3 | all ×3 | all ×3 | all ×3 | all ×3 |
| `hr_holidays_attendance` | installed | installed | installed | installed | installed |
| Pay items already coded LATEMIN / EARLYMIN | 0 | 0 | 0 | 0 | 0 |
| Leave kinds / allocations (with an end date; ran out) | 80 / 73 (67; 0) | 73 / 0 | 73 / 1 | 108 / 5 | 73 / 0 |
| Overtime requests / attendances / shifts | 24 / 3,487 / 2,640 | 0 / 0 / 0 | 0 / 5 / 5 | 0 / 4 / 0 | 0 / 0 / 0 |
| Pay runs / payslips / employees | 53 / 34,322 / 4,575 | 0 / 0 / 3 | 10 / 39 / 14 | 10 / 487 / 311 | 0 / 0 / 653 |

rize still has no finished pay run (10 draft trial runs).

## 3. Go live (risky tier)

Evidence on the server: `/tmp/wdgap-s5-20261116T082802Z/`; backups
`/odoo/backups/wdgap-s5-20261116T082802Z/` (payobook 81.3 MB, payobook_template 28.8, p0clone 29.2,
rize 43.9, sudima 30.7; each read back with `pg_restore -l`) + the 5 previous module trees. Lock held by
its own unit (`wdgaps5-lock`) the whole window, released after DONE. **START 08:28, DONE 08:52 UTC
(16 Nov).** Staged = `git archive d12b8d26b` (8 trees hash-checked = commit).

**Rehearsal — rize copy only (owner-shortened)**; copy hidden from the live job runner while
restoring; jobs and mail servers off; real row counts asserted; recompute with OLD code, upgrade with
the staged code, recompute with NEW code (rolled back); copy dropped with `--force`. Run three times
(≈4½ min each) because my own back-pay probe needed two fixes; the payslip proof was the same every
time.

| Item | Result |
|---|---|
| Upgrade | EXIT 0 in 80–83 s; only the 3 known `payroll_analytics` lines; 0 Traceback |
| Recompute old vs new | runs **2110** "TEST IN August 2026 — monthly Excel import" and **2115** "TEST IN August 2026 — application inputs without Excel" (scheme 7119): **54 payslips, 1,296 lines, 0 differing payslips**; "figures add up" true before and after; 1 payslip of 2115 refused identically by old and new code (pre-existing); as before, 2110's recompute ≠ its stored draft lines, identical old vs new |
| Pay run figures (W2-D2 §10 b) | per-payslip run totals identical old vs new on both runs |
| New things after install | 0 build-up rows, 0 service steps, 0 late decisions, 0 patterns; no kind building up, no in-lieu kind, no ready-made kind; 1 new job "Leave: add the days people have earned" |
| The new job and the Close read, run by hand on the copy | the build-up job answered `{}`; last week's Close read for 236 people: 0 suggestions, 2 late rows shown — **nothing written** (mails 913, to-dos 93, allocations 5, kinds 108 unchanged) |
| Back-pay route (W2-D2) | "Back pay for past months" published, one step Head of pay; 0 entries, 0 requests |
| W2-D2 §10 c (re-work → send → next month takes it → delete → back to waiting) | **Could not be shown on rize**: its trial runs work out to take-home 0 without their pay data file, so a re-work finds no difference ("Nobody in this re-work can be paid automatically"). Proven instead by W2-D2's B02/B09/B24 and merge seam e (§1.1). Nothing was changed on the copy beyond the rollback. |

- **Downtime 431 s (7 min 11 s)**: stop 08:43:48, port up 08:50:59 UTC. Upgrades in order
  payobook_template 74 s, p0clone 73 s, sudima 71 s, rize 77 s, payobook 115 s — all EXIT 0, only the 3
  known lines each.
- Per database: `-u pb_hr_payroll_formula,pb_mission,pb_retro,pb_source_atlas,pb_timeoff`
  + `-i pb_leave_setup,pb_time_pay,pb_shift_patterns`; signal row + bundle purge +
  `web.assets.version` = `wdgap-s5-20261116T082802Z`.
- Job repair: payobook_template's upgrade switched 4 jobs back on (84, 85, 86 time clocks, 91 attendance
  connectors) — switched off again at once. Job 156 on payobook: still OFF.

### Versions before → after (all five)

| Module | Before | After |
|---|---|---|
| pb_timeoff | 19.0.1.11.0 | 19.0.1.12.0 |
| pb_hr_payroll_formula | 19.0.1.168.0 | 19.0.1.169.0 |
| pb_source_atlas | 19.0.1.14.0 | 19.0.1.15.0 |
| pb_mission | 19.0.1.13.1 | 19.0.1.14.0 |
| pb_retro | 19.0.1.0.0 | 19.0.1.1.0 (migration: back-pay route) |
| pb_leave_setup | — | 19.0.1.0.0 (new) |
| pb_time_pay | — | 19.0.1.0.0 (new) |
| pb_shift_patterns | — | 19.0.1.0.0 (new) |

### Verification

- **Trees**: all 8 server trees byte-identical to `d12b8d26b`.
- **Versions**: manifest = `latest_version` for all 8 on all five (0 mismatches).
- **Jobs**: one new job per database, "Leave: add the days people have earned" (daily, active, first run
  2026-11-16 18:30 UTC; id 158 on payobook, 94 elsewhere) — quiet: no email, no to-do, nothing to do
  until HR sets a kind to build up (rehearsal proof above). No job changed or lost. Active 53/35/43/86/85.
- **Data** (before = after on all five): mails, to-dos, active users, employees, pay runs, payslips,
  lines, line totals, components, schemes, leave kinds, allocations (and allocated days), leave
  requests, overtime requests, attendances, shifts.
- **Silent install** ×5: every new table empty; no kind created, building up, ready-made or in-lieu; no
  allocation of a leave year; no overtime with a choice or from punches; no shift from a pattern.
- **Back pay** ×5: the route "Back pay for past months" is published as **one step, Head of pay** on
  every company that has a Head of pay seat (payobook 4 of 5 — **SG Company has nobody**, as for loans
  and fund payments; the other four sites 1 of 1); **0 back-pay entries, 0 requests waiting, 0
  re-works, 0 payslip lines marked back pay.** Head of pay: payobook — Mitchell Admin (companies 1, 2,
  6), Demo User (Payobook Vietnam JSC); payobook_template, p0clone, sudima — Platform support (recovery
  account); rize — Ash Sohani.
- Server log since start: 0 ERROR/CRITICAL/Traceback (also after the checks below). One service
  process. Sites 200 on all five. Deploy notes: START 08:28, DONE 08:52.

## 4. Check on the real system

My rules do not let me type a password into the live site, so (unlike earlier steps) the QA login was
not signed in over the network. Instead: **functional checks as QA Test (uid 6672, company Payobook
Vietnam JSC) inside the server's own shell, read-only, rolled back**, plus a **look-only walk in the
owner's signed-in browser** (nothing pressed that saves).

As QA (nothing created, applied, sent or changed):
1. **Kinds of leave**: board allowed; 80 kinds listed (e.g. "Accident leave · Not counted · Pay to decide ·
   Switched on"). **Ready-made kinds for Vietnam offered: 8** ("Annual leave — 12 days a year, built up
   each month · more with long service · paid", each with its legal source). **Not applied** (look only:
   applying makes switched-off kinds that the keep-demo-data rule would not let me remove).
2. **Employee leave page**: an employee with an allocation (Ưng Hoàng Long) sees "DEMO Carry-forward
   annual — 14 days".
3. **Patterns**: answers empty (0 patterns, 0 people, 0 drafts), can edit.
4. **Weekly Close** (Assembly Line A, week of 9 Nov): "Time into pay" present — 0 suggestions, 0 late
   rows, grace 15/15 minutes, no file-paid scheme.
5. **Overtime desk**: cards carry the choice ("Paid" on the three looked at).
6. **A finished demo payslip print still renders** (payslip 144281, Bùi Hữu Khang, 296 KB HTML).
   White-label note: the print's web preview has the framework's default page title "Odoo Report"
   (the browser tab, not the payslip itself) — pre-existing, not from this step (W2-D2 saw it too).
7. Back pay: 0 entries, 0 re-works.

Browser (owner's session, look-only, window ~500 px): Kinds of leave renders (set-up check "80 kinds
that are switched on have no pay decision yet", glance, steps, list); Mission Control → PATTERNS "No
patterns yet" with the ready shapes; CLOSE → "Time into pay" section; console: no errors (after a
reload).

Other four sites (cheap checks): login page 200 on all five (payobook_template via the server's own
address); the served script bundle on all five contains "Kinds of leave", "Time into pay", "Make shifts
from a pattern" and "Pay the difference in the next pay run".

## 5. Held / left off / follow-ups

- Nothing held back.
- Not done on purpose: applying the ready-made Vietnam kinds on payobook (would leave switched-off kinds
  behind — look only); accepting overtime, confirming minutes, making a pattern or a re-work on live; a
  true 390 px check (500 px in the shared window); Vietnamese / Indonesian screens (PO gate only).
- The rize back-pay walk (W2-D2 §10 c) — not possible on rize's trial data (above).
- White-label follow-up: the printed payslip's web preview title "Odoo Report" (framework default).
- First customer view of Kinds of leave will be amber: every kind "Pay to decide" (80 on payobook, 108 on
  rize, 73 elsewhere) — owner question 1 below.

## 6. Questions for the owner (plain words) — all four builders, carried forward

**Kinds of leave (S5-A)**
1. **"Pay not decided" will show amber on every site at first.** No kind of leave has been marked paid /
   unpaid / who pays yet — 80 on payobook.com, 108 on Rize, 73 on the others (many came with the system for
   other countries). Leave it so HR sees the truth, hide kinds for countries the company does not work
   in, or do a one-off clean-up per customer?
2. **India's ready-made leave is a placeholder** (each state sets its own: earned 15, casual 7, sick 7).
   Offer it now with that warning (as built), or hide India until the main states are checked?
3. **Leave year = January to December** for leave that builds up. Does any customer need another year
   (for example April–March in India)?
4. **Singapore sick leave**: the law gives 5, 8, 11 then 14 days in months 3–6; the ready-made kind gives
   14 days after 6 months and says "add the earlier days by hand". Good enough as a starting point?

**Time into pay (S5-B)**
5. **Payslips made from a pay data file** (Rize pays 15 schemes that way): approved overtime and
   confirmed late minutes do not go into those payslips by themselves — the weekly Close lists them for
   the team to type into the file. A real fix would let those payslips take them from Payobook only for
   pay items the file has no column for, paid once. It touches the file import (another money path),
   so it needs its own step and rehearsal. Build it, or keep taking everything from the file?
6. **How late minutes count**: 20 minutes late with 15 minutes' grace counts as 20 today. The other common
   rule counts only the 5 past the grace. Which one?
7. **Rounding suggested overtime**: rounded down to the quarter hour; nothing under 10 minutes is
   suggested. Keep, or round to the half / full hour?
8. **"Give time off" in the Approvals inbox and on My team**: today managers choose on the Overtime desk,
   the weekly Close and the overtime form; the inbox and My team only show the choice. Add it there (a
   small change in the inbox)?
9. **Who accepts suggested overtime**: whoever accepts it becomes the sender, and the approval rules then
   stop that same person approving it. Should a line manager be able to accept AND approve in one go
   (needs an exception on the overtime route), or keep it as it is?
10. **Should employees see their own confirmed late minutes on My Payobook?** Not built.

**Shift patterns (S5-C)**
11. **Public holidays**: a pattern leaves public holidays empty unless "Work on public holidays" is on
    (a 24-hour plant would switch it on). Is "empty on holidays" the right default?
12. **Overtime limit**: like Copy week, someone already at 90% of their monthly overtime limit gets no new
    rota shifts that month (and is listed). Should a rota ignore that warning, since rota shifts are
    normal hours?

**Back pay (W2-D2)**
13. **Someone who owes money and cannot pay it all this month**: whole months wait for the next pay run
    (never part of a month). Fine, or should part of a month be taken?
14. **Back pay for someone who has left**: not paid automatically today (the screen says so; the team can
    use a one-off in Updates or the final settlement). Put it into their final payslip instead?
15. **Approval**: one sign-off by the Head of pay, like loans and fund payments. Keep? (On payobook.com
    "SG Company" has no Head of pay, so it has no back-pay approval route — same as loans and fund
    payments there.)

## 7. New gotchas (ledger)

S5M-1 (two clock/calendar-dependent `pb_ess_workforce` tests), S5M-2 (rize's trial pay runs work out
to take-home 0 without their pay data file — a back-pay or any "difference" walk cannot be shown on a
rize copy; use the demo world or a test), S5M-3 (`hr.payslip.run` has no `company_id` on rize — read
the company from its payslips), S5M-4 (live checks as QA without a password: run them as uid 6672 in
`odoo-bin shell`, read-only, rolled back; browser part look-only in the owner's session), S5M-5 (the
printed payslip's web preview title is the framework default "Odoo Report" — white-label gap, follow-up).
Also added from the builders' reports: S5A-1..7, S5B-1..5, S5C-1..5.
