"""Recover only explicit imported zero dependent counts; never infer a count."""
import hashlib,json,os
from pathlib import Path
assert env.cr.dbname=='rize'
source=Path('/tmp/rize-eight-scenarios-20261022/controls.json')
assert hashlib.sha256(source.read_bytes()).hexdigest() == '9fb83f02d77922783142cb7140fae6f3776d9a04956cea83eeb2ac7c85e30f4e', 'Archived controls changed'
data=json.loads(source.read_text())
config=env['hr.formula.config'].browse(7118).exists()
assert config and config.country_code=='VN' and config.company_id.name=='Rize Farms'
desk=env['pb.records.desk'].with_company(config.company_id)
probe=desk._probe(config.id)
card=desk._cards(config.id)['c:VNREGISTER']
assert card['component']['code']=='VNREGISTER'
changes=[];skipped={};eligible=0
for row in data['vn']:
    if type(row['values'].get('VNREGISTER')) not in (int,float) or row['values']['VNREGISTER']!=0:continue
    eligible+=1
    people=env['hr.employee'].with_context(active_test=False).search([('company_id','=',config.company_id.id),'|',('barcode','=',row['code']),('employee_id','=',row['code'])])
    assert len(people)<=1,'Ambiguous source employee'
    if not people:
        skipped['outside_current_roster']=skipped.get('outside_current_roster',0)+1;continue
    contract=probe._get_latest_contract(people)
    assert contract
    if desk._advantage_line(probe,contract,'VNREGISTER'):
        skipped['already_saved']=skipped.get('already_saved',0)+1;continue
    history=env['hr.contract.advantage.change'].search([('contract_id','=',contract.id),('advantage_template_id.code','=','VNREGISTER')])
    if history:
        skipped['later_history']=skipped.get('later_history',0)+1;continue
    # A correction must apply to a previously imported contract, not a new one.
    imported=env['pb.records.change'].search([('employee_id','=',people.id),('model','=','hr.contract'),('res_id','=',contract.id),('apply_id.applied','=',True),('apply_id.source','=','import')],limit=1)
    if not imported:
        skipped['no_import_evidence']=skipped.get('no_import_evidence',0)+1;continue
    changes.append({'emp_id':people.id,'field_id':'c:VNREGISTER','value':0})
assert eligible==48,eligible
preview=desk.preview_changes(config.id,changes)
assert not any(i['status']!='ok' for i in preview['items']),preview['counts']
print('ZERO_REPAIR_PREVIEW',json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'eligible':eligible,'recoverable':len(changes),'skipped':skipped}))
if os.getenv('APPLY_ZERO_REPAIR') in ('1', 'rehearse'):
    result=desk.apply_changes(config.id,changes,note='Recover explicit zero registered-dependent counts omitted by the original Vietnam master import because absent contract components compared equal to zero. Preserve existing values and later change history.',source='import')
    assert result.get('ok') and not result.get('refused'),result
    print('ZERO_REPAIR_RESULT',json.dumps({k:result.get(k) for k in ('ok','written','people','pending','reference','apply_id','state')},default=str))
    if not result.get('pending'):
        for change in changes:
            person=env['hr.employee'].browse(change['emp_id']);contract=probe._get_latest_contract(person)
            line=desk._advantage_line(probe,contract,'VNREGISTER');assert line and line.amount==0
    if os.getenv('APPLY_ZERO_REPAIR')=='1':env.cr.commit()
    else:env.cr.rollback()
else:env.cr.rollback()
