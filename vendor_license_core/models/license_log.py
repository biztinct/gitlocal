# -*- coding: utf-8 -*-
"""
License Audit Log — records every validation event.
"""
from odoo import models, fields


class VendorLicenseLog(models.Model):
    _name = 'vendor.license.log'
    _description = 'Vendor License Audit Log'
    _order = 'create_date desc'

    event_type = fields.Selection([
        ('validate_ok', 'Validation Passed'),
        ('validate_fail', 'Validation Failed'),
        ('expired', 'License Expired'),
        ('tamper', 'Tampering Detected'),
        ('fingerprint_mismatch', 'Fingerprint Mismatch'),
    ], string='Event', required=True)

    details = fields.Text('Details')
    fingerprint_hash = fields.Char('Fingerprint')
