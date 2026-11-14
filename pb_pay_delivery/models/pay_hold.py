# -*- coding: utf-8 -*-
"""Hold one person's pay — and pay them later (WDGAP PR-C).

WHAT A HOLD IS. A flag on ONE payslip that stops the MONEY and the payslip
delivery for that person, and nothing else. The payslip is still calculated
with the run and approved with the run (no hold touches the calculation): a
hold is about the bank and the email, not about payroll.

WHAT IT STOPS, AND WHERE (every door re-checks, nothing trusts a cache):
  * the bank file leaves a held payslip out, with the reason "On hold"
    (`vietnam.bank.export.wizard._row_sources`);
  * the payment release refuses a file that carries a payslip held AFTER the
    file was prepared, and only ever stamps `pb_paid_on` on the payslips that
    are in the released file (`pb.payment.release`);
  * the payslip send-out skips a held payslip (`pb.payslip.delivery.batch`);
  * the employee does not see a held payslip on My Payobook (`pb_me_portal`
    reads `pb_pay_hold` when the field exists).

WHAT A HOLD CANNOT DO. It cannot reach money that has already gone: a payslip
already paid, or in a bank file whose money has been released, cannot be held.

WHO. The pay team — the same people who may prepare the bank file
(`PAY_GROUPS`) — in the payslip's own company. Nobody holds or lifts the hold
on their OWN payslip.

AUDIT. Each hold and each release writes a line on the payslip's history and
one entry in the platform-wide trail (`pb.money.approval.mixin.audit`, the
module's one-call entry point into `biz_audit_trail`).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

#: A reason is a sentence somebody can act on, not a keystroke.
MIN_REASON = 6
#: Payslip states a hold may be placed in: calculated (draft with lines, or
#: waiting for the run's approval) or finished.
HOLDABLE_STATES = ('draft', 'verify', 'level1', 'level2', 'done')
#: Who may READ the hold's details through the ORM (the flag itself is open).
HOLD_DETAIL_GROUPS = 'om_hr_payroll.group_hr_payroll_user'


class HrPayslipHold(models.Model):
    _inherit = 'hr.payslip'

    pb_pay_hold = fields.Boolean(
        string='Pay on hold', index=True, readonly=True, copy=False,
        help="This person's money and payslip are held back until the hold "
             "is released. The payslip itself is calculated and approved "
             "with the pay run as usual.")
    # The details are for the payroll team only (R5): an employee who can read
    # their own payslip never reads why or by whom their pay is held. Every
    # screen that shows them reads them under sudo after its own rights check.
    pb_hold_reason = fields.Char(string='Why the pay is on hold',
                                 readonly=True, copy=False,
                                 groups=HOLD_DETAIL_GROUPS)
    pb_hold_by = fields.Many2one('res.users', string='Put on hold by',
                                 readonly=True, copy=False,
                                 ondelete='set null',
                                 groups=HOLD_DETAIL_GROUPS)
    pb_hold_on = fields.Datetime(string='Put on hold on', readonly=True,
                                 copy=False, groups=HOLD_DETAIL_GROUPS)
    pb_hold_released_by = fields.Many2one(
        'res.users', string='Hold released by', readonly=True, copy=False,
        ondelete='set null', groups=HOLD_DETAIL_GROUPS)
    pb_hold_released_on = fields.Datetime(string='Hold released on',
                                          readonly=True, copy=False,
                                          groups=HOLD_DETAIL_GROUPS)

    @api.constrains('pb_pay_hold', 'pb_hold_reason')
    def _check_pb_hold_reason(self):
        for slip in self:
            if slip.pb_pay_hold and len((slip.pb_hold_reason or '').strip()) < MIN_REASON:
                raise ValidationError(_(
                    "Write why the pay is on hold (at least %s characters).",
                    MIN_REASON))

    # ------------------------------------------------------------ reading
    def _pb_slip_currency(self):
        """The money this payslip is paid in: its scheme's, else its company's."""
        self.ensure_one()
        config = self.formula_config_id if 'formula_config_id' in self._fields \
            else False
        if config and config.currency_id:
            return config.currency_id
        return self.company_id.currency_id or self.env.company.currency_id

    def _pb_net_amount(self):
        """Take-home pay: the scheme's own net line (the bank file's figure)."""
        self.ensure_one()
        return self.env['vietnam.bank.export.wizard']._slip_net(self)

    def _pb_released_slip_ids(self):
        """Ids of the payslips (of these payslips' runs) that sit in a bank
        file whose money has been RELEASED."""
        runs = self.mapped('payslip_run_id')
        if not runs:
            return set()
        releases = self.env['pb.payment.release'].sudo().search([
            ('run_id', 'in', runs.ids), ('state', '=', 'released')])
        ids = set()
        for release in releases:
            ids.update(release.bank_file_id._pb_file_slips().ids)
        return ids

    def _pb_hold_blocker(self, released_ids=None):
        """Why this payslip cannot be put on hold, in words; '' when it can."""
        self.ensure_one()
        name = self.employee_id.name or _('This person')
        if self.state == 'cancel':
            return _("%s's payslip was rejected, so there is no pay to hold.",
                     name)
        if self.state not in HOLDABLE_STATES or (
                self.state == 'draft' and not self.line_ids):
            return _("%s's payslip has not been calculated yet. Calculate the "
                     "pay run first.", name)
        if self.pb_paid_on:
            return _("%(name)s has already been paid (%(date)s), so this pay "
                     "can no longer be held.", name=name,
                     date=fields.Date.to_string(
                         fields.Datetime.context_timestamp(
                             self, self.pb_paid_on).date()))
        if released_ids is None:
            released_ids = self._pb_released_slip_ids()
        if self.id in released_ids:
            return _("%s is in a bank file whose money has already been "
                     "released, so this pay can no longer be held.", name)
        return ''

    def _pb_hold_payload(self, may_act=None):
        """What the screens show about the hold on this payslip."""
        self.ensure_one()
        sudo = self.sudo()
        if may_act is None:
            may_act = self._pb_hold_may_act()
        blocker = '' if sudo.pb_pay_hold else sudo._pb_hold_blocker()
        own = self._pb_is_own()
        may_act = may_act and not own
        return {
            'on': bool(sudo.pb_pay_hold),
            'reason': sudo.pb_hold_reason or '',
            'by': sudo.pb_hold_by.name or '',
            'on_date': fields.Datetime.to_string(sudo.pb_hold_on) or '',
            'released_by': sudo.pb_hold_released_by.name or '',
            'released_on': fields.Datetime.to_string(
                sudo.pb_hold_released_on) or '',
            'can_hold': bool(may_act and not sudo.pb_pay_hold and not blocker),
            'can_release': bool(may_act and sudo.pb_pay_hold),
            'blocker': blocker,
            'own': own,
            'may_act': bool(may_act),
        }

    # ------------------------------------------------------------ the gate
    def _pb_is_own(self):
        self.ensure_one()
        user = self.sudo().employee_id.user_id
        return bool(user and user.id == self.env.uid)

    def _pb_hold_may_act(self):
        """May the current user hold or release pay at all (role only)?"""
        return self.env['pb.money.approval.mixin']._pay_groups_held()

    def _pb_hold_check(self):
        """Refuse, by name, anybody who may not hold or release this pay."""
        Mixin = self.env['pb.money.approval.mixin']
        if not Mixin._pay_groups_held():
            raise AccessError(_(
                "Only the pay team can hold or release a person's pay. This "
                "needs the Payroll Manager or a Finance role."))
        allowed = set(self.env.user.company_ids.ids)
        for slip in self.sudo():
            if slip.company_id and slip.company_id.id not in allowed:
                raise AccessError(_(
                    "%s's payslip belongs to a company you do not work in.",
                    slip.employee_id.name or _('This person')))
            if slip.with_env(self.env)._pb_is_own():
                raise AccessError(_(
                    "You cannot hold or release your own pay. Ask someone "
                    "else in the pay team."))

    # ------------------------------------------------------------ actions
    def action_pb_hold(self, reason):
        """Hold these payslips' pay, for `reason`."""
        reason = (reason or '').strip()
        if len(reason) < MIN_REASON:
            raise UserError(_(
                "Write why the pay is on hold (at least %s characters).",
                MIN_REASON))
        self._pb_hold_check()
        slips = self.sudo()
        released_ids = slips._pb_released_slip_ids()
        for slip in slips:
            if slip.pb_pay_hold:
                raise UserError(_("%s's pay is already on hold.",
                                  slip.employee_id.name or _('This person')))
            blocker = slip._pb_hold_blocker(released_ids)
            if blocker:
                raise UserError(blocker)
        now = fields.Datetime.now()
        Mixin = self.env['pb.money.approval.mixin']
        for slip in slips:
            slip.write({
                'pb_pay_hold': True, 'pb_hold_reason': reason[:256],
                'pb_hold_by': self.env.uid, 'pb_hold_on': now,
                'pb_hold_released_by': False, 'pb_hold_released_on': False,
            })
            slip._pb_hold_note(_(
                "Pay put on hold by %(who)s. Reason: %(reason)s. This person "
                "is left out of the bank file and their payslip is not sent "
                "until the hold is released.",
                who=self.env.user.name, reason=reason))
            Mixin.audit(slip, 'pb_pay_hold', _('Pay on hold'), _('No'),
                        _('Yes · %s', reason))
        return True

    def action_pb_release_hold(self):
        """Lift the hold: the pay can go in a payment file again."""
        self._pb_hold_check()
        slips = self.sudo()
        for slip in slips:
            if not slip.pb_pay_hold:
                raise UserError(_("%s's pay is not on hold.",
                                  slip.employee_id.name or _('This person')))
        now = fields.Datetime.now()
        Mixin = self.env['pb.money.approval.mixin']
        for slip in slips:
            old = slip.pb_hold_reason or ''
            slip.write({'pb_pay_hold': False,
                        'pb_hold_released_by': self.env.uid,
                        'pb_hold_released_on': now})
            slip._pb_hold_note(_(
                "Hold released by %(who)s. Their pay can now go in a payment "
                "file and their payslip can be sent.", who=self.env.user.name))
            Mixin.audit(slip, 'pb_pay_hold', _('Pay on hold'),
                        _('Yes · %s', old), _('No'))
        return True

    def _pb_hold_note(self, body):
        """One line on the payslip's history, written by the person who acted."""
        self.ensure_one()
        try:
            self.sudo().message_post(
                body=body, author_id=self.env.user.partner_id.id,
                message_type='comment', subtype_xmlid='mail.mt_note')
        except Exception:   # noqa: BLE001 — a note must never undo the hold
            _logger.exception('pb_pay_delivery: could not note the hold on '
                              'payslip %s', self.id)


class HrPayslipRunHold(models.Model):
    """What the run's approver and the bank-file approver are told."""
    _inherit = 'hr.payslip.run'

    def pb_hold_summary(self):
        """{count, people, sentence, by_currency} for this run's held payslips."""
        self.ensure_one()
        held = self.sudo().slip_ids.filtered(
            lambda s: s.pb_pay_hold and s.state != 'cancel')
        people, by_cur = [], {}
        for slip in held.sorted(key=lambda s: s.employee_id.name or ''):
            cur = slip._pb_slip_currency()
            net = slip._pb_net_amount()
            row = by_cur.setdefault(cur.id, {'currency': cur.name or '',
                                             'symbol': cur.symbol or '',
                                             'amount': 0.0, 'count': 0})
            row['amount'] += net
            row['count'] += 1
            people.append({
                'slip_id': slip.id, 'employee': slip.employee_id.name or '',
                'employee_id': slip.employee_id.id,
                'reason': slip.pb_hold_reason or '',
                'by': slip.pb_hold_by.name or '',
                'on_date': fields.Datetime.to_string(slip.pb_hold_on) or '',
                'amount': net, 'currency': cur.name or '',
                'symbol': cur.symbol or '',
            })
        count = len(people)
        sentence = ''
        if count == 1:
            sentence = _("1 person's pay is on hold")
        elif count:
            sentence = _("%s people's pay is on hold", count)
        return {'count': count, 'people': people, 'sentence': sentence,
                'by_currency': list(by_cur.values())}

    def _approval_detail(self, request):
        """The run's approver sees who is on hold — only when somebody is."""
        self.ensure_one()
        base = super()._approval_detail(request) \
            if hasattr(super(), '_approval_detail') else None
        if base:
            return base
        summary = self.pb_hold_summary()
        if not summary['count']:
            return base
        return {
            'title': summary['sentence'],
            'columns': [_('Why')],
            'rows': [{
                'head': p['employee'][:40],
                'sub': _('Held by %s', p['by']) if p['by'] else '',
                'cells': [p['reason'][:80]],
                'tone': 'off',
            } for p in summary['people'][:40]],
            'chips': [],
            'note': _("Their payslips are approved with the run as usual. "
                      "Their money and their payslip are held back until "
                      "someone in the pay team releases the hold."),
        }
