# JOURNEY — Phase J10: the record is a source too, and the writeback obeys the order

**Status:** handed to Opus 2026-08-26
**Reads first:** `docs/handovers/JOURNEY_PHASE_J9_HANDOVER.md` (the architecture this extends) and
`docs/handovers/JOURNEY_LEDGER.md` (MJ1–MJ47, inheriting the MF and CR ledgers).
**Predecessor:** J9 (commit `fd2b3c58`, `pb_hr_payroll_formula` 19.0.1.82.0 + `pb_formula_studio`
19.0.1.158.0, live on **abm · payobook · payobook_template**; **acme is redundant — never deploy
there**).

---

## 0. The owner's two requests, verbatim

> **(a)** Yes writeback should also follow the same priority.

> **(b)** A payslip schema component can be mapped only to an Employee/Contract field or a contract
> component. So when you are showing the source … you would need to show CONTRACT RECORD or EMPLOYEE
> RECORD or CONTRACT COMPONENT. For eg Designation is only showing CONNECTED SYSTEM but it is also
> mapped to Contract record field — that information is not showing up here, it should have shown
> CONNECTED SYSTEM **and also** CONTRACT RECORD … just like you are showing for Gas Allowance you
> are showing SPREADSHEET and also CONTRACT COMPONENT with order of priority. I want you to treat
> CONTRACT RECORD and EMPLOYEE RECORD in the same way as you are showing CONTRACT COMPONENT. So if a
> payroll component has second or third source as EMPLOYEE or CONTRACT RECORD you need to show that
> as well. **Currently you are showing EMPLOYEE RECORD or CONTRACT RECORD only if that is the only
> source.**

The owner's last sentence is a precise bug report. It is correct, and §2.1 is the line that causes
it.

Note what request (b) also settles: the owner **confirms** that a component's record destination is
either a field or a component, never both. So MAPFIX B2's demotion (wiring to a native field demotes
a contract component) is **correct and stays**. Do not change it. It is not this phase's subject.

---

## 1. Scope and non-goals

### In scope

1. `employee_field` splits into **`employee_field`** and **`contract_field`**, and `bank_account`
   becomes a source kind of its own. All three join the ranked list **at rank 4** — after
   spreadsheet, before the contract component — instead of only appearing when nothing else does.
2. The three writebacks that populate employee, contract and bank records stop re-reading the
   primary payload by name and take **the value the declared-source order picked**.
3. One shared function decides that order for both the resolver and the writeback.

### Non-goals

- **No ladder reorder** (J-D5). Rank 4 is where the record read already sits — see §2.2.
- **Do not touch the MAPFIX B2 demotion.** The owner has just confirmed the rule it enforces.
- **Do not change the emptiness test.** `_feed_value_is_empty` stands: `None` or whitespace-only is
  nothing; **`0` and `False` are real values** (MJ15).
- **Do not run `action_process` on a live database.** This phase changes code that writes into
  employee, contract and bank records, which makes that rail more important than in any prior phase,
  not less. No live external API pulls.
- **Do not add a fourth writeback, a new board, or a new lane.**
- **acme is out of scope.** Deploy to abm (validate there) then batch `payobook` and
  `payobook_template`.

---

## 2. Verified facts — do not re-derive

Checked against the code and the live `abm` database on 2026-08-26.

### 2.1 The defect, exactly

[`pb_formula_studio.py:612-619`](../../pb_formula_studio/models/pb_formula_studio.py#L612):

```python
        if rule.is_contract_component:
            out.append({'kind': 'contract_component', 'key': '', 'wirable': False})
        if out:
            return out
        if rule.id in emp_dest_rule_ids:
            return [{'kind': 'employee_field', 'key': '', 'wirable': False}]
        return [{'kind': 'none', 'key': '', 'wirable': True}]
```

`if out: return out` is the bug. The record tier is reachable **only when the list is otherwise
empty**. Note the contrast two lines above: the contract component is *appended* unconditionally,
which is exactly the treatment the owner is asking for here.

`_source_employee_dest_ids`
([`:287-303`](../../pb_formula_studio/models/pb_formula_studio.py#L287)) returns a bare
`set()` of rule ids, so the kind and the field name are not even available to render. It must return
a dict.

### 2.2 Rank 4 is where the record read already is

The resolver's tail, [`payroll_import_batch.py:3460-3480`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3460):
after the raw/bound branches fail, `get_mapped_input_value(rule)`
([`:3068`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3068)) reads the mapped
employee/contract field, and **only if that is empty** does `contract_component_amounts` get a look,
then the default. So:

```
feed  >  rule  >  excel  >  employee_field / contract_field / bank_account  >  contract_component  >  default
```

The owner's stated 1-2-3 (API, Excel, contract component) is preserved intact; the record field
slots in above the component, which is where the code has always put it. **`_source_rank()` gains
three members and nothing moves.**

`employee_field`, `contract_field` and `bank_account` are **one rung**, not three — a component has
at most one `hr.payslip.import.mapping` row, so they never compete. They are three labels for one
tier, chosen by what the row points at.

### 2.3 Which model, and how to tell

`hr.payslip.import.mapping` columns: `component_id`, `destination_type` (`field` | `bank_account`),
`target_model_id` → `ir_model`, `target_field_id` → `ir_model_fields`, `bank_role`.

- `destination_type == 'bank_account'` → kind `bank_account`, key = `bank_role`.
- `destination_type == 'field'` and `ir_model.model == 'hr.contract'` → kind `contract_field`.
- `destination_type == 'field'` and `ir_model.model == 'hr.employee'` → kind `employee_field`.
- key = the field's technical name (`job_id`, `basic_salary`, …). Render the **field's label**, not
  the technical name, in the chip's tooltip; the key is what the fold compares.

### 2.4 abm today — 21 mappings, and **10 cards are hiding one**

18 `field` + 3 `bank_account`. Split by model: **8 on `hr.contract`** (BASESALARY/`basic_salary`,
DEPARTMENT/`department_id`, DESIGNATION/`job_id`, EMPSTATUS/`hirestatus`, LASTWORKIDAY/`date_end`,
PITNUMBER/`tax_identification_number`, SHUIPARTICIP/`shuipart`, TUPARTICIPAT/`tupart`) and **10 on
`hr.employee`**.

**Ten of the 21 sit on a rule that already declares a source, so today they render nothing:**

| component | declared today | hidden record destination |
|---|---|---|
| DESIGNATION | feed `Designation` | contract `job_id` |
| EMPLOYEENAME | feed `Name` | employee `name` |
| EMPLOYMETYPE | feed `Employee_type` | employee `org_employee_type` |
| FULLNAMEVN | feed `Full_Name_Vietnamese` | employee `full_name_vn` |
| INSBOOKNO | feed `Insurance_Book_Number` | employee `insurance_code` |
| PITNUMBER | feed `PIT_Number` | contract `tax_identification_number` |
| WORKEMAIL | feed `EmailID` | employee `work_email` |
| BANKNAME | feed `Bank_Name` | bank account (role) |
| LASTWORKIDAY | excel `SEVL\|Last Working Day` | contract `date_end` |
| RESIDENCSTAT | excel `SEVL\|Residency Status` | employee `vn_residency_status` |

**Expected outcome:** abm goes from **1** card with ≥2 chips to **11** — the ten above plus
`GASALLOWANCE`. DESIGNATION must read **Connected system¹ · Contract record²**, which is the card in
the owner's screenshot.

**Zero rules have both a `hr.payslip.import.mapping` row and `is_contract_component`** — the two are
mutually exclusive on live data, as the owner's rule says they should be. Assert it; do not rely on
it (a database predating the demotion could hold both, and the ranked list handles that correctly by
showing both in rank order).

### 2.5 The three writebacks, and the ordering constraint that shapes this phase

[`payroll_import_batch.py:1275-1294`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L1275):

```python
    self._sync_employee_bank_account(employee, raw_data, line=line)     # step 1b
    ...
    self._update_contract_from_raw_data(contract, raw_data)             # step 2
    contract = self._sync_contract_components(line, contract)           # step 3
    if self.create_payslips:
        payslip = self._create_payslip(employee, contract, line)        # step 4
```

All three read **`raw_data`** — the primary blob only — by name candidates. On a run carrying a
top-up they cannot see the other payload at all, which is the whole of the owner's request (a).

**The constraint:** the writebacks run at steps 1b–3; the resolver runs inside step 4. So a
writeback **cannot** simply reuse `input_values` — it does not exist yet. Do **not** solve this by
moving the resolve earlier or by reordering the steps; that changes transaction shape and error
isolation (note each step's deliberate try/except at
[`:1274-1279`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L1274) and
[`:1303-1306`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L1303)).

### 2.6 Ledger items that will bite here

- **MJ46** — a throwaway *rule* is not a throwaway *gesture*. `api_mapping_create` unlinks a rival on
  the **source** end as well as the target, so a probe draw deleted live mapping id 28 on abm last
  phase. Fingerprint every table you go near, before and after.
- **MJ45** — guards that read `source_binding` as if it were the only source. J9 fixed three; assume
  a fourth exists in the writeback paths and look for it.
- **MJ43 / MJ42** — no `//` inside an `import { }` list; `node --check` exits 0 without parsing an ES
  module. Verify JS by fetching the **served bundle**.
- **MJ40** — a fixed-width neighbour on the name line steals the name's width. You are adding a
  *second* chip to ten more cards. `0 clipped` is the gate.
- **MJ11** — take your own suite baselines.

---

## 3. Architecture

### 3.1 One function decides the order, and both callers use it

Add to `hr.formula.rule` (or the batch, whichever keeps the query count honest — state which and
why):

```python
def resolve_declared_value(rule, blobs, contract=None, employee=None):
    """The winning value for this component and where it came from, or (None, None)."""
```

It walks `declared_sources()` in rank order, using `blob_for_kind` for `feed`/`rule`/`excel`
([`payroll_import_batch.py:2970`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L2970)),
the mapped record read for `employee_field`/`contract_field`/`bank_account`, and the contract
component last — taking the first that is non-empty by **the existing test**.

**Both the resolver's bound branch and all three writebacks call this.** Two implementations of one
order is how the boards started disagreeing in the first place, and it is the failure this whole
programme exists to remove.

### 3.2 Writeback — request (a)

Each of the three writeback sites resolves its value through §3.1 instead of reading `raw_data` by
name. Two rails:

- **Never write a value back onto the record it came from.** If the winner's kind is
  `employee_field`, `contract_field`, `bank_account` or `contract_component`, the writeback for that
  component is a **no-op** — the record already holds it, and writing it back would be a self-assign
  that dirties `write_date` and pollutes any audit trail.
- **A blank everywhere is still a blank.** Nothing declared and nothing delivered means the writeback
  does exactly what it does today: nothing. This phase must not start creating rows that previously
  were not created — `hr_contract_advantage_template` and `hr_contract_advantage` are at **0 rows**
  on abm and must stay there.

Keep each site's existing try/except isolation. A component whose resolution raises must not fail the
line, let alone the batch.

### 3.3 Display — request (b)

**`_source_employee_dest_ids` → `_source_record_dests(config)`** returning
`{rule_id: {'kind': …, 'key': …, 'label': …}}` in **one query** (join `ir_model` and
`ir_model_fields`; do not read them per rule). Keep the existing `except` → empty guard: a chip must
never break the studio.

Every caller passes the dict where it passed the set — [`:945`](../../pb_formula_studio/models/pb_formula_studio.py#L945),
[`:953`](../../pb_formula_studio/models/pb_formula_studio.py#L953),
[`:958`](../../pb_formula_studio/models/pb_formula_studio.py#L958),
[`:991`](../../pb_formula_studio/models/pb_formula_studio.py#L991),
[`:1041`](../../pb_formula_studio/models/pb_formula_studio.py#L1041),
[`:6240`](../../pb_formula_studio/models/pb_formula_studio.py#L6240),
[`:6312`](../../pb_formula_studio/models/pb_formula_studio.py#L6312). **`in` works on both a set and
a dict**, so a missed call site fails silently rather than loudly — grep for every one and change
them together. `_declared_source` still returns `list[0]`; its shape does not change.

In `_declared_sources`, **delete the `if out: return out` early return** and append the record entry
in rank position, exactly as `contract_component` is appended.

Vocabulary — `_SOURCE_LABELS` and its `srcLabel` mirror in `source_vocab.js` gain two terms and
change none:

```
'employee_field':  "Employee record"      (unchanged)
'contract_field':  "Contract record"      (new)
'bank_account':    "Bank account"         (new)
```

Every literal written out for gettext; `_(variable)` extracts nothing and ships English forever
(S19). **The word "Odoo" must not appear in any of them** — see §5.

Chip tooltip states the field in human terms and its place in the order, e.g. *"Reads Job Position
from the contract record. Used when nothing above delivered a value."* Use the field's **label**, not
`job_id`.

Ranking, superscripts and the `(kind, key)` fold are J9's and are unchanged: the superscript shows
only at ≥2 sources and is the rank **among the sources mapped on that card**.

---

## 4. Test cases — run every one, report by number

Server:

1. `_declared_sources` for a rule with a feed source **and** a contract-field mapping returns **two**
   entries, feed first, `contract_field` second — the DESIGNATION shape.
2. The same rule's `_declared_source` (scalar) still returns the feed entry. Journey bucketing and
   the transform board unchanged.
3. `hr.employee` mapping → `employee_field`; `hr.contract` → `contract_field`;
   `destination_type='bank_account'` → `bank_account` with the role as key.
4. A rule with **only** a record mapping renders exactly as it does today: one chip, no superscript.
   (J9 case 15's guarantee must not regress.)
5. `_source_record_dests` costs **one** query for a 99-rule config. Assert with `assertQueryCount`
   or an equivalent; state the number.
6. Feed delivers → feed wins; the record field is **not** read (assert the read did not happen, not
   merely that the value differs).
7. Feed blank → the record field wins, `fell_back=True`, and the skipped feed is reported through
   `ignored_side`.
8. Feed blank **and** record field blank → the contract component wins; blank again → default.
9. Record field is `0` / `False` → it **wins** (MJ15); the tier below is not consulted.
10. **Writeback follows the order.** Dual-blob run, feed and Excel both carrying a value for a
    component: the contract component is written with the **feed** value, matching the payslip.
11. **Writeback no-op.** Winner is the contract field → the contract field is **not** rewritten;
    assert `write_date` is untouched.
12. Same for `contract_component` as winner and for `bank_account` as winner.
13. Nothing declared and nothing delivered → no advantage template and no advantage line is created.
14. All three writeback sites resolve through the **same** function as the resolver — a source
    assertion that there is one implementation of the order, in the style of J9's
    `_multi_source_walk_entered`.
15. Single-source neutrality holds: a component declaring one source resolves and writes back exactly
    as before J10. Quote the counter.

Client (hoot):

16. Two chips for a feed + contract-field card, `<sup>1</sup>` / `<sup>2</sup>`, in rank order.
17. `Contract record` and `Bank account` render with the right labels and classes.
18. A record-only card renders one chip and **no** superscript.
19. Three sources (feed + excel + contract field) render 1/2/3 in rank order.
20. A stale server sending the old `employee_field` for a contract field still renders one valid
    chip.

Live, on **abm only**:

21. **11** cards render ≥2 chips: the ten in §2.4 plus GASALLOWANCE. `DESIGNATION` reads
    **Connected system¹ · Contract record²**. Quote the list you measured.
22. `BANKNAME` renders **Connected system¹ · Bank account²**.
23. Sweep + `maxErr` at 1440 and 1024: 0 overlaps, 0 dock-over-card, 0 occluded/clipped heads, **0
    names clipped** (MJ40 — ten more cards just grew a chip).
24. Board round-trips before/after in ms for `employee_mapping_data`, `import_mapping_data`,
    `api_mapping_data`.

---

## 5. Safety rails

- **White-label, absolute.** "Odoo" must never appear in any user-visible string — labels, chips,
  tooltips, help text, placeholders, empty states, toasts, action/menu names, field `string=`/`help=`,
  selection labels, reports, exports, emails, `.po` msgstr. Use **Payobook** or a neutral term. Never
  rewrite technical identifiers: `from odoo import …`, model/XML ids, `odoo-bin`, config paths, addon
  names, log messages, code comments, docs. The pre-existing one in `import_wizard.scss`'s comment is
  a recorded owner debt — leave it.
- **Never `action_process` on a live database.** This phase edits record-writing code; that is the
  reason for the rail, not an exception to it. Exercise the writebacks in `TransactionCase` only.
- Live writes go through a throwaway rule named **`J10PROBE`**, created → exercised → reversed →
  deleted. **MJ46**: fingerprint `hr_payslip_import_mapping` and `hr_integration_field_mapping`
  before and after every board gesture, not just at the end.
- **MF37.** Before/after fingerprints on abm for `hr_formula_rule`, `hr_formula_rule_source`,
  `hr_payslip_import_mapping`, `hr_integration_field_mapping`, `hr_contract_advantage_template`,
  `hr_contract_advantage`, plus `hr_employee` and `hr_contract` **write_date** maxima — this is the
  first phase that could silently touch employee data, so prove it did not. Close with a clean diff.
- Suites: your own baselines (MJ11). Current **Python 515 / hoot 135**, with **three known
  pre-existing reds** (`TestBankDestinations.test_09_make_text_component`,
  `TestEndpointFieldCatalogue.test_05c`, `pb_integrations TestLedgers.test_the_ledgers_never_sudo`).
  Do not silence them; any fourth red is yours.
- One feature-scoped commit, explicit staging, reviewer-focused message. **Do not push.**
- Append **MJ48+** to `docs/handovers/JOURNEY_LEDGER.md`.

---

## 6. Deploy

Build and validate on **abm**. Then batch **`payobook`** and **`payobook_template`** in one pass.
**Never `acme`** — the owner has confirmed it is redundant and it is deliberately behind at
19.0.1.81.0 / 19.0.1.153.0.

Ritual (MAPFIX, unchanged): rsync → `sudo chmod -R a+rX` → stop → detached `systemd-run` with
`sudo -u odoo /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d <db> -u
pb_hr_payroll_formula,pb_formula_studio --stop-after-init` → start → verify
`ir_module_module.latest_version` in psql on the **three** databases you touched.

abm login: `ash@biztinct.com` / `J5validate!2026`.

---

## 7. Report back

- Commit sha, both module versions, `latest_version` on the three databases.
- Each of the 24 cases by number: pass / fail / deviation, stated plainly.
- The neutrality counter (case 15) — quote it.
- The query count for `_source_record_dests` (case 5).
- Suite deltas from your own baselines and the reds by name.
- The MF37 diff, including the `hr_employee` / `hr_contract` write_date maxima.
- **The abm picture after the change**: the measured list of cards with ≥2 chips. Expected 11. If it
  is 1, the early return is still there; if it is 21, the fold has broken.
- Anything that contradicts §2. That section is a claim, not scripture.
