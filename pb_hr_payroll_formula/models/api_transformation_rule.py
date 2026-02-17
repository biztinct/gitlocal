# -*- coding: utf-8 -*-

import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class HrApiTransformationRule(models.Model):
    """
    API Data Transformation Rule.

    Derives values from sets of stored records that don't exist in any single API record.
    Examples: count dependents, calculate tenure, sum attendance days.

    Transformation rules run AFTER pull/extraction and BEFORE field mapping.
    Results are written to computed_data (JSONB) on the data store record.
    """
    _name = 'hr.api.transformation.rule'
    _description = 'API Data Transformation Rule'
    _order = 'sequence, id'

    # ==========================================
    # IDENTITY
    # ==========================================
    connector_id = fields.Many2one(
        'hr.integration.connector', string='Connector',
        required=True, ondelete='cascade',
    )
    name = fields.Char(
        string='Rule Name', required=True,
        help="e.g., 'Count Dependents', 'Calculate Tenure'",
    )
    output_key = fields.Char(
        string='Output Key', required=True,
        help="Key name written to computed_data, e.g., 'NUM_DEPENDENTS'. "
             "This becomes available for field mapping.",
    )
    description = fields.Text(
        string='Description',
        help="Explain what this rule computes and why.",
    )

    # ==========================================
    # RULE TYPE
    # ==========================================
    rule_type = fields.Selection([
        ('count', 'Count Records'),
        ('sum', 'Sum Field Across Records'),
        ('avg', 'Average Field Across Records'),
        ('min', 'Minimum Field Across Records'),
        ('max', 'Maximum Field Across Records'),
        ('date_diff', 'Date Difference Calculation'),
        ('date_check', 'Date Condition Check'),
        ('python', 'Python Expression (Advanced)'),
    ], string='Rule Type', required=True, default='count')

    # ==========================================
    # SOURCE: Which stored records to operate on
    # ==========================================
    source_data_type = fields.Selection([
        ('employee', 'Employee Master Data'),
        ('salary', 'Salary / Compensation'),
        ('attendance', 'Attendance'),
        ('leave', 'Leave / Time-Off'),
        ('dependent', 'Dependents / Family'),
        ('benefit', 'Benefits'),
        ('tax', 'Tax Information'),
        ('custom', 'Custom / Other'),
    ], string='Source Data Type', required=True,
        help="Which data_type records to operate on. "
             "e.g., 'dependent' to count dependent records.",
    )

    # ==========================================
    # AGGREGATE SETTINGS (count, sum, avg, min, max)
    # ==========================================
    aggregate_field = fields.Char(
        string='Field to Aggregate',
        help="For sum/avg/min/max: which key in extracted_data to aggregate. "
             "Leave empty for count (counts records, not a field).",
    )
    filter_expression = fields.Char(
        string='Filter Expression',
        help="Optional Python expression to filter records before aggregating. "
             "Available: `rec` (the extracted_data dict), `env` (Odoo env). "
             "Examples:\n"
             "  rec.get('status') == 'Active'\n"
             "  rec.get('relationship') == 'Child'\n"
             "  rec.get('age', 0) < 18",
    )

    # ==========================================
    # DATE SETTINGS (date_diff, date_check)
    # ==========================================
    date_source_field = fields.Char(
        string='Date Source Field',
        help="Key in extracted_data containing the date, e.g., 'date_of_joining'",
    )
    date_compare_to = fields.Selection([
        ('period_start', 'Period Start Date'),
        ('period_end', 'Period End Date'),
        ('today', 'Today'),
        ('fixed', 'Fixed Date'),
    ], string='Compare To', default='period_end')
    date_fixed_value = fields.Date(string='Fixed Date')
    date_unit = fields.Selection([
        ('days', 'Days'),
        ('months', 'Months'),
        ('years', 'Years'),
    ], string='Result Unit', default='months',
        help="For date_diff: return difference in days, months, or years.",
    )
    date_check_operator = fields.Selection([
        ('before', 'Is Before'),
        ('after', 'Is After'),
        ('within', 'Is Within N months'),
    ], string='Check Operator')
    date_check_value = fields.Integer(
        string='Check Value (months)',
        help="For 'within' operator: number of months to check.",
    )

    # ==========================================
    # PYTHON (advanced, full flexibility)
    # ==========================================
    python_code = fields.Text(
        string='Python Expression',
        help="Advanced: Full Python code. Available variables:\n"
             "  `records` — list of extracted_data dicts for this data_type\n"
             "  `employee_data` — the employee's own extracted_data dict\n"
             "  `all_records` — dict of {data_type: [records]} for all types\n"
             "  `period_start`, `period_end` — batch period dates\n"
             "  `env` — Odoo environment\n"
             "  `employee` — hr.employee record (if matched)\n\n"
             "Must set `result = <value>` as the output.\n\n"
             "Example:\n"
             "  children = [r for r in records if r.get('relationship') == 'Child']\n"
             "  minors = [c for c in children if c.get('age', 0) < 18]\n"
             "  result = len(minors)",
    )

    # ==========================================
    # SETTINGS
    # ==========================================
    default_value = fields.Float(
        string='Default Value', default=0,
        help="Value to use if no matching records found or rule errors.",
    )
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    # ==========================================
    # EXECUTION ENGINE
    # ==========================================
    def _execute_for_records(self, data_store_records):
        """
        Execute all transformation rules against a set of data store records.

        For each unique employee in the target records, we:
        1. Gather all their data store records by data_type
        2. Run each rule that matches the source_data_type
        3. Write results to computed_data on the employee's salary/employee record
        """
        DataStore = self.env['hr.api.data.store']

        # Group target records by employee
        employee_records = {}
        for rec in data_store_records:
            key = rec.employee_external_id or f"_no_ext_id_{rec.id}"
            if key not in employee_records:
                employee_records[key] = {
                    'main_record': rec,
                    'all_records': {},
                }
            data_type = rec.data_type
            if data_type not in employee_records[key]['all_records']:
                employee_records[key]['all_records'][data_type] = []
            employee_records[key]['all_records'][data_type].append(rec)

        # For employees whose records are in our set, also load their other data types
        for emp_ext_id, emp_data in employee_records.items():
            if emp_ext_id.startswith('_no_ext_id_'):
                continue
            main_rec = emp_data['main_record']
            all_store_records = DataStore.search([
                ('connector_id', '=', main_rec.connector_id.id),
                ('employee_external_id', '=', emp_ext_id),
                ('state', 'in', ['extracted', 'consumed']),
            ])
            for sr in all_store_records:
                if sr.data_type not in emp_data['all_records']:
                    emp_data['all_records'][sr.data_type] = []
                if sr.id not in [r.id for r in emp_data['all_records'][sr.data_type]]:
                    emp_data['all_records'][sr.data_type].append(sr)

        # Execute each rule for each employee
        for emp_ext_id, emp_data in employee_records.items():
            main_rec = emp_data['main_record']
            computed = dict(main_rec.computed_data or {})

            for rule in self:
                try:
                    value = rule._execute_single(
                        emp_data['all_records'],
                        main_rec,
                    )
                    computed[rule.output_key] = value
                except Exception as e:
                    _logger.warning(
                        "Transformation rule '%s' failed for employee %s: %s",
                        rule.name, emp_ext_id, str(e)
                    )
                    computed[rule.output_key] = rule.default_value

            # Write computed_data to the main record (salary or employee type)
            # Find the best target record to write computed_data to
            target_records = emp_data['all_records'].get('salary', []) or \
                             emp_data['all_records'].get('employee', []) or \
                             [main_rec]
            for target in target_records:
                existing_computed = dict(target.computed_data or {})
                existing_computed.update(computed)
                target.computed_data = existing_computed

    def _execute_single(self, all_records_by_type, main_record):
        """
        Execute a single transformation rule.

        Args:
            all_records_by_type: dict of {data_type: [hr.api.data.store records]}
            main_record: the primary data store record for context

        Returns:
            The computed value (float, int, bool as 0/1)
        """
        # Get source records for this rule's data type
        source_records_orm = all_records_by_type.get(self.source_data_type, [])
        source_records = [r.extracted_data or {} for r in source_records_orm]

        # Apply filter if specified
        if self.filter_expression:
            filtered = []
            for rec_data in source_records:
                try:
                    match = safe_eval(self.filter_expression, {
                        'rec': rec_data,
                        'env': self.env,
                        'datetime': datetime,
                        'date': date,
                    })
                    if match:
                        filtered.append(rec_data)
                except Exception:
                    pass  # Skip records that fail filter evaluation
            source_records = filtered

        # Execute based on rule type
        if self.rule_type == 'count':
            return len(source_records)

        elif self.rule_type in ('sum', 'avg', 'min', 'max'):
            return self._execute_aggregate(source_records)

        elif self.rule_type == 'date_diff':
            return self._execute_date_diff(source_records, main_record)

        elif self.rule_type == 'date_check':
            return self._execute_date_check(source_records, main_record)

        elif self.rule_type == 'python':
            return self._execute_python(source_records, all_records_by_type, main_record)

        return self.default_value

    def _execute_aggregate(self, source_records):
        """Execute aggregate rules: sum, avg, min, max."""
        if not source_records or not self.aggregate_field:
            return self.default_value

        values = []
        for rec_data in source_records:
            val = rec_data.get(self.aggregate_field)
            if val is not None:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    continue

        if not values:
            return self.default_value

        if self.rule_type == 'sum':
            return sum(values)
        elif self.rule_type == 'avg':
            return sum(values) / len(values)
        elif self.rule_type == 'min':
            return min(values)
        elif self.rule_type == 'max':
            return max(values)

        return self.default_value

    def _execute_date_diff(self, source_records, main_record):
        """
        Calculate date difference.
        Reads date field from the first matching source record.
        """
        if not source_records or not self.date_source_field:
            return self.default_value

        # Get the date value from the first source record
        date_str = source_records[0].get(self.date_source_field)
        if not date_str:
            return self.default_value

        try:
            source_date = self._parse_date(date_str)
        except (ValueError, TypeError):
            return self.default_value

        compare_date = self._get_compare_date(main_record)
        if not compare_date:
            return self.default_value

        # Calculate difference
        if self.date_unit == 'days':
            return (compare_date - source_date).days
        elif self.date_unit == 'months':
            rd = relativedelta(compare_date, source_date)
            return rd.years * 12 + rd.months
        elif self.date_unit == 'years':
            rd = relativedelta(compare_date, source_date)
            return rd.years

        return self.default_value

    def _execute_date_check(self, source_records, main_record):
        """
        Check a date condition. Returns 1 (true) or 0 (false).
        """
        if not source_records or not self.date_source_field:
            return self.default_value

        date_str = source_records[0].get(self.date_source_field)
        if not date_str:
            return self.default_value

        try:
            source_date = self._parse_date(date_str)
        except (ValueError, TypeError):
            return self.default_value

        compare_date = self._get_compare_date(main_record)
        if not compare_date:
            return self.default_value

        if self.date_check_operator == 'before':
            return 1 if source_date < compare_date else 0
        elif self.date_check_operator == 'after':
            return 1 if source_date > compare_date else 0
        elif self.date_check_operator == 'within':
            n_months = self.date_check_value or 0
            cutoff = compare_date - relativedelta(months=n_months)
            return 1 if source_date >= cutoff else 0

        return self.default_value

    def _execute_python(self, source_records, all_records_by_type, main_record):
        """Execute a Python expression transformation rule."""
        if not self.python_code:
            return self.default_value

        # Build all_records dict (data_type -> list of extracted_data dicts)
        all_records_data = {}
        for dtype, recs in all_records_by_type.items():
            all_records_data[dtype] = [r.extracted_data or {} for r in recs]

        # Employee data from employee-type records
        employee_recs = all_records_by_type.get('employee', [])
        employee_data = employee_recs[0].extracted_data if employee_recs else {}

        local_vars = {
            'records': source_records,
            'employee_data': employee_data or {},
            'all_records': all_records_data,
            'period_start': main_record.period_from or date.today().replace(day=1),
            'period_end': main_record.period_to or date.today(),
            'env': self.env,
            'employee': main_record.employee_id or self.env['hr.employee'],
            'datetime': datetime,
            'date': date,
            'relativedelta': relativedelta,
            'result': self.default_value,
        }

        safe_eval(self.python_code, local_vars, mode='exec', nocopy=True)

        return local_vars.get('result', self.default_value)

    # ==========================================
    # HELPERS
    # ==========================================
    def _get_compare_date(self, main_record):
        """Get the comparison date based on rule configuration."""
        if self.date_compare_to == 'period_start':
            return main_record.period_from or date.today().replace(day=1)
        elif self.date_compare_to == 'period_end':
            return main_record.period_to or date.today()
        elif self.date_compare_to == 'today':
            return date.today()
        elif self.date_compare_to == 'fixed':
            return self.date_fixed_value or date.today()
        return date.today()

    @staticmethod
    def _parse_date(date_value):
        """Parse a date from various formats."""
        if isinstance(date_value, date):
            return date_value
        if isinstance(date_value, datetime):
            return date_value.date()

        date_str = str(date_value).strip()

        # Try common formats
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y',
                    '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f',
                    '%Y-%m-%d %H:%M:%S'):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        raise ValueError(f"Cannot parse date: {date_value}")
