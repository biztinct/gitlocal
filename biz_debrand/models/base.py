# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
r"""Debrand the BACKEND view arch — the one path server-rendered QWeb never takes.

ERRORS E3-1. ``ir_ui_view._get_view_etrees`` (see ir_ui_view.py) is the seam for
server-rendered QWeb only. A form / list / settings arch reaches the web client
through ``base.get_view`` instead, and ``_get_view_etrees`` never sees it — so a
``help=`` or a text node written into a settings view's XML is covered by
neither of biz_debrand's existing view seams.

``web_debranding`` does override ``base.get_view``, and runs its own regex over
the raw arch STRING. Measured on ``rztest`` 2026-09-11, that is not enough:

1. Its word rule is ``\b(?<!\.)odoo(?!\.\S|\s?=|\w|\[)\b``. The ``(?!\.\S)``
   guard was written to protect the JS namespace (``odoo.define``), but it also
   refuses any sentence that ENDS in the vendor name whenever the next character
   is not whitespace — which inside an arch it never is, because the next
   character is ``<``. The Vietnamese Settings page therefore rendered
   ``Cho phép người dùng đăng nhập/xuất từ Odoo.</span>`` verbatim, while the
   very same sentence handed to the very same function WITHOUT its closing tag
   came back correctly rewritten. That is the whole of the E3-1 bug.
2. It has no rule for ``OdooBot`` (its ``(?!\w)`` guard refuses it), none for
   ``Odoo S.A.``, and none of the whole-sentence replacements E2 added.

So the arch is walked here with the canonical ``debrand_tree`` — the same walker
every other seam uses, with the same guarantees (ER1): prose text and
whitelisted prose attributes only; ``t-`` expressions, ``domain``/``context``
expressions and ``<pre>``/``<code>`` bodies left exactly as they are.

Cost: ``get_view`` already parses and re-serialises the arch on every call
(``ir_ui_view.py:3170``), so the extra pass is a parse only when the string
mentions a name we rewrite at all, and a re-serialise only when something
changed.

An arch is SOURCE — every value a customer typed arrives through an expression
attribute this walker skips — so this is one of the seams that carries E3-2's
product rule.
"""
import logging

from lxml import etree

from odoo import models

from .brand import debrand_tree, prefilter_for, source_brand

_logger = logging.getLogger(__name__)


class Base(models.AbstractModel):
    _inherit = "base"

    def get_view(self, view_id=None, view_type="form", **options):
        result = super().get_view(view_id=view_id, view_type=view_type, **options)
        arch = result.get("arch") if isinstance(result, dict) else None
        if not arch or not isinstance(arch, str):
            return result
        try:
            # An arch is SOURCE, so the product rule applies here (E3-2).
            brand, website, product = source_brand(self.env)
            if not prefilter_for(brand, product).search(arch):
                return result
            tree = etree.fromstring(arch)
            if not debrand_tree(tree, brand, website, product):
                return result
            result = dict(result)
            result["arch"] = etree.tostring(tree, encoding="unicode")
        except Exception:
            # Branding must never stop a view from opening.
            _logger.warning("biz_debrand: view arch debrand failed", exc_info=True)
        return result
