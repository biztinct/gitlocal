# -*- coding: utf-8 -*-
"""Contract components that can hold TEXT as well as an amount.

`hr.contract.advantage` was built for money: one Float per line, a bound check that
refuses anything outside the template's window. But the red-header convention in the
source workbooks marks "this belongs on the contract", not "this is a number", and
operators use it for job grade, cost centre, a contract reference — values that are
text and that a Float silently flattens to 0.0.

WHY THIS LIVES HERE AND NOT IN `om_hr_payroll` (CR-A3). The models being extended are
om's, and editing om would mean `-u om_hr_payroll` on four production databases —
which re-validates every module that depends on it, a cascade this codebase has been
bitten by before (CR1). An `_inherit` from this module adds the same columns with a
blast radius of one module.

WHAT IS NOT CHANGED. `amount` still exists, still means what it meant, and every
existing template stays `value_type = 'amount'` — a template's type is never flipped
automatically, because flipping it would reinterpret every historic line under it.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrContractAdvantageTemplate(models.Model):
    _inherit = 'hr.contract.advantage.template'

    value_type = fields.Selection([
        ('amount', 'Amount'),
        ('text', 'Text'),
    ], string='Value Type', default='amount', required=True,
        help="Whether this component holds a monetary amount or a piece of text.")


class HrContractAdvantage(models.Model):
    _inherit = 'hr.contract.advantage'

    value_type = fields.Selection(
        related='advantage_template_id.value_type',
        string='Value Type',
        readonly=True,
    )

    text_value = fields.Char(
        string='Text Value',
        help="Value for components that hold text instead of an amount.",
    )

    @api.constrains('advantage_template_id', 'amount')
    def _check_bound_limits(self):
        """Same window check as before, with one exception: a text-typed component has
        no amount to police, and its `amount` stays 0.0 forever. Overriding by name
        replaces the base constraint rather than adding a second one, so the original
        logic below is a faithful re-statement — a text line must not be rejected for
        an amount it was never going to carry."""
        for record in self:
            if record.value_type == 'text':
                continue
            if record.amount and record.amount != 0.00 and not (
                    record.advantage_upper_bound == 0 and record.advantage_lower_bound == 0):
                if record.amount > record.advantage_upper_bound:
                    raise ValidationError(
                        _("Component amount can't be greater than upper bound limit for %s")
                        % (record.advantage_template_id.name or '')
                    )
                elif record.amount < record.advantage_lower_bound:
                    raise ValidationError(
                        _("Component amount can't be less than lower bound limit for %s")
                        % (record.advantage_template_id.name or '')
                    )
