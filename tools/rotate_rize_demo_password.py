"""Set the owner-supplied demo password from a private JSON file.

Run in Rize Odoo shell with RIZE_DEMO_CREDENTIALS pointing to a mode-600 JSON
file containing login/password. Never store credentials in this repository.
"""
import fcntl
import json
import os
from pathlib import Path

assert env.cr.dbname == 'rize'
lock = open('/tmp/payobook-studio-deploy.lock', 'r')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
path = Path(os.environ['RIZE_DEMO_CREDENTIALS'])
assert path.stat().st_mode & 0o077 == 0
secret = json.loads(path.read_text())
assert secret['login'] == 'employee.preview@rize.farm'
user = env['res.users'].sudo().search([('login', '=', secret['login'])])
assert len(user) == 1 and user.id == 2558 and user.active
assert user.share and user.company_id.id == 1
assert not user.has_group('base.group_user')
scope = user.read(['group_ids', 'company_id', 'company_ids', 'active'])
user.with_context(no_reset_password=True).write({'password': secret['password']})
assert user.read(['group_ids', 'company_id', 'company_ids', 'active']) == scope
env.cr.commit()
print('Demo password updated; account access unchanged.')
