# Part of biz_debrand — portable Odoo 19 white-label layer.
# License LGPL-3.
{
    "name": "Business Debranding",
    "version": "19.0.2.2.0",
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
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
