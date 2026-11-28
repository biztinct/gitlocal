# WFSETUP P5b (odoo-bin shell on the REHEARSAL COPY only): a throwaway attendance manager + HR user in
# the company with the most active people. The password goes to a root-only file in the evidence folder
# (never the repo, never the report); wfs_rh_drop.sh drops the whole copy (and the file) afterwards.
import os, secrets
assert env.cr.dbname.startswith('wfs_rh_'), 'rehearsal copy only'
counts = {}
for e in env['hr.employee'].sudo().search([('active', '=', True)]):
    counts[e.company_id.id] = counts.get(e.company_id.id, 0) + 1
cid = max(counts, key=counts.get)
company = env['res.company'].browse(cid)
pw = secrets.token_urlsafe(18)
groups = [env.ref('base.group_user').id, env.ref('hr.group_hr_user').id,
          env.ref('hr_attendance.group_hr_attendance_manager').id]
u = env['res.users'].with_context(no_reset_password=True, mail_create_nosubscribe=True).create({
    'name': 'Rehearsal Manager', 'login': 'wfs-rh-manager', 'password': pw,
    'company_id': cid, 'company_ids': [(6, 0, [cid])], 'group_ids': [(6, 0, groups)], 'lang': 'en_US'})
env.cr.commit()
path = os.environ['RH_LOGIN_FILE']
with open(path, 'w') as f:
    f.write('%s %s %s\n' % (env.cr.dbname, u.login, pw))
os.chmod(path, 0o600)
print('PROBE user', u.id, 'company', cid, company.name, 'people per company', counts)
