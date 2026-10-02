# -*- coding: utf-8 -*-
"""RECRUIT P2 — application forms on a database that already has P1.

The seed in `data/journey_seed.xml` runs on every load and is idempotent, so
this migration only makes the order explicit and logs what it found: the four
product templates per company, every role its own copy, and the Vietnamese /
Indonesian words wherever those languages are installed (a language installed
LATER is filled by the next upgrade, never by hand).
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    made = env['pb.hiring.form']._ensure_templates()
    filled = env['pb.hiring.requisition']._pb_fill_forms()
    from odoo.addons.pb_hiring.models.forms_p2 import seed_received_i18n
    mails = seed_received_i18n(env)
    _logger.info('pb_hiring 2.1.0: %s form templates made; %s roles given their own form; '
                 '%s received-email translations written', made, filled, mails)
