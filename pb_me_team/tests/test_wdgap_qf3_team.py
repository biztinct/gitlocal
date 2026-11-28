# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WDGAP QF3 (handover case 12) — the manager sees the half day and the
papers; "left after this" is right for a kind that is not counted (R7)."""

import base64
from datetime import date, timedelta
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from .test_my_team import _staff

PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


@tagged('post_install', '-at_install', 'wdgap_qf3')
class TestWdgapQf3Team(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.boss, cls.boss_emp = _staff(cls.env, 'qf3_mt_boss', 'QF3 MT Boss')
        cls.staff, cls.staff_emp = _staff(cls.env, 'qf3_mt_staff', 'QF3 MT Ana')
        cls.staff_emp.write({'parent_id': cls.boss_emp.id,
                             'leave_manager_id': cls.boss.id})
        cls.env['hr.leave']._approval_seed_default(cls.env.company)
        cls.half = cls.env['hr.leave.type'].create({
            'name': 'QF3 MT Half', 'requires_allocation': False,
            'leave_validation_type': 'manager', 'request_unit': 'half_day',
            'company_id': cls.env.company.id})
        anchor = date.today() + timedelta(days=14)
        cls.mon = anchor - timedelta(days=anchor.weekday())

    def test_12a_files_with_tokens_and_the_half_day(self):
        leave = self.env['hr.leave'].with_user(self.staff).create({
            'employee_id': self.staff_emp.id,
            'holiday_status_id': self.half.id,
            'request_date_from': self.mon, 'request_date_to': self.mon,
            'request_date_from_period': 'pm', 'request_date_to_period': 'pm',
            'name': 'QF3'})
        self.env['ir.attachment'].sudo().create({
            'name': 'note.pdf', 'datas': base64.b64encode(PDF),
            'mimetype': 'application/pdf',
            'res_model': 'hr.leave', 'res_id': leave.id})
        request = leave.sudo().approval_request_id
        self.assertTrue(request, 'fixture: the leave went to the route')
        ctx = self.env['pb.me.team'].with_user(self.boss)._leave_context(
            self.boss_emp, request.id)
        self.assertEqual(ctx['period_label'], 'Half day, afternoon')
        self.assertEqual(ctx['days'], 0.5)
        self.assertEqual([f['name'] for f in ctx['files']], ['note.pdf'])
        self.assertIn('access_token=', ctx['files'][0]['url'])
        self.assertIsNone(ctx['balance_after'], 'a kind that is not counted')

    def test_12b_balance_after_skips_a_kind_that_is_not_counted(self):
        """R7: `requires_allocation` is a Boolean; the old `== 'no'` never
        matched, so the allocation maths ran for nothing."""
        leave = self.env['hr.leave'].sudo().create({
            'employee_id': self.staff_emp.id,
            'holiday_status_id': self.half.id,
            'request_date_from': self.mon + timedelta(days=1),
            'request_date_to': self.mon + timedelta(days=1), 'name': 'QF3'})
        Type = type(self.env['hr.leave.type'])
        with patch.object(Type, 'get_allocation_data',
                          side_effect=AssertionError('asked for nothing')):
            self.assertIsNone(self.env['pb.me.team']._balance_after(leave))
        # a counted kind still answers: 5 granted, this request 1 → 4 left
        counted = self.env['hr.leave.type'].create({
            'name': 'QF3 MT Counted', 'requires_allocation': True,
            'leave_validation_type': 'manager',
            'allocation_validation_type': 'hr',
            'company_id': self.env.company.id})
        alloc = self.env['hr.leave.allocation'].sudo().create({
            'name': 'QF3', 'employee_id': self.staff_emp.id,
            'holiday_status_id': counted.id, 'number_of_days': 5,
            'allocation_type': 'regular',
            'date_from': date.today() - timedelta(days=10)})
        alloc.action_approve()
        asked = self.env['hr.leave'].sudo().create({
            'employee_id': self.staff_emp.id, 'holiday_status_id': counted.id,
            'request_date_from': self.mon + timedelta(days=2),
            'request_date_to': self.mon + timedelta(days=2), 'name': 'QF3'})
        self.assertEqual(self.env['pb.me.team']._balance_after(asked), 4)
