# -*- coding: utf-8 -*-
"""One computed flag on `res.users`, and the reason it has to exist.

`pb_pip.manager_sees_own` is a SWITCH: on, a line manager can read the one
request they raised; off, they cannot. The obvious way to build that is a record
rule whose domain is `[('requested_by_user_id','=',user.id)]` plus an
`active` flag on the rule that something toggles when the parameter changes.

That way has a fault line in it. The parameter and the rule are two facts about
the same decision, and they drift the first time somebody sets the parameter by
hand (which is exactly what an administrator does) — leaving a switch that says
"off" over a rule that is still granting the access. A visibility switch that
lies is worse than no switch.

So the rule reads the switch DIRECTLY, through this field:

    ['&', ('requested_by_user_id', '=', user.id),
          ('id', '!=', 0 if user.pip_manager_sees_own else -1)]

is the shape it wants, and the shorter version the rule actually uses is

    [('requested_by_user_id', '=', user.id if user.pip_manager_sees_own
                                   else -1)]

— a domain that matches nothing when the switch is off, because no record has
a `requested_by_user_id` of -1. There is one source of truth, no sync job, and
no state to get out of step.

NOT STORED, deliberately: a stored copy would be the drift again, one table
further along. The read is a single indexed lookup on `ir_config_parameter`
behind `sudo()`, evaluated when a rule domain is built, which for this model is
a low-volume path.
"""

from odoo import api, fields, models

from .pip_common import P_MANAGER_SEES_OWN, flag


class ResUsers(models.Model):
    _inherit = 'res.users'

    pip_manager_sees_own = fields.Boolean(
        compute='_compute_pip_manager_sees_own',
        string='Can see the improvement plan they asked for',
        help='Read from the pb_pip.manager_sees_own setting. It exists so '
             'that the record rule granting a manager sight of their own '
             'request has a single source of truth.')

    @api.depends_context('uid')
    def _compute_pip_manager_sees_own(self):
        # One read for the whole recordset — the answer is a company-wide
        # setting, not a per-user one, and computing it per row would turn a
        # rule evaluation over a list of users into a query each.
        on = flag(self.env, P_MANAGER_SEES_OWN)
        for rec in self:
            rec.pip_manager_sees_own = on
