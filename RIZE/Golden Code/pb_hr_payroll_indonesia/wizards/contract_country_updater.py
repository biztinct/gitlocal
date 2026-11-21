# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ContractCountryUpdater(models.TransientModel):
    _name = 'contract.country.updater'
    _description = 'Update Employee Contracts for Specific Country'
    
    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India')
    ], string='Target Country', required=True, help="Select the country structure to apply to employee contracts")
    
    employee_ids = fields.Many2many(
        'hr.employee', 
        string='Employees', 
        help="Select specific employees to update. Leave empty to update all employees with active contracts."
    )
    
    update_mode = fields.Selection([
        ('all', 'Update All Active Contracts'),
        ('selected', 'Update Selected Employees Only'),
        ('force_create', 'Force Create New Contracts')
    ], string='Update Mode', default='all', required=True)
    
    def action_update_contracts(self):
        """Update employee contracts with the selected country structure"""
        self.ensure_one()
        
        # Get the target salary structure
        target_structure = self._get_salary_structure_for_country(self.country)
        if not target_structure:
            raise UserError(f"Salary structure for {self.country} not found! Please create it first.")
        
        # Determine which employees to process
        if self.update_mode == 'selected' and self.employee_ids:
            employees = self.employee_ids
        else:
            # Get all employees with zoho data
            zoho_employees = self.env['zoho.employee.data'].search([])
            employee_ids = []
            for zoho_emp in zoho_employees:
                hr_emp = self.env['hr.employee'].search([('employee_id', '=', zoho_emp.employee_id)], limit=1)
                if hr_emp:
                    employee_ids.append(hr_emp.id)
            employees = self.env['hr.employee'].browse(employee_ids)
        
        if not employees:
            raise UserError("No employees found to update!")
        
        updated_count = 0
        created_count = 0
        error_count = 0
        
        for employee in employees:
            try:
                if self.update_mode == 'force_create':
                    # Create new contract regardless of existing ones
                    self._create_new_contract(employee, target_structure)
                    created_count += 1
                else:
                    # Update or create contract as needed
                    result = self._update_or_create_contract(employee, target_structure)
                    if result == 'updated':
                        updated_count += 1
                    elif result == 'created':
                        created_count += 1
                        
            except Exception as e:
                error_count += 1
                _logger.error(f"Error updating contract for {employee.name}: {str(e)}")
                continue
        
        # Show summary message
        message = f"Contract update completed!\n"
        message += f"Updated: {updated_count} contracts\n"
        message += f"Created: {created_count} contracts\n"
        if error_count > 0:
            message += f"Errors: {error_count} contracts"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Contract Update Complete'),
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': True,
            }
        }
    
    def _update_or_create_contract(self, employee, target_structure):
        """Update existing contract or create new one"""
        # Find active contract
        active_contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open')
        ], limit=1)
        
        if active_contract:
            # Update existing contract
            active_contract.write({
                'struct_id': target_structure.id,
                'name': f"{employee.name} - {self.country} Contract"
            })
            
            # Update country-specific fields
            self._update_contract_country_fields(active_contract, employee)
            return 'updated'
        else:
            # Create new contract
            self._create_new_contract(employee, target_structure)
            return 'created'
    
    def _create_new_contract(self, employee, target_structure):
        """Create a new contract for the employee"""
        # Get zoho employee data
        zoho_employee = self.env['zoho.employee.data'].search([
            ('employee_id', '=', employee.employee_id)
        ], limit=1)
        
        gen_journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
        if not gen_journal:
            raise UserError("No general journal found!")
        
        # Determine contract type
        contract_type_name = zoho_employee.employee_type if zoho_employee else 'Permanent'
        contract_type = self.env['hr.contract.type'].search([('name', '=', contract_type_name)], limit=1)
        if not contract_type:
            contract_type = self.env['hr.contract.type'].create({'name': contract_type_name})
        
        # Calculate contract dates
        import datetime
        date_start = zoho_employee.date_of_joining if zoho_employee and hasattr(zoho_employee, 'date_of_joining') and zoho_employee.date_of_joining else datetime.date.today()
        
        # Prepare contract data
        contract_data = {
            'name': f"{employee.name} - {self.country} Contract",
            'employee_id': employee.id,
            'date_start': date_start,
            'state': 'open',
            'wage': getattr(zoho_employee, 'base_salary', 0) if zoho_employee else 0,
            'type_id': contract_type.id,
            'journal_id': gen_journal.id,
            'struct_id': target_structure.id,
            'dependents': getattr(zoho_employee, 'number_of_dependents', 0) if zoho_employee else 0,
        }
        
        # Add location to contract if the field exists
        if hasattr(self.env['hr.contract']._fields, 'location') and zoho_employee:
            contract_data['location'] = zoho_employee.location_name
        
        # Add country-specific contract fields
        if self.country == 'ID' and zoho_employee:
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
                
        elif self.country == 'VN' and zoho_employee:
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
    
    def _update_contract_country_fields(self, contract, employee):
        """Update contract with country-specific fields"""
        # Get zoho employee data
        zoho_employee = self.env['zoho.employee.data'].search([
            ('employee_id', '=', employee.employee_id)
        ], limit=1)
        
        if not zoho_employee:
            return
        
        update_data = {}
        
        if self.country == 'VN':
            # Vietnam specific fields
            if hasattr(self.env['hr.contract']._fields, 'tupart'):
                update_data['tupart'] = getattr(zoho_employee, 'tu_part', 'YES')
            if hasattr(self.env['hr.contract']._fields, 'shuipart'):
                update_data['shuipart'] = getattr(zoho_employee, 'shui_part', 'YES')
            if hasattr(self.env['hr.contract']._fields, 'costcenter'):
                update_data['costcenter'] = getattr(zoho_employee, 'costcenter', '')
                
        elif self.country == 'ID':
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
    
    def _get_salary_structure_for_country(self, country):
        """Get salary structure for specific country"""
        if country == 'VN':
            structure_name = 'Vietnam Salary Structure'
        elif country == 'ID':
            structure_name = 'Indonesia Salary Structure'
        elif country == 'IN':
            structure_name = 'India Salary Structure'
        else:
            return None
        
        return self.env['hr.payroll.structure'].search([
            ('name', '=', structure_name)
        ], limit=1)
    
    @api.onchange('country')
    def _onchange_country(self):
        """Clear employee selection when country changes"""
        if self.country:
            self.employee_ids = [(5, 0, 0)]  # Clear selection