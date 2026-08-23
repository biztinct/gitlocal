# -*- coding: utf-8 -*-
{
    "name": "Payobook Zoho SSO",
    "summary": "Secure Zoho Accounts single sign-on for Payobook",
    "version": "19.0.1.0.0",
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
