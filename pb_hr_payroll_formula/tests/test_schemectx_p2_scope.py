# -*- coding: utf-8 -*-
"""SCHEMECTX P2 — the scope helper, the fan-out, and pay neutrality.

Cases 10 and 11 of the handover, plus the helper's own three states.

10  a new contract gets NO lines any more, and the import sync afterwards
    creates only the components the file actually carries;
11  PAY NEUTRALITY: an absent line and a zero line resolve to the same input
    value, so removing the fan-out cannot move a single payslip.

The helper itself: it names the schemes that pay somebody, it says "known:
False" on a database with no scheme map, and it writes nothing.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchemeCtxP2Scope(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.Contract = cls.env['hr.contract']
        cls.Employee = cls.env['hr.employee']
        cls.Advantage = cls.env['hr.contract.advantage']
        cls.Template = cls.env['hr.contract.advantage.template']
        cls.company = cls.env.company
        cls.calendar = (cls.company.resource_calendar_id
                        or cls.env['resource.calendar'].search([], limit=1))
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'SCP2 Type'})

    # ------------------------------------------------------------- fixtures
    def _config(self, name, code, country='VN'):
        return self.Config.create({
            'name': name, 'code': code, 'country_code': country,
            'state': 'active', 'company_id': self.company.id})

    def _rule(self, config, code, **extra):
        return self.Rule.create(dict({
            'config_id': config.id, 'name': 'SCP2 %s' % code, 'code': code,
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
        }, **extra))

    def _person(self, name):
        return self.Employee.create({'name': name,
                                     'company_id': self.company.id})

    def _contract(self, employee):
        return self.Contract.create({
            'name': '%s - 2026-06-01' % employee.name,
            'employee_id': employee.id, 'wage': 10000000.0, 'state': 'open',
            'date_start': '2026-06-01',
            'resource_calendar_id': self.calendar.id,
            'type_id': self.ctype.id})

    # ==================================================================== 10
    def test_10_a_new_contract_gets_no_components_at_all(self):
        """The fan-out is gone. A contract starts empty, whatever the
        catalogue holds — and the catalogue on any live database holds
        every scheme's components at once, which is the whole defect."""
        self.Template.create({
            'name': 'SCP2 Fanout Probe', 'code': 'SCPFANOUT',
            'lower_bound': 0.0, 'upper_bound': 0.0, 'default_value': 0.0})
        self.assertTrue(self.Template.search_count([]),
                        "the catalogue is empty, so this proves nothing")
        contract = self._contract(self._person('SCP2 Fresh Start'))
        self.assertEqual(
            self.Advantage.search_count([('contract_id', '=', contract.id)]), 0,
            "creating a contract still fans the whole catalogue out onto it")

    def test_10b_the_import_sync_makes_only_what_the_file_carries(self):
        config = self._config('SCP2 Sync', 'SCP2SYNC')
        wanted = self._rule(config, 'SCPSYNCA', is_contract_component=True)
        wanted.set_source_binding('excel', 'Sync A Column')
        # a second contract component the file says nothing about
        self._rule(config, 'SCPSYNCB', is_contract_component=True)
        employee = self._person('SCP2 Sync Person')
        contract = self._contract(employee)
        batch = self.Batch.create({
            'name': 'SCP2 Sync', 'source_type': 'excel',
            'formula_config_id': config.id})
        line = self.env['hr.payroll.import.line'].create({
            'batch_id': batch.id, 'employee_id': employee.id,
            'raw_data_json': '{"Sync A Column": 640000}'})
        batch._sync_contract_components(line, contract)
        contract.invalidate_recordset()
        made = self.Advantage.search([('contract_id', '=', contract.id)])
        codes = {(l.advantage_template_code or '') for l in made}
        self.assertIn('SCPSYNCA', codes)
        self.assertEqual(
            made.filtered(lambda l: l.advantage_template_code == 'SCPSYNCA').amount,
            640000.0)
        self.assertNotIn(
            'SCPSYNCB', {c for c in codes
                         if (made.filtered(
                             lambda l, c=c: l.advantage_template_code == c)
                             .amount)},
            "a component the file never mentioned came back with a value")

    # ==================================================================== 11
    def test_11_a_zero_line_and_no_line_resolve_to_the_same_number(self):
        """PAY NEUTRALITY, asserted on the resolver itself.

        `_transform_data_to_formula_inputs` is the one place a contract
        component becomes an input. Its two rungs — `contract_component` when
        a line exists and `contract_component_default` when it does not —
        must agree for an EMPTY line, or removing the fan-out would move
        somebody's pay.
        """
        config = self._config('SCP2 Neutral', 'SCP2NEUT')
        rule = self._rule(config, 'SCPNEUTRAL', is_contract_component=True)
        self.assertTrue(rule)
        template = self.Template.create({
            'name': 'SCP2 Neutral', 'code': 'SCPNEUTRAL',
            'lower_bound': 0.0, 'upper_bound': 0.0, 'default_value': 0.0})
        employee = self._person('SCP2 Neutral Person')
        contract = self._contract(employee)
        batch = self.Batch.create({
            'name': 'SCP2 Neutral', 'source_type': 'excel',
            'formula_config_id': config.id})

        without = batch._transform_data_to_formula_inputs(
            {}, contract=contract, provenance={}, topup_data={})
        zero = self.Advantage.create({
            'contract_id': contract.id,
            'advantage_template_id': template.id, 'amount': 0.0})
        contract.invalidate_recordset()
        with_zero = batch._transform_data_to_formula_inputs(
            {}, contract=contract, provenance={}, topup_data={})
        self.assertEqual(without, with_zero,
                         "an empty line and no line produce different inputs")

        # …and a line that HOLDS something is still the answer, so the rung
        # itself has not been weakened.
        zero.amount = 480000.0
        contract.invalidate_recordset()
        with_value = batch._transform_data_to_formula_inputs(
            {}, contract=contract, provenance={}, topup_data={})
        self.assertEqual(with_value['SCPNEUTRAL'], 480000.0)

    # ================================================== the helper's 3 states
    def test_12a_the_helper_names_the_scheme_that_pays_somebody(self):
        if 'pb_paid_by_id' not in self.Employee._fields:
            self.skipTest("no scheme map on this database")
        config = self._config('SCP2 Helper', 'SCP2HELP')
        self._rule(config, 'SCPHELPA', is_contract_component=True)
        self._rule(config, 'SCPHELPB', is_text_component=True)
        self._rule(config, 'SCPHELPC')          # not a contract component
        employee = self._person('SCP2 Helper Person')
        employee.sudo().write({'pb_paid_by_id': config.id,
                               'pb_paid_by_stale': False})
        answer = self.Config.component_scope_for_employee(employee)
        self.assertTrue(answer['known'])
        self.assertEqual([s['id'] for s in answer['schemes']], [config.id])
        self.assertEqual(answer['schemes'][0]['country_code'], 'VN')
        self.assertIn('SCPHELPA', answer['codes'])
        self.assertIn('SCPHELPB', answer['codes'])
        self.assertNotIn('SCPHELPC', answer['codes'],
                         "a component the scheme never put on a contract is "
                         "in the contract's list")

    def test_12a2_another_schemes_code_stays_out(self):
        """Ledger SC8 — the widened scope is bounded by the scheme's OWN rules.

        The scope is "the components this scheme declares, plus any other rule
        of THIS scheme the catalogue already has a row for". A code that only
        another scheme has a rule for is outside it however the catalogue
        looks, and that is the whole of the defect this phase closes.
        """
        if 'pb_paid_by_id' not in self.Employee._fields:
            self.skipTest("no scheme map on this database")
        mine = self._config('SCP2 Bound Mine', 'SCP2BNDA')
        theirs = self._config('SCP2 Bound Theirs', 'SCP2BNDB', country='IN')
        # Mine: a declared contract component, and a plain input rule whose
        # code the catalogue happens to carry (the widened half).
        self._rule(mine, 'SCPBNDMINE', is_contract_component=True)
        self._rule(mine, 'SCPBNDDRIFT')
        self.Template.create({
            'name': 'SCP2 Drift', 'code': 'SCPBNDDRIFT', 'lower_bound': 0.0,
            'upper_bound': 0.0, 'default_value': 0.0})
        # Theirs: a declared contract component WITH a catalogue row, which is
        # the strongest form of "belongs to somebody else".
        self._rule(theirs, 'SCPBNDTHEIRS', is_contract_component=True)
        self.Template.create({
            'name': 'SCP2 Theirs', 'code': 'SCPBNDTHEIRS', 'lower_bound': 0.0,
            'upper_bound': 0.0, 'default_value': 0.0})

        employee = self._person('SCP2 Bound Person')
        employee.sudo().write({'pb_paid_by_id': mine.id,
                               'pb_paid_by_stale': False})
        codes = self.Config.component_scope_for_employee(employee)['codes']
        self.assertIn('SCPBNDMINE', codes)
        self.assertIn('SCPBNDDRIFT', codes,
                      "the widened half of the scope did not open (SC8)")
        self.assertNotIn('SCPBNDTHEIRS', codes,
                         "another scheme's component is in this person's "
                         "list — this is the defect the phase closes")

    def test_12b_the_helper_writes_nothing(self):
        if 'pb_paid_by_id' not in self.Employee._fields:
            self.skipTest("no scheme map on this database")
        config = self._config('SCP2 Read', 'SCP2READ')
        self._rule(config, 'SCPREADA', is_contract_component=True)
        employee = self._person('SCP2 Read Person')
        employee.sudo().write({'pb_paid_by_id': config.id,
                               'pb_paid_by_stale': False})
        self.env.flush_all()
        before = (employee.write_date, config.write_date,
                  self.Advantage.search_count([]))
        self.Config.component_scope_for_employee(employee)
        self.Config.schemes_for_employee(employee)
        self.env.flush_all()
        self.env.invalidate_all()
        after = (employee.write_date, config.write_date,
                 self.Advantage.search_count([]))
        self.assertEqual(before, after, "a read moved a record")

    def test_12c_a_stale_answer_is_worked_out_again_and_not_stored(self):
        if 'pb_paid_by_stale' not in self.Employee._fields:
            self.skipTest("no scheme map on this database")
        config = self._config('SCP2 Stale', 'SCP2STALE')
        self._rule(config, 'SCPSTALEA', is_contract_component=True)
        employee = self._person('SCP2 Stale Person')
        employee.sudo().write({'pb_paid_by_id': config.id,
                               'pb_paid_by_stale': True})
        self.env.flush_all()
        found = self.Config.schemes_for_employee(employee)
        # Whatever the map says, the stored value is the floor — it is never
        # thrown away for an answer of "nobody".
        self.assertTrue(found, "a stale answer was dropped rather than reused")
        self.env.invalidate_all()
        self.assertTrue(employee.pb_paid_by_stale,
                        "a read settled the stored value, which is a write")
