# -*- coding: utf-8 -*-
"""An extension is asked for, agreed, and then built — in that order.

WHY THIS IS A RECORD AND NOT A BUTTON. "We extended Minh's contract" is a
sentence somebody will need to defend in a year, and the two things that make
it defensible are the REASON and the NAME of the person who agreed. A button
that creates a contract on the spot has neither, and the only trace it leaves
is a contract that appeared.

THE WINDOW IS PART OF THE DESIGN. A manager gets a fixed number of days to
agree — five, by default — because an extension request that sits in an inbox
until the contract runs out is a decision the calendar took. Past the date the
request is escalated to the HR team, ONCE, and the request stays open: the
escalation is a nudge, never an approval.

THE APPROVAL ITSELF IS `biz.approval.chain.mixin`, the codebase's own multi-tier
machine, rather than a `state` field and three buttons. It gives the trail
widget, the state-write guard (a client cannot `write({'state': 'approved'})`
past the chain) and the log rows for free.

RULING D1 LIVES ON THE OTHER SIDE OF THIS. Approving does not touch the running
contract; it calls `pb.contract.review._on_extension_approved`, which builds a
NEW contract starting the day after the old one ends.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .contract_common import (
    GROUP_MANAGER, P_APPROVE_DAYS, P_MAIL, counted, flag, number, term_end,
)

_logger = logging.getLogger(__name__)

STATES = [
    ('draft', 'Being written'),
    ('pending', 'Waiting to be agreed'),
    ('approved', 'Agreed'),
    ('refused', 'Turned down'),
]
STATE_LABEL = dict(STATES)


class PbContractExtension(models.Model):
    _name = 'pb.contract.extension'
    _description = 'Contract Extension Request'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'biz.approval.chain.mixin']
    _order = 'create_date desc, id desc'

    #: (from, to) -> the group that may make the move. `None` means "open by
    #: default", and `_approval_can` below narrows it to the ONE person who
    #: should be agreeing: the employee's own manager. A demo — or a company
    #: whose HR administrator IS the approver — must never dead-end because the
    #: group holder is absent, so the HR tier passes as well.
    _approval_transitions = {
        ('draft', 'pending'): None,
        ('pending', 'approved'): None,
        ('pending', 'refused'): None,
        ('draft', 'refused'): None,
    }
    _approval_dead_states = ('refused',)

    name = fields.Char(compute='_compute_name', store=True, string='Request')
    review_id = fields.Many2one(
        'pb.contract.review', string='Contract decision', required=True,
        index=True, ondelete='cascade')
    contract_id = fields.Many2one(
        'hr.contract', string='Contract', related='review_id.contract_id',
        store=True, readonly=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', related='review_id.employee_id',
        store=True, index=True, readonly=True)
    reason = fields.Text(
        string='Why', required=True,
        help='Why this contract should run for longer. Somebody will read '
             'this before agreeing the next extension.')
    months = fields.Integer(
        string='For how many months', default=12, required=True)
    new_date_start = fields.Date(compute='_compute_new_dates',
                                 string='The new contract starts')
    new_date_end = fields.Date(compute='_compute_new_dates',
                               string='and ends')
    approver_user_id = fields.Many2one(
        'res.users', string='Who agrees it', index=True, ondelete='set null')
    approve_by = fields.Date(
        string='Agree by', index=True,
        help='After this date the request is escalated to the HR team. It '
             'stays open — the escalation is a nudge, never an approval.')
    escalated = fields.Boolean(string='Escalated', readonly=True, copy=False)
    state = fields.Selection(
        STATES, string='Status', default='draft', required=True, index=True,
        tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    # ------------------------------------------------------------- computes
    @api.depends('employee_id', 'months')
    def _compute_name(self):
        for rec in self:
            rec.name = _(
                '%(who)s — %(span)s more',
                who=rec.employee_id.name or _('Employee'),
                span=counted(rec.months or 0, _('month'), _('months')))

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Extension request')

    @api.depends('review_id.end_date', 'months')
    def _compute_new_dates(self):
        for rec in self:
            end = rec.review_id.end_date if rec.review_id else False
            rec.new_date_start = (end + timedelta(days=1)) if end else False
            rec.new_date_end = (term_end(rec.new_date_start,
                                         max(1, rec.months or 1))
                                if rec.new_date_start else False)

    # ----------------------------------------------------------- the chain
    def _approval_can(self, from_state, to_state):
        """The manager named on the request, or the HR team.

        `super()` covers the superuser, an administrator and the transition's
        own group (all `None` here). This adds the SPECIFIC person — safety
        rail 4 of the mixin, and the reason it exists: an approval that only a
        group can give is an approval that stalls the moment nobody in the
        company holds that group.
        """
        self.ensure_one()
        if super()._approval_can(from_state, to_state):
            return True
        user = self.env.user
        if self.approver_user_id and self.approver_user_id.id == user.id:
            return True
        return user.has_group(GROUP_MANAGER)

    def action_submit(self):
        """Put it in front of the manager, with a date on it."""
        self.ensure_one()
        if self.state != 'draft':
            return False
        emp = self.employee_id
        manager = emp.parent_id if emp else False
        approver = False
        if manager and manager.user_id:
            approver = manager.user_id
        elif self.review_id and self.review_id.manager_user_id:
            approver = self.review_id.manager_user_id
        days = max(1, number(self.env, P_APPROVE_DAYS, 5))
        self.sudo().write({
            'approver_user_id': approver.id if approver else False,
            'approve_by': fields.Date.today() + timedelta(days=days),
        })
        self._advance_state('pending')
        self._notify('pb_contract_lifecycle.mail_template_extension_ask',
                     self._approver_addresses())
        self.message_post(body=_(
            "Asked. %(who)s has until %(when)s to agree it.",
            who=(approver.name if approver else _('The HR team')),
            when=self.approve_by))
        try:
            self.activity_schedule(
                act_type_xmlid='mail.mail_activity_data_todo',
                summary=_("Agree the contract extension for %s",
                          emp.name if emp else ''),
                note=_("%(who)s's contract ends on %(when)s. The reason given "
                       "is: %(why)s",
                       who=emp.name if emp else '',
                       when=(self.review_id.end_date
                             if self.review_id else ''),
                       why=self.reason or ''),
                user_id=(approver or self.env.user).id,
                date_deadline=self.approve_by)
        except Exception:               # noqa: BLE001
            _logger.exception('pb_contract_lifecycle: could not raise the '
                              'to-do for extension %s', self.id)
        return True

    def action_approve(self, note=None):
        """Agree it — and the new contract is built on the way out."""
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_(
                "This request is %s, so there is nothing to agree.",
                STATE_LABEL.get(self.state, self.state)))
        self._advance_state('approved', note=note)
        return True

    def action_refuse(self, note=None):
        """Turn it down, and hand the choice back to the decision board."""
        self.ensure_one()
        if self.state not in ('draft', 'pending'):
            raise UserError(_("This request has already been settled."))
        self.action_refuse_chain(note=note)
        return True

    def _after_approval_transition(self, to_state):
        """The consequences, once the state is written and the log is honest."""
        res = super()._after_approval_transition(to_state)
        if to_state == 'approved':
            try:
                self.review_id._on_extension_approved(self)
            except Exception:           # noqa: BLE001
                _logger.exception('pb_contract_lifecycle: the new contract '
                                  'for extension %s could not be built',
                                  self.id)
                self.message_post(body=_(
                    "This was agreed, but the new contract could not be "
                    "prepared. Nothing has been changed on the contract that "
                    "is running. Try again from the decision, or write the "
                    "new contract by hand."))
        elif to_state == 'refused':
            try:
                if self.review_id and self.review_id.state == 'extension':
                    self.review_id.sudo().write({'state': 'decide'})
                    self.review_id.message_post(body=_(
                        "The extension was turned down, so the choice is back "
                        "here: let the contract end, or evaluate for a "
                        "permanent one."))
            except Exception:           # noqa: BLE001
                _logger.exception('pb_contract_lifecycle: could not hand the '
                                  'decision back after refusing %s', self.id)
            self._notify(
                'pb_contract_lifecycle.mail_template_extension_refused',
                self._hr_addresses())
        return res

    # ------------------------------------------------------ the escalation
    @api.model
    def _escalate_overdue(self, today=None):
        """One escalation per request, on the day after the window shut.

        STAMPED, not counted from the date, because a job that decides "is it
        overdue" every night sends the same escalation every night. `escalated`
        is the whole guard, and it is set whether or not the mail went — an
        address that does not exist is not a reason to keep trying for ever.
        """
        today = today or fields.Date.today()
        rows = self.sudo().search([
            ('state', '=', 'pending'),
            ('approve_by', '!=', False),
            ('approve_by', '<', today),
            ('escalated', '=', False),
        ])
        made = 0
        for row in rows:
            try:
                row._notify(
                    'pb_contract_lifecycle.mail_template_extension_overdue',
                    row._hr_addresses() + row._approver_addresses())
                row.write({'escalated': True})
                row.message_post(body=_(
                    "Nobody had agreed this by %(when)s, so the HR team has "
                    "been told. It is still waiting on %(who)s.",
                    when=row.approve_by,
                    who=(row.approver_user_id.name
                         if row.approver_user_id else _('a manager'))))
                made += 1
            except Exception:           # noqa: BLE001
                _logger.exception('pb_contract_lifecycle: could not escalate '
                                  'extension %s', row.id)
        return made

    # ------------------------------------------------------------- the mail
    def _notify(self, xmlid, addresses):
        """Queue one message. Never raises; never counts a dead letter.

        Its own sender rather than the decision's, because a `mail.template`
        renders against the model it is declared on: handing the DECISION's id
        to a template declared on this model renders somebody else's record,
        silently, with no error anywhere. Same shape as the decision's, same
        explicit `email_to` (R6), same switch.
        """
        self.ensure_one()
        if not flag(self.env, P_MAIL):
            _logger.info('pb_contract_lifecycle: contract emails are switched '
                         'off')
            return False
        clean, seen = [], set()
        for address in (addresses or []):
            address = (address or '').strip()
            if address and address.lower() not in seen:
                seen.add(address.lower())
                clean.append(address)
        if not clean:
            _logger.info('pb_contract_lifecycle: extension %s — nobody to '
                         'write to', self.id)
            return False
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_contract_lifecycle: %s is missing', xmlid)
            return False
        try:
            template.sudo().send_mail(
                self.id, force_send=False,
                email_values={'email_to': ','.join(clean),
                              'auto_delete': False})
            return True
        except Exception:               # noqa: BLE001
            _logger.exception('pb_contract_lifecycle: could not queue %s for '
                              'extension %s', xmlid, self.id)
            return False

    def _approver_addresses(self):
        self.ensure_one()
        out = []
        if self.approver_user_id and self.approver_user_id.email:
            out.append(self.approver_user_id.email)
        manager = self.employee_id.parent_id if self.employee_id else False
        if manager and manager.work_email:
            out.append(manager.work_email)
        return out

    def _hr_addresses(self):
        self.ensure_one()
        return self.review_id._hr_addresses() if self.review_id else []

    def state_label(self):
        self.ensure_one()
        return STATE_LABEL.get(self.state, self.state or '')

    def approval_ladder(self):
        """The stepper's own rungs — written once, read by the drawer."""
        self.ensure_one()
        return self._approval_widget_payload([
            {'state': 'draft', 'label': _('Written')},
            {'state': 'pending', 'label': _('With the manager')},
            {'state': 'approved', 'label': _('Agreed')},
        ])
