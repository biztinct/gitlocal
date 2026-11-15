# -*- coding: utf-8 -*-
"""Paid another way — cash, cheque, a separate transfer (WDGAP PR-E, E2).

Owner ruling (2026-11-15): add the button; lifting a hold stays one-person.

WHO IT IS FOR. A finished payslip that no bank file paid and none will: the
"left out" list (no bank details, an unknown bank, …) of Pay & deliver, or
anybody the pay team paid outside the file. Marking it says the money went,
how, and why — and from then on it is PAID, exactly like a payslip a released
bank file paid:

  * it carries the paid date (`pb_paid_on`), so the run's "Paid" answer, the
    Pay runs board, Payslip review's Paid filter and My Payobook all read it
    as paid with no change of their own;
  * it never enters a bank file or a follow-up file again (`pb_unpaid_only`
    reads the same stamp), and a file prepared BEFORE it was marked is refused
    at the release (`pb.payment.release._pb_refuse_held`) until it is
    prepared again without that person;
  * it cannot be put on hold (the hold's own rule: already paid);
  * its payslip is sent like any paid payslip.

WHAT IS RECORDED. How (`pb_paid_method`), the note (`pb_paid_note`, at least
six characters), who (`pb_paid_by`), when (`pb_paid_on`, a date never in the
future); a line on the payslip's history by the person, and one entry in the
platform-wide trail (`pb.money.approval.mixin.audit`).

UNDO. "Not paid after all", with a reason, only for a payslip marked this
way — never for one a released bank file paid.

WHO. The pay team (`PAY_GROUPS`, the same people as hold / release), in the
payslip's own company, never on their own pay. Several people at once (one
method and note for the selection), at most `MAX_AT_ONCE`.
"""

import logging
from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .pay_hold import HOLD_DETAIL_GROUPS

_logger = logging.getLogger(__name__)

#: How the money went, when it did not go through a bank file.
PAID_METHODS = [
    ('cash', 'Cash'),
    ('cheque', 'Cheque'),
    ('transfer', 'Other bank transfer'),
    ('other', 'Other'),
]
#: A note is a sentence somebody can check later, not a keystroke.
MIN_NOTE = 6
#: People marked in one go.
MAX_AT_ONCE = 50


class HrPayslipPaidOther(models.Model):
    _inherit = 'hr.payslip'

    # The method is read by every total (the pay team's screens read it under
    # their own rights); the note and the person are payroll-only, like the
    # hold's details (ledger PRC-W1).
    pb_paid_method = fields.Selection(
        PAID_METHODS, string='Paid another way', readonly=True, copy=False,
        index=True,
        help="This person's pay was paid outside the bank file — in cash, by "
             "cheque, by a separate transfer or otherwise.")
    pb_paid_note = fields.Char(string='How it was paid', readonly=True,
                               copy=False, groups=HOLD_DETAIL_GROUPS)
    pb_paid_by = fields.Many2one('res.users', string='Marked as paid by',
                                 readonly=True, copy=False,
                                 ondelete='set null',
                                 groups=HOLD_DETAIL_GROUPS)

    @api.constrains('pb_paid_method', 'pb_paid_note', 'pb_paid_on')
    def _check_pb_paid_other(self):
        for slip in self.sudo():
            if not slip.pb_paid_method:
                continue
            if len((slip.pb_paid_note or '').strip()) < MIN_NOTE:
                raise ValidationError(_(
                    "Write how the pay was paid (at least %s characters).",
                    MIN_NOTE))
            if not slip.pb_paid_on:
                raise ValidationError(_(
                    "A payslip paid another way needs the day it was paid."))

    # ------------------------------------------------------------ reading
    @api.model
    def _pb_paid_method_label(self, method):
        return dict(self._fields['pb_paid_method']._description_selection(
            self.env)).get(method, '') if method else ''

    def _pb_paid_other_blocker(self, released_ids=None):
        """Why this payslip cannot be marked as paid another way; '' when it
        can."""
        self.ensure_one()
        name = self.employee_id.name or _('This person')
        if self.state != 'done':
            return _("%s's payslip is not finished yet. Approve the pay run "
                     "first.", name)
        if self.pb_paid_on:
            return _("%(name)s has already been paid (%(date)s).", name=name,
                     date=fields.Date.to_string(
                         fields.Datetime.context_timestamp(
                             self, self.pb_paid_on).date()))
        if self.pb_pay_hold:
            return _("%s's pay is on hold. Release the hold first.", name)
        if released_ids is None:
            released_ids = self._pb_released_slip_ids()
        if self.id in released_ids:
            return _("%s is in a bank file whose money has already been "
                     "released.", name)
        return ''

    def _pb_paid_other_check(self):
        """Refuse, by name, anybody who may not mark this pay as paid."""
        Mixin = self.env['pb.money.approval.mixin']
        if not Mixin._pay_groups_held():
            raise AccessError(_(
                "Only the pay team can mark pay as paid another way. This "
                "needs the Payroll Manager or a Finance role."))
        allowed = set(self.env.user.company_ids.ids)
        for slip in self.sudo():
            if slip.company_id and slip.company_id.id not in allowed:
                raise AccessError(_(
                    "%s's payslip belongs to a company you do not work in.",
                    slip.employee_id.name or _('This person')))
            if slip.with_env(self.env)._pb_is_own():
                raise AccessError(_(
                    "You cannot mark your own pay as paid. Ask someone else "
                    "in the pay team."))

    # ------------------------------------------------------------ actions
    def action_pb_paid_other(self, method, note, paid_date=None):
        """Mark these payslips as paid another way: one method and one note
        for all of them, on `paid_date` (default today, never later)."""
        if not self:
            raise UserError(_("Pick at least one person."))
        if len(self) > MAX_AT_ONCE:
            raise UserError(_(
                "Mark at most %s people at once.", MAX_AT_ONCE))
        if method not in dict(PAID_METHODS):
            raise UserError(_(
                "Choose how the pay was paid: cash, cheque, another bank "
                "transfer or something else."))
        note = (note or '').strip()
        if len(note) < MIN_NOTE:
            raise UserError(_(
                "Write how the pay was paid (at least %s characters), for "
                "example the cheque number or who handed over the cash.",
                MIN_NOTE))
        today = fields.Date.context_today(self)
        day = fields.Date.to_date(paid_date) if paid_date else today
        if day > today:
            raise UserError(_(
                "The day it was paid cannot be in the future."))
        self._pb_paid_other_check()
        slips = self.sudo()
        released_ids = slips._pb_released_slip_ids()
        for slip in slips:
            blocker = slip._pb_paid_other_blocker(released_ids)
            if blocker:
                raise UserError(blocker)
        if day == today:
            stamp = fields.Datetime.now()
        else:
            # noon, so the day reads the same in every time zone around it
            stamp = datetime.combine(day, time(12, 0))
        label = self._pb_paid_method_label(method)
        Mixin = self.env['pb.money.approval.mixin']
        for slip in slips:
            slip.write({
                'pb_paid_on': stamp, 'pb_paid_ref': False,
                'pb_paid_method': method, 'pb_paid_note': note[:256],
                'pb_paid_by': self.env.uid,
            })
            slip._pb_hold_note(_(
                "Marked as paid another way by %(who)s: %(how)s, on "
                "%(day)s. Note: %(note)s. This pay is not in any bank file.",
                who=self.env.user.name, how=label,
                day=fields.Date.to_string(day), note=note))
            Mixin.audit(slip, 'pb_paid_method', _('Paid another way'), '',
                        '%s · %s · %s' % (label, fields.Date.to_string(day),
                                          note))
        return True

    def action_pb_not_paid_after_all(self, reason):
        """Undo "paid another way": the pay is still to pay again. Never for
        pay a released bank file paid."""
        reason = (reason or '').strip()
        if len(reason) < MIN_NOTE:
            raise UserError(_(
                "Write why this pay was not paid after all (at least %s "
                "characters).", MIN_NOTE))
        self._pb_paid_other_check()
        slips = self.sudo()
        released_ids = slips._pb_released_slip_ids()
        for slip in slips:
            name = slip.employee_id.name or _('This person')
            if not slip.pb_paid_method:
                if slip.pb_paid_on:
                    raise UserError(_(
                        "%s was paid by a released bank file. That cannot be "
                        "undone here.", name))
                raise UserError(_("%s's pay is not marked as paid another "
                                  "way.", name))
            if slip.id in released_ids:
                raise UserError(_(
                    "%s is in a bank file whose money has already been "
                    "released. That cannot be undone here.", name))
        Mixin = self.env['pb.money.approval.mixin']
        for slip in slips:
            old = '%s · %s' % (self._pb_paid_method_label(slip.pb_paid_method),
                               slip.pb_paid_note or '')
            slip.write({'pb_paid_on': False, 'pb_paid_ref': False,
                        'pb_paid_method': False, 'pb_paid_note': False,
                        'pb_paid_by': False})
            slip._pb_hold_note(_(
                "Marked as not paid after all by %(who)s. Reason: %(reason)s. "
                "Their pay is still to pay.", who=self.env.user.name,
                reason=reason))
            Mixin.audit(slip, 'pb_paid_method', _('Paid another way'), old,
                        _('No · %s', reason))
        return True

    def _pb_paid_other_payload(self):
        """What the screens show about one payslip paid another way."""
        self.ensure_one()
        sudo = self.sudo()
        return {
            'slip_id': self.id,
            'employee': sudo.employee_id.name or '',
            'employee_id': sudo.employee_id.id,
            'method': sudo.pb_paid_method or '',
            'method_label': self._pb_paid_method_label(sudo.pb_paid_method),
            'note': sudo.pb_paid_note or '',
            'by': sudo.pb_paid_by.name or '',
            'on_date': fields.Datetime.to_string(sudo.pb_paid_on) or '',
        }


class HrPayslipRunPaidOther(models.Model):
    _inherit = 'hr.payslip.run'

    def pb_paid_other_summary(self):
        """{count, people, sentence, by_currency} — who in this run was paid
        another way."""
        self.ensure_one()
        slips = self.sudo().slip_ids.filtered(
            lambda s: s.state == 'done' and s.pb_paid_method)
        people, by_cur = [], {}
        for slip in slips.sorted(key=lambda s: s.employee_id.name or ''):
            cur = slip._pb_slip_currency()
            net = max(slip._pb_net_amount(), 0.0)
            row = by_cur.setdefault(cur.id, {'currency': cur.name or '',
                                             'symbol': cur.symbol or '',
                                             'amount': 0.0, 'count': 0})
            row['amount'] += net
            row['count'] += 1
            person = slip._pb_paid_other_payload()
            person.update(amount=net, currency=cur.name or '',
                          symbol=cur.symbol or '')
            people.append(person)
        count = len(people)
        sentence = ''
        if count == 1:
            sentence = _("1 person was paid another way")
        elif count:
            sentence = _("%s people were paid another way", count)
        return {'count': count, 'people': people, 'sentence': sentence,
                'by_currency': list(by_cur.values())}
