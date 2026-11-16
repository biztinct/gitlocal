# -*- coding: utf-8 -*-
import logging

from . import models

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """WDGAP W2-D2: every company gets the default back-pay route (one step,
    the Head of pay). Nothing else is created: no back pay, no job, no email.
    A failure is logged and never stops the install."""
    try:
        from .models.retro_backpay import seed_all
        seed_all(env)
    except Exception:       # noqa: BLE001 — an install must not die here
        _logger.exception('pb_retro: the default back-pay routes were not laid')
