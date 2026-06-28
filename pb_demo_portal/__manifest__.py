# -*- coding: utf-8 -*-
{
    'name': 'Payobook Demo Registration Portal',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'Public demo sign-up: business-email validation, email verification, '
               'password setup, then login to the Demo environment.',
    'description': """
Payobook Demo Registration Portal
=================================
A beautiful public landing where prospects register for the live demo:
  * Fields: Name, Company, Business Email, Mobile, Country, Industry, Company Size.
  * Rejects free/consumer email domains (gmail, outlook, yahoo, ...).
  * Creates a Demo User, sends a verification / set-password email (auth_signup),
    and on completion the visitor logs straight into the demo.
""",
    'author': 'Payobook',
    'license': 'LGPL-3',
    'depends': ['website', 'auth_signup', 'mail', 'pb_demo'],
    'data': [
        'views/demo_portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pb_demo_portal/static/src/scss/demo_portal.scss',
        ],
    },
    'installable': True,
    'application': False,
}
