# -*- coding: utf-8 -*-
"""The one field this module puts on a company — and the one it deliberately
does not.

`pb_group_id` is the whole of membership. It is a plain Many2one with
`ondelete='set null'`, so removing a group leaves its companies exactly as they
were rather than taking them with it.

WHAT IS NOT HERE, ON PURPOSE
----------------------------
`presentation_currency_id`. A demo module defined that column on `res.company`
long before there was a group record to hold the decision, and on the databases
that have it the column already holds what an administrator set. Defining it a
second time here would mean either two answers to one question or editing a
demo module for the sake of a group screen. So `pb.fx.presentation_currency()`
PROBES for it — the group's choice first, that column second, the company's own
money last — and this module works identically on a database that has never
heard of it.

And `parent_id` is never written. Ruling G1: on Odoo 19 a branch copies its
root's currency and shows it read-only, so the branch tree cannot express a
multi-currency group. It stays exactly as the customer left it.
"""

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    pb_group_id = fields.Many2one(
        'pb.group', string='Group', index=True, ondelete='set null',
        help="The group of companies this one belongs to.")
