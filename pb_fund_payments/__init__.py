# -*- coding: utf-8 -*-
import logging

from . import models

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Every company gets the default fund-payment route (the payment
    release's two signatures). Nothing else is created: no payee, no payment,
    no job, no email (R5). A failure is logged and never stops the install."""
    try:
        from .models.fund_approval import seed_all
        seed_all(env)
    except Exception:       # noqa: BLE001 — an install must not die here
        _logger.exception('pb_fund_payments: the default routes were not laid')
