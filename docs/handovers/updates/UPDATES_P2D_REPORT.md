# UPDATES — Phase 2d report (one-off pay items for a pay month)

Implemented, tested, deployed and checked live on 2026-11-11 by the Opus implementation
agent, against `UPDATES_P2D_HANDOVER.md` and `UPDATES_LEDGER.md`.

**Shipped:** `pb_updates` 19.0.1.3.0 only (no other module changed: `pb_records`,
`pb_hr_payroll_formula`, `pb_payrun_wizard`, `pb_payroll_templates` untouched — every pay-run
seam is an override inside `pb_updates`, which now depends on `pb_payrun_wizard` and
`pb_payroll_templates`, both installed on all five databases).

Commits: `6f374c15c` (the feature) · the docs commit carrying this report, the handover and the
ledger.

R0 below was written BEFORE the deploy, as the handover asks; `<TS>` = `20261111T093000Z`.

## R0. Rollback note (written before deploying)

- **Files:** the previous `pb_updates` tree is kept on the server in
  `/odoo/backups/updates-p2d-<TS>/pb_updates.prev` (hash e70c180c7d627d18 = git `5a22b1c11`).
  Restore = scoped `rsync -a --delete` of that tree into `/odoo/odoo-server/addons/pb_updates/`,
  `-u pb_updates` on the five databases, asset signal + purge + version bump, restart.
- **Data:** five dumps `/odoo/backups/updates-p2d-<TS>/<db>.pre-updates-p2d.dump`, taken before
  the service stops.
- **What a files-only rollback leaves behind:** one new table `pb_updates_oneoff`, three new
  columns (`pb_updates_batch.kind/period_month`, `pb_updates_layout.kind`,
  `pb_records_apply.updates_oneoff`). An old registry ignores them. While no one-off row is
  `approved`/`reserved`, nothing else reads them. If one-off rows exist, either cancel them
  first (Updates home → Cancel) or restore the dumps — after a files-only rollback a pay run
  would simply stop reading them (no double pay, but nothing paid either).
- A one-off update still **waiting for approval** must be cancelled before a files-only
  rollback: the old code would try to write its plan as a records change on approval and
  refuse every value (nothing paid, nothing written — but a confusing "refused" list).
- **No new scheduled job.** Nothing to switch off.

---

## R1. Tests E1-E19 (and X1, the "Could not be made" display)

New file `pb_updates/tests/test_updates_p2d.py` — 26 tests in two classes (`TestUpdatesP2d`,
`TestUpdatesP2dRoute` with a real approval route), a company of its own in Ho Chi Minh City,
today frozen at 11 Nov 2026. Every payslip is computed through the real seams
(`compute_sheet`, `pb.payrun.wizard.attach_spreadsheet` with a pay data file and with a monthly
template file, `action_recompute_formula_lines`, the run's "Recalculate everyone").

| # | Case | Result |
|---|---|---|
| E1 | **Out of suite, before/after on a fresh read-only copy of live payobook** (`e1_capture.py`): Retail end-month scheme, 12 people, December 2026 — no-file compute + recompute, pay-file create + recompute (one-time file with three pay-item columns), monthly-template create + recompute (902-person roster). Hash of every payslip's inputs JSON, sources JSON, computed values and lines, keyed by person. Pre-phase code (HEAD tree, pb_updates 1.2.0) vs new code (pb_updates 1.3.0 installed, table present): **6 of 6 identical** (`4ecfc381…`, `4ecfc381…`, `d88c66c1…`, `d88c66c1…`, `f9755a52…`, `f9755a52…`). Again with 20 live one-offs seeded that must NOT reach these payslips (other people in December, these people in January): **6 of 6 identical**. In suite, `test_E1b_no_row_no_difference`: a December row never touches a November payslip (default value, no Updates source), and the pay-run line stays empty. Application-data mode: see E15 | PASS |
| E2 | `test_E2_no_file_run` — approved bonus 500 → no-file payslip input 500, source `employee_field`/`updates_oneoff`, one line of 500; row `reserved` by that payslip, `paid` when the payslip is done | PASS |
| E3 | `test_E3_pay_file_without_the_column` — pay-file run whose file carries only the base pay: base pay 2000 from the file, bonus 500 from Updates, row reserved by the file's payslip | PASS |
| E4 | `test_E4_template_month_file` — server-built month file: the template's filler 0 is a blank, so the bonus is 500 from Updates; row reserved; the colleague without a one-off has 0 | PASS |
| E5 | `test_E5_recompute_everywhere` — native Compute Sheet again, Recalculate (slip), "Recalculate everyone" (run), on a no-file run and on a pay-file run: still 500, still one line, same reservation | PASS |
| E6 | `test_E6_two_runs_same_month` — regular run pays it; a top-up run in the same month reads 0 (also after its own recalculate); the reservation stays with the first payslip | PASS |
| E7 | `test_E7_cancel_delete_clear` — payslip cancelled → back to waiting, the next payslip pays it; payslip deleted → waiting; run cleared (`_clean_period`) → waiting; run deleted → waiting; the row's history says why | PASS |
| E8 | `test_E8_clash_choose_updates` — Updates 500, file 700: no payslip from the file for that person (only for her), the question stored (run, file amount 700, no choice); the no-file compute the run does next refuses with "…500… from Updates, 700… in the pay data file. Choose…"; her payslip cannot be marked done; `get_summary` lists one question with both amounts; Updates home lists it; "Use the Updates amount" → the stray payslip becomes the file's payslip, input 500, source Updates with the file's 700 recorded as the ignored side; choice, chooser, time and file amount stored; question gone; done → paid. `test_E8b_clash_choose_file` — "Use the file's amount" → 700 from the file with Updates' 500 as the ignored side; row `paid` against that payslip ("Not paid: the pay data file's amount … was used instead"); a later top-up run in the month reads 0 | PASS |
| E9 | `test_E9_equal_amounts` — file 500, Updates 500: one payslip, no stop, value 500 from the file, row reserved by it (paid once), no question | PASS |
| E10 | `test_E10_pending_and_cancelled_never_read` (+ `test_E16_approve` with a real route: pending reads 0) | PASS |
| E11 | `test_E11_deduction_and_negative` — "-200" refused: "A one-off amount cannot be negative. P2D Fine already takes it from pay: type the amount without a minus sign."; 200 lands as a deduction line (`pay_role` deduction); a minus sent past the screen straight to `apply` is refused by the server too | PASS |
| E12 | `test_E12_not_in_scheme_and_no_scheme` — Bob's scheme has no fine: greyed `off_scheme` naming his scheme; Ned in no scheme: "P2D Ned is not in any pay scheme for November 2026, so a one-off pay item cannot be paid to them."; `apply` drops an off-scheme value and counts it | PASS |
| E13 | `test_E13_replace_clear_reserved` — 500 → 800: review shows "replaces 500", old row `replaced`, new row points at it; CLEAR → the waiting row `cancelled`, nothing live; a row a pay run took: "P2D Bonus for November 2026 is already in pay run P2D Nov run. Change it there." | PASS |
| E14 | `test_E14_months_and_mid_month` — November payslip reads November only (December row untouched); the mid-month payslip (1–15 Nov) reads its own scheme's item (advance bonus 40) and NOT the end-of-month bonus although the mid-month scheme has the same code | PASS |
| E15 | `test_E15_application_data_reads_nothing` — seam 1 in the application-data context returns the default, no Updates source, row untouched; the pay-run line for an application-data scheme says the one-offs are not included in that kind of run. Decision: **not covered, notice shipped** (R6) | PASS |
| E16 | `TestUpdatesP2dRoute`: `test_E16_approve` (pending → approver approves → rows approved, payslip recalculated reads it; the approval drawer shows "P2D Bonus · November 2026"), `test_E16_send_back_and_turn_down` (rows `returned` / `rejected`, nothing live), `test_E16_cancel_waiting` (Cancel on the Updates home withdraws the request: rows `cancelled`, request `cancelled`) | PASS |
| E17 | `test_E17_existing_stores_untouched` — no row created in `hr.payroll.period.input` or `pb.payroll.month.inputs`. Their own suites (and the Awards board's code is left out of one-off items): see E18 | PASS |
| E18 | Local isolated tree (G13), the five suites upgraded together, **pre-phase code vs new code side by side**: `pb_hr_payroll_formula` 799, `pb_payroll_templates` 105, `pb_payrun_wizard` 106, `pb_records` 134, `pb_updates` 59 → 89 tests. Pre-phase: 3 failed of 1,045; new: **the same 3 failed of 1,071** (`test_records_r1_one_time.test_07b…`, `test_schemectx_currency.test_04…`, `test_run_input_review.test_monthly_duplicate_department_label…` — pre-existing on the local build, untouched by this phase). Final `pb_updates`: **79/79**. Live `p0clone`: R4. Speed: R2 | PASS |
| E19 | `.po`: built from `odoo-bin i18n export -l pot` (G2/G6), 197 new entries, `pb_updates` 603/603 translated, `PoFileReader` reads it; split template sentences rewritten as whole sentences first (11 fragments that would have read badly in Vietnamese); no "Odoo" in any msgid/msgstr or new visible string (P1's `test_no_odoo_in_visible_strings` green; the one-off sheet's file name asserted in S3) | PASS |
| X1 | `test_X1_could_not_be_made` — a lasting change approved after its value was changed by somebody else: request `approved` with a block reason; Updates Past updates reads state `blocked`, "Could not be made", the reason; Records history row "Could not be made" with "Approved, but it could not be made: …". Display only (engine unchanged) | PASS |
| S1-S4 | Screens: catalogue (base pay and hours are never one-off items), month window (2 back – 12 ahead), the sheet round trip (grey cells, Read me, pre-filled amounts, from-sheet matching, sent straight back = 0 changes), one-off column matchings kept apart from lasting ones | PASS |
| H1 | Home: "Waiting for a pay run" (month, people, items, totals), Past updates states ("Waiting for a pay run" → "In pay run P2D Nov"), Cancel takes back only what no run took ("1 cancelled, 2 stay in the pay run"), Records history line | PASS |

## R2. Timings

Fresh copy of live payobook (4,575 people), uid 2, same machine (other test runs were busy on it
at the same time, so these are upper bounds), cold / warm:

| Step | P2c (pre-phase) | This phase | Target |
|---|---|---|---|
| Lasting sheet, 73 columns | 19.3 s / 12.4 s | 19.2–19.6 s / 13.6–14.7 s | ≤ 20 s |
| Read the columns | 5.3 s / 5.0 s | 5.4–5.5 s | — |
| **Review 4,575 × 73** | 14.0 s / 13.8 s | **15.8–20.9 s / 15.3–16.3 s** | ≤ 25 s ✔ |
| Answer | 0 changes, 60,074 same, 1,499 unmatched | identical | — |
| One-off sheet, whole roster, November 2026 (6 one-off items) | — | 3.5–3.8 s | — |
| One-off read columns / review, whole roster | — | 2.9–3.1 s / 2.8 s | — |

A pay run with no one-off for a person pays one indexed query per payslip (the store is
searched by person + month before anything else); E1 shows the results are unchanged.

## R3. Browser walk (local copy of live payobook) and screenshots

My own local server on a fresh copy of live payobook (port 8497, cron and mail off), active
company Payobook Vietnam JSC (G22), console read at every step: **no errors**. Screenshots in
`outputs/updates-p2d/` (not committed). Local-only changes made for the walk and said here:
two people given a code (WALK1/WALK2), the Retail end-month scheme's division tag removed and a
spreadsheet source put on "KPI Bonus (in)" so the Run Payroll screen asks for a pay data file,
and one P2b update re-marked as "approved but could not be made" to show that state.

1. `01-start-oneoff-month` — Start: two large choices, "One-off pay items for a pay month"
   picked, pay month "November 2026 (this month)", the one-off sheet download.
2. `02/03-match` — a person's own CSV ("KPI bonus", "Commission", "Loan repayment"): "Goes to"
   offers only one-off pay items grouped by scheme with "adds to pay" / "takes from pay";
   scheme head-counts; the one-off note.
3. `04–07-review` — "This sheet sends … paid in November 2026"; two namesake rows bound / skipped;
   the month strip with "Adds to pay / Takes from pay" totals; per-column totals in the headers;
   negative amount refused with the sentence and fixed on screen (totals update); "abc" refused;
   the Manufacturing person's KPI greyed (not in their scheme); DEMO Nguyen Van An refused
   (no pay scheme).
4. `08-apply-month-card`, `09-done-approved` — "Paid in the November 2026 pay run", totals,
   "Send 4 one-off amounts"; done: "Approved … These will be included in the November 2026 pay
   run." (no Undo on a one-off).
5. `10-home-waiting-list` — "Waiting for a pay run": November 2026, 2 people · 4 one-off amounts,
   totals, the list (person, item, amount, where it is) and Cancel per update; Past updates row
   with the coins icon.
6. `11-payrun-step1-line` — Run Payroll step 1: "4 one-off pay items from Updates will be
   included for 2 people (2,600,000 ₫ added to pay, 50,000 ₫ taken from pay)."
7. `12-payrun-review-clash` — the run's review step ("Review exceptions"): "One pay item has two
   amounts — Bùi Hữu Bảo, KPI Bonus (in) · November 2026, From Updates 1,500,000 ₫ or In the pay
   data file 2,000,000 ₫" with **Use the Updates amount / Use the file's amount**.
   `13-payrun-choice-made` — after "Use the Updates amount": the box is gone, server check: his
   payslip now reads 1,500,000 from Updates with the file's 2,000,000 as the ignored side, both
   his one-offs reserved by it, the file line linked to it.
8. `14-home-in-pay-run` — Past updates "In pay run Payobook Retail — End-Month Payroll ·
   November 2026"; `18-home-clash-card` — the same question on the Updates home card, answered
   there too.
9. `15-could-not-be-made-updates`, `17-records-could-not-be-made` — "Could not be made" with the
   reason on Updates and on the Records screen's History (button "See the request" kept);
   `16-records-history-oneoff` — the one-off update in Records history.
10. `19-lasting-start` — the lasting-change start screen unchanged under the new choice.

Found and fixed on the walk: "empty" over a new one-off amount (now "new"); the cancel button of
a "Could not be made" update read "Cancel the scheduled part" (now "Cancel it", with its own
sentence); the summary refresh after a choice showed the global loader (now silent); the month
picker stretched full width; the done line's icon; the proposal title "· 4" (now "· 4 amounts").
**Found and NOT fixed (deviation R8.1):** on payobook the Run Payroll screen computes the demo
divisions' payslips with the demo generator's shortcut, which reads no input source at all — so
a demo-division run shows the step-1 line and the D11 question but does not put one-offs into
the payslips it computes until they are recalculated.

## R4. Deploy evidence (five databases)

Unit `updates-p2d-20261111T093000Z` under `flock /tmp/payobook-studio-deploy.lock` (it waited for
the WORKFLOW-2 P2b deploy to release the lock); START 09:34 / DONE 09:40 UTC in
`/opt/deploy-notes.md`. Evidence `/tmp/updates-p2d-20261111T093000Z/`.

- Dry run first: server `pb_updates` tree = pre-phase commit (e70c180c7d627d18), staged tree =
  repo HEAD (e4577742b0f62fcb). Only `pb_updates` deployed; no standard addon, no other module.
- **Backups (tier 3), before the stop**: `/odoo/backups/updates-p2d-20261111T093000Z/` — payobook
  78,972,771 B, payobook_template 27,644,526 B, p0clone 27,969,937 B, rize 41,409,419 B, sudima
  27,643,006 B (`*.pre-updates-p2d.dump`), plus `pb_updates.prev`. Nightly backups untouched.
- `-u pb_updates` on all five: EXIT=0, **0 ERROR/CRITICAL** in every upgrade log; table
  `pb_updates_oneoff` present on all five (0 rows after the live check except payobook's one
  cancelled row).
- **Active scheduled jobs unchanged** — 50→50, 32→32, 39→39, 82→82, 81→81; nothing re-activated,
  nothing lost, no new job.
- Assets: signal row + `/web/assets/%` purge + `web.assets.version` bump on all five.
- **Downtime 1 min 39 s** (09:35:31–09:37:10). **No test in the stopped window** (G19).
- Sites after start: payobook.com, p0clone, rize, sudima 200. Server log since start: 0 ERROR.
- Live `p0clone`, after start, `--http-port 8471`: **pb_updates 79/79**, 0 ERROR.

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| `pb_updates` latest_version | 19.0.1.3.0 | 19.0.1.3.0 | 19.0.1.3.0 | 19.0.1.3.0 | 19.0.1.3.0 |
| table `pb_updates_oneoff` | yes | yes | yes | yes | yes |
| active jobs before → after | 50 → 50 | 32 → 32 | 39 → 39 | 82 → 82 | 81 → 81 |
| one-offs waiting after the check | 0 | 0 | 0 | 0 | 0 |

Tree hash (sha256 of sorted per-file sha256, skipping `__pycache__`, `*.pyc`, `.DS_Store`), repo =
server: `pb_updates` e4577742b0f62fcb.

## R5. Live check (payobook, server-side as the QA user)

Rehearsed first on a fresh local copy of payobook (three rounds; it found that runs and payslips
must be created the way the Run Payroll screen creates them — as superuser, Access Studio refuses
the QA user's direct create — and computed the way `compute_batch` computes them, `sudo` with
the QA user acting). Log `outputs/updates-p2d/live-check-log.txt` (not committed).

1. Person: the demo-world Retail employee with the `ess1` demo login (company Payobook Vietnam
   JSC, Retail end-month scheme), pay item "KPI Bonus (in)", pay month **January 2027** — no run
   of any kind exists that month. Before: 0 runs, 0 payslips, 0 one-offs waiting, 0 period inputs.
2. Own-headings CSV → read columns → review (`ok`) → apply "P2d live check - one-off":
   **approved at once** (company 5 has no approval route), RD00179.
3. A NEW draft run for January 2027 on that scheme, one payslip, computed: **KPI Bonus =
   1,234,000 from Updates** (`updates_oneoff`), row **reserved** by that payslip.
4. Run cleared with the screen's own clean-up: run gone, row **back to waiting**.
5. Update cancelled from Updates: row **cancelled**.
6. After = before (0 runs, 0 payslips, 0 waiting, 0 period inputs) — **RESTORED**.
7. Browser, look only, existing session: payobook People › Updates shows the third tile, the
   cancelled live-check update with the coins icon, the one-off start screen; console clean
   (`20-live-payobook-oneoff-start.jpg`). sudima: the browser extension may not open that host,
   so its Updates home was checked server-side, read only (loads; "None of your pay schemes has
   a one-off pay item yet" — sudima has no active scheme). Nothing applied on rize or sudima.

Left behind on purpose (audit, not data; D10): one cancelled named update with its file, its
approval proposal RD00179 and the cancelled one-off row with its history. Payslip/run sequence
numbers moved on by one. No demo data deleted or changed.

## R6. Application-data mode — what was done

**Not covered; the notice ships** (handover §3 rail). That mode certifies a frozen snapshot of
exactly three accepted sources (employee field, contract component, period) and refuses approval
when stored inputs differ from it (ledger U25). Feeding one-offs into it cleanly needs a fourth,
certified source inside `pb_hr_payroll_formula`'s snapshot — a change to the certification
kernel, not something to bend from outside. So:

- seam 1 returns at once in the application-data context (`pb_application_data_mode`), and the
  three compute wrappers skip application-mode payslips: nothing is read, reserved or paid;
- Run Payroll step 1, for a scheme with application data switched on: "N one-off pay items from
  Updates are not included in a pay run from application data. A run with a pay data file, or
  without one, includes them.";
- the application-data "Review pay data" worksheet: "N one-off pay items from Updates are not
  included in this kind of pay run. Run it with a pay data file, or without one, to include
  them." (`hr.payroll.preparation._workspace`, one template line);
- the one-offs stay "Waiting for a pay run" — never dropped.

Only rize uses application-data runs today (P2b report R7.1); payobook, payobook_template,
p0clone and sudima do not.

## R7. Which surface carries the two buttons (D11)

1. **The Run Payroll screen's review step** ("Review exceptions", `pb_payrun_wizard`), extended in
   place from `pb_updates` (template inheritance + a small JS patch; the data comes with the
   step's own `get_summary`). A box above the exceptions list: both amounts, "Use the Updates
   amount" / "Use the file's amount", for payroll runners only.
2. **The Updates home**, "Waiting for a pay run" card — the same question and buttons, because
   the review step lives only as long as the screen is open.

Both call `pb.updates.oneoff.resolve_clash`. No new screen. Meanwhile the run cannot finish for
that person: the pay-file payslip is not made, the no-file compute refuses with the sentence
(it shows in the exceptions list), and a payslip of that person in that run cannot be marked
done. Choosing recomputes that person's payslip from the pay data file at once.

## R8. Deviations, and why

1. **Demo-division runs on payobook (pb_demo) do not read one-offs at compute time.** On payobook
   every company-5 scheme is a demo division, and the Run Payroll screen computes those payslips
   with the demo generator's own shortcut (`pb_demo/models/demo_payrun.py` `compute_batch`), which
   stages generated inputs and calls no input resolver at all — not contracts, not files, not
   Updates. Covering it would mean `pb_updates` overriding `pb_demo` (not a dependency; MRO not
   guaranteed). Every real path is covered (E2-E14); on payobook a one-off reaches a demo payslip
   on "Recalculate" (seam 1), and a D11 question still blocks finishing. The live check therefore
   computes its payslip the way the generic Run Payroll does (`compute_sheet`), not through the
   demo shortcut. Owner item R9.1.
2. **Approval vehicle** = the named update's one `pb.records.apply`, flagged `updates_oneoff` (the
   smaller of the two options): same process key, routes, inbox, Cancel/Withdraw; the drawer shows
   "Bonus · November 2026: Now → In this update". Its Records-history Undo takes back what no run
   took (with the same write-permission gate).
3. **Store keyed by month; scheme kept for the mid-month rule.** A row also stores the scheme it
   was entered under: a MID-month scheme reads only rows entered for it; end-of-month / any-run
   schemes read any row whose code is one of their one-off items. Without this, a mid-month
   advance run (ending on the 15th) would have paid the month's bonus (E14).
4. **One-off items are narrower than U24 literally reads**: money only (no hours/days quantities —
   those are time, P4), and minus the codes the run fills itself (`BASIC/WAGE/BASE`, mapped
   fields, the mid-month carry-over target, the Awards board code `INCENTV`, contract-line
   templates, the templates' own "recurring salary"). Without the last, every scheme's base pay
   input showed up as a "one-off" (seen in the fixture).
5. **What counts as "the file carries a value"** (D11): a numeric cell found by the file's own
   column. The resolver can also bind by column LETTER, which handed a file without the item's
   column the Name column read as 0 (G32); a template's filler 0 is a blank unless entered for the
   month (G33). A 0 typed in a plain pay data file IS an amount and asks.
6. **A connected-system value on the no-file path** (rare: a feed wired to a one-off item) with a
   different amount refuses the compute with a sentence ("…from the connected system. Remove one
   of them…") rather than buttons — the handover's buttons are for the pay data file.
7. **The verdicts reach the reserving code through a per-cursor token, not a dict in the context**
   (G31) — the template resolver copies the context.
8. **Run Payroll step-1 line sits above "Batch name"** (shown whether or not the scheme picker is),
   from the scheme preview the screen already asks for.
9. **No "Undo" on a one-off update**; "Cancel" takes back what no pay run has taken, says how many
   stay in a run.
10. **"Could not be made"** is read off the approval request (`state='approved'` + `block_reason`)
    for a change still `pending` — the engine leaves exactly that shape (it rolls back the
    change's own block note with the failed write). Records history keeps "See the request" (where
    it can be tried again).

New ledger entries: D11, U21–U28 (the handover's U19–U24 renumbered, noted once), G31–G38.

## R9. Needs an owner decision / owner action

1. **payobook demo runs and one-offs** (R8.1): to SHOW one-offs in a demo pay run on payobook.com,
   either press "Recalculate" on the run after computing, or decide that the demo generator should
   read Updates one-offs too (a small change in `pb_demo`). Recommend: change `pb_demo`.
2. **Application-data runs (rize)** do not read one-offs (R6). Covering them needs a certified
   fourth source in the payroll certification kernel — a separate, careful phase. Until then rize
   should keep entering one-offs the way it does today for application-data runs.
3. The live check left one more cancelled update ("P2d live check - one-off") in payobook's Past
   updates (kept per D10).
