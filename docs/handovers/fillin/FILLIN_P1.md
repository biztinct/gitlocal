# FILLIN P1 — a new contract starts with the scheme's usual answers (server)

Read `docs/handovers/fillin/FILLIN_LEDGER.md` first. Its §0 rules, §1 facts
and §2 decisions bind this phase; do not re-derive anything listed there.

## 1. Scope

Deliver, in `pb_hr_payroll_formula` (+ one hook in `pb_scheme_map`):

1. **Fill-in on create.** `hr.contract.create` → for each new contract whose
   employee's paying scheme is known, add a component line for every rule of
   that scheme that `is_contract_component`, has a non-empty `default_value`
   (≠ 0 / None), and whose code the contract does not already carry.
2. **Fill-in when "Paid by" becomes known.** In `pb_scheme_map`'s
   `_pb_recompute_paid_by` (`hr_employee.py:116`), for every employee whose
   `pb_paid_by_id` went from empty to a scheme, run the same fill on their
   draft/running contracts (missing codes only).
3. **Marking.** New fields on `hr.contract.advantage` (D3): `pb_fill`,
   `pb_checked_by`, `pb_checked_at`. A human/file write clears `pb_fill` and
   stamps `pb_checked_*`. Two server methods on `hr.contract`:
   `pb_fillin_unchecked()` → the unchecked lines, and
   `pb_fillin_check(line_ids=None)` → stamps them (all unchecked lines of the
   contract when `line_ids` is None). Access: `pb_fillin_check` requires the
   same right as the contract panel's save (`pb.contracts._cd_may_write`
   semantics: `hr_contract.group_hr_contract_manager` or the Payobook payroll
   manager group — read `pb_contract_360.py:245-260` and mirror it, do not
   import pb_contracts).
4. **Change log.** `hr.contract.advantage.change.change_source` gains
   `auto_default` ("Filled in by Payobook from the scheme's usual answer") and
   `checked` ("Checked, no change"). Every fill writes one `auto_default` row
   (`changed_by` = the user whose action created the contract, or the cron
   user; `new_value` = the default). Every check writes one `checked` row.
5. **Words for each value.** `hr.formula.rule.value_labels` Char (D4) + helper
   `hr.formula.rule.value_label_options()` → `[{'value': 0.0, 'label': 'No'}, …]`
   (parses `0=No;1=Yes`; invalid text → `[]`; never raises). And
   `value_label_for(amount)` → the label or `''`.
6. **rize seed (one-off, scripted, evidenced).** On scheme 7121 only:
   `IDBPJSTKCOVERE.default_value=1`, `IDBPJSHEALCOVE=1`, `IDERREIMBUBPJS=0`,
   `IDTAXALLOWMODE=1`; labels `0=No;1=Yes` on the three flags and
   `0=None;1=Insurance-premium tax only;2=All tax (net salary)` on the tax
   mode. Script in `tools/seed_fillin_rize_indonesia.py` (idempotent, prints
   before/after, runs through `odoo-bin shell`). **Do not touch any existing
   contract line.**
7. **Unit tests** (§5) and a **report** (§7).

### Non-goals (binding)
* No screen work: no panel, board, chip, pay run line, studio editor. That is
  P2. (You may add `value_labels` and `pb_fill`/`pb_checked_*` to RPC payloads
  only where P2 will need them: `pb_contract_360._cd_comp_row/_cd_virtual_row`
  — ONLY if trivial; otherwise leave for P2 and say so.)
* No retyping of `value_kind`. No change to `normalize_input_value`, the
  Excel generators, formulas or `_sync_contract_components` behaviour — except
  the write-hook side effect in §3.3.
* No backfill of existing contracts. No touch of `abm`.
* The catalogue template `default_value` stays what it is.

## 2. Plumbing — verified, do not re-derive

* Fields and helpers: FILLIN_LEDGER §1. Of note:
  * `component_scope_for_employee(employee)` →
    `{known: bool, schemes: hr.formula.config recordset, codes: set}`
    (`scheme_component_scope.py:173`). Use `schemes` and read
    `rule_ids.filtered(lambda r: r.is_contract_component and not r.is_text_component)`.
    Check how `known` is computed (`:65-110`) — a stale answer resolves live.
  * Template get-or-create: clone the body of
    `payroll_import_batch._get_or_create_advantage_template` (`:5215-5235`)
    into a small `@api.model` helper on `hr.contract.advantage.template`
    (`template_for_rule(rule)`), then make the import batch call it (one-line
    change) so there is ONE search-by-code.
  * The change-log writer the import uses:
    `_log_contract_component_change(contract, template, old, new, source, …)`
    on the batch (`payroll_import_batch.py`, grep it). Add a model-level
    `hr.contract.advantage.change.log(contract, template, old, new, source,
    notes='', user=None)` and have both the fill-in and (if trivial) the batch
    use it. Do not change the batch's call sites beyond a delegating wrapper.
* `hr.contract` is already inherited in
  `pb_hr_payroll_formula/models/employee_work_timezone.py:131`; add a NEW
  file `models/contract_fill_in.py` (register in `models/__init__.py`), do not
  grow that one.
* Odoo 19: `@api.model_create_multi`; `self.env.user`; `fields.Datetime.now()`;
  `Domain`-free plain lists are fine here. A `sudo()` is needed to read a rule
  behind payroll groups when the creator is an HR user who is not payroll —
  read rules via `self.env['hr.formula.rule'].sudo()`, write lines in the
  caller's rights **except** when the caller may create a contract but not its
  lines (check `security/ir.model.access.csv` of `om_hr_payroll` for
  `hr.contract.advantage`); if that is the case, write with `sudo()` and say so
  in the report.

## 3. Design to build

### 3.1 `models/contract_fill_in.py`

```python
class HrContract(models.Model):
    _inherit = 'hr.contract'

    @api.model_create_multi
    def create(self, vals_list):
        contracts = super().create(vals_list)
        if not self.env.context.get('pb_skip_fill_in'):
            contracts._pb_fill_in_defaults()
        return contracts

    def _pb_fill_in_defaults(self):
        """Add the paying scheme's usual answers to every contract in self
        that lacks them. Never raises, never overwrites (ledger rule 9/10)."""
        for contract in self:
            try:
                self._pb_fill_one(contract)
            except Exception:                       # noqa: BLE001
                _logger.warning('pb fill-in: contract %s', contract.id, exc_info=True)

    def _pb_fill_one(self, contract):
        if not contract.employee_id or contract.state not in ('draft', 'open'):
            return 0
        Config = self.env['hr.formula.config'].sudo()
        scope = Config.component_scope_for_employee(contract.employee_id)
        if not scope.get('known') or not scope.get('schemes'):
            return 0
        have = {l.advantage_template_id.code for l in contract.advantages_ids}   # FI2
        made = 0
        for scheme in scope['schemes']:
            for rule in scheme.rule_ids.filtered(
                    lambda r: r.is_contract_component and not r.is_text_component
                    and r.code and r.code not in have and (r.default_value or 0.0) != 0.0):
                template = self.env['hr.contract.advantage.template'].template_for_rule(rule)
                self.env['hr.contract.advantage'].with_context(pb_fill_in_write=True).create({
                    'contract_id': contract.id, 'advantage_template_id': template.id,
                    'amount': rule.default_value, 'pb_fill': 'auto'})
                self.env['hr.contract.advantage.change'].log(
                    contract, template, 0.0, rule.default_value, 'auto_default',
                    notes='Filled in from the usual answer on %s' % scheme.name)
                have.add(rule.code); made += 1
        return made

    def pb_fillin_unchecked(self):
        return self.mapped('advantages_ids').filtered(
            lambda l: l.pb_fill == 'auto' and not l.pb_checked_at)

    def pb_fillin_check(self, line_ids=None): ...   # §1.3; returns how many were stamped
```

* Multiple schemes in `scope['schemes']` (a group/host case): fill from each,
  first scheme wins on a duplicate code.
* The `made` count per contract is logged at INFO (`'pb fill-in: %s lines on
  contract %s for %s'`).

### 3.2 `hr.contract.advantage` fields + write hook (same file or `contract_advantage_typed.py`)

```python
pb_fill = fields.Selection([('auto', 'Filled in by Payobook')], string='Filled in by', copy=False)
pb_checked_by = fields.Many2one('res.users', string='Checked by', copy=False)
pb_checked_at = fields.Datetime(string='Checked on', copy=False)

def write(self, vals):
    res = super().write(vals)
    if ({'amount', 'text_value'} & set(vals)) and not self.env.context.get('pb_fill_in_write'):
        touched = self.filtered(lambda l: l.pb_fill)
        if touched:
            super(HrContractAdvantage, touched).write({
                'pb_fill': False, 'pb_checked_by': self.env.uid,
                'pb_checked_at': fields.Datetime.now()})
    return res
```
`copy=False` matters: `contract.copy()` (import's new-contract-for-components
path `:5280`) must not carry "filled in, unchecked" onto a copy that a file
is about to overwrite. **Verify** that `copy()` of a contract copies
`advantages_ids` (One2many default copy=True) — if so the copied line has
`pb_fill=False`, which is the wanted outcome; state it in the report.

### 3.3 Hook in `pb_scheme_map/models/hr_employee.py::_pb_recompute_paid_by`

After the bulk write that stores the new `pb_paid_by_id`, collect the
employees whose previous `pb_paid_by_id` was empty and new one is set, and
call `self.env['hr.contract'].search([('employee_id','in',ids),
('state','in',['draft','open'])])._pb_fill_in_defaults()`. Guard with
`hasattr(Contract, '_pb_fill_in_defaults')`. Read the method fully first
(`:116-180`) to find where "changed" is known.

### 3.4 `hr.formula.rule.value_labels`

```python
value_labels = fields.Char(
    string='Words for each value',
    help='Optional. How a value reads on screen, e.g. "0=No;1=Yes" or '
         '"0=None;1=Insurance-premium tax only;2=All tax (net salary)". '
         'The pay data file and formulas keep using the numbers.')
```
+ `value_label_options()` / `value_label_for(amount)` as in §1.5. Add
`'value_labels'` to the studio rule read-back list ONLY if it is a plain
field list (`pb_formula_studio.py:2602, 6837` — these are in the file we never
edit; so NO. Leave it to P2 via `_inherit`.) Also include `value_labels` in
whatever `hr.formula.rule` copy/duplicate helpers list fields explicitly
(grep `'default_value'` across `pb_hr_payroll_formula/models/` and mirror).

### 3.5 Seed script `tools/seed_fillin_rize_indonesia.py`

Run as `sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c
/etc/odoo-server.conf -d rize --no-http < tools/seed_fillin_rize_indonesia.py`
(the repo has precedents: `tools/configure_rize_indonesia_inputs.py`). It must:
print the four rules' `default_value` and `value_labels` before, write, print
after, `env.cr.commit()`, and assert no `hr.contract.advantage` row changed
(count + max write_date before/after). Keep a copy of its output in the
report.

## 4. Safety rails

* The create override must be exception-proof (ledger rule 10). A test proves
  a broken scope helper still lets the contract save.
* Never write a line whose code the contract already has. Never write text
  rules. Never write when `known` is False.
* `pb_skip_fill_in` context honoured (for scripts that build contracts with
  explicit lines and want no defaults).
* `pb_fill_in_write` context is the ONLY way to write a line without clearing
  the mark.
* The fill runs inside the creating transaction; no commit, no cron.
* No change to any `.po` is needed in P1 unless you add a user-visible
  string; `value_labels` help text is user-visible → add EN + VI entries to
  `pb_hr_payroll_formula/i18n/vi_VN.po` following the PO rules in memory
  `po-translation-loading-rules` (restated in `APPROVAL_MATRIX_CLOSEOUT.md`).

## 5. Test cases (`pb_hr_payroll_formula/tests/test_fillin_p1.py`, tag `fillin`)

Fixture: a company, an active scheme with country ID, three component rules
(`T_FLAG` default 1, labels `0=No;1=Yes`; `T_MODE` default 1, three labels;
`T_ZERO` default 0; `T_TEXT` text component), an employee in a team that the
scheme map resolves (or make the scheme the company's only active one, which
resolves by rung 5 — read `pb_scheme_map.py:18-41`). Use
`test_records_r5_record_rung.py` as the style precedent.

| # | Case | Expect |
|---|---|---|
| T1 | create a draft contract for the employee | lines for `T_FLAG`=1 and `T_MODE`=1 with `pb_fill='auto'`, none for `T_ZERO` or `T_TEXT`; two `auto_default` change rows |
| T2 | create with `advantages_ids` command carrying `T_FLAG`=0 | `T_FLAG` stays 0 with `pb_fill=False`; `T_MODE` filled (FI2) |
| T3 | employee with no resolvable scheme | contract saves, no lines, no error |
| T4 | scope helper raises (patch it) | contract saves; WARNING logged |
| T5 | human write `amount=0` on a filled line | `pb_fill=False`, `pb_checked_by=uid`, `pb_checked_at` set |
| T6 | `pb_fillin_check()` | lines keep `pb_fill='auto'`, get `pb_checked_*`; one `checked` row each; `pb_fillin_unchecked()` now empty; a non-manager gets AccessError |
| T7 | import-sync shape: a line exists with 1, the file lacks the column | amount stays 1 and `pb_fill` stays 'auto' (call `_sync_contract_components` with a batch whose row has no such column, or replicate its branch — see FI1) |
| T8 | `contract.copy()` | copied lines have `pb_fill=False`, no `pb_checked_*` |
| T9 | `value_label_options()` on the three label strings + garbage | parsed lists; `[]` on garbage; `value_label_for(1.0)=='Yes'` |
| T10 | "Paid by" becomes known: employee with no scheme, contract created (no lines), then map resolves and `_pb_recompute_paid_by(employee_ids=[e])` | lines appear |
| T11 | `pb_skip_fill_in` context | nothing filled |
| T12 | seed script dry logic (unit-level): applying the four defaults twice is idempotent | second run writes nothing |

Run on `p0clone` with the ledger recipe; report the numbers and the log path.

## 6. Deploy / verify

1. Commit (`feat(fillin): a new contract starts with the scheme's usual
   answers; filled-in lines are marked and checkable`), push `19.1`.
2. Announce to live sessions, then `/odoo/ops/filter_deploy.sh full` with
   `pb_hr_payroll_formula,pb_scheme_map` (sync + upgrade) on the four DBs.
   Bump both manifest versions (patch). START/DONE lines in `/opt/deploy-notes.md`.
3. Run the seed script on `rize` only. Then verify with psql:
   `select code, default_value, value_labels from hr_formula_rule where
   config_id=7121 and code in (...)`; and that
   `select count(*), max(write_date) from hr_contract_advantage` is unchanged.
4. Live smoke on `rize` **without creating a real person**: create a contract
   in the `odoo-bin shell` inside a transaction for an existing Indonesia
   employee who has none (e.g. employee 5285 Aradea Putra Suriya), print the
   filled lines and the change rows, then `env.cr.rollback()`. Paste the
   output. Do NOT commit that transaction.

## 7. Report back (`docs/handovers/fillin/FILLIN_P1_REPORT.md`)

* T1–T12 results with evidence; deploy evidence per DB (versions); seed script
  output; the rollback smoke output.
* Facts P2 needs: exact field names; the payload keys you added (if any);
  the `pb_fillin_check` signature and its access rule; whether lines are
  written with sudo; whether `copy()` behaved as §3.2 expects.
* Anything you had to decide that the handover did not cover, and any gotcha
  for the ledger (as a proposed `FI<n>` line).
* Plain-English summary (5 lines) for the owner.
