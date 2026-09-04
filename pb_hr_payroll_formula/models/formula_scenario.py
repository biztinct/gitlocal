# -*- coding: utf-8 -*-
"""Scenario columns (F14).

A *scenario* is a what-if overlay on a single component: a draft Excel formula
for one `hr.formula.rule` that is evaluated side-by-side with the live formula
(via F8's `_evaluate_config_overlay`) WITHOUT ever writing the rule. The user
promotes it (writes the draft into the real rule, versioned) or discards it.

Design decisions honoured here:
  D14.1 — a scenario NEVER touches `hr.formula.rule` until it is promoted; its
          value is computed by the F8 overlay, so no persistence of the draft
          leaks into the live config.
  D14.2 — scenarios persist (survive reload) as their own records; the grid
          renders them as ghost column pairs next to the base component.
"""
from odoo import _, api, fields, models

# a small stable palette so two scenarios on the same column read differently
_SCENARIO_COLORS = ['violet', 'teal', 'amber', 'rose', 'cyan']


class HrFormulaScenario(models.Model):
    _name = 'hr.formula.scenario'
    _description = 'Formula Scenario (what-if overlay on one component)'
    _order = 'rule_id, sequence, id'

    name = fields.Char(required=True, default=lambda s: _('Scenario'))
    config_id = fields.Many2one(
        'hr.formula.config', string='Configuration', required=True,
        ondelete='cascade', index=True)
    rule_id = fields.Many2one(
        'hr.formula.rule', string='Base component', required=True,
        ondelete='cascade', index=True)
    override_formula = fields.Text(
        string='Draft formula',
        help="The what-if Excel formula. Evaluated as an overlay; never written "
             "to the base rule until the scenario is promoted.")
    sequence = fields.Integer(default=10)
    color_key = fields.Char(default='violet')
    user_id = fields.Many2one('res.users', default=lambda s: s.env.user, readonly=True)

    @api.model
    def next_color(self, rule_id):
        """Pick a palette colour that the rule's existing scenarios aren't using."""
        used = self.search([('rule_id', '=', int(rule_id))]).mapped('color_key')
        for c in _SCENARIO_COLORS:
            if c not in used:
                return c
        return _SCENARIO_COLORS[len(used) % len(_SCENARIO_COLORS)]
