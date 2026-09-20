# -*- coding: utf-8 -*-
"""
License State — Singleton model holding current license status.
Updated by startup hook and daily cron.
"""
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class VendorLicenseState(models.Model):
    _name = 'vendor.license.state'
    _description = 'Vendor License Status'
    _order = 'id desc'

    name = fields.Char(default='License Status', readonly=True)
    status = fields.Selection([
        ('valid', 'Valid'),
        ('grace', 'Grace Period'),
        ('expired', 'Expired'),
        ('invalid', 'Invalid'),
        ('missing', 'Missing'),
        ('tampered', 'Tampered'),
        ('fingerprint_mismatch', 'Fingerprint Mismatch'),
        ('over_employee_limit', 'Over Employee Limit'),
    ], string='Status', default='missing', readonly=True)

    customer = fields.Char('Customer', readonly=True)
    license_id = fields.Char('License ID', readonly=True)
    expiry = fields.Date('Expiry Date', readonly=True)
    max_employees = fields.Integer('Max Employees', readonly=True)
    max_employees_display = fields.Char(
        'Max Employees', compute='_compute_max_employees_display')

    @api.depends('max_employees')
    def _compute_max_employees_display(self):
        for rec in self:
            rec.max_employees_display = (
                'Unlimited' if rec.max_employees == 0
                else str(rec.max_employees)
            )
    current_employees = fields.Integer('Current Employees', readonly=True)
    grace_days_left = fields.Integer('Grace Days Left', readonly=True)
    last_check = fields.Datetime('Last Checked', readonly=True)
    message = fields.Text('Details', readonly=True)
    fingerprint = fields.Char('Server Fingerprint', readonly=True)

    def check_license(self):
        """Run license validation and update the singleton record."""
        from ..services.validator import validate_license
        from ..services.fingerprint import get_fingerprint
        from ..services.enforce import clear_license_cache

        # Count active employees
        try:
            emp_count = self.env['hr.employee'].sudo().search_count(
                [('active', '=', True)]
            )
        except Exception:
            emp_count = 0

        result = validate_license(employee_count=emp_count)
        lic = result.get('license', {})

        # Parse expiry
        expiry_date = False
        if lic.get('expiry'):
            try:
                from datetime import datetime
                expiry_date = datetime.strptime(
                    lic['expiry'], '%Y-%m-%d'
                ).date()
            except (ValueError, TypeError):
                pass

        vals = {
            'name': 'License Status',
            'status': result['status'],
            'customer': lic.get('customer', ''),
            'license_id': lic.get('license_id', ''),
            'expiry': expiry_date,
            'max_employees': lic.get('max_employees', 0),
            'current_employees': emp_count,
            'grace_days_left': result.get('grace_days_left', 0),
            'last_check': fields.Datetime.now(),
            'message': result['message'],
            'fingerprint': get_fingerprint(),
        }

        # Get or create singleton
        record = self.sudo().search([], limit=1)
        if record:
            record.sudo().write(vals)
        else:
            record = self.sudo().create(vals)

        # Log the event
        event_type = 'validate_ok' if result['ok'] else 'validate_fail'
        if result['status'] == 'tampered':
            event_type = 'tamper'
        elif result['status'] == 'fingerprint_mismatch':
            event_type = 'fingerprint_mismatch'
        elif result['status'] == 'expired':
            event_type = 'expired'

        self.env['vendor.license.log'].sudo().create({
            'event_type': event_type,
            'details': result['message'],
            'fingerprint_hash': get_fingerprint(),
        })

        # Clear the enforcement cache so next @require_license picks up new state
        clear_license_cache()

        # ── File Integrity Check ──
        try:
            from ..services.integrity import verify_integrity
            integrity = verify_integrity()
            if not integrity['ok']:
                _logger.error("INTEGRITY CHECK FAILED: %s", integrity['message'])
                self.env['vendor.license.log'].sudo().create({
                    'event_type': 'integrity_fail',
                    'details': (
                        f"{integrity['message']}\n"
                        f"Modified: {integrity.get('modified', [])}\n"
                        f"Missing: {integrity.get('missing', [])}"
                    ),
                    'fingerprint_hash': get_fingerprint(),
                })
        except Exception as e:
            _logger.debug("Integrity check skipped: %s", e)

        if result['ok']:
            _logger.info("License check PASSED: %s", result['status'])
        else:
            _logger.error("License check FAILED: %s — %s",
                          result['status'], result['message'])

        return result
