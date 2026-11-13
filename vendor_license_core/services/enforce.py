# -*- coding: utf-8 -*-
"""
@require_license Decorator

Wraps model methods so they check for a valid license before executing.
If the license is invalid/expired/missing, raises UserError.
"""
import functools
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# In-memory cache to avoid hitting disk on every single call
_cache = {'result': None, 'checked_at': None}
_CACHE_TTL_SECONDS = 300  # Re-check every 5 minutes


def require_license(func):
    """
    Decorator for model methods that require a valid vendor license.

    Usage:
        from vendor_license_core.services.enforce import require_license

        class HrPayslip(models.Model):
            _inherit = 'hr.payslip'

            @require_license
            def compute_sheet(self):
                return super().compute_sheet()
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        import time
        now = time.time()

        # Use cached result if recent
        if (_cache['result'] is not None and
                _cache['checked_at'] and
                now - _cache['checked_at'] < _CACHE_TTL_SECONDS):
            result = _cache['result']
        else:
            from .validator import validate_license
            # Get employee count from the database
            try:
                emp_count = self.env['hr.employee'].sudo().search_count(
                    [('active', '=', True)]
                )
            except Exception:
                emp_count = None

            result = validate_license(employee_count=emp_count)
            _cache['result'] = result
            _cache['checked_at'] = now

        if not result.get('ok', False):
            _logger.error(
                "License enforcement blocked %s.%s: %s",
                self._name, func.__name__, result.get('message', '')
            )
            raise UserError(
                "⚠️ License Validation Failed\n\n"
                f"{result.get('message', 'License is not valid.')}\n\n"
                "Please contact your software vendor for license assistance."
            )

        # License OK — log grace warning if applicable
        if result.get('status') == 'grace':
            _logger.warning(
                "License GRACE: %s — grace_days_left=%d",
                func.__name__, result.get('grace_days_left', 0)
            )

        return func(self, *args, **kwargs)

    return wrapper


def clear_license_cache():
    """Clear the in-memory license cache (e.g. after updating license file)."""
    _cache['result'] = None
    _cache['checked_at'] = None
