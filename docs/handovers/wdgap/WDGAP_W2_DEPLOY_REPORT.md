# WDGAP W2 — deploy report (merge PR-E, W2-A, W2-B, W2-C; live ×5; verify)

Merge-deploy-verify agent, 2026-11-15 (UTC). Handover `WDGAP_W2_DEPLOY_HANDOVER.md` (method of
`WDGAP_PR_DEPLOY_HANDOVER.md` / `WDGAP_PR_DEPLOY_REPORT.md`).
**Result: merged, pushed to `19.1` at `d88c3f024`, LIVE on all five databases** (payobook,
payobook_template, p0clone, rize, sudima); `pb_fund_payments` installed on all five. 401 s down. ABM,
pbf_preview and every other database untouched. Rehearsal recompute old vs new code: 0 differences.**

## 1. Merge

Branch `wdgap-w2-merge` from `origin/19.1` @ `4c9c82a40`; merged `--no-ff` in the order
`wdgap-w2a` (a7659ae0a), `wdgap-pre` (bc803e58d), `wdgap-w2c` (7026cf618), `wdgap-w2b` (d9ec49bde).
The only conflicts were `WDGAP_LEDGER.md` (three times: phase rows and gotcha rows) — resolved as a
union. No code conflict: the four phases touch disjoint files (W2-A: engine, `pb_updates`,
`pb_me_portal`; PR-E: `pb_payrun_wizard`, `pb_pay_delivery`, `pb_loans`; W2-C: `pb_formula_studio`,
`pb_contracts`; W2-B: the new `pb_fund_payments`). No `.po` header conflict.

Pushed: `4c9c82a40..d88c3f024  19.1` (no force; `origin/19.1` had not moved — fetched again before
the push). Commits: 4 merges, `f78f736e3` (fix F1 + seam tests), `d88c3f024` (handover copy, ledger
phase map, gotchas W2M-1..3), and this report.

### 1.1 Seam checks (§1 a–d) — new tests on the merged tree, all pass

| # | Seam | Read | Test (`wdgap_w2m` tag) |
|---|---|---|---|
| a | Fund payments owe a payslip "paid another way", an Extra-run payslip and a held one | The owed reading (`fund_payment.py` SQL) selects finished payslips by `state IN ('done','paid')` only; "Paid another way" stamps `pb_paid_on/method/note/by` and never changes the state | `pb_fund_payments/tests/test_wdgap_w2_merge_seams.py::test_a` — owed before and after marking Ann paid in cash is identical; Ann (paid another way), Bob (held) and Cai (Extra run) are all in the rows; social 30M × 30 %, tax 1.75M: **pass** |
| b | Year-to-date with a loan instalment PR-E cut | `history.*` reads `formula_computed_values` of finished payslips; PR-E's second pass stores the cut amount there | `pb_loans/tests/test_wdgap_w2_merge_seams.py::test_b` — planned 15M, cut to 10M: `history.ytd.PRBLOANIN` = 10,000,000, `…PRBLOANREP` = −10,000,000, `…PRBNET` = 0, `history.mtd.PRBLOANIN` = 10,000,000: **pass** |
| c | Take-home calculator on a person with a running loan | The calculator takes the stored `formula_input_values` of the payslip (the cut amount) and evaluates in memory; it never calls `_get_formula_input_values`, the loan plan, the floor pass or any reservation | `test_c` — SQL spy: 0 INSERT/UPDATE/DELETE; the loan plan is asked 0 times; target 5,000,000 → BASIC 15,000,000 (with the 10M cut instalment; a fresh plan or a second floor pass would answer 20,000,000); repayment lines, payslip stamps and the 10M reservation unchanged: **pass** |
| d | W2-A's Extra/top-up "counts once" with PR-D's Extra run | W2-A reads the run kind by name (`hr_payslip_run.pb_run_kind` in `('topup','extra')`), the values PR-D's selection defines | `test_d` — Extra run made the ordinary way (kind on create), payslips computed by the real engine: March + Extra (March) + April = 30,000,000, `additional_payslips` = 1, the Extra-run payslip took no instalment; a second REGULAR March payslip still stops the chain: **pass** |

### 1.2 Small fixes on the merge branch

| # | Fix | Result |
|---|---|---|
| F1 | **Pay & deliver opens for every pay-team member after a release** (PR-E question 3, ledger PRE-3) | `pb_pay_delivery/models/pb_pay_delivery.py::_route_payload` now reads the approval request through `sudo()` after `_require_access()` (the Pay & deliver gate: administrator, payroll manager or a finance role) — only the step titles, states, seat names and "with whom" the screen already shows. The request itself stays unreadable to them; who may decide is unchanged; the screen stays closed to anybody else. Test `pb_pay_delivery/tests/test_wdgap_w2_merge_f1.py`: a payroll manager in no seat opens Pay & deliver while the bank file waits (sees "with whom", cannot decide: refused) and after the release (sees who signed it); reading the request directly is still refused; a payroll officer and a plain user are still refused the screen. **The test fails without the fix ("AccessError … top-secret records") and passes with it.** It only reproduced after `flush_all()` + `invalidate_all()` (ledger W2M-1). `pb_pay_delivery` stays 19.0.1.6.0 (PR-E's version, not shipped before). The approval's TIME is not on that payload (names and states only) — not widened. |
| F2 | W2-C "all 12 demo schemes work" vs "the VPTQ schemes have no take-home line" | **Both are true.** Live payobook has 15 active schemes; 12 are the Payobook demo schemes (6 end-of-month, 6 mid-month advance) and all have a take-home line; the other 3 — "VPTQ End Cycle", "VPTQ Mid Cycle" and "Payobook Scale Demo — 250 Columns" — have none. On the payobook copy with the new code the calculator answers on every scheme: all 12 Payobook demo schemes give an exact answer ("To take home 23,992,199 ₫, Basic Salary must be
16,920,838 ₫." and so on, 30–36 tries each); the Scale Demo has no finished payslip; the two VPTQ
schemes belong to a company the rehearsal shell was not working in (refused by the company check) —
their "no take-home line" answer is W2-C's own test 7d ("This scheme has no take-home line, so there is
nothing to work back from.") together with the data fact above. Demo data not changed. |
| F3 | "Tax year starts in" on the Formula Studio scheme panel | **Left, not a one-line change.** The Studio's scheme panel (Health tab) shows only the scheme's validation status; it lists no cycle field (`cycle_type` appears only in the new-scheme wizard and the scheme list chip). The setting is on both scheme forms (W2-A). |

### 1.3 Static gates (merged diff vs `origin/19.1`, 111 files)

py_compile 57 files: 0 failures. XML 14: 0 failures. PO gate (`PoFileReader`) 13 changed `.po`: 0
failures, 0 msgstr naming the vendor (re-run on the server's own reader for the 14 `.po` files of
the 9 staged modules: all parse). Vendor name in added user-visible strings: **0** (the one line the
classifier flagged is the `<odoo noupdate="1">` root of a data file). Product name in `biz_*`: none.

### 1.4 Combined local run (Mac; one database at a time; each dropped after)

| Run | Database | Result |
|---|---|---|
| A — full suites `/pb_hr_payroll_formula,/pb_formula_studio,/pb_loans,/pb_pay_delivery,/pb_payrun_wizard,/pb_me_portal,/pb_updates,/pb_contracts,/pb_fund_payments,/pb_payslip_review,/pb_payroll_templates,/pb_approval_config`, `-i pb_loans,pb_fund_payments` + `-u` the 33 modules behind | copy of `upd_p6_t_tpl` | **2,138 tests, 20 failed, 4 errors.** 23 are the union of the recorded baselines (PR-A 12: TestRd49SyncCost ×2, TestRecordsR1OneTime 07b, TestSchemeCtxCurrency 04, TestJourneyView ×2, TestNetPayCandidates 01, TestOneMappingHome ×4, TestRunsrcPcBoardLane 14; pb_me_portal ×5: TestMeHomeCards 05/06, TestMeHomeSource 12, TestPortalOnlyDoors t1_7, TestPbMePortal 01; W2-C TestCd1Contract360 01; PR-E TestRunInputReview monthly duplicate label; W2-B pb_approval_config ×4: TestApprovalStaticContract, TestVietnameseIsComplete u13, TestP7Vietnamese z06d/z06e). The 24th, `TestInboxFacade.test_u10_an_arranged_exception_opens_the_way_behind_a_real_reason` (AccessError reading a user in `biz.approval.outbox._queue`), **fails the same on `origin/19.1` code without `pb_fund_payments`** (run "base_inbox", same template) — pre-existing; W2-B's baseline missed it because its copy was upgraded with `-u all`. |
| — the new tests within A | | PR-E (`pb_payrun_wizard` 145, `pb_pay_delivery` 64, `pb_loans` 42 incl. the floor F1–F9), W2-A (12 + 9), W2-C (`TestW2cTakeHome`, test 20 skipped off the demo world), W2-B (18 + 1), merge seams a–d and F1: **all pass** |
| W2-A demo recompute | not run locally (disk: 4.8 GB free) | done in the rehearsal on the live payobook copy instead (§3) |

Leftover builder databases `wdgap_pre_*` / `wdgap_w2*`: none existed (listed first).

## 2. Read-only checks on live (before anything changed)

Run 2026-11-15 ~01:15 UTC, and the deploy notes and module trees again just before the prep (03:11).

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| Open START by anyone in `/opt/deploy-notes.md` | none (last: WDGAP PR DONE 20:55 UTC 14 Nov) | | | | |
| Server | disk 28 GB free of 77; memory 3.8 GB, 1.7 GB available; backups folder 18 GB; one service process | | | | |
| Jobs total / active | 105 / 52 (job 156 OFF) | 93 / 34 | 93 / 42 | 93 / 85 | 93 / 84 |
| The 9 module trees on the server = `origin/19.1` | yes (all 8 existing; `pb_fund_payments` absent) | | | | |
| **a.** Schemes of a company in India | 0 | 0 | 0 | **0 — but 5 schemes carry the India country code** (the company is Rize Farms, not Indian) | 0 |
| **a.** Finished Extra / top-up payslips in 2026 (the people whose year-to-date total now counts them once) | **5 top-up payslips, 5 people** | 0 | 0 | 0 | 0 |
| a. Components reading a running total (`history.*`) | 0 | 0 | 0 | 0 | 0 |
| **b.** Loans (any state) | 0 | 0 | 0 | 0 | 0 |
| **b.** Bank files / releases (any state) | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| **c.** `pb_fund_payments` dependencies installed → install | all → yes | all → yes | all → yes | all → yes | all → yes |
| c. Who the fund route would ask: Finance | Mitchell Admin ×3 companies, DEMO Tran Thi Binh (Payobook Vietnam JSC), **SG Company: nobody** | Platform support (recovery account) | same | Ash Sohani | Platform support (recovery account) |
| c. … then Country director | Mitchell Admin ×4, **SG Company: nobody** | Platform support | same | Ash Sohani | Platform support |
| **d.** Head of pay (loan approver) | Mitchell Admin ×4, **SG Company: nobody** | Platform support | same | Ash Sohani | Platform support |
| F2. Active schemes with no take-home line | 3 of 15 (VPTQ End, VPTQ Mid, Scale Demo 250 columns) | 0 of 0 | 0 of 0 | 0 of 4 | 0 of 0 |
| Pay runs / payslips / employees | 53 / 34,322 / 4,575 | 0 / 0 / 3 | 10 / 39 / 14 | 10 / 487 / 311 | 0 / 0 / 653 |

**d. Loan approval seat for "SG Company" — NOT changed.** The handover allowed a plain seat
assignment only if a DEMO person already holds the equivalent seat (Head of pay) for another payobook
demo company. Nobody DEMO does: all four other companies have Mitchell Admin, which is the owner's own
account (ash@biztinct.com). The only DEMO seat holder on payobook is DEMO Tran Thi Binh, as Finance for
Payobook Vietnam JSC — a different seat. Reported as an owner question; no seat touched anywhere.

## 3. Go live (risky tier)

Evidence on the server: `/tmp/wdgap-w2-20261115T031155Z/`; backups
`/odoo/backups/wdgap-w2-20261115T031155Z/` (payobook 81.1 MB, payobook_template 28.5, p0clone 28.9, rize
42.1, sudima 28.9; each read back with `pg_restore -l`) + the 8 previous module trees. Lock held by its own
unit (`wdgapw2-lock`) the whole window, released after DONE. START 03:11, DONE 06:00 UTC (the window was
long because of the rehearsals; the service was down only 401 s). Staged = `git archive d88c3f024`
(9 trees hash-checked = commit). PO gate on the server's reader: 14 files parse.

**Rehearsals** (copies hidden from the live job runner while restoring; jobs and mail servers off; real row
counts asserted; recompute with OLD code, upgrade with the staged code, recompute with NEW code, each run
rolled back; copies dropped with `--force`):

| Copy | Upgrade | Recompute old code vs new code | Counts before → after |
|---|---|---|---|
| rize | EXIT 0 in 74–76 s; only the 3 known `payroll_analytics` lines; 0 Traceback; 0 new jobs; 0 payees / 0 fund payments; 1 fund route; all 19 schemes "January" | rize has **no finished run**, so all its runs were recomputed (two passes): 9 runs, **485 payslips, 0 differing**. Fully computed and identical old/new: TEST IN Excel 27, TEST ID Excel 122, TEST SG app-data 2, TEST IN app-data 26, TEST ID app-data 3. The rest are refused IDENTICALLY by old and new code for reasons already there: run 1591 "October 2026" (63) — its scheme is archived; TEST VN / SG Excel — text in a number column ("Review payroll inputs", "Working days required"); TEST ID / VN app-data — "The source changed" (119 + 29) and "Payroll preparation does not match this run" (10). **The application-data refusals are the same before and after, so W2-A's change to the year-to-date reader moved no fingerprint.** | identical (311 employees, 487 payslips, 16,179 lines, line total 29,559,077,500.24, 93 jobs, 897 mails) |
| payobook | EXIT 0 in 96 s; same 3 lines; 0 new jobs; 0 payees / 0 payments; fund routes 4 for 5 companies (SG Company: nobody in the seats); all 26 schemes "January" | the smallest finished REGULAR run of **every scheme that has one (14: 12 Payobook demo + 2 VPTQ)**, the first 300 payslips of each (a cap, so each pass stayed near 45 minutes; run 335 Manufacturing July and both VPTQ runs whole): **14 runs, 3,354 payslips, 86,491 lines — 0 differing payslips; "figures add up" true before and after on all 14.** As in the PR step, the recompute does not equal the STORED demo lines (pre-existing, PR-A R5) — identical old vs new. | identical (34,322 payslips, 873,586 lines, line total 2,869,624,867,029.71, 105 jobs, 3,135 mails) |

- **Downtime 401 s (6 min 41 s)**: stop 05:51:31, port up 05:58:12 UTC. Upgrades in order
  payobook_template 74 s, p0clone 71 s, sudima 71 s, rize 75 s, payobook 87 s — all EXIT 0, only the 3
  known lines each.
- Per database: `-u pb_contracts,pb_formula_studio,pb_hr_payroll_formula,pb_loans,pb_me_portal,pb_pay_delivery,pb_payrun_wizard,pb_updates`
  + `-i pb_fund_payments`; signal row + bundle purge + `web.assets.version` = `wdgap-w2-20261115T031155Z`.
- Job repair: payobook_template's upgrade switched 4 jobs back on (84, 85, 86 time clocks, 91 attendance
  connectors) — switched off again at once. Job 156 on payobook: still OFF.

### Versions before → after (all five)

| Module | Before | After |
|---|---|---|
| pb_hr_payroll_formula | 19.0.1.166.0 | 19.0.1.167.0 |
| pb_formula_studio | 19.0.1.212.0 | 19.0.1.213.0 |
| pb_contracts | 19.0.1.13.0 | 19.0.1.14.0 |
| pb_fund_payments | — | 19.0.1.0.0 (new) |
| pb_loans | 19.0.1.0.0 | 19.0.1.1.0 |
| pb_me_portal | 19.0.3.6.1 | 19.0.3.7.0 |
| pb_pay_delivery | 19.0.1.5.0 | 19.0.1.6.0 |
| pb_payrun_wizard | 19.0.1.44.0 | 19.0.1.45.0 |
| pb_updates | 19.0.1.7.4 | 19.0.1.8.0 |

### Verification

- **Trees**: all 9 server trees byte-identical to `d88c3f024`.
- **Versions**: manifest = `latest_version` for all 9 on all five databases (0 mismatches).
- **Jobs**: id lists and active states identical before/after on all five (52/34/42/85/84); no new job.
- **Data**: mails queued, active users, employees, pay runs, payslips, payslip lines, line totals,
  components, schemes and loans identical before/after on all five. Only change: +1 approval route per
  company ("Fund and tax payments") — payobook +4 (SG Company none), the others +1. 0 payees, 0 fund
  payments, 0 "paid another way", 0 loan cuts, 0 Extra-run picks; every scheme's tax year = January.
- **Who a fund payment would go to** (Finance, then Country director): payobook — Mitchell Admin (the
  owner's own account) in 3 companies, DEMO Tran Thi Binh then Mitchell Admin for Payobook Vietnam JSC,
  **SG Company nobody**; payobook_template, p0clone, sudima — Platform support (recovery account) twice;
  rize — Ash Sohani twice (one person signs both steps).
- Server log since start: 0 ERROR/CRITICAL/Traceback. One service process. Sites 200 on all five.
- `/opt/deploy-notes.md`: START 03:11, DONE 06:00, plus a NOTE correcting the DONE line's rize rehearsal
  count (it said 10 runs / 607 payslips; one run was done in both passes: 9 runs, 485 payslips).

## 4. Check on the real system

The Chrome DevTools browser was again in use by another session (profile locked), so no private
window could be opened. Functional checks were done **as the QA login by JSON-RPC from this Mac**
(password never printed or written to the repo), plus a **look-only walk** in the owner's signed-in
browser (nothing pressed that saves).

As QA (`qa.test@payobook.com`, uid 6672, company Payobook Vietnam JSC) — nothing created, sent or changed:
1. **Funds & tax board** answers (allowed, November 2026, no totals — empty). **Suggest** proposed 7 funds
   from the demo schemes: Health Insurance, Social Insurance, Unemployment Insurance (18 pay items each,
   across the schemes), Personal Income Tax, Trade Union Fund, Loan Repayment, Mid-Month Advance (the last
   four with the "untick it if it is not paid to an outside office" note). **Not accepted**, so nothing to
   remove: 0 payees, 0 payments in the database afterwards.
2. **Take-home calculator** on Phan Công Đạt (Corporate Office End-Month, payslip of July 2026): opens
   ("Everything else as on the payslip of 07/01/2026", item Basic Salary, take-home 31,006,962);
   +15 % → exact: "To take home 35,658,006 ₫, Basic Salary must be 27,878,255 ₫." (34 tries). From his
   contract: opens ("as on the payslip of 10/01/2026"). Nothing saved.
3. **Tax year**: all 13 active schemes QA can see read "Tax year starts in" = January. Not changed.
4. **Pay & deliver** of finished demo run 335 opens for QA; the new "paid another way" block is there
   (0 people; methods Cash / Cheque / Other bank transfer / Other); the money line carries "paid another
   way" 0. Run 335 leaves nobody out (all 40 have bank details), so its left-out list is empty; nobody
   was marked.
5. **Run payroll** offers Regular / Top-up / Extra run. The Extra run's pay-data-file line was not walked:
   payobook has no scheme that asks for a pay data file in Run payroll (PR-step finding).
6. **Loans board** answers.
7. Browser (owner's session, look-only): the Funds & tax board renders with its first-run card ("Who does
   the company pay after payroll?" — Suggest from my pay schemes / Add one myself), the month switcher and
   "1 finished payslip this month"; console: no errors. ⌘K "fund and tax" finds "Fund and tax payments ·
   Payroll".

Other four sites (cheap checks): login page 200 on all; the served page script on payobook, p0clone, rize
and sudima contains W2-A ("from the start of the tax year"), W2-B (`pb_fund_payments_board`), W2-C ("Work
back from take-home") and PR-E ("Paid another way").

## 5. Held / left off / follow-ups

- Nothing held back.
- Not done on purpose: sending a fund payment for approval on payobook (Finance / Country director there
  is the owner's own account, which gets real email); accepting the suggested funds; marking anybody "paid
  another way"; the Extra-run pay-data-file walk (no such scheme on payobook); a 390 px check; the
  Vietnamese / Indonesian screens (PO gate only).
- Seat question d: SG Company on payobook has nobody as Head of pay, Finance or Country director, so it
  has no loan route and no fund route. Not changed (no DEMO person holds the equivalent seat).
- Rehearsal cap: the payobook recompute took the first 300 payslips of each large demo run (3,354 in all)
  instead of whole runs (7,867) — each pass already took 45 minutes on the live box.
- Observations for later: (1) Suggest offers "Loan Repayment" and "Mid-Month Advance" as funds (with the
  untick note) — they are deductions, not outside offices; (2) on the Logistics, IT and Construction demo
  schemes the calculator shows take-home rising very slowly with basic pay (e.g. take-home 9.8M needs
  basic 46M) — exact by the engine, but those demo schemes deduct heavily; worth a look before a demo;
  (3) the `TestInboxFacade` u10 failure is pre-existing on `19.1`.

## 6. Questions for the owner (plain words)

1. **Who should approve payments to funds and the tax office on payobook.com?** Today it is your own
   account (Finance and Country director) for most demo companies, so a demo fund payment sent for
   approval would email you. A demo person could hold those seats instead. "SG Company" has nobody in any
   money seat (loans, funds) — leave it, or put a demo person there? On rize, Ash Sohani signs both steps
   of a fund payment — is one person signing twice acceptable?
2. **Should "Suggest" leave out loan repayments and the mid-month advance?** They are offered as funds with
   a note to untick them. Hiding them is cleaner but means trusting the pay roles more.
3. **India tax year (W2-A question 3)**: no customer company is in India; rize has 5 schemes marked as
   India schemes — should they start their tax year in April? (Nothing changes until someone picks it.)
4. Carried forward from the builders, still open: one company with schemes on different tax years (W2-A
   q1); Formula Studio panel showing "Tax year starts in" (W2-A q2 — the panel has no cycle field today,
   so it is a small new panel row, not done here); fund payments with one signature instead of two (W2-B
   q1); Vietnam insurance as one fund by default (W2-B q2); reminders before a fund payment is due (W2-B
   q3); a take-home calculator for a list of people (W2-C q1); "net basis" contracts (W2-C q2); category
   review on the VPTQ demo schemes (W2-C q3); an Extra run with a pay data file still takes the mid-month
   advance again — flagged only (PR-E q1); a ₫0 payslip counting as paid (PR-E q2); the older offer
   calculator in Formula Studio shows no earnings/deductions boxes on live (W2C-1, one-line fix
   available).

## 7. New gotchas (ledger)

W2M-1 (a rights test must invalidate the cache or it passes on the bug), W2M-2 (`assertRaises`
takes no tuple), W2M-3 (`caffeinate` wrapping `odoo-bin` segfaulted once — start it beside),
W2M-4 (a rehearsal recompute can read "identical" because every payslip was REFUSED — count
the refusals; rize's run 1591 is on an archived scheme and refuses, which the PR step's report read as
"identical to the stored lines").
