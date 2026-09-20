# =============================================================================
# FIXED FILE: pb_hr_payroll_base/wizards/payroll_import_wizard.py
# Replace the existing file with this corrected version
# =============================================================================
# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import base64
import csv
import io
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class PayrollImportWizard(models.TransientModel):
    _name = 'payroll.import.wizard'
    _description = 'Payroll Data Import Wizard'

    # Import Configuration
    country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
        ('TH', 'Thailand'),
        ('PH', 'Philippines'),
    ], string='Country', required=True)
    
    import_type = fields.Selection([
        ('payslips', 'Payslip Data'),
        ('salary_components', 'Salary Components'),
        ('deductions', 'Deductions'),
        ('bonuses', 'Bonuses'),
        ('adjustments', 'Adjustments'),
    ], default='payslips', string='Import Type')
    
    period_start = fields.Date('Period Start', required=True)
    period_end = fields.Date('Period End', required=True)

    # File Upload
    import_file = fields.Binary('Import File', required=True)
    import_filename = fields.Char('Filename')
    file_format = fields.Selection([
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('json', 'JSON'),
    ], default='csv', string='File Format')
    has_header_row = fields.Boolean('Has Header Row', default=True)

    # Processing Options
    create_missing_employees = fields.Boolean('Create Missing Employees', default=False)
    update_existing_payslips = fields.Boolean('Update Existing Payslips', default=True)
    validate_data = fields.Boolean('Validate Data', default=True)
    auto_confirm_payslips = fields.Boolean('Auto Confirm Payslips', default=False)

    # Error Handling
    skip_errors = fields.Boolean('Skip Errors', default=True)
    error_threshold = fields.Integer('Error Threshold (%)', default=10)
    send_error_report = fields.Boolean('Send Error Report', default=True)
    error_email_recipients = fields.Many2many('res.users', string='Error Report Recipients')

    # Field Mapping
    employee_number_column = fields.Char('Employee Number Column', default='employee_number')
    employee_name_column = fields.Char('Employee Name Column', default='employee_name')
    employee_email_column = fields.Char('Employee Email Column', default='email')
    department_column = fields.Char('Department Column', default='department')
    basic_salary_column = fields.Char('Basic Salary Column', default='basic_salary')
    gross_salary_column = fields.Char('Gross Salary Column', default='gross_salary')
    net_salary_column = fields.Char('Net Salary Column', default='net_salary')
    deductions_column = fields.Char('Deductions Column', default='deductions')

    field_mapping_ids = fields.One2many('field.mapping', 'wizard_id', string='Field Mappings')

    # Data Validation
    validate_employee_exists = fields.Boolean('Validate Employee Exists', default=True)
    validate_salary_positive = fields.Boolean('Validate Salary Positive', default=True)
    validate_dates = fields.Boolean('Validate Dates', default=True)
    validate_currency = fields.Boolean('Validate Currency', default=True)
    custom_validation_rules = fields.Text('Custom Validation Rules')

    # Preview Data
    preview_data = fields.Text('Preview Data', readonly=True)
    preview_employee_count = fields.Integer('Preview Employee Count', readonly=True)
    preview_total_amount = fields.Float('Preview Total Amount', readonly=True)
    preview_validation_errors = fields.Integer('Preview Validation Errors', readonly=True)

    # Processing Results
    state = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ], default='draft', string='State')
    
    processed_records = fields.Integer('Processed Records', readonly=True)
    failed_records = fields.Integer('Failed Records', readonly=True)
    processing_duration = fields.Float('Processing Duration (s)', readonly=True)
    processing_log = fields.Text('Processing Log', readonly=True)

    @api.onchange('import_file')
    def _onchange_import_file(self):
        """Preview import file when uploaded"""
        if self.import_file:
            try:
                # Decode and preview first few rows
                file_content = base64.b64decode(self.import_file)
                
                if self.file_format == 'csv':
                    reader = csv.DictReader(io.StringIO(file_content.decode('utf-8')))
                    rows = list(reader)[:5]  # Preview first 5 rows
                    self.preview_data = json.dumps(rows, indent=2)
                    self.preview_employee_count = len(rows)
                
            except Exception as e:
                self.preview_data = f"Error reading file: {str(e)}"

    def action_preview_import(self):
        """Load and validate import data"""
        if not self.import_file:
            raise UserError(_('Please upload a file first'))
        
        try:
            rows = self._parse_import_file()
            
            # Validate data
            validation_errors = 0
            for row in rows:
                if self._validate_row(row):
                    validation_errors += 1
            
            self.preview_employee_count = len(rows)
            self.preview_validation_errors = validation_errors
            self.preview_data = json.dumps(rows[:10], indent=2)  # Show first 10 rows
            
        except Exception as e:
            raise UserError(_('Error previewing file: %s') % str(e))

    def action_start_import(self):
        """Start the import process"""
        if not self.import_file:
            raise UserError(_('Please upload a file first'))
        
        self.state = 'processing'
        start_time = datetime.now()
        
        try:
            result = self._process_import_data()
            
            self.processed_records = result['processed']
            self.failed_records = result['failed']
            self.processing_log = result['log']
            self.processing_duration = (datetime.now() - start_time).total_seconds()
            self.state = 'completed'
            
        except Exception as e:
            self.state = 'error'
            self.processing_log = str(e)
            raise UserError(_('Import failed: %s') % str(e))

    def action_download_template(self):
        """Download import template file"""
        # Create template CSV
        headers = [
            self.employee_number_column,
            self.employee_name_column,
            self.employee_email_column,
            self.department_column,
            self.basic_salary_column,
            self.gross_salary_column,
            self.net_salary_column,
            self.deductions_column,
        ]
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        
        # Add sample row
        writer.writerow([
            'EMP001',
            'John Doe',
            'john.doe@company.com',
            'IT Department',
            '5000',
            '6000',
            '4800',
            '1200'
        ])
        
        file_content = output.getvalue().encode('utf-8')
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'data:text/csv;charset=utf-8;base64,{base64.b64encode(file_content).decode()}',
            'target': 'new',
        }

    def _parse_import_file(self):
        """Parse the uploaded file and return rows"""
        file_content = base64.b64decode(self.import_file)
        
        if self.file_format == 'csv':
            reader = csv.DictReader(io.StringIO(file_content.decode('utf-8')))
            return list(reader)
        else:
            raise UserError(_('File format %s not supported yet') % self.file_format)

    def _process_import_data(self):
        """Process the import data"""
        rows = self._parse_import_file()
        processed = 0
        failed = 0
        log_entries = []
        
        for i, row in enumerate(rows, 1):
            try:
                # Validate row
                validation_error = self._validate_row(row)
                if validation_error:
                    if not self.skip_errors:
                        raise UserError(_('Validation error in row %d: %s') % (i, validation_error))
                    else:
                        failed += 1
                        log_entries.append(f"Row {i}: Validation error - {validation_error}")
                        continue
                
                # Process row based on import type
                if self.import_type == 'payslips':
                    self._process_payslip_row(row)
                else:
                    self._process_generic_row(row)
                
                processed += 1
                
                # Check if we should stop due to too many errors
                if failed > 0 and (failed / (processed + failed)) * 100 > self.error_threshold:
                    log_entries.append(_('Error threshold exceeded. Import stopped.'))
                    break
                
            except Exception as e:
                failed += 1
                error_msg = f"Row {i}: {str(e)}"
                log_entries.append(error_msg)
                
                if not self.skip_errors:
                    raise UserError(error_msg)
        
        return {
            'processed': processed,
            'failed': failed,
            'log': '\n'.join(log_entries)
        }

    def _validate_row(self, row):
        """Validate a single row of data"""
        errors = []
        
        # Check required fields
        if not row.get(self.employee_number_column):
            errors.append('Missing employee number')
        
        # Validate employee exists
        if self.validate_employee_exists and row.get(self.employee_number_column):
            employee = self.env['hr.employee'].search([
                ('employee_number', '=', row[self.employee_number_column])
            ], limit=1)
            if not employee:
                errors.append('Employee not found')
        
        # Validate salary is positive
        if self.validate_salary_positive:
            try:
                salary = float(row.get(self.gross_salary_column, 0) or 0)
                if salary < 0:
                    errors.append('Negative salary not allowed')
            except (ValueError, TypeError):
                errors.append('Invalid salary format')
        
        return '; '.join(errors)

    def _process_payslip_row(self, row):
        """Process a single payslip row"""
        # Get employee
        employee = self.env['hr.employee'].search([
            ('employee_number', '=', row[self.employee_number_column])
        ], limit=1)
        
        if not employee:
            if self.create_missing_employees:
                employee = self._create_employee_from_row(row)
            else:
                raise UserError(_('Employee %s not found') % row[self.employee_number_column])
        
        # Check if payslip already exists
        existing_payslip = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('date_from', '=', self.period_start),
            ('date_to', '=', self.period_end),
        ], limit=1)
        
        # FIXED: Complete the if statement that was causing the syntax error
        if existing_payslip:
            if self.update_existing_payslips:
                # Update existing payslip
                existing_payslip.write({
                    'basic_wage': float(row.get(self.basic_salary_column, 0) or 0),
                    # Add other field updates as needed
                })
            else:
                # Skip if we don't want to update existing payslips
                return
        else:
            # Create new payslip
            payslip_vals = {
                'employee_id': employee.id,
                'date_from': self.period_start,
                'date_to': self.period_end,
                'basic_wage': float(row.get(self.basic_salary_column, 0) or 0),
                # Add other field mappings as needed
            }
            
            # Get contract and structure
            contract = employee.contract_id
            if contract and contract.struct_id:
                payslip_vals['struct_id'] = contract.struct_id.id
                payslip_vals['contract_id'] = contract.id
            
            payslip = self.env['hr.payslip'].create(payslip_vals)
            
            if self.auto_confirm_payslips:
                payslip.action_payslip_done()

    def _process_generic_row(self, row):
        """Process other types of import data"""
        # Placeholder for other import types
        pass

    def _create_employee_from_row(self, row):
        """Create employee from import row"""
        employee_vals = {
            'name': row.get(self.employee_name_column),
            'employee_number': row.get(self.employee_number_column),
            'work_email': row.get(self.employee_email_column),
        }
        
        # Add department if provided
        department_name = row.get(self.department_column)
        if department_name:
            department = self.env['hr.department'].search([
                ('name', 'ilike', department_name)
            ], limit=1)
            if department:
                employee_vals['department_id'] = department.id
        
        return self.env['hr.employee'].create(employee_vals)

    def action_download_errors(self):
        """Download error report"""
        if not self.processing_log or self.failed_records == 0:
            raise UserError(_('No errors to download.'))
        
        try:
            # Create error report content
            content = f"Payroll Import Error Report\n"
            content += f"="*50 + "\n"
            content += f"Country: {self.country_code}\n"
            content += f"Import Type: {self.import_type}\n"
            content += f"Period: {self.period_start} to {self.period_end}\n"
            content += f"Processed Records: {self.processed_records}\n"
            content += f"Failed Records: {self.failed_records}\n"
            content += f"Processing Duration: {self.processing_duration:.2f} seconds\n\n"
            content += "Error Details:\n"
            content += "="*50 + "\n"
            content += self.processing_log
            
            content_b64 = base64.b64encode(content.encode('utf-8'))
            
            # Create attachment
            filename = f'payroll_import_errors_{self.country_code}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': content_b64,
                'mimetype': 'text/plain',
                'res_model': self._name,
                'res_id': self.id,
            })
            
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'new',
            }
            
        except Exception as e:
            raise UserError(_('Error creating error report: %s') % str(e))

    def action_preview_import(self):
        """Preview import data"""
        if not self.import_file:
            raise UserError(_('Please upload a file first'))
        
        try:
            rows = self._parse_import_file()
            
            # Validate first few rows and create preview
            validation_errors = 0
            preview_data = []
            
            for i, row in enumerate(rows[:10], 1):  # Preview first 10 rows
                error = self._validate_row(row)
                if error:
                    validation_errors += 1
                preview_data.append({
                    'row': i,
                    'data': row,
                    'error': error
                })
            
            # Update preview fields
            self.preview_employee_count = len(rows)
            self.preview_validation_errors = validation_errors
            
            # Calculate total amount
            total_amount = 0
            try:
                for row in rows:
                    amount = float(row.get(self.gross_salary_column, 0) or 0)
                    total_amount += amount
                self.preview_total_amount = total_amount
            except:
                self.preview_total_amount = 0
            
            # Store preview as JSON
            self.preview_data = json.dumps(preview_data, indent=2, default=str)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Preview Generated'),
                    'message': _('Preview data loaded successfully.'),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise UserError(_('Error generating preview: %s') % str(e))

class FieldMapping(models.TransientModel):
    """Field mapping for import wizard"""
    _name = 'field.mapping'
    _description = 'Field Mapping'
    
    wizard_id = fields.Many2one('payroll.import.wizard', 'Wizard', ondelete='cascade')
    column_name = fields.Char('Column Name', required=True)
    odoo_field = fields.Char('Payobook Field', required=True)
    field_type = fields.Selection([
        ('char', 'Text'),
        ('float', 'Number'),
        ('date', 'Date'),
        ('datetime', 'Date/Time'),
        ('boolean', 'Boolean'),
    ], string='Field Type', default='char')
    is_required = fields.Boolean('Required')
    default_value = fields.Char('Default Value')
    validation_rule = fields.Char('Validation Rule')