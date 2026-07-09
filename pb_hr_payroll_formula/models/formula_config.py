# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import json
import re
import logging

_logger = logging.getLogger(__name__)


class HrFormulaConfig(models.Model):
    """
    Excel Formula Configuration - Main configuration model linking
    payroll structures to formula-based salary rules.
    """
    _name = 'hr.formula.config'
    _description = 'Excel Formula Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    _rec_name = 'display_name'

    # ==========================================
    # BASIC FIELDS
    # ==========================================
    name = fields.Char(
        string='Configuration Name',
        required=True,
        tracking=True,
        help="A descriptive name for this formula configuration"
    )
    code = fields.Char(
        string='Reference Code',
        required=True,
        tracking=True,
        help="Unique code for this configuration (e.g., VN_STD_2024)"
    )
    description = fields.Html(
        string='Description',
        help="Detailed description of this configuration"
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Determines display order"
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    cycle_type = fields.Selection([
        ('regular', 'Regular'),
        ('mid_cycle', 'Mid-Cycle'),
        ('end_cycle', 'End-Cycle'),
        ('full_final', 'Full & Final'),
    ], string='Cycle Type', default='regular', tracking=True)
    use_proration = fields.Boolean(
        string='Enable Proration',
        help="Automatically prorate selected components when contract values change mid-period."
    )
    proration_basis = fields.Selection([
        ('calendar', 'Calendar Days'),
        ('workdays', 'Work Days'),
    ], string='Proration Basis', default='calendar')
    proration_component_ids = fields.Many2many(
        'hr.formula.rule',
        'formula_config_proration_rule_rel',
        'config_id',
        'rule_id',
        string='Prorated Components',
        domain="[('config_id', '=', id), ('column_type', 'in', ['input', 'constant'])]",
        help="Components to prorate based on contract change effective dates."
    )
    proration_rounding = fields.Integer(
        string='Proration Rounding',
        default=2,
        help="Number of decimal places to round prorated amounts."
    )
    use_auto_retro = fields.Boolean(
        string='Enable Auto Retro',
        help="Automatically calculate retro adjustments for backdated contract changes."
    )
    retro_component_id = fields.Many2one(
        'hr.formula.rule',
        string='Retro Target Component',
        domain="[('config_id', '=', id), ('column_type', '=', 'input')]",
        help="Component that will receive retro adjustment amounts."
    )

    # ==========================================
    # COUNTRY & STRUCTURE LINKING
    # ==========================================
    country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
        ('TH', 'Thailand'),
        ('KH', 'Cambodia'),
        ('PH', 'Philippines'),
    ], string='Country', required=True, tracking=True)

    country_id = fields.Many2one(
        'res.country',
        string='Country Reference',
        compute='_compute_country_id',
        store=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_currency_id',
        store=True
    )

    payroll_journal_id = fields.Many2one(
        'account.journal',
        string='Payroll Journal',
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
        help="Optional default journal to use when creating payslips from this configuration."
    )
    debit_account_id = fields.Many2one(
        'account.account',
        string='Default Debit Account',
        help="Default debit account to assign when creating salary rules from this formula configuration."
    )
    credit_account_id = fields.Many2one(
        'account.account',
        string='Default Credit Account',
        help="Default credit account to assign when creating salary rules from this formula configuration."
    )

    structure_id = fields.Many2one(
        'hr.payroll.structure',
        string='Payroll Structure',
        tracking=True,
        help="Link to the payroll structure this config applies to"
    )
    mid_cycle_source_component_id = fields.Many2one(
        'hr.formula.rule',
        string='Mid-Cycle Source Component',
        domain="[('config_id', '=', id)]",
        help="Component whose value will be carried forward from mid-cycle runs."
    )
    mid_cycle_target_component_id = fields.Many2one(
        'hr.formula.rule',
        string='End-Cycle Target Component',
        domain="[('config_id', '=', id)]",
        help="Component that receives the carried mid-cycle amount in end-cycle runs."
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    # ==========================================
    # NOTE: Country-specific fields (e.g., Vietnam insurance/tax links)
    # should be added via model inheritance in country-specific modules
    # ==========================================

    # ==========================================
    # FORMULA RULES (One2many)
    # ==========================================
    rule_ids = fields.One2many(
        'hr.formula.rule',
        'config_id',
        string='Formula Rules',
        copy=True
    )

    # F11 — progressive rate/bracket tables referenced by BRACKET(code, value)
    rate_table_ids = fields.One2many(
        'hr.formula.rate.table',
        'config_id',
        string='Rate Tables',
        copy=True
    )

    # ==========================================
    # B2 — CONFIG BRANCHES (safe fork / merge)
    # ==========================================
    # A branch is a full config copy tagged with the config it was forked from.
    # Edits happen in the branch in isolation; a merge writes the branch's
    # changed formulas back onto the parent and seals a release. None of these
    # copy into a clone (a clone starts life as its own mainline).
    parent_branch_id = fields.Many2one(
        'hr.formula.config', string='Branched from',
        ondelete='set null', index=True, copy=False,
        help="The configuration this one was forked from (empty for mainline configs)."
    )
    child_branch_ids = fields.One2many(
        'hr.formula.config', 'parent_branch_id',
        string='Branches', copy=False
    )
    branch_note = fields.Char(string='Branch note', copy=False)
    fork_milestone_id = fields.Many2one(
        'hr.formula.config.milestone', string='Fork point',
        ondelete='set null', copy=False,
        help="Milestone recorded on the parent when this branch was cut — the "
             "reference point for detecting parent drift (merge conflicts)."
    )
    branch_state = fields.Selection([
        ('open', 'Open'),
        ('merged', 'Merged'),
        ('discarded', 'Discarded'),
    ], string='Branch Status', default='open', copy=False,
        help="Lifecycle of a branch after it is cut.")

    # ==========================================
    # B5 — SCHEME VARIANTS (master → variants)
    # ==========================================
    # A variant is a materialized config that inherits its components from a
    # master scheme. Editing the master and pushing propagates every component
    # EXCEPT those the variant has locally overridden. Variants are real configs
    # (no compute-path change) kept in sync — the cure for "N near-identical
    # configurations" a bureau otherwise maintains by hand.
    master_config_id = fields.Many2one(
        'hr.formula.config', string='Master scheme',
        ondelete='set null', index=True, copy=False,
        help="The master scheme this variant inherits its components from."
    )
    variant_ids = fields.One2many(
        'hr.formula.config', 'master_config_id',
        string='Variants', copy=False
    )
    variant_override_codes = fields.Char(
        string='Overridden components', copy=False,
        help="Comma-separated component codes that are locally overridden in "
             "this variant and therefore protected from a master push/sync."
    )

    rule_count = fields.Integer(
        string='Rules Count',
        compute='_compute_rule_count'
    )

    input_rule_count = fields.Integer(
        string='Input Rules',
        compute='_compute_rule_count'
    )

    formula_rule_count = fields.Integer(
        string='Formula Rules',
        compute='_compute_rule_count'
    )

    # ==========================================
    # SAMPLE DATA & TESTING
    # ==========================================
    sample_data_ids = fields.One2many(
        'hr.formula.sample.data',
        'config_id',
        string='Sample Data'
    )

    test_result_ids = fields.One2many(
        'hr.formula.test.result',
        'config_id',
        string='Test Results'
    )

    sample_count = fields.Integer(
        string='Sample Count',
        compute='_compute_sample_count'
    )

    carryover_count = fields.Integer(
        string='Carryover Count',
        compute='_compute_carryover_count'
    )
    proration_count = fields.Integer(
        string='Proration Count',
        compute='_compute_proration_count'
    )
    retro_count = fields.Integer(
        string='Retro Count',
        compute='_compute_retro_count'
    )

    # ==========================================
    # INTEGRATION
    # ==========================================
    connector_id = fields.Many2one(
        'hr.integration.connector',
        string='Data Source Connector',
        help="HR system connector for importing payroll input data"
    )

    use_color_coded_excel_import = fields.Boolean(
        string='Use Color-Coded Excel Import',
        default=False,
        help="When enabled, Excel import uses color-coded headers and rows."
    )

    # ==========================================
    # STATE & VALIDATION
    # ==========================================
    state = fields.Selection([
        ('draft', 'Draft'),
        ('testing', 'Testing'),
        ('validated', 'Validated'),
        ('active', 'Active'),
        ('archived', 'Archived')
    ], string='Status', default='draft', tracking=True, required=True)

    validation_status = fields.Selection([
        ('pending', 'Pending Validation'),
        ('passed', 'All Tests Passed'),
        ('failed', 'Tests Failed'),
        ('warning', 'Warnings')
    ], string='Validation Status', compute='_compute_validation_status', store=True)

    last_validated = fields.Datetime(
        string='Last Validated',
        readonly=True
    )

    last_validated_by = fields.Many2one(
        'res.users',
        string='Validated By',
        readonly=True
    )

    validation_message = fields.Text(
        string='Validation Message',
        readonly=True
    )

    has_circular_refs = fields.Boolean(
        string='Has Circular References',
        compute='_compute_has_circular_refs',
        store=True
    )

    has_errors = fields.Boolean(
        string='Has Errors',
        compute='_compute_has_errors',
        store=True
    )

    error_details = fields.Text(
        string='Error Details',
        compute='_compute_error_details',
        help="Detailed list of formulas with errors"
    )

    circular_ref_details = fields.Text(
        string='Circular Reference Details',
        compute='_compute_circular_ref_details',
        help="Detailed list of formulas with circular references"
    )

    # ==========================================
    # UI SETTINGS
    # ==========================================
    theme = fields.Selection([
        ('light', 'Light Theme'),
        ('dark', 'Dark Theme'),
        ('auto', 'Auto (System)')
    ], string='Grid Theme', default='light')

    grid_row_height = fields.Integer(
        string='Row Height (px)',
        default=32
    )

    show_formula_bar = fields.Boolean(
        string='Show Formula Bar',
        default=True
    )

    show_column_letters = fields.Boolean(
        string='Show Column Letters',
        default=True
    )

    show_gridlines = fields.Boolean(
        string='Show Gridlines',
        default=True
    )

    frozen_columns = fields.Integer(
        string='Frozen Columns',
        default=1,
        help="Number of columns to freeze on the left"
    )

    default_column_width = fields.Integer(
        string='Default Column Width (px)',
        default=120
    )

    # ==========================================
    # DISPLAY NAME
    # ==========================================
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    # ==========================================
    # COMPUTED METHODS
    # ==========================================
    @api.depends('name', 'code', 'country_code')
    def _compute_display_name(self):
        for record in self:
            country = dict(self._fields['country_code'].selection).get(record.country_code, '')
            record.display_name = f"{record.name} ({country})" if country else record.name

    def name_get(self):
        result = []
        country_map = dict(self._fields['country_code'].selection)
        for record in self:
            country = country_map.get(record.country_code, '')
            label = f"{record.name} ({country})" if country else record.name
            result.append((record.id, label))
        return result

    @api.depends('country_code')
    def _compute_country_id(self):
        country_mapping = {
            'VN': 'VN', 'ID': 'ID', 'IN': 'IN', 'SG': 'SG',
            'MY': 'MY', 'TH': 'TH', 'KH': 'KH', 'PH': 'PH'
        }
        for record in self:
            if record.country_code:
                country = self.env['res.country'].search([
                    ('code', '=', country_mapping.get(record.country_code))
                ], limit=1)
                record.country_id = country
            else:
                record.country_id = False

    @api.depends('country_code')
    def _compute_currency_id(self):
        currency_mapping = {
            'VN': 'VND', 'ID': 'IDR', 'IN': 'INR', 'SG': 'SGD',
            'MY': 'MYR', 'TH': 'THB', 'KH': 'KHR', 'PH': 'PHP'
        }
        for record in self:
            if record.country_code:
                currency = self.env['res.currency'].search([
                    ('name', '=', currency_mapping.get(record.country_code))
                ], limit=1)
                record.currency_id = currency or self.env.company.currency_id
            else:
                record.currency_id = self.env.company.currency_id

    @api.depends('rule_ids', 'rule_ids.column_type')
    def _compute_rule_count(self):
        for record in self:
            record.rule_count = len(record.rule_ids)
            record.input_rule_count = len(record.rule_ids.filtered(
                lambda r: r.column_type == 'input'
            ))
            record.formula_rule_count = len(record.rule_ids.filtered(
                lambda r: r.column_type == 'formula'
            ))

    @api.depends('sample_data_ids')
    def _compute_sample_count(self):
        for record in self:
            record.sample_count = len(record.sample_data_ids)

    def _compute_carryover_count(self):
        for record in self:
            record.carryover_count = self.env['hr.payroll.cycle.carryover'].search_count([
                ('formula_config_id', '=', record.id)
            ])

    def _compute_proration_count(self):
        for record in self:
            record.proration_count = self.env['hr.payroll.proration.line'].search_count([
                ('formula_config_id', '=', record.id)
            ])

    def _compute_retro_count(self):
        for record in self:
            record.retro_count = self.env['hr.payroll.retro.adjustment'].search_count([
                ('formula_config_id', '=', record.id)
            ])

    def action_view_cycle_carryovers(self):
        self.ensure_one()
        action = self.env.ref('pb_hr_payroll_formula.action_payroll_cycle_carryover').read()[0]
        action['domain'] = [('formula_config_id', '=', self.id)]
        action['context'] = {
            'default_formula_config_id': self.id,
        }
        return action

    def action_view_proration_lines(self):
        self.ensure_one()
        action = self.env.ref('pb_hr_payroll_formula.action_payroll_proration_line').read()[0]
        action['domain'] = [('formula_config_id', '=', self.id)]
        action['context'] = {
            'default_formula_config_id': self.id,
        }
        return action

    def action_view_retro_adjustments(self):
        self.ensure_one()
        action = self.env.ref('pb_hr_payroll_formula.action_payroll_retro_adjustment').read()[0]
        action['domain'] = [('formula_config_id', '=', self.id)]
        action['context'] = {
            'default_formula_config_id': self.id,
        }
        return action

    def action_rebuild_cycle_carryover(self):
        self.ensure_one()
        if self.cycle_type != 'mid_cycle':
            raise UserError(_("Carryover can only be rebuilt for mid-cycle configurations."))
        batch_model = self.env['hr.payroll.import.batch']
        batches = batch_model.search([
            ('formula_config_id', '=', self.id),
            ('state', '=', 'done'),
        ])
        if not batches:
            raise UserError(_("No completed batches found for this configuration."))
        rebuilt = 0
        skipped = 0
        for batch in batches:
            payslips = batch.created_payslip_ids
            payslip_run = batch.payslip_run_id
            if not payslips and payslip_run:
                payslips = payslip_run.slip_ids
            if not payslips:
                skipped += 1
                continue
            batch._create_mid_cycle_carryovers(payslips, payslip_run=payslip_run)
            rebuilt += 1
        if not rebuilt:
            raise UserError(_("No payslips found for completed batches."))
        message = _('Carryover rebuilt for %s batch(es).') % rebuilt
        if skipped:
            message += _(' %s batch(es) skipped without payslips.') % skipped
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }
    @api.depends('test_result_ids', 'test_result_ids.status')
    def _compute_validation_status(self):
        for record in self:
            if not record.test_result_ids:
                record.validation_status = 'pending'
            elif all(r.status == 'passed' for r in record.test_result_ids):
                record.validation_status = 'passed'
            elif any(r.status == 'failed' for r in record.test_result_ids):
                record.validation_status = 'failed'
            else:
                record.validation_status = 'warning'

    @api.depends('rule_ids.has_circular_ref')
    def _compute_has_circular_refs(self):
        for record in self:
            record.has_circular_refs = any(
                r.has_circular_ref for r in record.rule_ids
            )

    @api.depends('rule_ids.is_valid')
    def _compute_has_errors(self):
        for record in self:
            record.has_errors = any(
                not r.is_valid for r in record.rule_ids if r.excel_formula
            )

    @api.depends('rule_ids.is_valid', 'rule_ids.validation_message')
    def _compute_error_details(self):
        for record in self:
            invalid_rules = record.rule_ids.filtered(
                lambda r: r.excel_formula and not r.is_valid
            )
            if invalid_rules:
                details = []
                for rule in invalid_rules:
                    error_msg = rule.validation_message or _("Unknown error")
                    details.append(
                        f"• Column {rule.column_letter} ({rule.code}): {error_msg}"
                    )
                record.error_details = "\n".join(details)
            else:
                record.error_details = False

    @api.depends('rule_ids.has_circular_ref')
    def _compute_circular_ref_details(self):
        for record in self:
            circular_rules = record.rule_ids.filtered('has_circular_ref')
            if circular_rules:
                details = []
                for rule in circular_rules:
                    formula_preview = (rule.excel_formula or '')[:50]
                    if len(rule.excel_formula or '') > 50:
                        formula_preview += "..."
                    details.append(
                        f"• Column {rule.column_letter} ({rule.code}): {formula_preview}"
                    )
                record.circular_ref_details = "\n".join(details)
            else:
                record.circular_ref_details = False

    # ==========================================
    # CONSTRAINTS
    # ==========================================
    _sql_constraints = [
        ('code_uniq', 'unique(code, company_id)',
         'Configuration code must be unique per company!'),
    ]

    @api.model
    def _generate_unique_code(self, name, company_id=None):
        """Build a meaningful, unique Reference Code from the config name
        (e.g. 'VPTQ Mid Cycle' -> 'VPTQ_MID_CYCLE', with a _2/_3 suffix on
        collision). Used by create() and the Formula Studio wizard so the
        code never has to be typed by hand."""
        base = re.sub(r'[^A-Z0-9]+', '_', (name or 'CONFIG').upper()).strip('_')[:28] or 'CONFIG'
        company_id = company_id or self.env.company.id
        code, n = base, 1
        while self.with_context(active_test=False).search_count(
                [('code', '=', code), ('company_id', '=', company_id)]):
            n += 1
            code = '%s_%s' % (base, n)
        return code

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_unique_code(vals.get('name'), vals.get('company_id'))
        return super().create(vals_list)

    @api.constrains('rule_ids')
    def _check_rule_codes(self):
        for record in self:
            codes = record.rule_ids.mapped('code')
            if len(codes) != len(set(codes)):
                raise ValidationError(_(
                    "Duplicate rule codes found! Each rule must have a unique code."
                ))

    @api.constrains('use_proration', 'proration_component_ids')
    def _check_proration_components(self):
        for record in self:
            if record.use_proration and not record.proration_component_ids:
                raise ValidationError(_(
                    "Select at least one prorated component when proration is enabled."
                ))

    @api.constrains('use_auto_retro', 'retro_component_id')
    def _check_retro_component(self):
        for record in self:
            if record.use_auto_retro and not record.retro_component_id:
                raise ValidationError(_(
                    "Select a retro target component when auto retro is enabled."
                ))

    # ==========================================
    # STATE ACTIONS
    # ==========================================
    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_start_testing(self):
        self.write({'state': 'testing'})
        action = self.action_validate_formulas()
        if isinstance(action, dict):
            if action.get('type') == 'ir.actions.client' and action.get('tag') == 'display_notification':
                params = action.setdefault('params', {})
                if not params.get('next'):
                    params['next'] = {'type': 'ir.actions.client', 'tag': 'reload'}
        return action

    def action_validate(self):
        """Validate all formulas and mark as validated"""
        self.ensure_one()
        self.action_validate_formulas()
        if not self.has_errors and not self.has_circular_refs:
            self.write({
                'state': 'validated',
                'last_validated': fields.Datetime.now(),
                'last_validated_by': self.env.user.id,
                'validation_message': _("All formulas validated successfully.")
            })
        else:
            self.write({
                'validation_message': _("Validation failed. Please fix errors before activating.")
            })

    def action_activate(self):
        """Activate the configuration for use in payroll"""
        self.ensure_one()
        if self.has_errors or self.has_circular_refs:
            raise UserError(_(
                "Cannot activate configuration with errors or circular references. "
                "Please validate and fix all issues first."
            ))
        self.write({'state': 'active'})
        # F7: anchor a milestone so "compare to activation" has a reference point.
        n = self.env['hr.formula.config.milestone'].sudo().search_count(
            [('config_id', '=', self.id)]) + 1
        self.env['hr.formula.config.milestone'].sudo().record(
            self, _("Activated v%s") % n)

    def action_archive(self):
        self.write({'state': 'archived', 'active': False})

    # ==========================================
    # FORMULA VALIDATION
    # ==========================================
    def action_regenerate_formulas(self):
        """Regenerate Python code for all formula rules

        Use this after updating the formula conversion logic to refresh
        all cached Python formulas with the latest conversion engine.
        """
        self.ensure_one()
        rules = self.rule_ids.filtered(lambda r: r.column_type == 'formula' and r.excel_formula)

        # Build column mapping
        column_map = {}
        for r in self.rule_ids.sorted(key=lambda r: r.sequence):
            if r.column_letter and r.code:
                column_map[r.column_letter] = r.code

        regenerated = 0
        errors = []
        for rule in rules:
            try:
                python_code = rule._convert_excel_to_python(rule.excel_formula, column_map)
                rule.write({'python_formula': python_code})
                regenerated += 1
                _logger.info(f"Regenerated formula for {rule.code}: {rule.excel_formula} -> {python_code}")
            except Exception as e:
                errors.append(f"{rule.code}: {str(e)}")
                _logger.error(f"Failed to regenerate formula for {rule.code}: {e}")

        if errors:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Regeneration Complete with Errors'),
                    'message': _('%d formulas regenerated, %d errors:\n%s') % (
                        regenerated, len(errors), '\n'.join(errors[:5])
                    ),
                    'type': 'warning',
                    'sticky': True,
                }
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Formulas Regenerated'),
                'message': _('%d Python formulas successfully regenerated.') % regenerated,
                'type': 'success',
            }
        }

    def action_validate_formulas(self):
        """Validate all formulas (syntax + evaluation) in this configuration"""
        self.ensure_one()
        from ..formula_engine import FormulaValidator

        validator = FormulaValidator()
        rules = self.rule_ids.sorted(key=lambda r: r.sequence)

        # Build column mapping
        column_map = {r.column_letter: r.code for r in rules}

        # PART 1: Syntax Validation
        syntax_errors = []
        for rule in rules:
            if rule.column_type == 'formula' and rule.excel_formula:
                is_valid, message = validator.validate_formula(
                    rule.excel_formula,
                    column_map
                )
                rule.write({
                    'is_valid': is_valid,
                    'validation_message': message if not is_valid else ''
                })
                if not is_valid:
                    syntax_errors.append(f"• {rule.column_letter} ({rule.code}): {message}")

        # Check circular references
        circular = validator.check_circular_references(rules)
        for rule in rules:
            rule.has_circular_ref = rule.code in circular

        # PART 2: Evaluation Testing (if sample data exists)
        evaluation_errors = []
        formula_rules = rules.filtered(lambda r: r.column_type == 'formula')

        if self.sample_data_ids:
            # Clear previous evaluation errors
            formula_rules.write({
                'has_evaluation_error': False,
                'last_evaluation_error': False
            })

            # Use first sample data for testing
            sample = self.sample_data_ids[0]
            input_values = json.loads(sample.input_values_json or '{}')

            # Test each formula
            _logger.info(f"Testing {len(formula_rules)} formulas with sample data...")
            for rule in formula_rules:
                try:
                    rule.evaluate(input_values)
                except Exception as e:
                    _logger.warning(f"Formula evaluation failed for {rule.code}: {e}")

            # Collect evaluation errors
            error_rules = self.rule_ids.filtered(lambda r: r.has_evaluation_error)
            for rule in error_rules:
                # Get first line of error for summary
                error_summary = rule.last_evaluation_error.split('\n')[1] if rule.last_evaluation_error else 'Unknown error'
                evaluation_errors.append(f"• {rule.column_letter} ({rule.code}): {error_summary}")

        # PART 3: Build combined error message
        all_errors = []

        if syntax_errors:
            all_errors.append("SYNTAX ERRORS:")
            all_errors.extend(syntax_errors)
            all_errors.append("")  # Empty line

        if evaluation_errors:
            all_errors.append("EVALUATION ERRORS:")
            all_errors.extend(evaluation_errors)
            all_errors.append("")  # Empty line
            all_errors.append("→ Click on formulas with red highlighting to see detailed error messages")

        if all_errors:
            self.validation_message = "\n".join(all_errors)
            message_type = 'warning'
            title = _('Formula Errors Found')
        else:
            self.validation_message = _("✓ All formulas are valid and evaluate correctly!")
            message_type = 'success'
            title = _('Validation Complete')

        # Force reload to show updated error highlights
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': self.validation_message if all_errors else _('All %d formulas validated successfully!') % len(formula_rules),
                'type': message_type,
                'sticky': bool(all_errors),
                'next': {'type': 'ir.actions.client', 'tag': 'reload'} if evaluation_errors else None,
            }
        }

    # ==========================================
    # SAMPLE DATA TESTING
    # ==========================================
    def action_run_tests(self):
        """Run all sample data tests"""
        self.ensure_one()
        from ..formula_engine import FormulaEvaluator

        evaluator = FormulaEvaluator()
        rules = self.rule_ids.sorted(key=lambda r: r.sequence)

        # Clear previous test results
        self.test_result_ids.unlink()

        results = []

        def _coerce_number(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        for sample in self.sample_data_ids:
            # Get input values
            input_values = json.loads(sample.input_values_json or '{}')
            expected_values = json.loads(sample.expected_values_json or '{}')

            # Evaluate formulas
            try:
                computed = evaluator.evaluate_all(rules, input_values)
                sample.computed_values_json = json.dumps(computed)

                # Compare results
                for code, expected in expected_values.items():
                    actual = computed.get(code, 0)
                    expected_num = _coerce_number(expected)
                    actual_num = _coerce_number(actual)
                    if expected_num is None or actual_num is None:
                        match = str(expected) == str(actual)
                        discrepancy = 0 if match else 100
                        status = 'passed' if match else 'failed'
                    else:
                        discrepancy = abs(expected_num - actual_num) / max(abs(expected_num), 1) * 100
                        status = 'passed' if discrepancy < 0.01 else 'failed'

                    results.append({
                        'config_id': self.id,
                        'sample_id': sample.id,
                        'rule_code': code,
                        'expected_value': expected,
                        'computed_value': actual,
                        'discrepancy_percent': discrepancy,
                        'status': status,
                    })
            except Exception as e:
                results.append({
                    'config_id': self.id,
                    'sample_id': sample.id,
                    'rule_code': 'ERROR',
                    'expected_value': 0,
                    'computed_value': 0,
                    'discrepancy_percent': 100,
                    'status': 'failed',
                    'error_message': str(e),
                })

        # Create test result records
        self.env['hr.formula.test.result'].create(results)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tests Complete'),
                'message': _('%d tests executed. Check results for details.') % len(results),
                'type': 'info',
            }
        }

    # ==========================================
    # GRID DATA FOR UI
    # ==========================================
    def get_grid_data(self):
        """Return data formatted for the Excel-like grid widget"""
        self.ensure_one()
        rules = self.rule_ids.sorted(key=lambda r: r.sequence)

        columns = []
        for rule in rules:
            columns.append({
                'id': rule.id,
                'letter': rule.column_letter,
                'code': rule.code,
                'name': rule.name,
                'type': rule.column_type,
                'formula': rule.excel_formula or '',
                'width': rule.column_width,
                'format': rule.number_format,
                'decimals': rule.decimal_places,
                'isValid': rule.is_valid,
                'hasCircularRef': rule.has_circular_ref,
                'validationMessage': rule.validation_message or '',
                'categoryId': rule.category_id.id if rule.category_id else False,
                'categoryName': rule.category_id.name if rule.category_id else '',
            })

        # Sample data rows
        rows = []
        for sample in self.sample_data_ids:
            input_vals = json.loads(sample.input_values_json or '{}')
            computed_vals = json.loads(sample.computed_values_json or '{}')
            expected_vals = json.loads(sample.expected_values_json or '{}')

            row = {
                'id': sample.id,
                'name': sample.name,
                'isHeader': False,
                'values': {},
            }
            for rule in rules:
                code = rule.code
                row['values'][code] = {
                    'input': input_vals.get(code),
                    'computed': computed_vals.get(code),
                    'expected': expected_vals.get(code),
                }
            rows.append(row)

        return {
            'configId': self.id,
            'name': self.name,
            'theme': self.theme,
            'showFormulaBar': self.show_formula_bar,
            'showColumnLetters': self.show_column_letters,
            'showGridlines': self.show_gridlines,
            'frozenColumns': self.frozen_columns,
            'rowHeight': self.grid_row_height,
            'columns': columns,
            'rows': rows,
            'currency': self.currency_id.symbol if self.currency_id else '',
        }

    def save_grid_data(self, data):
        """Save grid data from the Excel-like widget"""
        self.ensure_one()

        # Update column order and formulas
        for col_data in data.get('columns', []):
            rule = self.env['hr.formula.rule'].browse(col_data['id'])
            if rule.exists():
                rule.write({
                    'sequence': col_data.get('sequence', rule.sequence),
                    'excel_formula': col_data.get('formula', rule.excel_formula),
                    'column_width': col_data.get('width', rule.column_width),
                    'name': col_data.get('name', rule.name),
                })

        # Update sample data
        for row_data in data.get('rows', []):
            sample = self.env['hr.formula.sample.data'].browse(row_data['id'])
            if sample.exists():
                sample.write({
                    'input_values_json': json.dumps(row_data.get('inputValues', {})),
                    'expected_values_json': json.dumps(row_data.get('expectedValues', {})),
                })

        # Trigger recomputation of column letters
        self.rule_ids._compute_column_letter()

        return {'success': True}

    # ==========================================
    # IMPORT FROM EXISTING STRUCTURE
    # ==========================================
    def action_import_from_structure(self):
        """Open wizard to import rules from existing payroll structure"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import from Payroll Structure'),
            'res_model': 'hr.formula.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_config_id': self.id,
                'default_structure_id': self.structure_id.id if self.structure_id else False,
            }
        }

    # ==========================================
    # IMPORT FROM EXCEL (MULTI-SHEET WIZARD)
    # ==========================================
    def action_import_from_excel_multisheet(self):
        """Open multi-sheet Excel import wizard with enhanced features.

        This wizard provides:
        - Worksheet selection with checkboxes
        - Per-sheet column selection
        - Append order configuration
        - Cross-sheet formula resolution (VLOOKUP, SUMIF, etc.)
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import from Excel (Multi-Sheet)'),
            'res_model': 'hr.formula.multisheet.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_config_id': self.id,
            }
        }

    # ==========================================
    # GENERATE SAMPLE DATA
    # ==========================================
    def action_generate_sample_data(self):
        """Open wizard to generate sample data from employees/payslips"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Sample Data'),
            'res_model': 'hr.formula.sample.data.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_config_id': self.id,
            }
        }

    # ==========================================
    # OPEN EXCEL GRID
    # ==========================================
    def action_open_excel_grid(self):
        """Open the Excel-like formula configuration grid"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Formula Configuration Grid'),
            'res_model': 'hr.formula.config',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('pb_hr_payroll_formula.view_formula_config_excel_grid').id,
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_launch_payroll_import(self):
        """Launch payroll import with this configuration pre-selected"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Payroll Import'),
            'res_model': 'hr.payroll.import.batch',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_formula_config_id': self.id,
                'default_source_type': 'excel',
            },
        }

    def action_delete_all_rules(self):
        """Delete all salary component rules from this configuration"""
        self.ensure_one()
        rule_count = len(self.rule_ids)
        if rule_count == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Components'),
                    'message': _('There are no salary components to delete.'),
                    'type': 'warning',
                    'sticky': False,
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }

        self.rule_ids.unlink()
        _logger.info(f"Deleted {rule_count} salary component rules from config {self.code}")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Components Deleted'),
                'message': _('%d salary components have been deleted.') % rule_count,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_test_all_formulas(self):
        """Test evaluate all formulas with sample data and report errors"""
        self.ensure_one()

        # Check if we have sample data
        if not self.sample_data_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Sample Data'),
                    'message': _('Please create sample data first to test formula evaluation. '
                               'Go to Sample Data tab and add test cases.'),
                    'type': 'warning',
                    'sticky': True,
                }
            }

        # Use the first sample data for testing
        sample = self.sample_data_ids[0]
        input_values = json.loads(sample.input_values_json or '{}')

        # Clear previous evaluation errors
        formula_rules = self.rule_ids.filtered(lambda r: r.column_type == 'formula')
        formula_rules.write({
            'has_evaluation_error': False,
            'last_evaluation_error': False
        })

        # Evaluate each rule with the sample data
        _logger.info(f"Testing {len(formula_rules)} formulas with sample data...")
        for rule in formula_rules:
            try:
                rule.evaluate(input_values)
            except Exception as e:
                # Error will be captured by the evaluate method
                _logger.warning(f"Formula test failed for {rule.code}: {e}")

        # Count errors
        error_rules = self.rule_ids.filtered(lambda r: r.has_evaluation_error)
        error_count = len(error_rules)

        if error_count > 0:
            error_list = []
            for rule in error_rules:
                error_list.append(f"• {rule.column_letter} ({rule.code}): {rule.name}")

            message = _(
                "%d formula(s) have evaluation errors:\n\n%s\n\n"
                "Click on the formula rules with red highlighting to see detailed error messages."
            ) % (error_count, '\n'.join(error_list[:10]))

            if error_count > 10:
                message += _("\n... and %d more. Check the list for all errors.") % (error_count - 10)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Formula Evaluation Errors Found'),
                    'message': message,
                    'type': 'danger',
                    'sticky': True,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('All Formulas Valid'),
                    'message': _('All %d formulas evaluated successfully without errors!') % len(formula_rules),
                    'type': 'success',
                    'sticky': False,
                }
            }
