# -*- coding: utf-8 -*-
"""LEARNING L4 — sessions, attendance and toolbox talks.

Training that happens in a room or on site becomes a record like any other:

  * `slide.channel` gains `delivery` (online / in a room / both), the hours a
    session usually lasts, whether attending finishes the course, whether
    people may book a seat themselves and whether attending files a
    certificate;
  * `pb.training.session`     one sitting of a course: when, where, who runs
                              it, how many seats, and where it has got to
                              (planned → invitations sent → under way →
                              closed, or cancelled);
  * `pb.training.attendance`  one person at one session: booked, waiting for
                              a seat, attended, did not come, cancelled — with
                              the hours it counts for.

ATTENDANCE COMPLETES THE ASSIGNMENT. A classroom course is still a course: a
booking puts the person on it through the existing assignment engine (reason
"One-off", due the session day) when they are not on it already, and the
assignment's ONE progress answer (`_progress`) says "finished" for a classroom
course when the person attended. So reminders, more time, paths (L3), required
training (L2), hours and the Numbers all follow without a second rule.

NEVER `hr.attendance` (handover F4): that table is pay-side working time.
Training attendance is its own table. No faces are ever stored (ruling D13).

THE DIARY ENTRY IS QUIET (ruling D12): our own mail carries the calendar file;
the `calendar.event` only puts the session in people's diaries and is created
and moved under `QUIET`, copied from pb_hiring (not imported — this module does
not depend on hiring).

The practical sign-off (`signoff`) is reserved for a later phase (owner decision
LD5) and deliberately not built here.
"""

import base64
import logging
import re
import secrets
from datetime import datetime, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import format_date

from .training_common import (
    ASSIGN_OPEN, GROUP_MANAGER, GROUP_ADMIN, as_id, leg, tr,
)

_logger = logging.getLogger(__name__)

DELIVERY = [
    ('online', 'Online'),
    ('session', 'In a room or on site'),
    ('blended', 'Online and in a room'),
]
DELIVERY_LABEL = dict(DELIVERY)
SESSION_DELIVERY = ('session', 'blended')

SESSION_KINDS = [
    ('classroom', 'Classroom'),
    ('onsite', 'On site'),
    ('toolbox', 'Toolbox talk'),
]
SESSION_KIND_LABEL = dict(SESSION_KINDS)

SESSION_STATES = [
    ('planned', 'Planned'),
    ('open', 'Invitations sent'),
    ('held', 'Under way'),
    ('closed', 'Closed'),
    ('cancelled', 'Cancelled'),
]
SESSION_STATE_LABEL = dict(SESSION_STATES)
SESSION_LIVE = ('planned', 'open', 'held')

ATT_STATES = [
    ('booked', 'Booked'),
    ('waitlisted', 'Waiting for a seat'),
    ('attended', 'Attended'),
    ('no_show', 'Did not come'),
    ('cancelled', 'Cancelled'),
]
ATT_STATE_LABEL = dict(ATT_STATES)
#: Somebody holding a seat (or who used one).
ATT_SEATED = ('booked', 'attended')
#: A row that still counts as "on the session".
ATT_LIVE = ('booked', 'waitlisted', 'attended', 'no_show')

ATT_HOW = [
    ('qr', 'Scanned the code'),
    ('trainer', 'Ticked by the trainer'),
    ('self', 'Checked in themselves'),
]

#: The calendar quiet context (ruling D12) — copied from
#: `pb_hiring/models/google_p5.py:47-49`, plus the follower notice, so the
#: diary entry never mails anybody: our own invitation carries the file.
QUIET = dict(dont_notify=True, no_mail_to_attendees=True,
             mail_create_nolog=True, mail_notrack=True, send_updates=False,
             mail_auto_subscribe_no_notify=True, tracking_disable=True)

#: Context key: a booking or a toolbox talk is making the assignment, so the
#: assignment's own "a course has been added" mails stay quiet — the session
#: invitation is the announcement (and a toolbox talk is already over).
NO_ANNOUNCE = 'pb_training_no_announce'

#: The photo of a sign-in sheet (toolbox talk): the vault's limits.
PHOTO_MIMES = ('image/jpeg', 'image/png', 'image/webp', 'application/pdf')
PHOTO_MAX_BYTES = 5 * 1024 * 1024

#: The engine's own attendance-certificate report (this module).
SESSION_CERT_REPORT = 'pb_training.report_session_certificate'


# =========================================================================
#  the calendar file
# =========================================================================
def _ics_esc(text):
    out = (text or '')
    out = out.replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,')
    return out.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\n')


def _ics_stamp(value):
    return value.strftime('%Y%m%dT%H%M%SZ')


def _ics_fold(line):
    raw = line.encode('utf-8')
    if len(raw) <= 75:
        return line
    parts, chunk = [], b''
    for ch in line:
        enc = ch.encode('utf-8')
        if len(chunk) + len(enc) > 73:
            parts.append(chunk.decode('utf-8'))
            chunk = b''
        chunk += enc
    parts.append(chunk.decode('utf-8'))
    return '\r\n '.join(parts)


def build_session_ics(summary, dt_start, dt_end, uid, method='REQUEST',
                      location='', description='', organizer=None,
                      attendees=None, sequence=0):
    """One event as an iCalendar file (bytes).

    The same shape as `pb_lifecycle.models.ics.build_ics` (handover F1) with a
    METHOD: `REQUEST` for an invitation, `CANCEL` (and `STATUS:CANCELLED`)
    when a session is called off. Kept here rather than added to
    pb_lifecycle so this phase upgrades one module only; the uid is stable per
    session so a calendar replaces the entry instead of adding a second one.
    """
    now = datetime.utcnow()
    safe_uid = re.sub(r'[^A-Za-z0-9@._-]', '', uid or '') or (
        '%s@payobook' % _ics_stamp(now))
    method = 'CANCEL' if method == 'CANCEL' else 'REQUEST'
    lines = [
        'BEGIN:VCALENDAR', 'VERSION:2.0',
        'PRODID:-//Payobook//Learning//EN', 'CALSCALE:GREGORIAN',
        'METHOD:%s' % method,
        'BEGIN:VEVENT',
        'UID:%s' % safe_uid,
        'SEQUENCE:%s' % int(sequence or 0),
        'DTSTAMP:%s' % _ics_stamp(now),
        'DTSTART:%s' % _ics_stamp(dt_start),
        'DTEND:%s' % _ics_stamp(dt_end or dt_start + timedelta(hours=1)),
        'SUMMARY:%s' % _ics_esc(summary),
    ]
    if description:
        lines.append('DESCRIPTION:%s' % _ics_esc(description))
    if location:
        lines.append('LOCATION:%s' % _ics_esc(location))
    if organizer:
        lines.append('ORGANIZER:mailto:%s' % organizer)
    for who in (attendees or []):
        if who:
            lines.append(
                'ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=FALSE:mailto:%s' % who)
    lines += ['STATUS:%s' % ('CANCELLED' if method == 'CANCEL'
                             else 'CONFIRMED'),
              'END:VEVENT', 'END:VCALENDAR']
    return ('\r\n'.join(_ics_fold(x) for x in lines) + '\r\n').encode('utf-8')


# =========================================================================
#  the course
# =========================================================================
class SlideChannelSessions(models.Model):
    _inherit = 'slide.channel'

    delivery = fields.Selection(
        DELIVERY, string='How it is taught', default='online', required=True,
        help='Online: lessons on the training page. In a room or on site: '
             'the course is a session people attend. Online and in a room: '
             'both, and attending is part of finishing it.')
    session_hours = fields.Float(
        string='A session usually lasts (hours)', digits=(6, 2),
        help='New sessions of this course start with this length.')
    attendance_completes = fields.Boolean(
        string='Attending finishes the course', default=True,
        help='Ticked: attending a session marks the course finished for that '
             'person (and, for a course that is also online, the lessons and '
             'the test still count).')
    self_booking = fields.Boolean(
        string='People may book a seat themselves',
        help='Ticked: somebody put on this course sees its open sessions on '
             'their training page with a "Book a seat" button.')
    session_certificate = fields.Boolean(
        string='Attending files a certificate',
        help='Ticked: closing a session files a certificate on the record of '
             'everybody who attended.')
    session_validity_months = fields.Integer(
        string='That certificate is valid for (months)',
        help='Empty or 0: it never runs out.')
    session_ids = fields.One2many('pb.training.session', 'channel_id',
                                  string='Sessions')

    def _pb_is_session(self):
        self.ensure_one()
        return self.sudo().delivery in SESSION_DELIVERY

    def _pb_session_hours(self):
        self.ensure_one()
        sudo = self.sudo()
        return float(sudo.session_hours or sudo.pb_hours or 1.0)


# =========================================================================
#  one session
# =========================================================================
class PbTrainingSession(models.Model):
    _name = 'pb.training.session'
    _description = 'Training session'
    _inherit = ['mail.thread']
    _order = 'start desc, id desc'

    name = fields.Char(string='Session', compute='_compute_name', store=True)
    channel_id = fields.Many2one(
        'slide.channel', string='Course', required=True, index=True,
        ondelete='restrict')
    kind = fields.Selection(SESSION_KINDS, string='Kind', required=True,
                            default='classroom')
    start = fields.Datetime(string='Starts', required=True, index=True)
    minutes = fields.Integer(string='Minutes', default=60)
    stop = fields.Datetime(string='Ends', compute='_compute_stop',
                           store=True, index=True)
    place = fields.Char(string='Where')
    join_url = fields.Char(string='Join link',
                           help='Optional: a link for people joining from '
                                'somewhere else.')
    trainer_id = fields.Many2one('hr.employee', string='Trainer',
                                 index=True, ondelete='set null')
    trainer_name = fields.Char(string='Outside trainer')
    seats = fields.Integer(string='Seats', default=0,
                           help='0 = as many as come.')
    state = fields.Selection(SESSION_STATES, string='Where it has got to',
                             default='planned', required=True, index=True,
                             tracking=True)
    attendance_ids = fields.One2many('pb.training.attendance', 'session_id',
                                     string='People')
    hours = fields.Float(string='Hours it counts for', digits=(6, 2))
    notes = fields.Html(string='Notes')
    event_id = fields.Many2one('calendar.event', string='Diary entry',
                               ondelete='set null', copy=False,
                               readonly=True)
    qr_token = fields.Char(string='Attendance code', index=True, copy=False,
                           readonly=True)
    invite_sequence = fields.Integer(default=0, copy=False, readonly=True)
    reminded = fields.Boolean(string='Day-before reminder sent', copy=False,
                              readonly=True)
    photo_id = fields.Many2one('ir.attachment', string='Sign-in sheet photo',
                               ondelete='set null', copy=False)
    logged_by_id = fields.Many2one('res.users', string='Logged by',
                                   readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)

    booked_count = fields.Integer(compute='_compute_counts')
    attended_count = fields.Integer(compute='_compute_counts')
    waiting_count = fields.Integer(compute='_compute_counts')
    no_show_count = fields.Integer(compute='_compute_counts')
    waitlist_ids = fields.Many2many('hr.employee', string='Waiting for a seat',
                                    compute='_compute_counts')
    when_words = fields.Char(compute='_compute_words')
    where_words = fields.Char(compute='_compute_words')
    seats_words = fields.Char(compute='_compute_words')
    state_words = fields.Char(compute='_compute_words')

    _qr_token_uniq = models.Constraint(
        'unique(qr_token)',
        'Two sessions cannot share the same attendance code.')

    # ------------------------------------------------------------ computes
    @api.depends('start', 'minutes')
    def _compute_stop(self):
        for rec in self:
            rec.stop = rec.start + timedelta(minutes=max(rec.minutes or 0, 0)) \
                if rec.start else False

    @api.depends('channel_id', 'start')
    def _compute_name(self):
        for rec in self:
            course = rec.channel_id.sudo().name or _('Session')
            day = rec._local(rec.start).date() if rec.start else None
            rec.name = '%s · %s' % (course, day.strftime('%d %b %Y')) \
                if day else course

    @api.depends('attendance_ids.state')
    def _compute_counts(self):
        for rec in self:
            rows = rec.attendance_ids
            rec.booked_count = len(rows.filtered(
                lambda a: a.state in ATT_SEATED))
            rec.attended_count = len(rows.filtered(
                lambda a: a.state == 'attended'))
            waiting = rows.filtered(lambda a: a.state == 'waitlisted')
            rec.waiting_count = len(waiting)
            rec.no_show_count = len(rows.filtered(
                lambda a: a.state == 'no_show'))
            rec.waitlist_ids = waiting.mapped('employee_id')

    @api.depends('start', 'minutes', 'place', 'join_url', 'seats', 'state',
                 'attendance_ids.state')
    def _compute_words(self):
        for rec in self:
            rec.when_words = rec._when_words()
            rec.where_words = rec._where_words()
            rec.seats_words = rec._seats_words()
            rec.state_words = tr(self.env, SESSION_STATE_LABEL.get(
                rec.state or 'planned', ''))

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Session')

    # ------------------------------------------------------------ the words
    def _tz(self):
        """The reader's zone, else whoever made the session, else the
        company's, else UTC — a time on a screen is a local time."""
        self.ensure_one()
        return (self.env.context.get('tz') or self.env.user.tz
                or self.create_uid.tz or self.company_id.partner_id.tz
                or 'UTC')

    def _local(self, value):
        if not value:
            return value
        try:
            zone = pytz.timezone(self._tz())
        except Exception:               # noqa: BLE001 — an odd zone is UTC
            zone = pytz.utc
        return pytz.utc.localize(value).astimezone(zone).replace(tzinfo=None)

    def _when_words(self, env=None):
        """"Thu 12 Nov 2026 · 09:00–11:00" in the reader's language."""
        self.ensure_one()
        env = env or self.env
        if not self.start:
            return ''
        start = self._local(self.start)
        stop = self._local(self.stop or self.start)
        try:
            day = format_date(env, start.date(), date_format='EEE d MMM yyyy')
        except Exception:               # noqa: BLE001 — a word is not fatal
            day = start.strftime('%a %d %b %Y')
        return '%s · %s–%s' % (day, start.strftime('%H:%M'),
                               stop.strftime('%H:%M'))

    def _where_words(self, env=None):
        self.ensure_one()
        env = env or self.env
        if self.place:
            return self.place
        if self.join_url:
            return tr(env, 'Online')
        return tr(env, 'Place not set yet')

    def _seats_words(self, env=None):
        """"12 of 20 seats · 3 waiting" — whole pieces (R117)."""
        self.ensure_one()
        env = env or self.env
        booked = self.booked_count
        if self.seats:
            bits = [tr(env, '%s of %s seats', booked, self.seats)]
        else:
            bits = [tr(env, '1 booked') if booked == 1
                    else tr(env, '%s booked', booked)]
        if self.waiting_count:
            bits.append(tr(env, '%s waiting', self.waiting_count))
        return ' · '.join(bits)

    def _trainer_words(self):
        self.ensure_one()
        return self.trainer_id.sudo().name or self.trainer_name or ''

    # ------------------------------------------------------------ the rules
    @api.constrains('channel_id')
    def _check_course(self):
        for rec in self:
            if rec.channel_id and not rec.channel_id.sudo()._pb_is_session():
                raise ValidationError(_(
                    "%s is an online course. Set it to \"In a room or on "
                    "site\" (or both) on the course before planning a "
                    "session.", rec.channel_id.sudo().name))

    @api.constrains('minutes', 'seats', 'hours')
    def _check_numbers(self):
        for rec in self:
            if rec.minutes < 0 or rec.seats < 0 or rec.hours < 0:
                raise ValidationError(_("These numbers cannot be below zero."))

    @api.model_create_multi
    def create(self, vals_list):
        Channel = self.env['slide.channel'].sudo()
        for vals in vals_list:
            if not vals.get('qr_token'):
                vals['qr_token'] = secrets.token_urlsafe(18)
            channel = Channel.browse(as_id(vals.get('channel_id'))).exists()
            if 'minutes' not in vals and channel:
                vals['minutes'] = int(round(channel._pb_session_hours() * 60))
            if not vals.get('hours'):
                vals['hours'] = round(max(vals.get('minutes') or 60, 0) / 60.0,
                                      2)
        return super().create(vals_list)

    # =====================================================================
    #  who may run it
    # =====================================================================
    def _is_manager(self):
        user = self.env.user
        return user.has_group(GROUP_MANAGER) or user.has_group(GROUP_ADMIN)

    def _check_editable(self):
        for rec in self:
            if rec.state in ('closed', 'cancelled'):
                raise UserError(_(
                    "This session is %s. A training manager can open it "
                    "again if something needs changing.",
                    tr(self.env, SESSION_STATE_LABEL[rec.state]).lower()))

    # =====================================================================
    #  booking
    # =====================================================================
    def _free_seats(self):
        self.ensure_one()
        if not self.seats:
            return 10 ** 6
        return max(self.seats - self.booked_count, 0)

    def _ensure_assignment(self, emp):
        """The person's open assignment on this course, or a new one made
        for this session (reason One-off, due the session day). Nothing for
        somebody with no login (an assignment needs one) — their attendance
        still counts in hours and on their record."""
        self.ensure_one()
        Assignment = self.env['pb.training.assignment'].sudo()
        open_row = Assignment.search([
            ('channel_id', '=', self.channel_id.id),
            ('employee_id', '=', emp.id),
            ('state', 'in', ASSIGN_OPEN)], limit=1)
        if open_row:
            return open_row
        if not emp.user_id or not emp.user_id.partner_id:
            return Assignment.browse()
        due = self._local(self.start).date() if self.start else None
        res = Assignment.with_context(
            allowed_company_ids=[(emp.company_id or self.company_id).id],
            **{NO_ANNOUNCE: True}).assign_many(
            self.channel_id.id, [emp.id], 'adhoc', due,
            extra={'session_id': self.id})
        if res.get('made'):
            return Assignment.browse(res['made'][0])
        return Assignment.browse()

    def _book(self, employees, by_user=None, send=True, state=None,
              how=None):
        """Put people on this session. Idempotent (one row per person —
        safety rail 3). Returns {'booked', 'waitlisted', 'already'} as lists
        of names. Beyond the seats a person waits; a cancelled row comes back
        to life rather than a second row being made."""
        self.ensure_one()
        Att = self.env['pb.training.attendance'].sudo()
        out = {'booked': [], 'waitlisted': [], 'already': []}
        rows = self.attendance_ids.sudo()
        for emp in employees.sudo():
            row = rows.filtered(lambda a: a.employee_id == emp)[:1]
            if row and row.state != 'cancelled':
                out['already'].append(emp.name or '')
                continue
            if state:
                new_state = state
            else:
                new_state = 'booked' if self._free_seats() > 0 \
                    else 'waitlisted'
            assignment = self._ensure_assignment(emp)
            vals = {'state': new_state,
                    'assignment_id': assignment.id or False,
                    'hours': self.hours}
            if new_state == 'attended':
                vals.update({'checked_in_at': fields.Datetime.now(),
                             'how': how or 'trainer'})
            if row:
                row.write(dict(vals, invited=False, reminded=False))
            else:
                row = Att.create(dict(vals, session_id=self.id,
                                      employee_id=emp.id,
                                      company_id=(emp.company_id
                                                  or self.company_id).id))
                rows |= row
            self.invalidate_recordset(['attendance_ids', 'booked_count',
                                      'waiting_count'])
            key = 'waitlisted' if new_state == 'waitlisted' else 'booked'
            out[key].append(emp.name or '')
            # Booking after the invitations went out sends this person's at
            # once (handover §3.3).
            if send and new_state == 'booked' and \
                    self.state in ('open', 'held'):
                leg(self.env, 'send the session invitation',
                    lambda r=row: r._send_invite())
        if send and self.state in ('open', 'held'):
            leg(self.env, 'diary entry', self._sync_event)
        return out

    def _unbook(self, attendance, reason_mail=True):
        """Take one person off. Their seat goes to the first person waiting;
        a course put on them only for this session (and not started) goes
        too."""
        self.ensure_one()
        att = attendance.sudo()
        if att.state in ('cancelled',):
            return False
        had_seat = att.state == 'booked'
        att.write({'state': 'cancelled'})
        att._drop_session_assignment()
        if had_seat:
            self._promote()
        if self.state in ('open', 'held'):
            leg(self.env, 'diary entry', self._sync_event)
        return True

    def _promote(self):
        """Fill free seats from the waiting list, first come first served,
        and tell each person their seat is free."""
        self.ensure_one()
        promoted = self.env['pb.training.attendance']
        waiting = self.attendance_ids.sudo().filtered(
            lambda a: a.state == 'waitlisted').sorted('id')
        for att in waiting:
            self.invalidate_recordset(['attendance_ids', 'booked_count'])
            if self._free_seats() <= 0:
                break
            att.write({'state': 'booked'})
            promoted |= att
            if self.state in ('open', 'held'):
                leg(self.env, 'seat-free mail', lambda a=att: a._send_mail(
                    'pb_training.mail_template_session_seat_free',
                    with_ics=True))
                att.sudo().write({'invited': True})
        return promoted

    # =====================================================================
    #  the lifecycle
    # =====================================================================
    def action_send_invites(self):
        """planned → open: every booked person (and the trainer) gets the
        invitation with the calendar file; the quiet diary entry is made."""
        sent = 0
        for rec in self:
            rec._check_editable()
            if rec.state == 'planned':
                rec.write({'state': 'open'})
            rec.sudo().write({'invite_sequence': rec.invite_sequence + 1})
            for att in rec.attendance_ids.sudo().filtered(
                    lambda a: a.state == 'booked' and not a.invited):
                if leg(self.env, 'send the session invitation',
                       att._send_invite):
                    sent += 1
            leg(self.env, 'tell the trainer', rec._send_trainer_invite)
            leg(self.env, 'diary entry', rec._sync_event)
        return sent

    def action_start(self):
        for rec in self:
            rec._check_editable()
            if rec.state != 'held':
                rec.write({'state': 'held'})
        return True

    def action_close(self, note=None):
        """Booked but absent → did not come; hours written; the linked
        assignments brought up to date (attending finishes the course);
        certificates filed; the session becomes read-only."""
        closed = 0
        for rec in self:
            if rec.state in ('closed', 'cancelled'):
                continue
            rows = rec.attendance_ids.sudo()
            rows.filtered(lambda a: a.state == 'booked').write(
                {'state': 'no_show'})
            rows.filtered(lambda a: a.state == 'waitlisted').write(
                {'state': 'cancelled'})
            for att in rows.filtered(lambda a: a.state == 'attended'):
                vals = {}
                if not att.hours:
                    vals['hours'] = rec.hours
                if not att.assignment_id:
                    assignment = rec._ensure_assignment(att.employee_id)
                    if assignment:
                        vals['assignment_id'] = assignment.id
                if vals:
                    att.write(vals)
            rec.write({'state': 'closed'})
            for att in rows.filtered(lambda a: a.state == 'attended'):
                if att.assignment_id:
                    att.assignment_id._refresh()
                leg(self.env, 'file the session certificate',
                    lambda a=att: self.env['pb.training.certificate']
                    .file_session_certificate(a))
            rec.message_post(body=note or _(
                "Closed: %(here)s attended, %(away)s did not come.",
                here=rec.attended_count, away=rec.no_show_count))
            closed += 1
        return closed

    def action_reopen(self):
        if not self._is_manager():
            raise AccessError(_("Only a training manager can open a closed "
                                "session again."))
        for rec in self:
            if rec.state != 'closed':
                continue
            rec.write({'state': 'held'})
            rec.message_post(body=_("Opened again by %s.",
                                    self.env.user.name or ''))
        return True

    def action_cancel(self):
        """Everybody's booking is cancelled, the people who had an
        invitation get a cancellation with the calendar file (METHOD:
        CANCEL), the diary entry is archived, and a course put on somebody
        only for this session (and not started) is taken off again."""
        for rec in self:
            if rec.state in ('closed', 'cancelled'):
                raise UserError(_("This session is already %s.", tr(
                    self.env, SESSION_STATE_LABEL[rec.state]).lower()))
            rows = rec.attendance_ids.sudo().filtered(
                lambda a: a.state in ('booked', 'waitlisted'))
            told = rows.filtered('invited')
            rec.write({'state': 'cancelled'})
            for att in told:
                leg(self.env, 'cancellation mail', lambda a=att: a._send_mail(
                    'pb_training.mail_template_session_cancelled',
                    with_ics=True, method='CANCEL'))
            rows.write({'state': 'cancelled'})
            for att in rows:
                att._drop_session_assignment()
            if rec.event_id:
                leg(self.env, 'archive the diary entry',
                    lambda r=rec: r.event_id.sudo().with_context(
                        **QUIET).write({'active': False}))
            rec.message_post(body=_("Cancelled by %s.",
                                    self.env.user.name or ''))
        return True

    # =====================================================================
    #  the calendar
    # =====================================================================
    def _ics_uid(self):
        self.ensure_one()
        return 'pbtraining-session-%s@payobook' % self.id

    def _ics(self, method='REQUEST', attendees=None):
        self.ensure_one()
        organizer = (self.trainer_id.sudo().work_email or
                     self.env.user.email or '').strip() or None
        return build_session_ics(
            self.channel_id.sudo().name or _('Training session'),
            self.start, self.stop, self._ics_uid(), method=method,
            location=self.place or self.join_url or '',
            description=self._ics_description(),
            organizer=organizer, attendees=attendees,
            sequence=self.invite_sequence)

    def _ics_description(self):
        self.ensure_one()
        bits = [self.channel_id.sudo().name or '']
        trainer = self._trainer_words()
        if trainer:
            bits.append(_("Trainer: %s", trainer))
        if self.join_url:
            bits.append(_("Join: %s", self.join_url))
        return '\n'.join(b for b in bits if b)

    def _ics_attachment(self, method='REQUEST'):
        self.ensure_one()
        data = self._ics(method=method)
        return self.env['ir.attachment'].sudo().create({
            'name': 'session.ics' if method != 'CANCEL'
            else 'session-cancelled.ics',
            'raw': data,
            'mimetype': 'text/calendar',
            'res_model': self._name,
            'res_id': self.id,
        })

    def _event_partners(self):
        self.ensure_one()
        partners = self.attendance_ids.sudo().filtered(
            lambda a: a.state in ATT_SEATED).mapped('partner_id')
        trainer_user = self.trainer_id.sudo().user_id
        if trainer_user:
            partners |= trainer_user.partner_id
        return partners

    def _sync_event(self):
        """The quiet diary entry: made on the first invitation, moved and
        re-peopled after, archived on cancel. Never mails anybody."""
        self.ensure_one()
        if 'calendar.event' not in self.env or not self.start:
            return False
        Event = self.env['calendar.event'].sudo().with_context(**QUIET)
        vals = {
            'name': self.channel_id.sudo().name or _('Training session'),
            'start': self.start,
            'stop': self.stop or self.start + timedelta(hours=1),
            'location': self.place or self.join_url or '',
            'partner_ids': [(6, 0, self._event_partners().ids)],
        }
        if self.event_id:
            self.event_id.with_context(**QUIET).write(vals)
            return self.event_id
        trainer_user = self.trainer_id.sudo().user_id
        vals['user_id'] = (trainer_user or self.env.user).id
        event = Event.create(vals)
        self.sudo().write({'event_id': event.id})
        return event

    def _send_trainer_invite(self):
        self.ensure_one()
        email = (self.trainer_id.sudo().work_email or '').strip()
        if not email:
            return False
        template = self.env.ref('pb_training.mail_template_session_trainer',
                                raise_if_not_found=False)
        if not template:
            return False
        attachment = self._ics_attachment()
        template.sudo().send_mail(self.id, force_send=False, email_values={
            'email_to': email, 'auto_delete': False,
            'attachment_ids': [(6, 0, attachment.ids)]})
        return True

    # =====================================================================
    #  the attendance screen
    # =====================================================================
    def _attend_url(self):
        self.ensure_one()
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        return '%s/my/training/attend/%s' % (base.rstrip('/'),
                                             self.sudo().qr_token)

    def _qr_src(self, size=400):
        """The stock QR route (handover F3): a PNG from reportlab, public."""
        self.ensure_one()
        from urllib.parse import quote
        return '/report/barcode/?barcode_type=QR&value=%s&width=%s&height=%s' \
            % (quote(self._attend_url(), safe=''), size, size)

    def qr_src(self, size=220):
        """The sign-in sheet's QR (a report template calls it)."""
        self.ensure_one()
        return self._qr_src(size)

    def sheet_rows(self):
        """The sign-in sheet's rows: everybody on the session, by name."""
        self.ensure_one()
        rows = self.attendance_ids.sudo().filtered(
            lambda a: a.state in ATT_LIVE)
        out = [{'name': a.employee_id.name or '',
                'department': a.employee_id.department_id.name or '',
                'checked_in': a._checked_in_words()} for a in rows]
        return sorted(out, key=lambda r: r['name'].lower())

    def _scan_window_open(self, now=None):
        """A scan counts while the session is under way, or — if the trainer
        never pressed Start — from an hour before it to an hour after."""
        self.ensure_one()
        if self.state == 'held':
            return True
        if self.state != 'open' or not self.start:
            return False
        now = now or fields.Datetime.now()
        stop = self.stop or self.start
        return self.start - timedelta(hours=1) <= now <= \
            stop + timedelta(hours=1)


# =========================================================================
#  one person at one session
# =========================================================================
class PbTrainingAttendance(models.Model):
    _name = 'pb.training.attendance'
    _description = 'Training session attendance'
    _order = 'id'

    session_id = fields.Many2one('pb.training.session', string='Session',
                                 required=True, index=True,
                                 ondelete='cascade')
    channel_id = fields.Many2one(related='session_id.channel_id', store=True,
                                 index=True, string='Course')
    employee_id = fields.Many2one('hr.employee', string='Who', required=True,
                                  index=True, ondelete='cascade')
    partner_id = fields.Many2one(
        'res.partner', string='Their contact', index=True,
        compute='_compute_partner', store=True, readonly=True)
    assignment_id = fields.Many2one(
        'pb.training.assignment', string='The course it completes',
        index=True, ondelete='set null')
    state = fields.Selection(ATT_STATES, string='Where they stand',
                             required=True, default='booked', index=True)
    checked_in_at = fields.Datetime(string='Checked in at')
    how = fields.Selection(ATT_HOW, string='How they checked in')
    hours = fields.Float(string='Hours', digits=(6, 2))
    note = fields.Char(string='Note')
    invited = fields.Boolean(string='Invitation sent', copy=False)
    reminded = fields.Boolean(string='Reminder sent', copy=False)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)

    session_start = fields.Datetime(related='session_id.start', store=True,
                                    string='Session starts')

    _person_once = models.Constraint(
        'unique(session_id, employee_id)',
        'That person is already on this session.')

    @api.depends('employee_id')
    def _compute_partner(self):
        for rec in self:
            emp = rec.employee_id.sudo()
            rec.partner_id = emp.user_id.partner_id.id if emp.user_id \
                else False

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (
                rec.employee_id.sudo().name or _('Somebody'),
                rec.session_id.sudo().name or _('a session'))

    # ------------------------------------------------------------ marking
    def _mark(self, state, how='trainer'):
        for rec in self.sudo():
            vals = {'state': state}
            if state == 'attended':
                vals['how'] = how
                if not rec.checked_in_at:
                    vals['checked_in_at'] = fields.Datetime.now()
                if not rec.hours:
                    vals['hours'] = rec.session_id.hours
            elif state in ('booked', 'no_show'):
                vals['checked_in_at'] = False
                vals['how'] = False
            rec.write(vals)
        return True

    def _drop_session_assignment(self):
        """A course put on somebody only for this session, never started and
        not needed by another of their bookings, goes when the booking goes
        (the path precedent: never take away work somebody started)."""
        for rec in self.sudo():
            row = rec.assignment_id
            if not row or row.session_id != rec.session_id \
                    or row.state == 'done' or row.path_enrolment_id:
                continue
            other = self.search_count([
                ('id', '!=', rec.id), ('assignment_id', '=', row.id),
                ('state', 'in', ('booked', 'waitlisted', 'attended'))])
            if other:
                continue
            try:
                started = row._progress().get('done')
            except Exception:           # noqa: BLE001 — keep it when unsure
                started = True
            if started:
                continue
            rec.write({'assignment_id': False})
            row.unlink()
        return True

    # ------------------------------------------------------------ mail
    def _email(self):
        self.ensure_one()
        emp = self.employee_id.sudo()
        return (emp.work_email or '').strip() or \
            (emp.user_id.email or '').strip()

    def _send_mail(self, xmlid, with_ics=False, method='REQUEST'):
        """One mail to this person (to the address, explicitly — R6)."""
        self.ensure_one()
        email = self._email()
        if not email:
            return False
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_training: %s is missing', xmlid)
            return False
        values = {'email_to': email, 'auto_delete': False}
        if with_ics:
            attachment = self.session_id.sudo()._ics_attachment(method)
            values['attachment_ids'] = [(6, 0, attachment.ids)]
        template.sudo().send_mail(self.id, force_send=False,
                                  email_values=values)
        return True

    def _send_invite(self):
        self.ensure_one()
        if self._send_mail('pb_training.mail_template_session_invite',
                           with_ics=True):
            self.sudo().write({'invited': True})
            return True
        return False

    # ------------------------------------------------------------ words
    def _state_word(self, env=None):
        self.ensure_one()
        return tr(env or self.env, ATT_STATE_LABEL.get(self.state, ''))

    def _checked_in_words(self):
        self.ensure_one()
        if not self.checked_in_at:
            return ''
        return self.session_id._local(self.checked_in_at).strftime('%H:%M')


# =========================================================================
#  the assignment: attending finishes a classroom course
# =========================================================================
class PbTrainingAssignmentSession(models.Model):
    _inherit = 'pb.training.assignment'

    session_id = fields.Many2one(
        'pb.training.session', string='Made for the session', index=True,
        ondelete='set null', readonly=True,
        help='Set when booking a session put this course on the person.')
    attendance_ids = fields.One2many('pb.training.attendance',
                                     'assignment_id', string='Sessions')

    def _attended_row(self):
        """The attendance that counts for this assignment: one linked to it,
        else any attended session of the course since it was put on."""
        self.ensure_one()
        Att = self.env['pb.training.attendance'].sudo()
        row = Att.search([('assignment_id', '=', self.id),
                          ('state', '=', 'attended')], limit=1)
        if row or not self.channel_id:
            return row
        domain = [('employee_id', '=', self.employee_id.id),
                  ('channel_id', '=', self.channel_id.id),
                  ('state', '=', 'attended')]
        if self.assigned_on:
            domain.append(('session_start', '>=', fields.Datetime.to_string(
                datetime.combine(self.assigned_on, datetime.min.time()))))
        return Att.search(domain, order='session_start desc', limit=1)

    def _progress(self):
        facts = super()._progress()
        channel = self.channel_id.sudo()
        if not channel or channel.delivery not in SESSION_DELIVERY \
                or not channel.attendance_completes:
            return facts
        attended = bool(self._attended_row())
        test_ok = facts.get('test') in ('passed', 'none')
        if channel.delivery == 'session':
            # Lesson counts are ignored; a test still gates if there is one.
            finished = attended and test_ok
        else:
            lessons_ok = facts.get('finished') or (
                not facts.get('total') and test_ok)
            finished = attended and bool(lessons_ok)
        return dict(facts, finished=finished, attended=attended,
                    percent=100 if finished else facts.get('percent', 0))

    def _refresh_one(self, today=None):
        was = self.state
        state = super()._refresh_one(today)
        if state == 'done' and was != 'done':
            att = self._attended_row() if self.channel_id.sudo().delivery \
                in SESSION_DELIVERY else None
            if att and att.hours:
                self.sudo().with_context(
                    tracking_disable=True, mail_notrack=True).write(
                    {'hours': att.hours})
        return state

    def _announce(self):
        if self.env.context.get(NO_ANNOUNCE):
            return True
        return super()._announce()

    def _payload(self, today=None):
        data = super()._payload(today)
        try:
            data['delivery'] = self.channel_id.sudo().delivery or 'online'
        except Exception:               # noqa: BLE001 — a word is not fatal
            data['delivery'] = 'online'
        return data


# =========================================================================
#  the certificate for attending
# =========================================================================
class PbEmployeeDocumentSession(models.Model):
    _inherit = 'pb.employee.document'

    attendance_id = fields.Many2one(
        'pb.training.attendance', string='Session attended', index=True,
        copy=False, ondelete='set null')


class PbTrainingCertificateSession(models.AbstractModel):
    _inherit = 'pb.training.certificate'

    @api.model
    def _render_session(self, attendance):
        """The attendance certificate as PDF bytes. Never fatal. One record
        id, one document (ledger LN33)."""
        try:
            report = self.env['ir.actions.report'].sudo().with_context(
                allowed_company_ids=[attendance.company_id.id])
            pdf, _kind = report._render_qweb_pdf(
                SESSION_CERT_REPORT, [attendance.id],
                data={'report_type': 'pdf'})
            return pdf
        except Exception:               # noqa: BLE001 — filing is not fatal
            _logger.warning('pb_training: the certificate for attendance %s '
                            'could not be rendered', attendance.id,
                            exc_info=True)
            return None

    @api.model
    def file_session_certificate(self, attendance):
        """File a certificate for one attended session, when the course says
        attending files one. Idempotent per attendance."""
        att = self.env['pb.training.attendance'].sudo().browse(
            as_id(attendance)).exists()
        if not att or att.state != 'attended':
            return None
        session = att.session_id
        channel = session.channel_id
        if not channel.session_certificate:
            return None
        if 'pb.employee.document' not in self.env:
            return None
        Doc = self.env['pb.employee.document'].sudo().with_context(
            active_test=False)
        existing = Doc.search([('attendance_id', '=', att.id)], limit=1)
        if existing:
            return existing
        emp = att.employee_id
        issued = session._local(session.start).date() if session.start \
            else fields.Date.today()
        pdf = self._render_session(att)
        if not pdf:
            return None
        name = self._document_name(channel.name,
                                   provider=fields.Date.to_string(issued))
        attachment = self.env['ir.attachment'].sudo().create({
            'name': '%s.pdf' % name, 'raw': pdf,
            'mimetype': 'application/pdf',
            'res_model': 'hr.employee', 'res_id': emp.id,
        })
        months = max(channel.session_validity_months or 0, 0)
        document = self._file(
            emp, name, attachment,
            note=_("Attended on %(when)s (%(hours)s hours).",
                   when=fields.Date.to_string(issued),
                   hours=('%g' % (att.hours or 0))),
            extra={
                'training_source': 'session',
                'channel_id': channel.id,
                'attendance_id': att.id,
                'issuer': session._trainer_words()
                or (emp.company_id or self.env.company).name or '',
                'issue_date': issued,
                'expiry_date': issued + relativedelta(months=months)
                if months else False,
            })
        if document and att.hours and 'hours' in document._fields:
            document.write({'hours': att.hours})
        return document
