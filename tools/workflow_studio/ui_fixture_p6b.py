"""WF2 P6b browser fixture — LOCAL DISPOSABLE DATABASES ONLY (wf2p6b_ui*).

    odoo-bin shell -d wf2p6b_ui --no-http < tools/workflow_studio/ui_fixture_p6b.py

For the Studio editor's English golden files and the Vietnamese / Indonesian
screenshots. Creates three logins with the same rights (English, Vietnamese,
Indonesian designers/publishers) and drafts that between them use every step
type and every way to start: a repeat over the days of a time-off request
(running, so the progress page shows its lines), a repeat over a list
question's lines, a weekly and a monthly schedule, "at a record date",
"when a field changes", plus one waiting task for each designer so
"My tasks" and the task page have something to show. Passwords are random
and written only to a 0600 file outside the repo (path printed).
"""
import json
import os
import secrets
import uuid
from datetime import timedelta
from pathlib import Path

from odoo import fields
from odoo.addons.pb_lifecycle.models import workflow_definition as D

assert env.cr.dbname.startswith('wf2p6b_ui'), 'Local disposable databases only.'
out = Path(os.environ.get('P6B_FIXTURE_FILE') or '/tmp/wf2p6b-ui-%s.json' % env.cr.dbname)
company = env.company
password = secrets.token_urlsafe(18)
Users = env['res.users'].with_context(no_reset_password=True)
GROUPS = ['base.group_user', 'base.group_system', 'pb_lifecycle.group_workflow_publisher', 'hr.group_hr_manager',
          'hr_holidays.group_hr_holidays_manager']


def login(name, key, lang):
    found = Users.search([('login', '=', key)], limit=1)
    vals = {'name': name, 'login': key, 'password': password, 'company_id': company.id, 'lang': lang,
            'company_ids': [(6, 0, company.ids)], 'notification_type': 'inbox', 'tz': 'Asia/Ho_Chi_Minh',
            'group_ids': [(6, 0, [env.ref(g).id for g in GROUPS if env.ref(g, raise_if_not_found=False)])]}
    if found:
        found.write(vals)
        return found
    return Users.create(vals)


people = {lang: login('P6b Designer %s' % lang[:2].upper(), 'p6b.%s' % lang[:2], lang)
          for lang in ('en_US', 'vi_VN', 'id_ID')}
designer = people['en_US']
service = env['pb.workflow.studio'].with_user(designer).with_company(company)
made = {}


def draft(name, model, area, nodes, order, trigger=None, stages=None):
    row = service.create_workflow(name, model, area)
    w = env['pb.workflow'].browse(row['id'])
    d = D.fresh(w.name)
    d['nodes'] += nodes
    d['order'] += order
    if trigger:
        d['trigger'].update(trigger)
    if stages:
        d['stages'] = stages
    service.save_draft(w.id, w.revision, d)
    made[name] = w.id
    return w


# 1. A repeat over the days of a time-off request, published and running.
Employee = env['hr.employee']
asker = Employee.search([('name', '=', 'P6b Leave Asker')], limit=1) or Employee.create(
    {'name': 'P6b Leave Asker', 'company_id': company.id})
kind = env['hr.leave.type'].search([('name', '=', 'P6b days')], limit=1) or env['hr.leave.type'].create(
    {'name': 'P6b days', 'requires_allocation': False, 'leave_validation_type': 'no_validation',
     'company_id': company.id})
anchor = fields.Date.today() + timedelta(days=21)
monday = anchor - timedelta(days=anchor.weekday())
leave = env['hr.leave'].sudo().create({'holiday_status_id': kind.id, 'employee_id': asker.id, 'name': 'P6b week off',
                                       'request_date_from': monday, 'request_date_to': monday + timedelta(days=4)})
w = draft('P6b cover each day', 'hr.leave', 'Time off', [
    {'id': 'rep', 'type': 'repeat', 'title': 'For each day', 'stage': 0, 'steps': ['check'],
     'source': {'kind': 'area', 'key': 'days', 'fields': ['date', 'hours']},
     'mode': 'one_by_one', 'join': 'any', 'max_lines': 20},
    {'id': 'check', 'type': 'task', 'title': 'Find cover for the day', 'stage': 0,
     'owner': {'kind': 'user', 'id': designer.id}, 'due': 2, 'notes': 'Is someone covering this day?',
     'buttons': [{'key': 'done', 'label': 'Done'}, {'key': 'cannot', 'label': 'Cannot do'}]},
], ['rep'])
w = env['pb.workflow'].browse(w.id)
service.publish(w.id, w.revision)
service.activate(w.id, True, acknowledge_existing=True)
started = service.start(w.id, leave.id, str(uuid.uuid4()))
assert started['run_id'], started
run_id = started['run_id']

# 2. A process with a list question and a repeat over its lines, every helper step.
draft('P6b receipts by line', False, 'Finance', [
    {'id': 'ask', 'type': 'input', 'title': 'List the receipts', 'stage': 0, 'owner': {'kind': 'initiator'},
     'due': 2, 'due_kind': 'working',
     'form': {'fields': [{'id': 'lines', 'type': 'rows', 'label': 'Receipts', 'required': True},
                         {'id': 'kind', 'type': 'select', 'label': 'Kind', 'options': ['Taxi', 'Hotel'],
                          'required': False}]}},
    {'id': 'rep2', 'type': 'repeat', 'title': 'For each line of “Receipts”', 'stage': 1, 'steps': ['tick'],
     'source': {'kind': 'answers', 'step': 'ask', 'field': 'lines'}, 'mode': 'together', 'join': 'all',
     'max_lines': 50},
    {'id': 'tick', 'type': 'task', 'title': 'Check the receipt', 'stage': 1, 'owner': {'kind': 'initiator'},
     'due': 1},
    {'id': 'pause', 'type': 'wait', 'title': 'Wait a day', 'stage': 2, 'wait_for': 1, 'unit': 'day'},
    {'id': 'tell', 'type': 'notify', 'title': 'Tell the requester', 'stage': 2, 'owner': {'kind': 'initiator'},
     'message': 'All receipts are checked.'},
], ['ask', 'rep2', 'pause', 'tell'], stages=[{'name': 'Collect'}, {'name': 'Check'}, {'name': 'Finish'}])

# 3. Schedules: weekly for a new process, monthly for each matching record.
draft('P6b weekly check', False, 'Finance', [
    {'id': 'look', 'type': 'task', 'title': 'Look at the week', 'stage': 0, 'owner': {'kind': 'user', 'id': designer.id},
     'due': 1},
], ['look'], trigger={'kind': 'schedule', 'schedule': {'every': 'week', 'at': '09:00', 'weekdays': [0, 2],
                                                        'day': 1, 'month': 1, 'date': '', 'working_days': True,
                                                        'starts': 'process'}})
draft('P6b monthly claims', 'pb.expense.claim', 'Expenses', [
    {'id': 'chase', 'type': 'task', 'title': 'Chase the claim', 'stage': 0, 'owner': {'kind': 'initiator'}, 'due': 2},
], ['chase'], trigger={'kind': 'schedule', 'schedule': {'every': 'month', 'at': '17:30', 'weekdays': [0], 'day': 31,
                                                         'month': 1, 'date': '', 'working_days': False,
                                                         'starts': 'each_record'}})
# 4. At a record date, and when a field changes.
draft('P6b before the leave', 'hr.leave', 'Time off', [
    {'id': 'remind', 'type': 'notify', 'title': 'Remind the manager', 'stage': 0, 'owner': {'kind': 'manager'},
     'message': 'Time off starts soon.'},
], ['remind'], trigger={'kind': 'date', 'date_field': 'request_date_from', 'delay': 3, 'mode': 'before',
                        'unit': 'day'})
draft('P6b claim changed', 'pb.expense.claim', 'Expenses', [
    {'id': 'look2', 'type': 'task', 'title': 'Look at the change', 'stage': 0, 'owner': {'kind': 'initiator'},
     'due': 1},
], ['look2'], trigger={'kind': 'changed', 'fields': ['name']})

# One waiting task for each designer ("My tasks", the task page).
tasks = {}
for lang, person in people.items():
    step = env['pb.workflow.step'].sudo().search([('state', '=', 'waiting'), ('run_id', '=', run_id)], limit=1)
    other = env['pb.workflow.step'].sudo().search([('state', '=', 'waiting'), ('assignee_id', '!=', False)],
                                                  order='id desc', limit=1)
    pick = step if lang == 'en_US' and step else other
    if pick:
        tasks[lang] = pick.id
env.cr.commit()
out.write_text(json.dumps({
    'database': env.cr.dbname, 'password': password, 'company_id': company.id,
    'logins': {lang: p.login for lang, p in people.items()}, 'workflows': made, 'run_id': run_id,
    'tasks': tasks,
}, ensure_ascii=False))
os.chmod(out, 0o600)
print('P6B_FIXTURE', out)
