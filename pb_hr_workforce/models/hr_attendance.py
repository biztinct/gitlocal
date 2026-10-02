# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Marks attendance rows SYNTHESIZED by the Weekly Entry grid. Only 'grid'
    # rows may be adjusted/unlinked by the grid — real device/kiosk punches
    # (blank source) are never mutated or destroyed (Phase-B safety rail 2).
    pb_entry_source = fields.Selection(
        [('grid', 'Week grid')],
        string='Entry Source', index=True,
        help='Set when a record is created by the Weekly Entry grid; blank for '
             'device/kiosk/manual punches which the grid must never overwrite.')
