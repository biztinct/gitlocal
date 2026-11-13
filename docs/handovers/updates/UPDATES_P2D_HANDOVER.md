# UPDATES — Phase 2d handover: one-off pay items for a pay month

Start only after Phase 2c is live (same modules). Read first: `UPDATES_LEDGER.md` (all of
it), `UPDATES_P2C_REPORT.md`, then `UPDATES_P2A_REPORT.md` §R7.4 and `UPDATES_P2B_REPORT.md`
§R7.1–2. Visual reference: `docs/design/updates-desk-prototype.html`.

**Design mandate (owner, verbatim): "extreme WOW, intuitive, out-of-this-world experience,
best in class".** Indigo design system (`#5A4BB0`), white cards, Lucide icons, never emoji.

**White-label rule:** the word "Odoo" never appears in any user-visible string. Technical
identifiers stay. **Plain words on screen**: "one-off pay item", "pay month", "pay run",
"pay data file", "pay scheme" — never model names, state keys or rule codes in a sentence.

First job of this phase: add to the ledger decision **D11** and facts **U19–U24** below
(the ledger was being edited by Phase 2c when this was written).

## 1. Owner decision D11 (2026-11-11) — do not re-ask

When an approved one-off from Updates and the pay data file BOTH carry a value for the same
person, pay item and pay month, the pay run **stops and asks**: it shows both amounts and
does not finish until somebody picks one. Never silently one or the other, never the sum.

## 2. Scope

1. A second kind of sheet in People › Updates: **"One-off pay items for a pay month"** —
   bonus, one-time deduction, overtime amount and the like — entered any day, before the
   pay run exists, through the same four steps (Start → Match columns → Review → Apply).
2. **One store** for them, approved through the approval engine, read by every kind of pay
   run, paid once.
3. The clash rule D11.
4. "Waiting for a pay run" on the Updates home; one line in pay-run preparation.

Versions: `pb_updates` → `19.0.1.3.0`; `pb_hr_payroll_formula` patch bump if a file there
changes (prefer overrides living in `pb_updates`; see §5).

## 3. Binding non-goals and safety rails

- **The three existing stores are not changed, migrated or read by the new one**:
  `hr.payroll.period.input`, `pb.payroll.month.inputs`, `pb.incentive`/`pb.oneoff.feed`
  keep working exactly as today. No draft row is ever created in
  `hr.payroll.period.input` (a draft there blocks application-data runs, U19).
- **A run with no Updates one-off for its people and month computes byte-identically to
  before** — same inputs JSON, same sources, same lines (test E1, on every run mode).
- **Never pay twice, never drop silently.** Paid-once tracking is part of the store (§4);
  every ignored or overruled value is recorded with who decided.
- **Earnings stay earnings.** The sign comes from the pay item (`net_role`), never from a
  minus typed in a cell: a negative amount is refused in a sentence.
- No proration of a one-off; merge AFTER the engine's proration/back-pay/segment
  adjustments (U22).
- If application-data mode cannot be covered without weakening its freshness check
  (U23), do not force it: leave that mode reading nothing from the new store, make
  pay-run preparation say "N one-off items from Updates are not included in this kind of
  pay run" for it, and report. The other modes still ship.
- No approval split, no new joiners, no timesheets. No change to the Awards board.
- Never apply anything on `rize` or `sudima`. Do not touch `pb_lifecycle`, `pb_hiring`,
  `pb_me_expense`, `pb_timeoff`, `docs/handovers/workflow2`.

## 4. Verified plumbing facts U19–U24 (from read-only research 2026-11-11; do not re-derive, do re-grep line numbers)

- **U19** `hr.payroll.period.input` (`pb_hr_payroll_formula/models/payroll_period_input.py`):
  managers only, `reason` + `evidence_reference` required, exact `date_from`/`date_to`
  match (`:418`), any draft row is a conflict that blocks application-data run creation and
  compute (`:432-434`; `application_payroll_source.py:710-712`). Read only by
  application-data runs. Its reserve/consume/release pattern (`:318-356`, `:498-513`) is
  the precedent to clone for paid-once.
- **U20** `pb.payroll.month.inputs` (`pb_payroll_templates/models/templates.py:68-79`): JSON
  keyed by `"rule:<id>"`, default zeros indistinguishable from entries except via
  `origins`, no state, no approval, values frozen into import lines at attach. Template
  runs are recognised by filename `Payobook-month-YYYY-MM.xlsx` (`:1184-1191`) and their
  resolver override calls `super()` (`:1231`).
- **U21** `pb.incentive` awards are pushed into an already computed run only when somebody
  presses "Queue this month" (`pb_comp_ben/models/oneoff_feed.py:258-335, 440-476`),
  earnings only, one code (`INCENTV`), and are LOST on native "Compute Sheet", on a
  pay-file recompute when the file has a column for the item, and on application-data
  recompute. Not a base to build on.
- **U22** There is no single input resolver. Two seams cover every mode:
  (1) the end of `hr.payslip._get_formula_input_values`
  (`pb_hr_payroll_formula/models/hr_payslip_formula.py:199`; bridge-override precedents:
  `pb_workforce_payroll_bridge/models/hr_payslip.py:28-80`,
  `pb_trip_payroll_bridge/models/hr_payslip.py:15-60`) — no-file compute, both recompute
  branches, native Compute Sheet;
  (2) the end of `hr.payroll.import.batch._transform_data_to_formula_inputs`
  (`payroll_import_batch.py`, `return` near `:4978`; override precedent
  `pb_hr_payroll_vietnam/models/dependent_count_source.py:62-78`) — pay-file create
  (`:3773`), pay-file recompute (`hr_payslip_formula.py:1138`), template runs. The
  full-and-final and run-input-review screens call this resolver too. The file's value for
  a code is found by `_lookup_in_blob` candidates (`:4596-4660`); the standing rule for a
  losing side is `input_provenance.ignored_side` (`:4456-4458`, `:4761-4773`).
- **U23** Application-data mode reaches seam 1 (`application_payroll_source.py:746`) but
  accepts a value only when its source is `employee_field`, `contract_component` or
  `period` (`:794-807`), drops values for rules that have an `application_source_key`
  (`:779-784`), and refuses approval when stored inputs differ from the frozen snapshot
  (`:1106-1107`, checked `:1015-1022`, `:1035`, `:1141`).
- **U24** One-off pay items of a scheme = `config.rule_ids` with `column_type == 'input'`,
  not `is_contract_component`, not `is_text_component`, `column_role == 'payroll'`,
  numeric `value_kind`, no Records Desk card / field mapping (the "recurring" test,
  `templates.py:305-336`), `application_settlement_kind == 'none'`. `net_role`
  (`formula_net_role.py:602`) says earning or deduction. The closest curated list is the
  Templates layout's `adjustments` lane. Who is in a scheme for a month before a run
  exists: `_eligible_employees(config_id, date_start, date_end)`
  (`pb_payrun_wizard.py:646`). Pay-run dates are free to type; only calendar-month schemes
  have derivable dates — so the store is keyed by MONTH, not by exact dates.

## 5. Design

### 5.1 The store (`pb_updates`)

`pb.updates.oneoff` — one row per person × pay item × pay month:
`employee_id`, `company_id`, `code` (the pay item's rule code, the same key the engine
uses), `label` (as shown when entered), `period_month` (Date, 1st of month), `amount`
(> 0), `batch_id` (`pb.updates.batch`), `state`
(`pending` → `approved` → `reserved` → `paid`; `cancelled`; `replaced`),
`reserved_slip_id`, `paid_slip_id`, `clash_choice` (`updates` / `file`, with
`clash_by`, `clash_at`, `clash_file_amount`), `config_name` (the scheme at entry, for
display only). `models.Constraint`s (G1): one live row (`approved`/`reserved`/`paid`) per
employee + code + month; amount > 0. Access: read for Records viewers, write only through
the model's own methods (no direct ACL write for users); record rule by company.

Approval: the BATCH is what is approved, through the approval engine exactly as a records
change is (same process key and routes as `pb.records.apply`, so no company needs new
set-up; reuse `biz.approval.adapter.mixin` on the batch or on a thin apply row — pick the
smaller, report which). Approved → its rows become `approved`. Cancel (Phase 2c's rules)
→ rows `cancelled`.

A later sheet for the same person + item + month: REPLACES an `approved` row (old row
`replaced`, shown in review as old → new); `CLEAR` cancels it; a `reserved`/`paid` row
refuses: "<Item> for <month> is already in pay run <name>. Change it there."

### 5.2 Which run reads a row

A payslip reads the `approved` rows of its employee whose `code` is a one-off pay item
(U24) of the SLIP's own pay scheme and whose `period_month` is the month of the slip's end
date. The first slip that computes with it reserves it (`reserved_slip_id`); other slips
(a top-up run with the same dates) do not see it. Recompute of the same slip keeps its
reservation. Slip done/paid → `paid`. Slip cancelled, deleted or the run cleared →
released back to `approved` (clone U19's hooks; also cover `_clean_period`,
`pb_payrun_wizard.py:1047-1089`). One helper, `pb.updates.oneoff._for_slip(employee,
config, date_to, slip)` → `{code: row}`, is the only reader.

### 5.3 The two seams (U22) and the clash (D11)

Overrides in `pb_updates` (new file), each calling `super()` then merging through ONE
shared method:
- value absent from every other source → the one-off's amount is used; the inputs' source
  entry says it came from Updates (follow the existing source/provenance vocabulary).
- the pay data file (or a template month file) carries a non-blank value for that code:
  - equal amount → use it once; record that both agreed;
  - different amount and no `clash_choice` → **the slip is not computed to a result**:
    raise/collect a conflict in the same way the path already reports a blocking input
    problem (pay-file path: the batch's existing blocking-issue mechanism; no-file path
    cannot clash). The pay run's review screen lists it — "Bonus for <name>: <amount> from
    Updates, <amount> in the pay data file" — with two buttons, **Use the Updates amount**
    / **Use the file's amount**. The choice is stored on the row (`clash_choice` + who +
    when + the file's amount); choosing "file" marks the row `paid` against that slip with
    amount noted as overruled (it must not reappear next month); the losing side is
    recorded via `input_provenance.ignored_side`. Then the normal recompute proceeds.
  Find the smallest existing surface for the two buttons (the run's review / "Review pay
  data" issues list) and report which you used; do not build a new screen.
- Application-data mode: attempt only per the rail in §3 (a new accepted source name
  rather than loosening the existing three; the snapshot must include the value so the
  freshness check stays strict). If not clean, ship the "not included" notice instead.

### 5.4 Screens (`pb_updates`)

- **Start**: two large choices — "Lasting changes" (today's flow) and "One-off pay items
  for a pay month" with a month picker (this month default; from 2 months back to 12 ahead).
- **Download sheet**: the chosen people × the one-off pay items of THEIR schemes (U24,
  grouped by scheme in the header band; grey cells where the item is not in the person's
  scheme, as P2b); existing approved amounts for that month pre-filled; "Read me" sheet
  explains month, CLEAR, positive amounts.
- **Match columns**: "Goes to" offers only one-off pay items (grouped by scheme, each with
  a small "adds to pay" / "takes from pay" tag from `net_role`), plus the columns that
  find the person. Remembered layouts are kept separately from lasting-change layouts.
- **Review**: the P1/P2b grid; cell states new / replaces <old> / same / cleared / not in
  their pay scheme / refused (negative, not a number, already in a pay run, person not in
  any scheme that month). A header total per pay item and a grand total "adds to pay" /
  "takes from pay" for the month. A warning chip when a FINISHED pay run already exists
  for a person's scheme and month: "Already paid for <month>; this will wait for another
  pay run in that month, or never be paid."
- **Apply / Done**: "Sent for approval" or "Approved", and "These will be included in the
  <month> pay run."
- **Home**: card "Waiting for a pay run" — per month: people, items, total; opens a list;
  each batch can be cancelled until a pay run has taken it. Past updates shows one-off
  batches with a distinct icon and states (waiting for approval / waiting for a pay run /
  in pay run <name> / paid / cancelled).
- **Pay-run preparation**: one informational line "N one-off items from Updates will be
  included (total …)" — or the "not included in this kind of pay run" line.
- Vietnamese translations for every new string (G2, G6).

## 6. Tests (numbered)

| # | Case | Expect |
|---|---|---|
| E1 | No-file run, pay-file run, template run, application-data run with NO Updates one-off | inputs, sources and lines byte-identical to before (capture first) |
| E2 | Approved bonus, no-file run | in the slip once; row `reserved`, then `paid` when the slip is done |
| E3 | Same on a pay-file run whose file has no column for the item | same |
| E4 | Same on a template (month file) run | same |
| E5 | Recompute, native Compute Sheet, "Recalculate everyone" on each mode | value still there, still once |
| E6 | Two runs, same scheme, same month (regular + top-up) | paid in the first only |
| E7 | Slip cancelled / deleted / run cleared | row back to waiting; next run pays it |
| E8 | Clash, different amounts | run stops; both amounts listed; each button resolves; choice, person and file amount stored; ignored side recorded; "file" choice never pays the row later |
| E9 | Clash, equal amounts | paid once, no stop |
| E10 | Pending (unapproved) and cancelled rows | never read |
| E11 | Deduction item | lands as a deduction; negative typed amount refused |
| E12 | Item not in the person's scheme; person in no scheme | greyed and skipped / refused in a sentence |
| E13 | Replace an approved row; CLEAR it; try to change a reserved row | replaced / cancelled / refused with the sentence |
| E14 | Month matching: slip ending 30 Nov reads November rows only; mid-month scheme slip reads only its own scheme's items | as stated |
| E15 | Application-data mode | covered with the freshness check intact, OR the notice line and nothing read |
| E16 | Approval route present: approve, send back, turn down, cancel | rows follow the batch |
| E17 | The three existing stores and the Awards board | untouched (their suites green) |
| E18 | Full suites `pb_records`, `pb_updates`, `pb_hr_payroll_formula`, `pb_payroll_templates`, `pb_payrun_wizard`; review speed 4,575 × 73 | green; ≤ 25 s |
| E19 | `.po` parse gate; "Odoo" scan of new strings | clean |

Demo fixtures: reuse the persistent demo schemes; no "ZZ", no "RIZE" in names.

## 7. Browser validation, deploy, report

- Browser (local copy, console read at every step, company of the people — G22): the whole
  one-off flow, the home card, a pay run that includes a one-off, and the clash with both
  buttons. Screenshots to `outputs/updates-p2d/` (never committed).
- **Tier 3** on all five (`payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`;
  never `abm`, `pbf_preview`, `recruit_connect_20261023`): deploy-notes START/DONE + flock;
  `pg_dump` of all five first; scoped per-module rsync; cron snapshot before/after (expect
  no new job); asset purge; **no tests in the stopped window** (G19); hashes and versions
  on all five; suites on live `p0clone` after start on free ports.
- Live check on `payobook`, server-side as the QA user, DEMO people in Payobook Vietnam
  JSC, on a NEW draft pay run made for the check in a month with no real demo run, or — if
  that would disturb demo data — on a database copy with jobs and mail servers switched
  off first (memory note `copy-db-runs-live-crons`): one-off approved → run computes with
  it → run deleted → row released → batch cancelled. Leave nothing waiting and no run
  behind. Look-only in the browser on `payobook` and `sudima`.
- Commit per feature with explicit paths, credential scan, push `origin 19.1`.
- Report `UPDATES_P2D_REPORT.md`: E1–E19 with output; which surface carries the clash
  buttons; what was done for application-data mode; deploy evidence ×5; deviations; new
  gotchas; ledger phase map updated. For Phase 3, answer nothing new — Phase 2c's report
  carries that research.
