# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class IndiaPayrollProcessor(models.TransientModel):
    _name = 'india.payroll.processor'
    _description = 'India Payroll Data Processor'

    payslip_ids = fields.Many2many(
        'hr.payslip', 
        string='Payslips to Process',
        help="Select payslips to apply India-specific data to"
    )
    
    process_mode = fields.Selection([
        ('selected', 'Selected Payslips Only'),
        ('all_draft', 'All Draft Payslips'),
        ('all_india', 'All India Structure Payslips')
    ], default='selected', required=True, string='Processing Mode')
    
    auto_compute = fields.Boolean(
        string='Auto Compute After Processing',
        default=True,
        help="Automatically recompute payslips after applying India data"
    )

    @api.model
    def default_get(self, fields_list):
        """Pre-fill with selected payslips from context"""
        res = super().default_get(fields_list)
        
        # If called from payslip tree view, get selected payslips
        active_ids = self.env.context.get('active_ids', [])
        if active_ids and 'payslip_ids' in fields_list:
            res['payslip_ids'] = [(6, 0, active_ids)]
            
        return res

    def action_process_india_payrolls(self):
        """Process India payroll data for selected payslips"""
        
        # Get payslips to process based on mode
        if self.process_mode == 'selected':
            payslips = self.payslip_ids
        elif self.process_mode == 'all_draft':
            payslips = self.env['hr.payslip'].search([('state', '=', 'draft')])
        elif self.process_mode == 'all_india':
            payslips = self.env['hr.payslip'].search([
                ('struct_id.name', 'ilike', 'india')
            ])
        
        if not payslips:
            raise ValidationError(_("No payslips found to process."))
        
        # Filter to only India payslips
        india_payslips = payslips.filtered(
            lambda p: p.struct_id and 'india' in p.struct_id.name.lower()
        )
        
        if not india_payslips:
            raise ValidationError(_("No India structure payslips found in the selection."))
        
        # Process each India payslip
        processed_count = 0
        total_updated_lines = 0
        errors = []
        
        for payslip in india_payslips:
            try:
                # Apply India-specific data using our isolated method
                result = payslip.apply_india_payroll_data(payslip)
                
                if result.get('success'):
                    processed_count += 1
                    total_updated_lines += result.get('updated_lines', 0)
                    
                    # Auto-compute if requested
                    if self.auto_compute:
                        payslip.compute_sheet()
                        
                else:
                    errors.append(f"{payslip.employee_id.name}: {result.get('message', 'Unknown error')}")
                    
            except Exception as e:
                errors.append(f"{payslip.employee_id.name}: {str(e)}")
        
        # Show results
        if processed_count > 0:
            message = _("Successfully processed %s India payslips (%s salary lines updated).") % (
                processed_count, total_updated_lines
            )
            
            if errors:
                message += _("\n\nErrors encountered:\n• ") + "\n• ".join(errors)
                notification_type = 'warning'
            else:
                notification_type = 'success'
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('India Payroll Processing Complete'),
                    'message': message,
                    'type': notification_type,
                    'sticky': True if errors else False,
                }
            }
        else:
            error_message = _("No payslips were processed successfully.")
            if errors:
                error_message += _("\n\nErrors:\n• ") + "\n• ".join(errors)
                
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Processing Failed'),
                    'message': error_message,
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_preview_changes(self):
        """Preview what changes would be made without applying them"""
        # Similar logic but just show preview
        payslips = self.payslip_ids if self.process_mode == 'selected' else self.env['hr.payslip'].search([])
        
        india_payslips = payslips.filtered(
            lambda p: p.struct_id and 'india' in p.struct_id.name.lower()
        )[:5]  # Limit to 5 for preview
        
        if not india_payslips:
            raise ValidationError(_("No India payslips found for preview."))
        
        preview_data = []
        
        for payslip in india_payslips:
            zoho_data = self.env['zoho.employee.data'].search([
                ('employee_id', '=', payslip.employee_id.employee_id)
            ], limit=1)
            
            if zoho_data:
                # Show what would change
                employee_changes = []
                for line in payslip.line_ids[:10]:  # Show first 10 lines
                    if line.code in ['BASIC', 'HRA', 'PF_EMPLOYEE', 'ESI_EMPLOYEE']:
                        employee_changes.append(f"{line.name}: {line.amount}")
                
                preview_data.append({
                    'employee': payslip.employee_id.name,
                    'changes': employee_changes[:5]  # Show first 5 changes
                })
        
        # Create a simple message showing preview
        preview_message = _("Preview of changes:\n\n")
        for item in preview_data:
            preview_message += f"Employee: {item['employee']}\n"
            for change in item['changes']:
                preview_message += f"  • {change}\n"
            preview_message += "\n"
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('India Payroll Preview'),
                'message': preview_message,
                'type': 'info',
                'sticky': True,
            }
        }