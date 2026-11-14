# -*- coding: utf-8 -*-
import logging

from . import models
from . import controllers

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Every company gets the default loan route (Head of pay), exactly as
    awards do. A failure is logged and never stops the install."""
    try:
        from .models.loan_approval import seed_all
        seed_all(env)
    except Exception:       # noqa: BLE001 — an install must not die here
        _logger.exception('pb_loans: the default loan routes were not laid')
