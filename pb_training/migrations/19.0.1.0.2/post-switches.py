# -*- coding: utf-8 -*-
"""Materialise any switch this module has GROWN since it was installed.

`post_init_hook` fires on INSTALL ONLY and never on `-u` — the Odoo 19 trap
the ledger records — so the switch E1 added after its own first install
(`pb_training.unenrol_on_failed_test`) had no row, on a database where the
hook had already run. Nothing BEHAVED wrong: every reader goes through
`flag()`/`number()`, which fall back to the same defaults in code. But a
switch nobody can find on the Settings screen is a switch nobody can turn,
and the one it hides is the one that decides whether failing a test takes
somebody off a course.

Idempotent by construction — it writes only where there is no row at all, so
a value a company has chosen is never put back.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    from odoo.addons.pb_training.models.training_common import DEFAULTS
    env = api.Environment(cr, SUPERUSER_ID, {})
    icp = env['ir.config_parameter'].sudo()
    added = []
    for key, value in DEFAULTS.items():
        if not icp.get_param(key):
            icp.set_param(key, value)
            added.append(key)
    _logger.info('pb_training: %s switch(es) materialised: %s',
                 len(added), ', '.join(added) or 'none')
