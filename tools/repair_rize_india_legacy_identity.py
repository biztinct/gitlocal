"""Clear legacy payroll-code placeholders from Government ID, Rize only.

The reviewed master has no Government ID for these people. Only a value equal
to that person's original payroll code is eligible; actual government IDs are
never cleared. The original code remains a separate contract reference alias.
Uses Records Desk's published approval route and rolls back unless explicitly
applied. The private record-plan.json is not part of the repository.
"""
import json,os
from pathlib import Path

assert env.cr.dbname=='rize'
root=Path(os.environ['IN_SETUP_DIR']);plan=json.loads((root/'record-plan.json').read_text())
baseline={p['id']:p for p in json.loads((root/'before.json').read_text())['employees_hr_fields']}
e=env(user=int(os.getenv('IN_SETUP_USER_ID','2')),context=dict(env.context,allowed_company_ids=[1]))
cfg=e['hr.formula.config'].search([('code','=','RIZE_INDIA_CLIENT_MASTER_2026')])
assert len(cfg)==1 and cfg.company_id.name=='Rize Farms'
desk=e['pb.records.desk'];e['pb.payroll.templates']._lock(cfg)
field='f:hr.employee:identification_id'
assert desk._cards(cfg.id)[field]['editable'],'Use the published records route; never bypass its restrictions.'
changes=[]
for record in plan['records']:
    if not record.get('existing_employee_id') or record['values'].get('INHCAN'):
        continue
    person=e['hr.employee'].browse(record['existing_employee_id']).exists()
    assert person.employee_id==person.barcode==record['code']
    original=baseline[person.id].get('identification_id')
    if original==record['payroll_code']:
        assert person.identification_id==original,'Government ID changed since the audit; inspect before clearing.'
        changes.append(dict(emp_id=person.id,field_id=field,value=''))
assert len(changes)>=6,'The audited legacy code placeholders must be present before this repair.'
preview=desk.preview_changes(cfg.id,changes)
assert not preview['counts']['refused'],preview
result=desk.apply_changes(cfg.id,changes,source='desk',note='Owner-authorized India rebuild: remove legacy employee-code placeholders from Government ID where the authoritative master supplies no Government ID. Original payroll aliases remain in their dedicated contract information component. No actual government identifier is removed.')
assert result.get('ok') and not result.get('pending') and not result.get('refused'),result
assert result['written']==len(changes)
assert all(not e['hr.employee'].browse(c['emp_id']).identification_id for c in changes)
committed=os.getenv('IN_SETUP_APPLY')=='1'
if committed:e.cr.commit()
else:e.cr.rollback()
print('IN_LEGACY_ID_RESULT '+json.dumps(dict(cleared_placeholders=len(changes),records_reference=result['reference'],pending=False,committed=committed)))
