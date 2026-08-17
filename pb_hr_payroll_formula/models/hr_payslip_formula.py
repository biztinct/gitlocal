# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import json
import logging

_logger = logging.getLogger(__name__)


class HrPayslipFormula(models.Model):
    """
    Extends hr.payslip to support formula-based computation.
    """
    _name = 'hr.payslip'  # Explicitly set for Odoo 19 inheritance compatibility
    _inherit = ['hr.payslip']

    # ==========================================
    # FORMULA COMPUTATION FIELDS
    # ==========================================
    calculation_method = fields.Selection([
        ('standard', 'Standard (Salary Rules)'),
        ('spreadsheet', 'Spreadsheet Import'),
        ('formula', 'Formula Engine')
    ], string='Calculation Method', default='standard',
       help="Method used to compute this payslip")

    formula_config_id = fields.Many2one(
        'hr.formula.config',
        string='Formula Configuration',
        help="Formula configuration used for computation"
    )

    formula_computation_log = fields.Text(
        string='Computation Log',
        readonly=True,
        help="Detailed log of formula computations"
    )

    formula_input_values = fields.Text(
        string='Input Values (JSON)',
        help="Input values used for formula computation"
    )

    formula_computed_values = fields.Text(
        string='Computed Values (JSON)',
        readonly=True,
        help="Computed values from formula engine"
    )

    payslip_identifier_payload = fields.Text(
        string='Payslip Identifier Payload (JSON)',
        readonly=True,
        help="Grouped component values for payslip printing."
    )
    report_visible_string_payload = fields.Text(
        string='Report Visible String Payload (JSON)',
        readonly=True,
        help="String values for report_visible components (used for exports)."
    )

    has_formula_errors = fields.Boolean(
        string='Has Formula Errors',
        compute='_compute_has_formula_errors'
    )

    # ==========================================
    # COMPUTED
    # ==========================================
    @api.depends('formula_computation_log')
    def _compute_has_formula_errors(self):
        for record in self:
            log = record.formula_computation_log or ''
            record.has_formula_errors = 'Error' in log or 'error' in log

    # ==========================================
    # FORMULA COMPUTATION
    # ==========================================
    def compute_sheet_with_formulas(self):
        """
        Compute payslip using formula engine instead of standard salary rules.
        """
        for payslip in self:
            if not payslip.formula_config_id:
                # Try to find appropriate config
                config = payslip._find_formula_config()
                if config:
                    payslip.formula_config_id = config
                else:
                    raise UserError(_(
                        "No formula configuration found for this payslip. "
                        "Please configure formula rules or use standard computation."
                    ))

            config = payslip.formula_config_id

            # Validate config is active
            if config.state != 'active':
                raise UserError(_(
                    "Formula configuration '%s' is not active. "
                    "Please activate it before using for payroll."
                ) % config.name)

            # Get input values
            input_values = payslip._get_formula_input_values(config)
            payslip.formula_input_values = json.dumps(input_values, indent=2)

            # Get rules in order (display) but compute using dependency sorting
            rules = config.rule_ids.sorted(key=lambda r: r.sequence)

            computed_values, computation_log = payslip._evaluate_rules_with_dependencies(
                rules,
                input_values
            )

            payslip.formula_computed_values = json.dumps(computed_values, indent=2)
            payslip.formula_computation_log = '\n'.join(computation_log)
            if 'report_visible_string_payload' in payslip._fields:
                payload = payslip._build_report_visible_string_payload(rules, computed_values)
                payslip.report_visible_string_payload = json.dumps(payload)

            # Create/update payslip lines
            payslip._create_payslip_lines_from_formulas(rules, computed_values)

            # Mark calculation method
            payslip.calculation_method = 'formula'

        return True

    def _evaluate_rules_with_dependencies(self, rules, input_values):
        """Evaluate rules using dependency order to handle forward references."""
        self.ensure_one()
        if not rules:
            return input_values.copy(), []

        rules._compute_dependencies()
        try:
            from ..formula_engine import FormulaEvaluator
            evaluator = FormulaEvaluator()
            sorted_rules = evaluator._topological_sort(rules)
        except Exception:
            sorted_rules = rules.sorted(key=lambda r: r.sequence)

        results = input_values.copy()
        computation_log = []

        for rule in sorted_rules:
            try:
                if rule.column_type == 'input':
                    if rule.code not in results:
                        results[rule.code] = rule.default_value or 0.0
                    value = results.get(rule.code, 0.0)
                    computation_log.append(
                        f"[{rule.column_letter}] {rule.code} (input) = {value}"
                    )
                elif rule.column_type == 'constant':
                    value = rule.constant_value or 0.0
                    results[rule.code] = value
                    computation_log.append(
                        f"[{rule.column_letter}] {rule.code} (constant) = {value}"
                    )
                elif rule.column_type == 'formula':
                    value = rule.evaluate(results)
                    results[rule.code] = value
                    computation_log.append(
                        f"[{rule.column_letter}] {rule.code} = {rule.excel_formula} -> {value}"
                    )
            except Exception as e:
                error_msg = f"Error in {rule.code}: {str(e)}"
                computation_log.append(f"[ERROR] {error_msg}")
                results[rule.code] = 0.0

            if rule.column_letter:
                results[rule.column_letter] = results.get(rule.code, 0.0)

        # Second pass to resolve forward references not captured in dependency parsing.
        for _pass in range(2):
            changed = False
            for rule in sorted_rules:
                if rule.column_type != 'formula':
                    continue
                try:
                    value = rule.evaluate(results)
                except Exception as e:
                    computation_log.append(f"[ERROR] Error in {rule.code}: {str(e)}")
                    value = 0.0
                if results.get(rule.code) != value:
                    results[rule.code] = value
                    if rule.column_letter:
                        results[rule.column_letter] = value
                    changed = True
            if not changed:
                break

        return results, computation_log

    def _build_report_visible_string_payload(self, rules, computed_values):
        """Capture string values for report_visible components."""
        self.ensure_one()

        def coerce_numeric_string(value):
            cleaned = value.strip().replace(' ', '')
            if not cleaned:
                return None
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
                return float(cleaned)
            except (ValueError, TypeError):
                return None

        payload = []
        for rule in rules:
            if not rule.report_visible:
                continue
            value = computed_values.get(rule.code)
            if value is None and rule.column_letter:
                value = computed_values.get(rule.column_letter)
            if not isinstance(value, str):
                continue
            stripped = value.strip()
            if not stripped:
                continue
            if coerce_numeric_string(stripped) is not None:
                continue
            payload.append({
                'code': rule.code or '',
                'name': rule.name or '',
                'value': stripped,
            })
        return payload

    def _find_formula_config(self):
        """Find the formula configuration for a payslip that has none set.

        Only reached when ``formula_config_id`` is empty — everything created by
        the pay-run wizard or the import batch sets it explicitly.

        Ordered most-specific first. Note that ``struct_id`` is a WEAK signal:
        several configs legitimately share one ``hr.payroll.structure`` (a
        mid-cycle and an end-cycle config for the same structure is the normal
        shape), and a payslip carries no cycle marker of its own to tell them
        apart. So a structure match is used only when it is unambiguous;
        otherwise we fall through rather than silently pick the wrong cycle.

        Every lookup is company-scoped: without it, a multi-company database
        can hand a payslip a config belonging to another company.
        """
        self.ensure_one()
        Config = self.env['hr.formula.config']
        # Company-less configs are shared, so include them — a strict equality
        # filter would resolve to nothing at all for such a config, which is
        # worse than the cross-company match this replaces.
        company_domain = [
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
        ] if self.company_id else []

        # 1. A sibling payslip in the same run already resolved this. Strongest
        #    signal available and free of the ambiguity below.
        if self.payslip_run_id:
            sibling = self.payslip_run_id.slip_ids.filtered(
                lambda s: s.id != self.id and s.formula_config_id
            )[:1]
            if sibling:
                return sibling.formula_config_id

            # 2. The import batch that produced the run records the config it
            #    was run with.
            batch = self.env['hr.payroll.import.batch'].search(
                [('payslip_run_id', '=', self.payslip_run_id.id)], limit=1
            )
            if batch.formula_config_id:
                return batch.formula_config_id

        # 3. Payroll structure — only when it identifies exactly one config.
        if self.struct_id:
            configs = Config.search(company_domain + [
                ('structure_id', '=', self.struct_id.id),
                ('state', '=', 'active'),
            ])
            if len(configs) == 1:
                return configs
            if len(configs) > 1:
                _logger.warning(
                    "Payslip %s: structure %s maps to %s active formula configs (%s) — "
                    "ambiguous, ignoring the structure and falling back.",
                    self.id, self.struct_id.display_name, len(configs),
                    ", ".join(configs.mapped('name')),
                )

        # 4. Employee's country.
        if self.employee_id and self.employee_id.country_id:
            config = Config.search(company_domain + [
                ('country_code', '=', self.employee_id.country_id.code),
                ('state', '=', 'active'),
            ], limit=1)
            if config:
                return config

        # 5. Any active config for this company.
        return Config.search(company_domain + [('state', '=', 'active')], limit=1)

    def _get_formula_input_values(self, config):
        """
        Get input values for formula computation from various sources:
        - Contract data (wage, allowances)
        - Worked days
        - External integration (Zoho, etc.)
        """
        self.ensure_one()
        values = {}

        # Get input rules
        input_rules = config.rule_ids.filtered(lambda r: r.column_type == 'input')

        for rule in input_rules:
            value = rule.default_value

            # Try to get from contract
            if self.contract_id:
                contract_mapping = {
                    'BASIC': 'wage',
                    'WAGE': 'wage',
                    'BASE': 'wage',
                }
                contract_field = contract_mapping.get(rule.code.upper())
                if contract_field and hasattr(self.contract_id, contract_field):
                    value = getattr(self.contract_id, contract_field) or value

            # Try to get from worked days
            if rule.code.startswith('WD_') or rule.code.startswith('HOURS'):
                wd_code = rule.code.replace('WD_', '').replace('HOURS_', '')
                worked_day = self.worked_days_line_ids.filtered(
                    lambda w: w.code == wd_code
                )[:1]
                if worked_day:
                    if 'HOURS' in rule.code:
                        value = worked_day.number_of_hours
                    else:
                        value = worked_day.number_of_days

            # Try to get from integration connector (only confirmed 'active'
            # mappings are load-bearing — F114/D114.2)
            if config.connector_id:
                # Get from mapped field
                mapping = config.connector_id._sync_mapping_ids().filtered(
                    lambda m: m.target_rule_id == rule
                )[:1]
                if mapping:
                    # TODO: Get actual value from synced data
                    pass

            values[rule.code] = value

        return values

    def _create_payslip_lines_from_formulas(self, rules, computed_values):
        """Create payslip lines from formula computation results"""
        self.ensure_one()

        # Clear existing lines
        self.line_ids.unlink()

        lines_to_create = []

        for rule in rules:
            if not rule.appears_on_payslip:
                continue

            amount = computed_values.get(rule.code, 0.0)

            # Find or create salary rule
            salary_rule = rule.salary_rule_id
            if not salary_rule:
                # Try to find existing rule with same code. When computing many
                # payslips (the Run Payroll wizard) a shared cache is passed via
                # context to avoid repeating this search per-rule per-payslip
                # (an N+1 that was ~45k queries for a 900-slip run). Cache is
                # keyed by (code, company) so results are identical either way.
                cache = self.env.context.get('pb_salary_rule_cache')
                key = (rule.code, self.company_id.id)
                if cache is not None and key in cache:
                    salary_rule = cache[key]
                else:
                    salary_rule = self.env['hr.salary.rule'].search([
                        ('code', '=', rule.code),
                        ('company_id', '=', self.company_id.id),
                    ], limit=1)
                    if cache is not None:
                        cache[key] = salary_rule

            line_data = {
                'slip_id': self.id,
                'name': rule.name,
                'code': rule.code,
                'category_id': rule.category_id.id if rule.category_id else False,
                'sequence': rule.sequence,
                'amount': amount,
                'quantity': 1.0,
                'rate': 100.0,
                'salary_rule_id': salary_rule.id if salary_rule else False,
                'contract_id': self.contract_id.id,
                'employee_id': self.employee_id.id,
                'report_visible': rule.report_visible or False,
                'component_type': rule.component_type or False,
            }
            lines_to_create.append(line_data)

        if lines_to_create:
            self.env['hr.payslip.line'].create(lines_to_create)

    # ==========================================
    # OVERRIDE STANDARD COMPUTE
    # ==========================================
    def compute_sheet(self):
        """Override to support formula-based computation"""
        formula_payslips = self.filtered(
            lambda p: p.calculation_method == 'formula' and p.formula_config_id
        )
        standard_payslips = self - formula_payslips

        # Compute formula payslips
        if formula_payslips:
            formula_payslips.compute_sheet_with_formulas()

        # Compute standard payslips
        if standard_payslips:
            return super(HrPayslipFormula, standard_payslips).compute_sheet()

        return True

    # ==========================================
    # ACTIONS
    # ==========================================
    def action_recompute_formula_lines(self):
        for payslip in self:
            config = payslip.formula_config_id or payslip._find_formula_config()
            if not config:
                raise UserError(_(
                    "No formula configuration found for this payslip."
                ))
            if payslip.formula_config_id != config:
                payslip.formula_config_id = config.id
            if payslip.calculation_method != 'formula':
                payslip.calculation_method = 'formula'

            import_line = self.env['hr.payroll.import.line'].search(
                [('payslip_id', '=', payslip.id)],
                limit=1
            )
            input_values = None
            if import_line and import_line.batch_id:
                batch = import_line.batch_id
                input_values = batch._transform_data_to_formula_inputs(
                    import_line.get_raw_data(),
                    contract=payslip.contract_id,
                    employee=payslip.employee_id,
                )
                payslip.formula_input_values = json.dumps(input_values)
                payslip.line_ids.unlink()
                batch._compute_and_create_payslip_lines(payslip, input_values)
            else:
                if payslip.formula_input_values:
                    try:
                        input_values = json.loads(payslip.formula_input_values or '{}')
                    except Exception:
                        input_values = {}
                else:
                    input_values = payslip._get_formula_input_values(config)
                    payslip.formula_input_values = json.dumps(input_values, indent=2)

                rules = config.rule_ids.sorted(key=lambda r: r.sequence)
                computed_values, computation_log = payslip._evaluate_rules_with_dependencies(
                    rules,
                    input_values
                )
                payslip.formula_computed_values = json.dumps(computed_values, indent=2)
                payslip.formula_computation_log = '\n'.join(computation_log)
                if 'report_visible_string_payload' in payslip._fields:
                    payload = payslip._build_report_visible_string_payload(rules, computed_values)
                    payslip.report_visible_string_payload = json.dumps(payload)
                payslip._create_payslip_lines_from_formulas(rules, computed_values)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Recomputed'),
                'message': _("Payslip formulas recalculated with current settings."),
                'type': 'success',
            }
        }

    def action_switch_to_formula(self):
        """Switch this payslip to formula-based computation"""
        self.ensure_one()
        config = self._find_formula_config()
        if not config:
            raise UserError(_(
                "No active formula configuration found. "
                "Please create and activate a formula configuration first."
            ))

        self.write({
            'calculation_method': 'formula',
            'formula_config_id': config.id,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Switched to Formula Mode'),
                'message': _("Using configuration: %s") % config.name,
                'type': 'success',
            }
        }

    def action_payslip_level2_done(self):
        result = super().action_payslip_level2_done()
        self._trigger_mid_cycle_carryover()
        return result

    def _trigger_mid_cycle_carryover(self):
        if 'hr.payroll.import.batch' not in self.env:
            return
        batch_model = self.env['hr.payroll.import.batch']
        batches = batch_model
        for slip in self:
            batch = False
            if slip.payslip_run_id:
                batch = batch_model.search(
                    [('payslip_run_id', '=', slip.payslip_run_id.id)],
                    limit=1
                )
            if not batch:
                batch = batch_model.search(
                    [('created_payslip_ids', 'in', slip.id)],
                    limit=1
                )
            if not batch:
                continue
            config = batch.formula_config_id or slip.formula_config_id
            if not config or config.cycle_type != 'mid_cycle':
                continue
            batches |= batch
        for batch in batches:
            payslips = batch.created_payslip_ids
            run = batch.payslip_run_id
            if not payslips and run:
                payslips = run.slip_ids
            if payslips:
                batch._create_mid_cycle_carryovers(payslips, payslip_run=run)

    def action_switch_to_standard(self):
        """Switch back to standard salary rule computation"""
        self.write({
            'calculation_method': 'standard',
        })

    def action_view_formula_log(self):
        """View detailed formula computation log"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Formula Computation Log'),
            'res_model': 'hr.payslip',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref(
                'pb_hr_payroll_formula.view_payslip_formula_log'
            ).id,
            'target': 'new',
        }

    # ==========================================
    # W73 — themed payslip render data (WRITE-FREE by construction, D-L8)
    # ==========================================
    # Accent palette hex — the LOCKED sc-* keys, same values the studio preview
    # and payslip.scss section variants use (C11; no free hex).
    _THEME_ACCENT_HEX = {
        'slate': '#64748B', 'indigo': '#5A4BB0', 'emerald': '#059669',
        'amber': '#D97706', 'rose': '#E11D48', 'sky': '#0284C7', 'violet': '#7C3AED',
    }
    _THEME_FONT_STACK = {
        'system': "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
        'serif': "Georgia, 'Times New Roman', Times, serif",
        'mono': "'SF Mono', 'Cascadia Code', Consolas, monospace",
    }

    def _themed_payslip_render(self):
        """Build the F9-scheme render tree for the themed QWeb report, read-only:
        sections by ``payslip_identifier`` ordered by sequence, lines by
        ``payslip_sequence``, ``visibility_rule`` honored against LINE totals,
        ``collapse_when_empty`` honored, ``label_vi`` under a Vietnamese reader,
        theme tokens applied. Pure reads — the report never writes (D-L8/C16).

        A slip with no formula config still renders (all appears-on lines fall
        into a default 'Payslip' section) so the action never crashes (C7)."""
        self.ensure_one()
        lang = self.env.context.get('lang') or 'en_US'
        is_vi = str(lang).startswith('vi')

        # Line totals summed by code (mirrors the legacy report's dsal helper).
        dsal = {}
        for line in self.line_ids:
            if line.code:
                dsal[line.code] = dsal.get(line.code, 0.0) + line.total

        config = self.formula_config_id
        rules_by_code = {}
        if config:
            for r in config.rule_ids:
                if r.code:
                    rules_by_code[r.code] = r

        # Accent / font / logo — theme fields with safe fallbacks.
        accent_key = (config.theme_accent if config else False) or 'slate'
        font_key = (config.theme_font if config else False) or 'system'
        show_logo = bool(config.theme_show_logo) if config else True
        logo = False
        if show_logo:
            logo = (config.theme_logo if config else False) or (
                self.company_id.logo if self.company_id else False)

        def _line_name(r, code):
            if r:
                nm = (r.salary_rule_id.name if r.salary_rule_id else False) or r.name or r.code
                return nm or code
            return code

        def _visible(r, total):
            rule_vis = r.visibility_rule if r else 'always'
            if rule_vis == 'never':
                return False
            if rule_vis == 'when_nonzero':
                return abs(total) > 0.0000001
            return True

        Section = self.env['hr.payslip.config']
        sections = Section.search(
            [('salary_structure_id', '=', config.id)], order='sequence, id'
        ) if config else Section.browse()

        # Which config rules belong to each section; the rest (appears_on_payslip
        # but unsectioned) fall into a synthetic default section (C7).
        sectioned_codes = set()
        out_sections = []
        for s in sections:
            comps = [r for r in config.rule_ids
                     if r.payslip_identifier.id == s.id and r.appears_on_payslip]
            comps.sort(key=lambda r: (r.payslip_sequence or 0, r.sequence))
            lines = []
            for r in comps:
                sectioned_codes.add(r.code)
                total = dsal.get(r.code, 0.0)
                if not _visible(r, total):
                    continue
                lines.append({'name': _line_name(r, r.code), 'total': total,
                              'is_deduction': total < 0})
            if not lines and s.collapse_when_empty:
                continue
            title = (s.label_vi if (is_vi and s.label_vi) else False) or s.label or s.identifier or ''
            out_sections.append({
                'title': title,
                'color_hex': self._THEME_ACCENT_HEX.get(s.color_key or 'slate', '#64748B'),
                'lines': lines,
                'subtotal': sum(l['total'] for l in lines),
            })

        # Default 'Payslip' section: config rules that appear on the payslip but
        # carry no section (never silently dropped).
        default_lines = []
        for r in config.rule_ids if config else []:
            if r.code in sectioned_codes or not r.appears_on_payslip or r.payslip_identifier:
                continue
            total = dsal.get(r.code, 0.0)
            if not _visible(r, total):
                continue
            default_lines.append({'name': _line_name(r, r.code), 'total': total,
                                  'is_deduction': total < 0})
        # No config at all → every coded line is a default line.
        if not config:
            for code, total in dsal.items():
                default_lines.append({'name': code, 'total': total,
                                      'is_deduction': total < 0})
        if default_lines:
            out_sections.append({
                'title': _('Payslip'),
                'color_hex': self._THEME_ACCENT_HEX.get(accent_key, '#64748B'),
                'lines': default_lines,
                'subtotal': sum(l['total'] for l in default_lines),
            })

        # The slip's own NET line is the only trustworthy net — summing visible
        # section subtotals double-counts totals (GROSS, NET itself) and adds
        # positive employer contributions (WP-L review M1: 42.2M printed vs the
        # real 12.1M). No NET line and no NET-category line → hide the card
        # rather than print a derived number on an employee-facing PDF.
        net = dsal.get('NET')
        if net is None:
            net_lines = self.line_ids.filtered(
                lambda l: l.category_id and l.category_id.code == 'NET')
            net = sum(net_lines.mapped('total')) if net_lines else None
        currency = (config.currency_id.symbol if (config and config.currency_id)
                    else (self.company_id.currency_id.symbol if self.company_id else ''))
        return {
            'accent_hex': self._THEME_ACCENT_HEX.get(accent_key, '#64748B'),
            'font_stack': self._THEME_FONT_STACK.get(font_key, self._THEME_FONT_STACK['system']),
            'show_logo': show_logo and bool(logo),
            'logo': logo,
            'sections': out_sections,
            'net': net,
            'has_net': net is not None,
            'currency': currency,
        }
