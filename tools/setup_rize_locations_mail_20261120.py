"""Rize-only configuration. Private SMTP input; rollback unless APPLY_RIZE_SETUP=1."""
import json, os
from pathlib import Path
assert env.cr.dbname in ('rize', 'codex_rize_ui_20261120')
apply = os.getenv('APPLY_RIZE_SETUP') == '1'
secret_path = Path(os.environ['RIZE_SMTP_SECRET'])
assert secret_path.stat().st_mode & 0o077 == 0
secret = json.loads(secret_path.read_text())
e = env(user=2, context=dict(env.context, allowed_company_ids=[1], mail_notrack=True, tracking_disable=True))
company = e['res.company'].browse(1)
assert company.name == 'Rize Farms'

def digest(table):
    e.cr.execute('SELECT count(*),md5(coalesce(string_agg(row_to_json(t)::text,chr(10) ORDER BY id),\'\')) FROM '+table+' t')
    return list(e.cr.fetchone())
protected = ['hr_contract','hr_contract_advantage','hr_payslip','hr_payslip_line','res_partner_bank','mail_mail','res_users']
before = {t:digest(t) for t in protected}
employees = e['hr.employee'].search([('company_id','=',1)])
weekdays = tuple(day+'_location_id' for day in ('monday','tuesday','wednesday','thursday','friday'))
weekends = ['saturday_location_id','sunday_location_id']
old_weekends = employees.read(weekends)
office = e['hr.work.location'].browse(2)
assert office.name == 'Office' and office.company_id == company
company.write({'pb_weekday_location_defaults':True, 'pb_weekday_fallback_location_id':office.id})
changed = []
for emp in employees:
    defaults = emp._pb_weekday_defaults()
    if defaults:
        emp.write(defaults)
        changed.append({'employee_id':emp.id,'locations':defaults})
assert employees.read(weekends) == old_weekends
assert all(all(emp[day] for day in weekdays) for emp in employees)
M = e['ir.mail_server'].with_context(active_test=False)
servers = M.search([('smtp_user','=',secret['username'])])
assert len(servers) <= 1
vals = {'name':'Rize — support@payobook.com (Zoho)', 'smtp_host':'smtppro.zoho.com',
        'smtp_port':465, 'smtp_encryption':'ssl', 'smtp_authentication':'login',
        'smtp_user':secret['username'], 'smtp_pass':secret['password'],
        'from_filter':secret['username'], 'active':False}
if servers:
    servers.write(vals)
else:
    servers=M.create(vals)
assert not servers.active
assert servers not in e['ir.mail_server'].search([])
assert {t:digest(t) for t in protected} == before, 'Protected data changed'
result={'applied':apply,'company_id':company.id,'employees':len(employees),'weekday_records_updated':len(changed),
        'weekends_unchanged':True,'mail_server_id':servers.id,'mail_server_active':servers.active,
        'protected_data_unchanged':True,'changes':changed}
if apply:
    assert env.cr.dbname == 'rize'
    env.cr.commit()
else:
    env.cr.rollback()
Path(os.environ['RIZE_SETUP_RESULT']).write_text(json.dumps(result,indent=2))
print('RIZE_SETUP',json.dumps({k:v for k,v in result.items() if k != 'changes'}))
