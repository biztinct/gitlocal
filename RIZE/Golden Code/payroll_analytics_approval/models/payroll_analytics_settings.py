# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class PayrollAnalyticsSettings(models.Model):
    _name = 'payroll.analytics.settings'
    _description = 'Payroll Analytics Settings'

    name = fields.Char(string='Settings Name', default='Analytics Settings')
    variance_threshold = fields.Float(string='Variance Threshold %', default=10.0)
    anomaly_detection_enabled = fields.Boolean(string='Enable Anomaly Detection', default=True)
    auto_generate_analytics = fields.Boolean(string='Auto Generate Analytics', default=True)
    email_notifications = fields.Boolean(string='Email Notifications', default=True)
    chart_library = fields.Selection([
        ('chartjs', 'Chart.js'),
        ('plotly', 'Plotly'),
        ('d3', 'D3.js')
    ], string='Chart Library', default='chartjs')
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')