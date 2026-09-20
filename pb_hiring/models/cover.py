# -*- coding: utf-8 -*-
"""`pb.hiring.cover` — somebody standing in for a recruiter for a fortnight.

WHY THIS IS NOT A DELEGATION. `pb.access.delegation` (P11) lends a person's
PERMISSIONS: it snapshots the groups they hold, grants them to somebody else
for a window and measures them back afterwards. That is the right machine for
"the equipment manager is away and somebody has to approve laptop requests",
and it is far too heavy for this. A recruiter's cover changes nothing about
what anybody is allowed to do in general — it says that, for two weeks, one
named person may publish adverts and screen candidates ON THIS RECRUITER'S
ROLES. Nothing is granted, nothing has to be taken back, and the day the
window closes there is nothing left over to go wrong.

SO THE COVER IS A FACT THE FACADE READS, and that is the whole design. The
gates already ask "may this person recruit"; they now also ask "is this person
covering somebody whose role this is". A cover that has ended answers no by
itself, because the answer is computed from the dates rather than from a group
somebody has to remember to remove.

IT IS STILL AGREED. Handing your candidates to a colleague is a real decision
and it goes through the matrix like everything else — one rung, the recruiter's
own manager, resolved from the hiring rule for their country and falling back
to the org chart. Whichever it was is said out loud on the request.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .hiring_common import COVER_STATES, GROUP_MANAGER, as_id, counted

_logger = logging.getLogger(__name__)


class PbHiringCover(models.Model):
    _name = 'pb.hiring.cover'
    _description = 'Recruiter cover'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'biz.approval.chain.mixin']
    _order = 'date_from desc, id desc'

    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('submitted', 'approved'): None,
        ('submitted', 'refused'): None,
        ('draft', 'refused'): None,
    }

    name = fields.Char(string='Reference', compute='_compute_name',
                       store=True, readonly=True)
    recruiter_id = fields.Many2one(
        'res.users', string='Who is away', required=True, index=True,
        domain="[('share', '=', False)]",
        default=lambda self: self.env.user)
    cover_user_id = fields.Many2one(
        'res.users', string='Who is standing in', required=True, index=True,
        domain="[('share', '=', False)]")
    date_from = fields.Date(string='From', required=True,
                            default=fields.Date.context_today)
    date_to = fields.Date(string='Until', required=True)
    reason = fields.Text(string='Why', required=True)
    state = fields.Selection(COVER_STATES, string='How far it has got',
                             default='draft', required=True, index=True,
                             tracking=True, copy=False)
    started_on = fields.Datetime(string='Started', readonly=True, copy=False)
    ended_on = fields.Datetime(string='Ended', readonly=True, copy=False)
    refuse_note = fields.Text(string='Why it was turned down', copy=False)
    #: WHICH ANSWER WE USED, said out loud. "Your manager approved this" means
    #: nothing if nobody can tell whether "your manager" came from the hiring
    #: rule for Vietnam or from the org chart.
    approver_source = fields.Selection(
        [('rule', 'From the hiring rule'),
         ('chart', 'From the org chart'),
         ('none', 'Nobody could be found')],
        string='Who was asked', compute='_compute_approver', store=True,
        readonly=True)
    approver_user_id = fields.Many2one(
        'res.users', string='Asked to agree it', compute='_compute_approver',
        store=True, readonly=True)
    requisition_count = fields.Integer(string='Roles covered',
                                       compute='_compute_requisitions')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)

    # =====================================================================
    #  Names and computes
    # =====================================================================
    @api.depends('recruiter_id', 'cover_user_id', 'date_from', 'date_to')
    def _compute_name(self):
        for rec in self:
            rec.name = _('%(who)s covering %(for_whom)s',
                         who=rec.cover_user_id.name or _('somebody'),
                         for_whom=rec.recruiter_id.name or _('a recruiter'))

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Cover')

    @api.depends('recruiter_id', 'company_id')
    def _compute_approver(self):
        for rec in self:
            user, source = rec._resolve_approver()
            rec.approver_user_id = user
            rec.approver_source = source

    def _resolve_approver(self):
        """`(user, where it came from)`.

        The hiring rule first, because that is the table a business filled in
        on purpose to say who runs recruiting where. The org chart second,
        because it is always there. Nobody third — and the request says so
        rather than quietly asking the person who raised it.
        """
        self.ensure_one()
        Users = self.env['res.users']
        recruiter = self.recruiter_id
        if not recruiter:
            return Users.browse(), 'none'
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', recruiter.id)], limit=1)
        rule = self.env['pb.hiring.country.rule'].sudo().rule_for(
            self.company_id,
            (employee.country_id if employee else False)
            or self.company_id.country_id)
        if rule and rule.recruiter_manager_id \
                and rule.recruiter_manager_id.id != recruiter.id:
            return rule.recruiter_manager_id, 'rule'
        boss = employee.sudo().parent_id.user_id if employee else False
        if boss and boss.id != recruiter.id:
            return boss, 'chart'
        return Users.browse(), 'none'

    def _compute_requisitions(self):
        for rec in self:
            rec.requisition_count = self.env[
                'pb.hiring.requisition'].sudo().search_count([
                    ('recruiter_id', '=', rec.recruiter_id.id),
                    ('state', 'in', ('open', 'hr_ok')),
                ]) if rec.recruiter_id else 0

    @api.constrains('date_from', 'date_to', 'recruiter_id', 'cover_user_id')
    def _check_window(self):
        for rec in self:
            if rec.date_to and rec.date_from and rec.date_to < rec.date_from:
                raise ValidationError(_(
                    "The cover cannot end before it starts."))
            if rec.cover_user_id and rec.recruiter_id \
                    and rec.cover_user_id.id == rec.recruiter_id.id:
                raise ValidationError(_(
                    "Somebody cannot cover for themselves. Pick the colleague "
                    "who is picking the work up."))

    # =====================================================================
    #  The buttons
    # =====================================================================
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("This one has already been sent in."))
            if not (rec.reason or '').strip():
                raise UserError(_(
                    "Say why. A cover request with no reason is one nobody "
                    "can agree to in good conscience."))
            if rec.approver_source == 'none':
                raise UserError(_(
                    "Payobook cannot work out who should agree this. Add a "
                    "hiring rule for this company naming the recruiter's "
                    "manager, or ask the HR team to set your manager on your "
                    "employee record."))
            rec._advance_state('submitted')
            rec.sudo().message_post(body=_(
                "Sent to %(who)s to agree. %(source)s",
                who=rec.approver_user_id.name or '',
                source=dict(rec._fields['approver_source'].selection).get(
                    rec.approver_source, '')))
        return True

    def action_approve(self, note=False):
        for rec in self:
            rec._advance_state('approved', note=note or False)
        return True

    def action_refuse(self, note=False):
        for rec in self:
            rec.refuse_note = note or rec.refuse_note
        return self.action_refuse_chain(note=note or False)

    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state == 'approved':
            # A cover agreed on the morning it starts should start, not wait
            # for a job to run at midnight.
            if self.date_from and self.date_from <= self._window_today():
                self.action_start()
        return res

    def action_start(self):
        """The cover begins. Every role it touches says so in its own
        chatter, because a recruiter coming back should be able to see what
        happened on their roles and who did it."""
        for rec in self:
            if rec.state not in ('approved', 'active'):
                raise UserError(_(
                    "Only a cover that has been agreed can start."))
            if rec.state == 'active':
                continue
            rec.sudo().write({'state': 'active',
                              'started_on': fields.Datetime.now()})
            rec._note_on_roles(_(
                "%(who)s is covering for %(for_whom)s until %(when)s.",
                who=rec.cover_user_id.name or '',
                for_whom=rec.recruiter_id.name or '', when=rec.date_to or ''))
            rec.sudo().message_post(body=_("Cover has started."))
        return True

    def action_end(self, note=None):
        for rec in self:
            if rec.state not in ('active', 'approved'):
                raise UserError(_("This cover is not running."))
            rec.sudo().write({'state': 'ended',
                              'ended_on': fields.Datetime.now()})
            rec._note_on_roles(_(
                "%(who)s is no longer covering for %(for_whom)s.",
                who=rec.cover_user_id.name or '',
                for_whom=rec.recruiter_id.name or ''))
            rec.sudo().message_post(body=_("Cover has finished. %s",
                                           (note or '').strip()))
        return True

    def _note_on_roles(self, body):
        """One chatter line per role, in its own savepoint via the request's
        own leg helper — a role that cannot take a note must not stop a cover
        starting."""
        self.ensure_one()
        roles = self.env['pb.hiring.requisition'].sudo().search([
            ('recruiter_id', '=', self.recruiter_id.id),
            ('state', 'in', ('open', 'hr_ok', 'manager_ok')),
        ])
        for role in roles:
            role._leg('the cover note on %s' % role.name,
                      lambda r=role: r.message_post(body=body))
        return len(roles)

    def _approval_can(self, from_state, to_state):
        self.ensure_one()
        if self.env.su or self.env.user._is_admin():
            return True
        if to_state == 'submitted':
            return bool(self.recruiter_id.id == self.env.uid) \
                or self.env.user.has_group(GROUP_MANAGER)
        if to_state in ('approved', 'refused') and from_state == 'submitted':
            if self.approver_user_id and \
                    self.approver_user_id.id == self.env.uid:
                return True
            return self.env.user.has_group(GROUP_MANAGER)
        return super()._approval_can(from_state, to_state)

    # =====================================================================
    #  What a cover MEANS — the only question the gates ask
    # =====================================================================
    @api.model
    def _window_today(self):
        """ONE CLOCK FOR EVERYBODY, and it is the server's.

        `fields.Date.context_today` answers in the READER's timezone, and a
        permission that changes with who is asking is not a permission. A
        Vietnamese recruiter writing "from today" stores tomorrow's date by
        the server's reckoning for seven hours of every day; a colleague
        whose account has no timezone set then reads UTC, finds the window
        has not started, and is refused a role they are demonstrably covering
        — with nothing on any screen to explain it. Found by the very first
        test that asked the question as somebody else.

        The server's own date is the only clock both of them share (R36 from
        the permission side rather than the job side). It can make a cover
        live a few hours early or late against a reader's wall clock, which
        is the generous direction: a cover that lasts an extra evening costs
        nothing, and one that ends early costs somebody their afternoon.
        """
        return fields.Date.today()

    @api.model
    def covered_recruiter_uids(self, user=None):
        """Whose roles this person may work on today, as user ids.

        COMPUTED FROM THE DATES, never from a flag: a cover that ended last
        Friday answers "nobody" whether or not any job has run. The nightly
        step tidies the status so a screen reads honestly; this is what the
        permission actually turns on.
        """
        uid = as_id(user) or self.env.uid
        today = self._window_today()
        rows = self.sudo().search([
            ('cover_user_id', '=', uid),
            ('state', 'in', ('approved', 'active')),
            ('date_from', '<=', today),
            ('date_to', '>=', today),
        ])
        return sorted({row.recruiter_id.id for row in rows
                       if row.recruiter_id})

    @api.model
    def active_for_recruiter(self, recruiter):
        """The cover standing in for this recruiter today, if there is one."""
        uid = as_id(recruiter)
        if not uid:
            return self.browse()
        today = self._window_today()
        return self.sudo().search([
            ('recruiter_id', '=', uid),
            ('state', 'in', ('approved', 'active')),
            ('date_from', '<=', today),
            ('date_to', '>=', today),
        ], order='date_to desc', limit=1)

    # =====================================================================
    #  The nightly tidy
    # =====================================================================
    @api.model
    def run_window(self):
        """Start the ones that are due and end the ones that are over.

        Both directions, because a cover that never says "active" is a cover
        nobody can see on a screen, and a cover that never says "ended" is a
        list that grows for ever. Idempotent: it looks at the status it is
        about to write.
        """
        # THE SAME CLOCK THE PERMISSION USES. A job that started covers on
        # one calendar while the gate read another would leave rows saying
        # "Covering now" that grant nothing.
        today = self._window_today()
        started = ended = 0
        for rec in self.sudo().search([('state', '=', 'approved'),
                                       ('date_from', '<=', today),
                                       ('date_to', '>=', today)]):
            try:
                rec.action_start()
                started += 1
            except Exception:           # noqa: BLE001 — per record
                _logger.warning('pb_hiring: cover %s could not be started',
                                rec.id, exc_info=True)
        for rec in self.sudo().search([('state', 'in', ('approved', 'active')),
                                       ('date_to', '<', today)]):
            try:
                rec.action_end()
                ended += 1
            except Exception:           # noqa: BLE001 — per record
                _logger.warning('pb_hiring: cover %s could not be ended',
                                rec.id, exc_info=True)
        return {'started': started, 'ended': ended}

    @api.model
    def describe_window(self, counts):
        started = counts.get('started', 0)
        ended = counts.get('ended', 0)
        parts = []
        if started:
            parts.append(_("%(n)s %(word)s started.", n=started,
                           word=counted(started, _('cover has'),
                                        _('covers have'))))
        if ended:
            parts.append(_("%(n)s %(word)s finished.", n=ended,
                           word=counted(ended, _('cover has'),
                                        _('covers have'))))
        if not parts:
            return _("No cover started or finished today.")
        return ' '.join(parts)
