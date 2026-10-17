# Copyright 2022 Ivan Yelizariev <https://twitter.com/yelizariev>
# License MIT (https://opensource.org/licenses/MIT).
# License OPL-1 (https://www.odoo.com/documentation/user/14.0/legal/licenses/licenses.html#odoo-apps) for derivative work.
from odoo import api, models

from .ir_translation import debrand


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @api.model
    def _get_translations_for_webclient(self, *args, **kwargs):
        translations_per_module, lang_params = super(
            IrHttp, self
        )._get_translations_for_webclient(*args, **kwargs)

        # ODOO 19 COMPATIBILITY -- do not "simplify" this back to an in-place
        # `message["id"] = ...` loop.
        #
        # Since Odoo 19 the super() call hands back entries straight out of the
        # PROCESS-WIDE translation cache, wrapped in `ReadonlyDict`
        # (`odoo/tools/translate.py`, `CodeTranslations._load_web_translations`).
        # Assigning into them raised
        #     TypeError: 'ReadonlyDict' object does not support item assignment
        # so `/web/webclient/translations?lang=<any non-English>` answered 500,
        # the web client's boot rejected at fetchTranslations, and the whole
        # backend was English-only on any database with a second language
        # installed. (en_US never crashed only because it carries no .po rows,
        # so the loop body never ran.) The read-only wrapper is deliberate: the
        # cache is shared by every database served by this worker, so mutating
        # it in place would have leaked one database's debranding into all of
        # them. We therefore build a fresh, plain-dict catalogue and leave the
        # cached objects alone.
        #
        # Only `string` -- the text the user reads -- is rewritten. `id` is the
        # msgid, and the web client uses it as the LOOKUP KEY
        # (`localization_service.js`: `terms[addon][message.id] = message.string`),
        # i.e. it is the literal that `_t()` is called with in the JS sources.
        # Rewriting it would silently drop the translation of every term that
        # happens to contain the vendor name.
        debranded_per_module = {}
        for module_key, module_vals in translations_per_module.items():
            messages = module_vals.get("messages") or ()
            debranded_per_module[module_key] = dict(
                module_vals,
                messages=[
                    dict(message, string=debrand(self.env, message.get("string", "")))
                    for message in messages
                ],
            )

        return debranded_per_module, lang_params
