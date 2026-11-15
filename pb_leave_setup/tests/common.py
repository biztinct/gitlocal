# -*- coding: utf-8 -*-
"""Shared fixture for WDGAP S5-A: a company, the people and the logins the
tests need, and helpers that make a kind of leave or a leave request."""
from datetime import date

from odoo.tests.common import TransactionCase

from odoo.addons.pb_timeoff.models.hr_leave_approval import ENGINE_APPLY


class LeaveSetupCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        ref = cls.env.ref

        def user(login, groups, **kw):
            return Users.create(dict({
                'name': login.split('@')[0].replace('.', ' ').title(),
                'login': login, 'email': login,
                'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [ref(g).id for g in groups])]}, **kw))

        # a tenant HR manager: HR manager rights, NOT a system administrator
        cls.hr_user = user('s5a.hr@example.invalid', ['base.group_user', 'hr.group_hr_manager'])
        cls.officer = user('s5a.officer@example.invalid',
                           ['base.group_user', 'hr_holidays.group_hr_holidays_user'])
        cls.plain = user('s5a.plain@example.invalid', ['base.group_user'])
        cls.portal_user = user('s5a.portal@example.invalid', ['base.group_portal'],
                               password='s5a-portal-Pass-1')
        Emp = cls.env['hr.employee']
        cls.emp_portal = Emp.create({
            'name': 'S5A Portal Person', 'user_id': cls.portal_user.id,
            'company_id': cls.company.id})
        if 'date_of_joining' in Emp._fields:
            cls.emp_portal.date_of_joining = date(2020, 1, 1)

    @classmethod
    def _emp(cls, name, joined=None, left=None, **kw):
        Emp = cls.env['hr.employee']
        emp = Emp.create(dict({'name': name, 'company_id': cls.company.id}, **kw))
        if joined and 'date_of_joining' in Emp._fields:
            emp.date_of_joining = joined
        if left:
            emp.departure_date = left
        return emp

    @classmethod
    def _kind(cls, name, **vals):
        Kind = cls.env['hr.leave.type'].sudo()
        steps = vals.pop('steps', [])
        base = {
            'name': name, 'company_id': cls.company.id, 'requires_allocation': True,
            'request_unit': 'day', 'leave_validation_type': 'hr',
            'allocation_validation_type': 'hr',
            'pb_pay_treatment': 'paid', 'pb_pay_funding': 'employer',
        }
        base.update(vals)
        if steps:
            base['pb_ls_step_ids'] = [(0, 0, {'after_years': y, 'extra_days': d}) for y, d in steps]
        kind = Kind.create(base)
        # every country: the kind is for everybody in the fixture company
        kind.write({'country_id': False, 'pb_policy_country_id': False})
        return kind

    def _leave(self, emp, kind, start, end, state='confirm'):
        leave = self.env['hr.leave'].sudo().with_context(
            leave_skip_state_check=True, mail_create_nolog=True).create({
                'employee_id': emp.id, 'holiday_status_id': kind.id,
                'request_date_from': start, 'request_date_to': end, 'name': 'S5A'})
        if state != leave.state:
            leave.with_context(**{ENGINE_APPLY: True}).write({'state': state})
        return leave

    def _alloc(self, emp, kind, days, date_from, date_to=False):
        alloc = self.env['hr.leave.allocation'].sudo().create({
            'name': 'S5A grant', 'employee_id': emp.id, 'holiday_status_id': kind.id,
            'number_of_days': days, 'allocation_type': 'regular',
            'date_from': date_from, 'date_to': date_to})
        if alloc.state != 'validate':
            alloc.action_approve()
        return alloc

    @property
    def Earn(self):
        return self.env['pb.leave.earning'].sudo()

    def _year_alloc(self, emp, kind, year):
        return self.Earn._year_allocation(kind, emp, year)
