# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""Restore Python-side debranding of translated strings on Odoo 19.

``web_debranding``'s own translation monkey-patch (``web_debranding/translate.py``)
was disabled during the Odoo 19 port — "Translation internals have changed" —
so every ``_()`` / ``_lt()`` / ``env._()`` string containing the vendor name has
been reaching users verbatim. That covers user-facing errors such as
"Odoo is unable to merge the generated PDFs." and
"Odoo is currently processing another module operation.".

Rather than resurrect the removed ``GettextAlias._get_translation`` hook, we
wrap the single funnel that survives in Odoo 19:
``odoo.tools.translate.get_translation(module, lang, source, args)``. Both
``get_text_alias`` (``_``) and ``LazyGettext._translate`` (``_lt``) call it.

Two bindings must be patched: the module attribute, and the *direct* import in
``odoo.orm.environments`` (``from odoo.tools.translate import get_translation``,
environments.py:21) which backs the modern ``self.env._(...)`` idiom.

The vendor name is stripped from the *template*, never from the interpolated
arguments — so a record whose own name contains the vendor word is left alone.
"""
import logging

from .brand import HAS_ODOO_RE, current_brand, debrand_text

_logger = logging.getLogger(__name__)

_PATCH_FLAG = "_biz_debrand_patched"


def _install():
    import odoo.orm.environments as env_mod
    import odoo.tools.translate as tr_mod

    original = tr_mod.get_translation
    if getattr(original, _PATCH_FLAG, False):
        return  # already installed in this process

    def get_translation(module, lang, source, args):
        try:
            if not source or not HAS_ODOO_RE.search(source):
                return original(module, lang, source, args)
            pair = current_brand()
            if not pair:
                # Cache not primed (very early boot) — fail open, never raise.
                return original(module, lang, source, args)
            brand, website = pair
            if lang == "en_US":
                # Source language: no catalogue lookup happens, the msgid IS
                # the output. Rewrite it before the args are interpolated.
                return original(module, lang, debrand_text(source, brand, website), args)
            # Translated language: resolve the catalogue entry for the ORIGINAL
            # msgid (so the .po lookup still hits), debrand the result, then let
            # the original handle markup/lazy/list argument formatting. The
            # second lookup misses and returns the string unchanged.
            translated = tr_mod.code_translations.get_python_translations(module, lang).get(
                source, source
            )
            return original(module, lang, debrand_text(translated, brand, website), args)
        except Exception:
            _logger.warning("biz_debrand: translation debrand failed", exc_info=True)
            return original(module, lang, source, args)

    setattr(get_translation, _PATCH_FLAG, True)
    get_translation._biz_debrand_original = original

    tr_mod.get_translation = get_translation
    # environments.py imported the symbol directly; rebind it too or every
    # ``self.env._(...)`` call in core would bypass the patch.
    env_mod.get_translation = get_translation
    _logger.info("biz_debrand: Python translation debranding installed")


_install()
