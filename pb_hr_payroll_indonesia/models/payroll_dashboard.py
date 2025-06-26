# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PayrollDashboard(models.Model):  # Changed to Model instead of TransientModel
    _name = 'payroll.dashboard'
    _description = 'Payroll Dashboard'
    
    name = fields.Char('Dashboard Name', compute='_compute_name', store=True)
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India')
    ], string='Country', default='VN')
    
    @api.depends('country')
    def _compute_name(self):
        """Compute dashboard name based on country"""
        country_names = {
            'VN': 'Vietnam Payroll Dashboard',
            'ID': 'Indonesia Payroll Dashboard', 
            'IN': 'India Payroll Dashboard'
        }
        for record in self:
            record.name = country_names.get(record.country, 'Payroll Dashboard')
    
    @api.model
    def get_or_create_dashboard(self, country_code):
        """Get or create a single dashboard record for the country"""
        dashboard = self.search([('country', '=', country_code)], limit=1)
        if not dashboard:
            dashboard = self.create({'country': country_code})
        return dashboard
    
    @api.model
    def open_vietnam_dashboard(self):
        """Open Vietnam dashboard actions"""
        dashboard = self.get_or_create_dashboard('VN')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vietnam Payroll Dashboard',
            'res_model': 'payroll.dashboard',
            'view_mode': 'form',
            'view_id': self.env.ref('pb_hr_payroll_indonesia.view_payroll_dashboard_vietnam').id,
            'res_id': dashboard.id,
            'target': 'current',
            'context': {'default_payroll_country': 'VN'}
        }
    
    @api.model
    def open_indonesia_dashboard(self):
        """Open Indonesia dashboard actions"""
        dashboard = self.get_or_create_dashboard('ID')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Indonesia Payroll Dashboard',
            'res_model': 'payroll.dashboard',
            'view_mode': 'form',
            'view_id': self.env.ref('pb_hr_payroll_indonesia.view_payroll_dashboard_indonesia').id,
            'res_id': dashboard.id,
            'target': 'current',
            'context': {'default_payroll_country': 'ID'}
        }
    
    # Vietnam Actions
    def action_get_employee_data_vietnam(self):
        """Get employee data for Vietnam"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Get Employee Data - Vietnam',
            'res_model': 'zoho.staging.importer',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_payroll_country': 'VN'}
        }
    
    def action_vietnam_edit_spreadsheet(self):
        """Edit Vietnam payroll spreadsheet"""
        try:
            spreadsheet = self.env.ref('__custom__.payrollstaging', raise_if_not_found=False)
            if not spreadsheet:
                raise UserError(_(
                    'Vietnam payroll spreadsheet not found. '
                    'Please create it with external ID __custom__.payrollstaging'
                ))
            
            return spreadsheet.with_context(payroll_country='VN').open_spreadsheet()
        except Exception as e:
            raise UserError(_('Error opening spreadsheet: %s') % str(e))
    
    def action_vietnam_import_spreadsheet(self):
        """Import Vietnam spreadsheet data"""
        try:
            spreadsheet = self.env.ref('__custom__.payrollstaging', raise_if_not_found=False)
            if not spreadsheet:
                raise UserError(_(
                    'Vietnam payroll spreadsheet not found. '
                    'Please create it with external ID __custom__.payrollstaging'
                ))
            
            # Ensure all employees have Vietnam contracts before import
            self._ensure_employee_contracts_for_country('VN')
            
            # Try importing with proper error handling
            try:
                action = spreadsheet.with_context(payroll_country='VN').import_json_data()
                
                # If the import method returns a dictionary (action), return it
                if isinstance(action, dict):
                    return action
                
                # Otherwise show success message
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Vietnam payroll data imported successfully'),
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
    
    # Indonesia Actions
    def action_get_employee_data_indonesia(self):
        """Get employee data for Indonesia"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Get Employee Data - Indonesia',
            'res_model': 'zoho.staging.importer',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_payroll_country': 'ID'}
        }
    
    def action_indonesia_edit_spreadsheet(self):
        """Edit Indonesia payroll spreadsheet"""
        try:
            spreadsheet = self.env.ref('__custom__.payrollstaging_indonesia', raise_if_not_found=False)
            if not spreadsheet:
                # Fall back to the general spreadsheet if Indonesia-specific one doesn't exist
                spreadsheet = self.env.ref('__custom__.payrollstaging', raise_if_not_found=False)
                if not spreadsheet:
                    raise UserError(_(
                        'Indonesia payroll spreadsheet not found. '
                        'Please create it with external ID __custom__.payrollstaging_indonesia or __custom__.payrollstaging'
                    ))
            
            return spreadsheet.with_context(payroll_country='ID').open_spreadsheet()
        except Exception as e:
            raise UserError(_('Error opening spreadsheet: %s') % str(e))
    
    def action_indonesia_import_spreadsheet(self):
        """Import Indonesia spreadsheet data"""
        try:
            spreadsheet = self.env.ref('__custom__.payrollstaging_indonesia', raise_if_not_found=False)
            if not spreadsheet:
                # Fall back to the general spreadsheet if Indonesia-specific one doesn't exist
                spreadsheet = self.env.ref('__custom__.payrollstaging', raise_if_not_found=False)
                if not spreadsheet:
                    raise UserError(_(
                        'Indonesia payroll spreadsheet not found. '
                        'Please create it with external ID __custom__.payrollstaging_indonesia or __custom__.payrollstaging'
                    ))
            
            # Ensure all employees have Indonesia contracts before import
            self._ensure_employee_contracts_for_country('ID')
            
            # Try importing with proper error handling
            try:
                action = spreadsheet.with_context(payroll_country='ID').import_json_data()
                
                # If the import method returns a dictionary (action), return it
                if isinstance(action, dict):
                    return action
                
                # Otherwise show success message
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Indonesia payroll data imported successfully'),
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
    
    def action_thr_payment(self):
        """Process THR payment for Indonesia"""
        try:
            # Look for THR payment wizard action
            action = self.env.ref('pb_hr_payroll_indonesia.action_thr_payment_wizard', raise_if_not_found=False)
            if action:
                return {
                    'type': 'ir.actions.act_window',
                    'name': action.name,
                    'res_model': action.res_model,
                    'view_mode': action.view_mode,
                    'target': 'new',
                    'context': {'default_payroll_country': 'ID'}
                }
            else:
                raise UserError(_('THR Payment wizard not found. Please contact your administrator.'))
        except Exception as e:
            raise UserError(_('Error opening THR payment: %s') % str(e))
    
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
        if payroll_country == 'VN':
            structure_name = 'Vietnam Salary Structure'
        elif payroll_country == 'ID':
            structure_name = 'Indonesia Salary Structure'
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
        
        # Add country-specific contract fields
        if payroll_country == 'ID':
            # Indonesia specific fields
            if hasattr(self.env['hr.contract']._fields, 'pph21_rate'):
                contract_data['pph21_rate'] = getattr(zoho_employee, 'pph21_rate', 0)
            
            # BPJS Employee contributions
            if hasattr(self.env['hr.contract']._fields, 'bpjs_kesehatan_employee'):
                contract_data['bpjs_kesehatan_employee'] = getattr(zoho_employee, 'bpjs_kesehatan_employee', 1.0)
            if hasattr(self.env['hr.contract']._fields, 'bpjs_tk_jht_employee'):
                contract_data['bpjs_tk_jht_employee'] = getattr(zoho_employee, 'bpjs_tk_jht_employee', 2.0)
            if hasattr(self.env['hr.contract']._fields, 'bpjs_tk_jp_employee'):
                contract_data['bpjs_tk_jp_employee'] = getattr(zoho_employee, 'bpjs_tk_jp_employee', 1.0)
                
            # BPJS Employer contributions
            if hasattr(self.env['hr.contract']._fields, 'bpjs_kesehatan_employer'):
                contract_data['bpjs_kesehatan_employer'] = getattr(zoho_employee, 'bpjs_kesehatan_employer', 4.0)
            if hasattr(self.env['hr.contract']._fields, 'bpjs_tk_jht_employer'):
                contract_data['bpjs_tk_jht_employer'] = getattr(zoho_employee, 'bpjs_tk_jht_employer', 3.7)
            if hasattr(self.env['hr.contract']._fields, 'bpjs_tk_jp_employer'):
                contract_data['bpjs_tk_jp_employer'] = getattr(zoho_employee, 'bpjs_tk_jp_employer', 2.0)
            if hasattr(self.env['hr.contract']._fields, 'bpjs_tk_jkm'):
                contract_data['bpjs_tk_jkm'] = getattr(zoho_employee, 'bpjs_tk_jkm', 0.3)
            if hasattr(self.env['hr.contract']._fields, 'bpjs_tk_jkk'):
                contract_data['bpjs_tk_jkk'] = getattr(zoho_employee, 'bpjs_tk_jkk', 0.24)
                
        elif payroll_country == 'VN':
            # Vietnam specific fields
            if hasattr(self.env['hr.contract']._fields, 'tupart'):
                contract_data['tupart'] = getattr(zoho_employee, 'tu_part', 'YES')
            if hasattr(self.env['hr.contract']._fields, 'shuipart'):
                contract_data['shuipart'] = getattr(zoho_employee, 'shui_part', 'YES')
            if hasattr(self.env['hr.contract']._fields, 'costcenter'):
                contract_data['costcenter'] = getattr(zoho_employee, 'costcenter', '')
        
        # Create the contract
        contract = self.env['hr.contract'].create(contract_data)
        return contract
    
    def _update_contract_country_fields(self, contract, zoho_employee, payroll_country):
        """Update contract with country-specific fields"""
        update_data = {}
        
        if payroll_country == 'VN':
            # Vietnam specific fields
            if hasattr(self.env['hr.contract']._fields, 'tupart'):
                update_data['tupart'] = getattr(zoho_employee, 'tu_part', 'YES')
            if hasattr(self.env['hr.contract']._fields, 'shuipart'):
                update_data['shuipart'] = getattr(zoho_employee, 'shui_part', 'YES')
            if hasattr(self.env['hr.contract']._fields, 'costcenter'):
                update_data['costcenter'] = getattr(zoho_employee, 'costcenter', '')
                
        elif payroll_country == 'ID':
            # Indonesia specific fields
            if hasattr(self.env['hr.contract']._fields, 'pph21_rate'):
                update_data['pph21_rate'] = getattr(zoho_employee, 'pph21_rate', 0)
            
            # BPJS Employee contributions
            if hasattr(self.env['hr.contract']._fields, 'bpjs_kesehatan_employee'):
                update_data['bpjs_kesehatan_employee'] = getattr(zoho_employee, 'bpjs_kesehatan_employee', 1.0)
            if hasattr(self.env['hr.contract']._fields, 'bpjs_tk_jht_employee'):
                update_data['bpjs_tk_jht_employee'] = getattr(zoho_employee, 'bpjs_tk_jht_employee', 2.0)
            if hasattr(self.env['hr.contract']._fields, 'bpjs_tk_jp_employee'):
                update_data['bpjs_tk_jp_employee'] = getattr(zoho_employee, 'bpjs_tk_jp_employee', 1.0)
                
            # BPJS Employer contributions
            if hasattr(self.env['hr.contract']._fields, 'bpjs_kesehatan_employer'):
                update_data['bpjs_kesehatan_employer'] = getattr(zoho_employee, 'bpjs_kesehatan_employer', 4.0)
            if hasattr(self.env['hr.contract']._fields, 'bpjs_tk_jht_employer'):
                update_data['bpjs_tk_jht_employer'] = getattr(zoho_employee, 'bpjs_tk_jht_employer', 3.7)
            if hasattr(self.env['hr.contract']._fields, 'bpjs_tk_jp_employer'):
                update_data['bpjs_tk_jp_employer'] = getattr(zoho_employee, 'bpjs_tk_jp_employer', 2.0)
            if hasattr(self.env['hr.contract']._fields, 'bpjs_tk_jkm'):
                update_data['bpjs_tk_jkm'] = getattr(zoho_employee, 'bpjs_tk_jkm', 0.3)
            if hasattr(self.env['hr.contract']._fields, 'bpjs_tk_jkk'):
                update_data['bpjs_tk_jkk'] = getattr(zoho_employee, 'bpjs_tk_jkk', 0.24)
        
        if update_data:
            contract.write(update_data)