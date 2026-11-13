# -*- coding: utf-8 -*-
"""The scheme a pay run was run FOR, written on the run itself.

WHY THE RUN AND NOT ONLY THE PAYSLIPS
-------------------------------------
Every payslip this phase creates carries its own `formula_config_id`, so the
scheme is never in doubt per person. But a run is the thing a person opens, and
"which scheme was this?" has until now been answered by reading a payslip out
of it and hoping the rest agree. Two consequences follow from writing it down:

  * `_find_formula_config` can ask the run what KIND of run this is, so a
    payslip added to a mid-month advance run resolves through the map's
    mid-month line rather than through the end-of-month one;
  * a run whose payslips disagree with its own scheme is a fact somebody can
    see, instead of a difference nobody can look for.

WHY THE FIELD LIVES HERE AND NOT IN THE PAY-RUN WIZARD
------------------------------------------------------
`pb_payrun_wizard` deliberately does not depend on the formula engine — it
still runs the salary-structure path on a database that has no schemes at all.
A `Many2one('hr.formula.config')` declared there would make that dependency
real. So the column belongs to this module, which already depends on both, and
the wizard writes it only when it finds it (`'pb_formula_config_id' in
Run._fields`).
"""

from odoo import fields, models


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    pb_formula_config_id = fields.Many2one(
        'hr.formula.config', string='Payroll scheme', index=True,
        ondelete='set null',
        help="The payroll scheme this run was run for. Set by the Run Payroll "
             "screen when a scheme was chosen there.")
