"""Refresh automatic metadata after disambiguating event-based payments."""
import logging
from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for config in env['hr.formula.config'].search([]):
        if not config.rule_ids:
            continue
        try:
            with cr.savepoint():
                result = config._classify_component_treatment()
                _logger.info('TREATMENT schema %s: %s rows refreshed', config.id, result['changed'])
        except Exception:
            _logger.exception('TREATMENT schema %s retained its previous metadata; needs review', config.id)
