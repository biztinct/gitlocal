# -*- coding: utf-8 -*-
import logging

from . import models
from .models.hr_payslip import TRIP_INPUT_CODES

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Warn (C18.2) about any existing formula rule whose code collides with —
    or is a substring-conflict of — the two trip input codes we own. Substring
    collisions don't break the converter (C13), but a code equal to or
    containing one of ours would shadow the injected value, so we surface it."""
    codes = list(TRIP_INPUT_CODES)
    try:
        rules = env['hr.formula.rule'].sudo().search([])
    except Exception as e:  # pragma: no cover - engine may be absent mid-install
        _logger.warning("pb_trip_payroll_bridge: cannot scan formula rules: %s", e)
        return
    conflicts = []
    for r in rules:
        c = (r.code or '').upper()
        if not c:
            continue
        for nc in codes:
            if c == nc or c in nc or nc in c:
                cfg = r.config_id.code if r.config_id else '?'
                conflicts.append('%s (config %s) ~ %s' % (r.code, cfg, nc))
                break
    if conflicts:
        _logger.warning(
            "pb_trip_payroll_bridge: %d formula-rule code collision(s) with trip "
            "input codes %s: %s", len(conflicts), codes, '; '.join(conflicts))
    else:
        _logger.info("pb_trip_payroll_bridge: no trip input code collisions found.")
