# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
import base64
import logging

from odoo import api, fields, models
from odoo.tools import file_open

_logger = logging.getLogger(__name__)

# Neutral defaults — override them in Settings → General Settings → Branding
# (or pre-seed the biz_debrand.* config parameters before install).
DEFAULT_BRAND = "BizApp"
DEFAULT_WEBSITE = "https://example.com"
DEFAULT_THEME_COLOR = "#1565C0"

# Self-contained brand icon shipped with this module. Replace
# static/src/img/brand_icon.png with your own logo (square PNG recommended).
# Optional: if the file is missing, text debranding still applies and the
# favicon/avatar/DB-manager-logo steps are skipped gracefully.
BRAND_ICON = "biz_debrand/static/src/img/brand_icon.png"


def _read_icon_b64():
    try:
        with file_open(BRAND_ICON, "rb") as f:
            return base64.b64encode(f.read())
    except Exception:
        _logger.info("biz_debrand: no brand icon at %s — skipping image branding", BRAND_ICON)
        return None


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    biz_debrand_brand_name = fields.Char(
        string="Brand Name",
        config_parameter="biz_debrand.brand_name",
        help="Product name shown everywhere in place of Odoo "
             "(browser title, backend, emails, bot, database manager).",
    )
    biz_debrand_brand_website = fields.Char(
        string="Brand Website",
        config_parameter="biz_debrand.brand_website",
        help="Replaces odoo.com links across the UI.",
    )
    biz_debrand_theme_color = fields.Char(
        string="Brand Theme Color",
        config_parameter="biz_debrand.theme_color",
        help="Brand color (hex, e.g. #1565C0). Consumed by integrations "
             "such as a PWA if you wire one up.",
    )

    # ------------------------------------------------------------------
    # Seeding — runs on install AND every upgrade (via data <function>),
    # and on every Save of the Branding settings. Idempotent.
    # ------------------------------------------------------------------
    @api.model
    def _biz_debrand_apply_brand(self):
        icp = self.env["ir.config_parameter"].sudo()

        brand = (icp.get_param("biz_debrand.brand_name") or DEFAULT_BRAND).strip()
        website = (icp.get_param("biz_debrand.brand_website") or DEFAULT_WEBSITE).strip()
        theme_color = (icp.get_param("biz_debrand.theme_color") or DEFAULT_THEME_COLOR).strip()

        # Canonical brand params (source of truth).
        icp.set_param("biz_debrand.brand_name", brand)
        icp.set_param("biz_debrand.brand_website", website)
        icp.set_param("biz_debrand.theme_color", theme_color)

        # Drive the installed debranding suite.
        icp.set_param("web_debranding.new_name", brand)
        icp.set_param("web_debranding.new_title", brand)
        icp.set_param("web_debranding.new_website", website)
        icp.set_param("web_debranding.new_documentation_website", website + "/documentation/")

        icon_b64 = _read_icon_b64()

        # Favicon on every company (web_debranding only defaults it for new ones).
        if icon_b64:
            for company in self.env["res.company"].sudo().search([]):
                try:
                    company.favicon = icon_b64
                except Exception:
                    _logger.warning("biz_debrand: favicon on %s failed", company.name, exc_info=True)

        # Website identity (login/portal/website tab title + favicon).
        if "website" in self.env:
            for site in self.env["website"].sudo().search([]):
                try:
                    vals = {"name": brand}
                    if icon_b64:
                        vals["favicon"] = icon_b64
                    site.write(vals)
                except Exception:
                    _logger.warning("biz_debrand: website branding on %s failed", site.name, exc_info=True)

        # OdooBot → brand bot. Name always; avatar best-effort.
        bot = self.env.ref("base.partner_root", raise_if_not_found=False)
        if bot:
            bot.sudo().write({"name": brand})
            if icon_b64:
                try:
                    bot.sudo().write({"image_1920": icon_b64})
                except Exception:
                    _logger.warning("biz_debrand: bot avatar failed", exc_info=True)

        _logger.info("biz_debrand: white-label identity applied as %r", brand)
        return True

    def set_values(self):
        super().set_values()
        self._biz_debrand_apply_brand()
