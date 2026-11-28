# -*- coding: utf-8 -*-
from odoo import fields, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # 'set default' is safe: the base in_mode/out_mode both define default='manual'
    # (C9 — 'set default' only asserts when the base field has no default). Safety
    # rail 6: without an ondelete policy the module becomes un-uninstallable.
    in_mode = fields.Selection(
        selection_add=[('gps', 'GPS')], ondelete={'gps': 'set default'})
    out_mode = fields.Selection(
        selection_add=[('gps', 'GPS')], ondelete={'gps': 'set default'})

    pb_selfie_attachment_id = fields.Many2one(
        'ir.attachment', string='Check-in Selfie', readonly=True,
        help='Optional photo evidence captured at driver check-in. '
             'Follows this attendance record\'s access rules (privacy).')
