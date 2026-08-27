# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from markupsafe import Markup
from odoo.exceptions import UserError, ValidationError
import json
import logging

from . import input_provenance

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
        ondelete='restrict',
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

    # SOURCING S1 — the sibling of the blob above: for each input code, WHERE its
    # value came from on the run that produced this payslip. Text-holding-JSON and
    # not `fields.Json`, deliberately: it is always read together with
    # `formula_input_values`, which is Text, and two fields that are always read
    # together must not need two different accessors.
    #
    # Absent or empty means "this payslip predates the feature" — which is a
    # different statement from "this component has no source", and no reader may
    # collapse the two.
    formula_input_sources = fields.Text(
        string='Input Sources (JSON)',
        readonly=True,
        help="Where each input value came from on the run that produced this payslip."
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
            # SOURCING S1 — provenance is filled in the same pass and written beside
            # the values, never derived afterwards: re-deriving would have to guess
            # which branch won, which is the whole class of bug this replaces.
            input_sources = {}
            input_values = payslip._get_formula_input_values(config, provenance=input_sources)
            payslip.formula_input_values = json.dumps(input_values, indent=2)
            payslip.formula_input_sources = json.dumps(input_sources, indent=2)

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

    def _j3_feed_hits_by_rule(self, config):
        """What this employee's connected-system data delivers, per component.

        JOURNEY J3 S4 — the batch-free half of the connector story.

        The blob is built exactly the way the import batch builds it
        (`action_load_from_data_store`): the connector's `hr.api.data.store` rows
        for this employee, `data_type` in employee/salary, merged through
        `get_mappable_data()` so a transformation rule's `computed_data` overrides
        the raw `extracted_data` of the same name. Rows are merged OLDEST FIRST so
        the newest version of a key wins, and `employee` is merged before `salary`
        so compensation beats master data where they collide — the same precedence
        the batch loader applies by its `employee_external_id, data_type` ordering.

        Preference, in order: `state='extracted'` rows (ready for mapping) if there
        are any, else whatever is there apart from `archived`/`error`. A `consumed`
        row is data an import batch has already used — still true, still readable,
        and refusing it would mean a live payrun stopped working the moment
        somebody ran an import.

        Then `_feed_values_for` — the SAME function the import pre-pass calls —
        applies the wires, their transforms and J3's empty-value guard. There is no
        second implementation of "what did the feed say" anywhere in this codebase,
        which is the whole point of the helper existing.

        Returns `{rule_id: {'value', 'key', 'kind'}}`; `{}` on any absence, and it
        never raises: a payslip must compute even when the integration layer is
        misconfigured, missing or mid-migration.
        """
        self.ensure_one()
        if not (config and config.connector_id and self.employee_id):
            return {}
        Store = self.env.get('hr.api.data.store')
        FieldMapping = self.env.get('hr.integration.field.mapping')
        if Store is None or FieldMapping is None:
            return {}
        try:
            connector = config.connector_id.sudo()
            mappings = connector._sync_mapping_ids()
            if not mappings:
                return {}
            base = [('connector_id', '=', connector.id),
                    ('employee_id', '=', self.employee_id.id),
                    ('data_type', 'in', ['employee', 'salary'])]
            rows = Store.sudo().search(
                base + [('state', '=', 'extracted')],
                order='data_type asc, version asc, id asc')
            if not rows:
                rows = Store.sudo().search(
                    base + [('state', 'not in', ('archived', 'error'))],
                    order='data_type asc, version asc, id asc')
            if not rows:
                return {}
            blob = {}
            for row in rows:
                data = row.get_mappable_data()
                if isinstance(data, dict):
                    blob.update(data)
            computed = FieldMapping._computed_output_keys(connector)
            out = {}
            for hit in FieldMapping._feed_values_for(mappings, blob):
                out[hit['rule'].id] = {
                    'value': hit['value'], 'key': hit['key'],
                    'kind': 'rule' if hit['key'] in computed else 'feed',
                }
            return out
        except Exception:       # noqa: BLE001
            _logger.warning(
                "J3 S4: could not read connected-system data for payslip %s",
                self.id, exc_info=True)
            return {}

    def _get_formula_input_values(self, config, provenance=None):
        """
        Get input values for formula computation from various sources:
        - Contract data (wage, allowances)
        - Worked days
        - External integration (Zoho, etc.)

        SOURCING S1: ``provenance`` is an optional caller-supplied dict, filled with
        one `input_provenance.entry` per code. It is an OUT-PARAMETER rather than a
        second return value so that every existing caller — and any out-of-tree one
        — keeps today's signature and today's return exactly.

        This is the batch-free producer: the path taken when a payslip has no import
        line, so there is no spreadsheet and no feed to attribute anything to. Its
        sources are the contract, the worked-days lines, or nothing at all.
        """
        self.ensure_one()
        values = {}

        # Get input rules
        input_rules = config.rule_ids.filtered(lambda r: r.column_type == 'input')

        # JOURNEY J3 S4 — read the connected system's data ONCE, not per rule.
        # `_feed_hits_by_rule` returns {rule_id: hit} for the wires that actually
        # delivered something for THIS employee; empty dict when there is no
        # connector, no data, or nothing matched, in which case every branch below
        # behaves exactly as it did before this phase.
        feed_hits = self._j3_feed_hits_by_rule(config)

        for rule in input_rules:
            value = rule.default_value
            src, key, via = 'none', None, 'default'

            # Try to get from contract
            if self.contract_id:
                contract_mapping = {
                    'BASIC': 'wage',
                    'WAGE': 'wage',
                    'BASE': 'wage',
                }
                contract_field = contract_mapping.get(rule.code.upper())
                if contract_field and hasattr(self.contract_id, contract_field):
                    # Split out of the original one-liner so provenance can see WHICH
                    # branch of the `or` won. The resulting `value` is identical:
                    # `raw or value` is exactly what was here before.
                    raw_contract = getattr(self.contract_id, contract_field)
                    if raw_contract:
                        src, key, via = 'employee_field', contract_field, 'contract_field'
                    value = raw_contract or value

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
                    src, key, via = 'employee_field', wd_code, 'worked_days'

            # Get from integration connector (only confirmed 'active' mappings are
            # load-bearing — F114/D114.2).
            #
            # JOURNEY J3 S4 — this was `if mapping: # TODO … pass`. A live pay run
            # with no import batch could not read API data AT ALL: every wire on
            # the API mapping board was decorative on this path, and the only way
            # to get a feed value into a payslip was to route it through an import
            # batch. The component silently fell to its contract wage or its
            # default and the provenance said so, truthfully and unhelpfully.
            #
            # The wire wins over the contract/worked-days branches above for the
            # same reason it does inside the import resolver: it is the one thing
            # here a PERSON declared. And it wins only when it DELIVERED —
            # `_feed_values_for` applies J3's empty-value guard identically, so an
            # empty feed leaves the contract/worked-days/default tail exactly as it
            # was, which is what makes "keep the other source as a fallback" true
            # on this path as well as on the batch one.
            hit = feed_hits.get(rule.id)
            if hit:
                value = hit['value']
                src = 'rule' if hit['kind'] == 'rule' else 'feed'
                key, via = hit['key'], 'connector_mapping'

            values[rule.code] = value
            if provenance is not None:
                provenance[rule.code] = input_provenance.entry(src, key=key, via=via)

        # NOTE constants are deliberately NOT added here. On this path they never
        # enter `input_values` (the rule evaluator reads `constant_value` directly),
        # and the invariant this blob is verified against is that its key set EQUALS
        # `input_values`' key set — an invariant worth more than the extra entry,
        # because S4 derives "Fixed value" from the component's own type anyway.
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
                # NETROLE — same copy the batch producer makes, for the same
                # reason: the run's totals must count each dong once.
                'component_detail': bool(rule.net_role_detail),
            }
            lines_to_create.append(line_data)

        if lines_to_create:
            self.env['hr.payslip.line'].create(lines_to_create)

    # ==========================================
    # OVERRIDE STANDARD COMPUTE
    # ==========================================
    def _adopt_scheme_when_structureless(self):
        """Give a payslip with no salary structure the scheme that governs it.

        The standard engine computes a payslip by walking its structure's salary
        rules. With no `struct_id` there are no rules, so it walks nothing,
        writes nothing, and returns True — a payslip of zero lines and no
        complaint. On a tenant whose payroll is defined by a formula scheme
        rather than by salary structures that is EVERY payslip the Run Payroll
        wizard makes, and it is how ABM's June 2026 run reported 146 employees
        and a total net of 0.00.

        So: no structure and a scheme that resolves means the scheme is what
        this payslip is for. Nothing here touches a payslip that HAS a
        structure — that one has a real standard computation to do and keeps it.

        Returns the payslips promoted, for the caller's own bookkeeping.
        """
        promoted = self.browse()
        for payslip in self:
            if payslip.struct_id or payslip.calculation_method == 'formula':
                continue
            config = payslip._find_formula_config()
            if not config:
                continue
            payslip.write({
                'calculation_method': 'formula',
                'formula_config_id': config.id,
            })
            promoted |= payslip
        if promoted:
            _logger.info(
                "Computing %s payslip(s) with no salary structure through their "
                "payroll scheme instead of the structure engine, which has no "
                "rules to run for them.", len(promoted))
        return promoted

    def compute_sheet(self):
        """Override to support formula-based computation"""
        self._adopt_scheme_when_structureless()
        formula_payslips = self.filtered(
            lambda p: p.calculation_method == 'formula' and p.formula_config_id
        )
        standard_payslips = self - formula_payslips
        # What is left with neither a structure nor a scheme cannot compute at
        # all. Saying so is the point: it used to return True and write nothing.
        stranded = standard_payslips.filtered(lambda p: not p.struct_id)
        if stranded:
            raise UserError(_(
                "%(count)s payslip(s) cannot be computed: %(who)s has neither a "
                "salary structure on the contract nor a payroll scheme for this "
                "company. Assign one and run payroll again.",
                count=len(stranded),
                who=stranded[0].employee_id.display_name or _('this employee'),
            ))

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
                input_sources = {}
                input_values = batch._transform_data_to_formula_inputs(
                    import_line.get_raw_data(),
                    contract=payslip.contract_id,
                    employee=payslip.employee_id,
                    provenance=input_sources,
                    topup_data=import_line.get_topup_data(),
                )
                payslip.formula_input_values = json.dumps(input_values)
                payslip.formula_input_sources = json.dumps(input_sources)
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
        currency = (config.currency_id.symbol if (config and config.currency_id)
                    else (self.company_id.currency_id.symbol if self.company_id else ''))
        values_by_rule = {
            rule.id: dsal.get(rule.code) for rule in config.rule_ids
        } if config else {}
        rich_blocks = []
        if config:
            rich_blocks = [config.payslip_header_html or '', config.payslip_footer_html or '',
                           config.payslip_layout_html or '']
            rich_blocks.extend(section.note_html or '' for section in sections)
        embedded_value_ids = set()
        for block in rich_blocks:
            embedded_value_ids.update(
                config._payslip_content_rule_ids(block, amount_only=True))

        # Which config rules belong to each section; the rest (appears_on_payslip
        # but unsectioned) fall into a synthetic default section (C7).
        sectioned_codes = set()
        out_sections = []
        for s in sections:
            comps = [r for r in config.rule_ids
                     if r.payslip_identifier.id == s.id and r.appears_on_payslip
                     and r.id not in embedded_value_ids]
            comps.sort(key=lambda r: (r.payslip_sequence or 0, r.sequence))
            lines = []
            for r in comps:
                sectioned_codes.add(r.code)
                total = dsal.get(r.code, 0.0)
                if not _visible(r, total):
                    continue
                lines.append({'name': _line_name(r, r.code), 'total': total,
                              'is_deduction': total < 0})
            section_embedded_ids = config._payslip_content_rule_ids(
                s.note_html or '', amount_only=True)
            embedded_total = 0.0
            embedded_visible = False
            for rule in config.rule_ids.filtered(lambda r: r.id in section_embedded_ids):
                total = dsal.get(rule.code, 0.0)
                if _visible(rule, total):
                    embedded_visible = True
                    embedded_total += total
            if not lines and not embedded_visible and s.collapse_when_empty:
                continue
            title = (s.label_vi if (is_vi and s.label_vi) else False) or s.label or s.identifier or ''
            out_sections.append({
                'title': title,
                'color_hex': self._THEME_ACCENT_HEX.get(s.color_key or 'slate', '#64748B'),
                'note_html': config._render_payslip_content(
                    s.note_html or '', values_by_rule, currency),
                'lines': lines,
                'subtotal': sum(l['total'] for l in lines) + embedded_total,
            })

        # Default 'Payslip' section: config rules that appear on the payslip but
        # carry no section (never silently dropped).
        default_lines = []
        for r in config.rule_ids if config else []:
            if (r.code in sectioned_codes or not r.appears_on_payslip
                    or r.payslip_identifier or r.id in embedded_value_ids):
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
                'note_html': Markup(''),
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
        meta = {
            'employee_name': self.employee_id.name or '',
            'employee_id': (self.employee_id.employee_id
                            or self.employee_id.barcode or ''),
            'department': self.employee_id.department_id.name or '',
            'date_from': self.date_from.strftime('%d/%m/%Y') if self.date_from else '',
            'date_to': self.date_to.strftime('%d/%m/%Y') if self.date_to else '',
        }
        meta['period'] = ('From %s to %s' % (meta['date_from'], meta['date_to'])
                          if meta['date_from'] or meta['date_to'] else '')
        return {
            'accent_hex': self._THEME_ACCENT_HEX.get(accent_key, '#64748B'),
            'font_stack': self._THEME_FONT_STACK.get(font_key, self._THEME_FONT_STACK['system']),
            'show_logo': show_logo and bool(logo),
            'logo': logo,
            'header_html': config._render_payslip_content(
                config.payslip_header_html or '', values_by_rule, currency) if config else Markup(''),
            'footer_html': config._render_payslip_content(
                config.payslip_footer_html or '', values_by_rule, currency) if config else Markup(''),
            'layout_html': config._render_payslip_content(
                config.payslip_layout_html or '', values_by_rule, currency, meta) if config else Markup(''),
            'sections': out_sections,
            'net': net,
            'has_net': net is not None,
            'currency': currency,
        }
