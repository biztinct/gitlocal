# -*- coding: utf-8 -*-
"""One improvement plan, from a manager's worry to a decision somebody made.

SEVEN STOPS, AND A PLAN IS ONLY EVER AT ONE OF THEM:

    requested    a line manager has asked HR to look at somebody
    coaching     HR has taken it up; there is a conversation and a written note
    active       a plan with objectives and dates is running
    evaluation   the plan has reached its end date and the manager is asked
    passed       it worked
    failed       it did not
    terminated   they left before it finished

THE FIRST TWO ARE THE ARGUMENT OF THIS MODULE. A request is not a plan, and a
coaching conversation is not a plan either. Nothing is written to the person,
nothing is filed in their documents and nothing appears on their own page until
`action_start_plan()` — so a manager having a bad month cannot, by filling in
one form, put a letter in somebody's permanent record.

WHAT `action_start_plan()` REFUSES, and why the refusals are sentences rather
than state errors: a plan with no objectives is a threat with a date on it, and
an objective with no metric cannot be passed or failed on evidence. Both are
named in the refusal, because "invalid" is not something anybody can act on.

EVERY WRITE IS CHATTERED. This is the most private record in the product and
the one most likely to be argued about a year later, so each transition posts
what it did and who did it.
"""

import json
import logging
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .pip_common import (
    CHECKIN_FREQ_DAYS, CHECKIN_FREQS, EVAL_OBJECTIVE_PREFIX, EVAL_QUESTIONS,
    GROUP_HEAD, GROUP_USER, LETTER_PIP, OBJECTIVE_STATE_LABEL,
    P_AUTO_TERMINATE, P_DEFAULT_WEEKS, P_EMPLOYEE_VIEW, P_MISSED_DAYS,
    P_PIP_MAIL, PIP_EMPLOYEE_VISIBLE, PIP_OPEN, PIP_STATE_LABEL, PIP_STATES,
    VERDICT_LABEL, VERDICT_STATE, counted, first_name, flag, joined_sentence,
    number,
)

_logger = logging.getLogger(__name__)

#: How soon after HR takes a request up the first conversation is put in the
#: diary. Two days: soon enough that "we are looking at it" is true, far enough
#: that somebody can prepare.
COACHING_CALL_DAYS = 2

#: How long the manager gets to fill in the evaluation form.
EVAL_WINDOW_DAYS = 5

#: A plan never schedules more check-ins than this, whatever arithmetic says.
#: A twenty-six week weekly plan is twenty-six diary entries, which is fine; a
#: bad date pair that asks for four hundred is a bug, and a cap turns it into a
#: short plan rather than into four hundred emails.
MAX_CHECKINS = 30


class PbPipCase(models.Model):
    _name = 'pb.pip.case'
    _description = 'Improvement Plan'
    # `mail.activity.mixin` as well as `mail.thread` — R3: `activity_schedule`
    # lives on the ACTIVITY mixin, and a missed check-in raises a to-do.
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'end_date, id desc'

    name = fields.Char(compute='_compute_name', store=True, string='Plan')
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='cascade', tracking=True)
    requested_by_user_id = fields.Many2one(
        'res.users', string='Asked for by', index=True, ondelete='set null',
        help='The line manager who asked HR to look at this. They can see '
             'this one request and nothing else.')
    hr_owner_user_id = fields.Many2one(
        'res.users', string='HR owner', index=True, ondelete='set null',
        help='The person in HR who is actually running this.')
    template_id = fields.Many2one(
        'pb.pip.template', string='Started from', ondelete='set null')
    reason_text = fields.Text(
        string='Why it was asked for',
        help='In the manager\'s own words. Only HR and the manager who wrote '
             'it can read this.')
    state = fields.Selection(
        PIP_STATES, string='Status', default='requested', required=True,
        index=True, tracking=True, copy=False)

    # ---- coaching
    coaching_html = fields.Html(
        string='The coaching note', sanitize=True,
        help='What was said, what was agreed and by when. This is the stage '
             'most of these should end at.')
    coaching_start = fields.Date(string='Coaching started', readonly=True)
    coaching_end = fields.Date(string='Coaching finished', readonly=True)
    coaching_checkin_id = fields.Many2one(
        'pb.employee.checkin', string='The first conversation',
        ondelete='set null', readonly=True)

    # ---- the plan
    weeks = fields.Integer(
        string='How long it runs (weeks)', default=6,
        help='Copied from the template when the plan starts, and editable '
             'until it does.')
    checkin_freq = fields.Selection(
        CHECKIN_FREQS, string='Check in', default='weekly')
    start_date = fields.Date(string='Plan starts', index=True, tracking=True)
    end_date = fields.Date(string='Plan ends', index=True, tracking=True)
    objective_ids = fields.One2many(
        'pb.pip.objective', 'case_id', string='Objectives')
    objective_count = fields.Integer(
        compute='_compute_progress', string='Objectives')
    at_risk_count = fields.Integer(
        compute='_compute_progress', string='At risk')
    on_track_count = fields.Integer(
        compute='_compute_progress', string='On track')
    checkin_ids = fields.One2many(
        'pb.employee.checkin', 'pip_case_id', string='Check-ins')
    checkins_planned = fields.Integer(
        compute='_compute_progress', string='Check-ins planned')
    checkins_done = fields.Integer(
        compute='_compute_progress', string='Check-ins held')

    # ---- the person's own page
    employee_ack = fields.Boolean(
        string='They have seen it', readonly=True, copy=False, tracking=True)
    ack_at = fields.Datetime(string='Seen on', readonly=True, copy=False)

    # ---- the decision
    eval_request_id = fields.Many2one(
        'pb.feedback.request', string='Evaluation form', readonly=True,
        ondelete='set null', copy=False)
    verdict = fields.Selection(
        [('pass', 'Completed successfully'), ('fail', 'Not successful')],
        string='Decision', readonly=True, copy=False, tracking=True)
    verdict_at = fields.Datetime(string='Decided on', readonly=True)
    verdict_by = fields.Many2one('res.users', string='Decided by',
                                 readonly=True)
    final_rating = fields.Integer(
        string='Where they ended up (1-5)',
        help='1 is nowhere near, 5 is comfortably past what the plan asked '
             'for. Written onto their performance rating when the plan is '
             'completed successfully.')
    outcome_note = fields.Text(string='What was decided, and why')
    letter_id = fields.Many2one('pb.hr.letter', string='Letter', readonly=True,
                                ondelete='set null', copy=False)
    exit_case_id = fields.Many2one(
        'pb.journey.case', string='Leaving checklist', readonly=True,
        ondelete='set null', copy=False)
    closed_at = fields.Datetime(string='Closed on', readonly=True)

    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    # ------------------------------------------------------------- computes
    @api.depends('employee_id')
    def _compute_name(self):
        for rec in self:
            rec.name = _('%s — improvement plan',
                         rec.employee_id.sudo().name or _('Employee'))

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Improvement plan')

    @api.depends('objective_ids.status', 'checkin_ids.state')
    def _compute_progress(self):
        # `sudo()` on the COUNTS, and only on the counts. The requesting
        # manager may read the case they raised (record rule) but holds no
        # access to the objectives or the check-ins, deliberately — so a plain
        # `read()` of every field on their own case would otherwise die on the
        # compute rather than on the field they were not meant to see. Five
        # numbers about their own request is not the leak this module guards.
        for rec in self:
            plain = rec.sudo()
            objectives = plain.objective_ids
            rec.objective_count = len(objectives)
            rec.at_risk_count = len(
                [o for o in objectives if o.status in ('at_risk', 'not_met')])
            rec.on_track_count = len(
                [o for o in objectives if o.status in ('on_track', 'met')])
            checkins = plain.checkin_ids.filtered(
                lambda c: c.state != 'cancelled')
            rec.checkins_planned = len(checkins)
            rec.checkins_done = len(
                [c for c in checkins if c.state == 'done'])

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id and self.employee_id.company_id:
            self.company_id = self.employee_id.company_id

    @api.onchange('template_id')
    def _onchange_template_id(self):
        if not self.template_id:
            return
        self.weeks = self.template_id.default_weeks or 6
        self.checkin_freq = self.template_id.checkin_freq or 'weekly'
        if not self.coaching_html and self.template_id.coaching_body_html:
            self.coaching_html = self.template_id.coaching_body_html

    # =====================================================================
    #  THE WAY IN. A manager asks; nothing else happens.
    # =====================================================================
    @api.model
    def request_for(self, employee, reason=None, template=None):
        """Raise a request. IDEMPOTENT — one open plan per person at a time.

        A second manager (or the same one twice) asking about somebody who is
        already on a plan finds THAT plan rather than opening a second one:
        two improvement plans running at once for one person is not a state
        anybody could act on, and the person would be given two sets of
        objectives that disagree.

        `employee` may be a record or an id — over JSON-RPC a recordset
        argument arrives as a plain integer (R43), and this method is called
        from the request dialog.
        """
        employee = self._as_employee(employee)
        if not employee:
            raise UserError(_("Choose the person this is about first."))
        existing = self.sudo().search([
            ('employee_id', '=', employee.id),
            ('state', 'in', PIP_OPEN),
        ], order='id desc', limit=1)
        if existing:
            return existing
        if isinstance(template, int):
            template = self.env['pb.pip.template'].sudo().browse(
                template).exists()
        case = self.sudo().create({
            'employee_id': employee.id,
            'requested_by_user_id': self.env.uid,
            'template_id': template.id if template else False,
            'reason_text': (reason or '').strip()[:4000] or False,
            'weeks': (template.default_weeks if template
                      else number(self.env, P_DEFAULT_WEEKS, 6)) or 6,
            'checkin_freq': (template.checkin_freq if template else 'weekly'),
            'state': 'requested',
            'company_id': (employee.company_id or self.env.company).id,
        })
        case.message_post(body=_(
            "%(who)s asked HR to look at this.", who=self.env.user.name))
        case._mail('pb_pip.mail_template_pip_requested', case._hr_addresses())
        return case

    @api.model
    def _as_employee(self, value):
        """A record, an id, or nothing — always a SUDO `hr.employee` recordset.

        R43/R52: every public method here whose argument is a record is called
        with a plain integer over JSON-RPC, and an integer walks straight past
        `if not employee` and answers False to every getattr.

        SUDO, and see `_person()` for why: reading one field of an employee
        record on this build reads forty, and about forty of those are behind
        payroll groups an HR lead running improvement plans does not hold.
        """
        Emp = self.env['hr.employee'].sudo()
        if not value:
            return Emp.browse()
        if isinstance(value, models.BaseModel):
            return value.sudo()[:1] if value._name == 'hr.employee' \
                else Emp.browse()
        try:
            return Emp.browse(int(value)).exists()
        except (TypeError, ValueError):
            return Emp.browse()

    def _person(self):
        """The employee on this plan, read as the system.

        NOT A HOLE IN ANY GATE. Whoever is executing has already been proved
        entitled to this case — by the record rule on the way in, or by
        `_require_hr()`. This is about a different mechanism: reading ONE field
        of an `hr.employee` prefetches EVERY stored field of it, and this
        build's employee record carries about forty behind `groups=` (payroll
        country, insurance code, union fee, tham_gia_bhxh…). A reader who holds
        the improvement-plan group but not the payroll ones therefore gets an
        AccessError naming forty fields nobody asked for, in the middle of an
        action that only wanted somebody's first name.

        The alternative — requiring every HR lead who runs improvement plans to
        also hold the payroll groups — would hand out far more than it
        withholds.
        """
        self.ensure_one()
        return self.employee_id.sudo()

    # ---------------------------------------------------------------- gates
    def _is_hr(self):
        user = self.env.user
        return bool(self.env.su or user.has_group(GROUP_USER)
                    or user.has_group(GROUP_HEAD))

    def _require_hr(self):
        """Who may move a plan on. HR, and nobody else — not even the manager.

        Deliberately tighter than P5's equivalent. A trial-period review is a
        conversation the line manager owns; an improvement plan is a process
        with a legal shape to it, and the manager who asked for it is the last
        person who should also be the one running it.
        """
        self.ensure_one()
        if self._is_hr():
            return True
        raise AccessError(_(
            "Improvement plans are run by the HR team. Ask them to make the "
            "change — you can see the request you raised."))

    # =====================================================================
    #  1. HR TAKES IT UP  → coaching
    # =====================================================================
    def action_take_up(self, note=None):
        """Accept the request and put the first conversation in the diary."""
        for rec in self:
            rec._require_hr()
            if rec.state != 'requested':
                raise UserError(_(
                    "This has already been taken up — it is at "
                    "\"%(where)s\".",
                    where=PIP_STATE_LABEL.get(rec.state, rec.state or '')))
            vals = {'state': 'coaching',
                    'coaching_start': fields.Date.context_today(rec)}
            if not rec.hr_owner_user_id:
                vals['hr_owner_user_id'] = self.env.uid
            if note:
                vals['coaching_html'] = Markup('<p>%s</p>') % note
            elif not rec.coaching_html and rec.template_id:
                vals['coaching_html'] = \
                    rec.template_id.coaching_body_html or False
            rec.sudo().write(vals)
            rec._ensure_coaching_call()
            rec.message_post(body=_(
                "%(who)s in HR has taken this up. Nothing has been written to "
                "%(person)s — this is a conversation, not a plan.",
                who=self.env.user.name,
                person=first_name(rec._person().name)
                or rec._person().name or _('them')))
            rec._mail('pb_pip.mail_template_pip_taken_up',
                      rec._manager_addresses())
        return True

    def _ensure_coaching_call(self):
        """The first conversation, in the diary. Idempotent on (case)."""
        self.ensure_one()
        if self.coaching_checkin_id:
            return self.coaching_checkin_id
        owner = self.hr_owner_user_id or self.env.user
        checkin = self.env['pb.employee.checkin'].sudo().create({
            'employee_id': self.employee_id.id,
            'kind': 'other',
            'pip_case_id': self.id,
            'owner_user_id': owner.id,
            'scheduled_date': fields.Date.today() + timedelta(
                days=COACHING_CALL_DAYS),
            'company_id': (self.company_id or self.env.company).id,
        })
        self.sudo().coaching_checkin_id = checkin.id
        return checkin

    def action_save_coaching(self, html):
        """Write down what was said. Available for as long as the plan runs."""
        self.ensure_one()
        self._require_hr()
        if self.state in ('passed', 'failed', 'terminated'):
            raise UserError(_("This plan is closed."))
        self.sudo().coaching_html = html or False
        self.message_post(body=_("The coaching note was updated."))
        return True

    def action_close_at_coaching(self, note=None):
        """The best outcome there is: it did not need a plan.

        A separate ending from `passed`, and it uses the same state on purpose
        — "completed successfully" is exactly what happened — but the note says
        it was settled in coaching, because a record that reads as a
        successfully completed formal plan when there never was one is not
        true.
        """
        self.ensure_one()
        self._require_hr()
        if self.state != 'coaching':
            raise UserError(_(
                "This can only be closed here while it is still at the "
                "coaching stage."))
        self.sudo().write({
            'state': 'passed',
            'coaching_end': fields.Date.context_today(self),
            'outcome_note': (note or '').strip()[:4000] or _(
                'Settled in coaching. No formal plan was needed.'),
            'closed_at': fields.Datetime.now(),
            'verdict': False,
        })
        self._cancel_open_checkins(_('the case was settled in coaching'))
        self.message_post(body=_(
            "Closed at the coaching stage — no formal plan was needed. "
            "Nothing was written to their record and nothing was filed."))
        return True

    # =====================================================================
    #  2. THE PLAN STARTS
    # =====================================================================
    def start_preview(self):
        """What pressing "Start the plan" will actually do, in plain English.

        Shown BEFORE the button, because this is the moment the module stops
        being a private HR conversation and starts writing to somebody's
        record. The same discipline as P5's verdict preview, and the server
        produces the list because a second opinion written in JavaScript would
        only ever disagree with the one that counts.
        """
        self.ensure_one()
        person = self._person()
        who = first_name(person.name) or person.name or _('this person')
        weeks = max(1, self.weeks or number(self.env, P_DEFAULT_WEEKS, 6))
        start = fields.Date.today()
        end = start + timedelta(weeks=weeks)
        every = CHECKIN_FREQ_DAYS.get(self.checkin_freq or 'weekly', 7)
        planned = min(MAX_CHECKINS, max(1, (weeks * 7) // every))
        employee_sees = flag(self.env, P_EMPLOYEE_VIEW)
        lines = [
            _('The plan runs from %(from)s to %(to)s.', **{'from': start,
                                                           'to': end}),
            _('%(count)s go in the diary, %(who)s and their manager in each '
              'one.',
              count=counted(planned, _('check-in'), _('check-ins')),
              who=who),
            _('A letter setting out the plan is prepared and filed with their '
              'documents.'),
        ]
        if employee_sees:
            lines.append(_(
                '%s is emailed and can read the plan on their own page, where '
                'they are asked to acknowledge it.', who))
        else:
            lines.append(_(
                'The employee page is switched off, so nothing is emailed to '
                '%s — the letter is filed and given to them by hand.', who))
        return {
            'lines': lines,
            'blocked': self._start_blockers(),
            'weeks': weeks,
            'end_date': str(end),
            'checkins': planned,
            'employee_sees': employee_sees,
        }

    def _start_blockers(self):
        """Everything in the way of starting, named. Never counted (R46)."""
        self.ensure_one()
        out = []
        if not self.objective_ids:
            out.append(_(
                'There are no objectives yet. A plan with no objectives is a '
                'threat with a date on it — add at least one.'))
            return out
        missing = [o.name or _('an objective') for o in self.objective_ids
                   if not (o.metric or '').strip()]
        if missing:
            out.append(_(
                'These have no "what good looks like" on them, so nobody '
                'could pass or fail them on evidence: %s.',
                joined_sentence(missing, limit=4)))
        if not (self.coaching_html or '').strip():
            out.append(_(
                'The coaching note is empty. Write down what was already '
                'said before the plan starts — it is what makes this fair.'))
        return out

    def action_start_plan(self):
        """Objectives, dates, check-ins, letter — and only then, the person."""
        self.ensure_one()
        self._require_hr()
        if self.state not in ('coaching', 'requested'):
            raise UserError(_(
                "This plan is already running — it is at \"%(where)s\".",
                where=PIP_STATE_LABEL.get(self.state, self.state or '')))
        blockers = self._start_blockers()
        if blockers:
            # The whole reason each blocker is a SENTENCE: the reader has to be
            # able to go and fix it without asking anybody what it meant.
            raise UserError('\n\n'.join(blockers))

        weeks = max(1, self.weeks or number(self.env, P_DEFAULT_WEEKS, 6))
        start = fields.Date.today()
        end = start + timedelta(weeks=weeks)
        self.sudo().write({
            'state': 'active',
            'weeks': weeks,
            'start_date': start,
            'end_date': end,
            'coaching_end': self.coaching_end or start,
        })
        made = self._schedule_checkins()
        letter = self._prepare_letter()
        self.message_post(body=_(
            "The plan is running from %(from)s to %(to)s. %(checkins)s are in "
            "the diary and %(objectives)s were agreed.",
            **{'from': start, 'to': end,
               'checkins': counted(made, _('check-in'), _('check-ins')),
               'objectives': counted(len(self.objective_ids),
                                     _('objective'), _('objectives'))}))
        # THE PERSON IS TOLD LAST, and only if their own page is switched on.
        # An email that says "read your plan here" pointing at a page that
        # 404s is worse than no email at all.
        if flag(self.env, P_EMPLOYEE_VIEW):
            self._mail('pb_pip.mail_template_pip_started',
                       self._employee_address())
        else:
            self.message_post(body=_(
                "The employee page is switched off, so nothing was emailed. "
                "The letter is filed with their documents."))
        return {'checkins': made,
                'letter_id': letter.id if letter else 0,
                'end_date': str(end)}

    def _schedule_checkins(self):
        """Every conversation, in the diary, on the day the plan starts.

        IDEMPOTENT ON THE DATE. A plan re-started (or a job that reaches this
        twice) must not double the diary, so a check-in already sitting on the
        same day for the same case IS that check-in.
        """
        self.ensure_one()
        Checkin = self.env['pb.employee.checkin'].sudo()
        every = CHECKIN_FREQ_DAYS.get(self.checkin_freq or 'weekly', 7)
        owner = self.hr_owner_user_id or self.env.user
        existing = {c.scheduled_date for c in self.checkin_ids}
        made, when = 0, (self.start_date or fields.Date.today())
        end = self.end_date or (when + timedelta(weeks=self.weeks or 6))
        for _index in range(MAX_CHECKINS):
            when = when + timedelta(days=every)
            if when > end:
                break
            if when in existing:
                continue
            try:
                Checkin.create({
                    'employee_id': self.employee_id.id,
                    'kind': 'pip',
                    'pip_case_id': self.id,
                    'owner_user_id': owner.id,
                    'scheduled_date': when,
                    'company_id': (self.company_id or self.env.company).id,
                })
                made += 1
            except Exception:           # noqa: BLE001 — one date, one grave
                _logger.exception('pb_pip: could not plan the check-in on %s '
                                  'for plan %s', when, self.id)
        return made

    def _cancel_open_checkins(self, why):
        """Take the rest of the diary back when a plan ends early."""
        self.ensure_one()
        open_rows = self.checkin_ids.filtered(
            lambda c: c.state == 'scheduled')
        if not open_rows:
            return 0
        open_rows.sudo().write({'state': 'cancelled'})
        self.message_post(body=_(
            "%(count)s were taken out of the diary because %(why)s.",
            count=counted(len(open_rows), _('check-in was'),
                          _('check-ins were')), why=why))
        return len(open_rows)

    # =====================================================================
    #  3. THE PERSON'S OWN PAGE
    # =====================================================================
    def action_acknowledge(self):
        """They have read it. Once, and it cannot be un-pressed.

        Called ONLY from the portal route, which has already proved the plan
        belongs to the session user — so this does not re-derive who is asking,
        it just refuses to stamp a second time.
        """
        self.ensure_one()
        if self.employee_ack:
            return False
        self.sudo().write({'employee_ack': True,
                           'ack_at': fields.Datetime.now()})
        self.message_post(body=_(
            "%(who)s has read the plan and acknowledged it.",
            who=self._person().name or _('The employee')))
        self._mail('pb_pip.mail_template_pip_acknowledged',
                   self._hr_addresses())
        return True

    # =====================================================================
    #  4. THE EVALUATION
    # =====================================================================
    def action_evaluate(self):
        """Ask the manager how each objective actually went.

        The objectives themselves become the questions, which is the only
        honest way to evaluate a plan: a generic form asks about the person,
        and this asks about the things that were written down and agreed.
        """
        self.ensure_one()
        self._require_hr()
        if self.state != 'active':
            raise UserError(_(
                "A plan is evaluated once it is running — this one is at "
                "\"%(where)s\".",
                where=PIP_STATE_LABEL.get(self.state, self.state or '')))
        self.sudo().state = 'evaluation'
        request = self._make_eval_request()
        self.message_post(body=_(
            "The plan has reached its end and %(who)s has been asked to say "
            "how each objective went.",
            who=(self.requested_by_user_id.name if self.requested_by_user_id
                 else _('their manager'))))
        return {'request_id': request.id if request else 0,
                'link': request._token_url() if request else ''}

    def _make_eval_request(self):
        """One private link for the manager. Idempotent on (case).

        The respondent is the manager who raised it, falling back to the
        person's line manager. THE KEY IS THE CASE and nothing else — R49's
        lesson: an idempotency test that can match on an empty value matches
        every other row that is also empty, and on this database most people
        have no login.
        """
        self.ensure_one()
        if self.eval_request_id:
            return self.eval_request_id
        Feedback = self.env['pb.feedback.request'].sudo()
        existing = Feedback.search([('pip_case_id', '=', self.id)], limit=1)
        if existing:
            self.sudo().eval_request_id = existing.id
            return existing

        respondent = self.requested_by_user_id
        manager = self._person().parent_id
        email = ''
        if respondent and respondent.email:
            email = respondent.email
        elif manager and manager.work_email:
            email = manager.work_email
        elif self.hr_owner_user_id and self.hr_owner_user_id.email:
            email = self.hr_owner_user_id.email

        questions = []
        for objective in self.objective_ids:
            questions.append({
                'key': '%s%s' % (EVAL_OBJECTIVE_PREFIX, objective.id),
                'type': 'rating',
                'label': '%s — %s' % (
                    objective.name or _('Objective'),
                    objective.metric or _('what good looks like was not '
                                          'written down')),
            })
        questions.extend(EVAL_QUESTIONS)
        try:
            request = Feedback.create({
                'subject_employee_id': self.employee_id.id,
                'respondent_user_id': respondent.id if respondent else False,
                'respondent_email': email or False,
                'kind': 'pip',
                'pip_case_id': self.id,
                'window_end': fields.Date.today() + timedelta(
                    days=EVAL_WINDOW_DAYS),
                'questions_json': json.dumps(questions),
                'company_id': (self.company_id or self.env.company).id,
            })
        except Exception:               # noqa: BLE001
            _logger.exception('pb_pip: could not create the evaluation form '
                              'for plan %s', self.id)
            return self.env['pb.feedback.request'].browse()
        self.sudo().eval_request_id = request.id
        if flag(self.env, P_PIP_MAIL) and email:
            try:
                request.action_send()
            except Exception:           # noqa: BLE001
                _logger.exception('pb_pip: could not send the evaluation form '
                                  'for plan %s', self.id)
        return request

    def evaluation_answers(self):
        """What the manager said, put back beside the objective it is about.

        Never raises — it feeds a screen, and a screen that will not open
        because one answer is unreadable JSON is worse than a screen with one
        answer missing.
        """
        self.ensure_one()
        out = {'answered': False, 'when': '', 'objectives': [], 'notes': []}
        request = self.eval_request_id
        if not request:
            return out
        out['answered'] = request.state == 'submitted'
        out['when'] = str(request.submitted_at or '')
        try:
            payload = json.loads(request.sudo().answers_json or '{}') or {}
        except Exception:               # noqa: BLE001
            _logger.warning('pb_pip: unreadable evaluation answers on plan %s',
                            self.id)
            payload = {}
        by_id = {o.id: o for o in self.objective_ids}
        for key, item in payload.items():
            if key.startswith('_'):
                continue
            value = (item or {}).get('value')
            if value in (None, ''):
                continue
            if key.startswith(EVAL_OBJECTIVE_PREFIX):
                try:
                    objective = by_id.get(
                        int(key[len(EVAL_OBJECTIVE_PREFIX):]))
                except (TypeError, ValueError):
                    objective = None
                if not objective:
                    continue
                out['objectives'].append({
                    'id': objective.id,
                    'name': objective.name or '',
                    'metric': objective.metric or '',
                    'status': objective.status,
                    'status_label': OBJECTIVE_STATE_LABEL.get(
                        objective.status, ''),
                    'score': str(value),
                })
            else:
                out['notes'].append({
                    'label': next((q['label'] for q in EVAL_QUESTIONS
                                   if q['key'] == key),
                                  (item or {}).get('label') or key),
                    'value': str(value),
                })
        return out

    # =====================================================================
    #  5. THE DECISION
    # =====================================================================
    def verdict_preview(self, verdict):
        """What pressing Confirm will do. Said before, never after."""
        self.ensure_one()
        person = self._person()
        who = first_name(person.name) or person.name or _('this person')
        if verdict == 'pass':
            lines = [
                _('%s comes off the plan. It is recorded as completed '
                  'successfully.', who),
                _('Any check-ins still in the diary are taken back out.'),
                _('Their performance rating is set from the number you give '
                  'below.'),
                _('Their manager and the HR team are told. Nothing is filed '
                  'in their documents.'),
            ]
        else:
            lines = [
                _('%s is recorded as not having completed the plan.', who),
                _('The HR team is told, with what you write below.'),
                _('NOTHING about their leaving is started. If that is where '
                  'this is going, somebody has to press "Start their exit" '
                  'afterwards, having read this.'),
            ]
        return {'verdict': verdict,
                'label': VERDICT_LABEL.get(verdict, ''),
                'lines': lines,
                'blocked': [],
                'blocked_text': ''}

    def action_verdict(self, verdict, rating=None, note=None,
                       objective_states=None):
        """Decide, and do everything that follows from deciding."""
        self.ensure_one()
        self._require_hr()
        if verdict not in VERDICT_LABEL:
            raise UserError(_("Choose one of the two outcomes."))
        if self.state in ('passed', 'failed', 'terminated'):
            raise UserError(_(
                "This plan was already closed on %(when)s.",
                when=self.closed_at or _('an earlier date')))
        if self.state not in ('active', 'evaluation'):
            raise UserError(_(
                "Nothing has been agreed with this person yet, so there is "
                "nothing to decide. Start the plan first."))

        # The per-objective answers, written before the state changes so the
        # record shows what the decision was actually made on.
        if objective_states:
            self._write_objective_states(objective_states)

        vals = {'verdict': verdict,
                'state': VERDICT_STATE[verdict],
                'verdict_at': fields.Datetime.now(),
                'verdict_by': self.env.uid,
                'closed_at': fields.Datetime.now()}
        if note is not None:
            vals['outcome_note'] = (note or '').strip()[:4000] or False
        if rating not in (None, '', False):
            try:
                vals['final_rating'] = max(1, min(5, int(rating)))
            except (TypeError, ValueError):
                pass
        self.sudo().write(vals)
        self._cancel_open_checkins(
            _('the plan was closed') if verdict == 'fail'
            else _('the plan was completed'))

        if verdict == 'pass':
            self._write_performance_rating()
            self._mail('pb_pip.mail_template_pip_passed',
                       self._employee_address() + self._manager_addresses())
        else:
            self._mail('pb_pip.mail_template_pip_failed',
                       self._hr_addresses() + self._manager_addresses())
        self.message_post(body=_(
            "Decision: %(what)s.%(note)s",
            what=VERDICT_LABEL.get(verdict, verdict),
            note=(' ' + (note or '')) if note else ''))
        return {'verdict': verdict,
                'needs_exit': verdict == 'fail',
                'state': self.state}

    def _write_objective_states(self, states):
        """`{objective_id: status}` from the wizard, applied one at a time."""
        self.ensure_one()
        by_id = {o.id: o for o in self.objective_ids}
        for key, value in (states or {}).items():
            try:
                objective = by_id.get(int(key))
            except (TypeError, ValueError):
                continue
            if not objective or value not in OBJECTIVE_STATE_LABEL:
                continue
            try:
                objective.sudo().status = value
            except Exception:           # noqa: BLE001
                _logger.exception('pb_pip: could not write objective %s',
                                  objective.id)
        return True

    def _write_performance_rating(self):
        """Carry the agreed rating onto the employee record, if it exists.

        PROBED rather than depended on, exactly as P5's is:
        `wfp_performance_rating` comes from the workforce-planning module,
        which is not a dependency of this one, and a hard reference would make
        this phase refuse to install on a database that does not have it.
        Absent field, log line, carry on. It is a SELECTION on this build, so
        the value written is the STRING.
        """
        self.ensure_one()
        if not self.final_rating:
            return False
        emp = self._person()
        if 'wfp_performance_rating' not in emp._fields:
            _logger.info('pb_pip: no performance rating field on this build — '
                         'plan %s did not write one', self.id)
            return False
        try:
            value = max(1, min(5, int(self.final_rating)))
            field = emp._fields['wfp_performance_rating']
            emp.sudo().write({
                'wfp_performance_rating':
                    str(value) if field.type == 'selection' else value})
            self.message_post(body=_(
                "Their performance rating was set to %s out of 5.", value))
            return True
        except Exception:               # noqa: BLE001
            _logger.exception('pb_pip: could not write the performance rating '
                              'for plan %s', self.id)
            return False

    # ------------------------------------------------------- the exit button
    def action_start_exit(self):
        """Open the leaving checklist — reusing P4's own way in.

        NOT a second implementation, and NOT automatic. `setup_offboarding()`
        is what P4 built for exactly this: it creates the clearances and the
        exit questionnaire, and it is idempotent, so reaching the same case
        from a resignation and from here leaves one set of rows behind (R30).
        Cloned from `pb.probation.review.action_start_exit`, which made the
        same call for the same reason.
        """
        self.ensure_one()
        self._require_hr()
        if self.verdict != 'fail':
            raise UserError(_(
                "An exit is only ever started from a plan that was not "
                "completed."))
        emp = self._person()
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
                'anchor_date': self.end_date or fields.Date.today(),
                'source': 'manual',
                'company_id': (self.company_id or self.env.company).id,
            })
            case.action_open()
        else:
            case.setup_offboarding()
        self.sudo().exit_case_id = case.id
        case.message_post(body=_(
            "Opened because an improvement plan was not completed."))
        self.message_post(body=_(
            "The leaving checklist is open — %s.",
            counted(len(case.task_ids), _('step'), _('steps'))))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pb.journey.case',
            'res_id': case.id,
            'view_mode': 'form',
        }

    # =====================================================================
    #  6. THEY LEFT.  (P4's extension point lands here.)
    # =====================================================================
    @api.model
    def _terminate_for_employee(self, employee, reason=None):
        """Close every running plan for somebody who is leaving.

        NEVER RAISES, and that is a contract rather than a courtesy: this is
        reached from `pb.resignation._on_resignation_approved`, inside the
        approval transaction, and a failure here must not undo an approval the
        person has already been emailed about.

        Also honest about doing nothing: switched off, or no open plan, it
        answers zero rather than pretending.
        """
        try:
            if not flag(self.env, P_AUTO_TERMINATE):
                _logger.info('pb_pip: auto-close on resignation is switched '
                             'off')
                return 0
            employee = self._as_employee(employee)
            if not employee:
                return 0
            cases = self.sudo().search([
                ('employee_id', '=', employee.id),
                ('state', 'in', PIP_OPEN),
            ])
            closed = 0
            for case in cases:
                try:
                    case.action_terminate(reason=reason)
                    closed += 1
                except Exception:       # noqa: BLE001 — one plan, one grave
                    _logger.exception('pb_pip: could not close plan %s after '
                                      'a resignation', case.id)
            if closed:
                _logger.info('pb_pip: closed %s improvement plan(s) for '
                             'employee %s after a resignation',
                             closed, employee.id)
            return closed
        except Exception:               # noqa: BLE001 — the outer promise
            _logger.exception('pb_pip: the resignation hook failed for %s',
                              employee)
            return 0

    def action_terminate(self, reason=None):
        """Close a plan because the person is going, not because it failed.

        A SEPARATE STATE from `failed` on purpose. Somebody who resigns in week
        three of a plan has not failed it — nobody ever found out — and a record
        that says otherwise is a record that will be read wrongly in two years.
        """
        self.ensure_one()
        if self.state not in PIP_OPEN:
            return False
        self.sudo().write({
            'state': 'terminated',
            'closed_at': fields.Datetime.now(),
            'outcome_note': self.outcome_note or (reason or _(
                'Closed because they are leaving the company.')),
        })
        self._cancel_open_checkins(_('they are leaving the company'))
        self.message_post(body=_(
            "Closed because %(who)s is leaving the company. %(why)s",
            who=self._person().name or _('the employee'),
            why=reason or _(
                'This is not a failed plan — nobody found out either way.')))
        self._mail('pb_pip.mail_template_pip_terminated', self._hr_addresses())
        return True

    # =====================================================================
    #  THE CHECK-IN NUDGES
    # =====================================================================
    @api.model
    def _nudge_missed_checkins(self, today=None):
        """A check-in nobody held is the earliest sign a plan is drifting.

        P0's daily job already writes to the owner of every check-in planned
        for TODAY, and a PIP check-in is a check-in — so this deliberately does
        not send a second copy of that. What it adds is the thing P0 has no way
        to know about: a conversation that was planned on a running improvement
        plan and did not happen.

        IDEMPOTENT. The row is marked `missed` in the same breath as the alert,
        so tomorrow's run finds nothing to say. One try/except per record, and
        an honest count in the log.
        """
        today = today or fields.Date.today()
        days = max(1, number(self.env, P_MISSED_DAYS, 2))
        cutoff = today - timedelta(days=days)
        Checkin = self.env['pb.employee.checkin'].sudo()
        stale = Checkin.search([
            ('pip_case_id', '!=', False),
            ('state', '=', 'scheduled'),
            ('scheduled_date', '!=', False),
            ('scheduled_date', '<', cutoff),
            ('pip_case_id.state', 'in', list(PIP_OPEN)),
        ])
        made = 0
        for row in stale:
            try:
                case = row.pip_case_id
                row.write({'state': 'missed'})
                if case._mail('pb_pip.mail_template_pip_checkin_missed',
                              case._hr_addresses()):
                    made += 1
                case.message_post(body=_(
                    "The check-in planned for %(when)s did not happen. The HR "
                    "owner has been told.", when=row.scheduled_date))
            except Exception:           # noqa: BLE001
                _logger.exception('pb_pip: missed check-in alert for %s',
                                  row.id)
        if stale:
            _logger.info('pb_pip: %s missed check-in(s), %s alert(s) sent',
                         len(stale), made)
        return made

    # ---------------------------------------------------------- the letter
    def _prepare_letter(self):
        """Prepare and file the plan letter. Never raises.

        A letter that could not be produced is a letter somebody writes by
        hand, and it must not undo a plan that has already started and put six
        conversations in the diary.

        NOT EMAILED FROM HERE. `action_send()` on the letter would put the PDF
        in the person's inbox before the page that explains it exists; the
        started-plan email points them at `/my/growth`, where the same letter
        is one click away with the plan around it.
        """
        self.ensure_one()
        template = self.env.ref(LETTER_PIP, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_pip: %s is missing — no letter for plan %s',
                            LETTER_PIP, self.id)
            return self.env['pb.hr.letter'].browse()
        try:
            objectives = '<ul>%s</ul>' % ''.join(
                '<li><b>%s</b>%s</li>' % (
                    escape(o.name or ''),
                    (' — %s' % escape(o.metric)) if o.metric else '')
                for o in self.objective_ids)
            letter = self.env['pb.hr.letter'].sudo().create({
                'employee_id': self.employee_id.id,
                'template_id': template.id,
                'context_json': json.dumps({
                    'plan_start': str(self.start_date or ''),
                    'plan_end': str(self.end_date or ''),
                    'objectives': objectives,
                    'checkin_freq': _('every week')
                    if (self.checkin_freq or 'weekly') == 'weekly'
                    else _('every two weeks'),
                    'hr_owner': (self.hr_owner_user_id.name
                                 if self.hr_owner_user_id else ''),
                }),
                'company_id': (self.company_id or self.env.company).id,
            })
            letter.action_generate()
            self.sudo().letter_id = letter.id
            return letter
        except Exception:               # noqa: BLE001
            _logger.exception('pb_pip: could not prepare the letter for plan '
                              '%s', self.id)
            return self.env['pb.hr.letter'].browse()

    # ------------------------------------------------------------- the mail
    def _mail(self, xmlid, addresses):
        """Queue one message. Never raises; never counts a dead letter.

        `email_to` is passed EXPLICITLY (R6): a template's own rendered address
        can reach `mail.mail` empty and the message is then created, queued and
        addressed to nobody with no error anywhere.

        And note R47 — on this database a message queued with
        `force_send=False` goes out within the second, so every address that
        reaches here in a test has to be one nobody reads.
        """
        self.ensure_one()
        if not flag(self.env, P_PIP_MAIL):
            _logger.info('pb_pip: improvement-plan emails are switched off')
            return False
        clean, seen = [], set()
        for address in (addresses or []):
            address = (address or '').strip()
            if address and address.lower() not in seen:
                seen.add(address.lower())
                clean.append(address)
        if not clean:
            _logger.info('pb_pip: plan %s — nobody to write to', self.id)
            return False
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_pip: %s is missing', xmlid)
            return False
        try:
            template.sudo().send_mail(
                self.id, force_send=False,
                email_values={'email_to': ','.join(clean),
                              'auto_delete': False})
            return True
        except Exception:               # noqa: BLE001
            _logger.exception('pb_pip: could not queue %s for plan %s',
                              xmlid, self.id)
            return False

    def _hr_addresses(self):
        """The HR owner, then everybody in the PIP group for this company.

        `res.groups.all_user_ids` and NOT `group_ids` — direct membership
        misses everybody who holds the group through `implied_ids`, which is
        most administrators (R7).
        """
        self.ensure_one()
        out = []
        if self.hr_owner_user_id and self.hr_owner_user_id.email:
            out.append(self.hr_owner_user_id.email)
        for xmlid in (GROUP_USER, GROUP_HEAD):
            try:
                group = self.env.ref(xmlid, raise_if_not_found=False)
                if not group:
                    continue
                company = self.company_id or self.env.company
                for user in group.sudo().all_user_ids:
                    if not user.email or not user.active:
                        continue
                    if company and user.company_ids \
                            and company.id not in user.company_ids.ids:
                        continue
                    out.append(user.email)
            except Exception:           # noqa: BLE001
                _logger.debug('pb_pip: no HR addresses from %s', xmlid)
        return out

    def _manager_addresses(self):
        self.ensure_one()
        out = []
        if self.requested_by_user_id and self.requested_by_user_id.email:
            out.append(self.requested_by_user_id.email)
        manager = self._person().parent_id
        if manager and manager.work_email:
            out.append(manager.work_email)
        return out

    def _employee_address(self):
        self.ensure_one()
        emp = self._person()
        return [a for a in (emp.work_email, emp.private_email) if a][:1]

    # ------------------------------------------------------------ the reader
    @api.model
    def for_employee(self, employee):
        """The plan this person's own page should show, or nothing.

        Only the states in which they have something to read — a request
        nobody has taken up yet is deliberately invisible to them, and so is a
        plan that closed six months ago.
        """
        employee = self._as_employee(employee)
        if not employee:
            return self.browse()
        return self.sudo().search([
            ('employee_id', '=', employee.id),
            ('state', 'in', list(PIP_EMPLOYEE_VISIBLE)),
        ], order='start_date desc, id desc', limit=1)

    def state_label(self):
        self.ensure_one()
        return PIP_STATE_LABEL.get(self.state, self.state or '')

    def greeting(self):
        """"Tâm" — the given name, wherever it sits in the full one."""
        self.ensure_one()
        return first_name(self._person().name)

    def action_open_letter(self):
        self.ensure_one()
        if not self.letter_id:
            raise UserError(_(
                "There is no letter yet — one is prepared when the plan "
                "starts."))
        return self.letter_id.action_open_pdf()
