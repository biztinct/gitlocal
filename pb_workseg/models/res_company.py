# -*- coding: utf-8 -*-
"""The joiner-and-leaver switch, and why it ships OFF.

Paying a mid-month joiner for the days they actually worked is obviously
right. It is also a CHANGE to what an existing customer's payroll produces —
today those people are paid a full month, and every one of them would be paid
less from the next run. That is not a decision a software upgrade gets to make
on somebody's behalf.

So it is a switch, per company, off, with a sentence beside it saying exactly
what turning it on does and when.
"""

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    prorate_joiners_leavers = fields.Boolean(
        string='Pay joiners and leavers by the day', default=False,
        tracking=True,
        help="Turns on day-based pay for people who start or leave part-way "
             "through a month. Payslips for those people will change from the "
             "next pay run.")
