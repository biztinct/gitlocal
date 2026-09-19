# -*- coding: utf-8 -*-
"""SCHEMECTX P2, case 15 — the assistant can answer "by payroll scheme".

Three things are asserted here, and the third is the one that matters:

* the words route — "payroll cost by payroll scheme" reaches the cost query
  grouped by scheme, "salary by country" reaches the salary query grouped by
  country, and a plain salary question still answers by department exactly as
  it did before;
* a filter narrows the answer to one scheme or one country;
* MIXED CURRENCIES ARE NEVER ADDED UP. A grouping whose people are paid in two
  currencies comes back as two rows, each carrying its own money, and the
  single overall average is withheld rather than quoted in no currency at all.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchemeCtxP2Grouping(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Query = cls.env['payroll.data.query']
        cls.Config = cls.env.get('hr.formula.config')
        cls.Employee = cls.env['hr.employee']
        cls.Contract = cls.env['hr.contract']
        cls.company = cls.env.company
        cls.calendar = (cls.company.resource_calendar_id
                        or cls.env['resource.calendar'].search([], limit=1))
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'AI2 Type'})

        cls.ready = bool(cls.Config is not None
                         and 'pb_paid_by_id' in cls.Employee._fields)
        if cls.ready:
            cls.vn = cls.Config.create({
                'name': 'AI2 Vietnam', 'code': 'AI2VN', 'country_code': 'VN',
                'state': 'active', 'company_id': cls.company.id})
            cls.ind = cls.Config.create({
                'name': 'AI2 India', 'code': 'AI2IN', 'country_code': 'IN',
                'state': 'active', 'company_id': cls.company.id})
            cls.p_vn = cls._person('AI2 Hanoi', cls.vn, 11000000.0)
            cls.p_in = cls._person('AI2 Pune', cls.ind, 90000.0)

    @classmethod
    def _person(cls, name, config, wage):
        employee = cls.Employee.create({'name': name,
                                        'company_id': cls.company.id})
        cls.Contract.create({
            'name': '%s - 2026-06-01' % name, 'employee_id': employee.id,
            'wage': wage, 'state': 'open', 'date_start': '2026-06-01',
            'resource_calendar_id': cls.calendar.id, 'type_id': cls.ctype.id})
        employee.sudo().write({'pb_paid_by_id': config.id,
                               'pb_paid_by_stale': False})
        return employee

    # ==================================================================== 15
    def test_15a_the_words_reach_the_right_grouping(self):
        self.assertEqual(self.Query._sc_group_by('salary by department', {}),
                         'department')
        self.assertEqual(
            self.Query._sc_group_by('payroll cost by payroll scheme', {}),
            'scheme')
        self.assertEqual(self.Query._sc_group_by('cost by country', {}),
                         'country')
        self.assertEqual(self.Query._sc_group_by('anything', {'pb_group_by': 'country'}),
                         'country')
        # the router itself, not just the helper
        answer = self.Query.query_for_message('payroll cost by payroll scheme')
        if not answer.get('access_refused'):
            self.assertEqual(answer.get('query_type'), 'payroll_cost_by_scheme')
        answer = self.Query.query_for_message('salary by name')
        if not answer.get('access_refused'):
            self.assertIn(answer.get('query_type'),
                          ('salary_by_department', 'individual_employees'),
                          "a plain salary question stopped answering by "
                          "department")

    def test_15b_two_currencies_are_two_rows_and_no_average(self):
        if not self.ready:
            self.skipTest("no formula engine or scheme map on this database")
        if self.vn.currency_id == self.ind.currency_id:
            self.skipTest("the two schemes pay in the same currency here")
        answer = self.Query._query_salary_data('salary by payroll scheme', {})
        if answer.get('access_refused'):
            self.skipTest("this user may not read contracts")
        self.assertEqual(answer['query_type'], 'salary_by_scheme')
        rows = {r['group']: r for r in answer['data']}
        self.assertIn('AI2 Vietnam', rows)
        self.assertIn('AI2 India', rows)
        self.assertNotEqual(rows['AI2 Vietnam']['currency_name'],
                            rows['AI2 India']['currency_name'],
                            "both schemes were reported in one currency")
        self.assertTrue(answer['mixed_currency'])
        self.assertEqual(answer['overall_average'], 0,
                         "one average was quoted across two currencies")
        for row in answer['data']:
            self.assertTrue(row['currency'], "a row carries no money sign")

    def test_15c_a_filter_narrows_to_one_scheme_and_one_country(self):
        if not self.ready:
            self.skipTest("no formula engine or scheme map on this database")
        answer = self.Query._query_salary_data(
            'salary by payroll scheme', {'scheme': self.ind.id})
        if answer.get('access_refused'):
            self.skipTest("this user may not read contracts")
        groups = {r['group'] for r in answer['data']}
        self.assertEqual(groups, {'AI2 India'},
                         "the scheme filter let other schemes through: %s"
                         % groups)

        answer = self.Query._query_salary_data('salary by country',
                                               {'country': 'IN'})
        groups = {r['group'] for r in answer['data']}
        self.assertTrue(groups)
        for group in groups:
            self.assertNotEqual(group, 'Vietnam',
                                "the country filter let Vietnam through")
