# -*- coding: utf-8 -*-
"""`pb.training.delay` — "I need more time", with a reason and an answer.

WHY THIS IS A RECORD AND NOT A FIELD ON THE ASSIGNMENT. A due date that anybody
can move is not a due date. The whole value of the chasing is that the date was
agreed by somebody — so asking for more time is a REQUEST, it names a reason, it
goes to the person's own manager through the Approval Matrix like every other
sign-off in this product, and the new date carries their name.

WHAT AN APPROVAL DOES, exactly: the assignment's due date moves on by the days
that were asked for, the assignment reads "More time agreed" until that date,
the reminder ledger is cleared so the new date starts a fresh chase rather than
inheriting the old one's keys, and the employee is told. A REFUSAL changes
nothing at all and the chasing carries on — which is the honest outcome, and is
why the refusal note is shown on their own page rather than swallowed.

THE STATE IS DRIVEN BY THE CHAIN, never written by hand: `biz.approval.chain
.mixin` refuses a bare `write({'state': ...})` outright, which is what stops a
"Mark as agreed" button ever appearing on this record by accident.
"""

import logging

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .training_common import (
    DELAY_KIND_LABEL, DELAY_KINDS, DELAY_MAX_DAYS, DELAY_STATES, as_id, leg,
)

_logger = logging.getLogger(__name__)


class PbTrainingDelay(models.Model):
    _name = 'pb.training.delay'
    _description = 'Request for more time on a course'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'biz.approval.chain.mixin']
    _order = 'id desc'

    #: The ladder the record keeps for itself when no route is published. One
    #: rung, because asking for a few more days is a conversation with one
    #: person. Under a published route the shim takes every press and the
    #: route decides the order (AM84).
    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('submitted', 'approved'): None,
        ('submitted', 'refused'): None,
        ('draft', 'refused'): None,
    }

    assignment_id = fields.Many2one(
        'pb.training.assignment', string='The course', required=True,
        index=True, ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', related='assignment_id.employee_id', store=True,
        index=True, string='Who is asking', readonly=True)
    channel_id = fields.Many2one(
        'slide.channel', related='assignment_id.channel_id', store=True,
        string='Course', readonly=True)
    company_id = fields.Many2one(
        'res.company', related='assignment_id.company_id', store=True,
        index=True, string='Company', readonly=True)

    reason_kind = fields.Selection(
        DELAY_KINDS, string='Why', required=True, default='other',
        tracking=True)
    note = fields.Text(string='Anything they want to add')
    days_asked = fields.Integer(
        string='Days they are asking for', default=7, required=True,
        tracking=True)
    state = fields.Selection(
        DELAY_STATES, string='How far it has got', default='draft',
        required=True, index=True, tracking=True, copy=False)

    old_due_date = fields.Date(string='Was due', readonly=True, copy=False)
    new_due_date = fields.Date(string='Now due', readonly=True, copy=False)
    decided_on = fields.Datetime(string='Answered on', readonly=True,
                                 copy=False)
    refuse_note = fields.Text(string='Why it was turned down', copy=False)

    # =====================================================================
    #  sanity
    # =====================================================================
    @api.constrains('days_asked')
    def _check_days(self):
        for rec in self:
            if rec.days_asked < 1:
                raise ValidationError(_(
                    "Ask for at least one more day."))
            if rec.days_asked > DELAY_MAX_DAYS:
                raise ValidationError(_(
                    "The most that can be asked for in one go is %s days. "
                    "For longer than that, ask the training team to set a new "
                    "date.", DELAY_MAX_DAYS))

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _(
                "More time · %(who)s · %(course)s",
                who=rec.employee_id.sudo().name or '',
                course=rec.channel_id.sudo().name or '')

    # =====================================================================
    #  the two hooks the chain calls
    # =====================================================================
    def _before_approval_transition(self, to_state):
        """Remember the date that was true when it was agreed."""
        res = super()._before_approval_transition(to_state)
        if to_state == 'approved':
            self.sudo().write({'old_due_date':
                               self.assignment_id.sudo().due_date})
        return res

    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state == 'approved':
            leg(self.env, 'move the due date', self._apply)
        elif to_state == 'refused':
            self.sudo().write({'decided_on': fields.Datetime.now()})
            leg(self.env, 'tell them it was turned down',
                lambda: self._tell('pb_training.mail_template_delay_refused'))
        return res

    def _apply(self):
        """Move the date, excuse the chasing, start a fresh ledger."""
        self.ensure_one()
        assignment = self.assignment_id.sudo()
        if not assignment:
            return False
        base = assignment.due_date or fields.Date.today()
        new_due = base + timedelta(days=max(self.days_asked, 1))
        assignment.with_context(tracking_disable=True, mail_notrack=True) \
            .write({'due_date': new_due, 'excused_until': new_due})
        # The old date's nudges must not be inherited by the new one (a key
        # that has been sent is never sent again), or five more days would be
        # agreed and then chased on yesterday's schedule.
        assignment._clear_reminders()
        assignment._refresh_one()
        self.sudo().write({'new_due_date': new_due,
                           'decided_on': fields.Datetime.now()})
        leg(self.env, 'tell them it was agreed',
            lambda: self._tell('pb_training.mail_template_delay_approved'))
        return True

    def _tell(self, xmlid):
        self.ensure_one()
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_training: %s is missing', xmlid)
            return False
        emp = self.employee_id.sudo()
        to = (emp.work_email or '').strip() or (emp.user_id.email or '').strip()
        if not to:
            _logger.info('pb_training: delay %s has nobody to write to',
                         self.id)
            return False
        template.sudo().send_mail(
            self.id, force_send=False,
            email_values={'email_to': to, 'auto_delete': False})
        return True

    # =====================================================================
    #  the three buttons on the record's own form
    # =====================================================================
    # UNDER A PUBLISHED ROUTE THESE SAY WHAT SOMEBODY MEANS AND THE ENGINE
    # SAYS WHETHER IT MAY HAPPEN (AM84). `_advance_state` is the shim's entry
    # point: with a route live it opens or decides the request, and with no
    # route published at all it walks the small ladder above instead — which
    # is what keeps this record usable on a database where training approvals
    # were never switched on.
    def action_submit(self):
        for rec in self:
            rec._advance_state('submitted')
        return True

    def action_approve(self):
        for rec in self:
            rec._advance_state('approved')
        return True

    def action_refuse(self):
        for rec in self:
            rec.action_refuse_chain(rec.refuse_note or False)
        return True

    # =====================================================================
    #  the door the employee's own page uses
    # =====================================================================
    @api.model
    def ask(self, assignment_id, reason_kind, days_asked, note=''):
        """Raise one, and send it in, in a single press.

        A DRAFT NOBODY SENDS IN IS A REQUEST THAT WAS NEVER MADE. The employee
        page has one button and one dialog, so the record is created and
        submitted in the same call — there is no half-made state a person can
        leave behind and then wonder why nobody answered.
        """
        assignment = self.env['pb.training.assignment'].sudo().browse(
            as_id(assignment_id)).exists()
        if not assignment:
            raise UserError(_("That course is not one of yours."))
        me = self.env.user
        if assignment.employee_id.sudo().user_id != me and not me._is_admin():
            raise UserError(_("That course is not one of yours."))
        if assignment.state == 'done':
            raise UserError(_(
                "That one is already finished, so there is nothing to put "
                "off."))
        live = self.sudo().search([
            ('assignment_id', '=', assignment.id),
            ('state', '=', 'submitted')], limit=1)
        if live:
            raise UserError(_(
                "You have already asked for more time on this one and "
                "%(who)s has not answered yet.",
                who=assignment._manager().sudo().name or _('your manager')))
        try:
            days = int(days_asked or 0)
        except (TypeError, ValueError):
            days = 0
        if days < 1:
            raise UserError(_("Say how many more days you need."))
        record = self.sudo().create({
            'assignment_id': assignment.id,
            'reason_kind': reason_kind if reason_kind in DELAY_KIND_LABEL
            else 'other',
            'days_asked': min(days, DELAY_MAX_DAYS),
            'note': (note or '').strip()[:2000],
        })
        record._advance_state('submitted')
        return {'id': record.id, 'state': record.state,
                'message': _(
                    "Asked. %(who)s will see it and you will get an email "
                    "either way.",
                    who=assignment._manager().sudo().name
                    or _('Your manager'))}
