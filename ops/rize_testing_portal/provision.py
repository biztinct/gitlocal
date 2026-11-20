"""Odoo shell: reconcile a supplied testing roster with existing Rize employees.
INPUT_JSON contains the workbook rows and SHA256; no workbook or private rows
are stored in git. Default mode validates a rollback-only rehearsal. APPLY=1
persists only new portal accounts and links. Existing internal users are held.
No invitation/reset messages are sent by this script.
"""
import json
import os
import unicodedata
from pathlib import Path
from odoo import Command

assert env.cr.dbname == 'rize'
source = json.loads(Path(os.environ['INPUT_JSON']).read_text())
rows = source['records']
assert len(rows) == 13
assert len({r['Official email ID'].strip().lower() for r in rows}) == len(rows)
company = env['res.company'].browse(1)
assert company.name == 'Rize Farms'
actor = env['res.users'].search([('login', '=', 'ash@biztinct.com')])
assert len(actor) == 1 and actor.has_group('base.group_system')
Users = env['res.users'].with_user(actor).sudo().with_context(active_test=False, no_reset_password=True,
    mail_create_nosubscribe=True, mail_notrack=True, allowed_company_ids=[company.id])
Employees = env['hr.employee'].with_user(actor).sudo().with_context(active_test=False)
portal = env.ref('base.group_portal')
allowed = portal | portal.all_implied_ids

def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.lower().replace('đ', 'd')) if not unicodedata.combining(c)).strip()

plan = []
for row in rows:
    email = row['Official email ID'].strip().lower()
    emp = Employees.search([('work_email', '=ilike', email), ('company_id', '=', company.id)])
    assert len(emp) == 1 and emp.active, ('Employee missing/ambiguous/inactive', email)
    assert emp.barcode == row['Country-Based Employee ID'], ('Vietnam ID mismatch', email)
    assert norm(emp.name) == norm(row['Employee Name']), ('Name mismatch', email)
    users = Users.search(['|', ('login', '=ilike', email), ('email', '=ilike', email)]) | emp.user_id
    assert len(users) <= 1, ('Ambiguous user', email)
    if users and (not users.share or not users.active):
        plan.append((row, emp, users, 'held_existing_internal_or_inactive'))
        continue
    partner = emp.work_contact_id
    assert partner and partner.active, ('Missing work contact', email)
    assert not partner.user_ids or partner.user_ids == users, ('Contact used by another login', email)
    assert (partner.email or '').lower() == email, ('Contact email mismatch', email)
    if users:
        assert users.login.lower() == email and users.email.lower() == email
        assert emp.user_id == users and users.partner_id == partner
        assert users.company_id == company and users.company_ids == company
        assert users.all_group_ids <= allowed and users._pb_portal_only()
    plan.append((row, emp, users, 'existing_portal' if users else 'create_portal'))

report = []
for row, emp, user, action in plan:
    email = row['Official email ID'].strip().lower()
    if action == 'create_portal':
        user = Users.create({'name': emp.name, 'login': email, 'email': email,
            'partner_id': emp.work_contact_id.id, 'company_id': company.id,
            'company_ids': [Command.set(company.ids)], 'group_ids': [Command.set(portal.ids)],
            'lang': 'en_US', 'tz': 'Asia/Ho_Chi_Minh', 'active': True})
        emp.write({'user_id': user.id})
    if not action.startswith('held_'):
        assert user.share and not user._is_internal() and user._pb_portal_only()
        assert user.all_group_ids <= allowed
        assert not user.has_group('base.group_user') and not user.has_group('base.group_system')
        assert Employees.search([('user_id', '=', user.id)]).ids == emp.ids
        assert not env['pb.role.assignment'].search_count([('user_id', '=', user.id), ('active', '=', True)])
        for model in ('hr.employee', 'hr.payslip', 'res.users', 'ir.mail_server'):
            assert not env['ir.model.access'].with_user(user).check(model, 'write', raise_exception=False), (email, model)
    report.append({'email': email, 'employee_id': emp.id, 'vietnam_id': emp.barcode,
                   'user_id': user.id, 'action': action, 'portal_only': user._pb_portal_only()})
apply = os.environ.get('APPLY') == '1'
if apply:
    env.cr.commit()
else:
    env.cr.rollback()
result = {'applied': apply, 'source_sha256': source['sha256'], 'records': report}
Path(os.environ['REPORT_JSON']).write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False))
