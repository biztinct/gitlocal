# -*- coding: utf-8 -*-
"""LEARNING L5 — course feedback and the manager's 30-day follow-up.

THE HOUSE PATTERN, NOT A NEW ONE (ledger F5): both are `pb.feedback.request`
rows — a token, a window, a list of questions as JSON, the answers as JSON —
with two new kinds added from here (`training`, `training_followup`). The
link opens OUR token page `/my/training/feedback/<token>`, worded for the
course ("How was DEMO Site safety?" / "Has Lan's work changed since DEMO
Site safety?"), never the stock survey website (binding non-goal).

  * COURSE FEEDBACK — the moment an assignment is finished (the same
    crossing that files the certificate) the person gets two ratings and one
    line: "Was it useful?", "Would you recommend it?", "What would you
    change?". Open 14 days. Switch `pb_training.feedback_on`.
  * MANAGER FOLLOW-UP — on the same crossing a `pb.training.followup` row is
    planned for `completed_on + followup_days` (30). The morning job sends it
    to their manager as a `training_followup` request: "Has their work
    changed since the course?" (rating), "Did they use what they learned?"
    (Yes / Partly / No), and a line. Nobody to ask → the row is "Skipped".
    Switch `pb_training.followup_on`.

Respondents get at most one email per request (handover §5.5). Answers roll
up to the course (ours or outside): `avg_rating` / `ratings_count` /
`recommend_pct` and `effect_avg` / `used_pct`, read by the course drawer, the
outside catalogue and Numbers.
"""

import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models

from .training_common import (
    FOLLOWUP_STATES, P_FEEDBACK_ON, P_FOLLOWUP_DAYS, P_FOLLOWUP_ON,
    P_REMINDER_CAP, as_id, flag, leg, number,
)

_logger = logging.getLogger(__name__)

FEEDBACK_WINDOW_DAYS = 14
FOLLOWUP_WINDOW_DAYS = 14
USED_YES, USED_PARTLY, USED_NO = 'Yes', 'Partly', 'No'


def feedback_questions():
    """English keys and labels — the token page says them in the reader's
    language from the keys, the stored labels are for the record."""
    return [
        {'key': 'useful', 'label': 'Was it useful?', 'type': 'rating'},
        {'key': 'recommend', 'label': 'Would you recommend it?',
         'type': 'rating'},
        {'key': 'change', 'label': 'What would you change?', 'type': 'text'},
    ]


def followup_questions():
    return [
        {'key': 'effect', 'label': 'Has their work changed since the course?',
         'type': 'rating'},
        {'key': 'used', 'label': 'Did they use what they learned?',
         'type': 'choice', 'options': [USED_YES, USED_PARTLY, USED_NO]},
        {'key': 'note', 'label': 'Anything to add?', 'type': 'text'},
    ]


def _answers(req):
    try:
        data = json.loads(req.answers_json or '{}')
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def _rating(value):
    try:
        n = int(str(value or '').strip())
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 5 else None


class PbFeedbackRequestTraining(models.Model):
    _inherit = 'pb.feedback.request'

    kind = fields.Selection(
        selection_add=[('training', 'Course feedback'),
                       ('training_followup', 'Manager follow-up')],
        ondelete={'training': 'cascade', 'training_followup': 'cascade'})
    assignment_id = fields.Many2one(
        'pb.training.assignment', string='Finished course', index=True,
        ondelete='set null')
    training_request_id = fields.Many2one(
        'pb.training.request', string='Course request', index=True,
        ondelete='set null')
    channel_id = fields.Many2one('slide.channel', string='Course',
                                 index=True, ondelete='set null')
    outside_course_id = fields.Many2one(
        'pb.training.outside.course', string='Outside course', index=True,
        ondelete='set null')
    followup_id = fields.Many2one('pb.training.followup', string='Follow-up',
                                  index=True, ondelete='set null')

    def _pb_course_name(self):
        self.ensure_one()
        return (self.channel_id.sudo().name or self.outside_course_id.sudo().name
                or (self.training_request_id.sudo().course_name or ''))

    def _pb_feedback_url(self):
        self.ensure_one()
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        return '%s/my/training/feedback/%s' % (base.rstrip('/'),
                                               self.sudo().token)

    def submit_answers(self, answers):
        res = super().submit_answers(answers)
        for rec in self.filtered('followup_id'):
            rec.followup_id.sudo().write({'state': 'answered'})
        return res

    def _pb_send(self, xmlid):
        """One email, addressed explicitly, English body (LD10 / LN47)."""
        self.ensure_one()
        template = self.env.ref(xmlid, raise_if_not_found=False)
        user = self.respondent_user_id.sudo()
        to = self.respondent_email or (user.email or '')
        if not template or not to:
            return False
        template.sudo().with_context(lang='en_US').send_mail(
            self.id, force_send=False,
            email_values={'email_to': to, 'auto_delete': False})
        return True


class PbTrainingFollowup(models.Model):
    _name = 'pb.training.followup'
    _description = 'Manager follow-up after a course'
    _order = 'due_date desc, id desc'

    assignment_id = fields.Many2one(
        'pb.training.assignment', string='Finished course', index=True,
        ondelete='cascade')
    training_request_id = fields.Many2one(
        'pb.training.request', string='Course request', index=True,
        ondelete='cascade')
    channel_id = fields.Many2one('slide.channel', string='Course',
                                 index=True, ondelete='set null')
    outside_course_id = fields.Many2one(
        'pb.training.outside.course', string='Outside course', index=True,
        ondelete='set null')
    employee_id = fields.Many2one('hr.employee', string='Who took it',
                                  required=True, index=True,
                                  ondelete='cascade')
    manager_id = fields.Many2one('hr.employee', string='Their manager',
                                 index=True, ondelete='set null')
    due_date = fields.Date(string='Ask on', index=True)
    state = fields.Selection(FOLLOWUP_STATES, string='How far it has got',
                             default='planned', required=True, index=True)
    feedback_request_id = fields.Many2one(
        'pb.feedback.request', string='The questions sent', ondelete='set null')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)

    def _course_name(self):
        self.ensure_one()
        return self.channel_id.sudo().name or \
            self.outside_course_id.sudo().name or \
            self.training_request_id.sudo().course_name or ''

    def _send(self):
        """Turn a planned row into one question set to the manager."""
        self.ensure_one()
        if self.state != 'planned':
            return False
        manager = self.manager_id.sudo()
        user = manager.user_id
        email = (manager.work_email or '').strip() or (user.email or '')
        if not manager or not email:
            self.write({'state': 'skipped'})
            return False
        req = self.env['pb.feedback.request'].sudo().create({
            'subject_employee_id': self.employee_id.id,
            'respondent_user_id': user.id or False,
            'respondent_email': email,
            'kind': 'training_followup',
            'window_end': fields.Date.today()
            + timedelta(days=FOLLOWUP_WINDOW_DAYS),
            'questions_json': json.dumps(followup_questions()),
            'assignment_id': self.assignment_id.id or False,
            'training_request_id': self.training_request_id.id or False,
            'channel_id': self.channel_id.id or False,
            'outside_course_id': self.outside_course_id.id or False,
            'followup_id': self.id,
            'company_id': self.company_id.id,
        })
        self.write({'state': 'sent', 'feedback_request_id': req.id})
        req._pb_send('pb_training.mail_template_training_followup')
        return True


class PbTrainingFeedbackMixin(models.AbstractModel):
    """The two things a finished course asks for, in one place, for an
    assignment (ours) and for a request (outside / something else)."""
    _name = 'pb.training.feedback.maker'
    _description = 'Course feedback and follow-up maker'

    @api.model
    def _plan(self, employee, channel=None, outside=None, assignment=None,
              request=None, finished_on=None):
        employee = employee.sudo()
        made = {'feedback': False, 'followup': False}
        company = employee.company_id or self.env.company
        if flag(self.env, P_FEEDBACK_ON) and employee.user_id:
            Feedback = self.env['pb.feedback.request'].sudo()
            domain = [('kind', '=', 'training'),
                      ('subject_employee_id', '=', employee.id)]
            if assignment:
                domain.append(('assignment_id', '=', assignment.id))
            else:
                domain.append(('training_request_id', '=', request.id))
            if not Feedback.search_count(domain):
                user = employee.user_id
                req = Feedback.create({
                    'subject_employee_id': employee.id,
                    'respondent_user_id': user.id,
                    'respondent_email': (employee.work_email or '').strip()
                    or (user.email or ''),
                    'kind': 'training',
                    'window_end': fields.Date.today()
                    + timedelta(days=FEEDBACK_WINDOW_DAYS),
                    'questions_json': json.dumps(feedback_questions()),
                    'assignment_id': assignment.id if assignment else False,
                    'training_request_id': request.id if request else False,
                    'channel_id': channel.id if channel else False,
                    'outside_course_id': outside.id if outside else False,
                    'company_id': company.id,
                })
                leg(self.env, 'ask for course feedback',
                    lambda: req._pb_send(
                        'pb_training.mail_template_course_feedback'))
                made['feedback'] = req.id
        if flag(self.env, P_FOLLOWUP_ON):
            Followup = self.env['pb.training.followup'].sudo()
            domain = [('employee_id', '=', employee.id)]
            if assignment:
                domain.append(('assignment_id', '=', assignment.id))
            else:
                domain.append(('training_request_id', '=', request.id))
            if not Followup.search_count(domain):
                days = number(self.env, P_FOLLOWUP_DAYS, 30)
                manager = employee.parent_id
                row = Followup.create({
                    'assignment_id': assignment.id if assignment else False,
                    'training_request_id': request.id if request else False,
                    'channel_id': channel.id if channel else False,
                    'outside_course_id': outside.id if outside else False,
                    'employee_id': employee.id,
                    'manager_id': manager.id or False,
                    'due_date': (finished_on or fields.Date.today())
                    + timedelta(days=max(days, 1)),
                    'state': 'planned' if manager else 'skipped',
                    'company_id': company.id,
                })
                made['followup'] = row.id
        return made


class PbTrainingAssignmentFeedback(models.Model):
    _inherit = 'pb.training.assignment'

    def _refresh_one(self, today=None):
        was = self.state
        state = super()._refresh_one(today)
        if state == 'done' and was != 'done':
            leg(self.env, 'plan course feedback and the follow-up',
                lambda: self.env['pb.training.feedback.maker']._plan(
                    self.employee_id, channel=self.channel_id,
                    assignment=self, finished_on=self.completed_on))
        return state


class PbTrainingRequestFeedback(models.Model):
    _inherit = 'pb.training.request'

    def _after_taken(self):
        res = super()._after_taken()
        if self.kind != 'ours':
            self.env['pb.training.feedback.maker']._plan(
                self.employee_id, outside=self.outside_course_id or None,
                request=self)
        return res


# =========================================================================
#  the roll-ups
# =========================================================================
def rollup(env, domain):
    """Ratings and follow-up answers for whatever `domain` adds to the
    feedback search (a course, an outside course, a company …)."""
    Feedback = env['pb.feedback.request'].sudo()
    base = [('state', '=', 'submitted')] + list(domain)
    useful, recommend, comments = [], [], []
    for req in Feedback.search(base + [('kind', '=', 'training')],
                               order='submitted_at desc, id desc'):
        ans = _answers(req)
        u = _rating((ans.get('useful') or {}).get('value'))
        r = _rating((ans.get('recommend') or {}).get('value'))
        if u:
            useful.append(u)
        if r:
            recommend.append(r)
        text = ((ans.get('change') or {}).get('value') or '').strip()
        if text and len(comments) < 5:
            comments.append({'text': text[:300],
                             'when': fields.Datetime.to_string(
                                 req.submitted_at) or ''})
    effect, used = [], []
    for req in Feedback.search(base + [('kind', '=', 'training_followup')]):
        ans = _answers(req)
        e = _rating((ans.get('effect') or {}).get('value'))
        if e:
            effect.append(e)
        u = ((ans.get('used') or {}).get('value') or '').strip()
        if u in (USED_YES, USED_PARTLY, USED_NO):
            used.append(u)
    return {
        'ratings_count': len(useful),
        'avg_rating': round(sum(useful) / len(useful), 1) if useful else None,
        'recommend_pct': int(round(100.0 * len([x for x in recommend
                                                 if x >= 4])
                                   / len(recommend))) if recommend else None,
        'comments': comments,
        'followups_answered': len(effect) or len(used),
        'effect_avg': round(sum(effect) / len(effect), 1) if effect else None,
        'used_pct': int(round(100.0 * len([x for x in used
                                            if x in (USED_YES, USED_PARTLY)])
                              / len(used))) if used else None,
    }


class SlideChannelRatings(models.Model):
    _inherit = 'slide.channel'

    pb_avg_rating = fields.Float(string='Average rating',
                                 compute='_compute_pb_ratings', digits=(3, 1))
    pb_ratings_count = fields.Integer(string='How many ratings',
                                      compute='_compute_pb_ratings')
    pb_recommend_pct = fields.Integer(string='Would recommend (%)',
                                      compute='_compute_pb_ratings')

    def _compute_pb_ratings(self):
        for rec in self:
            data = rollup(rec.env, [('channel_id', '=', rec.id)]) if rec.id \
                else {}
            rec.pb_avg_rating = data.get('avg_rating') or 0.0
            rec.pb_ratings_count = data.get('ratings_count') or 0
            rec.pb_recommend_pct = data.get('recommend_pct') or 0


class OutsideCourseRatings(models.Model):
    _inherit = 'pb.training.outside.course'

    avg_rating = fields.Float(string='Average rating',
                              compute='_compute_ratings', digits=(3, 1))
    ratings_count = fields.Integer(string='How many ratings',
                                   compute='_compute_ratings')

    def _compute_ratings(self):
        for rec in self:
            data = rollup(rec.env, [('outside_course_id', '=', rec.id)]) \
                if rec.id else {}
            rec.avg_rating = data.get('avg_rating') or 0.0
            rec.ratings_count = data.get('ratings_count') or 0


def rating_words(env, data):
    """"4.3 · 17 ratings" — '' when nobody has rated it."""
    n = data.get('ratings_count') or 0
    if not n:
        return ''
    count = env._("1 rating") if n == 1 else env._("%s ratings", n)
    return '%s · %s' % (data.get('avg_rating'), count)


# =========================================================================
#  the morning job
# =========================================================================
class PbTrainingAutomationFollowups(models.AbstractModel):
    _inherit = 'pb.training.automation'

    @api.model
    def _cron_daily(self):
        counts = super()._cron_daily() or {}
        if flag(self.env, P_FOLLOWUP_ON):
            counts['followups'] = self._leg(
                'ask managers whether the course made a difference',
                lambda: self._send_followups(fields.Date.today()))
        return counts

    @api.model
    def _send_followups(self, today=None, rows=None):
        """Every planned follow-up that is due, once. Capped like the other
        mail legs (the cap is a safety rail)."""
        today = today or fields.Date.today()
        cap = number(self.env, P_REMINDER_CAP, 400)
        if rows is None:
            rows = self.env['pb.training.followup'].sudo().search(
                [('state', '=', 'planned'), ('due_date', '<=', today)],
                order='due_date asc, id asc', limit=cap)
        sent = 0
        for row in rows:
            if leg(self.env, 'send follow-up %s' % row.id, row._send):
                sent += 1
        return sent
