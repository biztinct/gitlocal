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

        for _module_key, module_vals in translations_per_module.items():
            messages = module_vals.get("messages", [])
            for message in messages:
                message["id"] = debrand(self.env, message.get("id", ""))
                message["string"] = debrand(self.env, message.get("string", ""))

        return translations_per_module, lang_params
