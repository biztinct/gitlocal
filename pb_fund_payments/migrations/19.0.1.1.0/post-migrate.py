# -*- coding: utf-8 -*-
"""WDGAP W2-F (F-2): fund payments start with one sign-off (the Head of pay).

Rewrites a company's fund-payment route ONLY where it is still exactly the
two-signature route 19.0.1.0.0 seeded and no fund payment of that company was
ever sent for approval (`fund_approval._pb_one_signature`). Every other route
is left as it is. One line per company in the log says which.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_fund_payments.models.fund_approval import one_signature_all
    out = one_signature_all(env)
    _logger.info('pb_fund_payments W2-F: %s of %s routes set to one signature',
                 len([v for v in out.values() if v == 'changed']), len(out))
