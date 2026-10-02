# -*- coding: utf-8 -*-
{
    "name": "Payobook Zoho SSO",
    "summary": "Secure Zoho Accounts single sign-on for Payobook",
    "description": """
Sign in to Payobook with a Zoho account.

Authorization Code with PKCE, and the sign-in flow never reuses or stores the
access tokens the payroll import holds. An administrator switches it on in
General Settings, registers the callback this system shows them in the Zoho
API Console, and chooses whether a verified Zoho email may link itself to an
existing Payobook user or must wait for approval.

The engineering README beside this file has the full set-up walkthrough.
""",
    "version": "19.0.1.0.1",
    "category": "Administration/Authentication",
    "license": "LGPL-3",
    "author": "Payobook",
    "website": "https://www.payobook.com",
    "depends": ["base_setup", "web"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/res_config_settings_views.xml",
        "views/zoho_sso_identity_views.xml",
        "views/zoho_sso_templates.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
