# -*- coding: utf-8 -*-
"""`/my/privacy` — the company's privacy notice and the person's answer.

THE ROUTE IS THE GATE (ledger T-R11). The person is the session's login; no
route accepts an employee id. The notice answered must be the CURRENT notice
of one of the login's own employee records' companies. Answers are written
under sudo after that check; `sudo()` keeps the uid, so the row names the
login that answered.

`next` is followed only when it is a My Payobook path on this site.
"""

import logging

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal

from ..models.ir_http import SESSION_KEY
from ..models.notice import STAMP_PARAM

_logger = logging.getLogger(__name__)


def _safe_next(target):
    target = (target or '').strip()
    if not target.startswith('/') or target.startswith('//') or '\\' in target:
        return '/my'
    path = target.split('?', 1)[0]
    parts = path.split('/', 2)
    if path == '/my' or path.startswith('/my/'):
        return target
    # a language prefix: /vi/my/...
    if len(parts) > 2 and ('/' + parts[2]).startswith('/my'):
        return target
    return '/my'


class PbMePrivacyPortal(PbMePortal):

    def _pbpv_user(self):
        user = request.env.user
        return user if user and not user._is_public() else None

    def _pbpv_mark_done(self):
        """Nothing left to ask: remember it for this session (against the
        publish stamp, so a new version is asked at once)."""
        stamp = request.env['ir.config_parameter'].sudo().get_param(
            STAMP_PARAM) or '0'
        request.session[SESSION_KEY] = '%s:%s' % (request.session.uid, stamp)

    # ---------------------------------------------------------- the door
    @http.route(['/my/privacy/notice'], type='http', auth='user',
                website=True, methods=['GET'])
    def pbpv_notice(self, next=None, **kw):
        user = self._pbpv_user()
        target = _safe_next(next)
        if not user:
            return request.redirect('/my')
        Consent = request.env['pb.privacy.consent'].sudo()
        notice, employee = Consent._pb_pending(user)
        if not notice:
            self._pbpv_mark_done()
            return request.redirect(target)
        lang = request.env.lang
        values = {
            'page_name': 'privacy_notice',
            'notice': notice.with_context(lang=lang),
            'company': notice.company_id,
            'employee': employee,
            'next': target,
        }
        return request.render('pb_me_privacy.portal_privacy_notice', values)

    @http.route(['/my/privacy/answer'], type='http', auth='user',
                website=True, methods=['POST'])
    def pbpv_answer(self, notice_id=None, answer=None, next=None, **post):
        user = self._pbpv_user()
        target = _safe_next(next)
        if not user:
            return request.redirect('/my')
        Notice = request.env['pb.privacy.notice'].sudo()
        Consent = request.env['pb.privacy.consent'].sudo()
        try:
            notice = Notice.browse(int(notice_id or 0)).exists()
        except (TypeError, ValueError):
            notice = Notice.browse()
        own = Consent._pb_own_employees(user)
        # Only the CURRENT notice of one of the person's own companies.
        if (not notice or notice.state != 'published'
                or notice.company_id not in own.company_id):
            return request.redirect('/my/privacy/notice?next=%s' % target)
        try:
            Consent._pb_record_screen(user, notice, answer,
                                      lang=request.env.lang)
        except (AccessError, UserError):
            _logger.info('pb_me_privacy: an answer was refused for user %s',
                         user.id, exc_info=True)
            return request.redirect('/my/privacy/notice?next=%s' % target)
        pending, _emp = Consent._pb_pending(user)
        if pending:
            return request.redirect('/my/privacy/notice?next=%s' % target)
        self._pbpv_mark_done()
        if target.split('?', 1)[0].rstrip('/').endswith('/my/privacy'):
            return request.redirect('/my/privacy?done=%s' % (
                'agree' if answer == 'agree' else 'disagree'))
        return request.redirect(target)

    # --------------------------------------------------- the person's page
    @http.route(['/my/privacy'], type='http', auth='user', website=True,
                methods=['GET'])
    def pbpv_mine(self, done=None, **kw):
        user = self._pbpv_user()
        if not user:
            return request.redirect('/my')
        Consent = request.env['pb.privacy.consent'].sudo()
        Notice = request.env['pb.privacy.notice'].sudo()
        lang = request.env.lang
        cards = []
        seen = set()
        for emp in Consent._pb_own_employees(user):
            if emp.company_id.id in seen:
                continue
            seen.add(emp.company_id.id)
            notice = Notice._pb_current(emp.company_id)
            if not notice:
                continue
            row = Consent._pb_latest(emp, notice)
            cards.append({
                'company': emp.company_id.name,
                'notice': notice.with_context(lang=lang),
                'status': Consent._pb_status(row),
                'row': row,
            })
        values = {
            'page_name': 'privacy',
            'cards': cards,
            'done': done if done in ('agree', 'disagree') else None,
            'ask_hr_url': '/my/ask-hr/new?category=other'
            if 'pb.ask.hr.ticket' in request.env else None,
        }
        return request.render('pb_me_privacy.portal_my_privacy', values)
