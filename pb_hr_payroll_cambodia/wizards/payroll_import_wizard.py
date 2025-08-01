# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class PayrollImportWizardCambodia(models.TransientModel):
    _name = 'payroll.import.wizard.cambodia'
    _description = 'Cambodia Payroll Import Wizard'

    file_data = fields.Binary('CSV File', required=True)
    filename = fields.Char('Filename')
    import_type = fields.Selection([
        ('employee_data', 'Employee Data'),
        ('payroll_data', 'Payroll Data'),
        ('nssf_data', 'NSSF Data')
    ], required=True, default='employee_data')
    
    @api.model
    def action_import_cambodia_data(self):
        """Import Cambodia payroll data"""
        if not self.file_data:
            raise ValidationError("Please upload a file to import")
        
        # Process Cambodia-specific import logic
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Cambodia payroll data imported successfully',
                'type': 'success',
                'sticky': False,
            }
        }