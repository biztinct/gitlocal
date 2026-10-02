# -*- coding: utf-8 -*-
"""Remember the inputs every already-agreed scenario was agreed against.

WHY A BACKFILL AND NOT "IT STARTS WORKING FOR NEW ONES". Every scenario on
every database already has its expected numbers, agreed long before there was
anywhere to record the inputs behind them. Without this the new explanation
would be blank on exactly the scenarios people have — which is to say the
feature would ship switched off and nobody would know.

WHERE THE ANSWER COMES FROM, AND WHY IT IS NOT A GUESS. A scenario seeded from
a starter carries the starter's code in its own description, and the starter
carries the certification suite it was seeded from: the persona, by name, with
the inputs its expected numbers were certified against. That is not an
approximation of what they were agreed against — it IS what they were agreed
against.

WHAT IT REFUSES TO DO. Anything it cannot answer exactly, it leaves empty:
a scenario somebody wrote by hand, one whose name has been changed, one whose
starter is not on this database. Empty means "nobody recorded this", and every
reader treats it as "say nothing". Filling it with today's inputs would be
worse than useless — it would report "nothing changed" about a scenario whose
inputs are the very reason its check is failing.
"""

import json
import logging
import re

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

#: "Certification test (template vn_complete_2026 v1.0)" — written by
#: `_seed_sample_tests`, and the only record a sample keeps of where it is from.
_FROM_TEMPLATE = re.compile(r'\(template\s+([A-Za-z0-9_.-]+)\s', re.I)


def migrate(cr, version):
    if not version or not table_exists(cr, 'hr_formula_sample_data'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Sample = env['hr.formula.sample.data'].sudo().with_context(
        active_test=False)
    Template = env['hr.formula.config.template'].sudo()

    todo = Sample.search([('expected_confirmed', '=', True)]).filtered(
        lambda s: not _loads(s.expected_inputs_json))
    if not todo:
        return

    personas = {}       # template code -> {scenario name: inputs}
    filled = unknown = 0
    for sample in todo:
        match = _FROM_TEMPLATE.search(sample.description or '')
        code = match.group(1) if match else ''
        if not code:
            unknown += 1
            continue
        if code not in personas:
            personas[code] = _personas_of(Template, code)
        inputs = personas[code].get(sample.name or '')
        if inputs is None:
            unknown += 1
            continue
        try:
            sample.expected_inputs_json = json.dumps(inputs)
            filled += 1
        except Exception:                           # noqa: BLE001
            _logger.warning(
                "Could not record the agreed inputs of sample %s", sample.id,
                exc_info=True)
            unknown += 1

    _logger.info(
        "Sample scenarios — %s now remember the inputs their expected numbers "
        "were agreed against, %s could not be matched to a starter and stay "
        "silent rather than guessing", filled, unknown)


def _personas_of(Template, code):
    template = Template.search([('code', '=', code)], limit=1)
    if not template:
        return {}
    out = {}
    try:
        for test in template._sample_tests() or []:
            name = test.get('name')
            if name:
                out[name] = test.get('inputs') or {}
    except Exception:                               # noqa: BLE001
        _logger.warning("Starter %s could not be read", code, exc_info=True)
    return out


def _loads(raw):
    try:
        value = json.loads(raw or '{}')
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}
