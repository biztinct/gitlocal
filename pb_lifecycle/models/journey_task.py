# -*- coding: utf-8 -*-
"""One step of one journey.

A task is the case's OWN copy of a checklist step: its wording, its date and its
owner were decided when the journey opened and belong to it from then on. The
`step_id` link is kept for reporting, never re-read to re-derive anything —
with one read-only exception (NEWHIRE P6, `_pb_shown_texts`): a task whose
words are still exactly the step's own is SHOWN in the reader's language.
"""

import json
import logging
import secrets

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .lifecycle_common import (
    ASSIGNEE_RULES, STEP_KINDS, TASK_STATES, TOKEN_KINDS,
)

_logger = logging.getLogger(__name__)

_OPEN_STATES = ('pending', 'in_progress', 'blocked')


class PbJourneyTask(models.Model):
    _name = 'pb.journey.task'
    _description = 'Journey Step'
    _order = 'due_date, sequence, id'

    case_id = fields.Many2one(
        'pb.journey.case', string='Journey', required=True, index=True,
        ondelete='cascade')
    step_id = fields.Many2one(
        'pb.journey.template.step', string='From step', ondelete='set null')
    employee_id = fields.Many2one(
        related='case_id.employee_id', store=True, index=True,
        string='Employee')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Step', required=True)
    description = fields.Text(string='What to do')
    assignee_rule = fields.Selection(ASSIGNEE_RULES, string='Owner role')
    assignee_user_id = fields.Many2one(
        'res.users', string='Owner', index=True)
    due_date = fields.Date(string='Due', index=True)
    state = fields.Selection(
        TASK_STATES, string='Status', default='pending', required=True,
        index=True)
    step_kind = fields.Selection(STEP_KINDS, string='Kind', default='task')
    blocking_ff = fields.Boolean(string='Blocks final settlement')
    mail_template_id = fields.Many2one('mail.template', string='Email to send')
    letter_template_id = fields.Many2one('pb.letter.template', string='Letter')

    # No field-level `groups=` on the token, deliberately. A same-module group
    # on a field is resolved at REGISTRY LOAD, which on a fresh install runs
    # before this module's security data exists — and it would also refuse the
    # very create that mints the token. The protection that matters is the
    # ACL (only the lifecycle tiers read this model at all), the record rule
    # (a plain user sees only their own steps) and the fact that no view and no
    # facade payload ever carries the raw value: `_token_url()` builds the link
    # under sudo and the cockpit hands it only to a writer.
    portal_token = fields.Char(
        string='Link key', index=True, copy=False, readonly=True,
        help='The key in the private link sent to someone who has no login.')
    form_questions_json = fields.Text(string='Questions')
    payload_json = fields.Text(string='Answers', readonly=True)

    done_by = fields.Many2one('res.users', string='Done by', readonly=True)
    done_at = fields.Datetime(string='Done on', readonly=True)
    escalation_days = fields.Integer(string='Escalate after (days)', default=3)
    escalated = fields.Boolean(string='Escalated', readonly=True, copy=False)
    reminded_on = fields.Date(string='Last reminder', readonly=True, copy=False)
    note = fields.Text(string='Note')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    # ----------------------------------------------------------------- links
    @api.model
    def _needs_token(self, vals):
        return (vals.get('step_kind') in TOKEN_KINDS
                or vals.get('assignee_rule') == 'candidate')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self._needs_token(vals) and not vals.get('portal_token'):
                vals['portal_token'] = secrets.token_urlsafe(24)
        return super().create(vals_list)

    # ------------------------------------------------------------- wording
    def _pb_shown_texts(self, lang=None):
        """``{task_id: {'name', 'description'}}`` in the reader's language.

        NEWHIRE P6. A task keeps the words it was given when the journey
        opened, in the language of whoever opened it. When those words are
        still EXACTLY one of the checklist step's own versions (any language
        it holds), nobody changed them since, so the reader gets the step's
        version in their own language. A task whose words were changed in
        the journey, or whose step was renamed afterwards, keeps its own
        words, as before. Read-only: nothing is written.
        """
        lang = lang or self.env.lang or 'en_US'
        out = {t.id: {'name': t.name or '', 'description': t.description or ''} for t in self}
        step_ids = list({t.step_id.id for t in self if t.step_id})
        if not step_ids:
            return out
        Step = self.env['pb.journey.template.step']
        Step.flush_model(['name', 'description'])
        self.env.cr.execute(
            'SELECT id, name, description FROM pb_journey_template_step WHERE id = ANY(%s)',
            (step_ids,))
        words = {}
        for sid, name, desc in self.env.cr.fetchall():
            words[sid] = (name if isinstance(name, dict) else {},
                          desc if isinstance(desc, dict) else {})

        def pick(own, versions):
            plain = {k: v for k, v in versions.items() if not k.startswith('_') and v}
            if not own or own not in plain.values():
                return own
            return plain.get(lang) or plain.get('en_US') or own

        for t in self:
            if t.step_id.id not in words:
                continue
            names, descs = words[t.step_id.id]
            out[t.id] = {'name': pick(t.name or '', names),
                         'description': pick(t.description or '', descs)}
        return out

    def _token_url(self):
        self.ensure_one()
        if not self.sudo().portal_token:
            return ''
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        return '%s/journey/t/%s' % (base.rstrip('/'), self.sudo().portal_token)

    @api.model
    def _task_for_token(self, token):
        """(task, status) for a link. The ONLY way in from a public route.

        Unknown and used tokens are answered the same way by the page above, so
        the URL space cannot be probed for what exists.
        """
        blank = self.browse()
        if not token or len(token) < 12:
            return blank, 'invalid'
        task = self.sudo().search([('portal_token', '=', token)], limit=1)
        if not task:
            return blank, 'invalid'
        if task.case_id.state in ('cancelled',):
            return task, 'closed'
        if task.state in ('done', 'skipped'):
            return task, 'used'
        return task, 'ok'

    # --------------------------------------------------------------- actions
    def _settle(self, state, payload=None, by_user=None, note=None):
        self.ensure_one()
        vals = {'state': state,
                'done_at': fields.Datetime.now(),
                'done_by': (by_user or self.env.user).id}
        if payload is not None:
            vals['payload_json'] = json.dumps(payload, default=str)
        if note:
            vals['note'] = note
        self.write(vals)
        return True

    def action_done(self, payload=None):
        for rec in self:
            if rec.state in ('done', 'skipped'):
                continue
            rec._settle('done', payload=payload)
            rec.case_id.message_post(body=_(
                "%(step)s — done.", step=rec.name))
        return True

    def action_skip(self, reason=None):
        for rec in self:
            if rec.state in ('done', 'skipped'):
                continue
            rec._settle('skipped', note=reason)
            rec.case_id.message_post(body=_(
                "%(step)s — skipped%(why)s.", step=rec.name,
                why=(': %s' % reason) if reason else ''))
        return True

    def action_start(self):
        self.filtered(lambda t: t.state == 'pending').write(
            {'state': 'in_progress'})
        return True

    def action_block(self, reason=None):
        for rec in self:
            rec.write({'state': 'blocked', 'note': reason or rec.note})
            rec.case_id.message_post(body=_(
                "%(step)s — blocked%(why)s.", step=rec.name,
                why=(': %s' % reason) if reason else ''))
        return True

    def action_unblock(self):
        self.filtered(lambda t: t.state == 'blocked').write(
            {'state': 'pending'})
        return True

    def action_reassign(self, user_id):
        user = self.env['res.users'].browse(int(user_id)).exists()
        if not user:
            raise UserError(_("That person could not be found."))
        for rec in self:
            rec.assignee_user_id = user.id
            rec.case_id.message_post(body=_(
                "%(step)s — now owned by %(who)s.", step=rec.name,
                who=user.name))
        return True

    # ------------------------------------------------------------- questions
    def questions(self):
        """The form's questions, as a list the page can render.

        Anything unreadable answers with an empty list rather than raising: a
        broken question set must not turn a person's link into an error page.
        """
        self.ensure_one()
        raw = self.form_questions_json
        if not raw:
            return []
        try:
            loaded = json.loads(raw)
        except Exception:
            _logger.warning('pb.journey.task %s: questions are not readable '
                            'JSON', self.id)
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
                    'label': str(q.get('label') or q.get('key') or ''),
                    'type': q.get('type') if q.get('type') in
                            ('text', 'rating', 'choice') else 'text',
                    'options': [str(o) for o in (q.get('options') or [])],
                })
        return out

    @property
    def is_open(self):
        self.ensure_one()
        return self.state in _OPEN_STATES
