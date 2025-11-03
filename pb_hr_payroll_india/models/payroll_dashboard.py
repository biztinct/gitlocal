# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PayrollDashboardIndia(models.Model):
    _inherit = 'payroll.dashboard'
    
    def action_get_employee_data_india(self):
        """Get employee data for India"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Get Employee Data - India',
            'res_model': 'zoho.staging.importer',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_payroll_country': 'IN'}
        }
    
    def action_india_edit_spreadsheet(self):
        """Edit India payroll spreadsheet"""
        try:
            spreadsheet = self.env.ref('pb_hr_payroll_india.payrollstaging_india', raise_if_not_found=False)
            if not spreadsheet:
                # Fall back to the general spreadsheet if India-specific one doesn't exist
                spreadsheet = self.env.ref('__custom__.payrollstaging', raise_if_not_found=False)
                if not spreadsheet:
                    raise UserError(_(
                        'India payroll spreadsheet not found. '
                        'Please create it with external ID pb_hr_payroll_india.payrollstaging_india'
                    ))
            
            return spreadsheet.with_context(payroll_country='IN').open_spreadsheet()
        except Exception as e:
            raise UserError(_('Error opening spreadsheet: %s') % str(e))
    
    def action_india_import_spreadsheet(self):
        """Import India spreadsheet data"""
        try:
            spreadsheet = self.env.ref('pb_hr_payroll_india.payrollstaging_india', raise_if_not_found=False)
            if not spreadsheet:
                # Fall back to the general spreadsheet if India-specific one doesn't exist
                spreadsheet = self.env.ref('__custom__.payrollstaging', raise_if_not_found=False)
                if not spreadsheet:
                    raise UserError(_(
                        'India payroll spreadsheet not found. '
                        'Please create it with external ID pb_hr_payroll_india.payrollstaging_india'
                    ))
            
            # Ensure all employees have India contracts before import
            self._ensure_employee_contracts_for_country('IN')
            
            # Try importing with proper error handling
            try:
                action = spreadsheet.with_context(payroll_country='IN').import_json_data()
                
                # If the import method returns a dictionary (action), return it
                if isinstance(action, dict):
                    return action
                
                # Otherwise show success message
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('India payroll data imported successfully'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            except ValueError as ve:
                if 'work_location' in str(ve):
                    raise UserError(_(
                        'Configuration Error: Missing field in employee model. '
                        'Please update your module to the latest version. '
                        'The import process has been fixed to handle this issue.'
                    ))
                else:
                    raise UserError(_('Import validation error: %s') % str(ve))
                    
        except UserError:
            raise  # Re-raise UserError as-is
        except Exception as e:
            raise UserError(_('Unexpected error importing spreadsheet: %s') % str(e))
    
    
    def action_process_gratuity(self):
        """Process gratuity payment for India"""
        try:
            # Look for gratuity payment wizard action
            action = self.env.ref('pb_hr_payroll_india.action_gratuity_payment_wizard', raise_if_not_found=False)
            if action:
                return {
                    'type': 'ir.actions.act_window',
                    'name': action.name,
                    'res_model': action.res_model,
                    'view_mode': action.view_mode,
                    'target': 'new',
                    'context': {'default_payroll_country': 'IN'}
                }
            else:
                raise UserError(_('Gratuity Payment wizard not found. Please contact your administrator.'))
        except Exception as e:
            raise UserError(_('Error opening gratuity payment: %s') % str(e))
    
    def _ensure_employee_contracts_for_country(self, payroll_country):
        """Ensure all employees have contracts with the correct structure for the selected country"""
        # Get the correct salary structure for the country
        salary_structure = self._get_salary_structure_for_country(payroll_country)
        
        if not salary_structure:
            raise UserError(f"Salary structure for {payroll_country} not found! Please create it first.")
        
        # Find all zoho employee data
        zoho_employees = self.env['zoho.employee.data'].search([])
        
        updated_count = 0
        created_count = 0
        
        for zoho_employee in zoho_employees:
            # Find the corresponding HR employee
            hr_employee = self.env['hr.employee'].search([
                ('employee_id', '=', zoho_employee.employee_id)
            ], limit=1)
            
            if hr_employee:
                # Find active contract
                active_contract = self.env['hr.contract'].search([
                    ('employee_id', '=', hr_employee.id),
                    ('state', '=', 'open')
                ], limit=1)
                
                if active_contract:
                    if active_contract.struct_id.id != salary_structure.id:
                        # Update contract to use correct structure
                        active_contract.write({
                            'struct_id': salary_structure.id,
                            'name': f"{hr_employee.name} - {payroll_country} Contract"
                        })
                        
                        # Update country-specific fields
                        self._update_contract_country_fields(active_contract, zoho_employee, payroll_country)
                        updated_count += 1
                else:
                    # Create new contract with correct structure
                    self._create_contract_for_employee(hr_employee, zoho_employee, payroll_country, salary_structure)
                    created_count += 1
        
        if updated_count > 0 or created_count > 0:
            self.env.user.notify_info(
                message=f"Updated {updated_count} contracts and created {created_count} new contracts for {payroll_country}",
                title="Contract Update Complete"
            )
    
    def _get_salary_structure_for_country(self, payroll_country):
        """Get salary structure for specific country"""
        if payroll_country == 'IN':
            structure_name = 'India Salary Structure'
        else:
            return None
        
        return self.env['hr.payroll.structure'].search([
            ('name', '=', structure_name)
        ], limit=1)
    
    def _create_contract_for_employee(self, employee, zoho_employee, payroll_country, salary_structure):
        """Create a new contract for employee with correct structure"""
        gen_journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
        if not gen_journal:
            raise UserError("No general journal found!")
        
        # Determine contract type
        contract_type_name = zoho_employee.employee_type or 'Permanent'
        contract_type = self.env['hr.contract.type'].search([('name', '=', contract_type_name)], limit=1)
        if not contract_type:
            contract_type = self.env['hr.contract.type'].create({'name': contract_type_name})
        
        # Calculate contract dates
        import datetime
        date_start = zoho_employee.date_of_joining if hasattr(zoho_employee, 'date_of_joining') and zoho_employee.date_of_joining else datetime.date.today()
        
        # Prepare contract data
        contract_data = {
            'name': f"{employee.name} - {payroll_country} Contract",
            'employee_id': employee.id,
            'date_start': date_start,
            'state': 'open',
            'wage': getattr(zoho_employee, 'base_salary', 0) or 0,
            'type_id': contract_type.id,
            'journal_id': gen_journal.id,
            'struct_id': salary_structure.id,
            'dependents': getattr(zoho_employee, 'number_of_dependents', 0) or 0,
        }
        
        # Add location to contract if the field exists
        if hasattr(self.env['hr.contract']._fields, 'location'):
            contract_data['location'] = zoho_employee.location_name
        
        # Add country-specific contract fields for India
        if payroll_country == 'IN':
            # India specific fields
            if hasattr(self.env['hr.contract']._fields, 'pf_number'):
                contract_data['pf_number'] = getattr(zoho_employee, 'pf_number', '')
            if hasattr(self.env['hr.contract']._fields, 'esi_number'):
                contract_data['esi_number'] = getattr(zoho_employee, 'esi_number', '')
            if hasattr(self.env['hr.contract']._fields, 'pan_number'):
                contract_data['pan_number'] = getattr(zoho_employee, 'pan_number', '')
        
        # Create the contract
        contract = self.env['hr.contract'].create(contract_data)
        return contract
    
    def _update_contract_country_fields(self, contract, zoho_employee, payroll_country):
        """Update contract with country-specific fields"""
        update_data = {}
        
        if payroll_country == 'IN':
            # India specific fields
            if hasattr(self.env['hr.contract']._fields, 'pf_number'):
                update_data['pf_number'] = getattr(zoho_employee, 'pf_number', '')
            if hasattr(self.env['hr.contract']._fields, 'esi_number'):
                update_data['esi_number'] = getattr(zoho_employee, 'esi_number', '')
            if hasattr(self.env['hr.contract']._fields, 'pan_number'):
                update_data['pan_number'] = getattr(zoho_employee, 'pan_number', '')
        
        if update_data:
            contract.write(update_data)