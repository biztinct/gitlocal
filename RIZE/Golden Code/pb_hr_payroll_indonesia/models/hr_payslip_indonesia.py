# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HrPayslipIndonesia(models.Model):
    _inherit = 'hr.payslip'
    
    def _get_report_name(self):
        """Determine which report template to use based on payroll structure"""
        self.ensure_one()
        
        if self.struct_id and self.struct_id.name == 'Indonesia Salary Structure':
            return 'pb_hr_payroll_indonesia.report_payslip_indonesia'
        else:
            # Use default Vietnam template for all other structures
            return 'om_hr_payroll.report_payslip'
    
    def action_print_payslip(self):
        """Override print action to use country-specific template"""
        self.ensure_one()
        
        report_name = self._get_report_name()
        
        # Debug logging
        _logger.info(f"Printing payslip for {self.employee_id.name}, Structure: {self.struct_id.name}, Using template: {report_name}")
        
        return {
            'type': 'ir.actions.report',
            'report_name': report_name,
            'report_type': 'qweb-pdf',
            'data': {},
            'context': self.env.context,
        }
    
    @api.model
    def get_payslip_report_action(self, payslip_ids):
        """Get the appropriate report action for given payslips"""
        payslips = self.browse(payslip_ids)
        
        # Check if all payslips use the same structure
        structures = payslips.mapped('struct_id.name')
        
        if len(set(structures)) > 1:
            raise UserError(_('Cannot print payslips with different structures together. Please select payslips with the same structure.'))
        
        # Determine report based on structure
        if 'Indonesia Salary Structure' in structures:
            report_ref = 'pb_hr_payroll_indonesia.action_report_payslip_indonesia'
        else:
            report_ref = 'om_hr_payroll.action_report_payslip'
        
        return self.env.ref(report_ref).report_action(payslips)


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'
    
    def action_print_payslips(self):
        """Override to use country-specific templates"""
        payslips = self.slip_ids.filtered(lambda slip: slip.state in ['done', 'level1', 'level2'])
        
        if not payslips:
            raise UserError(_('No confirmed payslips found to print.'))
        
        # Group payslips by structure
        structure_groups = {}
        for payslip in payslips:
            struct_name = payslip.struct_id.name if payslip.struct_id else 'Unknown'
            if struct_name not in structure_groups:
                structure_groups[struct_name] = self.env['hr.payslip']
            structure_groups[struct_name] |= payslip
        
        # If only one structure, print directly
        if len(structure_groups) == 1:
            struct_name, group_payslips = list(structure_groups.items())[0]
            return group_payslips.get_payslip_report_action(group_payslips.ids)
        
        # Multiple structures - show selection wizard
        return {
            'type': 'ir.actions.act_window',
            'name': 'Select Payslip Structure to Print',
            'res_model': 'payslip.print.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payslip_run_id': self.id,
                'structure_groups': {k: v.ids for k, v in structure_groups.items()}
            }
        }


class PayslipPrintWizard(models.TransientModel):
    _name = 'payslip.print.wizard'
    _description = 'Payslip Print Structure Selector'
    
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip Run', required=True)
    structure_name = fields.Selection([], string='Payroll Structure', required=True)
    
    @api.model
    def default_get(self, fields_list):
        """Populate structure options based on payslips in the run"""
        res = super().default_get(fields_list)
        
        if 'structure_name' in fields_list and self.env.context.get('structure_groups'):
            structure_groups = self.env.context['structure_groups']
            options = [(name, f"{name} ({len(ids)} payslips)") for name, ids in structure_groups.items()]
            
            # Update field selection dynamically
            self._fields['structure_name'].selection = options
            
        return res
    
    def action_print_selected_structure(self):
        """Print payslips for selected structure"""
        structure_groups = self.env.context.get('structure_groups', {})
        payslip_ids = structure_groups.get(self.structure_name, [])
        
        if not payslip_ids:
            raise UserError(_('No payslips found for selected structure.'))
        
        payslips = self.env['hr.payslip'].browse(payslip_ids)
        return payslips.get_payslip_report_action(payslip_ids)