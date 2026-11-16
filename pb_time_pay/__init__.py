# -*- coding: utf-8 -*-
import logging

from . import controllers
from . import models
from .models.time_pay import LATE_INPUT_CODES

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Warn (the C18.2 rule the overtime bridge follows) about any existing
    pay item whose code equals, contains or is contained in LATEMIN / EARLYMIN.
    A collision does not break the converter, but a code that shadows ours
    would receive (or hide) the confirmed minutes, so it is surfaced."""
    codes = list(LATE_INPUT_CODES)
    try:
        rules = env['hr.formula.rule'].sudo().with_context(
            active_test=False).search([])
    except Exception as exc:  # pragma: no cover - engine absent mid-install
        _logger.warning("pb_time_pay: cannot scan pay items: %s", exc)
        return
    conflicts = []
    for rule in rules:
        code = (rule.code or '').upper()
        if not code:
            continue
        for ours in codes:
            if code != ours and (code in ours or ours in code):
                conflicts.append('%s (scheme %s) ~ %s' % (
                    rule.code, rule.config_id.code or '?', ours))
                break
    if conflicts:
        _logger.warning(
            "pb_time_pay: %d pay item code collision(s) with %s: %s",
            len(conflicts), codes, '; '.join(conflicts))
    else:
        _logger.info("pb_time_pay: no late-minute code collisions found.")
