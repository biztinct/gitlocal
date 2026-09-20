# VALUEKIND — Phases 2 & 3: you choose the type, then the run is repaired

**Programme:** VALUEKIND (`VK`) · **Phases:** 2 and 3 of 3 · **Date:** 2026-08-28
**Predecessor:** `VALUEKIND_P1_TYPE_CONTRACT.md` (shipped, commit `0ede31d9`)
**Ledger:** `docs/FORMULA_ENGINE_CONVENTIONS.md` C18.115-121 — binding.
New gotchas continue at **122**.

---

## 0. Where P1 left it

`hr.formula.rule.value_kind` exists, is auto-classified, is honoured by the wire,
the resolver and the Atlas display, and is correct on all four databases. What it
does NOT yet have is a way for a person to disagree with it, and it has not been
applied to any payslip that already exists.

Owner instructions of 2026-08-28, verbatim in substance:

1. *"an ability to decide whether the field should be considered as text, float,
   integer, currency/amount etc"* — with the audit as the surface to do it on.
2. *"This would be for both Excel and API and anything else which you can
   recommend."*
3. Fix ABM's `"HCM"` literal (ruling of 2026-08-27).
4. Explain the deleted-payrun / still-zero behaviour (answered in §1.3; the fix
   is P3).

---

## 1. Verified plumbing — do NOT re-derive

### 1.1 `appears_on_payslip` is a line-CREATION flag, not a print flag

`_create_payslip_lines_from_formulas`
([`hr_payslip_formula.py:518-522`](../../pb_hr_payroll_formula/models/hr_payslip_formula.py#L518-L522)):

```python
for rule in rules:
    if not rule.appears_on_payslip:
        continue
    amount = computed_values.get(rule.code, 0.0)
```

So the flag decides whether an `hr.payslip.line` ROW EXISTS. Everything
downstream aggregates those rows: `pb_total_*` on the run, `pb.fact.*` in the
Explorer, the payroll report, GL. Measured on abm run 14:

| code | lines | sum(total) |
|---|---|---|
| EMPBANKACCOA | 152 | 1,084,804,462,467,690 |
| INSBOOKNO | 152 | 759,131,862,427 |
| BASESALARY | 152 | 1,900,000,000 |

`pb_payslip` ("Payobook Payslip Statement") is presentation only. A payslip line
carries a Float `total`; an identifier has no total, so a non-numeric component
must never become one.

### 1.2 Deleting a pay run orphans its payslips

`hr_payslip.payslip_run_id` FK is `ON DELETE SET NULL`
(`pg_constraint.confdeltype = 'n'`), declared at
[`om_hr_payroll/models/hr_payslip.py:85`](../../om_hr_payroll/models/hr_payslip.py#L85),
and `hr.payslip.run` has **no `unlink` override**. Deleting a run therefore
leaves every payslip behind with a null run.

Live evidence: abm run 13 was deleted and run 14 created; the 152 payslips
(ids 1133-1284) still carry `create_date = 2026-08-26 15:17:08` — the import
batch's own timestamp — and were re-parented to run 14 at 21:00 on 08-27.

### 1.3 Which is why a "new" run still stored 0.0

Only a recompute rewrites `formula_input_values`. Re-parenting does not. The
classification and the wire types landed correctly on abm on 2026-08-27:

```
LOCATION      text        "a formula compares it against text, never counts it"
DATEOFJOININ  date        "every value seen is a date"
EMPSTATUS     text        EMPLOYEECODE identifier   EMPBANKACCOA identifier
LocationName  -> string   Dateofjoining -> date     EmployeeID -> string
```

The stored blob is simply older than the fix.

### 1.4 The type lives on the COMPONENT, which is what makes "Excel and API" one job

`transform_value` already reads `self.target_rule_id.value_kind`
([`integration_field_mapping.py:389-...`](../../pb_hr_payroll_formula/models/integration_field_mapping.py#L389)),
and `normalize_input_value` already reads `rule.value_kind`
([`payroll_import_batch.py:3761`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3761)).
The first is the API path, the second is the Excel/header path. One field
governs both, so the control surface is per-component and source-agnostic by
construction. **Do not add a per-wire type control** — that is the thing that
drifted in the first place.

### 1.5 Read-only doctrine

`pb.source.atlas` has no create/write/unlink and `test_07` counts rows around
every endpoint. That stays true: the new board READS through `pb.source.atlas`
and WRITES through `hr.formula.config.set_value_kinds()`, a different model with
its own ACL. State this in the module docstring; do not add a writer to the
atlas model.

---

## 2. Phase 2 — the control surface

### 2.1 Vocabulary

Extend `value_kind` to cover the owner's words. Final list, and what each does:

| key | label | coerced? | display |
|---|---|---|---|
| `money` | Amount (currency) | yes | grouped, currency decimals + symbol |
| `decimal` | Decimal number | yes | grouped, up to 2 dp, no symbol |
| `integer` | Whole number | yes, rounded | grouped, 0 dp |
| `quantity` | Quantity (hours, days) | yes | grouped, up to 2 dp, no symbol |
| `rate` | Percentage / rate | yes | as a rate |
| `identifier` | Reference code | **no** | verbatim, leading zeros kept |
| `text` | Text | **no** | verbatim |
| `date` | Date | **no** | the reader's date format |
| `boolean` | Yes / No | **no** | verbatim |

`decimal` and `quantity` differ only downstream: `quantity` is excluded from
money totals in the Explorer (`_MONEY_ROLES`), `decimal` is a plain number. Keep
both; label them so the difference is visible.

`NUMERIC_KINDS` becomes `{money, decimal, integer, quantity, rate}`. **This set
is the single definition of "may meet float()"** — test 14 of P1 asserts it, and
that assertion must be updated, not deleted.

`integer` additionally rounds: `round(value)` after coercion, so a whole-number
field never shows `2.0000001`.

### 2.2 Server API (in `pb_hr_payroll_formula`)

On `hr.formula.config`:

* `value_kind_board(run_id=None)` — one payload for the whole board:
  per component `{code, name, band, kind, kind_source, kind_reason, suggested,
  lane, source_key, delivered_examples, stored_examples, drift, appears_on_payslip}`.
  `lane` says where the value comes from — reuse the Atlas lane vocabulary
  (`feed`, `excel`, `employee_field`, `contract_component`, `constant`,
  `calculated`) so the board and the Atlas agree.
* `set_value_kinds(updates)` — `updates` is `{code: kind}`. Validates the kind
  against the selection, writes `value_kind` + `value_kind_source='user'` +
  a reason naming the person, and returns the rows changed. Gate on the same
  officer ladder the Atlas uses.
* `reset_value_kind(codes)` — back to `auto`, then re-classify those rows only.

### 2.3 UI

A third tab in the Source Atlas cockpit — **Lanes · Grid · Field types** — since
that is where the owner saw the problem.

* One row per component: name + code, a lane chip, what the source delivered
  (up to 3 examples), and a `<select>` of the nine kinds.
* A row whose stored payslip values contradict the source is flagged — this is
  P1's `drift` list, and it is the finding that matters.
* A row the auto-classifier and the person disagree on shows both, with the
  classifier's reason as a tooltip.
* Changing a select marks the row dirty; one **Save types** button writes them
  all through `set_value_kinds`. Never write per keystroke.
* A "Reset to automatic" per row.
* After a save, the board reloads and offers a recompute of the current run —
  it does NOT recompute silently. Nothing on this screen may change a number
  without the person pressing the button that says so.

Do NOT put the type on the payslip; this board is a Settings-grade surface.

### 2.4 The `appears_on_payslip` rail

`_create_payslip_lines_from_formulas` gains one guard: a component whose
`value_kind` is not in `NUMERIC_KINDS` does not produce a payslip line, whatever
`appears_on_payslip` says. Log the codes skipped, once per run.

This is a BEHAVIOUR CHANGE and it removes lines. It is correct — a payslip line
holds a Float `total` and a bank account has no total — but it must appear in
P3's diff, not slip in unannounced.

---

## 3. Phase 3 — repair ABM

Strictly ordered. Do not reorder; each step's output is the next step's input.

1. **Snapshot** run 14: per payslip, `formula_input_values`,
   `formula_computed_values`, every line `(code, total)`, and the run's
   `pb_total_gross / pb_total_deductions / pb_total_net / pb_employee_count`.
   Write it to a file on the server; it is the only way back.
2. **Fix the literal.** `EMPTRADEUNIO`'s `"HCM"` → `"Ho Chi Minh Branch"`, the
   feed's actual vocabulary (`LocationName`: `Ho Chi Minh Branch` ×86,
   `La Nga` ×62, empty ×4). Owner-approved 2026-08-27. Do not touch the
   `"La Nga"` literal — it already matches.
3. **Recompute** run 14 through the normal path (`Recompute Formulas`), so the
   repair is the product's own behaviour and not a script.
4. **Diff** against the snapshot: which components changed, on how many
   payslips, and the run totals before and after. Report it BEFORE anything is
   approved; the run stays `draft`.

### Expected, and to be checked rather than assumed

* `LOCATION` / `EMPSTATUS` become text; `DATEOFJOININ` becomes a date string.
* `EMPBANKACCOA` / `INSBOOKNO` keep their leading zeros and STOP being payslip
  lines — this alone removes ~1,084T of nonsense from every line-based total.
* `EMPTRADEUNIO` starts producing 45,000 for the Ho Chi Minh employees who also
  satisfy `SHUIPARTICIP="YES"` and `$BS5>0`. **This is real money and it is the
  one number the owner must sign off.** Report the exact headcount and total.
* `ACTUALMEAL`'s `IF(F5="La Nga",0,…)` branch becomes reachable for 62 people.
  It computed 0 for everyone before for an unrelated reason
  (`ACTUWORKHOUR`/`STANWORKHOUR` are 0.0), so expect no change — and if a number
  DOES move there, stop and report rather than proceeding.
* `pb_total_gross / net` are expected to change only via `EMPTRADEUNIO`. Any
  other movement is a finding, not a success.

---

## 4. Safety rails

1. **Nothing recomputes without an explicit press.** Not the classifier, not the
   board's save, not a migration.
2. **The snapshot exists before step 2.** No snapshot, no repair.
3. `pb.source.atlas` gains no writer. `test_07` stays green.
4. A person's `value_kind_source='user'` is never overwritten, including by the
   re-classify path — only `reset_value_kind` clears it, and only on request.
5. The run stays `draft` throughout. Do not confirm, do not post.
6. `NUMERIC_KINDS` is the one definition of coercion. Adding `text`,
   `identifier`, `date` or `boolean` to it restores the original defect.
7. Bump manifest versions on any asset change (C2). Deploy with
   `rsync -az --perms --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r` and verify
   `find <addons>/<module> ! -perm -o+r | wc -l` is 0 (C18.121).
8. Upgrade all four databases.

---

## 5. Test cases

**Vocabulary**
1. `NUMERIC_KINDS == {money, decimal, integer, quantity, rate}`; the four
   non-numeric kinds are absent.
2. `integer` coerces AND rounds: `'12.7'` → `13`.
3. `decimal` coerces without rounding: `'12.7'` → `12.7`.
4. An existing `money`/`quantity` component is unchanged by the vocabulary
   extension (no reclassification churn).

**Board**
5. `value_kind_board()` returns one row per component with a lane and a kind.
6. `set_value_kinds({'LOCATION': 'text'})` writes `value_kind_source='user'`.
7. A subsequent `classify_value_kinds()` leaves it alone.
8. `reset_value_kind(['LOCATION'])` returns it to `auto` and re-derives it.
9. `set_value_kinds` refuses a kind outside the selection.
10. `set_value_kinds` refuses a user below the officer ladder.
11. `pb.source.atlas` still has no create/write/unlink (P1 test 07).

**The payslip-line rail**
12. A `text` component with `appears_on_payslip=True` produces NO payslip line.
13. A `money` component with `appears_on_payslip=True` still produces one.
14. Turning a component from `money` to `text` and recomputing removes its line
    and reduces the line-sum by exactly that component's old total.

**Repair (live, abm)**
15. Snapshot written and readable before any change.
16. After recompute: `LOCATION` holds `'Ho Chi Minh Branch'` / `'La Nga'`, not 0.
17. After recompute: `EMPBANKACCOA` keeps its leading zeros as a string.
18. `EMPBANKACCOA` and `INSBOOKNO` have no payslip lines.
19. `EMPTRADEUNIO` = 45,000 for exactly the employees meeting all three
    conditions; report the count and the total.
20. Every run total, before and after, with every difference attributed to a
    named component.

---

## 6. Report back

1. Pass/fail per numbered case.
2. The full before/after run-total table with each delta attributed.
3. `EMPTRADEUNIO`: headcount and money it now applies to.
4. Any component whose value moved that §3 did not predict.
5. New gotchas as C18 entries from 122.
6. Anything done that this document did not authorise, and why.
