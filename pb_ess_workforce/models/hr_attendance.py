# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""TIERS T3b — a punch made from My Payobook says so.

The ``pb_entry_source`` rail (pb_hr_workforce's ``grid``, extended by
pb_attendance_flow with ``correction`` / ``import``) gains ``portal``: a row
created by the Clock page (`/my/work/clock`, ``pb.ess.workforce.clock_toggle``).

A ``'portal'`` row is NOT a device punch. ``_is_device_row`` (pb_attendance_flow)
reads a BLANK source as "raw device/kiosk punch", and only those are protected by
the delete guard; a portal row carries a source, so HR can remove a mistaken
portal punch the same way it removes a grid row — the employee's own tap is not
evidence from a device, it is a statement the employee can also ask to have fixed.
The week grid treats it like any other non-grid row (read-only in the grid, edited
on the attendance form).
"""

from odoo import fields, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # The exact shape pb_attendance_flow uses (`hr_attendance.py:33-35`): a
    # plain optional Selection with no base default can only honour 'set null'.
    # The label is neutral on purpose (white-label tenants see it in the
    # backend): never a product name.
    pb_entry_source = fields.Selection(
        selection_add=[('portal', 'Self-service')],
        ondelete={'portal': 'set null'})
