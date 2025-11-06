# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)


class HrAnalyticsHeadcount(models.Model):
    """Headcount & FTE Analysis with trends and attrition tracking"""

    _name = 'hr.analytics.headcount'
    _description = 'HR Analytics - Headcount Analysis'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from DESC'

    period_name = fields.Char(string='Period Name', required=True)
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)
    country = fields.Selection([
        ('VN', 'Vietnam'), ('ID', 'Indonesia'), ('IN', 'India'),
        ('SG', 'Singapore'), ('TH', 'Thailand'), ('KH', 'Cambodia'), ('MY', 'Malaysia')
    ])

    # Headcount JSON Data
    headcount_data = fields.Text(string='Headcount Data (JSON)')
    headcount_by_type = fields.Text(string='Headcount by Type (JSON)')
    headcount_by_title = fields.Text(string='Headcount by Job Title (JSON)')

    # FTE Metrics
    total_headcount = fields.Integer(string='Total Headcount', compute='_compute_metrics', store=True)
    total_fte = fields.Float(string='Total FTE', compute='_compute_metrics', store=True)
    part_time_count = fields.Integer(string='Part-time Count', compute='_compute_metrics', store=True)
    contractor_count = fields.Integer(string='Contractors', compute='_compute_metrics', store=True)
    fte_percentage = fields.Float(string='FTE %', compute='_compute_metrics', store=True)

    # Attrition & Movement
    new_hires = fields.Integer(string='New Hires', compute='_compute_attrition', store=True)
    separations = fields.Integer(string='Separations', compute='_compute_attrition', store=True)
    attrition_rate = fields.Float(string='Attrition Rate %', compute='_compute_attrition', store=True)
    movements = fields.Text(string='Movements (JSON)')

    # Historical Tracking
    previous_period_headcount = fields.Integer(string='Previous Period Headcount')
    headcount_trend = fields.Text(string='Headcount Trend (JSON)')
    yoy_comparison = fields.Text(string='Year-over-Year Comparison (JSON)')

    # Analysis Grouping
    group_by = fields.Selection([
        ('department', 'By Department'),
        ('job_title', 'By Job Title'),
        ('employment_type', 'By Employment Type'),
        ('country', 'By Country'),
        ('combination', 'Combined View')
    ], default='department')

    # Workflow
    state = fields.Selection([('draft', 'Draft'), ('ready', 'Ready')], default='draft')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    last_refresh = fields.Datetime(string='Last Refresh', readonly=True)

    @api.depends('headcount_data')
    def _compute_metrics(self):
        """Compute headcount metrics from JSON data"""
        for record in self:
            try:
                data = json.loads(record.headcount_data or '{}')
                record.total_headcount = data.get('total_headcount', 0)
                record.total_fte = data.get('total_fte', 0)
                record.part_time_count = data.get('part_time_count', 0)
                record.contractor_count = data.get('contractor_count', 0)

                if record.total_headcount > 0:
                    record.fte_percentage = (record.total_fte / record.total_headcount) * 100
                else:
                    record.fte_percentage = 0
            except (json.JSONDecodeError, ValueError, TypeError):
                record.total_headcount = 0
                record.total_fte = 0
                record.part_time_count = 0
                record.contractor_count = 0
                record.fte_percentage = 0

    @api.depends('movements')
    def _compute_attrition(self):
        """Compute attrition metrics"""
        for record in self:
            try:
                moves = json.loads(record.movements or '{}')
                record.new_hires = moves.get('new_hires', 0)
                record.separations = moves.get('separations', 0)

                # Attrition rate = Separations / Average Headcount
                avg_headcount = (record.total_headcount + record.previous_period_headcount) / 2
                if avg_headcount > 0:
                    record.attrition_rate = (record.separations / avg_headcount) * 100
                else:
                    record.attrition_rate = 0
            except (json.JSONDecodeError, ValueError, TypeError):
                record.new_hires = 0
                record.separations = 0
                record.attrition_rate = 0

    def action_generate_analytics(self):
        """Generate headcount analytics"""
        self.ensure_one()
        try:
            employees = self.env['hr.employee'].search([
                ('company_id', '=', self.company_id.id),
                ('active', '=', True)
            ])

            headcount_data = {
                'total_headcount': len(employees),
                'total_fte': self._calculate_total_fte(employees),
                'part_time_count': self._count_part_time(employees),
                'contractor_count': self._count_contractors(employees)
            }

            self.headcount_data = json.dumps(headcount_data)
            self.headcount_by_type = json.dumps(self._group_by_type(employees))
            self.headcount_by_title = json.dumps(self._group_by_title(employees))
            self.movements = json.dumps(self._calculate_movements())

            self.state = 'ready'
            self.last_refresh = fields.Datetime.now()

            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'message': _('Headcount analysis generated!'), 'type': 'success'}}
        except Exception as e:
            _logger.exception('Error: %s', str(e))
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'message': _('Error: %s') % str(e), 'type': 'danger'}}

    def _calculate_total_fte(self, employees):
        """Calculate total FTE from contract hours"""
        total_fte = 0
        for emp in employees:
            if emp.contract_id:
                # Assuming standard 40 hours/week = 1 FTE
                hours = emp.contract_id.resource_calendar_id.hours_per_day if emp.contract_id.resource_calendar_id else 8
                total_fte += (hours / 8)  # 8 hours = 1 FTE day
        return total_fte

    def _count_part_time(self, employees):
        """Count part-time employees"""
        count = 0
        for emp in employees:
            if emp.contract_id and emp.contract_id.resource_calendar_id:
                if emp.contract_id.resource_calendar_id.hours_per_day < 8:
                    count += 1
        return count

    def _count_contractors(self, employees):
        """Count contractor employees"""
        return len(employees.filtered(lambda e: e.contract_id and e.contract_id.type_id and 'contractor' in e.contract_id.type_id.name.lower()))

    def _group_by_type(self, employees):
        """Group employees by employment type"""
        result = {}
        for emp in employees:
            emp_type = emp.contract_id.type_id.name if emp.contract_id else 'Unknown'
            if emp_type not in result:
                result[emp_type] = 0
            result[emp_type] += 1
        return result

    def _group_by_title(self, employees):
        """Group employees by job title"""
        result = {}
        for emp in employees:
            job_title = emp.job_id.name if emp.job_id else 'Unassigned'
            if job_title not in result:
                result[job_title] = {'count': 0, 'fte': 0, 'avg_salary': 0}
            result[job_title]['count'] += 1
        return result

    def _calculate_movements(self):
        """Calculate new hires and separations"""
        return {'new_hires': 0, 'separations': 0}
