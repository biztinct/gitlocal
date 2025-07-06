# -*- coding: utf-8 -*-
# Zoho Staging Wizard - Extracted from zoho_staging_base.py

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import csv
import io
import logging

_logger = logging.getLogger(__name__)

class ZohoStagingImportWizard(models.TransientModel):
    """Multi-Country Zoho Import Wizard"""
    _name = 'zoho.staging.import.wizard'
    _description = 'Zoho Staging Import Wizard'
    
    import_file = fields.Binary('Import File', required=True)
    import_filename = fields.Char('Filename')
    target_country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Target Country', required=True)
    
    import_mode = fields.Selection([
        ('create_only', 'Create Only'),
        ('update_only', 'Update Only'),
        ('create_update', 'Create or Update'),
    ], string='Import Mode', default='create_only')
    
    auto_create_employees = fields.Boolean('Auto Create Employees', default=True)
    auto_create_contracts = fields.Boolean('Auto Create Contracts', default=True)
    update_existing = fields.Boolean('Update Existing Records', default=False)
    validate_data = fields.Boolean('Validate Data', default=True)
    
    country_mapping_ids = fields.One2many('zoho.staging.field.mapping', 'wizard_id', 'Field Mappings')
    
    # Preview fields
    preview_data = fields.Text('Preview Data', readonly=True)
    import_summary = fields.Text('Import Summary', readonly=True)
    
    @api.onchange('target_country')
    def _onchange_target_country(self):
        """Update field mappings based on target country"""
        if self.target_country:
            self._setup_default_mappings()
    
    def _setup_default_mappings(self):
        """Setup default field mappings for the selected country"""
        mappings = []
        
        # Common mappings for all countries
        common_mappings = [
            ('employee_id', 'employee_id', 'char', True),
            ('full_name_en', 'full_name_en', 'char', True),
            ('email', 'email', 'char', False),
            ('mobile', 'mobile', 'char', False),
            ('date_of_birth', 'date_of_birth', 'date', False),
            ('date_of_joining', 'date_of_joining', 'date', False),
            ('department', 'department', 'char', False),
            ('designation', 'designation', 'char', False),
            ('base_salary', 'base_salary', 'float', True),
        ]
        
        # Country-specific mappings
        if self.target_country == 'VN':
            country_mappings = [
                ('vn_tax_code', 'vn_tax_code', 'char', False),
                ('vn_social_insurance_number', 'vn_social_insurance_number', 'char', False),
                ('vn_personal_income_tax', 'vn_personal_income_tax', 'float', False),
            ]
        elif self.target_country == 'ID':
            country_mappings = [
                ('id_npwp_number', 'id_npwp_number', 'char', False),
                ('id_bpjs_kesehatan_number', 'id_bpjs_kesehatan_number', 'char', False),
                ('id_pph21_tax', 'id_pph21_tax', 'float', False),
            ]
        elif self.target_country == 'IN':
            country_mappings = [
                ('in_pan_number', 'in_pan_number', 'char', False),
                ('in_aadhaar_number', 'in_aadhaar_number', 'char', False),
                ('in_income_tax', 'in_income_tax', 'float', False),
            ]
        else:
            country_mappings = []
        
        all_mappings = common_mappings + country_mappings
        
        # Create mapping records
        for source, target, data_type, required in all_mappings:
            mappings.append((0, 0, {
                'source_field': source,
                'target_field': target,
                'data_type': data_type,
                'required': required,
            }))
        
        self.country_mapping_ids = mappings
    
    def action_preview_data(self):
        """Preview import data"""
        if not self.import_file:
            raise UserError(_('Please select a file to import'))
        
        try:
            # Decode file content
            file_content = base64.b64decode(self.import_file)
            
            # Parse CSV content
            if self.import_filename and self.import_filename.endswith('.csv'):
                content = file_content.decode('utf-8')
                csv_reader = csv.DictReader(io.StringIO(content))
                rows = list(csv_reader)
            else:
                raise UserError(_('Only CSV files are supported currently'))
            
            # Generate preview
            preview_lines = []
            preview_lines.append(f"File: {self.import_filename}")
            preview_lines.append(f"Total rows: {len(rows)}")
            preview_lines.append(f"Target country: {self.target_country}")
            preview_lines.append("")
            
            if rows:
                preview_lines.append("Sample data (first 3 rows):")
                for i, row in enumerate(rows[:3], 1):
                    preview_lines.append(f"Row {i}: {dict(row)}")
                
                preview_lines.append("")
                preview_lines.append("Available fields:")
                if rows:
                    preview_lines.append(", ".join(rows[0].keys()))
            
            self.preview_data = "\n".join(preview_lines)
            
        except Exception as e:
            raise UserError(_('Error previewing file: %s') % str(e))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zoho.staging.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_import_data(self):
        """Import data from file"""
        if not self.import_file:
            raise UserError(_('Please select a file to import'))
        
        try:
            # Decode and parse file
            file_content = base64.b64decode(self.import_file)
            content = file_content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(content))
            rows = list(csv_reader)
            
            # Create field mapping dictionary
            field_mapping = {}
            for mapping in self.country_mapping_ids:
                field_mapping[mapping.source_field] = {
                    'target': mapping.target_field,
                    'type': mapping.data_type,
                    'required': mapping.required,
                    'default': mapping.default_value,
                }
            
            # Process each row
            created_count = 0
            error_count = 0
            errors = []
            
            for row_num, row in enumerate(rows, 1):
                try:
                    staging_vals = {'payroll_country': self.target_country}
                    
                    # Map fields according to configuration
                    for source_field, config in field_mapping.items():
                        target_field = config['target']
                        value = row.get(source_field, config.get('default', ''))
                        
                        # Convert value based on data type
                        if config['type'] == 'float':
                            staging_vals[target_field] = float(value) if value else 0.0
                        elif config['type'] == 'date':
                            if value:
                                staging_vals[target_field] = value
                        elif config['type'] == 'boolean':
                            staging_vals[target_field] = value.lower() in ('true', '1', 'yes')
                        else:
                            staging_vals[target_field] = value
                    
                    # Create staging record
                    self.env['zoho.staging.data'].create(staging_vals)
                    created_count += 1
                    
                except Exception as e:
                    error_count += 1
                    errors.append(f"Row {row_num}: {str(e)}")
            
            # Generate summary
            summary_lines = [
                f"Import completed for {self.target_country}",
                f"Total rows processed: {len(rows)}",
                f"Successfully created: {created_count}",
                f"Errors: {error_count}",
            ]
            
            if errors:
                summary_lines.append("\nErrors:")
                summary_lines.extend(errors[:10])  # Show first 10 errors
                if len(errors) > 10:
                    summary_lines.append(f"... and {len(errors) - 10} more errors")
            
            self.import_summary = "\n".join(summary_lines)
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'zoho.staging.import.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }
            
        except Exception as e:
            raise UserError(_('Error importing data: %s') % str(e))

class ZohoStagingFieldMapping(models.TransientModel):
    """Field mapping for import wizard"""
    _name = 'zoho.staging.field.mapping'
    _description = 'Zoho Staging Field Mapping'
    
    wizard_id = fields.Many2one('zoho.staging.import.wizard', 'Wizard', ondelete='cascade')
    source_field = fields.Char('Source Field', required=True)
    target_field = fields.Char('Target Field', required=True)
    data_type = fields.Selection([
        ('char', 'Text'),
        ('float', 'Number'),
        ('date', 'Date'),
        ('datetime', 'Date/Time'),
        ('boolean', 'Boolean'),
    ], string='Data Type', default='char')
    required = fields.Boolean('Required')
    default_value = fields.Char('Default Value')