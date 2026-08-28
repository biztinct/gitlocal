# VALUEKIND — Phase 4: the reports read the scheme, and you can edit what they read

**Programme:** VALUEKIND (`VK`) · **Phase:** 4 · **Date:** 2026-08-28
**Predecessors:** `VALUEKIND_P1_TYPE_CONTRACT.md`, `VALUEKIND_P23_CONTROL_AND_REPAIR.md`
**Ledger:** `docs/FORMULA_ENGINE_CONVENTIONS.md` C18.115-124. New entries from **125**.

---

## 0. The confusion this phase removes

The owner sees, on the Atlas grid, chips reading **Basic · Allowance · Gross ·
Deduction · Net · Company Contribution · Other**, and was told "every label says
allowance". Both are true, because they are two different fields on the same
record:

| | field | ABM's value | who reads it |
|---|---|---|---|
| what you SEE | `hr_salary_rule_category.name` | "Basic", "Net", "Deduction" — **correct** | the Atlas chips |
| what the Explorer reads | `hr_salary_rule_category.category_type` | `allowance` on **all seven** in use | `pb_explorer` |

```
id  code   name                    category_type   lines
1   BASIC  Basic                   allowance         304
3   GROSS  Gross                   allowance         152
4   DED    Deduction               allowance        1368
5   NET    Net                     allowance         152
6   COMP   Company Contribution    allowance         912
23  OTH    Other                   allowance        3952
13  BASIC  Basic Salary            basic               0   <- correct type, unused
15  DED    Deductions              deduction           0   <- correct type, unused
```

The name says "Net"; the hidden type field on the same row says "allowance". So
the Explorer adds Gross and Net and Deduction into "earnings" alongside the
components they are already made of, and reports ~14bn against a true 927m.

**This phase stops the reports reading `category_type` at all.** The scheme
already knows the answer and derives it from its own net-pay formula.

---

## 1. Verified plumbing — do NOT re-derive

### 1.1 `net_role` is already correct on ABM

`hr.formula.rule.net_role` ∈ `earning · deduction · net · employer_cost · info ·
mixed`, with `net_role_detail` ("already inside another component of the same
kind — count the total, not this line"), `net_role_confidence`
(`certain·likely·review`) and `net_role_reason`.

```
earning 47 · info 36 · deduction 9 · employer_cost 6 · net 1
NETPAY        net        certain  "This is the net pay component."
TOTALDEDUCTI  deduction  certain  "Subtracted straight from Net Pay."
EMPTRADEUNIO  deduction  certain  "…Already counted inside Total Deduction…"
```

### 1.2 It reconciles EXACTLY — measured on abm run 14

Classifying live payslip lines by `net_role` and excluding `net_role_detail`
roll-ups:

| net_role | lines | roll-ups | sum excluding roll-ups | run header |
|---|---|---|---|---|
| earning | 6840 | 6536 | **927,155,630** | gross 927,155,630 ✓ |
| deduction | 1368 | 1216 | **203,370,000** | deductions 203,370,000 ✓ |
| net | 152 | 0 | **723,785,630** | net 723,785,630 ✓ |
| employer_cost | 912 | **912** | *(nothing left)* | — |
| info | 2432 | 304 | 2,168,218,130 | must be EXCLUDED from money |

Three of four reconcile to the penny. **`employer_cost` is the exception and it
is a data gap, not a design flaw**: every one of ABM's six employer-cost
components — `TOTACOSTTOER` included, which IS the top-level total — is flagged
`net_role_detail`, so excluding roll-ups leaves nothing. That is what §3's
editable board and §4's review gate exist to let a person fix.

### 1.3 The line already carries half of what is needed

`hr_payslip_line` has `component_type` and `component_detail` (a copy of
`net_role_detail`, stamped at creation by both line creators). It does NOT carry
the role itself. `pb_payruns` computes the run header with
`AND (c.code = 'NET' OR pl.component_detail IS NOT TRUE)`
([`hr_payslip_run.py:181`](../../pb_payruns/models/hr_payslip_run.py#L181)) —
which is why the header is right while the Explorer is wrong.

### 1.4 Two line creators, again

`hr_payslip_formula._create_payslip_lines_from_formulas` AND
`payroll_import_batch._compute_and_create_payslip_lines`. Both already stamp
`component_detail`; both must stamp the role (C18.122).

### 1.5 The Explorer's measure vocabulary

`pb_explorer._MEASURES` is keyed on `category_type` values
(`net·basic·allowance·deduction·tax·social_security·employer_cost`), NOT on
`net_role`. A translation is required; do not rename either vocabulary.

| net_role | category_type |
|---|---|
| `earning` | `allowance` |
| `deduction` | `deduction` |
| `net` | `net` |
| `employer_cost` | `employer_cost` |
| `info` | *(excluded from every money measure)* |
| `mixed` | fall back to the category's own type |

`basic`, `tax` and `social_security` have no `net_role` equivalent, so a scheme
never produces them; the category fallback still can, and the Basic-salary and
Tax measures keep working for structure-based payroll.

---

## 2. Scope

### In

1. `hr_payslip_line.pay_role` — stamped by both creators, backfilled by migration.
2. `pb_explorer` classifies by `pay_role` (translated) and falls back to
   `category_type`; roll-ups excluded from money measures; `info` excluded.
3. The **Component setup** board (an extension of Field types): edit Group,
   Pay role, Subtotal?, and Value type per component.
4. A review gate: a component the classifier is not sure about must be answered
   by a person before the scheme is used.
5. Payslip generation rules (§5) — owner's ruling of 2026-08-28.

### Binding non-goals

- **Do not change `net_role`'s classifier.** This phase READS it and lets a
  person override it. Re-deriving it is NETROLE's job.
- **Do not touch `pb_payruns`' run-header maths.** It is correct today; two
  writers of one total is how they drift.
- **Do not rename `category_type` or `net_role`.** Translate between them.
- **Do not recompute any payslip** as a side effect. The board saves; a person
  presses Recompute.
- No user-visible string may contain "Odoo".

---

## 3. The Component setup board

The owner asked for drag-and-drop between the grid's category chips. **Recommend
against, and say why:** the grid is a horizontally-scrolled 152 × 95 matrix, the
chips are filters rather than containers, and dragging one of 95 column headers
onto a chip is slow, imprecise, and unusable by keyboard. For 95 components a
dense editable list is faster to use and easier to review before saving.

So: the Field types tab becomes **Component setup**, one row per component, with
four editable columns and one batched Save:

| column | field | why it is here |
|---|---|---|
| Group | `component_type` (falls back to category name) | what the owner sees as "category" — the chips |
| Pay role | `net_role` | what every report counts it as |
| Subtotal? | `net_role_detail` | "this is already inside another total" — the double-count guard, and ABM's employer-cost fix |
| Value type | `value_kind` | P2, unchanged |

Show the classifier's reason and confidence per row; flag `review` rows. Saving
a pay role sets `net_role_confidence='certain'` and records the person, exactly
as `value_kind_source='user'` does — an answer a person gave is never re-derived.

Writes go to `hr.formula.config`, never to the read-only `pb.source.atlas`.

---

## 4. The review gate

Owner's ruling: *"enforce in the wizard when the classifier is unsure — ask the
user."*

`hr.formula.config.unreviewed_components()` returns components with
`net_role_confidence = 'review'` or no `net_role` at all. Surface it as a
blocking step in the pay-run wizard's existing Pay-data step, with a link to the
board. **Do not block on `likely`** — only on genuinely unsure, or the gate
becomes noise people click through.

---

## 5. Who gets a payslip (owner's ruling, 2026-08-28)

> *"compute only for the employees which are active irrespective of the actual
> work hour. So even if they don't work or the work hours are zero, they still
> get a payroll created. Anything which is not active but has actual work hours
> not zero, then you have to display or compute that payslip as well."*

So the rule is a union, not a filter on hours:

```
include IF employee is active
     OR (employee is not active AND actual worked hours <> 0)
```

An inactive employee with zero hours is excluded — that is the only exclusion.
"Active" is the employment status the run resolves for that period, not
`hr.employee.active` alone; on ABM it arrives as `EMPSTATUS` (`Active` /
`Resigned`). Report the counts on both sides before changing behaviour.

**The divide-by-zero stays as it is.** Owner's ruling: no attendance means no
earnings, and 0 is the right answer. This phase does not touch it.

---

## 6. Test cases

1. Both line creators stamp `pay_role`; a line created by either carries it.
2. Migration backfills existing lines; a re-run is a no-op.
3. Explorer `gross` on abm run 14 = 927,155,630 (was ~14bn).
4. Explorer `deductions` = 203,370,000. `net` = 723,785,630.
5. `info` components contribute to NO money measure.
6. A roll-up (`component_detail`) is excluded from money measures but still
   visible in the `component` measure, so drill-down keeps working.
7. A structure-based payslip with no scheme still classifies by `category_type`.
8. Board: setting Pay role writes it, marks it `certain` + names the person, and
   survives re-classification.
9. Board: setting Subtotal? on ABM's `TOTACOSTTOER` to false makes
   Explorer `employer_cost` = 1,170,285,630.
10. `unreviewed_components()` lists only `review`/unset, never `likely`.
11. Generation: an active employee with 0 hours gets a payslip.
12. Generation: an inactive employee with hours ≠ 0 gets a payslip.
13. Generation: an inactive employee with 0 hours does not.
14. Run-header totals (`pb_payruns`) are byte-identical throughout.

---

## 7. Report back

1. Pass/fail per case.
2. Explorer measures on abm before and after, against the run header.
3. Payslip counts under the new generation rule versus today, with the
   employees added and removed.
4. New gotchas as C18 entries from 125.
