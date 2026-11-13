from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    website = env['website'].search([('domain', 'ilike', 'biztinct.com')], limit=1)
    if website:
        env['ir.config_parameter'].set_param('biztinct_website.website_id', website.id)
        website.write({'name': 'Biztinct'})
