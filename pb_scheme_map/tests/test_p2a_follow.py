# -*- coding: utf-8 -*-
"""PSCHEME P2a E — the contract follows the pay scheme.

T11 a row of another country taking effect today -> the running contract's
    Country of work, its currency and the new scheme's usual answers; a row
    from a later day -> nothing until the daily job reaches that day, then
    the same; a change within one country -> the contract untouched;
    idempotent; editing the wage clears "check their pay amounts"; the
    dialog's cards say which contract currency they would bring
"""

from unittest.mock import patch

from odoo import fields
from odoo.tests.common import tagged

from .p2a_common import P2aCase


@tagged('post_install', '-at_install', 'pscheme', 'pscheme_p2a')
class TestP2aFollow(P2aCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.calendar = cls.company.resource_calendar_id or env['resource.calendar'].create(
            {'name': 'DEMO P2A Hours', 'company_id': cls.company.id})
        cls.kind = env['hr.contract.type'].search([], limit=1) or env[
            'hr.contract.type'].create({'name': 'DEMO P2A Kind'})
        # Singapore's scheme has a usual answer the contract should receive
        cls.usual = env['hr.formula.rule'].create({
            'config_id': cls.sg_end.id, 'name': 'DEMO P2A SG allowance',
            'code': 'DEMOP2ASGA', 'column_type': 'input', 'sequence': 1,
            'is_contract_component': True, 'default_value': 150.0})
        cls.Assign.create({'config_id': cls.vn_end.id, 'cycle_type': 'any',
                           'department_id': cls.team.id, 'company_id': cls.company.id})

    def person_with_contract(self, name):
        person = self._person(name, self.team, 'SG')
        contract = self.env['hr.contract'].create({
            'name': 'DEMO P2A contract %s' % name, 'employee_id': person.id,
            'company_id': self.company.id, 'wage': 5000.0, 'state': 'open',
            'date_start': '2020-01-01', 'resource_calendar_id': self.calendar.id,
            'type_id': self.kind.id, 'payroll_country': 'VN'})
        return person, contract

    def codes(self, contract):
        contract.invalidate_recordset()
        return set(contract.sudo().advantages_ids.mapped('advantage_template_id.code'))

    def test_t11_contract_follows(self):
        Board = self.board()
        # ---- effective today: country, currency, usual answers, the note
        ana, contract = self.person_with_contract('DEMO P2A Ana SG')
        self.assertEqual(contract.currency_id.name, 'VND')
        Board.person_set(ana.ids, self.sg_end.id, False, str(self.first))
        contract.invalidate_recordset()
        self.assertEqual(contract.payroll_country, 'SG')
        self.assertEqual(contract.currency_id.name, 'SGD')
        self.assertEqual(contract.wage, 5000.0)                 # never rewritten
        self.assertTrue(contract.pb_ps_check_amounts)
        self.assertIn('DEMOP2ASGA', self.codes(contract))
        panel = Board.person_scheme(ana.id)
        self.assertIn('SGD', panel['contract_note']['line'])
        self.assertEqual(panel['contract']['currency'], 'SGD')
        # idempotent: asking again changes nothing
        lines = len(contract.sudo().advantages_ids)
        Board._ps_follow(ana)
        self.assertEqual(len(contract.sudo().advantages_ids), lines)
        # editing the wage clears the note; so does "Got it"
        contract.wage = 5200.0
        self.assertFalse(contract.pb_ps_check_amounts)
        self.assertIsNone(Board.person_scheme(ana.id)['contract_note'])

        # ---- from a later day: nothing until the daily job reaches it
        budi, later = self.person_with_contract('DEMO P2A Budi SG')
        day = self.next_first
        Board.person_set(budi.ids, self.sg_end.id, False, str(day))
        later.invalidate_recordset()
        self.assertEqual(later.payroll_country, 'VN')
        self.assertNotIn('DEMOP2ASGA', self.codes(later))
        with patch.object(fields.Date, 'context_today', lambda *a, **k: day):
            self.env['pb.person.scheme']._cron_mark_boundaries()
        later.invalidate_recordset()
        self.assertEqual(later.payroll_country, 'SG')
        self.assertIn('DEMOP2ASGA', self.codes(later))
        Board.contract_note_dismiss(later.id)
        self.assertFalse(later.pb_ps_check_amounts)

        # ---- a change within one country: the contract is untouched
        chi, same = self.person_with_contract('DEMO P2A Chi VN')
        Board.person_set(chi.ids, self.vn_reg.id, False, str(self.first))
        same.invalidate_recordset()
        self.assertEqual((same.payroll_country, same.pb_ps_check_amounts), ('VN', False))

        # ---- the one-time fill never moves a contract
        dan, kept = self.person_with_contract('DEMO P2A Dan')
        out = Board.fill_apply(self.company.id, tick=[], picks={str(dan.id): self.sg_end.id},
                               employee_ids=dan.ids)
        self.assertTrue(out['applied'], out)
        kept.invalidate_recordset()
        self.assertEqual((kept.payroll_country, kept.pb_ps_check_amounts), ('VN', False))
        # the dialog's cards name the currency a contract would take
        cards = {c['id']: c for c in panel['choices'] + panel['others']}
        self.assertEqual(cards[self.sg_end.id]['contract_currency'], 'SGD')
        self.assertEqual(cards[self.vn_end.id]['contract_currency'], 'VND')
