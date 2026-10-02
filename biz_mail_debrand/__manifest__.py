# Part of biz_mail_debrand — portable outgoing-email white-label layer.
# License LGPL-3.
{
    "name": "Business Mail Debranding",
    "description": """
Every email that leaves this system carries YOUR brand.

The vendor's name and links are rewritten at send time in the subject, the
body and the sender address of every outgoing message, the informational
headers that carried it are dropped, the stored email templates are cleaned on
install and on every upgrade, and the periodic summary email nobody asked for
is switched off. The brand is read from configuration, so nothing here has a
name written into it.

Backend deep links are never rewritten, and neither are code tokens or foreign
domains that merely look like the vendor's. The engineering README beside this
file has the detail.
""",
    "version": "19.0.1.0.1",
    "category": "Debranding",
    "summary": "Send-time catch-all that rewrites vendor branding in every outgoing "
               "email (subject, body, from, headers), scrubs stored mail "
               "templates and disables the stock periodic digest. Brand is "
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
