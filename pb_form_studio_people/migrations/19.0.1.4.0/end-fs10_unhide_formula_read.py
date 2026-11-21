# -*- coding: utf-8 -*-
"""FS-10 — a standard employee field that something on THIS database really
reads (a pay scheme component bound to it in a scheme that is not archived,
or a pay data file column) can no longer be hidden (owner rule R23, architect
ruling FS-10). The reason names what uses it.

A hide rule saved on such a field before this upgrade (for everyone or for
some Countries of Work) is cleared, with one Form builder history line each.
The screens already ignored it (a locked field is never hidden), so nothing
on screen changes; an own label is kept. A field a formula merely COULD read
is left alone. Counts only in the log. Expected on every live database: 0.
Idempotent.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

MODEL = 'hr.employee'


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    names = env['pb.form.studio']._pbfs_std_unhide_locked(MODEL, 'FS-10.')
    _logger.info('pb_form_studio_people FS-10: locked standard fields shown again %s', len(names))
