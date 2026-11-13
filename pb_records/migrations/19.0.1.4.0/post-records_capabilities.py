from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    parent = env.ref('pb_people_hub.item_people', raise_if_not_found=False)
    if parent:
        group = env.ref('pb_records.group_records_viewer')
        if 'pb.role.profile' in env.registry:
            from odoo.addons.biz_access.models.role_assignments import INTERNAL
            parent = parent.with_context(_pb_access_internal=INTERNAL)
        parent.sudo().write({'groups_id': [(4, group.id)]})
    if 'pb.role.profile' in env.registry:
        from odoo.addons.biz_access.hooks import ensure_catalogue
        ensure_catalogue(env)
