# WDGAP Step 6 (+ S8-D) — deploy report: merged, tested, rehearsed — HELD at the owner gate

**Result: NOT LIVE. Held before go-live by the owner gate in handover §3** — the read-only bank
check found employees whose two bank records disagree on **rize (198)** and **sudima (642)**; the
owner sees the lists first. Everything up to the go-live is done: merge pushed to `19.1` at
`7f2045121` (Step 6 + the S8-D scope addition), combined local runs at baseline, rize rehearsal
passed, five fresh dumps kept. **The service was never stopped; no live module tree or database
was changed.** Deploy notes: START 17:30 UTC, NOTE "held, nothing changed" 18:06 UTC, lock released.

**Live bug still open:** "Make it permanent" on a contract decision raises an error on all five
databases (S8-B's `pb_contract_rules._build_new_contract(start, new_end)` drops the
`contract_type` keyword that `pb_contract_lifecycle/models/contract_review.py:590` passes). The
fix is in S8-D (merged here, not live). S8-D touches none of Step 6's modules and can go live on
its own (six modules, list in §4) if the owner wants it before the bank decision.

Merge-deploy-verify agent, 2026-11-16 (UTC). Handover `WDGAP_S6_DEPLOY_HANDOVER.md` (method of the
S5/S8 deploy handovers) + coordinator additions (Step 9 first; S8-D merged into this go-live).

## 1. Merge

Branch `wdgap-s6-merge` from `origin/19.1` @ `38e1b524e`; `--no-ff` in the order `wdgap-s6a`
(c426bd1f4), `wdgap-s6c` (da719070a), `wdgap-s6b` (6558890c4) — **no conflict**. After the WDGAP S9
DONE line (14:29 UTC): `origin/19.1` (Step 9 + S5-F) merged in — one conflict, `pb_me_portal`'s
pinned home test, resolved keeping ALL tiles (Letters from HR, My review, My details,
Certificates). Then `origin/wdgap-s8d` (c18bc91f2) — no conflict. Then `origin/19.1` again (S9
deploy report; ledger conflict resolved keeping both). Pushed `147a1ccf0..7f2045121 19.1`
(fast-forward, no force).

Versions: pb_bank_ocr 19.0.1.2.2 → 19.0.1.4.0, pb_records 19.0.1.10.1 → 19.0.1.10.2 (builders);
**pb_payrun_wizard 19.0.1.46.0 → 19.0.1.47.0** (merge task b); eight new modules (pb_me_details,
pb_me_letters, pb_me_privacy 19.0.1.0.0; pb_hiring_internal, pb_me_payai 19.0.1.1.0;
pb_expense_payroll, pb_expense_allowance 19.0.1.0.0; pb_trip_advance 19.0.1.1.0). S8-D:
pb_pay_scales 19.0.1.1.0, pb_pay_package 19.0.1.1.0, pb_job_change 19.0.1.0.1,
pb_contract_lifecycle 19.0.1.3.3, pb_people_advanced 19.0.1.1.3, pb_contract_rules 19.0.1.0.1.
`pb_me_portal`: test file only (no version change; rsync without `-u`).

### 1.1 Merge-time edits (the only edits outside merging)

| Task | Files | What |
|---|---|---|
| a. ME1 | `pb_me_details/models/pb_me_home.py` (tile row), `pb_me_letters/models/pb_me_home.py` (tile row), `pb_me_portal/tests/test_me_home.py` test_02 | My details (Me seq 9) and Certificates (Me seq 10) under "Me", after Letters from HR (seq 8, Step 9). The pinned test expects the optional tiles only when their module is loaded (S6M-4). |
| b. BK2 gap | `pb_payrun_wizard/models/pb_payrun_wizard.py` `attach_spreadsheet` answer (+ `bank_waiting` only when something waits), `static/src/xml/payrun_wizard.xml` (one `pw-warn` line, no new static words), test `test_wdgap_s6_bank_waiting.py` | The result screen says "N bank changes are waiting for approval…" (pb_bank_ocr's own sentence). **Finding (S6M-1): with `pb_payroll_templates` installed — all five live sites — the wizard loads every file "this run only", so nothing reaches a bank record from the wizard and the line will not appear there;** bank changes from files come through the Import screens and connected-system refreshes, where BK2 already holds them. |
| fixes found on the merged tree | `pb_bank_ocr/i18n/id_ID.po` header | "Project-Id-Version: Odoo Server" → "Payobook" (white-label PO gate `TestP7Matrix.test_z06a`, S6M-3) |
| | `pb_hiring_internal/tests/test_internal_move.py` B30/B30b | hide Step 8's Change job explicitly (it is installed now; S6M-5) |

### 1.2 Seams (new tests, tag `wdgap_s6m`) — all pass

| # | Seam | Where | Result |
|---|---|---|---|
| c | Every `pb.me.home` override (S6 ×5 modules, Step 5 late page, older ones) calls `super()`; My requests sources unique + readable; home data/needs stack; `/my`, `/my/details`, `/my/certificates`, `/my/requests`, `/my/expenses`, `/my/jobs`, `/my/privacy`, `/my/ask-policy`, `/my/work/late` answer for a portal login, no vendor word; My details/Certificates drawn under "Me" | `pb_me_details/tests/test_wdgap_s6_merge_home.py` | pass (re-run after the Step 9 merge) |
| d | C-1 against the REAL Change job: internal hire → Change job opens prefilled (job, team, manager, "transfer", source internal_hire), nothing created, no second employee; IM1 no joiner list. Also with S8-D's Pay › Changes hook installed | `pb_hiring_internal/tests/test_wdgap_s6_merge_seams.py` | pass |
| e | C-2 against the REAL pause: role, team, company paused → hidden and refused | same | pass |
| f | ONE payslip with an expense claim (+300,000), an unspent trip advance (−5,000,000), Aug–Oct back pay and 40 confirmed late minutes: each held once; recompute identical; payslip totals = pay run SQL; gross − deductions = take-home; a person with none of them byte-identical with Step 6 switched off; finished → each paid once | `pb_trip_advance/tests/test_wdgap_s6_merge_payslip.py` | pass |
| g | Bank, every path, both stores only on approval, approver ≠ requester | builders' suites on the merged tree: S6-A B1–B12, K1–K6, M1–M10, R1–R4 (pb_bank_ocr 54, pb_records 140) + BK2 wizard test | pass (pb_bank_ocr's 4 known errors only) |
| h | Approvals inbox: me_details, me_certificate, tripadvance, records_bank, **scaleraise (S8-D)** — each process once, one route per company, laying again lays nothing, nothing waiting | `test_wdgap_s6_merge_home.py::test_h` | pass |
| i | PayAI for employees off for every company; page sends the employee home; no outside call (the one egress point would raise) | `::test_i` | pass |
| j | Certificate PDFs | rize rehearsal copy (§2) | printed |
| S8-D a | Hiring board + a draft offer with "Build from a total" + Staff moves together | browser (local `s6m.localhost:8987`, merged tree, DEMO role/offer/staff application) | board, role board (staff application shown "Internal"), Details › Offer & joining › Offer shows "Build from a total" beside "Add a line" (opens; plain sentence when the company has no scheme), Staff moves lists the application "Manager not told yet"; **console: no errors after a reload** |
| S8-D b | C-1 with Pay › Changes hook | seam d (run B, with S8-D installed) | pass |
| S8-D c | renew → pay lines carried; Make it permanent works | S8-D X1–X6 on the merged tree + rehearsal signature check | pass |

### 1.3 Combined local runs (one database `wdgap_s6m_t`, own port 8987; dropped at the end)

| Run | What | Result |
|---|---|---|
| A (before the Step 9 / S8-D merges) | copy of `upd_p6_t_tpl`, every module behind the tree `-u`, live-installed modules since the template + the 8 new `-i`; suites of the 8 new + pb_bank_ocr, pb_records, pb_payrun_wizard, pb_me_portal, pb_ask_hr, pb_hiring, pb_hr_payroll_vietnam, pb_me_expense, pb_expenses_hub, pb_business_trip, both trip bridges, pb_me_trip, pb_loans, pb_payslip_review, pb_payruns, pb_approval_config, biz_approval_workflow, pb_retro, pb_time_pay, pb_job_change, pb_hr_payroll_formula | 2,501 tests, 33 failed + 25 errors. 52 = the recorded baselines. 6 outside: E1/A7 goldens (BK2 key → fixed), z06a PO header (fixed), BK2 wizard test (test drove the "this run only" path → fixed), test_i (tile assertion too strict → fixed), jc11 (local jobs-off artifact, S6M-7), MeHomeSource test_01 (merge mid-run, S6M-8) |
| B (after Step 9 + S8-D merges, all fixes) | same base, `-u` behind + the S6 and S8-D modules, `-i` the four Step 9 modules; suites of pb_pay_scales, pb_pay_package, pb_contract_lifecycle, pb_contract_rules, pb_people_advanced, pb_hiring, pb_me_portal, the 8 new, pb_payrun_wizard, pb_bank_ocr, pb_records, pb_ask_hr, pb_approval_config, biz_approval_workflow, pb_time_pay, pb_retro, pb_job_change, pb_review_forms, pb_conduct, pb_people_reports, pb_voice | **1,704 tests, 17 failed + 9 errors = exactly the recorded baselines** (pb_bank_ocr test_07/07b/09/15; approval u10, the look, z06d/e, u13; pb_me_portal 05_grid/06_font/12_vi_po/t1_7/test_01_profile; pb_ask_hr 12/13; pb_hiring 10). All seams, all S8-D (111) and Step 9 suites pass. |

Static gates on the merged diff (288 files): py_compile 0, XML 0, `node --check` ok, PO parse 0
failures, 0 msgstr naming the vendor; product name in `biz_*` 0. Test-fixture passwords only for
throwaway test logins (same convention as every phase).

## 2. Rehearsal — rize copy (passed, 340 s)

Evidence `/tmp/wdgap-s6-20261116T173025Z/`, staged = `git archive 7f2045121` (18 trees = commit).
Copy restored hidden from the live job runner, jobs + mail off, real counts (311 employees, 487
payslips). Upgrade `-u` pb_bank_ocr, pb_records, pb_payrun_wizard + the six S8-D modules, `-i` the
eight new: **EXIT 0 in 75 s, 0 ERROR, 0 Traceback.**

| Check | Result |
|---|---|
| Recompute old vs new (runs 2110, 2115, 2116) | 114 payslips, 3,516 lines, **0 differing payslips**, run totals identical (2116's 60 and 2115's 1 refusal identical before/after, W2M-4) |
| Bank file fields, bank accounts, employee-account links, ID papers/marital, permits, dependants, contracts, **contract pay lines + pay-line hash, pay-line changes, pay records**, payslips, lines, receipts, claims, trips, mails, to-dos, approval requests | **identical after install and at the end** |
| Bank check before / after | identical (rize: 198 "account only", 113 neither); S6-A's own ORM check = the SQL twin (311 checked, same counts) |
| New rows | routes only: me_details, me_certificate, tripadvance, records_bank, scaleraise — one each for Rize Farms; 0 requests; 0 everything else |
| New jobs | 1, quiet: "Pay scales: write approved rises on their day" (S8-D) |
| Silent | PayAI for employees off, claims "by finance", no privacy notice, no staff-open role, 0 scale rises |
| Make it permanent | every `_build_new_contract` override takes `contract_type` (pb_contract_rules, pb_contract_lifecycle) |
| Certificates (DEMO person made inside the rolled-back probe) | employment EN and VI, salary EN — real PDFs (wkhtmltopdf), 180–235 KB, numbered CERT/2026/0001–3; salary waits for HR then prints "agreed monthly salary is 12,345,000 ₫"; no vendor word. Cosmetic: a person with no team reads "in the team," / "bộ phận ," |

## 3. Read-only live checks (all five; nothing changed)

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| Open START by anyone | none (Step 9 DONE 14:29) | | | | |
| Server | disk 27 GB free of 77; memory 2.0 GB available; one service process | | | | |
| Jobs total / active | 108 / 55 (156 OFF) | 96 / 37 | 96 / 45 | 96 / 88 | 96 / 87 |
| Every dependency of the 8 new modules | installed | installed | installed | installed | installed |
| New tables already there | none | none | none | none | none |
| "Bank details — a second person" route | 4 companies | My Company | My Company | Rize Farms | Sudima Panels Vietnam |
| AI accounts (active) | 4 (2) | 1 (0) | 1 (0) | 1 (0) | 1 (0) |
| Live trees of the 18 modules = `19.1` before this merge | yes (Codex modules not in the set; not touched) | | | | |

**Bank-store check (OWNER GATE)** — employees whose two bank records disagree:

| Site | Disagree | Kind | Agree / have neither |
|---|---|---|---|
| payobook (demo) | **4,500** | bank-file number, no bank account | 75 neither |
| payobook_template | 0 | — | 3 neither |
| p0clone | 0 | — | 14 neither |
| **rize** | **198** (10 archived) | bank account on record, but NO bank-file number | 113 neither |
| **sudima** | **642** | bank account on record, but NO bank-file number | 11 neither |

Lists (one CSV per site, numbers masked to the last 4): `outputs/wdgap-s6-bank-check-2026-11-17/`
(main checkout, never committed). Nothing is rewritten by the go-live itself.

**Nightly backups include the file folder?** Yes for payobook, payobook_template, p0clone, rize
(hard links, same disk). **sudima has no nightly backup at all** (S9M-1).

**S8-D renewal check (read-only, run now on live; nothing changed)** — people whose current
contract lost pay lines at an earlier renewal: payobook 7 people (24 lines, all "by dates"),
others 0. List: `outputs/wdgap-s8d-renewal-check-2026-11-17/`.

## 4. Go live — NOT DONE (held)

Ready to resume: `ssh Payobook19v2`; the staged trees `/tmp/deployWDGAPS6` and dumps
`/odoo/backups/wdgap-s6-20261116T173025Z/` (+ file folders) are from 17:30 — **take fresh dumps
on resume** (re-run `s6_prep.sh 7f2045121 …`, then `s6_golive.sh`, `s6_verify.sh`; scripts in the
session scratchpad `s6m/`). Per database: `-u pb_bank_ocr,pb_records,pb_payrun_wizard,
pb_pay_scales,pb_pay_package,pb_job_change,pb_contract_lifecycle,pb_people_advanced,
pb_contract_rules -i` the eight new; rsync also `pb_me_portal` (test file). The go-live script
re-checks request-log activity (15 min) right before the stop and refuses if live trees moved.

S8-D alone (if the owner wants the "Make it permanent" fix first): the six S8-D modules only,
`-u` ×5; they share no file with Step 6.

## 5. Checks on payobook.com — not done (nothing went live)

## 6. Questions for the owner (plain words)

**Bank details (gate)**
1. **Rize 198 and Sudima 642 people have a bank account on their record but no account number in
   the bank-file fields.** The bank file pays from those fields, so these people would be left out
   of a bank file today. For each list: copy the account into the bank-file fields (through the
   normal second-person approval), or leave as is? Go live with Step 6 before deciding?
2. Payobook demo: 4,500 demo people have a bank-file number but no bank account. Leave (demo)?
3. Who writes Rize's privacy notice? Until a customer publishes one, nobody is asked.

**Step 6 builders**
4. **Internal movers and papers:** when the company asks new hires for papers at offer time, a
   person moving inside the company is still asked. Turn that off for internal moves too?
5. Should a manager ever see that someone in their team applied before an offer is near? (Today no,
   unless the manager is on that role's hiring team.)
6. Bank changes from a pay data file loaded in the Run payroll wizard: on all five sites the wizard
   uses each file "this run only", so it never changes bank details; imports from the Import
   screens and connected systems do (and wait for a second person). Fine?

**S8-D (carried from its report)**
7. The yearly Pay Review round still raises pay at once, whatever start date it shows. Wait for the
   start date too?
8. Should an extended contract copy the Vietnam contract kind (never the trial flag)?
9. The Contracts "Renew" button does not link the new contract to the old one, so fixed-term
   counting does not see those renewals. Link them (some people may then show the red warning)?
10. A scale rise raises the wage only, not a grade's allowances. Should it raise those too?
11. Renewals that already lost pay lines (payobook demo 7 people, others none): add them back by
    hand or leave?

## 7. Smaller notes

- Certificate wording when a person has no team ("in the team," / "bộ phận ,").
- S6-A sentence "1 bank changes are waiting…" (plural with one).
- New `.po` headers in the eight new modules still say "Odoo Server 19.0" (not shown to anyone;
  only pb_bank_ocr's was caught by a gate and fixed).

## 8. New gotchas (ledger)

S6M-1 … S6M-8 (wizard loads "this run only"; goldens pin answer keys; PO header gate; tile seq
after pb_me_portal's rows; stand-in tests must hide the real Change job; bank check as SQL twin;
local jobs-off artifact; merging mid-run). Builders' rows S6A-1..8, S6B-1..9, S6C-1..5, S8D-1..6
added to the ledger.
