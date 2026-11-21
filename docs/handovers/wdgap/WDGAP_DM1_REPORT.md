# WDGAP DM1 — demo contracts for the Contracts "Renew" screen (payobook only): report

Owner ruling DM1 (2026-11-18, answer to W3 deploy report §7 question 3): give the demo world a few
fixed-term / Permanent contracts so the Renew dialog's ready-filled boxes ("Kind of contract (Vietnam)",
"Payroll treatment (Vietnam)", W3-B RN1/RN3) can be shown. Before this, every contract on payobook was
open-ended with no payroll treatment (4,513 running + 12 ended + 9 draft), so the boxes read
"Open-ended / Not set".

**Result: LIVE on payobook only, 2026-11-17 22:51 UTC (Sydney 18 Nov). No module shipped, no upgrade,
no restart — the service stayed up.** Code `19.1` @ `3bb6142f9` (branch `wdgap-dm1`, fast-forward,
no force). Deploy notes START 22:50 / DONE 22:56 UTC.

## 1. What was added (what a demo viewer sees)

People › Contracts, company Payobook Vietnam JSC, search "DEMO". Six new people in Retail /
Stores - Central, each "Paid by" the demo Retail scheme (`DEMO_RETAIL_END`, through the scheme map,
like the other 902 Retail demo people), each with ONE running contract:

| Person (employee id) | Contract | Kind | Payroll treatment | Runs | Renew shows |
|---|---|---|---|---|---|
| DEMO Nguyễn Thu Hà (23440) | 15405 | Fixed-term | Permanent | 23 Dec 2025 → 22 Dec 2026 | Fixed-term / Permanent |
| DEMO Trần Minh Quân (23441) | 15406 | Fixed-term | Permanent | 7 Jan 2025 → 6 Jan 2027 | Fixed-term / Permanent |
| DEMO Lê Ngọc Lan (23442) | 15407 | Fixed-term | Probation | 30 Sep 2026 → 29 Dec 2026 | Fixed-term / Not set (a trial is never copied) |
| DEMO Phạm Quang Huy (23443) | 15408 | Fixed-term | (empty) | 12 Jan 2026 → 11 Jan 2027 | Fixed-term / Not set |
| DEMO Võ Bích Yến (23444) | 15409 | Seasonal | (empty) | 18 Aug 2026 → 17 Dec 2026 | Seasonal / Not set |
| DEMO Hoàng Đức Bảo (23445) | 15410 | Open-ended | Permanent | 1 Nov 2023 → (no end) | Open-ended / Permanent |

Wages 7.6M–21M VND; employee category "Permanent" (the seasonal one "Seasonal"); working schedule,
pay frequency and department copied from an existing Retail demo contract (read only). The four
fixed-term contracts end 30–55 days out (only the seasonal one, 30 days, is inside the "Ending
within 30 days" tab today). All start dates are in the past and outside the current month (the
joiner/leaver job reads only the current month).

**None of them has** a login, a work or private email address, an email on their contact, bank
details, a payslip, or a place in any pay run. All 12 records are on the demo register ("DEMO HR
programme data", `pb.demo.seed.register`, label "DEMO renewal contracts (WDGAP DM1)"; people first,
contracts after, so a removal would take contracts first). Owner rule: demo data on payobook is kept.

## 2. How (regenerable)

`docs/handovers/wdgap/dm1/dm1_demo_seed.py` — an `odoo-bin shell` script (the L1–L7 demo-seed
precedent), not a module change, so nothing had to be shipped or upgraded:

* ADD-ONLY and idempotent: people found by exact name in the demo company; an existing person is never
  written again; a contract is made only for a seed person who has none. A second run makes nothing.
* Refuses any database other than `payobook` (or a local `wdgap_dm1*` copy).
* Rails, all inside the script's own transaction (repeatable read, so other sessions do not count):
  payslips, pay runs, logins, every mail row, active jobs must be unchanged and the people/contract
  counts must move by exactly what it made; any new email/login/bank detail on a seed person — else
  rollback and stop. `DM1_DRY=1` = everything, then rollback.
* Employees and contracts are created with tracking/notify switched off (the pb_demo `_GEN_CTX`
  precedent); "Paid by" worked out for the new people only (`_pb_recompute_paid_by(employee_ids=…)`).

`docs/handovers/wdgap/dm1/dm1_qa_check.py` — look-only check as the QA login (uid 6672, no password),
rolled back: opens each contract the way the Contracts screen does, checks Renew is offered, reads the
Renew dialog's ready-filled values.

Why `is_demo = True` on the people: they are demo people like the 4,500 others. Consequence: a full
pb_demo regeneration (`generate_employees`, which cleans every demo person first) would remove them
too; re-run the seed afterwards.

## 3. Local test (database `wdgap_dm1_t`, dropped after)

Copy of the local demo world `upd_p5e_pay` (4,575 people, 34,322 payslips), its 45 out-of-date custom
modules upgraded to the 19.1 tree (EXIT 0, 0 ERROR), own conf/port 8981, jobs off.

| # | Case | Result |
|---|---|---|
| L1 | Dry run | 6 people + 6 contracts made, Renew values as the table, rolled back; table counts identical after |
| L2 | Run | committed; payslips, pay runs, logins, mails, to-dos, active jobs unchanged |
| L3 | Second run | "made 0 people, 0 contracts"; **every one of 1,322 tables identical** to after L2 |
| L4 | Renew dialog for each new contract (as an HR administrator, rolled back) | **6/6 as expected**, Renew offered on all |
| L5 | Existing data untouched (rows written since the run, per table, minus rows created) | only the demo register's summary line and the "Time Off" task total (standard recompute from the new people's holiday lines) |

Rows that standard employee creation adds (same on live): contact, resource, version, avatar
images (60), 48 time-off lines for the 2027 public holidays, 2 chatter notes per person (empty + the
stock "set up an onboarding plan" note — the other demo people carry the same), 6 pay-band positions.
No follower, no notification, no mail.

## 4. Live (payobook only)

* `/opt/deploy-notes.md` read: no open START (last: W3-C BG1 DONE 21:57). START 22:50, DONE 22:56 UTC.
* Scripts copied to `/tmp/dm1-20261117T2252Z/` (evidence there: before/after counts, table counts,
  shell logs). Dry run → identical to local, rolled back. Run → committed. Second run → made 0.

| Check | Before | After |
|---|---|---|
| Employees | 4,575 | 4,581 (+6) |
| Contracts | 4,534 | 4,540 (+6) |
| Payslips / payslip lines / pay runs | 34,322 / 873,586 / 53 | same |
| Logins | 453 | 453 |
| Mail queue | 0 outgoing; 1,668 sent, 857 cancelled, 610 failed; last id 11,045 | same |
| To-dos | 391 | 391 |
| Jobs | 111, 58 active (same ids) | same |
| Demo register rows | 1,534 | 1,546 (+12) |
| Contract kind / treatment | all open-ended, none | + the six rows of §1 |

All-table comparison on live: the same additions as locally (plus job-progress rows from live jobs,
not this work); existing rows written: the register summary and the Time Off task total only. The
new people: no email anywhere, no login, Paid by `DEMO_RETAIL_END`, no payslip, no follower, no
notification. Server log since 22:51: 0 ERROR / WARNING / Traceback. One service process throughout.

## 5. Look-only check on payobook.com

* As QA Test (uid 6672) in the server shell, rolled back: **6 of 6** contracts offer Renew and the
  dialog is ready-filled exactly as §1.
* Browser (owner's signed-in session, own tab): People › Contracts → search "DEMO Nguyễn Thu Hà" →
  the contract ("Ends in 35 days", Running) → Renew → dialog shows **Kind of contract (Vietnam) =
  Fixed-term** and **Payroll treatment (Vietnam) = Permanent** → Cancel. No vendor name on screen.
  Console: no errors (also after a reload). Counts identical afterwards — nothing saved. Tab closed.

## 6. Held / notes for the owner

* Nothing held.
* The fixed-term contracts end on real dates (17 Dec 2026 – 11 Jan 2027). After those dates the
  daily contract job marks them ended, like any contract; the Renew demo then still works from the
  ended contract (Renew is offered on ended contracts too), but "ending soon" stops showing them.
  Re-running the seed does not move dates (it never rewrites a person it already made).
* Pressing Create on a Renew in a demo makes a real (demo) contract for that person — expected.

## 7. Gotchas → ledger

| # | Gotcha |
|---|---|
| DM1-1 | A demo-world test copy (`upd_p5e_pay`) is far behind `19.1`: before using the 19.1 tree on it, `-u` every custom module whose `latest_version` differs from its manifest (45 here, ~4 min on 2.1 GB) — compare with a script, standard addons excluded. |
| DM1-2 | Creating `hr.employee` always adds (stock): a work contact, avatar images, future public-holiday time-off lines (and a recompute of the internal "Time Off" task), and an "onboarding plan" chatter note — even with `tracking_disable`. Count these as expected side rows in any add-only check. |
| DM1-3 | A "rows written since T" check must skip rows CREATED since T, and `awk '$0 >= "date"'` on a log also passes every undated continuation line (tracebacks of any age): find the first dated line and `tail -n +N` from there. |
| DM1-4 | Long SQL built in Python (1,400 tables `union all`) exceeds the argument limit when passed with `psql -c`: pipe it on stdin. |
