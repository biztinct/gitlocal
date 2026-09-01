# -*- coding: utf-8 -*-
"""One trial period, walked from "the date is coming" to "here is the letter".

SEVEN STOPS, AND A REVIEW IS ONLY EVER AT ONE OF THEM:

    scheduled      the date is known, nobody has been asked anything
    nomination     the manager has been asked for three to five colleagues
    feedback       those colleagues have links, with a window on them
    consolidation  the answers are in (or the window shut) and are being read
    one_on_one     the manager has the conversation
    verdict        somebody has to decide
    closed         they decided, and the letter went out

WHAT MAKES THIS RE-USABLE BY P10. `kind` is `probation` or `conversion`, and
every method below is written against the FIELD rather than against the word:
the entry point takes a kind, the letters are looked up by a mapping keyed on
it, and the verdict hook `_on_verdict()` is deliberately empty so a later phase
can act on a decision without editing this file. P10 turns a fixed-term
contract into a permanent one by calling `open_for(employee, kind='conversion')`
and overriding that hook. This phase ships the field, not the flow.

EVERY WRITE IS GUARDED AND CHATTERED. A trial period is the most consequential
thing in this module — somebody's job is on the end of it — so nothing here
happens quietly: each transition posts what it did and why, and each refusal
says in words what is missing rather than raising a state error.
"""

import json
import logging
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .probation_common import (
    GROUP_MANAGER, MAX_NOMINEES, MIN_NOMINEES, P_PROBATION_MAIL,
    PEER_QUESTIONS, PEER_QUESTION_LABEL, PEER_RATING_KEYS, REVIEW_KINDS,
    REVIEW_KIND_LABEL, REVIEW_OPEN, REVIEW_STATE_LABEL, REVIEW_STATES,
    VERDICT_LABEL, VERDICTS, add_months, counted, first_name, flag,
    joined_sentence,
)

_logger = logging.getLogger(__name__)

#: Which letter each verdict prepares. Keyed on the verdict rather than
#: branched on in three places, so the day somebody adds a fourth outcome the
#: letter follows it.
VERDICT_LETTER = {
    'pass': 'pb_lifecycle.letter_template_probation_pass',
    'extend': 'pb_probation.letter_template_probation_extend',
    'fail': 'pb_probation.letter_template_probation_fail',
}

#: What each verdict leaves on the employee record.
VERDICT_STATE = {'pass': 'passed', 'extend': 'extended', 'fail': 'failed'}

#: How long the manager has for the 1:1 once the answers are in.
ONE_ON_ONE_DUE_DAYS = 2


class PbProbationReview(models.Model):
    _name = 'pb.probation.review'
    _description = 'Probation Review'
    # `mail.activity.mixin` as well as `mail.thread`, and it is load-bearing:
    # `activity_schedule()` lives on the ACTIVITY mixin, not on the thread one
    # (R3), and the HR reminders raise their to-dos through it.
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'trial_end, id'

    name = fields.Char(compute='_compute_name', store=True, string='Review')
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='cascade', tracking=True)
    kind = fields.Selection(
        REVIEW_KINDS, string='What this is', required=True, default='probation',
        tracking=True)
    round = fields.Integer(
        string='Round', default=1, required=True,
        help='1 for the first review, 2 after an extension, and so on.')
    trial_end = fields.Date(
        string='Trial period ends', index=True, tracking=True,
        help='A snapshot, taken when the review opened. Moving the date on the '
             'employee record later does not re-plan a review somebody has '
             'already started working to.')
    manager_user_id = fields.Many2one(
        'res.users', string='Manager', index=True, ondelete='set null')
    hrbp_user_id = fields.Many2one(
        'res.users', string='HR partner', ondelete='set null')
    case_id = fields.Many2one(
        'pb.journey.case', string='Journey', index=True, ondelete='set null')
    policy_id = fields.Many2one(
        'pb.probation.policy', string='Policy used', ondelete='set null')
    state = fields.Selection(
        REVIEW_STATES, string='Status', default='scheduled', required=True,
        index=True, tracking=True)

    nominee_ids = fields.Many2many(
        'hr.employee', 'pb_probation_review_nominee_rel', 'review_id',
        'employee_id', string='Colleagues asked')
    nominee_count = fields.Integer(
        compute='_compute_feedback_state', string='Colleagues asked')
    feedback_request_ids = fields.One2many(
        'pb.feedback.request', 'probation_review_id', string='Feedback links')
    feedback_deadline = fields.Date(string='Answers by', index=True)
    feedback_total = fields.Integer(
        compute='_compute_feedback_state', string='Links sent')
    feedback_in = fields.Integer(
        compute='_compute_feedback_state', string='Answers in')
    deadline_extended = fields.Boolean(
        string='Deadline already stretched', readonly=True, copy=False)
    deadline_alerted = fields.Boolean(
        string='Last-hours alert sent', readonly=True, copy=False)
    remind_far_done = fields.Boolean(readonly=True, copy=False)
    remind_near_done = fields.Boolean(readonly=True, copy=False)

    consolidated_html = fields.Html(
        string='What everybody said', sanitize=False, readonly=True)
    consolidated_at = fields.Datetime(string='Put together on', readonly=True)
    avg_rating = fields.Float(string='Average rating', digits=(3, 2),
                              readonly=True)
    one_on_one_checkin_id = fields.Many2one(
        'pb.employee.checkin', string='The conversation', ondelete='set null')

    verdict = fields.Selection(VERDICTS, string='Decision', tracking=True)
    verdict_at = fields.Datetime(string='Decided on', readonly=True)
    verdict_by = fields.Many2one('res.users', string='Decided by',
                                 readonly=True)
    strengths = fields.Text(string='What they are good at')
    improvements = fields.Text(string='What to work on')
    extension_months = fields.Integer(string='Extended by (months)')
    new_trial_end = fields.Date(string='New trial end', readonly=True)
    letter_id = fields.Many2one('pb.hr.letter', string='Letter',
                                readonly=True, ondelete='set null')
    exit_case_id = fields.Many2one(
        'pb.journey.case', string='Leaving checklist', readonly=True,
        ondelete='set null')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    # ------------------------------------------------------------- computes
    @api.depends('employee_id', 'kind', 'round')
    def _compute_name(self):
        for rec in self:
            rec.name = _(
                '%(who)s — %(kind)s review%(round)s',
                who=rec.employee_id.name or _('Employee'),
                kind=REVIEW_KIND_LABEL.get(rec.kind, rec.kind or '').lower(),
                round=(_(' (round %s)', rec.round) if rec.round > 1 else ''))

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Probation review')

    @api.depends('nominee_ids', 'feedback_request_ids.state')
    def _compute_feedback_state(self):
        for rec in self:
            rec.nominee_count = len(rec.nominee_ids)
            rows = rec.feedback_request_ids
            rec.feedback_total = len(rows)
            rec.feedback_in = len(
                [r for r in rows if r.state == 'submitted'])

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            if self.employee_id.company_id:
                self.company_id = self.employee_id.company_id
            manager = self.employee_id.parent_id
            if manager and manager.user_id:
                self.manager_user_id = manager.user_id

    # =====================================================================
    #  THE ENTRY POINT.  P10 calls this with kind='conversion'.
    # =====================================================================
    @api.model
    def open_for(self, employee, kind='probation', trial_end=None,
                 case=None, round_no=None):
        """The review for this person — one at a time, reused, never doubled.

        IDEMPOTENT BY DESIGN (R30). The daily job reaches this every night for
        the same person until the review closes, and the lens reaches it again
        when somebody presses "start the review". Both must find the same
        record. An OPEN review of the same kind is that record; a closed one is
        history and does not stop the next round.

        `employee` may be a record or an id — over JSON-RPC a recordset
        argument arrives as a plain integer (R43).
        """
        Policy = self.env['pb.probation.policy']
        employee = Policy._as_employee(employee)
        if not employee:
            raise UserError(_("Pick the person this review is about first."))
        if kind not in REVIEW_KIND_LABEL:
            kind = 'probation'
        existing = self.sudo().search([
            ('employee_id', '=', employee.id),
            ('kind', '=', kind),
            ('state', 'in', REVIEW_OPEN),
        ], order='id desc', limit=1)
        if existing:
            return existing

        settings = Policy.settings_for(employee)
        if not trial_end:
            trial_end = employee.sudo().trial_date_end \
                or Policy.trial_end_for(employee)
        if isinstance(case, int):
            case = self.env['pb.journey.case'].sudo().browse(case).exists()
        if not case:
            case = self.env['pb.journey.case'].sudo().search([
                ('employee_id', '=', employee.id),
                ('state', 'in', ('draft', 'active', 'on_hold')),
            ], order='id desc', limit=1)
        if round_no is None:
            round_no = 1 + self.sudo().search_count([
                ('employee_id', '=', employee.id), ('kind', '=', kind),
                ('state', '=', 'closed')])

        review = self.sudo().create({
            'employee_id': employee.id,
            'kind': kind,
            'round': max(1, int(round_no)),
            'trial_end': trial_end or False,
            'manager_user_id': employee.parent_id.user_id.id
            if (employee.parent_id and employee.parent_id.user_id) else False,
            'hrbp_user_id': employee.hrbp_user_id.id
            if getattr(employee, 'hrbp_user_id', False) else False,
            'case_id': case.id if case else False,
            'policy_id': settings['policy_id'] or False,
            'company_id': (employee.company_id or self.env.company).id,
        })
        # The training rows, in case a course was bound to this job after the
        # person joined. Idempotent, so calling it here as well as at the
        # joining hook costs nothing.
        try:
            self.env['pb.training.track'].ensure_for_employee(employee)
        except Exception:               # noqa: BLE001
            _logger.exception('pb_probation: training rows for employee %s',
                              employee.id)
        review.message_post(body=_(
            "Review opened. The trial period ends on %(when)s.",
            when=trial_end or _('a date nobody has set')))
        return review

    # ---------------------------------------------------------------- gates
    def _require_manager(self):
        """Who may move a review on.

        The HR team, the person's own manager, and the HR partner named on the
        review. Not "anybody with a login": a verdict writes a state onto
        somebody's employment record and prepares a letter with their name on
        it.
        """
        self.ensure_one()
        user = self.env.user
        if user.has_group(GROUP_MANAGER) or user._is_admin():
            return True
        if self.manager_user_id and self.manager_user_id.id == user.id:
            return True
        if self.hrbp_user_id and self.hrbp_user_id.id == user.id:
            return True
        raise AccessError(_(
            "Only the HR team, this person's manager or their HR partner can "
            "move a probation review on."))

    def _settings(self):
        self.ensure_one()
        return self.env['pb.probation.policy'].settings_for(self.employee_id)

    # =====================================================================
    #  1. ASK THE MANAGER FOR COLLEAGUES
    # =====================================================================
    def action_start_nomination(self):
        """Move to "peers being chosen" and ask the manager, once."""
        for rec in self:
            rec._require_manager()
            if rec.state not in ('scheduled', 'nomination'):
                raise UserError(_(
                    "This review has moved past choosing colleagues."))
            if rec.state == 'scheduled':
                rec.state = 'nomination'
                rec.message_post(body=_(
                    "%(who)s has been asked to name %(min)s to %(max)s "
                    "colleagues.",
                    who=(rec.manager_user_id.name if rec.manager_user_id
                         else _('The manager')),
                    min=MIN_NOMINEES, max=MAX_NOMINEES))
            rec._mail('pb_probation.mail_template_nominate_peers',
                      rec._manager_addresses())
        return True

    def suggest_nominees(self, term=None, limit=14):
        """Who the manager might ask: their own team first, then the rest.

        Deliberately a SUGGESTION and never a filter — the best answer is often
        the person from another team they work with every day, so the search
        box behind this reaches everybody in the company.
        """
        self.ensure_one()
        Emp = self.env['hr.employee']
        emp = self.employee_id
        if not emp:
            return []
        company = emp.company_id or self.env.company
        base = [('active', '=', True), ('id', '!=', emp.id),
                ('company_id', '=', company.id)]
        limit = max(1, min(int(limit or 14), 40))
        if term:
            found = Emp.search(base + [('name', 'ilike', term)],
                               order='name', limit=limit)
        else:
            found = Emp.browse()
            if emp.department_id:
                found = Emp.search(
                    base + [('department_id', '=', emp.department_id.id)],
                    order='name', limit=limit)
            if len(found) < limit:
                found |= Emp.search(base, order='name',
                                    limit=limit - len(found))
        return [self._nominee_card(c) for c in found]

    def _nominee_card(self, candidate):
        self.ensure_one()
        months = 0
        try:
            months = candidate._pb_tenure_months()
        except Exception:               # noqa: BLE001
            months = 0
        return {
            'id': candidate.id,
            'name': candidate.name or '',
            'job': candidate.job_title
            or (candidate.job_id.name if candidate.job_id else '') or '',
            'dept': candidate.department_id.name
            if candidate.department_id else '',
            'avatar': '/web/image/hr.employee/%s/avatar_128' % candidate.id,
            'tenure': months,
            'same_team': bool(
                self.employee_id.department_id and candidate.department_id
                and self.employee_id.department_id.id
                == candidate.department_id.id),
            'chosen': candidate.id in self.nominee_ids.ids,
        }

    def action_confirm_nominees(self, employee_ids=None):
        """Lock the colleagues in and send them each a private link.

        THE COUNT IS CHECKED HERE AND NOWHERE ELSE. Fewer than three and one
        bad week decides somebody's job; more than five and nobody answers
        because everybody assumes somebody else will. The refusal says the
        numbers rather than "invalid selection".
        """
        self.ensure_one()
        self._require_manager()
        if self.state not in ('scheduled', 'nomination'):
            raise UserError(_(
                "The colleagues for this review have already been asked."))
        if employee_ids is not None:
            ids = [int(i) for i in (employee_ids or []) if i]
            people = self.env['hr.employee'].sudo().browse(ids).exists()
            self.sudo().nominee_ids = [(6, 0, people.ids)]
        chosen = self.nominee_ids
        if self.employee_id.id in chosen.ids:
            raise UserError(_("Nobody can be asked about themselves."))
        if len(chosen) < MIN_NOMINEES:
            raise UserError(_(
                "Choose at least %(min)s colleagues — you have chosen "
                "%(now)s. Three answers are what stop one bad week deciding "
                "somebody's job.", min=MIN_NOMINEES, now=len(chosen)))
        if len(chosen) > MAX_NOMINEES:
            raise UserError(_(
                "Choose no more than %(max)s colleagues — you have chosen "
                "%(now)s. Past five, people assume somebody else will answer "
                "and nobody does.", max=MAX_NOMINEES, now=len(chosen)))

        settings = self._settings()
        deadline = fields.Date.today() + timedelta(
            days=max(1, settings['feedback_window_days']))
        made = self._make_feedback_requests(chosen, deadline)
        self.sudo().write({'state': 'feedback',
                           'feedback_deadline': deadline})
        self.message_post(body=_(
            "%(count)s asked, with links that close on %(when)s.",
            count=counted(made, _('colleague'), _('colleagues')),
            when=deadline))
        return {'sent': made, 'deadline': str(deadline)}

    def _make_feedback_requests(self, people, deadline):
        """One link per colleague, idempotent on (review, respondent).

        The link IS the credential (P0's doctrine): a colleague may be on leave,
        may be a contractor with no login at all, and a questionnaire that needs
        a sign-in is a questionnaire nobody fills in.
        """
        self.ensure_one()
        Feedback = self.env['pb.feedback.request'].sudo()
        questions = json.dumps(PEER_QUESTIONS)
        made = 0
        for person in people:
            try:
                existing = Feedback.search([
                    ('probation_review_id', '=', self.id),
                    ('subject_employee_id', '=', self.employee_id.id),
                    '|', ('respondent_user_id', '=',
                          person.user_id.id if person.user_id else False),
                    ('respondent_email', '=',
                     (person.work_email or '').strip() or False),
                ], limit=1)
                if existing:
                    continue
                request = Feedback.create({
                    'subject_employee_id': self.employee_id.id,
                    'respondent_user_id': person.user_id.id
                    if person.user_id else False,
                    'respondent_email': (person.work_email or '').strip()
                    or False,
                    'kind': 'probation_peer',
                    'case_id': self.case_id.id if self.case_id else False,
                    'probation_review_id': self.id,
                    'window_end': deadline,
                    'questions_json': questions,
                    'company_id': (self.company_id
                                   or self.env.company).id,
                })
                if flag(self.env, P_PROBATION_MAIL):
                    request.action_send()
                made += 1
            except Exception:           # noqa: BLE001 — one peer, one grave
                _logger.exception(
                    'pb_probation: could not ask %s about review %s',
                    person.id, self.id)
        return made

    # =====================================================================
    #  2. THE DEADLINE
    # =====================================================================
    def action_extend_deadline(self):
        """Give everybody one more day — ONCE.

        Once, because a deadline that can be pushed indefinitely is not a
        deadline, and the whole reason the window is short is that a review
        which drifts past the trial end date is a decision made by the calendar
        rather than by a person.
        """
        self.ensure_one()
        self._require_manager()
        if self.state != 'feedback':
            raise UserError(_(
                "There is no answer window running on this review."))
        if self.deadline_extended:
            raise UserError(_(
                "This window has already been stretched once. The trial period "
                "ends on %(when)s, so the decision cannot wait much longer — "
                "put it together with what you have.",
                when=self.trial_end or _('the date on the record')))
        days = max(1, self._settings()['extension_grace_days'])
        base = self.feedback_deadline or fields.Date.today()
        new_end = base + timedelta(days=days)
        self.sudo().write({'feedback_deadline': new_end,
                           'deadline_extended': True,
                           'deadline_alerted': False})
        open_rows = self.feedback_request_ids.filtered(
            lambda r: r.state in ('sent', 'extended'))
        if open_rows:
            open_rows.sudo().action_extend(days=days)
        self.message_post(body=_(
            "The answer window now closes on %(when)s. %(who)s still to "
            "answer.", when=new_end,
            who=counted(len(open_rows), _('colleague is'),
                        _('colleagues are'))))
        return {'deadline': str(new_end), 'reminded': len(open_rows)}

    def pending_respondents(self):
        """Who has not answered yet, as addresses. Never raises."""
        self.ensure_one()
        out = []
        for row in self.feedback_request_ids:
            if row.state not in ('sent', 'extended'):
                continue
            to = row.respondent_email or (
                row.respondent_user_id.email if row.respondent_user_id else '')
            if to:
                out.append(to)
        return out

    # =====================================================================
    #  3. PUTTING IT TOGETHER
    # =====================================================================
    def maybe_consolidate(self):
        """Consolidate when everybody has answered, or the window has shut.

        Called from the feedback submit and from the daily job. Never raises —
        it runs inside somebody else's transaction (a colleague pressing Send
        on a public page) and an exception here would roll back their answer.
        """
        self.ensure_one()
        try:
            if self.state != 'feedback':
                return False
            rows = self.feedback_request_ids
            all_in = bool(rows) and all(r.state == 'submitted' for r in rows)
            window_shut = bool(self.feedback_deadline
                               and self.feedback_deadline
                               < fields.Date.today())
            if not (all_in or window_shut):
                return False
            return self.action_consolidate()
        except Exception:               # noqa: BLE001
            _logger.exception('pb_probation: could not consolidate review %s',
                              self.id)
            return False

    def action_consolidate(self):
        """Build the report, tell the manager, and put the 1:1 in the diary."""
        self.ensure_one()
        if self.state in ('closed',):
            raise UserError(_("This review is already closed."))
        html, average = self._build_report()
        self.sudo().write({
            'consolidated_html': html,
            'avg_rating': average,
            'consolidated_at': fields.Datetime.now(),
            'state': 'one_on_one',
        })
        self._ensure_one_on_one()
        self._mail('pb_probation.mail_template_review_ready',
                   self._manager_addresses())
        self.message_post(body=_(
            "The answers are in and the report is ready — "
            "%(count)s answered%(avg)s.",
            count=counted(self.feedback_in, _('colleague'), _('colleagues')),
            avg=(_(', average %s out of 5', round(average, 1))
                 if average else '')))
        return True

    def _build_report(self):
        """Every answer, every rating and every red flag, on one page.

        THE COMMENTS ARE NOT SUMMARISED. An average tells a manager whether to
        worry; the sentence a colleague actually wrote is the thing that makes
        the conversation useful, and the moment this starts paraphrasing them
        it becomes a screen nobody trusts.

        The names of the colleagues are NOT shown against their answers. Four
        people who know their comments will be attributed give four comments
        that say nothing.
        """
        self.ensure_one()
        emp = self.employee_id
        answered = [r for r in self.feedback_request_ids
                    if r.state == 'submitted']
        totals, counts, comments = {}, {}, []
        for row in answered:
            try:
                payload = json.loads(row.answers_json or '{}') or {}
            except Exception:           # noqa: BLE001
                _logger.warning('pb_probation: unreadable answers on %s',
                                row.id)
                continue
            for key, item in payload.items():
                if key.startswith('_'):
                    continue
                value = (item or {}).get('value')
                if value in (None, ''):
                    continue
                if key in PEER_RATING_KEYS:
                    try:
                        number = float(str(value).strip())
                    except (TypeError, ValueError):
                        continue
                    totals[key] = totals.get(key, 0.0) + number
                    counts[key] = counts.get(key, 0) + 1
                else:
                    comments.append({
                        'label': PEER_QUESTION_LABEL.get(
                            key, (item or {}).get('label') or key),
                        'value': str(value),
                    })

        averages = [(PEER_QUESTION_LABEL.get(k, k), totals[k] / counts[k])
                    for k in PEER_RATING_KEYS if counts.get(k)]
        overall = (sum(a for _lbl, a in averages) / len(averages)) \
            if averages else 0.0

        parts = [
            '<div class="pbpr-report">',
            '<p><strong>%s</strong></p>' % escape(_(
                '%(count)s of %(total)s colleagues answered.',
                count=len(answered), total=len(self.feedback_request_ids))),
        ]
        if averages:
            parts.append('<h4>%s</h4><ul>' % escape(_('How they were rated')))
            for label, value in averages:
                parts.append('<li>%s — <strong>%s</strong> %s</li>' % (
                    escape(label), escape('%.1f' % value),
                    escape(_('out of 5'))))
            parts.append('</ul>')
            parts.append('<p>%s <strong>%s</strong> %s</p>' % (
                escape(_('Overall:')), escape('%.1f' % overall),
                escape(_('out of 5'))))
        else:
            parts.append('<p>%s</p>' % escape(_(
                'Nobody gave a rating, so there is no average to show. The '
                'comments below are what there is to go on.')))

        if comments:
            parts.append('<h4>%s</h4>' % escape(_('What they said')))
            parts.append('<p><em>%s</em></p>' % escape(_(
                'Unattributed on purpose — colleagues who know their comments '
                'carry their name write comments that say nothing.')))
            for comment in comments:
                parts.append(
                    '<p><span style="color:#6b7280;font-size:11px;'
                    'text-transform:uppercase;letter-spacing:.05em;">%s</span>'
                    '<br/>%s</p>' % (escape(comment['label']),
                                     escape(comment['value'])))

        parts.extend(self._checkin_section(emp))
        parts.append('</div>')
        return Markup(''.join(parts)), round(overall, 2)

    def _checkin_section(self, emp):
        """The 30/60/90 notes and every red flag, beside the peer answers.

        P3 already planned those conversations and somebody already wrote in
        them. A probation report that ignores them asks a manager to remember
        three months of notes, which is the thing this whole module exists to
        stop.
        """
        self.ensure_one()
        parts = []
        try:
            rows = self.env['pb.employee.checkin'].sudo().search(
                [('employee_id', '=', emp.id),
                 ('state', '!=', 'cancelled')],
                order='scheduled_date')
        except Exception:               # noqa: BLE001
            _logger.exception('pb_probation: check-ins for employee %s',
                              emp.id)
            return parts
        flags = [r for r in rows if r.red_flag]
        said = [r for r in rows if (r.notes or '').strip()]
        if flags:
            parts.append('<h4 style="color:#b42318;">%s</h4><ul>'
                         % escape(_('Raised for attention')))
            for row in flags:
                parts.append('<li><strong>%s</strong> — %s</li>' % (
                    escape(str(row.scheduled_date or '')),
                    escape(row.red_flag_note or row.notes
                           or _('flagged, with no note'))))
            parts.append('</ul>')
        if said:
            parts.append('<h4>%s</h4>' % escape(_('From the check-ins')))
            for row in said:
                parts.append(
                    '<p><span style="color:#6b7280;font-size:11px;">%s</span>'
                    '<br/>%s</p>' % (
                        escape('%s · %s' % (row.scheduled_date or '',
                                            row.name or '')),
                        escape(row.notes or '')))
        if not flags and not said:
            parts.append('<h4>%s</h4><p>%s</p>' % (
                escape(_('From the check-ins')),
                escape(_('Nothing was written down in the 30, 60 or 90 day '
                         'conversations.'))))
        return parts

    def _ensure_one_on_one(self):
        """The conversation, in the diary. Idempotent on (review)."""
        self.ensure_one()
        if self.one_on_one_checkin_id:
            return self.one_on_one_checkin_id
        Checkin = self.env['pb.employee.checkin'].sudo()
        owner = self.manager_user_id or self.hrbp_user_id or self.env.user
        checkin = Checkin.create({
            'employee_id': self.employee_id.id,
            'case_id': self.case_id.id if self.case_id else False,
            'kind': 'probation',
            'owner_user_id': owner.id,
            'scheduled_date': fields.Date.today() + timedelta(
                days=ONE_ON_ONE_DUE_DAYS),
            'company_id': (self.company_id or self.env.company).id,
        })
        self.sudo().one_on_one_checkin_id = checkin.id
        return checkin

    def action_one_on_one_done(self, notes=None):
        """The conversation happened — now somebody has to decide."""
        self.ensure_one()
        self._require_manager()
        if self.state not in ('one_on_one', 'consolidation'):
            raise UserError(_(
                "This review is not waiting on the conversation."))
        if self.one_on_one_checkin_id:
            self.one_on_one_checkin_id.sudo().action_done(notes=notes)
        self.sudo().state = 'verdict'
        self.message_post(body=_(
            "The conversation has happened. The decision is next."))
        return True

    # =====================================================================
    #  4. THE DECISION
    # =====================================================================
    def verdict_preview(self, verdict, extension_months=None):
        """What pressing Confirm will actually do, in plain English.

        The wizard shows this BEFORE the button, because a verdict writes a
        state onto somebody's employment record, prepares a letter with their
        name on it and — for an extension — moves a date on their contract.
        Nobody should have to guess which of those happens.
        """
        self.ensure_one()
        emp = self.employee_id
        who = first_name(emp.name) or emp.name or _('this person')
        lines = []
        blocked = []
        if verdict == 'pass':
            pending = self.env['pb.training.status'].pending_required_for(emp)
            if pending:
                blocked = pending
            lines = [
                _('%s is confirmed — their trial period ends here.', who),
                _('The confirmation letter is prepared, filed with their '
                  'documents and emailed to them.'),
                _('Their record shows "Passed" from today.'),
            ]
        elif verdict == 'extend':
            months = int(extension_months
                         or self._settings()['default_extension_months'] or 1)
            new_end = add_months(
                self.trial_end or fields.Date.today(), months)
            lines = [
                _('%(who)s stays in their trial period until %(when)s.',
                  who=who, when=new_end),
                _('A letter goes to them setting out what to work on.'),
                _('A second review is scheduled, so this does not have to be '
                  'remembered.'),
            ]
        elif verdict == 'fail':
            lines = [
                _('%s is not confirmed.', who),
                _('The letter is prepared and the HR team is told.'),
                _('NOTHING about their leaving is started automatically — '
                  'somebody has to press "Start their exit" afterwards.'),
            ]
        return {
            'verdict': verdict,
            'label': VERDICT_LABEL.get(verdict, ''),
            'lines': lines,
            'blocked': blocked,
            'blocked_text': joined_sentence(blocked) if blocked else '',
        }

    def action_verdict(self, verdict, strengths=None, improvements=None,
                       extension_months=None):
        """Decide, and do everything that follows from deciding."""
        self.ensure_one()
        self._require_manager()
        if verdict not in VERDICT_LABEL:
            raise UserError(_("Choose one of the three decisions."))
        if self.state == 'closed':
            raise UserError(_(
                "This review was already decided on %(when)s.",
                when=self.verdict_at or _('an earlier date')))
        if self.state in ('scheduled', 'nomination'):
            raise UserError(_(
                "Nobody has been asked about this person yet. Ask their "
                "colleagues first, or the decision rests on one opinion."))
        if verdict == 'pass':
            self._check_training_gate()

        vals = {'verdict': verdict,
                'verdict_at': fields.Datetime.now(),
                'verdict_by': self.env.uid,
                'state': 'closed'}
        if strengths is not None:
            vals['strengths'] = strengths
        if improvements is not None:
            vals['improvements'] = improvements
        if verdict == 'extend':
            vals['extension_months'] = int(
                extension_months
                or self._settings()['default_extension_months'] or 1)
        self.sudo().write(vals)

        handler = {'pass': self._verdict_pass, 'extend': self._verdict_extend,
                   'fail': self._verdict_fail}[verdict]
        outcome = handler()
        self._on_verdict(verdict)
        self.message_post(body=_(
            "Decision: %(what)s.", what=VERDICT_LABEL.get(verdict, verdict)))
        return outcome

    def _check_training_gate(self):
        """Refuse a pass while a required course is outstanding.

        Named, never counted: "the pass was blocked" is not something anybody
        can act on, and "Soil sampling — module 2" is.
        """
        self.ensure_one()
        pending = self.env['pb.training.status'].pending_required_for(
            self.employee_id)
        if not pending:
            return True
        raise UserError(_(
            "%(who)s cannot be confirmed yet — %(what)s still to finish: "
            "%(items)s. Tick it off on their training record and the "
            "confirmation goes through.",
            who=self.employee_id.name or _('This person'),
            what=counted(len(pending), _('course item'), _('course items')),
            items=joined_sentence(pending, limit=5)))

    def _verdict_pass(self):
        self.ensure_one()
        emp = self.employee_id
        emp._pb_set_probation_state('passed', reason=_(
            "Trial period passed — confirmed on %s.",
            fields.Date.today()))
        self._write_performance_rating()
        letter = self._prepare_letter('pass')
        self._mail('pb_probation.mail_template_verdict_hr',
                   self._hr_addresses())
        return {'verdict': 'pass', 'letter_id': letter.id if letter else 0}

    def _verdict_extend(self):
        """Move the trial end IN PLACE (ruling D1's carve-out) and come back."""
        self.ensure_one()
        emp = self.employee_id
        months = max(1, self.extension_months or 1)
        base = self.trial_end or emp.sudo().trial_date_end \
            or fields.Date.today()
        new_end = add_months(base, months)
        emp.pb_set_trial_end(new_end, note=_(
            "The trial period was extended by %(count)s at the review on "
            "%(when)s, and now ends on %(end)s.",
            count=counted(months, _('month'), _('months')),
            when=fields.Date.today(), end=new_end))
        emp._pb_set_probation_state('extended', reason=_(
            "Trial period extended to %s.", new_end))
        self.sudo().new_trial_end = new_end
        letter = self._prepare_letter('extend')
        nxt = self._schedule_next_round(new_end)
        self._mail('pb_probation.mail_template_verdict_hr',
                   self._hr_addresses())
        return {'verdict': 'extend', 'new_trial_end': str(new_end),
                'letter_id': letter.id if letter else 0,
                'next_review_id': nxt.id if nxt else 0}

    def _schedule_next_round(self, new_end):
        """The second look, in the diary rather than in somebody's memory."""
        self.ensure_one()
        try:
            return self.sudo().open_for(
                self.employee_id, kind=self.kind, trial_end=new_end,
                case=self.case_id or None, round_no=(self.round or 1) + 1)
        except Exception:               # noqa: BLE001
            _logger.exception('pb_probation: could not schedule round %s for '
                              'review %s', (self.round or 1) + 1, self.id)
            return self.browse()

    def _verdict_fail(self):
        """Write it down, prepare the letter, and STOP.

        The exit is not started here and it is not started by the daily job
        either. Somebody presses a button, having read the letter, because a
        module that opens a leaving checklist on its own the moment a box is
        ticked is a module nobody will trust with the box.
        """
        self.ensure_one()
        self.employee_id._pb_set_probation_state('failed', reason=_(
            "Trial period not passed — decided on %s.", fields.Date.today()))
        letter = self._prepare_letter('fail')
        self._mail('pb_probation.mail_template_verdict_fail_hr',
                   self._hr_addresses())
        return {'verdict': 'fail', 'letter_id': letter.id if letter else 0,
                'needs_exit': True}

    def _write_performance_rating(self):
        """Carry the average onto the employee's rating, if the field exists.

        PROBED rather than depended on: `wfp_performance_rating` comes from the
        workforce-planning module, which is not a dependency of this one, and a
        hard reference would make this phase refuse to install on a database
        that does not have it. Absent field, log line, carry on.
        """
        self.ensure_one()
        if not self.avg_rating:
            return False
        emp = self.employee_id
        if 'wfp_performance_rating' not in emp._fields:
            _logger.info('pb_probation: no performance rating field on this '
                         'build — review %s did not write one', self.id)
            return False
        try:
            value = max(1, min(5, int(round(self.avg_rating))))
            # It is a SELECTION on this build ('1'..'5'), so the value has to
            # be the string. Probed rather than assumed, because a tenant whose
            # field is an integer must not get a silent write of "3".
            field = emp._fields['wfp_performance_rating']
            emp.sudo().write({
                'wfp_performance_rating':
                    str(value) if field.type == 'selection' else value})
            self.message_post(body=_(
                "Their performance rating was set to %s out of 5 from the "
                "average of what colleagues said.", value))
            return True
        except Exception:               # noqa: BLE001
            _logger.exception('pb_probation: could not write the performance '
                              'rating for review %s', self.id)
            return False

    # ---------------------------------------------------------- the letters
    def _prepare_letter(self, verdict):
        """Prepare, file and email the letter for this decision.

        Never raises: a letter that could not be produced is a letter somebody
        writes by hand, and it must not undo a verdict that has already been
        written onto an employment record.
        """
        self.ensure_one()
        xmlid = VERDICT_LETTER.get(verdict)
        if not xmlid:
            return self.env['pb.hr.letter'].browse()
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_probation: %s is missing — no letter for '
                            'review %s', xmlid, self.id)
            return self.env['pb.hr.letter'].browse()
        try:
            extra = {}
            if verdict == 'extend':
                extra = {'new_trial_end': str(self.new_trial_end or ''),
                         'improvements': self.improvements or ''}
            elif verdict == 'fail':
                extra = {'trial_end': str(self.trial_end or ''),
                         'improvements': self.improvements or ''}
            else:
                extra = {'strengths': self.strengths or ''}
            letter = self.env['pb.hr.letter'].sudo().create({
                'employee_id': self.employee_id.id,
                'template_id': template.id,
                'case_id': self.case_id.id if self.case_id else False,
                'context_json': json.dumps(extra),
                'company_id': (self.company_id or self.env.company).id,
            })
            letter.action_generate()
            if flag(self.env, P_PROBATION_MAIL):
                letter.action_send()
            self.sudo().letter_id = letter.id
            return letter
        except Exception:               # noqa: BLE001
            _logger.exception('pb_probation: could not prepare the %s letter '
                              'for review %s', verdict, self.id)
            return self.env['pb.hr.letter'].browse()

    # ------------------------------------------------------- the exit button
    def action_start_exit(self):
        """Open the leaving checklist — reusing P4's own way in.

        NOT a second implementation. `pb.journey.case.setup_offboarding()` is
        what P4 built for exactly this: it creates the four clearances and the
        exit questionnaire, and it is idempotent, so reaching the same case
        from a resignation and from here leaves one set of rows behind (R30).
        The case itself is opened the same way a resignation opens one — an
        existing draft/running/on-hold leaving checklist IS the checklist for
        this exit, whoever started it.
        """
        self.ensure_one()
        self._require_manager()
        if self.verdict != 'fail':
            raise UserError(_(
                "An exit is only started from a trial period that was not "
                "passed."))
        emp = self.employee_id
        Case = self.env['pb.journey.case'].sudo()
        case = Case.search([
            ('employee_id', '=', emp.id),
            ('case_type', '=', 'offboarding'),
            ('state', 'in', ('draft', 'active', 'on_hold')),
        ], limit=1)
        if not case:
            template = self.env['pb.journey.template'].sudo().pick_for(
                'offboarding',
                country_id=Case._employee_country(emp),
                company_id=(self.company_id or self.env.company).id)
            case = Case.create({
                'employee_id': emp.id,
                'case_type': 'offboarding',
                'template_id': template.id if template else False,
                'anchor_date': self.trial_end or fields.Date.today(),
                'source': 'manual',
                'company_id': (self.company_id or self.env.company).id,
            })
            case.action_open()
        else:
            case.setup_offboarding()
        self.sudo().exit_case_id = case.id
        case.message_post(body=_(
            "Opened because the trial period was not passed."))
        self.message_post(body=_(
            "The leaving checklist is open — %s.",
            counted(len(case.task_ids), _('step'), _('steps'))))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pb.journey.case',
            'res_id': case.id,
            'view_mode': 'form',
        }

    # ------------------------------------------------------- extension point
    def _on_verdict(self, verdict):
        """Called ONCE, last, after a decision has been fully written.

        Deliberately empty and deliberately last: everything else has already
        happened, so an override sees a finished world — the state is on the
        employee record, the letter exists, the next round (if any) is
        scheduled.

        P10 overrides this so that a CONVERSION review that ends in "pass"
        raises the new permanent contract. **Overrides must never raise** — a
        failure here would undo a verdict somebody has already been told about.
        """
        return True

    # ------------------------------------------------------------- the mail
    def _mail(self, xmlid, addresses):
        """Queue one message. Never raises; never counts a dead letter.

        `email_to` is passed EXPLICITLY (R6): a template's own rendered address
        can reach `mail.mail` empty and the message is then created, queued and
        addressed to nobody with no error anywhere.
        """
        self.ensure_one()
        if not flag(self.env, P_PROBATION_MAIL):
            _logger.info('pb_probation: probation emails are switched off')
            return False
        clean, seen = [], set()
        for address in (addresses or []):
            address = (address or '').strip()
            if address and address.lower() not in seen:
                seen.add(address.lower())
                clean.append(address)
        if not clean:
            _logger.info('pb_probation: review %s — nobody to write to',
                         self.id)
            return False
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_probation: %s is missing', xmlid)
            return False
        try:
            template.sudo().send_mail(
                self.id, force_send=False,
                email_values={'email_to': ','.join(clean),
                              'auto_delete': False})
            return True
        except Exception:               # noqa: BLE001
            _logger.exception('pb_probation: could not queue %s for review %s',
                              xmlid, self.id)
            return False

    def _manager_addresses(self):
        self.ensure_one()
        out = []
        if self.manager_user_id and self.manager_user_id.email:
            out.append(self.manager_user_id.email)
        manager = self.employee_id.parent_id
        if manager and manager.work_email:
            out.append(manager.work_email)
        if not out and self.hrbp_user_id and self.hrbp_user_id.email:
            out.append(self.hrbp_user_id.email)
        return out or self._hr_addresses()

    def _hr_addresses(self):
        self.ensure_one()
        out = []
        if self.hrbp_user_id and self.hrbp_user_id.email:
            out.append(self.hrbp_user_id.email)
        try:
            people = self.env['pb.journey.case']._users_in_group(
                GROUP_MANAGER, self.company_id or self.env.company, limit=0)
            out.extend(u.email for u in people if u.email)
        except Exception:               # noqa: BLE001
            _logger.debug('pb_probation: no HR addresses for review %s',
                          self.id)
        return out

    def _employee_address(self):
        self.ensure_one()
        emp = self.employee_id
        return [a for a in (emp.work_email, emp.private_email) if a][:1]

    # ------------------------------------------------------------ the reader
    @api.model
    def for_employee(self, employee):
        """The review this person's own page should show."""
        employee = self.env['pb.probation.policy']._as_employee(employee)
        if not employee:
            return self.browse()
        live = self.sudo().search(
            [('employee_id', '=', employee.id),
             ('state', 'in', REVIEW_OPEN)],
            order='trial_end, id desc', limit=1)
        return live or self.sudo().search(
            [('employee_id', '=', employee.id)],
            order='id desc', limit=1)

    def state_label(self):
        self.ensure_one()
        return REVIEW_STATE_LABEL.get(self.state, self.state or '')
