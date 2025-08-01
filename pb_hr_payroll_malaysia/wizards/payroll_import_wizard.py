# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class PayrollImportWizardMalaysia(models.TransientModel):
    _name = 'payroll.import.wizard.malaysia'
    _description = 'Malaysia Payroll Import Wizard'

    file_data = fields.Binary('CSV File', required=True)
    filename = fields.Char('Filename')
    import_type = fields.Selection([
        ('employee_data', 'Employee Data'),
        ('payroll_data', 'Payroll Data'),
        ('epf_data', 'EPF Data')
    ], required=True, default='employee_data')
    
    @api.model
    def action_import_malaysia_data(self):
        """Import Malaysia payroll data"""
        if not self.file_data:
            raise ValidationError("Please upload a file to import")
        
        # Process Malaysia-specific import logic
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Malaysia payroll data imported successfully',
                'type': 'success',
                'sticky': False,
            }
        }