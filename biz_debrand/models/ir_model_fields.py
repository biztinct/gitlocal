# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
r"""Field labels, tooltips and selection labels — the canonical rules on top.

ERRORS E3-1. Core asks ``ir.model.fields`` for the translated label and help of
every field it describes (``odoo/orm/fields.py:958`` ``_description_string``,
``:965`` ``_description_help``, ``odoo/orm/fields_selection.py:209``), so these
three methods ARE the seam for everything a tooltip shows.

``web_debranding`` already overrides them, and for a tooltip it mostly works —
measured on ``rztest`` 2026-09-11, all 37 ``ir_model_fields.help`` rows that
name the vendor come back clean. What its rule cannot do is the shapes it was
never taught:

* ``OdooBot``. Its word rule ends ``(?!\w)``, so a vendor name with a letter
  glued to it is refused. ``res.users.odoobot_state`` was therefore labelled
  ``Trạng thái OdooBot`` on every screen that shows a field label.
* ``Odoo S.A.``, and every whole-sentence replacement E2 added (E2-4).

Rather than widen a gutted module's regex, the canonical ``debrand_text`` is
applied on top. It is a no-op for everything ``web_debranding`` already fixed
(the pre-filter no longer matches), so this layer only ever catches the
remainder.

Cached with the same key as the layer below it — ``_description_help`` is called
once per FIELD, and a model can carry a thousand of them, so an uncached pass
over the whole dict would be quadratic. The cache lives in the registry's
``default`` cache, which ``_biz_debrand_apply_brand`` already clears on every
brand save (see scrub.py) and which a registry reload rebuilds from scratch.
"""
import logging

from odoo import api, models, tools

from .brand import brand_for_env, debrand_text

_logger = logging.getLogger(__name__)


class IrModelFields(models.Model):
    _inherit = "ir.model.fields"

    def _biz_debrand_terms(self, terms):
        """Return a NEW dict with every value run through the canonical rules.

        Never mutates ``terms``: the dict handed up by ``super()`` is itself
        held in an ormcache, and rewriting it in place would poison that cache
        for every other reader.
        """
        try:
            brand, website = brand_for_env(self.env)
        except Exception:
            _logger.warning("biz_debrand: field-term debrand failed", exc_info=True)
            return terms
        return {
            name: debrand_text(value, brand, website) if isinstance(value, str) else value
            for name, value in terms.items()
        }

    @api.model
    @tools.ormcache("self.env.context.get('lang')", "model_name")
    def get_field_string(self, model_name):
        return self._biz_debrand_terms(super().get_field_string(model_name))

    @api.model
    @tools.ormcache("self.env.context.get('lang')", "model_name")
    def get_field_help(self, model_name):
        return self._biz_debrand_terms(super().get_field_help(model_name))

    @api.model
    @tools.ormcache("self.env.context.get('lang')", "model_name", "field_name")
    def get_field_selection(self, model_name, field_name):
        selection = super().get_field_selection(model_name, field_name)
        try:
            brand, website = brand_for_env(self.env)
        except Exception:
            _logger.warning("biz_debrand: selection debrand failed", exc_info=True)
            return selection
        return [
            (value, debrand_text(label, brand, website) if isinstance(label, str) else label)
            for value, label in selection
        ]
