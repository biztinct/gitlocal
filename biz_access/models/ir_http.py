# -*- coding: utf-8 -*-
"""The first-password door: someone given a password by an administrator
chooses their own before any page opens (account_workers.py, point 2).

Only PAGES are redirected. A call from a page that is already open is left
alone: the next page load brings the person to the door, and refusing calls
would break the very page they are on.
"""
import logging

import werkzeug

from odoo import models
from odoo.http import request

_logger = logging.getLogger(__name__)

DOOR = '/biz_access/first-password'
OPEN_PREFIXES = (
    DOOR,
    '/web/login',
    '/web/session/logout',
    '/web/session/destroy',
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
