# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WfpBudgetGuardrail(models.Model):
    """Budget guardrails — configurable rules that enforce governance.
    
    Each guardrail defines a constraint (max increase %, budget cap, 
    compa-ratio bounds) and applies to a scope (company-wide, department,
    or grade). Violations are flagged as warnings or hard blocks.
    """
    _name = 'wfp.budget.guardrail'
    _description = 'Budget Guardrail Rule'
    _order = 'sequence, id'

    name = fields.Char(
        string='Rule Name',
        required=True,
        help="e.g. 'Max Increase Cap', 'Department Budget Limit'",
    )
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # Rule type
    rule_type = fields.Selection([
        ('max_increase_pct', 'Max Increase %'),
        ('max_increase_amount', 'Max Increase Amount'),
        ('dept_budget_cap', 'Department Budget Cap'),
        ('compa_min', 'Minimum Compa Ratio'),
        ('compa_max', 'Maximum Compa Ratio'),
        ('total_budget_cap', 'Total Cycle Budget Cap'),
        ('min_rating_for_increase', 'Min Performance Rating for Increase'),
    ], string='Rule Type', required=True)

    # Scope
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        help="If set, rule only applies to this department.",
    )
    grade_id = fields.Many2one(
        'wfp.pay.grade',
        string='Pay Grade',
        help="If set, rule only applies to this grade.",
    )

    # Thresholds
    threshold_value = fields.Float(
        string='Threshold Value',
        help="The limit value (%, amount, or rating depending on rule type).",
    )
    threshold_amount = fields.Monetary(
        string='Amount Limit',
        help="For amount-based rules.",
    )

    # Enforcement
    enforcement = fields.Selection([
        ('warn', 'Warning (Yellow Badge)'),
        ('block', 'Block (Prevent Submission)'),
    ], string='Enforcement', default='warn', required=True)

    description = fields.Text(
        string='Rule Description',
        help="Detailed explanation shown to managers when violated.",
    )

    @api.model
    def check_recommendation(self, recommendation):
        """Check a single recommendation against all active guardrails.
        
        Returns list of violations: [{'rule': name, 'message': str, 'level': 'warn'|'block'}]
        """
        violations = []
        guardrails = self.search([
            ('active', '=', True),
            ('company_id', '=', recommendation.cycle_id.company_id.id),
        ])

        for rule in guardrails:
            # Check scope
            if rule.department_id and rule.department_id != recommendation.department_id:
                continue
            if rule.grade_id and recommendation.contract_id:
                if rule.grade_id != recommendation.contract_id.grade_id:
                    continue

            violation = rule._evaluate(recommendation)
            if violation:
                violations.append(violation)

        return violations

    def _evaluate(self, rec):
        """Evaluate a single guardrail against a recommendation."""
        self.ensure_one()

        if self.rule_type == 'max_increase_pct':
            if rec.recommended_pct > self.threshold_value:
                return {
                    'rule': self.name,
                    'level': self.enforcement,
                    'message': _(
                        'Increase of %.1f%% exceeds maximum %.1f%%'
                    ) % (rec.recommended_pct, self.threshold_value),
                }

        elif self.rule_type == 'max_increase_amount':
            if rec.recommended_increase > self.threshold_amount:
                return {
                    'rule': self.name,
                    'level': self.enforcement,
                    'message': _(
                        'Increase amount exceeds limit of %s'
                    ) % self.threshold_amount,
                }

        elif self.rule_type == 'dept_budget_cap':
            # Check total allocated to this department
            dept_total = sum(
                rec.cycle_id.recommendation_ids.filtered(
                    lambda r: r.department_id == rec.department_id
                ).mapped('recommended_increase')
            )
            if dept_total > self.threshold_amount:
                return {
                    'rule': self.name,
                    'level': self.enforcement,
                    'message': _(
                        'Department total %s exceeds budget cap %s'
                    ) % (dept_total, self.threshold_amount),
                }

        elif self.rule_type == 'compa_min':
            compa = rec.contract_id.compa_ratio if rec.contract_id else 0
            if compa and compa < self.threshold_value:
                return {
                    'rule': self.name,
                    'level': 'warn',
                    'message': _(
                        'Compa ratio %.2f is below minimum %.2f'
                    ) % (compa, self.threshold_value),
                }

        elif self.rule_type == 'compa_max':
            compa = rec.contract_id.compa_ratio if rec.contract_id else 0
            if compa and compa > self.threshold_value:
                return {
                    'rule': self.name,
                    'level': self.enforcement,
                    'message': _(
                        'Compa ratio %.2f exceeds maximum %.2f'
                    ) % (compa, self.threshold_value),
                }

        elif self.rule_type == 'total_budget_cap':
            total = sum(
                rec.cycle_id.recommendation_ids.mapped('recommended_increase')
            )
            if total > self.threshold_amount:
                return {
                    'rule': self.name,
                    'level': self.enforcement,
                    'message': _(
                        'Cycle total %s exceeds budget cap %s'
                    ) % (total, self.threshold_amount),
                }

        elif self.rule_type == 'min_rating_for_increase':
            rating = int(rec.employee_id.wfp_performance_rating or '0')
            if rec.recommended_increase > 0 and rating < int(self.threshold_value):
                return {
                    'rule': self.name,
                    'level': self.enforcement,
                    'message': _(
                        'Performance rating %d is below minimum %d for an increase'
                    ) % (rating, int(self.threshold_value)),
                }

        return None
