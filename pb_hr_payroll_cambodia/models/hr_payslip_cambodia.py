# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrPayslipCambodia(models.Model):
    _inherit = 'hr.payslip'
    
    # Add currency_id field if it doesn't exist in base model
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    
    # Cambodia-specific fields
    nssf_employee = fields.Monetary('NSSF Employee Contribution', compute='_compute_cambodia_contributions', currency_field='currency_id')
    nssf_employer = fields.Monetary('NSSF Employer Contribution', compute='_compute_cambodia_contributions', currency_field='currency_id')
    withholding_tax = fields.Monetary('Withholding Tax on Salary', compute='_compute_cambodia_tax', currency_field='currency_id')
    fringe_benefits_tax = fields.Monetary('Fringe Benefits Tax', compute='_compute_cambodia_tax', currency_field='currency_id')
    
    @api.depends('line_ids')
    def _compute_cambodia_contributions(self):
        """Compute Cambodia NSSF contributions"""
        for payslip in self:
            nssf_employee = 0
            nssf_employer = 0
            
            for line in payslip.line_ids:
                if 'NSSF_EE' in line.salary_rule_id.code:
                    nssf_employee += line.amount
                elif 'NSSF_ER' in line.salary_rule_id.code:
                    nssf_employer += line.amount
            
            payslip.nssf_employee = nssf_employee
            payslip.nssf_employer = nssf_employer
    
    @api.depends('line_ids')
    def _compute_cambodia_tax(self):
        """Compute Cambodia tax calculations"""
        for payslip in self:
            withholding_tax = 0
            fringe_benefits_tax = 0
            
            for line in payslip.line_ids:
                if 'WTS' in line.salary_rule_id.code:
                    withholding_tax += line.amount
                elif 'FBT' in line.salary_rule_id.code:
                    fringe_benefits_tax += line.amount
            
            payslip.withholding_tax = withholding_tax
            payslip.fringe_benefits_tax = fringe_benefits_tax