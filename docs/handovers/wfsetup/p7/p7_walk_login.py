# WFSETUP P7 (odoo-bin shell on a LIVE database; clone of ../p5b/wfs_walk_login.py): switch an existing,
# disabled QA login on with a fresh random password for the look-only walk (MODE=on), giving it the
# groups the studio needs for the walk only (ADD_GROUPS, xmlids; the ones it lacked are written to
# STATE_FILE), and off again (MODE=off): those groups taken away, a new random password nobody keeps,
# login disabled, password file removed. The password goes to a root-only file in the evidence folder.
import os, secrets
mode = os.environ['MODE']
uid = int(os.environ['WALK_UID'])
prefix = os.environ['WALK_PREFIX']
u = env['res.users'].with_context(active_test=False).browse(uid)
assert u.exists() and u.login.startswith(prefix), 'not the QA login'
state = os.environ['STATE_FILE']
pw = secrets.token_urlsafe(18)
if mode == 'on':
    want = [env.ref(x) for x in os.environ.get('ADD_GROUPS', '').split(',') if x]
    missing = [g for g in want if g not in u.group_ids]
    with open(state, 'w') as f:
        f.write(','.join(str(g.id) for g in missing))
    u.write({'active': True, 'password': pw, 'lang': 'en_US', 'group_ids': [(4, g.id) for g in missing]})
    with open(os.environ['LOGIN_FILE'], 'w') as f:
        f.write('%s %s\n' % (u.login, pw))
    os.chmod(os.environ['LOGIN_FILE'], 0o600)
    print('PROBE added groups', [g.id for g in missing])
else:
    added = [int(x) for x in open(state).read().split(',') if x] if os.path.exists(state) else []
    u.write({'group_ids': [(3, g) for g in added], 'password': pw, 'active': False})
    for p in (os.environ['LOGIN_FILE'],):
        if os.path.exists(p):
            os.remove(p)
    print('PROBE removed groups', added)
env.cr.commit()
print('PROBE user', u.id, u.login, 'active', u.active,
      'attendance officer', u.has_group('hr_attendance.group_hr_attendance_officer'),
      'settings', u.has_group('base.group_system'))
