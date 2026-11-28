# WDGAP PR-E — report: three owner rulings on the pay-run extras

Branch `wdgap-pre` (from `origin/19.1` at `4c9c82a40`). Not merged, not deployed, no live
server touched. Handover: `WDGAP_PR_E_HANDOVER.md` (copied into this branch).

## 1. What was built

| Item | Module | Version | Commit |
|---|---|---|---|
| E1 Extra run + pay data file keeps only the people picked | `pb_payrun_wizard` | 19.0.1.44.0 → **19.0.1.45.0** | `7ec47c589` |
| E2 "Paid another way" | `pb_pay_delivery` | 19.0.1.5.0 → **19.0.1.6.0** | `9381005e1` |
| E3 A loan instalment never takes take-home below zero | `pb_loans` | 19.0.1.0.0 → **19.0.1.1.0** | `8268ee701` |
| Browser-walk fixes (layout, drawer reason line) | `pb_pay_delivery`, `pb_loans` | (same versions) | walk-fix commit |

### E1 — Extra run + pay data file
- **Where the file's rows became payslips**: `pb.payrun.wizard.attach_spreadsheet` drives
  `hr.payroll.import.batch` load → match → validate → process; `action_process` makes one
  payslip per row (and, in "update records" mode, writes each row back to the person). The
  filter sits in the wizard, after matching and before validate/process: for an Extra run,
  every row that is not about a picked person is taken out of the batch. So nobody else gets
  a payslip, nobody else's record is touched by the file, and nobody is created from it
  (auto-create is also forced off for an Extra run). The engine (`pb_hr_payroll_formula`) is
  not changed.
- **The picks live on the run**: `prepare_run` / `create_and_compute` write the people already
  checked by `_extra_run_people` onto `hr.payslip.run.pb_extra_employee_ids` (new relation
  table `pb_payslip_run_extra_employee_rel`). The server decides what the file keeps — a stale
  tab or a script cannot widen the run. An Extra run that names nobody (made elsewhere, no
  payslips) is refused with nothing created. The demo division path (`pb_demo`) has no file
  step and was not touched.
- **Words, before computing**: the pay-data step's check (`preflight_spreadsheet`, new optional
  `employee_ids`) reads the file and matches its rows on in-memory records only (creates
  nothing) and shows one calm line — "This file has 5 people. This extra run keeps the 1 you
  picked." — plus a plain warning naming anybody picked who is not in the file. The same block
  is repeated on the result step.
- **A picked person not in the file** is treated exactly as the regular path treats anybody the
  file leaves out: the wizard's own compute works their payslip out without the file, from the
  contract and records (never an empty payslip). The warning says so: "DEMO Em Vo is not in
  this file. Their payslip is worked out without it, from their contract and records — the same
  as a regular run does for anybody the file leaves out."
- **Regular and top-up runs**: no change; golden recorded on `origin/19.1` with the same file.

### E2 — Paid another way
- `hr.payslip`: `pb_paid_method` (Cash / Cheque / Other bank transfer / Other), `pb_paid_note`
  (≥ 6 characters), `pb_paid_by`; note and person are payroll-only fields (ledger PRC-W1).
  `action_pb_paid_other(method, note, day)` — finished, not paid, not on hold, not in a released
  file; day defaults to today, never in the future; stamps `pb_paid_on` (noon of the day when
  back-dated), clears the bank reference, writes a history line by the person and one audit
  entry. Up to 50 at once, one method and note for all. `action_pb_not_paid_after_all(reason)`
  undoes it — only for pay marked this way, never for pay a released bank file paid.
- Rights: the pay team (`PAY_GROUPS`, as hold/release), own company, never your own pay.
- Never in a bank file again: `_resolve_slips` leaves it out at **every** door (not only with
  `pb_unpaid_only`), so neither a new file nor a follow-up carries it. Cannot be held (the
  hold's own "already paid" rule). A file prepared BEFORE somebody in it was marked is refused
  at the release ("Prepare the bank file again — it will leave them out"), and the bank-file
  card says so in red — the same rail as a hold placed after the file.
- Totals: `_money_totals` gains `paid_other` per currency; per currency **paid (released files)
  + paid another way + on hold + still to pay = run total**. The bank-file sentence gains
  "− 9,000,000 paid another way (1 person)".
- **Run paid state**: the run's "Paid" (`hr.payslip.run.pb_paid`, and the Pay runs board's SQL
  `_paid_by_run`) is "every finished payslip has a paid date" — marking stamps that date, so a
  run with nobody left to pay reads Paid with no change to either.
- Delivery: unchanged code — a payslip paid another way is sent like any paid payslip (test).
- Screen: in the left-out list each row gets a tick (+ "All"); "Paid another way" opens one
  form (method chips, note, day, Ctrl+Enter / Esc); a quiet group "N people were paid another
  way" lists method, note, by, day, amount and "Not paid after all" (inline reason box); the
  hero adds "paid another way" per currency; "Everybody who can be paid has been paid" also
  when nobody is left because of this path.

### E3 — Take-home floor for loan instalments
- After a payslip is worked out with the planned instalment, if take-home
  (`hr.payslip.pb_net_amount`, the one-pay-band reader) is below zero, the instalment is cut by
  the shortfall — shortfall rounded UP to the currency's unit so the cut instalment rounds down
  (person's favour), **newest loan first** (highest id), never below zero — and the payslip is
  worked out **once more** with the smaller amounts (context `pb_loans_cap`, read by
  `_plan_for_slip`, under the same `FOR UPDATE` lock). A second pass is never floored again: if
  other deductions still leave take-home below zero, it is left and flagged as before.
- Only payslips that took an instalment AND came out below zero pay the second pass (a person
  with no loan: exactly one pass, counted in a test).
- All paths: no file (compute and "Recalculate"), pay data file (`_create_payslip` links its
  import line first so the recalculation reads the file — ledger PRE-5), application-data mode
  (the typed source answers the cut amount and the reservation follows). A file carrying its
  own loan amount still wins and the instalment is skipped (no cut).
- The untaken part stays in the balance (plan runs longer — "months left" grows); nothing else is
  created. Leaving month + "take the rest": the same cap; the rest stays owed, loan stays
  Running.
- Words: payslip `pb_loan_cut` keeps planned vs taken; review flag "Loan instalment cut from
  1,200,000 ₫ to 450,000 ₫ so take-home is not below zero · 6,750,000 ₫ left" (+ "(newest loan cut
  first)" with several loans) — it replaces the generic "zero or below" reason when the loan is
  the reason, keeps it when other deductions are. Loans drawer: the month's row shows the
  smaller amount with "Cut from … so take-home is not below zero"; the loan's history says it
  once (not on every recalculation).

## 2. Tests

Local copies of `upd_p6_t_tpl` (one at a time, dropped after), `-u` the PR-touched modules,
`-i pb_loans`. Baseline = the same run with the four touched modules taken from `origin/19.1`
(pristine copies first on the path), run before any edit.

| Run | Tests | Failed | Errors |
|---|---|---|---|
| Baseline `/pb_payrun_wizard,/pb_pay_delivery,/pb_payslip_review,/pb_loans,/pb_payroll_templates` | 270 | 1 | 0 |
| After (same tags, all three items) | 303 | 1 | 0 |
| After the walk fixes (`/pb_loans,/pb_pay_delivery`, fresh copy) | 80 | 0 | 0 |

The one failure is the same before and after: `pb_payroll_templates`
`TestRunInputReview.test_monthly_duplicate_department_label_is_unchanged_context` (not touched).
33 more tests in the runner's count; per-module stats lines: `pb_payrun_wizard` 131 → 145,
`pb_pay_delivery` 48 → 61, `pb_loans` 23 → 37 (`pb_payslip_review` 11 and `pb_payroll_templates`
105 unchanged). New test files: `pb_payrun_wizard/tests/test_wdgap_pre_extra_file.py`,
`pb_pay_delivery/tests/test_wdgap_pre_paid_other.py`, `pb_loans/tests/test_wdgap_pre_floor.py`.

**Deliberately changed existing tests** (owner ruling E3): PR-B `T9` asserted "instalment bigger
than take-home → amount NOT changed"; merge seam `2c` asserted the "more than this month's
take-home" sentence for that person. Both now assert the cut (₫15,000,000 → ₫10,000,000) and
the cut sentence (with "Pay on hold" still kept in 2c).

| # | Case | Test | Result |
|---|---|---|---|
| E1.1 | Extra + file keeps the one picked: 1 payslip, other rows out of the batch, nobody created, compute after pays nobody twice; "this run only" mode too | `test_e1_1*` | pass |
| E1.2 | Picked-but-absent named before computing (pre-flight creates nothing) and in the answer; computed without the file (lines, no file value); nobody picked in the file | `test_e1_2*` | pass |
| E1.3 | Regular and top-up with the same file = GOLDEN recorded on `origin/19.1` (rows, created, matched, errors, keys, payslips and values) | `test_e1_3` | pass |
| E1.4 | Extra run naming nobody refused, nothing created; older door stores the picks; regular stores none | `test_e1_4*` | pass |
| E1.5 | Mid-month advance: extra payslip takes it (₫3,000,000) and is flagged; regular run not flagged; extra payslip without it not flagged | `test_e1_5*` | pass |
| E2.1 | Mark: method, note ≥ 6, no future day; stamp, method, note, by; history line by the person; audit; twice refused; stored rule; held / unfinished refused | `test_e2_1*` | pass |
| E2.2 | Undo with reason; never for pay a released file paid | `test_e2_2` | pass |
| E2.3 | Several at once from the left-out list (screen calls); other run's payslip refused; cap (patched to 1); undo from the screen | `test_e2_3` | pass |
| E2.4 | Rights: plain user / officer without pay role refused; note & by unreadable for an employee; never your own; other company | `test_e2_4` | pass |
| E2.5 | Not in a new file, not in any door's slip list, not in a follow-up; cannot be held | `test_e2_5` | pass |
| E2.6 | File prepared before the mark → release refused, payload names the person; release asked before the mark → refused when carried out | `test_e2_6` | pass |
| E2.7 | Identity per currency: released + paid another way + on hold + still to pay = run total; second currency never added | `test_e2_7` | pass |
| E2.8 | Run reads Paid once nobody is left (run field, screen, board SQL); undo → not paid | `test_e2_8` | pass |
| E2.9 | Delivered like any paid payslip | `test_e2_9` | pass |
| E2.10 | Golden with none marked (plus PR-C `TestPrcGolden` green) | `test_e2_10` | pass |
| F1 | Cut to zero take-home (15M → 10M), flag words, balance 20M after done | `test_F1` | pass |
| F2 | Partial cut = the handover's example (1,200,000 → 450,000 · 6,750,000 left); drawer row; months left 5 → 6 | `test_F2` | pass |
| F3 | Two loans: newest cut first; newest cut to nothing then the next | `test_F3*` | pass |
| F4 | Leaving month, take the rest: capped, rest stays owed, Running | `test_F4` | pass |
| F5 | Recompute / compute again: same line, same amount, history said once; more pay → full instalment, record cleared | `test_F5` | pass |
| F6 | Delete the payslip releases the smaller reservation | `test_F6` | pass |
| F7 | Passes counted: no loan 1, loan that fits 1, below zero 2; other deductions → still 2, flagged with the generic words | `test_F7*` | pass |
| F8 | Pay data file path (and recalculate); file's own loan amount still wins, no cut | `test_F8*` | pass |
| F9 | Application mode: one extra pass with the cut amount, reservation follows; nothing to cut → no pass | `test_F9` | pass |
| — | PR-B R1 paid once, R2 never more than owed, R3 derived balance, R4 never raise: PR-B's own suite (T3–T14) | `test_loans` | pass |
| — | Static gates (§2b) | | pass |

### 2a. Re-run after the walk fixes
The walk fixes changed only SCSS/XML in `pb_pay_delivery` and `pb_loans`; both suites were run
again on a fresh copy: 80 tests, 0 failed, 0 errors (stats: `pb_loans` 37, `pb_pay_delivery` 61).
`pb_payrun_wizard` had no change after the full run.

### 2b. Static gates
`py_compile` 22 Python files; XML parse of both changed OWL templates; pyflakes (one old
warning in `bank_file.py`, not this change); PO gate with Odoo's `PoFileReader` on
`pb_pay_delivery/vi_VN.po` (56 new entries), `pb_payrun_wizard/vi_VN.po` (14),
`pb_loans/vi_VN.po` + `id_ID.po` (5 each): all parse, every new msgid reaches a screen (module
line + marker + `code:` occurrence; model terms for the new fields and the method choices), no
msgstr names the vendor; no added user-visible line names the vendor.

## 3. Browser walk (local copy, Claude in Chrome, console clean)

Local copy `wdgap_pre_walk` (from `upd_p6_t_tpl`, seeded by `scratchpad/pre/walk_seed.py`: a
company of its own "DEMO Walk Co" with one live end-of-month scheme, six DEMO people, an
approved June run computed through the real engine, a ₫7,200,000 loan for a person paid
₫450,000). Not the demo-world copy: the 2.1 GB demo world was not copied for the walk (disk);
the demo world has no pay data file step and no `pb.loan`, so none of the three changes can
reach its figures (see §5). Dropped after.

1. **E3** — seeding computed DEMO Giang Ho's June payslip: planned 1,200,000, taken 450,000,
   take-home 0. Payslip review: the card reads "Loan instalment cut from 1,200,000 ₫ to 450,000 ₫
   so take-home is not below zero · 6,750,000 ₫ left", 1 Need review. Loans board drawer: left to
   repay 6,750,000 ₫, months left 6 (was 5 + this month), repayments row "June 2026 · 450,000 ₫ ·
   Cut from 1,200,000 ₫ to 450,000 ₫ so take-home is not below zero", What happened has the same
   line once. Found: the drawer did not show a repayment's reason — fixed (one `<small>` line).
2. **E2** — Pay & deliver, "3 left out — view": ticks + "All" + "Paid another way". Found: the
   left-out rows wrapped onto three lines and cut the names (the grid framework's `.row` class
   on those rows) — fixed. Ticked two, Cash, note, Ctrl+Enter → "2 people were paid another way"
   group, hero "₫16,000,000 paid another way · ₫37,000,000 still to pay", left out 1. Found: the
   group's five columns hid the note in a half-width card — re-laid out on two lines (who ·
   amount · action, then note and who marked it). "Not paid after all" → reason box → Confirm:
   back to the left-out list, hero "₫9,000,000 paid another way · ₫44,000,000 still to pay".
   Prepared the file: "Bank file 37,000,000 = run 53,000,000 − 9,000,000 paid another way
   (1 person) − 7,000,000 left out for other reasons". Released. Marked the last two by cheque:
   the run's header reads **Paid**, hero "₫37,000,000 paid · ₫16,000,000 paid another way · ₫0
   still to pay", "Everybody who can be paid has been paid".
3. **E1** — Run payroll → Extra run → picked DEMO An Nguyen and DEMO Em Vo → pay data step,
   uploaded a 5-row file (four people + one stranger): before computing, "This file has 5 people.
   This extra run keeps the 1 you picked." and "DEMO Em Vo is not in this file. Their payslip is
   worked out without it…". Computed: 2 of 2 payslips (An from the file, Em from the contract),
   the same block on the result step; the run holds exactly the two picks; nobody else got a
   payslip. (An's take-home read 0 because the walk file had no Basic column and the importer's
   loose column binding put the code column into Basic — ledger PRB-W3, importer behaviour,
   same on a regular run.)
4. Console: no errors on any of the screens above (read after each reload).

Not walked: a true 390 px width (window minimum, QF2-G7); Vietnamese screens (PO gate only).

## 4. What an Extra run with a pay data file does with the mid-month advance

**It takes it off again.** On an end-of-month scheme with a mid-month advance link, the pay data
file path adds the month's posted advance (`_apply_mid_cycle_carryover`) to every payslip it
makes, whatever the kind of run, and carry-over has no "already used" marker. So a picked
person's extra payslip has the advance deducted a second time (test E1.5: ₫3,000,000 on the
extra payslip, as on the regular one). As the handover says, carry-over was not redesigned;
instead the extra payslip is flagged on the run's review — "This file also takes the mid-month
advance; check it has not been taken already" — counted under Need review on both screens, and
the result step says "1 payslip in this extra run also takes the mid-month advance off. Check it
has not been taken already." Owner question 1. Live exposure (deploy report): rize has no
mid-month schemes; no other database has a scheme that asks for a file and has a mid-month link.
Loan instalments are not affected: an Extra run never takes one (PR-D seam 2a); a loan amount
written IN the file is the file's value, as in any run.

## 5. Self-review against the handover

| Rule | Verdict |
|---|---|
| E1 keeps only the picks; the calm line; absent named before computing; follows the regular path | Met (E1.1, E1.2, walk). |
| E1 regular / top-up byte-identical | Met: golden recorded on `origin/19.1` with the same file (E1.3). The only new code on those paths is `if extra` branches. |
| E1 demo path keeps working, demo figures unchanged | `pb_demo` not touched; its division path never reaches the file step; E1 changes only Extra runs with a file. Not re-run on a demo-world copy (disk; the PR-D demo tests are not in this phase's touched set). |
| E2 all bullets (method, note, day, stamps, history, audit, undo rule, rights, bulk ≤ 50, never a file / follow-up, cannot be held, totals identity per currency, run paid, delivery, golden) | Met (E2.1–E2.10, walk). Audit uses PR-C's one-call entry point. |
| E3 cut by the shortfall, ≥ 0, rounded in the person's favour, reservation updated under the same lock, one extra pass at most, never loop | Met (F1–F7). |
| E3 plan runs longer, nothing else created; leaving month | Met (F2, F4). |
| E3 several loans: newest first, stated on the flag | Met (F3). |
| E3 flag wording; drawer history | Met (F1, F2, walk). Cut-to-nothing has no repayment row (a row needs an amount above zero): that month is said on the loan's history instead. |
| E3 both input paths + application mode; file's own amount wins | Met (F8, F9). Application mode tested at the source + reservation level, as PR-B did (no certified application run locally). |
| E3 R1–R4 still hold; idempotent; release on delete; no second pass without a loan | Met (PR-B suite + F5, F6, F7). |
| E3 performance: second pass only with an instalment AND negative take-home | Met (F7 counts). No loans exist on any live database today, so no live payslip is computed twice. |
| White-label, plain words, vi (+ id for pb_loans), PO gate, version bumps | Met. |
| Non-goals (no general net floor, no arrears, no second approver for a hold, no bank layout / formula / engine / `pb_pack_*` change) | Kept. |

Design bar ("extreme WOW, best in class"): E1's hero is the one sentence on the pay-data step
that says what the file and the run have in common *before* anything is computed; E2's is the
hero line that now adds up to the run in one glance (paid · paid another way · on hold · still
to pay) with a single, keyboard-driven form for several people; E3's is the sentence that says
exactly how much was taken, how much is left, and why. Every refusal names its reason and next
step.

## 6. Deviations

- E1: the picks are stored on the run (new relation table) rather than sent again by the
  browser, so the server decides what a file keeps.
- E1: the people-in-the-file check before computing is best effort (a file it cannot read says
  nothing there); the authoritative answer is the one after loading.
- E2: "never in a bank file" is enforced at every door that lists payslips for a file
  (`_resolve_slips`), not only on the Pay & deliver path.
- E2: marking is allowed while a prepared (not released) file still contains the person; the
  release then refuses until the file is prepared again — the same rail PR-C uses for a hold.
- E3: the cut amount is written on the repayment line's "Why" (shown in the drawer) and once on
  the loan's history; a loan cut to nothing has only the history line.
- Walk: on a seeded small copy, not on the demo-world copy (disk).

## 7. Deploy notes — RISKY tier (pay run + money-out path; new stored fields)

- `-u pb_payrun_wizard,pb_pay_delivery,pb_loans` on all five databases (backups + clone
  rehearsal first). New stored columns: `hr_payslip.pb_paid_method / pb_paid_note /
  pb_paid_by` (pb_pay_delivery), `hr_payslip.pb_loan_cut` (pb_loans); new table
  `pb_payslip_run_extra_employee_rel` (pb_payrun_wizard). No backfill: existing Extra runs have
  payslips, which `_extra_picks_of` falls back to; nobody is "paid another way" until somebody
  marks them; no loans exist live.
- JS / XML / SCSS changed in all three: purge `/web/assets/%`, bump `web.assets.version`,
  restart.
- Check after: Pay & deliver on a paid demo run — same totals, no "paid another way" line; the
  left-out list shows ticks for the pay team; Run payroll → Extra run unchanged on schemes
  without a file; Loans board opens.
- PO gate on the box for the four `.po` files.

## 8. Owner questions (plain words)

1. **An extra run with a pay data file on an end-of-month scheme also takes the mid-month
   advance off again.** Today we only flag it ("check it has not been taken already"). Should
   an extra run never take the advance (so a correction run with a file cannot double it), or is
   the flag enough? No customer has this combination today.
2. **Paid another way for a payslip of ₫0** (for example a person whose take-home was cut to
   zero) is allowed, so the run can read Paid. Fine, or should a ₫0 payslip simply count as
   paid on its own?
3. **Pay & deliver after a release, for a second pay-team member** (found while testing, not
   changed): the screen reads the release's approval, which only the people involved in it may
   read, so a pay-team member who neither sent nor approved the release can get an error there.
   Should every pay-team member be able to see who approved a release?

## 9. New gotchas → ledger

PRE-1 (pay data tests need "no approval needed" or they make 0 payslips), PRE-2 (a live
scheme's formulas cannot be edited in a test), PRE-3 (Pay & deliver reads the release's
approval as the reader), PRE-4 (count passes by patching `_evaluate_rules_with_dependencies`),
PRE-5 (a file payslip's recalculation needs its import line linked first) — added to
`WDGAP_LEDGER.md`, with the PR-E phase row.
