# -*- coding: utf-8 -*-
"""Lightweight employee loan model.

The base platform has no loan object, yet enterprise payroll demos need credible
loans feeding a monthly deduction component. This is intentionally small: enough
to drive realistic 'Loan Repayment' lines and a Loans dashboard, extensible later.
"""
from odoo import api, fields, models


class HrLoan(models.Model):
    _name = 'hr.loan'
    _description = 'Employee Loan'
    _order = 'date_start desc, id desc'

    name = fields.Char(string='Reference', required=True, default='New', copy=False)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
                                  ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  related='company_id.currency_id', store=True)
    loan_type = fields.Selection([
        ('personal', 'Personal Loan'),
        ('housing', 'Housing Loan'),
        ('vehicle', 'Vehicle Loan'),
        ('emergency', 'Emergency Advance'),
        ('education', 'Education Loan'),
    ], string='Loan Type', default='personal', required=True)
    principal_amount = fields.Monetary(string='Principal', required=True)
    installment_amount = fields.Monetary(string='Monthly Installment', required=True)
    balance_amount = fields.Monetary(string='Outstanding Balance')
    total_months = fields.Integer(string='Tenure (months)', default=12)
    paid_months = fields.Integer(string='Months Paid', default=0)
    date_start = fields.Date(string='Start Date', default=fields.Date.context_today)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('closed', 'Closed'),
    ], string='Status', default='running', index=True)
    is_demo = fields.Boolean(string='Demo Record', default=False, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.loan') or 'LOAN'
            if not vals.get('balance_amount'):
                vals['balance_amount'] = vals.get('principal_amount', 0.0)
        return super().create(vals_list)
