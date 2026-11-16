# WDGAP S6-C — Claims paid in pay: report

Branch `wdgap-s6c` (from `origin/19.1` at `abc2259b6`). Three NEW modules, **no file of
any existing module edited** (everything by inheritance). Not merged, not deployed, no
live server touched. Owner ruling E6; FACTS §7, §8 (lane), §10 defaults.

| Module | Version | What |
|---|---|---|
| `pb_expense_payroll` | 19.0.1.0.0 | company choice "by finance / in the next pay run"; a pay-run claim = a separate untaxed line on the next REGULAR payslip, paid once |
| `pb_trip_advance` | 19.0.1.0.0 | trip cash advance given → claimed against → settled; unspent part taken back from the next regular pay, take-home never below zero |
| `pb_expense_allowance` | 19.0.1.0.0 | yearly limit per kind of expense, per-person figure wins, "limit, used, left" refusal or "may go over" with approval |

## 1. What was built

### 1a. Claims paid in pay (`pb_expense_payroll`)
- **Setting** `res.company.pb_claims_paid_by` (`finance` default / `payrun`), who/when
  changed. Form "How claims are paid" (`pb.expense.pay.setup`), opened from Expenses ›
  Claims (toolbar button, shown only to expense managers / payroll managers / admins). It
  says how many approved claims are already set for the pay run ("they stay that way").
- **Stamp at approval**: `pb.expense.claim.pb_pay_route` written once in
  `_after_approval_transition('approved')` from the company's setting at that moment
  (server token; a write from outside is refused). Changing the setting never moves an
  approved claim. Empty stamp (all claims approved before) = finance = today.
- **What is paid**: receipts the person paid themselves (`own_account`); company-card
  receipts are never paid back. Hook `_pb_payable_amount` (trip advances lower it).
- **Paid once**: `pb.expense.payline` (claim, payslip, run, pay month, amount, kind
  payroll / file / advance, state reserved → paid / released). Partial unique index: one
  live line per claim. Rows locked `FOR UPDATE` while a payslip takes them. Create/write
  /delete only with the server token.
- **Life**: compute → reserved; payslip finished (done/paid) → paid, claim Paid with
  paid-on; finished payslip set back → reserved again, claim Approved; payslip cancelled
  or deleted, run deleted, recompute without it → released (claim Approved, the next
  regular run takes it).
- **Which payslip takes it**: a payslip being worked out, in a REGULAR run (never top-up,
  Extra, no run), scheme not mid-month, not paid from a pay data file, the scheme the
  scheme map says pays the person; same company and currency as the scheme; claim
  approved in this pay month or earlier.
- **Finance cannot pay it too**: stock "Post" of an own-account receipt of a pay-run claim
  refuses with a plain sentence; stock `_sync_paid` (accounting) never moves a pay-run
  claim.
- **Where the money is, in words**: claim form ("Paid back" + "Where the money is" +
  "Paid back in pay" tab), Claims list (filter "How it is paid", views "To pay in the pay
  run" and "Paid in pay", a line under each row's status: "In pay run X (not finished
  yet)" / "Paid in pay run X"), My Payobook claim page ("It is paid back in your next
  pay, as a separate line with no tax." → "In your November 2026 pay…" → "Paid in your
  November 2026 pay. It is a separate line on that payslip, with no tax."), new-claim
  page "What happens next" step 3, pay-run review note "Expense claims paid back: ₫X (no
  tax)" (a note, never a flag), printed payslip block "Expenses and trip advances".

### 1b. Trip cash advances (`pb_trip_advance`)
- `pb.trip.advance` per trip: given (day, reference, by) → settled (claimed, not spent,
  spent above, how it comes back) → closed. Buttons on the trip form "Cash advance
  given", "Settle the cash advance", "Paid back directly" (finance / pay team only), each
  a small form with the figures before confirming.
- **Nothing changes until somebody records an advance as given** (silent install; every
  existing trip behaves as today).
- While an advance is out, a pay-run claim tagged to the trip **waits** ("Waits until the
  cash advance of trip X is settled; then only what the advance did not cover is paid.").
- **Settle** (refused while a claim for the trip still waits approval): approved, not yet
  paid own-account receipts tagged to the trip are set against the advance, oldest first.
  Spent more → claims pay only the part above the advance. Spent less → claims fully
  covered read "Covered by your trip's cash advance" (paid), and the unspent part is taken
  back from the next regular pay, or recorded as paid back in cash.
- **Taken back once, never below zero**: `pb.trip.advance.recovery` (reserved / paid /
  released, one live line per advance and pay month). The deduction is an appended line
  like the claims, after them: the pay run takes `min(what is left, take-home)`, the rest
  waits for the next regular run (review note "₫X of an unspent trip advance waits for
  the next pay run so take-home is not below zero"). No second pass of the formulas, no
  loop. Only a payslip whose period ends on/after the settlement day takes it — the
  person sees the figure on My Payobook (home card + Expenses page) from the settlement
  day, before any run.
- **Trips board "advance outstanding"**: advances given → whole advance; settled → what
  is still to take back; closed → 0; trips nobody recorded → counted exactly as before
  (so the figure does not move on install).

### 1c. Yearly claim limits (`pb_expense_allowance`)
- `pb.expense.allowance` (company, year, kind of expense, optional person, amount); the
  person's row wins over the company row; one company row per kind and year (checked).
- Checked at each receipt and again for the whole claim at send (per kind and year):
  over what is left → refused with the numbers ("Your limit for 2026 is 1,000,000 ₫,
  700,000 ₫ is already approved, so 300,000 ₫ is left and this comes to 400,000 ₫."),
  waiting claims counted too. Company switch "Claims may go over the yearly limit" (on
  the "How claims are paid" form): then the claim is sent, the route fact
  `over_yearly_limit` lets a route ask for a step, and approvers see the chip "Over the
  yearly limit: … limit, used, left, this claim".
- My Payobook › Expenses: "Your yearly limits" (limit, used, waiting, left, a bar).
- No limit set = no check (golden).

## 2. The seam that adds payslip lines, and why it is safe

**Where**: `hr.payslip._create_payslip_lines_from_formulas` (the no-file line producer,
`pb_hr_payroll_formula/models/hr_payslip_formula.py:922`) is overridden in
`pb_expense_payroll/models/hr_payslip.py`: `super()` first, then `_pb_extras_apply()`
appends the lines. The same seam W2-D2 (`origin/wdgap-w2d2`, `pb_retro`) uses; **no line
of `pb_hr_payroll_formula` was edited, no hook was needed**.

**Why safe**:
- Nothing is fed into the formulas: the claim is appended after them, so no tax or
  insurance formula sees it — untaxed by construction on every scheme, no set-up (C3:
  tax line and every computed value equal to the engine alone).
- The producer deletes every line before rebuilding, so a recompute replaces, never
  doubles (C4, A4).
- Golden: a payslip with nothing to pay, take back or give back costs two indexed counts
  and writes nothing (no savepoint, not even its note field) — C1, C2 compare lines,
  computed values and inputs with the step switched off, on a classified and an older
  scheme.
- Typed so every band reader reads it with **no reader changed**: claim = earning (gross
  up, take-home up), unspent advance = deduction (deductions up, take-home down), never a
  "detail" line; take-home moves on the payslip's ONE take-home line (W2D2-1). On a
  payslip whose lines carry pay roles the line carries `earning` / `deduction`; on an
  older scheme with no roles it carries none (one role there would make `pb_net_line` read
  "no take-home") and the category its gross/deductions are read from. A deduction takes
  the sign the payslip's own deductions use. ORM `pb_pay_totals` and the run's SQL twin
  `_pb_slip_totals` agree (C3, C9, A3).
- Everything in one savepoint; a failure gives back what the payslip held and notes it
  (C17) — never a claim held that is not on the payslip.
- File path NOT changed: the pay data file producer is not overridden (handover).
- Order with loans: the lines are added inside the producer, so the loans' take-home
  floor (PR-E) sees them; claims help take-home, the unspent advance only takes what fits
  after the loan (A12), and when the loan itself would take take-home below zero the
  loan's own floor cuts it and nothing is taken back (A13).

## 3. Files touched outside the new modules

**None.** `pb_me_expense`, `pb_expenses_hub`, `pb_business_trip`, `pb_me_portal`,
`pb_hr_payroll_formula`, `pb_loans`, `pb_payruns` are extended by inheritance only:
model `_inherit`, QWeb `inherit_id` + xpath (claim page panels, new-claim step 3,
expenses list sections), OWL `t-inherit` + `patch()` of `PbClaimsLens` (toolbar button,
row line), controller subclass of `PbMeExpensePortal` (adds to the list page's values),
`pb.trips` facade override (outstanding figure). Version raises at deploy: none of the
existing modules (none changed); install the three new ones.

## 4. Tests

Local copy `wdgap_s6c_t` (template `upd_p6_t_tpl`, the 33 behind-HEAD modules `-u`,
`pb_loans` installed as on live). Baseline recorded BEFORE any install.

### 4a. New tests (all pass)
| # | Case | Result |
|---|---|---|
| C1 | default "by finance": claim stamped finance; payslip byte-identical to the engine alone; finance words unchanged | pass |
| C2 | golden: pay-run setting on, person without a claim, classified + older scheme: identical, nothing written | pass |
| C3 | separate untaxed line: own receipts only (company card left out), earning role, tax & computed values unchanged, take-home +claim, gross +claim, deductions same, ORM = SQL, reserved, words | pass |
| C4 | compute again + Recalculate: one line, one reservation | pass |
| C5 | second regular run of the month, top-up, Extra run, mid-month scheme never take it; delete gives it back; free claim still not taken by top-up/Extra; next regular takes it | pass |
| C6 | payslip outside a run takes nothing | pass |
| C7 | matrix: finish → paid + claim Paid + "Paid in pay run X" / "Paid in your March 2026 pay"; set back → reserved, claim Approved; finish again; cancel a paid payslip → given back; next run takes it; delete that run → given back | pass |
| C8 | recompute without it (held) → line gone, reservation given back, note | pass |
| C9 | older scheme without pay roles: no role on the line, take-home line still found, gross − deductions = take-home, SQL = ORM | pass |
| C10 | pay data file scheme: not taken, note "Include them in the file"; pay team marks "Paid in the pay data file" (kind file, paid); a plain user refused; twice refused | pass |
| C11 | claim in another currency than the scheme: not taken, note | pass |
| C12 | approved after the pay month: waits for that month's run | pass |
| C13 | guards: route not writable, payline create/write/delete refused, finance "Post" refused, stock paid never moves it | pass |
| C14 | employee login: own claim page data with "Paid in your March 2026 pay"; another person's claim refused; no right on paylines | pass |
| C15 | setup: plain user refused; manager saves; who/when; approved claim keeps its route after a change; new claim follows the new choice | pass |
| C16 | staff list row words, views, filter; printed payslip block; review note is a note, not a flag | pass |
| C17 | a failure inside the step never breaks the run, gives back, notes it | pass |
| C18 | HTTP as a real employee login (portal user): claim page 200 with the sentence, no vendor word; another person's claim 404; new-claim page step 3 | pass |
| C19 | silent install: every company "by finance", no job, no mail template, no salary rule made, no advance, no limit, list views unchanged at the front | pass (after-run, before the walk data was seeded; on the walk copy it rightly sees the walk's own company) |
| A1 | trip with an advance nobody recorded: claims paid as today; board figure unchanged | pass |
| A2 | advance given: pay-run claim tagged to the trip waits (note, words); recording twice refused | pass |
| A3 | spent less: claims covered ("Covered by your trip's cash advance"), 3,000,000 not spent seen on My Payobook BEFORE the run, taken back as a deduction line in the next regular run, covered claim not paid again, deductions/take-home ORM = SQL, closes when finished, review note | pass |
| A4 | never below zero: take-home 1,800,000, 5,000,000 to take back → 1,800,000 taken, take-home 0, 3,200,000 waits (note); recompute never doubles; April 1,800,000, May the last 1,400,000; closes | pass |
| A5 | spent more than the advance: claim pays only the part above (500,000) | pass |
| A6 | cancel a finished payslip re-opens the advance; delete gives it back | pass |
| A7 | top-up / Extra never take it; settled after the pay month → waits | pass |
| A8 | paid back in cash: never from pay; over-amount refused; plain user refused; nobody writes an advance; employee login has no right | pass |
| A9 | settlement refused while a claim for the trip waits approval | pass |
| A10 | board "advance outstanding": unchanged on recording, drops to what is left after settlement | pass |
| A11 | only the person sees their own advances | pass |
| A12 | seam with loans: loan 1,500,000 in full, claim 300,000 paid, 600,000 of the advance (what fits) taken, take-home 0, 400,000 waits | pass |
| A13 | seam with loans: loan bigger than pay → the loan's own floor cuts it to 2,100,000, claim still paid, nothing taken back, take-home 0 | pass |
| L1 | no limit = no check | pass |
| L2 | company limit refusal with limit / used / left / asked | pass |
| L3 | the person's figure wins | pass |
| L4 | send weighs the whole claim (two receipts each under, together over) → refused, still a draft | pass |
| L5 | "may go over": sent, route fact `over_yearly_limit`, approver chip with the numbers | pass |
| L6 | waiting claims count; My Payobook rows (used, waiting, left, bar) | pass |
| L7 | setup switch saved; door to the limits; employee login has no right on limits | pass |

### 4b. Existing suites vs baseline
Same database, same tags, every module `-u` so its tests run (ledger S6C-4).

| Run | Tests (runner) | Failed | Errors |
|---|---|---|---|
| Baseline 1 `/pb_me_expense,/pb_expenses_hub` (before any install) | 52 | 0 | 0 |
| Baseline 2 `/pb_business_trip,/pb_trip_expense_bridge,/pb_trip_payroll_bridge,/pb_me_trip,/pb_loans,/pb_payslip_review,/pb_payruns,/pb_me_portal` | 348 | 8 | 18 |
| Baseline 3 `/pb_hr_payroll_formula` | 721 | 4 | 0 |
| **After** — all of the above + `/pb_expense_payroll,/pb_trip_advance,/pb_expense_allowance` (new modules installed) | 1,160 | 12 | 18 |

**Failure set after = baseline union exactly (30 = 30; none new, none gone).** The 30
known: `TestBusinessTrip` 01–07, 12, `TestTripExpenseBridge` 01–05, `TestTripPayrollBridge`
01–03 (trip approval chain on a bare copy, ledger PRD-4); `TestRunScreen` ×5 (close week,
PRB-W6); `TestMeHomeCards` 05/06, `TestMeHomeSource` 12, `TestPbMePortal` 01,
`TestPortalOnlyDoors` t1_7 (pb_me_portal on this copy); formula: `TestRd49SyncCost`
02ab/02i, `TestRecordsR1OneTime` 07b, `TestSchemeCtxCurrency` 04 (known since PR-A).
New suites: pb_expense_payroll 23, pb_trip_advance 15, pb_expense_allowance 9 (runner
stats), all pass. Re-run of the three after the walk fixes: all pass except C19, which on
the walk copy sees the walk's own seeded company (expected).

### 4c. Static gates
`pyflakes` clean (only the usual `__init__` imports); every XML parses; PO gate with the
framework reader: pb_expense_payroll 142 / 142, pb_trip_advance 195 / 195,
pb_expense_allowance 57 / 57 entries in each of vi and id, 0 empty, 0 placeholder
mismatch, 0 msgstr naming the vendor.

## 5. Browser walk (Claude in Chrome, local copy, server on its own port, no jobs)
Walk world seeded on `wdgap_s6c_t` (`scratchpad/s6c/walk_seed.py`): company "DEMO Walk
Claims Co" set to "in the next pay run", employee login (portal) DEMO Linh Tran, pay-team
login DEMO Hoa Pay, one scheme, a 2-receipt meals claim (630,000 ₫), a Da Nang trip with a
3,000,000 ₫ advance given then settled against a 1,200,000 ₫ taxi claim, a 2,000,000 ₫
yearly meals limit, the November regular run computed: BASIC 12,000,000 · TAX 1,200,000 ·
claim +630,000 · unspent advance −1,800,000 · take-home 9,630,000 (exact).
Walked on `http://s6c.localhost:8955` — another builder was signed in on `127.0.0.1` in
the same browser (ledger S6C-5).
1. **My Payobook › Expenses** (employee login, 500 px wide): "Trip cash advances" — Given
   3,000,000 ₫ · Claimed against it 1,200,000 ₫ · To pay back 1,800,000 ₫ · "1,800,000 ₫
   comes off your November 2026 pay."; "Your yearly limits" — DEMO Meals, bar, Limit
   2,000,000 ₫ · Used 630,000 ₫ · Left 1,370,000 ₫. No sideways scroll.
2. **Claim pages**: meals claim "Approved on 16 Nov 2026. In your November 2026 pay. It
   shows as a separate line on that payslip, with no tax. 630,000 ₫"; taxi claim "Paid …
   Covered by your trip's cash advance. Nothing more comes in your pay for it."; another
   person's claim → 404; no vendor word in the HTML.
3. **Vietnamese** checked from the page source (`fetch('/vi/my/…')`, W2A-8): "Trong lương
   tháng 11 2026 của bạn. Hiển thị là một dòng riêng trên phiếu lương đó, không tính thuế.",
   "Tạm ứng công tác", "1.800.000 ₫ được trừ vào lương tháng 11 2026 của bạn.", "Hạn mức năm
   của bạn".
4. **Home** card "Trip cash advance — BT/2026/0186 Da Nang — 1,800,000 ₫ to pay back —
   1,800,000 ₫ comes off your November 2026 pay — See my expenses".
5. **Expenses › Trips** (pay-team login): "Advance outstanding 1,800,000 ₫" (was 3,000,000
   ₫ requested). **Expenses › Claims**: "How claims are paid" button; views "To pay in the
   pay run 1", "Paid in pay 1"; the row reads "Approved — In pay run DEMO November 2026 (not
   finished yet)". The form "How claims are paid" with the explanation and the yearly-limit
   switch. **Trip form**: status "Settled — being taken back", "Still to take back
   1,800,000 ₫", history lines for given and settled.
6. Console: no errors on any page (employee and staff).
Fixed on the way (commit after the walk): "1 approved claims" → its own singular sentence;
"Not changed yet: finance pays…" shown only when the company really is on "by finance";
the chatter date printed raw ("2026-11-01") → the reader's date format; the advances
heading icon had no gap. Not walked: a true 390 px width (window minimum here 500 px), the
PDF file itself (the printed block is covered by C16).

## 6. Deviations
- **D1 — "released on reset/reopen"** is implemented as the loans/back-pay rule: a
  finished payslip set back to draft keeps the claim HELD (reserved, claim back to
  Approved, not paid), because that payslip's lines still carry the claim; releasing it
  then would let a second run pay it while the first still shows it (double pay on
  re-finish). Cancel / delete / recompute without it release it. Tested in C7/C8.
- **D2 — "Paid in <run>"** for the employee reads the pay MONTH ("Paid in your November
  2026 pay"); the staff screens name the run.
- **D3 — only own-account receipts are paid back**; company-card receipts never are.
- **D4 — no approval step for settling an advance**: finance / pay team press Settle and
  see the figures first; the settlement is logged on the trip and the advance. Owner
  question 3.
- **D5 — claims already paid before the settlement are not set against the advance**
  (their money reached the person already); only approved, not-yet-paid claims are.
- **D6 — draft (never-sent) receipts drawn by the trip bridge** (`pb_trip_expense_bridge`
  makes draft expenses with no claim) are not counted as spent; only claimed receipts.

## 7. Schemes paid from a pay data file — what a real fix needs
Today (as the handover asks): those payslips never take a claim or an advance; the run's
review notes per person "Approved expense claims of ₫X are not in this payslip: this pay
scheme is paid from a pay data file. Include them in the file." (and the same for an
unspent advance); the claim form has "Paid in the pay data file" for the pay team. A real
fix needs: the pay data file producer (`hr.payroll.import.batch.
_compute_and_create_payslip_lines`) to append the same lines (the seam W2-D2 also
overrides), a rule for a file that ALREADY carries the claim in a column (take the file's
or ours — never both; a clash stop like `pb.updates.oneoff`'s `OneoffClash`), and the
Run payroll wizard's file template to show the amounts. Owner question 1.

## 8. Rehearsal on a rize copy should prove
1. Install the three modules: nothing changes (every company "by finance", claims list
   and trips board figures identical, recompute of a recent regular run identical — count
   refused recomputes separately, ledger W2M-4).
2. On the copy only, set a Rize company to "in the next pay run", approve a test claim,
   compute that company's regular run: one "Expense claim paid back" line, take-home up by
   the claim, tax lines unchanged; on a rize scheme paid from a pay data file (15 of them)
   the claim is NOT added and the review note appears.
3. Delete that run on the copy: the claim is back to "To pay in the next regular pay run".
4. Record an advance given / settle on a test trip and see the deduction stop at zero
   take-home.

## 9. Deploy notes (RISKY tier — pay calculation, new module install)
- Backups first, rehearse (above), then `-i pb_expense_payroll,pb_trip_advance,
  pb_expense_allowance` on `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`.
  All dependencies are already installed everywhere.
- New stored columns on big tables: `hr_payslip_line.pb_extra_kind` (nullable, partial
  index `btree_not_null`), `hr_payslip.pb_extras_note`; `res_company.pb_claims_paid_by`
  (filled "finance"), `pb_claims_paid_by_changed_by/on`, `pb_expense_allow_over`. New
  tables: `pb_expense_payline`, `pb_trip_advance`, `pb_trip_advance_offset`,
  `pb_trip_advance_recovery`, `pb_expense_allowance`. No data migration, no job, no mail.
- JS/XML/SCSS (backend: claims list patch; frontend: three small stylesheets): purge
  `/web/assets/%`, bump `web.assets.version`, restart.
- Verify: Expenses › Claims opens with the "How claims are paid" button for a manager;
  a trip form shows "Cash advance given" only on an authorized trip with an advance;
  My Payobook › Expenses unchanged for a person with no limit and no advance.
- Merge with S5-B (time into pay) later: seam test = a payslip carrying a claim and their
  time inputs (theirs are fed to formulas, mine appended after; they do not meet).

## 10. Contracts other phases may rely on
- `pb.expense.claim._pb_payable_amount()`, `_pb_pay_hold_reason()` (hooks),
  `_pb_pay_status()` → `{route, step, amount, month, run, me, staff}` or None.
- `hr.payslip._pb_extras_steps(ctx)`, `_pb_extras_wanted()`, `_pb_extras_add_lines(kind,
  items, currency, code=None)` (append typed fixed lines), `_pb_extras_follow`,
  `_pb_extras_gone`; `hr.payslip.run._pb_extras_more_notes(slip, note)`.
- Line codes `PBEXPBACK` (claim, earning), `ADVPBTRIP` (unspent advance, deduction — starts
  with ADV so full-and-final reads it as an advance); `hr.payslip.line.pb_extra_kind`.

## 11. Owner questions (plain words)
1. **Pay schemes paid from a pay data file** (Rize has 15): approved claims are listed on
   the pay run for the pay team to type into the file, and the pay team then marks each
   claim "paid in the file". Is that enough for now, or should claims be added to those
   payslips automatically (more work, and we must decide what wins if the file already
   has the amount)?
2. **A trip cash advance is only tracked once finance presses "Cash advance given"** on
   the trip. Trips where nobody does that work exactly as today. Fine, or should every
   authorized trip with an advance count as given automatically?
3. **Settling an advance needs no second person**: finance presses Settle and sees the
   figures first; the person sees what comes off their pay on My Payobook before any pay
   run. Should settling go through an approval (for example the Head of pay) instead?
4. **Company-card receipts are never paid back** to the person (it was not their money).
   Correct?

## 12. Left for later
- Pay data file schemes adding claims automatically (§7).
- A run-level chip "includes claims for N people" on the pay run screens (needs an edit
  in `pb_payruns` / `pb_payrun_wizard`).
- My Payobook payslip page: claims show as their own lines in the line list (no separate
  block — that page is `pb_me_portal`'s, C-3).
- The trips board figure still adds advances of different currencies for trips nobody
  recorded (that is the existing code; tracked advances are counted in the company's
  currency only).
- Employee-side trip page (`pb_me_trip`) showing the advance (the figure is on the home
  card and Expenses page instead).

## 13. Gotchas → ledger
- S6C-1: a QWeb page render outside an HTTP request (`ir.ui.view._render_template` of a
  `portal.portal_layout` page in a TransactionCase) fails in the frontend layout
  (`'NoneType' object has no attribute 'replace'`); test portal pages through HttpCase as
  the employee login.
- S6C-2: `hr.payslip.run` has no `company_id` on this build; a fixture that sets it fails
  "Invalid field" (guard with `'company_id' in Run._fields`).
- S6C-3: an appended payslip line on a payslip whose lines carry NO pay role must carry
  none either: one role makes `pb_net_line()` read "classified, no net line" and
  take-home becomes 0 everywhere (bank file, review, My Payobook).
- S6C-5: cookies are per HOST, not per port: with another builder signed in on
  `127.0.0.1:<their port>` in the same browser, signing in on `127.0.0.1:<my port>` logs
  them out. Walk on your own name, e.g. `http://s6c.localhost:<port>` (resolves to
  127.0.0.1; start the server with `--db-filter='^<db>$'`).
- S6C-4: tests run only for modules being installed or updated: a baseline with
  `--test-tags` must also `-u` each module whose suite it means to record.
