# Part of pb_theme — the Payobook overlay on biz_theme.
from odoo import api, models

PAYOBOOK_LOGO = "/pb_theme/static/src/img/payobook_logo.png"


class IrConfigParameter(models.Model):
    _inherit = "ir.config_parameter"

    @api.model
    def _pb_theme_seed_loader_logo(self):
        """Give the loading animation the Payobook mark — but ONLY where the
        brand IS Payobook.

        biz_theme's loading language (splash, long-wait mark) animates whatever
        ``biz_debrand.loader_logo_url`` points at and never knows a product
        logo of its own. This overlay seeds that address on install/upgrade
        when it is empty, unless the database is white-labelled (its brand
        name differs from the product name it replaces): a tenant such as
        rize keeps its own picture or, with none, its brand name as text.
        Owner rule 2026-10-11: a white-labelled customer never sees our mark.
        """
        icp = self.sudo()
        if (icp.get_param("biz_debrand.loader_logo_url") or "").strip():
            return False
        brand = (icp.get_param("biz_debrand.brand_name") or "").strip()
        product = (icp.get_param("biz_debrand.product_name") or "").strip()
        if brand and product and brand.lower() != product.lower():
            return False
        icp.set_param("biz_debrand.loader_logo_url", PAYOBOOK_LOGO)
        return True
