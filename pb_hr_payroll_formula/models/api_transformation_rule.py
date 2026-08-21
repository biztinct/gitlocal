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
from ..formula_engine import rule_formula
from ..formula_engine.excel_semantics import coerce_number

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

# ===========================================================================
# Integrations Cycle 8 — the Rule Composer's vocabulary
# ===========================================================================
#
# A transformation rule is a SENTENCE: take some records, keep some, derive one
# number, name it. Everything below is the closed vocabulary that sentence is
# built from, and it is closed on purpose — a guided rule generates NO code, so
# there is nothing here a browser could widen into an expression.
#
# `builder_mode` names which lane a rule is written in:
#
#   guided  the four step-cards. Conditions and value steps are evaluated
#           NATIVELY on plain dicts — zero safe_eval on this path.
#   excel   the same steps, but the per-record value comes from an Excel
#           formula over `excel_semantics` (formula_engine/rule_formula.py).
#   python  the lane that was here before: the declarative `rule_type` fields
#           AND `python_code`. It is the administrator's escape hatch, it is
#           edited in the backend form, and no RPC in this codebase may write
#           it (W12). Existing rows default to it, so nothing changes meaning
#           the day this field arrives.
BUILDER_MODES = [
    ('guided', 'Guided steps'),
    ('excel', 'Excel formula'),
    ('python', 'Advanced (backend form)'),
]

RECORD_SOURCES = [
    ('records', 'Each record from the feed'),
    ('nested', 'Rows inside a table on each record'),
]

# The comparison vocabulary. Deliberately small: these nine cover every filter
# the legacy ABM application expressed in python, and each of them can be read
# aloud in the sentence the composer prints.
CONDITION_OPERATORS = [
    ('is', 'is'),
    ('is_not', 'is not'),
    ('contains', 'contains'),
    ('present', 'is present'),
    ('blank', 'is blank'),
    ('gt', 'is more than'),
    ('gte', 'is at least'),
    ('lt', 'is less than'),
    ('lte', 'is at most'),
]
CONDITION_OPS = {code for code, _label in CONDITION_OPERATORS}
# The two that ask about the field rather than about a value, so the composer
# hides the value box and the validator does not demand one.
UNARY_OPS = {'present', 'blank'}

# What a field CONTAINS, which is the question a novice can answer and the unit
# conversion is the answer's consequence. Every entry converts into HOURS
# except `number` and `days`, which are already the unit the rule reports in.
VALUE_UNITS = [
    ('number', 'a number'),
    ('seconds', 'a number of seconds'),
    ('hmm', 'hours and minutes, like 7:30'),
    ('minutes', 'a number of minutes'),
    ('days', 'a number of days'),
]
VALUE_UNIT_CODES = {code for code, _label in VALUE_UNITS}

# The aggregates a guided rule may use. `date_diff`/`date_check` are already
# declarative and stay field-driven; `python` is not a guided shape at all.
GUIDED_RULE_TYPES = ('count', 'sum', 'avg', 'min', 'max')


def _unit_value(raw, unit):
    """One field value, in the rule's own unit — or None when it is not a value.

    None is not zero, and the difference is the whole reason this returns it:
    a row whose field is missing or malformed must be SKIPPED by the aggregate,
    exactly as `_execute_aggregate` skips a `float()` that raises. Turning it
    into a 0 would drag an average down and make a min wrong.

    The `hmm` parse is `isdigit`-guarded on both halves rather than wrapped in
    try/except, because that is precisely what the legacy WORKEDHRS did: a
    malformed value contributes nothing and the rest of the day still counts.
    """
    if raw is None or raw is False:
        return None
    if isinstance(raw, bool):
        return 1.0 if raw else 0.0
    if unit == 'hmm':
        parts = str(raw).strip().split(':')
        if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
            return int(parts[0].strip()) + int(parts[1].strip()) / 60.0
        # Not "H:MM" at all — a bare number in a field declared as H:MM is
        # read as hours rather than refused, which is what a human means when
        # they type 8 into a box labelled hours and minutes.
        number = coerce_number(raw)
        return float(number) if number is not None else None
    number = coerce_number(raw)
    if number is None:
        return None
    if unit == 'seconds':
        return number / 3600.0
    if unit == 'minutes':
        return number / 60.0
    return float(number)


def _text(value):
    """A payload value as comparable text. `False` is the ORM's empty, and an
    unset JSON key is `None`; both read as blank rather than as the words."""
    if value is None or value is False:
        return ''
    if value is True:
        return 'true'
    return str(value).strip()


def _condition_matches(row, condition):
    """One KEEP row against one record. Never raises — a condition that cannot
    be evaluated simply does not match, which is the leniency the legacy
    `except Exception: pass` filter had and the one payroll depends on.

    Comparison follows Excel and the excel lane: if BOTH sides read as numbers
    they are compared as numbers ("8" equals 8.0), otherwise as trimmed,
    case-insensitive text. The two lanes agreeing about equality is not a
    nicety — the same rule is meant to give the same answer in either.
    """
    try:
        field = (condition or {}).get('field') or ''
        op = (condition or {}).get('op') or 'is'
        if op not in CONDITION_OPS:
            return False
        raw, _found = rule_formula.resolve_ref(row, field)
        if op == 'present':
            return _text(raw) != ''
        if op == 'blank':
            return _text(raw) == ''
        wanted = condition.get('value')
        left, right = _text(raw), _text(wanted)
        if op == 'contains':
            return right.casefold() in left.casefold()
        left_n, right_n = coerce_number(raw), coerce_number(wanted)
        numeric = left_n is not None and right_n is not None
        if op == 'is':
            return left_n == right_n if numeric else left.casefold() == right.casefold()
        if op == 'is_not':
            return left_n != right_n if numeric else left.casefold() != right.casefold()
        if not numeric:
            # "more than" over text is not a question with an answer, and
            # answering it alphabetically is how "9 > 10" becomes True.
            return False
        if op == 'gt':
            return left_n > right_n
        if op == 'gte':
            return left_n >= right_n
        if op == 'lt':
            return left_n < right_n
        return left_n <= right_n
    except Exception:       # noqa: BLE001 — see the docstring: a row, not a crash
        return False


_AGG_VERB = {
    'sum': 'Adds up', 'avg': 'Averages',
    'min': 'Takes the smallest', 'max': 'Takes the largest',
}
_UNIT_LABEL = dict(VALUE_UNITS)
_OP_LABEL = dict(CONDITION_OPERATORS)
_DATA_TYPE_LABEL = dict(DATA_TYPES)


def _spoken_conditions(spec):
    """The KEEP step as half a sentence, or '' when nothing is filtered."""
    rows = (spec or {}).get('rows') or []
    if not rows:
        return ''
    joiner = ' or ' if (spec.get('join') or 'all') == 'any' else ' and '
    parts = []
    for row in rows:
        field = row.get('field') or ''
        label = _OP_LABEL.get(row.get('op') or 'is', row.get('op') or 'is')
        if (row.get('op') or 'is') in UNARY_OPS:
            parts.append('%s %s' % (field, label))
        else:
            parts.append('%s %s %s' % (field, label, row.get('value')))
    return ' where ' + joiner.join(parts)


def plain_summary_for(rule):
    """The rule as one plain sentence, generated from the spec.

    This is what the ledger prints in place of "Python Expression (Advanced)",
    and it is a COMPUTED field rather than a stored description because a
    sentence that can disagree with the rule it describes is worse than no
    sentence. Product voice throughout: it names the feed, the fields and the
    arithmetic, and it never names the platform.

    Takes anything with the rule's attributes — the rule, the template, or an
    in-memory draft — so the composer's preview and the saved row are described
    by the same function.
    """
    mode = getattr(rule, 'builder_mode', None) or 'python'
    if mode == 'python':
        if getattr(rule, 'python_code', None):
            return 'Advanced rule (Python), maintained by your administrator'
        # A pre-composer declarative rule: still readable, still honest.
        kind = dict(RULE_TYPES).get(rule.rule_type, rule.rule_type or '')
        source = _DATA_TYPE_LABEL.get(rule.source_data_type, rule.source_data_type or '')
        return ('%s over %s records, set up in the backend form'
                % (kind, source)) if kind else 'Advanced rule'

    source = _DATA_TYPE_LABEL.get(rule.source_data_type, rule.source_data_type or 'source')
    nested = (getattr(rule, 'record_source', 'records') == 'nested')
    subject = ('rows in %s on each %s record'
               % (getattr(rule, 'nested_table_path', '') or 'the table', source)
               ) if nested else '%s records' % source
    where = _spoken_conditions(getattr(rule, 'filter_conditions', None))

    if rule.rule_type == 'count':
        return 'Counts %s%s' % (subject, where)

    if mode == 'excel':
        return ('%s the result of %s for each of the %s%s'
                % (_AGG_VERB.get(rule.rule_type, 'Combines'),
                   getattr(rule, 'excel_formula', '') or 'the formula',
                   subject, where))

    steps = getattr(rule, 'value_steps', None) or []
    names = [s.get('field') or '' for s in steps if s.get('field')]
    if not names:
        return 'Reads %s%s' % (subject, where)
    joined = names[0] if len(names) == 1 else (
        ' plus '.join(names[:-1]) + ' plus ' + names[-1])
    verb = _AGG_VERB.get(rule.rule_type, 'Combines')
    if rule.rule_type == 'date_diff':
        verb = 'Measures the time to'
    return '%s %s over %s%s' % (verb, joined, subject, where)


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
             "Available: `rec` (the extracted_data dict), `env` (the server "
             "environment). "
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
             "  `env` — the server environment\n"
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
    # THE COMPOSER (Integrations Cycle 8)
    # ==========================================
    builder_mode = fields.Selection(
        BUILDER_MODES, string='Written as', required=True, default='python',
        help="How this rule is written. Guided steps and Excel formulas are "
             "edited in the Rule Composer; the advanced lane is edited here, "
             "in this form, and only by an administrator.",
    )
    record_source = fields.Selection(
        RECORD_SOURCES, string='Take', required=True, default='records',
        help="Whether the rule works through the feed's records, or through "
             "the rows of a table carried INSIDE each record.",
    )
    nested_table_path = fields.Char(
        string='Table inside the record',
        help="Where the rows live on each record, e.g. "
             "tabularSections.Dependent and Dependent Health Insurance.",
    )
    filter_conditions = fields.Json(
        string='Keep',
        help="The KEEP step, as data rather than as code: "
             "{'join': 'all'|'any', 'rows': [{'field', 'op', 'value'}]}.",
    )
    value_steps = fields.Json(
        string='Derive',
        help="The DERIVE step: [{'field', 'contains'}]. Steps inside ONE "
             "record are added together; the rule's own kind (sum, average, "
             "smallest, largest) then applies across the records.",
    )
    excel_formula = fields.Char(
        string='Excel formula',
        help="The Excel lane's per-record value, with field names in square "
             "brackets: [totalWorkedHours]/3600 + HOURS([paidLeaveHours]).",
    )
    plain_summary = fields.Char(
        string='In plain words', compute='_compute_plain_summary', store=True,
        help="What this rule does, said in one sentence.",
    )

    # ---- the silent-failure gap, closed -------------------------------
    # Every failure used to be a log WARNING and a silent `default_value`
    # (:241-246 before this cycle). A payroll that used the 0 had no way to
    # know, and the only trace was one line per employee per rule in a log
    # nobody reads during a pull — which is exactly how the `nocopy` breakage
    # survived four cycles (W137). These two fields are that trace, on the
    # record, where the person who owns the rule can see it.
    last_error = fields.Char(
        string='Last error', readonly=True,
        help="What went wrong the last time this rule ran. Cleared "
             "automatically as soon as it succeeds again.",
    )
    last_error_at = fields.Datetime(string='Last error at', readonly=True)

    @api.depends('builder_mode', 'rule_type', 'source_data_type', 'record_source',
                 'nested_table_path', 'filter_conditions', 'value_steps',
                 'excel_formula', 'python_code')
    def _compute_plain_summary(self):
        for rule in self:
            rule.plain_summary = plain_summary_for(rule)

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
                    rule._clear_error()
                except Exception as e:
                    _logger.warning(
                        "Transformation rule '%s' failed for employee %s: %s",
                        rule.name, emp_ext_id, str(e)
                    )
                    computed[rule.output_key] = rule.default_value
                    rule._flag_error(e, emp_ext_id)

            # Write computed_data to the main record (salary or employee type)
            # Find the best target record to write computed_data to
            target_records = emp_data['all_records'].get('salary', []) or \
                             emp_data['all_records'].get('employee', []) or \
                             [main_rec]
            for target in target_records:
                existing_computed = dict(target.computed_data or {})
                existing_computed.update(computed)
                target.computed_data = existing_computed

    # ---- the failure that used to be invisible -------------------------
    def _flag_error(self, error, employee_ref=''):
        """Record WHY this rule fell back to its default.

        Written only when the message CHANGES: `_execute_for_records` runs
        every rule once per employee, and a broken rule on a four-thousand-row
        pull would otherwise be four thousand writes of the same sentence.

        Sanitised (W40): the type and the message, capped. A rule's failure is
        a configuration fact its owner needs, so it is not replaced by "see the
        log" the way an unexpected preview failure is — but it is not a
        traceback either.
        """
        self.ensure_one()
        if not self.id:                     # an in-memory draft never writes
            return
        message = ('%s: %s' % (type(error).__name__, error))[:500] \
            if str(error) else type(error).__name__
        if employee_ref:
            message = ('%s (while reading %s)' % (message, employee_ref))[:500]
        if self.last_error == message:
            return
        self.sudo().write({'last_error': message,
                           'last_error_at': fields.Datetime.now()})

    def _clear_error(self):
        """A success clears the flag — a stale error badge is a lie with a
        timestamp on it. Guarded so a healthy rule writes nothing at all."""
        self.ensure_one()
        if not self.id or not self.last_error:
            return
        self.sudo().write({'last_error': False, 'last_error_at': False})

    def _execute_single(self, all_records_by_type, main_record):
        """
        Execute a single transformation rule.

        Args:
            all_records_by_type: dict of {data_type: [hr.api.data.store records]}
            main_record: the primary data store record for context

        Returns:
            The computed value (float, int, bool as 0/1)
        """
        # THE COMPOSER LANES (Cycle 8). A guided or excel rule never reaches
        # `safe_eval` at all: its conditions are evaluated natively on plain
        # dicts and its value comes from either a unit conversion or the
        # hardened excel converter. `python` is the lane everything was in
        # before, unchanged below.
        if self.builder_mode in ('guided', 'excel'):
            return self._execute_builder(all_records_by_type, main_record)

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

    # ==========================================
    # THE GUIDED / EXCEL ENGINE (Integrations Cycle 8)
    # ==========================================
    #
    # THREE PRIMITIVES, ONE PATH. `_builder_expand` turns store rows into the
    # rows the sentence talks about; `_builder_run` is the sentence. Execution
    # calls them with no trace; the composer's preview calls THE SAME TWO with
    # a dict, and the dict is filled in as the loops go. There is no second
    # implementation to drift — which is the law `preview_transform` states in
    # its own docstring and the reason this cycle could not simply write a
    # "simulator".
    #
    # PROVEN, not asserted: `test_rule_composer.py` runs both entry points over
    # identical specs and records and compares the numbers.

    def _builder_expand(self, record_dicts):
        """The TAKE step: which rows this rule is actually about.

        `records` — one row per stored record, the ordinary case.
        `nested`  — the rows of a table carried inside each record. Zoho
                    returns dependants that way (one employee record holding a
                    `tabularSections` list), which is why counting RECORDS
                    answered 1 for an employee with four dependants and made
                    DEPCOUNT a python rule in the first place.
        """
        if self.record_source != 'nested':
            return list(record_dicts or [])
        path = (self.nested_table_path or '').strip()
        rows = []
        for record in (record_dicts or []):
            for row in self._nested_rows(record, path):
                rows.append(row)
        return rows

    @staticmethod
    def _nested_rows(record, path):
        """Walk `path` into one record and return the list it names.

        The whole path is tried as a single KEY first: a Zoho tabular section
        is called "Dependent and Dependent Health Insurance", and one day a
        vendor will ship a section whose name contains a dot. Only then is the
        path split, which is the ordinary `a.b.c` case.
        """
        if not isinstance(record, dict) or not path:
            return []
        node = record
        if path in node:
            node = node[path]
        else:
            for part in path.split('.'):
                if not isinstance(node, dict):
                    return []
                value, found = rule_formula.resolve_ref(node, part)
                if not found:
                    return []
                node = value
        if isinstance(node, dict):
            # A table keyed by id rather than listed — its VALUES are the rows.
            node = list(node.values())
        return [r for r in node if isinstance(r, dict)] if isinstance(node, list) else []

    def _row_matches(self, row):
        """The KEEP step. No conditions means keep everything, which is the
        honest reading of an empty filter and matches the legacy behaviour of
        an empty `filter_expression`."""
        spec = self.filter_conditions or {}
        conditions = spec.get('rows') or []
        if not conditions:
            return True
        results = [_condition_matches(row, c) for c in conditions]
        return any(results) if (spec.get('join') or 'all') == 'any' else all(results)

    def _row_value(self, row, compiled=None):
        """The DERIVE step for ONE row — or None when the row has no value.

        Guided: every step is read and converted into the rule's unit, and the
        steps are ADDED. WORKEDHRS is the reason: its two halves arrive in one
        payload as an integer count of seconds and an "H:MM" string, and no
        single-field aggregate can add those.

        Excel: the compiled formula, evaluated against this row.

        None means "this row has nothing to contribute" and the aggregate skips
        it — exactly as `_execute_aggregate` skips a value `float()` refuses.
        Returning 0 instead would drag an average down and break a minimum.
        """
        if self.builder_mode == 'excel':
            if compiled is None:
                compiled = self._compiled_formula()
            code, refs = compiled
            return rule_formula.eval_rule_formula(code, refs, row)
        total = None
        for step in (self.value_steps or []):
            field = (step or {}).get('field') or ''
            unit = (step or {}).get('contains') or 'number'
            if unit not in VALUE_UNIT_CODES:
                unit = 'number'
            raw, _found = rule_formula.resolve_ref(row, field)
            value = _unit_value(raw, unit)
            if value is None:
                continue
            total = value if total is None else total + value
        return total

    def _compiled_formula(self):
        """This rule's Excel formula, compiled. Raises `RuleFormulaError`,
        which `_execute_for_records` turns into `last_error` — a formula that
        stopped compiling is exactly the invisible breakage this cycle set out
        to make visible."""
        return rule_formula.compile_rule_formula(self.excel_formula)

    def _builder_run(self, rows, main_record=None, trace=None):
        """The sentence, over the rows the TAKE step produced.

        `trace` is an OPTIONAL dict. When it is given, the same loops that
        compute the answer also record what they saw — how many rows arrived,
        which ones matched, what each contributed. That is the whole of the
        composer's proof rail, and it is a decoration on this function rather
        than a copy of it.
        """
        if trace is not None:
            trace['records_in'] = len(rows)
            trace['rows'] = []

        compiled = self._compiled_formula() if self.builder_mode == 'excel' else None

        matched, values = [], []
        for index, row in enumerate(rows):
            keep = self._row_matches(row)
            value = None
            if keep:
                matched.append(row)
                if self.rule_type in ('sum', 'avg', 'min', 'max'):
                    value = self._row_value(row, compiled)
                    if value is not None:
                        values.append(value)
            if trace is not None and index < 60:
                trace['rows'].append({
                    'i': index, 'kept': keep,
                    'value': value if value is not None else None,
                    'cells': self._trace_cells(row),
                })
        if trace is not None:
            trace['matched'] = len(matched)
            trace['valued'] = len(values)

        if self.rule_type == 'count':
            result = float(len(matched))
        elif self.rule_type in ('sum', 'avg', 'min', 'max'):
            if not values:
                result = self.default_value
            elif self.rule_type == 'sum':
                result = sum(values)
            elif self.rule_type == 'avg':
                result = sum(values) / len(values)
            elif self.rule_type == 'min':
                result = min(values)
            else:
                result = max(values)
        elif self.rule_type == 'date_diff':
            result = self._execute_date_diff(matched, main_record)
        elif self.rule_type == 'date_check':
            result = self._execute_date_check(matched, main_record)
        else:
            # `python` cannot be reached from here (`_execute_single` routes it
            # away) and an unknown kind is a data defect, not a value.
            result = self.default_value
        if trace is not None:
            trace['result'] = result
        return result

    def _trace_cells(self, row):
        """The handful of fields this rule actually mentions, for the proof
        rail. A record can be a hundred keys wide and the rail is a column —
        showing everything would bury the two the reader is checking."""
        names = []
        for condition in ((self.filter_conditions or {}).get('rows') or []):
            if condition.get('field'):
                names.append(condition['field'])
        for step in (self.value_steps or []):
            if step.get('field'):
                names.append(step['field'])
        if self.builder_mode == 'excel' and self.excel_formula:
            try:
                names.extend(rule_formula.compile_rule_formula(self.excel_formula)[1])
            except Exception:       # noqa: BLE001 — the rail still shows rows
                pass
        cells, seen = [], set()
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            raw, _found = rule_formula.resolve_ref(row, name)
            text = _text(raw)
            cells.append({'k': name, 'v': text if len(text) <= 60 else text[:57] + '…'})
            if len(cells) >= 4:
                break
        return cells

    def _execute_builder(self, all_records_by_type, main_record, trace=None):
        """The guided/excel lane's entry point from the execution engine."""
        source_records_orm = all_records_by_type.get(self.source_data_type, [])
        record_dicts = [r.extracted_data or {} for r in source_records_orm]
        return self._builder_run(
            self._builder_expand(record_dicts), main_record, trace)

    def preview_on_records(self, record_dicts, main_record=None):
        """The traced twin, for the composer. SAME two primitives as execution.

        Returns `{result, records_in, matched, valued, rows: [...]}`. Nothing
        here writes: the caller hands it plain dicts and an (optionally
        in-memory) rule, and the proof rail is the trace.
        """
        self.ensure_one()
        trace = {}
        self._builder_run(self._builder_expand(record_dicts or []),
                          main_record, trace)
        return trace

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

    # Cycle 8 — the composer's spec, mirrored so a vendor row can ship as a
    # SENTENCE rather than as a python program. Same names, same types, same
    # meaning as the rule's; `_COPIED` carries every one of them across.
    builder_mode = fields.Selection(BUILDER_MODES, required=True, default='python')
    record_source = fields.Selection(RECORD_SOURCES, required=True, default='records')
    nested_table_path = fields.Char()
    filter_conditions = fields.Json()
    value_steps = fields.Json()
    excel_formula = fields.Char()
    plain_summary = fields.Char(compute='_compute_plain_summary', store=True)

    default_value = fields.Float(default=0.0)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    is_legacy_abm = fields.Boolean(
        help="Used by the legacy ABM application.")

    @api.depends('builder_mode', 'rule_type', 'source_data_type', 'record_source',
                 'nested_table_path', 'filter_conditions', 'value_steps',
                 'excel_formula', 'python_code')
    def _compute_plain_summary(self):
        """The same generator the rule uses — one function, so a catalogue row
        and the rule instantiated from it can never describe themselves
        differently."""
        for template in self:
            template.plain_summary = plain_summary_for(template)

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
    #
    # Cycle 8 adds the six composer fields. Three of the rule's new columns are
    # deliberately NOT here and each for the same reason — they are not
    # attributes of a catalogue row:
    #   `plain_summary`            computed on both models from the fields
    #                              above, so copying it would be copying an
    #                              answer instead of the question;
    #   `last_error`/`last_error_at`  what happened on THIS database during
    #                              THIS pull. A vendor template has never run.
    _COPIED = (
        'name', 'output_key', 'description', 'rule_type', 'source_data_type',
        'aggregate_field', 'filter_expression', 'date_source_field',
        'date_compare_to', 'date_fixed_value', 'date_unit',
        'date_check_operator', 'date_check_value', 'python_code',
        'default_value', 'sequence',
        'builder_mode', 'record_source', 'nested_table_path',
        'filter_conditions', 'value_steps', 'excel_formula',
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
