# -*- coding: utf-8 -*-
"""The platform's message rides in with the page, not after it.

WHY NOT JUST CALL THE SERVER FROM THE BROWSER. Because then the top of every
page would be empty for the length of a round trip and the banner would drop in
a beat late — on every navigation, for every user, forever. A maintenance
warning that arrives after the reader has started typing is a worse warning
than none. So the state travels in `session_info`, which the page already
carries, and the banner is drawn on the first paint with no request of its own.

The 60-second poll (`/pb_tenancy/state`) exists for the OTHER case: a tab that
has been open for an hour when the platform sends something.
"""
import logging

import psycopg2
import werkzeug.exceptions

from odoo import _, fields, models
from odoo.exceptions import AccessDenied
from odoo.http import request

_logger = logging.getLogger(__name__)

#: WHERE THE PAUSED DOOR IS NOT. Everything a paused database still has to be
#: able to serve:
#:
#:   * the paused page itself, or the redirect would loop for ever;
#:   * the login and logout pages, so the platform's recovery account can get
#:     in and so the person who was redirected can sign out;
#:   * the assets and images the paused page is drawn from;
#:   * `/pb_tenancy/state`, which is how an ALREADY OPEN tab finds out it has
#:     been paused and takes itself to the page. Without it a paused customer
#:     would carry on working in the tab they had open until they navigated.
#:
#: Prefix matching, and the list is deliberately short: anything not on it is
#: shut.
OPEN_PREFIXES = (
    '/pb_tenancy/',
    '/web/login',
    '/web/session/logout',
    '/web/session/destroy',
    '/web/reset_password',
    '/web/assets',
    '/web/static',
    '/web/image',
    '/web/binary',
    '/web/health',
    '/websocket',
    '/longpolling',
    '/favicon.ico',
)


#: FLEET P6. Where the support clock is NOT read, for the same reason as
#: OPEN_PREFIXES above: the page that says the session has finished, the way
#: out, and the assets both are drawn from must all still be served to somebody
#: whose session has just ended, or they meet a redirect loop instead of a
#: sentence.
SUPPORT_OPEN_PREFIXES = (
    '/pb_tenancy/support/',
    '/web/session/logout',
    '/web/session/destroy',
    '/web/assets',
    '/web/static',
    '/favicon.ico',
)

#: The two addresses a SCREEN lives at on this build: the backend prefix
#: (`/bizapp`, renamed by `biz_deroute`) and the one it replaced. Everything
#: else a page load asks for is machinery.
SCREEN_PREFIXES = ('/bizapp', '/odoo')


def _is_screen(path):
    """Is this address a screen somebody opened, or a piece of a page? PURE."""
    for prefix in SCREEN_PREFIXES:
        if path == prefix or path.startswith(prefix + '/'):
            return True
    return False


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    # ================================================== FLEET P5 — the door
    @classmethod
    def _pre_dispatch(cls, rule, args):
        super()._pre_dispatch(rule, args)
        try:
            cls._pb_paused_door(rule)
        except (werkzeug.exceptions.HTTPException, AccessDenied):
            raise
        except Exception as exc:                             # noqa: BLE001
            # FAIL OPEN, ALWAYS. A broken settings row, a half-installed
            # module, a database with no `pb.tenancy` yet — none of those may
            # be allowed to shut a payroll office out of its own data. The
            # only thing that closes this door is the platform saying so.
            #
            # THE REASON IS IN THE MESSAGE, not only in the traceback: this is
            # the one place where a silent failure means an open door, and the
            # line has to be greppable on a live box.
            _logger.warning("pb_tenancy: could not read the access state (%r); "
                            "letting the request through", exc, exc_info=True)
        try:
            cls._pb_support_clock(rule)
        except (werkzeug.exceptions.HTTPException,
                psycopg2.errors.ReadOnlySqlTransaction):
            # THE READ-ONLY ERROR IS DELIBERATELY LET OUT. Most pages in this
            # product are served on a read-only cursor (a route declared
            # `auth='none'` is read-only by default on this framework), and both
            # things this method does are writes. The framework's own answer to
            # that is to run the request again on a read/write cursor
            # (`odoo/http.py:2274`), which is exactly what should happen — so
            # catching it here would silently lose the end of a session.
            raise
        except Exception as exc:                             # noqa: BLE001
            # FAILS CLOSED IN SPIRIT, OPEN IN PRACTICE, and the difference is
            # worth being clear about. If this check breaks, a support session
            # runs past its finish time until somebody signs it out — it does
            # not let ANYBODY IN who was not already in, because getting in is
            # the login seam's job and that fails closed. The reason goes in the
            # line, not only the traceback (the lesson of ledger F53).
            _logger.warning("pb_tenancy: could not read the support session "
                            "(%r); the session is left running", exc,
                            exc_info=True)

    # ============================================ FLEET P6 — the support clock
    @classmethod
    def _pb_support_clock(cls, rule):
        """End a support session that is over, and remember the screens opened.

        COSTS NOTHING FOR ANYBODY ELSE. The whole method is behind one lookup in
        the session dictionary, which is already in memory: a person doing their
        payroll has no `pb_support_id` on their session and leaves at the first
        line. Only the one account that came through the support door pays for
        the row read.
        """
        if not request:
            return
        sid = request.session.get('pb_support_id')
        if not sid:
            return
        path = request.httprequest.path or ''
        if path.startswith(SUPPORT_OPEN_PREFIXES):
            return
        env = request.env
        if 'pb.support.access' not in env:
            return
        row = env['pb.support.access'].sudo().browse(int(sid)).exists()
        if not row:
            return
        now = fields.Datetime.now()
        over = (row.state != 'active'
                or (row.session_expires_at and row.session_expires_at <= now))
        if over:
            if row.state == 'active':
                row.expire()
            # SIGNED OUT, NOT MERELY REDIRECTED. A session that is over has to
            # stop being a session; leaving the cookie alive and only sending
            # the page somewhere else would leave every RPC call still answering.
            request.session.logout(keep_db=True)
            if (rule.endpoint.routing.get('type') or 'http') == 'http':
                werkzeug.exceptions.abort(
                    request.redirect('/pb_tenancy/support/gone'))
            raise AccessDenied(_("This support session has finished."))
        # A BACKSTOP, NOT THE RECORD. Moving between screens in this product
        # changes the address without asking the server for anything, so this
        # sees the first page load and little else; the bar reports the rest
        # through `/pb_tenancy/support/seen`.
        #
        # AND IT RECORDS SCREENS, NOT REQUESTS. A page load is thirty requests —
        # a stylesheet, a translations bundle, eleven avatars, a websocket — and
        # the first version of this recorded every one of them, which turned the
        # customer's trust page into a list of `/web/image` and made the two
        # screens somebody actually opened impossible to find. Only the backend
        # address counts, and only the bar can name it.
        if (rule.endpoint.routing.get('type') or 'http') == 'http' \
                and _is_screen(path):
            row.note_route(path)

    @classmethod
    def _pb_paused_door(cls, rule):
        """A paused customer meets a calm page instead of their payroll.

        THE DATA IS UNTOUCHED. This is a door, not a deletion: nothing is
        archived, nothing is dropped, and the moment somebody presses Resume on
        the platform the next request goes straight through.

        TWO ACCOUNTS STILL GET IN. The platform's recovery account, whose login
        is mirrored onto this database precisely so this check does not need
        the platform to be reachable; and anybody holding the platform's own
        administrator group, which on a customer's database is normally nobody
        at all (the tenant-admin rails see to that).
        """
        if not request:
            return
        # `request.env.uid` FIRST, AND `request.session.uid` ONLY AS A FALLBACK.
        # A route declared `auth='none'` runs with an environment whose uid is
        # None even when somebody is signed in, so `env.user` is an EMPTY
        # recordset and `has_group()` raises "Expected singleton" — which the
        # handler above swallowed, leaving the door open on every request.
        # The session still knows who it is, so the user is browsed explicitly.
        uid = request.env.uid or request.session.uid
        if not uid:
            return
        path = request.httprequest.path or ''
        if path.startswith(OPEN_PREFIXES):
            return
        env = request.env
        if 'pb.tenancy' not in env:
            return
        state = env['pb.tenancy'].sudo().access_state()
        if state['access'] != 'suspended':
            return
        user = env['res.users'].sudo().browse(uid).exists()
        if not user:
            return
        recovery = env['pb.tenancy'].sudo().recovery_login()
        if recovery and (user.login or '').strip().lower() == recovery:
            return
        if user.has_group('base.group_system'):
            return
        # An `http` request is a page: send them somewhere that explains
        # itself. Anything else is a call from a page that is already open —
        # refuse it by name, and the tab's own poll will move it along.
        if (rule.endpoint.routing.get('type') or 'http') == 'http':
            werkzeug.exceptions.abort(request.redirect('/pb_tenancy/paused'))
        raise AccessDenied(state['access_text'])

    def session_info(self):
        info = super().session_info()
        # Nothing for a visitor who is not logged in: there is no page with our
        # chrome on it to put a banner at the top of.
        if not (request and request.session.uid):
            return info
        try:
            info['pb_tenancy'] = self.env['pb.tenancy'].state()
        except Exception:                                    # noqa: BLE001
            # A broken settings row must never stop somebody logging in. The
            # browser treats a missing key as "no notice, no release".
            _logger.warning("pb_tenancy: could not read the platform state for "
                            "this session", exc_info=True)
        # FLEET P6. The support bar, on the first paint and for one account.
        # The key is ABSENT for everybody else — not false, not an empty object
        # — so nothing on any other person's page has to decide anything.
        try:
            sid = request.session.get('pb_support_id')
            if sid:
                sess = self.env['pb.tenancy'].sudo().support_session(sid)
                if sess:
                    info['pb_support_session'] = sess
        except Exception:                                    # noqa: BLE001
            _logger.warning("pb_tenancy: could not read the support session "
                            "for this page", exc_info=True)
        return info
