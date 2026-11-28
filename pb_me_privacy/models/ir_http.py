# -*- coding: utf-8 -*-
"""The privacy door on My Payobook (owner ruling E3).

Before any My Payobook page opens, a person whose company has published a
privacy notice they have not answered yet is shown that notice first. The
notice offers two answers and BOTH continue to the page they asked for:
nobody is ever locked out of their payslip.

WHY `ir.http` AND NOT THE HOME PAGE. A deep link (`/my/payslips` from an
email) never passes through `/my`, so a home-only screen would be skipped by
exactly the people who sign in from a link (FACTS §4.4).

CHEAP AND FAIL-OPEN. Only GET pages under `/my`, only signed-in people. The
answer "nothing to ask" is cached in the session against one database stamp
(bumped on every publish), so an ordinary page costs one cached setting read.
Anything unexpected opens the page: a door that cannot decide never blocks.
"""

import logging
from urllib.parse import quote

import werkzeug

from odoo import models
from odoo.http import request

from .notice import STAMP_PARAM

_logger = logging.getLogger(__name__)

#: The notice itself, the photo route the notice page draws, and sign-in
#: security (a person must always be able to change their password).
OPEN_PREFIXES = ('/my/privacy', '/my/photo', '/my/security')
DOOR = '/my/privacy/notice'
SESSION_KEY = 'pb_privacy_ok'


def _is_my_path(path):
    return path == '/my' or path.startswith('/my/')


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _pre_dispatch(cls, rule, args):
        super()._pre_dispatch(rule, args)
        try:
            cls._pb_privacy_door(rule)
        except werkzeug.exceptions.HTTPException:
            raise
        except Exception as exc:                              # noqa: BLE001
            _logger.debug('pb_me_privacy: the privacy door was skipped: %r',
                          exc)

    @classmethod
    def _pb_privacy_door(cls, rule):
        if not request or not request.session.uid:
            return
        if (rule.endpoint.routing.get('type') or 'http') != 'http':
            return
        if request.httprequest.method != 'GET':
            return
        path = request.httprequest.path or ''
        lang_prefix = ''
        # A language prefix (/vi/my/...) is part of the path on website pages.
        parts = path.split('/', 2)
        if len(parts) > 2 and parts[1] and not _is_my_path(path) \
                and _is_my_path('/' + parts[2]):
            lang_prefix = '/' + parts[1]
            path = '/' + parts[2]
        if not _is_my_path(path) or path.startswith(OPEN_PREFIXES):
            return
        stamp = request.env['ir.config_parameter'].sudo().get_param(
            STAMP_PARAM) or '0'
        key = '%s:%s' % (request.session.uid, stamp)
        if request.session.get(SESSION_KEY) == key:
            return
        user = request.env['res.users'].sudo().browse(request.session.uid)
        notice, _employee = request.env['pb.privacy.consent'].sudo() \
            ._pb_pending(user)
        if not notice:
            request.session[SESSION_KEY] = key
            return
        target = request.httprequest.full_path or path
        if target.endswith('?'):
            target = target[:-1]
        werkzeug.exceptions.abort(request.redirect(
            '%s%s?next=%s' % (lang_prefix, DOOR, quote(target, safe=''))))
