"""Restore Rize's existing Settings navigation, without changing permissions.

Run in Odoo shell with RIZE_SETTINGS_ARCHIVE pointing to a private directory.
Defaults to rollback; RIZE_SETTINGS_APPLY=1 commits the owner-approved change.
"""
import json
import os
from pathlib import Path
from odoo.addons.biz_access.models.access_common import implied_closure

assert env.cr.dbname == 'rize'
user = env['res.users'].sudo().search([('login', '=', 'ash@biztinct.com')])
assert len(user) == 1 and user.active and user.has_group('base.group_system')
e = env(user=user.id, context=dict(env.context, lang='en_US'))
item = e.ref('pb_settings.item_settings')
role = e.ref('pb_vendor_access.role_tenant_administrator')
assert role.active and item.section_id.active and not item.feature_key
assert not item.active, 'Settings is already active; inspect before changing it.'
assert item.role_ids and not item.groups_id
groups = implied_closure(role.group_ids | role.membership_group_id)
assert e['pb.sidebar.item']._state_for(item, False, groups) == (True, False)
assert e['pb.sidebar.item']._state_for(item, True, user.all_group_ids) == (True, False)
snapshot = item.read(['name', 'active', 'role_ids', 'groups_id', 'restricted',
                      'access_customized', 'section_id'])[0]
root = Path(os.environ['RIZE_SETTINGS_ARCHIVE'])
root.mkdir(mode=0o700, parents=True, exist_ok=True)
assert not (root / 'applied.json').exists()
(root / 'before.json').write_text(json.dumps(snapshot, indent=2))
(root / 'retention.json').write_text(json.dumps({'database': 'rize', 'permanent': True,
                                               'never_auto_delete': True}))
result = e['pb.access'].set_screen_flags(item.id, active=True)
e.flush_all()
after = item.read(list(snapshot.keys() - {'id'}))[0]
assert after == dict(snapshot, active=True, access_customized=True)
sidebar = e['pb.sidebar.item'].get_sidebar_data()
assert any(row['id'] == item.id for section in sidebar for row in section['items'])
assert e['pb.sidebar.item']._state_for(item, False, groups) == (True, False)
apply = os.getenv('RIZE_SETTINGS_APPLY') == '1'
receipt = {'database': 'rize', 'committed': apply, 'actor': user.login,
           'before': snapshot, 'after': after, 'result': result,
           'tenant_admin_visible': True, 'platform_admin_visible': True,
           'permission_gates_unchanged': True}
if apply:
    e.cr.commit()
else:
    e.cr.rollback()
(root / ('applied.json' if apply else 'rehearsal.json')).write_text(json.dumps(receipt, indent=2))
print('SETTINGS_RESTORED', json.dumps(receipt))
