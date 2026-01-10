# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrPayrollCycleComponentMapping(models.Model):
    _name = 'hr.payroll.cycle.component.mapping'
    _description = 'Mid-Cycle to End-Cycle Component Mapping'
    _order = 'mid_cycle_config_id, end_cycle_config_id, id'

    mid_cycle_config_id = fields.Many2one(
        'hr.formula.config',
        string='Mid-Cycle Configuration',
        required=True,
        domain="[('cycle_type', '=', 'mid_cycle')]",
        ondelete='cascade'
    )
    end_cycle_config_id = fields.Many2one(
        'hr.formula.config',
        string='End-Cycle Configuration',
        required=True,
        domain="[('cycle_type', '=', 'end_cycle')]",
        ondelete='cascade'
    )
    mid_component_id = fields.Many2one(
        'hr.formula.rule',
        string='Mid-Cycle Component',
        required=True,
        domain="[('config_id', '=', mid_cycle_config_id)]",
        ondelete='restrict'
    )
    end_component_id = fields.Many2one(
        'hr.formula.rule',
        string='End-Cycle Component',
        required=True,
        domain="[('config_id', '=', end_cycle_config_id)]",
        ondelete='restrict'
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'cycle_component_unique_pair',
            'unique(mid_cycle_config_id, end_cycle_config_id, mid_component_id, end_component_id)',
            'This mid-cycle to end-cycle component mapping already exists.'
        ),
        (
            'cycle_component_unique_mid',
            'unique(mid_cycle_config_id, end_cycle_config_id, mid_component_id)',
            'Each mid-cycle component can map to only one end-cycle component.'
        ),
        (
            'cycle_component_unique_end',
            'unique(mid_cycle_config_id, end_cycle_config_id, end_component_id)',
            'Each end-cycle component can be mapped from only one mid-cycle component.'
        ),
    ]

    @api.constrains('mid_cycle_config_id', 'end_cycle_config_id')
    def _check_cycle_types(self):
        for record in self:
            if record.mid_cycle_config_id.cycle_type != 'mid_cycle':
                raise ValidationError(_("Mid-Cycle Configuration must have cycle type Mid-Cycle."))
            if record.end_cycle_config_id.cycle_type != 'end_cycle':
                raise ValidationError(_("End-Cycle Configuration must have cycle type End-Cycle."))
