# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
# translate_patch must be imported before any model so the get_translation
# wrapper is in place for the whole registry-load pass.
from . import translate_patch
from . import brand
from . import ir_config_parameter
from . import ir_module_module
from . import ir_ui_view
from . import scrub
from . import res_config_settings
