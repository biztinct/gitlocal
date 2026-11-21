# -*- coding: utf-8 -*-
"""2.23.6 -> 2.23.7 (WF2 P6a, closeout item 12) — Hiring's own stage names and
meanings in Indonesian.

The 17 product stages are rows made by the seed, not data records, so a
`.po` cannot reach them: the translation is the stored value. Writes the
product's Indonesian (and any missed Vietnamese) only where a row still
carries the product's English and no words of its own in that language; a
client's own names are never touched. Idempotent.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api
    env = api.Environment(cr, SUPERUSER_ID, {})
    written = env['hr.recruitment.stage']._pb_stage_translations()
    _logger.info('pb_hiring 2.23.7: %s stage names and meanings translated', written)
