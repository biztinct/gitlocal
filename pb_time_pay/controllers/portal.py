# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`/my/work/late` — the person's own decided late and early minutes
(WDGAP S5-F, owner ruling TP3).

A page of its own, linked from My Overtime, so neither `pb_me_portal` nor
`pb_ess_workforce` is edited. Like every My Work route it reads no identity
from the request: the facade resolves the employee from the session user
(C18.26), so a forged parameter has nothing to land on.
"""

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request


class PbTimePayPortal(http.Controller):

    @http.route(['/my/work/late'], type='http', auth='user', website=True)
    def portal_my_work_late(self, **kw):
        try:
            data = request.env['pb.ess.workforce'].get_my_late_minutes()
        except UserError:
            return request.render('pb_ess_workforce.portal_work_no_employee',
                                  {'page_name': 'work_overtime'})
        return request.render('pb_time_pay.portal_my_work_late', {
            'page_name': 'work_overtime',
            'late': data,
            'flash': '',
        })
