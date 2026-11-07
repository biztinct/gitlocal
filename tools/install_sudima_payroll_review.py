"""Sudima-only draft setup through existing UI services; default rollback.

SUDIMA_REVIEW_DIR contains definition.json, private-fixtures.json and template.xlsx.
SUDIMA_REVIEW_APPLY=1 commits a fresh install. SUDIMA_REVIEW_VERIFY=1 reads and
tests an existing install, without reapplying customer edits. No shared modules,
approval policies, payroll runs, scheme assignments or attendance are changed.
"""
import base64
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path

assert env.cr.dbname == 'sudima', 'Customer records belong only in Sudima.'
root = Path(os.environ['SUDIMA_REVIEW_DIR'])
definitions = json.loads((root/'definition.json').read_text())
assert len(definitions) == 1 and definitions[0]['view'] == 'audit', 'Actual Pay extras are not authorized for implementation.'
private = json.loads((root/'private-fixtures.json').read_text())
verify = os.getenv('SUDIMA_REVIEW_VERIFY') == '1'
apply = os.getenv('SUDIMA_REVIEW_APPLY') == '1'
assert not (apply and verify)
previous=json.loads((root/'applied.json').read_text()) if verify else {}
e = env(user=2, context=dict(env.context, allowed_company_ids=[1], lang='en_US'))
assert e.company.name == 'Sudima Panels Vietnam'
studio = e['pb.formula.studio']
blueprints = e['pb.blueprint.studio']
desk = e['pb.records.desk']
facade = e['pb.payroll.templates']
Config = e['hr.formula.config']
Sample = e['hr.formula.sample.data']
Employee = e['hr.employee'].with_context(active_test=False)
Contract = e['hr.contract'].with_context(active_test=False)

def snapshot(model):
    records = e[model].search([])
    names = [n for n,f in records._fields.items() if f.store and not f.compute and f.type != 'binary']
    data = records.read(names)
    return {'count':len(records),'sha256':hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()}

protected = {m:snapshot(m) for m in ('hr.payslip','hr.payslip.run','hr.attendance','hr.formula.scheme.assignment')}
report = {'database':'sudima','mode':'verify' if verify else 'apply' if apply else 'rollback',
          'configuration':[],'created_employees':0,'created_contracts':0,'master_issues':[],
          'source_sha256':private['source_sha256']}
calendar=e.company.resource_calendar_id
assert calendar and calendar.company_id == e.company
if not verify:
    calendar.tz='Asia/Ho_Chi_Minh'
assert calendar.tz=='Asia/Ho_Chi_Minh'
report['calendar_timezone']=calendar.tz
installed = {}
for spec in definitions:
    cfg = Config.search([('code','=',spec['code'])])
    assert len(cfg) <= 1 and bool(cfg) == verify, 'Existing draft: verify it; never overwrite customer edits.'
    if not cfg:
        started = blueprints.bp_start(dict(name=spec['name'],country_code='VN',cycle_type='regular',
            template_key='excel',effective_from='2026-09-01'),token=spec['code'].lower())
        assert started.get('ok'),started
        cfg=Config.browse(started['config_id'])
        cfg.write({'code':spec['code'],'application_effective_from':'2026-09-01',
            'application_data_enabled':False,'payroll_basis':'timesheet','standard_day_basis':'calendar',
            'focused_payroll_inputs':True,
            'description':'<p>September 2026 historical reconciliation. Amounts converted from thousands to VND. '
                'No monthly historical values are defaults. This draft is not assigned to employees or released.</p>'
                '<p>Print-Audit base calculation only. Actual Pay extras are excluded by owner instruction. Source allowances, '
                'insurance, relief and explicit exceptions remain test inputs pending policy confirmation. '
                'Tax uses the Print-Audit basis, including its explicit historical exceptions.</p>'
                '<p>Automatic payroll awaits raw punches, shifts, breaks, approved overtime, allowance rules, '
                'employee eligibility and verified contracts. Do not activate this reconciliation draft as an unattended payroll.</p>',
            'import_sample_file':base64.b64encode((root/'template.xlsx').read_bytes()),
            'import_sample_filename':'Sudima_September_Payroll_Review_Template.xlsx'})
        cfg.sample_data_ids.write({'active':False})
        for r in spec['rules']:
            created=studio.add_component(cfg.id,dict(name=r['name'],code=r['code'],column_type='input',value_kind=r['kind']))
            assert created.get('ok'),created
            added=e['hr.formula.rule'].browse(created['rule_id'])
            if added.code != r['code']:
                renamed=studio.rename_component(added.id,r['code'])
                assert renamed.get('ok'),(r['code'],renamed)
        by={r.code:r for r in cfg.rule_ids}
        assert set(by)=={r['code'] for r in spec['rules']}
        for r in spec['rules']:
            rule=by[r['code']]
            rule.write(dict(value_kind=r['kind'],value_kind_source='user',net_role=r['role'],net_role_source='user',
                net_role_confidence='certain',net_role_detail=False,is_required=r['required'],
                column_role='identity' if r['code'] in ('VNID','VNNAME') else 'payroll',column_role_source='user',
                appears_on_payslip=r['role'] in ('earning','deduction','net'),report_visible=True,
                number_format='currency' if r['kind']=='money' else 'number',
                application_source_key=r['application'] or False,application_source_required=bool(r['application'])))
            if r['formula']:
                formula='='+r['formula'].format(**{c:x.column_letter+'2' for c,x in by.items()})
                saved=studio.save_component(rule.id,dict(column_type='formula',excel_formula=formula))
                assert saved.get('ok'),(r['code'],saved)
            else:
                rule.set_source_binding('excel',spec['view'].title()+'|'+r['name'],origin='user')
                if r['destination']:
                    mapped=studio.employee_mapping_create(cfg.id,'',rule.id,r['destination'])
                    assert mapped.get('ok'),(r['code'],mapped)
        by['VNBASIS'].value_labels='1=Monthly;2=Daily'
        for code in ('VNTAXZERO','VNRECOVERYUSED'):
            by[code].value_labels='0=No;1=Yes'
    else:
        by={r.code:r for r in cfg.rule_ids}
    assert cfg.state=='draft' and not cfg.application_data_enabled
    for r in spec['rules']:
        if r['formula']:
            assert by[r['code']].excel_formula=='='+r['formula'].format(**{c:x.column_letter+'2' for c,x in by.items()})
    installed[spec['view']] = (cfg,by)
    comparisons=0;total=0
    for i,fixture in enumerate(private['views'][spec['view']]):
        sample=Sample.new(dict(config_id=cfg.id))
        errors={}
        values=sample._evaluate_rules_with_dependencies(fixture['inputs'],readonly=True,errors=errors)
        assert not errors, (spec['view'],fixture['source_row'],errors)
        for code,expected in fixture['expected'].items():
            assert isinstance(values.get(code),(int,float)) and math.isclose(values[code],expected,rel_tol=0,abs_tol=.01), \
                (spec['view'],fixture['source_row'],code,values.get(code),expected)
            comparisons+=1
        total+=values['VNNET']
        earned=sum(values[r.code] for r in cfg.rule_ids if r.net_role=='earning')
        deducted=sum(values[r.code] for r in cfg.rule_ids if r.net_role=='deduction')
        assert math.isclose(earned-deducted,values['VNNET'],rel_tol=0,abs_tol=.01),('pay role rollup',spec['view'],fixture['source_row'])
        if not verify:
            Sample.create(dict(config_id=cfg.id,name='September source row %s'%fixture['source_row'],sequence=i+1,
                source_type='manual',source_date='2026-09-30',is_anonymized=False,
                description='Historical '+spec['view']+' workbook inputs, converted to VND. These are test values, not recurring monthly defaults.',
                input_values_json=json.dumps(fixture['inputs']),expected_inputs_json=json.dumps(fixture['inputs']),
                expected_values_json=json.dumps(fixture['expected'])))
    tests=cfg.run_sample_tests()
    assert tests['failed']==0, tests
    report['configuration'].append(dict(id=cfg.id,code=cfg.code,state=cfg.state,components=len(by),
        employees=len(private['views'][spec['view']]),net_vnd=total,component_comparisons=comparisons,tests=tests))
    print('SUDIMA_CONFIG_CHECK',json.dumps(report['configuration'][-1]),flush=True)

# Import identity once. Existing blank-code demo/admin employees are preserved.
people=Employee.search([('company_id','=',e.company.id)])
existing_ids=people.ids
roster=[]
master_changes=[]
audit_fixtures={f['key']:f for f in private['views']['audit']}
for record in private['employees']:
    person=people.filtered(lambda p:record['code'] in (p.barcode,p.employee_id))
    assert len(person)<=1, 'Ambiguous employee code'
    if not person:
        assert not verify, 'Missing imported employee'
        department=e['hr.department'].search([('company_id','=',e.company.id),('name','=',record['department'])]) if record['department'] else e['hr.department']
        assert len(department)<=1
        if not department and record['department']:
            department=e['hr.department'].create(dict(name=record['department'],company_id=e.company.id))
        person=Employee.create(dict(name=record['name'],company_id=e.company.id,barcode=record['code'],
            employee_id=record['code'],department_id=department.id or False))
        person.resource_id.tz='Asia/Ho_Chi_Minh'
        people|=person
        report['created_employees']+=1
    roster.append(person.id)
    contract=desk._io_contracts(person).get(person.id)
    if not contract:
        assert not verify, 'Missing September baseline contract'
        contract=Contract.create(dict(name='September 2026 salary baseline — '+record['code'],employee_id=person.id,
            company_id=e.company.id,date_start='2026-09-01',wage=0,state='draft'))
        report['created_contracts']+=1
    assert contract.state=='draft', 'Do not overwrite a reviewed/activated contract'
    def master(field,value):
        master_changes.append(dict(emp_id=person.id,field_id=field,value=value))
    try:
        date=datetime.strptime(record['join_date'],'%d/%m/%Y').date().isoformat()
        master('f:hr.employee:date_of_joining',date)
    except (ValueError,TypeError):
        report['master_issues'].append({'key':record['key'],'field':'Joining date','reason':'Source requires date review'})
    if record['government_id'].isdigit() and len(record['government_id'])==12:
        master('f:hr.employee:identification_id',record['government_id'])
    elif record['government_id']:
        report['master_issues'].append({'key':record['key'],'field':'Government ID','reason':'Source is not a complete 12-digit identifier; not padded or guessed'})
    if record['bank_account'].isdigit() and 6<=len(record['bank_account'])<=24:
        master('b:acc_number',record['bank_account'])
        if record['bank_name']: master('b:bank_name',record['bank_name'])
        if record['bank_holder']: master('b:acc_holder_name',record['bank_holder'])
    elif record['bank_account']:
        report['master_issues'].append({'key':record['key'],'field':'Bank account','reason':'Source account requires review'})
    inputs=audit_fixtures[record['key']]['inputs']
    master('f:hr.contract:wage',inputs['VNBASE']*(26 if inputs['VNBASIS']==2 else 1))

if not verify:
    result=desk.apply_changes(0,master_changes,note='Sudima September 2026 employee master from supplied payroll. Preserve identifiers verbatim. Salary contracts are September review baselines, not confirmed employment terms.',source='import')
    assert result.get('ok') and not result.get('refused'), result.get('refused')
    report['master_import']={k:result.get(k) for k in ('reference','written','pending','people','with_whom')}
    print('SUDIMA_MASTER_IMPORT',json.dumps(report['master_import']),flush=True)
else:
    proposal=e['pb.records.apply'].sudo().search([('name','=',previous['master_import']['reference'])])
    assert len(proposal)==1
    report['master_import']=dict(reference=proposal.name,pending=not proposal.applied,with_whom=proposal._waiting_for())
if not report['master_import']['pending']:
    cards=desk._cards(0)
    probe=desk._probe(0)
    contracts=desk._io_contracts(Employee.browse(roster))
    for change in master_changes:
        person=Employee.browse(change['emp_id'])
        saved=desk._read_cell(probe,cards[change['field_id']],person,contracts[person.id])
        assert saved['v']==change['value'],('Stored master mismatch',change['field_id'],person.id)
    report['master_value_checks']=len(master_changes)

for spec in definitions:
    cfg,by=installed[spec['view']]
    fixtures={f['key']:f for f in private['views'][spec['view']]}
    changes=[]
    selected=[]
    for record,person_id in zip(private['employees'],roster):
        fixture=fixtures.get(record['key'])
        if not fixture: continue
        selected.append(person_id)
        for rule in spec['rules']:
            if rule['destination']=='c:amount':
                changes.append(dict(emp_id=person_id,field_id='c:'+rule['code'],value=fixture['inputs'][rule['code']]))
    if not verify:
        result=desk.apply_changes(cfg.id,changes,note='September 2026 source salary baseline, awaiting contract/policy review. Historical time and variable allowances are test-only.',source='import')
        assert result.get('ok') and not result.get('refused'), result.get('refused')
        report['configuration'][definitions.index(spec)]['records']={k:result.get(k) for k in ('reference','written','pending','people','with_whom')}
        catalog=facade._catalog(cfg)
        specs={r['code']:r for r in spec['rules']}
        layout={k:[] for k in ('time','adjustments','records','available')}
        for col in catalog:
            rule=specs.get(col.get('code'))
            lane='records' if col.get('record_eligible') else rule['lane'] if rule and not rule['formula'] else 'available'
            layout[lane].append(col['id'])
        assert facade.save_layout(cfg.id,layout)['ok']
    else:
        prior=next(c for c in previous['configuration'] if c['code']==cfg.code)
        proposal=e['pb.records.apply'].sudo().search([('name','=',prior['records']['reference'])])
        assert len(proposal)==1
        report['configuration'][definitions.index(spec)]['records']=dict(reference=proposal.name,pending=not proposal.applied,with_whom=proposal._waiting_for())
    if not report['configuration'][definitions.index(spec)]['records']['pending']:
        cards=desk._cards(cfg.id)
        probe=desk._probe(cfg.id)
        saved_contracts=desk._io_contracts(Employee.browse(selected))
        for change in changes:
            person=Employee.browse(change['emp_id'])
            read=desk._read_cell(probe,cards[change['field_id']],person,saved_contracts[person.id])
            assert read['v']==change['value'],('Stored salary component mismatch',change['field_id'],person.id)
        report['configuration'][definitions.index(spec)]['stored_component_checks']=len(changes)
    workspace=facade.workspace(cfg.id,'2026-09')
    # Preview-roster internals have no UI writer. Do not seed them directly.
    # The draft has no live payroll assignments; its Test step holds the roster.
    assert workspace['people']==0,(cfg.code,'Unexpected active payroll roster')
    assert not e['pb.payroll.month.inputs'].sudo().search_count([('config_id','=',cfg.id)])

assert {m:snapshot(m) for m in protected}==protected, 'Payroll, attendance or assignments changed'
report['roster']=len(roster)
report['protected']=protected
report['existing_employee_ids_preserved']=existing_ids
(root/('verify.json' if verify else 'applied.json' if apply else 'dry-run.json')).write_text(json.dumps(report,indent=2,default=str))
if apply:
    e.cr.commit()
else:
    e.cr.rollback()
print('SUDIMA_REVIEW_RESULT',json.dumps({k:v for k,v in report.items() if k not in ('protected','existing_employee_ids_preserved')},default=str))
