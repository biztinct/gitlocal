# -*- coding: utf-8 -*-
"""FS-10 — a standard contract field a pay formula can read can no longer be
hidden (owner rule R23; every field of the formula catalogue is locked now,
as on the employee).

A hide rule saved on such a field before this upgrade is cleared, with one
Form builder history line each. The screens already ignored it, so nothing on
screen changes; an own label is kept. Counts only in the log. Expected on
every live database: 0. Idempotent.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

MODEL = 'hr.contract'


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    names = env['pb.form.studio']._pbfs_std_unhide_locked(MODEL, 'FS-10.')
    _logger.info('pb_form_studio_contracts FS-10: locked standard fields shown again %s', len(names))
