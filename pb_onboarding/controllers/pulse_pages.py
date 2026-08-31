# -*- coding: utf-8 -*-
"""One question, five taps, no login.

Modelled on `pb_lifecycle/controllers/token_pages.py`, which is modelled on
`pb_ess_workforce`'s acknowledgement page — the login-less pattern this
codebase trusts:

  * an unguessable token, minted per CHECK, so a leaked link answers one
    question for one person on one day;
  * a GET to look and a POST to answer, and nothing else under the prefix;
  * no data beyond the target record — the joiner's own first name and the
    question, never an id, a department or a neighbouring check;
  * ONE page for every outcome, so a stranger probing the URL space cannot
    tell an unknown link from a used one.

The controller is sudo because the visitor is the public user with no ACL on
anything. The one write behind it touches one record and can only move it
forward.
"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_MAX_COMMENT = 500


class PbOnboardingPulsePages(http.Controller):

    @http.route('/journey/p/<string:token>', type='http', auth='public',
                website=True, sitemap=False)
    def pulse_view(self, token, **kw):
        pulse, status = request.env[
            'pb.newhire.pulse'].sudo()._pulse_for_token(token)
        if kw.get('done') == '1' and status in ('used', 'ok'):
            status = 'thanks'
        return request.render('pb_onboarding.newhire_pulse_page',
                              pulse._page_values(token, status))

    @http.route('/journey/p/<string:token>/submit', type='http',
                auth='public', website=True, methods=['POST'], csrf=False,
                sitemap=False)
    def pulse_submit(self, token, **post):
        """csrf=False for the reason every login-less page here is: the
        visitor has no session to carry a token in. The write is idempotent —
        a replay finds the check already answered and writes nothing."""
        pulse, status = request.env[
            'pb.newhire.pulse'].sudo()._pulse_for_token(token)
        if status == 'ok':
            try:
                pulse.sudo().submit(
                    post.get('score'),
                    (post.get('comment') or '').strip()[:_MAX_COMMENT])
            except Exception:           # noqa: BLE001 — never a 500 on a link
                _logger.exception('pb_onboarding: check submit failed')
        return request.redirect('/journey/p/%s?done=1' % token)
