"""Dedicated, removable browser-test fixtures. Never run on customer databases."""
import json, secrets, os
from pathlib import Path
from odoo.addons.pb_lifecycle.models import workflow_definition as D
assert env.cr.dbname in ('workflow_studio_test_20261109', 'p0clone')
path=Path('/tmp/workflow-studio-ui-'+env.cr.dbname+'.json')
assert not path.exists(), 'A browser fixture already exists. Inspect/clean it first.'
company=env.company
login='workflow.ui.'+secrets.token_hex(5)
password=secrets.token_urlsafe(32)
groups=['base.group_system','pb_lifecycle.group_workflow_publisher','hr.group_hr_manager','hr_expense.group_hr_expense_team_approver']
user=env['res.users'].with_context(no_reset_password=True).create({
    'name':'Workflow UI verification', 'login':login, 'password':password,
    'email':'workflow-ui@example.invalid', 'notification_type':'inbox',
    'company_id':company.id, 'company_ids':[(6,0,company.ids)],
    'group_ids':[(6,0,[env.ref(x).id for x in groups if env.ref(x,raise_if_not_found=False)])]})
service=env['pb.workflow.studio'].with_user(user).with_company(company)
employee=env['hr.employee'].create({'name':'Workflow UI verification', 'company_id':company.id,'user_id':user.id})
claim=env['pb.expense.claim'].create({'employee_id':employee.id,'company_id':company.id,'note':'Temporary Workflow Studio browser verification; no receipts or financial effects.'})
row=service.create_workflow('UI verification · expense progress','pb.expense.claim','Expenses')
w=env['pb.workflow'].browse(row['id']); d=D.fresh(w.name)
d['nodes'] += [{'id':'check','type':'task','title':'Check supporting details','stage':0,'owner':{'kind':'initiator'},'due':2},
               {'id':'approve','type':'matrix','title':'Existing expense approval','stage':1}]
d['order'] += ['check','approve']
process=env['biz.approval.process'].search([('model_name','=','pb.expense.claim')],limit=1)
service.save_draft(w.id,w.revision,d,process_id=process.id)
service.publish(w.id,w.revision);service.activate(w.id,True)
result=service.start(w.id,claim.id,str(__import__('uuid').uuid4()))
assert result['run_id'],result
run=env['pb.workflow.run'].browse(result['run_id'])
assert run.state=='waiting',run.step_ids.mapped('error')
fixture={'database':env.cr.dbname,'login':login,'password':password,'user_id':user.id,
         'company_id':company.id,'employee_id':employee.id,'claim_id':claim.id,
         'workflow_id':w.id,'run_id':run.id,'action_id':env.ref('pb_lifecycle.action_pb_workflow_studio').id}
path.write_text(json.dumps(fixture));os.chmod(path,0o600)
env.cr.commit()
print('WORKFLOW_UI_FIXTURE_READY')
