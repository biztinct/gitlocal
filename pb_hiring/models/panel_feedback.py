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
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .hiring_common import (
    DECISIONS, FEEDBACK_STATES, P_CHASE_EVERY_HOURS, RECOMMENDATION_DECISION,
    RECOMMENDATIONS, as_id, counted, leg, number,
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

    # ---------------------------------------------------- RECRUIT P5 (G-32)
    scorecard_id = fields.Many2one('pb.hiring.scorecard', string='Scorecard',
                                   ondelete='set null', index=True)
    #: `[{part_id, kind, prompt, value}]` — self-describing, so an answer
    #: still reads correctly after the scorecard is reworded.
    answers_json = fields.Text(string='The answers', readonly=True, copy=False)
    decision = fields.Selection(DECISIONS, string='Their decision', index=True,
                                copy=False)
    entered_by_user_id = fields.Many2one(
        'res.users', string='Entered by', readonly=True, copy=False,
        help='Set when a recruiter typed the opinion in for the panellist.')
    entered_via = fields.Char(string='Where it came from', readonly=True,
                              copy=False)
    entered_on = fields.Datetime(string='Entered on', readonly=True, copy=False)
    invited_at = fields.Datetime(string='Link sent', readonly=True, copy=False)
    ask_sent_at = fields.Datetime(string='"How did it go?" sent', readonly=True,
                                  copy=False)
    reminder_count = fields.Integer(string='Reminders sent', readonly=True,
                                    default=0, copy=False)
    last_reminded_at = fields.Datetime(string='Last reminded', readonly=True,
                                       copy=False)
    lead_told_at = fields.Datetime(string='Talent lead told', readonly=True,
                                   copy=False)
    # Public computes for the mail templates (RC49: a template calls no
    # private method).
    pb_link_url = fields.Char(string='Their link', compute='_compute_pb_mail_words')
    pb_due_local = fields.Char(compute='_compute_pb_mail_words')
    pb_round_label = fields.Char(compute='_compute_pb_mail_words')
    pb_late_days = fields.Integer(compute='_compute_pb_mail_words')

    def _compute_pb_mail_words(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.id:
                rec.pb_link_url = rec.pb_due_local = rec.pb_round_label = ''
                rec.pb_late_days = 0
                continue
            rec.pb_link_url = rec._token_url() if rec.sudo().token else ''
            rec.pb_due_local = rec._local(rec.due_at)
            card = rec.sudo().scorecard_id or rec.sudo().interview_id.scorecard_id
            rec.pb_round_label = card.name if card else \
                _('Round %s', rec.sudo().interview_id.round_no or 1)
            rec.pb_late_days = max(0, (now - rec.due_at).days) if rec.due_at else 0

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

    @api.depends('ratings_json', 'answers_json')
    def _compute_score(self):
        """The mean of every star rating and scored line (RECRUIT P5); the
        five old lines for an opinion given before scorecards."""
        for rec in self:
            scores = [a.get('value') for a in rec._answers()
                      if a.get('kind') in ('rating', 'line')
                      and isinstance(a.get('value'), (int, float))]
            if not scores:
                scores = [r.get('score') for r in rec._ratings()
                          if isinstance(r.get('score'), (int, float))]
            rec.score_avg = (sum(scores) / len(scores)) if scores else 0.0

    def _answers(self):
        self.ensure_one()
        if not self.answers_json:
            return []
        try:
            loaded = json.loads(self.answers_json)
        except Exception:               # noqa: BLE001
            _logger.warning('pb_hiring: the answers on opinion %s are not '
                            'readable', self.id)
            return []
        return loaded if isinstance(loaded, list) else []

    def _answer_map(self):
        """{part_id: value} for the answers that have a part."""
        self.ensure_one()
        return {a['part_id']: a.get('value') for a in self._answers()
                if a.get('part_id')}

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
            # RECRUIT P5: an answer can be changed until the recruiter
            # decides; after that the link says it is done.
            return row, ('ok' if row._editable() else 'used')
        if row.state == 'expired':
            return row, 'closed'
        # BEING LATE DOES NOT CLOSE THE LINK, and that is deliberate. The
        # whole purpose of the urgent chase is to get a late opinion IN; a
        # link that shut itself at the deadline would make the chase a lie.
        return row, 'ok'

    def questions(self):
        """The five shipped scoring lines (kept for the opinions given
        before scorecards, and for callers that still score on them)."""
        self.ensure_one()
        return self.env['pb.hiring.criterion'].criteria_for(self.company_id)

    # =====================================================================
    #  RECRUIT P5 — the scorecard this opinion is written on
    # =====================================================================
    def _ensure_scorecard(self):
        self.ensure_one()
        if self.scorecard_id:
            return self.scorecard_id
        interview = self.interview_id.sudo()
        card = interview.scorecard_id or interview._pb_default_scorecard()
        if card:
            self.sudo().write({'scorecard_id': card.id})
        return card

    def _editable(self):
        """An answer can be changed until the recruiter decides: the round's
        debrief, or the candidate moving to an offer or a closed outcome."""
        self.ensure_one()
        interview = self.interview_id.sudo()
        if interview.decision or interview.state in ('cancelled', 'rescheduled', 'no_show'):
            return False
        app = self.applicant_id.sudo().with_context(active_test=False)
        stage = app.stage_id
        if not app.active or (stage.pb_family or 'open') != 'open' \
                or stage.pb_key in ('offer', 'post_offer'):
            return False
        return True

    def parts_for_page(self):
        """The questions the interviewer answers, in order, each with the
        answer already given (an edit, or a draft from the recruiter)."""
        self.ensure_one()
        card = self._ensure_scorecard()
        given = self._answer_map()
        return [dict(p._payload(), value=given.get(p.id))
                for p in card._parts_sorted()] if card else []

    def _local(self, when, fmt='%a %d %b, %H:%M'):
        """A stored UTC time in the recruiter's own time zone, with the zone
        named, because the panellist may be anywhere."""
        if not when:
            return ''
        import pytz
        user = self.interview_id.sudo().recruiter_id
        tzname = user.tz or self.company_id.partner_id.tz or 'UTC'
        try:
            tz = pytz.timezone(tzname)
        except Exception:               # noqa: BLE001
            tz, tzname = pytz.utc, 'UTC'
        local = pytz.utc.localize(when).astimezone(tz)
        return '%s (%s)' % (local.strftime(fmt), tzname.split('/')[-1].replace('_', ' '))

    def _cv_link(self):
        """The CV, when the panellist may read it: their own share (P4) if
        they have a login, else the role's default "the hiring manager and
        the panel" with CV ticked. A private, tokened link."""
        self.ensure_one()
        from .privacy_p4 import _split
        app = self.applicant_id.sudo()
        req = self.requisition_id.sudo()
        user = self.panel_user_id
        allowed = False
        if user:
            allowed = 'cv' in self.env['pb.hiring.share'].parts_for(app, user)
        if not allowed and req:
            allowed = req.default_share_with == 'hiring_manager_and_panel' \
                and 'cv' in _split(req.default_share_parts)
        if not allowed:
            return ''
        docs = self.env['pb.hiring']._doc_rows(app, parts={'cv'}, tokenised=True)
        if not docs:
            return ''
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        return base.rstrip('/') + docs[0]['url']

    def page_facts(self):
        """The little a panel member needs to see, and nothing else.

        No id, no department, no salary expectation, no link into the
        backend, and NOTHING another panellist said: the page is for one
        opinion about one hour.
        """
        self.ensure_one()
        interview = self.interview_id.sudo()
        card = self._ensure_scorecard()
        company = self.company_id.sudo()
        brand = company._hiring_brand() if hasattr(company, '_hiring_brand') else company.name
        panel = interview.panel_employee_ids.mapped('name')
        me = self.panel_employee_id.sudo().name or ''
        return {
            'candidate': interview.candidate_name or '',
            'role': interview.requisition_id.title or '',
            'round': interview.round_no or 1,
            'round_label': card.name if card else _('Round %s', interview.round_no or 1),
            'when': self._local(interview.start),
            'due': self._local(self.due_at),
            'company': company.name or '',
            'brand': brand or '',
            'late': bool(self.state == 'pending' and self.due_at
                         and self.due_at < fields.Datetime.now()),
            'me': me,
            'others': [n for n in panel if n != me],
            'intro': (card.intro or '') if card else '',
            'video': interview.videocall_url or '',
            'cv': self._cv_link(),
            'answered': self.state == 'submitted',
            'decision': self.decision or '',
            'notes': self.notes or '',
            'submitted_on': self._local(self.submitted_at),
            'decisions': [{'key': k, 'label': v} for k, v in DECISIONS],
            'recommendations': [{'key': k, 'label': v}
                                for k, v in RECOMMENDATIONS],
        }

    # =====================================================================
    #  Answering
    # =====================================================================
    def submit(self, ratings, recommendation=None, notes=None):
        """The scored-lines answer (A2's page, and its callers). RECRUIT P5:
        the recommendation is read as a decision, the lines as answers; an
        answer can be changed until the recruiter decides."""
        self.ensure_one()
        if self.state == 'expired' or (self.state == 'submitted' and not self._editable()):
            return False
        first = self.state == 'pending'
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
            'answers_json': json.dumps([{'part_id': False, 'kind': 'line',
                                         'prompt': r['name'], 'value': r['score'],
                                         'criterion_id': r['id']} for r in clean]),
            'recommendation': recommendation,
            'decision': RECOMMENDATION_DECISION.get(recommendation) or False,
            'notes': (notes or '').strip()[:_MAX_NOTES],
            'state': 'submitted',
            'submitted_at': fields.Datetime.now(),
        })
        if first:
            leg(self.env, 'the summary for interview %s' % self.interview_id.id,
                self._summarise_if_complete)
        return True

    def _clean_answers(self, answers):
        """Every answer checked against the scorecard: numbers 1–5, yes/no,
        text cut to length; a required question left empty is named."""
        self.ensure_one()
        card = self._ensure_scorecard()
        if isinstance(answers, dict):
            given = {as_id(k): v for k, v in answers.items()}
        else:
            given = {as_id(a.get('part_id')): a.get('value')
                     for a in (answers or []) if isinstance(a, dict)}
        out, missing = [], []
        for part in (card._parts_sorted() if card else []):
            raw = given.get(part.id)
            value = None
            if part.kind in ('rating', 'line'):
                try:
                    value = int(raw)
                except (TypeError, ValueError):
                    value = None
                if value is not None and not 1 <= value <= 5:
                    value = None
            elif part.kind == 'yes_no':
                value = raw if raw in ('yes', 'no') else None
            else:
                value = (str(raw).strip()[:_MAX_NOTES] if raw not in (None, False) else '') or None
            if value is None:
                if part.required:
                    missing.append(part.prompt or '')
                continue
            out.append({'part_id': part.id, 'kind': part.kind,
                        'prompt': part.prompt or '', 'value': value})
        return out, missing

    def submit_answers(self, answers, decision, notes=None, by_user=None, via=None):
        """One opinion on the scorecard (the interviewer's page, or a
        recruiter typing it in for them with `by_user` and `via`).

        Refused with a sentence when a required question or the decision is
        missing. An answer already given can be changed until the recruiter
        decides (`_editable`)."""
        self.ensure_one()
        if self.state == 'expired':
            raise UserError(_("This opinion is no longer being asked for."))
        if self.state == 'submitted' and not self._editable():
            raise UserError(_("The recruiter has already decided on this round, so the "
                              "answer can no longer change."))
        clean, missing = self._clean_answers(answers)
        if missing:
            raise UserError(_("Answer these first: %s", ', '.join(missing)))
        if decision not in dict(DECISIONS):
            raise UserError(_("Choose Yes, Maybe, No or Hold."))
        first = self.state == 'pending'
        vals = {
            'answers_json': json.dumps(clean),
            'decision': decision,
            'notes': (notes or '').strip()[:_MAX_NOTES],
            'state': 'submitted',
            'submitted_at': fields.Datetime.now(),
        }
        if by_user:
            vals.update({'entered_by_user_id': as_id(by_user),
                         'entered_via': (via or '').strip()[:120] or False,
                         'entered_on': fields.Datetime.now()})
        elif first:
            vals.update({'entered_by_user_id': False, 'entered_via': False,
                         'entered_on': False})
        self.sudo().write(vals)
        if first:
            leg(self.env, 'the summary for interview %s' % self.interview_id.id,
                self._summarise_if_complete)
        else:
            who = self.panel_employee_id.sudo().name or ''
            leg(self.env, 'the change note on opinion %s' % self.id,
                lambda: self.interview_id.sudo().message_post(
                    body=_("%(who)s changed their scorecard: %(what)s.", who=who,
                           what=dict(DECISIONS).get(decision, ''))))
        return True

    def _entered_words(self):
        """"entered by An (Slack message, 3 Oct)" — or nothing."""
        self.ensure_one()
        if not self.entered_by_user_id:
            return ''
        when = (self.entered_on or fields.Datetime.now()).strftime('%d %b').lstrip('0')
        via = self.entered_via or ''
        bits = ', '.join(b for b in (via, when) if b)
        return _('entered by %(who)s (%(how)s)', who=self.entered_by_user_id.name or '',
                 how=bits)

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
        labels = dict(DECISIONS)
        old = dict(RECOMMENDATIONS)
        # `message_post` ESCAPES A PLAIN STRING BODY, so a `<br/>` built into
        # a `_()` sentence lands in the chatter as the four characters
        # `&lt;br/&gt;` and the summary reads as one run-on line with its own
        # markup in it (R51, from the writing side). Only `Markup` is rendered
        # raw — and `Markup('%s') % value` escapes each interpolated value, so
        # a panel member called "Nguyễn <script>" cannot inject anything.
        lines = [
            Markup('%(who)s — %(verdict)s (%(score)s out of 5). %(notes)s %(entered)s') % {
                'who': row.panel_employee_id.sudo().name or '',
                'verdict': labels.get(row.decision) or old.get(row.recommendation)
                or _('no answer'),
                'score': round(row.score_avg, 1),
                'notes': (row.notes or '').strip(),
                'entered': ('· ' + row._entered_words()) if row.entered_by_user_id else '',
            }
            for row in rows.sorted('id')
        ]
        headline = _("Everybody has answered — %(n)s %(word)s in.",
                     n=len(rows),
                     word=counted(len(rows), _('opinion'), _('opinions')))
        interview.message_post(
            body=Markup('%s<br/>%s') % (headline, Markup('<br/>').join(lines)))
        if interview.recruiter_id:
            counts = {}
            for row in rows:
                if row.decision:
                    counts[row.decision] = counts.get(row.decision, 0) + 1
            tally = ', '.join('%s %s' % (n, labels[k]) for k, n in
                              sorted(counts.items(), key=lambda kv: list(labels).index(kv[0])))
            interview.activity_schedule(
                _TODO,
                summary=_('Decide the next step: %s',
                          interview.candidate_name or ''),
                note=_("Every opinion is in: %(tally)s. Move them to the next "
                       "round, or tell them it is not this time.",
                       tally=tally or _('no decisions')),
                user_id=interview.recruiter_id.id,
                date_deadline=fields.Date.context_today(self))
        return True

    # =====================================================================
    #  The chase — RECRUIT P5: repeated until it lands
    # =====================================================================
    def _address(self):
        self.ensure_one()
        employee = self.panel_employee_id.sudo()
        return (employee.user_id.email or '').strip() \
            or (employee.work_email or '').strip()

    def _send_template(self, xmlid, to=None):
        self.ensure_one()
        to = to or self._address()
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not (to and template):
            return False
        template.sudo().send_mail(
            self.id, force_send=False,
            email_values={'email_to': to, 'auto_delete': False})
        return True

    def _chase(self, manual=False):
        """One reminder, then another every day until the opinion lands
        (G-32). Stamped, so a job that runs every ten minutes still sends at
        most one a day; `manual` is the recruiter's own "Remind" press.
        The recruiter's to-do is raised once, on the first reminder."""
        self.ensure_one()
        if self.state != 'pending':
            return False
        now = fields.Datetime.now()
        every = max(1, number(self.env, P_CHASE_EVERY_HOURS, 24))
        if not manual and self.last_reminded_at \
                and self.last_reminded_at > now - timedelta(hours=every):
            return False
        first = not self.urgent_sent_at
        vals = {'last_reminded_at': now, 'reminder_count': (self.reminder_count or 0) + 1}
        if first:
            vals['urgent_sent_at'] = now
        self.sudo().write(vals)
        if not self._send_template('pb_hiring.mail_template_feedback_urgent'):
            _logger.info('pb_hiring: opinion %s is late and there is nobody '
                         'to chase', self.id)
        employee = self.panel_employee_id.sudo()
        recruiter = self.interview_id.sudo().recruiter_id
        if first and recruiter:
            self.interview_id.sudo().activity_schedule(
                _TODO,
                summary=_('Chase an opinion: %s',
                          employee.name or ''),
                note=_("%(who)s was asked what they thought of %(candidate)s "
                       "and the window has passed. They are reminded every day; "
                       "their link still works, and you can enter it for them.",
                       who=employee.name or '',
                       candidate=self.interview_id.candidate_name or ''),
                user_id=recruiter.id,
                date_deadline=fields.Date.context_today(self))
        return True

    def _lead_uids(self):
        """The talent leads of this company — the hiring managers' tier —
        and, when nobody holds it, the Head of hiring."""
        self.ensure_one()
        company = self.company_id
        for xmlid in ('pb_hiring.group_hiring_manager', 'pb_hiring.group_hiring_admin'):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if not group:
                continue
            users = group.sudo().all_user_ids.filtered(
                lambda u: u.active and not u.share and company in u.company_ids
                and u.id != self.env.ref('base.user_root').id)
            # Not the admin accounts the security file puts in every tier.
            users = users.filtered(lambda u: u.id != 2) or users
            if users:
                return users.sorted('id')
        return self.env['res.users']

    def _tell_lead(self):
        """Two days late: the Talent lead gets one email and a to-do, once."""
        self.ensure_one()
        if self.state != 'pending' or self.lead_told_at:
            return False
        self.sudo().write({'lead_told_at': fields.Datetime.now()})
        interview = self.interview_id.sudo()
        who = self.panel_employee_id.sudo().name or ''
        for user in self._lead_uids()[:5]:
            if user.email:
                self._send_template('pb_hiring.mail_template_feedback_lead', to=user.email)
            interview.activity_schedule(
                _TODO,
                summary=_("%s's opinion is two days late", who),
                note=_("%(who)s has not said what they thought of %(candidate)s "
                       "(round %(n)s). They are reminded every day. The recruiter "
                       "can enter it for them from the candidate's page.",
                       who=who, candidate=interview.candidate_name or '',
                       n=interview.round_no or 1),
                user_id=user.id,
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
