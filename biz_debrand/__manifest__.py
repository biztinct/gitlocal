# Part of biz_debrand — portable Odoo 19 white-label layer.
# License LGPL-3.
{
    "name": "Business Debranding",
    "version": "19.0.1.0.0",
    "category": "Debranding",
    "summary": "Portable white-label layer: replaces every user-visible 'Odoo' "
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
        "data/apply_brand.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "biz_debrand/static/src/xml/notification_alert.xml",
            "biz_debrand/static/src/xml/res_config_edition.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
