# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Fixtures shared by the E3 suites (handover E3 "Tests"): `share_emp` (an
employee login + employee in a company that has an Internal project, on an
8 h Monday–Friday schedule), `plain` (a full account + employee), `other` (an
employee of another company); a project of the employee's company with two
tasks; a followers-only project the employee does not follow; a project of
the other company; a template project."""
from datetime import date

from odoo.addons.pb_me_portal.tests.test_portal_accounts import _make_share
from odoo.addons.pb_me_portal.tests.test_portal_only import _make_people
from odoo.addons.pb_me_project_time.models.project_time import PARAM

TZ = 'Asia/Ho_Chi_Minh'
#: a week with no public holiday on the clone (checked 2026-10-16)
MONDAY = date(2026, 9, 14)
PASSWORD = 'etp-e3-project-time-probe-2026'


def make_calendar(env, name='E3 8 h Monday to Friday'):
    """8 h a day, Monday to Friday (08–12, 13–17; the lunch hour is a break)."""
    att = [(5, 0, 0)]
    for dow in '01234':
        att += [
            (0, 0, {'name': 'Morning', 'dayofweek': dow, 'hour_from': 8,
                    'hour_to': 12, 'day_period': 'morning'}),
            (0, 0, {'name': 'Lunch', 'dayofweek': dow, 'hour_from': 12,
                    'hour_to': 13, 'day_period': 'lunch'}),
            (0, 0, {'name': 'Afternoon', 'dayofweek': dow, 'hour_from': 13,
                    'hour_to': 17, 'day_period': 'afternoon'}),
        ]
    return env['resource.calendar'].create({
        'name': name, 'tz': TZ, 'company_id': env.company.id,
        'attendance_ids': att})


def setup_e3(cls, prefix, password=None):
    env = cls.env
    company = env.company
    cls.company = company
    cls.cal = make_calendar(env)
    cls.share, cls.share_emp = _make_share(
        env, '%s_share' % prefix, 'Pia Project Share', password)
    cls.plain, cls.plain_emp, _lead, _staff = _make_people(
        env, prefix, password=password)
    for emp in (cls.share_emp, cls.plain_emp):
        emp.write({'resource_calendar_id': cls.cal.id, 'tz': TZ})

    Project = env['project.project']
    Task = env['project.task']
    cls.internal = company.internal_project_id
    if not cls.internal:
        cls.internal = Project.create({
            'name': 'Internal', 'company_id': company.id,
            'allow_timesheets': True, 'privacy_visibility': 'employees'})
        company.internal_project_id = cls.internal
    cls.leave_task = company.leave_timesheet_task_id \
        if 'leave_timesheet_task_id' in company._fields else Task
    cls.proj = Project.create({
        'name': 'E3 Website refresh', 'company_id': company.id,
        'allow_timesheets': True, 'privacy_visibility': 'employees'})
    cls.task_a = Task.create({'name': 'E3 Design', 'project_id': cls.proj.id,
                              'sequence': 1})
    cls.task_b = Task.create({'name': 'E3 Build', 'project_id': cls.proj.id,
                              'sequence': 2})
    cls.followers_proj = Project.create({
        'name': 'E3 Followers only', 'company_id': company.id,
        'allow_timesheets': True, 'privacy_visibility': 'followers'})
    cls.tpl_proj = Project.create({
        'name': 'E3 Template', 'company_id': company.id,
        'allow_timesheets': True, 'privacy_visibility': 'employees',
        'is_template': True})
    cls.other_co = env['res.company'].create({'name': 'E3 Other Company'})
    cls.other_proj = Project.create({
        'name': 'E3 Other company project', 'company_id': cls.other_co.id,
        'allow_timesheets': True, 'privacy_visibility': 'employees'})
    cls.other_emp = env['hr.employee'].create({
        'name': 'E3 Other Employee', 'company_id': cls.other_co.id})
    env['ir.config_parameter'].sudo().set_param(PARAM % company.id, False)
    cls.Line = env['account.analytic.line'].sudo()


def lines_of(cls, emp):
    return cls.Line.with_context(active_test=False).search(
        [('employee_id', '=', emp.id), ('project_id', '!=', False)])
