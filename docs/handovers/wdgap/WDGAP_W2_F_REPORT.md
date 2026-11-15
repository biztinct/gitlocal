# WDGAP W2-F — report: five small items after round W2

Branch `wdgap-w2f` from `origin/19.1` @ `7f0fa3aad`. Not merged, not deployed, no live
server touched. Handover: `WDGAP_W2_F_HANDOVER.md` (copied into this branch).

## 1. What was built

| Item | Module | Version | Commit |
|---|---|---|---|
| F-1 An Extra run never takes the mid-month advance twice | `pb_hr_payroll_formula`, `pb_payrun_wizard`, `pb_payslip_review` | 19.0.1.167.0 → **19.0.1.168.0**; 19.0.1.45.0 → **19.0.1.46.0**; 19.0.1.5.0 → **19.0.1.6.0** | `15e219c24` |
| F-2 Fund payments: one sign-off (Head of pay) + migration | `pb_fund_payments` | 19.0.1.0.0 → **19.0.1.1.0** | `e354c0780` |
| F-3 Suggest leaves out loan repayments and the advance | `pb_fund_payments` | (F-2's version) | `f9b32d0aa` |
| F-5 Older offer calculator shows Earnings/Deductions again | `pb_formula_studio` | 19.0.1.213.0 → **19.0.1.214.0** | `fb8365ed2` |
| F-4 "Tax year starts in" on the Studio Health tab | `pb_formula_studio` | (F-5's version) | `d9e675785` |
| Browser-walk fixes | `pb_formula_studio`, `pb_payrun_wizard` | (same versions) | `847aba261` |

### F-1 — the advance, once
- **What "the advance" is**: only what the scheme's carry-over setting types — the active
  `hr.payroll.cycle.component.mapping` rows with the scheme as the end side (the rows
  `_apply_mid_cycle_carryover` itself reads), spelt as it writes them (`code or
  column_letter`). No code is written anywhere. (`hr.formula.config.mid_cycle_target_component_id`
  exists but nothing reads it; not used.)
- **Where**: `pb_hr_payroll_formula/models/advance_once.py` + one branch at the carry-over call in
  `_transform_data_to_formula_inputs`. `pb_payrun_wizard` cannot inherit the import batch (no
  dependency on the engine), so the read sits with the carry-over it decides about; the run kind
  is read by name (`pb_run_kind`), the W2-A precedent.
- **The rule**, per person, only when the batch feeds an Extra run of an end-of-month scheme:
  - **taken** — another payslip of the scheme family (the scheme and its branches) for the same
    month, worked out (not cancelled, not a draft without lines), not in this run, carries a
    non-zero advance → the Extra run feeds **0** for the advance input(s) and the payslip records
    where it was taken (`hr.payslip.pb_advance_taken_in_id`, new stored column, empty on every
    other payslip). Read on create AND on "Recalculate" (idempotent, tested). I read "regular (or
    carry-over consuming)" as: any worked-out payslip carrying the advance — a regular one, or an
    earlier Extra run that was itself the one to take it. A regular one is named when several do.
  - **undecided** — nothing carries it but the month's REGULAR payslip exists and is not worked out
    → unchanged (the Extra run takes it), flagged with why.
  - **free** — nothing carries it, no regular payslip waiting → **unchanged: the Extra run may be the
    one that takes it.** PR-E's flag and sentence stay exactly as they were (handover: "behaviour is
    unchanged").
- **Screens**: pay-data step, before computing — "The mid-month advance was already taken in
  August 2026 for 2 of the people picked. This extra run will not take it again." (one person:
  "…for the person picked."), calm indigo line with an info icon; the result step repeats it; the
  review step and Pay Run › Payslips show a NOTE, not a flag: "Advance not taken again (already in
  August 2026)" — never counted under Need review (new optional `note` key in the shared
  `pb_review_flags` answer; both screens show it quietly). Flags that remain say why:
  "Takes the mid-month advance: <run> is not worked out yet, so it could not be told whether it
  takes it too", and — when the regular run was worked out AFTER the Extra run and took it too —
  "Takes the mid-month advance, and <run> took it too — it is taken twice".
- Regular and top-up runs never reach the new branch: golden test A7 recorded on `origin/19.1`
  (inputs, sources, lines, flags of both runs) passes unchanged on the branch.

### F-2 — one sign-off
- Seed: `fundpay` default route = ONE step "Head of pay" (`pay_head`, filled from the payroll
  manager group — `pb_loans`' seat and code shape). New installs and new companies get it.
- Migration `pb_fund_payments/migrations/19.0.1.1.0/post-migrate.py`: per company, rewrites ONLY a
  route that is still exactly what 19.0.1.0.0 seeded (one workflow named "Fund and tax payments",
  one published revision whose definition fingerprint = the old two-signature definition, the one
  default binding to it) AND where no approval request of process `fundpay` exists for the
  company. The rewrite is a new published revision of the same workflow (the old one is kept as
  "Replaced"), binding untouched, reason "Set to one signature, the Head of pay". Anything else is
  left; one log line per company says which ("changed", "already used", "changed by the business").
  Proven on a real upgrade of a 19.0.1.0.0 database: company 1 → `1:superseded, 2:published,
  pay_head`.

### F-3 — Suggest
- Keeps W2-B's typing (pay role) and always leaves out, from the scheme's own settings: the "Loan
  repayments go into" item (`pb_loan_rule_id`, read by probe — no dependency on `pb_loans`), the
  advance items (F-1's typing, both sides of the mapping), and every component whose formula reads
  nothing but those (and fixed values) — so the "Loan repayment" line fed by the instalment input
  goes too, while a line reading the loan AND other pay stays. The "untick it" note is gone.
- **Limit (owner question 1)**: on a scheme where "Loan repayments go into" is not set, Suggest
  cannot tell a loan line from a fund. The payobook.com demo schemes feed `INLOAN` / `LOANREP` from
  the demo generator by code and have no such setting, so "Loan Repayment" is still offered there.
  The mid-month advance IS typed on the demo (its carry-over mapping) and is left out. Demo data
  not changed.

### F-4 — Tax year on the Studio
- Health tab (the Studio's scheme panel) gets a row of its own: calendar icon, the field's own
  label and help ("Tax year starts in", already in Vietnamese from W2-A), a month list. Saving goes
  through the scheme's own `write` (the form's path: tracked; scheme settings follow no approval —
  only components and money fields are gated). With finished payslips the first press shows the
  form's own warning ("Year-to-date figures for this scheme will be counted from April from now
  on. Finished payslips are not changed.") with **Change it** / **Keep it as it is**; nothing is
  saved until "Change it". Read-only when the login may not change the scheme.
- Found and fixed on the way: the Studio kept the Health tab's data of the PREVIOUS scheme after
  another one was opened (ledger W2F-2) — it is now reset and re-read.

### F-5 — older offer calculator
- **Reproduced** on a local copy with the `origin/19.1` code: `offer_calc` answered `subtotals: []`
  (tests F5.1/F5.2 fail on that code — run "golden" in §2). **Cause: code, not demo data** — the
  boxes were totalled on bare `hr.payslip.line.new()` lines, and `pb_payruns` totals per payslip,
  so lines with no payslip add up to 0 wherever `pb_payruns` is installed (ledger W2C-1).
- **Fix** (smallest): build the same lines inside an in-memory payslip (`hr.payslip.new`, never
  saved), the take-home calculator's way. Boxes still read the one pay-band rule.

## 2. Tests

Local copy of `upd_p6_t_tpl` (`wdgap_w2f_t`, one database the whole time, dropped with its
filestore at the end). Baseline = `-u` the 33 modules behind + `-i pb_loans,pb_fund_payments` with
PRISTINE copies (`git archive` of `origin/19.1`) of the five touched modules first on the path, run
before any edit was loaded. After = the branch code `-u` the touched modules on that same database
(which also ran the F-2 migration for real) with the same tags.

| Run | Tests | Failed | Errors |
|---|---|---|---|
| Baseline `/pb_hr_payroll_formula,/pb_payrun_wizard,/pb_payslip_review,/pb_fund_payments,/pb_formula_studio,/pb_loans,/pb_payroll_templates` | 1,544 | 12 | 1 |
| After (same tags) | 1,565 | 13 | 1 |
| Re-run `/pb_payrun_wizard,/pb_formula_studio:TestW2fStudio` after the last code edits | 127 | 1 | 0 |
| Re-run `/pb_formula_studio:TestW2fStudio` (F4.2 test fixed) | 6 | 0 | 0 |

The 13 baseline failures/errors are identical before and after (the known set: TestRd49SyncCost
×2, TestRecordsR1OneTime 07b, TestSchemeCtxCurrency 04, TestJourneyView ×2, TestNetPayCandidates
01, TestOneMappingHome ×4 incl. the error, TestRunsrcPcBoardLane 14, TestRunInputReview monthly
duplicate label). The one extra failure after was my own F4.2 asserting the tracking message, which
is only written at commit (never in a test); F4.2 now proves the form's path by spying the scheme's
own write — 6/6 pass. Per-module counts: `pb_payrun_wizard` 145 → 155, `pb_fund_payments` 25 →
36, `pb_formula_studio` 619 → 627, the others unchanged.

| # | Case | Result |
|---|---|---|
| A1 | Taken before: regular run took Ann's ₫3,000,000; Extra run feeds 0, records the regular payslip, pre-flight + result sentence, review note not flag, summary Need review 0, regular untouched | pass |
| A1b | Three picked, two kept out: "for 2 of the people picked", notes on the two only | pass |
| A2 | Not taken before: Extra run takes it (₫3,000,000), PR-E flag unchanged, no note | pass |
| A3 | Regular payslip not worked out yet: takes it, flagged "…is not worked out yet…" | pass |
| A4 | Extra first, regular after: flagged "…took it too — it is taken twice" | pass |
| A5 | No carry-over setting: nothing decided, Extra gets exactly what the regular run got from the file | pass |
| A6 | Recalculate twice (Extra and regular): identical inputs, sources, record and lines | pass |
| A7 | GOLDEN regular + top-up on the advance fixture, recorded on `origin/19.1` | pass |
| F2.1 | New company: one step, `pay_head`, "Head of pay", someone holds the seat | pass |
| F2.2 | Untouched old route rewritten once (new revision, old "Replaced", binding kept); second run leaves it | pass |
| F2.3 | Old route with a request: left | pass |
| F2.4 | Old route renamed, or re-published by the business: left | pass |
| T8 (changed on purpose) | Real route: one signature, the Head of pay holds no payroll role (W2B-2 rail kept) | pass |
| T1 (changed on purpose) | The lone-deduction note is gone | pass |
| F3.1–F3.3 | Loan input + its repayment line + the advance not offered, tax offered; without the settings they are offered; a line reading loan AND basic stays | pass |
| F4.1–F4.4 | Payload; saved at once through the scheme's write; warning first with finished payslips, then saved; refusals (bad month, same month, no rights) | pass |
| F5.1–F5.2 | Boxes back (₫10M / ₫1M), nothing saved; three boxes, gross counted once — **both fail on `origin/19.1`** (the reproduction) | pass |

Static gates: `py_compile` and pyflakes on every changed Python file; the three changed OWL
templates parse; `node --check` on both changed JS files; PO gate with the framework's
`PoFileReader` — `pb_payrun_wizard` vi (11 new), `pb_hr_payroll_formula` vi (2, model terms),
`pb_fund_payments` vi + id (1 each), `pb_formula_studio` vi (6): all parse, every new msgid reaches
a screen, no msgstr names the vendor; no added user-visible line names the vendor.

## 3. Browser walk (local copy, Claude in Chrome, console clean on every screen)

Seeded "DEMO Walk Co" (a company of its own): a live end-of-month scheme asking for a pay data file
(basic, meal, advance, loan input → loan repayment, tax, insurance, employer insurance, net), its
mid-month scheme and carry-over link, five DEMO people, ₫6,000,000 posted advances for three, the
August regular run loaded from a file and finished.
1. **F-1** Run payroll → Extra run → An, Binh, Dung → August → upload a 4-row file: "This file has 4
   people. This extra run keeps the 3 you picked." and "The mid-month advance was already taken in
   August 2026 for 2 of the people picked. This extra run will not take it again." Computed 3 of 3;
   result step repeats both lines; review step lists "Advance not taken again (already in August
   2026)" for An and Binh. Database: An and Binh fed 0 with the regular payslip recorded, Dung 0
   with nothing recorded; take-home ₫500,000 each (before the fix An and Binh would have read
   −₫5,500,000). Pay Run › Payslips: the note in indigo under the name, Need review 0. A second
   Extra run for An alone: "…for the person picked."
2. **F-3** Funds & tax → Suggest: Personal Income Tax and Social Insurance only — no Loan
   Repayment, no Mid-Month Advance, no note. Cancelled, nothing created.
3. **F-4** Formula Studio → the scheme → Health: the row; April → the warning with Change it / Keep
   it as it is; Keep → nothing saved; April again → Change it → "The tax year now starts in April.";
   database April, one tracking line on the scheme.
4. **F-5** Tools → Offer calculator, basic ₫20,000,000: Earnings ₫20,000,000 · Deductions
   ₫2,600,000 · Employer contributions ₫3,500,000, take-home ₫17,400,000.

Found and fixed during the walk (`847aba261`): the tax-year select was drawn full width and squeezed
its label into a one-word column; the review notes read as part of "These items need a look" (now
under "Good to know — nothing to do:").
Not walked: Vietnamese screens (PO gate only), a true phone width, the F-2 route in the browser
(the migration ran for real on the upgrade, and T8 walks the route through the engine).

## 4. Self-review against the handover

| Rule | Verdict |
|---|---|
| F-1 feed 0 + record why when another payslip of the family and month took it; unchanged when not | Met (A1, A2). |
| F-1 identification from the scheme's own typing, never a code; no typing → nothing changes | Met (A5). |
| F-1 calm line before computing; informational review line; old flag removed for those; kept with a reason where undecided | Met (A1, A3, A4, walk). |
| F-1 regular/top-up byte-identical; recompute idempotent | Met (A7 golden on `origin/19.1`, A6). Demo recompute: the demo regular path never reaches the file path's carry-over (unchanged), not re-run on a demo copy (disk) — rehearsal item. |
| F-2 one step Head of pay from the seed; migration only for the untouched, never-used route; both branches tested | Met (F2.1–F2.4, real upgrade). |
| F-3 typing + loan setting (probe) + advance typing; note removed; tested with loan input and advance | Met (F3.1–F3.3, walk). Limit: schemes without the loan setting (owner question 1). |
| F-4 own row, same label, same warning, same path; browser check | Met (F4.1–F4.4, walk). |
| F-5 reproduced, cause found, smallest fix; demo data untouched | Met — cause is code. |
| White-label, vi (+ id where present), PO gate, version bumps, no `pb_pack_*`, no engine internals | Met. The formula evaluation is untouched; the only engine-module change is the carry-over read and one stored field. |

Design bar (owner, verbatim: "extreme WOW, best in class"): F-1's hero is the one calm sentence on
the pay-data step that says, before anything is computed, whose advance will not be taken twice and
where it already was; F-4's is the row that warns in the scheme form's own words and saves nothing
until "Change it".

## 5. Deviations

1. **F-1 code lives in `pb_hr_payroll_formula`** (the carry-over's own module), not the wizard:
   the wizard cannot inherit the import batch. It is the "F-1 read" beside the carry-over call; no
   formula-engine code changed.
2. **F-1 "free" keeps PR-E's flag and sentence** word for word ("behaviour is unchanged"); a calmer
   wording is possible later (owner question 3).
3. **F-1 reads "regular (or carry-over consuming)"** as any worked-out payslip carrying a non-zero
   advance — so an earlier Extra run that took it also counts, and two Extra runs never both take it.
4. **F-1 adds an optional `note` key** to the shared review answer (`pb_payslip_review` 19.0.1.6.0)
   so a line can be shown without being counted.
5. **F-2/F-3 and F-4/F-5 share one version bump per module**; their commits were split by item
   (each commit carries only its own code and tests).

## 6. Deploy notes — RISKY tier (pay run path, a stored column, a route migration)

- `-u pb_hr_payroll_formula,pb_payrun_wizard,pb_payslip_review,pb_fund_payments,pb_formula_studio`
  on all five (`-u pb_hr_payroll_formula` reaches its dependents; expect the 3 PRM-4 lines).
- New column `hr_payslip.pb_advance_taken_in_id` (nullable, nothing backfilled).
- **F-2 migration** rewrites a company's fund route only where it is untouched and unused; the log
  says one line per company. Live today (W2 deploy report): 0 fund payments anywhere, so every
  company's route that is still as seeded becomes one step "Head of pay" — payobook: Mitchell Admin
  (the owner's own account) holds Head of pay in four companies, **SG Company holds nobody**, so a
  fund payment there would block until someone is seated; rize: Ash Sohani; payobook_template,
  p0clone, sudima: Platform support. Check the per-company log lines after the upgrade.
- JS/XML/SCSS changed in `pb_payrun_wizard`, `pb_payslip_review`, `pb_formula_studio`: purge
  `/web/assets/%`, bump `web.assets.version`, restart.
- Rehearsal: recompute one regular demo run per demo scheme old vs new (the regular path is
  untouched; expect 0 differences); live has no Extra run on a mid-month-linked scheme with a file.
- PO gate on the box for the five `.po` files.

## 7. Owner questions (plain words)

1. **"Loan Repayment" still appears in Suggest on payobook.com.** Suggest now leaves out loan
   repayments only on schemes that say where loan repayments go (Loans › set-up, one choice per
   scheme). The 12 demo schemes have never had that set. Should we set it on the demo schemes (12
   choices, nothing else changes), or leave it to whoever sets up loans?
2. **Who signs fund payments for "SG Company" on payobook.com?** After this change it is the Head of
   pay, and that company has nobody in the seat — a fund payment there would wait for someone.
3. **An extra run that is the first to take the advance** (no regular payslip has it yet) still
   shows the old warning "check it has not been taken already". It now could say "nothing else has
   taken it yet". Keep the warning (safer, because a regular run made later would take it again),
   or change it to a calm note?

## 8. New gotchas → ledger

W2F-1 (a reused msgid's translation may name the wrong thing — "người khác" = people), W2F-2 (the
Studio kept the previous scheme's Health data), W2F-3 (PR-E's fixture feeds the advance input the
person's name), W2F-4 (Suggest needs "Loan repayments go into" to recognise a loan), W2F-5 (no
`timeout` on macOS). Also hit, already known: W2A-6 — another phase's local server on
127.0.0.1 signed this walk out mid-way; walking on `localhost:<port>` (its own cookie jar) fixed it.
