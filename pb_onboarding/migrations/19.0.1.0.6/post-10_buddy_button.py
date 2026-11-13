# -*- coding: utf-8 -*-
"""The "you are a buddy" email gains an "Open My buddy" button.

The templates are `noupdate="1"` (a company may reword its own emails), so a
module upgrade does not carry the new body across. `reset_template()` — the
mail module's own "Reset template" — reloads it from the data file, but only
on a database where nobody has touched it since it was loaded: an edited
template is left alone and logged, because a company's own words win.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    tpl = env.ref('pb_onboarding.mail_template_buddy_to_buddy',
                  raise_if_not_found=False)
    if not tpl:
        return
    if tpl.write_uid.id not in (False, SUPERUSER_ID, env.ref('base.user_root').id):
        _logger.info("buddy email: edited by %s, left as it is",
                     tpl.write_uid.login)
        return
    if '/my/buddy' in (tpl.body_html or ''):
        return
    tpl.reset_template()
    _logger.info("buddy email: reloaded with the My buddy button")
