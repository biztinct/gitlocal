# -*- coding: utf-8 -*-
"""NEWHIRE P3b — `/my/welcome`, the page the welcome link lands on
(handover §2.4).

THE ROUTE IS THE GATE (as every `/my` page): the employee is the session's
own (`_ess_employee`); no route takes an employee id, so a person only ever
sees what THEY were asked. Nothing here writes; every card is a link to the
existing My Payobook page that collects that thing (its own form, approval,
masks and file checks). No asks at all → the home.
"""
from odoo import http
from odoo.http import request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal


class PbNewHireWelcomePortal(PbMePortal):

    @http.route(['/my/welcome'], type='http', auth='user', website=True, methods=['GET'])
    def pbnh_welcome(self, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        values = request.env['pb.new.hire.welcome'].sudo().page(emp)
        if not values:
            return request.redirect('/my')
        values['page_name'] = 'my_welcome'
        return request.render('pb_new_hire.portal_my_welcome', values)
