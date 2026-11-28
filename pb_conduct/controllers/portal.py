# -*- coding: utf-8 -*-
"""`/my/letters` — the employee's own finished letters from HR.

THE ROUTE IS THE GATE. The employee comes from the SESSION (`_ess_employee`)
on every request; a letter reached by id is served only when it is ISSUED and
addressed to one of the session user's own employee records. Draft letters,
the case, its notes, its hearing minutes and its files never reach this page.
Employee logins (mostly portal) hold no access right on any conduct model.

Plain words on purpose: no "disciplinary", no "warning" in the page chrome —
the letter's own title says what it is.
"""
import logging

from odoo import http
from odoo.http import content_disposition, request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal

_logger = logging.getLogger(__name__)


class PbConductPortal(PbMePortal):

    def _conduct_own(self):
        """Every employee record of the session user (one per company)."""
        try:
            return self._ess_own_employees()
        except Exception:       # noqa: BLE001
            emp = self._ess_employee()
            return emp

    @http.route()
    def home(self, **kw):
        response = super().home(**kw)
        if not hasattr(response, 'qcontext'):
            return response
        has = False
        try:
            has = bool(request.env['pb.conduct.letter']._mine(self._conduct_own()))
        except Exception:       # noqa: BLE001 — never break /my
            _logger.warning('pb_conduct: could not look for letters', exc_info=True)
        response.qcontext['has_hr_letters'] = has
        return response

    @http.route(['/my/letters'], type='http', auth='user', website=True,
                sitemap=False)
    def portal_my_letters(self, **kw):
        emps = self._conduct_own()
        data = {'letters': [], 'unread': 0}
        if emps:
            try:
                data = request.env['pb.conduct.letter'].my_letters(emps)
            except Exception:   # noqa: BLE001 — never a 500 on /my
                _logger.warning('pb_conduct: My letters failed', exc_info=True)
        values = {
            'page_name': 'my_hr_letters',
            'pbc': data,
            'pbc_linked': bool(emps),
            'pbc_done': kw.get('done') or '',
            'pbc_error': kw.get('error') or '',
        }
        return request.render('pb_conduct.portal_my_letters', values)

    @http.route(['/my/letters/<int:letter_id>/read'], type='http', auth='user',
                methods=['POST'], website=True, sitemap=False)
    def portal_letter_read(self, letter_id, **kw):
        ok = request.env['pb.conduct.letter'].mark_read(self._conduct_own(), letter_id)
        return request.redirect('/my/letters?done=read' if ok else '/my/letters')

    @http.route(['/my/letters/<int:letter_id>/reply'], type='http', auth='user',
                methods=['POST'], website=True, sitemap=False)
    def portal_letter_reply(self, letter_id, reply=None, **kw):
        res = request.env['pb.conduct.letter'].send_reply(
            self._conduct_own(), letter_id, reply)
        if res.get('ok'):
            return request.redirect('/my/letters?done=reply')
        return request.redirect('/my/letters?error=reply')

    @http.route(['/my/letters/<int:letter_id>/pdf'], type='http', auth='user',
                website=True, sitemap=False)
    def portal_letter_pdf(self, letter_id, **kw):
        letter = request.env['pb.conduct.letter']._own_letter(
            self._conduct_own(), letter_id)
        if not letter or not letter.attachment_id:
            return request.not_found()
        att = letter.attachment_id.sudo()
        content = att.raw or b''
        name = (att.name or 'letter.pdf').replace('"', '')
        return request.make_response(content, headers=[
            ('Content-Type', att.mimetype or 'application/pdf'),
            ('Content-Disposition', content_disposition(name)),
            ('Cache-Control', 'no-store'),
        ])
