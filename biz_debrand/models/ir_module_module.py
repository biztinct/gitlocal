# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""Debrand the Apps list.

``ir_module_module.shortdesc`` / ``summary`` / ``description`` are record
*data*, not field metadata, so the ``fields_get`` debranding in
``web_debranding`` never reached them: the Apps list still advertised
"Odoo 19 HR Payroll", "OdooBot", "Remove Odoo Branding from Portal" and so on
(12 installed modules on the audited database).

Done at read time rather than by rewriting the rows because module metadata is
re-imported from every ``__manifest__.py`` on each ``-u``; a stored scrub would
silently rot the first time a single core module is upgraded.

The hook is ``_read_format``, NOT ``read``: in Odoo 19 ``search_read`` calls
``records._read_format(...)`` directly (orm/models.py:5785) and never goes
through ``read()``, so a ``read()`` override silently misses the Apps kanban —
which is exactly how it was caught here. ``read()`` and ``web_read`` both land
on ``_read_format`` too, so this one override covers every path.
"""
import logging

from odoo import models

from .brand import brand_for_env, debrand_text

_logger = logging.getLogger(__name__)

BRANDED_FIELDS = ("shortdesc", "summary", "description")


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    def _read_format(self, fnames, load="_classic_read"):
        result = super()._read_format(fnames, load=load)
        if not result:
            return result
        if fnames and not any(f in fnames for f in BRANDED_FIELDS):
            return result
        try:
            brand, website = brand_for_env(self.env)
        except Exception:
            _logger.warning("biz_debrand: Apps-list debrand failed", exc_info=True)
            return result
        for values in result:
            for fname in BRANDED_FIELDS:
                value = values.get(fname)
                if isinstance(value, str):
                    values[fname] = debrand_text(value, brand, website)
        return result
