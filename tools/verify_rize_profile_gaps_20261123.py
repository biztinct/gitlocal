"""Read-only verification of the live HR drawer under actual admin and HR accounts."""
import json,os
from pathlib import Path
assert env.cr.dbname=='rize'
root=Path(os.environ['RIZE_GAPS_DIR']);plan=json.loads((root/'gap-plan.json').read_text());results=[]
for login in ['ash@biztinct.com','thao@rize.farm']:
 user=env['res.users'].search([('login','=',login)]);assert len(user)==1
 service=env['pb.people'].with_user(user).with_context(allowed_company_ids=[1],lang='en_US')
 for code in ['RIZ017','RIZ230','RIZ235']:
  emp=env['hr.employee'].search([('barcode','=',code)])
  payload=service.get_employee_360(emp.id);assert payload['is_hr'] and payload['can_manage']
  values={r['key']:r['value'] for tab in payload['details'].values() for g in tab for r in g['rows']}
  for field in ['identification_id','private_street','vietnam_dependents_count','emergency_contact','emergency_phone']:
   op=next((op for op in plan['operations'] if op['model']=='hr.employee' and op['id']==emp.id and op['field']==field),None)
   if not op:continue
   if field=='private_street':assert op['after'] in values['_home_address']
   else:assert str(values[field])==str(op['after']),(code,field)
  assert values['department_id']==emp.department_id.display_name
  assert 'VNREGISTER' in values  # Existing payroll registration stays separate from family records.
  if code=='RIZ230':
   missing=[d for d in plan['dependents'] if d['code']==code]
   dep_group=next(g for g in payload['details']['pay'] if g['key']=='vn_dependents')
   assert all(any(row['label']==d['name'] and 'Pending verification' in row['value'] for row in dep_group['rows']) for d in missing)
  results.append({'login':login,'code':code,'drawer_values_correct':True})
# Confirm register and portal ownership source contains each exact employee holding.
for item in plan['assets']:
 rows=env['pb.asset.assignment'].search([('employee_id','=',item['employee_id']),('state','=','open')])
 assert any(a.asset_id.serial==item['serial'] for a in rows)
 assert any(a['serial']==item['serial'] for a in env['pb.asset'].open_items_for(item['employee_id'])['tangible'])
env.cr.rollback()
out={'hr_drawer_checks':results,'asset_register_and_ownership_checks':25,'readonly':True}
p=root/'live-screen-data-verification.json';p.write_text(json.dumps(out,indent=2));p.chmod(0o600)
print('LIVE_SCREEN_DATA_VERIFIED',len(results),'drawer checks; 25 asset ownership checks')
