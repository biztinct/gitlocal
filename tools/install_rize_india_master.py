"""Install the reviewed India definition in Rize only; rollback by default.

Run in the Rize Odoo shell as the real administrator. IN_SETUP_DIR contains
definition.json, payroll-fixtures.json and the client source-data.json. Set
IN_SETUP_APPLY=1 only after backing up the database. This step creates the new
definition and its comparison cases, never employees, contracts or pay runs.
"""
import hashlib
import json
import os
from pathlib import Path


assert env.cr.dbname == 'rize', 'Client data belongs only to the Rize database.'
root = Path(os.environ['IN_SETUP_DIR'])
definition = json.loads((root/'definition.json').read_text())
fixtures = json.loads((root/'payroll-fixtures.json').read_text())
assert definition['code'] == 'RIZE_INDIA_CLIENT_MASTER_2026'
company = env['res.company'].search([('name', '=', definition['company'])])
assert len(company) == 1
e = env(user=int(os.getenv('IN_SETUP_USER_ID', '2')),
        context=dict(env.context, allowed_company_ids=company.ids))
studio = e['pb.formula.studio']
templates = e['pb.payroll.templates']
assert studio._can_edit()
assert not e['hr.formula.config'].with_context(active_test=False).search_count([('code','=',definition['code'])])


def business_hashes():
    result = {}
    for table in ('hr_employee','hr_contract','hr_contract_advantage','res_partner_bank',
                  'hr_payslip','hr_payslip_run','pb_payroll_month_inputs'):
        e.cr.execute('SELECT row_to_json(t)::text FROM '+table+' t ORDER BY id')
        result[table] = hashlib.sha256('\n'.join(r[0] for r in e.cr.fetchall()).encode()).hexdigest()
    return result


baseline = business_hashes()
old = e['hr.formula.config'].with_context(active_test=False).search([('country_code','=','IN')])
old_fields = old.read(['name','code','state','active','import_sample_filename','import_sample_columns_json'])
old_rules = old.mapped('rule_ids').read(['code','name','excel_formula','column_type','is_contract_component','is_text_component'])
cfg = e['hr.formula.config'].create(dict(
    name=definition['name'],code=definition['code'],country_code='IN',company_id=company.id,
    state='draft',cycle_type='regular',source_priority='excel,records,api',
    description='<p>Calculation master: Final Rize Payroll August 2026. Employee master: India Employee Details, India worksheet.</p>'
                '<p>CTC includes employer PF. Annual variable is a target, not an automatic monthly payment. TDS, employee PF and profession tax are approved monthly inputs because the client supplies values without calculations.</p>'
                '<p>Visible Basic/HRA rounding adjustments preserve the source exceptions. August PF constants reproduce the historical workbook; review the applicable later-period statutory settings before live use.</p>'))
templates._lock(cfg)
by = {}
for i,spec in enumerate(definition['rules']):
    values=dict(config_id=cfg.id,code=spec['code'],name=spec['name'],sequence=(i+1)*10,
        column_type='input' if spec['type']=='formula' else spec['type'],
        component_type=spec['group'],value_kind=spec['kind'],value_kind_source='user',
        value_kind_reason='Reviewed against the client payroll and India employee master.',
        net_role=spec['role'],net_role_detail=spec['detail'],net_role_source='user',
        net_role_confidence='certain',net_role_reason=spec['note'],
        column_role='reference' if spec['group']=='Contract calculation' else 'payroll' if spec['tab'] or spec['type']!='input' else 'profile',
        column_role_source='user',is_required=spec['required'],
        appears_on_payslip=spec['role']!='info',
        visibility_rule='when_nonzero' if spec['role']!='info' else 'never',
        report_visible=True,
        number_format='currency' if spec['kind']=='money' else 'percentage' if spec['kind']=='rate' else 'number')
    if spec['value'] is not None:values['constant_value']=spec['value']
    rule = e['hr.formula.rule'].create(values)
    by[spec['code']] = rule
    if spec['type']=='input':
        rule.set_source_binding('excel',spec['source_key'],origin='user')
        rule.source_sheet_name='Consolidated'
        if spec['destination']:
            answer=studio.employee_mapping_create(cfg.id,'',rule.id,spec['destination'])
            assert answer.get('ok'),(spec['code'],answer)
            rule.write(dict(column_role='contract' if rule.is_contract_component or spec['destination'].startswith('f:hr.contract:') else 'profile',
                            column_role_source='user',net_role=spec['role'],net_role_detail=spec['detail'],
                            net_role_source='user',net_role_confidence='certain'))
    if spec['code'] in {'INCODE','INMASTERID','INNAME'}:
        rule.write({'column_role':'identity','column_role_source':'user'})
for spec in definition['rules']:
    if spec['formula']:
        by[spec['code']].write(dict(column_type='formula',excel_formula='='+spec['formula'].format(**{c:r.column_letter+'2' for c,r in by.items()})))
assert len(by)==len(definition['rules'])
assert not cfg.rule_ids.filtered(lambda r:r.column_type!='input' and (r.source_ids or r.is_contract_component or r.is_text_component))
catalog=templates._catalog(cfg)
ids={c['code']:c['id'] for c in catalog if c['code']}
layout=dict(time=[ids[c] for c in definition['time_order']],
            adjustments=[ids[c] for c in definition['adjustments_order']],
            records=[c['id'] for c in catalog if c['record_eligible']],
            available=[c['id'] for c in catalog if not c['record_eligible'] and c['id'] not in
                       [ids[k] for k in definition['time_order']+definition['adjustments_order']]])
assert templates.save_layout(cfg.id,layout)['ok']
comparisons=0
for i,record in enumerate(fixtures,1):
    sample=e['hr.formula.sample.data'].create(dict(config_id=cfg.id,name='Client August row '+str(record['row']),
        sequence=i,source_type='import',source_date='2026-08-01',
        input_values_json=json.dumps(record['values']),expected_inputs_json=json.dumps(record['values']),
        expected_values_json=json.dumps(record['expected']),expected_confirmed=True))
    errors={}
    computed=sample._evaluate_rules_with_dependencies(record['values'],readonly=True,errors=errors)
    assert not errors,(record['row'],errors)
    for code,value in record['expected'].items():
        assert abs(float(computed[code])-value)<.00001,(record['row'],code,computed[code],value)
        comparisons+=1
    assert computed['INREADY']=='Ready'
cfg.action_validate_formulas()
assert not cfg.has_errors and not cfg.has_circular_refs
health=cfg.value_kind_board()
assert health['review_count']==health['role_conflict_count']==health['drift_count']==0,health
tests=cfg.run_sample_tests()
assert tests['total']==tests['passed']==27 and tests['failed']==tests['pending']==0,tests
assert old.read(['name','code','state','active','import_sample_filename','import_sample_columns_json'])==old_fields
assert old.mapped('rule_ids').read(['code','name','excel_formula','column_type','is_contract_component','is_text_component'])==old_rules
assert business_hashes()==baseline,'Definition installation must not modify business records.'
report=dict(database='rize',config_id=cfg.id,code=cfg.code,state=cfg.state,
            rules=len(by),inputs=sum(r.column_type=='input' for r in cfg.rule_ids),
            formulas=sum(r.column_type=='formula' for r in cfg.rule_ids),
            input_sources=len(cfg.rule_ids.source_ids),native_mappings=e['hr.payslip.import.mapping'].search_count([('salary_structure_id','=',cfg.id)]),
            contract_components=len(cfg.rule_ids.filtered(lambda r:r.is_contract_component or r.is_text_component)),
            time=len(layout['time']),adjustments=len(layout['adjustments']),records=len(layout['records']),
            exact_calculation_checks=comparisons,scenarios=tests,business_unchanged=True,
            committed=os.getenv('IN_SETUP_APPLY')=='1')
if report['committed']:e.cr.commit()
else:e.cr.rollback()
print('IN_SETUP_RESULT '+json.dumps(report,ensure_ascii=False))
