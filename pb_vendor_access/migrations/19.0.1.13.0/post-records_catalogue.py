from odoo import api, SUPERUSER_ID
from odoo.addons.pb_vendor_access.hooks import ensure_catalogue


def migrate(cr, version):
    ensure_catalogue(api.Environment(cr, SUPERUSER_ID, {}))
