"""WF2 P6a browser fixture — LOCAL DISPOSABLE DATABASES ONLY (am_wf2p6a*).

    odoo-bin shell -d am_wf2p6a_ui --no-http < tools/workflow_studio/ui_fixture_p6a.py

Creates two local logins (a designer/publisher and a checker), a time-off
request of five working days, a time-off workflow that repeats "Check the
day" for each day (running), and two "sent back" emails queued by the areas'
own code: a business trip for a Vietnamese-speaking employee and an
equipment request for an Indonesian-speaking one. Passwords are random and
written only to a 0600 file outside the repo (path printed).
"""
import json
import os
import secrets
import uuid
from datetime import timedelta
from pathlib import Path

from odoo import fields
from odoo.addons.pb_lifecycle.models import workflow_definition as D

assert env.cr.dbname.startswith('am_wf2p6a'), 'Local disposable databases only.'
out = Path(os.environ.get('P6A_FIXTURE_FILE') or '/tmp/wf2p6a-ui-%s.json' % env.cr.dbname)
company = env.company
password = secrets.token_urlsafe(18)
Users = env['res.users'].with_context(no_reset_password=True)


def login(name, key, groups, lang='en_US', notice='inbox'):
    found = Users.search([('login', '=', key)], limit=1)
    vals = {'name': name, 'login': key, 'password': password, 'company_id': company.id, 'lang': lang,
            'company_ids': [(6, 0, company.ids)], 'notification_type': notice,
            'group_ids': [(6, 0, [env.ref(g).id for g in groups if env.ref(g, raise_if_not_found=False)])]}
    if found:
        found.write(vals)
        return found
    return Users.create(vals)


designer = login('P6a Designer', 'p6a.designer', ['base.group_user', 'base.group_system',
                                                  'pb_lifecycle.group_workflow_publisher', 'hr.group_hr_manager',
                                                  'hr_holidays.group_hr_holidays_manager'])
checker = login('P6a Checker', 'p6a.checker', ['base.group_user', 'hr_holidays.group_hr_holidays_user',
                                               'pb_lifecycle.group_workflow_viewer'])
Employee = env['hr.employee']
asker = Employee.search([('name', '=', 'P6a Leave Asker')], limit=1) or Employee.create(
    {'name': 'P6a Leave Asker', 'company_id': company.id})
kind = env['hr.leave.type'].search([('name', '=', 'P6a days')], limit=1) or env['hr.leave.type'].create(
    {'name': 'P6a days', 'requires_allocation': False, 'leave_validation_type': 'no_validation',
     'company_id': company.id})
anchor = fields.Date.today() + timedelta(days=21)
monday = anchor - timedelta(days=anchor.weekday())
leave = env['hr.leave'].sudo().create({'holiday_status_id': kind.id, 'employee_id': asker.id, 'name': 'P6a week off',
                                       'request_date_from': monday, 'request_date_to': monday + timedelta(days=4)})
service = env['pb.workflow.studio'].with_user(designer).with_company(company)
row = service.create_workflow('P6a cover each day', 'hr.leave', 'Time off')
w = env['pb.workflow'].browse(row['id'])
d = D.fresh(w.name)
d['nodes'] += [
    {'id': 'rep', 'type': 'repeat', 'title': 'For each day', 'stage': 0, 'steps': ['check'],
     'source': {'kind': 'area', 'key': 'days', 'fields': ['date', 'hours']},
     'mode': 'together', 'join': 'all', 'max_lines': 50},
    {'id': 'check', 'type': 'task', 'title': 'Find cover for the day', 'stage': 0,
     'owner': {'kind': 'user', 'id': checker.id}, 'due': 2,
     'notes': 'Is someone covering this day?'},
]
d['order'] += ['rep']
service.save_draft(w.id, w.revision, d)
service.publish(w.id, w.revision)
service.activate(w.id, True, acknowledge_existing=True)
started = service.start(w.id, leave.id, str(uuid.uuid4()))
assert started['run_id'], started
run = env['pb.workflow.run'].browse(started['run_id'])
assert run.line_ids, run.step_ids.mapped('error')

# Two "sent back" emails, queued by the areas' own code, with a reason.
reasons = {'pb.business.trip': 'Vui lòng thêm chi phí khách sạn.',
           'pb.asset.request': 'Masih ada laptop cadangan, silakan minta yang itu.'}
for model in reasons:
    type(env[model])._pb_sent_back_note = lambda self, _m=model: reasons[_m]
lan = Employee.create({'name': 'P6a Lan (vi)', 'company_id': company.id, 'work_email': 'p6a.lan@example.invalid',
                       'user_id': login('P6a Lan', 'p6a.lan', ['base.group_user'], lang='vi_VN', notice='email').id})
sari = Employee.create({'name': 'P6a Sari (id)', 'company_id': company.id, 'work_email': 'p6a.sari@example.invalid',
                        'user_id': login('P6a Sari', 'p6a.sari', ['base.group_user'], lang='id_ID', notice='email').id})
trip = env['pb.business.trip'].sudo().create({'employee_id': lan.id, 'purpose': 'Visit the Hanoi office',
                                              'destination_city': 'Hà Nội', 'date_from': monday,
                                              'date_to': monday + timedelta(days=2)})
cat = env['pb.asset.category'].search([], limit=1)
req = env['pb.asset.request'].sudo().create({'employee_id': sari.id, 'category_id': cat.id})
assert trip._pb_tell_sent_back() and req._pb_tell_sent_back()
mails = {m: env['mail.mail'].sudo().search([('model', '=', m), ('res_id', '=', r.id)], limit=1)
         for m, r in (('pb.business.trip', trip), ('pb.asset.request', req))}
env.cr.commit()
out.write_text(json.dumps({
    'database': env.cr.dbname, 'password': password, 'designer': designer.login, 'checker': checker.login,
    'workflow_id': w.id, 'leave_id': leave.id, 'lines': len(run.line_ids),
    'mail': {m: {'subject': x.subject, 'body': x.body_html} for m, x in mails.items()},
}, ensure_ascii=False))
os.chmod(out, 0o600)
print('P6A_FIXTURE', out)
