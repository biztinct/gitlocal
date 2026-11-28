# -*- coding: utf-8 -*-
"""pb.clock.command — the command channel to a machine (CLOCK-2 §3.5, D13).

A machine polls `GET /iclock/getrequest` every few seconds. Up to three queued
commands are handed out per poll as `C:<id>:<command>` lines and marked
`sent`; the machine answers `POST /iclock/devicecmd` with `ID=<id>&Return=<rc>`
and the command is closed. A `sent` command with no answer after 10 minutes
is `failed` ("no answer").

Kinds:
  * set_time — `SET OPTIONS DateTime=<zk seconds>`, queued by the measured
    skew (never by a person).
  * resend   — `DATA QUERY ATTLOG StartTime=…\tEndTime=…` ("Resend punches
    since…"). When the machine refuses or does not answer, the fallback is
    queued: the punch stamp goes back to 0 and a `CHECK` makes the machine
    re-read its options, so it sends everything it holds again — repeats are
    kept once by the ledger.
  * check    — `CHECK`.
  * custom   — reserved; nothing in the product queues one.

Written only by the receiver and the lens facade, both sudo; officers may
read (the machine card shows the latest command), plain users may not.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

NO_ANSWER_AFTER = timedelta(minutes=10)
PER_POLL = 3

KINDS = [
    ('set_time', 'Set the clock'),
    ('resend', 'Resend punches'),
    ('check', 'Re-read settings'),
    ('custom', 'Other'),
]
STATES = [
    ('queued', 'Waiting for the machine'),
    ('sent', 'Sent'),
    ('done', 'Done'),
    ('failed', 'Failed'),
]


class PbClockCommand(models.Model):
    _name = 'pb.clock.command'
    _description = 'Command to an attendance machine'
    _order = 'id desc'

    device_id = fields.Many2one('pb.clock.device', string='Machine', required=True, index=True,
                                ondelete='cascade', readonly=True)
    company_id = fields.Many2one(related='device_id.company_id', store=True,
                                 index=True)
    command = fields.Char(string='Command', required=True, readonly=True)
    kind = fields.Selection(KINDS, string='What', required=True, default='custom', readonly=True)
    state = fields.Selection(STATES, string='Status', required=True, default='queued', index=True)
    return_code = fields.Char(string='Answer')
    queued_at = fields.Datetime(string='Asked', default=fields.Datetime.now, readonly=True)
    sent_at = fields.Datetime(string='Sent to the machine')
    done_at = fields.Datetime(string='Answered')
    note = fields.Char(string='Note')
    # what the command was about, kept for the plain sentence on the card
    skew_s = fields.Integer(string='Clock difference (seconds)')
    since = fields.Date(string='Resend from')

    # ------------------------------------------------------------ queue
    @api.model
    def _queue(self, device, kind, command, **extra):
        vals = dict(device_id=device.id, kind=kind, command=command,
                    state='queued', queued_at=fields.Datetime.now())
        vals.update(extra)
        return self.sudo().create(vals)

    @api.model
    def _queue_set_time(self, device, now=None):
        now = now or fields.Datetime.now()
        local = device._local_now(now)
        value = device.zk_encode(local)
        return self._queue(device, 'set_time', 'SET OPTIONS DateTime=%s' % value,
                           skew_s=device.clock_skew_s or 0)

    @api.model
    def _queue_resend(self, device, since, now=None):
        now = now or fields.Datetime.now()
        local_now = device._local_now(now)
        cmd = 'DATA QUERY ATTLOG StartTime=%s 00:00:00\tEndTime=%s' % (
            fields.Date.to_string(since), local_now.strftime('%Y-%m-%d %H:%M:%S'))
        return self._queue(device, 'resend', cmd, since=since)

    # ------------------------------------------------------------ channel
    @api.model
    def _hand_out(self, device, now=None):
        """The `getrequest` answer body for this machine: at most three queued
        commands, oldest first, marked sent."""
        now = now or fields.Datetime.now()
        self._sweep(device, now)
        todo = self.sudo().search([('device_id', '=', device.id),
                                   ('state', '=', 'queued')],
                                  order='id', limit=PER_POLL)
        if not todo:
            return ''
        todo.write({'state': 'sent', 'sent_at': now})
        return '\r\n'.join('C:%s:%s' % (c.id, c.command) for c in todo)

    @api.model
    def _close(self, device, cmd_id, return_code, now=None):
        """`devicecmd` result for one command id. Return >= 0 = done (ZK
        answers a count for some queries), negative = failed."""
        now = now or fields.Datetime.now()
        try:
            cid = int(str(cmd_id).strip())
        except (TypeError, ValueError):
            return False
        cmd = self.sudo().search([('id', '=', cid), ('device_id', '=', device.id)],
                                 limit=1)
        if not cmd or cmd.state in ('done', 'failed'):
            return False
        rc = str(return_code if return_code is not None else '').strip()
        try:
            ok = int(rc) >= 0
        except ValueError:
            ok = False
        cmd.write({'state': 'done' if ok else 'failed', 'return_code': rc or False,
                   'done_at': now,
                   'note': False if ok else _("The machine answered %s.") % (rc or '?')})
        if ok:
            cmd._after_done(now)
        else:
            cmd._after_failed(now)
        return True

    def _after_done(self, now):
        for cmd in self:
            if cmd.kind == 'set_time':
                # the clock is right now: start measuring afresh
                cmd.device_id.sudo().write({
                    'clock_corrected_at': now,
                    'clock_corrected_by_s': cmd.skew_s or 0,
                    'skew_samples': '[]', 'clock_skew_s': 0})

    def _after_failed(self, now):
        for cmd in self:
            if cmd.kind == 'resend':
                cmd._fallback_resend()

    def _fallback_resend(self):
        """The machine did not take DATA QUERY: punch stamp back to 0 and a
        CHECK — it then sends everything it holds again."""
        self.ensure_one()
        device = self.device_id.sudo()
        device.write({'attlog_stamp': '0'})
        self._queue(device, 'check', 'CHECK',
                    note=_("Asked the machine to send everything it holds again; "
                           "repeats are kept once."), since=self.since)
        note = (self.note or '').strip()
        extra = _("Trying another way: the machine will send everything again.")
        self.write({'note': ('%s %s' % (note, extra)).strip()[:250]})

    @api.model
    def _sweep(self, device=None, now=None):
        """`sent` for more than 10 minutes with no answer → failed."""
        now = now or fields.Datetime.now()
        dom = [('state', '=', 'sent'), ('sent_at', '<', now - NO_ANSWER_AFTER)]
        if device:
            dom.append(('device_id', '=', device.id))
        stale = self.sudo().search(dom, limit=200)
        for cmd in stale:
            cmd.write({'state': 'failed', 'done_at': now, 'note': _("No answer.")})
            cmd._after_failed(now)
        return len(stale)
