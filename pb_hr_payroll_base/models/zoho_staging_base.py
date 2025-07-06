# -*- coding: utf-8 -*-
# Enhanced Zoho Staging Models - Extends om_hr_payroll base functionality

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging
import json

_logger = logging.getLogger(__name__)

class ZohoStagingData(models.Model):
    """Extend base Zoho staging data with multi-country support"""
    _inherit = 'zoho.staging.data'
    
    # === MULTI-COUNTRY ENHANCEMENTS ===
    
    # Processing status for better tracking
    processing_status = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('error', 'Error'),
    ], string='Processing Status', default='draft', index=True)
    
    # Country assignment
    payroll_country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Payroll Country', index=True)
    
    # Processing tracking
    processed_date = fields.Datetime('Processed Date', readonly=True)
    created_employee_id = fields.Many2one('hr.employee', 'Created Employee', readonly=True)
    created_contract_id = fields.Many2one('hr.contract', 'Created Contract', readonly=True)
    error_message = fields.Text('Error Message', readonly=True)
    processing_notes = fields.Text('Processing Notes')
    
    # === VIETNAM-SPECIFIC FIELDS ===
    vn_personal_income_tax = fields.Float('Vietnam PIT')
    vn_social_insurance_employee = fields.Float('VN Social Insurance (Employee)')
    vn_health_insurance_employee = fields.Float('VN Health Insurance (Employee)')
    vn_unemployment_insurance_employee = fields.Float('VN Unemployment Insurance (Employee)')
    vn_union_fee = fields.Float('VN Union Fee')
    
    vn_social_insurance_employer = fields.Float('VN Social Insurance (Employer)')
    vn_health_insurance_employer = fields.Float('VN Health Insurance (Employer)')
    vn_unemployment_insurance_employer = fields.Float('VN Unemployment Insurance (Employer)')
    vn_accident_insurance = fields.Float('VN Accident Insurance')
    
    vn_tax_code = fields.Char('Vietnam Tax Code')
    vn_social_insurance_number = fields.Char('VN Social Insurance Number')
    vn_id_card_number = fields.Char('VN ID Card Number')
    
    # === INDONESIA-SPECIFIC FIELDS ===
    id_pph21_tax = fields.Float('Indonesia PPh21 Tax')
    id_bpjs_kesehatan_employee = fields.Float('BPJS Kesehatan (Employee)')
    id_bpjs_tk_jht_employee = fields.Float('BPJS TK JHT (Employee)')
    id_bpjs_tk_jp_employee = fields.Float('BPJS TK JP (Employee)')
    
    id_bpjs_kesehatan_employer = fields.Float('BPJS Kesehatan (Employer)')
    id_bpjs_tk_jht_employer = fields.Float('BPJS TK JHT (Employer)')
    id_bpjs_tk_jp_employer = fields.Float('BPJS TK JP (Employer)')
    id_bpjs_tk_jkm = fields.Float('BPJS TK JKM')
    id_bpjs_tk_jkk = fields.Float('BPJS TK JKK')
    
    id_npwp_number = fields.Char('NPWP Number')
    id_bpjs_kesehatan_number = fields.Char('BPJS Kesehatan Number')
    id_bpjs_ketenagakerjaan_number = fields.Char('BPJS Ketenagakerjaan Number')
    id_ktp_number = fields.Char('KTP Number')
    
    # === INDIA-SPECIFIC FIELDS ===
    in_income_tax = fields.Float('India Income Tax')
    in_provident_fund_employee = fields.Float('PF (Employee)')
    in_esi_employee = fields.Float('ESI (Employee)')
    in_professional_tax = fields.Float('Professional Tax')
    
    in_provident_fund_employer = fields.Float('PF (Employer)')
    in_esi_employer = fields.Float('ESI (Employer)')
    in_gratuity = fields.Float('Gratuity')
    
    in_pan_number = fields.Char('PAN Number')
    in_aadhaar_number = fields.Char('Aadhaar Number')
    in_pf_number = fields.Char('PF Number')
    in_esi_number = fields.Char('ESI Number')
    
    @api.model
    def create(self, vals):
        """Auto-detect country from data if not specified"""
        if not vals.get('payroll_country'):
            # Try to detect country from specific fields
            if vals.get('vn_tax_code') or vals.get('vn_social_insurance_number'):
                vals['payroll_country'] = 'VN'
            elif vals.get('id_npwp_number') or vals.get('id_bpjs_kesehatan_number'):
                vals['payroll_country'] = 'ID'
            elif vals.get('in_pan_number') or vals.get('in_aadhaar_number'):
                vals['payroll_country'] = 'IN'
        
        return super().create(vals)
    
    def action_process_to_employee(self):
        """Process staging data to create employee and contract"""
        self.ensure_one()
        
        if self.processing_status == 'processed':
            raise UserError(_('This record has already been processed'))
        
        try:
            self.processing_status = 'processing'
            
            # Create employee
            employee = self._create_employee_from_staging()
            
            # Create contract
            contract = self._create_contract_from_staging(employee)
            
            # Update processing status
            self.write({
                'processing_status': 'processed',
                'processed_date': fields.Datetime.now(),
                'created_employee_id': employee.id,
                'created_contract_id': contract.id,
                'error_message': False,
            })
            
            return {
                'type': 'ir.actions.act_window',
                'name': 'Created Employee',
                'res_model': 'hr.employee',
                'res_id': employee.id,
                'view_mode': 'form',
                'target': 'current',
            }
            
        except Exception as e:
            self.write({
                'processing_status': 'error',
                'error_message': str(e),
            })
            raise UserError(_('Error processing data: %s') % str(e))
    
    def _create_employee_from_staging(self):
        """Create employee from staging data"""
        employee_vals = {
            'name': self.full_name_en or self.full_name_vn,
            'employee_id': self.employee_id,
            'work_email': getattr(self, 'email', False),
            'mobile_phone': getattr(self, 'mobile', False),
            'birthday': getattr(self, 'date_of_birth', False),
            'department_id': self._get_or_create_department(),
            'job_id': self._get_or_create_job_position(),
        }
        
        # Add country-specific fields
        if self.payroll_country:
            employee_vals['payroll_country'] = self.payroll_country
        
        return self.env['hr.employee'].create(employee_vals)
    
    def _create_contract_from_staging(self, employee):
        """Create contract from staging data"""
        contract_vals = {
            'name': f"Contract - {employee.name}",
            'employee_id': employee.id,
            'wage': self.base_salary or 0.0,
            'date_start': getattr(self, 'date_of_joining', fields.Date.today()),
            'state': 'draft',
        }
        
        # Get appropriate payroll structure
        if self.payroll_country:
            structure = self.env['hr.payroll.structure'].search([
                ('payroll_country_code', '=', self.payroll_country),
                ('active', '=', True)
            ], limit=1)
            if structure:
                contract_vals['struct_id'] = structure.id
        
        # Add country-specific contract fields
        self._add_country_specific_contract_fields(contract_vals)
        
        return self.env['hr.contract'].create(contract_vals)
    
    def _add_country_specific_contract_fields(self, contract_vals):
        """Add country-specific fields to contract"""
        if self.payroll_country == 'VN':
            contract_vals.update({
                'social_security_number': self.vn_social_insurance_number,
                'tax_identification_number': self.vn_tax_code,
            })
        elif self.payroll_country == 'ID':
            contract_vals.update({
                'social_security_number': self.id_bpjs_ketenagakerjaan_number,
                'tax_identification_number': self.id_npwp_number,
            })
        elif self.payroll_country == 'IN':
            contract_vals.update({
                'social_security_number': self.in_pf_number,
                'tax_identification_number': self.in_pan_number,
            })
    
    def _get_or_create_department(self):
        """Get or create department"""
        if not getattr(self, 'department', False):
            return False
        
        department = self.env['hr.department'].search([
            ('name', '=', self.department)
        ], limit=1)
        
        if not department:
            department = self.env['hr.department'].create({
                'name': self.department
            })
        
        return department.id
    
    def _get_or_create_job_position(self):
        """Get or create job position"""
        if not getattr(self, 'designation', False):
            return False
        
        job = self.env['hr.job'].search([
            ('name', '=', self.designation)
        ], limit=1)
        
        if not job:
            job = self.env['hr.job'].create({
                'name': self.designation
            })
        
        return job.id
    
    @api.model
    def process_batch_by_country(self, country_code):
        """Process all draft records for a specific country"""
        records = self.search([
            ('payroll_country', '=', country_code),
            ('processing_status', '=', 'draft')
        ])
        
        success_count = 0
        error_count = 0
        
        for record in records:
            try:
                record.action_process_to_employee()
                success_count += 1
            except Exception as e:
                error_count += 1
                _logger.error(f"Error processing record {record.id}: {str(e)}")
        
        return {
            'success_count': success_count,
            'error_count': error_count,
            'total_processed': len(records)
        }