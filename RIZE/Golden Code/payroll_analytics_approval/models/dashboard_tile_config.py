# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class DashboardTileConfig(models.Model):
    _name = 'dashboard.tile.config'
    _description = 'Dashboard Tile Configuration'

    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India')
    ], string='Country', required=True)
    tile_type = fields.Selection([
        ('payroll_approval', 'Payroll Approval'),
        ('bank_export', 'Bank Export'),
        ('analytics_overview', 'Analytics Overview')
    ], string='Tile Type', required=True)
    title = fields.Char(string='Tile Title', required=True)
    subtitle = fields.Char(string='Subtitle')
    icon = fields.Char(string='Icon Class')
    action_model = fields.Char(string='Action Model')
    action_method = fields.Char(string='Action Method')
    is_active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer(string='Sequence', default=10)
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)