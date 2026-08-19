# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# The vocabulary of "what kind of thing a connector pulls", declared ONCE.
#
# `hr.integration.endpoint` describes the FEED that produces these rows, so the
# two models have to agree exactly or a feed can be catalogued for a data type
# the store cannot hold (and its counts would silently always be zero). Sharing
# the list is the only way that stays true through a later edit — the endpoint
# model imports this constant rather than retyping it.
DATA_TYPES = [
    ('employee', 'Employee Master Data'),
    ('salary', 'Salary / Compensation'),
    ('attendance', 'Attendance'),
    ('leave', 'Leave / Time-Off'),
    ('dependent', 'Dependents / Family'),
    ('benefit', 'Benefits'),
    ('tax', 'Tax Information'),
    ('custom', 'Custom / Other'),
]


class HrApiDataStore(models.Model):
    """
    API Data Store — Local Cache of External HRIS Data.

    Implements the Pull → Store → Transform → Map → Compute pipeline.
    Three-layer architecture:
      Layer 1: Raw Payload (immutable audit trail)
      Layer 2: Extracted Data (flattened, queryable)
      Layer 2b: Computed Data (from transformation rules)
      Layer 3: Versioning & Change Detection
    """
    _name = 'hr.api.data.store'
    _description = 'API Data Store — Local Cache of External HRIS Data'
    _order = 'pull_date desc, id desc'

    # ==========================================
    # IDENTITY
    # ==========================================
    connector_id = fields.Many2one(
        'hr.integration.connector', string='Source Connector',
        required=True, ondelete='cascade', index=True,
    )
    data_type = fields.Selection(
        DATA_TYPES, string='Data Type', required=True, index=True)

    employee_external_id = fields.Char(
        string='External Employee ID', index=True,
        help="Employee ID in the source HRIS system",
    )
    employee_id = fields.Many2one(
        'hr.employee', string='Matched Employee',
        help="Employee this data belongs to (matched after pull)",
    )

    # ==========================================
    # PERIOD
    # ==========================================
    period_from = fields.Date(string='Period From')
    period_to = fields.Date(string='Period To')
    period_label = fields.Char(
        string='Period', compute='_compute_period_label', store=True,
    )

    # ==========================================
    # LAYER 1: RAW PAYLOAD (immutable after write)
    # ==========================================
    raw_payload = fields.Json(
        string='Raw API Response',
        help="Complete, unmodified API response. Never edited after initial write.",
    )

    # ==========================================
    # LAYER 2: EXTRACTED DATA (flattened for mapping)
    # ==========================================
    extracted_data = fields.Json(
        string='Extracted Data',
        help="Flattened key-value pairs extracted from raw payload, ready for field mapping.",
    )

    # ==========================================
    # LAYER 2b: COMPUTED DATA (from transformation rules)
    # ==========================================
    computed_data = fields.Json(
        string='Computed Data',
        help="Derived values produced by transformation rules (e.g., dependent count, tenure). "
             "Merged with extracted_data at mapping time.",
    )

    # ==========================================
    # LAYER 3: VERSIONING & CHANGE DETECTION
    # ==========================================
    version = fields.Integer(
        string='Version', default=1,
        help="Increments with each pull for the same employee+data_type+period",
    )
    previous_version_id = fields.Many2one(
        'hr.api.data.store', string='Previous Version',
        help="Link to previous pull for change detection",
    )
    change_summary = fields.Json(
        string='Changes from Previous',
        help="Diff: {field: {old: x, new: y}} — auto-computed on pull",
    )
    has_changes = fields.Boolean(
        string='Has Changes', compute='_compute_has_changes', store=True,
    )

    # ==========================================
    # METADATA
    # ==========================================
    pull_date = fields.Datetime(
        string='Pull Date', default=fields.Datetime.now, required=True,
    )
    pull_duration_ms = fields.Integer(
        string='Pull Duration (ms)',
        help="How long the API call took",
    )
    pull_triggered_by = fields.Selection([
        ('manual', 'Manual (Button Click)'),
        ('cron', 'Scheduled (Cron Job)'),
    ], string='Triggered By', default='manual')

    state = fields.Selection([
        ('raw', 'Raw (Just Pulled)'),
        ('extracted', 'Extracted (Ready for Mapping)'),
        ('consumed', 'Consumed (Used in Import Batch)'),
        ('archived', 'Archived'),
        ('error', 'Error'),
    ], string='Status', default='raw', index=True)

    error_message = fields.Text(string='Error Message')

    # Traceability: which import batch consumed this data
    import_batch_id = fields.Many2one(
        'hr.payroll.import.batch', string='Used in Import Batch',
        readonly=True,
    )

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    @api.depends('employee_external_id', 'data_type', 'pull_date')
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.employee_external_id or '?', rec.data_type or '?']
            if rec.pull_date:
                parts.append(rec.pull_date.strftime('%Y-%m-%d %H:%M'))
            rec.display_name = ' / '.join(parts)

    @api.depends('period_from', 'period_to')
    def _compute_period_label(self):
        for rec in self:
            if rec.period_from and rec.period_to:
                rec.period_label = f"{rec.period_from} → {rec.period_to}"
            else:
                rec.period_label = False

    @api.depends('change_summary')
    def _compute_has_changes(self):
        for rec in self:
            rec.has_changes = bool(rec.change_summary)

    # ==========================================
    # EXTRACTION LOGIC
    # ==========================================
    def action_extract(self):
        """Extract flattened data from raw payload."""
        for rec in self:
            if not rec.raw_payload:
                rec.state = 'error'
                rec.error_message = _("No raw payload to extract from.")
                continue
            try:
                extracted = rec._extract_from_raw(rec.raw_payload)
                rec.extracted_data = extracted
                rec.state = 'extracted'
                rec.error_message = False
            except Exception as e:
                rec.state = 'error'
                rec.error_message = _("Extraction failed: %s") % str(e)
                _logger.exception("Extraction failed for data store %s: %s", rec.id, str(e))

    def _extract_from_raw(self, raw_payload):
        """
        Flatten a raw API payload into a simple key-value dict.

        Handles common API response wrappers:
          - Zoho: {"response": {"result": [{...}]}}
          - SAP:  {"d": {"results": [{...}]}}
          - Direct: {key: value, ...}
        """
        if not raw_payload:
            return {}

        data = raw_payload

        # Unwrap common response wrappers
        if isinstance(data, dict):
            # Zoho format: response.result[0]
            if 'response' in data and isinstance(data['response'], dict):
                result = data['response'].get('result', data['response'])
                if isinstance(result, list) and result:
                    data = result[0]
                elif isinstance(result, dict):
                    data = result

            # SAP format: d.results[0]
            elif 'd' in data and isinstance(data['d'], dict):
                results = data['d'].get('results', data['d'])
                if isinstance(results, list) and results:
                    data = results[0]
                elif isinstance(results, dict):
                    data = results

            # Generic wrapper: data[0] for list response
            elif 'data' in data:
                inner = data['data']
                if isinstance(inner, list) and inner:
                    data = inner[0]
                elif isinstance(inner, dict):
                    data = inner

        # If data is still a list, take the first item
        if isinstance(data, list) and data:
            data = data[0]

        # Flatten nested dicts using dot-notation
        return self._flatten_dict(data) if isinstance(data, dict) else {}

    def _flatten_dict(self, d, parent_key='', sep='.'):
        """Recursively flatten a nested dict, keeping leaf values only."""
        items = {}
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.update(self._flatten_dict(v, new_key, sep=sep))
            elif isinstance(v, list):
                # For lists of primitives, store as-is
                # For lists of dicts, skip (these are child records, handled by data_type)
                if not v or not isinstance(v[0], dict):
                    items[new_key] = v
            else:
                items[new_key] = v
        # Also keep top-level keys without prefix for easy mapping
        if parent_key:
            for k, v in d.items():
                if not isinstance(v, (dict, list)):
                    if k not in items:
                        items[k] = v
        return items

    # ==========================================
    # VERSIONING & DIFF
    # ==========================================
    def _compute_version_and_diff(self):
        """
        For each record, find the previous version with same employee+data_type+connector,
        compute version number, and generate change_summary.
        """
        for rec in self:
            # Find previous version
            domain = [
                ('connector_id', '=', rec.connector_id.id),
                ('employee_external_id', '=', rec.employee_external_id),
                ('data_type', '=', rec.data_type),
                ('id', '!=', rec.id),
            ]
            # If we have period, match on period too
            if rec.period_from and rec.period_to:
                domain += [
                    ('period_from', '=', rec.period_from),
                    ('period_to', '=', rec.period_to),
                ]

            previous = self.search(domain, order='pull_date desc, id desc', limit=1)

            if previous:
                rec.previous_version_id = previous.id
                rec.version = previous.version + 1
                # Compute diff
                rec.change_summary = self._compute_diff(
                    previous.extracted_data or {},
                    rec.extracted_data or {}
                )
            else:
                rec.previous_version_id = False
                rec.version = 1
                rec.change_summary = False

    @staticmethod
    def _compute_diff(old_data, new_data):
        """
        Compute field-level diff between two extracted_data dicts.
        Returns: {field: {old: x, new: y}} for changed fields.
        """
        if not old_data and not new_data:
            return {}

        old_data = old_data or {}
        new_data = new_data or {}

        changes = {}
        all_keys = set(list(old_data.keys()) + list(new_data.keys()))

        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)
            # Compare as strings to handle type differences (e.g., "15000000" vs 15000000)
            if str(old_val) != str(new_val):
                changes[key] = {'old': old_val, 'new': new_val}

        return changes if changes else {}

    # ==========================================
    # EMPLOYEE MATCHING
    # ==========================================
    def action_match_employees(self):
        """Try to match stored records to employee records."""
        matched = 0
        for rec in self.filtered(lambda r: not r.employee_id and r.employee_external_id):
            employee = rec._find_matching_employee()
            if employee:
                rec.employee_id = employee.id
                matched += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Employee Matching'),
                'message': _('Matched %d records to employees.') % matched,
                'type': 'success',
            }
        }

    def _find_matching_employee(self):
        """Find an employee record matching this record's external ID."""
        Employee = self.env['hr.employee']

        if not self.employee_external_id:
            return False

        ext_id = self.employee_external_id.strip()

        # Try by employee code / barcode / identification_id
        employee = Employee.search([
            '|', '|',
            ('identification_id', '=', ext_id),
            ('barcode', '=', ext_id),
            ('employee_id', '=', ext_id),
        ], limit=1)
        if employee:
            return employee

        # Try by work email
        extracted = self.extracted_data or {}
        email = extracted.get('Email') or extracted.get('email') or extracted.get('work_email')
        if email:
            employee = Employee.search([
                '|',
                ('work_email', '=ilike', email),
                ('private_email', '=ilike', email),
            ], limit=1)
            if employee:
                return employee

        return False

    # ==========================================
    # MERGE DATA FOR MAPPING
    # ==========================================
    def get_mappable_data(self):
        """
        Return merged dict of extracted_data + computed_data.
        computed_data keys override extracted_data if same name (intentional).
        """
        self.ensure_one()
        result = dict(self.extracted_data or {})
        if self.computed_data:
            result.update(self.computed_data)
        return result

    # ==========================================
    # STATE MANAGEMENT
    # ==========================================
    def action_mark_consumed(self, import_batch):
        """Mark records as consumed by an import batch."""
        self.write({
            'state': 'consumed',
            'import_batch_id': import_batch.id,
        })

    def action_archive(self):
        """Archive old records."""
        self.write({'state': 'archived'})

    def action_re_extract(self):
        """Re-extract data from raw payload (e.g., after fixing extraction logic)."""
        self.action_extract()

    def action_recompute_transformations(self):
        """Trigger transformation rules to recompute computed_data."""
        for rec in self:
            if rec.connector_id:
                rules = self.env['hr.api.transformation.rule'].search([
                    ('connector_id', '=', rec.connector_id.id),
                    ('active', '=', True),
                ])
                if rules:
                    rules._execute_for_records(rec)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Transformations Recomputed'),
                'message': _('Computed data updated for %d records.') % len(self),
                'type': 'success',
            }
        }
