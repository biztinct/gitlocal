# WDGAP PR-B — Loans and salary advances with a running balance: report

Branch `wdgap-prb` (from `origin/19.1` at `d3fba29ea`). New module **`pb_loans` 19.0.1.0.0**.
Not merged, not deployed. No other module's file was edited (no seam line needed).

## 1. What was built

| Part | Where | What it does |
|---|---|---|
| The record | `models/loan.py` | `pb.loan` (person, company, kind Loan / Salary advance, amount, currency, why, first pay month, plan "amount each month" or "number of months" — the other worked out in whole currency units, last instalment = remainder; if the person leaves: take the rest / leave it open; states draft → waiting → running ⇄ paused → closed, + cancelled, refused). Stored computes `repaid` / `balance` from paid lines only (R3); `in_payrun`, `next_amount`, `next_month`, `months_left`. `pb.loan.repayment` (pay month, amount, payslip, run, state reserved / paid / released, kind payroll / manual, why, reference). Partial unique index: one live payroll line per loan + pay month (R1). Repayment writes need a server-only token (R3). What was agreed is frozen once sent. |
| Approval | `models/loan_approval.py`, `data/approval_process.xml` | Process `loan` (area People, `money=True` → never "approve selected"). Chain shim like awards: send in → Waiting for approval; route done → Running. Default route **Head of pay** laid for every company at install (`post_init_hook`) and for every new company (`res.company.create`). Inbox detail chips: amount, plan sentence, if the person leaves. |
| Pay run takes it once | `models/loan_payroll.py` | Clone of `pb.updates.oneoff` paid-once: own token `pb_loans_token` (context token + cursor cache), wrappers on `_pb_compute_sheet_with_formulas`, `action_recompute_formula_lines`, `hr.payroll.import.batch._create_payslip`; seams `hr.payslip._get_formula_input_values` and `_transform_data_to_formula_inputs` (both call `super()` first, forward provenance, via `loan_repayment`). Reserve on compute, paid on done/paid, released on cancel / delete / run delete / recompute without it; a done payslip set back holds it again. `FOR UPDATE` lock on the loans when a real payslip computes + a write-date touch so a concurrent run retries. Only `regular` runs, never a mid-month scheme, only the scheme the scheme map says pays the person (no answer = yes). Instalment = min(plan, amount − paid − held elsewhere); several loans = one summed input, one line each; paused = skipped. Leaving month (departure date inside the period) + "take the rest" = whole balance. |
| Which pay item | `hr.formula.config.pb_loan_rule_id` "Loan repayments go into" | An input money pay item of the scheme; fed as a positive amount, the scheme's formula decides the sign. On the scheme form and in the board's Set up (payroll managers only). Application-data schemes: a rule keyed `loans.instalment`. |
| Application data | same file | Typed source `loans.instalment` in `_application_source_catalogue` / `_application_domain_values`; reserved in `hr.payslip._application_resolve_inputs` from the evidence amounts (see deviation D1). |
| Nothing silent | `models/loan_review.py` | Adds to the run's ONE `pb_review_flags` answer: payslip flagged when an instalment was due but not taken (no pay item / other currency / pay data file had another amount / error), or when take-home after the instalment is below zero ("Loan instalment is more than this month's take-home", amount not changed). Every payslip with an instalment carries `loan_note` "Loan instalment ₫1,000,000 taken · ₫5,000,000 left"; `run.pb_loan_notes()` gives the run sentences ("3 people have a loan instalment due but this pay scheme has no pay item for loan repayments."). `get_slip_detail` carries `loan_note`. |
| Loans board | `models/pb_loans_board.py`, `static/src/{js,xml,scss}/loans_board.*` | Payroll hub lens "Loans" (`PAY_LENSES`, sequence 40) + ⌘K row (4400) + client action `pb_loans_board`. Quiet numbers line, five steps, shared filter panel, table with paid-back bar, side drawer (balance hero, plan, upcoming months, repayments, what happened) with Send for approval, Approve / Do not approve (when it is your seat), Record a repayment, Settle now, Pause, Resume, Cancel, Delete (draft) — each with a reason. "New loan" with the **live plan** (hero): instalments month by month as you type. Set up dialog per scheme. Banners: schemes with loans but no pay item; unfinished pay runs that did not take an instalment. Esc closes. |
| My Payobook | `models/pb_me_home.py`, `controllers/portal.py`, `views/portal_templates.xml`, `static/src/scss/loans_portal.scss` | `/my/loans` (read-only): left to repay, next pay, per loan the bar (native `<progress>`, no inline styles — G95), plan, history. A home card only while something is owed. Sudo after ownership guard (`my_loans` refuses anybody but the caller's own employee); no portal right on `pb.loan`. |
| Rights | `security/*` | Payroll officers / managers: all loans of their companies (read, write, create; delete drafts only); repayments read-only. Any internal user: only loans a route asked them to decide (`seat_user_ids`). Company rules on both models. |
| Words | `i18n/vi_VN.po`, `i18n/id_ID.po` | 306 of 337 entries in each (the 31 left are stock mail/technical field labels). PO parse gate passes. |

## 2. Tests

`pb_loans/tests/test_loans.py`, tag `pb_loans`, local copy `wdgap_prb_t` (template `upd_p6_t_tpl` upgraded to HEAD).

| # | Case | Result |
|---|---|---|
| T1 | plan maths: by amount, by months (rounded up, last smaller), remainder, VND and USD rounding, preview | pass |
| T2 | real route: company gets Head of pay route, waiting → approved → running; refused; inbox card `can_bulk` False (money) | pass |
| T3 | regular run: instalment into the setting, line −1,000,000 by formula, reserved while draft, balance drops only when done, note on flags; T3b no loan = nothing touched | pass |
| T4 | recompute reuses; delete / cancel / run delete release; cancel of a done payslip gives the balance back; paused + recompute feeds 0 (no stale value) | pass |
| T5 | second regular run other scheme, Clean & Run, duplicate same-scheme payslip — never twice | pass |
| T6 | top-up run and mid-month scheme take nothing | pass |
| T7 | two loans → one summed input, two lines; paused skipped; last instalment = what is left; closes itself; re-opens when a paid payslip is cancelled | pass |
| T8 | leaving month: take the rest = whole balance; leave it open = normal and stays running | pass |
| T9 | no setting → nothing fed + slip flag + run sentence + board banner; setting it clears; instalment > take-home → flag, amount unchanged; T9b other currency flag, other source amount not overridden | pass |
| T10 | application source offered, resolved with amounts, no `consumption_required`, reservation honoured (another payslip gets 0) | pass |
| T11 | pay data file path same result as no-file path; recompute once; file with another amount → file's amount kept, flagged, loan not taken | pass |
| T12 | with a `pb.updates.oneoff` in the same payslip: both applied once, both paid | pass |
| T13 | plain employee cannot read a loan or the board; portal method returns only own; home card; other company hidden; repayment line not writable | pass |
| T14 | manual repayment, over-payment refused (incl. part already in a pay run), Settle now, cancel refused while in an unfinished run, agreed terms frozen | pass |
| B1 | board head, page, steps, drawer, moves, create + send, people search, filter layout, no "Odoo" | pass |
| T15 | existing suites — see below | SUITES_RESULT |
| T16 | browser walk | WALK_RESULT |
| T17 | static gates: py_compile, XML parse, pyflakes, PO parse gate, "Odoo" grep | pass |

**pb_loans: 17 of 17 pass.**

SUITES_TABLE

## 3. Self-review against the rails

| Rail | Verdict |
|---|---|
| R1 paid once | Met. Partial unique index (loan, pay month) on live payroll lines; reservation tied to the payslip; recompute reuses it (T4); second run / Clean & Run / duplicate never take it again (T5); cancel / delete / run delete release (T4). Token logic cloned from `pb_updates` (own key). Defensive stop if a line is somehow held by another payslip at sync time (raises — never pays twice). |
| R2 never more than owed | Met. Instalment = min(plan, amount − paid − held by other payslips) read under `FOR UPDATE` when a real payslip computes; manual repayment above that refused (T14). |
| R3 balance derived | Met. Stored compute of paid lines; repayment writes need a server-only token; no screen writes it. |
| R4 never raises into the run | Met for loan problems: no item / currency / other amount / plan error → skipped + flag, run continues (T9, T9b, T11). The one deliberate raise is the R1 race stop above. |
| R5 both modes + one-offs | Met (T3–T11 regular + file, T10 application source, T12 with one-offs). Application mode tested at the source + reservation level, not a full certified application run (see D1). |
| R6 currency | Met. Loan in the person's pay currency; a scheme in another currency takes nothing and flags (T9b); board total "left to repay" is shown per currency, never added across currencies; plan maths in whole currency units, currency rounding only. |
| R7 risky deploy | New module; no demo data, no cron; a database with no loans shows only the empty board. Install lays one route per company and adds one stored column on `hr.payslip` (`pb_loan_issue`) and one on `hr.formula.config`. |
| R8 words | Plain words, Lucide icons only (cached `pbfIcon`, no flicker), vi + id files, PO gate passes, "Odoo" appears in no user-visible string. |

Design bar (owner, verbatim: "extreme WOW, best in class"): hero = the live month-by-month plan in New loan; every state designed (locked, loading skeleton, error + Try again, empty board, no match, empty My loans, login not linked, waiting / paused / closed sentences); motion with purpose (drawer slide, plan tiles stagger, reduced-motion respected); keyboard: rows open with Enter, Esc closes. Not built: multi-select / bulk moves on loans (each move needs its own reason).

## 4. Deviations

- **D1 — application data: no `consumption_required`.** The handover asked to clone the awards source with `consumption_required=True`. The engine turns any such cell into "missing — needs a paid-once reservation" unconditionally (`application_payroll_source.py:838`); nothing ever lifts it, so loans would never be taken in that mode (awards cannot be either — ledger PRB-W2). The source answers `resolved` with the per-loan amounts in its evidence and the payslip reserves them in `_application_resolve_inputs` — the paid-once pattern period inputs already use. Another payroll asking for a reserved instalment gets 0.
- **D2 — approval date.** `register_chain` carries no `date_field`: with the first pay month as the date, a holder whose start date is later than that month is not found and the request blocks (ledger PRB-W1).
- **D3 — "instalment is more than take-home"** is read as: the take-home before the instalment is smaller than the instalment, i.e. take-home after it is below zero. The flag replaces the generic "zero or below" reason in that case.
- **D4 — a pay data file (or a contract line, or a connected system) carrying a different non-zero amount for the loan pay item**: that amount is kept, the loan instalment is not taken and the payslip is flagged ("never one or the other silently", like UPDATES D11 but without stopping the run, per R4). A 0 from the file counts as blank (G33).
- **D5 — a pay run without a run kind** (a payslip outside any run) counts as regular.

## 5. How a customer sets it up (plain words, for the owner)

1. **Choose where repayments go.** Payroll › Loans › Set up: for each pay scheme pick the pay item that receives the monthly instalment (a "Loan instalment" input), and make sure the scheme has a line that takes it off pay (for example "Loan repayment = − Loan instalment"). One-time, by a payroll manager.
2. **Raise the loan.** Payroll › Loans › New loan: who, loan or salary advance, how much, first pay month, and either "an amount each month" or "a number of months" — the screen shows every instalment before you send it. Send for approval; the Head of pay approves it in Approvals.
3. **Run payroll as usual.** Every regular pay run takes one instalment until it is paid back; the person sees it on My Payobook › My loans. Pause, record a cash repayment or settle early from the loan's panel.

## 6. Full & final settlement

The final settlement screen does not read loan balances. Its "Loan / advance" figure adds up the payslip's lines whose code is exactly `LOAN`, `ADV`, `ADVANCE`, `TAMUNG`, `TAM_UNG` or **starts with `LOAN`, `ADV` or `TAM`** (`pb_hr_fullandfinal/models/full_and_final.py:345`). So: name the **deduction** line so it starts with `LOAN` (e.g. `LOANREP`), and name the **input** so it does NOT (e.g. `INLOAN`, as the demo does) — otherwise the input and the deduction are both counted and the figure doubles. With "take the rest from the final pay" the final payslip's deduction carries the whole balance, so the settlement shows it. A balance still owed after the final payslip stays "Running" and is listed on the board — it never closes silently.

## 7. Follow-ups (not in this phase)

- Net-pay floor / carry the unpaid part to the next month (today: flagged only).
- Employee self-request of a loan or advance from My Payobook.
- Paying the loan money out (bank file) — today the loan starts as "given".
- Interest and any tax treatment of a staff loan.
- Demo world: `pb_demo`'s own `hr.loan` / `INLOAN` stream is untouched and its shortcut computes skip the seams, so demo pay runs on payobook.com take no `pb.loan` instalment.
- Approvals matrix import aliases for "loan" (`pb_approval_config/models/matrix_import.py`) not added (non-goal: no `pb_approval_config` code change).

## 8. Owner questions (plain words)

1. When a person's take-home would go below zero because of an instalment, the payslip is only flagged. Should the instalment be cut to what the person can afford, with the rest moved to next month? (That is the "net pay floor" follow-up.)
2. Choosing which pay item receives loan repayments changes what a live pay scheme takes from pay. Today a payroll manager can set it straight away from the Loans screen. Should it go through the scheme's own approval instead?
3. If a pay data file has its own amount in the loan repayment column, the file's amount is used and the loan instalment is NOT taken (flagged). Should the run stop and ask instead, like one-off pay items do?

## 9. Deploy notes (RISKY tier — new module install on all five)

- Backups first, rehearse on a clone with jobs and mail switched off, then `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima` (never `abm`).
- `-i pb_loans` per database (it depends on modules already installed everywhere: pb_payhub, pb_payslip_review, pb_me_portal, pb_approval_config, pb_hr_payroll_formula, pb_payruns, pb_filter_kit). The install lays a "Loans and salary advances" route (Head of pay) per company — check each company's Head of pay holder afterwards (the seed takes the first payroll manager, or the publisher).
- New JS/SCSS: purge `/web/assets/%`, bump `web.assets.version`, restart.
- Verify: `ir_module_module.latest_version` = 19.0.1.0.0 ×5; Payroll hub shows a "Loans" lens for a payroll officer; /my/loans opens for an employee login; console clean.

## 10. New gotchas → ledger

PRB-W1 … PRB-W4 added to `WDGAP_LEDGER.md`.
