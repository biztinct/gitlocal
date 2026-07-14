# -*- coding: utf-8 -*-
"""W95 — Component budgets (WP-H, D-H1).

A *budget* is a per-component target authored for a formula config: one amount
per component code. It is the synthetic "side A" of a budget-vs-actual variance
folded through the SAME period-comparison transient (see
``formula_period_comparison.py`` — budget mode extends that flow, it does NOT
fork it). This module is the entire engine footprint of W95: two persistent
models + access rows. All CRUD RPCs and the variance UI live in
``pb_formula_studio`` (C1 boundary).

Budget lines key strictly by CODE (the same key the fold uses via
``_slip_computed``) — a line whose code no longer exists in the config is kept
and surfaced as an orphan, never silently matched by name (C7).
"""
from odoo import fields, models


class HrFormulaBudget(models.Model):
    _name = 'hr.formula.budget'
    _description = 'Formula Component Budget'
    _order = 'name, id'

    name = fields.Char(required=True)
    config_id = fields.Many2one(
        'hr.formula.config', required=True, ondelete='cascade', index=True,
        help="The configuration this budget targets. Budget lines key by the "
             "config's component codes.")
    period_label = fields.Char(
        help="Free-text label for the period this budget represents "
             "(e.g. 'FY2026 Q3', 'May target').")
    note = fields.Char(help="One-line note shown beside the budget in the picker.")
    active = fields.Boolean(default=True)
    line_ids = fields.One2many('hr.formula.budget.line', 'budget_id', string='Lines')
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company)


class HrFormulaBudgetLine(models.Model):
    _name = 'hr.formula.budget.line'
    _description = 'Formula Component Budget Line'
    _order = 'code, id'

    budget_id = fields.Many2one(
        'hr.formula.budget', required=True, ondelete='cascade', index=True)
    code = fields.Char(
        required=True,
        help="Component code this amount budgets. Matched against the config's "
             "component codes at variance time.")
    amount = fields.Float(default=0.0)

    # Odoo 19: legacy _sql_constraints is silently IGNORED (model_classes.py
    # logs "no longer supported") — constraints must be models.Constraint
    # class attributes or they never reach the database (ledger C9).
    _budget_code_uniq = models.Constraint(
        'unique(budget_id, code)',
        'A budget can carry only one line per component code.')
