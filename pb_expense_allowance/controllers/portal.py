# -*- coding: utf-8 -*-
"""/my/expenses shows the person's own yearly limits (limit, used, left).
The employee is the session's own (`_ess_employee`)."""
from odoo import http
from odoo.http import request

from odoo.addons.pb_me_expense.controllers.portal import PbMeExpensePortal


class PbExpenseAllowancePortal(PbMeExpensePortal):

    @http.route()
    def portal_my_expenses(self, filter=None, fresh=None, **kw):
        response = super().portal_my_expenses(filter=filter, fresh=fresh, **kw)
        qcontext = getattr(response, 'qcontext', None)
        if qcontext is not None:
            emp = self._ess_employee()
            qcontext['pb_limits'] = request.env['pb.expense.allowance'].my_limits(emp) \
                if emp else []
        return response
