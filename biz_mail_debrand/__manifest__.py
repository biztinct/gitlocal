# Part of biz_mail_debrand — portable outgoing-email white-label layer.
# License LGPL-3.
{
    "name": "Business Mail Debranding",
    "version": "19.0.1.0.0",
    "category": "Debranding",
    "summary": "Send-time catch-all that rewrites 'Odoo' in every outgoing "
               "email (subject, body, from, headers), scrubs stored mail "
               "templates and disables the Odoo periodic digest. Brand is "
               "resolved from config parameters — no hardcoded name.",
    "author": "biz_debrand",
    "website": "https://example.com",
    "license": "LGPL-3",
    # Deliberately NO dependency on biz_debrand / web_debranding: their
    # brand parameters are read if present, with graceful fallbacks, so the
    # module drops into any Odoo 19 database.
    "depends": [
        "mail",
        "digest",
    ],
    "data": [
        "data/apply.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
