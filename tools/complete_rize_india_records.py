"""Apply the reviewed India master through Records Desk, Rize only.

IN_SETUP_DIR contains the private record-plan.json. The owner explicitly chose
master IDs/names, including the reviewed surname, and kept the ambiguous stipend
pending. Default rollback. IN_SETUP_APPLY=1 commits only after every proposed
record update has passed the published approval route and verification.
"""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path


assert env.cr.dbname=='rize'
root=Path(os.environ['IN_SETUP_DIR'])
definition=json.loads((root/'definition.json').read_text())
plan=json.loads((root/'record-plan.json').read_text())
assert plan['stipend_decision']=='pending'
assert len(plan['records'])==35 and len(plan['crosswalk'])==27
cfg=env['hr.formula.config'].search([('code','=',definition['code'])])
assert len(cfg)==1 and cfg.state=='draft' and cfg.company_id.name=='Rize Farms'
e=env(user=int(os.getenv('IN_SETUP_USER_ID','2')),context=dict(env.context,allowed_company_ids=cfg.company_id.ids))
cfg=cfg.with_env(e);desk=e['pb.records.desk'];api=e['pb.payroll.templates'];studio=e['pb.formula.studio']
api._lock(cfg)
assert not e['hr.payslip'].search_count([('formula_config_id','=',cfg.id)])
by={r.code:r for r in cfg.rule_ids}
specs={r['code']:r for r in definition['rules']}
assert set(by)==set(specs)
for code in ('INHCK','INHCZ','INPFMODE'):
    spec=specs[code]
    by[code].write(dict(value_kind=spec['kind'],value_kind_source='user',is_required=spec['required']))
    if code=='INHCZ':
        assert studio.employee_mapping_create(cfg.id,'',by[code].id,spec['destination']).get('ok')
cards=desk._cards(cfg.id)
card_by_code={card['component']['code']:fid for fid,card in cards.items() if card.get('component')}


def digest(table):
    e.cr.execute('SELECT row_to_json(t)::text FROM '+table+' t ORDER BY id')
    return hashlib.sha256('\n'.join(r[0] for r in e.cr.fetchall()).encode()).hexdigest()


untouched={t:digest(t) for t in ('hr_payslip','hr_payslip_run','pb_payroll_month_inputs','vietnam_employee_dependent')}
people={};contracts={};created_people=[];created_contracts=[];issues=[]
Employee=e['hr.employee'].with_context(active_test=False)
Contract=e['hr.contract'].with_context(active_test=False)
existing_ids={r['existing_employee_id'] for r in plan['records'] if r.get('existing_employee_id')}
assert len(existing_ids)==27
assert all(Employee.browse(i).company_id==cfg.company_id for i in existing_ids)
for record in plan['records']:
    key=record['code'];values=record['values']
    if record.get('existing_employee_id'):
        person=Employee.browse(record['existing_employee_id']).exists()
        assert person.barcode==record['payroll_code'],(key,'Identity changed since review')
    else:
        assert not Employee.search_count(['|',('barcode','=',key),('employee_id','=',key)]),(key,'Unexpected existing identity')
        person=Employee.create(dict(name=record['name'],employee_id=key,barcode=key,company_id=cfg.company_id.id,active=True))
        created_people.append(person.id)
    people[key]=person
    contract=desk._io_contracts(person).get(person.id)
    if not contract:
        start=values.get('INHCAL') or values.get('INJOIN')
        assert start and str(start)[:10].count('-')==2,(key,'Missing contract start')
        contract=Contract.create(dict(name='India master — '+key,employee_id=person.id,company_id=cfg.company_id.id,
                                     date_start=str(start)[:10],wage=0,state='draft',payroll_country='IN'))
        created_contracts.append(contract.id)
    contracts[key]=contract
    # Set the explicit denomination before writing Monetary amounts. This is
    # part of the atomic owner-authorized record import, not a currency conversion.
    contract.payroll_country='IN'

# Respect current uniqueness during the six ID renames. A target is written
# only after the employee who previously held it has moved to their master ID.
# Records Desk retains the order and audits the real-user writes atomically.
pending=[r for r in plan['records'] if r.get('existing_employee_id')]
ordered=[]
held={str(p.barcode or ''):p.id for p in Employee.search([('company_id','=',cfg.company_id.id)]) if p.barcode}
while pending:
    free=[r for r in pending if held.get(r['code']) in (None,people[r['code']].id)]
    assert free,'Identity cycle requires an explicit migration plan; no records changed.'
    for record in free:
        person=people[record['code']]
        held.pop(person.barcode,None);held[record['code']]=person.id
        ordered.append(record);pending.remove(record)
ordered += [r for r in plan['records'] if not r.get('existing_employee_id')]

changes=[]
for record in ordered:
    person=people[record['code']]
    values=record['values']
    for spec in definition['rules']:
        code=spec['code'];fid=card_by_code.get(code)
        if not fid:continue  # monthly input and formula output have no record destination
        value=values.get(code)
        if value is None or value=='':continue
        if spec['kind']=='date':
            value=str(value)[:10]
            datetime.strptime(value,'%Y-%m-%d')
        elif spec['kind'] in ('text','identifier'):
            if isinstance(value,float) and value.is_integer():value=int(value)
            value=str(value).strip()
        changes.append(dict(emp_id=person.id,field_id=fid,value=value))
    # The source end date is preserved while its contradictory master "Active"
    # status remains visible as source context; period selection handles the exit.
    if values.get('INDOR') and record['active']:
        issues.append(dict(code=record['code'],issue='August DOR conflicts with master Active status; contract end date follows final payroll. Payment Hold retained.'))
preview=desk.preview_changes(cfg.id,changes)
assert not preview['counts']['refused'],[i for i in preview['items'] if i['status']=='refused']
applied=desk.apply_changes(cfg.id,changes,note='Owner-authorized India rebuild. Employee master IDs and reviewed names are authoritative. August final payroll supplies historical pay and contract CTC. The ambiguous stipend identity remains pending. No payroll payment is authorized.',source='import')
assert applied.get('ok') and not applied.get('refused'),applied
assert not applied.get('pending'),{'pending_record_request':applied.get('reference'),'with_whom':applied.get('with_whom'),'note':'Use the published approval route; never bypass it.'}

for record in plan['records']:
    key=record['code'];person=people[key];contract=contracts[key]
    assert person.barcode==person.employee_id==key and person.name==record['name'],key
    if record['active']:
        assert contract.state in ('open','close') and contract.wage>0,(key,'Expected a salaried contract for August')
        if contract.state=='close':
            assert record['values']['INDOR'] and str(contract.date_end)==str(record['values']['INDOR'])[:10],key
        contract.payroll_country='IN'
    else:
        assert contract.state=='draft' and not record['payroll_row']
        person.active=False
    if record.get('payroll_row'):
        # Native monthly money is stored to cents. Payroll still derives its
        # component calculations from the unrounded annual CTC, as the source does.
        assert abs(contract.wage-record['values']['INHCBL'])<.00001,(key,contract.wage,record['values']['INHCBL'],contract.currency_id.name,contract.currency_id.rounding)
        assert abs(desk._read_cell(desk._probe(cfg.id),cards[card_by_code['INANNFIX']],person,contract)['v']-record['values']['INANNFIX'])<.00001,key
assert len(created_people)==len(created_contracts)==8
assert not Employee.search_count([('name','=',plan['pending_stipend']['name'])])
saved=e['pb.payroll.template.layout'].sudo().search([('config_id','=',cfg.id),('company_id','=',cfg.company_id.id)])
assert len(saved)==1
roster=[people[r['code']].id for r in plan['records'] if r['active']]
saved.payload=dict(saved.payload or {},preview_employee_ids=roster,preview_expected_count=27)
assert len(api._roster(cfg,'2026-08'))==27
assert {t:digest(t) for t in untouched}==untouched,'No payroll or dependent transactions may be changed by master-data import.'
report=dict(database='rize',config_id=cfg.id,master_records=35,active_review_roster=27,
    archived_profiles_created=len(created_people),draft_archived_contracts_created=len(created_contracts),
    renamed_source_ids=6,records_reference=applied['reference'],values_written=applied['written'],
    records_pending=False,issues=issues,stipend_pending=True,
    committed=os.getenv('IN_SETUP_APPLY')=='1')
if report['committed']:e.cr.commit()
else:e.cr.rollback()
print('IN_RECORDS_RESULT '+json.dumps(report,ensure_ascii=False))
