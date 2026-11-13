# -*- coding: utf-8 -*-
"""Three questions in the first two months, each one tap long.

WHY THIS IS NOT ANONYMOUS. `pb_ess_workforce`'s shift pulse hides who answered
behind a salted hash, because its whole purpose is a number nobody can trace to
a person. This one is the opposite: a new joiner who taps "2" in week one needs
somebody to call them on Tuesday, and an anonymous 2 is a statistic nobody can
act on. So the anonymity machinery is deliberately NOT cloned — only the one-tap
page is. The page says so, in words, before the person taps.

THE LINK IS THE CREDENTIAL. A joiner in week one may have a portal account they
have not signed into yet, so the pulse is answered from an emailed token exactly
as a journey step is: one token per pulse, one question, and an unknown token
gets the same courteous page a used one does.
"""

import logging
import secrets
from datetime import timedelta

from odoo import api, fields, models, _

from .onboarding_common import (
    DAY_MARKS, DAY_MARK_LABEL, DAY_MARK_OFFSET, P_PULSE_MAIL, PULSE_RED_MAX,
    PULSE_STATES, first_name, flag,
)

_logger = logging.getLogger(__name__)

SCORES = [('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')]

#: How each score reads on the page and on the board. Plain words, never a
#: number on its own — "3 out of 5" tells a manager nothing they can act on.
SCORE_WORD = {
    '1': 'Struggling',
    '2': 'Not great',
    '3': 'Finding my feet',
    '4': 'Going well',
    '5': 'Really good',
}


class PbNewhirePulse(models.Model):
    _name = 'pb.newhire.pulse'
    _description = 'New Joiner Check'
    _order = 'due_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True, string='Check')
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='cascade')
    case_id = fields.Many2one(
        'pb.journey.case', string='Joining checklist', index=True,
        ondelete='cascade')
    day_mark = fields.Selection(
        DAY_MARKS, string='When', required=True, default='7', index=True)
    due_date = fields.Date(string='Ask on', index=True)
    state = fields.Selection(
        PULSE_STATES, string='Status', default='planned', required=True,
        index=True)
    score = fields.Selection(SCORES, string='How it is going')
    score_word = fields.Char(compute='_compute_score_word', string='In words')
    comment = fields.Char(string='What they said')
    red_flag = fields.Boolean(string='Needs attention', index=True)
    sent_at = fields.Datetime(string='Asked on', readonly=True)
    answered_at = fields.Datetime(string='Answered on', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    # No field-level `groups=` on the token — same reasoning as P0's journey
    # task (R13): a same-module group on a field is resolved at registry load,
    # before this module's security data exists, and it would refuse the very
    # create that mints the value. The ACL, the record rule and the fact that
    # no view or payload carries the raw value are the protection.
    portal_token = fields.Char(
        string='Link key', index=True, copy=False, readonly=True)

    _pulse_uniq = models.Constraint(
        'unique(employee_id, day_mark, case_id)',
        'That check has already been planned for this person.')

    # ------------------------------------------------------------- computes
    @api.depends('employee_id', 'day_mark')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s — %s' % (
                rec.employee_id.name or _('Employee'),
                DAY_MARK_LABEL.get(rec.day_mark, rec.day_mark or ''))

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('New joiner check')

    @api.depends('score')
    def _compute_score_word(self):
        for rec in self:
            rec.score_word = SCORE_WORD.get(rec.score or '', '')

    # ----------------------------------------------------------------- links
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('portal_token'):
                vals['portal_token'] = secrets.token_urlsafe(24)
        return super().create(vals_list)

    def _token_url(self):
        self.ensure_one()
        token = self.sudo().portal_token
        if not token:
            return ''
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        return '%s/journey/p/%s' % (base.rstrip('/'), token)

    @api.model
    def _pulse_for_token(self, token):
        """(pulse, status) for a link — the only way in from a public route."""
        blank = self.browse()
        if not token or len(token) < 12:
            return blank, 'invalid'
        pulse = self.sudo().search([('portal_token', '=', token)], limit=1)
        if not pulse:
            return blank, 'invalid'
        if pulse.state == 'cancelled':
            return pulse, 'closed'
        if pulse.state == 'answered':
            return pulse, 'used'
        return pulse, 'ok'

    # ------------------------------------------------------------- planning
    @api.model
    def ensure_for_case(self, case):
        """The three checks this joiner should get. Safe to call twice (R30).

        Called both when the journey opens and from the daily job, because a
        journey that opened before this module existed has no checks and would
        otherwise never get any. Search before create, per day mark.
        """
        if not case or case.case_type != 'onboarding':
            return self.browse()
        emp = case.employee_id
        if not emp:
            return self.browse()
        anchor = case.anchor_date or case._joining_date()
        if not anchor:
            return self.browse()
        made = self.browse()
        for mark, offset in DAY_MARK_OFFSET.items():
            try:
                found = self.sudo().search([
                    ('employee_id', '=', emp.id),
                    ('case_id', '=', case.id),
                    ('day_mark', '=', mark),
                ], limit=1)
                if found:
                    made |= found
                    continue
                made |= self.sudo().create({
                    'employee_id': emp.id,
                    'case_id': case.id,
                    'day_mark': mark,
                    'due_date': anchor + timedelta(days=offset),
                    'company_id': (case.company_id or emp.company_id
                                   or self.env.company).id,
                })
            except Exception:           # noqa: BLE001 — one mark, one grave
                _logger.exception(
                    'pb_onboarding: could not plan the %s-day check for %s',
                    mark, emp.id)
        return made

    # ----------------------------------------------------------------- the job
    @api.model
    def _cron_send_due(self, today=None):
        """Ask everybody whose check falls due today or earlier.

        Idempotent by STATE: a pulse that has been asked is 'sent' and is never
        picked up again, so a second run of the same day sends nothing. A pulse
        with no way to reach the person is left 'planned' rather than marked
        sent — tomorrow's run tries again, and the day somebody fills in a work
        email the backlog goes out.
        """
        today = today or fields.Date.today()
        mail_on = flag(self.env, P_PULSE_MAIL)
        due = self.sudo().search([
            ('state', '=', 'planned'),
            ('due_date', '!=', False),
            ('due_date', '<=', today),
            ('case_id.state', 'in', ('draft', 'active', 'on_hold')),
        ])
        if not mail_on:
            _logger.info('pb_onboarding: new-joiner checks are switched off — '
                         '%s were due and none was sent', len(due))
            return 0
        sent = 0
        for pulse in due:
            try:
                if pulse._queue_mail():
                    pulse.write({'state': 'sent',
                                 'sent_at': fields.Datetime.now()})
                    sent += 1
            except Exception:           # noqa: BLE001
                _logger.exception('pb_onboarding: check %s could not be sent',
                                  pulse.id)
        _logger.info('pb_onboarding: %s new-joiner check(s) sent of %s due',
                     sent, len(due))
        return sent

    def _queue_mail(self):
        """One queued message. NO ADDRESS, NO MAIL (R6) — and the recipient is
        passed explicitly, because a template's own rendered `email_to` can
        reach `mail.mail` empty with no error anywhere."""
        self.ensure_one()
        emp = self.employee_id
        to = (emp.work_email or '').strip() or (
            emp.user_id.email if emp.user_id else '')
        if not to:
            _logger.info('pb_onboarding: %s has no email — check %s not sent',
                         emp.name, self.id)
            return False
        template = self.env.ref('pb_onboarding.mail_template_newhire_pulse',
                                raise_if_not_found=False)
        if not template:
            _logger.warning('pb_onboarding: the check email is missing')
            return False
        template.sudo().send_mail(
            self.id, force_send=False,
            email_values={'email_to': to, 'auto_delete': False})
        return True

    # ------------------------------------------------------------- answering
    def submit(self, score, comment=None):
        """One tap, recorded once. A replay changes nothing."""
        self.ensure_one()
        if self.state == 'answered':
            return False
        score = str(score or '').strip()
        if score not in dict(SCORES):
            return False
        red = int(score) <= PULSE_RED_MAX
        self.sudo().write({
            'score': score,
            'comment': (comment or '').strip()[:500] or False,
            'state': 'answered',
            'answered_at': fields.Datetime.now(),
            'red_flag': red,
        })
        self.sudo()._after_answer(red)
        return True

    def _after_answer(self, red):
        """Put a struggling joiner in front of a human the same day.

        Wrapped whole: the answer is already saved and committed by the time
        this runs, and a failure to raise the flag must never turn the
        person's thank-you page into an error.
        """
        self.ensure_one()
        case = self.case_id
        try:
            if case:
                case.message_post(body=_(
                    "%(who)s answered their %(mark)s check: %(word)s"
                    "%(said)s.",
                    who=self.employee_id.name or '',
                    mark=DAY_MARK_LABEL.get(self.day_mark, self.day_mark),
                    word=SCORE_WORD.get(self.score, self.score or ''),
                    said=(' — “%s”' % self.comment) if self.comment else ''))
        except Exception:               # noqa: BLE001
            _logger.exception('pb_onboarding: could not log check %s', self.id)
        if not red:
            return
        try:
            owner = self.employee_id.hrbp_user_id or (
                self.employee_id.parent_id.user_id
                if self.employee_id.parent_id else False)
            if case and owner:
                case.activity_schedule(
                    act_type_xmlid='mail.mail_activity_data_todo',
                    summary=_("Check in with %s — they are struggling",
                              self.employee_id.name or ''),
                    note=_("Their %(mark)s answer was “%(word)s”%(said)s. "
                           "A short call today is worth more than a form.",
                           mark=DAY_MARK_LABEL.get(self.day_mark,
                                                   self.day_mark),
                           word=SCORE_WORD.get(self.score, self.score or ''),
                           said=(': “%s”' % self.comment)
                           if self.comment else ''),
                    user_id=owner.id,
                    date_deadline=fields.Date.today())
        except Exception:               # noqa: BLE001
            _logger.exception('pb_onboarding: could not raise the flag on %s',
                              self.id)

    # ------------------------------------------------------------- the page
    def _page_values(self, token, status):
        """What the login-less page is allowed to know.

        The joiner's own first name and the question. Not an id, not a
        department, not their manager, not the other two checks.
        """
        emp = self.employee_id if self else None
        return {
            'status': status,
            'token': token,
            'has_pulse': bool(self),
            'greeting': _('Hi %(name)s', name=first_name(emp.name))
            if emp else '',
            'mark': DAY_MARK_LABEL.get(self.day_mark, '') if self else '',
            'company': (self.company_id.name
                        if self and self.company_id else ''),
            'scores': [{'value': v, 'word': SCORE_WORD[v]}
                       for v, _lab in SCORES],
        }
