# -*- coding: utf-8 -*-
# Mid→End mapping auto-suggestions (Feature 4a). Persistent and keyed by the
# config PAIR (not a transient wizard line — a persistent m2o to a TransientModel
# is forbidden), so a rejected suggestion survives a re-run and is not resurfaced
# (T4.2). The wizard displays them via a computed o2m over the config pair.

from odoo import fields, models


class HrPayrollCycleMappingSuggestion(models.Model):
    _name = 'hr.payroll.cycle.mapping.suggestion'
    _description = 'Mid-Cycle to End-Cycle Mapping Suggestion'
    _order = 'confidence desc, id'

    mid_cycle_config_id = fields.Many2one(
        'hr.formula.config', string='Mid-Cycle Configuration',
        required=True, ondelete='cascade', index=True)
    end_cycle_config_id = fields.Many2one(
        'hr.formula.config', string='End-Cycle Configuration',
        required=True, ondelete='cascade', index=True)

    mid_component_id = fields.Many2one(
        'hr.formula.rule', string='Mid-Cycle Component', required=True, ondelete='cascade')
    end_component_id = fields.Many2one(
        'hr.formula.rule', string='End-Cycle Component', required=True, ondelete='cascade')

    confidence = fields.Float(string='Confidence')
    match_reason = fields.Char(string='Why')
    state = fields.Selection([
        ('proposed', 'Proposed'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ], string='Status', default='proposed', index=True)

    # ---- accept / reject (T4.2) -------------------------------------------
    def action_accept(self):
        """Create the real mapping(s) and remove the suggestion — an accepted
        suggestion graduates to an actual mapping (visible under Open Mappings)."""
        Mapping = self.env['hr.payroll.cycle.component.mapping']
        for s in self:
            # respect the unique constraints: skip if either side is already mapped
            already = Mapping.search([
                ('mid_cycle_config_id', '=', s.mid_cycle_config_id.id),
                ('end_cycle_config_id', '=', s.end_cycle_config_id.id),
                '|', ('mid_component_id', '=', s.mid_component_id.id),
                     ('end_component_id', '=', s.end_component_id.id),
            ], limit=1)
            if not already:
                Mapping.create({
                    'mid_cycle_config_id': s.mid_cycle_config_id.id,
                    'end_cycle_config_id': s.end_cycle_config_id.id,
                    'mid_component_id': s.mid_component_id.id,
                    'end_component_id': s.end_component_id.id,
                })
        self.unlink()
        return True

    def action_reject(self):
        """Reject persists so a re-run of Suggest never resurfaces this pair."""
        self.write({'state': 'rejected'})
        return True
