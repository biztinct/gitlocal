# -*- coding: utf-8 -*-
"""Where the yearly limit is checked, and what approvers see.

* At each receipt (`pb.me.expense.check_receipt`) and when the claim is sent
  (`pb.me.expense.send`, the whole claim per kind of expense and year): over
  what is left → refused with "limit, used, left" — unless the company allows
  going over, in which case the claim is sent and its approvers see it is
  over (a route fact `over_yearly_limit` and a chip with the numbers).
* The company switch sits on the "How claims are paid" form.
"""
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.pb_me_expense.models.me_expense import ExpenseRefusal


def _over_rows(env, claim):
    """[(product, year, facts, asked)] for the kinds of expense in this claim
    that would go over their yearly limit."""
    claim = claim.sudo()
    Allow = env['pb.expense.allowance']
    groups = defaultdict(float)
    for exp in claim.expense_ids:
        if exp.product_id and exp.date:
            groups[(exp.product_id, exp.date.year)] += exp.total_amount_currency or 0.0
    out = []
    for (product, year), asked in groups.items():
        facts = Allow.facts_for(claim.employee_id, product, year, skip_claim=claim)
        if facts and facts['currency'].compare_amounts(asked, facts['left']) > 0:
            out.append((product, year, facts, asked))
    return out


class ResCompanyAllowance(models.Model):
    _inherit = 'res.company'

    pb_expense_allow_over = fields.Boolean(
        string='Claims may go over the yearly limit',
        help='Off: a claim over what is left of a yearly limit is refused, with '
             'the numbers. On: it is sent, and its approvers see it is over.')


class PbMeExpenseAllowance(models.AbstractModel):
    _inherit = 'pb.me.expense'

    @api.model
    def check_receipt(self, emp, receipt, amount, product_id, date=None, trip_id=None):
        clean = super().check_receipt(emp, receipt, amount, product_id, date, trip_id)
        emp = self._own_employee(emp)
        if emp.company_id.pb_expense_allow_over:
            return clean
        Allow = self.env['pb.expense.allowance']
        facts = Allow.facts_for(emp, clean['product'], clean['date'].year)
        if facts and facts['currency'].compare_amounts(clean['amount'], facts['left']) > 0:
            raise ExpenseRefusal('allowance', Allow.refusal(clean['product'], facts,
                                                             clean['amount']))
        return clean

    @api.model
    def send(self, claim):
        own = self._own_claim(claim)
        if own.state == 'draft' and not own.company_id.pb_expense_allow_over:
            over = _over_rows(self.env, own)
            if over:
                product, _year, facts, asked = over[0]
                raise ExpenseRefusal('allowance', self.env['pb.expense.allowance'].refusal(
                    product, facts, asked))
        return super().send(claim)


class PbExpenseClaimAllowance(models.Model):
    _inherit = 'pb.expense.claim'

    def _chain_facts(self):
        facts = dict(super()._chain_facts())
        facts['over_yearly_limit'] = {'value': bool(_over_rows(self.env, self)), 'unit': ''}
        return facts

    @api.model
    def _chain_fact_specs(self):
        specs = dict(super()._chain_fact_specs())
        specs['over_yearly_limit'] = {'type': 'bool',
                                      'label': _('Over a yearly limit')}
        return specs

    def _approval_detail(self, request):
        detail = super()._approval_detail(request)
        try:
            over = _over_rows(self.env, self)
        except Exception:       # noqa: BLE001 — a chip never breaks the inbox
            over = []
        if over and isinstance(detail, dict):
            Allow = self.env['pb.expense.allowance']
            for product, year, facts, asked in over[:3]:
                m = lambda v, f=facts: Allow.money(v, f['currency'])   # noqa: E731
                detail.setdefault('chips', []).append({
                    'label': _('Over the yearly limit'),
                    'value': _("%(what)s %(year)s: limit %(limit)s, used %(used)s, left "
                               "%(left)s, this claim %(asked)s", what=product.name or '',
                               year=year, limit=m(facts['limit']),
                               used=m(facts['used'] + facts['waiting']),
                               left=m(facts['left']), asked=m(asked))})
        return detail


class PbExpensePaySetupAllowance(models.TransientModel):
    _inherit = 'pb.expense.pay.setup'

    allow_over = fields.Boolean(
        string='Claims may go over the yearly limit',
        default=lambda self: self.env.company.pb_expense_allow_over)

    def action_save(self):
        res = super().action_save()
        company = self.company_id
        if company.pb_expense_allow_over != self.allow_over:
            company.sudo().pb_expense_allow_over = self.allow_over
        return res

    def action_open_limits(self):
        self.ensure_one()
        if not self._pb_can_setup():
            raise AccessError(_("Only an expense manager or a payroll manager can set "
                                "yearly limits."))
        return self.env['ir.actions.act_window']._for_xml_id(
            'pb_expense_allowance.action_pb_expense_allowance')
