"""Run in the Rize Odoo shell; explicit APPLY_PLATFORM_NAVIGATION=1 writes.
Owner requested native platform menus for ash@biztinct.com. No other user's
permissions change, and this group grants no data access by itself.
"""
import json
import os

assert env.cr.dbname == 'rize'
user = env['res.users'].sudo().search([('login', '=', 'ash@biztinct.com')])
assert len(user) == 1 and user.active and user._is_system()
group = env.ref('pb_dashboard.group_platform_navigation')
assert not group.implied_ids
others = env['res.users'].sudo().with_context(active_test=False).search([('id', '!=', user.id)])
before = {u.id: sorted(u.group_ids.ids) for u in others}
result = {'database': env.cr.dbname, 'login': user.login, 'user_id': user.id,
          'group': group.display_name, 'already_assigned': group in user.group_ids}
if os.environ.get('APPLY_PLATFORM_NAVIGATION') == '1':
    user.write({'group_ids': [(4, group.id)]})
    menus = env['ir.ui.menu'].with_user(user).load_web_menus(True)
    assert env.ref('base.menu_administration').id in menus['root']['children']
    assert env.ref('base.menu_custom').id in menus
    assert env.ref('mail.menu_email_templates').id in menus
    assert before == {u.id: sorted(u.group_ids.ids) for u in others}
    env.cr.commit()
    result.update(applied=True, other_users_unchanged=True)
else:
    env.cr.rollback()
    result['applied'] = False
print('PLATFORM_NAVIGATION_SETUP ' + json.dumps(result))
