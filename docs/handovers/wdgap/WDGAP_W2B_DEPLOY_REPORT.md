# WDGAP W2B — deploy report (merge W2-F + W2-D1; live ×5; verify; demo data tasks)

Merge-deploy-verify agent, 2026-11-15 (UTC). Handover `WDGAP_W2B_DEPLOY_HANDOVER.md` (method of
`WDGAP_W2_DEPLOY_HANDOVER.md` / `WDGAP_W2_DEPLOY_REPORT.md`), plus the owner's mid-task update that
shortened the rehearsal (below).
**Result: merged, pushed to `19.1` at `7d80ddced`, LIVE on all five databases** (payobook,
payobook_template, p0clone, rize, sudima); `pb_retro` installed on all five. **387 s down.** ABM,
pbf_preview and every other database untouched. D-2 done on payobook; **D-1 held** (owner question 1).

## 1. Merge

Branch `wdgap-w2b-merge` from `origin/19.1` @ `7f0fa3aad`; merged `--no-ff` in the order `wdgap-w2f`
(27b28cc1f), `wdgap-w2d1` (d515295bf). **No conflict at all** (not even the ledger: the two branches
added rows in different places; no `.po` header clash). Code is disjoint: W2-F touches
`pb_hr_payroll_formula`, `pb_payrun_wizard`, `pb_payslip_review`, `pb_fund_payments`,
`pb_formula_studio`; W2-D1 is the new module `pb_retro`.

Pushed: `7f0fa3aad..7d80ddced  19.1` (no force; re-fetched just before, `origin/19.1` had not moved).
Commits: 2 merges, `12ea2314f` (seam test), `7d80ddced` (handover copy + ledger phase map), this report.

### 1.1 Seams

| # | Seam | Result |
|---|---|---|
| a | `pb_retro` re-working a month that holds an Extra-run payslip whose advance was NOT taken again (W2-F F-1) | New test `pb_retro/tests/test_wdgap_w2b_merge_seams.py` (tag `wdgap_w2bm`): scheme with basic + advance input; September regular payslip took ₫3,000,000 advance; Extra-run payslip fed 0 with `pb_advance_taken_in_id` = the regular payslip; a ₫44M → ₫50M rise from 1 Sep. Re-work of September: the Extra payslip is `skipped` / "Extra run", no lines; the regular payslip `changed` with BASICPAY +6,000,000, SIEMP +630,000, NETPAY +5,370,000 and **no advance line** (would-be take-home = 50M × 0.895 − 3M); SQL spy: only `pb_retro_*` tables written; payroll stamps, both payslips' stored inputs and the Extra payslip's advance record unchanged. **Pass.** |
| b | `pb_retro` board/palette and W2-F's Studio Health-tab row in one bundle | Local copy after run A, server on `127.0.0.1:8673`, Claude in Chrome: the one `web.assets_web` bundle carries the re-work board (`pb_retro_board` ×2, "Past-month re-work" ×2) and the Studio tax-year row (12 hits) and `offer_calc`; Past-month re-work board renders (empty hero, "Start a re-work"); Formula Studio opens; **console: no errors** on either after a reload. (The local template has no scheme, so the Health tab itself was not drawn locally; it was read on live, §5.) |

### 1.2 Static gates (merged diff vs `origin/19.1`, 58 files)

py_compile 31 files: 0 failures. XML 6: 0 failures. `node --check` on the 4 changed JS files: ok. PO
gate (`PoFileReader`) 7 changed `.po`: 0 failures, 0 msgstr naming the vendor; re-run on the server's
own reader for the 9 `.po` files of the 6 staged modules: all parse. Vendor name in added user-visible
strings: **0** (the three lines flagged are two `.po` headers and an `<odoo noupdate="1">` root).
Product name in `biz_*`: none.

### 1.3 Combined local run (Mac; one database; dropped after)

| Run | Database | Result |
|---|---|---|
| A — full suites `/pb_hr_payroll_formula,/pb_payrun_wizard,/pb_payslip_review,/pb_fund_payments,/pb_formula_studio,/pb_loans,/pb_payroll_templates,/pb_retro`, `-i pb_loans,pb_fund_payments,pb_retro` + `-u` the 33 modules behind | copy of `upd_p6_t_tpl` (`wdgap_w2bm_t`) | **1,587 tests, 12 failed, 1 error — exactly W2-F's recorded baseline of 13** (TestRd49SyncCost ×2, TestRecordsR1OneTime 07b, TestSchemeCtxCurrency 04, TestJourneyView ×2, TestNetPayCandidates 01, TestOneMappingHome ×4 incl. the error, TestRunsrcPcBoardLane 14, TestRunInputReview monthly duplicate label); W2-D1's baseline (the first 12) is a subset. Per module: formula engine 835, Studio 627, wizard 155, payroll templates 105, loans 42, fund payments 36, `pb_retro` 26, payslip review 11. |
| — the new tests within A | | W2-F (A1–A7, F2.1–F2.4, F3.1–F3.3, F4.1–F4.4, F5.1–F5.2), W2-D1 (T1–T16) and merge seam a: **all pass** |

Leftover builder databases `wdgap_w2f_*` / `wdgap_w2d1_*`: none existed (listed first). Run time ≈ 25 min.

## 2. Read-only checks on live (before anything changed, 08:3x UTC; notes and trees again at 09:01)

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| Open START by anyone in `/opt/deploy-notes.md` | none (last: W2 NOTE 06:50, rize 7119 → April) | | | | |
| Server | disk 29 GB free of 77; memory 3.8 GB, 1.5 GB available; backups folder 18 GB; one service process; deploy lock free | | | | |
| Jobs total / active | 105 / 52 (job 156 OFF) | 93 / 34 | 93 / 42 | 93 / 85 | 93 / 84 |
| The 6 module trees on the server = `origin/19.1` | yes (5 existing; `pb_retro` absent) | | | | |
| **a.** Fund route still the seeded two-step and never used? | **yes ×4** (Your Company, Payobook, Payobook Vietnam JSC, Payobook Singapore); SG Company has **no route** | yes | yes | yes | yes |
| a. fund payments / payees | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| **b.** rize scheme 7119 `RIZE_IN_FOCUSED_2026` tax year | | | | **'4' (April)** | |
| **c.** `pb_retro` dependencies installed → install | all → yes | all → yes | all → yes | all → yes | all → yes |
| Pay runs / payslips / employees | 53 / 34,322 / 4,575 | 0 / 0 / 3 | 10 / 39 / 14 | 10 / 487 / 311 | 0 / 0 / 653 |
| Extra runs | 0 | 0 | 0 | 0 | 0 |

rize has **no finished pay run** (all 10 are draft trial runs).

## 3. Go live (risky tier)

Evidence on the server: `/tmp/wdgap-w2b-20261115T090128Z/`; backups
`/odoo/backups/wdgap-w2b-20261115T090128Z/` (payobook 81.2 MB, payobook_template 28.6, p0clone 29.0,
rize 42.2, sudima 29.0; each read back with `pg_restore -l`) + the 5 previous module trees. Lock held by its
own unit (`wdgapw2b-lock`) the whole window, released after DONE. START 09:01, DONE 09:25 UTC.
Staged = `git archive 7d80ddced` (6 trees hash-checked = commit).

**Rehearsal — the owner-shortened one** (coordinator message mid-task: rize and sudima are production but
not yet in real use, payobook is demo): **rize copy only, no payobook sample.** Copy hidden from the live
job runner while restoring; jobs and mail servers off; real row counts asserted; recompute with OLD code,
upgrade with the staged code, recompute with NEW code, both rolled back; copy dropped with `--force`.
**Took 3 min 21 s.**

| Copy | Upgrade | Recompute old vs new | Counts before → after |
|---|---|---|---|
| rize | EXIT 0 in 74 s; only the 3 known `payroll_analytics` lines; 0 Traceback; 0 new jobs; `pb_retro` 0 rows; fund route "changed" → one step Head of pay (Ash Sohani); 7119 still April | rize has no finished run, so the most recent regular run that actually computes was taken (W2M-4): **run 2110 "TEST IN August 2026 — monthly Excel import" (scheme 7119, the April tax year), 27 payslips, 648 lines, 0 refused — 0 differing payslips**; "figures add up" true before and after. As on earlier rize runs, the recompute does not equal the stored lines of this draft trial run — identical old vs new, so not this change. | identical (311 employees, 487 payslips, 16,179 lines, line total 29,559,077,500.24, 93 jobs, 897 mails) |

One false start, caught by the guard: the first restore ran as the login user and could not read the dump
("Permission denied"); the script's empty-copy check stopped it before any upgrade (ledger W2BM-1). Fixed
to `sudo cat`, rerun clean.

- **Downtime 387 s (6 min 27 s)**: stop 09:06:59, port up 09:13:26 UTC. Upgrades in order
  payobook_template 71 s, p0clone 71 s, sudima 72 s, rize 74 s, payobook 90 s — all EXIT 0, only the 3
  known lines each.
- Per database: `-u pb_formula_studio,pb_fund_payments,pb_hr_payroll_formula,pb_payrun_wizard,pb_payslip_review`
  + `-i pb_retro`; signal row + bundle purge + `web.assets.version` = `wdgap-w2b-20261115T090128Z`.
- Job repair: payobook_template's upgrade switched 4 jobs back on (84, 85, 86 time clocks, 91 attendance
  connectors) — switched off again at once. Job 156 on payobook: still OFF.

### Versions before → after (all five)

| Module | Before | After |
|---|---|---|
| pb_hr_payroll_formula | 19.0.1.167.0 | 19.0.1.168.0 |
| pb_payrun_wizard | 19.0.1.45.0 | 19.0.1.46.0 |
| pb_payslip_review | 19.0.1.5.0 | 19.0.1.6.0 |
| pb_fund_payments | 19.0.1.0.0 | 19.0.1.1.0 (route migration) |
| pb_formula_studio | 19.0.1.213.0 | 19.0.1.214.0 |
| pb_retro | — | 19.0.1.0.0 (new) |

### Verification

- **Trees**: all 6 server trees byte-identical to `7d80ddced`.
- **Versions**: manifest = `latest_version` for all 6 on all five databases (0 mismatches).
- **Jobs**: id lists and active states identical before/after on all five (52/34/42/85/84); no new job.
- **Data**: mails queued, active users, employees, pay runs, payslips, lines, line totals, components,
  schemes, loans, route bindings and seats identical before/after on all five. 0 re-works, 0 advance
  stamps, 0 fund payments.
- **§3a — what each fund route became** (migration log line per company): every route that existed was
  "changed" → a new published revision with ONE step, Head of pay (the old two-step kept as "superseded").
  payobook: Your Company, Payobook, Payobook Vietnam JSC, Payobook Singapore — Head of pay = **Mitchell
  Admin (the owner's own account)**; **SG Company — "no route"** (it never had one; nobody seated).
  payobook_template, p0clone, sudima — Head of pay = Platform support (recovery account). rize — Ash
  Sohani. **Nobody was newly seated anywhere** (every company with a route already had a Head of pay).
- **§3b** rize 7119 tax year = April after the upgrade (and every other scheme unchanged: payobook 26 ×
  January, rize 18 × January + 1 × April, sudima 1 × January).
- **§3c** `pb_retro` installed ×5: no rows, no job, no email queued.
- Server log since start: 0 ERROR/CRITICAL/Traceback (also after the checks below). One service process.
  Sites 200 (payobook_template via local Host header).

## 4. Demo-only data tasks on `payobook`

### D-2 — "Loan repayments go into" on the 12 demo schemes: DONE

Through the Loans set-up's own method (`pb.loans.set_loan_item`) as QA Test, in an odoo shell; dry run
(rolled back) first, then committed; cache signal row after. Each scheme has exactly one loan input.

| Scheme ids | Before | After |
|---|---|---|
| 42–53 (Retail, Manufacturing, Logistics, Corporate Office, Information Technology, Construction — End-Month and Mid-Month each) | (empty) | `INLOAN` "Loan Installment (in)" — rules 2175, 2228, 2284, 2335, 2389, 2441, 2496, 2548, 2603, 2656, 2712, 2762 |

Not touched: "VPTQ End Cycle", "VPTQ Mid Cycle", "Payobook Scale Demo — 250 Columns" (not demo schemes
of the 12; no loan input). Nothing recomputed; mail queue unchanged (3,135). With no loan on payobook the
loan step feeds exactly what it fed before (PR-B byte-identity rule), so demo pay runs are unaffected.
**Suggest on Payobook Vietnam JSC, as QA:** before = 6 funds (Health Insurance, **Loan Repayment**,
Personal Income Tax, Social Insurance, Trade Union Fund, Unemployment Insurance — Mid-Month Advance was
already gone with W2-F, no "untick" notes); after = **5, no Loan Repayment.** Undo recorded in
`/opt/deploy-notes.md` (set the field empty on 42–53 + signal row).

### D-1 — approval seats for loans and fund payments: NOT DONE (held, owner question 1)

Both routes now ask one seat: **Head of pay**. Read, and a rolled-back dry run of the product's own seat
method (`pb.approval.matrix.set_responsibility`, as QA Test) with the demo login that holds the comparable
pay seat (Payroll manager) in Payobook Vietnam JSC, "Demo User" (demo@payobook.com):

| Company | Head of pay now | Dry run with Demo User |
|---|---|---|
| Payobook Vietnam JSC | Mitchell Admin | accepted — **but on payobook the Head of pay also approves "pay awards" and "pay bands"** (published routes `awards` and `bands` in all four companies ask the same seat), so moving it would change who approves those too — the handover forbids that |
| Your Company, Payobook, Payobook Singapore | Mitchell Admin | refused: "Demo User does not work in this company." No DEMO-named login works in these companies (their staff logins: QA Test, LOOK P4 validator, Mitchell Admin, and in Your Company "Marc Demo" and two drivers) |
| SG Company | nobody | refused (only Mitchell Admin works there) — and SG Company has no loan route and no fund route at all |

The only DEMO-named holder of a money seat, "DEMO Tran Thi Binh" (Finance, Payobook Vietnam JSC), is a
portal login, which the seat method refuses. No seat was changed anywhere.

## 5. Check on the real system

The browser is signed in as the owner on payobook.com, so the browser part was **look-only**; the
functional checks ran **as the QA login by JSON-RPC** (password never printed or written to the repo).

As QA (`qa.test@payobook.com`, uid 6672, company Payobook Vietnam JSC):
1. **Past-month re-work**: board answers empty (0 re-works). New re-work offers the 12 demo schemes with
   finished payslips. "Corporate Office — End-Month", July 2026, two people (Bùi Anh Nam, Bùi Bá Hùng),
   one what-if: Bùi Anh Nam's Basic Salary 19,600,000 → 22,560,000 ("DEMO what-if"); reason "DEMO check
   after go-live (W2B) - to be deleted". Worked out 2 payslips in 0.9 s: Bùi Bá Hùng "no difference" (the
   demo payslip reproduces exactly), Bùi Anh Nam "would change": **take-home +2,880,820 ₫ · gross
   +3,700,000 · deductions +819,180 (income tax 508,380, social insurance 236,800, health insurance
   44,400) · employer cost +695,600**. Banner: "worked out with today's version of the scheme — 2 payslips
   carry no record of which version worked them out" (the demo generator stamps none). **Cancelled, then
   deleted** (its rows live only in the re-work's own tables; 0 re-works left on every database).
2. **Funds & tax → Suggest**: no loan or advance rows (after D-2, above). Nothing accepted.
3. **Formula Studio Health tab** payload: "Tax year starts in" = January, with its help text and the 12
   months; editable for QA. Not changed.
4. **Offer calculator** (older one, in Studio) on Corporate Office End-Month with a July payslip's inputs:
   boxes back — **Earnings 35,304,279 · Deductions 4,297,316.85 · Employer contributions 5,428,500**.
   Nothing saved.
5. **Run payroll**: the defaults answer with the three kinds Regular / Top-up / Extra run; no run made
   (0 Extra runs).
6. Browser (owner's session, look-only): Past-month re-work board renders with its hero card and "Start a
   re-work"; console clean; the served bundle holds the Payroll hub lens "Past months" and the ⌘K entry
   "Past-month re-work", the Studio "Keep it as it is" warning and the "Good to know" review heading.

Other four sites (cheap checks): login page 200 on payobook, p0clone, rize, sudima (payobook_template 200
on the server's own address); the served page script on all four contains "Past-month re-work" (W2-D1)
and "Keep it as it is" / "Good to know" (W2-F).

## 6. Held / left off / follow-ups

- **Held: D-1** (seats) — needs the owner's choice (question 1). Nothing changed.
- Not done on purpose: payobook demo recompute sample (owner-shortened rehearsal); sending a loan or fund
  payment for approval on payobook (Head of pay is the owner's own account, real email); the Extra-run step
  walked in the browser (owner session; checked through the wizard's defaults instead); Health tab drawn
  in the browser (payload read instead); Vietnamese / Indonesian screens (PO gate only); a 390 px check.
- rize run 2110 recompute ≠ its stored lines (draft trial run, same old and new) — pre-existing.

## 7. Questions for the owner (plain words)

1. **Who should approve loans and fund payments on payobook.com?** Today it is your own account
   (as "Head of pay") in all four demo companies, and "SG Company" has nobody and no approval route at all.
   Two things stop a clean switch to a demo person: (a) on payobook the same "Head of pay" seat also
   approves **pay awards and pay bands**, so moving it moves those too; (b) the only demo login with a pay
   seat, "Demo User", works in Payobook Vietnam JSC only. Options: **A** — Demo User becomes Head of pay in
   Payobook Vietnam JSC only (moves loans, fund payments, pay awards and pay bands there to Demo User;
   nothing else); **B** — also give Demo User access to the other three demo companies and seat them there
   (Demo User then sees those companies' data); **C** — leave it as it is. SG Company would also need its
   approval routes created before anyone there could approve a loan or fund payment.
2. **How should a past-month difference be paid?** (carried from W2-D1; nothing pays it today — the
   re-work only shows it)

   | Way | Tax and insurance | Funds and tax office | Effort / risk |
   |---|---|---|---|
   | A. A one-off in Updates this month, typed by hand | worked out with this month's rules on the lump, so tax can differ from the re-work | all in this month's payments | nothing to build; tax may not match |
   | B. Back-pay lines in this month's pay run, carrying the re-worked tax and insurance | exactly the re-work's figures | in this month's payments, labelled for the earlier months | moderate build |
   | C. A correction payslip dated in each past month | exactly per month | lands in months already paid to the funds — those need correcting | biggest; touches closed months |
   | D. Reopen the old pay runs | — | — | not advised: those people were already paid |
3. **Should a re-work also re-check attendance, leave and connected-system figures**, or only contract
   amounts and typed what-if values (as now)? Each is its own piece of work.
4. Carried from the builders: **who may see re-works** — only the people who approve pay runs (as built)
   or the whole pay team? **An Extra run that is the first to take the advance** still shows the old
   "check it has not been taken already" warning — keep it (safer) or make it a calm note?

## 8. New gotchas (ledger)

W2BM-1 (restoring a dump under `/odoo/backups` from a plain ssh shell needs `sudo cat`; a failed restore
leaves the copy marked as a template, so reset `IS_TEMPLATE` before dropping it), W2BM-2 (on payobook the
Head of pay seat serves loans, fund payments, pay awards and pay bands — re-seating it moves all four),
W2BM-3 (a test that borrows another TestCase's fixtures must restate `setUpClass` — the zero-argument
`super()` is bound to the original class — and import the other test module as a module, never the class,
or the loader runs its tests twice), W2BM-4 (a scratch script that `cd`s into the worktree and writes to a
relative folder leaves that folder inside the worktree — use absolute paths).
