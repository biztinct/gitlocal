"""Retire the obsolete layout extension; homepage assets belong to the page."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    view = env.ref("pb_website.pb_website_homepage_assets", raise_if_not_found=False)
    if view:
        view.write({"active": False})
