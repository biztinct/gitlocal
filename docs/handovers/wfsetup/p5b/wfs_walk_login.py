# WFSETUP P5b (odoo-bin shell on LIVE sudima): switch the earlier, disabled QA login 2501
# (workspace-live-qa-…@example.invalid, attendance manager) on with a fresh random password for the
# read-only walk (MODE=on), and off again with another random password nobody keeps (MODE=off).
# The password goes to a root-only file in the evidence folder only.
import os, secrets
mode = os.environ['MODE']
u = env['res.users'].with_context(active_test=False).browse(2501)
assert u.exists() and u.login.startswith('workspace-live-qa-'), 'not the QA login'
pw = secrets.token_urlsafe(18)
if mode == 'on':
    u.write({'active': True, 'password': pw, 'lang': 'en_US'})
    with open(os.environ['LOGIN_FILE'], 'w') as f:
        f.write('%s %s\n' % (u.login, pw))
    os.chmod(os.environ['LOGIN_FILE'], 0o600)
else:
    u.write({'password': pw, 'active': False})
    if os.path.exists(os.environ['LOGIN_FILE']):
        os.remove(os.environ['LOGIN_FILE'])
env.cr.commit()
print('PROBE user', u.id, 'active', u.active, 'lang', u.lang)
