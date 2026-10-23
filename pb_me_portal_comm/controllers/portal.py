# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`/my/notices` — the company's notices for the person (TIERS T3b D4).

THE ROUTE IS THE GATE (ledger T-R11). The employee is re-resolved from the
SESSION on every request (`_ess_employee`, pb_me_portal); no route accepts an
employee id. A notice reached by id exists for the person only when
pb_hr_comm sent it to them (a delivery row of a sent announcement) — anything
else is a styled 404, never a 500 and never a stock error page. Opening a
notice records the read under sudo after that guard.
"""

from odoo import http
from odoo.http import request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal

#: Notices per page of the board ("Show earlier" adds a page).
NOTICES_PAGE = 30


class PbMeNoticesPortal(PbMePortal):

    def _notices(self):
        return request.env['pb.me.notices']

    # ------------------------------------------------------ home counter
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'notice_count' in counters:
            emp = self._ess_employee()
            values['notice_count'] = self._notices().unread_count(emp) if emp else 0
        return values

    # ------------------------------------------------------------ board
    @http.route(['/my/notices'], type='http', auth='user', website=True)
    def portal_my_notices(self, page=1, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        try:
            page = max(1, min(int(page), 100))
        except (TypeError, ValueError):
            page = 1
        Notices = self._notices()
        counts = Notices.notice_counts(emp)
        rows = Notices.get_my_notices(emp, limit=page * NOTICES_PAGE)
        more_url = None
        if counts['total'] > len(rows):
            more_url = '/my/notices?page=%s' % (page + 1)
        return request.render('pb_me_portal_comm.portal_my_notices', {
            'page_name': 'notices',
            'first': rows[0] if rows else None,
            'rest': rows[1:],
            'counts': counts,
            'more_url': more_url,
        })

    # ------------------------------------------------------- one notice
    @http.route(['/my/notices/<int:post_id>'], type='http', auth='user',
                website=True)
    def portal_my_notice(self, post_id, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        Notices = self._notices()
        notice = Notices.get_my_notice(emp, post_id)
        if not notice:
            return request.render('pb_me_portal_comm.portal_notice_missing',
                                  {'page_name': 'notices'}, status=404)
        was_unread = not notice['read']
        if was_unread:
            Notices.mark_read(emp, post_id)
        return request.render('pb_me_portal_comm.portal_my_notice', {
            'page_name': 'notice',
            'notice': notice,
            'was_unread': was_unread,
        })
