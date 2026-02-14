# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import base64
import csv
import io
import json
import requests
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class EmployeeImportWizard(models.TransientModel):
    _name = 'employee.import.wizard'
    _description = 'Employee Import Wizard'

    # Import Source
    import_source = fields.Selection([
        ('file', 'File Upload'),
        ('zoho', 'Zoho People'),
        ('api', 'External API'),
    ], default='file', string='Import Source', required=True)
    
    country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
        ('TH', 'Thailand'),
        ('PH', 'Philippines'),
    ], string='Country', required=True)

    # File Upload
    import_file = fields.Binary('Import File')
    import_filename = fields.Char('Filename')
    data_source_url = fields.Char('API URL')

    # Processing Options
    update_existing = fields.Boolean('Update Existing Employees', default=True)
    create_contracts = fields.Boolean('Create Contracts', default=True)
    auto_assign_structure = fields.Boolean('Auto Assign Payroll Structure', default=True)
    send_welcome_email = fields.Boolean('Send Welcome Email', default=False)

    # Zoho Integration
    zoho_api_key = fields.Char('Zoho API Key')
    zoho_org_id = fields.Char('Zoho Organization ID')
    zoho_department_filter = fields.Char('Department Filter')
    zoho_last_sync_date = fields.Datetime('Last Sync Date')
    zoho_sync_active_only = fields.Boolean('Sync Active Only', default=True)

    # Field Mapping
    name_field = fields.Char('Name Field', default='name')
    email_field = fields.Char('Email Field', default='email')
    phone_field = fields.Char('Phone Field', default='phone')
    employee_number_field = fields.Char('Employee Number Field', default='employee_number')
    department_field = fields.Char('Department Field', default='department')
    job_title_field = fields.Char('Job Title Field', default='job_title')
    manager_field = fields.Char('Manager Field', default='manager')
    join_date_field = fields.Char('Join Date Field', default='join_date')
    birthday_field = fields.Char('Birthday Field', default='birthday')
    gender_field = fields.Char('Gender Field', default='gender')
    address_field = fields.Char('Address Field', default='address')
    emergency_contact_field = fields.Char('Emergency Contact Field', default='emergency_contact')
    salary_field = fields.Char('Salary Field', default='salary')
    currency_field = fields.Char('Currency Field', default='currency')
    payment_method_field = fields.Char('Payment Method Field', default='payment_method')
    bank_account_field = fields.Char('Bank Account Field', default='bank_account')

    custom_field_mappings = fields.One2many('custom.field.mapping', 'wizard_id', string='Custom Field Mappings')

    # Data Validation
    validate_email_format = fields.Boolean('Validate Email Format', default=True)
    validate_phone_format = fields.Boolean('Validate Phone Format', default=True)
    validate_required_fields = fields.Boolean('Validate Required Fields', default=True)
    validate_duplicate_employees = fields.Boolean('Validate Duplicate Employees', default=True)
    auto_format_names = fields.Boolean('Auto Format Names', default=True)
    auto_format_emails = fields.Boolean('Auto Format Emails', default=True)
    normalize_phone_numbers = fields.Boolean('Normalize Phone Numbers', default=True)
    default_country_id = fields.Many2one('res.country', 'Default Country')
    custom_validation_code = fields.Text('Custom Validation Code')

    # Contract Creation
    default_contract_type = fields.Many2one('hr.contract.type', 'Default Contract Type')
    default_wage = fields.Float('Default Wage')
    default_currency_id = fields.Many2one('res.currency', 'Default Currency')
    default_working_hours = fields.Many2one('resource.calendar', 'Default Working Hours')
    payroll_structure_id = fields.Many2one('hr.payroll.structure', 'Payroll Structure')
    contract_start_date = fields.Date('Contract Start Date', default=fields.Date.today)
    contract_state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Running'),
    ], default='draft', string='Initial Contract State')

    # Preview Data
    preview_data = fields.Text('Preview Data', readonly=True)
    preview_employee_count = fields.Integer('Preview Employee Count', readonly=True)
    preview_new_employees = fields.Integer('Preview New Employees', readonly=True)
    preview_existing_employees = fields.Integer('Preview Existing Employees', readonly=True)
    preview_validation_errors = fields.Integer('Preview Validation Errors', readonly=True)

    # Import Results
    state = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ], default='draft', string='State')
    
    imported_count = fields.Integer('Imported Count', readonly=True)
    updated_count = fields.Integer('Updated Count', readonly=True)
    failed_count = fields.Integer('Failed Count', readonly=True)
    contracts_created = fields.Integer('Contracts Created', readonly=True)
    start_time = fields.Datetime('Start Time', readonly=True)
    end_time = fields.Datetime('End Time', readonly=True)
    processing_duration = fields.Float('Processing Duration (seconds)', readonly=True)
    import_log = fields.Text('Import Log', readonly=True)
    error_details = fields.Text('Error Details', readonly=True)

    @api.onchange('country_code')
    def _onchange_country_code(self):
        """Set defaults based on country"""
        if self.country_code:
            # Set default country
            country = self.env['res.country'].search([('code', '=', self.country_code)], limit=1)
            if country:
                self.default_country_id = country.id
            
            # Set default currency
            currency_map = {
                'VN': 'VND', 'ID': 'IDR', 'IN': 'INR',
                'SG': 'SGD', 'MY': 'MYR', 'TH': 'THB', 'PH': 'PHP'
            }
            currency_code = currency_map.get(self.country_code)
            if currency_code:
                currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
                if currency:
                    self.default_currency_id = currency.id
            
            # Set payroll structure
            structure = self.env['hr.payroll.structure'].search([
                ('payroll_country_code', '=', self.country_code),
                ('active', '=', True)
            ], limit=1)
            if structure:
                self.payroll_structure_id = structure.id

    def action_test_zoho_connection(self):
        """Test Zoho API connection"""
        if self.import_source != 'zoho':
            raise UserError(_('This action is only available for Zoho import.'))
        
        if not self.zoho_api_key or not self.zoho_org_id:
            raise UserError(_('Please provide Zoho API Key and Organization ID.'))
        
        try:
            # Test API connection (simplified)
            url = f"https://people.zoho.com/api/forms/P_EmployeeView/records"
            headers = {
                'Authorization': f'Zoho-oauthtoken {self.zoho_api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _('Successfully connected to Zoho People API.'),
                        'type': 'success',
                    }
                }
            else:
                raise UserError(_('Connection failed with status code: %s') % response.status_code)
        
        except requests.exceptions.RequestException as e:
            raise UserError(_('Connection error: %s') % str(e))

    def action_load_preview(self):
        """Load preview of import data"""
        self.ensure_one()
        
        try:
            if self.import_source == 'file':
                preview_data = self._load_file_preview()
            elif self.import_source == 'zoho':
                preview_data = self._load_zoho_preview()
            elif self.import_source == 'api':
                preview_data = self._load_api_preview()
            else:
                raise UserError(_('Invalid import source.'))
            
            # Store preview data (first 10 records)
            self.preview_data = json.dumps(preview_data[:10], indent=2, default=str)
            
            # Calculate preview statistics
            self._calculate_preview_statistics(preview_data)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Preview Loaded'),
                    'message': _('Preview data loaded successfully.'),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise UserError(_('Error loading preview: %s') % str(e))

    def _load_file_preview(self):
        """Load preview from uploaded file"""
        if not self.import_file:
            raise UserError(_('Please upload a file first.'))
        
        file_data = base64.b64decode(self.import_file)
        
        if self.import_filename.endswith('.csv'):
            return self._parse_csv_file(file_data)
        elif self.import_filename.endswith(('.xlsx', '.xls')):
            return self._parse_excel_file(file_data)
        elif self.import_filename.endswith('.json'):
            return self._parse_json_file(file_data)
        else:
            raise UserError(_('Unsupported file format. Please use CSV, Excel, or JSON.'))

    def _load_zoho_preview(self):
        """Load preview from Zoho People"""
        if not self.zoho_api_key or not self.zoho_org_id:
            raise UserError(_('Please provide Zoho API credentials.'))
        
        try:
            url = f"https://people.zoho.com/api/forms/P_EmployeeView/records"
            headers = {
                'Authorization': f'Zoho-oauthtoken {self.zoho_api_key}',
                'Content-Type': 'application/json'
            }
            
            params = {
                'limit': 50,  # Preview limit
            }
            
            if self.zoho_department_filter:
                params['searchColumn'] = 'Department'
                params['searchValue'] = self.zoho_department_filter
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data.get('response', {}).get('result', [])
            
        except requests.exceptions.RequestException as e:
            raise UserError(_('Error connecting to Zoho: %s') % str(e))

    def _load_api_preview(self):
        """Load preview from external API"""
        if not self.data_source_url:
            raise UserError(_('Please provide API URL.'))
        
        try:
            response = requests.get(self.data_source_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if isinstance(data, list):
                return data
            else:
                return [data]
                
        except requests.exceptions.RequestException as e:
            raise UserError(_('Error connecting to API: %s') % str(e))

    def _parse_csv_file(self, file_data):
        """Parse CSV file"""
        csv_content = file_data.decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_content))
        return list(reader)

    def _parse_excel_file(self, file_data):
        """Parse Excel file"""
        try:
            import openpyxl
            workbook = openpyxl.load_workbook(io.BytesIO(file_data))
            sheet = workbook.active
            
            # Get headers
            headers = [cell.value for cell in sheet[1]]
            
            data = []
            for row in sheet.iter_rows(min_row=2, values_only=True):
                row_data = dict(zip(headers, row))
                data.append(row_data)
            
            return data
            
        except ImportError:
            raise UserError(_('openpyxl library is required for Excel file processing.'))

    def _parse_json_file(self, file_data):
        """Parse JSON file"""
        json_content = file_data.decode('utf-8')
        data = json.loads(json_content)
        
        if isinstance(data, list):
            return data
        else:
            return [data]

    def _calculate_preview_statistics(self, preview_data):
        """Calculate preview statistics"""
        self.preview_employee_count = len(preview_data)
        
        new_employees = 0
        existing_employees = 0
        validation_errors = 0
        
        for record in preview_data:
            # Check if employee exists
            employee_number = record.get(self.employee_number_field)
            if employee_number:
                existing = self.env['hr.employee'].search([
                    ('employee_number', '=', employee_number)
                ], limit=1)
                if existing:
                    existing_employees += 1
                else:
                    new_employees += 1
            
            # Basic validation
            if not record.get(self.name_field):
                validation_errors += 1
            
            if self.validate_email_format and record.get(self.email_field):
                email = record[self.email_field]
                if '@' not in email:
                    validation_errors += 1
        
        self.preview_new_employees = new_employees
        self.preview_existing_employees = existing_employees
        self.preview_validation_errors = validation_errors

    def action_start_import(self):
        """Start the employee import process"""
        self.ensure_one()
        
        try:
            self.state = 'processing'
            self.start_time = fields.Datetime.now()
            
            # Load all data
            if self.import_source == 'file':
                import_data = self._load_file_preview()
            elif self.import_source == 'zoho':
                import_data = self._load_all_zoho_data()
            elif self.import_source == 'api':
                import_data = self._load_api_preview()
            else:
                raise UserError(_('Invalid import source.'))
            
            # Process the import
            results = self._process_employee_import(import_data)
            
            # Update results
            self.end_time = fields.Datetime.now()
            self.processing_duration = (self.end_time - self.start_time).total_seconds()
            self.imported_count = results['imported']
            self.updated_count = results['updated']
            self.failed_count = results['failed']
            self.contracts_created = results['contracts_created']
            self.import_log = results['log']
            self.error_details = results['errors']
            self.state = 'completed'
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Import Completed'),
                    'message': _('Imported %d employees, updated %d, %d failed.') % (
                        results['imported'], results['updated'], results['failed']
                    ),
                    'type': 'success' if results['failed'] == 0 else 'warning',
                }
            }
            
        except Exception as e:
            self.state = 'error'
            self.error_details = str(e)
            _logger.error(f"Error in employee import: {str(e)}")
            raise UserError(_('Import failed: %s') % str(e))

    def _load_all_zoho_data(self):
        """Load all data from Zoho (not just preview)"""
        # Implementation similar to _load_zoho_preview but without limit
        if not self.zoho_api_key or not self.zoho_org_id:
            raise UserError(_('Please provide Zoho API credentials.'))
        
        try:
            url = f"https://people.zoho.com/api/forms/P_EmployeeView/records"
            headers = {
                'Authorization': f'Zoho-oauthtoken {self.zoho_api_key}',
                'Content-Type': 'application/json'
            }
            
            params = {}
            if self.zoho_department_filter:
                params['searchColumn'] = 'Department'
                params['searchValue'] = self.zoho_department_filter
            
            if self.zoho_sync_active_only:
                params['searchColumn'] = 'Employee_Status'
                params['searchValue'] = 'Active'
            
            response = requests.get(url, headers=headers, params=params, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            return data.get('response', {}).get('result', [])
            
        except requests.exceptions.RequestException as e:
            raise UserError(_('Error connecting to Zoho: %s') % str(e))

    def _process_employee_import(self, import_data):
        """Process the employee import data"""
        imported = 0
        updated = 0
        failed = 0
        contracts_created = 0
        log_entries = []
        error_entries = []
        
        for i, record in enumerate(import_data, 1):
            try:
                # Validate record
                if self.validate_required_fields:
                    validation_errors = self._validate_employee_record(record)
                    if validation_errors:
                        failed += 1
                        error_entries.append(f"Row {i}: {validation_errors}")
                        continue
                
                # Process employee
                employee, is_new = self._process_employee_record(record)
                
                if is_new:
                    imported += 1
                    log_entries.append(f"Imported employee: {employee.name}")
                else:
                    updated += 1
                    log_entries.append(f"Updated employee: {employee.name}")
                
                # Create contract if requested
                if self.create_contracts and employee:
                    contract = self._create_employee_contract(employee, record)
                    if contract:
                        contracts_created += 1
                        log_entries.append(f"Created contract for: {employee.name}")
                
                # Send welcome email if requested
                if self.send_welcome_email and is_new:
                    self._send_welcome_email(employee)
                
            except Exception as e:
                failed += 1
                error_msg = f"Row {i}: {str(e)}"
                error_entries.append(error_msg)
                log_entries.append(error_msg)
        
        return {
            'imported': imported,
            'updated': updated,
            'failed': failed,
            'contracts_created': contracts_created,
            'log': '\n'.join(log_entries),
            'errors': '\n'.join(error_entries)
        }

    def _validate_employee_record(self, record):
        """Validate employee record"""
        errors = []
        
        # Check required name field
        if not record.get(self.name_field):
            errors.append('Missing employee name')
        
        # Validate email format
        if self.validate_email_format and record.get(self.email_field):
            email = record[self.email_field]
            if '@' not in email or '.' not in email:
                errors.append('Invalid email format')
        
        # Check for duplicates
        if self.validate_duplicate_employees and record.get(self.employee_number_field):
            existing = self.env['hr.employee'].search([
                ('employee_number', '=', record[self.employee_number_field])
            ], limit=1)
            if existing and not self.update_existing:
                errors.append('Duplicate employee number')
        
        # Custom validation
        if self.custom_validation_code:
            try:
                # Execute custom validation code
                local_vars = {'record': record, 'errors': errors}
                exec(self.custom_validation_code, {}, local_vars)
                errors = local_vars.get('errors', errors)
            except Exception as e:
                errors.append(f'Custom validation error: {str(e)}')
        
        return '; '.join(errors)

    def _process_employee_record(self, record):
        """Process a single employee record"""
        # Check if employee exists
        employee_number = record.get(self.employee_number_field)
        existing_employee = None
        
        if employee_number:
            existing_employee = self.env['hr.employee'].search([
                ('employee_number', '=', employee_number)
            ], limit=1)
        
        if existing_employee:
            if self.update_existing:
                self._update_employee_from_record(existing_employee, record)
                return existing_employee, False
            else:
                raise UserError(_('Employee %s already exists') % employee_number)
        else:
            new_employee = self._create_employee_from_record(record)
            return new_employee, True

    def _create_employee_from_record(self, record):
        """Create new employee from record"""
        # Prepare employee data
        employee_data = {
            'name': self._format_name(record.get(self.name_field, 'Unknown')),
            'employee_number': record.get(self.employee_number_field),
            'work_email': self._format_email(record.get(self.email_field)),
            'work_phone': self._format_phone(record.get(self.phone_field)),
            'country_id': self.default_country_id.id if self.default_country_id else False,
        }
        
        # Add optional fields
        if record.get(self.birthday_field):
            try:
                birthday = self._parse_date(record[self.birthday_field])
                employee_data['birthday'] = birthday
            except:
                pass
        
        if record.get(self.gender_field):
            gender = record[self.gender_field].lower()
            if gender in ['male', 'm']:
                employee_data['gender'] = 'male'
            elif gender in ['female', 'f']:
                employee_data['gender'] = 'female'
        
        if record.get(self.address_field):
            employee_data['private_street'] = record[self.address_field]
        
        # Set department
        if record.get(self.department_field):
            department = self._get_or_create_department(record[self.department_field])
            if department:
                employee_data['department_id'] = department.id
        
        # Set job title
        if record.get(self.job_title_field):
            job = self._get_or_create_job(record[self.job_title_field])
            if job:
                employee_data['job_id'] = job.id
        
        # Set manager
        if record.get(self.manager_field):
            manager = self._find_manager(record[self.manager_field])
            if manager:
                employee_data['parent_id'] = manager.id
        
        return self.env['hr.employee'].create(employee_data)

    def _update_employee_from_record(self, employee, record):
        """Update existing employee from record"""
        update_data = {}
        
        # Update basic fields
        if record.get(self.name_field):
            update_data['name'] = self._format_name(record[self.name_field])
        
        if record.get(self.email_field):
            update_data['work_email'] = self._format_email(record[self.email_field])
        
        if record.get(self.phone_field):
            update_data['work_phone'] = self._format_phone(record[self.phone_field])
        
        # Update other fields as needed
        if record.get(self.department_field):
            department = self._get_or_create_department(record[self.department_field])
            if department:
                update_data['department_id'] = department.id
        
        if record.get(self.job_title_field):
            job = self._get_or_create_job(record[self.job_title_field])
            if job:
                update_data['job_id'] = job.id
        
        if update_data:
            employee.write(update_data)

    def _create_employee_contract(self, employee, record):
        """Create contract for employee"""
        if not self.create_contracts:
            return None
        
        # Check if contract already exists
        existing_contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ['open', 'draft'])
        ], limit=1)
        
        if existing_contract:
            return existing_contract
        
        # Prepare contract data
        contract_data = {
            'name': f"Contract - {employee.name}",
            'employee_id': employee.id,
            'date_start': self.contract_start_date,
            'state': self.contract_state,
            'wage': record.get(self.salary_field, self.default_wage or 0),
            'currency_id': self.default_currency_id.id if self.default_currency_id else self.env.company.currency_id.id,
        }
        
        # Set contract type
        if self.default_contract_type:
            contract_data['type_id'] = self.default_contract_type.id
        
        # Set working hours
        if self.default_working_hours:
            contract_data['resource_calendar_id'] = self.default_working_hours.id
        
        # Set payroll structure
        if self.payroll_structure_id:
            contract_data['struct_id'] = self.payroll_structure_id.id
        
        # Add country-specific fields
        if self.country_code:
            contract_data['payroll_country_code'] = self.country_code
        
        return self.env['hr.contract'].create(contract_data)

    # Helper methods for data formatting and lookup
    
    def _format_name(self, name):
        """Format employee name"""
        if self.auto_format_names and name:
            return ' '.join(word.capitalize() for word in name.split())
        return name

    def _format_email(self, email):
        """Format email address"""
        if self.auto_format_emails and email:
            return email.lower().strip()
        return email

    def _format_phone(self, phone):
        """Format phone number"""
        if self.normalize_phone_numbers and phone:
            # Basic phone normalization
            import re
            phone = re.sub(r'[^\d+]', '', phone)
            return phone
        return phone

    def _parse_date(self, date_str):
        """Parse date string"""
        if not date_str:
            return None
        
        # Try common date formats
        formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']
        
        for fmt in formats:
            try:
                return datetime.strptime(str(date_str), fmt).date()
            except ValueError:
                continue
        
        raise ValueError(f"Unable to parse date: {date_str}")

    def _get_or_create_department(self, dept_name):
        """Get or create department"""
        if not dept_name:
            return None
        
        department = self.env['hr.department'].search([
            ('name', '=', dept_name)
        ], limit=1)
        
        if not department:
            department = self.env['hr.department'].create({
                'name': dept_name
            })
        
        return department

    def _get_or_create_job(self, job_title):
        """Get or create job position"""
        if not job_title:
            return None
        
        job = self.env['hr.job'].search([
            ('name', '=', job_title)
        ], limit=1)
        
        if not job:
            job = self.env['hr.job'].create({
                'name': job_title
            })
        
        return job

    def _find_manager(self, manager_info):
        """Find manager by name or employee number"""
        if not manager_info:
            return None
        
        # Try to find by employee number first
        manager = self.env['hr.employee'].search([
            ('employee_number', '=', manager_info)
        ], limit=1)
        
        if not manager:
            # Try to find by name
            manager = self.env['hr.employee'].search([
                ('name', 'ilike', manager_info)
            ], limit=1)
        
        return manager

    def _send_welcome_email(self, employee):
        """Send welcome email to new employee"""
        try:
            if not employee.work_email:
                return
            
            # Create welcome email
            template = self.env.ref('hr.mail_template_employee_welcome', raise_if_not_found=False)
            if template:
                template.send_mail(employee.id, force_send=True)
            
        except Exception as e:
            _logger.warning(f"Error sending welcome email to {employee.name}: {str(e)}")

    # Action methods
    
    def action_download_template(self):
        """Download employee import template"""
        try:
            # Create CSV template
            headers = [
                self.name_field,
                self.employee_number_field,
                self.email_field,
                self.phone_field,
                self.department_field,
                self.job_title_field,
                self.salary_field,
                self.join_date_field,
                self.birthday_field,
                self.gender_field,
            ]
            
            # Sample data
            sample_data = [
                ['John Doe', 'EMP001', 'john@example.com', '+1234567890', 'IT', 'Software Developer', '5000', '2024-01-01', '1990-05-15', 'Male'],
                ['Jane Smith', 'EMP002', 'jane@example.com', '+1234567891', 'HR', 'HR Manager', '6000', '2024-01-02', '1988-08-20', 'Female'],
            ]
            
            # Create CSV content
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(headers)
            writer.writerows(sample_data)
            
            csv_content = output.getvalue().encode('utf-8')
            csv_b64 = base64.b64encode(csv_content)
            
            # Create attachment
            filename = f'employee_import_template_{self.country_code}.csv'
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': csv_b64,
                'mimetype': 'text/csv',
                'res_model': self._name,
                'res_id': self.id,
            })
            
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'new',
            }
            
        except Exception as e:
            raise UserError(_('Error creating template: %s') % str(e))

    def action_download_error_report(self):
        """Download error report"""
        if not self.error_details:
            raise UserError(_('No errors to download.'))
        
        try:
            # Create error report content
            content = f"Employee Import Error Report\n"
            content += f"Country: {self.country_code}\n"
            content += f"Import Source: {self.import_source}\n"
            content += f"Imported: {self.imported_count}\n"
            content += f"Updated: {self.updated_count}\n"
            content += f"Failed: {self.failed_count}\n"
            content += f"Duration: {self.processing_duration:.2f} seconds\n\n"
            content += "Error Details:\n"
            content += self.error_details
            
            content_b64 = base64.b64encode(content.encode('utf-8'))
            
            # Create attachment
            filename = f'employee_import_errors_{self.country_code}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
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

    def action_view_imported_employees(self):
        """View imported employees"""
        if self.imported_count == 0:
            raise UserError(_('No employees were imported.'))
        
        return {
            'name': _('Imported Employees'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('country_id.code', '=', self.country_code)],
            'context': {'create': False},
        }

    @api.constrains('zoho_api_key')
    def _check_zoho_credentials(self):
        """Basic validation of Zoho credentials"""
        for record in self:
            if record.import_source == 'zoho' and record.zoho_api_key:
                if len(record.zoho_api_key) < 10:
                    raise ValidationError(_('Zoho API key seems too short.'))


class CustomFieldMapping(models.TransientModel):
    _name = 'custom.field.mapping'
    _description = 'Custom Field Mapping for Employee Import'

    wizard_id = fields.Many2one('employee.import.wizard', string='Wizard', ondelete='cascade')
    source_field = fields.Char('Source Field', required=True)
    target_field = fields.Selection([
        ('employee_number', 'Employee Number'),
        ('name', 'Name'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('department', 'Department'),
        ('job_title', 'Job Title'),
        ('manager', 'Manager'),
        ('salary', 'Salary'),
        ('join_date', 'Join Date'),
        ('birthday', 'Birthday'),
        ('gender', 'Gender'),
        ('address', 'Address'),
        ('emergency_contact', 'Emergency Contact'),
    ], string='Target Field', required=True)
    field_type = fields.Selection([
        ('char', 'Text'),
        ('float', 'Number'),
        ('date', 'Date'),
        ('boolean', 'Boolean'),
        ('selection', 'Selection'),
    ], default='char', string='Field Type')
    transformation_rule = fields.Text('Transformation Rule',
                                    help='Python code to transform the value. Use "value" variable.')
    is_required = fields.Boolean('Required', default=False)
    default_value = fields.Char('Default Value')