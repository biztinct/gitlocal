# -*- coding: utf-8 -*-
"""`/my/compensation` — the page that answers "what am I paid".

THE ROUTE IS THE GATE, exactly as P2–P6 established. The employee is
re-resolved from the SESSION user on every request and no route accepts an
employee id, a package id or an enrollment id, so a crafted URL cannot reach
another person's package. Everything past that point is read under `sudo()` —
the doctrine `pb_me_portal` set — because the record has already been proved to
be the caller's own.

THE PAGE IS SWITCHED OFF IN ONE PARAMETER (`pb_comp_ben.employee_view`), and
switched off it answers a polite redirect to `/my` rather than a 403.

THE VOCABULARY IS THE FEATURE. "Your pay package". Not "compensation
structure", not "CTC", not "snapshot", not "component". The page prints what
somebody gets a month and what that is over a year, and nothing on it needs
explaining.

WHAT IT DOES NOT SHOW: anybody else's package, a package that is not current, an
award that has not been paid, or what the company spends on top. A person's own
page shows what was decided about them, once it was decided.
"""

import logging

from datetime import date

from odoo import _, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

from odoo.addons.pb_comp_ben.models.comp_common import (
    COMP_KIND_LABEL, COMP_KIND_ORDER, P_EMPLOYEE_VIEW, flag,
)

_logger = logging.getLogger(__name__)

#: What each kind is called on the person's own page. The model's labels are
#: written for HR; these are written for the person, and they are not the same
#: words.
MINE_KIND = {
    'earning': 'Your pay',
    'statutory': 'What is taken off by law',
    'benefit': 'Benefits',
    'perquisite': 'Perks',
    'bonus': 'Variable pay',
}

#: How often, said out loud.
MINE_PERIOD = {
    'monthly': 'every month',
    'yearly': 'once a year',
    'one_time': 'one-off',
}


class PbCompBenPortal(CustomerPortal):

    # --------------------------------------------------------------- helpers
    def _comp_enabled(self):
        return flag(request.env, P_EMPLOYEE_VIEW)

    def _comp_employee(self):
        """The OWN employee, from the session user. Never a parameter."""
        Emp = request.env['hr.employee'].sudo()
        emp = Emp.search([('user_id', '=', request.env.user.id),
                          ('company_id', '=', request.env.company.id)],
                         limit=1)
        return emp or Emp.search(
            [('user_id', '=', request.env.user.id)], limit=1)

    def _comp_package(self, emp):
        if not emp:
            return request.env['pb.employee.comp'].browse()
        return request.env['pb.employee.comp'].sudo().search([
            ('employee_id', '=', emp.id), ('state', '=', 'active'),
        ], order='effective_date desc, id desc', limit=1)

    # ------------------------------------------------------------ /my's card
    def _prepare_home_portal_values(self, counters):
        """The counter counts BENEFIT PLANS, because that is the number that
        means something on a card — how many things you are covered by."""
        values = super()._prepare_home_portal_values(counters)
        if 'compensation_count' in counters:
            count = 0
            try:
                if self._comp_enabled():
                    emp = self._comp_employee()
                    if emp:
                        count = request.env['pb.benefit.enrollment'].sudo(
                        ).search_count([('employee_id', '=', emp.id),
                                        ('state', '=', 'active')])
            except Exception:           # noqa: BLE001 — never break /my
                _logger.exception('pb_comp_ben: could not count the benefits')
            values['compensation_count'] = count
        return values

    @http.route()
    def home(self, **kw):
        """`/my` — with one extra key, eagerly computed.

        R62 — portal counters are fetched LAZILY, after the page has rendered,
        so a card gated on `compensation_count` is simply never drawn. The
        question is answered here instead, on EVERY path through, because QWeb
        raises on a name it has never heard of and a missing key would turn a
        hidden card into a 500 for the whole of `/my`.
        """
        response = super().home(**kw)
        if not hasattr(response, 'qcontext'):
            return response
        has_pay = False
        try:
            if self._comp_enabled():
                emp = self._comp_employee()
                has_pay = bool(self._comp_package(emp)) if emp else False
        except Exception:               # noqa: BLE001 — never break /my
            _logger.exception('pb_comp_ben: could not look for a pay package')
        response.qcontext['has_pay_package'] = has_pay
        return response

    # =================================================================
    #  /my/compensation
    # =================================================================
    @http.route(['/my/compensation'], type='http', auth='user', website=True)
    def portal_my_compensation(self, **kw):
        if not self._comp_enabled():
            return request.redirect('/my')
        emp = self._comp_employee()
        if not emp:
            return request.redirect('/my')
        package = self._comp_package(emp)
        values = {
            'page_name': 'compensation',
            'employee': emp,
            'package': package if package else None,
            'currency': (package.currency_id if package
                         else emp.company_id.currency_id),
            'groups': self._package_groups(package) if package else [],
            'benefits': self._benefit_cards(emp),
            'awards': self._award_rows(emp),
            'effective_label': (_friendly(package.effective_date)
                                if package else ''),
        }
        return request.render('pb_comp_ben.portal_my_compensation', values)

    def _package_groups(self, package):
        """The lines, grouped the way a person reads them: pay first."""
        buckets = {}
        for line in package.line_ids:
            buckets.setdefault(line.kind or 'earning', []).append({
                'name': line.name or '',
                'amount': line.amount or 0.0,
                'annual': line.annual_amount or 0.0,
                'period': MINE_PERIOD.get(line.period or 'monthly', ''),
                'note': line.note or '',
            })
        out = []
        for kind in COMP_KIND_ORDER:
            rows = buckets.get(kind)
            if not rows:
                continue
            out.append({
                'kind': kind,
                'label': MINE_KIND.get(kind, COMP_KIND_LABEL.get(kind, kind)),
                'rows': rows,
                'monthly': sum(r['amount'] for r in rows
                               if r['period'] == MINE_PERIOD['monthly']),
                'annual': sum(r['annual'] for r in rows),
            })
        return out

    def _benefit_cards(self, emp):
        rows = request.env['pb.benefit.enrollment'].sudo().search([
            ('employee_id', '=', emp.id), ('state', '=', 'active'),
        ], order='start_date desc, id desc')
        cards = []
        for row in rows:
            plan = row.plan_id
            cards.append({
                'plan': plan.name or '',
                'kind': plan.kind or '',
                'provider': plan.provider_name or '',
                'url': (plan.provider_url or '').strip(),
                'coverage': plan.coverage_html or '',
                'member_ref': row.member_ref or '',
                'from_label': _friendly(row.start_date),
                'family': row.dependants(),
            })
        return cards

    def _award_rows(self, emp):
        """Awards that have actually been PAID. An award still being decided is
        not something to put in front of the person it is about."""
        rows = request.env['pb.incentive'].sudo().search([
            ('employee_id', '=', emp.id), ('fulfilment', '=', 'paid'),
        ], order='period_month desc, id desc', limit=24)
        out = []
        for rec in rows:
            out.append({
                'id': rec.id,
                'kind': rec.kind or '',
                'amount': rec.amount or 0.0,
                'currency': rec.currency_id,
                'month': (rec.period_month.strftime('%B %Y')
                          if rec.period_month else ''),
                'reason': rec.reason or '',
                'has_letter': bool(rec.letter_id and rec.letter_id.attachment_id),
            })
        return out

    # ---------------------------------------------------------- the letter
    @http.route(['/my/compensation/letter/<int:award_id>'], type='http',
                auth='user', website=True)
    def portal_award_letter(self, award_id, **kw):
        """The person's own copy of an award letter.

        NOT `/web/content/<id>` — a portal user has no access to the attachment,
        and handing them a link that 403s is worse than not offering it. The
        route proves the award is theirs and then streams the file it already
        knows the id of.
        """
        if not self._comp_enabled():
            return request.redirect('/my')
        emp = self._comp_employee()
        if not emp:
            return request.redirect('/my')
        award = request.env['pb.incentive'].sudo().browse(
            int(award_id or 0)).exists()
        # THE OWNERSHIP TEST IS THE GATE, and it is checked on the record the
        # route fetched rather than on anything the caller sent.
        if not award or award.employee_id.id != emp.id \
                or award.fulfilment != 'paid':
            return request.redirect('/my/compensation')
        attachment = award.letter_id.attachment_id if award.letter_id else None
        if not attachment:
            return request.redirect('/my/compensation')
        try:
            return request.env['ir.binary']._get_stream_from(
                attachment.sudo(), 'raw').get_response(as_attachment=True)
        except Exception:               # noqa: BLE001
            _logger.exception('pb_comp_ben: could not serve the letter for '
                              'award %s', award.id)
            return request.redirect('/my/compensation')


def _friendly(day):
    """"1 September" — or "1 September 2027" when it is not this year.

    Written out rather than passed through `format_date`, so the answer is the
    same on the page and in the sentence beside it.
    """
    if not day:
        return ''
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
              'August', 'September', 'October', 'November', 'December']
    same_year = day.year == date.today().year
    return '%s %s%s' % (day.day, months[day.month - 1],
                        '' if same_year else ' %s' % day.year)
