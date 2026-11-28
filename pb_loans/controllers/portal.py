# -*- coding: utf-8 -*-
"""`/my/loans` — what I borrowed, what is left, what comes off next (read-only).

THE ROUTE IS THE GATE: the employee is re-resolved from the SESSION on every
request (`_ess_employee`, pb_me_portal); no route accepts an employee id, and
`pb.loan.my_loans` refuses any employee that is not the caller's own. Employee
logins hold no right on `pb.loan` at all.
"""
import logging

from odoo import http
from odoo.http import request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal

_logger = logging.getLogger(__name__)


class PbLoansPortal(PbMePortal):

    @http.route(['/my/loans'], type='http', auth='user', website=True,
                sitemap=False)
    def portal_my_loans(self, **kw):
        emp = self._ess_employee()
        data = None
        if emp:
            try:
                data = request.env['pb.loan'].my_loans(emp)
            except Exception:       # noqa: BLE001 — never a 500 on /my
                _logger.warning('pb_loans: My loans failed', exc_info=True)
                data = None
        values = {
            'page_name': 'my_loans',
            'pbl': data or {'loans': [], 'left_label': '', 'next_label': '',
                            'any_open': False, 'count': 0},
            'pbl_linked': bool(emp),
        }
        return request.render('pb_loans.portal_my_loans', values)
