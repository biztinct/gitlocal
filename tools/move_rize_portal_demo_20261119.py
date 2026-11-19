"""Move the existing portal demo to Rize Farms, per the owner's correction.

Run in rize Odoo shell. Default is a rollback rehearsal; set RIZE_DEMO_APPLY=1
to save. No emails, passwords, payroll inputs or real employee records change.
"""
import fcntl
import json
import os
from pathlib import Path
from odoo import Command
from odoo.exceptions import AccessError

assert env.cr.dbname == 'rize'
lock = open('/tmp/payobook-studio-deploy.lock', 'r')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
root = Path('/odoo/archives/rize-demo-production-20261119')
apply = os.getenv('RIZE_DEMO_APPLY') == '1'
assert (root / 'before.dump').stat().st_size > 1000000
e = env(user=2, context=dict(env.context, allowed_company_ids=[1],
    no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))
assert e.user.login == 'ash@biztinct.com'
u = e['res.users'].sudo().browse(2558)
employee = e['hr.employee'].sudo().browse(5909)
preview = e['res.company'].sudo().browse(377)
company = e['res.company'].browse(1)
assert company.name == 'Rize Farms' and preview.name == 'Rize — Employee preview'
assert u.login == 'employee.preview@rize.farm' and u.active and u.share
assert employee.name == 'Demo Employee' and employee.user_id == u and employee.active
assert employee.company_id == preview and u.company_id == preview
assert not employee.contract_id and not employee.pb_paid_by_id

def digest(table, condition='TRUE'):
    e.cr.execute('SELECT count(*),md5(coalesce(string_agg(row_to_json(t)::text,chr(10) ORDER BY id),\'\')) FROM '+table+' t WHERE '+condition)
    return list(e.cr.fetchone())

protected = ['hr_contract', 'hr_payslip', 'hr_payslip_line', 'hr_payslip_run',
    'hr_contract_advantage', 'hr_formula_config', 'hr_formula_rule',
    'res_partner_bank', 'pb_payroll_month_inputs']
before = {t: digest(t) for t in protected}
others = digest('hr_employee', 'id <> 5909')
users = digest('res_users', 'id <> 2558')
original_roster = e['hr.employee'].search([('company_id', '=', 1)]).ids
old = {'employee_company': employee.company_id.id, 'user_company': u.company_id.id,
    'allowed_companies': u.company_ids.ids, 'groups': u.group_ids.ids}

# Clear company-specific defaults from the disposable sample before moving it.
employee.with_context(allowed_company_ids=[1, 377]).write({
    'company_id': 1, 'address_id': company.partner_id.id,
    'resource_calendar_id': company.resource_calendar_id.id})
u.with_context(allowed_company_ids=[1, 377]).write({
    'company_id': 1, 'company_ids': [Command.set([1])]})
assert not e['hr.employee'].sudo().search_count([('company_id', '=', 377)])
assert not e['res.users'].sudo().search_count([('company_ids', 'in', [377])])
preview.write({'active': False})
portal = e(user=u.id, context=dict(e.context, allowed_company_ids=[1]))
assert u.share and not u.has_group('base.group_user') and u._pb_employee_only()
assert u.group_ids.ids == old['groups'] and u.company_ids == company
assert portal['pb.me.home'].get_home_data(employee)['person']['name'] == 'Demo Employee'
assert portal['pb.me.home'].get_home_data(e['hr.employee'].browse(3390)) is None
for model, record_id in [('hr.employee', 3390), ('hr.contract', 1839), ('res.partner.bank', 954)]:
    try:
        portal[model].browse(record_id).read(['display_name'])
    except AccessError:
        pass
    else:
        raise AssertionError('Demo can read another employee private record: ' + model)
assert not employee.contract_id and not employee.pb_paid_by_id
assert not e['hr.payslip'].sudo().search_count([('employee_id', '=', employee.id)])
e.flush_all()
assert {t: digest(t) for t in protected} == before
assert digest('hr_employee', 'id <> 5909') == others
assert digest('res_users', 'id <> 2558') == users
assert set(e['hr.employee'].search([('company_id', '=', 1)]).ids) == set(original_roster + [5909])
receipt = {'applied': apply, 'employee': employee.id, 'user': u.id,
    'company': company.name, 'company_id': company.id, 'previous': old,
    'unused_preview_company_archived': True, 'portal_private_data_isolation': True,
    'payroll_unchanged': True, 'other_employees_and_users_unchanged': True,
    'headcount_before': len(original_roster), 'headcount_after': len(original_roster)+1}
(root / ('applied.json' if apply else 'rehearsal.json')).write_text(json.dumps(receipt, indent=2))
if apply:
    e.cr.commit()
else:
    e.cr.rollback()
print('DEMO_MOVE', json.dumps(receipt))
