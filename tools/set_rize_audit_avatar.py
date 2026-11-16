"""Run in an Odoo shell on rize; set RIZE_AVATAR_APPLY=1 to save.

Replace only the inactive Rize system account's inherited flower avatar with
the existing Rize website logo. Keep a permanent, targeted rollback backup.
No addon upgrade or service restart is needed for this tenant configuration.
"""
import base64
import hashlib
import json
import os
from pathlib import Path


assert env.cr.dbname == 'rize', 'This configuration is Rize-only'
source = Path('/odoo/odoo-server/addons/rize_website/static/src/img/rize_logo.png')
logo = source.read_bytes()
assert hashlib.sha256(logo).hexdigest() == '60b941ae61d53afa369bb946aa8b11cc26e52733f71cdbfd378d29c9567afc2b'
user = env['res.users'].with_context(active_test=False, bin_size=False).browse(1).exists()
assert user and user.name == 'Rize' and not user.active and user.partner_id.id == 2
assert user.partner_id not in env['res.company'].search([]).mapped('partner_id')
assert not env['hr.employee'].with_context(active_test=False).search_count([('user_id', '=', user.id)])
old = user.image_1920 or b''
old_sha = hashlib.sha256(base64.b64decode(old)).hexdigest()
assert old_sha == 'd762441a7291bcf2cf2f03cc239ab042a6de8c5d39a3313a8c1d3c19733fc881', 'Avatar changed since review'


def digest(table):
    # Table names below are fixed application tables, never user input.
    env.cr.execute("SELECT count(*), md5(coalesce(string_agg(md5(row_to_json(t)::text), chr(10) ORDER BY id), '')) FROM " + table + ' t')
    return list(env.cr.fetchone())


protected = ['hr_employee', 'hr_contract', 'hr_payslip', 'hr_payslip_line',
             'vietnam_employee_dependent', 'biz_audit_entry', 'mail_message']
before = {table: digest(table) for table in protected}
identity = user.read(['name', 'active', 'login', 'partner_id', 'company_id', 'group_ids'])[0]
other_users = env['res.users'].with_context(active_test=False).search([('id', '!=', user.id)])
other_images = {u.id: u.image_1920 for u in other_users}
apply = os.environ.get('RIZE_AVATAR_APPLY') == '1'
if not apply:
    print('RIZE_AVATAR_PREVIEW=' + json.dumps({'database': 'rize', 'user_id': 1,
          'partner_id': 2, 'source': str(source), 'old_avatar_sha256': old_sha}))
    env.cr.rollback()
else:
    archive = Path('/odoo/archives/rize-audit-avatar-20261117')
    assert archive.is_dir(), 'Prepare the permanent archive before applying'
    backup = {'database': 'rize', 'user_id': user.id, 'partner_id': user.partner_id.id,
              'field': 'image_1920', 'old_image_base64': old.decode() if isinstance(old, bytes) else old,
              'old_sha256': old_sha, 'source_sha256': hashlib.sha256(logo).hexdigest(),
              'permanent': True, 'never_auto_delete': True}
    with (archive / 'avatar-before.json').open('x') as stream:
        json.dump(backup, stream, indent=2)
    user.with_context(tracking_disable=True, mail_notrack=True).write({'image_1920': base64.b64encode(logo)})
    env.flush_all()
    assert user.read(['name', 'active', 'login', 'partner_id', 'company_id', 'group_ids'])[0] == identity
    assert {u.id: u.image_1920 for u in other_users} == other_images
    assert {table: digest(table) for table in protected} == before, 'Protected records changed'
    new_sha = hashlib.sha256(base64.b64decode(user.image_1920)).hexdigest()
    assert new_sha != old_sha and user.avatar_128
    receipt = {'database': 'rize', 'user_id': user.id, 'partner_id': user.partner_id.id,
               'source_sha256': backup['source_sha256'], 'new_avatar_sha256': new_sha,
               'protected_tables_unchanged': protected, 'other_user_images_unchanged': True,
               'identity_and_access_unchanged': True, 'restart_required': False}
    env.cr.commit()
    (archive / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('RIZE_AVATAR_UPDATED=' + json.dumps(receipt))
