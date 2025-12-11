# -*- coding: utf-8 -*-

import logging
import json
from datetime import date, datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


def json_serializer(obj):
    """Custom JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class HrPayrollImportBatch(models.Model):
    """
    Batch processing model for payroll import from Excel/connectors.
    This is a NEW staging model - does NOT use existing zoho staging tables.
    """
    _name = 'hr.payroll.import.batch'
    _description = 'Payroll Import Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Batch Name',
        required=True,
        tracking=True,
        default=lambda self: _('New Import Batch')
    )

    # Source Configuration
    source_type = fields.Selection([
        ('excel', 'Excel/CSV File'),
        ('connector', 'Integration Connector'),
        ('manual', 'Manual Entry'),
    ], string='Source Type', required=True, default='excel', tracking=True)

    connector_id = fields.Many2one(
        'hr.integration.connector',
        string='Connector',
        domain="[('connector_type', 'in', ['excel', 'zoho', 'sap', 'workday', 'oracle'])]"
    )

    formula_config_id = fields.Many2one(
        'hr.formula.config',
        string='Formula Configuration',
        required=True,
        tracking=True,
        help="Formula configuration to use for salary calculations"
    )

    # File Import Fields
    import_file = fields.Binary(string='Import File', attachment=True)
    import_filename = fields.Char(string='Filename')
    file_header_row = fields.Integer(
        string='Header Row',
        default=1,
        help="Row number containing column headers (1-based)"
    )
    file_data_start_row = fields.Integer(
        string='Data Start Row',
        default=2,
        help="Row number where data starts (1-based)"
    )
    file_sheet_name = fields.Char(
        string='Sheet Name',
        default='Sheet1',
        help="Name of the Excel sheet to import (leave empty for first sheet)"
    )

    # Period Information
    payroll_period = fields.Selection([
        ('current', 'Current Month'),
        ('previous', 'Previous Month'),
        ('custom', 'Custom Period'),
    ], string='Payroll Period', default='current', required=True)

    date_from = fields.Date(string='Period Start')
    date_to = fields.Date(string='Period End')

    # Country and Company
    country_code = fields.Selection(
        related='formula_config_id.country_code',
        string='Country',
        store=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    # Import Lines (Staging Data)
    import_line_ids = fields.One2many(
        'hr.payroll.import.line',
        'batch_id',
        string='Import Lines'
    )

    # Statistics
    total_lines = fields.Integer(
        string='Total Lines',
        compute='_compute_statistics',
        store=True
    )
    matched_employees = fields.Integer(
        string='Matched Employees',
        compute='_compute_statistics',
        store=True
    )
    new_employees = fields.Integer(
        string='New Employees',
        compute='_compute_statistics',
        store=True
    )
    error_lines = fields.Integer(
        string='Error Lines',
        compute='_compute_statistics',
        store=True
    )
    processed_lines = fields.Integer(
        string='Processed Lines',
        compute='_compute_statistics',
        store=True
    )

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('loaded', 'Data Loaded'),
        ('matched', 'Employees Matched'),
        ('validated', 'Validated'),
        ('processing', 'Processing'),
        ('done', 'Completed'),
        ('error', 'Error'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Options
    auto_create_employees = fields.Boolean(
        string='Auto-Create Employees',
        default=True,
        help="Automatically create employees for unmatched records"
    )
    auto_create_contracts = fields.Boolean(
        string='Auto-Create Contracts',
        default=True,
        help="Automatically create contracts for new employees"
    )
    match_by_code = fields.Boolean(
        string='Match by Employee Code',
        default=True,
        help="First try to match employees by their code/ID"
    )
    match_by_email = fields.Boolean(
        string='Match by Email',
        default=True,
        help="If code match fails, try matching by email"
    )

    # Payslip Settings
    create_payslips = fields.Boolean(
        string='Create Payslips',
        default=True,
        help="Create payslips for matched/created employees"
    )
    payslip_state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Waiting'),
        ('done', 'Done'),
    ], string='Payslip State', default='draft',
       help="State to set for created payslips")
    payroll_journal_id = fields.Many2one(
        'account.journal',
        string='Payroll Journal',
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
        help="Journal to use when creating payslips. If empty, falls back to the configuration's journal or the first general journal."
    )

    # Processing Log
    processing_log = fields.Text(
        string='Processing Log',
        readonly=True
    )

    # Results
    created_employee_ids = fields.Many2many(
        'hr.employee',
        'payroll_import_batch_created_employees_rel',
        'batch_id', 'employee_id',
        string='Created Employees',
        readonly=True
    )
    created_contract_ids = fields.Many2many(
        'hr.contract',
        'payroll_import_batch_created_contracts_rel',
        'batch_id', 'contract_id',
        string='Created Contracts',
        readonly=True
    )
    created_payslip_ids = fields.Many2many(
        'hr.payslip',
        'payroll_import_batch_created_payslips_rel',
        'batch_id', 'payslip_id',
        string='Created Payslips',
        readonly=True
    )

    @api.onchange('formula_config_id')
    def _onchange_formula_config_id(self):
        """Default payroll journal from configuration if not already set."""
        if self.formula_config_id and not self.payroll_journal_id:
            self.payroll_journal_id = self.formula_config_id.payroll_journal_id

    @api.depends('import_line_ids', 'import_line_ids.state', 'import_line_ids.employee_id')
    def _compute_statistics(self):
        for batch in self:
            lines = batch.import_line_ids
            batch.total_lines = len(lines)
            batch.matched_employees = len(lines.filtered(lambda l: l.employee_id and not l.is_new_employee))
            batch.new_employees = len(lines.filtered(lambda l: l.is_new_employee))
            batch.error_lines = len(lines.filtered(lambda l: l.state == 'error'))
            batch.processed_lines = len(lines.filtered(lambda l: l.state == 'processed'))

    @api.onchange('payroll_period')
    def _onchange_payroll_period(self):
        """Set date_from and date_to based on selected period"""
        import calendar
        from datetime import timedelta

        today = date.today()
        if self.payroll_period == 'current':
            self.date_from = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            self.date_to = today.replace(day=last_day)
        elif self.payroll_period == 'previous':
            first_of_current = today.replace(day=1)
            last_of_previous = first_of_current - timedelta(days=1)
            self.date_to = last_of_previous
            self.date_from = last_of_previous.replace(day=1)

    @api.model
    def create(self, vals):
        """Generate sequence name on create"""
        if vals.get('name', _('New Import Batch')) == _('New Import Batch'):
            vals['name'] = self.env['ir.sequence'].next_by_code('hr.payroll.import.batch') or _('New Import Batch')
        return super().create(vals)

    def action_load_file(self):
        """Load data from Excel/CSV file into import lines"""
        self.ensure_one()

        if not self.import_file:
            raise UserError(_("Please upload a file first."))

        if not self.formula_config_id:
            raise UserError(_("Please select a Formula Configuration first."))

        # Get connector instance for file parsing
        connector = self._get_excel_connector()

        # Parse file
        try:
            import base64
            file_content = base64.b64decode(self.import_file)
            data = connector.load_file(
                file_content,
                self.import_filename,
                header_row=self.file_header_row,
                data_start_row=self.file_data_start_row,
                sheet_name=self.file_sheet_name
            )
        except Exception as e:
            raise UserError(_("Failed to parse file: %s") % str(e))

        if not data.get('rows'):
            raise UserError(_("No data found in file."))

        # Clear existing lines
        self.import_line_ids.unlink()

        # Create import lines
        headers = data.get('headers', [])
        rows = data.get('rows', [])

        self._log("Loaded %d rows with headers: %s" % (len(rows), headers))

        line_vals_list = []
        for idx, row in enumerate(rows, start=1):
            # Build raw data JSON
            raw_data = {}
            for col_idx, header in enumerate(headers):
                if col_idx < len(row):
                    raw_data[header] = row[col_idx]

            # Extract key fields for matching
            employee_code = self._normalize_code(self._extract_field(raw_data, ['employee_code', 'emp_code', 'code', 'employee_id', 'emp_id', 'id']))
            employee_name = self._extract_field(raw_data, ['employee_name', 'name', 'full_name', 'emp_name'])
            employee_email = self._extract_field(raw_data, ['email', 'work_email', 'emp_email', 'employee_email'])

            line_vals_list.append({
                'batch_id': self.id,
                'sequence': idx,
                # Serialize with custom handler to support datetime/date from Excel
                'raw_data_json': json.dumps(raw_data, default=json_serializer),
                'employee_code': employee_code,
                'employee_name': employee_name,
                'employee_email': employee_email,
                'state': 'draft',
            })

        # Bulk create lines
        self.env['hr.payroll.import.line'].create(line_vals_list)

        self.state = 'loaded'
        self._log("Created %d import lines" % len(line_vals_list))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _("Loaded %d records from file") % len(line_vals_list),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_match_employees(self):
        """Match import lines to existing employees"""
        self.ensure_one()

        if self.state not in ['loaded', 'matched']:
            raise UserError(_("Please load data first."))

        matched_count = 0
        new_count = 0

        for line in self.import_line_ids:
            employee = self._find_employee(line)

            if employee:
                line.employee_id = employee.id
                line.is_new_employee = False
                line.state = 'matched'
                matched_count += 1
            else:
                line.is_new_employee = True
                line.state = 'unmatched'
                new_count += 1

        self.state = 'matched'
        self._log("Matched %d employees, %d new employees to create" % (matched_count, new_count))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _("Matched %d employees, %d unmatched") % (matched_count, new_count),
                'type': 'success',
                'sticky': False,
            }
        }

    def _find_employee(self, line):
        """
        Find employee by code first, then by email.
        Returns employee record or False.
        """
        Employee = self.env['hr.employee']

        # Try matching by employee code first
        if self.match_by_code and line.employee_code:
            code = self._normalize_code(line.employee_code)
            employee = Employee.search([
                '|',
                '|',
                ('identification_id', '=', code),
                ('barcode', '=', code),
                ('employee_id', '=', code),
            ], limit=1)
            if employee:
                return employee

        # Try matching by email
        if self.match_by_email and line.employee_email:
            employee = Employee.search([
                ('work_email', '=ilike', line.employee_email)
            ], limit=1)
            if employee:
                return employee

            # Also check private email
            employee = Employee.search([
                ('private_email', '=ilike', line.employee_email)
            ], limit=1)
            if employee:
                return employee

        return False

    def action_validate(self):
        """Validate import lines before processing"""
        self.ensure_one()

        if self.state not in ['matched', 'validated']:
            raise UserError(_("Please match employees first."))

        errors = []

        for line in self.import_line_ids:
            line_errors = line.validate_line()
            if line_errors:
                errors.extend(line_errors)
                line.state = 'error'
            else:
                if line.state != 'error':
                    line.state = 'validated'

        if errors:
            self._log("Validation errors:\n" + "\n".join(errors))

        self.state = 'validated'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _("Validation complete. %d errors found.") % len(errors),
                'type': 'warning' if errors else 'success',
                'sticky': bool(errors),
            }
        }

    def action_process(self):
        """Process all validated lines - create employees, contracts, and payslips"""
        self.ensure_one()

        if self.state not in ['validated', 'matched']:
            raise UserError(_("Please validate data first."))

        self.state = 'processing'

        created_employees = self.env['hr.employee']
        created_contracts = self.env['hr.contract']
        created_payslips = self.env['hr.payslip']

        try:
            for line in self.import_line_ids.filtered(lambda l: l.state in ['validated', 'matched', 'unmatched']):
                try:
                    # Step 1: Ensure employee exists
                    employee = line.employee_id
                    if not employee and line.is_new_employee and self.auto_create_employees:
                        employee = self._create_employee(line)
                        created_employees |= employee
                        line.employee_id = employee.id

                    if not employee:
                        line.state = 'error'
                        line.error_message = "No employee found and auto-create is disabled"
                        continue

                    # Step 2: Ensure contract exists
                    contract = employee.contract_id or employee.contract_ids[:1]
                    if not contract and self.auto_create_contracts:
                        contract = self._create_contract(employee, line)
                        created_contracts |= contract

                    # Step 3: Create payslip with formula-based lines
                    if self.create_payslips:
                        payslip = self._create_payslip(employee, contract, line)
                        if payslip:
                            created_payslips |= payslip
                            line.payslip_id = payslip.id

                    line.state = 'processed'

                except Exception as e:
                    line.state = 'error'
                    line.error_message = str(e)
                    _logger.exception("Error processing line %s: %s", line.id, str(e))

            # Store created records
            self.created_employee_ids = [(6, 0, created_employees.ids)]
            self.created_contract_ids = [(6, 0, created_contracts.ids)]
            self.created_payslip_ids = [(6, 0, created_payslips.ids)]

            self.state = 'done'
            self._log("Processing complete. Created: %d employees, %d contracts, %d payslips" % (
                len(created_employees), len(created_contracts), len(created_payslips)
            ))

        except Exception as e:
            self.state = 'error'
            self._log("Processing error: %s" % str(e))
            raise UserError(_("Processing failed: %s") % str(e))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _("Created %d employees, %d contracts, %d payslips") % (
                    len(created_employees), len(created_contracts), len(created_payslips)
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    def _create_employee(self, line):
        """Create a new employee from import line data"""
        raw_data = line.get_raw_data()

        # Extract employee info from raw data
        name = line.employee_name or self._extract_field(raw_data, ['name', 'full_name', 'employee_name'])

        if not name:
            raise ValidationError(_("Cannot create employee: Name is required"))

        vals = {
            'name': name,
            'identification_id': line.employee_code,
            'work_email': line.employee_email,
            'company_id': self.company_id.id,
        }

        # Extract additional fields if available
        department_name = self._extract_field(raw_data, ['department', 'dept', 'department_name'])
        if department_name:
            department = self.env['hr.department'].search([
                ('name', '=ilike', department_name),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
            if department:
                vals['department_id'] = department.id

        job_title = self._extract_field(raw_data, ['job_title', 'job', 'position', 'designation'])
        if job_title:
            job = self.env['hr.job'].search([
                ('name', '=ilike', job_title),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
            if job:
                vals['job_id'] = job.id

        employee = self.env['hr.employee'].create(vals)
        self._log("Created employee: %s [%s]" % (employee.name, employee.identification_id))

        return employee

    def _create_contract(self, employee, line):
        """Create a new contract for employee"""
        raw_data = line.get_raw_data()

        # Get basic salary from raw data
        basic_salary = self._extract_number(raw_data, ['basic', 'basic_salary', 'wage', 'salary', 'base_salary'])

        # Find structure from formula config
        structure = self.formula_config_id.structure_id

        vals = {
            'name': _("%s - Contract") % employee.name,
            'employee_id': employee.id,
            'company_id': self.company_id.id,
            'wage': basic_salary or 0,
            'state': 'open',
            'date_start': self.date_from or date.today().replace(day=1),
        }

        if structure:
            vals['struct_id'] = structure.id

        contract = self.env['hr.contract'].create(vals)
        self._log("Created contract for %s: wage=%s" % (employee.name, basic_salary))

        return contract

    def _create_payslip(self, employee, contract, line):
        """
        Create payslip with formula-based lines.
        This directly creates hr.payslip.line records without going through salary rules.
        """
        raw_data = line.get_raw_data()

        # Transform raw data using field mappings
        input_values = self._transform_data_to_formula_inputs(raw_data)

        # Create payslip
        payslip_vals = {
            'name': _("%s - %s") % (employee.name, self.date_from.strftime('%B %Y') if self.date_from else 'Payslip'),
            'employee_id': employee.id,
            'company_id': self.company_id.id,
            'contract_id': contract.id if contract else False,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'struct_id': self.formula_config_id.structure_id.id if self.formula_config_id.structure_id else False,
            'journal_id': self._get_payroll_journal().id,
            'state': 'draft',
            # Store formula computation info
            'calculation_method': 'formula',
            'formula_config_id': self.formula_config_id.id,
            'formula_input_values': json.dumps(input_values),
        }

        payslip = self.env['hr.payslip'].create(payslip_vals)

        # Compute payslip using formula engine and create lines directly
        self._compute_and_create_payslip_lines(payslip, input_values)

        # Update payslip state if needed
        if self.payslip_state == 'verify':
            payslip.action_payslip_verify()
        elif self.payslip_state == 'done':
            payslip.action_payslip_done()

        self._log("Created payslip for %s: %s" % (employee.name, payslip.name))

        return payslip

    def _get_payroll_journal(self):
        """
        Resolve the journal to use for payslip creation:
        1) Batch journal (if set)
        2) Configuration journal (if set)
        3) First general journal for the company
        Raises a clear error if none found.
        """
        Journal = self.env['account.journal'].with_context(active_test=True)
        if self.payroll_journal_id:
            return self.payroll_journal_id
        if self.formula_config_id.payroll_journal_id:
            return self.formula_config_id.payroll_journal_id

        journal = Journal.search([('type', '=', 'general'), ('company_id', '=', self.company_id.id)], limit=1, order='sequence, id')
        if journal:
            return journal
        raise UserError(_("No general journal found for company %s. Please set a Payroll Journal on the batch or configuration.") % (self.company_id.display_name,))

    def _compute_and_create_payslip_lines(self, payslip, input_values):
        """
        Compute formulas and directly create hr.payslip.line records.
        Does NOT use hr.salary.rule computation.
        """
        config = self.formula_config_id
        rules = config.rule_ids.sorted(key=lambda r: r.sequence)

        # Build column map for formula evaluation
        column_map = {}
        for rule in rules:
            column_map[rule.column_letter] = rule.code
            column_map[rule.code] = rule.column_letter

        # Evaluate all formulas
        computed_values = {}
        computation_log = []

        for rule in rules:
            try:
                value = rule.evaluate(input_values)
                computed_values[rule.code] = value
                # Also store by column letter for dependent formulas
                input_values[rule.code] = value
                input_values[rule.column_letter] = value

                computation_log.append("%s (%s) = %s" % (rule.code, rule.column_letter, value))
            except Exception as e:
                computed_values[rule.code] = 0
                computation_log.append("%s (%s) = ERROR: %s" % (rule.code, rule.column_letter, str(e)))
                _logger.warning("Error computing %s: %s", rule.code, str(e))

        # Store computed values in payslip
        payslip.formula_computed_values = json.dumps(computed_values)
        payslip.formula_computation_log = "\n".join(computation_log)

        # Create payslip lines directly
        line_vals_list = []
        sequence = 1

        for rule in rules:
            if not rule.appears_on_payslip:
                continue

            amount = computed_values.get(rule.code, 0)

            # Get or create salary rule category
            category = rule.category_id
            if not category:
                # Use a default category based on code pattern
                category = self._get_default_category(rule.code)

            # Find or create salary rule for proper linking
            salary_rule = self._get_or_create_salary_rule(rule)

            line_vals = {
                'slip_id': payslip.id,
                'name': rule.name,
                'code': rule.code,
                'category_id': category.id if category else False,
                'sequence': sequence,
                'quantity': 1,
                'rate': 100,
                'amount': amount,
                'total': amount,
                'salary_rule_id': salary_rule.id if salary_rule else False,
            }

            line_vals_list.append(line_vals)
            sequence += 1

        # Bulk create payslip lines
        if line_vals_list:
            self.env['hr.payslip.line'].create(line_vals_list)

    def _get_default_category(self, code):
        """Get default salary rule category based on code pattern"""
        code_upper = code.upper()

        # Map common codes to categories
        category_mapping = {
            'BASIC': 'BASIC',
            'BASE': 'BASIC',
            'GROSS': 'GROSS',
            'NET': 'NET',
            'ALLOWANCE': 'ALW',
            'ALW': 'ALW',
            'HRA': 'ALW',
            'TRANSPORT': 'ALW',
            'DEDUCTION': 'DED',
            'DED': 'DED',
            'TAX': 'DED',
            'PIT': 'DED',
            'SI': 'DED',
            'HI': 'DED',
            'INSURANCE': 'DED',
        }

        for pattern, cat_code in category_mapping.items():
            if pattern in code_upper:
                category = self.env['hr.salary.rule.category'].search([
                    ('code', '=', cat_code)
                ], limit=1)
                if category:
                    return category

        # Fallback: ensure a generic category exists
        category = self.env['hr.salary.rule.category'].search([('code', '=', 'OTH')], limit=1)
        if not category:
            category = self.env['hr.salary.rule.category'].create({
                'name': 'Other',
                'code': 'OTH',
            })
        return category

    def _get_or_create_salary_rule(self, formula_rule):
        """Get existing salary rule or create one for the formula rule"""
        if formula_rule.salary_rule_id:
            return formula_rule.salary_rule_id

        # Try to find existing rule by code
        SalaryRule = self.env['hr.salary.rule']
        existing = SalaryRule.search([
            ('code', '=', formula_rule.code),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

        if existing:
            # Link it
            formula_rule.salary_rule_id = existing.id
            return existing

        # Create a minimal salary rule so salary_rule_id is never null on payslip lines
        category = formula_rule.category_id or self._get_default_category(formula_rule.code)
        rule_vals = {
            'name': formula_rule.name or formula_rule.code,
            'code': formula_rule.code,
            'sequence': formula_rule.sequence or 100,
            'category_id': category.id if category else False,
            'company_id': self.company_id.id,
            'condition_select': 'none',
            'amount_select': 'fix',
            'amount_fix': 0.0,
            'quantity': '1.0',
            'appears_on_payslip': True,
            'active': True,
        }
        new_rule = SalaryRule.create(rule_vals)
        # Link back to formula rule
        formula_rule.salary_rule_id = new_rule.id
        # Optionally link to structure for visibility
        if self.formula_config_id.structure_id:
            self.formula_config_id.structure_id.rule_ids = [(4, new_rule.id)]
        return new_rule

    def _transform_data_to_formula_inputs(self, raw_data):
        """Transform raw Excel data to formula input values using field mappings"""
        input_values = {}
        config = self.formula_config_id

        # First, try using connector field mappings if available
        if config.connector_id:
            for mapping in config.connector_id.field_mapping_ids:
                if mapping.target_rule_id and mapping.source_field:
                    source_value = raw_data.get(mapping.source_field)
                    if source_value is not None:
                        # Apply transformation
                        transformed = mapping.transform_value(source_value, raw_data)
                        input_values[mapping.target_rule_id.code] = transformed

        # Then, do direct mapping for input rules based on data_source_field
        for rule in config.rule_ids.filtered(lambda r: r.column_type == 'input'):
            if rule.code not in input_values:
                # Try to find value from raw data
                value = None

                # First try data_source_field
                if rule.data_source_field:
                    value = raw_data.get(rule.data_source_field)

                # Then try by rule code
                if value is None:
                    value = raw_data.get(rule.code)

                # Then try by column letter
                if value is None:
                    value = raw_data.get(rule.column_letter)

                # Then try common variations
                if value is None:
                    for key in raw_data.keys():
                        if key.upper().replace(' ', '_').replace('-', '_') == rule.code.upper():
                            value = raw_data.get(key)
                            break

                if value is not None:
                    try:
                        input_values[rule.code] = float(value) if value != '' else rule.default_value
                    except (ValueError, TypeError):
                        input_values[rule.code] = rule.default_value
                else:
                    input_values[rule.code] = rule.default_value

        # Add constant values
        for rule in config.rule_ids.filtered(lambda r: r.column_type == 'constant'):
            input_values[rule.code] = rule.constant_value

        return input_values

    def _get_excel_connector(self):
        """Get or create Excel connector instance"""
        from ..integrations.excel_connector import ExcelConnector
        return ExcelConnector(self.connector_id or self.env['hr.integration.connector'])

    def _extract_field(self, data, field_names):
        """Extract field value trying multiple possible field names"""
        def _norm(s):
            return ''.join(ch for ch in s.replace(' ', '').replace('_', '').lower() if ch.isalnum())

        for name in field_names:
            # Try exact match
            if name in data:
                return data[name]
            # Try case-insensitive with loose normalization (spaces/underscores/punctuation)
            target = _norm(name)
            for key in data.keys():
                if _norm(str(key)) == target:
                    return data[key]
        return None

    def _extract_number(self, data, field_names):
        """Extract numeric field value"""
        value = self._extract_field(data, field_names)
        if value is None:
            return 0
        try:
            if isinstance(value, str):
                # Remove currency symbols and commas
                value = value.replace(',', '').replace('$', '').replace('₫', '').replace('Rp', '').strip()
            return float(value)
        except (ValueError, TypeError):
            return 0

    def _normalize_code(self, value):
        """Normalize employee code/id to a comparable string"""
        if value is None:
            return False
        try:
            # If numeric (int/float/Decimal), drop trailing .0
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if float(value).is_integer():
                    return str(int(value))
                return str(value).strip()
            # Strings: strip spaces
            return str(value).strip()
        except Exception:
            return str(value)

    def _log(self, message):
        """Add message to processing log"""
        timestamp = fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = "[%s] %s" % (timestamp, message)

        if self.processing_log:
            self.processing_log = self.processing_log + "\n" + log_entry
        else:
            self.processing_log = log_entry

        _logger.info("Import Batch %s: %s", self.name, message)

    def action_cancel(self):
        """Cancel the batch"""
        self.state = 'cancelled'
        self._log("Batch cancelled")

    def action_reset_to_draft(self):
        """Reset batch to draft state"""
        self.state = 'draft'
        self.import_line_ids.write({'state': 'draft', 'employee_id': False, 'payslip_id': False})
        self._log("Reset to draft")

    def action_view_created_employees(self):
        """View created employees"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Created Employees'),
            'res_model': 'hr.employee',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.created_employee_ids.ids)],
        }

    def action_view_created_payslips(self):
        """View created payslips"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Created Payslips'),
            'res_model': 'hr.payslip',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.created_payslip_ids.ids)],
        }
