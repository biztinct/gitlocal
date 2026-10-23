# CD-1 — The contract drawer's server side: one payload, one save path

**Programme:** CONTRACT DRAWER (CD). Owner asked, 2026-08-31, for the Contract
screen to be as good as the Employee one and to be **editable in place**
("Read beautifully, edit in place" — chosen explicitly over a read-only panel).

**Phase CD-1 scope:** the server only. No JS, no SCSS, no template. Build the
payload the drawer will read and the save path it will write through, and prove
both with tests. CD-2 builds the drawer that reads this; CD-3 makes it write.

Implemented by an Opus build agent. Fable designed this and will not re-review
the code — read the numbered test cases, run them, and report.

---

## 0. Standing rules that bind this phase

**WHITE-LABEL (hard rule).** The word "Odoo" and Odoo branding must never appear
in anything an end user can see: field `string=`/`help=`, selection labels,
error and refusal sentences, notification text, exported files. Use "Payobook"
or a neutral term ("the system", "this app", "the connected system", "the
native form"). **Never rewrite technical identifiers** — `from odoo import …`,
model/XML ids, `odoo-bin`, addon names, config paths, log messages, code
comments, docs. Those stay exactly as they are.

**PLAIN ENGLISH in every user-visible sentence.** Refusals are sentences a
payroll administrator understands, using the words on the screen: "pay run",
"pay data file", "the connected system", "the employee record", "the contract".
Never `hr.contract`, never `_coerce`, never a field's technical name, never an
internal ticket code (CD-1, W96, RD62) in anything a user reads.

**DESIGN BAR (binding, owner re-mandated 2026-08-29):** extreme WOW, intuitive,
out-of-this-world, best in class. Applies to this phase through the *sentences*
and the *shape of the payload* — a payload that forces the client to re-derive
facts produces a slow, inconsistent screen.

**DEPLOY CONTRACT** — see `CLAUDE.md`. Everything ships to
`/odoo/odoo-server/addons`. Clean the staging dir. Per-module
`sudo rsync -a --delete /tmp/<dir>/<m>/ /odoo/odoo-server/addons/<m>/`.
**NEVER** `--delete` with `/odoo/odoo-server/addons/` itself as destination.
Upgrade **all four** databases: `payobook`, `abm`, `acme`, `payobook_template`.

**CONVENTIONS LEDGER:** `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` (W-rules) and
`docs/FORMULA_ENGINE_CONVENTIONS.md` (C18.x). Cite rule numbers in comments.
Append any new gotcha you hit as a CD-n entry at the end of the W file.

---

## 1. Verified plumbing — DO NOT RE-DERIVE ANY OF THIS

Every reference below was read on 2026-08-31 and is current.

### 1.1 The module and the model

- `pb_contracts/models/pb_contracts.py` — `models.AbstractModel`,
  `_name = 'pb.contracts'` (`:28-30`). This is the RPC facade. Everything you
  add goes here.
- Existing methods: `_safe(fn, default=0)` `:32`; `get_board()` `:40`;
  `get_contract_detail(contract_id)` `:112`; `run_contract_action(contract_id,
  method, value=None)` `:164`.
- `STATE_LABEL` `:9` = `{'draft':'Draft','open':'Running','close':'Expired',
  'cancel':'Cancelled'}`. `ROSTER_LIMIT = 240` `:10`. `NEXT` `:12-19` maps state
  → `(method, label, icon, kind)`. `LIFECYCLE = {'set_running','terminate',
  'cancel'}` `:20`. `_initials(name)` `:23-25`.
- `get_contract_detail` returns 22 keys (`:141-162`): `id, name, employee,
  employee_id, initials, avatar, job, dept, structure, currency, state,
  state_label, kanban_state, wage, date_start, date_end, trial_end,
  days_to_expiry, tenure_label, pipeline, next_actions, error`.
  `pipeline` = `[{'key','label','done','current'}]` over a hardcoded 3-step
  `['draft','running','expired']` (`:132-137`); `cancel` folds into `expired`.
- **There is no write path on `pb.contracts` today.** `run_contract_action`
  (`:164-189`) is whitelisted to `set_running`/`terminate`/`cancel` and only
  writes `state` and `date_end` (`:176-181`).

### 1.2 The house server contract for a cockpit facade

From `docs/handovers/RECORDS_PHASE_R2_DESK.md:129` and confirmed in
`pb_records/models/pb_records_desk.py:1349,1351`:

> every method `@api.model`, returns plain dicts, **never raises to the client
> for user mistakes** — `{'ok': False, 'msg': …}`.

`UserError` is reserved for "you have no access at all"
(`pb_records_desk.py:85`). Per-cell ACL refusals become sentences instead
(`_may_write` `:91`), because "a cell this person could never save is read-only
on screen instead of raising an access dialog after they have typed into forty
of them".

### 1.3 `hr.contract` field inventory on this build

Core (`hr_contract/models/hr_contract.py`): `name` `:24`, `active` `:25`,
`structure_type_id` M2O `:26`, `employee_id` M2O `:27`, `department_id` M2O
compute+store readonly=False `:28`, `job_id` M2O compute+store `:30`,
`date_start` Date required `:32`, `date_end` Date `:33`, `trial_date_end` Date
`:35`, `resource_calendar_id` M2O `:37`, `wage` Monetary required tracking
`:41`, `notes` Html `:43`, `state` Selection `:44`, `company_id` `:51`,
`contract_type_id` M2O `:55`, `kanban_state` `:63`, `currency_id` `:68`,
`hr_responsible_id` M2O res.users tracking `:76`.

`om_hr_payroll/models/hr_contract.py` (`_inherit` at `:50`):
- `struct_id` M2O `hr.payroll.structure` `:53` — **not required**
- `schedule_pay` Selection (7) default monthly `:54`
- `resource_calendar_id` **redefined `required=True`** `:64`
- `dependents` Integer `:65` — the field is named **`dependents`**, string
  "No of dependents"
- `type_id` M2O `hr.contract.type` **required=True**, default = first record
  `:72`, string **"Employee Category"** (NOT "Contract Type" — that is
  `contract_type_id`)
- `advantages_ids` **One2many** `hr.contract.advantage` ← `contract_id` `:75`,
  string "Contract Components"
- `location` Char `:78`, `tupart` Selection YES/NO default YES `:79`,
  `shuipart` Selection YES/NO default YES `:80`
- `hirestatus` Selection `:87-93` — **as of commit 576d432a (2026-08-31)**:
  `active / resigned / terminated / long leave / new hire`, string
  "Employment status"
- `costcenter` Char `:94`
- `create(vals)` override `:118-125` auto-creates one `hr.contract.advantage`
  per `hr.contract.advantage.template` on every new contract.

`pb_hr_payroll_base/models/hr_payroll_structure_base.py:271` (`_inherit`):
`payroll_country` `:274`, `basic_salary` `:283`, `housing_allowance` `:284`,
`transport_allowance` `:285`, `meal_allowance` `:286`, `other_allowances`
`:287`, `tax_exemption_amount` `:290`, `social_security_number` `:291`,
**`tax_identification_number` Char `:292`**, `payroll_schedule` `:295`,
`wage_calculation` `:307`.

`pb_hr_payroll_formula/models/hr_contract.py:9` —
`advantage_change_count` Integer compute, string "Component Changes";
`_compute_advantage_change_count` `:14`; `action_view_advantage_changes()` `:21`.

`pb_hr_workforce_planning/models/formula_rule_extension.py:36` —
`grade_id` M2O `wfp.pay.grade` `:38`, `compa_ratio` Float compute+store `:46`,
`range_penetration` Float compute+store `:55`.

`om_hr_payroll_account/models/hr_payroll_account.py:217` — `journal_id` M2O
`account.journal`, "Salary Journal".

**Duplicate-definition hazards** (do not write blind): `meal_allowance` (om
`:69` vs base `:286`); `type_id` (om `:72` vs `hr_contract_types/models/
contract_type.py:18`).

### 1.4 `hr.contract.advantage` — the components

`om_hr_payroll/models/hr_contract.py:7-43`, `_name = "hr.contract.advantage"`.

| line | field | type | note |
|---|---|---|---|
| `:11` | `contract_id` | M2O `hr.contract` | |
| `:12` | `advantage_template_id` | M2O `hr.contract.advantage.template` | |
| `:15` | `advantage_template_code` | Char related `.code`, readonly | the CODE column |
| `:18` | `advantage_lower_bound` | Float related, readonly | |
| `:21` | `advantage_upper_bound` | Float related, readonly | |
| `:24` | `amount` | Float | |

Extended by `pb_hr_payroll_formula/models/contract_advantage_typed.py:36`:
`value_type` Selection related `advantage_template_id.value_type` readonly `:38`;
`text_value` Char `:44`.

**`_order` IS NOT DECLARED** — falls back to `id`, which because of the
`create` override is *template id* order. **Sort your payload explicitly by
`advantage_template_code`** or the grid looks random.

Value semantics:
- `value_type == 'text'` → `amount` stays `0.0`, the value is `text_value`, and
  **bounds are skipped** (`contract_advantage_typed.py:57-58`).
- `value_type == 'amount'` → bounds enforced **only when not both zero**
  (`om_hr_payroll/models/hr_contract.py:35`,
  `contract_advantage_typed.py:59-60`):
  ```python
  if record.amount and record.amount != 0.00 and not (
          record.advantage_upper_bound == 0 and record.advantage_lower_bound == 0):
  ```
  Auto-created templates get `lower_bound=0, upper_bound=0` → effectively
  unbounded.
- `@api.onchange("advantage_template_id")` `:26-29` sets `amount` from
  `template.default_value`.
- The formula module's `@api.constrains('advantage_template_id','amount')`
  `:49` **replaces** the base constraint by name (docstring `:51-55`).

Template model `hr.contract.advantage.template`
(`om_hr_payroll/models/hr_contract.py:128-136`): `name` `:132`, `code` required
`:133`, `lower_bound` `:134`, `upper_bound` `:135`, `default_value` `:136`,
plus `value_type` (`contract_advantage_typed.py:28`).
Auto-created from formula rules at
`pb_hr_payroll_formula/models/payroll_import_batch.py:4957-4982`, matched by
`code` against `hr.formula.rule.code`; **an existing template is never
flipped** (`:4973-4981`).

**The join you need for a good row label and the right editor:**
`hr.contract.advantage → advantage_template_id.code → hr.formula.rule (by
code) → {value_kind, is_text_component, requires_new_contract, net_role,
column_type}`. It is a **string-code join**, the same one
`_get_or_create_advantage_template` uses. Relevant rule fields
(`pb_hr_payroll_formula/models/formula_rule.py`): `is_contract_component` `:630`,
`requires_new_contract` `:636`, `is_text_component` `:666`, `value_kind`
Selection money/decimal/integer/quantity/rate/identifier/text/date/boolean
`:686`, `payroll_signal` `:714`, `column_type` `:120`.

### 1.5 History sources

1. **Component changes** — `pb_hr_payroll_formula/models/
   contract_component_change.py`, `_name` `:7`,
   `_order = 'effective_date desc, id desc'` `:9`. Fields: `contract_id`
   required cascade `:11`, `employee_id` related store `:17`, `company_id` `:24`,
   `advantage_template_id` required `:31`, `advantage_template_code` related
   store `:36`, `old_amount`/`new_amount` Float `:42-43`,
   `old_text_value`/`new_text_value` Char `:46-47`, `effective_date` required
   `:48`, `change_source` Selection `import / import_default / manual` default
   `import` `:49`, `import_batch_id` `:54`, `changed_by` `:59`, `changed_at`
   `:65`, `notes` `:70`.
   Manual-write precedent: `pb_records/models/pb_records_desk.py:1246-1256`
   (`change_source='manual'`) — **clone that shape.**
2. **Field audit** — `pb_employee_vault/models/hr_contract_audit.py:14-16` adds
   `biz.audit.mixin` to `hr.contract`, watching **`wage, state, date_start,
   date_end, struct_id, structure_type_id`** (docstring `:5-6`).
   Read the mixin's model to learn its record shape before you query it.
3. **Retro adjustments** —
   `pb_hr_payroll_formula/models/payroll_retro_adjustment.py:6`,
   `_order = 'period_from desc, employee_id'` `:9`. Carries `contract_id` M2O
   directly `:51` and `advantage_change_id` `:68`, plus `component_code`
   related store `:62`, `old_amount`/`new_amount`/`delta_amount` `:76-78`,
   `period_from`/`period_to` `:74-75`, `state` `:79`.

### 1.6 Reference data already available

`pb_people_advanced/models/people_wizards.py:79-96` — `pb.people.refs._refs()`
returns `{structures, structure_types, calendars, default_calendar,
default_struct, currency, today}`. **Reuse it, do not re-implement.**
The create-a-contract whitelist-and-cast precedent is
`pb.people.contract.wizard.create_contract` at `:130-155`.

### 1.7 Access

From `RECORDS_PHASE_R2_DESK.md:122`:
- **read**: `hr.group_hr_user` OR `pb_hr_payroll_base.group_payroll_base_officer`
- **write to a contract**: additionally `hr_contract.group_hr_contract_manager`

Implementation precedent: `_may_write(model_name)` at
`pb_records/models/pb_records_desk.py:91`, surfaced to the client as
`canWrite: {...}` (`pb_records/static/src/js/records_desk.js:64`) so unwritable
fields render read-only rather than raising after the fact.

Wage visibility: the employee drawer masks it server-side —
`pb_employee_vault/models/pb_people_360.py:106-108` sets
`profile['contract']['wage'] = False` and `wage_masked = True`. **Mirror that
exactly**; read that method before writing yours.

### 1.8 Owner ruling that shapes the save path

`pb_records/__manifest__.py` description:

> Contract fields are written **IN PLACE** on the person's current contract —
> **no new contract version**. That is an owner ruling (2026-08-29), not a
> shortcut.

CD follows it. A component whose rule carries `requires_new_contract` is
**still written in place**; the payload merely flags it so the drawer can warn.

---

## 2. What to build

Four new `@api.model` methods on `pb.contracts`, plus their tests. Nothing else.
Do not touch the existing four methods except where §2.5 says so.

### 2.1 `get_contract_360(self, contract_id)`

The single call the drawer makes on open. One round trip; the drawer must never
have to ask a second question to render a tab.

Return shape — **exact keys, this is a contract**:

```python
{
  'ok': True,
  'error': False,                  # a plain sentence when the contract is gone
  'currency': '₫',
  'can_write': True,               # §1.7 write gate
  'unmask_wage': True,             # §1.7 wage visibility

  'header': {
      'contract_id': 1051,
      'reference': 'Thuy Bui - 2026-06-01',   # hr.contract.name
      'employee': 'Thuy Bui',
      'employee_id': 1432,
      'initials': 'TB',
      'avatar': '/web/image/hr.employee/1432/avatar_128' or False,
      'job': 'Junior Logistic Executive',
      'dept': 'Finance - Accounting - IT',
      'state': 'open',
      'state_label': 'Running',
      'wage': 12500000.0,          # False when masked
      'wage_masked': False,
      'ends_label': 'Open-ended' | 'Ends in 92 days' | 'Ended 14 days ago',
      'ends_tone': 'ok' | 'warn' | 'err' | 'muted',
      'pipeline': [ {'key','label','done','current'}, … ],   # reuse §1.1
      'next_actions': [ {'method','label','icon','kind'}, … ],  # reuse §1.1
  },

  # TERMS TAB — grouped so the client renders sections without re-deriving.
  # `groups` is an ORDERED list; each field is an ORDERED list inside it.
  'terms': [
    {'key': 'money',   'label': 'The money',        'fields': [ …field… ]},
    {'key': 'dates',   'label': 'Dates',            'fields': [ … ]},
    {'key': 'place',   'label': 'Where they sit',   'fields': [ … ]},
    {'key': 'rules',   'label': 'Payroll rules',    'fields': [ … ]},
  ],

  'readiness': [       # the bottom chip row, mirrors the employee drawer
      {'key': 'structure', 'label': 'Salary structure', 'ok': True},
      {'key': 'schedule',  'label': 'Working schedule', 'ok': True},
      {'key': 'tax',       'label': 'Tax number',       'ok': False},
  ],

  'components': {
      'rows': [ …component row… ],       # sorted by code, see below
      'count': 26,
      'total': 18500000.0,               # sum of amount-typed rows; False if masked
      'addable': [ {'template_id': 7, 'code': 'OTALLOW', 'name': 'Other Allowance',
                    'value_type': 'amount', 'lower': 0.0, 'upper': 0.0,
                    'default': 0.0} ],   # templates not yet on this contract
  },

  'history': {
      'rows': [ …history row… ],         # newest first, capped 120
      'total': 340,
      'shown': 120,
  },
}
```

**A `field` entry** — one object per editable or readable term. This is the
whole point of the payload: the client renders and edits without knowing a
single Odoo field name's semantics.

```python
{
  'name': 'wage',                  # technical name — the save key
  'label': 'Monthly wage',         # SCREEN words, plain English
  'kind': 'money',                 # money|number|integer|text|date|select|toggle|m2o|readonly
  'value': 12500000.0,             # raw value, JSON-safe
  'display': '₫12,500,000',        # server-formatted, so the client never guesses
  'options': [ {'value': 'active', 'label': 'Active'}, … ],   # select/toggle only
  'comodel': 'hr.payroll.structure',                           # m2o only
  'value_label': 'Vietnam Permanent Monthly',                  # m2o only
  'required': True,
  'writable': True,                # False → render read-only, never send it
  'hint': 'Gross, before deductions.',   # optional one-liner under the field
  'tone': None | 'warn',
}
```

Field list per group — **build exactly these, in this order**:

- **money**: `wage` (money, required), `struct_id` (m2o
  `hr.payroll.structure`, label "Salary structure"), `type_id` (m2o
  `hr.contract.type`, label "Employee category", required), `schedule_pay`
  (select, label "Paid"), `grade_id` (m2o `wfp.pay.grade`, label "Pay grade",
  **only when the field exists** — `pb_hr_workforce_planning` may not be
  installed; use `'grade_id' in Contract._fields`), `compa_ratio`
  (readonly, only when `grade_id` is set), `journal_id` (m2o
  `account.journal`, label "Salary journal", only when the field exists).
- **dates**: `date_start` (date, required, "Contract starts"), `date_end`
  (date, "Contract ends"), `trial_date_end` (date, "Trial ends"),
  `resource_calendar_id` (m2o `resource.calendar`, "Working schedule",
  required).
- **place**: `department_id` (m2o `hr.department`, "Department"), `job_id`
  (m2o `hr.job`, "Job position"), `location` (text, "Location"), `costcenter`
  (text, "Cost centre"), `hr_responsible_id` (m2o `res.users`, "HR
  responsible").
- **rules**: `hirestatus` (select, "Employment status"), `tupart` (toggle
  YES/NO, "Union participation"), `shuipart` (toggle YES/NO, "Social insurance
  participation"), `dependents` (integer, "Dependants"),
  `tax_identification_number` (text, "Tax number").

For a `select`, take the options from the field's own selection and use the
**labels as declared** — do not re-word them here (the labels are already the
screen words; `hirestatus` now reads Active / Resigned / Terminated / Long
Leave / New Hire).

`writable` is `can_write AND not field.readonly AND not field.compute-without-
inverse`. `wage.writable` is additionally `False` when `unmask_wage` is False.

**A `component` row**:

```python
{
  'id': 8821,                       # hr.contract.advantage id
  'code': 'BASESALARY',
  'name': 'Base Salary',            # template name
  'value_type': 'amount',           # 'amount' | 'text'
  'amount': 12500000.0,
  'text_value': False,
  'display': '₫12,500,000',         # server-formatted; the text value verbatim for text rows
  'lower': 0.0, 'upper': 0.0,
  'bounded': False,                 # not (lower == 0 and upper == 0)
  'bounds_hint': 'Between ₫0 and ₫20,000,000.' or False,
  'value_kind': 'money',            # from the joined hr.formula.rule, 'money' when no rule
  'requires_new_contract': False,   # from the joined rule
  'template_id': 12,
  'writable': True,
}
```

Sort by `code`. `total` sums only `value_type == 'amount'` rows.

**A `history` row** — one merged, sorted stream:

```python
{
  'kind': 'component' | 'field' | 'retro',
  'when': '2026-08-30 12:33:41',     # UTC datetime string; the client localises
  'when_label': '30 Aug 2026',
  'title': 'Base Salary',            # what changed, in screen words
  'from': '₫12,500,000',             # already formatted, or False
  'to': '₫13,000,000',
  'source': 'Typed in Payobook' | 'From a pay data file' | 'From the connected system',
  'actor': 'Ash Nguyen' or False,
  'tone': 'indigo' | 'teal' | 'amber',
}
```

Map `change_source`: `manual` → "Typed in Payobook"; `import` → "From a pay
data file"; `import_default` → "Filled from the component's default".
When `import_batch_id.source_type` says the batch came from the connected
system, say "From the connected system" instead — check the batch's
`source_type` value (`api_data_store`) before choosing the sentence.

Cap at 120 rows, report `total` and `shown`.

**Errors:** a missing or unreadable contract returns
`{'ok': False, 'error': "That contract is no longer here."}` — never raise.

### 2.2 `save_contract_360(self, contract_id, terms=None, components=None, note=None)`

The one write path. Both payloads are optional so the drawer can save either
tab alone.

- `terms` — `{field_name: raw_value}`, only fields the payload marked
  `writable`.
- `components` — `{'edits': {advantage_id: {'amount': x} | {'text_value': s}},
  'adds': [{'template_id': n, 'amount': x} | {'template_id': n,
  'text_value': s}], 'removes': [advantage_id, …]}`

Behaviour:

1. **ACL first.** No write group → `{'ok': False, 'refusals': [], 'msg':
   "You can look at contracts but not change them. Ask an HR manager to make
   this change."}`. Do not raise.
2. **Whitelist.** Reject any key not produced as `writable` by
   `get_contract_360` for this contract and this user. Silently dropping is
   wrong — return it as a refusal.
3. **Coerce and validate per field**, producing a plain sentence for each
   failure. Clone the sentence style of
   `pb_records/models/pb_records_desk.py:791 _coerce(...)` — e.g.
   `"'abc' is not a number — type an amount like 1500000."` Reuse that method
   if you can call it cleanly; otherwise write the same shapes and say in a
   comment that the sentences are deliberately identical.
4. **Never write an empty value into a required field.** `resource_calendar_id`
   (required=True, `om_hr_payroll/models/hr_contract.py:64`), `type_id`
   (required=True `:72`), `date_start`, `wage`. Refuse with:
   "A contract must always have a working schedule — pick one before saving."
5. **Write in place** (§1.8). One `contract.write(vals)` for the accepted
   terms. **No new contract record, ever.**
6. **Components:**
   - edit: write `amount` or `text_value` on the advantage row, respecting
     `value_type`. Writing `amount` on a text row is a refusal, not a coercion.
   - bounds: enforce the same rule as the model (§1.4) and refuse with
     "Base Salary must be between ₫0 and ₫20,000,000." Let the model's own
     `@api.constrains` be the backstop, but **check first** so the user gets
     your sentence rather than a raised constraint.
   - add: create with `contract_id` + `advantage_template_id`; refuse a
     template already on the contract with "This contract already has Other
     Allowance."
   - remove: unlink. Refuse when the component is the destination of an active
     record mapping — look it up through `hr.payslip.import.mapping` /
     the formula rule by code — with "Other Allowance is filled automatically
     from a mapping, so it cannot be removed here."
   - **Every accepted amount/text change writes an
     `hr.contract.advantage.change` row** with `change_source='manual'`,
     `changed_by=self.env.user`, `changed_at=now`, `effective_date=today`, and
     both old/new in the right pair of columns (`old_amount`/`new_amount` for
     amount rows, `old_text_value`/`new_text_value` for text rows). Clone
     `pb_records/models/pb_records_desk.py:1246-1256`.
7. **Partial success is the normal case.** Write what passed, refuse what did
   not, and return:
   ```python
   {'ok': True,
    'saved': 4,
    'refusals': [{'scope': 'term'|'component', 'key': 'wage'|8821,
                  'why': "…plain sentence…"}],
    'msg': "4 changes saved." | "4 changes saved, 1 left alone.",
    'detail': { …the full get_contract_360 payload… }}
   ```
   Returning the full fresh payload is the house "mutate returns the whole
   thing" contract (`pb_employee_vault/models/pb_people_360.py` — all three
   mutations return `get_employee_360(...)`). The drawer re-renders from it and
   never patches locally.
8. **A refused change must not be rolled back into a lie.** If a `write` raises
   despite your checks, catch it, log with `_logger.exception`, and turn it into
   a refusal sentence. Nothing partially written may be silently reported as
   saved.

### 2.3 `preview_contract_360(self, contract_id, terms=None, components=None)`

Same validation as `save_contract_360` steps 1–4 and 6, **but writes nothing**.
Returns `{'ok': True, 'refusals': [...], 'accept': N}`.

This is what lets CD-3 paint a refusal under a field while the user is still
typing, exactly as the Records Desk does
(`pb_records/static/src/js/records_desk.js:417,442` — 400ms debounce; the
docstring at `:412` is the ruling: "a refusal is a red dot with a sentence, not
a modal").

**Factor the validation into one private helper** used by both `save_` and
`preview_`. Two copies of a predicate are two answers the day one is edited.

### 2.4 `lookup_contract_m2o(self, comodel, term='', limit=12)`

Mirror `pb_records/models/pb_records_desk.py`'s `lookup_m2o`
(client side at `pb_records/static/src/js/records_desk.js:465`). Returns
`[{'id': n, 'label': '…'}]`.

**Whitelist the comodels** to exactly the ones the terms payload can name:
`hr.payroll.structure`, `hr.contract.type`, `resource.calendar`,
`hr.department`, `hr.job`, `res.users`, `wfp.pay.grade`, `account.journal`.
Anything else returns `[]`. An open `comodel` argument is a data-exfiltration
hole.

### 2.5 One touch to an existing method

`get_board()` `:40` currently caps at `ROSTER_LIMIT = 240` and filters
client-side. **Leave it exactly as it is.** The only permitted edit to existing
code in this phase is adding `'has_360': True` to the `get_board()` return dict
so CD-2's contracts list can decide whether the drawer exists without probing.

---

## 3. Safety rails

1. **Never create a contract.** This phase writes to an existing contract or
   refuses. No `hr.contract.create` anywhere.
2. **Never `unlink` a contract.** Removes are component rows only.
3. **`sudo` discipline.** Read with the user's own rights so record rules
   apply. Use `sudo()` only for the two satellite writes that need it
   (`hr.contract.advantage`, `hr.contract.advantage.change`) and only *after*
   you have proved the user may write the contract. **W97**
   (`docs/WORKFORCE_REDESIGN_CONVENTIONS.md:1470`): a satellite table with no
   `company_id` inherits its owner's record rule and one unreadable row takes
   the whole table with it — `hr.contract.advantage` has no `company_id`.
4. **No new fields on any model in this phase.** Everything is read from what
   already exists.
5. **No migration.** Nothing structural changes.
6. **Money formatting happens server-side, once** (`display`). Do not send a
   half-formatted number and hope the client agrees.
7. **`_safe()` (`:32`) exists for a reason** — the board must render when one
   sub-computation fails. Use the same discipline for the three history
   sources: a missing `biz.audit.mixin` model, an uninstalled
   `pb_hr_workforce_planning`, or a retro table with nothing in it must all
   degrade to an empty list, never to an exception.
8. **Guard every optional module's field** with `'x' in Model._fields` before
   reading it. `grade_id`, `compa_ratio`, `journal_id`,
   `advantage_change_count` all come from modules that may be absent.

---

## 4. Numbered test cases

New file: `pb_contracts/tests/test_cd1_contract_360.py`, plus
`pb_contracts/tests/__init__.py` and the `tests` import in the module's
`__init__.py` (the module has no tests today — create the package).
Tag `@tagged('post_install', '-at_install')`.

Build a fixture contract with: an employee, a wage, a structure, a working
schedule, a `type_id`, two amount components (one bounded, one not) and one
text component.

1. **Payload shape.** `get_contract_360` returns every top-level key in §2.1,
   `ok is True`, `error is False`.
2. **Terms are grouped and ordered.** The four group keys appear in the order
   `money, dates, place, rules`, and `wage` is the first field of `money`.
3. **Every field entry is complete.** For each field in every group: `name`,
   `label`, `kind`, `value`, `display`, `writable` are present, `label`
   contains no underscore and is not equal to `name`.
4. **Components are sorted by code and typed.** The rows come back in `code`
   order; the text component has `value_type == 'text'`, a `text_value`, and
   `amount == 0.0`; `bounded` is True only for the bounded one, and
   `bounds_hint` is a sentence for it and False for the others.
5. **`addable` excludes what is already on the contract** and includes at least
   one template that is not.
6. **Wage masking.** With the wage-visibility gate off, `unmask_wage is False`,
   `header['wage'] is False`, `header['wage_masked'] is True`, the `wage` field
   entry is `writable: False`, and `components['total'] is False`.
7. **Missing contract.** `get_contract_360(0)` returns
   `{'ok': False}` with a plain-English `error`, and does **not** raise.
8. **Save writes in place.** `save_contract_360` with a new wage changes the
   wage on the SAME contract id; `hr.contract.search_count` for that employee is
   unchanged (the owner ruling — no new version).
9. **Save refuses a non-writable key** it never offered, returning a refusal
   entry rather than silently dropping it, and `saved` does not count it.
10. **Save refuses to empty a required field.** Sending
    `resource_calendar_id: False` produces a refusal whose sentence names the
    working schedule in screen words, and the contract keeps its calendar.
11. **A bad number is a sentence, not an exception.** `wage: 'abc'` returns a
    refusal, `ok is True`, and the wage is unchanged.
12. **Partial save.** One good field + one bad field → the good one is written,
    `saved == 1`, exactly one refusal, and `msg` says both halves.
13. **Component amount change logs an audit row.** Editing an amount creates
    exactly one `hr.contract.advantage.change` with `change_source == 'manual'`,
    correct `old_amount`/`new_amount`, and `changed_by == self.env.user`.
14. **Text component change logs into the TEXT columns**
    (`old_text_value`/`new_text_value`), and `old_amount`/`new_amount` stay 0.
15. **Writing an amount onto a text row is refused**, not coerced.
16. **Out-of-bounds amount is refused with the bounds in the sentence**, and
    the stored amount is unchanged.
17. **Adding a component** creates one advantage row with the template's
    `default_value`; adding a template already present is refused with a
    sentence naming the component.
18. **Removing a component** unlinks it; removing one that a mapping fills is
    refused with a sentence.
19. **Preview writes nothing.** `preview_contract_360` with the same bad payload
    as case 11 returns the identical refusal and the contract is byte-identical
    afterwards.
20. **Preview and save agree.** For a mixed payload, the set of refusal keys
    from `preview_` equals the set from `save_` (the shared-helper pin).
21. **ACL.** As a user with read but not contract-write rights:
    `get_contract_360` still returns `ok`, `can_write is False`, every field is
    `writable: False`, and `save_contract_360` refuses with a plain sentence and
    writes nothing.
22. **`lookup_contract_m2o` whitelist.** A listed comodel returns rows; an
    unlisted one (`res.partner`) returns `[]`.
23. **History merges three sources, newest first**, each row carrying `kind`,
    `when`, `title`, `source`, and the `source` sentence for a manual change
    reads "Typed in Payobook".
24. **History degrades gracefully.** With no component changes, no audit rows
    and no retro rows, `history['rows'] == []` and nothing raises.
25. **`save_contract_360` returns a fresh payload** whose `header['wage']`
    already reflects the change just made (the mutate-returns-everything
    contract).
26. **No "Odoo" anywhere.** Assert that no string value in the whole
    `get_contract_360` payload, and no refusal sentence produced by the tests
    above, contains "odoo" case-insensitively. Walk the dict recursively.

---

## 5. Build, test and deploy steps

1. Bump `pb_contracts/__manifest__.py` version (it is `19.0.1.0.0`; go to
   `19.0.1.1.0`).
2. Create the tests package; register it in `pb_contracts/__init__.py`.
3. Deploy per §0:
   ```
   ssh Payobook19v2 "sudo rm -rf /tmp/deployCD1 && mkdir -p /tmp/deployCD1"
   rsync -az --exclude=__pycache__ --exclude='*.pyc' --exclude='.DS_Store' \
       pb_contracts Payobook19v2:/tmp/deployCD1/
   ssh Payobook19v2 "sudo rsync -a --delete /tmp/deployCD1/pb_contracts/ \
       /odoo/odoo-server/addons/pb_contracts/"
   ```
4. Run the suite detached, scoped (**W9**: never a bare `--test-tags`):
   ```
   sudo systemd-run --collect --unit=cd1 --property=User=odoo \
     --property=WorkingDirectory=/odoo/odoo-server \
     /usr/bin/python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf \
     -d payobook_template -u pb_contracts --stop-after-init \
     --http-port=8199 --gevent-port=8198 \
     --test-enable --test-tags=/pb_contracts
   ```
   Read `/var/log/odoo/odoo-server.log` — **not** a `/tmp` sentinel.
   Note: the template database cannot create persona users; ~15 unrelated
   modules error on that. Scope with `-u pb_contracts` and judge only your own.
5. Upgrade all four databases and verify
   `ir_module_module.latest_version` per database (Odoo prefixes the series —
   `19.0.1.1.0` in the DB matches a manifest of `1.1.0` or `19.0.1.1.0`).
6. No asset purge needed — this phase ships no JS or SCSS.
7. Sanity-check against real data on `abm`: call `get_contract_360` in a shell
   for contract **1051** (employee Thuy Bui) and for one contract that has
   component changes in its history, and paste both payloads' key sets into the
   report.
8. **One feature-scoped commit**, explicit file staging, reviewer-focused
   message. Do not push.

---

## 6. Report back

Answer each of these explicitly:

1. Test results — the exact `N failed, M error(s) of K tests` line, and for any
   failure whether it is yours or pre-existing/environmental.
2. The real `get_contract_360` payload key sets from step 7, and the row counts
   for `components.rows`, `components.addable` and `history.rows` on abm
   contract 1051.
3. Anything in §1 that turned out to be **wrong or stale** — that is the most
   valuable thing you can report, and it goes into the ledger.
4. Every place you had to make a judgement call the spec did not settle, and
   what you chose.
5. Which of the 26 test cases you could not write, and why.
6. Whether `biz.audit.mixin` gave you a usable history source, and its actual
   record shape — CD-2 depends on it.
7. Any field in §2.1's terms list that does not exist on this build, or that is
   readonly/computed and therefore came back `writable: False`.
8. A one-paragraph plain-English summary a non-engineer could read.
