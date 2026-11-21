# -*- coding: utf-8 -*-
"""P2 — a pay run says when PayAI prepared it.

`pb_prepared_via` is written once, by the runner after the run PayAI drove is
finished (as the person; never sudo). The Runs board's history then reads
"Prepared by <name> through PayAI" instead of "Prepared by <name>".
"""
from odoo import api, fields, models


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    pb_prepared_via = fields.Selection(
        [('screen', 'The screen'), ('payai', 'PayAI')],
        string='Prepared through', copy=False,
        help="Where this run was prepared: on the Run payroll screen, or by "
             "PayAI after the person confirmed the plan.")


class PbPayruns(models.AbstractModel):
    _inherit = 'pb.payruns'

    @api.model
    def _history(self, run, approval, delivery):
        ev = super()._history(run, approval, delivery)
        try:
            if ev and run.pb_prepared_via == 'payai':
                who = run.pb_prepared_uid.name or run.create_uid.name or ''
                ev[0] = [self.env._("Prepared by %s through PayAI", who) if who
                         else self.env._("Prepared through PayAI"), ev[0][1]]
        except Exception:                               # noqa: BLE001
            pass                                        # a story never blanks the board
        return ev
