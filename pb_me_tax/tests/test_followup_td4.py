# -*- coding: utf-8 -*-
"""WDGAP S2-F — owner ruling TD4: an empty dependants figure on the contract
is "nothing to compare", so no "does not match" note (numbered TD4.x in the
S2-F report)."""
from odoo.tests import tagged

from .common import TaxCase


@tagged('post_install', '-at_install', 'wdgap_s2f')
class TestS2fTd4(TaxCase):

    def setUp(self):
        super().setUp()
        self.contract = self.env['hr.contract'].sudo().create({
            'name': 'DEMO S2F TD4', 'employee_id': self.emp.id,
            'company_id': self.company.id, 'wage': 10_000_000.0,
            'state': 'open', 'date_start': '2026-01-01'})
        Template = self.env['hr.contract.advantage.template'].sudo()
        self.tpl = Template.search([('code', '=', 'VNREGISTER')], limit=1) or Template.create(
            {'name': 'Registered tax dependents', 'code': 'VNREGISTER',
             'lower_bound': 0, 'upper_bound': 20, 'default_value': 0})
        self.contract.advantages_ids.filtered(
            lambda a: a.advantage_template_id == self.tpl).unlink()

    def _line(self, **vals):
        return self.env['hr.contract.advantage'].sudo().create(dict(
            {'contract_id': self.contract.id, 'advantage_template_id': self.tpl.id}, **vals))

    def _confirmed(self, n):
        Dep = self.env['vietnam.employee.dependent'].sudo()
        for i in range(n):
            Dep.create({'employee_id': self.emp.id, 'name': 'DEMO Child %s' % i,
                        'relationship': 'child', 'status': 'eligible',
                        'effective_from': '2025-01-01'})
        self.emp.invalidate_recordset()

    def _note(self):
        self.emp.invalidate_recordset()
        return self.emp.with_user(self.hr).pb_vn_dependants_check

    def _is_null(self, line):
        line.flush_recordset()
        self.env.cr.execute('SELECT amount IS NULL FROM hr_contract_advantage WHERE id = %s',
                            [line.id])
        return self.env.cr.fetchone()[0]

    def test_td4_1_never_written_is_nothing_to_compare(self):
        line = self._line()            # created without a figure: the column stays empty
        self.assertTrue(self._is_null(line))
        self._confirmed(2)
        self.assertFalse(self._note(), 'an empty figure is nothing to compare')
        self.assertTrue(self._is_null(line), 'reading never writes the contract')

    def test_td4_2_zero_with_confirmed_dependants_counts_as_not_set(self):
        self._line(amount=0)
        self.assertFalse(self._note(), '0 and nobody confirmed: equal')
        self._confirmed(2)
        self.assertFalse(self._note(), '0 cannot be told from "not filled in": no note')

    def test_td4_3_equal_figures_no_note(self):
        self._line(amount=2)
        self._confirmed(2)
        self.assertFalse(self._note())

    def test_td4_4_a_real_figure_that_differs_shows_the_note(self):
        line = self._line(amount=3)
        self._confirmed(2)
        note = self._note()
        self.assertTrue(note)
        self.assertIn('2', note)
        self.assertIn('3', note)
        # a real figure with nobody confirmed also differs
        self.env['vietnam.employee.dependent'].sudo().search(
            [('employee_id', '=', self.emp.id)]).unlink()
        self.assertIn('3', self._note() or '')
        self.assertEqual(line.amount, 3, 'the contract is never changed')

    def test_td4_5_an_empty_first_code_falls_to_the_next_figure(self):
        self._line()                   # VNREGISTER present but never filled in
        Template = self.env['hr.contract.advantage.template'].sudo()
        deps = Template.search([('code', '=', 'DEPS')], limit=1) or Template.create(
            {'name': 'Number of Dependents', 'code': 'DEPS', 'lower_bound': 0, 'upper_bound': 20})
        self.env['hr.contract.advantage'].sudo().create(
            {'contract_id': self.contract.id, 'advantage_template_id': deps.id, 'amount': 1})
        self._confirmed(2)
        self.assertIn('1', self._note() or '')

    def test_td4_6_the_written_figure_after_an_empty_one(self):
        line = self._line()
        self._confirmed(1)
        self.assertFalse(self._note())
        line.amount = 3                # HR fills it in
        self.assertIn('3', self._note() or '')
        line.amount = 1
        self.assertFalse(self._note())
