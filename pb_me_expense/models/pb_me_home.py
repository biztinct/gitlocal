# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Expenses on the employee home (D9): a "Needs you" row while a claim came
back refused, and a source for "My requests" (pb_me_portal's T3a hooks)."""

import logging

from odoo import api, models
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)


class PbMeHome(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        _ = self.env._
        refused = self.env['pb.expense.claim'].sudo().search(
            [('employee_id', '=', emp.id), ('state', '=', 'refused')])
        n = len(refused)
        if not n:
            return
        if n == 1:
            label = _('1 expense claim refused — fix and resend')
            sentence = _('An expense claim came back refused.')
            url = '/my/expenses/%s' % refused.id
        else:
            label = _('%s expense claims refused — fix and resend', n)
            sentence = _('%s expense claims came back refused.', n)
            url = '/my/expenses?filter=act'
        put('expense_refused', n, url, label=label,
            sub=_('See why, change what is needed, and send it again'),
            icon='receipt', tone='amber', sentence=sentence)

    @api.model
    def _pb_expense_title(self, claim):
        _ = self.env._
        amount = formatLang(self.env, claim.total or 0.0,
                            currency_obj=claim.currency_id)
        n = claim.receipt_count
        if n == 1:
            return _('Expense claim · %s · 1 receipt', amount)
        return _('Expense claim · %(amount)s · %(n)s receipts', amount=amount, n=n)

    @api.model
    def _my_requests_sources(self):
        sources = super()._my_requests_sources()
        _ = self.env._
        sources.append({
            'key': 'expense_claim', 'model': 'pb.expense.claim',
            'label': _('Expenses'), 'icon': 'receipt',
            'employee_field': 'employee_id', 'date_field': 'submitted_on',
            'state_field': 'state',
            'states': {
                'draft': (_('Draft'), 'off'),
                'submitted': (_('Waiting approval'), 'wait'),
                'approved': (_('Approved — being paid'), 'ok'),
                'paid': (_('Paid'), 'ok'),
                'refused': (_('Refused — your turn'), 'act'),
            },
            'url': lambda rec: '/my/expenses/%s' % rec.id,
            'title': self._pb_expense_title,
        })
        return sources

    @api.model
    def get_my_requests(self, emp, bucket=None):
        # "Paid" is read from the expenses: look again before listing
        try:
            with self.env.cr.savepoint():
                if emp and emp.sudo().user_id.id == self.env.uid:
                    self.env['pb.expense.claim'].sudo().search(
                        [('employee_id', '=', emp.id),
                         ('state', '=', 'approved')])._sync_paid()
        except Exception:               # noqa: BLE001 — never blank the page
            _logger.warning('pb_me_expense: paid claims could not be read '
                            'again for My requests', exc_info=True)
        return super().get_my_requests(emp, bucket)
