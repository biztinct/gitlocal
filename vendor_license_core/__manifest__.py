# -*- coding: utf-8 -*-
{
    'name': 'Vendor License Core',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'License validation with hardware fingerprinting and RSA signature verification',
    'description': """
        Validates vendor license at startup and daily via cron.
        - Hardware fingerprint (MAC + machine-id + CPU)
        - RSA-4096 signature verification (embedded public key)
        - Employee count enforcement
        - 7-day grace period on expiry
        - Audit logging
    """,
    'author': 'Biztinct Solutions',
    'depends': ['base', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/license_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
