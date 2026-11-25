# NEWHIRE P7 (odoo-bin shell on a REHEARSAL COPY only): two throwaway logins for the walk on the copy -
# a maker and a second person who approves (an approval needs someone other than the maker), with the HR,
# contracts, payroll, Settings, lifecycle and equipment roles, every company; default = the company with
# the most active people. Passwords go to a root-only file in the evidence folder only; nh7_rh_drop.sh drops
# the whole copy (and the file) afterwards. Clone of ../p6/nh6_rh_users.py.
import os, secrets
assert env.cr.dbname.startswith('nh7_rh_'), 'rehearsal copy only'
counts = {}
for e in env['hr.employee'].sudo().search([('active', '=', True)]):
    counts[e.company_id.id] = counts.get(e.company_id.id, 0) + 1
cid = max(counts, key=counts.get)
companies = env['res.company'].sudo().search([]).ids
groups = []
for x in ('base.group_user', 'base.group_system', 'hr.group_hr_manager', 'hr_contract.group_hr_contract_manager',
          'pb_hr_payroll_base.group_payroll_base_manager', 'pb_hr_payroll_base.group_payroll_super_admin',
          'pb_lifecycle.group_lifecycle_manager', 'pb_assets.group_assets_manager'):
    g = env.ref(x, raise_if_not_found=False)
    if g:
        groups.append(g.id)
lines = []
for login, name in (('nh7-rh-maker', 'Rehearsal Maker'), ('nh7-rh-approver', 'Rehearsal Approver')):
    pw = secrets.token_urlsafe(18)
    u = env['res.users'].with_context(no_reset_password=True, mail_create_nosubscribe=True).create({
        'name': name, 'login': login, 'password': pw, 'company_id': cid,
        'company_ids': [(6, 0, companies)], 'group_ids': [(6, 0, groups)], 'lang': 'en_US'})
    lines.append('%s %s %s' % (env.cr.dbname, login, pw))
env.cr.commit()
path = os.environ['RH_LOGIN_FILE']
with open(path, 'w') as f:
    f.write('\n'.join(lines) + '\n')
os.chmod(path, 0o600)
print('PROBE users made, company', cid, 'people per company', counts)
