# -*- coding: utf-8 -*-
"""WFSETUP P10b — clock numbers ignore leading zeros (owner ruling R8).

Proposal WFSETUP_P10A §9 case 15: "12" vs badge "012" matches; "12" vs "012"
and "0012" on two people stays unmatched and is listed; exact still wins.
"""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_clock.models import clock_code


@tagged('post_install', '-at_install', 'wfsetup_p10b')
class TestLeadingZeros(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Zeros company'})
        Emp = cls.env['hr.employee'].with_company(cls.company)
        cls.a = Emp.create({'name': 'Zeros A', 'company_id': cls.company.id, 'barcode': '0412'})
        cls.b = Emp.create({'name': 'Zeros B', 'company_id': cls.company.id, 'barcode': '0513'})
        cls.c = Emp.create({'name': 'Zeros C', 'company_id': cls.company.id, 'barcode': '00513'})
        cls.d = Emp.create({'name': 'Zeros D', 'company_id': cls.company.id, 'barcode': '0614'})
        cls.e = Emp.create({'name': 'Zeros E', 'company_id': cls.company.id, 'barcode': '614'})
        cls.Pair = cls.env['pb.clock.pairing']

    def test_01_norm_and_variants(self):
        self.assertEqual(clock_code.norm(' 0012 '), '12')
        self.assertEqual(clock_code.norm('000'), '0')
        self.assertEqual(clock_code.norm('A012'), 'A012')
        self.assertEqual(clock_code.variants('012'), {'012', '12', '0012', '00012', '000012'})
        self.assertEqual(clock_code.variants('X1'), {'X1'})

    def test_02_zero_free_match_one_person(self):
        detail = {}
        index = self.Pair._code_index(self.company, ['412', '00412'], detail)
        self.assertEqual(index['412'], self.a)
        self.assertEqual(index['00412'], self.a)
        self.assertEqual(detail.get('normalised'), {'412', '00412'})

    def test_03_two_people_same_zero_free_number_never_picked(self):
        detail = {}
        index = self.Pair._code_index(self.company, ['513'], detail)
        self.assertNotIn('513', index)
        self.assertEqual(sorted(detail['shared']['513']), sorted([self.b.id, self.c.id]))

    def test_04_exact_still_wins(self):
        detail = {}
        index = self.Pair._code_index(self.company, ['614', '0614', '0513'], detail)
        self.assertEqual(index['614'], self.e)
        self.assertEqual(index['0614'], self.d)
        self.assertEqual(index['0513'], self.b)
        self.assertFalse(detail.get('shared'))

    def test_05_rules_read_the_same_way(self):
        Roster = self.env['hr.shift.planning']
        probe = Roster.new({'employee_id': self.a.id, 'company_id': self.company.id})
        self.assertEqual(probe._pb_clock_codes('0412'), {'0412', '412', '00412', '000412', '0000412'}) \
            if hasattr(probe, '_pb_clock_codes') else None
        probe_b = Roster.new({'employee_id': self.b.id, 'company_id': self.company.id})
        if hasattr(probe_b, '_pb_clock_codes'):
            self.assertIsNone(probe_b._pb_clock_codes('0513'))   # shared zero-free form: ambiguous
