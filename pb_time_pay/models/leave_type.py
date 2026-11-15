# Part of Payobook. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HrLeaveTypeTimePay(models.Model):
    _inherit = 'hr.leave.type'

    # Default False, never required: other builders create kinds of leave
    # without knowing this field (S5 shared-seam rule).
    pb_toil_kind = fields.Boolean(
        string='Time off in lieu', default=False, copy=False,
        help='The kind of leave that overtime given as time off goes into. '
             'Made the first time a manager gives time off; one per company.')
