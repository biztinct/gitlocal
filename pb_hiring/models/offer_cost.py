"""Read-only offer simulation using the existing payroll formula converter."""
import json
import math

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.addons.pb_hr_payroll_formula.formula_engine import FormulaEvaluator, excel_semantics
from .hiring_common import OFFER_PERIOD_MONTH, OFFER_PERIOD_YEAR


class OfferCostProfile(models.Model):
    _name = 'pb.hiring.cost.profile'
    _description = 'Country offer setup'
    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    country_id = fields.Many2one('res.country', required=True)
    config_id = fields.Many2one('hr.formula.config', string='Approved payroll calculation', required=True)
    gross_input_id = fields.Many2one('hr.formula.rule', string='Monthly offer input', required=True,
        domain="[('config_id', '=', config_id), ('column_type', '=', 'input')]")
    employer_rule_ids = fields.Many2many('hr.formula.rule', string='Monthly employer contribution outputs',
        domain="[('config_id', '=', config_id), ('column_type', '!=', 'input')]")
    defaults_json = fields.Text(string='Other calculation inputs (JSON)', default='{}',
        help='Explicit approved defaults for payroll inputs, such as working days or contribution class. Missing inputs stop the calculation.')
    effective_from = fields.Date(required=True)
    effective_to = fields.Date()
    letter_template_id = fields.Many2one('pb.letter.template', string='Country offer letter', domain="[('letter_type', '=', 'offer')]")
    company_signer_id = fields.Many2one('res.users', string='Company counter-signatory')
    active = fields.Boolean(default=True)

    @api.constrains('config_id','gross_input_id','employer_rule_ids','company_id','country_id','effective_from','effective_to','defaults_json')
    def _validate_profile(self):
        for rec in self:
            if rec.config_id.company_id != rec.company_id or rec.config_id.country_id != rec.country_id:
                raise ValidationError(_('The payroll calculation must belong to this company and country.'))
            if rec.gross_input_id.config_id != rec.config_id or rec.gross_input_id.column_type != 'input' or any(r.config_id != rec.config_id for r in rec.employer_rule_ids):
                raise ValidationError(_('Select inputs and outputs from this payroll calculation.'))
            if rec.effective_to and rec.effective_to < rec.effective_from:
                raise ValidationError(_('The effective end date must follow the start date.'))
            try:
                if not isinstance(json.loads(rec.defaults_json or '{}'), dict):
                    raise ValueError()
            except ValueError:
                raise ValidationError(_('Calculation inputs must be a JSON object.')) from None


class OfferCost(models.Model):
    _inherit = 'pb.hiring.offer'
    pb_cost_profile_id = fields.Many2one('pb.hiring.cost.profile', string='Country calculation', domain="[('company_id', '=', company_id)]")
    pb_cost_inputs = fields.Text(string='Additional calculation inputs (JSON)', default='{}')
    pb_cost_result = fields.Html(string='Employer-cost estimate', sanitize=True, readonly=True, copy=False, groups='pb_hiring.group_hiring_user')
    pb_cost_at = fields.Datetime(readonly=True, copy=False)

    def action_country_offer_setup(self):
        self._sign_gate()
        country = self.requisition_id.country_id or self.company_id.country_id
        profiles = self.env['pb.hiring.cost.profile'].search([('company_id', '=', self.company_id.id),
            ('country_id', '=', country.id), ('effective_from', '<=', self.start_date), '|',
            ('effective_to', '=', False), ('effective_to', '>=', self.start_date)])
        if len(profiles) != 1:
            raise UserError(_('Configure exactly one approved country offer setup for this start date.'))
        values = {'pb_cost_profile_id': profiles.id}
        if profiles.letter_template_id:
            values['letter_template_id'] = profiles.letter_template_id.id
        if profiles.company_signer_id:
            values['pb_company_signer_id'] = profiles.company_signer_id.id
        self.write(values)
        return True

    def action_calculate_employer_cost(self):
        self._sign_gate()
        profile = self.pb_cost_profile_id.sudo()
        country = self.requisition_id.country_id or self.company_id.country_id
        if not profile or profile.company_id != self.company_id or profile.country_id != country:
            raise UserError(_('Choose an approved calculation for this company and country.'))
        if not profile.active or profile.effective_from > self.start_date or (profile.effective_to and profile.effective_to < self.start_date):
            raise UserError(_('The country calculation is not effective on the offer start date.'))
        config = profile.config_id
        if config.currency_id != self.currency_id or not profile.employer_rule_ids:
            raise UserError(_('Match the offer currency and select the employer contribution outputs in country setup.'))
        try:
            inputs = dict(json.loads(profile.defaults_json or '{}'))
            extra = json.loads(self.pb_cost_inputs or '{}')
            if not isinstance(extra, dict):
                raise ValueError()
            inputs.update(extra)
        except (ValueError, TypeError):
            raise UserError(_('Additional calculation inputs must be a JSON object.')) from None
        cash_lines = self.line_ids.filtered(lambda ln: ln.kind != 'statutory')
        monthly = sum(ln.amount * OFFER_PERIOD_MONTH.get(ln.period, 1) for ln in cash_lines)
        annual = sum(ln.amount * OFFER_PERIOD_YEAR.get(ln.period, 12) for ln in cash_lines)
        inputs[profile.gross_input_id.code] = monthly
        rules = config.rule_ids
        missing = rules.filtered(lambda r: r.column_type == 'input' and r.code not in inputs)
        if missing:
            raise UserError(_('Supply these calculation inputs: %s', ', '.join(missing.mapped('code'))))
        # Use the same converter and Excel semantics as payroll, with strict
        # errors: a missing/failed contribution must never masquerade as zero.
        results = dict(inputs)
        column_map = {r.column_letter: r.code for r in rules if r.column_letter}
        try:
            for rule in FormulaEvaluator()._topological_sort(rules):
                if rule.column_type == 'constant':
                    results[rule.code] = rule.constant_value
                elif rule.column_type == 'formula':
                    if not rule.excel_formula:
                        raise ValueError('Missing formula')
                    expression = rule._convert_excel_to_python(rule.excel_formula, column_map)
                    excel_semantics.assert_safe_expression(expression)
                    context = {'__builtins__': {}, 'values': {k: excel_semantics.coerce_value(v) for k,v in results.items()},
                        'raw_values': dict(results), 'self': rule, 'math': math, 'sum': rule._sumlist,
                        'min': rule._minlist, 'max': rule._maxlist, 'abs': abs, 'round': round,
                        'pow': pow, 'all': all, 'any': any}
                    results[rule.code] = eval(expression, context)
                if rule.column_letter:
                    results[rule.column_letter] = results[rule.code]
            amounts = [(r.name, float(results[r.code])) for r in profile.employer_rule_ids]
            if any(not math.isfinite(v) or v < 0 for _,v in amounts):
                raise ValueError('Invalid employer amount')
        except Exception:
            raise UserError(_('The payroll calculation could not be evaluated. Have HR/Finance check the inputs and formulas; no cost estimate has been saved.')) from None
        employer = sum(v for _,v in amounts)
        money = lambda value: escape(self._money(value))
        rows = Markup('').join(Markup('<tr><td>%s</td><td>%s</td></tr>') % (escape(name), money(amount)) for name,amount in amounts)
        html = Markup('<p>Calculation: %s · Effective start: %s · Currency: %s</p><table class="table"><tr><td>Recurring monthly package (excluding statutory lines)</td><td>%s</td></tr>%s<tr><th>Total monthly employer cost</th><th>%s</th></tr><tr><th>First-year estimate</th><th>%s</th></tr></table><p>First year uses the offer’s annual package plus twelve months of employer contributions. This is an estimate, without partial-year proration. Existing statutory offer lines are excluded to avoid counting them twice.</p>') % (escape(profile.name), escape(str(self.start_date)), escape(self.currency_id.name), money(monthly), rows, money(monthly + employer), money(annual + 12*employer))
        self.write({'pb_cost_result': html, 'pb_cost_at': fields.Datetime.now()})
        return True

    def write(self, vals):
        if set(vals) & {'line_ids','start_date','currency_id','pb_cost_profile_id','pb_cost_inputs'}:
            vals = dict(vals, pb_cost_result=False, pb_cost_at=False)
        return super().write(vals)


class OfferCostLine(models.Model):
    _inherit = 'pb.hiring.offer.line'

    @api.model_create_multi
    def create(self, vals):
        self.env['pb.hiring.offer'].browse([v['offer_id'] for v in vals if v.get('offer_id')])._check_signing_edit()
        result = super().create(vals)
        result.offer_id.sudo().write({'pb_cost_result': False, 'pb_cost_at': False})
        return result

    def write(self, vals):
        self.offer_id._check_signing_edit()
        if vals.get('offer_id'):
            self.env['pb.hiring.offer'].browse(vals['offer_id'])._check_signing_edit()
        previous = self.offer_id
        result = super().write(vals)
        (previous | self.offer_id).sudo().write({'pb_cost_result': False, 'pb_cost_at': False})
        return result

    def unlink(self):
        self.offer_id._check_signing_edit()
        offers = self.offer_id
        result = super().unlink()
        offers.sudo().write({'pb_cost_result': False, 'pb_cost_at': False})
        return result
