# -*- coding: utf-8 -*-
"""`pb.hr.comm.post` — one announcement: what it says, who gets it, and when.

THE POST IS THE WHOLE THING, AND THAT IS WHY IT IS ONE RECORD. The words, the
poster, the audience and the moment are agreed together or not at all: an
announcement whose audience can be changed after somebody agreed the words is
an announcement nobody really agreed. So the audience is on the post, the
revision stamp covers all four, and the edit window protects them as a set.

THREE RULES ABOUT TIME, AND THEY ARE THE POINT OF THE MODULE.

  1. Up to two days before it goes out, the person responsible can change
     anything about it. That is the whole of their authority and it needs no
     group: the record rule finds their own posts, and this model's `write`
     lets them through.
  2. Inside those two days only the HR lead can, and the change is written
     into the post's own history where anybody can read it afterwards. A
     window that silently allows a late change is not a window.
  3. After it has gone out nothing changes, ever. The answer to "we need to
     say that differently" is a new announcement, and the button that makes
     one is on the screen.

WHAT THE SENDER IS ALLOWED TO DO. `state`, the counts and the stamps — never a
word of the content. The guard below names the content fields explicitly for
that reason: a job that could rewrite an announcement on its way out is a job
nobody can trust with four thousand mailboxes.
"""

import logging

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .comm_common import (
    AUDIENCE_KINDS, AUDIENCE_LABEL, CONTENT_FIELDS, GROUP_MANAGER,
    GROUP_USER, P_EDIT_WINDOW, P_SIGNOFF, POST_STATES, POST_STATE_LABEL,
    RECURRENCES, company_words, counted, flag, number,
)

_logger = logging.getLogger(__name__)


class PbHrCommPost(models.Model):
    _name = 'pb.hr.comm.post'
    _description = 'Announcement'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'biz.approval.chain.mixin']
    _order = 'send_at desc, id desc'

    #: The ladder the record keeps for itself when no route is published.
    #: Under a published route the shim takes every press and the route
    #: decides the order (ledger AM84); with nothing published — which is the
    #: shipped state, because sign-off is off — this is what makes the module
    #: usable at all.
    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('draft', 'scheduled'): None,
        ('submitted', 'scheduled'): GROUP_MANAGER,
        ('submitted', 'draft'): None,
        ('scheduled', 'draft'): None,
        ('draft', 'cancelled'): None,
        ('submitted', 'cancelled'): None,
        ('scheduled', 'cancelled'): None,
        ('sending', 'cancelled'): None,
        ('scheduled', 'sending'): None,
        ('scheduled', 'sent'): None,
        ('sending', 'sent'): None,
    }
    _approval_dead_states = ('cancelled',)

    # ------------------------------------------------------------ what it is
    subject = fields.Char(
        string='Subject', required=True, tracking=True,
        help='What people see in their inbox before they open anything.')
    body_html = fields.Html(
        string='What it says', sanitize=True,
        help='The announcement itself. It goes out inside a Payobook card '
             'with the company name on it.')
    poster_ids = fields.Many2many(
        'ir.attachment', 'pb_hr_comm_post_attachment_rel',
        'post_id', 'attachment_id', string='Poster',
        help='A picture or a PDF that goes out with it.')
    template_id = fields.Many2one(
        'pb.hr.comm.template', string='Start from',
        help='Copies a subject, some words and a poster in. After that this '
             'announcement is its own — changing the template later never '
             'changes this.')

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company, tracking=True)
    country_id = fields.Many2one(
        'res.country', string='Country',
        related='company_id.partner_id.country_id', readonly=True,
        help='Where the company is. An announcement can be sent to every '
             'company in the same country.')

    # -------------------------------------------------------- who gets it
    audience_kind = fields.Selection(
        AUDIENCE_KINDS, string='Who gets it', default='everyone',
        required=True, tracking=True)
    department_ids = fields.Many2many(
        'hr.department', 'pb_hr_comm_post_department_rel',
        'post_id', 'department_id', string='Parts of the business')
    job_ids = fields.Many2many(
        'hr.job', 'pb_hr_comm_post_job_rel', 'post_id', 'job_id',
        string='Jobs')
    audience_note = fields.Char(
        string='Who that is', compute='_compute_audience_note',
        help='The audience, said in a sentence.')
    recipient_count = fields.Integer(
        string='How many people', readonly=True, copy=False,
        help='How many people have a work email and would get this. Worked '
             'out when somebody presses "Check who gets it", and again the '
             'moment it goes out.')
    recipient_checked_on = fields.Datetime(
        string='Counted on', readonly=True, copy=False)

    # ------------------------------------------------------------- when
    send_at = fields.Datetime(
        string='Goes out', required=True, index=True, tracking=True,
        default=lambda self: fields.Datetime.now() + timedelta(days=3),
        help='The date and time it is sent. Shown in your own time zone.')
    locked_from = fields.Datetime(
        string='Last day to change it', compute='_compute_locked_from',
        help='After this, only the HR lead can change it — and the change is '
             'written into its history.')
    editable_now = fields.Boolean(
        string='Can still be changed', compute='_compute_locked_from')

    recurrence = fields.Selection(
        RECURRENCES, string='How often', default='none', required=True,
        tracking=True)
    recur_until = fields.Date(
        string='Until', help='The last day it may come round. Leave it empty '
                             'and it carries on.')
    parent_id = fields.Many2one(
        'pb.hr.comm.post', string='First one', index=True, ondelete='set null',
        copy=False, help='The announcement this one came round from.')
    child_ids = fields.One2many('pb.hr.comm.post', 'parent_id',
                                string='The ones after it')

    # ------------------------------------------------------------- who owns it
    responsible_user_id = fields.Many2one(
        'res.users', string='Who looks after it', required=True, index=True,
        tracking=True, domain=[('share', '=', False)],
        default=lambda self: self._default_responsible(),
        help='The person reminded two days before, and the one who can '
             'change it until then.')
    responsible_employee_id = fields.Many2one(
        'hr.employee', string='Responsible', compute='_compute_responsible',
        store=True, readonly=True,
        help='The same person as an employee record, so a sign-off route can '
             'say whose announcement it is.')

    # --------------------------------------------------------- how it goes out
    #: EMAIL, AND THE OTHER ONE IS HONEST ABOUT BEING OFF. The owner's ruling
    #: is that outside services stay disconnected for now, so chat is a field
    #: that says "not connected" rather than a promise on a screen. When it is
    #: connected the sender grows one leg and nothing else here changes.
    to_email = fields.Boolean(
        string='By email', default=True, readonly=True,
        help='Everybody with a work email gets it.')
    to_chat = fields.Boolean(
        string='To the chat app', default=False, readonly=True,
        help='Not connected yet. Announcements go out by email.')
    channels = fields.Char(string='How', compute='_compute_channels')

    # --------------------------------------------------------------- state
    state = fields.Selection(
        POST_STATES, string='Status', default='draft', required=True,
        index=True, tracking=True, copy=False)
    sent_at = fields.Datetime(string='Went out', readonly=True, copy=False)
    sent_count = fields.Integer(string='Sent to', readonly=True, copy=False)
    skipped_count = fields.Integer(
        string='Could not be sent to', readonly=True, copy=False,
        help='People the message could not be queued for. The reason is in '
             'the history.')
    no_email_count = fields.Integer(
        string='No work email', readonly=True, copy=False,
        help='People in the audience who have no work email on their record. '
             'They are counted and named in the history, never silently '
             'dropped.')
    nudge_sent_at = fields.Datetime(
        string='Reminder sent', readonly=True, copy=False)
    delivery_ids = fields.One2many(
        'pb.hr.comm.delivery', 'post_id', string='Who got it')

    active = fields.Boolean(default=True)

    # ==================================================================
    #  Defaults and computes
    # ==================================================================
    @api.model
    def _default_responsible(self):
        return self.env['pb.hr.comm.default'].responsible_for(
            self.env.company) or self.env.user

    @api.depends('responsible_user_id')
    def _compute_responsible(self):
        """The employee behind the login.

        NAME THE HOP THE ANSWER IS MADE OF (R138). This depends on the USER
        and is re-read when the user changes; it deliberately does not follow
        somebody's employee record being re-created underneath them, which is
        a data repair rather than a change of responsibility.
        """
        Employee = self.env['hr.employee'].sudo()
        for rec in self:
            user = rec.responsible_user_id
            rec.responsible_employee_id = Employee.search(
                [('user_id', '=', user.id)], limit=1) if user else False

    @api.depends('send_at')
    def _compute_locked_from(self):
        """NOT STORED, on purpose.

        The window is `send_at` minus a switch, and a switch that is changed
        has to apply at once — a stored column would keep yesterday's answer
        until somebody wrote to the record. Nothing searches on it (R10: a
        non-stored compute cannot be used in a search filter), and both the
        guard and the board read it through this compute.
        """
        days = max(number(self.env, P_EDIT_WINDOW, 2), 0)
        now = fields.Datetime.now()
        for rec in self:
            rec.locked_from = (rec.send_at - timedelta(days=days)) \
                if rec.send_at else False
            rec.editable_now = bool(
                rec.state in ('draft', 'submitted', 'scheduled')
                and (not rec.locked_from or now < rec.locked_from))

    @api.depends('audience_kind', 'department_ids', 'job_ids', 'company_id',
                 'country_id')
    def _compute_audience_note(self):
        """The audience in words a person would say out loud."""
        for rec in self:
            rec.audience_note = rec._audience_sentence()

    def _audience_sentence(self):
        self.ensure_one()
        kind = self.audience_kind
        if kind == 'department':
            names = self.department_ids.mapped('name')
            if not names:
                return _('Nobody yet — pick a part of the business.')
            if len(names) <= 3:
                return _('Everybody in %s', ', '.join(names))
            return _('%(first)s and %(rest)s more parts of the business',
                     first=', '.join(names[:3]), rest=len(names) - 3)
        if kind == 'job':
            names = self.job_ids.mapped('name')
            if not names:
                return _('Nobody yet — pick a job.')
            if len(names) <= 3:
                return _('Everybody doing %s', ', '.join(names))
            return _('%(first)s and %(rest)s more jobs',
                     first=', '.join(names[:3]), rest=len(names) - 3)
        if kind == 'country':
            return _('Everybody at every company in %s',
                     self.country_id.name or _('this country'))
        return _('Everybody at %s', self.company_id.name or '')

    @api.depends('to_email', 'to_chat')
    def _compute_channels(self):
        for rec in self:
            rec.channels = _('Email') if rec.to_email else _('Nothing yet')

    @api.depends('subject', 'send_at')
    def _compute_display_name(self):
        """Friendly titles are `_compute_display_name` on Odoo 19, never
        `name_get`."""
        for rec in self:
            when = fields.Datetime.to_string(rec.send_at)[:10] \
                if rec.send_at else ''
            rec.display_name = '%s · %s' % (rec.subject or _('Announcement'),
                                            when) if when \
                else (rec.subject or _('Announcement'))

    # ==================================================================
    #  Integrity
    # ==================================================================
    @api.constrains('audience_kind', 'department_ids', 'job_ids')
    def _check_audience_is_named(self):
        """An audience of nobody is the one mistake that looks like success.

        A post whose audience is "certain parts of the business" and names
        none is perfectly valid to the database, goes out to nobody, and
        reports a cheerful zero.
        """
        for rec in self:
            if rec.audience_kind == 'department' and not rec.department_ids:
                raise ValidationError(_(
                    "Say which parts of the business this is for, or change "
                    "it to everybody."))
            if rec.audience_kind == 'job' and not rec.job_ids:
                raise ValidationError(_(
                    "Say which jobs this is for, or change it to everybody."))

    @api.constrains('recurrence', 'recur_until', 'send_at')
    def _check_recurrence_ends_after_it_starts(self):
        for rec in self:
            if rec.recurrence == 'none' or not rec.recur_until \
                    or not rec.send_at:
                continue
            if rec.recur_until < rec.send_at.date():
                raise ValidationError(_(
                    "It cannot stop coming round before the first one has "
                    "gone out. Pick a later day, or leave it empty."))

    @api.onchange('template_id')
    def _onchange_template(self):
        """A template is COPIED IN and then forgotten (see template.py).

        Only the empty fields are filled, so somebody who has already written
        half an announcement does not lose it by looking at the library.
        """
        for rec in self:
            template = rec.template_id
            if not template:
                continue
            if not rec.subject:
                rec.subject = template.subject or template.name
            if not rec.body_html:
                rec.body_html = template.body_html
            if template.poster_ids and not rec.poster_ids:
                rec.poster_ids = [(6, 0, template.poster_ids.ids)]

    # ==================================================================
    #  Who gets it — the one audience helper
    # ==================================================================
    def expand_audience(self, cap=0, skip_delivered=False):
        """Who this announcement is for, read AS THE SYSTEM.

        Returns ``{'rows': [{'employee_id', 'name', 'email'}], 'total',
        'with_email', 'no_email', 'no_email_names', 'capped', 'company_ids'}``
        — `total` is everybody the audience describes, `with_email` is how
        many of them can actually be reached, and the two are reported
        separately because a person with no work email is a HOLE in the
        delivery rather than a number nobody mentions (the publish-notify
        precedent, `pb_ess_workforce/models/publish_notify.py`).

        READ AS THE SYSTEM (R56/R104). Reading one field of an `hr.employee`
        prefetches forty, about forty of which sit behind payroll groups on
        this build — so a country HR user asking who is in their own audience
        would get an `AccessError` naming fields nobody asked for. The
        security boundary is the record rule that let them open the POST; who
        is in a company is not a secret from the person announcing to them.

        `cap` is a CEILING ON ONE PASS and never a page size: the sender
        passes the burst cap and comes back for the rest ten minutes later,
        and every other caller passes nothing. A cap that is right for a
        screen is a bug in a job (R76).
        """
        self.ensure_one()
        Employee = self.env['hr.employee'].sudo()
        company_ids = self._audience_company_ids()
        domain = [('active', '=', True), ('company_id', 'in', company_ids)]
        if self.audience_kind == 'department':
            domain.append(('department_id', 'in', self.department_ids.ids))
        elif self.audience_kind == 'job':
            domain.append(('job_id', 'in', self.job_ids.ids))
        people = Employee.search(domain, order='id')

        done = set()
        if skip_delivered:
            done = set(self.sudo().delivery_ids.mapped('employee_id').ids)

        rows, no_email = [], []
        for person in people:
            email = (person.work_email or '').strip()
            if not email:
                no_email.append(person.name or str(person.id))
                continue
            if person.id in done:
                continue
            rows.append({'employee_id': person.id,
                         'name': person.name or '',
                         'email': email})
        capped = bool(cap) and len(rows) > int(cap)
        if capped:
            rows = rows[:int(cap)]
        return {
            'rows': rows,
            'total': len(people),
            'with_email': len(people) - len(no_email),
            'no_email': len(no_email),
            'no_email_names': no_email[:20],
            'capped': capped,
            'company_ids': company_ids,
        }

    def _audience_company_ids(self):
        """Which companies the audience is drawn from.

        "Every company in this country" is the one kind that reaches past the
        post's own company, and it reads the COMPANY's country through its
        partner — which is where Odoo 19 keeps it, and it has no column of its
        own on `res.company` (checked, not assumed).
        """
        self.ensure_one()
        company = self.sudo().company_id
        if self.audience_kind != 'country':
            return company.ids
        country = company.partner_id.country_id
        if not country:
            return company.ids
        siblings = self.env['res.company'].sudo().search(
            [('partner_id.country_id', '=', country.id)])
        return siblings.ids or company.ids

    def action_check_audience(self):
        """"Check who gets it" — count, and never send.

        The number is stamped with the moment it was worked out, because an
        audience is a live thing: somebody joins, somebody leaves, and a count
        with no date on it is a number nobody can trust a week later.
        """
        for rec in self:
            found = rec.expand_audience()
            rec.sudo().write({
                'recipient_count': found['with_email'],
                'recipient_checked_on': fields.Datetime.now(),
            })
            rec._hc_note(_(
                "%(who)s would get this: %(n)s with a work email, "
                "%(none)s without one.",
                who=rec.audience_note or '',
                n=found['with_email'], none=found['no_email']))
        return True

    # ==================================================================
    #  The edit window
    # ==================================================================
    def _hc_is_hr_lead(self):
        """The HR lead, for the purposes of a late change.

        TWO PEOPLE ANSWER TO THIS NAME and both are right: whoever holds the
        head-HR group, and whoever holds the company's HR-lead seat in the
        Approval Matrix — which on this database is frequently somebody with
        no HR group at all. Asking only the group would refuse the very person
        the business named (R157 again).
        """
        self.ensure_one()
        if self.env.su or self.env.user._is_admin():
            return True
        if self.env.user.has_group(GROUP_MANAGER):
            return True
        holder = self.env['pb.hr.comm.default']._hr_lead_for(
            self.sudo().company_id)
        return bool(holder and holder.id == self.env.uid)

    def write(self, vals):
        """The window, enforced where it cannot be walked around.

        NOT IN THE FACADE AND NOT IN THE FORM. A rule about who may change
        what has to live on the model, or the native form, a bulk edit and a
        JSON-RPC call are three doors with three different answers.
        """
        guarded = [key for key in vals if key in CONTENT_FIELDS]
        if guarded and not self.env.su:
            now = fields.Datetime.now()
            for rec in self:
                rec._hc_check_window(now, guarded)
        return super().write(vals)

    def _hc_check_window(self, now, changed):
        self.ensure_one()
        if self.state in ('sending', 'sent'):
            raise UserError(_(
                "This went out on %(when)s, so it cannot be changed. Make a "
                "copy of it if you want to say something new.",
                when=company_words(self.env, self.sent_at or self.send_at,
                                   self.sudo().company_id)))
        if self.state == 'cancelled':
            raise UserError(_(
                "This announcement was cancelled. Make a copy of it if you "
                "want to send it after all."))
        locked = self.locked_from
        if not locked or now < locked:
            return True
        if self._hc_is_hr_lead():
            # THE CHANGE IS WRITTEN INTO ITS HISTORY. A window that lets a
            # late change through quietly is not a window — the point is that
            # anybody reading the announcement afterwards can see it happened
            # and who did it.
            self._hc_note(_(
                "Changed inside the last %(days)s days before it goes out, by "
                "%(who)s: %(what)s.",
                days=max(number(self.env, P_EDIT_WINDOW, 2), 0),
                who=self.env.user.name or '',
                what=', '.join(self._hc_field_words(changed))))
            return True
        raise UserError(_(
            "This goes out on %(when)s and the last moment to change it was "
            "%(locked)s. The HR lead can still change it — ask them.",
            when=company_words(self.env, self.send_at,
                               self.sudo().company_id),
            locked=company_words(self.env, locked, self.sudo().company_id)))

    def _hc_field_words(self, names):
        """Field names as a person would say them, for the history line."""
        words = []
        for name in names:
            field = self._fields.get(name)
            words.append(field.string if field and field.string else name)
        return words

    def _hc_note(self, body):
        """A line in the announcement's own history. Never fatal.

        `message_post` ESCAPES A PLAIN STRING BODY (R144), so anything with
        markup in it has to be built with `Markup` — these are plain
        sentences, which is why they are passed as they are.
        """
        self.ensure_one()
        try:
            self.sudo().message_post(body=body)
        except Exception:               # noqa: BLE001 — a note is a courtesy
            _logger.warning('pb_hr_comm: a history line could not be written '
                            'on post %s', self.id, exc_info=True)
        return True

    # ==================================================================
    #  The doors
    # ==================================================================
    def _hc_move(self, state, note=''):
        """A status change this module made on its own, off the route.

        `_chain_state_write` is the mixin's one sanctioned door — the status
        of a chain consumer cannot be written any other way, deliberately, or
        anybody with write access could skip every rung. The after-hook is
        called here because THE CONSEQUENCE HANGS OFF THE STATUS AND NEVER OFF
        THE DOOR (R204): a post reaches `scheduled` through a published route
        on one database and through this method on another, and both have to
        do the same thing.
        """
        self.ensure_one()
        frm = self.state
        if frm == state:
            return True
        self._before_approval_transition(state)
        self._chain_state_write(state)
        self._after_approval_transition(state)
        try:
            self._log_transition(frm, state, note or False)
        except Exception:               # noqa: BLE001 — a trail is not a move
            _logger.warning('pb_hr_comm: post %s could not log %s to %s',
                            self.id, frm, state, exc_info=True)
        return True

    def action_schedule(self):
        """"Schedule it" — the one door, whichever way the switch is set.

        WHEN SIGN-OFF IS OFF THE ROUTE IS NEVER ENTERED and the post says so
        in its own history, with the name of the switch. A thing that is off
        and does not say so is reported as broken (R54).
        """
        for rec in self:
            rec._hc_ready_to_schedule()
            if rec.state == 'scheduled':
                continue
            if flag(rec.env, P_SIGNOFF) and rec._engine_managed():
                rec.action_approval_submit()
                continue
            rec._hc_move('scheduled', _("Scheduled"))
            rec._hc_note(_(
                "Scheduled without sign-off — sign-off is switched off "
                "(pb_hr_comm.signoff). It goes out on %(when)s.",
                when=company_words(rec.env, rec.send_at,
                                   rec.sudo().company_id)))
        return True

    def _hc_ready_to_schedule(self):
        """Everything that has to be true before a date is promised."""
        self.ensure_one()
        if self.state in ('sending', 'sent'):
            raise UserError(_("This has already gone out."))
        if self.state == 'cancelled':
            raise UserError(_(
                "This announcement was cancelled. Make a copy of it to send "
                "it after all."))
        if not (self.body_html or '').strip():
            raise UserError(_("Write what it says first."))
        if not self.send_at:
            raise UserError(_("Say when it should go out."))
        if self.send_at <= fields.Datetime.now():
            raise UserError(_(
                "That time has already passed. Pick when it should go out."))
        found = self.expand_audience()
        if not found['with_email']:
            raise UserError(_(
                "Nobody in this audience has a work email, so there is "
                "nobody to send it to. Check who it is for."))
        self.sudo().write({
            'recipient_count': found['with_email'],
            'recipient_checked_on': fields.Datetime.now(),
        })
        return True

    def action_back_to_draft(self):
        for rec in self:
            if rec.state in ('sending', 'sent'):
                raise UserError(_("This has already gone out."))
            rec._hc_move('draft', _("Taken off the calendar"))
        return True

    def action_cancel(self, reason=False):
        """Stop it. An open sign-off request is withdrawn with it.

        That last part is the shim's own `write` override doing its job: a
        status written outside the engine closes the request, so nobody is
        left with an announcement in their inbox that is never going out.
        """
        for rec in self:
            if rec.state == 'sent':
                raise UserError(_(
                    "This has already gone out, so it cannot be cancelled."))
            rec._hc_move('cancelled', reason or _("Cancelled"))
            if reason:
                rec._hc_note(_("Cancelled: %s", reason))
        return True

    def action_copy_it(self):
        """"Say something new" — the way out of a post that has gone out.

        A COPY AND NEVER AN EDIT. The announcement that went out is what four
        thousand people read, and it stays exactly as they read it.
        """
        self.ensure_one()
        copied = self.copy({
            'subject': _('%s (copy)', self.subject or ''),
            'state': 'draft',
            'send_at': fields.Datetime.now() + timedelta(days=3),
            'parent_id': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('New announcement'),
            'res_model': 'pb.hr.comm.post',
            'res_id': copied.id,
            'view_mode': 'form',
            'views': [[False, 'form']],          # R125
            'target': 'current',
        }

    def copy_data(self, default=None):
        """A copy starts clean: no counts, no stamps, nobody delivered to."""
        default = dict(default or {})
        default.setdefault('state', 'draft')
        default.setdefault('sent_at', False)
        default.setdefault('sent_count', 0)
        default.setdefault('skipped_count', 0)
        default.setdefault('no_email_count', 0)
        default.setdefault('nudge_sent_at', False)
        default.setdefault('recipient_checked_on', False)
        return super().copy_data(default)

    # ==================================================================
    #  What the route does to it
    # ==================================================================
    def _after_approval_transition(self, to_state):
        """THE CONSEQUENCE HANGS OFF THE STATUS (R204).

        Both paths reach here — the published route and this module's own
        `_hc_move` — so anything that must happen when a post is scheduled,
        cancelled or turned down is written once, here, and cannot depend on
        whether a company switched sign-off on.
        """
        result = super()._after_approval_transition(to_state)
        for rec in self:
            if to_state == 'scheduled':
                # A fresh count on the way out of the door, because an
                # audience agreed a week ago is not the audience today.
                found = rec.expand_audience()
                rec.sudo().write({
                    'recipient_count': found['with_email'],
                    'recipient_checked_on': fields.Datetime.now(),
                })
            if to_state == 'cancelled':
                rec.sudo().activity_unlink(['mail.mail_activity_data_todo'])
        return result

    # ==================================================================
    #  Reading it
    # ==================================================================
    def state_word(self):
        self.ensure_one()
        return POST_STATE_LABEL.get(self.state, self.state)

    def audience_word(self):
        self.ensure_one()
        return AUDIENCE_LABEL.get(self.audience_kind, self.audience_kind)

    def counted_people(self, count):
        return counted(count, _('person'), _('people'))

    def action_view_deliveries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Who got it'),
            'res_model': 'pb.hr.comm.delivery',
            'view_mode': 'list',
            'views': [[False, 'list']],          # R125
            'domain': [('post_id', '=', self.id)],
            'target': 'current',
        }

    # ------------------------------------------------------------- guards
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('responsible_user_id'):
                company = self.env['res.company'].browse(
                    vals.get('company_id') or self.env.company.id)
                holder = self.env['pb.hr.comm.default'].responsible_for(
                    company)
                vals['responsible_user_id'] = (holder or self.env.user).id
        return super().create(vals_list)

    def unlink(self):
        """An announcement that has gone out is a record of what was said.

        Deleting one is how a company loses the only copy of a notice
        somebody is arguing about six months later. Cancel, or archive.
        """
        for rec in self:
            if rec.state in ('sending', 'sent') and not self.env.su:
                raise UserError(_(
                    "This has already gone out, so it cannot be deleted — it "
                    "is the record of what was said. Archive it instead."))
        return super().unlink()

    # A COUNTRY HR USER MAY NOT REACH PAST THEIR OWN COMPANIES and the record
    # rules say so; this is the second half of the same sentence, for the one
    # thing a rule cannot express — that the writer has any business here at
    # all. Kept deliberately small: everything else is a rule.
    @api.model
    def _hc_require_writer(self):
        if self.env.su or self.env.user._is_admin():
            return True
        if self.env.user.has_group(GROUP_USER) \
                or self.env.user.has_group(GROUP_MANAGER):
            return True
        raise AccessError(_(
            "Announcements are written by the HR team. Ask them to put one "
            "on the calendar."))
