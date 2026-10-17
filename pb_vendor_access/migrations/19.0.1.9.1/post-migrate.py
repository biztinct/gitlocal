# -*- coding: utf-8 -*-
"""The role catalogue in Vietnamese (LEARN REFRESH step 6, item 5).

Role and ability names/descriptions are stored translatable (jsonb) values
seeded from Python data, so they only ever held English and the Access screen
read English to a Vietnamese reader. This writes the `vi_VN` value of every
seeded row whose English is still the catalogue's own. Idempotent; leaves
renamed rows, hand-made rows and existing Vietnamese alone; does nothing on a
database without Vietnamese installed.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not table_exists(cr, 'pb_role_profile'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_vendor_access.catalogue_vi import apply_catalogue_vi
    written = apply_catalogue_vi(env)
    _logger.info('pb_vendor_access 1.9.1: %s Vietnamese role values written',
                 written)
