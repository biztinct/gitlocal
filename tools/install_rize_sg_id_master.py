"""Install/review Rize SG/ID client definitions using the published ORM APIs.

RIZE_MASTER_DIR holds private definitions, fixtures and record plans. Select
RIZE_MASTER_COUNTRY=SG/ID and RIZE_MASTER_PHASE=definition/refine/records/bankfill/activate/
attach/verify. Default is rollback; RIZE_MASTER_APPLY=1 persists after assertions.
No approval, payment, bank submission or accounting posting is performed.
"""
import base64
from datetime import date
import hashlib
import json
import os
from pathlib import Path


assert env.cr.dbname=='rize','Client payroll belongs only to Rize.'
root=Path(os.environ['RIZE_MASTER_DIR'])
country=os.environ['RIZE_MASTER_COUNTRY']
assert country in {'SG','ID'}
key=country.lower()
definition=json.loads((root/(key+'-definition.json')).read_text())
records=json.loads((root/(key+'-record-plan.json')).read_text())['records']
fixtures=json.loads((root/(key+'-fixtures.json')).read_text())
phase=os.environ.get('RIZE_MASTER_PHASE','definition')
apply=os.environ.get('RIZE_MASTER_APPLY')=='1'
company=env['res.company'].search([('name','=',definition['company'])])
assert len(company)==1
e=env(user=int(os.environ.get('RIZE_MASTER_USER_ID','2')),context=dict(env.context,allowed_company_ids=company.ids))
studio=e['pb.formula.studio'];api=e['pb.payroll.templates'];desk=e['pb.records.desk']
assert studio._can_edit()
Config=e['hr.formula.config'].with_context(active_test=False)
cfg=Config.search([('code','=',definition['code']),('company_id','=',company.id)])
old=Config.search([('code','=',definition['source_config_code']),('company_id','=',company.id)])
assert len(old)==1 and old.country_code==country


def digest(table):
    e.cr.execute('SELECT row_to_json(t)::text FROM '+table+' t ORDER BY id')
    return hashlib.sha256('\n'.join(r[0] for r in e.cr.fetchall()).encode()).hexdigest()


def existing_rows(table,ids):
    e.cr.execute('SELECT row_to_json(t)::text FROM '+table+' t WHERE id=ANY(%s) ORDER BY id',[ids])
    return hashlib.sha256('\n'.join(r[0] for r in e.cr.fetchall()).encode()).hexdigest()


transaction_tables=('hr_payslip','hr_payslip_run','pb_payroll_month_inputs')
baseline={t:digest(t) for t in transaction_tables}
report=dict(database='rize',country=country,phase=phase,committed=apply)
specs={s['code']:s for s in definition['rules']}
if phase=='definition':
    assert not cfg,'Do not replace an installed or concurrently created definition.'
    preserved={t:digest(t) for t in ('hr_employee','hr_contract','hr_contract_advantage','res_partner_bank')}
    old_snapshot=old.rule_ids.read(['code','name','column_letter','column_type','excel_formula','constant_value','is_contract_component','is_text_component'])
    cfg=Config.create(dict(name=definition['name'],code=definition['code'],country_code=country,
        company_id=company.id,state='draft',cycle_type='regular',source_priority='records,excel,api',
        description=''.join('<p>'+s+'</p>' for s in definition['notes'])))
    api._lock(cfg)
    original={r.code:r for r in old.rule_ids}
    create=[]
    taxfields=('tax_table_id','tax_field','tax_band_sequence','tax_parameter_code','tax_source_sheet','tax_source_cell')
    for i,s in enumerate(definition['rules']):
        values=dict(config_id=cfg.id,code=s['code'],name=s['name'],sequence=(i+1)*10,
            column_letter=s['column'],column_type='input' if s['type']=='formula' else s['type'],
            component_type=s['group'],value_kind=s['kind'],value_kind_source='user',
            value_kind_reason='Reviewed against the supplied August payroll and employee master.',
            net_role=s['role'],net_role_detail=s['detail'],net_role_source='user',net_role_confidence='certain',
            net_role_reason=s['note'] or 'Preserved source payroll calculation and reviewed treatment.',
            column_role='payroll' if s['tab'] or s['type']!='input' else 'profile',column_role_source='user',
            is_required=s['required'],appears_on_payslip=s['role']!='info',
            visibility_rule='when_nonzero' if s['role']!='info' else 'never',report_visible=True,
            number_format={'money':'currency','rate':'percentage','integer':'integer'}.get(s['kind'],'number'))
        if s['type']=='constant':values['constant_value']=s['value']
        src=original.get(s.get('original_code'))
        if src:
            for field in taxfields:
                if field in src._fields:
                    values[field]=src[field].id if src._fields[field].type=='many2one' else src[field]
        create.append(values)
    made=e['hr.formula.rule'].create(create)
    by={r.code:r for r in made}
    for s in definition['rules']:
        r=by[s['code']]
        if s['type']=='input':
            r.set_source_binding('excel',s['source_key'],origin='user')
            r.source_sheet_name='Consolidated'
            if s['destination']:
                answer=studio.employee_mapping_create(cfg.id,'',r.id,s['destination'])
                assert answer.get('ok'),(s['code'],answer)
                r.write(dict(column_role='contract' if r.is_contract_component or s['destination'].startswith('f:hr.contract:') else 'profile',column_role_source='user',
                    net_role=s['role'],net_role_detail=s['detail'],net_role_source='user',net_role_confidence='certain'))
        if s['formula']:r.write(dict(column_type='formula',excel_formula=s['formula']))
    for code in (definition['primary_code'],definition['native_id_code'],definition['name_code']):
        by[code].write(dict(column_role='identity',column_role_source='user'))
    # Purely informational full-month CTC helpers do not compete with payslip
    # totals and never enter spreadsheet/record input mapping.
    if country=='SG':
        for col in ('N','O','P','Q'):
            made.filtered(lambda r:r.column_letter==col).write(dict(column_role='reference',column_role_source='user'))
    catalog=api._catalog(cfg)
    ids={c['code']:c['id'] for c in catalog if c['code']}
    requested=definition['time_order']+definition['adjustments_order']
    layout=dict(time=[ids[c] for c in definition['time_order']],adjustments=[ids[c] for c in definition['adjustments_order']],
        records=[c['id'] for c in catalog if c['record_eligible']],
        available=[c['id'] for c in catalog if not c['record_eligible'] and c['id'] not in [ids[k] for k in requested]])
    assert api.save_layout(cfg.id,layout)['ok']
    for i,f in enumerate(fixtures):
        values={s['code']:f['values'].get(s['code']) for s in definition['rules'] if s.get('original_code') and s['type']=='input' or s.get('tab')}
        values[definition['primary_code']]='CONTROL'+str(i+1)
        values[definition['name_code']]='August control '+str(i+1)
        for s in definition['rules']:
            if s['destination'].startswith('b:'):values.pop(s['code'],None)
        e['hr.formula.sample.data'].create(dict(config_id=cfg.id,name='Client August row '+str(f['row']),sequence=i+1,
            source_type='import',source_date='2026-08-01',is_anonymized=True,input_values_json=json.dumps(values),
            expected_inputs_json=json.dumps(values),expected_values_json=json.dumps(f['expected']),expected_confirmed=True))
    cfg.action_validate_formulas()
    assert not cfg.has_errors and not cfg.has_circular_refs,(cfg.has_errors,cfg.has_circular_refs)
    treatment=cfg.value_kind_board()
    assert treatment['review_count']==treatment['role_conflict_count']==treatment['drift_count']==0,{
        k:treatment[k] for k in ('review_count','role_conflict_count','drift_count')}
    tests=cfg.run_sample_tests()
    assert tests['total']==tests['passed']==len(fixtures) and tests['failed']==tests['pending']==0,tests
    exact=0
    for sample,f in zip(cfg.sample_data_ids.sorted('sequence'),fixtures):
        actual=json.loads(sample.computed_values_json)
        for code,value in f['expected'].items():
            if isinstance(value,(int,float)):assert abs(float(actual[code])-value)<.00001,(f['row'],code,actual[code],value)
            else:assert actual[code]==value,(f['row'],code,actual[code],value)
            exact+=1
    assert not made.filtered(lambda r:r.column_type!='input' and (r.source_ids or r.is_contract_component or r.is_text_component))
    assert old.rule_ids.read(['code','name','column_letter','column_type','excel_formula','constant_value','is_contract_component','is_text_component'])==old_snapshot
    assert {t:digest(t) for t in preserved}==preserved
    report.update(config_id=cfg.id,components=len(made),tests=tests,exact_comparisons=exact,
        inputs=sum(r.column_type=='input' for r in made),formulas=sum(r.column_type=='formula' for r in made),
        statutory_bindings=len(made.filtered('tax_table_id')),time=len(layout['time']),adjustments=len(layout['adjustments']))
elif phase=='refine':
    assert len(cfg)==1 and cfg.state=='draft' and country=='ID'
    assert not e['hr.payslip'].search_count([('formula_config_id','=',cfg.id)])
    api._lock(cfg)
    missing=set(specs)-set(cfg.rule_ids.mapped('code'))
    assert missing<={'IDBANKCODE','IDPAYROLLNIK'},missing
    for code in sorted(missing,key=lambda k:specs[k]['column']):
        spec=specs[code]
        rule=e['hr.formula.rule'].create(dict(config_id=cfg.id,code=code,name=spec['name'],column_letter=spec['column'],
            sequence=(definition['rules'].index(spec)+1)*10,column_type='input',value_kind='identifier',value_kind_source='user',
            net_role='info',net_role_source='user',net_role_confidence='certain',net_role_reason=spec['note'],
            component_type='Employee master',column_role='contract',column_role_source='user',appears_on_payslip=False,visibility_rule='never'))
        rule.set_source_binding('excel',spec['source_key'],origin='user')
        rule.source_sheet_name='Consolidated'
        assert studio.employee_mapping_create(cfg.id,'',rule.id,spec['destination']).get('ok')
    cfg.write({'description':''.join('<p>'+s+'</p>' for s in definition['notes'])})
    if missing:
        catalog=api._catalog(cfg);ids={c['code']:c['id'] for c in catalog if c['code']}
        requested=definition['time_order']+definition['adjustments_order']
        layout=dict(time=[ids[c] for c in definition['time_order']],adjustments=[ids[c] for c in definition['adjustments_order']],
            records=[c['id'] for c in catalog if c['record_eligible']],
            available=[c['id'] for c in catalog if not c['record_eligible'] and c['id'] not in [ids[k] for k in requested]])
        assert api.save_layout(cfg.id,layout)['ok']
    changed=[]
    for rule in cfg.rule_ids.filtered(lambda r:r.column_type=='formula'):
        spec=specs[rule.code]
        if rule.excel_formula!=spec['formula']:
            assert rule.column_letter=='BS','Only the final-period gross-up residual refinement is authorized here.'
            rule.write(dict(excel_formula=spec['formula'],net_role_reason=spec['note']))
            changed.append(rule.code)
    end_rule=cfg.rule_ids.filtered(lambda r:r.column_letter=='H')
    assert len(end_rule)==1 and specs[end_rule.code]['name']=='Contract end date'
    end_rule.write({'name':specs[end_rule.code]['name']})
    end_rule.set_source_binding('excel',specs[end_rule.code]['source_key'],origin='user')
    cfg.action_validate_formulas()
    assert not cfg.has_errors and not cfg.has_circular_refs
    report.update(config_id=cfg.id,changed=changed)
elif phase=='records':
    assert len(cfg)==1 and cfg.state=='draft'
    assert not e['hr.payslip'].search_count([('formula_config_id','=',cfg.id)])
    api._lock(cfg)
    cards=desk._cards(cfg.id)
    card_by_code={c['component']['code']:fid for fid,c in cards.items() if c.get('component')}
    Employee=e['hr.employee'].with_context(active_test=False)
    Contract=e['hr.contract'].with_context(active_test=False)
    old_ids={t:[] for t in ('hr_employee','hr_contract','hr_contract_advantage','res_partner_bank')}
    for table in old_ids:
        e.cr.execute('SELECT id FROM '+table+' ORDER BY id');old_ids[table]=[r[0] for r in e.cr.fetchall()]
    untouched={t:existing_rows(t,ids) for t,ids in old_ids.items()}
    people={};contracts={};changes=[]
    for record in records:
        code=record['code']
        assert not Employee.search_count(['|',('barcode','=',code),('employee_id','=',code)]),(code,'Identity was created concurrently')
        person=Employee.create(dict(name=record['name'],barcode=code,employee_id=code,company_id=company.id,
            payroll_country=country,active=True))
        end=record['contract_end']
        contract_state=('close' if end and date.fromisoformat(end)<date.today() else 'open') if record['payroll_eligible'] else 'draft'
        contract=Contract.create(dict(name=country+' client master — '+code,employee_id=person.id,company_id=company.id,
            date_start=record['contract_start'],date_end=end or False,wage=0,state=contract_state,payroll_country=country))
        people[code]=person;contracts[code]=contract
        for s in definition['rules']:
            fid=card_by_code.get(s['code']);value=record['values'].get(s['code'])
            if not fid or value is None or value=='':continue
            if s['kind']=='date':value=str(value)[:10]
            elif s['kind'] in {'text','identifier'}:value=str(int(value)) if isinstance(value,float) and value.is_integer() else str(value).strip()
            changes.append(dict(emp_id=person.id,field_id=fid,value=value))
    preview=desk.preview_changes(cfg.id,changes)
    assert not preview['counts']['refused'],[x for x in preview['items'] if x['status']=='refused']
    applied=desk.apply_changes(cfg.id,changes,note='Owner-authorized '+country+' payroll configuration from the supplied employee master and August payroll. Unique country identity, saved salary/settings and actual source dates. No payment or approval is authorized.',source='import')
    assert applied.get('ok') and not applied.get('refused'),applied
    if applied.get('pending'):
        request=e['biz.approval.request'].browse(applied.get('request_id')).exists()
        print('RECORD_REQUEST_DIAGNOSIS '+json.dumps(request.read([f for f in ('state','block_reason','apply_error','current_step_key') if f in request._fields]),default=str),flush=True)
    assert not applied.get('pending'),{k:applied.get(k) for k in ('reference','state','with_whom','route','block_note')}
    for record in records:
        person=people[record['code']];contract=contracts[record['code']]
        assert person.barcode==person.employee_id==record['code'] and person.name==record['name']
        if record['payroll_eligible']:
            assert abs(contract.wage-record['wage'])<.00001,(record['code'],contract.wage,record['wage'])
            assert contract.state in ('open','close'),(record['code'],contract.state)
            assert str(contract.date_end or '')==str(record['contract_end'] or ''),(record['code'],contract.date_end,record['contract_end'])
            assert contract.payroll_country==country
        else:
            assert contract.state=='draft','Unreviewed master-only profiles cannot silently join payroll.'
        if not record['profile_active']:person.active=False
    saved=e['pb.payroll.template.layout'].sudo().search([('config_id','=',cfg.id),('company_id','=',company.id)])
    assert len(saved)==1
    saved.payload=dict(saved.payload or {},preview_employee_ids=[people[r['code']].id for r in records if r['payroll_eligible']],preview_expected_count=len(fixtures))
    report.update(config_id=cfg.id,created_people=len(people),created_contracts=len(contracts),
        active_payroll=len(fixtures),master_only=len(records)-len(fixtures),records_reference=applied['reference'],values_written=applied['written'])
    assert {t:existing_rows(t,ids) for t,ids in old_ids.items()}==untouched,'Pre-existing employee, contract and bank records must remain unchanged.'
elif phase=='bankfill':
    assert len(cfg)==1 and country=='SG' and cfg.state=='active'
    assert not e['hr.payslip'].search_count([('formula_config_id','=',cfg.id)])
    api._lock(cfg)
    cards=desk._cards(cfg.id)
    card_by_code={c['component']['code']:fid for fid,c in cards.items() if c.get('component')}
    bank_specs=[s for s in definition['rules'] if s['destination'].startswith('b:')]
    changes=[];people=[]
    for record in records:
        if not record.get('bank_fill_from_payroll'):continue
        person=e['hr.employee'].search([('barcode','=',record['code']),('company_id','=',company.id)])
        assert len(person)==1 and not person.bank_account_ids,'Do not displace a bank account chosen by another session.'
        people.append(person.id)
        for s in bank_specs:
            value=record['values'].get(s['code'])
            if value:changes.append(dict(emp_id=person.id,field_id=card_by_code[s['code']],value=value))
    result=desk.apply_changes(cfg.id,changes,note='Complete the active Singapore profile whose HR master has no banking. Use the matched August payroll bank fields; no payment is authorized.',source='import')
    assert result.get('ok') and not result.get('pending') and not result.get('refused'),result
    assert all(e['hr.employee'].browse(i).bank_account_ids for i in people)
    report.update(config_id=cfg.id,people=len(people),values_written=result['written'],records_reference=result['reference'])
elif phase=='activate':
    assert len(cfg)==1 and cfg.state=='draft'
    assert not e['hr.formula.scheme.assignment'].search_count([('config_id','=',cfg.id)])
    assert not e['hr.payslip'].search_count([('formula_config_id','=',cfg.id)])
    api._lock(cfg)
    # Normal statutory publication route, never a raw state write or bypass.
    tables=cfg.rule_ids.mapped('tax_table_id')
    for table in tables.filtered(lambda t:t.state!='published'):
        answer=table.action_publish()
        assert table.state=='published',{'table':table.code,'answer':answer,'reason':'Use the published statutory approval route.'}
    constants={r.code:r.constant_value for r in cfg.rule_ids.filtered('tax_table_id')}
    refresh=e['hr.payroll.tax.refresh.wizard'].create(dict(config_id=cfg.id,asof='2026-08-01'))
    answer=refresh.action_refresh()
    assert str(cfg.statutory_asof)=='2026-08-01',{'answer':answer,'reason':'Use the published statutory refresh route.'}
    assert {r.code:r.constant_value for r in cfg.rule_ids.filtered('tax_table_id')}==constants,'The reviewed August constants changed during statutory refresh.'
    cfg.action_validate_formulas()
    assert not cfg.has_errors and not cfg.has_circular_refs
    old.action_archive()
    cfg.action_activate()
    assignment=e['hr.formula.scheme.assignment'].create(dict(config_id=cfg.id,cycle_type='regular',
        domain=repr([('company_id','=',company.id),('payroll_country','=',country)]),source='manual',confidence=1,
        note='Country and dated contract population. New hires follow normal employee/contract setup; no fixed employee ID list. Master-only Draft contracts require payroll review.'))
    august=api._roster(cfg,'2026-08')
    expected={r['code'] for r in records if r['payroll_eligible']}
    assert set(august.mapped('barcode'))==expected,(len(august),len(expected))
    for p in august:assert e['hr.payslip'].get_contract(p,'2026-08-01','2026-08-31'),p.barcode
    report.update(config_id=cfg.id,state=cfg.state,assignment_id=assignment.id,archived_configs=old.ids,
        august=len(august),september=len(api._roster(cfg,'2026-09')),october=len(api._roster(cfg,'2026-10')),statutory_tables=len(tables))
elif phase=='attach':
    assert len(cfg)==1
    path=root/('Rize_'+('Singapore' if country=='SG' else 'Indonesia')+'_Consolidated_Payroll_and_Master.xlsx')
    content=path.read_bytes()
    result=studio.import_mapping_read_headers(cfg.id,base64.b64encode(content).decode(),path.name)
    assert result.get('ok'),result
    assert result.get('formula_columns_hidden',0)>0,'Calculation outputs must remain excluded from source inputs.'
    # The importer sees other workbook tables too; only declared Consolidated
    # input keys are bound to payroll components.
    by={r.code:r for r in cfg.rule_ids}
    for s in definition['rules']:
        if s['type']=='input':assert by[s['code']].source_ids.filtered(lambda x:x.kind=='excel').mapped('key')==[s['source_key']]
    cfg.write(dict(import_sample_file=base64.b64encode(content),import_sample_filename=path.name))
    e['ir.attachment'].create(dict(name=path.name,res_model=cfg._name,res_id=cfg.id,type='binary',datas=base64.b64encode(content),mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))
    report.update(config_id=cfg.id,filename=path.name,sha256=hashlib.sha256(content).hexdigest(),formula_columns_hidden=result.get('formula_columns_hidden'))
elif phase=='verify':
    assert len(cfg)==1 and cfg.state=='active'
    by={r.code:r for r in cfg.rule_ids}
    assert set(by)==set(specs)
    for code,s in specs.items():
        assert by[code].column_type==s['type']
        if s['formula']:assert by[code].excel_formula==s['formula']
    august=api._roster(cfg,'2026-08')
    assert len(august)==len(fixtures)
    assert {r.barcode for r in august}=={r['code'] for r in records if r['payroll_eligible']}
    for p in august:
        record=next(r for r in records if r['code']==p.barcode)
        c=e['hr.payslip'].get_contract(p,'2026-08-01','2026-08-31')
        assert c and abs(c.wage-record['wage'])<.00001
    report.update(config_id=cfg.id,state=cfg.state,august=len(august),
        september=len(api._roster(cfg,'2026-09')),october=len(api._roster(cfg,'2026-10')))
else:raise AssertionError('Unknown phase: '+phase)
assert {t:digest(t) for t in transaction_tables}==baseline,'Configuration work cannot alter payroll transactions.'
report['payroll_transactions_unchanged']=True
if apply:e.cr.commit()
else:e.cr.rollback()
print('RIZE_MASTER_RESULT '+json.dumps(report,ensure_ascii=False,default=str),flush=True)
