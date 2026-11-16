# WDGAP W2-D2 — Back pay for past months in this month's pay run: report

Branch `wdgap-w2d2` (from `origin/19.1` @ abc2259b6). Not merged, not deployed, no live
server touched. Handover: `WDGAP_W2_D2_HANDOVER.md`; owner rulings R1, R2, C-6.

**One module changed: `pb_retro` 19.0.1.0.0 → 19.0.1.1.0.** No file of any other module
was edited — the seam needed no hook in `pb_hr_payroll_formula` (§2).

## 1. What was built, per handover item

| # | Item | Built |
|---|---|---|
| 1 | Send for payment | Result screen button **"Pay the difference in the next pay run"** (payroll managers who hold the money role). Pre-check per person, stored as `pb.retro.person` (status + reason): any month "cannot be compared exactly" → not paid automatically ("add a one-off in Updates if needed"); "could not be worked out"; has left (archived or leaving date passed); now paid by another scheme (scheme map, else the person's latest payslip); the scheme pays in another currency now; the scheme has no take-home line; **already paid as back pay by another re-work** (added: see §6 D3); no difference → nothing to pay. Nobody payable → refused with a plain sentence. Payment states on the re-work: `waiting → approved → partly paid → paid` (+ payment cancelled); fully paid **closes the re-work itself**. Withdraw while waiting. A re-work that has been sent is frozen (no Change, no work out again, no cancel, no close while unpaid). |
| 2 | Approval | Process `backpay` ("Back pay for past months", area Pay, money, never bulk) in the one Approvals inbox, ONE step **Head of pay** (`pay_head`, filled from the payroll base manager group — the loan/fund-payment seat). Adapter on `biz.approval.adapter.mixin` + `pb.money.approval.mixin`, cloned from `pb_fund_payments`: context/revision/detail read under sudo (W2B-2), own seat hook (`seat_user_ids`, W2B-3), inbox detail = per person take-home difference + months, not-payable people listed with their reason. Makers (`create_uid`, worked out by, sent by) go to the engine, which applies each route's own independence rule (rize: off). Seeded by `post_init_hook`, by **migration 19.0.1.1.0** on databases that already have `pb_retro`, and on every new company. |
| 3 | Entries | `pb.retro.backpay`: person × pay item × past month, signed difference, currency, scheme, the re-work, the past payslip, the item's typing (code, category, salary rule, pay role, "included in another total"), `band_amount` (see §2c), state open / reserved / paid / cancelled, the payslip and run that took it. Made on approval from the STORED `pb.retro.line` rows — never worked out again. Create/write only through the module's own token; never deleted (cancel with a reason). |
| 4 | Into the pay run | §2. Next REGULAR run of the same scheme (top-up, Extra, a payslip outside any run, and any payslip of the re-worked months never take it). One line per pay item, months collapsed: "Back pay · Income tax · Aug–Oct 2026". Paid once, never below zero, golden. |
| 5 | Downstream readers | §3 table. |
| 6 | Screens | Result view: "What happens next" follows the payment; **Payment strip** (state badge, with whom it waits, take-home for N people, in which pay run, per person: where their back pay is — waiting for approval / will be paid in the next pay run / in pay run X / paid in X / part waits so take-home is not below zero — plus a fold with the not-payable people and their reasons, Withdraw, Cancel the back pay). Board: glance item **"waiting to be paid"** (amber only when not zero), list badge, filter "Payment" + saved view. Excel: third sheet **"Payment"** (per person, past month, pay item, difference, where it is, pay run). Pay run review: a per-payslip note (both review screens show it under "Good to know — nothing to do"). ⌘K unchanged. |
| 7 | Undo | "Cancel the back pay" (all, or one person) with a reason: cancels approved back pay no pay run has taken, AND back pay sitting in a payslip that is not finished (a reopened run) — it is taken out of that payslip at once (lines removed, take-home put back). Paid back pay: only by reopening its run (its entries go back to "in a pay run"; then it can be cancelled). No raw deletes. |

## 2. The seam — exactly where and why it is safe

**a. Where.** The engine has exactly two producers of payslip lines from formulas, and
each one deletes every line of the payslip before writing:

* `hr.payslip._create_payslip_lines_from_formulas` (`pb_hr_payroll_formula/models/hr_payslip_formula.py:922`,
  `self.line_ids.unlink()` at :927) — compute, recompute without a file, application-data
  mode, loans' second pass, the demo division path;
* `hr.payroll.import.batch._compute_and_create_payslip_lines` (`payroll_import_batch.py:3887`)
  — runs with a pay data file and their "recalculate" (which unlinks the lines first,
  `hr_payslip_formula.py:1158`).

`pb_retro/models/retro_backpay.py` overrides both: `super()` first, then
`hr.payslip._pb_backpay_apply(fresh=True)`. **No hook was added in `pb_hr_payroll_formula`.**

**b. Why it is safe.**
* Nothing is fed to the formulas: the back pay is appended after them as fixed lines, so
  this month's tax, insurance and take-home formulas neither see it nor tax it again
  (B03, B04).
* Idempotent: the producer has just removed every line, so a recompute replaces and never
  doubles (B09, B21, B24). The reservation follows the same call.
* Golden: a payslip whose person has no back pay waiting and that holds none gets nothing
  written at all — one indexed lookup (`employee_id`, `state`) and return (B01 compares the
  lines, the take-home, both band readings and the SQL writes with the seam switched off,
  for regular, top-up and Extra runs and a negative-sign scheme).
* Row lock `FOR UPDATE` on the entries a payslip takes; a reserved entry is taken only by
  the payslip that holds it (B09: a second regular payslip of the same month takes nothing).

**c. The two places a plain "same typing" line would have been read wrongly** (found and
fixed inside `pb_retro`):
1. Take-home is read from ONE line everywhere (`pb_net_line()` returns the first net line:
   bank file, review flags SQL, My Payobook, PDF, loans' floor). A second net line would
   never be read, so the take-home difference is **added to the payslip's own take-home
   line**; `hr.payslip.pb_backpay_net` records how much (taken out again on strip).
2. Deductions and employer cost are counted by SIZE per line (`abs()`), so a line that
   LOWERS them (a person who owes money: less insurance, less tax) would count as more.
   Each back-pay line carries `pb_backpay_band_amount` = |would be| − |was| and the band
   readers count that instead — only for payslips that hold back pay:
   `hr.payslip.line.pb_pay_totals` (ORM), `hr.payslip.run._pb_slip_totals` (its SQL twin,
   affected payslips rebuilt with the same bucket rule and the same signed-deduction
   decision) and `pb.fund.payment._pb_read`. B05 proves it for a positive-sign scheme and
   B05b for a scheme that writes deductions as negative amounts (the demo world's way).

**d. Never below zero.** After the formula lines exist, months are taken whole (a month's
earning never without its tax): every month that RAISES take-home first, then the months
that lower it, oldest first, while take-home stays at or above zero; the first month that
does not fit and every later one wait (`waited`) for the next regular run. One pass, no
loop, no recompute (the lines are fixed, so the arithmetic is exact). B06, B06b. It runs
inside the line producer, i.e. before the loans' floor (PR-E); a loan cut then sees the
take-home with the back pay in it.

## 3. Everything downstream reads the lines once

| Reader | Result | How |
|---|---|---|
| Gross / deductions / take-home / employer cost on a payslip (`pb_pay_totals`) | correct, both signs | ORM override (B02, B05, B05b) |
| Pay run figures and the people table (`_pb_slip_totals`) | correct, both signs | SQL twin override (B02, B05, B05b); run gross − deductions = take-home (B05) |
| Bank file / take-home everywhere (`pb_net_line`, `pb_net_amount`, Pay & deliver `_pb_net_amount`) | includes the net effect | added to the one net line (B17) |
| Pay & deliver left out / held / paid another way | as any payslip | nothing special: the payslip is an ordinary payslip with more lines |
| Year-to-date (W2-A `history.ytd/qtd/mtd`) | counted in the month PAID | `hr.formula.config._pb_history_read` adds the paid entries per code (B15); untouched rows stay unparsed |
| Updates year-to-date sheet (`pb_updates._ledger`) | counted in the month paid | it sums payslip lines by code — the back-pay lines carry the item's code (no change needed) |
| Fund payments owed (W2-B) | includes back-pay tax and insurance under the right fund, a lowering lowers it | `_pb_read` override (B16) |
| Payslip PDF (themed) | own block **"Back pay for past months"** (each line + "Take-home from back pay", subtotal = take-home effect); every pay item prints this month's own figure; the big net card includes it | `_themed_payslip_render` override (B18) |
| A later re-work of the month that PAID back pay | compares exactly | `_RetroWork` leaves back-pay lines and `pb_backpay_net` out (B23) |
| My Payobook payslip page | back pay shows as its own lines ("Back pay · … · Aug–Oct 2026") in the line list; take-home includes it | no separate block: the page is `pb_me_portal`'s template (C-3, no edit) — **STOPPED, see §8** |
| Pay run review | a quiet note per payslip "Back pay for Aug–Oct 2026: +13,694,400 ₫ take-home" (+ "… waits for the next pay run so take-home is not below zero"); never a flag of its own | `pb_review_flags` extension (B06, B17). A run-level chip "Includes back pay for 3 people" needs a change in the pay run screens (`pb_payrun_wizard` / `pb_payruns`) — **STOPPED, §8** |
| Insights (Explorer) | reads the lines (C-5: nobody edits it) — a back pay that LOWERS a deduction is counted by its size there | **left, §8** |
| Payslip designed page layouts (`payslip_layout_html` / document pages) | the value of a pay item quoted inside a designed layout includes its back pay | only the section/line render was adjusted; **left, §8** |

## 4. Tests

New file `pb_retro/tests/test_wdgap_w2d2_backpay.py` (B01–B27). Local copy `wdgap_w2d2_t`
(= `upd_p6_t_tpl` brought to `origin/19.1` with `-u all`, `pb_loans` / `pb_fund_payments` /
`pb_retro` installed), dropped at the end.

| # | Case | Result |
|---|---|---|
| B01 | R1 golden: no back pay → regular, top-up, Extra payslips: lines, take-home, ORM and SQL band readings identical with the seam switched off; no SQL write to payslip, line or entry; a negative-sign scheme too | pass |
| B02 | pay rise Aug–Oct: one line per item, the past months' figures, labels, typing = the item's; take-home = November + back pay; every band reading moves by exactly the re-work's figures; reserved → paid; re-work paid and closed | pass |
| B03 | progressive tax: back-pay tax = the past months' tax differences; re-taxing the lump in November would charge > 1,000,000 more | pass |
| B04 | insurance ceiling: back-pay insurance stops at the cap per month | pass |
| B05 / B05b | negative difference (owes): deductions and employer cost go DOWN in ORM and SQL readings; run balances; negative-sign scheme | pass |
| B06 / B06b | never below zero: oldest months first, the rest waits and December takes it; a payslip that cannot pay anything owed takes nothing; a rise month is taken first so a cut month fits | pass |
| B07 | two people, one cannot be compared exactly → not payable with its reason; only the other gets entries | pass |
| B08 | left; moved to another scheme; nothing to pay → refused | pass |
| B09 | paid-once matrix: compute / recompute (identical, not doubled) / second regular payslip of the month (takes nothing) / done → paid / set back → held, re-work reopened / recompute / cancel → open → taken by another payslip / delete → open / run delete → open | pass |
| B10 | Extra, top-up, a payslip outside any run, a payslip of the re-worked months: never | pass |
| B11 | another scheme, another currency: never | pass |
| B12 | R3: lines on payslips = approved entries per person, item, currency; take-home part = net entries | pass |
| B13 | real route: one step Head of pay, money (never bulk), detail rows, no vendor name; somebody without the seat refused; the seat reads that re-work and nothing else; approve → entries; withdraw; send back; the sender who also holds the seat cannot approve their own | pass |
| B14 | migration on a company without the route → route published (one step), twice = once, fresh install does nothing more; every existing company has it | pass |
| B15 | year-to-date counts back pay in the month paid; other months' rows untouched | pass |
| B16 | fund owed (insurance office, tax office) includes back pay, lowered by a negative one; a month without back pay reads its lines | pass |
| B17 | bank / take-home readers include the net effect; review note, never a flag of its own | pass |
| B18 | PDF block, items at this month's figure, net card includes it; no back pay → no block | pass |
| B19 | rights: officer, plain employee, portal: no read of entries / people; no re-work; refused on the board; writes/creates/deletes of entries refused; another company sees nothing | pass |
| B20 | R8 silent: nothing until a re-work is approved; no job; glance 0 | pass |
| B21 | R10 deterministic | pass |
| B22 | R6: no write to rules, schemes, rule versions or past payslips while a run takes back pay | pass |
| B23 | a re-work of the month that paid back pay compares exactly | pass |
| B24 | pay data file producer takes it the same way; recalculate replaces | pass |
| B25 | undo: reason required; frozen re-work; cancel one person (not taken); a finished payslip cannot; reopened → cancelled and taken out of that payslip; re-work payment cancelled with its reason | pass |
| B26 | screen: Payment strip states and words, board glance and filter, list badge, Excel Payment sheet (no vendor name) | pass |
| B27 | a second re-work of months already back-paid: the paid change is listed as paid back (no difference); a what-if on such a month is "already paid by another re-work" | pass |

**`pb_retro`: 57 tests in the runner's count, 0 failed, 0 errors** (D1's 21 + W2B seam +
the 27 above with sub-tests).

**Regression suites** (`/pb_retro,/pb_hr_payroll_formula,/pb_payruns,/pb_payrun_wizard,/pb_loans,/pb_fund_payments,/pb_pay_delivery`,
same database; baseline with pristine `origin/19.1` copies of these seven modules first on
the path, run before any edit):

| Run | Tests | Failed | Errors |
|---|---|---|---|
| Baseline | 1,135 | 9 | 0 |
| After (branch, `pb_retro` 19.0.1.1.0) | 1,164 (+29 new) | 9 | 0 |

Baseline failure set (all known, unchanged code): TestRd49SyncCost ×2, TestRecordsR1OneTime
07b, TestSchemeCtxCurrency 04 (formula baseline since PR-A), TestRunScreen ×5 (close week,
PRB-W6). **After: the identical 9** (`diff` of the two failure lists: empty).
Per module after: pb_hr_payroll_formula 835, pb_payrun_wizard 155, pb_payruns 185,
pb_pay_delivery 64, pb_loans 42, pb_fund_payments 36, pb_retro 57 (runner counts).
`pb_retro` was run once more on its own after the walk fixes (§4a): see the line below.

After the walk fixes, `/pb_retro` alone on the walked copy: 51 tests, 1 failed — B01's "no back pay exists anywhere" count, which the walk's own back pay broke; the count was scoped to the test company and B01 re-run alone: pass. (B20 got the same scoping.)

Static gates: `py_compile` + pyflakes on every changed Python file (only old warnings);
`node --check` on the board JS; the board XML parses; vendor-name grep over every added
user-visible line and msgstr: clean; PO gate with the framework's `PoFileReader`: **503 rows
in each of vi_VN / id_ID, 0 empty, 0 placeholder mismatches** (113 new msgids each, the
existing entries reused given their new occurrences).

### 4a. Browser walk

Local copy, server on `w2d2.localhost:8785` with jobs off (a `*.localhost` name: the
other builders' local servers on `127.0.0.1` share its cookies — new ledger note in W2D2-6).
Seed: company "DEMO Walk Co", scheme "DEMO Office — End-Month" (basic, meal allowance,
capped insurance, progressive tax, take-home, employer insurance), DEMO An Nguyen / Binh
Tran / Chi Le, finished August–October runs, An's rise 30,000,000 → 36,000,000 from
1 August entered after the payslips; a second login "DEMO Hoa Nguyen (Head of pay)".

1. Re-work (made and worked out through the board's own server calls; the guided New
   re-work was walked in D1): result shows +13,101,000 ₫ take-home for An; "What happens
   next": "Nothing has been paid or changed. Pay the difference in the next pay run, or add
   it as a one-off in Updates." + **Pay the difference in the next pay run**.
2. Pressed it: toast "Sent for approval — with DEMO Hoa Nguyen (Head of pay)."; Payment
   strip "Waiting for approval · With DEMO Hoa Nguyen (Head of pay). Take-home +13,101,000 ₫
   for 1 person", An "Waiting for approval", fold "2 people not paid automatically or with
   nothing to pay" (Binh and Chi: no difference), Withdraw offered; the re-work's Change /
   Work out again are gone.
3. As the Head of pay, Approvals: card "Back pay · DEMO Office — End-Month · Aug 2026 – Oct
   2026", 13,101,000 VND, 1 person; drawer table "Back pay in the next pay run" (An, Aug–Oct
   2026, +13,101,000 ₫, Next pay run), chips, the note on tax; **Approve** → "This one is
   finished".
4. November regular run computed (shell, through the payslip line producer): An's payslip
   has four lines "Back pay · Basic pay · Aug–Oct 2026" 18,000,000, social insurance
   1,890,000, income tax 3,009,000, employer insurance 3,150,000; take-home 30,210,000 +
   13,101,000 = **43,311,000**; Binh and Chi untouched. Payment strip: "In pay run DEMO Office
   November 2026"; "What happens next" → "Approved. The next regular pay run …".
5. Payslip print (themed report, HTML): November's own lines (basic 36,000,000, tax
   2,740,000, take-home 30,210,000), then the block **BACK PAY FOR PAST MONTHS** with the four
   lines and "Take-home from back pay 13,101,000", subtotal 13,101,000; net card 43,311,000 ₫.
6. Run finished: review note "Back pay for Aug–Oct 2026: +13,101,000 ₫ take-home"; the
   re-work reads **Paid**, closed by itself; An "Paid in DEMO Office November 2026"; "What
   happens next": "The back pay is paid. Those months stay as they were …"; board glance
   "0 waiting to be paid" (amber "1" while it waited), list badges Worked out / Approved.
7. Console: no error on the board, the result or Approvals.

Fixed during the walk (commit after the feature): the Payment strip ran "…(Head of pay).Take-home"
together (spacing); at 614 px "What happens next" squeezed its text beside the long button
(it now wraps); the approval table's last column read "Paid" over "Next pay run" (now "Paid
in"); the board's own sub-title still said "Nothing is paid or changed" (now says the
difference can be paid once approved).

Not walked: Vietnamese / Indonesian screens (PO gate only), the PDF file itself (no PDF
printer on this Mac — the HTML of the same report was checked), My Payobook (shows the lines
as its line list; see §8), a true phone width.

Seen, not this phase: the re-work board's filter panel reads "Nothing matches “” here" on this
copy (the panel's sections arrive with `shown: false`; it is the filter kit's own state, the
same sections plus the new "Payment"); the HTML report's browser title is the framework's
default ("… Report") — the report route's page, not `pb_retro`.

## 5. Rails

| Rail | Verdict |
|---|---|
| R1 golden | Met — B01 (and every pre-existing suite, §4). |
| R2 paid once | Met — B09, B06, B25 (compute / recompute / reset / reopen / finish / cancel / delete / run delete; row lock). |
| R3 lines = entries | Met — B12, B02. |
| R4 currencies / schemes | Met — B11; entries carry the scheme's currency, every roll-up keyed by currency. |
| R5 never below zero | Met — B06, B06b. |
| R6 nothing past written | Met — B22; the past payslip is only read. |
| R7 portal | Met — B19 (no read of entries for employee or portal logins); an employee sees back pay only as lines of their own payslip through the payslip pages' ownership guard. |
| R8 silent | Met — B20; install adds only the catalogue row and one route per company. |
| R9 Extra / top-up | Met — B10. |
| R10 determinism | Met — B21. |

## 6. Deviations

* **D1 — the take-home item is not its own line**: its difference is added to the
  payslip's own take-home line (§2c-1). Every other item is its own line.
* **D2 — band readers extended** for payslips with back pay (ORM, SQL twin, fund payments,
  year-to-date, PDF), all inside `pb_retro` by inheritance (§2c-2). A payslip without back
  pay goes through the untouched code.
* **D3 — "already paid by another re-work"**: a payslip whose difference a live re-work
  already pays is never paid automatically by a second one (its difference would be
  measured from the stored payslip again and pay twice); a contract change a live re-work
  applied is shown as "already paid back" on the next re-work. (Not asked; found while
  testing.)
* **D4 — "next regular run"** = a regular-run payslip of the same scheme, company and
  currency whose period starts AFTER the last re-worked month.
* **D5 — never below zero is per whole month** (a month's earning, tax and insurance stay
  together); a single month that does not fit waits whole.
* **D6 — cancel also works on back pay in a reopened run's unfinished payslip** (taken out
  of it at once), so "reopen the run" is the way back after a run finished, as the handover
  says, and the lines can never disagree with the entries.
* **D7 — approval apply is not gated on the money role** (as fund payments, W2-B D2):
  nothing leaves the company at approval; the money moves with the pay run's own approval.
  Sending is gated (payroll manager + money role).

## 7. Contracts other phases rely on (J2 / S8 "a change starting on a date already paid")

* Make and work out a re-work: `pb.retro.review.create({...})` + `action_work_out()` (D1).
* Send it: `pb.retro.review.action_send_for_payment()` → the `backpay` route.
* `pb.retro.review.pay_state` ∈ waiting / approved / partly / paid / cancelled;
  `action_withdraw_payment(reason)`, `action_cancel_backpay(reason, employee_ids=None)`.
* Entries: `pb.retro.backpay` (state open / reserved / paid / cancelled; `payslip_id`).
* Payslip: `hr.payslip.pb_backpay_net` (take-home part), `pb_backpay_note`;
  line: `hr.payslip.line.pb_backpay`, `pb_backpay_band_amount`.
* `hr.payslip._pb_backpay_apply(fresh=True)` is called after each line producer; any new
  line producer must call it too.
* No other phase writes back-pay inputs (C-6).

## 8. Left for later / stopped readers (out-of-lane)

1. **My Payobook payslip page block** "Back pay for past months": the page template is
   `pb_me_portal`'s (`portal_payslip_page`, C-3). Today back pay shows as its own named lines
   and in the take-home; the PDF downloaded from there has the block. Needs the
   orchestrator's prep commit (one block on the template).
2. **Run-level chip** "Includes back pay for 3 people" on the pay run review: needs a line in
   `pb_payrun_wizard`'s review step / `pb_payruns`' run screen. Today each payslip carries the
   note (the drill-in already exists: "Good to know — nothing to do").
3. **Insights (Explorer)** counts a back pay that lowers a deduction by its size (C-5).
4. **Designed payslip layouts** quote an item's value with its back pay inside.
5. Big-change flag: a large back pay raises take-home and the existing "Net pay up N% on
   <month>" flag fires (correct, but not about back pay).
6. Demo: no back pay exists anywhere; nothing to seed.

## 9. Owner questions (plain words)

1. **A person who owes money and cannot pay it all this month**: today whole months wait for
   the next pay run (never part of a month). Fine, or should part of a month be taken?
2. **Back pay for someone who has left**: today it is not paid automatically (the screen
   says so; the pay team can use a one-off in Updates or the final settlement). Should it
   go into their final payslip instead?
3. **Approval**: one sign-off by the Head of pay, like loans and fund payments. Keep?

## 10. Deploy notes — RISKY tier (pay calculation)

* `-u pb_retro` on all five (`payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`;
  never `abm`). New dependencies are installed everywhere already (biz_approval_workflow,
  pb_approval_config, pb_pay_delivery, pb_fund_payments). New tables `pb_retro_person`,
  `pb_retro_backpay`, `pb_retro_review_seat_rel`; new columns `hr_payslip.pb_backpay_net /
  pb_backpay_note`, `hr_payslip_line.pb_backpay` (partial index, NULL on every existing
  line) / `pb_backpay_band_amount`; new review columns. No backfill.
* Migration 19.0.1.1.0 lays the "Back pay for past months" route (one step, Head of pay) on
  every company; check the Head of pay holder per company afterwards (W2BM-2: the same seat
  approves loans, fund payments, awards, bands).
* JS / XML / SCSS changed: purge `/web/assets/%`, bump `web.assets.version`, restart. PO gate.
* **Rehearsal on a rize copy should prove**: (a) recompute of a real regular run old vs new
  = 0 differences (no back pay exists: the golden on real schemes and on pay data file runs);
  (b) run totals `_pb_slip_totals` identical; (c) a test re-work → send (fast lane on the
  copy) → a draft regular run of the next month takes it: lines, take-home, run balance,
  fund owed; then delete that run on the copy and see the entries back to "waiting".

## 11. Worked example (one person, three months)

Pay rise 44,000,000 → 50,000,000 from 1 August, entered after August–October were paid.
Insurance base is capped at 46,800,000 (10.5 % employee, 17.5 % employer); tax ladder
5 / 10 / 15 / 20 % after an 11,000,000 allowance.

| Each past month | Was | Would be | Difference |
|---|---|---|---|
| Basic pay | 44,000,000 | 50,000,000 | +6,000,000 |
| Social insurance | 4,620,000 | 4,914,000 | +294,000 (cap) |
| Income tax | 4,026,000 | 5,167,200 | +1,141,200 |
| Take-home | 35,354,000 | 39,918,800 | +4,564,800 |
| Employer insurance | 7,700,000 | 8,190,000 | +490,000 |

November's regular payslip then shows its own November lines (take-home 39,918,800) and
four back-pay lines: "Back pay · Basic pay · Aug–Oct 2026" +18,000,000, social insurance
+882,000, income tax +3,423,600, employer insurance +1,470,000 — and take-home
39,918,800 + 13,694,400 = **53,613,200**. Had the 18,000,000 been added to November's pay
as a lump, November's tax formula would have charged 3,600,000 tax on it; the back pay
carries the 3,423,600 worked out for those months.

## 12. Gotchas → ledger

W2D2-1 … W2D2-6 added to `WDGAP_LEDGER.md` (one take-home line; abs() per line; the PDF
sums by code; running totals read stored results; double pay by a second re-work; fast-lane
submit runs freeze and apply in one call).
