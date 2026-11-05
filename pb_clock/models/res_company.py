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
    pb_clock_allow_plain = fields.Boolean(
        string='Allow a plain connection', default=False,
        help='Lets an older machine send over a plain web connection when it '
             'cannot make a secure one. Only the number, the time and the '
             'machine’s serial travel.')

    pb_clock_alert_mail = fields.Boolean(
        string='Email the attendance managers', default=True,
        help='A summary at 08:00 when something needs attention, and a note '
             'when a machine stops calling in on a working day.')

    # ---- CLOCK-3: the watcher's own memory (never edited by a person)
    pb_clock_backlog_since = fields.Datetime(
        string='Pairing behind since', readonly=True, copy=False,
        help='When more than 20,000 punches first waited to be paired. Cleared '
             'when fewer than 1,000 wait.')
    pb_clock_digest_sent_on = fields.Date(
        string='Time clock summary sent on', readonly=True, copy=False)
    pb_clock_last_recheck_at = fields.Datetime(
        string='Last full re-check', readonly=True, copy=False,
        help='When the nightly re-check last rebuilt the last 35 days of '
             'time-clock days from their punches.')
    pb_clock_last_recheck_fixed = fields.Integer(
        string='Days the last re-check changed', readonly=True, copy=False)
    pb_clock_recheck_on = fields.Date(
        string='Re-checked on (local day)', readonly=True, copy=False)
