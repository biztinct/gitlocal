# -*- coding: utf-8 -*-
"""`/my/pay` — "Your pay, explained".

WHAT A PERSON SEES
------------------
What they are paid, in their own company's money. Where that sits in the range
for their job, in one sentence and one picture, when the company keeps ranges.
What last changed, when, by how much, and why — with the letter to download.
And nothing whatsoever about anybody else.

THE THREE RAILS
---------------
1. **The employee is resolved from the SESSION**, never from a parameter. The
   route takes no employee id and there is nothing to tamper with.
2. **No comparison to another person, ever.** Not an average, not a median, not
   "you are in the top quarter of your team" — a team of four is four people
   who can work the rest out between them.
3. **A company can switch it off** and the page then says so plainly rather
   than showing an empty shell.
"""

import logging

from odoo import _, http
from odoo.http import request
from odoo.tools import format_date
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


class PbPayPortal(CustomerPortal):

    def _ess_employee(self):
        """The OWN employee, resolved from the session user.

        The same helper the rest of the portal uses: prefer the employee
        record in the company the person is standing in, and fall back to any
        record linked to them. `sudo` so the route may read the HR-scoped
        fields of the reader's OWN record and nobody else's.
        """
        Employee = request.env['hr.employee'].sudo()
        found = Employee.search(
            [('user_id', '=', request.env.user.id),
             ('company_id', '=', request.env.company.id)], limit=1)
        return found or Employee.search(
            [('user_id', '=', request.env.user.id)], limit=1)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'pay_change_count' in counters:
            employee = self._ess_employee()
            values['pay_change_count'] = request.env['pb.pay.apply'].sudo(
            ).search_count([('employee_id', '=', employee.id),
                            ('state', '=', 'applied')]) if employee else 0
        return values

    @http.route(['/my/pay'], type='http', auth='user', website=True)
    def portal_my_pay(self, **kw):
        employee = self._ess_employee()
        if not employee:
            return request.redirect('/my')
        company = employee.company_id or request.env.company
        # READ, never create: a settings row written by somebody opening a
        # portal page is a write on a page that has no business making one.
        settings = request.env['pb.pay.settings'].sudo().search(
            [('company_id', '=', company.id)], limit=1)
        enabled = settings.portal_enabled if settings else True
        values = {
            'page_name': 'pay',
            'employee': employee,
            'enabled': bool(enabled),
            'off_note': _(
                "This company does not show pay details here. Your payslips "
                "are still under “Payslips”, and your manager or the people "
                "team can answer anything else."),
        }
        if enabled:
            values.update(self._pay_values(employee, company))
        return request.render('pb_pay.portal_my_pay', values)

    @http.route(['/my/pay/letter/<int:letter_id>'], type='http', auth='user',
                website=True)
    def portal_my_pay_letter(self, letter_id, **kw):
        """The reader's OWN letter, and only ever their own.

        The id in the URL is checked against the letters this person has,
        rather than trusted: a route that reads a record by the number in the
        address bar is a route that hands out everybody's letters to whoever
        can count.
        """
        employee = self._ess_employee()
        if not employee:
            return request.redirect('/my')
        row = request.env['pb.pay.apply'].sudo().search([
            ('employee_id', '=', employee.id),
            ('letter_id', '=', int(letter_id or 0)),
        ], limit=1)
        if not row or not row.letter_id.attachment_id:
            return request.redirect('/my/pay')
        return request.redirect(
            '/web/content/%s?download=true' % row.letter_id.attachment_id.id)

    # ------------------------------------------------------------- the read
    def _pay_values(self, employee, company):
        contract = request.env['hr.contract'].sudo().search(
            [('employee_id', '=', employee.id), ('state', '=', 'open')],
            order='date_start desc, id desc', limit=1)
        currency = company.currency_id
        money = request.env['pb.pay.bands'].sudo()
        position = request.env['pb.pay.position'].sudo().search(
            [('employee_id', '=', employee.id)], limit=1)
        last = request.env['pb.pay.apply'].sudo().latest_for_employee(
            employee.id)

        band_sentence = ''
        band_pct = 0
        if position and position.band_id:
            band_pct = max(0, min(100, int(round(position.position_pct or 0))))
            band_sentence = self._band_sentence(position, money, currency)

        change = {}
        if last:
            rise = float(last.new_wage or 0.0) - float(last.old_wage or 0.0)
            base = float(last.old_wage or 0.0)
            change = {
                'old': money._money(last.old_wage, currency),
                'new': money._money(last.new_wage, currency),
                'pct': '%.1f' % (rise / base * 100.0) if base else '0.0',
                'date': last.effective_date,
                'date_label': format_date(request.env,
                                          last.effective_date) or '',
                'reason': self._reason(last),
                'letter_id': last.letter_id.id if last.letter_id
                and last.letter_id.attachment_id else 0,
            }

        return {
            'contract': contract,
            'has_pay': bool(contract),
            'pay_label': money._money(contract.wage, currency)
            if contract else '',
            'currency_name': currency.name or '',
            'band': position.band_id if position else None,
            'band_pct': band_pct,
            'band_sentence': band_sentence,
            'change': change,
            'no_change_note': _(
                "Nothing has changed your pay through this system yet. When "
                "it does, what changed and why will appear here."),
            'no_pay_note': _(
                "There is no open contract on your record, so there is no "
                "monthly figure to show. The people team can put that right."),
        }

    def _band_sentence(self, position, money, currency):
        band = position.band_id
        pct = float(position.position_pct or 0.0)
        low = money._money(band.min_amount, currency)
        high = money._money(band.max_amount, currency)
        if pct < 0:
            return _("The range for this kind of work runs from %(low)s to "
                     "%(high)s a month. Your pay is below it.",
                     low=low, high=high)
        if pct > 100:
            return _("The range for this kind of work runs from %(low)s to "
                     "%(high)s a month. Your pay is above it.",
                     low=low, high=high)
        return _("The range for this kind of work runs from %(low)s to "
                 "%(high)s a month, and your pay is %(pct)s%% of the way "
                 "through it.", low=low, high=high, pct=int(round(pct)))

    def _reason(self, apply_row):
        """Why it changed, in the words whoever decided it used."""
        if apply_row.review_id:
            return apply_row.review_id.name or _('a pay review')
        if apply_row.change_id:
            change = apply_row.change_id
            return change.reason or dict(
                change._fields['kind'].selection).get(change.kind, '')
        return ''
