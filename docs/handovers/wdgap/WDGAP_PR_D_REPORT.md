# WDGAP PR-D — report: the Extra run

Branch `wdgap-prd` (from `origin/19.1` at `d3fba29ea`). Not merged, not deployed.
Spec: `WDGAP_PR_D_HANDOVER.md`; facts: `WDGAP_PR1_FACTS.md`.

## 1. What was built

| Module | Version | Change |
|---|---|---|
| `pb_payruns` | 19.0.3.5.0 → **19.0.3.6.0** | `PB_RUN_KINDS` gains `('extra', 'Extra run')` (keys `regular`/`topup` unchanged — pb_loans reads them). Board card tag "Extra run", quick-look line, run-screen header chip (`userPlus` icon, `.kind-extra`), kanban tag. "Compared with": an Extra run is compared with nothing — "An extra run has nothing to compare with." Board month line no longer counts an Extra run's / top-up's people again when the month has a regular run. vi + id. |
| `pb_payrun_wizard` | 19.0.1.43.0 → **19.0.1.44.0** | Kind of run: Regular / Top-up / Extra run, each with its one-line promise (stacked). Extra run: the people picker is always shown (status ticks hidden, not sent), chips of the people picked, a calm note ("An extra run works out everything this scheme contains…"), suggested name "Extra run — <scheme> — <date>" (follows the kind while it is the screen's own suggestion). Server: `_run_kind_from_vals` knows `extra` (only where the field offers it); `_extra_run_name` / `_extra_run_people` refuse BEFORE any run exists (no name; nobody; anybody the scheme does not pay → named); `_period_runs(kind='extra')` returns nothing; `_clean_period(kind='extra')` clears nothing; `_adopt_loose_slips` adopts nothing for top-up and extra; plan preview agrees; an Extra run's payslips are named "<person> - <run name>". vi. |
| `pb_trip_payroll_bridge` | 19.0.1.1.0 → **19.0.1.2.0** | TRIPDAYS / PERDIEM fed only to a payslip in a Regular run (or in no run). |
| `pb_workforce_payroll_bridge` | 19.0.1.2.0 → **19.0.1.3.0** | OTHRS* / BONHRS fed only to a payslip in a Regular run (or in no run). |
| `pb_demo` | 19.0.1.14.1 → **19.0.1.15.0** | Division path (`prepare_run`, `compute_batch`, `create_and_compute`) honours `employee_ids` for every kind; Extra run uses the wizard's refusals, meets / clears no division run, takes no loan instalment (INLOAN 0) and no mid-month advance (ADVPAY 0); Extra runs are never read as a division's month (`_period_config_runs`). |
| `pb_me_portal` | 19.0.3.5.3 → **19.0.3.6.0** | My Payobook › Payslips and the payslip page: a payslip from an Extra run or a top-up shows the run's name under the month (quiet violet tag; full name on hover). Regular payslips look exactly as before. No new words. |

Not touched (as bound): `pb_hr_payroll_formula`, `pb_formula_studio`, `pb_pay_delivery`, `pb_payslip_review`, `pb_updates`, `pb_comp_ben`, `pb_loans`, `pb_pack_*`.

## 2. Tests

New: `pb_payrun_wizard/tests/test_wdgap_prd_extra_run.py`, `pb_demo/tests/test_wdgap_prd_demo_extra.py`, and `tests/test_wdgap_prd_run_kinds.py` in both bridges — 31 more tests run than the baseline (the one-off class skips itself where pb_updates is absent).

| # | Case | Result |
|---|---|---|
| T1 | prepare_run extra, two people → exactly two payslips, nobody else; retried chunk never pays twice; older door works; payslip names carry the run name | pass |
| T2 | Extra beside a finished Regular run → regular untouched (lines, states, slips); beside a draft regular + top-up nothing asked | pass |
| T3 | Two Extra runs same scheme + month allowed; name required on both doors, nothing created when refused | pass |
| T4 | No people → refused (prepare, create, plan); person from another company / contract ended → refused by name, nothing created; status ticks never drop a pick | pass |
| T5 | Clean & Run never offered nor done for extra (force_clean included); `_clean_period(kind='extra')` = 0; regular / top-up cleans never reach an extra run; loose payslips never adopted | pass |
| T6 | Bridges: regular fed exactly as before (golden 5 h / 4 h / 3 h; 3 days / ₫600,000); extra not fed; **top-up no longer fed** | pass |
| T7 | One-off reserved by a regular payslip, then paid → an Extra run gets 0 both times; an unreserved one is taken once by an Extra run and then not by the regular run nor a second Extra run | pass |
| T8 | Explorer facts: regular 1,000 + extra 250 for one person → one row per run, month total 1,250 | pass |
| T9 | Demo path: one person → one payslip, no loan instalment; regular golden (₫9,900,000 with loan, ₫20,000,000) unchanged beside an Extra run; shortlist honoured; refusals; older door | pass |
| R1/R4 | regular door unchanged (adopts loose payslips, kind Regular); regular payslip recomputes identically beside an extra; kind locked after draft | pass |
| T10 | Suites vs baseline — below | baseline failures unchanged; all new pass |
| T11 | Browser walk — §4 | pass |
| T12 | Static gates: PO parse (Odoo reader) on the three touched `.po`, no "Odoo" in any added user-facing line, Python compile, XML parse | pass |

**Suites** (`pb_payrun_wizard`, `pb_payruns`, both bridges, `pb_demo`, `pb_me_portal`, one local copy of `upd_p5_t_full2`):

| | tests | failed | errors |
|---|---|---|---|
| Baseline (origin/19.1, before any edit) | 387 | 8 | 5 |
| After (first full run) | 418 | 9 | 5 |
| After the fixes | see §2a | | |

The baseline failures are all pre-existing and unchanged after: `TestRunScreen` ×5 (pb_payruns), pb_me_portal ×6 (`test_05_grid`, `test_06_font`, `test_12_vi_po…`, `test_t1_7…`, `test_01_profile…`), and the 3 old trip-bridge tests (trip approval chain on a bare copy: "No step is waiting for a decision"). The one extra failure in the first run was my own new provenance assertion (fixed — PRD-5).

### 2a. Re-run after the walk fixes
FILLED BELOW.

## 3. Self-review against the rails

| Rail | Verdict |
|---|---|
| R1 Regular / top-up as before (except the bridge change) | Held. `test_run_kind`, `test_two_schemes_one_month`, `test_run_adopts_the_period` green; regular golden checks in T6/T9/R1; a regular run's code path only gained `if kind == 'extra'` branches. Live demo check (rolled back, nothing saved, `upd_p5c_pay`): 24 people across the 6 End-Month schemes recomputed through the demo path give **the same lines with and without this change** (to the cent; 4 schemes show an older ±0.05–0.4 income-tax rounding drift against the stored October runs on BOTH — not this change, PRD-7); every run's balance check stays OK. |
| R2 Extra never deletes / cleans / adopts / modifies another run | Held (T2, T5; `_period_runs` empty, `_clean_period` returns 0, adoption off, demo guard skips). |
| R3 zero people refused; outsider refused by name | Held (T4, T9), before anything is created. |
| R4 kind changes only in draft | Kept (unchanged rule; test). |
| R5 demo runs keep balance; demo Extra run for one person = one payslip | Held: live check above (balance OK on all 6; Extra run on Retail → 1 payslip, the 902-payslip October run untouched). |
| R6 white-label, plain words, vi (+ id for pb_payruns), PO gate, version bumps | Held. |

Design bar ("extreme WOW, best in class"): the hero moment is the people chips — you see exactly who will be paid, by name, before anything is made; the run says "Extra run" everywhere it appears (board, run screen, the employee's own list). Zero dead-ends: no name / nobody / wrong person each say what to do. Not done: keyboard shortcuts in the picker beyond tab + space (the existing picker's level).

## 4. Browser walk (local copy, seeded DEMO people, Chrome)

Run payroll → Kind of run shows the three choices stacked → Extra run: name becomes "Extra run — Walk Monthly Payroll — 14 Nov 2026", picker "Who is this extra run for?" appears → Compute with nobody → "An extra run is only for the people you pick…" → pick DEMO Mai Tran (chip) → **Computed 1 of 1 payslips** → review → open run: chips "Draft · Extra run", "An extra run has nothing to compare with." → Send for approval (no sign-off) → board: card tagged **EXTRA RUN**, approved; month line "3 people · 2 pay runs" (was "4 people" before the fix); the regular November run unchanged (3 people, ₫16.64B, no tag) → switching back to Regular restores the regular name → as DEMO Mai Tran on /my/payslips: **two November cards, the second tagged with the run's name**; its payslip page shows the run name under the month. Console: no errors.
Not shown locally: the PDF (this Mac has no PDF printer — the regular payslip fails the same way) and a bank file (no bank details in the copy).

## 5. The top-up change, in plain words

- **Before:** a Top-up run for a month was given that month's approved overtime hours, overtime bonus hours, trip days and trip allowance again — so a scheme that uses them paid them twice (once in the regular run, once in the top-up).
- **After:** only the month's regular run (and a payslip made outside any run) gets them. A top-up and an extra run get none.
- **Who could notice:** a company whose top-up scheme contains overtime or trip-allowance items. Their next top-up will show zero for those items — which is the right amount, since the regular run pays them. Nobody whose schemes do not use those items sees any difference. Already-made payslips are not changed; only a recalculation would apply it.

## 6. What an employee sees

On My Payobook › Payslips, the regular payslip looks as before. The extra one is a second card for the same month with the run's name under the dates (e.g. "Extra run — bonus — 14 Nov 2026"). Its payslip page shows that name under the month, and its PDF file name carries it. **The PDF page itself still prints only the dates** — the payslip print lives in the formula engine module, which this phase must not touch (owner question 2).

## 7. Reports that assume one payslip per person per month

- Explorer: correct — one row per run, month totals add both payslips once (T8). Its line-level head-count is "distinct at its own grain" and must not be summed across runs (already documented in the model).
- Pay run board month line: fixed for Extra runs and top-ups; it still adds a mid-month advance run's people to the end-of-month run's (old, demo shows "2×" head-count).
- Payslip review flags (`pb_payslip_review`, not touched): "big change from the previous payslip" picks the latest earlier payslip in the same scheme — after an Extra run in October, November's regular payslip is compared with the October **extra** payslip, and an extra payslip is compared with last month's regular one, so both may be flagged. Follow-up for the hold-pay builder.
- Pay-data-file path (`pb_hr_payroll_formula`, not touched): the mid-month advance carry-over has no "used" marker; an Extra run on an end-of-month scheme **that loads a pay data file** would subtract the advance again (FACTS §1). The regular wizard path (no file) does not apply it.
- Year-to-date sheet: sums finished payslips; only uses a "latest payslip" to read a sign. OK.

## 8. Owner questions (plain words)

1. **Should an extra run on an end-of-month scheme be stopped from loading a pay data file?** Today that combination would take the mid-month advance off a second time. Stopping it costs nothing for the bonus use; the cost is that a correction run can't use a spreadsheet.
2. **Should the payslip PDF print the run's name** (e.g. "Extra run — bonus — 14 Nov 2026") under the dates? It needs a small change in the payslip print, which belongs to the formula engine work stream.
3. **Bonus-only scheme:** an extra run works out everything in the scheme. Do you want a ready-made "bonus and its tax" scheme to pick (a later step), or do customers build their own?

## 9. Deploy notes — RISKY tier (pay run path)

- `-u pb_payruns,pb_payrun_wizard,pb_trip_payroll_bridge,pb_workforce_payroll_bridge,pb_me_portal` on all five; `pb_demo` where installed (payobook). New selection value only — no column, no data rewrite. Asset purge + version bump (JS/SCSS/templates changed in pb_payrun_wizard, pb_payruns, pb_me_portal).
- Coordinate: pb_loans (reads `pb_run_kind == 'regular'`) — compatible; pb_pay_delivery / pb_payslip_review builders — untouched.
- After deploy: payobook QA login → Run payroll shows three kinds; one Extra run for one DEMO person in the demo's open month → 1 payslip, board tag; leave it (demo data is never deleted) or name it clearly.

## 10. New gotchas → ledger (PRD-1 … PRD-8)
Added to `WDGAP_LEDGER.md`.
