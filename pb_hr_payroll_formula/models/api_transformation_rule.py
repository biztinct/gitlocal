# -*- coding: utf-8 -*-

import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.sql import table_exists

from .api_data_store import DATA_TYPES
from .integration_endpoint import CONNECTOR_TYPES

_logger = logging.getLogger(__name__)

# Declared once and shared with `hr.api.transformation.rule.template` below.
# A template that could express a rule type the engine cannot execute — or that
# lost one the engine grew — is a vendor catalogue that ships rules nobody can
# run, and nothing would error until a pull tried it (the same argument C1 made
# for `DATA_TYPES`, which `source_data_type` now also borrows rather than
# retyping: the two lists were already identical, character for character).
RULE_TYPES = [
    ('count', 'Count Records'),
    ('sum', 'Sum Field Across Records'),
    ('avg', 'Average Field Across Records'),
    ('min', 'Minimum Field Across Records'),
    ('max', 'Maximum Field Across Records'),
    ('date_diff', 'Date Difference Calculation'),
    ('date_check', 'Date Condition Check'),
    ('python', 'Python Expression (Advanced)'),
]

DATE_COMPARE_TO = [
    ('period_start', 'Period Start Date'),
    ('period_end', 'Period End Date'),
    ('today', 'Today'),
    ('fixed', 'Fixed Date'),
]

DATE_UNITS = [('days', 'Days'), ('months', 'Months'), ('years', 'Years')]

DATE_CHECK_OPERATORS = [
    ('before', 'Is Before'),
    ('after', 'Is After'),
    ('within', 'Is Within N months'),
]


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
    rule_type = fields.Selection(
        RULE_TYPES, string='Rule Type', required=True, default='count')

    # ==========================================
    # SOURCE: Which stored records to operate on
    # ==========================================
    source_data_type = fields.Selection(
        DATA_TYPES, string='Source Data Type', required=True,
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
    date_compare_to = fields.Selection(
        DATE_COMPARE_TO, string='Compare To', default='period_end')
    date_fixed_value = fields.Date(string='Fixed Date')
    date_unit = fields.Selection(
        DATE_UNITS, string='Result Unit', default='months',
        help="For date_diff: return difference in days, months, or years.",
    )
    date_check_operator = fields.Selection(
        DATE_CHECK_OPERATORS, string='Check Operator')
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
    # OPEN FORM (for inline list views)
    # ==========================================
    def action_open_form(self):
        """Open this record in a popup form dialog."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': self.env.context,
        }

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

        # Odoo 19 REMOVED `nocopy`. The signature is now
        # `safe_eval(expr, /, context=None, *, mode="eval", filename=None)`, and
        # its docstring makes the old opt-in the only behaviour: "This dict will
        # be mutated with any variables created during evaluation". Passing
        # `nocopy=True` is therefore a TypeError — raised before the expression
        # runs, on EVERY python rule, since the port.
        #
        # It never surfaced, and that is the interesting half. `_execute_for_records`
        # wraps each rule in `except Exception` and writes `default_value`
        # instead (:243), so a python rule did not fail loudly — it quietly
        # returned 0 and the payroll used the 0. The only trace was one WARNING
        # per employee per rule in a log nobody reads during a pull.
        #
        # Found by Integrations Cycle 3, which ships the first python rules this
        # codebase has had: DEPCOUNT and WORKEDHRS both answered 0.0 against
        # payloads whose right answers were 2 and 10.5.
        safe_eval(self.python_code, local_vars, mode='exec')

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


class HrApiTransformationRuleTemplate(models.Model):
    """The vendor catalogue a connector's transformation rules come from.

    Integrations Cycle 3. `hr.integration.endpoint.template` did this for feeds
    and `hr.integration.mapping.template` does it for field maps; the third leg
    of the legacy ABM inventory is its AGGREGATIONS — six overtime bands, a
    dependent count and a worked-hours conversion, all of which lived as inline
    arithmetic in `om_hr_payroll/models/hr_zoho_staging.py` and none of which
    survived being read by anybody but its author.

    Shaped exactly like the endpoint template: a row belongs to a VENDOR, not to
    a connector, and instantiation is CREATE-ONLY by `output_key` so an operator
    who has retuned a rule keeps their version through every later apply.

    The python rows are data-shipped and are the reason this model carries
    `python_code` at all. They are not editable from any cockpit — the same rule
    the mapping canvas obeys for `python` transforms (W12): a python expression
    arrives through a reviewed data file or it does not arrive.
    """

    _name = 'hr.api.transformation.rule.template'
    _description = 'API Transformation Rule Template'
    _order = 'connector_type, sequence, id'

    # The connector's own seven types, borrowed from the endpoint template so a
    # rule can be written for any vendor a connector can BE — including `demo`,
    # which is the one every test and every trial database has.
    connector_type = fields.Selection(CONNECTOR_TYPES, required=True, index=True)

    name = fields.Char(required=True, help="Human name, e.g. 'Overtime 150%'.")
    output_key = fields.Char(
        required=True,
        help="Key written to computed_data, and therefore the source path a "
             "field mapping reads. Unique per vendor — instantiation matches "
             "on it.")
    description = fields.Text()

    rule_type = fields.Selection(RULE_TYPES, required=True, default='count')
    source_data_type = fields.Selection(DATA_TYPES, required=True)

    aggregate_field = fields.Char()
    filter_expression = fields.Char(
        help="Python expression evaluated per record. The namespace is `rec` "
             "(the extracted_data dict), `env`, `datetime` and `date` — see "
             "`_execute_single`. NOT `record`.")

    date_source_field = fields.Char()
    date_compare_to = fields.Selection(DATE_COMPARE_TO, default='period_end')
    date_fixed_value = fields.Date()
    date_unit = fields.Selection(DATE_UNITS, default='months')
    date_check_operator = fields.Selection(DATE_CHECK_OPERATORS)
    date_check_value = fields.Integer()

    python_code = fields.Text()

    default_value = fields.Float(default=0.0)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    is_legacy_abm = fields.Boolean(
        help="Used by the legacy ABM application.")

    _type_key_uniq = models.Constraint(
        'unique(connector_type, output_key)',
        'That vendor already has a transformation-rule template with this '
        'output key.',
    )

    # The fields an instantiated rule copies verbatim. Named rather than
    # derived from `_fields`, because the two models are deliberately NOT the
    # same shape: the template has `connector_type` and `is_legacy_abm`, which
    # the rule has no column for, and the rule has `connector_id`, which is the
    # thing instantiation supplies.
    _COPIED = (
        'name', 'output_key', 'description', 'rule_type', 'source_data_type',
        'aggregate_field', 'filter_expression', 'date_source_field',
        'date_compare_to', 'date_fixed_value', 'date_unit',
        'date_check_operator', 'date_check_value', 'python_code',
        'default_value', 'sequence',
    )

    @api.model
    def _schema_ready(self):
        """Does THIS database actually have the rule-template table?

        C1's degrade rail, applied to the third catalogue. The addons tree is
        SHARED by every database on this box and a schema is created by an
        UPGRADE, per database — so between the rsync of this model and the `-u`
        of database N, database N loads code describing a table it has not got,
        while `'hr.api.transformation.rule.template' in self.env` answers True
        the whole time (the model class comes from the python, not the schema).

        Unguarded, the first `search` raises `UndefinedTable` and leaves the
        request's transaction ABORTED, so everything after it fails too. This
        one is reached from `action_apply_mapping_template`, which the
        onboarding wizard and the connector form both call.
        """
        if table_exists(self.env.cr, self._table):
            return True
        if not self.env.registry.__dict__.get('_pb_ruletmpl_schema_warned'):
            self.env.registry.__dict__['_pb_ruletmpl_schema_warned'] = True
            _logger.warning(
                "Database %s loads the transformation-rule catalogue but has "
                "no %s table: this database has not been upgraded since the "
                "model was added. Vendor rules are skipped until "
                "`-u pb_hr_payroll_formula` runs here; mapping templates and "
                "every other apply step are unaffected.",
                self.env.cr.dbname, self._table)
        return False

    def _rule_vals(self, connector):
        """This template as `hr.api.transformation.rule` values.

        Every copied field has the same type on both models — that is what
        `_COPIED` is asserting — so the values come across untouched, unset
        included (an unset Char reads False on both sides, and writing False is
        how the ORM spells "empty" for both).
        """
        self.ensure_one()
        vals = {'connector_id': connector.id}
        for name in self._COPIED:
            vals[name] = self[name]
        return vals
