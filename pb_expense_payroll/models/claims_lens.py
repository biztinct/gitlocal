# -*- coding: utf-8 -*-
"""Expenses › Claims: how each approved claim is paid back.

By inheritance of the list's server side (`pb.expense.claims`, the filter
panel facade) — no file of `pb_expenses_hub` is edited: a filter "How it is
paid", two views ("To pay in the pay run", "Paid in pay"), a short line under
each row's status and, in the panel's layout, whether the reader may change
the company's choice (the "How claims are paid" button)."""
from odoo import _, api, models

PAY_FILTER_ROUTES = (
    ('payrun', 'In the pay run', 'blue',
     [('pb_pay_route', '=', 'payrun')]),
    ('finance', 'By finance', 'slate',
     ['|', ('pb_pay_route', '=', 'finance'), ('pb_pay_route', '=', False)]),
)


class PbExpenseClaimsPay(models.AbstractModel):
    _inherit = 'pb.expense.claims'

    def _pbf_spec(self):
        spec = list(super()._pbf_spec())
        words = {'payrun': _('In the pay run'), 'finance': _('By finance')}
        spec.append({
            'key': 'paid_by', 'label': _('How it is paid'), 'icon': 'wallet',
            'group': 'pay', 'type': 'choice',
            'options': [{'value': key, 'label': words[key], 'tone': tone,
                         'domain': domain}
                        for key, _w, tone, domain in PAY_FILTER_ROUTES]})
        return spec

    def _pbf_builtin_views(self):
        views = list(super()._pbf_builtin_views())
        views.insert(2, {'key': 'pay_run', 'label': _('To pay in the pay run'),
                         'icon': 'banknote',
                         'filters': {'status': ['approved'], 'paid_by': ['payrun']}})
        views.insert(3, {'key': 'paid_in_pay', 'label': _('Paid in pay'),
                         'icon': 'wallet',
                         'filters': {'status': ['paid'], 'paid_by': ['payrun']}})
        return views

    def _pbf_layout_extra(self):
        extra = dict(super()._pbf_layout_extra())
        setup = self.env['pb.expense.pay.setup']
        extra['pb_can_setup'] = setup._pb_can_setup()
        extra['pb_paid_by'] = setup._pb_route_words(
            self.env.company.pb_claims_paid_by or 'finance')
        return extra

    @api.model
    def _row(self, c, words):
        row = super()._row(c, words)
        status = c._pb_pay_status()
        row['pay_note'] = status['staff'] if status else ''
        row['pay_step'] = status['step'] if status else ''
        return row
