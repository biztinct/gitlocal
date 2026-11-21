from datetime import date
from unittest.mock import patch
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'pb_leave_policy')
class TestPolicyYearOpening(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.policy = cls.env['pb.leave.policy.edition'].create({
            'name': 'Scheduled year test', 'code': 'SCHEDULED_YEAR_TEST',
            'company_id': cls.env.company.id, 'country_id': cls.env.ref('base.vn').id,
            'effective_from': '2030-01-01', 'source_reference': 'Test annual policy'})
        cls.env['pb.leave.policy.rule'].create({'edition_id': cls.policy.id, 'name': 'Annual',
            'category': 'annual', 'quantity': 20, 'counting': 'working', 'limit_period': 'year'})
        cls.policy.action_publish()
        cls.employee = cls.env['hr.employee'].create({'name': 'Scheduled year subject',
            'company_id': cls.env.company.id, 'pb_leave_policy_id': cls.policy.id,
            'pb_policy_full_time_confirmed': True})
        cls.leave_type = cls.env['hr.leave.type'].create({'name': 'Scheduled annual',
            'requires_allocation': True, 'allocation_validation_type': 'no_validation',
            'pb_policy_category': 'annual', 'company_id': cls.env.company.id})

    def _job(self):
        return self.env['pb.leave.policy.year.opening'].create({
            'employee_id': self.employee.id, 'edition_id': self.policy.id,
            'leave_type_id': self.leave_type.id, 'year': 2031,
            'employment_start': '2020-01-01', 'review_reference': 'Approved future opening'})

    def test_scheduled_opening_waits_then_posts_once(self):
        self.policy.post_annual_credit(self.employee.id, self.leave_type.id, 2030, '2020-01-01')
        job = self._job()
        job.action_schedule()
        with patch.object(fields.Date, 'today', return_value=date(2030, 12, 31)):
            job._cron_open_year()
        self.assertEqual(job.state, 'scheduled')
        with patch.object(fields.Date, 'today', return_value=date(2031, 1, 1)):
            job._cron_open_year()
            job._cron_open_year()
        self.assertEqual(job.state, 'done')
        posts = self.env['pb.leave.policy.posting'].search([('employee_id', '=', self.employee.id), ('year', '=', 2031)])
        self.assertEqual(len(posts), 2)
        self.assertEqual(sum(posts.mapped('days')), 28)

    def test_unreconciled_year_blocks_without_partial_annual_grant(self):
        job = self._job()
        job.action_schedule()
        with patch.object(fields.Date, 'today', return_value=date(2031, 1, 1)):
            job._cron_open_year()
        self.assertEqual(job.state, 'blocked')
        self.assertIn('reconciled', job.result)
        self.assertFalse(self.env['hr.leave.allocation'].search([('employee_id', '=', self.employee.id)]))
        with self.assertRaises(UserError):
            job.write({'employment_start': '2031-01-01'})
        with self.assertRaises(AccessError):
            job.write({'state': 'done'})
