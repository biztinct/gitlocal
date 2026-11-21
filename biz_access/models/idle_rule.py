# -*- coding: utf-8 -*-
"""SIGN PEOPLE OUT AFTER N MINUTES WITHOUT ACTIVITY (WDGAP QF5 B). The kernel.

One switch, `biz_access.idle_minutes`: 0 (the default) is off; otherwise 15,
30, 60 or 120 (the screen's choices; the platform may set any value of 5 or
more by hand, 1-4 are refused as a typing slip).

Activity is what the PERSON does. The browser (static/src/js/idle_watch.js)
watches pointer, keyboard and touch, shares the last moment across tabs and,
while the person is active, tells the server at most once a minute
(`POST /web/session/alive`). The server keeps `pb_last_active` in the session
and refreshes it ONLY from that call and from a full page navigation — never
from background calls or the websocket — so a closed laptop or a script cannot
keep a session forever. The server's own limit is the setting plus two
minutes, so the browser's one-minute warning always shows first.

Never signed out by this rule: support sessions, the recovery login and the
logins in `biz_access.two_step_exempt_logins` (two_step_rule.is_exempt without
the demo group: demo logins DO idle out when a database turns this on).

Kill switch: set `biz_access.idle_minutes` to 0 or blank (psql) — the next
request reads it and nothing more happens, no restart.
"""
import logging
import time

from odoo import _, api, models
from odoo.exceptions import UserError

from .access_common import param_int
from .two_step_rule import is_exempt

_logger = logging.getLogger(__name__)

IDLE_PARAM = 'biz_access.idle_minutes'
CHOICES = (0, 15, 30, 60, 120)
MINIMUM = 5
GRACE_SECONDS = 120
STAMP = 'pb_last_active'

#: Requests that are never "a page the person opened", whatever the browser
#: says: files, images, translations, the websocket, background feeds.
NOT_PAGES = (
    '/web/static/', '/web/assets/', '/web/image', '/web/content',
    '/web/binary/', '/web/webclient/', '/web/manifest', '/web/service-worker',
    '/websocket', '/longpolling', '/bus/', '/website/translations',
    '/favicon', '/iclock/', '/web/session/',
)


def idle_minutes(env):
    """The setting, 0 when off or unreadable."""
    minutes = param_int(env, IDLE_PARAM, 0)
    return minutes if minutes >= MINIMUM else 0


def minutes_for(user, session):
    """The limit that applies to this signed-in session, 0 for none."""
    minutes = idle_minutes(user.env)
    if not minutes or is_exempt(user, session, include_demo=False):
        return 0
    return minutes


def stamp(session):
    session[STAMP] = int(time.time())


def is_page_navigation(httprequest):
    """A full page the person opened (GET, a document, not a file or a feed)."""
    if httprequest.method != 'GET':
        return False
    if (httprequest.path or '').startswith(NOT_PAGES):
        return False
    dest = httprequest.headers.get('Sec-Fetch-Dest')
    return dest in (None, '', 'document')


def expired(session, minutes, now=None):
    """True when the session has been idle past the limit and its grace.

    A session with no stamp yet is stamped, not expired: switching the rule on
    never throws out somebody who is in the middle of their work.
    """
    last = session.get(STAMP)
    now = int(now or time.time())
    if not isinstance(last, (int, float)):
        session[STAMP] = now
        return False
    return now - last > minutes * 60 + GRACE_SECONDS


class PbAccessIdle(models.AbstractModel):
    _inherit = 'pb.access'

    @api.model
    def idle_setting(self):
        self._require_manage()
        return {'minutes': idle_minutes(self.env), 'choices': list(CHOICES)}

    @api.model
    def set_idle_setting(self, minutes):
        self._require_manage()
        try:
            minutes = int(minutes or 0)
        except (TypeError, ValueError):
            raise UserError(_("Choose how many minutes."))
        if minutes < 0 or 0 < minutes < MINIMUM:
            raise UserError(_("Choose at least %s minutes, or Off.", MINIMUM))
        self.env['ir.config_parameter'].sudo().set_param(
            IDLE_PARAM, str(minutes) if minutes else '0')
        _logger.info('biz_access: user %s set sign-out when idle to %s minutes',
                     self.env.uid, minutes)
        if minutes:
            message = _("Saved. People are signed out after %s minutes "
                        "without activity.", minutes)
        else:
            message = _("Saved. Nobody is signed out for being away from the "
                        "screen.")
        self._two_step_audit(_("Sign-out when idle changed"), message,
                             {'minutes': minutes})
        return {'minutes': minutes, 'choices': list(CHOICES), 'message': message}
