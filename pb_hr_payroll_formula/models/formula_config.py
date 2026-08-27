# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from . import formula_operand_context
from . import value_kind_classifier
from odoo.tools.sql import table_exists
from markupsafe import Markup, escape
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
        string='Legacy Payroll Structure',
        tracking=True,
        help="Optional link to an old-style payroll structure, for interop only. "
             "Nothing in the Excel import or the formula calculation reads it — "
             "leave it empty unless this configuration must line up with salary "
             "rules defined outside the formula engine. Several configurations "
             "may share one structure (mid-cycle and end-cycle for the same "
             "structure is normal), so a structure alone does not identify a "
             "configuration."
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

    # F111 — high-water mark for permanent column letters. Monotonic: never
    # decreases, so a deleted component's letter is never handed out again
    # (D111.3). Lazily initialised from the current max letter on first use.
    col_letter_hwm = fields.Integer(string='Letter high-water mark', default=0)

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

    def _resolve_feed_connector(self):
        """The connector whose field mappings feed this scheme, or empty.

        The explicit binding wins. When there is none, the wires themselves are
        asked — a mapping already carries both its connector and, through
        `target_rule_id.config_id`, the scheme it lands on, so a scheme with
        wires is never genuinely ambiguous about where its values come from.

        This exists because the run-time gate in
        `payroll_import_batch._transform_data_to_formula_inputs` reads
        `config.connector_id` and, when it is unset, applies NO mappings at all
        — silently. ABM had 25 confirmed Zoho wires onto this scheme and an
        unset binding, so the board reported 25 mapped while the pay run
        behaved as though the connector did not exist. `create` on
        `hr.integration.field.mapping` now binds on the way in and a migration
        backfilled what was already there; this is the third rail, so that a
        row written by SQL, a restore, or a future path that clears the field
        cannot put a scheme back into that silence.

        Resolving also BINDS, so the answer is stable and visible on the record
        afterwards rather than being recomputed differently later. When wires
        from more than one connector land on the same scheme the one with the
        most wires is chosen, ties broken by id, and the choice is logged —
        the run-time gate can only honour one, and picking silently at random
        would be the same class of defect this method exists to close.
        """
        self.ensure_one()
        if self.connector_id:
            return self.connector_id
        Mapping = self.env['hr.integration.field.mapping']
        mappings = Mapping.sudo().search([
            ('target_rule_id.config_id', '=', self.id),
            ('connector_id', '!=', False),
        ])
        if not mappings:
            return self.env['hr.integration.connector']
        tally = {}
        for mapping in mappings:
            tally[mapping.connector_id] = tally.get(mapping.connector_id, 0) + 1
        winner = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0].id))[0][0]
        if len(tally) > 1:
            _logger.warning(
                "Scheme %s has field mappings from %s connectors; the pay run "
                "can apply only one and chose %s (%s of %s wires). Bind the "
                "scheme explicitly to say otherwise.",
                self.display_name, len(tally), winner.display_name,
                tally[winner], len(mappings))
        self.sudo().connector_id = winner.id
        return winner

    use_color_coded_excel_import = fields.Boolean(
        string='Use Color-Coded Excel Import',
        default=True,
        help="When enabled, Excel import uses color-coded headers and rows."
    )

    # COLROLES P4 — opt-in: let the roles you assigned drive the payroll export's
    # leading employee columns instead of the built-in fixed set. Default OFF, and
    # while it is off the exported workbook is byte-for-byte what it always was.
    export_identity_columns = fields.Boolean(
        string='Role-Driven Export Columns',
        default=False,
        help="Off (default): the payroll Excel export opens with its standard "
             "employee columns.\n"
             "On: it opens with the columns you marked Identity or Employee Profile "
             "in this structure, in their own order. Nothing else about the export "
             "changes."
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
    # W73 — PAYSLIP THEME (brand tokens within compliance bounds; D-L7)
    # ==========================================
    # Accent is a LOCKED palette key over the existing sc-* section colours (no
    # free hex — brand/compliance bounds, C11). Preview and print read these same
    # four fields; the themed QWeb report (D-L8) is the only new report.
    theme_accent = fields.Selection([
        ('slate', 'Slate'),
        ('indigo', 'Indigo'),
        ('emerald', 'Emerald'),
        ('amber', 'Amber'),
        ('rose', 'Rose'),
        ('sky', 'Sky'),
        ('violet', 'Violet'),
    ], string='Payslip Accent', default='slate')
    theme_font = fields.Selection([
        ('system', 'System (sans-serif)'),
        ('serif', 'Serif'),
        ('mono', 'Monospace'),
    ], string='Payslip Font', default='system')
    theme_logo = fields.Binary(
        string='Payslip Logo',
        help="Brand logo for the themed payslip. Falls back to the company logo.")
    theme_show_logo = fields.Boolean(string='Show Logo on Payslip', default=True)
    payslip_header_html = fields.Html(
        string='Payslip Header Content',
        sanitize=True,
        help="Optional formatted content shown below the employee header."
    )
    payslip_footer_html = fields.Html(
        string='Payslip Footer Content',
        sanitize=True,
        help="Optional formatted content shown after the payslip totals."
    )
    payslip_layout_html = fields.Html(
        string='Imported Payslip Document Layout',
        sanitize=True,
        help=("Optional full-document layout reconstructed from an uploaded "
              "payslip. When set, it replaces the standard section preview and "
              "print body without deleting the seeded section configuration.")
    )

    # ------------------------------------------------------------------
    # JOURNEY J2 — the spreadsheet this scheme's columns were read from.
    #
    # A mapping board that can only show the columns of a file somebody has
    # already imported is a board you cannot use until after you have done the
    # thing it exists to help you do. These four fields hold the answer to
    # "what does my file look like" between visits: the workbook itself (so the
    # same gesture can hand it on as a pay run), its name and when it was read,
    # and the columns the loader produced from it.
    #
    # Nothing here is pay DATA. The stored columns carry one sample value each
    # so a heading can be recognised; the file is kept because the user
    # uploaded it to be used, and it is replaced or forgotten on request.
    # ------------------------------------------------------------------
    import_sample_file = fields.Binary(
        string='Sample Pay File', attachment=True, copy=False,
        help="The spreadsheet whose column headings were read for the mapping board.")
    import_sample_filename = fields.Char(string='Sample Pay File Name', copy=False)
    import_sample_date = fields.Datetime(string='Headings Read On', copy=False)
    import_sample_columns_json = fields.Text(
        string='Discovered Columns', copy=False,
        help="The column keys the loader produces for the stored file, as JSON.")

    # Dynamic components inside rich payslip content are persisted as inert,
    # human-readable markers.  The editor turns them into non-editable chips;
    # preview and print resolve them with the active sample/payslip values.
    # Keeping the reference out of HTML attributes also means Odoo's HTML
    # sanitizer can remain fully enabled without losing the component link.
    _payslip_component_token_re = re.compile(
        r'\{\{pb_component:(\d+):(label|value|both)\}\}')
    _payslip_meta_token_re = re.compile(
        r'\{\{pb_meta:(employee_name|employee_id|department|date_from|date_to|period)\}\}')

    def _normalise_payslip_content_tokens(self, html_value):
        """Keep only canonical tokens belonging to this configuration."""
        self.ensure_one()
        allowed = set(self.rule_ids.ids)

        def replace(match):
            rule_id = int(match.group(1))
            if rule_id not in allowed:
                return ''
            return '{{pb_component:%s:%s}}' % (rule_id, match.group(2))

        return self._payslip_component_token_re.sub(replace, str(html_value or ''))

    def _payslip_content_rule_ids(self, html_value, amount_only=False):
        """Return scoped component ids referenced by a rich-content block."""
        self.ensure_one()
        allowed = set(self.rule_ids.ids)
        result = set()
        for match in self._payslip_component_token_re.finditer(str(html_value or '')):
            rule_id, mode = int(match.group(1)), match.group(2)
            if rule_id in allowed and (not amount_only or mode in ('value', 'both')):
                result.add(rule_id)
        return result

    @staticmethod
    def _payslip_token_value(rule, value, currency):
        if value is None:
            return '—'
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        number_format = rule.number_format or 'currency'
        if number_format == 'percentage':
            return ('{:,.2f}'.format(number * 100).rstrip('0').rstrip('.') + '%')
        if number_format == 'integer':
            return '{:,.0f}'.format(number)
        if number_format == 'number':
            return '{:,.2f}'.format(number).rstrip('0').rstrip('.')
        sign = '−' if number < 0 else ''
        return '%s%s%s' % (
            sign, currency or '', '{:,.0f}'.format(abs(number)))

    def _render_payslip_content(self, html_value, values_by_rule=None, currency='', meta=None):
        """Resolve rich-content markers with values for preview or one slip."""
        self.ensure_one()
        rules = {rule.id: rule for rule in self.rule_ids}
        values_by_rule = values_by_rule or {}
        meta = meta or {}

        def replace(match):
            rule = rules.get(int(match.group(1)))
            if not rule:
                return ''
            mode = match.group(2)
            name = ((rule.salary_rule_id.name if rule.salary_rule_id else False)
                    or rule.name or rule.code or _('Component'))
            value = self._payslip_token_value(
                rule, values_by_rule.get(rule.id), currency)
            if mode == 'label':
                return '<span class="pb-ps-component pb-ps-component-label">%s</span>' % escape(name)
            if mode == 'value':
                return '<span class="pb-ps-component pb-ps-component-value">%s</span>' % escape(value)
            return (
                '<span class="pb-ps-component pb-ps-component-both">'
                '<span class="pb-ps-component-name">%s</span>'
                '<span class="pb-ps-component-amount">%s</span>'
                '</span>'
            ) % (escape(name), escape(value))

        # html_value comes from a sanitize=True field.  Only escaped rule data
        # is introduced while resolving markers, so the result remains safe.
        rendered = self._payslip_component_token_re.sub(
            replace, str(html_value or ''))
        rendered = self._payslip_meta_token_re.sub(
            lambda match: str(escape(meta.get(match.group(1)) or '—')),
            rendered)
        return Markup(rendered)

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
    # Odoo 19: legacy _sql_constraints is silently IGNORED (model_classes.py
    # logs "no longer supported") — constraints must be models.Constraint
    # class attributes or they never reach the database (ledger C9).
    _code_uniq = models.Constraint(
        'unique(code, company_id)',
        'Configuration code must be unique per company!')

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
    # DELETE SAFETY
    # ==========================================
    # Real payroll history must never be destroyed by removing the config that
    # produced it. The child FKs are the backstop (payslips / carryover /
    # proration / retro adjustments / import batches are all ondelete='restrict'),
    # but a raw restrict raises an opaque Postgres error, so we look first and
    # report in plain language. Everything NOT listed here is config-scoped
    # metadata on ondelete='cascade' and is meant to go with the config.
    # (model, field, singular, plural) - the plural is spelled out rather than
    # derived, because "import batch" pluralises to "batches", not "batchs".
    _DELETE_BLOCKER_MODELS = [
        ('hr.payslip', 'formula_config_id', 'payslip', 'payslips'),
        ('hr.payroll.import.batch', 'formula_config_id', 'import batch', 'import batches'),
        ('hr.payroll.cycle.carryover', 'formula_config_id', 'carry-forward record', 'carry-forward records'),
        ('hr.payroll.proration.line', 'formula_config_id', 'proration record', 'proration records'),
        ('hr.payroll.retro.adjustment', 'formula_config_id', 'retro adjustment', 'retro adjustments'),
    ]

    def _delete_blockers(self):
        """Records that make a hard delete unsafe, newest concern first.

        Returns a list of ``{'model', 'label', 'count'}`` dicts - empty means
        the config carries no payroll history and can be deleted outright.

        ``table_exists`` is checked per model because the addons tree is SHARED
        across databases while schemas are created by a per-database upgrade:
        between an rsync and the `-u` of database N, the model class is in the
        registry but its table is not in the schema, and an unguarded search
        would raise UndefinedTable and leave the transaction ABORTED - which
        would take the whole cockpit board down with it, not just this check.
        """
        self.ensure_one()
        blockers = []
        for model_name, field_name, singular, plural in self._DELETE_BLOCKER_MODELS:
            Model = self.env.get(model_name)
            if Model is None or field_name not in Model._fields:
                continue
            if not table_exists(self.env.cr, Model._table):
                continue
            count = Model.sudo().with_context(active_test=False).search_count(
                [(field_name, '=', self.id)])
            if count:
                blockers.append({
                    'model': model_name,
                    'label': singular if count == 1 else plural,
                    'count': count,
                })
        return blockers

    def _delete_blocker_message(self, blockers):
        """Human sentence for a blocker list, e.g. '12 payslips and 1 import batch'."""
        parts = ['%d %s' % (b['count'], b['label']) for b in blockers]
        if not parts:
            return ''
        if len(parts) == 1:
            return parts[0]
        return '%s and %s' % (', '.join(parts[:-1]), parts[-1])

    def unlink(self):
        for config in self:
            blockers = config._delete_blockers()
            if blockers:
                raise UserError(_(
                    "\"%(name)s\" cannot be deleted because it is used by "
                    "%(blockers)s.\n\nArchive it instead - the configuration is "
                    "hidden from everyday use while the payroll history that "
                    "depends on it stays intact.",
                    name=config.name or '',
                    blockers=config._delete_blocker_message(blockers),
                ))
        return super().unlink()

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
    # SET UP COLUMNS FROM EXCEL (MULTI-SHEET WIZARD)
    # ==========================================
    def action_import_from_excel_multisheet(self):
        """Read a workbook's STRUCTURE and turn it into this scheme's columns.

        JOURNEY J2 — behaviour unchanged, name corrected. This is the sixth
        and most confusing of the old import doors: it was called "Import from
        Excel" next to another button called "Payroll Import", and the two do
        opposite things. This one defines what the columns ARE (a one-off
        setup act, from a colour-coded workbook); the other loads this month's
        numbers into them. Every string it puts on screen now says "columns"
        and "set up" so the two can never be confused again.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Set Up Columns from Excel'),
            'res_model': 'hr.formula.multisheet.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_config_id': self.id,
            }
        }

    # ==========================================
    # JOURNEY J2 — the template built from this scheme
    # ==========================================
    def _pay_template_pk_header(self):
        """The employee-identifier heading a generated template leads with.

        Prefer what this scheme already reads — a component bound to (or named
        after) an identifier column means the file in use spells it that way,
        and a template that spells it differently would fail to merge. Fall
        back to the loader's own first candidate.
        """
        self.ensure_one()
        from ..integrations.excel_connector import ExcelConnector
        Batch = self.env['hr.payroll.import.batch']
        for rule in self.rule_ids.sorted(key=lambda r: r.sequence):
            _sheet, header = ExcelConnector.template_slot_for(rule)
            if header and Batch._find_primary_key_header([header]):
                return header
        return _('Employee Code')

    def _build_pay_data_template(self):
        """`(bytes, filename)` — the workbook whose headings this scheme reads.

        One generator, and it lives where every other Excel-shaped thing in
        this module lives. The studio's download button and the tests are its
        callers; before J2 it had none at all.
        """
        self.ensure_one()
        from ..integrations.excel_connector import ExcelConnector
        connector = ExcelConnector(self.env['hr.integration.connector'])
        content = connector.generate_template(
            self.rule_ids.sorted(key=lambda r: r.sequence),
            pk_header=self._pay_template_pk_header(),
            sheet_title=_('Pay Data'),
        )
        stem = (self.code or self.name or 'scheme').strip().replace(' ', '_')
        return content, '%s_pay_data_template.xlsx' % stem

    # ==========================================
    # COLUMN ROLES — shared summary (COLROLES P4)
    # ==========================================
    # An import that has just filed six of a workbook's columns as people data
    # should SAY so; the studio, the single-sheet wizard and the multi-sheet
    # wizard all need the same sentence, so it is written once here.
    @api.model
    def role_labels(self):
        """Lowercase role words for a running sentence ("2 identity · 4 bank")."""
        return {
            'payroll': _("payroll"),
            'identity': _("identity"),
            'profile': _("employee profile"),
            'contract': _("contract"),
            'bank': _("bank"),
            'reference': _("reference"),
        }

    @api.model
    def role_counts_for_rules(self, rules):
        """Ordered {role: count} over a rule recordset — roles with no column
        are dropped, and payroll always leads because it is what most of the
        workbook is."""
        order = ('payroll', 'identity', 'profile', 'contract', 'bank', 'reference')
        tally = dict.fromkeys(order, 0)
        for rule in rules:
            role = rule.column_role or 'payroll'
            tally[role] = tally.get(role, 0) + 1
        return {role: tally[role] for role in order if tally.get(role)}

    @api.model
    def format_role_summary(self, counts):
        """"41 payroll · 2 identity · 4 bank columns" — empty when nothing counted."""
        labels = self.role_labels()
        parts = ['%s %s' % (n, labels.get(role, role)) for role, n in counts.items() if n]
        if not parts:
            return ''
        return _("%s columns") % ' · '.join(parts)

    def role_column_summary(self):
        """The sentence for THIS structure, over the columns it holds now."""
        self.ensure_one()
        return self.format_role_summary(self.role_counts_for_rules(self.rule_ids))

    #: roles whose columns describe a PERSON rather than their pay — the ones a
    #: mapping board exists for.
    PEOPLE_ROLES = ('identity', 'profile', 'contract', 'bank')

    def studio_people_mapping_action(self, rules):
        """Reopen Formula Studio on the people-mapping board after an import.

        Deliberately narrow. It fires only when the import was launched FROM the
        studio (context flag `pbfs_studio_import`) AND the import actually produced
        people columns — a pure-payroll workbook is never bounced to a board it has
        nothing to put on. Returns None when the studio is not installed, so the
        formula engine keeps working without it.
        """
        self.ensure_one()
        if not self.env.context.get('pbfs_studio_import'):
            return None
        if not rules.filtered(
                lambda r: (r.column_role or 'payroll') in self.PEOPLE_ROLES):
            return None
        action = self.env.ref('pb_formula_studio.action_pb_formula_studio',
                              raise_if_not_found=False)
        if not action:
            return None
        signal = {'config_id': self.id, 'pbfs_open_people_mapping': True}
        return {
            'type': 'ir.actions.client',
            'tag': action.tag,
            'name': action.name,
            'target': 'current',
            'params': dict(signal),
            'context': dict(signal),
        }

    # ==========================================
    # NETROLE P2 — the import ends with a category conversation
    # ==========================================
    # An Excel scheme arrives with every component on the same shelf, and until
    # now the only thing that ever moved one was a person opening each row. The
    # formulas already say what each component does to net pay (NETROLE Phase 1);
    # this is where that reading is offered — as a question, at the moment the
    # import finishes, never as a silent write.
    def category_review_action(self, next_action=None):
        """Classify this scheme and return the review action — or None.

        None means "say nothing": the studio is not installed, the
        classification failed, or every component is already filed the way the
        formulas read it. In all three cases the caller's existing chain is
        byte-identical to what it was before this method existed.

        A classification failure must NEVER fail an import (C7 says log it), so
        every step here is guarded. The one failure that DOES open the review is
        a scheme with no net-pay component: that is not an error to swallow, it
        is the one question only a person can answer.
        """
        self.ensure_one()
        try:
            summary = (self.classify_net_roles() or {}).get(self.id) or {}
        except Exception:
            _logger.exception(
                "NETROLE: could not classify configuration %s after import; "
                "the import itself is unaffected", self.id)
            return None
        action = self.env.ref('pb_formula_studio.action_pb_category_review',
                              raise_if_not_found=False)
        if not action:
            return None
        if summary.get('error'):
            worth_asking = bool(self.rule_ids)
        else:
            try:
                suggestions = self.suggest_categories()
            except Exception:
                _logger.exception(
                    "NETROLE: could not build category suggestions for "
                    "configuration %s", self.id)
                return None
            worth_asking = any(
                row.get('changes') or row.get('band_conflict')
                or row.get('confidence') == 'review'
                for row in suggestions)
        if not worth_asking:
            return None
        params = {'config_id': self.id}
        if next_action:
            params['next_action'] = next_action
        return {
            'type': 'ir.actions.client',
            'tag': action.tag,
            'name': action.name,
            'target': 'current',
            'params': params,
            'context': {'config_id': self.id},
        }

    def action_open_category_review(self):
        """Reopen the review any time, from the structure itself."""
        self.ensure_one()
        action = self.env.ref('pb_formula_studio.action_pb_category_review',
                              raise_if_not_found=False)
        if not action:
            raise UserError(_(
                "The category review needs the Formula Studio, which is not "
                "installed on this database."))
        try:
            self.classify_net_roles()
        except Exception:
            _logger.exception("NETROLE: classification failed for config %s",
                              self.id)
        return {
            'type': 'ir.actions.client',
            'tag': action.tag,
            'name': action.name,
            'target': 'current',
            'params': {'config_id': self.id},
            'context': {'config_id': self.id},
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
        """Load this month's pay data for this scheme — through the guided flow.

        JOURNEY J2: same door, same pre-scoping, one destination. It used to
        open the raw batch form; it now arrives in the same four-step flow the
        Import cockpit's hero button opens, with this scheme already chosen.
        """
        self.ensure_one()
        return self.env['hr.payroll.import.batch'].action_open_guided_import(
            config=self, source_type='excel')

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

    # ==================================================================
    # VALUEKIND — what each component's value IS
    # ==================================================================
    def _value_kind_samples(self, limit=200):
        """``{CODE: [raw values]}`` from the newest finished import batch.

        Read from ``hr_payroll_import_line.raw_data_json`` — the material as it
        ARRIVED. Never from ``hr_payslip.formula_input_values``: that blob is
        downstream of the two coercion sites this whole feature exists to fix,
        so evidence drawn from it would only confirm its own damage (C18.118).

        A component is looked up by its connector mapping's ``source_field``
        first, then by its own spellings (code, name, column letter), because a
        component fed through the header ladder has no mapping row at all.
        """
        self.ensure_one()
        Line = self.env['hr.payroll.import.line'].sudo()
        Batch = self.env['hr.payroll.import.batch'].sudo()
        batch = Batch.search([('formula_config_id', '=', self.id),
                              ('state', '=', 'done')], order='id desc', limit=1)
        if not batch:
            batch = Batch.search([('formula_config_id', '=', self.id)],
                                 order='id desc', limit=1)
        if not batch:
            return {}
        lines = Line.search([('batch_id', '=', batch.id)], limit=limit)
        rows = []
        for line in lines:
            try:
                data = json.loads(line.raw_data_json or '{}')
            except (TypeError, ValueError):
                continue
            if isinstance(data, dict):
                rows.append(data)
        if not rows:
            return {}

        # One normalised index per row, so a header spelling that differs only in
        # case, spacing or punctuation still finds its column.
        Batchm = self.env['hr.payroll.import.batch']
        indexed = []
        for row in rows:
            indexed.append({Batchm._normalize_header_key(k): v
                            for k, v in row.items() if isinstance(k, str)})

        mapping_by_rule = {}
        if 'hr.integration.field.mapping' in self.env:
            wires = self.env['hr.integration.field.mapping'].sudo().search(
                [('target_rule_id', 'in', self.rule_ids.ids)])
            mapping_by_rule = {w.target_rule_id.id: w for w in wires
                               if w.target_rule_id}

        out = {}
        for rule in self.rule_ids:
            keys = []
            wire = mapping_by_rule.get(rule.id)
            if wire and wire.source_field:
                keys.append(wire.source_field)
            keys += [rule.code, rule.name, rule.data_source_field]
            values = []
            for key in keys:
                if not key:
                    continue
                norm = Batchm._normalize_header_key(key)
                if not norm:
                    continue
                found = [row.get(norm) for row in indexed if norm in row]
                if found:
                    values = found
                    break
            if values:
                out[rule.code] = values
        return out

    def _scheme_operand_contexts(self):
        """``{REF: set(contexts)}`` over EVERY formula in this scheme.

        A component's kind is decided by how the WHOLE scheme uses it, not by
        its own formula — an input column has no formula of its own at all.
        """
        self.ensure_one()
        merged = {}
        for rule in self.rule_ids:
            formula_operand_context.merge_contexts(
                merged,
                formula_operand_context.deserialize(rule.formula_operand_roles))
        return merged

    def _rule_operand_contexts(self, rule, scheme_contexts):
        """The contexts applied to ONE rule, under any spelling it answers to.

        `formula_dependencies` and the operand scan both record COLUMN LETTERS
        as often as codes, so all three spellings are asked (C18.115).
        """
        contexts = set()
        for spelling in (rule.code, rule.column_letter, rule.original_column_letter):
            key = formula_operand_context.normalize_ref(spelling)
            if key:
                contexts |= set(scheme_contexts.get(key, ()))
        return contexts

    def classify_value_kinds(self, force=False):
        """(Re)classify every component's `value_kind`. Returns rows changed.

        `value_kind_source='user'` is never touched unless `force`, which the UI
        does not offer — a person's answer outranks the ladder, permanently.
        """
        self.ensure_one()
        # Imported here, not at module top: `formula_net_role` declares
        # `_inherit` on both hr.formula.rule and hr.formula.config, and
        # `models/__init__.py` loads it deliberately LAST (line 78). A top-level
        # import would pull those inherits in before `formula_rule` itself.
        from .formula_net_role import looks_like_a_quantity

        scheme = self._scheme_operand_contexts()
        samples = self._value_kind_samples()
        vendor = {}
        if 'hr.integration.field.mapping' in self.env:
            for wire in self.env['hr.integration.field.mapping'].sudo().search(
                    [('target_rule_id', 'in', self.rule_ids.ids)]):
                if wire.target_rule_id:
                    vendor[wire.target_rule_id.id] = wire.source_data_type or ''

        changed = 0
        for rule in self.rule_ids:
            if rule.value_kind_source == 'user' and not force:
                continue
            kind, reason = value_kind_classifier.classify_value_kind(
                code=rule.code or '',
                name=rule.name or '',
                column_role=rule.column_role or 'payroll',
                net_role=rule.net_role or '',
                column_type=rule.column_type or 'input',
                contexts=self._rule_operand_contexts(rule, scheme),
                quantity=bool(looks_like_a_quantity(rule.name or '', rule.code or '')),
                vendor_type=vendor.get(rule.id, ''),
                sample_values=samples.get(rule.code) or [],
                appears_on_payslip=bool(rule.appears_on_payslip),
            )
            if rule.value_kind != kind or rule.value_kind_reason != reason:
                rule.with_context(skip_formula_version=True).write({
                    'value_kind': kind,
                    'value_kind_source': 'auto',
                    'value_kind_reason': reason,
                })
                changed += 1
        _logger.info("VALUEKIND: classified %s component(s) on scheme %s (%s)",
                     changed, self.id, self.name)
        return changed

    def audit_value_kinds(self, run_id=None):
        """Read-only. Two different disagreements, deliberately kept apart.

        ``rows``  — the component's DECLARED kind versus the values the source
                    actually delivers. Self-healing: re-classifying makes these
                    agree, so an empty list here means the declarations are
                    consistent, not that payroll is correct.

        ``drift`` — what the source delivered versus WHAT THE PAYSLIP STORED.
                    This is the one that matters, and the one that would have
                    caught ABM's LOCATION in March instead of leaving it to a
                    screenshot: the feed sent "Ho Chi Minh Branch", the payslip
                    holds 0.0, and every `IF(F5="La Nga", …)` in the scheme has
                    been false ever since. No declaration is wrong; the VALUE
                    was destroyed on the way in.

        Reads and reports. Never writes, never recomputes a payslip — repairing
        a historic run is a separate, explicitly-approved exercise.
        """
        self.ensure_one()
        samples = self._value_kind_samples()
        scheme = self._scheme_operand_contexts()
        rows = []
        for rule in self.rule_ids:
            values = samples.get(rule.code) or []
            if not values:
                continue
            bad = value_kind_classifier.contradictions(rule.value_kind, values)
            if not bad:
                continue
            rows.append({
                'code': rule.code,
                'name': rule.name or rule.code,
                'declared': rule.value_kind,
                'source': rule.value_kind_source,
                'reason': rule.value_kind_reason or '',
                'contexts': sorted(self._rule_operand_contexts(rule, scheme)),
                'seen': len(values),
                'contradicted': len(bad),
                'examples': [str(v)[:60] for v in bad[:3]],
            })
        rows.sort(key=lambda r: -r['contradicted'])
        return {
            'config_id': self.id,
            'name': self.name or '',
            'rows': rows,
            'drift': self._audit_stored_drift(run_id=run_id, samples=samples),
        }

    def _audit_stored_drift(self, run_id=None, samples=None, limit=200):
        """Components whose payslips hold a number where the source sent text.

        The comparison is per COMPONENT, not per employee: a component is
        reported when the source delivered a non-blank, non-numeric value for a
        row and the payslip for that same period stored the component's numeric
        fallback. That pairing is what "the value was destroyed on the way in"
        looks like from the outside.
        """
        self.ensure_one()
        samples = samples if samples is not None else self._value_kind_samples()
        if not samples:
            return []
        Slip = self.env['hr.payslip'].sudo()
        domain = [('formula_config_id', '=', self.id)]
        if run_id:
            domain.append(('payslip_run_id', '=', int(run_id)))
        slips = Slip.search(domain, order='id desc', limit=limit)
        if not slips:
            return []

        stored = {}        # code -> list of stored values
        for slip in slips:
            try:
                blob = json.loads(slip.formula_input_values or '{}')
            except (TypeError, ValueError):
                continue
            if not isinstance(blob, dict):
                continue
            for code, value in blob.items():
                stored.setdefault(code, []).append(value)

        out = []
        for rule in self.rule_ids:
            delivered = samples.get(rule.code) or []
            held = stored.get(rule.code) or []
            if not delivered or not held:
                continue
            texty = [v for v in delivered
                     if value_kind_classifier.is_texty_sample(v)]
            if not texty:
                continue
            numeric_held = [v for v in held
                            if isinstance(v, (int, float))
                            and not isinstance(v, bool)]
            if not numeric_held:
                continue
            out.append({
                'code': rule.code,
                'name': rule.name or rule.code,
                'declared': rule.value_kind,
                'delivered_examples': [str(v)[:60] for v in texty[:3]],
                'stored_examples': numeric_held[:3],
                'slips_seen': len(held),
                'slips_numeric': len(numeric_held),
            })
        out.sort(key=lambda r: -r['slips_numeric'])
        return out

    # ==================================================================
    # VALUEKIND P2 — the board a person decides types on
    # ==================================================================
    _VALUE_KIND_GATE = (
        'pb_hr_payroll_base.group_payroll_base_officer',
        'pb_hr_payroll_base.group_payroll_base_manager',
        'pb_hr_payroll_base.group_payroll_super_admin',
        'om_hr_payroll.group_hr_payroll_manager',
    )

    def _value_kind_gate(self):
        """Same ladder the pay run itself requires. Read AND write."""
        if self.env.su or self.env.user._is_admin():
            return
        if any(self.env.user.has_group(g) for g in self._VALUE_KIND_GATE):
            return
        raise AccessError(_(
            "You need payroll officer access to change how a pay component's "
            "value is read."))

    def _value_kind_lane(self, rule, wire):
        """Where this component's value comes from, in the Atlas's own words.

        One vocabulary for both boards. The point of this whole feature is that
        a type is a property of the COMPONENT, not of the wire that happens to
        feed it — so the lane is information, never the thing being edited.
        """
        if rule.column_type == 'formula':
            return 'calculated'
        if rule.column_type == 'constant':
            return 'constant'
        if wire:
            return 'feed'
        if getattr(rule, 'is_contract_component', False):
            return 'contract_component'
        return 'excel'

    @api.model
    def _value_kind_options(self):
        """The selection, as the client needs it — value, label, and whether
        choosing it means the value gets converted to a number."""
        field = self.env['hr.formula.rule']._fields['value_kind']
        return [{'value': key,
                 'label': label,
                 'numeric': value_kind_classifier.wants_number(key)}
                for key, label in field.selection]

    def value_kind_board(self, run_id=None):
        """Everything the Field types board shows, in one call.

        Read-only. Nothing here changes a value or recomputes a payslip —
        a person presses Save, and then presses Recompute, and both say so.
        """
        self.ensure_one()
        self._value_kind_gate()
        samples = self._value_kind_samples()
        scheme = self._scheme_operand_contexts()
        drift = {d['code']: d
                 for d in self._audit_stored_drift(run_id=run_id, samples=samples)}

        wires = {}
        if 'hr.integration.field.mapping' in self.env:
            for wire in self.env['hr.integration.field.mapping'].sudo().search(
                    [('target_rule_id', 'in', self.rule_ids.ids)]):
                if wire.target_rule_id:
                    wires[wire.target_rule_id.id] = wire

        rows = []
        for rule in self.rule_ids.sorted(key=lambda r: (r.sequence, r.id)):
            wire = wires.get(rule.id)
            values = samples.get(rule.code) or []
            row_drift = drift.get(rule.code)
            rows.append({
                'id': rule.id,
                'code': rule.code or '',
                'name': rule.name or rule.code or '',
                'band': (rule.component_type or '')
                        or (rule.category_id.name or '') or _('Ungrouped'),
                'lane': self._value_kind_lane(rule, wire),
                'source_key': (wire.source_field if wire
                               else (rule.data_source_field or rule.column_letter or '')),
                'kind': rule.value_kind,
                'kind_source': rule.value_kind_source,
                'kind_reason': rule.value_kind_reason or '',
                'appears_on_payslip': bool(rule.appears_on_payslip),
                'numeric': value_kind_classifier.wants_number(rule.value_kind),
                'delivered': [str(v)[:48] for v in values[:3]],
                'seen': len(values),
                'drift': bool(row_drift),
                'drift_stored': (row_drift or {}).get('stored_examples') or [],
                'contexts': sorted(self._rule_operand_contexts(rule, scheme)),
            })
        return {
            'config_id': self.id,
            'name': self.name or '',
            'options': self._value_kind_options(),
            'rows': rows,
            'drift_count': len(drift),
        }

    def set_value_kinds(self, updates):
        """``{code: kind}`` -> the rows changed. A person's decision.

        Writes `value_kind_source='user'`, which every automatic writer —
        the classifier and the upgrade migration alike — is required to respect
        for good. `reset_value_kind` is the only way back.
        """
        self.ensure_one()
        self._value_kind_gate()
        valid = {k for k, _label in
                 self.env['hr.formula.rule']._fields['value_kind'].selection}
        by_code = {(r.code or '').upper(): r for r in self.rule_ids}
        changed = []
        for code, kind in (updates or {}).items():
            rule = by_code.get(str(code).upper())
            if not rule:
                raise UserError(_("No component named '%s' on this scheme.", code))
            if kind not in valid:
                raise UserError(_("'%(kind)s' is not a value kind.", kind=kind))
            if rule.value_kind == kind and rule.value_kind_source == 'user':
                continue
            rule.write({
                'value_kind': kind,
                'value_kind_source': 'user',
                'value_kind_reason': _("%s chose this.", self.env.user.name),
            })
            changed.append(rule.code)
        if changed:
            _logger.info("VALUEKIND: %s set %s on scheme %s: %s",
                         self.env.user.login, len(changed), self.id,
                         ', '.join(changed))
        return {'changed': changed,
                'note': _("Saved. Existing payslips keep the values they were "
                          "computed with until the run is recomputed.")}

    def reset_value_kind(self, codes):
        """Hand chosen components back to the classifier."""
        self.ensure_one()
        self._value_kind_gate()
        wanted = {str(c).upper() for c in (codes or [])}
        rules = self.rule_ids.filtered(lambda r: (r.code or '').upper() in wanted)
        if rules:
            rules.write({'value_kind_source': 'auto'})
            self.classify_value_kinds()
        return {'reset': rules.mapped('code')}
