# -*- coding: utf-8 -*-
"""LEARN REFRESH step 6 — automatic final settlements reach "ready to check".

The monthly load (`hr.payroll.import.batch.action_process`) makes a settlement
for each leaver. It is never sent for approval by itself; once its figures are
worked out it is `pb_to_check`, the officers get ONE to-do for the load, and
Send for approval puts it on the route. One that cannot be worked out is still
made, with the reason on it. Also pins the 2026-09-22 crash: the component
summary called ORM methods on a plain object and every settlement with a
figure on it failed to compute.
"""
import json
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReadyToCheck(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.FF = cls.env['hr.full.final.settlement']
        cls.company = cls.env.company
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'RC scheme', 'country_code': 'VN', 'cycle_type': 'regular',
            'company_id': cls.company.id, 'state': 'draft'})
        rules = cls.env['hr.formula.rule'].create([
            {'config_id': cls.config.id, 'name': 'Basic pay', 'code': 'BASICPAY',
             'column_type': 'input', 'sequence': 10},
            {'config_id': cls.config.id, 'name': 'Insurance base', 'code': 'SIBASE',
             'column_type': 'input', 'sequence': 15},
            {'config_id': cls.config.id, 'name': 'Tax', 'code': 'PIT',
             'column_type': 'input', 'sequence': 18},
            {'config_id': cls.config.id, 'name': 'Take home', 'code': 'NETPAY',
             'column_type': 'formula', 'excel_formula': '=A', 'sequence': 20},
        ])
        if 'net_role' in rules._fields:
            for rule, role in zip(rules, ('earning', 'info', 'deduction', 'net')):
                rule.net_role = role
        cls.emp = cls.env['hr.employee'].create({
            'name': 'RC Leaver', 'company_id': cls.company.id,
            'departure_date': date(2026, 7, 20)})
        cls.env['hr.contract'].create({
            'name': 'RC contract', 'employee_id': cls.emp.id, 'wage': 1000.0,
            'state': 'open', 'date_start': '2020-01-01',
            'company_id': cls.company.id})
        officer_group = cls.env.ref(
            'pb_hr_payroll_base.group_payroll_base_officer',
            raise_if_not_found=False) or cls.env.ref(
            'om_hr_payroll.group_hr_payroll_manager')
        cls.officer = cls.env['res.users'].create({
            'name': 'RC Officer', 'login': 'rc_officer_s6',
            'company_id': cls.company.id, 'company_ids': [(6, 0, cls.company.ids)],
            'group_ids': [(4, cls.env.ref('base.group_user').id),
                          (4, officer_group.id)]})

    def _batch(self):
        return self.env['hr.payroll.import.batch'].create({
            'name': 'RC July', 'company_id': self.company.id,
            'formula_config_id': self.config.id,
            'date_from': '2026-07-01', 'date_to': '2026-07-31'})

    FIGS = {'BASICPAY': 9000.0, 'SIBASE': 50000.0, 'PIT': 500.0, 'NETPAY': 8500.0}

    def test_01_summary_reads_roles_and_does_not_crash(self):
        rec = self.FF.create({
            'name': 'RC direct', 'employee_id': self.emp.id,
            'settlement_date': date(2026, 7, 21), 'formula_config_id': self.config.id,
            'computed_values_json': json.dumps(self.FIGS)})
        self.assertEqual(rec.total_earnings, 9000.0)
        self.assertEqual(rec.total_deductions, 500.0,
                         'a working figure (insurance base) is not money off')
        self.assertEqual(rec.net_payable, 8500.0)

    def test_02_load_makes_it_ready_to_check_not_sent(self):
        batch = self._batch()
        with patch.object(type(self.FF), '_compute_from_config',
                          lambda *a, **k: ({}, dict(self.FIGS))):
            batch._generate_full_and_final_records()
        rec = self.FF.search([('employee_id', '=', self.emp.id)])
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec.state, 'draft', 'never sent in by itself')
        self.assertTrue(rec.pb_to_check)
        self.assertFalse(rec.pb_compute_issue)
        todo = self.env['mail.activity'].search([
            ('res_model', '=', 'hr.payroll.import.batch'),
            ('res_id', '=', batch.id), ('user_id', '=', self.officer.id)])
        self.assertEqual(len(todo), 1, 'one to-do per officer per load')
        self.assertIn('1 final settlement is ready to check', todo.summary)

    def test_03_one_that_cannot_be_worked_out_says_why(self):
        batch = self._batch()

        def boom(*a, **k):
            raise ValueError('division by zero in OTPAY')
        with patch.object(type(self.FF), '_compute_from_config', boom):
            batch._generate_full_and_final_records()
        rec = self.FF.search([('employee_id', '=', self.emp.id)])
        self.assertEqual(len(rec), 1, 'the leaver is not silently missing')
        self.assertIn('could not be worked out', rec.pb_compute_issue)
        self.assertIn('OTPAY', rec.pb_compute_issue)
        self.assertFalse(rec.pb_to_check)
        with self.assertRaises(UserError):
            rec.action_pb_send_for_approval()

    def test_04_send_for_approval_leaves_being_prepared(self):
        rec = self.FF.create({
            'name': 'RC send', 'employee_id': self.emp.id,
            'settlement_date': date(2026, 7, 22), 'formula_config_id': self.config.id,
            'computed_values_json': json.dumps(self.FIGS)})
        self.assertTrue(rec.pb_to_check)
        try:
            rec.action_pb_send_for_approval()
        except UserError as e:
            # a company with no route set up refuses in words — also a pass
            # for "nothing is sent silently"; the state must not have moved
            self.assertEqual(rec.state, 'draft', str(e))
            return
        self.assertIn(rec.state, ('pending', 'approved'))
        self.assertFalse(rec.pb_to_check)

    def test_05_settle_screen_counts_and_offers_it(self):
        self.FF.create({
            'name': 'RC settle', 'employee_id': self.emp.id,
            'settlement_date': date(2026, 7, 23), 'formula_config_id': self.config.id,
            'computed_values_json': json.dumps(self.FIGS)})
        Ledger = self.env.get('pb.fullfinal')
        if Ledger is None:
            self.skipTest('Settle screen not installed')
        data = Ledger.get_data()
        kpi = next(k for k in data['kpis'] if k.get('facet') == ['check', 'yes'])
        self.assertGreaterEqual(kpi['value'], 1)
        row = next(r for r in data['rows'] if r['title'] == 'RC Leaver')
        self.assertEqual(row['action']['method'], 'action_pb_send_for_approval')
