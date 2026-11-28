from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Repair system-import attribution using the existing source's responsible
    # person. Every entry remains scoped to exactly one company; restrictions stay.
    for q in env['survey.question'].search([
        ('pb_bank', '=', True), ('create_uid', '=', SUPERUSER_ID),
        ('pb_bank_state', '=', 'draft'), '|',
        ('pb_bank_origin_id', '!=', False), ('pb_bank_origin_slide_id', '!=', False),
    ]):
        owner = q.pb_bank_origin_id.user_id or q.pb_bank_origin_slide_id.channel_id.user_id
        if owner.company_id:
            q.write({'pb_bank_company_id': owner.company_id.id, 'pb_bank_owner_id': owner.id})
