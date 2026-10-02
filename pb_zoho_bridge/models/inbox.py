# -*- coding: utf-8 -*-
"""Every record that ever arrived, and what Payobook did with it.

This model is doing two jobs at once and both of them matter.

It is the AUDIT TRAIL. When somebody asks "why does this person have a leaving
checklist" the answer has to be a row with a date, a payload and a sentence —
not a shrug. So a row is written for every record, including the ones that were
ignored, the ones that were duplicates and the ones that failed.

It is also the IDEMPOTENCY KEY. A webhook that gets no answer retries, and a
spreadsheet gets uploaded twice by two different people on the same afternoon.
`external_event_id` carries a database-level unique constraint, so the SECOND
arrival of the same event cannot create a second set of side effects even if two
requests race each other into the same second. Where the sender gives us no
event id of its own we derive a stable one by hashing the record — same payload,
same key, same refusal.
"""

import hashlib
import json

from odoo import api, fields, models, _

SOURCES = [
    ('webhook', 'Live push'),
    ('file', 'File upload'),
    ('manual', 'Entered by hand'),
]

STATES = [
    ('applied', 'Applied'),
    ('skipped', 'Skipped (already received)'),
    ('review', 'Needs a look'),
    ('error', 'Something went wrong'),
]


class PbZohoInbox(models.Model):
    _name = 'pb.zoho.inbox'
    _description = 'Arrival from the Connected System'
    _order = 'received_at desc, id desc'
    _rec_name = 'display_summary'

    external_event_id = fields.Char(
        string='Event reference', index=True, readonly=True, copy=False,
        help='What the connected system called this event, or a fingerprint of '
             'the record when it did not name one. The same reference is never '
             'processed twice.')
    zoho_record_id = fields.Char(string='Their record id', index=True, readonly=True)
    employee_number = fields.Char(string='Employee number', readonly=True)
    person_name = fields.Char(string='Name on the record', readonly=True)
    payload_json = fields.Text(string='What arrived', readonly=True)
    received_at = fields.Datetime(
        string='Received', readonly=True, index=True,
        default=lambda self: fields.Datetime.now())
    source = fields.Selection(
        SOURCES, string='Came in by', required=True, default='webhook',
        readonly=True)
    state = fields.Selection(
        STATES, string='Outcome', required=True, default='review', readonly=True,
        index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', readonly=True, ondelete='set null',
        index=True)
    case_id = fields.Many2one(
        'pb.journey.case', string='Journey started', readonly=True,
        ondelete='set null')
    rule_id = fields.Many2one(
        'pb.zoho.event.rule', string='Rule that decided', readonly=True,
        ondelete='set null')
    trigger = fields.Char(string='Read as', readonly=True)
    status_value = fields.Char(string='Status word', readonly=True)
    action_taken = fields.Char(string='What happened', readonly=True)
    error_note = fields.Text(string='Details', readonly=True)
    duplicate_of_id = fields.Many2one(
        'pb.zoho.inbox', string='First seen as', readonly=True,
        ondelete='set null')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True, readonly=True,
        default=lambda self: self.env.company)

    display_summary = fields.Char(
        string='Arrival', compute='_compute_display_summary')

    # Odoo 19 SILENTLY IGNORES `_sql_constraints`. The constraint is what makes
    # the retry safe under a race — two workers replaying the same push at the
    # same instant both pass the search and one of them then fails the INSERT,
    # which is exactly the outcome we want. NULLs stay distinct in Postgres, so
    # the duplicate rows (which carry no reference of their own) are unaffected.
    _event_uniq = models.Constraint(
        'unique(external_event_id)',
        'This arrival has already been recorded.')

    @api.depends('person_name', 'employee_number', 'zoho_record_id')
    def _compute_display_summary(self):
        for rec in self:
            who = rec.person_name or rec.employee_number or rec.zoho_record_id
            rec.display_summary = who or _('Arrival')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.display_summary or _('Arrival')

    # --------------------------------------------------------------- helpers
    @api.model
    def fingerprint(self, rec):
        """A stable event reference for a sender that gives us none.

        Deliberately built from the WHOLE normalised record and not just the id:
        a record that arrives twice unchanged is a duplicate, and the same
        person arriving tomorrow with a new status is not. Hashing only the id
        would make the second one invisible.
        """
        try:
            body = json.dumps(rec, sort_keys=True, default=str)
        except (TypeError, ValueError):
            body = repr(rec)
        return 'fp:' + hashlib.sha256(body.encode('utf-8')).hexdigest()[:40]

    @api.model
    def already_seen(self, external_event_id):
        if not external_event_id:
            return self.browse()
        return self.sudo().search(
            [('external_event_id', '=', external_event_id)], limit=1)

    def action_view_employee(self):
        self.ensure_one()
        if not self.employee_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Employee'),
            'res_model': 'hr.employee',
            'res_id': self.employee_id.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
        }

    def action_view_case(self):
        self.ensure_one()
        if not self.case_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journey'),
            'res_model': 'pb.journey.case',
            'res_id': self.case_id.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
        }
