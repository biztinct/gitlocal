# -*- coding: utf-8 -*-
"""The gate in front of the last payment.

`hr.full.final.settlement` has no state of its own — it is a calculation with a
date on it, and it is generated in bulk by the payroll batch. That is the right
shape for a calculation, and it is why there is nothing here that touches the
MATHS. What it lacks is the one thing an exit needs: a moment when somebody
says "this is finished, pay it", and something standing in front of that moment.

So this adds `pb_closed`, and one button to reach it, and a guard that refuses
the button in WORDS:

    Not yet — 2 items are still with Tâm (VN-LT-00003 MacBook Pro,
    VN-PH-00007 iPhone), the Finance clearance is still open, and 1 step on the
    leaving checklist is not done (Handover plan).

THREE THINGS ARE ASKED, and every one of them is read under sudo, because a
gate a reader's own access can soften is not a gate:

  1. the steps on the leaving checklist that were marked as holding the money
     (`pb.journey.case.blocking_tasks_for`, P0's single source for that fact);
  2. the clearances that are still pending (P4's own);
  3. what the person is still physically holding (`pb.asset.open_items_for`,
     P2's). Only the TANGIBLE half: an email account that has not been
     switched off is a security job, not a reason to withhold somebody's last
     salary.

NOTHING HERE EVER CLOSES A SETTLEMENT BY ITSELF. `pb_ready` is a question. The
only thing that answers it is a person pressing a button.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .offboarding_common import (
    CLEARANCE_DEPT_LABEL, GROUP_MANAGER, joined_sentence,
)

_logger = logging.getLogger(__name__)


class HrFullFinalSettlement(models.Model):
    _inherit = 'hr.full.final.settlement'

    pb_closed = fields.Boolean(
        string='Settlement closed', readonly=True, copy=False, index=True,
        help='Set when somebody confirms the settlement is finished and may '
             'be paid. Nothing sets it automatically.')
    pb_closed_at = fields.Datetime(string='Closed on', readonly=True,
                                   copy=False)
    pb_closed_by = fields.Many2one('res.users', string='Closed by',
                                   readonly=True, copy=False)
    pb_ready = fields.Boolean(
        string='Ready to close', compute='_compute_pb_gate')
    pb_blockers = fields.Text(
        string='What is still open', compute='_compute_pb_gate')
    pb_case_id = fields.Many2one(
        'pb.journey.case', string='Leaving checklist',
        compute='_compute_pb_gate')

    # ------------------------------------------------------------- the gate
    def _pb_blocker_list(self):
        """The reasons this settlement cannot be closed, as sentences.

        Every probe in its OWN try/except: a register that cannot be read must
        answer "we could not check" rather than taking the other two answers
        down with it — and "we could not check" is a blocker, never a pass. A
        gate that opens when it is broken is not a gate.
        """
        self.ensure_one()
        emp = self.employee_id
        out = []
        if not emp:
            return [_("This settlement is not linked to anybody.")]

        try:
            tasks = self.env['pb.journey.case'].blocking_tasks_for(emp.id)
            if tasks:
                out.append(_(
                    "%(count)s step(s) on the leaving checklist are not done: "
                    "%(what)s.",
                    count=len(tasks),
                    what=joined_sentence(tasks.mapped('name'))))
        except Exception:               # noqa: BLE001
            _logger.exception('pb_offboarding: could not read the leaving '
                              'checklist for employee %s', emp.id)
            out.append(_(
                "The leaving checklist could not be read, so it is not safe to "
                "say this is finished."))

        try:
            pending = self.env['pb.exit.clearance'].pending_for(emp.id)
            if pending:
                out.append(_(
                    "%(count)s clearance(s) still open: %(what)s.",
                    count=len(pending),
                    what=joined_sentence([
                        CLEARANCE_DEPT_LABEL.get(c.dept, c.dept or '')
                        for c in pending], limit=4)))
        except Exception:               # noqa: BLE001
            _logger.exception('pb_offboarding: could not read the clearances '
                              'for employee %s', emp.id)
            out.append(_(
                "The clearances could not be read, so it is not safe to say "
                "this is finished."))

        try:
            items = self.env['pb.asset'].open_items_for(emp.id)
            tangible = items.get('tangible') or []
            if tangible:
                out.append(_(
                    "%(count)s item(s) have not come back: %(what)s.",
                    count=len(tangible),
                    what=joined_sentence([
                        ('%s %s' % (i.get('code') or '', i.get('name') or ''))
                        .strip() for i in tangible])))
        except Exception:               # noqa: BLE001
            _logger.exception('pb_offboarding: could not read the equipment '
                              'register for employee %s', emp.id)
            out.append(_(
                "The equipment register could not be read, so it is not safe "
                "to say this is finished."))
        return out

    @api.depends('employee_id', 'pb_closed')
    def _compute_pb_gate(self):
        Case = self.env['pb.journey.case']
        for rec in self:
            rec.pb_case_id = False
            try:
                blockers = rec._pb_blocker_list()
            except Exception:           # noqa: BLE001
                _logger.exception('pb_offboarding: gate for settlement %s',
                                  rec.id)
                blockers = [_("This could not be checked.")]
            rec.pb_ready = not blockers
            rec.pb_blockers = '\n'.join(blockers)
            if rec.employee_id:
                try:
                    rec.pb_case_id = Case.sudo().search([
                        ('employee_id', '=', rec.employee_id.id),
                        ('case_type', '=', 'offboarding'),
                    ], order='state, anchor_date desc, id desc', limit=1).id
                except Exception:       # noqa: BLE001
                    rec.pb_case_id = False

    # ------------------------------------------------------------- the button
    def _pb_can_close(self):
        user = self.env.user
        return (self.env.su or user._is_admin()
                or user.has_group(GROUP_MANAGER))

    def action_pb_close(self):
        """Say this settlement is finished. Refused, in words, when it is not.

        The refusal names exactly what is outstanding — the whole reason this
        exists is that "you cannot close this" is a dead end and "the Finance
        clearance is still open and the MacBook has not come back" is a next
        action.
        """
        for rec in self:
            if not rec._pb_can_close():
                raise AccessError(_(
                    "Closing a final settlement is for the HR team. Ask them "
                    "to do it once everything is signed off."))
            if rec.pb_closed:
                raise UserError(_(
                    "This settlement was already closed on %(when)s by "
                    "%(who)s.",
                    when=fields.Date.to_string(
                        rec.pb_closed_at.date()) if rec.pb_closed_at else '',
                    who=rec.pb_closed_by.name or _('somebody')))
            blockers = rec._pb_blocker_list()
            if blockers:
                raise UserError(_(
                    "%(who)s's settlement cannot be closed yet.\n\n%(what)s\n\n"
                    "Sort these out and press Close again — nothing here is "
                    "lost in the meantime.",
                    who=rec.employee_id.name or _('This person'),
                    what='\n'.join('• %s' % b for b in blockers)))
            rec.write({
                'pb_closed': True,
                'pb_closed_at': fields.Datetime.now(),
                'pb_closed_by': self.env.uid,
            })
            rec._pb_after_close()
        return True

    def action_pb_reopen(self):
        """Undo the closure. HR only, and the checklist is told."""
        for rec in self:
            if not rec._pb_can_close():
                raise AccessError(_(
                    "Re-opening a final settlement is for the HR team."))
            if not rec.pb_closed:
                continue
            rec.write({'pb_closed': False, 'pb_closed_at': False,
                       'pb_closed_by': False})
            case = rec.pb_case_id
            if case:
                case.sudo().message_post(body=_(
                    "The final settlement was re-opened by %(who)s.",
                    who=self.env.user.name))
        return True

    def _pb_after_close(self):
        """What follows a closure: a line in the checklist, and the letter.

        `hr.full.final.settlement` has no chatter of its own and this module
        deliberately does not give it one — adding `mail.thread` to a model the
        payroll batch creates in bulk is a change with a blast radius far
        wider than an exit. The line goes where somebody would look for it: the
        leaving checklist.
        """
        self.ensure_one()
        case = self.pb_case_id
        if case:
            try:
                case.sudo().message_post(body=_(
                    "The final settlement was closed by %(who)s. Everything "
                    "that was holding it had been signed off.",
                    who=self.env.user.name))
            except Exception:           # noqa: BLE001
                _logger.exception('pb_offboarding: could not log the closure '
                                  'on journey %s', case.id)
            try:
                # The covering letter waits for exactly this moment. Running it
                # here rather than waiting for tomorrow's job is the difference
                # between a letter that arrives with the payment and one that
                # arrives a day later; `action_auto` is a no-op on a step that
                # is already settled, so a second closure sends nothing.
                for task in case.sudo().task_ids.filtered(
                        lambda t: t.automation_key == 'ff_cover'):
                    task.action_auto(force=True)
            except Exception:           # noqa: BLE001
                _logger.exception('pb_offboarding: could not send the '
                                  'settlement letter for journey %s', case.id)
        return True

    # -------------------------------------------------------- for the board
    @api.model
    def pb_gate_for(self, employee_id):
        """The settlement picture for one leaver, for the Exits board.

        Answers the same shape whether there is a settlement or not, so the
        board never has to branch on None: `{'id', 'ready', 'closed',
        'blockers', 'net'}`.
        """
        out = {'id': 0, 'ready': False, 'closed': False, 'blockers': [],
               'net': 0.0, 'currency': '', 'date': ''}
        settlement = self.sudo().search(
            [('employee_id', '=', int(employee_id or 0))],
            order='pb_closed desc, settlement_date desc, id desc', limit=1)
        if not settlement:
            return out
        out['id'] = settlement.id
        out['closed'] = settlement.pb_closed
        out['net'] = settlement.net_payable or 0.0
        out['currency'] = (settlement.currency_id.symbol
                           if settlement.currency_id else '')
        out['date'] = (str(settlement.settlement_date)
                       if settlement.settlement_date else '')
        blockers = settlement._pb_blocker_list()
        out['ready'] = not blockers
        out['blockers'] = blockers
        return out
