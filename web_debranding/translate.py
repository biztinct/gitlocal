# Copyright 2022-2023 Ivan Yelizariev <https://twitter.com/yelizariev>
# License OPL-1 (https://www.odoo.com/documentation/user/14.0/legal/licenses/licenses.html#odoo-apps)
# Odoo 19 compatibility: Translation internals have changed, monkey-patching disabled
import logging

_logger = logging.getLogger(__name__)

# In Odoo 19, the _ function no longer has _get_translation or _get_cr methods.
# The debranding of translations is handled via other mechanisms (field strings, etc.)
_logger.info("web_debranding: Translation monkey-patching skipped for Odoo 19 compatibility")
