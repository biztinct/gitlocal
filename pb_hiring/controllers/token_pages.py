# -*- coding: utf-8 -*-
"""`/hiring/f/<token>` — the one page in this module with no login behind it.

THE LINK IS THE CREDENTIAL, exactly as `pb_lifecycle`'s two token pages
established and `pb_ess_workforce`'s acknowledgment page before them:

  * an unguessable key — 24 bytes of `secrets.token_urlsafe`, minted per
    OPINION, so a leaked link answers one question about one hour for one
    person;
  * single-purpose routes — a GET to look and a POST to answer, and nothing
    else lives under the prefix;
  * no data beyond the target — the candidate's name, the role, the round and
    the questions. Not an id, not a salary expectation, not what anybody else
    on the panel said, not a link into the backend;
  * ONE page for every outcome, so a stranger probing the URL space learns
    nothing: an unknown key, a finished one and a called-off interview all get
    the same courteous "this link has closed".

The controller is sudo because the visitor is the public user with no access
to anything. Every write behind it goes through the model's own `submit`,
touches one record, and can only move that record forward.
"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

#: A public form must never be usable to post a book.
_MAX_NOTES = 4000


class PbHiringTokenPages(http.Controller):

    def _page(self, token, row, status):
        return request.render('pb_hiring.hiring_feedback_page', {
            'status': status,
            # Echoed back so the form posts to the same key — never
            # re-derived from the record, whose token is a restricted field.
            'token': token,
            # NOT `request`: QWeb already has one, and ours would shadow the
            # HTTP request the layout itself reads — the page then dies with
            # "'Request' object is not subscriptable" and the visitor gets a
            # 500 instead of a form (R4).
            'facts': row.page_facts() if (row and status == 'ok') else {},
            'questions': row.questions() if (row and status == 'ok') else [],
        })

    @http.route('/hiring/f/<string:token>', type='http', auth='public',
                website=True, sitemap=False)
    def hiring_feedback_view(self, token, **kw):
        row, status = request.env[
            'pb.hiring.feedback'].sudo()._request_for_token(token)
        if kw.get('done') == '1' and status in ('used', 'ok'):
            status = 'thanks'
        return self._page(token, row, status)

    @http.route('/hiring/f/<string:token>/submit', type='http',
                auth='public', website=True, methods=['POST'], csrf=False,
                sitemap=False)
    def hiring_feedback_submit(self, token, **post):
        """`csrf=False` for the reason every token page in this product has
        it: the visitor has no session to carry a token in. The write is
        idempotent — a replay finds the opinion already given and writes
        nothing."""
        row, status = request.env[
            'pb.hiring.feedback'].sudo()._request_for_token(token)
        if status == 'ok':
            try:
                ratings = []
                for question in row.questions():
                    raw = post.get('c_%s' % question['id'])
                    if raw:
                        ratings.append({'id': question['id'], 'score': raw})
                row.sudo().submit(
                    ratings,
                    recommendation=post.get('recommendation'),
                    notes=(post.get('notes') or '').strip()[:_MAX_NOTES])
            except Exception:           # noqa: BLE001 — never a traceback
                _logger.exception('pb_hiring: a feedback submit failed')
        return request.redirect('/hiring/f/%s?done=1' % token)
