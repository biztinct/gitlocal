# -*- coding: utf-8 -*-
"""What the panel thought — asked by link, answered without a login.

THE PERSON WITH THE OPINION IS OFTEN THE PERSON WITHOUT AN ACCOUNT. A plant
manager who interviews two people a year does not have a Payobook login and
should not need one to say what they thought. So the LINK IS THE CREDENTIAL:
one unguessable token addressing one opinion, a page that shows only what that
person needs, and the same courteous answer for a token that is finished as for
one that never existed. Exactly the shape `pb.feedback.request` established for
peer reviews (`pb_lifecycle/models/feedback.py:31`).

WHY A TIMER AT ALL. An opinion given the next morning is a different and better
opinion than one given a fortnight later, and a candidate waiting on three
people is waiting on the slowest of them. Twenty-four WORKING hours is long
enough to sleep on it and short enough that nobody has forgotten the
conversation. Late is chased once, by name, and never twice.

THE CRITERIA ARE A TEMPLATE, not a fixed list. Five ship with the product
because a blank scoring sheet is a scoring sheet nobody fills in; a company
that scores something else edits them under Settings and the next interview
asks the new questions.
"""

import json
import logging
import secrets

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .hiring_common import (
    FEEDBACK_STATES, RECOMMENDATIONS, counted, leg,
)

_logger = logging.getLogger(__name__)

_TODO = 'mail.mail_activity_data_todo'

#: A public form must never be usable to post a book.
_MAX_NOTES = 4000


class PbHiringCriterion(models.Model):
    _name = 'pb.hiring.criterion'
    _description = 'Interview scoring line'
    _order = 'sequence, id'

    name = fields.Char(string='What is being judged', required=True,
                       translate=True)
    sequence = fields.Integer(string='Order', default=10)
    help_text = fields.Char(
        string='What a five looks like', translate=True,
        help='One sentence under the line, so two people scoring the same '
             'candidate mean the same thing by a four.')
    active = fields.Boolean(string='In use', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        help='Leave empty and every company uses it.')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Scoring line')

    @api.model
    def criteria_for(self, company=None):
        """The lines this company scores on: its own, plus the shared ones.

        Company-less rows are the shipped five (R8 — a seed that carries a
        company installs onto whichever company ran the install and is then
        invisible to every other one).
        """
        from .hiring_common import as_id
        company_id = as_id(company) or self.env.company.id
        rows = self.sudo().search(
            ['|', ('company_id', '=', False), ('company_id', '=', company_id)])
        return [{'id': r.id, 'name': r.name or '', 'help': r.help_text or ''}
                for r in rows]


class PbHiringFeedback(models.Model):
    _name = 'pb.hiring.feedback'
    _description = 'Interview opinion'
    _order = 'due_at, id'

    interview_id = fields.Many2one(
        'pb.hiring.interview', string='The interview', required=True,
        index=True, ondelete='cascade')
    panel_employee_id = fields.Many2one(
        'hr.employee', string='Who was asked', required=True, index=True,
        ondelete='cascade')
    panel_user_id = fields.Many2one(
        'res.users', string='Who was asked (login)', index=True,
        compute='_compute_panel_user', store=True, readonly=True)
    applicant_id = fields.Many2one(
        'hr.applicant', related='interview_id.applicant_id', store=True,
        index=True, readonly=True, string='Candidate')
    requisition_id = fields.Many2one(
        'pb.hiring.requisition', related='interview_id.requisition_id',
        store=True, index=True, readonly=True, string='Hiring request')

    # NO FIELD-LEVEL `groups=` ON THE TOKEN (R13). It is resolved at registry
    # load, which on a fresh install runs before this module's security data
    # exists, and it refuses the very `create` that mints the value. The token
    # is protected by the access list, the record rule, and by never appearing
    # in a view or a payload.
    token = fields.Char(string='Link key', index=True, copy=False,
                        readonly=True)
    due_at = fields.Datetime(string='Wanted by', index=True, readonly=True)
    state = fields.Selection(FEEDBACK_STATES, string='Status',
                             default='pending', required=True, index=True,
                             copy=False)
    ratings_json = fields.Text(string='The scores', readonly=True)
    recommendation = fields.Selection(RECOMMENDATIONS, string='Would you hire',
                                      copy=False)
    notes = fields.Text(string='What they said', copy=False)
    submitted_at = fields.Datetime(string='Answered on', readonly=True,
                                   copy=False)
    urgent_sent_at = fields.Datetime(string='Chased on', readonly=True,
                                     copy=False)
    score_avg = fields.Float(string='Average score', compute='_compute_score',
                             store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)

    _token_uniq = models.Constraint(
        'unique(token)', 'Two feedback links cannot share the same key.')
    _one_per_member = models.Constraint(
        'unique(interview_id, panel_employee_id)',
        'Somebody can only be asked once about one interview.')

    # =====================================================================
    #  Names, computes, creation
    # =====================================================================
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _(
                '%(who)s on %(candidate)s',
                who=rec.panel_employee_id.sudo().name or _('a panel member'),
                candidate=rec.interview_id.candidate_name or _('a candidate'))

    @api.depends('panel_employee_id')
    def _compute_panel_user(self):
        for rec in self:
            rec.panel_user_id = rec.panel_employee_id.sudo().user_id

    @api.depends('ratings_json')
    def _compute_score(self):
        for rec in self:
            scores = [r.get('score') for r in rec._ratings()
                      if isinstance(r.get('score'), (int, float))]
            rec.score_avg = (sum(scores) / len(scores)) if scores else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('token'):
                vals['token'] = secrets.token_urlsafe(24)
        return super().create(vals_list)

    def _ratings(self):
        self.ensure_one()
        if not self.ratings_json:
            return []
        try:
            loaded = json.loads(self.ratings_json)
        except Exception:               # noqa: BLE001
            _logger.warning('pb_hiring: the scores on opinion %s are not '
                            'readable', self.id)
            return []
        return loaded if isinstance(loaded, list) else []

    # =====================================================================
    #  The link
    # =====================================================================
    def _token_url(self):
        self.ensure_one()
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        return '%s/hiring/f/%s' % (base.rstrip('/'), self.sudo().token)

    @api.model
    def _request_for_token(self, token):
        """`(record, status)` — and a stranger probing the URL space learns
        nothing from the difference between a wrong key and a finished one."""
        blank = self.browse()
        if not token or len(token) < 12:
            return blank, 'invalid'
        row = self.sudo().search([('token', '=', token)], limit=1)
        if not row:
            return blank, 'invalid'
        if row.state == 'submitted':
            return row, 'used'
        if row.state == 'expired':
            return row, 'closed'
        # BEING LATE DOES NOT CLOSE THE LINK, and that is deliberate. The
        # whole purpose of the urgent chase is to get a late opinion IN; a
        # link that shut itself at the deadline would make the chase a lie.
        return row, 'ok'

    def questions(self):
        """What the page asks, from the criteria this company scores on."""
        self.ensure_one()
        return self.env['pb.hiring.criterion'].criteria_for(self.company_id)

    def page_facts(self):
        """The little a panel member needs to see, and nothing else.

        No id, no department, no salary expectation, no link into the
        backend: the page is for one opinion about one hour.
        """
        self.ensure_one()
        interview = self.interview_id.sudo()
        return {
            'candidate': interview.candidate_name or '',
            'role': interview.requisition_id.title or '',
            'round': interview.round_no or 1,
            'when': str(interview.start or '')[:16],
            'due': str(self.due_at or '')[:16],
            'company': self.company_id.name or '',
            'late': bool(self.due_at and self.due_at < fields.Datetime.now()),
            'recommendations': [{'key': k, 'label': v}
                                for k, v in RECOMMENDATIONS],
        }

    # =====================================================================
    #  Answering
    # =====================================================================
    def submit(self, ratings, recommendation=None, notes=None):
        """Record one opinion. Called from the public route only."""
        self.ensure_one()
        if self.state != 'pending':
            return False
        clean = []
        known = {c['id']: c['name']
                 for c in self.env['pb.hiring.criterion'].criteria_for(
                     self.company_id)}
        for raw in (ratings or []):
            try:
                cid = int(raw.get('id'))
                score = int(raw.get('score'))
            except (AttributeError, TypeError, ValueError):
                continue
            if cid not in known or not 1 <= score <= 5:
                continue
            clean.append({'id': cid, 'name': known[cid], 'score': score})
        if recommendation not in dict(RECOMMENDATIONS):
            recommendation = False
        self.sudo().write({
            'ratings_json': json.dumps(clean),
            'recommendation': recommendation,
            'notes': (notes or '').strip()[:_MAX_NOTES],
            'state': 'submitted',
            'submitted_at': fields.Datetime.now(),
        })
        leg(self.env, 'the summary for interview %s' % self.interview_id.id,
            self._summarise_if_complete)
        return True

    def _summarise_if_complete(self):
        """When the last opinion lands, say so in ONE place.

        A chatter line per answer is three lines nobody reads; one line when
        the set is complete is the moment somebody can act on. The recruiter
        gets a to-do at the same instant, because "everybody has answered" is
        the only signal that the round can be closed.
        """
        self.ensure_one()
        interview = self.interview_id.sudo()
        rows = interview.feedback_ids.filtered(lambda f: f.state != 'expired')
        if not rows or any(r.state != 'submitted' for r in rows):
            return False
        labels = dict(RECOMMENDATIONS)
        # `message_post` ESCAPES A PLAIN STRING BODY, so a `<br/>` built into
        # a `_()` sentence lands in the chatter as the four characters
        # `&lt;br/&gt;` and the summary reads as one run-on line with its own
        # markup in it (R51, from the writing side). Only `Markup` is rendered
        # raw — and `Markup('%s') % value` escapes each interpolated value, so
        # a panel member called "Nguyễn <script>" cannot inject anything.
        lines = [
            Markup('%(who)s — %(verdict)s (%(score)s out of 5). %(notes)s') % {
                'who': row.panel_employee_id.sudo().name or '',
                'verdict': labels.get(row.recommendation, _('no answer')),
                'score': round(row.score_avg, 1),
                'notes': (row.notes or '').strip(),
            }
            for row in rows.sorted('id')
        ]
        headline = _("Everybody has answered — %(n)s %(word)s in.",
                     n=len(rows),
                     word=counted(len(rows), _('opinion'), _('opinions')))
        interview.message_post(
            body=Markup('%s<br/>%s') % (headline, Markup('<br/>').join(lines)))
        if interview.recruiter_id:
            interview.activity_schedule(
                _TODO,
                summary=_('Decide the next step: %s',
                          interview.candidate_name or ''),
                note=_("Every opinion is in. The average is %(avg)s out of 4. "
                       "Move them to the next round, or tell them it is not "
                       "this time.",
                       avg=round(interview.recommendation_avg, 1)),
                user_id=interview.recruiter_id.id,
                date_deadline=fields.Date.context_today(self))
        return True

    # =====================================================================
    #  The chase
    # =====================================================================
    def _chase(self):
        """ONE urgent mail per late opinion, ever, and a to-do for the
        recruiter beside it. Stamped, so a daily job cannot nag."""
        self.ensure_one()
        if self.state != 'pending' or self.urgent_sent_at:
            return False
        employee = self.panel_employee_id.sudo()
        address = (employee.user_id.email or '').strip() \
            or (employee.work_email or '').strip()
        template = self.env.ref('pb_hiring.mail_template_feedback_urgent',
                                raise_if_not_found=False)
        if address and template:
            template.sudo().send_mail(
                self.id, force_send=False,
                email_values={'email_to': address, 'auto_delete': False})
        else:
            _logger.info('pb_hiring: opinion %s is late and there is nobody '
                         'to chase', self.id)
        self.sudo().write({'urgent_sent_at': fields.Datetime.now()})
        recruiter = self.interview_id.sudo().recruiter_id
        if recruiter:
            self.interview_id.sudo().activity_schedule(
                _TODO,
                summary=_('Chase an opinion: %s',
                          employee.name or ''),
                note=_("%(who)s was asked what they thought of %(candidate)s "
                       "and the window has passed. Their link still works.",
                       who=employee.name or '',
                       candidate=self.interview_id.candidate_name or ''),
                user_id=recruiter.id,
                date_deadline=fields.Date.context_today(self))
        return True

    # ------------------------------------------------------------- the door
    def action_open_interview(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.hiring.interview',
                'res_id': self.interview_id.id, 'view_mode': 'form',
                'views': [[False, 'form']],
                'name': self.interview_id.display_name}

    def action_copy_link(self):
        """The recruiter's own escape hatch: the link, said out loud.

        A panel member whose mail bounced is a very ordinary problem, and
        without this the only fix is a database query.
        """
        self.ensure_one()
        if not self.env.user.has_group('pb_hiring.group_hiring_user'):
            raise UserError(_(
                "Only the hiring team can read somebody else's feedback "
                "link."))
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'info', 'sticky': True,
                       'title': _('Their own link'),
                       'message': self._token_url()},
        }
