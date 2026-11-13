# RUNSRC Phase D — the run's numbers in Transformations, and the Vietnamese

**Read `docs/handovers/RUNSRC_LEDGER.md` first** — §0 binding rules, §1
inherited facts, and §2 gotchas **RS1–RS19**. RS13, RS14, RS16 and RS17 were
written by Phase C about exactly the surfaces you are touching. Do not
re-derive anything in there.

Phases A, B and C are merged, deployed and live on all six databases. Their
handovers are `RUNSRC_PA_ONE_CARD_PER_COLUMN.md`,
`RUNSRC_PB_THE_RUN_ANSWERS.md`, `RUNSRC_PC_FROM_THIS_PAY_RUN.md`.

This is the **last phase of the programme**. It closes the remaining half of
the owner's original request:

> "use these payrun wizard fields in transformation for something which payroll
> might require."

---

## 1. Scope

**D1 — the run's six numbers are available to a transformation rule**, in both
lanes a rule can be written in.

**D2 — one worked example, shipped and usable.** The owner asked for
"something payroll might require", not a capability note. See §5.

**D3 — the contract drawer learns the kind.** Phase C's parting finding.

**D4 — Vietnamese, and the polish pass.** Everything Phases B, C and D added.

## 2. Binding non-goals

* **Do not change `pay_period.py`'s API** — `PERIOD_CODES`, `period_values`,
  `default_standard_work_days`, `fill_period_inputs`. Three phases now depend
  on them and the bare-`python3` battery imports the module.
* **Do not touch `_raw_data_from_row`** (ledger §1.1).
* **Do not widen `DATE_COMPARE_TO`.** See the ruling in §4.2.
* **Do not change the resolver order.** The run stays last (Phase C §5).
* No migration; nothing written to an existing record on upgrade.

## 3. Where the seams are — verified, do not re-derive

Phase C's report §8 established these and I have re-checked each one:

* **The Python lane's namespace is assembled in exactly one place**:
  `pb_hr_payroll_formula/models/api_transformation_rule.py`, `_execute_python`,
  the `local_vars` dict at **`:1058-1072`**. `period_start` and `period_end`
  are already there at `:1064-1065`, taken from `main_record.period_from` /
  `.period_to` with a today-based fallback.
* **`main_record` is an `hr.api.data.store` row**, not a batch —
  `api_data_store.py:88-89` gives it `period_from` / `period_to`, and it has an
  `employee_id`. **It has no `pb_std_work_days`.** That is the whole of §4.1.
* **The guided lane** is `builder_mode` (`:431`, vocabulary at `:83`), executed
  by `_execute_builder` (`:962`) → `_builder_expand` (`:726`) → `_builder_run`
  (`:822`). Value steps and filter conditions are its vocabulary
  (`:940` lists the stored fields). There is a template twin of the model at
  `:1152-1190` — **anything you add to the rule, check whether the template
  needs it too.** Phase C found the same doubling in the JS (RS13).
* **The contract drawer**: `pb_contracts/models/pb_contract_360.py:331`
  `_cd_winning_bucket` maps a kind to one of five buckets via `_FILLS`.
  `rank.index('pay_run')` now succeeds (Phase C put it in the rank), so the
  guard at `:338` passes and the lookup lands on a bucket that does not exist
  for it.

## 4. The two decisions — settled, build to these

### 4.1 Where `std_days` comes from on this path — RULING

Phase C named the risk precisely: *"a transformation reading a different
standard-working-days number from the payslip beside it would be the worst
outcome."* Agreed, and that outcome is forbidden.

**The rule is: the same number the payslip uses, or an honest default, and the
user is always told which.**

1. Resolve the pay run or pay-data load behind this period when there is one,
   and take its `pb_std_work_days`. The resolution order Phase B built is
   run → load → default; reuse `_pb_standard_work_days()` rather than writing a
   second lookup. `api_data_store.py:303-306` already matches a period by
   `period_from` / `period_to` and is the precedent for finding it.
2. When nothing is found, fall back to `default_standard_work_days()` — the
   same Mon–Fri count everything else in the programme uses.
3. **Never** invent a number, and never let a zero through (Phase B's rail:
   zero divides by zero in every daily-rate formula in the product).

And the part that makes this safe rather than merely correct: **the rule
tester must show the number it used and where it came from** — "22 working
days (the Monday-to-Friday count of this period)" versus "20 working days (set
on the pay run)". A person writing a pro-rata rule must be able to see which,
without reading code. If the tester has no room for a line like that, put it in
the trace that `_builder_run` already takes (`:822`, `trace=None`).

### 4.2 The guided lane — RULING

**Do not widen `DATE_COMPARE_TO`** (`:49-50`, field at `:386`). It answers
"compare this date against what?" and its two period entries are *dates*. The
six run values are **numbers**. Putting `stddays` in a date Selection would be
a type lie, and the guided lane is where the least technical users work — it is
the worst place to put one.

Instead the six must be available **wherever the guided lane already takes a
number**: as a value step's operand, and in a filter condition's comparison
value. Find where that vocabulary is built (start at `:940`'s field list and
`_builder_run` at `:822`) and add them there, named and labelled in plain
English — "Standard working days", not `STDDAYS`.

If it turns out the guided lane genuinely has no numeric-operand vocabulary to
extend — that its operands are only ever fields of the source record — then
say so in the report and ship D1 for the Python lane only, with the guided lane
written up as a costed follow-up. **Do not invent a half-lane to satisfy the
spec.** That judgement is yours to make on the code; state which you found.

### 4.3 Naming

Lower-case, snake_case, matching the namespace they join: `paymonth`,
`payyear`, `paydays`, `stddays`, `startday`, `endday`, beside the existing
`period_start` / `period_end`. One import of `pay_period`, one `update()`, no
retyped constants — the Selection Phase C built is the precedent (it is
generated from `PERIOD_CODES`, not retyped).

## 5. D2 — the worked example

Ship **one** real, usable rule, not a docstring.

**The example: an unpaid-leave deduction.** It is the thing standard working
days exists for, every payroll in the region needs it, and it cannot be written
at all without this phase:

```
unpaid leave deduction = monthly salary ÷ standard working days × unpaid days
```

Requirements:

* It must be written in the **guided lane** if §4.2 finds one, so the owner can
  open it and read it as a sentence. Python lane only if guided is genuinely
  unavailable.
* It must run against real data on `rize` and produce a number you can check by
  hand, and the report must show that arithmetic.
* Put it where a user would find it, not in a test file. If there is a starter
  or demo rule set for the Vietnamese scheme, it belongs there.
* Its help text is the place to state which standard-working-days number it
  read (§4.1) — in plain English, no code names, and **never the word "Odoo"**.

## 6. D3 — the contract drawer

`_cd_winning_bucket` (`pb_contract_360.py:331`) must give `'pay_run'` a bucket.
Read `_FILLS` and the five buckets before choosing; the drawer's vocabulary is
contract-centric and the honest answer may be a sixth bucket rather than
squeezing it into one of the five. A component whose only source is the pay run
currently reads as having no source at all, which is the same class of lie
RS6/RS13 were about.

Check for other consumers of the full rank while you are there — RS16 says the
studio needed an explicit append. `grep` for `_config_kind_rank` and
`declared_sources` across all modules and report what you find, even if you fix
nothing.

## 7. D4 — Vietnamese and polish

* **Every user-visible string Phases B, C and D added needs `vi_VN` entries** —
  the six value labels, the lane header, the standard-working-days field and
  its note, the wizard box, the chip label "Pay period", and anything D adds.
  `pb_hr_payroll_formula/i18n/vi_VN.po`,
  `pb_formula_studio/i18n/vi_VN.po`, `pb_import_wizard/i18n/vi_VN.po`.
* **Follow the PO rules or the upgrade crashes**: there is a standing memo in
  this repo on the three things a PO entry needs, the `.pot`-is-merged trap,
  and the parse gate to run before any deploy. Find it and run the gate.
* **A translation fix is TWO fixes** (LOOK L24): the `.po` entry *and* the
  value already stored in every database. Check whether any of these strings
  are stored values.
* Read every string added by this programme once more against the white-label
  rule. Phases B and C both passed; D must not be the one that slips.

## 8. Tests — numbered

1. The six numbers are in the Python namespace, correctly valued for a period.
2. `stddays` equals the run's hand-typed number when a run exists.
3. `stddays` falls back to the Mon–Fri count when no run exists.
4. `stddays` is never zero and never negative, whatever is stored.
5. A transformation reading `stddays` agrees with the payslip beside it for the
   same period — the §4.1 forbidden outcome, asserted.
6. The tester/trace states which number was used and where it came from.
7. The guided lane offers the six as numeric operands (or the report explains
   why there is no such vocabulary — §4.2).
8. The unpaid-leave rule computes correctly on real `rize` data, checked by
   hand in the report.
9. The rule survives a period with no dates, and a period running backwards,
   without raising.
10. `_cd_winning_bucket` gives `pay_run` a bucket; a component sourced only by
    the run no longer reads as sourceless.
11. Template twin parity — anything added to the rule model exists on the
    template model too, or the report says why not.
12. Pay-neutrality: real payslips before and after, byte-identical. No existing
    transformation changes its output.
13. Every new string has a `vi_VN` entry, and the PO parse gate passes on all
    three modules.
14. No user-visible string added by this programme contains "Odoo" — grep the
    three modules' new strings and the three `.po` files.

Run the full suites for `pb_hr_payroll_formula`, `pb_formula_studio`,
`pb_contracts`. **Baseline them first** — RS19: `rztest` has ten failures that
are its data, not the code. Report the delta, not the count.

## 9. Deploy, validate, commit

Per ledger §0.5. Six databases: `payobook`, `abm`, `payobook_template`,
`rize`, `rztest`, `p9clone`. Bump every manifest you touch. **Never `--delete`
into the addons directory itself. Never compile `web.assets_backend` in a
shell.** Purge `/web/assets/%` per database and restart after any JS/SCSS.

Browser validation on **`rize.payobook.com`** (ledger RS3 — the Vietnamese
scheme is on that tenant, not payobook): open the unpaid-leave rule, run it,
read the console, take the shots into `docs/runsrc_pd_shots/`. Switch the
interface to Vietnamese and shoot the translated screens too — D4 is not done
until somebody has looked at it in Vietnamese.

Leave `rize` exactly as you found it. Confirm payobook.com and
rize.payobook.com both answer 200 before you finish.

One feature-scoped commit, explicit file staging, **do not push**, ending:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

## 10. Report back

1. The 14 tests by number, PASS/FAIL, with evidence.
2. **Which way §4.2 went** — did the guided lane have a numeric vocabulary to
   extend, or not? This decides how much of the owner's request actually
   shipped, so be explicit.
3. The unpaid-leave example: the rule, the real data it ran on, and the
   arithmetic checked by hand.
4. What `_FILLS` bucket you gave the pay run, and why.
5. Everything else that reads the full rank and did not know the kind (§6).
6. Per-database version table; confirmation both sites answer 200.
7. Screenshots, including Vietnamese.
8. New gotchas as **RS20+** (RS1–RS19 taken), appended to the ledger yourself.
9. Anything in this handover that turned out to be wrong.
10. **Whatever is left.** This is the programme's last phase; anything you did
    not finish, or found and did not fix, has no later phase to catch it. List
    it plainly so it can go in the closeout.
