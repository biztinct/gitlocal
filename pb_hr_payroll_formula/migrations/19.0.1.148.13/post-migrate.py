"""Preserve existing group choices; repair only automatic treatment metadata."""
import logging
from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Earlier versions had no origin marker: a nonblank saved group may be a
    # deliberate choice. Preserve it; Constant was the importer's fixed label.
    cr.execute("""UPDATE hr_formula_rule
        SET imported_component_type = component_type,
            component_type_source = CASE
                WHEN coalesce(component_type, '') NOT IN ('', 'Constant') THEN 'legacy'
                ELSE 'auto' END""")
    env['hr.formula.rule'].invalidate_model()
    for config in env['hr.formula.config'].search([]):
        if not config.rule_ids:
            continue
        try:
            with cr.savepoint():
                result = config._classify_component_treatment()
                _logger.info('TREATMENT schema %s: %s rows refreshed%s', config.id,
                             result['changed'], ': ' + result['error'] if result.get('error') else '')
        except Exception:
            _logger.exception('TREATMENT schema %s retained its previous metadata; needs review', config.id)
