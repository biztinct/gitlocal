# -*- coding: utf-8 -*-
"""The `device` entry source (CLOCK ledger §1, design §3.1).

Before CLOCK-1 a BLANK `pb_entry_source` meant a device/kiosk punch. The time
clock pairing now writes the explicit value `device`; blank keeps its old
meaning, so `_is_device_row` answers yes for either. Application payroll's
mixed-source check and the packet snapshot already read
`pb_entry_source or 'device'`, so both values land in the same bucket there.
"""

from odoo import fields, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    pb_entry_source = fields.Selection(
        selection_add=[('device', 'Time clock')],
        ondelete={'device': 'set null'})

    def _is_device_row(self):
        """A raw device / kiosk punch: blank source, or one the time clock
        pairing wrote."""
        self.ensure_one()
        return not self.pb_entry_source or self.pb_entry_source == 'device'

    pb_clock_auto_closed = fields.Boolean(
        string='Check-out missing', readonly=True, copy=False, index=True,
        help='The time clock closed this day at its own check-in because the '
             'person punched again on a later day without a check-out here. '
             'Fix it with a correction.')
