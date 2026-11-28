#!/usr/bin/env python3
"""Assign security groups to demo users via XML-RPC on running server."""
import xmlrpc.client
import ssl

URL = 'http://localhost:8069'
DB = 'vietuat'
ADMIN_USER = 'admin'
ADMIN_PASS = 'Plone@123'

# Connect
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common', context=ctx)
uid = common.authenticate(DB, ADMIN_USER, ADMIN_PASS, {})
print(f"Authenticated as uid={uid}")
models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object', context=ctx)

def call(model, method, *args, **kw):
    return models.execute_kw(DB, uid, ADMIN_PASS, model, method, *args, **kw)

# Get group IDs
def get_group_id(xmlid):
    module, name = xmlid.split('.')
    res = call('ir.model.data', 'search_read',
        [[('module','=',module),('name','=',name),('model','=','res.groups')]],
        {'fields': ['res_id'], 'limit': 1})
    return res[0]['res_id'] if res else None

groups = {}
for xmlid in [
    'base.group_user',
    'hr_development_ai.group_bfsi_banker',
    'hr_development_ai.group_bfsi_branch_manager',
    'hr_development_ai.group_bfsi_regional_manager',
    'hr_development_ai.group_hr_development_user',
    'hr_development_ai.group_hr_development_manager',
    'hr_development_ai.group_hr_development_admin',
]:
    gid = get_group_id(xmlid)
    groups[xmlid] = gid
    print(f"  Group {xmlid} = {gid}")

# User -> group mapping
USER_GROUPS = {
    'minh.nv': ['base.group_user', 'hr_development_ai.group_bfsi_branch_manager', 'hr_development_ai.group_hr_development_manager'],
    'lan.tt': ['base.group_user', 'hr_development_ai.group_bfsi_banker', 'hr_development_ai.group_hr_development_user'],
    'nam.lh': ['base.group_user', 'hr_development_ai.group_bfsi_banker', 'hr_development_ai.group_hr_development_user'],
    'anh.pd': ['base.group_user', 'hr_development_ai.group_bfsi_banker', 'hr_development_ai.group_hr_development_user'],
    'mai.vt': ['base.group_user', 'hr_development_ai.group_bfsi_banker', 'hr_development_ai.group_hr_development_user'],
    'tuan.hm': ['base.group_user', 'hr_development_ai.group_bfsi_banker', 'hr_development_ai.group_hr_development_user'],
    'ha.dt': ['base.group_user', 'hr_development_ai.group_bfsi_branch_manager', 'hr_development_ai.group_hr_development_manager'],
    'khoa.bv': ['base.group_user', 'hr_development_ai.group_bfsi_banker', 'hr_development_ai.group_hr_development_user'],
    'huong.nt': ['base.group_user', 'hr_development_ai.group_bfsi_banker', 'hr_development_ai.group_hr_development_user'],
    'bao.tq': ['base.group_user', 'hr_development_ai.group_bfsi_regional_manager', 'hr_development_ai.group_hr_development_admin'],
}

for login, group_xmlids in USER_GROUPS.items():
    users = call('res.users', 'search_read', [[('login','=',login)]], {'fields':['id','name'], 'limit':1})
    if not users:
        print(f"  WARNING: User {login} not found!")
        continue
    user_id = users[0]['id']
    group_ids = [groups[g] for g in group_xmlids if groups.get(g)]
    # Add groups using (4, id) commands
    group_cmds = [(4, gid) for gid in group_ids]
    try:
        call('res.users', 'write', [[user_id], {'groups_id': group_cmds}])
        print(f"  ✓ {login} ({users[0]['name']}): assigned {len(group_ids)} groups")
    except Exception as e:
        print(f"  ✗ {login}: {e}")

print("\nDone!")
