# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""SCHEMECTX P1 — heal every scheme whose stored currency is the wrong money.

`currency_id` is a STORED compute that depended on `country_code` alone, so a
row written while the lookup was broken (SC1: INR ships `active=False`, the
search found nothing, the code fell through to the company's dong) never heals
by itself — the country never changes again.

This walks every configuration, archived ones included, recomputes the field
and logs one line per row that actually moved. Idempotent: a second run
changes nothing. Nothing is activated and no amount is restated — only the
currency stamped on the scheme.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Config = env.get('hr.formula.config')
    if Config is None:
        return
    configs = Config.sudo().with_context(active_test=False).search([])
    if not configs:
        _logger.info("SCHEMECTX P1: no payroll configurations to check.")
        return

    before = {c.id: (c.currency_id.id, c.currency_id.name or '')
              for c in configs}
    # Run the real resolver, then flush it to the table. Assigning inside the
    # compute marks the stored field dirty, which is what makes this land.
    configs._compute_currency_id()
    configs.flush_recordset(['currency_id'])

    changed = 0
    for config in configs:
        old_id, old_name = before.get(config.id, (0, ''))
        new = config.currency_id
        if new.id != old_id:
            changed += 1
            _logger.info(
                "SCHEMECTX P1: scheme %s (%s, country %s) currency %s -> %s",
                config.id, config.name, config.country_code or '-',
                old_name or 'none', new.name or 'none')
    _logger.info(
        "SCHEMECTX P1: checked %s payroll configurations, %s re-stamped.",
        len(configs), changed)
