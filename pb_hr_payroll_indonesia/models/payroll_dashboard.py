# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PayrollDashboard(models.TransientModel):
    _name = 'payroll.dashboard'
    _description = 'Payroll Dashboard'
    
    @api.model
    def open_vietnam_dashboard(self):
        """Open Vietnam dashboard actions"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vietnam Payroll Dashboard',
            'res_model': 'payroll.dashboard',
            'view_mode': 'form',
            'view_id': self.env.ref('pb_hr_payroll_indonesia.view_payroll_dashboard_vietnam').id,
            'target': 'new',
        }
    
    @api.model
    def open_indonesia_dashboard(self):
        """Open Indonesia dashboard actions"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Indonesia Payroll Dashboard',
            'res_model': 'payroll.dashboard',
            'view_mode': 'form',
            'view_id': self.env.ref('pb_hr_payroll_indonesia.view_payroll_dashboard_indonesia').id,
            'target': 'new',
        }