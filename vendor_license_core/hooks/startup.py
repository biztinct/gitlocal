# -*- coding: utf-8 -*-
"""
Post-init hook — validates license when Odoo starts up.
"""
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Called after module installation/upgrade. Validates the license."""
    _logger.info("═══ Vendor License: Running startup validation ═══")
    try:
        LicenseState = env['vendor.license.state']
        # Ensure at least one record exists
        record = LicenseState.sudo().search([], limit=1)
        if not record:
            record = LicenseState.sudo().create({'name': 'License Status'})
        result = record.check_license()
        if result.get('ok'):
            _logger.info(
                "═══ Vendor License: %s — %s ═══",
                result['status'].upper(),
                result.get('message', '')[:80]
            )
        else:
            _logger.warning(
                "═══ Vendor License: %s — %s ═══",
                result['status'].upper(),
                result.get('message', '')[:120]
            )
    except Exception as e:
        _logger.error("═══ Vendor License: Startup validation error: %s ═══", e)
