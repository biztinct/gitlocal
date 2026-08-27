# -*- coding: utf-8 -*-
"""The one door into the Source Atlas.

An ``ir.actions.client`` record carries no record context of its own, and the
Atlas is always about ONE run. Returning the action from a button on the run is
how the run id reaches the cockpit without a context-passing dance that breaks
the moment the board opens it instead of the form.
"""

from odoo import _, models


class HrPayslipRunSourceAtlas(models.Model):
    _inherit = 'hr.payslip.run'

    def action_open_source_atlas(self):
        """Open the Source Atlas on this pay run."""
        self.ensure_one()
        self.env['pb.source.atlas']._atlas_gate()
        return {
            'type': 'ir.actions.client',
            'tag': 'pb_source_atlas_cockpit',
            'name': _('Where the numbers come from'),
            'params': {'run_id': self.id, 'run_name': self.name or ''},
            'context': dict(self.env.context, active_id=self.id,
                            active_model='hr.payslip.run'),
        }
