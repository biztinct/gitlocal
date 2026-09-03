# -*- coding: utf-8 -*-
"""FLEET P6 — the door a support session comes through, and the way out of it.

FOUR ROUTES AND NOTHING ELSE.

    /pb_tenancy/support/<token>   the one-time link. Public, because nobody is
                                  logged in yet — that is the whole point of it.
    /pb_tenancy/support/gone      the calm page for a link that did not work and
                                  for a session that has finished.
    /pb_tenancy/support/leave     the Leave button on the bar.
    /pb_tenancy/support/seen      the bar telling us which screen was opened.

THE RATE LIMIT, AND WHY IT IS A DICTIONARY. This server runs ONE process with no
workers (`/etc/odoo-server.conf` has no `workers` line — it is threaded), so a
module-level dict guarded by a lock is a complete and honest rate limiter for
this box, and it costs nothing. It is written here in one place with a comment
saying what would have to change the day a second worker appears: the counter
would have to move somewhere both processes can see. Underneath it sits the
framework's own failed-login cooldown (`res.users._assert_can_auth`), which is
per-database and survives a restart — so a link guessed at from a thousand
addresses is still met by that.
"""
import logging
import threading
import time

from odoo import _, http
from odoo.http import request

from ..models.support import token_digest

_logger = logging.getLogger(__name__)

#: Five tries a minute from one address. A person clicking a link they were
#: sent uses one; anybody who needs six is not a person.
RATE_LIMIT = 5
RATE_WINDOW = 60

_RATE = {}
_RATE_LOCK = threading.Lock()


def _rate_ok(ip):
    """Has this address had its five tries this minute?

    In memory, per process. See the module docstring: one process on this box,
    and the framework's own cooldown underneath.
    """
    now = time.time()
    with _RATE_LOCK:
        hits = [t for t in _RATE.get(ip or '?', []) if now - t < RATE_WINDOW]
        # Housekeeping while we are here, so an idle box does not accumulate a
        # row per address that ever knocked.
        for key in [k for k, v in _RATE.items()
                    if not v or now - v[-1] > RATE_WINDOW * 10]:
            _RATE.pop(key, None)
        if len(hits) >= RATE_LIMIT:
            _RATE[ip or '?'] = hits
            return False
        hits.append(now)
        _RATE[ip or '?'] = hits
        return True


def _entry_path(env):
    """Where a support session lands. `/bizapp` on this build, `/odoo` without it.

    The backend prefix is renamed by `biz_deroute`, which 301s `/odoo` to
    `/bizapp`. Following the redirect would work, but it costs a hop and it puts
    the framework's own word in the address bar of the one session most likely
    to be screenshotted — so the right prefix is chosen here.
    """
    try:
        installed = env['ir.module.module'].sudo().search_count(
            [('name', '=', 'biz_deroute'), ('state', '=', 'installed')])
    except Exception:                                        # noqa: BLE001
        installed = 0
    return '/bizapp' if installed else '/odoo'


class PbTenancySupport(http.Controller):

    # =================================================== the one-time link
    @http.route('/pb_tenancy/support/<string:token>', type='http',
                auth='none', sitemap=False, csrf=False)
    def support_enter(self, token, **kw):
        ip = request.httprequest.environ.get('REMOTE_ADDR') or ''
        if not _rate_ok(ip):
            _logger.warning("pb_tenancy: too many support link attempts from %s", ip)
            return self._gone(_("Too many attempts from this connection. "
                                "Wait a minute and ask for a new link."))
        env = request.env
        login = env['pb.tenancy'].sudo().recovery_login()
        if not login:
            return self._gone(_("This company is not set up for support access."))
        try:
            request.session.authenticate(env, {
                'type': 'pb_support_token', 'login': login, 'token': token,
            })
        except Exception:                                    # noqa: BLE001
            # EVERY failure looks the same from out here, on purpose: a page
            # that distinguishes "expired" from "never existed" tells whoever
            # is knocking which of their guesses was close. The trail on the
            # customer's own page carries the real reason.
            _logger.info("pb_tenancy: a support link was not accepted (from %s)", ip)
            return self._gone()
        row = request.env['pb.support.access'].sudo().search(
            [('token_hash', '=', token_digest(token))], limit=1)
        if row:
            # ON THE SESSION, so every request afterwards knows which session it
            # belongs to without a lookup. It is set AFTER `authenticate`, which
            # rotates the session on its way through `finalize`.
            request.session['pb_support_id'] = row.id
        return request.redirect(_entry_path(request.env), local=True)

    # ======================================================= the calm pages
    def _gone(self, text=None):
        return request.render('pb_tenancy.support_gone_page', {
            'text': text or _("This support link has expired or was already "
                              "used."),
            'finished': False,
        })

    @http.route('/pb_tenancy/support/gone', type='http', auth='none',
                sitemap=False)
    def support_gone(self, **kw):
        return request.render('pb_tenancy.support_gone_page', {
            'text': _("This support session has finished."),
            'finished': True,
        })

    # ============================================================== leaving
    @http.route('/pb_tenancy/support/leave', type='jsonrpc', auth='user')
    def support_leave(self, **kw):
        """The Leave button. Ends the session, then signs out."""
        sid = request.session.get('pb_support_id')
        if sid:
            row = request.env['pb.support.access'].sudo().browse(
                int(sid)).exists()
            if row:
                row.end(_("Payobook support left"))
        request.session.logout(keep_db=True)
        return {'ok': True, 'next': '/pb_tenancy/support/gone'}

    # ==================================================== which screen it was
    @http.route('/pb_tenancy/support/seen', type='jsonrpc', auth='user')
    def support_seen(self, path='', title='', **kw):
        """The bar, saying where it is.

        THE SERVER CANNOT SEE THIS FOR ITSELF. Moving between screens in this
        product changes the address without asking the server for a page, so a
        listener on the request is blind to almost every screen anybody opens.
        The bar is the only thing that knows, and it is the bar the person can
        see while it is doing it.
        """
        sid = request.session.get('pb_support_id')
        if not sid:
            return {'ok': False}
        row = request.env['pb.support.access'].sudo().browse(int(sid)).exists()
        if not row:
            return {'ok': False}
        return {'ok': bool(row.note_route(path, title))}
