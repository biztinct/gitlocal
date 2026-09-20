# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""Debrand server-rendered QWeb (website, portal, reports, webclient shell).

``web_debranding`` patches ``ir.ui.view.get_combined_arch``, which covers
*backend* form/list arches. Server-side QWeb does not go through it — it loads
templates via ``ir.qweb._preload_trees`` -> ``ir.ui.view._get_view_etrees``
(ir_qweb.py:1229). That is why strings like the offline splash
("Odoo will load as soon as you're back online"), ``alt="Odoo logo"`` and
``<meta name="generator" content="Odoo">`` survived every previous pass.

``_get_view_etrees`` is the one seam every server-rendered template passes
through, and it sits *before* ``_generate_code_cached``, so the rewrite is paid
once per template per registry rather than once per render.
"""
import logging

from odoo import models

from .brand import debrand_tree, source_brand

_logger = logging.getLogger(__name__)


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    def _get_view_etrees(self):
        trees = super()._get_view_etrees()
        if not trees:
            return trees
        try:
            # A template is SOURCE, so the product rule applies here (E3-2).
            brand, website, product = source_brand(self.env)
            for tree in trees:
                debrand_tree(tree, brand, website, product)
        except Exception:
            # Never let branding break template rendering.
            _logger.warning("biz_debrand: QWeb tree debrand failed", exc_info=True)
        return trees
