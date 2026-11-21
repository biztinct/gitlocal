# -*- coding: utf-8 -*-
"""/my/expenses also lists the person's trip cash advances (the figure is
seen here before any pay run takes it back). The employee is the session's
own (`_ess_employee`); the rows are read for that employee only."""
from odoo import http
from odoo.http import request

from odoo.addons.pb_me_expense.controllers.portal import PbMeExpensePortal


class PbTripAdvancePortal(PbMeExpensePortal):

    @http.route()
    def portal_my_expenses(self, filter=None, fresh=None, **kw):
        response = super().portal_my_expenses(filter=filter, fresh=fresh, **kw)
        qcontext = getattr(response, 'qcontext', None)
        if qcontext is not None:
            emp = self._ess_employee()
            data = request.env['pb.trip.advance'].my_advances(emp) if emp else None
            qcontext['pb_advances'] = (data or {}).get('rows') or []
        return response
