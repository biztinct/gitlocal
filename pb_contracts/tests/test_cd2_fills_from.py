# -*- coding: utf-8 -*-
"""CD-2 — "where does this number actually come from?", case by case.

Eight numbered cases, and the numbers are the handover's. A live contract
already carries every component template, and on a tenant whose numbers arrive
per pay run every one of those amounts is genuinely zero. A grid of twenty-one
zeroes reads as a broken screen and is not one, so each row now says where it is
really filled from: `fills_from` is on every row and is one of five values (1),
a connected-system key reads as the connected system (2), a spreadsheet column
as a pay data file (3), a record destination as held on the contract (4), a
component no scheme knows about as fed by nothing (5), the SCHEME's own source
order decides the winner rather than a ladder written here (6), the explainer
sentence appears exactly when the contract itself holds nothing (7), and the
whole answer costs a bounded number of queries however many rows there are (8).
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCd2FillsFrom(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Facade = cls.env['pb.contracts']
        cls.Contract = cls.env['hr.contract']
        cls.Employee = cls.env['hr.employee']
        cls.Advantage = cls.env['hr.contract.advantage']
        cls.Template = cls.env['hr.contract.advantage.template']
        cls.Rule = cls.env.get('hr.formula.rule')
        cls.Config = cls.env.get('hr.formula.config')
        cls.Mapping = cls.env.get('hr.payslip.import.mapping')
        cls.company = cls.env.company

        cls.calendar = (cls.company.resource_calendar_id
                        or cls.env['resource.calendar'].search(
                            [('company_id', 'in', (cls.company.id, False))],
                            limit=1))
        if not cls.calendar:
            cls.calendar = cls.env['resource.calendar'].create(
                {'name': 'CD2 Schedule', 'company_id': cls.company.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1)
        if not cls.ctype:
            cls.ctype = cls.env['hr.contract.type'].create({'name': 'CD2 Staff'})

        # Component codes are underscore-free and no code is a substring of
        # another — the converter contract, and it applies to fixtures too.
        cls.codes = {
            'feed':   'CDBFEED',
            'excel':  'CDBSHEET',
            'record': 'CDBRECORD',
            'silent': 'CDBSILENT',
            'both':   'CDBBOTH',
        }
        for code in cls.codes.values():
            cls.Template.create({'name': 'CD2 %s' % code, 'code': code,
                                 'lower_bound': 0.0, 'upper_bound': 0.0,
                                 'default_value': 0.0})

        # The templates go in BEFORE the contract: `hr.contract.create`
        # auto-creates one advantage line per template that exists at the time
        # (om_hr_payroll/models/hr_contract.py:118).
        cls.employee = cls.Employee.create(
            {'name': 'CD2 Drawer Person', 'company_id': cls.company.id})
        cls.contract = cls.Contract.create({
            'name': 'CD2 Drawer Person - 2026-06-01',
            'employee_id': cls.employee.id,
            'wage': 10000000.0, 'state': 'open', 'date_start': '2026-06-01',
            'resource_calendar_id': cls.calendar.id, 'type_id': cls.ctype.id,
        })

        cls.have_rules = bool(cls.Rule is not None and cls.Config is not None)
        cls.cfg = None
        if cls.have_rules:
            cls.cfg = cls.Config.create({
                'name': 'CD2 Drawer Scheme', 'code': 'CD2DRAWER',
                'country_code': 'VN', 'state': 'active',
                'company_id': cls.company.id})
            cls.r_feed = cls._rule(cls.codes['feed'])
            cls.r_feed.set_source_binding('feed', 'payload.cdbfeed')
            cls.r_excel = cls._rule(cls.codes['excel'])
            cls.r_excel.set_source_binding('excel', 'CD2 Sheet Column')
            # a record destination: a mapping onto a contract field, which is
            # the employee-field board's model and NOT the vendor feed's
            cls.r_record = cls._rule(cls.codes['record'])
            cls._map_onto_contract(cls.r_record)
            # declares nothing at all
            cls.r_silent = cls._rule(cls.codes['silent'])
            # declares BOTH a connected-system key and a record destination —
            # the case that proves the scheme's order is what decides
            cls.r_both = cls._rule(cls.codes['both'])
            cls.r_both.set_source_binding('feed', 'payload.cdbboth')
            cls._map_onto_contract(cls.r_both)

    # --------------------------------------------------------------- fixtures
    @classmethod
    def _rule(cls, code):
        return cls.Rule.create({
            'config_id': cls.cfg.id, 'name': 'CD2 %s' % code, 'code': code,
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0})

    @classmethod
    def _map_onto_contract(cls, rule):
        if cls.Mapping is None:
            return None
        model = cls.env['ir.model'].search([('model', '=', 'hr.contract')],
                                           limit=1)
        field = cls.env['ir.model.fields'].search(
            [('model', '=', 'hr.contract'), ('name', '=', 'costcenter')],
            limit=1)
        if not model or not field:
            return None
        return cls.Mapping.create({
            'destination_type': 'field', 'target_model_id': model.id,
            'target_field_id': field.id, 'salary_structure_id': cls.cfg.id,
            'component_id': rule.id})

    # ---------------------------------------------------------------- helpers
    def _rows(self, contract=None):
        payload = self.Facade.get_contract_360(
            (contract or self.contract).id)
        self.assertTrue(payload.get('ok'), payload.get('error'))
        return payload

    def _row(self, payload, code):
        for row in payload['components']['rows']:
            if row['code'] == code:
                return row
        return None

    def _bucket(self, code):
        return (self._row(self._rows(), code) or {}).get('fills_from')

    # ================================================================== case 1
    def test_01_every_row_says_where_it_is_filled_from(self):
        payload = self._rows()
        rows = payload['components']['rows']
        self.assertTrue(rows, "the fixture contract carries no components")
        allowed = {'records', 'api', 'excel', 'rule', 'none'}
        for row in rows:
            self.assertIn('fills_from', row, row.get('code'))
            self.assertIn(row['fills_from'], allowed, row.get('code'))
            self.assertTrue(row.get('fills_label'), row.get('code'))
            self.assertIn(row.get('fills_tone'),
                          {'indigo', 'cyan', 'green', 'slate', 'muted'})

    # ================================================================== case 2
    def test_02_a_connected_system_key_reads_as_the_connected_system(self):
        if not self.have_rules:
            self.skipTest("no formula module on this database")
        row = self._row(self._rows(), self.codes['feed'])
        self.assertIsNotNone(row)
        self.assertEqual(row['fills_from'], 'api')
        self.assertEqual(row['fills_label'], "From the connected system")
        self.assertEqual(row['fills_tone'], 'cyan')

    # ================================================================== case 3
    def test_03_a_spreadsheet_column_reads_as_a_pay_data_file(self):
        if not self.have_rules:
            self.skipTest("no formula module on this database")
        row = self._row(self._rows(), self.codes['excel'])
        self.assertIsNotNone(row)
        self.assertEqual(row['fills_from'], 'excel')
        self.assertEqual(row['fills_label'], "From a pay data file")

    # ================================================================== case 4
    def test_04_a_record_destination_reads_as_held_on_the_contract(self):
        if not self.have_rules or self.Mapping is None:
            self.skipTest("no record mapping model on this database")
        row = self._row(self._rows(), self.codes['record'])
        self.assertIsNotNone(row)
        self.assertEqual(row['fills_from'], 'records')
        self.assertEqual(row['fills_label'], "Held on this contract")
        self.assertEqual(row['fills_tone'], 'indigo')

    # ================================================================== case 5
    def test_05_a_component_no_scheme_knows_still_renders(self):
        row = self._row(self._rows(), self.codes['silent'])
        self.assertIsNotNone(row)
        self.assertEqual(row['fills_from'], 'none')
        self.assertEqual(row['fills_label'], "Not fed by anything")
        # rail 10 — the row is complete, not a stub
        for key in ('id', 'code', 'name', 'value_type', 'amount', 'display',
                    'lower', 'upper', 'bounded', 'bounds_hint', 'value_kind',
                    'requires_new_contract', 'template_id', 'writable'):
            self.assertIn(key, row, key)

    # ================================================================== case 6
    def test_06_the_schemes_own_order_decides_the_winner(self):
        """The SC-3 pin. Nothing here knows a ladder — it asks the scheme."""
        if not self.have_rules or self.Mapping is None:
            self.skipTest("no formula module on this database")
        self.cfg.write({'source_priority': 'api,excel,records'})
        self.assertEqual(self._bucket(self.codes['both']), 'api')
        self.cfg.write({'source_priority': 'records,api,excel'})
        self.assertEqual(self._bucket(self.codes['both']), 'records')
        # and a lane switched OFF is not read at all
        self.cfg.write({'source_priority': 'api,excel,records',
                        'source_api_enabled': False})
        self.assertEqual(self._bucket(self.codes['both']), 'records')
        self.cfg.write({'source_api_enabled': True})

    # ================================================================== case 7
    def test_07_the_explainer_appears_only_when_nothing_is_stored(self):
        if not self.have_rules:
            self.skipTest("no formula module on this database")
        # A live database already holds component templates of its own, and
        # `hr.contract.create` puts one line per template on every new
        # contract — so this case works on a contract pruned down to the
        # fixture's own components, or it would be testing the tenant's data
        # instead of the sentence.
        # a person of their own: `hr.contract._check_current_contract` refuses
        # a second running contract over the same dates
        other = self.Employee.create({'name': 'CD2 Explainer Person',
                                      'company_id': self.company.id})
        contract = self.Contract.create({
            'name': 'CD2 Explainer - 2026-06-01',
            'employee_id': other.id, 'wage': 10000000.0,
            'state': 'open', 'date_start': '2026-06-01',
            'resource_calendar_id': self.calendar.id, 'type_id': self.ctype.id,
        })
        keep = {self.codes['feed'], self.codes['excel'], self.codes['silent'],
                self.codes['both']}
        lines = self.Advantage.search([('contract_id', '=', contract.id)])
        lines.filtered(
            lambda l: (l.advantage_template_code or '') not in keep).unlink()
        self.Advantage.search([('contract_id', '=', contract.id)]).write(
            {'amount': 0.0})
        # the connected system is the dominant source of what is left
        self.cfg.write({'source_priority': 'api,excel,records'})

        payload = self._rows(contract)
        explainer = payload['components']['explainer']
        self.assertTrue(
            explainer, "no sentence above a grid of zeroes: %s"
            % [(r['code'], r['fills_from'], r['amount'])
               for r in payload['components']['rows']])
        self.assertIn("Nothing is stored on the contract itself", explainer)
        self.assertIn("the connected system", explainer)
        self.assertNotIn('_', explainer)
        self.assertNotIn('odoo', explainer.lower())

        # A records-held MINORITY softens the wording rather than silencing it
        # (abm contract 1051 is exactly this shape: one row of twenty-one).
        self.Advantage.create({
            'contract_id': contract.id,
            'advantage_template_id': self.Template.search(
                [('code', '=', self.codes['record'])], limit=1).id})
        softened = self._rows(contract)['components']['explainer']
        self.assertTrue(softened)
        self.assertIn("Most of the components below", softened)

        # …and it goes away the moment the contract genuinely holds a value.
        line = self.Advantage.search(
            [('contract_id', '=', contract.id),
             ('advantage_template_code', '=', self.codes['feed'])], limit=1)
        line.write({'amount': 1500000.0})
        self.assertFalse(self._rows(contract)['components']['explainer'])

    # ================================================================== case 8
    def test_08_the_answer_costs_a_bounded_number_of_queries(self):
        """Twenty-one rows must not cost forty-two queries (§2.1.6)."""
        if not self.have_rules:
            self.skipTest("no formula module on this database")
        codes = list(self.codes.values())
        rules_small = self.Facade._cd_rule_by_code(codes[:2],
                                                   company=self.company)
        rules_big = self.Facade._cd_rule_by_code(codes, company=self.company)
        self.assertTrue(rules_big)

        def cost(rules):
            self.env.invalidate_all()
            before = self.env.cr.sql_log_count
            self.Facade._cd_fills(rules)
            return self.env.cr.sql_log_count - before

        small = cost(rules_small)
        big = cost(rules_big)
        # constant work, not work per row: more than twice the rows must not
        # cost meaningfully more queries
        self.assertLessEqual(big, small + 2,
                             "the source lookup scales with the row count: "
                             "%s queries for 2 rows, %s for %s"
                             % (small, big, len(rules_big)))
        self.assertLessEqual(big, 20, "%s queries is not a bounded budget" % big)
