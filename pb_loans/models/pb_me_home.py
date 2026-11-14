# -*- coding: utf-8 -*-
"""My Payobook — "My loans": what I borrowed, what is left, what comes off
next, and the history. Read-only.

THE ROUTE IS THE GATE (TIERS): employees hold no right on `pb.loan`. Every
read here is `sudo()` keyed on the employee the SESSION resolves to (the
controller's `_ess_employee`), and `my_loans` refuses any employee that is not
the caller's own. QUIET AT ZERO: the home card is drawn only for a person who
has a loan that is waiting, running, paused or closed this year.
"""
import logging

from odoo import api, models

from .loan import OPEN_STATES

_logger = logging.getLogger(__name__)

#: Loans a person sees on their own page.
SHOWN_STATES = ('waiting', 'running', 'paused', 'closed')


class PbLoanPortal(models.Model):
    _inherit = 'pb.loan'

    @api.model
    def my_loans(self, employee):
        """`{'loans': [...], 'left_label', 'next_label', 'any_open'}` for the
        caller's OWN employee, or None for anybody else's."""
        if not employee or employee._name != 'hr.employee':
            return None
        employee = employee.sudo()[:1]
        if not employee or employee.user_id.id != self.env.uid:
            return None
        _ = self.env._
        loans = self.sudo().search([('employee_id', '=', employee.id),
                                    ('state', 'in', SHOWN_STATES)], order='id desc')
        rows = []
        left = {}
        upcoming = []
        for loan in loans:
            amount = loan.amount or 0.0
            pct = int(max(0.0, min(100.0, (loan.repaid or 0.0) / amount * 100.0))) \
                if amount > 0 else 0
            history = []
            for line in loan.repayment_ids.filtered(
                    lambda l: l.state in ('reserved', 'paid')).sorted(
                    lambda l: (l.pay_month, l.id), reverse=True):
                history.append({
                    'month': loan._month_label(line.pay_month),
                    'amount': loan._money(line.amount),
                    'how': (_("From your pay") if line.kind == 'payroll'
                            else _("Paid back directly")),
                    'state': line.state,
                    'state_label': (_("Paid") if line.state == 'paid'
                                    else _("In this month's pay run")),
                })
            next_label = ''
            if loan.state == 'running' and loan.next_amount:
                next_label = _("%(amount)s comes off your %(month)s pay",
                               amount=loan._money(loan.next_amount),
                               month=loan._month_label(loan.next_month))
                upcoming.append((loan.next_month, loan.currency_id, loan.next_amount))
            if loan.state in OPEN_STATES:
                left.setdefault(loan.currency_id, 0.0)
                left[loan.currency_id] += loan.balance
            rows.append({
                'id': loan.id, 'name': loan.name or '',
                'kind_label': loan._kind_label(),
                'state': loan.state,
                'state_label': {
                    'waiting': _("Waiting for approval"),
                    'running': _("Being paid back"),
                    'paused': _("Paused"),
                    'closed': _("Paid back in full"),
                }.get(loan.state, loan._state_label()),
                'amount': loan._money(amount),
                'repaid': loan._money(loan.repaid),
                'balance': loan._money(loan.balance),
                'pct': pct,
                'plan': loan._plan_sentence(),
                'reason': loan.reason or '',
                'next_label': next_label,
                'paused': loan.state == 'paused',
                'history': history,
                'closed_on': loan._month_label(loan.closed_on) if loan.closed_on else '',
            })
        left_label = ' · '.join(self._money(v, c) for c, v in left.items()) if left else ''
        next_label = ''
        if upcoming:
            first = min(m for m, _c, _a in upcoming)
            sums = {}
            for month, cur, amt in upcoming:
                if month == first:
                    sums[cur] = sums.get(cur, 0.0) + amt
            next_label = _("%(amount)s comes off your %(month)s pay",
                           amount=' · '.join(self._money(v, c) for c, v in sums.items()),
                           month=self._month_label(first))
        return {'loans': rows, 'left_label': left_label, 'next_label': next_label,
                'any_open': bool(left), 'count': len(rows)}


class PbMeHomeLoans(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_extra_cards(self, emp):
        cards = super()._pbme_extra_cards(emp)
        try:
            data = self.env['pb.loan'].my_loans(emp)
        except Exception:       # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_loans: the home card failed', exc_info=True)
            data = None
        if data and data.get('any_open'):
            cards.append({'key': 'loans', 'template': 'pb_loans.pbme_card_loans',
                          'data': data})
        return cards
