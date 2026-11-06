# RUNSRC Phase B — the pay run answers its own period

**Read `docs/handovers/RUNSRC_LEDGER.md` first**, §0 (binding rules) and §1.4,
§1.5. Everything there is verified with file:line — **do not re-derive it.**

Phase A is running in parallel on `pb_formula_studio`. **Do not edit
`pb_formula_studio/models/pb_formula_studio.py` in this phase** — Phase C picks
up the board.

---

## 1. What the owner asked for

> "How to map fields like start and end date of payslip, standard working days
> etc. from the pay run wizard when it runs — and make that editable in the
> wizard (e.g. standard working days so user can change that to account for
> holidays)."

Today **standard working days has to arrive in the spreadsheet every month**.
The run's own dates already answer exactly one thing — `PAYMONTH` — and nothing
else.

Owner decision, already taken: **standard working days defaults to the Mon–Fri
count of the period.** Not a holiday-calendar subtraction. Not a per-scheme
constant. The user adjusts it on the run.

## 2. Scope

**B1 — the period answers more codes.** Extend `pay_period.py` from one code to
six.

**B2 — standard working days is a real, stored, editable number** on the pay
run and on the pay-data load, defaulting to the Mon–Fri count.

**B3 — the guided pay-data wizard collects it**, pre-filled and changeable, on
the same step that already collects the dates.

**B4 — provenance tells the truth.** Every value the run fills is recorded as
coming from the pay period, so the source chip on the payslip says so.

## 3. Binding non-goals

* **`fill_period_inputs` stays the LAST rung.** It fills only codes that are
  already in `values` AND in `unresolved`. It must never beat a spreadsheet
  column, a feed, a rule output or a contract component. It must never *add* a
  component to a run. Ledger §1.4.
* **`pay_period.py` stays stdlib-only** — no `odoo` import, so the bare
  `python3` battery keeps working. Anything that needs the ORM lives in the
  caller.
* **Nothing in `pay_period.py` raises.** It runs inside a payroll computation;
  a period it cannot read leaves the component exactly as it found it and lets
  the run finish.
* No date is exposed as an Excel serial. `YEAR` / `MONTH` / `DAY` / `DATE`
  appear in the parser's and validator's allowed-name lists
  (`formula_engine/parser.py:90`, `validator.py:55`) but are **not implemented
  in the evaluator or in `excel_semantics.py`** — verified. A date serial would
  be a value no formula could take apart. The run therefore answers
  **pre-decomposed numbers**.
* Do not touch the mapping board, the studio, or any JS outside
  `pb_import_wizard`. That is Phase C.
* No holiday calendar. Not this phase, possibly never — the owner ruled it out.

## 4. Architecture

### 4.1 B1 — the six codes

`pb_hr_payroll_formula/models/pay_period.py`, `PERIOD_CODES`:

| Code | Meaning | Value |
|---|---|---|
| `PAYMONTH` | month the period **ends** in (existing behaviour, unchanged) | 1–12 |
| `PAYYEAR` | year the period **ends** in | e.g. 2026.0 |
| `PAYDAYS` | calendar days in the period, **inclusive** of both ends | e.g. 31.0 |
| `STDDAYS` | standard working days for this run | see §4.2 |
| `STARTDAY` | day of month the period starts on | 1–31 |
| `ENDDAY` | day of month the period ends on | 1–31 |

All six are floats, matched on the component's **CODE**, upper-cased and
stripped — because that is what a formula names. Every code is underscore-free,
≤12 characters, ≥6 characters, and can never equal a column letter, which are
the settled converter floors (ledger §1.3). Substring overlap between codes is
safe — the converter matches greedily (MAPFIX, settled).

Keep the same end-date-wins rule the docstring already states: **a 26 Sep →
25 Oct run is the October run**, so `date_to` answers `PAYMONTH`, `PAYYEAR` and
`ENDDAY`; `date_from` answers `STARTDAY`; both answer `PAYDAYS`. `date_from`
alone is used only when there is no end date at all.

`STDDAYS` is deliberately a code that **already exists in the field** — it is a
spreadsheet column on the reference Vietnamese scheme. Because the period is
the last rung, that file keeps winning and nothing about that scheme changes.
Schemes where the component exists with no source gain the fallback they should
always have had. **That is the point of the phase, and it is also its main
risk — see §6.**

Signature change: `period_values(date_from=None, date_to=None, std_days=None)`
and `fill_period_inputs(values, unresolved, date_from=None, date_to=None,
std_days=None)`. Keep both callable with the old positional signature —
`payroll_import_batch.py:4628` and `hr_payslip_formula.py:812` both call
positionally today.

Add a stdlib helper in the same module:

```
def default_standard_work_days(date_from, date_to) -> float | None
```

— the count of Mon–Fri days between the two dates inclusive, `None` when either
date is missing. This is the ONE definition of the default; nothing else may
compute it.

### 4.2 B2 — where the number lives

Two stored fields, both Float, both `digits=(16, 2)` so a half-day is
expressible:

* **`hr.payslip.run.pb_std_work_days`** — the run's own answer. Extend the
  existing `pb_hr_payroll_formula/models/hr_payslip_run.py` (it already
  `_inherit`s `hr.payslip.run`).
* **`hr.payroll.import.batch.pb_std_work_days`** — what the load was told.
  Alongside `date_from` / `date_to` at `payroll_import_batch.py:167-168`.

Resolution order when a resolver needs the number:

1. the run's `pb_std_work_days`, if set and > 0;
2. else the batch's `pb_std_work_days`, if set and > 0;
3. else `default_standard_work_days(date_from, date_to)`.

Reading it in each resolver:

* **`models/hr_payslip_formula.py:812-816`** — the payslip has
  `payslip_run_id`; read the run's value, fall back to the default from
  `self.date_from` / `self.date_to`.
* **`models/payroll_import_batch.py:4628-4632`** — read `self.pb_std_work_days`,
  falling back to the default from `self.date_from` / `self.date_to`.

When the batch creates or attaches a run, copy the batch's value onto the run
so the two never disagree. Find the creation site (`payslip_run_id` is set by
the batch; `payroll_import_batch.py:1598-1599` already carries `date_start` /
`date_end` into a related create — check whether that is the same seam) and
carry the number the same way.

**Default on create, not a compute.** Make it an onchange/default that fills
the Mon–Fri count when the dates are known, and leave the stored value alone
afterwards — a stored compute would overwrite the user's holiday adjustment
the next time anything touched the dates. This is the whole point of the
feature.

Expose it on screen:

* The pay run form — a **Standard working days** field beside the period, with
  help text in plain words ("How many working days a full month is paid
  against. Lower it for a month with public holidays."). Find the existing
  `hr.payslip.run` form inherit in `pb_hr_payroll_formula/views/`.
* Changing it on the run should be followed by **Recompute**; the existing
  `action_recompute_formula_lines_batch` (`hr_payslip_run.py:24`) already does
  the work. Say so in the field's help rather than auto-recomputing — an
  automatic recompute of a whole run on a keystroke is not a thing to build.

### 4.3 B3 — the wizard

`pb_import_wizard`:

* **`models/pb_import_wizard.py:17-35` `_period_presets()`** — give every preset
  a `std_days`, computed with `pay_period.default_standard_work_days` from the
  preset's own dates. `custom` gets `''`. Import the helper; do not re-implement
  the Mon–Fri count (ledger §0, one definition).
* **`:142 create_and_load`** — accept `std_days` from `vals` and put it on the
  batch alongside `date_from` / `date_to` at `:153-156`. Guard the cast; an
  empty string must mean "use the default", not zero. **Zero is not the same as
  empty** — a run with zero standard days would divide by zero in a daily-rate
  formula. Refuse or ignore a non-positive value.
* **`static/src/js/import_wizard.js:37`** — add `std_days: ""` to the form
  state; `:83-87 applyPeriod` sets it from the preset; a manual change to
  `date_from` / `date_to` recomputes it **only while the user has not typed
  their own value** (track a `std_days_touched` flag — silently overwriting a
  holiday adjustment because somebody nudged a date is exactly the bug this
  feature exists to prevent).
* **`static/src/xml/import_wizard.xml:60-63`** — a third box in the `iw-row2`
  row, labelled **Standard working days**, `type="number"`, `min="0.5"`,
  `step="0.5"`, with a one-line hint underneath: *"Working days a full month is
  paid against. Drop it for a month with public holidays."* Match the existing
  `iw-in` styling exactly; three boxes must still lay out sanely at narrow
  widths.

### 4.4 B4 — provenance

Both call sites already write
`input_provenance.entry('period', key=code, via=pay_period.PERIOD_VIA)` for
every code returned by `fill_period_inputs`. Because the extension returns more
codes from the same function, this keeps working with no change — **verify it
rather than assume it**, and check the source chip on a payslip reads
**"Pay period"** (`_SOURCE_LABELS['period']`, ledger §1.4) for a component the
run filled.

## 5. Safety rails

* **Nothing may change on a scheme that already sources these codes.** Prove
  it, do not assert it.
* A period with no dates at all fills nothing and the run finishes.
* A `std_days` of zero or negative is treated as "not set" everywhere — form,
  wizard, resolvers.
* The stdlib battery (`tools/excel_semantics_battery.py` and friends) must
  still run under bare `python3` after the change. Run it.
* Do not write a migration that back-fills `pb_std_work_days` on historical
  runs. Old runs keep computing exactly what they computed.

## 6. The risk this phase carries, and how you must discharge it

Adding a code to `PERIOD_CODES` means any scheme that **has** a component with
that code and **no source for it** starts receiving a real number where it
previously received its default. That is the intended fix. It is also a live
pay change.

Before deploying anywhere, produce a **change report per database**
(`payobook`, `abm`, `acme`, `payobook_template`):

* which schemes have a component coded `PAYYEAR`, `PAYDAYS`, `STDDAYS`,
  `STARTDAY` or `ENDDAY`;
* for each, whether it currently resolves from a real source;
* for the ones that do not, recompute a sample of real payslips before and
  after and show the line-by-line difference.

**If any payslip's net pay moves, stop and report before deploying.** A number
moving may well be correct — it is the bug being fixed — but it is the owner's
call, not yours.

## 7. Numbered test cases

`pb_hr_payroll_formula/tests/`. Every test states its number in the docstring.

1. `period_values` for 1–31 Oct 2026 → `PAYMONTH` 10, `PAYYEAR` 2026,
   `PAYDAYS` 31, `STARTDAY` 1, `ENDDAY` 31.
2. Mid-cycle 26 Sep → 25 Oct 2026 → `PAYMONTH` **10**, `PAYYEAR` 2026,
   `PAYDAYS` 30, `STARTDAY` 26, `ENDDAY` 25.
3. `date_to` missing, `date_from` present → the start date answers; no crash.
4. Both dates missing → `{}`, and `fill_period_inputs` fills nothing.
5. `default_standard_work_days` for Oct 2026 (1–31) → 22.0. Assert against a
   hand-counted month, not against the function.
6. `default_standard_work_days` across a month boundary and for a single
   Saturday → correct, and `None` when a date is missing.
7. **The period never beats a source.** A component coded `STDDAYS` bound to a
   spreadsheet column keeps the column's value even when the run has a
   different one.
8. **The period never invents a component.** A scheme with no `PAYYEAR`
   component still has no `PAYYEAR` in its values after the fill.
9. `pb_std_work_days` on the run wins over the batch's, which wins over the
   default.
10. Zero and negative `pb_std_work_days` are treated as unset at every one of
    those three levels.
11. A user's edited value **survives** a later change to the run's dates (no
    stored compute clobbering it).
12. Provenance: a component the run filled reports `src='period'`,
    `via='pay_period'`, and the payslip's source chip reads "Pay period".
13. Wizard round trip: `create_and_load` with `std_days: 20` puts 20 on the
    batch; with `''` leaves it unset; with `0` leaves it unset.
14. `_period_presets()` returns a sane `std_days` for every preset, and
    `custom` returns empty.
15. `pay_period.py` still imports and runs under bare `python3` with no Odoo on
    the path.
16. **Pay-neutrality on real data** — §6's change report, with the before/after
    payslip diff. Report it whether it is empty or not.

Plus the existing `pb_hr_payroll_formula` and `pb_import_wizard` suites, with
counts.

## 8. Deploy and verify

Per ledger §0.5. Bump `pb_hr_payroll_formula` (currently `19.0.1.137.0`) and
`pb_import_wizard` (currently `19.0.1.3.0`). **Hold the deploy until §6's
change report is clean or the owner has ruled on it.** Assets changed in
`pb_import_wizard`, so after upgrading: delete `/web/assets/%` attachments per
database and restart. Never compile `web.assets_backend` in a shell — it
OOM-kills the box.

## 9. Browser validation (mandatory)

Chrome MCP on `payobook`:

* Open the guided pay-data load. Step 1 shows **Standard working days**
  pre-filled (22 for an ordinary month), the three boxes lay out cleanly at
  1440 and at 1024, and the hint reads in plain words.
* Change it to 20, pick a different period preset, confirm **your 20 survives**.
* Complete a load on a demo scheme and open a payslip: the component the run
  filled shows a **Pay period** source chip.
* Open a pay run form: the field is there, editable, with its help text.
* Console clean — read it.
* Shots into `docs/runsrc_pb_shots/`.

## 10. Commit

One feature-scoped commit, explicit file staging, reviewer-focused message. Do
**not** push. End the message with:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

## 11. Report back

1. Each of the 16 tests by number, PASS/FAIL, with evidence.
2. **§6's change report in full**, per database — this is the most important
   thing you return.
3. Screenshots of the wizard and of a "Pay period" source chip.
4. Per-database version table after deploy (or a clear statement that the
   deploy was held, and why).
5. New gotchas as **RS<n>** ready for `RUNSRC_LEDGER.md` §2.
6. Anything in this handover that turned out to be wrong.
7. For Phase C: the exact names of the seams a board lane would need to offer
   these six codes as a source — where a lane's items are built, and where a
   transformation rule takes its inputs from.
