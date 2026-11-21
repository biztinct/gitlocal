# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class BankExportLog(models.Model):
    _name = 'bank.export.log'
    _description = 'Bank Export History'
    _order = 'export_date desc'

    period_name = fields.Char(string='Period', required=True)
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India')
    ], string='Country', required=True)
    
    export_date = fields.Datetime(string='Export Date', default=fields.Datetime.now, required=True)
    total_records = fields.Integer(string='Total Records')
    total_amount = fields.Monetary(string='Total Amount')
    export_format = fields.Selection([
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('txt', 'Text')
    ], string='Format')
    
    # File
    export_file = fields.Binary(string='Export File')
    filename = fields.Char(string='Filename')
    
    # Additional Info
    export_details = fields.Text(string='Export Details')
    created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')