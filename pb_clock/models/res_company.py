# -*- coding: utf-8 -*-
"""The three pairing settings (CLOCK ledger D9). Edited from the Time clocks
lens settings card — managers only — never from a native settings page."""

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    pb_clock_max_span_h = fields.Float(
        string='Longest possible work day', default=21.0,
        help='Every punch within this many hours of the first punch of a day '
             'belongs to that day, so a night shift stays one day.')
    pb_clock_double_tap_min = fields.Integer(
        string='Taps closer than this count once', default=2,
        help='Minutes. A second tap by the same person within this time is '
             'kept on record but counted once.')
    pb_clock_trust_direction = fields.Boolean(
        string='Trust the In / Out keys', default=False,
        help='Use the In and Out keys people press on the machine. Leave off '
             'when nobody presses them: the first punch of a day is then the '
             'start and the last punch is the end.')
