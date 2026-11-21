# -*- coding: utf-8 -*-
"""JOURNEY J10 — the record is a source too, and the writeback obeys the order.

Two owner requests that turn out to be one:

  * **(a)** the writeback should follow the same priority as the payslip. It did
    not, and it could not: `_update_employee_from_raw_data`,
    `_sync_employee_bank_account`, `_update_contract_from_raw_data` and
    `_sync_contract_components` each read `raw_data` — THE PRIMARY BLOB ONLY —
    by name candidates, so on a run carrying a top-up they could not see the
    other payload at all.
  * **(b)** a card must show EMPLOYEE RECORD / CONTRACT RECORD beside whatever
    else it declares, not only when it is the sole source. That is the display
    half and it lives in `pb_formula_studio`.

Both need one answer to "which declared source wins", and before this phase
there were two: the resolver's ranked walk, and three writeback sites guessing
by header name. `_declared_source_walk` is now the only implementation, and
`_shared_resolution_entered` is the instrument that says so.

**THE ORDERING CONSTRAINT.** The writebacks run at steps 1-3 of
`action_process`; the resolver runs inside step 4. A writeback therefore cannot
reuse `input_values` — it does not exist yet — and nothing here moves the
resolve earlier or reorders the steps, because each step's try/except isolation
is deliberate. The ORDER was extracted instead of the RESULT.

`action_process` is never called anywhere in this file. The writebacks are
exercised directly, on records this transaction created, which is the only way a
test of record-writing code has any business running (J3's rule, and J10 is the
first phase that could silently touch employee data).
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _src(module, *parts):
    with open(os.path.join(get_module_path(module), *parts), encoding='utf-8') as fh:
        return fh.read()


def _strip_py_comments(src):
    """Comments are exempt from a source assertion, and MJ47 is why.

    A grep for a token fails on the prose that documents the rule it is
    enforcing — which is exactly the sentence the next reader needs. Strip
    first, then assert; do not "fix" it by deleting the comment.
    """
    out = []
    for line in src.splitlines():
        stripped = re.sub(r'(?<!["\'])#.*$', '', line)
        out.append(stripped)
    return '\n'.join(out)


@tagged('post_install', '-at_install')
class TestJourneyJ10Writeback(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.Mapping = cls.env['hr.payslip.import.mapping']
        cls.IrModel = cls.env['ir.model']
        cls.IrField = cls.env['ir.model.fields']

    # ------------------------------------------------------------- fixtures
    def _config(self, name):
        cfg = self.Config.create({
            'name': name, 'code': name.upper().replace(' ', '')[:32],
            'country_code': 'VN', 'state': 'active',
        })
        self.bonus = self.Rule.create({
            'config_id': cfg.id, 'name': 'Site Bonus', 'code': 'SITEBONUS',
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
        })
        return cfg

    def _batch(self, cfg, source_type='excel'):
        return self.Batch.create({
            'name': 'J10 %s' % source_type, 'source_type': source_type,
            'formula_config_id': cfg.id})

    def _field(self, model, name):
        return self.IrField.search(
            [('model', '=', model), ('name', '=', name)], limit=1)

    def _model(self, model):
        return self.IrModel.search([('model', '=', model)], limit=1)

    def _map_field(self, cfg, rule, model, field):
        return self.Mapping.create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'destination_type': 'field',
            'target_model_id': self._model(model).id,
            'target_field_id': self._field(model, field).id,
        })

    def _map_bank(self, cfg, rule, role):
        return self.Mapping.create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'destination_type': 'bank_account', 'bank_role': role})

    def _employee(self, name='J10 Person', **vals):
        """`barcode` is deliberately never used as the record-tier field here.

        `hr.employee` AUTO-GENERATES a badge id on create and then validates it
        (alphanumeric, <= 18 chars), so it is neither reliably empty nor
        reliably writable — a fixture built on it tests the badge generator
        rather than the ladder. `job_title` is a plain Char with no default.
        """
        return self.env['hr.employee'].create(dict({'name': name}, **vals))

    def _blobs(self, batch, raw, topup=None):
        """The two payloads, exactly as `_writeback_blobs` assembles them."""
        primary = 'feed' if batch.source_type == 'api_data_store' else 'excel'
        other = 'excel' if primary == 'feed' else 'feed'
        return {primary: raw or {}, other: topup or {}}

    @property
    def _shared(self):
        return self.Batch._sourcing_shared_counter()

    def _reset(self):
        self.Batch._sourcing_reset_branch_counter()
        self.Batch._sourcing_reset_shared_counter()

    # =====================================================================
    # 3 — the three spellings of rank 4, chosen by what the row points at
    # =====================================================================
    def test_03a_an_employee_field_mapping_is_employee_field(self):
        cfg = self._config('J10 Kind Emp')
        m = self._map_field(cfg, self.bonus, 'hr.employee', 'barcode')
        spec = self.Batch._record_dest_spec(m)
        self.assertEqual(spec['kind'], 'employee_field')
        self.assertEqual(spec['key'], 'barcode')
        self.assertTrue(spec['label'])

    def test_03b_a_contract_field_mapping_is_contract_field(self):
        cfg = self._config('J10 Kind Con')
        m = self._map_field(cfg, self.bonus, 'hr.contract', 'name')
        spec = self.Batch._record_dest_spec(m)
        self.assertEqual(spec['kind'], 'contract_field')
        self.assertEqual(spec['key'], 'name')

    def test_03c_a_bank_row_is_bank_account_keyed_by_its_role(self):
        cfg = self._config('J10 Kind Bank')
        m = self._map_bank(cfg, self.bonus, 'acc_number')
        spec = self.Batch._record_dest_spec(m)
        self.assertEqual(spec['kind'], 'bank_account')
        self.assertEqual(spec['key'], 'acc_number')
        self.assertEqual(spec['label'], 'Account number')

    def test_03d_the_rank_gained_three_members_and_nothing_moved(self):
        """J-D5. Rank 4 is where the resolver's tail already read the record."""
        rank = self.env['hr.formula.rule']._SOURCE_RANK
        self.assertEqual(rank[:3], ('feed', 'rule', 'excel'),
                         "the first three rungs are untouched")
        self.assertEqual(rank[3:],
                         ('employee_field', 'contract_field', 'bank_account'))

    def test_03e_the_record_tier_sits_between_excel_and_the_component(self):
        cfg = self._config('J10 Plan')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        self.bonus.is_contract_component = True
        m = self._map_field(cfg, self.bonus, 'hr.contract', 'name')
        batch = self._batch(cfg)
        plan = batch._declared_source_plan(self.bonus, mapping=m)
        self.assertEqual([p['kind'] for p in plan],
                         ['excel', 'contract_field', 'contract_component'])

    # =====================================================================
    # 6-9 — the walk takes the first that DELIVERED, and reads no further
    # =====================================================================
    def test_06_a_delivering_feed_wins_and_the_record_is_never_read(self):
        """Case 6. The assertion is that the read DID NOT HAPPEN, not that the
        value differs — a lazy tier that is merely outranked is still a query
        per component and still a fact the card would be wrong about."""
        cfg = self._config('J10 Six')
        self.bonus.set_source_binding('feed', 'Bonus')
        emp = self._employee(job_title='FROM THE RECORD')
        m = self._map_field(cfg, self.bonus, 'hr.employee', 'job_title')
        batch = self._batch(cfg, 'api_data_store')

        seen = []
        original = type(batch)._mapped_record_value

        def spy(self, mapping, contract=None, employee=None):
            seen.append(mapping.id)
            return original(self, mapping, contract=contract, employee=employee)

        self.patch(type(batch), '_mapped_record_value', spy)
        hits = batch._declared_source_walk(
            self.bonus, self._blobs(batch, {'Bonus': 900}), mapping=m,
            employee=emp)
        self.assertEqual(hits[0]['value'], 900)
        self.assertEqual(hits[0]['kind'], 'feed')
        self.assertEqual(seen, [], "the record was read for a component whose "
                                  "feed had already answered")

    def test_07_a_blank_feed_falls_through_to_the_record_field(self):
        cfg = self._config('J10 Seven')
        self.bonus.set_source_binding('feed', 'Bonus')
        emp = self._employee(job_title='FROM THE RECORD')
        m = self._map_field(cfg, self.bonus, 'hr.employee', 'job_title')
        batch = self._batch(cfg, 'api_data_store')
        hits = batch._declared_source_walk(
            self.bonus, self._blobs(batch, {'Bonus': '   '}), mapping=m,
            employee=emp)
        self.assertEqual([h['kind'] for h in hits], ['employee_field'])
        self.assertEqual(hits[0]['value'], 'FROM THE RECORD')
        self.assertEqual(hits[0]['tier'], 'record')

    def test_07b_the_resolver_reports_the_skipped_side_through_ignored(self):
        """The same fall-through in the resolver, where `fell_back` and the
        skipped side are the owner's standing rule: the unused source is
        REPORTED, never silently discarded."""
        cfg = self._config('J10 SevenB')
        self.bonus.set_source_binding('feed', 'Bonus')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        batch = self._batch(cfg, 'excel')
        self._reset()
        prov = {}
        vals = batch._transform_data_to_formula_inputs(
            {'Bonus Col': 500}, provenance=prov, topup_data={'Bonus': '  '})
        self.assertEqual(vals['SITEBONUS'], 500.0)
        self.assertEqual(prov['SITEBONUS']['src'], 'excel')
        self.assertTrue(prov['SITEBONUS']['fell_back'])

    def test_08_blank_feed_and_blank_record_reach_the_contract_component(self):
        cfg = self._config('J10 Eight')
        self.bonus.set_source_binding('feed', 'Bonus')
        self.bonus.is_contract_component = True
        m = self._map_field(cfg, self.bonus, 'hr.employee', 'job_title')
        emp = self._employee()          # job title empty
        batch = self._batch(cfg, 'api_data_store')
        hits = batch._declared_source_walk(
            self.bonus, self._blobs(batch, {}), mapping=m, employee=emp,
            component_amounts={'sitebonus': 1500.0})
        self.assertEqual([h['kind'] for h in hits], ['contract_component'])
        self.assertEqual(hits[0]['value'], 1500.0)
        # and blank again is nothing at all, which is a default further down
        hits = batch._declared_source_walk(
            self.bonus, self._blobs(batch, {}), mapping=m, employee=emp,
            component_amounts={})
        self.assertEqual(hits, [])

    def test_09_a_record_holding_zero_or_false_WINS(self):
        """MJ15, one rung further down. `0` and `False` are values; only `None`
        or whitespace is silence. A tier consulted below a real zero would be
        the numeric-zero branch this programme has refused three times."""
        cfg = self._config('J10 Nine')
        self.bonus.set_source_binding('feed', 'Bonus')
        self.bonus.is_contract_component = True
        m = self._map_field(cfg, self.bonus, 'hr.contract', 'wage')
        emp = self._employee()
        contract = self.env['hr.contract'].create({
            'name': 'J10 C', 'employee_id': emp.id, 'wage': 0.0,
            'state': 'open'})
        batch = self._batch(cfg, 'api_data_store')
        hits = batch._declared_source_walk(
            self.bonus, self._blobs(batch, {}), mapping=m, contract=contract,
            employee=emp, component_amounts={'sitebonus': 999.0})
        self.assertEqual(hits[0]['kind'], 'contract_field')
        self.assertEqual(hits[0]['value'], 0.0)
        self.assertEqual(len(hits), 1,
                         "the tier below a real zero must not be consulted")
        # and a boolean False, which `_blob_is_empty` must not confuse with None
        self.assertFalse(self.Batch._blob_is_empty(False))
        self.assertFalse(self.Batch._blob_is_empty(0))
        self.assertTrue(self.Batch._blob_is_empty(None))
        self.assertTrue(self.Batch._blob_is_empty('   '))

    # =====================================================================
    # 10-12 — the writeback follows the order, and declines a self-assign
    # =====================================================================
    def test_10_the_contract_component_is_written_with_the_FEED_value(self):
        """Case 10, and the whole of request (a). A dual-blob run with a value
        on both sides writes the winner — the same number the payslip reads —
        where before this phase the writeback read the primary blob by name and
        could not see the feed at all."""
        cfg = self._config('J10 Ten')
        self.bonus.set_source_binding('feed', 'Bonus')
        self.bonus.set_source_binding('excel', 'Site Bonus')
        self.bonus.is_contract_component = True
        batch = self._batch(cfg, 'excel')       # excel primary, feed top-up
        emp = self._employee()
        contract = self.env['hr.contract'].create({
            'name': 'J10 C10', 'employee_id': emp.id, 'wage': 1.0,
            'state': 'open'})

        line = self.env['hr.payroll.import.line'].create({
            'batch_id': batch.id, 'employee_id': emp.id,
            'raw_data_json': '{"Site Bonus": 100}',
            'raw_data_topup_json': '{"Bonus": 750}',
        })
        batch._sync_contract_components(line, contract)
        amounts = batch._contract_component_amounts(contract)
        self.assertEqual(amounts.get('sitebonus'), 750.0,
                         "the feed outranks the spreadsheet and the contract "
                         "must carry the number the payslip will read")

        # and the payslip agrees, which is the point of one shared function
        vals = batch._transform_data_to_formula_inputs(
            line.get_raw_data(), contract=contract, employee=emp,
            topup_data=line.get_topup_data())
        self.assertEqual(vals['SITEBONUS'], 750.0)

    def test_11_a_contract_field_winner_is_not_rewritten(self):
        """Case 11. `write_date` is the assertion: the record already holds it,
        and a self-assign dirties an audit trail for no reader's benefit."""
        cfg = self._config('J10 Eleven')
        self.bonus.set_source_binding('feed', 'Bonus')
        m = self._map_field(cfg, self.bonus, 'hr.contract', 'name')
        emp = self._employee()
        contract = self.env['hr.contract'].create({
            'name': 'ALREADY ON THE RECORD', 'employee_id': emp.id,
            'wage': 1.0, 'state': 'open'})
        self.env.flush_all()
        before = contract.write_date
        batch = self._batch(cfg, 'api_data_store')
        line = self.env['hr.payroll.import.line'].create({
            'batch_id': batch.id, 'employee_id': emp.id, 'raw_data_json': '{}'})
        # nothing in either payload: the contract field is the winner
        batch._update_contract_from_raw_data(contract, {}, line=line)
        self.env.flush_all()
        self.assertEqual(contract.name, 'ALREADY ON THE RECORD')
        self.assertEqual(contract.write_date, before,
                         "the winner came OFF this field; writing it back on "
                         "would be a self-assign")
        # the walk agrees about who won, which is why nothing was written
        hits = batch._declared_source_walk(
            self.bonus, self._blobs(batch, {}), mapping=m, contract=contract,
            employee=emp)
        self.assertEqual(hits[0]['kind'], 'contract_field')

    def test_12a_a_contract_component_winner_is_a_no_op(self):
        cfg = self._config('J10 TwelveA')
        self.bonus.set_source_binding('feed', 'Bonus')
        self.bonus.is_contract_component = True
        batch = self._batch(cfg, 'api_data_store')
        emp = self._employee()
        contract = self.env['hr.contract'].create({
            'name': 'J10 C12', 'employee_id': emp.id, 'wage': 1.0,
            'state': 'open'})
        line = self.env['hr.payroll.import.line'].create({
            'batch_id': batch.id, 'employee_id': emp.id, 'raw_data_json': '{}'})
        # seed the component, then re-sync with an empty payload
        batch._sync_contract_components(line, contract)
        seeded = self.env['hr.contract.advantage'].search(
            [('contract_id', '=', contract.id)])
        for adv in seeded:
            adv.amount = 4321.0
        self.env.flush_all()
        stamps = {a.id: a.write_date for a in seeded}
        contract.invalidate_recordset()
        batch._sync_contract_components(line, contract)
        self.env.flush_all()
        for adv in seeded:
            self.assertEqual(adv.amount, 4321.0)
            self.assertEqual(adv.write_date, stamps[adv.id],
                             "the contract component was the winner; it must "
                             "not be written back onto itself")

    def test_12b_a_bank_account_winner_is_a_no_op(self):
        """Case 12, bank half. The read-back exists to answer "is this already
        on the record" and is NEVER used to supply a part the run did not
        carry: a row with a bank name and no account number is still not a
        bank account, and this method still declines it."""
        cfg = self._config('J10 TwelveB')
        acc = self.Rule.create({
            'config_id': cfg.id, 'name': 'Account No', 'code': 'ACCNO',
            'column_type': 'input', 'sequence': 2})
        acc.set_source_binding('feed', 'AccNo')
        m = self._map_bank(cfg, acc, 'acc_number')
        emp = self._employee('J10 Banked')
        partner = self.env['res.partner'].create({'name': 'J10 Banked'})
        emp.sudo().work_contact_id = partner.id
        account = self.env['res.partner.bank'].create({
            'acc_number': '111222333', 'partner_id': partner.id})
        emp.sudo().bank_account_ids = [(4, account.id)]
        self.env.flush_all()
        before = account.write_date
        batch = self._batch(cfg, 'api_data_store')
        line = self.env['hr.payroll.import.line'].create({
            'batch_id': batch.id, 'employee_id': emp.id, 'raw_data_json': '{}'})

        # the walk says the bank account is the winner …
        hits = batch._declared_source_walk(
            acc, self._blobs(batch, {}), mapping=m, employee=emp)
        self.assertEqual(hits[0]['kind'], 'bank_account')
        self.assertEqual(hits[0]['value'], '111222333')
        # … and the writeback therefore does nothing at all
        touched = batch._sync_employee_bank_account(emp, {}, line=line)
        self.env.flush_all()
        self.assertFalse(touched)
        self.assertEqual(account.write_date, before)
        self.assertEqual(
            self.env['res.partner.bank'].search_count(
                [('partner_id', '=', partner.id)]), 1,
            "no second account was minted out of a read-back")

    # =====================================================================
    # 13 — nothing declared and nothing delivered creates nothing
    # =====================================================================
    def test_13_nothing_declared_and_nothing_delivered_creates_nothing(self):
        cfg = self._config('J10 Thirteen')
        batch = self._batch(cfg)
        emp = self._employee()
        contract = self.env['hr.contract'].create({
            'name': 'J10 C13', 'employee_id': emp.id, 'wage': 1.0,
            'state': 'open'})
        line = self.env['hr.payroll.import.line'].create({
            'batch_id': batch.id, 'employee_id': emp.id, 'raw_data_json': '{}'})
        Template = self.env['hr.contract.advantage.template']
        Advantage = self.env['hr.contract.advantage']
        t0, a0 = Template.search_count([]), Advantage.search_count([])
        # SITEBONUS declares nothing and is not a contract component
        batch._sync_contract_components(line, contract)
        batch._update_employee_from_raw_data(emp, {}, line=line)
        batch._update_contract_from_raw_data(contract, {}, line=line)
        batch._sync_employee_bank_account(emp, {}, line=line)
        self.env.flush_all()
        self.assertEqual(Template.search_count([]), t0)
        self.assertEqual(Advantage.search_count([]), a0)

    def test_13b_a_flagged_component_creates_exactly_what_it_did_before(self):
        """The literal wording of case 13 is FALSE of the code that predates
        J10, and it is worth saying so rather than smoothing it over: a
        component flagged `is_contract_component` has ALWAYS had its template
        minted and a 0.0 advantage line created on the first sync, whether or
        not anything was delivered (`found=False` → `new_value = 0.0` →
        `create`). J10 must not change that in either direction — it must not
        start creating rows, and it must not stop creating them either, because
        a phase about display and precedence has no business quietly changing
        what an import produces. The assertion is therefore EQUALITY with the
        pre-J10 behaviour, which is one template and one line."""
        cfg = self._config('J10 ThirteenB')
        self.bonus.is_contract_component = True
        batch = self._batch(cfg)
        emp = self._employee()
        contract = self.env['hr.contract'].create({
            'name': 'J10 C13B', 'employee_id': emp.id, 'wage': 1.0,
            'state': 'open'})
        line = self.env['hr.payroll.import.line'].create({
            'batch_id': batch.id, 'employee_id': emp.id, 'raw_data_json': '{}'})
        Advantage = self.env['hr.contract.advantage']
        batch._sync_contract_components(line, contract)
        self.env.flush_all()
        rows = Advantage.search([('contract_id', '=', contract.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.amount, 0.0)

    # =====================================================================
    # 14 — ONE implementation of the order
    # =====================================================================
    def test_14a_every_writeback_seam_enters_the_shared_walk(self):
        """The instrument, in J9's `_multi_source_walk_entered` style: a source
        grep can be satisfied by a second copy that happens to spell the method
        name in a comment. A counter cannot."""
        cfg = self._config('J10 Fourteen')
        # One component per SEAM, because a component has at most one record
        # destination and a seam with no mapping of its shape returns before it
        # reaches the ladder at all — which would make this assertion pass for
        # the wrong reason.
        self.bonus.set_source_binding('excel', 'Bonus Col')
        self.bonus.is_contract_component = True
        self._map_field(cfg, self.bonus, 'hr.employee', 'job_title')
        con_rule = self.Rule.create({
            'config_id': cfg.id, 'name': 'Job Grade', 'code': 'J10GRADE',
            'column_type': 'input', 'sequence': 2})
        con_rule.set_source_binding('excel', 'Grade Col')
        self._map_field(cfg, con_rule, 'hr.contract', 'name')
        bank_rule = self.Rule.create({
            'config_id': cfg.id, 'name': 'Account No', 'code': 'J10ACCNO',
            'column_type': 'input', 'sequence': 3})
        bank_rule.set_source_binding('excel', 'Acc Col')
        self._map_bank(cfg, bank_rule, 'acc_number')
        batch = self._batch(cfg)
        emp = self._employee()
        contract = self.env['hr.contract'].create({
            'name': 'J10 C14', 'employee_id': emp.id, 'wage': 1.0,
            'state': 'open'})
        line = self.env['hr.payroll.import.line'].create({
            'batch_id': batch.id, 'employee_id': emp.id,
            'raw_data_json': '{"Bonus Col": 42, "Grade Col": "G4",'
                             ' "Acc Col": "999888777"}'})
        raw = line.get_raw_data()

        for label, call in (
                ('employee', lambda: batch._update_employee_from_raw_data(
                    emp, raw, line=line)),
                ('contract', lambda: batch._update_contract_from_raw_data(
                    contract, raw, line=line)),
                ('bank', lambda: batch._sync_employee_bank_account(
                    emp, raw, line=line)),
                ('components', lambda: batch._sync_contract_components(
                    line, contract))):
            self._reset()
            call()
            self.assertGreater(
                self._shared, 0,
                "the %s writeback resolved without entering the shared walk — "
                "it has grown a second implementation of the order" % label)

        # and the resolver enters the SAME function
        self._reset()
        batch._transform_data_to_formula_inputs(raw, contract=contract,
                                                employee=emp)
        self.assertGreater(self._shared, 0)

    def test_14b_no_writeback_seam_reads_the_blob_by_name_on_its_own(self):
        """The source half of the same claim, comments stripped (MJ47)."""
        src = _strip_py_comments(_src(
            'pb_hr_payroll_formula', 'models', 'payroll_import_batch.py'))
        for seam in ('_get_mapping_updates', '_sync_employee_bank_account',
                     '_sync_employee_contract_mirror_fields',
                     '_sync_contract_components'):
            body = src.split('def %s(' % seam, 1)[1].split('\n    def ', 1)[0]
            self.assertNotIn(
                '_get_rule_raw_value(', body,
                "%s still reads the primary blob by name; the declared order "
                "is decided in one place now" % seam)
            self.assertIn('_writeback_raw_value(', body)

    # =====================================================================
    # 15 — THE NEUTRALITY RAIL
    # =====================================================================
    def test_15a_a_single_source_run_never_enters_the_multi_walk(self):
        """J9's counter, re-quoted. J10 moved both of its branches into one
        function and the claim is unchanged: the multi walk is entered only by
        a component declaring two or more sources."""
        cfg = self._config('J10 Fifteen')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        batch = self._batch(cfg, 'excel')
        self._reset()
        prov = {}
        vals = batch._transform_data_to_formula_inputs(
            {'Bonus Col': 1250}, provenance=prov)
        self.assertEqual(vals['SITEBONUS'], 1250.0)
        self.assertEqual(prov['SITEBONUS'],
                         {'src': 'excel', 'key': 'Bonus Col', 'via': 'binding'})
        self.assertEqual(self.Batch._sourcing_multi_walk_counter(), 0)

    def test_15b_the_single_source_heuristic_and_its_provenance_survive(self):
        """S3's `side_o`, verbatim: the other blob is searched by the bound key
        FIRST and then by the component's natural candidates, and the fallback
        says so. This is the branch J10 moved, so it is the one at risk."""
        cfg = self._config('J10 FifteenB')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        batch = self._batch(cfg, 'excel')
        self._reset()
        prov = {}
        vals = batch._transform_data_to_formula_inputs(
            {}, provenance=prov, topup_data={'Site Bonus': 400})
        self.assertEqual(vals['SITEBONUS'], 400.0)
        self.assertEqual(prov['SITEBONUS'], {
            'src': 'feed', 'key': 'Site Bonus', 'via': 'fallback',
            'fell_back': True})
        self.assertEqual(self.Batch._sourcing_multi_walk_counter(), 0)

    def test_15c_a_single_source_reports_the_loser_as_ignored(self):
        """The other half of S3's shape: with one declared kind the other side
        is searched UNCONDITIONALLY, because the binding winning is not a
        reason to drop what the other payload said."""
        cfg = self._config('J10 FifteenC')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        batch = self._batch(cfg, 'excel')
        self._reset()
        prov = {}
        batch._transform_data_to_formula_inputs(
            {'Bonus Col': 10}, provenance=prov, topup_data={'Bonus Col': 20})
        entry = prov['SITEBONUS']
        self.assertEqual(entry['via'], 'binding')
        self.assertEqual(entry['ignored']['src'], 'feed')
        self.assertEqual(entry['ignored']['value'], 20)

    def test_15d_an_undeclared_component_writes_back_exactly_as_before(self):
        """The rail that matters most on the live databases: roughly forty
        mapped components declare NO source at all, and for them
        `_writeback_raw_value` is `_get_rule_raw_value` unchanged."""
        cfg = self._config('J10 FifteenD')
        self.assertFalse(self.bonus.source_ids)
        self._map_field(cfg, self.bonus, 'hr.employee', 'job_title')
        batch = self._batch(cfg)
        emp = self._employee()
        line = self.env['hr.payroll.import.line'].create({
            'batch_id': batch.id, 'employee_id': emp.id,
            'raw_data_json': '{"Site Bonus": "ABC123"}'})
        batch._update_employee_from_raw_data(emp, line.get_raw_data(), line=line)
        self.env.flush_all()
        self.assertEqual(emp.job_title, 'ABC123',
                         "a component that declares nothing must write back "
                         "the way it always did — the record tier is a rung of "
                         "the order, not a veto on the import")

    def test_15e_the_walk_agrees_with_get_rule_raw_value_for_one_blob(self):
        """Value-for-value neutrality on a single-payload run, which is every
        run on every live database today."""
        cfg = self._config('J10 FifteenE')
        self.bonus.set_source_binding('excel', 'Site Bonus')
        batch = self._batch(cfg)
        raw = {'Site Bonus': 77}
        old = batch._get_rule_raw_value(raw, self.bonus,
                                        allow_column_letter=False)
        new = batch._writeback_raw_value(raw, self.bonus,
                                         allow_column_letter=False)
        self.assertEqual(old, new)

    # =====================================================================
    # the record read has one implementation too
    # =====================================================================
    def test_16_the_resolver_and_the_writeback_read_the_record_identically(self):
        src = _strip_py_comments(_src(
            'pb_hr_payroll_formula', 'models', 'payroll_import_batch.py'))
        body = src.split('def get_mapped_input_value(rule):', 1)[1] \
                  .split('\n        # ', 1)[0]
        self.assertIn('_mapped_record_value(', body,
                      "rank 4 must be read through one function, or the card "
                      "and the payslip can disagree about what the record says")
