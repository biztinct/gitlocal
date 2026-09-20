# -*- coding: utf-8 -*-
"""A questionnaire with a link and a window.

The respondent is very often not an employee — a peer at a client, a manager who
left, a referee. So the link IS the credential, exactly as the shift
acknowledgment page established: one unguessable token addressing one request,
a page that shows only what that person needs, and the same polite answer for a
token that is finished as for one that never existed.
"""

import json
import logging
import secrets

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

FEEDBACK_KINDS = [
    ('probation_peer', 'Probation peer'),
    ('exit', 'Exit'),
    ('pip', 'PIP'),
    ('other', 'Other'),
]

FEEDBACK_KIND_LABEL = dict(FEEDBACK_KINDS)


class PbFeedbackRequest(models.Model):
    _name = 'pb.feedback.request'
    _description = 'Feedback Request'
    _order = 'window_end desc, id desc'

    name = fields.Char(compute='_compute_name', store=True, string='Request')
    subject_employee_id = fields.Many2one(
        'hr.employee', string='About', required=True, index=True,
        ondelete='cascade')
    respondent_user_id = fields.Many2one('res.users', string='Ask (internal)')
    respondent_email = fields.Char(string='Ask (email)')
    kind = fields.Selection(
        FEEDBACK_KINDS, string='Kind', required=True, default='other')
    case_id = fields.Many2one(
        'pb.journey.case', string='Journey', index=True, ondelete='set null')
    # No field-level `groups=` — see the note on `pb.journey.task.portal_token`
    # for why. This model's ACL already starts at the manager tier.
    token = fields.Char(
        string='Link key', index=True, copy=False, readonly=True)
    window_end = fields.Date(
        string='Answer by', index=True,
        help='After this date the link politely closes.')
    state = fields.Selection(
        [('sent', 'Waiting'), ('submitted', 'Answered'),
         ('expired', 'Closed'), ('extended', 'Extended')],
        string='Status', default='sent', required=True, index=True)
    questions_json = fields.Text(
        string='Questions',
        help='A list of {"key", "label", "type", "options"} entries. '
             'The types are text, rating and choice.')
    answers_json = fields.Text(string='Answers', readonly=True)
    submitted_at = fields.Datetime(string='Answered on', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    _token_uniq = models.Constraint(
        'unique(token)',
        'Two feedback links cannot share the same key.')

    @api.depends('subject_employee_id', 'kind')
    def _compute_name(self):
        for rec in self:
            rec.name = _('Feedback about %(who)s (%(kind)s)',
                         who=rec.subject_employee_id.name or _('an employee'),
                         kind=FEEDBACK_KIND_LABEL.get(rec.kind, rec.kind or ''))

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Feedback request')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('token'):
                vals['token'] = secrets.token_urlsafe(24)
        return super().create(vals_list)

    # ------------------------------------------------------------------ link
    def _token_url(self):
        self.ensure_one()
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        return '%s/journey/f/%s' % (base.rstrip('/'), self.sudo().token)

    @api.model
    def _request_for_token(self, token):
        blank = self.browse()
        if not token or len(token) < 12:
            return blank, 'invalid'
        req = self.sudo().search([('token', '=', token)], limit=1)
        if not req:
            return blank, 'invalid'
        if req.state == 'submitted':
            return req, 'used'
        if req.window_end and req.window_end < fields.Date.today():
            return req, 'closed'
        return req, 'ok'

    def questions(self):
        self.ensure_one()
        raw = self.questions_json
        if not raw:
            return []
        try:
            loaded = json.loads(raw)
        except Exception:
            _logger.warning('pb.feedback.request %s: questions are not '
                            'readable JSON', self.id)
            return []
        out = []
        if isinstance(loaded, list):
            for i, q in enumerate(loaded):
                if isinstance(q, str):
                    q = {'key': 'q%s' % (i + 1), 'label': q, 'type': 'text'}
                if not isinstance(q, dict):
                    continue
                out.append({
                    'key': str(q.get('key') or 'q%s' % (i + 1)),
                    'label': str(q.get('label') or ''),
                    'type': q.get('type') if q.get('type') in
                            ('text', 'rating', 'choice') else 'text',
                    'options': [str(o) for o in (q.get('options') or [])],
                })
        return out

    # --------------------------------------------------------------- actions
    def action_send(self):
        template = self.env.ref('pb_lifecycle.mail_template_feedback_invite',
                                raise_if_not_found=False)
        if not template:
            raise UserError(_("The feedback email is not set up yet."))
        sent = 0
        for rec in self:
            to = rec.respondent_email or (
                rec.respondent_user_id.email if rec.respondent_user_id else '')
            if not to:
                _logger.info('pb.feedback.request %s: nobody to ask', rec.id)
                continue
            try:
                template.send_mail(rec.id, force_send=False,
                                   email_values={'email_to': to})
                sent += 1
            except Exception:
                _logger.exception('pb.feedback.request %s: invite failed',
                                  rec.id)
        _logger.info('pb.feedback.request: queued %s invite(s)', sent)
        return sent

    def action_extend(self, days=1):
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 1
        for rec in self:
            base = rec.window_end or fields.Date.today()
            rec.write({'window_end': fields.Date.add(base, days=max(days, 1)),
                       'state': 'extended'})
        return True

    def submit_answers(self, answers):
        """Record what somebody answered. Called from the public route only."""
        self.ensure_one()
        self.write({
            'answers_json': json.dumps(answers, default=str),
            'state': 'submitted',
            'submitted_at': fields.Datetime.now(),
        })
        if self.case_id:
            self.case_id.message_post(body=_(
                "Feedback received (%(kind)s).",
                kind=FEEDBACK_KIND_LABEL.get(self.kind, self.kind or '')))
        return True
