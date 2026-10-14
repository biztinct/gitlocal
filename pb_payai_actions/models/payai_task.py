# -*- coding: utf-8 -*-
"""`payai.task` — one row per thing a person asked PayAI to DO.

Refusals are rows too: the audit must show the asks that were refused, not
only the ones that ran.

WRITTEN BY THE SERVER ONLY. People hold READ on their own rows (record rule)
and payroll managers read their companies' rows; nobody holds create/write by
ACL, so an RPC client cannot forge or edit an audit row. The runner writes
them with `sudo()` — bookkeeping, not an Action: every Action itself runs as
the asking person (PA-R2).
"""
from datetime import timedelta

from odoo import api, fields, models

#: A plan / question is good for ten minutes, then it must be asked again.
TASK_TTL = timedelta(minutes=10)


class PayaiTask(models.Model):
    _name = 'payai.task'
    _description = 'PayAI request'
    _order = 'create_date desc, id desc'
    _rec_name = 'action_title'

    user_id = fields.Many2one('res.users', string='Asked by', required=True,
                              index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True, index=True)
    session_id = fields.Many2one('payroll.ai.conversation',
                                 string='Conversation', ondelete='set null')
    utterance = fields.Text(string='What was asked',
                            help="The person's words, with names taken out.")
    action_key = fields.Char(string='Action', required=True)
    action_title = fields.Char(string='Request')
    tier = fields.Selection([
        ('look', 'Look'), ('prepare', 'Prepare'),
        ('decide', 'Decide'), ('never', 'Never'),
    ], string='Kind', required=True, default='look')
    params_json = fields.Text(string='Details understood')
    plan_json = fields.Text(string='Card shown')
    state = fields.Selection([
        ('planned', 'Planned'),
        ('clarify', 'Waiting for a choice'),
        ('confirmed', 'Confirmed'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Did not work'),
        ('refused', 'Refused'),
        ('undone', 'Undone'),
        # P3-W6: plain words in the Audit console's "Asked PayAI: … — <status>".
        # Only a plan or question left past its ten minutes.
        ('expired', 'Not answered in time'),
        ('cancelled', 'Cancelled'),
        # FIX-1 (P3 wf-10): closed for a reason other than time — a newer
        # request took its place, or things changed under it at Do it and it
        # was planned again (the new task carries the fresh card).
        ('replaced', 'Replaced by a newer request'),
        ('replanned', 'Changed before it was done'),
    ], string='Status', required=True, default='planned', index=True)
    confirm_kind = fields.Selection([
        ('none', 'Not needed'), ('tap', 'Tap'), ('typed', 'Typed word'),
        ('voice', 'Spoken'),
    ], string='Confirmed by', default='none')
    confirmed_at = fields.Datetime(string='Confirmed at')
    expires_at = fields.Datetime(string='Good until')
    result_json = fields.Text(string='Result')
    undo_until = fields.Datetime(string='Can be undone until')
    error = fields.Text(string='Why it stopped')

    _user_create_idx = models.Index('(user_id, create_date)')

    @api.model
    def _ttl(self):
        return TASK_TTL

    def is_expired(self):
        self.ensure_one()
        return bool(self.expires_at and self.expires_at < fields.Datetime.now())
