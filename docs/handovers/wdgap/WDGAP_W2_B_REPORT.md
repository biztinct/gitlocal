# WDGAP W2-B — Payments to funds and tax offices: report

Branch `wdgap-w2b` (from `origin/19.1` at `4c9c82a40`). New module **`pb_fund_payments` 19.0.1.0.0**.
Not merged, not deployed. No other module's file was edited (`pb_pay_delivery`, `pb_payruns`,
`pb_approval_config`, `pb_hub`, `pb_payhub`, `pb_statutory`, `pb_pack_*` untouched).

## 1. What was built

| Part | Where | What it does |
|---|---|---|
| Who we pay | `models/fund_payee.py` | `pb.fund.payee`: name, company, usual currency, due day ("by day N of the month after the pay month"), how to pay them (free text), reference to quote, and its pay items `pb.fund.payee.item` (a scheme component + employee share / employer share). One pay item can belong to one active payee only (it would be paid twice). |
| Suggest | same file | Reads the one typing the product has: the component's pay role (`hr.formula.rule.net_role`: taken off net pay → employee share, employer cost → employer share), only money items printed on the payslip, never a part already "included in another total". Pairs each employer cost with the deduction of the same name or code once the share words are gone ("Social Insurance (EE)" / "(ER)", SIEMP / SICOMP, "BHXH - NLĐ" / "BHXH - DN") and gathers the same name across schemes. A lone deduction carries a note ("untick it if it is not paid to an outside office — a loan repayment …"). No country codes, no `pb_pack_*` read. Nothing is created until a person accepts; the dialog renames, merges ("Pay together with …") and unticks. |
| What is owed | `models/fund_payment.py` | `pb.fund.payment`: one row per payee per pay month per currency. Owed = the payee's items on the FINISHED payslips (done/paid) whose period ends in the month, every kind of run (regular, top-up, Extra), payslips on hold included; split employee / employer, people, payslips behind it, per-item breakdown. One SQL read per month. States to pay → waiting for approval → approved, not paid → paid (+ cancelled). Due date from the payee's due day; late flag (unpaid past due, or paid after it). |
| Work out | `pb_work_out` | "Work out what we owe for <month>": creates rows that are missing, updates rows still "to pay", leaves waiting / approved / paid figures alone and records the latest reading beside them ("Figures changed since approval: +3,000,000 ₫"), cancels a "to pay" row nothing is owed on any more. Idempotent; partial unique index (payee, month, currency) on live rows. The toast says what moved ("1 new, 2 updated, 1 changed since approval"). |
| Approval | `models/fund_approval.py`, `data/approval_process.xml`, adapter in `fund_payment.py` | Catalogue row `fundpay` (area Money out, `money=True`, `bulk_ok=False`), adapter on `biz.approval.adapter.mixin` + `pb.money.approval.mixin` cloned from `pb.payment.release`. Default route = the release's two signatures (Finance, then Country director), laid for every company at install and for every new company. Inbox card: "Pay Social insurance office · October 2026", amount, "6 people"; detail table per pay item (employee share, employer share, people) + chips (pay to, month, due by, shares, reference). Seat read: own `biz.approval.request.seat` hook (the shared one only knows pb_pay_delivery's models). Sent back / turned down / withdrawn → back to "to pay". |
| Paid | `action_mark_paid` | Only an approved row; the receipt (an attachment on the payment) is required; paid on (not in the future), amount paid (default = owed), payment reference; a paid amount that differs from what is owed needs a note. Gated on the money role (`require_pay`). Audit line + history note. |
| Reopen | `action_reopen` | Approved or paid → reason required → back to "to pay", worked out again from the payslips, paid details cleared (the receipt stays in the history), needs a new approval (attempt 2). |
| R1 guard | `create` / `write` | Any create or write of a business field that does not come from the module's own methods is refused with a plain sentence; only `seat_user_ids` and the message fields are free. |
| Board | `models/fund_board.py`, `static/src/{js,xml,scss}` | "Fund and tax payments": Payroll hub lens "Funds & tax" (`PAY_LENSES`, sequence 45) + palette row (4410) + client action `pb_fund_payments_board`. Month switcher (‹ October 2026 › + month picker), per-currency "Owed · Paid · Left to pay", the one late line ("2 payments are past their due date — Show them" jumps to the oldest month), quiet numbers, four steps, filter kit (where it is, pay to, due date, figures changed, currency, owed), table (pay to, due by + Past due / Paid late chips, people, employee share, employer share, owed + changed chip, paid + difference, status + receipt clip). Drawer: owed hero with split, state sentence (waiting — with whom), moves (Send for approval, Open in Approvals, Withdraw, Record the payment with receipt upload, Reopen, See the payslip lines), the proof, how to pay them, pay items, the people behind it (top 100), what happened. "Who we pay" dialog (list, warnings, editor with item finder and share toggle) and "Suggest" dialog. First-run hero card when nobody is set up. Excel: the month, one block per currency with its own total. |
| Rights | `security/*` | Mirrors the bank file: payroll users read; payroll managers act (and the finance roles through `PAY_GROUPS`, checked in code); anyone asked to decide reads that one payment (seat rule). Company rule on payee, item and payment. |
| Words | `i18n/vi_VN.po`, `i18n/id_ID.po` | 360 of 362 terms in each (the 2 left are technical field names). PO gate passes; header names Payobook. |

## 2. How a customer sets it up (three steps, plain words)

1. **Say who you pay.** Payroll › Funds & tax › "Suggest from my pay schemes". Payobook proposes the funds from what each pay item does to net pay. Put together the ones one office collects (in Vietnam: social, health and unemployment insurance go to one office), untick anything that is not paid outside (a loan repayment), rename them, then open each one to add the bank details and the due day.
2. **Work out the month.** When the month's pay runs are finished, press "Work out what we owe for October 2026". Each fund gets one line: what is owed, split employee / employer, how many people, due by. Open a line and "Send for approval".
3. **Pay and record it.** After approval, pay the fund as you do today, then "Record the payment": date, amount, reference and the receipt. If the amount differs, say why. Late or changed payments show on the board.

## 3. Tests

`pb_fund_payments/tests/test_fund_payments.py`, tag `pb_fund_payments`, local copy `wdgap_w2b_t` (template `upd_p6_t_tpl` upgraded to HEAD with `-u all`).

| # | Case | Result |
|---|---|---|
| T1 | Suggest from typed components: pairs EE/ER by name and code, same name across schemes, lone deduction note, never a detail / info / off-payslip / earning / net item; accept with a merge → 2 payees, nothing left to suggest | pass |
| T2 | owed = employee + employer shares for a fixture; due date; per-item breakdown; draft payslip never counts | pass |
| T3 | Extra-run payslip included | pass |
| T4 | held payslip included | pass |
| T5 | two currencies → two rows; board totals per currency | pass |
| T6 | work out twice: nothing new, "nothing changed"; unique index refuses a second live row | pass |
| T7 | figures-changed chip after a new finished payslip post-approval; approved figure unchanged | pass |
| T8 | real default route: two different signatures (the second holds no payroll role — seat read + sudo context), inbox card `can_bulk` False, `bulk_ok` refused on the process, detail table, seat reads only its own payment | pass |
| T9 | mark paid needs approval and the receipt (and one of its own, not another record's) | pass |
| T10 | a difference needs a note; a future date refused | pass |
| T11 | late flag (unpaid past due; paid on time / paid late), board late count + oldest month, "late" filter | pass |
| T12 | reopen: reason required, back to "to pay", worked out again, paid details cleared, second approval | pass |
| T13 | rights: plain employee refused, payroll user reads but cannot act, payroll manager acts; company rule | pass |
| T14 | Excel: one block per currency with its own total, no vendor name | pass |
| T15 | R6 identity: a payee holding every deduction (employee) and employer-cost item equals the runs' Deductions and Employer cost, and `pb_pay_totals` per payslip | pass |
| T16 | R1: no write or create path types a figure; one item, one payee; a "to pay" row nothing is owed on is cancelled | pass |
| T17 | board surface: work out toast, head, page with month ctx, other month empty, drawer, payslip-lines drill (8 lines), filter layout, payees, item options ("already paid to"), save payee, submit; no vendor name | pass |
| T18 | install is silent: no payee or payment shipped, no job, no email template, nothing queued; module data only rules, views, actions, the catalogue row. (First runs, on the fresh copy, also counted zero payees / payments in the whole database; after the browser walk seeded its own the test judges the module's shipped data instead.) | pass |

**pb_fund_payments: 18 of 18 pass** (runner count 22 with sub-tests).

**Existing suites vs baseline** (baseline run on the same fresh copy BEFORE the module existed; after: one run with the module installed):

| Suite | Baseline | With pb_fund_payments |
|---|---|---|
| pb_pay_delivery | 48 tests, 0 failed | 48 tests, 0 failed |
| pb_approval_config | 184 tests, 4 failed | 184 tests, 4 failed |

The 4 are the same in both runs (failure set equal): `TestApprovalStaticContract.test_the_look_invents_no_colour_and_carries_no_gradient`, `TestVietnameseIsComplete.test_u13_the_catalogue_covers_the_whole_exported_template`, `TestP7Vietnamese.test_z06d_every_p7_block_is_filled_in`, `TestP7Vietnamese.test_z06e_no_p7_translation_loses_a_placeholder` — pre-existing on 19.1.

**Static gates:** py_compile, XML parse, pyflakes (only the usual `__init__` import notes), PO parse gate (416 rows each), "Odoo" grep over XML / JS / SCSS / msgstr — clean.

**Browser walk** (Claude in Chrome, local copy, server on 127.0.0.1:8931 with jobs off; a small seeded world: DEMO Monthly payroll scheme typed like the demo world, 6 DEMO people, a finished October 2026 regular run + an Extra run, one person's pay on hold; a one-step Finance route decided by a second local login `demo.finance`):
1. Board empty: the first-run card. "Suggest from my pay schemes" proposed 5 funds (Health, Loan Repayment with its note, Personal Income Tax, Social, Unemployment); Health and Unemployment put together with Social, Loan untick, renamed "Social insurance office" / "Tax office" → "2 funds added". Tax office edited (bank details, reference) and saved.
2. "Work out what we owe for October 2026" → "October 2026 worked out: 2 new." Social insurance office 35,360,000 ₫ (11,602,500 employee + 23,757,500 employer, 6 people — hand-checked: 10.5 % and 21.5 % of 110,500,000); Tax office 5,150,000 ₫, 5 people (includes the Extra run and the held person).
3. Inside the Payroll hub ("Funds & tax" tab): same board; the lens scrolls (scrollTop 600 of 1,228). Palette: "fund and tax" finds "Fund and tax payments · Payroll".
4. Drawer → Send for approval → "Waiting for approval — with DEMO Hoa Finance". As demo.finance in Approvals: card "Pay Social insurance office · October 2026 · 35,360,000 VND · 6 people", tick box disabled ("Money leaves the company with this one, so it is approved on its own."), detail table per item → Approve.
5. As admin: Record the payment with 35,350,000 → "Mark as paid" disabled until the receipt was attached; pressing it without a note → "The amount paid is not what is owed. Say why"; with a note → "Marked as paid. The receipt is kept with it." Drawer shows the proof, "Paid −10,000 ₫ against what was owed" and the note. "See the payslip lines" opened 36 lines inside the Payroll rail. Excel downloaded (200).
6. Console: no error from this module. The only errors were the Pay runs lens refusing the local admin (no scheme rights on that copy — ledger PRD-6), present before this module was opened.
Fixed during the walk: the main buttons were drawn as plain (they need `pbim-btn primary`); the filter panel was laid out over the empty month and said "Nothing matches" after the first work-out (now laid out again after each work-out); the payee editor's currency list missed an inactive scheme currency (VND on a USD company) and showed USD; drawer dates now read "15 Nov 2026".
Not walked: Vietnamese / Indonesian screens (PO gate only), a true phone width, the two-signature default route in the browser (covered by T8).

## 4. Safety rails

| Rail | Verdict |
|---|---|
| R1 owed is derived | Met. Figures written only by the work-out / refresh (context token); `create`/`write` refuse anything else (T16). The paid amount and the difference note are the only human figures. |
| R2 never two currencies | Met. Rows are per (payee, month, currency); the currency is the scheme's; board totals and Excel blocks per currency (T5, T14). |
| R3 approved/paid immutable | Met. Work-out never touches their figures (latest reading beside them, T7); reopen needs a reason and a new approval (T12); receipt required to mark paid (T9). |
| R4 idempotent work-out | Met. Partial unique index on live (payee, month, currency); second press creates nothing (T6). |
| R5 silent install | Met for data, jobs and email (T18). Visible beyond the board and palette: the catalogue row "Fund and tax payments" and its default route in the Approval Matrix (the handover's own §1.3 asks for it). |
| R6 same reading as reports | Met. Lines are read by the component link (payslip's scheme + line code) and counted by size, as the run's Deductions / Employer cost count them; identity with the run totals and with `pb_pay_totals` (T15). |
| R7 words | Met. vi + id (360/362), PO gate, no vendor name in any user-visible string. |

Design bar (owner, verbatim: "extreme WOW, best in class"): hero = the one press that fills the month and says what moved, plus the suggestion that sets the funds up from the schemes; every state designed (locked, loading, error + Try again, first run, month not worked out, no finished payslips, no match, nothing left to suggest, waiting with whom, changed since approval, past due, paid late, cancelled); motion with purpose (drawer slide, cards fade in, reduced motion respected); keyboard: rows open with Enter, Esc closes the innermost layer. Not built: bulk moves (a money process is decided one at a time).

## 5. Deviations

- **D1 — area.** The handover says "area Payroll"; the catalogue has no such area. The row sits in **Money out** with the bank file and the payment release (where money leaving the company lives).
- **D2 — approval is not gated on the money role.** The release's `_approval_apply` calls `require_pay()`; here it does not: approving moves no money, and the default route's last signature (Country director) usually holds no payroll role, so the approval would be "approved but could not be carried out". The money role is required to work out, send, record the payment and reopen.
- **D3 — a refusal sends the row back to "To pay"** (the money is still owed) instead of a "turned down" state.
- **D4 — a "to pay" row nothing is owed on any more is cancelled** by the next work-out (kept for history, not deleted).
- **D5 — the walk used a small seeded world** (the full demo world does not fit on the local disk) and a one-step Finance route (the default two-signature route is proven by T8).
- **D6 — a deduction "refund" line** (a positive amount on a deduction item) is counted by its size, as the run's figures count older schemes.

## 6. Owner questions (plain words)

1. **Who approves a payment to a fund?** It ships with the same two signatures as releasing salaries (Finance, then the Country director). Would you rather one signature (the Head of pay), since the amounts come straight from approved payslips?
2. **Insurance in one payment or three?** Payobook suggests one fund per insurance kind (social, health, unemployment); in Vietnam all three go to one office, so the customer puts them together in the suggestion. Should it put same-office items together by default for Vietnam? (That needs country knowledge — postponed with Step 1.)
3. **Late payments** only show on the board ("2 payments are past their due date"). Do you want a reminder message to the pay team before the due date in a later phase?

## 7. Deploy notes (RISKY tier — new module on all five)

- Backups first, rehearse on a clone with jobs and mail off, then `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima` (never `abm`).
- `-i pb_fund_payments` per database. Depends only on modules already installed everywhere (mail, om_hr_payroll, pb_hr_payroll_formula, biz_approval_workflow, pb_approval_config, pb_pay_delivery, pb_payruns, pb_payhub, pb_hub, pb_import_kit, pb_filter_kit).
- The install adds the catalogue row and lays one "Fund and tax payments" route per company (Finance, then Country director) — check each company's Finance and Country director holders afterwards, or the first request blocks with "nobody holds …".
- New JS/SCSS: purge `/web/assets/%`, bump `web.assets.version`, restart.
- Verify: `latest_version` 19.0.1.0.0 ×5; Payroll hub shows "Funds & tax" for a payroll user; palette finds "Fund and tax payments"; board opens empty with the first-run card; console clean.

## 8. Gotchas → ledger

W2B-1 … W2B-5 added to `WDGAP_LEDGER.md` (run-totals detail clause keeps NET-category lines; the engine applies as the last decider so adapter reads need sudo; `SEATED_MODELS` is pb_pay_delivery's own list; a ctx-dependent filter kit needs `defer` + `kit.kw`; `with_company` keeps old allowed companies in tests).
