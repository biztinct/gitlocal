"""Remove only records owned by our dedicated nonproduction browser fixture."""
import json
from pathlib import Path
assert env.cr.dbname in ('workflow_studio_test_20261109', 'p0clone')
path=Path('/tmp/workflow-studio-ui-'+env.cr.dbname+'.json')
f=json.loads(path.read_text());assert f['database']==env.cr.dbname
user=env['res.users'].browse(f['user_id']).exists()
assert user.login==f['login'] and user.email=='workflow-ui@example.invalid'
flows=env['pb.workflow'].with_context(active_test=False).search([('create_uid','=',user.id)])
# Configuration writes use narrow sudo, but preserve the actual acting uid.
assert f['workflow_id'] in flows.ids and all(w.name.startswith(('UI test ·','UI verification ·')) for w in flows)
runs=env['pb.workflow.run'].search([('workflow_id','in',flows.ids)])
assert not runs.mapped('step_ids.approval_id') and not runs.mapped('source_approval_id')
assert not runs.mapped('step_ids.mail_id')
assert not flows.mapped('automation_id'), 'Browser fixtures use manual starts only'
assert not flows.filtered(lambda w:not w.source_model).mapped('process_id')
activities=runs.mapped('step_ids.activity_id');activities.unlink()
env['ir.attachment'].search([('res_model','=','pb.workflow.step'),('res_id','in',runs.mapped('step_ids').ids)]).unlink()
events=env['pb.workflow.event'].search([('workflow_id','in',flows.ids)])
counts={'workflows':len(flows),'runs':len(runs),'events':len(events),'activities':len(activities)}
events.unlink();runs.unlink()
versions=flows.mapped('version_ids');flows.write({'published_id':False,'enabled':False})
versions.with_context(module_uninstall=True).unlink();flows.unlink()
claim=env['pb.expense.claim'].browse(f['claim_id']).exists()
assert claim.employee_id.id==f['employee_id'] and claim.state=='draft'
claim.unlink()
employee=env['hr.employee'].browse(f['employee_id']).exists()
assert employee.user_id==user
employee.unlink()
partner=user.partner_id
user.unlink()
if not env['res.users'].with_context(active_test=False).search_count([('partner_id','=',partner.id)]):partner.unlink()
assert not env['pb.workflow'].with_context(active_test=False).search_count([('create_uid','=',f['user_id'])])
env.cr.commit()
path.unlink()
print('WORKFLOW_UI_CLEANUP='+json.dumps(counts))
