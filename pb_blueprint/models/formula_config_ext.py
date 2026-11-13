# -*- coding: utf-8 -*-
"""The return door from the Excel workbook review.

Choosing "Import Excel workbook" as the starting point creates an empty draft
and hands over to the existing multi-sheet review. When that review finishes it
has to come BACK to the guided setup, on the step after Start, with the
imported components in place — otherwise the person is dropped into a grid and
the journey they were half-way through simply vanishes.

The hand-back rides on one context flag the guided setup sets when it opens the
review. Without that flag nothing changes: the import behaves exactly as it
always has.
"""
import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class HrFormulaConfigBlueprintReturn(models.Model):
    _inherit = 'hr.formula.config'

    def studio_people_mapping_action(self, rules):
        """Send a workbook import that started in the guided setup back to it.

        Deliberately checked BEFORE calling super(): the parent only bounces to
        a board when the workbook produced people columns, and a purely
        financial workbook must still return to the journey.
        """
        self.ensure_one()
        if self.env.context.get('pb_blueprint_return'):
            blueprint = self.env['pb.formula.blueprint'].search(
                [('config_id', '=', self.id), ('state', '=', 'draft')], limit=1)
            if blueprint:
                blueprint.step = 'rules'
                signal = {'config_id': self.id}
                return {
                    'type': 'ir.actions.client',
                    'tag': 'pb_blueprint',
                    'name': _("New configuration"),
                    'target': 'current',
                    'params': dict(signal),
                    'context': dict(signal),
                }
        return super().studio_people_mapping_action(rules)
