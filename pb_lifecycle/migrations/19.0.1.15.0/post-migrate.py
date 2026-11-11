# -*- coding: utf-8 -*-
"""1.14.0 -> 1.15.0 — "where time goes" starts from what the history proves.

Stays in company stages are counted from now on by the position model itself
(`pb.workflow.stage.visit`). Before this version only the workflow history
kept them: a "Moved to …" line (it names the stage) and, when the record left,
a "Left …" line or the next "Moved to …". This rebuilds a stay ONLY when both
ends are in that history, or when the record is still in that stage today.
Nothing is guessed: a stay whose end is unknown is not rebuilt.

Idempotent: it does nothing when any stay is already counted.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api
    env = api.Environment(cr, SUPERUSER_ID, {})
    made = env['pb.workflow.stage.visit']._backfill()
    _logger.info('pb_lifecycle 1.15.0: %s stays in company stages rebuilt from the history', made)
