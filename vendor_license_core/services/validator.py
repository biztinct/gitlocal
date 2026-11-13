# -*- coding: utf-8 -*-
"""
License Validator

Reads /opt/vendor_license/license.json, verifies:
1. File exists and is valid JSON
2. RSA signature is authentic
3. Hardware fingerprint matches
4. License has not expired (with 7-day grace)
5. Employee count is within limit
"""
import json
import os
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

LICENSE_PATH = '/opt/vendor_license/license.json'
GRACE_PERIOD_DAYS = 7

# Status constants
STATUS_VALID = 'valid'
STATUS_GRACE = 'grace'
STATUS_EXPIRED = 'expired'
STATUS_INVALID = 'invalid'
STATUS_MISSING = 'missing'
STATUS_TAMPERED = 'tampered'
STATUS_FINGERPRINT = 'fingerprint_mismatch'
STATUS_OVER_LIMIT = 'over_employee_limit'


def validate_license(employee_count=None):
    """
    Validate the license file and return a status dict.

    Args:
        employee_count: current number of active employees (optional).
                        If None, employee count check is skipped.

    Returns:
        dict with keys:
            status: one of the STATUS_* constants
            ok: bool — True if module operations should be allowed
            message: human-readable description
            license: parsed license dict (if file was readable)
            grace_days_left: int (only if status == 'grace')
    """
    result = {
        'status': STATUS_MISSING,
        'ok': False,
        'message': '',
        'license': {},
        'grace_days_left': 0,
    }

    # ── Step 1: Read file ──
    if not os.path.isfile(LICENSE_PATH):
        result['message'] = (
            f'License file not found at {LICENSE_PATH}. '
            'Contact your vendor for license activation.'
        )
        _logger.warning("License file missing: %s", LICENSE_PATH)
        return result

    try:
        with open(LICENSE_PATH, 'r') as f:
            license_data = json.load(f)
    except (json.JSONDecodeError, IOError, OSError) as e:
        result['status'] = STATUS_INVALID
        result['message'] = f'Cannot read license file: {e}'
        _logger.error("License file read error: %s", e)
        return result

    result['license'] = license_data

    # ── Step 2: Verify RSA signature ──
    signature = license_data.get('signature')
    if not signature:
        result['status'] = STATUS_TAMPERED
        result['message'] = 'License file has no signature. File may be tampered.'
        return result

    from .crypto import verify_signature
    if not verify_signature(license_data, signature):
        result['status'] = STATUS_TAMPERED
        result['message'] = (
            'License signature is invalid. '
            'The file may have been modified. Contact your vendor.'
        )
        _logger.warning("License signature verification FAILED")
        return result

    # ── Step 3: Check hardware fingerprint ──
    from .fingerprint import get_fingerprint
    server_fp = get_fingerprint()
    license_fp = license_data.get('fingerprint_hash', '')

    if server_fp != license_fp:
        result['status'] = STATUS_FINGERPRINT
        result['message'] = (
            'License is not valid for this server. '
            'Hardware fingerprint does not match. Contact your vendor.'
        )
        _logger.warning(
            "Fingerprint mismatch: server=%s...%s license=%s...%s",
            server_fp[:8], server_fp[-8:],
            license_fp[:8], license_fp[-8:],
        )
        return result

    # ── Step 4: Check expiry (with grace period) ──
    expiry_str = license_data.get('expiry', '')
    try:
        expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        result['status'] = STATUS_INVALID
        result['message'] = f'Invalid expiry date in license: {expiry_str}'
        return result

    today = datetime.now().date()
    if today > expiry_date:
        days_past = (today - expiry_date).days
        if days_past <= GRACE_PERIOD_DAYS:
            grace_left = GRACE_PERIOD_DAYS - days_past
            result['status'] = STATUS_GRACE
            result['ok'] = True  # Still allowed during grace
            result['grace_days_left'] = grace_left
            result['message'] = (
                f'License expired on {expiry_str}. '
                f'Grace period: {grace_left} day(s) remaining. '
                'Please renew immediately.'
            )
            _logger.warning(
                "License in GRACE period: %d days left", grace_left
            )
            return result
        else:
            result['status'] = STATUS_EXPIRED
            result['message'] = (
                f'License expired on {expiry_str} '
                f'({days_past} days ago). Grace period has ended. '
                'Contact your vendor for renewal.'
            )
            _logger.error("License EXPIRED: %d days past expiry", days_past)
            return result

    # ── Step 5: Check employee count ──
    max_employees = license_data.get('max_employees', 0)
    if employee_count is not None and max_employees > 0:
        if employee_count > max_employees:
            result['status'] = STATUS_OVER_LIMIT
            result['ok'] = False
            result['message'] = (
                f'Active employees ({employee_count}) exceed licensed limit '
                f'({max_employees}). Contact your vendor to increase the limit.'
            )
            _logger.warning(
                "Employee limit exceeded: %d / %d",
                employee_count, max_employees
            )
            return result

    # ── All checks passed ──
    result['status'] = STATUS_VALID
    result['ok'] = True
    days_left = (expiry_date - today).days
    emp_label = 'Unlimited employees' if max_employees == 0 else f'Max employees: {max_employees}'
    result['message'] = (
        f'License valid for {license_data.get("customer", "Unknown")}. '
        f'Expires: {expiry_str} ({days_left} days remaining). '
        f'{emp_label}.'
    )
    return result
