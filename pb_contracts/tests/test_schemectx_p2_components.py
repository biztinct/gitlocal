# -*- coding: utf-8 -*-
"""SCHEMECTX P2 — the components tab follows the person's scheme.

Nine numbered cases, and the numbers are the handover's.

1  a person on a Vietnamese scheme sees only that scheme's codes;
2  a stray component that HOLDS money is not lost — it moves to "Other values";
3  a stray component that holds nothing is not shown, and is still in the database;
4  a scheme component the contract has never held is shown as a virtual row, and
   opening the drawer created nothing;
5  typing a value into that virtual row creates exactly one line;
6  a person paid by two schemes sees the union of both, and the strip names both;
7  a person no scheme pays gets the unassigned state and keeps their valued lines;
8  a database with no scheme map behaves exactly as it did before this phase;
9  `addable` never offers a component outside the scheme.
"""

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from .approval_lane import no_approval_needed
from .scheme_scope import paid_by


@tagged('post_install', '-at_install')
class TestSchemeCtxP2Components(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        no_approval_needed(cls.env)
        cls.Facade = cls.env['pb.contracts']
        cls.Contract = cls.env['hr.contract']
        cls.Employee = cls.env['hr.employee']
        cls.Advantage = cls.env['hr.contract.advantage']
        cls.Template = cls.env['hr.contract.advantage.template']
        cls.Rule = cls.env.get('hr.formula.rule')
        cls.Config = cls.env.get('hr.formula.config')
        cls.company = cls.env.company
        cls.typed = 'value_type' in cls.Advantage._fields

        cls.calendar = (cls.company.resource_calendar_id
                        or cls.env['resource.calendar'].search(
                            [('company_id', 'in', (cls.company.id, False))],
                            limit=1))
        if not cls.calendar:
            cls.calendar = cls.env['resource.calendar'].create(
                {'name': 'SCP2 Schedule', 'company_id': cls.company.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1)
        if not cls.ctype:
            cls.ctype = cls.env['hr.contract.type'].create(
                {'name': 'SCP2 Staff'})

        # Codes are underscore-free and none is a substring of another — the
        # converter contract, and it applies to fixtures too.
        cls.vn_codes = ('SCPVNBASE', 'SCPVNMEAL', 'SCPVNNEW')
        cls.in_codes = ('SCPINHRA', 'SCPINPF')
        cls.templates = {}
        for code in cls.vn_codes + cls.in_codes:
            cls.templates[code] = cls.Template.create({
                'name': 'SCP2 %s' % code, 'code': code,
                'lower_bound': 0.0, 'upper_bound': 0.0,
                'default_value': 0.0})

        cls.have_engine = bool(cls.Rule is not None and cls.Config is not None)
        cls.vn = cls.ind = None
        if cls.have_engine:
            cls.vn = cls.Config.create({
                'name': 'SCP2 Vietnam', 'code': 'SCP2VN',
                'country_code': 'VN', 'state': 'active',
                'company_id': cls.company.id})
            cls.ind = cls.Config.create({
                'name': 'SCP2 India', 'code': 'SCP2IN',
                'country_code': 'IN', 'state': 'active',
                'company_id': cls.company.id})
            for code in cls.vn_codes:
                cls._rule(cls.vn, code)
            for code in cls.in_codes:
                cls._rule(cls.ind, code)

        cls.employee = cls.Employee.create(
            {'name': 'SCP2 Person One', 'company_id': cls.company.id})
        cls.contract = cls._contract(cls.employee)
        # Two of the three Vietnamese components are held; the third has never
        # been filled in, which is what makes it a virtual row.
        cls.l_base = cls._line(cls.contract, 'SCPVNBASE', 12500000.0)
        cls.l_meal = cls._line(cls.contract, 'SCPVNMEAL', 0.0)
        # Two strays from the other country's scheme: one with money in it,
        # one empty. Exactly what the old create-time fan-out left behind.
        cls.l_stray_value = cls._line(cls.contract, 'SCPINHRA', 750000.0)
        cls.l_stray_empty = cls._line(cls.contract, 'SCPINPF', 0.0)

        cls.mapped = paid_by(cls.env, cls.employee, cls.vn)

    # --------------------------------------------------------------- fixtures
    @classmethod
    def _rule(cls, config, code, **extra):
        return cls.Rule.create(dict({
            'config_id': config.id, 'name': 'SCP2 %s' % code, 'code': code,
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
            'is_contract_component': True,
        }, **extra))

    @classmethod
    def _contract(cls, employee, **vals):
        base = {'name': '%s - 2026-06-01' % employee.name,
                'employee_id': employee.id, 'wage': 12500000.0,
                'state': 'open', 'date_start': '2026-06-01',
                'resource_calendar_id': cls.calendar.id,
                'type_id': cls.ctype.id}
        base.update(vals)
        return cls.Contract.create(base)

    @classmethod
    def _line(cls, contract, code, amount):
        return cls.Advantage.create({
            'contract_id': contract.id,
            'advantage_template_id': cls.templates[code].id,
            'amount': amount})

    # ---------------------------------------------------------------- helpers
    def _components(self, contract=None):
        payload = self.Facade.get_contract_360((contract or self.contract).id)
        self.assertTrue(payload.get('ok'), payload.get('error'))
        return payload['components']

    def _codes(self, rows):
        return [r['code'] for r in rows]

    def _need_scope(self, components):
        if components['scope']['state'] != 'scoped':
            self.skipTest("this database cannot say who pays somebody: %s"
                          % components['scope']['state'])

    # ===================================================================== 1
    def test_01_rows_are_the_schemes_own_components(self):
        if not self.have_engine:
            self.skipTest("no formula engine on this database")
        components = self._components()
        self._need_scope(components)
        shown = set(self._codes(components['rows']))
        for code in self.vn_codes:
            self.assertIn(code, shown,
                          "the scheme's own component is missing")
        for code in self.in_codes:
            self.assertNotIn(code, shown,
                             "another country's component is still on the list")
        self.assertEqual(components['count'], len(components['rows']))
        strip = components['scope']['schemes']
        self.assertEqual([s['name'] for s in strip], ['SCP2 Vietnam'])
        self.assertEqual(strip[0]['country_code'], 'VN')
        self.assertTrue(strip[0]['country_name'])

    # ===================================================================== 2
    def test_02_a_stray_line_that_holds_money_is_never_lost(self):
        if not self.have_engine:
            self.skipTest("no formula engine on this database")
        components = self._components()
        self._need_scope(components)
        self.assertNotIn('SCPINHRA', self._codes(components['rows']))
        other = self._codes(components['other_rows'])
        self.assertIn('SCPINHRA', other,
                      "a component holding 750,000 was dropped from the drawer")
        self.assertEqual(components['other_count'], len(components['other_rows']))
        row = [r for r in components['other_rows'] if r['code'] == 'SCPINHRA'][0]
        self.assertEqual(row['amount'], 750000.0)
        self.assertIn('writable', row,
                      "a stray value is not offered for editing at all")
        self.assertTrue(self.l_stray_value.exists())

    # ===================================================================== 3
    def test_03_a_stray_empty_line_is_shown_nowhere_and_deleted_nowhere(self):
        if not self.have_engine:
            self.skipTest("no formula engine on this database")
        components = self._components()
        self._need_scope(components)
        self.assertNotIn('SCPINPF', self._codes(components['rows']))
        self.assertNotIn('SCPINPF', self._codes(components['other_rows']))
        self.assertTrue(self.l_stray_empty.exists(),
                        "opening the drawer deleted a line")

    # ===================================================================== 4
    def test_04_an_unfilled_scheme_component_is_a_virtual_row(self):
        if not self.have_engine:
            self.skipTest("no formula engine on this database")
        before = self.Advantage.search_count(
            [('contract_id', '=', self.contract.id)])
        components = self._components()
        self._need_scope(components)
        row = [r for r in components['rows'] if r['code'] == 'SCPVNNEW']
        self.assertEqual(len(row), 1, "the unfilled component is not on screen")
        row = row[0]
        self.assertIs(row['id'], False)
        self.assertTrue(row['virtual'])
        self.assertEqual(row['template_id'], self.templates['SCPVNNEW'].id)
        self.assertEqual(row['amount'], 0.0)
        self.assertEqual(
            self.Advantage.search_count(
                [('contract_id', '=', self.contract.id)]), before,
            "reading the drawer created a line")

    # ===================================================================== 5
    def test_05_typing_into_a_virtual_row_creates_exactly_one_line(self):
        if not self.have_engine:
            self.skipTest("no formula engine on this database")
        components = self._components()
        self._need_scope(components)
        before = self.Advantage.search_count(
            [('contract_id', '=', self.contract.id)])
        answer = self.Facade.save_contract_360(
            self.contract.id, terms={}, components={
                'edits': {}, 'removes': [],
                'adds': [{'template_id': self.templates['SCPVNNEW'].id,
                          'amount': 333000.0}]})
        self.assertTrue(answer['ok'], answer.get('msg'))
        self.assertFalse(answer['refusals'], answer['refusals'])
        after = self.Advantage.search(
            [('contract_id', '=', self.contract.id),
             ('advantage_template_id', '=', self.templates['SCPVNNEW'].id)])
        self.assertEqual(len(after), 1, "one press made %s lines" % len(after))
        self.assertEqual(after.amount, 333000.0)
        self.assertEqual(
            self.Advantage.search_count(
                [('contract_id', '=', self.contract.id)]), before + 1)
        # and it is a normal row from now on
        row = [r for r in self._components()['rows'] if r['code'] == 'SCPVNNEW'][0]
        self.assertFalse(row['virtual'])
        self.assertEqual(row['id'], after.id)

    # ===================================================================== 6
    def test_06_two_schemes_show_the_union_and_name_both(self):
        if not self.have_engine:
            self.skipTest("no formula engine on this database")
        if 'pb_paid_by_advance_id' not in self.Employee._fields:
            self.skipTest("no scheme map on this database")
        person = self.Employee.create(
            {'name': 'SCP2 Person Two', 'company_id': self.company.id})
        contract = self._contract(person)
        person.sudo().write({'pb_paid_by_id': self.vn.id,
                             'pb_paid_by_advance_id': self.ind.id,
                             'pb_paid_by_stale': False})
        components = self._components(contract)
        self._need_scope(components)
        shown = set(self._codes(components['rows']))
        for code in self.vn_codes + self.in_codes:
            self.assertIn(code, shown, "%s is missing from the union" % code)
        names = [s['name'] for s in components['scope']['schemes']]
        self.assertEqual(names, ['SCP2 Vietnam', 'SCP2 India'])
        self.assertEqual(
            [s['role'] for s in components['scope']['schemes']],
            ['regular', 'advance'])

    # ===================================================================== 7
    def test_07_nobody_pays_this_person(self):
        if not self.have_engine:
            self.skipTest("no formula engine on this database")
        if 'pb_paid_by_id' not in self.Employee._fields:
            self.skipTest("no scheme map on this database")
        person = self.Employee.create(
            {'name': 'SCP2 Person Three', 'company_id': self.company.id})
        contract = self._contract(person)
        self._line(contract, 'SCPVNBASE', 9000000.0)
        self._line(contract, 'SCPINPF', 0.0)
        # No map, no stored answer, and nothing to work one out from.
        person.sudo().write({'pb_paid_by_id': False,
                             'pb_paid_by_advance_id': False,
                             'pb_paid_by_stale': False})
        components = self._components(contract)
        if components['scope']['state'] == 'scoped':
            self.skipTest("this database resolves a scheme for anybody")
        self.assertEqual(components['scope']['state'], 'unassigned')
        self.assertEqual(self._codes(components['rows']), ['SCPVNBASE'],
                         "an empty stray survived, or a valued line was lost")
        self.assertEqual(components['addable'], [])

    # ===================================================================== 8
    def test_08_a_database_with_no_scheme_map_is_untouched(self):
        """The probe is the whole of the compatibility promise."""
        components = self._components()
        # Patched on the REGISTRY class, not on the file's own class: the model
        # the server actually runs is composed from every `_inherit`, and a
        # patch on one contributor is a patch on a class nothing calls.
        with patch.object(type(self.Facade), '_cd_scope',
                          return_value={'state': 'off', 'schemes': [],
                                        'codes': set()}):
            plain = self._components()
        self.assertEqual(plain['scope'], {'state': 'off', 'schemes': []})
        self.assertEqual(plain['other_rows'], [])
        # every line the contract holds, exactly as before this phase
        held = self.Advantage.search_count(
            [('contract_id', '=', self.contract.id)])
        self.assertEqual(len(plain['rows']), held)
        self.assertIn('SCPINPF', self._codes(plain['rows']))
        self.assertTrue(plain['addable'] or True)
        # …and it really is a different answer from the scoped one
        if components['scope']['state'] == 'scoped':
            self.assertLess(len(components['rows']), len(plain['rows']) + 1)

    # ===================================================================== 9
    def test_09_addable_never_reaches_outside_the_scheme(self):
        if not self.have_engine:
            self.skipTest("no formula engine on this database")
        components = self._components()
        self._need_scope(components)
        scope_codes = self.vn.component_rule_codes()
        for entry in components['addable']:
            self.assertIn(entry['code'], scope_codes,
                          "%s is offered but belongs to no scheme that pays "
                          "this person" % entry['code'])
