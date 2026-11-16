# -*- coding: utf-8 -*-
""""How claims are paid" — the company's choice, in one small form.

Opened from Expenses › Claims. Only an expense manager, a payroll manager or
an administrator may change it. Changing it moves no claim already approved
(each claim keeps the route it was approved with), and the form says so with
the numbers."""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.misc import format_datetime, formatLang

from .common import PAY_ROUTES

SETUP_GROUPS = ('hr_expense.group_hr_expense_manager',
                'pb_hr_payroll_base.group_payroll_base_manager',
                'om_hr_payroll.group_hr_payroll_manager')


class PbExpensePaySetup(models.TransientModel):
    _name = 'pb.expense.pay.setup'
    _description = 'How approved expense claims are paid back'

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 readonly=True, default=lambda self: self.env.company)
    paid_by = fields.Selection(PAY_ROUTES, string='Approved claims are paid',
                               required=True,
                               default=lambda self: self.env.company.pb_claims_paid_by
                               or 'finance')
    changed_words = fields.Char(compute='_compute_words')
    waiting_words = fields.Char(compute='_compute_words')

    # ------------------------------------------------------------ rights
    @api.model
    def _pb_can_setup(self):
        user = self.env.user
        if user._is_admin():
            return True
        for xmlid in SETUP_GROUPS:
            if self.env.ref(xmlid, raise_if_not_found=False) and user.has_group(xmlid):
                return True
        return False

    @api.model
    def _pb_route_words(self, route):
        return {'finance': _('By finance'),
                'payrun': _('In the next pay run')}.get(route, _('By finance'))

    @api.depends('company_id')
    def _compute_words(self):
        Claim = self.env['pb.expense.claim'].sudo()
        for rec in self:
            company = rec.company_id.sudo()
            if company.pb_claims_paid_by_changed_by:
                rec.changed_words = _(
                    "Last changed by %(who)s on %(when)s.",
                    who=company.pb_claims_paid_by_changed_by.name or '',
                    when=format_datetime(self.env, company.pb_claims_paid_by_changed_on,
                                         dt_format='d MMM yyyy'))
            elif (company.pb_claims_paid_by or 'finance') == 'finance':
                rec.changed_words = _("Not changed yet: finance pays claims back, as "
                                      "it always has.")
            else:
                rec.changed_words = ''
            waiting = Claim.search([('company_id', '=', company.id),
                                    ('state', '=', 'approved'),
                                    ('pb_pay_route', '=', 'payrun')])
            total = formatLang(self.env, sum(c._pb_payable_amount() for c in waiting),
                               currency_obj=company.currency_id) if waiting else ''
            if len(waiting) == 1:
                rec.waiting_words = _(
                    "1 approved claim (%s) is already set to be paid in the pay run. "
                    "It stays that way whatever you choose here.", total)
            elif waiting:
                rec.waiting_words = _(
                    "%(n)s approved claims (%(total)s) are already set to be paid in "
                    "the pay run. They stay that way whatever you choose here.",
                    n=len(waiting), total=total)
            else:
                rec.waiting_words = ''

    # ------------------------------------------------------------ save
    def action_save(self):
        self.ensure_one()
        if not self._pb_can_setup():
            raise AccessError(_("Only an expense manager or a payroll manager can "
                                "choose how claims are paid."))
        company = self.company_id
        if company not in self.env.user.company_ids:
            raise AccessError(_("You do not work for %s.", company.name))
        if company.pb_claims_paid_by != self.paid_by:
            company.sudo().write({
                'pb_claims_paid_by': self.paid_by,
                'pb_claims_paid_by_changed_by': self.env.uid,
                'pb_claims_paid_by_changed_on': fields.Datetime.now(),
            })
        return {'type': 'ir.actions.act_window_close'}
