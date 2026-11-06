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
    "biz_debrand.product_name",
    "biz_debrand.powered_by",
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
        # WHITELABEL 2026-10-31. The stored-row scrub runs while THIS module
        # upgrades — 121st of 266 on rize — and every module loaded after it
        # re-imports its own data from source: cron names, group comments,
        # model descriptions, constraint messages, seeded rule notes. Measured
        # on 2026-10-31: 1,269 rows rewritten, then 70-odd written back by the
        # modules that followed. So on a registry load that UPGRADED anything
        # the scrub runs once more here, at the very end, after the last
        # module. A plain server start (nothing updated) pays nothing, and the
        # scrub is idempotent, so a second pass over clean rows is a handful
        # of pre-filtered SELECTs. Wrapped: a scrub must never stop a boot.
        if getattr(self.env.registry, "updated_modules", None):
            try:
                self.env["res.config.settings"]._biz_debrand_scrub_data()
            except Exception:  # noqa: BLE001
                _logger.warning("biz_debrand: post-upgrade scrub skipped", exc_info=True)
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
