# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PayrollComparisonWizard(models.TransientModel):
    _name = 'payroll.comparison.wizard'
    _description = 'Payroll Comparison Wizard'

    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India')
    ], string='Country', required=True)
    
    # Current Period
    current_date_from = fields.Date(string='Current Period From', required=True, default=fields.Date.today)
    current_date_to = fields.Date(string='Current Period To', required=True, default=fields.Date.today)
    
    # Comparison
    comparison_type = fields.Selection([
        ('previous_month', 'Previous Month'),
        ('previous_quarter', 'Previous Quarter'),
        ('same_month_last_year', 'Same Month Last Year'),
        ('custom', 'Custom Period')
    ], string='Compare With', required=True, default='previous_month')
    previous_date_from = fields.Date(string='Previous Period From')
    previous_date_to = fields.Date(string='Previous Period To')
    
    # Options
    include_charts = fields.Boolean(string='Include Charts', default=True)
    include_variance_analysis = fields.Boolean(string='Include Variance Analysis', default=True)
    variance_threshold = fields.Float(string='Variance Threshold %', default=10.0)
    export_format = fields.Selection([
        ('pdf', 'PDF Report'),
        ('excel', 'Excel File')
    ], string='Export Format', default='pdf')

    def action_generate_comparison(self):
        """Generate comparison analysis"""
        self.ensure_one()
        
        # Create comparison record
        comparison = self.env['payroll.comparison'].create({
            'name': f'{self.country} Comparison - {self.current_date_from} to {self.current_date_to}',
            'country': self.country,
            'current_period_from': self.current_date_from,
            'current_period_to': self.current_date_to,
            'comparison_type': self.comparison_type,
            'previous_period_from': self.previous_date_from,
            'previous_period_to': self.previous_date_to,
            'variance_threshold': self.variance_threshold,
            'include_charts': self.include_charts,
        })
        
        # Generate analysis
        comparison.action_regenerate_analysis()
        
        # Return action to view comparison
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payroll Comparison Analysis',
            'res_model': 'payroll.comparison',
            'res_id': comparison.id,
            'view_mode': 'form',
            'target': 'current',
        }