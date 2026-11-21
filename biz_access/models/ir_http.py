# -*- coding: utf-8 -*-
"""The sign-in doors, in the order a person meets them.

1. The first-password door: someone given a password by an administrator
   chooses their own before any page opens (account_workers.py, point 2).
2. The two-step door (WDGAP QF5 A, two_step_rule.py): someone the
   "two-step sign-in is required" rule covers sets up an authenticator app
   before any page opens. It runs AFTER the first door — password first.
3. The idle check (WDGAP QF5 B, idle_rule.py): a session idle past the limit
   is signed out on its next request, page or call.

Only PAGES are redirected by the doors. A call from a page that is already
open is left alone: the next page load brings the person to the door, and
refusing calls would break the very page they are on.

Every door FAILS OPEN and says so in the log: a door that cannot decide never
blocks the page, and never takes a database down.
"""
import logging

import werkzeug
from werkzeug.urls import url_encode

from odoo import api, models
from odoo.http import request, root

from . import idle_rule, two_step_rule

_logger = logging.getLogger(__name__)

DOOR = '/biz_access/first-password'
TWO_STEP_DOOR = '/web/two-step'
OPEN_PREFIXES = (
    DOOR,
    TWO_STEP_DOOR,
    '/web/login',
    '/web/session/logout',
    '/web/session/destroy',
    '/web/session/alive',
    '/web/static/',
    '/web/assets/',
    '/web/image',
    '/web/binary/',
    '/web/webclient/',
    '/websocket',
    # Public UI strings are needed by the website-backed password form.
    '/website/translations',
    '/favicon',
    '/pb_tenancy/',
    '/iclock/',
)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    # ------------------------------------------------------------ idle check
    @classmethod
    def _authenticate(cls, endpoint):
        try:
            cls._pb_idle_check(endpoint)
        except Exception as exc:                              # noqa: BLE001
            _logger.warning('biz_access: idle check skipped, the request goes '
                            'through: %r', exc, exc_info=True)
        super()._authenticate(endpoint)

    @classmethod
    def _pb_idle_check(cls, endpoint):
        """Sign out a session idle past the limit, BEFORE the route's own
        authentication runs: the standard "session ended" path then follows
        (sign-in page for a page, the session-ended dialog for a call)."""
        # Every route with a signed-in session, `auth='none'` ones included:
        # the web client's own page (`/odoo`) is one of those.
        if not request or request.session.uid is None:
            return
        minutes = idle_rule.idle_minutes(request.env)
        if not minutes:
            return
        user = request.env['res.users'].sudo().browse(request.session.uid)
        if two_step_rule.is_exempt(user, request.session, include_demo=False):
            return
        if idle_rule.expired(request.session, minutes):
            _logger.info('biz_access: user %s signed out after %s minutes '
                         'without activity', request.session.uid, minutes)
            request.session.logout(keep_db=True)
            # Saved now: a call that ends in "session expired" is an error
            # response, and the framework does not save the session then.
            root.session_store.save(request.session)
            request.env = api.Environment(request.env.cr, None,
                                          request.session.context)

    # ------------------------------------------------------------ the doors
    @classmethod
    def _pre_dispatch(cls, rule, args):
        super()._pre_dispatch(rule, args)
        try:
            cls._pb_first_password_door(rule)
        except werkzeug.exceptions.HTTPException:
            raise
        except Exception as exc:                              # noqa: BLE001
            # A door that cannot decide never blocks the page.
            _logger.debug('biz_access: first-password door skipped: %s', exc)
        try:
            cls._pb_two_step_door(rule)
        except werkzeug.exceptions.HTTPException:
            raise
        except Exception as exc:                              # noqa: BLE001
            _logger.warning('biz_access: two-step door skipped, the page '
                            'opens: %r', exc, exc_info=True)
        try:
            cls._pb_idle_stamp(rule)
        except Exception as exc:                              # noqa: BLE001
            _logger.warning('biz_access: idle stamp skipped: %r', exc,
                            exc_info=True)

    @classmethod
    def _pb_first_password_door(cls, rule):
        if not request or not request.session.uid:
            return
        if (rule.endpoint.routing.get('type') or 'http') != 'http':
            return
        path = request.httprequest.path or ''
        if path.startswith(OPEN_PREFIXES):
            return
        user = request.env['res.users'].sudo().browse(request.session.uid)
        if 'pb_must_change_password' not in user._fields:
            return
        if user.exists() and user.pb_must_change_password:
            werkzeug.exceptions.abort(request.redirect(DOOR))

    @classmethod
    def _pb_two_step_door(cls, rule):
        if not request or not request.session.uid:
            return
        if not two_step_rule.read_rule(request.env):
            return                                  # the default: nobody
        if (rule.endpoint.routing.get('type') or 'http') != 'http':
            return
        if (request.httprequest.path or '').startswith(OPEN_PREFIXES):
            return
        user = request.env['res.users'].sudo().browse(request.session.uid)
        if not user.exists() or not two_step_rule.needs_setup(user, request.session):
            return
        target = TWO_STEP_DOOR
        if request.httprequest.method == 'GET':
            target += '?' + url_encode(
                {'redirect': request.httprequest.full_path.rstrip('?')})
        werkzeug.exceptions.abort(request.redirect(target))

    @classmethod
    def _pb_idle_stamp(cls, rule):
        """A full page the person opened counts as activity."""
        if not request or not request.session.uid:
            return
        if (rule.endpoint.routing.get('type') or 'http') != 'http':
            return
        if not idle_rule.idle_minutes(request.env):
            return
        if idle_rule.is_page_navigation(request.httprequest):
            idle_rule.stamp(request.session)

    # ------------------------------------------------------- the browser's value
    def _pb_idle_info(self, info):
        try:
            if request and request.session.uid:
                minutes = idle_rule.minutes_for(self.env.user, request.session)
                if minutes:
                    info['pb_idle_minutes'] = minutes
        except Exception:                                     # noqa: BLE001
            _logger.warning('biz_access: the idle limit could not be read for '
                            'this page', exc_info=True)
        return info

    def session_info(self):
        return self._pb_idle_info(super().session_info())

    @api.model
    def get_frontend_session_info(self):
        return self._pb_idle_info(super().get_frontend_session_info())
