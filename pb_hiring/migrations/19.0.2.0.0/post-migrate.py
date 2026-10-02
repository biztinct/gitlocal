# -*- coding: utf-8 -*-
"""RECRUIT P1 — Rize's stage set on a database that already has wave 2.

The seed in `data/journey_seed.xml` runs on every load of the module and is
idempotent, so this migration only makes the order explicit and logs what
changed: the stages renamed and re-ordered (only where they still carry the
wave-2 words), the six stock stages retired with their candidates moved, a
Standard preset per company, and every existing role given its columns.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['hr.recruitment.stage']._ensure_journey_stages()
    made = env['pb.hiring.stage.preset']._ensure_standard()
    filled = env['pb.hiring.requisition']._pb_fill_visible_stages()
    _logger.info('pb_hiring 2.0.0: stages seeded; %s Standard presets made; '
                 '%s roles given their columns', made, filled)
