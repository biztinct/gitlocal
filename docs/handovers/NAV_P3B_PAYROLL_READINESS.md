# NAV P3b — Payroll: readiness on the run cards

Read first: `docs/handovers/NAV_LEDGER.md`; `docs/design/PAYRUN_BOARD_REDESIGN.md` (the board as built 2026-10-11);
`docs/design/payobook-navigation-review-20261019.html` §13 Payroll rows (RUN: readiness checks, deadlines, owners,
workforce-close evidence are **Change**). Owner decisions 2026-10-21: (a) the run cards **show** "changes close in N days ·
paid on <date>" from the Payroll calendar (this reverses the 11 Oct "no pay-day words" ruling, which was made because no
pay-day setting existed; `pb.payroll.calendar.pay_date` now exists); (b) P3b follows P3a. Implementer: Opus.

## 1. Goal

Every run card answers "can this run move, and who must act" in one glance: a short checklist with an owner on each line,
the month's deadlines on the hero, and a workforce-close line that advises but never blocks. Submit, approval and reject
flows stay exactly as they are.

## 2. Verified plumbing (do not re-derive)

| Fact | Where |
|---|---|
| Board payload `get_board_data` (`pb_payruns/models/pb_payruns.py:42-208`); per-run dict `:113-168` with the three checks `balance_ok :134-135`, `balance_gap :136`, `unsourced :137`; `return_note/return_by/return_on`, `prepared_by`, `awaiting_me`, `approval` (chip `_approval_chip_data :225-268`: `step`, `steps[{key,title,status,with,decided_by,decided_on}]`, `with`, `blocked=request.block_reason`), `next_action`, `can_act`; top level `period` from `_period_block :404-440` (`key,label,short,range,date_start,date_end,stage,total,next_label`), `company`, `kpis`. No run owner field; person fields on the run are `pb_prepared_uid`, `pb_return_uid` (`hr_payslip_run.py:183-191`). Run company = scheme's company, payslip company wins (`_run_companies :443-467`). | agent fact-find 2026-10-21 |
| JS: lane flags `payruns.js:263-276`; `route(b) :478-490` ("your turn" / "stuck" / "in progress", "With X"); `delivery(b) :492-517`; `notes(b) :518-528` → `{tone, icon, head, text, next}` (amber sent back; rose unsourced; rose balance); hero decision order `:358-388`. Templates: hero `payruns.xml:34-70` (`.pbr-month :37`, `.pbr-range :38`), card `:289-398` (notes loop `:308-311`, route `:314-322`, delivery rail `:325-331`), peek checks `:441-445`. Styles `payruns.scss` (`.pbr-note :206-211` amber/rose only, `.pbr-route :212-222`, tokens `:5-50`). Class prefix `.pbr-*`. QuietGlance/QuietSteps are NOT used on this board. | |
| "Ready" exists only in Learn: `pb_payruns_learn.py:145-147` (draft + next_action submit + not unbalanced/unsourced); it calls `get_board_data()` (`:76`) so payload keys must stay. | |
| Pay calendar `pb.payroll.calendar` (`pb_comp_ben/models/payroll_calendar.py:35-71`): `month` (1st of month), `cutoff_date` ("Changes close"), `pay_date` ("People are paid"), `company_id` (nullable), `state upcoming/closed`, reminders; `unique(month, company_id)`; `next_cutoff(company_id) :269-276`. Home reads it with `search_read([('month','=',first),('company_id','in',cos+[False])])`, company rows before shared (`home_data.py:443-451`), guarded by `optional()` because the module may be absent. **`pb_payruns` does not depend on `pb_comp_ben` or `pb_close`** (`pb_payruns/__manifest__.py:24-26`): read both through `self.env.get('pb.payroll.calendar')` / `'pb.wf.lock' in self.env`, never a hard import. | |
| Workforce close: `pb.wf.lock` (`pb_close/models/wf_lock.py:74-105`) per **company per day**: `company_id, date, state locked/open, reason, locked_by_id, locked_on`; read helpers `_locked_pairs(company_ids, dates) :200-215` (one sudo query), `_locked_dates :224-228`. The wizard's advisory uses `_close_weeks_in(ds, de)` (`pb_close/models/payrun_wizard.py:62-73`, Mondays overlapping the period) and `_close_week_status(week_start, ds, de, emp_ids) :75-90` (counts only days inside the period; uses `self.env.company`, so call `with_company(run_company)`); a week is closed when `total == 0 or locked >= total` (`:148`); labels "Week of %d %b". Lock writes are gated to attendance manager + payroll manager (`wf_lock.py:68-71`). | |
| Owners: current approvers = open seats' `acting_user_id` on the current step (board `:259-261`; the Inbox names "X, covering for Y" `inbox_facade.py:314-334`). Payroll owner per company = `biz.approval.responsibility` role `payroll_mgr` (`biz_approval_workflow/models/responsibility.py:16-40`, `resolve(company, role, ['']) :90-127`; seeded from the officer group by `pb_payruns/models/approval_seed.py:36-40,151-170`). Attendance owner per employee = `hr.employee.attendance_manager_id`; group `hr_attendance.group_hr_attendance_officer`. | |
| Learn anchors on the card: `pk-card` (repeats), `pk-route`, `pk-reject-why`, `pk-card-actions`, `pk-peek`; new anchors must be registered in `anchors.json` (`"reserved": true`) or `test_anchor_registry.py` 05/08 fail. | |
| Tests that pin the payload: `pb_payruns/tests/test_board_redesign.py:55-65` (period keys), `:74-90` (card keys; **exact** `delivery` key set), `:98-105`; `test_board_currency.py:68,89-122` (regex forbids `money(b.x)` in the template; use `runMoney`/`runGross`); `test_approval_engine.py:608,615,666-673`; `pb_payhub/tests/test_payhub.py:400-428,482` (no `window.confirm`, no emoji, exactly one `!props.embedded`, literal `'division': run.pb_division or ''`). | |

## 3. Design (R11 bar applies; plain words; Lucide; no "Odoo")

### 3.1 Hero deadlines
Under `.pbr-range` add one line `.pbr-deadline`: **"Changes close in 4 days (Fri 24 Oct) · People are paid on Fri 31 Oct"**. Past cut-off: "Changes closed Fri 24 Oct · People are paid on Fri 31 Oct"; past pay date: "Paid on Fri 31 Oct" in green once every run of the month is paid, else amber "Pay day was Fri 31 Oct". No calendar row: the line is absent (not "—"). Multi-company board: use the company picked by the division/company context the board already uses for `company`; if none, the shared row. Payload: `period.cutoff`, `period.pay_date`, `period.cutoff_in_days`, `period.pay_in_days` (ISO strings / ints or null); add the four keys to the `test_board_redesign.py:55-65` expectation.

### 3.2 Card checklist
Replace the ad-hoc notes list with a **checklist block** `.pbr-checks` on every non-done card (Done cards keep the delivery rail only). Each line: icon · sentence · owner chip · tone. Lines, in this order, only when relevant:
1. **Sent back by Linh: "<return_note>"** (amber) — owner: `prepared_by` (the person who must fix). Existing.
2. **3 payslips have no source data** (rose) — owner: `prepared_by` if set else the company's Payroll manager (responsibility `payroll_mgr`, first user; "Payroll team" if none). Existing check, now with an owner. Next: "Open the payslips" (existing door).
3. **Figures do not add up (gap ₫1,200,000)** (rose) — same owner. Existing.
4. **Attendance week of 13 Oct not closed** (amber, advisory) — owner: the attendance manager of the run's company (first `hr.employee.attendance_manager_id` among the run's employees that is set; else "Attendance team"). One line per open week, max 2 then "+N more weeks"; absent when `pb_close` is not installed or all weeks are closed. Next: "Open Workforce › Close" (door `pb_workforce` lens `close`). **Never blocks**: Submit stays enabled; the line says "advice" in the tooltip.
5. **Waiting for Nam (covering for Hoa)** (indigo when "your turn", grey otherwise) — existing route block stays as is; do not duplicate.
When nothing is open on a draft, the block shows one green line: **"Ready to send in"** (the Learn rule: draft, submit allowed, no rose lines). When `awaiting_me`: "Your turn: decide" stays the route's job.

Payload: per run `checks: [{key: 'sent_back'|'unsourced'|'balance'|'close_week', tone, text, owner: {name, uid} | null, next: {door key}|null, advisory: bool}]`, `ready: bool`. Keep the old keys (`unsourced`, `balance_ok`, `balance_gap`, `return_note`…) for Learn and tests; `notes(b)` in JS reads `checks`.

### 3.3 Owner chips
`.pbr-owner`: avatar initials + first name; tooltip full name; for the current user: "you" lit in the brand tint. Click opens nothing in P3b (no new verbs).

### 3.4 Quick look
The peek (`:441-455`) lists the same checklist with full sentences and the owner's full name, plus "Weeks closed 3 of 4" when the close line exists.

### 3.5 Performance
One query for locks per board load (`_locked_pairs(all run company ids, all days of the period)`), one `search_read` for calendar rows, one `resolve` per company for the payroll owner, and one read of `attendance_manager_id` grouped per company. Measure the board load before and after on the demo DB (≥ 40 runs) and report the delta; stay within +150 ms.

### 3.6 Learn and Access
Anchors `pk-checks` (repeats), `pk-deadline`, `pk-owner` reserved in `anchors.json`. Lesson station `runpayroll`/`payruns` outline: one sentence on the checklist and one on the deadline line (EN+VI) in `data.js`; practice replica `payruns` in `screens.js` draws a checklist and the deadline line from fixture data (it is a replica screen; update it so the lesson matches). Regenerate; `--check`; .po unchanged; bump `pb_learn`. Access: no change; confirm Screens lens unchanged.

## 4. Non-goals
No new models; no run owner field; no blocking; no change to Submit/approve/reject, delivery rail, or the Learn "ready" rule; no Compliance BANK move; no readiness screen elsewhere.

## 5. Tests
Python (`pb_payruns/tests/test_readiness_p3b.py`): period deadline keys with/without a calendar row and past/future dates; checklist lines for each state incl. owner resolution fallbacks; close line present/absent (with `pb_close` installed in the test DB; absent when a week has no days in the period); `ready` true only for a clean draft; payload still passes `test_board_redesign.py`, `test_board_currency.py`, `test_approval_engine.py`, `pb_payhub/tests/test_payhub.py`; Learn `pb_payruns_learn.py` unchanged behaviour; anchor registry tests. Chrome (local): hero line in the three date states; a card with sent-back + unsourced + open week shows three lines with three different owners; a clean draft shows "Ready to send in"; Submit works with an open week; peek lists the lines; Vietnamese fits; console clean; board load time delta reported.

## 6. Deploy (after Fable's go) — NORMAL tier
`-u pb_payruns,pb_learn` (add `pb_payhub` if its tests or templates change), p0clone first then the three; PO gate; asset signal + purge + version bump; **bundle warm-up curl per DB**; cron snapshot; push after.

## 7. Report
`docs/handovers/NAV_P3B_REPORT.md` as for P3a; stop at the deploy gate first.
