# -*- coding: utf-8 -*-
"""`pb.hiring.interview` — the hour that decides it, and everything around it.

AN INTERVIEW IS A PROMISE TO FOUR PEOPLE AT ONCE: the candidate, who has to
take time off to be there; two or three panel members, who have to read a CV
first; and the recruiter, whose whole week is these hours. A hiring process
does not fall over because somebody makes a bad decision — it falls over
because nobody was told where to be, or because three people sat in a room and
then nobody ever wrote down what they thought.

So this model does four things and nothing else:

  * **It puts the hour in one place.** One row, one `calendar.event` behind it,
    and one invitation per person WITH AN ICS ATTACHMENT (ruling D3/D12: no
    external calendar is connected, so the meeting cannot exist twice and
    disagree with itself). The stock calendar's own branded invitation is
    silenced — every mail that leaves this module is ours.
  * **It chases.** A day before and half an hour before, once each, stamped so
    a job that runs every ten minutes cannot send the same reminder twice.
  * **It keeps the history when the hour moves.** A reschedule does not edit
    the row: it closes it, opens a new one and writes down WHY and WHOSE side
    caused it. Six weeks later "our hiring is slow" becomes a number somebody
    can act on rather than a feeling.
  * **It makes the opinions land.** Every panel member gets their own link and
    twenty-four WORKING hours to use it. An interview whose opinions are not
    all in cannot be marked done, because "done" would then mean "we have
    forgotten about it".

WHAT IT DELIBERATELY DOES NOT DO. It does not decide anything. The decision
lives on the debrief of the last round and, past that, on A3's offer.
"""

import base64
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.pb_lifecycle.models.ics import build_ics

from .hiring_common import (
    DEBRIEF_DECISIONS, DELAY_KINDS, FINAL_KINDS, INTERVIEW_MODES,
    INTERVIEW_STATES, NO_SHOW_BY, P_CANDIDATE_MAIL, P_FEEDBACK_HOURS,
    P_INTERVIEW_DURATION, STEP_KINDS, as_id, counted, flag, leg, number,
)

_logger = logging.getLogger(__name__)

_TODO = 'mail.mail_activity_data_todo'

#: A reschedule made inside this many minutes of the hour itself is not
#: refused — somebody's train really is cancelled — but it is MARKED, because
#: a panel that finds out with twenty minutes' notice has already left.
LATE_NOTICE_MINUTES = 30


class PbHiringInterview(models.Model):
    _name = 'pb.hiring.interview'
    _description = 'Interview'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start desc, id desc'

    # ------------------------------------------------------------- what it is
    requisition_id = fields.Many2one(
        'pb.hiring.requisition', string='Hiring request', required=True,
        index=True, ondelete='cascade')
    applicant_id = fields.Many2one(
        'hr.applicant', string='Candidate', required=True, index=True,
        ondelete='cascade')
    step_id = fields.Many2one(
        'pb.hiring.step', string='Which stage',
        help='The stage of this role the interview is for, as it was agreed '
             'on the hiring request.')
    round_no = fields.Integer(
        string='Round', default=1, readonly=True, copy=False,
        help='Which time this is that this candidate has been seen. Moving '
             'an interview keeps its round number — it is the same round, on '
             'a different day.')
    kind = fields.Selection(
        STEP_KINDS, string='What kind', default='interview', required=True,
        compute='_compute_kind', store=True, readonly=False)

    start = fields.Datetime(string='When', required=True, index=True,
                            tracking=True)
    duration_minutes = fields.Integer(
        string='How long, in minutes', required=True,
        default=lambda self: number(self.env, P_INTERVIEW_DURATION, 45))
    stop = fields.Datetime(string='Until', compute='_compute_stop', store=True,
                           index=True, readonly=True)
    mode = fields.Selection(INTERVIEW_MODES, string='How', default='in_person',
                            required=True)
    location = fields.Char(
        string='Where',
        help='A room, an address, or the link to the video call.')

    panel_employee_ids = fields.Many2many(
        'hr.employee', 'pb_hiring_interview_panel_rel', 'interview_id',
        'employee_id', string='Who is on the panel')
    recruiter_id = fields.Many2one('res.users', string='Recruiter', index=True,
                                   domain="[('share', '=', False)]")

    # R56 — one field of an `hr.employee` reads forty and half of them are
    # behind payroll groups. The same is true of an applicant on this build,
    # whose `requirements`-adjacent fields carry their own `groups=`, so the
    # candidate's name and address are read AS THE SYSTEM and stored here.
    # The security boundary stays the search that found the interview.
    candidate_name = fields.Char(string='Their name', compute='_compute_who',
                                 compute_sudo=True, store=True, readonly=True)
    candidate_email = fields.Char(string='Their email', compute='_compute_who',
                                  compute_sudo=True, store=True, readonly=True)
    job_id = fields.Many2one('hr.job', string='The job',
                             related='requisition_id.job_id', store=True,
                             readonly=True)

    event_id = fields.Many2one('calendar.event', string='The diary entry',
                               copy=False, ondelete='set null')

    # ---------------------------------------------------------- what happened
    state = fields.Selection(INTERVIEW_STATES, string='How it went',
                             default='scheduled', required=True, index=True,
                             tracking=True, copy=False)
    no_show_by = fields.Selection(NO_SHOW_BY, string='Who did not come',
                                  copy=False)
    no_show_note = fields.Text(string='What happened', copy=False)
    cancel_note = fields.Text(string='Why it was called off', copy=False)

    reminder_24h_sent = fields.Datetime(string='Day-before reminder sent',
                                        readonly=True, copy=False)
    reminder_30m_sent = fields.Datetime(string='Half-hour reminder sent',
                                        readonly=True, copy=False)

    rescheduled_from_id = fields.Many2one(
        'pb.hiring.interview', string='Moved from', copy=False,
        ondelete='set null')
    rescheduled_to_id = fields.Many2one(
        'pb.hiring.interview', string='Moved to', copy=False,
        ondelete='set null')
    reschedule_ids = fields.One2many('pb.hiring.reschedule', 'interview_id',
                                     string='Times it has moved')
    late_notice = fields.Boolean(
        string='Moved at short notice', readonly=True, copy=False,
        help='It was moved with less than half an hour to go, so somebody may '
             'already have set off.')

    # ------------------------------------------------------------- the panel
    feedback_ids = fields.One2many('pb.hiring.feedback', 'interview_id',
                                   string='What the panel thought')
    feedback_due_at = fields.Datetime(
        string='Opinions wanted by', readonly=True, copy=False,
        help='Twenty-four working hours after the interview, on this '
             "company's own working calendar.")
    feedback_in = fields.Integer(compute='_compute_feedback', string='In')
    feedback_total = fields.Integer(compute='_compute_feedback', string='Asked')
    feedback_late = fields.Integer(compute='_compute_feedback', string='Late')
    recommendation_avg = fields.Float(compute='_compute_feedback',
                                      string='Average recommendation')

    debrief_notes = fields.Text(string='What the panel agreed', copy=False)
    decision = fields.Selection(DEBRIEF_DECISIONS, string='The decision',
                                copy=False, tracking=True)
    decided_on = fields.Datetime(string='Decided on', readonly=True,
                                 copy=False)

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)

    # =====================================================================
    #  Names and small computes
    # =====================================================================
    def _compute_display_name(self):
        for rec in self:
            who = rec.candidate_name or _('a candidate')
            rec.display_name = _('Round %(n)s with %(who)s', n=rec.round_no or 1,
                                 who=who)

    @api.depends('step_id', 'step_id.kind')
    def _compute_kind(self):
        for rec in self:
            rec.kind = rec.step_id.kind or rec.kind or 'interview'

    @api.depends('start', 'duration_minutes')
    def _compute_stop(self):
        for rec in self:
            if not rec.start:
                rec.stop = False
                continue
            rec.stop = rec.start + timedelta(
                minutes=max(5, rec.duration_minutes or 45))

    @api.depends('applicant_id', 'applicant_id.partner_name',
                 'applicant_id.email_from')
    def _compute_who(self):
        for rec in self:
            app = rec.applicant_id
            rec.candidate_name = (app.partner_name or app.email_from
                                  or '') if app else ''
            rec.candidate_email = (app.email_from or '') if app else ''

    @api.depends('feedback_ids', 'feedback_ids.state',
                 'feedback_ids.recommendation', 'feedback_ids.due_at')
    def _compute_feedback(self):
        from .hiring_common import RECOMMENDATION_SCORE
        now = fields.Datetime.now()
        for rec in self:
            rows = rec.feedback_ids
            asked = rows.filtered(lambda r: r.state != 'expired')
            inb = rows.filtered(lambda r: r.state == 'submitted')
            rec.feedback_total = len(asked)
            rec.feedback_in = len(inb)
            rec.feedback_late = len(asked.filtered(
                lambda r: r.state == 'pending' and r.due_at
                and r.due_at < now))
            scores = [RECOMMENDATION_SCORE.get(r.recommendation)
                      for r in inb if r.recommendation]
            rec.recommendation_avg = (sum(scores) / len(scores)) if scores \
                else 0.0

    # =====================================================================
    #  Making one
    # =====================================================================
    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            # THE CHECK IS AT CREATION AND NOT A `constrains`, deliberately.
            # An hour that has already gone cannot be arranged — but an hour
            # that has gone can certainly be marked done, no-show or moved,
            # and a constraint would refuse every one of those writes on a
            # record whose whole job is to age.
            start = vals.get('start')
            if start:
                when = fields.Datetime.to_datetime(start)
                if when and when < now - timedelta(minutes=5):
                    raise ValidationError(_(
                        "That time has already gone. Pick a time in the "
                        "future — the candidate has to be able to get there."))
        records = super().create(vals_list)
        for rec in records:
            if not rec.round_no or rec.round_no < 1:
                rec.round_no = rec._next_round()
        return records

    def _next_round(self):
        """Which time this is that we are seeing this person.

        Counted rather than stored on the candidate, because a candidate can
        be in two pipelines at once and "round 2" means round two OF THIS
        ROLE. A cancelled hour never happened, so it does not count; a moved
        one is the same round on a different day and is carried across by the
        reschedule rather than recounted here.
        """
        self.ensure_one()
        if not self.applicant_id:
            return 1
        earlier = self.sudo().search_count([
            ('applicant_id', '=', self.applicant_id.id),
            ('id', '!=', self.id),
            ('state', 'not in', ('cancelled', 'rescheduled')),
        ])
        return earlier + 1

    @api.constrains('panel_employee_ids', 'state')
    def _check_panel(self):
        for rec in self:
            if rec.state == 'scheduled' and not rec.panel_employee_ids:
                raise ValidationError(_(
                    "An interview needs at least one person on the panel. "
                    "Nobody can give an opinion on a conversation they were "
                    "not in."))

    # =====================================================================
    #  R56 / R43 — people, read as the system, ids coerced at the door
    # =====================================================================
    @api.model
    def _person(self, employee):
        emp_id = as_id(employee)
        if not emp_id:
            return self.env['hr.employee'].sudo().browse()
        return self.env['hr.employee'].sudo().browse(emp_id).exists()

    def _panel_contacts(self):
        """`[(employee, address)]` for everybody on the panel who can be
        reached, read as the system.

        A panel member does not have to have a login — a plant manager who
        interviews two people a year usually does not — so the login's email
        is tried first and the employee's work address second. Somebody with
        neither is reported rather than silently dropped.
        """
        self.ensure_one()
        out = []
        for emp in self.panel_employee_ids.sudo():
            address = (emp.user_id.email or '').strip() \
                or (emp.work_email or '').strip()
            if not address:
                _logger.info(
                    'pb_hiring: %s is on the panel for interview %s and has '
                    'no email address anywhere, so they cannot be invited',
                    emp.name, self.id)
                continue
            out.append((emp, address))
        return out

    # =====================================================================
    #  Twenty-four WORKING hours
    # =====================================================================
    def _feedback_due(self):
        """When the opinions are wanted by.

        Twenty-four hours is meaningless on its own: an interview at four on
        a Friday would want an answer by four on a Saturday. It is twenty-four
        WORKING hours on the company's own calendar, which for a Vietnamese
        company at four on Friday is four on Tuesday.

        A company with no working calendar is answered honestly: plain
        twenty-four hours, and the log says so. Guessing somebody's working
        week is worse than admitting it is not configured.
        """
        self.ensure_one()
        hours = max(1, number(self.env, P_FEEDBACK_HOURS, 24))
        base = self.stop or self.start
        if not base:
            return False
        calendar = self.company_id.sudo().resource_calendar_id
        if not calendar:
            _logger.info(
                'pb_hiring: %s has no working calendar, so the feedback '
                'window on interview %s is a plain %s hours rather than %s '
                'working ones', self.company_id.name, self.id, hours, hours)
            return base + timedelta(hours=hours)
        try:
            return calendar.plan_hours(hours, base, compute_leaves=True)
        except Exception:               # noqa: BLE001 — never fail an invite
            _logger.warning('pb_hiring: the working-hours window could not be '
                            'worked out for interview %s', self.id,
                            exc_info=True)
            return base + timedelta(hours=hours)

    # =====================================================================
    #  The door
    # =====================================================================
    @api.model
    def schedule(self, values):
        """Arrange one interview and tell everybody about it.

        PUBLIC AND THEREFORE COERCED AT THE DOOR (R43): everything arrives as
        plain data. The gate is the facade's `_require_recruit()`; this method
        is about what an arranged interview IS.
        """
        values = values or {}
        applicant = self.env['hr.applicant'].sudo().browse(
            as_id(values.get('applicant_id'))).exists()
        if not applicant:
            raise UserError(_("Pick the candidate this interview is with."))
        req = self.env['pb.hiring.requisition'].sudo().browse(
            as_id(values.get('requisition_id'))).exists()
        if not req:
            req = applicant.pb_requisition_id
        if not req:
            raise UserError(_(
                "This candidate is not on a hiring request, so there is "
                "nothing to arrange an interview against."))
        panel = [as_id(p) for p in (values.get('panel_employee_ids') or [])]
        panel = [p for p in panel if p]
        if not panel:
            raise UserError(_(
                "Say who is on the panel. Nobody can give an opinion on a "
                "conversation they were not in."))
        start = values.get('start')
        if not start:
            raise UserError(_("Say when it is."))

        vals = {
            'requisition_id': req.id,
            'applicant_id': applicant.id,
            'start': start,
            'duration_minutes': int(values.get('duration_minutes')
                                    or number(self.env, P_INTERVIEW_DURATION,
                                              45)),
            'mode': values.get('mode') or 'in_person',
            'location': (values.get('location') or '').strip(),
            'panel_employee_ids': [(6, 0, panel)],
            'recruiter_id': (as_id(values.get('recruiter_id'))
                             or req.recruiter_id.id or False),
            'company_id': req.company_id.id,
        }
        if values.get('step_id'):
            vals['step_id'] = as_id(values['step_id'])
        if values.get('kind'):
            vals['kind'] = values['kind']
        interview = self.sudo().create(vals)
        interview._after_scheduled(move_stage=True)
        return interview

    def _after_scheduled(self, move_stage=True):
        """Everything that follows an hour being written down.

        Each piece is a LEG in its own savepoint (R131): the hour is arranged
        the moment the row exists, and a mail server that is down must never
        be able to undo that — nor to take the diary entry with it.
        """
        self.ensure_one()
        self.sudo().write({'feedback_due_at': self._feedback_due()})
        leg(self.env, 'the diary entry for interview %s' % self.id,
            self._ensure_event)
        leg(self.env, 'the feedback links for interview %s' % self.id,
            self._mint_feedback)
        if move_stage:
            leg(self.env, 'the candidate stage for interview %s' % self.id,
                self._move_candidate_stage)
        leg(self.env, 'the candidate invitation for interview %s' % self.id,
            self._invite_candidate)
        leg(self.env, 'the panel invitations for interview %s' % self.id,
            self._invite_panel)
        leg(self.env, "the recruiter's copy for interview %s" % self.id,
            self._invite_recruiter)
        return True

    # =====================================================================
    #  The diary entry
    # =====================================================================
    def _ensure_event(self):
        """One `calendar.event`, and NOT ONE BRANDED INVITATION.

        The stock calendar sends its own invitation the moment an attendee is
        created, from a template that is not ours and does not read like this
        product. `dont_notify` stops the alarm setup and
        `no_mail_to_attendees` stops the attendee mail
        (`calendar_attendee.py:140`) — both are needed, because they guard
        two different things. Our own invitation, with our own ICS, goes out
        from `_invite_candidate` / `_invite_panel` a few lines later.
        """
        self.ensure_one()
        if self.event_id:
            return self.event_id
        partners = self.env['res.partner'].sudo().browse()
        for emp in self.panel_employee_ids.sudo():
            if emp.user_id and emp.user_id.partner_id:
                partners |= emp.user_id.partner_id
        if self.recruiter_id and self.recruiter_id.partner_id:
            partners |= self.recruiter_id.partner_id
        event = self.env['calendar.event'].sudo().with_context(
            dont_notify=True, no_mail_to_attendees=True,
            mail_create_nolog=True, mail_notrack=True,
        ).create({
            'name': self._event_title(),
            'start': self.start,
            'stop': self.stop,
            'allday': False,
            'duration': max(5, self.duration_minutes or 45) / 60.0,
            'location': self.location or '',
            'description': self._agenda_text(),
            'partner_ids': [(6, 0, partners.ids)],
            'user_id': self.recruiter_id.id or self.env.uid,
            'applicant_id': self.applicant_id.id,
        })
        self.sudo().write({'event_id': event.id})
        return event

    def _event_title(self):
        self.ensure_one()
        return _('%(what)s: %(who)s — %(role)s',
                 what=dict(STEP_KINDS).get(self.kind, _('Interview')),
                 who=self.candidate_name or _('a candidate'),
                 role=self.requisition_id.title or '')

    def _agenda_text(self):
        """What the panel is supposed to have read before they walk in."""
        self.ensure_one()
        bits = []
        if self.step_id and self.step_id.notes:
            bits.append(self.step_id.notes)
        req = self.requisition_id.sudo()
        if req.requirements:
            bits.append(_("What the role needs:\n%s", req.requirements))
        if req.jd_current_id and req.jd_current_id.summary:
            bits.append(_("The advert says: %s", req.jd_current_id.summary))
        return '\n\n'.join(b for b in bits if b)

    def _ics(self, method='REQUEST'):
        """The invitation, as bytes. Naive UTC in, naive UTC out (D3)."""
        self.ensure_one()
        organiser = (self.recruiter_id.email or '').strip() or None
        attendees = [a for _emp, a in self._panel_contacts()]
        if self.candidate_email:
            attendees.append(self.candidate_email)
        return build_ics(
            summary=self._event_title(),
            dt_start=self.start,
            dt_end=self.stop,
            organizer=organiser,
            attendees=attendees,
            description=self._agenda_text(),
            location=self.location or '',
            uid='pbhiring-interview-%s@payobook' % self.id)

    def _ics_attachment(self, name='interview.ics'):
        self.ensure_one()
        return self.env['ir.attachment'].sudo().create({
            'name': name,
            'datas': base64.b64encode(self._ics()),
            'mimetype': 'text/calendar',
            'res_model': 'pb.hiring.interview',
            'res_id': self.id,
        })

    # =====================================================================
    #  The invitations — ours, every one of them
    # =====================================================================
    def _send(self, xmlid, to, with_ics=False, ics_name='interview.ics'):
        """One mail, addressed EXPLICITLY (R6).

        A template's own rendered `email_to` can reach `mail.mail` empty, and
        the message is then created, queued and addressed to nobody with no
        error anywhere. The recipient is always passed in.
        """
        self.ensure_one()
        if not to:
            return False
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.info('pb_hiring: the mail template %s is not in this '
                         'build', xmlid)
            return False
        email_values = {'email_to': to, 'auto_delete': False}
        if with_ics:
            email_values['attachment_ids'] = [
                (6, 0, self._ics_attachment(ics_name).ids)]
        template.sudo().send_mail(self.id, force_send=False,
                                  email_values=email_values)
        return True

    def _invite_candidate(self):
        self.ensure_one()
        if not flag(self.env, P_CANDIDATE_MAIL):
            _logger.info('pb_hiring: candidate mail is switched off; %s would '
                         'have been invited to interview %s',
                         self.candidate_email or 'nobody', self.id)
            return False
        if not self.candidate_email:
            _logger.info('pb_hiring: interview %s has no address for the '
                         'candidate, so no invitation was sent', self.id)
            return False
        return self._send('pb_hiring.mail_template_interview_candidate',
                          self.candidate_email, with_ics=True)

    def _invite_panel(self):
        """ONE MAIL PER PANEL MEMBER, never one mail to a list.

        A panel of three on one `email_to` is three people who can all see
        each other's addresses, and — far worse — one mail that either lands
        or does not. Separately sent, a member with a bad address is the only
        one who misses it, and the log says which.
        """
        self.ensure_one()
        sent = 0
        for _emp, address in self._panel_contacts():
            ok = self._send('pb_hiring.mail_template_interview_panel',
                            address, with_ics=True)
            sent += 1 if ok else 0
        return sent

    def _invite_recruiter(self):
        self.ensure_one()
        address = (self.recruiter_id.email or '').strip()
        if not address:
            return False
        return self._send('pb_hiring.mail_template_interview_recruiter',
                          address, with_ics=True)

    # =====================================================================
    #  The feedback links
    # =====================================================================
    def _mint_feedback(self):
        """One row per panel member, made once.

        Search-before-create on the MEMBER, so a reschedule that re-runs this
        does not double the number of opinions being waited for.
        """
        self.ensure_one()
        Feedback = self.env['pb.hiring.feedback'].sudo()
        made = 0
        for emp in self.panel_employee_ids.sudo():
            existing = Feedback.search_count([
                ('interview_id', '=', self.id),
                ('panel_employee_id', '=', emp.id)])
            if existing:
                continue
            Feedback.create({
                'interview_id': self.id,
                'panel_employee_id': emp.id,
                'due_at': self.feedback_due_at,
                'company_id': self.company_id.id,
            })
            made += 1
        return made

    def _move_candidate_stage(self):
        """The candidate moves to the stage this step names, and only then.

        A stage the hiring request never mentioned is a stage somebody would
        have to undo, so silence is the default: no stage on the step means
        the candidate stays exactly where the recruiter put them.
        """
        self.ensure_one()
        stage = self.step_id.sudo().stage_id if self.step_id else False
        if not stage:
            return False
        if self.applicant_id.sudo().stage_id.id == stage.id:
            return False
        self.applicant_id.sudo().write({'stage_id': stage.id})
        return True

    # =====================================================================
    #  Moving it
    # =====================================================================
    def reschedule(self, values):
        """The hour moves. The row does not.

        A reschedule that edits the start time in place destroys the only
        evidence that anything was ever moved — and "how often do we move
        interviews, and whose side does it" is the single most useful number
        a hiring process has. So the old row is closed as MOVED, a new one
        opens beside it, and a `pb.hiring.reschedule` records the reason and
        whose side it came from. Both are required, because a reschedule with
        no reason is exactly the one nobody can learn anything from.
        """
        self.ensure_one()
        values = values or {}
        if self.state != 'scheduled':
            raise UserError(_(
                "Only an interview that is still going to happen can be "
                "moved. This one is already marked “%s”.",
                dict(INTERVIEW_STATES).get(self.state, self.state)))
        reason = (values.get('reason') or '').strip()
        kind = values.get('delay_kind') or ''
        if not reason:
            raise UserError(_(
                "Say why it is moving. In six weeks nobody will remember, and "
                "this is the only place the answer will be."))
        if kind not in dict(DELAY_KINDS):
            raise UserError(_(
                "Say whose side moved it — ours or the candidate's. It is not "
                "about blame; it is the only way anybody can answer why "
                "hiring here takes as long as it does."))
        start = values.get('start')
        if not start:
            raise UserError(_("Say when it is moving to."))

        old_start = self.start
        late = bool(old_start and (
            fields.Datetime.to_datetime(old_start) - fields.Datetime.now()
        ) < timedelta(minutes=LATE_NOTICE_MINUTES))

        fresh = self.sudo().create({
            'requisition_id': self.requisition_id.id,
            'applicant_id': self.applicant_id.id,
            'step_id': self.step_id.id or False,
            'kind': self.kind,
            'start': start,
            'duration_minutes': int(values.get('duration_minutes')
                                    or self.duration_minutes or 45),
            'mode': values.get('mode') or self.mode,
            'location': values.get('location') if values.get('location')
            is not None else self.location,
            'panel_employee_ids': [(6, 0, self.panel_employee_ids.ids)],
            'recruiter_id': self.recruiter_id.id or False,
            'company_id': self.company_id.id,
            'rescheduled_from_id': self.id,
            'round_no': self.round_no or 1,
            'late_notice': late,
        })
        self.env['pb.hiring.reschedule'].sudo().create({
            'interview_id': self.id,
            'new_interview_id': fresh.id,
            'old_start': old_start,
            'new_start': fresh.start,
            'reason': reason,
            'delay_kind': kind,
            'late_notice': late,
            'by_user_id': self.env.uid,
            'company_id': self.company_id.id,
        })
        # THE RECORD SAYS IT BEFORE THE MAIL DOES. The cancellation template
        # reads the reason and the new time off this row, so both have to be
        # written first — a template that took them from the context would
        # render an empty sentence the day somebody sends the same mail from
        # anywhere else.
        self.sudo().write({'state': 'rescheduled',
                           'rescheduled_to_id': fresh.id,
                           'cancel_note': reason})
        # The old hour is called off BEFORE the new one goes out, so nobody
        # holds two invitations at once and wonders which is real.
        leg(self.env, 'calling off interview %s' % self.id,
            self._tell_everybody_it_is_off)
        leg(self.env, 'the diary entry for interview %s' % self.id,
            self._drop_event)
        self.sudo().message_post(body=_(
            "Moved to %(when)s. %(why)s", when=fresh.start, why=reason))
        # The candidate does not change stage again — they are on the same
        # round, and a second move would look like progress that has not
        # happened.
        fresh._after_scheduled(move_stage=False)
        return fresh

    def _drop_event(self):
        self.ensure_one()
        if not self.event_id:
            return False
        self.event_id.sudo().with_context(
            dont_notify=True, no_mail_to_attendees=True).write(
                {'active': False})
        return True

    def _tell_everybody_it_is_off(self):
        self.ensure_one()
        recipients = []
        if flag(self.env, P_CANDIDATE_MAIL) and self.candidate_email:
            recipients.append(self.candidate_email)
        recipients += [a for _emp, a in self._panel_contacts()]
        if self.recruiter_id and self.recruiter_id.email:
            recipients.append(self.recruiter_id.email)
        sent = 0
        for address in dict.fromkeys(recipients):
            ok = self._send('pb_hiring.mail_template_interview_off', address)
            sent += 1 if ok else 0
        return sent

    # =====================================================================
    #  Nobody came
    # =====================================================================
    def action_no_show(self, by=None, note=None):
        """Mandatory: whose side. Everything else about a no-show is
        forgettable and that one fact is not."""
        self.ensure_one()
        if by not in dict(NO_SHOW_BY):
            raise UserError(_(
                "Say who did not come — the candidate, or somebody on our "
                "side. An unexplained empty hour teaches nobody anything."))
        if self.state not in ('scheduled', 'done'):
            raise UserError(_("This interview is already closed."))
        self.sudo().write({'state': 'no_show', 'no_show_by': by,
                           'no_show_note': (note or '').strip()})
        # The opinions are not late — there is nothing to have an opinion
        # about. Closed with a reason rather than left waiting for ever.
        self.feedback_ids.sudo().filtered(
            lambda f: f.state == 'pending').write({
                'state': 'expired',
                'notes': _('Nobody came, so there was nothing to say.')})
        leg(self.env, 'the no-show to-do on interview %s' % self.id,
            self._raise_no_show_todo)
        self.sudo().message_post(body=_(
            "Nobody came — %(who)s. %(note)s",
            who=dict(NO_SHOW_BY).get(by, ''), note=(note or '').strip()))
        return True

    def _raise_no_show_todo(self):
        self.ensure_one()
        if not self.recruiter_id:
            return False
        self.sudo().activity_schedule(
            _TODO,
            summary=_('Nobody came: %s', self.candidate_name or ''),
            note=_("Decide what happens next — arrange it again, or close "
                   "the candidate off. The role stays where it is until "
                   "somebody says."),
            user_id=self.recruiter_id.id,
            date_deadline=fields.Date.context_today(self))
        return True

    # =====================================================================
    #  Marking it done
    # =====================================================================
    def action_mark_done(self, force=False):
        """DONE MEANS THE OPINIONS ARE IN, not that the hour has passed.

        An interview marked done with two of three opinions missing is how a
        candidate waits a fortnight for an answer nobody is working on. The
        refusal says exactly how many are outstanding and who they are
        waiting on, so it is an instruction rather than a wall.
        """
        self.ensure_one()
        if self.state == 'no_show':
            return True
        if self.state != 'scheduled':
            raise UserError(_("This interview is already closed."))
        pending = self.feedback_ids.filtered(lambda f: f.state == 'pending')
        if pending and not force:
            names = ', '.join(
                p.panel_employee_id.sudo().name or '' for p in pending)
            raise UserError(_(
                "Still waiting for %(n)s of %(total)s %(word)s — %(who)s. "
                "Their links are live; chase them, or record a no-show if the "
                "interview did not happen.",
                n=len(pending), total=len(self.feedback_ids),
                word=counted(len(self.feedback_ids), _('opinion'),
                             _('opinions')),
                who=names))
        self.sudo().write({'state': 'done'})
        self.sudo().message_post(body=_("Marked done."))
        return True

    def action_cancel(self, note=None):
        self.ensure_one()
        if self.state != 'scheduled':
            raise UserError(_("This interview is already closed."))
        self.feedback_ids.sudo().filtered(
            lambda f: f.state == 'pending').write({'state': 'expired'})
        self.sudo().write({'state': 'cancelled',
                           'cancel_note': (note or '').strip()})
        leg(self.env, 'calling off interview %s' % self.id,
            self._tell_everybody_it_is_off)
        leg(self.env, 'the diary entry for interview %s' % self.id,
            self._drop_event)
        self.sudo().message_post(body=_("Called off. %s", note or ''))
        return True

    # =====================================================================
    #  The debrief
    # =====================================================================
    def action_debrief(self, notes=None, decision=None):
        """The last round, written down while everybody still remembers it.

        ONLY ON A FINAL ROUND, and that is the point rather than a
        restriction: a decision recorded after round one is a decision taken
        before the process the hiring request itself set out has run.
        """
        self.ensure_one()
        if self.kind not in FINAL_KINDS:
            raise UserError(_(
                "A debrief belongs on the last conversation — a panel or the "
                "final one. This round is “%(kind)s”. Change the kind of this "
                "interview if it really was the last one.",
                kind=dict(STEP_KINDS).get(self.kind, self.kind)))
        if decision not in dict(DEBRIEF_DECISIONS):
            raise UserError(_(
                "Say what was decided: we want them, keep them warm, or not "
                "this time."))
        self.sudo().write({
            'debrief_notes': (notes or '').strip(),
            'decision': decision,
            'decided_on': fields.Datetime.now(),
        })
        if decision == 'select':
            self.requisition_id.sudo().write(
                {'selected_applicant_id': self.applicant_id.id})
            self.requisition_id.sudo().message_post(body=_(
                "%(who)s is the one, after round %(n)s.",
                who=self.candidate_name or '', n=self.round_no or 1))
        self.sudo().message_post(body=_(
            "Debrief: %(what)s. %(notes)s",
            what=dict(DEBRIEF_DECISIONS).get(decision, ''),
            notes=(notes or '').strip()))
        return True

    # =====================================================================
    #  The chasing
    # =====================================================================
    def _remind(self, which):
        """One reminder to everybody who is expected, stamped so it is sent
        once and only once."""
        self.ensure_one()
        xmlid = ('pb_hiring.mail_template_interview_tomorrow' if which == '24h'
                 else 'pb_hiring.mail_template_interview_soon')
        sent = 0
        if flag(self.env, P_CANDIDATE_MAIL) and self.candidate_email:
            sent += 1 if self._send(xmlid, self.candidate_email) else 0
        for _emp, address in self._panel_contacts():
            sent += 1 if self._send(xmlid, address) else 0
        if self.recruiter_id and self.recruiter_id.email:
            sent += 1 if self._send(xmlid, self.recruiter_id.email) else 0
        self.sudo().write({
            ('reminder_24h_sent' if which == '24h' else 'reminder_30m_sent'):
                fields.Datetime.now()})
        return sent

    # =====================================================================
    #  The doors (every hand-built act_window dict carries `views`, R125)
    # =====================================================================
    def action_open_applicant(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'hr.applicant',
                'res_id': self.applicant_id.id, 'view_mode': 'form',
                'views': [[False, 'form']],
                'name': self.candidate_name or _('Candidate'),
                'context': {'active_test': False}}

    def action_open_event(self):
        self.ensure_one()
        if not self.event_id:
            raise UserError(_("There is no diary entry behind this one."))
        return {'type': 'ir.actions.act_window',
                'res_model': 'calendar.event', 'res_id': self.event_id.id,
                'view_mode': 'form', 'views': [[False, 'form']],
                'name': self.event_id.name or ''}


class PbHiringReschedule(models.Model):
    """Every time an hour moved, why, and whose side it came from.

    Kept as its own table rather than as a note, because this is the raw
    material of the only honest answer to "why does hiring here take eleven
    weeks". A note cannot be counted.
    """
    _name = 'pb.hiring.reschedule'
    _description = 'Interview moved'
    _order = 'at desc, id desc'

    interview_id = fields.Many2one(
        'pb.hiring.interview', string='The interview', required=True,
        index=True, ondelete='cascade')
    new_interview_id = fields.Many2one(
        'pb.hiring.interview', string='Moved to', ondelete='set null')
    applicant_id = fields.Many2one(
        'hr.applicant', related='interview_id.applicant_id', store=True,
        index=True, readonly=True, string='Candidate')
    requisition_id = fields.Many2one(
        'pb.hiring.requisition', related='interview_id.requisition_id',
        store=True, index=True, readonly=True, string='Hiring request')
    old_start = fields.Datetime(string='Was', readonly=True)
    new_start = fields.Datetime(string='Now', readonly=True)
    reason = fields.Text(string='Why', required=True)
    delay_kind = fields.Selection(DELAY_KINDS, string='Whose side',
                                  required=True, index=True)
    late_notice = fields.Boolean(string='At short notice', readonly=True)
    by_user_id = fields.Many2one('res.users', string='Moved by', readonly=True,
                                 default=lambda self: self.env.user)
    at = fields.Datetime(string='Moved on', readonly=True,
                         default=fields.Datetime.now)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('Moved on %s', rec.at or '')
