# -*- coding: utf-8 -*-

import logging
import json
from datetime import date, datetime, timedelta, time
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from ..formula_engine.column_manager import ColumnManager
# COLROLES — the employee-code marker tuple and the header-candidate lists used to
# exist in three and five copies respectively inside this file, drifting apart by a
# word or two each time somebody added a spelling. `column_role_classifier` is now
# the definition; the names below are the same strings in the same order.
from .bank_account_util import (
    acc_numbers_match,
    sanitize_acc_number,
    sanitize_bank_text,
)
from . import input_provenance
from .column_role_classifier import (
    EMPLOYEE_CODE_MARKERS,
    EMPLOYEE_CODE_HEADER_CANDIDATES,
    EMPLOYEE_NAME_HEADER_CANDIDATES,
    EXTERNAL_CODE_HEADER_CANDIDATES,
    EXTERNAL_NAME_HEADER_CANDIDATES,
    PRIMARY_KEY_HEADER_CANDIDATES,
)

_logger = logging.getLogger(__name__)


def json_serializer(obj):
    """Custom JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# ---------------------------------------------------------------------------
# MAPFIX D5 — the ONE predicate for "what happens to a many2one column".
#
# `_coerce_mapped_value` resolves a many2one by NAME and creates the record when
# it finds nothing — but only when the comodel actually has a `name` field. When
# its identity lives somewhere else (`res.partner.bank`, whose `_rec_name` is the
# account number) it deliberately refuses and stores nothing: minting a bank
# account out of a spreadsheet cell nobody has checked is the one outcome an
# import must not produce.
#
# That behaviour is correct and stays. What was missing is that a person wiring
# the column could not see it BEFORE the import ran. The studio's right-hand card
# now says which of the two will happen — and it says so by calling these
# functions, not by re-typing the rule. Two copies of a predicate are two answers
# the day one of them is edited.
# ---------------------------------------------------------------------------
def m2o_resolution_key(comodel):
    """Which field of `comodel` an imported cell is matched against, or None when
    there is nothing to match by at all."""
    if 'name' in comodel._fields:
        return 'name'
    rec_name = comodel._rec_name
    return rec_name if rec_name and rec_name in comodel._fields else None


def m2o_creates_missing(comodel):
    """True when an unseen value CREATES a record of `comodel`; False when the
    value must already exist (or cannot be resolved at all)."""
    return m2o_resolution_key(comodel) == 'name'


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
        ('api_data_store', 'API Data Store'),
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
        ('mid_cycle', 'Mid Cycle'),
        ('end_cycle', 'End Cycle'),
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
    cycle_type = fields.Selection(
        related='formula_config_id.cycle_type',
        string='Cycle Type',
        readonly=True
    )
    use_proration = fields.Boolean(
        related='formula_config_id.use_proration',
        string='Use Proration',
        readonly=True
    )
    use_auto_retro = fields.Boolean(
        related='formula_config_id.use_auto_retro',
        string='Use Auto Retro',
        readonly=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        help="If unchecked, this record will be archived and hidden from the default view."
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
    proration_line_count = fields.Integer(
        string='Proration Lines',
        compute='_compute_proration_line_count'
    )
    retro_adjustment_count = fields.Integer(
        string='Retro Adjustments',
        compute='_compute_retro_adjustment_count'
    )
    carryover_count = fields.Integer(
        string='Carryovers',
        compute='_compute_carryover_count'
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
        domain="[('type', '=', 'general'), ('company_id', 'in', allowed_company_ids)]",
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
    payslip_run_id = fields.Many2one(
        'hr.payslip.run',
        string='Payslip Run',
        readonly=True,
        help="Batch-generated payslip run containing the created payslips."
    )

    @api.onchange('formula_config_id')
    def _onchange_formula_config_id(self):
        """Default payroll journal from configuration."""
        if self.formula_config_id and self.formula_config_id.payroll_journal_id:
            self.payroll_journal_id = self.formula_config_id.payroll_journal_id

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """Default payroll journal from the first available general journal."""
        if self.company_id and not self.payroll_journal_id and not self.formula_config_id:
            self.payroll_journal_id = self._get_first_general_journal(self.company_id)

    @api.depends('import_line_ids', 'import_line_ids.state', 'import_line_ids.employee_id')
    def _compute_statistics(self):
        for batch in self:
            lines = batch.import_line_ids
            batch.total_lines = len(lines)
            batch.matched_employees = len(lines.filtered(lambda l: l.employee_id and not l.is_new_employee))
            batch.new_employees = len(lines.filtered(lambda l: l.is_new_employee))
            batch.error_lines = len(lines.filtered(lambda l: l.state == 'error'))
            batch.processed_lines = len(lines.filtered(lambda l: l.state == 'processed'))

    def _compute_proration_line_count(self):
        for batch in self:
            batch.proration_line_count = self.env['hr.payroll.proration.line'].search_count([
                ('import_batch_id', '=', batch.id)
            ])

    def _compute_retro_adjustment_count(self):
        for batch in self:
            batch.retro_adjustment_count = self.env['hr.payroll.retro.adjustment'].search_count([
                ('applied_in_batch_id', '=', batch.id)
            ])

    def _compute_carryover_count(self):
        for batch in self:
            batch.carryover_count = self.env['hr.payroll.cycle.carryover'].search_count([
                ('import_batch_id', '=', batch.id)
            ])

    def action_view_carryovers(self):
        """Open the list of carryover records created for this batch."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Carryovers - %s') % self.name,
            'res_model': 'hr.payroll.cycle.carryover',
            'view_mode': 'list,form',
            'domain': [('import_batch_id', '=', self.id)],
            'context': {'default_import_batch_id': self.id},
        }

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
        elif self.payroll_period == 'mid_cycle':
            self.date_from = today.replace(day=1)
            self.date_to = today.replace(day=15)
        elif self.payroll_period == 'end_cycle':
            last_day = calendar.monthrange(today.year, today.month)[1]
            self.date_from = today.replace(day=1)
            self.date_to = today.replace(day=last_day)

    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence name on create"""
        for vals in vals_list:
            if vals.get('name', _('New Import Batch')) == _('New Import Batch'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.payroll.import.batch') or _('New Import Batch')
            if not vals.get('payroll_journal_id'):
                # First try formula config's journal
                config_id = vals.get('formula_config_id')
                if config_id:
                    config = self.env['hr.formula.config'].browse(config_id)
                    if config.payroll_journal_id:
                        vals['payroll_journal_id'] = config.payroll_journal_id.id
                # Fall back to first general journal only if still not set
                if not vals.get('payroll_journal_id'):
                    company_id = vals.get('company_id') or self.env.company.id
                    journal = self._get_first_general_journal(self.env['res.company'].browse(company_id))
                    if journal:
                        vals['payroll_journal_id'] = journal.id
        return super().create(vals_list)

    def action_load_file(self):
        """Load data from Excel/CSV file into import lines"""
        self.ensure_one()

        if not self.import_file:
            raise UserError(_("Please upload a file first."))

        if not self.formula_config_id:
            raise UserError(_("Please select a Formula Configuration first."))

        if self.formula_config_id.cycle_type == 'mid_cycle':
            self._check_mid_cycle_overlap()

        # Get connector instance for file parsing
        connector = self._get_excel_connector()

        # Parse file
        try:
            import base64
            file_content = base64.b64decode(self.import_file)
            use_multisheet = (
                self.import_filename and
                self.import_filename.lower().endswith(('.xlsx', '.xls')) and
                self.formula_config_id.rule_ids.filtered(lambda r: r.source_sheet_name)
            )

            if use_multisheet:
                headers, rows = self._load_multisheet_data(file_content, connector)
                data = {'headers': headers, 'rows': rows}
            else:
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
            if isinstance(row, dict):
                raw_data = dict(row)
            else:
                raw_data = {}
                for col_idx, header in enumerate(headers):
                    if col_idx < len(row):
                        raw_data[header] = row[col_idx]
                        col_letter = ColumnManager.index_to_letter(col_idx)
                        if col_letter not in raw_data:
                            raw_data[col_letter] = row[col_idx]

            # Extract key fields for matching
            employee_code, employee_name, employee_email = \
                self._identity_from_file_row(raw_data)

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

        # Refresh the form to reflect new state and stats
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    # ==================================================================
    # SOURCING S3 — who a row is about.
    #
    # Extracted VERBATIM from the two loaders so the top-up can identify an
    # employee by exactly the same rules the primary load used, rather than
    # growing a second copy that drifts (MF31). The two are deliberately NOT
    # unified: a spreadsheet row is identified with the help of the field
    # mappings, a feed record falls back to its external id, and that difference
    # is real rather than accidental.
    # ==================================================================
    def _merge_topup_rows(self, rows, kind):
        """Fold a SECOND source into a run that already has lines. Never unlinks.

        `rows` is `[(raw_data, code, name, email), …]` already identified by the
        caller with the extractor that matches where the rows came from.

        The primary blob is never touched. That is the point: a top-up cannot
        regress a run that already worked, and the value a binding chooses NOT to
        use survives in its own blob for the `ignored` report.

        An employee present in only ONE source still gets a line, flagged — never
        silently absent, and never a row of zeros pretending to be data.
        Re-running a top-up REPLACES its blob rather than accumulating, so the
        merge is keyed rather than appended and running it twice is running it once.
        """
        self.ensure_one()
        Line = self.env['hr.payroll.import.line']
        existing = self.import_line_ids
        by_code, by_email, by_name = {}, {}, {}
        for line in existing:
            if line.employee_code:
                by_code.setdefault(self._normalize_code(line.employee_code), line)
            if line.employee_email:
                by_email.setdefault((line.employee_email or '').strip().lower(), line)
            if line.employee_name:
                by_name.setdefault(self._normalize_header_key(line.employee_name), line)

        matched, created = 0, 0
        seq = max(existing.mapped('sequence') or [0])
        new_vals = []
        for raw_data, code, name, email in rows:
            line = (by_code.get(self._normalize_code(code or ''))
                    or by_email.get((email or '').strip().lower())
                    or by_name.get(self._normalize_header_key(name or '')))
            blob = json.dumps(raw_data, default=json_serializer)
            if line:
                line.write({'raw_data_topup_json': blob, 'source_origin': 'both'})
                matched += 1
            else:
                seq += 1
                new_vals.append({
                    'batch_id': self.id, 'sequence': seq,
                    # No primary data for this person: they exist in the added
                    # source only, and the blob says so rather than implying zeros.
                    'raw_data_json': json.dumps({}),
                    'raw_data_topup_json': blob,
                    'source_origin': 'topup',
                    'employee_code': code, 'employee_name': name,
                    'employee_email': email, 'state': 'draft',
                })
                created += 1
        if new_vals:
            Line.create(new_vals)
        self._log("Added a second source (%s): %d employees matched an existing row, "
                  "%d were only in the added source." % (kind, matched, created))
        return {'matched': matched, 'created': created, 'kind': kind}

    def action_top_up_from_data_store(self):
        """Also pull this run's values from the connected system.

        `source_type` is NOT changed — it stays the run's base source. This is the
        explicit "also pull from…" step, and it merges rather than replacing.
        """
        self.ensure_one()
        if not self.connector_id:
            raise UserError(_("Choose a connected system for this run first."))
        if not self.import_line_ids:
            raise UserError(_("Load this run's main source before adding a second one."))
        # Same selection the primary data-store loader uses — a top-up must read
        # the feed the same way a primary load of that feed would, or the two
        # sources disagree about what the feed even contains.
        DataStore = self.env['hr.api.data.store']
        store_records = DataStore.search([
            ('connector_id', '=', self.connector_id.id),
            ('state', '=', 'extracted'),
            ('data_type', 'in', ['salary', 'employee']),
        ], order='employee_external_id, data_type')
        if not store_records:
            raise UserError(_(
                "There is no pulled data on %s to add. Pull data on the "
                "connected system first.") % (self.connector_id.name or ''))
        grouped = {}
        for rec in store_records:
            ext_id = rec.employee_external_id or ('_unknown_%s' % rec.id)
            grouped.setdefault(ext_id, {}).update(rec.get_mappable_data())
        rows = []
        for ext_id, data in grouped.items():
            code, name, email = self._identity_from_store_row(data, ext_id)
            rows.append((data, code, name, email))
        self._merge_topup_rows(rows, 'feed')
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _identity_from_file_row(self, raw_data):
        """Employee code / name / email as the FILE loader has always read them."""
        employee_code = self._normalize_code(self._extract_field(raw_data, [
            'employee_code', 'employee code', 'emp_code', 'emp code', 'emp. code', 'empcode',
            'employee_id', 'employee id', 'emp_id', 'emp id', 'empid', 'employee no', 'employee number',
            'staff id', 'staff code', 'code', 'id', 'msnv', 'ma nv', 'manv', 'ma so nhan vien'
        ]))
        mapped_employee_code = self._get_employee_identifier_value(raw_data)
        if mapped_employee_code not in (None, ''):
            employee_code = self._normalize_code(mapped_employee_code)

        employee_name = self._extract_field(raw_data, list(EMPLOYEE_NAME_HEADER_CANDIDATES))
        mapped_employee_name = self._get_mapped_value_for_field(raw_data, 'hr.employee', 'name')
        if mapped_employee_name not in (None, ''):
            employee_name = mapped_employee_name

        employee_email = self._extract_field(raw_data, ['email', 'work_email', 'emp_email', 'employee_email'])
        mapped_employee_email = (
            self._get_mapped_value_for_field(raw_data, 'hr.employee', 'work_email')
            or self._get_mapped_value_for_field(raw_data, 'hr.employee', 'private_email')
        )
        if mapped_employee_email not in (None, ''):
            employee_email = mapped_employee_email
        return employee_code, employee_name, employee_email

    def _identity_from_store_row(self, raw_data, ext_id=None):
        """Employee code / name / email as the DATA STORE loader has always read them."""
        employee_code = self._normalize_code(
            self._extract_field(raw_data, list(EXTERNAL_CODE_HEADER_CANDIDATES)) or ext_id)
        employee_name = self._extract_field(raw_data, list(EXTERNAL_NAME_HEADER_CANDIDATES))
        employee_email = self._extract_field(raw_data, [
            'email', 'work_email', 'emp_email', 'employee_email',
            'Email', 'EmailID',
        ])
        return employee_code, employee_name, employee_email

    def action_load_from_data_store(self):
        """Load data from API Data Store into import lines.

        This bridges the API Data Store with the existing payroll pipeline.
        It reads from extracted_data + computed_data (merged) and creates
        import lines, then marks the data store records as consumed.
        """
        self.ensure_one()

        if self.source_type != 'api_data_store':
            raise UserError(_("Source type must be 'API Data Store' to use this action."))

        if not self.connector_id:
            raise UserError(_("Please select a Connector first."))

        if not self.formula_config_id:
            raise UserError(_("Please select a Formula Configuration first."))

        DataStore = self.env['hr.api.data.store']

        # Find extracted (not yet consumed) salary records for this connector
        domain = [
            ('connector_id', '=', self.connector_id.id),
            ('state', '=', 'extracted'),
            ('data_type', 'in', ['salary', 'employee']),
        ]

        # Filter by period if specified
        if self.date_from and self.date_to:
            domain += [
                '|',
                ('period_from', '=', False),
                ('period_from', '>=', self.date_from),
                '|',
                ('period_to', '=', False),
                ('period_to', '<=', self.date_to),
            ]

        store_records = DataStore.search(domain, order='employee_external_id, data_type')

        if not store_records:
            raise UserError(_(
                "No extracted data found in the API Data Store for connector '%s'. "
                "Please pull data first using the 'Pull Data' button on the connector."
            ) % self.connector_id.name)

        # Group records by employee
        employee_data = {}
        for rec in store_records:
            ext_id = rec.employee_external_id or f"_unknown_{rec.id}"
            if ext_id not in employee_data:
                employee_data[ext_id] = {
                    'store_records': DataStore,
                    'merged_data': {},
                }
            employee_data[ext_id]['store_records'] |= rec
            # Merge mappable data (extracted + computed)
            employee_data[ext_id]['merged_data'].update(rec.get_mappable_data())

        # Clear existing lines
        self.import_line_ids.unlink()

        line_vals_list = []
        for idx, (ext_id, emp_data) in enumerate(employee_data.items(), start=1):
            raw_data = emp_data['merged_data']

            # Extract key fields for matching
            employee_code, employee_name, employee_email = \
                self._identity_from_store_row(raw_data, ext_id)

            line_vals_list.append({
                'batch_id': self.id,
                'sequence': idx,
                'raw_data_json': json.dumps(raw_data, default=json_serializer),
                'employee_code': employee_code,
                'employee_name': employee_name,
                'employee_email': employee_email,
                'state': 'draft',
            })

        # Bulk create lines
        self.env['hr.payroll.import.line'].create(line_vals_list)

        # Mark data store records as consumed
        store_records.action_mark_consumed(self)

        self.state = 'loaded'
        self._log("Loaded %d employees from API Data Store (%s)" % (
            len(line_vals_list), self.connector_id.name
        ))

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _load_multisheet_data(self, file_content, connector):
        """Load and merge data across all sheets using primary key matching."""
        workbook_data = connector.load_workbook_multisheet(file_content, include_formulas=False)

        sheet_summaries = []
        for sheet_name in workbook_data['sheet_names']:
            sheet_data = connector.load_sheet_with_detection(sheet_name)
            headers = [h.get('value') for h in sheet_data.get('headers', []) if h.get('value')]
            primary_key = self._find_primary_key_header(headers)
            match_count = self._count_header_matches(headers)
            sheet_summaries.append({
                'sheet_name': sheet_name,
                'headers': headers,
                'headers_meta': sheet_data.get('headers', []),
                'data_rows': sheet_data.get('data_rows', []),
                'primary_key': primary_key,
                'match_count': match_count,
                'row_count': sheet_data.get('total_rows', 0),
                'col_count': sheet_data.get('total_columns', 0),
            })

        candidates = [s for s in sheet_summaries if s['primary_key']]
        if not candidates:
            raise UserError(_("No primary key column found in any worksheet."))

        candidates.sort(key=lambda s: (s['match_count'], s['col_count'], s['row_count']), reverse=True)
        main_sheet = candidates[0]
        main_pk = main_sheet['primary_key']

        self._log(
            "Multi-sheet import: main sheet '%s' using primary key '%s' (matched %d headers)"
            % (main_sheet['sheet_name'], main_pk, main_sheet['match_count'])
        )

        merged_rows = {}
        for row in main_sheet['data_rows']:
            pk_value = row.get(main_pk)
            pk_key = self._normalize_code(pk_value)
            if not pk_key:
                continue
            base_row = row.copy()
            for header, value in row.items():
                base_row[f"{main_sheet['sheet_name']}|{header}"] = value
            for header_info in main_sheet.get('headers_meta', []):
                col_letter = header_info.get('column_letter')
                header_value = header_info.get('value')
                if not col_letter or not header_value:
                    continue
                value = row.get(header_value)
                base_row[f"{main_sheet['sheet_name']}|{col_letter}"] = value
                base_row[col_letter] = value
            merged_rows[pk_key] = base_row

        for sheet in sheet_summaries:
            if sheet['sheet_name'] == main_sheet['sheet_name']:
                continue

            pk_header = sheet['primary_key'] or main_pk
            if not pk_header:
                continue

            aux_map = {}
            for row in sheet['data_rows']:
                pk_value = row.get(pk_header)
                pk_key = self._normalize_code(pk_value)
                if not pk_key:
                    continue
                aux_map[pk_key] = row

            for pk_key, base_row in merged_rows.items():
                aux_row = aux_map.get(pk_key)
                if aux_row:
                    for header in sheet['headers']:
                        if header == pk_header:
                            continue
                        value = aux_row.get(header)
                        base_row[f"{sheet['sheet_name']}|{header}"] = value
                        if header not in base_row:
                            base_row[header] = value
                    for header_info in sheet.get('headers_meta', []):
                        col_letter = header_info.get('column_letter')
                        header_value = header_info.get('value')
                        if not col_letter or not header_value or header_value == pk_header:
                            continue
                        value = aux_row.get(header_value)
                        base_row[f"{sheet['sheet_name']}|{col_letter}"] = value
                else:
                    for header in sheet['headers']:
                        if header == pk_header:
                            continue
                        base_row.setdefault(f"{sheet['sheet_name']}|{header}", None)
                        base_row.setdefault(header, None)
                    for header_info in sheet.get('headers_meta', []):
                        col_letter = header_info.get('column_letter')
                        header_value = header_info.get('value')
                        if not col_letter or not header_value or header_value == pk_header:
                            continue
                        base_row.setdefault(f"{sheet['sheet_name']}|{col_letter}", None)

        header_set = set()
        for row in merged_rows.values():
            header_set.update(row.keys())
        headers = sorted(header_set)

        return headers, list(merged_rows.values())

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

        # Refresh the form to reflect new state and stats
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_view_error_lines(self):
        """Open import lines filtered to errors for this batch."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Error Lines'),
            'res_model': 'hr.payroll.import.line',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id), ('state', '=', 'error')],
            'context': {'default_batch_id': self.id},
        }

    def action_view_proration_lines(self):
        self.ensure_one()
        action = self.env.ref('pb_hr_payroll_formula.action_payroll_proration_line').read()[0]
        action['domain'] = [('import_batch_id', '=', self.id)]
        action['context'] = {'default_import_batch_id': self.id}
        return action

    def action_view_retro_adjustments(self):
        self.ensure_one()
        action = self.env.ref('pb_hr_payroll_formula.action_payroll_retro_adjustment').read()[0]
        action['domain'] = [('applied_in_batch_id', '=', self.id)]
        action['context'] = {'default_applied_in_batch_id': self.id}
        return action

    def _find_employee(self, line):
        """
        Find employee by code first, then by email.
        Returns employee record or False.
        """
        Employee = self.env['hr.employee']
        raw_data = line.get_raw_data() if line else {}
        employee_name = line.employee_name or self._extract_field(raw_data, list(EMPLOYEE_NAME_HEADER_CANDIDATES))
        mapped_employee_name = self._get_mapped_value_for_field(raw_data, 'hr.employee', 'name')
        if mapped_employee_name not in (None, ''):
            employee_name = mapped_employee_name

        employee_email = line.employee_email or self._extract_field(raw_data, ['email', 'work_email', 'emp_email', 'employee_email'])
        mapped_employee_email = (
            self._get_mapped_value_for_field(raw_data, 'hr.employee', 'work_email')
            or self._get_mapped_value_for_field(raw_data, 'hr.employee', 'private_email')
        )
        if mapped_employee_email not in (None, ''):
            employee_email = mapped_employee_email

        employee_code = line.employee_code or self._extract_field(raw_data, list(EMPLOYEE_CODE_HEADER_CANDIDATES))
        mapped_employee_code = self._get_employee_identifier_value(raw_data)
        if mapped_employee_code not in (None, ''):
            employee_code = mapped_employee_code
        employee_code = self._normalize_code(employee_code) if employee_code else False
        id_no = self._extract_field(raw_data, [
            'id_no', 'id no', 'idno', 'id_number', 'id number', 'identification_id', 'identity'
        ])
        id_no = self._normalize_code(id_no) if id_no else False
        phone = self._extract_field(raw_data, [
            'work_phone', 'work phone', 'phone', 'phone_number', 'phone number',
            'mobile', 'mobile_phone', 'mobile phone', 'cell', 'cellphone', 'contact', 'contact_number'
        ])
        phone = self._normalize_phone(phone)

        base_domain = []
        if self.company_id:
            base_domain.append(('company_id', '=', self.company_id.id))

        # Try matching by employee code first
        if self.match_by_code and employee_code:
            code_domain = [
                '|',
                '|',
                ('identification_id', '=', employee_code),
                ('barcode', '=', employee_code),
                ('employee_id', '=', employee_code),
            ]
            employee = Employee.search(code_domain + base_domain, limit=1)
            if employee:
                return employee

        if id_no:
            employee = Employee.search([('identification_id', '=', id_no)] + base_domain, limit=1)
            if employee:
                return employee

        # Try matching by email
        if self.match_by_email and employee_email:
            employee = Employee.search([
                ('work_email', '=ilike', employee_email)
            ] + base_domain, limit=1)
            if employee:
                return employee

            # Also check private email
            employee = Employee.search([
                ('private_email', '=ilike', employee_email)
            ] + base_domain, limit=1)
            if employee:
                return employee

        if phone:
            phone_domain = []
            if 'work_phone' in Employee._fields:
                phone_domain.append(('work_phone', 'ilike', phone))
            if 'mobile_phone' in Employee._fields:
                phone_domain.append(('mobile_phone', 'ilike', phone))
            if 'phone' in Employee._fields:
                phone_domain.append(('phone', 'ilike', phone))
            if phone_domain:
                domain = phone_domain[0]
                for clause in phone_domain[1:]:
                    domain = ['|', domain, clause]
                employee = Employee.search(domain + base_domain, limit=1)
                if employee:
                    return employee

        if employee_name:
            candidates = Employee.search([('name', '=ilike', employee_name)] + base_domain, limit=2)
            if len(candidates) == 1:
                return candidates[0]

        return False

    def action_validate(self):
        """Validate import lines before processing"""
        self.ensure_one()

        if self.state not in ['matched', 'validated']:
            raise UserError(_("Please match employees first."))

        if self.formula_config_id.cycle_type == 'mid_cycle':
            self._check_mid_cycle_overlap()

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

        # Refresh the form to show updated states
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_process(self):
        """Process all validated lines - create employees, contracts, and payslips"""
        self.ensure_one()

        if self.state not in ['validated', 'matched']:
            raise UserError(_("Please validate data first."))

        if self.formula_config_id.cycle_type == 'mid_cycle':
            self._check_mid_cycle_overlap()

        self.state = 'processing'

        if self.formula_config_id.use_proration:
            self.env['hr.payroll.proration.line'].search([
                ('import_batch_id', '=', self.id)
            ]).unlink()
        if self.formula_config_id.use_auto_retro:
            self.env['hr.payroll.retro.adjustment'].search([
                ('applied_in_batch_id', '=', self.id)
            ]).unlink()
        self = self.with_context(retro_adjustment_cache={})

        created_employees = self.env['hr.employee']
        created_contracts = self.env['hr.contract']
        created_payslips = self.env['hr.payslip']

        try:
            for line in self.import_line_ids.filtered(lambda l: l.state in ['validated', 'matched', 'unmatched']):
                try:
                    # Step 1: Ensure employee exists
                    employee = line.employee_id
                    if not employee and line.is_new_employee and self.auto_create_employees:
                        employee = self._find_employee(line)
                        if employee:
                            line.employee_id = employee.id
                            line.is_new_employee = False
                        else:
                            employee = self._create_employee(line)
                            created_employees |= employee
                            line.employee_id = employee.id

                    if not employee:
                        line.state = 'error'
                        line.error_message = "No employee found and auto-create is disabled"
                        continue

                    raw_data = line.get_raw_data()
                    self._update_employee_from_raw_data(employee, raw_data, line=line)

                    # Step 1b: Bank destinations (COLROLES P3). Deliberately its own
                    # try/except: an unparseable bank cell is a detail of one row, and
                    # failing the whole line over it would throw away the payslip too.
                    try:
                        self._sync_employee_bank_account(employee, raw_data, line=line)
                    except Exception as bank_error:      # noqa: BLE001 — see above
                        _logger.exception(
                            "Bank sync failed for line %s (employee %s): %s",
                            line.id, employee.id, bank_error)

                    # Step 2: Ensure contract exists
                    contract = self._get_latest_contract(employee)
                    if not contract and self.auto_create_contracts:
                        contract = self._create_contract(employee, line)
                        created_contracts |= contract
                    else:
                        self._update_contract_from_raw_data(contract, raw_data)

                    # Step 3: Sync contract components from import data
                    contract = self._sync_contract_components(line, contract)

                    # Step 4: Create payslip with formula-based lines
                    if self.create_payslips:
                        payslip = self._create_payslip(employee, contract, line)
                        if payslip:
                            created_payslips |= payslip
                            line.payslip_id = payslip.id
                            if self.formula_config_id.use_auto_retro:
                                self._link_retro_adjustments(payslip)

                    line.state = 'processed'

                except Exception as e:
                    line.state = 'error'
                    line.error_message = str(e)
                    _logger.exception("Error processing line %s: %s", line.id, str(e))

            # Store created records
            self.created_employee_ids = [(6, 0, created_employees.ids)]
            self.created_contract_ids = [(6, 0, created_contracts.ids)]
            self.created_payslip_ids = [(6, 0, created_payslips.ids)]

            # Create or link a payslip run to group created payslips
            if self.create_payslips and created_payslips:
                if not self.payslip_run_id:
                    run_vals = {
                        'name': "%s - Payslips" % self.name,
                        'date_start': self.date_from,
                        'date_end': self.date_to,
                    }
                    run = self.env['hr.payslip.run'].create(run_vals)
                    self.payslip_run_id = run.id
                else:
                    run = self.payslip_run_id
                # Link slips to run
                created_payslips.write({'payslip_run_id': run.id})

                if self.formula_config_id.cycle_type == 'mid_cycle':
                    self._create_mid_cycle_carryovers(created_payslips, payslip_run=run)

            self.state = 'done'
            self._log("Processing complete. Created: %d employees, %d contracts, %d payslips" % (
                len(created_employees), len(created_contracts), len(created_payslips)
            ))

        except Exception as e:
            self.state = 'error'
            self._log("Processing error: %s" % str(e))
            raise UserError(_("Processing failed: %s") % str(e))

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _create_employee(self, line):
        """Create a new employee from import line data"""
        raw_data = line.get_raw_data()
        mappings = self._get_model_mappings('hr.employee')
        mapped_fields = set(mappings.mapped('target_field_id.name'))

        # Extract employee info from raw data
        mapped_name = self._get_mapped_value_for_field(raw_data, 'hr.employee', 'name')
        if 'name' in mapped_fields:
            name = mapped_name
        else:
            name = mapped_name or line.employee_name or self._extract_field(
                raw_data,
                ['name', 'full_name', 'employee_name']
            )

        if not name:
            raise ValidationError(_("Cannot create employee: Name is required"))

        mapped_email = (
            self._get_mapped_value_for_field(raw_data, 'hr.employee', 'work_email')
            or self._get_mapped_value_for_field(raw_data, 'hr.employee', 'private_email')
        )
        work_email = mapped_email if 'work_email' in mapped_fields else mapped_email or line.employee_email
        vals = {
            'name': name,
            'work_email': work_email,
            'company_id': self.company_id.id,
        }

        identifier_fields = {'employee_id', 'identification_id', 'barcode'}
        mapped_identifier = self._get_employee_identifier_value(raw_data)
        if mapped_fields & identifier_fields:
            employee_code = mapped_identifier
        else:
            employee_code = mapped_identifier or line.employee_code
        if employee_code:
            employee_code = self._normalize_code(employee_code)
            vals['identification_id'] = employee_code
            if 'employee_id' in self.env['hr.employee']._fields:
                vals['employee_id'] = employee_code

        if 'private_email' in mapped_fields and mapped_email:
            vals['private_email'] = mapped_email

        employee = self.env['hr.employee'].create(vals)
        self._update_employee_from_raw_data(employee, raw_data, line=line)
        self._log("Created employee: %s [%s]" % (employee.name, employee.identification_id))

        return employee

    def _create_contract(self, employee, line):
        """Create a new contract for employee"""
        raw_data = line.get_raw_data()

        # Get basic salary from raw data
        basic_salary = self._extract_number(raw_data, ['basic', 'basic_salary', 'wage', 'salary', 'base_salary'])
        joining_date = self._parse_date_value(self._extract_field(
            raw_data,
            ['joining_date', 'joining date', 'date_of_joining', 'join_date', 'join date']
        ))

        # Find structure from formula config
        structure = self.formula_config_id.structure_id

        date_start = self.date_from or joining_date or date.today().replace(day=1)
        name_suffix = fields.Date.to_string(date_start) if date_start else _("Contract")
        vals = {
            'name': _("%s - %s") % (employee.name, name_suffix),
            'employee_id': employee.id,
            'company_id': self.company_id.id,
            'wage': basic_salary or 0,
            'state': 'open',
            'date_start': date_start,
        }

        if structure:
            vals['struct_id'] = structure.id

        if date_start:
            future_contracts = employee.contract_ids.filtered(
                lambda c: c.date_start and c.date_start > date_start
            ).sorted(key=lambda c: c.date_start)
            if future_contracts:
                vals['date_end'] = future_contracts[0].date_start - timedelta(days=1)

        contract = self.env['hr.contract'].create(vals)
        self._update_contract_from_raw_data(contract, raw_data)
        self._log("Created contract for %s: wage=%s" % (employee.name, basic_salary))

        return contract

    def _parse_date_value(self, value):
        """Parse a date from Excel or string values."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y"):
                try:
                    return datetime.strptime(text, fmt).date()
                except ValueError:
                    continue
            for parser in (getattr(fields.Date, 'to_date', None), getattr(fields.Date, 'from_string', None)):
                if parser:
                    try:
                        return parser(text)
                    except Exception:
                        continue
        return None

    def _get_mapped_value_for_field(self, raw_data, model_name, field_name):
        mapping = self.env['hr.payslip.import.mapping'].sudo().search([
            ('salary_structure_id', '=', self.formula_config_id.id),
            ('destination_type', '=', 'field'),
            ('target_model_id.model', '=', model_name),
            ('target_field_id.name', '=', field_name),
        ], limit=1)
        if not mapping or not mapping.component_id:
            return None
        value, has_value = self._get_rule_raw_value(
            raw_data,
            mapping.component_id,
            allow_column_letter=False,
        )
        return value if has_value else None

    def _get_employee_identifier_value(self, raw_data):
        for field_name in ('employee_id', 'identification_id', 'barcode'):
            value = self._get_mapped_value_for_field(raw_data, 'hr.employee', field_name)
            if value not in (None, ''):
                return value
        return None

    def _coerce_mapped_value(self, record, field, value):
        if value in (None, ''):
            return None

        field_type = getattr(field, 'ttype', None) or getattr(field, 'type', None)
        if field_type == 'many2one':
            name_value = str(value).strip()
            if not name_value:
                return None
            relation = getattr(field, 'relation', None) or getattr(field, 'comodel_name', None)
            if not relation:
                return None
            target = self.env[relation]
            # MAPFIX B1 — the studio can now wire a column onto ANY many2one, not
            # just the four this path was written for, and `name` is not universal
            # (res.partner.bank has none; `display_name` is its account number).
            # Searching a field that does not exist raises, and CREATING one would
            # be worse: a record with a column of a spreadsheet in a field nobody
            # asked about. So: resolve by whatever the comodel calls its name, and
            # when there is nothing to resolve BY, refuse loudly and store nothing.
            # MAPFIX D5 — the predicate is `m2o_resolution_key`, and the studio's
            # card calls the SAME function, so the promise on screen and the
            # behaviour here cannot drift apart.
            key = m2o_resolution_key(target)
            if not key:
                _logger.warning(
                    "Mapped field %s.%s points at %s, which has no name field to "
                    "match %r against — the column was not stored.",
                    record._name, field.name, relation, name_value)
                return None
            existing = target.search([(key, '=ilike', name_value)], limit=1)
            if not existing:
                if not m2o_creates_missing(target):
                    _logger.warning(
                        "No %s matches %r for %s.%s, and %s records are not created "
                        "from an import — the column was not stored.",
                        relation, name_value, record._name, field.name, relation)
                    return None
                vals = {'name': name_value}
                if 'company_id' in target._fields and self.company_id:
                    vals['company_id'] = self.company_id.id
                existing = target.create(vals)
            return existing.id

        if field_type == 'boolean':
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            return text in ('1', 'true', 'yes', 'y', 't')

        if field_type in ('integer', 'float', 'monetary'):
            try:
                number = float(value)
                return int(number) if field_type == 'integer' else number
            except (TypeError, ValueError):
                return None

        if field_type == 'date':
            return self._parse_date_value(value)

        if field_type == 'datetime':
            parsed = self._parse_date_value(value)
            if isinstance(parsed, date) and not isinstance(parsed, datetime):
                return datetime.combine(parsed, datetime.min.time())
            return parsed if isinstance(parsed, datetime) else None

        if field_type == 'selection':
            selection = field.selection(record.env) if callable(field.selection) else field.selection
            allowed = []
            for entry in (selection or []):
                if isinstance(entry, (list, tuple)):
                    if entry:
                        allowed.append(entry[0])
                else:
                    allowed.append(entry)
            if not allowed and selection:
                _logger.warning(
                    "Selection for %s.%s has unexpected format: %s",
                    record._name,
                    field.name,
                    selection,
                )
            return str(value) if str(value) in allowed else None

        return str(value)

    def _get_model_mappings(self, model_name):
        # COLROLES P3 — `destination_type` is stated rather than implied. A bank row
        # has no target model, so it could not match this domain anyway; saying so
        # explicitly is what makes every consumer of this method (there are five)
        # safe to read without re-deriving that fact. `_coerce_mapped_value`'s
        # many2one path CREATES the record it cannot find, so a bank row reaching it
        # would silently mint a res.partner named after an account number.
        return self.env['hr.payslip.import.mapping'].sudo().search([
            ('salary_structure_id', '=', self.formula_config_id.id),
            ('destination_type', '=', 'field'),
            ('target_model_id.model', '=', model_name),
        ])

    def _get_bank_mappings(self):
        """The config's bank destinations, keyed by `bank_role`.

        Several columns may claim the same role in a badly-built structure; the first
        by id wins and the rest are ignored rather than fought over — there is no
        sensible way to merge two account numbers, and refusing the whole import over
        it would punish the wrong person.
        """
        mappings = self.env['hr.payslip.import.mapping'].sudo().search([
            ('salary_structure_id', '=', self.formula_config_id.id),
            ('destination_type', '=', 'bank_account'),
        ], order='id asc')
        by_role = {}
        for mapping in mappings:
            if mapping.bank_role and mapping.component_id and mapping.bank_role not in by_role:
                by_role[mapping.bank_role] = mapping
        return by_role

    def _get_mappings_by_field(self, model_name, mappings=None):
        mappings = mappings or self._get_model_mappings(model_name)
        return {mapping.target_field_id.name: mapping for mapping in mappings}

    def _get_mirrored_employee_contract_fields(self):
        return {'job_id', 'department_id', 'resource_calendar_id', 'company_id'}

    def _check_mid_cycle_overlap(self):
        if not self.date_from or not self.date_to:
            return
        overlapping = self.search([
            ('id', '!=', self.id),
            ('state', '!=', 'cancelled'),
            ('formula_config_id.cycle_type', '=', 'mid_cycle'),
            ('company_id', '=', self.company_id.id),
            ('date_from', '<=', self.date_to),
            ('date_to', '>=', self.date_from),
        ])
        if overlapping:
            names = ', '.join(overlapping.mapped('name'))
            raise UserError(_(
                "A mid-cycle payroll run already exists for the selected dates: %s. "
                "Please change the date range."
            ) % names)

    def _get_cycle_component_mappings_for_mid(self):
        return self.env['hr.payroll.cycle.component.mapping'].search([
            ('mid_cycle_config_id', '=', self.formula_config_id.id),
            ('active', '=', True),
        ])

    def _get_cycle_component_mappings_for_end(self):
        return self.env['hr.payroll.cycle.component.mapping'].search([
            ('end_cycle_config_id', '=', self.formula_config_id.id),
            ('active', '=', True),
        ])

    def _coerce_numeric_string(self, value):
        cleaned = value.strip().replace(' ', '')
        if not cleaned:
            return None
        is_percent = False
        if cleaned.endswith('%'):
            cleaned = cleaned[:-1]
            is_percent = True
        try:
            if ',' in cleaned and '.' in cleaned:
                if cleaned.rfind(',') > cleaned.rfind('.'):
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                parts = cleaned.split(',')
                if all(len(p) == 3 for p in parts[1:]):
                    cleaned = ''.join(parts)
                else:
                    cleaned = cleaned.replace(',', '.')
            elif '.' in cleaned:
                parts = cleaned.split('.')
                if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
                    cleaned = ''.join(parts)
            number = float(cleaned)
            if is_percent:
                number = number / 100
            return number
        except (ValueError, TypeError):
            return None

    def _normalize_computed_value(self, rule, value):
        if value is None:
            return 0.0
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == '':
                return 0.0
            if self._is_employee_code_rule(rule):
                return 0.0
            numeric_value = self._coerce_numeric_string(stripped)
            if numeric_value is not None:
                return numeric_value
        return 0.0

    def _sync_employee_contract_mirror_fields(self, employee, contract, raw_data,
                                              employee_mappings=None, contract_mappings=None):
        if not employee and not contract:
            return set()

        if not employee and contract:
            employee = contract.employee_id

        if not contract and employee:
            contract = employee.contract_id or False

        employee_mappings = employee_mappings or self._get_model_mappings('hr.employee')
        contract_mappings = contract_mappings or self._get_model_mappings('hr.contract')
        employee_map = self._get_mappings_by_field('hr.employee', mappings=employee_mappings)
        contract_map = self._get_mappings_by_field('hr.contract', mappings=contract_mappings)

        handled_fields = set()
        employee_updates = {}
        contract_updates = {}
        for field_name in self._get_mirrored_employee_contract_fields():
            mapping = employee_map.get(field_name) or contract_map.get(field_name)
            if not mapping or not mapping.component_id:
                continue
            value, has_value = self._get_rule_raw_value(
                raw_data,
                mapping.component_id,
                allow_column_letter=False,
            )
            if not has_value:
                continue
            handled_fields.add(field_name)
            if employee and field_name in employee._fields:
                employee_field = employee._fields[field_name]
                coerced = self._coerce_mapped_value(employee, employee_field, value)
                if coerced is not None:
                    employee_updates[field_name] = coerced
            if contract and field_name in contract._fields:
                contract_field = contract._fields[field_name]
                coerced = self._coerce_mapped_value(contract, contract_field, value)
                if coerced is not None:
                    contract_updates[field_name] = coerced

        if employee_updates and employee:
            employee.write(employee_updates)
        if contract_updates and contract:
            contract.write(contract_updates)

        return handled_fields

    def _create_mid_cycle_carryovers(self, payslips, payslip_run=None):
        mappings = self._get_cycle_component_mappings_for_mid()
        if not mappings:
            _logger.info(
                "Carryover: no mappings found for batch %s (config %s).",
                self.id, self.formula_config_id.display_name
            )
            return
        carryover_model = self.env['hr.payroll.cycle.carryover']
        carryover_model.search([('import_batch_id', '=', self.id)]).unlink()

        payslips = payslips.filtered(lambda p: p.state in ('done', 'paid', 'level1', 'level2'))
        if not payslips:
            _logger.info(
                "Carryover: no completed payslips for batch %s (config %s).",
                self.id, self.formula_config_id.display_name
            )
            return

        vals_list = []
        _logger.info(
            "Carryover: start batch %s config %s mappings=%s payslips=%s period=%s..%s",
            self.id,
            self.formula_config_id.display_name,
            len(mappings),
            len(payslips),
            self.date_from,
            self.date_to,
        )
        for idx, payslip in enumerate(payslips):
            employee = payslip.employee_id
            if not employee:
                continue
            try:
                computed_values = json.loads(payslip.formula_computed_values or '{}')
            except json.JSONDecodeError:
                computed_values = {}
            if idx < 5:
                _logger.info(
                    "Carryover: payslip %s employee %s computed_keys=%s",
                    payslip.id,
                    employee.id,
                    list(computed_values.keys())[:10],
                )

            for mapping in mappings:
                rule = mapping.mid_component_id
                value = computed_values.get(rule.code)
                if value is None and rule.column_letter:
                    value = computed_values.get(rule.column_letter)
                if idx < 5:
                    _logger.info(
                        "Carryover: mapping %s rule %s/%s value=%s",
                        mapping.id,
                        rule.code,
                        rule.column_letter,
                        value,
                    )
                amount = self._normalize_computed_value(rule, value)
                if not amount:
                    if idx < 5:
                        _logger.info(
                            "Carryover: skip rule %s for employee %s amount=%s",
                            rule.code,
                            employee.id,
                            amount,
                        )
                    continue
                vals_list.append({
                    'employee_id': employee.id,
                    'formula_config_id': self.formula_config_id.id,
                    'source_component_id': rule.id,
                    'amount': amount,
                    'date_from': self.date_from,
                    'date_to': self.date_to,
                    'payslip_run_id': payslip_run.id if payslip_run else False,
                    'import_batch_id': self.id,
                    'state': 'posted',
                })

        if vals_list:
            carryover_model.create(vals_list)
        _logger.info(
            "Carryover: created %s rows for batch %s.",
            len(vals_list),
            self.id,
        )

    def action_rebuild_cycle_carryover(self):
        self.ensure_one()
        if self.formula_config_id.cycle_type != 'mid_cycle':
            raise UserError(_("Carryover can only be rebuilt for mid-cycle batches."))
        payslips = self.created_payslip_ids
        payslip_run = self.payslip_run_id
        if not payslips and payslip_run:
            payslips = payslip_run.slip_ids
        if not payslips:
            raise UserError(_("No payslips found for this batch."))
        self._create_mid_cycle_carryovers(payslips, payslip_run=payslip_run)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Carryover rebuilt for %s') % self.name,
                'type': 'success',
                'sticky': False,
            }
        }

    def _apply_mid_cycle_carryover(self, input_values, employee):
        if not employee:
            return
        if not self.date_from or not self.date_to:
            return
        mappings = self._get_cycle_component_mappings_for_end()
        if not mappings:
            return

        carryover_model = self.env['hr.payroll.cycle.carryover']
        for mapping in mappings:
            target_rule = mapping.end_component_id
            target_code = target_rule.code or target_rule.column_letter
            if not target_code:
                continue

            carryovers = carryover_model.search([
                ('employee_id', '=', employee.id),
                ('formula_config_id', '=', mapping.mid_cycle_config_id.id),
                ('source_component_id', '=', mapping.mid_component_id.id),
                ('state', '=', 'posted'),
                ('import_batch_id', '!=', False),
                ('import_batch_id.state', '=', 'done'),
                ('date_from', '<=', self.date_to),
                ('date_to', '>=', self.date_from),
            ])
            if not carryovers:
                continue
            total_amount = sum(carryovers.mapped('amount'))
            if total_amount == 0:
                continue
            existing = input_values.get(target_code, 0.0)
            try:
                input_values[target_code] = float(existing) + total_amount
            except (TypeError, ValueError):
                input_values[target_code] = total_amount

    def _get_proration_days(self, employee, start_date, end_date, basis):
        if not start_date or not end_date or start_date > end_date:
            return 0.0
        if basis == 'workdays' and employee:
            try:
                from_dt = datetime.combine(start_date, time.min)
                to_dt = datetime.combine(end_date + timedelta(days=1), time.min)
                data = employee._get_work_days_data(from_dt, to_dt, compute_leaves=True)
                return float(data.get('days') or 0.0)
            except Exception as exc:
                _logger.info("Proration fallback to calendar days: %s", exc)
        return float((end_date - start_date).days + 1)

    def _apply_proration(self, input_values, employee, contract, raw_input_codes=None):
        config = self.formula_config_id
        if not config.use_proration:
            return
        if not self.date_from or not self.date_to:
            return
        rules = config.proration_component_ids
        if not rules:
            return
        code_map = {rule.code: rule for rule in rules if rule.code}
        if not code_map:
            return
        raw_input_codes = raw_input_codes or set()

        change_model = self.env['hr.contract.advantage.change']
        changes = change_model.search([
            ('employee_id', '=', employee.id),
            ('effective_date', '>=', self.date_from),
            ('effective_date', '<=', self.date_to),
            ('advantage_template_code', 'in', list(code_map.keys())),
        ])
        if not changes:
            return

        basis = config.proration_basis or 'calendar'
        period_days = self._get_proration_days(employee, self.date_from, self.date_to, basis)
        if not period_days:
            return

        changes_by_code = {}
        for change in changes:
            changes_by_code.setdefault(change.advantage_template_code, []).append(change)

        vals_list = []
        for code, change_list in changes_by_code.items():
            rule = code_map.get(code)
            if not rule:
                continue
            if rule.code in raw_input_codes:
                if self._normalize_header_key(rule.code) == 'laborcontractsalary':
                    _logger.info(
                        "Proration skip: batch=%s emp=%s rule=%s source=raw_input",
                        self.name,
                        employee.id,
                        rule.code,
                    )
                continue
            if self._normalize_header_key(code) == 'laborcontractsalary':
                _logger.info(
                    "Proration input: batch=%s emp=%s code=%s changes=%s",
                    self.name,
                    employee.id,
                    code,
                    [(c.id, c.effective_date, c.old_amount, c.new_amount) for c in change_list],
                )
            sorted_changes = sorted(
                change_list,
                key=lambda c: c.effective_date or self.date_from
            )
            current_start = self.date_from
            current_amount = sorted_changes[0].old_amount or 0.0
            total_weighted = 0.0
            segments = []
            for change in sorted_changes:
                effective_date = change.effective_date or self.date_from
                if effective_date < self.date_from:
                    current_amount = change.new_amount or 0.0
                    current_start = self.date_from
                    continue
                if effective_date > self.date_to:
                    break
                segment_end = effective_date - timedelta(days=1)
                if current_start <= segment_end:
                    days = self._get_proration_days(employee, current_start, segment_end, basis)
                    total_weighted += current_amount * days
                    segments.append("%s..%s: %s" % (current_start, segment_end, current_amount))
                current_amount = change.new_amount or 0.0
                current_start = effective_date
            if current_start <= self.date_to:
                days = self._get_proration_days(employee, current_start, self.date_to, basis)
                total_weighted += current_amount * days
                segments.append("%s..%s: %s" % (current_start, self.date_to, current_amount))

            prorated = total_weighted / period_days if period_days else 0.0
            if config.proration_rounding is not None:
                prorated = round(prorated, int(config.proration_rounding))

            if self._normalize_header_key(rule.code) == 'laborcontractsalary':
                _logger.info(
                    "Proration apply: batch=%s emp=%s rule=%s before=%s after=%s",
                    self.name,
                    employee.id,
                    rule.code,
                    input_values.get(rule.code),
                    prorated,
                )
            input_values[rule.code] = prorated

            old_days = 0.0
            new_days = 0.0
            if len(sorted_changes) == 1:
                effective_date = sorted_changes[0].effective_date or self.date_from
                if effective_date > self.date_from:
                    old_days = self._get_proration_days(
                        employee, self.date_from, effective_date - timedelta(days=1), basis
                    )
                new_days = period_days - old_days

            vals_list.append({
                'formula_config_id': config.id,
                'import_batch_id': self.id,
                'employee_id': employee.id,
                'contract_id': contract.id if contract else False,
                'component_id': rule.id,
                'advantage_change_id': sorted_changes[-1].id,
                'effective_date': sorted_changes[0].effective_date or self.date_from,
                'date_from': self.date_from,
                'date_to': self.date_to,
                'proration_basis': basis,
                'period_days': period_days,
                'old_days': old_days,
                'new_days': new_days,
                'old_amount': sorted_changes[0].old_amount or 0.0,
                'new_amount': sorted_changes[-1].new_amount or 0.0,
                'prorated_amount': prorated,
                'segment_summary': "\n".join(segments),
                'state': 'posted',
            })

        if vals_list:
            self.env['hr.payroll.proration.line'].create(vals_list)

    def _apply_retro_adjustments(self, input_values, employee, contract):
        config = self.formula_config_id
        if not config.use_auto_retro:
            return
        if not config.retro_component_id or not config.retro_component_id.code:
            return
        if not self.date_from:
            return
        cache = self._context.get('retro_adjustment_cache')
        if cache is None:
            cache = {}
        if employee.id in cache:
            total_delta = cache[employee.id]
        else:
            total_delta = self._prepare_retro_adjustments(employee, contract)
            cache[employee.id] = total_delta
        if not total_delta:
            return
        target_code = config.retro_component_id.code
        input_values[target_code] = input_values.get(target_code, 0.0) + total_delta

    def _prepare_retro_adjustments(self, employee, contract):
        config = self.formula_config_id
        change_model = self.env['hr.contract.advantage.change']
        retro_model = self.env['hr.payroll.retro.adjustment']
        rule_map = {
            rule.code: rule
            for rule in config.rule_ids
            if rule.code
        }
        changes = change_model.search([
            ('employee_id', '=', employee.id),
            ('effective_date', '<', self.date_from),
            ('advantage_template_code', 'in', list(rule_map.keys())),
        ])
        if not changes:
            return 0.0

        payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ['done', 'paid']),
            ('date_to', '<', self.date_from),
        ], order='date_from')
        if not payslips:
            return 0.0

        basis = config.proration_basis or 'calendar'
        total_delta = 0.0

        for change in changes:
            rule = rule_map.get(change.advantage_template_code)
            if not rule:
                continue
            old_amount = change.old_amount or 0.0
            new_amount = change.new_amount or 0.0
            delta_base = new_amount - old_amount
            if not delta_base:
                continue

            for payslip in payslips:
                if not payslip.date_from or not payslip.date_to:
                    continue
                if payslip.date_to < change.effective_date:
                    continue
                segment_start = max(change.effective_date, payslip.date_from)
                segment_end = payslip.date_to
                if segment_start > segment_end:
                    continue
                period_days = self._get_proration_days(
                    employee, payslip.date_from, payslip.date_to, basis
                )
                segment_days = self._get_proration_days(
                    employee, segment_start, segment_end, basis
                )
                if not period_days or not segment_days:
                    continue
                delta_amount = delta_base * (segment_days / period_days)
                if config.proration_rounding is not None:
                    delta_amount = round(delta_amount, int(config.proration_rounding))
                if not delta_amount:
                    continue

                existing = retro_model.search([
                    ('employee_id', '=', employee.id),
                    ('component_id', '=', rule.id),
                    ('original_payslip_id', '=', payslip.id),
                    ('advantage_change_id', '=', change.id),
                    ('state', '!=', 'cancelled'),
                ], limit=1)
                if existing:
                    continue

                retro_model.create({
                    'formula_config_id': config.id,
                    'applied_in_batch_id': self.id,
                    'employee_id': employee.id,
                    'contract_id': contract.id if contract else False,
                    'component_id': rule.id,
                    'advantage_change_id': change.id,
                    'change_effective_date': change.effective_date,
                    'period_from': payslip.date_from,
                    'period_to': payslip.date_to,
                    'old_amount': old_amount,
                    'new_amount': new_amount,
                    'delta_amount': delta_amount,
                    'original_payslip_id': payslip.id,
                    'state': 'posted',
                })
                total_delta += delta_amount

        return total_delta

    def _link_retro_adjustments(self, payslip):
        retro_lines = self.env['hr.payroll.retro.adjustment'].search([
            ('applied_in_batch_id', '=', self.id),
            ('employee_id', '=', payslip.employee_id.id),
            ('applied_in_payslip_id', '=', False),
        ])
        if retro_lines:
            retro_lines.write({'applied_in_payslip_id': payslip.id})

    def _get_mapping_updates(self, record, raw_data, mappings=None):
        mappings = mappings or self._get_model_mappings(record._name)
        # Belt and braces (COLROLES P3, test 6): callers may pass a recordset they
        # assembled themselves, and a bank row here would look up a field that is not
        # there. One line, and the guarantee holds no matter who calls.
        mappings = mappings.filtered(lambda m: m.destination_type == 'field')
        updates = {}
        for mapping in mappings:
            field = mapping.target_field_id
            if not mapping.component_id:
                continue
            if field.name not in record._fields:
                continue
            value, has_value = self._get_rule_raw_value(
                raw_data,
                mapping.component_id,
                allow_column_letter=False,
            )
            if not has_value:
                continue
            coerced = self._coerce_mapped_value(record, field, value)
            if coerced is None:
                continue
            updates[field.name] = coerced
        return updates

    def _get_latest_contract(self, employee):
        if not employee:
            return False
        contracts = employee.contract_ids
        if self.date_from or self.date_to:
            date_from = self.date_from or date.min
            date_to = self.date_to or date.max
            contracts = contracts.filtered(
                lambda c: (not c.date_start or c.date_start <= date_to)
                and (not c.date_end or c.date_end >= date_from)
            )
        contracts = contracts.sorted(key=lambda c: c.date_start or date.min, reverse=True)
        if _logger.isEnabledFor(logging.INFO):
            _logger.info(
                "Contract select: batch=%s emp=%s candidates=%s chosen=%s",
                self.name,
                employee.id,
                [(c.id, c.date_start, c.date_end) for c in contracts],
                contracts[:1].id if contracts else False,
            )
        return contracts[:1] if contracts else False

    # ==================================================================
    # COLROLES P3 — bank destinations
    #
    # Three or four spreadsheet columns ("Số tài khoản", "Ngân hàng", "Chủ tài
    # khoản", a SWIFT code) describe ONE thing: where this person's salary is paid.
    # A field mapping cannot express that — there is no scalar to point at — so a
    # bank mapping names a `bank_role` and this code assembles the parts.
    #
    # Idempotence is structural rather than remembered: the account NUMBER is the
    # key, so a second import of the same file finds the record it created the first
    # time and writes the same values into it. Nothing here ever deletes or replaces
    # an account; the worst case for a re-run is a no-op.
    # ==================================================================
    def _sanitize_acc_number(self, raw, line=None):
        """`bank_account_util.sanitize_acc_number`, plus the line-level warning.

        Damage is reported and then dropped. Guessing at a mangled account number is
        the one mistake in this file that pays somebody else's salary into the wrong
        bank, so a damaged value is worth a loud log and no record at all."""
        acc_number, damaged = sanitize_acc_number(raw)
        if damaged:
            _logger.warning(
                "Bank sync: batch=%s line=%s account number damaged by the "
                "spreadsheet (%r) — enter it as text in the source file. "
                "No bank account was created for this row.",
                self.name, line.id if line else False, raw,
            )
        return acc_number

    def _get_employee_bank_partner(self, employee):
        """The partner a `res.partner.bank` hangs off. On this platform an employee's
        contact is `work_contact_id`, and an employee without one cannot own a bank
        account at all — so one is created, exactly as the native inverse on
        `work_email`/`mobile_phone` does when it is first written."""
        partner = employee.sudo().work_contact_id
        if partner:
            return partner
        partner = self.env['res.partner'].sudo().create({
            'name': employee.name or employee.employee_id or _("Employee"),
            'company_id': (employee.company_id or self.company_id).id,
            'type': 'private',
            'email': employee.work_email or False,
        })
        employee.sudo().work_contact_id = partner.id
        return partner

    def _resolve_bank(self, bank_name, bank_bic):
        """A `res.bank` for the given name/BIC, created if genuinely new.

        Name first (that is what a spreadsheet carries), BIC second, create last.
        `=ilike` rather than `=` because "vietcombank" and "Vietcombank" are one bank
        and a payroll database with both in it is a database nobody trusts."""
        Bank = self.env['res.bank'].sudo()
        if bank_name:
            existing = Bank.search([('name', '=ilike', bank_name)], limit=1)
            if existing:
                if bank_bic and not existing.bic:
                    existing.bic = bank_bic
                return existing
        if bank_bic:
            existing = Bank.search([('bic', '=ilike', bank_bic)], limit=1)
            if existing:
                return existing
        if not bank_name and not bank_bic:
            return self.env['res.bank']
        vals = {'name': bank_name or bank_bic}
        if bank_bic:
            vals['bic'] = bank_bic
        return Bank.create(vals)

    def _link_employee_bank_account(self, employee, bank_account):
        """Attach the account to the employee without ever displacing one.

        Odoo 19 keeps employee bank accounts in a many2many (`bank_account_ids`) with
        a computed primary, where earlier versions had a single `bank_account_id`.
        Both spellings are handled because this addon tree is also read by older
        deployments — and in both cases the rule is the same: ADD, never replace. If
        somebody has already chosen where this person is paid, an import does not get
        to overrule them."""
        employee = employee.sudo()
        if 'bank_account_ids' in employee._fields:
            if bank_account.id not in employee.bank_account_ids.ids:
                employee.bank_account_ids = [(4, bank_account.id)]
            return
        if 'bank_account_id' in employee._fields and not employee.bank_account_id:
            employee.bank_account_id = bank_account.id

    def _sync_employee_bank_account(self, employee, raw_data, line=None):
        """Create or update the employee's bank account from this row's bank columns.

        Returns the `res.partner.bank` touched, or an empty recordset when there was
        nothing to do. A row with a bank NAME but no account number is not a bank
        account — creating one would produce a record that cannot be paid into — so
        it is deliberately a no-op (test 5).
        """
        if not employee:
            return self.env['res.partner.bank']
        bank_mappings = self._get_bank_mappings()
        if not bank_mappings:
            return self.env['res.partner.bank']

        values = {}
        for role, mapping in bank_mappings.items():
            raw, has_value = self._get_rule_raw_value(
                raw_data, mapping.component_id, allow_column_letter=False)
            if not has_value:
                continue
            values[role] = raw

        acc_number = self._sanitize_acc_number(values.get('acc_number'), line=line)
        if not acc_number:
            return self.env['res.partner.bank']

        bank_name = sanitize_bank_text(values.get('bank_name'))
        bank_bic = sanitize_bank_text(values.get('bank_bic'))
        holder = sanitize_bank_text(values.get('acc_holder_name'))

        partner = self._get_employee_bank_partner(employee)
        PartnerBank = self.env['res.partner.bank'].sudo()
        # Compare sanitized-to-sanitized: rows written before this code existed may
        # still carry the spaces and dashes a human typed (`acc_numbers_match`).
        existing = PartnerBank.search([('partner_id', '=', partner.id)])
        account = existing.filtered(
            lambda a: acc_numbers_match(a.acc_number, acc_number))[:1]

        bank = self._resolve_bank(bank_name, bank_bic)

        if account:
            updates = {}
            if bank and account.bank_id != bank:
                updates['bank_id'] = bank.id
            if holder and account.acc_holder_name != holder:
                updates['acc_holder_name'] = holder
            if updates:
                account.write(updates)
        else:
            vals = {'acc_number': acc_number, 'partner_id': partner.id}
            if bank:
                vals['bank_id'] = bank.id
            if holder:
                vals['acc_holder_name'] = holder
            if 'company_id' in PartnerBank._fields:
                vals['company_id'] = (employee.company_id or self.company_id).id
            account = PartnerBank.create(vals)

        self._link_employee_bank_account(employee, account)
        return account

    def _update_employee_from_raw_data(self, employee, raw_data, line=None):
        """Update employee fields from raw import data."""
        mappings = self._get_model_mappings(employee._name)
        mapped_fields = set(mappings.mapped('target_field_id.name'))
        contract_mappings = self._get_model_mappings('hr.contract')
        mirror_fields = self._get_mirrored_employee_contract_fields()
        mapped_fields |= mirror_fields.intersection(set(contract_mappings.mapped('target_field_id.name')))
        updates = self._get_mapping_updates(employee, raw_data, mappings=mappings)

        emp_code = self._extract_field(raw_data, list(EMPLOYEE_CODE_HEADER_CANDIDATES))
        if not emp_code and line and line.employee_code:
            emp_code = line.employee_code
        emp_code = self._normalize_code(emp_code) if emp_code is not None else emp_code

        id_no = self._extract_field(raw_data, [
            'id_no', 'id no', 'idno', 'id_number', 'id number', 'identification_id', 'identity'
        ])

        if emp_code and 'employee_id' in employee._fields and 'employee_id' not in mapped_fields:
            updates['employee_id'] = emp_code
        if id_no and 'identification_id' not in mapped_fields:
            updates['identification_id'] = id_no
        elif emp_code and not employee.identification_id and 'identification_id' not in mapped_fields:
            updates['identification_id'] = emp_code

        full_name = self._extract_field(raw_data, ['full_name', 'full name', 'employee_name', 'name'])
        if full_name and 'name' not in mapped_fields:
            updates['name'] = full_name

        email = self._extract_field(raw_data, ['email', 'work_email', 'emp_email', 'employee_email'])
        if email and 'work_email' not in mapped_fields:
            updates['work_email'] = email

        phone = self._extract_field(raw_data, [
            'work_phone', 'work phone', 'phone', 'phone_number', 'phone number',
            'mobile', 'mobile_phone', 'mobile phone', 'cell', 'cellphone', 'contact', 'contact_number'
        ])
        if phone:
            if 'work_phone' in employee._fields and not employee.work_phone and 'work_phone' not in mapped_fields:
                updates['work_phone'] = phone
            if 'mobile_phone' in employee._fields and not employee.mobile_phone and 'mobile_phone' not in mapped_fields:
                updates['mobile_phone'] = phone

        division = self._extract_field(raw_data, ['division'])
        if division and 'division' in employee._fields and 'division' not in mapped_fields:
            updates['division'] = division

        position = self._extract_field(raw_data, ['position'])
        if position and 'position_name' in employee._fields and 'position_name' not in mapped_fields:
            updates['position_name'] = position

        job_title = self._extract_field(raw_data, ['job_title', 'job title', 'jobtitle', 'designation'])
        if job_title:
            if 'job_title' in employee._fields and 'job_title' not in mapped_fields:
                updates['job_title'] = job_title
            elif 'job_title_text' in employee._fields and 'job_title_text' not in mapped_fields:
                updates['job_title_text'] = job_title

        joining_date = self._parse_date_value(self._extract_field(
            raw_data,
            ['joining_date', 'joining date', 'date_of_joining', 'join_date', 'join date']
        ))
        if joining_date and 'date_of_joining' in employee._fields and 'date_of_joining' not in mapped_fields:
            updates['date_of_joining'] = joining_date

        department_name = self._extract_field(raw_data, ['department', 'dept', 'department_name'])
        if department_name and 'department_id' not in mapped_fields:
            department = self.env['hr.department'].search([
                ('name', '=ilike', department_name),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
            if department:
                updates['department_id'] = department.id

        job_name = position or job_title
        if job_name and 'job_id' not in mapped_fields:
            job = self.env['hr.job'].search([
                ('name', '=ilike', job_name),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
            if job:
                updates['job_id'] = job.id

        if updates:
            employee.write(updates)

    def _update_contract_from_raw_data(self, contract, raw_data):
        """Update contract fields from raw import data."""
        if not contract:
            return
        mappings = self._get_model_mappings(contract._name)
        mapped_fields = set(mappings.mapped('target_field_id.name'))
        updates = self._get_mapping_updates(contract, raw_data, mappings=mappings)
        employee_mappings = self._get_model_mappings('hr.employee')
        handled_mirrors = self._sync_employee_contract_mirror_fields(
            contract.employee_id,
            contract,
            raw_data,
            employee_mappings=employee_mappings,
            contract_mappings=mappings,
        )
        for field_name in handled_mirrors:
            updates.pop(field_name, None)
        joining_date = self._parse_date_value(self._extract_field(
            raw_data,
            ['joining_date', 'joining date', 'date_of_joining', 'join_date', 'join date']
        ))
        if joining_date and contract.date_start != joining_date and 'date_start' not in mapped_fields:
            updates['date_start'] = joining_date
        if updates:
            contract.write(updates)

    def _create_payslip(self, employee, contract, line):
        """
        Create payslip with formula-based lines.
        This directly creates hr.payslip.line records without going through salary rules.
        """
        raw_data = line.get_raw_data()

        # Transform raw data using field mappings
        input_sources = {}
        input_values = self._transform_data_to_formula_inputs(
            raw_data,
            contract=contract,
            employee=employee,
            provenance=input_sources,
            topup_data=line.get_topup_data() if line else None,
        )

        # Create payslip
        payslip_vals = {
            'name': _("%s - %s") % (employee.name, self.date_from.strftime('%B %Y') if self.date_from else 'Payslip'),
            'employee_id': employee.id,
            'company_id': self.company_id.id,
            'contract_id': contract.id if contract else False,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'struct_id': self.formula_config_id.structure_id.id if self.formula_config_id.structure_id else False,
            'state': 'draft',
            # Store formula computation info
            'calculation_method': 'formula',
            'formula_config_id': self.formula_config_id.id,
            'formula_input_values': json.dumps(input_values),
            # SOURCING S1 — written in the same create as its sibling. Two writes
            # would leave a window where a payslip has values and no provenance,
            # which is the state S4 must be able to read as "predates the feature".
            'formula_input_sources': json.dumps(input_sources),
        }
        if 'journal_id' in self.env['hr.payslip']._fields:
            payslip_vals['journal_id'] = self._get_payroll_journal().id

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
        4) Create a default general payroll journal if none exist
        """
        Journal = self.env['account.journal'].with_context(active_test=True)
        if self.payroll_journal_id:
            return self.payroll_journal_id
        if self.formula_config_id.payroll_journal_id:
            return self.formula_config_id.payroll_journal_id

        journal = Journal.search([('type', '=', 'general'), ('company_id', '=', self.company_id.id)], limit=1, order='sequence, id')
        if journal:
            return journal
        journal = self._get_or_create_default_payroll_journal()
        if journal:
            self.payroll_journal_id = journal.id
            return journal
        raise UserError(_("No general journal found for company %s. Please set a Payroll Journal on the batch or configuration.") % (self.company_id.display_name,))

    def _get_first_general_journal(self, company):
        """Return the first general journal for a company, if any."""
        if not company:
            return None
        Journal = self.env['account.journal'].with_context(active_test=True)
        return Journal.search([('type', '=', 'general'), ('company_id', '=', company.id)], limit=1, order='sequence, id')

    def _get_or_create_default_payroll_journal(self):
        """Create a default general journal for payroll if none exist."""
        self.ensure_one()
        Journal = self.env['account.journal'].with_context(active_test=True)

        existing = Journal.search([('type', '=', 'general'), ('company_id', '=', self.company_id.id)], limit=1)
        if existing:
            return existing

        base_code = 'PAYR'
        code = base_code
        suffix = 1
        while Journal.search([('code', '=', code), ('company_id', '=', self.company_id.id)], limit=1):
            code = f"{base_code}{suffix}"
            suffix += 1

        try:
            journal = Journal.create({
                'name': _('Payroll Journal'),
                'code': code,
                'type': 'general',
                'company_id': self.company_id.id,
            })
        except Exception as e:
            _logger.warning("Failed to create default payroll journal: %s", e)
            return None

        return journal

    def _compute_and_create_payslip_lines(self, payslip, input_values):
        """
        Compute formulas and directly create hr.payslip.line records.
        Does NOT use hr.salary.rule computation.
        """
        config = self.formula_config_id
        rules = config.rule_ids.sorted(key=lambda r: r.sequence)

        employee_code_markers = EMPLOYEE_CODE_MARKERS

        def is_employee_code_rule(rule):
            tokens = [
                (rule.code or '').upper(),
                (rule.name or '').upper(),
                (rule.data_source_field or '').upper(),
            ]
            for token in tokens:
                if not token:
                    continue
                for marker in employee_code_markers:
                    if marker in token:
                        return True
            return False

        def coerce_numeric_string(value):
            cleaned = value.strip().replace(' ', '')
            if not cleaned:
                return None
            is_percent = False
            if cleaned.endswith('%'):
                cleaned = cleaned[:-1]
                is_percent = True
            try:
                if ',' in cleaned and '.' in cleaned:
                    if cleaned.rfind(',') > cleaned.rfind('.'):
                        cleaned = cleaned.replace('.', '').replace(',', '.')
                    else:
                        cleaned = cleaned.replace(',', '')
                elif ',' in cleaned:
                    parts = cleaned.split(',')
                    if all(len(p) == 3 for p in parts[1:]):
                        cleaned = ''.join(parts)
                    else:
                        cleaned = cleaned.replace(',', '.')
                elif '.' in cleaned:
                    parts = cleaned.split('.')
                    if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
                        cleaned = ''.join(parts)
                number = float(cleaned)
                if is_percent:
                    number = number / 100
                return number
            except (ValueError, TypeError):
                return None

        def normalize_payslip_amount(rule, value):
            if value is None:
                return 0.0
            if isinstance(value, bool):
                return float(value)
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                stripped = value.strip()
                if stripped == '':
                    return 0.0
                if is_employee_code_rule(rule):
                    return 0.0
                numeric_value = coerce_numeric_string(stripped)
                if numeric_value is not None:
                    return numeric_value
            return 0.0

        # Evaluate all formulas using dependency order (handles forward references)
        computed_values, computation_log = payslip._evaluate_rules_with_dependencies(
            rules,
            input_values
        )

        # Store computed values in payslip
        payslip.formula_computed_values = json.dumps(computed_values)
        payslip.formula_computation_log = "\n".join(computation_log)
        if 'report_visible_string_payload' in payslip._fields:
            payload = payslip._build_report_visible_string_payload(rules, computed_values)
            payslip.report_visible_string_payload = json.dumps(payload)
        if 'payslip_identifier_payload' in payslip._fields:
            payload = self._build_payslip_identifier_payload(rules, computed_values)
            payslip.payslip_identifier_payload = json.dumps(payload)

        # Create payslip lines directly
        line_vals_list = []
        sequence = 1

        for rule in rules:
            if not rule.appears_on_payslip:
                continue

            amount = normalize_payslip_amount(rule, computed_values.get(rule.code, 0))

            if self._normalize_header_key(rule.code) == 'laborcontractsalary':
                _logger.info(
                    "Payslip line: batch=%s slip=%s emp=%s rule=%s input=%s computed=%s amount=%s",
                    self.name,
                    payslip.id,
                    payslip.employee_id.id if payslip.employee_id else False,
                    rule.code,
                    input_values.get(rule.code),
                    computed_values.get(rule.code),
                    amount,
                )

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
                'report_visible': rule.report_visible or False,
                'component_type': rule.component_type or False,
            }

            line_vals_list.append(line_vals)
            sequence += 1

        # Bulk create payslip lines
        if line_vals_list:
            self.env['hr.payslip.line'].create(line_vals_list)

    def _build_payslip_identifier_payload(self, rules, computed_values):
        """Build payload for dynamic payslip sections."""
        payload = []
        for rule in rules:
            if not rule.payslip_identifier:
                continue
            identifier = rule.payslip_identifier.identifier
            if not identifier:
                continue
            value = computed_values.get(rule.code)
            if value is None and rule.column_letter:
                value = computed_values.get(rule.column_letter)
            payload.append({
                'identifier': identifier,
                'name': rule.name or '',
                'code': rule.code or '',
                'sequence': rule.sequence,
                'value': self._normalize_payload_value(value),
            })
        return payload

    @staticmethod
    def _normalize_payload_value(value):
        if value is None or isinstance(value, (int, float, str, bool)):
            return value
        return str(value)

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
            # If missing accounts and config has defaults, fill them once
            updates = {}
            config = self.formula_config_id
            if config.debit_account_id and not existing.account_debit:
                updates['account_debit'] = config.debit_account_id.id
            if config.credit_account_id and not existing.account_credit:
                updates['account_credit'] = config.credit_account_id.id
            if updates:
                existing.write(updates)
            return existing

        # Create a minimal salary rule so salary_rule_id is never null on payslip lines
        config = self.formula_config_id
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
        if config.debit_account_id:
            rule_vals['account_debit'] = config.debit_account_id.id
        if config.credit_account_id:
            rule_vals['account_credit'] = config.credit_account_id.id
        new_rule = SalaryRule.create(rule_vals)
        # Link back to formula rule
        formula_rule.salary_rule_id = new_rule.id
        # Optionally link to structure for visibility
        if self.formula_config_id.structure_id:
            self.formula_config_id.structure_id.rule_ids = [(4, new_rule.id)]
        return new_rule

    #: SOURCING S3 — the neutrality instrument. Incremented every time the bound
    #: branch is ENTERED. A single-source run must leave it at zero, which is a
    #: strictly stronger claim than "the numbers came out the same": it proves the
    #: new code path was never reached, rather than that it happened to agree.
    _sourcing_bound_branch_entered = 0

    @api.model
    def _sourcing_reset_branch_counter(self):
        HrPayrollImportBatch._sourcing_bound_branch_entered = 0

    @api.model
    def _sourcing_branch_counter(self):
        return HrPayrollImportBatch._sourcing_bound_branch_entered

    def _transform_data_to_formula_inputs(self, raw_data, contract=None, employee=None,
                                          provenance=None, topup_data=None):
        """Transform raw Excel data to formula input values using field mappings

        SOURCING S1 — ``provenance`` is an optional caller-supplied dict. When given,
        it is filled with one `input_provenance.entry` per code in the returned
        `input_values`, recording WHERE that number came from and WHY that source
        won. It is an OUT-PARAMETER and the return value is unchanged, so every
        existing caller keeps today's signature, today's return and today's numbers.

        This function already knew all of it. `resolved_source` has been computed on
        every branch for as long as the branches have existed, and
        `lookup_raw_value_with_key` has always handed back the header that matched —
        both were logged for two hardcoded component names and then dropped. Nothing
        new is computed here; something that was already computed stops being thrown
        away.
        """
        input_values = {}
        # `provenance is None` must stay distinguishable from an empty dict: the
        # former means "the caller does not want this", the latter "nothing resolved
        # yet". Writing into a local and copying out at the end would lose that.
        prov = provenance if provenance is not None else None
        config = self.formula_config_id
        employee = employee or (contract.employee_id if contract else None)
        employee_code_markers = EMPLOYEE_CODE_MARKERS
        contract_component_amounts = {}
        if contract:
            for advantage in contract.advantages_ids:
                template = advantage.advantage_template_id
                # Text-typed components have no amount to contribute; letting them in
                # would feed a permanent 0.0 into any formula naming them, which is
                # worse than the formula plainly having no such input.
                if template and 'value_type' in template._fields \
                        and template.value_type == 'text':
                    continue
                code = advantage.advantage_template_code or (
                    template.code if template else False
                )
                if code:
                    normalized_code = self._normalize_header_key(code)
                    if normalized_code:
                        contract_component_amounts[normalized_code] = advantage.amount

        def lookup_raw_value(candidates):
            for key in candidates:
                if key in raw_data:
                    return raw_data.get(key)
            normalized_map = {self._normalize_header_key(k): k for k in raw_data.keys()}
            for key in candidates:
                normalized_key = self._normalize_header_key(key)
                if normalized_key in normalized_map:
                    return raw_data.get(normalized_map[normalized_key])
            normalized_candidates = [
                self._normalize_header_key(key) for key in candidates if key
            ]
            normalized_candidates = [key for key in normalized_candidates if len(key) >= 6]
            if not normalized_candidates:
                return None
            matches = []
            for header_key, original_key in normalized_map.items():
                for candidate in normalized_candidates:
                    if candidate and candidate in header_key:
                        matches.append(original_key)
            if len(set(matches)) == 1:
                return raw_data.get(matches[0])
            if matches:
                _logger.info(
                    "Input match ambiguous for candidates %s: %s",
                    candidates,
                    sorted(set(matches)),
                )
            return None

        def lookup_in_with_key(data, candidates):
            """The header-matching ladder, over whichever blob it is given.

            SOURCING S3 — this is `lookup_raw_value_with_key`'s body, parameterised
            by the dict instead of closing over `raw_data`, so the top-up blob is
            searched by exactly the same rules rather than by a second
            implementation that would drift. `lookup_raw_value_with_key` below is
            now a one-line call with `raw_data`, so the unbound path is unchanged.
            """
            for key in candidates:
                if key in data:
                    return data.get(key), key
            normalized_map = {self._normalize_header_key(k): k for k in data.keys()}
            for key in candidates:
                normalized_key = self._normalize_header_key(key)
                if normalized_key in normalized_map:
                    matched = normalized_map[normalized_key]
                    return data.get(matched), matched
            normalized_candidates = [
                self._normalize_header_key(key) for key in candidates if key
            ]
            normalized_candidates = [key for key in normalized_candidates if len(key) >= 6]
            if not normalized_candidates:
                return None, None
            matches = []
            for header_key, original_key in normalized_map.items():
                for candidate in normalized_candidates:
                    if candidate and candidate in header_key:
                        matches.append(original_key)
            if len(set(matches)) == 1:
                matched = matches[0]
                return data.get(matched), matched
            if matches:
                _logger.info(
                    "Input match ambiguous for candidates %s: %s",
                    candidates,
                    sorted(set(matches)),
                )
            return None, None

        def lookup_raw_value_with_key(candidates):
            return lookup_in_with_key(raw_data, candidates)

        # SOURCING S3 — which blob is which. A run has at most two sources: the
        # primary (whatever `source_type` says) and an explicit top-up, which is by
        # definition the other kind. `rule` bindings read the FEED side, because a
        # transformation rule's output is delivered in the feed payload.
        topup = topup_data or {}
        primary_origin = ('feed' if self.source_type in ('connector', 'api_data_store')
                          else 'excel')
        topup_origin = 'excel' if primary_origin == 'feed' else 'feed'

        def blob_for_kind(kind):
            want = 'feed' if kind == 'rule' else kind
            if want == primary_origin:
                return raw_data, primary_origin
            return topup, topup_origin

        def is_employee_code_rule(rule):
            tokens = [
                (rule.code or '').upper(),
                (rule.name or '').upper(),
                (rule.data_source_field or '').upper(),
            ]
            for token in tokens:
                if not token:
                    continue
                for marker in employee_code_markers:
                    if marker in token:
                        return True
            return False

        def coerce_numeric_string(value):
            cleaned = value.strip().replace(' ', '')
            if not cleaned:
                return None
            is_percent = False
            if cleaned.endswith('%'):
                cleaned = cleaned[:-1]
                is_percent = True
            try:
                if ',' in cleaned and '.' in cleaned:
                    if cleaned.rfind(',') > cleaned.rfind('.'):
                        cleaned = cleaned.replace('.', '').replace(',', '.')
                    else:
                        cleaned = cleaned.replace(',', '')
                elif ',' in cleaned:
                    parts = cleaned.split(',')
                    if all(len(p) == 3 for p in parts[1:]):
                        cleaned = ''.join(parts)
                    else:
                        cleaned = cleaned.replace(',', '.')
                elif '.' in cleaned:
                    parts = cleaned.split('.')
                    if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
                        cleaned = ''.join(parts)
                number = float(cleaned)
                if is_percent:
                    number = number / 100
                return number
            except (ValueError, TypeError):
                return None

        def normalize_input_value(rule, value):
            if value is None:
                return rule.default_value
            if isinstance(value, bool):
                return float(value)
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                stripped = value.strip()
                if stripped == '':
                    return rule.default_value
                if is_employee_code_rule(rule):
                    return stripped
                numeric_value = coerce_numeric_string(stripped)
                if numeric_value is not None:
                    return numeric_value
                return stripped
            return value

        mapping_by_rule = {}
        if config:
            rule_ids = config.rule_ids.ids
            if rule_ids:
                # Field destinations only (COLROLES P3). `has_mapping` below suppresses
                # the column-letter fallback, so a bank-mapped rule counted here would
                # quietly lose its ability to resolve by column letter — a mapping that
                # writes nowhere near hr.employee must not change how the column reads.
                mappings = self.env['hr.payslip.import.mapping'].sudo().search([
                    ('salary_structure_id', '=', config.id),
                    ('destination_type', '=', 'field'),
                    ('component_id', 'in', rule_ids),
                ])
                mapping_by_rule = {m.component_id.id: m for m in mappings if m.component_id}

        def get_mapped_input_value(rule):
            mapping = mapping_by_rule.get(rule.id)
            if not mapping:
                return None
            model_name = mapping.target_model_id.model
            record = employee if model_name == 'hr.employee' else contract if model_name == 'hr.contract' else None
            if not record:
                return None
            field = mapping.target_field_id
            if field.name not in record._fields:
                return None
            value = getattr(record, field.name, None)
            if value in (None, ''):
                return None
            field_type = getattr(field, 'ttype', None) or getattr(field, 'type', None)
            if field_type == 'many2one':
                return value.display_name
            if field_type == 'selection':
                selection = field.selection(record.env) if callable(field.selection) else field.selection
                lookup = dict(selection or [])
                return lookup.get(value, value)
            if field_type == 'boolean':
                return bool(value)
            if field_type in ('integer', 'float', 'monetary'):
                return float(value)
            if field_type == 'date':
                return fields.Date.to_string(value)
            if field_type == 'datetime':
                return fields.Datetime.to_string(value)
            return value

        # First, try using connector field mappings if available (F114/D114.2:
        # only confirmed 'active' mappings — never 'suggested' template guesses)
        # SOURCING S2 — the gate opens for the data-store path too.
        #
        # It was written for `source_type == 'connector'`, but there is no
        # `action_load_from_connector` in this codebase: the cockpit routes a
        # connector batch to `action_load_from_data_store`, which refuses anything
        # that is not `api_data_store` (:521-522). So the branch below has never
        # executed in production and every wire drawn on the API mapping board was
        # decorative. The connector is reachable via `config.connector_id` on both
        # paths, which is what makes widening it correct rather than merely possible.
        #
        # Safe by data as well as by argument: there is no `api_data_store` batch on
        # any of the four databases (all 6 live batches are `excel`), so this changes
        # nothing that exists today.
        #
        # PRECEDENCE, stated exactly, because it is the opposite of what the guard
        # further down looks like it says. This block runs BEFORE the input loop and
        # assigns unconditionally; the loop's `if rule.code not in input_values`
        # then SKIPS a code a mapping already filled. So **an explicit mapping beats
        # a name-matched header**, and the header fills the gaps — not the reverse.
        # That is the right way round (it is the owner's "per-component binding
        # decides"), but it was never observable before this gate opened, so it is
        # written down here rather than left to be re-derived.
        #
        # Because a mapping can now displace a value that genuinely arrived, the
        # displaced one is RECORDED (`ignored`) rather than dropped — the owner's
        # rule is that the unused side is reported, never silently discarded.
        if self.source_type in ('connector', 'api_data_store') and config.connector_id:
            connector = config.connector_id.sudo()
            for mapping in connector._sync_mapping_ids():
                if mapping.target_rule_id and mapping.source_field:
                    source_value = raw_data.get(mapping.source_field)
                    if source_value is not None:
                        transformed = mapping.transform_value(source_value, raw_data)
                        target = mapping.target_rule_id
                        input_values[target.code] = normalize_input_value(
                            target, transformed
                        )
                        if prov is not None:
                            # Did a header for this same component also arrive? If so
                            # the mapping has just displaced it, and the displaced
                            # value is reported rather than dropped.
                            ignored = None
                            own_keys = [k for k in (target.name, target.code) if k]
                            if own_keys:
                                other_value, other_key = lookup_raw_value_with_key(own_keys)
                                if other_value is not None and other_key != mapping.source_field:
                                    ignored = input_provenance.ignored_side(
                                        'feed', other_key, other_value)
                            prov[target.code] = input_provenance.entry(
                                'feed', key=mapping.source_field,
                                via='connector_mapping', ignored=ignored)

        # ------------------------------------------------------------------
        # COLROLES P3 — people data stops pretending to be an input.
        #
        # An imported structure carries the employee's name, bank account and joining
        # date alongside the pay components, and until now every one of them was
        # loaded into `input_values` and handed to the formula engine, where it sat
        # unread. The exclusion below drops a column from the engine's inputs ONLY
        # when all three of these hold:
        #
        #   1. its role is not payroll — a person (or the classifier) has said it is
        #      identity/profile/contract/bank/reference data;
        #   2. no other column's formula names it — `formula_dependencies` is a
        #      comma-joined list (CR2) holding BOTH codes and COLUMN LETTERS, because
        #      an Excel formula may say `=C3` where a person would say `=DOJ`. Both
        #      spellings are checked; a coincidental letter match only ever keeps a
        #      column in, which is the safe direction;
        #   3. `appears_on_payslip` is False — a payslip LINE is created from
        #      `computed_values.get(code, 0)`, and only for rules that print.
        #
        # Neutrality proof (CR-A7): (2) says nothing computes from it and (3) says
        # nothing prints it, so its presence in `input_values` cannot change a single
        # number or line. A legacy all-payroll configuration fails (1) on every rule
        # and is therefore byte-identical. Text-component sync is untouched — it reads
        # raw_data through `_get_rule_raw_value`, never `input_values`.
        # ------------------------------------------------------------------
        referenced_codes = set()
        for rule in config.rule_ids:
            for dep in (rule.formula_dependencies or '').split(','):
                dep = dep.strip().upper()
                if dep:
                    referenced_codes.add(dep)

        def is_excluded_people_column(rule):
            if (rule.column_role or 'payroll') == 'payroll':
                return False
            if rule.appears_on_payslip:
                return False
            names = {(rule.code or '').strip().upper(),
                     (rule.column_letter or '').strip().upper(),
                     (rule.original_column_letter or '').strip().upper()}
            names.discard('')
            return not (names & referenced_codes)

        # Then, do direct mapping for input rules based on data_source_field
        raw_input_codes = set()
        excluded_people_codes = []
        for rule in config.rule_ids.filtered(lambda r: r.column_type == 'input'):
            if is_excluded_people_column(rule):
                excluded_people_codes.append(rule.code)
                continue
            if rule.code not in input_values:
                # Try to find value from raw data
                value = None
                candidates = []
                column_candidates = []
                has_mapping = rule.id in mapping_by_rule
                mapped_value = None
                resolved_source = None
                matched_key = None
                # SOURCING S3 — a binding only exists on an input, and only counts
                # when it names a key. A half-set binding resolves as unbound
                # rather than as "bound to nothing", so a partially-filled form can
                # never make a component stop resolving.
                bound_kind = rule.source_binding or False
                bound_key = (rule.source_binding_key or '').strip()
                if bound_kind and not bound_key:
                    bound_kind = False
                bound_empty = False
                matched_group = None
                is_collaborate = self._normalize_header_key(rule.code or rule.name or '') == 'collaborate'
                explicit_header_found = False

                # First try data_source_field
                if rule.data_source_field:
                    candidates.append(rule.data_source_field)

                # Try sheet-prefixed fields for multisheet imports
                if rule.source_sheet_name:
                    if rule.name:
                        candidates.append(f"{rule.source_sheet_name}|{rule.name}")
                    if rule.code:
                        candidates.append(f"{rule.source_sheet_name}|{rule.code}")
                    if not has_mapping:
                        if rule.original_column_letter:
                            column_candidates.append(
                                f"{rule.source_sheet_name}|{rule.original_column_letter}"
                            )
                        if rule.column_letter:
                            column_candidates.append(
                                f"{rule.source_sheet_name}|{rule.column_letter}"
                            )

                # Then try by rule name
                if rule.name:
                    candidates.append(rule.name)

                # Then try by rule code
                if rule.code:
                    candidates.append(rule.code)

                # Then try by column letter
                if rule.column_letter and not has_mapping:
                    column_candidates.append(rule.column_letter)

                if candidates:
                    value, candidate_key = lookup_raw_value_with_key(candidates)
                    if candidate_key is not None:
                        explicit_header_found = True
                        # SOURCING S1 — capture unconditionally. The key was already
                        # returned on every path; it was merely discarded unless the
                        # component happened to be the one hardcoded below. Capturing
                        # it cannot affect `value`, which is the neutrality argument.
                        matched_key = candidate_key
                        matched_group = 'candidates'
                if value is None and column_candidates and not explicit_header_found:
                    rule_code_key = self._normalize_header_key(rule.code) if rule.code else ''
                    component_amount = contract_component_amounts.get(rule_code_key)
                    skip_column_fallback = (
                        rule.is_contract_component
                        and component_amount is not None
                        and not self._float_equal(component_amount, 0.0)
                    )
                    if not skip_column_fallback:
                        value, column_key = lookup_raw_value_with_key(column_candidates)
                        if column_key is not None:
                            matched_key = column_key
                            matched_group = 'column_candidates'

                if isinstance(value, str) and value.strip() == '':
                    value = None

                # ----------------------------------------------------------
                # SOURCING S3 — the bound branch. ENTERED ONLY IF A BINDING EXISTS.
                #
                # It sits in FRONT of the ladder above rather than inside it, and
                # nothing reaches it unless a person (or the migration, and only
                # where it could prove the answer) declared where this component
                # reads from. That guard is the whole neutrality argument: no
                # component in any existing database has a binding, so on every run
                # that works today this block is skipped entirely — asserted by
                # `_sourcing_bound_branch_entered` staying at zero, which is a
                # stronger claim than the numbers merely agreeing.
                # ----------------------------------------------------------
                if bound_kind:
                    HrPayrollImportBatch._sourcing_bound_branch_entered += 1
                    side_b, _bo = blob_for_kind(bound_kind)
                    side_o, other_origin = (
                        (topup, topup_origin) if side_b is raw_data
                        else (raw_data, primary_origin))
                    v_b, k_b = lookup_in_with_key(side_b, [bound_key])
                    # The other side is searched by the BOUND KEY FIRST, then by the
                    # component's natural candidates. Both matter, and the bound key
                    # matters most: the same column is very often called the same
                    # thing in both sources ("Bonus Col" in the file and in the
                    # feed), and searching only by name/code/letter would miss it
                    # and report "nothing arrived" while the value sat one key away.
                    v_o, k_o = lookup_in_with_key(
                        side_o, [bound_key] + candidates + column_candidates) \
                        if side_o else (None, None)
                    if isinstance(v_b, str) and v_b.strip() == '':
                        v_b = None
                    if isinstance(v_o, str) and v_o.strip() == '':
                        v_o = None
                    if v_b is not None:
                        input_values[rule.code] = normalize_input_value(rule, v_b)
                        raw_input_codes.add(rule.code)
                        if prov is not None:
                            prov[rule.code] = input_provenance.entry(
                                bound_kind, key=k_b, via='binding',
                                # Both sides carried it: the binding wins and the
                                # loser is REPORTED. Reusing S2's `ignored_side`
                                # rather than writing a second one.
                                ignored=(input_provenance.ignored_side(
                                    other_origin, k_o, v_o) if v_o is not None else None))
                        continue
                    if v_o is not None:
                        # Owner decision 3 — fall back, but say so.
                        input_values[rule.code] = normalize_input_value(rule, v_o)
                        raw_input_codes.add(rule.code)
                        if prov is not None:
                            prov[rule.code] = input_provenance.entry(
                                other_origin, key=k_o, via='fallback', fell_back=True)
                        continue
                    # Neither side had it. Fall through to the untouched tail below
                    # so the value is exactly what an unbound component would get;
                    # only the explanation differs.
                    value = None
                    bound_empty = True

                if value is not None:
                    resolved_source = 'raw'
                    input_values[rule.code] = normalize_input_value(rule, value)
                    raw_input_codes.add(rule.code)
                else:
                    mapped_value = get_mapped_input_value(rule) if has_mapping else None
                    if mapped_value not in (None, ''):
                        resolved_source = 'mapped'
                        input_values[rule.code] = normalize_input_value(rule, mapped_value)
                    else:
                        rule_code = self._normalize_header_key(rule.code) if rule.code else ''
                        if rule_code and rule_code in contract_component_amounts:
                            resolved_source = 'contract_component'
                            input_values[rule.code] = contract_component_amounts[rule_code]
                        elif rule.is_contract_component:
                            resolved_source = 'contract_component_default'
                            input_values[rule.code] = contract_component_amounts.get(rule_code, 0.0)
                        else:
                            resolved_source = 'default'
                            input_values[rule.code] = rule.default_value

                # SOURCING S1 — one entry, built from what the branches above already
                # decided. `via` is finer-grained than `resolved_source`: a header
                # match and a column-letter match are both 'raw', and telling them
                # apart is exactly the difference between "you configured this" and
                # "the spreadsheet happened to line up".
                if prov is not None:
                    if resolved_source == 'raw':
                        via = ('column_letter' if matched_group == 'column_candidates'
                               else 'header')
                    else:
                        via = {
                            'mapped': 'employee_mapping',
                            'contract_component': 'contract',
                            'contract_component_default': 'contract_default',
                            'default': 'default',
                        }.get(resolved_source, 'default')
                        # A bound component whose source carried nothing lands on
                        # exactly the value an unbound one would have — the only
                        # difference is that it can SAY the bound source was empty,
                        # which is what the "produced nothing last run" health hint
                        # in S5 reads.
                        if bound_empty and resolved_source == 'default':
                            via = 'binding_empty'
                    prov[rule.code] = input_provenance.entry(
                        # `origin` is 'excel' for every batch until S3 gives a run a
                        # second source; the argument is passed explicitly so S3 adds
                        # a caller rather than a signature.
                        input_provenance.provenance_token(resolved_source, origin='excel'),
                        key=matched_key if resolved_source == 'raw' else None,
                        via=via,
                    )

                if self._normalize_header_key(rule.code) == 'laborcontractsalary':
                    _logger.info(
                        "Input resolve: batch=%s emp=%s contract=%s rule=%s source=%s raw=%s mapped=%s contract_component=%s final=%s",
                        self.name,
                        employee.id if employee else False,
                        contract.id if contract else False,
                        rule.code,
                        resolved_source,
                        value,
                        mapped_value,
                        contract_component_amounts.get(self._normalize_header_key(rule.code or ''), None),
                        input_values.get(rule.code),
                    )
                if is_collaborate:
                    _logger.info(
                        "Input resolve COLLABORATE: batch=%s emp=%s contract=%s source=%s matched_group=%s matched_key=%s raw=%s mapped=%s contract_component=%s final=%s",
                        self.name,
                        employee.id if employee else False,
                        contract.id if contract else False,
                        resolved_source,
                        matched_group,
                        matched_key,
                        value,
                        mapped_value,
                        contract_component_amounts.get(self._normalize_header_key(rule.code or ''), None),
                        input_values.get(rule.code),
                    )

        if excluded_people_codes and _logger.isEnabledFor(logging.INFO):
            # Logged once per line rather than per column: the point is to be able to
            # answer "why is FULLNAME not in the trace?" without reading this file.
            _logger.info(
                "Input exclusion: batch=%s config=%s dropped %d people/reference "
                "columns (unreferenced and not on the payslip): %s",
                self.name, config.id, len(excluded_people_codes),
                ', '.join(c for c in excluded_people_codes if c),
            )

        # Add constant values
        for rule in config.rule_ids.filtered(lambda r: r.column_type == 'constant'):
            input_values[rule.code] = rule.constant_value
            if prov is not None:
                prov[rule.code] = input_provenance.entry('constant', via='constant')

        # ------------------------------------------------------------------
        # SOURCING S1 — adjustments are recorded, not hidden.
        #
        # Proration, retro and mid-cycle carryover MUTATE `input_values` after every
        # component has been resolved. A chip reading "Spreadsheet · 'OT Hours'" for
        # a number proration later rewrote would be a lie of exactly the kind this
        # programme exists to remove — so each adjustment is diffed and the codes it
        # touched are stamped. The entry still says where the value came FROM; `adj`
        # says what happened to it afterwards. A code an adjustment CREATED had no
        # source at all, and says so.
        # ------------------------------------------------------------------
        def _run_adjustment(name, fn):
            if prov is None:
                fn()
                return
            before = dict(input_values)
            fn()
            for code, new_value in input_values.items():
                if code not in before:
                    # The adjustment INVENTED this code — it has no import source at
                    # all, and `via` names the adjustment that produced it.
                    prov[code] = input_provenance.entry(
                        'calculated', via=name, adj=[name])
                elif before[code] != new_value:
                    existing = prov.get(code) or input_provenance.entry('none')
                    prov[code] = input_provenance.entry(
                        existing['src'], key=existing.get('key'), via=existing['via'],
                        fell_back=existing.get('fell_back', False),
                        ignored=existing.get('ignored'),
                        adj=list(existing.get('adj') or []) + [name],
                    )

        if config.use_proration and employee:
            _run_adjustment('proration', lambda: self._apply_proration(
                input_values,
                employee,
                contract,
                raw_input_codes=raw_input_codes,
            ))

        if config.use_auto_retro and employee:
            _run_adjustment('retro', lambda: self._apply_retro_adjustments(
                input_values, employee, contract))

        if config.cycle_type == 'end_cycle':
            _run_adjustment('carryover', lambda: self._apply_mid_cycle_carryover(
                input_values, employee))

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

    def _normalize_header_key(self, value):
        if value is None:
            return ''
        return ''.join(ch for ch in str(value).lower() if ch.isalnum())

    def _find_primary_key_header(self, headers):
        candidates = list(PRIMARY_KEY_HEADER_CANDIDATES)
        for candidate in candidates:
            target = self._normalize_header_key(candidate)
            for header in headers:
                if self._normalize_header_key(header) == target:
                    return header
        return None

    def _count_header_matches(self, headers):
        rules = self.formula_config_id.rule_ids
        lookup = set()
        for rule in rules:
            if rule.code:
                lookup.add(self._normalize_header_key(rule.code))
            if rule.name:
                lookup.add(self._normalize_header_key(rule.name))
            if rule.source_sheet_name:
                lookup.add(self._normalize_header_key(rule.source_sheet_name))
        count = 0
        for header in headers:
            if self._normalize_header_key(header) in lookup:
                count += 1
        return count

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

    def _normalize_phone(self, value):
        """Normalize phone number for matching"""
        if not value:
            return False
        digits = ''.join(ch for ch in str(value) if ch.isdigit())
        return digits or False

    def _lookup_raw_value(self, raw_data, candidates):
        for key in candidates:
            if key in raw_data:
                return raw_data.get(key)
        normalized_map = {self._normalize_header_key(k): k for k in raw_data.keys()}
        for key in candidates:
            normalized_key = self._normalize_header_key(key)
            if normalized_key in normalized_map:
                return raw_data.get(normalized_map[normalized_key])
        return None

    def _get_rule_raw_value(self, raw_data, rule, allow_column_letter=True):
        if not rule:
            return None, False
        candidates = []

        if rule.data_source_field:
            candidates.append(rule.data_source_field)

        if rule.source_sheet_name:
            if rule.name:
                candidates.append(f"{rule.source_sheet_name}|{rule.name}")
            if rule.code:
                candidates.append(f"{rule.source_sheet_name}|{rule.code}")
            if allow_column_letter:
                if rule.original_column_letter:
                    candidates.append(f"{rule.source_sheet_name}|{rule.original_column_letter}")
                if rule.column_letter:
                    candidates.append(f"{rule.source_sheet_name}|{rule.column_letter}")

        if rule.name:
            candidates.append(rule.name)
        if rule.code:
            candidates.append(rule.code)
        if allow_column_letter and rule.column_letter:
            candidates.append(rule.column_letter)

        value = self._lookup_raw_value(raw_data, candidates) if candidates else None
        if isinstance(value, str) and value.strip() == '':
            return None, False
        if value is None:
            return None, False
        return value, True

    def _is_employee_code_rule(self, rule):
        """Role first, marker heuristic second.

        The marker scan below is the original test and stays as the fallback, so a
        rule nobody has classified yet behaves exactly as it did. The role short-
        circuits it because a column an operator has explicitly filed as Identity is
        an identifier even when its header does not happen to contain the word
        "code" — and the upgrade migration only hands out `identity` on marker or
        field-mapping evidence, so no existing row changes hands here."""
        if getattr(rule, 'column_role', False) == 'identity':
            return True
        employee_code_markers = EMPLOYEE_CODE_MARKERS
        tokens = [
            (rule.code or '').upper(),
            (rule.name or '').upper(),
            (rule.data_source_field or '').upper(),
        ]
        for token in tokens:
            if not token:
                continue
            for marker in employee_code_markers:
                if marker in token:
                    return True
        return False

    def _coerce_numeric_string(self, value):
        cleaned = value.strip().replace(' ', '')
        if not cleaned:
            return None
        is_percent = False
        if cleaned.endswith('%'):
            cleaned = cleaned[:-1]
            is_percent = True
        try:
            if ',' in cleaned and '.' in cleaned:
                if cleaned.rfind(',') > cleaned.rfind('.'):
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                parts = cleaned.split(',')
                if all(len(p) == 3 for p in parts[1:]):
                    cleaned = ''.join(parts)
                else:
                    cleaned = cleaned.replace(',', '.')
            elif '.' in cleaned:
                parts = cleaned.split('.')
                if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
                    cleaned = ''.join(parts)
            number = float(cleaned)
            if is_percent:
                number = number / 100
            return number
        except (ValueError, TypeError):
            return None

    def _normalize_rule_input_value(self, rule, value):
        if value is None:
            return rule.default_value
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == '':
                return rule.default_value
            if self._is_employee_code_rule(rule):
                return stripped
            numeric_value = self._coerce_numeric_string(stripped)
            if numeric_value is not None:
                return numeric_value
            return stripped
        return value

    def _normalize_component_text(self, value):
        """Spreadsheet cell -> the string a text component stores. Whole floats are
        rendered without the trailing `.0` openpyxl gives them, because a job grade
        read as 3.0 should land on the contract as "3"."""
        if value is None:
            return ''
        if isinstance(value, bool):
            return 'Yes' if value else 'No'
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return str(value).strip()

    def _float_equal(self, left, right, tolerance=0.0001):
        try:
            return abs(float(left or 0.0) - float(right or 0.0)) <= tolerance
        except (TypeError, ValueError):
            return False

    def _get_contract_component_rules(self):
        if not self.formula_config_id:
            return self.env['hr.formula.rule']
        return self.formula_config_id.rule_ids.filtered(lambda r: r.is_contract_component)

    def _get_or_create_advantage_template(self, rule, cache):
        if rule.code in cache:
            return cache[rule.code]
        template = self.env['hr.contract.advantage.template'].search([
            ('code', '=', rule.code)
        ], limit=1)
        wanted_type = 'text' if getattr(rule, 'is_text_component', False) else 'amount'
        if not template:
            template = self.env['hr.contract.advantage.template'].create({
                'name': rule.name or rule.code,
                'code': rule.code,
                'lower_bound': 0.0,
                'upper_bound': 0.0,
                'default_value': 0.0,
                'value_type': wanted_type,
            })
        elif 'value_type' in template._fields and template.value_type != wanted_type:
            # An existing template is NEVER flipped. Every line already filed under it
            # was written as the other kind, and re-typing the template would silently
            # reinterpret all of that history. The workbook is told, not obeyed.
            _logger.warning(
                "Contract component sync: rule %s wants value type %s but template %s "
                "is already %s — keeping the template as it is.",
                rule.code, wanted_type, template.code, template.value_type)
        cache[rule.code] = template
        return template

    def _get_contract_advantage_map(self, contract):
        lines = contract.advantages_ids if contract else self.env['hr.contract.advantage']
        advantage_map = {}
        for line in lines:
            code = line.advantage_template_code or (
                line.advantage_template_id.code if line.advantage_template_id else False
            )
            if code:
                advantage_map[code] = line
        return advantage_map

    def _log_contract_component_change(self, contract, template, old_amount, new_amount,
                                       source, notes=None, old_text=None, new_text=None):
        vals = {
            'contract_id': contract.id,
            'advantage_template_id': template.id,
            'old_amount': old_amount,
            'new_amount': new_amount,
            'effective_date': self.date_from or fields.Date.context_today(self),
            'change_source': source,
            'import_batch_id': self.id,
            'notes': notes or False,
        }
        Change = self.env['hr.contract.advantage.change']
        if 'old_text_value' in Change._fields:
            vals['old_text_value'] = old_text or False
            vals['new_text_value'] = new_text or False
        Change.create(vals)

    def _create_new_contract_for_components(self, contract):
        if not contract:
            return contract
        effective_date = self.date_from or fields.Date.context_today(self)
        updates = {}
        if 'date_end' in contract._fields and (not contract.date_end or contract.date_end >= effective_date):
            updates['date_end'] = effective_date - timedelta(days=1)
        if updates:
            contract.write(updates)
        new_contract = contract.copy({
            'date_start': effective_date,
            'date_end': False,
        })
        return new_contract

    def _sync_contract_components(self, line, contract):
        rules = self._get_contract_component_rules()
        if not contract or not rules:
            return contract

        raw_data = line.get_raw_data() if line else {}
        template_cache = {}
        desired_values = {}
        new_contract_needed = False
        line_map = self._get_contract_advantage_map(contract)

        for rule in rules:
            template = self._get_or_create_advantage_template(rule, template_cache)
            existing_line = line_map.get(template.code)
            is_text = 'value_type' in template._fields and template.value_type == 'text'
            value, found = self._get_rule_raw_value(
                raw_data,
                rule,
                allow_column_letter=False,
            )
            if is_text:
                # Text components never touch `amount`; an absent cell keeps whatever
                # the contract already says rather than blanking it.
                if found:
                    new_value = self._normalize_component_text(value)
                else:
                    new_value = (existing_line.text_value or '') if existing_line else ''
                desired_values[template.code] = {
                    'template': template,
                    'value': new_value,
                    'found': found,
                    'rule': rule,
                    'is_text': True,
                }
                if found and rule.requires_new_contract:
                    old_text = (existing_line.text_value or '') if existing_line else ''
                    if old_text != new_value:
                        new_contract_needed = True
                continue
            if found:
                new_value = self._normalize_rule_input_value(rule, value)
            else:
                new_value = existing_line.amount if existing_line else 0.0

            if self._normalize_header_key(rule.code) == 'laborcontractsalary':
                _logger.info(
                    "Contract component sync: batch=%s emp=%s contract=%s rule=%s found=%s raw=%s existing=%s new=%s",
                    self.name,
                    contract.employee_id.id if contract.employee_id else False,
                    contract.id,
                    rule.code,
                    found,
                    value,
                    existing_line.amount if existing_line else None,
                    new_value,
                )

            desired_values[template.code] = {
                'template': template,
                'value': new_value,
                'found': found,
                'rule': rule,
                'is_text': False,
            }

            if found and rule.requires_new_contract:
                existing_line = line_map.get(template.code)
                old_value = existing_line.amount if existing_line else 0.0
                if not self._float_equal(old_value, new_value):
                    new_contract_needed = True

        if new_contract_needed:
            contract = self._create_new_contract_for_components(contract)
            line_map = self._get_contract_advantage_map(contract)

        for code, data in desired_values.items():
            template = data['template']
            new_value = data['value']
            found = data['found']
            rule = data['rule']
            line_obj = line_map.get(code)
            source = 'import' if found else 'import_default'

            if data.get('is_text'):
                if line_obj:
                    old_text = line_obj.text_value or ''
                    if old_text != new_value:
                        line_obj.write({'text_value': new_value or False})
                        self._log_contract_component_change(
                            contract, template, 0.0, 0.0, source,
                            old_text=old_text, new_text=new_value
                        )
                else:
                    line_obj = self.env['hr.contract.advantage'].create({
                        'contract_id': contract.id,
                        'advantage_template_id': template.id,
                        'text_value': new_value or False,
                    })
                    line_map[code] = line_obj
                    self._log_contract_component_change(
                        contract, template, 0.0, 0.0, source,
                        notes='Created contract component',
                        old_text='', new_text=new_value
                    )
            elif line_obj:
                old_value = line_obj.amount
                if not self._float_equal(old_value, new_value):
                    line_obj.write({'amount': new_value})
                    self._log_contract_component_change(
                        contract, template, old_value, new_value, source
                    )
            else:
                line_obj = self.env['hr.contract.advantage'].create({
                    'contract_id': contract.id,
                    'advantage_template_id': template.id,
                    'amount': new_value,
                })
                line_map[code] = line_obj
                self._log_contract_component_change(
                    contract, template, 0.0, new_value, source,
                    notes='Created contract component'
                )

        # Ensure latest contract component values are visible for downstream computations.
        if hasattr(contract, 'invalidate_recordset'):
            contract.invalidate_recordset()
        else:
            contract.invalidate_cache(['advantages_ids'])

        return contract

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
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.created_employee_ids.ids)],
        }

    def action_view_created_payslips(self):
        """View created payslips"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Created Payslips'),
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.created_payslip_ids.ids)],
        }

    def action_open_payslip_run(self):
        self.ensure_one()
        if not self.payslip_run_id:
            return False
        view = self.env.ref('om_hr_payroll.hr_payslip_run_form', raise_if_not_found=False)
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Payslip Run'),
            'res_model': 'hr.payslip.run',
            'view_mode': 'form',
            'res_id': self.payslip_run_id.id,
            'target': 'current',
        }
        if view:
            action['views'] = [(view.id, 'form')]
        return action
