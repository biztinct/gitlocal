# -*- coding: utf-8 -*-
"""`/my/goals/review/<id>` — the employee's own review form on My Payobook.

THE ROUTE PROVES NOTHING ITSELF AND TRUSTS NOTHING: the review id in the
address is checked by `pb.review.forms._own_review` (the review's employee
must be the session user) before anything is read or written, so another
person's id answers the same refusal as an id that does not exist. No route
takes an employee id.

EVERY PRIVATE HELPER CARRIES `_rf_` (pb_goals R186): all `CustomerPortal`
subclasses merge into one class, and a helper name shared with another module
silently loses to whichever loads last.
"""

import logging

from odoo import _, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


class PbReviewFormsPortal(CustomerPortal):

    def _rf_facade(self):
        return request.env['pb.review.forms']

    def _rf_back(self, review_id, ok=None, flash=None):
        if flash:
            request.session['pb_rf_flash'] = str(flash)[:400]
        url = '/my/goals/review/%s' % int(review_id or 0)
        if ok:
            url += '?ok=%s' % ok
        return request.redirect(url)

    def _rf_notice(self, key):
        return {
            'saved': _("Saved. Your manager sees nothing until you send it."),
            'sent': _("Sent to your manager. They write their part next."),
            'read': _("Thank you. It is marked as read."),
            'talk': _("Your HR team has been asked to talk with you."),
        }.get(key or '', '')

    @staticmethod
    def _rf_answers(post):
        out = {}
        for key, value in post.items():
            if key.startswith('a_'):
                out[key[2:]] = value
        return out

    def _prepare_portal_layout_values(self):
        """The eager key the home entry is drawn on (pb_goals R62): a counter
        is fetched after the page renders, so a conditional entry needs a
        value computed now. Never lets /my fail over this module."""
        values = super()._prepare_portal_layout_values()
        try:
            values['pb_rf_has'] = bool(self._rf_facade().my_current_review())
        except Exception:               # noqa: BLE001 — /my never 500s over us
            values['pb_rf_has'] = False
        return values

    # ================================================================ page
    @http.route(['/my/review'], type='http', auth='user', website=True,
                sitemap=False)
    def portal_rf_current(self, **kw):
        """The home tile's stable door: this year's review, or My goals."""
        review_id = self._rf_facade().my_current_review()
        if not review_id:
            return request.redirect('/my/goals')
        return request.redirect('/my/goals/review/%s' % review_id)

    @http.route(['/my/goals/review/<int:review_id>'], type='http',
                auth='user', website=True, sitemap=False)
    def portal_rf_page(self, review_id, **kw):
        try:
            data = self._rf_facade().my_form(review_id)
        except (AccessError, UserError) as err:
            request.session['pb_goals_flash'] = str(
                err.args[0] if err.args else '')[:400]
            return request.redirect('/my/goals')
        if not data.get('ok'):
            request.session['pb_goals_flash'] = data.get('why') or ''
            return request.redirect('/my/goals')
        return request.render('pb_review_forms.portal_review_form', {
            'page_name': 'goals',
            'rf': data,
            'notice': self._rf_notice(kw.get('ok')),
            'problem': request.session.pop('pb_rf_flash', ''),
        })

    @http.route(['/my/goals/review/<int:review_id>/save'], type='http',
                auth='user', website=True, methods=['POST'], sitemap=False)
    def portal_rf_save(self, review_id, **post):
        send = post.get('do') == 'send'
        try:
            self._rf_facade().my_save(review_id, self._rf_answers(post),
                                      send=send)
        except (AccessError, UserError) as err:
            return self._rf_back(review_id, flash=err.args[0]
                                 if err.args else '')
        except Exception:               # noqa: BLE001 — never a 500 on a form
            _logger.exception('pb_review_forms: saving a review failed')
            return self._rf_back(review_id, flash=_(
                "That did not save. Try again, and tell your HR team if it "
                "keeps happening."))
        return self._rf_back(review_id, ok='sent' if send else 'saved')

    @http.route(['/my/goals/review/<int:review_id>/ack'], type='http',
                auth='user', website=True, methods=['POST'], sitemap=False)
    def portal_rf_ack(self, review_id, **post):
        kind = 'talk' if post.get('kind') == 'talk' else 'read'
        try:
            answer = self._rf_facade().my_ack(review_id, kind)
        except (AccessError, UserError) as err:
            return self._rf_back(review_id, flash=err.args[0]
                                 if err.args else '')
        if kind == 'talk' and answer.get('ticket_id'):
            return request.redirect('/my/ask-hr/%s' % answer['ticket_id'])
        return self._rf_back(review_id, ok=kind)

    @http.route(['/my/goals/review/<int:review_id>/pdf'], type='http',
                auth='user', website=True, sitemap=False)
    def portal_rf_pdf(self, review_id, **kw):
        """The person's own copy. Not `/web/content/<id>`: a portal login
        holds no right on the attachment, so the route proves the review is
        theirs and streams the file it already knows."""
        try:
            attachment = self._rf_facade().my_pdf(review_id)
        except (AccessError, UserError):
            attachment = False
        if not attachment:
            return request.redirect('/my/goals/review/%s' % int(review_id))
        return request.env['ir.binary']._get_stream_from(
            attachment, 'raw').get_response(as_attachment=True)

    # ============================================================= preview
    @http.route(['/my/goals/review-form/<int:form_id>/preview'], type='http',
                auth='user', website=True, sitemap=False)
    def portal_rf_preview(self, form_id, **kw):
        """HR's "Preview as the employee". Nothing on it is saved."""
        try:
            data = self._rf_facade().preview(form_id)
        except (AccessError, UserError):
            return request.redirect('/my')
        return request.render('pb_review_forms.portal_review_form', {
            'page_name': 'goals',
            'rf': data,
            'notice': '',
            'problem': '',
        })
