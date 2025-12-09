# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class HrIntegrationFieldMapping(models.Model):
    """
    Integration Field Mapping - Maps fields from external HR systems
    to formula rule input columns.
    """
    _name = 'hr.integration.field.mapping'
    _description = 'Integration Field Mapping'
    _order = 'sequence, source_field'
    _rec_name = 'display_name'

    # ==========================================
    # LINKS
    # ==========================================
    connector_id = fields.Many2one(
        'hr.integration.connector',
        string='Connector',
        required=True,
        ondelete='cascade',
        index=True
    )

    connector_type = fields.Selection(
        related='connector_id.connector_type',
        store=True
    )

    # ==========================================
    # SOURCE FIELD
    # ==========================================
    source_field = fields.Char(
        string='Source Field Path',
        required=True,
        help="Field name or path in source system (e.g., 'base_salary', 'employee.department.name')"
    )

    source_field_label = fields.Char(
        string='Source Field Label',
        help="Human-readable name from source system"
    )

    source_data_type = fields.Selection([
        ('string', 'Text'),
        ('number', 'Number'),
        ('integer', 'Integer'),
        ('float', 'Decimal'),
        ('date', 'Date'),
        ('datetime', 'Date/Time'),
        ('boolean', 'Yes/No'),
        ('currency', 'Currency')
    ], string='Source Data Type', default='number')

    source_sample_value = fields.Char(
        string='Sample Value',
        help="Example value from source system"
    )

    # ==========================================
    # TARGET (Formula Rule)
    # ==========================================
    target_rule_id = fields.Many2one(
        'hr.formula.rule',
        string='Target Formula Rule',
        domain="[('column_type', '=', 'input')]",
        help="Formula rule to receive this value"
    )

    target_column_letter = fields.Char(
        related='target_rule_id.column_letter',
        string='Target Column',
        store=True
    )

    target_rule_code = fields.Char(
        related='target_rule_id.code',
        string='Target Code',
        store=True
    )

    # ==========================================
    # TRANSFORMATION
    # ==========================================
    transformation_type = fields.Selection([
        ('direct', 'Direct Copy'),
        ('multiply', 'Multiply by Factor'),
        ('divide', 'Divide by Factor'),
        ('add', 'Add Value'),
        ('subtract', 'Subtract Value'),
        ('round', 'Round to Decimals'),
        ('abs', 'Absolute Value'),
        ('default_if_empty', 'Use Default if Empty'),
        ('python', 'Python Expression')
    ], string='Transformation', default='direct')

    transformation_value = fields.Float(
        string='Factor/Value',
        default=1.0,
        help="Multiplication factor, divisor, or value to add/subtract"
    )

    transformation_decimals = fields.Integer(
        string='Decimal Places',
        default=2,
        help="For rounding transformation"
    )

    transformation_code = fields.Text(
        string='Python Expression',
        help="""
Python expression to transform the value.
Available variables:
- value: The source value
- record: The full source record (dict)
- env: Odoo environment

Example: value * 1.1 if value > 1000 else value
        """
    )

    # ==========================================
    # VALIDATION
    # ==========================================
    is_required = fields.Boolean(
        string='Required',
        default=False,
        help="Raise error if this field is missing in source data"
    )

    default_value = fields.Float(
        string='Default Value',
        default=0.0,
        help="Value to use when source field is empty"
    )

    min_value = fields.Float(
        string='Min Value',
        help="Minimum allowed value (leave empty for no limit)"
    )

    max_value = fields.Float(
        string='Max Value',
        help="Maximum allowed value (leave empty for no limit)"
    )

    # ==========================================
    # STATUS
    # ==========================================
    is_mapped = fields.Boolean(
        string='Is Mapped',
        compute='_compute_is_mapped',
        store=True
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    notes = fields.Text(
        string='Notes'
    )

    # ==========================================
    # DISPLAY
    # ==========================================
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    # ==========================================
    # COMPUTED
    # ==========================================
    @api.depends('source_field', 'source_field_label', 'target_rule_id')
    def _compute_display_name(self):
        for record in self:
            source = record.source_field_label or record.source_field
            target = record.target_rule_id.name if record.target_rule_id else 'Unmapped'
            record.display_name = f"{source} -> {target}"

    @api.depends('target_rule_id')
    def _compute_is_mapped(self):
        for record in self:
            record.is_mapped = bool(record.target_rule_id)

    # ==========================================
    # TRANSFORMATION METHODS
    # ==========================================
    def transform_value(self, value, record=None):
        """Apply transformation to a value"""
        self.ensure_one()

        # Handle None/empty values
        if value is None or value == '':
            if self.is_required:
                raise ValidationError(_(
                    "Required field '%s' is missing in source data"
                ) % self.source_field)
            return self.default_value

        # Convert to float if needed
        try:
            if self.source_data_type in ('number', 'float', 'integer', 'currency'):
                value = float(value)
        except (ValueError, TypeError):
            if self.is_required:
                raise ValidationError(_(
                    "Cannot convert value '%s' to number for field '%s'"
                ) % (value, self.source_field))
            return self.default_value

        # Apply transformation
        result = value

        if self.transformation_type == 'direct':
            result = value

        elif self.transformation_type == 'multiply':
            result = value * self.transformation_value

        elif self.transformation_type == 'divide':
            if self.transformation_value == 0:
                raise ValidationError(_("Division by zero in transformation"))
            result = value / self.transformation_value

        elif self.transformation_type == 'add':
            result = value + self.transformation_value

        elif self.transformation_type == 'subtract':
            result = value - self.transformation_value

        elif self.transformation_type == 'round':
            result = round(value, self.transformation_decimals)

        elif self.transformation_type == 'abs':
            result = abs(value)

        elif self.transformation_type == 'default_if_empty':
            result = value if value else self.transformation_value

        elif self.transformation_type == 'python':
            if self.transformation_code:
                try:
                    local_vars = {
                        'value': value,
                        'record': record or {},
                        'env': self.env,
                    }
                    result = eval(self.transformation_code, {"__builtins__": {}}, local_vars)
                except Exception as e:
                    _logger.error(f"Transformation error for {self.source_field}: {e}")
                    result = self.default_value

        # Apply min/max constraints
        if self.min_value is not None and result < self.min_value:
            result = self.min_value
        if self.max_value is not None and result > self.max_value:
            result = self.max_value

        return result

    def get_value_from_record(self, record):
        """Extract and transform value from a source record"""
        self.ensure_one()

        # Navigate nested path (e.g., "employee.department.name")
        value = record
        for key in self.source_field.split('.'):
            if isinstance(value, dict):
                value = value.get(key)
            elif hasattr(value, key):
                value = getattr(value, key)
            else:
                value = None
                break

        # Apply transformation
        return self.transform_value(value, record)

    # ==========================================
    # ACTIONS
    # ==========================================
    def action_test_mapping(self):
        """Test the mapping with sample data"""
        self.ensure_one()
        if not self.source_sample_value:
            raise UserError(_("Please provide a sample value to test"))

        try:
            result = self.transform_value(self.source_sample_value)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Mapping Test'),
                    'message': _("Input: %s -> Output: %s") % (
                        self.source_sample_value, result
                    ),
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Mapping Error'),
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def action_auto_map(self):
        """Try to auto-map based on field name similarity"""
        self.ensure_one()
        if self.target_rule_id:
            return  # Already mapped

        # Get all input rules from associated formula configs
        configs = self.env['hr.formula.config'].search([
            ('connector_id', '=', self.connector_id.id)
        ])

        if not configs:
            return

        input_rules = configs.mapped('rule_ids').filtered(
            lambda r: r.column_type == 'input'
        )

        # Try exact match
        source_lower = self.source_field.lower().replace('_', '').replace('-', '')
        for rule in input_rules:
            rule_lower = rule.code.lower().replace('_', '').replace('-', '')
            if source_lower == rule_lower or source_lower in rule_lower or rule_lower in source_lower:
                self.target_rule_id = rule
                break
