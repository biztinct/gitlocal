"""Refresh only this module's website editor copies after its initial install."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {'lang': 'en_US'})
    for xmlid in ('homepage', 'login_layout'):
        source = env.ref('sudima_website.' + xmlid)
        copies = env['ir.ui.view'].with_context(active_test=False).search([
            ('key', '=', source.key),
            ('website_id', '!=', False),
            ('id', '!=', source.id),
        ])
        for copy in copies:
            copy.write({'arch_db': source.arch_db, 'name': source.name})
