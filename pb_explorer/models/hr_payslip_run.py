# -*- coding: utf-8 -*-
"""Fact-staleness hook on the pay run (Phase N).

Hooked on ``write()``, deliberately NOT on the approval actions. The demo world
advances runs with a raw ``run.write({'state': ...})`` under sudo
(``pb_demo/models/demo_history.py:175``), which never passes through
``action_payslip_run_level2_done`` — an action-level hook would simply never
fire there, and the facts would go quietly stale on the exact database used for
every demo.

The flag is an OPTIMISATION, not the correctness guarantee: ``ensure_fresh()``
compares the source fingerprint on every read regardless of it, so facts stay
correct even if this hook is bypassed entirely.
"""

from odoo import models

# State changes move a run between approved and provisional; everything else
# about a run (name, dates) is denormalised onto the header too.
_FACT_FIELDS = {'state', 'name', 'date_start', 'date_end'}


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def write(self, vals):
        res = super().write(vals)
        if self.ids and _FACT_FIELDS.intersection(vals or {}):
            # sudo: marking a derived row dirty is bookkeeping, not a grant —
            # the reader still has to pass the Explorer gate to see anything.
            self.env['pb.fact.run'].sudo().search(
                [('run_id', 'in', self.ids)]).write({'dirty': True})
        return res

    def unlink(self):
        # ondelete='cascade' on pb.fact.run.run_id handles the rows; this keeps
        # the ORM cache honest when a run is deleted mid-session.
        self.env['pb.fact.run'].sudo().search(
            [('run_id', 'in', self.ids)]).unlink()
        return super().unlink()
