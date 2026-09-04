# Part of Payobook. See LICENSE file for full copyright and licensing details.

import json
from datetime import date, datetime, timedelta
from collections import defaultdict

from odoo import api, fields, models, _


class WorkforceDashboard(models.TransientModel):
    _name = 'hr.workforce.dashboard'
    _description = 'Workforce Dashboard'
    _rec_name = 'display_name_computed'

    # Display name
    display_name_computed = fields.Char(
        string='Name', compute='_compute_display_name_field', default='Workforce Dashboard')

    # Filters
    date_from = fields.Date(string='From',
                             default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(string='To',
                           default=fields.Date.context_today)
    department_id = fields.Many2one('hr.department', string='Department')

    # KPI fields (computed)
    total_employees = fields.Integer(compute='_compute_kpis')
    present_today = fields.Integer(compute='_compute_kpis')
    absent_today = fields.Integer(compute='_compute_kpis')
    presence_rate = fields.Float(compute='_compute_kpis')
    avg_hours_week = fields.Float(compute='_compute_kpis')
    ot_hours_month = fields.Float(compute='_compute_kpis')
    pending_leaves = fields.Integer(compute='_compute_kpis')
    pending_ot_requests = fields.Integer(compute='_compute_kpis')
    shift_compliance_rate = fields.Float(compute='_compute_kpis')

    # JSON data for charts
    chart_data = fields.Text(compute='_compute_chart_data')

    def _compute_display_name_field(self):
        for rec in self:
            rec.display_name_computed = 'Workforce Dashboard'

    def _get_employee_domain(self):
        domain = [('active', '=', True)]
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        return domain

    @api.depends('date_from', 'date_to', 'department_id')
    def _compute_kpis(self):
        for rec in self:
            emp_domain = rec._get_employee_domain()
            employees = self.env['hr.employee'].search(emp_domain)
            rec.total_employees = len(employees)

            # Present today
            today_start = datetime.combine(date.today(), datetime.min.time())
            today_end = today_start + timedelta(days=1)
            checked_in = self.env['hr.attendance'].search([
                ('employee_id', 'in', employees.ids),
                ('check_in', '>=', today_start),
                ('check_in', '<', today_end),
            ]).mapped('employee_id')
            rec.present_today = len(set(checked_in.ids))
            rec.absent_today = rec.total_employees - rec.present_today
            rec.presence_rate = (rec.present_today / rec.total_employees * 100) if rec.total_employees else 0

            # Average hours this week
            week_start = date.today() - timedelta(days=date.today().weekday())
            week_attendances = self.env['hr.attendance'].search([
                ('employee_id', 'in', employees.ids),
                ('check_in', '>=', datetime.combine(week_start, datetime.min.time())),
                ('check_out', '!=', False),
            ])
            total_hrs = sum(a.worked_hours for a in week_attendances)
            rec.avg_hours_week = (total_hrs / rec.total_employees) if rec.total_employees else 0

            # OT hours this month
            ot_records = self.env['hr.attendance.overtime.line'].search([
                ('employee_id', 'in', employees.ids),
                ('date', '>=', rec.date_from),
                ('date', '<=', rec.date_to),
            ])
            rec.ot_hours_month = sum(o.duration for o in ot_records)

            # Pending leave requests
            rec.pending_leaves = self.env['hr.leave'].search_count([
                ('employee_id', 'in', employees.ids),
                ('state', '=', 'confirm'),
            ])

            # Pending OT requests
            rec.pending_ot_requests = self.env['hr.overtime.request'].search_count([
                ('employee_id', 'in', employees.ids),
                ('state', '=', 'submitted'),
            ])

            # Shift compliance
            shift_plans = self.env['hr.shift.planning'].search([
                ('employee_id', 'in', employees.ids),
                ('date', '>=', rec.date_from),
                ('date', '<=', rec.date_to),
                ('state', '=', 'completed'),
            ])
            if shift_plans:
                on_time = len(shift_plans.filtered(lambda s: s.compliance_status == 'on_time'))
                rec.shift_compliance_rate = (on_time / len(shift_plans) * 100)
            else:
                rec.shift_compliance_rate = 100.0

    @api.depends('date_from', 'date_to', 'department_id')
    def _compute_chart_data(self):
        for rec in self:
            emp_domain = rec._get_employee_domain()
            employees = self.env['hr.employee'].search(emp_domain)

            data = {
                'attendance_by_day': rec._get_attendance_by_day(employees),
                'ot_by_department': rec._get_ot_by_department(),
                'leave_by_type': rec._get_leave_by_type(employees),
                'hours_trend': rec._get_hours_trend(employees),
            }
            rec.chart_data = json.dumps(data)

    def _get_attendance_by_day(self, employees):
        """Attendance count per day of week for the period."""
        result = {d: 0 for d in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']}
        attendances = self.env['hr.attendance'].search([
            ('employee_id', 'in', employees.ids),
            ('check_in', '>=', datetime.combine(self.date_from, datetime.min.time())),
            ('check_in', '<=', datetime.combine(self.date_to, datetime.max.time())),
        ])
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for att in attendances:
            dow = att.check_in.weekday()
            result[day_names[dow]] += 1
        return result

    def _get_ot_by_department(self):
        """Overtime hours grouped by department."""
        result = {}
        deps = self.env['hr.department'].search([])
        for dep in deps:
            ot = self.env['hr.attendance.overtime.line'].search([
                ('employee_id.department_id', '=', dep.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
            ])
            total = sum(o.duration for o in ot)
            if total > 0:
                result[dep.name] = round(total, 1)
        return result

    def _get_leave_by_type(self, employees):
        """Leave days by type for the period."""
        result = {}
        leaves = self.env['hr.leave'].search([
            ('employee_id', 'in', employees.ids),
            ('state', '=', 'validate'),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
        ])
        for lv in leaves:
            name = lv.holiday_status_id.name or 'Other'
            result.setdefault(name, 0)
            result[name] += lv.number_of_days
        return result

    def _get_hours_trend(self, employees):
        """Total worked hours per week for the last 8 weeks."""
        result = []
        for i in range(7, -1, -1):
            week_start = date.today() - timedelta(weeks=i, days=date.today().weekday())
            week_end = week_start + timedelta(days=6)
            atts = self.env['hr.attendance'].search([
                ('employee_id', 'in', employees.ids),
                ('check_in', '>=', datetime.combine(week_start, datetime.min.time())),
                ('check_in', '<=', datetime.combine(week_end, datetime.max.time())),
                ('check_out', '!=', False),
            ])
            total = sum(a.worked_hours for a in atts)
            result.append({
                'week': week_start.strftime('W%V'),
                'hours': round(total, 1),
            })
        return result
