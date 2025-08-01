# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrPayslipMalaysia(models.Model):
    _inherit = 'hr.payslip'
    
    # Add currency_id field if it doesn't exist in base model
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    
    # Malaysia-specific fields
    epf_employee = fields.Monetary('EPF Employee Contribution', compute='_compute_malaysia_contributions', currency_field='currency_id')
    epf_employer = fields.Monetary('EPF Employer Contribution', compute='_compute_malaysia_contributions', currency_field='currency_id')
    socso_employee = fields.Monetary('SOCSO Employee Contribution', compute='_compute_malaysia_contributions', currency_field='currency_id')
    socso_employer = fields.Monetary('SOCSO Employer Contribution', compute='_compute_malaysia_contributions', currency_field='currency_id')
    eis_employee = fields.Monetary('EIS Employee Contribution', compute='_compute_malaysia_contributions', currency_field='currency_id')
    eis_employer = fields.Monetary('EIS Employer Contribution', compute='_compute_malaysia_contributions', currency_field='currency_id')
    pcb_tax = fields.Monetary('PCB Income Tax', compute='_compute_malaysia_tax', currency_field='currency_id')
    
    @api.depends('line_ids')
    def _compute_malaysia_contributions(self):
        """Compute Malaysia EPF, SOCSO, and EIS contributions"""
        for payslip in self:
            epf_employee = 0
            epf_employer = 0
            socso_employee = 0
            socso_employer = 0
            eis_employee = 0
            eis_employer = 0
            
            for line in payslip.line_ids:
                if 'EPF_EE' in line.salary_rule_id.code:
                    epf_employee += line.amount
                elif 'EPF_ER' in line.salary_rule_id.code:
                    epf_employer += line.amount
                elif 'SOCSO_EE' in line.salary_rule_id.code:
                    socso_employee += line.amount
                elif 'SOCSO_ER' in line.salary_rule_id.code:
                    socso_employer += line.amount
                elif 'EIS_EE' in line.salary_rule_id.code:
                    eis_employee += line.amount
                elif 'EIS_ER' in line.salary_rule_id.code:
                    eis_employer += line.amount
            
            payslip.epf_employee = epf_employee
            payslip.epf_employer = epf_employer
            payslip.socso_employee = socso_employee
            payslip.socso_employer = socso_employer
            payslip.eis_employee = eis_employee
            payslip.eis_employer = eis_employer
    
    @api.depends('line_ids')
    def _compute_malaysia_tax(self):
        """Compute Malaysia PCB tax calculations"""
        for payslip in self:
            pcb_tax = 0
            
            for line in payslip.line_ids:
                if 'PCB' in line.salary_rule_id.code:
                    pcb_tax += line.amount
            
            payslip.pcb_tax = pcb_tax