# -*- coding: utf-8 -*-
"""A resignation, from the moment somebody types it to the moment HR accepts it.

THE LADDER

    draft → submitted (manager) → manager_ok (HR) → approved

and two ways out that are not the bottom of it: `refused`, which is HR or the
manager saying no, and `withdrawn`, which is the person taking it back. The
withdrawal window closes at APPROVAL and not one step later — by then the
departure date is on the record, the leaving checklist is running and other
people have started work off the back of it, so taking it back is a
conversation rather than a button (and the button says so).

WHAT APPROVAL ACTUALLY DOES, in this order:

  1. writes the last working day and the reason onto the employee record —
     never over a DIFFERENT date somebody already put there, which is P1's rule
     and is the same rule for the same reason: HR's own answer outranks
     everybody's;
  2. ATTACHES to the leaving checklist that is already running when there is
     one, and opens a new one only when there is not. The connected system
     opens a case the moment it hears "Resigned", so on a Zoho-driven exit the
     case exists before the resignation is approved and duplicating it would
     give one person two exits (R30);
  3. makes sure the four clearances and the exit feedback request exist;
  4. tells the person it is approved;
  5. calls `_on_resignation_approved(case)` — the extension point P6 overrides
     so a performance process that ends in a departure closes itself. LAST, so
     the override sees a finished world, and inside a try/except, so an
     override that fails cannot undo an approval.

Every one of 1-4 is idempotent, because `_after_approval_transition` is not the
only door: a resignation approved by hand and a resignation approved through
the stepper both land here, and a re-run must not double anything.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .offboarding_common import (
    GROUP_MANAGER, P_EXIT_FEEDBACK_DAYS, P_RESIGN_MAIL, RESIGNATION_SOURCES,
    RESIGNATION_STATES, RESIGNATION_WITHDRAWABLE, first_name, flag, number,
)

_logger = logging.getLogger(__name__)


class PbResignation(models.Model):
    _name = 'pb.resignation'
    _description = 'Resignation'
    # `mail.activity.mixin` as well as `mail.thread` — R3: `activity_schedule`
    # lives on the ACTIVITY mixin, and a resignation books a to-do for HR.
    _inherit = ['mail.thread', 'mail.activity.mixin', 'biz.approval.chain.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'), index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        tracking=True, ondelete='cascade',
        default=lambda self: self.env.user.employee_id)
    manager_id = fields.Many2one(
        'hr.employee', string='Manager', related='employee_id.parent_id',
        store=True, readonly=True)
    department_id = fields.Many2one(
        'hr.department', string='Team',
        related='employee_id.department_id', store=True, readonly=True)

    submit_date = fields.Date(string='Handed in on', readonly=True,
                              tracking=True)
    reason_text = fields.Text(
        string='Reason',
        help='In the words of the person leaving. Nobody but HR and their '
             'manager sees this.')
    notice_days = fields.Integer(
        string='Notice (days)', readonly=True,
        help='What the policy for their country says. HR can set a different '
             'last working day when they approve.')
    requested_lwd = fields.Date(
        string='Last working day asked for', tracking=True,
        help='Filled in from the notice policy when the form opens.')
    approved_lwd = fields.Date(
        string='Agreed last working day', tracking=True,
        help='What HR agreed. This is the date that goes on the employee '
             'record and the date the leaving checklist counts from.')
    departure_reason_id = fields.Many2one(
        'hr.departure.reason', string='Reason on the record',
        default=lambda self: self.env.ref('hr.departure_resigned',
                                          raise_if_not_found=False))

    # HR-ONLY, and safely so: the group named here belongs to `pb_lifecycle`,
    # which is loaded and installed before this module ever exists. R13's trap
    # is a field guarded by a group from its OWN module — resolved at registry
    # load, before that module's security data has been written.
    regrettable = fields.Boolean(
        string='Sorry to lose them', tracking=True,
        groups='pb_lifecycle.group_lifecycle_manager',
        help='HR only. Used to tell the leavers worth understanding from the '
             'ones that were expected.')
    hr_note = fields.Text(
        string='HR note', groups='pb_lifecycle.group_lifecycle_manager')

    state = fields.Selection(
        RESIGNATION_STATES, string='Status', default='draft', required=True,
        index=True, tracking=True, copy=False)
    source = fields.Selection(
        RESIGNATION_SOURCES, string='Filed from', default='manual',
        required=True)
    case_id = fields.Many2one(
        'pb.journey.case', string='Leaving checklist', readonly=True,
        index=True, ondelete='set null', copy=False)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)

    # widget payload for the embedded ApprovalStepper (biz_approval_stepper)
    approval_widget_json = fields.Char(
        compute='_compute_approval_widget', string='Approval trail')

    # Cosmetic per-user button gates. The server decides in `_approval_can`;
    # these only decide whether a control is OFFERED, because an offer the
    # server would refuse is worse than no offer.
    can_submit = fields.Boolean(compute='_compute_can')
    can_manager_approve = fields.Boolean(compute='_compute_can')
    can_hr_approve = fields.Boolean(compute='_compute_can')
    can_refuse = fields.Boolean(compute='_compute_can')
    can_withdraw = fields.Boolean(compute='_compute_can')

    _approval_transitions = {
        # Open by default and narrowed in `_approval_can` below: the person who
        # may submit is the employee THEMSELF, which is not a group and cannot
        # be expressed as one.
        ('draft', 'submitted'): None,
        ('submitted', 'manager_ok'): None,
        ('manager_ok', 'approved'): GROUP_MANAGER,
    }
    #: `withdrawn` is terminal in exactly the way `refused` is: nothing advances
    #: out of it, and the mixin must never offer it as a forward target.
    _approval_dead_states = ('refused', 'withdrawn')

    # ------------------------------------------------------------- housekeeping
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _(
                '%(ref)s — %(who)s', ref=rec.name or _('Resignation'),
                who=rec.employee_id.name or '')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'pb.resignation') or _('Resignation')
            if vals.get('employee_id') and not vals.get('company_id'):
                emp = self.env['hr.employee'].sudo().browse(
                    vals['employee_id'])
                if emp.exists() and emp.company_id:
                    vals['company_id'] = emp.company_id.id
        return super().create(vals_list)

    # ------------------------------------------------------------- the notice
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """Fill in the expected last working day before anybody types a date.

        The whole point of the notice policy: the person leaving should not
        have to know it, and HR should not have to correct it.
        """
        if not self.employee_id:
            return
        days = self.env['pb.notice.policy'].days_for(self.employee_id)
        self.notice_days = days
        if not self.requested_lwd:
            self.requested_lwd = fields.Date.context_today(self) + timedelta(
                days=days)
        if self.employee_id.company_id:
            self.company_id = self.employee_id.company_id

    @api.model
    def prefill_for(self, employee):
        """The same answer, for a caller that has no form — the portal page.

        Returns `{'days', 'lwd'}`. One implementation, so the date the employee
        page shows and the date a form would have filled in cannot disagree.
        `employee` may be a record or an id — the policy coerces it, because
        over JSON-RPC a recordset argument arrives as a plain integer.
        """
        days = self.env['pb.notice.policy'].days_for(employee)
        return {'days': days,
                'lwd': fields.Date.today() + timedelta(days=days)}

    # ---------------------------------------------------------------- computes
    @api.depends('state')
    def _compute_approval_widget(self):
        steps = [
            {'state': 'draft', 'label': _('Handed in'),
             'group_label': _('The employee')},
            {'state': 'submitted', 'label': _('Manager'),
             'group_label': _('Their manager')},
            {'state': 'manager_ok', 'label': _('HR'),
             'group_label': _('HR')},
            {'state': 'approved', 'label': _('Agreed'),
             'group_label': _('HR')},
        ]
        for rec in self:
            rec.approval_widget_json = (
                rec._approval_widget_payload(steps) if rec.id else False)

    @api.depends('state', 'employee_id')
    def _compute_can(self):
        for rec in self:
            state = rec.state
            rec.can_submit = (state == 'draft'
                              and rec._approval_can('draft', 'submitted'))
            rec.can_manager_approve = (
                state == 'submitted'
                and rec._approval_can('submitted', 'manager_ok'))
            rec.can_hr_approve = (
                state == 'manager_ok'
                and rec._approval_can('manager_ok', 'approved'))
            rec.can_refuse = (state in ('submitted', 'manager_ok')
                              and rec._approval_can_refuse(state))
            rec.can_withdraw = (state in RESIGNATION_WITHDRAWABLE
                                and rec._can_withdraw())

    # ----------------------------------------------------------- who may act
    def _is_hr(self):
        user = self.env.user
        return (self.env.su or user._is_admin()
                or user.has_group(GROUP_MANAGER))

    def _is_owner(self):
        self.ensure_one()
        user_id = self.sudo().employee_id.user_id.id
        return bool(user_id and user_id == self.env.uid)

    def _is_line_manager(self):
        self.ensure_one()
        manager = self.sudo().employee_id.parent_id
        return bool(manager and manager.user_id
                    and manager.user_id.id == self.env.uid)

    def _approval_can(self, from_state, to_state):
        """Who may move this one step forward.

        The two open transitions are narrowed to PEOPLE rather than groups,
        which is the case the mixin's `None` exists for: the employee submits
        their own, and the manager step is the employee's own manager. HR can
        do either — somebody has to be able to move a resignation on when a
        manager is on leave, and a chain that dead-ends is a chain nobody uses.
        """
        self.ensure_one()
        if self.env.su or self.env.user._is_admin():
            return True
        pair = (from_state, to_state)
        if pair == ('draft', 'submitted'):
            return self._is_owner() or self._is_hr()
        if pair == ('submitted', 'manager_ok'):
            return self._is_line_manager() or self._is_hr()
        return super()._approval_can(from_state, to_state)

    def _can_withdraw(self):
        self.ensure_one()
        return self._is_owner() or self._is_hr()

    # ---------------------------------------------------------------- actions
    def action_submit(self):
        for rec in self:
            if not rec.reason_text:
                raise UserError(_(
                    "Write a line about why you are leaving before you hand "
                    "this in — your manager and HR will read it."))
            if not rec.requested_lwd:
                raise UserError(_(
                    "Say which day you would like to be your last."))
            rec._advance_state('submitted')
            rec.write({'submit_date': fields.Date.context_today(rec)})
            rec._notify_filed()
        return True

    def action_manager_approve(self, note=False):
        for rec in self:
            rec._advance_state('manager_ok', note=note)
            rec.message_post(body=_(
                "%(who)s has seen this. It is with HR now.",
                who=self.env.user.name))
        return True

    def action_hr_approve(self, note=False):
        for rec in self:
            if not rec.approved_lwd and not rec.requested_lwd:
                raise UserError(_(
                    "Set the agreed last working day before approving — it is "
                    "the date everything else counts from."))
            if not rec.approved_lwd:
                rec.approved_lwd = rec.requested_lwd
            rec._advance_state('approved', note=note)
        return True

    def action_refuse(self, note=False):
        """Not accepted. The employee is told, and the record says who and why."""
        self.action_refuse_chain(note=note)
        for rec in self:
            rec._notify_employee(
                'pb_offboarding.mail_template_resignation_refused')
        return True

    def action_withdraw(self, note=False):
        """Taken back by the person who filed it. Only before HR agrees."""
        for rec in self:
            if not rec._can_withdraw():
                raise AccessError(_(
                    "Only %(who)s or the HR team can take this resignation "
                    "back.", who=rec.employee_id.name or _('the employee')))
            if rec.state == 'approved':
                raise UserError(_(
                    "This resignation has already been agreed, so it cannot "
                    "be taken back here. The last working day is on "
                    "%(who)s's record and the leaving checklist is running — "
                    "talk to HR and they will cancel both.",
                    who=rec.employee_id.name or _('the employee')))
            if rec.state not in RESIGNATION_WITHDRAWABLE:
                raise UserError(_(
                    "This resignation is already closed, so there is nothing "
                    "to take back."))
            frm = rec.state
            rec._chain_state_write('withdrawn')
            rec._log_transition(frm, 'withdrawn', note)
            rec.message_post(body=_(
                "Taken back by %(who)s.", who=self.env.user.name))
            rec._notify_withdrawn()
        return True

    # ------------------------------------------------------- what approval does
    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state != 'approved':
            return res
        self.ensure_one()
        for name, fn in (
                ('record', self._stamp_employee_record),
                ('case', self._ensure_case),
                ('extras', self._ensure_case_extras),
                ('notify', self._notify_approved)):
            try:
                fn()
            except Exception:           # noqa: BLE001 — one piece, one grave
                _logger.exception(
                    'pb_offboarding: %s failed after approving resignation %s',
                    name, self.id)
        # LAST, and swallowed: an override that fails must not undo an
        # approval that has already been written.
        try:
            self._on_resignation_approved(self.case_id)
        except Exception:               # noqa: BLE001
            _logger.exception(
                'pb_offboarding: _on_resignation_approved failed for %s',
                self.id)
        return res

    # ------------------------------------------------------------ the pieces
    def _stamp_employee_record(self):
        """The last working day and the reason, onto the employee record.

        NEVER over a DIFFERENT date. A departure date already on the record was
        put there by somebody who knew something — the connected system, or an
        HR person who agreed a different day in a meeting — and silently
        overwriting it is how two systems end up disagreeing about when
        somebody left. A clash is POSTED, and the record is left alone.
        """
        self.ensure_one()
        emp = self.employee_id
        lwd = self.approved_lwd or self.requested_lwd
        if not emp or not lwd:
            return False
        vals = {}
        current = emp.departure_date
        if not current:
            vals['departure_date'] = lwd
        elif current != lwd:
            self.message_post(body=_(
                "%(who)s already has %(existing)s as their last day, and this "
                "resignation agreed %(agreed)s. The record was left alone — "
                "change it by hand if %(agreed)s is right.",
                who=emp.name or '', existing=current, agreed=lwd))
            self.activity_schedule(
                act_type_xmlid='mail.mail_activity_data_todo',
                summary=_('Two different last working days'),
                note=_("%(who)s's record says %(existing)s; this resignation "
                       "agreed %(agreed)s. Decide which is right.",
                       who=emp.name or '', existing=current, agreed=lwd),
                user_id=self.env.uid)
        if self.departure_reason_id and not emp.departure_reason_id:
            vals['departure_reason_id'] = self.departure_reason_id.id
        if not emp.departure_description and self.reason_text:
            vals['departure_description'] = self.reason_text[:500]
        if vals:
            # Through the ORM, always. On this build the employment fields live
            # on a version record and are non-stored relateds, so raw SQL both
            # fails on some columns and lies about others (R14).
            emp.sudo().write(vals)
        return True

    def _ensure_case(self):
        """Attach to the leaving checklist, or open one. Never both (R30).

        `pb.zoho.pipeline._open_case()` already runs this test on its own side,
        and this is deliberately the same test rather than a smarter one: a
        checklist that is draft, running or on hold is THE checklist for this
        exit, whoever started it and for whatever reason.
        """
        self.ensure_one()
        emp = self.employee_id
        if not emp:
            return False
        Case = self.env['pb.journey.case'].sudo()
        if self.case_id and self.case_id.state in ('draft', 'active',
                                                   'on_hold'):
            case = self.case_id
        else:
            case = Case.search([
                ('employee_id', '=', emp.id),
                ('case_type', '=', 'offboarding'),
                ('state', 'in', ('draft', 'active', 'on_hold')),
            ], limit=1)
        lwd = self.approved_lwd or self.requested_lwd
        if case:
            self.sudo().case_id = case.id
            if lwd and case.anchor_date != lwd:
                # The anchor is corrected; the STEPS keep the dates they were
                # given. P0's whole doctrine is that a task is the case's own
                # copy — re-dating work somebody has already planned around is
                # exactly what that rule exists to prevent — so the case says
                # so out loud instead of quietly moving nine dates.
                had = case.anchor_date
                case.write({'anchor_date': lwd})
                case.message_post(body=_(
                    "The agreed last working day is %(new)s%(was)s. The steps "
                    "keep the dates they were given — move any that matter by "
                    "hand.", new=lwd,
                    was=(_(' (it was %s)', had) if had else '')))
            case.append_asset_exit_tasks()
            self.message_post(body=_(
                "Added to the leaving checklist that was already running."))
            return case
        template = self.env['pb.journey.template'].sudo().pick_for(
            'offboarding',
            country_id=Case._employee_country(emp),
            company_id=(self.company_id or self.env.company).id)
        case = Case.create({
            'employee_id': emp.id,
            'case_type': 'offboarding',
            'template_id': template.id if template else False,
            'anchor_date': lwd or fields.Date.today(),
            'source': 'portal' if self.source == 'portal' else (
                'zoho' if self.source == 'zoho' else 'manual'),
            'company_id': (self.company_id or self.env.company).id,
        })
        case.action_open()
        self.sudo().case_id = case.id
        self.message_post(body=_(
            "The leaving checklist is open — %(count)s step(s).",
            count=len(case.task_ids)))
        return case

    def _ensure_case_extras(self):
        """The four clearances and the exit conversation. Both idempotent."""
        self.ensure_one()
        if not self.case_id:
            return False
        return self.case_id.setup_offboarding()

    # ------------------------------------------------------------ the emails
    def _mail(self, xmlid, to):
        """Queue one message. Never raises; never counts a dead letter.

        `email_to` is passed EXPLICITLY (R6): a template's own rendered address
        can reach `mail.mail` empty and the message is then created, queued and
        addressed to nobody with no error anywhere.
        """
        self.ensure_one()
        if not flag(self.env, P_RESIGN_MAIL):
            _logger.info('pb_offboarding: resignation emails are switched off')
            return False
        addresses = [a.strip() for a in (to or []) if a and a.strip()]
        seen, clean = set(), []
        for address in addresses:
            if address.lower() not in seen:
                seen.add(address.lower())
                clean.append(address)
        if not clean:
            _logger.info('pb_offboarding: resignation %s — nobody to write to',
                         self.id)
            return False
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_offboarding: %s is missing', xmlid)
            return False
        try:
            template.sudo().send_mail(
                self.id, force_send=False,
                email_values={'email_to': ','.join(clean),
                              'auto_delete': False})
            return True
        except Exception:               # noqa: BLE001
            _logger.exception('pb_offboarding: could not queue %s for %s',
                              xmlid, self.id)
            return False

    def _hr_addresses(self):
        self.ensure_one()
        case = self.env['pb.journey.case']
        try:
            people = case._users_in_group(
                GROUP_MANAGER, self.company_id or self.env.company, limit=0)
        except Exception:               # noqa: BLE001
            people = self.env['res.users'].browse()
        return [u.email for u in people if u.email]

    def _manager_address(self):
        self.ensure_one()
        manager = self.employee_id.parent_id
        if manager and manager.work_email:
            return [manager.work_email]
        if manager and manager.user_id and manager.user_id.email:
            return [manager.user_id.email]
        return []

    def _employee_address(self):
        self.ensure_one()
        emp = self.employee_id
        return [a for a in (emp.work_email, emp.private_email) if a][:1]

    def _notify_filed(self):
        self.ensure_one()
        self._mail('pb_offboarding.mail_template_resignation_filed',
                   self._manager_address() + self._hr_addresses())
        return True

    def _notify_withdrawn(self):
        self.ensure_one()
        self._mail('pb_offboarding.mail_template_resignation_withdrawn',
                   self._manager_address() + self._hr_addresses())
        return True

    def _notify_approved(self):
        self.ensure_one()
        self._mail('pb_offboarding.mail_template_resignation_approved',
                   self._employee_address())
        return True

    def _notify_employee(self, xmlid):
        self.ensure_one()
        return self._mail(xmlid, self._employee_address())

    # ------------------------------------------------------- extension point
    def _on_resignation_approved(self, case):
        """Called ONCE, last, after a resignation has been fully approved.

        Deliberately empty and deliberately last: everything else has already
        happened, so an override sees a finished world — the departure date is
        on the record, `self.case_id` is the leaving checklist, its clearances
        exist and the person has been told.

        `case` is the `pb.journey.case` (possibly an empty recordset, if the
        checklist could not be opened). `self` is a single resignation.

        P6 overrides this so a performance process that ends in a departure
        closes itself. **Overrides must never raise** — this runs inside the
        approval transaction and the caller swallows the exception, so a
        failure here is a log line rather than a resignation that half
        happened.
        """
        return True

    # ------------------------------------------------------------- convenience
    def action_open_case(self):
        self.ensure_one()
        if not self.case_id:
            raise UserError(_(
                "There is no leaving checklist for this resignation yet — one "
                "is opened when HR approves it."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pb.journey.case',
            'res_id': self.case_id.id,
            'view_mode': 'form',
        }

    # ------------------------------------------------------------- the reader
    @api.model
    def for_employee(self, employee):
        """The resignation this person's own page should show.

        The live one if there is one; otherwise the most recent, so the page
        can say "you took this back on the 4th" rather than pretending nothing
        ever happened. A record or an id — see `prefill_for`.
        """
        employee = self.env['pb.notice.policy']._as_employee(employee)
        if not employee:
            return self.browse()
        live = self.sudo().search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ('draft', 'submitted', 'manager_ok', 'approved')),
        ], order='create_date desc', limit=1)
        return live or self.sudo().search(
            [('employee_id', '=', employee.id)],
            order='create_date desc', limit=1)

    @api.model
    def feedback_window_days(self):
        return max(1, number(self.env, P_EXIT_FEEDBACK_DAYS, 21))

    def greeting(self):
        """"Tâm" — the given name, wherever it sits in the full one."""
        self.ensure_one()
        return first_name(self.employee_id.name)
