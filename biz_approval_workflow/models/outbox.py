# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Telling people, exactly once.

Rows are written inside the same transaction as the thing that happened, so a
decision and its "it is your turn" can never disagree. Delivery is a separate,
retryable cron pass keyed on a unique dedupe key — a retry never repeats a
business transition (design §9).

Nothing here ever puts an amount, a wage or a bank detail in a subject line.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

KINDS = [
    ('your_turn', 'It is your turn'),
    ('reminder', 'Still waiting'),
    ('escalation', 'Overdue'),
    ('returned', 'Sent back to you'),
    ('approved', 'Approved'),
    ('rejected', 'Turned down'),
    ('exception_used', 'An exception was used'),
    ('covering', 'You are covering for someone'),
    ('notified', 'For your information'),
]


def _subject_for(kind, title):
    """Plain, safe subject lines — never an amount, a wage or a bank detail."""
    return {
        'your_turn': _("Your approval is needed: %s", title),
        'reminder': _("Still waiting for your approval: %s", title),
        'escalation': _("Overdue approval: %s", title),
        'returned': _("Sent back to you: %s", title),
        'approved': _("Approved: %s", title),
        'rejected': _("Turned down: %s", title),
        'exception_used': _("An exception was used: %s", title),
        'covering': _("You are covering an approval: %s", title),
        'notified': _("For your information: %s", title),
    }.get(kind, _("Approval: %s", title))


class BizApprovalOutbox(models.Model):
    _name = 'biz.approval.outbox'
    _description = 'Approval Notification Queue'
    _order = 'id'

    kind = fields.Selection(KINDS, required=True, index=True)
    user_id = fields.Many2one('res.users', required=True, index=True)
    request_id = fields.Many2one('biz.approval.request', index=True,
                                 ondelete='cascade')
    payload = fields.Json(default=dict)
    dedupe_key = fields.Char(required=True, index=True, copy=False)
    state = fields.Selection([('queued', 'Waiting'), ('sent', 'Sent'),
                              ('failed', 'Could not send')],
                             default='queued', required=True, index=True)
    attempts = fields.Integer(default=0)
    last_error = fields.Char()

    _dedupe_uniq = models.Constraint(
        'unique(dedupe_key)',
        'That message is already queued.')

    @api.model
    def _queue(self, kind, user, request=None, payload=None, dedupe=None):
        """Queue one message; a repeat of the same dedupe key is a no-op."""
        if not user or not user.active or user.share:
            return self.browse()
        key = dedupe or '%s-%s-%s' % (kind, request.id if request else 0,
                                      user.id)
        existing = self.sudo().search([('dedupe_key', '=', key)], limit=1)
        if existing:
            return existing
        return self.sudo().create({
            'kind': kind, 'user_id': user.id,
            'request_id': request.id if request else False,
            'payload': payload or {}, 'dedupe_key': key,
        })

    # --------------------------------------------------------------- cron
    @api.model
    def _cron_deliver(self, limit=200):
        rows = self.sudo().search([('state', '=', 'queued')], limit=limit)
        for row in rows:
            try:
                # a savepoint per row: one message that cannot be sent must
                # not poison the transaction the next nine are queued in
                with self.env.cr.savepoint():
                    row._deliver()
                row.write({'state': 'sent', 'attempts': row.attempts + 1,
                           'last_error': False})
            except Exception as exc:  # noqa: BLE001 — one bad row must not
                self.env.invalidate_all()
                _logger.exception('biz.approval.outbox %s failed', row.id)
                row.write({'state': 'failed' if row.attempts >= 4 else 'queued',
                           'attempts': row.attempts + 1,
                           'last_error': str(exc)[:250]})
        return True

    def _deliver(self):
        self.ensure_one()
        request = self.request_id
        title = request.title if request else _('an approval')
        subject = _subject_for(self.kind, title)
        if not request:
            return True
        body = self._body()
        request.sudo().message_post(
            body=body, subject=subject,
            partner_ids=self.user_id.partner_id.ids,
            message_type='notification',
            subtype_xmlid='mail.mt_note')
        if self.kind in ('your_turn', 'reminder', 'escalation', 'returned'):
            request.sudo().activity_schedule(
                act_type_xmlid='mail.mail_activity_data_todo',
                summary=subject, note=body,
                user_id=self.user_id.id,
                date_deadline=(request.due_at
                               or fields.Datetime.now()).date())
        return True

    def _body(self):
        self.ensure_one()
        payload = self.payload or {}
        lines = []
        if self.kind == 'your_turn':
            lines.append(_("Your approval is needed on \"%s\".",
                           self.request_id.title))
        elif self.kind == 'reminder':
            lines.append(_("This is still waiting for you."))
        elif self.kind == 'escalation':
            lines.append(_("This has passed its target time and nobody has "
                           "decided it yet."))
        elif self.kind == 'returned':
            lines.append(_("This was sent back to you."))
        elif self.kind == 'approved':
            lines.append(_("This was approved."))
        elif self.kind == 'rejected':
            lines.append(_("This was turned down."))
        elif self.kind == 'exception_used':
            lines.append(_("Someone approved a step they were involved in, "
                           "using an exception you allowed."))
        elif self.kind == 'covering':
            lines.append(_("You are covering this for someone else."))
        elif self.kind == 'notified':
            # A "tell someone" step is not a decision and never asks for one.
            lines.append(_("This is for your information. Nothing is waiting "
                           "for you."))
        if payload.get('step_title'):
            lines.append(_("Step: %s", payload['step_title']))
        if payload.get('reason'):
            lines.append(_("Reason given: %s", payload['reason']))
        return '<br/>'.join(lines)
