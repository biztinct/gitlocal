# WFSETUP P7 (odoo-bin shell, READ-ONLY, rolled back): the Workforce menu tree exactly as the web client
# gets it (load_web_menus) for one user, so the live database and the rehearsal copy can be compared.
import os
uid = int(os.environ.get('MENU_UID', '2'))
u = env['res.users'].with_context(active_test=False).browse(uid)
M = env['ir.ui.menu'].with_user(u).with_context(lang='en_US')
menus = M.load_web_menus(False)
roots = [m for k, m in menus.items() if k != 'root' and m.get('id') in menus['root']['children']]
def walk(mid, depth, out):
    m = menus[mid]; out.append('  ' * depth + (m.get('name') or '?') + ('  [%s]' % m.get('xmlid') if m.get('xmlid') else ''))
    for c in m.get('children', []):
        walk(c, depth + 1, out)
out = []
for r in roots:
    if (r.get('name') or '') in ('Workforce', 'Attendances', 'Time', 'Settings') or 'workforce' in (r.get('xmlid') or ''):
        walk(r['id'], 0, out)
print('PROBE user', u.id, u.login, 'root apps', len(roots))
print('PROBE apps', ' | '.join(sorted((r.get('name') or '?') for r in roots)))
for line in out:
    print('MENU', line)
env.cr.rollback()
