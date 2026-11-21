# -*- coding: utf-8 -*-
"""Home › Policies: the questions people asked (no names) as an Excel file.

HR only (`pb.policy.desk` gate), for a company the reader belongs to, and
only where the company is big enough for questions to be shown at all (PA1:
under five people who could ask, the list and the file are empty)."""
from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request


class PbMePayaiDownload(http.Controller):

    @http.route(['/pb_me_payai/questions.xlsx'], type='http', auth='user',
                methods=['GET'])
    def pbpa_questions_xlsx(self, company_id=None, which='not_answered', **kw):
        user = request.env.user
        try:
            cid = int(company_id or user.company_id.id)
        except (TypeError, ValueError):
            cid = user.company_id.id
        if cid not in user.company_ids.ids:
            return request.not_found()
        env = request.env(context=dict(request.env.context, allowed_company_ids=[cid]))
        Desk = env['pb.policy.desk']
        if not Desk.can_open():
            raise AccessError(env._("Only the HR team manages company policies."))
        company = env['res.company'].browse(cid)
        if not env['pb.policy.answer']._questions_shown(company):
            return request.not_found()
        data = Desk._questions_xlsx(company, which if which in (
            'not_answered', 'answered', 'all') else 'not_answered')
        name = 'policy-questions.xlsx'
        return request.make_response(data, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', 'attachment; filename="%s"' % name),
            ('Cache-Control', 'no-store'),
        ])
