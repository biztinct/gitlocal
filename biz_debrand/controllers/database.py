# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
import re

from odoo.http import request
from odoo.addons.web.controllers.database import Database

# Server-level fallback brand (the database manager lists ALL databases on the
# server, so it is inherently not per-database).
FALLBACK_BRAND = "BizApp"
FALLBACK_WEBSITE = "https://example.com"
BRAND_LOGO = "/biz_debrand/static/src/img/brand_icon.png"


class BizDebrandDatabase(Database):
    """Debrand the /web/database/{manager,selector} pages.

    Served pre-login (auth='none') from static qweb.html files, bypassing the
    normal translation/debranding pipeline — so we post-process the rendered
    HTML instead of forking the core template.
    """

    def _biz_debrand_brand(self):
        try:
            icp = request.env["ir.config_parameter"].sudo()
            return (
                icp.get_param("web_debranding.new_name") or FALLBACK_BRAND,
                icp.get_param("web_debranding.new_website") or FALLBACK_WEBSITE,
            )
        except Exception:
            # No database selected (multi-db) → config params unavailable.
            return FALLBACK_BRAND, FALLBACK_WEBSITE

    def _render_template(self, **d):
        html = super()._render_template(**d)
        if not isinstance(html, str):
            return html
        brand, website = self._biz_debrand_brand()
        html = html.replace("/web/static/img/logo2.png", BRAND_LOGO)
        html = html.replace("/web/static/img/favicon.ico", BRAND_LOGO)
        html = re.sub(r"https?://(www\.)?odoo\.com[^\"'> ]*", website, html, flags=re.IGNORECASE)
        html = re.sub(r"\bOdoo\b", brand, html)
        return html
