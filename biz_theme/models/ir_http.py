"""Runtime flags for the web client — and the developer-mode rail.

TWO THINGS LIVE HERE, AND THE SECOND ONE IS A SECURITY RAIL.

  * ``session_info`` decorations: the theme's kill-switch, published theme
    version, brand name and menu-sidebar list.
  * **The developer-mode rail (ACCESS P5, Rail A).** Developer mode is a
    session flag anybody can ask for by putting ``?debug=1`` in the address
    bar, and once it is on it puts the technical machinery of the whole
    database on the screen: every model's fields, the view editor, raw record
    ids, the server-action runner. On a platform where one database belongs to
    one customer, the person who administers that customer's own application
    must not be able to switch it on for themselves. So it is decided on the
    SERVER: for anybody who is not a system administrator the flag is cleared
    on every request, whatever the address bar says.

WHY AN ``_inherit`` AND NOT A MONKEY-PATCH
------------------------------------------
``biz_deroute/models/ir_http_session_guard.py`` documents an ordering hazard
that looks like this problem and is not: it had to patch ``hr_timesheet``'s
class because an ``_inherit`` would have made its own method the OUTERMOST one
(so the crash it was guarding happened inside its own ``super()`` call), and
because importing an addon it does not DEPEND on drags that addon's ``ir.http``
into the class registry ahead of its place in the module graph — which took the
login page of every database on the box down.

Neither applies here, and both point the same way:

  * outermost is exactly where this rail wants to be. ``_handle_debug`` is
    where ``web`` writes the flag, and this override runs AFTER ``web`` has
    written it, so it clears what was just set rather than being overwritten by
    it.
  * nothing new is imported. This module already declares ``web`` in its
    ``depends`` and this class already inherits ``ir.http`` for
    ``session_info``, so the rail adds two methods to a class that is already
    in the registry at exactly the position the module graph puts it. No new
    edge, no new import, no ordering to reason about.

So: ``_inherit``, in ``biz_theme``, which is installed on every database on
this platform — including the tenant databases that do not have the access
module. A rail that only exists where the access module is installed is not a
rail.

THE SECOND SEAM, AND WHY ONE IS NOT ENOUGH. Clearing the session is not the
whole job, because not every page reads developer mode off the session. The
LOGIN page does not: `web`'s own controller copies a short list of query-string
parameters straight into the template values, and `debug` is one of them
(`web/controllers/home.py`, ``SIGN_UP_REQUEST_PARAMS``), so `?debug=1` on
`/web/login` reaches the page even with the session cleared — and the login form
then draws a "Log in as superuser" button on a white-labelled sign-in screen for
anybody who typed it. Measured on this build. So the rail is applied a second
time where every page is finally assembled: ``ir.qweb._prepare_environment``,
below. Cheap, because it only looks when a value is actually set.

WHAT IT DOES NOT DO. It does not touch public or website routes' behaviour
beyond the flag itself (an anonymous visitor asking for developer mode simply
does not get it), it does not remove anybody's access to anything, and a system
administrator — the owner — keeps developer mode everywhere, exactly as before.
There is also a switch: set ``biz_theme.debug_rail`` to ``off`` and the rail
stands down without a deploy.
"""
import logging

from odoo import api, models
from odoo.http import request

_logger = logging.getLogger(__name__)

#: ir.config_parameter that stands the rail down. Anything other than these
#: words leaves it armed — a mistyped value must never open developer mode.
_RAIL_OFF = ('off', '0', 'false', 'no')


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    # ===================================================== the developer rail
    @staticmethod
    def _biz_rail_armed_in(env):
        """Is the rail switched on for this database?

        Takes the environment rather than reaching for the request, because the
        same question is asked from two places — a request being dispatched and
        an ORM method — and two ways of answering it is how they come to
        disagree. Read only when somebody is actually asking for developer
        mode, so an ordinary request pays nothing for it, and ``get_param`` is
        cached on the registry, so even then it is not a query per request.
        """
        try:
            icp = env['ir.config_parameter'].sudo()
            return str(icp.get_param('biz_theme.debug_rail', 'on')).strip(
            ).lower() not in _RAIL_OFF
        except Exception:                           # noqa: BLE001
            # A check that cannot be made is not a pass. Leaving the rail armed
            # costs a system administrator one refreshed page; standing it down
            # costs the platform the rail itself.
            _logger.warning(
                'biz_theme: could not read the developer-mode switch — the '
                'rail stays armed', exc_info=True)
            return True

    @classmethod
    def _biz_debug_rail_armed(cls):
        """The same question, from a request being dispatched."""
        try:
            return cls._biz_rail_armed_in(request.env)
        except Exception:                           # noqa: BLE001
            return True

    @staticmethod
    def _biz_request_user(env):
        """Who is logged in on THIS request — read from the session, not the env.

        THE ENVIRONMENT IS NOT ALWAYS THE PERSON, AND A LIVE RUN PROVED IT. At
        the moment developer mode is decided the request has been authenticated
        but its environment has not necessarily been moved onto the logged-in
        user yet: on this build's own backend route the environment still
        answered an empty user while the session carried a real one, so a system
        administrator was refused developer mode on their own screen. The
        session's `uid` is the authenticated answer by then — `_authenticate`
        has already run and clears it when it is not — so that is what is read.
        """
        try:
            uid = request.session.uid if request else None
        except Exception:                           # noqa: BLE001
            uid = None
        if uid:
            user = env['res.users'].sudo().browse(uid).exists()
            if user:
                return user
        return env.user if env else None

    @classmethod
    def _biz_may_debug(cls):
        """May the person making THIS request use developer mode?

        Only a system administrator may. Everything else — an ordinary
        employee, a tenant's own administrator, the anonymous visitor on a
        public page, a request made before anybody has logged in — may not, and
        anything that goes wrong while working that out is read as "may not".
        """
        try:
            if request is None or request.env is None:
                return False
            if not request.session.uid:
                return False
            user = cls._biz_request_user(request.env)
            return bool(user) and user._is_system()
        except Exception:                           # noqa: BLE001
            _logger.warning(
                'biz_theme: could not work out whether this request may use '
                'developer mode — it may not', exc_info=True)
            return False

    @classmethod
    def _handle_debug(cls):
        """``web``'s own ``?debug=`` handling, then the rail.

        ``web.ir_http._handle_debug`` writes ``request.session.debug`` from the
        query string and is called from ``_pre_dispatch`` for every route this
        server dispatches. Clearing it HERE — after ``super()``, on every
        request rather than only on the one carrying ``?debug=`` — is what
        makes the rail hold: a flag set in an earlier request, or carried into
        a session by any route at all, is taken away again on the next one.

        The write only happens when there is something to clear, so a session
        that never had developer mode on is never marked dirty by this.
        """
        super()._handle_debug()
        if not request.session.debug:
            return
        if cls._biz_may_debug() or not cls._biz_debug_rail_armed():
            return
        # Worth a line in the log. Somebody putting `?debug=` in the address bar
        # of a product that never offers it is not an accident, and a rail that
        # holds silently tells nobody it was tested.
        who = cls._biz_request_user(request.env) if request.session.uid else None
        _logger.info(
            'biz_theme: developer mode refused for %s on %s',
            (who.login if who else 'a visitor'), request.httprequest.path)
        request.session.debug = ''

    def _biz_debug_allowed(self):
        """The same question, asked from an ORM method rather than a request.

        ``session_info`` runs as a normal model method with a real environment,
        so it asks ``self.env.user`` rather than the request — the answer has
        to be the same one, and reading it from the environment is what makes
        it right when the session and the environment differ.
        """
        try:
            user = self._biz_request_user(self.env)
            if user and user._is_system():
                return True
            return not self._biz_rail_armed_in(self.env)
        except Exception:                           # noqa: BLE001
            return False

    @staticmethod
    def _biz_strip_debug(info):
        """Take the developer-mode bundle out of a session payload.

        Belt and braces on top of ``_handle_debug``: the flag is already
        cleared by the time this runs, so in ordinary use there is nothing
        here to remove. It stays because ``bundle_params.debug`` is what the
        browser reads to decide whether to load the developer assets, and a
        rail whose only enforcement point is one method is a rail with one
        place to forget.
        """
        params = info.get('bundle_params')
        if isinstance(params, dict):
            params.pop('debug', None)
        return info

    # ==================================================== the runtime payload
    def session_info(self):
        """Expose biz_theme runtime flags to the web client.

        - ``vu_form_engine``: kill-switch for the VU Form Engine. Set
          ``biz_theme.vu_form_engine = off`` (ir.config_parameter) to revert
          every form to stock Odoo rendering without a deploy. The legacy
          ``pb_theme.vu_form_engine`` key is still honoured so live databases
          keep working after the pb_theme → biz_theme split.
        - ``biz_theme_version``: published runtime-theme version, used by the
          Theme Studio to invalidate cached tokens.css.
        """
        info = super().session_info()
        icp = self.env["ir.config_parameter"].sudo()
        info["vu_form_engine"] = icp.get_param(
            "biz_theme.vu_form_engine",
            icp.get_param("pb_theme.vu_form_engine", "on"),
        )
        info["biz_theme_version"] = icp.get_param("biz_theme.theme_version", "0")
        # Brand/app name for the browser-tab title. Same resolution chain as the
        # backend favicon/title template (webclient_templates.xml): an explicit
        # `biz_theme.app_name` knob wins, then the debrand suite's keys if
        # installed, then the current company name, then "Odoo". The core JS
        # title service hard-codes "Odoo" as its empty-title fallback and runs
        # AFTER the server-rendered <title>, so biz_title_service.js reads this
        # to keep the tab branded.
        info["biz_app_name"] = (
            icp.get_param("biz_theme.app_name")
            or icp.get_param("biz_debrand.brand_name")
            or icp.get_param("web_debranding.new_title")
            or (self.env.company.name if self.env.company else None)
            or "Odoo"
        )
        # Menu-driven sidebar: comma-separated root-menu xml_ids for which the
        # zero-config BizSidebar renders (empty = feature off).
        info["biz_menu_sidebar_apps"] = [
            x.strip()
            for x in icp.get_param("biz_theme.menu_sidebar_apps", "").split(",")
            if x.strip()
        ]
        if not self._biz_debug_allowed():
            self._biz_strip_debug(info)
        return info

    @api.model
    def get_frontend_session_info(self):
        """The same rail on the public side.

        The website and portal build their own payload from their own method,
        and it carries the same ``bundle_params.debug`` key. Left alone, a
        public page would be the one place the developer assets could still be
        asked for.
        """
        info = super().get_frontend_session_info()
        if not self._biz_debug_allowed():
            self._biz_strip_debug(info)
        return info


class IrQweb(models.AbstractModel):
    """The second half of the developer-mode rail (see the header).

    EVERY PAGE ON THIS SERVER IS ASSEMBLED HERE, so this is the one place that
    catches a page whose developer-mode value did not come from the session.
    The login page is the one that forced it: its controller copies `?debug=`
    out of the query string into the template values, and `setdefault` in the
    method below then leaves that value alone — so the sign-in screen drew the
    technical "Log in as superuser" button for anybody who typed the parameter,
    on a session that had already been cleared.

    IT COSTS NOTHING WHEN THERE IS NOTHING TO DO. The value is almost always
    empty, and an empty value is not looked at twice: the permission question is
    only asked when a page has actually been handed a developer-mode value.
    """
    _inherit = 'ir.qweb'

    def _prepare_environment(self, values):
        res = super()._prepare_environment(values)
        try:
            if values.get('debug') and not self.env['ir.http']._biz_debug_allowed():
                values['debug'] = ''
        except Exception:                           # noqa: BLE001
            # A rail that cannot answer takes developer mode away rather than
            # leaving it on — and a page must never fail to render because of
            # this check.
            _logger.warning(
                'biz_theme: could not decide developer mode while rendering — '
                'it is switched off for this page', exc_info=True)
            values['debug'] = ''
        return res
