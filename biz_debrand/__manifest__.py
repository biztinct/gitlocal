# Part of biz_debrand — portable Odoo 19 white-label layer.
# License LGPL-3.
{
    "name": "Business Debranding",
    "description": """
One knob that puts your brand everywhere a person can see it.

Set the brand name, website and colour in General Settings and this layer
applies them across the backend, the login page, the browser tab and its icon,
the assistant, the website and portal, emails, the notification banner, the
copyright line and the database manager page. It carries no project-specific
dependency and no name of its own: an unconfigured install says so out loud
rather than pretending to be somebody.

Seeding runs on install, on every upgrade and on every Save, and it is safe to
repeat. Nothing in the platform's own source is edited. The engineering README
beside this file explains how it is put together and what it deliberately
leaves alone.
""",
    "version": "19.0.2.5.0",
    "category": "Debranding",
    "summary": "Portable white-label layer: replaces every user-visible vendor "
               "reference with a configurable brand. No project dependencies.",
    "author": "biz_debrand",
    "website": "https://example.com",
    "license": "LGPL-3",
    # Orchestrates the debranding suite (the engine). web_debranding is a
    # commercial (OPL-1) module; the others are OCA. The target database must
    # have these installed/available. `website` is pulled in via
    # website_debranding. No project-specific modules are required.
    "depends": [
        "base_setup",
        "web_debranding",
        "mail_debranding",
        "portal_debranding",
        "website_debranding",
        "disable_odoo_online",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/brand_layout.xml",
        "data/apply_brand.xml",
    ],
    "assets": {
        # The runtime patches must reach every JS context: the backend web
        # client and the login/portal/website pages both carry _t() strings
        # naming the vendor. Both bundles include web/static/src/core/**, so
        # the two imports resolve in each.
        "web.assets_backend": [
            "biz_debrand/static/src/js/biz_debrand_runtime.js",
            "biz_debrand/static/src/xml/notification_alert.xml",
            "biz_debrand/static/src/xml/res_config_edition.xml",
        ],
        "web.assets_frontend": [
            "biz_debrand/static/src/js/biz_debrand_runtime.js",
        ],
        "web.assets_unit_tests": [
            "biz_debrand/static/tests/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
