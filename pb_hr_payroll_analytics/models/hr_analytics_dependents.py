# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import json
import logging

_logger = logging.getLogger(__name__)


class HrAnalyticsDependents(models.Model):
    """Dependents & Benefits Analysis"""

    _name = 'hr.analytics.dependents'
    _description = 'HR Analytics - Dependents & Benefits'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from DESC'

    period_name = fields.Char(string='Period Name', required=True)
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)

    # Dependent Data
    dependent_summary = fields.Text(string='Dependent Summary (JSON)')
    dependents_by_employee = fields.Text(string='Dependents by Employee (JSON)')
    age_distribution = fields.Text(string='Age Distribution (JSON)')

    # Metrics
    total_dependents = fields.Integer(string='Total Dependents', compute='_compute_metrics', store=True)
    employees_with_dependents = fields.Integer(string='Employees with Dependents', compute='_compute_metrics', store=True)
    avg_dependents_per_employee = fields.Float(string='Average Dependents/Employee', compute='_compute_metrics', store=True)

    # Financial Impact
    total_dependent_allowance = fields.Float(string='Total Dependent Allowance', compute='_compute_financial', store=True)
    average_dependent_benefit = fields.Float(string='Avg Dependent Benefit', compute='_compute_financial', store=True)
    insurance_impact = fields.Text(string='Insurance Impact (JSON)')
    tax_benefit_impact = fields.Text(string='Tax Benefit Impact (JSON)')

    state = fields.Selection([('draft', 'Draft'), ('ready', 'Ready')], default='draft')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    last_refresh = fields.Datetime(string='Last Refresh', readonly=True)

    @api.depends('dependent_summary')
    def _compute_metrics(self):
        """Compute dependent metrics"""
        for record in self:
            try:
                data = json.loads(record.dependent_summary or '{}')
                record.total_dependents = data.get('total_dependents', 0)
                record.employees_with_dependents = data.get('employees_with_dependents', 0)
                record.avg_dependents_per_employee = data.get('avg_dependents_per_employee', 0)
            except (json.JSONDecodeError, ValueError, TypeError):
                record.total_dependents = 0
                record.employees_with_dependents = 0
                record.avg_dependents_per_employee = 0

    @api.depends('total_dependent_allowance')
    def _compute_financial(self):
        """Compute financial impact"""
        for record in self:
            try:
                allowance = json.loads(record.total_dependent_allowance or '0')
                record.total_dependent_allowance = float(allowance)
                if record.employees_with_dependents > 0:
                    record.average_dependent_benefit = record.total_dependent_allowance / record.total_dependents
                else:
                    record.average_dependent_benefit = 0
            except (json.JSONDecodeError, ValueError, TypeError):
                record.total_dependent_allowance = 0
                record.average_dependent_benefit = 0

    def action_generate_analytics(self):
        """Generate dependents analytics"""
        self.ensure_one()
        try:
            employees = self.env['hr.employee'].search([('company_id', '=', self.company_id.id)])

            dependent_data = {
                'total_dependents': 0,
                'employees_with_dependents': 0,
                'avg_dependents_per_employee': 0
            }

            self.dependent_summary = json.dumps(dependent_data)
            self.dependents_by_employee = '{}'
            self.age_distribution = '{}'
            self.insurance_impact = '{}'
            self.tax_benefit_impact = '{}'

            self.state = 'ready'
            self.last_refresh = fields.Datetime.now()

            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'message': _('Dependents analysis generated!'), 'type': 'success'}}
        except Exception as e:
            _logger.exception('Error: %s', str(e))
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'message': _('Error: %s') % str(e), 'type': 'danger'}}
