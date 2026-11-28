# -*- coding: utf-8 -*-
"""PDR P3 F2 — the pay package never counts a yes/no or worded answer as pay.

`_lines_from_contract` used to turn every non-zero contract component into an
earning line, so "BPJS TK covered = 1" became an earning of 1 and "Tax
allowance mode = 2" an earning of 2. The scheme rule for each component is now
found exactly as the contract panel finds it, and a rule with words or with a
value type other than money is skipped. A component with no rule keeps
today's behaviour.
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'pdr_p3')
class TestPdrP3PackageAnswers(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Comp = cls.env['pb.employee.comp']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Template = cls.env['hr.contract.advantage.template']
        cls.Advantage = cls.env['hr.contract.advantage']
        cls.company = cls.env.company
        cls.cfg = cls.env['hr.formula.config'].create({
            'name': 'PDR P3 package scheme', 'code': 'PDRP3PKG',
            'country_code': 'ID', 'state': 'active',
            'company_id': cls.company.id})
        # A draft scheme of the same company that claims the money code has
        # words: the live scheme must win, exactly as on the contract panel.
        cls.cfg_draft = cls.env['hr.formula.config'].create({
            'name': 'PDR P3 package draft', 'code': 'PDRP3PKGDRAFT',
            'country_code': 'ID', 'state': 'draft',
            'company_id': cls.company.id})

        cls._rule(cls.cfg, 'P3FLAG', 'P3 BPJS covered', 'integer', '0=No;1=Yes')
        cls._rule(cls.cfg, 'P3MODE', 'P3 Tax allowance mode', 'money',
                  '0=None;1=Insurance tax;2=All tax')
        cls._rule(cls.cfg, 'P3DAYS', 'P3 Leave days', 'quantity', False)
        cls._rule(cls.cfg, 'P3RATE', 'P3 Overtime rate', 'rate', False)
        cls._rule(cls.cfg, 'P3ALLOW', 'P3 Transport allowance', 'money', False)
        cls._rule(cls.cfg_draft, 'P3ALLOW', 'P3 Transport (draft)', 'integer',
                  '0=No;1=Yes')

        cls.templates = {}
        for code in ('P3FLAG', 'P3MODE', 'P3DAYS', 'P3RATE', 'P3ALLOW',
                     'P3NORULE'):
            cls.templates[code] = cls.Template.create({
                'name': 'Tmpl %s' % code, 'code': code, 'lower_bound': 0.0,
                'upper_bound': 0.0, 'default_value': 0.0})

        cls.calendar = (cls.company.resource_calendar_id
                        or cls.env['resource.calendar'].search([], limit=1))
        cls.employee = cls.env['hr.employee'].create(
            {'name': 'PDR P3 Package Person', 'company_id': cls.company.id})
        cls.contract = cls._contract(cls.employee, 9000000.0, {
            'P3FLAG': 1.0, 'P3MODE': 2.0, 'P3DAYS': 12.0, 'P3RATE': 1.5,
            'P3ALLOW': 750000.0, 'P3NORULE': 333.0})

    @classmethod
    def _rule(cls, cfg, code, name, kind, labels):
        vals = {'config_id': cfg.id, 'name': name, 'code': code,
                'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
                'is_contract_component': True, 'value_kind': kind}
        if labels:
            vals['value_labels'] = labels
        return cls.Rule.create(vals)

    @classmethod
    def _contract(cls, employee, wage, amounts):
        contract = cls.env['hr.contract'].create({
            'name': '%s - 2026-06-01' % employee.name,
            'employee_id': employee.id, 'wage': wage, 'state': 'open',
            'date_start': '2026-06-01', 'company_id': cls.company.id,
            'resource_calendar_id': cls.calendar.id})
        # Only the lines this test lays down (nothing else seeds a contract
        # with the catalogue any more, SCHEMECTX P2).
        contract.advantages_ids.unlink()
        for code, amount in amounts.items():
            cls.Advantage.create({
                'contract_id': contract.id,
                'advantage_template_id': cls.templates[code].id,
                'amount': amount})
        return contract

    def _package(self, employee):
        return self.Comp.create({'employee_id': employee.id,
                                 'effective_date': '2026-06-15'})

    def _names(self, contract, employee):
        vals = self._package(employee)._lines_from_contract(contract)
        return {v['name']: v for v in vals}

    def test_p3_f2_flag_and_worded_components_are_skipped(self):
        names = self._names(self.contract, self.employee)
        self.assertNotIn('Tmpl P3FLAG', names, 'a Yes / No answer became pay')
        self.assertNotIn('Tmpl P3MODE', names,
                         'a worded answer became pay, although its value '
                         'type says money')

    def test_p3_f2_counts_and_rates_are_skipped(self):
        names = self._names(self.contract, self.employee)
        self.assertNotIn('Tmpl P3DAYS', names)
        self.assertNotIn('Tmpl P3RATE', names)

    def test_p3_f2_money_component_is_kept(self):
        names = self._names(self.contract, self.employee)
        self.assertIn('Tmpl P3ALLOW', names,
                      "money was dropped because a draft scheme's rule for "
                      "the same code has words")
        line = names['Tmpl P3ALLOW']
        self.assertEqual(line['kind'], 'earning')
        self.assertEqual(line['amount'], 750000.0)
        self.assertIn('Base salary', names)

    def test_p3_f2_component_without_a_rule_is_kept(self):
        names = self._names(self.contract, self.employee)
        self.assertIn('Tmpl P3NORULE', names)
        self.assertEqual(names['Tmpl P3NORULE']['amount'], 333.0)
        self.assertEqual(len(names), 3)   # wage + money + no-rule

    def test_p3_f2_nothing_left_message_only_when_nothing_is_left(self):
        # wage 0 and only answers: the old message still fires
        only_answers = self.env['hr.employee'].create(
            {'name': 'PDR P3 Answers Only', 'company_id': self.company.id})
        self._contract(only_answers, 0.0, {'P3FLAG': 1.0, 'P3MODE': 2.0})
        package = self._package(only_answers)
        with self.assertRaisesRegex(UserError, 'carries no wage and no components'):
            package.action_bootstrap()
        # wage 0 but one money component: it builds, with that one line
        one_money = self.env['hr.employee'].create(
            {'name': 'PDR P3 One Money', 'company_id': self.company.id})
        self._contract(one_money, 0.0, {'P3FLAG': 1.0, 'P3ALLOW': 500.0})
        package = self._package(one_money)
        self.assertEqual(package.action_bootstrap(), 1)
        self.assertEqual(package.line_ids.mapped('name'), ['Tmpl P3ALLOW'])
