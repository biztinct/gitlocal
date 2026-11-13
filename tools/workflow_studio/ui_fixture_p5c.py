"""WF2 P5c browser fixture — LOCAL DISPOSABLE DATABASES ONLY (am_wf2p5c*).

    odoo-bin shell -d am_wf2p5c_ui --no-http < tools/workflow_studio/ui_fixture_p5c.py

Creates two local logins (a designer/publisher and a checker), an employee-home
login, a claim workflow that repeats "Check receipt" for each receipt, and a
claim with three receipts running through it; a second workflow whose second
line needs attention (for Retry). Passwords are random and written only to a
0600 file outside the repo (path printed); nothing is committed.
"""
import json
import os
import secrets
import uuid
from datetime import timedelta
from pathlib import Path

from odoo import fields
from odoo.addons.pb_lifecycle.models import workflow_definition as D

assert env.cr.dbname.startswith('am_wf2p5c'), 'Local disposable databases only.'
out = Path(os.environ.get('P5C_FIXTURE_FILE') or '/tmp/wf2p5c-ui-%s.json' % env.cr.dbname)
company = env.company
password = secrets.token_urlsafe(18)
Users = env['res.users'].with_context(no_reset_password=True)


def login(name, key, groups, share=False):
    found = Users.search([('login', '=', key)], limit=1)
    vals = {'name': name, 'login': key, 'password': password, 'company_id': company.id,
            'company_ids': [(6, 0, company.ids)],
            'group_ids': [(6, 0, [env.ref(g).id for g in groups if env.ref(g, raise_if_not_found=False)])]}
    # An employee-home login keeps email notices (ledger G37).
    vals['notification_type'] = 'email' if share else 'inbox'
    if found:
        found.write(vals)
        return found
    return Users.create(vals)


designer = login('P5c Designer', 'p5c.designer', ['base.group_user', 'base.group_system', 'pb_lifecycle.group_workflow_publisher',
                                                  'hr.group_hr_manager', 'hr_expense.group_hr_expense_manager'])
checker = login('P5c Checker', 'p5c.checker', ['base.group_user', 'hr_expense.group_hr_expense_user',
                                               'pb_lifecycle.group_workflow_viewer'])
home = login('P5c Home', 'p5c.home', ['base.group_portal'], share=True)
Employee = env['hr.employee']
emp = Employee.search([('user_id', '=', home.id)], limit=1) or Employee.create(
    {'name': 'P5c Home', 'company_id': company.id, 'user_id': home.id, 'work_email': 'p5c.home@example.invalid'})
claimant = Employee.search([('name', '=', 'P5c Claimant')], limit=1) or Employee.create(
    {'name': 'P5c Claimant', 'company_id': company.id})
service = env['pb.workflow.studio'].with_user(designer).with_company(company)
product = env['product.product'].search([('name', '=', 'P5c Taxi')], limit=1) or env['product.product'].create(
    {'name': 'P5c Taxi', 'can_be_expensed': True, 'standard_price': 0.0})


def claim_with(employee, names):
    claim = env['pb.expense.claim'].create({'employee_id': employee.id, 'company_id': company.id})
    for i, name in enumerate(names):
        env['hr.expense'].create({'name': name, 'employee_id': employee.id, 'product_id': product.id,
                                  'total_amount_currency': 25.0 * (i + 1), 'company_id': company.id,
                                  'pb_claim_id': claim.id, 'date': fields.Date.today() - timedelta(days=len(names) - i)})
    return claim


BUTTONS = [{'key': 'fine', 'label': 'Looks fine'}, {'key': 'missing', 'label': 'Paper receipt missing'}]
row = service.create_workflow('P5c receipts check', 'pb.expense.claim', 'Expenses')
w = env['pb.workflow'].browse(row['id'])
d = D.fresh(w.name)
d['nodes'] += [
    {'id': 'rep', 'type': 'repeat', 'title': 'For each receipt', 'stage': 1, 'steps': ['check'],
     'source': {'kind': 'area', 'key': 'receipts', 'fields': ['description', 'date', 'category', 'amount']},
     'mode': 'together', 'join': 'all', 'max_lines': 50},
    {'id': 'check', 'type': 'task', 'title': 'Check receipt', 'stage': 1, 'owner': {'kind': 'user', 'id': checker.id},
     'due': 2, 'buttons': BUTTONS, 'notes': 'Is the receipt readable and does it match the amount?'},
    {'id': 'wrap', 'type': 'task', 'title': 'Book the claim', 'stage': 2, 'owner': {'kind': 'user', 'id': designer.id}, 'due': 2},
]
d['order'] += ['rep', 'wrap']
service.save_draft(w.id, w.revision, d)
service.publish(w.id, w.revision)
service.activate(w.id, True, acknowledge_existing=True)
claim = claim_with(claimant, ['Taxi to airport', 'Hotel Hanoi', 'Team dinner'])
started = service.start(w.id, claim.id, str(uuid.uuid4()))
assert started['run_id'], started
run = env['pb.workflow.run'].browse(started['run_id'])
assert len(run.line_ids) == 3, run.step_ids.mapped('error')

# Six lines for the checker (grouped inbox card) on a second claim.
claim6 = claim_with(claimant, ['Lunch %s' % i for i in range(1, 7)])
run6 = env['pb.workflow.run'].browse(service.start(w.id, claim6.id, str(uuid.uuid4()))['run_id'])

# Employee-home: a claim of the home login's employee with the repeat running.
claim_home = claim_with(emp, ['Parking', 'Train'])
w_home = service.create_workflow('P5c home check', 'pb.expense.claim', 'Expenses')
wh = env['pb.workflow'].browse(w_home['id'])
dh = D.fresh(wh.name)
dh['nodes'] += [{'id': 'rep', 'type': 'repeat', 'title': 'For each receipt', 'stage': 0, 'steps': ['own'],
                 'source': {'kind': 'area', 'key': 'receipts', 'fields': ['amount']}, 'mode': 'one_by_one',
                 'join': 'all', 'max_lines': 50},
                {'id': 'own', 'type': 'confirm', 'title': 'Confirm this receipt is yours', 'stage': 0,
                 'owner': {'kind': 'subject'}, 'due': 2, 'text': 'I paid this myself.'}]
dh['order'] += ['rep']
service.save_draft(wh.id, wh.revision, dh)
service.publish(wh.id, wh.revision)
service.activate(wh.id, True, acknowledge_existing=True)
run_home = env['pb.workflow.run'].browse(service.start(wh.id, claim_home.id, str(uuid.uuid4()))['run_id'])

# A line that needs attention (owner switched off), for Retry.
away = login('P5c Away', 'p5c.away', ['base.group_user', 'hr_expense.group_hr_expense_user'], share=True)
w_fail = service.create_workflow('P5c retry a line', 'pb.expense.claim', 'Expenses')
wf = env['pb.workflow'].browse(w_fail['id'])
df = D.fresh(wf.name)
df['nodes'] += [{'id': 'rep', 'type': 'repeat', 'title': 'For each receipt', 'stage': 0, 'steps': ['look'],
                 'source': {'kind': 'area', 'key': 'receipts', 'fields': ['amount']}, 'mode': 'together',
                 'join': 'all', 'max_lines': 50},
                {'id': 'look', 'type': 'task', 'title': 'Look at the big one', 'stage': 0,
                 'owner': {'kind': 'user', 'id': away.id}, 'due': 2,
                 'when': {'match': 'all', 'rules': [{'field': 'line.amount', 'op': 'gt', 'value': 40}]}}]
df['order'] += ['rep']
service.save_draft(wf.id, wf.revision, df)
service.publish(wf.id, wf.revision)
service.activate(wf.id, True, acknowledge_existing=True)
away.active = False
claim_fail = claim_with(claimant, ['Small', 'Big'])
run_fail = env['pb.workflow.run'].browse(service.start(wf.id, claim_fail.id, str(uuid.uuid4()))['run_id'])
assert run_fail.state == 'failed', run_fail.state
away.active = True

out.write_text(json.dumps({
    'database': env.cr.dbname, 'password': password,
    'designer': designer.login, 'checker': checker.login, 'home': home.login,
    'workflow_id': w.id, 'claim_id': claim.id, 'run_id': run.id, 'run6_id': run6.id,
    'home_claim_id': claim_home.id, 'home_run_id': run_home.id,
    'fail_run_id': run_fail.id, 'fail_workflow_id': wf.id}))
os.chmod(out, 0o600)
env.cr.commit()
print('P5C_UI_FIXTURE=' + str(out))
