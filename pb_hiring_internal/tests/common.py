# -*- coding: utf-8 -*-
"""Shared people and roles for the S6-B internal-jobs tests (DEMO names)."""
from datetime import timedelta

from odoo import fields

PASSWORD = 'wdgap-s6b-internal-jobs-2026'


def make_world(cls, prefix, password=None):
    """An employee login (PORTAL user) with a manager who has an internal
    login and no hiring group, a recruiter, and open roles."""
    env = cls.env
    company = env.company
    Users = env['res.users'].with_context(no_reset_password=True)
    Emp = env['hr.employee']

    def user(login, name, groups):
        vals = {'name': name, 'login': login, 'email': '%s@example.com' % login,
                'company_id': company.id, 'company_ids': [(6, 0, [company.id])],
                'group_ids': [(6, 0, [env.ref(g).id for g in groups])]}
        if password:
            vals['password'] = password
        return Users.create(vals)

    cls.company = company
    cls.dept_now = env['hr.department'].create(
        {'name': 'DEMO S6B Finance', 'company_id': company.id})
    cls.dept_new = env['hr.department'].create(
        {'name': 'DEMO S6B Operations', 'company_id': company.id})

    cls.manager_user = user('%s_manager' % prefix, 'DEMO S6B Manager',
                            ['base.group_user'])
    cls.manager_user.sudo().write({'notification_type': 'inbox'})
    cls.manager = Emp.create({'name': 'DEMO S6B Manager', 'user_id': cls.manager_user.id,
                              'company_id': company.id,
                              'department_id': cls.dept_now.id})
    cls.share = user('%s_share' % prefix, 'DEMO S6B Mover', ['base.group_portal'])
    cls.mover = Emp.create({'name': 'DEMO S6B Mover', 'user_id': cls.share.id,
                            'company_id': company.id, 'parent_id': cls.manager.id,
                            'department_id': cls.dept_now.id,
                            'job_title': 'DEMO Accounts clerk',
                            'work_email': 'demo.s6b.mover@example.com'})
    cls.recruiter = user('%s_recruiter' % prefix, 'DEMO S6B Recruiter',
                         ['base.group_user', 'pb_hiring.group_hiring_user'])
    cls.boss = Emp.create({'name': 'DEMO S6B Ops Lead', 'company_id': company.id,
                           'department_id': cls.dept_new.id})

    def role(title, posting='both', **extra):
        job = env['hr.job'].create({'name': title, 'company_id': company.id,
                                    'department_id': cls.dept_new.id})
        vals = {
            'title': title, 'department_id': cls.dept_new.id,
            'company_id': company.id, 'reporting_manager_id': cls.boss.id,
            'recruiter_id': cls.recruiter.id, 'headcount': 1,
            'requirements': 'DEMO: able to run the night shift.',
            'job_id': job.id, 'state': 'open', 'request_state': 'agreed',
            'opened_on': fields.Date.context_today(env.user) - timedelta(days=3),
            'pb_staff_posting': posting,
        }
        vals.update(extra)
        return env['pb.hiring.requisition'].sudo().create(vals)

    cls.make_role = staticmethod(role)
    cls.role_both = role('DEMO S6B Shift lead')
    cls.role_staff = role('DEMO S6B Planner', posting='staff')
    cls.role_outside = role('DEMO S6B Driver', posting='outside')
    cls.role_secret = role('DEMO S6B Secret role', is_confidential=True)
    cls.role_quiet = role('DEMO S6B Quiet replacement',
                          role_type='sensitive_replacement')
    cls.App = env['hr.applicant'].sudo()
    return cls


def stage(env, key):
    return env['hr.recruitment.stage']._pb_stage(key)
