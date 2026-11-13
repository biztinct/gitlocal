"""Activate the reviewed Rize India scheme and country population.

Rize only. IN_SETUP_APPLY=1 persists; default rollback. Archives the previous
active India definition for reference, without deleting its components or
history. No monthly inputs, payslips, approvals or payments are created here.
"""
import hashlib,json,os
from pathlib import Path

assert env.cr.dbname=='rize'
root=Path(os.environ['IN_SETUP_DIR'])
plan=json.loads((root/'record-plan.json').read_text())
definition=json.loads((root/'definition.json').read_text())
e=env(user=int(os.getenv('IN_SETUP_USER_ID','2')),context=dict(env.context,allowed_company_ids=[1]))
cfg=e['hr.formula.config'].search([('code','=',definition['code'])])
assert len(cfg)==1 and cfg.state=='draft' and cfg.company_id.name=='Rize Farms'
assert not e['hr.formula.scheme.assignment'].search_count([('config_id','=',cfg.id)])
assert not e['hr.payslip'].search_count([('formula_config_id','=',cfg.id)])
api=e['pb.payroll.templates'];api._lock(cfg)
old=e['hr.formula.config'].search([('country_code','=','IN'),('state','=','active'),('id','!=',cfg.id)])
old_rules=old.rule_ids.read(['name','code','excel_formula','column_type','is_contract_component','is_text_component'])
assert all(not e['hr.payslip'].search_count([('formula_config_id','=',c.id)]) for c in old)
# Publish the reviewed final formulas before activating the new Draft. This
# also keeps installation and activation reproducible from the same metadata.
by={r.code:r for r in cfg.rule_ids}
assert set(by)=={r['code'] for r in definition['rules']}
for spec in definition['rules']:
    if spec['formula']:
        by[spec['code']].write(dict(excel_formula='='+spec['formula'].format(**{c:r.column_letter+'2' for c,r in by.items()}),
                                    column_role='reference' if spec['group']=='Contract calculation' else 'payroll',
                                    column_role_source='user'))
cfg.action_validate_formulas()
assert not cfg.has_errors and not cfg.has_circular_refs
tests=cfg.run_sample_tests()
assert tests['total']==tests['passed']==27 and not tests['failed'],tests
sample=cfg.sample_data_ids[:1]
baseline=json.loads(sample.input_values_json)
invalid_inputs=[dict(INPDAYS=32),dict(INWDAYS=0),dict(INANNVAR=-1),
                dict(INPFMODE='Unreviewed'),dict(INADAYS=1,INARREARS=0)]
for mutation in invalid_inputs:
    errors={}
    computed=sample._evaluate_rules_with_dependencies(dict(baseline,**mutation),readonly=True,errors=errors)
    assert computed.get('INREADY')!='Ready',(mutation,computed.get('INREADY'))
old.action_archive()
cfg.action_activate()
assignment=e['hr.formula.scheme.assignment'].create(dict(config_id=cfg.id,cycle_type='regular',
    domain=repr([('company_id','=',cfg.company_id.id),('payroll_country','=','IN')]),
    source='manual',confidence=1,
    note='India employee master is authoritative. Include this company’s India employments with contracts covering the chosen month. New India hires follow the normal country and contract setup; no fixed name or ID shortlist.'))
assert old.rule_ids.read(['name','code','excel_formula','column_type','is_contract_component','is_text_component'])==old_rules
expected={r['code'] for r in plan['records'] if r['active']}
august=api._roster(cfg,'2026-08')
september=api._roster(cfg,'2026-09')
assert set(august.mapped('barcode'))==expected and len(august)==27
ended={r['code'] for r in plan['records'] if r['active'] and r['values'].get('INDOR')}
assert len(ended)==1 and set(september.mapped('barcode'))==expected-ended
for person in august:
    native=e['hr.payslip'].get_contract(person,'2026-08-01','2026-08-31')
    assert native,(person.barcode,'The actual payslip resolver must accept the same historical population')
report=dict(database='rize',config_id=cfg.id,state=cfg.state,assignment_id=assignment.id,
    archived_configs=old.ids,august=27,september=26,scenarios=tests,
    invalid_input_flags=len(invalid_inputs),
    pending_stipend=True,committed=os.getenv('IN_SETUP_APPLY')=='1')
if report['committed']:e.cr.commit()
else:e.cr.rollback()
print('IN_ACTIVATE_RESULT '+json.dumps(report,ensure_ascii=False))
