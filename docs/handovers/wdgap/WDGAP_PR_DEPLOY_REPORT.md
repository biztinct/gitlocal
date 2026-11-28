# WDGAP PR — deploy report (merge PR-A..D, live ×5, verify)

Merge-deploy-verify agent, 2026-11-14/15 (UTC 2026-11-14). Handover `WDGAP_PR_DEPLOY_HANDOVER.md`.
**Result: merged, pushed to `19.1` at `f2fc48beb`, LIVE on all five databases** (payobook,
payobook_template, p0clone, rize, sudima). ABM, pbf_preview and every other database untouched.
The PR-C gate allowed go-live: no database has ever released a bank file (0 left-out people).

## 1. Merge

Branch `wdgap-pr-merge` from `origin/19.1` @ `884f0e5ff`; merged `--no-ff` in the order
`wdgap-pra` (f47298aa8), `wdgap-prd` (32a243a0d), `wdgap-prc` (bdf1a734a), `wdgap-prb` (b4862dff7).

| Merge | Conflicts | Resolution |
|---|---|---|
| PR-A | `WDGAP_LEDGER.md` (QF-deploy row, QFM-2/3 vs PRA rows) | union, `origin/19.1`'s QF-deploy row kept |
| PR-D | ledger | union |
| PR-C | ledger; **`pb_me_portal/__manifest__.py`** version (PR-D 19.0.3.6.0 vs PR-C 19.0.3.5.4) | **19.0.3.6.1** (both changes; neither had shipped). The three `pb_me_portal` code files auto-merged; read: PR-C's `_ess_visible_domain` filters and PR-D's run label sit side by side, no overlap |
| PR-B | ledger | union. No `review_flags.py` conflict: PR-B adds its flag in its own override in `pb_loans`, not in `pb_payslip_review` |

### 1.1 Seam checks (§1.2)

| # | Seam | Result |
|---|---|---|
| 2a | Extra run takes NO loan instalment | Read: `pb_loans/models/loan_payroll.py:259` skips any kind `!= 'regular'`. New test `pb_loans/tests/test_wdgap_pr_merge_seams.py::test_2a` (Extra run → 0, nothing reserved, not flagged; the regular run after it still takes one; a second Extra run changes nothing): **pass** |
| 2b | Held payslip in an Extra run left out of bank file / release / send-out | New test `pb_pay_delivery/tests/test_wdgap_pr_merge_extra_hold.py` (PR-C's fixture with the run made an Extra run): left out of the file and its bytes, not marked paid on release, "held" in the send-out: **pass** |
| 2c | Loan flags and "on hold" flag on one run | **Seam bug found and fixed** (ledger PRM-1): when a loan pushed take-home below zero, PR-B rewrote the generic "zero or below" reason and dropped PR-C's " · Pay on hold". Fixed in `pb_loans/models/loan_review.py` (keep the tail after the first " · "), commit `cdd7ad4b1`; `pb_loans` stays 19.0.1.0.0 (never shipped). Test `test_2c` (held-only person: kind `hold`, loan note kept; held + loan-over-take-home person: both sentences): **pass** |
| 2d | Reserved names | Scan of `pb_loans`, `pb_demo` and every new/changed test (121 files) for component codes equal to any of the 40 function names: **0**. `pb_loans` ships no components. PR-A's golden conversion test (`test_wdgap_pra_dates` T7) passed on the merged tree |
| 2e | Bridges regular-only + loans regular-only + one-offs paid once | Full `pb_updates`, both bridges, `pb_loans` (T12 with a one-off) suites in the same run: no new failure |

**PR-D question — can an Extra run load a pay data file? YES** (ledger PRM-2). The Run payroll
pay-data step follows the scheme (does it ask for a file?), not the kind of run, and
`pb.payrun.wizard.attach_spreadsheet` has no kind check. So on a scheme that asks for a file:
(1) every row of the file becomes a payslip inside the Extra run — not only the people picked —
and (2) on an end-of-month scheme with a mid-month advance the advance would be taken off again.
Read from the code, not tried. Live exposure today: **rize 15 schemes ask for a pay data file**
(no mid-month schemes, so (2) cannot happen there; (1) can), sudima 1, payobook and p0clone 0.
Not redesigned (owner question 1).

### 1.2 Static gates (merged diff vs `origin/19.1`, 129 changed files)

py_compile 70 files: 0 failures. XML 16 files: 0 failures. PO gate (Odoo `PoFileReader`) 9 changed
`.po` files: 0 failures, 0 msgstr naming the vendor (re-run on the server's own reader for all 15
`.po` files of the 11 modules: all parse). Vendor name in added user-visible strings (`_()`,
`string=`, `help=`, placeholders, XML text): **0**; the other added lines naming it are imports,
`<odoo>` roots, comments and tool docstrings. Product name in `biz_*`: none changed.

### 1.3 Combined local tests (Mac; one database at a time; each dropped after)

| Run | Database | Result |
|---|---|---|
| A — full suites of the 10 touched modules + `pb_updates` (`/pb_hr_payroll_formula,/pb_formula_studio,/pb_loans,/pb_pay_delivery,/pb_payslip_review,/pb_me_portal,/pb_payruns,/pb_payrun_wizard,/pb_trip_payroll_bridge,/pb_workforce_payroll_bridge,/pb_updates`), `-i pb_loans` | copy of `upd_p6_t_tpl` | **1,900 tests, 19 failed, 6 errors — exactly the union of the four reports' baselines** (PR-A 12: TestRd49SyncCost ×2, TestRecordsR1OneTime 07b, TestSchemeCtxCurrency 04, TestJourneyView ×2, TestNetPayCandidates 01, TestOneMappingHome ×4, TestRunsrcPcBoardLane 14; PR-B/PR-D TestRunScreen ×5; PR-C/PR-D pb_me_portal ×5; PR-D trip bridge ×3 errors). |
| — the four phases' new tests within A | | **71 of 71 pass** (PR-A dates 10 + Studio 6; PR-B 17; PR-C 12; PR-D wizard 19 + bridges 3 + 4) **+ 3 of 3 merge seam tests** |
| B — R5 demo recompute on the MERGED tree | copy of `upd_p5e_pay` (demo world, 53 runs, 34,308 payslips) brought to `origin/19.1` first | latest REGULAR run of each of the 7 end-of-month demo schemes recomputed with `origin/19.1` code, then `-i pb_loans -u` the 10 touched modules, recomputed again (both rolled back): **4,129 payslips, 106,350 lines, 79,544 evaluated values — 0 differences; "Figures add up" true before and after on all 7.** (As PR-A noted, a plain recompute does not reproduce the generator's STORED lines on these demo runs — identical before and after, so not this change.) |
| B — `pb_demo` full suite on the merged demo world | same | 42 tests, 1 failed: `TestWorkforceCurrent.test_running_it_twice_changes_nothing`. **Baseline (run C, same copy on `origin/19.1` code): the same test fails with the same numbers** (`{'att': 855, 'shift': 1356, 'ot': 13} → {866, 1371, 14}`; the attendance seeder, date-dependent, not touched by any phase). PR-D's 5 demo Extra-run tests pass. |

Leftover builder databases `wdgap_pr*`: none existed (listed first). Run B was slowed overnight by
the Mac sleeping (recompute resumed under `caffeinate`).

Pushed: `884f0e5ff..f2fc48beb  19.1` (no force; `origin/19.1` had not moved — re-fetched before push).
Commits: 4 merges, `cdd7ad4b1` (seam fix + seam tests), `f2fc48beb` (handover copy + ledger), this report.

## 2. Read-only checks on live (before anything changed; re-run fresh the next morning, unchanged)

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| a. Open START in `/opt/deploy-notes.md` | none (last: Rize HRMS domain (Codex) DONE + VERIFIED 07:59 UTC, no app change) | | | | |
| b. Server | disk 29 GB free of 77; memory 3.8 GB, 1.8–2.0 GB available; backups folder 18 GB | | | | |
| c. Jobs total / active | 105 / 52 (job 156 OFF) | 93 / 34 | 93 / 42 | 93 / 85 | 93 / 84 |
| d. Stored formulas using TODAY/NOW/IFS/LEFT/RIGHT/MID/COUNT/YEAR/MONTH/DAY/DAYS/INT/DATE/DATEDIF/EDATE/EOMONTH + `(` | **0** of 773 | 0 of 0 | 0 of 0 | **0** of 495 | 0 of 15 |
| d. Component codes equal to a function name | none | none | none | none | none |
| e. Bank files / payment releases ever made | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| e. Payslips in runs with a prepared-not-released file | 0 | 0 | 0 | 0 | 0 |
| e. Done payslips with no paid date in runs with a released file | 0 | 0 | 0 | 0 | 0 |
| **PR-C GATE: finished payslips left out of the released file, 3 most recent released runs** | 0 (no released run) | 0 | 0 | **0** | **0** |
| f. Open top-up runs (draft/computed) | 0 (3 top-ups, all done) | 0 | 0 | 0 | 0 |
| g. Touched modules installed | all 10 + pb_demo | all 10 | all 10 | all 10 | all 10 |
| g. `pb_loans` dependencies installed → install | yes | yes | yes | yes | yes |

Before the deploy the 10 existing module trees on the server were byte-identical to `origin/19.1`.

## 3. Go live (risky tier)

Evidence on the server: `/tmp/wdgap-pr-20261114T203131Z/`; backups
`/odoo/backups/wdgap-pr-20261114T203131Z/` (payobook 81.0 MB, payobook_template 28.4,
p0clone 28.7, rize 43.5, sudima 28.8; each read back with `pg_restore -l`) + the 10 previous module
trees. Lock held by its own unit (`wdgappr-lock`) the whole window, released after DONE.
START 20:31, DONE 20:55 UTC. Staged = `git archive f2fc48beb` (11 trees hash-checked = commit).

**Rehearsals** (copies hidden from the live job runner while restoring; jobs and mail servers off;
real row counts asserted; recompute with OLD code, upgrade with the staged code first, recompute with
NEW code, both rolled back; copies dropped with `--force`):

| Copy | Upgrade | Recompute (old code vs new code) | Counts before → after |
|---|---|---|---|
| rize | EXIT 0 in 80 s; 0 Traceback | run 1591 "Rize Vietnam Payroll · October 2026" (draft — rize has no finished regular run), **63 people, 2,331 lines: identical before/after AND identical to the stored lines**; figures add up | identical (311 employees, 487 payslips, 16,179 lines, line total 29,559,077,500.24) |
| payobook | EXIT 0 in 86 s; 0 Traceback | run 335 "Payroll Manufacturing July 2026" (finished demo regular run), **40 people, 1,000 lines: identical before/after (0 differing payslips)**; figures add up | identical (34,322 payslips, 873,586 lines) |

On the payobook copy the recompute does NOT equal the stored demo lines — on all 40 payslips, with
the OLD code too (GROSS/NET/PIT, production bonus, overtime pay, the demo's own loan line: the demo
generator stages values a plain recompute re-reads differently, same as PR-A's R5 note). I read the
handover's "identical" rule as "the deploy must not change a figure", which old-vs-new proves; the
stored mismatch is not caused by this deploy. Each upgrade log carries the same 3 ERROR lines on every
database, all pre-existing and harmless: `odoo.schema: column "country"/"date_from"/"date_to" of
relation "payroll_analytics" contains null values` (2–3 old rows per database without them stop a
NOT NULL from being added; the upgrade continues). The go-live script allowed exactly those three and
stopped on anything else.

- **Downtime 400 s (6 min 40 s)**: stop 20:47:47, port up 20:54:27 UTC. Upgrades in order
  payobook_template 74 s, p0clone 72 s, sudima 71 s, rize 75 s, payobook 88 s — all EXIT 0.
- Per database: `-u` of the installed touched modules (pb_demo on payobook only) + `-i pb_loans`;
  signal row + bundle purge + `web.assets.version` = `wdgap-pr-20261114T203131Z`.
- Job repair: payobook_template's upgrade switched 4 jobs back on that were off (84 Time clocks: pair
  punches, 85 watch machines and days, 86 nightly re-check, 91 Attendance connectors: review received
  records) — switched off again at once. Job 156 on payobook: still OFF.
- Sites after start: payobook.com, p0clone, rize, sudima 200; payobook_template 200 (local).

### Versions before → after

| Module | Before | After | Where |
|---|---|---|---|
| pb_hr_payroll_formula | 19.0.1.165.0 | 19.0.1.166.0 | ×5 |
| pb_formula_studio | 19.0.1.211.0 | 19.0.1.212.0 | ×5 |
| pb_loans | — | 19.0.1.0.0 (new) | ×5 |
| pb_pay_delivery | 19.0.1.4.2 | 19.0.1.5.0 | ×5 |
| pb_payslip_review | 19.0.1.4.0 | 19.0.1.5.0 | ×5 |
| pb_me_portal | 19.0.3.5.3 | 19.0.3.6.1 | ×5 |
| pb_payruns | 19.0.3.5.0 | 19.0.3.6.0 | ×5 |
| pb_payrun_wizard | 19.0.1.43.0 | 19.0.1.44.0 | ×5 |
| pb_trip_payroll_bridge | 19.0.1.1.0 | 19.0.1.2.0 | ×5 |
| pb_workforce_payroll_bridge | 19.0.1.2.0 | 19.0.1.3.0 | ×5 |
| pb_demo | 19.0.1.14.1 | 19.0.1.15.0 | payobook only |

### Verification

- **Trees**: all 11 server trees byte-identical to `f2fc48beb`.
- **Versions**: manifest = `latest_version` for all 11 on every database where installed (0 mismatches).
- **Jobs**: id lists and active states identical before/after on all five (52/34/42/85/84); no new job.
- **Data**: employees, pay runs, payslips, payslip lines, line totals, components, active users and the
  mail queue identical before/after on all five. Only change: +1 approval route per company
  ("Loans and salary advances", Head of pay) — payobook +4, the others +1. 0 loans, 0 holds, 0 Extra runs.
- **Head of pay** (who would approve a loan): payobook — Mitchell Admin for 4 companies (this is the
  owner's own account, ash@biztinct.com); **"SG Company" has nobody and got no loan route**;
  payobook_template, p0clone, sudima — "Platform support (recovery account)"; rize — Ash Sohani.
- Server log since start: 0 ERROR/CRITICAL/Traceback (also after the checks below). One service process.

## 4. Check on the real system

The Chrome DevTools browser was in use by another session (its profile locked), so no private
window could be opened. Instead: **functional checks as the QA login by JSON-RPC from this Mac**
(the owner's browser untouched; password never printed or written to the repo) + a **look-only
browser walk** in the owner's signed-in browser (nothing saved).

As QA (`qa.test@payobook.com`, uid 6672, company Payobook Vietnam JSC):
1. **Formula Studio**: the function list contains DATEDIF; live check of
   `=DATEDIF(DATE(2020,2,29),DATE(2024,2,29),"Y")` on "Payobook Corporate Office — End-Month Payroll":
   valid; `=YEAR(TODAY())-2020`: refused with "TODAY() can't be used in a formula. A payslip must give
   the same answer whenever it is worked out. Use the pay period instead, for example DATE(PAYYEAR,
   PAYMONTH, ENDDAY)." Nothing saved. (The per-person preview was not repeated.)
2. **Loans**: board answers (empty); people search offers DEMO people; plan preview "4 instalments of
   2,250,000 ₫, from December 2026 to March 2027."; a DEMO loan for "DEMO HR Lead" created as a
   **draft**, its panel read, then deleted (0 loans left). **Not sent for approval**: the Head of pay
   on payobook is the owner's own account with a real email and payobook sends real mail.
3. **Run payroll**: kinds offered Regular / Top-up / Extra run. In the browser: the three choices
   with their one-line promises; picking Extra run renamed the run "Extra run — 15 Nov 2026" and
   showed "Who is this extra run for?" with the people list and the calm note. Closed without computing
   (0 Extra runs exist).
4. **Hold pay** on a payslip of the finished demo run 335 (Đặng Đức Trí, demo world): hold accepted;
   the run flag read "Net pay up 412% on June 2026 · Pay on hold"; Payslip review "On hold" count 1;
   Pay & deliver "1 person's pay is on hold" group with reason, by QA Test, amount; released from Pay &
   deliver → 0 held. Leaves two internal notes on that payslip's history and two audit rows (no email).
5. **QF leftovers**: sign out → the next call answers "Session expired"; sign in again → OK.
   Approving two DEMO leave requests and saving/deleting an Explorer view were NOT done.
6. Browser (owner's session, look-only): Loans board renders, quiet, console clean. **Small flaw:**
   its filter panel shows "Nothing matches “” here — Try the name of a filter, like , or a value…"
   (an empty no-match state; the board has no filters to offer). Run payroll: console clean.

Other four sites (cheap checks): login page 200 on all; the served page script on payobook, p0clone,
rize and sudima contains the flowchart date functions (PR-A), the Loans board (PR-B), "Release hold"
(PR-C) and "Extra run — only the people you pick" (PR-D).

## 5. Held / left off / follow-ups

- Nothing held back. Go-live allowed by the PR-C gate (0 / 0 on rize and sudima).
- Not done on purpose: loan "send for approval" on payobook (would email the owner); DEMO leave
  approvals and Explorer view save/delete (QF leftovers); a 390 px check.
- Follow-ups: Extra run + pay data file (PRM-2, owner question 1); Loans filter panel empty-state text;
  "SG Company" has no Head of pay and no loan route on payobook; `payroll_analytics` rows without
  country/dates (cause of the 3 known ERROR lines on every upgrade).

## 6. Questions for the owner (plain words)

1. **Extra runs and pay data files.** On Rize, 15 pay schemes ask for a pay data file. If someone starts
   an Extra run on one of them and loads the month's file, everybody in the file gets a payslip in that
   Extra run — not just the people picked. Should an Extra run skip the pay-data-file step? (Cost: a
   correction run could not use a spreadsheet.)
2. **Who approves loans on payobook.com?** It is your own account for four companies, so a demo loan
   sent for approval would email you. Should a demo person hold that seat instead? And "SG Company" has
   nobody — leave it?
3. The builders' open questions still stand (second person to lift a hold; "paid another way" button;
   cut an instalment when take-home goes below zero; loan pay item through scheme approval; run name on
   the payslip PDF). The "paid another way" one is not urgent: no customer has released a bank file yet.

## 7. New gotchas (ledger)

PRM-1 (two modules rewrite the one review-flag reason), PRM-2 (Extra run can load a pay data file),
PRM-3 (worktree guard refuses loops/vars with "gitlocal" paths — use scratchpad scripts), PRM-4
(every `-u` of the formula engine logs 3 harmless `payroll_analytics` NOT NULL ERROR lines — allow
exactly those in a go-live gate), PRM-5 (the Mac sleeps during long local runs — wrap them in
`caffeinate`; a background waiter can miss the end, poll with a bounded loop).
