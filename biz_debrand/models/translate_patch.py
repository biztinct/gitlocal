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

That is also exactly what makes this seam safe to run ERRORS E3-2's product
rule through. `_('Paid by %s') % company.name` has the rewrite applied to
`Paid by %s` and never to `company.name`, so a customer genuinely called
"Payobook Vietnam JSC" survives a database where the product rule is on.

The two languages are asked different questions. In ``en_US`` there is no
catalogue and the msgid is the output, so the cheap pre-filter runs on the
source. In every other language the catalogue entry is resolved FIRST and the
pre-filter runs on the *translation*: a string whose English does not name the
vendor may well have a translation that does (``calendar``'s Vietnamese
catalogue, ERRORS E2-2), and filtering on the msgid let every one of those
through.
"""
import logging

from .brand import current_brand, debrand_text, prefilter_for

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
            if not source:
                return original(module, lang, source, args)

            if lang == "en_US":
                # Source language: no catalogue lookup happens, the msgid IS
                # the output, so the cheap pre-filter on the source is both
                # correct and the hot path. Rewrite it before the args are
                # interpolated.
                #
                # The brand is read BEFORE the pre-filter because the filter now
                # depends on it: E3-2's product rule means a msgid naming only
                # the product ("Welcome to Payobook") must not be skipped.
                # current_brand() is a dict lookup, so the hot path is unchanged
                # in shape. It fails open — an unprimed cache (very early boot)
                # leaves the string alone rather than opening a cursor.
                triple = current_brand()
                if not triple:
                    return original(module, lang, source, args)
                brand, website, product = triple
                if not prefilter_for(brand, product).search(source):
                    return original(module, lang, source, args)
                return original(
                    module, lang, debrand_text(source, brand, website, product), args
                )

            # Translated language: the SOURCE is the wrong thing to ask.
            # `Synchronize your calendar with Google Calendar` does not name the
            # vendor — its Vietnamese translation does
            # (`Đồng bộ lịch của bạn trên Odoo với Lịch Google`), and a
            # pre-filter on the msgid never let it reach the rewrite. So resolve
            # the catalogue entry for the ORIGINAL msgid first (that is what the
            # .po lookup hits) and put the question to the RESULT.
            #
            # get_python_translations returns a per-(module, lang) dict held in
            # memory by CodeTranslations, so this is a dict `get`, not a query.
            translated = tr_mod.code_translations.get_python_translations(module, lang).get(
                source, source
            )
            triple = current_brand()
            if not triple:
                return original(module, lang, source, args)
            brand, website, product = triple
            if not translated or not prefilter_for(brand, product).search(translated):
                # Nothing to rewrite in either language: hand the ORIGINAL msgid
                # back untouched so the normal lookup path runs exactly as it
                # did before this patch existed.
                return original(module, lang, source, args)
            # Pass the debranded translation back in as the msgid: the second
            # lookup misses and returns it unchanged, and the original still
            # handles markup / lazy / list argument formatting.
            return original(
                module, lang, debrand_text(translated, brand, website, product), args
            )
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
