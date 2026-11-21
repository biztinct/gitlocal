# -*- coding: utf-8 -*-
"""One computed flag on `res.users` that the GLOBAL document rule reads.

The documents vault lets every HR officer and payroll officer read every
document (ledger S9-F2). A finished conduct letter is filed there under this
module's own category, so this module adds a GLOBAL rule (ANDed with all the
vault's own rules) that hides that category from everybody who is not named
for conduct cases — except the person the letter is addressed to.

The rule reads this flag rather than a group id because a rule domain is
evaluated without `ref()`. Not stored: a stored copy would drift from the
group the moment somebody is named or un-named (the pb_pip lesson).
"""

from odoo import api, fields, models

from .conduct_common import GROUP_HEAD, GROUP_USER


class ResUsers(models.Model):
    _inherit = 'res.users'

    pb_conduct_reader = fields.Boolean(
        compute='_compute_pb_conduct_reader',
        string='Named for conduct cases',
        help='True for the people HR has named on the Access screen to see '
             'conduct cases. Read by the record rules.')

    @api.depends('group_ids')
    def _compute_pb_conduct_reader(self):
        for who in self:
            # `_has_group`, not `has_group`: the rule is also evaluated for
            # portal logins, and `has_group` refuses a non-internal caller.
            who.pb_conduct_reader = bool(
                who.id and (who._has_group(GROUP_USER)
                            or who._has_group(GROUP_HEAD)))
