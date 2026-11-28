# -*- coding: utf-8 -*-
"""Roles for the screens that shipped with permission groups and no role.

THE HOLE THIS CLOSES. Hiring, Goals, Training, Announcements, the Decision
Room, Pay bands and reviews, Where they work, Field staff, group set-up and
government reports each gate on groups of their own, and no role in the
catalogue carried any of them. "Give a role" therefore had nothing to offer
for them — found by the owner on 2026-09-24 looking for a hiring role.

R84 — `post_init_hook` fires on INSTALL ONLY, so the catalogue grows on an
upgrade only because this asks it to.

IT GRANTS NOBODY ANYTHING. It writes catalogue rows; somebody still has to
press "Give a role", and the audit trail records that they did. The tenant
administrator bundle is NOT widened here.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not table_exists(cr, 'pb_role_profile'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_vendor_access.hooks import ensure_catalogue
    result = ensure_catalogue(env)
    _logger.info('pb_vendor_access 1.9.0: catalogue reseeded — %s', result)
