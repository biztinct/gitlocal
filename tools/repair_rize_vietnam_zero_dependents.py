"""Recover only explicit imported zero dependent counts; never infer a count."""
import hashlib,json,os
from pathlib import Path
assert env.cr.dbname=='rize'
source=Path(os.environ['VN_ZERO_SOURCE_DATA'])
assert hashlib.sha256(source.read_bytes()).hexdigest() == '530d646f34802027aef53434ba7f7e6e44640ac6fdd09fa7a4107495505f6749', 'Source data changed'
data=json.loads(source.read_text())
config=env['hr.formula.config'].browse(7118).exists()
assert config and config.country_code=='VN' and config.company_id.name=='Rize Farms'
desk=env['pb.records.desk'].with_company(config.company_id)
probe=desk._probe(config.id)
card=desk._cards(config.id)['c:VNREGISTER']
assert card['component']['code']=='VNREGISTER'
changes=[];skipped={};eligible=0
for row in data['records']:
    payroll=row.get('payroll')
    if not payroll or type(payroll['values'].get('VNREGISTER')) not in (int,float) or payroll['values']['VNREGISTER']!=0:continue
    eligible+=1
    people=env['hr.employee'].with_context(active_test=False).search([('company_id','=',config.company_id.id),'|',('barcode','=',row['key']),('employee_id','=',row['key'])])
    assert len(people)==1,'Ambiguous or missing source employee'
    contract=probe._get_latest_contract(people)
    assert contract
    if desk._advantage_line(probe,contract,'VNREGISTER'):
        skipped['already_saved']=skipped.get('already_saved',0)+1;continue
    history=env['hr.contract.advantage.change'].search([('contract_id','=',contract.id),('advantage_template_id.code','=','VNREGISTER')])
    if history:
        skipped['later_history']=skipped.get('later_history',0)+1;continue
    # A correction must apply to a previously imported contract, not a new one.
    imported=env['pb.records.change'].search([('employee_id','=',people.id),('model','=','hr.contract'),('res_id','=',contract.id)],limit=1)
    assert imported,'No previous Records Desk contract evidence'
    changes.append({'emp_id':people.id,'field_id':'c:VNREGISTER','value':0})
assert eligible==42,eligible
preview=desk.preview_changes(config.id,changes)
assert not any(i['status']!='ok' for i in preview['items']),preview['counts']
print('ZERO_REPAIR_PREVIEW',json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'eligible':eligible,'recoverable':len(changes),'skipped':skipped}))
if os.getenv('APPLY_ZERO_REPAIR')=='1':
    result=desk.apply_changes(config.id,changes,note='Recover explicit zero registered-dependent counts omitted by the original Vietnam master import because absent contract components compared equal to zero. Preserve existing values and later change history.',source='import')
    assert result.get('ok') and not result.get('refused'),result
    print('ZERO_REPAIR_RESULT',json.dumps(result,default=str))
    if not result.get('pending'):
        for change in changes:
            person=env['hr.employee'].browse(change['emp_id']);contract=probe._get_latest_contract(person)
            line=desk._advantage_line(probe,contract,'VNREGISTER');assert line and line.amount==0
    env.cr.commit()
else:env.cr.rollback()
