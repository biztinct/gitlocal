# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

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
    
    def action_import_malaysia_data(self, *args, **kwargs):
        """WDGAP S2-A (S2F-4): RETIRED. This door used to say a file was
        made (or data imported) and made none. It now says so and makes
        no claim. (Malaysia payroll import)"""
        raise UserError(_("This import is not available yet, so nothing was imported. Load pay data with the pay data file on the pay run instead."))

