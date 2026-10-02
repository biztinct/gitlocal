# License MIT (https://opensource.org/licenses/MIT).

from . import models
from . import controllers
from . import translate

MODULE = "_web_debranding"


def uninstall_hook(env):
    """Odoo 19 compatible uninstall hook - takes env directly."""
    env["ir.model.data"]._module_data_uninstall([MODULE])
