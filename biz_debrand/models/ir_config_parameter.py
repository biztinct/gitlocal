# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""Keep the process-level brand cache in step with the database.

The Python ``_()`` patch runs on a hot path with no ``env`` in scope, so it
reads the brand from a per-database process cache instead of the ORM. This
model primes that cache on every registry load and invalidates it whenever a
branding parameter is written.
"""
import logging

from odoo import api, models

from . import brand as brand_mod

_logger = logging.getLogger(__name__)

WATCHED_KEYS = (
    "biz_debrand.brand_name",
    "biz_debrand.brand_website",
    "web_debranding.new_name",
    "web_debranding.new_website",
)


class IrConfigParameter(models.Model):
    _inherit = "ir.config_parameter"

    def _register_hook(self):
        # Runs once per database on every registry load, before requests are
        # served — so current_brand() is primed by the time anything renders.
        res = super()._register_hook()
        brand_mod.cache_brand(self.env)
        return res

    def _biz_debrand_refresh(self):
        brand_mod.invalidate(self.env.cr.dbname)
        brand_mod.cache_brand(self.env)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if any(v.get("key") in WATCHED_KEYS for v in vals_list):
            self._biz_debrand_refresh()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(rec.key in WATCHED_KEYS for rec in self):
            self._biz_debrand_refresh()
        return res
