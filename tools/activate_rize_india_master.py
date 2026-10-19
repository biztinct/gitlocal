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
cfg.action_validate_formulas()
assert not cfg.has_errors and not cfg.has_circular_refs
tests=cfg.run_sample_tests()
assert tests['total']==tests['passed']==27 and not tests['failed']
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
    pending_stipend=True,committed=os.getenv('IN_SETUP_APPLY')=='1')
if report['committed']:e.cr.commit()
else:e.cr.rollback()
print('IN_ACTIVATE_RESULT '+json.dumps(report,ensure_ascii=False))
