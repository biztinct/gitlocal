# -*- coding: utf-8 -*-
"""FS-14b — no broken app pictures behind the employee record page.

The standard Employees action carries an empty-list advert in its `help`
with fifteen app pictures (`hr/views/hr_employee_views.xml:672`, pictures
705-765); seven of those apps are not part of this build. The web client
puts an action's `help` into the live page to test whether it is empty
(`web/static/src/core/utils/html.js:189-191`, called from
`webclient/actions/action_service.js:431-433`), so every open of an employee
record asked the server for seven pictures that do not exist (404s in the
browser console).

Fixed where the action is handed to the browser, for every action: a picture
of an app's own icon (`/<app>/static/...`) is left out when that app is not
on this server. Nothing is stored or changed; an upgrade of the HR addon
cannot bring the 404s back; pictures of apps that exist stay.
"""
import functools
import re

from odoo import models
from odoo.modules.module import get_module_path

APP_IMG = re.compile(r'<img\b[^>]*\bsrc=["\']/([A-Za-z0-9_]+)/static/[^"\']*["\'][^>]*>', re.I)


@functools.lru_cache(maxsize=512)
def _app_on_server(name):
    return bool(get_module_path(name, display_warning=False))


def strip_missing_app_pictures(html):
    if not html or '<img' not in html:
        return html
    return APP_IMG.sub(lambda m: m.group(0) if _app_on_server(m.group(1)) else '', html)


class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    def _get_action_dict(self):
        result = super()._get_action_dict()
        if isinstance(result.get('help'), str):
            result['help'] = strip_missing_app_pictures(result['help'])
        return result
